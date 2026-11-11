"""U5-3: schema of the coding-pipeline extension of the state store (pipeline schema version 1).

The extension is additive. It lives in the same SQLite file as `tools/vst/store.py` (baseline
decision BD-1: the store is the state authority) but is versioned on its own through the table
`pl_schema_version`; the store's own `PRAGMA user_version` (SCHEMA_VERSION 7) is not changed, so
every existing table, trigger and API behaves as before. Version 0 means "no pl_ table exists".
The only way to reach version 1 is `pipeline_migration.migrate_pipeline`, which takes a rollback
point first. This module holds only constants and DDL; it opens no database.

Schema v1 is FROZEN: the DDL below uses literal enum lists (no value is computed at import time) and
`schema_sha256` over the pl_ entries of `sqlite_master` is stored in `pl_schema_version` and checked
against the DDL of this module at runtime (`expected_schema_sha256`). A dropped trigger or index or an
edited CHECK is therefore reported as a partial schema. Any change of the v1 DDL after release needs
pipeline schema version 2 and a migration.

Standard library only.
"""

from __future__ import annotations

import functools
import hashlib
import json
import sqlite3

PIPELINE_SCHEMA_VERSION = 1
PIPELINE_COMPONENT = "pipeline"
PIPELINE_PREFIX = "pl_"

STEP_KINDS = (
    "ATTEMPT_START", "ATTEMPT_FINISH", "PATCH_PROPOSAL", "DIFF_GATE",
    "REVIEW_ITERATION", "TEST_EVIDENCE", "RECEIPT_LINK", "STOP", "STOP_ACK",
)
ATTEMPT_STATES = ("STARTED", "SUCCEEDED", "FAILED", "STOPPED")
FINISH_STATES = ("SUCCEEDED", "FAILED")           # STOPPED is reachable only through the stop path
APPLY_VERDICTS = ("ACCEPTED", "REFUSED", "BLOCKED")  # U5-2 ApplyResult.verdict
GATE_VERDICTS = ("ACCEPTED", "REFUSED", "BLOCKED")   # U5-1 WorkerGateVerdict.verdict
PROOF_STATUSES = ("VERIFIED", "NOT_VERIFIED", "CALLER_ASSERTED", "FAILED")  # U5-1 isolation proof
REVIEW_VERDICTS = ("CLEAN", "FINDINGS", "PARTIAL", "BLOCKED")
TEST_STATUSES = ("BLOCKED", "FAIL", "INCONCLUSIVE", "NOT_RUN", "PASS")  # equals sorted(contracts.RESULT); a test pins it
SUBJECT_KINDS = ("WORKER_ATTEMPT", "PATCH_PROPOSAL", "DIFF_GATE", "REVIEW_ITERATION", "TEST_EVIDENCE")

PIPELINE_TABLES = (
    "pl_schema_version", "pl_steps", "pl_story_control", "pl_worker_attempts",
    "pl_patch_proposals", "pl_diff_gates", "pl_review_iterations", "pl_test_evidence",
    "pl_receipt_links",
)


def _append_only(table: str, noun: str) -> tuple[str, str]:
    message = f"{noun} are append-only"
    return (
        f"CREATE TRIGGER {table}_no_update BEFORE UPDATE ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END",
        f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END",
    )


def pipeline_schema_statements() -> tuple[str, ...]:
    """DDL of pipeline schema version 1, in dependency order (parents before children)."""
    return (
        """CREATE TABLE pl_schema_version (
            component TEXT PRIMARY KEY CHECK (component = 'pipeline'),
            version INT NOT NULL CHECK (version >= 1),
            schema_sha256 TEXT NOT NULL,
            applied_at REAL NOT NULL
        )""",
        *_append_only("pl_schema_version", "pipeline schema version rows"),
        # Idempotency ledger: one row per accepted step. Same (story_id, step_id) with the same
        # payload digest replays the stored result; a different digest is a conflict.
        """CREATE TABLE pl_steps (
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            step_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('ATTEMPT_START', 'ATTEMPT_FINISH', 'PATCH_PROPOSAL', 'DIFF_GATE',
                'REVIEW_ITERATION', 'TEST_EVIDENCE', 'RECEIPT_LINK', 'STOP', 'STOP_ACK')),
            epoch INT NOT NULL CHECK (epoch >= 1),
            payload_sha256 TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at REAL NOT NULL,
            PRIMARY KEY (story_id, step_id)
        )""",
        *_append_only("pl_steps", "pipeline steps"),
        # Stop marker: a row means the story is stopped. Written once, never changed.
        """CREATE TABLE pl_story_control (
            story_id TEXT PRIMARY KEY REFERENCES stories(story_id),
            stop_step_id TEXT NOT NULL,
            stop_epoch INT NOT NULL CHECK (stop_epoch >= 1),
            stop_reason TEXT NOT NULL,
            stopped_at REAL NOT NULL
        )""",
        *_append_only("pl_story_control", "story stop markers"),
        """CREATE TABLE pl_worker_attempts (
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            attempt_no INT NOT NULL CHECK (attempt_no >= 1),
            epoch INT NOT NULL CHECK (epoch >= 1),
            step_id TEXT NOT NULL,
            base_head TEXT NOT NULL,
            candidate_head TEXT,
            state TEXT NOT NULL CHECK (state IN ('STARTED', 'SUCCEEDED', 'FAILED', 'STOPPED')),
            finish_step_id TEXT,
            PRIMARY KEY (story_id, attempt_no),
            CHECK (state != 'SUCCEEDED' OR candidate_head IS NOT NULL)
        )""",
        "CREATE UNIQUE INDEX pl_one_started_attempt ON pl_worker_attempts(story_id) WHERE state = 'STARTED'",
        "CREATE TRIGGER pl_worker_attempts_no_delete BEFORE DELETE ON pl_worker_attempts "
        "BEGIN SELECT RAISE(ABORT, 'worker attempts are append-only'); END",
        "CREATE TRIGGER pl_worker_attempts_identity BEFORE UPDATE OF story_id, attempt_no, epoch, "
        "step_id, base_head ON pl_worker_attempts "
        "BEGIN SELECT RAISE(ABORT, 'worker attempts are append-only: identity is immutable'); END",
        "CREATE TRIGGER pl_worker_attempts_closed BEFORE UPDATE ON pl_worker_attempts "
        "WHEN OLD.state != 'STARTED' "
        "BEGIN SELECT RAISE(ABORT, 'worker attempts are append-only: a closed attempt cannot change'); END",
        """CREATE TABLE pl_patch_proposals (
            story_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            attempt_no INT NOT NULL,
            epoch INT NOT NULL CHECK (epoch >= 1),
            step_id TEXT NOT NULL,
            base_head TEXT NOT NULL,
            proposal_document_sha256 TEXT,
            candidate_head TEXT,
            verdict TEXT NOT NULL CHECK (verdict IN ('ACCEPTED', 'REFUSED', 'BLOCKED')),
            stage TEXT NOT NULL,
            attempted_hunks INT NOT NULL CHECK (attempted_hunks >= 0),
            applied_hunks INT NOT NULL CHECK (applied_hunks >= 0),
            proposal_lines INT NOT NULL CHECK (proposal_lines >= 0),
            model_lines INT NOT NULL CHECK (model_lines >= 0),
            run_record TEXT NOT NULL,
            PRIMARY KEY (story_id, proposal_id),
            CHECK (applied_hunks <= attempted_hunks),
            CHECK (verdict = 'ACCEPTED' OR applied_hunks = 0),
            FOREIGN KEY (story_id, attempt_no) REFERENCES pl_worker_attempts(story_id, attempt_no)
        )""",
        *_append_only("pl_patch_proposals", "patch proposals"),
        """CREATE TABLE pl_diff_gates (
            story_id TEXT NOT NULL,
            gate_id TEXT NOT NULL,
            attempt_no INT NOT NULL,
            proposal_id TEXT,
            epoch INT NOT NULL CHECK (epoch >= 1),
            step_id TEXT NOT NULL,
            verdict TEXT NOT NULL CHECK (verdict IN ('ACCEPTED', 'REFUSED', 'BLOCKED')),
            reasons TEXT NOT NULL,
            isolation_proof TEXT,
            proof_statuses TEXT NOT NULL,
            PRIMARY KEY (story_id, gate_id),
            CHECK (verdict != 'ACCEPTED' OR isolation_proof IS NOT NULL),
            FOREIGN KEY (story_id, attempt_no) REFERENCES pl_worker_attempts(story_id, attempt_no),
            FOREIGN KEY (story_id, proposal_id) REFERENCES pl_patch_proposals(story_id, proposal_id)
        )""",
        *_append_only("pl_diff_gates", "diff gate results"),
        """CREATE TABLE pl_review_iterations (
            story_id TEXT NOT NULL,
            iteration_index INT NOT NULL CHECK (iteration_index >= 1),
            iteration_of INT,
            attempt_no INT NOT NULL,
            epoch INT NOT NULL CHECK (epoch >= 1),
            step_id TEXT NOT NULL,
            findings_count INT NOT NULL CHECK (findings_count >= 0),
            coverage_declared TEXT NOT NULL,
            verdict TEXT NOT NULL CHECK (verdict IN ('CLEAN', 'FINDINGS', 'PARTIAL', 'BLOCKED')),
            PRIMARY KEY (story_id, iteration_index),
            CHECK (iteration_of IS NULL OR iteration_of < iteration_index),
            CHECK (iteration_of IS NOT NULL OR iteration_index = 1),
            CHECK (verdict != 'CLEAN' OR findings_count = 0),
            FOREIGN KEY (story_id, attempt_no) REFERENCES pl_worker_attempts(story_id, attempt_no),
            FOREIGN KEY (story_id, iteration_of) REFERENCES pl_review_iterations(story_id, iteration_index)
        )""",
        *_append_only("pl_review_iterations", "review iterations"),
        """CREATE TABLE pl_test_evidence (
            story_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            attempt_no INT NOT NULL,
            test_id TEXT NOT NULL,
            epoch INT NOT NULL CHECK (epoch >= 1),
            step_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('BLOCKED', 'FAIL', 'INCONCLUSIVE', 'NOT_RUN', 'PASS')),
            evidence_sha256 TEXT,
            reason TEXT,
            PRIMARY KEY (story_id, evidence_id),
            UNIQUE (story_id, attempt_no, test_id),
            CHECK (status NOT IN ('PASS', 'FAIL') OR evidence_sha256 IS NOT NULL),
            CHECK (status IN ('PASS', 'FAIL') OR reason IS NOT NULL),
            FOREIGN KEY (story_id, attempt_no) REFERENCES pl_worker_attempts(story_id, attempt_no)
        )""",
        *_append_only("pl_test_evidence", "test evidence rows"),
        """CREATE TABLE pl_receipt_links (
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            receipt_id TEXT NOT NULL REFERENCES receipts(receipt_id),
            subject_kind TEXT NOT NULL CHECK (subject_kind IN ('WORKER_ATTEMPT', 'PATCH_PROPOSAL', 'DIFF_GATE', 'REVIEW_ITERATION', 'TEST_EVIDENCE')),
            subject_key TEXT NOT NULL,
            epoch INT NOT NULL CHECK (epoch >= 1),
            step_id TEXT NOT NULL,
            PRIMARY KEY (story_id, receipt_id, subject_kind, subject_key)
        )""",
        *_append_only("pl_receipt_links", "receipt links"),
    )


def schema_sha256(conn: sqlite3.Connection) -> str:
    """sha256 over the pl_ entries of sqlite_master (type, name, table, sql), sorted by type and name."""
    entries = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master WHERE sql IS NOT NULL "
        "AND (substr(name, 1, 3) = 'pl_' OR substr(tbl_name, 1, 3) = 'pl_') ORDER BY type, name"
    ).fetchall()
    data = json.dumps([list(tuple(e)) for e in entries], separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@functools.lru_cache(maxsize=1)
def expected_schema_sha256() -> str:
    """The hash a correct v1 database has: the DDL of this module applied to an empty in-memory database.

    SQLite accepts foreign keys to tables that do not exist yet, so no store tables are needed.
    """
    conn = sqlite3.connect(":memory:")
    try:
        for statement in pipeline_schema_statements():
            conn.execute(statement)
        return schema_sha256(conn)
    finally:
        conn.close()
