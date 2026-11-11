"""U5-3: migration, rollback point, restore and down-migration for the pipeline schema extension.

Procedure (see docs/sdlc/u5/PIPELINE_STATE.md):
1. `migrate_pipeline(db_path)` takes an exclusive lock file (`<db>.migrate.lock`), then opens the write
   transaction (`BEGIN IMMEDIATE`) FIRST. From that locked state it writes a ROLLBACK POINT (SQLite online
   backup through a second connection, a reader snapshot in WAL, plus a manifest holding the versions, the
   sha256 of the backup file, a digest of all rows and a cheap state invariant) and asserts that the
   invariant of the backup equals the invariant of the locked state, so a point from any other state is
   never accepted. Then it applies the DDL, proves that every non-pl_ object is unchanged by the same
   cheap invariant (non-pl_ `sqlite_master` rows, per-table row count and max rowid, sequences), checks
   the frozen schema hash and COMMITs. Any failure rolls the transaction back: the database is at the old
   version or at the new one, never in between.
   Lock time: the live database is only scanned with the cheap invariant; the full row digest is computed
   on the backup copy. The backup and its digest are made while the write lock is held, because the
   rollback point must be complete and verified before the first DDL statement; the cost grows with the
   store size (documented limit).
2. `migration_status` tells NOT_MIGRATED, CURRENT, INTERRUPTED, COMMIT_UNRECORDED. Pipeline tables without
   a version row, tables or triggers that differ from the frozen v1 schema hash: MigrationError('partial').
3. `restore_rollback_point(db_path, manifest_path, confirm_stopped=True)` is a WHOLE-STORE restore: events,
   receipts, leases, budget and every other row written after the point are lost, and an external event
   anchor then no longer matches the database. It refuses unless the caller attests that the store is
   stopped and a `BEGIN EXCLUSIVE` probe succeeds, and unless the point's store schema version equals the
   current one (override `allow_store_version_change=True`, recorded in the journal).
4. `down_migrate_pipeline(db_path)` is the scoped rollback of this schema change: it drops only the pl_
   objects and refuses when pl_ rows exist unless `allow_data_loss=True`; nothing else in the store changes.

Fail closed: a newer unknown store or pipeline version, a corrupted or foreign backup, a held lock and a
database that is not a file are refused with MigrationError (a StoreError subclass). Stale locks are never
broken automatically; `clear_stale_lock` needs the token read from the lock file, and a holder removes the
lock only if the file still carries its own token. The manifest detects accidental corruption; it is NOT a
signature.

Standard library only; no network.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .pipeline_schema import (
    PIPELINE_COMPONENT,
    PIPELINE_PREFIX,
    PIPELINE_SCHEMA_VERSION,
    PIPELINE_TABLES,
    expected_schema_sha256,
    pipeline_schema_statements,
    schema_sha256,
)
from .store import SCHEMA_VERSION as STORE_SCHEMA_VERSION, StoreError

MANIFEST_FORMAT = "vst-rollback-point-v1"
JOURNAL_NAME = "migration.journal.json"
JOURNAL_FORMAT = "vst-pipeline-migration-journal-v1"
LOCK_SUFFIX = ".migrate.lock"
ROLLBACK_SUFFIX = ".rollback"
POINT_KINDS = ("pre-migration", "pre-restore", "pre-down-migration")
_MANIFEST_KEYS = {
    "format", "kind", "backup_file", "size", "sha256", "content_sha256", "invariant_sha256",
    "store_user_version", "pipeline_version", "created_at",
}
_JOURNAL_STATES = ("STARTED", "COMMITTED", "ABORTED", "RESTORED", "DOWNGRADED")
_HEX64 = frozenset("0123456789abcdef")
# children first, so DROP TABLE never meets a referencing row
_DROP_ORDER = (
    "pl_receipt_links", "pl_test_evidence", "pl_review_iterations", "pl_diff_gates", "pl_patch_proposals",
    "pl_worker_attempts", "pl_story_control", "pl_steps", "pl_schema_version",
)


class MigrationError(StoreError):
    """Migration or rollback rule violation. kind: locked, schema, newer, partial, backup, restore, data, migration."""

    def __init__(self, message: str, kind: str = "migration") -> None:
        super().__init__(message, kind=kind)


@dataclass(frozen=True)
class RollbackPoint:
    manifest_path: str
    backup_path: str
    kind: str
    store_user_version: int
    pipeline_version: int | None
    sha256: str
    content_sha256: str
    invariant_sha256: str
    size: int
    created_at: str


@dataclass(frozen=True)
class MigrationResult:
    from_version: int
    to_version: int
    performed: bool          # False: nothing to migrate (already current)
    resumed: bool            # True: an earlier interrupted attempt was found and superseded or closed
    rollback_manifest: str | None


@dataclass(frozen=True)
class RestoreResult:
    store_user_version: int
    pipeline_version: int | None
    content_sha256: str
    pre_restore_manifest: str


@dataclass(frozen=True)
class DownMigrationResult:
    from_version: int
    to_version: int
    rows_dropped: int
    rollback_manifest: str | None


# ------------------------------------------------------------------ paths and small helpers
def rollback_dir(db_path: str) -> str:
    return db_path + ROLLBACK_SUFFIX


def _journal_path(db_path: str) -> str:
    return os.path.join(rollback_dir(db_path), JOURNAL_NAME)


def _need_db_file(db_path: object) -> str:
    if not isinstance(db_path, str) or not db_path:
        raise MigrationError("db_path: must be a non-empty string", kind="schema")
    if not os.path.isfile(db_path):
        # sqlite3.connect would silently create an empty database; refuse instead.
        raise MigrationError(f"store file does not exist: {db_path!r}", kind="schema")
    return db_path


def _connect(path: str, busy_timeout_sec: float) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, timeout=float(busy_timeout_sec))
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _replace(source: str, target: str) -> None:
    """os.replace with a short retry: Windows briefly refuses it (winerror 5 or 32)."""
    for attempt in range(12):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(0.05 * (attempt + 1))


def _write_bytes_atomic(path: str, data: bytes) -> None:
    tmp = path + "." + uuid.uuid4().hex[:8] + ".tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _replace(tmp, path)


def _file_sha256(path: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX64


def _iso(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _cell(value: object) -> object:
    if isinstance(value, bytes):
        return {"blob": value.hex()}
    return value


# ------------------------------------------------------------------ content digest and cheap invariant
def content_digest(conn: sqlite3.Connection, *, exclude_prefix: str | None = None, rows: bool = True) -> str:
    """sha256 over the logical content: user_version, every schema object and (rows=True) every row.

    Rows are read in rowid order; `sqlite_sequence` (AUTOINCREMENT counters) is included. With
    `rows=False` a table contributes only its row count and max rowid (the cheap invariant, see
    `state_invariant`). With `exclude_prefix` the objects whose name starts with it are left out.
    """
    digest = hashlib.sha256()

    def feed(label: str, payload: object) -> None:
        data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        digest.update(label.encode("ascii") + b":" + str(len(data)).encode("ascii") + b":" + data + b"\n")

    feed("user_version", conn.execute("PRAGMA user_version").fetchone()[0])
    objects = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE substr(name, 1, 7) != 'sqlite_' ORDER BY type, name"
    ).fetchall()
    for kind, name, table_name, sql in (tuple(row) for row in objects):
        if exclude_prefix and (name.startswith(exclude_prefix) or table_name.startswith(exclude_prefix)):
            continue
        feed("object", [kind, name, table_name, sql])
        if kind != "table":
            continue
        try:
            if rows:
                for row in conn.execute(f"SELECT rowid, * FROM {_quote(name)} ORDER BY rowid"):
                    feed("row:" + name, [_cell(value) for value in tuple(row)])
            else:
                total, top = conn.execute(f"SELECT COUNT(*), COALESCE(MAX(rowid), 0) FROM {_quote(name)}").fetchone()
                feed("table:" + name, [total, top])
        except sqlite3.OperationalError as exc:
            raise MigrationError(f"cannot read table {name!r} for the content digest: {exc}", kind="schema") from exc
    has_sequence = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
    ).fetchone()
    if has_sequence is not None:
        for name, seq in (tuple(row) for row in conn.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name")):
            if exclude_prefix and name.startswith(exclude_prefix):
                continue
            feed("sequence", [name, seq])
    return digest.hexdigest()


def state_invariant(conn: sqlite3.Connection) -> str:
    """Cheap fingerprint of the store without the pipeline objects: user_version, non-pl_ schema entries,
    per-table row count and max rowid, sequences. Used inside the write lock instead of a full row scan.
    It does not see an UPDATE that keeps counts and max rowid; the full digest of the backup covers rows."""
    return content_digest(conn, exclude_prefix=PIPELINE_PREFIX, rows=False)


# ------------------------------------------------------------------ version detection
def pipeline_version(conn: sqlite3.Connection) -> int:
    """0 when no pl_ table exists, else the recorded version. Inconsistent states raise.

    kind 'partial': pl_ tables without a version table or row, tables that do not match the recorded
    version, or a schema (triggers, indexes, CHECKs) that differs from the frozen v1 hash.
    kind 'newer': a version above what this code knows.
    """
    names = {
        tuple(row)[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND substr(name, 1, 3) = ?",
            (PIPELINE_PREFIX,),
        )
    }
    if not names:
        return 0
    if "pl_schema_version" not in names:
        raise MigrationError("pipeline tables exist without pl_schema_version (partial migration)", kind="partial")
    row = conn.execute(
        "SELECT version, schema_sha256 FROM pl_schema_version WHERE component = ?", (PIPELINE_COMPONENT,)
    ).fetchone()
    if row is None:
        raise MigrationError("pl_schema_version has no pipeline row (partial migration)", kind="partial")
    version, stored_hash = tuple(row)
    if type(version) is not int or version < 1:
        raise MigrationError("pipeline schema version is malformed", kind="partial")
    if version > PIPELINE_SCHEMA_VERSION:
        raise MigrationError(
            f"pipeline schema version {version} is newer than supported {PIPELINE_SCHEMA_VERSION}", kind="newer"
        )
    if names != set(PIPELINE_TABLES):
        raise MigrationError("pipeline tables do not match the recorded version (partial migration)", kind="partial")
    live = schema_sha256(conn)
    if live != stored_hash or live != expected_schema_sha256():
        raise MigrationError(
            "pipeline schema differs from the frozen v1 schema (a trigger, index or constraint changed)", kind="partial"
        )
    return version


def _store_version(conn: sqlite3.Connection) -> int:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > STORE_SCHEMA_VERSION:
        raise MigrationError(
            f"store schema version {version} is newer than supported {STORE_SCHEMA_VERSION}", kind="newer"
        )
    if version != STORE_SCHEMA_VERSION:
        raise MigrationError(
            f"store schema version {version} is not {STORE_SCHEMA_VERSION}; upgrade the store first", kind="schema"
        )
    return version


# ------------------------------------------------------------------ lock
class MigrationLock:
    """Exclusive lock file `<db>.migrate.lock`, created with O_EXCL. Never broken automatically.

    The release reads the file and removes it only when it still carries this holder's token.
    """

    def __init__(self, db_path: str) -> None:
        self.path = db_path + LOCK_SUFFIX
        self.token = uuid.uuid4().hex
        self._held = False

    def __enter__(self) -> "MigrationLock":
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError) as exc:
            raise MigrationError(
                f"migration lock is held or stale: {self.path!r} (inspect it; clear_stale_lock needs its token)",
                kind="locked",
            ) from exc
        try:
            os.write(fd, json.dumps({"pid": os.getpid(), "token": self.token}).encode("ascii"))
        finally:
            os.close(fd)
        self._held = True
        return self

    def _stored_token(self) -> str | None:
        for attempt in range(12):
            try:
                with open(self.path, "rb") as handle:
                    doc = json.loads(handle.read().decode("ascii"))
                return doc.get("token") if isinstance(doc, dict) else None
            except FileNotFoundError:
                return None
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
            except (OSError, ValueError):
                return None
        return None

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if not self._held:
            return
        self._held = False
        if not os.path.exists(self.path):
            return
        if self._stored_token() != self.token:
            # Another holder owns the file now (it was cleared and re-taken): never remove it.
            if exc_type is None:
                raise MigrationError(f"migration lock {self.path!r} no longer carries this holder's token", kind="locked")
            return
        for attempt in range(12):
            try:
                os.remove(self.path)
                return
            except FileNotFoundError:
                return
            except PermissionError:
                time.sleep(0.05 * (attempt + 1))
        raise MigrationError(f"could not release the migration lock {self.path!r}", kind="locked")


def clear_stale_lock(db_path: str, token: str) -> None:
    """Remove a lock left by a dead process. The caller must present the token stored in the file."""
    path = db_path + LOCK_SUFFIX
    try:
        with open(path, "rb") as handle:
            stored = json.loads(handle.read().decode("ascii"))
    except FileNotFoundError:
        return
    except (OSError, ValueError) as exc:
        raise MigrationError(f"lock file {path!r} is unreadable; remove it by hand after inspection", kind="locked") from exc
    if not isinstance(stored, dict) or stored.get("token") != token or not isinstance(token, str) or not token:
        raise MigrationError("lock token does not match; refusing to clear the lock", kind="locked")
    os.remove(path)


# ------------------------------------------------------------------ rollback points
def create_rollback_point(
    db_path: str, *, kind: str = "pre-migration", busy_timeout_sec: float = 30.0,
    clock: Callable[[], float] = time.time, expect_invariant: str | None = None,
) -> RollbackPoint:
    """SQLite online backup of the whole database into `<db>.rollback/` plus a manifest.

    With `expect_invariant` the backup is refused (kind 'backup') unless its cheap state invariant equals
    it: the caller passes the invariant of the state it is about to change.
    """
    _need_db_file(db_path)
    if kind not in POINT_KINDS:
        raise MigrationError(f"unknown rollback point kind {kind!r}", kind="backup")
    directory = rollback_dir(db_path)
    os.makedirs(directory, exist_ok=True)
    created = clock()
    base = "rp-" + datetime.fromtimestamp(created, timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
    backup_name = base + ".sqlite"
    backup_path = os.path.join(directory, backup_name)
    tmp_path = backup_path + ".tmp"
    source = _connect(db_path, busy_timeout_sec)
    try:
        target = sqlite3.connect(tmp_path, isolation_level=None)
        try:
            source.backup(target)  # consistent snapshot; fails closed with 'database is locked'
            if str(target.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower() != "delete":
                raise MigrationError("the backup could not be made a single self-contained file", kind="backup")
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise MigrationError("the fresh backup failed integrity_check", kind="backup")
            invariant = state_invariant(target)
            if expect_invariant is not None and invariant != expect_invariant:
                raise MigrationError(
                    "the backup is not the state that is being changed (state invariant differs)", kind="backup"
                )
            content = content_digest(target)
            store_version = target.execute("PRAGMA user_version").fetchone()[0]
            try:
                pv: int | None = pipeline_version(target)
            except MigrationError:
                pv = None
        finally:
            target.close()
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp_path)
        raise
    finally:
        source.close()
    _replace(tmp_path, backup_path)
    sha, size = _file_sha256(backup_path)
    manifest = {
        "format": MANIFEST_FORMAT, "kind": kind, "backup_file": backup_name, "size": size, "sha256": sha,
        "content_sha256": content, "invariant_sha256": invariant, "store_user_version": store_version,
        "pipeline_version": pv, "created_at": _iso(created),
    }
    manifest_path = os.path.join(directory, base + ".manifest.json")
    _write_bytes_atomic(manifest_path, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return load_rollback_point(manifest_path)


def load_rollback_point(manifest_path: str) -> RollbackPoint:
    """Verify a rollback point completely (manifest shape, file size and sha256, integrity, row digest)."""
    try:
        with open(manifest_path, "rb") as handle:
            manifest = json.loads(handle.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise MigrationError(f"rollback manifest unreadable: {manifest_path!r}", kind="backup") from exc
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS or manifest["format"] != MANIFEST_FORMAT:
        raise MigrationError("rollback manifest has an unknown shape", kind="backup")
    name = manifest["backup_file"]
    if (not isinstance(name, str) or not name or name != os.path.basename(name)
            or "/" in name or "\\" in name or name in (".", "..") or not name.endswith(".sqlite")):
        raise MigrationError("rollback manifest names an unsafe backup file", kind="backup")
    if (manifest["kind"] not in POINT_KINDS or not _is_hex64(manifest["sha256"])
            or not _is_hex64(manifest["content_sha256"]) or not _is_hex64(manifest["invariant_sha256"])
            or type(manifest["size"]) is not int
            or type(manifest["store_user_version"]) is not int
            or not (manifest["pipeline_version"] is None or type(manifest["pipeline_version"]) is int)
            or not isinstance(manifest["created_at"], str)):
        raise MigrationError("rollback manifest has malformed fields", kind="backup")
    backup_path = os.path.join(os.path.dirname(os.path.abspath(manifest_path)), name)
    if not os.path.isfile(backup_path):
        raise MigrationError("rollback backup file is missing", kind="backup")
    sha, size = _file_sha256(backup_path)
    if size != manifest["size"] or sha != manifest["sha256"]:
        raise MigrationError("rollback backup file does not match its manifest (corrupted)", kind="backup")
    try:
        check = sqlite3.connect(backup_path, isolation_level=None)
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise MigrationError("rollback backup failed integrity_check", kind="backup")
            if check.execute("PRAGMA user_version").fetchone()[0] != manifest["store_user_version"]:
                raise MigrationError("rollback backup user_version differs from its manifest", kind="backup")
            if content_digest(check) != manifest["content_sha256"]:
                raise MigrationError("rollback backup rows differ from its manifest", kind="backup")
            if state_invariant(check) != manifest["invariant_sha256"]:
                raise MigrationError("rollback backup invariant differs from its manifest", kind="backup")
        finally:
            check.close()
    except sqlite3.DatabaseError as exc:
        raise MigrationError(f"rollback backup is not a readable SQLite database: {exc}", kind="backup") from exc
    return RollbackPoint(
        manifest_path=manifest_path, backup_path=backup_path, kind=manifest["kind"],
        store_user_version=manifest["store_user_version"], pipeline_version=manifest["pipeline_version"],
        sha256=sha, content_sha256=manifest["content_sha256"], invariant_sha256=manifest["invariant_sha256"],
        size=size, created_at=manifest["created_at"],
    )


# ------------------------------------------------------------------ journal
def _read_journal(db_path: str) -> dict | None:
    path = _journal_path(db_path)
    try:
        with open(path, "rb") as handle:
            doc = json.loads(handle.read().decode("utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise MigrationError("migration journal is unreadable", kind="partial") from exc
    if (not isinstance(doc, dict) or doc.get("format") != JOURNAL_FORMAT
            or doc.get("state") not in _JOURNAL_STATES
            or type(doc.get("from_version")) is not int or type(doc.get("to_version")) is not int):
        raise MigrationError("migration journal is malformed", kind="partial")
    return doc


def _write_journal(db_path: str, state: str, from_version: int, to_version: int, manifest: str | None, note: str = "") -> None:
    os.makedirs(rollback_dir(db_path), exist_ok=True)
    doc = {
        "format": JOURNAL_FORMAT, "state": state, "from_version": from_version, "to_version": to_version,
        "rollback_manifest": manifest, "note": note[:300],
    }
    _write_bytes_atomic(_journal_path(db_path), (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def migration_status(db_path: str, *, busy_timeout_sec: float = 30.0) -> dict:
    """Read-only report: state is NOT_MIGRATED, CURRENT, INTERRUPTED or COMMIT_UNRECORDED."""
    _need_db_file(db_path)
    conn = _connect(db_path, busy_timeout_sec)
    try:
        store_version = conn.execute("PRAGMA user_version").fetchone()[0]
        version = pipeline_version(conn)
    finally:
        conn.close()
    journal = _read_journal(db_path)
    journal_state = None if journal is None else journal["state"]
    if journal_state == "STARTED":
        if version == journal["from_version"]:
            state = "INTERRUPTED"
        elif version == journal["to_version"]:
            state = "COMMIT_UNRECORDED"
        else:
            raise MigrationError("migration journal STARTED but the database is at an unrelated version", kind="partial")
    else:
        state = "CURRENT" if version == PIPELINE_SCHEMA_VERSION else "NOT_MIGRATED"
    return {
        "store_user_version": store_version, "pipeline_version": version,
        "target_version": PIPELINE_SCHEMA_VERSION, "journal_state": journal_state, "state": state,
    }


# ------------------------------------------------------------------ migration
def _rollback_quietly(conn: sqlite3.Connection) -> None:
    if conn.in_transaction:
        with contextlib.suppress(sqlite3.Error):
            conn.execute("ROLLBACK")


def migrate_pipeline(
    db_path: str, *, busy_timeout_sec: float = 30.0, clock: Callable[[], float] = time.time,
    fault: Callable[[str], None] | None = None,
) -> MigrationResult:
    """Bring the pipeline schema from version 0 to PIPELINE_SCHEMA_VERSION; see the module docstring.

    `fault(stage)` is a test seam called at 'after_backup', 'before_ddl', 'mid_ddl' and 'before_commit'
    (inside the transaction; raising rolls it back) and at 'after_commit' (raising there simulates a crash
    after COMMIT and before the journal is closed). Production callers leave it None.
    """
    _need_db_file(db_path)
    hook = fault or (lambda stage: None)
    with MigrationLock(db_path):
        conn = _connect(db_path, busy_timeout_sec)
        point: RollbackPoint | None = None
        current = 0
        interrupted = False
        try:
            conn.execute("BEGIN IMMEDIATE")  # the locked state we migrate; the backup is taken from it
            try:
                _store_version(conn)
                current = pipeline_version(conn)
                journal = _read_journal(db_path)
                interrupted = journal is not None and journal["state"] == "STARTED"
                if current == PIPELINE_SCHEMA_VERSION:
                    conn.execute("ROLLBACK")
                    if interrupted:
                        _write_journal(db_path, "COMMITTED", journal["from_version"], journal["to_version"],
                                       journal.get("rollback_manifest"), "closed by a later run")
                    return MigrationResult(current, current, False, interrupted, None)
                start_state = state_invariant(conn)
                point = create_rollback_point(
                    db_path, kind="pre-migration", busy_timeout_sec=busy_timeout_sec, clock=clock,
                    expect_invariant=start_state,
                )
                _write_journal(db_path, "STARTED", current, PIPELINE_SCHEMA_VERSION, os.path.basename(point.manifest_path))
                hook("after_backup")
                _apply_pipeline_v1(conn, clock, hook, start_state)
            except BaseException as exc:
                _rollback_quietly(conn)
                if point is not None:
                    with contextlib.suppress(Exception):
                        _write_journal(db_path, "ABORTED", current, PIPELINE_SCHEMA_VERSION,
                                       os.path.basename(point.manifest_path), type(exc).__name__)
                if isinstance(exc, Exception) and not isinstance(exc, MigrationError):
                    raise MigrationError(f"pipeline migration failed and was rolled back: {exc}") from exc
                raise
        finally:
            conn.close()
        hook("after_commit")
        _write_journal(db_path, "COMMITTED", current, PIPELINE_SCHEMA_VERSION, os.path.basename(point.manifest_path))
        return MigrationResult(current, PIPELINE_SCHEMA_VERSION, True, interrupted, point.manifest_path)


def _apply_pipeline_v1(
    conn: sqlite3.Connection, clock: Callable[[], float], hook: Callable[[str], None], start_state: str,
) -> None:
    """Runs inside the caller's BEGIN IMMEDIATE and ends with COMMIT; the caller rolls back on any error."""
    statements = pipeline_schema_statements()
    hook("before_ddl")
    for index, statement in enumerate(statements):
        conn.execute(statement)
        if index == len(statements) // 2:
            hook("mid_ddl")
    conn.execute(
        "INSERT INTO pl_schema_version (component, version, schema_sha256, applied_at) VALUES (?, ?, ?, ?)",
        (PIPELINE_COMPONENT, PIPELINE_SCHEMA_VERSION, schema_sha256(conn), float(clock())),
    )
    hook("before_commit")
    if pipeline_version(conn) != PIPELINE_SCHEMA_VERSION:
        raise MigrationError("pipeline schema is not complete after the migration", kind="partial")
    if state_invariant(conn) != start_state:
        raise MigrationError("migration changed pre-existing store content", kind="migration")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise MigrationError("foreign key check failed after the migration", kind="migration")
    conn.execute("COMMIT")


# ------------------------------------------------------------------ down-migration (scoped rollback)
def down_migrate_pipeline(
    db_path: str, *, allow_data_loss: bool = False, busy_timeout_sec: float = 30.0,
    clock: Callable[[], float] = time.time,
) -> DownMigrationResult:
    """Drop the pl_ objects and pl_schema_version atomically; nothing else in the store changes.

    Refused (kind 'data') while any pl_ row besides the version row exists, unless `allow_data_loss=True`.
    A rollback point (kind 'pre-down-migration') is written first. Stop pipeline writers first: a
    PipelineState that stays open refuses its next step because the schema is gone.
    """
    if type(allow_data_loss) is not bool:
        raise MigrationError("allow_data_loss must be a boolean", kind="data")
    _need_db_file(db_path)
    with MigrationLock(db_path):
        conn = _connect(db_path, busy_timeout_sec)
        point: RollbackPoint | None = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                _store_version(conn)
                current = pipeline_version(conn)
                if current == 0:
                    conn.execute("ROLLBACK")
                    return DownMigrationResult(0, 0, 0, None)
                rows_dropped = sum(
                    int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                    for table in _DROP_ORDER if table != "pl_schema_version"
                )
                if rows_dropped and not allow_data_loss:
                    raise MigrationError(
                        f"{rows_dropped} pipeline row(s) exist; pass allow_data_loss=True to drop them", kind="data"
                    )
                start_state = state_invariant(conn)
                point = create_rollback_point(
                    db_path, kind="pre-down-migration", busy_timeout_sec=busy_timeout_sec, clock=clock,
                    expect_invariant=start_state,
                )
                for table in _DROP_ORDER:
                    conn.execute(f"DROP TABLE {table}")  # triggers and indexes of the table go with it
                if pipeline_version(conn) != 0:
                    raise MigrationError("pipeline objects remain after the down-migration", kind="partial")
                if state_invariant(conn) != start_state:
                    raise MigrationError("down-migration changed pre-existing store content", kind="migration")
                if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise MigrationError("foreign key check failed after the down-migration", kind="migration")
                conn.execute("COMMIT")
            except BaseException as exc:
                _rollback_quietly(conn)
                if isinstance(exc, Exception) and not isinstance(exc, MigrationError):
                    raise MigrationError(f"down-migration failed and was rolled back: {exc}") from exc
                raise
        finally:
            conn.close()
        _write_journal(db_path, "DOWNGRADED", current, 0, os.path.basename(point.manifest_path))
        return DownMigrationResult(current, 0, rows_dropped, point.manifest_path)


# ------------------------------------------------------------------ restore (whole store)
def restore_rollback_point(
    db_path: str, manifest_path: str, *, confirm_stopped: bool = False, allow_store_version_change: bool = False,
    busy_timeout_sec: float = 30.0, clock: Callable[[], float] = time.time,
) -> RestoreResult:
    """Return the WHOLE store to the state captured by a verified rollback point.

    Everything written after the point is lost: events (the hash chain and an external anchor then no
    longer match), receipts, leases, budget, phases and all pipeline rows. For the schema change alone use
    `down_migrate_pipeline`. The caller must pass `confirm_stopped=True` (an attestation that no Store,
    worker or supervisor uses the file; idle connections cannot be detected) and a `BEGIN EXCLUSIVE`
    probe on the target must succeed (a live writer makes it fail, kind 'restore'). The point's store
    user_version must equal the current store schema version; `allow_store_version_change=True` overrides
    that and is recorded in the journal. A `pre-restore` point of the current state is written first.
    """
    if confirm_stopped is not True:
        raise MigrationError("restore needs confirm_stopped=True: stop every writer of the store first", kind="restore")
    if type(allow_store_version_change) is not bool:
        raise MigrationError("allow_store_version_change must be a boolean", kind="restore")
    _need_db_file(db_path)
    directory = os.path.realpath(rollback_dir(db_path))
    if os.path.realpath(os.path.dirname(os.path.abspath(manifest_path))) != directory:
        raise MigrationError("the rollback manifest does not belong to this store's rollback directory", kind="backup")
    with MigrationLock(db_path):
        point = load_rollback_point(manifest_path)  # refuse a corrupted backup before touching the store
        note = ""
        if point.store_user_version != STORE_SCHEMA_VERSION:
            if not allow_store_version_change:
                raise MigrationError(
                    f"rollback point has store schema version {point.store_user_version}, current is "
                    f"{STORE_SCHEMA_VERSION}; pass allow_store_version_change=True to restore it anyway",
                    kind="restore",
                )
            note = f"allow_store_version_change: store schema {STORE_SCHEMA_VERSION} -> {point.store_user_version}"
        probe = sqlite3.connect(db_path, isolation_level=None, timeout=min(float(busy_timeout_sec), 1.0))
        try:
            probe.execute("BEGIN EXCLUSIVE")
            probe.execute("ROLLBACK")
        except sqlite3.OperationalError as exc:
            raise MigrationError(f"the store is in use (exclusive probe failed: {exc})", kind="restore") from exc
        finally:
            probe.close()
        safety = create_rollback_point(db_path, kind="pre-restore", busy_timeout_sec=busy_timeout_sec, clock=clock)
        source = sqlite3.connect(point.backup_path, isolation_level=None)
        try:
            target = _connect(db_path, busy_timeout_sec)
            try:
                source.backup(target)
                with contextlib.suppress(sqlite3.Error):
                    target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error as exc:
                raise MigrationError(
                    f"restore failed: {exc}; the store is unchanged or restorable from {safety.manifest_path!r}",
                    kind="restore",
                ) from exc
            finally:
                target.close()
        finally:
            source.close()
        check = _connect(db_path, busy_timeout_sec)
        try:
            ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            version = check.execute("PRAGMA user_version").fetchone()[0]
            digest = content_digest(check)
            try:
                pv: int | None = pipeline_version(check)
            except MigrationError:
                pv = None
        finally:
            check.close()
        if not ok or version != point.store_user_version or digest != point.content_sha256:
            raise MigrationError(
                f"restored store does not match the rollback point; the state before the restore is "
                f"{safety.manifest_path!r}", kind="restore",
            )
        _write_journal(db_path, "RESTORED", point.pipeline_version or 0, PIPELINE_SCHEMA_VERSION,
                       os.path.basename(point.manifest_path), note)
        return RestoreResult(version, pv, digest, safety.manifest_path)
