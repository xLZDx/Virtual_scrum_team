"""Trusted supervisor boundary for synthetic worker lifecycle operations."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Callable

from .contracts import canonical_bytes
from .lifecycle import STOP_TRANSITIONS, transition
from .signing import OPERATOR_MANUAL_OVERRIDE_LABEL, verify
from .store import ACTION_RESOLUTION_LABEL, Store, StoreError

_LIFECYCLE_ACTIONS = {"start", "stop_terminate", "stop_cleanup", "rollback_effect", "rollback_cleanup", "resume"}


def _valid_sha256(value: Any) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


class Supervisor:
    """Coordinates lifecycle and synthetic operations; worker gets no push route."""

    def __init__(
        self,
        store: Store,
        *,
        operation_backend: Any,
        failure_threshold: int = 3,
        manual_override_recorder: Callable[[dict], None] | None = None,
        run_id: str | None = None,
        probe_nonce: str | None = None,
        probe_key: bytes | None = None,
        operator_key: bytes | None = None,
    ):
        if isinstance(failure_threshold, bool) or not isinstance(failure_threshold, int) or failure_threshold < 1:
            raise ValueError("failure_threshold must be a positive integer")
        self.store = store
        self.backend = operation_backend
        self.failure_threshold = failure_threshold
        self.manual_override_recorder = manual_override_recorder
        self.run_id = run_id
        self.probe_nonce = probe_nonce
        self.probe_key = probe_key
        self.operator_key = operator_key
        self._seen_run_ids = {run_id} if isinstance(run_id, str) else set()
        self._seen_probe_nonces = {probe_nonce} if isinstance(probe_nonce, str) else set()
        self._probe_consumed = False
        if store.sandbox_mode and (
            not isinstance(run_id, str) or not run_id.strip()
            or not isinstance(probe_nonce, str) or not probe_nonce.strip()
            or not isinstance(probe_key, (bytes, bytearray)) or len(probe_key) < 32
            or not isinstance(operator_key, (bytes, bytearray)) or len(operator_key) < 32
            or bytes(operator_key) == bytes(probe_key)
        ):
            raise ValueError("sandbox supervisor requires trusted run id, nonce and probe verification key")
        if operator_key is not None and bytes(operator_key) == store._event_key:
            raise ValueError("operator_key must differ from the event key")
        self._action_status: dict[str, dict] = {}
        self._control_history = store.control_events()
        configs = [row for row in self._control_history if row["kind"] == "CONTROL_BREAKER_CONFIG"]
        config = {"threshold": failure_threshold, "policy": "consecutive_failures_v1"}
        if configs and configs[0].get("config") != config:
            raise StoreError("provider breaker policy differs from persisted configuration", kind="provider")
        if not configs:
            store._append_control_event("CONTROL_BREAKER_CONFIG", "breaker-config-v1", {"config": config})
            self._control_history = store.control_events()
        self._replay_controls()
        self.lifecycle_state = "READY"
        self.lifecycle_action_id: str | None = None
        for event in self._control_history:
            if event["kind"] == "CONTROL_ACTION_COMPLETED":
                action = event.get("action")
                if action == "start": self.lifecycle_state = "RUNNING"
                elif action == "stop_terminate": self.lifecycle_state = "STOPPING"
                elif action == "rollback_effect": self.lifecycle_state = "ROLLING_BACK"
                elif action in {"stop_cleanup", "rollback_cleanup"}: self.lifecycle_state = "STOPPED"
                elif action == "resume": self.lifecycle_state = "READY"
                if self.lifecycle_state in {"STOPPING", "ROLLING_BACK"}:
                    self.lifecycle_action_id = event.get("group_id")
                elif self.lifecycle_state == "STOPPED":
                    self.lifecycle_action_id = None
            if event["kind"] == "CONTROL_ACTION_INTENT":
                action_id = event.get("action_id", event["event_id"])
                status = self._action_status.get(action_id, {})
                if status.get("action") in _LIFECYCLE_ACTIONS and status.get("status") not in {"completed", "reconciled"}:
                    self.lifecycle_state = "BLOCKED_RECOVERY"
                    self.lifecycle_action_id = status.get("group_id")
            if event["kind"] == "CONTROL_ACTION_RECONCILED":
                if event.get("action") in _LIFECYCLE_ACTIONS and self._valid_resolution_event(event):
                    self._apply_reconciled_state(event["action"], event["completed"])
                    self.lifecycle_action_id = event.get("group_id") if self.lifecycle_state in {"STOPPING", "ROLLING_BACK"} else None

    def _apply_reconciled_state(self, action: str, completed: bool) -> None:
        states = {
            ("start", True): "RUNNING", ("start", False): "READY",
            ("stop_terminate", True): "STOPPING", ("stop_terminate", False): "RUNNING",
            ("stop_cleanup", True): "STOPPED", ("stop_cleanup", False): "STOPPING",
            ("rollback_effect", True): "ROLLING_BACK", ("rollback_effect", False): "RUNNING",
            ("rollback_cleanup", True): "STOPPED", ("rollback_cleanup", False): "ROLLING_BACK",
            ("resume", True): "READY", ("resume", False): "STOPPED",
        }
        self.lifecycle_state = states[(action, completed)]

    def _replay_controls(self) -> None:
        self.provider_failures = 0
        self.breaker_state = "CLOSED"
        self._action_status = {}
        for event in self._control_history:
            kind = event["kind"]
            if kind == "CONTROL_PROVIDER_FAILURE":
                self.provider_failures += 1
                if self.provider_failures >= self.failure_threshold: self.breaker_state = "PAUSED_PROVIDER"
            elif kind == "CONTROL_PROVIDER_SUCCESS":
                self.provider_failures = 0
            elif kind == "CONTROL_BREAKER_OVERRIDE":
                self.provider_failures = 0
                self.breaker_state = "CLOSED"
            elif kind in {"CONTROL_ACTION_INTENT", "CONTROL_ACTION_COMPLETED", "CONTROL_ACTION_UNKNOWN", "CONTROL_ACTION_RECONCILED"}:
                root_id = event.get("action_id", event["event_id"])
                status = kind.rsplit("_", 1)[-1].lower()
                if kind == "CONTROL_ACTION_RECONCILED" and not self._valid_resolution_event(event):
                    status = "unknown"
                self._action_status[root_id] = {"status": status, **event}

    def _valid_resolution_event(self, event: dict) -> bool:
        record = event.get("resolution_record")
        if not isinstance(self.operator_key, (bytes, bytearray)) or len(self.operator_key) < 32 or not isinstance(record, dict):
            return False
        expected_fields = {"action_id", "action", "attempt", "completed", "resolution_id", "evidence_sha256", "signature"}
        if set(record) != expected_fields or type(event.get("completed")) is not bool:
            return False
        if isinstance(record.get("attempt"), bool) or not isinstance(record.get("attempt"), int):
            return False
        if not verify(record, bytes(self.operator_key), ACTION_RESOLUTION_LABEL):
            return False
        for field in ("action_id", "action", "attempt", "completed", "resolution_id"):
            if record.get(field) != event.get(field):
                return False
        return _valid_sha256(record.get("evidence_sha256"))

    def _perform(self, action: str, callback: Callable[[], Any], action_id: str | None = None, *, group_id: str | None = None, control_data: dict | None = None) -> Any:
        action_id = action_id or str(uuid.uuid4())
        group_id = group_id or action_id
        status = self._action_status.get(action_id)
        if status:
            if status.get("action") != action:
                raise StoreError("lifecycle action id reused for a different action", kind="integrity")
            if status["status"] == "completed":
                if status.get("result_omitted"):
                    raise StoreError("action completed but its return value cannot be replayed", kind="lifecycle")
                return status.get("result")
            if status["status"] == "reconciled" and status.get("completed") is False:
                # A recorded resolution established that the effect did not occur;
                # continue under the exact same id, never mint a replacement id.
                pass
            else:
                raise StoreError("lifecycle action has an unresolved outcome; reconcile before continuing", kind="lifecycle")
        attempt = (status.get("attempt", 0) + 1) if status else 1
        event_data = {**(control_data or {}), "action": action, "action_id": action_id, "attempt": attempt}
        if group_id is not None:
            event_data["group_id"] = group_id
        begin = self.store.begin_action(
            action_id, event_data,
            resolution_key=None if self.operator_key is None else bytes(self.operator_key),
        )
        self._control_history = self.store.control_events()
        self._replay_controls()
        attempt = int(begin.get("attempt", attempt))
        event_data["attempt"] = attempt
        if begin["status"] in {"completed", "reconciled"}:
            if begin.get("status") == "reconciled" and begin.get("completed") is False:
                raise StoreError("reconciled action was not completed; continuation did not begin", kind="lifecycle")
            if begin.get("result_omitted"):
                raise StoreError("action completed but its return value cannot be replayed", kind="lifecycle")
            return begin.get("result")
        try:
            result = callback()
            completion = dict(event_data)
            try:
                canonical_bytes(result)
            except (TypeError, ValueError):
                completion["result_omitted"] = True
            else:
                completion["result"] = result
            self.store._append_control_event("CONTROL_ACTION_COMPLETED", f"{action_id}:completed:{attempt}", completion)
            self._control_history = self.store.control_events()
            self._replay_controls()
            return result
        except BaseException as exc:
            if action in _LIFECYCLE_ACTIONS:
                self.lifecycle_state = "BLOCKED_RECOVERY"
                self.lifecycle_action_id = group_id
            self.store._append_control_event("CONTROL_ACTION_UNKNOWN", f"{action_id}:unknown:{attempt}", {**event_data, "error_type": type(exc).__name__})
            self._control_history = self.store.control_events()
            self._replay_controls()
            raise

    def reconcile_action(
        self, action_id: str, *, completed: bool, resolution_id: str,
        resolution_record: dict | None = None,
    ) -> None:
        """Record an operator-signed resolution; never replays an uncertain callback."""
        if type(completed) is not bool:
            raise StoreError("completed must be an explicit boolean", kind="argument")
        if not isinstance(resolution_id, str) or not resolution_id.strip():
            raise StoreError("reconciliation requires an auditable resolution id", kind="argument")
        if not isinstance(self.operator_key, (bytes, bytearray)) or len(self.operator_key) < 32:
            raise StoreError("trusted operator key is required for lifecycle reconciliation", kind="authorization")
        current = self._action_status.get(action_id)
        if current is None:
            matches = [
                row for row in self._action_status.values()
                if row.get("group_id") == action_id and row.get("status") in {"intent", "unknown"}
            ]
            if len(matches) == 1:
                current = matches[0]
                action_id = current["action_id"]
        if not current or current["status"] not in {"intent", "unknown"}:
            raise StoreError("action is not awaiting reconciliation", kind="lifecycle")
        expected_fields = {"action_id", "action", "attempt", "completed", "resolution_id", "evidence_sha256", "signature"}
        if not isinstance(resolution_record, dict) or set(resolution_record) != expected_fields:
            raise StoreError("operator-signed reconciliation record is required", kind="authorization")
        resolution_event = {
            "action_id": action_id, "action": current["action"],
            "attempt": current.get("attempt", 1), "completed": completed,
            "resolution_id": resolution_id, "resolution_record": resolution_record,
            "group_id": current.get("group_id"),
        }
        if not verify(resolution_record, bytes(self.operator_key), ACTION_RESOLUTION_LABEL):
            raise StoreError("operator reconciliation signature is invalid", kind="authorization")
        for field in ("action_id", "action", "attempt", "completed", "resolution_id"):
            if resolution_record.get(field) != resolution_event.get(field):
                raise StoreError("signed reconciliation record does not match the pending action", kind="authorization")
        if not _valid_sha256(resolution_record.get("evidence_sha256")):
            raise StoreError("reconciliation evidence digest must be a lowercase SHA-256", kind="argument")
        self.store.reconcile_action(action_id, resolution_event, resolution_key=bytes(self.operator_key))
        self._control_history = self.store.control_events()
        self._replay_controls()
        if current["action"] in _LIFECYCLE_ACTIONS:
            self._apply_reconciled_state(current["action"], completed)
            self.lifecycle_action_id = current.get("group_id") if self.lifecycle_state in {"STOPPING", "ROLLING_BACK"} else None

    def start_worker(self, start: Callable[[], Any], *, probe: dict | None = None, action_id: str | None = None) -> Any:
        if not self.store.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before worker start", kind="integrity")
        if self.lifecycle_state == "BLOCKED_RECOVERY":
            raise StoreError("unresolved lifecycle action requires reconciliation", kind="lifecycle")
        if self.breaker_state != "CLOSED":
            raise StoreError("provider breaker is open; worker start refused", kind="provider")
        if self.store.sandbox_mode:
            from .preflight import SPEC_PATH, verify_fresh_probe, verify_network_policy_attestation

            if self._probe_consumed:
                raise StoreError("preflight probe has already authorized a worker start", kind="probe")
            spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
            if not verify_fresh_probe(
                probe, run_id=self.run_id, spec_sha256=spec_sha256,
                nonce=self.probe_nonce, key=bytes(self.probe_key),
            ):
                raise StoreError("fresh passing signed preflight is required for this run", kind="probe")
            attestation = probe["inventory"].get("network_policy_attestation")
            if not verify_network_policy_attestation(
                attestation, run_id=self.run_id, spec_sha256=spec_sha256,
                nonce=self.probe_nonce, key=bytes(self.operator_key),
            ):
                raise StoreError("operator-root-signed network policy attestation is required", kind="probe")
            probe_digest = hashlib.sha256(canonical_bytes(probe)).hexdigest()
            self.store.consume_preflight(self.run_id, self.probe_nonce, spec_sha256, probe_digest)
        next_state, _ = transition(self.lifecycle_state, "START")
        if self.store.sandbox_mode:
            self._probe_consumed = True
        result = self._perform("start", start, action_id, group_id=action_id)
        self.lifecycle_state = next_state
        return result

    def prepare_run(self, run_id: str, nonce: str) -> None:
        """Bind the next worker start to a never-before-used run and probe nonce."""
        if not self.store.sandbox_mode:
            raise StoreError("run-bound probes are required only in sandbox mode", kind="probe")
        if self.lifecycle_state != "READY":
            raise StoreError("next run can be prepared only from READY state", kind="lifecycle")
        if not isinstance(run_id, str) or not run_id.strip() or run_id in self._seen_run_ids:
            raise StoreError("run_id must be fresh and non-empty", kind="probe")
        if not isinstance(nonce, str) or not nonce.strip() or nonce in self._seen_probe_nonces:
            raise StoreError("probe nonce must be fresh and non-empty", kind="probe")
        self.run_id = run_id
        self.probe_nonce = nonce
        self._seen_run_ids.add(run_id)
        self._seen_probe_nonces.add(nonce)
        self._probe_consumed = False

    def evaluate_gate(
        self,
        task_id: str,
        current_head: str,
        current_epoch: int,
        worker_key: bytes,
        **gate_options: Any,
    ) -> Any:
        """Authoritative decision wrapper; store validates anchor and receipts."""
        if not self.store.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before gate decision", kind="integrity")
        gate_options["event_key"] = self.store._event_key
        return self.store.evaluate_gate(
            task_id, current_head, current_epoch, worker_key, **gate_options
        )

    def provider_succeeded(self, outcome_id: str | None = None) -> None:
        if self.breaker_state == "CLOSED":
            self.store._append_control_event("CONTROL_PROVIDER_SUCCESS", outcome_id or str(uuid.uuid4()), {})
            self._control_history = self.store.control_events(); self._replay_controls()

    def provider_failed(self, outcome_id: str | None = None) -> None:
        self.store._append_control_event("CONTROL_PROVIDER_FAILURE", outcome_id or str(uuid.uuid4()), {})
        self._control_history = self.store.control_events(); self._replay_controls()

    def manual_override(self, record: dict) -> None:
        """Resume the paused provider only with a distinct operator record."""
        if not isinstance(record, dict) or not record or "verdict" not in record:
            raise StoreError("manual override requires a distinct signed/identified record", kind="provider")
        try:
            canonical_bytes(record)
        except (TypeError, ValueError) as exc:
            raise StoreError("manual override record must be canonical JSON", kind="provider") from exc
        required = {
            "id", "action", "breaker_state", "breaker_episode_id",
            "breaker_config_id", "verdict", "evidence_sha256", "signature",
        }
        if set(record) != required or record.get("action") != "manual_override" or record.get("breaker_state") != "PAUSED_PROVIDER":
            raise StoreError("manual override signature must bind action and paused breaker state", kind="provider")
        if not isinstance(record.get("verdict"), str) or record.get("verdict").upper() == "APPROVE":
            raise StoreError("manual override cannot be represented as plain APPROVE", kind="provider")
        override_id = record.get("id")
        if not isinstance(override_id, str) or not override_id.strip():
            raise StoreError("manual override requires a stable record id", kind="provider")
        if not _valid_sha256(record.get("evidence_sha256")):
            raise StoreError("manual override requires lowercase evidence SHA-256", kind="provider")
        if not isinstance(self.operator_key, (bytes, bytearray)) or len(self.operator_key) < 32:
            raise StoreError("trusted operator key is unavailable for manual override", kind="provider")
        if not verify(record, bytes(self.operator_key), OPERATOR_MANUAL_OVERRIDE_LABEL):
            raise StoreError("manual override operator signature is invalid", kind="provider")
        if self.manual_override_recorder is None:
            raise StoreError("manual override record sink is unavailable", kind="provider")
        self._perform(
            "manual_override",
            lambda: self.manual_override_recorder(dict(record)),
            override_id,
            control_data={"override_record": record},
        )
        self.store.append_manual_override(record, operator_key=bytes(self.operator_key))
        self._control_history = self.store.control_events(); self._replay_controls()

    def stop(self, terminate: Callable[[], None], cleanup: Callable[[], None], *, action_id: str | None = None) -> None:
        if self.lifecycle_state == "BLOCKED_RECOVERY": raise StoreError("unresolved lifecycle action requires reconciliation", kind="lifecycle")
        base = action_id or (self.lifecycle_action_id if self.lifecycle_state == "STOPPING" else None) or str(uuid.uuid4())
        if self.lifecycle_state == "RUNNING":
            previous_state = self.lifecycle_state
            next_state, _ = transition(self.lifecycle_state, "STOP")
            self.lifecycle_state = next_state
            try:
                self._perform("stop_terminate", terminate, base + ":terminate", group_id=base)
            except BaseException:
                if self.lifecycle_state != "BLOCKED_RECOVERY":
                    self.lifecycle_state = previous_state
                raise
        elif self.lifecycle_state != "STOPPING":
            raise StoreError("stop can continue only from RUNNING or STOPPING", kind="lifecycle")
        final_state, _ = transition(self.lifecycle_state, "CLEANUP_COMPLETE")
        self._perform("stop_cleanup", cleanup, base + ":cleanup", group_id=base)
        self.lifecycle_state = final_state
        self.lifecycle_action_id = None

    def rollback(self, rollback_effect: Callable[[], None], cleanup: Callable[[], None], *, action_id: str | None = None) -> None:
        if self.lifecycle_state == "BLOCKED_RECOVERY": raise StoreError("unresolved lifecycle action requires reconciliation", kind="lifecycle")
        base = action_id or (self.lifecycle_action_id if self.lifecycle_state == "ROLLING_BACK" else None) or str(uuid.uuid4())
        if self.lifecycle_state == "RUNNING":
            previous_state = self.lifecycle_state
            next_state, _ = transition(self.lifecycle_state, "ROLLBACK")
            self.lifecycle_state = next_state
            try:
                self._perform("rollback_effect", rollback_effect, base + ":effect", group_id=base)
            except BaseException:
                if self.lifecycle_state != "BLOCKED_RECOVERY":
                    self.lifecycle_state = previous_state
                raise
        elif self.lifecycle_state != "ROLLING_BACK":
            raise StoreError("rollback can continue only from RUNNING or ROLLING_BACK", kind="lifecycle")
        final_state, _ = transition(self.lifecycle_state, "CLEANUP_COMPLETE")
        self._perform("rollback_cleanup", cleanup, base + ":cleanup", group_id=base)
        self.lifecycle_state = final_state
        self.lifecycle_action_id = None

    def resume(self, increment_epoch: Callable[[], Any], *, action_id: str | None = None) -> Any:
        if self.lifecycle_state == "BLOCKED_RECOVERY": raise StoreError("unresolved lifecycle action requires reconciliation", kind="lifecycle")
        next_state, _ = transition(self.lifecycle_state, "RESUME")
        epoch = self._perform("resume", increment_epoch, action_id)
        self.lifecycle_state = next_state
        return epoch

    def _simulate(
        self, kind: str, idempotency_key: str, payload: dict,
        effect: Callable[[Any], Any],
    ) -> Any:
        if kind not in {"push", "pull_request", "receipt"}:
            raise StoreError("unsupported supervisor operation", kind="argument")
        # Bind the operation payload to both caller intent and the repository
        # object identity; no corresponding method exists on a worker object.
        binding = {"kind": kind, "payload": payload, "payload_sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}
        return self.store.execute_idempotent(idempotency_key, kind, binding, effect)

    def simulate_push(self, idempotency_key: str, payload: dict) -> Any:
        return self._simulate(
            "push", idempotency_key, payload,
            lambda _conn: self.backend.push(payload, operation_key=idempotency_key),
        )

    def simulate_pull_request(self, idempotency_key: str, payload: dict) -> Any:
        return self._simulate(
            "pull_request", idempotency_key, payload,
            lambda _conn: self.backend.open_pull_request(payload, operation_key=idempotency_key),
        )

    def create_receipt(
        self, idempotency_key: str, receipt: dict, story_id: str, worker_key: bytes
    ) -> Any:
        if not self.store.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before receipt creation", kind="integrity")
        return self.store.append_receipt_idempotent(
            idempotency_key, receipt, story_id, worker_key
        )


__all__ = ["Supervisor", "STOP_TRANSITIONS"]
