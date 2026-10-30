from __future__ import annotations

import copy
import ast
import base64
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.qa import verify_s2_runtime_config_inventory as inventory
from tools.qa import apply_s2_runtime_configuration as applier
from tools.qa import collect_s2_runtime_config_inventory as collector


_load_pinned_baseline_fingerprints = inventory._previous_installed_fingerprints
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
EXPECTED_REPO_HEAD = subprocess.run(
    ["git", "-C", str(inventory.REPO), "rev-parse", "HEAD"],
    check=True, capture_output=True, text=True).stdout.strip()
VALIDATOR_PATH = "tools/qa/verify_s2_runtime_config_inventory.py"
APPLIER_PATH = "tools/qa/apply_s2_runtime_configuration.py"
EXPECTED_CAPTURE_SHA256 = collector.CAPTURE_SHA
WORKTREE_APPLIER_SHA256 = hashlib.sha256(Path(applier.__file__).read_bytes()).hexdigest()
EXPECTED_APPLIER_SHA256 = WORKTREE_APPLIER_SHA256
WORKTREE_VALIDATOR_SHA256 = hashlib.sha256(Path(inventory.__file__).read_bytes()).hexdigest()
EXPECTED_PREVIOUS_CONFIG_HEAD = "7d1d16f6348e6c00a5a568b5cfbc8caf309194b9"
EXPECTED_PREVIOUS_BUNDLE_SHA256 = "388e6bb00f97b54bbd456994ccdd399317ab2e527c6f37d8a1b71ce20a280e45"
EXPECTED_PREVIOUS_FINGERPRINTS_SHA256 = "e116dd237401d0f89d3ac706a883e19f53bda0bdba5f853afc153f3fc5eac095"
EXPECTED_CONSUMED_IDENTITIES = (
    ("e520e04f58ad5e6a431a3a20b0efb87c",
     "s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910",
     "0aac24fec9a2a5c53c5e9da21cbb4a42"),
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
try:
    COMMITTED_VALIDATOR_MATCHES_WORKTREE = (
        inventory._git_blob(EXPECTED_REPO_HEAD, VALIDATOR_PATH)
        == Path(inventory.__file__).read_bytes())
except inventory.InventoryError:
    COMMITTED_VALIDATOR_MATCHES_WORKTREE = False
try:
    COMMITTED_APPLIER_MATCHES_WORKTREE = (
        inventory._git_blob(EXPECTED_REPO_HEAD, APPLIER_PATH)
        == Path(applier.__file__).read_bytes())
except inventory.InventoryError:
    COMMITTED_APPLIER_MATCHES_WORKTREE = False


@pytest.fixture(scope="module")
def baseline_fingerprints() -> dict[str, dict[str, object]]:
    fingerprints = inventory._previous_installed_fingerprints()
    assert len(fingerprints) == 26
    return fingerprints


def test_consumed_predecessor_pins_all_26_installed_fingerprints(
        baseline_fingerprints) -> None:
    assert inventory.PREVIOUS_CONFIG_HEAD == EXPECTED_PREVIOUS_CONFIG_HEAD
    assert inventory.PREVIOUS_BUNDLE_SHA256 == EXPECTED_PREVIOUS_BUNDLE_SHA256
    assert (inventory.CONSUMED_REQUEST_ID, inventory.CONSUMED_RUN_ID,
            inventory.CONSUMED_NONCE) == EXPECTED_CONSUMED_IDENTITIES[0]
    assert (inventory.BASELINE_REQUEST_ID, inventory.BASELINE_RUN_ID,
            inventory.BASELINE_NONCE) == EXPECTED_CONSUMED_IDENTITIES[0]
    assert set(inventory.HISTORIC_CONSUMED_IDENTITIES) == set(EXPECTED_CONSUMED_IDENTITIES[1:])

    canonical_fingerprints = json.dumps(
        baseline_fingerprints, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(canonical_fingerprints).hexdigest() == (
        EXPECTED_PREVIOUS_FINGERPRINTS_SHA256)
    bootstrap = baseline_fingerprints["/etc/vst-runner/bootstrap-request.json"]
    assert bootstrap["size"] == 4104
    assert bootstrap["sha256"] == (
        "df0d5701e6a356d43224208cd9a099183e12404967f5133838bd978e0b7834c1")


@pytest.fixture(autouse=True)
def use_pinned_baseline(monkeypatch, baseline_fingerprints) -> None:
    monkeypatch.setattr(inventory, "_previous_installed_fingerprints",
                        lambda: baseline_fingerprints)
    if not COMMITTED_VALIDATOR_MATCHES_WORKTREE or not COMMITTED_APPLIER_MATCHES_WORKTREE:
        committed_source_sha256 = inventory._committed_source_sha256

        def candidate_validator_sha256(expected_repo_head: str, relative_path: str) -> str:
            if relative_path == VALIDATOR_PATH:
                return WORKTREE_VALIDATOR_SHA256
            if relative_path == APPLIER_PATH and not COMMITTED_APPLIER_MATCHES_WORKTREE:
                return WORKTREE_APPLIER_SHA256
            return committed_source_sha256(expected_repo_head, relative_path)

        monkeypatch.setattr(inventory, "_committed_source_sha256", candidate_validator_sha256)
    _use_candidate_config_blobs(monkeypatch)


@pytest.fixture
def valid_inventory(baseline_fingerprints) -> dict[str, object]:
    candidate_bundle = json.loads(inventory._git_blob(
        EXPECTED_REPO_HEAD, "docs/sdlc/runtime-config/bundle-manifest.json"))
    candidate_layout = json.loads(inventory._git_blob(
        EXPECTED_REPO_HEAD, "docs/sdlc/runtime-config/installation-layout.json"))
    candidate_entries = (
        list(candidate_bundle["configuration_installation"])
        + list(candidate_layout["unit_overrides"])
        + [item for item in candidate_bundle["units"]
           if item["publication"].startswith("new absent-only configuration unit")]
    )
    candidate_destinations = {item["destination"] for item in candidate_entries}
    assert len(candidate_entries) == len(candidate_destinations) == 25
    assert candidate_destinations <= set(baseline_fingerprints)
    return {
        "schema": inventory.INVENTORY_SCHEMA,
        "source_head": inventory.SOURCE_HEAD,
        "boot_id": "11111111-2222-3333-4444-555555555555",
        "captured_utc": NOW.isoformat(),
        "mount": {
            "source": {"command": "/usr/bin/findmnt -n -o SOURCE --target /mnt/d",
                       "exit_code": 0, "stdout": "D:\n", "stderr": ""},
            "filesystem_options": {
                "command": "/usr/bin/findmnt -n -o FSTYPE,OPTIONS --target /mnt/d",
                "exit_code": 0, "stdout": "9p ro,relatime\n", "stderr": ""},
        },
        "source_identity": {
            "repo_head": EXPECTED_REPO_HEAD,
            "implementation_source_commit": inventory.IMPLEMENTATION_HEAD,
            "runtime_capture_sha256": EXPECTED_CAPTURE_SHA256,
            "applier_sha256": EXPECTED_APPLIER_SHA256,
            "validator_sha256": WORKTREE_VALIDATOR_SHA256,
            "bundle_manifest_sha256": inventory.CANDIDATE_BUNDLE_SHA256,
            "installation_layout_sha256": inventory.CANDIDATE_LAYOUT_SHA256,
            "runtime_source_head": inventory.SOURCE_HEAD,
        },
        "readiness": {
            "distro": "Ubuntu-24.04",
            "kernel": "6.6.114.1-microsoft-standard-WSL2",
            "systemd": "running",
            "systemd_jobs": "",
            "shutdown_scheduled": False,
            "systemd_version": "255 (255.4-1ubuntu8)",
            "boot_id": "11111111-2222-3333-4444-555555555555",
            "pid1": {"comm": "systemd", "start_ticks": 1,
                     "net_ns_inode": 2, "mount_ns_inode": 3,
                     "uid": [0, 0, 0, 0], "gid": [0, 0, 0, 0]},
            "accounts": {"vst-runner": {"uid": 997, "gid": 988},
                         "vst-worker": {"uid": 999, "gid": 989}},
            "units": {name: ["loaded", "inactive", "dead", "0"]
                      for name in inventory.UNITS},
            "runtime_selector": inventory.RUNTIME_PATH,
            "store_present": False,
            "preflight_present": False,
            "attestation_present": False,
            "container_sockets": {path: False for path in inventory.CONTAINER_SOCKETS},
            "candidate_identity_collision": False,
            "installed_bootstrap_identity": {
                "request_id": inventory.BASELINE_REQUEST_ID,
                "run_id": inventory.BASELINE_RUN_ID,
            },
        },
        "configuration_files": {
            destination: {**fingerprint, "state": "PRESENT", "kind": "regular",
                          "mode": f"{fingerprint['mode']:04o}"}
            for destination, fingerprint in copy.deepcopy(baseline_fingerprints).items()
            if destination in candidate_destinations
        },
        "runtime_selector": {"state": "PRESENT", "kind": "symlink",
                             "link_target": inventory.RUNTIME_PATH},
    }


def _validate(value: dict[str, object]):
    return inventory.validate_inventory(
        value, expected_repo_head=EXPECTED_REPO_HEAD,
        expected_capture_sha256=EXPECTED_CAPTURE_SHA256, now=NOW)


def _use_candidate_config_blobs(monkeypatch, overrides: dict[str, bytes] | None = None) -> None:
    read_committed = inventory._git_blob
    candidate_overrides = overrides or {}

    def read_candidate(commit: str, relative_path: str) -> bytes:
        prefix = "docs/sdlc/runtime-config/"
        if commit == EXPECTED_REPO_HEAD and relative_path.startswith(prefix):
            name = relative_path.removeprefix(prefix)
            if name in candidate_overrides:
                return candidate_overrides[name]
            return (inventory.REPO / relative_path).read_bytes()
        return read_committed(commit, relative_path)

    monkeypatch.setattr(inventory, "_git_blob", read_candidate)


def test_candidate_config_identity_and_bundle_pins_match_exact_inputs(monkeypatch) -> None:
    consumed_identity = {
        "run_id": "s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910",
        "request_id": "e520e04f58ad5e6a431a3a20b0efb87c",
        "nonce": "0aac24fec9a2a5c53c5e9da21cbb4a42",
    }
    candidate_identity = {
        "run_id": collector.RUN_ID,
        "request_id": collector.REQUEST_ID,
        "nonce": collector.NONCE,
    }
    assert candidate_identity == {
        "run_id": inventory.RUN_ID,
        "request_id": inventory.REQUEST_ID,
        "nonce": inventory.NONCE,
    }
    assert len(set(candidate_identity.values())) == len(candidate_identity)
    assert set(candidate_identity.values()).isdisjoint(consumed_identity.values())

    bundle_dir = inventory.REPO / "docs/sdlc/runtime-config"
    identity_inputs = {
        "bootstrap-request.json", "network-profile.json", "run-binding.json",
        "supervisor-service.json",
    }
    bundle_raw = (bundle_dir / "bundle-manifest.json").read_bytes()
    bundle = json.loads(bundle_raw)
    member_records = {item["path"]: item for item in bundle["files"]}
    assert member_records
    assert identity_inputs <= set(member_records)
    assert "probe-request.json" not in member_records
    assert not any("probe-request" in path for path in member_records)

    input_values = {
        name: json.loads((bundle_dir / name).read_bytes()) for name in identity_inputs
    }
    assert input_values["bootstrap-request.json"]["request_id"] == collector.REQUEST_ID
    assert input_values["bootstrap-request.json"]["run_id"] == collector.RUN_ID
    assert input_values["network-profile.json"]["environment_id"] == (
        f"Ubuntu-24.04:S2:{collector.RUN_ID}")
    assert input_values["run-binding.json"]["run_id"] == collector.RUN_ID
    assert input_values["run-binding.json"]["probe_nonce"] == collector.NONCE
    assert input_values["supervisor-service.json"]["run_id"] == collector.RUN_ID
    assert input_values["supervisor-service.json"]["probe_nonce"] == collector.NONCE
    assert not any("probe_request" in key or "probe-request" in key
                   for key in input_values["supervisor-service.json"])

    for relative in identity_inputs:
        raw = (bundle_dir / relative).read_bytes()
        assert len(raw) == member_records[relative]["size"], relative
        assert hashlib.sha256(raw).hexdigest() == member_records[relative]["sha256"], relative

    layout_raw = (bundle_dir / "installation-layout.json").read_bytes()
    bundle_digest = hashlib.sha256(bundle_raw).hexdigest()
    layout_digest = hashlib.sha256(layout_raw).hexdigest()
    assert {
        collector.BUNDLE_SHA,
        inventory.CANDIDATE_BUNDLE_SHA256,
        applier.BUNDLE_MANIFEST_SHA256,
    } == {bundle_digest}
    assert {
        collector.LAYOUT_SHA,
        inventory.CANDIDATE_LAYOUT_SHA256,
        applier.INSTALLATION_LAYOUT_SHA256,
    } == {layout_digest}
    _use_candidate_config_blobs(monkeypatch)
    inventory._validate_candidate_identity(EXPECTED_REPO_HEAD)


@pytest.mark.parametrize("mismatch", ["member", "identity", "consumed_reuse"])
def test_candidate_identity_rejects_member_or_identity_mismatch(monkeypatch, mismatch) -> None:
    _use_candidate_config_blobs(monkeypatch)
    if mismatch == "member":
        original_git_blob = inventory._git_blob

        def tampered_member(commit: str, relative_path: str) -> bytes:
            if relative_path.endswith("/bootstrap-request.json"):
                return original_git_blob(commit, relative_path) + b" "
            return original_git_blob(commit, relative_path)

        monkeypatch.setattr(inventory, "_git_blob", tampered_member)
        expected_error = "candidate config differs from its bundle member"
    elif mismatch == "identity":
        monkeypatch.setattr(inventory, "REQUEST_ID", "f" * 32)
        expected_error = "candidate run/request/nonce identities are not cross-bound"
    else:
        monkeypatch.setattr(inventory, "RUN_ID", inventory.CONSUMED_RUN_ID)
        expected_error = "reuses a consumed identity"

    with pytest.raises(inventory.InventoryError, match=expected_error):
        inventory._validate_candidate_identity(EXPECTED_REPO_HEAD)


@pytest.mark.parametrize(
    ("constant_name", "tuple_index"),
    [("REQUEST_ID", 0), ("RUN_ID", 1), ("NONCE", 2)],
)
@pytest.mark.parametrize("consumed_index", range(len(EXPECTED_CONSUMED_IDENTITIES)))
def test_candidate_identity_rejects_each_consumed_tuple_component(
        monkeypatch, constant_name, tuple_index, consumed_index) -> None:
    consumed_tuple = EXPECTED_CONSUMED_IDENTITIES[consumed_index]
    monkeypatch.setattr(inventory, constant_name, consumed_tuple[tuple_index])

    with pytest.raises(inventory.InventoryError, match="reuses a consumed identity"):
        inventory._validate_candidate_identity(EXPECTED_REPO_HEAD)


def test_complete_inventory_accepts_exact_read_only_nine_p_mount(valid_inventory) -> None:
    result = _validate(valid_inventory)

    assert result["configuration_destination_count"] == 25
    assert result["mount_fstype"] == "9p"
    assert result["mount_source"] == "D:"
    assert result["mount_read_only"] is True
    assert result["runtime_selector"] == inventory.RUNTIME_PATH


@pytest.mark.parametrize(("source", "filesystem_options"), [
    ("D:\n", "9p\n"),
    ("D:\n", "9p rw,relatime\n"),
    ("D: E:\n", "9p ro,relatime\n"),
    ("E:\n", "9p ro,relatime\n"),
])
def test_inventory_rejects_malformed_or_untrusted_mount(
        valid_inventory, source, filesystem_options) -> None:
    valid_inventory["mount"]["source"]["stdout"] = source
    valid_inventory["mount"]["filesystem_options"]["stdout"] = filesystem_options

    with pytest.raises(inventory.InventoryError, match="mount observation|read-only 9p"):
        _validate(valid_inventory)


@pytest.mark.parametrize("missing", [
    "pid1", "pid1_uid", "pid1_gid", "runner", "worker", "systemd_version",
])
def test_inventory_rejects_missing_or_malformed_systemd_or_worker_identity(
        valid_inventory, missing) -> None:
    readiness = valid_inventory["readiness"]
    if missing == "pid1":
        del readiness["pid1"]
    elif missing == "pid1_uid":
        readiness["pid1"]["uid"] = [False, False, False, False]
    elif missing == "pid1_gid":
        readiness["pid1"]["gid"] = [False, False, False, False]
    elif missing == "runner":
        del readiness["accounts"]["vst-runner"]
    elif missing == "worker":
        del readiness["accounts"]["vst-worker"]
    else:
        del readiness["systemd_version"]

    with pytest.raises(inventory.InventoryError):
        _validate(valid_inventory)


@pytest.mark.parametrize("change", ["missing", "mismatch"])
def test_inventory_requires_top_level_boot_id_to_match_readiness(valid_inventory, change) -> None:
    if change == "missing":
        del valid_inventory["boot_id"]
    else:
        valid_inventory["boot_id"] = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    with pytest.raises(inventory.InventoryError):
        _validate(valid_inventory)


@pytest.mark.parametrize("change", ["missing", "wrong_kind", "extra_key"])
def test_inventory_rejects_incomplete_or_noncanonical_runtime_selector(
        valid_inventory, change) -> None:
    selector = valid_inventory["runtime_selector"]
    if change == "missing":
        del selector["kind"]
    elif change == "wrong_kind":
        selector["kind"] = "regular"
    else:
        selector["resolved_target"] = inventory.RUNTIME_PATH

    with pytest.raises(inventory.InventoryError, match="exact pinned candidate"):
        _validate(valid_inventory)


@pytest.mark.parametrize("change", ["missing", "extra", "tampered"])
def test_inventory_requires_exact_25_candidate_destinations(valid_inventory, change) -> None:
    files = valid_inventory["configuration_files"]
    destination = next(iter(files))
    if change == "missing":
        del files[destination]
    elif change == "extra":
        files["/etc/vst-runner/unexpected.conf"] = copy.deepcopy(files[destination])
    else:
        files[destination]["sha256"] = "0" * 64

    with pytest.raises(inventory.InventoryError, match="exactly all 25 configured destinations|differs from consumed-run baseline"):
        _validate(valid_inventory)


@pytest.mark.parametrize("mode_value", ["integer", "noncanonical_unpadded", "noncanonical_prefix"])
def test_inventory_rejects_noncanonical_octal_file_mode(valid_inventory, mode_value) -> None:
    destination = next(iter(valid_inventory["configuration_files"]))
    mode = valid_inventory["configuration_files"][destination]["mode"]
    if mode_value == "integer":
        valid_inventory["configuration_files"][destination]["mode"] = int(mode, 8)
    elif mode_value == "noncanonical_unpadded":
        valid_inventory["configuration_files"][destination]["mode"] = mode.lstrip("0")
    else:
        valid_inventory["configuration_files"][destination]["mode"] = "0o" + mode

    with pytest.raises(inventory.InventoryError):
        _validate(valid_inventory)


def test_inventory_rejects_stale_capture(valid_inventory) -> None:
    valid_inventory["captured_utc"] = "2026-10-30T11:54:59+00:00"

    with pytest.raises(inventory.InventoryError, match="five-minute freshness"):
        _validate(valid_inventory)


@pytest.mark.parametrize("mismatch", [
    "collision", "runtime_selector", "bootstrap_identity", "validator_sha256", "applier_sha256",
])
def test_inventory_rejects_candidate_or_installed_identity_mismatch(valid_inventory, mismatch) -> None:
    readiness = valid_inventory["readiness"]
    if mismatch == "collision":
        readiness["candidate_identity_collision"] = True
    elif mismatch == "runtime_selector":
        valid_inventory["runtime_selector"]["link_target"] = "/opt/vst-runtime-unpinned"
    elif mismatch == "validator_sha256":
        valid_inventory["source_identity"]["validator_sha256"] = "0" * 64
    elif mismatch == "applier_sha256":
        valid_inventory["source_identity"]["applier_sha256"] = "0" * 64
    else:
        readiness["installed_bootstrap_identity"]["run_id"] = "another-run"

    with pytest.raises(inventory.InventoryError):
        _validate(valid_inventory)


def test_pinned_baseline_rejects_mismatched_consumed_identity(monkeypatch) -> None:
    original_git_blob = inventory._git_blob

    def mismatched_bootstrap(commit: str, relative_path: str) -> bytes:
        raw = original_git_blob(commit, relative_path)
        if relative_path == "docs/sdlc/runtime-config/bootstrap-request.json":
            bootstrap = json.loads(raw)
            bootstrap["request_id"] = "f" * 32
            return json.dumps(bootstrap).encode("utf-8")
        return raw

    monkeypatch.setattr(inventory, "_git_blob", mismatched_bootstrap)

    with pytest.raises(inventory.InventoryError, match="baseline identity is inconsistent"):
        _load_pinned_baseline_fingerprints()


def test_apply_payload_preserves_validated_canonical_octal_mode(
        valid_inventory, tmp_path, monkeypatch) -> None:
    _validate(valid_inventory)
    committed_git_blob = applier._git_blob

    def candidate_bundle_blob(commit: str, relative_path: str) -> bytes:
        if relative_path.startswith("docs/sdlc/runtime-config/"):
            return (inventory.REPO / relative_path).read_bytes()
        return committed_git_blob(commit, relative_path)

    monkeypatch.setattr(applier, "_git_blob", candidate_bundle_blob)
    valid_inventory["captured_utc"] = datetime.now(timezone.utc).isoformat()
    raw_inventory = json.dumps(valid_inventory, sort_keys=True, separators=(",", ":")).encode()
    inventory_path = tmp_path / "runtime-inventory.json"
    inventory_path.write_bytes(raw_inventory)
    if not COMMITTED_VALIDATOR_MATCHES_WORKTREE:
        # Before commit, exercise payload serialization with the candidate validator already
        # covered by the unit tests, without claiming its bytes exist in Git HEAD.
        monkeypatch.setattr(applier, "_load_committed_inventory_validator",
                            lambda _repo_head: inventory.validate_inventory)

    payload_bytes = applier.build_payload(
        inventory_path, hashlib.sha256(raw_inventory).hexdigest(), EXPECTED_REPO_HEAD,
        expected_repo_head=EXPECTED_REPO_HEAD,
        expected_capture_sha256=EXPECTED_CAPTURE_SHA256)
    payload = json.loads(payload_bytes)
    payload_inventory = json.loads(base64.b64decode(payload["inventory_b64"]))
    assert payload["expected_boot_id"] == payload_inventory["boot_id"]
    assert payload_inventory == valid_inventory
    source_manifest = json.loads(
        (inventory.REPO / "docs/sdlc/runtime-config/deployment-source-manifest.json").read_bytes())
    snapshot = payload["task_source_snapshot"]
    archived_source = base64.b64decode(snapshot["archive_b64"], validate=True)
    assert snapshot["head"] == source_manifest["task_source_head"] == applier.RUNTIME_SOURCE_HEAD
    assert snapshot["format"] == source_manifest["task_source_archive_format"]
    assert snapshot["size"] == len(archived_source) == source_manifest["task_source_archive_bytes"]
    assert snapshot["sha256"] == hashlib.sha256(archived_source).hexdigest()
    assert snapshot["sha256"] == source_manifest["task_source_archive_sha256"]
    assert payload["deployment_source_manifest_sha256"] == hashlib.sha256(
        base64.b64decode(payload["deployment_source_manifest_b64"], validate=True)).hexdigest()

    monkeypatch.setattr(applier, "_build_task_source_archive", lambda _head: b"wrong pinned archive")
    with pytest.raises(ValueError, match="task-source archive differs"):
        applier.build_payload(
            inventory_path, hashlib.sha256(raw_inventory).hexdigest(), EXPECTED_REPO_HEAD,
            expected_repo_head=EXPECTED_REPO_HEAD,
            expected_capture_sha256=EXPECTED_CAPTURE_SHA256)

    payload_files = payload["files"]
    if isinstance(payload_files, list):
        payload_files = {item["destination"]: item for item in payload_files}
    for destination, observed in payload_inventory["configuration_files"].items():
        parsed_mode = int(observed["mode"], 8)
        assert parsed_mode == payload_files[destination]["expected_current"]["mode"]


def test_apply_payload_rejects_validator_blob_that_differs_from_worktree(
        valid_inventory, tmp_path, monkeypatch) -> None:
    valid_inventory["captured_utc"] = datetime.now(timezone.utc).isoformat()
    raw_inventory = json.dumps(valid_inventory, sort_keys=True, separators=(",", ":")).encode()
    inventory_path = tmp_path / "runtime-inventory.json"
    inventory_path.write_bytes(raw_inventory)
    original_git_blob = applier._git_blob

    def mismatched_validator_blob(commit: str, relative_path: str) -> bytes:
        if relative_path == VALIDATOR_PATH:
            return b"# not the committed validator source"
        return original_git_blob(commit, relative_path)

    monkeypatch.setattr(applier, "_git_blob", mismatched_validator_blob)

    with pytest.raises(ValueError):
        applier.build_payload(
            inventory_path, hashlib.sha256(raw_inventory).hexdigest(), EXPECTED_REPO_HEAD,
            expected_repo_head=EXPECTED_REPO_HEAD,
            expected_capture_sha256=EXPECTED_CAPTURE_SHA256)


def _remote_snapshot_functions():
    tree = ast.parse(applier._REMOTE)
    names = {"read_task_snapshot", "snapshot_matches", "install_task_snapshot"}
    definitions = [node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in definitions} == names
    namespace = {
        "hashlib": hashlib,
        "io": io,
        "os": os,
        "shutil": shutil,
        "stat": stat,
        "tarfile": tarfile,
        "tempfile": __import__("tempfile"),
    }
    code = compile(ast.Module(body=definitions, type_ignores=[]), "<remote-task-snapshot>", "exec")
    exec(code, namespace)
    return namespace


def _install_snapshot_with_diagnostics(functions, target, expected, observed):
    try:
        return functions["install_task_snapshot"](str(target), expected)
    except SystemExit as exc:
        if "staged task-source snapshot failed" not in str(exc):
            raise
        expected_metadata = {
            path: {key: value for key, value in entry.items() if key != "data"}
            for path, entry in expected.items()
        }
        pytest.fail(
            f"{exc}; expected task-source metadata={expected_metadata}; "
            f"observed lstat metadata={observed}"
        )


def _task_snapshot_tar(entries):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:") as archive:
        for name, kind, mode, data, linkname in entries:
            member = tarfile.TarInfo(name)
            member.mode = mode
            member.uid = 0
            member.gid = 0
            member.mtime = 0
            if kind == "directory":
                member.type = tarfile.DIRTYPE
                member.size = 0
                archive.addfile(member)
            elif kind == "file":
                member.type = tarfile.REGTYPE
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            else:
                member.type = {
                    "symlink": tarfile.SYMTYPE,
                    "hardlink": tarfile.LNKTYPE,
                    "fifo": tarfile.FIFOTYPE,
                }[kind]
                member.linkname = linkname
                member.size = 0
                archive.addfile(member)
    return raw.getvalue()


def _valid_task_snapshot_tar():
    return _task_snapshot_tar([
        ("task-source", "directory", 0o775, b"", ""),
        ("task-source/tests", "directory", 0o775, b"", ""),
        ("task-source/tests/test_example.py", "file", 0o664, b"value = 1\n", ""),
    ])


@pytest.mark.parametrize(
    ("entries", "error"),
    [
        ([("task-source", "directory", 0o775, b"", ""),
          ("task-source/../escape", "file", 0o664, b"x", "")],
         "path escapes"),
        ([("task-source", "directory", 0o775, b"", ""),
          ("task-source/a", "file", 0o664, b"x", ""),
          ("task-source/a", "file", 0o664, b"x", "")],
         "duplicate path"),
        ([("task-source", "directory", 0o775, b"", ""),
          ("task-source/link", "symlink", 0o777, b"", "../../etc/passwd")],
         "link or special file"),
        ([("task-source", "directory", 0o775, b"", ""),
          ("task-source/link", "hardlink", 0o644, b"", "task-source/a")],
         "link or special file"),
        ([("task-source", "directory", 0o775, b"", ""),
          ("task-source/pipe", "fifo", 0o644, b"", "")],
         "link or special file"),
        ([("task-source", "directory", 0o775, b"", ""),
          ("task-source/large", "file", 0o664, b"x" * (8 * 1024 * 1024 + 1), "")],
         "file metadata is unsafe"),
    ],
    ids=["traversal", "duplicate", "symlink", "hardlink", "special", "member-bomb"],
)
def test_remote_task_snapshot_parser_rejects_unsafe_tar_members(entries, error) -> None:
    functions = _remote_snapshot_functions()
    with pytest.raises(SystemExit, match=error):
        functions["read_task_snapshot"](_task_snapshot_tar(entries))


def _emulate_root_owned_temp_tree(
        monkeypatch, root: Path, observed: dict[str, dict[str, object]] | None = None
) -> tuple[list[tuple[str, int, int]], list[tuple[str, int, int]]]:
    root = root.resolve()
    original_lstat = os.lstat
    original_open = os.open
    original_rename = os.rename
    original_close = os.close
    chown_calls: list[tuple[str, int, int]] = []
    fchown_calls: list[tuple[str, int, int]] = []
    owner_map: dict[str, tuple[int, int]] = {}
    opened_paths: dict[int, str] = {}

    def normalized_path(path) -> str:
        return os.path.normcase(os.path.abspath(os.fsdecode(path)))

    normalized_root = normalized_path(root)
    for current, directories, files in os.walk(root):
        owner_map[normalized_path(current)] = (0, 0)
        for name in directories + files:
            owner_map[normalized_path(os.path.join(current, name))] = (0, 0)

    def in_tree(path) -> bool:
        try:
            return os.path.commonpath((normalized_root, normalized_path(path))) == normalized_root
        except (OSError, RuntimeError, ValueError):
            return False

    def open_with_path_tracking(path, flags, mode=0o777, *args, **kwargs):
        fd = original_open(path, flags, mode, *args, **kwargs)
        if in_tree(path):
            opened_paths[fd] = normalized_path(path)
        return fd

    def chown_with_owner_tracking(path, uid, gid):
        if in_tree(path):
            owner_map[normalized_path(path)] = (uid, gid)
        chown_calls.append((str(path), uid, gid))

    def fchown_with_owner_tracking(fd, uid, gid):
        path = opened_paths.get(fd)
        if path is not None:
            owner_map[path] = (uid, gid)
        fchown_calls.append((path or str(fd), uid, gid))

    def rename_with_tracking(source, destination, *args, **kwargs):
        result = original_rename(source, destination, *args, **kwargs)
        source_path = normalized_path(source)
        destination_path = normalized_path(destination)
        relocated_owners = {}
        for path, owner in list(owner_map.items()):
            try:
                if os.path.commonpath((source_path, path)) == source_path:
                    relative = os.path.relpath(path, source_path)
                    relocated_owners[normalized_path(os.path.join(destination_path, relative))] = owner
                    owner_map.pop(path, None)
            except (OSError, RuntimeError, ValueError):
                continue
        owner_map.update(relocated_owners)
        if os.name == "nt":
            old_paths = []
            relocated_modes = {}
            for path, mode in list(posix_modes.items()):
                try:
                    if os.path.commonpath((source_path, path)) == source_path:
                        relative = os.path.relpath(path, source_path)
                        old_paths.append(path)
                        relocated_modes[normalized_path(os.path.join(destination_path, relative))] = mode
                except (OSError, RuntimeError, ValueError):
                    continue
            for old_path in old_paths:
                del posix_modes[old_path]
            posix_modes.update(relocated_modes)
        return result

    def close_with_path_tracking(fd):
        opened_paths.pop(fd, None)
        return original_close(fd)

    if os.name == "nt":
        original_chmod = os.chmod
        original_fchmod = getattr(os, "fchmod", None)
        original_fsync = os.fsync
        original_rmtree = shutil.rmtree
        posix_modes: dict[str, int] = {}
        directory_fds: set[int] = set()
        next_directory_fd = [-1]

        def chmod_with_posix_mode(path, mode, *args, **kwargs):
            if in_tree(path):
                posix_modes[normalized_path(path)] = stat.S_IMODE(mode)
            return original_chmod(path, mode, *args, **kwargs)

        def open_with_path_tracking(path, flags, mode=0o777, *args, **kwargs):
            if in_tree(path):
                try:
                    path_info = original_lstat(path)
                except FileNotFoundError:
                    path_info = None
                if path_info is not None and stat.S_ISDIR(path_info.st_mode):
                    fd = next_directory_fd[0]
                    next_directory_fd[0] -= 1
                    opened_paths[fd] = normalized_path(path)
                    directory_fds.add(fd)
                    return fd
                flags |= getattr(os, "O_BINARY", 0)
            fd = original_open(path, flags, mode, *args, **kwargs)
            if in_tree(path):
                opened_paths[fd] = normalized_path(path)
            return fd

        def fchmod_with_posix_mode(fd, mode):
            path = opened_paths.get(fd)
            if path is not None:
                posix_modes[path] = stat.S_IMODE(mode)
            if fd not in directory_fds and original_fchmod is not None:
                return original_fchmod(fd, mode)
            return None

        def fsync_with_directory_fd_shim(fd):
            if fd not in directory_fds:
                return original_fsync(fd)
            return None

        def close_with_directory_fd_shim(fd):
            if fd in directory_fds:
                directory_fds.remove(fd)
                opened_paths.pop(fd, None)
                return None
            return close_with_path_tracking(fd)

        def rmtree_with_posix_unlink_semantics(path, *args, **kwargs):
            for current, directories, files in os.walk(path, topdown=False):
                for name in files:
                    try:
                        original_chmod(os.path.join(current, name), 0o600)
                    except FileNotFoundError:
                        pass
                for name in directories:
                    try:
                        original_chmod(os.path.join(current, name), 0o700)
                    except FileNotFoundError:
                        pass
                try:
                    original_chmod(current, 0o700)
                except FileNotFoundError:
                    pass
            return original_rmtree(path, *args, **kwargs)

    def lstat_with_root_owner(path, *args, **kwargs):
        info = original_lstat(path, *args, **kwargs)
        if os.name == "nt":
            path_in_tree = in_tree(path)
        else:
            try:
                absolute_path = os.path.abspath(os.fsdecode(path))
                path_in_tree = os.path.commonpath((str(root), absolute_path)) == str(root)
            except (OSError, RuntimeError, ValueError):
                path_in_tree = False
        if not path_in_tree:
            return info
        uid, gid = owner_map.get(normalized_path(path), (1000, 1000))
        if os.name == "nt":
            kind = stat.S_IFMT(info.st_mode)
            default_mode = 0o755 if stat.S_ISDIR(info.st_mode) else 0o644
            mode = kind | posix_modes.get(normalized_path(path), default_mode)

            class SyntheticStatResult:
                def __init__(self, source):
                    self._source = source
                    self.st_mode = mode
                    self.st_uid = uid
                    self.st_gid = gid

                def __getattr__(self, name):
                    # Preserve platform fields such as Windows st_file_attributes
                    # and st_reparse_tag for consumers like shutil.rmtree.
                    return getattr(self._source, name)

            result = SyntheticStatResult(info)
            if observed is not None:
                observed[normalized_path(path)] = {
                    "st_mode": result.st_mode,
                    "st_uid": result.st_uid,
                    "st_gid": result.st_gid,
                    "st_nlink": result.st_nlink,
                    "st_size": result.st_size,
                    "st_file_attributes": getattr(result, "st_file_attributes", None),
                    "st_reparse_tag": getattr(result, "st_reparse_tag", None),
                }
            return result
        values = list(info)
        values[4] = uid
        values[5] = gid
        result = os.stat_result(values)
        if observed is not None:
            observed[os.path.abspath(os.fsdecode(path))] = {
                "st_mode": result.st_mode,
                "st_uid": result.st_uid,
                "st_gid": result.st_gid,
                "st_nlink": result.st_nlink,
                "st_size": result.st_size,
            }
        return result

    monkeypatch.setattr(os, "lstat", lstat_with_root_owner)
    if os.name == "nt":
        monkeypatch.setattr(os, "chmod", chmod_with_posix_mode)
        monkeypatch.setattr(os, "open", open_with_path_tracking)
        monkeypatch.setattr(os, "fchmod", fchmod_with_posix_mode, raising=False)
        monkeypatch.setattr(os, "fsync", fsync_with_directory_fd_shim)
        monkeypatch.setattr(os, "close", close_with_directory_fd_shim)
        monkeypatch.setattr(shutil, "rmtree", rmtree_with_posix_unlink_semantics)
    else:
        monkeypatch.setattr(os, "open", open_with_path_tracking)
        monkeypatch.setattr(os, "close", close_with_path_tracking)
    monkeypatch.setattr(os, "chown", chown_with_owner_tracking, raising=False)
    monkeypatch.setattr(os, "fchown", fchown_with_owner_tracking, raising=False)
    monkeypatch.setattr(os, "rename", rename_with_tracking)
    return chown_calls, fchown_calls


def test_remote_task_snapshot_installs_exact_read_only_tree_and_is_idempotent(
        tmp_path, monkeypatch) -> None:
    functions = _remote_snapshot_functions()
    raw = _valid_task_snapshot_tar()
    expected = functions["read_task_snapshot"](raw)
    var_lib = tmp_path / "var" / "lib"
    var_lib.mkdir(parents=True)
    observed: dict[str, dict[str, object]] = {}
    chown_calls, fchown_calls = _emulate_root_owned_temp_tree(monkeypatch, tmp_path, observed)
    target = var_lib / "vst-runner" / "repository"

    assert _install_snapshot_with_diagnostics(functions, target, expected, observed) == "installed"
    assert functions["snapshot_matches"](str(target), expected)
    assert stat.S_IMODE(os.lstat(target).st_mode) == 0o555
    assert stat.S_IMODE(os.lstat(target / "tests").st_mode) == 0o555
    assert stat.S_IMODE(os.lstat(target / "tests" / "test_example.py").st_mode) == 0o444
    assert os.lstat(target).st_uid == 0 and os.lstat(target).st_gid == 0
    assert any(uid == gid == 0 for _path, uid, gid in chown_calls)
    for relative, item in expected.items():
        if item["kind"] == "file":
            assert any(
                Path(path).as_posix().endswith("/" + relative) and uid == gid == 0
                for path, uid, gid in fchown_calls
            )
        elif relative:
            assert any(
                Path(path).as_posix().endswith("/" + relative) and uid == gid == 0
                for path, uid, gid in chown_calls
            )
    assert any(Path(path).name.startswith(".vst-task-source-") and uid == gid == 0
               for path, uid, gid in chown_calls)

    assert functions["install_task_snapshot"](str(target), expected) == "already-exact"


def test_remote_task_snapshot_refuses_nonexact_existing_tree_without_overwrite(
        tmp_path, monkeypatch) -> None:
    functions = _remote_snapshot_functions()
    expected = functions["read_task_snapshot"](_valid_task_snapshot_tar())
    var_lib = tmp_path / "var" / "lib"
    var_lib.mkdir(parents=True)
    observed: dict[str, dict[str, object]] = {}
    _emulate_root_owned_temp_tree(monkeypatch, tmp_path, observed)
    target = var_lib / "vst-runner" / "repository"
    assert _install_snapshot_with_diagnostics(functions, target, expected, observed) == "installed"

    sample = target / "tests" / "test_example.py"
    sample.chmod(0o644)
    sample.write_bytes(b"operator-owned replacement\n")
    sample.chmod(0o444)
    with pytest.raises(SystemExit, match="refusing overwrite"):
        functions["install_task_snapshot"](str(target), expected)
    assert sample.read_bytes() == b"operator-owned replacement\n"


def test_remote_task_snapshot_rejects_unsafe_parent_without_writing(tmp_path, monkeypatch) -> None:
    functions = _remote_snapshot_functions()
    expected = functions["read_task_snapshot"](_valid_task_snapshot_tar())
    parent_parent = tmp_path / "var" / "lib"
    parent_parent.mkdir(parents=True)
    _emulate_root_owned_temp_tree(monkeypatch, tmp_path)
    parent = parent_parent / "vst-runner"
    parent.mkdir()
    os.chown(parent, 0, 0)
    parent.chmod(0o777)
    target = parent / "repository"

    with pytest.raises(SystemExit, match="parent has unexpected owner or mode"):
        functions["install_task_snapshot"](str(target), expected)
    assert not target.exists()
