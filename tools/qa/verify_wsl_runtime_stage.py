"""Verify a root-owned S2 runtime stage against its reviewed source map."""
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
MANIFEST = ".vst-runtime-manifest.json"
MAX_SOURCE_MANIFEST_BYTES = 8 * 1024 * 1024


def _fail(message: str) -> None:
    raise SystemExit("runtime stage verification failed: " + message)


def _hash_file(path: str, info: os.stat_result) -> tuple[str, int]:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or opened.st_uid != 0 or opened.st_gid != 0
                or stat.S_IMODE(opened.st_mode) != 0o644
                or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)):
            _fail("staged file changed type or identity while opening")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
             after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode))
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns,
                    opened.st_uid, opened.st_gid, stat.S_IMODE(opened.st_mode))):
            _fail("staged file changed while hashing")
        return digest.hexdigest(), size
    finally:
        os.close(fd)


def _expected_runtime(members: object) -> dict[str, dict[str, Any]]:
    if not isinstance(members, dict) or not members:
        _fail("reviewed source member map is absent")
    for name, entry in members.items():
        if (not isinstance(name, str) or not name or name.startswith("/")
                or "\\" in name or any(part in ("", ".", "..") for part in name.split("/"))
                or not isinstance(entry, dict)):
            _fail("reviewed source map contains an invalid path or entry")
        if entry == {"kind": "dir"}:
            continue
        if (set(entry) != {"kind", "sha256", "size"} or entry.get("kind") != "file"
                or not isinstance(entry.get("sha256"), str)
                or not HEX64.fullmatch(entry["sha256"])
                or type(entry.get("size")) is not int or entry["size"] < 0):
            _fail("reviewed source map contains an invalid file fingerprint")
    allowed_files = {
        "docs/SANDBOX_SPEC.md", "tools/qa/install_wsl_runner_runtime.sh",
        "tools/qa/install_wsl_worker_helper.sh", "tools/qa/verify_wsl_source_bundle.py",
        "tools/qa/verify_wsl_runtime_stage.py", "tools/qa/worker_exec.c",
    }
    for name, entry in members.items():
        allowed = (name in allowed_files or name.startswith("tools/vst/")
                   or name in {"tools", "tools/vst", "tools/qa", "docs"})
        if not allowed:
            _fail("reviewed source map contains a path outside the runtime allowlist")
        if entry == {"kind": "dir"}:
            if not (name in {"tools", "tools/vst", "tools/qa", "docs"}
                    or name.startswith("tools/vst/")):
                _fail("reviewed source map contains a disallowed directory")
            continue
        if (set(entry) != {"kind", "sha256", "size"} or entry.get("kind") != "file"
                or not isinstance(entry.get("sha256"), str)
                or not HEX64.fullmatch(entry["sha256"])
                or type(entry.get("size")) is not int or entry["size"] < 0):
            _fail("reviewed source map contains an invalid file fingerprint")
    expected = {
        name: entry for name, entry in members.items()
        if name in {"tools", "tools/vst", "docs"}
        or name.startswith("tools/vst/") or name.startswith("docs/")
    }
    if not expected or "tools/vst" not in expected or "docs" not in expected:
        _fail("reviewed source map lacks runtime roots")
    required = {
        "docs/SANDBOX_SPEC.md", "tools/vst/runner.py", "tools/vst/signer.py",
        "tools/vst/store.py", "tools/vst/supervisor.py", "tools/vst/runner_service.py",
        "tools/vst/supervisor_service.py", "tools/vst/execution_grant.py",
        "tools/vst/runner_fence.py", "tools/vst/dispatcher_service.py",
        "tools/vst/dispatch_instruction.py", "tools/vst/dispatch_owner_client.py",
        "tools/vst/dispatch_owner_service.py", "tools/vst/dispatch_owner_latch.py",
        "tools/vst/systemd/vst-supervisor.service", "tools/vst/systemd/vst-signer.service",
        "tools/vst/systemd/vst-runner.service", "tools/vst/systemd/vst-dispatcher.service",
        "tools/vst/systemd/vst-dispatch-owner.service",
        "tools/vst/systemd/vst-dispatch-owner.socket",
    }
    if not required <= expected.keys():
        _fail("reviewed source map lacks a required runtime artifact")
    return expected


def _read_root_json(path: Path, *, mode: int, maximum: int) -> dict[str, Any]:
    before = os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_uid != 0 or before.st_gid != 0
            or stat.S_IMODE(before.st_mode) != mode or before.st_nlink != 1
            or before.st_size > maximum):
        _fail("root-owned JSON artifact has invalid metadata")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if ((opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or opened.st_uid != 0 or opened.st_gid != 0
                or stat.S_IMODE(opened.st_mode) != mode):
            _fail("root-owned JSON artifact changed while opening")
        chunks = []
        size = 0
        while True:
            chunk = os.read(fd, min(65536, maximum + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                _fail("root-owned JSON artifact exceeds its size bound")
        after = os.fstat(fd)
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
             after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode))
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns,
                    opened.st_uid, opened.st_gid, stat.S_IMODE(opened.st_mode))
                or size != before.st_size):
            _fail("root-owned JSON artifact changed while reading")
    finally:
        os.close(fd)
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                _fail("root-owned JSON artifact has duplicate fields")
            result[key] = value
        return result
    try:
        value = json.loads(b"".join(chunks), object_pairs_hook=pairs,
                           parse_constant=lambda _value: _fail("root-owned JSON has non-finite values"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit("runtime stage verification failed: root-owned JSON is invalid") from exc
    if not isinstance(value, dict):
        _fail("root-owned JSON artifact must be an object")
    return value


def verify_staged_runtime(stage: Path, source_manifest_path: Path, *,
                          expected_head: str, archive_sha256: str,
                          plan_sha256: str, inventory_sha256: str) -> dict[str, Any]:
    if (not HEX40.fullmatch(expected_head)
            or not all(HEX64.fullmatch(value) for value in
                       (archive_sha256, plan_sha256, inventory_sha256))):
        _fail("requested source identity is malformed")
    source_manifest = _read_root_json(source_manifest_path, mode=0o600,
                                      maximum=MAX_SOURCE_MANIFEST_BYTES)
    if (set(source_manifest) != {"archive_members", "archive_sha256", "compiler_path",
                                "compiler_resolved_path", "compiler_sha256",
                                "compiler_symlink_target", "head", "inventory_sha256",
                                "plan_sha256", "schema"}
            or source_manifest.get("schema") != 3
            or source_manifest.get("head") != expected_head
            or source_manifest.get("archive_sha256") != archive_sha256
            or source_manifest.get("plan_sha256") != plan_sha256
            or source_manifest.get("inventory_sha256") != inventory_sha256):
        _fail("source manifest differs from the exact reviewed identity")
    compiler_sha = source_manifest.get("compiler_sha256")
    if (not isinstance(compiler_sha, str) or not HEX64.fullmatch(compiler_sha)
            or source_manifest.get("compiler_path") != "/usr/bin/cc"
            or source_manifest.get("compiler_symlink_target") != "/etc/alternatives/cc"
            or not isinstance(source_manifest.get("compiler_resolved_path"), str)
            or not re.fullmatch(r"/usr/bin/[A-Za-z0-9._+-]+",
                                source_manifest["compiler_resolved_path"])):
        _fail("source manifest compiler digest is malformed")
    expected = _expected_runtime(source_manifest.get("archive_members"))
    root_info = os.lstat(stage)
    if (not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != 0 or root_info.st_gid != 0
            or stat.S_IMODE(root_info.st_mode) != 0o755):
        _fail("staged runtime root must be root:root mode 0755")
    actual: dict[str, dict[str, Any]] = {}
    for current, directories, files in os.walk(stage, topdown=True, followlinks=False):
        directories.sort()
        files.sort()
        for name in directories + files:
            path = os.path.join(current, name)
            relative = os.path.relpath(path, stage).replace(os.sep, "/")
            if relative == MANIFEST:
                continue
            info = os.lstat(path)
            if stat.S_ISDIR(info.st_mode):
                if (info.st_uid != 0 or info.st_gid != 0
                        or stat.S_IMODE(info.st_mode) != 0o755):
                    _fail("staged directory owner or mode is invalid: " + relative)
                actual[relative] = {"kind": "dir"}
            elif stat.S_ISREG(info.st_mode):
                if (info.st_uid != 0 or info.st_gid != 0
                        or stat.S_IMODE(info.st_mode) != 0o644 or info.st_nlink != 1):
                    _fail("staged file owner, mode, or link count is invalid: " + relative)
                digest, size = _hash_file(path, info)
                actual[relative] = {"kind": "file", "sha256": digest, "size": size}
            else:
                _fail("staged tree contains a symlink or special object: " + relative)
    if actual != expected:
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        changed = sorted(name for name in expected.keys() & actual.keys()
                         if expected[name] != actual[name])
        _fail("tree differs from source map (missing=%r extra=%r changed=%r)" %
              (missing[:5], extra[:5], changed[:5]))
    if sorted(os.listdir(stage)) != [MANIFEST, "docs", "tools"]:
        _fail("staged top-level entries differ from the fixed layout")
    marker_path = stage / MANIFEST
    marker_info = os.lstat(marker_path)
    if (not stat.S_ISREG(marker_info.st_mode) or marker_info.st_uid != 0
            or marker_info.st_gid != 0 or stat.S_IMODE(marker_info.st_mode) != 0o644
            or marker_info.st_nlink != 1 or marker_info.st_size > 4096):
        _fail("runtime marker metadata is invalid")
    marker = _read_root_json(marker_path, mode=0o644, maximum=4096)
    expected_marker = {
        "archive_sha256": archive_sha256,
        "compiler_path": source_manifest.get("compiler_path"),
        "compiler_resolved_path": source_manifest.get("compiler_resolved_path"),
        "compiler_sha256": compiler_sha,
        "compiler_symlink_target": source_manifest.get("compiler_symlink_target"),
        "head": expected_head, "inventory_sha256": inventory_sha256,
        "plan_sha256": plan_sha256, "schema": 3,
    }
    if marker != expected_marker:
        _fail("runtime marker differs from source and target provenance")
    return marker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--inventory-sha256", required=True)
    args = parser.parse_args()
    verify_staged_runtime(Path(args.stage), Path(args.source_manifest),
                          expected_head=args.expected_head,
                          archive_sha256=args.archive_sha256,
                          plan_sha256=args.plan_sha256,
                          inventory_sha256=args.inventory_sha256)
    print("verified staged runtime against exact reviewed source map")


if __name__ == "__main__":
    main()
