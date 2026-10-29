"""Strict, non-secret manifest contract for the first S2 runtime bootstrap.

This module deliberately does not inspect or open the Store, provision keys, or
start services.  The privileged selector lives in tools/qa/select_wsl_bootstrap_runtime.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .contracts import ContractError, canonical_bytes

SCHEMA = 1
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
UNITS = (
    "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
    "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
)
UNIT_DIR = "/etc/systemd/system"
RUNTIME_LINK = "/opt/vst-runtime"
HELPER_BASE = "/usr/local/libexec"
PARENTS = {
    "/opt": (0, 0, 0o755),
    UNIT_DIR: (0, 0, 0o755),
    HELPER_BASE: (0, 0, 0o755),
}
MANIFEST_FIELDS = frozenset({
    "schema", "repository", "archive_sha256", "source_head", "spec_sha256", "old_runtime_tree_sha256",
    "runtime_path", "runtime_tree_sha256", "helper_path", "helper_head",
    "helper_source_sha256", "helper_binary_sha256", "helper_gid", "helper_mode",
    "helper_nlink", "old_selector", "units", "parents",
})
FILE_FIELDS = frozenset({"kind", "sha256", "uid", "gid", "mode", "size", "nlink"})
LINK_FIELDS = frozenset({"kind", "target", "uid", "gid", "mode"})
ABSENT_FIELDS = frozenset({"kind"})


def _fail(message: str) -> None:
    raise ContractError("runtime bundle: " + message)


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        _fail(f"{name} must be 64 lowercase hexadecimal characters")
    return value


def _head(value: object, name: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        _fail(f"{name} must be a full lowercase Git object id")
    return value


def _path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("/") or "\x00" in value:
        _fail(f"{name} must be an absolute POSIX path")
    parts = value.split("/")[1:]
    if any(part in ("", ".", "..") for part in parts):
        _fail(f"{name} is not canonical")
    return value


def _entry(value: object, name: str, *, allow_absent: bool) -> dict[str, Any]:
    if not isinstance(value, dict) or "kind" not in value:
        _fail(f"{name} fingerprint must be an object")
    kind = value["kind"]
    if kind == "absent" and allow_absent and set(value) == ABSENT_FIELDS:
        return value
    if kind == "file" and set(value) == FILE_FIELDS:
        _digest(value["sha256"], name + ".sha256")
        if any(type(value[k]) is not int or value[k] < 0 for k in ("uid", "gid", "mode", "size", "nlink")):
            _fail(f"{name} has invalid file metadata")
        if value["nlink"] != 1:
            _fail(f"{name} must have exactly one hard link")
        return value
    if kind == "symlink" and set(value) == LINK_FIELDS:
        _path(value["target"], name + ".target")
        if any(type(value[k]) is not int or value[k] < 0 for k in ("uid", "gid", "mode")):
            _fail(f"{name} has invalid link metadata")
        return value
    _fail(f"{name} fingerprint kind or fields are invalid")


def validate_manifest(value: object) -> dict[str, Any]:
    """Validate the exact canonical field set; this does not authorize its digest."""
    if not isinstance(value, dict) or set(value) != MANIFEST_FIELDS:
        _fail("manifest fields do not match schema 1")
    if type(value["schema"]) is not int or value["schema"] != SCHEMA:
        _fail("unsupported schema")
    if value["repository"] != "Virtual_scrum_team":
        _fail("repository identity is invalid")
    _head(value["source_head"], "source_head")
    _head(value["helper_head"], "helper_head")
    for key in ("archive_sha256", "spec_sha256", "runtime_tree_sha256", "old_runtime_tree_sha256",
                "helper_source_sha256", "helper_binary_sha256"):
        _digest(value[key], key)
    expected_runtime = "/opt/vst-runtime-" + value["source_head"]
    expected_helper = HELPER_BASE + "/vst-s4-worker-exec-" + value["helper_head"]
    if value["runtime_path"] != expected_runtime or value["helper_path"] != expected_helper:
        _fail("runtime/helper paths are not the fixed versioned destinations")
    if type(value["helper_gid"]) is not int or value["helper_gid"] != 988:
        _fail("helper gid is not the reviewed vst-runner gid")
    if type(value["helper_mode"]) is not int or value["helper_mode"] != 0o4750:
        _fail("helper mode is not the reviewed setgid executable mode")
    if type(value["helper_nlink"]) is not int or value["helper_nlink"] != 1:
        _fail("helper link count is invalid")
    _entry(value["old_selector"], "old_selector", allow_absent=False)
    if value["old_selector"]["kind"] != "symlink":
        _fail("bootstrap baseline requires the existing runtime selector symlink")
    if (value["old_selector"]["uid"] != 0 or value["old_selector"]["gid"] != 0
            or value["old_selector"]["mode"] != 0o777):
        _fail("old runtime selector must be a root-owned symlink")
    old_target = value["old_selector"]["target"]
    if not re.fullmatch(r"/opt/vst-runtime-[0-9a-f]{40}", old_target):
        _fail("old selector target is not a versioned runtime")
    units = value["units"]
    if not isinstance(units, dict) or set(units) != set(UNITS):
        _fail("unit map must contain exactly the six S2 unit names")
    for unit in UNITS:
        entry = units[unit]
        if not isinstance(entry, dict) or set(entry) != {"old", "new"}:
            _fail(f"unit {unit} must bind old and new fingerprints")
        _entry(entry["old"], unit + ".old", allow_absent=True)
        _entry(entry["new"], unit + ".new", allow_absent=False)
        if entry["new"]["kind"] != "file" or entry["new"]["uid"] != 0 or entry["new"]["gid"] != 0 or entry["new"]["mode"] != 0o644:
            _fail(f"new unit {unit} must be a root-owned regular 0644 file")
        if entry["old"]["kind"] == "file" and (entry["old"]["uid"] != 0 or entry["old"]["gid"] != 0 or entry["old"]["mode"] != 0o644):
            _fail(f"old unit {unit} must be root-owned regular 0644 or absent")
        if entry["old"]["kind"] == "symlink":
            _fail(f"old unit {unit} cannot be a symlink")
    parents = value["parents"]
    if not isinstance(parents, dict) or set(parents) != set(PARENTS):
        _fail("parent map must contain exactly the fixed installation parents")
    for path, expected in PARENTS.items():
        parent = parents[path]
        if (not isinstance(parent, dict) or set(parent) != {"uid", "gid", "mode"}
                or tuple(parent[k] for k in ("uid", "gid", "mode")) != expected
                or any(type(parent[k]) is not int for k in ("uid", "gid", "mode"))):
            _fail(f"parent metadata for {path} differs from the fixed root-owned contract")
    return value


def manifest_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(validate_manifest(value))).hexdigest()


def _fingerprint(path: str, *, absent: bool = False) -> dict[str, Any]:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if absent:
            return {"kind": "absent"}
        raise
    metadata = {"uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        if not target.startswith("/"):
            _fail(f"{path} symlink target is not absolute")
        return {"kind": "symlink", "target": target, **metadata}
    if not stat.S_ISREG(info.st_mode):
        _fail(f"{path} is neither a regular file nor symlink")
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"kind": "file", "sha256": digest.hexdigest(), "size": info.st_size,
            "nlink": info.st_nlink, **metadata}


def tree_sha256(root: str) -> str:
    """Hash complete staged tree contents and metadata without following links."""
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != 0 or stat.S_IMODE(root_info.st_mode) != 0o755:
        _fail("staged runtime root must be a root-owned 0755 directory")
    records: list[dict[str, Any]] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        files.sort()
        for name in dirs + files:
            path = os.path.join(current, name)
            info = os.lstat(path)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if stat.S_ISDIR(info.st_mode):
                if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o755:
                    _fail(f"staged runtime directory metadata is unsafe: {rel}")
                records.append({"path": rel, "kind": "directory", "uid": info.st_uid,
                                "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)})
            elif stat.S_ISREG(info.st_mode):
                if info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o644 or info.st_nlink != 1:
                    _fail(f"staged runtime file metadata is unsafe: {rel}")
                fp = _fingerprint(path)
                records.append({"path": rel, **fp})
            else:
                _fail(f"staged runtime contains a link or special object: {rel}")
    return hashlib.sha256(canonical_bytes(records)).hexdigest()


def build_manifest(*, source_head: str, archive_sha256: str, spec_sha256: str,
                   helper_head: str, helper_source_sha256: str) -> dict[str, Any]:
    """Build a review candidate after stage-only; caller must review its digest before selection."""
    _head(source_head, "source_head")
    _head(helper_head, "helper_head")
    for value, name in ((archive_sha256, "archive_sha256"), (spec_sha256, "spec_sha256"),
                        (helper_source_sha256, "helper_source_sha256")):
        _digest(value, name)
    runtime_path = "/opt/vst-runtime-" + source_head
    helper_path = HELPER_BASE + "/vst-s4-worker-exec-" + helper_head
    if not os.path.lexists(runtime_path):
        _fail("stage-only runtime is absent")
    if not os.path.lexists(helper_path):
        _fail("stage-only helper is absent")
    marker_path = os.path.join(runtime_path, ".vst-runtime-manifest.json")
    marker = _read_small_json(marker_path)
    if marker != {"archive_sha256": archive_sha256, "head": source_head, "schema": 1}:
        _fail("staged runtime source marker does not match the candidate")
    spec_path = os.path.join(runtime_path, "docs", "SANDBOX_SPEC.md")
    spec_info = _fingerprint(spec_path)
    if spec_info["kind"] != "file" or spec_info["uid"] != 0 or spec_info["gid"] != 0 or spec_info["mode"] != 0o644:
        _fail("staged sandbox specification metadata differs from runtime contract")
    observed_spec = spec_info["sha256"]
    if observed_spec != spec_sha256:
        _fail("staged sandbox specification digest does not match the candidate")
    selector = _fingerprint(RUNTIME_LINK)
    old_target = selector.get("target")
    if not isinstance(old_target, str) or not re.fullmatch(r"/opt/vst-runtime-[0-9a-f]{40}", old_target):
        _fail("old selector target is not a versioned runtime")
    old_tree_digest = tree_sha256(old_target)
    units: dict[str, Any] = {}
    for unit in UNITS:
        units[unit] = {
            "old": _fingerprint(os.path.join(UNIT_DIR, unit), absent=True),
            "new": _fingerprint(os.path.join(runtime_path, "tools/vst/systemd", unit)),
        }
    helper = _fingerprint(helper_path)
    if (helper["kind"] != "file" or helper["uid"] != 0 or helper["gid"] != 988
            or helper["mode"] != 0o4750 or os.lstat(helper_path).st_nlink != 1):
        _fail("staged worker helper metadata differs from reviewed root:vst-runner 4750 contract")
    value = {
        "schema": SCHEMA, "repository": "Virtual_scrum_team", "archive_sha256": archive_sha256,
        "source_head": source_head, "spec_sha256": spec_sha256, "runtime_path": runtime_path,
        "runtime_tree_sha256": tree_sha256(runtime_path), "old_runtime_tree_sha256": old_tree_digest,
        "helper_path": helper_path,
        "helper_head": helper_head, "helper_source_sha256": helper_source_sha256,
        "helper_binary_sha256": helper["sha256"], "helper_gid": 988, "helper_mode": 0o4750,
        "helper_nlink": 1, "old_selector": selector, "units": units,
        "parents": {path: {"uid": uid, "gid": gid, "mode": mode}
                    for path, (uid, gid, mode) in PARENTS.items()},
    }
    return validate_manifest(value)


def load_canonical_manifest(path: str) -> dict[str, Any]:
    """Read a bounded regular manifest and reject duplicate keys/noncanonical bytes."""
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
        _fail("manifest must be a root-owned mode-0600 regular file")
    if info.st_size > 1024 * 1024:
        _fail("manifest exceeds one MiB")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            _fail("manifest changed while opening")
        raw = os.read(fd, 1024 * 1024 + 1)
    finally:
        os.close(fd)
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                _fail("manifest contains duplicate JSON fields")
            result[key] = item
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: _fail("manifest contains non-finite number"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("runtime bundle: manifest is not valid UTF-8 JSON") from exc
    validated = validate_manifest(value)
    if raw not in (canonical_bytes(validated), canonical_bytes(validated) + b"\n"):
        _fail("manifest bytes are not canonical JSON")
    return validated


def _read_small_json(path: str) -> object:
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o644:
        _fail("staged source marker must be root-owned mode-0644 regular file")
    if info.st_size > 4096:
        _fail("staged source marker exceeds its bound")
    with open(path, "rb") as stream:
        raw = stream.read(4097)
    try:
        def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in items:
                if key in result:
                    _fail("staged source marker contains duplicate fields")
                result[key] = item
            return result
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: _fail("staged source marker contains non-finite value"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("runtime bundle: staged source marker is invalid JSON") from exc

