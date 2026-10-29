"""SQLite state store: epochs, tasks, leases, slots, receipts, events, budget (BD-5, BD-6).

One connection per Store instance; autocommit mode (isolation_level=None) with
an explicit BEGIN IMMEDIATE around every mutating method. `_tx` always ends the
transaction with an explicit COMMIT or ROLLBACK; SQLite "busy"/"locked"
errors become the distinct StoreBusyError (a StoreError with kind 'busy').
journal_mode is WAL, foreign_keys and recursive_triggers are ON.

Schema versioning: PRAGMA user_version is SCHEMA_VERSION (6). A new file is
initialised inside one transaction; supported v3-v5 layouts are upgraded
additively, while un-versioned legacy tables and unknown versions are refused
with StoreError(kind='schema').
The database file (and its -wal/-shm files) get mode 0o600 on a best-effort
basis (os.chmod failures are ignored).

Keys and authority (all keys are bytes of length >= 32):
- event_key (constructor): HMAC key of the event chain.
- worker key: passed to append_receipt; verifies worker receipts.
- supervisor_key: passed to the supervisor methods, acquire_lease (needed to
  write the RETRY_EXHAUSTED marker), charge (needed to write the
  BUDGET_EXCEEDED marker) and append_supervisor_receipt. Receipts in
  SUPERVISOR_SLOT are verified ONLY with it, so a receipt signed with the
  worker key cannot enter the supervisor chain. A supervisor_key equal to the
  event_key is refused (StoreError kind 'key') by every one of those methods.

Authority rules:
- Task link: register_task stores the validated manifest once per task_id
  (tasks table, append-only). It fixes story_id, manifest_sha256 and retry_cap.
  The same manifest may be registered again (idempotent); a different manifest
  for the same task_id is rejected. Every receipt must name the registered task,
  the registered story and the registered manifest_sha256.
- Epoch: stories.epoch is a fencing token. acquire_epoch is a compare-and-swap
  that only succeeds when no live owner holds the story. Every lease operation
  and every receipt append must carry the current epoch.
- Phase: set_phase is a compare-and-swap on the epoch by the live owner;
  get_phase reads it; render_state_md prints it.
- Leases are history: every acquisition INSERTs a row (lease_id, task_id,
  attempt, worker_id, epoch, expires_at, status, wrote, marked). Rows are never
  overwritten or deleted (triggers) and only status (LIVE -> closed), expires_at,
  wrote and marked change. At most one LIVE lease per task (partial unique
  index). Lease attempts per task are consecutive from 1. `wrote` is set when
  the lease holder appended a receipt, so a lease that never wrote one is the
  only kind that gets a WORKER_LOST marker. `receipt_count` counts the
  receipts written under the lease; a lease that wrote at least one receipt
  and then EXPIRED records a LEASE_EXPIRED_PARTIAL event (with the count) in
  addition to LEASE_EXPIRED, and still gets no WORKER_LOST marker.
- Receipts: append_receipt verifies the worker signature, the manifest hash,
  the task/story link, the slot (must be a declared slot of the receipt type),
  result == derive_result, epoch == current epoch, a live unexpired lease held
  by runner_id at the same epoch, the per-epoch slot bound (at most
  retry_cap + 1 NON-PASS receipts of the slot in the CURRENT epoch) and the chain
  position (attempt = previous + 1, prev_receipt_sha256 = previous hash), and
  that the budget is not exceeded (spent <= cap and no BUDGET_EXCEEDED event
  or marker; spending exactly the cap still lets the worker record results).
  Worker receipt ids must not start with the reserved prefix 'sup-' (kind
  'validation'; supervisor markers use it).
  Receipts for SUPERVISOR_SLOT are refused there: only append_supervisor_receipt
  and the supervisor methods write them (supervisor isolation: a worker lease
  never writes supervisor receipts and the supervisor path never writes worker
  slots). Supervisor markers are WORKER_LOST (INCONCLUSIVE),
  BUDGET_EXCEEDED and RETRY_EXHAUSTED (BLOCKED, terminal, one per task).
  After a terminal marker no lease and no worker receipt is accepted.
- Retry cap (what counts): retry_cap bounds WORKER-ATTRIBUTED failed attempts
  only. failed_attempts(task) = (the largest number of non-PASS results - FAIL,
  INCONCLUSIVE, NOT_RUN or BLOCKED - in any one worker slot) + (the number of
  EXPIRED or RELEASED leases that wrote no receipt). Fenced leases (epoch
  takeover) are NOT counted, with or without a receipt, so a supervisor
  takeover can never exhaust the cap (acquire_epoch reaps expired leases
  first, so a worker that really died is counted as EXPIRED). acquire_lease
  refuses when failed_attempts >= retry_cap + 1: the first refusal commits a
  signed RETRY_EXHAUSTED supervisor marker, then raises StoreError(kind=
  'retry'); repeated attempts do not add markers. Lease attempts stay
  consecutive per task (previous + 1) and receipt attempts stay consecutive per
  (task, slot) chain across epochs; append_receipt additionally refuses a slot
  receipt once the slot already holds retry_cap + 1 NON-PASS receipts in the
  current epoch (PASS receipts never count, so re-attesting at a new head is
  never refused), which bounds a worker that keeps writing receipts inside one epoch
  while a takeover after a full PASS set can still re-run every slot.
- Events and receipts are append-only (triggers). The event log is a hash
  chain keyed with HMAC: hash = HMAC(event_key, label + prev_hash + canonical
  row fields). A keyed anchor row in `meta` (count, head hash, HMAC) is
  updated with every event. BEFORE every event append the anchor is verified:
  its MAC, count == COUNT(*) of events and head == hash of the last event; any
  mismatch (or a missing anchor while events exist) raises StoreError(kind=
  'integrity') and nothing is recomputed or repaired, so a tampered log can
  never be re-sealed by the store. verify_event_chain detects editing,
  deleting or truncating events unless an attacker rolls back to an older
  consistent (events, anchor) pair; event_anchor() returns the verified
  (count, head) for anchoring outside the database. verify_event_chain,
  event_anchor and render_state_md read inside ONE explicit read transaction
  (BEGIN ... end), so a concurrent writer cannot make a consistent log look
  tampered.
- Budget: register_task seeds the budget row from the manifest cost_cap;
  set_budget can only lower it (a cap above the manifest cost_cap is refused,
  kind 'budget'). acquire_lease and append_receipt refuse only when spent > cap or a
  BUDGET_EXCEEDED event or marker exists (acquire_lease commits the signed
  marker first, kind 'budget'; append_receipt raises 'budget', or 'terminal'
  after the marker). Spending exactly the cap never blocks, and a cost_cap 0
  task with nothing spent may run. charge never lets spent exceed cap; when it
  would, it commits the BUDGET_EXCEEDED event and the supervisor marker itself
  (supervisor_key required) and then raises kind 'budget'. mark_budget_exceeded
  is idempotent (a single BUDGET_EXCEEDED marker per task).
- Callers may record only NOTE events; OPERATOR_ACTION is no longer a caller
  kind (operator decisions enter through signed waivers).
- Closed enums: EVENT_KINDS (also a CHECK constraint), LEASE_STATUSES,
  STORY_STATES. Integers are bounds-checked (epoch/attempt <= MAX_COUNTER,
  budget values <= MAX_BUDGET, slots <= MAX_SLOTS, ttl <= MAX_TTL_SEC).

Standard library only; no network.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import math
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from .contracts import (
    ContractError,
    SUPERVISOR_SLOT,
    canonical_bytes,
    derive_result,
    manifest_sha256,
    receipt_sha256,
    validate_receipt,
    validate_task_manifest,
)
from .signing import MIN_KEY_BYTES, OPERATOR_MANUAL_OVERRIDE_LABEL, RECEIPT_V2_LABEL, sign, verify
from .lifecycle import AnchorError, FileExternalAnchor, signed_checkpoint

SCHEMA_VERSION = 6
GENESIS_HASH = "0" * 64
DEFAULT_OWNER_TTL_SEC = 3600.0
SUPERVISOR_RUNNER_ID = "store-supervisor"

MAX_COUNTER = 2**31 - 1
MAX_BUDGET = 10**12
MAX_SLOTS = 1024
MAX_TTL_SEC = 366 * 24 * 3600
RUNNER_PRESPAWN_NO_EXECUTION_REASON = "PRESPAWN_REFUSAL"
RUNNER_PRESPAWN_REASON_CODES = frozenset({"RUNNER_PRESPAWN_FAILURE"})
RUNNER_AUTHORITY_COMPLETION_MARGIN_SEC = 5.0

LEASE_LIVE = "LIVE"
LEASE_RELEASED = "RELEASED"
LEASE_EXPIRED = "EXPIRED"
LEASE_FENCED = "FENCED"
LEASE_STATUSES = frozenset({LEASE_LIVE, LEASE_RELEASED, LEASE_EXPIRED, LEASE_FENCED})
STORY_STATES = frozenset({"OPEN", "OWNED"})

# Events written by the store itself, plus the one kind callers may record.
CALLER_EVENT_KINDS = frozenset({"NOTE"})
CONTROL_EVENT_KINDS = frozenset({
    "CONTROL_BREAKER_CONFIG", "CONTROL_PROVIDER_FAILURE", "CONTROL_PROVIDER_SUCCESS",
    "CONTROL_BREAKER_OVERRIDE", "CONTROL_ACTION_INTENT", "CONTROL_ACTION_COMPLETED",
    "CONTROL_ACTION_UNKNOWN", "CONTROL_ACTION_RECONCILED",
    "DISPATCH_OWNER_OUTCOME_PENDING", "DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED",
})
LIFECYCLE_ACTION_STATES = {
    "start": ("READY", "RUNNING"),
    "stop_terminate": ("RUNNING", "STOPPING"),
    "stop_cleanup": ("STOPPING", "STOPPED"),
    "rollback_effect": ("RUNNING", "ROLLING_BACK"),
    "rollback_cleanup": ("ROLLING_BACK", "STOPPED"),
    "resume": ("STOPPED", "READY"),
}
SUPERVISOR_ACTIONS = frozenset({"manual_override"})
ACTION_RESOLUTION_LABEL = b"vst-lifecycle-resolution-v1\0"
RUNNER_EXECUTION_RESOLUTION_LABEL = b"vst-runner-execution-resolution-v1\0"
RUNNER_EXECUTION_RESOLUTION_OUTCOMES = frozenset({
    "NO_EXECUTION_PROVEN", "EFFECTS_RESOLVED",
    "EFFECTS_UNRESOLVED", "RECONCILIATION_REJECTED",
})
RUNNER_EXECUTION_RESOLUTION_ATTESTATIONS = {
    "NO_EXECUTION_PROVEN": "operator-attests-no-child-launch-for-grant",
    "EFFECTS_RESOLVED": "operator-attests-all-effects-resolved-for-grant",
    "EFFECTS_UNRESOLVED": "operator-attests-effects-unresolved-for-grant",
    "RECONCILIATION_REJECTED": "operator-rejects-reconciliation-for-grant",
}
EVENT_KINDS = frozenset(
    {
        "EPOCH_ACQUIRED",
        "EPOCH_RENEWED",
        "EPOCH_RELEASED",
        "PHASE_SET",
        "TASK_REGISTERED",
        "LEASE_ACQUIRED",
        "DISPATCH_INTENT_ACCEPTED",
        "LEASE_RELEASED",
        "LEASE_EXPIRED",
        "LEASE_EXPIRED_PARTIAL",
        "LEASE_FENCED",
        "RECEIPT_APPENDED",
        "BUDGET_EXCEEDED",
        "BUDGET_BLOCKED",
    }
    | CALLER_EVENT_KINDS
)

# Supervisor marker -> the result its receipt must carry.
MARKER_RESULTS = {
    "WORKER_LOST": "INCONCLUSIVE",
    "BUDGET_EXCEEDED": "BLOCKED",
    "RETRY_EXHAUSTED": "BLOCKED",
}
TERMINAL_MARKERS = ("BUDGET_EXCEEDED", "RETRY_EXHAUSTED")
# Receipt ids starting with this prefix are reserved for supervisor markers.
SUPERVISOR_RECEIPT_PREFIX = "sup-"

_EVENT_LABEL = b"vst-event-v1\0"
_DISPATCH_CURSOR_LABEL = b"vst-dispatch-cursor-v1\0"
_ANCHOR_LABEL = b"vst-anchor-v1\0"
_ANCHOR_KEY = "events_anchor"


def _sql_list(values: Any) -> str:
    return ", ".join("'" + value + "'" for value in sorted(values))


def _runner_execution_schema_statements() -> tuple[str, ...]:
    """Append-only identities and lifecycle events for manifest-run claims."""
    return (
        """CREATE TABLE runner_execution_claims (
            grant_id TEXT PRIMARY KEY,
            invocation_id TEXT NOT NULL UNIQUE,
            request_id TEXT NOT NULL UNIQUE,
            task_id TEXT NOT NULL REFERENCES tasks(task_id),
            slot TEXT NOT NULL,
            runner_id TEXT NOT NULL,
            attempt INT NOT NULL CHECK (attempt >= 1),
            epoch INT NOT NULL CHECK (epoch >= 1),
            run_id TEXT NOT NULL REFERENCES supervisor_probes(run_id),
            service_generation TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            grant_body TEXT NOT NULL,
            claimed_at REAL NOT NULL,
            UNIQUE (task_id, slot, attempt)
        )""",
        """CREATE TABLE runner_execution_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_id TEXT NOT NULL REFERENCES runner_execution_claims(grant_id),
            state TEXT NOT NULL CHECK (state IN ('PENDING', 'EXECUTION_RESERVED', 'COMPLETE', 'INDETERMINATE', 'RECONCILED')),
            payload TEXT NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE (grant_id, state)
        )""",
        """CREATE TRIGGER runner_execution_claims_no_update BEFORE UPDATE ON runner_execution_claims
        BEGIN SELECT RAISE(ABORT, 'runner execution claims are append-only'); END""",
        """CREATE TRIGGER runner_execution_claims_no_delete BEFORE DELETE ON runner_execution_claims
        BEGIN SELECT RAISE(ABORT, 'runner execution claims are append-only'); END""",
        """CREATE TRIGGER runner_execution_events_no_update BEFORE UPDATE ON runner_execution_events
        BEGIN SELECT RAISE(ABORT, 'runner execution events are append-only'); END""",
        """CREATE TRIGGER runner_execution_events_no_delete BEFORE DELETE ON runner_execution_events
        BEGIN SELECT RAISE(ABORT, 'runner execution events are append-only'); END""",
    )


def _schema_statements() -> tuple[str, ...]:
    return (
        f"""CREATE TABLE stories (
            story_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            phase INT NOT NULL CHECK (phase BETWEEN 1 AND 10),
            epoch INT NOT NULL CHECK (epoch >= 1),
            owner TEXT,
            state TEXT NOT NULL CHECK (state IN ({_sql_list(STORY_STATES)})),
            owner_expires_at REAL
        )""",
        """CREATE TABLE tasks (
            task_id TEXT PRIMARY KEY,
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            manifest_sha256 TEXT NOT NULL,
            retry_cap INT NOT NULL CHECK (retry_cap >= 0),
            manifest TEXT NOT NULL
        )""",
        f"""CREATE TABLE leases (
            lease_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES tasks(task_id),
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            attempt INT NOT NULL CHECK (attempt >= 1),
            worker_id TEXT NOT NULL,
            epoch INT NOT NULL CHECK (epoch >= 1),
            expires_at REAL NOT NULL,
            status TEXT NOT NULL CHECK (status IN ({_sql_list(LEASE_STATUSES)})),
            wrote INT NOT NULL DEFAULT 0 CHECK (wrote IN (0, 1)),
            marked INT NOT NULL DEFAULT 0 CHECK (marked IN (0, 1)),
            receipt_count INT NOT NULL DEFAULT 0 CHECK (receipt_count >= 0),
            UNIQUE (task_id, attempt)
        )""",
        "CREATE UNIQUE INDEX one_live_lease ON leases(task_id) WHERE status = 'LIVE'",
        """CREATE TABLE slots (
            slot_no INTEGER PRIMARY KEY,
            lease_id INT REFERENCES leases(lease_id),
            expires_at REAL
        )""",
        """CREATE TABLE receipts (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id TEXT NOT NULL UNIQUE,
            story_id TEXT NOT NULL REFERENCES stories(story_id),
            task_id TEXT NOT NULL REFERENCES tasks(task_id),
            slot TEXT NOT NULL,
            attempt INT NOT NULL,
            epoch INT NOT NULL,
            receipt_sha256 TEXT NOT NULL,
            prev_receipt_sha256 TEXT,
            body TEXT NOT NULL,
            UNIQUE (task_id, slot, attempt)
        )""",
        f"""CREATE TABLE events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            task_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ({_sql_list(EVENT_KINDS)})),
            payload TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            hash TEXT NOT NULL
        )""",
        """CREATE TABLE budget (
            task_id TEXT PRIMARY KEY,
            cap INT NOT NULL CHECK (cap >= 0),
            spent INT NOT NULL DEFAULT 0 CHECK (spent >= 0)
        )""",
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        *_runner_execution_schema_statements(),
        """CREATE TABLE supervisor_operations (
            operation_key TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            result TEXT NOT NULL
        )""",
        """CREATE TRIGGER supervisor_operations_no_update BEFORE UPDATE ON supervisor_operations
        BEGIN SELECT RAISE(ABORT, 'supervisor operations are append-only'); END""",
        """CREATE TABLE supervisor_probes (
            run_id TEXT PRIMARY KEY,
            nonce TEXT NOT NULL UNIQUE,
            spec_sha256 TEXT NOT NULL,
            probe_sha256 TEXT NOT NULL
        )""",
        """CREATE TRIGGER supervisor_probes_no_update BEFORE UPDATE ON supervisor_probes
        BEGIN SELECT RAISE(ABORT, 'supervisor probes are append-only'); END""",
        """CREATE TRIGGER supervisor_probes_no_delete BEFORE DELETE ON supervisor_probes
        BEGIN SELECT RAISE(ABORT, 'supervisor probes are append-only'); END""",
        """CREATE TRIGGER supervisor_operations_no_delete BEFORE DELETE ON supervisor_operations
        BEGIN SELECT RAISE(ABORT, 'supervisor operations are append-only'); END""",
        """CREATE TRIGGER receipts_no_update BEFORE UPDATE ON receipts
        BEGIN SELECT RAISE(ABORT, 'receipts are append-only'); END""",
        """CREATE TRIGGER receipts_no_delete BEFORE DELETE ON receipts
        BEGIN SELECT RAISE(ABORT, 'receipts are append-only'); END""",
        """CREATE TRIGGER events_no_update BEFORE UPDATE ON events
        BEGIN SELECT RAISE(ABORT, 'events are append-only'); END""",
        """CREATE TRIGGER events_no_delete BEFORE DELETE ON events
        BEGIN SELECT RAISE(ABORT, 'events are append-only'); END""",
        """CREATE TRIGGER tasks_no_update BEFORE UPDATE ON tasks
        BEGIN SELECT RAISE(ABORT, 'tasks are append-only'); END""",
        """CREATE TRIGGER tasks_no_delete BEFORE DELETE ON tasks
        BEGIN SELECT RAISE(ABORT, 'tasks are append-only'); END""",
        """CREATE TRIGGER leases_no_delete BEFORE DELETE ON leases
        BEGIN SELECT RAISE(ABORT, 'leases are append-only'); END""",
        """CREATE TRIGGER leases_identity_immutable
        BEFORE UPDATE OF lease_id, task_id, story_id, attempt, worker_id, epoch ON leases
        BEGIN SELECT RAISE(ABORT, 'leases are append-only: identity is immutable'); END""",
        """CREATE TRIGGER leases_closed_stays_closed BEFORE UPDATE OF status ON leases
        WHEN OLD.status != 'LIVE'
        BEGIN SELECT RAISE(ABORT, 'leases are append-only: a closed lease cannot change'); END""",
    )


class StoreError(Exception):
    """Store rule violation. `kind` is a short machine-readable category.

    Kinds: story, epoch, lease, slot, chain, duplicate, budget, argument,
    task (unknown task), manifest (manifest hash/role mismatch or conflicting
    registration), signature (bad signature or inconsistent result), supervisor
    (supervisor/worker isolation or marker rules), retry (retry cap),
    terminal (a terminal marker blocks the task), key (supervisor_key equals
    the event_key), integrity (the event log or its anchor does not verify),
    schema, busy,
    append_only (an UPDATE/DELETE hit an append-only trigger).
    """

    def __init__(self, message: str, kind: str = "store") -> None:
        super().__init__(message)
        self.kind = kind


class StoreBusyError(StoreError):
    """SQLite reported the database as busy or locked; the call may be retried."""

    def __init__(self, message: str) -> None:
        super().__init__(message, kind="busy")


def _busy_error(exc: sqlite3.OperationalError) -> StoreBusyError | None:
    text = str(exc).lower()
    if "locked" in text or "busy" in text:
        return StoreBusyError(f"database busy: {exc}")
    return None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _need_int(value: Any, name: str, minimum: int, maximum: int = MAX_COUNTER) -> int:
    if not _is_int(value) or value < minimum or value > maximum:
        raise StoreError(
            f"{name}: must be an integer in [{minimum}, {maximum}]", kind="argument"
        )
    return value


def _need_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoreError(f"{name}: must be a non-empty string", kind="argument")
    return value


def _need_ttl(value: Any) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
        or value > MAX_TTL_SEC
    ):
        raise StoreError(
            f"ttl_sec: must be a finite number in (0, {MAX_TTL_SEC}]", kind="argument"
        )
    return float(value)


def _need_key(value: Any, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)) or len(value) < MIN_KEY_BYTES:
        raise StoreError(f"{name}: must be bytes of length >= {MIN_KEY_BYTES}", kind="argument")
    return bytes(value)


def _valid_action_resolution(event: dict, key: bytes | None) -> bool:
    record = event.get("resolution_record")
    if not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES or not isinstance(record, dict):
        return False
    expected_fields = {"action_id", "action", "attempt", "completed", "resolution_id", "evidence_sha256", "signature"}
    if set(record) != expected_fields:
        return False
    digest = record.get("evidence_sha256")
    if (not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        return False
    for name in ("action_id", "action", "attempt", "completed", "resolution_id"):
        if record.get(name) != event.get(name):
            return False
    if (type(record.get("completed")) is not bool or type(event.get("completed")) is not bool
            or not _is_int(record.get("attempt")) or not _is_int(event.get("attempt"))
            or not isinstance(record.get("resolution_id"), str)
            or not record.get("resolution_id").strip()):
        return False
    return verify(record, bytes(key), ACTION_RESOLUTION_LABEL)


def _valid_runner_execution_resolution(
    event: dict, claim: sqlite3.Row, key: bytes | None, predecessor_state: str,
) -> bool:
    record = event.get("resolution")
    if (not isinstance(key, (bytes, bytearray)) or len(key) < MIN_KEY_BYTES
            or not isinstance(record, dict)):
        return False
    expected_fields = {
        "version", "resolution_id", "outcome", "attestation", "evidence_sha256", "actor", "key_id",
        "grant_id", "grant_sha256", "request_id", "invocation_id", "task_id", "slot",
        "attempt", "epoch", "run_id", "service_generation", "predecessor_state", "signature",
    }
    if (set(record) != expected_fields or type(record.get("version")) is not int
            or record.get("version") != 1):
        return False
    if (not isinstance(record.get("resolution_id"), str)
            or not record["resolution_id"].strip() or len(record["resolution_id"]) > 128
            or record.get("actor") != "operator"
            or record.get("key_id") != hashlib.sha256(bytes(key)).hexdigest()
            or not isinstance(record.get("outcome"), str)
            or record.get("outcome") not in RUNNER_EXECUTION_RESOLUTION_OUTCOMES
            or record.get("attestation") != RUNNER_EXECUTION_RESOLUTION_ATTESTATIONS.get(record.get("outcome"))
            or record.get("predecessor_state") != predecessor_state):
        return False
    for name in ("evidence_sha256", "grant_sha256"):
        digest = record.get(name)
        if (not isinstance(digest, str) or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)):
            return False
    bindings = {
        "grant_id": "grant_id", "grant_sha256": "payload_sha256",
        "request_id": "request_id", "invocation_id": "invocation_id",
        "task_id": "task_id", "slot": "slot", "attempt": "attempt",
        "epoch": "epoch", "run_id": "run_id", "service_generation": "service_generation",
    }
    if any(record.get(record_name) != claim[claim_name]
           for record_name, claim_name in bindings.items()):
        return False
    for field in ("attempt", "epoch"):
        if not _is_int(record.get(field)):
            return False
    allowed_predecessors = {
        "NO_EXECUTION_PROVEN": {"PENDING"},
        "EFFECTS_RESOLVED": {"EXECUTION_RESERVED"},
        "EFFECTS_UNRESOLVED": {"PENDING", "EXECUTION_RESERVED"},
        "RECONCILIATION_REJECTED": {"PENDING", "EXECUTION_RESERVED"},
    }
    if (predecessor_state not in {"PENDING", "EXECUTION_RESERVED"}
            or predecessor_state not in allowed_predecessors[record["outcome"]]):
        return False
    if (event.get("event") != "RUNNER_EXECUTION_RECONCILED"
            or event.get("state") != "RECONCILED"
            or event.get("grant_id") != claim["grant_id"]
            or event.get("payload_sha256") != claim["payload_sha256"]
            or event.get("predecessor_state") != predecessor_state):
        return False
    return verify(record, bytes(key), RUNNER_EXECUTION_RESOLUTION_LABEL)


def _valid_runner_prespawn_no_execution_event(event: dict, claim: sqlite3.Row) -> bool:
    """Validate the terminal claim that proves no child reservation occurred."""
    reason = event.get("reason") if isinstance(event, dict) else None
    # Schema-v5 stores written before change 0473 can contain this exact recovery
    # event. A PENDING predecessor is conclusively pre-spawn because reservation
    # is durable before child creation. Keep accepting only the old closed shape;
    # the event remains bound to the claim ID/digest and authenticated by the
    # append-only supervisor history chain.
    legacy_recovery_fields = {
        "event", "state", "grant_id", "payload_sha256", "reason",
        "predecessor_state", "recovery_service_generation",
    }
    if (reason == "PREDECESSOR_GENERATION_STOPPED"
            and isinstance(event, dict) and set(event) == legacy_recovery_fields):
        recovery_generation = event.get("recovery_service_generation")
        return (
            event.get("event") == "RUNNER_EXECUTION_INDETERMINATE"
            and event.get("state") == "INDETERMINATE"
            and event.get("predecessor_state") == "PENDING"
            and isinstance(recovery_generation, str)
            and bool(recovery_generation)
            and recovery_generation != claim["service_generation"]
            and event.get("grant_id") == claim["grant_id"]
            and event.get("payload_sha256") == claim["payload_sha256"]
        )
    expected_fields = {
        "event", "state", "grant_id", "payload_sha256", "reason",
        "terminal_disposition", "predecessor_state", "request_id", "invocation_id",
        "task_id", "slot", "runner_id", "attempt", "epoch", "run_id",
        "service_generation",
    }
    if reason == RUNNER_PRESPAWN_NO_EXECUTION_REASON:
        expected_fields.add("reason_code")
    elif reason == "PREDECESSOR_GENERATION_STOPPED":
        expected_fields.add("recovery_service_generation")
    if (not isinstance(event, dict) or set(event) != expected_fields
            or event.get("event") != "RUNNER_EXECUTION_INDETERMINATE"
            or event.get("state") != "INDETERMINATE"
            or event.get("terminal_disposition") != "NO_EXECUTION"
            or (reason == RUNNER_PRESPAWN_NO_EXECUTION_REASON
                and event.get("reason_code") not in RUNNER_PRESPAWN_REASON_CODES)
            or (reason == "PREDECESSOR_GENERATION_STOPPED"
                and (not isinstance(event.get("recovery_service_generation"), str)
                     or event.get("recovery_service_generation") == claim["service_generation"]))
            or reason not in {RUNNER_PRESPAWN_NO_EXECUTION_REASON, "PREDECESSOR_GENERATION_STOPPED"}
            or event.get("predecessor_state") != "PENDING"):
        return False
    bindings = {
        "grant_id": "grant_id", "payload_sha256": "payload_sha256",
        "request_id": "request_id", "invocation_id": "invocation_id",
        "task_id": "task_id", "slot": "slot", "runner_id": "runner_id",
        "attempt": "attempt", "epoch": "epoch", "run_id": "run_id",
        "service_generation": "service_generation",
    }
    return all(event.get(event_name) == claim[claim_name]
               for event_name, claim_name in bindings.items())


def _valid_predecessor_generation_stopped_event(
    event: dict, claim: sqlite3.Row, predecessor_state: str,
) -> bool:
    """Validate a generation-stop event against its exact predecessor and claim."""
    legacy_fields = {
        "event", "state", "grant_id", "payload_sha256", "reason",
        "predecessor_state", "recovery_service_generation",
    }
    current_fields = legacy_fields | {
        "request_id", "invocation_id", "task_id", "slot", "runner_id",
        "attempt", "epoch", "run_id", "service_generation",
    }
    if predecessor_state not in {"PENDING", "EXECUTION_RESERVED"}:
        return False
    recovery_generation = event.get("recovery_service_generation") if isinstance(event, dict) else None
    if (not isinstance(event, dict)
            or event.get("event") != "RUNNER_EXECUTION_INDETERMINATE"
            or event.get("state") != "INDETERMINATE"
            or event.get("reason") != "PREDECESSOR_GENERATION_STOPPED"
            or event.get("predecessor_state") != predecessor_state
            or not isinstance(recovery_generation, str)
            or not recovery_generation
            or recovery_generation == claim["service_generation"]):
        return False
    if predecessor_state == "PENDING":
        return _valid_runner_prespawn_no_execution_event(event, claim)
    if event.get("terminal_disposition") is not None:
        return False
    fields = frozenset(event)
    if fields not in {frozenset(legacy_fields), frozenset(current_fields)}:
        return False
    if (event.get("grant_id") != claim["grant_id"]
            or event.get("payload_sha256") != claim["payload_sha256"]):
        return False
    if fields == frozenset(current_fields):
        bindings = {
            "request_id": "request_id", "invocation_id": "invocation_id",
            "task_id": "task_id", "slot": "slot", "runner_id": "runner_id",
            "attempt": "attempt", "epoch": "epoch", "run_id": "run_id",
            "service_generation": "service_generation",
        }
        return all(event.get(event_name) == claim[claim_name]
                   for event_name, claim_name in bindings.items())
    return True


def _iso(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _restrict_permissions(path: str) -> None:
    """Best effort: owner read/write only for the database and its WAL files."""
    if not path or path == ":memory:":
        return
    for suffix in ("", "-wal", "-shm"):
        try:
            os.chmod(path + suffix, 0o600)
        except OSError:
            pass


class Store:
    """SQLite-backed control-plane state. See module docstring."""

    def __init__(
        self,
        path: str,
        clock: Callable[[], float] = time.time,
        *,
        event_key: bytes,
        busy_timeout_sec: float = 30.0,
        anchor_path: str | None = None,
        sandbox_mode: bool = False,
        supervisor_key: bytes | None = None,
        execution_resolution_key: bytes | None = None,
        supervisor_runner_id: str = "store-startup-supervisor",
        allow_schema_upgrade: bool = False,
    ) -> None:
        self._event_key = _need_key(event_key, "event_key")
        if not isinstance(path, str) or not path:
            raise StoreError("path: must be a non-empty string", kind="argument")
        self._clock = clock
        self._path = path
        self.sandbox_mode = bool(sandbox_mode)
        if sandbox_mode and not anchor_path:
            raise StoreError("sandbox mode requires an external anchor path", kind="integrity")
        if sandbox_mode and supervisor_key is None:
            raise StoreError("sandbox mode requires a supervisor key for startup reconciliation", kind="key")
        self._startup_supervisor_key = None if supervisor_key is None else self._need_supervisor_key(supervisor_key)
        self._execution_resolution_key = (
            None if execution_resolution_key is None
            else _need_key(execution_resolution_key, "execution_resolution_key")
        )
        if (self._execution_resolution_key is not None
                and (self._execution_resolution_key == self._event_key
                     or self._execution_resolution_key == self._startup_supervisor_key)):
            raise StoreError("execution resolution key must be distinct from Store keys", kind="key")
        self._startup_supervisor_runner_id = _need_str(supervisor_runner_id, "supervisor_runner_id")
        if type(allow_schema_upgrade) is not bool:
            raise StoreError("allow_schema_upgrade must be a boolean", kind="argument")
        self._allow_schema_upgrade = allow_schema_upgrade
        self._external_anchor = (
            FileExternalAnchor(anchor_path, self._event_key) if anchor_path else None
        )
        if self._external_anchor is not None and os.path.realpath(self._external_anchor.path) == os.path.realpath(path):
            raise StoreError("external anchor must not be the database file", kind="integrity")
        self._reconciliation_complete = False
        self._integrity_locked = False
        self._integrity_lock_reason: str | None = None
        self._conn = sqlite3.connect(
            path, isolation_level=None, timeout=float(busy_timeout_sec)
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            synchronous = self._conn.execute("PRAGMA synchronous").fetchone()[0]
            if synchronous != 2:
                raise StoreError(
                    "Store connection did not retain PRAGMA synchronous=FULL", kind="integrity"
                )
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA recursive_triggers=ON")
            self._init_schema()
        except sqlite3.OperationalError as exc:
            self._conn.close()
            busy = _busy_error(exc)
            if busy is not None:
                raise busy from exc
            raise
        except AnchorError as exc:
            self._conn.close()
            raise StoreError(str(exc), kind="integrity") from exc
        except BaseException:
            self._conn.close()
            raise
        _restrict_permissions(path)
        try:
            self.startup_reconcile()
        except AnchorError as exc:
            # Lock acquisition failed before reconciliation could establish a
            # safe diagnostic state. Do not leak a live SQLite handle.
            self._conn.close()
            raise StoreError(str(exc), kind="integrity") from exc
        except StoreError as exc:
            # Keep the handle available for diagnostics, but all acceptance and
            # mutation entry points remain locked until explicit recovery.
            self._integrity_locked = True
            self._integrity_lock_reason = str(exc)

    def _init_schema(self) -> None:
        with self._tx() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version in (3, 4, 5) and not self._allow_schema_upgrade:
                raise StoreError(
                    f"schema version {version} requires an explicitly authorized upgrade to {SCHEMA_VERSION}",
                    kind="schema",
                )
            if version == 0:
                legacy = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'stories'"
                ).fetchone()
                if legacy is not None:
                    raise StoreError(
                        "database has tables but no schema version (legacy layout); "
                        "refusing to use it",
                        kind="schema",
                    )
                for statement in _schema_statements():
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            elif version == 3:
                # Additive migration only: historical event and receipt bytes,
                # hashes, sequence numbers and triggers are not rewritten.
                conn.execute(
                    "CREATE TABLE supervisor_operations ("
                    "operation_key TEXT PRIMARY KEY, operation TEXT NOT NULL, "
                    "payload_sha256 TEXT NOT NULL, result TEXT NOT NULL)"
                )
                conn.execute(
                    "CREATE TRIGGER supervisor_operations_no_update BEFORE UPDATE ON supervisor_operations "
                    "BEGIN SELECT RAISE(ABORT, 'supervisor operations are append-only'); END"
                )
                conn.execute(
                    "CREATE TRIGGER supervisor_operations_no_delete BEFORE DELETE ON supervisor_operations "
                    "BEGIN SELECT RAISE(ABORT, 'supervisor operations are append-only'); END"
                )
                conn.execute(
                    "CREATE TABLE supervisor_probes (run_id TEXT PRIMARY KEY, nonce TEXT NOT NULL UNIQUE, "
                    "spec_sha256 TEXT NOT NULL, probe_sha256 TEXT NOT NULL)"
                )
                conn.execute(
                    "CREATE TRIGGER supervisor_probes_no_update BEFORE UPDATE ON supervisor_probes "
                    "BEGIN SELECT RAISE(ABORT, 'supervisor probes are append-only'); END"
                )
                conn.execute(
                    "CREATE TRIGGER supervisor_probes_no_delete BEFORE DELETE ON supervisor_probes "
                    "BEGIN SELECT RAISE(ABORT, 'supervisor probes are append-only'); END"
                )
                for statement in _runner_execution_schema_statements():
                    conn.execute(statement)
            elif version == 4:
                # Add the one-invocation runner authorization ledger without
                # rewriting prior task, lease, receipt, or event history.
                for statement in _runner_execution_schema_statements():
                    conn.execute(statement)
            elif version not in (5, SCHEMA_VERSION):
                raise StoreError(
                    f"schema version {version} is not supported (expected {SCHEMA_VERSION})",
                    kind="schema",
                )
            if version in (3, 4, 5):
                self._migrate_events_v5_to_v6(conn)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _migrate_events_v5_to_v6(conn: sqlite3.Connection) -> None:
        """Extend the event-kind constraint without rewriting historical event bytes."""
        for trigger in ("events_no_update", "events_no_delete"):
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        conn.execute("ALTER TABLE events RENAME TO events_v5")
        conn.execute(
            "CREATE TABLE events ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, task_id TEXT NOT NULL, "
            "actor TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ("
            f"{_sql_list(EVENT_KINDS)})), payload TEXT NOT NULL, prev_hash TEXT NOT NULL, "
            "hash TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO events (seq, ts, task_id, actor, kind, payload, prev_hash, hash) "
            "SELECT seq, ts, task_id, actor, kind, payload, prev_hash, hash FROM events_v5 ORDER BY seq"
        )
        conn.execute("DROP TABLE events_v5")
        conn.execute(
            "CREATE TRIGGER events_no_update BEFORE UPDATE ON events "
            "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END"
        )
        conn.execute(
            "CREATE TRIGGER events_no_delete BEFORE DELETE ON events "
            "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END"
        )

    # ------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self._conn.close()
        _restrict_permissions(self._path)

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _rollback(self) -> None:
        if self._conn.in_transaction:
            try:
                self._conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        """Serialize anchored writes across SQLite commit and anchor synchronization."""
        if self._external_anchor is None:
            with self._tx_locked() as conn:
                yield conn
            return
        with self._external_anchor.transaction_lock():
            with self._tx_locked() as conn:
                yield conn

    @contextlib.contextmanager
    def _tx_locked(self) -> Iterator[sqlite3.Connection]:
        """BEGIN IMMEDIATE ... explicit COMMIT, or ROLLBACK on any exception."""
        try:
            if self._integrity_locked:
                detail = "" if not self._integrity_lock_reason else f": {self._integrity_lock_reason}"
                raise StoreError(f"store is integrity-locked pending startup reconciliation{detail}", kind="integrity")
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            busy = _busy_error(exc)
            if busy is not None:
                raise busy from exc
            raise
        try:
            yield self._conn
        except BaseException as exc:
            self._rollback()
            if isinstance(exc, sqlite3.IntegrityError) and "append-only" in str(exc):
                raise StoreError(
                    f"append-only violation: {exc}", kind="append_only"
                ) from exc
            if isinstance(exc, sqlite3.OperationalError):
                busy = _busy_error(exc)
                if busy is not None:
                    raise busy from exc
            raise
        try:
            self._conn.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            self._rollback()
            busy = _busy_error(exc)
            if busy is not None:
                raise busy from exc
            raise
        if self._external_anchor is not None and self._reconciliation_complete:
            try:
                self._sync_external_anchor()
            except StoreError as exc:
                self._integrity_locked = True
                self._integrity_lock_reason = str(exc)
                raise

    @contextlib.contextmanager
    def _read_tx(self) -> Iterator[sqlite3.Connection]:
        """Read under the external-anchor coordinator when anchoring is enabled."""
        if self._external_anchor is None:
            with self._read_tx_locked() as conn:
                yield conn
            return
        with self._external_anchor.transaction_lock():
            with self._read_tx_locked() as conn:
                yield conn

    @contextlib.contextmanager
    def _read_tx_locked(self) -> Iterator[sqlite3.Connection]:
        """One explicit read transaction (a consistent snapshot), always ended."""
        try:
            self._conn.execute("BEGIN")
        except sqlite3.OperationalError as exc:
            busy = _busy_error(exc)
            if busy is not None:
                raise busy from exc
            raise
        try:
            yield self._conn
        except sqlite3.OperationalError as exc:
            busy = _busy_error(exc)
            if busy is not None:
                raise busy from exc
            raise
        finally:
            self._rollback()  # read-only: ending the snapshot, nothing to commit

    def _now(self) -> float:
        return float(self._clock())

    def _need_supervisor_key(self, value: Any) -> bytes:
        key = _need_key(value, "supervisor_key")
        if hmac.compare_digest(key, self._event_key):
            raise StoreError("supervisor_key must differ from the event_key", kind="key")
        return key

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _story_row(conn: sqlite3.Connection, story_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM stories WHERE story_id = ?", (story_id,)
        ).fetchone()
        if row is None:
            raise StoreError(f"unknown story {story_id!r}", kind="story")
        return row

    @staticmethod
    def _task_row(conn: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise StoreError(f"unknown task {task_id!r} (register_task first)", kind="task")
        return row

    @staticmethod
    def _free_slot(conn: sqlite3.Connection, lease_id: int) -> None:
        conn.execute(
            "UPDATE slots SET lease_id = NULL, expires_at = NULL WHERE lease_id = ?",
            (lease_id,),
        )

    def _event_mac(self, prev_hash: str, fields: dict) -> str:
        message = _EVENT_LABEL + prev_hash.encode("utf-8") + canonical_bytes(fields)
        return hmac.new(self._event_key, message, hashlib.sha256).hexdigest()

    def _anchor_mac(self, count: int, head: str) -> str:
        message = _ANCHOR_LABEL + f"{count}:{head}".encode("utf-8")
        return hmac.new(self._event_key, message, hashlib.sha256).hexdigest()

    def _anchor_state(self, conn: sqlite3.Connection) -> tuple[int, str]:
        """Verify the keyed anchor against the events table; return (count, head).

        Checks the anchor MAC, count == COUNT(*) of events and head == hash of
        the last event (GENESIS_HASH and 0 for an empty log without anchor).
        Any mismatch raises StoreError(kind='integrity'); nothing is repaired.
        """
        rows = int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        last = conn.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        head = last["hash"] if last is not None else GENESIS_HASH
        anchor_row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_ANCHOR_KEY,)
        ).fetchone()
        if anchor_row is None:
            if rows != 0:
                raise StoreError("event anchor is missing but events exist", kind="integrity")
            return 0, GENESIS_HASH
        try:
            anchor = json.loads(anchor_row["value"])
            count, stored_head, mac = anchor["count"], anchor["head"], anchor["mac"]
        except (ValueError, KeyError, TypeError) as exc:
            raise StoreError("event anchor is malformed", kind="integrity") from exc
        if (
            not _is_int(count)
            or count < 0
            or not isinstance(stored_head, str)
            or not isinstance(mac, str)
        ):
            raise StoreError("event anchor is malformed", kind="integrity")
        expected = self._anchor_mac(count, stored_head)
        if not hmac.compare_digest(mac.encode("utf-8"), expected.encode("utf-8")):
            raise StoreError("event anchor MAC does not verify", kind="integrity")
        if count != rows:
            raise StoreError(
                f"event anchor count {count} differs from the {rows} stored events",
                kind="integrity",
            )
        if stored_head != head:
            raise StoreError(
                "event anchor head differs from the last stored event", kind="integrity"
            )
        return count, head

    def _record_event_locked(
        self, conn: sqlite3.Connection, task_id: str, actor: str, kind: str, payload: Any
    ) -> int:
        if kind not in EVENT_KINDS:
            raise StoreError(f"unknown event kind {kind!r}", kind="argument")
        count, prev_hash = self._anchor_state(conn)
        fields = {
            "ts": self._now(),
            "task_id": task_id,
            "actor": actor,
            "kind": kind,
            "payload": canonical_bytes(payload).decode("utf-8"),
        }
        new_hash = self._event_mac(prev_hash, fields)
        cursor = conn.execute(
            "INSERT INTO events (ts, task_id, actor, kind, payload, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                fields["ts"], task_id, actor, kind, fields["payload"],
                prev_hash, new_hash,
            ),
        )
        anchor = {
            "count": count + 1,
            "head": new_hash,
            "mac": self._anchor_mac(count + 1, new_hash),
        }
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_ANCHOR_KEY, json.dumps(anchor, sort_keys=True)),
        )
        return int(cursor.lastrowid)

    @staticmethod
    def _validate_dispatch_intent_event(payload: Any, *, task_id: str, actor: str) -> dict:
        required = {
            "principal", "task_id", "slot", "attempt", "epoch", "run_id",
            "request_id", "service_generation", "lease_id", "payload_digest",
            "manifest_digest", "instruction", "key_id",
        }
        delegated_fields = {"key_class", "key_fingerprint", "issuance_operation_key",
                            "issuance_envelope_sha256"}
        if (not isinstance(payload, dict) or frozenset(payload) not in {frozenset(required),
                                                                        frozenset(required | delegated_fields)}
                or payload.get("task_id") != task_id
                or payload.get("principal") != actor
                or not isinstance(actor, str) or not actor):
            raise StoreError("stored dispatch intent event binding is invalid", kind="integrity")
        for field in ("slot", "run_id", "service_generation"):
            if not isinstance(payload[field], str) or not payload[field].strip():
                raise StoreError("stored dispatch intent string field is invalid", kind="integrity")
        for field in ("attempt", "epoch", "lease_id"):
            if type(payload[field]) is not int or payload[field] < 1:
                raise StoreError("stored dispatch intent integer field is invalid", kind="integrity")
        request_id = payload["request_id"]
        if (not isinstance(request_id, str) or len(request_id) != 32
                or any(ch not in "0123456789abcdef" for ch in request_id)):
            raise StoreError("stored dispatch intent request id is invalid", kind="integrity")
        from .dispatch_instruction import validate_dispatch_instruction
        try:
            instruction = validate_dispatch_instruction(payload["instruction"])
        except ContractError as exc:
            raise StoreError("stored dispatch instruction envelope is invalid", kind="integrity") from exc
        if (instruction["key_id"] != payload["key_id"]
                or any(instruction[key] != payload[key] for key in (
                    "task_id", "slot", "attempt", "epoch", "run_id", "request_id",
                ))):
            raise StoreError("stored dispatch instruction does not match event fields", kind="integrity")
        caller = {"principal": payload["principal"], "service_generation": payload["service_generation"],
                  "key_id": payload["key_id"], "instruction": instruction}
        if "key_class" in payload:
            if (payload["key_class"] != "DELEGATED_V1"
                    or payload["issuance_envelope_sha256"] != hashlib.sha256(canonical_bytes(instruction)).hexdigest()
                    or not isinstance(payload["issuance_operation_key"], str)
                    or not isinstance(payload["key_fingerprint"], str)
                    or len(payload["key_fingerprint"]) != 64):
                raise StoreError("stored delegated dispatch binding is malformed", kind="integrity")
            caller.update({"key_class": payload["key_class"],
                           "key_fingerprint": payload["key_fingerprint"],
                           "issuance_operation_key": payload["issuance_operation_key"],
                           "issuance_envelope_sha256": payload["issuance_envelope_sha256"]})
        expected = hashlib.sha256(canonical_bytes(caller)).hexdigest()
        for field in ("payload_digest", "manifest_digest"):
            value = payload[field]
            if (not isinstance(value, str) or len(value) != 64
                    or any(ch not in "0123456789abcdef" for ch in value)):
                raise StoreError("stored dispatch intent digest is invalid", kind="integrity")
        if payload["payload_digest"] != expected:
            raise StoreError("stored dispatch intent canonical digest does not verify", kind="integrity")
        return payload

    def _bind_dispatch_key_class_locked(self, conn: sqlite3.Connection, *, key_id: str,
                                        key_class: str, purpose: str,
                                        fingerprint: str) -> None:
        from .dispatch_issuance import _SHA256, _ID
        if (not isinstance(key_id, str) or not _ID.fullmatch(key_id)
                or key_class not in {"LEGACY_V1", "DELEGATED_V1"}
                or purpose != "VST_S2_DISPATCH_INSTRUCTION_V1"
                or not isinstance(fingerprint, str) or not _SHA256.fullmatch(fingerprint)):
            raise StoreError("dispatch key class binding is invalid", kind="authorization")
        task_id = "dispatch-key-class:" + key_id
        rows = conn.execute(
            "SELECT actor, payload FROM events WHERE task_id=? AND kind='NOTE' ORDER BY seq", (task_id,),
        ).fetchall()
        if len(rows) > 1:
            raise StoreError("dispatch key class has multiple immutable bindings", kind="integrity")
        binding = {"event": "SUPERVISOR_DISPATCH_KEY_CLASS_BOUND", "key_id": key_id,
                   "key_class": key_class, "purpose": purpose,
                   "public_key_fingerprint": fingerprint}
        if rows:
            try:
                prior = json.loads(rows[0]["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch key class binding is malformed", kind="integrity") from exc
            if rows[0]["actor"] != "supervisor" or prior != binding:
                raise StoreError("dispatch key class cannot be changed", kind="integrity")
            return
        self._record_event_locked(conn, task_id, "supervisor", "NOTE", binding)

    def _require_dispatch_key_class_locked(self, conn: sqlite3.Connection, *, key_id: str,
                                           key_class: str, purpose: str,
                                           fingerprint: str) -> None:
        task_id = "dispatch-key-class:" + key_id
        rows = conn.execute(
            "SELECT actor, payload FROM events WHERE task_id=? AND kind='NOTE' ORDER BY seq", (task_id,),
        ).fetchall()
        expected = {"event": "SUPERVISOR_DISPATCH_KEY_CLASS_BOUND", "key_id": key_id,
                    "key_class": key_class, "purpose": purpose,
                    "public_key_fingerprint": fingerprint}
        if (len(rows) != 1 or rows[0]["actor"] != "supervisor"
                or json.loads(rows[0]["payload"]) != expected):
            raise StoreError("dispatch key class binding is absent or changed", kind="integrity")

    def dispatch_key_class_binding(self, key_id: str) -> dict | None:
        task_id = "dispatch-key-class:" + key_id
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            rows = conn.execute(
                "SELECT actor, payload FROM events WHERE task_id=? AND kind='NOTE' ORDER BY seq",
                (task_id,),
            ).fetchall()
            if not rows:
                return None
            if len(rows) != 1 or rows[0]["actor"] != "supervisor":
                raise StoreError("dispatch key class has invalid journal multiplicity", kind="integrity")
            try:
                value = json.loads(rows[0]["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch key class journal is malformed", kind="integrity") from exc
            if (not isinstance(value, dict) or value.get("event") != "SUPERVISOR_DISPATCH_KEY_CLASS_BOUND"
                    or value.get("key_id") != key_id):
                raise StoreError("dispatch key class journal identity is invalid", kind="integrity")
            return value

    def _validate_dispatch_current_locked(self, conn: sqlite3.Connection, *, principal: str,
                                          task_id: str, slot: str, attempt: int, epoch: int,
                                          run_id: str, now: float) -> tuple[sqlite3.Row, dict, sqlite3.Row]:
        task = self._task_row(conn, task_id)
        self._guard_runner_task_continuation_locked(conn, task_id)
        manifest = validate_task_manifest(json.loads(task["manifest"]))
        if manifest_sha256(manifest) != task["manifest_sha256"]:
            raise StoreError("registered manifest digest is inconsistent", kind="integrity")
        declared = {item["slot"]: item["receipt_type"] for item in manifest["required_receipts"]}
        if declared.get(slot) != "TestRun":
            raise StoreError("dispatch intent slot is not a manifest TestRun slot", kind="slot")
        story = self._story_row(conn, task["story_id"])
        if (story["state"] != "OWNED" or story["owner"] != principal
                or int(story["epoch"]) != epoch or story["owner_expires_at"] is None
                or float(story["owner_expires_at"]) <= now):
            raise StoreError("authenticated principal does not hold the live task owner epoch", kind="epoch")
        lease = conn.execute(
            "SELECT lease_id, epoch, status, expires_at FROM leases WHERE task_id=? AND attempt=?",
            (task_id, attempt),
        ).fetchone()
        if (lease is None or int(lease["epoch"]) != epoch or lease["status"] != LEASE_LIVE
                or float(lease["expires_at"]) <= now):
            raise StoreError("dispatch intent has no matching live lease", kind="lease")
        if not self.reconciliation_complete:
            raise StoreError("Store startup reconciliation is required for dispatch intent", kind="integrity")
        if conn.execute("SELECT 1 FROM supervisor_probes WHERE run_id=?", (run_id,)).fetchone() is None:
            raise StoreError("dispatch intent requires a consumed run-bound preflight", kind="probe")
        last = conn.execute(
            "SELECT attempt FROM receipts WHERE task_id=? AND slot=? ORDER BY attempt DESC LIMIT 1",
            (task_id, slot),
        ).fetchone()
        expected = 1 if last is None else int(last["attempt"]) + 1
        if (attempt != expected or not self._runner_receipt_gap_is_eligible_locked(
                conn, task_id, slot, expected - 1, attempt)):
            raise StoreError("dispatch intent attempt is not eligible for this receipt slot", kind="chain")
        if conn.execute(
            "SELECT 1 FROM receipts WHERE task_id=? AND slot=? AND attempt=?",
            (task_id, slot, attempt),
        ).fetchone() is not None:
            raise StoreError("dispatch intent attempt already has a receipt", kind="duplicate")
        blocked = self._budget_block_locked(conn, task_id)
        if blocked is not None:
            raise StoreError(blocked, kind="budget")
        return task, manifest, lease

    def _validate_dispatch_issuance_proof_locked(self, conn: sqlite3.Connection, *,
                                                proof: Any, instruction: dict,
                                                principal: str, service_generation: str) -> dict:
        from .root_dispatch_issuer import is_verified_issuance_context
        from .dispatch_issuance import canonical_sha256, validate_frozen_intent
        if not is_verified_issuance_context(proof):
            raise StoreError("delegated dispatch lacks a root-verified issuance context", kind="authorization")
        intent = validate_frozen_intent(proof.intent)
        handoff, policy = intent["handoff"], intent["policy"]
        if (proof.envelope != instruction
                or proof.fingerprint != intent["signer"]["public_key_fingerprint"]
                or intent["signer"]["key_class"] != "DELEGATED_V1"
                or intent["signer"]["purpose"] != "VST_S2_DISPATCH_INSTRUCTION_V1"
                or policy["owner_principal"] != principal
                or intent["service_generation"] != service_generation
                or any(instruction[name] != intent["unsigned"][name] for name in intent["unsigned"])):
            raise StoreError("delegated dispatch proof does not match exact current request", kind="authorization")
        operation = conn.execute(
            "SELECT operation_key, operation, payload_sha256, result FROM supervisor_operations WHERE operation_key=?",
            (intent["operation_key"],),
        ).fetchone()
        if operation is None:
            raise StoreError("delegated dispatch issuance row is missing", kind="integrity")
        events = self._dispatch_issuance_records_locked(conn, intent["operation_key"])
        self._verify_dispatch_issuance_structure(operation, events)
        if (events[-1].get("event") != "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED"
                or events[-1].get("envelope") != instruction
                or canonical_sha256(intent) != canonical_sha256(events[0]["intent"])):
            raise StoreError("delegated dispatch proof no longer matches durable issuance records", kind="integrity")
        self._require_dispatch_key_class_locked(
            conn, key_id=intent["signer"]["key_id"], key_class="DELEGATED_V1",
            purpose=intent["signer"]["purpose"], fingerprint=proof.fingerprint,
        )
        expected = {"task_id": handoff["task_id"], "slot": handoff["slot"],
                    "attempt": handoff["attempt"], "epoch": handoff["epoch"],
                    "run_id": handoff["run_id"]}
        if any(instruction[key] != value for key, value in expected.items()):
            raise StoreError("delegated dispatch tuple differs from its authenticated handoff", kind="authorization")
        return intent

    def accept_dispatch_intent(
        self, *, principal: str, instruction: dict, service_generation: str,
        key_class: str = "LEGACY_V1", key_fingerprint: str | None = None,
        issuance_proof: Any = None, authority_guard: Callable[[], bool] | None = None,
    ) -> dict:
        """Record only a signed-envelope intent already verified by root Supervisor."""
        from .dispatch_instruction import validate_dispatch_instruction
        instruction = validate_dispatch_instruction(instruction)
        task_id, slot = instruction["task_id"], instruction["slot"]
        attempt, epoch = instruction["attempt"], instruction["epoch"]
        run_id, request_id = instruction["run_id"], instruction["request_id"]
        for value, name in ((principal, "principal"), (task_id, "task_id"),
                            (slot, "slot"), (run_id, "run_id"),
                            (service_generation, "service_generation")):
            _need_str(value, name)
        _need_int(attempt, "attempt", 1)
        _need_int(epoch, "epoch", 1)
        if (not isinstance(request_id, str) or len(request_id) != 32
                or any(ch not in "0123456789abcdef" for ch in request_id)):
            raise StoreError("request_id must be 32 lowercase hexadecimal characters", kind="argument")
        caller_payload = {"principal": principal, "service_generation": service_generation,
                          "key_id": instruction["key_id"], "instruction": instruction}
        if key_class == "DELEGATED_V1":
            if issuance_proof is None:
                raise StoreError("delegated dispatch requires verified issuance provenance", kind="authorization")
            caller_payload.update({
                "key_class": "DELEGATED_V1", "key_fingerprint": key_fingerprint,
                "issuance_operation_key": issuance_proof.intent["operation_key"],
                "issuance_envelope_sha256": hashlib.sha256(canonical_bytes(instruction)).hexdigest(),
            })
        elif key_class != "LEGACY_V1":
            raise StoreError("dispatch key class is unknown", kind="authorization")
        payload_digest = hashlib.sha256(canonical_bytes(caller_payload)).hexdigest()
        operation_key = f"dispatch-intent:{request_id}"
        with self._tx() as conn:
            self._verify_control_history_locked(conn)
            self._verify_supervisor_records(conn)
            outcome_state, pending = self._dispatch_outcome_state_locked(conn)
            if outcome_state == "LEGACY_UNRESOLVED":
                raise StoreError(
                    "legacy dispatch history requires separately authorized reconciliation",
                    kind="integrity",
                )
            if outcome_state == "PENDING" and pending["request_id"] != request_id:
                raise StoreError(
                    "a prior dispatch outcome is still awaiting relay acknowledgement",
                    kind="lifecycle",
                )
            if key_class == "DELEGATED_V1":
                if authority_guard is None or authority_guard() is not True:
                    raise StoreError("delegated root policy/generation changed at admission write", kind="authorization")
                delegated_intent = self._validate_dispatch_issuance_proof_locked(
                    conn, proof=issuance_proof, instruction=instruction,
                    principal=principal, service_generation=service_generation,
                )
            else:
                delegated_intent = None
                if not isinstance(key_fingerprint, str):
                    raise StoreError("legacy dispatch key fingerprint is unavailable", kind="authorization")
                self._bind_dispatch_key_class_locked(
                    conn, key_id=instruction["key_id"], key_class=key_class,
                    purpose="VST_S2_DISPATCH_INSTRUCTION_V1", fingerprint=key_fingerprint,
                )
            prior = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations "
                "WHERE operation_key = ?", (operation_key,),
            ).fetchone()
            if prior is not None:
                if (prior["operation"] != "dispatch_intent"
                        or prior["payload_sha256"] != payload_digest):
                    raise StoreError("dispatch request id was reused with a different payload", kind="duplicate")
                try:
                    result = json.loads(prior["result"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("stored dispatch intent result is invalid", kind="integrity") from exc
                if not isinstance(result, dict) or result.get("service_generation") != service_generation:
                    raise StoreError("dispatch intent belongs to another service generation", kind="duplicate")
                if delegated_intent is not None:
                    self._validate_dispatch_current_locked(
                        conn, principal=principal, task_id=task_id, slot=slot,
                        attempt=attempt, epoch=epoch, run_id=run_id, now=self._now(),
                    )
                    if (result.get("issuance_operation_key") != delegated_intent["operation_key"]
                            or result.get("issuance_envelope_sha256") !=
                            hashlib.sha256(canonical_bytes(instruction)).hexdigest()):
                        raise StoreError("dispatch replay differs from its immutable issuance binding",
                                         kind="integrity")
                return result

            now = self._now()
            task, manifest, lease = self._validate_dispatch_current_locked(
                conn, principal=principal, task_id=task_id, slot=slot,
                attempt=attempt, epoch=epoch, run_id=run_id, now=now,
            )
            manifest_digest = manifest_sha256(manifest)
            event_payload = {
                **caller_payload, "task_id": task_id, "slot": slot, "attempt": attempt,
                "epoch": epoch, "run_id": run_id, "request_id": request_id,
                "lease_id": int(lease["lease_id"]),
                "payload_digest": payload_digest,
                "manifest_digest": manifest_digest,
            }
            event_seq = self._record_event_locked(
                conn, task_id, principal, "DISPATCH_INTENT_ACCEPTED", event_payload,
            )
            result = {"event_seq": event_seq, **event_payload}
            encoded = canonical_bytes(result).decode("utf-8")
            conn.execute(
                "INSERT INTO supervisor_operations(operation_key, operation, payload_sha256, result) "
                "VALUES (?, 'dispatch_intent', ?, ?)",
                (operation_key, payload_digest, encoded),
            )
            self._record_event_locked(
                conn, operation_key, "supervisor", "NOTE",
                {"event": "SUPERVISOR_OPERATION", "operation": "dispatch_intent",
                 "payload_sha256": payload_digest,
                 "result_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest()},
            )
            self._append_control_event_locked(
                conn, "DISPATCH_OWNER_OUTCOME_PENDING",
                f"dispatch-owner-outcome:{request_id}:pending",
                self._dispatch_outcome_binding(result),
            )
            return result

    def validate_delegated_dispatch_snapshot(self, *, intent: dict, proof: Any,
                                             principal: str, generation: str,
                                             current_policy: dict) -> dict:
        """Verify issuance and every live Store predicate in one read snapshot."""
        instruction = intent.get("instruction")
        if not isinstance(instruction, dict):
            raise StoreError("delegated dispatch snapshot lacks its instruction", kind="authorization")
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_control_history_locked(conn)
            self._verify_supervisor_records(conn)
            issuance = self._validate_dispatch_issuance_proof_locked(
                conn, proof=proof, instruction=instruction, principal=principal,
                service_generation=generation,
            )
            if (current_policy != issuance["policy"]
                    or intent.get("issuance_operation_key") != issuance["operation_key"]
                    or intent.get("issuance_envelope_sha256") !=
                    hashlib.sha256(canonical_bytes(instruction)).hexdigest()):
                raise StoreError("delegated dispatch snapshot differs from its root issuance", kind="integrity")
            accepted_rows = conn.execute(
                "SELECT task_id, actor, payload FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED' "
                "AND task_id=? ORDER BY seq", (instruction["task_id"],),
            ).fetchall()
            accepted = None
            for row in accepted_rows:
                try:
                    payload = json.loads(row["payload"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("accepted delegated dispatch record is malformed", kind="integrity") from exc
                if isinstance(payload, dict) and payload.get("request_id") == instruction["request_id"]:
                    accepted = self._validate_dispatch_intent_event(
                        payload, task_id=row["task_id"], actor=row["actor"],
                    )
                    break
            if (accepted is None or accepted.get("issuance_operation_key") != issuance["operation_key"]
                    or accepted.get("issuance_envelope_sha256") != hashlib.sha256(
                        canonical_bytes(instruction)).hexdigest()):
                raise StoreError("accepted dispatch is not joined to its exact issuance", kind="integrity")
            basis = self._execution_grant_basis_locked(
                conn, instruction["task_id"], instruction["slot"], instruction["attempt"],
                instruction["epoch"], instruction["run_id"],
                active_service_generation=generation, expected_owner=principal,
                expected_lease_id=accepted["lease_id"], now=self._now(),
            )
            if basis["manifest_sha256"] != accepted["manifest_digest"]:
                raise StoreError("delegated dispatch manifest authority changed", kind="manifest")
            return basis

    def _assert_delegated_dispatch_use_locked(self, conn: sqlite3.Connection, *,
                                              dispatch_request_id: str,
                                              proof: Any,
                                              generation: str,
                                              grant: dict | None = None,
                                              check_current: bool = True,
                                              reservation_grant_id: str | None = None) -> dict:
        self._verify_supervisor_records(conn)
        rows = conn.execute(
            "SELECT task_id, actor, payload FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED' "
            "ORDER BY seq",
        ).fetchall()
        accepted = None
        for row in rows:
            try:
                candidate = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("accepted dispatch event is malformed", kind="integrity") from exc
            if isinstance(candidate, dict) and candidate.get("request_id") == dispatch_request_id:
                accepted = self._validate_dispatch_intent_event(
                    candidate, task_id=row["task_id"], actor=row["actor"],
                )
                break
        if accepted is None or accepted.get("key_class") != "DELEGATED_V1":
            raise StoreError("delegated grant has no delegated accepted-dispatch record", kind="integrity")
        instruction = accepted["instruction"]
        issuance = self._validate_dispatch_issuance_proof_locked(
            conn, proof=proof, instruction=instruction, principal=accepted["principal"],
            service_generation=generation,
        )
        envelope_digest = hashlib.sha256(canonical_bytes(instruction)).hexdigest()
        if (accepted["issuance_operation_key"] != issuance["operation_key"]
                or accepted["issuance_envelope_sha256"] != envelope_digest
                or accepted["key_fingerprint"] != proof.fingerprint):
            raise StoreError("dispatch grant lost its exact issuance association", kind="integrity")
        if check_current:
            basis = self._execution_grant_basis_locked(
                conn, accepted["task_id"], accepted["slot"], accepted["attempt"],
                accepted["epoch"], accepted["run_id"], active_service_generation=generation,
                expected_owner=accepted["principal"], expected_lease_id=accepted["lease_id"],
                now=self._now(), reservation_grant_id=reservation_grant_id,
            )
            if basis["manifest_sha256"] != accepted["manifest_digest"]:
                raise StoreError("delegated dispatch current manifest differs", kind="manifest")
            if grant is not None and any(grant.get(field) != value for field, value in {
                "task_id": accepted["task_id"], "slot": accepted["slot"],
                "attempt": accepted["attempt"], "epoch": accepted["epoch"],
                "run_id": accepted["run_id"], "service_generation": generation,
                "manifest_sha256": accepted["manifest_digest"],
            }.items()):
                raise StoreError("execution grant tuple differs from its delegated dispatch", kind="integrity")
        return accepted

    def _dispatch_grant_source_locked(self, conn: sqlite3.Connection, grant: dict) -> tuple[str, dict] | None:
        matches = []
        for row in conn.execute(
            "SELECT operation_key, operation, payload_sha256, result FROM supervisor_operations "
            "WHERE operation='dispatch_grant'",
        ).fetchall():
            try:
                result = json.loads(row["result"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch grant operation result is malformed", kind="integrity") from exc
            if isinstance(result, dict) and canonical_bytes(result) == canonical_bytes(grant):
                try:
                    digest = hashlib.sha256(canonical_bytes(result)).hexdigest()
                    notes = conn.execute(
                        "SELECT payload FROM events WHERE task_id=? AND kind='NOTE' ORDER BY seq",
                        (row["operation_key"],),
                    ).fetchall()
                    event = json.loads(notes[0]["payload"]) if len(notes) == 1 else None
                except (TypeError, ValueError) as exc:
                    raise StoreError("dispatch grant operation journal is malformed", kind="integrity") from exc
                if (digest != hashlib.sha256(canonical_bytes(grant)).hexdigest()
                        or not isinstance(event, dict)
                        or event.get("event") != "SUPERVISOR_OPERATION"
                        or event.get("operation") != "dispatch_grant"
                        or event.get("payload_sha256") != row["payload_sha256"]
                        or event.get("result_sha256") != hashlib.sha256(
                            canonical_bytes(result).decode("utf-8").encode("utf-8"),
                        ).hexdigest()):
                    raise StoreError("dispatch grant operation differs from its immutable note", kind="integrity")
                payload = row["payload_sha256"]
                matches.append((row["operation_key"], result, payload))
        if len(matches) > 1:
            raise StoreError("execution grant is bound to multiple dispatch requests", kind="integrity")
        if not matches:
            return None
        key, result, digest = matches[0]
        note_row = conn.execute(
            "SELECT payload FROM events WHERE task_id=? AND kind='NOTE'", (key,),
        ).fetchone()
        # The operation payload itself is not stored in the result row. Its source
        # request is recovered from the stable dispatch-grant:<request_id> key.
        dispatch_request_id = key.removeprefix("dispatch-grant:")
        return dispatch_request_id, {"result": result, "payload_sha256": digest}

    def _grant_has_delegated_origin_locked(self, conn: sqlite3.Connection, grant: dict) -> bool:
        """Classify only for refusal; missing grant links never downgrade delegated work."""
        from .assignment_basis import OPERATION as ASSIGNMENT_OPERATION
        task_id = grant.get("task_id") if isinstance(grant, dict) else None
        if not isinstance(task_id, str) or not task_id:
            raise StoreError("execution grant task identity is invalid", kind="authorization")
        self._verify_supervisor_records(conn)
        for row in conn.execute(
                "SELECT result FROM supervisor_operations WHERE operation=?",
                (ASSIGNMENT_OPERATION,)).fetchall():
            try:
                handoff = json.loads(row["result"])
            except (TypeError, ValueError) as exc:
                raise StoreError("authenticated assignment history is malformed", kind="integrity") from exc
            if not isinstance(handoff, dict):
                raise StoreError("authenticated assignment history is malformed", kind="integrity")
            if handoff.get("task_id") == task_id:
                return True
        for row in conn.execute(
                "SELECT task_id, actor, payload FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'"
                " AND task_id=? ORDER BY seq", (task_id,)).fetchall():
            try:
                event = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("accepted dispatch history is malformed", kind="integrity") from exc
            accepted = self._validate_dispatch_intent_event(
                event, task_id=row["task_id"], actor=row["actor"],
            )
            if accepted.get("key_class") == "DELEGATED_V1":
                return True
        return False

    def dispatch_issuance_target_for_grant(self, grant: dict) -> dict | None:
        """Return the exact delegated instruction/key binding associated with a signed grant."""
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            source = self._dispatch_grant_source_locked(conn, grant)
            if source is None:
                if self._grant_has_delegated_origin_locked(conn, grant):
                    raise StoreError("execution grant has no immutable dispatch-grant association", kind="integrity")
                return None
            request_id, _ = source
            for row in conn.execute(
                "SELECT task_id, actor, payload FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED' ORDER BY seq",
            ).fetchall():
                try:
                    payload = json.loads(row["payload"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("accepted dispatch record is malformed", kind="integrity") from exc
                if isinstance(payload, dict) and payload.get("request_id") == request_id:
                    accepted = self._validate_dispatch_intent_event(
                        payload, task_id=row["task_id"], actor=row["actor"],
                    )
                    if accepted.get("key_class") != "DELEGATED_V1":
                        return None
                    return {"instruction": accepted["instruction"],
                            "key_id": accepted["key_id"],
                            "key_fingerprint": accepted["key_fingerprint"],
                            "principal": accepted["principal"],
                            "issuance_operation_key": accepted["issuance_operation_key"],
                            "issuance_envelope_sha256": accepted["issuance_envelope_sha256"]}
            raise StoreError("dispatch grant points to a missing accepted dispatch", kind="integrity")

    def _validate_dispatch_grant_authority_locked(self, conn: sqlite3.Connection, *,
                                                  grant: dict,
                                                  dispatch_request_id: str,
                                                  proof: Any,
                                                  generation: str,
                                                  current: bool,
                                                  expected_operation_payload: dict | None = None,
                                                  reservation_grant_id: str | None = None) -> dict:
        accepted = self._assert_delegated_dispatch_use_locked(
            conn, dispatch_request_id=dispatch_request_id, proof=proof,
            generation=generation, grant=grant if current else None,
            check_current=current, reservation_grant_id=reservation_grant_id,
        )
        key = f"dispatch-grant:{dispatch_request_id}"
        row = conn.execute(
            "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key=?",
            (key,),
        ).fetchone()
        if row is None or row["operation"] != "dispatch_grant":
            raise StoreError("delegated execution grant lacks dispatch-grant operation", kind="integrity")
        try:
            stored_result = json.loads(row["result"])
        except (TypeError, ValueError) as exc:
            raise StoreError("delegated dispatch grant result is malformed", kind="integrity") from exc
        if canonical_bytes(stored_result) != canonical_bytes(grant):
            raise StoreError("execution grant differs from its exact dispatch-grant operation", kind="integrity")
        exact_payload = {
            "request_id": dispatch_request_id,
            "service_generation": generation,
            "issuance_operation_key": accepted["issuance_operation_key"],
            "issuance_envelope_sha256": accepted["issuance_envelope_sha256"],
        }
        expected = exact_payload if expected_operation_payload is None else expected_operation_payload
        if expected != exact_payload or row["payload_sha256"] != hashlib.sha256(
                canonical_bytes(exact_payload)).hexdigest():
            raise StoreError("dispatch-grant operation payload lost its issuance association", kind="integrity")
        return accepted

    def _maybe_validate_delegated_execution_grant_locked(self, conn: sqlite3.Connection, *,
                                                         grant: dict, proof: Any,
                                                         generation: str,
                                                         current: bool,
                                                         authority_guard: Callable[[], bool] | None = None,
                                                         reservation_grant_id: str | None = None) -> None:
        source = self._dispatch_grant_source_locked(conn, grant)
        if source is None:
            if self._grant_has_delegated_origin_locked(conn, grant):
                raise StoreError("execution grant lacks an immutable dispatch-grant operation", kind="integrity")
            return
        dispatch_request_id, source_row = source
        accepted = None
        for event_row in conn.execute(
            "SELECT task_id, actor, payload FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED' ORDER BY seq",
        ).fetchall():
            try:
                payload = json.loads(event_row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("accepted dispatch record is malformed", kind="integrity") from exc
            if isinstance(payload, dict) and payload.get("request_id") == dispatch_request_id:
                accepted = self._validate_dispatch_intent_event(
                    payload, task_id=event_row["task_id"], actor=event_row["actor"],
                )
                break
        if accepted is None:
            raise StoreError("execution grant dispatch operation has no accepted request", kind="integrity")
        if accepted.get("key_class") != "DELEGATED_V1":
            legacy_payload = {"request_id": dispatch_request_id,
                              "service_generation": accepted["service_generation"]}
            if (hashlib.sha256(canonical_bytes(legacy_payload)).hexdigest() != source_row["payload_sha256"]
                    or any(grant.get(field) != value for field, value in {
                        "task_id": accepted["task_id"], "slot": accepted["slot"],
                        "attempt": accepted["attempt"], "epoch": accepted["epoch"],
                        "run_id": accepted["run_id"],
                        "service_generation": accepted["service_generation"],
                        "manifest_sha256": accepted["manifest_digest"],
                    }.items())):
                raise StoreError("execution grant does not match its accepted legacy dispatch", kind="integrity")
            return
        if proof is None and not current:
            expected_payload = {
                "request_id": dispatch_request_id,
                "service_generation": accepted["service_generation"],
                "issuance_operation_key": accepted["issuance_operation_key"],
                "issuance_envelope_sha256": accepted["issuance_envelope_sha256"],
            }
            row = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations "
                "WHERE operation_key=?", (f"dispatch-grant:{dispatch_request_id}",),
            ).fetchone()
            if (row is None or row["operation"] != "dispatch_grant"
                    or row["payload_sha256"] != hashlib.sha256(canonical_bytes(expected_payload)).hexdigest()
                    or canonical_bytes(json.loads(row["result"])) != canonical_bytes(grant)):
                raise StoreError("historical delegated grant observation lost its immutable association",
                                 kind="integrity")
            return
        if proof is None:
            raise StoreError("delegated execution grant lacks root-verified provenance", kind="authorization")
        if current and (authority_guard is None or authority_guard() is not True):
            raise StoreError("delegated root policy/generation changed at execution boundary",
                             kind="authorization")
        expected_payload = {
            "request_id": dispatch_request_id,
            "service_generation": generation,
            "issuance_operation_key": accepted["issuance_operation_key"],
            "issuance_envelope_sha256": accepted["issuance_envelope_sha256"],
        }
        self._validate_dispatch_grant_authority_locked(
            conn, grant=grant, dispatch_request_id=dispatch_request_id,
            proof=proof, generation=generation, current=current,
            expected_operation_payload=expected_payload,
            reservation_grant_id=reservation_grant_id,
        )

    def replay_dispatch_outcome(self, *, principal: str, instruction: dict) -> dict | None:
        """Read an exact, previously accepted result without authorizing new work."""
        from .dispatch_instruction import validate_dispatch_instruction

        _need_str(principal, "principal")
        instruction = validate_dispatch_instruction(instruction)
        if not self.reconciliation_complete:
            raise StoreError("verified Store startup is required for outcome replay", kind="integrity")
        request_id = instruction["request_id"]
        with self._read_tx() as conn:
            # Verify the complete chain, external anchor, operation rows, and
            # pending/ack protocol in the same read snapshot before returning data.
            self._verify_control_history_locked(conn)
            outcome_state, _pending = self._dispatch_outcome_state_locked(conn)
            if outcome_state == "LEGACY_UNRESOLVED":
                raise StoreError(
                    "legacy dispatch history requires separately authorized reconciliation",
                    kind="integrity",
                )
            rows = conn.execute(
                "SELECT seq, task_id, actor, payload FROM events "
                "WHERE kind='DISPATCH_INTENT_ACCEPTED' ORDER BY seq"
            ).fetchall()
            for row in rows:
                try:
                    payload = json.loads(row["payload"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("accepted dispatch event is malformed", kind="integrity") from exc
                payload = self._validate_dispatch_intent_event(
                    payload, task_id=row["task_id"], actor=row["actor"],
                )
                if payload["request_id"] != request_id:
                    continue
                if (payload["principal"] != principal
                        or canonical_bytes(payload["instruction"]) != canonical_bytes(instruction)):
                    return None
                operation = conn.execute(
                    "SELECT operation, payload_sha256, result FROM supervisor_operations "
                    "WHERE operation_key=?", (f"dispatch-intent:{request_id}",),
                ).fetchone()
                if operation is None or operation["operation"] != "dispatch_intent":
                    raise StoreError("accepted dispatch result is missing", kind="integrity")
                try:
                    result = json.loads(operation["result"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("accepted dispatch result is malformed", kind="integrity") from exc
                expected = {"event_seq": int(row["seq"]), **payload}
                if (operation["payload_sha256"] != payload["payload_digest"]
                        or result != expected):
                    raise StoreError("accepted dispatch result differs from verified history", kind="integrity")
                return result
        return None

    @staticmethod
    def _dispatch_outcome_binding(result: dict) -> dict:
        encoded = canonical_bytes(result).decode("utf-8")
        return {
            "request_id": result["request_id"],
            "principal": result["principal"],
            "payload_digest": result["payload_digest"],
            "event_seq": result["event_seq"],
            "result_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "service_generation": result["service_generation"],
        }

    def _dispatch_outcome_state_locked(self, conn: sqlite3.Connection) -> tuple[str, dict | None]:
        """Reconstruct the dispatch admission barrier from the complete event history."""
        accepted_rows = conn.execute(
            "SELECT seq, task_id, actor, payload FROM events "
            "WHERE kind='DISPATCH_INTENT_ACCEPTED' ORDER BY seq"
        ).fetchall()
        controls: dict[str, dict[str, list[tuple[int, str, dict]]]] = {}
        for row in conn.execute(
            "SELECT seq, task_id, payload FROM events "
            "WHERE actor='supervisor' AND kind='NOTE' ORDER BY seq"
        ).fetchall():
            try:
                note = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch control history contains malformed NOTE", kind="integrity") from exc
            if not isinstance(note, dict):
                raise StoreError("dispatch control history NOTE is not an object", kind="integrity")
            control_type = note.get("_vst_control_type")
            if control_type not in {
                "DISPATCH_OWNER_OUTCOME_PENDING", "DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED",
            }:
                continue
            required = {
                "_vst_control_type", "event_id", "request_id", "principal", "payload_digest",
                "event_seq", "result_sha256", "service_generation",
            }
            if set(note) != required:
                raise StoreError("dispatch outcome control record fields are malformed", kind="integrity")
            request_id = note["request_id"]
            if (not isinstance(request_id, str) or not request_id
                    or not isinstance(note["principal"], str) or not note["principal"]
                    or not isinstance(note["service_generation"], str) or not note["service_generation"]
                    or type(note["event_seq"]) is not int or note["event_seq"] < 1
                    or not isinstance(note["payload_digest"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", note["payload_digest"])
                    or not isinstance(note["result_sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", note["result_sha256"])):
                raise StoreError("dispatch outcome control request id is malformed", kind="integrity")
            bucket = controls.setdefault(request_id, {"pending": [], "ack": []})
            key = "pending" if control_type.endswith("PENDING") else "ack"
            bucket[key].append((int(row["seq"]), row["task_id"], note))

        if not accepted_rows:
            if controls:
                raise StoreError("dispatch outcome controls have no accepted event", kind="integrity")
            return "OPEN", None

        accepted: list[tuple[int, dict, str, int]] = []
        seen_ids: set[str] = set()
        for row in accepted_rows:
            try:
                raw = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("accepted dispatch event is malformed", kind="integrity") from exc
            payload = self._validate_dispatch_intent_event(
                raw, task_id=row["task_id"], actor=row["actor"],
            )
            request_id = payload["request_id"]
            if request_id in seen_ids:
                raise StoreError("dispatch request id has duplicate accepted events", kind="integrity")
            seen_ids.add(request_id)
            operation_key = f"dispatch-intent:{request_id}"
            operation = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations "
                "WHERE operation_key=?", (operation_key,),
            ).fetchone()
            if (operation is None or operation["operation"] != "dispatch_intent"
                    or operation["payload_sha256"] != payload["payload_digest"]):
                raise StoreError("accepted dispatch lacks matching operation result", kind="integrity")
            try:
                result = json.loads(operation["result"])
            except (TypeError, ValueError) as exc:
                raise StoreError("stored dispatch result is malformed", kind="integrity") from exc
            event_seq = int(row["seq"])
            if result != {"event_seq": event_seq, **payload}:
                raise StoreError("stored dispatch result differs from accepted event", kind="integrity")
            result_sha256 = hashlib.sha256(operation["result"].encode("utf-8")).hexdigest()
            operation_notes = conn.execute(
                "SELECT seq, payload FROM events WHERE task_id=? AND actor='supervisor' "
                "AND kind='NOTE' ORDER BY seq", (operation_key,),
            ).fetchall()
            if len(operation_notes) != 1:
                raise StoreError("dispatch operation note is missing or duplicated", kind="integrity")
            try:
                operation_note = json.loads(operation_notes[0]["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch operation note is malformed", kind="integrity") from exc
            if (operation_note != {
                    "event": "SUPERVISOR_OPERATION", "operation": "dispatch_intent",
                    "payload_sha256": payload["payload_digest"], "result_sha256": result_sha256,
                } or int(operation_notes[0]["seq"]) <= event_seq):
                raise StoreError("dispatch operation note differs from stored result", kind="integrity")
            accepted.append((event_seq, payload, result_sha256, int(operation_notes[0]["seq"])))

        if set(controls) - seen_ids:
            raise StoreError("dispatch outcome control has no accepted request", kind="integrity")
        pending_states: list[tuple[int, dict]] = []
        protocol_order: list[tuple[int, int | None]] = []
        legacy = False
        for event_seq, payload, result_sha256, operation_seq in accepted:
            request_id = payload["request_id"]
            bucket = controls.get(request_id, {"pending": [], "ack": []})
            if not bucket["pending"] and not bucket["ack"]:
                legacy = True
                continue
            if len(bucket["pending"]) != 1 or len(bucket["ack"]) > 1:
                raise StoreError("dispatch pending or acknowledgement controls are duplicated", kind="integrity")
            expected = {
                "request_id": request_id, "principal": payload["principal"],
                "payload_digest": payload["payload_digest"], "event_seq": event_seq,
                "result_sha256": result_sha256, "service_generation": payload["service_generation"],
            }
            pending_seq, pending_task_id, pending_note = bucket["pending"][0]
            if (pending_task_id != "__control__"
                    or pending_note["event_id"] != f"dispatch-owner-outcome:{request_id}:pending"
                    or {key: pending_note[key] for key in expected} != expected
                    or not event_seq < operation_seq < pending_seq):
                raise StoreError("dispatch pending control does not bind the accepted result", kind="integrity")
            if bucket["ack"]:
                ack_seq, ack_task_id, ack_note = bucket["ack"][0]
                if (ack_task_id != "__control__"
                        or ack_note["event_id"] != f"dispatch-owner-outcome:{request_id}:acknowledged"
                        or {key: ack_note[key] for key in expected} != expected
                        or not pending_seq < ack_seq):
                    raise StoreError("dispatch acknowledgement does not bind its pending result", kind="integrity")
                protocol_order.append((event_seq, ack_seq))
            else:
                pending_states.append((event_seq, expected))
                protocol_order.append((event_seq, None))

        if legacy:
            if protocol_order:
                raise StoreError("dispatch history mixes legacy and acknowledgement protocols", kind="integrity")
            return "LEGACY_UNRESOLVED", None
        previous_ack_seq: int | None = None
        for index, (event_seq, ack_seq) in enumerate(protocol_order):
            if index and (previous_ack_seq is None or previous_ack_seq >= event_seq):
                raise StoreError(
                    "a dispatch was accepted before the previous outcome was acknowledged",
                    kind="integrity",
                )
            previous_ack_seq = ack_seq
        if len(pending_states) > 1:
            raise StoreError("multiple dispatch outcomes remain pending", kind="integrity")
        if pending_states:
            latest_event_seq = accepted[-1][0]
            pending_event_seq, binding = pending_states[0]
            if pending_event_seq != latest_event_seq:
                raise StoreError("a later dispatch was accepted while an earlier outcome was pending", kind="integrity")
            return "PENDING", binding
        return "ACKNOWLEDGED", None

    def acknowledge_dispatch_intent(
        self, *, principal: str, request_id: str, payload_digest: str, event_seq: int,
        result_sha256: str, service_generation: str,
    ) -> dict:
        """Record authenticated relay forwarding of the exact immutable Supervisor result."""
        _need_str(principal, "principal")
        _need_str(request_id, "request_id")
        _need_str(payload_digest, "payload_digest")
        _need_int(event_seq, "event_seq", 1)
        _need_str(result_sha256, "result_sha256")
        _need_str(service_generation, "service_generation")
        if (not re.fullmatch(r"[0-9a-f]{32}", request_id)
                or not re.fullmatch(r"[0-9a-f]{64}", payload_digest)
                or not re.fullmatch(r"[0-9a-f]{64}", result_sha256)):
            raise StoreError("dispatch acknowledgement binding is malformed", kind="argument")
        binding = {
            "request_id": request_id, "principal": principal, "payload_digest": payload_digest,
            "event_seq": event_seq, "result_sha256": result_sha256,
            "service_generation": service_generation,
        }
        event_id = f"dispatch-owner-outcome:{request_id}:acknowledged"
        with self._tx() as conn:
            self._verify_control_history_locked(conn)
            state, pending = self._dispatch_outcome_state_locked(conn)
            if state == "LEGACY_UNRESOLVED":
                raise StoreError("legacy dispatch history cannot be acknowledged", kind="integrity")
            existing = []
            for row in conn.execute(
                "SELECT payload FROM events WHERE actor='supervisor' AND kind='NOTE' ORDER BY seq"
            ).fetchall():
                note = json.loads(row["payload"])
                if (isinstance(note, dict)
                        and note.get("_vst_control_type") == "DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED"
                        and note.get("request_id") == request_id):
                    existing.append(note)
            if existing:
                if (len(existing) != 1 or existing[0].get("event_id") != event_id
                        or {key: existing[0].get(key) for key in binding} != binding):
                    raise StoreError("dispatch acknowledgement conflicts with recorded history", kind="integrity")
                return binding
            if state == "PENDING":
                if pending != binding:
                    raise StoreError("dispatch acknowledgement conflicts with pending outcome", kind="integrity")
            elif state == "ACKNOWLEDGED":
                raise StoreError("there is no pending dispatch outcome to acknowledge", kind="lifecycle")
            else:
                raise StoreError("there is no pending dispatch outcome to acknowledge", kind="lifecycle")
            self._append_control_event_locked(
                conn, "DISPATCH_OWNER_OUTCOME_ACKNOWLEDGED", event_id, binding,
            )
            return binding

    def read_dispatch_intents(self, *, after_seq: int, limit: int = 64) -> dict:
        """Read a verified event window for the Supervisor's filtered subscription."""
        _need_int(after_seq, "after_seq", 0)
        _need_int(limit, "limit", 1, 256)
        # Startup reconciliation verifies the complete chain. The single root
        # writer appends new rows through _record_event_locked, so polling must
        # not rescan the full historical log on every idle tick.
        if not self.reconciliation_complete:
            raise StoreError("verified Store startup is required for dispatch replay", kind="integrity")
        with self._read_tx() as conn:
            rows = conn.execute(
                "SELECT seq, task_id, actor, kind, payload FROM events "
                "WHERE seq > ? ORDER BY seq LIMIT ?",
                (after_seq, limit),
            ).fetchall()
            high_watermark = int(rows[-1]["seq"]) if rows else after_seq
        intents = []
        for row in rows:
            if row["kind"] != "DISPATCH_INTENT_ACCEPTED":
                continue
            try:
                payload = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("stored dispatch intent payload is invalid", kind="integrity") from exc
            valid = self._validate_dispatch_intent_event(
                payload, task_id=row["task_id"], actor=row["actor"],
            )
            intents.append({"event_seq": int(row["seq"]), **valid})
        return {"high_watermark": high_watermark, "intents": intents}

    def find_dispatch_intent(self, request_id: str, *, principal: str | None = None) -> dict:
        """Find one exact intent after verifying its event-chain provenance."""
        _need_str(request_id, "request_id")
        if principal is not None:
            _need_str(principal, "principal")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for dispatch lookup", kind="integrity")
        with self._read_tx() as conn:
            rows = conn.execute(
                "SELECT seq, task_id, actor, payload FROM events "
                "WHERE kind = 'DISPATCH_INTENT_ACCEPTED' ORDER BY seq",
            ).fetchall()
        found = None
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("stored dispatch intent payload is invalid", kind="integrity") from exc
            payload = self._validate_dispatch_intent_event(
                payload, task_id=row["task_id"], actor=row["actor"],
            )
            if payload.get("request_id") == request_id:
                if principal is not None and row["actor"] != principal:
                    raise StoreError("dispatch intent principal does not match its event actor", kind="integrity")
                if found is not None:
                    raise StoreError("dispatch request id has multiple accepted events", kind="integrity")
                found = {"event_seq": int(row["seq"]), **payload}
        if found is None:
            raise StoreError("dispatch intent was not accepted by Supervisor", kind="authorization")
        return found

    def make_dispatch_cursor(self, *, sequence: int, service_generation: str, audience: str) -> dict:
        """Create a peer- and generation-bound cursor token for the Supervisor RPC."""
        _need_int(sequence, "sequence", 0)
        _need_str(service_generation, "service_generation")
        _need_str(audience, "audience")
        body = {"version": 1, "sequence": sequence,
                "service_generation": service_generation, "audience": audience}
        mac = hmac.new(
            self._event_key, _DISPATCH_CURSOR_LABEL + canonical_bytes(body), hashlib.sha256,
        ).hexdigest()
        return {**body, "mac": mac}

    def verify_dispatch_cursor(
        self, cursor: Any, *, service_generation: str, audience: str,
    ) -> int:
        """Verify an opaque cursor; callers cannot forge forward/rewind tokens."""
        fields = {"version", "sequence", "service_generation", "audience", "mac"}
        if not isinstance(cursor, dict) or set(cursor) != fields:
            raise StoreError("dispatch cursor fields are invalid", kind="cursor")
        if (type(cursor["version"]) is not int or cursor["version"] != 1
                or type(cursor["sequence"]) is not int or cursor["sequence"] < 0
                or cursor["service_generation"] != service_generation
                or cursor["audience"] != audience
                or not isinstance(cursor["mac"], str)
                or len(cursor["mac"]) != 64
                or any(ch not in "0123456789abcdef" for ch in cursor["mac"])):
            raise StoreError("dispatch cursor binding is invalid", kind="cursor")
        body = {key: cursor[key] for key in fields - {"mac"}}
        expected = hmac.new(
            self._event_key, _DISPATCH_CURSOR_LABEL + canonical_bytes(body), hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(cursor["mac"], expected):
            raise StoreError("dispatch cursor authentication failed", kind="cursor")
        with self._read_tx() as conn:
            maximum = int(conn.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0])
        if cursor["sequence"] > maximum:
            raise StoreError("dispatch cursor advances beyond committed Store history", kind="cursor")
        return int(cursor["sequence"])

    def _reap_locked(self, conn: sqlite3.Connection, now: float) -> list[sqlite3.Row]:
        rows = conn.execute(
            "SELECT lease_id, task_id, attempt, receipt_count FROM leases "
            "WHERE status = 'LIVE' AND expires_at <= ? ORDER BY lease_id",
            (now,),
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE leases SET status = 'EXPIRED' WHERE lease_id = ?", (row["lease_id"],)
            )
            self._free_slot(conn, row["lease_id"])
            self._record_event_locked(
                conn, row["task_id"], "store", "LEASE_EXPIRED", {"attempt": row["attempt"]}
            )
            if row["receipt_count"] > 0:
                # Partial work: the holder wrote receipts, then died. No WORKER_LOST
                # marker is written for it; the event records what was lost.
                self._record_event_locked(
                    conn, row["task_id"], "store", "LEASE_EXPIRED_PARTIAL",
                    {
                        "attempt": row["attempt"],
                        "lease_id": row["lease_id"],
                        "receipts": int(row["receipt_count"]),
                    },
                )
        return rows

    # ---------------------------------------------------------------- slots

    def init_slots(self, n: int) -> None:
        """Create concurrency slots 1..n (idempotent; existing slots are kept)."""
        _need_int(n, "n", 1, MAX_SLOTS)
        with self._tx() as conn:
            for slot_no in range(1, n + 1):
                conn.execute("INSERT OR IGNORE INTO slots (slot_no) VALUES (?)", (slot_no,))

    # -------------------------------------------------------------- stories

    def open_story(self, story_id: str, project_id: str, phase: int) -> int:
        """Create a story at epoch 1 with no owner; raises if it already exists."""
        _need_str(story_id, "story_id")
        _need_str(project_id, "project_id")
        _need_int(phase, "phase", 1, 10)
        with self._tx() as conn:
            return self._open_story_locked(conn, story_id, project_id, phase)

    def _open_story_locked(
        self, conn: sqlite3.Connection, story_id: str, project_id: str, phase: int,
    ) -> int:
        """Create a new unowned story on the caller's transaction."""
        _need_str(story_id, "story_id")
        _need_str(project_id, "project_id")
        _need_int(phase, "phase", 1, 10)
        if conn.execute(
            "SELECT 1 FROM stories WHERE story_id = ?", (story_id,)
        ).fetchone():
            raise StoreError(f"story {story_id!r} already exists", kind="story")
        conn.execute(
            "INSERT INTO stories (story_id, project_id, phase, epoch, owner, state) "
            "VALUES (?, ?, ?, 1, NULL, 'OPEN')",
            (story_id, project_id, phase),
        )
        return 1

    def current_epoch(self, story_id: str) -> int:
        row = self._story_row(self._conn, story_id)
        return int(row["epoch"])

    def acquire_epoch(
        self, story_id: str, owner: str, ttl_sec: float = DEFAULT_OWNER_TTL_SEC
    ) -> int:
        """Compare-and-swap: bump the epoch unless a live owner holds the story.

        A live owner is one with owner_expires_at in the future. The caller who
        wins becomes the owner for ttl_sec; live leases of the story are fenced
        (status FENCED, slots freed) so a zombie cannot keep a slot.
        """
        _need_str(owner, "owner")
        ttl = _need_ttl(ttl_sec)
        with self._tx() as conn:
            return self._acquire_epoch_locked(conn, story_id, owner, ttl)

    def _acquire_epoch_locked(
        self,
        conn: sqlite3.Connection,
        story_id: str,
        owner: str,
        ttl: float,
        *,
        expected_epoch: int | None = None,
        reap_expired: bool = True,
    ) -> int:
        """Existing epoch transition, shared by direct and idempotent APIs."""
        now = self._now()
        story = self._story_row(conn, story_id)
        if expected_epoch is not None and int(story["epoch"]) != expected_epoch:
            raise StoreError("epoch acquisition has a stale expected fence", kind="epoch")
        expires = story["owner_expires_at"]
        if story["owner"] is not None and expires is not None and expires > now:
            raise StoreError(
                f"story {story_id!r} is owned by live owner {story['owner']!r}",
                kind="epoch",
            )
        # Reap on established public transitions. A fresh-only caller may
        # disable this because its precondition proves the story has no history.
        if reap_expired:
            self._reap_locked(conn, now)
        new_epoch = int(story["epoch"]) + 1
        if new_epoch > MAX_COUNTER:
            raise StoreError("epoch counter exhausted", kind="epoch")
        conn.execute(
            "UPDATE stories SET epoch = ?, owner = ?, owner_expires_at = ?, "
            "state = 'OWNED' WHERE story_id = ?",
            (new_epoch, owner, now + ttl, story_id),
        )
        old = conn.execute(
            "SELECT lease_id, task_id, attempt FROM leases "
            "WHERE story_id = ? AND status = 'LIVE' ORDER BY lease_id",
            (story_id,),
        ).fetchall()
        for row in old:
            conn.execute(
                "UPDATE leases SET status = 'FENCED' WHERE lease_id = ?",
                (row["lease_id"],),
            )
            self._free_slot(conn, row["lease_id"])
            self._record_event_locked(
                conn, row["task_id"], "store", "LEASE_FENCED",
                {"attempt": row["attempt"], "new_epoch": new_epoch},
            )
        self._record_event_locked(
            conn, story_id, owner, "EPOCH_ACQUIRED", {"epoch": new_epoch}
        )
        return new_epoch

    def renew_epoch(self, story_id: str, owner: str, ttl_sec: float) -> None:
        """Extend the owner's liveness; only the current, still-live owner may renew.

        The epoch number is unchanged. Any other caller, or the owner after its
        ownership expired, gets StoreError(kind='epoch').
        """
        _need_str(owner, "owner")
        ttl = _need_ttl(ttl_sec)
        with self._tx() as conn:
            now = self._now()
            story = self._story_row(conn, story_id)
            expires = story["owner_expires_at"]
            if story["owner"] != owner or expires is None or expires <= now:
                raise StoreError(
                    f"{owner!r} is not the live owner of story {story_id!r}", kind="epoch"
                )
            conn.execute(
                "UPDATE stories SET owner_expires_at = ? WHERE story_id = ?",
                (now + ttl, story_id),
            )
            self._record_event_locked(
                conn, story_id, owner, "EPOCH_RENEWED", {"epoch": int(story["epoch"])}
            )

    def release_epoch(self, story_id: str, owner: str) -> None:
        """Give up ownership (owner and expiry cleared, epoch number kept).

        Only the recorded owner may release; otherwise StoreError(kind='epoch').
        The next acquire_epoch then succeeds immediately and bumps the epoch.
        """
        _need_str(owner, "owner")
        with self._tx() as conn:
            story = self._story_row(conn, story_id)
            if story["owner"] != owner:
                raise StoreError(
                    f"{owner!r} is not the owner of story {story_id!r}", kind="epoch"
                )
            conn.execute(
                "UPDATE stories SET owner = NULL, owner_expires_at = NULL, state = 'OPEN' "
                "WHERE story_id = ?",
                (story_id,),
            )
            self._record_event_locked(
                conn, story_id, owner, "EPOCH_RELEASED", {"epoch": int(story["epoch"])}
            )

    # ---------------------------------------------------------------- phase

    def set_phase(self, story_id: str, owner: str, epoch: int, phase: int) -> None:
        """Set the story phase by compare-and-swap on the epoch.

        Succeeds only for the live owner of the story and only when `epoch` is
        still the current epoch (a takeover in between makes it fail with
        StoreError(kind='epoch')). Records a PHASE_SET event.
        """
        _need_str(owner, "owner")
        _need_int(epoch, "epoch", 1)
        _need_int(phase, "phase", 1, 10)
        with self._tx() as conn:
            now = self._now()
            story = self._story_row(conn, story_id)
            expires = story["owner_expires_at"]
            if (
                int(story["epoch"]) != epoch
                or story["owner"] != owner
                or expires is None
                or expires <= now
            ):
                raise StoreError(
                    f"{owner!r} does not own story {story_id!r} at epoch {epoch}",
                    kind="epoch",
                )
            changed = conn.execute(
                "UPDATE stories SET phase = ? WHERE story_id = ? AND epoch = ?",
                (phase, story_id, epoch),
            )
            if changed.rowcount != 1:
                raise StoreError("phase compare-and-swap lost", kind="epoch")
            self._record_event_locked(
                conn, story_id, owner, "PHASE_SET",
                {"epoch": epoch, "from": int(story["phase"]), "to": phase},
            )

    def get_phase(self, story_id: str) -> int:
        return int(self._story_row(self._conn, story_id)["phase"])

    # ---------------------------------------------------------------- tasks

    def register_task(self, manifest: dict) -> str:
        """Store the validated manifest once and fix the task/story link.

        Returns manifest_sha256. Registering the identical manifest again is a
        no-op; a different manifest for the same task_id raises
        StoreError(kind='manifest'). The story must exist and share project_id.
        The budget row is seeded here with cap = manifest cost_cap and spent 0.
        """
        valid = validate_task_manifest(manifest)
        digest = manifest_sha256(valid)
        with self._tx() as conn:
            return self._register_task_locked(conn, valid, digest)

    def _register_task_locked(
        self, conn: sqlite3.Connection, valid: dict, digest: str | None = None,
    ) -> str:
        """Register a validated task and seed its exact manifest budget in one transaction."""
        valid = validate_task_manifest(valid)
        actual_digest = manifest_sha256(valid)
        if digest is not None and digest != actual_digest:
            raise StoreError("task manifest digest differs from its canonical content", kind="manifest")
        digest = actual_digest
        story = self._story_row(conn, valid["story_id"])
        if story["project_id"] != valid["project_id"]:
            raise StoreError("manifest project_id differs from the story", kind="story")
        existing = conn.execute(
            "SELECT manifest_sha256 FROM tasks WHERE task_id = ?", (valid["task_id"],)
        ).fetchone()
        if existing is not None:
            if existing["manifest_sha256"] != digest:
                raise StoreError(
                    f"task {valid['task_id']!r} is registered with a different manifest",
                    kind="manifest",
                )
        else:
            _need_int(valid["cost_cap"], "cost_cap", 0, MAX_BUDGET)
            conn.execute(
                "INSERT INTO tasks (task_id, story_id, manifest_sha256, retry_cap, manifest) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    valid["task_id"], valid["story_id"], digest,
                    valid["retry_cap"], canonical_bytes(valid).decode("utf-8"),
                ),
            )
            conn.execute(
                "INSERT INTO budget (task_id, cap, spent) VALUES (?, ?, 0)",
                (valid["task_id"], valid["cost_cap"]),
            )
            self._record_event_locked(
                conn, valid["task_id"], "store", "TASK_REGISTERED",
                {"manifest_sha256": digest, "story_id": valid["story_id"]},
            )
        return digest

    def get_manifest(self, task_id: str) -> dict:
        """The registered manifest of a task (deep copy from the stored JSON)."""
        return json.loads(self._task_row(self._conn, task_id)["manifest"])

    def get_manifest_by_digest(self, task_id: str, digest: str) -> dict:
        """Return only the immutable registered manifest named by its digest."""
        _need_str(task_id, "task_id")
        _need_str(digest, "manifest_sha256")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for manifest lookup", kind="integrity")
        with self._read_tx() as conn:
            task = self._task_row(conn, task_id)
            if task["manifest_sha256"] != digest:
                raise StoreError("manifest digest is not registered for the task", kind="manifest")
            manifest = validate_task_manifest(json.loads(task["manifest"]))
            if manifest_sha256(manifest) != digest:
                raise StoreError("registered manifest digest is inconsistent", kind="integrity")
            return manifest

    def previous_receipt_sha256(self, task_id: str, slot: str) -> str | None:
        """Read the current receipt-chain tip for one registered task slot."""
        _need_str(task_id, "task_id")
        _need_str(slot, "slot")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for receipt lookup", kind="integrity")
        with self._read_tx() as conn:
            self._task_row(conn, task_id)
            row = conn.execute(
                "SELECT receipt_sha256 FROM receipts WHERE task_id = ? AND slot = ? ORDER BY attempt DESC LIMIT 1",
                (task_id, slot),
            ).fetchone()
            return None if row is None else str(row["receipt_sha256"])

    def execution_grant_basis(
        self, task_id: str, slot: str, attempt: int, epoch: int, run_id: str,
        *, active_service_generation: str, expected_owner: str | None = None,
        expected_lease_id: int | None = None,
    ) -> dict:
        """Return a read-only snapshot for grant signing; claim rechecks it atomically."""
        for value, name in ((task_id, "task_id"), (slot, "slot"), (run_id, "run_id"),
                            (active_service_generation, "active_service_generation")):
            _need_str(value, name)
        _need_int(attempt, "attempt", 1, MAX_COUNTER)
        _need_int(epoch, "epoch", 1, MAX_COUNTER)
        if expected_lease_id is not None:
            _need_int(expected_lease_id, "expected_lease_id", 1)
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store reconciliation is required before grant issuance", kind="integrity")
        with self._read_tx() as conn:
            return self._execution_grant_basis_locked(
                conn, task_id, slot, attempt, epoch, run_id,
                active_service_generation=active_service_generation,
                expected_owner=expected_owner, expected_lease_id=expected_lease_id,
                now=self._now(),
            )

    def _execution_grant_basis_locked(
        self, conn: sqlite3.Connection, task_id: str, slot: str, attempt: int, epoch: int, run_id: str,
        *, active_service_generation: str, expected_owner: str | None = None,
        expected_lease_id: int | None = None, now: float,
        reservation_grant_id: str | None = None,
    ) -> dict:
        """Derive grant authority from an already-open read snapshot."""
        task = self._task_row(conn, task_id)
        self._guard_runner_task_continuation_locked(
            conn, task_id, reservation_grant_id=reservation_grant_id,
        )
        story = self._story_row(conn, task["story_id"])
        if (int(story["epoch"]) != epoch or story["state"] != "OWNED"
                or story["owner"] is None or story["owner_expires_at"] is None
                or float(story["owner_expires_at"]) <= now):
            raise StoreError("grant has no current live story owner/epoch", kind="epoch")
        if expected_owner is not None and story["owner"] != expected_owner:
            raise StoreError("grant caller is not the current story owner", kind="authorization")
        manifest = validate_task_manifest(json.loads(task["manifest"]))
        digest = manifest_sha256(manifest)
        if digest != task["manifest_sha256"]:
            raise StoreError("registered manifest digest is inconsistent", kind="integrity")
        if {entry["slot"]: entry["receipt_type"] for entry in manifest["required_receipts"]}.get(slot) != "TestRun":
            raise StoreError("grant slot is not a manifest TestRun slot", kind="slot")
        lease = conn.execute(
            "SELECT lease_id, epoch, status, expires_at, worker_id "
            "FROM leases WHERE task_id = ? AND attempt = ?",
            (task_id, attempt),
        ).fetchone()
        if (lease is None or int(lease["epoch"]) != epoch or lease["status"] != LEASE_LIVE
                or float(lease["expires_at"]) <= now):
            raise StoreError("grant has no current live lease", kind="lease")
        if expected_lease_id is not None and int(lease["lease_id"]) != expected_lease_id:
            raise StoreError("grant lease differs from its accepted dispatch intent", kind="lease")
        last_receipt = conn.execute(
            "SELECT attempt FROM receipts WHERE task_id = ? AND slot = ? ORDER BY attempt DESC LIMIT 1",
            (task_id, slot),
        ).fetchone()
        expected_attempt = 1 if last_receipt is None else int(last_receipt["attempt"]) + 1
        if not self._runner_receipt_gap_is_eligible_locked(
                conn, task_id, slot, expected_attempt - 1, attempt):
            raise StoreError("receipt attempt gap lacks a verified successor disposition", kind="chain")
        if conn.execute(
            "SELECT 1 FROM receipts WHERE task_id = ? AND slot = ? AND attempt = ?",
            (task_id, slot, attempt),
        ).fetchone() is not None:
            raise StoreError("grant attempt already has a receipt", kind="duplicate")
        if conn.execute(
            "SELECT 1 FROM supervisor_probes WHERE run_id = ?", (run_id,)
        ).fetchone() is None:
            raise StoreError("grant requires a consumed run-bound preflight", kind="probe")
        blocked = self._budget_block_locked(conn, task_id)
        if blocked is not None:
            raise StoreError(blocked, kind="budget")
        return {
            "task_id": task_id, "slot": slot, "attempt": attempt,
            "epoch": epoch, "run_id": run_id, "manifest_sha256": digest,
            "manifest_timeout_sec": int(manifest["timeout_sec"]),
            "runner_id": lease["worker_id"],
            "authority_expires_at": min(
                float(story["owner_expires_at"]), float(lease["expires_at"]),
            ),
            "service_generation": active_service_generation,
        }

    def authenticated_assignment_basis(
        self, assignment_operation_id: str, *, policy: dict, policy_sha256: str,
        active_service_generation: str, expected_run_id: str,
    ) -> dict:
        """Read a verified assignment handoff and live basis in one immutable snapshot."""
        from .assignment_basis import OPERATION, validate_handoff, validate_policy

        if (not isinstance(assignment_operation_id, str)
                or len(assignment_operation_id) != 64
                or any(char not in "0123456789abcdef" for char in assignment_operation_id)):
            raise StoreError("assignment operation id is malformed", kind="authorization")
        _need_str(active_service_generation, "active_service_generation")
        _need_str(expected_run_id, "expected_run_id")
        policy, calculated_policy_sha256 = validate_policy(policy)
        if calculated_policy_sha256 != policy_sha256:
            raise StoreError("assignment policy digest does not match policy content", kind="authorization")
        if not self.reconciliation_complete:
            raise StoreError("verified Store reconciliation is required", kind="integrity")
        with self._read_tx() as conn:
            now = self._now()
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            row = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key = ?",
                (assignment_operation_id,),
            ).fetchone()
            if row is None or row["operation"] != OPERATION:
                raise StoreError("authenticated assignment handoff was not found", kind="authorization")
            operation_events = conn.execute(
                "SELECT actor, kind, payload FROM events WHERE task_id = ? AND kind = 'NOTE'",
                (assignment_operation_id,),
            ).fetchall()
            matched_events = []
            for event_row in operation_events:
                try:
                    event_payload = json.loads(event_row["payload"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("authenticated assignment event is malformed", kind="integrity") from exc
                if isinstance(event_payload, dict) and event_payload.get("event") == "SUPERVISOR_OPERATION":
                    matched_events.append((event_row, event_payload))
            if (len(matched_events) != 1 or matched_events[0][0]["actor"] != "supervisor"
                    or set(matched_events[0][1]) != {
                        "event", "operation", "payload_sha256", "result_sha256",
                    }
                    or matched_events[0][1].get("operation") != OPERATION):
                raise StoreError("authenticated assignment event identity is invalid", kind="integrity")
            try:
                result = json.loads(row["result"])
            except (TypeError, ValueError) as exc:
                raise StoreError("authenticated assignment result is malformed", kind="integrity") from exc
            if row["result"] != canonical_bytes(result).decode("utf-8"):
                raise StoreError("authenticated assignment result is not canonical", kind="integrity")
            handoff = validate_handoff(
                result, policy=policy, policy_sha256=policy_sha256,
                now=datetime.fromtimestamp(now, timezone.utc),
            )
            if handoff["assignment_operation_id"] != assignment_operation_id:
                raise StoreError("assignment operation result identity differs", kind="integrity")
            if (handoff["run_id"] != expected_run_id
                    or handoff["service_generation"] != active_service_generation):
                raise StoreError("assignment handoff belongs to a stale Supervisor run or generation", kind="integrity")
            if row["payload_sha256"] != handoff["payload_sha256"]:
                raise StoreError("assignment operation payload digest differs from canonical request", kind="integrity")
            probe = conn.execute(
                "SELECT probe_sha256 FROM supervisor_probes WHERE run_id = ?",
                (handoff["run_id"],),
            ).fetchone()
            if probe is None or probe["probe_sha256"] != handoff["probe_sha256"]:
                raise StoreError("assignment handoff is not bound to its consumed probe", kind="integrity")
            basis = self._execution_grant_basis_locked(
                conn, handoff["task_id"], handoff["slot"], handoff["attempt"], handoff["epoch"],
                handoff["run_id"], active_service_generation=active_service_generation,
                expected_owner=policy["owner_principal"], expected_lease_id=handoff["lease_id"],
                now=now,
            )
            exact = {
                "task_id": handoff["task_id"], "slot": handoff["slot"],
                "attempt": handoff["attempt"], "epoch": handoff["epoch"],
                "run_id": handoff["run_id"], "manifest_sha256": handoff["task_manifest_sha256"],
                "runner_id": handoff["runner_id"],
            }
            if any(basis[key] != value for key, value in exact.items()):
                raise StoreError("live assignment basis differs from authenticated handoff", kind="integrity")
            return {
                # Validation enriches local metadata; consumers need the exact stored wire object.
                "handoff": result, "basis": basis,
                "authority_expires_at": min(
                    basis["authority_expires_at"],
                    datetime.strptime(handoff["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=timezone.utc).timestamp(),
                ),
            }

    # --------------------------------------------------------------- leases

    def acquire_lease(
        self,
        task_id: str,
        story_id: str,
        worker_id: str,
        epoch: int,
        attempt: int,
        ttl_sec: float,
        *,
        supervisor_key: bytes,
    ) -> None:
        """Take a lease and a free concurrency slot in one transaction.

        A new history row is inserted; earlier leases stay. Raises StoreError
        for: unknown task or wrong story (task/story); stale epoch (epoch); a
        live lease, a previous lease lost and not yet marked by
        supervisor_reap_and_mark, or an attempt other than previous + 1
        (lease); no free slot (slot); a terminal marker already present, the
        budget exceeded (spent > cap or a BUDGET_EXCEEDED event; kind
        'budget'), or the retry cap reached (kind 'retry'; only worker-attributed
        failures count, see failed_attempts). supervisor_key signs the
        RETRY_EXHAUSTED / BUDGET_EXCEEDED marker that is committed before kind
        'retry' / 'budget' is raised (a BUDGET_EXCEEDED event is recorded once)
        and must differ from the event_key (kind 'key'). A worker that spent
        exactly its cap is not blocked: neither new leases nor receipts are
        refused until spent > cap.
        """
        _need_str(task_id, "task_id")
        _need_str(story_id, "story_id")
        _need_str(worker_id, "worker_id")
        _need_int(epoch, "epoch", 1)
        _need_int(attempt, "attempt", 1)
        ttl = _need_ttl(ttl_sec)
        sup_key = self._need_supervisor_key(supervisor_key)
        blocked: str | None = None
        blocked_kind = "retry"
        with self._tx() as conn:
            now = self._now()
            self._reap_locked(conn, now)
            story = self._story_row(conn, story_id)
            if int(story["epoch"]) != epoch:
                raise StoreError(
                    f"stale epoch {epoch}; current is {story['epoch']}", kind="epoch"
                )
            task = self._task_row(conn, task_id)
            if task["story_id"] != story_id:
                raise StoreError(
                    f"task {task_id!r} belongs to story {task['story_id']!r}", kind="story"
                )
            self._guard_runner_task_continuation_locked(conn, task_id)
            prior = conn.execute(
                "SELECT * FROM leases WHERE task_id = ? ORDER BY attempt DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            if prior is not None:
                self._check_prior_lease(prior, task_id)
            terminal = self._terminal_marker(conn, task_id)
            if terminal is not None:
                raise StoreError(
                    f"task {task_id!r} is blocked by terminal marker {terminal}",
                    kind="retry" if terminal == "RETRY_EXHAUSTED" else "budget",
                )
            budget_reason = self._budget_block_locked(conn, task_id)
            if budget_reason is not None:
                # Commit the signed marker, then raise after the commit (as RETRY_EXHAUSTED).
                self._budget_exceeded_locked(conn, task, sup_key, SUPERVISOR_RUNNER_ID, 0)
                blocked = budget_reason
                blocked_kind = "budget"
            expected = 1 if prior is None else int(prior["attempt"]) + 1
            if blocked is None and attempt != expected:
                raise StoreError(
                    f"attempt {attempt} must be previous attempt + 1 (expected {expected})",
                    kind="lease",
                )
            if blocked is not None:
                pass
            elif self._retry_exhausted(conn, task):
                self._supervisor_marker_locked(
                    conn, task, "RETRY_EXHAUSTED", sup_key, SUPERVISOR_RUNNER_ID,
                    f"supervisor-{task_id}-retry",
                )
                blocked = (
                    f"retry cap {task['retry_cap']} reached for task {task_id!r}; "
                    "RETRY_EXHAUSTED marker written"
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO leases (task_id, story_id, attempt, worker_id, epoch, "
                    "expires_at, status, wrote, marked) VALUES (?, ?, ?, ?, ?, ?, 'LIVE', 0, 0)",
                    (task_id, story_id, attempt, worker_id, epoch, now + ttl),
                )
                lease_id = cursor.lastrowid
                claimed = conn.execute(
                    "UPDATE slots SET lease_id = ?, expires_at = ? "
                    "WHERE slot_no = (SELECT MIN(slot_no) FROM slots WHERE lease_id IS NULL)",
                    (lease_id, now + ttl),
                )
                if claimed.rowcount != 1:
                    raise StoreError("no free slot", kind="slot")
                self._record_event_locked(
                    conn, task_id, worker_id, "LEASE_ACQUIRED",
                    {"attempt": attempt, "epoch": epoch, "lease_id": lease_id},
                )
        if blocked is not None:
            raise StoreError(blocked, kind=blocked_kind)

    @staticmethod
    def _check_prior_lease(prior: sqlite3.Row, task_id: str) -> None:
        if prior["status"] == LEASE_LIVE:
            raise StoreError(f"live lease exists for task {task_id!r}", kind="lease")
        if (
            prior["status"] in (LEASE_EXPIRED, LEASE_FENCED)
            and prior["wrote"] == 0
            and prior["marked"] == 0
        ):
            raise StoreError(
                f"attempt {prior['attempt']} of task {task_id!r} was lost and "
                "must be marked by supervisor_reap_and_mark first",
                kind="lease",
            )

    def _acquire_initial_assignment_lease_locked(
        self, conn: sqlite3.Connection, *, task_id: str, story_id: str, worker_id: str,
        epoch: int, ttl_sec: float, expected_manifest_sha256: str, now: float,
    ) -> tuple[int, float]:
        """Create only a proven fresh attempt-1 lease, never writing retry/budget markers."""
        story = self._story_row(conn, story_id)
        task = self._task_row(conn, task_id)
        if (task["story_id"] != story_id or task["manifest_sha256"] != expected_manifest_sha256
                or story["state"] != "OWNED" or story["owner"] != "Codex"
                or int(story["epoch"]) != epoch or story["owner_expires_at"] is None
                or float(story["owner_expires_at"]) <= now):
            raise StoreError("fresh assignment lost its task, owner, or epoch fence", kind="epoch")
        if conn.execute(
            "SELECT 1 FROM leases WHERE task_id = ? OR story_id = ?", (task_id, story_id),
        ).fetchone() is not None:
            raise StoreError("fresh assignment already has lease history", kind="lease")
        if conn.execute("SELECT 1 FROM receipts WHERE task_id = ?", (task_id,)).fetchone() is not None:
            raise StoreError("fresh assignment already has receipt history", kind="lease")
        if conn.execute("SELECT 1 FROM events WHERE task_id = ? AND kind IN "
                        "('RETRY_EXHAUSTED', 'BUDGET_EXCEEDED') LIMIT 1", (task_id,)).fetchone():
            raise StoreError("fresh assignment already has a terminal marker", kind="budget")
        budget = conn.execute(
            "SELECT cap, spent FROM budget WHERE task_id = ?", (task_id,),
        ).fetchone()
        manifest = validate_task_manifest(json.loads(task["manifest"]))
        if (budget is None or int(budget["cap"]) != manifest["cost_cap"]
                or int(budget["spent"]) != 0):
            raise StoreError("fresh assignment budget does not match its pinned manifest", kind="budget")
        prior = conn.execute(
            "SELECT 1 FROM leases WHERE task_id = ? OR story_id = ? ORDER BY attempt DESC LIMIT 1",
            (task_id, story_id),
        ).fetchone()
        if prior is not None or self._terminal_marker(conn, task_id) is not None:
            raise StoreError("fresh assignment has prior lease or terminal history", kind="lease")
        if self._budget_block_locked(conn, task_id) is not None or self._retry_exhausted(conn, task):
            raise StoreError("fresh assignment proof does not exclude retry or budget marker branches",
                             kind="integrity")
        free_slot = conn.execute(
            "SELECT slot_no FROM slots WHERE lease_id IS NULL ORDER BY slot_no LIMIT 1",
        ).fetchone()
        if free_slot is None:
            raise StoreError("no free slot for fresh assignment", kind="slot")
        lease_expires_at = now + _need_ttl(ttl_sec)
        cursor = conn.execute(
            "INSERT INTO leases (task_id, story_id, attempt, worker_id, epoch, "
            "expires_at, status, wrote, marked) VALUES (?, ?, 1, ?, ?, ?, 'LIVE', 0, 0)",
            (task_id, story_id, worker_id, epoch, lease_expires_at),
        )
        lease_id = int(cursor.lastrowid)
        claimed = conn.execute(
            "UPDATE slots SET lease_id = ?, expires_at = ? WHERE slot_no = ? AND lease_id IS NULL",
            (lease_id, lease_expires_at, int(free_slot["slot_no"])),
        )
        if claimed.rowcount != 1:
            raise StoreError("fresh assignment slot claim lost", kind="slot")
        self._record_event_locked(
            conn, task_id, worker_id, "LEASE_ACQUIRED",
            {"attempt": 1, "epoch": epoch, "lease_id": lease_id},
        )
        return lease_id, lease_expires_at

    def bootstrap_assignment(
        self, request: dict, *, policy: dict, policy_sha256: str,
        bootstrap_peer: dict, expected_run_id: str, active_service_generation: str,
        policy_provider: Callable[[], dict], generation_provider: Callable[[], str],
    ) -> dict:
        """Atomically create one fresh policy-pinned assignment and its immutable handoff."""
        from .assignment_basis import (
            HANDOFF_SCHEMA, assignment_operation_id,
            validate_bootstrap_request, validate_handoff, validate_policy,
        )

        policy, computed_policy_sha256 = validate_policy(policy)
        if computed_policy_sha256 != policy_sha256:
            raise StoreError("assignment policy digest differs from its content", kind="authorization")
        if bootstrap_peer != policy["bootstrap_peer"]:
            raise StoreError("authenticated bootstrap peer differs from root policy", kind="authorization")
        if not callable(policy_provider) or not callable(generation_provider):
            raise StoreError("trusted policy and generation providers are required", kind="authorization")
        normalized_request = validate_bootstrap_request(request, policy=policy)
        if normalized_request["run_id"] != expected_run_id:
            raise StoreError("bootstrap request run differs from current Supervisor run", kind="authorization")
        _need_str(expected_run_id, "expected_run_id")
        _need_str(active_service_generation, "active_service_generation")
        op_key = assignment_operation_id(normalized_request, policy_sha256=policy_sha256)
        payload = {
            "request": normalized_request, "bootstrap_peer": bootstrap_peer,
            "policy_sha256": policy_sha256,
        }
        if not self.reconciliation_complete:
            raise StoreError("Store reconciliation is required before assignment bootstrap", kind="integrity")

        def create(conn: sqlite3.Connection) -> dict:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            now = self._now()
            wall_now = datetime.fromtimestamp(now, timezone.utc)
            valid_from = datetime.strptime(policy["valid_from_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc,
            )
            policy_expiry = datetime.strptime(policy["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc,
            )
            if not valid_from <= wall_now < policy_expiry:
                raise StoreError("assignment policy is not currently valid", kind="authorization")
            if generation_provider() != active_service_generation:
                raise StoreError("Supervisor generation changed before assignment commit", kind="integrity")
            probe = conn.execute(
                "SELECT probe_sha256 FROM supervisor_probes WHERE run_id = ?",
                (expected_run_id,),
            ).fetchone()
            if probe is None:
                raise StoreError("current Supervisor run has no consumed preflight", kind="probe")

            story_id = normalized_request["story_id"]
            task_id = normalized_request["task_id"]
            manifest = normalized_request["task_manifest"]
            assignment = next(
                item for item in policy["allowed_assignments"]
                if item["story_id"] == story_id and item["task_id"] == task_id
            )
            digest = manifest_sha256(manifest)
            if (assignment["task_manifest_sha256"] != digest
                    or assignment["project_id"] != manifest["project_id"]
                    or assignment["phase"] != manifest["phase"]):
                raise StoreError("requested assignment differs from the root policy tuple",
                                 kind="authorization")
            if (conn.execute("SELECT 1 FROM stories WHERE story_id = ?", (story_id,)).fetchone()
                    or conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone()):
                raise StoreError("bootstrap only creates absent story and task rows", kind="story")
            if (conn.execute("SELECT 1 FROM leases WHERE task_id = ? OR story_id = ?",
                             (task_id, story_id)).fetchone()
                    or conn.execute("SELECT 1 FROM receipts WHERE task_id = ?", (task_id,)).fetchone()
                    or conn.execute("SELECT 1 FROM events WHERE task_id IN (?, ?) LIMIT 1",
                                    (story_id, task_id)).fetchone()):
                raise StoreError("bootstrap refuses existing assignment history", kind="lease")
            if (conn.execute("SELECT 1 FROM budget WHERE task_id = ?", (task_id,)).fetchone()
                    or self._terminal_marker(conn, task_id) is not None):
                raise StoreError("bootstrap refuses existing budget or terminal history", kind="budget")
            for operation_row in conn.execute(
                    "SELECT result FROM supervisor_operations WHERE operation = ?",
                    (HANDOFF_SCHEMA,)).fetchall():
                try:
                    prior_handoff = json.loads(operation_row["result"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("prior authenticated assignment result is malformed",
                                     kind="integrity") from exc
                if (not isinstance(prior_handoff, dict)
                        or prior_handoff.get("task_id") == task_id
                        or prior_handoff.get("story_id") == story_id):
                    raise StoreError("bootstrap refuses existing assignment handoff history",
                                     kind="story")

            if self._open_story_locked(conn, story_id, manifest["project_id"], manifest["phase"]) != 1:
                raise StoreError("new assignment story did not start at epoch 1", kind="integrity")
            registered_digest = self._register_task_locked(conn, manifest, digest)
            epoch = self._acquire_epoch_locked(
                conn, story_id, policy["owner_principal"], policy["owner_ttl_seconds"],
                expected_epoch=1, reap_expired=False,
            )
            if epoch != 2 or registered_digest != digest:
                raise StoreError("fresh assignment epoch or manifest invariant failed", kind="integrity")
            lease_id, lease_expiry = self._acquire_initial_assignment_lease_locked(
                conn, task_id=task_id, story_id=story_id, worker_id=policy["runner_id"],
                epoch=epoch, ttl_sec=policy["lease_ttl_seconds"],
                expected_manifest_sha256=digest, now=self._now(),
            )
            story = self._story_row(conn, story_id)
            if (story["owner_expires_at"] is None
                    or float(story["owner_expires_at"]) <= self._now()):
                raise StoreError("fresh assignment owner authority expired before handoff",
                                 kind="epoch")

            def canonical_second(timestamp: float) -> datetime:
                return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0)

            issued = canonical_second(self._now())
            maximum_handoff_expiry = issued.timestamp() + policy["maximum_handoff_ttl_seconds"]
            expires = canonical_second(min(
                maximum_handoff_expiry, policy_expiry.timestamp(),
                float(story["owner_expires_at"]), lease_expiry,
            ))
            if expires <= issued:
                raise StoreError("fresh assignment has no positive handoff lifetime", kind="lease")
            current_policy, current_policy_sha256 = validate_policy(policy_provider())
            if current_policy_sha256 != policy_sha256 or current_policy != policy:
                raise StoreError("root assignment policy changed before assignment commit",
                                 kind="authorization")
            if generation_provider() != active_service_generation:
                raise StoreError("Supervisor generation changed before assignment commit",
                                 kind="integrity")
            current_probe = conn.execute(
                "SELECT probe_sha256 FROM supervisor_probes WHERE run_id = ?",
                (expected_run_id,),
            ).fetchone()
            if current_probe is None or current_probe["probe_sha256"] != probe["probe_sha256"]:
                raise StoreError("current preflight changed before assignment commit", kind="probe")
            result = {
                "schema": HANDOFF_SCHEMA,
                "assignment_operation_id": op_key,
                "policy_id": policy["policy_id"], "policy_sha256": policy_sha256,
                "repository": policy["repository"], "sprint_id": policy["sprint_id"],
                "source_head": policy["source_head"], "manifest_sha256": policy["manifest_sha256"],
                "bootstrap_peer": bootstrap_peer, "assignment_principal": policy["owner_principal"],
                "bootstrap_request": normalized_request,
                "task_id": task_id, "story_id": story_id, "project_id": manifest["project_id"],
                "phase": manifest["phase"], "task_manifest_sha256": digest,
                "slot": normalized_request["slot"], "attempt": 1, "epoch": epoch,
                "lease_id": lease_id, "runner_id": policy["runner_id"],
                "run_id": expected_run_id, "service_generation": active_service_generation,
                "probe_sha256": probe["probe_sha256"],
                "issued_at_utc": issued.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "expires_at_utc": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            result["handoff_sha256"] = hashlib.sha256(canonical_bytes(result)).hexdigest()
            return result

        def before_commit(conn: sqlite3.Connection, result: dict) -> None:
            self._verify_event_chain_locked(conn, verify_external_anchor=False)
            self._verify_supervisor_records(conn)
            current_policy, current_policy_sha256 = validate_policy(policy_provider())
            if current_policy_sha256 != policy_sha256 or current_policy != policy:
                raise StoreError("root assignment policy changed before assignment commit",
                                 kind="authorization")
            if generation_provider() != active_service_generation:
                raise StoreError("Supervisor generation changed before assignment commit",
                                 kind="integrity")
            handoff = validate_handoff(
                result, policy=policy, policy_sha256=policy_sha256,
                now=datetime.fromtimestamp(self._now(), timezone.utc),
            )
            if (handoff["run_id"] != expected_run_id
                    or handoff["service_generation"] != active_service_generation):
                raise StoreError("fresh assignment trusted state changed before commit",
                                 kind="integrity")
            current_probe = conn.execute(
                "SELECT probe_sha256 FROM supervisor_probes WHERE run_id = ?",
                (expected_run_id,),
            ).fetchone()
            if current_probe is None or current_probe["probe_sha256"] != handoff["probe_sha256"]:
                raise StoreError("current preflight changed before assignment commit", kind="probe")
            story = self._story_row(conn, handoff["story_id"])
            lease = conn.execute(
                "SELECT lease_id, epoch, status, expires_at, worker_id FROM leases "
                "WHERE task_id = ? AND attempt = 1",
                (handoff["task_id"],),
            ).fetchone()
            if (story["owner"] != policy["owner_principal"]
                    or int(story["epoch"]) != handoff["epoch"]
                    or story["owner_expires_at"] is None
                    or float(story["owner_expires_at"]) <= self._now()
                    or lease is None or int(lease["lease_id"]) != handoff["lease_id"]
                    or int(lease["epoch"]) != handoff["epoch"] or lease["status"] != LEASE_LIVE
                    or lease["worker_id"] != policy["runner_id"]
                    or float(lease["expires_at"]) <= self._now()):
                raise StoreError("fresh assignment authority changed before commit", kind="epoch")

        result = self.execute_idempotent(
            op_key, HANDOFF_SCHEMA, payload, create, before_commit=before_commit,
        )
        # Re-read the committed journal so an uncertain anchor or mismatched result is never
        # reported as success. For an exact replay, use its own issue time to validate history
        # without treating it as refreshed authority.
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            stored = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key = ?",
                (op_key,),
            ).fetchone()
            if (stored is None or stored["operation"] != HANDOFF_SCHEMA
                    or stored["payload_sha256"] != hashlib.sha256(canonical_bytes(payload)).hexdigest()
                    or stored["result"] != canonical_bytes(result).decode("utf-8")):
                raise StoreError("assignment operation result cannot be durably verified", kind="integrity")
        current_policy, current_policy_sha256 = validate_policy(policy_provider())
        if current_policy_sha256 != policy_sha256 or current_policy != policy:
            raise StoreError("root assignment policy changed or was revoked", kind="authorization")
        if generation_provider() != active_service_generation:
            raise StoreError("Supervisor generation changed before assignment response", kind="integrity")
        issued_at = datetime.strptime(result["issued_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc,
        )
        verified = validate_handoff(
            result, policy=policy, policy_sha256=policy_sha256, now=issued_at,
        )
        if verified["payload_sha256"] != stored["payload_sha256"]:
            raise StoreError("assignment operation payload differs from its authenticated handoff",
                             kind="integrity")
        if (verified["run_id"] != expected_run_id
                or verified["service_generation"] != active_service_generation):
            raise StoreError("assignment replay belongs to a stale Supervisor run or generation",
                             kind="integrity")
        return result

    @staticmethod
    def _failed_attempts_locked(conn: sqlite3.Connection, task_id: str) -> int:
        """Worker-attributed failed attempts of a task (the retry-cap counter).

        = max over worker slots of the non-PASS worker results in that slot
        (FAIL, INCONCLUSIVE, NOT_RUN, BLOCKED)
        + EXPIRED and RELEASED leases that wrote nothing. FENCED leases
        (epoch takeover) are never counted.
        """
        per_slot: dict[str, int] = {}
        rows = conn.execute(
            "SELECT slot, body FROM receipts WHERE task_id = ? AND slot != ?",
            (task_id, SUPERVISOR_SLOT),
        ).fetchall()
        for row in rows:
            if json.loads(row["body"])["result"] != "PASS":
                per_slot[row["slot"]] = per_slot.get(row["slot"], 0) + 1
        lost = int(
            conn.execute(
                "SELECT COUNT(*) FROM leases WHERE task_id = ? "
                "AND status IN ('EXPIRED', 'RELEASED') AND wrote = 0",
                (task_id,),
            ).fetchone()[0]
        )
        return max(per_slot.values(), default=0) + lost

    def _retry_exhausted(self, conn: sqlite3.Connection, task: sqlite3.Row) -> bool:
        return self._failed_attempts_locked(conn, task["task_id"]) >= int(task["retry_cap"]) + 1

    def failed_attempts(self, task_id: str) -> int:
        """Worker-attributed failed attempts counted toward retry_cap (read-only)."""
        _need_str(task_id, "task_id")
        with self._read_tx() as conn:
            self._task_row(conn, task_id)
            return self._failed_attempts_locked(conn, task_id)

    @staticmethod
    def _budget_block_locked(conn: sqlite3.Connection, task_id: str) -> str | None:
        """Reason the budget blocks the task, or None.

        Blocks only when spent > cap or a BUDGET_EXCEEDED event exists. Spending
        exactly the cap never blocks (charge refuses to go beyond the cap and
        commits the marker itself), so a lease attempt can never invalidate a
        complete PASS set unless spent really exceeded the cap.
        """
        row = conn.execute(
            "SELECT cap, spent FROM budget WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is not None and row["spent"] > row["cap"]:
            return f"budget exhausted for task {task_id!r} (spent {row['spent']} of {row['cap']})"
        if conn.execute(
            "SELECT 1 FROM events WHERE task_id = ? AND kind = 'BUDGET_EXCEEDED' LIMIT 1",
            (task_id,),
        ).fetchone():
            return f"budget exceeded for task {task_id!r}"
        return None

    def _check_budget_locked(self, conn: sqlite3.Connection, task_id: str) -> None:
        """Refuse (kind 'budget') when spent > cap or a BUDGET_EXCEEDED event exists."""
        reason = self._budget_block_locked(conn, task_id)
        if reason is not None:
            raise StoreError(reason, kind="budget")

    def _budget_exceeded_locked(
        self,
        conn: sqlite3.Connection,
        task: sqlite3.Row,
        supervisor_key: bytes,
        runner_id: str,
        amount: int,
    ) -> None:
        """Record the BUDGET_EXCEEDED event (once) and the signed marker (once)."""
        task_id = task["task_id"]
        row = conn.execute(
            "SELECT cap, spent FROM budget WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row is not None and not conn.execute(
            "SELECT 1 FROM events WHERE task_id = ? AND kind = 'BUDGET_EXCEEDED' LIMIT 1",
            (task_id,),
        ).fetchone():
            self._record_event_locked(
                conn, task_id, "store", "BUDGET_EXCEEDED",
                {"cap": row["cap"], "spent": row["spent"], "amount": amount},
            )
        self._budget_marker_locked(conn, task, supervisor_key, runner_id)

    def _live_lease(
        self, conn: sqlite3.Connection, task_id: str, worker_id: str, epoch: int, now: float
    ) -> sqlite3.Row:
        lease = conn.execute(
            "SELECT * FROM leases WHERE task_id = ? AND status = 'LIVE'", (task_id,)
        ).fetchone()
        if lease is None:
            raise StoreError(f"no live lease for task {task_id!r}", kind="lease")
        if lease["worker_id"] != worker_id:
            raise StoreError("lease belongs to another worker", kind="lease")
        story = self._story_row(conn, lease["story_id"])
        if lease["epoch"] != epoch or int(story["epoch"]) != epoch:
            raise StoreError(f"stale epoch {epoch}", kind="epoch")
        if lease["expires_at"] <= now:
            raise StoreError(f"lease for task {task_id!r} has expired", kind="lease")
        return lease

    def heartbeat(self, task_id: str, worker_id: str, epoch: int, ttl_sec: float) -> None:
        """Extend a live lease; rejects expired, foreign or stale-epoch callers."""
        _need_str(task_id, "task_id")
        _need_str(worker_id, "worker_id")
        _need_int(epoch, "epoch", 1)
        ttl = _need_ttl(ttl_sec)
        with self._tx() as conn:
            now = self._now()
            lease = self._live_lease(conn, task_id, worker_id, epoch, now)
            terminal = self._terminal_marker(conn, task_id)
            if terminal is not None:
                raise StoreError(
                    f"task {task_id!r} is blocked by terminal marker {terminal}",
                    kind="budget" if terminal == "BUDGET_EXCEEDED" else "terminal",
                )
            self._check_budget_locked(conn, task_id)
            conn.execute(
                "UPDATE leases SET expires_at = ? WHERE lease_id = ?",
                (now + ttl, lease["lease_id"]),
            )
            conn.execute(
                "UPDATE slots SET expires_at = ? WHERE lease_id = ?",
                (now + ttl, lease["lease_id"]),
            )

    def release_lease(self, task_id: str, worker_id: str, epoch: int) -> None:
        """Close a live lease (status RELEASED) and free its slot."""
        _need_str(task_id, "task_id")
        _need_str(worker_id, "worker_id")
        _need_int(epoch, "epoch", 1)
        with self._tx() as conn:
            now = self._now()
            lease = self._live_lease(conn, task_id, worker_id, epoch, now)
            conn.execute(
                "UPDATE leases SET status = 'RELEASED' WHERE lease_id = ?", (lease["lease_id"],)
            )
            self._free_slot(conn, lease["lease_id"])
            self._record_event_locked(
                conn, task_id, worker_id, "LEASE_RELEASED", {"lease_id": lease["lease_id"]}
            )

    def reap_expired(self) -> list[str]:
        """Close expired live leases (EXPIRED), free their slots, return task ids."""
        with self._tx() as conn:
            rows = self._reap_locked(conn, self._now())
        return [row["task_id"] for row in rows]

    # ------------------------------------------------------------- receipts

    def append_receipt(self, receipt: dict, story_id: str, key: bytes) -> None:
        """Verify and append one WORKER receipt; never overwrites.

        `key` is the worker signing key. Raises ContractError for a malformed
        receipt and StoreError otherwise: supervisor (receipt in
        SUPERVISOR_SLOT), task / story / manifest (link or hash mismatch), slot
        (undeclared slot or wrong type), signature (bad signature or result !=
        derive_result), epoch (!= current epoch), terminal (terminal marker
        present), budget (spent > cap or a BUDGET_EXCEEDED event; spent == cap
        still allows the final receipts), key (worker key equals the event_key),
        lease (no live unexpired lease held by runner_id at this
        epoch), validation (receipt_id starts with the reserved 'sup-'), retry
        (the slot already has retry_cap + 1 NON-PASS attempts in the CURRENT
        epoch; attempt numbers stay globally consecutive), chain (attempt != last + 1 or
        wrong prev_receipt_sha256), duplicate (receipt_id reused).
        """
        worker_key = _need_key(key, "key")
        if hmac.compare_digest(worker_key, self._event_key):
            raise StoreError("worker key must differ from the event_key", kind="key")
        with self._tx() as conn:
            self._append_locked(conn, receipt, story_id, worker_key, supervisor=False)

    def append_supervisor_receipt(
        self, receipt: dict, story_id: str, *, supervisor_key: bytes
    ) -> None:
        """Verify and append one receipt of SUPERVISOR_SLOT (signed by supervisor_key).

        Same checks as append_receipt except that no lease is involved (the
        supervisor key is the authority) and the slot must be SUPERVISOR_SLOT,
        check_description one of WORKER_LOST / BUDGET_EXCEEDED /
        RETRY_EXHAUSTED with the matching result and empty covered_acceptance.
        A terminal marker is accepted once per task (kind 'duplicate' after).
        """
        sup_key = self._need_supervisor_key(supervisor_key)
        with self._tx() as conn:
            self._append_locked(conn, receipt, story_id, sup_key, supervisor=True)

    def _append_locked(
        self,
        conn: sqlite3.Connection,
        receipt: dict,
        story_id: str,
        key: bytes | None,
        *,
        supervisor: bool,
    ) -> str:
        valid = validate_receipt(receipt)
        _need_str(story_id, "story_id")
        is_supervisor_slot = valid["slot"] == SUPERVISOR_SLOT
        if is_supervisor_slot != supervisor:
            raise StoreError(
                "supervisor-slot receipts only via append_supervisor_receipt; "
                "worker slots only via append_receipt",
                kind="supervisor",
            )
        task = self._task_row(conn, valid["task_id"])
        if task["story_id"] != story_id:
            raise StoreError(
                f"task {valid['task_id']!r} belongs to story {task['story_id']!r}", kind="story"
            )
        if valid["manifest_sha256"] != task["manifest_sha256"]:
            raise StoreError("manifest_sha256 does not match the registered manifest", kind="manifest")
        manifest = json.loads(task["manifest"])
        if valid["role_sha256"] != manifest["role_sha256"]:
            raise StoreError("role_sha256 does not match the registered manifest", kind="manifest")
        if supervisor:
            self._check_marker_shape(valid)
        else:
            declared = {s["slot"]: s["receipt_type"] for s in manifest["required_receipts"]}
            if declared.get(valid["slot"]) != valid["receipt_type"]:
                raise StoreError(
                    f"slot {valid['slot']!r} is not a declared {valid['receipt_type']} slot",
                    kind="slot",
                )
        is_v2 = valid.get("contract_version") == 2
        if not is_v2 and (key is None or not verify(valid, key)):
            raise StoreError("invalid receipt signature", kind="signature")
        if is_v2 and valid["receipt_type"] == "TestRun":
            # The runner key is deliberately not available to the store. The
            # authoritative gate verifies the attestation with its trust input.
            if valid["signature"] != valid["runner_attestation"]["signature"]:
                raise StoreError("TestRun signature does not match runner attestation", kind="signature")
        elif is_v2 and valid["receipt_type"] != "IndependentReview":
            if key is None or not verify(valid, key, RECEIPT_V2_LABEL):
                raise StoreError("invalid v2 receipt signature", kind="signature")
        if derive_result(valid) != valid["result"]:
            raise StoreError("receipt result does not match the derived result", kind="signature")
        story = self._story_row(conn, story_id)
        if valid["epoch"] != int(story["epoch"]):
            raise StoreError(
                f"stale epoch {valid['epoch']}; current is {story['epoch']}", kind="epoch"
            )
        if supervisor:
            reason = valid["check_description"]
            if reason in TERMINAL_MARKERS and self._find_marker(conn, task["task_id"], reason):
                raise StoreError(f"{reason} marker already exists", kind="duplicate")
            lease = None
        else:
            terminal = self._terminal_marker(conn, task["task_id"])
            if terminal is not None:
                raise StoreError(f"task is blocked by terminal marker {terminal}", kind="terminal")
            self._check_budget_locked(conn, task["task_id"])
            lease = self._receipt_lease(conn, valid)
            # Reserved supervisor receipt-id namespace (markers use sup-{task}-{n}).
            if valid["receipt_id"].startswith(SUPERVISOR_RECEIPT_PREFIX):
                raise StoreError(
                    f"receipt_id must not start with the reserved prefix "
                    f"{SUPERVISOR_RECEIPT_PREFIX!r}",
                    kind="validation",
                )
            # Bound per epoch: attempt numbers stay globally consecutive, but only
            # NON-PASS attempts of the slot in the current epoch count against
            # retry_cap + 1, so re-attesting with PASS at a new head is never refused.
            in_epoch = sum(
                1
                for row in conn.execute(
                    "SELECT body FROM receipts WHERE task_id = ? AND slot = ? AND epoch = ?",
                    (valid["task_id"], valid["slot"], valid["epoch"]),
                ).fetchall()
                if json.loads(row["body"])["result"] != "PASS"
            )
            if in_epoch >= int(task["retry_cap"]) + 1:
                raise StoreError(
                    f"slot {valid['slot']!r} already has {in_epoch} non-PASS attempts in epoch "
                    f"{valid['epoch']}; retry_cap {task['retry_cap']} + 1 reached",
                    kind="retry",
                )
        last = conn.execute(
            "SELECT attempt, receipt_sha256 FROM receipts WHERE task_id = ? AND slot = ? "
            "ORDER BY attempt DESC LIMIT 1",
            (valid["task_id"], valid["slot"]),
        ).fetchone()
        expected_attempt = 1 if last is None else last["attempt"] + 1
        persistent_runner_receipt = (
            valid["receipt_type"] == "TestRun"
            and valid.get("contract_version") == 2
            and isinstance(valid.get("runner_attestation"), dict)
        )
        if (valid["attempt"] != expected_attempt
                and not (persistent_runner_receipt and self._runner_receipt_gap_is_eligible_locked(
                    conn, valid["task_id"], valid["slot"], expected_attempt - 1, valid["attempt"],
                ))):
            raise StoreError(
                f"attempt {valid['attempt']} breaks the chain or lacks a verified successor disposition; "
                f"expected {expected_attempt}",
                kind="chain",
            )
        expected_prev = None if last is None else last["receipt_sha256"]
        if valid["prev_receipt_sha256"] != expected_prev:
            raise StoreError("prev_receipt_sha256 does not match the previous receipt", kind="chain")
        digest = receipt_sha256(valid)
        try:
            conn.execute(
                "INSERT INTO receipts (receipt_id, story_id, task_id, slot, attempt, epoch, "
                "receipt_sha256, prev_receipt_sha256, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    valid["receipt_id"], story_id, valid["task_id"], valid["slot"],
                    valid["attempt"], valid["epoch"], digest, valid["prev_receipt_sha256"],
                    canonical_bytes(valid).decode("utf-8"),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise StoreError(f"duplicate receipt: {exc}", kind="duplicate") from exc
        if lease is not None:
            conn.execute(
                "UPDATE leases SET wrote = 1, receipt_count = receipt_count + 1 "
                "WHERE lease_id = ?",
                (lease["lease_id"],),
            )
        self._record_event_locked(
            conn, valid["task_id"], valid["runner_id"], "RECEIPT_APPENDED",
            {"receipt_id": valid["receipt_id"], "sha256": digest, "result": valid["result"]},
        )
        return digest

    @staticmethod
    def _check_marker_shape(valid: dict) -> None:
        reason = valid["check_description"]
        if reason not in MARKER_RESULTS:
            raise StoreError(f"unknown supervisor marker {reason!r}", kind="supervisor")
        if valid["result"] != MARKER_RESULTS[reason]:
            raise StoreError(
                f"marker {reason} must carry result {MARKER_RESULTS[reason]}", kind="supervisor"
            )
        if valid["covered_acceptance"]:
            raise StoreError("supervisor markers must not cover acceptance", kind="supervisor")

    def _receipt_lease(self, conn: sqlite3.Connection, valid: dict) -> sqlite3.Row:
        """The live, unexpired lease that authorises a worker receipt."""
        lease = conn.execute(
            "SELECT * FROM leases WHERE task_id = ? AND status = 'LIVE'", (valid["task_id"],)
        ).fetchone()
        if lease is None:
            raise StoreError(f"no live lease for task {valid['task_id']!r}", kind="lease")
        if lease["worker_id"] != valid["runner_id"]:
            raise StoreError("runner_id is not the lease holder", kind="lease")
        if lease["epoch"] != valid["epoch"]:
            raise StoreError("lease epoch differs from the receipt epoch", kind="epoch")
        if lease["expires_at"] <= self._now():
            raise StoreError("lease has expired", kind="lease")
        return lease

    @staticmethod
    def _find_marker(conn: sqlite3.Connection, task_id: str, reason: str) -> dict | None:
        rows = conn.execute(
            "SELECT body FROM receipts WHERE task_id = ? AND slot = ? ORDER BY attempt",
            (task_id, SUPERVISOR_SLOT),
        ).fetchall()
        for row in rows:
            body = json.loads(row["body"])
            if body["check_description"] == reason:
                return body
        return None

    def _terminal_marker(self, conn: sqlite3.Connection, task_id: str) -> str | None:
        for reason in TERMINAL_MARKERS:
            if self._find_marker(conn, task_id, reason) is not None:
                return reason
        return None

    def receipts_for_task(self, task_id: str) -> list[dict]:
        """All receipts of a task in append order, cross-checked against the event log.

        Within one read transaction the keyed anchor is verified and the set of
        RECEIPT_APPENDED event sha256 values of the task must equal the set of
        receipt digests of the task's rows; any mismatch (a deleted or injected
        receipt row, a truncated event tail) raises StoreError(kind='integrity').
        """
        if self._external_anchor is not None and not self.verify_event_chain():
            raise StoreError("event chain or external checkpoint does not verify", kind="integrity")
        with self._read_tx() as conn:
            self._anchor_state(conn)
            rows = conn.execute(
                "SELECT body FROM receipts WHERE task_id = ? ORDER BY seq", (task_id,)
            ).fetchall()
            bodies = [json.loads(row["body"]) for row in rows]
            row_shas = {receipt_sha256(body) for body in bodies}
            event_shas: set[str] = set()
            for event in conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND kind = 'RECEIPT_APPENDED'",
                (task_id,),
            ).fetchall():
                try:
                    event_shas.add(json.loads(event["payload"])["sha256"])
                except (ValueError, KeyError, TypeError) as exc:
                    raise StoreError(
                        "RECEIPT_APPENDED event payload is malformed", kind="integrity"
                    ) from exc
            if row_shas != event_shas or len(row_shas) != len(bodies):
                raise StoreError(
                    f"receipt rows of task {task_id!r} do not match the RECEIPT_APPENDED events",
                    kind="integrity",
                )
            return bodies

    def evaluate_gate(
        self,
        task_id: str,
        current_head: str,
        current_epoch: int,
        worker_key: bytes,
        **gate_options: Any,
    ) -> Any:
        """Run the pure gate over a verified, single-snapshot store decision set.

        The evaluator gets no integrity flag from the caller. The store verifies
        its full chain and external checkpoint, then supplies the exact stored
        receipts while the read snapshot remains open.
        """
        from .gate import evaluate as gate_evaluator

        _need_str(task_id, "task_id")
        if "verified_successor_attempts" in gate_options:
            raise StoreError(
                "runner successor eligibility is supplied only by verified Store history",
                kind="authorization",
            )
        if not self._reconciliation_complete or self._integrity_locked:
            raise StoreError("startup reconciliation is incomplete or integrity-locked", kind="integrity")
        with self._read_tx() as conn:
            rows = conn.execute(
                "SELECT ts, task_id, actor, kind, payload, prev_hash, hash FROM events ORDER BY seq"
            ).fetchall()
            previous = GENESIS_HASH
            for row in rows:
                fields = {name: row[name] for name in ("ts", "task_id", "actor", "kind", "payload")}
                expected = self._event_mac(previous, fields)
                if row["prev_hash"] != previous or not hmac.compare_digest(row["hash"], expected):
                    self._integrity_locked = True
                    raise StoreError("event chain does not verify", kind="integrity")
                previous = row["hash"]
            count, stored_head = self._anchor_state(conn)
            if count != len(rows) or stored_head != previous:
                self._integrity_locked = True
                raise StoreError("database event head does not verify", kind="integrity")
            self._verify_supervisor_records(conn)
            if self._external_anchor is not None:
                try:
                    latest = self._external_anchor.read_latest()
                except AnchorError as exc:
                    self._integrity_locked = True
                    raise StoreError(str(exc), kind="integrity") from exc
                if latest != signed_checkpoint(count, stored_head, self._event_key):
                    self._integrity_locked = True
                    raise StoreError("database head differs from external checkpoint", kind="integrity")
            task_row = conn.execute(
                "SELECT manifest FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if task_row is None:
                raise StoreError(f"unknown task {task_id!r}", kind="task")
            # Evaluate receipts and execution lifecycle from this same SQLite
            # snapshot. A stale PASS receipt cannot mask a newer ambiguous run.
            self._guard_runner_task_continuation_locked(conn, task_id)
            manifest = json.loads(task_row["manifest"])
            body_rows = conn.execute(
                "SELECT body, receipt_sha256 FROM receipts WHERE task_id = ? ORDER BY seq", (task_id,)
            ).fetchall()
            receipts = [json.loads(row["body"]) for row in body_rows]
            verified_successor_attempts: dict[str, set[int]] = {}
            slot_types = {
                item["slot"]: item["receipt_type"]
                for item in manifest["required_receipts"]
            }
            for slot in slot_types:
                through_attempt = max(
                    (receipt["attempt"] for receipt in receipts if receipt["slot"] == slot),
                    default=0,
                )
                verified_successor_attempts[slot] = (
                    self._verified_runner_successor_attempts_locked(
                        conn, task_id, slot, through_attempt,
                    )
                )
            row_shas = {row["receipt_sha256"] for row in body_rows}
            event_shas: set[str] = set()
            for event in conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND kind = 'RECEIPT_APPENDED'", (task_id,)
            ).fetchall():
                try:
                    event_shas.add(json.loads(event["payload"])["sha256"])
                except (ValueError, KeyError, TypeError) as exc:
                    self._integrity_locked = True
                    raise StoreError("receipt event payload is malformed", kind="integrity") from exc
            if row_shas != event_shas or len(row_shas) != len(receipts):
                self._integrity_locked = True
                raise StoreError("receipt rows do not match the event chain", kind="integrity")
            return gate_evaluator(
                manifest, receipts, current_head, current_epoch, worker_key,
                verified_successor_attempts=verified_successor_attempts,
                **gate_options,
            )

    # --------------------------------------------------------------- events

    def record_event(self, task_id: str, actor: str, kind: str, payload: Any) -> None:
        """Append a caller event; kind must be in CALLER_EVENT_KINDS (closed enum)."""
        _need_str(task_id, "task_id")
        _need_str(actor, "actor")
        if kind not in CALLER_EVENT_KINDS:
            raise StoreError(
                f"event kind must be one of {sorted(CALLER_EVENT_KINDS)}", kind="argument"
            )
        if isinstance(payload, dict) and "_vst_control_type" in payload:
            raise StoreError("reserved supervisor control payload", kind="argument")
        with self._tx() as conn:
            self._record_event_locked(conn, task_id, actor, kind, payload)

    def _append_control_event(self, kind: str, event_id: str, payload: dict) -> dict:
        """Append a supervisor-only NOTE control record, idempotent by event_id."""
        if kind not in CONTROL_EVENT_KINDS:
            raise StoreError("reserved control event kind required", kind="argument")
        if kind == "CONTROL_BREAKER_OVERRIDE":
            raise StoreError("breaker override requires signed atomic admission", kind="provider")
        _need_str(event_id, "event_id")
        if not isinstance(payload, dict):
            raise StoreError("control payload must be an object", kind="argument")
        envelope = {**payload, "_vst_control_type": kind, "event_id": event_id}
        canonical = canonical_bytes(envelope).decode("utf-8")
        with self._tx() as conn:
            return self._append_control_event_locked(conn, kind, event_id, payload, envelope, canonical)
        return envelope

    def _append_control_event_locked(
        self, conn: sqlite3.Connection, kind: str, event_id: str, payload: dict,
        envelope: dict | None = None, canonical: str | None = None,
        *, override_key: bytes | None = None,
    ) -> dict:
        envelope = envelope or {**payload, "_vst_control_type": kind, "event_id": event_id}
        canonical = canonical or canonical_bytes(envelope).decode("utf-8")
        prior = conn.execute(
            "SELECT payload FROM events WHERE actor='supervisor' AND kind='NOTE' ORDER BY seq"
        ).fetchall()
        for row in prior:
            parsed = json.loads(row["payload"])
            if not isinstance(parsed, dict):
                continue
            if parsed.get("event_id") == event_id and parsed.get("_vst_control_type") != kind:
                if kind.startswith("CONTROL_PROVIDER_") or kind == "CONTROL_BREAKER_OVERRIDE":
                    raise StoreError("provider outcome id reused for a different outcome", kind="integrity")
            if parsed.get("_vst_control_type") == kind and parsed.get("event_id") == event_id:
                if canonical_bytes(parsed).decode("utf-8") != canonical:
                    raise StoreError("control event id reused with different payload", kind="integrity")
                if kind == "CONTROL_BREAKER_OVERRIDE":
                    controls = self._control_events_locked(conn)
                    if self._breaker_state_locked(controls) == "PAUSED_PROVIDER":
                        raise StoreError(
                            "a prior override cannot clear a later breaker episode",
                            kind="provider",
                        )
                return parsed
        if kind == "CONTROL_PROVIDER_SUCCESS":
            controls = self._control_events_locked(conn)
            if self._breaker_state_locked(controls) != "CLOSED":
                raise StoreError("provider success cannot close a paused breaker", kind="provider")
        if kind == "CONTROL_BREAKER_OVERRIDE":
            controls = self._control_events_locked(conn)
            record = payload.get("record")
            self._validate_manual_override_locked(event_id, record, override_key, controls)
        self._record_event_locked(conn, "__control__", "supervisor", "NOTE", envelope)
        return envelope

    def append_manual_override(self, record: dict, *, operator_key: bytes) -> dict:
        """Append a signed override only if its pause episode is still current."""
        if not isinstance(record, dict):
            raise StoreError("manual override record must be an object", kind="provider")
        event_id = _need_str(record.get("id"), "manual override id")
        with self._tx() as conn:
            self._verify_control_history_locked(conn)
            return self._append_control_event_locked(
                conn,
                "CONTROL_BREAKER_OVERRIDE",
                event_id,
                {"record": record},
                override_key=operator_key,
            )

    def _validate_manual_override_locked(
        self, action_id: str, record: Any, operator_key: bytes | None,
        controls: list[dict],
    ) -> None:
        required = {
            "id", "action", "breaker_state", "breaker_episode_id",
            "breaker_config_id", "verdict", "evidence_sha256", "signature",
        }
        if (not isinstance(operator_key, (bytes, bytearray))
                or len(operator_key) < MIN_KEY_BYTES
                or not isinstance(record, dict) or set(record) != required
                or not verify(record, bytes(operator_key), OPERATOR_MANUAL_OVERRIDE_LABEL)):
            raise StoreError("manual override operator signature is invalid", kind="provider")
        if (record.get("id") != action_id
                or record.get("action") != "manual_override"
                or record.get("breaker_state") != "PAUSED_PROVIDER"
                or not isinstance(record.get("verdict"), str)
                or not record.get("verdict").strip()
                or record.get("verdict").upper() == "APPROVE"):
            raise StoreError("manual override signature fields are invalid", kind="provider")
        digest = record.get("evidence_sha256")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
            raise StoreError("manual override evidence digest is invalid", kind="provider")
        state, episode_id, config_id = self._breaker_episode_locked(controls)
        if (state != "PAUSED_PROVIDER"
                or record.get("breaker_episode_id") != episode_id
                or record.get("breaker_config_id") != config_id):
            raise StoreError("manual override is stale for the current breaker episode", kind="provider")

    def begin_action(
        self, action_id: str, payload: dict, *, resolution_key: bytes | None = None
    ) -> dict:
        """Atomically validate lifecycle transition and append its intent."""
        _need_str(action_id, "action_id")
        if not isinstance(payload, dict) or payload.get("action") not in (set(LIFECYCLE_ACTION_STATES) | SUPERVISOR_ACTIONS):
            raise StoreError("known supervisor action required", kind="argument")
        if payload.get("action_id") != action_id:
            raise StoreError("intent action_id must match its transaction key", kind="argument")
        action = payload["action"]
        with self._tx() as conn:
            self._verify_control_history_locked(conn)
            controls = self._control_events_locked(conn)
            if action == "manual_override":
                # Validate even when this action ID already completed: a
                # replay must never carry authority from an earlier pause.
                self._validate_manual_override_locked(
                    action_id, payload.get("override_record"), resolution_key, controls
                )
            statuses: dict[str, dict] = {}
            for event in controls:
                if event["kind"] not in {
                    "CONTROL_ACTION_INTENT", "CONTROL_ACTION_COMPLETED",
                    "CONTROL_ACTION_UNKNOWN", "CONTROL_ACTION_RECONCILED",
                }:
                    continue
                root_id = event.get("action_id", event["event_id"])
                status = event["kind"].rsplit("_", 1)[-1].lower()
                if event["kind"] == "CONTROL_ACTION_RECONCILED" and not _valid_action_resolution(event, resolution_key):
                    status = "unknown"
                statuses[root_id] = {"status": status, **event}

            prior_action = statuses.get(action_id)
            if prior_action and prior_action["action"] != action:
                raise StoreError("lifecycle action id reused for a different action", kind="integrity")
            if (prior_action and action == "manual_override"
                    and prior_action["status"] in {"completed", "reconciled"}
                    and canonical_bytes(prior_action.get("override_record"))
                    != canonical_bytes(payload.get("override_record"))):
                raise StoreError(
                    "completed manual override action id reused with a different record",
                    kind="duplicate",
                )
            if prior_action and prior_action["status"] == "completed":
                return prior_action
            if prior_action and prior_action["status"] == "reconciled" and prior_action.get("completed") is True:
                return prior_action
            if prior_action and prior_action["status"] == "reconciled" and prior_action.get("completed") is False:
                attempt = int(prior_action.get("attempt", 1)) + 1
            elif prior_action:
                raise StoreError("another lifecycle outcome is unresolved", kind="lifecycle")
            else:
                attempt = 1

            unresolved = [
                row for row in statuses.values()
                if row.get("action") in LIFECYCLE_ACTION_STATES
                and row["status"] in {"intent", "unknown"}
            ]
            if unresolved:
                raise StoreError("an unresolved lifecycle action blocks new actions", kind="lifecycle")

            if action in SUPERVISOR_ACTIONS:
                if any(row.get("action") == action and row["status"] in {"intent", "unknown"} for row in statuses.values()):
                    raise StoreError("an unresolved supervisor action blocks retry", kind="lifecycle")
                intent_payload = {**payload, "action_id": action_id, "attempt": attempt}
                result = self._append_control_event_locked(
                    conn, "CONTROL_ACTION_INTENT", f"{action_id}:intent:{attempt}", intent_payload
                )
                return {"status": "intent", **result}

            if action == "start" and self._breaker_state_locked(controls) != "CLOSED":
                raise StoreError("provider breaker is open; worker start refused", kind="provider")

            state = "READY"
            for event in controls:
                if event["kind"] == "CONTROL_ACTION_COMPLETED":
                    action_state = LIFECYCLE_ACTION_STATES.get(event.get("action"))
                    if action_state:
                        state = action_state[1]
                elif (event["kind"] == "CONTROL_ACTION_RECONCILED"
                      and event.get("action") in LIFECYCLE_ACTION_STATES
                      and _valid_action_resolution(event, resolution_key)):
                    before, after = LIFECYCLE_ACTION_STATES[event["action"]]
                    state = after if event.get("completed") is True else before

            expected, _ = LIFECYCLE_ACTION_STATES[action]
            if state != expected:
                raise StoreError(
                    f"lifecycle action {action!r} requires {expected}, stored state is {state}",
                    kind="lifecycle",
                )
            intent_payload = {**payload, "action_id": action_id, "attempt": attempt}
            result = self._append_control_event_locked(
                conn, "CONTROL_ACTION_INTENT", f"{action_id}:intent:{attempt}", intent_payload
            )
            return {"status": "intent", **result}

    @staticmethod
    def _breaker_state_locked(controls: list[dict]) -> str:
        return Store._breaker_episode_locked(controls)[0]

    @staticmethod
    def _breaker_episode_locked(controls: list[dict]) -> tuple[str, str | None, str | None]:
        threshold = 3
        failures = 0
        state = "CLOSED"
        episode_id = None
        config_id = None
        for event in controls:
            if event["kind"] == "CONTROL_BREAKER_CONFIG":
                config = event.get("config")
                if isinstance(config, dict) and isinstance(config.get("threshold"), int) and not isinstance(config.get("threshold"), bool):
                    threshold = config["threshold"]
                    config_id = event.get("event_id")
            elif event["kind"] == "CONTROL_PROVIDER_FAILURE":
                failures += 1
                if state != "PAUSED_PROVIDER" and failures >= threshold:
                    state = "PAUSED_PROVIDER"
                    episode_id = event.get("event_id")
            elif event["kind"] == "CONTROL_PROVIDER_SUCCESS":
                failures = 0
                state = "CLOSED"
                episode_id = None
            elif event["kind"] == "CONTROL_BREAKER_OVERRIDE":
                failures = 0
                state = "CLOSED"
                episode_id = None
        return state, episode_id, config_id

    def reconcile_action(
        self, action_id: str, payload: dict, *, resolution_key: bytes
    ) -> dict:
        """Atomically verify signed resolution for the latest unresolved action."""
        _need_str(action_id, "action_id")
        if not isinstance(payload, dict) or payload.get("action_id") != action_id:
            raise StoreError("reconciliation action_id mismatch", kind="argument")
        with self._tx() as conn:
            self._verify_control_history_locked(conn)
            controls = self._control_events_locked(conn)
            statuses: dict[str, dict] = {}
            for event in controls:
                if event["kind"] not in {
                    "CONTROL_ACTION_INTENT", "CONTROL_ACTION_COMPLETED",
                    "CONTROL_ACTION_UNKNOWN", "CONTROL_ACTION_RECONCILED",
                }:
                    continue
                root_id = event.get("action_id", event["event_id"])
                status = event["kind"].rsplit("_", 1)[-1].lower()
                if event["kind"] == "CONTROL_ACTION_RECONCILED" and not _valid_action_resolution(event, resolution_key):
                    status = "unknown"
                statuses[root_id] = {"status": status, **event}
            current = statuses.get(action_id)
            if not current or current["status"] not in {"intent", "unknown"}:
                raise StoreError("action is no longer awaiting reconciliation", kind="lifecycle")
            if (payload.get("action") != current.get("action")
                    or payload.get("attempt") != current.get("attempt")
                    or payload.get("group_id") != current.get("group_id")):
                raise StoreError("reconciliation does not match the current action", kind="integrity")
            event_id = f"{action_id}:reconciled:{current.get('attempt', 1)}:{payload.get('resolution_id')}"
            if not _valid_action_resolution(payload, resolution_key):
                raise StoreError("operator-signed reconciliation record is required", kind="authorization")
            return self._append_control_event_locked(
                conn, "CONTROL_ACTION_RECONCILED", event_id, payload
            )

    def _control_events_locked(self, conn: sqlite3.Connection) -> list[dict]:
        rows = conn.execute(
            "SELECT payload FROM events WHERE actor='supervisor' AND kind='NOTE' ORDER BY seq"
        ).fetchall()
        result = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (ValueError, TypeError) as exc:
                raise StoreError("control NOTE payload is malformed", kind="integrity") from exc
            if isinstance(payload, dict) and payload.get("_vst_control_type") in CONTROL_EVENT_KINDS:
                result.append({"kind": payload["_vst_control_type"], **payload})
        return result

    def _verify_control_history_locked(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            "SELECT ts, task_id, actor, kind, payload, prev_hash, hash FROM events ORDER BY seq"
        ).fetchall()
        previous = GENESIS_HASH
        for row in rows:
            fields = {name: row[name] for name in ("ts", "task_id", "actor", "kind", "payload")}
            expected = self._event_mac(previous, fields)
            if row["prev_hash"] != previous or not hmac.compare_digest(row["hash"], expected):
                self._integrity_locked = True
                raise StoreError("event chain does not verify before lifecycle transition", kind="integrity")
            previous = row["hash"]
        count, head = self._anchor_state(conn)
        if count != len(rows) or head != previous:
            self._integrity_locked = True
            raise StoreError("event anchor mismatch before lifecycle transition", kind="integrity")
        if self._external_anchor is not None:
            try:
                latest = self._external_anchor.read_latest()
            except AnchorError as exc:
                self._integrity_locked = True
                raise StoreError(str(exc), kind="integrity") from exc
            if latest != signed_checkpoint(count, head, self._event_key):
                self._integrity_locked = True
                raise StoreError("external checkpoint mismatch before lifecycle transition", kind="integrity")

    def control_events(self) -> list[dict]:
        """Return verified supervisor control records in append order."""
        if not self.verify_event_chain():
            raise StoreError("control event chain failed verification", kind="integrity")
        with self._read_tx() as conn:
            rows = conn.execute(
                "SELECT payload FROM events WHERE actor='supervisor' AND kind='NOTE' ORDER BY seq"
            ).fetchall()
        result = []
        for row in rows:
            payload = json.loads(row["payload"])
            if isinstance(payload, dict) and payload.get("_vst_control_type") in CONTROL_EVENT_KINDS:
                result.append({"kind": payload["_vst_control_type"], **payload})
        return result

    def verify_event_chain(self) -> bool:
        """True iff the keyed chain is intact AND matches the keyed anchor.

        Detects edited rows, inserted or removed rows and tail truncation (the
        anchor holds the event count and head hash under the same HMAC key).
        Everything is read inside one read transaction, so a concurrent writer
        cannot produce a false tamper result.
        """
        with self._read_tx() as conn:
            try:
                return self._verify_event_chain_locked(conn)
            except StoreError as exc:
                if exc.kind == "integrity":
                    return False
                raise

    def _verify_event_chain_locked(
        self, conn: sqlite3.Connection, *, verify_external_anchor: bool = True,
    ) -> bool:
        """Verify chain and configured external anchor on the caller's snapshot."""
        rows = conn.execute(
            "SELECT ts, task_id, actor, kind, payload, prev_hash, hash "
            "FROM events ORDER BY seq"
        ).fetchall()
        prev_hash = GENESIS_HASH
        for row in rows:
            fields = {
                "ts": row["ts"], "task_id": row["task_id"], "actor": row["actor"],
                "kind": row["kind"], "payload": row["payload"],
            }
            expected = self._event_mac(prev_hash, fields)
            if row["prev_hash"] != prev_hash or not hmac.compare_digest(
                row["hash"].encode("utf-8"), expected.encode("utf-8")
            ):
                self._integrity_locked = True
                raise StoreError("event chain does not verify", kind="integrity")
            prev_hash = row["hash"]
        try:
            self._anchor_state(conn)
        except StoreError as exc:
            if exc.kind == "integrity":
                self._integrity_locked = True
            raise
        if verify_external_anchor and self._external_anchor is not None:
            try:
                latest = self._external_anchor.read_latest()
            except AnchorError as exc:
                self._integrity_locked = True
                raise StoreError(str(exc), kind="integrity") from exc
            if latest != signed_checkpoint(len(rows), prev_hash, self._event_key):
                self._integrity_locked = True
                raise StoreError("external checkpoint mismatch", kind="integrity")
        return True

    def event_anchor(self) -> tuple[int, str]:
        """Verified (event count, head hash) of the log, for external anchoring.

        Read in one read transaction; raises StoreError(kind='integrity') when
        the anchor does not verify against the stored events.
        """
        with self._read_tx() as conn:
            value = self._anchor_state(conn)
            if self._external_anchor is not None:
                try:
                    latest = self._external_anchor.read_latest()
                except AnchorError as exc:
                    self._integrity_locked = True
                    raise StoreError(str(exc), kind="integrity") from exc
                if latest != signed_checkpoint(value[0], value[1], self._event_key):
                    self._integrity_locked = True
                    raise StoreError("database head differs from external checkpoint", kind="integrity")
        return value

    @property
    def reconciliation_complete(self) -> bool:
        return self._reconciliation_complete and not self._integrity_locked

    def reserve_dispatch_issuance(self, intent: dict, *, authority_snapshot: dict) -> dict:
        """Durably reserve one frozen root dispatch issuance before signer entry."""
        from .dispatch_issuance import (
            ISSUANCE_OPERATION, validate_frozen_intent,
        )
        frozen = validate_frozen_intent(intent)
        if not isinstance(authority_snapshot, dict):
            raise StoreError("root issuance authority snapshot is unavailable", kind="authorization")
        key = frozen["operation_key"]
        with self._tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            self._assert_issuance_current_locked(
                conn, frozen, authority_snapshot=authority_snapshot, now=self._now(),
            )
            for prior_row in conn.execute(
                "SELECT * FROM supervisor_operations WHERE operation=?",
                (ISSUANCE_OPERATION,),
            ).fetchall():
                prior_events = self._dispatch_issuance_records_locked(conn, prior_row["operation_key"])
                if not prior_events:
                    raise StoreError("dispatch issuance operation lacks its immutable intent", kind="integrity")
                self._verify_dispatch_issuance_structure(prior_row, prior_events)
                prior_intent = prior_events[0]["intent"]
                if (prior_intent["request_id"] == frozen["request_id"]
                        and prior_row["operation_key"] != key):
                    raise StoreError("truncated dispatch request ID collides across full identities",
                                     kind="integrity")
            row = conn.execute(
                "SELECT operation_key, operation, payload_sha256, result "
                "FROM supervisor_operations WHERE operation_key=?", (key,),
            ).fetchone()
            if row is None:
                self._bind_dispatch_key_class_locked(
                    conn, key_id=frozen["signer"]["key_id"], key_class="DELEGATED_V1",
                    purpose=frozen["signer"]["purpose"],
                    fingerprint=frozen["signer"]["public_key_fingerprint"],
                )
                conn.execute(
                    "INSERT INTO supervisor_operations(operation_key, operation, payload_sha256, result) "
                    "VALUES (?, ?, ?, ?)",
                    (key, ISSUANCE_OPERATION, frozen["payload_sha256"],
                     canonical_bytes({"_vst_state": "PENDING"}).decode("utf-8")),
                )
                self._record_event_locked(conn, key, "supervisor", "NOTE", {
                    "event": "SUPERVISOR_DISPATCH_ISSUANCE_INTENT",
                    "type": "SUPERVISOR_DISPATCH_ISSUANCE_INTENT",
                    "operation_key": key, "operation": ISSUANCE_OPERATION,
                    "payload_sha256": frozen["payload_sha256"], "intent": frozen,
                })
                return {"state": "PENDING", "intent": frozen, "envelope": None,
                        "may_sign": False}
            records = self._dispatch_issuance_records_locked(conn, key)
            if records and records[0].get("intent") != frozen:
                raise StoreError("dispatch issuance identity conflicts with its immutable reservation",
                                 kind="integrity")
            self._verify_dispatch_issuance_structure(row, records)
            state = records[-1].get("event") if records else None
            return {"state": "VERIFY_REQUIRED" if state == "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED"
                    else "PENDING" if state == "SUPERVISOR_DISPATCH_ISSUANCE_INTENT"
                    else "UNKNOWN", "intent": frozen,
                    "envelope": records[-1].get("envelope") if state ==
                    "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED" else None,
                    "may_sign": False}

    def _assert_issuance_current_locked(self, conn: sqlite3.Connection, intent: dict, *,
                                        authority_snapshot: dict, now: float) -> None:
        self._verify_supervisor_records(conn)
        from .assignment_basis import OPERATION as ASSIGNMENT_OPERATION, validate_handoff, validate_policy
        if (set(authority_snapshot) != {"policy", "policy_sha256", "generation", "run_id"}
                or authority_snapshot["policy"] != intent["policy"]
                or authority_snapshot["policy_sha256"] != intent["policy_sha256"]
                or authority_snapshot["generation"] != intent["service_generation"]
                or authority_snapshot["run_id"] != intent["handoff"]["run_id"]):
            raise StoreError("root issuance policy or generation changed", kind="authorization")
        policy, policy_sha256 = validate_policy(authority_snapshot["policy"])
        if policy_sha256 != intent["policy_sha256"]:
            raise StoreError("root issuance policy digest changed", kind="authorization")
        handoff_id = intent["assignment_operation_id"]
        row = conn.execute(
            "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key=?",
            (handoff_id,),
        ).fetchone()
        if row is None or row["operation"] != ASSIGNMENT_OPERATION:
            raise StoreError("root issuance assignment handoff is missing", kind="authorization")
        try:
            handoff_result = json.loads(row["result"])
        except (TypeError, ValueError) as exc:
            raise StoreError("root issuance assignment handoff is malformed", kind="integrity") from exc
        now_utc = datetime.fromtimestamp(now, timezone.utc)
        handoff = validate_handoff(
            handoff_result, policy=policy, policy_sha256=policy_sha256, now=now_utc,
        )
        if handoff_result != intent["handoff"] or row["payload_sha256"] != handoff["payload_sha256"]:
            raise StoreError("root issuance handoff differs from current immutable assignment", kind="integrity")
        probe = conn.execute(
            "SELECT probe_sha256 FROM supervisor_probes WHERE run_id=?", (handoff["run_id"],),
        ).fetchone()
        if probe is None or probe["probe_sha256"] != handoff["probe_sha256"]:
            raise StoreError("root issuance preflight probe is no longer current", kind="probe")
        basis = self._execution_grant_basis_locked(
            conn, handoff["task_id"], handoff["slot"], handoff["attempt"], handoff["epoch"],
            handoff["run_id"], active_service_generation=authority_snapshot["generation"],
            expected_owner=policy["owner_principal"], expected_lease_id=handoff["lease_id"], now=now,
        )
        expected = {
            "manifest_sha256": handoff["task_manifest_sha256"],
            "task_id": handoff["task_id"], "slot": handoff["slot"],
            "attempt": handoff["attempt"], "epoch": handoff["epoch"],
            "run_id": handoff["run_id"], "runner_id": handoff["runner_id"],
        }
        if any(basis.get(name) != value for name, value in expected.items()):
            raise StoreError("root issuance current execution basis changed", kind="authorization")
        frozen_expiry = datetime.strptime(
            intent["unsigned"]["expires_at"], "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=timezone.utc).timestamp()
        authority_expiry = min(
            float(basis["authority_expires_at"]),
            datetime.strptime(handoff["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc).timestamp(),
            datetime.strptime(policy["expires_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc).timestamp(),
        )
        if frozen_expiry > authority_expiry or frozen_expiry <= now:
            raise StoreError("root dispatch instruction no longer fits current authority lifetime",
                             kind="authorization")

    def existing_dispatch_issuance(self, assignment_operation_id: str) -> dict | None:
        """Read the immutable frozen intent before deriving any retry-time fields."""
        import hashlib
        from .dispatch_issuance import OPERATION_KEY_DOMAIN, validate_frozen_intent
        _need_str(assignment_operation_id, "assignment_operation_id")
        digest = hashlib.sha256(OPERATION_KEY_DOMAIN + canonical_bytes({
            "assignment_operation_id": assignment_operation_id,
        })).hexdigest()
        operation_key = "dispatch-issue:" + digest
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            row = conn.execute(
                "SELECT operation_key, operation, payload_sha256, result "
                "FROM supervisor_operations WHERE operation_key=?", (operation_key,),
            ).fetchone()
            if row is None:
                return None
            events = self._dispatch_issuance_records_locked(conn, operation_key)
            self._verify_dispatch_issuance_structure(row, events)
            intent = validate_frozen_intent(events[0]["intent"])
            if intent["assignment_operation_id"] != assignment_operation_id:
                raise StoreError("dispatch issuance assignment identity changed", kind="integrity")
            return intent

    def assert_dispatch_issuance_authority(self, intent: dict, *, authority_snapshot: dict) -> None:
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            self._assert_issuance_current_locked(
                conn, intent, authority_snapshot=authority_snapshot, now=self._now(),
            )

    def verify_dispatch_issuance_completion(self, operation_key: str, verifier) -> dict:
        """Verify an immutable completion outside SQL; the caller must recheck authority before use."""
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            row = conn.execute(
                "SELECT operation_key, operation, payload_sha256, result "
                "FROM supervisor_operations WHERE operation_key=?", (operation_key,),
            ).fetchone()
            if row is None:
                raise StoreError("dispatch issuance reservation is missing", kind="integrity")
            self._verify_dispatch_issuance_structure(row, self._dispatch_issuance_records_locked(conn, operation_key))
            row_value = {name: row[name] for name in
                         ("operation_key", "operation", "payload_sha256", "result")}
            records = self._dispatch_issuance_records_locked(conn, operation_key)
        reduced = self._reduce_dispatch_issuance(row_value, records, verifier)
        if reduced["state"] != "COMPLETED":
            raise StoreError("dispatch issuance completion signature is not verified", kind="integrity")
        return reduced

    def dispatch_issuance_for_envelope(self, envelope: dict, verifier) -> dict:
        """Find one exact immutable issuance completion, verify outside SQL, and return it."""
        from .dispatch_instruction import validate_dispatch_instruction
        exact = validate_dispatch_instruction(envelope)
        matches = []
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            rows = conn.execute(
                "SELECT * FROM supervisor_operations WHERE operation=?",
                ("VST_S2_ROOT_DISPATCH_ISSUE_V1",),
            ).fetchall()
            for row in rows:
                events = self._dispatch_issuance_records_locked(conn, row["operation_key"])
                self._verify_dispatch_issuance_structure(row, events)
                if (events[-1].get("event") == "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED"
                        and events[-1].get("envelope") == exact):
                    matches.append((
                        {name: row[name] for name in
                         ("operation_key", "operation", "payload_sha256", "result")}, events,
                    ))
        if len(matches) != 1:
            raise StoreError("dispatch instruction does not have one exact issuance completion",
                             kind="authorization")
        row_value, events = matches[0]
        result = self._reduce_dispatch_issuance(row_value, events, verifier)
        if result["state"] != "COMPLETED":
            raise StoreError("dispatch issuance signature verification failed", kind="authorization")
        return result

    @staticmethod
    def _dispatch_issuance_records_locked(conn: sqlite3.Connection, operation_key: str) -> list[dict]:
        rows = conn.execute(
            "SELECT actor, payload FROM events WHERE task_id=? AND kind='NOTE' ORDER BY seq",
            (operation_key,),
        ).fetchall()
        records = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch issuance note is malformed", kind="integrity") from exc
            event = payload.get("event") if isinstance(payload, dict) else None
            if event in {
                "SUPERVISOR_DISPATCH_ISSUANCE_INTENT",
                "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
                "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED",
                "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN",
            }:
                if row["actor"] != "supervisor":
                    raise StoreError("dispatch issuance journal actor is not root Supervisor", kind="integrity")
                records.append(payload)
        return records

    @staticmethod
    def _reduce_dispatch_issuance(row: dict, records: list[dict], verifier=None) -> dict:
        from .dispatch_issuance import reduce_issuance_state
        normalized = []
        for item in records:
            event = item.get("event")
            normalized.append({"type": event, **{k: v for k, v in item.items() if k != "event"}})
        normalized_row = dict(row)
        if isinstance(normalized_row.get("result"), str):
            encoded = normalized_row["result"]
            try:
                decoded = json.loads(encoded)
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch issuance operation result is malformed", kind="integrity") from exc
            if canonical_bytes(decoded).decode("utf-8") != encoded:
                raise StoreError("dispatch issuance operation result is not canonical", kind="integrity")
            normalized_row["result"] = decoded
        result = reduce_issuance_state(normalized_row, normalized, completion_verifier=verifier)
        if result["state"] == "CONFLICT":
            raise StoreError("dispatch issuance journal conflicts: " + result["reason"], kind="integrity")
        return result

    def start_dispatch_issuance(self, operation_key: str, intent_sha256: str, *,
                                authority_snapshot: dict) -> bool:
        """Claim the sole signer invocation right with a fresh locked authority check."""
        with self._tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            row = conn.execute(
                "SELECT operation_key, operation, payload_sha256, result "
                "FROM supervisor_operations WHERE operation_key=?", (operation_key,),
            ).fetchone()
            if row is None:
                raise StoreError("dispatch issuance reservation is missing", kind="integrity")
            records = self._dispatch_issuance_records_locked(conn, operation_key)
            if len(records) != 1 or records[0].get("event") != "SUPERVISOR_DISPATCH_ISSUANCE_INTENT":
                raise StoreError("dispatch issuance cannot claim signer after journal divergence", kind="integrity")
            intent = records[0]["intent"]
            from .dispatch_issuance import canonical_sha256
            if canonical_sha256(intent) != intent_sha256:
                raise StoreError("dispatch issuance intent changed before signer claim", kind="integrity")
            if (row["operation"] != "VST_S2_ROOT_DISPATCH_ISSUE_V1"
                    or row["payload_sha256"] != intent["payload_sha256"]
                    or row["result"] != canonical_bytes({"_vst_state": "PENDING"}).decode("utf-8")):
                raise StoreError("dispatch issuance operation row is invalid", kind="integrity")
            self._assert_issuance_current_locked(
                conn, intent, authority_snapshot=authority_snapshot, now=self._now(),
            )
            self._record_event_locked(conn, operation_key, "supervisor", "NOTE", {
                "event": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
                "type": "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
                "operation_key": operation_key, "intent_sha256": intent_sha256,
                "unsigned_sha256": intent["unsigned_sha256"],
            })
            return True

    def complete_dispatch_issuance(self, operation_key: str, intent_sha256: str,
                                   envelope: dict, verifier, *, authority_snapshot: dict) -> dict:
        """Persist a signed envelope only after external root-key verification."""
        from .dispatch_issuance import canonical_sha256
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            row = conn.execute(
                "SELECT operation_key, operation, payload_sha256, result "
                "FROM supervisor_operations WHERE operation_key=?", (operation_key,),
            ).fetchone()
            if row is None:
                raise StoreError("dispatch issuance reservation is missing", kind="integrity")
            records = self._dispatch_issuance_records_locked(conn, operation_key)
            if len(records) != 2 or records[-1].get("event") != "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED":
                raise StoreError("dispatch issuance signer claim is missing or already terminal", kind="integrity")
            intent = records[0].get("intent")
            if canonical_sha256(intent) != intent_sha256:
                raise StoreError("dispatch issuance intent changed before completion", kind="integrity")
            row_value = {name: row[name] for name in
                         ("operation_key", "operation", "payload_sha256", "result")}
            captured_records = records
            completion = {
                "event": "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED",
                "type": "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED",
                "operation_key": operation_key, "intent_sha256": intent_sha256,
                "unsigned_sha256": intent["unsigned_sha256"], "envelope": envelope,
                "envelope_sha256": canonical_sha256(envelope),
            }
        # The root verifier (including key file reads and OpenSSL) runs outside SQL.
        reduced = self._reduce_dispatch_issuance(row_value, [*captured_records, completion], verifier)
        if reduced["state"] != "COMPLETED":
            raise StoreError("dispatch signer completion did not verify", kind="integrity")
        with self._tx() as conn:
            self._verify_event_chain_locked(conn)
            self._assert_issuance_current_locked(
                conn, captured_records[0]["intent"],
                authority_snapshot=authority_snapshot, now=self._now(),
            )
            current = conn.execute(
                "SELECT operation_key, operation, payload_sha256, result "
                "FROM supervisor_operations WHERE operation_key=?", (operation_key,),
            ).fetchone()
            current_records = self._dispatch_issuance_records_locked(conn, operation_key)
            if (current is None
                    or {name: current[name] for name in row_value} != row_value
                    or canonical_bytes(current_records) != canonical_bytes(captured_records)):
                raise StoreError("dispatch issuance journal changed during signature verification", kind="integrity")
            self._record_event_locked(conn, operation_key, "supervisor", "NOTE", completion)
            return reduced

    def mark_dispatch_issuance_unknown(self, operation_key: str, intent_sha256: str,
                                       error_class: str) -> None:
        """Record an ambiguous signer outcome; this identity can never be signed again."""
        from .dispatch_issuance import canonical_sha256
        with self._tx() as conn:
            self._verify_event_chain_locked(conn)
            records = self._dispatch_issuance_records_locked(conn, operation_key)
            if len(records) != 2 or records[-1].get("event") != "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED":
                return
            intent = records[0].get("intent")
            if canonical_sha256(intent) != intent_sha256:
                raise StoreError("dispatch issuance intent changed before UNKNOWN record", kind="integrity")
            self._record_event_locked(conn, operation_key, "supervisor", "NOTE", {
                "event": "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN",
                "type": "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN",
                "operation_key": operation_key, "intent_sha256": intent_sha256,
                "unsigned_sha256": intent["unsigned_sha256"],
                "error_class": error_class,
            })

    def _verified_database_history(self) -> list[tuple[int, str]]:
        """Return every verified `(event_count, head)` prefix in the DB chain."""
        with self._read_tx() as conn:
            rows = conn.execute(
                "SELECT ts, task_id, actor, kind, payload, prev_hash, hash FROM events ORDER BY seq"
            ).fetchall()
            previous = GENESIS_HASH
            history = [(0, GENESIS_HASH)]
            for row in rows:
                fields = {name: row[name] for name in ("ts", "task_id", "actor", "kind", "payload")}
                expected = self._event_mac(previous, fields)
                if row["prev_hash"] != previous or not hmac.compare_digest(row["hash"], expected):
                    raise StoreError("event chain does not verify", kind="integrity")
                previous = row["hash"]
                history.append((len(history), previous))
            count, head = self._anchor_state(conn)
            if count != len(rows) or head != previous:
                raise StoreError("database event head is inconsistent", kind="integrity")
            self._verify_supervisor_records(conn)
            return history

    def _verified_database_head(self) -> tuple[int, str]:
        return self._verified_database_history()[-1]

    def _verify_supervisor_records(self, conn: sqlite3.Connection) -> None:
        """Cross-check supervisor side tables against their append-only events."""
        operations = {
            row["operation_key"]: row
            for row in conn.execute("SELECT * FROM supervisor_operations").fetchall()
        }
        probes = {row["run_id"]: row for row in conn.execute("SELECT * FROM supervisor_probes").fetchall()}
        event_operations: dict[str, dict] = {}
        external_intents: dict[str, list[dict]] = {}
        external_completions: dict[str, list[dict]] = {}
        external_unknown: dict[str, list[dict]] = {}
        issuance_events: dict[str, list[dict]] = {}
        dispatch_class_events: dict[str, list[tuple[str, dict]]] = {}
        event_probes: dict[str, dict] = {}
        runner_chain_events: dict[str, list[dict]] = {}
        for row in conn.execute("SELECT task_id, actor, payload FROM events WHERE kind = 'NOTE'").fetchall():
            try:
                payload = json.loads(row["payload"])
            except (ValueError, TypeError) as exc:
                raise StoreError("supervisor note event is malformed", kind="integrity") from exc
            if not isinstance(payload, dict):
                raise StoreError("supervisor note event is not an object", kind="integrity")
            if payload.get("event") == "SUPERVISOR_OPERATION":
                event_operations[row["task_id"]] = payload
            elif payload.get("event") == "SUPERVISOR_EXTERNAL_OPERATION_INTENT":
                external_intents.setdefault(row["task_id"], []).append(payload)
            elif payload.get("event") == "SUPERVISOR_EXTERNAL_OPERATION_COMPLETED":
                external_completions.setdefault(row["task_id"], []).append(payload)
            elif payload.get("event") == "SUPERVISOR_EXTERNAL_OPERATION_UNKNOWN":
                external_unknown.setdefault(row["task_id"], []).append(payload)
            elif payload.get("event") in {
                "SUPERVISOR_DISPATCH_ISSUANCE_INTENT",
                "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
                "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED",
                "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN",
            }:
                if row["actor"] != "supervisor":
                    raise StoreError("dispatch issuance event was not written by root Supervisor",
                                     kind="integrity")
                issuance_events.setdefault(row["task_id"], []).append(payload)
            elif payload.get("event") == "SUPERVISOR_DISPATCH_KEY_CLASS_BOUND":
                dispatch_class_events.setdefault(row["task_id"], []).append((row["actor"], payload))
            elif row["task_id"].startswith("dispatch-key-class:"):
                raise StoreError("dispatch key-class journal contains an unknown NOTE family",
                                 kind="integrity")
            elif payload.get("event") == "PREFLIGHT_CONSUMED":
                event_probes[row["task_id"]] = payload
            elif payload.get("event") in {
                    "RUNNER_EXECUTION_PENDING", "RUNNER_EXECUTION_RESERVED", "RUNNER_EXECUTION_COMPLETE",
                    "RUNNER_EXECUTION_INDETERMINATE", "RUNNER_EXECUTION_RECONCILED"}:
                runner_chain_events.setdefault(row["task_id"], []).append(payload)
        external_keys = set(external_intents)
        issuance_keys = set(issuance_events)
        if (set(operations) != set(event_operations) | external_keys | issuance_keys
                or external_keys & set(event_operations)
                or issuance_keys & (set(event_operations) | external_keys)
                or (set(external_completions) | set(external_unknown)) - external_keys
                or set(probes) != set(event_probes)):
            raise StoreError("supervisor records differ from their append-only events", kind="integrity")
        class_bindings: dict[str, dict] = {}
        for task_id, bindings in dispatch_class_events.items():
            if len(bindings) != 1:
                raise StoreError("dispatch key class binding has multiple immutable events", kind="integrity")
            actor, binding = bindings[0]
            key_id = task_id.removeprefix("dispatch-key-class:")
            if (actor != "supervisor" or not task_id.startswith("dispatch-key-class:")
                    or binding != {
                        "event": "SUPERVISOR_DISPATCH_KEY_CLASS_BOUND", "key_id": key_id,
                        "key_class": binding.get("key_class"), "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
                        "public_key_fingerprint": binding.get("public_key_fingerprint"),
                    } or binding.get("key_class") not in {"LEGACY_V1", "DELEGATED_V1"}
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key_id)
                    or not isinstance(binding.get("public_key_fingerprint"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", binding["public_key_fingerprint"])):
                raise StoreError("dispatch key class binding is malformed", kind="integrity")
            class_bindings[key_id] = binding
        for issuance_key, events in issuance_events.items():
            if not events or not isinstance(events[0].get("intent"), dict):
                raise StoreError("dispatch issuance lacks its immutable intent", kind="integrity")
            signer = events[0]["intent"].get("signer", {})
            binding = class_bindings.get(signer.get("key_id"))
            if (binding is None or binding.get("key_class") != "DELEGATED_V1"
                    or binding.get("purpose") != signer.get("purpose")
                    or binding.get("public_key_fingerprint") != signer.get("public_key_fingerprint")
                    or events[0].get("operation_key") != issuance_key
                    or events[0].get("payload_sha256") != events[0]["intent"].get("payload_sha256")):
                raise StoreError("dispatch issuance differs from its immutable delegated key binding",
                                 kind="integrity")
        for operation_key, row in operations.items():
            try:
                result = json.loads(row["result"])
            except (KeyError, ValueError, TypeError) as exc:
                raise StoreError("supervisor operation record is malformed", kind="integrity") from exc
            event = event_operations.get(operation_key)
            if event is not None:
                result_digest = hashlib.sha256(row["result"].encode("utf-8")).hexdigest()
                if (event.get("operation") != row["operation"]
                        or event.get("payload_sha256") != row["payload_sha256"]
                        or event.get("result_sha256") != result_digest):
                    raise StoreError("supervisor operation record does not match its event", kind="integrity")
                continue

            issuance = issuance_events.get(operation_key)
            if issuance is not None:
                self._verify_dispatch_issuance_structure(row, issuance)
                continue

            intents = external_intents.get(operation_key, [])
            if not intents or result != {"_vst_state": "PENDING"}:
                raise StoreError("external operation intent row is malformed", kind="integrity")
            for intent in intents:
                attempt = intent.get("attempt")
                if (intent.get("operation_key") != operation_key
                        or intent.get("operation") != row["operation"]
                        or intent.get("payload_sha256") != row["payload_sha256"]
                        or intent.get("state") != "PENDING"
                        or isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1):
                    raise StoreError("external operation intent does not match its row", kind="integrity")
            completion_results: list[Any] = []
            for completion in external_completions.get(operation_key, []):
                attempt = completion.get("attempt")
                result_value = completion.get("result")
                try:
                    encoded = canonical_bytes(result_value).decode("utf-8")
                except (TypeError, ValueError) as exc:
                    raise StoreError("external operation completion result is malformed", kind="integrity") from exc
                if (completion.get("operation_key") != operation_key
                        or completion.get("operation") != row["operation"]
                        or completion.get("payload_sha256") != row["payload_sha256"]
                        or isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1
                        or hashlib.sha256(encoded.encode("utf-8")).hexdigest() != completion.get("result_sha256")):
                    raise StoreError("external operation completion does not match its intent", kind="integrity")
                completion_results.append(result_value)
            if completion_results and any(
                    canonical_bytes(value) != canonical_bytes(completion_results[0])
                    for value in completion_results[1:]):
                raise StoreError("external operation has conflicting completion results", kind="integrity")
            for unknown in external_unknown.get(operation_key, []):
                attempt = unknown.get("attempt")
                if (unknown.get("operation_key") != operation_key
                        or unknown.get("operation") != row["operation"]
                        or unknown.get("payload_sha256") != row["payload_sha256"]
                        or isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1):
                    raise StoreError("external operation outcome does not match its intent", kind="integrity")
        dispatch_operations = {
            key: row for key, row in operations.items()
            if row["operation"] == "dispatch_intent"
        }
        dispatch_events: dict[str, dict] = {}
        for row in conn.execute(
            "SELECT seq, task_id, actor, payload FROM events "
            "WHERE kind = 'DISPATCH_INTENT_ACCEPTED' ORDER BY seq",
        ).fetchall():
            try:
                payload = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch intent event is malformed", kind="integrity") from exc
            payload = self._validate_dispatch_intent_event(
                payload, task_id=row["task_id"], actor=row["actor"],
            )
            operation_key = f"dispatch-intent:{payload['request_id']}"
            if operation_key in dispatch_events:
                raise StoreError("dispatch request id has multiple events", kind="integrity")
            operation = dispatch_operations.get(operation_key)
            if operation is None or operation["payload_sha256"] != payload["payload_digest"]:
                raise StoreError("dispatch event lacks its matching idempotency record", kind="integrity")
            try:
                result = json.loads(operation["result"])
            except (TypeError, ValueError) as exc:
                raise StoreError("dispatch idempotency result is malformed", kind="integrity") from exc
            if result != {"event_seq": int(row["seq"]), **payload}:
                raise StoreError("dispatch idempotency result differs from its event", kind="integrity")
            class_binding = class_bindings.get(payload["key_id"])
            expected_class = payload.get("key_class", "LEGACY_V1")
            if ((class_binding is None and expected_class == "DELEGATED_V1")
                    or (class_binding is not None and (
                        class_binding.get("key_class") != expected_class
                        or class_binding.get("purpose") != "VST_S2_DISPATCH_INSTRUCTION_V1"))):
                raise StoreError("accepted dispatch lacks its immutable key-class binding", kind="integrity")
            if payload.get("key_class") == "DELEGATED_V1":
                binding = class_binding
                issue_events = issuance_events.get(payload.get("issuance_operation_key"), [])
                if (binding is None or binding.get("key_class") != "DELEGATED_V1"
                        or binding.get("public_key_fingerprint") != payload.get("key_fingerprint")
                        or not issue_events
                        or issue_events[-1].get("event") != "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED"
                        or issue_events[-1].get("envelope") != payload["instruction"]
                        or payload.get("issuance_envelope_sha256") != hashlib.sha256(
                            canonical_bytes(payload["instruction"])).hexdigest()):
                    raise StoreError("accepted delegated dispatch is not joined to its exact issuance",
                                     kind="integrity")
            dispatch_events[operation_key] = payload
        if set(dispatch_events) != set(dispatch_operations):
            raise StoreError("dispatch idempotency records differ from accepted events", kind="integrity")
        for run_id, row in probes.items():
            event = event_probes[run_id]
            if (event.get("nonce") != row["nonce"]
                    or event.get("spec_sha256") != row["spec_sha256"]
                    or event.get("probe_sha256") != row["probe_sha256"]):
                raise StoreError("supervisor probe record does not match its event", kind="integrity")

        runner_claims = {
            row["grant_id"]: row
            for row in conn.execute("SELECT * FROM runner_execution_claims").fetchall()
        }
        runner_table_events: dict[str, list[dict]] = {}
        for row in conn.execute(
                "SELECT grant_id, state, payload FROM runner_execution_events ORDER BY seq").fetchall():
            try:
                event = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("runner execution side event is malformed", kind="integrity") from exc
            if not isinstance(event, dict) or event.get("state") != row["state"]:
                raise StoreError("runner execution side event state is invalid", kind="integrity")
            runner_table_events.setdefault(row["grant_id"], []).append(event)
        if set(runner_claims) != set(runner_table_events) or set(runner_claims) != set(runner_chain_events):
            raise StoreError("runner execution claims differ from their append-only events", kind="integrity")
        event_name = {
            "PENDING": "RUNNER_EXECUTION_PENDING",
            "EXECUTION_RESERVED": "RUNNER_EXECUTION_RESERVED",
            "COMPLETE": "RUNNER_EXECUTION_COMPLETE",
            "INDETERMINATE": "RUNNER_EXECUTION_INDETERMINATE",
            "RECONCILED": "RUNNER_EXECUTION_RECONCILED",
        }
        runner_resolution_ids: set[str] = set()
        for grant_id, claim in runner_claims.items():
            try:
                grant = json.loads(claim["grant_body"])
                canonical_grant = canonical_bytes(grant)
            except (TypeError, ValueError) as exc:
                raise StoreError("runner execution grant record is malformed", kind="integrity") from exc
            if (hashlib.sha256(canonical_grant).hexdigest() != claim["payload_sha256"]
                    or grant.get("grant_id") != claim["grant_id"]
                    or grant.get("invocation_id") != claim["invocation_id"]
                    or grant.get("request_id") != claim["request_id"]
                    or grant.get("task_id") != claim["task_id"]
                    or grant.get("slot") != claim["slot"]
                    or grant.get("runner_id") != claim["runner_id"]
                    or grant.get("attempt") != claim["attempt"]
                    or grant.get("epoch") != claim["epoch"]
                    or grant.get("run_id") != claim["run_id"]
                    or grant.get("service_generation") != claim["service_generation"]
                    or grant.get("manifest_sha256") != claim["manifest_sha256"]):
                raise StoreError("runner execution claim differs from its signed grant", kind="integrity")
            side_events = runner_table_events[grant_id]
            chain_events = runner_chain_events[grant_id]
            states = tuple(event.get("state") for event in side_events)
            if (states not in {
                    ("PENDING",),
                    ("PENDING", "EXECUTION_RESERVED"),
                    ("PENDING", "INDETERMINATE"),
                    ("PENDING", "EXECUTION_RESERVED", "COMPLETE"),
                    ("PENDING", "EXECUTION_RESERVED", "INDETERMINATE"),
                    ("PENDING", "INDETERMINATE", "RECONCILED"),
                    ("PENDING", "EXECUTION_RESERVED", "INDETERMINATE", "RECONCILED"),
                } or len(chain_events) != len(side_events)):
                raise StoreError("runner execution lifecycle event sequence is invalid", kind="integrity")
            for side, chained in zip(side_events, chain_events):
                if (side.get("event") != event_name.get(side.get("state"))
                        or canonical_bytes(side) != canonical_bytes(chained)
                        or side.get("grant_id") != grant_id
                        or side.get("payload_sha256") != claim["payload_sha256"]):
                    raise StoreError("runner execution side event differs from hash-chained event", kind="integrity")
            pending = side_events[0]
            if (pending.get("invocation_id") != claim["invocation_id"]
                    or pending.get("request_id") != claim["request_id"]
                    or pending.get("task_id") != claim["task_id"]
                    or pending.get("slot") != claim["slot"]
                    or pending.get("runner_id") != claim["runner_id"]
                    or pending.get("attempt") != claim["attempt"]
                    or pending.get("epoch") != claim["epoch"]
                    or pending.get("run_id") != claim["run_id"]
                    or pending.get("service_generation") != claim["service_generation"]):
                raise StoreError("runner execution pending event differs from its claim", kind="integrity")
            if len(side_events) >= 2 and side_events[1]["state"] == "EXECUTION_RESERVED":
                reserved = side_events[1]
                if (reserved.get("grant_id") != claim["grant_id"]
                        or reserved.get("payload_sha256") != claim["payload_sha256"]
                        or reserved.get("service_generation") != claim["service_generation"]
                        or reserved.get("invocation_id") != claim["invocation_id"]
                        or reserved.get("request_id") != claim["request_id"]):
                    raise StoreError("execution reservation differs from its claim", kind="integrity")
            terminal = side_events[-1] if len(side_events) > 1 else None
            if terminal is not None and terminal["state"] == "COMPLETE":
                receipt = terminal.get("receipt")
                if (not isinstance(receipt, dict)
                        or receipt_sha256(receipt) != terminal.get("receipt_sha256")):
                    raise StoreError("completed runner receipt digest is invalid", kind="integrity")
            indeterminate_indexes = [
                index for index, event in enumerate(side_events)
                if event["state"] == "INDETERMINATE"
            ]
            if len(indeterminate_indexes) > 1:
                raise StoreError("runner execution has multiple indeterminate transitions", kind="integrity")
            if indeterminate_indexes:
                indeterminate_index = indeterminate_indexes[0]
                indeterminate = side_events[indeterminate_index]
                if indeterminate_index < 1:
                    raise StoreError("indeterminate runner claim lacks its predecessor state", kind="integrity")
                predecessor_state = side_events[indeterminate_index - 1]["state"]
                if indeterminate.get("reason") == RUNNER_PRESPAWN_NO_EXECUTION_REASON:
                    if (predecessor_state != "PENDING"
                            or indeterminate.get("terminal_disposition") != "NO_EXECUTION"
                            or not _valid_runner_prespawn_no_execution_event(indeterminate, claim)):
                        raise StoreError("runner pre-spawn terminal event does not match its claim", kind="integrity")
                elif indeterminate.get("reason") == "PREDECESSOR_GENERATION_STOPPED":
                    expected_index = 1 if predecessor_state == "PENDING" else 2
                    if (indeterminate_index != expected_index
                            or not _valid_predecessor_generation_stopped_event(
                                indeterminate, claim, predecessor_state,
                            )):
                        raise StoreError("indeterminate runner claim lacks a predecessor-generation fence", kind="integrity")
                elif indeterminate.get("reason") == "AUTHORITY_CHANGED_BEFORE_COMPLETION":
                    observed_generation = indeterminate.get("observed_service_generation")
                    if (not isinstance(observed_generation, str) or not observed_generation
                            or predecessor_state != "EXECUTION_RESERVED"
                            or indeterminate.get("predecessor_state") != predecessor_state
                            or "terminal_disposition" in indeterminate
                            or indeterminate_index != 2):
                        raise StoreError("indeterminate runner completion lacks authority evidence", kind="integrity")
                else:
                    raise StoreError("indeterminate runner event has no recognized reason", kind="integrity")
                if terminal is not None and terminal["state"] == "RECONCILED":
                    if indeterminate_index != len(side_events) - 2 or not _valid_runner_execution_resolution(
                        terminal, claim, self._execution_resolution_key,
                        indeterminate.get("predecessor_state"),
                    ):
                        raise StoreError("runner execution reconciliation is invalid or unauthenticated", kind="integrity")
                    resolution_id = terminal["resolution"]["resolution_id"]
                    if resolution_id in runner_resolution_ids:
                        raise StoreError("runner execution resolution id is reused", kind="integrity")
                    runner_resolution_ids.add(resolution_id)
        self._verify_runner_receipt_chains_locked(conn)

    @staticmethod
    def _verify_dispatch_issuance_structure(row: sqlite3.Row, events: list[dict]) -> None:
        """Check issuer journal shape without treating startup as crypto verification."""
        from .dispatch_instruction import validate_dispatch_instruction
        from .dispatch_issuance import ISSUANCE_OPERATION, canonical_sha256, validate_frozen_intent
        if row["operation"] != ISSUANCE_OPERATION:
            raise StoreError("dispatch issuance uses the wrong operation family", kind="integrity")
        try:
            result = json.loads(row["result"])
        except (TypeError, ValueError) as exc:
            raise StoreError("dispatch issuance operation result is malformed", kind="integrity") from exc
        if result != {"_vst_state": "PENDING"}:
            raise StoreError("dispatch issuance operation result is not immutable pending state", kind="integrity")
        types = [event.get("event") for event in events]
        allowed = [
            ["SUPERVISOR_DISPATCH_ISSUANCE_INTENT"],
            ["SUPERVISOR_DISPATCH_ISSUANCE_INTENT", "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED"],
            ["SUPERVISOR_DISPATCH_ISSUANCE_INTENT", "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
             "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED"],
            ["SUPERVISOR_DISPATCH_ISSUANCE_INTENT", "SUPERVISOR_DISPATCH_ISSUANCE_SIGNING_STARTED",
             "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN"],
        ]
        if types not in allowed:
            raise StoreError("dispatch issuance event order or multiplicity is invalid", kind="integrity")
        intent_event = events[0]
        if set(intent_event) != {"event", "type", "operation_key", "operation", "payload_sha256", "intent"}:
            raise StoreError("dispatch issuance intent event fields are invalid", kind="integrity")
        try:
            intent = validate_frozen_intent(intent_event["intent"])
        except Exception as exc:
            raise StoreError("dispatch issuance frozen intent is invalid", kind="integrity") from exc
        key = intent["operation_key"]
        if (intent_event.get("operation_key") != key or intent_event.get("type") != types[0]
                or intent_event.get("operation") != ISSUANCE_OPERATION
                or intent_event.get("payload_sha256") != intent["payload_sha256"]
                or row["operation_key"] != key or row["payload_sha256"] != intent["payload_sha256"]):
            raise StoreError("dispatch issuance intent differs from its operation row", kind="integrity")
        intent_digest = canonical_sha256(intent)
        for event in events[1:]:
            if (event.get("type") != event.get("event") or event.get("operation_key") != key
                    or event.get("intent_sha256") != intent_digest
                    or event.get("unsigned_sha256") != intent["unsigned_sha256"]):
                raise StoreError("dispatch issuance progress event differs from its intent", kind="integrity")
        if len(events) > 1:
            started = events[1]
            if set(started) != {"event", "type", "operation_key", "intent_sha256", "unsigned_sha256"}:
                raise StoreError("dispatch issuance STARTED event fields are invalid", kind="integrity")
        if types[-1] == "SUPERVISOR_DISPATCH_ISSUANCE_UNKNOWN":
            unknown = events[-1]
            if (set(unknown) != {"event", "type", "operation_key", "intent_sha256",
                                 "unsigned_sha256", "error_class"}
                    or not isinstance(unknown["error_class"], str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", unknown["error_class"])):
                raise StoreError("dispatch issuance UNKNOWN event fields are invalid", kind="integrity")
        if types[-1] == "SUPERVISOR_DISPATCH_ISSUANCE_COMPLETED":
            completed = events[-1]
            if set(completed) != {"event", "type", "operation_key", "intent_sha256",
                                  "unsigned_sha256", "envelope", "envelope_sha256"}:
                raise StoreError("dispatch issuance completion event fields are invalid", kind="integrity")
            try:
                envelope = validate_dispatch_instruction(completed["envelope"])
            except Exception as exc:
                raise StoreError("dispatch issuance completion envelope is malformed", kind="integrity") from exc
            unsigned = {name: value for name, value in envelope.items() if name != "signature"}
            if (unsigned != intent["unsigned"]
                    or completed.get("envelope_sha256") != canonical_sha256(envelope)):
                raise StoreError("dispatch issuance completion differs from its frozen unsigned bytes", kind="integrity")
            # Startup validates structure only. A root-owned verifier must bind
            # this envelope and fingerprint before any delegated use.

    def _verify_runner_receipt_chains_locked(self, conn: sqlite3.Connection) -> None:
        """Replay receipt attempt and digest links against verified successor proofs."""
        tips: dict[tuple[str, str], tuple[int, str | None]] = {}
        rows = conn.execute(
            "SELECT task_id, slot, attempt, receipt_sha256, prev_receipt_sha256, body "
            "FROM receipts ORDER BY task_id, slot, seq"
        ).fetchall()
        for row in rows:
            key = (row["task_id"], row["slot"])
            previous_attempt, previous_sha = tips.get(key, (0, None))
            try:
                receipt = json.loads(row["body"])
            except (TypeError, ValueError) as exc:
                raise StoreError("receipt row is malformed during history replay", kind="integrity") from exc
            if (not isinstance(receipt, dict)
                    or receipt.get("task_id") != row["task_id"]
                    or receipt.get("slot") != row["slot"]
                    or receipt.get("attempt") != int(row["attempt"])
                    or receipt_sha256(receipt) != row["receipt_sha256"]
                    or receipt.get("prev_receipt_sha256") != row["prev_receipt_sha256"]
                    or row["prev_receipt_sha256"] != previous_sha):
                raise StoreError("receipt digest chain differs during history replay", kind="integrity")
            expected_attempt = previous_attempt + 1
            if int(row["attempt"]) != expected_attempt:
                persistent_runner_receipt = (
                    receipt.get("receipt_type") == "TestRun"
                    and receipt.get("contract_version") == 2
                    and isinstance(receipt.get("runner_attestation"), dict)
                )
                if (not persistent_runner_receipt
                        or not self._runner_receipt_gap_is_eligible_locked(
                            conn, row["task_id"], row["slot"], previous_attempt,
                            int(row["attempt"]),
                        )):
                    raise StoreError("receipt history contains an ineligible attempt gap", kind="integrity")
            tips[key] = (int(row["attempt"]), row["receipt_sha256"])

    def _sync_external_anchor(self) -> None:
        if self._external_anchor is None:
            return
        try:
            history = self._verified_database_history()
            count, head = history[-1]
            latest = self._external_anchor.read_latest()
            latest_count = -1 if latest is None else latest["count"]
            if latest_count >= len(history):
                raise StoreError("external anchor is ahead of the verified database", kind="integrity")
            if latest is not None and history[latest_count][1] != latest["head"]:
                raise StoreError("database does not extend the external checkpoint", kind="integrity")
            if latest is None:
                if count != 0:
                    raise StoreError("external anchor missing for non-empty database", kind="integrity")
                latest = self._external_anchor.compare_and_append(
                    None, signed_checkpoint(0, GENESIS_HASH, self._event_key)
                )
                latest_count = 0
            for checkpoint_count in range(latest_count + 1, count + 1):
                checkpoint = signed_checkpoint(
                    checkpoint_count, history[checkpoint_count][1], self._event_key
                )
                latest = self._external_anchor.compare_and_append(latest, checkpoint)
        except AnchorError as exc:
            raise StoreError(str(exc), kind="integrity") from exc

    def startup_reconcile(self) -> None:
        """Reconcile DB and external anchor while excluding concurrent operations."""
        if self._external_anchor is None:
            self._startup_reconcile_locked()
            return
        with self._external_anchor.transaction_lock():
            self._startup_reconcile_locked()

    def _startup_reconcile_locked(self) -> None:
        """Verify the DB and external checkpoint before any lease or gate action.

        Any valid contiguous event suffix may be re-anchored after a crash. A
        missing anchor with existing events is never reconstructed.
        """
        try:
            history = self._verified_database_history()
            count, head = history[-1]
            if self._external_anchor is None:
                with self._read_tx_locked() as conn:
                    self._dispatch_outcome_state_locked(conn)
                self._reconciliation_complete = True
                self._integrity_locked = False
                self._integrity_lock_reason = None
                return
            latest = self._external_anchor.read_latest()
            if latest is None:
                if count != 0 or head != GENESIS_HASH:
                    raise StoreError("external anchor missing for non-empty database", kind="integrity")
                latest = self._external_anchor.compare_and_append(
                    None, signed_checkpoint(0, GENESIS_HASH, self._event_key)
                )
            if latest["count"] >= len(history) or history[latest["count"]][1] != latest["head"]:
                raise StoreError("database does not extend the external checkpoint", kind="integrity")
            for checkpoint_count in range(latest["count"] + 1, count + 1):
                checkpoint = signed_checkpoint(
                    checkpoint_count, history[checkpoint_count][1], self._event_key
                )
                latest = self._external_anchor.compare_and_append(latest, checkpoint)
            with self._read_tx_locked() as conn:
                self._dispatch_outcome_state_locked(conn)
            self._reconciliation_complete = True
            self._integrity_locked = False
            self._integrity_lock_reason = None
            if self._startup_supervisor_key is not None:
                self.supervisor_reap_and_mark(
                    self._startup_supervisor_key, self._startup_supervisor_runner_id
                )
        except AnchorError as exc:
            self._integrity_locked = True
            self._reconciliation_complete = False
            raise StoreError(str(exc), kind="integrity") from exc
        except StoreError:
            self._integrity_locked = True
            self._reconciliation_complete = False
            raise

    def execute_idempotent(
        self, operation_key: str, operation: str, payload: Any,
        effect: Callable[[sqlite3.Connection], Any],
        *, before_commit: Callable[[sqlite3.Connection, Any], None] | None = None,
        on_replay: Callable[[sqlite3.Connection, Any], None] | None = None,
    ) -> Any:
        """Run an internal Store effect atomically with its idempotency record.

        The callback executes under the SQLite transaction and anchor lock. Do not
        pass a backend, process, network, or other external side effect here.
        """
        _need_str(operation_key, "operation_key")
        _need_str(operation, "operation")
        payload_digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        with self._tx() as conn:
            row = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key = ?",
                (operation_key,),
            ).fetchone()
            if row is not None:
                if row["operation"] != operation or row["payload_sha256"] != payload_digest:
                    raise StoreError("idempotency key reused with different operation or payload", kind="duplicate")
                result = json.loads(row["result"])
                if on_replay is not None:
                    on_replay(conn, result)
                return result
            result = effect(conn)
            try:
                encoded = canonical_bytes(result).decode("utf-8")
            except (TypeError, ValueError) as exc:
                raise StoreError("supervisor operation result is not canonical JSON", kind="argument") from exc
            conn.execute(
                "INSERT INTO supervisor_operations(operation_key, operation, payload_sha256, result) VALUES (?, ?, ?, ?)",
                (operation_key, operation, payload_digest, encoded),
            )
            self._record_event_locked(
                conn, operation_key, "supervisor", "NOTE",
                {
                    "event": "SUPERVISOR_OPERATION", "operation": operation,
                    "payload_sha256": payload_digest,
                    "result_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                },
            )
            if before_commit is not None:
                before_commit(conn, result)
            return result

    def lookup_idempotent_operation(
        self,
        operation_key: str,
        *,
        operation: str | None = None,
        payload: Any = None,
        check_payload: bool = False,
        validate_result: Callable[[sqlite3.Connection, Any], None] | None = None,
    ) -> dict | None:
        """Read a durable operation result and its completion/uncertainty state.

        Supplying ``operation`` and setting ``check_payload`` binds the lookup to
        the exact operation and canonical payload digest. External operations
        remain PENDING until a matching completion is recorded; an unresolved
        external failure is reported as INCONCLUSIVE, never as success.
        """
        _need_str(operation_key, "operation_key")
        if operation is not None:
            _need_str(operation, "operation")
        if check_payload and operation is None:
            raise StoreError("payload-bound operation lookup requires an operation", kind="argument")
        expected_digest = hashlib.sha256(canonical_bytes(payload)).hexdigest() if check_payload else None
        if not self.verify_event_chain():
            raise StoreError("event chain failed verification during operation lookup", kind="integrity")
        with self._read_tx() as conn:
            row = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key = ?",
                (operation_key,),
            ).fetchone()
            if row is None:
                return None
            if operation is not None and row["operation"] != operation:
                raise StoreError("idempotency key reused for a different operation", kind="duplicate")
            if expected_digest is not None and row["payload_sha256"] != expected_digest:
                raise StoreError("idempotency key reused with different payload", kind="duplicate")
            try:
                stored_result = json.loads(row["result"])
            except (TypeError, ValueError) as exc:
                raise StoreError("stored idempotent operation result is invalid", kind="integrity") from exc
            pending = {"_vst_state": "PENDING"}
            if row["result"] != canonical_bytes(pending).decode("utf-8"):
                if validate_result is not None:
                    validate_result(conn, stored_result)
                return {
                    "operation": row["operation"],
                    "payload_sha256": row["payload_sha256"],
                    "state": "COMPLETED",
                    "result": stored_result,
                }

            completed = None
            inconclusive = False
            error_types: list[str] = []
            rows = conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND actor = 'supervisor' AND kind = 'NOTE' ORDER BY seq",
                (operation_key,),
            ).fetchall()
            for event_row in rows:
                try:
                    event = json.loads(event_row["payload"])
                except (TypeError, ValueError) as exc:
                    raise StoreError("stored operation event is invalid", kind="integrity") from exc
                if event.get("operation_key") != operation_key:
                    continue
                if event.get("event") == "SUPERVISOR_EXTERNAL_OPERATION_UNKNOWN":
                    if (event.get("operation") != row["operation"]
                            or event.get("payload_sha256") != row["payload_sha256"]):
                        raise StoreError("external operation uncertainty binding is invalid", kind="integrity")
                    inconclusive = True
                    error_type = event.get("error_type")
                    if isinstance(error_type, str) and error_type not in error_types:
                        error_types.append(error_type)
                elif event.get("event") == "SUPERVISOR_EXTERNAL_OPERATION_COMPLETED":
                    if (event.get("operation") != row["operation"]
                            or event.get("payload_sha256") != row["payload_sha256"]):
                        raise StoreError("external operation completion binding is invalid", kind="integrity")
                    result = event.get("result")
                    encoded = canonical_bytes(result).decode("utf-8")
                    if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != event.get("result_sha256"):
                        raise StoreError("external operation result digest is invalid", kind="integrity")
                    if completed is not None and canonical_bytes(completed) != canonical_bytes(result):
                        raise StoreError("external operation has conflicting completion records", kind="integrity")
                    completed = result
            if completed is not None:
                if validate_result is not None:
                    validate_result(conn, completed)
                return {
                    "operation": row["operation"],
                    "payload_sha256": row["payload_sha256"],
                    "state": "COMPLETED",
                    "result": completed,
                }
            return {
                "operation": row["operation"],
                "payload_sha256": row["payload_sha256"],
                "state": "INCONCLUSIVE" if inconclusive else "PENDING",
                "result": None,
                "error_types": error_types,
            }

    def _runner_execution_states_locked(self, conn: sqlite3.Connection, grant_id: str) -> list[dict]:
        rows = conn.execute(
            "SELECT state, payload FROM runner_execution_events WHERE grant_id = ? ORDER BY seq",
            (grant_id,),
        ).fetchall()
        states = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except (TypeError, ValueError) as exc:
                raise StoreError("runner execution event is malformed", kind="integrity") from exc
            if not isinstance(payload, dict) or payload.get("state") != row["state"]:
                raise StoreError("runner execution event state is inconsistent", kind="integrity")
            states.append(payload)
        if not states or states[0].get("state") != "PENDING":
            raise StoreError("runner execution record lacks its PENDING claim", kind="integrity")
        sequence = tuple(state.get("state") for state in states)
        if sequence not in {
                ("PENDING",),
                ("PENDING", "EXECUTION_RESERVED"),
                ("PENDING", "INDETERMINATE"),
                ("PENDING", "EXECUTION_RESERVED", "COMPLETE"),
                ("PENDING", "EXECUTION_RESERVED", "INDETERMINATE"),
                ("PENDING", "INDETERMINATE", "RECONCILED"),
                ("PENDING", "EXECUTION_RESERVED", "INDETERMINATE", "RECONCILED"),
        }:
            raise StoreError("runner execution lifecycle is invalid", kind="integrity")
        indeterminate_indexes = [
            index for index, state in enumerate(states)
            if state.get("state") == "INDETERMINATE"
        ]
        if len(indeterminate_indexes) > 1:
            raise StoreError("runner execution has multiple indeterminate transitions", kind="integrity")
        claim = None
        if indeterminate_indexes:
            indeterminate_index = indeterminate_indexes[0]
            if indeterminate_index < 1:
                raise StoreError("indeterminate runner claim lacks its predecessor state", kind="integrity")
            claim = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (grant_id,)
            ).fetchone()
            indeterminate = states[indeterminate_index]
            predecessor_state = states[indeterminate_index - 1]["state"]
            reason = indeterminate.get("reason")
            if reason == RUNNER_PRESPAWN_NO_EXECUTION_REASON:
                if (claim is None or indeterminate_index != 1 or predecessor_state != "PENDING"
                        or not _valid_runner_prespawn_no_execution_event(indeterminate, claim)):
                    raise StoreError("runner pre-spawn terminal event does not match its claim", kind="integrity")
            elif reason == "PREDECESSOR_GENERATION_STOPPED":
                expected_index = 1 if predecessor_state == "PENDING" else 2
                if (claim is None or indeterminate_index != expected_index
                        or not _valid_predecessor_generation_stopped_event(
                            indeterminate, claim, predecessor_state,
                        )):
                    raise StoreError("indeterminate runner claim lacks a predecessor-generation fence", kind="integrity")
            elif reason == "AUTHORITY_CHANGED_BEFORE_COMPLETION":
                observed_generation = indeterminate.get("observed_service_generation")
                if (indeterminate_index != 2 or predecessor_state != "EXECUTION_RESERVED"
                        or indeterminate.get("predecessor_state") != predecessor_state
                        or not isinstance(observed_generation, str) or not observed_generation
                        or "terminal_disposition" in indeterminate):
                    raise StoreError("runner execution completion lacks authority evidence", kind="integrity")
            else:
                raise StoreError("indeterminate runner event has no recognized reason", kind="integrity")

        if states[-1]["state"] == "RECONCILED":
            indeterminate = states[-2]
            predecessor_state = indeterminate.get("predecessor_state")
            if (claim is None or indeterminate.get("state") != "INDETERMINATE"
                    or not _valid_runner_execution_resolution(
                        states[-1], claim, self._execution_resolution_key, predecessor_state,
                    )):
                raise StoreError("runner execution resolution is invalid or unauthenticated", kind="integrity")
        return states

    def _runner_attempt_successor_eligibility_locked(
        self, conn: sqlite3.Connection, task_id: str, slot: str, attempt: int,
    ) -> str | None:
        """Return the verified terminal disposition that permits a successor attempt.

        The evidence is bound to one exact claim and its lease identity. Reconciled
        EFFECTS_RESOLVED is eligible only from EXECUTION_RESERVED and only after
        validating the signed resolution record; generic INDETERMINATE and other
        signed outcomes never authorize a successor.
        """
        claim = conn.execute(
            "SELECT * FROM runner_execution_claims WHERE task_id = ? AND slot = ? AND attempt = ?",
            (task_id, slot, attempt),
        ).fetchone()
        if claim is None:
            return None
        lease = conn.execute(
            "SELECT epoch, worker_id FROM leases WHERE task_id = ? AND attempt = ?",
            (task_id, attempt),
        ).fetchone()
        if (lease is None or int(lease["epoch"]) != int(claim["epoch"])
                or lease["worker_id"] != claim["runner_id"]):
            return None
        states = self._runner_execution_states_locked(conn, claim["grant_id"])
        terminal = states[-1]
        if (terminal["state"] == "INDETERMINATE"
                and terminal.get("predecessor_state") == "PENDING"
                and _valid_runner_prespawn_no_execution_event(terminal, claim)):
            return "NO_EXECUTION_PROVEN"
        if terminal["state"] != "RECONCILED":
            return None
        predecessor_state = terminal.get("predecessor_state")
        if not _valid_runner_execution_resolution(
                terminal, claim, self._execution_resolution_key, predecessor_state):
            return None
        resolution = terminal.get("resolution")
        if (resolution.get("outcome") == "NO_EXECUTION_PROVEN"
                and predecessor_state == "PENDING"):
            return "NO_EXECUTION_PROVEN"
        if (resolution.get("outcome") == "EFFECTS_RESOLVED"
                and predecessor_state == "EXECUTION_RESERVED"):
            return "EFFECTS_RESOLVED"
        return None

    def _verified_runner_successor_attempts_locked(
        self, conn: sqlite3.Connection, task_id: str, slot: str, through_attempt: int,
    ) -> set[int]:
        return {
            attempt for attempt in range(1, through_attempt + 1)
            if self._runner_attempt_successor_eligibility_locked(conn, task_id, slot, attempt)
        }

    def _runner_receipt_gap_is_eligible_locked(
        self, conn: sqlite3.Connection, task_id: str, slot: str,
        previous_receipt_attempt: int, successor_attempt: int,
    ) -> bool:
        """Verify each missing attempt between this receipt tip and its successor."""
        if successor_attempt <= previous_receipt_attempt:
            return False
        if successor_attempt == previous_receipt_attempt + 1:
            return True
        return all(
            self._runner_attempt_successor_eligibility_locked(conn, task_id, slot, attempt) is not None
            for attempt in range(previous_receipt_attempt + 1, successor_attempt)
        )

    def _guard_runner_task_continuation_locked(
        self, conn: sqlite3.Connection, task_id: str, *,
        reservation_grant_id: str | None = None,
    ) -> None:
        """Block successors until every earlier execution has verified successor eligibility."""
        claims = conn.execute(
            "SELECT grant_id, task_id, slot, attempt FROM runner_execution_claims WHERE task_id = ? ORDER BY attempt",
            (task_id,),
        ).fetchall()
        for claim_row in claims:
            states = self._runner_execution_states_locked(conn, claim_row["grant_id"])
            state = states[-1]["state"]
            # Only reserve_runner_execution supplies this identity, after matching
            # the entire persisted claim and proving its sole state is PENDING.
            # It is this execution, not a predecessor or permission to reclaim it.
            if (claim_row["grant_id"] == reservation_grant_id
                    and len(states) == 1 and state == "PENDING"):
                continue
            if state == "COMPLETE":
                continue
            if self._runner_attempt_successor_eligibility_locked(
                    conn, claim_row["task_id"], claim_row["slot"], int(claim_row["attempt"])):
                continue
            raise StoreError(
                f"prior runner execution {claim_row['grant_id']!r} is {state} and blocks continuation",
                kind="lifecycle",
            )

    def completed_runner_execution_receipt(self, grant: dict) -> dict | None:
        """Return an exact historical COMPLETE receipt without granting execution authority."""
        from .execution_grant import validate_execution_grant
        valid = validate_execution_grant(grant)
        digest = hashlib.sha256(canonical_bytes(valid)).hexdigest()
        with self._read_tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            row = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id=?", (valid["grant_id"],),
            ).fetchone()
            if row is None or row["payload_sha256"] != digest:
                return None
            try:
                stored = json.loads(row["grant_body"])
            except (TypeError, ValueError) as exc:
                raise StoreError("stored runner grant is malformed", kind="integrity") from exc
            if canonical_bytes(stored) != canonical_bytes(valid):
                return None
            states = self._runner_execution_states_locked(conn, valid["grant_id"])
            terminal = states[-1]
            if terminal["state"] != "COMPLETE":
                return None
            self._maybe_validate_delegated_execution_grant_locked(
                conn, grant=valid, proof=None,
                generation=valid["service_generation"], current=False,
            )
            receipt = terminal.get("receipt")
            if not isinstance(receipt, dict):
                raise StoreError("completed runner receipt is missing", kind="integrity")
            return dict(receipt)

    def claim_runner_execution(
        self, grant: dict, *, active_service_generation: str,
        dispatch_issuance_proof: Any = None,
        authority_guard: Callable[[], bool] | None = None,
    ) -> dict | None:
        """Atomically recheck current Store authority and claim a grant as PENDING.

        The authenticated Supervisor IPC is the authorization boundary for this
        method. Its caller must provide the generation obtained from the trusted
        lifecycle fence, not from the runner request. This method does not verify
        Ed25519; the daemon verifies the signature and the Store independently
        rechecks every current task/lease/preflight/budget fence before child
        creation.

        Returns None for a newly claimed run, or the exact stored receipt for a
        duplicate COMPLETE grant. PENDING, EXECUTION_RESERVED, INDETERMINATE,
        and RECONCILED grants are never replayed or reclaimed.
        """
        if not self.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before runner admission", kind="integrity")
        if not self.verify_event_chain():
            raise StoreError("event chain failed verification before runner admission", kind="integrity")
        from .execution_grant import MAX_EXECUTION_DEADLINE_SEC, validate_execution_grant

        try:
            valid = validate_execution_grant(grant)
        except Exception as exc:
            raise StoreError("execution grant is malformed", kind="authorization") from exc
        _need_str(active_service_generation, "active_service_generation")
        if valid["service_generation"] != active_service_generation:
            raise StoreError("execution grant belongs to a stale service generation", kind="authorization")
        grant_bytes = canonical_bytes(valid)
        grant_digest = hashlib.sha256(grant_bytes).hexdigest()
        with self._tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            now = self._now()
            collision = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ? OR invocation_id = ? "
                "OR request_id = ? OR (task_id = ? AND slot = ? AND attempt = ?)",
                (valid["grant_id"], valid["invocation_id"], valid["request_id"],
                 valid["task_id"], valid["slot"], valid["attempt"]),
            ).fetchone()
            if collision is not None:
                identity_matches = (
                    collision["grant_id"] == valid["grant_id"]
                    and collision["invocation_id"] == valid["invocation_id"]
                    and collision["request_id"] == valid["request_id"]
                    and collision["task_id"] == valid["task_id"]
                    and collision["runner_id"] == valid["runner_id"]
                    and collision["run_id"] == valid["run_id"]
                    and collision["slot"] == valid["slot"]
                    and int(collision["attempt"]) == valid["attempt"]
                    and collision["payload_sha256"] == grant_digest
                )
                if not identity_matches:
                    raise StoreError("execution grant, invocation, request, or attempt was already claimed", kind="duplicate")
                states = self._runner_execution_states_locked(conn, valid["grant_id"])
                terminal = states[-1]
                self._maybe_validate_delegated_execution_grant_locked(
                    conn, grant=valid, proof=dispatch_issuance_proof,
                    generation=active_service_generation,
                    current=terminal["state"] != "COMPLETE",
                    authority_guard=authority_guard,
                )
                if terminal["state"] == "COMPLETE":
                    receipt = terminal.get("receipt")
                    if not isinstance(receipt, dict):
                        raise StoreError("completed runner receipt is missing", kind="integrity")
                    return dict(receipt)
                raise StoreError(f"execution grant is non-replayable ({terminal['state']})", kind="lifecycle")

            self._maybe_validate_delegated_execution_grant_locked(
                conn, grant=valid, proof=dispatch_issuance_proof,
                generation=active_service_generation, current=True,
                authority_guard=authority_guard,
            )

            if (valid["issued_at"] > now + 5.0 or valid["claim_expires_at"] <= now
                    or valid["expires_at"] <= now):
                raise StoreError("execution grant claim window or run deadline expired", kind="authorization")

            task = self._task_row(conn, valid["task_id"])
            self._guard_runner_task_continuation_locked(conn, valid["task_id"])
            story = self._story_row(conn, task["story_id"])
            if (int(story["epoch"]) != valid["epoch"] or story["state"] != "OWNED"
                    or story["owner"] is None or story["owner_expires_at"] is None
                    or float(story["owner_expires_at"]) <= now):
                raise StoreError("execution grant has no current live story owner/epoch", kind="epoch")
            manifest = json.loads(task["manifest"])
            if (task["manifest_sha256"] != valid["manifest_sha256"]
                    or manifest_sha256(manifest) != valid["manifest_sha256"]):
                raise StoreError("execution grant manifest is no longer registered", kind="manifest")
            declared_slots = {
                entry["slot"]: entry["receipt_type"] for entry in manifest["required_receipts"]
            }
            if declared_slots.get(valid["slot"]) != "TestRun":
                raise StoreError("execution grant slot is not a manifest TestRun slot", kind="slot")
            if (int(manifest["timeout_sec"]) > MAX_EXECUTION_DEADLINE_SEC
                    or valid["execution_deadline_sec"] != int(manifest["timeout_sec"])):
                raise StoreError("execution grant does not cover the full manifest run window", kind="authorization")
            lease = conn.execute(
                "SELECT epoch, status, expires_at, worker_id FROM leases WHERE task_id = ? AND attempt = ?",
                (valid["task_id"], valid["attempt"]),
            ).fetchone()
            if (lease is None or int(lease["epoch"]) != valid["epoch"]
                    or lease["status"] != LEASE_LIVE or float(lease["expires_at"]) <= now
                    or lease["worker_id"] != valid["runner_id"]):
                raise StoreError("execution grant has no current live lease", kind="lease")
            authority_expires_at = min(
                float(story["owner_expires_at"]), float(lease["expires_at"]),
            )
            if authority_expires_at - now < (
                    valid["execution_deadline_sec"] + RUNNER_AUTHORITY_COMPLETION_MARGIN_SEC):
                raise StoreError("execution grant exceeds the remaining owner/lease authority window", kind="authorization")
            last_receipt = conn.execute(
                "SELECT attempt FROM receipts WHERE task_id = ? AND slot = ? ORDER BY attempt DESC LIMIT 1",
                (valid["task_id"], valid["slot"]),
            ).fetchone()
            previous_receipt_attempt = 0 if last_receipt is None else int(last_receipt["attempt"])
            if not self._runner_receipt_gap_is_eligible_locked(
                    conn, valid["task_id"], valid["slot"], previous_receipt_attempt, valid["attempt"]):
                raise StoreError("receipt attempt gap lacks a verified successor disposition", kind="chain")
            if conn.execute(
                "SELECT 1 FROM receipts WHERE task_id = ? AND slot = ? AND attempt = ?",
                (valid["task_id"], valid["slot"], valid["attempt"]),
            ).fetchone() is not None:
                raise StoreError("execution attempt already has a receipt", kind="duplicate")
            if conn.execute(
                "SELECT 1 FROM supervisor_probes WHERE run_id = ?", (valid["run_id"],)
            ).fetchone() is None:
                raise StoreError("execution grant has no consumed run-bound preflight", kind="probe")
            blocked = self._budget_block_locked(conn, valid["task_id"])
            if blocked is not None:
                raise StoreError(blocked, kind="budget")
            try:
                conn.execute(
                    "INSERT INTO runner_execution_claims "
                    "(grant_id, invocation_id, request_id, task_id, slot, runner_id, attempt, epoch, run_id, "
                    "service_generation, manifest_sha256, payload_sha256, grant_body, claimed_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (valid["grant_id"], valid["invocation_id"], valid["request_id"],
                     valid["task_id"], valid["slot"], valid["runner_id"],
                     valid["attempt"], valid["epoch"], valid["run_id"],
                     valid["service_generation"], valid["manifest_sha256"], grant_digest,
                     grant_bytes.decode("utf-8"), now),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreError("execution grant identity was concurrently claimed", kind="duplicate") from exc
            event = {
                "event": "RUNNER_EXECUTION_PENDING", "state": "PENDING",
                "grant_id": valid["grant_id"], "invocation_id": valid["invocation_id"],
                "request_id": valid["request_id"], "task_id": valid["task_id"],
                "slot": valid["slot"], "runner_id": valid["runner_id"], "attempt": valid["attempt"],
                "epoch": valid["epoch"], "service_generation": valid["service_generation"],
                "run_id": valid["run_id"],
                "payload_sha256": grant_digest,
            }
            conn.execute(
                "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
                "VALUES (?, 'PENDING', ?, ?)",
                (valid["grant_id"], canonical_bytes(event).decode("utf-8"), now),
            )
            self._record_event_locked(conn, valid["grant_id"], "supervisor", "NOTE", event)
        return None

    def mark_runner_prespawn_no_execution(
        self, grant: dict, *, active_service_generation: str, reason_code: str,
    ) -> dict:
        """Terminalize an exact PENDING claim after the runner proves no spawn occurred.

        This is only called by the authenticated runner daemon. Child creation is
        impossible before EXECUTION_RESERVED, so a still-PENDING claim is a
        conclusive pre-spawn state. The transaction rejects any concurrent or
        previously committed reservation.
        """
        from .execution_grant import validate_execution_grant

        try:
            valid = validate_execution_grant(grant)
        except Exception as exc:
            raise StoreError("execution grant is malformed", kind="authorization") from exc
        _need_str(active_service_generation, "active_service_generation")
        if valid["service_generation"] != active_service_generation:
            raise StoreError("execution claim belongs to a different service generation", kind="authorization")
        if (not isinstance(reason_code, str)
                or reason_code not in RUNNER_PRESPAWN_REASON_CODES):
            raise StoreError("runner pre-spawn reason code is not recognized", kind="argument")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for pre-spawn terminalization", kind="integrity")
        digest = hashlib.sha256(canonical_bytes(valid)).hexdigest()
        with self._tx() as conn:
            claim = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (valid["grant_id"],)
            ).fetchone()
            if (claim is None or claim["payload_sha256"] != digest
                    or claim["service_generation"] != active_service_generation
                    or claim["request_id"] != valid["request_id"]
                    or claim["invocation_id"] != valid["invocation_id"]
                    or claim["task_id"] != valid["task_id"]
                    or claim["slot"] != valid["slot"]
                    or int(claim["attempt"]) != valid["attempt"]
                    or int(claim["epoch"]) != valid["epoch"]
                    or claim["run_id"] != valid["run_id"]):
                raise StoreError("pre-spawn terminalization does not match the exact claim", kind="integrity")
            states = self._runner_execution_states_locked(conn, valid["grant_id"])
            if len(states) != 1 or states[0]["state"] != "PENDING":
                raise StoreError("claim is no longer an unreserved PENDING execution", kind="lifecycle")
            event = {
                "event": "RUNNER_EXECUTION_INDETERMINATE", "state": "INDETERMINATE",
                "grant_id": claim["grant_id"], "payload_sha256": claim["payload_sha256"],
                "reason": RUNNER_PRESPAWN_NO_EXECUTION_REASON,
                "terminal_disposition": "NO_EXECUTION",
                "reason_code": reason_code, "predecessor_state": "PENDING",
                "request_id": claim["request_id"], "invocation_id": claim["invocation_id"],
                "task_id": claim["task_id"], "slot": claim["slot"],
                "runner_id": claim["runner_id"], "attempt": int(claim["attempt"]),
                "epoch": int(claim["epoch"]), "run_id": claim["run_id"],
                "service_generation": claim["service_generation"],
            }
            conn.execute(
                "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
                "VALUES (?, 'INDETERMINATE', ?, ?)",
                (valid["grant_id"], canonical_bytes(event).decode("utf-8"), self._now()),
            )
            self._record_event_locked(conn, valid["grant_id"], "supervisor", "NOTE", event)
        return {
            "state": "NO_EXECUTION", "grant_id": valid["grant_id"],
            "payload_sha256": digest, "service_generation": active_service_generation,
        }

    def verify_pending_runner_execution(
        self, grant: dict, *, active_service_generation: str,
    ) -> bool:
        """Read-only signer-side check that a grant is pending/reserved and current."""
        from .execution_grant import validate_execution_grant

        try:
            valid = validate_execution_grant(grant)
        except Exception as exc:
            raise StoreError("execution grant is malformed", kind="authorization") from exc
        _need_str(active_service_generation, "active_service_generation")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for signer admission", kind="integrity")
        now = self._now()
        with self._read_tx() as conn:
            row = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (valid["grant_id"],)
            ).fetchone()
            if row is None:
                return False
            digest = hashlib.sha256(canonical_bytes(valid)).hexdigest()
            if (row["payload_sha256"] != digest
                    or row["service_generation"] != active_service_generation
                    or valid["service_generation"] != active_service_generation
                    or valid["expires_at"] <= now
                    or float(row["claimed_at"]) > float(valid["claim_expires_at"])
                    or valid["issued_at"] > now + 5.0):
                return False
            states = self._runner_execution_states_locked(conn, valid["grant_id"])
            if states[-1]["state"] not in {"PENDING", "EXECUTION_RESERVED"}:
                return False
            task = self._task_row(conn, valid["task_id"])
            story = self._story_row(conn, task["story_id"])
            lease = conn.execute(
                "SELECT epoch, status, expires_at, worker_id FROM leases "
                "WHERE task_id = ? AND attempt = ?",
                (valid["task_id"], valid["attempt"]),
            ).fetchone()
            return not (
                int(story["epoch"]) != valid["epoch"] or story["state"] != "OWNED"
                or story["owner"] is None or story["owner_expires_at"] is None
                or float(story["owner_expires_at"]) <= now
                or lease is None or int(lease["epoch"]) != valid["epoch"]
                or lease["status"] != LEASE_LIVE or float(lease["expires_at"]) <= now
                or lease["worker_id"] != valid["runner_id"]
                or min(float(story["owner_expires_at"]), float(lease["expires_at"])) - now < (
                    valid["execution_deadline_sec"] + RUNNER_AUTHORITY_COMPLETION_MARGIN_SEC
                )
                or self._budget_block_locked(conn, valid["task_id"]) is not None
            )

    def runner_execution_claim_status(
        self, grant: dict, *, active_service_generation: str,
    ) -> dict:
        """Return state only for this exact grant under its original live generation."""
        from .execution_grant import validate_execution_grant

        try:
            valid = validate_execution_grant(grant)
        except Exception as exc:
            raise StoreError("execution grant is malformed", kind="authorization") from exc
        _need_str(active_service_generation, "active_service_generation")
        if valid["service_generation"] != active_service_generation:
            raise StoreError("execution claim belongs to a different service generation", kind="authorization")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for claim status", kind="integrity")
        digest = hashlib.sha256(canonical_bytes(valid)).hexdigest()
        with self._read_tx() as conn:
            row = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (valid["grant_id"],)
            ).fetchone()
            if row is None:
                return {"state": "NOT_FOUND", "service_generation": active_service_generation}
            if (row["payload_sha256"] != digest
                    or row["service_generation"] != active_service_generation
                    or row["invocation_id"] != valid["invocation_id"]
                    or row["request_id"] != valid["request_id"]
                    or row["task_id"] != valid["task_id"]
                    or row["slot"] != valid["slot"]
                    or int(row["attempt"]) != valid["attempt"]):
                raise StoreError("execution claim status does not match the exact grant", kind="integrity")
            states = self._runner_execution_states_locked(conn, valid["grant_id"])
            if states[-1]["state"] == "PENDING":
                now = self._now()
                if (valid["expires_at"] <= now
                        or now + valid["execution_deadline_sec"] > valid["expires_at"]):
                    raise StoreError(
                        "pending execution claim is no longer recoverable within its signed run window",
                        kind="authorization",
                    )
            result = {"state": states[-1]["state"], "service_generation": row["service_generation"]}
            if (states[-1]["state"] == "INDETERMINATE"
                    and states[-1].get("reason") == RUNNER_PRESPAWN_NO_EXECUTION_REASON):
                result["reason_code"] = states[-1]["reason_code"]
            if states[-1]["state"] == "COMPLETE":
                receipt = states[-1].get("receipt")
                if not isinstance(receipt, dict):
                    raise StoreError("completed runner receipt is missing", kind="integrity")
                result["receipt"] = dict(receipt)
            return result

    def reserve_runner_execution(
        self, grant: dict, *, active_service_generation: str,
        dispatch_issuance_proof: Any = None,
        authority_guard: Callable[[], bool] | None = None,
    ) -> dict:
        """Atomically reserve the one permitted launch after rechecking authority."""
        from .execution_grant import MAX_EXECUTION_DEADLINE_SEC, validate_execution_grant

        try:
            valid = validate_execution_grant(grant)
        except Exception as exc:
            raise StoreError("execution grant is malformed", kind="authorization") from exc
        _need_str(active_service_generation, "active_service_generation")
        if valid["service_generation"] != active_service_generation:
            raise StoreError("execution grant belongs to a stale service generation", kind="authorization")
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for execution reservation", kind="integrity")
        digest = hashlib.sha256(canonical_bytes(valid)).hexdigest()
        with self._tx() as conn:
            self._verify_event_chain_locked(conn)
            self._verify_supervisor_records(conn)
            now = self._now()
            row = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (valid["grant_id"],)
            ).fetchone()
            if (row is None or row["payload_sha256"] != digest
                    or row["service_generation"] != active_service_generation
                    or row["invocation_id"] != valid["invocation_id"]
                    or row["request_id"] != valid["request_id"]
                    or row["task_id"] != valid["task_id"]
                    or row["slot"] != valid["slot"]
                    or int(row["attempt"]) != valid["attempt"]):
                raise StoreError("execution reservation does not match the exact claimed grant", kind="integrity")
            states = self._runner_execution_states_locked(conn, valid["grant_id"])
            if len(states) != 1 or states[0]["state"] != "PENDING":
                raise StoreError("execution grant is not an unreserved PENDING claim", kind="lifecycle")
            self._maybe_validate_delegated_execution_grant_locked(
                conn, grant=valid, proof=dispatch_issuance_proof,
                generation=active_service_generation, current=True,
                authority_guard=authority_guard,
                reservation_grant_id=valid["grant_id"],
            )
            if (valid["issued_at"] > now + 5.0 or valid["expires_at"] <= now
                    or now + valid["execution_deadline_sec"] > valid["expires_at"]
                    or valid["execution_deadline_sec"] > MAX_EXECUTION_DEADLINE_SEC):
                raise StoreError("execution grant lacks its full bounded run window at reservation", kind="authorization")
            task = self._task_row(conn, valid["task_id"])
            story = self._story_row(conn, task["story_id"])
            if (task["manifest_sha256"] != valid["manifest_sha256"]
                    or manifest_sha256(json.loads(task["manifest"])) != valid["manifest_sha256"]):
                raise StoreError("execution grant manifest is no longer registered", kind="manifest")
            manifest = json.loads(task["manifest"])
            declared_slots = {
                entry["slot"]: entry["receipt_type"] for entry in manifest["required_receipts"]
            }
            if (declared_slots.get(valid["slot"]) != "TestRun"
                    or int(manifest["timeout_sec"]) > MAX_EXECUTION_DEADLINE_SEC
                    or valid["execution_deadline_sec"] != int(manifest["timeout_sec"])):
                raise StoreError("execution grant no longer matches its manifest run contract", kind="authorization")
            if (int(story["epoch"]) != valid["epoch"] or story["state"] != "OWNED"
                    or story["owner"] is None or story["owner_expires_at"] is None
                    or float(story["owner_expires_at"]) <= now):
                raise StoreError("execution grant has no current live story owner/epoch", kind="epoch")
            lease = conn.execute(
                "SELECT epoch, status, expires_at, worker_id FROM leases "
                "WHERE task_id = ? AND attempt = ?", (valid["task_id"], valid["attempt"]),
            ).fetchone()
            if (lease is None or int(lease["epoch"]) != valid["epoch"]
                    or lease["status"] != LEASE_LIVE or float(lease["expires_at"]) <= now
                    or lease["worker_id"] != valid["runner_id"]):
                raise StoreError("execution grant has no current live lease", kind="lease")
            authority_expires_at = min(
                float(story["owner_expires_at"]), float(lease["expires_at"]),
            )
            if authority_expires_at - now < (
                    valid["execution_deadline_sec"] + RUNNER_AUTHORITY_COMPLETION_MARGIN_SEC):
                raise StoreError("execution reservation exceeds the remaining owner/lease authority window", kind="authorization")
            last_receipt = conn.execute(
                "SELECT attempt FROM receipts WHERE task_id = ? AND slot = ? ORDER BY attempt DESC LIMIT 1",
                (valid["task_id"], valid["slot"]),
            ).fetchone()
            previous_receipt_attempt = 0 if last_receipt is None else int(last_receipt["attempt"])
            if not self._runner_receipt_gap_is_eligible_locked(
                    conn, valid["task_id"], valid["slot"], previous_receipt_attempt, valid["attempt"]):
                raise StoreError("receipt attempt gap lacks a verified successor disposition", kind="chain")
            if self._budget_block_locked(conn, valid["task_id"]) is not None:
                raise StoreError("execution budget is blocked before launch reservation", kind="budget")
            event = {
                "event": "RUNNER_EXECUTION_RESERVED", "state": "EXECUTION_RESERVED",
                "grant_id": valid["grant_id"], "payload_sha256": digest,
                "invocation_id": valid["invocation_id"], "request_id": valid["request_id"],
                "service_generation": active_service_generation,
            }
            conn.execute(
                "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
                "VALUES (?, 'EXECUTION_RESERVED', ?, ?)",
                (valid["grant_id"], canonical_bytes(event).decode("utf-8"), now),
            )
            self._record_event_locked(conn, valid["grant_id"], "supervisor", "NOTE", event)
        return {
            "state": "EXECUTION_RESERVED", "grant_id": valid["grant_id"],
            "payload_sha256": digest, "service_generation": active_service_generation,
        }

    def complete_runner_execution(
        self, grant: dict, receipt: dict, *, active_service_generation: str,
    ) -> None:
        """Persist receipt only if the lease, epoch, budget, and generation remain current."""
        from .execution_grant import validate_execution_grant

        try:
            valid = validate_execution_grant(grant)
            valid_receipt = validate_receipt(receipt)
        except Exception as exc:
            raise StoreError("runner execution completion is malformed", kind="validation") from exc
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError("verified Store history is required for runner completion", kind="integrity")
        _need_str(active_service_generation, "active_service_generation")
        digest = hashlib.sha256(canonical_bytes(valid)).hexdigest()
        authority_changed = False
        with self._tx() as conn:
            row = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (valid["grant_id"],)
            ).fetchone()
            if row is None or row["payload_sha256"] != digest:
                raise StoreError("runner execution completion does not match its exact claim", kind="integrity")
            states = self._runner_execution_states_locked(conn, valid["grant_id"])
            if (len(states) != 2 or states[0]["state"] != "PENDING"
                    or states[1]["state"] != "EXECUTION_RESERVED"):
                raise StoreError("runner execution claim is not durably reserved", kind="lifecycle")
            if (valid_receipt["task_id"] != valid["task_id"]
                    or valid_receipt["manifest_sha256"] != valid["manifest_sha256"]
                    or valid_receipt["slot"] != valid["slot"]
                    or valid_receipt["attempt"] != valid["attempt"]
                    or valid_receipt["epoch"] != valid["epoch"]
                    or valid_receipt["invocation_id"] != valid["invocation_id"]
                    or valid_receipt["runner_id"] != valid["runner_id"]
                    or valid_receipt["resolved_model"] != valid["resolved_model"]
                    or valid_receipt["runner_attestation"]["request"]["request_id"] != valid["request_id"]):
                raise StoreError("runner receipt differs from its execution grant", kind="integrity")
            now = self._now()
            task = self._task_row(conn, valid["task_id"])
            story = self._story_row(conn, task["story_id"])
            lease = conn.execute(
                "SELECT epoch, status, expires_at, worker_id FROM leases "
                "WHERE task_id = ? AND attempt = ?",
                (valid["task_id"], valid["attempt"]),
            ).fetchone()
            authority_changed = (
                valid["service_generation"] != active_service_generation
                or int(story["epoch"]) != valid["epoch"] or story["state"] != "OWNED"
                or story["owner"] is None or story["owner_expires_at"] is None
                or float(story["owner_expires_at"]) <= now
                or lease is None or int(lease["epoch"]) != valid["epoch"]
                or lease["status"] != LEASE_LIVE or float(lease["expires_at"]) <= now
                or lease["worker_id"] != valid["runner_id"]
                or self._budget_block_locked(conn, valid["task_id"]) is not None
            )
            if authority_changed:
                event = {
                    "event": "RUNNER_EXECUTION_INDETERMINATE", "state": "INDETERMINATE",
                    "grant_id": valid["grant_id"], "payload_sha256": digest,
                    "reason": "AUTHORITY_CHANGED_BEFORE_COMPLETION",
                    "predecessor_state": "EXECUTION_RESERVED",
                    "observed_service_generation": active_service_generation,
                }
                state = "INDETERMINATE"
            else:
                # Persistent runner TestRun receipts must enter the same
                # receipt/hash chain consumed by gates and retries. The v2
                # TestRun branch validates the embedded runner attestation
                # shape here; cryptographic trust is checked by the gate.
                self._append_locked(
                    conn, valid_receipt, str(task["story_id"]), None, supervisor=False,
                )
                event = {
                    "event": "RUNNER_EXECUTION_COMPLETE", "state": "COMPLETE",
                    "grant_id": valid["grant_id"], "payload_sha256": digest,
                    "receipt": valid_receipt,
                    "receipt_sha256": receipt_sha256(valid_receipt),
                }
                state = "COMPLETE"
            conn.execute(
                "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (valid["grant_id"], state, canonical_bytes(event).decode("utf-8"), now),
            )
            self._record_event_locked(conn, valid["grant_id"], "supervisor", "NOTE", event)
        if authority_changed:
            raise StoreError("execution authority changed before completion; no receipt was returned", kind="authorization")

    def mark_pending_runner_executions_indeterminate(self, *, current_service_generation: str) -> int:
        """Terminalize predecessor PENDING/reserved grants without reclaiming them."""
        if not self.reconciliation_complete:
            raise StoreError("startup reconciliation must complete before runner recovery", kind="integrity")
        if not self.verify_event_chain():
            raise StoreError("event chain failed verification during runner recovery", kind="integrity")
        _need_str(current_service_generation, "current_service_generation")
        marked = 0
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT claim.* FROM runner_execution_claims claim "
                "WHERE NOT EXISTS (SELECT 1 FROM runner_execution_events terminal "
                "WHERE terminal.grant_id = claim.grant_id AND terminal.state IN "
                "('COMPLETE', 'INDETERMINATE', 'RECONCILED')) "
                "AND claim.service_generation != ? ORDER BY claim.grant_id",
                (current_service_generation,),
            ).fetchall()
            now = self._now()
            for row in rows:
                states = self._runner_execution_states_locked(conn, row["grant_id"])
                predecessor_state = states[-1]["state"]
                if predecessor_state not in {"PENDING", "EXECUTION_RESERVED"}:
                    raise StoreError("predecessor runner claim has an invalid recovery state", kind="integrity")
                event = {
                    "event": "RUNNER_EXECUTION_INDETERMINATE", "state": "INDETERMINATE",
                    "grant_id": row["grant_id"], "payload_sha256": row["payload_sha256"],
                    "reason": "PREDECESSOR_GENERATION_STOPPED",
                    "predecessor_state": predecessor_state,
                    "recovery_service_generation": current_service_generation,
                    "request_id": row["request_id"], "invocation_id": row["invocation_id"],
                    "task_id": row["task_id"], "slot": row["slot"],
                    "runner_id": row["runner_id"], "attempt": int(row["attempt"]),
                    "epoch": int(row["epoch"]), "run_id": row["run_id"],
                    "service_generation": row["service_generation"],
                }
                if predecessor_state == "PENDING":
                    event["terminal_disposition"] = "NO_EXECUTION"
                conn.execute(
                    "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
                    "VALUES (?, 'INDETERMINATE', ?, ?)",
                    (row["grant_id"], canonical_bytes(event).decode("utf-8"), now),
                )
                self._record_event_locked(conn, row["grant_id"], "supervisor", "NOTE", event)
                marked += 1
        return marked

    def reconcile_runner_execution(self, resolution_record: dict) -> dict:
        """Append an operator-attested resolution for one exact INDETERMINATE grant."""
        key = self._execution_resolution_key
        if key is None:
            raise StoreError("trusted execution-resolution key is unavailable", kind="authorization")
        if (not self.reconciliation_complete or not self.verify_event_chain()):
            raise StoreError("verified Store history is required for execution reconciliation", kind="integrity")
        if not isinstance(resolution_record, dict):
            raise StoreError("execution resolution record must be an object", kind="authorization")
        grant_id = resolution_record.get("grant_id")
        _need_str(grant_id, "grant_id")
        with self._tx() as conn:
            self._verify_supervisor_records(conn)
            claim = conn.execute(
                "SELECT * FROM runner_execution_claims WHERE grant_id = ?", (grant_id,)
            ).fetchone()
            if claim is None:
                raise StoreError("execution resolution names an unknown grant", kind="task")
            states = self._runner_execution_states_locked(conn, grant_id)
            if states[-1]["state"] != "INDETERMINATE":
                raise StoreError("only an unresolved INDETERMINATE grant may be reconciled", kind="lifecycle")
            predecessor_state = states[-1].get("predecessor_state")
            event = {
                "event": "RUNNER_EXECUTION_RECONCILED", "state": "RECONCILED",
                "grant_id": grant_id, "payload_sha256": claim["payload_sha256"],
                "predecessor_state": predecessor_state,
                "resolution": dict(resolution_record),
            }
            if not _valid_runner_execution_resolution(event, claim, key, predecessor_state):
                raise StoreError(
                    "operator execution resolution signature or exact-grant binding is invalid",
                    kind="authorization",
                )
            resolution_id = resolution_record["resolution_id"]
            for row in conn.execute(
                "SELECT payload FROM runner_execution_events WHERE state = 'RECONCILED'"
            ).fetchall():
                prior_event = json.loads(row["payload"])
                prior_record = prior_event.get("resolution") if isinstance(prior_event, dict) else None
                if isinstance(prior_record, dict) and prior_record.get("resolution_id") == resolution_id:
                    raise StoreError("execution resolution id is already used", kind="duplicate")
            now = self._now()
            conn.execute(
                "INSERT INTO runner_execution_events(grant_id, state, payload, created_at) "
                "VALUES (?, 'RECONCILED', ?, ?)",
                (grant_id, canonical_bytes(event).decode("utf-8"), now),
            )
            self._record_event_locked(conn, grant_id, "supervisor", "NOTE", event)
        return {
            "grant_id": grant_id, "state": "RECONCILED",
            "outcome": resolution_record["outcome"],
            "continuation_allowed": resolution_record["outcome"] in {
                "NO_EXECUTION_PROVEN", "EFFECTS_RESOLVED",
            },
        }

    def execute_external_idempotent(
        self, operation_key: str, operation: str, payload: Any, effect: Callable[[], Any]
    ) -> Any:
        """Run a retry-safe external effect outside the Store transaction.

        The append-only operation row is the durable intent. Completion is a
        separate hash-chained event, so a crash leaves an observable pending
        operation. Retrying the same key/payload is safe only when the backend
        also durably enforces that idempotency key.
        """
        _need_str(operation_key, "operation_key")
        _need_str(operation, "operation")
        if not callable(effect):
            raise StoreError("external operation effect must be callable", kind="argument")
        payload_digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
        intent_event = "SUPERVISOR_EXTERNAL_OPERATION_INTENT"
        completion_event = "SUPERVISOR_EXTERNAL_OPERATION_COMPLETED"
        pending = {"_vst_state": "PENDING"}
        no_completion = object()

        def completion_locked(conn: sqlite3.Connection) -> Any:
            rows = conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND actor = 'supervisor' AND kind = 'NOTE' ORDER BY seq",
                (operation_key,),
            ).fetchall()
            completed = no_completion
            for row in rows:
                try:
                    event = json.loads(row["payload"])
                except (TypeError, ValueError):
                    continue
                if event.get("event") != completion_event:
                    continue
                if (event.get("operation") != operation
                        or event.get("payload_sha256") != payload_digest
                        or event.get("operation_key") != operation_key):
                    raise StoreError("external operation completion binding is invalid", kind="integrity")
                result = event.get("result")
                encoded = canonical_bytes(result).decode("utf-8")
                if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != event.get("result_sha256"):
                    raise StoreError("external operation result digest is invalid", kind="integrity")
                if completed is not no_completion and canonical_bytes(completed) != canonical_bytes(result):
                    raise StoreError("external operation produced conflicting completed results", kind="integrity")
                completed = result
            return completed

        with self._tx() as conn:
            row = conn.execute(
                "SELECT operation, payload_sha256, result FROM supervisor_operations WHERE operation_key = ?",
                (operation_key,),
            ).fetchone()
            if row is not None:
                if row["operation"] != operation or row["payload_sha256"] != payload_digest:
                    raise StoreError("idempotency key reused with different operation or payload", kind="duplicate")
                if row["result"] != canonical_bytes(pending).decode("utf-8"):
                    # Results committed by the pre-intent implementation remain
                    # readable and idempotent across the transition.
                    return json.loads(row["result"])
                result = completion_locked(conn)
                if result is not no_completion:
                    return result
            else:
                conn.execute(
                    "INSERT INTO supervisor_operations(operation_key, operation, payload_sha256, result) VALUES (?, ?, ?, ?)",
                    (operation_key, operation, payload_digest, canonical_bytes(pending).decode("utf-8")),
                )
            attempts = 1
            for row in conn.execute(
                "SELECT payload FROM events WHERE task_id = ? AND actor = 'supervisor' AND kind = 'NOTE'",
                (operation_key,),
            ).fetchall():
                try:
                    prior = json.loads(row["payload"])
                except (TypeError, ValueError):
                    continue
                if prior.get("event") == intent_event:
                    attempts = max(attempts, int(prior.get("attempt", 0)) + 1)
            self._record_event_locked(
                conn, operation_key, "supervisor", "NOTE",
                {"event": intent_event, "operation_key": operation_key,
                 "operation": operation, "payload_sha256": payload_digest,
                 "state": "PENDING", "attempt": attempts},
            )

        try:
            result = effect()
            encoded = canonical_bytes(result).decode("utf-8")
        except BaseException as exc:
            with self._tx() as conn:
                self._record_event_locked(
                    conn, operation_key, "supervisor", "NOTE",
                    {"event": "SUPERVISOR_EXTERNAL_OPERATION_UNKNOWN",
                     "operation_key": operation_key, "operation": operation,
                     "payload_sha256": payload_digest, "attempt": attempts,
                     "error_type": type(exc).__name__},
                )
            raise

        result_digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self._tx() as conn:
            row = conn.execute(
                "SELECT operation, payload_sha256 FROM supervisor_operations WHERE operation_key = ?",
                (operation_key,),
            ).fetchone()
            if (row is None or row["operation"] != operation
                    or row["payload_sha256"] != payload_digest):
                raise StoreError("external operation intent changed before completion", kind="integrity")
            prior_result = completion_locked(conn)
            if prior_result is not no_completion:
                if canonical_bytes(prior_result) != canonical_bytes(result):
                    raise StoreError("external operation retry returned a conflicting result", kind="integrity")
                return prior_result
            self._record_event_locked(
                conn, operation_key, "supervisor", "NOTE",
                {"event": completion_event, "operation_key": operation_key,
                 "operation": operation, "payload_sha256": payload_digest,
                 "result": result, "result_sha256": result_digest,
                 "attempt": attempts},
            )
        return result

    def append_receipt_idempotent(
        self, operation_key: str, receipt: dict, story_id: str, worker_key: bytes
    ) -> dict:
        """Atomically append one worker receipt and its supervisor idempotency result."""
        key = _need_key(worker_key, "worker_key")
        if hmac.compare_digest(key, self._event_key):
            raise StoreError("worker key must differ from the event_key", kind="key")
        payload = {"receipt": receipt, "story_id": story_id}

        def append(conn: sqlite3.Connection) -> dict:
            digest = self._append_locked(conn, receipt, story_id, key, supervisor=False)
            return {"receipt_id": receipt.get("receipt_id"), "receipt_sha256": digest}

        return self.execute_idempotent(operation_key, "receipt", payload, append)

    def consume_preflight(self, run_id: str, nonce: str, spec_sha256: str, probe_sha256: str) -> None:
        """Persist one-time probe use before the supervisor launches a worker."""
        for value, name in ((run_id, "run_id"), (nonce, "nonce")):
            _need_str(value, name)
        for value, name in ((spec_sha256, "spec_sha256"), (probe_sha256, "probe_sha256")):
            if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise StoreError(f"{name}: must be a lowercase SHA-256 digest", kind="argument")
        with self._tx() as conn:
            try:
                conn.execute(
                    "INSERT INTO supervisor_probes(run_id, nonce, spec_sha256, probe_sha256) VALUES (?, ?, ?, ?)",
                    (run_id, nonce, spec_sha256, probe_sha256),
                )
            except sqlite3.IntegrityError as exc:
                raise StoreError("preflight run id or nonce was already consumed", kind="duplicate") from exc
            self._record_event_locked(
                conn, run_id, "supervisor", "NOTE",
                {
                    "event": "PREFLIGHT_CONSUMED", "nonce": nonce,
                    "spec_sha256": spec_sha256, "probe_sha256": probe_sha256,
                },
            )

    def ensure_preflight_consumed(
        self, run_id: str, nonce: str, spec_sha256: str, probe_sha256: str,
    ) -> bool:
        """Consume an exact verified run probe, allowing idempotent service restart only.

        Returns True when this call appended the first consumption record and
        False when the same immutable run/nonce/digest tuple was already stored.
        A reused run ID or nonce with different evidence remains a hard failure.
        """
        if not self.reconciliation_complete or not self.verify_event_chain():
            raise StoreError(
                "verified Store history is required before preflight consumption",
                kind="integrity",
            )
        for value, name in ((run_id, "run_id"), (nonce, "nonce")):
            _need_str(value, name)
        for value, name in ((spec_sha256, "spec_sha256"), (probe_sha256, "probe_sha256")):
            if not isinstance(value, str) or len(value) != 64 or any(
                char not in "0123456789abcdef" for char in value
            ):
                raise StoreError(f"{name}: must be a lowercase SHA-256 digest", kind="argument")
        with self._tx() as conn:
            existing = conn.execute(
                "SELECT run_id, nonce, spec_sha256, probe_sha256 FROM supervisor_probes "
                "WHERE run_id = ? OR nonce = ?", (run_id, nonce),
            ).fetchall()
            if existing:
                if (len(existing) == 1 and existing[0]["run_id"] == run_id
                        and existing[0]["nonce"] == nonce
                        and existing[0]["spec_sha256"] == spec_sha256
                        and existing[0]["probe_sha256"] == probe_sha256):
                    return False
                raise StoreError("preflight run id or nonce was already consumed", kind="duplicate")
            conn.execute(
                "INSERT INTO supervisor_probes(run_id, nonce, spec_sha256, probe_sha256) "
                "VALUES (?, ?, ?, ?)", (run_id, nonce, spec_sha256, probe_sha256),
            )
            self._record_event_locked(
                conn, run_id, "supervisor", "NOTE",
                {"event": "PREFLIGHT_CONSUMED", "nonce": nonce,
                 "spec_sha256": spec_sha256, "probe_sha256": probe_sha256},
            )
        return True

    # --------------------------------------------------------------- budget

    def set_budget(self, task_id: str, cap: int) -> None:
        """Lower (or restore) the cap of a registered task; spent is preserved.

        The cap can never exceed the manifest cost_cap (StoreError kind
        'budget') nor drop below the amount already spent (kind 'argument');
        an unknown task is kind 'task'. register_task seeds the row.
        """
        _need_str(task_id, "task_id")
        _need_int(cap, "cap", 0, MAX_BUDGET)
        with self._tx() as conn:
            task = self._task_row(conn, task_id)
            manifest_cap = int(json.loads(task["manifest"])["cost_cap"])
            if cap > manifest_cap:
                raise StoreError(
                    f"cap {cap} exceeds the manifest cost_cap {manifest_cap}", kind="budget"
                )
            row = conn.execute(
                "SELECT spent FROM budget WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is not None and row["spent"] > cap:
                raise StoreError(
                    f"cap {cap} is below the amount already spent ({row['spent']})",
                    kind="argument",
                )
            conn.execute(
                "INSERT INTO budget (task_id, cap, spent) VALUES (?, ?, 0) "
                "ON CONFLICT(task_id) DO UPDATE SET cap = excluded.cap",
                (task_id, cap),
            )

    def charge(
        self,
        task_id: str,
        amount: int,
        *,
        supervisor_key: bytes,
        runner_id: str = SUPERVISOR_RUNNER_ID,
    ) -> int:
        """Charge metered usage; return the remaining budget.

        When spent + amount would exceed cap nothing is charged; a
        'BUDGET_EXCEEDED' event AND the signed BUDGET_EXCEEDED supervisor marker
        (plus a BUDGET_BLOCKED event, once) are committed, and then
        StoreError(kind='budget') is raised after the commit. supervisor_key
        signs the marker and must differ from the event_key (kind 'key');
        runner_id is the marker's runner_id.
        """
        _need_str(task_id, "task_id")
        _need_int(amount, "amount", 0, MAX_BUDGET)
        sup_key = self._need_supervisor_key(supervisor_key)
        _need_str(runner_id, "runner_id")
        with self._tx() as conn:
            task = self._task_row(conn, task_id)
            row = conn.execute(
                "SELECT cap, spent FROM budget WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"no budget set for task {task_id!r}", kind="budget")
            if row["spent"] + amount > row["cap"]:
                self._budget_exceeded_locked(conn, task, sup_key, runner_id, amount)
                remaining = None
            else:
                conn.execute(
                    "UPDATE budget SET spent = spent + ? WHERE task_id = ?", (amount, task_id)
                )
                remaining = row["cap"] - row["spent"] - amount
        if remaining is None:
            raise StoreError(f"budget exceeded for task {task_id!r}", kind="budget")
        return remaining

    # ----------------------------------------------------------- supervisor

    def supervisor_reap_and_mark(self, supervisor_key: bytes, runner_id: str) -> list[dict]:
        """Reap expired leases and mark lost attempts with WORKER_LOST receipts.

        For every closed-by-loss lease (EXPIRED or FENCED, not yet marked) whose
        holder NEVER wrote a receipt (wrote = 0), a signed Documentation receipt
        in SUPERVISOR_SLOT with result INCONCLUSIVE and check_description
        'WORKER_LOST' is appended. Leases that wrote receipts are only flagged
        marked. The receipt attempt is the next in the supervisor chain, its
        epoch is the story's CURRENT epoch and its candidate_head is the head
        of the task's latest receipt (else manifest base_head). Everything is
        written in one transaction; the receipts are returned.
        """
        sup_key = self._need_supervisor_key(supervisor_key)
        _need_str(runner_id, "runner_id")
        written: list[dict] = []
        with self._tx() as conn:
            self._reap_locked(conn, self._now())
            lost = conn.execute(
                "SELECT lease_id, task_id, attempt, wrote FROM leases "
                "WHERE status IN ('EXPIRED', 'FENCED') AND marked = 0 ORDER BY lease_id"
            ).fetchall()
            for lease in lost:
                if lease["wrote"] == 0:
                    task = self._task_row(conn, lease["task_id"])
                    body, _created = self._supervisor_marker_locked(
                        conn, task, "WORKER_LOST", sup_key, runner_id,
                        f"supervisor-{lease['task_id']}-lease-{lease['lease_id']}",
                    )
                    written.append(body)
                conn.execute(
                    "UPDATE leases SET marked = 1 WHERE lease_id = ?", (lease["lease_id"],)
                )
        return written

    def _supervisor_marker_locked(
        self,
        conn: sqlite3.Connection,
        task: sqlite3.Row,
        reason: str,
        supervisor_key: bytes,
        runner_id: str,
        invocation_id: str,
    ) -> tuple[dict, bool]:
        """Build, sign and append one supervisor marker; return (receipt, created).

        Terminal markers (BUDGET_EXCEEDED, RETRY_EXHAUSTED) are idempotent: an
        existing marker of the same reason is returned with created = False.
        """
        task_id = task["task_id"]
        if reason in TERMINAL_MARKERS:
            existing = self._find_marker(conn, task_id, reason)
            if existing is not None:
                return existing, False
        manifest = json.loads(task["manifest"])
        story = self._story_row(conn, task["story_id"])
        last = conn.execute(
            "SELECT attempt, receipt_sha256 FROM receipts WHERE task_id = ? AND slot = ? "
            "ORDER BY attempt DESC LIMIT 1",
            (task_id, SUPERVISOR_SLOT),
        ).fetchone()
        newest = conn.execute(
            "SELECT body FROM receipts WHERE task_id = ? ORDER BY seq DESC LIMIT 1", (task_id,)
        ).fetchone()
        head = json.loads(newest["body"])["candidate_head"] if newest else manifest["base_head"]
        attempt = 1 if last is None else last["attempt"] + 1
        body = {
            "receipt_id": f"{SUPERVISOR_RECEIPT_PREFIX}{task_id}-{attempt}",
            "receipt_type": "Documentation",
            "task_id": task_id,
            "manifest_sha256": task["manifest_sha256"],
            "slot": SUPERVISOR_SLOT,
            "attempt": attempt,
            "prev_receipt_sha256": None if last is None else last["receipt_sha256"],
            "candidate_head": head,
            "epoch": int(story["epoch"]),
            "runner_id": runner_id,
            "role_sha256": manifest["role_sha256"],
            "resolved_model": "supervisor",
            "invocation_id": invocation_id,
            "result": MARKER_RESULTS[reason],
            "created_at": _iso(self._now()),
            "check_description": reason,
            "covered_acceptance": [],
        }
        if manifest.get("contract_version") == 2:
            body["contract_version"] = 2
            body["signature"] = sign(dict(body), supervisor_key, RECEIPT_V2_LABEL)
        else:
            body["signature"] = sign(dict(body), supervisor_key)
        self._append_locked(conn, body, task["story_id"], supervisor_key, supervisor=True)
        return body, True

    def mark_budget_exceeded(
        self, task_id: str, supervisor_key: bytes, runner_id: str
    ) -> dict:
        """Write the supervisor BLOCKED(BUDGET_EXCEEDED) marker; idempotent.

        The manifest and story come from the registered task. A signed
        Documentation receipt with result BLOCKED and check_description
        'BUDGET_EXCEEDED' is appended to SUPERVISOR_SLOT and a BUDGET_BLOCKED
        event is recorded. A second call returns the existing marker without
        writing anything. Does not require an exceeded budget row: the caller
        (supervisor) decides after charge raised StoreError(kind='budget').
        """
        _need_str(task_id, "task_id")
        sup_key = self._need_supervisor_key(supervisor_key)
        _need_str(runner_id, "runner_id")
        with self._tx() as conn:
            task = self._task_row(conn, task_id)
            receipt = self._budget_marker_locked(conn, task, sup_key, runner_id)
        return receipt

    def _budget_marker_locked(
        self, conn: sqlite3.Connection, task: sqlite3.Row, supervisor_key: bytes, runner_id: str
    ) -> dict:
        """Idempotently write the BUDGET_EXCEEDED marker (+ BUDGET_BLOCKED event once)."""
        receipt, created = self._supervisor_marker_locked(
            conn, task, "BUDGET_EXCEEDED", supervisor_key, runner_id,
            f"supervisor-{task['task_id']}-budget",
        )
        if created:
            self._record_event_locked(
                conn, task["task_id"], runner_id, "BUDGET_BLOCKED",
                {"receipt_id": receipt["receipt_id"]},
            )
        return receipt

    # --------------------------------------------------------------- render

    def render_state_md(self, story_id: str) -> str:
        """Deterministic read-only markdown view of one story (one read transaction)."""
        with self._read_tx() as conn:
            story = self._story_row(conn, story_id)
            leases = conn.execute(
                "SELECT * FROM leases WHERE story_id = ? ORDER BY lease_id", (story_id,)
            ).fetchall()
            receipts = conn.execute(
                "SELECT task_id, slot, attempt, epoch, receipt_sha256, body FROM receipts "
                "WHERE story_id = ? ORDER BY task_id, slot, attempt",
                (story_id,),
            ).fetchall()
        lines = [
            "<!-- GENERATED VIEW - do not edit. Source of truth: the state store. -->",
            "GENERATED VIEW - do not edit",
            "",
            f"# STATE: {_cell(story['story_id'])}",
            "",
            f"- project: {_cell(story['project_id'])}",
            f"- phase: {story['phase']}",
            f"- epoch: {story['epoch']}",
            f"- owner: {_cell(story['owner'] if story['owner'] is not None else '-')}",
            f"- state: {_cell(story['state'])}",
            "",
            "## Leases",
            "",
            "| lease | task | attempt | worker | epoch | expires_at | status | wrote | marked |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for lease in leases:
            lines.append(
                f"| {lease['lease_id']} | {_cell(lease['task_id'])} | {lease['attempt']} "
                f"| {_cell(lease['worker_id'])} | {lease['epoch']} | {lease['expires_at']!r} "
                f"| {lease['status']} | {lease['wrote']} | {lease['marked']} |"
            )
        lines += [
            "",
            "## Receipts",
            "",
            "| task | slot | attempt | type | result | epoch | sha256 |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in receipts:
            body = json.loads(row["body"])
            lines.append(
                f"| {_cell(row['task_id'])} | {_cell(row['slot'])} | {row['attempt']} "
                f"| {body['receipt_type']} | {body['result']} | {row['epoch']} "
                f"| {row['receipt_sha256']} |"
            )
        return "\n".join(lines) + "\n"
