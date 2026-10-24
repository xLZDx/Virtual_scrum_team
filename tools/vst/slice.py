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
import sqlite3
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
from .store import MARKER_RESULTS, SUPERVISOR_RECEIPT_PREFIX, Store, StoreError

SYNTHETIC_HEAD = "1234567890abcdef1234567890abcdef12345678"
OTHER_HEAD = "b" * 40
THIRD_HEAD = "d" * 40
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


def build_synthetic_manifest(task_id: str, base_head: str, retry_cap: int = 1) -> dict:
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
        "retry_cap": retry_cap,
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
        retry_cap: int = 1,
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
        self.manifest = build_synthetic_manifest(self.task_id, self.current_head, retry_cap)
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
    remaining = fx.store.charge(fx.task_id, 3, supervisor_key=fx.supervisor_key)
    extra: dict[str, Any] = {"remaining_after_first_charge": remaining}
    extra["charge_error_kind"] = _error_kind(
        lambda: fx.store.charge(
            fx.task_id, 3, supervisor_key=fx.supervisor_key, runner_id=SUPERVISOR_RUNNER
        )
    )
    extra["marker_written_by_charge"] = any(
        r["slot"] == SUPERVISOR_SLOT and r["check_description"] == "BUDGET_EXCEEDED"
        for r in fx.store.receipts_for_task(fx.task_id)
    )
    extra["begin_after_exceeded_kind"] = _error_kind(lambda: fx.begin(1))
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


def _scenario_retry_across_head_change(fx: SliceFixture, clock: FakeClock) -> dict:
    head_a = fx.current_head
    fx.begin(1)
    first = fx.make_test_receipt(1, EXPECTED_TEST_IDS, exit_code=1, head=head_a)
    fx.append(first)
    fx.end()
    fx.current_head = OTHER_HEAD  # the fix lands on a new commit
    fx.begin(2)
    second = fx.make_test_receipt(2, EXPECTED_TEST_IDS, prev=receipt_sha256(first))
    fx.append(second)
    fx.append(fx.make_static_receipt())
    fx.append(fx.make_review_receipt(REVIEWER, AUTHOR))
    fx.end()
    decision = fx.gate()
    return _observe(decision, {
        "failed_head": head_a,
        "passing_head": OTHER_HEAD,
        "failed_attempts": fx.store.failed_attempts(fx.task_id),
        "test_attempts": [
            {"attempt": r["attempt"], "result": r["result"], "head": r["candidate_head"]}
            for r in fx.store.receipts_for_task(fx.task_id)
            if r["slot"] == "tests"
        ],
    })


def _scenario_worker_lost_then_new_head(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1, 60)
    clock.advance(120)  # the first worker dies before writing any receipt
    written = fx.store.supervisor_reap_and_mark(fx.supervisor_key, SUPERVISOR_RUNNER)
    fx.current_head = OTHER_HEAD
    fx.begin(2)
    fx.append_good_set()
    fx.end()
    decision = fx.gate()
    return _observe(decision, {
        "markers": [
            {"reason": r["check_description"], "head": r["candidate_head"]} for r in written
        ],
        "passing_head": OTHER_HEAD,
        "failed_attempts": fx.store.failed_attempts(fx.task_id),
    })


def _scenario_budget_exact_cap(fx: SliceFixture, clock: FakeClock) -> dict:
    fx.begin(1)
    fx.store.set_budget(fx.task_id, 5)
    remaining = fx.store.charge(fx.task_id, 5, supervisor_key=fx.supervisor_key)  # exactly the cap
    extra: dict[str, Any] = {"remaining_after_exact_charge": remaining}
    extra["final_receipts_error_kind"] = _error_kind(fx.append_good_set)
    fx.end()
    decision = fx.gate()  # evaluated before any further lease call
    extra["stored_receipts"] = len(fx.store.receipts_for_task(fx.task_id))
    # Spent == cap does not block: the first lease call is granted, the repeat is refused
    # only because that lease is live (kind 'lease'), never as a budget block.
    extra["acquire_lease_error_kinds"] = [
        _error_kind(lambda: fx.begin(2)),
        _error_kind(lambda: fx.begin(2)),
    ]
    fx.end()
    extra["budget_markers"] = _budget_marker_count(fx)
    extra["event_chain_ok"] = fx.store.verify_event_chain()
    extra["gate_after_lease_calls"] = _brief(fx.gate())
    return _observe(decision, extra)


def _budget_marker_count(fx: SliceFixture) -> int:
    return sum(
        1
        for r in fx.store.receipts_for_task(fx.task_id)
        if r["slot"] == SUPERVISOR_SLOT and r["check_description"] == "BUDGET_EXCEEDED"
    )


def _next_pass_set(fx: SliceFixture, attempt: int) -> None:
    """Append a PASS set as attempt `attempt` of every slot, chained to the previous one."""
    last: dict[str, str] = {}
    for r in fx.store.receipts_for_task(fx.task_id):
        if r["slot"] != SUPERVISOR_SLOT:
            last[r["slot"]] = receipt_sha256(r)
    fx.append(fx.make_test_receipt(attempt, EXPECTED_TEST_IDS, prev=last.get("tests")))
    fx.append(fx.make_static_receipt(attempt=attempt, prev=last.get("static")))
    fx.append(fx.make_review_receipt(REVIEWER, AUTHOR, attempt=attempt, prev=last.get("review")))


def _scenario_takeover_after_full_pass_set(fx: SliceFixture, clock: FakeClock) -> dict:
    # Runs on a fixture with retry_cap 0 (see _SCENARIO_RETRY_CAP): one attempt per
    # slot per epoch. A takeover after a complete PASS set must stay satisfiable.
    extra: dict[str, Any] = {"retry_cap": fx.manifest["retry_cap"]}
    fx.begin(1)
    fx.append_good_set()
    fx.end()
    extra["verdict_epoch_1"] = _brief(fx.gate())["verdict"]
    for round_no in (2, 3):
        fx.store.release_epoch(fx.story_id, fx.owner)
        fx.owner = f"supervisor-{round_no}"
        fx.epoch = fx.store.acquire_epoch(fx.story_id, fx.owner, 3600)
        fx.begin(round_no)
        _next_pass_set(fx, round_no)
        fx.end()
        extra[f"verdict_takeover_{round_no - 1}"] = _brief(fx.gate())["verdict"]
    extra["final_epoch"] = fx.epoch
    extra["failed_attempts"] = fx.store.failed_attempts(fx.task_id)
    extra["attempts_per_slot"] = {
        slot: [r["attempt"] for r in fx.store.receipts_for_task(fx.task_id) if r["slot"] == slot]
        for slot in ("tests", "static", "review")
    }
    return _observe(fx.gate(), extra)


def _scenario_takeover_does_not_exhaust_cap(fx: SliceFixture, clock: FakeClock) -> dict:
    takeovers = 3  # more than retry_cap + 1 = 2 fenced leases, none wrote a receipt
    for round_no in range(1, takeovers + 1):
        fx.begin(round_no)
        fx.store.release_epoch(fx.story_id, fx.owner)
        fx.owner = f"supervisor-{round_no + 1}"
        fx.epoch = fx.store.acquire_epoch(fx.story_id, fx.owner, 3600)
        fx.store.supervisor_reap_and_mark(fx.supervisor_key, SUPERVISOR_RUNNER)
    extra: dict[str, Any] = {
        "retry_cap": fx.manifest["retry_cap"],
        "takeovers": takeovers,
        "failed_attempts_after_takeovers": fx.store.failed_attempts(fx.task_id),
    }
    begin_kind = _error_kind(lambda: fx.begin(takeovers + 1))
    extra["next_begin_error_kind"] = begin_kind
    if begin_kind is None:
        fx.append_good_set()
        fx.end()
    extra["final_epoch"] = fx.epoch
    decision = fx.gate()
    return _observe(decision, extra)


def _chain_tail(fx: SliceFixture) -> dict[str, str]:
    """Hash of the newest stored worker receipt per slot (the next prev link)."""
    tails: dict[str, str] = {}
    for r in fx.store.receipts_for_task(fx.task_id):
        if r["slot"] != SUPERVISOR_SLOT:
            tails[r["slot"]] = receipt_sha256(r)
    return tails


def _scenario_retry_across_three_heads(fx: SliceFixture, clock: FakeClock) -> dict:
    # retry_cap 1 (so retry_cap + 1 = 2 non-PASS receipts per slot per epoch) in ONE epoch:
    #   h1: tests FAIL, static PASS, review PASS
    #   h2: tests PASS, static INCONCLUSIVE (partial coverage), review PASS
    #   h3: tests PASS, static PASS, review PASS
    # At h3 every slot already holds two receipts of the epoch, but at most one is non-PASS,
    # so the per-epoch bound (non-PASS receipts only) must not refuse any of them.
    extra: dict[str, Any] = {"retry_cap": fx.manifest["retry_cap"]}
    fx.current_head = SYNTHETIC_HEAD
    fx.begin(1)
    tests1 = fx.make_test_receipt(1, EXPECTED_TEST_IDS, exit_code=1)
    static1 = fx.make_static_receipt()
    review1 = fx.make_review_receipt(REVIEWER, AUTHOR)
    extra["h1_append_error_kinds"] = [_error_kind(lambda r=r: fx.append(r)) for r in (tests1, static1, review1)]
    fx.end()
    extra["h1_verdict"] = _brief(fx.gate())["verdict"]

    fx.current_head = OTHER_HEAD
    fx.begin(2)
    tests2 = fx.make_test_receipt(2, EXPECTED_TEST_IDS, prev=receipt_sha256(tests1))
    static2 = fx.make_static_receipt(
        coverage="PARTIAL", unsupported=["R3"], attempt=2, prev=receipt_sha256(static1)
    )
    review2 = fx.make_review_receipt(REVIEWER, AUTHOR, attempt=2, prev=receipt_sha256(review1))
    extra["h2_append_error_kinds"] = [_error_kind(lambda r=r: fx.append(r)) for r in (tests2, static2, review2)]
    fx.end()
    extra["h2_results"] = [tests2["result"], static2["result"], review2["result"]]
    extra["h2_verdict"] = _brief(fx.gate())["verdict"]
    extra["failed_attempts_after_h2"] = fx.store.failed_attempts(fx.task_id)

    fx.current_head = THIRD_HEAD
    extra["h3_lease_error_kind"] = _error_kind(lambda: fx.begin(3))
    tails = _chain_tail(fx)
    tests3 = fx.make_test_receipt(3, EXPECTED_TEST_IDS, prev=tails["tests"])
    static3 = fx.make_static_receipt(attempt=3, prev=tails["static"])
    review3 = fx.make_review_receipt(REVIEWER, AUTHOR, attempt=3, prev=tails["review"])
    extra["h3_append_error_kinds"] = [_error_kind(lambda r=r: fx.append(r)) for r in (tests3, static3, review3)]
    fx.end()
    extra["receipts_per_slot"] = {
        slot: [
            {"attempt": r["attempt"], "result": r["result"], "head": r["candidate_head"]}
            for r in fx.store.receipts_for_task(fx.task_id)
            if r["slot"] == slot
        ]
        for slot in ("tests", "static", "review")
    }
    extra["failed_attempts"] = fx.store.failed_attempts(fx.task_id)
    extra["terminal_markers"] = sum(
        1 for r in fx.store.receipts_for_task(fx.task_id) if r["slot"] == SUPERVISOR_SLOT
    )
    return _observe(fx.gate(), extra)


def _scenario_exact_cap_reattest_keeps_approve(fx: SliceFixture, clock: FakeClock) -> dict:
    # The worker spends EXACTLY its cap and records a full PASS set. No later lease call,
    # repeated or after an epoch takeover, may commit a terminal marker or turn the APPROVE
    # into a block; a fresh PASS set at the new head and epoch approves again.
    extra: dict[str, Any] = {}
    fx.begin(1)
    fx.store.set_budget(fx.task_id, 5)
    extra["remaining_after_exact_charge"] = fx.store.charge(
        fx.task_id, 5, supervisor_key=fx.supervisor_key
    )
    fx.append_good_set()
    fx.end()
    extra["verdict_at_exact_cap"] = _brief(fx.gate())["verdict"]

    # Repeated lease calls at spent == cap: the first is granted, the second is refused
    # because that lease is live (kind 'lease'), never as a budget block.
    extra["repeated_acquire_error_kinds"] = [
        _error_kind(lambda: fx.begin(2)),
        _error_kind(lambda: fx.begin(2)),
    ]
    extra["markers_after_repeated_acquire"] = _budget_marker_count(fx)
    extra["verdict_with_live_lease"] = _brief(fx.gate())["verdict"]

    # Epoch takeover while that lease is live: it is fenced and marked WORKER_LOST.
    fx.store.release_epoch(fx.story_id, fx.owner)
    fx.owner = "supervisor-2"
    fx.epoch = fx.store.acquire_epoch(fx.story_id, fx.owner, 3600)
    marked = fx.store.supervisor_reap_and_mark(fx.supervisor_key, SUPERVISOR_RUNNER)
    extra["takeover_markers"] = [r["check_description"] for r in marked]
    takeover = _brief(fx.gate())
    extra["verdict_after_takeover_before_reattest"] = takeover["verdict"]
    extra["reasons_after_takeover_before_reattest"] = takeover["reasons"]

    # begin(3) at the new epoch, fresh PASS set (attempt 2 of every slot) at the new head.
    fx.current_head = OTHER_HEAD
    extra["takeover_lease_error_kind"] = _error_kind(lambda: fx.begin(3))
    extra["reattest_error_kind"] = _error_kind(lambda: _next_pass_set(fx, 2))
    fx.end()
    extra["verdict_after_reattest"] = _brief(fx.gate())["verdict"]

    # More lease calls after the re-attestation: still granted, still no marker.
    extra["post_reattest_acquire_error_kinds"] = [
        _error_kind(lambda: fx.begin(4)),
        _error_kind(lambda: fx.begin(4)),
    ]
    fx.end()
    extra["final_epoch"] = fx.epoch
    extra["budget_markers"] = _budget_marker_count(fx)
    extra["terminal_markers"] = sum(
        1
        for r in fx.store.receipts_for_task(fx.task_id)
        if r["slot"] == SUPERVISOR_SLOT and r["check_description"] in ("BUDGET_EXCEEDED", "RETRY_EXHAUSTED")
    )
    extra["failed_attempts"] = fx.store.failed_attempts(fx.task_id)
    extra["event_chain_ok"] = fx.store.verify_event_chain()
    return _observe(fx.gate(), extra)


def _tamper_spent(fx: SliceFixture, spent: int) -> None:
    """Write budget.spent behind the Store's back (a metering bug or an outside writer)."""
    conn = sqlite3.connect(os.path.join(fx.workdir, "state.db"), timeout=30)
    try:
        conn.execute("UPDATE budget SET spent = ? WHERE task_id = ?", (spent, fx.task_id))
        conn.commit()
    finally:
        conn.close()


def _scenario_overspend_still_blocks(fx: SliceFixture, clock: FakeClock) -> dict:
    # Only spent == cap is tolerated. Genuine overspend (spent > cap) and a charge beyond
    # the cap must still block, commit exactly one signed marker and refuse every later call.
    extra: dict[str, Any] = {}
    # Path A: spent > cap written outside the Store API, while a worker holds a lease.
    fx.begin(1)
    fx.store.set_budget(fx.task_id, 5)
    extra["remaining_after_exact_charge"] = fx.store.charge(
        fx.task_id, 5, supervisor_key=fx.supervisor_key
    )
    extra["receipt_at_exact_cap_error_kind"] = _error_kind(
        lambda: fx.append(fx.make_test_receipt(1, EXPECTED_TEST_IDS))
    )
    _tamper_spent(fx, 6)
    extra["receipt_after_overspend_error_kind"] = _error_kind(
        lambda: fx.append(fx.make_static_receipt())
    )
    extra["heartbeat_after_overspend_error_kind"] = _error_kind(
        lambda: fx.store.heartbeat(fx.task_id, WORKER_ID, fx.epoch, 600)
    )
    extra["markers_before_lease_call"] = _budget_marker_count(fx)
    fx.end()
    extra["acquire_after_overspend_error_kinds"] = [
        _error_kind(lambda: fx.begin(2)),
        _error_kind(lambda: fx.begin(2)),
    ]
    extra["markers_after_lease_calls"] = _budget_marker_count(fx)
    extra["stored_worker_receipts"] = sum(
        1 for r in fx.store.receipts_for_task(fx.task_id) if r["slot"] != SUPERVISOR_SLOT
    )
    extra["event_chain_ok"] = fx.store.verify_event_chain()

    # Path B (independent database): a complete PASS set at exactly the cap approves; the
    # first unit beyond the cap blocks through the public charge path and withdraws the approval.
    other = SliceFixture(
        os.path.join(fx.workdir, "charge_path"), fx.key, clock, retry_cap=fx.manifest["retry_cap"]
    )
    try:
        other.begin(1)
        other.store.set_budget(other.task_id, 5)
        other.store.charge(other.task_id, 5, supervisor_key=other.supervisor_key)
        other.append_good_set()
        other.end()
        extra["charge_path_verdict_at_cap"] = _brief(other.gate())["verdict"]
        extra["charge_beyond_cap_error_kind"] = _error_kind(
            lambda: other.store.charge(other.task_id, 1, supervisor_key=other.supervisor_key)
        )
        after = _brief(other.gate())
        extra["charge_path_verdict_after_overspend"] = after["verdict"]
        extra["charge_path_reasons_after_overspend"] = after["reasons"]
        extra["charge_path_acquire_error_kind"] = _error_kind(lambda: other.begin(2))
        extra["charge_path_markers"] = _budget_marker_count(other)
    finally:
        other.close()
    return _observe(fx.gate(), extra)


def _resign_with_id(fx: SliceFixture, receipt: dict, receipt_id: str) -> dict:
    """The same receipt content under another receipt_id, signed with the worker key."""
    body = copy.deepcopy(receipt)
    body.pop("signature")
    body["receipt_id"] = receipt_id
    body["signature"] = sign(dict(body), fx.key)
    return body


def _scenario_worker_cannot_claim_supervisor_receipt_id(fx: SliceFixture, clock: FakeClock) -> dict:
    # A worker tries to pre-claim the receipt id the first supervisor marker will use
    # (sup-{task}-1), which would make the marker collide on the receipt_id key. The claim is
    # refused, nothing is consumed, and the supervisor marker still lands under that exact id.
    marker_id = f"{SUPERVISOR_RECEIPT_PREFIX}{fx.task_id}-1"
    extra: dict[str, Any] = {"marker_id": marker_id}
    fx.begin(1, 60)
    claims = {
        "tests_marker_id": _resign_with_id(
            fx, fx.make_test_receipt(1, EXPECTED_TEST_IDS), marker_id
        ),
        "static_marker_id": _resign_with_id(fx, fx.make_static_receipt(), marker_id),
        "review_marker_id": _resign_with_id(
            fx, fx.make_review_receipt(REVIEWER, AUTHOR), marker_id
        ),
        "tests_prefix_x": _resign_with_id(
            fx, fx.make_test_receipt(1, EXPECTED_TEST_IDS), SUPERVISOR_RECEIPT_PREFIX + "x"
        ),
        "tests_prefix_only": _resign_with_id(
            fx, fx.make_test_receipt(1, EXPECTED_TEST_IDS), SUPERVISOR_RECEIPT_PREFIX
        ),
    }
    extra["claim_error_kinds"] = {
        name: _error_kind(lambda r=r: fx.append(r)) for name, r in claims.items()
    }
    extra["stored_after_claims"] = len(fx.store.receipts_for_task(fx.task_id))
    clock.advance(120)  # the worker dies without a single stored receipt
    written = fx.store.supervisor_reap_and_mark(fx.supervisor_key, SUPERVISOR_RUNNER)
    extra["marker_ids_written"] = [r["receipt_id"] for r in written]
    extra["marker_reasons_written"] = [r["check_description"] for r in written]
    extra["verdict_after_marker"] = _brief(fx.gate())["verdict"]

    # The refused claims consumed no attempt number: attempt 1 of every slot is still free.
    # An id that merely resembles the prefix ('support-...') is an ordinary id.
    fx.begin(2)
    near_miss = _resign_with_id(fx, fx.make_test_receipt(1, EXPECTED_TEST_IDS), "support-tests-1")
    extra["near_miss_id"] = near_miss["receipt_id"]
    extra["near_miss_error_kind"] = _error_kind(lambda: fx.append(near_miss))
    extra["rest_of_set_error_kinds"] = [
        _error_kind(lambda: fx.append(fx.make_static_receipt())),
        _error_kind(lambda: fx.append(fx.make_review_receipt(REVIEWER, AUTHOR))),
    ]
    fx.end()
    return _observe(fx.gate(), extra)


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
    ("retry_across_head_change", _scenario_retry_across_head_change),
    ("worker_lost_before_first_receipt", _scenario_worker_lost_then_new_head),
    ("takeover_does_not_exhaust_retry_cap", _scenario_takeover_does_not_exhaust_cap),
    ("budget_exact_cap_allows_final_receipts", _scenario_budget_exact_cap),
    ("takeover_after_full_pass_set", _scenario_takeover_after_full_pass_set),
    ("retry_across_three_heads", _scenario_retry_across_three_heads),
    ("exact_cap_reattest_keeps_approve", _scenario_exact_cap_reattest_keeps_approve),
    ("overspend_still_blocks", _scenario_overspend_still_blocks),
    ("worker_cannot_claim_supervisor_receipt_id", _scenario_worker_cannot_claim_supervisor_receipt_id),
)

# Scenarios that need a manifest retry_cap other than the default 1.
_SCENARIO_RETRY_CAP = {"takeover_after_full_pass_set": 0}


def run_scenarios(workdir: str) -> dict[str, dict]:
    """Run every scenario in its own subdirectory of workdir; return observations."""
    os.makedirs(workdir, exist_ok=True)
    report: dict[str, dict] = {}
    for name, scenario in SCENARIOS:
        clock = FakeClock()
        fixture = SliceFixture(
            os.path.join(workdir, name), SLICE_KEY, clock,
            retry_cap=_SCENARIO_RETRY_CAP.get(name, 1),
        )
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
