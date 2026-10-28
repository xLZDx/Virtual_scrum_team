"""Dispatch-owner RPC client that forwards only verified signed instructions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import ContractError
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
        self.principal = principal
        self.trust_registry = trust_registry
        self.openssl_path = openssl_path
        self.transport = transport

    def submit(self, instruction: object) -> dict:
        verified = verify_dispatch_instruction(
            instruction, self.trust_registry, expected_principal=self.principal,
            openssl_path=self.openssl_path,
        )
        # Preserve the exact parsed envelope: no caller-supplied principal or field projection.
        try:
            result = self.transport.submit_dispatch_intent(instruction=verified["instruction"])
            if not isinstance(result, dict) or "instruction" not in result:
                raise ContractError("Supervisor returned a malformed dispatch-intent response")
            accepted = validate_dispatch_instruction(result["instruction"])
            if (accepted != verified["instruction"] or result.get("key_id") != accepted["key_id"]
                    or any(result.get(field) != accepted[field] for field in (
                        "task_id", "slot", "attempt", "epoch", "run_id", "request_id",
                    ))):
                raise ContractError(
                    "Supervisor response differs from the submitted signed dispatch instruction"
                )
        except Exception as exc:
            # Once the transport call starts, even an error or malformed reply may follow
            # a durable append. An exception cannot prove that the request was not accepted.
            raise DispatchOutcomeUnknown("Supervisor acceptance is not proven") from exc
        return result
