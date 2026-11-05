#!/usr/bin/env python3
"""Apply only the reviewed non-secret S2 runtime configuration to Ubuntu-24.04 WSL."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) in sys.path:
    sys.path.remove(str(REPO))
sys.path.insert(0, str(REPO))
from tools.vst.contracts import ContractError, manifest_sha256, validate_task_manifest

BUNDLE = REPO / "docs/sdlc/runtime-config"
INVENTORY_SCHEMA = "VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1"
CONFIG_ROOT = "/etc/vst-runner"
SYSTEMD_ROOT = "/etc/systemd/system"
TASK_REPOSITORY_ROOT = "/var/lib/vst-runner/repository"
TASK_REPOSITORY_GIT_PACK_FORMAT = "git-pack-shallow-v1"
MAX_APPLY_PAYLOAD_BYTES = 16 * 1024 * 1024
MAX_REMOTE_SOURCE_BYTES = 512 * 1024
# Keep Windows CreateProcess argv small; the payload follows the framed source.
_WSL_SOURCE_LOADER = """import sys

def _vst_read_source():
    stream = sys.stdin.buffer
    header = stream.read(8)
    if len(header) != 8:
        raise SystemExit("remote source frame header is truncated")
    size = int.from_bytes(header, "big")
    if not 1 <= size <= 512 * 1024:
        raise SystemExit("remote source frame size is invalid")
    source = stream.read(size)
    if len(source) != size:
        raise SystemExit("remote source frame is truncated")
    return source

exec(compile(_vst_read_source(), "<vst-s2-runtime-remote>", "exec"))
"""


def _remote_stdin(source: str, payload: bytes) -> bytes:
    source_bytes = source.encode("utf-8")
    if not 1 <= len(source_bytes) <= MAX_REMOTE_SOURCE_BYTES:
        raise ValueError("remote source exceeds its bounded frame")
    if len(payload) > MAX_APPLY_PAYLOAD_BYTES:
        raise ValueError("remote payload exceeds its size bound")
    return len(source_bytes).to_bytes(8, "big") + source_bytes + payload


RUNTIME_SOURCE_HEAD = "ee69f9fbf074a4c73d2d5d1da81c627a57d06071"
BUNDLE_MANIFEST_SHA256 = "8f487494a1a6bc08c0ce567075a32945ca0c1a22c5ec03e7213ac3e2f4466741"
INSTALLATION_LAYOUT_SHA256 = "f46e97704a89b5da339701bb71b6e71c4ce846ae96cb4504929869352d0315dd"
DEPLOYMENT_BRANCH = "s2-canonical-continuation"
TASK_SOURCE_HEAD = "67361bb4aa23355d9a6bc7877a987ba688559eda"
TASK_SOURCE_TREE = "0c4a8440a38027563d2455024af6b58072fe3b57"
TASK_SOURCE_OBJECT_COUNT = 804
TASK_SOURCE_PACK_SHA256 = "2ce52ec7dfd3b1eb16c0704f133b491e8c571753ba8e3f6c9bfc931dd0328bd3"
TASK_SOURCE_PACK_BYTES = 2_666_915
WSL_REPOSITORY_ROOT = "/mnt/d/Repo/Virtual_scrum_team"
GUARD_DESTINATIONS = (
    "/etc/systemd/system/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    "/etc/systemd/system/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
)
IMPLEMENTATION_INPUTS = (
    "tools/qa/apply_s2_runtime_configuration.py",
    "tools/qa/runtime_snapshot_transaction.py",
    "tools/vst/contracts.py",
    "tools/qa/collect_s2_runtime_config_inventory.py",
    "tools/qa/verify_s2_runtime_config_inventory.py",
    "docs/sdlc/runtime-config/deployment-source-manifest.json",
    "docs/sdlc/runtime-config/bundle-manifest.json",
    "docs/sdlc/runtime-config/installation-layout.json",
    "docs/sdlc/runtime-config/unit-overrides/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    "docs/sdlc/runtime-config/unit-overrides/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
    "tests/vst/test_s2_runtime_config_bundle.py",
    "tests/vst/test_s2_runtime_config_inventory.py",
    "tests/vst/test_s2_runtime_configuration_apply.py",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")
    return _sha(data)


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


def _task_source_pack(source_manifest: dict[str, Any]) -> bytes:
    if (source_manifest.get("schema") != "VST_S2_DEPLOYMENT_SOURCE_BINDING_V2"
            or source_manifest.get("task_repository") != "Virtual_scrum_team"
            or source_manifest.get("task_repository_destination") != TASK_REPOSITORY_ROOT
            or source_manifest.get("task_source_head") != TASK_SOURCE_HEAD
            or source_manifest.get("task_source_tree_sha1") != TASK_SOURCE_TREE
            or source_manifest.get("task_source_git_pack_format") != TASK_REPOSITORY_GIT_PACK_FORMAT
            or source_manifest.get("task_source_shallow_commits") != [TASK_SOURCE_HEAD]
            or source_manifest.get("task_source_git_object_count") != TASK_SOURCE_OBJECT_COUNT):
        raise ValueError("task-source Git identity differs from its exact deployment binding")
    size = source_manifest.get("task_source_git_pack_bytes")
    digest = source_manifest.get("task_source_git_pack_sha256")
    if (type(size) is not int or size != TASK_SOURCE_PACK_BYTES
            or digest != TASK_SOURCE_PACK_SHA256
            or "task_source_git_pack_b64_chunks" in source_manifest):
        raise ValueError("task-source Git pack metadata differs from its non-self-referential pins")
    objects = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "rev-list", "--objects",
         "--no-walk", TASK_SOURCE_HEAD],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if objects.returncode or len(objects.stdout.splitlines()) != TASK_SOURCE_OBJECT_COUNT:
        raise ValueError("pinned task-source commit object closure is unavailable or has changed")
    packed_result = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "pack-objects", "--stdout", "--no-reuse-delta",
         "--no-reuse-object", "--threads=1", "--window=0", "--depth=0"],
        input=objects.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    packed = packed_result.stdout
    if (packed_result.returncode or len(packed) != size or _sha(packed) != digest
            or not packed.startswith(b"PACK")):
        raise ValueError("dynamically generated task-source Git pack differs from its exact manifest pin")
    return packed


def _validate_deployment_commit(commit: str) -> None:
    if not _HEX40.fullmatch(commit):
        raise ValueError("approved deployment commit must be a full lowercase Git object id")
    branch = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "rev-parse", "--abbrev-ref", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True,
    )
    head = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True,
    )
    upstream = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "merge-base", "--is-ancestor",
         commit, "@{upstream}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if (branch.returncode or branch.stdout.strip() != DEPLOYMENT_BRANCH
            or head.returncode or head.stdout.strip() != commit or upstream.returncode):
        raise ValueError("approved deployment commit is not the pushed canonical branch HEAD")
    dirty = subprocess.run(
        ["git", "-C", str(REPO), "status", "--porcelain=v1", "--", *IMPLEMENTATION_INPUTS],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True,
    )
    if dirty.returncode or dirty.stdout:
        raise ValueError("an in-scope deployment input differs from its pushed commit")
    for relative in IMPLEMENTATION_INPUTS:
        committed = _git_blob(commit, relative)
        try:
            working = (REPO / relative).read_bytes()
        except OSError as exc:
            raise ValueError("an approved deployment input is missing: " + relative) from exc
        if committed != working:
            raise ValueError("deployment input differs from its exact committed blob: " + relative)


def _current_inventory_validation_identity() -> tuple[str, str]:
    head = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "rev-parse", "HEAD"],
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
    _validate_deployment_commit(source_commit)
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
    if (bundle.get("source_head") != source_head
            or bundle.get("task_source_head") != task_source_head
            or deployment_source.get("runtime_source_head") != source_head
            or task_source_head != TASK_SOURCE_HEAD
            or deployment_source.get("task_source_tree_sha1") != TASK_SOURCE_TREE
            or deployment_source.get("task_repository_destination") != TASK_REPOSITORY_ROOT):
        raise ValueError("task-source identity differs from the runtime bundle contract")
    if bundle.get("source_binding_sha256") != _sha(
            json.dumps(deployment_source, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")):
        raise ValueError("deployment source binding differs from the canonical bundle pin")
    task_manifest_bytes = _git_blob(
        source_commit, "docs/sdlc/runtime-config/task-manifest.json")
    policy_bytes = _git_blob(
        source_commit, "docs/sdlc/runtime-config/assignment-delegation-policy.json")
    supervisor_bytes = _git_blob(
        source_commit, "docs/sdlc/runtime-config/supervisor-service.json")
    for name, data in (("task-manifest.json", task_manifest_bytes),
                       ("assignment-delegation-policy.json", policy_bytes),
                       ("supervisor-service.json", supervisor_bytes)):
        record = records.get(name)
        if (not isinstance(record, dict) or record.get("size") != len(data)
                or record.get("sha256") != _sha(data)):
            raise ValueError("task identity input differs from the pinned bundle: " + name)
    try:
        task_manifest = validate_task_manifest(json.loads(task_manifest_bytes))
    except ContractError as exc:
        raise ValueError("task manifest does not satisfy the VST contract") from exc
    assignment_policy = json.loads(policy_bytes)
    supervisor_config = json.loads(supervisor_bytes)
    if (not isinstance(task_manifest, dict) or not isinstance(assignment_policy, dict)
            or not isinstance(supervisor_config, dict)):
        raise ValueError("task identity configuration must be JSON objects")
    task_digest = manifest_sha256(task_manifest)
    policy_digest = _canonical_sha(assignment_policy)
    allowed_assignments = assignment_policy.get("allowed_assignments")
    change_scope = task_manifest.get("change_scope")
    if (not isinstance(change_scope, dict)
            or task_manifest.get("base_head") != task_source_head
            or task_manifest.get("scope") != change_scope.get("allowed_paths")
            or bundle.get("task_manifest_sha256") != task_digest
            or assignment_policy.get("source_head") != task_source_head
            or assignment_policy.get("manifest_sha256") != bundle.get("source_binding_sha256")
            or not isinstance(allowed_assignments, list)
            or len(allowed_assignments) != 1
            or not isinstance(allowed_assignments[0], dict)
            or allowed_assignments[0].get("task_manifest_sha256") != task_digest
            or bundle.get("assignment_policy_sha256") != policy_digest
            or supervisor_config.get("assignment_policy_sha256") != policy_digest):
        raise ValueError("task manifest, assignment policy and runtime bundle identities disagree")
    task_pack = _task_source_pack(deployment_source)
    helper_bytes = _git_blob(source_commit, "tools/qa/runtime_snapshot_transaction.py")
    if not helper_bytes or len(helper_bytes) > 512 * 1024:
        raise ValueError("runtime snapshot transaction helper is missing or oversized")
    entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
    entries += [item for item in bundle["units"]
                if item["publication"] == "new absent-only configuration unit; no enable/start during installation"]
    if len(entries) != 27 or len({item["destination"] for item in entries}) != len(entries):
        raise ValueError("configuration bundle does not contain the exact 27 unique destinations")

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
        "schema": "VST_S2_RUNTIME_CONFIG_APPLY_V2",
        "source_head": source_head,
        "task_source_head": task_source_head,
        "deployment_source_commit": source_commit,
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
            "tree_sha1": TASK_SOURCE_TREE,
            "format": TASK_REPOSITORY_GIT_PACK_FORMAT,
            "object_count": TASK_SOURCE_OBJECT_COUNT,
            "shallow_commits": [task_source_head],
            "size": len(task_pack),
            "sha256": _sha(task_pack),
            "pack_b64": base64.b64encode(task_pack).decode("ascii"),
        },
        "transaction_helper_sha256": _sha(helper_bytes),
        "transaction_helper_b64": base64.b64encode(helper_bytes).decode("ascii"),
        "files": files,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")
    if len(encoded) > MAX_APPLY_PAYLOAD_BYTES:
        raise ValueError("configuration and task-source Git pack exceed the fixed transfer limit")
    return encoded


_REMOTE = r'''import base64, fcntl, hashlib, json, os, platform, re, stat, subprocess, sys, tempfile, uuid
from datetime import datetime, timezone

BUNDLE_SHA256 = "8f487494a1a6bc08c0ce567075a32945ca0c1a22c5ec03e7213ac3e2f4466741"
LAYOUT_SHA256 = "f46e97704a89b5da339701bb71b6e71c4ce846ae96cb4504929869352d0315dd"
SOURCE_HEAD = "ee69f9fbf074a4c73d2d5d1da81c627a57d06071"
TASK_HEAD = "67361bb4aa23355d9a6bc7877a987ba688559eda"
TASK_TREE = "0c4a8440a38027563d2455024af6b58072fe3b57"
TASK_REPOSITORY_ROOT = "/var/lib/vst-runner/repository"
WSL_REPOSITORY_ROOT = "/mnt/d/Repo/Virtual_scrum_team"
TASK_REPOSITORY_PACK_FORMAT = "git-pack-shallow-v1"

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
if (p.get("schema") != "VST_S2_RUNTIME_CONFIG_APPLY_V2" or len(p.get("files", [])) != 27
        or p.get("source_head") != SOURCE_HEAD or p.get("task_source_head") != TASK_HEAD):
    raise SystemExit("configuration transfer schema/count invalid")
if (len(sys.argv) != 4 or not re.fullmatch(r"[0-9a-f]{64}", str(sys.argv[1]))
        or p.get("deployment_source_commit") != sys.argv[2]
        or not re.fullmatch(r"[0-9a-f]{40}", str(sys.argv[2]))
        or os.path.realpath(sys.argv[3]) != WSL_REPOSITORY_ROOT):
    raise SystemExit("deployment implementation commit differs from the independent invocation pin")
deployment_commit = sys.argv[2]
repo_root = sys.argv[3]
bundle_raw = base64.b64decode(p.get("bundle_manifest_b64", ""), validate=True)
layout_raw = base64.b64decode(p.get("installation_layout_b64", ""), validate=True)
if (hashlib.sha256(bundle_raw).hexdigest() != BUNDLE_SHA256
        or p.get("bundle_manifest_sha256") != BUNDLE_SHA256
        or hashlib.sha256(layout_raw).hexdigest() != LAYOUT_SHA256
        or p.get("installation_layout_sha256") != LAYOUT_SHA256):
    raise SystemExit("configuration manifest differs from the independently pinned candidate")
for relative, payload_blob in (
        ("docs/sdlc/runtime-config/bundle-manifest.json", bundle_raw),
        ("docs/sdlc/runtime-config/installation-layout.json", layout_raw)):
    committed = subprocess.run(
        ["/usr/bin/git", "-C", repo_root, "--no-replace-objects", "show",
         deployment_commit + ":" + relative],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if committed.returncode or committed.stdout != payload_blob:
        raise SystemExit("payload manifest differs from its exact deployment Git blob: " + relative)
bundle, layout = json.loads(bundle_raw), json.loads(layout_raw)
if (bundle.get("source_head") != SOURCE_HEAD
        or bundle.get("runtime_source_head") != SOURCE_HEAD
        or bundle.get("task_source_head") != TASK_HEAD
        or bundle.get("state") != "PREPARED_NOT_INSTALLED"):
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
committed_source_manifest = subprocess.run(
    ["/usr/bin/git", "-C", repo_root, "--no-replace-objects", "show",
     deployment_commit + ":docs/sdlc/runtime-config/deployment-source-manifest.json"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
if committed_source_manifest.returncode or committed_source_manifest.stdout != deployment_source_raw:
    raise SystemExit("deployment source manifest differs from its exact deployment Git blob")
deployment_source = json.loads(deployment_source_raw)
snapshot = p.get("task_source_snapshot")
if (not isinstance(snapshot, dict)
        or deployment_source.get("runtime_source_head") != SOURCE_HEAD
        or deployment_source.get("task_source_head") != TASK_HEAD
        or deployment_source.get("task_source_tree_sha1") != TASK_TREE
        or deployment_source.get("task_repository_destination") != TASK_REPOSITORY_ROOT
        or deployment_source.get("task_source_git_pack_format") != "git-pack-shallow-v1"
        or snapshot.get("head") != TASK_HEAD or snapshot.get("tree_sha1") != TASK_TREE):
    raise SystemExit("task-source snapshot identity differs from its exact source binding")
branch = subprocess.run(["/usr/bin/git", "-C", repo_root, "--no-replace-objects",
                         "rev-parse", "--abbrev-ref", "HEAD"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
head = subprocess.run(["/usr/bin/git", "-C", repo_root, "--no-replace-objects",
                       "rev-parse", "--verify", "HEAD"],
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
upstream = subprocess.run(["/usr/bin/git", "-C", repo_root, "--no-replace-objects",
                           "merge-base", "--is-ancestor", deployment_commit, "@{upstream}"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
if (branch.returncode or branch.stdout.strip() != "s2-canonical-continuation"
        or head.returncode or head.stdout.strip() != deployment_commit or upstream.returncode):
    raise SystemExit("deployment commit is not the exact pushed canonical branch HEAD")
implementation_inputs = (
    "tools/qa/apply_s2_runtime_configuration.py",
    "tools/qa/runtime_snapshot_transaction.py",
    "tools/qa/collect_s2_runtime_config_inventory.py",
    "tools/qa/verify_s2_runtime_config_inventory.py",
    "docs/sdlc/runtime-config/deployment-source-manifest.json",
    "docs/sdlc/runtime-config/bundle-manifest.json",
    "docs/sdlc/runtime-config/installation-layout.json",
    "docs/sdlc/runtime-config/unit-overrides/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    "docs/sdlc/runtime-config/unit-overrides/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
    "tests/vst/test_s2_runtime_config_bundle.py",
    "tests/vst/test_s2_runtime_config_inventory.py",
    "tests/vst/test_s2_runtime_configuration_apply.py",
)
for relative in implementation_inputs:
    committed = subprocess.run(["/usr/bin/git", "-C", repo_root, "--no-replace-objects",
                                "show", deployment_commit + ":" + relative],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        working = open(os.path.join(repo_root, relative), "rb").read()
    except OSError as exc:
        raise SystemExit("an approved deployment input is missing: " + relative) from exc
    if committed.returncode or committed.stdout != working:
        raise SystemExit("deployment input differs from its exact committed Git blob: " + relative)
    mode = os.lstat(os.path.join(repo_root, relative)).st_mode
    if not stat.S_ISREG(mode):
        raise SystemExit("deployment input is not a regular committed source file: " + relative)
helper_raw = base64.b64decode(p.get("transaction_helper_b64", ""), validate=True)
helper_digest = p.get("transaction_helper_sha256")
committed_helper = subprocess.run(
    ["/usr/bin/git", "-C", repo_root, "--no-replace-objects", "show",
     deployment_commit + ":tools/qa/runtime_snapshot_transaction.py"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
if (not helper_raw or len(helper_raw) > 512 * 1024
        or committed_helper.returncode or helper_raw != committed_helper.stdout
        or hashlib.sha256(helper_raw).hexdigest() != helper_digest):
    raise SystemExit("transaction helper differs from its exact committed source digest")
helper_ns = {"__name__": "_vst_s2_runtime_snapshot_transaction"}
exec(compile(helper_raw, "runtime_snapshot_transaction.py", "exec", dont_inherit=True), helper_ns)
snapshot_pack = helper_ns["validate_pack"](snapshot)

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
if len(expected) != 27:
    raise SystemExit("pinned manifest destination map is not the exact 27-file set")
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
if len(received) != 27 or set(received) != set(expected):
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
protected_units = ("vst-runner.service", "vst-dispatcher.service")


def parse_unit_identity(output):
    expected = {"ActiveState", "SubState", "InvocationID", "ControlGroup", "UnitFileState"}
    values = {}
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key not in expected or key in values:
            raise ValueError("unit activation properties are ambiguous")
        values[key] = value
    if set(values) != expected:
        raise ValueError("unit activation properties are incomplete")
    return values


unit_before = {}
for unit in units:
    loaded = subprocess.run(["/usr/bin/systemctl", "show", "--property=LoadState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    if loaded.returncode != 0 or loaded.stdout.strip() not in ("loaded", "not-found"):
        raise SystemExit("cannot establish unit load state: " + unit)
    if unit in protected_units and loaded.stdout.strip() != "loaded":
        raise SystemExit("protected transaction unit is not loaded: " + unit)
    if loaded.stdout.strip() == "not-found":
        continue
    properties = subprocess.run(
        ["/usr/bin/systemctl", "show", "--property=ActiveState,SubState,InvocationID,ControlGroup,UnitFileState", unit],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, check=False, timeout=10)
    if properties.returncode != 0:
        raise SystemExit("cannot establish unit activation identity: " + unit)
    try:
        values = parse_unit_identity(properties.stdout)
    except ValueError as exc:
        raise SystemExit(str(exc) + ": " + unit) from exc
    active_state, substate = values["ActiveState"], values["SubState"]
    invocation_id, control_group = values["InvocationID"], values["ControlGroup"]
    unit_file_state = values["UnitFileState"]
    if active_state not in ("active", "inactive"):
        raise SystemExit("unit is transitioning or failed; refusing configuration apply: " + unit)
    if unit_file_state in ("masked", "masked-runtime"):
        raise SystemExit("protected unit already has an unowned mask: " + unit)
    if unit not in protected_units and unit != "vst-dispatch-owner.socket" and active_state != "inactive":
        raise SystemExit("an unrelated S2 service is active: " + unit)
    unit_before[unit] = {"active": active_state == "active", "substate": substate,
                         "invocation_id": invocation_id, "control_group": control_group,
                         "unit_file_state": unit_file_state}
bootstrap_predecessor = False
if (not unit_before["vst-runner.service"]["invocation_id"]
        or not unit_before["vst-dispatcher.service"]["invocation_id"]):
    if all(not unit_before[unit]["active"]
           and not unit_before[unit]["invocation_id"]
           and not unit_before[unit]["control_group"] for unit in protected_units):
        # This is a genuine pre-start baseline, never a stopped invocation receipt.
        helper_ns["observe_bootstrap_predecessor"](allow_missing_ledger=True)
        bootstrap_predecessor = True
    else:
        raise SystemExit("protected service invocation identity is unavailable")
if (unit_before["vst-dispatcher.service"]["active"]
        and not unit_before["vst-runner.service"]["active"]):
    raise SystemExit("active Dispatcher without active Runner is an unexpected predecessor state")
for unit in protected_units:
    runtime_mask = "/run/systemd/system/" + unit
    if os.path.lexists(runtime_mask):
        raise SystemExit("protected unit has a pre-existing runtime mask: " + unit)
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

def run_systemctl(*arguments, timeout=30):
    result = subprocess.run(["/usr/bin/systemctl", *arguments], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            check=False, timeout=timeout)
    if result.returncode:
        raise SystemExit("systemd operation failed: " + " ".join(arguments[:3]))
    return result.stdout.strip()

def unit_value(unit, prop):
    return run_systemctl("show", "--property=" + prop, "--value", unit, timeout=10)

def ensure_destination_parent(path):
    parent = os.path.dirname(path)
    fixed_parents = {
        "/etc/systemd/system/vst-runner.service.d": "/etc/systemd/system",
        "/etc/systemd/system/vst-dispatcher.service.d": "/etc/systemd/system",
    }
    if parent in fixed_parents and not os.path.lexists(parent):
        base = fixed_parents[parent]
        info = os.lstat(base)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) & 0o022):
            raise SystemExit("systemd drop-in parent is not root-controlled")
        os.mkdir(parent, 0o755)
        os.chown(parent, 0, 0)
        os.chmod(parent, 0o755)
        dfd = os.open(base, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                      | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(dfd)
        finally: os.close(dfd)
    info = os.lstat(parent)
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) & 0o022):
        raise SystemExit("destination parent is not root-controlled: " + path)

def install_config_file(item, predecessor_backup=None):
    path = item["destination"]
    parent = os.path.dirname(path)
    data = base64.b64decode(item["content_b64"], validate=True)
    target = item["expected_new"]
    current = fingerprint(path)
    if current == target:
        return {"path":path, "sha256":target["sha256"], "result":"already-exact"}
    if current != item["expected_current"]:
        raise SystemExit("destination changed after its exact preflight: " + path)
    fd_tmp, temporary = tempfile.mkstemp(prefix=".vst-s2-config-", dir=parent)
    preserve_temporary = False
    try:
        with os.fdopen(fd_tmp, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chown(temporary, target["uid"], target["gid"])
        os.chmod(temporary, target["mode"])
        current = fingerprint(path)
        if current != item["expected_current"]:
            raise SystemExit("destination changed immediately before replacement: " + path)
        staged_info = os.lstat(temporary)
        if current.get("state") == "absent":
            helper_ns["_renameat2_file"](temporary, path, 1)
            published = os.lstat(path)
            if ((published.st_dev, published.st_ino) != (staged_info.st_dev, staged_info.st_ino)
                    or fingerprint(path) != target):
                raise SystemExit("exclusive config publication differs from its exact staged inode")
        else:
            if (not isinstance(predecessor_backup, str)
                    or not os.path.isabs(predecessor_backup)):
                raise SystemExit("atomic replacement requires its durable predecessor backup")
            prior_state, prior_bytes = helper_ns["_config_fingerprint"](predecessor_backup)
            if (prior_bytes is None or prior_state.get("uid") != 0 or prior_state.get("gid") != 0
                    or prior_state.get("mode") != 0o600
                    or prior_state.get("sha256") != current.get("sha256")
                    or prior_state.get("size") != current.get("size")):
                raise SystemExit("durable predecessor backup does not match the exact current config")
            previous_info = os.lstat(path)
            # Until the displaced inode is proven to be the journaled predecessor,
            # preserve the temporary path on every exception.
            preserve_temporary = True
            helper_ns["_renameat2_file"](temporary, path, 2)
            published = os.lstat(path)
            displaced = os.lstat(temporary)
            if ((published.st_dev, published.st_ino) != (staged_info.st_dev, staged_info.st_ino)
                    or (displaced.st_dev, displaced.st_ino) != (previous_info.st_dev, previous_info.st_ino)
                    or fingerprint(path) != target or fingerprint(temporary) != current):
                raise SystemExit("atomic exchange displaced an unexpected concurrent config; both versions retained")
            preserve_temporary = False
            os.unlink(temporary)
        dfd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                      | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(dfd)
        finally: os.close(dfd)
    except BaseException:
        if not preserve_temporary and os.path.lexists(temporary):
            os.unlink(temporary)
        raise
    if fingerprint(path) != target:
        raise SystemExit("installed destination does not match the exact target: " + path)
    return {"path":path, "sha256":target["sha256"], "result":"installed"}

def cgroup_is_empty(control_group):
    if not isinstance(control_group, str) or not control_group.startswith("/") or ".." in control_group.split("/"):
        raise SystemExit("systemd ControlGroup is invalid")
    if control_group == "/":
        return False
    path = os.path.join("/sys/fs/cgroup", control_group.lstrip("/"))
    if not os.path.lexists(path):
        return True
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise SystemExit("service cgroup path is not a directory")
    events = {}
    with open(os.path.join(path, "cgroup.events"), "r", encoding="ascii") as stream:
        for line in stream:
            key, value = line.split()
            events[key] = value
    with open(os.path.join(path, "cgroup.procs"), "r", encoding="ascii") as stream:
        procs = stream.read().split()
    return events.get("populated") == "0" and not procs

def verify_persistent_guard(unit):
    if not helper_ns["persistent_guard_loaded"](unit):
        raise SystemExit("systemd did not load the exact persistent snapshot guard: " + unit)

def verify_runtime_mask(unit):
    path = "/run/systemd/system/" + unit
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    if (not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or info.st_nlink != 1 or os.readlink(path) != "/dev/null"):
        return False
    return {"device":info.st_dev, "inode":info.st_ino, "target":"/dev/null"}

def read_runner_generation():
    path = "/var/lib/vst-runner/generation.json"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_size > 65536:
            raise SystemExit("Runner generation record has unsafe metadata")
        return json.loads(os.read(fd, 65537))
    finally:
        os.close(fd)

# Preflight the complete set before any write; retries may see only the pinned old or exact new bytes.
seen = set()
for item in p["files"]:
    path = item.get("destination", "")
    if not allowed_path(path) or path in seen: raise SystemExit("invalid/duplicate destination")
    seen.add(path)
    parent = os.path.dirname(path)
    ensure_destination_parent(path)
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
marker_path = "/var/lib/vst-runner/private/snapshot-transaction-incomplete.json"
if os.path.lexists(marker_path):
    transaction_fd = os.open(marker_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        transaction_info = os.fstat(transaction_fd)
        marker_raw = os.read(transaction_fd, 16 * 1024 + 1)
        if (not stat.S_ISREG(transaction_info.st_mode) or transaction_info.st_uid != 0
                or transaction_info.st_gid != 0 or stat.S_IMODE(transaction_info.st_mode) != 0o600
                or len(marker_raw) > 16 * 1024):
            raise SystemExit("existing snapshot transaction marker has unsafe metadata")
    finally:
        os.close(transaction_fd)
    marker_record = helper_ns["_unique_json"](marker_raw)
    transaction_id = marker_record.get("transaction_id")
    recovered = helper_ns["load_transaction_for_recovery"](transaction_id)
    path_state = helper_ns["reconcile_snapshot_paths"](recovered)
    print(json.dumps({"schema":"VST_S2_RUNTIME_CONFIG_APPLY_RESULT_V2",
                      "result":"recovery-required", "transaction_id":transaction_id,
                      "journal_path":recovered["journal_path"], "journal_state":recovered["state"],
                      "snapshot_paths":path_state}, sort_keys=True, separators=(",",":")))
    raise SystemExit("existing transaction preserved; use its explicit recovery path before applying")
transaction_id = uuid.uuid4().hex
stage_path = os.path.join(
    os.path.dirname(TASK_REPOSITORY_ROOT),
    ".vst-task-source-stage-" + TASK_HEAD + "-" + transaction_id)
marker_path = "/var/lib/vst-runner/private/snapshot-transaction-incomplete.json"
if not os.path.lexists(marker_path):
    try:
        live_identity = helper_ns["_tree_identity"](TASK_REPOSITORY_ROOT)
        live_stat = os.lstat(TASK_REPOSITORY_ROOT)
    except BaseException:
        live_identity = None
        live_stat = None
    if (live_identity is not None and live_identity[:2] == (TASK_HEAD, TASK_TREE)
            and live_stat is not None and stat.S_ISDIR(live_stat.st_mode)
            and not stat.S_ISLNK(live_stat.st_mode) and live_stat.st_uid == 0
            and live_stat.st_gid == 0 and stat.S_IMODE(live_stat.st_mode) == 0o555
            and all(fingerprint(item["destination"]) == item["expected_new"]
                    for item in p["files"])):
        for unit in protected_units:
            verify_persistent_guard(unit)
        print(json.dumps({"schema":"VST_S2_RUNTIME_CONFIG_APPLY_RESULT_V2",
                          "deployment_source_commit":deployment_commit,
                          "source_head":p["source_head"], "task_source_head":TASK_HEAD,
                          "inventory_sha256":p["inventory_sha256"], "boot_id":p["expected_boot_id"],
                          "task_source_snapshot":{"head":TASK_HEAD, "tree_sha1":TASK_TREE,
                              "result":"already-exact-no-op"},
                          "files":[{"path":item["destination"],
                                    "sha256":item["expected_new"]["sha256"],
                                    "result":"already-exact"} for item in p["files"]]},
                         sort_keys=True, separators=(",",":")))
        raise SystemExit(0)
task_stage_proof = helper_ns["build_git_stage"](snapshot_pack, stage_path)
transaction_preview = helper_ns["transaction_identity"](
    TASK_REPOSITORY_ROOT, stage_path, transaction_id)
recovery_path = ("/var/lib/vst-runner/repository-recovery-" +
                 transaction_preview["old_head"] + "-" + transaction_id)
transaction = None
results = []
guard_paths = {
    "/etc/systemd/system/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    "/etc/systemd/system/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
}
if len(guard_paths) != 2 or not guard_paths.issubset(received):
    raise SystemExit("exact Runner/Dispatcher recovery guard pair is absent from the payload")
for item in p["files"]:
    path = item["destination"]
    if path in guard_paths:
        results.append(install_config_file(item))
reload = subprocess.run(["/usr/bin/systemctl", "daemon-reload"], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        check=False, timeout=30)
if reload.returncode != 0:
    raise SystemExit("systemd did not reload the exact persistent recovery guards")
for unit in protected_units:
    verify_persistent_guard(unit)
activation_state = {unit: unit_before[unit]["active"] for unit in protected_units}
configuration_state = {
    item["destination"]: {"expected_current":item["expected_current"],
                          "expected_new":item["expected_new"]}
    for item in p["files"]
}
transaction = helper_ns["create_transaction"](
    TASK_REPOSITORY_ROOT, stage_path, deployment_commit=sys.argv[2],
    activation_state=activation_state, configuration_state=configuration_state,
    marker_path="/var/lib/vst-runner/private/snapshot-transaction-incomplete.json")
try:
    helper_ns["backup_configurations"](transaction, p["files"])
    mask_paths_before = {}
    for unit in protected_units:
        mask_path = "/run/systemd/system/" + unit
        if os.path.lexists(mask_path):
            raise SystemExit("runtime mask path became occupied before transaction fencing: " + unit)
        mask_paths_before[unit] = None
    helper_ns["record_state"](transaction, "MARKER_DURABLE", "FENCING",
                               runtime_mask_paths_before=mask_paths_before)
    transaction["state"] = "FENCING"
    installed_masks = {}
    for unit in protected_units:
        installed_masks[unit] = helper_ns["ensure_runtime_mask"](
            transaction, unit, mask_paths_before)
    helper_ns["record_fenced"](transaction, installed_masks)

    if bootstrap_predecessor:
        bootstrap_proof = helper_ns["ensure_bootstrap_predecessor"](transaction)
        helper_ns["record_dispatcher_bootstrap_quiescent"](
            transaction, proof=bootstrap_proof)
        helper_ns["record_runner_bootstrap_empty"](
            transaction, proof=bootstrap_proof)
    else:
        dispatcher = unit_before["vst-dispatcher.service"]
        if dispatcher["active"]:
            run_systemctl("stop", "vst-dispatcher.service", timeout=1910)
        if unit_value("vst-dispatcher.service", "ActiveState") != "inactive":
            raise SystemExit("Dispatcher did not reach inactive after graceful stop")
        dispatcher_empty = cgroup_is_empty(dispatcher["control_group"])
        if not dispatcher_empty:
            raise SystemExit("Dispatcher cgroup remains populated; both snapshots remain untouched")
        helper_ns["record_dispatcher_drained"](
            transaction, inactive=True, cgroup_empty=True,
            invocation_id=dispatcher["invocation_id"] or "NOT_ACTIVE")

        runner = unit_before["vst-runner.service"]
        runner_stop_started = datetime.now(timezone.utc)
        if runner["active"]:
            run_systemctl("stop", "vst-runner.service", timeout=1910)
        if unit_value("vst-runner.service", "ActiveState") != "inactive":
            raise SystemExit("Runner did not reach inactive after its bounded fence stop")
        if not cgroup_is_empty(runner["control_group"]):
            raise SystemExit("Runner cgroup remains populated; snapshot exchange is prohibited")
        fence_records = helper_ns["read_fence_ledger"]("/var/lib/vst-runner/private/fence-ledger.json")
        fence_record = fence_records[-1]
        if (fence_record.get("unit") != "vst-runner.service"
                or fence_record.get("state") != "STOPPED_EMPTY"
                or fence_record.get("invocation_id") != runner["invocation_id"]
                or fence_record.get("control_group") != runner["control_group"]):
            raise SystemExit("Runner lacks an exact STOPPED_EMPTY fence for its captured invocation")
        recorded_at = datetime.fromisoformat(str(fence_record["recorded_at"]).replace("Z", "+00:00"))
        if runner["active"] and recorded_at.astimezone(timezone.utc) < runner_stop_started:
            raise SystemExit("Runner STOPPED_EMPTY fence is stale relative to this stop")
        helper_ns["record_runner_stopped_empty"](
            transaction, inactive=True, cgroup_empty=True, fence_record=fence_record)

    for item in p["files"]:
        if item["destination"] not in guard_paths:
            backup_record = transaction["configuration_backup_records"].get(item["destination"], {})
            results.append(install_config_file(
                item, predecessor_backup=backup_record.get("predecessor_backup")))
    reload = subprocess.run(["/usr/bin/systemctl", "daemon-reload"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            check=False, timeout=30)
    if reload.returncode != 0:
        raise SystemExit("systemd did not reload the exact installed configuration")
    for unit in protected_units:
        verify_persistent_guard(unit)
        if unit_value(unit, "ActiveState") != "inactive":
            raise SystemExit("protected service unexpectedly became active while fenced: " + unit)
    for unit, before in unit_before.items():
        if unit == "vst-dispatch-owner.socket" and unit_value(unit, "ActiveState") != (
                "active" if before["active"] else "inactive"):
            raise SystemExit("separate dispatch-owner socket activation changed unexpectedly")

    helper_ns["exchange_candidate"](
        transaction, recovery_path=recovery_path,
        marker_path="/var/lib/vst-runner/private/snapshot-transaction-incomplete.json")
    if not verify_runtime_mask("vst-runner.service") or not verify_runtime_mask("vst-dispatcher.service"):
        raise SystemExit("transaction-owned runtime masks disappeared before activation restoration")
    runner_verified = not activation_state["vst-runner.service"]
    dispatcher_verified = not activation_state["vst-dispatcher.service"]
    try:
        for unit in protected_units:
            run_systemctl("unmask", "--runtime", unit)
        if activation_state["vst-runner.service"]:
            run_systemctl("start", "vst-runner.service", timeout=60)
            if unit_value("vst-runner.service", "ActiveState") != "active":
                raise SystemExit("previously active Runner did not return to active")
            runner_invocation = unit_value("vst-runner.service", "InvocationID")
            generation = read_runner_generation()
            records = helper_ns["read_fence_ledger"]("/var/lib/vst-runner/private/fence-ledger.json")
            if (generation.get("state") != "RUNNING"
                    or generation.get("invocation_id") != runner_invocation
                    or not records or records[-1].get("state") != "RUNNING"
                    or records[-1].get("invocation_id") != runner_invocation):
                raise SystemExit("Runner generation is not fenced to its new active invocation")
            runner_verified = True
        if activation_state["vst-dispatcher.service"]:
            if not runner_verified:
                raise SystemExit("Dispatcher cannot start before the new Runner generation is verified")
            run_systemctl("start", "vst-dispatcher.service", timeout=60)
            dispatcher_verified = unit_value("vst-dispatcher.service", "ActiveState") == "active"
            if not dispatcher_verified:
                raise SystemExit("previously active Dispatcher did not return to active")
        for unit in protected_units:
            expected_active = activation_state[unit]
            actual_active = unit_value(unit, "ActiveState") == "active"
            if actual_active != expected_active:
                raise SystemExit("protected unit activation state differs from its captured baseline")
        helper_ns["mark_activation_restored"](
            transaction, runner_verified=runner_verified,
            dispatcher_verified=dispatcher_verified, original_activation=activation_state)
    except BaseException as activation_error:
        marker_identity = helper_ns["create_durable_marker"](
            transaction["marker_path"],
            {key:transaction[key] for key in helper_ns["_TRANSACTION_FIELDS"]})
        transaction["marker_identity"] = marker_identity
        transaction["marker_present"] = True
        helper_ns["record_state"](
            transaction, "MARKER_CLEARED", "RECOVERY_REQUIRED",
            marker_device=marker_identity[0], marker_inode=marker_identity[1],
            reason="activation restoration failed; durable start guard was re-established",
            error_type=type(activation_error).__name__)
        mask_paths_before = {unit:(verify_runtime_mask(unit) or None) for unit in protected_units}
        helper_ns["record_state"](transaction, "RECOVERY_REQUIRED", "FENCING",
                                   runtime_mask_paths_before=mask_paths_before)
        quiescence_failures = []
        for unit in ("vst-dispatcher.service", "vst-runner.service"):
            try:
                if unit_value(unit, "ActiveState") == "active":
                    run_systemctl("stop", unit, timeout=1910)
            except BaseException as stop_error:
                quiescence_failures.append(unit + ":stop:" + type(stop_error).__name__)
            try:
                if (unit_value(unit, "ActiveState") != "inactive"
                        or not cgroup_is_empty(unit_before[unit]["control_group"])):
                    quiescence_failures.append(unit + ":still-active-or-populated")
            except BaseException as verify_error:
                quiescence_failures.append(unit + ":verify:" + type(verify_error).__name__)
        refreshed_masks = {}
        for unit in protected_units:
            refreshed_masks[unit] = helper_ns["ensure_runtime_mask"](
                transaction, unit, mask_paths_before)
        helper_ns["record_fenced"](transaction, refreshed_masks)
        helper_ns["record_state"](
            transaction, "FENCED", "RECOVERY_REQUIRED",
            reason="activation restoration failed after exact target verification",
            error_type=type(activation_error).__name__,
            quiescence_failures=quiescence_failures, runtime_masks=refreshed_masks)
        if quiescence_failures:
            raise SystemExit("activation failed and protected services remain active or unverified: "
                             + ",".join(quiescence_failures)) from activation_error
        raise
    task_source_snapshot_result = "installed-atomically"
except BaseException:
    # Marker, journal, masks and both tree identities are intentionally retained.
    # No automatic cleanup or service start is permitted after an ambiguous failure.
    raise
print(json.dumps({"schema":"VST_S2_RUNTIME_CONFIG_APPLY_RESULT_V2",
                  "deployment_source_commit":deployment_commit,
                  "source_head":p["source_head"], "task_source_head":TASK_HEAD,
                  "inventory_sha256":p["inventory_sha256"], "boot_id":p["expected_boot_id"],
                  "task_source_snapshot":{"head":snapshot["head"], "tree_sha1":snapshot["tree_sha1"],
                      "format":snapshot["format"], "sha256":snapshot["sha256"],
                      "object_count":snapshot["object_count"],
                      "read_only_git_proof":task_stage_proof,
                      "destination":TASK_REPOSITORY_ROOT, "recovery_path":recovery_path,
                      "result":task_source_snapshot_result,
                      "transaction_id":transaction["transaction_id"],
                      "journal_path":transaction["journal_path"], "state":transaction["state"]},
                  "daemon_reload":"success", "files":results}, sort_keys=True, separators=(",",":")))
'''


_RECOVERY_REMOTE = r'''import base64, fcntl, hashlib, json, os, platform, re, stat, subprocess, sys, time

TASK_HEAD = "67361bb4aa23355d9a6bc7877a987ba688559eda"
TASK_TREE = "0c4a8440a38027563d2455024af6b58072fe3b57"
TASK_REPOSITORY_ROOT = "/var/lib/vst-runner/repository"
EXPECTED_REPO_ROOT = "/mnt/d/Repo/Virtual_scrum_team"
expected_sha, deployment_commit, repo_root, transaction_id = sys.argv[1:5]
raw = sys.stdin.buffer.read(1024 * 1024 + 1)
if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha:
    raise SystemExit("recovery request digest/size invalid")
try:
    request = json.loads(raw)
except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    raise SystemExit("recovery request is invalid JSON") from exc
if (os.geteuid() != 0 or platform.system() != "Linux" or repo_root != EXPECTED_REPO_ROOT
        or not re.fullmatch(r"[0-9a-f]{40}", deployment_commit)
        or not re.fullmatch(r"[0-9a-f]{32}", transaction_id)
        or request.get("schema") != "VST_S2_RUNTIME_TRANSACTION_RECOVERY_V1"
        or request.get("transaction_id") != transaction_id):
    raise SystemExit("recovery request identity is outside the fixed contract")
if subprocess.run(["/usr/bin/git", "-C", repo_root, "--no-replace-objects", "rev-parse", "--verify", "HEAD"],
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False).stdout.strip().decode() != deployment_commit:
    raise SystemExit("recovery source checkout differs from the exact approved deployment commit")
helper_raw = base64.b64decode(request.get("transaction_helper_b64", ""), validate=True)
helper_sha = request.get("transaction_helper_sha256")
committed_helper = subprocess.run(
    ["/usr/bin/git", "-C", repo_root, "--no-replace-objects", "show",
     deployment_commit + ":tools/qa/runtime_snapshot_transaction.py"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
if (not helper_raw or len(helper_raw) > 512 * 1024 or committed_helper.returncode
        or helper_raw != committed_helper.stdout or hashlib.sha256(helper_raw).hexdigest() != helper_sha):
    raise SystemExit("recovery helper differs from its exact approved Git blob")
helper = {"__name__":"_vst_s2_runtime_snapshot_transaction"}
exec(compile(helper_raw, "runtime_snapshot_transaction.py", "exec", dont_inherit=True), helper)

def systemctl(*args, timeout=30):
    result = subprocess.run(["/usr/bin/systemctl", *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            check=False, timeout=timeout)
    if result.returncode:
        raise RuntimeError("systemd recovery command failed: " + " ".join(args[:3]))
    return result.stdout.strip()

def value(unit, prop):
    return systemctl("show", "--property=" + prop, "--value", unit)

def cgroup_empty(group):
    if not isinstance(group, str) or not group.startswith("/") or ".." in group.split("/") or group == "/":
        return False
    path = "/sys/fs/cgroup/" + group.lstrip("/")
    if not os.path.lexists(path):
        return True
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        return False
    with open(os.path.join(path, "cgroup.events"), "r", encoding="ascii") as stream:
        events = dict(line.split() for line in stream)
    with open(os.path.join(path, "cgroup.procs"), "r", encoding="ascii") as stream:
        pids = stream.read().split()
    return events.get("populated") == "0" and not pids

def mask_identity(unit):
    path = "/run/systemd/system/" + unit
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if (not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or info.st_nlink != 1 or os.readlink(path) != "/dev/null"):
        raise RuntimeError("transaction runtime mask is absent or not exact: " + unit)
    return {"device":info.st_dev, "inode":info.st_ino, "target":"/dev/null"}

units = ("vst-runner.service", "vst-dispatcher.service")
lock_path = "/run/vst-s2-config-apply.lock"
lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
lock_info = os.fstat(lock_fd)
if (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != 0 or lock_info.st_gid != 0
        or stat.S_IMODE(lock_info.st_mode) != 0o600 or lock_info.st_nlink != 1):
    raise SystemExit("recovery lock identity is unsafe")
fcntl.flock(lock_fd, fcntl.LOCK_EX)
transaction = helper["load_transaction_for_recovery"](transaction_id)
if transaction.get("task_source_head") != TASK_HEAD:
    raise SystemExit("recovery journal task-source pin differs")
if transaction.get("marker_present"):
    last_marker_record = next((record for record in reversed(transaction["records"])
                               if "marker_device" in record and "marker_inode" in record), None)
    observed_identity = transaction.get("marker_identity")
    if (last_marker_record is None or
            (last_marker_record.get("marker_device"), last_marker_record.get("marker_inode")) != observed_identity):
        state = transaction["state"]
        facts = {"marker_device":observed_identity[0], "marker_inode":observed_identity[1],
                 "reason":"explicit recovery durably adopted its exact re-established marker"}
        if state in {"GUARDS_VERIFIED", "ACTIVATION_READY", "MARKER_CLEARED", "FENCING"}:
            helper["record_state"](transaction, state, "RECOVERY_REQUIRED", **facts)
        elif state == "RECOVERY_REQUIRED":
            helper["_append_journal"](transaction["journal_path"], transaction,
                                      "RECOVERY_REQUIRED", **facts)
        else:
            raise SystemExit("re-established marker is not bound to a recoverable transaction state")
        transaction.update({"state":"RECOVERY_REQUIRED",
                            "records":helper["_read_journal"](transaction["journal_path"])})
prior_commit = transaction.get("deployment_commit")
ancestor = subprocess.run(
    ["/usr/bin/git", "-C", repo_root, "--no-replace-objects", "merge-base", "--is-ancestor",
     prior_commit, deployment_commit], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
if not re.fullmatch(r"[0-9a-f]{40}", str(prior_commit)) or ancestor.returncode:
    raise SystemExit("recovery journal deployment commit is not an ancestor of the approved current source")
guards = {}
for unit in units:
    guards[unit] = helper["persistent_guard_loaded"](unit)
if guards != {unit:True for unit in units}:
    raise SystemExit("both exact persistent recovery guards are not effective")
masks = {unit:mask_identity(unit) for unit in units}
recorded_masks = next((record.get("runtime_masks") for record in reversed(transaction["records"])
                       if isinstance(record.get("runtime_masks"), dict)), None)
if transaction.get("state") == "ACTIVATION_RESTORED":
    if transaction.get("marker_present") or any(mask is not None for mask in masks.values()):
        raise SystemExit("completed recovery has a marker or runtime mask that must remain absent")
    actual_activation = {unit:value(unit, "ActiveState") == "active" for unit in units}
    if actual_activation != transaction["activation_state"]:
        raise SystemExit("completed recovery activation differs from its durable result")
    layout = helper["reconcile_snapshot_paths"](transaction)
    safe_head, safe_tree = ((TASK_HEAD, TASK_TREE) if layout["live"] == "candidate"
                            else (transaction["old_head"], transaction["old_tree_sha1"]))
    if layout["live"] == "candidate":
        proof = helper["_verify_git_readonly"](transaction["live_path"])
        if (proof.get("head"), proof.get("tree_sha1")) != (safe_head, safe_tree):
            raise SystemExit("completed recovery candidate Git identity changed")
    for path, configuration in transaction["configuration_state"].items():
        expected = (configuration["expected_new"] if layout["live"] == "candidate"
                    else configuration["expected_current"])
        if (layout["live"] == "old" and path in helper["PREINSTALLED_GUARD_PATHS"]
                and expected.get("state") == "absent"):
            expected = configuration["expected_new"]
        if helper["_config_fingerprint"](path)[0] != expected:
            raise SystemExit("completed recovery configuration set changed: " + path)
    if actual_activation["vst-runner.service"]:
        invocation = value("vst-runner.service", "InvocationID")
        fences = helper["read_fence_ledger"]("/var/lib/vst-runner/private/fence-ledger.json")
        if (not fences or fences[-1].get("unit") != "vst-runner.service"
                or fences[-1].get("state") != "RUNNING"
                or fences[-1].get("invocation_id") != invocation):
            raise SystemExit("completed recovery Runner invocation no longer matches its RUNNING fence")
    print(json.dumps({"schema":"VST_S2_RUNTIME_TRANSACTION_RECOVERY_RESULT_V1",
                      "transaction_id":transaction_id, "safe_tree":layout["live"],
                      "safe_head":safe_head, "state":"ACTIVATION_RESTORED",
                      "marker_present":False, "activation_state":transaction["activation_state"],
                      "runtime_masks_removed":True, "already_restored":True},
                     sort_keys=True, separators=(",",":")))
    raise SystemExit(0)
def persist_recovery_marker():
    if transaction.get("marker_present"):
        return
    base = {key:transaction[key] for key in helper["_TRANSACTION_FIELDS"]}
    identity = helper["create_durable_marker"](transaction["marker_path"], base)
    facts = {"marker_device":identity[0], "marker_inode":identity[1],
             "reason":"explicit recovery re-established the persistent guard before service quiescence"}
    state = transaction["state"]
    if state in {"GUARDS_VERIFIED", "ACTIVATION_READY", "MARKER_CLEARED"}:
        helper["record_state"](transaction, state, "RECOVERY_REQUIRED", **facts)
    elif state == "RECOVERY_REQUIRED":
        helper["_append_journal"](transaction["journal_path"], transaction,
                                  "RECOVERY_REQUIRED", **facts)
    else:
        raise SystemExit("cannot re-establish the transaction marker from this state")
    transaction.update({"marker_identity":identity, "marker_present":True,
                        "state":"RECOVERY_REQUIRED",
                        "records":helper["_read_journal"](transaction["journal_path"])})

if transaction.get("state") == "GUARDS_VERIFIED" and not transaction.get("marker_present"):
    persist_recovery_marker()

state = transaction.get("state")
need_fence = False
if isinstance(recorded_masks, dict) and masks == recorded_masks:
    pass
elif transaction.get("marker_present") and state in {"GUARDS_VERIFIED", "MARKER_DURABLE", "FENCING"}:
    if state == "FENCING":
        fencing_record = next((record for record in reversed(transaction["records"])
                               if record.get("state") == "FENCING"), {})
        intent = fencing_record.get("runtime_mask_paths_before")
        prepared = fencing_record.get("prepared_runtime_masks", {})
        if (not isinstance(intent, dict) or set(intent) != set(units)
                or not isinstance(prepared, dict) or not set(prepared).issubset(units)
                or any(masks[unit] is not None
                       and masks[unit] != prepared.get(unit, intent[unit])
                       for unit in units)):
            raise SystemExit("partial runtime masks differ from the exact prepared fence inode or intent")
    elif any(mask is not None for mask in masks.values()):
        raise SystemExit("runtime masks appeared before the durable fencing intent")
    need_fence = True
elif (transaction.get("marker_present") and state == "RECOVERY_REQUIRED"
      and recorded_masks is None):
    fencing_record = next((record for record in reversed(transaction["records"])
                           if record.get("state") == "FENCING"), None)
    if fencing_record is None:
        if any(mask is not None for mask in masks.values()):
            raise SystemExit("runtime masks appeared before any durable fencing intent")
    else:
        intent = fencing_record.get("runtime_mask_paths_before")
        prepared = fencing_record.get("prepared_runtime_masks", {})
        if (not isinstance(intent, dict) or set(intent) != set(units)
                or not isinstance(prepared, dict) or not set(prepared).issubset(units)
                or any(masks[unit] is not None
                       and masks[unit] != prepared.get(unit, intent[unit])
                       for unit in units)):
            raise SystemExit("recovery-required mask state lacks its exact pre-fence inode lineage")
    need_fence = True
elif transaction.get("marker_present") and state in {
        "FENCED", "DISPATCHER_DRAINED", "RUNNER_STOPPED_EMPTY", "RUNNER_BOOTSTRAP_EMPTY", "EXCHANGED",
        "OLD_RETAINED", "TARGET_VERIFIED", "ACTIVATION_READY", "RECOVERY_REQUIRED"}:
    if not isinstance(recorded_masks, dict) or any(
            masks[unit] not in (None, recorded_masks.get(unit)) for unit in units):
        raise SystemExit("runtime masks differ from their durable pre-recovery identities")
    need_fence = masks != recorded_masks
elif state in {"ACTIVATION_READY", "MARKER_CLEARED", "RECOVERY_REQUIRED"}:
    if not isinstance(recorded_masks, dict) or any(
            masks[unit] not in (None, recorded_masks.get(unit)) for unit in units):
        raise SystemExit("runtime mask was replaced by an unrecorded inode")
    persist_recovery_marker()
    need_fence = masks != recorded_masks
else:
    raise SystemExit("current runtime masks do not match a recoverable transaction state")
if need_fence:
    if transaction.get("state") == "GUARDS_VERIFIED":
        identity = transaction.get("marker_identity")
        if identity is None:
            raise SystemExit("recovery cannot bind its observed durable transaction marker")
        helper["_append_journal"](transaction["journal_path"], transaction, "MARKER_DURABLE",
                                  marker_device=identity[0], marker_inode=identity[1],
                                  recovery_observed_marker=True)
        transaction.update({"state":"MARKER_DURABLE",
                            "records":helper["_read_journal"](transaction["journal_path"])})
    if transaction.get("state") == "MARKER_DURABLE":
        helper["record_state"](transaction, "MARKER_DURABLE", "FENCING",
                                runtime_mask_paths_before=masks)
    elif transaction.get("state") == "MARKER_CLEARED":
        helper["record_state"](transaction, "MARKER_CLEARED", "RECOVERY_REQUIRED",
                                reason="recovery re-established runtime fencing")
        helper["record_state"](transaction, "RECOVERY_REQUIRED", "FENCING",
                                runtime_mask_paths_before=masks)
    elif transaction.get("state") == "ACTIVATION_READY":
        helper["record_state"](transaction, "ACTIVATION_READY", "RECOVERY_REQUIRED",
                                reason="recovery re-established runtime fencing")
        helper["record_state"](transaction, "RECOVERY_REQUIRED", "FENCING",
                                runtime_mask_paths_before=masks)
    elif transaction.get("state") == "RECOVERY_REQUIRED":
        helper["record_state"](transaction, "RECOVERY_REQUIRED", "FENCING",
                                runtime_mask_paths_before=masks)
    elif transaction.get("state") in {
            "FENCED", "DISPATCHER_DRAINED", "RUNNER_STOPPED_EMPTY", "RUNNER_BOOTSTRAP_EMPTY", "EXCHANGED",
            "OLD_RETAINED", "TARGET_VERIFIED"}:
        helper["record_state"](transaction, transaction["state"], "RECOVERY_REQUIRED",
                                reason="recovery re-established volatile runtime masks")
        helper["record_state"](transaction, "RECOVERY_REQUIRED", "FENCING",
                                runtime_mask_paths_before=masks)
    elif transaction.get("state") != "FENCING":
        raise SystemExit("recovery could not durably enter the exact FENCING state")
    fencing_record = next((record for record in reversed(
        helper["_read_journal"](transaction["journal_path"]))
        if record.get("state") == "FENCING"), {})
    mask_paths_before = fencing_record.get("runtime_mask_paths_before")
    if not isinstance(mask_paths_before, dict) or set(mask_paths_before) != set(units):
        raise SystemExit("recovery lacks the exact durable FENCING intent")
before = {}
for unit in units:
    before[unit] = {"active":value(unit, "ActiveState") == "active",
                     "control_group":value(unit, "ControlGroup"),
                     "invocation_id":value(unit, "InvocationID")}
bootstrap_recovery = (
    all(transaction["activation_state"][unit] is False for unit in units)
    and all(not before[unit]["active"] and not before[unit]["invocation_id"]
            and not before[unit]["control_group"] for unit in units))
if bootstrap_recovery and need_fence:
    # Establish the exact journal-owned masks before collecting cold proof.
    current_masks = {}
    for unit in units:
        current_masks[unit] = helper["ensure_runtime_mask"](
            transaction, unit, mask_paths_before)
    helper["record_fenced"](transaction, current_masks)
    transaction["records"] = helper["_read_journal"](transaction["journal_path"])
    masks = current_masks
    need_fence = False
runner_stop_started = time.time()
for unit in ("vst-dispatcher.service", "vst-runner.service"):
    if before[unit]["active"]:
        systemctl("stop", unit, timeout=1910)
    if value(unit, "ActiveState") != "inactive" or not cgroup_empty(before[unit]["control_group"]):
        raise SystemExit("protected service did not reach exact inactive/empty state: " + unit)
bootstrap_proof = None
if bootstrap_recovery:
    bootstrap_proof = helper["ensure_bootstrap_predecessor"](
        transaction, create_baseline=False)
else:
    fences = helper["read_fence_ledger"]("/var/lib/vst-runner/private/fence-ledger.json")
    if not fences:
        raise SystemExit("recovery lacks a durable Runner STOPPED_EMPTY fence")
    fence = fences[-1]
    if (fence.get("unit") != "vst-runner.service" or fence.get("state") != "STOPPED_EMPTY"
            or fence.get("control_group") != before["vst-runner.service"]["control_group"]
            or (before["vst-runner.service"]["invocation_id"]
                and fence.get("invocation_id") != before["vst-runner.service"]["invocation_id"])):
        raise SystemExit("latest Runner fence is not bound to the observed stopped invocation")
    recorded_at = fence.get("recorded_at")
    if before["vst-runner.service"]["active"]:
        from datetime import datetime, timezone
        if datetime.fromisoformat(str(recorded_at).replace("Z", "+00:00")).timestamp() < runner_stop_started:
            raise SystemExit("Runner STOPPED_EMPTY fence predates this recovery stop")
if need_fence:
    current_masks = {}
    for unit in units:
        current_masks[unit] = helper["ensure_runtime_mask"](
            transaction, unit, mask_paths_before)
    helper["record_fenced"](transaction, current_masks)
    transaction["records"] = helper["_read_journal"](transaction["journal_path"])
    masks = current_masks
result = helper["recover_snapshot_transaction"](
    transaction, guards_verified=guards, runtime_masks_owned=masks,
    services_quiesced={unit:True for unit in units}, bootstrap_proof=bootstrap_proof)
if result.get("marker_present") or not result.get("runtime_masks_must_remain"):
    raise SystemExit("recovery did not reach its exact masked terminal state")
runner_verified = not transaction["activation_state"]["vst-runner.service"]
dispatcher_verified = not transaction["activation_state"]["vst-dispatcher.service"]
try:
    for unit in units:
        systemctl("unmask", "--runtime", unit)
    if transaction["activation_state"]["vst-runner.service"]:
        systemctl("start", "vst-runner.service", timeout=60)
        invocation = value("vst-runner.service", "InvocationID")
        generation_fd = os.open("/var/lib/vst-runner/generation.json", os.O_RDONLY | os.O_NOFOLLOW)
        try:
            generation_info = os.fstat(generation_fd)
            if not stat.S_ISREG(generation_info.st_mode) or generation_info.st_uid != 0 or generation_info.st_size > 65536:
                raise RuntimeError("Runner generation metadata is unsafe after recovery")
            generation = json.loads(os.read(generation_fd, 65537))
        finally:
            os.close(generation_fd)
        current_fences = helper["read_fence_ledger"]("/var/lib/vst-runner/private/fence-ledger.json")
        if (value("vst-runner.service", "ActiveState") != "active"
                or generation.get("state") != "RUNNING" or generation.get("invocation_id") != invocation
                or not current_fences or current_fences[-1].get("state") != "RUNNING"
                or current_fences[-1].get("invocation_id") != invocation):
            raise RuntimeError("recovered Runner generation does not match its exact active invocation")
        runner_verified = True
    if transaction["activation_state"]["vst-dispatcher.service"]:
        if not runner_verified:
            raise RuntimeError("Dispatcher recovery requires the exact active Runner generation")
        systemctl("start", "vst-dispatcher.service", timeout=60)
        dispatcher_verified = value("vst-dispatcher.service", "ActiveState") == "active"
        if not dispatcher_verified:
            raise RuntimeError("Dispatcher did not return to its recorded activation state")
    for unit in units:
        if (value(unit, "ActiveState") == "active") != transaction["activation_state"][unit]:
            raise RuntimeError("recovered unit activation differs from its recorded predecessor")
    helper["mark_activation_restored"](
        transaction, runner_verified=runner_verified, dispatcher_verified=dispatcher_verified,
        original_activation=transaction["activation_state"])
except BaseException as exc:
    marker_identity = helper["create_durable_marker"](
        transaction["marker_path"],
        {key:transaction[key] for key in helper["_TRANSACTION_FIELDS"]})
    transaction["marker_identity"] = marker_identity
    transaction["marker_present"] = True
    helper["record_state"](
        transaction, "MARKER_CLEARED", "RECOVERY_REQUIRED",
        marker_device=marker_identity[0], marker_inode=marker_identity[1],
        reason="activation restoration failed; durable start guard was re-established",
        error_type=type(exc).__name__)
    mask_paths_before = {unit:mask_identity(unit) for unit in units}
    helper["record_state"](transaction, "RECOVERY_REQUIRED", "FENCING",
                           runtime_mask_paths_before=mask_paths_before)
    quiescence_failures = []
    for unit in ("vst-dispatcher.service", "vst-runner.service"):
        control_group = value(unit, "ControlGroup")
        try:
            if value(unit, "ActiveState") == "active":
                systemctl("stop", unit, timeout=1910)
        except BaseException as stop_error:
            quiescence_failures.append(unit + ":stop:" + type(stop_error).__name__)
        try:
            if value(unit, "ActiveState") != "inactive" or not cgroup_empty(control_group):
                quiescence_failures.append(unit + ":still-active-or-populated")
        except BaseException as verify_error:
            quiescence_failures.append(unit + ":verify:" + type(verify_error).__name__)
    refreshed_masks = {}
    for unit in units:
        refreshed_masks[unit] = helper["ensure_runtime_mask"](
            transaction, unit, mask_paths_before)
    helper["record_fenced"](transaction, refreshed_masks)
    helper["record_state"](transaction, "FENCED", "RECOVERY_REQUIRED",
                           reason="activation restoration failed after safe recovery",
                           error_type=type(exc).__name__,
                           quiescence_failures=quiescence_failures,
                           runtime_masks=refreshed_masks)
    if quiescence_failures:
        raise RuntimeError("activation recovery failed and a protected service remains active/unverified: "
                           + ",".join(quiescence_failures)) from exc
    raise
print(json.dumps({"schema":"VST_S2_RUNTIME_TRANSACTION_RECOVERY_RESULT_V1",
                  "transaction_id":transaction_id, "safe_tree":result["safe_tree"],
                  "safe_head":result["safe_head"], "state":transaction["state"],
                  "marker_present":transaction["marker_present"],
                  "activation_state":transaction["activation_state"],
                  "runtime_masks_removed":True}, sort_keys=True, separators=(",",":")))
'''


def _validate_embedded_programs() -> None:
    """Compile embedded root-side programs before any command can build a payload."""
    compile(_WSL_SOURCE_LOADER, "<vst-s2-runtime-loader>", "exec")
    compile(_REMOTE, "<vst-s2-runtime-apply>", "exec")
    compile(_RECOVERY_REMOTE, "<vst-s2-runtime-recovery>", "exec")


_validate_embedded_programs()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--inventory-sha256")
    parser.add_argument("--approved-deployment-commit", required=True)
    parser.add_argument("--distribution", default="Ubuntu-24.04")
    parser.add_argument("--recover-transaction", metavar="TRANSACTION_ID")
    args = parser.parse_args()
    try:
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--verify", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
        if head.returncode or head.stdout.strip() != args.approved_deployment_commit:
            raise ValueError("approved deployment commit does not equal the current exact checkout HEAD")
        _validate_deployment_commit(args.approved_deployment_commit)
        committed_tool = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--verify", "HEAD:tools/qa/apply_s2_runtime_configuration.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
        working_tool = subprocess.run(
            ["git", "-C", str(REPO), "hash-object", "--", "tools/qa/apply_s2_runtime_configuration.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True, cwd=REPO)
        if (committed_tool.returncode or working_tool.returncode
                or committed_tool.stdout.strip() != working_tool.stdout.strip()):
            raise ValueError("installer source differs from the exact committed Git blob")
        if args.recover_transaction:
            if args.inventory is not None or args.inventory_sha256 is not None:
                raise ValueError("transaction recovery does not accept an inventory payload")
            if not re.fullmatch(r"[0-9a-f]{32}", args.recover_transaction):
                raise ValueError("recovery transaction ID must be 128-bit lowercase hex")
            helper_bytes = _git_blob(args.approved_deployment_commit,
                                     "tools/qa/runtime_snapshot_transaction.py")
            recovery_payload = json.dumps({
                "schema": "VST_S2_RUNTIME_TRANSACTION_RECOVERY_V1",
                "transaction_id": args.recover_transaction,
                "transaction_helper_b64": base64.b64encode(helper_bytes).decode("ascii"),
                "transaction_helper_sha256": _sha(helper_bytes),
            }, sort_keys=True, separators=(",", ":")).encode("ascii")
            digest = _sha(recovery_payload)
            wsl = subprocess.run(
                ["wsl.exe", "--distribution", args.distribution, "--user", "root", "--exec",
                 "/usr/bin/python3.12", "-I", "-B", "-S", "-c", _WSL_SOURCE_LOADER,
                 digest, args.approved_deployment_commit, WSL_REPOSITORY_ROOT,
                 args.recover_transaction],
                input=_remote_stdin(_RECOVERY_REMOTE, recovery_payload), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            if wsl.stdout:
                print(wsl.stdout.decode("utf-8", errors="replace").rstrip())
            if wsl.returncode:
                print(wsl.stderr.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
                return wsl.returncode
            return 0
        if args.inventory is None or args.inventory_sha256 is None:
            raise ValueError("normal apply requires both --inventory and --inventory-sha256")
        expected_repo_head, expected_capture_sha256 = _current_inventory_validation_identity()
        payload = build_payload(
            args.inventory, args.inventory_sha256, args.approved_deployment_commit,
            expected_repo_head=expected_repo_head,
            expected_capture_sha256=expected_capture_sha256,
        )
        digest = _sha(payload)
        wsl = subprocess.run(
            ["wsl.exe", "--distribution", args.distribution, "--user", "root", "--exec",
             "/usr/bin/python3.12", "-I", "-B", "-S", "-c", _WSL_SOURCE_LOADER,
             digest, args.approved_deployment_commit, WSL_REPOSITORY_ROOT],
            input=_remote_stdin(_REMOTE, payload), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
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
