"""Trusted supervisor boundary for synthetic worker lifecycle operations."""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from .contracts import canonical_bytes
from .lifecycle import STOP_TRANSITIONS, transition
from .signing import OPERATOR_MANUAL_OVERRIDE_LABEL, verify
from .store import (
    ACTION_RESOLUTION_LABEL, RUNNER_AUTHORITY_COMPLETION_MARGIN_SEC,
    Store, StoreError,
)

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
        execution_grant_key_id: str | None = None,
        execution_grant_private_key_path: str | None = None,
        execution_grant_openssl_path: str | None = None,
        execution_grant_trust_keys: dict[str, str] | None = None,
        dispatch_instruction_trust_keys: dict[str, dict[str, str]] | None = None,
        dispatch_instruction_openssl_path: str | None = None,
        execution_grant_audience: str = "vst-runner-service-v1",
        service_generation_provider: Callable[[], str] | None = None,
        model_provenance_verifier: Callable[[str, str], bool] | None = None,
        model_provenance_digest_provider: Callable[[str], str | None] | None = None,
        assignment_policy: dict | None = None,
        assignment_policy_provider: Callable[[], dict] | None = None,
        root_dispatch_issuer: dict | None = None,
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
        self.execution_grant_key_id = execution_grant_key_id
        self.execution_grant_private_key_path = execution_grant_private_key_path
        self.execution_grant_openssl_path = execution_grant_openssl_path
        self.execution_grant_trust_keys = execution_grant_trust_keys
        self.dispatch_instruction_trust_keys = dispatch_instruction_trust_keys
        self.dispatch_instruction_openssl_path = dispatch_instruction_openssl_path
        self.execution_grant_audience = execution_grant_audience
        self.service_generation_provider = service_generation_provider
        self.model_provenance_verifier = model_provenance_verifier
        self.model_provenance_digest_provider = model_provenance_digest_provider
        self.assignment_policy_provider = assignment_policy_provider
        self.root_dispatch_issuer = root_dispatch_issuer
        if assignment_policy is None:
            self.assignment_policy = None
            self.assignment_policy_sha256 = None
        else:
            from .assignment_basis import validate_policy
            self.assignment_policy, self.assignment_policy_sha256 = validate_policy(assignment_policy)
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
        grant_settings = (
            execution_grant_key_id, execution_grant_private_key_path,
            execution_grant_openssl_path, execution_grant_trust_keys, service_generation_provider,
            model_provenance_verifier,
        )
        if any(value is not None for value in grant_settings) and any(value is None for value in grant_settings):
            raise ValueError("execution grants require a signing key, active-generation provider, and model provenance verifier")
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

    def assignment_basis(self, *, assignment_operation_id: str) -> dict:
        """Return the current read-only basis for one root-policy assignment handoff."""
        from .assignment_basis import build_response, validate_request

        operation_id = validate_request({
            "schema": "VST_S2_ASSIGNMENT_BASIS_REQUEST_V1",
            "assignment_operation_id": assignment_operation_id,
        })
        policy = self.assignment_policy
        if (policy is None or self.assignment_policy_sha256 is None
                or self.service_generation_provider is None
                or self.assignment_policy_provider is None
                or not isinstance(self.run_id, str) or not self.run_id.strip()):
            raise StoreError("authenticated assignment-basis source is not provisioned", kind="authorization")
        from .assignment_basis import validate_policy
        try:
            current_policy, current_policy_sha256 = validate_policy(self.assignment_policy_provider())
        except (OSError, ValueError, TypeError) as exc:
            raise StoreError("root assignment policy is unreadable or invalid", kind="authorization") from exc
        if (current_policy_sha256 != self.assignment_policy_sha256
                or current_policy != policy):
            raise StoreError("root assignment policy changed or was revoked", kind="authorization")
        policy = current_policy
        if self.lifecycle_state != "READY" or self.breaker_state != "CLOSED":
            raise StoreError("Supervisor is not available for assignment-basis reads", kind="provider")
        now = datetime.now(timezone.utc)
        valid_from = datetime.strptime(policy["valid_from_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        expires = datetime.strptime(policy["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if not valid_from <= now < expires:
            raise StoreError("assignment delegation policy is not currently valid", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active Supervisor service generation is unavailable", kind="integrity")
        snapshot = self.store.authenticated_assignment_basis(
            operation_id, policy=policy, policy_sha256=self.assignment_policy_sha256,
            active_service_generation=generation,
            expected_run_id=self.run_id,
        )
        return build_response(
            snapshot["handoff"], policy=policy, policy_sha256=self.assignment_policy_sha256,
            authority_expires_at=snapshot["authority_expires_at"],
            service_generation=generation,
        )

    def issue_root_dispatch_instruction(self, *, assignment_operation_id: str) -> dict:
        """Issue only for the exact root-authenticated assignment operation ID."""
        config = self.root_dispatch_issuer
        if not isinstance(config, dict) or config.get("enabled") is not True:
            raise StoreError("root dispatch issuer is disabled or unconfigured", kind="authorization")
        policy = self.assignment_policy
        if (policy is None or self.assignment_policy_provider is None
                or not callable(self.service_generation_provider) or not self._probe_consumed
                or self.lifecycle_state != "READY" or self.breaker_state != "CLOSED"):
            raise StoreError("root dispatch issuance authority is unavailable", kind="authorization")
        from .assignment_basis import validate_policy
        current_policy, policy_sha256 = validate_policy(self.assignment_policy_provider())
        if current_policy != policy or policy_sha256 != self.assignment_policy_sha256:
            raise StoreError("root assignment policy changed or was revoked", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        snapshot = self.store.authenticated_assignment_basis(
            assignment_operation_id, policy=current_policy, policy_sha256=policy_sha256,
            active_service_generation=generation, expected_run_id=self.run_id,
        )
        from .root_dispatch_issuer import issue_frozen_dispatch
        now = datetime.now(timezone.utc)
        authority_expiry = datetime.fromtimestamp(
            snapshot["authority_expires_at"], timezone.utc,
        ).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
        def authority_provider(intent: dict) -> dict:
            latest_policy, latest_digest = validate_policy(self.assignment_policy_provider())
            latest_generation = self.service_generation_provider()
            if (latest_policy != intent["policy"] or latest_digest != intent["policy_sha256"]
                    or latest_generation != intent["service_generation"]):
                raise StoreError("root issuance policy or generation changed", kind="authorization")
            return {"policy": latest_policy, "policy_sha256": latest_digest,
                    "generation": latest_generation, "run_id": self.run_id}
        def before_sign(intent: dict) -> bool:
            latest_policy, latest_digest = validate_policy(self.assignment_policy_provider())
            latest_generation = self.service_generation_provider()
            if (latest_policy != current_policy or latest_digest != policy_sha256
                    or latest_generation != generation):
                return False
            latest_snapshot = self.store.authenticated_assignment_basis(
                assignment_operation_id, policy=latest_policy, policy_sha256=latest_digest,
                active_service_generation=latest_generation, expected_run_id=self.run_id,
            )
            latest_expiry = datetime.fromtimestamp(
                latest_snapshot["authority_expires_at"], timezone.utc,
            ).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
            return (
                latest_snapshot["handoff"] == intent["handoff"]
                and min(latest_expiry, latest_policy["expires_at_utc"],
                        latest_snapshot["handoff"]["expires_at_utc"])
                >= intent["unsigned"]["expires_at"]
            )
        try:
            return issue_frozen_dispatch(
                self.store, handoff=snapshot["handoff"], policy=current_policy,
                policy_sha256=policy_sha256, authority_expires_at_utc=authority_expiry,
                signer=config["signer"], private_key_path=config["private_key_path"],
                public_key_path=config["public_key_path"], openssl_path=config["openssl_path"],
                issuer_max_ttl_seconds=config["maximum_ttl_seconds"],
                minimum_safety_slack_seconds=config["minimum_safety_slack_seconds"], now=now,
                authority_provider=authority_provider, before_sign=before_sign,
            )
        except Exception as exc:
            raise StoreError("root dispatch issuance failed closed", kind="authorization") from exc

    def bootstrap_assignment(self, request: dict, *, peer: Any) -> dict:
        """Create one exact fresh assignment for the kernel-authenticated bootstrap peer."""
        from .assignment_basis import validate_bootstrap_request, validate_policy

        policy = self.assignment_policy
        if (policy is None or self.assignment_policy_sha256 is None
                or self.assignment_policy_provider is None
                or self.service_generation_provider is None
                or not isinstance(self.run_id, str) or not self.run_id.strip()
                or not self._probe_consumed):
            raise StoreError("authenticated assignment bootstrap is not provisioned", kind="authorization")
        current_policy, current_digest = validate_policy(self.assignment_policy_provider())
        if current_digest != self.assignment_policy_sha256 or current_policy != policy:
            raise StoreError("root assignment policy changed or was revoked", kind="authorization")
        if self.lifecycle_state != "READY" or self.breaker_state != "CLOSED":
            raise StoreError("Supervisor is not available for assignment bootstrap", kind="provider")
        peer_policy = {
            "role": getattr(peer, "role", None), "uid": getattr(peer, "uid", None),
            "gid": getattr(peer, "gid", None), "cgroup": getattr(peer, "cgroup", None),
        }
        if (peer_policy != policy["bootstrap_peer"]
                or getattr(peer, "operations", None) != frozenset({"bootstrap_assignment"})):
            raise StoreError("authenticated peer is not the root-configured assignment bootstrap role",
                             kind="authorization")
        validate_bootstrap_request(request, policy=policy)
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="integrity")
        return self.store.bootstrap_assignment(
            request, policy=policy, policy_sha256=self.assignment_policy_sha256,
            bootstrap_peer=peer_policy, expected_run_id=self.run_id,
            active_service_generation=generation,
            policy_provider=self.assignment_policy_provider,
            generation_provider=self.service_generation_provider,
        )

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

    def issue_execution_grant(
        self, *, task_id: str, slot: str, attempt: int, epoch: int,
        run_id: str, resolved_model: str, model_provenance_sha256: str,
        expected_owner: str | None = None,
        expected_lease_id: int | None = None,
    ) -> dict:
        """Issue a bounded one-run grant with a short claim window."""
        if (not isinstance(self.execution_grant_key_id, str)
                or not isinstance(self.execution_grant_private_key_path, str)
                or not isinstance(self.execution_grant_openssl_path, str)
                or not callable(self.service_generation_provider)
                or not callable(self.model_provenance_verifier)):
            raise StoreError("execution grant issuer is not configured", kind="authorization")
        if not self.store.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before grant issuance", kind="integrity")
        if self.lifecycle_state == "BLOCKED_RECOVERY" or self.breaker_state != "CLOSED":
            raise StoreError("supervisor is not in an admitting state", kind="lifecycle")
        if not isinstance(resolved_model, str) or not resolved_model.strip() or not _valid_sha256(model_provenance_sha256):
            raise StoreError("resolved model provenance is malformed", kind="authorization")
        if self.model_provenance_verifier(resolved_model, model_provenance_sha256) is not True:
            raise StoreError("resolved model provenance is not trusted", kind="authorization")
        if self.store.sandbox_mode and (run_id != self.run_id or not self._probe_consumed):
            raise StoreError("execution grant must use this service's consumed preflight run", kind="probe")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation.strip():
            raise StoreError("active service generation is unavailable", kind="authorization")
        basis = self.store.execution_grant_basis(
            task_id, slot, attempt, epoch, run_id,
            active_service_generation=generation,
            expected_owner=expected_owner,
            expected_lease_id=expected_lease_id,
        )
        manifest_timeout = basis.pop("manifest_timeout_sec")
        authority_expires_at = basis.pop("authority_expires_at")
        from .execution_grant import (
            GRANT_CLAIM_WINDOW_SEC, GRANT_COMPLETION_SLACK_SEC,
            MAX_EXECUTION_DEADLINE_SEC, sign_execution_grant,
        )
        now = self.store._now()
        if int(manifest_timeout) > MAX_EXECUTION_DEADLINE_SEC:
            raise StoreError(
                "manifest run window exceeds the persistent runner's supported execution bound",
                kind="authorization",
            )
        execution_deadline_sec = int(manifest_timeout)
        completion_margin_sec = RUNNER_AUTHORITY_COMPLETION_MARGIN_SEC
        remaining_window = float(authority_expires_at) - now
        if remaining_window <= execution_deadline_sec + completion_margin_sec:
            raise StoreError(
                "owner/lease authority window cannot cover the required run and completion margin",
                kind="authorization",
            )
        claim_window = min(
            float(GRANT_CLAIM_WINDOW_SEC),
            remaining_window - execution_deadline_sec - completion_margin_sec,
        )
        if claim_window < 1.0:
            raise StoreError("owner/lease authority window leaves no safe grant-claim interval", kind="authorization")
        claim_expires_at = now + claim_window
        grant = {
            "version": 1, "grant_id": uuid.uuid4().hex,
            "request_id": uuid.uuid4().hex, "audience": self.execution_grant_audience,
            **basis, "invocation_id": uuid.uuid4().hex,
            "resolved_model": resolved_model,
            "model_provenance_sha256": model_provenance_sha256,
            "execution_deadline_sec": execution_deadline_sec,
            "issued_at": now, "claim_expires_at": claim_expires_at,
            "expires_at": min(
                float(authority_expires_at),
                claim_expires_at + execution_deadline_sec + GRANT_COMPLETION_SLACK_SEC,
            ),
        }
        return sign_execution_grant(
            grant, key_id=self.execution_grant_key_id,
            private_key_path=self.execution_grant_private_key_path,
            openssl_path=self.execution_grant_openssl_path,
        )

    def accept_dispatch_intent(
        self, *, principal: str, instruction: object,
    ) -> dict:
        """Independently verify signed provenance, then ask Store to enforce current authority."""
        if (self.lifecycle_state != "READY" or self.breaker_state != "CLOSED"
                or not callable(self.service_generation_provider)):
            raise StoreError("Supervisor is not admitting dispatch intents", kind="lifecycle")
        from .dispatch_instruction import validate_dispatch_instruction, verify_dispatch_instruction
        try:
            candidate = validate_dispatch_instruction(instruction)
        except Exception as exc:
            raise StoreError("dispatch instruction is malformed", kind="authorization") from exc
        key_id = candidate["key_id"]
        binding = self.store.dispatch_key_class_binding(key_id)
        issuer = self.root_dispatch_issuer if isinstance(self.root_dispatch_issuer, dict) else None
        delegated_key = issuer is not None and key_id == issuer.get("key_id")
        if binding is not None and binding.get("key_class") == "DELEGATED_V1" and not delegated_key:
            raise StoreError("delegated dispatch key cannot fall back to the legacy trust registry",
                             kind="authorization")
        if delegated_key:
            if issuer.get("enabled") is not True:
                raise StoreError("delegated dispatch issuer is disabled; legacy fallback is forbidden",
                                 kind="authorization")
            policy = self.assignment_policy
            if (policy is None or self.assignment_policy_provider is None
                    or not callable(self.service_generation_provider)):
                raise StoreError("delegated dispatch policy provider is unavailable", kind="authorization")
            from .assignment_basis import validate_policy
            current_policy, policy_digest = validate_policy(self.assignment_policy_provider())
            if current_policy != policy or policy_digest != self.assignment_policy_sha256:
                raise StoreError("root assignment policy changed or was revoked", kind="authorization")
            if principal != current_policy["owner_principal"]:
                raise StoreError("delegated dispatch principal differs from root policy", kind="authorization")
            from .root_dispatch_issuer import verify_issued_instruction
            root_registry = {key_id: {
                "principal": principal, "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
                "public_key_path": issuer["public_key_path"],
            }}
            try:
                verified = verify_dispatch_instruction(
                    candidate, root_registry, expected_principal=principal,
                    openssl_path=issuer["openssl_path"],
                )
                proof = verify_issued_instruction(
                    self.store, candidate, key_id=key_id,
                    public_key_path=issuer["public_key_path"],
                    fingerprint=issuer["public_key_fingerprint"],
                    openssl_path=issuer["openssl_path"],
                )
            except Exception as exc:
                raise StoreError("delegated dispatch issuance is invalid", kind="authorization") from exc
            generation = self.service_generation_provider()
            snapshot = self.store.authenticated_assignment_basis(
                proof.intent["assignment_operation_id"], policy=current_policy,
                policy_sha256=policy_digest, active_service_generation=generation,
                expected_run_id=self.run_id,
            )
            if (snapshot["handoff"] != proof.intent["handoff"]
                    or proof.intent["policy"] != current_policy
                    or proof.intent["policy_sha256"] != policy_digest):
                raise StoreError("delegated issuance no longer matches the current assignment basis",
                                 kind="authorization")
            def authority_guard() -> bool:
                try:
                    latest_policy, latest_digest = validate_policy(self.assignment_policy_provider())
                    now_utc = datetime.now(timezone.utc)
                    valid_from = datetime.strptime(
                        latest_policy["valid_from_utc"], "%Y-%m-%dT%H:%M:%SZ",
                    ).replace(tzinfo=timezone.utc)
                    expires = datetime.strptime(
                        latest_policy["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ",
                    ).replace(tzinfo=timezone.utc)
                    return (latest_policy == current_policy and latest_digest == policy_digest
                            and self.service_generation_provider() == generation
                            and self.run_id == proof.intent["handoff"]["run_id"]
                            and self._probe_consumed and valid_from <= now_utc < expires)
                except Exception:
                    return False
            return self.store.accept_dispatch_intent(
                principal=verified["principal"], instruction=verified["instruction"],
                service_generation=generation, key_class="DELEGATED_V1",
                key_fingerprint=issuer["public_key_fingerprint"], issuance_proof=proof,
                authority_guard=authority_guard,
            )
        if (not isinstance(self.dispatch_instruction_trust_keys, dict)
                or not isinstance(self.dispatch_instruction_openssl_path, str)):
            raise StoreError("dispatch instruction trust registry is unavailable", kind="authorization")
        if binding is not None and binding.get("key_class") != "LEGACY_V1":
            raise StoreError("dispatch key class is not trusted as legacy", kind="authorization")
        try:
            verified = verify_dispatch_instruction(
                candidate, self.dispatch_instruction_trust_keys,
                expected_principal=principal,
                openssl_path=self.dispatch_instruction_openssl_path,
            )
        except Exception as exc:
            raise StoreError("dispatch instruction signature or provenance is invalid", kind="authorization") from exc
        run_id = verified["instruction"]["run_id"]
        if self.store.sandbox_mode and (run_id != self.run_id or not self._probe_consumed):
            raise StoreError("dispatch intent must use the consumed current preflight run", kind="probe")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation.strip():
            raise StoreError("active service generation is unavailable", kind="authorization")
        entry = self.dispatch_instruction_trust_keys.get(key_id)
        from .root_dispatch_issuer import public_key_fingerprint
        try:
            fingerprint = public_key_fingerprint(entry["public_key_path"])
        except Exception as exc:
            raise StoreError("legacy dispatch key fingerprint is unavailable", kind="authorization") from exc
        return self.store.accept_dispatch_intent(
            principal=verified["principal"], instruction=verified["instruction"],
            service_generation=generation, key_class="LEGACY_V1", key_fingerprint=fingerprint,
        )

    def replay_dispatch_outcome(self, *, principal: str, instruction: object) -> dict | None:
        """Observe an exact accepted result without granting current execution authority."""
        return self.store.replay_dispatch_outcome(principal=principal, instruction=instruction)

    def ack_dispatch_intent(
        self, *, principal: str, request_id: str, payload_digest: str, event_seq: int,
        result_sha256: str, service_generation: str,
    ) -> dict:
        """Persist the authenticated dispatch-owner relay-forwarding acknowledgement."""
        binding = self.store.acknowledge_dispatch_intent(
            principal=principal, request_id=request_id, payload_digest=payload_digest,
            event_seq=event_seq, result_sha256=result_sha256,
            service_generation=service_generation,
        )
        # Principal is bound from authenticated peer credentials, not echoed as caller input.
        return {key: value for key, value in binding.items() if key != "principal"}

    def _validate_current_dispatch_intent(self, intent: dict, generation: str,
                                          trust_registry: dict, openssl_path: str) -> dict | None:
        if ("instruction" not in intent or "key_id" not in intent
                or intent.get("instruction", {}).get("key_id") != intent.get("key_id")):
            raise StoreError("dispatch intent lacks signed instruction provenance", kind="authorization")
        from .dispatch_instruction import verify_dispatch_instruction
        if intent.get("key_class") == "DELEGATED_V1":
            issuer = self.root_dispatch_issuer
            if (not isinstance(issuer, dict) or issuer.get("enabled") is not True
                    or intent.get("key_id") != issuer.get("key_id")
                    or intent.get("key_fingerprint") != issuer.get("public_key_fingerprint")):
                raise StoreError("delegated dispatch key class is unavailable or changed", kind="authorization")
            from .assignment_basis import validate_policy
            from .root_dispatch_issuer import verify_issued_instruction
            if not callable(self.assignment_policy_provider):
                raise StoreError("delegated dispatch root policy is unavailable", kind="authorization")
            current_policy, policy_digest = validate_policy(self.assignment_policy_provider())
            if current_policy != self.assignment_policy or policy_digest != self.assignment_policy_sha256:
                raise StoreError("delegated dispatch root policy changed", kind="authorization")
            try:
                proof = verify_issued_instruction(
                    self.store, intent["instruction"], key_id=issuer["key_id"],
                    public_key_path=issuer["public_key_path"],
                    fingerprint=issuer["public_key_fingerprint"],
                    openssl_path=issuer["openssl_path"],
                )
            except Exception as exc:
                raise StoreError("delegated dispatch issuance verification failed", kind="authorization") from exc
            basis = self.store.validate_delegated_dispatch_snapshot(
                intent=intent, proof=proof, principal=intent["principal"],
                generation=generation, current_policy=current_policy,
            )
            if basis["manifest_sha256"] != intent["manifest_digest"]:
                raise StoreError("delegated dispatch intent no longer matches Store authority", kind="lease")
            return proof
        try:
            verify_dispatch_instruction(
                intent["instruction"], trust_registry,
                expected_principal=intent["principal"], openssl_path=openssl_path,
            )
        except Exception as exc:
            raise StoreError("dispatch intent instruction provenance is no longer valid", kind="authorization") from exc
        if intent.get("service_generation") != generation:
            raise StoreError("dispatch intent belongs to another service generation", kind="generation")
        basis = self.store.execution_grant_basis(
            intent["task_id"], intent["slot"], intent["attempt"], intent["epoch"],
            intent["run_id"], active_service_generation=generation,
            expected_owner=intent["principal"],
            expected_lease_id=intent["lease_id"],
        )
        if basis["manifest_sha256"] != intent["manifest_digest"]:
            raise StoreError("dispatch intent no longer matches Store authority", kind="lease")
        return None

    def next_dispatch_intent(self, *, cursor: dict | None, audience: str) -> dict:
        """Return at most one current authorized intent and a signed replay cursor."""
        if (self.lifecycle_state != "READY" or self.breaker_state != "CLOSED"
                or not callable(self.service_generation_provider)):
            raise StoreError("Supervisor is not admitting dispatch subscriptions", kind="lifecycle")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation.strip():
            raise StoreError("active service generation is unavailable", kind="authorization")
        after_seq = 0 if cursor is None else self.store.verify_dispatch_cursor(
            cursor, service_generation=generation, audience=audience,
        )
        window = self.store.read_dispatch_intents(after_seq=after_seq, limit=256)
        idle_cursor = self.store.make_dispatch_cursor(
            sequence=window["high_watermark"], service_generation=generation, audience=audience,
        )
        for intent in window["intents"]:
            try:
                self._validate_current_dispatch_intent(
                    intent, generation, self.dispatch_instruction_trust_keys or {},
                    self.dispatch_instruction_openssl_path or "",
                )
            except StoreError as exc:
                if exc.kind not in {
                    "authorization", "budget", "chain", "duplicate", "epoch", "generation",
                    "lease", "probe", "retry", "slot", "terminal",
                }:
                    # Busy/integrity/unknown failures must not advance the durable replay position.
                    raise
                # Old, revoked, or stale intents are historical facts, not delivery authority.
                continue
            return {
                "intent": intent,
                "cursor_after": self.store.make_dispatch_cursor(
                    sequence=intent["event_seq"], service_generation=generation,
                    audience=audience,
                ),
                "cursor_idle": idle_cursor,
            }
        return {"intent": None, "cursor_after": idle_cursor, "cursor_idle": idle_cursor}

    def issue_dispatch_intent_grant(self, *, request_id: str) -> dict:
        """Issue or replay the one grant bound to an accepted dispatch intent."""
        if (self.lifecycle_state != "READY" or self.breaker_state != "CLOSED"
                or not callable(self.service_generation_provider)):
            raise StoreError("Supervisor is not admitting dispatch grants", kind="lifecycle")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        if self.store.sandbox_mode and (self.run_id is None or not self._probe_consumed):
            raise StoreError("dispatch grant requires this service's consumed preflight", kind="probe")
        intent = self.store.find_dispatch_intent(request_id)
        delegated_proof = self._validate_current_dispatch_intent(
            intent, generation, self.dispatch_instruction_trust_keys or {},
            self.dispatch_instruction_openssl_path or "",
        )
        manifest = self.store.get_manifest(intent["task_id"])
        model = manifest["model_policy"]
        if not callable(self.model_provenance_digest_provider):
            raise StoreError("root model provenance resolver is unavailable", kind="authorization")
        model_digest = self.model_provenance_digest_provider(model)
        if not isinstance(model_digest, str) or not _valid_sha256(model_digest):
            raise StoreError("manifest model policy has no trusted root provenance", kind="authorization")
        payload = {"request_id": request_id, "service_generation": generation}
        if delegated_proof is not None:
            payload.update({
                "issuance_operation_key": delegated_proof.intent["operation_key"],
                "issuance_envelope_sha256": hashlib.sha256(
                    canonical_bytes(delegated_proof.envelope),
                ).hexdigest(),
            })
        operation_key = f"dispatch-grant:{request_id}"
        def validate_grant(conn, grant):
            if delegated_proof is None:
                return
            if not self._dispatch_authority_guard(delegated_proof, generation)():
                raise StoreError("delegated root policy/generation changed at grant boundary",
                                 kind="authorization")
            self.store._validate_dispatch_grant_authority_locked(
                conn, grant=grant, dispatch_request_id=request_id,
                proof=delegated_proof, generation=generation, current=True,
                expected_operation_payload=payload,
            )
        previous = self.store.lookup_idempotent_operation(
            operation_key, operation="dispatch_grant", payload=payload, check_payload=True,
            validate_result=validate_grant if delegated_proof is not None else None,
        )
        if previous is not None:
            return previous["result"]
        grant = self.issue_execution_grant(
            task_id=intent["task_id"], slot=intent["slot"], attempt=intent["attempt"],
            epoch=intent["epoch"], run_id=intent["run_id"], resolved_model=model,
            model_provenance_sha256=model_digest, expected_owner=intent["principal"],
            expected_lease_id=intent["lease_id"],
        )
        return self.store.execute_idempotent(
            operation_key, "dispatch_grant", payload, lambda _conn: grant,
            before_commit=validate_grant if delegated_proof is not None else None,
            on_replay=validate_grant if delegated_proof is not None else None,
        )

    def _dispatch_authority_guard(self, proof: Any, generation: str) -> Callable[[], bool]:
        def check() -> bool:
            try:
                from .assignment_basis import validate_policy
                current_policy, digest = validate_policy(self.assignment_policy_provider())
                now_utc = datetime.now(timezone.utc)
                valid_from = datetime.strptime(
                    current_policy["valid_from_utc"], "%Y-%m-%dT%H:%M:%SZ",
                ).replace(tzinfo=timezone.utc)
                expires = datetime.strptime(
                    current_policy["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ",
                ).replace(tzinfo=timezone.utc)
                return (current_policy == proof.intent["policy"]
                        and digest == proof.intent["policy_sha256"]
                        and self.service_generation_provider() == generation
                        and proof.intent["service_generation"] == generation
                        and self.run_id == proof.intent["handoff"]["run_id"]
                        and self._probe_consumed and valid_from <= now_utc < expires)
            except Exception:
                return False
        return check

    def _dispatch_issuance_proof_for_grant(self, grant: dict) -> Any:
        target = self.store.dispatch_issuance_target_for_grant(grant)
        if target is None:
            return None
        issuer = self.root_dispatch_issuer
        if (not isinstance(issuer, dict) or issuer.get("enabled") is not True
                or target["key_id"] != issuer.get("key_id")
                or target["key_fingerprint"] != issuer.get("public_key_fingerprint")):
            raise StoreError("delegated grant key class is disabled or changed", kind="authorization")
        from .assignment_basis import validate_policy
        if not callable(self.assignment_policy_provider):
            raise StoreError("delegated grant root policy is unavailable", kind="authorization")
        current_policy, digest = validate_policy(self.assignment_policy_provider())
        if current_policy != self.assignment_policy or digest != self.assignment_policy_sha256:
            raise StoreError("delegated grant root policy changed", kind="authorization")
        if current_policy["owner_principal"] != target["principal"]:
            raise StoreError("delegated grant principal differs from root policy", kind="authorization")
        from .root_dispatch_issuer import verify_issued_instruction
        try:
            proof = verify_issued_instruction(
                self.store, target["instruction"], key_id=target["key_id"],
                public_key_path=issuer["public_key_path"], fingerprint=target["key_fingerprint"],
                openssl_path=issuer["openssl_path"],
            )
        except Exception as exc:
            raise StoreError("delegated grant issuance proof is invalid", kind="authorization") from exc
        if (proof.intent["operation_key"] != target["issuance_operation_key"]
                or hashlib.sha256(canonical_bytes(target["instruction"])).hexdigest()
                != target["issuance_envelope_sha256"]
                or proof.intent["policy"] != current_policy
                or proof.intent["policy_sha256"] != digest):
            raise StoreError("delegated grant lost its exact issuance or policy binding", kind="integrity")
        return proof

    def claim_runner_execution(self, grant: dict) -> dict | None:
        """Supervisor IPC endpoint: recheck active generation and Store state before dispatch."""
        if not callable(self.service_generation_provider):
            raise StoreError("active service-generation provider is unavailable", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        # An expired grant may retrieve its exact already-completed receipt;
        # Store rejects any expired grant that has no matching COMPLETE claim.
        self._verify_issued_execution_grant(grant, generation, allow_expired=True)
        completed_receipt = self.store.completed_runner_execution_receipt(grant)
        if completed_receipt is not None:
            return completed_receipt
        issuance_proof = self._dispatch_issuance_proof_for_grant(grant)
        authority_guard = (None if issuance_proof is None else
                           self._dispatch_authority_guard(issuance_proof, generation))
        return self.store.claim_runner_execution(
            grant, active_service_generation=generation,
            dispatch_issuance_proof=issuance_proof,
            authority_guard=authority_guard,
        )

    def runner_execution_claim_status(self, grant: dict) -> dict:
        """Resolve an uncertain claim response without moving or reclaiming its owner."""
        if not callable(self.service_generation_provider):
            raise StoreError("active service-generation provider is unavailable", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        self._verify_issued_execution_grant(grant, generation, allow_expired=True)
        return self.store.runner_execution_claim_status(
            grant, active_service_generation=generation,
        )

    def mark_runner_prespawn_no_execution(self, grant: dict, *, reason_code: str) -> dict:
        """Accept a runnerd-only terminal proof for an unreserved exact claim."""
        if not callable(self.service_generation_provider):
            raise StoreError("active service-generation provider is unavailable", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        self._verify_issued_execution_grant(grant, generation, allow_expired=True)
        return self.store.mark_runner_prespawn_no_execution(
            grant, active_service_generation=generation, reason_code=reason_code,
        )

    def reserve_runner_execution(self, grant: dict) -> dict:
        """Atomically reserve launch for the current exact grant and service generation."""
        if not callable(self.service_generation_provider):
            raise StoreError("active service-generation provider is unavailable", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        self._verify_issued_execution_grant(grant, generation)
        issuance_proof = self._dispatch_issuance_proof_for_grant(grant)
        authority_guard = (None if issuance_proof is None else
                           self._dispatch_authority_guard(issuance_proof, generation))
        return self.store.reserve_runner_execution(
            grant, active_service_generation=generation,
            dispatch_issuance_proof=issuance_proof,
            authority_guard=authority_guard,
        )

    def verify_pending_runner_execution(self, grant: dict) -> bool:
        """Signer IPC endpoint: prove exact-grant PENDING/reserved authority is current."""
        if not callable(self.service_generation_provider):
            return False
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            return False
        try:
            self._verify_issued_execution_grant(grant, generation)
        except Exception:
            return False
        return self.store.verify_pending_runner_execution(
            grant, active_service_generation=generation,
        )

    def complete_runner_execution(self, grant: dict, receipt: dict) -> None:
        """Supervisor IPC endpoint: persist a receipt only while its authority remains current."""
        if not callable(self.service_generation_provider):
            raise StoreError("active service-generation provider is unavailable", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        self._verify_issued_execution_grant(grant, generation)
        self.store.complete_runner_execution(
            grant, receipt, active_service_generation=generation,
        )

    def _verify_issued_execution_grant(
        self, grant: dict, generation: str, *, allow_expired: bool = False,
    ) -> dict:
        if (not isinstance(self.execution_grant_openssl_path, str)
                or not isinstance(self.execution_grant_audience, str)
                or not isinstance(self.execution_grant_trust_keys, dict)):
            raise StoreError("execution grant trust roots are unavailable", kind="authorization")
        from .execution_grant import verify_execution_grant
        try:
            return verify_execution_grant(
                grant, self.execution_grant_trust_keys,
                audience=self.execution_grant_audience,
                service_generation=generation,
                openssl_path=self.execution_grant_openssl_path,
                allow_expired=allow_expired,
            )
        except Exception as exc:
            raise StoreError("execution grant signature or scope is invalid", kind="authorization") from exc

    def recover_predecessor_runner_claims(self) -> int:
        """Terminalize predecessor PENDING/reserved claims after the new generation is verified empty."""
        if not callable(self.service_generation_provider):
            raise StoreError("active service-generation provider is unavailable", kind="authorization")
        generation = self.service_generation_provider()
        if not isinstance(generation, str) or not generation:
            raise StoreError("active service generation is unavailable", kind="authorization")
        return self.store.mark_pending_runner_executions_indeterminate(
            current_service_generation=generation,
        )

    def reconcile_runner_execution(self, resolution_record: dict) -> dict:
        """Apply only an operator-signed exact-grant resolution to an indeterminate claim."""
        if (not isinstance(self.operator_key, (bytes, bytearray))
                or not isinstance(self.store._execution_resolution_key, (bytes, bytearray))
                or bytes(self.operator_key) != bytes(self.store._execution_resolution_key)):
            raise StoreError("matching trusted operator key is required for runner reconciliation", kind="authorization")
        return self.store.reconcile_runner_execution(resolution_record)

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
        prior = self._action_status.get(override_id)
        if (prior and prior.get("status") in {"completed", "reconciled"}
                and canonical_bytes(prior.get("override_record")) != canonical_bytes(record)):
            raise StoreError(
                "completed manual override action id reused with a different record",
                kind="duplicate",
            )
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
        effect: Callable[[], Any],
    ) -> Any:
        if kind not in {"push", "pull_request", "receipt"}:
            raise StoreError("unsupported supervisor operation", kind="argument")
        # Bind the operation payload to both caller intent and the repository
        # object identity; no corresponding method exists on a worker object.
        binding = {"kind": kind, "payload": payload, "payload_sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}
        return self.store.execute_external_idempotent(idempotency_key, kind, binding, effect)

    def simulate_push(self, idempotency_key: str, payload: dict) -> Any:
        return self._simulate(
            "push", idempotency_key, payload,
            lambda: self.backend.push(payload, operation_key=idempotency_key),
        )

    def simulate_pull_request(self, idempotency_key: str, payload: dict) -> Any:
        return self._simulate(
            "pull_request", idempotency_key, payload,
            lambda: self.backend.open_pull_request(payload, operation_key=idempotency_key),
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
