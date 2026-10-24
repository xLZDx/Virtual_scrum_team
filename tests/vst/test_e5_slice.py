"""E5 vertical-slice end-to-end tests: the fourteen synthetic scenarios, the fixture keys and the CLI.

Journey: synthetic story -> Store (epoch, task registration, lease, receipts)
-> signing -> gate. Every scenario is asserted on its exact observable verdict
and reasons, and where it matters on the rows of the SQLite file itself.

Self-contained: only tools.vst.slice is used for the fixture; no sibling test
helper is imported.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.vst import slice as vst_slice  # noqa: E402
from tools.vst.contracts import ContractError, SUPERVISOR_SLOT  # noqa: E402
from tools.vst.signing import verify  # noqa: E402
from tools.vst.store import StoreError  # noqa: E402

EXPECTED_SCENARIOS = {
    "happy_path",
    "worker_death_before_receipt",
    "zombie_late_write",
    "stale_head",
    "retry_after_fail",
    "forged_receipt",
    "partial_static_coverage",
    "missing_required_receipt",
    "not_run_with_waiver",
    "budget_exceeded",
    "real_run_and_sign",
    "retry_exhausted",
    "forged_supervisor_receipt",
    "manifest_swap",
}

MISSING_ALL = [
    "missing receipt for slot 'tests'",
    "missing receipt for slot 'static'",
    "missing receipt for slot 'review'",
    "acceptance not covered: 'AC-1'",
    "acceptance not covered: 'AC-2'",
]


def _reasons_text(obs: dict) -> str:
    return "\n".join(obs["reasons"])


class SliceScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.workdir = os.path.join(cls._tmp.name, "slice")
        cls.report = vst_slice.run_scenarios(cls.workdir)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _db(self, scenario: str) -> sqlite3.Connection:
        conn = sqlite3.connect(os.path.join(self.workdir, scenario, "state.db"))
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        return conn

    def _event_kinds(self, scenario: str) -> list[str]:
        return [r[0] for r in self._db(scenario).execute("SELECT kind FROM events ORDER BY seq")]

    def _leases(self, scenario: str) -> list[sqlite3.Row]:
        return self._db(scenario).execute(
            "SELECT attempt, status, wrote, marked, worker_id FROM leases ORDER BY lease_id"
        ).fetchall()

    def _held_slots(self, scenario: str) -> int:
        return self._db(scenario).execute(
            "SELECT COUNT(*) FROM slots WHERE lease_id IS NOT NULL"
        ).fetchone()[0]

    # ----------------------------------------------------------- catalogue

    def test_scenario_catalogue_is_exactly_the_fourteen_expected(self) -> None:
        self.assertEqual(set(self.report), EXPECTED_SCENARIOS)
        self.assertEqual(len(self.report), 14)
        names = [name for name, _ in vst_slice.SCENARIOS]
        self.assertEqual(len(names), 14)
        self.assertEqual(set(names), EXPECTED_SCENARIOS)
        for name, obs in self.report.items():
            self.assertEqual(
                set(obs), {"verdict", "reasons", "unresolved_findings", "extra"}, name
            )
            self.assertIn(obs["verdict"], {"APPROVE", "MODIFY", "NO_GO", "APPROVED_WITH_WAIVER"})

    def test_each_scenario_runs_in_its_own_database(self) -> None:
        for name in EXPECTED_SCENARIOS:
            self.assertTrue(os.path.isfile(os.path.join(self.workdir, name, "state.db")), name)

    def test_only_three_scenarios_approve_and_none_by_waiver_at_top_level(self) -> None:
        approving = {n for n, o in self.report.items() if o["verdict"] == "APPROVE"}
        self.assertEqual(
            approving, {"happy_path", "retry_after_fail", "real_run_and_sign"}
        )
        self.assertNotIn(
            "APPROVED_WITH_WAIVER", {o["verdict"] for o in self.report.values()}
        )

    # ------------------------------------------------------------ original ten

    def test_happy_path_approves_with_three_receipts_and_clean_lease(self) -> None:
        obs = self.report["happy_path"]
        self.assertEqual(obs["verdict"], "APPROVE", obs["reasons"])
        self.assertEqual(obs["reasons"], [])
        self.assertEqual(obs["unresolved_findings"], [])
        self.assertEqual(obs["extra"], {"receipt_count": 3, "event_chain_ok": True})
        leases = self._leases("happy_path")
        self.assertEqual(len(leases), 1)
        self.assertEqual(
            (leases[0]["attempt"], leases[0]["status"], leases[0]["wrote"], leases[0]["marked"]),
            (1, "RELEASED", 1, 0),
        )
        self.assertEqual(leases[0]["worker_id"], vst_slice.WORKER_ID)
        self.assertEqual(self._held_slots("happy_path"), 0)
        kinds = self._event_kinds("happy_path")
        self.assertEqual(kinds.count("TASK_REGISTERED"), 1)
        self.assertEqual(kinds.count("LEASE_ACQUIRED"), 1)
        self.assertEqual(kinds.count("RECEIPT_APPENDED"), 3)
        self.assertEqual(kinds.count("LEASE_RELEASED"), 1)
        # No supervisor marker on a clean run.
        rows = self._db("happy_path").execute(
            "SELECT COUNT(*) FROM receipts WHERE slot = ?", (SUPERVISOR_SLOT,)
        ).fetchone()[0]
        self.assertEqual(rows, 0)

    def test_worker_death_before_receipt_marks_worker_lost_and_keeps_attempt(self) -> None:
        obs = self.report["worker_death_before_receipt"]
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(obs["reasons"], MISSING_ALL)
        self.assertEqual(obs["unresolved_findings"], ["worker lost: attempt 1"])
        one = {"slot": SUPERVISOR_SLOT, "result": "INCONCLUSIVE", "reason": "WORKER_LOST"}
        self.assertEqual(obs["extra"]["written"], [one])
        self.assertEqual(obs["extra"]["stored"], [dict(one, attempt=1)])
        leases = self._leases("worker_death_before_receipt")
        self.assertEqual(len(leases), 1)
        self.assertEqual(
            (leases[0]["attempt"], leases[0]["status"], leases[0]["wrote"], leases[0]["marked"]),
            (1, "EXPIRED", 0, 1),
        )
        self.assertEqual(self._held_slots("worker_death_before_receipt"), 0)
        conn = self._db("worker_death_before_receipt")
        rows = conn.execute("SELECT slot, body FROM receipts").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slot"], SUPERVISOR_SLOT)
        body = json.loads(rows[0]["body"])
        self.assertEqual(body["check_description"], "WORKER_LOST")
        self.assertEqual(body["result"], "INCONCLUSIVE")
        self.assertEqual(body["runner_id"], vst_slice.SUPERVISOR_RUNNER)
        # Signed by the supervisor key, and by no other key.
        self.assertTrue(verify(body, vst_slice.SUPERVISOR_KEY))
        self.assertFalse(verify(body, vst_slice.WORKER_KEY))
        self.assertFalse(verify(body, vst_slice.OPERATOR_KEY))
        self.assertIn("LEASE_EXPIRED", self._event_kinds("worker_death_before_receipt"))

    def test_zombie_late_write_is_fenced_and_leaves_no_trace(self) -> None:
        obs = self.report["zombie_late_write"]
        extra = obs["extra"]
        self.assertEqual((extra["old_epoch"], extra["new_epoch"]), (2, 3))
        self.assertEqual(extra["append_error_kind"], "epoch")
        # The takeover fenced the old lease, so the zombie heartbeat has no live lease.
        self.assertEqual(extra["heartbeat_error_kind"], "lease")
        self.assertEqual(extra["stored_count"], 0)
        leases = self._leases("zombie_late_write")
        self.assertEqual(len(leases), 1)
        self.assertEqual((leases[0]["status"], leases[0]["wrote"]), ("FENCED", 0))
        self.assertEqual(self._held_slots("zombie_late_write"), 0)
        self.assertEqual(
            self._db("zombie_late_write").execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 0
        )
        self.assertIn("LEASE_FENCED", self._event_kinds("zombie_late_write"))
        # Even forced into the gate the stale-epoch receipt cannot approve.
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(
            obs["reasons"][0],
            "slot 'tests' needs a current-epoch attempt (latest attempt 1 is from epoch 2)",
        )
        self.assertEqual(obs["reasons"][1:], MISSING_ALL[1:])

    def test_stale_head_is_no_go_for_every_receipt(self) -> None:
        obs = self.report["stale_head"]
        self.assertEqual(obs["verdict"], "NO_GO")
        self.assertNotEqual(obs["extra"]["receipt_head"], obs["extra"]["current_head"])
        self.assertEqual(obs["extra"]["receipt_head"], vst_slice.SYNTHETIC_HEAD)
        self.assertEqual(obs["extra"]["current_head"], vst_slice.OTHER_HEAD)
        stale = [r for r in obs["reasons"] if "stale head: candidate_head != current head" in r]
        self.assertEqual(len(stale), 3)
        self.assertIn("all receipts for this task are stale (head mismatch or future epoch)",
                      obs["reasons"])
        for slot in ("tests", "static", "review"):
            self.assertIn(f"missing receipt for slot '{slot}'", obs["reasons"])

    def test_retry_after_fail_approves_but_keeps_the_earlier_failure(self) -> None:
        obs = self.report["retry_after_fail"]
        self.assertEqual(obs["verdict"], "APPROVE", obs["reasons"])
        self.assertEqual(obs["reasons"], [])
        self.assertEqual(obs["unresolved_findings"], ["earlier failure retained: tests attempt 1 FAIL"])
        self.assertEqual(
            obs["extra"]["test_attempts"],
            [{"attempt": 1, "result": "FAIL"}, {"attempt": 2, "result": "PASS"}],
        )
        conn = self._db("retry_after_fail")
        rows = conn.execute(
            "SELECT attempt, receipt_sha256, prev_receipt_sha256, body FROM receipts "
            "WHERE slot = 'tests' ORDER BY attempt"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[0]["body"])["result"], "FAIL")
        self.assertIsNone(rows[0]["prev_receipt_sha256"])
        self.assertEqual(rows[1]["prev_receipt_sha256"], rows[0]["receipt_sha256"])
        leases = self._leases("retry_after_fail")
        self.assertEqual([(l["attempt"], l["status"], l["wrote"]) for l in leases],
                         [(1, "RELEASED", 1), (2, "RELEASED", 1)])

    def test_forged_receipt_is_rejected_for_wrong_key_and_for_tampering(self) -> None:
        obs = self.report["forged_receipt"]
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(len(obs["reasons"]), 2)
        self.assertTrue(obs["reasons"][0].endswith("invalid signature"), obs["reasons"])
        self.assertTrue(obs["reasons"][0].startswith("receipt[0] "))
        self.assertEqual(obs["reasons"][1], "missing receipt for slot 'tests'")
        tampered = obs["extra"]["tampered_field"]
        self.assertEqual(tampered["verdict"], "MODIFY")
        self.assertEqual(len(tampered["reasons"]), 2)
        self.assertTrue(tampered["reasons"][0].endswith("invalid signature"))
        self.assertEqual(tampered["reasons"][1], "missing receipt for slot 'tests'")

    def test_partial_static_coverage_is_inconclusive_and_blocks(self) -> None:
        obs = self.report["partial_static_coverage"]
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(obs["extra"]["static_result"], "INCONCLUSIVE")
        self.assertEqual(obs["reasons"], ["slot 'static' latest attempt 1 result INCONCLUSIVE"])
        row = self._db("partial_static_coverage").execute(
            "SELECT body FROM receipts WHERE slot = 'static'"
        ).fetchone()
        body = json.loads(row["body"])
        self.assertEqual((body["coverage"], body["unsupported_rules"]), ("PARTIAL", ["R3"]))

    def test_missing_required_receipt_names_exactly_the_review_slot(self) -> None:
        obs = self.report["missing_required_receipt"]
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(obs["extra"], {"missing_slot": "review"})
        self.assertEqual(obs["reasons"], ["missing receipt for slot 'review'"])
        count = self._db("missing_required_receipt").execute(
            "SELECT COUNT(*) FROM receipts"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_not_run_with_waiver_matrix(self) -> None:
        obs = self.report["not_run_with_waiver"]
        extra = obs["extra"]
        not_run = "slot 'tests' latest attempt 1 result NOT_RUN"
        # No waiver.
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(obs["reasons"], [not_run])
        # Complete operator-signed waiver for the current head, epoch and manifest.
        self.assertEqual(extra["with_waiver"]["verdict"], "APPROVED_WITH_WAIVER")
        self.assertEqual(extra["with_waiver"]["reasons"], [not_run])  # reason stays visible
        self.assertEqual(extra["with_waiver_record"], "WV-1")
        self.assertEqual(extra["with_waiver_approvals"], ["operator-1"])
        # Waiver bound to another head.
        self.assertEqual(extra["wrong_head_waiver"]["verdict"], "MODIFY")
        self.assertEqual(
            extra["wrong_head_waiver"]["reasons"],
            [not_run, "waiver rejected: waiver head != current head"],
        )
        # Waiver signed with the worker key instead of the operator key.
        self.assertEqual(extra["waiver_signed_with_worker_key"]["verdict"], "MODIFY")
        self.assertEqual(
            extra["waiver_signed_with_worker_key"]["reasons"],
            [not_run, "waiver rejected: invalid signature"],
        )

    def test_budget_exceeded_writes_one_idempotent_blocked_marker(self) -> None:
        obs = self.report["budget_exceeded"]
        extra = obs["extra"]
        self.assertEqual(extra["remaining_after_first_charge"], 2)
        self.assertEqual(extra["charge_error_kind"], "budget")
        self.assertEqual(
            extra["marker"],
            {"slot": SUPERVISOR_SLOT, "result": "BLOCKED", "reason": "BUDGET_EXCEEDED"},
        )
        self.assertTrue(extra["marker_idempotent"])
        self.assertEqual(extra["marker_count"], 1)
        self.assertTrue(extra["event_chain_ok"])
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(
            obs["reasons"][0], "terminal marker BUDGET_EXCEEDED (supervisor attempt 1)"
        )
        self.assertEqual(obs["reasons"][1:], MISSING_ALL)
        conn = self._db("budget_exceeded")
        row = conn.execute("SELECT cap, spent FROM budget WHERE task_id='task-1'").fetchone()
        self.assertEqual((row["cap"], row["spent"]), (5, 3))  # rejected charge not applied
        kinds = self._event_kinds("budget_exceeded")
        self.assertEqual(kinds.count("BUDGET_EXCEEDED"), 1)
        self.assertEqual(kinds.count("BUDGET_BLOCKED"), 1)  # idempotent second call: no event

    # --------------------------------------------------------- the four new ones

    def test_real_run_and_sign_runs_a_real_command_and_gate_approves(self) -> None:
        obs = self.report["real_run_and_sign"]
        extra = obs["extra"]
        self.assertEqual(obs["verdict"], "APPROVE", obs["reasons"])
        self.assertEqual(obs["reasons"], [])
        self.assertEqual(obs["unresolved_findings"], [])
        self.assertTrue(extra["refused_unallowed_command"])
        self.assertTrue(extra["refused_wrong_expected_ids"])
        self.assertEqual(extra["receipt_result"], "PASS")
        self.assertEqual(extra["exit_code"], 0)
        self.assertEqual(extra["executed"], ["t1", "t2"])
        self.assertTrue(extra["bound_to_manifest"])
        self.assertFalse(extra["stdout_truncated"])
        conn = self._db("real_run_and_sign")
        row = conn.execute("SELECT body FROM receipts WHERE slot = 'tests'").fetchone()
        body = json.loads(row["body"])
        self.assertEqual(body["commands"][0]["argv"], vst_slice.REAL_ARGV)
        self.assertEqual(body["commands"][0]["exit_code"], 0)
        self.assertEqual(body["executed_test_ids"], ["t1", "t2"])
        self.assertEqual(body["runner_id"], vst_slice.WORKER_ID)
        self.assertTrue(verify(body, vst_slice.WORKER_KEY))
        # Refused runs never produced a receipt: only the signed run was stored.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 3)

    def test_retry_exhausted_blocks_third_attempt_with_a_single_marker(self) -> None:
        obs = self.report["retry_exhausted"]
        extra = obs["extra"]
        self.assertEqual(extra["retry_cap"], 1)
        self.assertEqual(extra["third_attempt_error_kinds"], ["retry", "retry"])
        self.assertEqual(extra["markers"], ["RETRY_EXHAUSTED"])  # written once, idempotent
        self.assertEqual(extra["marker_results"], ["BLOCKED"])
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(
            obs["reasons"][0], "terminal marker RETRY_EXHAUSTED (supervisor attempt 1)"
        )
        self.assertIn("slot 'tests' latest attempt 2 result FAIL", obs["reasons"])
        self.assertEqual(obs["unresolved_findings"], ["earlier failure retained: tests attempt 1 FAIL"])
        # The refused third attempt never created a lease row.
        leases = self._leases("retry_exhausted")
        self.assertEqual([(l["attempt"], l["status"]) for l in leases],
                         [(1, "RELEASED"), (2, "RELEASED")])
        self.assertEqual(self._held_slots("retry_exhausted"), 0)

    def test_forged_supervisor_receipt_cannot_enter_the_store_and_fails_the_gate(self) -> None:
        obs = self.report["forged_supervisor_receipt"]
        extra = obs["extra"]
        self.assertEqual(extra["store_supervisor_path_kind"], "signature")
        self.assertEqual(extra["store_worker_path_kind"], "supervisor")
        self.assertEqual(extra["genuine_via_worker_path_kind"], "supervisor")
        self.assertEqual(extra["stored_count"], 0)
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(len(obs["reasons"]), 1)
        self.assertTrue(obs["reasons"][0].startswith("receipt[3] "))
        self.assertTrue(obs["reasons"][0].endswith("invalid signature"))
        self.assertEqual(
            self._db("forged_supervisor_receipt").execute(
                "SELECT COUNT(*) FROM receipts"
            ).fetchone()[0],
            0,
        )

    def test_manifest_swap_is_rejected_by_store_and_gate(self) -> None:
        obs = self.report["manifest_swap"]
        extra = obs["extra"]
        self.assertTrue(extra["hashes_differ"])
        self.assertEqual(extra["store_append_kind"], "manifest")
        self.assertEqual(extra["register_other_manifest_kind"], "manifest")
        self.assertEqual(extra["stored_count"], 0)
        self.assertEqual(obs["verdict"], "MODIFY")
        self.assertEqual(len(obs["reasons"]), 2)
        self.assertTrue(
            obs["reasons"][0].endswith("manifest_sha256 does not match the manifest"),
            obs["reasons"],
        )
        self.assertEqual(obs["reasons"][1], "missing receipt for slot 'tests'")
        conn = self._db("manifest_swap")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
        # The lease taken before the bad append was released normally and wrote nothing.
        leases = self._leases("manifest_swap")
        self.assertEqual([(l["status"], l["wrote"]) for l in leases], [("RELEASED", 0)])

    def test_every_scenario_event_chain_is_intact_in_its_file(self) -> None:
        from tools.vst.store import Store

        for name in sorted(EXPECTED_SCENARIOS):
            store = Store(
                os.path.join(self.workdir, name, "state.db"),
                lambda: vst_slice.CLOCK_START,
                event_key=vst_slice.EVENT_KEY,
            )
            try:
                self.assertTrue(store.verify_event_chain(), name)
            finally:
                store.close()
        # A wrong event key must NOT verify the chain.
        store = Store(
            os.path.join(self.workdir, "happy_path", "state.db"),
            lambda: vst_slice.CLOCK_START,
            event_key=vst_slice.WRONG_KEY,
        )
        try:
            self.assertFalse(store.verify_event_chain())
        finally:
            store.close()


class SliceFixtureKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _dir(self, name: str) -> str:
        return os.path.join(self._tmp.name, name)

    def test_default_keys_are_distinct_and_at_least_32_bytes(self) -> None:
        keys = [
            vst_slice.WORKER_KEY, vst_slice.SUPERVISOR_KEY,
            vst_slice.OPERATOR_KEY, vst_slice.EVENT_KEY,
        ]
        self.assertEqual(len(set(keys)), 4)
        for key in keys:
            self.assertIsInstance(key, bytes)
            self.assertGreaterEqual(len(key), 32)
        self.assertNotIn(vst_slice.WRONG_KEY, keys)
        self.assertIs(vst_slice.SLICE_KEY, vst_slice.WORKER_KEY)

    def test_fixture_refuses_any_pair_of_equal_keys(self) -> None:
        w, s, o, e = (vst_slice.WORKER_KEY, vst_slice.SUPERVISOR_KEY,
                      vst_slice.OPERATOR_KEY, vst_slice.EVENT_KEY)
        cases = {
            "worker=supervisor": (w, s, o, e, dict(supervisor_key=w)),
            "worker=operator": (w, s, o, e, dict(operator_key=w)),
            "worker=event": (w, s, o, e, dict(event_key=w)),
            "supervisor=operator": (w, s, o, e, dict(operator_key=s)),
            "supervisor=event": (w, s, o, e, dict(event_key=s)),
            "operator=event": (w, s, o, e, dict(event_key=o)),
        }
        for label, (_w, _s, _o, _e, override) in cases.items():
            with self.assertRaises(ValueError, msg=label):
                vst_slice.SliceFixture(
                    self._dir(label.replace("=", "_")), w, vst_slice.FakeClock(), **override
                )

    def test_short_keys_are_refused_before_anything_is_signed_or_chained(self) -> None:
        short = b"s" * 31
        fixture = vst_slice.SliceFixture(self._dir("short-worker"), short, vst_slice.FakeClock())
        self.addCleanup(fixture.close)
        with self.assertRaises(ContractError):
            fixture.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS)
        with self.assertRaises(StoreError) as ctx:
            vst_slice.SliceFixture(
                self._dir("short-event"), vst_slice.WORKER_KEY, vst_slice.FakeClock(),
                event_key=short,
            )
        self.assertEqual(ctx.exception.kind, "argument")

    def test_fixture_flow_uses_lease_epoch_and_registered_manifest(self) -> None:
        clock = vst_slice.FakeClock()
        fixture = vst_slice.SliceFixture(self._dir("flow"), vst_slice.WORKER_KEY, clock)
        self.addCleanup(fixture.close)
        self.assertEqual(fixture.epoch, 2)
        self.assertEqual(fixture.store.get_manifest("task-1"), fixture.manifest)
        # No lease: appending is refused.
        receipt = fixture.make_test_receipt(1, vst_slice.EXPECTED_TEST_IDS)
        with self.assertRaises(StoreError) as ctx:
            fixture.append(receipt)
        self.assertEqual(ctx.exception.kind, "lease")
        fixture.begin(1)
        # A second live lease for the same task is refused.
        with self.assertRaises(StoreError) as ctx:
            fixture.begin(2)
        self.assertEqual(ctx.exception.kind, "lease")
        fixture.append(receipt)
        fixture.end()
        self.assertEqual(fixture.store.receipts_for_task("task-1"), [receipt])
        # After release the worker can no longer write.
        again = fixture.make_static_receipt()
        with self.assertRaises(StoreError) as ctx:
            fixture.append(again)
        self.assertEqual(ctx.exception.kind, "lease")

    def test_supervisor_receipt_is_signed_with_the_supervisor_key(self) -> None:
        fixture = vst_slice.SliceFixture(self._dir("sup"), vst_slice.WORKER_KEY, vst_slice.FakeClock())
        self.addCleanup(fixture.close)
        marker = fixture.make_supervisor_receipt("WORKER_LOST")
        self.assertEqual(marker["slot"], SUPERVISOR_SLOT)
        self.assertEqual(marker["result"], "INCONCLUSIVE")
        self.assertTrue(verify(marker, vst_slice.SUPERVISOR_KEY))
        self.assertFalse(verify(marker, vst_slice.WORKER_KEY))
        # The genuine marker is accepted only through the supervisor path.
        fixture.store.append_supervisor_receipt(
            marker, fixture.story_id, supervisor_key=vst_slice.SUPERVISOR_KEY
        )
        self.assertEqual(len(fixture.store.receipts_for_task("task-1")), 1)

    def test_waiver_is_signed_with_the_operator_key_under_the_waiver_label(self) -> None:
        from tools.vst.signing import WAIVER_LABEL

        fixture = vst_slice.SliceFixture(self._dir("wv"), vst_slice.WORKER_KEY, vst_slice.FakeClock())
        self.addCleanup(fixture.close)
        waiver = fixture.make_waiver(["tests"], ["AC-1"])
        self.assertTrue(verify(waiver, vst_slice.OPERATOR_KEY, WAIVER_LABEL))
        self.assertFalse(verify(waiver, vst_slice.WORKER_KEY, WAIVER_LABEL))
        self.assertFalse(verify(waiver, vst_slice.OPERATOR_KEY))  # receipt label must not verify
        self.assertEqual(waiver["epoch"], fixture.epoch)
        self.assertEqual(waiver["manifest_sha256"], fixture.manifest_hash)


class SliceCliTests(unittest.TestCase):
    def _run_cli(self, directory: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "tools.vst.slice", directory],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300, check=False,
        )

    def test_cli_runs_end_to_end_and_reports_all_fourteen_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = self._run_cli(os.path.join(one, "run"))
            second = self._run_cli(os.path.join(two, "run"))
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            parsed = json.loads(first.stdout)
            # The CLI really created one database per scenario in the given directory.
            for name in EXPECTED_SCENARIOS:
                self.assertTrue(
                    os.path.isfile(os.path.join(one, "run", name, "state.db")), name
                )
        self.assertEqual(set(parsed), EXPECTED_SCENARIOS)
        self.assertEqual(len(parsed), 14)
        self.assertEqual(first.stdout, second.stdout)  # deterministic
        self.assertEqual(first.stdout.strip(), json.dumps(parsed, sort_keys=True, indent=2))
        verdicts = {name: obs["verdict"] for name, obs in parsed.items()}
        self.assertEqual(
            verdicts,
            {
                "happy_path": "APPROVE",
                "worker_death_before_receipt": "MODIFY",
                "zombie_late_write": "MODIFY",
                "stale_head": "NO_GO",
                "retry_after_fail": "APPROVE",
                "forged_receipt": "MODIFY",
                "partial_static_coverage": "MODIFY",
                "missing_required_receipt": "MODIFY",
                "not_run_with_waiver": "MODIFY",
                "budget_exceeded": "MODIFY",
                "real_run_and_sign": "APPROVE",
                "retry_exhausted": "MODIFY",
                "forged_supervisor_receipt": "MODIFY",
                "manifest_swap": "MODIFY",
            },
        )
        for name, obs in parsed.items():
            self.assertEqual(
                set(obs), {"verdict", "reasons", "unresolved_findings", "extra"}, name
            )
        self.assertEqual(parsed["real_run_and_sign"]["extra"]["executed"], ["t1", "t2"])
        self.assertEqual(
            parsed["not_run_with_waiver"]["extra"]["with_waiver"]["verdict"], "APPROVED_WITH_WAIVER"
        )

    def test_cli_report_equals_the_in_process_report(self) -> None:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            proc = self._run_cli(os.path.join(one, "run"))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            in_process = vst_slice.run_scenarios(os.path.join(two, "run"))
        self.assertEqual(json.loads(proc.stdout), json.loads(json.dumps(in_process)))

    def test_cli_without_directory_exits_two_and_prints_usage(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.vst.slice"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("usage", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_cli_with_too_many_arguments_exits_two(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.vst.slice", "a", "b"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
