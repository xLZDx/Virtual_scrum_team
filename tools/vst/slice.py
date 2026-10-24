"""Synthetic vertical-slice harness (S1 epic E5).

Drives a synthetic story through the real Store, signing, contracts, gate and
(in one scenario) the real runner, with NO real project and NO external
service. Receipts are built directly by the fixture, except in the scenario
`real_run_and_sign` which runs one tiny allowed command (the current Python
interpreter printing two lines) through runner.run_and_sign. Everything else is
deterministic.

Keys (all bytes >= 32, pairwise distinct, enforced by SliceFixture): worker key
(signs worker receipts), supervisor key (signs SUPERVISOR_SLOT markers),
operator key (signs waivers) and the store event key.

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
from .contracts import (
    SUPERVISOR_SLOT,
    ContractError,
    derive_result,
    manifest_sha256,
    receipt_sha256,
    validate_task_manifest,
)
from .runner import run_and_sign
from .signing import WAIVER_LABEL, sign
from .store import MARKER_RESULTS, Store, StoreError

SYNTHETIC_HEAD = "1234567890abcdef1234567890abcdef12345678"
OTHER_HEAD = "b" * 40
WAIVER_WRONG_HEAD = "c" * 40


def _key(name: str) -> bytes:
    return hashlib.sha256(b"vst-slice-" + name.encode("ascii")).digest()


WORKER_KEY = _key("worker")
SUPERVISOR_KEY = _key("supervisor")
OPERATOR_KEY = _key("operator")
EVENT_KEY = _key("event")
WRONG_KEY = _key("wrong")
SLICE_KEY = WORKER_KEY  # backwards-compatible name for the worker key
ROLE_SHA256 = hashlib.sha256(b"synthetic-role").hexdigest()
STORY_ID = "story-1"
OWNER = "supervisor-1"
WORKER_ID = "runner-1"  # lease holder and receipt runner_id must be the same id
RUNNER_ID = WORKER_ID
SUPERVISOR_RUNNER = "supervisor-runner"
AUTHOR = "author-1"
REVIEWER = "reviewer-1"
EXPECTED_TEST_IDS = ("t1", "t2")
SYNTHETIC_ARGV = ["synthetic-test-run"]
REAL_ARGV = [sys.executable, "-c", "print('PASS t1'); print('PASS t2')"]
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
        "author_principal": AUTHOR,
        "required_tests": [
            {"slot": "tests", "test_id": test_id, "acceptance": ["AC-1"]}
            for test_id in EXPECTED_TEST_IDS
        ],
        "allowed_commands": [
            {"slot": "tests", "argv": list(SYNTHETIC_ARGV)},
            {"slot": "tests", "argv": list(REAL_ARGV)},
        ],
        "required_rules": [
            {"slot": "static", "rule_id": "R1"},
            {"slot": "static", "rule_id": "R2"},
        ],
        "timeout_sec": 600,
        "cost_cap": 100,
        "retry_cap": 1,
    }
    return validate_task_manifest(manifest)


def _parse_pass_lines(stdout: str) -> tuple[list[str], list[str], list[str]]:
    executed = [
        line[len("PASS "):].strip() for line in stdout.splitlines() if line.startswith("PASS ")
    ]
    return executed, [], []


class SliceFixture:
    """One synthetic story with a Store, a registered task, an owned epoch and builders."""

    def __init__(
        self,
        workdir: str,
        key: bytes,
        clock: Callable[[], float],
        *,
        supervisor_key: bytes = SUPERVISOR_KEY,
        operator_key: bytes = OPERATOR_KEY,
        event_key: bytes = EVENT_KEY,
    ) -> None:
        if len({bytes(key), bytes(supervisor_key), bytes(operator_key), bytes(event_key)}) != 4:
            raise ValueError("worker, supervisor, operator and event keys must be distinct")
        os.makedirs(workdir, exist_ok=True)
        self.workdir = workdir
        self.key = key
        self.supervisor_key = supervisor_key
        self.operator_key = operator_key
        self.clock = clock
        self.current_head = SYNTHETIC_HEAD
        self.task_id = "task-1"
        self.story_id = STORY_ID
        self.owner = OWNER
        self.runner_id = WORKER_ID
        self.manifest = build_synthetic_manifest(self.task_id, self.current_head)
        self.manifest_hash = manifest_sha256(self.manifest)
        self.store = Store(os.path.join(workdir, "state.db"), clock, event_key=event_key)
        self.store.init_slots(2)
        self.store.open_story(self.story_id, self.manifest["project_id"], 1)
        self.store.register_task(self.manifest)
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
        manifest_hash: str | None = None,
    ) -> dict:
        self._seq += 1
        body: dict[str, Any] = {
            "receipt_id": f"rc-{self.task_id}-{slot}-{attempt}-{self._seq}",
            "receipt_type": receipt_type,
            "task_id": self.task_id,
            "manifest_sha256": self.manifest_hash if manifest_hash is None else manifest_hash,
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
        manifest_hash: str | None = None,
    ) -> dict:
        """Signed TestRun receipt for slot 'tests'; expected ids are t1, t2."""
        return self._build(
            "TestRun", "tests", attempt, head, epoch, prev, key, result,
            {
                "expected_test_ids": list(EXPECTED_TEST_IDS),
                "executed_test_ids": list(executed_ids),
                "skipped_test_ids": list(skipped_ids),
                "xfail_test_ids": [],
                "commands": [{"argv": list(SYNTHETIC_ARGV), "exit_code": exit_code}],
                "covered_acceptance": ["AC-1"],
                "artifact_digests": {},
            },
            manifest_hash,
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

    def make_supervisor_receipt(
        self,
        reason: str,
        attempt: int = 1,
        prev: str | None = None,
        key: bytes | None = None,
    ) -> dict:
        """Signed SUPERVISOR_SLOT marker; signed with the SUPERVISOR key unless key is given."""
        return self._build(
            "Documentation", SUPERVISOR_SLOT, attempt, None, None, prev,
            self.supervisor_key if key is None else key, MARKER_RESULTS[reason],
            {
                "runner_id": SUPERVISOR_RUNNER,
                "check_description": reason,
                "covered_acceptance": [],
            },
        )

    def make_waiver(
        self,
        waived_slots: Any,
        waived_acceptance: Any,
        head: str | None = None,
        key: bytes | None = None,
    ) -> dict:
        """Operator-signed waiver bound to task, epoch, head and manifest hash."""
        epoch = self.store.current_epoch(self.story_id)
        body: dict[str, Any] = {
            "record_id": "WV-1",
            "operator": "operator-1",
            "task_id": self.task_id,
            "epoch": epoch,
            "head": self.current_head if head is None else head,
            "manifest_sha256": self.manifest_hash,
            "waived_slots": list(waived_slots),
            "waived_acceptance": list(waived_acceptance),
            "expires_epoch": epoch,
        }
        body["signature"] = sign(
            dict(body), self.operator_key if key is None else key, WAIVER_LABEL
        )
        return body

    # --------------------------------------------------------- store / gate

    def begin(self, attempt: int = 1, ttl_sec: float = 600) -> None:
        """Acquire the worker lease for this task (attempt n) at the fixture epoch."""
        self.store.acquire_lease(
            self.task_id, self.story_id, WORKER_ID, self.epoch, attempt, ttl_sec,
            supervisor_key=self.supervisor_key,
        )

    def end(self) -> None:
        """Release the worker lease."""
        self.store.release_lease(self.task_id, WORKER_ID, self.epoch)

    def append(self, receipt: dict) -> None:
        """Append a worker receipt (needs a live lease from begin())."""
        self.store.append_receipt(receipt, self.story_id, self.key)

    def append_good_set(self, skip: Any = ()) -> list[dict]:
        """Append PASS receipts for tests, static and review (except skipped slots)."""
        built = {
            "tests": self.make_test_receipt(1, EXPECTED_TEST_IDS),
            "static": self.make_static_receipt(),
            "review": self.make_review_receipt(REVIEWER, AUTHOR),
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
            supervisor_key=self.supervisor_key,
            operator_key=self.operator_key,
            waiver=waiver,
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


def _error_kind(call: Callable[[], Any]) -> str | None:
    """Run call; return the StoreError kind it raised, or None if it succeeded."""
    try:
        call()
    except StoreError as exc:
        return exc.kind
    return None


def _scenario_happy_path(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    fx.append_good_set()
    fx.end()
    decision = fx.gate()
    return _observe(decision, {
        "receipt_count": len(fx.store.receipts_for_task(fx.task_id)),
        "event_chain_ok": fx.store.verify_event_chain(),
    })


def _scenario_worker_death(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1, 60)
    clock.advance(120)
    written = fx.store.supervisor_reap_and_mark(fx.supervisor_key, SUPERVISOR_RUNNER)
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
    fx.begin(1, 600)
    clock.advance(4000)  # first owner's ownership expires
    new_epoch = fx.store.acquire_epoch(fx.story_id, "supervisor-2", 3600)
    late = fx.make_test_receipt(1, EXPECTED_TEST_IDS, epoch=old_epoch)
    extra: dict[str, Any] = {"old_epoch": old_epoch, "new_epoch": new_epoch}
    extra["append_error_kind"] = _error_kind(lambda: fx.append(late))
    extra["heartbeat_error_kind"] = _error_kind(
        lambda: fx.store.heartbeat(fx.task_id, WORKER_ID, old_epoch, 600)
    )
    extra["stored_count"] = len(fx.store.receipts_for_task(fx.task_id))
    decision = fx.gate(receipts=[late])
    return _observe(decision, extra)


def _scenario_stale_head(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    fx.append_good_set()
    fx.end()
    fx.current_head = OTHER_HEAD
    decision = fx.gate()
    return _observe(decision, {"receipt_head": SYNTHETIC_HEAD, "current_head": OTHER_HEAD})


def _scenario_retry_after_fail(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    first = fx.make_test_receipt(1, EXPECTED_TEST_IDS, exit_code=1)
    fx.append(first)
    fx.end()
    fx.begin(2)
    second = fx.make_test_receipt(2, EXPECTED_TEST_IDS, prev=receipt_sha256(first))
    fx.append(second)
    fx.append(fx.make_static_receipt())
    fx.append(fx.make_review_receipt(REVIEWER, AUTHOR))
    fx.end()
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
        fx.make_review_receipt(REVIEWER, AUTHOR),
    ]
    wrong_key = fx.make_test_receipt(1, EXPECTED_TEST_IDS, key=WRONG_KEY)
    tampered = copy.deepcopy(fx.make_test_receipt(1, EXPECTED_TEST_IDS))
    tampered["resolved_model"] = "tampered-model"  # changed after signing
    decision = fx.gate(receipts=[wrong_key] + others)
    tampered_decision = fx.gate(receipts=[tampered] + others)
    return _observe(decision, {"tampered_field": _brief(tampered_decision)})


def _scenario_partial_static(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    fx.append(fx.make_test_receipt(1, EXPECTED_TEST_IDS))
    fx.append(fx.make_static_receipt(coverage="PARTIAL", unsupported=["R3"]))
    fx.append(fx.make_review_receipt(REVIEWER, AUTHOR))
    fx.end()
    decision = fx.gate()
    return _observe(decision, {"static_result": fx.store.receipts_for_task(fx.task_id)[1]["result"]})


def _scenario_missing_required(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    fx.append_good_set(skip=("review",))
    fx.end()
    decision = fx.gate()
    return _observe(decision, {"missing_slot": "review"})


def _scenario_not_run_with_waiver(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    fx.append(fx.make_test_receipt(1, (), result="NOT_RUN"))
    fx.append(fx.make_static_receipt())
    fx.append(fx.make_review_receipt(REVIEWER, AUTHOR))
    fx.end()
    plain = fx.gate()
    waived = fx.gate(waiver=fx.make_waiver(["tests"], plain["acceptance_unmet"]))
    wrong_head = fx.gate(
        waiver=fx.make_waiver(["tests"], plain["acceptance_unmet"], head=WAIVER_WRONG_HEAD)
    )
    forged = fx.gate(
        waiver=fx.make_waiver(["tests"], plain["acceptance_unmet"], key=fx.key)
    )
    return _observe(plain, {
        "with_waiver": _brief(waived),
        "with_waiver_record": waived["waiver_record"],
        "with_waiver_approvals": list(waived["human_approvals"]),
        "wrong_head_waiver": _brief(wrong_head),
        "waiver_signed_with_worker_key": _brief(forged),
    })


def _scenario_budget_exceeded(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.store.set_budget(fx.task_id, 5)
    remaining = fx.store.charge(fx.task_id, 3)
    extra: dict[str, Any] = {"remaining_after_first_charge": remaining}
    extra["charge_error_kind"] = _error_kind(lambda: fx.store.charge(fx.task_id, 3))
    receipt = fx.store.mark_budget_exceeded(fx.task_id, fx.supervisor_key, SUPERVISOR_RUNNER)
    again = fx.store.mark_budget_exceeded(fx.task_id, fx.supervisor_key, SUPERVISOR_RUNNER)
    extra["marker"] = {
        "slot": receipt["slot"],
        "result": receipt["result"],
        "reason": receipt["check_description"],
    }
    extra["marker_idempotent"] = again["receipt_id"] == receipt["receipt_id"]
    extra["marker_count"] = sum(
        1 for r in fx.store.receipts_for_task(fx.task_id) if r["slot"] == SUPERVISOR_SLOT
    )
    extra["event_chain_ok"] = fx.store.verify_event_chain()
    decision = fx.gate()
    return _observe(decision, extra)


def _scenario_real_run_and_sign(fx: SliceFixture, clock: FakeClock) -> dict:
    run_dir = os.path.join(fx.workdir, "run")
    os.makedirs(run_dir, exist_ok=True)
    common = dict(
        manifest=fx.manifest, slot="tests", attempt=1, epoch=fx.epoch,
        candidate_head=fx.current_head, resolved_model="synthetic-model",
        invocation_id="inv-real-1", runner_id=WORKER_ID, key=fx.key,
        test_result_parser=_parse_pass_lines, covered_acceptance=["AC-1"],
        artifact_paths=[], prev_receipt_sha256=None, cwd=run_dir,
        created_at=CREATED_AT, timeout_sec=60, deadline_sec=120,
    )
    extra: dict[str, Any] = {}
    refused_command = refused_ids = False
    try:
        run_and_sign(
            commands=[[sys.executable, "-c", "print('not allowed')"]],
            expected_test_ids=list(EXPECTED_TEST_IDS), **common,
        )
    except ContractError:
        refused_command = True
    try:
        run_and_sign(commands=[list(REAL_ARGV)], expected_test_ids=["t1"], **common)
    except ContractError:
        refused_ids = True
    extra["refused_unallowed_command"] = refused_command
    extra["refused_wrong_expected_ids"] = refused_ids
    report: dict = {}
    receipt = run_and_sign(
        commands=[list(REAL_ARGV)], expected_test_ids=list(EXPECTED_TEST_IDS),
        report=report, **common,
    )
    fx.begin(1)
    fx.append(receipt)
    fx.append(fx.make_static_receipt())
    fx.append(fx.make_review_receipt(REVIEWER, AUTHOR))
    fx.end()
    extra["receipt_result"] = receipt["result"]
    extra["exit_code"] = receipt["commands"][0]["exit_code"]
    extra["executed"] = list(receipt["executed_test_ids"])
    extra["bound_to_manifest"] = receipt["manifest_sha256"] == fx.manifest_hash
    extra["stdout_truncated"] = report["commands"][0]["stdout_truncated"]
    decision = fx.gate()
    return _observe(decision, extra)


def _scenario_retry_exhausted(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    first = fx.make_test_receipt(1, EXPECTED_TEST_IDS, exit_code=1)
    fx.append(first)
    fx.end()
    fx.begin(2)
    second = fx.make_test_receipt(2, EXPECTED_TEST_IDS, exit_code=1, prev=receipt_sha256(first))
    fx.append(second)
    fx.end()
    kinds = [_error_kind(lambda: fx.begin(3)), _error_kind(lambda: fx.begin(3))]
    stored = fx.store.receipts_for_task(fx.task_id)
    markers = [r for r in stored if r["slot"] == SUPERVISOR_SLOT]
    decision = fx.gate()
    return _observe(decision, {
        "retry_cap": fx.manifest["retry_cap"],
        "third_attempt_error_kinds": kinds,
        "markers": [r["check_description"] for r in markers],
        "marker_results": [r["result"] for r in markers],
    })


def _scenario_forged_supervisor(fx: SliceFixture, clock: FakeClock) -> dict:
    forged = fx.make_supervisor_receipt("WORKER_LOST", key=fx.key)  # worker key, not supervisor
    genuine = fx.make_supervisor_receipt("WORKER_LOST")
    good = [
        fx.make_test_receipt(1, EXPECTED_TEST_IDS),
        fx.make_static_receipt(),
        fx.make_review_receipt(REVIEWER, AUTHOR),
    ]
    extra: dict[str, Any] = {
        "store_supervisor_path_kind": _error_kind(
            lambda: fx.store.append_supervisor_receipt(
                forged, fx.story_id, supervisor_key=fx.supervisor_key
            )
        ),
        "store_worker_path_kind": _error_kind(lambda: fx.append(forged)),
        "genuine_via_worker_path_kind": _error_kind(lambda: fx.append(genuine)),
        "stored_count": len(fx.store.receipts_for_task(fx.task_id)),
    }
    decision = fx.gate(receipts=good + [forged])
    return _observe(decision, extra)


def _scenario_manifest_swap(fx: SliceFixture, clock: FakeClock) -> dict:
    swapped = copy.deepcopy(fx.manifest)
    swapped["timeout_sec"] += 1  # a different manifest, hence a different hash
    other_hash = manifest_sha256(swapped)
    receipt = fx.make_test_receipt(1, EXPECTED_TEST_IDS, manifest_hash=other_hash)
    fx.begin(1)
    extra: dict[str, Any] = {
        "hashes_differ": other_hash != fx.manifest_hash,
        "store_append_kind": _error_kind(lambda: fx.append(receipt)),
        "register_other_manifest_kind": _error_kind(lambda: fx.store.register_task(swapped)),
        "stored_count": len(fx.store.receipts_for_task(fx.task_id)),
    }
    fx.end()
    others = [
        fx.make_static_receipt(),
        fx.make_review_receipt(REVIEWER, AUTHOR),
    ]
    decision = fx.gate(receipts=[receipt] + others)
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
    ("real_run_and_sign", _scenario_real_run_and_sign),
    ("retry_exhausted", _scenario_retry_exhausted),
    ("forged_supervisor_receipt", _scenario_forged_supervisor),
    ("manifest_swap", _scenario_manifest_swap),
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
