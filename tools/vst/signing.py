"""HMAC-SHA256 signing of receipts (runner-side) and waivers (operator-side).

The signature covers `label + canonical_bytes(obj)` where obj is the object
WITHOUT its 'signature' field. The label is a domain separator so that a
signature made for one object kind can never verify as another kind:
RECEIPT_LABEL for receipts, WAIVER_LABEL for operator waivers.

A key must be bytes (or bytearray) of length >= MIN_KEY_BYTES (32); anything
else raises ContractError. verify() returns False (never raises) for a
malformed object or signature; it raises only for an invalid key or label.
"""

from __future__ import annotations

import hashlib
import hmac

from .contracts import ContractError, canonical_bytes

RECEIPT_LABEL = b"vst-receipt-v1\0"
RECEIPT_V2_LABEL = b"vst-receipt-v2\0"
WAIVER_LABEL = b"vst-waiver-v1\0"
REVIEWER_LABEL = b"vst-independent-review-v2\0"
REVIEWER_REGISTRY_LABEL = b"vst-reviewer-registry-v2\0"
DIFF_GATE_LABEL = b"vst-diff-gate-v2\0"
SIGNING_REQUEST_LABEL = b"vst-runner-signing-request-v2\0"
OPERATOR_MANUAL_OVERRIDE_LABEL = b"vst-operator-manual-override-v1\0"
MIN_KEY_BYTES = 32


def _check_key(key: object) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES:
        raise ContractError(f"key: must be bytes of length >= {MIN_KEY_BYTES}")
    return bytes(key)


def _check_label(label: object) -> bytes:
    if not isinstance(label, (bytes, bytearray)) or len(label) == 0:
        raise ContractError("label: must be non-empty bytes")
    return bytes(label)


def sign(obj_without_signature: dict, key: bytes, label: bytes = RECEIPT_LABEL) -> str:
    """Return the HMAC-SHA256 hex digest over label + canonical object bytes."""
    raw_key = _check_key(key)
    raw_label = _check_label(label)
    if not isinstance(obj_without_signature, dict):
        raise ContractError("object: must be a dict")
    if "signature" in obj_without_signature:
        raise ContractError("object: must not contain 'signature' when signing")
    payload = raw_label + canonical_bytes(obj_without_signature)
    return hmac.new(raw_key, payload, hashlib.sha256).hexdigest()


def verify(obj: dict, key: bytes, label: bytes = RECEIPT_LABEL) -> bool:
    """True iff obj['signature'] matches the HMAC of the rest of the object."""
    raw_key = _check_key(key)
    raw_label = _check_label(label)
    if not isinstance(obj, dict):
        return False
    signature = obj.get("signature")
    if not isinstance(signature, str):
        return False
    body = {k: v for k, v in obj.items() if k != "signature"}
    try:
        expected = sign(body, raw_key, raw_label)
    except ContractError:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), signature.encode("utf-8"))
