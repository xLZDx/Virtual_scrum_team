"""Synthetic vertical-slice harness (S1 epic E5).

Drives a synthetic story through the real Store, signing, contracts and gate
with NO real project, NO external service and NO process spawning. Receipts are
built directly (the runner is not used), so every scenario is deterministic.

Public API: build_synthetic_manifest, SliceFixture, FakeClock, run_scenarios.
CLI: python -m tools.vst.slice <empty-or-new-directory>  (prints a JSON report).

Standard library only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from typing import Any, Callable

from . import gate as gate_module
from .contracts import derive_result, receipt_sha256, validate_task_manifest
from .signing import sign
from .store import Store, StoreError

SYNTHETIC_HEAD = "1234567890abcdef1234567890abcdef12345678"
OTHER_HEAD = "b" * 40
WAIVER_WRONG_HEAD = "c" * 40
SLICE_KEY = b"synthetic-slice-key"
WRONG_KEY = b"synthetic-wrong-key"
ROLE_SHA256 = hashlib.sha256(b"synthetic-role").hexdigest()
STORY_ID = "story-1"
OWNER = "supervisor-1"
RUNNER_ID = "runner-1"
WORKER_ID = "worker-1"
EXPECTED_TEST_IDS = ("t1", "t2")
CLOCK_START = 1_000_000.0
CREATED_AT = "2026-10-24T00:00:00+00:00"


class FakeClock:
    """Controllable clock: call it for the time, advance() to move it."""

    def __init__(self, start: float = CLOCK_START) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += float(seconds)


def build_synthetic_manifest(task_id: str, base_head: str) -> dict:
    """A valid TaskManifest with the slots tests, static and review."""
    manifest = {
        "task_id": task_id,
        "project_id": "synthetic-project",
        "phase": 1,
        "story_id": STORY_ID,
        "base_head": base_head,
        "scope": ["src/synthetic.py"],
        "forbidden_actions": [],
        "owner_role": "implementation-engineer",
        "role_sha256": ROLE_SHA256,
        "skills": [],
        "model_policy": "sonnet-5.5-medium",
        "tools": [],
        "acceptance": ["AC-1", "AC-2"],
        "required_receipts": [
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "static", "receipt_type": "StaticAnalysis"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        "timeout_sec": 600,
        "cost_cap": 100,
        "retry_cap": 1,
    }
    return validate_task_manifest(manifest)


class SliceFixture:
    """One synthetic story with a Store, an owned epoch and receipt builders."""

    def __init__(self, workdir: str, key: bytes, clock: Callable[[], float]) -> None:
        os.makedirs(workdir, exist_ok=True)
        self.workdir = workdir
        self.key = key
        self.clock = clock
        self.current_head = SYNTHETIC_HEAD
        self.task_id = "task-1"
        self.story_id = STORY_ID
        self.owner = OWNER
        self.runner_id = RUNNER_ID
        self.manifest = build_synthetic_manifest(self.task_id, self.current_head)
        self.store = Store(os.path.join(workdir, "state.db"), clock)
        self.store.init_slots(2)
        self.store.open_story(self.story_id, self.manifest["project_id"], 1)
        self.epoch = self.store.acquire_epoch(self.story_id, self.owner, 3600)
        self._seq = 0

    def close(self) -> None:
        self.store.close()

    # ------------------------------------------------------------- builders

    def _build(
        self,
        receipt_type: str,
        slot: str,
        attempt: int,
        head: str | None,
        epoch: int | None,
        prev: str | None,
        key: bytes | None,
        result: str | None,
        extra: dict,
    ) -> dict:
        self._seq += 1
        body: dict[str, Any] = {
            "receipt_id": f"rc-{self.task_id}-{slot}-{attempt}-{self._seq}",
            "receipt_type": receipt_type,
            "task_id": self.task_id,
            "slot": slot,
            "attempt": attempt,
            "prev_receipt_sha256": prev,
            "candidate_head": self.current_head if head is None else head,
            "epoch": self.epoch if epoch is None else epoch,
            "runner_id": self.runner_id,
            "role_sha256": ROLE_SHA256,
            "resolved_model": "synthetic-model",
            "invocation_id": f"inv-{slot}-{attempt}-{self._seq}",
            "result": "PASS",
            "created_at": CREATED_AT,
        }
        body.update(extra)
        body["result"] = result if result is not None else derive_result(body)
        body["signature"] = sign(dict(body), self.key if key is None else key)
        return body

    def make_test_receipt(
        self,
        attempt: int,
        executed_ids: Any,
        skipped_ids: Any = (),
        exit_code: int = 0,
        head: str | None = None,
        epoch: int | None = None,
        prev: str | None = None,
        key: bytes | None = None,
        result: str | None = None,
    ) -> dict:
        """Signed TestRun receipt for slot 'tests'; expected ids are t1, t2."""
        return self._build(
            "TestRun", "tests", attempt, head, epoch, prev, key, result,
            {
                "expected_test_ids": list(EXPECTED_TEST_IDS),
                "executed_test_ids": list(executed_ids),
                "skipped_test_ids": list(skipped_ids),
                "xfail_test_ids": [],
                "commands": [{"argv": ["synthetic-test-run"], "exit_code": exit_code}],
                "covered_acceptance": ["AC-1"],
            },
        )

    def make_static_receipt(
        self,
        coverage: str = "FULL",
        unsupported: Any = (),
        attempt: int = 1,
        head: str | None = None,
        epoch: int | None = None,
        prev: str | None = None,
        key: bytes | None = None,
        result: str | None = None,
    ) -> dict:
        """Signed StaticAnalysis receipt for slot 'static'."""
        return self._build(
            "StaticAnalysis", "static", attempt, head, epoch, prev, key, result,
            {
                "coverage": coverage,
                "covered_rules": ["R1", "R2"],
                "unsupported_rules": list(unsupported),
                "covered_acceptance": ["AC-2"],
            },
        )

    def make_review_receipt(
        self,
        reviewer: str,
        author: str,
        verdict: str = "APPROVE",
        attempt: int = 1,
        head: str | None = None,
        epoch: int | None = None,
        prev: str | None = None,
        key: bytes | None = None,
        result: str | None = None,
    ) -> dict:
        """Signed IndependentReview receipt for slot 'review'."""
        return self._build(
            "IndependentReview", "review", attempt, head, epoch, prev, key, result,
            {
                "reviewer_principal": reviewer,
                "author_principal": author,
                "covered_acceptance": ["AC-1", "AC-2"],
                "findings": [],
                "signed_verdict": verdict,
            },
        )

    # ----------------------------------------------------------- store / gate

    def append(self, receipt: dict) -> None:
        """Append a receipt to the store for this fixture's story."""
        self.store.append_receipt(receipt, self.story_id)

    def append_good_set(self, skip: Any = ()) -> list[dict]:
        """Append PASS receipts for tests, static and review (except skipped slots)."""
        built = {
            "tests": self.make_test_receipt(1, EXPECTED_TEST_IDS),
            "static": self.make_static_receipt(),
            "review": self.make_review_receipt("reviewer-1", "author-1"),
        }
        appended = []
        for slot in ("tests", "static", "review"):
            if slot not in skip:
                self.append(built[slot])
                appended.append(built[slot])
        return appended

    def gate(self, receipts: list[dict] | None = None, waiver: dict | None = None) -> dict:
        """gate.evaluate over given receipts or those read from the store."""
        listed = self.store.receipts_for_task(self.task_id) if receipts is None else receipts
        return gate_module.evaluate(
            self.manifest,
            listed,
            self.current_head,
            self.store.current_epoch(self.story_id),
            self.key,
            waiver,
        )


# ------------------------------------------------------------------ scenarios


def _observe(decision: dict, extra: dict | None = None) -> dict:
    return {
        "verdict": decision["verdict"],
        "reasons": list(decision["reasons"]),
        "unresolved_findings": list(decision["unresolved_findings"]),
        "extra": {} if extra is None else extra,
    }


def _brief(decision: dict) -> dict:
    return {"verdict": decision["verdict"], "reasons": list(decision["reasons"])}


def _scenario_happy_path(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.store.acquire_lease(fx.task_id, fx.story_id, WORKER_ID, fx.epoch, 1, 600)
    fx.append_good_set()
    fx.store.release_lease(fx.task_id, WORKER_ID, fx.epoch)
    decision = fx.gate()
    return _observe(decision, {
        "receipt_count": len(fx.store.receipts_for_task(fx.task_id)),
        "event_chain_ok": fx.store.verify_event_chain(),
    })


def _scenario_worker_death(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.store.acquire_lease(fx.task_id, fx.story_id, WORKER_ID, fx.epoch, 1, 60)
    clock.advance(120)
    written = fx.store.supervisor_reap_and_mark(lambda _task: fx.manifest, fx.key, RUNNER_ID)
    stored = fx.store.receipts_for_task(fx.task_id)
    decision = fx.gate()
    return _observe(decision, {
        "written": [
            {"slot": r["slot"], "result": r["result"], "reason": r["check_description"]}
            for r in written
        ],
        "stored": [
            {"slot": r["slot"], "attempt": r["attempt"], "result": r["result"],
             "reason": r["check_description"]}
            for r in stored
        ],
    })


def _scenario_zombie_late_write(fx: SliceFixture, clock: FakeClock) -> dict:
    old_epoch = fx.epoch
    fx.store.acquire_lease(fx.task_id, fx.story_id, WORKER_ID, old_epoch, 1, 600)
    clock.advance(4000)  # first owner's ownership expires
    new_epoch = fx.store.acquire_epoch(fx.story_id, "supervisor-2", 3600)
    late = fx.make_test_receipt(1, EXPECTED_TEST_IDS, epoch=old_epoch)
    extra: dict[str, Any] = {"old_epoch": old_epoch, "new_epoch": new_epoch}
    try:
        fx.append(late)
        extra["append_error_kind"] = None
    except StoreError as exc:
        extra["append_error_kind"] = exc.kind
    try:
        fx.store.heartbeat(fx.task_id, WORKER_ID, old_epoch, 600)
        extra["heartbeat_error_kind"] = None
    except StoreError as exc:
        extra["heartbeat_error_kind"] = exc.kind
    extra["stored_count"] = len(fx.store.receipts_for_task(fx.task_id))
    decision = fx.gate(receipts=[late])
    return _observe(decision, extra)


def _scenario_stale_head(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.append_good_set()
    fx.current_head = OTHER_HEAD
    decision = fx.gate()
    return _observe(decision, {"receipt_head": SYNTHETIC_HEAD, "current_head": OTHER_HEAD})


def _scenario_retry_after_fail(fx: SliceFixture, clock: FakeClock) -> dict:
    first = fx.make_test_receipt(1, EXPECTED_TEST_IDS, exit_code=1)
    fx.append(first)
    second = fx.make_test_receipt(2, EXPECTED_TEST_IDS, prev=receipt_sha256(first))
    fx.append(second)
    fx.append(fx.make_static_receipt())
    fx.append(fx.make_review_receipt("reviewer-1", "author-1"))
    decision = fx.gate()
    return _observe(decision, {
        "test_attempts": [
            {"attempt": r["attempt"], "result": r["result"]}
            for r in fx.store.receipts_for_task(fx.task_id)
            if r["slot"] == "tests"
        ],
    })


def _scenario_forged_receipt(fx: SliceFixture, clock: FakeClock) -> dict:
    others = [
        fx.make_static_receipt(),
        fx.make_review_receipt("reviewer-1", "author-1"),
    ]
    wrong_key = fx.make_test_receipt(1, EXPECTED_TEST_IDS, key=WRONG_KEY)
    tampered = copy.deepcopy(fx.make_test_receipt(1, EXPECTED_TEST_IDS))
    tampered["resolved_model"] = "tampered-model"  # changed after signing
    decision = fx.gate(receipts=[wrong_key] + others)
    tampered_decision = fx.gate(receipts=[tampered] + others)
    return _observe(decision, {"tampered_field": _brief(tampered_decision)})


def _scenario_partial_static(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.append(fx.make_test_receipt(1, EXPECTED_TEST_IDS))
    fx.append(fx.make_static_receipt(coverage="PARTIAL", unsupported=["R3"]))
    fx.append(fx.make_review_receipt("reviewer-1", "author-1"))
    decision = fx.gate()
    return _observe(decision, {"static_result": fx.store.receipts_for_task(fx.task_id)[1]["result"]})


def _scenario_missing_required(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.append_good_set(skip=("review",))
    decision = fx.gate()
    return _observe(decision, {"missing_slot": "review"})


def _scenario_not_run_with_waiver(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.append(fx.make_test_receipt(1, (), result="NOT_RUN"))
    fx.append(fx.make_static_receipt())
    fx.append(fx.make_review_receipt("reviewer-1", "author-1"))
    plain = fx.gate()

    def waiver(head: str) -> dict:
        return {
            "record_id": "WV-1",
            "operator": "operator-1",
            "waived_slots": ["tests"],
            "waived_acceptance": list(plain["acceptance_unmet"]),
            "head": head,
            "expires_epoch_or_date": "2026-12-31",
        }

    waived = fx.gate(waiver=waiver(fx.current_head))
    wrong_head = fx.gate(waiver=waiver(WAIVER_WRONG_HEAD))
    return _observe(plain, {
        "with_waiver": _brief(waived),
        "with_waiver_record": waived["waiver_record"],
        "with_waiver_approvals": list(waived["human_approvals"]),
        "wrong_head_waiver": _brief(wrong_head),
    })


def _scenario_budget_exceeded(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.store.set_budget(fx.task_id, 5)
    remaining = fx.store.charge(fx.task_id, 3)
    extra: dict[str, Any] = {"remaining_after_first_charge": remaining}
    try:
        fx.store.charge(fx.task_id, 3)
        extra["charge_error_kind"] = None
    except StoreError as exc:
        extra["charge_error_kind"] = exc.kind
    receipt = fx.store.mark_budget_exceeded(
        fx.task_id, fx.story_id, fx.manifest, fx.key, RUNNER_ID
    )
    extra["marker"] = {
        "slot": receipt["slot"],
        "result": receipt["result"],
        "reason": receipt["check_description"],
    }
    extra["event_chain_ok"] = fx.store.verify_event_chain()
    decision = fx.gate()
    return _observe(decision, extra)


SCENARIOS: tuple[tuple[str, Callable[[SliceFixture, FakeClock], dict]], ...] = (
    ("happy_path", _scenario_happy_path),
    ("worker_death_before_receipt", _scenario_worker_death),
    ("zombie_late_write", _scenario_zombie_late_write),
    ("stale_head", _scenario_stale_head),
    ("retry_after_fail", _scenario_retry_after_fail),
    ("forged_receipt", _scenario_forged_receipt),
    ("partial_static_coverage", _scenario_partial_static),
    ("missing_required_receipt", _scenario_missing_required),
    ("not_run_with_waiver", _scenario_not_run_with_waiver),
    ("budget_exceeded", _scenario_budget_exceeded),
)


def run_scenarios(workdir: str) -> dict[str, dict]:
    """Run every scenario in its own subdirectory of workdir; return observations."""
    os.makedirs(workdir, exist_ok=True)
    report: dict[str, dict] = {}
    for name, scenario in SCENARIOS:
        clock = FakeClock()
        fixture = SliceFixture(os.path.join(workdir, name), SLICE_KEY, clock)
        try:
            report[name] = scenario(fixture, clock)
        finally:
            fixture.close()
    return report


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m tools.vst.slice <temporary-directory>", file=sys.stderr)
        return 2
    report = run_scenarios(argv[1])
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
