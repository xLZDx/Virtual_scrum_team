"""E5 vertical-slice end-to-end tests: the ten synthetic scenarios and the CLI.

Journey: synthetic story -> Store (epoch, lease, receipts) -> signing -> gate.
Every scenario is asserted on its exact observable outcome from the plan.
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
}


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

    def test_scenario_names_are_exactly_the_ten_expected(self) -> None:
        self.assertEqual(set(self.report), EXPECTED_SCENARIOS)
        self.assertEqual(len(self.report), 10)
        self.assertEqual(
            {name for name, _ in vst_slice.SCENARIOS}, EXPECTED_SCENARIOS
        )
        for name, obs in self.report.items():
            self.assertEqual(
                set(obs), {"verdict", "reasons", "unresolved_findings", "extra"}, name
            )

    def test_happy_path_approves(self) -> None:
        obs = self.report["happy_path"]
        self.assertEqual(obs["verdict"], "APPROVE", obs["reasons"])
        self.assertEqual(obs["reasons"], [])
        self.assertEqual(obs["unresolved_findings"], [])
        self.assertEqual(obs["extra"]["receipt_count"], 3)
        self.assertTrue(obs["extra"]["event_chain_ok"])

    def test_worker_death_before_receipt_is_not_approved_and_attempt_retained(self) -> None:
        obs = self.report["worker_death_before_receipt"]
        self.assertNotEqual(obs["verdict"], "APPROVE")
        self.assertTrue(obs["reasons"])
        written = obs["extra"]["written"]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["result"], "INCONCLUSIVE")
        self.assertEqual(written[0]["reason"], "WORKER_LOST")
        stored = obs["extra"]["stored"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["attempt"], 1)
        self.assertEqual(stored[0]["reason"], "WORKER_LOST")
        # The lost attempt is still present in the store file itself.
        conn = self._db("worker_death_before_receipt")
        lease = conn.execute("SELECT * FROM leases WHERE task_id = 'task-1'").fetchone()
        self.assertIsNotNone(lease)
        self.assertEqual((lease["attempt"], lease["released"], lease["marked"]), (1, 2, 1))
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM slots WHERE task_id IS NOT NULL").fetchone()[0], 0
        )
        body = json.loads(conn.execute("SELECT body FROM receipts").fetchone()["body"])
        self.assertEqual(body["check_description"], "WORKER_LOST")
        self.assertEqual(body["result"], "INCONCLUSIVE")
        self.assertTrue(body["signature"])

    def test_zombie_late_write_rejected_with_epoch_error(self) -> None:
        obs = self.report["zombie_late_write"]
        extra = obs["extra"]
        self.assertLess(extra["old_epoch"], extra["new_epoch"])
        self.assertEqual(extra["append_error_kind"], "epoch")
        # The takeover fences the old lease (released=2), so the zombie heartbeat
        # is refused as 'lease' (no live lease) rather than 'epoch'; either is a rejection.
        self.assertIn(extra["heartbeat_error_kind"], ("lease", "epoch"))
        conn = self._db("zombie_late_write")
        fenced = conn.execute("SELECT released FROM leases WHERE task_id='task-1'").fetchone()
        self.assertEqual(fenced[0], 2)
        self.assertEqual(extra["stored_count"], 0)
        # Gate forced over the late receipt: stale epoch means NO_GO.
        self.assertEqual(obs["verdict"], "NO_GO")
        self.assertIn("stale epoch", _reasons_text(obs))
        conn = self._db("zombie_late_write")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0], 0)

    def test_stale_head_is_not_approved(self) -> None:
        obs = self.report["stale_head"]
        self.assertNotEqual(obs["verdict"], "APPROVE")
        self.assertIn("stale head", _reasons_text(obs))
        self.assertNotEqual(obs["extra"]["receipt_head"], obs["extra"]["current_head"])

    def test_retry_after_fail_approves_and_keeps_earlier_failure(self) -> None:
        obs = self.report["retry_after_fail"]
        self.assertEqual(obs["verdict"], "APPROVE", obs["reasons"])
        self.assertTrue(
            any("earlier failure retained" in f for f in obs["unresolved_findings"]),
            obs["unresolved_findings"],
        )
        attempts = obs["extra"]["test_attempts"]
        self.assertEqual([a["attempt"] for a in attempts], [1, 2])
        self.assertEqual(attempts[0]["result"], "FAIL")
        self.assertEqual(attempts[1]["result"], "PASS")
        conn = self._db("retry_after_fail")
        row = conn.execute(
            "SELECT body FROM receipts WHERE task_id='task-1' AND slot='tests' AND attempt=1"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row["body"])["result"], "FAIL")

    def test_forged_receipt_is_not_approved(self) -> None:
        obs = self.report["forged_receipt"]
        self.assertNotEqual(obs["verdict"], "APPROVE")
        self.assertIn("invalid signature", _reasons_text(obs))
        tampered = obs["extra"]["tampered_field"]
        self.assertNotEqual(tampered["verdict"], "APPROVE")
        self.assertIn("invalid signature", "\n".join(tampered["reasons"]))

    def test_partial_static_coverage_is_not_approved(self) -> None:
        obs = self.report["partial_static_coverage"]
        self.assertNotEqual(obs["verdict"], "APPROVE")
        self.assertNotEqual(obs["extra"]["static_result"], "PASS")
        self.assertTrue(obs["reasons"])

    def test_missing_required_receipt_is_not_approved(self) -> None:
        obs = self.report["missing_required_receipt"]
        self.assertNotEqual(obs["verdict"], "APPROVE")
        self.assertIn("missing receipt for slot 'review'", _reasons_text(obs))

    def test_not_run_with_waiver_matrix(self) -> None:
        obs = self.report["not_run_with_waiver"]
        extra = obs["extra"]
        # No waiver: not approved.
        self.assertNotEqual(obs["verdict"], "APPROVE")
        self.assertNotEqual(obs["verdict"], "APPROVED_WITH_WAIVER")
        # Complete waiver for the current head.
        self.assertEqual(extra["with_waiver"]["verdict"], "APPROVED_WITH_WAIVER",
                         extra["with_waiver"]["reasons"])
        self.assertEqual(extra["with_waiver_record"], "WV-1")
        self.assertEqual(extra["with_waiver_approvals"], ["operator-1"])
        # Waiver bound to another head.
        self.assertNotEqual(extra["wrong_head_waiver"]["verdict"], "APPROVED_WITH_WAIVER")
        self.assertNotEqual(extra["wrong_head_waiver"]["verdict"], "APPROVE")
        self.assertIn("head", "\n".join(extra["wrong_head_waiver"]["reasons"]))

    def test_budget_exceeded_blocks(self) -> None:
        obs = self.report["budget_exceeded"]
        extra = obs["extra"]
        self.assertEqual(extra["remaining_after_first_charge"], 2)
        self.assertEqual(extra["charge_error_kind"], "budget")
        self.assertEqual(extra["marker"]["result"], "BLOCKED")
        self.assertEqual(extra["marker"]["reason"], "BUDGET_EXCEEDED")
        self.assertTrue(extra["event_chain_ok"])
        self.assertNotEqual(obs["verdict"], "APPROVE")
        conn = self._db("budget_exceeded")
        spent = conn.execute("SELECT spent FROM budget WHERE task_id='task-1'").fetchone()[0]
        self.assertEqual(spent, 3)  # the rejected charge was not applied
        kinds = [r[0] for r in conn.execute("SELECT kind FROM events")]
        self.assertIn("BUDGET_EXCEEDED", kinds)
        self.assertIn("BUDGET_BLOCKED", kinds)


class SliceCliTests(unittest.TestCase):
    def _run_cli(self, directory: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "tools.vst.slice", directory],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False,
        )

    def test_cli_exits_zero_and_prints_deterministic_sorted_json(self) -> None:
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            first = self._run_cli(os.path.join(one, "run"))
            second = self._run_cli(os.path.join(two, "run"))
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        parsed = json.loads(first.stdout)
        self.assertEqual(set(parsed), EXPECTED_SCENARIOS)
        self.assertEqual(first.stdout.strip(), json.dumps(parsed, sort_keys=True, indent=2))
        self.assertEqual(parsed["happy_path"]["verdict"], "APPROVE")

    def test_cli_without_directory_exits_two(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.vst.slice"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
