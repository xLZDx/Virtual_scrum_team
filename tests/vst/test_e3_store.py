"""E3 state store (remediation B): schema, epoch CAS, phase, tasks, lease history,
retry cap, signed receipts, supervisor isolation, keyed event chain, budget, bounds.

Every test drives the public Store API against a real SQLite file. Raw sqlite3
connections are used only to OBSERVE state or to play the attacker (they bypass
the Store). Time is a FakeClock; nothing sleeps.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading

import pytest

from tools.vst import contracts as c
from tools.vst import gate, signing
from tools.vst.store import (
    EVENT_KINDS,
    GENESIS_HASH,
    LEASE_STATUSES,
    MAX_BUDGET,
    MAX_COUNTER,
    MAX_SLOTS,
    MAX_TTL_SEC,
    SCHEMA_VERSION,
    STORY_STATES,
    Store,
    StoreBusyError,
    StoreError,
)

from .e1e4_helpers import (
    EVENT_KEY,
    HEAD,
    HEAD2,
    KEY,
    OPERATOR_KEY,
    OTHER_EVENT_KEY,
    OWNER_TTL,
    STORY,
    STORY2,
    SUPERVISOR_KEY,
    TASK,
    WORKER,
    FakeClock,
    bound,
    doc_manifest,
    lease,
    manifest,
    new_env,
    open_store,
    receipt,
    resign,
    supervisor_receipt,
    unsigned_receipt,
)

SUPERVISOR_SLOT = c.SUPERVISOR_SLOT


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / "state.db")
    store, clock, epoch = new_env(path)
    yield store, clock, path, epoch
    store.close()


# --------------------------------------------------------------------- helpers


def raw(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def rows(path, sql, args=()):
    conn = raw(path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def kinds(path):
    return [r["kind"] for r in rows(path, "SELECT kind FROM events ORDER BY seq")]


def tr(epoch, **kw):
    """Signed default TestRun receipt (task T1, slot tests, runner-1)."""
    return receipt("TestRun", epoch=epoch, **kw)


def slot_map(path):
    return {
        r["slot_no"]: r["task_id"]
        for r in rows(
            path,
            "SELECT s.slot_no, l.task_id FROM slots s LEFT JOIN leases l ON l.lease_id = s.lease_id",
        )
    }


def leases(path):
    return rows(path, "SELECT * FROM leases ORDER BY lease_id")


def reg(store, task_id, **kw):
    m = manifest(task_id=task_id, **kw)
    store.register_task(m)
    return m


def supervisor_receipts(store, task=TASK):
    return [r for r in store.receipts_for_task(task) if r["slot"] == SUPERVISOR_SLOT]


def slot_run(epoch, attempt=1, prev=None, *, task=TASK, m=None, rtype="TestRun", **kw):
    """Signed worker receipt for `task` (bound to manifest m when given)."""
    kw.setdefault("receipt_id", f"{task}-{rtype}-{attempt}")
    kw.setdefault("task_id", task)
    kw["prev_receipt_sha256"] = prev
    if m is None:
        return receipt(rtype, epoch=epoch, attempt=attempt, **kw)
    return bound(m, rtype, KEY, epoch=epoch, attempt=attempt, **kw)


def failed_run(epoch, attempt=1, prev=None, **kw):
    """TestRun receipt that really derives FAIL (a command exited 1)."""
    kw.setdefault("commands", [{"argv": ["pytest", "-q"], "exit_code": 1}])
    kw.setdefault("result", "FAIL")
    return slot_run(epoch, attempt, prev, **kw)


def lose(store, clock, epoch, attempts, task=TASK, ttl=10):
    """Each attempt takes a lease, dies without writing; the supervisor marks it."""
    for attempt in attempts:
        lease(store, epoch, task=task, attempt=attempt, ttl=ttl)
        clock.advance(ttl)
        assert len(store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")) == 1


def assert_no_dangling_transaction(path):
    """A fresh writer must get the lock at once: the Store left no open transaction."""
    conn = sqlite3.connect(path, isolation_level=None, timeout=0.2)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
    finally:
        conn.close()


def raises_kind(kind, fn, *args, **kwargs):
    with pytest.raises(StoreError) as exc:
        fn(*args, **kwargs)
    assert exc.value.kind == kind, (exc.value.kind, str(exc.value))
    return exc.value


# ------------------------------------------------------- construction / schema


def test_store_requires_event_key_keyword(tmp_path):
    with pytest.raises(TypeError):
        Store(str(tmp_path / "s.db"), FakeClock())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Store(str(tmp_path / "s.db"), FakeClock(), EVENT_KEY)  # type: ignore[misc]


@pytest.mark.parametrize("bad", [b"", b"short", b"x" * 31, "x" * 40, None, 123])
def test_store_rejects_weak_or_non_bytes_event_key(tmp_path, bad):
    path = str(tmp_path / "s.db")
    raises_kind("argument", Store, path, FakeClock(), event_key=bad)
    assert not os.path.exists(path)  # refused before any file was created


def test_store_accepts_a_32_byte_event_key_and_bytearray(tmp_path):
    with Store(str(tmp_path / "a.db"), FakeClock(), event_key=b"k" * 32) as s:
        assert s.verify_event_chain()
    with Store(str(tmp_path / "b.db"), FakeClock(), event_key=bytearray(b"k" * 32)) as s:
        assert s.verify_event_chain()


@pytest.mark.parametrize("bad", ["", None, 5])
def test_store_rejects_bad_path(bad):
    raises_kind("argument", Store, bad, FakeClock(), event_key=EVENT_KEY)


def test_new_database_has_schema_version_four_and_wal(tmp_path):
    path = str(tmp_path / "s.db")
    with open_store(path):
        pass
    assert SCHEMA_VERSION == 4
    assert rows(path, "PRAGMA user_version")[0][0] == 4
    assert rows(path, "PRAGMA journal_mode")[0][0].lower() == "wal"
    tables = {r["name"] for r in rows(path, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"stories", "tasks", "leases", "slots", "receipts", "events", "budget", "meta"} <= tables


def test_reopen_of_a_version_four_database_keeps_data(tmp_path):
    path = str(tmp_path / "s.db")
    clock = FakeClock()
    with open_store(path, clock) as s:
        s.open_story(STORY, "proj", 4)
    with open_store(path, clock) as again:
        assert again.current_epoch(STORY) == 1
        assert again.get_phase(STORY) == 4
        assert again.verify_event_chain()


def test_legacy_database_with_tables_but_no_version_is_refused(tmp_path):
    path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE stories (story_id TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO stories VALUES ('keep-me')")
    conn.commit()
    conn.close()
    err = raises_kind("schema", Store, path, FakeClock(), event_key=EVENT_KEY)
    assert "legacy" in str(err)
    # refused, not migrated: the legacy data is untouched and still version 0
    assert rows(path, "PRAGMA user_version")[0][0] == 0
    assert [r[0] for r in rows(path, "SELECT story_id FROM stories")] == ["keep-me"]


@pytest.mark.parametrize("version", [1, 2, 99])
def test_foreign_schema_version_is_refused(tmp_path, version):
    path = str(tmp_path / "v.db")
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()
    conn.close()
    err = raises_kind("schema", Store, path, FakeClock(), event_key=EVENT_KEY)
    assert str(version) in str(err)
    assert rows(path, "PRAGMA user_version")[0][0] == version  # not upgraded


def test_failed_schema_init_creates_no_partial_schema(tmp_path):
    path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 7")
    conn.close()
    raises_kind("schema", Store, path, FakeClock(), event_key=EVENT_KEY)
    names = {r["name"] for r in rows(path, "SELECT name FROM sqlite_master")}
    assert "leases" not in names and "receipts" not in names


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not meaningful on Windows")
def test_database_file_is_owner_only_on_posix(tmp_path):
    path = str(tmp_path / "s.db")
    with open_store(path) as s:
        s.open_story(STORY, "p", 1)
    assert (os.stat(path).st_mode & 0o777) == 0o600


def test_foreign_keys_are_enforced_by_the_store_connection(env):
    store, _, path, epoch = env
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with store._tx() as conn:  # private seam: reaches the connection settings
            conn.execute(
                "INSERT INTO leases (task_id, story_id, attempt, worker_id, epoch, expires_at, status) "
                "VALUES ('NO-SUCH-TASK', ?, 1, 'w', ?, 9e9, 'LIVE')",
                (STORY, epoch),
            )
    assert rows(path, "SELECT 1 FROM leases WHERE task_id = 'NO-SUCH-TASK'") == []
    assert_no_dangling_transaction(path)


def test_no_dangling_transaction_after_success_and_after_error(env):
    store, _, path, epoch = env
    lease(store, epoch)
    assert_no_dangling_transaction(path)
    raises_kind("lease", lease, store, epoch, attempt=2)  # live lease -> rollback path
    assert_no_dangling_transaction(path)
    raises_kind("epoch", store.acquire_epoch, STORY, "owner-b", OWNER_TTL)
    assert_no_dangling_transaction(path)
    raises_kind("task", store.charge, "nobody", 1, supervisor_key=SUPERVISOR_KEY)
    assert_no_dangling_transaction(path)


# ------------------------------------------------------------- busy database


def test_busy_database_raises_store_busy_error_and_writes_nothing(tmp_path):
    path = str(tmp_path / "busy.db")
    a = open_store(path)
    b = open_store(path, busy_timeout_sec=0.05)
    holder = sqlite3.connect(path, isolation_level=None, timeout=0)
    try:
        a.open_story(STORY, "p", 1)
        holder.execute("BEGIN IMMEDIATE")  # another process holds the write lock
        err = raises_kind("busy", b.open_story, "second", "p", 1)
        assert isinstance(err, StoreBusyError) and isinstance(err, StoreError)
        holder.execute("ROLLBACK")
        assert [r[0] for r in rows(path, "SELECT story_id FROM stories")] == [STORY]
        b.open_story("second", "p", 1)  # retry after the lock is gone works
        assert b.current_epoch("second") == 1
    finally:
        holder.close()
        a.close()
        b.close()


def test_busy_error_is_distinct_from_other_store_errors(tmp_path):
    path = str(tmp_path / "busy.db")
    a = open_store(path)
    b = open_store(path, busy_timeout_sec=0.05)
    holder = sqlite3.connect(path, isolation_level=None, timeout=0)
    try:
        a.open_story(STORY, "p", 1)
        holder.execute("BEGIN IMMEDIATE")
        with pytest.raises(StoreBusyError):
            b.acquire_epoch(STORY, "x", 5)
        holder.execute("ROLLBACK")
        assert b.acquire_epoch(STORY, "x", 5) == 2  # the failed call changed nothing
    finally:
        holder.close()
        a.close()
        b.close()


def test_busy_database_on_open_raises_store_busy_error(tmp_path):
    path = str(tmp_path / "busy.db")
    open_store(path).close()
    holder = sqlite3.connect(path, isolation_level=None, timeout=0)
    try:
        holder.execute("BEGIN IMMEDIATE")
        raises_kind("busy", open_store, path, busy_timeout_sec=0.05)
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    open_store(path).close()  # and opens fine afterwards


# ------------------------------------------------------------------- stories


def test_open_story_starts_at_epoch_one_without_owner(tmp_path):
    path = str(tmp_path / "s.db")
    with open_store(path) as s:
        assert s.open_story("a", "p", 3) == 1
        assert s.current_epoch("a") == 1
        assert s.get_phase("a") == 3
        row = rows(path, "SELECT owner, state FROM stories")[0]
        assert row["owner"] is None and row["state"] == "OPEN"


def test_open_story_duplicate_and_unknown_story_errors(env):
    store, _, _, _ = env
    raises_kind("story", store.open_story, STORY, "proj", 4)
    raises_kind("story", store.current_epoch, "nope")
    raises_kind("story", store.get_phase, "nope")


@pytest.mark.parametrize(
    "args", [("", "p", 1), ("a", "", 1), ("a", "p", 0), ("a", "p", 11), ("a", "p", True), ("a", "p", 1.0)]
)
def test_open_story_bad_arguments(tmp_path, args):
    with open_store(str(tmp_path / "s.db")) as s:
        raises_kind("argument", s.open_story, *args)


# -------------------------------------------------------------- epoch (CAS)


def test_acquire_epoch_bumps_and_returns_new_epoch(env):
    store, _, path, epoch = env
    assert epoch == 2
    assert store.current_epoch(STORY) == 2
    row = rows(path, "SELECT owner, state FROM stories")[0]
    assert row["owner"] == "owner-a" and row["state"] == "OWNED"
    assert row["state"] in STORY_STATES


def test_second_acquire_while_owner_live_fails_and_keeps_epoch(env):
    store, clock, _, _ = env
    clock.advance(OWNER_TTL - 1)
    raises_kind("epoch", store.acquire_epoch, STORY, "owner-b", OWNER_TTL)
    assert store.current_epoch(STORY) == 2


def test_same_owner_cannot_reacquire_while_live(env):
    store, _, _, _ = env
    raises_kind("epoch", store.acquire_epoch, STORY, "owner-a", OWNER_TTL)


def test_acquire_after_ttl_fences_live_lease_and_old_epoch_writes(env):
    store, clock, path, old = env
    lease(store, old, ttl=10_000)
    clock.advance(OWNER_TTL)  # boundary: expires_at <= now is a dead owner
    new = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert new == old + 1
    row = leases(path)[0]
    assert row["status"] == "FENCED" and row["wrote"] == 0
    assert slot_map(path) == {1: None, 2: None}  # slot freed
    assert "LEASE_FENCED" in kinds(path)
    # the old epoch is dead for every write path
    raises_kind("lease", store.heartbeat, TASK, WORKER, old, 10)
    raises_kind("epoch", lease, store, old, attempt=2)
    raises_kind("epoch", store.append_receipt, tr(old), STORY, KEY)
    # the fenced lease cannot authorise a receipt in the new epoch either
    raises_kind("lease", store.append_receipt, tr(new), STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_acquire_epoch_one_instant_before_expiry_still_fails(env):
    store, clock, _, _ = env
    clock.advance(OWNER_TTL - 0.001)
    with pytest.raises(StoreError):
        store.acquire_epoch(STORY, "owner-b", OWNER_TTL)


def test_two_store_instances_on_one_file_only_one_wins(tmp_path):
    path = str(tmp_path / "shared.db")
    clock = FakeClock()
    a, b = open_store(path, clock), open_store(path, clock)
    try:
        a.open_story(STORY, "p", 1)
        assert a.acquire_epoch(STORY, "A", 50) == 2
        raises_kind("epoch", b.acquire_epoch, STORY, "B", 50)
        assert b.current_epoch(STORY) == 2
    finally:
        a.close()
        b.close()


def test_concurrent_acquire_exactly_one_holds_the_epoch(tmp_path):
    path = str(tmp_path / "race.db")
    clock = FakeClock()
    with open_store(path, clock) as s:
        s.open_story(STORY, "p", 1)
    barrier = threading.Barrier(4)
    results = []
    guard = threading.Lock()

    def worker(name):
        st = open_store(path, clock)
        try:
            barrier.wait()
            try:
                out = ("ok", st.acquire_epoch(STORY, name, 500))
            except StoreError as exc:
                out = ("fail", exc.kind)
        finally:
            st.close()
        with guard:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(r[0] for r in results) == ["fail", "fail", "fail", "ok"]
    assert [r for r in results if r[0] == "fail"] == [("fail", "epoch")] * 3
    with open_store(path, clock) as s:
        assert s.current_epoch(STORY) == 2


def test_acquire_epoch_bad_arguments(env):
    store, _, _, _ = env
    for ttl in (0, -1, True, "5", float("nan"), float("inf"), MAX_TTL_SEC + 1):
        raises_kind("argument", store.acquire_epoch, STORY, "x", ttl)
    raises_kind("argument", store.acquire_epoch, STORY, "", 5)
    raises_kind("story", store.acquire_epoch, "missing", "x", 5)


def test_acquire_epoch_exhausted_counter_is_refused(env):
    store, _, path, epoch = env
    store.release_epoch(STORY, "owner-a")
    conn = sqlite3.connect(path)
    conn.execute("UPDATE stories SET epoch = ?", (MAX_COUNTER,))
    conn.commit()
    conn.close()
    raises_kind("epoch", store.acquire_epoch, STORY, "owner-b", 5)
    assert store.current_epoch(STORY) == MAX_COUNTER


def test_renew_epoch_extends_liveness_without_changing_epoch(env):
    store, clock, path, epoch = env
    clock.advance(60)
    store.renew_epoch(STORY, "owner-a", OWNER_TTL)
    assert store.current_epoch(STORY) == epoch
    clock.advance(70)  # past the original expiry (100), before the renewed one (160)
    raises_kind("epoch", store.acquire_epoch, STORY, "owner-b", OWNER_TTL)
    clock.advance(40)  # now past 160
    assert store.acquire_epoch(STORY, "owner-b", OWNER_TTL) == epoch + 1
    assert "EPOCH_RENEWED" in kinds(path)


def test_renew_epoch_rejects_non_owner_and_expired_owner(env):
    store, clock, _, _ = env
    raises_kind("epoch", store.renew_epoch, STORY, "owner-b", OWNER_TTL)
    clock.advance(OWNER_TTL)
    raises_kind("epoch", store.renew_epoch, STORY, "owner-a", OWNER_TTL)


def test_release_epoch_owner_only_then_next_acquire_succeeds(env):
    store, _, path, epoch = env
    raises_kind("epoch", store.release_epoch, STORY, "owner-b")
    store.release_epoch(STORY, "owner-a")
    assert store.current_epoch(STORY) == epoch  # number kept
    row = rows(path, "SELECT owner, state, owner_expires_at FROM stories")[0]
    assert row["owner"] is None and row["state"] == "OPEN" and row["owner_expires_at"] is None
    assert store.acquire_epoch(STORY, "owner-b", OWNER_TTL) == epoch + 1


def test_release_epoch_without_owner_fails(tmp_path):
    with open_store(str(tmp_path / "s.db")) as s:
        s.open_story("a", "p", 1)
        raises_kind("epoch", s.release_epoch, "a", "anyone")


# --------------------------------------------------------------------- phase


def test_set_phase_by_live_owner_changes_phase_and_records_event(env):
    store, _, path, epoch = env
    assert store.get_phase(STORY) == 4
    store.set_phase(STORY, "owner-a", epoch, 5)
    assert store.get_phase(STORY) == 5
    assert "PHASE_SET" in kinds(path)
    payload = json.loads(
        rows(path, "SELECT payload FROM events WHERE kind='PHASE_SET'")[0]["payload"]
    )
    assert payload == {"epoch": epoch, "from": 4, "to": 5}
    assert store.verify_event_chain()


def test_set_phase_is_visible_to_a_second_instance_and_after_reopen(env):
    store, clock, path, epoch = env
    store.set_phase(STORY, "owner-a", epoch, 7)
    with open_store(path, clock) as other:
        assert other.get_phase(STORY) == 7


def test_set_phase_rejects_wrong_owner_stale_epoch_and_expired_owner(env):
    store, clock, path, epoch = env
    raises_kind("epoch", store.set_phase, STORY, "owner-b", epoch, 5)
    raises_kind("epoch", store.set_phase, STORY, "owner-a", epoch - 1, 5)
    raises_kind("epoch", store.set_phase, STORY, "owner-a", epoch + 1, 5)
    clock.advance(OWNER_TTL)  # ownership expired
    raises_kind("epoch", store.set_phase, STORY, "owner-a", epoch, 5)
    assert store.get_phase(STORY) == 4
    assert "PHASE_SET" not in kinds(path)


def test_set_phase_loses_after_takeover_even_for_the_old_owner(env):
    store, clock, _, epoch = env
    clock.advance(OWNER_TTL)
    new = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    raises_kind("epoch", store.set_phase, STORY, "owner-a", epoch, 6)  # stale zombie
    store.set_phase(STORY, "owner-b", new, 6)
    assert store.get_phase(STORY) == 6


@pytest.mark.parametrize("phase", [0, 11, -1, True, 4.0, "5", None])
def test_set_phase_bounds(env, phase):
    store, _, _, epoch = env
    raises_kind("argument", store.set_phase, STORY, "owner-a", epoch, phase)
    assert store.get_phase(STORY) == 4


def test_set_phase_boundary_values_one_and_ten_are_accepted(env):
    store, _, _, epoch = env
    store.set_phase(STORY, "owner-a", epoch, 1)
    store.set_phase(STORY, "owner-a", epoch, 10)
    assert store.get_phase(STORY) == 10


def test_set_phase_bad_epoch_and_unknown_story(env):
    store, _, _, epoch = env
    for bad in (0, True, MAX_COUNTER + 1):
        raises_kind("argument", store.set_phase, STORY, "owner-a", bad, 5)
    raises_kind("story", store.set_phase, "missing", "owner-a", epoch, 5)


def test_render_state_md_shows_the_phase(env):
    store, _, _, epoch = env
    store.set_phase(STORY, "owner-a", epoch, 9)
    assert "- phase: 9" in store.render_state_md(STORY)


# -------------------------------------------------------------- register_task


def test_register_task_returns_manifest_hash_and_get_manifest_roundtrips(env):
    store, _, path, _ = env
    m = manifest(task_id="T2")
    digest = store.register_task(m)
    assert digest == c.manifest_sha256(m)
    assert store.get_manifest("T2") == m
    row = rows(path, "SELECT story_id, manifest_sha256, retry_cap FROM tasks WHERE task_id='T2'")[0]
    assert (row["story_id"], row["manifest_sha256"], row["retry_cap"]) == (STORY, digest, 1)
    assert "TASK_REGISTERED" in kinds(path)


def test_get_manifest_returns_an_independent_copy(env):
    store, _, _, _ = env
    got = store.get_manifest(TASK)
    got["scope"].append("evil.py")
    got["retry_cap"] = 99
    assert store.get_manifest(TASK) == manifest()


def test_register_same_manifest_again_is_idempotent(env):
    store, _, path, _ = env
    before = kinds(path).count("TASK_REGISTERED")
    assert store.register_task(manifest()) == c.manifest_sha256(manifest())
    assert kinds(path).count("TASK_REGISTERED") == before  # no second event
    assert len(rows(path, "SELECT 1 FROM tasks WHERE task_id='T1'")) == 1


def test_register_different_manifest_for_same_task_is_rejected(env):
    store, _, path, _ = env
    other = manifest(scope=["src/other.py"])
    raises_kind("manifest", store.register_task, other)
    assert store.get_manifest(TASK) == manifest()  # original untouched
    assert rows(path, "SELECT manifest_sha256 FROM tasks")[0][0] == c.manifest_sha256(manifest())


def test_register_task_unknown_story_and_project_mismatch(env):
    store, _, _, _ = env
    raises_kind("story", store.register_task, manifest(task_id="T9", story_id="ghost"))
    raises_kind("story", store.register_task, manifest(task_id="T9", project_id="another-project"))
    raises_kind("task", store.get_manifest, "T9")


def test_register_task_rejects_invalid_manifest(env):
    store, _, path, _ = env
    bad = manifest(task_id="T9")
    del bad["allowed_commands"]
    with pytest.raises(c.ContractError):
        store.register_task(bad)
    with pytest.raises(c.ContractError):
        store.register_task("not a manifest")  # type: ignore[arg-type]
    assert rows(path, "SELECT 1 FROM tasks WHERE task_id='T9'") == []


def test_get_manifest_unknown_task(env):
    store, _, _, _ = env
    raises_kind("task", store.get_manifest, "ghost")


def test_tasks_table_is_append_only(env):
    _, _, path, _ = env
    for sql in ("UPDATE tasks SET retry_cap = 99", "UPDATE tasks SET manifest_sha256 = 'x'", "DELETE FROM tasks"):
        conn = sqlite3.connect(path)
        try:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conn.execute(sql)
                conn.commit()
        finally:
            conn.close()
    assert rows(path, "SELECT retry_cap FROM tasks")[0][0] == 1


# ------------------------------------------------------------ lease and slot


def test_acquire_lease_requires_a_registered_task(env):
    store, _, path, epoch = env
    raises_kind("task", lease, store, epoch, task="unregistered")
    assert leases(path) == []


def test_acquire_lease_task_must_belong_to_the_story(env):
    store, _, path, epoch = env
    store.open_story(STORY2, "proj", 4)
    store.register_task(manifest(task_id="TS2", story_id=STORY2))
    raises_kind("story", lease, store, epoch, task="TS2", story=STORY)
    assert leases(path) == []


def test_acquire_lease_takes_lowest_free_slot_and_records_history_row(env):
    store, _, path, epoch = env
    reg(store, "T2")
    lease(store, epoch)
    lease(store, epoch, task="T2", worker="w2")
    assert slot_map(path) == {1: "T1", 2: "T2"}
    row = leases(path)[0]
    assert (row["task_id"], row["worker_id"], row["epoch"], row["attempt"]) == ("T1", WORKER, epoch, 1)
    assert (row["status"], row["wrote"], row["marked"], row["expires_at"]) == ("LIVE", 0, 0, 1030.0)
    assert "LEASE_ACQUIRED" in kinds(path)


def test_lease_requires_supervisor_key_keyword_and_validates_it(env):
    store, _, path, epoch = env
    with pytest.raises(TypeError):
        store.acquire_lease(TASK, STORY, WORKER, epoch, 1, 30)  # type: ignore[call-arg]
    for bad in (b"", b"short", "s" * 40, None):
        raises_kind("argument", store.acquire_lease, TASK, STORY, WORKER, epoch, 1, 30, supervisor_key=bad)
    assert leases(path) == []


def test_no_free_slot_rejected_and_leaves_no_lease_row(env):
    store, _, path, epoch = env
    reg(store, "T2")
    reg(store, "T3")
    lease(store, epoch)
    lease(store, epoch, task="T2", worker="w2")
    events_before = len(kinds(path))
    raises_kind("slot", lease, store, epoch, task="T3", worker="w3")
    assert rows(path, "SELECT 1 FROM leases WHERE task_id='T3'") == []
    assert len(kinds(path)) == events_before  # nothing half-written
    assert slot_map(path) == {1: "T1", 2: "T2"}


def test_stale_epoch_lease_rejected_and_takes_no_slot(env):
    store, _, path, epoch = env
    raises_kind("epoch", lease, store, epoch - 1)
    raises_kind("epoch", lease, store, epoch + 1)
    assert slot_map(path) == {1: None, 2: None}
    assert leases(path) == []


def test_live_lease_blocks_second_acquire_for_same_task(env):
    store, _, path, epoch = env
    lease(store, epoch)
    raises_kind("lease", lease, store, epoch, worker="w2", attempt=2)
    assert len(leases(path)) == 1
    assert list(slot_map(path).values()).count("T1") == 1


def test_database_allows_at_most_one_live_lease_per_task(env):
    store, _, path, epoch = env
    lease(store, epoch)
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO leases (task_id, story_id, attempt, worker_id, epoch, expires_at, status) "
                "VALUES ('T1', ?, 2, 'w2', ?, 9e9, 'LIVE')",
                (STORY, epoch),
            )
    finally:
        conn.close()


def test_acquire_lease_bad_arguments(env):
    store, _, path, epoch = env
    good = {"task": TASK, "worker": "w", "epoch": epoch, "attempt": 1, "ttl": 30}
    for override in (
        {"task": ""}, {"worker": " "}, {"epoch": 0}, {"epoch": True}, {"epoch": MAX_COUNTER + 1},
        {"attempt": 0}, {"attempt": True}, {"attempt": MAX_COUNTER + 1},
        {"ttl": 0}, {"ttl": -5}, {"ttl": float("nan")}, {"ttl": MAX_TTL_SEC + 1},
    ):
        a = {**good, **override}
        raises_kind(
            "argument", lease, store, a["epoch"], task=a["task"], worker=a["worker"],
            attempt=a["attempt"], ttl=a["ttl"],
        )
    raises_kind("story", lease, store, epoch, story="missing")
    assert leases(path) == []


def test_lease_attempts_are_consecutive_from_one(env):
    store, _, path, epoch = env
    for first in (2, 3):
        raises_kind("lease", lease, store, epoch, attempt=first)
    lease(store, epoch, attempt=1)
    store.release_lease(TASK, WORKER, epoch)
    for attempt in (1, 3):
        raises_kind("lease", lease, store, epoch, attempt=attempt)
    lease(store, epoch, attempt=2)
    assert [r["attempt"] for r in leases(path)] == [1, 2]


def test_lease_history_is_never_overwritten(env):
    store, _, path, epoch = env
    lease(store, epoch, worker="first")
    store.release_lease(TASK, "first", epoch)
    lease(store, epoch, worker="second", attempt=2)
    history = leases(path)
    assert [(r["attempt"], r["worker_id"], r["status"]) for r in history] == [
        (1, "first", "RELEASED"),
        (2, "second", "LIVE"),
    ]
    assert history[0]["lease_id"] != history[1]["lease_id"]
    assert slot_map(path)[1] == "T1"  # slot now points at the second lease row
    assert rows(path, "SELECT lease_id FROM slots WHERE slot_no = 1")[0][0] == history[1]["lease_id"]


def test_lease_statuses_follow_the_closed_enum(env):
    store, clock, path, epoch = env
    reg(store, "T2")
    reg(store, "T3")
    lease(store, epoch, ttl=10)
    lease(store, epoch, task="T2", worker="w2", ttl=1000)
    clock.advance(10)
    store.reap_expired()  # T1 -> EXPIRED
    store.release_lease("T2", "w2", epoch)  # T2 -> RELEASED
    clock.advance(OWNER_TTL)
    new = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    lease(store, new, task="T3", worker="w3", ttl=10_000)
    clock.advance(OWNER_TTL)
    store.acquire_epoch(STORY, "owner-c", OWNER_TTL)  # T3 -> FENCED
    seen = {r["task_id"]: r["status"] for r in leases(path)}
    assert seen == {"T1": "EXPIRED", "T2": "RELEASED", "T3": "FENCED"}
    assert set(seen.values()) <= LEASE_STATUSES


def test_expired_lease_is_reaped_on_next_acquire_and_slot_reused(env):
    store, clock, path, epoch = env
    reg(store, "T2")
    reg(store, "T3")
    store.init_slots(1)  # idempotent: still 2 slots
    lease(store, epoch, ttl=10)
    lease(store, epoch, task="T2", worker="w2", ttl=10_000)
    clock.advance(10)
    lease(store, epoch, task="T3", worker="w3")  # reaps T1 first, then takes its slot
    assert {r["task_id"]: r["status"] for r in leases(path)}["T1"] == "EXPIRED"
    assert slot_map(path)[1] == "T3"
    assert "LEASE_EXPIRED" in kinds(path)


def test_lost_attempt_must_be_marked_before_retry(env):
    store, clock, _, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(10)
    store.reap_expired()
    err = raises_kind("lease", lease, store, epoch, worker="w2", attempt=2)
    assert "marked" in str(err)
    written = store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    assert len(written) == 1
    lease(store, epoch, worker="w2", attempt=2)  # now allowed


def test_lost_attempt_with_receipt_needs_no_marker(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)
    clock.advance(10)
    store.reap_expired()
    lease(store, epoch, worker="w2", attempt=2)
    assert supervisor_receipts(store) == []


def test_fenced_unwritten_lease_also_needs_a_marker(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10_000)
    clock.advance(OWNER_TTL)
    new = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    raises_kind("lease", lease, store, new, attempt=2)
    store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    lease(store, new, attempt=2)
    assert [r["status"] for r in leases(path)] == ["FENCED", "LIVE"]


def test_concurrent_acquire_for_the_same_task_has_one_winner(tmp_path):
    path = str(tmp_path / "race.db")
    store, clock, epoch = new_env(path)
    store.close()
    barrier = threading.Barrier(4)
    results = []
    guard = threading.Lock()

    def worker(i):
        st = open_store(path, clock)
        try:
            barrier.wait()
            try:
                lease(st, epoch, worker=f"w{i}")
                out = "ok"
            except StoreError as exc:
                out = exc.kind
        finally:
            st.close()
        with guard:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(results) == ["lease", "lease", "lease", "ok"]
    assert len(leases(path)) == 1


def test_concurrent_acquire_for_the_last_slot_has_exact_capacity(tmp_path):
    path = str(tmp_path / "race.db")
    store, clock, epoch = new_env(path, slots=2)
    for t in ("T2", "T3"):
        reg(store, t)
    store.close()
    barrier = threading.Barrier(3)
    results = []
    guard = threading.Lock()

    def worker(task):
        st = open_store(path, clock)
        try:
            barrier.wait()
            try:
                lease(st, epoch, task=task, worker=f"w-{task}")
                out = "ok"
            except StoreError as exc:
                out = exc.kind
        finally:
            st.close()
        with guard:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(t,)) for t in ("T1", "T2", "T3")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(results) == ["ok", "ok", "slot"]
    assert len(leases(path)) == 2
    assert None not in slot_map(path).values()  # both slots are held by a lease


# ----------------------------------------------- heartbeat / release / reaping


def test_heartbeat_extends_lease_beyond_original_expiry(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(9)
    store.heartbeat(TASK, WORKER, epoch, 10)  # now expires at +19
    clock.advance(5)  # past the original expiry
    assert store.reap_expired() == []
    assert leases(path)[0]["expires_at"] == 1019.0
    store.release_lease(TASK, WORKER, epoch)  # still live


def test_heartbeat_rejections(env):
    store, clock, _, epoch = env
    lease(store, epoch, ttl=10)
    raises_kind("lease", store.heartbeat, TASK, "intruder", epoch, 10)
    raises_kind("epoch", store.heartbeat, TASK, WORKER, epoch + 1, 10)
    raises_kind("lease", store.heartbeat, "unknown", WORKER, epoch, 10)
    raises_kind("argument", store.heartbeat, TASK, WORKER, epoch, 0)
    clock.advance(10)
    raises_kind("lease", store.heartbeat, TASK, WORKER, epoch, 10)
    assert store.reap_expired() == [TASK]  # the failed heartbeat did not resurrect it


def test_release_lease_frees_slot_and_second_release_fails(env):
    store, _, path, epoch = env
    lease(store, epoch)
    raises_kind("lease", store.release_lease, TASK, "intruder", epoch)
    store.release_lease(TASK, WORKER, epoch)
    assert leases(path)[0]["status"] == "RELEASED"
    assert slot_map(path) == {1: None, 2: None}
    raises_kind("lease", store.release_lease, TASK, WORKER, epoch)
    assert "LEASE_RELEASED" in kinds(path)


def test_reap_expired_returns_only_expired_and_is_idempotent(env):
    store, clock, path, epoch = env
    reg(store, "T2")
    lease(store, epoch, ttl=10)
    lease(store, epoch, task="T2", worker="w2", ttl=50)
    assert store.reap_expired() == []
    clock.advance(10)
    assert store.reap_expired() == [TASK]
    assert store.reap_expired() == []
    assert {r["task_id"]: r["status"] for r in leases(path)} == {"T1": "EXPIRED", "T2": "LIVE"}
    assert slot_map(path) == {1: None, 2: "T2"}


# ------------------------------------------------------------ receipts (valid)


def test_append_receipt_roundtrip_preserves_body_and_marks_lease_wrote(env):
    store, _, path, epoch = env
    lease(store, epoch)
    r = tr(epoch)
    store.append_receipt(r, STORY, KEY)
    assert store.receipts_for_task(TASK) == [r]
    row = rows(path, "SELECT receipt_sha256, story_id, slot, attempt FROM receipts")[0]
    assert row["receipt_sha256"] == c.receipt_sha256(r)
    assert (row["story_id"], row["slot"], row["attempt"]) == (STORY, "tests", 1)
    assert "RECEIPT_APPENDED" in kinds(path)
    assert leases(path)[0]["wrote"] == 1


def test_all_declared_slot_types_are_accepted_under_one_lease(env):
    store, _, _, epoch = env
    lease(store, epoch)
    for rtype in ("TestRun", "StaticAnalysis", "IndependentReview"):
        store.append_receipt(receipt(rtype, epoch=epoch), STORY, KEY)
    assert [r["slot"] for r in store.receipts_for_task(TASK)] == ["tests", "static", "review"]


def test_store_output_is_approved_by_the_gate(env):
    store, _, _, epoch = env
    lease(store, epoch)
    for rtype in ("TestRun", "StaticAnalysis", "IndependentReview"):
        store.append_receipt(receipt(rtype, epoch=epoch), STORY, KEY)
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "APPROVE", d["reasons"]


def test_receipt_chain_within_retry_cap_and_independent_slots(env):
    store, _, _, epoch = env
    lease(store, epoch)
    a1 = tr(epoch, attempt=1, result="BLOCKED")
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1))  # retry_cap 1 -> attempt 2 allowed
    for r in (a1, a2):
        store.append_receipt(r, STORY, KEY)
    store.append_receipt(receipt("StaticAnalysis", epoch=epoch), STORY, KEY)  # other slot starts at 1
    assert [(r["slot"], r["attempt"]) for r in store.receipts_for_task(TASK)] == [
        ("tests", 1), ("tests", 2), ("static", 1),
    ]


def test_receipts_survive_reopen(env):
    store, clock, path, epoch = env
    lease(store, epoch)
    r = tr(epoch)
    store.append_receipt(r, STORY, KEY)
    with open_store(path, clock) as again:
        assert again.receipts_for_task(TASK) == [r]
        assert again.verify_event_chain()
        again.release_lease(TASK, WORKER, epoch)  # the live lease survived the restart


# ---------------------------------------------------------- receipts (rejected)


def test_append_receipt_key_must_be_strong_bytes(env):
    store, _, path, epoch = env
    lease(store, epoch)
    for bad in (b"", b"short", "k" * 40, None):
        raises_kind("argument", store.append_receipt, tr(epoch), STORY, bad)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_receipt_signed_with_wrong_key_or_wrong_label_or_unlabeled_hmac_is_rejected(env):
    store, _, path, epoch = env
    lease(store, epoch)
    body = unsigned_receipt("TestRun", epoch=epoch)
    wrong_key = resign(body, SUPERVISOR_KEY)
    waiver_labeled = dict(body, signature=signing.sign(body, KEY, signing.WAIVER_LABEL))
    unlabeled = dict(
        body,
        signature=hmac.new(KEY, c.canonical_bytes(body), hashlib.sha256).hexdigest(),
    )
    for bad in (wrong_key, waiver_labeled, unlabeled, dict(body, signature="0" * 64)):
        raises_kind("signature", store.append_receipt, bad, STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert leases(path)[0]["wrote"] == 0
    store.append_receipt(resign(body, KEY), STORY, KEY)  # the same body signed properly passes


def test_tampered_receipt_after_signing_is_rejected(env):
    store, _, path, epoch = env
    lease(store, epoch)
    r = tr(epoch)
    r["resolved_model"] = "tampered"
    raises_kind("signature", store.append_receipt, r, STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_forged_pass_result_with_valid_signature_is_rejected(env):
    store, _, path, epoch = env
    lease(store, epoch)
    forged = resign(unsigned_receipt("TestRun", epoch=epoch, executed_test_ids=["t1"], result="PASS"))
    assert c.derive_result(forged) == "FAIL"
    err = raises_kind("signature", store.append_receipt, forged, STORY, KEY)
    assert "derived" in str(err)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_manifest_hash_mismatch_is_rejected(env):
    store, _, path, epoch = env
    lease(store, epoch)
    other = manifest(scope=["src/other.py"])
    raises_kind("manifest", store.append_receipt, bound(other, "TestRun", KEY, epoch=epoch), STORY, KEY)
    raises_kind("manifest", store.append_receipt, tr(epoch, manifest_sha256="e" * 64), STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_role_hash_mismatch_is_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    raises_kind("manifest", store.append_receipt, tr(epoch, role_sha256="d" * 64), STORY, KEY)


def test_unknown_task_and_story_link_are_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    raises_kind("task", store.append_receipt, tr(epoch, task_id="ghost"), STORY, KEY)
    store.open_story(STORY2, "proj", 4)
    raises_kind("story", store.append_receipt, tr(epoch), STORY2, KEY)  # task T1 lives in STORY
    raises_kind("story", store.append_receipt, tr(epoch), "missing-story", KEY)


def test_undeclared_slot_and_wrong_type_for_slot_are_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    raises_kind("slot", store.append_receipt, tr(epoch, slot="not-declared"), STORY, KEY)
    raises_kind(
        "slot", store.append_receipt,
        receipt("StaticAnalysis", epoch=epoch, slot="tests"), STORY, KEY,
    )  # slot 'tests' is declared as TestRun
    raises_kind(
        "slot", store.append_receipt,
        receipt("Documentation", epoch=epoch, slot="static"), STORY, KEY,
    )


def test_append_receipt_stale_or_future_epoch_rejected(env):
    store, _, path, epoch = env
    lease(store, epoch)
    for bad in (epoch - 1, epoch + 1):
        raises_kind("epoch", store.append_receipt, tr(bad), STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_append_requires_a_live_lease_held_by_the_runner(env):
    store, clock, path, epoch = env
    raises_kind("lease", store.append_receipt, tr(epoch), STORY, KEY)  # no lease at all
    lease(store, epoch, worker="someone-else")
    raises_kind("lease", store.append_receipt, tr(epoch), STORY, KEY)  # runner-1 is not the holder
    assert rows(path, "SELECT 1 FROM receipts") == []
    store.release_lease(TASK, "someone-else", epoch)
    lease(store, epoch, attempt=2)
    clock.advance(30)  # lease expired by time even though not yet reaped
    raises_kind("lease", store.append_receipt, tr(epoch), STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert [r["wrote"] for r in leases(path)] == [0, 0]


def test_released_lease_cannot_write_a_late_receipt(env):
    store, _, _, epoch = env
    lease(store, epoch)
    store.release_lease(TASK, WORKER, epoch)
    raises_kind("lease", store.append_receipt, tr(epoch), STORY, KEY)


def test_append_receipt_attempt_gap_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    m = reg(store, "TG", retry_cap=5)  # high cap, so a gap is a chain error and not a retry error
    lease(store, epoch, task="TG")
    g1 = bound(m, "TestRun", KEY, epoch=epoch, task_id="TG", receipt_id="g1")
    store.append_receipt(g1, STORY, KEY)
    gap = bound(
        m, "TestRun", KEY, epoch=epoch, task_id="TG",
        attempt=3, prev_receipt_sha256=c.receipt_sha256(g1), receipt_id="g3",
    )
    raises_kind("chain", store.append_receipt, gap, STORY, KEY)
    first_is_two = bound(
        m, "StaticAnalysis", KEY, epoch=epoch, task_id="TG",
        attempt=2, prev_receipt_sha256="e" * 64, receipt_id="g-s2",
    )
    raises_kind("chain", store.append_receipt, first_is_two, STORY, KEY)
    assert len(store.receipts_for_task("TG")) == 1


def test_append_receipt_wrong_prev_hash_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    raises_kind("chain", store.append_receipt, tr(epoch, attempt=2, prev_receipt_sha256="f" * 64), STORY, KEY)
    assert len(store.receipts_for_task(TASK)) == 1


def test_append_receipt_repeated_attempt_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    r = tr(epoch)
    store.append_receipt(r, STORY, KEY)
    raises_kind("chain", store.append_receipt, r, STORY, KEY)  # exact replay
    raises_kind("chain", store.append_receipt, tr(epoch, receipt_id="other-id"), STORY, KEY)
    assert len(store.receipts_for_task(TASK)) == 1


def test_append_receipt_duplicate_receipt_id_rejected(env):
    store, _, _, epoch = env
    lease(store, epoch)
    a1 = tr(epoch, receipt_id="same-id", result="BLOCKED")
    store.append_receipt(a1, STORY, KEY)
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), receipt_id="same-id")
    raises_kind("duplicate", store.append_receipt, a2, STORY, KEY)
    assert len(store.receipts_for_task(TASK)) == 1


def test_receipt_id_is_unique_across_tasks(env):
    store, _, _, epoch = env
    m2 = reg(store, "T2")
    lease(store, epoch)
    lease(store, epoch, task="T2", worker="w2")
    store.append_receipt(tr(epoch, receipt_id="shared"), STORY, KEY)
    other = bound(m2, "TestRun", KEY, epoch=epoch, task_id="T2", runner_id="w2", receipt_id="shared")
    raises_kind("duplicate", store.append_receipt, other, STORY, KEY)


def test_retry_cap_bounds_the_receipt_attempt(env):
    store, _, _, epoch = env  # T1 has retry_cap 1 -> attempts 1 and 2 only
    lease(store, epoch)
    a1 = tr(epoch, attempt=1, result="BLOCKED")
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), result="BLOCKED")
    store.append_receipt(a1, STORY, KEY)
    store.append_receipt(a2, STORY, KEY)
    a3 = tr(epoch, attempt=3, prev_receipt_sha256=c.receipt_sha256(a2))
    raises_kind("retry", store.append_receipt, a3, STORY, KEY)
    assert len(store.receipts_for_task(TASK)) == 2


def test_retry_cap_zero_allows_only_attempt_one(env):
    store, _, _, epoch = env
    m = reg(store, "T0", retry_cap=0)
    lease(store, epoch, task="T0")
    a1 = bound(m, "TestRun", KEY, epoch=epoch, task_id="T0", receipt_id="z1", result="BLOCKED")
    store.append_receipt(a1, STORY, KEY)
    a2 = bound(
        m, "TestRun", KEY, epoch=epoch, task_id="T0", receipt_id="z2", attempt=2,
        prev_receipt_sha256=c.receipt_sha256(a1),
    )
    raises_kind("retry", store.append_receipt, a2, STORY, KEY)


def test_invalid_receipt_and_non_dict_raise_contract_error_without_side_effects(env):
    store, _, path, epoch = env
    lease(store, epoch)
    bad = tr(epoch)
    bad["unexpected"] = 1
    with pytest.raises(c.ContractError):
        store.append_receipt(bad, STORY, KEY)
    with pytest.raises(c.ContractError):
        store.append_receipt("not a receipt", STORY, KEY)  # type: ignore[arg-type]
    old_shape = tr(epoch)
    del old_shape["manifest_sha256"]
    with pytest.raises(c.ContractError):
        store.append_receipt(old_shape, STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_failed_append_leaves_no_event_receipt_or_wrote_flag(env):
    store, _, path, epoch = env
    lease(store, epoch)
    before = len(kinds(path))
    raises_kind("epoch", store.append_receipt, tr(epoch + 1), STORY, KEY)
    edited = tr(epoch)
    edited["result"] = "FAIL"  # edited after signing
    raises_kind("signature", store.append_receipt, edited, STORY, KEY)
    assert len(kinds(path)) == before
    assert leases(path)[0]["wrote"] == 0
    assert_no_dangling_transaction(path)


def test_concurrent_identical_append_has_exactly_one_winner(tmp_path):
    path = str(tmp_path / "race.db")
    store, clock, epoch = new_env(path)
    lease(store, epoch)
    store.close()
    r = tr(epoch)
    barrier = threading.Barrier(2)
    results = []
    guard = threading.Lock()

    def worker():
        st = open_store(path, clock)
        try:
            barrier.wait()
            try:
                st.append_receipt(r, STORY, KEY)
                out = "ok"
            except StoreError as exc:
                out = exc.kind
        finally:
            st.close()
        with guard:
            results.append(out)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(results)[1] == "ok" and results.count("ok") == 1
    assert [x for x in results if x != "ok"][0] in ("chain", "duplicate")
    assert len(rows(path, "SELECT 1 FROM receipts")) == 1


# ------------------------------------------------------------ append-only


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE receipts SET slot = 'x'",
        "UPDATE receipts SET body = '{}'",
        "DELETE FROM receipts",
        "UPDATE events SET payload = 'x'",
        "UPDATE events SET hash = 'x'",
        "DELETE FROM events",
        "UPDATE leases SET worker_id = 'evil'",
        "UPDATE leases SET attempt = 9",
        "UPDATE leases SET task_id = 'T9'",
        "UPDATE leases SET epoch = 99",
        "DELETE FROM leases",
        "UPDATE leases SET status = 'LIVE'",  # a closed lease cannot be reopened
    ],
)
def test_raw_update_delete_of_history_tables_fail(env, sql):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)  # lease is now closed (RELEASED)
    counts = {t: len(rows(path, f"SELECT 1 FROM {t}")) for t in ("receipts", "events", "leases")}
    snapshot = [tuple(r) for r in rows(path, "SELECT * FROM leases")]
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(sql)
            conn.commit()
    finally:
        conn.close()
    assert {t: len(rows(path, f"SELECT 1 FROM {t}")) for t in counts} == counts
    assert [tuple(r) for r in rows(path, "SELECT * FROM leases")] == snapshot
    assert store.verify_event_chain()


def test_append_only_violation_inside_store_transaction_maps_to_store_error(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    err = None
    try:
        with store._tx() as conn:  # private seam: the only way to reach the trigger via Store code
            conn.execute("DELETE FROM receipts")
    except StoreError as exc:
        err = exc
    assert err is not None and err.kind == "append_only"
    assert len(store.receipts_for_task(TASK)) == 1
    store.record_event(TASK, "x", "NOTE", {})  # transaction was rolled back, store usable
    assert_no_dangling_transaction(path)


# ----------------------------------------------------------- retry exhaustion
# Third remediation: retry_cap bounds WORKER-ATTRIBUTED failed attempts only:
# every non-PASS worker result (FAIL, INCONCLUSIVE, NOT_RUN, BLOCKED), max over
# slots, plus EXPIRED and RELEASED leases that wrote nothing. Epoch takeovers
# (FENCED leases) never count.


def test_lost_attempts_count_toward_retry_cap_and_the_next_lease_commits_a_signed_marker(env):
    store, clock, path, epoch = env  # retry_cap 1 -> two failed attempts are allowed
    lose(store, clock, epoch, (1, 2))
    assert store.failed_attempts(TASK) == 2
    err = raises_kind("retry", lease, store, epoch, attempt=3)
    assert "RETRY_EXHAUSTED" in str(err)
    assert [r["attempt"] for r in leases(path)] == [1, 2]  # no third lease row
    markers = supervisor_receipts(store)
    assert [x["check_description"] for x in markers] == ["WORKER_LOST", "WORKER_LOST", "RETRY_EXHAUSTED"]
    m = markers[-1]  # committed although the call raised
    assert (m["result"], m["slot"], m["attempt"]) == ("BLOCKED", SUPERVISOR_SLOT, 3)
    assert signing.verify(m, SUPERVISOR_KEY) and not signing.verify(m, KEY)
    assert m["manifest_sha256"] == c.manifest_sha256(manifest())
    assert store.verify_event_chain()


def test_one_lost_attempt_below_the_cap_does_not_exhaust(env):
    store, clock, path, epoch = env  # retry_cap 1 -> a single loss is still retryable
    lose(store, clock, epoch, (1,))
    assert store.failed_attempts(TASK) == 1
    lease(store, epoch, attempt=2)
    assert [x["check_description"] for x in supervisor_receipts(store)] == ["WORKER_LOST"]


def test_retry_exhausted_marker_is_written_once_and_blocks_everything_after(env):
    store, clock, path, epoch = env
    lose(store, clock, epoch, (1, 2))
    for attempt in (3, 3, 4):
        raises_kind("retry", lease, store, epoch, attempt=attempt)
    names = [x["check_description"] for x in supervisor_receipts(store)]
    assert names.count("RETRY_EXHAUSTED") == 1  # repeated attempts add no markers
    assert len(leases(path)) == 2
    raises_kind("terminal", store.append_receipt, tr(epoch), STORY, KEY)  # no worker receipt either


def test_retry_cap_zero_refuses_the_second_lease_after_one_lost_attempt(env):
    store, clock, path, epoch = env
    reg(store, "T0", retry_cap=0)
    lose(store, clock, epoch, (1,), task="T0")
    raises_kind("retry", lease, store, epoch, task="T0", attempt=2)
    assert len(leases(path)) == 1
    assert supervisor_receipts(store, "T0")[-1]["check_description"] == "RETRY_EXHAUSTED"


def test_retry_cap_boundary_last_allowed_failed_attempt(env):
    store, clock, path, epoch = env
    reg(store, "T3", retry_cap=2)  # three failed attempts are allowed, the fourth lease is refused
    lose(store, clock, epoch, (1, 2), task="T3")
    assert store.failed_attempts("T3") == 2
    lease(store, epoch, task="T3", attempt=3)  # 2 < 3: still granted
    store.release_lease("T3", WORKER, epoch)  # a release that wrote nothing is the third failure
    assert store.failed_attempts("T3") == 3
    raises_kind("retry", lease, store, epoch, task="T3", attempt=4)
    assert [x["check_description"] for x in supervisor_receipts(store, "T3")] == [
        "WORKER_LOST", "WORKER_LOST", "RETRY_EXHAUSTED"]
    assert [r["attempt"] for r in leases(path) if r["task_id"] == "T3"] == [1, 2, 3]


def test_released_leases_that_wrote_nothing_count_toward_the_retry_cap(env):
    store, _, path, epoch = env  # retry_cap 1 -> two failed attempts exhaust it
    lease(store, epoch, attempt=1)
    store.release_lease(TASK, WORKER, epoch)
    assert store.failed_attempts(TASK) == 1
    lease(store, epoch, attempt=2)  # 1 < 2: still granted
    store.release_lease(TASK, WORKER, epoch)
    assert store.failed_attempts(TASK) == 2
    err = raises_kind("retry", lease, store, epoch, attempt=3)
    assert "RETRY_EXHAUSTED" in str(err)
    assert [r["status"] for r in leases(path)] == ["RELEASED", "RELEASED"]
    assert [x["check_description"] for x in supervisor_receipts(store)] == ["RETRY_EXHAUSTED"]
    assert kinds(path).count("LEASE_RELEASED") == 2


def test_released_lease_that_wrote_a_pass_receipt_is_not_a_failed_attempt(env):
    store, _, path, epoch = env
    for attempt in (1, 2, 3):
        lease(store, epoch, attempt=attempt)
        if attempt == 1:
            store.append_receipt(tr(epoch), STORY, KEY)  # PASS: the lease wrote something
        store.release_lease(TASK, WORKER, epoch)
        # only the releases that wrote nothing count: attempt 1 wrote a PASS receipt
        assert store.failed_attempts(TASK) == attempt - 1
    raises_kind("retry", lease, store, epoch, attempt=4)


def test_takeovers_do_not_exhaust_the_retry_cap(env):
    store, clock, path, epoch = env  # retry_cap 1: two ordinary failures would exhaust it
    for n in range(1, 5):  # four supervisor takeovers, each fences the live lease
        lease(store, epoch, attempt=n, ttl=5000)
        clock.advance(OWNER_TTL)
        epoch = store.acquire_epoch(STORY, f"owner-{n}", OWNER_TTL)
        assert leases(path)[-1]["status"] == "FENCED"
        assert len(store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")) == 1  # the loss is marked ...
        assert store.failed_attempts(TASK) == 0  # ... but it is not the worker's failure
    lease(store, epoch, attempt=5)  # still granted: the cap was not consumed
    assert [r["status"] for r in leases(path)] == ["FENCED"] * 4 + ["LIVE"]
    names = [x["check_description"] for x in supervisor_receipts(store)]
    assert names == ["WORKER_LOST"] * 4 and "RETRY_EXHAUSTED" not in names
    assert kinds(path).count("LEASE_FENCED") == 4


def test_fenced_lease_that_wrote_a_pass_receipt_is_not_counted_either(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=5000)
    store.append_receipt(tr(epoch), STORY, KEY)  # PASS: neither the lease nor the receipt counts
    clock.advance(OWNER_TTL)
    epoch = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert leases(path)[0]["status"] == "FENCED"
    assert store.failed_attempts(TASK) == 0
    lease(store, epoch, attempt=2)
    assert supervisor_receipts(store) == []


def test_fenced_lease_that_wrote_a_blocked_receipt_counts_through_the_receipt_only(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=5000)
    store.append_receipt(tr(epoch, result="BLOCKED"), STORY, KEY)  # non-PASS result counts ...
    clock.advance(OWNER_TTL)
    epoch = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert leases(path)[0]["status"] == "FENCED"
    assert store.failed_attempts(TASK) == 1  # ... once (the FENCED lease adds nothing)


def test_takeover_plus_real_failures_still_exhausts_at_the_cap(env):
    store, clock, path, epoch = env  # retry_cap 1 -> failed_attempts 2 exhausts
    lease(store, epoch, attempt=1, ttl=5000)
    clock.advance(OWNER_TTL)
    epoch = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)  # takeover: not counted
    store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    lose(store, clock, epoch, (2, 3))  # two real losses
    assert store.failed_attempts(TASK) == 2
    raises_kind("retry", lease, store, epoch, attempt=4)


def test_fail_receipts_count_toward_retry_cap(env):
    store, _, path, epoch = env  # retry_cap 1
    lease(store, epoch)
    a1 = failed_run(epoch, 1)
    store.append_receipt(a1, STORY, KEY)
    assert store.failed_attempts(TASK) == 1
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)  # 1 < 2: allowed
    a2 = failed_run(epoch, 2, c.receipt_sha256(a1))
    store.append_receipt(a2, STORY, KEY)
    assert store.failed_attempts(TASK) == 2
    store.release_lease(TASK, WORKER, epoch)
    err = raises_kind("retry", lease, store, epoch, attempt=3)
    assert "RETRY_EXHAUSTED" in str(err)
    assert supervisor_receipts(store)[-1]["check_description"] == "RETRY_EXHAUSTED"
    assert len(leases(path)) == 2


@pytest.mark.parametrize(
    "result,counted",
    [("FAIL", True), ("INCONCLUSIVE", True), ("BLOCKED", True), ("NOT_RUN", True), ("PASS", False)],
)
def test_every_non_pass_receipt_counts_as_a_failed_attempt(env, result, counted):
    store, _, _, epoch = env  # retry_cap 1 -> two counted receipts exhaust the cap
    lease(store, epoch)
    extra = {"commands": [{"argv": ["pytest", "-q"], "exit_code": 1}]} if result == "FAIL" else {}
    a1 = slot_run(epoch, 1, result=result, **extra)
    a2 = slot_run(epoch, 2, c.receipt_sha256(a1), result=result, **extra)
    store.append_receipt(a1, STORY, KEY)
    assert store.failed_attempts(TASK) == (1 if counted else 0)
    store.append_receipt(a2, STORY, KEY)
    assert store.failed_attempts(TASK) == (2 if counted else 0)


def test_non_pass_results_exhaust_and_a_final_pass_does_not(env):
    store, _, _, epoch = env
    lease(store, epoch)
    a1 = failed_run(epoch, 1)
    a2 = failed_run(epoch, 2, c.receipt_sha256(a1))
    store.append_receipt(a1, STORY, KEY)
    store.append_receipt(a2, STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    raises_kind("retry", lease, store, epoch, attempt=2)

    reg(store, "TB")
    lease(store, epoch, task="TB")
    m = manifest(task_id="TB")
    b1 = slot_run(epoch, 1, task="TB", m=m, result="BLOCKED")
    b2 = slot_run(epoch, 2, c.receipt_sha256(b1), task="TB", m=m)  # PASS
    store.append_receipt(b1, STORY, KEY)
    store.append_receipt(b2, STORY, KEY)
    store.release_lease("TB", WORKER, epoch)
    assert store.failed_attempts("TB") == 1  # the BLOCKED counts, the final PASS does not
    lease(store, epoch, task="TB", attempt=2)  # a slot at the cap that ended in PASS is not exhausted


def test_failed_attempts_is_the_max_over_slots_not_the_sum(env):
    store, _, _, epoch = env  # retry_cap 1
    lease(store, epoch)
    store.append_receipt(failed_run(epoch, 1), STORY, KEY)  # slot tests: 1
    store.append_receipt(
        slot_run(epoch, 1, rtype="StaticAnalysis", result="INCONCLUSIVE"), STORY, KEY
    )  # slot static: 1
    assert store.failed_attempts(TASK) == 1  # not 2
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)  # 1 < 2: granted (a sum would have refused it)


def test_receipt_failures_and_lost_leases_add_up(env):
    store, clock, _, epoch = env  # retry_cap 1
    lease(store, epoch)
    store.append_receipt(failed_run(epoch, 1), STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    lose(store, clock, epoch, (2,))
    assert store.failed_attempts(TASK) == 2
    raises_kind("retry", lease, store, epoch, attempt=3)


def test_lease_that_wrote_a_receipt_and_expired_is_not_a_lost_attempt(env):
    store, clock, _, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)  # PASS
    clock.advance(10)
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup") == []
    assert store.failed_attempts(TASK) == 0
    lease(store, epoch, attempt=2)  # allowed without any marker
    assert supervisor_receipts(store) == []


def test_failed_attempts_validation_and_read_only(env):
    store, _, path, _ = env
    raises_kind("task", store.failed_attempts, "ghost")
    raises_kind("argument", store.failed_attempts, "")
    n = len(kinds(path))
    assert store.failed_attempts(TASK) == 0
    assert len(kinds(path)) == n
    assert_no_dangling_transaction(path)


def test_slot_at_cap_with_pass_does_not_exhaust_retry(env):
    store, _, _, epoch = env
    lease(store, epoch)
    a1 = tr(epoch, attempt=1, result="BLOCKED")
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1))  # PASS
    store.append_receipt(a1, STORY, KEY)
    store.append_receipt(a2, STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)  # the other slots may still need work
    assert supervisor_receipts(store) == []


def test_retry_exhausted_is_gate_hard_blocked(env):
    store, clock, _, epoch = env
    lose(store, clock, epoch, (1, 2))
    raises_kind("retry", lease, store, epoch, attempt=3)
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "MODIFY"
    assert any("terminal marker RETRY_EXHAUSTED" in x for x in d["reasons"])


# --------------------------------------------------------------- supervisor


def test_supervisor_writes_worker_lost_receipt_for_reaped_lease(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(10)
    out = store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup-1")
    assert len(out) == 1
    r = out[0]
    m = manifest()
    assert r["receipt_type"] == "Documentation" and r["slot"] == SUPERVISOR_SLOT
    assert r["result"] == "INCONCLUSIVE" and r["check_description"] == "WORKER_LOST"
    assert r["attempt"] == 1 and r["prev_receipt_sha256"] is None
    assert r["epoch"] == epoch and r["candidate_head"] == m["base_head"]
    assert r["runner_id"] == "sup-1" and r["covered_acceptance"] == []
    assert r["task_id"] == TASK and r["manifest_sha256"] == c.manifest_sha256(m)
    assert r["role_sha256"] == m["role_sha256"]
    assert signing.verify(r, SUPERVISOR_KEY) and not signing.verify(r, KEY)
    assert c.derive_result(r) == r["result"]
    assert store.receipts_for_task(TASK) == [r]
    row = leases(path)[0]
    assert (row["status"], row["marked"], row["wrote"]) == ("EXPIRED", 1, 0)
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup-1") == []  # idempotent
    assert len(store.receipts_for_task(TASK)) == 1


def test_supervisor_receipt_is_a_non_approval_for_the_gate(env):
    store, clock, _, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(10)
    store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "MODIFY"
    assert "worker lost: attempt 1" in d["unresolved_findings"]
    assert not any("invalid" in x for x in d["reasons"])  # the gate accepts the supervisor receipt itself
    # and the worker key can NOT verify it (isolation holds at the gate too)
    d2 = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=OPERATOR_KEY
    )
    assert any("invalid signature" in x for x in d2["reasons"])


def test_supervisor_skips_lease_that_already_has_a_receipt_but_marks_it(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)
    clock.advance(10)
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup") == []
    row = leases(path)[0]
    assert (row["status"], row["marked"], row["wrote"]) == ("EXPIRED", 1, 1)
    assert len(store.receipts_for_task(TASK)) == 1


def test_supervisor_ignores_live_and_released_leases(env):
    store, clock, path, epoch = env
    reg(store, "T2")
    lease(store, epoch, ttl=1000)
    lease(store, epoch, task="T2", worker="w2", ttl=1000)
    store.release_lease("T2", "w2", epoch)
    clock.advance(10)
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup") == []
    assert [r["marked"] for r in leases(path)] == [0, 0]


def test_supervisor_marks_only_lost_attempts_not_ones_that_wrote(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)  # attempt 1: lost without writing
    clock.advance(10)
    assert len(store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")) == 1
    lease(store, epoch, attempt=2, ttl=10)  # attempt 2: writes, then is lost
    store.append_receipt(tr(epoch, attempt=1, result="BLOCKED"), STORY, KEY)
    clock.advance(10)
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup") == []
    assert [(r["attempt"], r["wrote"], r["marked"]) for r in leases(path)] == [(1, 0, 1), (2, 1, 1)]
    assert len(supervisor_receipts(store)) == 1


def test_supervisor_candidate_head_comes_from_latest_receipt_of_task(env):
    store, clock, _, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch, candidate_head=HEAD2, result="BLOCKED"), STORY, KEY)
    clock.advance(10)
    store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")  # attempt 1 wrote: no marker
    lease(store, epoch, attempt=2, ttl=10)
    clock.advance(10)
    r = store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")[0]
    assert r["candidate_head"] == HEAD2 != manifest()["base_head"]


def test_supervisor_marker_chain_is_gap_free_across_losses_and_exhaustion(env):
    store, clock, _, epoch = env  # retry_cap 1
    results = []
    for attempt in (1, 2):
        lease(store, epoch, attempt=attempt, ttl=10)
        clock.advance(10)
        out = store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
        assert len(out) == 1
        results.append((out[0]["result"], out[0]["check_description"], out[0]["attempt"]))
    raises_kind("retry", lease, store, epoch, attempt=3)
    final = supervisor_receipts(store)[-1]
    results.append((final["result"], final["check_description"], final["attempt"]))
    assert results == [
        ("INCONCLUSIVE", "WORKER_LOST", 1),
        ("INCONCLUSIVE", "WORKER_LOST", 2),
        ("BLOCKED", "RETRY_EXHAUSTED", 3),
    ]
    chain = supervisor_receipts(store)
    assert chain[0]["prev_receipt_sha256"] is None
    assert chain[1]["prev_receipt_sha256"] == c.receipt_sha256(chain[0])
    assert chain[2]["prev_receipt_sha256"] == c.receipt_sha256(chain[1])
    assert all(signing.verify(x, SUPERVISOR_KEY) for x in chain)


def test_supervisor_argument_validation(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(10)
    raises_kind("argument", store.supervisor_reap_and_mark, SUPERVISOR_KEY, "")
    for bad in (b"", b"short", "s" * 40, None):
        raises_kind("argument", store.supervisor_reap_and_mark, bad, "sup")
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert leases(path)[0]["marked"] == 0
    assert len(store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")) == 1  # still possible


def test_zombie_late_receipt_after_fencing_is_rejected(env):
    store, clock, _, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(OWNER_TTL)
    new_epoch = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    raises_kind("epoch", store.append_receipt, tr(epoch), STORY, KEY)  # zombie holds the old epoch
    assert new_epoch == epoch + 1
    assert store.receipts_for_task(TASK)[0]["epoch"] == new_epoch  # marker carries the CURRENT epoch


# --- supervisor isolation


def test_worker_path_rejects_supervisor_slot_receipts_even_if_perfectly_signed(env):
    store, _, path, epoch = env
    lease(store, epoch)
    forged = supervisor_receipt(epoch=epoch, key=KEY)  # worker key
    genuine = supervisor_receipt(epoch=epoch)  # supervisor key
    for r in (forged, genuine):
        raises_kind("supervisor", store.append_receipt, r, STORY, KEY)
        raises_kind("supervisor", store.append_receipt, r, STORY, SUPERVISOR_KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert leases(path)[0]["wrote"] == 0


def test_supervisor_path_rejects_worker_slot_receipts(env):
    store, _, path, epoch = env
    lease(store, epoch)
    raises_kind("supervisor", store.append_supervisor_receipt, tr(epoch), STORY, supervisor_key=SUPERVISOR_KEY)
    raises_kind("supervisor", store.append_supervisor_receipt, tr(epoch), STORY, supervisor_key=KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_supervisor_receipt_must_be_signed_with_the_supervisor_key(env):
    store, _, path, epoch = env
    raises_kind(
        "signature", store.append_supervisor_receipt,
        supervisor_receipt(epoch=epoch, key=KEY), STORY, supervisor_key=SUPERVISOR_KEY,
    )
    raises_kind(
        "signature", store.append_supervisor_receipt,
        supervisor_receipt(epoch=epoch), STORY, supervisor_key=KEY,
    )
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_append_supervisor_receipt_accepts_a_genuine_marker_without_a_lease(env):
    store, _, path, epoch = env
    r = supervisor_receipt(epoch=epoch)
    store.append_supervisor_receipt(r, STORY, supervisor_key=SUPERVISOR_KEY)
    assert store.receipts_for_task(TASK) == [r]
    assert rows(path, "SELECT slot FROM receipts")[0][0] == SUPERVISOR_SLOT
    assert leases(path) == []


def test_append_supervisor_receipt_marker_shape_rules(env):
    store, _, path, epoch = env
    cases = [
        supervisor_receipt("SOMETHING-ELSE", epoch=epoch),  # unknown marker
        supervisor_receipt("WORKER_LOST", epoch=epoch, result="BLOCKED"),  # wrong result for marker
        supervisor_receipt("BUDGET_EXCEEDED", epoch=epoch, result="INCONCLUSIVE"),
        supervisor_receipt("RETRY_EXHAUSTED", epoch=epoch, result="PASS"),
        supervisor_receipt("WORKER_LOST", epoch=epoch, covered_acceptance=["AC-1"]),
    ]
    for r in cases:
        raises_kind("supervisor", store.append_supervisor_receipt, r, STORY, supervisor_key=SUPERVISOR_KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_append_supervisor_receipt_checks_link_epoch_and_chain(env):
    store, _, _, epoch = env
    raises_kind(
        "epoch", store.append_supervisor_receipt,
        supervisor_receipt(epoch=epoch - 1), STORY, supervisor_key=SUPERVISOR_KEY,
    )
    raises_kind(
        "task", store.append_supervisor_receipt,
        supervisor_receipt(epoch=epoch, task_id="ghost"), STORY, supervisor_key=SUPERVISOR_KEY,
    )
    raises_kind(
        "manifest", store.append_supervisor_receipt,
        supervisor_receipt(epoch=epoch, manifest_sha256="e" * 64), STORY, supervisor_key=SUPERVISOR_KEY,
    )
    first = supervisor_receipt(epoch=epoch)
    store.append_supervisor_receipt(first, STORY, supervisor_key=SUPERVISOR_KEY)
    raises_kind(
        "chain", store.append_supervisor_receipt,
        supervisor_receipt(epoch=epoch, attempt=2, prev="f" * 64, receipt_id="sup-2"),
        STORY, supervisor_key=SUPERVISOR_KEY,
    )
    store.append_supervisor_receipt(
        supervisor_receipt(epoch=epoch, attempt=2, prev=c.receipt_sha256(first), receipt_id="sup-2"),
        STORY, supervisor_key=SUPERVISOR_KEY,
    )


def test_append_supervisor_receipt_requires_strong_keyword_key(env):
    store, _, _, epoch = env
    with pytest.raises(TypeError):
        store.append_supervisor_receipt(supervisor_receipt(epoch=epoch), STORY)  # type: ignore[call-arg]
    for bad in (b"", b"short", None):
        raises_kind(
            "argument", store.append_supervisor_receipt,
            supervisor_receipt(epoch=epoch), STORY, supervisor_key=bad,
        )


def test_terminal_marker_through_append_supervisor_receipt_is_accepted_once(env):
    store, _, _, epoch = env
    first = supervisor_receipt("BUDGET_EXCEEDED", epoch=epoch)
    store.append_supervisor_receipt(first, STORY, supervisor_key=SUPERVISOR_KEY)
    again = supervisor_receipt(
        "BUDGET_EXCEEDED", epoch=epoch, attempt=2, prev=c.receipt_sha256(first), receipt_id="sup-2"
    )
    raises_kind("duplicate", store.append_supervisor_receipt, again, STORY, supervisor_key=SUPERVISOR_KEY)
    assert len(supervisor_receipts(store)) == 1


def test_non_documentation_receipt_in_supervisor_slot_is_a_contract_error(env):
    store, _, _, epoch = env
    bad = receipt("TestRun", epoch=epoch, slot=SUPERVISOR_SLOT)
    with pytest.raises(c.ContractError):
        store.append_supervisor_receipt(bad, STORY, supervisor_key=SUPERVISOR_KEY)


# --- budget marker


def test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 1)
    raises_kind("budget", store.charge, TASK, 5, supervisor_key=SUPERVISOR_KEY)
    assert len(supervisor_receipts(store)) == 1  # charge already committed the marker
    r = store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    assert r == supervisor_receipts(store)[0]  # idempotent: the existing marker is returned
    assert r["result"] == "BLOCKED" and r["check_description"] == "BUDGET_EXCEEDED"
    assert r["slot"] == SUPERVISOR_SLOT and r["attempt"] == 1 and r["epoch"] == epoch
    assert r["candidate_head"] == manifest()["base_head"]
    assert signing.verify(r, SUPERVISOR_KEY) and not signing.verify(r, KEY)
    assert c.derive_result(r) == "BLOCKED"
    assert store.receipts_for_task(TASK) == [r]
    assert "BUDGET_BLOCKED" in kinds(path)
    assert store.verify_event_chain()


def test_mark_budget_exceeded_directly_writes_the_marker_with_the_given_runner(env):
    store, _, path, epoch = env
    r = store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup-direct")
    assert r["runner_id"] == "sup-direct" and r["check_description"] == "BUDGET_EXCEEDED"
    assert kinds(path).count("BUDGET_BLOCKED") == 1
    assert store.verify_event_chain()


def test_mark_budget_exceeded_is_idempotent(env):
    store, _, path, _ = env
    first = store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    second = store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup-other")
    assert second == first  # the existing marker, unchanged
    assert len(store.receipts_for_task(TASK)) == 1
    assert kinds(path).count("BUDGET_BLOCKED") == 1
    assert len(rows(path, "SELECT 1 FROM receipts")) == 1


def test_mark_budget_exceeded_does_not_need_an_exceeded_budget_row(env):
    store, _, _, _ = env
    r = store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")  # no set_budget, no charge
    assert r["check_description"] == "BUDGET_EXCEEDED"


def test_mark_budget_exceeded_validation_and_unknown_task(env):
    store, _, path, _ = env
    raises_kind("task", store.mark_budget_exceeded, "OTHER", SUPERVISOR_KEY, "sup")
    raises_kind("argument", store.mark_budget_exceeded, TASK, b"short", "sup")
    raises_kind("argument", store.mark_budget_exceeded, TASK, SUPERVISOR_KEY, "")
    raises_kind("argument", store.mark_budget_exceeded, "", SUPERVISOR_KEY, "sup")
    with pytest.raises(TypeError):
        store.mark_budget_exceeded(TASK, "sup")  # type: ignore[call-arg]
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_budget_exceeded_marker_blocks_new_leases_and_worker_receipts(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    raises_kind("terminal", store.append_receipt, tr(epoch), STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    raises_kind("budget", lease, store, epoch, attempt=2)
    assert len(leases(path)) == 1


def test_budget_exceeded_marker_makes_gate_non_approving(env):
    store, _, _, epoch = env
    store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "MODIFY"
    assert any("terminal marker BUDGET_EXCEEDED" in x for x in d["reasons"])


def test_both_terminal_markers_can_coexist_in_one_gap_free_supervisor_chain(env):
    store, clock, _, epoch = env
    lose(store, clock, epoch, (1, 2))
    raises_kind("retry", lease, store, epoch, attempt=3)
    budget = store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    chain = supervisor_receipts(store)
    assert [x["check_description"] for x in chain] == [
        "WORKER_LOST", "WORKER_LOST", "RETRY_EXHAUSTED", "BUDGET_EXCEEDED",
    ]
    assert [x["attempt"] for x in chain] == [1, 2, 3, 4]
    assert budget["attempt"] == 4 and budget["prev_receipt_sha256"] == c.receipt_sha256(chain[2])


# ------------------------------------------------------------- event chain


def test_empty_event_chain_verifies_and_anchor_is_genesis(tmp_path):
    with open_store(str(tmp_path / "e.db")) as s:
        assert s.verify_event_chain() is True
        assert s.event_anchor() == (0, GENESIS_HASH)


def test_event_chain_links_to_genesis_and_grows(env):
    store, _, path, _ = env
    store.record_event(TASK, "actor", "NOTE", {"k": [1, 2]})
    evs = rows(path, "SELECT seq, prev_hash, hash FROM events ORDER BY seq")
    assert evs[0]["prev_hash"] == GENESIS_HASH
    for prev, cur in zip(evs, evs[1:]):
        assert cur["prev_hash"] == prev["hash"]
    assert len({e["hash"] for e in evs}) == len(evs)
    assert store.verify_event_chain()


def test_event_anchor_reports_count_and_head(env):
    store, _, path, _ = env
    count, head = store.event_anchor()
    evs = rows(path, "SELECT hash FROM events ORDER BY seq")
    assert count == len(evs) and head == evs[-1]["hash"]
    store.record_event(TASK, "a", "NOTE", {})
    count2, head2 = store.event_anchor()
    assert count2 == count + 1 and head2 != head


def test_event_hashes_are_keyed_not_plain_sha256(env):
    store, _, path, _ = env
    first = rows(path, "SELECT * FROM events ORDER BY seq LIMIT 1")[0]
    fields = {"ts": first["ts"], "task_id": first["task_id"], "actor": first["actor"],
              "kind": first["kind"], "payload": first["payload"]}
    plain = hashlib.sha256(GENESIS_HASH.encode() + c.canonical_bytes(fields)).hexdigest()
    assert first["hash"] != plain
    assert len(first["hash"]) == 64


def test_verification_with_a_different_event_key_fails(env):
    store, clock, path, epoch = env
    store.record_event(TASK, "a", "NOTE", {"n": 1})
    assert store.verify_event_chain() is True
    with open_store(path, clock, event_key=OTHER_EVENT_KEY) as wrong:
        assert wrong.verify_event_chain() is False
    with open_store(path, clock) as right:
        assert right.verify_event_chain() is True


def test_record_event_is_closed_to_store_internal_kinds(env):
    store, _, path, _ = env
    before = len(kinds(path))
    for kind in ("EPOCH_ACQUIRED", "LEASE_ACQUIRED", "RECEIPT_APPENDED", "BUDGET_EXCEEDED", "CUSTOM", "", " "):
        raises_kind("argument", store.record_event, TASK, "a", kind, {})
    assert len(kinds(path)) == before
    store.record_event(TASK, "a", "NOTE", {})
    assert kinds(path)[-1] == "NOTE"
    raises_kind("argument", store.record_event, TASK, "a", "OPERATOR_ACTION", {"op": "ok"})
    assert kinds(path)[-1] == "NOTE"


def test_record_event_argument_validation(env):
    store, _, _, _ = env
    for args in (("", "a", "NOTE"), ("t", "", "NOTE"), (" ", "a", "NOTE")):
        raises_kind("argument", store.record_event, *args, {})


def test_record_event_unserialisable_payload_is_rejected_and_rolled_back(env):
    store, _, path, _ = env
    before = len(kinds(path))
    with pytest.raises(c.ContractError):
        store.record_event(TASK, "a", "NOTE", {"bad": object()})
    with pytest.raises(c.ContractError):
        store.record_event(TASK, "a", "NOTE", {"nan": float("nan")})
    assert len(kinds(path)) == before
    assert store.verify_event_chain()


def test_events_table_rejects_unknown_kind_even_via_raw_sql(env):
    _, _, path, _ = env
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute(
                "INSERT INTO events (ts, task_id, actor, kind, payload, prev_hash, hash) "
                "VALUES (1, 't', 'a', 'EVIL', '{}', 'x', 'y')"
            )
    finally:
        conn.close()


def test_story_state_and_lease_status_are_closed_enums_in_the_database(env):
    store, _, path, epoch = env
    lease(store, epoch)
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute("UPDATE stories SET state = 'BOGUS'")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute("UPDATE leases SET status = 'BOGUS'")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            conn.execute("UPDATE leases SET wrote = 2")
    finally:
        conn.close()


def test_every_event_kind_the_store_writes_is_in_the_closed_set(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.set_phase(STORY, "owner-a", epoch, 6)
    store.renew_epoch(STORY, "owner-a", OWNER_TTL)
    store.set_budget(TASK, 1)
    with pytest.raises(StoreError):
        store.charge(TASK, 9, supervisor_key=SUPERVISOR_KEY)
    store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    clock.advance(10)
    store.reap_expired()
    store.release_epoch(STORY, "owner-a")
    assert set(kinds(path)) <= EVENT_KINDS
    assert {"TASK_REGISTERED", "LEASE_ACQUIRED", "RECEIPT_APPENDED", "PHASE_SET", "EPOCH_RENEWED",
            "BUDGET_EXCEEDED", "BUDGET_BLOCKED", "LEASE_EXPIRED", "LEASE_EXPIRED_PARTIAL",
            "EPOCH_RELEASED"} <= set(kinds(path))


def _tampered_copy(path, tmp_path, name, statements):
    """Copy the db with sqlite's backup API and apply attacker SQL to the COPY."""
    copy_path = str(tmp_path / name)
    src = sqlite3.connect(path)
    dst = sqlite3.connect(copy_path)
    src.backup(dst)
    src.close()
    for sql in statements:
        dst.execute(sql)
    dst.commit()
    dst.close()
    return copy_path


DROP_TRIGGERS = ["DROP TRIGGER events_no_update", "DROP TRIGGER events_no_delete"]
TAMPERS = {
    "payload_of_first": ["UPDATE events SET payload = '{}' WHERE seq = (SELECT MIN(seq) FROM events)"],
    "payload_of_last": ["UPDATE events SET payload = '{}' WHERE seq = (SELECT MAX(seq) FROM events)"],
    "ts": ["UPDATE events SET ts = ts + 1 WHERE seq = 2"],
    "actor": ["UPDATE events SET actor = 'evil' WHERE seq = 2"],
    "kind": ["UPDATE events SET kind = 'NOTE' WHERE seq = 2"],
    "hash_only": ["UPDATE events SET hash = '%s' WHERE seq = 2" % ("9" * 64)],
    "prev_hash_only": ["UPDATE events SET prev_hash = '%s' WHERE seq = 3" % ("9" * 64)],
    "delete_middle": ["DELETE FROM events WHERE seq = 2"],
    "delete_first": ["DELETE FROM events WHERE seq = (SELECT MIN(seq) FROM events)"],
    # truncation: the chain stays internally consistent, only the keyed anchor betrays it
    "truncate_last_one": ["DELETE FROM events WHERE seq = (SELECT MAX(seq) FROM events)"],
    "truncate_last_three": ["DELETE FROM events WHERE seq > (SELECT MAX(seq) - 3 FROM events)"],
    "truncate_everything": ["DELETE FROM events"],
    "anchor_deleted": ["DELETE FROM meta WHERE key = 'events_anchor'"],
    "anchor_forged_count_only": [
        "UPDATE meta SET value = json_set(value, '$.count', 1) WHERE key = 'events_anchor'"
    ],
    "anchor_mac_zeroed": [
        "UPDATE meta SET value = json_set(value, '$.mac', '%s') WHERE key = 'events_anchor'" % ("0" * 64)
    ],
    "anchor_garbage": ["UPDATE meta SET value = 'not json' WHERE key = 'events_anchor'"],
}


@pytest.mark.parametrize("name", sorted(TAMPERS))
def test_tampered_event_log_is_detected_on_a_copy(env, tmp_path, name):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.record_event(TASK, "a", "NOTE", {"n": 1})
    assert store.verify_event_chain() is True
    copy_path = _tampered_copy(path, tmp_path, f"copy-{name}.db", DROP_TRIGGERS + TAMPERS[name])
    with open_store(copy_path) as tampered:
        assert tampered.verify_event_chain() is False
    assert store.verify_event_chain() is True  # the original is untouched


def test_truncation_with_a_forged_unkeyed_anchor_is_detected(env, tmp_path):
    store, _, path, epoch = env
    store.record_event(TASK, "a", "NOTE", {})
    n, _ = store.event_anchor()
    prev_head = rows(path, "SELECT hash FROM events WHERE seq = ?", (n - 1,))[0][0]
    forged = json.dumps({"count": n - 1, "head": prev_head,
                         "mac": hashlib.sha256(f"{n - 1}:{prev_head}".encode()).hexdigest()})
    copy_path = _tampered_copy(
        path, tmp_path, "forged.db",
        DROP_TRIGGERS + [
            "DELETE FROM events WHERE seq = (SELECT MAX(seq) FROM events)",
            "UPDATE meta SET value = '%s' WHERE key = 'events_anchor'" % forged,
        ],
    )
    with open_store(copy_path) as tampered:
        assert tampered.verify_event_chain() is False


def test_rollback_to_an_older_consistent_pair_passes_the_chain_but_not_the_external_anchor(env, tmp_path):
    """Documented limit: a full rollback is only detectable via event_anchor() kept outside."""
    store, _, path, _ = env
    old_copy = _tampered_copy(path, tmp_path, "old.db", [])
    pinned = store.event_anchor()  # what an operator stored outside the database
    store.record_event(TASK, "a", "NOTE", {"later": True})
    pinned_later = store.event_anchor()
    assert pinned_later[0] == pinned[0] + 1
    with open_store(old_copy) as rolled_back:
        assert rolled_back.verify_event_chain() is True  # internally consistent
        assert rolled_back.event_anchor() == pinned
        assert rolled_back.event_anchor() != pinned_later  # external comparison catches it


def test_event_chain_verifies_after_a_rich_history_and_reopen(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)
    clock.advance(10)
    store.reap_expired()
    store.set_phase(STORY, "owner-a", epoch, 5)
    assert store.verify_event_chain()
    with open_store(path, clock) as again:
        assert again.verify_event_chain()
        again.record_event(TASK, "a", "NOTE", {})
        assert again.verify_event_chain()
    assert store.verify_event_chain()


# ------------------------------------------------------------------- budget


def _budget_row(path, task=TASK):
    row = rows(path, "SELECT cap, spent FROM budget WHERE task_id = ?", (task,))[0]
    return row["cap"], row["spent"]


def test_budget_row_is_seeded_from_the_manifest_cost_cap(env):
    store, _, path, _ = env
    assert _budget_row(path) == (100, 0)  # the default manifest has cost_cap 100
    reg(store, "T7", cost_cap=7)
    assert _budget_row(path, "T7") == (7, 0)
    assert store.charge("T7", 3, supervisor_key=SUPERVISOR_KEY) == 4
    store.register_task(manifest(task_id="T7", cost_cap=7))  # idempotent: spent is not reset
    assert _budget_row(path, "T7") == (7, 3)


def test_register_task_refuses_a_cost_cap_above_the_store_maximum(env):
    store, _, path, _ = env
    raises_kind("argument", store.register_task, manifest(task_id="TX", cost_cap=MAX_BUDGET + 1))
    assert rows(path, "SELECT 1 FROM tasks WHERE task_id = 'TX'") == []
    assert rows(path, "SELECT 1 FROM budget WHERE task_id = 'TX'") == []


def test_set_budget_above_the_manifest_cost_cap_is_refused(env):
    store, _, path, _ = env
    err = raises_kind("budget", store.set_budget, TASK, 101)
    assert "cost_cap" in str(err)
    assert _budget_row(path) == (100, 0)  # unchanged
    store.set_budget(TASK, 100)  # equal to the manifest cap is fine
    store.set_budget(TASK, 40)  # lowering is fine
    assert _budget_row(path) == (40, 0)
    raises_kind("budget", store.set_budget, TASK, 41 + 59 + 1)  # cannot be raised above 100 again
    assert _budget_row(path) == (40, 0)


def test_set_budget_needs_a_registered_task_and_creates_no_row(env):
    store, _, path, _ = env
    raises_kind("task", store.set_budget, "ghost", 5)
    assert rows(path, "SELECT 1 FROM budget WHERE task_id = 'ghost'") == []
    raises_kind("argument", store.set_budget, "", 5)


def marker_rows(path, task=TASK):
    return [
        json.loads(r["body"])
        for r in rows(
            path,
            "SELECT body FROM receipts WHERE task_id = ? AND slot = ? ORDER BY attempt",
            (task, SUPERVISOR_SLOT),
        )
    ]


def event_payloads(path, kind, task=TASK):
    return [
        json.loads(r["payload"])
        for r in rows(
            path, "SELECT payload FROM events WHERE kind = ? AND task_id = ? ORDER BY seq",
            (kind, task),
        )
    ]


def test_acquire_lease_at_a_zero_cap_with_nothing_spent_succeeds_without_a_marker(env):
    store, _, path, epoch = env
    m = reg(store, "TZ", cost_cap=0)  # spent 0, cap 0: the task may start
    lease(store, epoch, task="TZ")
    assert len(leases(path)) == 1
    r = bound(m, epoch=epoch, task_id="TZ")
    assert r["result"] == "PASS"
    store.append_receipt(r, STORY, KEY)  # a worker PASS receipt is accepted
    assert len(rows(path, "SELECT 1 FROM receipts WHERE task_id = 'TZ'")) == 1
    assert marker_rows(path, "TZ") == []
    assert kinds(path).count("BUDGET_EXCEEDED") == 0 and kinds(path).count("BUDGET_BLOCKED") == 0
    assert store.verify_event_chain()
    assert_no_dangling_transaction(path)


def test_charge_on_a_zero_cap_task_raises_budget_writes_the_marker_then_blocks_new_leases(env):
    store, _, path, epoch = env
    reg(store, "TZ", cost_cap=0)
    err = raises_kind("budget", store.charge, "TZ", 1, supervisor_key=SUPERVISOR_KEY)
    assert "TZ" in str(err)
    (m,) = marker_rows(path, "TZ")
    assert (m["check_description"], m["result"]) == ("BUDGET_EXCEEDED", "BLOCKED")
    assert signing.verify(m, SUPERVISOR_KEY)
    assert event_payloads(path, "BUDGET_EXCEEDED", "TZ") == [{"amount": 1, "cap": 0, "spent": 0}]
    assert _budget_row(path, "TZ") == (0, 0)  # nothing was charged
    raises_kind("budget", lease, store, epoch, task="TZ", worker="w2", attempt=2)
    assert len(marker_rows(path, "TZ")) == 1  # the marker is not duplicated
    assert store.verify_event_chain()


def test_acquire_lease_at_spent_equal_to_cap_starts_without_a_marker(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 5)
    assert store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY) == 0  # exactly the cap: no overspend
    assert marker_rows(path) == [] and kinds(path).count("BUDGET_EXCEEDED") == 0
    lease(store, epoch)  # spent == cap does NOT block a lease (only spent > cap does)
    assert len(leases(path)) == 1 and leases(path)[0]["status"] == "LIVE"
    assert marker_rows(path) == []  # no signed marker was committed by the lease attempt
    assert kinds(path).count("BUDGET_EXCEEDED") == 0 and kinds(path).count("BUDGET_BLOCKED") == 0
    assert _budget_row(path) == (5, 5)  # the lease charged nothing
    assert store.verify_event_chain()
    assert_no_dangling_transaction(path)


def test_acquire_lease_above_the_cap_commits_the_signed_marker_and_then_raises(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 5)
    store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY)
    conn = raw(path)
    conn.execute("UPDATE budget SET spent = cap + 1 WHERE task_id = ?", (TASK,))  # real overspend (6 of 5)
    conn.commit()
    conn.close()
    err = raises_kind("budget", lease, store, epoch)
    assert "budget" in str(err)
    assert leases(path) == [] and slot_map(path) == {1: None, 2: None}
    (m,) = marker_rows(path)
    assert (m["check_description"], m["result"], m["runner_id"]) == (
        "BUDGET_EXCEEDED", "BLOCKED", "store-supervisor")
    assert signing.verify(m, SUPERVISOR_KEY) and not signing.verify(m, KEY)
    assert m["epoch"] == epoch and m["manifest_sha256"] == c.manifest_sha256(manifest())
    assert event_payloads(path, "BUDGET_EXCEEDED") == [{"amount": 0, "cap": 5, "spent": 6}]
    assert _budget_row(path) == (5, 6)  # nothing was charged by the refusal
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "MODIFY" and any("BUDGET_EXCEEDED" in x for x in d["reasons"])
    assert store.verify_event_chain()


def test_repeated_acquire_lease_above_the_cap_adds_exactly_one_marker_and_one_event(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 5)
    conn = raw(path)
    conn.execute("UPDATE budget SET spent = 6 WHERE task_id = ?", (TASK,))  # spent > cap
    conn.commit()
    conn.close()
    for attempt in (1, 1, 2, 7):
        raises_kind("budget", lease, store, epoch, attempt=attempt)
    assert len(marker_rows(path)) == 1
    assert kinds(path).count("BUDGET_EXCEEDED") == 1
    assert kinds(path).count("BUDGET_BLOCKED") == 1
    # a later overspend by charge and mark_budget_exceeded add nothing either
    raises_kind("budget", store.charge, TASK, 1, supervisor_key=SUPERVISOR_KEY)
    store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    assert len(marker_rows(path)) == 1
    assert kinds(path).count("BUDGET_EXCEEDED") == 1 and kinds(path).count("BUDGET_BLOCKED") == 1
    assert [x["attempt"] for x in marker_rows(path)] == [1]  # gap-free supervisor chain
    assert store.verify_event_chain()


def test_repeated_acquire_lease_at_exactly_the_cap_never_creates_a_marker(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 5)
    store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY)
    lease(store, epoch)
    n_events = len(kinds(path))
    for attempt in (1, 2, 3):  # live lease / wrong attempt: refused for OTHER reasons, never 'budget'
        err = pytest.raises(StoreError, lease, store, epoch, attempt=attempt)
        assert err.value.kind != "budget", str(err.value)
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)  # a fresh lease at spent == cap is still fine
    assert marker_rows(path) == []
    assert kinds(path).count("BUDGET_EXCEEDED") == 0 and kinds(path).count("BUDGET_BLOCKED") == 0
    assert _budget_row(path) == (5, 5)
    assert len(kinds(path)) >= n_events and store.verify_event_chain()


def test_budget_exceeded_event_is_written_once_when_charge_comes_first(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 5)
    raises_kind("budget", store.charge, TASK, 6, supervisor_key=SUPERVISOR_KEY)
    assert event_payloads(path, "BUDGET_EXCEEDED") == [{"amount": 6, "cap": 5, "spent": 0}]
    raises_kind("budget", lease, store, epoch)  # the marker exists: terminal -> budget
    raises_kind("budget", store.charge, TASK, 9, supervisor_key=SUPERVISOR_KEY)
    assert kinds(path).count("BUDGET_EXCEEDED") == 1 and len(marker_rows(path)) == 1


def test_append_receipt_at_exactly_the_cap_is_allowed_and_finishes_the_task(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.set_budget(TASK, 5)
    assert store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY) == 0  # spent == cap
    for rtype in ("TestRun", "StaticAnalysis", "IndependentReview"):
        store.append_receipt(receipt(rtype, epoch=epoch), STORY, KEY)  # the final receipts persist
    assert len(rows(path, "SELECT 1 FROM receipts")) == 3
    assert leases(path)[0]["wrote"] == 1
    assert marker_rows(path) == [] and kinds(path).count("BUDGET_EXCEEDED") == 0
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "APPROVE", d["reasons"]
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)  # a new lease at spent == cap is allowed too
    assert marker_rows(path) == [] and kinds(path).count("BUDGET_EXCEEDED") == 0
    d2 = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d2["verdict"] == "APPROVE", d2["reasons"]  # the lease did not invalidate the PASS set


def test_append_receipt_refuses_only_above_the_cap(env):
    store, _, path, epoch = env
    lease(store, epoch)
    conn = raw(path)
    conn.execute("UPDATE budget SET spent = cap + 1 WHERE task_id = ?", (TASK,))  # attacker/bug: spent > cap
    conn.commit()
    conn.close()
    n_events = len(kinds(path))
    err = raises_kind("budget", store.append_receipt, tr(epoch), STORY, KEY)
    assert "budget" in str(err)
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert leases(path)[0]["wrote"] == 0
    assert len(kinds(path)) == n_events
    assert_no_dangling_transaction(path)


def test_append_receipt_after_the_budget_marker_is_refused_as_terminal(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.set_budget(TASK, 5)
    store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY)
    raises_kind("budget", store.charge, TASK, 1, supervisor_key=SUPERVISOR_KEY)  # now the marker exists
    raises_kind("terminal", store.append_receipt, tr(epoch), STORY, KEY)
    assert rows(path, "SELECT slot FROM receipts") != [] and all(
        r["slot"] == SUPERVISOR_SLOT for r in rows(path, "SELECT slot FROM receipts"))


def test_charge_over_cap_commits_the_marker_and_then_raises(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.set_budget(TASK, 10)
    assert store.charge(TASK, 8, supervisor_key=SUPERVISOR_KEY) == 2
    raises_kind(
        "budget", store.charge, TASK, 3, supervisor_key=SUPERVISOR_KEY, runner_id="meter-1"
    )
    assert _budget_row(path) == (10, 8)  # nothing of the refused amount was charged
    # the marker was committed although the call raised (visible to a raw connection)
    markers = [json.loads(r["body"]) for r in rows(
        path, "SELECT body FROM receipts WHERE slot = ?", (SUPERVISOR_SLOT,))]
    assert len(markers) == 1
    m = markers[0]
    assert (m["check_description"], m["result"], m["runner_id"]) == ("BUDGET_EXCEEDED", "BLOCKED", "meter-1")
    assert signing.verify(m, SUPERVISOR_KEY) and not signing.verify(m, KEY)
    assert kinds(path).count("BUDGET_EXCEEDED") == 1 and kinds(path).count("BUDGET_BLOCKED") == 1
    # later work is refused
    raises_kind("terminal", store.append_receipt, tr(epoch), STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    raises_kind("budget", lease, store, epoch, attempt=2)
    # a second overspend raises again but adds no second marker
    raises_kind("budget", store.charge, TASK, 9, supervisor_key=SUPERVISOR_KEY)
    assert len(supervisor_receipts(store)) == 1
    assert kinds(path).count("BUDGET_BLOCKED") == 1
    assert store.verify_event_chain()
    d = gate.evaluate(
        manifest(), store.receipts_for_task(TASK), HEAD, epoch, KEY, supervisor_key=SUPERVISOR_KEY
    )
    assert d["verdict"] == "MODIFY" and any("BUDGET_EXCEEDED" in x for x in d["reasons"])


def test_charge_default_marker_runner_is_the_store_supervisor(env):
    store, _, _, _ = env
    store.set_budget(TASK, 1)
    raises_kind("budget", store.charge, TASK, 2, supervisor_key=SUPERVISOR_KEY)
    assert supervisor_receipts(store)[0]["runner_id"] == "store-supervisor"


def test_charge_returns_remaining_and_allows_exact_cap(env):
    store, _, path, _ = env
    store.set_budget(TASK, 10)
    assert store.charge(TASK, 4, supervisor_key=SUPERVISOR_KEY) == 6
    assert store.charge(TASK, 0, supervisor_key=SUPERVISOR_KEY) == 6
    assert store.charge(TASK, 6, supervisor_key=SUPERVISOR_KEY) == 0
    assert _budget_row(path) == (10, 10)
    assert supervisor_receipts(store) == []  # exact cap is not an overspend


def test_charge_over_cap_charges_nothing_and_keeps_the_log_valid(env):
    store, _, path, _ = env
    store.set_budget(TASK, 10)
    store.charge(TASK, 8, supervisor_key=SUPERVISOR_KEY)
    raises_kind("budget", store.charge, TASK, 3, supervisor_key=SUPERVISOR_KEY)
    assert _budget_row(path) == (10, 8)
    assert kinds(path).count("BUDGET_EXCEEDED") == 1
    assert store.verify_event_chain()


def test_charge_unknown_task_bad_amount_and_key_arguments(env):
    store, _, path, _ = env
    raises_kind("task", store.charge, "nobody", 1, supervisor_key=SUPERVISOR_KEY)
    store.set_budget(TASK, 5)
    for amount in (-1, True, 1.5, "1", MAX_BUDGET + 1):
        raises_kind("argument", store.charge, TASK, amount, supervisor_key=SUPERVISOR_KEY)
    with pytest.raises(TypeError):
        store.charge(TASK, 1)  # type: ignore[call-arg]
    for bad in (b"", b"short", "s" * 40, None):
        raises_kind("argument", store.charge, TASK, 1, supervisor_key=bad)
    raises_kind("argument", store.charge, TASK, 1, supervisor_key=SUPERVISOR_KEY, runner_id="")
    assert _budget_row(path) == (5, 0)
    assert supervisor_receipts(store) == []


def test_zero_cap_rejects_any_positive_charge(env):
    store, _, _, epoch = env
    store.set_budget(TASK, 0)
    assert store.charge(TASK, 0, supervisor_key=SUPERVISOR_KEY) == 0
    lease(store, epoch)  # nothing spent: a zero cap does not forbid starting
    raises_kind("budget", store.charge, TASK, 1, supervisor_key=SUPERVISOR_KEY)
    assert supervisor_receipts(store)[0]["check_description"] == "BUDGET_EXCEEDED"


def test_set_budget_preserves_spent_validates_and_refuses_cap_below_spent(env):
    store, _, path, _ = env
    store.set_budget(TASK, 10)
    store.charge(TASK, 7, supervisor_key=SUPERVISOR_KEY)
    store.set_budget(TASK, 20)
    assert _budget_row(path) == (20, 7)
    for cap in (-1, True, 1.5, MAX_BUDGET + 1):
        raises_kind("argument", store.set_budget, TASK, cap)
    raises_kind("argument", store.set_budget, TASK, 6)  # below what is already spent
    assert _budget_row(path) == (20, 7)


def test_max_budget_boundary_is_accepted(env):
    store, _, path, _ = env
    reg(store, "TM", cost_cap=MAX_BUDGET)
    assert _budget_row(path, "TM") == (MAX_BUDGET, 0)
    assert store.charge("TM", MAX_BUDGET, supervisor_key=SUPERVISOR_KEY) == 0
    raises_kind("budget", store.charge, "TM", 1, supervisor_key=SUPERVISOR_KEY)
    raises_kind("budget", store.set_budget, TASK, MAX_BUDGET)  # above TASK's own cost_cap


def test_concurrent_charges_never_exceed_the_cap(tmp_path):
    path = str(tmp_path / "race.db")
    store, clock, _ = new_env(path)
    store.set_budget(TASK, 10)
    store.close()
    barrier = threading.Barrier(8)
    results = []
    guard = threading.Lock()

    def worker():
        st = open_store(path, clock)
        try:
            barrier.wait()
            try:
                st.charge(TASK, 2, supervisor_key=SUPERVISOR_KEY)
                out = "ok"
            except StoreError as exc:
                out = exc.kind
        finally:
            st.close()
        with guard:
            results.append(out)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert results.count("ok") == 5 and results.count("budget") == 3
    assert _budget_row(path) == (10, 10)
    # three overspends raced, exactly one BUDGET_EXCEEDED marker exists
    assert len(rows(path, "SELECT 1 FROM receipts WHERE slot = ?", (SUPERVISOR_SLOT,))) == 1
    assert kinds(path).count("BUDGET_BLOCKED") == 1


# --------------------------------------------------------------- int bounds


@pytest.mark.parametrize("n", [0, -1, MAX_SLOTS + 1, True, 1.5, "2", None])
def test_init_slots_bounds(tmp_path, n):
    with open_store(str(tmp_path / "s.db")) as s:
        raises_kind("argument", s.init_slots, n)


def test_init_slots_boundary_and_idempotence(tmp_path):
    path = str(tmp_path / "s.db")
    with open_store(path) as s:
        s.init_slots(MAX_SLOTS)
        s.init_slots(3)
        assert len(rows(path, "SELECT 1 FROM slots")) == MAX_SLOTS


def test_counter_boundaries_are_accepted_exactly_at_the_limit(env):
    store, _, _, epoch = env
    # one past the limit is an argument error, the limit itself passes validation
    raises_kind("argument", lease, store, MAX_COUNTER + 1)
    raises_kind("epoch", lease, store, MAX_COUNTER)  # valid integer, but not the current epoch
    raises_kind("argument", lease, store, epoch, attempt=MAX_COUNTER + 1)
    raises_kind("lease", lease, store, epoch, attempt=MAX_COUNTER)  # valid, but not previous + 1


def test_ttl_boundary_is_accepted_exactly_at_the_limit(env):
    store, _, _, epoch = env
    lease(store, epoch, ttl=MAX_TTL_SEC)
    store.heartbeat(TASK, WORKER, epoch, MAX_TTL_SEC)
    raises_kind("argument", store.heartbeat, TASK, WORKER, epoch, MAX_TTL_SEC + 1)


# ------------------------------------------------------------------- render


def test_render_state_md_is_deterministic_and_marked_generated(env):
    store, _, _, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    first = store.render_state_md(STORY)
    assert first == store.render_state_md(STORY)
    lines = first.splitlines()
    assert "GENERATED VIEW" in lines[0] and "do not edit" in lines[0]
    assert f"# STATE: {STORY}" in first
    assert f"- epoch: {epoch}" in first and "- owner: owner-a" in first
    assert f"| T1 | 1 | {WORKER} | {epoch} |" in first and "| LIVE | 1 | 0 |" in first
    assert c.receipt_sha256(tr(epoch)) in first
    assert "| T1 | tests | 1 | TestRun | PASS |" in first
    assert first.endswith("\n")


def test_render_state_md_identical_for_identical_histories(tmp_path):
    outs = []
    for name in ("a", "b"):
        store, _, ep = new_env(str(tmp_path / f"{name}.db"), slots=1)
        lease(store, ep, ttl=20)
        store.append_receipt(tr(ep), STORY, KEY)
        outs.append(store.render_state_md(STORY))
        store.close()
    assert outs[0] == outs[1]


def test_render_state_md_shows_lease_history_and_changes(env):
    store, _, _, epoch = env
    lease(store, epoch, ttl=10)
    before = store.render_state_md(STORY)
    assert "| LIVE |" in before
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)
    after = store.render_state_md(STORY)
    assert before != after
    assert "| RELEASED |" in after and "| LIVE |" in after  # both history rows are rendered
    raises_kind("story", store.render_state_md, "missing")


def test_render_state_md_is_read_only(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    n = len(kinds(path))
    store.render_state_md(STORY)
    assert len(kinds(path)) == n


# ---------------------------------------- second round: keys, anchor, snapshots


def test_supervisor_key_equal_to_the_event_key_is_refused_everywhere(env):
    store, _, path, epoch = env
    n_events = len(kinds(path))
    for bad in (EVENT_KEY, bytearray(EVENT_KEY)):
        raises_kind("key", lease, store, epoch, supervisor_key=bad)
        raises_kind("key", store.charge, TASK, 1, supervisor_key=bad)
        raises_kind("key", store.supervisor_reap_and_mark, bad, "sup")
        raises_kind("key", store.mark_budget_exceeded, TASK, bad, "sup")
    raises_kind(
        "key", store.append_supervisor_receipt, supervisor_receipt(epoch=epoch), STORY,
        supervisor_key=EVENT_KEY,
    )
    assert len(kinds(path)) == n_events
    assert rows(path, "SELECT 1 FROM receipts") == [] and leases(path) == []
    assert _budget_row(path) == (100, 0)
    # equality only: a key that differs in one byte is a different key
    almost = EVENT_KEY[:-1] + b"?"
    lease(store, epoch, supervisor_key=almost)


def test_caller_cannot_record_operator_action_events(env):
    store, _, path, _ = env
    n = len(kinds(path))
    raises_kind("argument", store.record_event, TASK, "a", "OPERATOR_ACTION", {"op": "forged"})
    assert len(kinds(path)) == n and "OPERATOR_ACTION" not in kinds(path)
    assert "OPERATOR_ACTION" not in EVENT_KINDS


def _events_and_meta(path):
    ev = [tuple(r) for r in rows(path, "SELECT * FROM events ORDER BY seq")]
    meta = [tuple(r) for r in rows(path, "SELECT * FROM meta ORDER BY key")]
    return ev, meta


INTEGRITY = {
    "anchor_deleted": ["DELETE FROM meta WHERE key = 'events_anchor'"],
    "anchor_forged_count": [
        "UPDATE meta SET value = json_set(value, '$.count', 1) WHERE key = 'events_anchor'"
    ],
    "anchor_forged_head": [
        "UPDATE meta SET value = json_set(value, '$.head', '%s') WHERE key = 'events_anchor'" % ("9" * 64)
    ],
    "anchor_mac_zeroed": [
        "UPDATE meta SET value = json_set(value, '$.mac', '%s') WHERE key = 'events_anchor'" % ("0" * 64)
    ],
    "anchor_garbage": ["UPDATE meta SET value = 'not json' WHERE key = 'events_anchor'"],
    "anchor_missing_fields": ["UPDATE meta SET value = '{\"count\": 3}' WHERE key = 'events_anchor'"],
    "truncate_last_one": ["DELETE FROM events WHERE seq = (SELECT MAX(seq) FROM events)"],
    "truncate_last_three": ["DELETE FROM events WHERE seq > (SELECT MAX(seq) - 3 FROM events)"],
    "truncate_everything": ["DELETE FROM events"],
    "delete_first": ["DELETE FROM events WHERE seq = (SELECT MIN(seq) FROM events)"],
    "delete_middle": ["DELETE FROM events WHERE seq = 2"],
    "last_hash_replaced": [
        "UPDATE events SET hash = '%s' WHERE seq = (SELECT MAX(seq) FROM events)" % ("7" * 64)
    ],
}


@pytest.mark.parametrize("name", sorted(INTEGRITY))
def test_anchor_tamper_raises_integrity_on_append_and_is_never_repaired(env, tmp_path, name):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.record_event(TASK, "a", "NOTE", {"n": 1})
    copy_path = _tampered_copy(path, tmp_path, f"int-{name}.db", DROP_TRIGGERS + INTEGRITY[name])
    before = _events_and_meta(copy_path)
    with open_store(copy_path) as t:
        raises_kind("integrity", t.record_event, TASK, "a", "NOTE", {"n": 2})
        raises_kind("integrity", t.event_anchor)
        raises_kind("integrity", t.set_phase, STORY, "owner-a", epoch, 6)
        assert t.get_phase(STORY) == 4  # the failed mutation was rolled back
        assert t.verify_event_chain() is False
        raises_kind("integrity", t.record_event, TASK, "a", "NOTE", {"n": 3})  # still refused
    assert _events_and_meta(copy_path) == before  # nothing recomputed, nothing re-sealed
    assert store.verify_event_chain() is True


def _mac(count, head, key=EVENT_KEY):
    return hmac.new(key, b"vst-anchor-v1\0" + f"{count}:{head}".encode(), hashlib.sha256).hexdigest()


def _set_anchor(path, count, head, mac):
    conn = sqlite3.connect(path)
    conn.execute(
        "UPDATE meta SET value = ? WHERE key = 'events_anchor'",
        (json.dumps({"count": count, "head": head, "mac": mac}, sort_keys=True),),
    )
    conn.commit()
    conn.close()


def test_correctly_keyed_anchor_with_wrong_count_or_head_is_still_integrity(env, tmp_path):
    """Defence in depth: even a holder of the event key cannot get a mismatching anchor accepted."""
    store, _, path, _ = env
    n, head = store.event_anchor()
    # control: a forged anchor that is consistent (valid MAC, true count and head) is accepted,
    # so the integrity results below are caused by the mismatch and not by a wrong MAC helper
    ok_path = _tampered_copy(path, tmp_path, "ok.db", [])
    _set_anchor(ok_path, n, head, _mac(n, head))
    with open_store(ok_path) as t:
        t.record_event(TASK, "a", "NOTE", {})
    for label, count, h in (("count_low", n - 1, head), ("count_high", n + 5, head), ("head", n, "9" * 64)):
        p = _tampered_copy(path, tmp_path, f"{label}.db", [])
        _set_anchor(p, count, h, _mac(count, h))
        with open_store(p) as t:
            err = raises_kind("integrity", t.record_event, TASK, "a", "NOTE", {})
            assert "anchor" in str(err)


def test_an_empty_log_without_an_anchor_is_fine_and_the_first_event_creates_it(tmp_path):
    with open_store(str(tmp_path / "empty.db")) as s:
        assert rows(str(tmp_path / "empty.db"), "SELECT 1 FROM meta") == []
        s.record_event(TASK, "a", "NOTE", {})  # first event creates the anchor
        assert s.event_anchor()[0] == 1


def test_event_anchor_equals_the_stored_keyed_anchor(env):
    store, _, path, _ = env
    count, head = store.event_anchor()
    stored = json.loads(rows(path, "SELECT value FROM meta WHERE key = 'events_anchor'")[0][0])
    assert (stored["count"], stored["head"]) == (count, head)
    assert stored["mac"] == _mac(count, head)


def test_snapshot_reads_under_a_concurrent_writer_never_report_tamper(tmp_path):
    path = str(tmp_path / "snap.db")
    store, clock, _ = new_env(path)
    store.close()
    stop = threading.Event()
    errors = []

    def writer():
        st = open_store(path, clock)
        try:
            for n in range(150):
                st.record_event(TASK, "w", "NOTE", {"n": n})
        except BaseException as exc:  # noqa: BLE001 - reported through errors
            errors.append(("writer", repr(exc)))
        finally:
            st.close()
            stop.set()

    t = threading.Thread(target=writer)
    t.start()
    reader = open_store(path, clock)
    checks, last = 0, 0
    try:
        while not stop.is_set() or checks < 5:
            if reader.verify_event_chain() is not True:
                errors.append(("verify", checks))
            count, _head = reader.event_anchor()
            if count < last:
                errors.append(("anchor went backwards", count, last))
            last = count
            reader.render_state_md(STORY)
            checks += 1
    except StoreError as exc:
        errors.append(("reader", exc.kind, str(exc)))
    finally:
        reader.close()
        t.join(60)
    assert errors == []
    assert checks >= 5
    with open_store(path, clock) as final:
        assert final.verify_event_chain() is True
        assert final.event_anchor()[0] == len(rows(path, "SELECT 1 FROM events"))


# ------------------------------------------------- LEASE_EXPIRED_PARTIAL events


def test_lease_that_wrote_receipts_and_then_expired_records_a_partial_event(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.append_receipt(receipt("StaticAnalysis", epoch=epoch), STORY, KEY)
    clock.advance(10)
    assert store.reap_expired() == [TASK]
    evs = rows(
        path, "SELECT seq, kind, payload FROM events WHERE kind LIKE 'LEASE_EXPIRED%' ORDER BY seq"
    )
    assert [e["kind"] for e in evs] == ["LEASE_EXPIRED", "LEASE_EXPIRED_PARTIAL"]
    assert evs[1]["seq"] == evs[0]["seq"] + 1
    lease_row = leases(path)[0]
    assert json.loads(evs[1]["payload"]) == {
        "attempt": 1, "lease_id": lease_row["lease_id"], "receipts": 2,
    }
    assert (lease_row["status"], lease_row["wrote"], lease_row["receipt_count"]) == ("EXPIRED", 1, 2)
    assert supervisor_receipts(store) == []  # still no WORKER_LOST marker
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup") == []
    assert store.verify_event_chain()


def test_expired_lease_without_receipts_has_no_partial_event(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    clock.advance(10)
    store.reap_expired()
    assert kinds(path).count("LEASE_EXPIRED") == 1
    assert "LEASE_EXPIRED_PARTIAL" not in kinds(path)
    assert leases(path)[0]["receipt_count"] == 0


def test_partial_event_counts_receipts_per_lease_and_fires_through_acquire_lease(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch, result="BLOCKED"), STORY, KEY)
    clock.advance(10)
    lease(store, epoch, attempt=2, ttl=10)  # reaps attempt 1 on the way (wrote: no marker needed)
    a1 = tr(epoch, result="BLOCKED")
    store.append_receipt(
        tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), result="BLOCKED"), STORY, KEY
    )
    store.append_receipt(receipt("StaticAnalysis", epoch=epoch), STORY, KEY)
    clock.advance(10)
    store.reap_expired()
    payloads = [
        json.loads(r["payload"])
        for r in rows(path, "SELECT payload FROM events WHERE kind = 'LEASE_EXPIRED_PARTIAL' ORDER BY seq")
    ]
    assert [(p["attempt"], p["receipts"]) for p in payloads] == [(1, 1), (2, 2)]  # per lease


def test_released_and_fenced_leases_with_receipts_have_no_partial_event(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=5000)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    reg(store, "T2")
    lease(store, epoch, task="T2", worker="w2", ttl=5000)
    store.append_receipt(
        bound(manifest(task_id="T2"), "TestRun", KEY, epoch=epoch, task_id="T2",
              runner_id="w2", receipt_id="t2-r"),
        STORY, KEY,
    )
    clock.advance(OWNER_TTL)
    store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert "LEASE_FENCED" in kinds(path) and "LEASE_RELEASED" in kinds(path)
    assert "LEASE_EXPIRED_PARTIAL" not in kinds(path)


def test_schema_has_the_receipt_count_column_defaulting_to_zero(env):
    store, _, path, epoch = env
    cols = {r["name"]: r for r in rows(path, "PRAGMA table_info(leases)")}
    assert "receipt_count" in cols and cols["receipt_count"]["dflt_value"] == "0"
    lease(store, epoch)
    assert leases(path)[0]["receipt_count"] == 0
    store.append_receipt(tr(epoch), STORY, KEY)
    assert leases(path)[0]["receipt_count"] == 1


# ------------------------------------------------ third round: store decisions
# (A) budget boundary is covered in the budget section above.
# (B) slot-chain bound per epoch, (C) failed_attempts, (D) epoch reaping and
# heartbeat gates, (F) worker key and receipts_for_task integrity.

ALL_SLOT_TYPES = ("TestRun", "StaticAnalysis", "IndependentReview")


def test_takeover_after_a_full_pass_set_lets_the_new_epoch_write_its_receipts(env):
    store, clock, path, epoch = env
    m = reg(store, "T0", retry_cap=0)  # one attempt per slot per epoch
    lease(store, epoch, task="T0", ttl=5000)
    first = {}
    for rtype in ALL_SLOT_TYPES:
        first[rtype] = slot_run(epoch, 1, task="T0", m=m, rtype=rtype)
        store.append_receipt(first[rtype], STORY, KEY)
    # PASS receipts never count against the per-epoch bound (retry_cap 0 -> 1 non-PASS allowed)
    assert store.failed_attempts("T0") == 0
    clock.advance(OWNER_TTL)
    epoch2 = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert epoch2 == epoch + 1
    assert [r["status"] for r in leases(path) if r["task_id"] == "T0"] == ["FENCED"]
    assert store.failed_attempts("T0") == 0
    lease(store, epoch2, task="T0", attempt=2)  # global lease attempt; the fenced lease wrote, no marker
    restart = slot_run(epoch2, 1, None, task="T0", m=m, receipt_id="e2-restart")
    raises_kind("chain", store.append_receipt, restart, STORY, KEY)  # attempt numbers stay global
    second = {}
    for rtype in ALL_SLOT_TYPES:  # attempt numbers stay global; the epoch count restarts
        second[rtype] = slot_run(
            epoch2, 2, c.receipt_sha256(first[rtype]), task="T0", m=m, rtype=rtype,
            receipt_id=f"e2-{rtype}",
        )
        store.append_receipt(second[rtype], STORY, KEY)
    assert store.failed_attempts("T0") == 0
    stored = store.receipts_for_task("T0")
    assert sorted((r["slot"], r["attempt"], r["epoch"]) for r in stored) == sorted(
        [(sl, a, e) for sl in ("tests", "static", "review") for a, e in ((1, epoch), (2, epoch2))]
    )
    d = gate.evaluate(m, stored, HEAD, epoch2, KEY, supervisor_key=SUPERVISOR_KEY)
    assert d["verdict"] == "APPROVE", d["reasons"]


def test_slot_chain_bound_counts_only_non_pass_receipts_of_the_current_epoch(env):
    store, clock, path, epoch = env  # retry_cap 1 -> two NON-PASS receipts per slot per epoch
    lease(store, epoch, ttl=5000)
    a1 = tr(epoch, attempt=1, result="BLOCKED")  # epoch 1: one non-PASS ...
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), receipt_id="a2")  # ... one PASS
    store.append_receipt(a1, STORY, KEY)
    store.append_receipt(a2, STORY, KEY)
    assert store.failed_attempts(TASK) == 1
    clock.advance(OWNER_TTL)
    epoch2 = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    lease(store, epoch2, attempt=2)
    prev = a2
    for n in (3, 4):  # attempts 3 and 4 are the first two non-PASS of epoch 2: both allowed
        prev = tr(epoch2, attempt=n, prev_receipt_sha256=c.receipt_sha256(prev), receipt_id=f"b{n}",
                  result="BLOCKED")
        store.append_receipt(prev, STORY, KEY)  # if epoch-1 receipts were counted, b4 would be refused
    b5 = tr(epoch2, attempt=5, prev_receipt_sha256=c.receipt_sha256(prev), receipt_id="b5",
            result="BLOCKED")
    err = raises_kind("retry", store.append_receipt, b5, STORY, KEY)
    assert "epoch" in str(err) and "non-PASS" in str(err)
    pass5 = tr(epoch2, attempt=5, prev_receipt_sha256=c.receipt_sha256(prev), receipt_id="b5p")
    raises_kind("retry", store.append_receipt, pass5, STORY, KEY)  # the bound refuses any NEW receipt once full
    assert [r["attempt"] for r in store.receipts_for_task(TASK)] == [1, 2, 3, 4]


def test_per_epoch_bound_is_per_slot(env):
    store, clock, _, epoch = env  # retry_cap 1
    lease(store, epoch)
    a1 = tr(epoch, attempt=1, result="BLOCKED")
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), receipt_id="a2", result="BLOCKED")
    store.append_receipt(a1, STORY, KEY)
    store.append_receipt(a2, STORY, KEY)  # slot tests is full in this epoch (2 non-PASS)
    a3 = tr(epoch, attempt=3, prev_receipt_sha256=c.receipt_sha256(a2), receipt_id="a3", result="BLOCKED")
    raises_kind("retry", store.append_receipt, a3, STORY, KEY)
    for rtype in ("StaticAnalysis", "IndependentReview"):
        store.append_receipt(receipt(rtype, epoch=epoch), STORY, KEY)  # other slots are untouched


def test_failed_attempts_adds_expired_and_released_leases_that_wrote_nothing(env):
    store, clock, path, epoch = env  # retry_cap 1
    lose(store, clock, epoch, (1,))
    assert store.failed_attempts(TASK) == 1
    lease(store, epoch, attempt=2)
    store.release_lease(TASK, WORKER, epoch)
    assert store.failed_attempts(TASK) == 2
    assert [r["status"] for r in leases(path)] == ["EXPIRED", "RELEASED"]
    raises_kind("retry", lease, store, epoch, attempt=3)


def test_failed_attempts_is_the_max_over_slots_for_mixed_non_pass_results(env):
    store, _, _, epoch = env  # retry_cap 1
    lease(store, epoch)
    store.append_receipt(slot_run(epoch, 1, result="BLOCKED"), STORY, KEY)  # tests: 1
    store.append_receipt(slot_run(epoch, 1, rtype="StaticAnalysis", result="NOT_RUN"), STORY, KEY)  # static: 1
    assert store.failed_attempts(TASK) == 1
    store.append_receipt(
        slot_run(epoch, 2, c.receipt_sha256(slot_run(epoch, 1, result="BLOCKED")), result="NOT_RUN"),
        STORY, KEY,
    )  # tests: 2
    assert store.failed_attempts(TASK) == 2


def test_supervisor_markers_themselves_are_not_failed_attempts(env):
    store, clock, _, epoch = env
    lose(store, clock, epoch, (1,))  # one WORKER_LOST marker (an INCONCLUSIVE receipt in the supervisor slot)
    assert len(supervisor_receipts(store)) == 1
    assert store.failed_attempts(TASK) == 1  # the lease counts once; the marker receipt is not added


def test_acquire_epoch_reaps_an_expired_lease_to_expired_and_marks_worker_lost(env):
    store, clock, path, epoch = env
    reg(store, "T2")
    lease(store, epoch, ttl=10)  # will be expired by the takeover
    lease(store, epoch, task="T2", worker="w2", ttl=5000)  # still live at takeover
    clock.advance(OWNER_TTL)
    epoch2 = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    statuses = {r["task_id"]: r["status"] for r in leases(path)}
    assert statuses == {TASK: "EXPIRED", "T2": "FENCED"}
    assert kinds(path).count("LEASE_EXPIRED") == 1 and kinds(path).count("LEASE_FENCED") == 1
    assert event_payloads(path, "LEASE_FENCED", "T2") == [{"attempt": 1, "new_epoch": epoch2}]
    assert event_payloads(path, "LEASE_FENCED", TASK) == []
    assert slot_map(path) == {1: None, 2: None}
    assert store.failed_attempts(TASK) == 1  # an EXPIRED lease that wrote nothing is the worker's failure
    assert store.failed_attempts("T2") == 0  # a FENCED one is not
    out = store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    assert sorted(x["task_id"] for x in out) == [TASK, "T2"]  # both are lost attempts that wrote nothing
    assert [x["check_description"] for x in supervisor_receipts(store)] == ["WORKER_LOST"]
    assert store.verify_event_chain()


def test_acquire_epoch_reaps_before_fencing_so_a_takeover_loop_cannot_hide_failures(env):
    store, clock, path, epoch = env  # retry_cap 1 -> two EXPIRED attempts exhaust the cap
    for n in (1, 2):
        lease(store, epoch, attempt=n, ttl=10)
        clock.advance(OWNER_TTL)  # lease AND owner expired
        epoch = store.acquire_epoch(STORY, f"owner-{n}", OWNER_TTL)
        assert leases(path)[-1]["status"] == "EXPIRED"
        store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    assert store.failed_attempts(TASK) == 2
    raises_kind("retry", lease, store, epoch, attempt=3)


def test_acquire_epoch_reaps_an_expired_lease_that_wrote_a_receipt_with_the_partial_event(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_receipt(tr(epoch), STORY, KEY)
    clock.advance(OWNER_TTL)
    store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert leases(path)[0]["status"] == "EXPIRED"
    assert kinds(path).count("LEASE_EXPIRED_PARTIAL") == 1 and "LEASE_FENCED" not in kinds(path)
    assert store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup") == []  # it wrote: no marker


def test_heartbeat_is_refused_after_the_retry_exhausted_marker(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_supervisor_receipt(
        supervisor_receipt("RETRY_EXHAUSTED", epoch=epoch), STORY, supervisor_key=SUPERVISOR_KEY
    )
    before = leases(path)[0]["expires_at"]
    err = raises_kind("terminal", store.heartbeat, TASK, WORKER, epoch, 500)
    assert "RETRY_EXHAUSTED" in str(err)
    assert leases(path)[0]["expires_at"] == before  # not extended
    assert rows(path, "SELECT expires_at FROM slots WHERE lease_id IS NOT NULL")[0][0] == before
    assert_no_dangling_transaction(path)


def test_heartbeat_is_refused_after_the_budget_exceeded_marker(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.set_budget(TASK, 5)
    raises_kind("budget", store.charge, TASK, 6, supervisor_key=SUPERVISOR_KEY)  # commits the marker
    before = leases(path)[0]["expires_at"]
    err = raises_kind("budget", store.heartbeat, TASK, WORKER, epoch, 500)
    assert "BUDGET_EXCEEDED" in str(err)
    assert leases(path)[0]["expires_at"] == before


def test_heartbeat_is_refused_above_the_cap_but_not_at_the_cap(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.set_budget(TASK, 5)
    store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY)  # spent == cap: finishing work is allowed
    store.heartbeat(TASK, WORKER, epoch, 500)
    assert leases(path)[0]["expires_at"] == 1500.0
    conn = raw(path)
    conn.execute("UPDATE budget SET spent = cap + 1 WHERE task_id = ?", (TASK,))
    conn.commit()
    conn.close()
    raises_kind("budget", store.heartbeat, TASK, WORKER, epoch, 900)
    assert leases(path)[0]["expires_at"] == 1500.0


def test_heartbeat_still_extends_a_lease_with_budget_left_and_no_marker(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    store.append_supervisor_receipt(
        supervisor_receipt("WORKER_LOST", epoch=epoch), STORY, supervisor_key=SUPERVISOR_KEY
    )  # WORKER_LOST is not terminal
    store.heartbeat(TASK, WORKER, epoch, 500)
    assert leases(path)[0]["expires_at"] == 1500.0


def test_append_receipt_rejects_a_worker_key_equal_to_the_event_key(env):
    store, _, path, epoch = env
    lease(store, epoch)
    signed_with_event_key = receipt("TestRun", EVENT_KEY, epoch=epoch)  # would verify under EVENT_KEY
    n_events = len(kinds(path))
    for bad in (EVENT_KEY, bytearray(EVENT_KEY)):
        err = raises_kind("key", store.append_receipt, signed_with_event_key, STORY, bad)
        assert "event_key" in str(err)
        raises_kind("key", store.append_receipt, tr(epoch), STORY, bad)
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert len(kinds(path)) == n_events and leases(path)[0]["wrote"] == 0
    assert_no_dangling_transaction(path)
    # equality only: a key that differs in one byte is a different key (and fails the signature)
    almost = EVENT_KEY[:-1] + b"?"
    raises_kind("signature", store.append_receipt, tr(epoch), STORY, almost)
    store.append_receipt(tr(epoch), STORY, KEY)  # the real worker key still works


DROP_RECEIPT_TRIGGERS = ["DROP TRIGGER receipts_no_update", "DROP TRIGGER receipts_no_delete"]


def _store_with_two_receipts(env):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch), STORY, KEY)
    store.append_receipt(receipt("StaticAnalysis", epoch=epoch), STORY, KEY)
    return store, path, epoch


def _insert_receipt_row(copy_path, body, receipt_id, attempt=1):
    conn = sqlite3.connect(copy_path)
    conn.execute(
        "INSERT INTO receipts (receipt_id, story_id, task_id, slot, attempt, epoch, receipt_sha256, "
        "prev_receipt_sha256, body) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
        (receipt_id, STORY, body["task_id"], body["slot"], attempt, body["epoch"],
         c.receipt_sha256(body), c.canonical_bytes(body).decode("utf-8")),
    )
    conn.commit()
    conn.close()


def test_receipts_for_task_of_an_untampered_store_matches_and_is_read_only(env):
    store, path, epoch = _store_with_two_receipts(env)
    before = _events_and_meta(path)
    got = store.receipts_for_task(TASK)
    assert [r["slot"] for r in got] == ["tests", "static"]
    assert store.receipts_for_task("T-with-no-receipts") == []
    assert _events_and_meta(path) == before
    assert_no_dangling_transaction(path)


@pytest.mark.parametrize("name", sorted(INTEGRITY))
def test_receipts_for_task_verifies_the_anchor(env, tmp_path, name):
    store, path, epoch = _store_with_two_receipts(env)
    copy_path = _tampered_copy(path, tmp_path, f"rt-{name}.db", DROP_TRIGGERS + INTEGRITY[name])
    before = _events_and_meta(copy_path)
    with open_store(copy_path) as t:
        raises_kind("integrity", t.receipts_for_task, TASK)
    assert _events_and_meta(copy_path) == before
    assert len(store.receipts_for_task(TASK)) == 2  # the original still reads


def test_receipts_for_task_detects_a_missing_receipt_row(env, tmp_path):
    store, path, epoch = _store_with_two_receipts(env)
    copy_path = _tampered_copy(
        path, tmp_path, "missing.db",
        DROP_RECEIPT_TRIGGERS + ["DELETE FROM receipts WHERE slot = 'static'"],
    )
    with open_store(copy_path) as t:
        err = raises_kind("integrity", t.receipts_for_task, TASK)
        assert "RECEIPT_APPENDED" in str(err)
        assert t.verify_event_chain() is True  # only the cross-check can see this
    assert len(store.receipts_for_task(TASK)) == 2


def test_receipts_for_task_detects_all_rows_deleted(env, tmp_path):
    store, path, epoch = _store_with_two_receipts(env)
    copy_path = _tampered_copy(path, tmp_path, "norows.db", DROP_RECEIPT_TRIGGERS + ["DELETE FROM receipts"])
    with open_store(copy_path) as t:
        raises_kind("integrity", t.receipts_for_task, TASK)


def test_receipts_for_task_detects_an_injected_receipt_row(env, tmp_path):
    store, path, epoch = _store_with_two_receipts(env)
    copy_path = _tampered_copy(path, tmp_path, "extra.db", DROP_RECEIPT_TRIGGERS)
    injected = receipt("IndependentReview", epoch=epoch)  # never appended through the store
    _insert_receipt_row(copy_path, injected, "injected-1")
    with open_store(copy_path) as t:
        assert len(rows(copy_path, "SELECT 1 FROM receipts")) == 3
        raises_kind("integrity", t.receipts_for_task, TASK)
        assert t.verify_event_chain() is True


def test_receipts_for_task_detects_a_duplicated_receipt_body(env, tmp_path):
    store, path, epoch = _store_with_two_receipts(env)
    copy_path = _tampered_copy(path, tmp_path, "dup.db", DROP_RECEIPT_TRIGGERS)
    body = store.receipts_for_task(TASK)[0]  # the same body again under a new id/attempt
    _insert_receipt_row(copy_path, body, "dup-1", attempt=7)
    with open_store(copy_path) as t:
        raises_kind("integrity", t.receipts_for_task, TASK)


@pytest.mark.parametrize(
    "payload",
    ["not json", "{}", "[]", "null", '{"sha256": null}', '{"sha256": 5}', '{"sha256": "%s"}' % ("9" * 64)],
)
def test_receipts_for_task_detects_a_malformed_or_wrong_receipt_event(env, tmp_path, payload):
    store, path, epoch = _store_with_two_receipts(env)
    copy_path = _tampered_copy(
        path, tmp_path, "payload.db",
        DROP_TRIGGERS + [
            "UPDATE events SET payload = '%s' WHERE kind = 'RECEIPT_APPENDED' AND seq = "
            "(SELECT MIN(seq) FROM events WHERE kind = 'RECEIPT_APPENDED')" % payload.replace("'", "''")
        ],
    )
    with open_store(copy_path) as t:
        raises_kind("integrity", t.receipts_for_task, TASK)


def test_tampering_with_one_task_does_not_break_another_task_reads(env, tmp_path):
    store, _, path, epoch = env
    m2 = reg(store, "T2")
    lease(store, epoch)
    lease(store, epoch, task="T2", worker="w2")
    store.append_receipt(tr(epoch), STORY, KEY)
    store.append_receipt(bound(m2, "TestRun", KEY, epoch=epoch, task_id="T2", runner_id="w2", receipt_id="t2-r1"),
        STORY, KEY,
    )
    copy_path = _tampered_copy(
        path, tmp_path, "t2.db", DROP_RECEIPT_TRIGGERS + ["DELETE FROM receipts WHERE task_id = 'T2'"]
    )
    with open_store(copy_path) as t:
        assert len(t.receipts_for_task(TASK)) == 1
        raises_kind("integrity", t.receipts_for_task, "T2")


# ============================================================================
# Review fixes 0031: (1) per-epoch slot bound counts NON-PASS receipts only,
# (2) budget blocks only at spent > cap / marker, (3) reserved 'sup-' prefix.
# ============================================================================

H1 = "1" * 40
H2 = "2" * 40
H3 = "3" * 40
H4 = "4" * 40
SLOT_TYPES = {"tests": "TestRun", "static": "StaticAnalysis", "review": "IndependentReview"}


class Chains:
    """Appends one receipt per call and keeps each slot's attempt/prev chain consistent.

    The per-slot attempt number is global (consecutive across heads and epochs);
    the store's per-epoch bound is the thing under test, not the chain.
    """

    def __init__(self, store, epoch, *, task=TASK, m=None):
        self.store, self.epoch, self.task, self.m = store, epoch, task, m
        self.last = {}

    def add(self, slot, head, result="PASS", epoch=None, **extra):
        prev = self.last.get(slot)
        attempt = 1 if prev is None else prev["attempt"] + 1
        kw = dict(
            epoch=self.epoch if epoch is None else epoch,
            attempt=attempt,
            candidate_head=head,
            prev_receipt_sha256=None if prev is None else c.receipt_sha256(prev),
            task_id=self.task,
            receipt_id=f"{self.task}-{slot}-{attempt}",
        )
        rtype = SLOT_TYPES[slot]
        if result == "FAIL":  # a TestRun that really derives FAIL
            kw["commands"] = [{"argv": ["pytest", "-q"], "exit_code": 1}]
            kw["result"] = "FAIL"
        elif result != "PASS":
            kw["result"] = result
        kw.update(extra)
        r = receipt(rtype, **kw) if self.m is None else bound(self.m, rtype, KEY, **kw)
        self.store.append_receipt(r, STORY, KEY)
        self.last[slot] = r
        return r

    def decide(self, head, epoch=None):
        m = self.m if self.m is not None else manifest()
        return gate.evaluate(
            m, self.store.receipts_for_task(self.task), head,
            self.epoch if epoch is None else epoch, KEY, supervisor_key=SUPERVISOR_KEY,
        )


def _receipt_count(path, task=TASK):
    return len(rows(path, "SELECT 1 FROM receipts WHERE task_id = ?", (task,)))


def test_three_heads_with_retry_cap_one_can_always_re_attest_every_slot(env):
    """Regression for MAJOR-1: retry_cap 1, three heads, every slot must accept a PASS at h3."""
    store, _, path, epoch = env  # default manifest: retry_cap 1 -> two NON-PASS per slot per epoch
    lease(store, epoch, ttl=5000)
    ch = Chains(store, epoch)
    # h1: tests FAIL, static PASS, review PASS
    ch.add("tests", H1, "FAIL")
    ch.add("static", H1)
    ch.add("review", H1)
    assert ch.decide(H1)["verdict"] != "APPROVE"  # the failing tests slot blocks the head
    # h2: tests PASS, static not PASS (BLOCKED), review PASS
    ch.add("tests", H2)
    ch.add("static", H2, "BLOCKED")
    ch.add("review", H2)
    assert ch.decide(H2)["verdict"] != "APPROVE"  # static is unmet at h2
    # h3: every slot already has 2 receipts in this epoch; only 1 non-PASS each -> all accepted
    ch.add("tests", H3)
    ch.add("static", H3)
    ch.add("review", H3)
    assert _receipt_count(path) == 9
    assert sorted((r["slot"], r["attempt"]) for r in store.receipts_for_task(TASK)) == sorted(
        (s, n) for s in SLOT_TYPES for n in (1, 2, 3)
    )
    assert store.failed_attempts(TASK) == 1  # max over slots: one non-PASS each, no exhaustion
    assert marker_rows(path) == []
    decision = ch.decide(H3)
    assert decision["verdict"] == "APPROVE", decision["reasons"]
    assert store.verify_event_chain()


def test_one_failure_then_all_pass_then_a_new_head_is_never_refused_by_the_bound(env):
    store, _, path, epoch = env  # retry_cap 1
    lease(store, epoch, ttl=5000)
    ch = Chains(store, epoch)
    ch.add("tests", H1, "FAIL")
    ch.add("static", H1)
    ch.add("review", H1)
    for slot in SLOT_TYPES:  # h2: the whole set passes (attempt 2 of every slot)
        ch.add(slot, H2)
    assert ch.decide(H2)["verdict"] == "APPROVE"
    for slot in SLOT_TYPES:  # h3: a new head, attempt 3 for every slot in the same epoch
        ch.add(slot, H3)
    assert ch.decide(H3)["verdict"] == "APPROVE"
    for slot in SLOT_TYPES:  # PASS-only history keeps accepting more attestations
        ch.add(slot, H4)
    assert _receipt_count(path) == 12
    assert ch.decide(H4)["verdict"] == "APPROVE"


def test_all_pass_slots_are_never_bounded_even_far_beyond_retry_cap_plus_one(env):
    store, _, path, epoch = env  # retry_cap 1 -> the old bound stopped a slot at 2 receipts
    lease(store, epoch, ttl=5000)
    ch = Chains(store, epoch)
    for n in range(6):
        ch.add("tests", f"{n + 1}" * 40)
    assert _receipt_count(path) == 6
    assert store.failed_attempts(TASK) == 0


def test_non_pass_receipts_still_bound_the_slot_at_retry_cap_plus_one(env):
    store, _, path, epoch = env  # retry_cap 1 -> two non-PASS fill the slot for this epoch
    lease(store, epoch, ttl=5000)
    ch = Chains(store, epoch)
    ch.add("tests", H1, "BLOCKED")
    ch.add("tests", H1, "FAIL")
    assert _receipt_count(path) == 2
    before = len(kinds(path))
    third = tr(epoch, attempt=3, prev_receipt_sha256=c.receipt_sha256(ch.last["tests"]),
               receipt_id="third", result="BLOCKED")
    err = raises_kind("retry", store.append_receipt, third, STORY, KEY)
    assert "non-PASS" in str(err) and "epoch" in str(err)
    third_pass = tr(epoch, attempt=3, prev_receipt_sha256=c.receipt_sha256(ch.last["tests"]),
                    receipt_id="third-pass")
    raises_kind("retry", store.append_receipt, third_pass, STORY, KEY)  # a full slot refuses any new receipt
    assert _receipt_count(path) == 2 and len(kinds(path)) == before  # nothing written
    ch.add("static", H1)  # other slots are unaffected (bound is per slot)
    ch.add("review", H1)
    assert store.failed_attempts(TASK) == 2
    assert_no_dangling_transaction(path)


def test_non_pass_pass_non_pass_fills_the_slot_and_the_pass_in_between_did_not_count(env):
    store, _, path, epoch = env  # retry_cap 1
    lease(store, epoch, ttl=5000)
    ch = Chains(store, epoch)
    ch.add("tests", H1, "BLOCKED")  # non-PASS #1
    ch.add("tests", H2)  # PASS: does not count, so non-PASS #2 below is still allowed
    ch.add("tests", H3, "FAIL")  # non-PASS #2 -> slot now full
    nxt = tr(epoch, attempt=4, prev_receipt_sha256=c.receipt_sha256(ch.last["tests"]),
             receipt_id="n4", candidate_head=H4)
    raises_kind("retry", store.append_receipt, nxt, STORY, KEY)
    assert [r["result"] for r in store.receipts_for_task(TASK)] == ["BLOCKED", "PASS", "FAIL"]


def test_retry_cap_zero_allows_unlimited_pass_but_exactly_one_non_pass_per_epoch(env):
    store, _, path, epoch = env
    m = reg(store, "T0", retry_cap=0)
    lease(store, epoch, task="T0", ttl=5000)
    ch = Chains(store, epoch, task="T0", m=m)
    for head in (H1, H2, H3):  # retry_cap 0 used to allow a single receipt per slot per epoch
        ch.add("tests", head)
    ch.add("tests", H3, "BLOCKED")  # the single permitted non-PASS
    again = bound(m, "TestRun", KEY, epoch=epoch, task_id="T0", attempt=5, receipt_id="z5",
                  prev_receipt_sha256=c.receipt_sha256(ch.last["tests"]), result="BLOCKED")
    raises_kind("retry", store.append_receipt, again, STORY, KEY)
    assert _receipt_count(path, "T0") == 4


def test_exact_cap_spend_full_pass_set_repeated_leases_and_takeover_never_create_a_marker(env):
    store, clock, path, epoch = env
    store.set_budget(TASK, 5)
    lease(store, epoch, ttl=5000)
    assert store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY) == 0  # spent == cap
    ch = Chains(store, epoch)
    for slot in SLOT_TYPES:
        ch.add(slot, HEAD)
    assert ch.decide(HEAD)["verdict"] == "APPROVE"

    def no_marker():
        assert marker_rows(path) == []
        assert kinds(path).count("BUDGET_EXCEEDED") == 0 and kinds(path).count("BUDGET_BLOCKED") == 0
        assert _budget_row(path) == (5, 5)

    no_marker()
    for attempt in (1, 2, 3):  # repeated acquire while the lease is live: refused, but never 'budget'
        with pytest.raises(StoreError) as exc:
            lease(store, epoch, attempt=attempt)
        assert exc.value.kind != "budget"
    no_marker()
    assert ch.decide(HEAD)["verdict"] == "APPROVE"  # lease attempts did not invalidate the PASS set
    store.release_lease(TASK, WORKER, epoch)
    lease(store, epoch, attempt=2)  # a lease at spent == cap is allowed
    no_marker()
    assert ch.decide(HEAD)["verdict"] == "APPROVE"
    store.release_lease(TASK, WORKER, epoch)
    clock.advance(OWNER_TTL)
    epoch2 = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)  # takeover (begin(2))
    assert epoch2 == epoch + 1
    lease(store, epoch2, attempt=3)
    no_marker()
    ch2 = Chains(store, epoch2)
    ch2.last = dict(ch.last)
    for slot in SLOT_TYPES:  # the new epoch re-attests the same head; the chain continues
        ch2.add(slot, HEAD)
    no_marker()
    decision = ch2.decide(HEAD)
    assert decision["verdict"] == "APPROVE", decision["reasons"]
    assert store.verify_event_chain()


def test_overspend_after_an_exact_cap_spend_still_commits_the_marker_and_refuses(env):
    store, _, path, epoch = env
    store.set_budget(TASK, 5)
    lease(store, epoch, ttl=5000)
    ch = Chains(store, epoch)
    for slot in SLOT_TYPES:
        ch.add(slot, HEAD)
    assert store.charge(TASK, 5, supervisor_key=SUPERVISOR_KEY) == 0
    assert marker_rows(path) == []
    raises_kind("budget", store.charge, TASK, 1, supervisor_key=SUPERVISOR_KEY)  # 6 > cap 5
    (m,) = marker_rows(path)
    assert (m["check_description"], m["result"]) == ("BUDGET_EXCEEDED", "BLOCKED")
    assert signing.verify(m, SUPERVISOR_KEY)
    assert _budget_row(path) == (5, 5)  # the refused amount was not charged
    assert kinds(path).count("BUDGET_EXCEEDED") == 1
    late = tr(epoch, attempt=2, receipt_id="late", prev_receipt_sha256=c.receipt_sha256(ch.last["tests"]))
    raises_kind("terminal", store.append_receipt, late, STORY, KEY)
    store.release_lease(TASK, WORKER, epoch)
    raises_kind("budget", lease, store, epoch, attempt=2)
    d = ch.decide(HEAD)
    assert d["verdict"] == "MODIFY" and any("BUDGET_EXCEEDED" in x for x in d["reasons"])


def test_zero_cap_task_with_nothing_spent_runs_to_approval_and_any_charge_marks(env):
    store, _, path, epoch = env
    m = reg(store, "TZ", cost_cap=0)
    lease(store, epoch, task="TZ", ttl=5000)
    ch = Chains(store, epoch, task="TZ", m=m)
    for slot in SLOT_TYPES:
        ch.add(slot, HEAD)
    store.release_lease("TZ", WORKER, epoch)
    lease(store, epoch, task="TZ", attempt=2)  # repeated lease at spent 0 == cap 0: no marker
    assert marker_rows(path, "TZ") == []
    d = ch.decide(HEAD)
    assert d["verdict"] == "APPROVE", d["reasons"]
    raises_kind("budget", store.charge, "TZ", 1, supervisor_key=SUPERVISOR_KEY)  # any spend overspends
    assert len(marker_rows(path, "TZ")) == 1
    assert _budget_row(path, "TZ") == (0, 0)


@pytest.mark.parametrize("rid", ["sup-T1-1", "sup-", "sup-anything", "sup-1"])
def test_worker_receipt_id_with_the_reserved_sup_prefix_is_rejected(env, rid):
    store, _, path, epoch = env
    lease(store, epoch)
    before_events = kinds(path)
    err = raises_kind("validation", store.append_receipt, tr(epoch, receipt_id=rid), STORY, KEY)
    assert "sup-" in str(err)
    assert rows(path, "SELECT 1 FROM receipts") == []  # nothing stored
    assert kinds(path) == before_events  # no event
    assert leases(path)[0]["wrote"] == 0  # the lease did not become a writer
    assert_no_dangling_transaction(path)
    store.append_receipt(tr(epoch, receipt_id="ok-1"), STORY, KEY)  # the same lease still works


@pytest.mark.parametrize("rid", ["sup", "sup_1", "xsup-1", "s-up-1", "sup1"])
def test_receipt_ids_that_merely_resemble_the_reserved_prefix_are_accepted(env, rid):
    store, _, path, epoch = env
    lease(store, epoch)
    store.append_receipt(tr(epoch, receipt_id=rid), STORY, KEY)
    assert [r["receipt_id"] for r in store.receipts_for_task(TASK)] == [rid]


def test_supervisor_marker_with_the_sup_prefix_succeeds_after_a_rejected_worker_attempt(env):
    store, clock, path, epoch = env
    lease(store, epoch, ttl=10)
    # a worker tries to pre-claim the id the supervisor will use for the first marker
    raises_kind("validation", store.append_receipt, tr(epoch, receipt_id=f"sup-{TASK}-1"), STORY, KEY)
    assert rows(path, "SELECT 1 FROM receipts") == []
    clock.advance(10)  # the worker is lost
    written = store.supervisor_reap_and_mark(SUPERVISOR_KEY, "sup")
    assert len(written) == 1
    assert written[0]["receipt_id"] == f"sup-{TASK}-1"
    assert written[0]["slot"] == SUPERVISOR_SLOT
    assert written[0]["check_description"] == "WORKER_LOST"
    assert signing.verify(written[0], SUPERVISOR_KEY)
    assert [r["receipt_id"] for r in supervisor_receipts(store)] == [f"sup-{TASK}-1"]
    # terminal markers use the same prefix and still succeed
    store.mark_budget_exceeded(TASK, SUPERVISOR_KEY, "sup")
    assert [r["receipt_id"] for r in supervisor_receipts(store)] == [f"sup-{TASK}-1", f"sup-{TASK}-2"]
    assert store.verify_event_chain()
