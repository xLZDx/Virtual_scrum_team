"""Fail-closed verification of the reviewed S2 runtime source bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_NAME = ".vst-source-manifest.json"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 50_000
ALLOWED_FILES = frozenset({
    "docs/SANDBOX_SPEC.md",
    "tools/qa/install_wsl_runner_runtime.sh",
    "tools/qa/install_wsl_worker_helper.sh",
    "tools/qa/verify_wsl_source_bundle.py",
    "tools/qa/verify_wsl_runtime_stage.py",
    "tools/qa/worker_exec.c",
})
UNITS = (
    "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
    "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
)


def _fail(message: str) -> None:
    raise SystemExit("source bundle verification failed: " + message)


def _pairs_no_duplicates(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            _fail("manifest has duplicate JSON fields")
        result[key] = value
    return result


def _read_manifest(path: Path) -> dict[str, Any]:
    info = os.lstat(path)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1 or info.st_size > MAX_MANIFEST_BYTES):
        _fail("manifest must be a bounded root-owned mode-0600 single-link regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            _fail("manifest changed while opening")
        raw = os.read(fd, MAX_MANIFEST_BYTES + 1)
    finally:
        os.close(fd)
    if len(raw) != info.st_size or len(raw) > MAX_MANIFEST_BYTES:
        _fail("manifest changed or exceeded its size limit while reading")
    try:
        value = json.loads(raw, object_pairs_hook=_pairs_no_duplicates,
                           parse_constant=lambda _value: _fail("manifest contains a non-finite value"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit("source bundle verification failed: manifest is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        _fail("manifest must be an object")
    return value


def _valid_relative_path(name: object) -> bool:
    return (isinstance(name, str) and bool(name) and not name.startswith("/")
            and "\\" not in name
            and all(part not in ("", ".", "..") for part in name.split("/")))


def _validate_members(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict) or not 0 < len(value) <= MAX_ENTRIES:
        _fail("archive member map is missing, empty, or too large")
    result: dict[str, dict[str, Any]] = {}
    for name, entry in value.items():
        if not _valid_relative_path(name) or name == MANIFEST_NAME:
            _fail("archive member path is not canonical")
        if not isinstance(entry, dict):
            _fail("archive member record must be an object")
        if entry == {"kind": "dir"}:
            if not (name in {"tools", "tools/vst", "tools/qa", "docs"}
                    or name.startswith("tools/vst/")):
                _fail("archive directory is outside the fixed source allowlist")
            result[name] = entry
            continue
        if set(entry) != {"kind", "sha256", "size"} or entry.get("kind") != "file":
            _fail("archive member has an unsupported type or field set")
        if not isinstance(entry.get("sha256"), str) or not HEX64.fullmatch(entry["sha256"]):
            _fail("archive member digest is invalid")
        if type(entry.get("size")) is not int or entry["size"] < 0:
            _fail("archive member size is invalid")
        if not (name in ALLOWED_FILES or name.startswith("tools/vst/")):
            _fail("archive file is outside the fixed source allowlist")
        result[name] = entry
    required = set(ALLOWED_FILES) | {
        "tools/vst/runner.py", "tools/vst/signer.py", "tools/vst/store.py",
        "tools/vst/supervisor.py", "tools/vst/runner_service.py",
        "tools/vst/supervisor_service.py", "tools/vst/execution_grant.py",
        "tools/vst/runner_fence.py", "tools/vst/dispatcher_service.py",
        "tools/vst/dispatch_instruction.py", "tools/vst/dispatch_owner_client.py",
        "tools/vst/dispatch_owner_service.py", "tools/vst/dispatch_owner_latch.py",
    }
    required.update("tools/vst/systemd/" + unit for unit in UNITS)
    file_names = {name for name, entry in result.items() if entry["kind"] == "file"}
    if not required <= file_names:
        _fail("reviewed source plan is missing a required runtime artifact")
    return result


def _hash_regular_file(path: str, before: os.stat_result) -> tuple[str, int]:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            _fail("source file changed type or identity while opening")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)):
            _fail("source file changed while hashing")
        return digest.hexdigest(), size
    finally:
        os.close(fd)


def _scan_bundle(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}

    def onerror(error: OSError) -> None:
        raise error

    for current, directories, files in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
        directories.sort()
        files.sort()
        for name in directories + files:
            path = os.path.join(current, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            if relative == MANIFEST_NAME:
                continue
            info = os.lstat(path)
            if stat.S_ISDIR(info.st_mode):
                result[relative] = {"kind": "dir"}
            elif stat.S_ISREG(info.st_mode):
                digest, size = _hash_regular_file(path, info)
                result[relative] = {"kind": "file", "sha256": digest, "size": size}
            else:
                _fail("source tree contains a symlink or special object: " + relative)
            if len(result) > MAX_ENTRIES:
                _fail("source tree has too many entries")
    return result


def verify_source_bundle(root: Path, *, expected_head: str,
                         expected_archive_sha256: str,
                         expected_plan_sha256: str,
                         expected_inventory_sha256: str) -> dict[str, Any]:
    root = Path(root)
    try:
        info = os.lstat(root)
    except OSError as exc:
        raise SystemExit("source bundle verification failed: bundle root is unavailable") from exc
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        _fail("bundle root must be a root-owned mode-0700 directory")
    root = root.resolve(strict=True)
    if not HEX40.fullmatch(expected_head):
        _fail("expected source revision is invalid")
    if (not HEX64.fullmatch(expected_archive_sha256)
            or not HEX64.fullmatch(expected_plan_sha256)
            or not HEX64.fullmatch(expected_inventory_sha256)):
        _fail("expected source digest is invalid")
    manifest = _read_manifest(root / MANIFEST_NAME)
    if set(manifest) != {"archive_members", "archive_sha256", "compiler_path",
                         "compiler_resolved_path", "compiler_sha256", "compiler_symlink_target",
                         "head", "inventory_sha256", "plan_sha256", "schema"}:
        _fail("manifest field set differs from reviewed schema")
    if (manifest["schema"] != 3 or manifest["head"] != expected_head
            or manifest["archive_sha256"] != expected_archive_sha256
            or manifest["plan_sha256"] != expected_plan_sha256
            or manifest["inventory_sha256"] != expected_inventory_sha256
            or manifest["compiler_path"] != "/usr/bin/cc"
            or manifest["compiler_symlink_target"] != "/etc/alternatives/cc"
            or not isinstance(manifest["compiler_resolved_path"], str)
            or not re.fullmatch(r"/usr/bin/[A-Za-z0-9._+-]+", manifest["compiler_resolved_path"])
            or not isinstance(manifest["compiler_sha256"], str)
            or not HEX64.fullmatch(manifest["compiler_sha256"])):
        _fail("manifest identity does not match the reviewed source plan")
    expected = _validate_members(manifest["archive_members"])
    actual = _scan_bundle(root)
    if actual != expected:
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        changed = sorted(name for name in expected.keys() & actual.keys()
                         if expected[name] != actual[name])
        _fail("archive member map differs (missing=%r extra=%r changed=%r)" %
              (missing[:5], extra[:5], changed[:5]))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    args = parser.parse_args()
    verify_source_bundle(Path(args.root), expected_head=args.expected_head,
                         expected_archive_sha256=args.archive_sha256,
                         expected_plan_sha256=args.plan_sha256,
                         expected_inventory_sha256=args.inventory_sha256)
    print("verified exact reviewed source bundle")


if __name__ == "__main__":
    main()
