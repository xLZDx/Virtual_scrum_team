"""U5-3: pipeline state in the store: story, worker attempt, patch proposal, diff gate, review
iterations, test evidence and receipt links, with epoch checks, idempotent steps and a stop path.

Rules (details in docs/sdlc/u5/PIPELINE_STATE.md):
- Every mutating call is a STEP: (story_id, step_id) plus the caller's epoch. In ONE store
  transaction the step (1) refuses an epoch that is not the story's current epoch (nothing is
  written), (2) looks the step up in `pl_steps`: the same id with the same payload digest returns the
  stored result and writes nothing (`StepResult.replayed` is True), the same id with another payload
  or kind raises StoreError(kind='conflict'), (3) refuses a stopped story (kind 'stopped') unless the
  step is the stop path, (4) applies its rows and (5) records the step. A crash before COMMIT leaves
  nothing; a retry after COMMIT replays.
- The epoch check comes first, so a stale caller is refused even when it only replays an old step.
  The epoch is not part of the payload digest: a new owner may replay a step of an older epoch.
- Stop path: `stop_story` writes one marker row, marks the open worker attempt STOPPED and is
  idempotent (a second stop returns the first one and writes nothing). After it only `acknowledge_stop`
  (a recorded stop acknowledgment), replays of already recorded steps, and reads are accepted.
- Receipts are not duplicated: `link_receipt` points at an existing row of the store's `receipts`
  table of the same story.
- Nothing here signs anything and nothing is a gate decision; the rows record what U5-1 (worker
  gate) and U5-2 (patch proposals) reported, after checking that the report is internally consistent.

Requires the pipeline schema (`pipeline_migration.migrate_pipeline`); without it the constructor
raises StoreError(kind='schema'). Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .contracts import ContractError, canonical_bytes
from .patch_proposals import RUN_RECORD_SCHEMA
from .pipeline_migration import pipeline_version
from .pipeline_schema import (
    APPLY_VERDICTS,
    FINISH_STATES,
    GATE_VERDICTS,
    PIPELINE_SCHEMA_VERSION,
    PROOF_STATUSES,
    REVIEW_VERDICTS,
    SUBJECT_KINDS,
    TEST_STATUSES,
)
from .store import MAX_COUNTER, Store, StoreError
from .worker_gate import proof_is_honest

MAX_JSON_BYTES = 256 * 1024
MAX_REASON_CHARS = 500
MAX_COVERAGE_ITEMS = 256

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class StepResult:
    step_id: str
    kind: str
    replayed: bool       # True: the step was already recorded; nothing was written by this call
    result: dict


# ------------------------------------------------------------------ argument checks
def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _ID.match(value):
        raise StoreError(f"{name}: must match [A-Za-z0-9][A-Za-z0-9._:-]{{0,127}}", kind="argument")
    return value


def _int(value: Any, name: str, minimum: int = 0, maximum: int = MAX_COUNTER) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise StoreError(f"{name}: must be an integer in [{minimum}, {maximum}]", kind="argument")
    return value


def _head(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _HEAD.match(value):
        raise StoreError(f"{name}: must be a lowercase 40 or 64 hex commit id", kind="argument")
    return value


def _sha(value: Any, name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not _SHA256.match(value):
        raise StoreError(f"{name}: must be 64 lowercase hex characters", kind="argument")
    return value


def _text(value: Any, name: str, limit: int = MAX_REASON_CHARS) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise StoreError(f"{name}: must be a non-empty string of at most {limit} characters", kind="argument")
    return value


def _enum(value: Any, name: str, allowed: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise StoreError(f"{name}: must be one of {list(allowed)}", kind="argument")
    return value


def _json(value: Any, name: str) -> str:
    try:
        text = canonical_bytes(value).decode("utf-8")
    except ContractError as exc:
        raise StoreError(f"{name}: not JSON serialisable: {exc}", kind="argument") from exc
    if len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise StoreError(f"{name}: larger than {MAX_JSON_BYTES} bytes", kind="argument")
    return text


def _integrity_kind(exc: sqlite3.IntegrityError) -> str:
    return "duplicate" if "UNIQUE" in str(exc) else "pipeline"


def _plain(value: Any) -> Any:
    """Normalise to what a JSON round trip returns (tuples become lists)."""
    return json.loads(canonical_bytes(value).decode("utf-8"))


class PipelineState:
    """Pipeline rows on top of a `Store`. All writes go through `Store._tx` (BEGIN IMMEDIATE)."""

    def __init__(self, store: Store) -> None:
        if not isinstance(store, Store):
            raise StoreError("store: must be a Store", kind="argument")
        self._store = store
        with store._read_tx() as conn:
            version = pipeline_version(conn)
        if version != PIPELINE_SCHEMA_VERSION:
            raise StoreError(
                f"pipeline schema version is {version}, expected {PIPELINE_SCHEMA_VERSION}; "
                "run pipeline_migration.migrate_pipeline first",
                kind="schema",
            )

    # -------------------------------------------------------------- step engine
    def _step(
        self, story_id: Any, epoch: Any, step_id: Any, kind: str, payload: Mapping[str, Any],
        apply: Callable[[sqlite3.Connection, bool], dict], *, allow_stopped: bool = False,
    ) -> StepResult:
        story_id = _id(story_id, "story_id")
        step_id = _id(step_id, "step_id")
        epoch = _int(epoch, "epoch", 1)
        digest = hashlib.sha256(_json({"kind": kind, "payload": dict(payload)}, "payload").encode("utf-8")).hexdigest()
        store = self._store
        with store._tx() as conn:
            story = store._story_row(conn, story_id)
            if int(story["epoch"]) != epoch:
                raise StoreError(
                    f"stale epoch {epoch} for story {story_id!r} (current {int(story['epoch'])})", kind="epoch"
                )
            row = conn.execute(
                "SELECT kind, payload_sha256, result FROM pl_steps WHERE story_id = ? AND step_id = ?",
                (story_id, step_id),
            ).fetchone()
            if row is not None:
                if row["kind"] != kind or row["payload_sha256"] != digest:
                    raise StoreError(
                        f"step {step_id!r} of story {story_id!r} was recorded with a different kind or payload",
                        kind="conflict",
                    )
                return StepResult(step_id, kind, True, json.loads(row["result"]))
            stopped = conn.execute(
                "SELECT 1 FROM pl_story_control WHERE story_id = ?", (story_id,)
            ).fetchone() is not None
            if stopped and not allow_stopped:
                raise StoreError(f"story {story_id!r} is stopped; only the stop acknowledgment is accepted", kind="stopped")
            result = _plain(apply(conn, stopped))
            conn.execute(
                "INSERT INTO pl_steps (story_id, step_id, kind, epoch, payload_sha256, result, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (story_id, step_id, kind, epoch, digest, _json(result, "result"), store._now()),
            )
            return StepResult(step_id, kind, False, result)

    @staticmethod
    def _attempt(conn: sqlite3.Connection, story_id: str, attempt_no: int) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM pl_worker_attempts WHERE story_id = ? AND attempt_no = ?", (story_id, attempt_no)
        ).fetchone()
        if row is None:
            raise StoreError(f"unknown worker attempt {attempt_no} of story {story_id!r}", kind="pipeline")
        if row["state"] == "STOPPED":
            raise StoreError(f"worker attempt {attempt_no} was stopped", kind="stopped")
        return row

    # -------------------------------------------------------------- worker attempts
    def start_worker_attempt(self, story_id: str, *, epoch: int, step_id: str, base_head: str) -> StepResult:
        """Open the next attempt (numbers are consecutive from 1; only one attempt may be open)."""
        base_head = _head(base_head, "base_head")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            open_row = conn.execute(
                "SELECT attempt_no FROM pl_worker_attempts WHERE story_id = ? AND state = 'STARTED'", (sid,)
            ).fetchone()
            if open_row is not None:
                raise StoreError(f"attempt {open_row['attempt_no']} is still open", kind="pipeline")
            last = conn.execute(
                "SELECT COALESCE(MAX(attempt_no), 0) FROM pl_worker_attempts WHERE story_id = ?", (sid,)
            ).fetchone()[0]
            number = int(last) + 1
            if number > MAX_COUNTER:
                raise StoreError("attempt counter exhausted", kind="pipeline")
            conn.execute(
                "INSERT INTO pl_worker_attempts (story_id, attempt_no, epoch, step_id, base_head, state) "
                "VALUES (?, ?, ?, ?, ?, 'STARTED')",
                (sid, number, epoch, step_id, base_head),
            )
            return {"attempt_no": number}

        return self._step(story_id, epoch, step_id, "ATTEMPT_START", {"base_head": base_head}, apply)

    def finish_worker_attempt(
        self, story_id: str, *, epoch: int, step_id: str, attempt_no: int, state: str,
        candidate_head: str | None = None,
    ) -> StepResult:
        """STARTED -> SUCCEEDED (candidate head required) or FAILED. A closed attempt never changes."""
        attempt_no = _int(attempt_no, "attempt_no", 1)
        state = _enum(state, "state", FINISH_STATES)
        candidate_head = _head(candidate_head, "candidate_head", optional=state != "SUCCEEDED")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            row = self._attempt(conn, sid, attempt_no)
            if row["state"] != "STARTED":
                raise StoreError(f"attempt {attempt_no} is already {row['state']}", kind="pipeline")
            conn.execute(
                "UPDATE pl_worker_attempts SET state = ?, candidate_head = ?, finish_step_id = ? "
                "WHERE story_id = ? AND attempt_no = ?",
                (state, candidate_head, step_id, sid, attempt_no),
            )
            return {"attempt_no": attempt_no, "state": state}

        return self._step(
            story_id, epoch, step_id, "ATTEMPT_FINISH",
            {"attempt_no": attempt_no, "state": state, "candidate_head": candidate_head}, apply,
        )

    # -------------------------------------------------------------- patch proposal
    def record_patch_proposal(
        self, story_id: str, *, epoch: int, step_id: str, attempt_no: int, proposal_id: str,
        base_head: str, run_record: Mapping[str, Any],
    ) -> StepResult:
        """Record one U5-2 run record (`patch_proposals.build_run_record` output).

        Derived columns: verdict, stage, candidate_head, proposal_document_sha256 (the run record's
        report_sha256), attempted_hunks (hunks of the built diff), applied_hunks (the same count when the
        record says applied, else 0), proposal_lines and model_lines. Inconsistent records are refused.
        """
        attempt_no = _int(attempt_no, "attempt_no", 1)
        proposal_id = _id(proposal_id, "proposal_id")
        base_head = _head(base_head, "base_head")
        record, attempted_hunks, applied_hunks = self._check_run_record(run_record)
        record_json = _json(record, "run_record")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            self._attempt(conn, sid, attempt_no)
            conn.execute(
                "INSERT INTO pl_patch_proposals (story_id, proposal_id, attempt_no, epoch, step_id, base_head, "
                "proposal_document_sha256, candidate_head, verdict, stage, attempted_hunks, applied_hunks, "
                "proposal_lines, model_lines, run_record) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, proposal_id, attempt_no, epoch, step_id, base_head, record["report_sha256"],
                 record["candidate_head"], record["verdict"], record["stage"], attempted_hunks,
                 applied_hunks, record["proposal_lines"], record["model_lines"], record_json),
            )
            return {"proposal_id": proposal_id, "verdict": record["verdict"], "applied_hunks": applied_hunks}

        return self._step(
            story_id, epoch, step_id, "PATCH_PROPOSAL",
            {"attempt_no": attempt_no, "proposal_id": proposal_id, "base_head": base_head, "run_record": record},
            apply,
        )

    @staticmethod
    def _check_run_record(run_record: Any) -> tuple[dict, int, int]:
        if not isinstance(run_record, Mapping) or run_record.get("schema") != RUN_RECORD_SCHEMA:
            raise StoreError(f"run_record: schema must be {RUN_RECORD_SCHEMA!r}", kind="argument")
        record = dict(run_record)
        verdict = _enum(record.get("verdict"), "run_record.verdict", APPLY_VERDICTS)
        _text(record.get("stage"), "run_record.stage", 100)
        record["report_sha256"] = _sha(record.get("report_sha256"), "run_record.report_sha256", optional=True)
        record["candidate_head"] = _head(record.get("candidate_head"), "run_record.candidate_head", optional=True)
        if type(record.get("applied")) is not bool:
            raise StoreError("run_record.applied: must be a boolean", kind="argument")
        for name in ("proposal_lines", "model_lines", "attempted_proposal_lines"):
            _int(record.get(name), f"run_record.{name}", 0)
        hunks = record.get("attempted_proposal_hunks")
        if not isinstance(hunks, Mapping) or any(not isinstance(rows, list) for rows in hunks.values()):
            raise StoreError("run_record.attempted_proposal_hunks: must map paths to lists", kind="argument")
        attempted = sum(len(rows) for rows in hunks.values())
        applied = attempted if record["applied"] else 0
        if record["applied"] and verdict != "ACCEPTED":
            raise StoreError("run_record: applied is true but the verdict is not ACCEPTED", kind="argument")
        if verdict == "ACCEPTED" and (record["report_sha256"] is None or record["candidate_head"] is None):
            raise StoreError("run_record: an ACCEPTED record needs report_sha256 and candidate_head", kind="argument")
        if not record["applied"] and record["proposal_lines"] != 0:
            raise StoreError("run_record: proposal lines are counted only for applied proposals", kind="argument")
        return record, attempted, applied

    # -------------------------------------------------------------- diff gate
    def record_diff_gate(
        self, story_id: str, *, epoch: int, step_id: str, gate_id: str, attempt_no: int,
        gate: Any, proposal_id: str | None = None,
    ) -> StepResult:
        """Record one U5-1 `WorkerGateVerdict` (object with `to_dict()` or the dict itself).

        ACCEPTED needs an isolation proof that `worker_gate.proof_is_honest` accepts and that has no
        FAILED entry; REFUSED and BLOCKED need at least one reason. Proof statuses are stored as given
        (VERIFIED, NOT_VERIFIED, CALLER_ASSERTED, FAILED); nothing is promoted.
        """
        attempt_no = _int(attempt_no, "attempt_no", 1)
        gate_id = _id(gate_id, "gate_id")
        if proposal_id is not None:
            proposal_id = _id(proposal_id, "proposal_id")
        doc = gate.to_dict() if hasattr(gate, "to_dict") else gate
        if not isinstance(doc, Mapping):
            raise StoreError("gate: must be a WorkerGateVerdict or its dict", kind="argument")
        verdict = _enum(doc.get("verdict"), "gate.verdict", GATE_VERDICTS)
        reasons = doc.get("reasons")
        if not isinstance(reasons, (list, tuple)):
            raise StoreError("gate.reasons: must be a list", kind="argument")
        clean_reasons = []
        for item in reasons:
            if isinstance(item, Mapping):
                code, detail = item.get("code"), item.get("detail")
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                code, detail = item
            else:
                raise StoreError("gate.reasons: items must be {code, detail} or (code, detail)", kind="argument")
            if not isinstance(code, str) or not code or not isinstance(detail, str):
                raise StoreError("gate.reasons: code and detail must be strings", kind="argument")
            clean_reasons.append({"code": code, "detail": detail})
        if verdict != "ACCEPTED" and not clean_reasons:
            raise StoreError("gate: a REFUSED or BLOCKED verdict needs a reason", kind="argument")
        proof = doc.get("isolation_proof")
        statuses: dict[str, str] = {}
        if proof is not None:
            if not isinstance(proof, Mapping) or not isinstance(proof.get("properties"), list):
                raise StoreError("gate.isolation_proof: malformed", kind="argument")
            for item in proof["properties"]:
                if not isinstance(item, Mapping) or not isinstance(item.get("property"), str):
                    raise StoreError("gate.isolation_proof: malformed property", kind="argument")
                statuses[item["property"]] = _enum(item.get("status"), "isolation proof status", PROOF_STATUSES)
            if len(statuses) != len(proof["properties"]):
                raise StoreError("gate.isolation_proof: duplicate property", kind="argument")
        if verdict == "ACCEPTED":
            if proof is None or not proof_is_honest(proof) or "FAILED" in statuses.values():
                raise StoreError("gate: ACCEPTED needs an honest isolation proof without FAILED entries", kind="argument")
        proof_json = None if proof is None else _json(proof, "isolation_proof")
        reasons_json = _json(clean_reasons, "reasons")
        statuses_json = _json(statuses, "proof_statuses")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            self._attempt(conn, sid, attempt_no)
            if proposal_id is not None:
                owner = conn.execute(
                    "SELECT attempt_no FROM pl_patch_proposals WHERE story_id = ? AND proposal_id = ?",
                    (sid, proposal_id),
                ).fetchone()
                if owner is None or int(owner["attempt_no"]) != attempt_no:
                    raise StoreError(f"proposal {proposal_id!r} is unknown or belongs to another attempt", kind="pipeline")
            conn.execute(
                "INSERT INTO pl_diff_gates (story_id, gate_id, attempt_no, proposal_id, epoch, step_id, verdict, "
                "reasons, isolation_proof, proof_statuses) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, gate_id, attempt_no, proposal_id, epoch, step_id, verdict, reasons_json, proof_json,
                 statuses_json),
            )
            return {"gate_id": gate_id, "verdict": verdict}

        return self._step(
            story_id, epoch, step_id, "DIFF_GATE",
            {"attempt_no": attempt_no, "gate_id": gate_id, "proposal_id": proposal_id,
             "verdict": verdict, "reasons": clean_reasons, "isolation_proof": proof},
            apply,
        )

    # -------------------------------------------------------------- review iterations
    def record_review_iteration(
        self, story_id: str, *, epoch: int, step_id: str, attempt_no: int, iteration_index: int,
        iteration_of: int | None, findings_count: int, coverage_declared: Any, verdict: str,
    ) -> StepResult:
        """Iterations are consecutive from 1; index 1 has iteration_of None, later ones name an earlier one.

        CLEAN needs zero findings and a non-empty declared coverage; FINDINGS needs at least one finding.
        """
        attempt_no = _int(attempt_no, "attempt_no", 1)
        iteration_index = _int(iteration_index, "iteration_index", 1)
        if iteration_of is not None:
            iteration_of = _int(iteration_of, "iteration_of", 1, iteration_index - 1 if iteration_index > 1 else 0)
        elif iteration_index != 1:
            raise StoreError("iteration_of: required for every iteration after the first", kind="argument")
        findings_count = _int(findings_count, "findings_count", 0)
        verdict = _enum(verdict, "verdict", REVIEW_VERDICTS)
        if (not isinstance(coverage_declared, (list, tuple)) or len(coverage_declared) > MAX_COVERAGE_ITEMS
                or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in coverage_declared)
                or len(set(coverage_declared)) != len(coverage_declared)):
            raise StoreError("coverage_declared: must be a list of unique non-empty strings", kind="argument")
        coverage = sorted(coverage_declared)
        if verdict == "CLEAN" and (findings_count != 0 or not coverage):
            raise StoreError("a CLEAN iteration needs zero findings and a declared coverage", kind="argument")
        if verdict == "FINDINGS" and findings_count < 1:
            raise StoreError("a FINDINGS iteration needs at least one finding", kind="argument")
        coverage_json = _json(coverage, "coverage_declared")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            self._attempt(conn, sid, attempt_no)
            last = int(conn.execute(
                "SELECT COALESCE(MAX(iteration_index), 0) FROM pl_review_iterations WHERE story_id = ?", (sid,)
            ).fetchone()[0])
            if iteration_index != last + 1:
                raise StoreError(f"iteration_index must be {last + 1} (consecutive)", kind="pipeline")
            conn.execute(
                "INSERT INTO pl_review_iterations (story_id, iteration_index, iteration_of, attempt_no, epoch, "
                "step_id, findings_count, coverage_declared, verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, iteration_index, iteration_of, attempt_no, epoch, step_id, findings_count, coverage_json, verdict),
            )
            return {"iteration_index": iteration_index, "verdict": verdict}

        return self._step(
            story_id, epoch, step_id, "REVIEW_ITERATION",
            {"attempt_no": attempt_no, "iteration_index": iteration_index, "iteration_of": iteration_of,
             "findings_count": findings_count, "coverage_declared": coverage, "verdict": verdict},
            apply,
        )

    # -------------------------------------------------------------- test evidence
    def record_test_evidence(
        self, story_id: str, *, epoch: int, step_id: str, attempt_no: int, evidence_id: str, test_id: str,
        status: str, evidence_sha256: str | None = None, reason: str | None = None,
    ) -> StepResult:
        """PASS and FAIL need an evidence digest; every other status (incl. NOT_RUN) needs a reason."""
        attempt_no = _int(attempt_no, "attempt_no", 1)
        evidence_id = _id(evidence_id, "evidence_id")
        test_id = _text(test_id, "test_id", 200)
        status = _enum(status, "status", TEST_STATUSES)
        evidence_sha256 = _sha(evidence_sha256, "evidence_sha256", optional=True)
        if status in ("PASS", "FAIL"):
            if evidence_sha256 is None:
                raise StoreError(f"status {status} needs evidence_sha256", kind="argument")
            if reason is not None:
                reason = _text(reason, "reason")
        else:
            reason = _text(reason, "reason")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            self._attempt(conn, sid, attempt_no)
            try:
                conn.execute(
                    "INSERT INTO pl_test_evidence (story_id, evidence_id, attempt_no, test_id, epoch, step_id, "
                    "status, evidence_sha256, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (sid, evidence_id, attempt_no, test_id, epoch, step_id, status, evidence_sha256, reason),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreError(f"test evidence rejected: {exc}", kind=_integrity_kind(exc)) from exc
            return {"evidence_id": evidence_id, "status": status}

        return self._step(
            story_id, epoch, step_id, "TEST_EVIDENCE",
            {"attempt_no": attempt_no, "evidence_id": evidence_id, "test_id": test_id, "status": status,
             "evidence_sha256": evidence_sha256, "reason": reason},
            apply,
        )

    # -------------------------------------------------------------- receipt links
    def link_receipt(
        self, story_id: str, *, epoch: int, step_id: str, receipt_id: str, subject_kind: str, subject_key: str,
    ) -> StepResult:
        """Point an existing receipt of this story at a pipeline row. The receipt is not copied."""
        receipt_id = _text(receipt_id, "receipt_id", 200)
        subject_kind = _enum(subject_kind, "subject_kind", SUBJECT_KINDS)
        subject_key = _id(subject_key, "subject_key")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            receipt = conn.execute("SELECT story_id FROM receipts WHERE receipt_id = ?", (receipt_id,)).fetchone()
            if receipt is None or receipt["story_id"] != sid:
                raise StoreError(f"receipt {receipt_id!r} does not exist in story {sid!r}", kind="receipt")
            lookup = {
                "WORKER_ATTEMPT": "SELECT 1 FROM pl_worker_attempts WHERE story_id = ? AND attempt_no = CAST(? AS INT)",
                "PATCH_PROPOSAL": "SELECT 1 FROM pl_patch_proposals WHERE story_id = ? AND proposal_id = ?",
                "DIFF_GATE": "SELECT 1 FROM pl_diff_gates WHERE story_id = ? AND gate_id = ?",
                "REVIEW_ITERATION": "SELECT 1 FROM pl_review_iterations WHERE story_id = ? AND iteration_index = CAST(? AS INT)",
                "TEST_EVIDENCE": "SELECT 1 FROM pl_test_evidence WHERE story_id = ? AND evidence_id = ?",
            }[subject_kind]
            if conn.execute(lookup, (sid, subject_key)).fetchone() is None:
                raise StoreError(f"{subject_kind} {subject_key!r} does not exist in story {sid!r}", kind="pipeline")
            try:
                conn.execute(
                    "INSERT INTO pl_receipt_links (story_id, receipt_id, subject_kind, subject_key, epoch, step_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (sid, receipt_id, subject_kind, subject_key, epoch, step_id),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreError(f"receipt link rejected: {exc}", kind=_integrity_kind(exc)) from exc
            return {"receipt_id": receipt_id, "subject_kind": subject_kind, "subject_key": subject_key}

        return self._step(
            story_id, epoch, step_id, "RECEIPT_LINK",
            {"receipt_id": receipt_id, "subject_kind": subject_kind, "subject_key": subject_key}, apply,
        )

    # -------------------------------------------------------------- stop path
    def stop_story(self, story_id: str, *, epoch: int, step_id: str, reason: str) -> StepResult:
        """Stop the story. The first call writes the marker and stops the open attempt; later calls are no-ops.

        A second stop with another step id returns the first stop's result and writes nothing (not even a
        step row), so repeating a stop can never fail or change anything.
        """
        reason = _text(reason, "reason")
        sid = story_id
        store = self._store

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            if stopped:
                first = conn.execute(
                    "SELECT stop_step_id, stop_epoch, stop_reason FROM pl_story_control WHERE story_id = ?", (sid,)
                ).fetchone()
                raise _AlreadyStopped({
                    "stopped": True, "stop_step_id": first["stop_step_id"], "stop_epoch": int(first["stop_epoch"]),
                    "already_stopped": True,
                })
            closed = conn.execute(
                "UPDATE pl_worker_attempts SET state = 'STOPPED', finish_step_id = ? "
                "WHERE story_id = ? AND state = 'STARTED'", (step_id, sid),
            ).rowcount
            conn.execute(
                "INSERT INTO pl_story_control (story_id, stop_step_id, stop_epoch, stop_reason, stopped_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (sid, step_id, epoch, reason, store._now()),
            )
            return {"stopped": True, "stop_step_id": step_id, "stop_epoch": epoch, "already_stopped": False,
                    "attempts_stopped": int(closed)}

        try:
            return self._step(story_id, epoch, step_id, "STOP", {"reason": reason}, apply, allow_stopped=True)
        except _AlreadyStopped as already:
            return StepResult(step_id, "STOP", True, already.result)

    def acknowledge_stop(self, story_id: str, *, epoch: int, step_id: str, actor: str) -> StepResult:
        """Record that `actor` saw the stop. Refused (kind 'pipeline') when the story is not stopped."""
        actor = _id(actor, "actor")
        sid = story_id

        def apply(conn: sqlite3.Connection, stopped: bool) -> dict:
            if not stopped:
                raise StoreError(f"story {sid!r} is not stopped", kind="pipeline")
            first = conn.execute("SELECT stop_step_id FROM pl_story_control WHERE story_id = ?", (sid,)).fetchone()
            return {"acknowledged_by": actor, "stop_step_id": first["stop_step_id"]}

        return self._step(story_id, epoch, step_id, "STOP_ACK", {"actor": actor}, apply, allow_stopped=True)

    # -------------------------------------------------------------- reads (accepted while stopped)
    def get_status(self, story_id: str) -> dict:
        story_id = _id(story_id, "story_id")
        store = self._store
        with store._read_tx() as conn:
            story = store._story_row(conn, story_id)
            stop = conn.execute("SELECT * FROM pl_story_control WHERE story_id = ?", (story_id,)).fetchone()
            counts = {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE story_id = ?", (story_id,)).fetchone()[0])
                for table in ("pl_steps", "pl_worker_attempts", "pl_patch_proposals", "pl_diff_gates",
                              "pl_review_iterations", "pl_test_evidence", "pl_receipt_links")
            }
            return {
                "story_id": story_id, "epoch": int(story["epoch"]), "stopped": stop is not None,
                "stop": None if stop is None else dict(stop), "counts": counts,
            }

    def get_step(self, story_id: str, step_id: str) -> dict | None:
        story_id, step_id = _id(story_id, "story_id"), _id(step_id, "step_id")
        with self._store._read_tx() as conn:
            row = conn.execute("SELECT * FROM pl_steps WHERE story_id = ? AND step_id = ?", (story_id, step_id)).fetchone()
            return None if row is None else dict(row, result=json.loads(row["result"]))

    def _list(self, table: str, order: str, story_id: str, json_columns: tuple[str, ...] = ()) -> list[dict]:
        story_id = _id(story_id, "story_id")
        with self._store._read_tx() as conn:
            self._store._story_row(conn, story_id)
            rows = conn.execute(f"SELECT * FROM {table} WHERE story_id = ? ORDER BY {order}", (story_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for column in json_columns:
                if item[column] is not None:
                    item[column] = json.loads(item[column])
            result.append(item)
        return result

    def list_worker_attempts(self, story_id: str) -> list[dict]:
        return self._list("pl_worker_attempts", "attempt_no", story_id)

    def list_patch_proposals(self, story_id: str) -> list[dict]:
        return self._list("pl_patch_proposals", "proposal_id", story_id, ("run_record",))

    def list_diff_gates(self, story_id: str) -> list[dict]:
        return self._list("pl_diff_gates", "gate_id", story_id, ("reasons", "isolation_proof", "proof_statuses"))

    def list_review_iterations(self, story_id: str) -> list[dict]:
        return self._list("pl_review_iterations", "iteration_index", story_id, ("coverage_declared",))

    def list_test_evidence(self, story_id: str) -> list[dict]:
        return self._list("pl_test_evidence", "attempt_no, evidence_id", story_id)

    def list_receipt_links(self, story_id: str) -> list[dict]:
        return self._list("pl_receipt_links", "receipt_id, subject_kind, subject_key", story_id)


class _AlreadyStopped(Exception):
    """Internal: unwinds the stop step's transaction without a write; carries the first stop's result."""

    def __init__(self, result: dict) -> None:
        super().__init__("already stopped")
        self.result = result
