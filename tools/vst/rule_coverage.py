"""Truthful rule coverage and finding evidence map (S5-D, VST-041).

Pure, deterministic stdlib code: no model call, no network, no signing, no analyzer
execution. It owns three things:

  1. the committed, frozen required-rule catalog (docs/qa/aeve_required_rules.json):
     which AEVE rule ids are REQUIRED for a v3 StaticAnalysis receipt. A rule is
     REQUIRED only when it is linked to a committed S4 seeded-defect fixture id;
     every other rule is OPTIONAL with the explicit marker NO_FIXTURE. Rule ids
     must exist in the pinned AEVE g2 inventory; nothing is mapped by assumption;
  2. a closed-shape loader/validator with a sha256 digest over canonical bytes;
  3. build_static_coverage: v3 StaticAnalysis receipt body fields derived from an
     AnalysisReport plus the catalog, with a finding -> evidence map. FULL only
     when every catalog-required rule is SUPPORTED_AND_CHECKED and none is
     unsupported. An empty findings list is "clean" only under FULL coverage.

Optional rules never widen the mandatory denominator. Gate wiring is S5-E.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Collection, Mapping

from .analyzer_adapter import AEVE_G2_RULE_INVENTORY, AnalysisReport, static_analysis_fields
from .contracts import (
    COVERAGE,
    FINDING_FIELDS,
    FINDING_SEVERITY,
    MISSING_ARTIFACT_DIGEST,
    RULE_STATUS,
    ContractError,
    canonical_bytes,
)

CATALOG_SCHEMA_VERSION = 1
CATALOG_FIELDS = ("schema_version", "catalog_id", "aeve_rules_version", "s4_catalog", "note", "rules")
ENTRY_FIELDS = ("rule_id", "requirement", "fixture_id", "marker")
REQUIREMENTS = frozenset({"REQUIRED", "OPTIONAL"})
MARKERS = frozenset({"FIXTURE_LINKED", "NO_FIXTURE"})
DEFAULT_CATALOG_PATH = Path("docs/qa/aeve_required_rules.json")
MAX_CATALOG_BYTES = 1_000_000
_HEX64 = re.compile(r"[0-9a-f]{64}")
_FIXTURE_ID = re.compile(r"SF-[0-9]{3,}")


class CoverageError(ValueError):
    """Typed refusal for catalog, status and finding problems (AC-8)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class RuleCatalog:
    body: Mapping[str, Any]
    required_rule_ids: tuple[str, ...]  # sorted, unique
    optional_rule_ids: tuple[str, ...]  # sorted, unique
    fixture_by_rule: Mapping[str, str]  # required rule -> S4 fixture id
    sha256: str  # over canonical bytes of ``body``


# ------------------------------------------------------------------- catalog


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise CoverageError("CATALOG_INVALID", f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def _reject_constant(name: str) -> Any:
    raise CoverageError("CATALOG_INVALID", f"non-finite JSON constant {name}")


def s4_fixture_ids(s4_catalog: object) -> frozenset[str]:
    """Fixture ids of an already-parsed S4 seeded-failure catalog (closed, unique)."""
    fixtures = s4_catalog.get("fixtures") if isinstance(s4_catalog, dict) else None
    if not isinstance(fixtures, list) or not fixtures:
        raise CoverageError("S4_CATALOG_INVALID", "fixtures must be a non-empty list")
    ids: list[str] = []
    for index, item in enumerate(fixtures):
        fid = item.get("fixture_id") if isinstance(item, dict) else None
        if not isinstance(fid, str) or _FIXTURE_ID.fullmatch(fid) is None:
            raise CoverageError("S4_CATALOG_INVALID", f"fixtures[{index}].fixture_id is invalid")
        ids.append(fid)
    if len(set(ids)) != len(ids):
        raise CoverageError("S4_CATALOG_INVALID", "duplicate fixture_id")
    return frozenset(ids)


def validate_catalog(
    obj: object,
    *,
    fixture_ids: Collection[str],
    inventory: Collection[str] = AEVE_G2_RULE_INVENTORY,
    expected_sha256: str | None = None,
) -> RuleCatalog:
    """Closed-shape validation. ``fixture_ids`` is mandatory: a REQUIRED rule must name a
    fixture that exists in the S4 catalog, and every rule id must exist in ``inventory``."""
    if not isinstance(obj, dict) or tuple(sorted(obj)) != tuple(sorted(CATALOG_FIELDS)):
        raise CoverageError("CATALOG_INVALID", "top-level keys do not match the catalog shape")
    version = obj["schema_version"]
    if type(version) is not int or version != CATALOG_SCHEMA_VERSION:
        raise CoverageError("CATALOG_INVALID", f"schema_version must be {CATALOG_SCHEMA_VERSION}")
    for name in ("catalog_id", "aeve_rules_version", "s4_catalog", "note"):
        if not isinstance(obj[name], str) or not obj[name].strip():
            raise CoverageError("CATALOG_INVALID", f"{name}: must be a non-empty string")
    rules = obj["rules"]
    if not isinstance(rules, list):
        raise CoverageError("CATALOG_INVALID", "rules must be a list")
    known_fixtures = frozenset(fixture_ids)
    known_rules = frozenset(inventory)
    ids: list[str] = []
    required: list[str] = []
    optional: list[str] = []
    fixture_by_rule: dict[str, str] = {}
    for index, entry in enumerate(rules):
        ctx = f"rules[{index}]"
        if not isinstance(entry, dict) or tuple(sorted(entry)) != tuple(sorted(ENTRY_FIELDS)):
            raise CoverageError("CATALOG_INVALID", f"{ctx}: keys do not match the entry shape")
        rule_id, requirement, fixture_id, marker = (entry[k] for k in ENTRY_FIELDS)
        if not isinstance(rule_id, str) or not rule_id or rule_id.strip() != rule_id:
            raise CoverageError("CATALOG_INVALID", f"{ctx}.rule_id: must be a trimmed non-empty string")
        if rule_id not in known_rules:
            raise CoverageError("RULE_UNKNOWN", f"{ctx}: {rule_id!r} is not in the AEVE rule inventory")
        if requirement not in REQUIREMENTS or marker not in MARKERS:
            raise CoverageError("CATALOG_INVALID", f"{ctx}: requirement/marker outside the closed enums")
        if requirement == "REQUIRED":
            if marker != "FIXTURE_LINKED" or not isinstance(fixture_id, str) or fixture_id not in known_fixtures:
                raise CoverageError(
                    "REQUIRED_WITHOUT_FIXTURE", f"{ctx}: a REQUIRED rule needs a FIXTURE_LINKED S4 fixture id"
                )
            required.append(rule_id)
            fixture_by_rule[rule_id] = fixture_id
        else:
            if marker != "NO_FIXTURE" or fixture_id is not None:
                raise CoverageError("CATALOG_INVALID", f"{ctx}: an OPTIONAL rule must be NO_FIXTURE with null fixture_id")
            optional.append(rule_id)
        ids.append(rule_id)
    if len(set(ids)) != len(ids):
        raise CoverageError("CATALOG_INVALID", "rules: duplicate rule_id")
    if ids != sorted(ids):
        raise CoverageError("CATALOG_INVALID", "rules: must be sorted by rule_id")
    try:
        digest = hashlib.sha256(canonical_bytes(obj)).hexdigest()
    except ContractError as exc:
        raise CoverageError("CATALOG_INVALID", str(exc)) from exc
    if expected_sha256 is not None and digest != expected_sha256:
        raise CoverageError("CATALOG_DIGEST_MISMATCH", "catalog bytes differ from the frozen digest")
    return RuleCatalog(
        body=obj,
        required_rule_ids=tuple(required),
        optional_rule_ids=tuple(optional),
        fixture_by_rule=dict(fixture_by_rule),
        sha256=digest,
    )


def _read_json(path: Path) -> object:
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_CATALOG_BYTES + 1)
        if len(data) > MAX_CATALOG_BYTES:
            raise CoverageError("CATALOG_INVALID", f"{path.name}: too large")
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, CoverageError):
            raise
        raise CoverageError("CATALOG_UNREADABLE", f"{path.name}: {type(exc).__name__}") from exc


def load_catalog(
    repo_root: str | Path,
    *,
    catalog_path: str | Path = DEFAULT_CATALOG_PATH,
    expected_sha256: str | None = None,
    inventory: Collection[str] = AEVE_G2_RULE_INVENTORY,
) -> RuleCatalog:
    """Read the committed catalog and the S4 catalog it names (relative to ``repo_root``)."""
    root = Path(repo_root)
    body = _read_json(root / catalog_path)
    s4_rel = body.get("s4_catalog") if isinstance(body, dict) else None
    if not isinstance(s4_rel, str) or not s4_rel or s4_rel.startswith(("/", "\\")) or ".." in Path(s4_rel).parts:
        raise CoverageError("CATALOG_INVALID", "s4_catalog must be a repo-relative path")
    fixtures = s4_fixture_ids(_read_json(root / s4_rel))
    return validate_catalog(body, fixture_ids=fixtures, inventory=inventory, expected_sha256=expected_sha256)


def require_catalog_matches_manifest(manifest_v3: object, catalog: RuleCatalog) -> None:
    """Exact equality of the v3 manifest's required_rule_ids and the catalog's required set."""
    if not isinstance(manifest_v3, dict) or manifest_v3.get("contract_version") != 3:
        raise CoverageError("MANIFEST_NOT_V3", "manifest must be a v3 manifest")
    declared = manifest_v3.get("required_rule_ids")
    if not isinstance(declared, list) or not all(isinstance(r, str) for r in declared):
        raise CoverageError("MANIFEST_RULES_INVALID", "required_rule_ids must be a list of strings")
    if len(set(declared)) != len(declared) or declared != sorted(declared):
        raise CoverageError("MANIFEST_RULES_INVALID", "required_rule_ids must be sorted and unique")
    expected = list(catalog.required_rule_ids)
    if declared != expected:
        extra = sorted(set(declared) - set(expected))
        missing = sorted(set(expected) - set(declared))
        raise CoverageError(
            "MANIFEST_CATALOG_MISMATCH",
            f"manifest rules differ from the frozen catalog; not in catalog: {extra}; missing from manifest: {missing}",
        )


# ------------------------------------------------------------ coverage builder


def _bad(code: str, message: str) -> CoverageError:
    return CoverageError(code, message)


def build_static_coverage(report: AnalysisReport, catalog: RuleCatalog) -> dict[str, Any]:
    """Derive the v3 StaticAnalysis body fields and the finding evidence map.

    Returns ``{"fields", "required_rule_ids", "evidence_map", "clean"}``. ``fields`` is
    static_analysis_fields(report) re-derived against ``catalog``: required_rule_ids is the
    catalog-required set, every required rule has exactly one status, coverage is recomputed
    and must equal the report's. ``clean`` is True only for FULL coverage with no findings.
    """
    required = list(catalog.required_rule_ids)
    if not required:
        raise _bad("EMPTY_REQUIRED_SET", "catalog has no required rules; coverage would be vacuous")
    body = report.body
    statuses = body.get("rule_statuses")
    if not isinstance(statuses, list):
        raise _bad("STATUS_MALFORMED", "rule_statuses must be a list")
    checked: list[str] = []
    unsupported: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(statuses):
        ctx = f"rule_statuses[{index}]"
        if not isinstance(item, dict) or set(item) != {"rule_id", "status"}:
            raise _bad("STATUS_MALFORMED", f"{ctx}: shape mismatch")
        rule_id, status = item["rule_id"], item["status"]
        if not isinstance(rule_id, str) or not rule_id:
            raise _bad("STATUS_MALFORMED", f"{ctx}: invalid rule_id")
        if not isinstance(status, str) or status not in RULE_STATUS:
            raise _bad("STATUS_UNKNOWN", f"{ctx}: status outside the closed enum")
        if rule_id in seen:
            raise _bad("STATUS_DUPLICATE", f"{ctx}: duplicate status for {rule_id!r}")
        seen.add(rule_id)
        (checked if status == "SUPPORTED_AND_CHECKED" else unsupported).append(rule_id)
    unknown = sorted(seen - set(required))
    if unknown:
        raise _bad("STATUS_UNKNOWN_RULE", f"status for rule(s) outside the catalog required set: {unknown}")
    omitted = sorted(set(required) - seen)
    if omitted:
        raise _bad("STATUS_OMITTED", f"no status for required rule(s): {omitted}")
    if [i["rule_id"] for i in statuses] != required:
        raise _bad("STATUS_UNSORTED", "rule_statuses must be sorted by rule_id")
    if set(checked) & set(unsupported):
        raise _bad("STATUS_OVERLAP", "a rule is both checked and unsupported")
    if body.get("covered_rules") != sorted(checked) or body.get("unsupported_rules") != sorted(unsupported):
        raise _bad("STATUS_OVERLAP", "covered_rules/unsupported_rules contradict rule_statuses")
    coverage = "FULL" if not unsupported else ("PARTIAL" if checked else "NOT_COVERED")
    if coverage not in COVERAGE or body.get("coverage") != coverage:
        raise _bad("COVERAGE_CONTRADICTION", f"report coverage contradicts rule statuses (expected {coverage})")

    scope = body.get("analysis_scope")
    if not isinstance(scope, list) or not scope:
        raise _bad("FINDING_MALFORMED", "analysis_scope must be a non-empty list")
    findings = body.get("findings")
    if not isinstance(findings, list):
        raise _bad("FINDING_MALFORMED", "findings must be a list")
    checked_set = set(checked)
    evidence_map: list[dict[str, Any]] = []
    keys: set[str] = set()
    for index, item in enumerate(findings):
        ctx = f"findings[{index}]"
        if not isinstance(item, dict) or tuple(sorted(item)) != tuple(sorted(FINDING_FIELDS)):
            raise _bad("FINDING_MALFORMED", f"{ctx}: shape mismatch")
        rule_id, severity = item["rule_id"], item["severity"]
        if not isinstance(rule_id, str) or rule_id not in checked_set:
            raise _bad("FINDING_RULE_NOT_CHECKED", f"{ctx}: rule_id is not a checked required rule")
        if not isinstance(severity, str) or severity not in FINDING_SEVERITY:
            raise _bad("FINDING_MALFORMED", f"{ctx}: severity outside the closed enum")
        path, ref, sha, line = item["path"], item["evidence_ref"], item["evidence_sha256"], item["line"]
        if not isinstance(path, str) or path not in scope:
            raise _bad("FINDING_MALFORMED", f"{ctx}: path is not in analysis_scope")
        if not isinstance(ref, str) or not ref or ref != path:
            raise _bad("FINDING_EVIDENCE_INCOMPLETE", f"{ctx}: evidence_ref must name the finding path")
        if not isinstance(sha, str) or _HEX64.fullmatch(sha) is None or sha == MISSING_ARTIFACT_DIGEST:
            raise _bad("FINDING_EVIDENCE_INCOMPLETE", f"{ctx}: evidence_sha256 must be a non-zero sha256")
        if type(line) is not int or line < 1:
            raise _bad("FINDING_MALFORMED", f"{ctx}: invalid line")
        key = canonical_bytes(item).decode("ascii")
        if key in keys:
            raise _bad("FINDING_DUPLICATE", f"{ctx}: duplicate finding")
        keys.add(key)
        evidence_map.append({
            "finding_sha256": hashlib.sha256(key.encode("ascii")).hexdigest(),
            "rule_id": rule_id,
            "severity": severity,
            "evidence_ref": ref,
            "evidence_sha256": sha,
        })

    fields = static_analysis_fields(report)
    fields["rule_statuses"] = [{"rule_id": r, "status": s} for r, s in sorted(
        [(r, "SUPPORTED_AND_CHECKED") for r in checked] + [(r, "UNSUPPORTED") for r in unsupported]
    )]
    fields["covered_rules"] = sorted(checked)
    fields["unsupported_rules"] = sorted(unsupported)
    fields["coverage"] = coverage
    return {
        "fields": fields,
        "required_rule_ids": required,  # manifest-side list; not a v3 receipt field
        "evidence_map": evidence_map,
        "clean": coverage == "FULL" and not findings,
    }
