"""S2 Store-level regressions for durable idempotent operations and breaker replay."""

import json

import pytest

from tools.vst.signing import OPERATOR_MANUAL_OVERRIDE_LABEL, sign
from tools.vst.store import Store, StoreError
from tools.vst.supervisor import Supervisor
from tests.vst.e1e4_helpers import OPERATOR_KEY


EVENT = b"s2-test-event-key-0123456789-abcdef"


def _manual_override_record(episode_id, config_id="breaker-config-v1", *, record_id="override-1", verdict="REVIEW_REQUIRED"):
    body = {
        "id": record_id,
        "action": "manual_override",
        "breaker_state": "PAUSED_PROVIDER",
        "breaker_episode_id": episode_id,
        "breaker_config_id": config_id,
        "verdict": verdict,
        "evidence_sha256": "d" * 64,
    }
    return {**body, "signature": sign(body, OPERATOR_KEY, OPERATOR_MANUAL_OVERRIDE_LABEL)}


def _paused_supervisor(path, *, record_sink):
    store = Store(str(path), event_key=EVENT)
    supervisor = Supervisor(
        store, operation_backend=object(), failure_threshold=2,
        manual_override_recorder=record_sink, operator_key=OPERATOR_KEY,
    )
    supervisor.provider_failed("override-episode-failure-1")
    supervisor.provider_failed("override-episode-failure-2")
    return store, supervisor


def test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart(tmp_path):
    recorded = []
    db_path = tmp_path / "breaker.db"
    store, supervisor = _paused_supervisor(db_path, record_sink=recorded.append)
    try:
        original = _manual_override_record("override-episode-failure-2")
        supervisor.manual_override(original)
        supervisor.provider_failed("override-episode-failure-3")
        supervisor.provider_failed("override-episode-failure-4")
        assert supervisor.breaker_state == "PAUSED_PROVIDER"
    finally:
        store.close()

    restarted_store = Store(str(db_path), event_key=EVENT)
    restarted = Supervisor(
        restarted_store, operation_backend=object(), failure_threshold=2,
        manual_override_recorder=recorded.append, operator_key=OPERATOR_KEY,
    )
    changed = _manual_override_record(
        "override-episode-failure-4", record_id=original["id"],
        verdict="REVIEW_DEFERRED",
    )
    try:
        with pytest.raises(StoreError, match="completed manual override action id reused with a different record"):
            restarted.manual_override(changed)
        assert recorded == [original]
        assert restarted.breaker_state == "PAUSED_PROVIDER"
    finally:
        restarted_store.close()


def test_external_operation_intent_and_completion_are_committed_around_callback(tmp_path):
    with Store(str(tmp_path / "intent.db"), event_key=EVENT) as store:
        observed = {}

        def effect():
            assert not store._conn.in_transaction
            row = store._conn.execute(
                "SELECT result FROM supervisor_operations WHERE operation_key = ?",
                ("push-intent-outside-tx",),
            ).fetchone()
            observed["pending"] = json.loads(row["result"])
            return {"head": "a" * 40}

        result = store.execute_external_idempotent(
            "push-intent-outside-tx", "push", {"head": "a" * 40}, effect,
        )
        assert result == {"head": "a" * 40}
        assert observed["pending"] == {"_vst_state": "PENDING"}
        events = [
            json.loads(row["payload"])
            for row in store._conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND kind = 'NOTE' ORDER BY seq",
                ("push-intent-outside-tx",),
            ).fetchall()
        ]
        assert [event["event"] for event in events] == [
            "SUPERVISOR_EXTERNAL_OPERATION_INTENT",
            "SUPERVISOR_EXTERNAL_OPERATION_COMPLETED",
        ]


def test_external_operation_timeout_stays_pending_and_same_key_payload_recovers(tmp_path):
    class RetryBackend:
        def __init__(self):
            self.calls = []

        def push(self, payload, *, operation_key):
            self.calls.append((operation_key, dict(payload)))
            if len(self.calls) == 1:
                raise TimeoutError("synthetic backend timeout")
            return {"head": payload["head"]}

    backend = RetryBackend()
    with Store(str(tmp_path / "retry.db"), event_key=EVENT) as store:
        supervisor = Supervisor(store, operation_backend=backend)
        payload = {"branch": "s2-candidate", "head": "b" * 40}

        with pytest.raises(TimeoutError, match="synthetic backend timeout"):
            supervisor.simulate_push("push-recover-1", payload)

        row = store._conn.execute(
            "SELECT result FROM supervisor_operations WHERE operation_key = ?",
            ("push-recover-1",),
        ).fetchone()
        assert json.loads(row["result"]) == {"_vst_state": "PENDING"}
        rows = store._conn.execute(
            "SELECT payload FROM events WHERE task_id = ? AND kind = 'NOTE' ORDER BY seq",
            ("push-recover-1",),
        ).fetchall()
        pending_events = [json.loads(row["payload"]) for row in rows]
        assert [event["event"] for event in pending_events] == [
            "SUPERVISOR_EXTERNAL_OPERATION_INTENT",
            "SUPERVISOR_EXTERNAL_OPERATION_UNKNOWN",
        ]
        assert pending_events[0]["state"] == "PENDING"

        with pytest.raises(StoreError, match="idempotency key reused with different operation or payload"):
            supervisor.simulate_push("push-recover-1", {"branch": "other", "head": payload["head"]})
        assert len(backend.calls) == 1

        expected = {"head": payload["head"]}
        assert supervisor.simulate_push("push-recover-1", payload) == expected
        assert supervisor.simulate_push("push-recover-1", payload) == expected
        assert backend.calls == [("push-recover-1", payload), ("push-recover-1", payload)]

        completed = [
            json.loads(row["payload"])
            for row in store._conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND kind = 'NOTE' ORDER BY seq",
                ("push-recover-1",),
            ).fetchall()
        ]
        intents = [event for event in completed if event["event"] == "SUPERVISOR_EXTERNAL_OPERATION_INTENT"]
        completions = [event for event in completed if event["event"] == "SUPERVISOR_EXTERNAL_OPERATION_COMPLETED"]
        assert [event["attempt"] for event in intents] == [1, 2]
        assert len(completions) == 1 and completions[0]["result"] == expected


def test_completed_legacy_idempotent_operation_remains_replayable(tmp_path):
    with Store(str(tmp_path / "legacy.db"), event_key=EVENT) as store:
        payload = {"branch": "legacy", "head": "c" * 40}
        legacy = {"legacy_result": "already committed"}
        assert store.execute_idempotent(
            "legacy-push-1", "push", payload, lambda _conn: legacy,
        ) == legacy

        effects = []
        assert store.execute_external_idempotent(
            "legacy-push-1", "push", payload,
            lambda: effects.append(True) or {"unexpected": "new effect"},
        ) == legacy
        assert effects == []
