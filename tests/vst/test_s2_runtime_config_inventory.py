from __future__ import annotations

import copy
import base64
import hashlib
import json
from datetime import datetime, timezone

import pytest

from tools.qa import verify_s2_runtime_config_inventory as inventory
from tools.qa import apply_s2_runtime_configuration as applier


_load_pinned_baseline_fingerprints = inventory._previous_installed_fingerprints
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
EXPECTED_REPO_HEAD = "1b5dd9d7a639b629465ac6fcf29e300ba80c18ca"
EXPECTED_HELPER_SHA256 = "0f3b7b6fe11798ebc806a55bd4d6f687e7974b6f4394b2065e15defab8255083"


@pytest.fixture(scope="module")
def baseline_fingerprints() -> dict[str, dict[str, object]]:
    fingerprints = inventory._previous_installed_fingerprints()
    assert len(fingerprints) == 26
    return fingerprints


@pytest.fixture(autouse=True)
def use_pinned_baseline(monkeypatch, baseline_fingerprints) -> None:
    monkeypatch.setattr(inventory, "_previous_installed_fingerprints",
                        lambda: baseline_fingerprints)


@pytest.fixture
def valid_inventory(baseline_fingerprints) -> dict[str, object]:
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
            "helper_sha256": EXPECTED_HELPER_SHA256,
            "applier_sha256": "ac512db996eff8ca8572a1bcf14e9a14081cb77b621bff7a7369a10df8bcf52d",
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
        },
        "runtime_selector": {"state": "PRESENT", "kind": "symlink",
                             "link_target": inventory.RUNTIME_PATH},
    }


def _validate(value: dict[str, object]):
    return inventory.validate_inventory(
        value, expected_repo_head=EXPECTED_REPO_HEAD,
        expected_helper_sha256=EXPECTED_HELPER_SHA256, now=NOW)


def test_complete_inventory_accepts_exact_read_only_nine_p_mount(valid_inventory) -> None:
    result = _validate(valid_inventory)

    assert result["configuration_destination_count"] == 26
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
def test_inventory_requires_exact_26_baseline_fingerprints(valid_inventory, change) -> None:
    files = valid_inventory["configuration_files"]
    destination = next(iter(files))
    if change == "missing":
        del files[destination]
    elif change == "extra":
        files["/etc/vst-runner/unexpected.conf"] = copy.deepcopy(files[destination])
    else:
        files[destination]["sha256"] = "0" * 64

    with pytest.raises(inventory.InventoryError, match="exactly all 26|differs from consumed-run baseline"):
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


@pytest.mark.parametrize("mismatch", ["collision", "runtime_selector", "bootstrap_identity"])
def test_inventory_rejects_candidate_or_installed_identity_mismatch(valid_inventory, mismatch) -> None:
    readiness = valid_inventory["readiness"]
    if mismatch == "collision":
        readiness["candidate_identity_collision"] = True
    elif mismatch == "runtime_selector":
        valid_inventory["runtime_selector"]["link_target"] = "/opt/vst-runtime-unpinned"
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
    valid_inventory["captured_utc"] = datetime.now(timezone.utc).isoformat()
    raw_inventory = json.dumps(valid_inventory, sort_keys=True, separators=(",", ":")).encode()
    inventory_path = tmp_path / "runtime-inventory.json"
    inventory_path.write_bytes(raw_inventory)
    original_git_blob = applier._git_blob

    def committed_validator_from_worktree(commit: str, relative_path: str) -> bytes:
        if relative_path == "tools/qa/verify_s2_runtime_config_inventory.py":
            return inventory.Path(inventory.__file__).read_bytes()
        return original_git_blob(commit, relative_path)

    monkeypatch.setattr(applier, "_git_blob", committed_validator_from_worktree)

    payload_bytes = applier.build_payload(
        inventory_path, hashlib.sha256(raw_inventory).hexdigest(), EXPECTED_REPO_HEAD,
        expected_repo_head=EXPECTED_REPO_HEAD,
        expected_helper_sha256=EXPECTED_HELPER_SHA256)
    payload = json.loads(payload_bytes)
    payload_inventory = json.loads(base64.b64decode(payload["inventory_b64"]))
    assert payload["expected_boot_id"] == payload_inventory["boot_id"]
    assert payload_inventory == valid_inventory

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
        if relative_path == "tools/qa/verify_s2_runtime_config_inventory.py":
            return b"# not the committed validator source"
        return original_git_blob(commit, relative_path)

    monkeypatch.setattr(applier, "_git_blob", mismatched_validator_blob)

    with pytest.raises(ValueError):
        applier.build_payload(
            inventory_path, hashlib.sha256(raw_inventory).hexdigest(), EXPECTED_REPO_HEAD,
            expected_repo_head=EXPECTED_REPO_HEAD,
            expected_helper_sha256=EXPECTED_HELPER_SHA256)
