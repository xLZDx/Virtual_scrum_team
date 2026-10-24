"""Trusted supervisor boundary for synthetic worker lifecycle operations."""

from __future__ import annotations

import hashlib
from typing import Any, Callable

from .contracts import canonical_bytes
from .lifecycle import STOP_TRANSITIONS, transition
from .store import Store, StoreError


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
        self.provider_failures = 0
        self.breaker_state = "CLOSED"
        self.lifecycle_state = "READY"

    def start_worker(self, start: Callable[[], Any], *, probe: dict | None = None) -> Any:
        if not self.store.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before worker start", kind="integrity")
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
        result = start()
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

    def provider_succeeded(self) -> None:
        if self.breaker_state == "CLOSED":
            self.provider_failures = 0

    def provider_failed(self) -> None:
        self.provider_failures += 1
        if self.provider_failures >= self.failure_threshold:
            self.breaker_state = "PAUSED_PROVIDER"

    def manual_override(self, record: dict) -> None:
        """Resume the paused provider only with a distinct operator record."""
        if self.breaker_state != "PAUSED_PROVIDER":
            raise StoreError("manual override is only valid for a paused provider", kind="provider")
        if not isinstance(record, dict) or not record or "verdict" not in record:
            raise StoreError("manual override requires a distinct signed/identified record", kind="provider")
        if record.get("verdict") == "APPROVE":
            raise StoreError("manual override cannot be represented as plain APPROVE", kind="provider")
        if self.manual_override_recorder is None:
            raise StoreError("manual override record sink is unavailable", kind="provider")
        self.manual_override_recorder(dict(record))
        self.breaker_state = "CLOSED"
        self.provider_failures = 0

    def stop(self, terminate: Callable[[], None], cleanup: Callable[[], None]) -> None:
        next_state, _ = transition(self.lifecycle_state, "STOP")
        self.lifecycle_state = next_state
        terminate()
        final_state, _ = transition(self.lifecycle_state, "CLEANUP_COMPLETE")
        cleanup()
        self.lifecycle_state = final_state

    def rollback(self, rollback_effect: Callable[[], None], cleanup: Callable[[], None]) -> None:
        next_state, _ = transition(self.lifecycle_state, "ROLLBACK")
        self.lifecycle_state = next_state
        rollback_effect()
        final_state, _ = transition(self.lifecycle_state, "CLEANUP_COMPLETE")
        cleanup()
        self.lifecycle_state = final_state

    def resume(self, increment_epoch: Callable[[], Any]) -> Any:
        next_state, _ = transition(self.lifecycle_state, "RESUME")
        epoch = increment_epoch()
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
