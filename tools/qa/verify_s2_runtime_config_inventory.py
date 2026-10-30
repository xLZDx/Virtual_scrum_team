#!/usr/bin/env python3
"""Validate a complete, read-only S2 runtime inventory before config apply."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
INVENTORY_SCHEMA = "VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1"
SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"
IMPLEMENTATION_HEAD = "6fb47d966814005ea51992c37d8af342a7cb4219"
PREVIOUS_CONFIG_HEAD = "7d1d16f6348e6c00a5a568b5cfbc8caf309194b9"
PREVIOUS_BUNDLE_SHA256 = "388e6bb00f97b54bbd456994ccdd399317ab2e527c6f37d8a1b71ce20a280e45"
PREVIOUS_LAYOUT_SHA256 = "47d3e66f1d765c0b078428708d2d9bf6c0218085714878e11395d164d57d1c19"
CANDIDATE_BUNDLE_SHA256 = "05530c73ea583f0f7f60963ba9e196082dfb7abf92f86f0a0e2a0ae9ad10f91f"
CANDIDATE_LAYOUT_SHA256 = PREVIOUS_LAYOUT_SHA256
RUN_ID = "s2-runtime-20261030-1977eaba61274396b6b58d069c5cede2"
REQUEST_ID = "98b38065170f468c9943aa8f22160ff9"
NONCE = "a2a0dcab58b9451281ff0a7b079d4aa2"
CONSUMED_RUN_ID = "s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910"
CONSUMED_REQUEST_ID = "e520e04f58ad5e6a431a3a20b0efb87c"
CONSUMED_NONCE = "0aac24fec9a2a5c53c5e9da21cbb4a42"
# Keep all one-shot identities observed in the accepted config-history contract. A
# candidate must never revive an older run/request/nonce just because the immediately
# previous attempt has since changed.
HISTORIC_CONSUMED_IDENTITIES = (
    ("212a23e66ee94a7d87355b11e07e34fe",
     "s2-runtime-20261030-334296bd0779488d837a27e283b50b6a",
     "b57520d076e1acd355d310ed18364907"),
    ("3e56a61c5b1e45aea089c305b25e3187",
     "s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8",
     "0d2bb2c5f977478a924f7ec6629a339d"),
    ("c63842aefcf74f57af70a1b2f93b8271",
     "s2-runtime-20261030-8102de64e7b4472ca2b5d2d56ed48510",
     "5f5820a7cfc348cfa89de31af6c6d1a7"),
)
RUNTIME_PATH = "/opt/vst-runtime-" + SOURCE_HEAD
BASELINE_RUN_ID = "s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910"
BASELINE_REQUEST_ID = "e520e04f58ad5e6a431a3a20b0efb87c"
BASELINE_NONCE = "0aac24fec9a2a5c53c5e9da21cbb4a42"
UNITS = (
    "vst-assignment-bootstrap.service",
    "vst-dispatch-issuer.service",
    "vst-dispatch-owner.service",
    "vst-dispatch-owner.socket",
    "vst-dispatcher.service",
    "vst-runner.service",
    "vst-sandbox-probe.service",
    "vst-signer.service",
    "vst-supervisor.service",
)
CONTAINER_SOCKETS = (
    "/run/containerd/containerd.sock",
    "/run/docker.sock",
    "/run/podman/podman.sock",
    "/var/run/docker.sock",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
BOOT_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class InventoryError(ValueError):
    """The target snapshot is incomplete, stale, or differs from the approved baseline."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob(commit: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "show", f"{commit}:{relative_path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise InventoryError("pinned configuration baseline blob is unavailable: " + relative_path)
    return result.stdout


def _previous_installed_fingerprints() -> dict[str, dict[str, Any]]:
    bundle_raw = _git_blob(PREVIOUS_CONFIG_HEAD, "docs/sdlc/runtime-config/bundle-manifest.json")
    layout_raw = _git_blob(PREVIOUS_CONFIG_HEAD, "docs/sdlc/runtime-config/installation-layout.json")
    if (_sha(bundle_raw) != PREVIOUS_BUNDLE_SHA256
            or _sha(layout_raw) != PREVIOUS_LAYOUT_SHA256):
        raise InventoryError("consumed-run configuration baseline does not match its pinned hashes")
    bundle = json.loads(bundle_raw)
    layout = json.loads(layout_raw)
    if (bundle.get("state") != "PREPARED_NOT_INSTALLED"
            or bundle.get("runtime_source_head") != SOURCE_HEAD):
        raise InventoryError("consumed-run bundle is not the pinned S2 runtime candidate")
    bundle_records = {record["path"]: record for record in bundle["files"]}
    bootstrap = json.loads(_git_blob(
        PREVIOUS_CONFIG_HEAD, "docs/sdlc/runtime-config/bootstrap-request.json"))
    probe = json.loads(_git_blob(
        PREVIOUS_CONFIG_HEAD, "docs/sdlc/runtime-config/probe-request.json"))
    if (bootstrap.get("request_id") != BASELINE_REQUEST_ID
            or bootstrap.get("run_id") != BASELINE_RUN_ID
            or probe.get("nonce") != BASELINE_NONCE
            or probe.get("run_id") != BASELINE_RUN_ID):
        raise InventoryError("pinned consumed-run baseline identity is inconsistent")
    entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
    entries += [item for item in bundle["units"]
                if item["publication"].startswith("new absent-only configuration unit")]
    if len(entries) != 26 or len({item["destination"] for item in entries}) != 26:
        raise InventoryError("consumed-run baseline is not the exact 26-destination set")

    expected: dict[str, dict[str, Any]] = {}
    for item in entries:
        source = item["source"]
        if not isinstance(source, str) or source.startswith("/") or ".." in Path(source).parts:
            raise InventoryError("pinned baseline contains an unsafe bundle source path")
        raw = _git_blob(PREVIOUS_CONFIG_HEAD, "docs/sdlc/runtime-config/" + source)
        record = bundle_records.get(source)
        if record is None or len(raw) != record["size"] or _sha(raw) != record["sha256"]:
            raise InventoryError("consumed-run source does not match its bundle member digest")
        mode = int(item["mode"], 8) if isinstance(item["mode"], str) else item["mode"]
        expected[item["destination"]] = {
            "state": "file",
            "uid": item["uid"],
            "gid": item["gid"],
            "mode": mode,
            "size": len(raw),
            "sha256": _sha(raw),
        }
    return expected


def _validate_candidate_identity(expected_repo_head: str) -> None:
    consumed_identities = tuple(dict.fromkeys((
        (CONSUMED_REQUEST_ID, CONSUMED_RUN_ID, CONSUMED_NONCE),
        (BASELINE_REQUEST_ID, BASELINE_RUN_ID, BASELINE_NONCE),
        *HISTORIC_CONSUMED_IDENTITIES,
    )))
    if any(
        REQUEST_ID == request_id or RUN_ID == run_id or NONCE == nonce
        for request_id, run_id, nonce in consumed_identities
    ):
        raise InventoryError("candidate run/request/nonce reuses a consumed identity")

    bundle_raw = _git_blob(expected_repo_head, "docs/sdlc/runtime-config/bundle-manifest.json")
    if _sha(bundle_raw) != CANDIDATE_BUNDLE_SHA256:
        raise InventoryError("candidate bundle differs from its exact SHA-256 pin")
    bundle = json.loads(bundle_raw)
    if (bundle.get("schema") != "VST_S2_NON_SECRET_CONFIG_BUNDLE_V1"
            or bundle.get("state") != "PREPARED_NOT_INSTALLED"
            or bundle.get("runtime_source_head") != SOURCE_HEAD
            or not isinstance(bundle.get("files"), list)):
        raise InventoryError("candidate bundle schema/state/source is invalid")
    records = {item.get("path"): item for item in bundle["files"] if isinstance(item, dict)}

    def candidate_json(name: str) -> dict[str, Any]:
        raw = _git_blob(expected_repo_head, "docs/sdlc/runtime-config/" + name)
        record = records.get(name)
        if (not isinstance(record, dict) or type(record.get("size")) is not int
                or record["size"] != len(raw) or record.get("sha256") != _sha(raw)):
            raise InventoryError("candidate config differs from its bundle member: " + name)
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise InventoryError("candidate config is not a JSON object: " + name)
        return value

    bootstrap = candidate_json("bootstrap-request.json")
    probe = candidate_json("probe-request.json")
    network = candidate_json("network-profile.json")
    binding = candidate_json("run-binding.json")
    supervisor = candidate_json("supervisor-service.json")
    if (bootstrap.get("run_id") != RUN_ID or bootstrap.get("request_id") != REQUEST_ID
            or probe.get("run_id") != RUN_ID or probe.get("nonce") != NONCE
            or network.get("environment_id") != "Ubuntu-24.04:S2:" + RUN_ID
            or binding.get("run_id") != RUN_ID or binding.get("probe_nonce") != NONCE
            or binding.get("state") != "PREPARATION_NOT_EXECUTION"
            or supervisor.get("run_id") != RUN_ID or supervisor.get("probe_nonce") != NONCE):
        raise InventoryError("candidate run/request/nonce identities are not cross-bound")


def _regular_file_fingerprint(value: Any, destination: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("state") != "PRESENT":
        raise InventoryError("previously installed destination is not present: " + destination)
    if value.get("kind") != "regular":
        raise InventoryError("previously installed destination is not a regular file: " + destination)
    mode_text = value.get("mode")
    if not isinstance(mode_text, str) or not re.fullmatch(r"[0-7]{4,}", mode_text):
        raise InventoryError("configuration mode must be canonical octal text: " + destination)
    mode = int(mode_text, 8)
    if mode_text != f"{mode:04o}":
        raise InventoryError("configuration mode is not canonical octal text: " + destination)
    fields = (value.get("uid"), value.get("gid"), mode, value.get("size"))
    if any(type(field) is not int or field < 0 for field in fields):
        raise InventoryError("configuration ownership/mode/size is incomplete: " + destination)
    digest = value.get("sha256")
    if not isinstance(digest, str) or not HEX64.fullmatch(digest):
        raise InventoryError("configuration digest is invalid: " + destination)
    return {"state": "file", "uid": fields[0], "gid": fields[1], "mode": fields[2],
            "size": fields[3], "sha256": digest}


def _command_result(value: Any, label: str) -> tuple[int, str, str]:
    if not isinstance(value, dict):
        raise InventoryError(label + " command evidence is missing")
    code, stdout, stderr = value.get("exit_code"), value.get("stdout"), value.get("stderr")
    if type(code) is not int or not isinstance(stdout, str) or not isinstance(stderr, str):
        raise InventoryError(label + " command evidence is incomplete")
    if code != 0 or stderr.strip():
        raise InventoryError(label + " command failed or wrote unexpected stderr")
    return code, stdout, stderr


def validate_mount_observation(mount: Any) -> None:
    if not isinstance(mount, dict):
        raise InventoryError("read-only D: mount observation is missing")
    source_record = mount.get("source")
    filesystem_record = mount.get("filesystem_options")
    if not isinstance(source_record, dict) or not isinstance(filesystem_record, dict):
        raise InventoryError("D: mount command records are incomplete")
    if (source_record.get("command")
            != "/usr/bin/findmnt -n -o SOURCE --target /mnt/d"
            or filesystem_record.get("command")
            != "/usr/bin/findmnt -n -o FSTYPE,OPTIONS --target /mnt/d"):
        raise InventoryError("D: mount evidence is not from the pinned findmnt observations")
    _, source, _ = _command_result(source_record, "findmnt source")
    _, filesystem, _ = _command_result(filesystem_record, "findmnt filesystem/options")
    source_fields = source.split()
    mount_fields = filesystem.split()
    if source_fields != ["D:"] or len(mount_fields) != 2:
        raise InventoryError("D: mount observation is malformed or ambiguous")
    filesystem_type, options = mount_fields
    option_tokens = options.split(",")
    if filesystem_type != "9p" or "ro" not in option_tokens or "rw" in option_tokens:
        raise InventoryError("D: is not verified as the exact read-only 9p mount")


def _validate_source_identity(
        value: Any, expected_repo_head: str, expected_helper_sha256: str,
        expected_validator_sha256: str, expected_applier_sha256: str) -> None:
    if not isinstance(value, dict):
        raise InventoryError("source identity evidence is missing")
    expected = {
        "repo_head": expected_repo_head,
        "implementation_source_commit": IMPLEMENTATION_HEAD,
        "helper_sha256": expected_helper_sha256,
        "validator_sha256": expected_validator_sha256,
        "applier_sha256": expected_applier_sha256,
        "bundle_manifest_sha256": CANDIDATE_BUNDLE_SHA256,
        "installation_layout_sha256": CANDIDATE_LAYOUT_SHA256,
        "runtime_source_head": SOURCE_HEAD,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise InventoryError("source identity differs from its exact pin: " + key)


def _committed_source_sha256(expected_repo_head: str, relative_path: str) -> str:
    committed = _git_blob(expected_repo_head, relative_path)
    working = (REPO / relative_path).read_bytes()
    if committed != working:
        raise InventoryError("source file differs from its exact committed Git blob: " + relative_path)
    return _sha(committed)


def _validate_readiness(value: Any) -> None:
    if not isinstance(value, dict):
        raise InventoryError("target readiness evidence is missing")
    if (value.get("distro") != "Ubuntu-24.04"
            or not isinstance(value.get("kernel"), str)
            or "microsoft-standard-WSL2" not in value["kernel"]
            or value.get("systemd") != "running"
            or value.get("systemd_jobs") not in ("", "No jobs running.")
            or value.get("shutdown_scheduled") is not False
            or not isinstance(value.get("systemd_version"), str)
            or not value["systemd_version"].strip()):
        raise InventoryError("WSL/systemd readiness is missing, unstable, or unexpected")
    boot_id = value.get("boot_id")
    if not isinstance(boot_id, str) or not BOOT_ID.fullmatch(boot_id):
        raise InventoryError("WSL boot ID is missing or malformed")

    pid1 = value.get("pid1")
    if not isinstance(pid1, dict) or pid1.get("comm") != "systemd":
        raise InventoryError("PID 1 is not verified as systemd")
    pid1_uid = pid1.get("uid")
    pid1_gid = pid1.get("gid")
    exact_root_ids = lambda ids: (
        type(ids) is list and len(ids) == 4
        and all(type(item) is int and item == 0 for item in ids))
    if (type(pid1.get("start_ticks")) is not int or pid1["start_ticks"] <= 0
            or type(pid1.get("net_ns_inode")) is not int or pid1["net_ns_inode"] <= 0
            or type(pid1.get("mount_ns_inode")) is not int or pid1["mount_ns_inode"] <= 0
            or not exact_root_ids(pid1_uid) or not exact_root_ids(pid1_gid)):
        raise InventoryError("PID 1 identity/start-time/namespaces are incomplete or unexpected")

    accounts = value.get("accounts")
    if not isinstance(accounts, dict):
        raise InventoryError("runtime account identities are missing")
    if accounts.get("vst-runner") != {"uid": 997, "gid": 988}:
        raise InventoryError("vst-runner account identity differs from the fixed contract")
    if accounts.get("vst-worker") != {"uid": 999, "gid": 989}:
        raise InventoryError("vst-worker account identity differs from the fixed contract")

    units = value.get("units")
    if not isinstance(units, dict) or set(units) != set(UNITS):
        raise InventoryError("inventory does not contain exactly the nine required VST units")
    for name, state in units.items():
        if state != ["loaded", "inactive", "dead", "0"]:
            raise InventoryError("VST unit is not loaded and inactive: " + name)

    if value.get("runtime_selector") != RUNTIME_PATH:
        raise InventoryError("selected runtime path differs from the pinned S2 runtime")
    if value.get("store_present") is not False or value.get("preflight_present") is not False:
        raise InventoryError("Store or preflight state is not the expected unused state")
    if value.get("attestation_present") is not False:
        raise InventoryError("unexpected prior root attestation is present")
    sockets = value.get("container_sockets")
    if not isinstance(sockets, dict) or set(sockets) != set(CONTAINER_SOCKETS):
        raise InventoryError("container socket inventory is incomplete")
    if any(present is not False for present in sockets.values()):
        raise InventoryError("a container socket is present")
    if value.get("candidate_identity_collision") is not False:
        raise InventoryError("candidate run identity is already present or unknown")
    if value.get("installed_bootstrap_identity") != {
            "request_id": BASELINE_REQUEST_ID, "run_id": BASELINE_RUN_ID}:
        raise InventoryError("installed bootstrap identity is not the exact consumed baseline")


def validate_inventory(
        inventory: Any, *, expected_repo_head: str, expected_helper_sha256: str,
        now: datetime | None = None) -> dict[str, Any]:
    if not HEX40.fullmatch(expected_repo_head):
        raise InventoryError("expected repository HEAD must be a full lowercase Git object ID")
    if not HEX64.fullmatch(expected_helper_sha256):
        raise InventoryError("expected helper digest must be lowercase SHA-256")
    if not isinstance(inventory, dict) or inventory.get("schema") != INVENTORY_SCHEMA:
        raise InventoryError("target inventory schema is invalid")
    if inventory.get("source_head") != SOURCE_HEAD:
        raise InventoryError("target inventory does not identify the pinned runtime source")
    captured = inventory.get("captured_utc")
    try:
        captured_at = datetime.fromisoformat(str(captured).replace("Z", "+00:00"))
    except ValueError as exc:
        raise InventoryError("target inventory capture time is malformed") from exc
    if captured_at.tzinfo is None:
        raise InventoryError("target inventory capture time lacks timezone")
    now = now or datetime.now(timezone.utc)
    age = (now - captured_at.astimezone(timezone.utc)).total_seconds()
    if age < -30 or age > 300:
        raise InventoryError("target inventory is outside the five-minute freshness window")

    _validate_candidate_identity(expected_repo_head)
    validate_mount_observation(inventory.get("mount"))
    expected_validator_sha256 = _committed_source_sha256(
        expected_repo_head, "tools/qa/verify_s2_runtime_config_inventory.py")
    expected_applier_sha256 = _committed_source_sha256(
        expected_repo_head, "tools/qa/apply_s2_runtime_configuration.py")
    _validate_source_identity(inventory.get("source_identity"), expected_repo_head,
                              expected_helper_sha256, expected_validator_sha256,
                              expected_applier_sha256)
    readiness = inventory.get("readiness")
    _validate_readiness(readiness)
    inventory_boot_id = inventory.get("boot_id")
    if (not isinstance(inventory_boot_id, str) or not BOOT_ID.fullmatch(inventory_boot_id)
            or not isinstance(readiness, dict)
            or inventory_boot_id != readiness.get("boot_id")):
        raise InventoryError("top-level inventory boot ID is missing or differs from readiness")

    files = inventory.get("configuration_files")
    expected = _previous_installed_fingerprints()
    if not isinstance(files, dict) or set(files) != set(expected):
        raise InventoryError("inventory must contain exactly all 26 configured destinations")
    for destination, expected_fingerprint in expected.items():
        actual = _regular_file_fingerprint(files[destination], destination)
        if actual != expected_fingerprint:
            raise InventoryError("installed file differs from consumed-run baseline: " + destination)

    runtime_selector = inventory.get("runtime_selector")
    if (not isinstance(runtime_selector, dict)
            or set(runtime_selector) != {"state", "kind", "link_target"}
            or runtime_selector != {
                "state": "PRESENT", "kind": "symlink", "link_target": RUNTIME_PATH,
            }):
        raise InventoryError("runtime selector is not the exact pinned candidate")

    return {
        "schema": INVENTORY_SCHEMA,
        "source_head": SOURCE_HEAD,
        "repo_head": expected_repo_head,
        "captured_utc": captured_at.astimezone(timezone.utc).isoformat(),
        "configuration_destination_count": len(expected),
        "runtime_selector": RUNTIME_PATH,
        "mount_fstype": "9p",
        "mount_source": "D:",
        "mount_read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--helper-sha256", required=True)
    args = parser.parse_args(argv)
    if not HEX64.fullmatch(args.expected_sha256):
        parser.error("--expected-sha256 must be lowercase SHA-256")
    raw = args.inventory.read_bytes()
    if _sha(raw) != args.expected_sha256:
        raise InventoryError("inventory bytes differ from their exact SHA-256 pin")
    inventory = json.loads(raw)
    result = validate_inventory(inventory, expected_repo_head=args.expected_head,
                                expected_helper_sha256=args.helper_sha256)
    print("PASS: complete S2 runtime inventory " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InventoryError, OSError, json.JSONDecodeError) as exc:
        print("REFUSE: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
