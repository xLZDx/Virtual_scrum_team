"""U5-5: final package builder for GPT-PM (pure; every external fact is injected).

The builder answers one question: may these facts be handed to the final reviewer as ONE package bound to
ONE head? It reads no git, no file, no network and no clock and calls no model. Verdicts, fail closed:

* READY    every piece of evidence names the package head, the diff bytes hash to the recorded digest and
           parse to exactly the declared path set, the review result is CLEAN for this story and carries the
           same changed-paths digest (`uc.contracts.changed_paths_sha256`) as the declared path set, no test
           FAILED, at least one test has PASS evidence, every required test id has a record and is PASS (or
           NOT_RUN / SKIPPED with an explicit `allow_not_run` reason), and no free-text evidence looks like a
           secret. The package and its sha256 are returned.
* REFUSED  a definite policy violation (stale evidence, digest or path mismatch, review not CLEAN or bound to
           other paths, failed test, missing required test, no PASS evidence, unacknowledged NOT_RUN, secret).
           Every reason is
           listed; no package is returned. Reason details are fixed text plus validated item names only;
           unvalidated evidence text is never echoed.
* BLOCKED  the input is malformed or over a size cap, so no decision can be made. No package.

The package carries the head, the base head, the diff sha256 (never the diff bytes: the diff is delivered
to the reviewer by PM Bridge `--base/--head`), the evidence digests, the NOT_RUN list and the declared
limits. It says nothing stronger than its data: a NOT_RUN test is listed as NOT_RUN and never counted as
a PASS. `verify_package_current` refuses a package when the head or the diff changed; `render_scope_note`
renders deterministic, escaped Markdown from a package.

Secret scan: only free-text fields are scanned (test reasons, acknowledgement reasons, review reasons and
iteration texts, receipt type and result, isolation details, run-record verdict and overrides, declared
limits). Identifiers (story id, test ids, receipt ids, heads, digests, paths, property names) are validated
by shape, not scanned: the shared pattern also matches ordinary names such as `secret_patterns`.

The module checks consistency of what it is given, not provenance: all evidence is caller-supplied and
unsigned here. Standard library plus sibling modules only. Details: docs/sdlc/u5/FINAL_PACKAGE.md.
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
from typing import Any, Mapping, Sequence

from ..uc import contracts as uc_contracts
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
REVIEW_PATHS_MISMATCH = "REVIEW_PATHS_MISMATCH"
TEST_FAILED = "TEST_FAILED"
NO_PASS_EVIDENCE = "NO_PASS_EVIDENCE"
MISSING_REQUIRED_TEST = "MISSING_REQUIRED_TEST"
NOT_RUN_UNACKNOWLEDGED = "NOT_RUN_UNACKNOWLEDGED"
RECEIPT_NOT_PASS = "RECEIPT_NOT_PASS"
PROOF_DISHONEST = "PROOF_DISHONEST"
ISOLATION_FAILED = "ISOLATION_FAILED"
SHARE_NOT_ACCEPTED = "SHARE_NOT_ACCEPTED"
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
# pytest node ids: printable ASCII (spaces, brackets and quotes of parametrized ids included), no control chars
_TEST_ID = re.compile(r"[A-Za-z0-9_][ -~]{0,199}\Z")
_ITEM_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")  # same as receipt_builder._ID
_PROP = re.compile(r"[a-z0-9_]{1,100}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,59}\Z")
_KEY = re.compile(r"[A-Za-z0-9_]{1,64}\Z")
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


class PackageResult:
    """Outcome of `build_final_package`. Holds its own private copy of the package: `package` returns a fresh
    deep copy on every access, so neither the builder's internals nor a caller's edit can alias another copy."""

    __slots__ = ("verdict", "reasons", "_package", "package_sha256")

    def __init__(self, verdict: str, reasons: Sequence[tuple[str, str]], package: dict | None,
                 package_sha256: str | None) -> None:
        if verdict not in (READY, REFUSED, BLOCKED):
            raise ValueError("verdict must be READY, REFUSED or BLOCKED")
        reasons = tuple((str(c), str(d)) for c, d in reasons)
        if verdict == READY:
            if reasons or not isinstance(package, dict) or not package_sha256:
                raise ValueError("READY needs a package, its digest and no reasons")
        elif not reasons or package is not None or package_sha256 is not None:
            raise ValueError("REFUSED and BLOCKED need reasons and carry no package")
        object.__setattr__(self, "verdict", verdict)
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(self, "_package", copy.deepcopy(package))
        object.__setattr__(self, "package_sha256", package_sha256)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("PackageResult is immutable")

    @property
    def package(self) -> dict | None:
        return copy.deepcopy(self._package)

    @property
    def ready(self) -> bool:
        return self.verdict == READY

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(code for code, _ in self.reasons)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict, "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
            "package": self.package, "package_sha256": self.package_sha256,
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
        _bad(BAD_INPUT, f"{where} has the wrong shape")
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


def _path_shape_problem(path: Any) -> bool:
    """True for a path that cannot be safely listed: not a string, empty, control character or backtick."""
    return (not isinstance(path, str) or not path or "`" in path
            or any(ord(ch) < 32 or ord(ch) == 0x7F for ch in path))


def _hazards(path: str) -> list[str]:
    found = list(path_hazards(path))
    if "`" in path:
        found.append("BACKTICK")
    return found


def _stale(refusals: list, item: str, found: Any, head: str) -> None:
    shown = found if isinstance(found, str) and _HEX40.match(found) else "not a valid head"
    refusals.append((STALE_EVIDENCE, f"{item}: evidence names head {shown}, the package head is {head}"))


def _add(refusals: list, code: str, detail: str) -> None:
    """Add one reason per (code, detail): the same cause is never listed twice."""
    if (code, detail) not in refusals:
        refusals.append((code, detail))


# ------------------------------------------------------------------ secret scan (free text only)
def _get(value: Any, key: str) -> Any:
    return value.get(key) if isinstance(value, Mapping) else None


def _list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else []


def _free_text(test_evidence, allow_not_run, review, receipts, proof, share, limits) -> dict[str, Any]:
    """The free-text parts of the evidence, by section. Identifiers are validated by shape elsewhere."""
    return {
        "test_evidence": [_get(r, "reason") for r in _list(test_evidence)],
        "allow_not_run": list(allow_not_run.values()) if isinstance(allow_not_run, Mapping) else [],
        "review_results": [_get(review, "reasons")]
        + [[_get(i, "iteration_id"), _get(i, "reasons")] for i in _list(_get(review, "iterations"))],
        "receipts": [[_get(r, "receipt_type"), _get(r, "result")] for r in _list(receipts)],
        "isolation_proof": [_get(p, "detail") for p in _list(_get(proof, "properties"))],
        "patch_origin_share": [_get(share, "verdict"), _get(share, "overrides")],
        "declared_limits": limits,
    }


def _secret_sections(parts: Mapping[str, Any]) -> list[str]:
    hit = []
    for where, value in parts.items():
        try:
            _refuse_secrets(where, value)
        except ContractError as exc:
            if str(exc).startswith("RB_SECRET_LIKE_VALUE"):
                hit.append(where)
            else:
                raise _Bad(BAD_INPUT, f"{where} cannot be scanned") from exc
    return hit


# ------------------------------------------------------------------ sections
def _tests_section(raw: Any, allow: Any, required_raw: Any, head: str, refusals: list) -> tuple[dict, list[dict]]:
    items = _seq(raw, "test_evidence", MAX_TESTS)
    required_ids = _seq(required_raw, "required_test_ids", MAX_TESTS)
    if not required_ids:
        _bad(BAD_INPUT, "required_test_ids must be a non-empty list")
    for rid in required_ids:
        _hex(rid, "required_test_ids[]", _TEST_ID)
    if len(set(required_ids)) != len(required_ids):
        _bad(BAD_INPUT, "required_test_ids has duplicates")
    required_set = set(required_ids)
    if not isinstance(allow, Mapping):
        _bad(BAD_INPUT, "allow_not_run must be an object mapping test id to a reason")
    if len(allow) > MAX_TESTS:
        _bad(SIZE_CAP, "allow_not_run has too many entries")
    records: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        where = f"test_evidence[{index}]"
        _mapping(item, where, {"test_id", "status", "evidence_sha256", "head"}, {"reason"})
        test_id = _hex(item["test_id"], f"{where}.test_id", _TEST_ID)
        status = item["status"]
        if status not in _TEST_STATUSES:
            _bad(BAD_INPUT, f"{where}.status must be one of {', '.join(_TEST_STATUSES)}")
        ran = status in ("PASS", "FAIL")
        digest = _hex(item["evidence_sha256"], f"{where}.evidence_sha256", _SHA256, optional=not ran)
        test_head = _hex(item["head"], f"{where}.head", _HEX40, optional=not ran)
        reason = _text(item.get("reason"), f"{where}.reason", optional=True)
        if test_id in seen:
            _bad(BAD_INPUT, f"duplicate test record {index}")
        seen.add(test_id)
        records.append({"test_id": test_id, "status": status, "evidence_sha256": digest, "head": test_head,
                        "required": test_id in required_set, "reason": reason})
    records.sort(key=lambda r: r["test_id"])
    acks: dict[str, str] = {}
    for key, value in allow.items():
        acks[_hex(key, "allow_not_run id", _TEST_ID)] = _text(value, "allow_not_run reason")
    not_run_ids = {r["test_id"] for r in records if r["status"] in _NOT_PASSED}
    if set(acks) - not_run_ids:
        _bad(BAD_INPUT, "allow_not_run names an id that is not a NOT_RUN or SKIPPED record")
    by_id = {r["test_id"]: r for r in records}
    for record in records:
        if record["head"] is not None and record["head"] != head:
            _stale(refusals, f"test:{record['test_id']}", record["head"], head)
    failed = [r["test_id"] for r in records if r["status"] == "FAIL"]
    if failed:
        _add(refusals, TEST_FAILED, "failed tests: " + ", ".join(failed[:10]))
    missing = sorted(i for i in required_set if i not in by_id)
    if missing:
        _add(refusals, MISSING_REQUIRED_TEST, "required tests without a record: " + ", ".join(missing[:10]))
    unacknowledged = sorted(i for i in required_set
                            if i in by_id and by_id[i]["status"] in _NOT_PASSED and i not in acks)
    if unacknowledged:
        _add(refusals, NOT_RUN_UNACKNOWLEDGED,
             "required tests not run and not acknowledged: " + ", ".join(unacknowledged[:10]))
    if not any(r["status"] == "PASS" for r in records):
        _add(refusals, NO_PASS_EVIDENCE, "no test record has PASS evidence")
    not_run = [{"test_id": r["test_id"], "status": r["status"], "required": r["required"], "reason": r["reason"],
                "acknowledged_reason": acks.get(r["test_id"])} for r in records if r["status"] in _NOT_PASSED]
    section = {
        "required_test_ids": sorted(required_set),
        "records": records,
        "passed": [r["test_id"] for r in records if r["status"] == "PASS"],
        "failed": failed,
        "not_run": copy.deepcopy(not_run),
        "counts": {"PASS": sum(r["status"] == "PASS" for r in records), "FAIL": len(failed),
                   "NOT_RUN": sum(r["status"] == "NOT_RUN" for r in records),
                   "SKIPPED": sum(r["status"] == "SKIPPED" for r in records)},
    }
    return section, not_run


def _review_section(raw: Any, story_id: str, head: str, replay_verified: bool, paths_digest: str,
                    refusals: list) -> dict:
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
        codes.append(reason["code"] if _CODE.match(reason["code"]) else "?")
    iterations = _seq(raw.get("iterations"), "review_results.iterations", MAX_ITERATIONS)
    final_head = _hex(raw.get("final_head"), "review_results.final_head", _HEX40, optional=True)
    replayed = raw.get("replayed")
    if type(replayed) is not bool:
        _bad(BAD_INPUT, "review_results.replayed must be a bool")
    declared = [_text(c, "review_results.declared_coverage[]", limit=200)
                for c in _seq(raw.get("declared_coverage"), "review_results.declared_coverage", MAX_LIST)]
    review_story = raw.get("story_id")
    if review_story is not None and (not isinstance(review_story, str) or len(review_story) > 200):
        _bad(BAD_INPUT, "review_results.story_id must be a string or None")
    last: dict | None = None
    iteration_reasons: list = []
    strict_findings = False
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
        strict_findings = item.get("findings") == [] and item.get("truncated") is False
    if verdict != "CLEAN":
        _add(refusals, REVIEW_NOT_CLEAN, "review verdict is " + verdict + "; reason codes: "
             + (", ".join(codes[:10]) or "none listed"))
    else:
        proven = (last is not None and last["verdict"] == "CLEAN" and not reasons and not iteration_reasons
                  and last["findings_count"] == 0 and strict_findings and raw.get("iteration_count") == len(iterations)
                  and bool(declared) and set(declared) <= set(last["coverage"]) and not last["missing_coverage"])
        if not proven:
            _add(refusals, REVIEW_INCONSISTENT, "a CLEAN review result must have a CLEAN last iteration with no "
                 "findings (none truncated), no reasons, an iteration count equal to the iteration list and the "
                 "declared coverage complete")
    if final_head != head:
        _stale(refusals, "review_results.final_head", final_head, head)
    if last is not None and last["head"] != head:
        _stale(refusals, "review_results.iterations[-1].head", last["head"], head)
    if review_story != story_id:
        _add(refusals, REVIEW_STORY_MISMATCH, "the review result is not for this story (story id missing or different)")
    reviewed_paths = raw.get("changed_paths_sha256")
    if not isinstance(reviewed_paths, str) or not _SHA256.match(reviewed_paths):
        reviewed_paths = None
        _add(refusals, REVIEW_PATHS_MISMATCH, "review_results.changed_paths_sha256 is missing or malformed; the "
             "review is not bound to a path set")
    elif reviewed_paths != paths_digest:
        _add(refusals, REVIEW_PATHS_MISMATCH, "review_results.changed_paths_sha256 differs from the digest of "
             "changed_paths; the review did not cover exactly the packaged path set")
    if replayed and not replay_verified:
        _add(refusals, REVIEW_REPLAYED, "the review result was replayed without a verified store fact check; "
             "pass replay_store_verified=True only after the iterations were checked against the store")
    return {
        "verdict": verdict, "final_head": final_head, "iteration_count": len(iterations), "replayed": replayed,
        "replay_store_verified": bool(replay_verified), "declared_coverage": declared, "last_iteration": last,
        "changed_paths_sha256": reviewed_paths, "result_sha256": _digest_of(raw),
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
            _bad(BAD_INPUT, f"duplicate receipt record {index}")
        seen.add(receipt_id)
        result = item.get("result")
        if result is not None and (not isinstance(result, str) or len(result) > 40):
            _bad(BAD_INPUT, f"{where}.result must be a short string or missing")
        record = {
            "receipt_id": receipt_id, "head": _hex(item["head"], f"{where}.head", _HEX40),
            "receipt_sha256": _hex(item["receipt_sha256"], f"{where}.receipt_sha256", _SHA256),
            "receipt_type": _text(item.get("receipt_type"), f"{where}.receipt_type", optional=True, limit=100),
            "result": result,
        }
        out.append(record)
        if record["head"] != head:
            _stale(refusals, f"receipt:{receipt_id}", record["head"], head)
        if result is None:
            _add(refusals, RECEIPT_NOT_PASS, f"receipt {receipt_id}: result missing")
        elif result != "PASS":
            _add(refusals, RECEIPT_NOT_PASS, f"receipt {receipt_id}: result is not PASS")
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
        properties.append({"property": _hex(item["property"], f"{where}.property", _PROP), "status": status,
                           "detail": _text(item["detail"], f"{where}.detail")})
    if not proof_is_honest(raw):
        _add(refusals, PROOF_DISHONEST, "isolation proof promotes a property that was not checked or lists "
             "the wrong property set")
    failed = [p["property"] for p in properties if p["status"] == "FAILED"]
    if failed:
        _add(refusals, ISOLATION_FAILED, "isolation properties FAILED: " + ", ".join(failed[:10]))
    found = raw.get("candidate_head")
    if found != head and found != ascii(head):  # the proof stores ascii(candidate_head) (worker_gate._show)
        refusals.append((STALE_EVIDENCE, f"isolation_proof.candidate_head: evidence does not name the package head {head}"))
    return {"schema": PROOF_SCHEMA, "candidate_head": head if found in (head, ascii(head)) else None,
            "proof_sha256": _digest_of(raw), "properties": properties}


def _share_section(raw: Any, head: str, recorded_diff: str, refusals: list) -> dict | None:
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
    for name in ("files_touched_by_both", "model_only_paths"):
        paths = _seq(raw.get(name), f"patch_origin_share.{name}", MAX_LIST)
        if any(_path_shape_problem(p) or len(p) > 512 for p in paths):
            _bad(BAD_INPUT, f"patch_origin_share.{name} must hold plain path strings")
        out[name] = list(paths)
    overrides = []
    for index, override in enumerate(_seq(raw.get("overrides"), "patch_origin_share.overrides", MAX_LIST)):
        if not isinstance(override, Mapping) or len(override) > 16:
            _bad(BAD_INPUT, f"patch_origin_share.overrides[{index}] must be a small object")
        overrides.append({_hex(k, "override key", _KEY): _text(v, f"override[{index}] value")
                          for k, v in sorted(override.items(), key=lambda kv: str(kv[0]))})
    out["overrides"] = overrides
    candidate = _hex(raw.get("candidate_head"), "patch_origin_share.candidate_head", _HEX40, optional=True)
    recorded = _hex(raw.get("diff_sha256"), "patch_origin_share.diff_sha256", _SHA256, optional=True)
    if candidate is None:
        refusals.append((STALE_EVIDENCE, "patch_origin_share.candidate_head: missing; the record is not bound to a head"))
    elif candidate != head:
        _stale(refusals, "patch_origin_share.candidate_head", candidate, head)
    if recorded is None:
        _add(refusals, DIFF_HASH_MISMATCH, "patch_origin_share.diff_sha256: missing; the record is not bound to a diff")
    elif recorded != recorded_diff:
        _add(refusals, DIFF_HASH_MISMATCH, "patch_origin_share.diff_sha256 differs from the recorded diff digest")
    if out["verdict"] != "ACCEPTED" or out["applied"] is not True or out["partial"] is not False:
        _add(refusals, SHARE_NOT_ACCEPTED, "the patch origin run record is not an ACCEPTED, applied, complete run")
    out["candidate_head"] = candidate
    out["diff_sha256"] = recorded
    out["record_sha256"] = _digest_of(raw)
    return out


def _diff_section(diff_bytes: Any, recorded: str, changed: list[str], refusals: list) -> dict:
    if not isinstance(diff_bytes, bytes):
        _bad(BAD_INPUT, "diff_bytes must be bytes")
    actual = hashlib.sha256(diff_bytes).hexdigest()
    if actual != recorded:
        _add(refusals, DIFF_HASH_MISMATCH, "diff_bytes do not hash to the recorded diff digest")
    try:
        parsed = parse_diff_paths(diff_bytes)
    except Exception:  # noqa: BLE001 - worker_gate raises its private _Blocked for every grammar problem
        if not refusals:
            raise _Bad(DIFF_UNPARSABLE, "the diff does not parse as git diff grammar") from None
        # a definite refusal already exists: list both, like worker_gate (REFUSED wins over BLOCKED)
        _add(refusals, DIFF_UNPARSABLE, "the diff does not parse as git diff grammar")
        return {"sha256": actual, "bytes": len(diff_bytes), "changed_paths": sorted(changed), "path_count": len(changed),
                "renames": []}
    paths = set(parsed["paths"])
    if not paths:
        _add(refusals, EMPTY_DIFF, "the diff names no path")
    declared = set(changed)
    if paths - declared:
        _add(refusals, PATHS_UNDERSTATED, "diff changes paths missing from changed_paths: "
             + ", ".join(_safe(p, 100) for p in sorted(paths - declared)[:10]))
    if declared - paths:
        _add(refusals, PATHS_EXTRA, "changed_paths lists paths the diff does not change: "
             + ", ".join(_safe(p, 100) for p in sorted(declared - paths)[:10]))
    hazards = [f"{_safe(p, 100)} ({','.join(_hazards(p))})" for p in sorted(declared | paths) if _hazards(p)]
    if hazards:
        _add(refusals, PATH_HAZARD, "paths with hazards: " + "; ".join(hazards[:10]))
    special = sorted(set(parsed["links"]) | set(parsed["gitlinks"]) | set(parsed["badmodes"]))
    if special:
        _add(refusals, DIFF_SPECIAL_MODE, "link, submodule or non-standard mode: "
             + ", ".join(_safe(p, 100) for p in special[:10]))
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
    return out


# ------------------------------------------------------------------ the builder
def build_final_package(
    *, story_id: str, base_head: str, head: str, diff_bytes: bytes, diff_sha256: str, changed_paths: Sequence[str],
    test_evidence: Sequence[Mapping[str, Any]], required_test_ids: Sequence[str], review_results: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]], isolation_proof: Mapping[str, Any],
    patch_origin_share: Mapping[str, Any] | None, now: str,
    allow_not_run: Mapping[str, str] | None = None, declared_limits: Sequence[str] = (),
    replay_store_verified: bool = False,
) -> PackageResult:
    """Build the final package bound to `head`, or refuse. Never raises for input problems; never mutates inputs.

    `diff_sha256` is the recorded diff digest (for example the gate evidence digest); `diff_bytes` must hash to
    it. `required_test_ids` (non-empty, from the caller) names the tests that must be PASS; each needs a record.
    `test_evidence` records: {test_id, status PASS/FAIL/NOT_RUN/SKIPPED, evidence_sha256, head} plus optional
    `reason`; a record cannot mark itself not required. PASS and FAIL need a digest and the head the evidence was
    produced at. At least one record must be PASS. `review_results` is `ReviewLoopResult.to_dict()` and must name
    `story_id`. `receipts` records: {receipt_id, head, receipt_sha256, result} (result must be PASS) plus optional
    receipt_type. `isolation_proof` is `worker_gate.build_isolation_proof` output; `patch_origin_share` a
    `patch_proposals.build_run_record` dict (bound to the head and the diff, ACCEPTED, applied, not partial) or
    None. `allow_not_run` maps a NOT_RUN or SKIPPED required test id to the operator-visible reason it may stay
    unrun. `declared_limits` are copied verbatim. `replay_store_verified` must be True for a review result that
    was replayed from the store. `now` is an RFC 3339 UTC timestamp ending in 'Z', recorded as created_at.
    """
    try:
        return _build(story_id, base_head, head, diff_bytes, diff_sha256, changed_paths, test_evidence,
                      required_test_ids, review_results, receipts, isolation_proof, patch_origin_share, now,
                      allow_not_run, declared_limits, replay_store_verified)
    except _Bad as exc:
        return PackageResult(BLOCKED, ((exc.code, exc.detail),), None, None)
    except Exception as exc:  # noqa: BLE001 - fail closed on anything unexpected (also RecursionError)
        return PackageResult(BLOCKED, ((INTERNAL_ERROR, _safe(type(exc).__name__)),), None, None)


def _build(story_id, base_head, head, diff_bytes, diff_sha256, changed_paths, test_evidence, required_test_ids,
           review_results, receipts, isolation_proof, patch_origin_share, now, allow_not_run, declared_limits,
           replay_store_verified):
    if type(replay_store_verified) is not bool:
        _bad(BAD_INPUT, "replay_store_verified must be a bool")
    try:  # private copies: nothing below can touch a caller object
        test_evidence = copy.deepcopy(test_evidence)
        required_test_ids = copy.deepcopy(required_test_ids)
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

    # secrets first: a hit ends the decision with fixed text, so no later detail can echo secret-like input
    hit = _secret_sections(_free_text(test_evidence, allow_not_run, review_results, receipts, isolation_proof,
                                      patch_origin_share, declared_limits))
    if hit:
        return PackageResult(REFUSED, tuple((SECRET_IN_EVIDENCE, f"{where} contains a value that looks like a secret")
                                            for where in hit), None, None)

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
    if not paths or any(_path_shape_problem(p) for p in paths) or len(set(paths)) != len(paths):
        _bad(BAD_INPUT, "changed_paths must be a non-empty list of unique plain path strings "
             "(no backtick, newline or control character)")

    refusals: list[tuple[str, str]] = []
    paths_digest = uc_contracts.changed_paths_sha256(paths)  # the same function the review loop and reports use
    diff = _diff_section(diff_bytes, diff_sha256, paths, refusals)
    diff["changed_paths_sha256"] = paths_digest
    tests, not_run = _tests_section(test_evidence, allow_not_run, required_test_ids, head, refusals)
    review = _review_section(review_results, story_id, head, replay_store_verified, paths_digest, refusals)
    receipt_rows = _receipts_section(receipts, head, refusals)
    isolation = _isolation_section(isolation_proof, head, refusals)
    share = _share_section(patch_origin_share, head, diff_sha256, refusals)
    limits = _limits(declared_limits)
    if refusals:
        return PackageResult(REFUSED, tuple((c, _safe(d, 600)) for c, d in refusals), None, None)

    package = {
        "schema": PACKAGE_SCHEMA, "story_id": story_id, "head": head, "base_head": base_head,
        "valid_for_head": head, "created_at": now, "diff": diff, "tests": tests, "not_run": copy.deepcopy(not_run),
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
def verify_package_current(package: Any, current_head: Any, current_diff_sha256: Any,
                           package_sha256: Any) -> tuple[bool, tuple[tuple[str, str], ...]]:
    """(ok, reasons): False when the head or the diff differ from the package, or the package is not coherent.

    A new commit changes the head (and usually the diff), so the package stops being current. `package_sha256`
    is required: the package is re-hashed and must equal it. Every embedded head (review final head and last
    iteration head, isolation proof, test records that ran, receipts, patch origin record) must equal `head`.
    Never raises and never mutates the package.
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
        if not (isinstance(package_sha256, str) and _SHA256.match(package_sha256)):
            return False, ((BAD_INPUT, "package_sha256 is required and must be 64 lowercase hex characters"),)
        if valid != head:
            reasons.append((PACKAGE_INCONSISTENT, "valid_for_head differs from head"))
        review = package.get("review") if isinstance(package.get("review"), Mapping) else {}
        last = review.get("last_iteration")
        embedded = [("review.final_head", review.get("final_head")),
                    ("review.last_iteration.head", last.get("head") if isinstance(last, Mapping) else None),
                    ("isolation.candidate_head", (package.get("isolation") or {}).get("candidate_head"))]
        for record in (package.get("tests") or {}).get("records", ()):
            if record.get("status") in ("PASS", "FAIL"):
                embedded.append((f"test:{_safe(record.get('test_id'), 100)}", record.get("head")))
        embedded += [(f"receipt:{_safe(r.get('receipt_id'), 100)}", r.get("head")) for r in package.get("receipts") or ()]
        share = package.get("patch_origin_share")
        if share is not None:
            embedded.append(("patch_origin_share.candidate_head", share.get("candidate_head")))
        for item, found in embedded:
            if found != head:
                reasons.append((PACKAGE_INCONSISTENT, f"{item} does not name the package head"))
        if current_head != valid:
            reasons.append((HEAD_CHANGED, f"the package is valid for {_safe(valid, 80)}, the current head is {current_head}"))
        if current_diff_sha256 != diff_sha:
            reasons.append((DIFF_CHANGED, f"the package diff is {diff_sha}, the current diff is {current_diff_sha256}"))
        diff_paths = diff.get("changed_paths")
        expected_paths = uc_contracts.changed_paths_sha256(list(diff_paths)) if isinstance(diff_paths, list) else None
        for item, found in (("diff.changed_paths_sha256", diff.get("changed_paths_sha256")),
                            ("review.changed_paths_sha256", review.get("changed_paths_sha256"))):
            if expected_paths is None or found != expected_paths:
                reasons.append((PACKAGE_INCONSISTENT, f"{item} is not the digest of diff.changed_paths"))
        if hashlib.sha256(canonical_bytes(package)).hexdigest() != package_sha256:
            reasons.append((PACKAGE_TAMPERED, "the package does not hash to the given package_sha256"))
    except Exception as exc:  # noqa: BLE001 - fail closed
        return False, ((PACKAGE_MALFORMED, _safe(type(exc).__name__)),)
    return (not reasons), tuple(reasons)


# ------------------------------------------------------------------ rendering
_MD_SPECIAL = frozenset("\\`*_[]<>&|")
_MD_LEADING = frozenset("#-+=~")


def escape_markdown(value: Any) -> str:
    """Make untrusted text inert in Markdown: one line, no emphasis, code, links, tables, HTML or block starts."""
    text = re.sub(r"[\x00-\x1f\x7f  ]+", " ", value if isinstance(value, str) else str(value))
    out = "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in text)
    if out[:1] in _MD_LEADING:
        out = "\\" + out
    return re.sub(r"^(\d+)([.)])", r"\1\\\2", out)


def render_scope_note(package: Mapping[str, Any]) -> str:
    """Deterministic English Markdown for the reviewer. States only what the package data says.

    Every evidence-derived string goes through `escape_markdown`; only validated hex values sit in code spans.
    Raises ValueError when `package` is not a package of this schema.
    """
    e = escape_markdown
    try:
        if not isinstance(package, Mapping) or package["schema"] != PACKAGE_SCHEMA:
            raise ValueError("not a final package")
        diff, tests, review = package["diff"], package["tests"], package["review"]
        lines = [
            f"# Final package for story {e(package['story_id'])}", "",
            f"- Head: `{e(package['head'])}` (this package is valid for this head only; a new commit invalidates it)",
            f"- Base head: `{e(package['base_head'])}`",
            f"- Created at: {e(package['created_at'])}",
            f"- Diff sha256: `{e(diff['sha256'])}` ({int(diff['bytes'])} bytes, {int(diff['path_count'])} path(s))", "",
            "## What changed", "",
        ]
        lines += [f"- {e(p)}" for p in diff["changed_paths"]]
        lines += [f"- rename: {e(a)} -> {e(b)}" for a, b in diff["renames"]]
        last = review["last_iteration"] or {}
        lines += ["", "## Review", "",
                  f"- Local review loop verdict: {e(review['verdict'])} at head `{e(review['final_head'])}` after "
                  f"{int(review['iteration_count'])} iteration(s)",
                  f"- Declared coverage: {', '.join(e(c) for c in review['declared_coverage']) or 'none'}",
                  f"- Last iteration: {e(last.get('iteration_id'))} ({e(last.get('verdict'))}, "
                  f"{e(last.get('findings_count'))} finding(s))",
                  f"- Replayed from the store: {'yes' if review['replayed'] else 'no'}"
                  f"{' (store facts verified by the caller)' if review['replayed'] and review['replay_store_verified'] else ''}",
                  f"- Reviewed paths sha256: `{e(review['changed_paths_sha256'])}` (equals the digest of the changed "
                  f"paths above)",
                  f"- Result sha256: `{e(review['result_sha256'])}`", "", "## Test evidence", ""]
        counts = tests["counts"]
        lines.append(f"- Records: PASS {int(counts['PASS'])}, FAIL {int(counts['FAIL'])}, "
                     f"NOT_RUN {int(counts['NOT_RUN'])}, SKIPPED {int(counts['SKIPPED'])}")
        lines.append(f"- Required test ids: {', '.join(e(i) for i in tests['required_test_ids'])}")
        for record in tests["records"]:
            if record["status"] == "PASS":
                lines.append(f"- PASS record: {e(record['test_id'])} at head `{e(record['head'])}`, evidence "
                             f"`{e(record['evidence_sha256'])}`")
        lines += ["", "## NOT_RUN items", ""]
        if package["not_run"]:
            lines.append("No claim is made for these items; they are not counted as results.")
            for item in package["not_run"]:
                ack = item["acknowledged_reason"]
                # status is an enum validated at build time (NOT_RUN or SKIPPED): written as is, not escaped
                status = item["status"] if item["status"] in _NOT_PASSED else "?"
                lines.append(f"- {e(item['test_id'])}: {status}, required: {'yes' if item['required'] else 'no'}, "
                             f"reason: {e(item['reason']) if item['reason'] else 'none'}, "
                             f"acknowledged: {e(ack) if ack else 'no'}")
        else:
            lines.append("- none")
        lines += ["", "## Receipts", ""]
        lines += ([f"- {e(r['receipt_id'])} ({e(r['receipt_type']) if r['receipt_type'] else 'type not given'}, "
                   f"result {e(r['result'])}) at head `{e(r['head'])}`, sha256 `{e(r['receipt_sha256'])}`"
                   for r in package["receipts"]] or ["- none supplied"])
        lines += ["", "## Isolation", ""]
        lines += [f"- {e(p['property'])}: {e(p['status'])} - {e(p['detail'])}" for p in package["isolation"]["properties"]]
        share = package["patch_origin_share"]
        lines += ["", "## Change origin", ""]
        if share is None:
            lines.append("- no patch origin record was supplied")
        else:
            lines.append(f"- Proposal lines {int(share['proposal_lines'])}, model lines {int(share['model_lines'])}, total "
                         f"{int(share['total_lines'])}; proposal fraction {e(share['proposal_fraction'])}, model fraction "
                         f"{e(share['model_fraction'])}; run verdict {e(share['verdict'])}, applied: "
                         f"{'yes' if share['applied'] else 'no'}")
            lines += [f"- Model only path: {e(p)}" for p in share["model_only_paths"]]
            lines += [f"- Files touched by both: {e(p)}" for p in share["files_touched_by_both"]]
            lines += ["- Override: " + ", ".join(f"{e(k)}={e(v)}" for k, v in o.items()) for o in share["overrides"]]
            lines.append(f"- Overrides recorded: {len(share['overrides'])}")
        lines += ["", "## Declared limits (caller-supplied, verbatim apart from escaping)", ""]
        lines += [f"- {e(item)}" for item in package["declared_limits"]] or ["- none"]
        lines += ["", "## Derived limits", ""]
        lines += [f"- {e(item)}" for item in package["derived_limits"]]
        lines += ["", "## Evidence digests", "", f"- Diff: `{e(package['evidence_digests']['diff_sha256'])}`",
                  f"- Review result: `{e(package['evidence_digests']['review_result_sha256'])}`",
                  f"- Isolation proof: `{e(package['evidence_digests']['isolation_proof_sha256'])}`", ""]
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"package is malformed: {type(exc).__name__}") from exc
    return "\n".join(lines)
