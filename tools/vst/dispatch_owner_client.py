"""Dispatch-owner RPC client that forwards only verified signed instructions."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from .contracts import ContractError, canonical_bytes
from .dispatch_instruction import validate_dispatch_instruction, verify_dispatch_instruction


class DispatchOutcomeUnknown(RuntimeError):
    """Supervisor was called, but acceptance could not be proven to the relay."""


class DispatchOwnerClient:
    """Client-side verifier; Supervisor repeats verification at the trust boundary."""

    def __init__(self, *, principal: str, trust_registry: Mapping[str, Mapping[str, str]],
                 openssl_path: str, transport: Any):
        if not isinstance(principal, str) or not principal:
            raise ContractError("dispatch-owner principal is required from local authenticated config")
        if not callable(getattr(transport, "submit_dispatch_intent", None)):
            raise ContractError("dispatch-owner transport does not expose the submit operation")
        if not callable(getattr(transport, "replay_dispatch_outcome", None)):
            raise ContractError("dispatch-owner transport does not expose the historical replay operation")
        if not callable(getattr(transport, "ack_dispatch_intent", None)):
            raise ContractError("dispatch-owner transport does not expose the acknowledgement operation")
        if not callable(getattr(transport, "completed_dispatch_receipt", None)):
            raise ContractError("dispatch-owner transport does not expose the completed receipt operation")
        self.principal = principal
        self.trust_registry = trust_registry
        self.openssl_path = openssl_path
        self.transport = transport

    def submit(self, instruction: object) -> dict:
        envelope = validate_dispatch_instruction(instruction)
        try:
            verified = verify_dispatch_instruction(
                envelope, self.trust_registry, expected_principal=self.principal,
                openssl_path=self.openssl_path,
            )
        except ContractError as exc:
            # An expired/revoked envelope may retrieve only a matching historical
            # acceptance; a miss never falls through to current admission.
            result = self._replay_historical(envelope)
            if result is None:
                raise
            return result
        # Preserve the exact parsed envelope: no caller-supplied principal or field projection.
        try:
            result = self.transport.submit_dispatch_intent(instruction=verified["instruction"])
            self._validate_result(result, verified["instruction"])
        except Exception as exc:
            # Once admission RPC starts, recover only by reading the immutable result;
            # never retry the admission operation after an ambiguous response.
            try:
                result = self._replay_historical(verified["instruction"])
            except DispatchOutcomeUnknown:
                raise
            if result is not None:
                return result
            if self._is_explicit_refusal(exc):
                raise
            raise DispatchOutcomeUnknown("Supervisor acceptance is not proven") from exc
        return result

    @staticmethod
    def _is_explicit_refusal(exc: Exception) -> bool:
        kind = getattr(exc, "kind", None)
        if kind in {"argument", "authorization", "budget", "chain", "duplicate", "epoch",
                    "generation", "lease", "lifecycle", "probe", "refused", "slot"}:
            return True
        return False

    def _replay_historical(self, instruction: dict) -> dict | None:
        try:
            result = self.transport.replay_dispatch_outcome(instruction=instruction)
        except Exception as exc:
            raise DispatchOutcomeUnknown("historical dispatch outcome could not be verified") from exc
        if result is None:
            return None
        try:
            self._validate_result(result, instruction)
        except Exception as exc:
            raise DispatchOutcomeUnknown("historical dispatch outcome differs from the request") from exc
        return result

    def _validate_result(self, result: object, instruction: dict) -> None:
        if not isinstance(result, dict) or result.get("principal") != self.principal:
            raise ContractError("Supervisor response principal differs from the authenticated relay")
        if "instruction" not in result:
            raise ContractError("Supervisor returned a malformed dispatch-intent response")
        accepted = validate_dispatch_instruction(result["instruction"])
        if (accepted != instruction or result.get("key_id") != accepted["key_id"]
                or any(result.get(field) != accepted[field] for field in (
                    "task_id", "slot", "attempt", "epoch", "run_id", "request_id",
                ))):
            raise ContractError("Supervisor response differs from the submitted signed dispatch instruction")

    def acknowledge_forwarded(self, result: dict) -> dict:
        """Acknowledge only the exact result after the relay's local sendall succeeds."""
        if not isinstance(result, dict) or result.get("principal") != self.principal:
            raise DispatchOutcomeUnknown("Supervisor result principal is not the configured relay identity")
        try:
            result_sha256 = hashlib.sha256(canonical_bytes(result)).hexdigest()
            body = {
                "request_id": result["request_id"],
                "payload_digest": result["payload_digest"],
                "event_seq": result["event_seq"],
                "result_sha256": result_sha256,
                "service_generation": result["service_generation"],
            }
            acknowledged = self.transport.ack_dispatch_intent(**body)
            if acknowledged != body:
                raise ContractError("Supervisor acknowledgement differs from forwarded result")
        except Exception as exc:
            raise DispatchOutcomeUnknown("dispatch result was forwarded but acknowledgement is unknown") from exc
        return body

    def completed_receipt(self, instruction: object) -> dict | None:
        """Poll only for the exact durable receipt of this owner's accepted instruction."""
        envelope = validate_dispatch_instruction(instruction)
        accepted = self._replay_historical(envelope)
        if accepted is None:
            return None
        try:
            result = self.transport.completed_dispatch_receipt(instruction=envelope)
        except Exception as exc:
            raise DispatchOutcomeUnknown("completed dispatch receipt could not be verified") from exc
        if result is None:
            return None
        if (not isinstance(result, dict) or set(result) != {"dispatch", "execution"}
                or not isinstance(result["dispatch"], dict)
                or not isinstance(result["execution"], dict)
                or set(result["execution"]) != {"request_id", "receipt"}):
            raise DispatchOutcomeUnknown("completed dispatch receipt is malformed")
        dispatch = result["dispatch"]
        if set(dispatch) != {
                "principal", "task_id", "slot", "attempt", "epoch", "run_id",
                "request_id", "service_generation"}:
            raise DispatchOutcomeUnknown("completed dispatch binding is malformed")
        if any(dispatch.get(field) != accepted.get(field) for field in (
                "principal", "task_id", "slot", "attempt", "epoch", "run_id",
                "request_id", "service_generation")):
            raise DispatchOutcomeUnknown("completed dispatch differs from the accepted instruction")
        receipt = result["execution"].get("receipt")
        grant_request_id = result["execution"].get("request_id")
        if not isinstance(receipt, dict) or not isinstance(grant_request_id, str) or not grant_request_id:
            raise DispatchOutcomeUnknown("completed Runner receipt is malformed")
        attestation = receipt.get("runner_attestation")
        request = attestation.get("request") if isinstance(attestation, dict) else None
        if (not isinstance(request, dict)
                or request.get("request_id") != grant_request_id
                or request.get("task_id") != accepted.get("task_id")
                or request.get("slot") != accepted.get("slot")
                or request.get("attempt") != accepted.get("attempt")
                or request.get("epoch") != accepted.get("epoch")
                or receipt.get("task_id") != accepted.get("task_id")
                or receipt.get("slot") != accepted.get("slot")
                or receipt.get("attempt") != accepted.get("attempt")
                or receipt.get("epoch") != accepted.get("epoch")
                or receipt.get("manifest_sha256") != accepted.get("manifest_digest")):
            raise DispatchOutcomeUnknown("completed Runner receipt differs from the accepted instruction")
        return result
