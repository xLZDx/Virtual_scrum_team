"""U5-4: review-loop driver (resubmit with iteration_of until local checks are clean or a cap is hit).

The driver decides; it applies nothing. Every external action is INJECTED so a test needs no AEVE,
no model and no process:

* `submit(ReviewRequest) -> report`   runs ONE local review of the current candidate and returns the parsed
  `uc.role-result.v1` document (tools/uc/contracts.py). A raise, a non-dict, a `uc.blocked.v1` envelope or a
  contract violation makes the loop BLOCKED; nothing is recorded for it (no judgeable report exists).
* `verify_report(report) -> bool`     says whether the report's integrity (signature or digest) was verified.
  Only the exact value True counts; False, any other value, or a raise means "unverifiable".
* `fixer(FixContext) -> Candidate`    optional; produces the next candidate for the open findings. Its output
  goes through the already-built worker gate (`gate`, default `worker_gate.gate_worker_change`) and the gate
  verdict is recorded; a candidate that is not ACCEPTED ends the loop.
* `clock() -> float`                  seconds; used for timestamps and the optional total deadline.

Verdict. The result is CLEAN or BLOCKED, never anything else, and a verdict never upgrades.

CLEAN needs, for the LAST iteration, all of: a valid report for this request and this head, a fresh iteration
id (not one already seen in this loop), verified integrity, no findings, no model residual, every role CLEAN
with nothing uncovered, and every DECLARED executor id reported COMPLETE (reported coverage equals or exceeds
the declaration), and the report's purpose is "receipt" and its changed-paths digest is the expected one. A
partial or unsupported role, a missing declared executor, a report for another head, an advisory report, a
report for other paths, a repeated (stale) report or an unverifiable report is never CLEAN. CLEAN is returned only after the CLEAN
iteration row was recorded in `PipelineState`. The result carries `changed_paths_sha256` (the digest the reports
were checked against; a CLEAN result cannot be built without it) so a consumer can bind the review to a path set.

BLOCKED reasons (stable codes): ITERATION_CAP, NO_PROGRESS, NO_FIXER, STOPPED, EPOCH_STALE, DEADLINE,
SUBMIT_FAILED, SUBMIT_BLOCKED, BAD_REPORT, FIXER_FAILED, GATE_REFUSED, GATE_BLOCKED, GATE_NOT_ACCEPTED,
GATE_FAILED, STORE_ERROR, RESUME_MISMATCH, CALLBACK_FAILED, CLOCK_FAILED, BAD_INPUT,
CAP_INVALID, INTERNAL_ERROR. Details are ASCII-escaped and truncated.

Bounds. The cap is an int >= 1 (otherwise CAP_INVALID, nothing runs) and is clamped to MAX_ITERATIONS. Every
loop pass either ends or adds one iteration, so at most MAX_ITERATIONS submits happen per call.

Idempotency. Step ids are derived from attempt and story-level iteration index only: review `rl-a<attempt>-i<index>`,
gate `rl-a<attempt>-i<index>-gate` (gate id `rl-a<attempt>-g<index>`). The review step and the gate step carry the
loop's facts (AEVE iteration id, head, coverage, finding digest and findings, reasons; candidate head, diff digest
and verdict) in the step result, written in the SAME transaction as the row (`facts=` of `PipelineState`). A
repeated call therefore rebuilds every summary from the store: recorded iterations are never submitted again, a
recorded gate is adopted (or its refusal reported) without calling the fixer again, and nothing that existed
only in memory is needed. `resume` is an optional cross-check against what the store returned.

Standard library only. Details: docs/sdlc/u5/REVIEW_LOOP.md.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from ..uc import contracts as uc_contracts
from .pipeline_state import PipelineState
from .store import StoreError
from .worker_gate import ACCEPTED as GATE_ACCEPTED
from .worker_gate import BLOCKED as GATE_BLOCKED_VERDICT
from .worker_gate import REFUSED as GATE_REFUSED_VERDICT
from .worker_gate import WorkerGateVerdict, gate_worker_change

MAX_ITERATIONS = 10
MAX_DECLARED = 256
MAX_DETAIL = 300
MAX_SUMMARY_FINDINGS = 200

CLEAN = "CLEAN"
BLOCKED = "BLOCKED"
ITERATION_VERDICTS = ("CLEAN", "FINDINGS", "PARTIAL", "BLOCKED")

# loop-ending reason codes
ITERATION_CAP = "ITERATION_CAP"
NO_PROGRESS = "NO_PROGRESS"
NO_FIXER = "NO_FIXER"
STOPPED = "STOPPED"
EPOCH_STALE = "EPOCH_STALE"
DEADLINE = "DEADLINE"
SUBMIT_FAILED = "SUBMIT_FAILED"
SUBMIT_BLOCKED = "SUBMIT_BLOCKED"
BAD_REPORT = "BAD_REPORT"
FIXER_FAILED = "FIXER_FAILED"
GATE_REFUSED = "GATE_REFUSED"
GATE_BLOCKED = "GATE_BLOCKED"
GATE_NOT_ACCEPTED = "GATE_NOT_ACCEPTED"
GATE_FAILED = "GATE_FAILED"
STORE_ERROR = "STORE_ERROR"
RESUME_MISMATCH = "RESUME_MISMATCH"
CALLBACK_FAILED = "CALLBACK_FAILED"
CLOCK_FAILED = "CLOCK_FAILED"
BAD_INPUT = "BAD_INPUT"
CAP_INVALID = "CAP_INVALID"
INTERNAL_ERROR = "INTERNAL_ERROR"

# per-iteration reasons (why one iteration is not CLEAN)
REQUEST_MISMATCH = "REQUEST_MISMATCH"
HEAD_MISMATCH = "HEAD_MISMATCH"
PURPOSE_NOT_RECEIPT = "PURPOSE_NOT_RECEIPT"
PATHS_MISMATCH = "PATHS_MISMATCH"
REPORT_STALE = "REPORT_STALE"
SIGNATURE_UNVERIFIED = "SIGNATURE_UNVERIFIED"
FINDINGS_OPEN = "FINDINGS_OPEN"
MODEL_RESIDUAL_OPEN = "MODEL_RESIDUAL_OPEN"
COVERAGE_PARTIAL = "COVERAGE_PARTIAL"
DECLARED_EXECUTOR_MISSING = "DECLARED_EXECUTOR_MISSING"
EXIT_NOT_ZERO = "EXIT_NOT_ZERO"
_INTEGRITY_REASONS = (REQUEST_MISMATCH, HEAD_MISMATCH, PURPOSE_NOT_RECEIPT, PATHS_MISMATCH, REPORT_STALE,
                      SIGNATURE_UNVERIFIED)
FACTS_SCHEMA = "rl-iteration-facts-v1"
GATE_FACTS_SCHEMA = "rl-gate-facts-v1"
_FACT_KEYS = frozenset({
    "schema", "iteration_id", "iteration_of", "head", "coverage", "missing_coverage", "finding_set_sha256",
    "findings_count", "findings", "findings_truncated", "reasons", "changed_paths_sha256"})
_GATE_FACT_KEYS = frozenset({"schema", "base_head", "candidate_head", "diff_sha256", "verdict", "reason_codes"})
_GAP_STATUSES = ("PARTIAL", "NOT_COVERED", "NOT_RUN", "BLOCKED")

_HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_HEAD40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}\Z")  # same as tools/uc/contracts.py _TOKEN
_STORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")  # same as pipeline_state._ID


# ------------------------------------------------------------------ small helpers
def _safe(value: Any, limit: int = MAX_DETAIL) -> str:
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


def _exc_text(exc: BaseException) -> str:
    return _safe(f"{type(exc).__name__}: {exc}")


def request_id_for(story_id: str, attempt_no: int) -> str:
    """Deterministic request id of one attempt: 'rl-' + first 40 hex of sha256(story NUL attempt)."""
    return "rl-" + hashlib.sha256(f"{story_id}\x00{attempt_no}".encode("utf-8")).hexdigest()[:40]


def review_step_id(attempt_no: int, iteration_index: int) -> str:
    return f"rl-a{attempt_no}-i{iteration_index}"


def gate_step_id(attempt_no: int, iteration_index: int) -> str:
    return f"rl-a{attempt_no}-i{iteration_index}-gate"


def gate_id_for(attempt_no: int, iteration_index: int) -> str:
    return f"rl-a{attempt_no}-g{iteration_index}"


def finding_set_sha256(findings: Sequence[Mapping[str, Any]]) -> str:
    """sha256 of the sorted finding keys (role, rule, severity, path, line, column, evidence hash)."""
    keys = sorted(
        [f["role"], f["rule_id"], f["severity"], f["path"], f["line"], f["column"], f["evidence_hash"]]
        for f in findings
    )
    blob = json.dumps(keys, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ data
@dataclass(frozen=True)
class ReviewRequest:
    """What `submit` is asked to review. `iteration_of` is the previous iteration's id (None for the first)."""

    story_id: str
    attempt_no: int
    local_index: int          # 1-based position inside this attempt's loop
    iteration_index: int      # story-level index in pl_review_iterations
    request_id: str
    head: str                 # the candidate head to review
    iteration_of: str | None
    declared_coverage: tuple[str, ...]
    changed_paths_sha256: str | None = None   # the digest the report must carry (uc.role-result.v1 field)
    purpose: str = "receipt"                  # the purpose the report must carry for CLEAN


@dataclass(frozen=True)
class FixContext:
    """What `fixer` gets: the trusted open findings of the last iteration and the head they belong to."""

    story_id: str
    attempt_no: int
    local_index: int
    iteration_index: int
    head: str
    iteration_id: str
    findings: tuple[dict, ...]
    declared_coverage: tuple[str, ...]
    truncated: bool = False   # True when the loop kept only the first MAX_SUMMARY_FINDINGS findings


@dataclass(frozen=True)
class Candidate:
    """The fixer's next candidate and what the worker gate needs to judge it (gate defaults: no links, no renames)."""

    head: str
    changed_paths: tuple[str, ...]
    diff_bytes: bytes
    isolation: Any
    symlink_paths: tuple[str, ...] = ()
    rename_pairs: tuple[tuple[str, str], ...] = ()


class ReportUnusable(Exception):
    """No judgeable report: `code` is SUBMIT_BLOCKED or BAD_REPORT."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = _safe(detail)


@dataclass(frozen=True)
class Judgement:
    verdict: str                          # CLEAN, FINDINGS, PARTIAL or BLOCKED (the PipelineState vocabulary)
    reasons: tuple[str, ...]              # empty only for CLEAN
    iteration_id: str
    findings: tuple[dict, ...]
    covered: tuple[str, ...]              # executor ids reported COMPLETE in every role that lists them
    missing: tuple[str, ...]              # declared executor ids that are not covered
    exit_code: int


@dataclass(frozen=True)
class IterationSummary:
    local_index: int
    iteration_index: int
    step_id: str
    iteration_id: str
    iteration_of: str | None
    head: str
    findings_count: int
    findings: tuple[dict, ...]
    finding_set_sha256: str
    coverage: tuple[str, ...]
    missing_coverage: tuple[str, ...]
    verdict: str
    reasons: tuple[str, ...]
    truncated: bool = False
    replayed: bool = False
    started_at: float | None = None
    finished_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "local_index": self.local_index, "iteration_index": self.iteration_index, "step_id": self.step_id,
            "iteration_id": self.iteration_id, "iteration_of": self.iteration_of, "head": self.head,
            "findings_count": self.findings_count, "findings": [dict(f) for f in self.findings],
            "finding_set_sha256": self.finding_set_sha256, "coverage": list(self.coverage),
            "missing_coverage": list(self.missing_coverage), "verdict": self.verdict,
            "reasons": list(self.reasons), "truncated": self.truncated, "replayed": self.replayed,
            "started_at": self.started_at, "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "IterationSummary":
        """Strict inverse of to_dict (also accepts an IterationSummary). Raises ValueError on any deviation."""
        if isinstance(data, cls):
            data = data.to_dict()
        if not isinstance(data, Mapping):
            raise ValueError("summary must be a mapping")
        names = ("local_index", "iteration_index", "step_id", "iteration_id", "iteration_of", "head",
                 "findings_count", "findings", "finding_set_sha256", "coverage", "missing_coverage",
                 "verdict", "reasons", "truncated", "replayed", "started_at", "finished_at")
        if set(data) != set(names):
            raise ValueError("summary keys differ from the expected set")

        def integer(name: str, minimum: int) -> int:
            value = data[name]
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name}: bad integer")
            return value

        def text(name: str, optional: bool = False) -> str | None:
            value = data[name]
            if value is None and optional:
                return None
            if not isinstance(value, str) or not value or len(value) > 200:
                raise ValueError(f"{name}: bad string")
            return value

        def strings(name: str) -> tuple[str, ...]:
            value = data[name]
            if (not isinstance(value, (list, tuple)) or len(value) > MAX_DECLARED
                    or any(not isinstance(item, str) or not item or len(item) > 200 for item in value)):
                raise ValueError(f"{name}: bad string list")
            return tuple(value)

        def moment(name: str) -> float | None:
            value = data[name]
            if value is None:
                return None
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name}: bad time")
            return float(value)

        head = data["head"]
        digest = data["finding_set_sha256"]
        findings = data["findings"]
        if not isinstance(head, str) or not _HEAD.match(head) or not isinstance(digest, str) or not _SHA256.match(digest):
            raise ValueError("head or finding digest malformed")
        if (not isinstance(findings, (list, tuple)) or len(findings) > MAX_SUMMARY_FINDINGS
                or any(not isinstance(item, Mapping) for item in findings)):
            raise ValueError("findings: bad list")
        verdict = data["verdict"]
        if verdict not in ITERATION_VERDICTS:
            raise ValueError("verdict: unknown")
        if type(data["replayed"]) is not bool or type(data["truncated"]) is not bool:
            raise ValueError("replayed or truncated: not a bool")
        return cls(
            local_index=integer("local_index", 1), iteration_index=integer("iteration_index", 1),
            step_id=text("step_id"), iteration_id=text("iteration_id"), iteration_of=text("iteration_of", True),
            head=head, findings_count=integer("findings_count", 0),
            findings=tuple(dict(item) for item in findings), finding_set_sha256=digest,
            coverage=strings("coverage"), missing_coverage=strings("missing_coverage"), verdict=verdict,
            reasons=strings("reasons"), truncated=data["truncated"], replayed=data["replayed"],
            started_at=moment("started_at"), finished_at=moment("finished_at"),
        )


@dataclass(frozen=True)
class ReviewLoopResult:
    verdict: str                                   # CLEAN or BLOCKED, nothing else
    reasons: tuple[tuple[str, str], ...]           # (code, ASCII-escaped detail); empty only for CLEAN
    iterations: tuple[IterationSummary, ...]
    story_id: str | None
    attempt_no: int | None
    declared_coverage: tuple[str, ...]
    cap_requested: int | None
    cap_effective: int | None
    cap_clamped: bool
    final_head: str | None
    submit_calls: int
    fixer_calls: int
    gates: tuple[dict, ...]
    replayed: bool = False     # True when no new work happened: every iteration came from the store
    # digest of the sorted reviewed paths every report carried (the loop input; for a replay the stored fact, which
    # the replay cross-checks against the input). None only for a BLOCKED result that never got a valid input.
    changed_paths_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.verdict not in (CLEAN, BLOCKED):
            raise ValueError("verdict must be CLEAN or BLOCKED")
        if self.changed_paths_sha256 is not None and (
                not isinstance(self.changed_paths_sha256, str) or not _SHA256.match(self.changed_paths_sha256)):
            raise ValueError("changed_paths_sha256 must be None or 64 lowercase hex characters")
        if self.verdict == CLEAN:
            if self.changed_paths_sha256 is None:
                raise ValueError("CLEAN needs the changed_paths_sha256 the reports were checked against")
            last = self.iterations[-1] if self.iterations else None
            proven = (
                last is not None and last.verdict == CLEAN and not self.reasons and not last.reasons
                and last.findings_count == 0 and not last.findings and bool(self.declared_coverage)
                and set(self.declared_coverage) <= set(last.coverage) and not last.missing_coverage
            )
            if not proven:
                raise ValueError("CLEAN needs a CLEAN last iteration that covers the declared coverage")
        elif not self.reasons:
            raise ValueError("BLOCKED needs at least one reason")

    @property
    def clean(self) -> bool:
        return self.verdict == CLEAN

    @property
    def iteration_count(self) -> int:
        return len(self.iterations)

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(code for code, _ in self.reasons)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict, "reasons": [{"code": c, "detail": d} for c, d in self.reasons],
            "iteration_count": self.iteration_count, "iterations": [i.to_dict() for i in self.iterations],
            "story_id": self.story_id, "attempt_no": self.attempt_no,
            "declared_coverage": list(self.declared_coverage), "cap_requested": self.cap_requested,
            "cap_effective": self.cap_effective, "cap_clamped": self.cap_clamped, "final_head": self.final_head,
            "submit_calls": self.submit_calls, "fixer_calls": self.fixer_calls,
            "gates": [dict(g) for g in self.gates], "replayed": self.replayed,
            "changed_paths_sha256": self.changed_paths_sha256,
        }


# ------------------------------------------------------------------ report judgement (pure)
def validate_report(report: Any) -> dict:
    """Return the report as a validated `uc.role-result.v1` dict or raise ReportUnusable."""
    if isinstance(report, Mapping) and report.get("schema_version") == uc_contracts.BLOCKED_SCHEMA:
        raise ReportUnusable(SUBMIT_BLOCKED, f"reason={report.get('reason')!s}")
    if not isinstance(report, dict):
        raise ReportUnusable(BAD_REPORT, f"report is {type(report).__name__}, not an object")
    try:
        return uc_contracts.validate_result(report)
    except uc_contracts.ContractError as exc:
        raise ReportUnusable(BAD_REPORT, f"{exc.code} at {exc.where}") from exc
    except Exception as exc:  # noqa: BLE001 - e.g. RecursionError on hostile nesting
        raise ReportUnusable(BAD_REPORT, type(exc).__name__) from exc


def judge_report(
    report: Any, *, request_id: str, head: str, declared: Sequence[str], seen_ids: Sequence[str],
    verify_report: Callable[[Any], Any], changed_paths_sha256: str,
) -> Judgement:
    """Judge ONE report. CLEAN only when no reason applies; every doubt is a reason. Raises ReportUnusable."""
    doc = validate_report(report)
    try:
        verified = verify_report(copy.deepcopy(doc)) is True  # a verifier gets a copy: it cannot alter what is judged
    except Exception:  # noqa: BLE001 - an unverifiable report is a reason, not a crash
        verified = False
    findings: list[dict] = []
    residual = False
    gap = False
    standing: dict[str, bool] = {}
    for role in doc["roles"]:
        for item in role["findings"]:
            findings.append({"role": role["role"], **item})
        residual = residual or bool(role["model_residual"])
        gap = gap or role["status"] in _GAP_STATUSES or bool(role["uncovered"])
        for executor in role["executors"]:
            standing[executor["id"]] = standing.get(executor["id"], True) and executor["status"] == "COMPLETE"
    covered = tuple(sorted(name for name, complete in standing.items() if complete))
    missing = tuple(sorted(set(declared) - set(covered)))
    reasons: list[str] = []
    if doc["request_id"] != request_id:
        reasons.append(REQUEST_MISMATCH)
    if doc["base_revision"] != head:
        reasons.append(HEAD_MISMATCH)
    if doc["purpose"] != "receipt":
        reasons.append(PURPOSE_NOT_RECEIPT)
    if doc["changed_paths_sha256"] != changed_paths_sha256:
        reasons.append(PATHS_MISMATCH)
    if doc["iteration_id"] in set(seen_ids):
        reasons.append(REPORT_STALE)
    if not verified:
        reasons.append(SIGNATURE_UNVERIFIED)
    if findings:
        reasons.append(FINDINGS_OPEN)
    if residual:
        reasons.append(MODEL_RESIDUAL_OPEN)
    if gap:
        reasons.append(COVERAGE_PARTIAL)
    if missing:
        reasons.append(DECLARED_EXECUTOR_MISSING)
    if doc["exit_code"] != 0:
        reasons.append(EXIT_NOT_ZERO)
    if any(r in _INTEGRITY_REASONS for r in reasons):
        verdict = BLOCKED
    elif findings:
        verdict = "FINDINGS"
    elif reasons:
        verdict = "PARTIAL"
    else:
        verdict = CLEAN
    return Judgement(verdict, tuple(reasons), doc["iteration_id"], tuple(findings), covered, missing, doc["exit_code"])


def _facts_for(judged: Judgement, request: ReviewRequest, head: str, digest: str, truncated: bool) -> dict:
    return {
        "schema": FACTS_SCHEMA, "iteration_id": judged.iteration_id, "iteration_of": request.iteration_of,
        "head": head, "coverage": list(judged.covered), "missing_coverage": list(judged.missing),
        "finding_set_sha256": digest, "findings_count": len(judged.findings),
        "findings": [dict(f) for f in judged.findings[:MAX_SUMMARY_FINDINGS]], "findings_truncated": truncated,
        "reasons": list(judged.reasons), "changed_paths_sha256": request.changed_paths_sha256,
    }


def _summary_from_facts(facts: Any, *, local_index: int, iteration_index: int, step_id: str, verdict: str) -> IterationSummary:
    """Rebuild a summary from the facts stored in a review step. Raises ValueError on any deviation."""
    if not isinstance(facts, Mapping) or set(facts) != _FACT_KEYS or facts["schema"] != FACTS_SCHEMA:
        raise ValueError("facts: wrong shape or schema")

    def text(name: str, optional: bool = False) -> str | None:
        value = facts[name]
        if value is None and optional:
            return None
        if not isinstance(value, str) or not value or len(value) > 200:
            raise ValueError(f"facts.{name}: bad string")
        return value

    def strings(name: str) -> tuple[str, ...]:
        value = facts[name]
        if (not isinstance(value, list) or len(value) > MAX_DECLARED
                or any(not isinstance(i, str) or not i or len(i) > 200 for i in value)):
            raise ValueError(f"facts.{name}: bad string list")
        return tuple(value)

    head, digest, paths = facts["head"], facts["finding_set_sha256"], facts["changed_paths_sha256"]
    if (not isinstance(head, str) or not _HEAD.match(head) or not isinstance(digest, str) or not _SHA256.match(digest)
            or not isinstance(paths, str) or not _SHA256.match(paths)):
        raise ValueError("facts: head or digest malformed")
    count, findings, truncated = facts["findings_count"], facts["findings"], facts["findings_truncated"]
    if type(count) is not int or count < 0 or type(truncated) is not bool:
        raise ValueError("facts: bad count or truncated flag")
    if (not isinstance(findings, list) or len(findings) > MAX_SUMMARY_FINDINGS
            or any(not isinstance(f, dict) for f in findings)):
        raise ValueError("facts.findings: bad list")
    if truncated:
        if count <= len(findings):
            raise ValueError("facts: truncated but nothing was cut")
    else:
        if count != len(findings):
            raise ValueError("facts: finding count differs from the stored findings")
        try:
            recomputed = finding_set_sha256(findings)
        except (KeyError, TypeError) as exc:
            raise ValueError("facts.findings: malformed finding") from exc
        if recomputed != digest:
            raise ValueError("facts: finding digest differs from the stored findings")
    return IterationSummary(
        local_index=local_index, iteration_index=iteration_index, step_id=step_id, iteration_id=text("iteration_id"),
        iteration_of=text("iteration_of", True), head=head, findings_count=count,
        findings=tuple(dict(f) for f in findings), finding_set_sha256=digest, coverage=strings("coverage"),
        missing_coverage=strings("missing_coverage"), verdict=verdict, reasons=strings("reasons"),
        truncated=truncated, replayed=True)


def _gate_facts_ok(facts: Any, verdict: Any) -> bool:
    return (
        isinstance(facts, Mapping) and set(facts) == _GATE_FACT_KEYS and facts["schema"] == GATE_FACTS_SCHEMA
        and isinstance(facts["base_head"], str) and bool(_HEAD40.match(facts["base_head"]))
        and isinstance(facts["candidate_head"], str) and bool(_HEAD40.match(facts["candidate_head"]))
        and (facts["diff_sha256"] is None
             or (isinstance(facts["diff_sha256"], str) and bool(_SHA256.match(facts["diff_sha256"]))))
        and facts["verdict"] == verdict and isinstance(facts["reason_codes"], list)
        and all(isinstance(c, str) for c in facts["reason_codes"]))


def _core(summary: IterationSummary) -> dict:
    doc = summary.to_dict()
    for name in ("replayed", "started_at", "finished_at"):
        doc.pop(name)
    return doc


# ------------------------------------------------------------------ the driver
class _Halt(Exception):
    """Internal: the loop ends BLOCKED with these (code, detail) reasons."""

    def __init__(self, items: Sequence[tuple[str, str]]) -> None:
        super().__init__(items[0][0] if items else "halt")
        self.items = tuple((code, _safe(detail)) for code, detail in items)


def _halt(code: str, detail: str = "") -> None:
    raise _Halt([(code, detail)])


class _Loop:
    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)
        self.history: list[IterationSummary] = []
        self.gates: list[dict] = []
        self.submit_calls = 0
        self.fixer_calls = 0
        self.cap: int | None = None
        self.clamped = False
        self.declared: tuple[str, ...] = ()
        self.head: str | None = None
        self.first_index = 1
        self.t0 = 0.0
        self.last_now: float | None = None
        self.facts_paths: str | None = None   # changed_paths_sha256 of the last stored or recorded review facts

    # ------------------------------------------------------------- inputs
    def _validate_inputs(self) -> None:
        cap = self.iteration_cap
        if type(cap) is not int or cap < 1:
            _halt(CAP_INVALID, f"iteration_cap must be an integer >= 1, got {_safe(repr(cap), 60)}")
        self.cap = min(cap, MAX_ITERATIONS)
        self.clamped = cap > MAX_ITERATIONS
        if not isinstance(self.state, PipelineState):
            _halt(BAD_INPUT, "state must be a PipelineState")
        if not isinstance(self.story_id, str) or not _STORY.match(self.story_id):
            _halt(BAD_INPUT, "story_id is malformed")
        for name in ("epoch", "attempt_no"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                _halt(BAD_INPUT, f"{name} must be an integer >= 1")
        if not isinstance(self.initial_head, str) or not _HEAD.match(self.initial_head):
            _halt(BAD_INPUT, "initial_head must be a lowercase 40 or 64 hex commit id")
        declared = self.declared_coverage
        if (isinstance(declared, (str, bytes)) or not isinstance(declared, (list, tuple, set, frozenset))
                or not declared or len(declared) > MAX_DECLARED
                or any(not isinstance(item, str) or not _TOKEN.match(item) for item in declared)
                or len(set(declared)) != len(declared)):
            _halt(BAD_INPUT, "declared_coverage must be a non-empty collection of unique executor ids")
        self.declared = tuple(sorted(declared))
        if not isinstance(self.changed_paths_sha256, str) or not _SHA256.match(self.changed_paths_sha256):
            _halt(BAD_INPUT, "changed_paths_sha256 must be 64 lowercase hex characters")
        if self.fixer is not None and (
                not isinstance(self.manifest_sha256, str) or not _SHA256.match(self.manifest_sha256)):
            _halt(BAD_INPUT, "manifest_sha256 must be 64 lowercase hex characters when a fixer is given")
        for name in ("submit", "verify_report", "clock", "gate"):
            if not callable(getattr(self, name)):
                _halt(BAD_INPUT, f"{name} must be callable")
        for name in ("fixer", "on_iteration"):
            value = getattr(self, name)
            if value is not None and not callable(value):
                _halt(BAD_INPUT, f"{name} must be callable or None")
        total = self.max_total_seconds
        if total is not None and (type(total) not in (int, float) or not math.isfinite(total) or total <= 0):
            _halt(BAD_INPUT, "max_total_seconds must be None or a positive number")
        if isinstance(self.resume, (str, bytes)) or not isinstance(self.resume, (list, tuple)):
            _halt(BAD_INPUT, "resume must be a list or tuple of summaries")
        self.head = self.initial_head

    # ------------------------------------------------------------- environment checks
    def _now(self) -> float:
        try:
            value = self.clock()
        except Exception as exc:  # noqa: BLE001
            raise _Halt([(CLOCK_FAILED, _exc_text(exc))]) from exc
        if type(value) not in (int, float) or not math.isfinite(value):
            _halt(CLOCK_FAILED, "clock returned a non-finite or non-numeric value")
        if self.last_now is not None and value < self.last_now:
            _halt(CLOCK_FAILED, "clock went backwards")
        self.last_now = float(value)
        return self.last_now

    def _store_halt(self, exc: StoreError) -> None:
        kind = getattr(exc, "kind", "?")
        if kind == "stopped":
            _halt(STOPPED, f"story {self.story_id} is stopped")
        if kind == "epoch":
            _halt(EPOCH_STALE, str(exc))
        _halt(STORE_ERROR, f"kind={kind}: {exc}")

    def _guard(self) -> None:
        """Epoch first, then stop, exactly like a pipeline step. Called before every external action."""
        try:
            status = self.state.get_status(self.story_id)
        except StoreError as exc:
            self._store_halt(exc)
            return
        if int(status["epoch"]) != self.epoch:
            _halt(EPOCH_STALE, f"epoch {self.epoch} is not the story epoch {int(status['epoch'])}")
        if status["stopped"]:
            _halt(STOPPED, f"story {self.story_id} is stopped")

    def _check_attempt(self) -> None:
        try:
            attempts = self.state.list_worker_attempts(self.story_id)
        except StoreError as exc:
            self._store_halt(exc)
            return
        row = next((a for a in attempts if a["attempt_no"] == self.attempt_no), None)
        if row is None:
            _halt(STORE_ERROR, f"unknown worker attempt {self.attempt_no}")
        if row["state"] == "STOPPED":
            _halt(STOPPED, f"worker attempt {self.attempt_no} was stopped")

    def _check_deadline(self) -> None:
        if self.max_total_seconds is not None and self._now() - self.t0 > self.max_total_seconds:
            _halt(DEADLINE, f"more than {self.max_total_seconds} seconds since the loop started")

    # ------------------------------------------------------------- replay (from the store)
    def _get_step(self, step_id: str) -> dict | None:
        try:
            return self.state.get_step(self.story_id, step_id)
        except StoreError as exc:
            self._store_halt(exc)
            return None

    def _stored_gate(self, iteration_index: int) -> tuple[str, dict] | None:
        """The recorded gate step of this iteration as (verdict, facts), or None when there is none."""
        stored = self._get_step(gate_step_id(self.attempt_no, iteration_index))
        if stored is None:
            return None
        result = stored.get("result") or {}
        verdict, facts = result.get("verdict"), result.get("facts")
        if (stored.get("kind") != "DIFF_GATE" or result.get("gate_id") != gate_id_for(self.attempt_no, iteration_index)
                or not _gate_facts_ok(facts, verdict)):
            _halt(RESUME_MISMATCH, f"the gate step of iteration {iteration_index} carries no usable review-loop facts")
        return verdict, dict(facts)

    def _load_replay(self) -> None:
        try:
            rows = self.state.list_review_iterations(self.story_id)
        except StoreError as exc:
            self._store_halt(exc)
            return
        mine = [r for r in rows if r["attempt_no"] == self.attempt_no]
        last_index = max((int(r["iteration_index"]) for r in rows), default=0)
        if not mine:
            if self.resume:
                _halt(RESUME_MISMATCH, "resume summaries were given but no iteration of this attempt is recorded")
            self.first_index = last_index + 1
            return
        first = int(mine[0]["iteration_index"])
        consecutive = all(int(r["iteration_index"]) == first + n for n, r in enumerate(mine))
        if not consecutive or int(mine[-1]["iteration_index"]) != last_index:
            _halt(RESUME_MISMATCH, "recorded iterations of this attempt are not the last consecutive rows of the story")
        self.first_index = first
        if self.resume and len(self.resume) != len(mine):
            _halt(RESUME_MISMATCH, f"{len(self.resume)} resume summaries for {len(mine)} recorded iterations")
        for n, row in enumerate(mine, 1):
            index = int(row["iteration_index"])
            previous = self.history[-1] if self.history else None
            step_id = review_step_id(self.attempt_no, index)
            stored = self._get_step(step_id)
            if stored is None or stored.get("kind") != "REVIEW_ITERATION":
                _halt(RESUME_MISMATCH, f"iteration {index} has no recorded review step")
            result = stored.get("result") or {}
            try:
                summary = _summary_from_facts(
                    result.get("facts"), local_index=n, iteration_index=index, step_id=step_id, verdict=row["verdict"])
            except ValueError as exc:
                raise _Halt([(RESUME_MISMATCH, f"iteration {index}: {exc}")]) from exc
            facts = result["facts"]
            problems = []
            if row["step_id"] != step_id or result.get("iteration_index") != index or result.get("verdict") != row["verdict"]:
                problems.append("step")
            if int(row["findings_count"]) != summary.findings_count:
                problems.append("finding count")
            if list(row["coverage_declared"]) != list(self.declared):
                problems.append("declared coverage")
            if row["iteration_of"] != (index - 1 if index > 1 else None):
                problems.append("recorded iteration_of")
            if summary.iteration_of != (previous.iteration_id if previous else None):
                problems.append("iteration_of chain")
            if facts["changed_paths_sha256"] != self.changed_paths_sha256:
                problems.append("changed paths digest")
            if n == 1 and summary.head != self.initial_head:
                problems.append("first head")
            if previous is not None:
                expected = previous.head
                if previous.verdict == "FINDINGS":
                    gate = self._stored_gate(previous.iteration_index)
                    ok = gate is not None and gate[0] == GATE_ACCEPTED and gate[1]["base_head"] == previous.head
                    expected = gate[1]["candidate_head"] if ok else None
                if summary.head != expected:
                    problems.append("head continuity")
            if any(summary.iteration_id == s.iteration_id for s in self.history):
                problems.append("repeated iteration id")
            if summary.verdict == CLEAN and (
                    summary.reasons or summary.findings_count or not set(self.declared) <= set(summary.coverage)):
                problems.append("CLEAN without proof")
            if problems:
                _halt(RESUME_MISMATCH, f"iteration {index} differs from the store: {', '.join(problems)}")
            if self.resume:
                try:
                    given = IterationSummary.from_dict(self.resume[n - 1])
                except ValueError as exc:
                    raise _Halt([(RESUME_MISMATCH, f"resume summary {n}: {exc}")]) from exc
                if _core(given) != _core(summary):
                    _halt(RESUME_MISMATCH, f"resume summary {n} differs from the stored iteration")
            self.history.append(summary)
            self.facts_paths = facts["changed_paths_sha256"]   # equal to the input: checked above
        if any(s.verdict == CLEAN for s in self.history[:-1]):
            _halt(RESUME_MISMATCH, "a CLEAN iteration is followed by another iteration")
        if len(self.history) > self.cap:
            _halt(ITERATION_CAP, f"{len(self.history)} recorded iterations exceed the cap {self.cap}")
        self.head = self.history[-1].head

    # ------------------------------------------------------------- main loop
    def run(self) -> ReviewLoopResult:
        self._validate_inputs()
        self.t0 = self._now()
        self._guard()
        self._check_attempt()
        self._load_replay()
        while True:
            if self.history:
                last = self.history[-1]
                if last.verdict == CLEAN:
                    return self.result(CLEAN, ())
                self._after_unclean(last)
            self._iterate()

    def _after_unclean(self, last: IterationSummary) -> None:
        items: list[tuple[str, str]] = []
        if len(self.history) >= self.cap:
            items.append((ITERATION_CAP, f"{len(self.history)} iteration(s) reached the cap {self.cap}"))
        if len(self.history) >= 2:
            before = self.history[-2]
            if before.head == last.head and before.finding_set_sha256 == last.finding_set_sha256:
                items.append((NO_PROGRESS, "same head and same finding set as the previous iteration"))
        if items:
            raise _Halt(items)
        if last.verdict == "FINDINGS":
            if self.fixer is None:
                _halt(NO_FIXER, "findings are open and no fixer was given")
            self._fix(last)
        # PARTIAL and BLOCKED iterations carry nothing to fix: the same head is reviewed again.

    def _gate_halt(self, verdict: str, codes: Sequence[str]) -> None:
        code = {GATE_REFUSED_VERDICT: GATE_REFUSED, GATE_BLOCKED_VERDICT: GATE_BLOCKED}.get(verdict, GATE_NOT_ACCEPTED)
        _halt(code, ", ".join(codes[:5]))

    def _fix(self, last: IterationSummary) -> None:
        self._guard()
        stored = self._stored_gate(last.iteration_index)
        if stored is not None:
            # a crash after the gate record: adopt the stored decision, never run the fixer again
            verdict, facts = stored
            if facts["base_head"] != last.head:
                _halt(RESUME_MISMATCH, "the recorded gate was made for another base head")
            self.gates.append({"gate_id": gate_id_for(self.attempt_no, last.iteration_index), "verdict": verdict,
                               "candidate_head": facts["candidate_head"], "replayed": True})
            if verdict != GATE_ACCEPTED:
                self._gate_halt(verdict, facts["reason_codes"])
            self.head = facts["candidate_head"]
            return
        context = FixContext(
            story_id=self.story_id, attempt_no=self.attempt_no, local_index=last.local_index,
            iteration_index=last.iteration_index, head=last.head, iteration_id=last.iteration_id,
            findings=last.findings, declared_coverage=self.declared, truncated=last.truncated)
        self.fixer_calls += 1
        try:
            candidate = self.fixer(context)
        except Exception as exc:  # noqa: BLE001
            raise _Halt([(FIXER_FAILED, _exc_text(exc))]) from exc
        if not isinstance(candidate, Candidate) or not isinstance(candidate.head, str) or not _HEAD40.match(candidate.head):
            _halt(FIXER_FAILED, "fixer must return a Candidate with a lowercase 40 hex head")
        if candidate.head == last.head:
            _halt(NO_PROGRESS, "the fixer returned the head it was given")
        try:
            verdict = self.gate(
                manifest_sha256=self.manifest_sha256, base_head=last.head, candidate_head=candidate.head,
                changed_paths=candidate.changed_paths, allowed_paths=self.allowed_paths,
                protected_paths=self.protected_paths, diff_bytes=candidate.diff_bytes,
                isolation=candidate.isolation, symlink_paths=candidate.symlink_paths,
                rename_pairs=candidate.rename_pairs)
        except Exception as exc:  # noqa: BLE001
            raise _Halt([(GATE_FAILED, _exc_text(exc))]) from exc
        if not isinstance(verdict, WorkerGateVerdict):
            _halt(GATE_FAILED, "the gate did not return a WorkerGateVerdict")
        gate_id = gate_id_for(self.attempt_no, last.iteration_index)
        reason_codes = [c for c, _ in verdict.reasons]
        facts = {
            "schema": GATE_FACTS_SCHEMA, "base_head": last.head, "candidate_head": candidate.head,
            "diff_sha256": hashlib.sha256(candidate.diff_bytes).hexdigest()
            if isinstance(candidate.diff_bytes, bytes) else None,
            "verdict": verdict.verdict, "reason_codes": reason_codes}
        try:
            recorded = self.state.record_diff_gate(
                self.story_id, epoch=self.epoch, step_id=gate_step_id(self.attempt_no, last.iteration_index),
                gate_id=gate_id, attempt_no=self.attempt_no, gate=verdict, facts=facts)
        except StoreError as exc:
            self._store_halt(exc)
            return
        if recorded.replayed:
            _halt(RESUME_MISMATCH, "another loop recorded this gate step first")
        self.gates.append({"gate_id": gate_id, "verdict": verdict.verdict, "candidate_head": candidate.head,
                           "replayed": False})
        if verdict.verdict != GATE_ACCEPTED:
            self._gate_halt(verdict.verdict, reason_codes)
        self.head = candidate.head

    def _iterate(self) -> None:
        local = len(self.history) + 1
        index = self.first_index + local - 1
        previous = self.history[-1] if self.history else None
        self._check_deadline()
        self._guard()
        request = ReviewRequest(
            story_id=self.story_id, attempt_no=self.attempt_no, local_index=local, iteration_index=index,
            request_id=request_id_for(self.story_id, self.attempt_no), head=self.head,
            iteration_of=previous.iteration_id if previous else None, declared_coverage=self.declared,
            changed_paths_sha256=self.changed_paths_sha256, purpose="receipt")
        started = self._now()
        self.submit_calls += 1
        try:
            report = self.submit(request)
        except Exception as exc:  # noqa: BLE001 - any failure is BLOCKED, never a pass
            raise _Halt([(SUBMIT_FAILED, _exc_text(exc))]) from exc
        finished = self._now()
        try:
            judged = judge_report(
                report, request_id=request.request_id, head=self.head, declared=self.declared,
                seen_ids=[s.iteration_id for s in self.history], verify_report=self.verify_report,
                changed_paths_sha256=self.changed_paths_sha256)
        except ReportUnusable as exc:
            raise _Halt([(exc.code, exc.detail)]) from exc
        digest = finding_set_sha256(judged.findings)
        truncated = len(judged.findings) > MAX_SUMMARY_FINDINGS
        facts = _facts_for(judged, request, self.head, digest, truncated)
        step_id = review_step_id(self.attempt_no, index)
        try:
            recorded = self.state.record_review_iteration(
                self.story_id, epoch=self.epoch, step_id=step_id, attempt_no=self.attempt_no,
                iteration_index=index, iteration_of=index - 1 if index > 1 else None,
                findings_count=len(judged.findings), coverage_declared=list(self.declared),
                verdict=judged.verdict, facts=facts)
        except StoreError as exc:
            if getattr(exc, "kind", "") == "conflict":
                _halt(RESUME_MISMATCH, "another loop recorded this iteration with other facts")
            self._store_halt(exc)
            return
        if recorded.replayed:
            _halt(RESUME_MISMATCH, "another loop already recorded this iteration")
        summary = IterationSummary(
            local_index=local, iteration_index=index, step_id=step_id, iteration_id=judged.iteration_id,
            iteration_of=request.iteration_of, head=self.head, findings_count=len(judged.findings),
            findings=tuple(facts["findings"]), finding_set_sha256=digest,
            coverage=judged.covered, missing_coverage=judged.missing, verdict=judged.verdict,
            reasons=judged.reasons, truncated=truncated, replayed=False, started_at=started, finished_at=finished)
        self.history.append(summary)
        self.facts_paths = facts["changed_paths_sha256"]
        if self.on_iteration is not None:
            try:
                self.on_iteration(summary)
            except Exception as exc:  # noqa: BLE001
                raise _Halt([(CALLBACK_FAILED, _exc_text(exc))]) from exc

    # ------------------------------------------------------------- result
    def result(self, verdict: str, items: Sequence[tuple[str, str]]) -> ReviewLoopResult:
        cap_requested = self.iteration_cap if type(self.iteration_cap) is int else None
        given = self.changed_paths_sha256
        given = given if isinstance(given, str) and _SHA256.match(given) else None
        # with iterations the digest comes from their stored/recorded facts; it must equal the input
        digest = self.facts_paths if self.history else given
        if digest != given and self.history:
            items = [*items, (INTERNAL_ERROR, "stored changed_paths_sha256 differs from the loop input")]
            verdict = BLOCKED
            digest = given
        return ReviewLoopResult(
            verdict=verdict, reasons=tuple(items), iterations=tuple(self.history),
            story_id=self.story_id if isinstance(self.story_id, str) else None,
            attempt_no=self.attempt_no if type(self.attempt_no) is int else None,
            declared_coverage=self.declared, cap_requested=cap_requested, cap_effective=self.cap,
            cap_clamped=self.clamped, final_head=self.head, submit_calls=self.submit_calls,
            fixer_calls=self.fixer_calls, gates=tuple(self.gates),
            replayed=bool(self.history) and all(s.replayed for s in self.history)
            and self.submit_calls == 0 and self.fixer_calls == 0,
            changed_paths_sha256=digest)


def run_review_loop(
    state: PipelineState, story_id: str, *, epoch: int, attempt_no: int, initial_head: str,
    declared_coverage: Sequence[str], iteration_cap: int, changed_paths_sha256: str,
    submit: Callable[[ReviewRequest], Any], verify_report: Callable[[Any], Any], clock: Callable[[], float],
    fixer: Callable[[FixContext], Candidate] | None = None,
    gate: Callable[..., WorkerGateVerdict] = gate_worker_change,
    manifest_sha256: str | None = None, allowed_paths: Sequence[str] = (), protected_paths: Sequence[str] = (),
    max_total_seconds: float | None = None, resume: Sequence[Any] = (),
    on_iteration: Callable[[IterationSummary], None] | None = None,
) -> ReviewLoopResult:
    """Drive the loop for one worker attempt and return CLEAN or BLOCKED. Never raises for runtime conditions.

    `declared_coverage` is the required set of executor ids (strings matching the contract token pattern).
    `changed_paths_sha256` is the digest of the sorted reviewed paths (`uc.contracts.changed_paths_sha256`) the
    report must carry; the report purpose must be "receipt". `manifest_sha256` (64 hex, required with a fixer),
    `allowed_paths` and `protected_paths` are passed to the gate for every fixer candidate.
    A BaseException that is not an Exception (a simulated or real process death) propagates on purpose.
    """
    loop = _Loop(
        state=state, story_id=story_id, epoch=epoch, attempt_no=attempt_no, initial_head=initial_head,
        declared_coverage=declared_coverage, iteration_cap=iteration_cap,
        changed_paths_sha256=changed_paths_sha256, submit=submit,
        verify_report=verify_report, clock=clock, fixer=fixer, gate=gate, manifest_sha256=manifest_sha256,
        allowed_paths=allowed_paths, protected_paths=protected_paths, max_total_seconds=max_total_seconds,
        resume=resume, on_iteration=on_iteration)
    try:
        return loop.run()
    except _Halt as halt:
        return loop.result(BLOCKED, halt.items)
    except Exception as exc:  # noqa: BLE001 - fail closed on anything unexpected
        return loop.result(BLOCKED, [(INTERNAL_ERROR, _exc_text(exc))])
