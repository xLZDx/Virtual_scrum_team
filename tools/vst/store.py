"""SQLite state store: epochs, leases, slots, receipts, events, budget (BD-5, BD-6).

One connection per Store instance; autocommit mode with an explicit
BEGIN IMMEDIATE around every mutating method, so each public method is atomic
and writers are serialised by SQLite. journal_mode is WAL, foreign keys are on.

Authority rules:
- Epoch: stories.epoch is a fencing token. acquire_epoch is a compare-and-swap
  that only succeeds when no live owner holds the story (owner_expires_at is in
  the future). Every lease operation and every receipt append must carry the
  current epoch; a stale epoch is rejected.
- Lease + slot: acquire_lease takes a free row of `slots` in the SAME
  transaction as the lease row. Expired leases are reaped (released = 2) and
  their slots freed.
- Receipts and events are append-only: triggers RAISE(ABORT) on UPDATE and
  DELETE. Receipts are chained per (task_id, slot) by attempt and
  prev_receipt_sha256. Events form a global hash chain.
- Budget: charge never lets spent exceed cap.

Columns added to the minimal schema (documented in schemas/README.md):
stories.owner_expires_at (owner liveness), leases.marked (supervisor receipt
already written), receipts.story_id (needed to render a story view).

leases.released values: 0 = live, 1 = released by the worker, 2 = reaped on
expiry (or fenced by an epoch takeover).

Standard library only; no network.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterator

from .contracts import (
    canonical_bytes,
    receipt_sha256,
    validate_receipt,
    validate_task_manifest,
)
from .signing import sign

GENESIS_HASH = "0" * 64
DEFAULT_OWNER_TTL_SEC = 3600.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    story_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    phase INT NOT NULL,
    epoch INT NOT NULL,
    owner TEXT,
    state TEXT NOT NULL,
    owner_expires_at REAL
);
CREATE TABLE IF NOT EXISTS leases (
    task_id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL REFERENCES stories(story_id),
    attempt INT NOT NULL,
    worker_id TEXT NOT NULL,
    epoch INT NOT NULL,
    expires_at REAL NOT NULL,
    released INT NOT NULL DEFAULT 0,
    marked INT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS slots (
    slot_no INT PRIMARY KEY,
    task_id TEXT,
    worker_id TEXT,
    expires_at REAL
);
CREATE TABLE IF NOT EXISTS receipts (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id TEXT NOT NULL UNIQUE,
    story_id TEXT NOT NULL REFERENCES stories(story_id),
    task_id TEXT NOT NULL,
    slot TEXT NOT NULL,
    attempt INT NOT NULL,
    epoch INT NOT NULL,
    receipt_sha256 TEXT NOT NULL,
    prev_receipt_sha256 TEXT,
    body TEXT NOT NULL,
    UNIQUE (task_id, slot, attempt)
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    task_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budget (
    task_id TEXT PRIMARY KEY,
    cap INT NOT NULL,
    spent INT NOT NULL DEFAULT 0
);
CREATE TRIGGER IF NOT EXISTS receipts_no_update BEFORE UPDATE ON receipts
BEGIN SELECT RAISE(ABORT, 'receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS receipts_no_delete BEFORE DELETE ON receipts
BEGIN SELECT RAISE(ABORT, 'receipts are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;
"""


class StoreError(Exception):
    """Store rule violation. `kind` is a short machine-readable category.

    Kinds: story, epoch, lease, slot, chain, duplicate, budget, argument.
    """

    def __init__(self, message: str, kind: str = "store") -> None:
        super().__init__(message)
        self.kind = kind


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _need_int(value: Any, name: str, minimum: int) -> int:
    if not _is_int(value) or value < minimum:
        raise StoreError(f"{name}: must be an integer >= {minimum}", kind="argument")
    return value


def _need_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoreError(f"{name}: must be a non-empty string", kind="argument")
    return value


def _need_ttl(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise StoreError("ttl_sec: must be a number > 0", kind="argument")
    return float(value)


def _event_hash(prev_hash: str, fields: dict) -> str:
    return hashlib.sha256(prev_hash.encode("utf-8") + canonical_bytes(fields)).hexdigest()


def _iso(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


class Store:
    """SQLite-backed control-plane state. See module docstring."""

    def __init__(self, path: str, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._conn = sqlite3.connect(path, isolation_level=None, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------ lifecycle

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        self._conn.execute("COMMIT")

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
    def _free_slot(conn: sqlite3.Connection, task_id: str) -> None:
        conn.execute(
            "UPDATE slots SET task_id = NULL, worker_id = NULL, expires_at = NULL "
            "WHERE task_id = ?",
            (task_id,),
        )

    def _record_event_locked(
        self, conn: sqlite3.Connection, task_id: str, actor: str, kind: str, payload: Any
    ) -> None:
        last = conn.execute(
            "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = last["hash"] if last is not None else GENESIS_HASH
        fields = {
            "ts": self._now(),
            "task_id": task_id,
            "actor": actor,
            "kind": kind,
            "payload": canonical_bytes(payload).decode("utf-8"),
        }
        conn.execute(
            "INSERT INTO events (ts, task_id, actor, kind, payload, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                fields["ts"], task_id, actor, kind, fields["payload"],
                prev_hash, _event_hash(prev_hash, fields),
            ),
        )

    def _reap_locked(self, conn: sqlite3.Connection, now: float) -> list[sqlite3.Row]:
        rows = conn.execute(
            "SELECT task_id, story_id, attempt FROM leases "
            "WHERE released = 0 AND expires_at <= ? ORDER BY task_id",
            (now,),
        ).fetchall()
        for row in rows:
            conn.execute("UPDATE leases SET released = 2 WHERE task_id = ?", (row["task_id"],))
            self._free_slot(conn, row["task_id"])
            self._record_event_locked(
                conn, row["task_id"], "store", "LEASE_EXPIRED", {"attempt": row["attempt"]}
            )
        return rows

    # ---------------------------------------------------------------- slots

    def init_slots(self, n: int) -> None:
        """Create slots 1..n (idempotent; existing slots are kept)."""
        _need_int(n, "n", 1)
        with self._tx() as conn:
            for slot_no in range(1, n + 1):
                conn.execute("INSERT OR IGNORE INTO slots (slot_no) VALUES (?)", (slot_no,))

    # -------------------------------------------------------------- stories

    def open_story(self, story_id: str, project_id: str, phase: int) -> int:
        """Create a story at epoch 1 with no owner; raises if it already exists."""
        _need_str(story_id, "story_id")
        _need_str(project_id, "project_id")
        _need_int(phase, "phase", 1)
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
        wins becomes the owner for ttl_sec; leases of the previous epoch are
        fenced (released = 2, slots freed) so a zombie cannot keep a slot.
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
            conn.execute(
                "UPDATE stories SET epoch = ?, owner = ?, owner_expires_at = ?, "
                "state = 'OWNED' WHERE story_id = ?",
                (new_epoch, owner, now + ttl, story_id),
            )
            old = conn.execute(
                "SELECT task_id, attempt FROM leases WHERE story_id = ? AND released = 0 "
                "ORDER BY task_id",
                (story_id,),
            ).fetchall()
            for row in old:
                conn.execute(
                    "UPDATE leases SET released = 2 WHERE task_id = ?", (row["task_id"],)
                )
                self._free_slot(conn, row["task_id"])
                self._record_event_locked(
                    conn, row["task_id"], "store", "LEASE_FENCED",
                    {"attempt": row["attempt"], "new_epoch": new_epoch},
                )
            self._record_event_locked(
                conn, story_id, owner, "EPOCH_ACQUIRED", {"epoch": new_epoch}
            )
        return new_epoch

    # --------------------------------------------------------------- leases

    def acquire_lease(
        self,
        task_id: str,
        story_id: str,
        worker_id: str,
        epoch: int,
        attempt: int,
        ttl_sec: float,
    ) -> None:
        """Take a lease and a free slot in one transaction.

        Raises StoreError for a stale epoch, a live lease on the task, no free
        slot, a non-increasing attempt, or a previous attempt that was lost and
        not yet marked by supervisor_reap_and_mark (failures are never erased).
        """
        _need_str(task_id, "task_id")
        _need_str(worker_id, "worker_id")
        _need_int(epoch, "epoch", 1)
        _need_int(attempt, "attempt", 1)
        ttl = _need_ttl(ttl_sec)
        with self._tx() as conn:
            now = self._now()
            self._reap_locked(conn, now)
            story = self._story_row(conn, story_id)
            if int(story["epoch"]) != epoch:
                raise StoreError(
                    f"stale epoch {epoch}; current is {story['epoch']}", kind="epoch"
                )
            prior = conn.execute(
                "SELECT * FROM leases WHERE task_id = ?", (task_id,)
            ).fetchone()
            if prior is not None:
                self._check_prior_lease(conn, prior, task_id, attempt)
            claimed = conn.execute(
                "UPDATE slots SET task_id = ?, worker_id = ?, expires_at = ? "
                "WHERE slot_no = (SELECT MIN(slot_no) FROM slots WHERE task_id IS NULL)",
                (task_id, worker_id, now + ttl),
            )
            if claimed.rowcount != 1:
                raise StoreError("no free slot", kind="slot")
            conn.execute(
                "INSERT OR REPLACE INTO leases "
                "(task_id, story_id, attempt, worker_id, epoch, expires_at, released, marked) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, 0)",
                (task_id, story_id, attempt, worker_id, epoch, now + ttl),
            )
            self._record_event_locked(
                conn, task_id, worker_id, "LEASE_ACQUIRED",
                {"attempt": attempt, "epoch": epoch},
            )

    @staticmethod
    def _check_prior_lease(
        conn: sqlite3.Connection, prior: sqlite3.Row, task_id: str, attempt: int
    ) -> None:
        if prior["released"] == 0:
            raise StoreError(f"live lease exists for task {task_id!r}", kind="lease")
        if attempt <= prior["attempt"]:
            raise StoreError(
                f"attempt {attempt} must exceed previous attempt {prior['attempt']}",
                kind="lease",
            )
        if prior["released"] == 2 and prior["marked"] == 0:
            has_receipt = conn.execute(
                "SELECT 1 FROM receipts WHERE task_id = ? AND attempt = ?",
                (task_id, prior["attempt"]),
            ).fetchone()
            if has_receipt is None:
                raise StoreError(
                    f"attempt {prior['attempt']} of task {task_id!r} was lost and "
                    "must be marked by supervisor_reap_and_mark first",
                    kind="lease",
                )

    def _live_lease(
        self, conn: sqlite3.Connection, task_id: str, worker_id: str, epoch: int, now: float
    ) -> sqlite3.Row:
        lease = conn.execute("SELECT * FROM leases WHERE task_id = ?", (task_id,)).fetchone()
        if lease is None or lease["released"] != 0:
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
        _need_int(epoch, "epoch", 1)
        ttl = _need_ttl(ttl_sec)
        with self._tx() as conn:
            now = self._now()
            self._live_lease(conn, task_id, worker_id, epoch, now)
            conn.execute(
                "UPDATE leases SET expires_at = ? WHERE task_id = ?", (now + ttl, task_id)
            )
            conn.execute(
                "UPDATE slots SET expires_at = ? WHERE task_id = ?", (now + ttl, task_id)
            )

    def release_lease(self, task_id: str, worker_id: str, epoch: int) -> None:
        """Release a live lease (released = 1) and free its slot."""
        _need_int(epoch, "epoch", 1)
        with self._tx() as conn:
            now = self._now()
            self._live_lease(conn, task_id, worker_id, epoch, now)
            conn.execute("UPDATE leases SET released = 1 WHERE task_id = ?", (task_id,))
            self._free_slot(conn, task_id)
            self._record_event_locked(conn, task_id, worker_id, "LEASE_RELEASED", {})

    def reap_expired(self) -> list[str]:
        """Mark expired leases released (2), free their slots, return task ids."""
        with self._tx() as conn:
            rows = self._reap_locked(conn, self._now())
        return [row["task_id"] for row in rows]

    # ------------------------------------------------------------- receipts

    def append_receipt(self, receipt: dict, story_id: str) -> None:
        """Validate and append one receipt; never overwrites.

        Rejects (StoreError): epoch != current epoch of the story (kind
        'epoch'); attempt not equal to last attempt + 1 for (task_id, slot), or
        prev_receipt_sha256 not equal to the previous receipt's hash (kind
        'chain'); duplicate receipt_id (kind 'duplicate'). ContractError is
        raised by contracts.validate_receipt for malformed receipts.
        """
        with self._tx() as conn:
            self._append_receipt_locked(conn, receipt, story_id)

    def _append_receipt_locked(
        self, conn: sqlite3.Connection, receipt: dict, story_id: str
    ) -> str:
        valid = validate_receipt(receipt)
        story = self._story_row(conn, story_id)
        if valid["epoch"] != int(story["epoch"]):
            raise StoreError(
                f"stale epoch {valid['epoch']}; current is {story['epoch']}", kind="epoch"
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
        self._record_event_locked(
            conn, valid["task_id"], valid["runner_id"], "RECEIPT_APPENDED",
            {"receipt_id": valid["receipt_id"], "sha256": digest, "result": valid["result"]},
        )
        return digest

    def receipts_for_task(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT body FROM receipts WHERE task_id = ? ORDER BY seq", (task_id,)
        ).fetchall()
        return [json.loads(row["body"]) for row in rows]

    # --------------------------------------------------------------- events

    def record_event(self, task_id: str, actor: str, kind: str, payload: Any) -> None:
        """Append a hash-chained event: hash = sha256(prev_hash + canonical row fields)."""
        _need_str(task_id, "task_id")
        _need_str(actor, "actor")
        _need_str(kind, "kind")
        with self._tx() as conn:
            self._record_event_locked(conn, task_id, actor, kind, payload)

    def verify_event_chain(self) -> bool:
        """True iff every event links to its predecessor and its hash is recomputable."""
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
            if row["prev_hash"] != prev_hash or row["hash"] != _event_hash(prev_hash, fields):
                return False
            prev_hash = row["hash"]
        return True

    # --------------------------------------------------------------- budget

    def set_budget(self, task_id: str, cap: int) -> None:
        """Create or change the cap of a task; spent is preserved."""
        _need_str(task_id, "task_id")
        _need_int(cap, "cap", 0)
        with self._tx() as conn:
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
        _need_int(amount, "amount", 0)
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

    def supervisor_reap_and_mark(
        self, manifest_lookup: Callable[[str], dict], key: bytes, runner_id: str
    ) -> list[dict]:
        """Reap expired leases and write supervisor receipts for lost attempts.

        For every reaped lease (released = 2, not yet marked) without any
        receipt for (task_id, attempt), build, sign and append a Documentation
        receipt:
        - result INCONCLUSIVE, check_description 'WORKER_LOST'; or, when the
          lease attempt exceeds manifest retry_cap + 1, result BLOCKED and
          check_description 'RETRY_EXHAUSTED'.
        Slot rule: the first required_receipts entry whose receipt_type is
        Documentation; if the manifest has none, the first entry (the gate then
        reports a type mismatch, still a non-approval). The receipt attempt is
        the next attempt of that slot's chain (last + 1, or 1) so the chain
        stays gap-free; it carries the story's CURRENT epoch and the
        candidate_head of the task's latest receipt (else manifest base_head).
        All receipts are written in one transaction; returns them.
        """
        _need_str(runner_id, "runner_id")
        written: list[dict] = []
        with self._tx() as conn:
            self._reap_locked(conn, self._now())
            lost = conn.execute(
                "SELECT task_id, story_id, attempt FROM leases "
                "WHERE released = 2 AND marked = 0 ORDER BY task_id"
            ).fetchall()
            for lease in lost:
                has_receipt = conn.execute(
                    "SELECT 1 FROM receipts WHERE task_id = ? AND attempt = ?",
                    (lease["task_id"], lease["attempt"]),
                ).fetchone()
                if has_receipt is None:
                    manifest = validate_task_manifest(manifest_lookup(lease["task_id"]))
                    written.append(self._mark_lost(conn, lease, manifest, key, runner_id))
                conn.execute(
                    "UPDATE leases SET marked = 1 WHERE task_id = ?", (lease["task_id"],)
                )
        return written

    def _mark_lost(
        self,
        conn: sqlite3.Connection,
        lease: sqlite3.Row,
        manifest: dict,
        key: bytes,
        runner_id: str,
    ) -> dict:
        task_id = lease["task_id"]
        slots = manifest["required_receipts"]
        chosen = next((s for s in slots if s["receipt_type"] == "Documentation"), slots[0])
        slot = chosen["slot"]
        exhausted = lease["attempt"] > manifest["retry_cap"] + 1
        story = self._story_row(conn, lease["story_id"])
        last = conn.execute(
            "SELECT attempt, receipt_sha256 FROM receipts WHERE task_id = ? AND slot = ? "
            "ORDER BY attempt DESC LIMIT 1",
            (task_id, slot),
        ).fetchone()
        newest = conn.execute(
            "SELECT body FROM receipts WHERE task_id = ? ORDER BY seq DESC LIMIT 1", (task_id,)
        ).fetchone()
        head = json.loads(newest["body"])["candidate_head"] if newest else manifest["base_head"]
        attempt = 1 if last is None else last["attempt"] + 1
        reason = "RETRY_EXHAUSTED" if exhausted else "WORKER_LOST"
        body = {
            "receipt_id": f"sup-{task_id}-{slot}-{attempt}",
            "receipt_type": "Documentation",
            "task_id": task_id,
            "slot": slot,
            "attempt": attempt,
            "prev_receipt_sha256": None if last is None else last["receipt_sha256"],
            "candidate_head": head,
            "epoch": int(story["epoch"]),
            "runner_id": runner_id,
            "role_sha256": manifest["role_sha256"],
            "resolved_model": "supervisor",
            "invocation_id": f"supervisor-{task_id}-{lease['attempt']}",
            "result": "BLOCKED" if exhausted else "INCONCLUSIVE",
            "created_at": _iso(self._now()),
            "check_description": reason,
            "covered_acceptance": [],
        }
        body["signature"] = sign(dict(body), key)
        self._append_receipt_locked(conn, body, lease["story_id"])
        return body

    # --------------------------------------------------------------- render

    def render_state_md(self, story_id: str) -> str:
        """Deterministic read-only markdown view of one story."""
        story = self._story_row(self._conn, story_id)
        leases = self._conn.execute(
            "SELECT * FROM leases WHERE story_id = ? ORDER BY task_id", (story_id,)
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
            "| task | attempt | worker | epoch | expires_at | status |",
            "|---|---|---|---|---|---|",
        ]
        status = {0: "live", 1: "released", 2: "expired"}
        for lease in leases:
            lines.append(
                f"| {_cell(lease['task_id'])} | {lease['attempt']} | {_cell(lease['worker_id'])} "
                f"| {lease['epoch']} | {lease['expires_at']!r} | {status.get(lease['released'], '?')} |"
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
