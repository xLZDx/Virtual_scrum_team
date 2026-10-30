#!/usr/bin/env python3
"""Apply only the reviewed non-secret S2 runtime configuration to Ubuntu-24.04 WSL."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BUNDLE = REPO / "docs/sdlc/runtime-config"
INVENTORY_SCHEMA = "VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1"
CONFIG_ROOT = "/etc/vst-runner"
SYSTEMD_ROOT = "/etc/systemd/system"
TASK_REPOSITORY_ROOT = "/var/lib/vst-runner/repository"
TASK_REPOSITORY_ARCHIVE_FORMAT = "canonical-git-tree-tar-v1"
MAX_APPLY_PAYLOAD_BYTES = 16 * 1024 * 1024
RUNTIME_SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"
BUNDLE_MANIFEST_SHA256 = "2d0c7bcfdd92b3cffa3c9e1344d87f5d34cc690d65006298087d897cf5635d8c"
INSTALLATION_LAYOUT_SHA256 = "f403052cb26e6d635d7566fe25337e4c3fa18bf83c778dc600b807689b405d8f"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _git_blob(commit: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "show", f"{commit}:{relative_path}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise ValueError("committed S2 configuration blob is unavailable: " + relative_path)
    return result.stdout


def _build_task_source_archive(commit: str) -> bytes:
    if not _HEX40.fullmatch(commit):
        raise ValueError("task source commit must be a full lowercase Git object id")
    tree = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "ls-tree", "-rz",
         "--full-tree", "-r", commit],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if tree.returncode:
        raise ValueError("cannot enumerate the pinned task-source Git tree")
    records: list[tuple[str, str, bytes]] = []
    directories = {"task-source"}
    seen: set[str] = set()
    for raw_record in tree.stdout.split(b"\0"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        fields = metadata.split(b" ")
        if not separator or len(fields) != 3 or fields[1] != b"blob":
            raise ValueError("task source contains an unsupported Git tree entry")
        mode, object_id = fields[0], fields[2]
        if mode not in (b"100644", b"100755") or not re.fullmatch(rb"[0-9a-f]{40}", object_id):
            raise ValueError("task source contains a symlink, submodule, or unsupported file mode")
        try:
            relative = raw_path.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("task source path is not portable UTF-8") from exc
        parts = relative.split("/")
        if (not relative or relative.startswith("/") or "\\" in relative
                or any(part in ("", ".", "..") for part in parts)):
            raise ValueError("task source contains a path outside the portable repository root")
        if relative in seen:
            raise ValueError("task source contains a duplicate path")
        seen.add(relative)
        for count in range(1, len(parts)):
            directories.add("task-source/" + "/".join(parts[:count]))
        records.append((relative, mode.decode("ascii"), object_id))
    if not records or len(records) + len(directories) > 4096:
        raise ValueError("task source has an empty or oversized Git tree")

    request = b"".join(object_id + b"\n" for _relative, _mode, object_id in records)
    blobs = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "cat-file", "--batch"],
        input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if blobs.returncode:
        raise ValueError("cannot read the exact pinned task-source blobs")
    content_by_path: dict[str, tuple[int, bytes]] = {}
    cursor = 0
    total = 0
    for relative, mode, object_id in records:
        header_end = blobs.stdout.find(b"\n", cursor)
        if header_end < 0:
            raise ValueError("Git returned a truncated task-source blob header")
        header = blobs.stdout[cursor:header_end].split(b" ")
        if len(header) != 3 or header[0] != object_id or header[1] != b"blob":
            raise ValueError("Git returned a task-source blob with the wrong identity")
        try:
            size = int(header[2])
        except ValueError as exc:
            raise ValueError("Git returned a task-source blob with an invalid size") from exc
        if size < 0 or size > 8 * 1024 * 1024:
            raise ValueError("task-source file exceeds the fixed per-file limit")
        start = header_end + 1
        end = start + size
        if end >= len(blobs.stdout) or blobs.stdout[end:end + 1] != b"\n":
            raise ValueError("Git returned a truncated task-source blob")
        data = blobs.stdout[start:end]
        total += size
        if total > 32 * 1024 * 1024:
            raise ValueError("task-source Git tree exceeds the fixed expanded-size limit")
        content_by_path[relative] = (0o755 if mode == "100755" else 0o644, data)
        cursor = end + 1
    if cursor != len(blobs.stdout):
        raise ValueError("Git returned unexpected trailing task-source bytes")

    output = io.BytesIO()
    try:
        with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            directory_order = sorted(directories, key=lambda value: (value.count("/"), value))
            for name in directory_order:
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.size = 0
                archive.addfile(info)
            for relative, _mode, _object_id in records:
                file_mode, data = content_by_path[relative]
                info = tarfile.TarInfo("task-source/" + relative)
                info.type = tarfile.REGTYPE
                info.mode = file_mode
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    except (OSError, tarfile.TarError) as exc:
        raise ValueError("task-source paths cannot be represented in the fixed USTAR format") from exc
    archive_bytes = output.getvalue()
    if len(archive_bytes) > MAX_APPLY_PAYLOAD_BYTES:
        raise ValueError("canonical task-source archive exceeds the fixed transfer limit")
    return archive_bytes


def _current_inventory_validation_identity() -> tuple[str, str]:
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True,
    )
    repo_head = head.stdout.strip()
    if head.returncode or not _HEX40.fullmatch(repo_head):
        raise ValueError("cannot establish the exact committed inventory-validation HEAD")
    capture_path = "tools/vst/preflight_capture.py"
    committed_capture = _git_blob(repo_head, capture_path)
    working_capture = (REPO / capture_path).read_bytes()
    if committed_capture != working_capture:
        raise ValueError("runtime capture implementation differs from the committed inventory-validation HEAD")
    return repo_head, _sha(committed_capture)


def _load_committed_inventory_validator(repo_head: str):
    relative_path = "tools/qa/verify_s2_runtime_config_inventory.py"
    committed_source = _git_blob(repo_head, relative_path)
    working_path = REPO / relative_path
    if working_path.read_bytes() != committed_source:
        raise ValueError("runtime inventory validator differs from the exact committed Git blob")
    namespace = {"__file__": str(working_path), "__name__": "_vst_s2_inventory_validator"}
    exec(compile(committed_source, str(working_path), "exec", dont_inherit=True), namespace)
    validator = namespace.get("validate_inventory")
    if not callable(validator):
        raise ValueError("committed runtime inventory validator has no validation entry point")
    return validator


def _inventory_fingerprint(value: dict[str, Any]) -> dict[str, Any]:
    state = value.get("state")
    if state in ("absent", "ABSENT"):
        return {"state": "absent"}
    if state not in ("file", "PRESENT") or value.get("kind", "regular") not in ("regular", "file"):
        raise ValueError("target inventory contains a non-regular configuration destination")
    mode = value.get("mode")
    if isinstance(mode, str):
        try:
            mode = int(mode, 8)
        except ValueError as exc:
            raise ValueError("target inventory mode is invalid") from exc
    return {"state": "file", "uid": value.get("uid"), "gid": value.get("gid"),
            "mode": mode, "size": value.get("size"), "sha256": value.get("sha256")}


def build_payload(
        inventory_path: Path, expected_inventory_sha256: str, source_commit: str, *,
        expected_repo_head: str | None = None,
        expected_capture_sha256: str | None = None) -> bytes:
    if not _HEX64.fullmatch(expected_inventory_sha256):
        raise ValueError("expected inventory digest must be lowercase SHA-256")
    if not _HEX40.fullmatch(source_commit):
        raise ValueError("source commit must be a full lowercase Git object id")
    bundle_bytes = _git_blob(source_commit, "docs/sdlc/runtime-config/bundle-manifest.json")
    layout_bytes = _git_blob(source_commit, "docs/sdlc/runtime-config/installation-layout.json")
    if _sha(bundle_bytes) != BUNDLE_MANIFEST_SHA256 or _sha(layout_bytes) != INSTALLATION_LAYOUT_SHA256:
        raise ValueError("committed config bundle differs from the pinned S2 candidate")
    inventory_bytes = inventory_path.read_bytes()
    if _sha(inventory_bytes) != expected_inventory_sha256:
        raise ValueError("target inventory differs from its exact SHA-256 pin")
    inventory = json.loads(inventory_bytes)
    if (expected_repo_head is None) != (expected_capture_sha256 is None):
        raise ValueError("inventory validator HEAD and runtime capture digest must be supplied together")
    if expected_repo_head is not None and expected_capture_sha256 is not None:
        validate_inventory = _load_committed_inventory_validator(expected_repo_head)
        validate_inventory(
            inventory,
            expected_repo_head=expected_repo_head,
            expected_capture_sha256=expected_capture_sha256,
        )
    if (not isinstance(inventory, dict)
            or inventory.get("schema") != INVENTORY_SCHEMA
            or inventory.get("source_head", inventory.get("runtime_source_head")) != RUNTIME_SOURCE_HEAD
            or not isinstance(inventory.get("configuration_files"), dict)):
        raise ValueError("target inventory schema or configuration map is invalid")
    runtime_selector = inventory.get("runtime_selector")
    selected = runtime_selector.get("link_target") if isinstance(runtime_selector, dict) else None
    if selected != "/opt/vst-runtime-" + RUNTIME_SOURCE_HEAD:
        raise ValueError("target inventory does not identify the selected S2 runtime")
    captured = datetime.fromisoformat(str(inventory["captured_utc"]).replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
    if age < -30 or age > 300:
        raise ValueError("target inventory is outside the five-minute freshness window")

    bundle = json.loads(bundle_bytes)
    layout = json.loads(layout_bytes)
    source_head = bundle.get("runtime_source_head")
    if (bundle.get("schema") != "VST_S2_NON_SECRET_CONFIG_BUNDLE_V1"
            or bundle.get("state") != "PREPARED_NOT_INSTALLED"
            or source_head != RUNTIME_SOURCE_HEAD):
        raise ValueError("configuration bundle is not a pinned S2 preparation candidate")

    records = {item["path"]: item for item in bundle["files"]}
    deployment_source_bytes = _git_blob(
        source_commit, "docs/sdlc/runtime-config/deployment-source-manifest.json")
    deployment_source_record = records.get("deployment-source-manifest.json")
    if (not isinstance(deployment_source_record, dict)
            or deployment_source_record.get("size") != len(deployment_source_bytes)
            or deployment_source_record.get("sha256") != _sha(deployment_source_bytes)):
        raise ValueError("deployment source binding differs from the pinned bundle")
    deployment_source = json.loads(deployment_source_bytes)
    task_source_head = deployment_source.get("task_source_head")
    archive = _build_task_source_archive(task_source_head)
    archive_sha256 = deployment_source.get("task_source_archive_sha256")
    archive_bytes = deployment_source.get("task_source_archive_bytes")
    if (deployment_source.get("task_source_archive_format") != TASK_REPOSITORY_ARCHIVE_FORMAT
            or task_source_head != source_head
            or type(archive_bytes) is not int or archive_bytes != len(archive)
            or not _HEX64.fullmatch(str(archive_sha256 or ""))
            or _sha(archive) != archive_sha256):
        raise ValueError("task-source archive differs from the exact deployment source binding")
    entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
    entries += [item for item in bundle["units"]
                if item["publication"] == "new absent-only configuration unit; no enable/start during installation"]
    if len(entries) != 25 or len({item["destination"] for item in entries}) != len(entries):
        raise ValueError("configuration bundle does not contain the exact 25 unique destinations")

    files: list[dict[str, Any]] = []
    inventory_map = inventory["configuration_files"]
    for item in entries:
        destination, source = item["destination"], item["source"]
        if not (destination.startswith(CONFIG_ROOT + "/") or destination.startswith(SYSTEMD_ROOT + "/")):
            raise ValueError("destination is outside the fixed configuration roots")
        record = records.get(source)
        if record is None:
            raise ValueError("configuration source is absent from the bundle manifest")
        if not isinstance(source, str) or source.startswith("/") or ".." in Path(source).parts:
            raise ValueError("configuration source path is not a fixed bundle-relative path")
        data = _git_blob(source_commit, "docs/sdlc/runtime-config/" + source)
        if len(data) != record["size"] or _sha(data) != record["sha256"]:
            raise ValueError("configuration source differs from the pinned bundle: " + source)
        if b"PRIVATE KEY-----" in data:
            raise ValueError("private-key material is forbidden in the configuration transfer")
        inventory_entry = inventory_map.get(destination)
        if not isinstance(inventory_entry, dict):
            raise ValueError("target inventory lacks destination: " + destination)
        current = _inventory_fingerprint(inventory_entry)
        if current["state"] == "file":
            if (not _HEX64.fullmatch(str(current.get("sha256", "")))
                    or any(type(current.get(key)) is not int for key in ("uid", "gid", "mode", "size"))):
                raise ValueError("target inventory fingerprint is incomplete: " + destination)
        mode = int(item["mode"], 8) if isinstance(item["mode"], str) else item["mode"]
        if current.get("state") == "file" and (
                current["uid"] != item["uid"] or current["gid"] != item["gid"]
                or current["mode"] != mode or current["size"] > 1024 * 1024):
            raise ValueError("target inventory metadata differs from the fixed destination contract: " + destination)
        expected_new = {"state": "file", "uid": item["uid"], "gid": item["gid"],
                        "mode": mode, "size": len(data), "sha256": _sha(data)}
        files.append({"destination": destination, "expected_current": current,
                      "expected_new": expected_new, "content_b64": base64.b64encode(data).decode("ascii")})

    payload = {
        "schema": "VST_S2_RUNTIME_CONFIG_APPLY_V1",
        "source_head": source_head,
        "expected_boot_id": inventory["boot_id"],
        "selected_runtime_path": "/opt/vst-runtime-" + source_head,
        "inventory_sha256": expected_inventory_sha256,
        "inventory_b64": base64.b64encode(inventory_bytes).decode("ascii"),
        "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
        "installation_layout_sha256": INSTALLATION_LAYOUT_SHA256,
        "bundle_manifest_b64": base64.b64encode(bundle_bytes).decode("ascii"),
        "installation_layout_b64": base64.b64encode(layout_bytes).decode("ascii"),
        "deployment_source_manifest_sha256": _sha(deployment_source_bytes),
        "deployment_source_manifest_b64": base64.b64encode(deployment_source_bytes).decode("ascii"),
        "task_source_snapshot": {
            "head": task_source_head,
            "format": TASK_REPOSITORY_ARCHIVE_FORMAT,
            "size": len(archive),
            "sha256": archive_sha256,
            "archive_b64": base64.b64encode(archive).decode("ascii"),
        },
        "files": files,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(encoded) > MAX_APPLY_PAYLOAD_BYTES:
        raise ValueError("configuration and task-source snapshot exceed the fixed transfer limit")
    return encoded


_REMOTE = r'''import base64, fcntl, hashlib, io, json, os, platform, re, shutil, stat, subprocess, sys, tarfile, tempfile
from datetime import datetime, timezone

BUNDLE_SHA256 = "2d0c7bcfdd92b3cffa3c9e1344d87f5d34cc690d65006298087d897cf5635d8c"
LAYOUT_SHA256 = "f403052cb26e6d635d7566fe25337e4c3fa18bf83c778dc600b807689b405d8f"
SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"
TASK_REPOSITORY_ROOT = "/var/lib/vst-runner/repository"
TASK_REPOSITORY_ARCHIVE_FORMAT = "canonical-git-tree-tar-v1"

expected_sha = sys.argv[1]
raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha:
    raise SystemExit("configuration transfer digest/size invalid")
try:
    p = json.loads(raw)
except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    raise SystemExit("configuration transfer is invalid JSON") from exc
if os.geteuid() != 0 or platform.system() != "Linux":
    raise SystemExit("configuration apply requires root on Linux")
if (p.get("schema") != "VST_S2_RUNTIME_CONFIG_APPLY_V1" or len(p.get("files", [])) != 25
        or p.get("source_head") != SOURCE_HEAD):
    raise SystemExit("configuration transfer schema/count invalid")
bundle_raw = base64.b64decode(p.get("bundle_manifest_b64", ""), validate=True)
layout_raw = base64.b64decode(p.get("installation_layout_b64", ""), validate=True)
if (hashlib.sha256(bundle_raw).hexdigest() != BUNDLE_SHA256
        or p.get("bundle_manifest_sha256") != BUNDLE_SHA256
        or hashlib.sha256(layout_raw).hexdigest() != LAYOUT_SHA256
        or p.get("installation_layout_sha256") != LAYOUT_SHA256):
    raise SystemExit("configuration manifest differs from the independently pinned candidate")
bundle, layout = json.loads(bundle_raw), json.loads(layout_raw)
if bundle.get("runtime_source_head") != SOURCE_HEAD or bundle.get("state") != "PREPARED_NOT_INSTALLED":
    raise SystemExit("pinned bundle source/state is invalid")
manifest_files = {item["path"]: item for item in bundle["files"]}
deployment_source_raw = base64.b64decode(p.get("deployment_source_manifest_b64", ""), validate=True)
deployment_source_digest = p.get("deployment_source_manifest_sha256")
deployment_source_record = manifest_files.get("deployment-source-manifest.json")
if (not isinstance(deployment_source_record, dict)
        or len(deployment_source_raw) != deployment_source_record.get("size")
        or hashlib.sha256(deployment_source_raw).hexdigest() != deployment_source_record.get("sha256")
        or hashlib.sha256(deployment_source_raw).hexdigest() != deployment_source_digest):
    raise SystemExit("deployment source binding differs from the pinned bundle")
deployment_source = json.loads(deployment_source_raw)
snapshot = p.get("task_source_snapshot")
if (not isinstance(snapshot, dict)
        or deployment_source.get("task_source_head") != SOURCE_HEAD
        or deployment_source.get("task_repository_destination") != TASK_REPOSITORY_ROOT
        or deployment_source.get("task_source_archive_format") != TASK_REPOSITORY_ARCHIVE_FORMAT
        or snapshot.get("head") != SOURCE_HEAD
        or snapshot.get("format") != TASK_REPOSITORY_ARCHIVE_FORMAT):
    raise SystemExit("task-source snapshot identity differs from its exact source binding")
snapshot_raw = base64.b64decode(snapshot.get("archive_b64", ""), validate=True)
if (type(snapshot.get("size")) is not int
        or snapshot.get("size") != len(snapshot_raw)
        or snapshot.get("size") != deployment_source.get("task_source_archive_bytes")
        or snapshot.get("sha256") != deployment_source.get("task_source_archive_sha256")
        or hashlib.sha256(snapshot_raw).hexdigest() != snapshot.get("sha256")):
    raise SystemExit("task-source snapshot bytes differ from the exact source binding")

def read_task_snapshot(archive_raw):
    try:
        archive = tarfile.open(fileobj=io.BytesIO(archive_raw), mode="r:")
    except (tarfile.TarError, OSError) as exc:
        raise SystemExit("task-source snapshot is not a valid tar archive") from exc
    entries = {}
    total = 0
    try:
        members = archive.getmembers()
        if not members or len(members) > 4096:
            raise SystemExit("task-source snapshot member count is invalid")
        for member in members:
            name = member.name
            if "\x00" in name or "\\" in name or name.startswith("/"):
                raise SystemExit("task-source snapshot contains an unsafe path")
            parts = name.rstrip("/").split("/")
            if not parts or parts[0] != "task-source" or any(
                    part in ("", ".", "..") for part in parts):
                raise SystemExit("task-source snapshot path escapes the pinned root")
            relative = "/".join(parts[1:])
            if relative in entries:
                raise SystemExit("task-source snapshot contains a duplicate path")
            if member.isdir():
                if member.mode & ~0o777:
                    raise SystemExit("task-source snapshot directory mode is unsafe")
                entries[relative] = {"kind": "directory", "mode": 0o555}
            elif member.isfile():
                if (member.mode & ~0o777
                        or type(member.size) is not int or member.size < 0
                        or member.size > 8 * 1024 * 1024):
                    raise SystemExit("task-source snapshot file metadata is unsafe")
                total += member.size
                if total > 32 * 1024 * 1024:
                    raise SystemExit("task-source snapshot expands beyond its size limit")
                stream = archive.extractfile(member)
                if stream is None:
                    raise SystemExit("task-source snapshot file content is unavailable")
                data = stream.read(member.size + 1)
                if len(data) != member.size:
                    raise SystemExit("task-source snapshot file size differs from its tar header")
                entries[relative] = {
                    "kind": "file", "mode": 0o555 if member.mode & 0o111 else 0o444,
                    "executable": bool(member.mode & 0o111),
                    "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                    "data": data,
                }
            else:
                raise SystemExit("task-source snapshot contains a link or special file")
    finally:
        archive.close()
    if entries.get("") != {"kind": "directory", "mode": 0o555}:
        raise SystemExit("task-source snapshot root directory is missing")
    for relative, item in entries.items():
        if not relative:
            continue
        parent = relative.rpartition("/")[0]
        if parent not in entries or entries[parent].get("kind") != "directory":
            raise SystemExit("task-source snapshot contains a missing directory parent")
    return entries

snapshot_entries = read_task_snapshot(snapshot_raw)

def snapshot_matches(root, expected):
    try:
        root_info = os.lstat(root)
    except FileNotFoundError:
        return False
    if (not stat.S_ISDIR(root_info.st_mode) or stat.S_ISLNK(root_info.st_mode)
            or root_info.st_uid != 0 or root_info.st_gid != 0
            or stat.S_IMODE(root_info.st_mode) != 0o555):
        return False
    actual = {""}
    for current, directories, files_in_dir in os.walk(root, topdown=True, followlinks=False):
        relative_root = os.path.relpath(current, root)
        if relative_root == ".": relative_root = ""
        for name in directories:
            path = os.path.join(current, name)
            info = os.lstat(path)
            relative = "/".join(filter(None, (relative_root, name)))
            item = expected.get(relative)
            if (item is None or item.get("kind") != "directory"
                    or not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or info.st_uid != 0 or info.st_gid != 0
                    or stat.S_IMODE(info.st_mode) != item["mode"]):
                return False
            actual.add(relative)
        for name in files_in_dir:
            path = os.path.join(current, name)
            info = os.lstat(path)
            relative = "/".join(filter(None, (relative_root, name)))
            item = expected.get(relative)
            if (item is None or item.get("kind") != "file"
                    or not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
                    or info.st_nlink != 1 or info.st_uid != 0 or info.st_gid != 0
                    or stat.S_IMODE(info.st_mode) != item["mode"]
                    or info.st_size != item["size"]):
                return False
            digest = hashlib.sha256()
            with open(path, "rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""): digest.update(chunk)
            if digest.hexdigest() != item["sha256"]:
                return False
            actual.add(relative)
    return actual == set(expected)

def install_task_snapshot(root, expected):
    parent = os.path.dirname(root)
    parent_parent = os.path.dirname(parent)
    parent_parent_info = os.lstat(parent_parent)
    if (not stat.S_ISDIR(parent_parent_info.st_mode) or stat.S_ISLNK(parent_parent_info.st_mode)
            or parent_parent_info.st_uid != 0 or stat.S_IMODE(parent_parent_info.st_mode) & 0o022):
        raise SystemExit("task-source snapshot parent is not root-controlled")
    try:
        parent_info = os.lstat(parent)
    except FileNotFoundError:
        os.mkdir(parent, 0o755)
        os.chown(parent, 0, 0)
        os.chmod(parent, 0o755)
        parent_info = os.lstat(parent)
        parent_fd = os.open(parent_parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                            | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(parent_fd)
        finally: os.close(parent_fd)
    if (not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode)
            or parent_info.st_uid != 0 or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) != 0o755):
        raise SystemExit("task-source snapshot parent has unexpected owner or mode")
    try:
        os.lstat(root)
    except FileNotFoundError:
        pass
    else:
        if snapshot_matches(root, expected):
            return "already-exact"
        raise SystemExit("existing task-source snapshot differs from the pinned source; refusing overwrite")
    stage = tempfile.mkdtemp(prefix=".vst-task-source-", dir=parent)
    try:
        directories = sorted((path for path, item in expected.items()
                              if path and item["kind"] == "directory"),
                             key=lambda path: (path.count("/"), path))
        for relative in directories:
            path = os.path.join(stage, *relative.split("/"))
            os.makedirs(path, mode=0o755, exist_ok=True)
            info = os.lstat(path)
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SystemExit("task-source snapshot path conflicts with a directory")
        for relative, item in expected.items():
            if not relative or item["kind"] != "file":
                continue
            path = os.path.join(stage, *relative.split("/"))
            fd_file = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                              | getattr(os, "O_NOFOLLOW", 0), 0o600)
            try:
                view = memoryview(item["data"])
                while view:
                    written = os.write(fd_file, view)
                    if written <= 0: raise SystemExit("task-source snapshot write made no progress")
                    view = view[written:]
                os.fchown(fd_file, 0, 0)
                os.fchmod(fd_file, item["mode"])
                os.fsync(fd_file)
            finally:
                os.close(fd_file)
        for relative in sorted(directories, key=lambda path: (-path.count("/"), path)):
            path = os.path.join(stage, *relative.split("/"))
            os.chown(path, 0, 0)
            os.chmod(path, 0o555)
            dir_fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                             | getattr(os, "O_NOFOLLOW", 0))
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
        os.chown(stage, 0, 0)
        os.chmod(stage, 0o555)
        stage_fd = os.open(stage, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                           | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(stage_fd)
        finally: os.close(stage_fd)
        if not snapshot_matches(stage, expected):
            raise SystemExit("staged task-source snapshot failed its read-only verification")
        try:
            os.rename(stage, root)
        except FileExistsError as exc:
            raise SystemExit("task-source snapshot appeared during provisioning; no overwrite occurred") from exc
        parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                            | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(parent_fd)
        finally: os.close(parent_fd)
    except BaseException:
        if os.path.isdir(stage) and not os.path.islink(stage):
            for current, dirs, _files in os.walk(stage, topdown=False, followlinks=False):
                for name in dirs:
                    candidate = os.path.join(current, name)
                    if not os.path.islink(candidate): os.chmod(candidate, 0o700)
            os.chmod(stage, 0o700)
            shutil.rmtree(stage)
        raise
    if not snapshot_matches(root, expected):
        raise SystemExit("installed task-source snapshot differs from its pinned archive")
    return "installed"

expected_entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
expected_entries += [item for item in bundle["units"] if item["publication"].startswith("new absent-only configuration unit")]
expected = {}
for entry in expected_entries:
    mode = int(entry["mode"], 8) if isinstance(entry["mode"], str) else entry["mode"]
    source = manifest_files[entry["source"]]
    expected[entry["destination"]] = {
        "uid": entry["uid"], "gid": entry["gid"], "mode": mode,
        "size": source["size"], "sha256": source["sha256"], "source": entry["source"],
    }
if len(expected) != 25:
    raise SystemExit("pinned manifest destination map is not the exact 25-file set")
inventory_raw = base64.b64decode(p.get("inventory_b64", ""), validate=True)
if hashlib.sha256(inventory_raw).hexdigest() != p.get("inventory_sha256"):
    raise SystemExit("target inventory differs from its exact SHA-256 pin")
inventory = json.loads(inventory_raw)
if (inventory.get("schema") != "VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1"
        or inventory.get("source_head") != SOURCE_HEAD
        or inventory.get("boot_id") != p.get("expected_boot_id")):
    raise SystemExit("target inventory identity differs from the pinned source/boot")
captured = datetime.fromisoformat(str(inventory["captured_utc"]).replace("Z", "+00:00"))
age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
if age < -30 or age > 300:
    raise SystemExit("target inventory is outside the five-minute freshness window")
if inventory.get("runtime_selector", {}).get("link_target") != p.get("selected_runtime_path"):
    raise SystemExit("inventory does not identify the selected candidate runtime")
received = {item.get("destination"): item for item in p["files"]}
if len(received) != 25 or set(received) != set(expected):
    raise SystemExit("configuration payload destination set differs from the pinned manifest")
for path, contract in expected.items():
    item = received[path]
    observed = inventory.get("configuration_files", {}).get(path)
    if not isinstance(observed, dict):
        raise SystemExit("target inventory lacks configuration destination: " + path)
    state = observed.get("state")
    if state == "ABSENT":
        current = {"state": "absent"}
    elif state == "PRESENT" and observed.get("kind") == "regular":
        current = {"state":"file", "uid":observed.get("uid"), "gid":observed.get("gid"),
                   "mode":int(observed["mode"], 8), "size":observed.get("size"),
                   "sha256":observed.get("sha256")}
    else:
        raise SystemExit("target inventory contains a non-regular path: " + path)
    if current != item.get("expected_current"):
        raise SystemExit("payload old fingerprint differs from exact target inventory: " + path)
    target = item.get("expected_new", {})
    if any(target.get(k) != contract[k] for k in ("uid", "gid", "mode", "size", "sha256")):
        raise SystemExit("destination metadata/hash differs from pinned manifest: " + path)
with open("/proc/sys/kernel/osrelease", encoding="ascii") as stream:
    if "microsoft" not in stream.read().lower():
        raise SystemExit("configuration apply requires WSL")
release = {}
with open("/etc/os-release", encoding="ascii") as stream:
    for line in stream:
        k, sep, v = line.rstrip("\n").partition("=")
        if sep: release[k] = v.strip('"')
if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
    raise SystemExit("configuration apply requires Ubuntu 24.04")
with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as stream:
    if stream.read().strip() != p["expected_boot_id"]:
        raise SystemExit("WSL boot identity changed since inventory")
if os.readlink("/opt/vst-runtime") != p["selected_runtime_path"]:
    raise SystemExit("the exact candidate runtime is not selected")
if p["selected_runtime_path"] != "/opt/vst-runtime-" + SOURCE_HEAD:
    raise SystemExit("selected runtime path differs from pinned source")

roots = ("/etc/vst-runner", "/etc/systemd/system")
for root in roots:
    info = os.lstat(root)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
        raise SystemExit("configuration parent is not root-controlled: " + root)

units = ("vst-supervisor.service", "vst-signer.service", "vst-runner.service",
         "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
         "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service", "vst-sandbox-probe.service")
for unit in units:
    result = subprocess.run(["/usr/bin/systemctl", "show", "--property=LoadState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    if result.returncode != 0 or result.stdout.strip() not in ("loaded", "not-found"):
        raise SystemExit("cannot establish unit load state: " + unit)
    if result.stdout.strip() == "loaded":
        active = subprocess.run(["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", unit],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, check=False, timeout=10)
        if active.returncode != 0 or active.stdout.strip() != "inactive":
            raise SystemExit("configuration apply requires inactive services: " + unit)
jobs = subprocess.run(["/usr/bin/systemctl", "list-jobs", "--no-legend", "--plain"],
                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      text=True, check=False, timeout=10)
if jobs.returncode != 0:
    raise SystemExit("cannot establish systemd job inventory")
for line in jobs.stdout.splitlines():
    fields = line.split()
    if len(fields) < 4 or not fields[0].isdigit():
        if line.strip() != "No jobs running.": raise SystemExit("unparseable systemd job row")
    elif fields[1] in units:
        raise SystemExit("configuration apply refuses a pending S2 systemd job")

def fingerprint(path):
    try: info = os.lstat(path)
    except FileNotFoundError: return {"state": "absent"}
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SystemExit("destination is not a single-link regular file: " + path)
    h = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise SystemExit("destination changed while opening: " + path)
        while True:
            chunk = os.read(fd, 65536)
            if not chunk: break
            h.update(chunk)
    finally: os.close(fd)
    return {"state": "file", "uid": info.st_uid, "gid": info.st_gid,
            "mode": stat.S_IMODE(info.st_mode), "size": info.st_size, "sha256": h.hexdigest()}

def allowed_path(path):
    return ((path.startswith("/etc/vst-runner/") and "/../" not in path and not path.endswith("/.."))
            or (path.startswith("/etc/systemd/system/") and "/../" not in path and not path.endswith("/..")))

# Preflight the complete set before any write; retries may see only the pinned old or exact new bytes.
seen = set()
for item in p["files"]:
    path = item.get("destination", "")
    if not allowed_path(path) or path in seen: raise SystemExit("invalid/duplicate destination")
    seen.add(path)
    parent = os.path.dirname(path)
    info = os.lstat(parent)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
        raise SystemExit("destination parent is not root-controlled: " + path)
    actual = fingerprint(path)
    if actual not in (item["expected_current"], item["expected_new"]):
        raise SystemExit("destination differs from pinned old/new state: " + path)
    data = base64.b64decode(item["content_b64"], validate=True)
    new = item["expected_new"]
    if (len(data) != new["size"] or hashlib.sha256(data).hexdigest() != new["sha256"]
            or b"PRIVATE KEY-----" in data):
        raise SystemExit("candidate bytes differ from their non-secret manifest")

lock_path = "/run/vst-s2-config-apply.lock"
fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
lock_info = os.fstat(fd)
if (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != 0 or lock_info.st_gid != 0
        or stat.S_IMODE(lock_info.st_mode) != 0o600 or lock_info.st_nlink != 1):
    raise SystemExit("configuration apply lock is unsafe")
fcntl.flock(fd, fcntl.LOCK_EX)
task_source_snapshot_result = install_task_snapshot(TASK_REPOSITORY_ROOT, snapshot_entries)
results = []
for item in p["files"]:
    path = item["destination"]
    parent = os.path.dirname(path)
    data = base64.b64decode(item["content_b64"], validate=True)
    target = item["expected_new"]
    current = fingerprint(path)
    if current == target:
        results.append({"path": path, "sha256": target["sha256"], "result": "already-exact"})
        continue
    if current != item["expected_current"]:
        raise SystemExit("destination changed after preflight: " + path)
    fd_tmp, temporary = tempfile.mkstemp(prefix=".vst-s2-config-", dir=parent)
    try:
        with os.fdopen(fd_tmp, "wb", closefd=True) as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chown(temporary, target["uid"], target["gid"])
        os.chmod(temporary, target["mode"])
        # Recheck immediately before replacement. Parent directories are root-controlled.
        if fingerprint(path) != item["expected_current"]:
            raise SystemExit("destination changed immediately before replacement: " + path)
        os.replace(temporary, path)
        dfd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    if fingerprint(path) != target:
        raise SystemExit("installed destination does not match candidate: " + path)
    results.append({"path": path, "sha256": target["sha256"], "result": "installed"})
reload = subprocess.run(["/usr/bin/systemctl", "daemon-reload"], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        check=False, timeout=30)
if reload.returncode != 0:
    raise SystemExit("systemd did not reload the exact installed unit files")
for unit in units:
    loaded = subprocess.run(["/usr/bin/systemctl", "show", "--property=LoadState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    active = subprocess.run(["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    if loaded.returncode != 0 or active.returncode != 0 or loaded.stdout.strip() != "loaded" or active.stdout.strip() != "inactive":
        raise SystemExit("post-reload unit state is not loaded-inactive: " + unit)
print(json.dumps({"schema":"VST_S2_RUNTIME_CONFIG_APPLY_RESULT_V1", "source_head":p["source_head"],
                  "inventory_sha256":p["inventory_sha256"], "boot_id":p["expected_boot_id"],
                  "task_source_snapshot":{"head":snapshot["head"], "sha256":snapshot["sha256"],
                      "destination":TASK_REPOSITORY_ROOT, "result":task_source_snapshot_result},
                  "daemon_reload":"success", "files":results}, sort_keys=True, separators=(",",":")))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--distribution", default="Ubuntu-24.04")
    args = parser.parse_args()
    try:
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--verify", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
        if head.returncode or head.stdout.strip() != args.source_commit:
            raise ValueError("source commit does not equal the current exact checkout HEAD")
        committed_tool = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--verify", "HEAD:tools/qa/apply_s2_runtime_configuration.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
        working_tool = subprocess.run(
            ["git", "-C", str(REPO), "hash-object", "--", "tools/qa/apply_s2_runtime_configuration.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True, cwd=REPO)
        if (committed_tool.returncode or working_tool.returncode
                or committed_tool.stdout.strip() != working_tool.stdout.strip()):
            raise ValueError("installer source differs from the exact committed Git blob")
        expected_repo_head, expected_capture_sha256 = _current_inventory_validation_identity()
        payload = build_payload(
            args.inventory, args.inventory_sha256, args.source_commit,
            expected_repo_head=expected_repo_head,
            expected_capture_sha256=expected_capture_sha256,
        )
        digest = _sha(payload)
        wsl = subprocess.run(
            ["wsl.exe", "--distribution", args.distribution, "--user", "root", "--exec",
             "/usr/bin/python3.12", "-I", "-B", "-S", "-c", _REMOTE, digest],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if wsl.stdout:
            print(wsl.stdout.decode("utf-8", errors="replace").rstrip())
        if wsl.returncode:
            print(wsl.stderr.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
            return wsl.returncode
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
