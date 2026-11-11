"""U5-5: final package builder for GPT-PM (pure; every external fact is injected).

The builder answers one question: may these facts be handed to the final reviewer as ONE package bound to
ONE head? It reads no git, no file, no network and no clock and calls no model. Verdicts, fail closed:

* READY    every piece of evidence names the package head, the diff bytes hash to the recorded digest and
           parse to exactly the declared path set, the review result is CLEAN, no test FAILED, every
           NOT_RUN or SKIPPED required test is acknowledged with a reason, and no evidence text looks like a
           secret. The package and its sha256 are returned.
* REFUSED  a definite policy violation (stale evidence, digest or path mismatch, review not CLEAN, failed
           test, unacknowledged NOT_RUN, secret). Every reason is listed; no package is returned.
* BLOCKED  the input is malformed or over a size cap, so no decision can be made. No package.

The package carries the head, the base head, the diff sha256 (never the diff bytes: the diff is delivered
to the reviewer by PM Bridge `--base/--head`), the evidence digests, the NOT_RUN list and the declared
limits. It says nothing stronger than its data: a NOT_RUN test is listed as NOT_RUN and never counted as
a PASS. `verify_package_current` refuses a package when the head or the diff changed; `render_scope_note`
renders deterministic Markdown from a package.

The module checks consistency of what it is given, not provenance: all evidence is caller-supplied and
unsigned here. Standard library plus sibling modules only. Details: docs/sdlc/u5/FINAL_PACKAGE.md.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contracts import ContractError, canonical_bytes
from .patch_proposals import RUN_RECORD_SCHEMA
from .receipt_builder import _refuse_secrets
from .worker_gate import MAX_CHANGED_PATHS, PROOF_SCHEMA, parse_diff_paths, path_hazards, proof_is_honest

READY = "READY"
REFUSED = "REFUSED"
BLOCKED = "BLOCKED"

PACKAGE_SCHEMA = "vst-final-package-v1"

MAX_TESTS = 512
MAX_RECEIPTS = 128
MAX_LIMITS = 128
MAX_TEXT = 500
MAX_ITERATIONS = 64
MAX_PROPERTIES = 64
MAX_LIST = 256
MAX_PACKAGE_BYTES = 512 * 1024

# refusal codes
STALE_EVIDENCE = "STALE_EVIDENCE"
DIFF_HASH_MISMATCH = "DIFF_HASH_MISMATCH"
PATHS_UNDERSTATED = "PATHS_UNDERSTATED"
PATHS_EXTRA = "PATHS_EXTRA"
PATH_HAZARD = "PATH_HAZARD"
EMPTY_DIFF = "EMPTY_DIFF"
DIFF_SPECIAL_MODE = "DIFF_SPECIAL_MODE"
REVIEW_NOT_CLEAN = "REVIEW_NOT_CLEAN"
REVIEW_INCONSISTENT = "REVIEW_INCONSISTENT"
REVIEW_REPLAYED = "REVIEW_REPLAYED"
REVIEW_STORY_MISMATCH = "REVIEW_STORY_MISMATCH"
TEST_FAILED = "TEST_FAILED"
NO_TEST_EVIDENCE = "NO_TEST_EVIDENCE"
NOT_RUN_UNACKNOWLEDGED = "NOT_RUN_UNACKNOWLEDGED"
RECEIPT_NOT_PASS = "RECEIPT_NOT_PASS"
PROOF_DISHONEST = "PROOF_DISHONEST"
ISOLATION_FAILED = "ISOLATION_FAILED"
SECRET_IN_EVIDENCE = "SECRET_IN_EVIDENCE"
# blocking codes
BAD_INPUT = "BAD_INPUT"
DIFF_UNPARSABLE = "DIFF_UNPARSABLE"
SIZE_CAP = "SIZE_CAP"
PACKAGE_TOO_LARGE = "PACKAGE_TOO_LARGE"
INTERNAL_ERROR = "INTERNAL_ERROR"
# verify_package_current codes
HEAD_CHANGED = "HEAD_CHANGED"
DIFF_CHANGED = "DIFF_CHANGED"
PACKAGE_MALFORMED = "PACKAGE_MALFORMED"
PACKAGE_INCONSISTENT = "PACKAGE_INCONSISTENT"
PACKAGE_TAMPERED = "PACKAGE_TAMPERED"

PROVENANCE_LIMIT = ("provenance: all evidence in this package is caller-supplied and unsigned; the builder checks "
                    "consistency of heads and digests, not who produced them")
DIFF_LIMIT = "diff: bound by sha256 and path list only; the package does not contain the diff bytes"

_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")  # same as pipeline_state._ID
_TEST_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./:\[\]-]{0,199}\Z")
_ITEM_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")  # same as receipt_builder._ID
_RFC3339_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z\Z")
_TEST_STATUSES = ("PASS", "FAIL", "NOT_RUN", "SKIPPED")
_NOT_PASSED = ("NOT_RUN", "SKIPPED")
_PROOF_STATUSES = ("VERIFIED", "CALLER_ASSERTED", "FAILED", "NOT_VERIFIED")


class _Bad(Exception):
    """Internal: the input is malformed; the result is BLOCKED with this (code, detail)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = _safe(detail)


def _bad(code: str, detail: str) -> None:
    raise _Bad(code, detail)


def _safe(value: Any, limit: int = 300) -> str:
    """ASCII-only, control-free, truncated text for a reason detail (never raises)."""
    try:
        text = value if isinstance(value, str) else str(value)
    except Exception:  # noqa: BLE001 - a hostile __str__ must not break the report
        text = "<unprintable>"
    out = []
    for ch in text:
        code = ord(ch)
        if 32 <= code < 127:
            out.append(ch)
        elif code < 256:
            out.append("\\x%02x" % code)
        elif code < 65536:
            out.append("\\u%04x" % code)
        else:
            out.append("\\U%08x" % code)
    return "".join(out)[:limit]


@dataclass(frozen=True)
class PackageResult:
    verdict: str                                  # READY, REFUSED or BLOCKED
    reasons: tuple[tuple[str, str], ...]          # (code, ASCII-escaped detail); empty only for READY
    package: dict | None                          # only for READY
    package_sha256: str | None                    # sha256 of canonical_bytes(package); only for READY

    def __post_init__(self) -> None:
        if self.verdict not in (READY, REFUSED, BLOCKED):
            raise ValueError("verdict must be READY, REFUSED or BLOCKED")
        if self.verdict == READY:
            if self.reasons or not isinstance(self.package, dict) or not self.package_sha256:
                raise ValueError("READY needs a package, its digest and no reasons")
        elif not self.reasons or self.package is not None or self.package_sha256 is not None:
            raise ValueError("REFUSED and BLOCKED need reasons and carry no package")

    @property
    def ready(self) -> bool:
        return self.verdict == READY

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(code for code, _ in self.reasons)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict, "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
            "package": copy.deepcopy(self.package), "package_sha256": self.package_sha256,
        }


# ------------------------------------------------------------------ field validators (raise _Bad)
def _text(value: Any, where: str, *, optional: bool = False, limit: int = MAX_TEXT) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value:
        _bad(BAD_INPUT, f"{where} must be a non-empty string")
    if len(value) > limit:
        _bad(SIZE_CAP, f"{where} is longer than {limit} characters")
    if any(ord(ch) < 32 or ord(ch) == 0x7F for ch in value):
        _bad(BAD_INPUT, f"{where} contains a control character")
    return value


def _hex(value: Any, where: str, pattern: re.Pattern, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not pattern.match(value):
        _bad(BAD_INPUT, f"{where} must be lowercase hex of the right length")
    return value


def _mapping(value: Any, where: str, required: set[str], optional: set[str] = frozenset()) -> Mapping:
    if not isinstance(value, Mapping):
        _bad(BAD_INPUT, f"{where} must be an object")
    keys = set(value)
    if not required <= keys or not keys <= (required | set(optional)):
        _bad(BAD_INPUT, f"{where} has missing or unknown keys")
    return value


def _seq(value: Any, where: str, cap: int) -> list:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        _bad(BAD_INPUT, f"{where} must be a list")
    if len(value) > cap:
        _bad(SIZE_CAP, f"{where} has more than {cap} entries")
    return list(value)


def _int(value: Any, where: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _bad(BAD_INPUT, f"{where} must be an integer >= {minimum}")
    return value


def _digest_of(value: Any) -> str:
    try:
        return hashlib.sha256(canonical_bytes(value)).hexdigest()
    except ContractError as exc:
        raise _Bad(BAD_INPUT, f"evidence is not canonical JSON: {exc}") from exc


def _stale(refusals: list, item: str, found: Any, head: str) -> None:
    refusals.append((STALE_EVIDENCE, f"{item}: evidence names head {_safe(found, 80)}, the package head is {head}"))


# ------------------------------------------------------------------ sections
def _tests_section(raw: Any, allow: Any, head: str, refusals: list) -> tuple[dict, list[dict]]:
    items = _seq(raw, "test_evidence", MAX_TESTS)
    if not isinstance(allow, Mapping):
        _bad(BAD_INPUT, "allow_not_run must be an object mapping test id to a reason")
    if len(allow) > MAX_TESTS:
        _bad(SIZE_CAP, "allow_not_run has too many entries")
    records: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        where = f"test_evidence[{index}]"
        _mapping(item, where, {"test_id", "status", "evidence_sha256", "head"}, {"required", "reason"})
        test_id = _hex(item["test_id"], f"{where}.test_id", _TEST_ID)
        status = item["status"]
        if status not in _TEST_STATUSES:
            _bad(BAD_INPUT, f"{where}.status must be one of {', '.join(_TEST_STATUSES)}")
        ran = status in ("PASS", "FAIL")
        digest = _hex(item["evidence_sha256"], f"{where}.evidence_sha256", _SHA256, optional=not ran)
        test_head = _hex(item["head"], f"{where}.head", _HEX40, optional=not ran)
        required = item.get("required", True)
        if type(required) is not bool:
            _bad(BAD_INPUT, f"{where}.required must be a bool")
        reason = _text(item.get("reason"), f"{where}.reason", optional=True)
        if test_id in seen:
            _bad(BAD_INPUT, f"duplicate test id {_safe(test_id, 80)}")
        seen.add(test_id)
        records.append({"test_id": test_id, "status": status, "evidence_sha256": digest, "head": test_head,
                        "required": required, "reason": reason})
    records.sort(key=lambda r: r["test_id"])
    acks: dict[str, str] = {}
    for key, value in allow.items():
        acks[_hex(key, "allow_not_run id", _TEST_ID)] = _text(value, f"allow_not_run[{_safe(key, 60)}] reason")
    not_run_ids = {r["test_id"] for r in records if r["status"] in _NOT_PASSED}
    if set(acks) - not_run_ids:
        _bad(BAD_INPUT, f"allow_not_run names ids that are not NOT_RUN or SKIPPED: {sorted(set(acks) - not_run_ids)[0]}")
    for record in records:
        if record["head"] is not None and record["head"] != head:
            _stale(refusals, f"test:{record['test_id']}", record["head"], head)
    failed = [r["test_id"] for r in records if r["status"] == "FAIL"]
    if failed:
        refusals.append((TEST_FAILED, "failed tests: " + ", ".join(failed[:10])))
    unacknowledged = [r["test_id"] for r in records
                      if r["status"] in _NOT_PASSED and r["required"] and r["test_id"] not in acks]
    if unacknowledged:
        refusals.append((NOT_RUN_UNACKNOWLEDGED,
                         "required tests not run and not acknowledged: " + ", ".join(unacknowledged[:10])))
    if not records:
        refusals.append((NO_TEST_EVIDENCE, "no test evidence record was supplied"))
    not_run = [{"test_id": r["test_id"], "status": r["status"], "required": r["required"], "reason": r["reason"],
                "acknowledged_reason": acks.get(r["test_id"])} for r in records if r["status"] in _NOT_PASSED]
    section = {
        "records": records,
        "passed": [r["test_id"] for r in records if r["status"] == "PASS"],
        "failed": failed,
        "not_run": not_run,
        "counts": {"PASS": sum(r["status"] == "PASS" for r in records), "FAIL": len(failed),
                   "NOT_RUN": sum(r["status"] == "NOT_RUN" for r in records),
                   "SKIPPED": sum(r["status"] == "SKIPPED" for r in records)},
    }
    return section, not_run


def _review_section(raw: Any, story_id: str, head: str, replay_verified: bool, refusals: list) -> dict:
    if not isinstance(raw, Mapping):
        _bad(BAD_INPUT, "review_results must be an object (ReviewLoopResult.to_dict)")
    verdict = raw.get("verdict")
    if verdict not in ("CLEAN", "BLOCKED"):
        _bad(BAD_INPUT, "review_results.verdict must be CLEAN or BLOCKED")
    reasons = _seq(raw.get("reasons"), "review_results.reasons", MAX_LIST)
    codes = []
    for index, reason in enumerate(reasons):
        if not isinstance(reason, Mapping) or not isinstance(reason.get("code"), str):
            _bad(BAD_INPUT, f"review_results.reasons[{index}] must carry a string code")
        codes.append(_safe(reason["code"], 60))
    iterations = _seq(raw.get("iterations"), "review_results.iterations", MAX_ITERATIONS)
    final_head = _hex(raw.get("final_head"), "review_results.final_head", _HEX40, optional=True)
    replayed = raw.get("replayed")
    if type(replayed) is not bool:
        _bad(BAD_INPUT, "review_results.replayed must be a bool")
    declared = [_text(c, "review_results.declared_coverage[]", limit=200)
                for c in _seq(raw.get("declared_coverage"), "review_results.declared_coverage", MAX_LIST)]
    review_story = _text(raw.get("story_id"), "review_results.story_id", optional=True, limit=200)
    last: dict | None = None
    if iterations:
        item = iterations[-1]
        if not isinstance(item, Mapping):
            _bad(BAD_INPUT, "review_results.iterations[-1] must be an object")
        last = {
            "iteration_id": _text(item.get("iteration_id"), "last iteration id", limit=200),
            "head": _hex(item.get("head"), "last iteration head", _HEX40),
            "verdict": _text(item.get("verdict"), "last iteration verdict", limit=40),
            "coverage": [_text(c, "last iteration coverage[]", limit=200)
                         for c in _seq(item.get("coverage"), "last iteration coverage", MAX_LIST)],
            "missing_coverage": [_text(c, "last iteration missing_coverage[]", limit=200)
                                 for c in _seq(item.get("missing_coverage"), "last iteration missing_coverage", MAX_LIST)],
            "findings_count": _int(item.get("findings_count"), "last iteration findings_count"),
        }
        iteration_reasons = _seq(item.get("reasons"), "last iteration reasons", MAX_LIST)
    else:
        iteration_reasons = []
    if verdict != "CLEAN":
        refusals.append((REVIEW_NOT_CLEAN, "review verdict is " + _safe(verdict, 20) + "; reasons: "
                         + (", ".join(codes[:10]) or "none listed")))
    else:
        proven = (last is not None and last["verdict"] == "CLEAN" and not reasons and not iteration_reasons
                  and last["findings_count"] == 0 and bool(declared) and set(declared) <= set(last["coverage"])
                  and not last["missing_coverage"])
        if not proven:
            refusals.append((REVIEW_INCONSISTENT, "a CLEAN review result must have a CLEAN last iteration with no "
                             "findings, no reasons and the declared coverage complete"))
    if final_head != head:
        _stale(refusals, "review_results.final_head", final_head, head)
    if last is not None and last["head"] != head:
        _stale(refusals, "review_results.iterations[-1].head", last["head"], head)
    if review_story is not None and review_story != story_id:
        refusals.append((REVIEW_STORY_MISMATCH, f"review result is for story {_safe(review_story, 80)}"))
    if replayed and not replay_verified:
        refusals.append((REVIEW_REPLAYED, "the review result was replayed without a verified store fact check; "
                         "pass replay_store_verified=True only after the iterations were checked against the store"))
    return {
        "verdict": verdict, "final_head": final_head, "iteration_count": len(iterations), "replayed": replayed,
        "replay_store_verified": bool(replay_verified), "declared_coverage": declared, "last_iteration": last,
        "result_sha256": _digest_of(raw),
    }


def _receipts_section(raw: Any, head: str, refusals: list) -> list[dict]:
    items = _seq(raw, "receipts", MAX_RECEIPTS)
    out: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        where = f"receipts[{index}]"
        _mapping(item, where, {"receipt_id", "head", "receipt_sha256"}, {"receipt_type", "result"})
        receipt_id = _hex(item["receipt_id"], f"{where}.receipt_id", _ITEM_ID)
        if receipt_id in seen:
            _bad(BAD_INPUT, f"duplicate receipt id {_safe(receipt_id, 80)}")
        seen.add(receipt_id)
        record = {
            "receipt_id": receipt_id, "head": _hex(item["head"], f"{where}.head", _HEX40),
            "receipt_sha256": _hex(item["receipt_sha256"], f"{where}.receipt_sha256", _SHA256),
            "receipt_type": _text(item.get("receipt_type"), f"{where}.receipt_type", optional=True, limit=100),
            "result": _text(item.get("result"), f"{where}.result", optional=True, limit=40),
        }
        out.append(record)
        if record["head"] != head:
            _stale(refusals, f"receipt:{receipt_id}", record["head"], head)
        if record["result"] is not None and record["result"] != "PASS":
            refusals.append((RECEIPT_NOT_PASS, f"receipt {receipt_id} result is {_safe(record['result'], 40)}"))
    out.sort(key=lambda r: r["receipt_id"])
    return out


def _isolation_section(raw: Any, head: str, refusals: list) -> dict:
    if not isinstance(raw, Mapping):
        _bad(BAD_INPUT, "isolation_proof must be an object (worker_gate.build_isolation_proof)")
    if raw.get("schema") != PROOF_SCHEMA:
        _bad(BAD_INPUT, "isolation_proof has the wrong schema")
    items = _seq(raw.get("properties"), "isolation_proof.properties", MAX_PROPERTIES)
    properties = []
    for index, item in enumerate(items):
        where = f"isolation_proof.properties[{index}]"
        _mapping(item, where, {"property", "status", "detail"})
        status = item["status"]
        if status not in _PROOF_STATUSES:
            _bad(BAD_INPUT, f"{where}.status is unknown")
        properties.append({"property": _text(item["property"], f"{where}.property", limit=100), "status": status,
                           "detail": _text(item["detail"], f"{where}.detail")})
    if not proof_is_honest(raw):
        refusals.append((PROOF_DISHONEST, "isolation proof promotes a property that was not checked or lists "
                         "the wrong property set"))
    failed = [p["property"] for p in properties if p["status"] == "FAILED"]
    if failed:
        refusals.append((ISOLATION_FAILED, "isolation properties FAILED: " + ", ".join(failed[:10])))
    found = raw.get("candidate_head")
    if found != head and found != ascii(head):  # the proof stores ascii(candidate_head) (worker_gate._show)
        _stale(refusals, "isolation_proof.candidate_head", found, head)
    return {"schema": PROOF_SCHEMA, "candidate_head": head if found in (head, ascii(head)) else None,
            "proof_sha256": _digest_of(raw), "properties": properties}


def _share_section(raw: Any, head: str, diff_sha: str, refusals: list) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or raw.get("schema") != RUN_RECORD_SCHEMA:
        _bad(BAD_INPUT, "patch_origin_share must be a U5-2 run record (build_run_record) or None")
    if type(raw.get("applied")) is not bool or type(raw.get("partial")) is not bool:
        _bad(BAD_INPUT, "patch_origin_share.applied and .partial must be bools")
    out: dict[str, Any] = {"schema": RUN_RECORD_SCHEMA, "verdict": _text(raw.get("verdict"), "share verdict", limit=60),
                           "applied": raw["applied"], "partial": raw["partial"]}
    for name in ("proposal_lines", "model_lines", "total_lines"):
        out[name] = _int(raw.get(name), f"patch_origin_share.{name}")
    for name in ("proposal_fraction", "model_fraction"):
        value = raw.get(name)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            _bad(BAD_INPUT, f"patch_origin_share.{name} must be None or a finite number")
        out[name] = value
    for name in ("files_touched_by_both", "model_only_paths", "overrides"):
        out[name] = copy.deepcopy(_seq(raw.get(name), f"patch_origin_share.{name}", MAX_LIST))
    candidate = _hex(raw.get("candidate_head"), "patch_origin_share.candidate_head", _HEX40, optional=True)
    recorded = _hex(raw.get("diff_sha256"), "patch_origin_share.diff_sha256", _SHA256, optional=True)
    if candidate is not None and candidate != head:
        _stale(refusals, "patch_origin_share.candidate_head", candidate, head)
    if recorded is not None and recorded != diff_sha:
        refusals.append((DIFF_HASH_MISMATCH, "patch_origin_share.diff_sha256 differs from the package diff digest"))
    out["candidate_head"] = candidate
    out["diff_sha256"] = recorded
    out["record_sha256"] = _digest_of(raw)
    return out


def _diff_section(diff_bytes: Any, recorded: str, changed: list[str], refusals: list) -> dict:
    if not isinstance(diff_bytes, bytes):
        _bad(BAD_INPUT, "diff_bytes must be bytes")
    actual = hashlib.sha256(diff_bytes).hexdigest()
    if actual != recorded:
        refusals.append((DIFF_HASH_MISMATCH, f"diff_bytes hash to {actual}, the recorded digest is {recorded}"))
    try:
        parsed = parse_diff_paths(diff_bytes)
    except Exception as exc:  # noqa: BLE001 - worker_gate raises its private _Blocked for every grammar problem
        if not refusals:
            raise _Bad(DIFF_UNPARSABLE, f"{type(exc).__name__}: {exc}") from exc
        # a definite refusal already exists: list both, like worker_gate (REFUSED wins over BLOCKED)
        refusals.append((DIFF_UNPARSABLE, _safe(f"{type(exc).__name__}: {exc}")))
        return {"sha256": actual, "bytes": len(diff_bytes), "changed_paths": sorted(changed), "path_count": len(changed),
                "renames": []}
    paths = set(parsed["paths"])
    if not paths:
        refusals.append((EMPTY_DIFF, "the diff names no path"))
    declared = set(changed)
    if paths - declared:
        refusals.append((PATHS_UNDERSTATED, "diff changes paths missing from changed_paths: "
                         + ", ".join(_safe(p, 100) for p in sorted(paths - declared)[:10])))
    if declared - paths:
        refusals.append((PATHS_EXTRA, "changed_paths lists paths the diff does not change: "
                         + ", ".join(_safe(p, 100) for p in sorted(declared - paths)[:10])))
    hazards = [f"{_safe(p, 100)} ({','.join(path_hazards(p))})" for p in sorted(declared | paths) if path_hazards(p)]
    if hazards:
        refusals.append((PATH_HAZARD, "paths with hazards: " + "; ".join(hazards[:10])))
    special = sorted(set(parsed["links"]) | set(parsed["gitlinks"]) | set(parsed["badmodes"]))
    if special:
        refusals.append((DIFF_SPECIAL_MODE, "link, submodule or non-standard mode: "
                         + ", ".join(_safe(p, 100) for p in special[:10])))
    return {"sha256": actual, "bytes": len(diff_bytes), "changed_paths": sorted(declared), "path_count": len(declared),
            "renames": [[a, b] for a, b in sorted(parsed["renames"])]}


def _limits(raw: Any) -> list[str]:
    return [_text(item, f"declared_limits[{i}]") for i, item in enumerate(_seq(raw, "declared_limits", MAX_LIMITS))]


def _derived_limits(tests: dict, not_run: list[dict], review: dict, isolation: dict, receipts: list, share: Any) -> list[str]:
    out = [PROVENANCE_LIMIT, DIFF_LIMIT]
    for item in not_run:
        out.append(f"{item['status']}: {item['test_id']} (required: {'yes' if item['required'] else 'no'}); "
                   f"acknowledged: {item['acknowledged_reason'] or 'no'}")
    for prop in isolation["properties"]:
        if prop["status"] != "VERIFIED":
            out.append(f"isolation {prop['property']}: {prop['status']}")
    if review["replayed"]:
        out.append("review: the result was replayed from the pipeline store, no new review ran for this package")
    if not receipts:
        out.append("receipts: none were supplied")
    if share is None:
        out.append("patch_origin_share: no run record was supplied")
    if not tests["passed"]:
        out.append("tests: no test has PASS evidence")
    return out


# ------------------------------------------------------------------ the builder
def build_final_package(
    *, story_id: str, base_head: str, head: str, diff_bytes: bytes, diff_sha256: str, changed_paths: Sequence[str],
    test_evidence: Sequence[Mapping[str, Any]], review_results: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]], isolation_proof: Mapping[str, Any],
    patch_origin_share: Mapping[str, Any] | None, now: str,
    allow_not_run: Mapping[str, str] | None = None, declared_limits: Sequence[str] = (),
    replay_store_verified: bool = False,
) -> PackageResult:
    """Build the final package bound to `head`, or refuse. Never raises for input problems; never mutates inputs.

    `diff_sha256` is the recorded diff digest (for example the gate evidence digest); `diff_bytes` must hash to
    it. `test_evidence` records: {test_id, status PASS/FAIL/NOT_RUN/SKIPPED, evidence_sha256, head} plus optional
    `required` (default True) and `reason`; PASS and FAIL need a digest and the head the evidence was produced
    at. `review_results` is `ReviewLoopResult.to_dict()`. `receipts` records: {receipt_id, head, receipt_sha256}
    plus optional receipt_type and result. `isolation_proof` is `worker_gate.build_isolation_proof` output,
    `patch_origin_share` a `patch_proposals.build_run_record` dict or None. `allow_not_run` maps a NOT_RUN or
    SKIPPED test id to the operator-visible reason it may stay unrun. `declared_limits` are copied verbatim.
    `replay_store_verified` must be True for a review result that was replayed from the store. `now` is an
    RFC 3339 UTC timestamp ending in 'Z', recorded as created_at.
    """
    try:
        return _build(story_id, base_head, head, diff_bytes, diff_sha256, changed_paths, test_evidence, review_results,
                      receipts, isolation_proof, patch_origin_share, now, allow_not_run, declared_limits,
                      replay_store_verified)
    except _Bad as exc:
        return PackageResult(BLOCKED, ((exc.code, exc.detail),), None, None)
    except Exception as exc:  # noqa: BLE001 - fail closed on anything unexpected (also RecursionError)
        return PackageResult(BLOCKED, ((INTERNAL_ERROR, _safe(f"{type(exc).__name__}: {exc}")),), None, None)


def _build(story_id, base_head, head, diff_bytes, diff_sha256, changed_paths, test_evidence, review_results,
           receipts, isolation_proof, patch_origin_share, now, allow_not_run, declared_limits, replay_store_verified):
    if type(replay_store_verified) is not bool:
        _bad(BAD_INPUT, "replay_store_verified must be a bool")
    try:  # private copies: nothing below can touch a caller object
        test_evidence = copy.deepcopy(test_evidence)
        review_results = copy.deepcopy(review_results)
        receipts = copy.deepcopy(receipts)
        isolation_proof = copy.deepcopy(isolation_proof)
        patch_origin_share = copy.deepcopy(patch_origin_share)
        allow_not_run = copy.deepcopy({} if allow_not_run is None else allow_not_run)
        declared_limits = copy.deepcopy(declared_limits)
        changed_paths = copy.deepcopy(changed_paths)
        diff_bytes = bytes(diff_bytes) if isinstance(diff_bytes, (bytes, bytearray)) else diff_bytes
    except RecursionError as exc:
        raise _Bad(BAD_INPUT, "input is nested too deeply") from exc
    except (TypeError, ValueError) as exc:
        raise _Bad(BAD_INPUT, f"input is not copyable ({type(exc).__name__})") from exc

    if not isinstance(story_id, str) or not _STORY.match(story_id):
        _bad(BAD_INPUT, "story_id is malformed")
    _hex(base_head, "base_head", _HEX40)
    _hex(head, "head", _HEX40)
    _hex(diff_sha256, "diff_sha256", _SHA256)
    if not isinstance(now, str) or not _RFC3339_UTC.match(now):
        _bad(BAD_INPUT, "now must be an RFC 3339 UTC timestamp ending in 'Z'")
    if base_head == head:
        _bad(BAD_INPUT, "base_head equals head: there is no change to package")
    paths = _seq(changed_paths, "changed_paths", MAX_CHANGED_PATHS)
    if not paths or any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
        _bad(BAD_INPUT, "changed_paths must be a non-empty list of unique strings")

    refusals: list[tuple[str, str]] = []
    diff = _diff_section(diff_bytes, diff_sha256, paths, refusals)
    tests, not_run = _tests_section(test_evidence, allow_not_run, head, refusals)
    review = _review_section(review_results, story_id, head, replay_store_verified, refusals)
    receipt_rows = _receipts_section(receipts, head, refusals)
    isolation = _isolation_section(isolation_proof, head, refusals)
    share = _share_section(patch_origin_share, head, diff["sha256"], refusals)
    limits = _limits(declared_limits)

    # secrets: scan the evidence text section by section so the refusal names the item (paths and the
    # diff are not scanned: identifiers are checked by path_hazards and the diff bytes never enter the package)
    scans = (("story_id", story_id), ("test_evidence", test_evidence), ("allow_not_run", allow_not_run),
             ("review_results", review_results), ("receipts", receipts), ("isolation_proof", isolation_proof),
             ("patch_origin_share", patch_origin_share), ("declared_limits", limits))
    for where, value in scans:
        try:
            _refuse_secrets(where, value)
        except ContractError as exc:
            if str(exc).startswith("RB_SECRET_LIKE_VALUE"):
                refusals.append((SECRET_IN_EVIDENCE, f"{where} contains a value that looks like a secret"))
            else:
                raise _Bad(BAD_INPUT, f"{where} cannot be scanned: {exc}") from exc
    if refusals:
        return PackageResult(REFUSED, tuple((c, _safe(d, 600)) for c, d in refusals), None, None)

    package = {
        "schema": PACKAGE_SCHEMA, "story_id": story_id, "head": head, "base_head": base_head,
        "valid_for_head": head, "created_at": now, "diff": diff, "tests": tests, "not_run": not_run,
        "allow_not_run": {k: allow_not_run[k] for k in sorted(allow_not_run)}, "review": review,
        "receipts": receipt_rows, "isolation": isolation, "patch_origin_share": share,
        "evidence_digests": {
            "diff_sha256": diff["sha256"],
            "tests": {r["test_id"]: r["evidence_sha256"] for r in tests["records"]},
            "review_result_sha256": review["result_sha256"],
            "receipts": {r["receipt_id"]: r["receipt_sha256"] for r in receipt_rows},
            "isolation_proof_sha256": isolation["proof_sha256"],
            "patch_origin_share_sha256": share["record_sha256"] if share else None,
        },
        "declared_limits": limits,
        "derived_limits": _derived_limits(tests, not_run, review, isolation, receipt_rows, share),
    }
    try:
        blob = canonical_bytes(package)
    except ContractError as exc:
        raise _Bad(BAD_INPUT, f"package is not canonical JSON: {exc}") from exc
    if len(blob) > MAX_PACKAGE_BYTES:
        _bad(PACKAGE_TOO_LARGE, f"package is {len(blob)} bytes, the cap is {MAX_PACKAGE_BYTES}")
    return PackageResult(READY, (), package, hashlib.sha256(blob).hexdigest())


# ------------------------------------------------------------------ invalidation
def verify_package_current(package: Any, current_head: Any, current_diff_sha256: Any, *,
                           package_sha256: str | None = None) -> tuple[bool, tuple[tuple[str, str], ...]]:
    """(ok, reasons): False when the head or the diff differ from the package, or the package is not coherent.

    A new commit changes the head (and usually the diff), so the package stops being current. When
    `package_sha256` is given the package is also re-hashed. Never raises and never mutates the package.
    """
    reasons: list[tuple[str, str]] = []
    try:
        if not isinstance(package, Mapping) or package.get("schema") != PACKAGE_SCHEMA:
            return False, ((PACKAGE_MALFORMED, "not a final package of this schema"),)
        head, valid = package.get("head"), package.get("valid_for_head")
        diff = package.get("diff")
        diff_sha = diff.get("sha256") if isinstance(diff, Mapping) else None
        if not (isinstance(head, str) and _HEX40.match(head) and isinstance(diff_sha, str) and _SHA256.match(diff_sha)):
            return False, ((PACKAGE_MALFORMED, "package head or diff digest is malformed"),)
        if not (isinstance(current_head, str) and _HEX40.match(current_head)
                and isinstance(current_diff_sha256, str) and _SHA256.match(current_diff_sha256)):
            return False, ((BAD_INPUT, "current head or current diff digest is malformed"),)
        if valid != head:
            reasons.append((PACKAGE_INCONSISTENT, "valid_for_head differs from head"))
        embedded = [("review.final_head", (package.get("review") or {}).get("final_head")),
                    ("isolation.candidate_head", (package.get("isolation") or {}).get("candidate_head"))]
        embedded += [(f"test:{r.get('test_id')}", r.get("head")) for r in (package.get("tests") or {}).get("records", ())
                     if r.get("head") is not None]
        embedded += [(f"receipt:{r.get('receipt_id')}", r.get("head")) for r in package.get("receipts") or ()]
        for item, found in embedded:
            if found != head:
                reasons.append((PACKAGE_INCONSISTENT, f"{_safe(item, 100)} names head {_safe(found, 80)}, not {head}"))
        if current_head != valid:
            reasons.append((HEAD_CHANGED, f"the package is valid for {_safe(valid, 80)}, the current head is {current_head}"))
        if current_diff_sha256 != diff_sha:
            reasons.append((DIFF_CHANGED, f"the package diff is {diff_sha}, the current diff is {current_diff_sha256}"))
        if package_sha256 is not None and hashlib.sha256(canonical_bytes(package)).hexdigest() != package_sha256:
            reasons.append((PACKAGE_TAMPERED, "the package does not hash to the given package_sha256"))
    except Exception as exc:  # noqa: BLE001 - fail closed
        return False, ((PACKAGE_MALFORMED, _safe(f"{type(exc).__name__}: {exc}")),)
    return (not reasons), tuple(reasons)


# ------------------------------------------------------------------ rendering
def render_scope_note(package: Mapping[str, Any]) -> str:
    """Deterministic English Markdown for the reviewer. States only what the package data says.

    Raises ValueError when `package` is not a package of this schema.
    """
    try:
        if not isinstance(package, Mapping) or package["schema"] != PACKAGE_SCHEMA:
            raise ValueError("not a final package")
        diff, tests, review = package["diff"], package["tests"], package["review"]
        lines = [
            f"# Final package for story {package['story_id']}", "",
            f"- Head: `{package['head']}` (this package is valid for this head only; a new commit invalidates it)",
            f"- Base head: `{package['base_head']}`",
            f"- Created at: {package['created_at']}",
            f"- Diff sha256: `{diff['sha256']}` ({diff['bytes']} bytes, {diff['path_count']} path(s))", "",
            "## What changed", "",
        ]
        lines += [f"- `{p}`" for p in diff["changed_paths"]]
        lines += [f"- rename: `{a}` -> `{b}`" for a, b in diff["renames"]]
        last = review["last_iteration"] or {}
        lines += ["", "## Review", "",
                  f"- Local review loop verdict: {review['verdict']} at head `{review['final_head']}` after "
                  f"{review['iteration_count']} iteration(s)",
                  f"- Declared coverage: {', '.join(review['declared_coverage']) or 'none'}",
                  f"- Last iteration: {last.get('iteration_id')} ({last.get('verdict')}, "
                  f"{last.get('findings_count')} finding(s))",
                  f"- Replayed from the store: {'yes' if review['replayed'] else 'no'}"
                  f"{' (store facts verified by the caller)' if review['replayed'] and review['replay_store_verified'] else ''}",
                  f"- Result sha256: `{review['result_sha256']}`", "", "## Test evidence", ""]
        counts = tests["counts"]
        lines.append(f"- Records: PASS {counts['PASS']}, FAIL {counts['FAIL']}, NOT_RUN {counts['NOT_RUN']}, "
                     f"SKIPPED {counts['SKIPPED']}")
        for record in tests["records"]:
            if record["status"] == "PASS":
                lines.append(f"- PASS record: `{record['test_id']}` at head `{record['head']}`, evidence "
                             f"`{record['evidence_sha256']}`")
        lines += ["", "## NOT_RUN items", ""]
        if package["not_run"]:
            lines.append("No claim is made for these items; they are not counted as results.")
            for item in package["not_run"]:
                ack = item["acknowledged_reason"]
                lines.append(f"- `{item['test_id']}`: {item['status']}, required: {'yes' if item['required'] else 'no'}, "
                             f"reason: {item['reason'] or 'none'}, acknowledged: {ack if ack else 'no'}")
        else:
            lines.append("- none")
        lines += ["", "## Receipts", ""]
        lines += ([f"- `{r['receipt_id']}` ({r['receipt_type'] or 'type not given'}) at head `{r['head']}`, "
                   f"sha256 `{r['receipt_sha256']}`" for r in package["receipts"]] or ["- none supplied"])
        lines += ["", "## Isolation", ""]
        lines += [f"- {p['property']}: {p['status']} - {p['detail']}" for p in package["isolation"]["properties"]]
        share = package["patch_origin_share"]
        lines += ["", "## Change origin", ""]
        if share is None:
            lines.append("- no patch origin record was supplied")
        else:
            lines.append(f"- Proposal lines {share['proposal_lines']}, model lines {share['model_lines']}, total "
                         f"{share['total_lines']}; proposal fraction {share['proposal_fraction']}, model fraction "
                         f"{share['model_fraction']}; run verdict {share['verdict']}, applied: "
                         f"{'yes' if share['applied'] else 'no'}")
            lines.append(f"- Overrides recorded: {len(share['overrides'])}")
        lines += ["", "## Declared limits (caller-supplied, verbatim)", ""]
        lines += [f"- {item}" for item in package["declared_limits"]] or ["- none"]
        lines += ["", "## Derived limits", ""]
        lines += [f"- {item}" for item in package["derived_limits"]]
        lines += ["", "## Evidence digests", "", f"- Diff: `{package['evidence_digests']['diff_sha256']}`",
                  f"- Review result: `{package['evidence_digests']['review_result_sha256']}`",
                  f"- Isolation proof: `{package['evidence_digests']['isolation_proof_sha256']}`", ""]
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"package is malformed: {type(exc).__name__}") from exc
    return "\n".join(lines)
