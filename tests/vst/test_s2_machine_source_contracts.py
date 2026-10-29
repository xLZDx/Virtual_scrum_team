"""TP-24/25: candidate machine authority schemas and observation-only evaluation."""
from __future__ import annotations

import base64
import copy
import datetime as dt
import hashlib
import os
import subprocess

import pytest

from tools.vst import machine_authorization as authorization
from tools.vst import machine_observations as observations
from tools.vst.contracts import ContractError, canonical_bytes

NOW = dt.datetime(2026, 10, 29, 12, 0, 0, tzinfo=dt.timezone.utc)
OP_POLICY_PURPOSE = authorization.POLICY_PURPOSE
OP_ASSIGN_PURPOSE = authorization.ASSIGNMENT_PURPOSE
ISSUER_PURPOSE = authorization.ISSUER_PURPOSE
OP_POLICY_KEY = "operator-policy-key"
OP_ASSIGN_KEY = "operator-assignment-key"
MACHINE_KEY = "delegated-issuer-key"
POLICY_ID = "s2-policy-1"
PROJECT = "Virtual_scrum_team"
REPOSITORY = "https://github.com/xLZDx/Virtual_scrum_team"
SPRINT = "39b7cc253f5d"
HEAD = "a" * 40
MANIFEST = "1" * 64
SIGNATURE = base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")


def valid_policy() -> dict:
    return {
        "schema": authorization.POLICY_SCHEMA,
        "operator_key_id": OP_POLICY_KEY,
        "policy_id": POLICY_ID,
        "project": PROJECT,
        "repository": REPOSITORY,
        "sprint_id": SPRINT,
        "role": "dispatch-issuer",
        "machine_principal": "vst-machine-issuer",
        "machine_key_id": MACHINE_KEY,
        "key_purpose": ISSUER_PURPOSE,
        "source_head": HEAD,
        "manifest_sha256": MANIFEST,
        "allowed_authorization_type": authorization.ASSIGNMENT_SCHEMA,
        "not_before": "2026-10-29T11:00:00Z",
        "expires_at": "2026-10-29T13:00:00Z",
        "revocation_id": "policy-revoke-1",
        "signature": SIGNATURE,
    }


def trust_config(policy: dict) -> dict:
    policy_digest = hashlib.sha256(canonical_bytes(policy)).hexdigest()
    return {
        "schema": authorization.TRUST_SCHEMA,
        "operator_authorities": [
            {"key_id": OP_POLICY_KEY, "purpose": OP_POLICY_PURPOSE,
             "public_key_path": "/test/policy.pub", "revocation_id": "op-policy-revoke"},
            {"key_id": OP_ASSIGN_KEY, "purpose": OP_ASSIGN_PURPOSE,
             "public_key_path": "/test/assignment.pub", "revocation_id": "op-assignment-revoke"},
        ],
        "machine_principals": [{
            "principal": "vst-machine-issuer", "key_id": MACHINE_KEY,
            "purpose": ISSUER_PURPOSE, "public_key_path": "/test/machine.pub",
            "policy_sha256": policy_digest, "not_before": "2026-10-29T11:00:00Z",
            "expires_at": "2026-10-29T13:00:00Z", "revocation_id": "machine-revoke-1",
        }],
        "revocations": [],
    }


def valid_assignment(policy: dict, config: dict) -> dict:
    return {
        "schema": authorization.ASSIGNMENT_SCHEMA,
        "authorization_id": "assignment-1",
        "project": PROJECT,
        "repository": REPOSITORY,
        "sprint_id": SPRINT,
        "manifest_sha256": MANIFEST,
        "task_id": "task-1",
        "story_id": "S2-3",
        "principal": "Codex",
        "slot": "slot-1",
        "attempt": 1,
        "epoch": 2,
        "lease_id": "lease-1",
        "run_id": "run-1",
        "request_id": "2" * 32,
        "policy_id": POLICY_ID,
        "policy_sha256": hashlib.sha256(canonical_bytes(policy)).hexdigest(),
        "authorization_key_id": OP_ASSIGN_KEY,
        "issuer_key_id": MACHINE_KEY,
        "issuer_key_purpose": ISSUER_PURPOSE,
        "issued_at": "2026-10-29T11:30:00Z",
        "expires_at": "2026-10-29T12:30:00Z",
        "revocation_id": "assignment-revoke-1",
        "signature": SIGNATURE,
    }


def valid_snapshot() -> dict:
    return {
        "task_id": "task-1", "story_id": "S2-3", "owner_principal": "Codex",
        "slot": "slot-1", "attempt": 1, "owner_epoch": 2, "lease_id": "lease-1",
        "run_id": "run-1", "manifest_sha256": MANIFEST,
        "assignment_state": "ASSIGNED", "lease_state": "LIVE",
    }


def test_policy_and_assignment_have_exact_closed_schemas() -> None:
    policy = valid_policy()
    assignment = valid_assignment(policy, trust_config(policy))

    assert authorization.validate_delegation_policy(policy, now=NOW) == policy
    assert authorization.validate_assignment_authorization(assignment, now=NOW) == assignment
    for source, validator in (
        (policy, authorization.validate_delegation_policy),
        (assignment, authorization.validate_assignment_authorization),
    ):
        extra = copy.deepcopy(source)
        extra["unreviewed"] = True
        with pytest.raises(ContractError, match="closed contract"):
            validator(extra, now=NOW)
        missing = copy.deepcopy(source)
        missing.pop("signature")
        with pytest.raises(ContractError, match="closed contract"):
            validator(missing, now=NOW)


def test_policy_and_assignment_reject_boolean_counters_and_expired_records() -> None:
    policy = valid_policy()
    assignment = valid_assignment(policy, trust_config(policy))
    assignment["attempt"] = True
    with pytest.raises(ContractError, match="positive integer"):
        authorization.validate_assignment_authorization(assignment, now=NOW)

    expired = valid_policy()
    expired["expires_at"] = "2026-10-29T11:59:59Z"
    with pytest.raises(ContractError, match="validity window"):
        authorization.validate_delegation_policy(expired, now=NOW)


def test_json_parser_rejects_duplicate_keys_and_non_object() -> None:
    with pytest.raises(ContractError, match="duplicate JSON field"):
        authorization.parse_json_object(b'{"schema":"one","schema":"two"}', name="fixture")
    with pytest.raises(ContractError, match="root must be an object"):
        authorization.parse_json_object(b'[1,2]', name="fixture")


def write_ed25519_keypair(directory, key_name: str) -> tuple[str, str]:
    private_path = directory / f"{key_name}.pem"
    public_path = directory / f"{key_name}.pub.pem"
    subprocess.run(["/usr/bin/openssl", "genpkey", "-algorithm", "Ed25519",
                    "-out", str(private_path)], check=True, capture_output=True)
    subprocess.run(["/usr/bin/openssl", "pkey", "-in", str(private_path), "-pubout",
                    "-out", str(public_path)], check=True, capture_output=True)
    os.chmod(private_path, 0o600)
    os.chmod(public_path, 0o644)
    return str(private_path), str(public_path)


def sign_object(value: dict, *, private_path: str, domain: str) -> None:
    payload_path = private_path + ".payload"
    signature_path = private_path + ".signature"
    with open(payload_path, "wb") as stream:
        stream.write(authorization.signing_bytes(value, domain=domain))
    subprocess.run(["/usr/bin/openssl", "pkeyutl", "-sign", "-inkey", private_path,
                    "-rawin", "-in", payload_path, "-out", signature_path],
                   check=True, capture_output=True)
    with open(signature_path, "rb") as stream:
        value["signature"] = base64.urlsafe_b64encode(stream.read()).decode("ascii").rstrip("=")


def signed_fixture(tmp_path):
    policy_private, policy_public = write_ed25519_keypair(tmp_path, "policy")
    assignment_private, assignment_public = write_ed25519_keypair(tmp_path, "assignment")
    policy = valid_policy()
    sign_object(policy, private_path=policy_private, domain=OP_POLICY_PURPOSE)
    config = trust_config(policy)
    config["operator_authorities"][0]["public_key_path"] = policy_public
    config["operator_authorities"][1]["public_key_path"] = assignment_public
    assignment = valid_assignment(policy, config)
    sign_object(assignment, private_path=assignment_private, domain=OP_ASSIGN_PURPOSE)
    return policy, assignment, config


@pytest.mark.skipif(os.name != "posix", reason="OpenSSL key verification requires POSIX root-controlled paths")
def test_signed_assignment_binds_current_store_snapshot_and_separate_purposes(
    tmp_path,
) -> None:
    policy, assignment, config = signed_fixture(tmp_path)

    result = authorization.verify_assignment_authorization(
        assignment, policy, config, valid_snapshot(), openssl_path="/usr/bin/openssl",
        expected_project=PROJECT, expected_repository=REPOSITORY,
        expected_sprint_id=SPRINT, expected_manifest_sha256=MANIFEST,
        expected_source_head=HEAD, now=NOW,
    )
    assert result["snapshot_match"] is True
    assert result["authorization"]["authorization_key_id"] == OP_ASSIGN_KEY
    assert result["authorization"]["issuer_key_id"] == MACHINE_KEY

    changed_snapshot = valid_snapshot()
    changed_snapshot["owner_principal"] = "different-principal"
    with pytest.raises(ContractError, match="current Store snapshot"):
        authorization.verify_assignment_authorization(
            assignment, policy, config, changed_snapshot, openssl_path="/usr/bin/openssl",
            expected_project=PROJECT, expected_repository=REPOSITORY,
            expected_sprint_id=SPRINT, expected_manifest_sha256=MANIFEST,
            expected_source_head=HEAD, now=NOW,
        )


@pytest.mark.skipif(os.name != "posix", reason="OpenSSL key verification requires POSIX root-controlled paths")
@pytest.mark.parametrize("mutation", ["bad_signature", "wrong_purpose", "revoked"])
def test_assignment_signature_purpose_and_revocation_fail_closed(tmp_path, mutation: str) -> None:
    policy, assignment, config = signed_fixture(tmp_path)
    if mutation == "bad_signature":
        assignment["signature"] = base64.urlsafe_b64encode(bytes([1]) * 64).decode("ascii").rstrip("=")
        expected_error = "signature verification failed"
    elif mutation == "wrong_purpose":
        assignment["authorization_key_id"] = OP_POLICY_KEY
        expected_error = "not uniquely trusted for purpose"
    else:
        config["revocations"].append({
            "revocation_id": "assignment-revoke-1", "revoked_at": "2026-10-29T11:45:00Z",
            "reason_code": "operator-revoked",
        })
        expected_error = "authorization is revoked"

    with pytest.raises(ContractError, match=expected_error):
        authorization.verify_assignment_authorization(
            assignment, policy, config, valid_snapshot(), openssl_path="/usr/bin/openssl",
            expected_project=PROJECT, expected_repository=REPOSITORY,
            expected_sprint_id=SPRINT, expected_manifest_sha256=MANIFEST,
            expected_source_head=HEAD, now=NOW,
        )


@pytest.mark.skipif(os.name != "posix", reason="OpenSSL key verification requires POSIX root-controlled paths")
def test_policy_rejects_a_bad_operator_signature(tmp_path) -> None:
    policy, _assignment, config = signed_fixture(tmp_path)
    policy["signature"] = base64.urlsafe_b64encode(bytes([1]) * 64).decode("ascii").rstrip("=")

    with pytest.raises(ContractError, match="signature verification failed"):
        authorization.verify_policy(policy, config, openssl_path="/usr/bin/openssl", now=NOW)


@pytest.mark.skipif(os.name != "posix", reason="OpenSSL key verification requires POSIX root-controlled paths")
def test_signed_assignment_rejects_changed_store_snapshot(tmp_path) -> None:
    policy, assignment, config = signed_fixture(tmp_path)
    snapshot = valid_snapshot()
    snapshot["owner_principal"] = "different-principal"

    with pytest.raises(ContractError, match="current Store snapshot"):
        authorization.verify_assignment_authorization(
            assignment, policy, config, snapshot, openssl_path="/usr/bin/openssl",
            expected_project=PROJECT, expected_repository=REPOSITORY,
            expected_sprint_id=SPRINT, expected_manifest_sha256=MANIFEST,
            expected_source_head=HEAD, now=NOW,
        )


def windows_observation() -> dict:
    return {
        "os_id": "windows", "os_build": "test-build", "firewall_profiles": [],
        "effective_firewall_rules": [], "wsl_hyperv_firewall_profiles": [],
        "effective_wsl_hyperv_firewall_rules": [], "wsl_distributions": [],
        "wsl_network_configuration": [], "host_endpoints": [], "host_path_exposures": [],
        "collection_complete": False, "errors": [], "raw_command_outputs": {},
    }


def wsl_observation() -> dict:
    return {
        "os_id": "ubuntu", "os_build": "24.04", "kernel_release": "test-kernel",
        "nft_ruleset_raw": "", "ipv4_routes_raw": "", "ipv6_routes_raw": "",
        "ipv4_rules_raw": "", "ipv6_rules_raw": "", "namespaces_raw": "",
        "interfaces_raw": "", "mounts_raw": "", "windows_drive_mounts": [],
        "wsl_interop_present": False, "wsl_interop_enabled": False,
        "container_socket_paths": [], "container_socket_inventory_complete": False,
        "listeners_raw": "", "uid": None, "gid": None,
        "collection_complete": False, "errors": [],
    }


def test_observation_bundle_hashes_both_sources_and_evaluation_never_passes() -> None:
    bundle = observations.build_observation_bundle(
        "run-1", HEAD, "3" * 64, windows_observation(), wsl_observation(),
        nonce="4" * 32, now=NOW,
    )
    assert observations.validate_observation_bundle(bundle) == bundle
    result = observations.evaluate_observation_completeness(
        bundle, expected_run_id="run-1", expected_nonce="4" * 32,
        expected_source_head=HEAD, expected_spec_sha256="3" * 64,
    )
    assert result["status"] == "UNKNOWN"
    assert "PASS" not in result["status"]
    assert result["missing_sources"]
    assert "not an E5 attestation" in result["limitations"]


@pytest.mark.parametrize("mutation", ["raw_hash", "missing_source", "unknown_field", "wrong_nonce"])
def test_observation_bundle_rejects_tampered_or_incomplete_provenance(mutation: str) -> None:
    bundle = observations.build_observation_bundle(
        "run-1", HEAD, "3" * 64, windows_observation(), wsl_observation(),
        nonce="4" * 32, now=NOW,
    )
    if mutation == "raw_hash":
        bundle["raw_observations"]["wsl-guest"]["os_build"] = "changed"
    elif mutation == "missing_source":
        bundle["sources"].pop()
    elif mutation == "unknown_field":
        bundle["extra"] = True
    else:
        with pytest.raises(ContractError, match="freshness or source binding"):
            observations.evaluate_observation_completeness(
                bundle, expected_run_id="run-1", expected_nonce="5" * 32,
                expected_source_head=HEAD, expected_spec_sha256="3" * 64,
            )
        return

    with pytest.raises(ContractError):
        observations.validate_observation_bundle(bundle)


def test_observation_inputs_cannot_claim_complete_windows_policy_or_e5_pass() -> None:
    raw = windows_observation()
    raw["collection_complete"] = True
    with pytest.raises(ContractError, match="not authorized in this source scope"):
        observations.build_observation_bundle(
            "run-1", HEAD, "3" * 64, raw, wsl_observation(), nonce="4" * 32, now=NOW,
        )

    incomplete = wsl_observation()
    incomplete["collection_complete"] = True
    with pytest.raises(ContractError, match="cannot be complete"):
        observations.build_observation_bundle(
            "run-1", HEAD, "3" * 64, windows_observation(), incomplete,
            nonce="4" * 32, now=NOW,
        )


def test_observation_schema_rejects_boolean_identity_and_omitted_fields() -> None:
    invalid_identity = wsl_observation()
    invalid_identity["uid"] = True
    with pytest.raises(ContractError, match="uid is invalid"):
        observations.build_observation_bundle(
            "run-1", HEAD, "3" * 64, windows_observation(), invalid_identity,
            nonce="4" * 32, now=NOW,
        )

    invalid_shape = windows_observation()
    invalid_shape.pop("effective_firewall_rules")
    with pytest.raises(ContractError, match="exact schema"):
        observations.build_observation_bundle(
            "run-1", HEAD, "3" * 64, invalid_shape, wsl_observation(),
            nonce="4" * 32, now=NOW,
        )
