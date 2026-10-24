"""SQLite state store: epochs, tasks, leases, slots, receipts, events, budget (BD-5, BD-6).

One connection per Store instance; autocommit mode (isolation_level=None) with
an explicit BEGIN IMMEDIATE around every mutating method. `_tx` always ends the
transaction with an explicit COMMIT or ROLLBACK; SQLite "busy"/"locked"
errors become the distinct StoreBusyError (a StoreError with kind 'busy').
journal_mode is WAL, foreign_keys and recursive_triggers are ON.

Schema versioning: PRAGMA user_version is SCHEMA_VERSION (2). A new file is
initialised inside one transaction; a legacy un-versioned database that already
has tables, or any other version, is refused with StoreError(kind='schema').
The database file (and its -wal/-shm files) get mode 0o600 on a best-effort
basis (os.chmod failures are ignored).

Keys and authority (all keys are bytes of length >= 32):
- event_key (constructor): HMAC key of the event chain.
- worker key: passed to append_receipt; verifies worker receipts.
- supervisor_key: passed to the supervisor methods, acquire_lease (needed to
  write the RETRY_EXHAUSTED marker) and append_supervisor_receipt. Receipts in
  SUPERVISOR_SLOT are verified ONLY with it, so a receipt signed with the
  worker key cannot enter the supervisor chain.

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
  only kind that gets a WORKER_LOST marker.
- Receipts: append_receipt verifies the worker signature, the manifest hash,
  the task/story link, the slot (must be a declared slot of the receipt type),
  result == derive_result, epoch == current epoch, a live unexpired lease held
  by runner_id at the same epoch, attempt <= retry_cap + 1 and the chain
  position (attempt = previous + 1, prev_receipt_sha256 = previous hash).
  Receipts for SUPERVISOR_SLOT are refused there: only append_supervisor_receipt
  and the supervisor methods write them (supervisor isolation: a worker lease
  never writes supervisor receipts and the supervisor path never writes worker
  slots). Supervisor markers are WORKER_LOST (INCONCLUSIVE),
  BUDGET_EXCEEDED and RETRY_EXHAUSTED (BLOCKED, terminal, one per task).
  After a terminal marker no lease and no worker receipt is accepted.
- Retry cap: acquire_lease refuses attempt > retry_cap + 1, and also refuses
  when a real slot already holds attempt retry_cap + 1 without a PASS. The first
  refusal commits a signed RETRY_EXHAUSTED supervisor marker, then raises
  StoreError(kind='retry'); repeated attempts do not add markers.
- Events and receipts are append-only (triggers). The event log is a hash
  chain keyed with HMAC: hash = HMAC(event_key, label + prev_hash + canonical
  row fields). A keyed anchor row in `meta` (count, head hash, HMAC) is
  updated with every event, so editing, deleting or truncating events is
  detected by verify_event_chain unless an attacker rolls back to an older
  consistent (events, anchor) pair; event_anchor() returns (count, head) for
  anchoring outside the database.
- Budget: charge never lets spent exceed cap; mark_budget_exceeded is
  idempotent (a single BUDGET_EXCEEDED marker per task).
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
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from .contracts import (
    SUPERVISOR_SLOT,
    canonical_bytes,
    derive_result,
    manifest_sha256,
    receipt_sha256,
    validate_receipt,
    validate_task_manifest,
)
from .signing import MIN_KEY_BYTES, sign, verify

SCHEMA_VERSION = 2
GENESIS_HASH = "0" * 64
DEFAULT_OWNER_TTL_SEC = 3600.0
SUPERVISOR_RUNNER_ID = "store-supervisor"

MAX_COUNTER = 2**31 - 1
MAX_BUDGET = 10**12
MAX_SLOTS = 1024
MAX_TTL_SEC = 366 * 24 * 3600

LEASE_LIVE = "LIVE"
LEASE_RELEASED = "RELEASED"
LEASE_EXPIRED = "EXPIRED"
LEASE_FENCED = "FENCED"
LEASE_STATUSES = frozenset({LEASE_LIVE, LEASE_RELEASED, LEASE_EXPIRED, LEASE_FENCED})
STORY_STATES = frozenset({"OPEN", "OWNED"})

# Events written by the store itself, plus the two kinds callers may record.
CALLER_EVENT_KINDS = frozenset({"NOTE", "OPERATOR_ACTION"})
EVENT_KINDS = frozenset(
    {
        "EPOCH_ACQUIRED",
        "EPOCH_RENEWED",
        "EPOCH_RELEASED",
        "PHASE_SET",
        "TASK_REGISTERED",
        "LEASE_ACQUIRED",
        "LEASE_RELEASED",
        "LEASE_EXPIRED",
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

_EVENT_LABEL = b"vst-event-v1\0"
_ANCHOR_LABEL = b"vst-anchor-v1\0"
_ANCHOR_KEY = "events_anchor"


def _sql_list(values: Any) -> str:
    return ", ".join("'" + value + "'" for value in sorted(values))


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
    terminal (a terminal marker blocks the task), schema, busy,
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
    ) -> None:
        self._event_key = _need_key(event_key, "event_key")
        if not isinstance(path, str) or not path:
            raise StoreError("path: must be a non-empty string", kind="argument")
        self._clock = clock
        self._path = path
        self._conn = sqlite3.connect(
            path, isolation_level=None, timeout=float(busy_timeout_sec)
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA recursive_triggers=ON")
            self._init_schema()
        except sqlite3.OperationalError as exc:
            self._conn.close()
            busy = _busy_error(exc)
            if busy is not None:
                raise busy from exc
            raise
        except BaseException:
            self._conn.close()
            raise
        _restrict_permissions(path)

    def _init_schema(self) -> None:
        with self._tx() as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
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
            elif version != SCHEMA_VERSION:
                raise StoreError(
                    f"schema version {version} is not supported (expected {SCHEMA_VERSION})",
                    kind="schema",
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
        """BEGIN IMMEDIATE ... explicit COMMIT, or ROLLBACK on any exception."""
        try:
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

    def _now(self) -> float:
        return float(self._clock())

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

    def _record_event_locked(
        self, conn: sqlite3.Connection, task_id: str, actor: str, kind: str, payload: Any
    ) -> None:
        if kind not in EVENT_KINDS:
            raise StoreError(f"unknown event kind {kind!r}", kind="argument")
        last = conn.execute(
            "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = last["hash"] if last is not None else GENESIS_HASH
        anchor_row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_ANCHOR_KEY,)
        ).fetchone()
        count = 0
        if anchor_row is not None:
            try:
                count = int(json.loads(anchor_row["value"])["count"])
            except (ValueError, KeyError, TypeError):
                count = int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        fields = {
            "ts": self._now(),
            "task_id": task_id,
            "actor": actor,
            "kind": kind,
            "payload": canonical_bytes(payload).decode("utf-8"),
        }
        new_hash = self._event_mac(prev_hash, fields)
        conn.execute(
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

    def _reap_locked(self, conn: sqlite3.Connection, now: float) -> list[sqlite3.Row]:
        rows = conn.execute(
            "SELECT lease_id, task_id, attempt FROM leases "
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
            now = self._now()
            story = self._story_row(conn, story_id)
            expires = story["owner_expires_at"]
            if story["owner"] is not None and expires is not None and expires > now:
                raise StoreError(
                    f"story {story_id!r} is owned by live owner {story['owner']!r}",
                    kind="epoch",
                )
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
        """
        valid = validate_task_manifest(manifest)
        digest = manifest_sha256(valid)
        with self._tx() as conn:
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
                conn.execute(
                    "INSERT INTO tasks (task_id, story_id, manifest_sha256, retry_cap, manifest) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        valid["task_id"], valid["story_id"], digest,
                        valid["retry_cap"], canonical_bytes(valid).decode("utf-8"),
                    ),
                )
                self._record_event_locked(
                    conn, valid["task_id"], "store", "TASK_REGISTERED",
                    {"manifest_sha256": digest, "story_id": valid["story_id"]},
                )
        return digest

    def get_manifest(self, task_id: str) -> dict:
        """The registered manifest of a task (deep copy from the stored JSON)."""
        return json.loads(self._task_row(self._conn, task_id)["manifest"])

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
        (lease); no free slot (slot); a terminal marker already present, or
        the retry cap reached (retry/budget). supervisor_key signs the
        RETRY_EXHAUSTED marker that is committed before kind 'retry' is raised.
        """
        _need_str(task_id, "task_id")
        _need_str(story_id, "story_id")
        _need_str(worker_id, "worker_id")
        _need_int(epoch, "epoch", 1)
        _need_int(attempt, "attempt", 1)
        ttl = _need_ttl(ttl_sec)
        sup_key = _need_key(supervisor_key, "supervisor_key")
        blocked: str | None = None
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
            expected = 1 if prior is None else int(prior["attempt"]) + 1
            if attempt != expected:
                raise StoreError(
                    f"attempt {attempt} must be previous attempt + 1 (expected {expected})",
                    kind="lease",
                )
            if self._retry_exhausted(conn, task, attempt):
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
            raise StoreError(blocked, kind="retry")

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

    def _retry_exhausted(self, conn: sqlite3.Connection, task: sqlite3.Row, attempt: int) -> bool:
        cap = int(task["retry_cap"])
        if attempt > cap + 1:
            return True
        tops = conn.execute(
            "SELECT slot, MAX(attempt) AS top FROM receipts "
            "WHERE task_id = ? AND slot != ? GROUP BY slot",
            (task["task_id"], SUPERVISOR_SLOT),
        ).fetchall()
        for row in tops:
            if row["top"] >= cap + 1:
                body = conn.execute(
                    "SELECT body FROM receipts WHERE task_id = ? AND slot = ? AND attempt = ?",
                    (task["task_id"], row["slot"], row["top"]),
                ).fetchone()
                if json.loads(body["body"])["result"] != "PASS":
                    return True
        return False

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
        present), lease (no live unexpired lease held by runner_id at this
        epoch), retry (attempt > retry_cap + 1), chain (attempt != last + 1 or
        wrong prev_receipt_sha256), duplicate (receipt_id reused).
        """
        worker_key = _need_key(key, "key")
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
        sup_key = _need_key(supervisor_key, "supervisor_key")
        with self._tx() as conn:
            self._append_locked(conn, receipt, story_id, sup_key, supervisor=True)

    def _append_locked(
        self,
        conn: sqlite3.Connection,
        receipt: dict,
        story_id: str,
        key: bytes,
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
        if not verify(valid, key):
            raise StoreError("invalid receipt signature", kind="signature")
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
            lease = self._receipt_lease(conn, valid)
            if valid["attempt"] > int(task["retry_cap"]) + 1:
                raise StoreError(
                    f"attempt {valid['attempt']} exceeds retry_cap {task['retry_cap']} + 1",
                    kind="retry",
                )
        last = conn.execute(
            "SELECT attempt, receipt_sha256 FROM receipts WHERE task_id = ? AND slot = ? "
            "ORDER BY attempt DESC LIMIT 1",
            (valid["task_id"], valid["slot"]),
        ).fetchone()
        expected_attempt = 1 if last is None else last["attempt"] + 1
        if valid["attempt"] != expected_attempt:
            raise StoreError(
                f"attempt {valid['attempt']} breaks the chain; expected {expected_attempt}",
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
            conn.execute("UPDATE leases SET wrote = 1 WHERE lease_id = ?", (lease["lease_id"],))
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
        rows = self._conn.execute(
            "SELECT body FROM receipts WHERE task_id = ? ORDER BY seq", (task_id,)
        ).fetchall()
        return [json.loads(row["body"]) for row in rows]

    # --------------------------------------------------------------- events

    def record_event(self, task_id: str, actor: str, kind: str, payload: Any) -> None:
        """Append a caller event; kind must be in CALLER_EVENT_KINDS (closed enum)."""
        _need_str(task_id, "task_id")
        _need_str(actor, "actor")
        if kind not in CALLER_EVENT_KINDS:
            raise StoreError(
                f"event kind must be one of {sorted(CALLER_EVENT_KINDS)}", kind="argument"
            )
        with self._tx() as conn:
            self._record_event_locked(conn, task_id, actor, kind, payload)

    def verify_event_chain(self) -> bool:
        """True iff the keyed chain is intact AND matches the keyed anchor.

        Detects edited rows, inserted or removed rows and tail truncation (the
        anchor holds the event count and head hash under the same HMAC key).
        """
        rows = self._conn.execute(
            "SELECT ts, task_id, actor, kind, payload, prev_hash, hash FROM events ORDER BY seq"
        ).fetchall()
        prev_hash = GENESIS_HASH
        for row in rows:
            fields = {
                "ts": row["ts"],
                "task_id": row["task_id"],
                "actor": row["actor"],
                "kind": row["kind"],
                "payload": row["payload"],
            }
            expected = self._event_mac(prev_hash, fields)
            if row["prev_hash"] != prev_hash or not hmac.compare_digest(
                row["hash"].encode("utf-8"), expected.encode("utf-8")
            ):
                return False
            prev_hash = row["hash"]
        anchor_row = self._conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_ANCHOR_KEY,)
        ).fetchone()
        if anchor_row is None:
            return len(rows) == 0
        try:
            anchor = json.loads(anchor_row["value"])
            count, head, mac = anchor["count"], anchor["head"], anchor["mac"]
        except (ValueError, KeyError, TypeError):
            return False
        if count != len(rows) or head != prev_hash or not isinstance(mac, str):
            return False
        return hmac.compare_digest(
            mac.encode("utf-8"), self._anchor_mac(len(rows), prev_hash).encode("utf-8")
        )

    def event_anchor(self) -> tuple[int, str]:
        """(event count, head hash) of the current log, for external anchoring."""
        count = int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        last = self._conn.execute("SELECT hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        return count, (last["hash"] if last is not None else GENESIS_HASH)

    # --------------------------------------------------------------- budget

    def set_budget(self, task_id: str, cap: int) -> None:
        """Create or change the cap of a task; spent is preserved (cap >= spent)."""
        _need_str(task_id, "task_id")
        _need_int(cap, "cap", 0, MAX_BUDGET)
        with self._tx() as conn:
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

    def charge(self, task_id: str, amount: int) -> int:
        """Charge metered usage; return the remaining budget.

        When spent + amount would exceed cap nothing is charged, a
        'BUDGET_EXCEEDED' event is committed, and StoreError(kind='budget') is
        raised after the commit.
        """
        _need_str(task_id, "task_id")
        _need_int(amount, "amount", 0, MAX_BUDGET)
        with self._tx() as conn:
            row = conn.execute(
                "SELECT cap, spent FROM budget WHERE task_id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise StoreError(f"no budget set for task {task_id!r}", kind="budget")
            if row["spent"] + amount > row["cap"]:
                self._record_event_locked(
                    conn, task_id, "store", "BUDGET_EXCEEDED",
                    {"cap": row["cap"], "spent": row["spent"], "amount": amount},
                )
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
        sup_key = _need_key(supervisor_key, "supervisor_key")
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
            "receipt_id": f"sup-{task_id}-{attempt}",
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
        sup_key = _need_key(supervisor_key, "supervisor_key")
        _need_str(runner_id, "runner_id")
        with self._tx() as conn:
            task = self._task_row(conn, task_id)
            receipt, created = self._supervisor_marker_locked(
                conn, task, "BUDGET_EXCEEDED", sup_key, runner_id,
                f"supervisor-{task_id}-budget",
            )
            if created:
                self._record_event_locked(
                    conn, task_id, runner_id, "BUDGET_BLOCKED",
                    {"receipt_id": receipt["receipt_id"]},
                )
        return receipt

    # --------------------------------------------------------------- render

    def render_state_md(self, story_id: str) -> str:
        """Deterministic read-only markdown view of one story."""
        story = self._story_row(self._conn, story_id)
        leases = self._conn.execute(
            "SELECT * FROM leases WHERE story_id = ? ORDER BY lease_id", (story_id,)
        ).fetchall()
        receipts = self._conn.execute(
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
