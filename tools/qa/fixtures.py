"""Validate synthetic QA fixtures without modifying product code or catalog data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .registry import RegistryError, ValidatedRegistry, _exact_keys, _read_repo_file


class FixtureCatalogError(ValueError):
    """Raised when seeded-failure fixture evidence is not bound to a test selector."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def input_sha256(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def load_fixture_catalog(
    root: Path,
    registry: ValidatedRegistry,
    relative_path: str = "docs/qa/fixtures.json",
) -> tuple[dict[str, Any], str]:
    raw = _read_repo_file(root, relative_path)
    try:
        catalog = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        raise FixtureCatalogError("fixture catalog is not valid UTF-8 JSON") from None
    catalog = _exact_keys(
        catalog,
        {"schema_version", "status", "reason", "fixtures"},
        "fixture catalog",
    )
    if catalog["schema_version"] != 1:
        raise FixtureCatalogError("fixture catalog schema version is unsupported")
    status = catalog["status"]
    fixtures = catalog["fixtures"]
    if status not in {"SUPPORTED", "NOT_RUN"} or not isinstance(fixtures, list):
        raise FixtureCatalogError("fixture catalog status or fixtures field is invalid")
    if status == "NOT_RUN" and (not isinstance(catalog["reason"], str) or not catalog["reason"].strip()):
        raise FixtureCatalogError("NOT_RUN fixture catalog requires an exact reason")
    if status == "SUPPORTED" and (not fixtures or catalog["reason"] is not None):
        raise FixtureCatalogError("SUPPORTED fixture catalog requires fixtures and no reason")

    known_ids = set(registry.selectors_by_id)
    seeded_ids = set(registry.category_test_ids["seeded-failure"])
    seen: set[str] = set()
    for index, raw_fixture in enumerate(fixtures):
        fixture = _exact_keys(
            raw_fixture,
            {
                "fixture_id",
                "source_interface",
                "input",
                "input_sha256",
                "expected_rejection",
                "test_id",
            },
            f"fixtures[{index}]",
        )
        fixture_id = fixture["fixture_id"]
        if not isinstance(fixture_id, str) or not fixture_id.startswith("QA-SEED-"):
            raise FixtureCatalogError(f"fixtures[{index}].fixture_id is invalid")
        if fixture_id in seen:
            raise FixtureCatalogError(f"duplicate fixture id: {fixture_id}")
        seen.add(fixture_id)
        source_interface = fixture["source_interface"]
        if (
            not isinstance(source_interface, str)
            or not source_interface.startswith("tools.vst.")
            or "/" in source_interface
        ):
            raise FixtureCatalogError(f"fixtures[{index}].source_interface is invalid")
        input_record = fixture["input"]
        if not isinstance(input_record, dict):
            raise FixtureCatalogError(f"fixtures[{index}].input must be a JSON object")
        digest = fixture["input_sha256"]
        if not isinstance(digest, str) or digest != input_sha256(input_record):
            raise FixtureCatalogError(f"fixtures[{index}].input_sha256 does not match input")
        expected = fixture["expected_rejection"]
        if expected not in {"FAIL", "BLOCKED", "NOT_RUN", "INCONCLUSIVE"}:
            raise FixtureCatalogError(f"fixtures[{index}] expected_rejection is approving or invalid")
        test_id = fixture["test_id"]
        if not isinstance(test_id, str) or test_id not in known_ids or test_id not in seeded_ids:
            raise FixtureCatalogError(f"fixtures[{index}] test_id is not a seeded-failure selector")

    if status == "SUPPORTED" and set(seeded_ids) != {fixture["test_id"] for fixture in fixtures}:
        raise FixtureCatalogError("seeded-failure selectors and fixture test IDs do not match")
    if status == "NOT_RUN" and (fixtures or seeded_ids):
        raise FixtureCatalogError("NOT_RUN fixture catalog cannot claim fixture selectors")
    return catalog, hashlib.sha256(raw).hexdigest()


def record_fixture_observation(fixture_id: str, observed_rejection: str) -> None:
    """Let a fixture test report the actual non-approving product outcome to the QA plugin."""
    from .pytest_plugin import record_fixture_observation as _record

    _record(fixture_id, observed_rejection)
