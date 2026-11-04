from __future__ import annotations

import copy
import ast
import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
WORKTREE_CONTRACTS_SHA256 = hashlib.sha256(
    (inventory.REPO / "tools/vst/contracts.py").read_bytes()).hexdigest()
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
    assert len(candidate_entries) == len(candidate_destinations) == 27
    absent_recovery_guard_destinations = {
        "/etc/systemd/system/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
        "/etc/systemd/system/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    }
    added_destinations = candidate_destinations - set(baseline_fingerprints)
    assert added_destinations == absent_recovery_guard_destinations
    existing_destinations = candidate_destinations - absent_recovery_guard_destinations
    assert existing_destinations <= set(baseline_fingerprints)
    configuration_files = {
        destination: {**fingerprint, "state": "PRESENT", "kind": "regular",
                      "mode": f"{fingerprint['mode']:04o}"}
        for destination, fingerprint in copy.deepcopy(baseline_fingerprints).items()
        if destination in existing_destinations
    }
    configuration_files.update({
        destination: {"state": "ABSENT", "kind": "absent"}
        for destination in absent_recovery_guard_destinations
    })
    assert {
        destination for destination, observed in configuration_files.items()
        if observed["state"] == "ABSENT"
    } == absent_recovery_guard_destinations
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
            "contracts_sha256": collector.CONTRACTS_SHA,
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
        "configuration_files": configuration_files,
        "runtime_selector": {"state": "PRESENT", "kind": "symlink",
                             "link_target": inventory.RUNTIME_PATH},
    }


def test_candidate_inventory_marks_only_the_two_new_recovery_guards_absent(valid_inventory):
    absent_destinations = {
        destination for destination, observed in valid_inventory["configuration_files"].items()
        if observed["state"] == "ABSENT"
    }
    assert absent_destinations == {
        "/etc/systemd/system/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
        "/etc/systemd/system/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    }
    assert len(valid_inventory["configuration_files"]) == 27


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


def _candidate_identity_overrides(mutation: str) -> dict[str, bytes]:
    names = ("task-manifest.json", "assignment-delegation-policy.json",
             "supervisor-service.json")
    bundle_dir = inventory.REPO / "docs/sdlc/runtime-config"
    values = {name: json.loads((bundle_dir / name).read_bytes()) for name in names}
    bundle = json.loads((bundle_dir / "bundle-manifest.json").read_bytes())
    task = values["task-manifest.json"]
    policy = values["assignment-delegation-policy.json"]
    supervisor = values["supervisor-service.json"]

    if mutation == "task-schema":
        values["task-manifest.json"] = []
    elif mutation == "policy-schema":
        values["assignment-delegation-policy.json"] = []
    elif mutation == "supervisor-schema":
        values["supervisor-service.json"] = []
    elif mutation == "task-base-head":
        task["base_head"] = "f" * 40
    elif mutation == "task-scope":
        task["scope"] = ["tests/another-selector.py"]
    elif mutation == "policy-source-head":
        policy["source_head"] = "f" * 40
    elif mutation == "policy-source-binding":
        policy["manifest_sha256"] = "f" * 64
    elif mutation == "allowed-task-digest":
        policy["allowed_assignments"][0]["task_manifest_sha256"] = "f" * 64
    elif mutation == "supervisor-policy-digest":
        supervisor["assignment_policy_sha256"] = "f" * 64
    elif mutation == "bundle-task-source-head":
        bundle["task_source_head"] = "f" * 40
    else:
        raise AssertionError(f"unknown test mutation: {mutation}")

    if mutation not in {"task-schema", "policy-schema", "supervisor-schema"}:
        canonical = lambda obj: hashlib.sha256(json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False).encode("utf-8")).hexdigest()
        task_digest = canonical(task)
        bundle["task_manifest_sha256"] = task_digest
        if mutation != "allowed-task-digest":
            policy["allowed_assignments"][0]["task_manifest_sha256"] = task_digest
        policy_digest = canonical(policy)
        bundle["assignment_policy_sha256"] = policy_digest
        if mutation != "supervisor-policy-digest":
            supervisor["assignment_policy_sha256"] = policy_digest

    records = {item["path"]: item for item in bundle["files"]}
    overrides = {}
    for name in names:
        raw = (json.dumps(values[name], indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        overrides[name] = raw
        records[name]["size"] = len(raw)
        records[name]["sha256"] = hashlib.sha256(raw).hexdigest()
    overrides["bundle-manifest.json"] = (
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return overrides


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
        "supervisor-service.json", "task-manifest.json",
        "assignment-delegation-policy.json",
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
    input_values["deployment-source-manifest.json"] = json.loads(
        (bundle_dir / "deployment-source-manifest.json").read_bytes())
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

    task = input_values["task-manifest.json"]
    policy = input_values["assignment-delegation-policy.json"]
    supervisor = input_values["supervisor-service.json"]
    source = input_values["deployment-source-manifest.json"]
    assert (bundle["source_head"] == bundle["runtime_source_head"]
            == source["runtime_source_head"] == inventory.SOURCE_HEAD)
    assert (bundle["task_source_head"] == source["task_source_head"]
            == task["base_head"] == policy["source_head"] == inventory.TASK_SOURCE_HEAD)
    assert bundle["runtime_source_head"] != bundle["task_source_head"]
    task_digest = inventory.manifest_sha256(task)
    policy_digest = hashlib.sha256(json.dumps(
        policy, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode("utf-8")).hexdigest()
    assert task["scope"] == task["change_scope"]["allowed_paths"]
    assert bundle["task_manifest_sha256"] == task_digest
    assert policy["allowed_assignments"][0]["task_manifest_sha256"] == task_digest
    assert policy["manifest_sha256"] == bundle["source_binding_sha256"]
    assert bundle["assignment_policy_sha256"] == policy_digest
    assert supervisor["assignment_policy_sha256"] == policy_digest
    assert collector.CONTRACTS_SHA == WORKTREE_CONTRACTS_SHA256

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


@pytest.mark.parametrize("mutation", [
    "task-schema", "policy-schema", "supervisor-schema", "task-base-head",
    "task-scope", "policy-source-head", "policy-source-binding",
    "allowed-task-digest", "supervisor-policy-digest", "bundle-task-source-head",
])
def test_candidate_identity_rejects_malformed_schema_or_crossbinding(
        monkeypatch, mutation) -> None:
    overrides = _candidate_identity_overrides(mutation)
    bundle_digest = hashlib.sha256(overrides["bundle-manifest.json"]).hexdigest()
    monkeypatch.setattr(inventory, "CANDIDATE_BUNDLE_SHA256", bundle_digest)
    _use_candidate_config_blobs(monkeypatch, overrides)

    if mutation in {"task-schema", "policy-schema", "supervisor-schema"}:
        expected_error = "candidate config is not a JSON object"
    elif mutation == "bundle-task-source-head":
        expected_error = "candidate bundle schema/state/source is invalid"
    else:
        expected_error = "candidate lacks its exact bounded shallow-Git task-source contract"
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

    assert result["configuration_destination_count"] == 27
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
def test_inventory_requires_exact_27_candidate_destinations(valid_inventory, change) -> None:
    files = valid_inventory["configuration_files"]
    destination = next(iter(files))
    if change == "missing":
        del files[destination]
    elif change == "extra":
        files["/etc/vst-runner/unexpected.conf"] = copy.deepcopy(files[destination])
    else:
        files[destination]["sha256"] = "0" * 64

    with pytest.raises(inventory.InventoryError, match="exactly all 27 configured destinations|differs from consumed-run baseline"):
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
    monkeypatch.setattr(applier, "_validate_deployment_commit", lambda _commit: None)

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
    packed_source = base64.b64decode(snapshot["pack_b64"], validate=True)
    assert snapshot["head"] == source_manifest["task_source_head"] == applier.TASK_SOURCE_HEAD
    assert snapshot["head"] != applier.RUNTIME_SOURCE_HEAD
    assert snapshot["format"] == source_manifest["task_source_git_pack_format"]
    assert snapshot["format"] == "git-pack-shallow-v1"
    assert snapshot["size"] == len(packed_source) == source_manifest["task_source_git_pack_bytes"]
    assert snapshot["sha256"] == hashlib.sha256(packed_source).hexdigest()
    assert snapshot["sha256"] == source_manifest["task_source_git_pack_sha256"]
    assert snapshot["object_count"] == source_manifest["task_source_git_object_count"]
    assert snapshot["shallow_commits"] == source_manifest["task_source_shallow_commits"]
    assert payload["deployment_source_manifest_sha256"] == hashlib.sha256(
        base64.b64decode(payload["deployment_source_manifest_b64"], validate=True)).hexdigest()

    payload_files = payload["files"]
    if isinstance(payload_files, list):
        payload_files = {item["destination"]: item for item in payload_files}
    for destination, observed in payload_inventory["configuration_files"].items():
        if observed["state"] == "ABSENT":
            continue
        assert observed["state"] == "PRESENT" and observed["kind"] == "regular"
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


class _SnapshotContractError(RuntimeError):
    pass


def _task_source_pack_validator():
    source = (inventory.REPO / "tools/qa/runtime_snapshot_transaction.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    definition = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate_pack")
    pin_names = {
        "MAX_PACK_BYTES", "TASK_HEAD", "TASK_TREE", "TASK_OBJECT_COUNT",
        "TASK_PACK_SHA256", "TASK_PACK_BYTES",
    }

    def constant_value(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            return constant_value(node.left) * constant_value(node.right)
        raise AssertionError(f"unsupported pinned constant expression: {ast.dump(node)}")

    pinned_values = {
        target.id: constant_value(node.value)
        for node in tree.body if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in pin_names
    }
    assert set(pinned_values) == pin_names
    namespace = {
        "Any": Any,
        "hashlib": hashlib,
        "SnapshotContractError": _SnapshotContractError,
        **pinned_values,
    }
    code = compile(ast.Module(body=[definition], type_ignores=[]),
                   "<runtime-snapshot-pack-validator>", "exec")
    exec(code, namespace)
    return namespace["validate_pack"]


def _pinned_task_source_pack() -> tuple[dict[str, object], bytes]:
    source_manifest = json.loads((
        inventory.REPO / "docs/sdlc/runtime-config/deployment-source-manifest.json"
    ).read_bytes())
    packed = applier._task_source_pack(source_manifest)
    snapshot = {
        "head": source_manifest["task_source_head"],
        "tree_sha1": source_manifest["task_source_tree_sha1"],
        "format": source_manifest["task_source_git_pack_format"],
        "object_count": source_manifest["task_source_git_object_count"],
        "shallow_commits": source_manifest["task_source_shallow_commits"],
        "sha256": source_manifest["task_source_git_pack_sha256"],
        "size": source_manifest["task_source_git_pack_bytes"],
        "pack_b64": base64.b64encode(packed).decode("ascii"),
    }
    return snapshot, packed


@pytest.fixture(scope="module")
def task_source_pack_validator():
    return _task_source_pack_validator()


@pytest.fixture(scope="module")
def pinned_task_source_pack():
    return _pinned_task_source_pack()


def test_task_source_git_pack_validator_accepts_exact_manifest_pack(
        task_source_pack_validator, pinned_task_source_pack) -> None:
    snapshot, packed = pinned_task_source_pack

    assert task_source_pack_validator(snapshot) == packed


def test_task_source_git_pack_validator_rejects_malformed_base64(
        task_source_pack_validator, pinned_task_source_pack) -> None:
    snapshot, _packed = pinned_task_source_pack
    snapshot = copy.deepcopy(snapshot)
    snapshot["pack_b64"] = "not valid base64!"

    with pytest.raises(_SnapshotContractError, match="pack encoding is malformed"):
        task_source_pack_validator(snapshot)


def test_task_source_git_pack_validator_rejects_wrong_identity_metadata(
        task_source_pack_validator, pinned_task_source_pack) -> None:
    snapshot, _packed = pinned_task_source_pack
    snapshot = copy.deepcopy(snapshot)
    snapshot["tree_sha1"] = "f" * 40

    with pytest.raises(_SnapshotContractError,
                       match="identity differs from the fixed contract"):
        task_source_pack_validator(snapshot)


def test_task_source_git_pack_validator_rejects_tampered_bytes(
        task_source_pack_validator, pinned_task_source_pack) -> None:
    snapshot, packed = pinned_task_source_pack
    snapshot = copy.deepcopy(snapshot)
    tampered = packed[:-1] + bytes((packed[-1] ^ 1,))
    snapshot["pack_b64"] = base64.b64encode(tampered).decode("ascii")

    with pytest.raises(_SnapshotContractError,
                       match="pack bytes differ from the fixed contract"):
        task_source_pack_validator(snapshot)
