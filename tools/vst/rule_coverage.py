"""Truthful rule coverage and finding evidence map (S5-D, VST-041).

Pure, deterministic stdlib code: no model call, no network, no signing, no analyzer
execution. It owns three things:

  1. the committed, frozen required-rule catalog (docs/qa/aeve_required_rules.json):
     which AEVE rule ids are REQUIRED for a v3 StaticAnalysis receipt. A rule is
     REQUIRED only when it is linked to a committed AF-### AEVE seeded-defect fixture that
     seeds that very rule (S4 SF-### fixtures seed no rule and are refused as links);
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
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any, Collection, Mapping

from .analyzer_adapter import AEVE_G2_RULE_INVENTORY, AnalysisReport, static_analysis_fields
from .contracts import (
    COVERAGE,
    FINDING_FIELDS,
    FINDING_SEVERITY,
    MISSING_ARTIFACT_DIGEST,
    RULE_STATUS,
    ContractError,
    _req_plain_repo_path,
    canonical_bytes,
)

CATALOG_SCHEMA_VERSION = 1
CATALOG_FIELDS = (
    "schema_version", "catalog_id", "aeve_rules_version", "s4_catalog", "s4_catalog_sha256",
    "aeve_fixture_index", "aeve_fixture_index_sha256", "note", "rules",
)
# The fixture index and every fixture file must live here (repo-relative, '/' separators).
AEVE_FIXTURES_DIR = "tests/qa/seeded_failure/aeve_fixtures"
AEVE_INDEX_FIELDS = ("schema_version", "note", "aeve_head", "command", "outcome", "fixtures")
AEVE_FIXTURE_FIELDS = (
    "fixture_id", "rule_slug", "rule_id", "defective", "defective_sha256", "clean", "clean_sha256",
    "copy_to", "expected_finding", "defective_outcome", "clean_outcome",
)
AEVE_EXPECTED_FINDING_FIELDS = ("rule_id", "path", "line")
ENTRY_FIELDS = ("rule_id", "requirement", "fixture_id", "marker")
REQUIREMENTS = frozenset({"REQUIRED", "OPTIONAL"})
MARKERS = frozenset({"FIXTURE_LINKED", "NO_FIXTURE"})
# Frozen pin: sha256 over the canonical bytes of docs/qa/aeve_required_rules.json. Any edit of the
# catalog (including its dependency digests) must change this constant in the same commit.
FROZEN_CATALOG_SHA256 = "13b80b2ec3ca1d50b07997077585e117825eef4e52fea96eeab7c7369f2e6b1a"
DEFAULT_CATALOG_PATH = Path("docs/qa/aeve_required_rules.json")
MAX_CATALOG_BYTES = 1_000_000
_HEX64 = re.compile(r"[0-9a-f]{64}")
_FIXTURE_ID = re.compile(r"SF-[0-9]{3,}")
_AEVE_FIXTURE_ID = re.compile(r"AF-[0-9]{3,}")


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


def _plain_rel(value: object, name: str, code: str) -> str:
    """Repo-relative '/' path: a string, no NUL/backslash, no '.'/'..'/empty segment, no drive or
    absolute form under either POSIX or Windows rules."""
    if not isinstance(value, str) or not value or "\0" in value or "\\" in value:
        raise CoverageError(code, f"{name}: must be a non-empty '/' path string")
    if PurePath(value).is_absolute() or PureWindowsPath(value).is_absolute():
        raise CoverageError(code, f"{name}: absolute path refused")
    win = PureWindowsPath(value)
    if win.drive or win.root or win.anchor or ":" in value:
        raise CoverageError(code, f"{name}: drive or anchor refused")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise CoverageError(code, f"{name}: empty, '.' or '..' segment refused")
    return value


def _resolve_under(base: Path, rel: object, name: str, code: str) -> Path:
    """Resolve ``rel`` below ``base``; the resolved path (symlinks followed) must stay inside."""
    _plain_rel(rel, name, code)
    real_base = base.resolve()
    resolved = (real_base / str(rel)).resolve()
    try:
        resolved.relative_to(real_base)
    except ValueError as exc:
        raise CoverageError(code, f"{name}: resolves outside {base.name!r}") from exc
    return resolved


def _read_bytes(path: Path, code: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_CATALOG_BYTES + 1)
    except OSError as exc:
        raise CoverageError(code, f"{path.name}: {type(exc).__name__}") from exc
    if len(data) > MAX_CATALOG_BYTES:
        raise CoverageError(code, f"{path.name}: too large")
    return data


def aeve_fixture_rules(index: object, fixtures_dir: Path) -> dict[str, str]:
    """AF-### fixture id -> the AEVE rule id it seeds, from a parsed aeve_fixtures/index.json.

    Closed shape, and integrity against the files in ``fixtures_dir``: paths stay under it, the
    defective/clean files exist and match the indexed sha256, differ from each other, the slug
    matches the directory and the rule id, copy_to equals the expected finding path, and the
    expected line is within the defective file. expected_finding must name the same rule id."""
    code = "AEVE_INDEX_INVALID"
    if not isinstance(index, dict) or tuple(sorted(index)) != tuple(sorted(AEVE_INDEX_FIELDS)):
        raise CoverageError(code, "top-level keys do not match the index shape")
    if type(index["schema_version"]) is not int or index["schema_version"] != 1:
        raise CoverageError(code, "schema_version must be 1")
    fixtures = index["fixtures"]
    if not isinstance(fixtures, list) or not fixtures:
        raise CoverageError(code, "fixtures must be a non-empty list")
    out: dict[str, str] = {}
    for position, item in enumerate(fixtures):
        ctx = f"fixtures[{position}]"
        if not isinstance(item, dict) or tuple(sorted(item)) != tuple(sorted(AEVE_FIXTURE_FIELDS)):
            raise CoverageError(code, f"{ctx}: keys do not match the fixture shape")
        fid, rule_id, slug = item["fixture_id"], item["rule_id"], item["rule_slug"]
        if not isinstance(fid, str) or _AEVE_FIXTURE_ID.fullmatch(fid) is None:
            raise CoverageError(code, f"{ctx}.fixture_id is invalid")
        if not isinstance(rule_id, str) or not rule_id:
            raise CoverageError(code, f"{ctx}.rule_id is invalid")
        if not isinstance(slug, str) or slug != rule_id.lower():
            raise CoverageError("FIXTURE_INTEGRITY", f"{ctx}.rule_slug must equal the lower-cased rule_id")
        for name in ("defective_sha256", "clean_sha256"):
            if not isinstance(item[name], str) or _HEX64.fullmatch(item[name]) is None:
                raise CoverageError(code, f"{ctx}.{name}: must be a sha256")
        expected = item["expected_finding"]
        if (
            not isinstance(expected, dict)
            or tuple(sorted(expected)) != tuple(sorted(AEVE_EXPECTED_FINDING_FIELDS))
            or expected["rule_id"] != rule_id
        ):
            raise CoverageError(code, f"{ctx}.expected_finding must name the fixture rule_id")
        if fid in out:
            raise CoverageError(code, f"{ctx}: duplicate fixture_id")
        # --- integrity against the committed files
        data: dict[str, bytes] = {}
        for kind in ("defective", "clean"):
            rel = item[kind]
            _plain_rel(rel, f"{ctx}.{kind}", "FIXTURE_INTEGRITY")
            if rel.split("/")[:2] != [slug, kind]:
                raise CoverageError("FIXTURE_INTEGRITY", f"{ctx}.{kind}: must live under '{slug}/{kind}/'")
            data[kind] = _read_bytes(_resolve_under(fixtures_dir, rel, f"{ctx}.{kind}", "FIXTURE_INTEGRITY"),
                                     "FIXTURE_INTEGRITY")
            if hashlib.sha256(data[kind]).hexdigest() != item[f"{kind}_sha256"]:
                raise CoverageError("FIXTURE_INTEGRITY", f"{ctx}.{kind}: bytes differ from the indexed sha256")
        if data["defective"] == data["clean"]:
            raise CoverageError("FIXTURE_INTEGRITY", f"{ctx}: defective and clean files are identical")
        _plain_rel(item["copy_to"], f"{ctx}.copy_to", "FIXTURE_INTEGRITY")
        if expected["path"] != item["copy_to"]:
            raise CoverageError("FIXTURE_INTEGRITY", f"{ctx}: expected_finding.path must equal copy_to")
        line = expected["line"]
        if type(line) is not int or line < 1 or line > len(data["defective"].splitlines()):
            raise CoverageError("FIXTURE_INTEGRITY", f"{ctx}: expected_finding.line is outside the defective file")
        out[fid] = rule_id
    if len(set(out.values())) != len(out):
        raise CoverageError(code, "two fixtures seed the same rule_id")
    return out


def validate_catalog(
    obj: object,
    *,
    fixtures: Mapping[str, str | None],
    expected_sha256: str,
    inventory: Collection[str] = AEVE_G2_RULE_INVENTORY,
) -> RuleCatalog:
    """Closed-shape validation. ``fixtures`` maps every known fixture id to the rule id it
    seeds (AF-### from aeve_fixture_rules) or None (SF-### from the S4 catalog, which seed VST
    gate failures, not rules). A REQUIRED rule must name a fixture that seeds that very rule, so
    an SF-### link is refused. Every rule id must exist in ``inventory``. ``expected_sha256``
    is the mandatory frozen pin over the canonical bytes of ``obj``."""
    if not isinstance(obj, dict) or tuple(sorted(obj)) != tuple(sorted(CATALOG_FIELDS)):
        raise CoverageError("CATALOG_INVALID", "top-level keys do not match the catalog shape")
    version = obj["schema_version"]
    if type(version) is not int or version != CATALOG_SCHEMA_VERSION:
        raise CoverageError("CATALOG_INVALID", f"schema_version must be {CATALOG_SCHEMA_VERSION}")
    for name in ("catalog_id", "aeve_rules_version", "s4_catalog", "aeve_fixture_index", "note"):
        if not isinstance(obj[name], str) or not obj[name].strip():
            raise CoverageError("CATALOG_INVALID", f"{name}: must be a non-empty string")
    for name in ("s4_catalog_sha256", "aeve_fixture_index_sha256"):
        if not isinstance(obj[name], str) or _HEX64.fullmatch(obj[name]) is None:
            raise CoverageError("CATALOG_INVALID", f"{name}: must be a sha256")
    if not isinstance(expected_sha256, str) or _HEX64.fullmatch(expected_sha256) is None:
        raise CoverageError("CATALOG_PIN_REQUIRED", "expected_sha256 must be the frozen 64-hex catalog digest")
    rules = obj["rules"]
    if not isinstance(rules, list):
        raise CoverageError("CATALOG_INVALID", "rules must be a list")
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
        if (
            not isinstance(requirement, str) or requirement not in REQUIREMENTS
            or not isinstance(marker, str) or marker not in MARKERS
        ):
            raise CoverageError("CATALOG_INVALID", f"{ctx}: requirement/marker outside the closed enums")
        if requirement == "REQUIRED":
            if marker != "FIXTURE_LINKED" or not isinstance(fixture_id, str) or fixture_id not in fixtures:
                raise CoverageError(
                    "REQUIRED_WITHOUT_FIXTURE", f"{ctx}: a REQUIRED rule needs a FIXTURE_LINKED known fixture id"
                )
            seeded = fixtures[fixture_id]
            if seeded is None:
                raise CoverageError(
                    "FIXTURE_NOT_RULE_LINKED", f"{ctx}: fixture {fixture_id} does not seed any AEVE rule"
                )
            if seeded != rule_id:
                raise CoverageError("FIXTURE_RULE_MISMATCH", f"{ctx}: fixture {fixture_id} seeds {seeded!r}")
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
    if digest != expected_sha256:
        raise CoverageError("CATALOG_DIGEST_MISMATCH", "catalog bytes differ from the frozen digest")
    return RuleCatalog(
        body=obj,
        required_rule_ids=tuple(required),
        optional_rule_ids=tuple(optional),
        fixture_by_rule=dict(fixture_by_rule),
        sha256=digest,
    )


def _parse_json(data: bytes, name: str) -> object:
    try:
        return json.loads(
            data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, CoverageError):
            raise
        raise CoverageError("CATALOG_UNREADABLE", f"{name}: {type(exc).__name__}") from exc


def load_catalog(
    repo_root: str | Path,
    *,
    expected_sha256: str,
    catalog_path: str = DEFAULT_CATALOG_PATH.as_posix(),
    inventory: Collection[str] = AEVE_G2_RULE_INVENTORY,
) -> RuleCatalog:
    """Read the committed catalog plus the S4 catalog and AEVE fixture index it names.

    ``expected_sha256`` (the frozen digest of the catalog's canonical bytes) is mandatory.
    The catalog also pins the raw-byte sha256 of the S4 catalog and of the fixture index, and
    those are verified here. Every path must stay under ``repo_root``; the fixture index must be
    ``AEVE_FIXTURES_DIR/index.json`` and its files are integrity-checked."""
    if expected_sha256 != FROZEN_CATALOG_SHA256:
        raise CoverageError("CATALOG_PIN_MISMATCH", "expected_sha256 differs from the frozen catalog pin")
    root = Path(repo_root)
    body = _parse_json(
        _read_bytes(_resolve_under(root, catalog_path, "catalog_path", "CATALOG_PATH_REFUSED"), "CATALOG_UNREADABLE"),
        "catalog",
    )
    if not isinstance(body, dict):
        raise CoverageError("CATALOG_INVALID", "catalog must be an object")
    raw: dict[str, bytes] = {}
    paths: dict[str, Path] = {}
    for name in ("s4_catalog", "aeve_fixture_index"):
        paths[name] = _resolve_under(root, body.get(name), name, "CATALOG_PATH_REFUSED")
        raw[name] = _read_bytes(paths[name], "CATALOG_UNREADABLE")
        pinned = body.get(f"{name}_sha256")
        if hashlib.sha256(raw[name]).hexdigest() != pinned:
            raise CoverageError("CATALOG_DEPENDENCY_DIGEST_MISMATCH", f"{name}: bytes differ from the pinned sha256")
    fixtures_dir = _resolve_under(root, AEVE_FIXTURES_DIR, "fixtures_dir", "CATALOG_PATH_REFUSED")
    if paths["aeve_fixture_index"] != fixtures_dir / "index.json":
        raise CoverageError("CATALOG_PATH_REFUSED", f"aeve_fixture_index must be {AEVE_FIXTURES_DIR}/index.json")
    fixtures: dict[str, str | None] = {fid: None for fid in s4_fixture_ids(_parse_json(raw["s4_catalog"], "s4_catalog"))}
    index = _parse_json(raw["aeve_fixture_index"], "aeve_fixture_index")
    for fid, seeded_rule in aeve_fixture_rules(index, fixtures_dir).items():
        if fid in fixtures:
            raise CoverageError("CATALOG_INVALID", f"fixture id {fid} exists in both fixture sources")
        fixtures[fid] = seeded_rule
    return validate_catalog(body, fixtures=fixtures, expected_sha256=expected_sha256, inventory=inventory)


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

    By design a finding for a rule outside the catalog-required checked set (an optional rule)
    is rejected with FINDING_RULE_NOT_CHECKED: the adapter already drops such findings into
    its accounting, so one reaching a receipt means the report and catalog disagree.
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
    # A rule listed twice in rule_statuses (checked and unsupported) is STATUS_DUPLICATE above.
    # STATUS_OVERLAP is about the report's separate covered_rules/unsupported_rules lists.
    covered_list, unsupported_list = body.get("covered_rules"), body.get("unsupported_rules")
    for name, value in (("covered_rules", covered_list), ("unsupported_rules", unsupported_list)):
        if not isinstance(value, list) or not all(isinstance(r, str) for r in value):
            raise _bad("STATUS_MALFORMED", f"{name} must be a list of strings")
    if set(covered_list) & set(unsupported_list):
        raise _bad("STATUS_OVERLAP", "a rule is listed as both covered and unsupported")
    if covered_list != sorted(checked) or unsupported_list != sorted(unsupported):
        raise _bad("STATUS_LIST_CONTRADICTION", "covered_rules/unsupported_rules contradict rule_statuses")
    coverage = "FULL" if not unsupported else ("PARTIAL" if checked else "NOT_COVERED")
    if coverage not in COVERAGE or body.get("coverage") != coverage:
        raise _bad("COVERAGE_CONTRADICTION", f"report coverage contradicts rule statuses (expected {coverage})")

    scope = body.get("analysis_scope")
    if not isinstance(scope, list) or not scope:
        raise _bad("SCOPE_INVALID", "analysis_scope must be a non-empty list")
    try:
        for position, rel in enumerate(scope):
            _req_plain_repo_path(rel, f"analysis_scope[{position}]")
    except ContractError as exc:
        raise _bad("SCOPE_INVALID", str(exc)) from exc
    if len(set(scope)) != len(scope) or scope != sorted(scope):
        raise _bad("SCOPE_INVALID", "analysis_scope must be sorted and unique")
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

    try:
        fields = static_analysis_fields(report)
    except (ContractError, KeyError, TypeError) as exc:
        raise _bad("REPORT_MALFORMED", f"{type(exc).__name__}: {exc}") from exc
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
