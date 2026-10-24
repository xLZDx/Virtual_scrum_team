"""E5 real process death and cross-instance serialisation tests.

A child interpreter is a REAL separate process: it takes an epoch and a worker
lease on a real SQLite file (optionally writes one receipt) and dies with
os._exit(1) in the middle of the lease: no close, no release, no cleanup. The
parent then plays the supervisor with a fake clock. The supervisor must write
WORKER_LOST only for leases that never wrote a receipt.

Self-contained: the child script and every helper are defined in this file.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.vst import slice as vst_slice  # noqa: E402
from tools.vst.contracts import SUPERVISOR_SLOT, ContractError, receipt_sha256  # noqa: E402
from tools.vst.signing import verify  # noqa: E402
from tools.vst.store import SCHEMA_VERSION, Store, StoreError  # noqa: E402

# argv: mode, directory, clock value, attempt
#   die_no_receipt        first attempt: epoch + task + lease, then hard death
#   die_after_receipt     first attempt: lease, ONE signed receipt appended, then hard death
#   next_attempt          later attempt on the existing database: lease, then hard death
CHILD_SCRIPT = """
import os, sys
from tools.vst import slice as s
from tools.vst.store import Store
mode, directory, clock_value, attempt = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
clock = s.FakeClock(clock_value)
if mode == "next_attempt":
    store = Store(os.path.join(directory, "state.db"), clock, event_key=s.EVENT_KEY)
    epoch = store.current_epoch(s.STORY_ID)
    store.acquire_lease("task-1", s.STORY_ID, s.WORKER_ID, epoch, attempt, 60,
                        supervisor_key=s.SUPERVISOR_KEY)
else:
    fx = s.SliceFixture(directory, s.WORKER_KEY, clock)
    epoch = fx.epoch
    fx.begin(attempt, 60)
    if mode == "die_after_receipt":
        fx.append(fx.make_test_receipt(1, s.EXPECTED_TEST_IDS, exit_code=1))
sys.stdout.write(str(epoch) + " " + str(os.getpid()) + "\\n")
sys.stdout.flush()
os._exit(1)  # hard death: no close, no receipt for this lease, no release
"""

STORY = vst_slice.STORY_ID
TASK = "task-1"
LEASE_TTL = 60
OWNER_TTL = 3600


class ProcessDeathBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = os.path.join(self._tmp.name, "world")
        self.db = os.path.join(self.dir, "state.db")
        self.clock = vst_slice.FakeClock()
        self.manifest = vst_slice.build_synthetic_manifest(TASK, vst_slice.SYNTHETIC_HEAD)
        self.stores: list[Store] = []

    def tearDown(self) -> None:
        for store in self.stores:
            try:
                store.close()
            except sqlite3.Error:
                pass

    def _open(self) -> Store:
        store = Store(self.db, self.clock, event_key=vst_slice.EVENT_KEY)
        self.stores.append(store)
        return store

    def _kill_child(self, mode: str = "die_no_receipt", attempt: int = 1) -> int:
        """Run the child to its hard death; return the epoch it worked under."""
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO_ROOT
        proc = subprocess.run(
            [sys.executable, "-c", CHILD_SCRIPT, mode, self.dir, repr(self.clock.now), str(attempt)],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300, check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)  # died by os._exit(1), not cleanly
        epoch_text, pid_text = proc.stdout.split()
        self.assertNotEqual(int(pid_text), os.getpid())  # a real separate process
        return int(epoch_text)

    def _raw(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        return conn

    def _leases(self) -> list[tuple]:
        return [
            (r["attempt"], r["status"], r["wrote"], r["marked"])
            for r in self._raw().execute(
                "SELECT attempt, status, wrote, marked FROM leases WHERE task_id = ? "
                "ORDER BY attempt", (TASK,)
            )
        ]

    def _held_slots(self) -> int:
        return self._raw().execute(
            "SELECT COUNT(*) FROM slots WHERE lease_id IS NOT NULL"
        ).fetchone()[0]

    def _gate(self, store: Store) -> dict:
        return vst_slice.gate_module.evaluate(
            self.manifest,
            store.receipts_for_task(TASK),
            vst_slice.SYNTHETIC_HEAD,
            store.current_epoch(STORY),
            vst_slice.WORKER_KEY,
            supervisor_key=vst_slice.SUPERVISOR_KEY,
            operator_key=vst_slice.OPERATOR_KEY,
        )

    def _mark(self, store: Store) -> list[dict]:
        return store.supervisor_reap_and_mark(vst_slice.SUPERVISOR_KEY, vst_slice.SUPERVISOR_RUNNER)

    def _builder(self) -> vst_slice.SliceFixture:
        """A separate fixture used only to build correctly signed receipts."""
        builder = vst_slice.SliceFixture(
            os.path.join(self._tmp.name, "builder"), vst_slice.WORKER_KEY, self.clock
        )
        self.addCleanup(builder.close)
        return builder


class ProcessDeathTests(ProcessDeathBase):
    def test_dead_worker_state_survives_in_the_file_and_live_lease_is_untouched(self) -> None:
        epoch = self._kill_child()
        self.assertEqual(epoch, 2)
        store = self._open()
        self.assertEqual(store.current_epoch(STORY), 2)
        self.assertEqual(store.receipts_for_task(TASK), [])
        self.assertEqual(store.get_manifest(TASK), self.manifest)  # registration persisted
        row = self._raw().execute(
            "SELECT worker_id, epoch, status, wrote, marked FROM leases WHERE task_id=?", (TASK,)
        ).fetchone()
        self.assertEqual(
            (row["worker_id"], row["epoch"], row["status"], row["wrote"], row["marked"]),
            (vst_slice.WORKER_ID, 2, "LIVE", 0, 0),
        )
        self.assertEqual(self._held_slots(), 1)
        # Before the TTL passes the lease is live: nothing is reaped and nothing is marked.
        self.assertEqual(store.reap_expired(), [])
        self.assertEqual(self._mark(store), [])
        self.assertEqual(self._leases(), [(1, "LIVE", 0, 0)])
        self.assertEqual(store.receipts_for_task(TASK), [])
        # And a second live lease for the dead-but-not-expired worker's task is refused.
        with self.assertRaises(StoreError) as ctx:
            store.acquire_lease(TASK, STORY, "worker-2", 2, 2, 60,
                                supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "lease")

    def test_reap_expired_frees_the_slot_but_the_lost_attempt_must_be_marked_first(self) -> None:
        self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(store.reap_expired(), [TASK])
        self.assertEqual(self._held_slots(), 0)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 0)])
        # A retry must not erase the failure: the lost attempt has to be marked first.
        with self.assertRaises(StoreError) as ctx:
            store.acquire_lease(TASK, STORY, "worker-2", 2, 2, 60,
                                supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "lease")
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 0)])  # no new lease row appeared
        # The already-expired lease is still marked by the supervisor afterwards.
        written = self._mark(store)
        self.assertEqual([r["check_description"] for r in written], ["WORKER_LOST"])
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 1)])
        self.assertTrue(store.verify_event_chain())

    def test_supervisor_marks_worker_lost_for_a_lease_that_never_wrote(self) -> None:
        epoch = self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        written = self._mark(store)
        self.assertEqual(len(written), 1)
        receipt = written[0]
        self.assertEqual(receipt["slot"], SUPERVISOR_SLOT)
        self.assertEqual(receipt["receipt_type"], "Documentation")
        self.assertEqual(receipt["check_description"], "WORKER_LOST")
        self.assertEqual(receipt["result"], "INCONCLUSIVE")
        self.assertEqual(receipt["epoch"], epoch)
        self.assertEqual(receipt["attempt"], 1)
        self.assertEqual(receipt["runner_id"], vst_slice.SUPERVISOR_RUNNER)
        self.assertEqual(receipt["covered_acceptance"], [])
        self.assertEqual(receipt["candidate_head"], self.manifest["base_head"])
        self.assertEqual(receipt["manifest_sha256"], store.register_task(self.manifest))

        self.assertEqual(self._held_slots(), 0)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 1)])
        stored = store.receipts_for_task(TASK)
        self.assertEqual(stored, [receipt])
        # Signed with the supervisor key and verifies under it only.
        self.assertTrue(verify(stored[0], vst_slice.SUPERVISOR_KEY))
        self.assertFalse(verify(stored[0], vst_slice.WORKER_KEY))
        self.assertFalse(verify(stored[0], vst_slice.OPERATOR_KEY))

        decision = self._gate(store)
        self.assertEqual(decision["verdict"], "MODIFY")
        self.assertIn("worker lost: attempt 1", decision["unresolved_findings"])
        self.assertIn("missing receipt for slot 'tests'", decision["reasons"])

        # Marking is idempotent: a second pass writes nothing more.
        self.assertEqual(self._mark(store), [])
        self.assertEqual(len(store.receipts_for_task(TASK)), 1)
        self.assertTrue(store.verify_event_chain())

        # After marking, the next attempt may take a lease again.
        store.acquire_lease(TASK, STORY, "worker-2", epoch, 2, 60,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 1), (2, "LIVE", 0, 0)])

    def test_no_worker_lost_marker_for_a_lease_that_wrote_a_receipt_before_dying(self) -> None:
        self._kill_child("die_after_receipt")
        store = self._open()
        self.assertEqual(self._leases(), [(1, "LIVE", 1, 0)])
        stored_before = store.receipts_for_task(TASK)
        self.assertEqual(len(stored_before), 1)
        self.assertEqual(stored_before[0]["slot"], "tests")
        self.clock.advance(LEASE_TTL + 1)
        written = self._mark(store)
        self.assertEqual(written, [])  # the worker produced evidence: no WORKER_LOST
        self.assertEqual(self._leases(), [(1, "EXPIRED", 1, 1)])  # flagged marked, nothing written
        self.assertEqual(self._held_slots(), 0)
        stored = store.receipts_for_task(TASK)
        self.assertEqual(stored, stored_before)
        self.assertEqual([r for r in stored if r["slot"] == SUPERVISOR_SLOT], [])
        decision = self._gate(store)
        self.assertNotIn("worker lost: attempt 1", decision["unresolved_findings"])
        self.assertNotIn("APPROVE", decision["verdict"])
        self.assertIn("slot 'tests' latest attempt 1 result FAIL", decision["reasons"])
        self.assertTrue(store.verify_event_chain())

    def test_mixed_history_marks_only_the_lease_that_never_wrote(self) -> None:
        # Attempt 1 writes a failing receipt and dies; attempt 2 dies without writing.
        epoch = self._kill_child("die_after_receipt", 1)
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])
        self._kill_child("next_attempt", 2)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 1, 1), (2, "LIVE", 0, 0)])
        self.clock.advance(LEASE_TTL + 1)
        written = self._mark(store)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["check_description"], "WORKER_LOST")
        self.assertEqual(written[0]["epoch"], epoch)
        self.assertEqual(written[0]["attempt"], 1)  # first marker of the supervisor chain
        # The marker inherits the head of the task's newest receipt.
        self.assertEqual(written[0]["candidate_head"], vst_slice.SYNTHETIC_HEAD)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 1, 1), (2, "EXPIRED", 0, 1)])
        stored = store.receipts_for_task(TASK)
        self.assertEqual([r["slot"] for r in stored], ["tests", SUPERVISOR_SLOT])
        self.assertEqual(self._held_slots(), 0)
        decision = self._gate(store)
        self.assertEqual(decision["verdict"], "MODIFY")
        self.assertIn("worker lost: attempt 1", decision["unresolved_findings"])
        # Attempt 3 would exceed retry_cap=1: refused, with a RETRY_EXHAUSTED marker committed.
        with self.assertRaises(StoreError) as ctx:
            store.acquire_lease(TASK, STORY, "worker-3", epoch, 3, 60,
                                supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "retry")
        markers = [
            r["check_description"] for r in store.receipts_for_task(TASK)
            if r["slot"] == SUPERVISOR_SLOT
        ]
        self.assertEqual(markers, ["WORKER_LOST", "RETRY_EXHAUSTED"])
        self.assertEqual(len(self._leases()), 2)
        self.assertTrue(store.verify_event_chain())

    def test_takeover_reaps_the_expired_dead_lease_and_marker_uses_new_epoch(self) -> None:
        # Third round: acquire_epoch reaps expired leases first, so a lease that has
        # already expired becomes EXPIRED (not FENCED) and is still markable.
        old_epoch = self._kill_child()
        store = self._open()
        self.clock.advance(OWNER_TTL + 1)  # both the lease and the first owner have expired
        new_epoch = self._open().acquire_epoch(STORY, "supervisor-2", OWNER_TTL)
        self.assertEqual(new_epoch, old_epoch + 1)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 0)])
        self.assertEqual(self._held_slots(), 0)
        kinds = [r[0] for r in self._raw().execute("SELECT kind FROM events ORDER BY seq")]
        self.assertEqual(kinds.count("LEASE_EXPIRED"), 1)
        self.assertNotIn("LEASE_FENCED", kinds)
        written = self._mark(store)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["check_description"], "WORKER_LOST")
        self.assertEqual(written[0]["epoch"], new_epoch)  # marker is written at the CURRENT epoch
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 1)])
        decision = self._gate(store)
        self.assertEqual(decision["verdict"], "MODIFY")
        self.assertIn("worker lost: attempt 1", decision["unresolved_findings"])
        self.assertEqual(store.failed_attempts(TASK), 1)  # an expired lease that wrote nothing counts

    def test_takeover_of_a_still_live_lease_fences_it_and_marker_uses_new_epoch(self) -> None:
        old_epoch = self._kill_child()
        store = self._open()
        # The owner steps down while the worker lease (60 s) is still live: it is fenced.
        store.release_epoch(STORY, vst_slice.OWNER)
        new_epoch = self._open().acquire_epoch(STORY, "supervisor-2", OWNER_TTL)
        self.assertEqual(new_epoch, old_epoch + 1)
        self.assertEqual(self._leases(), [(1, "FENCED", 0, 0)])
        self.assertEqual(self._held_slots(), 0)
        kinds = [r[0] for r in self._raw().execute("SELECT kind FROM events ORDER BY seq")]
        self.assertEqual(kinds.count("LEASE_FENCED"), 1)
        self.assertNotIn("LEASE_EXPIRED", kinds)
        written = self._mark(store)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["check_description"], "WORKER_LOST")
        self.assertEqual(written[0]["epoch"], new_epoch)
        self.assertEqual(self._leases(), [(1, "FENCED", 0, 1)])
        self.assertEqual(self._gate(store)["verdict"], "MODIFY")
        self.assertEqual(store.failed_attempts(TASK), 0)  # a fenced lease never counts

    def test_dead_workers_old_epoch_cannot_write_after_new_owner(self) -> None:
        old_epoch = self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self._mark(store)
        # Owner TTL passes; a new owner takes the story in a second Store instance.
        self.clock.advance(OWNER_TTL + 1)
        second = self._open()
        new_epoch = second.acquire_epoch(STORY, "supervisor-2", OWNER_TTL)
        self.assertEqual(new_epoch, old_epoch + 1)

        builder = self._builder()
        zombie = builder.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS, epoch=old_epoch)
        self.assertEqual(zombie["epoch"], old_epoch)
        for writer in (store, second):
            with self.assertRaises(StoreError) as ctx:
                writer.append_receipt(zombie, STORY, vst_slice.WORKER_KEY)
            self.assertEqual(ctx.exception.kind, "epoch")
        # The dead worker's heartbeat is refused as well (its lease is closed).
        with self.assertRaises(StoreError) as ctx:
            second.heartbeat(TASK, vst_slice.WORKER_ID, old_epoch, 60)
        self.assertIn(ctx.exception.kind, ("lease", "epoch"))
        # Only the WORKER_LOST marker exists; nothing from the zombie was stored.
        stored = second.receipts_for_task(TASK)
        self.assertEqual([r["check_description"] for r in stored], ["WORKER_LOST"])
        # The same content at the new epoch, under a fresh lease, is accepted: the
        # rejection was about the epoch only.
        second.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, new_epoch, 2, LEASE_TTL,
                             supervisor_key=vst_slice.SUPERVISOR_KEY)
        fresh = builder.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS, epoch=new_epoch)
        second.append_receipt(fresh, STORY, vst_slice.WORKER_KEY)
        self.assertEqual(
            [r["slot"] for r in second.receipts_for_task(TASK)], [SUPERVISOR_SLOT, "tests"]
        )
        self.assertEqual(self._leases()[-1], (2, "LIVE", 1, 0))
        self.assertTrue(second.verify_event_chain())

    def test_new_attempt_receipt_chains_to_the_dead_attempts_receipt(self) -> None:
        epoch = self._kill_child("die_after_receipt")
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])
        first = store.receipts_for_task(TASK)[0]
        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, 2, LEASE_TTL,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        builder = self._builder()
        # Attempt 2 with no prev link is malformed already at contract level.
        unlinked = builder.make_test_receipt(2, vst_slice.EXPECTED_TEST_IDS, epoch=epoch)
        with self.assertRaises(ContractError):
            store.append_receipt(unlinked, STORY, vst_slice.WORKER_KEY)
        # Attempt 2 pointing at a hash that is not the dead attempt's receipt breaks the chain.
        broken = builder.make_test_receipt(
            2, vst_slice.EXPECTED_TEST_IDS, epoch=epoch, prev="0" * 64
        )
        with self.assertRaises(StoreError) as ctx:
            store.append_receipt(broken, STORY, vst_slice.WORKER_KEY)
        self.assertEqual(ctx.exception.kind, "chain")
        self.assertEqual(len(store.receipts_for_task(TASK)), 1)
        chained = builder.make_test_receipt(
            2, vst_slice.EXPECTED_TEST_IDS, epoch=epoch, prev=receipt_sha256(first)
        )
        store.append_receipt(chained, STORY, vst_slice.WORKER_KEY)
        self.assertEqual(
            [(r["attempt"], r["result"]) for r in store.receipts_for_task(TASK)],
            [(1, "FAIL"), (2, "PASS")],
        )
        self.assertTrue(store.verify_event_chain())


class SecondRoundStoreTests(ProcessDeathBase):
    """Store contract of schema version 3 observed across a real process death."""

    def _events(self) -> list[tuple[str, dict]]:
        return [
            (r["kind"], json.loads(r["payload"]))
            for r in self._raw().execute("SELECT kind, payload FROM events ORDER BY seq")
        ]

    def test_schema_is_version_3_with_receipt_count_after_a_real_death(self) -> None:
        self._kill_child()
        conn = self._raw()
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(SCHEMA_VERSION, 3)
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(leases)")]
        self.assertIn("receipt_count", columns)
        self.assertEqual(
            conn.execute("SELECT receipt_count FROM leases").fetchone()[0], 0
        )
        # Reopening the file by a second Store keeps the version.
        store = self._open()
        self.assertTrue(store.verify_event_chain())
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 3)

    def test_a_version_2_database_is_refused_not_migrated(self) -> None:
        os.makedirs(self.dir, exist_ok=True)
        old = sqlite3.connect(self.db)
        old.execute("PRAGMA user_version = 2")
        old.execute("CREATE TABLE stories (story_id TEXT)")
        old.commit()
        old.close()
        with self.assertRaises(StoreError) as ctx:
            Store(self.db, self.clock, event_key=vst_slice.EVENT_KEY)
        self.assertEqual(ctx.exception.kind, "schema")
        check = self._raw()
        self.assertEqual(check.execute("PRAGMA user_version").fetchone()[0], 2)  # untouched
        self.assertEqual(
            [r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")],
            ["stories"],
        )

    def test_budget_row_is_seeded_from_the_manifest_cost_cap(self) -> None:
        self._kill_child()
        row = self._raw().execute(
            "SELECT cap, spent FROM budget WHERE task_id = ?", (TASK,)
        ).fetchone()
        self.assertEqual((row["cap"], row["spent"]), (self.manifest["cost_cap"], 0))

    def test_partial_lease_records_lease_expired_partial_but_no_worker_lost(self) -> None:
        self._kill_child("die_after_receipt")
        store = self._open()
        lease_id = self._raw().execute(
            "SELECT lease_id FROM leases WHERE task_id = ?", (TASK,)
        ).fetchone()[0]
        self.assertEqual(
            self._raw().execute("SELECT receipt_count FROM leases").fetchone()[0], 1
        )
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])  # no WORKER_LOST for a lease that wrote
        events = self._events()
        kinds = [k for k, _ in events]
        self.assertEqual(kinds.count("LEASE_EXPIRED"), 1)
        self.assertEqual(kinds.count("LEASE_EXPIRED_PARTIAL"), 1)
        # The partial event directly follows the expiry event of the same lease.
        at = kinds.index("LEASE_EXPIRED")
        self.assertEqual(kinds[at + 1], "LEASE_EXPIRED_PARTIAL")
        self.assertEqual(events[at][1], {"attempt": 1})
        self.assertEqual(
            events[at + 1][1], {"attempt": 1, "lease_id": lease_id, "receipts": 1}
        )
        self.assertEqual(
            [r for r in store.receipts_for_task(TASK) if r["slot"] == SUPERVISOR_SLOT], []
        )
        # A second pass records nothing new: the event is written once per expiry.
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])
        self.assertEqual([k for k, _ in self._events()].count("LEASE_EXPIRED_PARTIAL"), 1)
        self.assertTrue(store.verify_event_chain())

    def test_lease_that_wrote_nothing_records_no_partial_event(self) -> None:
        self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(len(self._mark(store)), 1)
        kinds = [k for k, _ in self._events()]
        self.assertEqual(kinds.count("LEASE_EXPIRED"), 1)
        self.assertNotIn("LEASE_EXPIRED_PARTIAL", kinds)

    def test_fenced_takeover_leases_do_not_count_toward_the_retry_cap(self) -> None:
        # retry_cap is 1, so the cap trips at 2 worker failures. Fence more leases than that.
        # The lease must still be LIVE at takeover (an expired one is reaped to EXPIRED
        # and does count), so the owner steps down instead of waiting for its TTL.
        self._kill_child()
        store = self._open()
        owner = vst_slice.OWNER
        epoch = store.current_epoch(STORY)
        for round_no in range(1, 4):
            if round_no > 1:
                store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, round_no, LEASE_TTL,
                                    supervisor_key=vst_slice.SUPERVISOR_KEY)
            store.release_epoch(STORY, owner)
            owner = f"supervisor-{round_no + 1}"
            epoch = store.acquire_epoch(STORY, owner, OWNER_TTL)
            written = self._mark(store)
            self.assertEqual([r["check_description"] for r in written], ["WORKER_LOST"])
            self.assertEqual(store.failed_attempts(TASK), 0, round_no)
        self.assertEqual(
            [(a, s) for a, s, _w, _m in self._leases()],
            [(1, "FENCED"), (2, "FENCED"), (3, "FENCED")],
        )
        # A fourth lease is still granted and no RETRY_EXHAUSTED marker exists.
        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, 4, LEASE_TTL,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(self._leases()[-1], (4, "LIVE", 0, 0))
        reasons = [
            r["check_description"] for r in store.receipts_for_task(TASK)
            if r["slot"] == SUPERVISOR_SLOT
        ]
        self.assertEqual(reasons, ["WORKER_LOST"] * 3)
        self.assertTrue(store.verify_event_chain())

    def test_expired_lease_without_receipts_counts_and_trips_the_cap(self) -> None:
        self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(len(self._mark(store)), 1)
        self.assertEqual(store.failed_attempts(TASK), 1)
        epoch = store.current_epoch(STORY)
        self._kill_child("next_attempt", 2)
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(len(self._mark(store)), 1)
        self.assertEqual(store.failed_attempts(TASK), 2)  # == retry_cap + 1
        with self.assertRaises(StoreError) as ctx:
            store.acquire_lease(TASK, STORY, "worker-3", epoch, 3, LEASE_TTL,
                                supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "retry")
        reasons = [
            r["check_description"] for r in store.receipts_for_task(TASK)
            if r["slot"] == SUPERVISOR_SLOT
        ]
        self.assertEqual(reasons, ["WORKER_LOST", "WORKER_LOST", "RETRY_EXHAUSTED"])
        self.assertEqual(len(self._leases()), 2)

    def test_worker_receipt_failures_count_per_slot_not_per_receipt_total(self) -> None:
        self._kill_child("die_after_receipt")  # one FAIL receipt in slot 'tests'
        store = self._open()
        self.assertEqual(store.failed_attempts(TASK), 1)
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])
        # Still counted exactly once after the lease expired with its receipt.
        self.assertEqual(store.failed_attempts(TASK), 1)
        # Attempt 2 is allowed (1 < retry_cap + 1).
        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, store.current_epoch(STORY), 2,
                            LEASE_TTL, supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 1, 1), (2, "LIVE", 0, 0)])

    # ---- third round: failed_attempts rules (every non-PASS worker result + lost leases)

    def _world(self, name: str, retry_cap: int = 4) -> vst_slice.SliceFixture:
        """A fresh fixture with a roomy retry_cap, so only the counter is observed."""
        fx = vst_slice.SliceFixture(
            os.path.join(self._tmp.name, name), vst_slice.WORKER_KEY, self.clock,
            retry_cap=retry_cap,
        )
        self.addCleanup(fx.close)
        return fx

    def test_failed_attempts_counts_a_released_lease_that_wrote_nothing(self) -> None:
        fx = self._world("released-empty")
        self.assertEqual(fx.store.failed_attempts(TASK), 0)
        fx.begin(1)
        self.assertEqual(fx.store.failed_attempts(TASK), 0)  # a LIVE lease is not a failure
        fx.end()
        self.assertEqual(fx.store.failed_attempts(TASK), 1)
        fx.begin(2)
        fx.end()
        self.assertEqual(fx.store.failed_attempts(TASK), 2)
        leases = self._lease_rows(fx)
        self.assertEqual(leases, [(1, "RELEASED", 0), (2, "RELEASED", 0)])

    def test_failed_attempts_does_not_count_a_released_lease_that_wrote_a_pass(self) -> None:
        fx = self._world("released-pass")
        fx.begin(1)
        fx.append_good_set()
        fx.end()
        self.assertEqual(self._lease_rows(fx), [(1, "RELEASED", 1)])
        self.assertEqual(fx.store.failed_attempts(TASK), 0)

    def test_failed_attempts_counts_every_non_pass_worker_result(self) -> None:
        # One world per result, so each count stands alone: exactly 1 for a non-PASS
        # result, 0 for PASS.
        cases = {
            "FAIL": dict(exit_code=1),
            "INCONCLUSIVE": dict(result="INCONCLUSIVE"),
            "NOT_RUN": dict(result="NOT_RUN"),
            "BLOCKED": dict(result="BLOCKED"),
            "PASS": dict(),
        }
        counts = {}
        for label, kwargs in cases.items():
            fx = self._world(f"result-{label.lower()}")
            fx.begin(1)
            executed = () if kwargs.get("result") == "NOT_RUN" else vst_slice.EXPECTED_TEST_IDS
            receipt = fx.make_test_receipt(1, executed, **kwargs)
            self.assertEqual(receipt["result"], label)
            fx.append(receipt)
            fx.end()
            counts[label] = fx.store.failed_attempts(TASK)
        self.assertEqual(
            counts, {"FAIL": 1, "INCONCLUSIVE": 1, "NOT_RUN": 1, "BLOCKED": 1, "PASS": 0}
        )

    def test_failed_attempts_is_the_maximum_over_slots_not_the_sum(self) -> None:
        fx = self._world("per-slot")
        fx.begin(1)
        tests1 = fx.make_test_receipt(1, (), result="NOT_RUN")
        fx.append(tests1)
        fx.append(fx.make_static_receipt(result="NOT_RUN"))
        fx.end()
        # Two slots failed once each: the counter is 1, not 2.
        self.assertEqual(fx.store.failed_attempts(TASK), 1)
        fx.begin(2)
        fx.append(fx.make_test_receipt(
            2, vst_slice.EXPECTED_TEST_IDS, exit_code=1, prev=receipt_sha256(tests1)
        ))
        fx.end()
        self.assertEqual(fx.store.failed_attempts(TASK), 2)  # tests twice, static once
        self.assertEqual(self._lease_rows(fx), [(1, "RELEASED", 1), (2, "RELEASED", 1)])

    def test_failed_attempts_adds_lost_leases_to_the_worker_receipt_failures(self) -> None:
        # A FAIL receipt (attempt 1) plus an expired lease that wrote nothing (attempt 2).
        self._kill_child("die_after_receipt")
        store = self._open()
        self.assertEqual(store.failed_attempts(TASK), 1)
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])
        self._kill_child("next_attempt", 2)
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(len(self._mark(store)), 1)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 1, 1), (2, "EXPIRED", 0, 1)])
        self.assertEqual(store.failed_attempts(TASK), 2)  # 1 receipt failure + 1 lost lease

    def _lease_rows(self, fx: vst_slice.SliceFixture) -> list[tuple]:
        conn = sqlite3.connect(os.path.join(fx.workdir, "state.db"))
        self.addCleanup(conn.close)
        return [
            (attempt, status, wrote)
            for attempt, status, wrote in conn.execute(
                "SELECT attempt, status, wrote FROM leases WHERE task_id = ? ORDER BY attempt",
                (TASK,),
            )
        ]

    # ---- third round: heartbeat after a terminal marker or an exceeded budget

    def _lease_expiry(self) -> tuple[float, float]:
        row = self._raw().execute(
            "SELECT l.expires_at AS lease_exp, s.expires_at AS slot_exp FROM leases l "
            "JOIN slots s ON s.lease_id = l.lease_id WHERE l.task_id = ?", (TASK,)
        ).fetchone()
        return row["lease_exp"], row["slot_exp"]

    def test_heartbeat_extends_a_healthy_lease_baseline(self) -> None:
        self._kill_child()
        store = self._open()
        before = self._lease_expiry()
        self.clock.advance(10)
        store.heartbeat(TASK, vst_slice.WORKER_ID, store.current_epoch(STORY), 600)
        after = self._lease_expiry()
        self.assertEqual(after, (self.clock.now + 600, self.clock.now + 600))
        self.assertGreater(after[0], before[0])

    def test_heartbeat_is_refused_after_budget_exceeded_and_does_not_extend(self) -> None:
        self._kill_child()
        store = self._open()
        epoch = store.current_epoch(STORY)
        store.set_budget(TASK, 5)
        with self.assertRaises(StoreError) as ctx:
            store.charge(TASK, 6, supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "budget")
        before = self._lease_expiry()
        self.clock.advance(10)
        with self.assertRaises(StoreError) as ctx:
            store.heartbeat(TASK, vst_slice.WORKER_ID, epoch, 600)
        self.assertEqual(ctx.exception.kind, "budget")
        self.assertEqual(self._lease_expiry(), before)  # nothing was extended
        # The refused lease runs out at its original deadline and is reaped.
        self.clock.advance(LEASE_TTL)
        self.assertEqual(store.reap_expired(), [TASK])
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 0)])
        self.assertTrue(store.verify_event_chain())

    def test_heartbeat_is_refused_after_a_retry_exhausted_marker(self) -> None:
        self._kill_child()
        store = self._open()
        epoch = store.current_epoch(STORY)
        marker = self._builder().make_supervisor_receipt("RETRY_EXHAUSTED")
        store.append_supervisor_receipt(marker, STORY, supervisor_key=vst_slice.SUPERVISOR_KEY)
        before = self._lease_expiry()
        self.clock.advance(10)
        with self.assertRaises(StoreError) as ctx:
            store.heartbeat(TASK, vst_slice.WORKER_ID, epoch, 600)
        self.assertEqual(ctx.exception.kind, "terminal")
        self.assertEqual(self._lease_expiry(), before)

    def test_heartbeat_at_exactly_the_cap_is_still_allowed(self) -> None:
        self._kill_child()
        store = self._open()
        epoch = store.current_epoch(STORY)
        store.set_budget(TASK, 5)
        self.assertEqual(store.charge(TASK, 5, supervisor_key=vst_slice.SUPERVISOR_KEY), 0)
        self.clock.advance(10)
        store.heartbeat(TASK, vst_slice.WORKER_ID, epoch, 600)  # spent == cap: finishing work
        self.assertEqual(self._lease_expiry(), (self.clock.now + 600,) * 2)
        self.assertEqual(
            [r for r in store.receipts_for_task(TASK) if r["slot"] == SUPERVISOR_SLOT], []
        )

    def test_charge_set_budget_and_record_event_signatures_on_a_real_file(self) -> None:
        self._kill_child()
        store = self._open()
        with self.assertRaises(TypeError):  # supervisor_key is keyword-only and required
            store.charge(TASK, 1)  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            store.charge(TASK, 1, vst_slice.SUPERVISOR_KEY)  # type: ignore[misc]
        with self.assertRaises(StoreError) as ctx:  # the event key must not sign markers
            store.charge(TASK, 1, supervisor_key=vst_slice.EVENT_KEY)
        self.assertEqual(ctx.exception.kind, "key")
        with self.assertRaises(StoreError) as ctx:
            store.set_budget("task-unregistered", 5)
        self.assertEqual(ctx.exception.kind, "task")
        with self.assertRaises(StoreError) as ctx:
            store.set_budget(TASK, self.manifest["cost_cap"] + 1)
        self.assertEqual(ctx.exception.kind, "budget")
        store.set_budget(TASK, 5)
        self.assertEqual(store.charge(TASK, 2, supervisor_key=vst_slice.SUPERVISOR_KEY), 3)
        with self.assertRaises(StoreError) as ctx:
            store.set_budget(TASK, 1)  # below the 2 already spent
        self.assertEqual(ctx.exception.kind, "argument")
        for forbidden in ("OPERATOR_ACTION", "LEASE_EXPIRED_PARTIAL", "BUDGET_EXCEEDED"):
            with self.assertRaises(StoreError, msg=forbidden) as ctx:
                store.record_event(TASK, "someone", forbidden, {})
            self.assertEqual(ctx.exception.kind, "argument")
        store.record_event(TASK, "someone", "NOTE", {"text": "hi"})
        self.assertIn(("NOTE", {"text": "hi"}), self._events())
        self.assertNotIn("OPERATOR_ACTION", [k for k, _ in self._events()])
        # The failed calls left the budget untouched.
        row = self._raw().execute("SELECT cap, spent FROM budget WHERE task_id=?", (TASK,)).fetchone()
        self.assertEqual((row["cap"], row["spent"]), (5, 2))

    def test_charge_over_cap_commits_the_marker_in_the_file_and_blocks_new_leases(self) -> None:
        self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self._mark(store)  # close the dead lease so only the budget can refuse the next one
        store.set_budget(TASK, 4)
        with self.assertRaises(StoreError) as ctx:
            store.charge(TASK, 5, supervisor_key=vst_slice.SUPERVISOR_KEY, runner_id="meter-1")
        self.assertEqual(ctx.exception.kind, "budget")
        # Committed despite the raise: seen by an independent connection and a second Store.
        other = self._open()
        budget_markers = [
            r for r in other.receipts_for_task(TASK) if r["check_description"] == "BUDGET_EXCEEDED"
        ]
        self.assertEqual(len(budget_markers), 1)
        self.assertEqual(budget_markers[0]["result"], "BLOCKED")
        self.assertEqual(budget_markers[0]["runner_id"], "meter-1")
        self.assertTrue(verify(budget_markers[0], vst_slice.SUPERVISOR_KEY))
        kinds = [k for k, _ in self._events()]
        self.assertEqual(kinds.count("BUDGET_EXCEEDED"), 1)
        self.assertEqual(kinds.count("BUDGET_BLOCKED"), 1)
        row = self._raw().execute("SELECT cap, spent FROM budget WHERE task_id=?", (TASK,)).fetchone()
        self.assertEqual((row["cap"], row["spent"]), (4, 0))  # nothing was charged
        with self.assertRaises(StoreError) as ctx:
            other.acquire_lease(TASK, STORY, "worker-2", other.current_epoch(STORY), 2, LEASE_TTL,
                                supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "budget")
        self.assertEqual(len(self._leases()), 1)  # the refused lease left no row
        self.assertTrue(other.verify_event_chain())

    def test_missing_event_anchor_is_an_integrity_error_not_a_silent_recompute(self) -> None:
        self._kill_child()
        store = self._open()
        self.assertTrue(store.verify_event_chain())
        count = len(self._events())
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        conn.execute("DELETE FROM meta WHERE key = 'events_anchor'")
        conn.commit()
        self.assertFalse(store.verify_event_chain())
        with self.assertRaises(StoreError) as ctx:
            store.record_event(TASK, "someone", "NOTE", {"n": 1})
        self.assertEqual(ctx.exception.kind, "integrity")
        self.assertEqual(len(self._events()), count)  # nothing was appended
        with self.assertRaises(StoreError) as ctx:
            store.event_anchor()
        self.assertEqual(ctx.exception.kind, "integrity")


class IndependentReviewFixTests(ProcessDeathBase):
    """Store fixes of the independent review observed across a real process death."""

    def _count_markers(self, store: Store, reason: str) -> int:
        return sum(
            1 for r in store.receipts_for_task(TASK)
            if r["slot"] == SUPERVISOR_SLOT and r["check_description"] == reason
        )

    def test_exact_cap_spend_does_not_block_the_next_lease_after_a_real_death(self) -> None:
        epoch = self._kill_child()
        store = self._open()
        store.set_budget(TASK, 5)
        self.assertEqual(store.charge(TASK, 5, supervisor_key=vst_slice.SUPERVISOR_KEY), 0)
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(len(self._mark(store)), 1)  # WORKER_LOST for the dead lease
        # spent == cap: the next lease is granted and no terminal marker is committed.
        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, 2, LEASE_TTL,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 1), (2, "LIVE", 0, 0)])
        self.assertEqual(self._count_markers(store, "BUDGET_EXCEEDED"), 0)
        kinds = [r[0] for r in self._raw().execute("SELECT kind FROM events")]
        self.assertNotIn("BUDGET_EXCEEDED", kinds)
        row = self._raw().execute("SELECT cap, spent FROM budget WHERE task_id=?", (TASK,)).fetchone()
        self.assertEqual((row["cap"], row["spent"]), (5, 5))
        # One unit more is still refused through charge and then blocks for good.
        with self.assertRaises(StoreError) as ctx:
            store.charge(TASK, 1, supervisor_key=vst_slice.SUPERVISOR_KEY)
        self.assertEqual(ctx.exception.kind, "budget")
        self.assertEqual(self._count_markers(store, "BUDGET_EXCEEDED"), 1)
        with self.assertRaises(StoreError) as ctx:
            store.heartbeat(TASK, vst_slice.WORKER_ID, epoch, 600)
        self.assertEqual(ctx.exception.kind, "budget")

    def test_worker_cannot_preclaim_the_marker_id_of_a_dead_lease_and_marker_lands(self) -> None:
        epoch = self._kill_child()
        store = self._open()
        builder = self._builder()
        marker_id = f"sup-{TASK}-1"
        claim = builder.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS, epoch=epoch)
        claim = vst_slice._resign_with_id(builder, claim, marker_id)
        # The dead worker's lease is still live (TTL not passed): the lease check passes and the
        # reserved prefix is what refuses the receipt.
        with self.assertRaises(StoreError) as ctx:
            store.append_receipt(claim, STORY, vst_slice.WORKER_KEY)
        self.assertEqual(ctx.exception.kind, "validation")
        self.assertEqual(store.receipts_for_task(TASK), [])
        self.assertEqual(self._leases(), [(1, "LIVE", 0, 0)])
        self.clock.advance(LEASE_TTL + 1)
        written = self._mark(store)
        self.assertEqual([r["receipt_id"] for r in written], [marker_id])
        self.assertEqual([r["check_description"] for r in written], ["WORKER_LOST"])
        self.assertEqual(self._leases(), [(1, "EXPIRED", 0, 1)])
        self.assertTrue(store.verify_event_chain())

    def test_retry_across_three_heads_after_a_real_death_in_one_epoch(self) -> None:
        # Attempt 1 (real child, then dead): tests FAIL at h1. Attempt 2 at h2: tests PASS,
        # static INCONCLUSIVE, review PASS. Attempt 3 at h3: everything PASS. In one epoch
        # the tests slot then holds three receipts with a single non-PASS one.
        epoch = self._kill_child("die_after_receipt")
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(self._mark(store), [])
        first = store.receipts_for_task(TASK)[0]
        self.assertEqual((first["slot"], first["result"], first["epoch"]), ("tests", "FAIL", epoch))
        builder = self._builder()
        h2, h3 = vst_slice.OTHER_HEAD, vst_slice.THIRD_HEAD

        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, 2, 600,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        builder.current_head = h2
        tests2 = builder.make_test_receipt(2, vst_slice.EXPECTED_TEST_IDS, epoch=epoch,
                                           prev=receipt_sha256(first))
        static2 = builder.make_static_receipt(coverage="PARTIAL", unsupported=["R3"], epoch=epoch)
        review2 = builder.make_review_receipt(vst_slice.REVIEWER, vst_slice.AUTHOR, epoch=epoch)
        for receipt in (tests2, static2, review2):
            store.append_receipt(receipt, STORY, vst_slice.WORKER_KEY)
        store.release_lease(TASK, vst_slice.WORKER_ID, epoch)
        self.assertEqual(static2["result"], "INCONCLUSIVE")
        self.assertEqual(store.failed_attempts(TASK), 1)  # below retry_cap + 1 = 2

        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, 3, 600,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        builder.current_head = h3
        tests3 = builder.make_test_receipt(3, vst_slice.EXPECTED_TEST_IDS, epoch=epoch,
                                           prev=receipt_sha256(tests2))
        static3 = builder.make_static_receipt(attempt=2, epoch=epoch, prev=receipt_sha256(static2))
        review3 = builder.make_review_receipt(vst_slice.REVIEWER, vst_slice.AUTHOR, attempt=2,
                                              epoch=epoch, prev=receipt_sha256(review2))
        for receipt in (tests3, static3, review3):
            store.append_receipt(receipt, STORY, vst_slice.WORKER_KEY)  # none refused as 'retry'
        store.release_lease(TASK, vst_slice.WORKER_ID, epoch)

        stored = store.receipts_for_task(TASK)
        per_slot = {}
        for r in stored:
            per_slot.setdefault(r["slot"], []).append(r["result"])
        self.assertEqual(per_slot["tests"], ["FAIL", "PASS", "PASS"])
        self.assertEqual(per_slot["static"], ["INCONCLUSIVE", "PASS"])
        self.assertEqual(per_slot["review"], ["PASS", "PASS"])
        decision = vst_slice.gate_module.evaluate(
            self.manifest, stored, h3, store.current_epoch(STORY), vst_slice.WORKER_KEY,
            supervisor_key=vst_slice.SUPERVISOR_KEY, operator_key=vst_slice.OPERATOR_KEY,
        )
        self.assertEqual(decision["verdict"], "APPROVE", decision["reasons"])
        self.assertEqual(self._leases(), [(1, "EXPIRED", 1, 1), (2, "RELEASED", 1, 0),
                                          (3, "RELEASED", 1, 0)])
        self.assertTrue(store.verify_event_chain())

    def test_non_pass_receipts_still_bound_a_slot_in_one_epoch(self) -> None:
        epoch = self._kill_child("die_after_receipt")  # tests attempt 1 FAIL (non-PASS 1 of 2)
        store = self._open()
        first = store.receipts_for_task(TASK)[0]
        builder = self._builder()
        self.clock.advance(LEASE_TTL + 1)
        self._mark(store)
        store.acquire_lease(TASK, STORY, vst_slice.WORKER_ID, epoch, 2, 600,
                            supervisor_key=vst_slice.SUPERVISOR_KEY)
        second = builder.make_test_receipt(2, vst_slice.EXPECTED_TEST_IDS, exit_code=1,
                                           epoch=epoch, prev=receipt_sha256(first))
        store.append_receipt(second, STORY, vst_slice.WORKER_KEY)  # non-PASS 2 of 2
        third = builder.make_test_receipt(3, vst_slice.EXPECTED_TEST_IDS, epoch=epoch,
                                          prev=receipt_sha256(second))
        with self.assertRaises(StoreError) as ctx:  # even a PASS is refused: bound reached
            store.append_receipt(third, STORY, vst_slice.WORKER_KEY)
        self.assertEqual(ctx.exception.kind, "retry")
        self.assertEqual(len(store.receipts_for_task(TASK)), 2)


class ConcurrentSerialisationTests(unittest.TestCase):
    ROUNDS = 25

    def _race(self, db: str, clock, action) -> dict[str, list[tuple[str, object]]]:
        barrier = threading.Barrier(2)
        results: dict[str, list[tuple[str, object]]] = {"a": [], "b": []}
        errors: list[BaseException] = []

        def worker(name: str) -> None:
            try:
                store = Store(db, clock, event_key=vst_slice.EVENT_KEY)  # own connection
                try:
                    for i in range(self.ROUNDS):
                        barrier.wait(timeout=120)
                        try:
                            results[name].append(("ok", action(store, name, i)))
                        except StoreError as exc:
                            results[name].append(("err", exc.kind))
                finally:
                    store.close()
            except BaseException as exc:  # noqa: BLE001 - surfaced below
                errors.append(exc)
                barrier.abort()

        threads = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=300)
        self.assertFalse(any(t.is_alive() for t in threads))
        self.assertEqual(errors, [])
        return results

    def test_two_store_instances_exactly_one_wins_each_epoch_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "state.db")
            clock = vst_slice.FakeClock()
            setup = Store(db, clock, event_key=vst_slice.EVENT_KEY)
            try:
                setup.init_slots(2)
                for i in range(self.ROUNDS):
                    setup.open_story(f"story-{i}", "synthetic-project", 1)
            finally:
                setup.close()
            results = self._race(
                db, clock, lambda s, name, i: s.acquire_epoch(f"story-{i}", f"owner-{name}", 3600)
            )
            verify_store = Store(db, clock, event_key=vst_slice.EVENT_KEY)
            try:
                for i in range(self.ROUNDS):
                    outcomes = [results["a"][i], results["b"][i]]
                    winners = [o for o in outcomes if o[0] == "ok"]
                    losers = [o for o in outcomes if o[0] == "err"]
                    self.assertEqual(len(winners), 1, (i, outcomes))
                    self.assertEqual(losers, [("err", "epoch")], (i, outcomes))
                    self.assertEqual(winners[0][1], 2)
                    self.assertEqual(verify_store.current_epoch(f"story-{i}"), 2)
                self.assertTrue(verify_store.verify_event_chain())
            finally:
                verify_store.close()

    def test_two_store_instances_exactly_one_live_lease_per_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "state.db")
            clock = vst_slice.FakeClock()
            setup = Store(db, clock, event_key=vst_slice.EVENT_KEY)
            try:
                setup.init_slots(2 * self.ROUNDS)
                setup.open_story(STORY, "synthetic-project", 1)
                epoch = setup.acquire_epoch(STORY, "supervisor-1", 3600)
                for i in range(self.ROUNDS):
                    setup.register_task(
                        vst_slice.build_synthetic_manifest(f"task-{i}", vst_slice.SYNTHETIC_HEAD)
                    )
            finally:
                setup.close()
            results = self._race(
                db, clock,
                lambda s, name, i: s.acquire_lease(
                    f"task-{i}", STORY, f"worker-{name}", epoch, 1, 600,
                    supervisor_key=vst_slice.SUPERVISOR_KEY,
                ),
            )
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                for i in range(self.ROUNDS):
                    outcomes = [results["a"][i], results["b"][i]]
                    winners = [o for o in outcomes if o[0] == "ok"]
                    losers = [o for o in outcomes if o[0] == "err"]
                    self.assertEqual(len(winners), 1, (i, outcomes))
                    self.assertEqual(losers, [("err", "lease")], (i, outcomes))
                    live = conn.execute(
                        "SELECT COUNT(*) FROM leases WHERE task_id = ? AND status = 'LIVE'",
                        (f"task-{i}",),
                    ).fetchone()[0]
                    self.assertEqual(live, 1)
                held = conn.execute(
                    "SELECT COUNT(*) FROM slots WHERE lease_id IS NOT NULL"
                ).fetchone()[0]
                self.assertEqual(held, self.ROUNDS)
            finally:
                conn.close()
            verify_store = Store(db, clock, event_key=vst_slice.EVENT_KEY)
            try:
                self.assertTrue(verify_store.verify_event_chain())
            finally:
                verify_store.close()


if __name__ == "__main__":
    unittest.main()
