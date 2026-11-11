"""U5-3: migration, rollback point and restore for the pipeline schema extension.

Procedure (see docs/sdlc/u5/PIPELINE_STATE.md):
1. `migrate_pipeline(db_path)` takes an exclusive lock file (`<db>.migrate.lock`), checks the store
   schema (`PRAGMA user_version` must be exactly store.SCHEMA_VERSION) and the pipeline version,
   writes a ROLLBACK POINT (SQLite online backup plus a manifest holding the versions, the sha256 of
   the backup file and a digest of all rows) into `<db>.rollback/`, records a STARTED journal entry
   and applies the DDL inside ONE `BEGIN IMMEDIATE` transaction. Before COMMIT it proves that every
   pre-existing (non pl_) table, trigger and row is unchanged. Any failure rolls the transaction
   back, so the database is at the old version or at the new one, never in between.
2. `migration_status` tells NOT_MIGRATED, CURRENT, INTERRUPTED (journal STARTED, database still at
   the old version: re-run `migrate_pipeline` to resume) or COMMIT_UNRECORDED (committed, journal not
   closed: re-run to close it). Pipeline tables without a version row, or a version row that does not
   match the tables, raise MigrationError(kind='partial').
3. `restore_rollback_point(db_path, manifest_path)` verifies the manifest and the backup file first
   (size, sha256, SQLite integrity_check, row digest, versions), then takes a "pre-restore" rollback
   point of the current database and restores the backup over it with the online backup API, then
   proves that the restored rows digest equals the manifest.

Fail closed: a newer unknown store or pipeline version, a corrupted or foreign backup, a held lock
and a database that is not a file are all refused with MigrationError (a StoreError subclass).
Stale locks are never broken automatically (a dead process cannot be told from a live one on this
platform); `clear_stale_lock` needs the token read from the lock file. The manifest detects accidental
corruption; it is NOT a signature and does not stop an attacker who can edit both files.

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
    pipeline_schema_statements,
)
from .store import SCHEMA_VERSION as STORE_SCHEMA_VERSION, StoreError

MANIFEST_FORMAT = "vst-rollback-point-v1"
JOURNAL_NAME = "migration.journal.json"
JOURNAL_FORMAT = "vst-pipeline-migration-journal-v1"
LOCK_SUFFIX = ".migrate.lock"
ROLLBACK_SUFFIX = ".rollback"
POINT_KINDS = ("pre-migration", "pre-restore")
_MANIFEST_KEYS = {
    "format", "kind", "backup_file", "size", "sha256", "content_sha256",
    "store_user_version", "pipeline_version", "created_at",
}
_JOURNAL_STATES = ("STARTED", "COMMITTED", "ABORTED", "RESTORED")
_HEX64 = frozenset("0123456789abcdef")


class MigrationError(StoreError):
    """Migration or rollback rule violation. kind: locked, schema, newer, partial, backup, restore, migration."""

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


# ------------------------------------------------------------------ content digest
def content_digest(conn: sqlite3.Connection, *, exclude_prefix: str | None = None) -> str:
    """sha256 over the logical content: user_version, every schema object and every row.

    Rows are read in rowid order; `sqlite_sequence` (AUTOINCREMENT counters) is included.
    With `exclude_prefix` the objects whose name starts with it (and their rows) are left out;
    `pl_` leaves exactly the pre-existing store content.
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
        if kind == "table":
            try:
                cursor = conn.execute(f"SELECT rowid, * FROM {_quote(name)} ORDER BY rowid")
            except sqlite3.OperationalError as exc:
                raise MigrationError(f"cannot read table {name!r} for the content digest: {exc}", kind="schema") from exc
            for row in cursor:
                feed("row:" + name, [_cell(value) for value in tuple(row)])
    has_sequence = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
    ).fetchone()
    if has_sequence is not None:
        for name, seq in (tuple(row) for row in conn.execute("SELECT name, seq FROM sqlite_sequence ORDER BY name")):
            if exclude_prefix and name.startswith(exclude_prefix):
                continue
            feed("sequence", [name, seq])
    return digest.hexdigest()


# ------------------------------------------------------------------ version detection
def pipeline_version(conn: sqlite3.Connection) -> int:
    """0 when no pl_ table exists, else the recorded version. Inconsistent states raise.

    kind 'partial': pl_ tables without a version table or row, or tables that do not match the
    recorded version. kind 'newer': a version above what this code knows.
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
        "SELECT version FROM pl_schema_version WHERE component = ?", (PIPELINE_COMPONENT,)
    ).fetchone()
    if row is None:
        raise MigrationError("pl_schema_version has no pipeline row (partial migration)", kind="partial")
    version = tuple(row)[0]
    if type(version) is not int or version < 1:
        raise MigrationError("pipeline schema version is malformed", kind="partial")
    if version > PIPELINE_SCHEMA_VERSION:
        raise MigrationError(
            f"pipeline schema version {version} is newer than supported {PIPELINE_SCHEMA_VERSION}", kind="newer"
        )
    if names != set(PIPELINE_TABLES):
        raise MigrationError("pipeline tables do not match the recorded version (partial migration)", kind="partial")
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
    """Exclusive lock file `<db>.migrate.lock`, created with O_EXCL. Never broken automatically."""

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

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if not self._held:
            return
        self._held = False
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
    clock: Callable[[], float] = time.time,
) -> RollbackPoint:
    """SQLite online backup of the whole database into `<db>.rollback/` plus a manifest."""
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
        "content_sha256": content, "store_user_version": store_version, "pipeline_version": pv,
        "created_at": _iso(created),
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
            or name in (".", "..") or not name.endswith(".sqlite")):
        raise MigrationError("rollback manifest names an unsafe backup file", kind="backup")
    if (manifest["kind"] not in POINT_KINDS or not _is_hex64(manifest["sha256"])
            or not _is_hex64(manifest["content_sha256"]) or type(manifest["size"]) is not int
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
        finally:
            check.close()
    except sqlite3.DatabaseError as exc:
        raise MigrationError(f"rollback backup is not a readable SQLite database: {exc}", kind="backup") from exc
    return RollbackPoint(
        manifest_path=manifest_path, backup_path=backup_path, kind=manifest["kind"],
        store_user_version=manifest["store_user_version"], pipeline_version=manifest["pipeline_version"],
        sha256=sha, content_sha256=manifest["content_sha256"], size=size, created_at=manifest["created_at"],
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
def migrate_pipeline(
    db_path: str, *, busy_timeout_sec: float = 30.0, clock: Callable[[], float] = time.time,
    fault: Callable[[str], None] | None = None,
) -> MigrationResult:
    """Bring the pipeline schema from version 0 to PIPELINE_SCHEMA_VERSION; see the module docstring.

    `fault(stage)` is a test seam called at 'before_ddl', 'mid_ddl' and 'before_commit' (inside the
    transaction; raising rolls it back) and at 'after_commit' (raising there simulates a crash after
    COMMIT and before the journal is closed). Production callers leave it None.
    """
    _need_db_file(db_path)
    hook = fault or (lambda stage: None)
    with MigrationLock(db_path):
        conn = _connect(db_path, busy_timeout_sec)
        try:
            _store_version(conn)
            current = pipeline_version(conn)
        finally:
            conn.close()
        journal = _read_journal(db_path)
        interrupted = journal is not None and journal["state"] == "STARTED"
        if current == PIPELINE_SCHEMA_VERSION:
            if interrupted:
                _write_journal(db_path, "COMMITTED", journal["from_version"], journal["to_version"],
                               journal.get("rollback_manifest"), "closed by a later run")
            return MigrationResult(current, current, False, interrupted, None)
        point = create_rollback_point(db_path, kind="pre-migration", busy_timeout_sec=busy_timeout_sec, clock=clock)
        _write_journal(db_path, "STARTED", current, PIPELINE_SCHEMA_VERSION, os.path.basename(point.manifest_path))
        conn = _connect(db_path, busy_timeout_sec)
        try:
            try:
                _apply_pipeline_v1(conn, clock, hook)
            except BaseException as exc:
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


def _apply_pipeline_v1(conn: sqlite3.Connection, clock: Callable[[], float], hook: Callable[[str], None]) -> None:
    statements = pipeline_schema_statements()
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Re-read inside the write lock: the first read was outside any transaction.
        _store_version(conn)
        if pipeline_version(conn) != 0:
            raise MigrationError("pipeline schema changed while the migration waited for the lock", kind="partial")
        before = content_digest(conn, exclude_prefix=PIPELINE_PREFIX)
        hook("before_ddl")
        for index, statement in enumerate(statements):
            conn.execute(statement)
            if index == len(statements) // 2:
                hook("mid_ddl")
        conn.execute(
            "INSERT INTO pl_schema_version (component, version, applied_at) VALUES (?, ?, ?)",
            (PIPELINE_COMPONENT, PIPELINE_SCHEMA_VERSION, float(clock())),
        )
        hook("before_commit")
        if pipeline_version(conn) != PIPELINE_SCHEMA_VERSION:
            raise MigrationError("pipeline schema is not complete after the migration", kind="partial")
        if content_digest(conn, exclude_prefix=PIPELINE_PREFIX) != before:
            raise MigrationError("migration changed pre-existing store content", kind="migration")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise MigrationError("foreign key check failed after the migration", kind="migration")
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            with contextlib.suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
        raise


# ------------------------------------------------------------------ restore
def restore_rollback_point(
    db_path: str, manifest_path: str, *, busy_timeout_sec: float = 30.0, clock: Callable[[], float] = time.time,
) -> RestoreResult:
    """Return the store to the exact state captured by a verified rollback point.

    Stop every writer first: SQLite refuses the restore while another connection holds a lock
    (kind 'restore'), and a Store object that stays open must be reopened afterwards.
    """
    _need_db_file(db_path)
    directory = os.path.realpath(rollback_dir(db_path))
    if os.path.realpath(os.path.dirname(os.path.abspath(manifest_path))) != directory:
        raise MigrationError("the rollback manifest does not belong to this store's rollback directory", kind="backup")
    with MigrationLock(db_path):
        point = load_rollback_point(manifest_path)  # refuse a corrupted backup before touching the store
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
                       os.path.basename(point.manifest_path))
        return RestoreResult(version, pv, digest, safety.manifest_path)
