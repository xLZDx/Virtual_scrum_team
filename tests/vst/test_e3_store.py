"""E3 state store: epoch CAS, lease+slot, receipts, append-only, event chain, budget."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from tools.vst import contracts as c
from tools.vst import gate, signing
from tools.vst.store import GENESIS_HASH, Store, StoreError

from .e1e4_helpers import (
    HEAD2,
    KEY,
    STORY,
    FakeClock,
    doc_manifest,
    manifest,
    receipt,
)

OWNER_TTL = 100.0


@pytest.fixture
def env(tmp_path):
    clock = FakeClock()
    path = str(tmp_path / "state.db")
    store = Store(path, clock)
    store.init_slots(2)
    store.open_story(STORY, "proj", 4)
    epoch = store.acquire_epoch(STORY, "owner-a", OWNER_TTL)
    yield store, clock, path, epoch
    store.close()


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
    return receipt("TestRun", epoch=epoch, **kw)


# ------------------------------------------------------------------ stories


def test_open_story_starts_at_epoch_one_without_owner(tmp_path):
    with Store(str(tmp_path / "s.db"), FakeClock()) as s:
        assert s.open_story("a", "p", 1) == 1
        assert s.current_epoch("a") == 1
        row = rows(str(tmp_path / "s.db"), "SELECT owner, state FROM stories")[0]
        assert row["owner"] is None and row["state"] == "OPEN"


def test_open_story_duplicate_and_unknown_story_errors(env):
    store, _, _, _ = env
    with pytest.raises(StoreError) as e:
        store.open_story(STORY, "proj", 4)
    assert e.value.kind == "story"
    with pytest.raises(StoreError) as e:
        store.current_epoch("nope")
    assert e.value.kind == "story"


@pytest.mark.parametrize("args", [("", "p", 1), ("a", "", 1), ("a", "p", 0), ("a", "p", True)])
def test_open_story_bad_arguments(tmp_path, args):
    with Store(str(tmp_path / "s.db"), FakeClock()) as s:
        with pytest.raises(StoreError) as e:
            s.open_story(*args)
        assert e.value.kind == "argument"


# -------------------------------------------------------------- epoch (CAS)


def test_acquire_epoch_bumps_and_returns_new_epoch(env):
    store, _, path, epoch = env
    assert epoch == 2
    assert store.current_epoch(STORY) == 2
    row = rows(path, "SELECT owner, state FROM stories")[0]
    assert row["owner"] == "owner-a" and row["state"] == "OWNED"


def test_second_acquire_while_owner_live_fails_and_keeps_epoch(env):
    store, clock, _, _ = env
    clock.advance(OWNER_TTL - 1)
    with pytest.raises(StoreError) as e:
        store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert e.value.kind == "epoch"
    assert store.current_epoch(STORY) == 2


def test_same_owner_cannot_reacquire_while_live(env):
    store, _, _, _ = env
    with pytest.raises(StoreError) as e:
        store.acquire_epoch(STORY, "owner-a", OWNER_TTL)
    assert e.value.kind == "epoch"


def test_acquire_after_ttl_succeeds_and_old_epoch_is_fenced(env):
    store, clock, path, old = env
    store.acquire_lease("T1", STORY, "w1", old, 1, 10_000)
    clock.advance(OWNER_TTL)  # boundary: expires_at <= now is dead owner
    new = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert new == old + 1
    # Fenced: old lease dead, slot freed, old-epoch operations rejected.
    lease = rows(path, "SELECT released FROM leases WHERE task_id='T1'")[0]
    assert lease["released"] == 2
    assert all(r["task_id"] is None for r in rows(path, "SELECT task_id FROM slots"))
    with pytest.raises(StoreError) as e:
        store.heartbeat("T1", "w1", old, 10)
    assert e.value.kind in ("lease", "epoch")
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T2", STORY, "w2", old, 1, 10)
    assert e.value.kind == "epoch"
    with pytest.raises(StoreError) as e:
        store.append_receipt(tr(old), STORY)
    assert e.value.kind == "epoch"
    store.append_receipt(tr(new), STORY)  # new epoch is accepted
    assert "LEASE_FENCED" in kinds(path)


def test_acquire_epoch_one_instant_before_expiry_still_fails(env):
    store, clock, _, _ = env
    clock.advance(OWNER_TTL - 0.001)
    with pytest.raises(StoreError):
        store.acquire_epoch(STORY, "owner-b", OWNER_TTL)


def test_two_store_instances_on_one_file_only_one_wins(tmp_path):
    path = str(tmp_path / "shared.db")
    clock = FakeClock()
    a, b = Store(path, clock), Store(path, clock)
    try:
        a.open_story(STORY, "p", 1)
        assert a.acquire_epoch(STORY, "A", 50) == 2
        with pytest.raises(StoreError) as e:
            b.acquire_epoch(STORY, "B", 50)
        assert e.value.kind == "epoch"
        assert b.current_epoch(STORY) == 2
    finally:
        a.close()
        b.close()


def test_concurrent_acquire_exactly_one_holds_the_epoch(tmp_path):
    path = str(tmp_path / "race.db")
    clock = FakeClock()
    with Store(path, clock) as s:
        s.open_story(STORY, "p", 1)
    barrier = threading.Barrier(4)
    results = []
    lock = threading.Lock()

    def worker(name):
        st = Store(path, clock)
        try:
            barrier.wait()
            try:
                out = ("ok", st.acquire_epoch(STORY, name, 500))
            except StoreError as exc:
                out = ("fail", exc.kind)
        finally:
            st.close()
        with lock:
            results.append(out)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert sorted(r[0] for r in results) == ["fail", "fail", "fail", "ok"]
    assert [r for r in results if r[0] == "fail"] == [("fail", "epoch")] * 3
    with Store(path, clock) as s:
        assert s.current_epoch(STORY) == 2


def test_acquire_epoch_bad_arguments(env):
    store, _, _, _ = env
    for ttl in (0, -1, True, "5"):
        with pytest.raises(StoreError) as e:
            store.acquire_epoch(STORY, "x", ttl)
        assert e.value.kind == "argument"
    with pytest.raises(StoreError) as e:
        store.acquire_epoch("missing", "x", 5)
    assert e.value.kind == "story"


def test_renew_epoch_extends_liveness_without_changing_epoch(env):
    store, clock, path, epoch = env
    clock.advance(60)
    store.renew_epoch(STORY, "owner-a", OWNER_TTL)
    assert store.current_epoch(STORY) == epoch
    clock.advance(70)  # past the original expiry (100), before the renewed one (160)
    with pytest.raises(StoreError):
        store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    clock.advance(40)  # now past 160
    assert store.acquire_epoch(STORY, "owner-b", OWNER_TTL) == epoch + 1
    assert "EPOCH_RENEWED" in kinds(path)


def test_renew_epoch_rejects_non_owner_and_expired_owner(env):
    store, clock, _, _ = env
    with pytest.raises(StoreError) as e:
        store.renew_epoch(STORY, "owner-b", OWNER_TTL)
    assert e.value.kind == "epoch"
    clock.advance(OWNER_TTL)
    with pytest.raises(StoreError) as e:
        store.renew_epoch(STORY, "owner-a", OWNER_TTL)
    assert e.value.kind == "epoch"


def test_release_epoch_owner_only_then_next_acquire_succeeds(env):
    store, _, path, epoch = env
    with pytest.raises(StoreError) as e:
        store.release_epoch(STORY, "owner-b")
    assert e.value.kind == "epoch"
    store.release_epoch(STORY, "owner-a")
    assert store.current_epoch(STORY) == epoch  # number kept
    row = rows(path, "SELECT owner, state, owner_expires_at FROM stories")[0]
    assert row["owner"] is None and row["state"] == "OPEN" and row["owner_expires_at"] is None
    assert store.acquire_epoch(STORY, "owner-b", OWNER_TTL) == epoch + 1


def test_release_epoch_without_owner_fails(tmp_path):
    with Store(str(tmp_path / "s.db"), FakeClock()) as s:
        s.open_story("a", "p", 1)
        with pytest.raises(StoreError) as e:
            s.release_epoch("a", "anyone")
        assert e.value.kind == "epoch"


# ------------------------------------------------------------ lease and slot


def test_acquire_lease_takes_lease_and_lowest_free_slot(env):
    store, _, path, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 30)
    store.acquire_lease("T2", STORY, "w2", epoch, 1, 30)
    slots = {r["slot_no"]: r["task_id"] for r in rows(path, "SELECT slot_no, task_id FROM slots")}
    assert slots == {1: "T1", 2: "T2"}
    lease = rows(path, "SELECT * FROM leases WHERE task_id='T1'")[0]
    assert (lease["worker_id"], lease["epoch"], lease["attempt"], lease["released"]) == ("w1", epoch, 1, 0)


def test_no_free_slot_rejected_and_leaves_no_lease_row(env):
    store, _, path, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 30)
    store.acquire_lease("T2", STORY, "w2", epoch, 1, 30)
    events_before = len(kinds(path))
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T3", STORY, "w3", epoch, 1, 30)
    assert e.value.kind == "slot"
    assert rows(path, "SELECT 1 FROM leases WHERE task_id='T3'") == []
    assert len(kinds(path)) == events_before  # nothing half-written


def test_stale_epoch_lease_rejected_and_takes_no_slot(env):
    store, _, path, epoch = env
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T1", STORY, "w1", epoch - 1, 1, 30)
    assert e.value.kind == "epoch"
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T1", STORY, "w1", epoch + 1, 1, 30)
    assert e.value.kind == "epoch"
    assert all(r["task_id"] is None for r in rows(path, "SELECT task_id FROM slots"))
    assert rows(path, "SELECT 1 FROM leases") == []


def test_live_lease_blocks_second_acquire_for_same_task(env):
    store, _, path, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 30)
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T1", STORY, "w2", epoch, 2, 30)
    assert e.value.kind == "lease"
    assert len([r for r in rows(path, "SELECT task_id FROM slots") if r["task_id"] == "T1"]) == 1


def test_acquire_lease_unknown_story_and_bad_args(env):
    store, _, _, epoch = env
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T1", "missing", "w", epoch, 1, 30)
    assert e.value.kind == "story"
    for kwargs in (
        {"task_id": ""}, {"worker_id": " "}, {"epoch": 0}, {"epoch": True},
        {"attempt": 0}, {"ttl": 0}, {"ttl": -5},
    ):
        a = {"task_id": "T1", "worker_id": "w", "epoch": epoch, "attempt": 1, "ttl": 30}
        a.update(kwargs)
        with pytest.raises(StoreError) as e:
            store.acquire_lease(a["task_id"], STORY, a["worker_id"], a["epoch"], a["attempt"], a["ttl"])
        assert e.value.kind == "argument"


def test_expired_lease_is_reaped_on_next_acquire_and_slot_reused(env):
    store, clock, path, epoch = env
    store.init_slots(1)  # idempotent: still 2 slots
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    store.acquire_lease("T2", STORY, "w2", epoch, 1, 10_000)
    clock.advance(10)
    store.acquire_lease("T3", STORY, "w3", epoch, 1, 30)  # reaps T1 first, then takes its slot
    assert rows(path, "SELECT released FROM leases WHERE task_id='T1'")[0]["released"] == 2
    assert {r["slot_no"]: r["task_id"] for r in rows(path, "SELECT * FROM slots")}[1] == "T3"
    assert "LEASE_EXPIRED" in kinds(path)


def test_attempt_must_increase_after_release(env):
    store, _, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 2, 30)
    store.release_lease("T1", "w1", epoch)
    for attempt in (1, 2):
        with pytest.raises(StoreError) as e:
            store.acquire_lease("T1", STORY, "w1", epoch, attempt, 30)
        assert e.value.kind == "lease"
    store.acquire_lease("T1", STORY, "w1", epoch, 3, 30)


def test_lost_attempt_must_be_marked_before_retry(env):
    store, clock, path, epoch = env
    m = manifest()
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    clock.advance(10)
    store.reap_expired()
    with pytest.raises(StoreError) as e:
        store.acquire_lease("T1", STORY, "w2", epoch, 2, 30)
    assert e.value.kind == "lease" and "marked" in str(e.value)
    written = store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")
    assert len(written) == 1
    store.acquire_lease("T1", STORY, "w2", epoch, 2, 30)  # now allowed


def test_lost_attempt_with_receipt_needs_no_marker(env):
    store, clock, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    store.append_receipt(tr(epoch), STORY)
    clock.advance(10)
    store.reap_expired()
    store.acquire_lease("T1", STORY, "w2", epoch, 2, 30)


# --------------------------------------------------- heartbeat / release / reap


def test_heartbeat_extends_lease_beyond_original_expiry(env):
    store, clock, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    clock.advance(9)
    store.heartbeat("T1", "w1", epoch, 10)  # now expires at +19
    clock.advance(5)  # past the original expiry
    assert store.reap_expired() == []
    store.release_lease("T1", "w1", epoch)  # still live: succeeds


def test_heartbeat_rejections(env):
    store, clock, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    with pytest.raises(StoreError) as e:
        store.heartbeat("T1", "intruder", epoch, 10)
    assert e.value.kind == "lease"
    with pytest.raises(StoreError) as e:
        store.heartbeat("T1", "w1", epoch + 1, 10)
    assert e.value.kind == "epoch"
    with pytest.raises(StoreError) as e:
        store.heartbeat("unknown", "w1", epoch, 10)
    assert e.value.kind == "lease"
    clock.advance(10)
    with pytest.raises(StoreError) as e:
        store.heartbeat("T1", "w1", epoch, 10)
    assert e.value.kind == "lease"
    assert store.reap_expired() == ["T1"]  # the failed heartbeat did not resurrect it


def test_release_lease_frees_slot_and_second_release_fails(env):
    store, _, path, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 30)
    with pytest.raises(StoreError):
        store.release_lease("T1", "intruder", epoch)
    store.release_lease("T1", "w1", epoch)
    assert rows(path, "SELECT released FROM leases")[0]["released"] == 1
    assert all(r["task_id"] is None for r in rows(path, "SELECT task_id FROM slots"))
    with pytest.raises(StoreError) as e:
        store.release_lease("T1", "w1", epoch)
    assert e.value.kind == "lease"
    assert "LEASE_RELEASED" in kinds(path)


def test_reap_expired_returns_only_expired_and_is_idempotent(env):
    store, clock, path, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    store.acquire_lease("T2", STORY, "w2", epoch, 1, 50)
    assert store.reap_expired() == []
    clock.advance(10)
    assert store.reap_expired() == ["T1"]
    assert store.reap_expired() == []
    assert {r["task_id"]: r["released"] for r in rows(path, "SELECT task_id, released FROM leases")} == {
        "T1": 2, "T2": 0,
    }
    assert [r["task_id"] for r in rows(path, "SELECT task_id FROM slots ORDER BY slot_no")] == [None, "T2"]


# ----------------------------------------------------------------- receipts


def test_append_receipt_roundtrip_preserves_body(env):
    store, _, path, epoch = env
    r = tr(epoch)
    store.append_receipt(r, STORY)
    assert store.receipts_for_task("T1") == [r]
    row = rows(path, "SELECT receipt_sha256, story_id, slot, attempt FROM receipts")[0]
    assert row["receipt_sha256"] == c.receipt_sha256(r)
    assert (row["story_id"], row["slot"], row["attempt"]) == (STORY, "tests", 1)
    assert "RECEIPT_APPENDED" in kinds(path)


def test_append_receipt_chain_of_three_and_independent_slots(env):
    store, _, _, epoch = env
    a1 = tr(epoch, attempt=1, result="BLOCKED")
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), result="NOT_RUN")
    a3 = tr(epoch, attempt=3, prev_receipt_sha256=c.receipt_sha256(a2))
    for r in (a1, a2, a3):
        store.append_receipt(r, STORY)
    store.append_receipt(receipt("StaticAnalysis", epoch=epoch), STORY)  # other slot starts at 1
    assert [r["attempt"] for r in store.receipts_for_task("T1")] == [1, 2, 3, 1]


def test_append_receipt_stale_or_future_epoch_rejected(env):
    store, _, path, epoch = env
    for bad in (epoch - 1, epoch + 1):
        with pytest.raises(StoreError) as e:
            store.append_receipt(tr(bad), STORY)
        assert e.value.kind == "epoch"
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_append_receipt_attempt_gap_rejected(env):
    store, _, _, epoch = env
    a1 = tr(epoch)
    store.append_receipt(a1, STORY)
    gap = tr(epoch, attempt=3, prev_receipt_sha256=c.receipt_sha256(a1))
    with pytest.raises(StoreError) as e:
        store.append_receipt(gap, STORY)
    assert e.value.kind == "chain"
    first_is_two = tr(epoch, slot="static", attempt=2, prev_receipt_sha256="e" * 64)
    with pytest.raises(StoreError) as e:
        store.append_receipt(first_is_two, STORY)
    assert e.value.kind == "chain"


def test_append_receipt_wrong_prev_hash_rejected(env):
    store, _, _, epoch = env
    store.append_receipt(tr(epoch), STORY)
    with pytest.raises(StoreError) as e:
        store.append_receipt(tr(epoch, attempt=2, prev_receipt_sha256="f" * 64), STORY)
    assert e.value.kind == "chain"
    assert len(store.receipts_for_task("T1")) == 1


def test_append_receipt_repeated_attempt_rejected(env):
    store, _, _, epoch = env
    r = tr(epoch)
    store.append_receipt(r, STORY)
    with pytest.raises(StoreError) as e:
        store.append_receipt(r, STORY)  # exact replay
    assert e.value.kind == "chain"
    with pytest.raises(StoreError) as e:
        store.append_receipt(tr(epoch, receipt_id="other-id"), STORY)  # same (task, slot, attempt)
    assert e.value.kind == "chain"
    assert len(store.receipts_for_task("T1")) == 1


def test_append_receipt_duplicate_receipt_id_rejected(env):
    store, _, _, epoch = env
    a1 = tr(epoch, receipt_id="same-id")
    store.append_receipt(a1, STORY)
    a2 = tr(epoch, attempt=2, prev_receipt_sha256=c.receipt_sha256(a1), receipt_id="same-id")
    with pytest.raises(StoreError) as e:
        store.append_receipt(a2, STORY)
    assert e.value.kind == "duplicate"
    assert len(store.receipts_for_task("T1")) == 1


def test_append_invalid_receipt_and_unknown_story(env):
    store, _, path, epoch = env
    bad = tr(epoch)
    bad["unexpected"] = 1
    with pytest.raises(c.ContractError):
        store.append_receipt(bad, STORY)
    with pytest.raises(c.ContractError):
        store.append_receipt("not a receipt", STORY)
    with pytest.raises(StoreError) as e:
        store.append_receipt(tr(epoch), "missing-story")
    assert e.value.kind == "story"
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_failed_append_leaves_no_event(env):
    store, _, path, epoch = env
    before = len(kinds(path))
    with pytest.raises(StoreError):
        store.append_receipt(tr(epoch + 1), STORY)
    assert len(kinds(path)) == before


def test_receipts_survive_reopen(env):
    store, clock, path, epoch = env
    r = tr(epoch)
    store.append_receipt(r, STORY)
    with Store(path, clock) as again:
        assert again.receipts_for_task("T1") == [r]
        assert again.verify_event_chain()


# ----------------------------------------------------------- append-only


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE receipts SET slot = 'x'",
        "UPDATE receipts SET body = '{}'",
        "DELETE FROM receipts",
        "UPDATE events SET payload = 'x'",
        "UPDATE events SET hash = 'x'",
        "DELETE FROM events",
    ],
)
def test_raw_update_delete_of_receipts_and_events_fail(env, sql):
    store, _, path, epoch = env
    store.append_receipt(tr(epoch), STORY)
    n_receipts = len(rows(path, "SELECT 1 FROM receipts"))
    n_events = len(rows(path, "SELECT 1 FROM events"))
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(sql)
            conn.commit()
    finally:
        conn.close()
    assert len(rows(path, "SELECT 1 FROM receipts")) == n_receipts
    assert len(rows(path, "SELECT 1 FROM events")) == n_events
    assert store.verify_event_chain()


def test_append_only_violation_inside_store_transaction_maps_to_store_error(env):
    store, _, path, epoch = env
    store.append_receipt(tr(epoch), STORY)
    with pytest.raises(StoreError) as e:
        with store._tx() as conn:  # private seam: the only way to reach the trigger via Store code
            conn.execute("DELETE FROM receipts")
    assert e.value.kind == "append_only"
    assert len(store.receipts_for_task("T1")) == 1
    store.record_event("T1", "x", "STILL_WORKS", {})  # transaction was rolled back, store usable


# ------------------------------------------------------------- event chain


def test_empty_event_chain_verifies(tmp_path):
    with Store(str(tmp_path / "e.db"), FakeClock()) as s:
        assert s.verify_event_chain() is True


def test_event_chain_links_to_genesis_and_grows(env):
    store, _, path, _ = env
    store.record_event("T1", "actor", "CUSTOM", {"k": [1, 2]})
    evs = rows(path, "SELECT seq, prev_hash, hash FROM events ORDER BY seq")
    assert evs[0]["prev_hash"] == GENESIS_HASH
    for prev, cur in zip(evs, evs[1:]):
        assert cur["prev_hash"] == prev["hash"]
    assert len({e["hash"] for e in evs}) == len(evs)
    assert store.verify_event_chain()


def test_record_event_argument_validation(env):
    store, _, _, _ = env
    for args in (("", "a", "k"), ("t", "", "k"), ("t", "a", " ")):
        with pytest.raises(StoreError) as e:
            store.record_event(*args, {})
        assert e.value.kind == "argument"


def _tampered_copy(path, tmp_path, name, statements):
    """Copy the db with sqlite's backup API, drop the trigger on the COPY, apply SQL."""
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


TAMPERS = {
    "payload_of_first": ["UPDATE events SET payload = '{}' WHERE seq = (SELECT MIN(seq) FROM events)"],
    "payload_of_last": ["UPDATE events SET payload = '{}' WHERE seq = (SELECT MAX(seq) FROM events)"],
    "ts": ["UPDATE events SET ts = ts + 1 WHERE seq = 2"],
    "actor": ["UPDATE events SET actor = 'evil' WHERE seq = 2"],
    "kind": ["UPDATE events SET kind = 'EVIL' WHERE seq = 2"],
    "hash_only": ["UPDATE events SET hash = '%s' WHERE seq = 2" % ("9" * 64)],
    "prev_hash_only": ["UPDATE events SET prev_hash = '%s' WHERE seq = 3" % ("9" * 64)],
    "delete_middle": ["DELETE FROM events WHERE seq = 2"],
    "delete_first": ["DELETE FROM events WHERE seq = (SELECT MIN(seq) FROM events)"],
}


@pytest.mark.parametrize("name", sorted(TAMPERS))
def test_tampered_event_is_detected_on_a_copy(env, tmp_path, name):
    store, _, path, epoch = env
    store.append_receipt(tr(epoch), STORY)
    store.record_event("T1", "a", "EXTRA", {"n": 1})
    assert store.verify_event_chain() is True
    sql = ["DROP TRIGGER events_no_update", "DROP TRIGGER events_no_delete"] + TAMPERS[name]
    copy_path = _tampered_copy(path, tmp_path, f"copy-{name}.db", sql)
    with Store(copy_path, FakeClock()) as tampered:
        assert tampered.verify_event_chain() is False
    assert store.verify_event_chain() is True  # the original is untouched


# ------------------------------------------------------------------- budget


def test_charge_returns_remaining_and_allows_exact_cap(env):
    store, _, path, _ = env
    store.set_budget("T1", 10)
    assert store.charge("T1", 4) == 6
    assert store.charge("T1", 0) == 6
    assert store.charge("T1", 6) == 0
    assert rows(path, "SELECT spent FROM budget")[0]["spent"] == 10


def test_charge_over_cap_raises_charges_nothing_and_commits_event(env):
    store, _, path, _ = env
    store.set_budget("T1", 10)
    store.charge("T1", 8)
    with pytest.raises(StoreError) as e:
        store.charge("T1", 3)
    assert e.value.kind == "budget"
    assert rows(path, "SELECT spent FROM budget")[0]["spent"] == 8
    assert kinds(path).count("BUDGET_EXCEEDED") == 1
    assert store.verify_event_chain()
    assert store.charge("T1", 2) == 0  # still usable up to the cap


def test_charge_unknown_task_and_bad_amount(env):
    store, _, _, _ = env
    with pytest.raises(StoreError) as e:
        store.charge("nobody", 1)
    assert e.value.kind == "budget"
    store.set_budget("T1", 5)
    for amount in (-1, True, 1.5, "1"):
        with pytest.raises(StoreError) as e:
            store.charge("T1", amount)
        assert e.value.kind == "argument"


def test_zero_cap_rejects_any_positive_charge(env):
    store, _, _, _ = env
    store.set_budget("T1", 0)
    assert store.charge("T1", 0) == 0
    with pytest.raises(StoreError) as e:
        store.charge("T1", 1)
    assert e.value.kind == "budget"


def test_set_budget_preserves_spent_and_validates(env):
    store, _, path, _ = env
    store.set_budget("T1", 10)
    store.charge("T1", 7)
    store.set_budget("T1", 20)
    row = rows(path, "SELECT cap, spent FROM budget")[0]
    assert (row["cap"], row["spent"]) == (20, 7)
    for cap in (-1, True, 1.5):
        with pytest.raises(StoreError) as e:
            store.set_budget("T1", cap)
        assert e.value.kind == "argument"


# ---------------------------------------------------------------- supervisor


def _lose(store, clock, epoch, task="T1", attempt=1, ttl=10):
    store.acquire_lease(task, STORY, "w1", epoch, attempt, ttl)
    clock.advance(ttl)


def test_supervisor_writes_worker_lost_receipt_for_reaped_lease(env):
    store, clock, path, epoch = env
    m = doc_manifest()
    _lose(store, clock, epoch)
    out = store.supervisor_reap_and_mark(lambda t: m, KEY, "sup-1")
    assert len(out) == 1
    r = out[0]
    assert r["receipt_type"] == "Documentation" and r["slot"] == "doc"
    assert r["result"] == "INCONCLUSIVE" and r["check_description"] == "WORKER_LOST"
    assert r["attempt"] == 1 and r["prev_receipt_sha256"] is None
    assert r["epoch"] == epoch and r["candidate_head"] == m["base_head"]
    assert r["runner_id"] == "sup-1" and r["covered_acceptance"] == []
    assert signing.verify(r, KEY) and not signing.verify(r, b"other-key")
    assert c.derive_result(r) == r["result"]
    assert store.receipts_for_task("T1") == [r]
    assert rows(path, "SELECT released, marked FROM leases")[0]["marked"] == 1
    assert store.supervisor_reap_and_mark(lambda t: m, KEY, "sup-1") == []  # idempotent


def test_supervisor_receipt_is_a_non_approval_for_the_gate(env):
    store, clock, _, epoch = env
    m = doc_manifest(acceptance=["AC-1"])
    _lose(store, clock, epoch)
    store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")
    d = gate.evaluate(m, store.receipts_for_task("T1"), m["base_head"], epoch, KEY)
    assert d["verdict"] == "MODIFY"
    assert "slot 'doc' latest attempt 1 result INCONCLUSIVE" in d["reasons"]
    assert not any("invalid" in x for x in d["reasons"])  # the gate accepts the supervisor receipt itself


def test_supervisor_skips_lease_that_already_has_a_receipt_but_marks_it(env):
    store, clock, path, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    store.append_receipt(tr(epoch), STORY)
    clock.advance(10)
    assert store.supervisor_reap_and_mark(lambda t: doc_manifest(), KEY, "sup") == []
    assert rows(path, "SELECT marked FROM leases")[0]["marked"] == 1
    assert len(store.receipts_for_task("T1")) == 1


def test_supervisor_ignores_live_and_released_leases(env):
    store, clock, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 1000)
    store.acquire_lease("T2", STORY, "w2", epoch, 1, 1000)
    store.release_lease("T2", "w2", epoch)
    clock.advance(10)
    assert store.supervisor_reap_and_mark(lambda t: doc_manifest(), KEY, "sup") == []


def test_supervisor_uses_first_slot_when_manifest_has_no_documentation_slot(env):
    store, clock, _, epoch = env
    m = manifest()  # tests, static, review: no Documentation slot
    _lose(store, clock, epoch)
    r = store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")[0]
    assert r["slot"] == "tests" and r["receipt_type"] == "Documentation"


def test_supervisor_candidate_head_comes_from_latest_receipt_of_task(env):
    store, clock, _, epoch = env
    m = doc_manifest()
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    store.append_receipt(tr(epoch, candidate_head=HEAD2, result="FAIL", skipped_test_ids=["z"]), STORY)
    clock.advance(10)
    store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")  # attempt 1 has a receipt: no write
    store.acquire_lease("T1", STORY, "w1", epoch, 2, 10)
    clock.advance(10)
    r = store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")[0]
    assert r["candidate_head"] == HEAD2 != m["base_head"]


def test_supervisor_retry_exhausted_boundary(env):
    store, clock, _, epoch = env
    m = doc_manifest(retry_cap=1)  # attempts 1 and 2 may be lost (WORKER_LOST); 3 exhausts
    results = []
    for attempt in (1, 2, 3):
        _lose(store, clock, epoch, attempt=attempt)
        out = store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")
        assert len(out) == 1
        results.append((out[0]["result"], out[0]["check_description"], out[0]["attempt"]))
    assert results == [
        ("INCONCLUSIVE", "WORKER_LOST", 1),
        ("INCONCLUSIVE", "WORKER_LOST", 2),
        ("BLOCKED", "RETRY_EXHAUSTED", 3),
    ]
    chain = store.receipts_for_task("T1")
    assert chain[1]["prev_receipt_sha256"] == c.receipt_sha256(chain[0])  # gap-free chain
    assert chain[2]["prev_receipt_sha256"] == c.receipt_sha256(chain[1])


def test_supervisor_retry_cap_zero_exhausts_on_second_attempt(env):
    store, clock, _, epoch = env
    m = doc_manifest(retry_cap=0)
    _lose(store, clock, epoch, attempt=1)
    assert store.supervisor_reap_and_mark(lambda t: m, KEY, "s")[0]["result"] == "INCONCLUSIVE"
    _lose(store, clock, epoch, attempt=2)
    out = store.supervisor_reap_and_mark(lambda t: m, KEY, "s")[0]
    assert (out["result"], out["check_description"]) == ("BLOCKED", "RETRY_EXHAUSTED")


def test_supervisor_with_invalid_manifest_raises_and_rolls_back(env):
    store, clock, path, epoch = env
    _lose(store, clock, epoch)
    with pytest.raises(c.ContractError):
        store.supervisor_reap_and_mark(lambda t: {"bad": 1}, KEY, "sup")
    assert rows(path, "SELECT 1 FROM receipts") == []
    assert rows(path, "SELECT marked FROM leases")[0]["marked"] == 0  # retried later
    out = store.supervisor_reap_and_mark(lambda t: doc_manifest(), KEY, "sup")
    assert len(out) == 1


def test_supervisor_requires_runner_id_and_key(env):
    store, clock, _, epoch = env
    with pytest.raises(StoreError) as e:
        store.supervisor_reap_and_mark(lambda t: doc_manifest(), KEY, "")
    assert e.value.kind == "argument"
    _lose(store, clock, epoch)
    with pytest.raises(c.ContractError):
        store.supervisor_reap_and_mark(lambda t: doc_manifest(), b"", "sup")


def test_zombie_late_receipt_after_fencing_is_rejected(env):
    store, clock, path, epoch = env
    m = doc_manifest()
    _lose(store, clock, epoch, ttl=10)
    clock.advance(OWNER_TTL)
    new_epoch = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    store.supervisor_reap_and_mark(lambda t: m, KEY, "sup")
    with pytest.raises(StoreError) as e:
        store.append_receipt(tr(epoch), STORY)  # zombie holds the old epoch
    assert e.value.kind == "epoch"
    assert new_epoch == epoch + 1
    sup = store.receipts_for_task("T1")[0]
    assert sup["epoch"] == new_epoch  # supervisor receipt carries the CURRENT epoch


def test_mark_budget_exceeded_writes_signed_blocked_receipt_and_event(env):
    store, _, path, epoch = env
    m = doc_manifest()
    store.set_budget("T1", 1)
    with pytest.raises(StoreError):
        store.charge("T1", 5)
    r = store.mark_budget_exceeded("T1", STORY, m, KEY, "sup")
    assert r["result"] == "BLOCKED" and r["check_description"] == "BUDGET_EXCEEDED"
    assert r["slot"] == "doc" and r["attempt"] == 1 and r["epoch"] == epoch
    assert r["candidate_head"] == m["base_head"]
    assert signing.verify(r, KEY) and c.derive_result(r) == "BLOCKED"
    assert store.receipts_for_task("T1") == [r]
    assert "BUDGET_BLOCKED" in kinds(path)
    assert store.verify_event_chain()
    second = store.mark_budget_exceeded("T1", STORY, m, KEY, "sup")
    assert second["attempt"] == 2 and second["prev_receipt_sha256"] == c.receipt_sha256(r)


def test_mark_budget_exceeded_rejects_task_mismatch_and_bad_manifest(env):
    store, _, path, _ = env
    with pytest.raises(StoreError) as e:
        store.mark_budget_exceeded("OTHER", STORY, doc_manifest(), KEY, "sup")
    assert e.value.kind == "argument"
    with pytest.raises(c.ContractError):
        store.mark_budget_exceeded("T1", STORY, {"bad": 1}, KEY, "sup")
    with pytest.raises(StoreError) as e:
        store.mark_budget_exceeded("T1", "missing", doc_manifest(), KEY, "sup")
    assert e.value.kind == "story"
    assert rows(path, "SELECT 1 FROM receipts") == []


def test_mark_budget_exceeded_makes_gate_non_approving(env):
    store, _, _, epoch = env
    m = doc_manifest(acceptance=["AC-1"], required_receipts=[{"slot": "doc", "receipt_type": "Documentation"}])
    store.mark_budget_exceeded("T1", STORY, m, KEY, "sup")
    d = gate.evaluate(m, store.receipts_for_task("T1"), m["base_head"], epoch, KEY)
    assert d["verdict"] == "MODIFY" and d["acceptance_unmet"] == ["AC-1"]


# -------------------------------------------------------------------- render


def test_render_state_md_is_deterministic_and_marked_generated(env):
    store, _, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 30)
    store.append_receipt(tr(epoch), STORY)
    first = store.render_state_md(STORY)
    assert first == store.render_state_md(STORY)
    lines = first.splitlines()
    assert "GENERATED VIEW" in lines[0] and "do not edit" in lines[0]
    assert f"# STATE: {STORY}" in first
    assert f"- epoch: {epoch}" in first and "- owner: owner-a" in first
    assert "| T1 | 1 | w1 |" in first and "live" in first
    assert c.receipt_sha256(tr(epoch)) in first
    assert "| T1 | tests | 1 | TestRun | PASS |" in first
    assert first.endswith("\n")


def test_render_state_md_identical_for_identical_histories(tmp_path):
    outs = []
    for name in ("a", "b"):
        clock = FakeClock()
        with Store(str(tmp_path / f"{name}.db"), clock) as s:
            s.init_slots(1)
            s.open_story(STORY, "proj", 4)
            ep = s.acquire_epoch(STORY, "o", 50)
            s.acquire_lease("T1", STORY, "w", ep, 1, 20)
            s.append_receipt(tr(ep), STORY)
            outs.append(s.render_state_md(STORY))
    assert outs[0] == outs[1]


def test_render_state_md_reflects_state_changes(env):
    store, clock, _, epoch = env
    store.acquire_lease("T1", STORY, "w1", epoch, 1, 10)
    before = store.render_state_md(STORY)
    store.release_lease("T1", "w1", epoch)
    after = store.render_state_md(STORY)
    assert before != after and "released" in after
    with pytest.raises(StoreError) as e:
        store.render_state_md("missing")
    assert e.value.kind == "story"


def test_render_state_md_is_read_only(env):
    store, _, path, epoch = env
    store.append_receipt(tr(epoch), STORY)
    n = len(kinds(path))
    store.render_state_md(STORY)
    assert len(kinds(path)) == n
