"""Default-off root-bound signer for the unchanged dispatch-instruction v1 wire format."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from typing import Any

from .contracts import ContractError, canonical_bytes
from .dispatch_instruction import DISPATCH_INSTRUCTION_PURPOSE
from .dispatch_issuance import (
    canonical_sha256, freeze_issuance_intent, validate_key_binding,
)
from .execution_grant import _openssl_signature

_ISSUANCE_PROOF_SEAL = object()


class VerifiedDispatchIssuance:
    """In-process root verification result bound to one immutable envelope and signer."""

    __slots__ = ("_intent", "_envelope", "fingerprint", "_seal")

    def __init__(self, seal: object, intent: dict, envelope: dict, fingerprint: str):
        if seal is not _ISSUANCE_PROOF_SEAL:
            raise ContractError("dispatch issuance proof must be created by the root verifier")
        object.__setattr__(self, "_intent", canonical_bytes(intent))
        object.__setattr__(self, "_envelope", canonical_bytes(envelope))
        object.__setattr__(self, "fingerprint", fingerprint)
        object.__setattr__(self, "_seal", seal)

    def __setattr__(self, name, value):
        raise AttributeError("verified dispatch proof is immutable")

    @property
    def intent(self) -> dict:
        return json.loads(self._intent)

    @property
    def envelope(self) -> dict:
        return json.loads(self._envelope)


def verify_issued_instruction(store: Any, envelope: dict, *, key_id: str,
                              public_key_path: str, fingerprint: str,
                              openssl_path: str) -> VerifiedDispatchIssuance:
    """Verify the exact completed journal envelope outside SQL and return a sealed context."""
    from .dispatch_instruction import dispatch_instruction_signing_bytes
    def verify(signer: dict, payload: bytes, signature: bytes) -> bool:
        return (
            signer == {"key_id": key_id, "key_class": "DELEGATED_V1",
                       "purpose": DISPATCH_INSTRUCTION_PURPOSE,
                       "public_key_fingerprint": fingerprint}
            and public_key_fingerprint(public_key_path) == fingerprint
            and _openssl_signature(openssl_path, key_path=public_key_path,
                                   payload=payload, signature=signature, private=False) is True
        )

    verified = store.dispatch_issuance_for_envelope(envelope, verify)
    if verified["state"] != "COMPLETED":
        raise ContractError("dispatch instruction lacks a verified issuance completion")
    intent = verified["intent"]
    if (intent["signer"]["key_id"] != key_id
            or intent["signer"]["public_key_fingerprint"] != fingerprint
            or dispatch_instruction_signing_bytes(envelope) !=
            b"VST_S2_DISPATCH_INSTRUCTION_V1\0" + canonical_bytes(
                {k: v for k, v in envelope.items() if k != "signature"})):
        raise ContractError("dispatch issuance context does not bind the exact envelope")
    return VerifiedDispatchIssuance(_ISSUANCE_PROOF_SEAL, intent, envelope, fingerprint)


def is_verified_issuance_context(value: Any) -> bool:
    return isinstance(value, VerifiedDispatchIssuance) and value._seal is _ISSUANCE_PROOF_SEAL


def public_key_fingerprint(path: str) -> str:
    """Fingerprint the exact root-pinned public-key file bytes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                    or info.st_mode & 0o022 or info.st_size < 1 or info.st_size > 65536):
                raise ContractError("dispatch signer public key file is unsafe")
            chunks = []
            remaining = 65537
            while remaining:
                chunk = os.read(fd, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
        finally:
            os.close(fd)
    except OSError as exc:
        raise ContractError("dispatch signer public key is unavailable") from exc
    if not data or len(data) > 65536:
        raise ContractError("dispatch signer public key file is invalid")
    return hashlib.sha256(data).hexdigest()


def issue_frozen_dispatch(store: Any, *, handoff: dict, policy: dict,
                          policy_sha256: str, authority_expires_at_utc: str,
                          signer: dict, private_key_path: str, public_key_path: str,
                          openssl_path: str, issuer_max_ttl_seconds: int,
                          minimum_safety_slack_seconds: int, now,
                          authority_provider=None, before_sign=None) -> dict:
    """Reserve, claim, sign once, verify and durably complete one frozen intent."""
    binding = validate_key_binding(signer)
    if (binding["purpose"] != DISPATCH_INSTRUCTION_PURPOSE
            or binding["public_key_fingerprint"] != public_key_fingerprint(public_key_path)):
        raise ContractError("dispatch signer fingerprint does not match the root public key")
    frozen = store.existing_dispatch_issuance(handoff["assignment_operation_id"])
    if frozen is None:
        frozen = freeze_issuance_intent(
            handoff, policy={"policy": policy, "policy_sha256": policy_sha256}, signer=binding,
            expires_at=_bounded_expiry(now, issuer_max_ttl_seconds, authority_expires_at_utc,
                                       policy["expires_at_utc"], handoff["expires_at_utc"]),
            authority_expires_at_utc=authority_expires_at_utc,
            issuer_max_ttl_seconds=issuer_max_ttl_seconds,
            minimum_safety_slack_seconds=minimum_safety_slack_seconds, now=now,
        )
    else:
        if (frozen["handoff"] != handoff or frozen["policy"] != policy
                or frozen["signer"] != binding
                or frozen["issuer_max_ttl_seconds"] != issuer_max_ttl_seconds
                or frozen["minimum_safety_slack_seconds"] != minimum_safety_slack_seconds
                or frozen["unsigned"]["expires_at"] > min(
                    authority_expires_at_utc, policy["expires_at_utc"], handoff["expires_at_utc"],
                )):
            raise ContractError("existing issuance identity or current authority changed")
        stored_expiry = datetime.strptime(
            frozen["unsigned"]["expires_at"], "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc)
        if stored_expiry <= now:
            raise ContractError("existing dispatch issuance is expired")
    if authority_provider is None:
        raise ContractError("fresh root authority provider is required")
    authority = authority_provider(frozen)
    state = store.reserve_dispatch_issuance(frozen, authority_snapshot=authority)
    def verify(exact_signer: dict, payload: bytes, signed: bytes) -> bool:
        return (
            exact_signer == binding
            and public_key_fingerprint(public_key_path) == binding["public_key_fingerprint"]
            and _openssl_signature(openssl_path, key_path=public_key_path,
                                   payload=payload, signature=signed, private=False) is True
        )

    if state["state"] == "VERIFY_REQUIRED":
        return store.verify_dispatch_issuance_completion(frozen["operation_key"], verify)["envelope"]
    if state["state"] != "PENDING":
        raise ContractError("dispatch issuance is not safely signable")
    intent_digest = canonical_sha256(frozen)
    authority = authority_provider(frozen)
    store.start_dispatch_issuance(
        frozen["operation_key"], intent_digest, authority_snapshot=authority,
    )
    try:
        latest_authority = authority_provider(frozen)
        store.assert_dispatch_issuance_authority(frozen, authority_snapshot=latest_authority)
        if (public_key_fingerprint(public_key_path) != binding["public_key_fingerprint"]
                or before_sign is None or before_sign(frozen) is not True):
            raise ContractError("current root authority changed before signer entry")
        signature = _openssl_signature(
            openssl_path, key_path=private_key_path,
            payload=b"VST_S2_DISPATCH_INSTRUCTION_V1\0" + canonical_bytes(frozen["unsigned"]),
            private=True,
        )
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise ContractError("dispatch signer returned malformed Ed25519 output")
        envelope = {
            **frozen["unsigned"],
            "signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        }

        completion_authority = authority_provider(frozen)
        completed = store.complete_dispatch_issuance(
            frozen["operation_key"], intent_digest, envelope, verify,
            authority_snapshot=completion_authority,
        )
        return completed["envelope"]
    except BaseException as exc:
        try:
            store.mark_dispatch_issuance_unknown(
                frozen["operation_key"], intent_digest, type(exc).__name__,
            )
        finally:
            raise


def _bounded_expiry(now, maximum_ttl: int, *authorities: str) -> str:
    from datetime import datetime, timedelta, timezone
    if (type(maximum_ttl) is not int or maximum_ttl <= 0 or now.tzinfo is None
            or now.utcoffset() != timezone.utc.utcoffset(now)):
        raise ContractError("dispatch issuer requires finite positive TTL and UTC clock")
    prepared = now.replace(microsecond=0)
    try:
        ttl_end = prepared + timedelta(seconds=maximum_ttl)
    except OverflowError as exc:
        raise ContractError("dispatch issuer TTL is out of bounds") from exc
    limits = [ttl_end]
    for value in authorities:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError) as exc:
            raise ContractError("dispatch issuer authority expiry is malformed") from exc
        limits.append(parsed)
    return min(limits).strftime("%Y-%m-%dT%H:%M:%SZ")
