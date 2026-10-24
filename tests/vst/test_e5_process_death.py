"""E5 real process death and cross-instance serialisation tests.

A child interpreter acquires an epoch and a lease on a real SQLite file and is
killed with os._exit(1) before writing any receipt. The parent then plays the
supervisor with a fake clock.
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
from tools.vst.store import Store, StoreError  # noqa: E402

CHILD_SCRIPT = """
import os, sys
from tools.vst.store import Store
db, clock_value, story, task = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
store = Store(db, lambda: clock_value)
store.init_slots(2)
store.open_story(story, "synthetic-project", 1)
epoch = store.acquire_epoch(story, "supervisor-1", 3600)
store.acquire_lease(task, story, "worker-1", epoch, 1, 60)
sys.stdout.write(str(epoch) + "\\n")
sys.stdout.flush()
os._exit(1)  # hard death: no close, no receipt, no release
"""

STORY = vst_slice.STORY_ID
TASK = "task-1"
LEASE_TTL = 60


class ProcessDeathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db = os.path.join(self._tmp.name, "state.db")
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
        store = Store(self.db, self.clock)
        self.stores.append(store)
        return store

    def _kill_child(self) -> int:
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO_ROOT
        proc = subprocess.run(
            [sys.executable, "-c", CHILD_SCRIPT, self.db, repr(self.clock.now), STORY, TASK],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120, check=False,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        return int(proc.stdout.strip())

    def _raw(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        return conn

    def _gate(self, store: Store) -> dict:
        return vst_slice.gate_module.evaluate(
            self.manifest,
            store.receipts_for_task(TASK),
            vst_slice.SYNTHETIC_HEAD,
            store.current_epoch(STORY),
            vst_slice.SLICE_KEY,
        )

    def test_dead_worker_state_survives_in_the_file(self) -> None:
        epoch = self._kill_child()
        self.assertEqual(epoch, 2)
        store = self._open()
        self.assertEqual(store.current_epoch(STORY), 2)
        self.assertEqual(store.receipts_for_task(TASK), [])
        conn = self._raw()
        lease = conn.execute("SELECT * FROM leases WHERE task_id=?", (TASK,)).fetchone()
        self.assertEqual((lease["worker_id"], lease["released"], lease["epoch"]), ("worker-1", 0, 2))
        held = conn.execute("SELECT slot_no FROM slots WHERE task_id=?", (TASK,)).fetchall()
        self.assertEqual(len(held), 1)
        # Before the TTL passes the lease is live: nothing is reaped.
        self.assertEqual(store.reap_expired(), [])

    def test_reap_expired_frees_the_slot_of_the_dead_worker(self) -> None:
        self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        self.assertEqual(store.reap_expired(), [TASK])
        conn = self._raw()
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM slots WHERE task_id IS NOT NULL").fetchone()[0], 0
        )
        self.assertEqual(
            conn.execute("SELECT released FROM leases WHERE task_id=?", (TASK,)).fetchone()[0], 2
        )
        # A retry must not erase the failure: the lost attempt has to be marked first.
        with self.assertRaises(StoreError) as ctx:
            store.acquire_lease(TASK, STORY, "worker-2", 2, 2, 60)
        self.assertEqual(ctx.exception.kind, "lease")
        self.assertTrue(store.verify_event_chain())

    def test_supervisor_marks_worker_lost_and_gate_refuses(self) -> None:
        epoch = self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        written = store.supervisor_reap_and_mark(
            lambda _task: self.manifest, vst_slice.SLICE_KEY, vst_slice.RUNNER_ID
        )
        self.assertEqual(len(written), 1)
        receipt = written[0]
        self.assertEqual(receipt["check_description"], "WORKER_LOST")
        self.assertEqual(receipt["result"], "INCONCLUSIVE")
        self.assertEqual(receipt["epoch"], epoch)
        self.assertEqual(receipt["attempt"], 1)

        conn = self._raw()
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM slots WHERE task_id IS NOT NULL").fetchone()[0], 0
        )
        lease = conn.execute("SELECT released, marked FROM leases WHERE task_id=?", (TASK,)).fetchone()
        self.assertEqual((lease["released"], lease["marked"]), (2, 1))

        stored = store.receipts_for_task(TASK)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0], receipt)
        # The receipt is signed with the supervisor key and verifies under it only.
        from tools.vst.signing import verify

        self.assertTrue(verify(stored[0], vst_slice.SLICE_KEY))
        self.assertFalse(verify(stored[0], vst_slice.WRONG_KEY))

        decision = self._gate(store)
        self.assertNotEqual(decision["verdict"], "APPROVE")
        self.assertNotEqual(decision["verdict"], "APPROVED_WITH_WAIVER")
        self.assertTrue(decision["reasons"])

        # Marking is idempotent: a second pass writes nothing more.
        again = store.supervisor_reap_and_mark(
            lambda _task: self.manifest, vst_slice.SLICE_KEY, vst_slice.RUNNER_ID
        )
        self.assertEqual(again, [])
        self.assertEqual(len(store.receipts_for_task(TASK)), 1)
        self.assertTrue(store.verify_event_chain())

        # After marking, the next attempt may take a lease again (slot is free).
        store.acquire_lease(TASK, STORY, "worker-2", epoch, 2, 60)

    def test_dead_workers_old_epoch_cannot_write_after_new_owner(self) -> None:
        old_epoch = self._kill_child()
        store = self._open()
        self.clock.advance(LEASE_TTL + 1)
        store.supervisor_reap_and_mark(
            lambda _task: self.manifest, vst_slice.SLICE_KEY, vst_slice.RUNNER_ID
        )
        # Owner TTL (3600) passes; a new owner takes the story in a second Store instance.
        self.clock.advance(4000)
        second = self._open()
        new_epoch = second.acquire_epoch(STORY, "supervisor-2", 3600)
        self.assertEqual(new_epoch, old_epoch + 1)

        # Build a correctly signed receipt that still carries the dead worker's epoch.
        builder_dir = os.path.join(self._tmp.name, "builder")
        builder = vst_slice.SliceFixture(builder_dir, vst_slice.SLICE_KEY, self.clock)
        self.addCleanup(builder.close)
        zombie = builder.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS, epoch=old_epoch)
        self.assertEqual(zombie["epoch"], old_epoch)
        for writer in (store, second):
            with self.assertRaises(StoreError) as ctx:
                writer.append_receipt(zombie, STORY)
            self.assertEqual(ctx.exception.kind, "epoch")
        # The dead worker's heartbeat is refused as well.
        with self.assertRaises(StoreError):
            second.heartbeat(TASK, "worker-1", old_epoch, 60)
        # Only the WORKER_LOST marker exists; nothing from the zombie was stored.
        stored = second.receipts_for_task(TASK)
        self.assertEqual([r["check_description"] for r in stored], ["WORKER_LOST"])
        # The same content at the new epoch is accepted: the rejection was about the epoch only.
        fresh = builder.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS, epoch=new_epoch)
        self.assertEqual(fresh["slot"], "tests")
        # tests slot already holds the supervisor attempt 1; next attempt must chain to it.
        chained = builder.make_test_receipt(
            2, vst_slice.EXPECTED_TEST_IDS, epoch=new_epoch, prev=_sha(stored[0])
        )
        second.append_receipt(chained, STORY)
        self.assertEqual(len(second.receipts_for_task(TASK)), 2)
        self.assertTrue(second.verify_event_chain())


def _sha(receipt: dict) -> str:
    from tools.vst.contracts import receipt_sha256

    return receipt_sha256(receipt)


class ConcurrentEpochTests(unittest.TestCase):
    ROUNDS = 25

    def test_two_store_instances_exactly_one_wins_each_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "state.db")
            clock = vst_slice.FakeClock()
            setup = Store(db, clock)
            try:
                setup.init_slots(2)
                for i in range(self.ROUNDS):
                    setup.open_story(f"story-{i}", "synthetic-project", 1)
            finally:
                setup.close()

            barrier = threading.Barrier(2)
            results: dict[str, list[tuple[str, object]]] = {"a": [], "b": []}
            errors: list[BaseException] = []

            def worker(name: str) -> None:
                try:
                    store = Store(db, clock)  # own connection, created in this thread
                    try:
                        for i in range(self.ROUNDS):
                            barrier.wait(timeout=60)
                            try:
                                epoch = store.acquire_epoch(f"story-{i}", f"owner-{name}", 3600)
                                results[name].append(("ok", epoch))
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
                t.join(timeout=120)
            self.assertFalse(any(t.is_alive() for t in threads))
            self.assertEqual(errors, [])

            verify = Store(db, clock)
            try:
                for i in range(self.ROUNDS):
                    outcomes = [results["a"][i], results["b"][i]]
                    winners = [o for o in outcomes if o[0] == "ok"]
                    losers = [o for o in outcomes if o[0] == "err"]
                    self.assertEqual(len(winners), 1, (i, outcomes))
                    self.assertEqual(losers, [("err", "epoch")], (i, outcomes))
                    self.assertEqual(winners[0][1], 2)
                    self.assertEqual(verify.current_epoch(f"story-{i}"), 2)
                self.assertTrue(verify.verify_event_chain())
            finally:
                verify.close()


if __name__ == "__main__":
    unittest.main()
