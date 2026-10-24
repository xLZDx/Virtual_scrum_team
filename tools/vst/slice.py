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
import stat
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable

from . import gate as gate_module
from .contracts import (
    SUPERVISOR_SLOT,
    ContractError,
    canonical_bytes,
    derive_result,
    manifest_sha256,
    receipt_sha256,
    validate_task_manifest,
)
from .runner import build_environment, run_and_sign
from .lifecycle import STOP_TRANSITIONS
from .signing import WAIVER_LABEL, sign
from .supervisor import Supervisor
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
        anchor_path: str | None = None,
        sandbox_mode: bool = False,
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
        self.store = Store(
            os.path.join(workdir, "state.db"), clock, event_key=event_key,
            anchor_path=anchor_path, sandbox_mode=sandbox_mode,
            supervisor_key=supervisor_key if sandbox_mode else None,
        )
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


class SyntheticOperationBackend:
    """Supervisor-only adapter for a local bare Git remote."""

    _LOCAL_STORAGE_LOCK = threading.RLock()
    _MAX_PACK_BYTES = 64 * 1024 * 1024
    _MAX_PACK_OBJECTS = 250_000
    _MAX_GIT_DIAGNOSTIC_BYTES = 8 * 1024
    _MAX_SOURCE_OBJECT_STORAGE_BYTES = 512 * 1024 * 1024
    _MAX_SOURCE_OBJECT_COUNT = 250_000
    _MAX_SOURCE_STORE_ENTRIES = 500_000
    _MAX_PREFLIGHT_OUTPUT_BYTES = 4096
    _MAX_IDEMPOTENCY_RECORD_BYTES = 64 * 1024
    _MAX_TARGET_OBJECT_STORAGE_BYTES = 512 * 1024 * 1024
    _MAX_PACK_INDEX_BYTES = (_MAX_PACK_OBJECTS * 48) + 4096
    _STORAGE_LOCK_FILE_BYTES = 2
    _STORAGE_STATE_BYTES = {"HEALTHY": b"H", "IN_PROGRESS": b"I", "POISONED": b"P"}

    def __init__(
        self, bare_path: str, *, source_repo: str, command_timeout_sec: int = 10,
    ) -> None:
        if isinstance(command_timeout_sec, bool) or not isinstance(command_timeout_sec, int) or command_timeout_sec < 1:
            raise ValueError("command_timeout_sec must be a positive integer")
        if not isinstance(bare_path, str) or not bare_path.strip():
            raise ValueError("bare_path must be a non-empty path")
        if not isinstance(source_repo, str) or not source_repo.strip():
            raise ValueError("source_repo must be a non-empty path")
        self.bare_path = os.path.realpath(bare_path)
        self.source_repo = source_repo
        self.command_timeout_sec = command_timeout_sec

    def _git_env(self, object_dir: str | None = None) -> dict[str, str]:
        env = {
            name: os.environ[name]
            for name in (
                "PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP",
                "TMPDIR", "LANG", "LC_ALL",
            )
            if name in os.environ
        }
        env.update({
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_NO_LAZY_FETCH": "1",
        })
        if object_dir is not None:
            env["GIT_OBJECT_DIRECTORY"] = os.path.abspath(object_dir)
        return env

    def _target_git_env(self) -> dict[str, str]:
        return self._git_env(os.path.join(self.bare_path, "objects"))

    def _git(self, *args: str, input_bytes: bytes | None = None) -> str:
        completed = subprocess.run(
            ["git", "--git-dir", self.bare_path, *args],
            input=input_bytes, stdin=None if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=self.command_timeout_sec, env=self._target_git_env(),
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
        return completed.stdout.decode("utf-8", "replace").strip()

    @contextmanager
    def _target_storage_lock(self):
        """Serialize every target object write across processes/supervisors."""
        object_dir = os.path.abspath(os.path.join(self.bare_path, "objects"))
        if self._is_link_or_junction(object_dir):
            raise RuntimeError("synthetic target object directory must not be a symlink")
        if not os.path.isdir(object_dir):
            raise RuntimeError("synthetic target object directory is unavailable")
        deadline = time.monotonic() + self.command_timeout_sec
        local_lock = self._LOCAL_STORAGE_LOCK
        if not local_lock.acquire(timeout=self.command_timeout_sec):
            raise TimeoutError("timed out waiting for in-process synthetic target storage lock")
        lock_path = os.path.join(self.bare_path, ".vst-object-storage.lock")
        if self._is_link_or_junction(lock_path):
            local_lock.release()
            raise RuntimeError("synthetic target storage lock must not be a symlink")
        fd = None
        lock_file = None
        os_locked = False
        try:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            except FileExistsError:
                fd = os.open(lock_path, os.O_RDWR)
            lock_file = os.fdopen(fd, "r+b", buffering=0)
            fd = None
            size = os.fstat(lock_file.fileno()).st_size
            if size == 0:
                os.ftruncate(lock_file.fileno(), self._STORAGE_LOCK_FILE_BYTES)
                os.fsync(lock_file.fileno())
            elif size != self._STORAGE_LOCK_FILE_BYTES:
                raise StoreError(
                    "synthetic target has a legacy or malformed storage lock; refusing writes",
                    kind="blocked",
                )
            while True:
                lock_file.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    os_locked = True
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("timed out waiting for synthetic target storage lock") from exc
                    time.sleep(0.01)
            lock_file.seek(1)
            state = lock_file.read(1)
            lease = {"file": lock_file, "state": "HEALTHY"}
            if state == self._STORAGE_STATE_BYTES["IN_PROGRESS"]:
                self._write_storage_state(lease, "POISONED")
                raise StoreError(
                    "synthetic target has an interrupted object write and is poisoned",
                    kind="blocked",
                )
            if state == self._STORAGE_STATE_BYTES["POISONED"]:
                raise StoreError("synthetic target is poisoned; refusing object writes", kind="blocked")
            if state not in {b"\0", self._STORAGE_STATE_BYTES["HEALTHY"]}:
                self._write_storage_state(lease, "POISONED")
                raise StoreError("synthetic target storage state is malformed and fail-closed", kind="blocked")
            if state == b"\0":
                self._write_storage_state(lease, "HEALTHY")
            yield lease
        finally:
            try:
                if os_locked:
                    if os.name == "nt":
                        import msvcrt
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                os_locked = False
                try:
                    if lock_file is not None:
                        lock_file.close()
                finally:
                    try:
                        if fd is not None:
                            os.close(fd)
                    finally:
                        local_lock.release()

    def _write_storage_state(self, lease: dict[str, Any], state: str) -> None:
        state_byte = self._STORAGE_STATE_BYTES[state]
        lock_file = lease["file"]
        lock_file.seek(1)
        written = lock_file.write(state_byte)
        if written != 1:
            raise OSError("short write while updating synthetic target storage state")
        lock_file.flush()
        os.fsync(lock_file.fileno())
        lease["state"] = state

    @staticmethod
    def _raise_walk_error(error: OSError) -> None:
        raise error

    def _target_object_storage_bytes(self) -> int:
        object_dir = os.path.join(self.bare_path, "objects")
        total = 0
        for root, directories, files in os.walk(
            object_dir, followlinks=False, onerror=self._raise_walk_error,
        ):
            for name in directories:
                path = os.path.join(root, name)
                if self._is_link_or_junction(path):
                    raise RuntimeError("synthetic target object directory contains a symlink")
            for name in files:
                path = os.path.join(root, name)
                if self._is_link_or_junction(path):
                    raise RuntimeError("synthetic target object store contains a symlink")
                total += os.stat(path, follow_symlinks=False).st_size
                if total > self._MAX_TARGET_OBJECT_STORAGE_BYTES:
                    return total
        return total

    def _reserve_target_object_storage(self, additional_bytes: int) -> None:
        current = self._target_object_storage_bytes()
        if current + additional_bytes > self._MAX_TARGET_OBJECT_STORAGE_BYTES:
            raise StoreError(
                "synthetic target object storage cap would be exceeded",
                kind="budget",
            )

    def _run_bounded_git(
        self, command: list[str], *, env: dict[str, str],
        output_limit: int | None = None,
    ) -> tuple[bytes, bytes, int]:
        """Run trusted Git plumbing with fixed-size output capture and timeout."""
        output_limit = self._MAX_PREFLIGHT_OUTPUT_BYTES if output_limit is None else output_limit
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=env, bufsize=0,
        )
        outputs = {"stdout": bytearray(), "stderr": bytearray()}
        overflow = {"stdout": False, "stderr": False}

        def drain(name: str, stream) -> None:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                remaining = output_limit - len(outputs[name])
                if remaining > 0:
                    outputs[name].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overflow[name] = True

        readers = [
            threading.Thread(target=drain, args=(name, stream), daemon=True)
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))
        ]
        for reader in readers:
            reader.start()
        try:
            returncode = process.wait(timeout=self.command_timeout_sec)
        except subprocess.TimeoutExpired as exc:
            try:
                process.kill()
            except OSError:
                pass
            try:
                process.wait(timeout=1)
            except (subprocess.TimeoutExpired, OSError) as reap_error:
                raise TimeoutError("bounded Git preflight process could not be reaped") from reap_error
            raise TimeoutError("bounded Git preflight command exceeded its time limit") from exc
        finally:
            for reader in readers:
                reader.join(timeout=1)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        if any(overflow.values()):
            raise RuntimeError("bounded Git command output exceeded its limit")
        if any(reader.is_alive() for reader in readers):
            raise RuntimeError("bounded Git preflight output reader did not finish")
        return bytes(outputs["stdout"]), bytes(outputs["stderr"]), returncode

    @staticmethod
    def _is_lower_hex(value: str) -> bool:
        return bool(value) and all(character in "0123456789abcdef" for character in value)

    @staticmethod
    def _is_link_or_junction(path: str) -> bool:
        is_junction = getattr(os.path, "isjunction", lambda candidate: False)
        if os.path.islink(path) or is_junction(path):
            return True
        reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if reparse_attribute:
            try:
                return bool(os.lstat(path).st_file_attributes & reparse_attribute)
            except (AttributeError, OSError):
                return False
        return False

    def _source_repository_paths(self) -> tuple[str, str, str]:
        supplied_root = os.path.abspath(self.source_repo)
        if self._is_link_or_junction(supplied_root):
            raise RuntimeError("synthetic source repository must not be a symlink")
        source_root = os.path.realpath(supplied_root)
        git_dir = os.path.join(source_root, ".git")
        if self._is_link_or_junction(git_dir) or not os.path.isdir(git_dir):
            raise RuntimeError("synthetic source must be a self-contained repository with a .git directory")
        if os.path.lexists(os.path.join(git_dir, "commondir")):
            raise RuntimeError("synthetic worktree repositories with external common Git directories are unsupported")
        git_dir_real = os.path.realpath(git_dir)
        if os.path.commonpath((source_root, git_dir_real)) != source_root:
            raise RuntimeError("synthetic source Git directory escapes its repository root")
        object_dir = os.path.join(git_dir_real, "objects")
        if self._is_link_or_junction(object_dir) or not os.path.isdir(object_dir):
            raise RuntimeError("synthetic source object directory is unavailable or symlinked")
        for alternate_file in (
            os.path.join(object_dir, "info", "alternates"),
            os.path.join(object_dir, "info", "http-alternates"),
        ):
            if os.path.lexists(alternate_file):
                raise RuntimeError("synthetic source object alternates are unsupported")
        object_dir_real = os.path.realpath(object_dir)
        if os.path.commonpath((git_dir_real, object_dir_real)) != git_dir_real:
            raise RuntimeError("synthetic source object directory escapes its Git directory")
        return source_root, git_dir_real, object_dir_real

    def _source_object_storage_bytes(self, object_dir: str) -> int:
        total = entries = 0
        deadline = time.monotonic() + self.command_timeout_sec
        for root, directories, files in os.walk(
            object_dir, followlinks=False, onerror=self._raise_walk_error,
        ):
            if time.monotonic() >= deadline:
                raise TimeoutError("synthetic source object-store scan exceeded its time limit")
            for name in directories:
                if time.monotonic() >= deadline:
                    raise TimeoutError("synthetic source object-store scan exceeded its time limit")
                entries += 1
                path = os.path.join(root, name)
                if self._is_link_or_junction(path):
                    raise RuntimeError("synthetic source object store contains a symlink directory")
                if entries > self._MAX_SOURCE_STORE_ENTRIES:
                    raise RuntimeError("synthetic source object store exceeds the entry-count limit")
            for name in files:
                if time.monotonic() >= deadline:
                    raise TimeoutError("synthetic source object-store scan exceeded its time limit")
                entries += 1
                path = os.path.join(root, name)
                if self._is_link_or_junction(path):
                    raise RuntimeError("synthetic source object store contains a symlink file")
                source_stat = os.stat(path, follow_symlinks=False)
                if not stat.S_ISREG(source_stat.st_mode):
                    raise RuntimeError("synthetic source object store contains a non-regular file")
                total += source_stat.st_size
                if entries > self._MAX_SOURCE_STORE_ENTRIES:
                    raise RuntimeError("synthetic source object store exceeds the entry-count limit")
                if total > self._MAX_SOURCE_OBJECT_STORAGE_BYTES:
                    raise RuntimeError("synthetic source object store exceeds the 512 MiB limit")
        return total

    def _source_object_counts(self, git_dir: str, object_dir: str) -> tuple[int, int]:
        output, diagnostic, returncode = self._run_bounded_git(
            ["git", "--git-dir", git_dir, "count-objects", "-v"],
            env=self._git_env(object_dir),
        )
        if returncode:
            raise RuntimeError(diagnostic.decode("utf-8", "replace"))
        fields: dict[str, int] = {}
        for line in output.decode("utf-8", "strict").splitlines():
            key, separator, value = line.partition(": ")
            if not separator:
                raise RuntimeError("Git count-objects returned malformed preflight output")
            if key == "alternate":
                raise RuntimeError("synthetic source object alternates are unsupported")
            if key not in {"count", "size", "in-pack", "packs", "size-pack", "prune-packable", "garbage", "size-garbage"}:
                raise RuntimeError("Git count-objects returned an unknown preflight field")
            if key in fields or not value.isdecimal():
                raise RuntimeError("Git count-objects returned a malformed numeric field")
            fields[key] = int(value)
        if not {"count", "in-pack", "size", "size-pack"}.issubset(fields):
            raise RuntimeError("Git count-objects omitted required object counts or sizes")
        return fields["count"] + fields["in-pack"], (fields["size"] + fields["size-pack"]) * 1024

    def _copy_source_object_file(
        self, entry, destination: str, copied: list[int], deadline: float,
    ) -> None:
        source_path = entry.path
        before = entry.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or self._is_link_or_junction(source_path):
            raise RuntimeError("synthetic source object entry changed type during snapshot")
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(source_path, flags)
        try:
            opened = os.fstat(fd)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_dev != before.st_dev
                    or opened.st_ino != before.st_ino or opened.st_size != before.st_size
                    or self._is_link_or_junction(source_path)):
                raise RuntimeError("synthetic source object file changed during snapshot")
            remaining = opened.st_size
            with os.fdopen(fd, "rb", closefd=False) as source, open(destination, "xb") as target:
                while remaining:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("synthetic source snapshot copy exceeded its time limit")
                    chunk = source.read(min(64 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError("synthetic source object file truncated during snapshot")
                    target.write(chunk)
                    copied[0] += len(chunk)
                    if copied[0] > self._MAX_SOURCE_OBJECT_STORAGE_BYTES:
                        raise RuntimeError("synthetic source snapshot exceeds the 512 MiB limit")
                    remaining -= len(chunk)
                if source.read(1):
                    raise RuntimeError("synthetic source object file grew during snapshot")
        finally:
            os.close(fd)

    def _copy_source_object_store(self, source_objects: str, snapshot_objects: str) -> int:
        copied = [0]
        entry_count = [0]
        deadline = time.monotonic() + self.command_timeout_sec

        def count_entry() -> None:
            entry_count[0] += 1
            if entry_count[0] > self._MAX_SOURCE_STORE_ENTRIES:
                raise RuntimeError("synthetic source snapshot exceeds the entry-count limit")

        with os.scandir(source_objects) as source_entries:
            for entry in source_entries:
                if time.monotonic() >= deadline:
                    raise TimeoutError("synthetic source snapshot copy exceeded its time limit")
                count_entry()
                name = entry.name
                if self._is_link_or_junction(entry.path):
                    raise RuntimeError("synthetic source object store contains a symlink")
                if name == "info":
                    continue
                if name == "pack" and entry.is_dir(follow_symlinks=False):
                    with os.scandir(entry.path) as pack_entries:
                        for pack_entry in pack_entries:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("synthetic source snapshot copy exceeded its time limit")
                            count_entry()
                            if self._is_link_or_junction(pack_entry.path):
                                raise RuntimeError("synthetic source pack directory contains a symlink")
                            pack_name = pack_entry.name
                            suffix = ".pack" if pack_name.endswith(".pack") else ".idx" if pack_name.endswith(".idx") else None
                            if suffix is None:
                                continue
                            object_hash = pack_name[5:-len(suffix)] if pack_name.startswith("pack-") else ""
                            if len(object_hash) not in {40, 64} or not self._is_lower_hex(object_hash):
                                raise RuntimeError("synthetic source pack file has an invalid name")
                            if not pack_entry.is_file(follow_symlinks=False):
                                raise RuntimeError("synthetic source pack entry is not a regular file")
                            self._copy_source_object_file(
                                pack_entry, os.path.join(snapshot_objects, "pack", pack_name), copied, deadline,
                            )
                elif entry.is_dir(follow_symlinks=False) and len(name) == 2 and self._is_lower_hex(name):
                    with os.scandir(entry.path) as loose_entries:
                        for loose_entry in loose_entries:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("synthetic source snapshot copy exceeded its time limit")
                            count_entry()
                            if self._is_link_or_junction(loose_entry.path):
                                raise RuntimeError("synthetic source loose-object directory contains a symlink")
                            if len(loose_entry.name) not in {38, 62} or not self._is_lower_hex(loose_entry.name):
                                continue
                            if not loose_entry.is_file(follow_symlinks=False):
                                raise RuntimeError("synthetic source loose object is not a regular file")
                            self._copy_source_object_file(
                                loose_entry,
                                os.path.join(snapshot_objects, name, loose_entry.name), copied, deadline,
                            )
                else:
                    raise RuntimeError("synthetic source object store has an unsupported root entry")
                if copied[0] > self._MAX_SOURCE_OBJECT_STORAGE_BYTES:
                    raise RuntimeError("synthetic source snapshot exceeds the 512 MiB limit")
        return copied[0]

    @contextmanager
    def _source_object_snapshot(self, head: str):
        """Copy only local object files into an isolated Git object database."""
        _, source_git_dir, source_objects = self._source_repository_paths()
        self._source_object_storage_bytes(source_objects)
        source_count, source_size_bytes = self._source_object_counts(source_git_dir, source_objects)
        if source_count > self._MAX_SOURCE_OBJECT_COUNT:
            raise RuntimeError("synthetic source repository exceeds the 250,000 object limit")
        if source_size_bytes > self._MAX_SOURCE_OBJECT_STORAGE_BYTES:
            raise RuntimeError("Git count-objects reports a source ODB larger than 512 MiB")
        with tempfile.TemporaryDirectory(prefix=".vst-source-snapshot-", dir=self.bare_path) as temp_root:
            template = os.path.join(temp_root, "empty-template")
            snapshot_git_dir = os.path.join(temp_root, "source.git")
            os.makedirs(template)
            init_output, init_error, init_returncode = self._run_bounded_git(
                ["git", "init", "--bare", f"--template={template}", snapshot_git_dir],
                env=self._git_env(),
            )
            if init_returncode:
                raise RuntimeError(init_error.decode("utf-8", "replace"))
            snapshot_objects = os.path.join(snapshot_git_dir, "objects")
            self._copy_source_object_store(source_objects, snapshot_objects)
            snapshot_bytes = self._source_object_storage_bytes(snapshot_objects)
            snapshot_count, snapshot_size_bytes = self._source_object_counts(snapshot_git_dir, snapshot_objects)
            if snapshot_count > self._MAX_SOURCE_OBJECT_COUNT or snapshot_size_bytes > self._MAX_SOURCE_OBJECT_STORAGE_BYTES:
                raise RuntimeError("sanitized source object snapshot exceeds its preflight limits")
            if snapshot_bytes > self._MAX_SOURCE_OBJECT_STORAGE_BYTES or snapshot_count > self._MAX_SOURCE_OBJECT_COUNT:
                raise RuntimeError("sanitized source object snapshot exceeds its preflight limits")
            snapshot_env = self._git_env(snapshot_objects)
            _, diagnostic, returncode = self._run_bounded_git(
                ["git", "--git-dir", snapshot_git_dir, "cat-file", "-e", f"{head}^{{commit}}"],
                env=snapshot_env,
            )
            if returncode:
                raise RuntimeError(
                    "candidate commit is not present in the isolated local source object store: "
                    + diagnostic.decode("utf-8", "replace")
                )
            yield snapshot_git_dir, snapshot_env

    def _import_head(self, head: str) -> None:
        with self._target_storage_lock() as lease:
            self._reserve_target_object_storage(
                self._MAX_PACK_BYTES + self._MAX_PACK_INDEX_BYTES,
            )
            self._write_storage_state(lease, "IN_PROGRESS")
            try:
                self._import_head_locked(head, lease)
            except BaseException:
                if not lease.get("cleanup_uncertain"):
                    try:
                        self._write_storage_state(lease, "HEALTHY")
                    except OSError:
                        # The durable IN_PROGRESS slot remains fail-closed.
                        pass
                raise
            else:
                self._write_storage_state(lease, "HEALTHY")
            if self._target_object_storage_bytes() > self._MAX_TARGET_OBJECT_STORAGE_BYTES:
                raise StoreError(
                    "synthetic target object storage cap was exceeded during pack import",
                    kind="budget",
                )

    def _import_head_locked(self, head: str, lease: dict[str, Any]) -> None:
        with self._source_object_snapshot(head) as (source_git_dir, source_env):
            self._transfer_snapshot_head_locked(head, source_git_dir, source_env, lease)

    def _transfer_snapshot_head_locked(
        self, head: str, source_git_dir: str, source_env: dict[str, str],
        lease: dict[str, Any],
    ) -> None:
        source_command = [
            "git", "-c", "pack.threads=1", "-c", "pack.windowMemory=16m",
            "-c", "pack.window=10", "-c", "pack.deltaCacheSize=16777216",
            "-c", "pack.deltaCacheLimit=32768", "--git-dir", source_git_dir,
            "pack-objects", "--stdout", "--revs",
        ]
        target_command = [
            "git", "--git-dir", self.bare_path, "index-pack", "--strict", "--stdin",
        ]
        source = target = None
        source_diagnostic = bytearray()
        target_diagnostic = bytearray()
        expired = threading.Event()
        finished = threading.Event()

        def drain(stream, output: bytearray) -> None:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                remaining = self._MAX_GIT_DIAGNOSTIC_BYTES - len(output)
                if remaining > 0:
                    output.extend(chunk[:remaining])

        def kill_after_timeout() -> None:
            if finished.is_set():
                return
            expired.set()
            for process in (source, target):
                if process is not None and process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        pass

        timer = threading.Timer(self.command_timeout_sec, kill_after_timeout)
        source_stderr_thread = target_stderr_thread = None
        cleanup_uncertain = False
        try:
            source = subprocess.Popen(
                source_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=source_env, bufsize=0,
            )
            target = subprocess.Popen(
                target_command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, env=self._target_git_env(), bufsize=0,
            )
            source_stderr_thread = threading.Thread(
                target=drain, args=(source.stderr, source_diagnostic), daemon=True,
            )
            target_stderr_thread = threading.Thread(
                target=drain, args=(target.stderr, target_diagnostic), daemon=True,
            )
            source_stderr_thread.start()
            target_stderr_thread.start()
            timer_start = time.monotonic()
            timer.start()
            source.stdin.write((head + "\n").encode("ascii"))
            source.stdin.close()

            total_bytes = 0
            pack_header = bytearray()
            while True:
                chunk = source.stdout.read(64 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > self._MAX_PACK_BYTES:
                    raise RuntimeError("Git source object pack exceeds the 64 MiB limit")
                if len(pack_header) < 12:
                    pack_header.extend(chunk[:12 - len(pack_header)])
                    if len(pack_header) == 12:
                        if pack_header[:4] != b"PACK":
                            raise RuntimeError("Git source did not produce a valid pack header")
                        object_count = int.from_bytes(pack_header[8:12], "big")
                        if object_count > self._MAX_PACK_OBJECTS:
                            raise RuntimeError("Git source object pack exceeds the object-count limit")
                target.stdin.write(chunk)
            if expired.is_set():
                raise TimeoutError("Git source pack import exceeded its time limit")
            if total_bytes == 0 or len(pack_header) < 12:
                raise RuntimeError("Git source repository produced an empty or truncated object pack")
            target.stdin.close()
            deadline = timer_start + self.command_timeout_sec
            source.wait(timeout=max(0.001, deadline - time.monotonic()))
            target.wait(timeout=max(0.001, deadline - time.monotonic()))
            if expired.is_set():
                raise TimeoutError("Git source pack import exceeded its time limit")
            if source.returncode:
                raise RuntimeError(source_diagnostic.decode("utf-8", "replace"))
            if target.returncode:
                raise RuntimeError(target_diagnostic.decode("utf-8", "replace"))
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Git source pack import exceeded its time limit") from exc
        finally:
            finished.set()
            timer.cancel()
            for process in (source, target):
                if process is not None and process.poll() is None:
                    try:
                        process.kill()
                    except OSError:
                        pass
            for process in (source, target):
                if process is not None:
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except OSError:
                            pass
                        try:
                            process.wait(timeout=1)
                        except (subprocess.TimeoutExpired, OSError):
                            cleanup_uncertain = True
                    except OSError:
                        cleanup_uncertain = True
                    if process.returncode is None:
                        cleanup_uncertain = True
            for worker in (source_stderr_thread, target_stderr_thread):
                if worker is not None:
                    worker.join(timeout=1)
            for stream in (
                source.stdin if source else None, source.stdout if source else None,
                source.stderr if source else None, target.stdin if target else None,
                target.stderr if target else None,
            ):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            if cleanup_uncertain:
                lease["cleanup_uncertain"] = True
                try:
                    self._write_storage_state(lease, "POISONED")
                except OSError as poison_error:
                    # The previously fsynced IN_PROGRESS slot remains valid and
                    # blocks future writers even if this final marker write fails.
                    raise RuntimeError(
                        "Git child cleanup is unconfirmed; target remains IN_PROGRESS"
                    ) from poison_error
                raise RuntimeError("Git child cleanup is unconfirmed; target is poisoned")
        self._git("cat-file", "-e", f"{head}^{{commit}}")

    def _is_ancestor(self, ancestor: str, descendant: str) -> bool:
        completed = subprocess.run(
            ["git", "--git-dir", self.bare_path, "merge-base", "--is-ancestor", ancestor, descendant],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=self.command_timeout_sec,
        )
        if completed.returncode == 0:
            return True
        if completed.returncode == 1:
            return False
        raise RuntimeError(completed.stderr.decode("utf-8", "replace"))

    def _update_ref(self, ref: str, head: str, expected: str | None) -> None:
        old_value = expected or ("0" * 40)
        try:
            self._git("update-ref", ref, head, old_value)
        except RuntimeError:
            try:
                if self.ref_head(ref) == head:
                    return
            except RuntimeError:
                pass
            raise StoreError("bare target ref changed during synthetic publication", kind="duplicate")

    def ref_head(self, ref: str) -> str:
        return self._git("rev-parse", "--verify", ref)

    def _bind_operation(self, kind: str, operation_key: str, payload: dict) -> None:
        with self._target_storage_lock() as lease:
            self._bind_operation_locked(kind, operation_key, payload, lease)

    def _bind_operation_locked(
        self, kind: str, operation_key: str, payload: dict, lease: dict[str, Any],
    ) -> None:
        key_hash = hashlib.sha256(f"{kind}\0{operation_key}".encode("utf-8")).hexdigest()
        ref = f"refs/vst/idempotency/{key_hash}"
        record = canonical_bytes({"kind": kind, "payload": payload})
        try:
            existing_oid = self._git("rev-parse", "--verify", ref)
        except RuntimeError:
            existing_oid = None
        if existing_oid is not None:
            existing, diagnostic, returncode = self._run_bounded_git(
                ["git", "--git-dir", self.bare_path, "cat-file", "blob", existing_oid],
                env=self._target_git_env(), output_limit=self._MAX_IDEMPOTENCY_RECORD_BYTES,
            )
            if returncode:
                raise RuntimeError(diagnostic.decode("utf-8", "replace"))
            if existing != record:
                raise StoreError("remote idempotency key reused with different payload", kind="duplicate")
            return
        if len(record) > self._MAX_IDEMPOTENCY_RECORD_BYTES:
            raise StoreError("synthetic idempotency record exceeds the 64 KiB limit", kind="budget")
        self._reserve_target_object_storage(len(record) + (len(record) // 100) + 256)
        self._write_storage_state(lease, "IN_PROGRESS")
        try:
            new_oid = self._git("hash-object", "-w", "--stdin", input_bytes=record)
        except BaseException:
            try:
                self._write_storage_state(lease, "POISONED")
            except OSError:
                pass
            raise
        self._write_storage_state(lease, "HEALTHY")
        try:
            self._git("update-ref", ref, new_oid, "0" * 40)
        except RuntimeError:
            # Another supervisor process may have won the create-only ref race.
            raced_oid = self._git("rev-parse", "--verify", ref)
            raced = subprocess.run(
                ["git", "--git-dir", self.bare_path, "cat-file", "blob", raced_oid],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=True, timeout=self.command_timeout_sec,
            ).stdout
            if raced != record:
                raise StoreError("remote idempotency key reused with different payload", kind="duplicate")

    def push(self, payload: dict, *, operation_key: str) -> dict:
        branch, head = payload["branch"], payload["head"]
        if not isinstance(branch, str) or not branch.replace("-", "").replace("_", "").isalnum():
            raise ValueError("invalid synthetic branch")
        if not isinstance(head, str) or len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
            raise ValueError("candidate head must be a 40-character git id")
        self._bind_operation("push", operation_key, payload)
        ref = f"refs/heads/{branch}"
        try:
            current = self._git("rev-parse", "--verify", ref)
        except RuntimeError:
            current = None
        if current != head:
            self._import_head(head)
            if current is not None and not self._is_ancestor(current, head):
                raise StoreError("synthetic branch update is not a fast-forward", kind="duplicate")
            self._update_ref(ref, head, current)
        return {"operation_key": operation_key, "ref": ref, "head": head}

    def open_pull_request(self, payload: dict, *, operation_key: str) -> dict:
        head = payload["head"]
        if not isinstance(head, str) or len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
            raise ValueError("pull-request head must be a 40-character git id")
        self._bind_operation("pull_request", operation_key, payload)
        pr_key = hashlib.sha256(operation_key.encode("utf-8")).hexdigest()[:20]
        ref = f"refs/pull-requests/{pr_key}/head"
        try:
            current = self._git("rev-parse", "--verify", ref)
        except RuntimeError:
            current = None
        if current is not None and current != head:
            raise StoreError("pull-request key already points at a different head", kind="duplicate")
        if current is None:
            self._import_head(head)
            self._update_ref(ref, head, None)
        return {"operation_key": operation_key, "ref": ref, "head": head}


class HandWrittenWorker:
    """Minimal synthetic worker with scoped edits and no remote/push API."""

    def __init__(self, repository: str, allowed_paths: tuple[str, ...] = ("src/synthetic.py",)):
        self.repository = os.path.realpath(repository)
        self.allowed_paths = frozenset(allowed_paths)

    def _run(self, action: str, path: str, content: str = "") -> subprocess.CompletedProcess:
        worker_code = r'''import os, subprocess, sys
repo, action, rel, content = sys.argv[1:5]
if rel.startswith(("/", "\\")) or ".." in rel.replace("\\", "/").split("/"):
    raise SystemExit(30)
root = os.path.realpath(repo)
target = os.path.realpath(os.path.join(root, rel))
if os.path.commonpath((root, target)) != root:
    raise SystemExit(31)
if action in ("edit", "crash"):
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content if action == "edit" else "# partial synthetic edit\n")
        stream.flush()
        os.fsync(stream.fileno())
    if action == "crash":
        os._exit(97)
elif action == "commit":
    subprocess.run(["git", "add", "--", rel], cwd=root, check=True, stdin=subprocess.DEVNULL)
    subprocess.run(["git", "commit", "-m", content], cwd=root, check=True, stdin=subprocess.DEVNULL)
    print(subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"], cwd=root, text=True).strip())
else:
    raise SystemExit(32)
'''
        return subprocess.run(
            [sys.executable, "-I", "-c", worker_code, self.repository, action, path, content],
            cwd=self.repository, env=build_environment(), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

    def edit(self, path: str, content: str) -> None:
        if path not in self.allowed_paths or path.startswith(("/", "\\")) or ".." in path.split("/"):
            raise ValueError("worker edit is outside the declared synthetic scope")
        completed = self._run("edit", path, content)
        if completed.returncode:
            raise RuntimeError(completed.stderr.decode("utf-8", "replace"))

    def crash_mid_edit(self, path: str = "src/synthetic.py") -> None:
        if path not in self.allowed_paths:
            raise ValueError("worker edit is outside the declared synthetic scope")
        completed = self._run("crash", path)
        if completed.returncode != 97:
            raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
        raise RuntimeError("synthetic worker killed during edit")

    def commit_candidate(self, message: str = "synthetic candidate") -> str:
        heads = []
        for path in sorted(self.allowed_paths):
            completed = self._run("commit", path, message)
            if completed.returncode:
                raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
            heads.append(completed.stdout.decode("ascii").strip())
        return heads[-1]


def run_lifecycle_scenarios(
    workdir: str,
    *,
    probe_key: bytes,
    probe_provider: Callable[[str, str], dict],
) -> dict[str, dict]:
    """Drive E8's synthetic fixture using a caller-provided real sandbox probe."""
    os.makedirs(workdir, exist_ok=True)
    remote = os.path.join(workdir, "local-bare.git")
    repository = os.path.join(workdir, "worker-repository")
    control = os.path.join(workdir, "control")
    anchor_path = os.path.join(workdir, "control-anchor", "events.jsonl")

    def git(cwd: str, *args: str) -> str:
        completed = subprocess.run(
            ["git", "-C", cwd, *args], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr.decode("utf-8", "replace"))
        return completed.stdout.decode("utf-8", "replace").strip()

    subprocess.run(["git", "init", "--bare", remote], check=True, stdout=subprocess.DEVNULL)
    os.makedirs(repository, exist_ok=True)
    subprocess.run(["git", "init", repository], check=True, stdout=subprocess.DEVNULL)
    git(repository, "config", "user.name", "Synthetic Worker")
    git(repository, "config", "user.email", "synthetic-worker@example.invalid")
    initial_file = os.path.join(repository, "src", "synthetic.py")
    os.makedirs(os.path.dirname(initial_file), exist_ok=True)
    with open(initial_file, "w", encoding="utf-8", newline="\n") as stream:
        stream.write("value = 'base'\n")
    git(repository, "add", "--", "src/synthetic.py")
    git(repository, "commit", "-m", "synthetic base")
    backend = SyntheticOperationBackend(remote, source_repo=repository)
    base_head = git(repository, "rev-parse", "--verify", "HEAD")
    backend.push({"branch": "main", "head": base_head}, operation_key="bootstrap")

    clock = FakeClock()
    fixture = SliceFixture(
        control, SLICE_KEY, clock, supervisor_key=SUPERVISOR_KEY,
        operator_key=OPERATOR_KEY, event_key=EVENT_KEY, anchor_path=anchor_path,
        sandbox_mode=True,
    )
    worker = HandWrittenWorker(repository)
    run_id = "synthetic-crash-run"
    nonce = "synthetic-crash-nonce"

    def make_probe(run: str, run_nonce: str) -> dict:
        return probe_provider(run, run_nonce)

    supervisor = Supervisor(
        fixture.store, operation_backend=backend, failure_threshold=2,
        run_id=run_id, probe_nonce=nonce, probe_key=probe_key,
    )
    report: dict[str, dict] = {}
    try:
        fixture.begin(1, ttl_sec=600)
        supervisor.start_worker(lambda: worker, probe=make_probe(run_id, nonce))
        crash_injected = False
        try:
            worker.crash_mid_edit()
        except RuntimeError:
            crash_injected = True
        clock.advance(601)
        lost = fixture.store.supervisor_reap_and_mark(SUPERVISOR_KEY, SUPERVISOR_RUNNER)
        supervisor.stop(lambda: None, lambda: None)

        def next_epoch() -> int:
            fixture.store.release_epoch(fixture.story_id, fixture.owner)
            fixture.epoch = fixture.store.acquire_epoch(fixture.story_id, fixture.owner, 3600)
            return fixture.epoch

        resumed_epoch = supervisor.resume(next_epoch)
        run_id, nonce = "synthetic-resume-run", "synthetic-resume-nonce"
        supervisor.prepare_run(run_id, nonce)
        fixture.begin(2, ttl_sec=600)
        supervisor.start_worker(lambda: worker, probe=make_probe(run_id, nonce))
        worker.edit("src/synthetic.py", "value = 'resumed candidate'\n")
        candidate_head = worker.commit_candidate()
        fixture.current_head = candidate_head

        test_receipt = fixture.make_test_receipt(1, EXPECTED_TEST_IDS)
        receipt_first = supervisor.create_receipt(
            "worker-test-receipt-1", test_receipt, fixture.story_id, SLICE_KEY,
        )
        receipt_retry = supervisor.create_receipt(
            "worker-test-receipt-1", test_receipt, fixture.story_id, SLICE_KEY,
        )
        fixture.store.append_receipt(
            fixture.make_static_receipt(), fixture.story_id, SLICE_KEY,
        )
        fixture.store.append_receipt(
            fixture.make_review_receipt(REVIEWER, AUTHOR), fixture.story_id, SLICE_KEY,
        )
        fixture.end()
        decision = supervisor.evaluate_gate(
            fixture.task_id, candidate_head, fixture.epoch, SLICE_KEY,
            supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY,
        )
        push_payload = {"branch": "main", "head": candidate_head}
        pushed = supervisor.simulate_push("candidate-push-1", push_payload)
        pr = supervisor.simulate_pull_request(
            "candidate-pr-1", {"head": candidate_head, "title": "Synthetic candidate"},
        )

        # Crash-window simulation: remote state and immutable operation binding
        # are persisted, while the SQLite operation result has not been written.
        crash_key = "push-crash-window"
        crash_payload = {"branch": "crash-recovery", "head": candidate_head}
        crash_result = backend.push(crash_payload, operation_key=crash_key)
        remote_before_restart_retry = backend.ref_head("refs/heads/crash-recovery")
        fixture.store.close()
        restarted_store = Store(
            os.path.join(control, "state.db"), event_key=EVENT_KEY,
            anchor_path=anchor_path, sandbox_mode=True, supervisor_key=SUPERVISOR_KEY,
        )
        restarted_supervisor = Supervisor(
            restarted_store, operation_backend=SyntheticOperationBackend(
                remote, source_repo=repository,
            ),
            run_id="synthetic-restart-context", probe_nonce="synthetic-restart-nonce",
            probe_key=probe_key,
        )
        retried = restarted_supervisor.simulate_push(crash_key, crash_payload)
        remote_after_restart_retry = restarted_supervisor.backend.ref_head("refs/heads/crash-recovery")
        fixture.store = restarted_store

        exact_budget = fixture.store.charge(
            fixture.task_id, 100, supervisor_key=SUPERVISOR_KEY,
            runner_id=SUPERVISOR_RUNNER,
        )
        budget_exhausted = False
        try:
            fixture.store.charge(
                fixture.task_id, 1, supervisor_key=SUPERVISOR_KEY,
                runner_id=SUPERVISOR_RUNNER,
            )
        except StoreError as exc:
            budget_exhausted = exc.kind == "budget"
        lease_blocked = False
        try:
            fixture.store.acquire_lease(
                fixture.task_id, fixture.story_id, fixture.runner_id, fixture.epoch,
                3, 600, supervisor_key=SUPERVISOR_KEY,
            )
        except StoreError:
            lease_blocked = True

        report["crash_stop_resume"] = {
            "crash_injected_mid_edit": crash_injected,
            "worker_lost_markers": [item["check_description"] for item in lost],
            "resumed_epoch": resumed_epoch,
            "candidate_head": candidate_head,
            "worker_has_remote_config": bool(git(repository, "remote")),
            "gate_verdict": decision["verdict"],
            "receipt_retry_returned_same_result": receipt_first == receipt_retry,
            "supervisor_push": pushed,
            "supervisor_pull_request": pr,
        }
        report["restart_idempotency"] = {
            "effect_recorded_before_store_commit": crash_result,
            "retry_result_after_store_restart": retried,
            "same_result": crash_result == retried,
            "remote_ref_unchanged_on_retry": remote_before_restart_retry == remote_after_restart_retry,
        }
        report["budget_exhaustion"] = {
            "remaining_at_exact_cap": exact_budget,
            "overflow_rejected": budget_exhausted,
            "new_lease_rejected": lease_blocked,
        }
        return report
    finally:
        fixture.close()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m tools.vst.slice <temporary-directory>", file=sys.stderr)
        return 2
    report = run_scenarios(argv[1])
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
