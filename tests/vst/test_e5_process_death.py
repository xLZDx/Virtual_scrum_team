"""E5 real process death and cross-instance serialisation tests.

A child interpreter is a REAL separate process: it takes an epoch and a worker
lease on a real SQLite file (optionally writes one receipt) and dies with
os._exit(1) in the middle of the lease: no close, no release, no cleanup. The
parent then plays the supervisor with a fake clock. The supervisor must write
WORKER_LOST only for leases that never wrote a receipt.

Self-contained: the child script and every helper are defined in this file.
"""

from __future__ import annotations

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
from tools.vst.store import Store, StoreError  # noqa: E402

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

    def test_takeover_by_a_new_owner_fences_the_dead_lease_and_marker_uses_new_epoch(self) -> None:
        old_epoch = self._kill_child()
        store = self._open()
        self.clock.advance(OWNER_TTL + 1)  # both the lease and the first owner have expired
        new_epoch = self._open().acquire_epoch(STORY, "supervisor-2", OWNER_TTL)
        self.assertEqual(new_epoch, old_epoch + 1)
        self.assertEqual(self._leases(), [(1, "FENCED", 0, 0)])
        self.assertEqual(self._held_slots(), 0)
        written = self._mark(store)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["check_description"], "WORKER_LOST")
        self.assertEqual(written[0]["epoch"], new_epoch)  # marker is written at the CURRENT epoch
        self.assertEqual(self._leases(), [(1, "FENCED", 0, 1)])
        self.assertEqual(self._gate(store)["verdict"], "MODIFY")

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
