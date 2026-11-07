"""S2-4 bounded source tests for versioned delegated assignment authorization.

All cryptographic keys and Store rows are disposable fixtures. These tests do not
provision trust, invoke a signer, enable dispatch, or produce machine E5 evidence.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools.vst import machine_authorization as auth
from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.store import StoreError
from tools.vst.supervisor_service import SupervisorPeer
from tests.vst.e1e4_helpers import manifest
from tests.vst.test_s2_assignment_basis import _readiness


def _unsigned_v2_shapes():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")
    policy = {
        "schema": auth.POLICY_SCHEMA_V2, "operator_key_id": "operator-policy-v2",
        "policy_id": "delegation-policy-v2", "project": "Virtual_scrum_team",
        "repository": "Virtual_scrum_team", "sprint_id": "39b7cc253f5d",
        "role": "dispatch-issuer", "machine_principal": "vst-machine-issuer-v2",
        "machine_key_id": "machine-issuer-key-v2", "key_purpose": auth.ISSUER_PURPOSE_V2,
        "source_head": "a" * 40, "manifest_sha256": "b" * 64,
        "allowed_authorization_type": auth.ASSIGNMENT_SCHEMA_V2,
        "not_before": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revocation_id": "delegation-revocation-v2", "signature": signature,
    }
    policy_sha = hashlib.sha256(canonical_bytes(policy)).hexdigest()
    trust = {
        "schema": auth.TRUST_SCHEMA_V2,
        "operator_authorities": [
            {"key_id": "operator-policy-v2", "purpose": auth.POLICY_PURPOSE_V2,
             "public_key_path": str(Path.cwd() / "synthetic-policy.pub"),
             "revocation_id": "operator-policy-revocation-v2"},
            {"key_id": "operator-auth-v2", "purpose": auth.ASSIGNMENT_PURPOSE_V2,
             "public_key_path": str(Path.cwd() / "synthetic-assignment.pub"),
             "revocation_id": "operator-auth-revocation-v2"},
        ],
        "machine_principals": [{
            "principal": "vst-machine-issuer-v2", "key_id": "machine-issuer-key-v2",
            "purpose": auth.ISSUER_PURPOSE_V2,
            "public_key_path": str(Path.cwd() / "synthetic-machine.pub"),
            "policy_sha256": policy_sha,
            "not_before": policy["not_before"], "expires_at": policy["expires_at"],
            "revocation_id": "machine-revocation-v2",
        }],
        "revocations": [],
    }
    assignment = {
        "schema": auth.ASSIGNMENT_SCHEMA_V2, "authorization_id": "assignment-auth-v2-1",
        "assignment_operation_id": "c" * 64, "project": "Virtual_scrum_team",
        "repository": "Virtual_scrum_team", "sprint_id": "39b7cc253f5d",
        "source_head": "a" * 40, "manifest_sha256": "b" * 64,
        "project_id": "vst-project", "phase": 3, "task_manifest_sha256": "d" * 64,
        "task_id": "task-v2-1", "story_id": "S2-4", "principal": "Codex",
        "slot": "tests", "attempt": 1, "epoch": 2, "lease_id": 3,
        "runner_id": "runner-1", "run_id": "run-v2-1", "service_generation": "generation-v2-1",
        "probe_sha256": "e" * 64, "request_id": "f" * 32,
        "assignment_policy_id": "assignment-policy-v1", "assignment_policy_sha256": "1" * 64,
        "delegation_policy_id": policy["policy_id"], "delegation_policy_sha256": policy_sha,
        "authorization_key_id": "operator-auth-v2", "issuer_key_id": policy["machine_key_id"],
        "issuer_key_purpose": auth.ISSUER_PURPOSE_V2,
        "issued_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revocation_id": "assignment-revocation-v2", "signature": signature,
    }
    return now, policy, trust, assignment


def test_v2_closed_schemas_and_v1_downgrade_rejection_without_crypto():
    now, policy, trust, assignment = _unsigned_v2_shapes()
    assert auth.validate_delegation_policy_v2(policy, now=now) == policy
    assert auth.validate_trust_config_v2(trust, now=now) == trust
    assert auth.validate_assignment_authorization_v2(assignment, now=now) == assignment
    for value, validator in (
        (policy, auth.validate_delegation_policy_v2),
        (trust, auth.validate_trust_config_v2),
        (assignment, auth.validate_assignment_authorization_v2),
    ):
        with pytest.raises(ContractError):
            validator({**value, "unreviewed": True}, now=now)
        missing = dict(value)
        missing.pop("signature" if "signature" in value else "revocations")
        with pytest.raises(ContractError):
            validator(missing, now=now)
    trust_v1 = {**trust, "schema": auth.TRUST_SCHEMA}
    with pytest.raises(ContractError, match="unsupported schema"):
        auth.validate_trust_config_v2(trust_v1, now=now)
    policy_v1 = {**policy, "schema": auth.POLICY_SCHEMA}
    with pytest.raises(ContractError, match="unsupported schema"):
        auth.validate_delegation_policy_v2(policy_v1, now=now)
    assignment_v1 = {**assignment, "schema": auth.ASSIGNMENT_SCHEMA}
    with pytest.raises(ContractError, match="unsupported schema"):
        auth.validate_assignment_authorization_v2(assignment_v1, now=now)


def test_v2_rejects_boolean_counters_and_v1_signature_purposes():
    now, policy, trust, assignment = _unsigned_v2_shapes()
    bad_counter = {**assignment, "attempt": True}
    with pytest.raises(ContractError, match="positive integer"):
        auth.validate_assignment_authorization_v2(bad_counter, now=now)
    bad_issuer = {**assignment, "issuer_key_purpose": auth.ISSUER_PURPOSE}
    with pytest.raises(ContractError, match="issuer purpose"):
        auth.validate_assignment_authorization_v2(bad_issuer, now=now)
    bad_policy = {**policy, "key_purpose": auth.ISSUER_PURPOSE}
    with pytest.raises(ContractError, match="key purpose"):
        auth.validate_delegation_policy_v2(bad_policy, now=now)
    bad_auth_type = {**policy, "allowed_authorization_type": auth.ASSIGNMENT_SCHEMA}
    with pytest.raises(ContractError, match="authorization type"):
        auth.validate_delegation_policy_v2(bad_auth_type, now=now)


@pytest.fixture
def synthetic_root_keys():
    if os.name != "posix" or os.geteuid() != 0:
        pytest.skip("synthetic V2 signatures require the designated root-owned POSIX fixture")
    openssl = shutil.which("openssl")
    root = Path("/root")
    if not openssl or not root.is_dir() or root.stat().st_uid != 0 or root.stat().st_mode & 0o022:
        pytest.skip("private root-owned OpenSSL fixture storage is unavailable")
    with tempfile.TemporaryDirectory(prefix="vst-s2-machine-v2-", dir="/root") as tmp:
        directory = Path(tmp)
        directory.chmod(0o700)
        keys = {}
        for name in ("policy", "authorization", "machine"):
            private = directory / f"{name}.pem"
            public = directory / f"{name}.pub.pem"
            subprocess.run([openssl, "genpkey", "-algorithm", "ED25519", "-out", str(private)],
                           check=True, capture_output=True, timeout=10)
            os.chmod(private, 0o600)
            subprocess.run([openssl, "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                           check=True, capture_output=True, timeout=10)
            os.chmod(public, 0o644)
            keys[name] = {"private": str(private), "public": str(public)}
        keys["openssl"] = openssl
        yield directory, keys


def _sign(value: dict, *, private_path: str, purpose: str) -> None:
    payload = private_path + ".payload"
    signature = private_path + ".signature"
    Path(payload).write_bytes(auth.signing_bytes(value, domain=purpose))
    subprocess.run(["/usr/bin/openssl", "pkeyutl", "-sign", "-inkey", private_path,
                    "-rawin", "-in", payload, "-out", signature],
                   check=True, capture_output=True, timeout=10)
    value["signature"] = base64.urlsafe_b64encode(Path(signature).read_bytes()).decode("ascii").rstrip("=")
    Path(payload).unlink()
    Path(signature).unlink()


def _signed_store_fixture(synthetic_root_keys):
    _directory, keys = synthetic_root_keys
    store, supervisor, assignment_policy, assignment_policy_sha, operation_id, handoff = _readiness(
        manifest(),
    )
    issued = datetime.strptime(handoff["issued_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc,
    )
    now = issued + timedelta(seconds=1)
    delegation_policy = {
        "schema": auth.POLICY_SCHEMA_V2,
        "operator_key_id": "operator-policy-v2",
        "policy_id": "delegation-policy-v2",
        "project": "Virtual_scrum_team",
        "repository": "Virtual_scrum_team",
        "sprint_id": handoff["sprint_id"],
        "role": "dispatch-issuer",
        "machine_principal": "vst-machine-issuer-v2",
        "machine_key_id": "machine-issuer-key-v2",
        "key_purpose": auth.ISSUER_PURPOSE_V2,
        "source_head": handoff["source_head"],
        "manifest_sha256": handoff["manifest_sha256"],
        "allowed_authorization_type": auth.ASSIGNMENT_SCHEMA_V2,
        "not_before": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (issued + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revocation_id": "delegation-revocation-v2",
        "signature": "A" * 86,
    }
    _sign(delegation_policy, private_path=keys["policy"]["private"],
          purpose=auth.POLICY_PURPOSE_V2)
    delegation_policy_sha = hashlib.sha256(canonical_bytes(delegation_policy)).hexdigest()
    trust_config = {
        "schema": auth.TRUST_SCHEMA_V2,
        "operator_authorities": [
            {"key_id": "operator-policy-v2", "purpose": auth.POLICY_PURPOSE_V2,
             "public_key_path": keys["policy"]["public"], "revocation_id": "op-policy-revoke-v2"},
            {"key_id": "operator-auth-v2", "purpose": auth.ASSIGNMENT_PURPOSE_V2,
             "public_key_path": keys["authorization"]["public"], "revocation_id": "op-auth-revoke-v2"},
        ],
        "machine_principals": [{
            "principal": "vst-machine-issuer-v2", "key_id": "machine-issuer-key-v2",
            "purpose": auth.ISSUER_PURPOSE_V2, "public_key_path": keys["machine"]["public"],
            "policy_sha256": delegation_policy_sha,
            "not_before": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": (issued + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "revocation_id": "machine-revocation-v2",
        }],
        "revocations": [],
    }
    record = {
        "schema": auth.ASSIGNMENT_SCHEMA_V2,
        "authorization_id": "assignment-auth-v2-1",
        "assignment_operation_id": operation_id,
        "project": handoff["repository"], "repository": handoff["repository"],
        "sprint_id": handoff["sprint_id"], "source_head": handoff["source_head"],
        "manifest_sha256": handoff["manifest_sha256"], "project_id": handoff["project_id"],
        "phase": handoff["phase"], "task_manifest_sha256": handoff["task_manifest_sha256"],
        "task_id": handoff["task_id"], "story_id": handoff["story_id"],
        "principal": "Codex", "slot": handoff["slot"], "attempt": handoff["attempt"],
        "epoch": handoff["epoch"], "lease_id": handoff["lease_id"],
        "runner_id": handoff["runner_id"], "run_id": handoff["run_id"],
        "service_generation": handoff["service_generation"], "probe_sha256": handoff["probe_sha256"],
        "request_id": handoff["bootstrap_request"]["request_id"],
        "assignment_policy_id": handoff["policy_id"],
        "assignment_policy_sha256": assignment_policy_sha,
        "delegation_policy_id": delegation_policy["policy_id"],
        "delegation_policy_sha256": delegation_policy_sha,
        "authorization_key_id": "operator-auth-v2",
        "issuer_key_id": "machine-issuer-key-v2",
        "issuer_key_purpose": auth.ISSUER_PURPOSE_V2,
        "issued_at": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": handoff["expires_at_utc"],
        "revocation_id": "assignment-revocation-v2",
        "signature": "A" * 86,
    }
    _sign(record, private_path=keys["authorization"]["private"],
          purpose=auth.ASSIGNMENT_PURPOSE_V2)
    supervisor._probe_consumed = True  # synthetic fixture state only; no E5 evidence is claimed
    supervisor.dispatch_instruction_openssl_path = keys["openssl"]
    supervisor.machine_delegation_policy_provider = lambda: copy.deepcopy(delegation_policy)
    supervisor.machine_delegation_trust_provider = lambda: copy.deepcopy(trust_config)
    supervisor.machine_assignment_authorization_provider = lambda identifier: copy.deepcopy(record)
    return {
        "store": store, "supervisor": supervisor, "assignment_policy": assignment_policy,
        "assignment_policy_sha256": assignment_policy_sha, "operation_id": operation_id,
        "handoff": handoff, "delegation_policy": delegation_policy,
        "delegation_policy_sha256": delegation_policy_sha, "trust_config": trust_config,
        "record": record, "keys": keys, "now": now,
    }


def _issuer_peer(**changes):
    values = {
        "role": "delegated_issuer", "uid": 981, "gid": 983,
        "cgroup": "/system.slice/vst-delegated-issuer.service",
        "operations": frozenset({"issue_root_dispatch_instruction"}),
    }
    values.update(changes)
    return SupervisorPeer(**values)


@pytest.mark.skipif(os.name != "posix", reason="V2 signing fixtures require root-owned POSIX key paths")
def test_v2_policy_and_assignment_signatures_bind_distinct_purposes_and_exact_store_tuple(
    synthetic_root_keys,
):
    case = _signed_store_fixture(synthetic_root_keys)
    try:
        verified = auth.verify_assignment_authorization_v2(
            case["record"], case["delegation_policy"], case["trust_config"],
            openssl_path=case["keys"]["openssl"], now=case["now"],
        )
        snapshot = case["store"].authenticated_assignment_basis(
            case["operation_id"], policy=case["assignment_policy"],
            policy_sha256=case["assignment_policy_sha256"],
            active_service_generation=case["handoff"]["service_generation"],
            expected_run_id=case["handoff"]["run_id"],
        )
        checked = auth.compare_assignment_authorization_v2_to_store(verified, snapshot)
        assert checked["authorization_id"] == case["record"]["authorization_id"]
        assert checked["assignment_operation_id"] == case["operation_id"]
        assert checked["handoff_sha256"] == case["handoff"]["handoff_sha256"]
    finally:
        case["store"].close()


@pytest.mark.skipif(os.name != "posix", reason="V2 signatures require root-owned POSIX key paths")
def test_v2_schemas_are_closed_and_v1_trust_or_purposes_cannot_authorize_v2(
    synthetic_root_keys,
):
    case = _signed_store_fixture(synthetic_root_keys)
    try:
        auth.validate_delegation_policy_v2(case["delegation_policy"], now=case["now"])
        auth.validate_trust_config_v2(case["trust_config"], now=case["now"])
        auth.validate_assignment_authorization_v2(case["record"], now=case["now"])
        for value, validator in (
            (case["delegation_policy"], auth.validate_delegation_policy_v2),
            (case["trust_config"], auth.validate_trust_config_v2),
            (case["record"], auth.validate_assignment_authorization_v2),
        ):
            extra = {**value, "unknown": "must reject"}
            with pytest.raises(ContractError):
                validator(extra, now=case["now"])
            missing = dict(value)
            missing.pop("signature" if "signature" in value else "revocations", None)
            with pytest.raises(ContractError):
                validator(missing, now=case["now"])

        v1_trust = copy.deepcopy(case["trust_config"])
        v1_trust["schema"] = auth.TRUST_SCHEMA
        with pytest.raises(ContractError, match="unsupported schema"):
            auth.validate_trust_config_v2(v1_trust, now=case["now"])
        wrong_purpose = copy.deepcopy(case["trust_config"])
        wrong_purpose["operator_authorities"][0]["purpose"] = auth.POLICY_PURPOSE
        with pytest.raises(ContractError, match="non-V2 purpose"):
            auth.validate_trust_config_v2(wrong_purpose, now=case["now"])
        v1_policy = {**case["delegation_policy"], "schema": auth.POLICY_SCHEMA}
        with pytest.raises(ContractError, match="unsupported schema"):
            auth.validate_delegation_policy_v2(v1_policy, now=case["now"])
        v1_record = {**case["record"], "schema": auth.ASSIGNMENT_SCHEMA}
        with pytest.raises(ContractError, match="unsupported schema"):
            auth.validate_assignment_authorization_v2(v1_record, now=case["now"])
    finally:
        case["store"].close()


@pytest.mark.skipif(os.name != "posix", reason="V2 signatures require root-owned POSIX key paths")
@pytest.mark.parametrize("mutation", ["bad_signature", "wrong_issuer_purpose", "stale_source", "revoked"])
def test_v2_assignment_rejects_bad_signature_purpose_stale_scope_and_revocation(
    synthetic_root_keys, mutation: str,
):
    case = _signed_store_fixture(synthetic_root_keys)
    try:
        record = copy.deepcopy(case["record"])
        trust = copy.deepcopy(case["trust_config"])
        if mutation == "bad_signature":
            record["signature"] = base64.urlsafe_b64encode(bytes([3]) * 64).decode("ascii").rstrip("=")
        elif mutation == "wrong_issuer_purpose":
            record["issuer_key_purpose"] = auth.ISSUER_PURPOSE
            _sign(record, private_path=case["keys"]["authorization"]["private"],
                  purpose=auth.ASSIGNMENT_PURPOSE_V2)
        elif mutation == "stale_source":
            record["source_head"] = "f" * 40
            _sign(record, private_path=case["keys"]["authorization"]["private"],
                  purpose=auth.ASSIGNMENT_PURPOSE_V2)
        else:
            trust["revocations"].append({
                "revocation_id": record["revocation_id"], "revoked_at": "2026-10-29T11:59:59Z",
                "reason_code": "operator-revoked",
            })
        with pytest.raises(ContractError):
            auth.verify_assignment_authorization_v2(
                record, case["delegation_policy"], trust,
                openssl_path=case["keys"]["openssl"], now=case["now"],
            )
    finally:
        case["store"].close()


@pytest.mark.skipif(os.name != "posix", reason="V2 signatures require root-owned POSIX key paths")
def test_supervisor_loads_authorization_by_id_and_reads_store_snapshot_internally(
    synthetic_root_keys, monkeypatch,
):
    case = _signed_store_fixture(synthetic_root_keys)
    try:
        calls = []
        original = case["store"].authenticated_assignment_basis

        def observe(operation_id, **kwargs):
            calls.append((operation_id, kwargs))
            return original(operation_id, **kwargs)

        monkeypatch.setattr(case["store"], "authenticated_assignment_basis", observe)
        checked = case["supervisor"].verify_machine_assignment_authorization_v2(
            case["record"]["authorization_id"], peer=_issuer_peer(),
        )
        assert checked["authorization_id"] == case["record"]["authorization_id"]
        assert checked["assignment_operation_id"] == case["operation_id"]
        assert len(calls) == 1
        assert calls[0][0] == case["record"]["assignment_operation_id"]
        assert calls[0][1]["expected_run_id"] == case["handoff"]["run_id"]
    finally:
        case["store"].close()


@pytest.mark.skipif(os.name != "posix", reason="V2 signatures require root-owned POSIX key paths")
@pytest.mark.parametrize("failure", ["missing_providers", "wrong_peer", "wrong_record_id", "changed_tuple"])
def test_supervisor_v2_comparison_fails_closed_before_any_issuance(
    synthetic_root_keys, failure: str,
):
    case = _signed_store_fixture(synthetic_root_keys)
    try:
        peer = _issuer_peer()
        if failure == "missing_providers":
            case["supervisor"].machine_delegation_policy_provider = None
        elif failure == "wrong_peer":
            peer = _issuer_peer(uid=982)
        elif failure == "wrong_record_id":
            case["supervisor"].machine_assignment_authorization_provider = lambda _identifier: {
                **case["record"], "authorization_id": "different-auth-v2",
            }
        else:
            changed = copy.deepcopy(case["record"])
            changed["epoch"] += 1
            _sign(changed, private_path=case["keys"]["authorization"]["private"],
                  purpose=auth.ASSIGNMENT_PURPOSE_V2)
            case["supervisor"].machine_assignment_authorization_provider = lambda _identifier: copy.deepcopy(changed)
        with pytest.raises(StoreError):
            case["supervisor"].verify_machine_assignment_authorization_v2(
                case["record"]["authorization_id"], peer=peer,
            )
    finally:
        case["store"].close()
