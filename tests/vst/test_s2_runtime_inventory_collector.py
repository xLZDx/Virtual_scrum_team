from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from datetime import datetime

import pytest

from tools.qa import collect_s2_runtime_config_inventory as collector
from tools.qa import verify_s2_runtime_config_inventory as inventory_validator


@pytest.fixture
def readiness() -> dict[str, object]:
    return {"distro": "Ubuntu-24.04", "systemd": "running"}


@pytest.fixture
def exact_units() -> dict[str, list[str]]:
    return {name: ["loaded", "inactive", "dead", "0"] for name in collector.UNITS}


def _assembly_state() -> dict[str, object]:
    return {
        "store_present": False,
        "preflight_present": False,
        "attestation_present": False,
        "container_sockets": {path: False for path in collector.CONTAINER_SOCKETS},
        "installed_bootstrap_identity": {
            "request_id": "212a23e66ee94a7d87355b11e07e34fe",
            "run_id": "s2-runtime-20261030-334296bd0779488d837a27e283b50b6a",
        },
        "candidate_identity_collision": False,
    }


def _complete_readiness(readiness, units, selector):
    return collector.complete_readiness(readiness, units, selector, **_assembly_state())


@pytest.fixture(scope="module")
def existing_valid_inventory_fixture() -> dict[str, object]:
    fixture_path = Path(__file__).with_name("test_s2_runtime_config_inventory.py")
    spec = importlib.util.spec_from_file_location("s2_runtime_config_inventory_fixture", fixture_path)
    assert spec is not None and spec.loader is not None
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    baseline = fixture_module.baseline_fingerprints.__wrapped__()
    return fixture_module.valid_inventory.__wrapped__(baseline)


def _assemble_existing_fixture(value: dict[str, object]) -> dict[str, object]:
    duplicated = {
        "readiness", "runtime_selector", "store_present", "preflight_present",
        "attestation_present", "container_sockets", "installed_bootstrap_identity",
        "candidate_identity_collision",
    }
    fields = {key: item for key, item in value.items() if key not in duplicated}
    readiness = value["readiness"]
    return collector.assemble_inventory(
        fields, readiness, readiness["units"], value["runtime_selector"],
        store_present=readiness["store_present"],
        preflight_present=readiness["preflight_present"],
        attestation_present=readiness["attestation_present"],
        container_sockets=readiness["container_sockets"],
        installed_bootstrap_identity=readiness["installed_bootstrap_identity"],
        candidate_identity_collision=readiness["candidate_identity_collision"],
    )


def _validate_real_inventory(value: dict[str, object]) -> dict[str, object]:
    source_identity = value["source_identity"]
    captured = datetime.fromisoformat(value["captured_utc"].replace("Z", "+00:00"))
    return inventory_validator.validate_inventory(
        value, expected_repo_head=source_identity["repo_head"],
        expected_helper_sha256=source_identity["helper_sha256"], now=captured)


def test_assemble_inventory_passes_existing_valid_fixture_to_real_validator(
        existing_valid_inventory_fixture) -> None:
    assembled = _assemble_existing_fixture(copy.deepcopy(existing_valid_inventory_fixture))

    result = _validate_real_inventory(assembled)

    assert result["configuration_destination_count"] == 26
    assert assembled["readiness"]["units"] == existing_valid_inventory_fixture["readiness"]["units"]
    assert assembled["readiness"]["runtime_selector"] == assembled["runtime_selector"]["link_target"]
    for key in (
        "store_present", "preflight_present", "attestation_present", "container_sockets",
        "installed_bootstrap_identity", "candidate_identity_collision",
    ):
        assert assembled["readiness"][key] == assembled[key]


@pytest.mark.parametrize("field", [
    "units", "runtime_selector", "store_present", "preflight_present", "attestation_present",
    "container_sockets", "installed_bootstrap_identity", "candidate_identity_collision",
])
@pytest.mark.parametrize("change", ["missing", "contradictory"])
def test_real_validator_rejects_missing_or_contradictory_assembled_readiness_fields(
        existing_valid_inventory_fixture, field, change) -> None:
    assembled = _assemble_existing_fixture(copy.deepcopy(existing_valid_inventory_fixture))
    readiness = assembled["readiness"]
    if change == "missing":
        del readiness[field]
    elif field == "units":
        readiness["units"] = copy.deepcopy(readiness["units"])
        readiness["units"][collector.UNITS[0]] = ["loaded", "active", "dead", "0"]
    elif field == "runtime_selector":
        readiness["runtime_selector"] = "/opt/vst-runtime-unpinned"
    elif field in {"store_present", "preflight_present", "attestation_present"}:
        readiness[field] = True
    elif field == "container_sockets":
        readiness["container_sockets"] = copy.deepcopy(readiness[field])
        readiness["container_sockets"][collector.CONTAINER_SOCKETS[0]] = True
    elif field == "installed_bootstrap_identity":
        readiness[field] = copy.deepcopy(readiness[field])
        readiness[field]["run_id"] = "another-run"
    else:
        readiness[field] = True

    with pytest.raises(inventory_validator.InventoryError):
        _validate_real_inventory(assembled)


def test_complete_readiness_attaches_exact_nine_units_and_observed_symlink_target(
        readiness, exact_units) -> None:
    target = "/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2"
    selector = {"state": "PRESENT", "kind": "symlink", "link_target": target}

    result = _complete_readiness(readiness, exact_units, selector)

    assert set(result["units"]) == set(collector.UNITS)
    assert len(result["units"]) == 9
    assert result["units"] == exact_units
    assert result["runtime_selector"] == target
    assert "units" not in readiness
    assert "runtime_selector" not in readiness


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_complete_readiness_rejects_non_exact_unit_observation_set(
        readiness, exact_units, change) -> None:
    if change == "missing":
        exact_units.pop(collector.UNITS[0])
    else:
        exact_units["unexpected.service"] = ["loaded", "inactive", "dead", "0"]

    with pytest.raises(ValueError, match="exact nine-unit contract"):
        _complete_readiness(
            readiness, exact_units,
            {"state": "PRESENT", "kind": "symlink", "link_target": "/opt/vst-runtime-candidate"})


@pytest.mark.parametrize("selector", [
    {"state": "PRESENT", "kind": "regular", "link_target": "/opt/vst-runtime-candidate"},
    {"state": "ABSENT", "kind": "unknown", "link_target": "/opt/vst-runtime-candidate"},
    {"state": "PRESENT", "kind": "symlink"},
])
def test_complete_readiness_does_not_trust_missing_or_non_symlink_selector(
        readiness, exact_units, selector) -> None:
    result = _complete_readiness(readiness, exact_units, selector)

    assert result["runtime_selector"] == ""
    assert result["runtime_selector"] != "/opt/vst-runtime-candidate"


def test_complete_readiness_rejects_missing_selector_observation(readiness, exact_units) -> None:
    with pytest.raises(ValueError, match="selector observation is missing"):
        _complete_readiness(readiness, exact_units, None)


@pytest.mark.parametrize("result", [
    {"exit_code": 1, "stdout": "value", "stderr": ""},
    {"exit_code": 0, "stdout": "value", "stderr": "unexpected warning"},
])
def test_require_success_rejects_failed_exit_or_unexpected_stderr(result) -> None:
    with pytest.raises(RuntimeError, match="command failed or produced unexpected stderr"):
        collector.require_success(result, "inventory command")


def test_parse_os_release_accepts_observed_ubuntu_2404() -> None:
    assert collector.parse_os_release('ID="ubuntu"\nVERSION_ID="24.04"\n') == "Ubuntu-24.04"


def test_parse_os_release_rejects_other_ubuntu_version() -> None:
    with pytest.raises(RuntimeError, match="not Ubuntu 24.04"):
        collector.parse_os_release('ID="ubuntu"\nVERSION_ID="22.04"\n')


def _systemd_unit_result(stdout: str, *, exit_code: int = 0, stderr: str = ""):
    return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}


def test_parse_unit_observation_accepts_exact_four_properties() -> None:
    result = _systemd_unit_result(
        "LoadState=loaded\nActiveState=inactive\nSubState=dead\nJob=0\n")

    assert collector.parse_unit_observation(result, "vst-runner.service", "") == [
        "loaded", "inactive", "dead", "0",
    ]


@pytest.mark.parametrize("result", [
    _systemd_unit_result(
        "LoadState=loaded\nActiveState=inactive\nSubState=dead\nJob=0\n", exit_code=1),
    _systemd_unit_result(
        "LoadState=loaded\nLoadState=loaded\nActiveState=inactive\nSubState=dead\nJob=0\n"),
    _systemd_unit_result("LoadState=loaded\nActiveState=inactive\nSubState=dead\n"),
])
def test_parse_unit_observation_rejects_failed_duplicate_or_missing_properties(result) -> None:
    with pytest.raises(RuntimeError):
        collector.parse_unit_observation(result, "vst-runner.service", "")


@pytest.mark.parametrize(("result", "scheduled"), [
    ({"exit_code": 1, "stdout": "", "stderr": "No scheduled shutdown."}, False),
    ({"exit_code": 0, "stdout": "Shutdown scheduled for 2026-10-30 12:30:00 UTC.\n",
      "stderr": ""}, True),
])
def test_shutdown_is_scheduled_accepts_only_explicit_known_results(result, scheduled) -> None:
    assert collector.shutdown_is_scheduled(result) is scheduled


@pytest.mark.parametrize("result", [
    {"exit_code": 2, "stdout": "", "stderr": "permission denied"},
    {"exit_code": 1, "stdout": "", "stderr": "unknown error"},
    {"exit_code": 0, "stdout": "", "stderr": ""},
])
def test_shutdown_is_scheduled_rejects_unknown_command_failure(result) -> None:
    with pytest.raises(RuntimeError, match="unknown result"):
        collector.shutdown_is_scheduled(result)


def test_candidate_identity_collision_accepts_installed_baseline_as_non_collision() -> None:
    bootstrap = {
        "request_id": "212a23e66ee94a7d87355b11e07e34fe",
        "run_id": "s2-runtime-20261030-334296bd0779488d837a27e283b50b6a",
    }
    probe = {
        "run_id": "s2-runtime-20261030-334296bd0779488d837a27e283b50b6a",
        "nonce": "b57520d076e1acd355d310ed18364907",
    }

    assert collector.candidate_identity_collision(False, bootstrap, probe) is False


@pytest.mark.parametrize("collision", ["bootstrap_run", "bootstrap_request", "probe_run", "probe_nonce"])
def test_candidate_identity_collision_detects_every_candidate_identifier(collision) -> None:
    bootstrap = {"request_id": "baseline-request", "run_id": "baseline-run"}
    probe = {"run_id": "baseline-run", "nonce": "baseline-nonce"}
    if collision == "bootstrap_run":
        bootstrap["run_id"] = collector.RUN_ID
    elif collision == "bootstrap_request":
        bootstrap["request_id"] = collector.REQUEST_ID
    elif collision == "probe_run":
        probe["run_id"] = collector.RUN_ID
    else:
        probe["nonce"] = collector.NONCE

    assert collector.candidate_identity_collision(False, bootstrap, probe) is True


@pytest.mark.parametrize(("bootstrap", "probe"), [
    ({"error": "JSONDecodeError: malformed bootstrap"},
     {"run_id": "baseline-run", "nonce": "baseline-nonce"}),
    ({"request_id": "request-only"},
     {"run_id": "baseline-run", "nonce": "baseline-nonce"}),
    ({"request_id": "", "run_id": "baseline-run"},
     {"run_id": "baseline-run", "nonce": "baseline-nonce"}),
    ({"request_id": "baseline-request", "run_id": "baseline-run"},
     {"error": "JSONDecodeError: malformed probe"}),
    ({"request_id": "baseline-request", "run_id": "baseline-run"},
     {"run_id": "baseline-run"}),
    ({"request_id": "baseline-request", "run_id": "baseline-run"},
     {"run_id": "baseline-run", "nonce": ""}),
])
def test_candidate_identity_collision_fails_closed_on_missing_error_or_malformed_records(
        bootstrap, probe) -> None:
    with pytest.raises(ValueError, match="identity observation is incomplete"):
        collector.candidate_identity_collision(False, bootstrap, probe)


def test_sanitized_git_environment_removes_overrides_and_keeps_path() -> None:
    source = {
        "GIT_DIR": "/tmp/untrusted.git",
        "GIT_WORK_TREE": "/tmp/untrusted-worktree",
        "GIT_INDEX_FILE": "/tmp/untrusted-index",
        "GIT_OPTIONAL_LOCKS": "0",
        "PATH": "/usr/bin:/bin",
        "HOME": "/root",
    }

    sanitized = collector.sanitized_git_environment(source)

    assert sanitized == {"PATH": "/usr/bin:/bin", "HOME": "/root"}
    assert "PATH" in sanitized
    assert not any(key.upper().startswith("GIT_") for key in sanitized)


def test_account_from_observation_parses_uid_gid_and_redacts_passwd_metadata() -> None:
    raw_metadata = "vst-runner:x:997:988:Private Person:/home/private:/bin/bash"
    result = {"exit_code": 0, "stdout": raw_metadata, "stderr": ""}

    account = collector.account_from_observation(result, "vst-runner")

    assert account == {"uid": 997, "gid": 988}
    assert result["stdout"] == "[redacted after UID/GID extraction]"
    assert raw_metadata not in result["stdout"]
    assert "Private Person" not in result["stdout"]
    assert "/home/private" not in result["stdout"]


@pytest.mark.parametrize("raw_record", [
    "other-user:x:997:988:Private Person:/home/private:/bin/bash",
    "vst-worker:x:not-a-uid:989:Private Person:/home/private:/bin/bash",
])
def test_account_from_observation_rejects_malformed_record_after_redaction(raw_record) -> None:
    result = {"exit_code": 0, "stdout": raw_record, "stderr": ""}

    with pytest.raises(RuntimeError, match="malformed"):
        collector.account_from_observation(result, "vst-worker")

    assert result["stdout"] == "[redacted after UID/GID extraction]"
    assert raw_record not in result["stdout"]
