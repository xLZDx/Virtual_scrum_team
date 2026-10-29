"""TP-29–TP-32: disposable Store boundary for fresh S2 assignments.

These tests prove source/SQLite fixture behavior only; seeded fixture state is not
evidence of process-crash recovery or production authentication.
"""
from __future__ import annotations

import copy
from pathlib import Path
import pytest

from tools.vst import contracts
from tools.vst.assignment_basis import POLICY_SCHEMA, validate_policy
from tools.vst.store import Store, StoreError
from tests.vst.e1e4_helpers import (
    EVENT_KEY, KEY, SUPERVISOR_KEY, bound, manifest as base_manifest,
    supervisor_receipt,
)

NOW = 1_793_275_200.0  # 2026-10-29 12:00:00 UTC
RUN = "bootstrap-run-1"
GENERATION = "bootstrap-generation-1"


def _fresh_fixture(*, cost_cap: int = 0, anchor_path: str | None = None,
                   store_path: str = ":memory:"):
    manifest = base_manifest(task_id="T-bootstrap-fresh", story_id="S2-bootstrap-fresh",
                             cost_cap=cost_cap, retry_cap=1)
    policy = {
        "schema": POLICY_SCHEMA, "policy_id": "policy-bootstrap-1",
        "repository": "Virtual_scrum_team", "sprint_id": "39b7cc253f5d",
        "source_head": "a" * 40, "manifest_sha256": "b" * 64,
        "owner_principal": "Codex",
        "allowed_assignments": [{
            "story_id": manifest["story_id"], "task_id": manifest["task_id"],
            "project_id": manifest["project_id"], "phase": manifest["phase"],
            "task_manifest_sha256": contracts.manifest_sha256(manifest),
            "test_run_slots": ["tests"],
        }],
        "bootstrap_peer": {"role": "assignment_bootstrap", "uid": 980, "gid": 982,
                           "cgroup": "/system.slice/vst-assignment-bootstrap.service"},
        "issuer_peer": {"role": "delegated_issuer", "uid": 981, "gid": 983,
                         "cgroup": "/system.slice/vst-delegated-issuer.service"},
        "allowed_bootstrap_operations": ["open_story", "register_task", "acquire_epoch", "acquire_lease"],
        "maximum_handoff_ttl_seconds": 300,
        "valid_from_utc": "2026-10-29T11:00:00Z", "expires_at_utc": "2026-10-29T13:00:00Z",
        "revocation_id": "bootstrap-revocation-1", "runner_id": "runner-bootstrap-1",
        "owner_ttl_seconds": 1800, "lease_ttl_seconds": 1200,
    }
    normalized_policy, policy_sha = validate_policy(policy)
    store = Store(store_path, clock=lambda: NOW, event_key=EVENT_KEY, anchor_path=anchor_path)
    store.init_slots(1)
    store.ensure_preflight_consumed(RUN, "bootstrap-nonce", "d" * 64, "c" * 64)
    request = {
        "schema": "VST_S2_ASSIGNMENT_BOOTSTRAP_REQUEST_V1",
        "request_id": "0123456789abcdef0123456789abcdef",
        "story_id": manifest["story_id"], "task_id": manifest["task_id"],
        "task_manifest": manifest, "slot": "tests", "attempt": 1, "run_id": RUN,
    }
    peer = normalized_policy["bootstrap_peer"]
    providers = {"policy_provider": lambda: normalized_policy,
                 "generation_provider": lambda: GENERATION}
    def invoke(req=request):
        return store.bootstrap_assignment(
            req, policy=normalized_policy, policy_sha256=policy_sha,
            bootstrap_peer=peer, expected_run_id=RUN,
            active_service_generation=GENERATION, **providers,
        )
    return store, manifest, normalized_policy, request, invoke


def _snapshot(store: Store) -> tuple:
    with store._read_tx() as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        return tuple((table, tuple(tuple(row) for row in conn.execute(f'SELECT * FROM "{table}"')))
                     for table in tables)


def test_fresh_bootstrap_commits_one_complete_epoch_two_zero_budget_handoff():
    store, manifest, _policy, request, invoke = _fresh_fixture(cost_cap=0)
    try:
        handoff = invoke()
        assert handoff["task_id"] == request["task_id"]
        assert handoff["attempt"] == 1 and handoff["epoch"] == 2
        assert handoff["service_generation"] == GENERATION
        with store._read_tx() as conn:
            story = conn.execute("SELECT epoch, owner FROM stories WHERE story_id=?",
                                 (manifest["story_id"],)).fetchone()
            task = conn.execute("SELECT task_id FROM tasks WHERE task_id=?",
                                (manifest["task_id"],)).fetchone()
            budget = conn.execute("SELECT cap, spent FROM budget WHERE task_id=?",
                                  (manifest["task_id"],)).fetchone()
            lease = conn.execute("SELECT attempt, epoch, status FROM leases WHERE task_id=?",
                                 (manifest["task_id"],)).fetchone()
            handoffs = conn.execute("SELECT COUNT(*) FROM supervisor_operations WHERE operation=?",
                                    ("VST_S2_AUTHENTICATED_ASSIGNMENT_V1",)).fetchone()[0]
            linked = conn.execute("SELECT COUNT(*) FROM events WHERE task_id=? AND actor='supervisor' AND kind='NOTE'",
                                  (handoff["assignment_operation_id"],)).fetchone()[0]
        assert tuple(story) == (2, "Codex")
        assert task["task_id"] == manifest["task_id"]
        assert tuple(budget) == (0, 0)
        assert tuple(lease) == (1, 2, "LIVE")
        assert handoffs == linked == 1
    finally:
        store.close()


def test_exact_bootstrap_replay_returns_same_bytes_and_conflicting_payload_has_no_effect():
    store, _manifest, _policy, request, invoke = _fresh_fixture()
    try:
        first = invoke()
        before = _snapshot(store)
        assert invoke() == first
        assert _snapshot(store) == before
        changed = copy.deepcopy(request)
        changed["request_id"] = "f" * 32
        with pytest.raises(StoreError):
            invoke(changed)
        assert _snapshot(store) == before
    finally:
        store.close()


def test_precommit_exception_rolls_back_every_assignment_row_event_and_anchor(monkeypatch, tmp_path):
    anchor = str(tmp_path / "anchor.json")
    database = str(tmp_path / "store.sqlite3")
    store, _manifest, _policy, _request, invoke = _fresh_fixture(
        anchor_path=anchor, store_path=database,
    )
    before = _snapshot(store)
    anchor_before = Path(anchor).read_bytes()
    original = store._acquire_initial_assignment_lease_locked
    def fail_after_story_task_epoch_and_budget(*args, **kwargs):
        raise RuntimeError("injected ordinary precommit failure")
    monkeypatch.setattr(store, "_acquire_initial_assignment_lease_locked",
                        fail_after_story_task_epoch_and_budget)
    try:
        with pytest.raises(RuntimeError, match="injected ordinary precommit failure"):
            invoke()
        assert _snapshot(store) == before
        assert Path(anchor).read_bytes() == anchor_before
        monkeypatch.setattr(store, "_acquire_initial_assignment_lease_locked", original)
        result = invoke()
        assert result["epoch"] == 2
    finally:
        store.close()


@pytest.mark.parametrize("history", [
    "story", "task", "event", "budget", "lease", "receipt", "terminal", "handoff",
])
def test_bootstrap_rejects_prior_assignment_history_without_adopting_it(history: str):
    store, manifest, _policy, _request, invoke = _fresh_fixture()
    try:
        if history == "story":
            store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
        elif history == "task":
            store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
            store.register_task(manifest)
        elif history == "event":
            with store._tx() as conn:
                store._record_event_locked(conn, manifest["task_id"], "Codex", "NOTE", {"prior": True})
        elif history == "budget":
            store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
            store.register_task(manifest)
        elif history == "lease":
            store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
            epoch = store.acquire_epoch(manifest["story_id"], "Codex", ttl_sec=1800)
            store.register_task(manifest)
            store.acquire_lease(manifest["task_id"], manifest["story_id"], "runner-bootstrap-1",
                                epoch, 1, 1200, supervisor_key=SUPERVISOR_KEY)
        elif history in {"receipt", "terminal"}:
            store.open_story(manifest["story_id"], manifest["project_id"], manifest["phase"])
            epoch = store.acquire_epoch(manifest["story_id"], "Codex", ttl_sec=1800)
            store.register_task(manifest)
            if history == "receipt":
                store.acquire_lease(manifest["task_id"], manifest["story_id"], "runner-bootstrap-1",
                                    epoch, 1, 1200, supervisor_key=SUPERVISOR_KEY)
                receipt = bound(
                    manifest, key=KEY, task_id=manifest["task_id"],
                    epoch=epoch, attempt=1, runner_id="runner-bootstrap-1",
                    slot="tests", receipt_type="TestRun",
                )
                store.append_receipt(receipt, manifest["story_id"], KEY)
            else:
                marker = supervisor_receipt(
                    "RETRY_EXHAUSTED", task_id=manifest["task_id"],
                    manifest_sha256=contracts.manifest_sha256(manifest),
                    role_sha256=manifest["role_sha256"], epoch=epoch,
                )
                store.append_supervisor_receipt(marker, manifest["story_id"],
                                                supervisor_key=SUPERVISOR_KEY)
        elif history == "handoff":
            prior = invoke()
            changed = copy.deepcopy(_request)
            changed["request_id"] = "f" * 32
            before = _snapshot(store)
            with pytest.raises(StoreError):
                invoke(changed)
            assert prior["task_id"] == manifest["task_id"]
            assert _snapshot(store) == before
            return
        before = _snapshot(store)
        with pytest.raises(StoreError):
            invoke()
        assert _snapshot(store) == before
    finally:
        store.close()


def test_over_cap_budget_injection_rolls_back_partial_assignment(monkeypatch):
    store, _manifest, _policy, _request, invoke = _fresh_fixture(cost_cap=2)
    before = _snapshot(store)
    original = store._register_task_locked

    def register_with_over_cap_spend(conn, task_manifest, digest):
        result = original(conn, task_manifest, digest)
        conn.execute("UPDATE budget SET spent=cap+1 WHERE task_id=?", (task_manifest["task_id"],))
        return result

    monkeypatch.setattr(store, "_register_task_locked", register_with_over_cap_spend)
    try:
        with pytest.raises(StoreError, match="budget does not match its pinned manifest"):
            invoke()
        assert _snapshot(store) == before
    finally:
        store.close()


def test_retry_exhausted_terminal_marker_refuses_and_rolls_back_partial_assignment(monkeypatch):
    store, _manifest, _policy, _request, invoke = _fresh_fixture()
    before = _snapshot(store)
    original = store._register_task_locked

    def register_with_retry_terminal(conn, task_manifest, digest):
        result = original(conn, task_manifest, digest)
        task = store._task_row(conn, task_manifest["task_id"])
        store._supervisor_marker_locked(
            conn, task, "RETRY_EXHAUSTED", SUPERVISOR_KEY, "synthetic-supervisor",
            "bootstrap-retry-exhausted-fixture",
        )
        return result

    monkeypatch.setattr(store, "_register_task_locked", register_with_retry_terminal)
    try:
        # Fresh-only eligibility rejects the marker receipt as prior receipt history
        # before the lower lease helper reaches its terminal-marker branch.
        with pytest.raises(StoreError):
            invoke()
        assert _snapshot(store) == before
    finally:
        store.close()


def test_occupied_runner_slot_refuses_bootstrap_without_partial_assignment():
    store, target_manifest, _policy, _request, invoke = _fresh_fixture()
    other = base_manifest(task_id="T-bootstrap-slot-holder", story_id="S2-bootstrap-slot-holder")
    try:
        store.open_story(other["story_id"], other["project_id"], other["phase"])
        epoch = store.acquire_epoch(other["story_id"], "Codex", ttl_sec=1800)
        store.register_task(other)
        store.acquire_lease(other["task_id"], other["story_id"], "runner-slot-holder",
                            epoch, 1, 1200, supervisor_key=SUPERVISOR_KEY)
        before = _snapshot(store)
        with pytest.raises(StoreError, match="no free slot"):
            invoke()
        assert _snapshot(store) == before
        assert store._conn.execute("SELECT 1 FROM tasks WHERE task_id=?",
                                   (target_manifest["task_id"],)).fetchone() is None
    finally:
        store.close()


def test_noninitial_attempt_and_boolean_attempt_refuse_without_writes():
    store, _manifest, _policy, request, invoke = _fresh_fixture()
    try:
        before = _snapshot(store)
        for attempt in (2, True):
            changed = copy.deepcopy(request)
            changed["attempt"] = attempt
            with pytest.raises((StoreError, ValueError)):
                invoke(changed)
            assert _snapshot(store) == before
    finally:
        store.close()
