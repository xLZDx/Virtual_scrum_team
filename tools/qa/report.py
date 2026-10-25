"""Canonical S4 report encoding, artifact hashing and semantic normalization."""

from __future__ import annotations

import hashlib
import json
from typing import Any


VOLATILE_FIELDS = frozenset({"created_utc", "duration_seconds", "run_id", "artifact_ranges"})
def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized_report(report: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        key: value
        for key, value in report.items()
        if key not in VOLATILE_FIELDS and key != "normalized_sha256"
    }
    return normalized


def set_normalized_digest(report: dict[str, Any]) -> str:
    digest = sha256_bytes(canonical_json(normalized_report(report)))
    report["normalized_sha256"] = digest
    return digest


def encode_report(report: dict[str, Any]) -> bytes:
    set_normalized_digest(report)
    return canonical_json(report) + b"\n"
