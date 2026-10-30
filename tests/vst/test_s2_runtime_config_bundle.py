"""Functional checks for the prepared, non-secret S2-4 runtime bundle.

These tests validate candidate artifacts and a harmless nested-pytest adapter
contract. They do not install the bundle, start services, sign evidence, or run
the configured production qualification journey.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.vst.assignment_basis import (
    validate_bootstrap_request,
    validate_policy,
)
from tools.vst.contracts import (
    ContractError,
    TRUSTED_PARSER_CATALOG,
    canonical_bytes,
    manifest_sha256,
    validate_task_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = REPO_ROOT / "docs" / "sdlc" / "runtime-config"
SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"


def _json(name: str) -> dict:
    return json.loads((BUNDLE_DIR / name).read_text(encoding="utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_bundle_manifest_covers_every_payload_with_exact_bytes_and_safe_scope():
    bundle = _json("bundle-manifest.json")
    records = {record["path"]: record for record in bundle["files"]}
    payload_paths = {
        str(path.relative_to(BUNDLE_DIR)).replace("\\", "/")
        for path in BUNDLE_DIR.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
        and path.name not in {"bundle-manifest.json", "README.md"}
    }

    assert len(records) == 34
    assert payload_paths == set(records)
    assert len(bundle["units"]) == 9
    assert bundle["schema"] == "VST_S2_NON_SECRET_CONFIG_BUNDLE_V1"
    assert bundle["state"] == "PREPARED_NOT_INSTALLED"
    assert bundle["source_head"] == bundle["runtime_source_head"] == SOURCE_HEAD
    assert bundle["existing_store_migration_authorized"] is False
    assert bundle["preserve_existing_store"] is True
    assert bundle["unrestricted_dispatch_authorized"] is False
    assert bundle["services_started_by_installation"] is False

    for relative, record in records.items():
        candidate = (BUNDLE_DIR / relative).resolve()
        assert candidate.is_relative_to(BUNDLE_DIR.resolve())
        data = candidate.read_bytes()
        assert len(data) == record["size"], relative
        assert _sha256(data) == record["sha256"], relative
        assert b"-----BEGIN PRIVATE KEY-----" not in data, relative
        assert b"-----BEGIN OPENSSH PRIVATE KEY-----" not in data, relative
        assert b"-----BEGIN EC PRIVATE KEY-----" not in data, relative

    installation_sources = {
        item["source"] for item in bundle["configuration_installation"]
    }
    assert installation_sources <= set(records)
    assert all(item["uid"] == 0 for item in bundle["configuration_installation"])

    overrides = _json("installation-layout.json")["unit_overrides"]
    expected_rate_limit_overrides = {
        "unit-overrides/vst-runner.service.d/rate-limits.conf",
        "unit-overrides/vst-signer.service.d/rate-limits.conf",
        "unit-overrides/vst-supervisor.service.d/rate-limits.conf",
    }
    expected_host_path_overrides = {
        "unit-overrides/vst-runner.service.d/host-paths.conf",
        "unit-overrides/vst-sandbox-probe.service.d/host-paths.conf",
    }
    assert {item["source"] for item in overrides} == (
        expected_rate_limit_overrides | expected_host_path_overrides
    )
    assert bundle["unit_overrides"] == overrides
    expected_destinations = {
        "unit-overrides/vst-runner.service.d/host-paths.conf":
            "/etc/systemd/system/vst-runner.service.d/90-s2-host-path-mask.conf",
        "unit-overrides/vst-sandbox-probe.service.d/host-paths.conf":
            "/etc/systemd/system/vst-sandbox-probe.service.d/90-s2-host-path-mask.conf",
    }
    for item in overrides:
        data = (BUNDLE_DIR / item["source"]).read_bytes()
        if item["source"] in expected_rate_limit_overrides:
            assert data == b"[Unit]\nStartLimitIntervalSec=60s\nStartLimitBurst=3\n"
        else:
            assert data == (
                b"[Service]\n"
                b"InaccessiblePaths=-/init -/home -/mnt -/root -/usr/lib/wsl -/run/WSL -/tmp/.X11-unix\n"
                b"ProtectHome=no\n"
                b"TemporaryFileSystem=/run/user:ro,mode=0755\n"
            )
        expected_destination = expected_destinations.get(
            item["source"],
            "/etc/systemd/system/" + item["source"].removeprefix("unit-overrides/"),
        )
        assert item["destination"] == expected_destination
        assert item["uid"] == 0 and item["gid"] == 0 and item["mode"] == "0644"
        assert item["sha256"] == records[item["source"]]["sha256"] == _sha256(data)
    assert {
        item["destination"]
        for item in overrides
        if item["source"] in expected_host_path_overrides
    } == {
        "/etc/systemd/system/vst-runner.service.d/90-s2-host-path-mask.conf",
        "/etc/systemd/system/vst-sandbox-probe.service.d/90-s2-host-path-mask.conf",
    }


def test_actual_task_policy_and_bootstrap_validators_accept_only_crossbound_candidate():
    task = _json("task-manifest.json")
    request = _json("bootstrap-request.json")
    policy = _json("assignment-delegation-policy.json")
    bundle = _json("bundle-manifest.json")
    supervisor = _json("supervisor-service.json")

    validated_task = validate_task_manifest(task)
    assert manifest_sha256(validated_task) == bundle["task_manifest_sha256"]
    assert task["base_head"] == policy["source_head"] == SOURCE_HEAD
    assert policy["manifest_sha256"] == bundle["source_binding_sha256"]

    validated_policy, policy_digest = validate_policy(policy)
    assert policy_digest == bundle["assignment_policy_sha256"]
    assert policy_digest == supervisor["assignment_policy_sha256"]
    normalized = validate_bootstrap_request(request, policy=validated_policy)
    assert normalized["task_id"] == task["task_id"] == "S2-4-runtime-owner-runner-qualification"
    assert normalized["story_id"] == task["story_id"] == "S2-4"
    assert normalized["slot"] == "runtime-tests"
    assert normalized["attempt"] == 1

    wrong_digest_policy = copy.deepcopy(validated_policy)
    wrong_digest_policy["allowed_assignments"][0]["task_manifest_sha256"] = "0" * 64
    with pytest.raises(ContractError, match="outside the root assignment allowlist"):
        validate_bootstrap_request(request, policy=wrong_digest_policy)

    retry_request = copy.deepcopy(request)
    retry_request["attempt"] = 2
    with pytest.raises(ContractError, match="only permits attempt 1"):
        validate_bootstrap_request(retry_request, policy=validated_policy)

    invalid_task = copy.deepcopy(task)
    invalid_task["scope"] = ["../outside-repository"]
    with pytest.raises(ContractError):
        validate_task_manifest(invalid_task)


def test_model_and_reviewer_registry_digests_bind_the_declared_artifacts():
    model = _json("model-provenance.json")
    supervisor = _json("supervisor-service.json")
    task = _json("task-manifest.json")
    registry = _json("reviewer-registry.json")
    record = _json("reviewer-registry-record.json")
    reviewer_use = _json("reviewer-use-policy.json")
    transition = _json("runtime-transition-manifest.json")
    source = _json("deployment-source-manifest.json")
    bundle = _json("bundle-manifest.json")

    model_digest = _sha256((BUNDLE_DIR / "model-provenance.json").read_bytes())
    assert model["configured_model"] == task["model_policy"] == "gpt-6-luna"
    assert model["role"] == task["owner_role"] == "functional-test-reviewer"
    assert model["provider_executed_model"] == "NOT_VERIFIED"
    assert model["provider_signed_identity"] == "NOT_ATTESTED"
    assert supervisor["model_provenance"]["gpt-6-luna"] == model_digest

    unsigned_registry = {key: value for key, value in registry.items() if key != "signature"}
    registry_digest = _sha256(canonical_bytes(unsigned_registry))
    assert registry == record["registry"]
    assert record["unsigned_body_sha256"] == registry_digest
    assert task["reviewer_registry"] == {
        "version": registry["version"],
        "sha256": registry_digest,
    }
    assert registry["signature"] and len(registry["signature"]) == 64
    assert registry["entries"] == [
        {
            "key_id": "s2-local-independent-review-20261030",
            "principal": "vst-independent-reviewer",
        }
    ]
    assert "no external GPT-PM credential or review result is asserted" in record[
        "declaration_scope"
    ]
    assert reviewer_use["external_GPT_PM_credential"] is False
    assert reviewer_use["identity_registration_is_review_result"] is False
    assert reviewer_use["may_satisfy_final_PM_Bridge_approval"] is False
    assert reviewer_use["self_approval_allowed"] is False
    assert reviewer_use["root_registry_issuer_is_trusted"] is True
    assert reviewer_use["resistance_to_malicious_policy_owner_root_claimed"] is False
    assert reviewer_use["key_id"] == registry["entries"][0]["key_id"]

    assert _sha256(canonical_bytes(source)) == bundle["source_binding_sha256"]
    assert _sha256(canonical_bytes(transition)) == bundle["runtime_transition_sha256"]
    assert source["runtime_transition_manifest_sha256"] == bundle["runtime_transition_sha256"]
    assert source["runtime_tree_sha256"] == transition["runtime_tree_sha256"]
    assert source["runtime_source_head"] == source["task_source_head"] == SOURCE_HEAD


def test_public_material_matches_standalone_public_keys_and_probe_run_binding():
    public = _json("public-material.json")["public"]
    run_binding = _json("run-binding.json")
    probe_request = _json("probe-request.json")
    bootstrap_request = _json("bootstrap-request.json")
    supervisor = _json("supervisor-service.json")
    network_profile = _json("network-profile.json")

    for key, filename in (
        ("dispatch-instruction", "dispatch-instruction-public.pem"),
        ("execution-grant", "execution-grant-public.pem"),
    ):
        data = (BUNDLE_DIR / filename).read_bytes()
        assert public[key]["public_pem"].encode("ascii") == data
        assert public[key]["public_file_sha256"] == _sha256(data)
        assert b"PRIVATE KEY" not in data

    assert probe_request == {
        "run_id": run_binding["run_id"],
        "nonce": run_binding["probe_nonce"],
    }
    assert bootstrap_request["run_id"] == run_binding["run_id"]
    assert supervisor["run_id"] == run_binding["run_id"]
    assert supervisor["probe_nonce"] == run_binding["probe_nonce"]
    assert network_profile["environment_id"] == f"Ubuntu-24.04:S2:{run_binding['run_id']}"
    assert run_binding["runtime_source_head"] == SOURCE_HEAD
    assert run_binding["state"] == "PREPARATION_NOT_EXECUTION"


def test_fresh_runtime_identity_is_crossbound_and_single_selector_only():
    run_binding = _json("run-binding.json")
    probe_request = _json("probe-request.json")
    bootstrap = _json("bootstrap-request.json")
    supervisor = _json("supervisor-service.json")
    network = _json("network-profile.json")
    task = _json("task-manifest.json")

    run_id = run_binding["run_id"]
    nonce = run_binding["probe_nonce"]
    request_id = bootstrap["request_id"]
    retired_run = "s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8"
    retired_nonce = "0d2bb2c5f977478a924f7ec6629a339d"
    retired_request = "3e56a61c5b1e45aea089c305b25e3187"

    assert run_id and run_id != retired_run
    assert re.fullmatch(r"[0-9a-f]{32}", nonce) and nonce != retired_nonce
    assert re.fullmatch(r"[0-9a-f]{32}", request_id) and request_id != retired_request
    assert probe_request == {"run_id": run_id, "nonce": nonce}
    assert bootstrap["run_id"] == run_id
    assert supervisor["run_id"] == run_id
    assert supervisor["probe_nonce"] == nonce
    assert network["environment_id"] == f"Ubuntu-24.04:S2:{run_id}"
    assert task["task_id"] == "S2-4-runtime-owner-runner-qualification"
    assert task["retry_cap"] == 0
    assert task["required_tests"] == [
        {
            "acceptance": ["REQ-003"],
            "slot": "runtime-tests",
            "test_id": (
                "tests/vst/test_s2_assignment_basis.py::"
                "test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment"
            ),
        }
    ]


@pytest.fixture
def probe_entrypoint(monkeypatch):
    # Import the candidate module without using its configured runtime path as
    # a host input; all file, identity, clock and collector boundaries are then
    # controlled by each test below.
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec = importlib.util.spec_from_file_location(
        "s2_probe_candidate", BUNDLE_DIR / "probe-entrypoint.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_entrypoint_rejects_wrong_worker_identity_before_reading(probe_entrypoint):
    probe = probe_entrypoint
    probe.os = SimpleNamespace(
        geteuid=lambda: 998,
        getegid=lambda: 989,
    )
    probe._read_root_controlled_json = lambda *args, **kwargs: pytest.fail(
        "identity mismatch must stop before reading the request"
    )
    probe.collect_inventory = lambda *args, **kwargs: pytest.fail(
        "identity mismatch must not collect an inventory"
    )

    with pytest.raises(ContractError, match="configured isolated worker identity"):
        probe.main()


@pytest.mark.parametrize("bad_request", [{"run_id": "run-only"}, {"run_id": "r", "nonce": "n", "extra": 1}])
def test_probe_entrypoint_rejects_malformed_request_without_attestation_or_probe(
    probe_entrypoint, bad_request
):
    probe = probe_entrypoint
    probe.os = SimpleNamespace(geteuid=lambda: 999, getegid=lambda: 989)
    reads = []

    def read_json(path, *, max_bytes):
        reads.append(path)
        return bad_request

    probe._read_root_controlled_json = read_json
    probe.collect_inventory = lambda *args, **kwargs: pytest.fail(
        "malformed request must not reach the collector"
    )

    with pytest.raises(ContractError, match="request fields"):
        probe.main()
    assert reads == [probe.REQUEST_PATH]


def test_probe_entrypoint_times_out_closed_without_collector_or_network(probe_entrypoint):
    probe = probe_entrypoint
    probe.os = SimpleNamespace(geteuid=lambda: 999, getegid=lambda: 989)
    reads = []

    def read_json(path, *, max_bytes):
        reads.append(path)
        return {"run_id": "qualification-run", "nonce": "qualification-nonce"}

    ticks = iter((0.0, 60.0))
    probe._read_root_controlled_json = read_json
    probe.os.path = SimpleNamespace(lexists=lambda path: False)
    probe.time = SimpleNamespace(monotonic=lambda: next(ticks), sleep=lambda _: pytest.fail("no real wait"))
    probe.collect_inventory = lambda *args, **kwargs: pytest.fail(
        "missing attestation must not reach the collector or network probe"
    )

    with pytest.raises(ContractError, match="not published before the deadline"):
        probe.main()
    assert reads == [probe.REQUEST_PATH]


def test_manifest_pytest_adapter_emits_pass_only_after_all_three_reports_pass(tmp_path):
    task = _json("task-manifest.json")
    adapter_argv = task["allowed_commands"][0]["argv"]
    assert adapter_argv[:2] == ["/usr/bin/python3", "-c"]
    adapter_source = adapter_argv[2]
    assert "pytest_runtest_logreport" in adapter_source
    assert "('setup','call','teardown')" in adapter_source

    test_file = tmp_path / "test_outcomes.py"
    test_file.write_text(
        "\n".join(
            [
                "import pytest",
                "def test_pass():",
                "    pass",
                "def test_call_failure():",
                "    assert False",
                "@pytest.mark.skip(reason='contract fixture')",
                "def test_skip():",
                "    pass",
                "@pytest.mark.xfail(reason='contract fixture')",
                "def test_xfail():",
                "    assert False",
                "@pytest.fixture",
                "def teardown_failure():",
                "    yield",
                "    raise RuntimeError('teardown failed')",
                "def test_teardown_failure(teardown_failure):",
                "    pass",
                "@pytest.fixture",
                "def setup_failure():",
                "    raise RuntimeError('setup failed')",
                "def test_setup_failure(setup_failure):",
                "    pass",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-c",
        adapter_source,
        "--rootdir",
        str(tmp_path),
        "test_outcomes.py",
    ]
    completed = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode != 0  # The inner suite has actual failing cases.
    command_spec = task["mandatory_commands"][0]
    parser_key = (
        command_spec["parser_id"],
        command_spec["parser_version"],
        command_spec["parser_sha256"],
    )
    trusted_parser = TRUSTED_PARSER_CATALOG[parser_key]
    executed, skipped, xfailed = trusted_parser(completed.stdout)
    assert executed == ["test_outcomes.py::test_pass"], completed.stdout + completed.stderr
    assert skipped == []
    assert xfailed == []
