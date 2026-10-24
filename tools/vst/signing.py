"""HMAC-SHA256 signing of receipts (runner-side) and verification (gate-side).

The signature covers canonical_bytes() of the receipt WITHOUT its
'signature' field. The key must be non-empty bytes; anything else raises
ContractError.
"""

from __future__ import annotations

import hashlib
import hmac

from .contracts import ContractError, canonical_bytes


def _check_key(key: object) -> bytes:
    if not isinstance(key, (bytes, bytearray)) or len(key) == 0:
        raise ContractError("key: must be non-empty bytes")
    return bytes(key)


def sign(receipt_without_signature: dict, key: bytes) -> str:
    """Return the HMAC-SHA256 hex digest over the canonical receipt bytes."""
    raw_key = _check_key(key)
    if not isinstance(receipt_without_signature, dict):
        raise ContractError("receipt: must be an object (dict)")
    if "signature" in receipt_without_signature:
        raise ContractError("receipt: must not contain 'signature' when signing")
    payload = canonical_bytes(receipt_without_signature)
    return hmac.new(raw_key, payload, hashlib.sha256).hexdigest()


def verify(receipt: dict, key: bytes) -> bool:
    """True iff receipt['signature'] matches the HMAC of the rest of the receipt."""
    raw_key = _check_key(key)
    if not isinstance(receipt, dict):
        return False
    signature = receipt.get("signature")
    if not isinstance(signature, str):
        return False
    body = {k: v for k, v in receipt.items() if k != "signature"}
    try:
        expected = sign(body, raw_key)
    except ContractError:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), signature.encode("utf-8"))
