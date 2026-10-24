"""S2 runner boundary and supervisor lifecycle journeys."""
from __future__ import annotations

import os
import hashlib
import inspect
import json
import sqlite3
import struct
import subprocess
import threading

import pytest

from tools.vst import contracts
from tools.vst.lifecycle import STOP_TRANSITIONS, transition
from tools.vst.runner import _derive_head, run_manifest_commands
from tools.vst.signer import AuthenticatedSigner, validate_signing_request
from tools.vst.signing import (
    DIFF_GATE_LABEL, RECEIPT_V2_LABEL, REVIEWER_LABEL, REVIEWER_REGISTRY_LABEL,
    SIGNING_REQUEST_LABEL, sign, verify,
)
from tools.vst.supervisor import Supervisor
from tools.vst.store import Store, StoreError
from tests.vst.e1e4_helpers import (
    EVENT_KEY, KEY, OPERATOR_KEY, SUPERVISOR_KEY, TASK,
    manifest as base_manifest, unsigned_receipt,
)


KEY = b"s2-test-runner-key-0123456789-abcdef"
EVENT = b"s2-test-event-key-0123456789-abcdef"
SIGNER_KEY = b"s2-test-isolated-signer-key-0123456789"


class Backend:
    def __init__(self, remote: str, repo: str | None = None):
        self.remote = remote
        self.repo = repo
        self.calls: list[tuple[str, str]] = []

    def push(self, payload: dict, *, operation_key: str):
        self.calls.append(("push", operation_key))
        if self.repo is None:
            raise AssertionError("local synthetic repo is required to populate bare remote objects")
        subprocess.run(["git", "-C", self.repo, "push", self.remote,
                        f"{payload['head']}:refs/heads/{payload['branch']}"], check=True, capture_output=True)
        return {"head": payload["head"]}

    def open_pull_request(self, payload: dict, *, operation_key: str):
        self.calls.append(("pull_request", operation_key))
        return {"number": len(self.calls), **payload}


def git(*args: str, cwd: str | None = None) -> str:
    result = subprocess.run(["git", *( ["-C", cwd] if cwd else []), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def test_lifecycle_transition_table_rejects_unlisted_pairs():
    assert set(STOP_TRANSITIONS) == {
        ("RUNNING", "STOP"), ("STOPPING", "CLEANUP_COMPLETE"),
        ("STOPPED", "RESUME"), ("RUNNING", "ROLLBACK"),
        ("ROLLING_BACK", "CLEANUP_COMPLETE"), ("READY", "START"),
    }
    for (state, event), row in STOP_TRANSITIONS.items():
        next_state, cleanup = transition(state, event)
        assert (next_state, cleanup) == (row["next_state"], row["cleanup_action"])
        assert row["trigger"] == "supervisor"
    with pytest.raises(ValueError, match="unsupported lifecycle transition"):
        transition("READY", "STOP")


def test_breaker_blocks_start_until_distinct_manual_override(tmp_path):
    db = tmp_path / "state.db"
    with Store(str(db), event_key=EVENT) as store:
        backend = Backend(str(tmp_path / "remote.git"))
        recorded = []
        supervisor = Supervisor(store, operation_backend=backend, failure_threshold=2,
                                manual_override_recorder=recorded.append)
        supervisor.provider_failed()
        supervisor.provider_failed()
        started = []
        with pytest.raises(StoreError, match="breaker is open"):
            supervisor.start_worker(lambda: started.append(True))
        assert not started
        with pytest.raises(StoreError, match="plain APPROVE"):
            supervisor.manual_override({"record_id": "override-1", "verdict": "APPROVE"})
        supervisor.manual_override({"record_id": "override-1", "verdict": "REVIEW_REQUIRED"})
        assert recorded == [{"record_id": "override-1", "verdict": "REVIEW_REQUIRED"}]
        assert supervisor.start_worker(lambda: "started") == "started"


def test_idempotent_push_and_pull_request_use_local_bare_remote(tmp_path):
    remote, repo = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repo.mkdir()
    git("init", cwd=str(repo))
    git("config", "user.name", "Synthetic", cwd=str(repo))
    git("config", "user.email", "synthetic@example.invalid", cwd=str(repo))
    (repo / "note.txt").write_text("synthetic\n", encoding="utf-8")
    git("add", "note.txt", cwd=str(repo)); git("commit", "-m", "synthetic", cwd=str(repo))
    head = git("rev-parse", "HEAD", cwd=str(repo))
    with Store(str(tmp_path / "state.db"), event_key=EVENT) as store:
        backend = Backend(str(remote), str(repo))
        supervisor = Supervisor(store, operation_backend=backend)
        payload = {"branch": "s2-candidate", "head": head}
        first = supervisor.simulate_push("push-1", payload)
        again = supervisor.simulate_push("push-1", payload)
        assert first == again and backend.calls == [("push", "push-1")]
        assert git("--git-dir", str(remote), "rev-parse", "refs/heads/s2-candidate") == head
        pr = {"head": head, "title": "Synthetic"}
        assert supervisor.simulate_pull_request("pr-1", pr) == supervisor.simulate_pull_request("pr-1", pr)
        assert [kind for kind, _ in backend.calls] == ["push", "pull_request"]
        with pytest.raises(StoreError):
            supervisor.simulate_push("push-1", {"branch": "other", "head": head})


def test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides(tmp_path):
    repo = tmp_path / "synthetic-repo"
    repo.mkdir()
    git("init", cwd=str(repo))
    git("config", "user.name", "Synthetic", cwd=str(repo))
    git("config", "user.email", "synthetic@example.invalid", cwd=str(repo))
    observed = []
    for index in range(3):
        (repo / "candidate.txt").write_text(f"candidate-{index}\n", encoding="utf-8")
        git("add", "candidate.txt", cwd=str(repo))
        git("commit", "-m", f"candidate {index}", cwd=str(repo))
        observed.append(_derive_head(str(repo)))
    assert len(set(observed)) == 3
    assert all(git("cat-file", "-t", head, cwd=str(repo)) == "commit" for head in observed)
    api = inspect.signature(run_manifest_commands).parameters
    assert "manifest" in api and "cwd" in api
    for forbidden in ("candidate_head", "commands", "parser", "test_result_parser", "key", "signing_key"):
        assert forbidden not in api
    assert all(len(head) == 40 for head in observed)


@pytest.mark.parametrize("override", ["candidate_head", "commands", "parser", "test_result_parser", "key", "signing_key"])
def test_runner_rejects_caller_supplied_head_parser_key_or_commands(override):
    arguments = {
        "manifest": {}, "slot": "tests", "attempt": 1, "epoch": 1,
        "resolved_model": "synthetic", "invocation_id": "inv-1", "runner_id": "runner-1",
        "signer_socket": "unused", "cwd": ".", "worker_uid": 1, "worker_gid": 1,
        "created_at": "2026-10-24T00:00:00Z",
    }
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        run_manifest_commands(**arguments, **{override: object()})


class _RequestConnection:
    """In-process protocol peer; this does not model or claim OS identity isolation."""

    def __init__(self, payload: bytes, uid: int = 4242):
        self.chunks = [payload, b""]
        self.uid = uid
        self.response = b""

    def getsockopt(self, _level, _option, _size):
        return struct.pack("3i", 101, self.uid, 4242)

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""

    def sendall(self, response: bytes):
        self.response = response


def _signer_protocol_request(request_id="request-1", candidate_head="a" * 40):
    parser_id, parser_version, parser_sha = next(iter(contracts.TRUSTED_PARSER_CATALOG))
    argv = ["python", "-c", "print('PASS t1')"]
    return {
        "request_id": request_id,
        "task_id": "task-1",
        "slot": "tests",
        "attempt": 1,
        "epoch": 1,
        "manifest_sha256": "b" * 64,
        "candidate_head": candidate_head,
        "commands": [{"argv": argv, "exit_code": 0}],
        "parser_results": [{
            "argv": argv, "parser_id": parser_id, "parser_version": parser_version,
            "parser_sha256": parser_sha,
            "parser_result": {"executed_test_ids": ["t1"], "skipped_test_ids": [], "xfail_test_ids": []},
        }],
        "artifact_digests": {},
    }


def _handle_signer_protocol(monkeypatch, server, request):
    import tools.vst.signer as signer_module

    monkeypatch.setattr(signer_module.socket, "SO_PEERCRED", 1, raising=False)
    connection = _RequestConnection(json.dumps(request).encode("utf-8"))
    server._handle(connection)
    return json.loads(connection.response)


def test_signing_request_exact_schema_and_replay_protocol_without_os_claim(monkeypatch):
    server = object.__new__(AuthenticatedSigner)
    server.runner_uid = 4242
    server.key = SIGNER_KEY
    server._ledger = sqlite3.connect(":memory:")
    server._ledger.execute("CREATE TABLE requests (request_id TEXT PRIMARY KEY, payload BLOB NOT NULL, signature TEXT NOT NULL)")
    server._lock = threading.Lock()
    request = _signer_protocol_request()
    assert set(validate_signing_request(request)) == {
        "request_id", "task_id", "slot", "attempt", "epoch", "manifest_sha256",
        "candidate_head", "commands", "parser_results", "artifact_digests",
    }
    first = _handle_signer_protocol(monkeypatch, server, request)
    replay = _handle_signer_protocol(monkeypatch, server, request)
    assert set(first) == {"signature"} and first == replay
    assert verify({**request, "signature": first["signature"]}, SIGNER_KEY, SIGNING_REQUEST_LABEL)
    assert server._ledger.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
    changed = {**request, "candidate_head": "c" * 40}
    rejected = _handle_signer_protocol(monkeypatch, server, changed)
    assert rejected.get("error") == "invalid_request"
    assert "different payload" in rejected.get("detail", "")
    assert server._ledger.execute("SELECT COUNT(*) FROM requests").fetchone()[0] == 1
    malformed = {**request, "unexpected": True, "request_id": "bad-request"}
    assert _handle_signer_protocol(monkeypatch, server, malformed).get("error") == "invalid_request"
    server._ledger.close()


@pytest.mark.parametrize("mutation", [
    lambda request: request.pop("candidate_head"),
    lambda request: request.update(epoch=True),
    lambda request: request["commands"][0].update(argv=["python", "-c", "different"]),
    lambda request: request["parser_results"][0].update(parser_sha256="0" * 64),
])
def test_signer_rejects_malformed_signing_evidence(mutation):
    request = _signer_protocol_request("malformed")
    mutation(request)
    with pytest.raises(contracts.ContractError):
        validate_signing_request(request)


def _authority_fixture():
    reviewer_key = b"s2-reviewer-authority-key-0123456789"
    entries = [{"principal": "reviewer-x", "key_id": "reviewer-key-1"}]
    registry_body = {"version": "registry-1", "entries": entries}
    registry = {
        **registry_body,
        "signature": sign(registry_body, OPERATOR_KEY, REVIEWER_REGISTRY_LABEL),
    }
    m = base_manifest(required_receipts=[
        {"slot": "tests", "receipt_type": "TestRun"},
        {"slot": "static", "receipt_type": "StaticAnalysis"},
        {"slot": "review", "receipt_type": "IndependentReview"},
        {"slot": "doc", "receipt_type": "Documentation"},
    ])
    m.update({
        "contract_version": 2,
        "reviewer_registry": {
            "version": "registry-1",
            "sha256": hashlib.sha256(contracts.canonical_bytes(registry_body)).hexdigest(),
        },
        "mandatory_commands": [{
            "slot": "tests", "argv": ["pytest", "-q"],
            "parser_id": "vst.pass-lines", "parser_version": "1",
            "parser_sha256": next(iter(contracts.TRUSTED_PARSER_CATALOG))[2],
        }],
        "change_scope": {"allowed_paths": ["src/app.py", "tests/test_app.py"]},
    })
    keys = {
        "worker": KEY,
        "supervisor": SUPERVISOR_KEY,
        "operator": OPERATOR_KEY,
        "event": EVENT_KEY,
        "signer": SIGNER_KEY,
        "reviewer": reviewer_key,
    }
    return m, registry, reviewer_key, keys


def _authority_receipt(receipt_type, slot, signing_key, manifest_obj, reviewer_key_id="reviewer-key-1"):
    manifest_sha = contracts.manifest_sha256(manifest_obj)
    candidate = unsigned_receipt(
        receipt_type,
        contract_version=2,
        task_id=TASK,
        manifest_sha256=manifest_sha,
        slot=slot,
        candidate_head="a" * 40,
        epoch=2,
    )
    if receipt_type == "IndependentReview":
        candidate["reviewer_key_id"] = reviewer_key_id
    elif receipt_type == "TestRun":
        parser_id, parser_version, parser_sha = next(iter(contracts.TRUSTED_PARSER_CATALOG))
        argv = ["pytest", "-q"]
        parser_result = {
            "executed_test_ids": ["t1", "t2"],
            "skipped_test_ids": [], "xfail_test_ids": [],
        }
        parser_results = [{
            "argv": argv, "parser_id": parser_id, "parser_version": parser_version,
            "parser_sha256": parser_sha, "parser_result": parser_result,
        }]
        request = {
            "request_id": "authority-request", "task_id": TASK, "slot": slot,
            "attempt": 1, "epoch": 2, "manifest_sha256": manifest_sha,
            "candidate_head": "a" * 40,
            "commands": [{"argv": argv, "exit_code": 0}],
            "parser_results": parser_results, "artifact_digests": {},
        }
        request_signature = sign(request, signing_key, SIGNING_REQUEST_LABEL)
        diff_body = {
            "manifest_sha256": manifest_sha, "candidate_head": "a" * 40,
            "diff_sha256": "d" * 64, "changed_paths": [],
            "verdict": "PASS", "reason": "PASS",
        }
        diff_gate = {
            **diff_body,
            "signature": sign(diff_body, SIGNER_KEY, DIFF_GATE_LABEL),
        }
        candidate.update({
            "parser_results": parser_results,
            "diff_gate": diff_gate,
            "runner_attestation": {"request": request, "signature": request_signature},
            "signature": request_signature,
        })
        return candidate
    signature_label = REVIEWER_LABEL if receipt_type == "IndependentReview" else RECEIPT_V2_LABEL
    candidate["signature"] = sign(candidate, signing_key, signature_label)
    return candidate


def _gate_authority_check(receipt_obj, manifest_obj, registry, reviewer_key):
    from tools.vst import gate

    decision = gate.evaluate(
        manifest_obj, [receipt_obj], "a" * 40, 2, KEY,
        supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
        reviewer_registry=registry, reviewer_keys={"reviewer-key-1": reviewer_key},
        signer_key=SIGNER_KEY, event_key=EVENT_KEY,
    )
    return decision["reasons"]


@pytest.mark.parametrize("receipt_type,slot,allowed_key", [
    ("TestRun", "tests", "signer"),
    ("IndependentReview", "review", "reviewer"),
    ("StaticAnalysis", "static", "worker"),
    ("Documentation", "doc", "worker"),
    ("Documentation", "__supervisor__", "supervisor"),
])
@pytest.mark.parametrize("key_kind", ["worker", "supervisor", "operator", "event", "signer", "reviewer"])
def test_gate_routes_each_v2_receipt_to_its_designated_authority(receipt_type, slot, allowed_key, key_kind):
    m, registry, reviewer_key, keys = _authority_fixture()
    candidate = _authority_receipt(receipt_type, slot, keys[key_kind], m)
    reasons = _gate_authority_check(candidate, m, registry, reviewer_key)
    invalid_signature = any("invalid signature" in reason for reason in reasons)
    assert invalid_signature is (key_kind != allowed_key)


@pytest.mark.skip(reason="NOT_RUN: real worker identity/key-file/signer-IPC boundary requires the operator-provisioned POSIX sandbox; OS identity must not be synthesized")
def test_posix_worker_cannot_read_signer_or_key_file():
    pytest.fail("A POSIX sandbox must be provisioned before this boundary test can run")


@pytest.mark.parametrize("scenario", [
    "posix_process_group_cleanup",
    "post_exit_descendant_cleanup",
    "key_file_permissions_for_worker_identity",
    "windows_parent_job_nesting",
])
@pytest.mark.skip(reason="NOT_RUN: E4 platform containment requires the provisioned POSIX sandbox or an authorized nested Windows Job Object host; process-kill/kill-table execution is explicitly prohibited")
def test_e4_platform_containment_scenarios_not_run(scenario):
    pytest.skip(scenario)

