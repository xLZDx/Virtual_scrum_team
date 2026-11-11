"""U5-3: pipeline state in the store, epoch checks, idempotent steps, stop path, migration and rollback.

Acceptance text: "The store models story, worker attempt, patch proposal, diff gate, review
iterations, tests and receipts with epoch checks, idempotent steps and a stop path; any schema
change has a migration, a rollback point and a test that restores the previous state."

Every test drives the public API against a real SQLite file. Raw sqlite3 connections only OBSERVE
state (or play the attacker). The "previous schema" fixture is a store as created by the unchanged
store.py (PRAGMA user_version 7, no pl_ table); the dump helper below is an independent restatement
of "all schema objects and all rows", not the code under test. Expected counts are hand-computed
from the data written in this file. Time is a FakeClock; nothing sleeps.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading

import pytest

from tools.vst import pipeline_migration as pm
from tools.vst import worker_gate as wg
from tools.vst.pipeline_migration import (
    MigrationError,
    MigrationLock,
    migrate_pipeline,
    migration_status,
    restore_rollback_point,
)
from tools.vst.pipeline_state import PipelineState
from tools.vst.store import Store, StoreError

from .e1e4_helpers import KEY, OWNER_TTL, STORY, STORY2, FakeClock, lease, new_env, open_store, receipt

BASE = "b" * 40
CAND = "c" * 40
REPORT = "d" * 64
DIFF = "e" * 64
EVID = "f" * 64
PL_TABLES = {
    "pl_schema_version", "pl_steps", "pl_story_control", "pl_worker_attempts", "pl_patch_proposals",
    "pl_diff_gates", "pl_review_iterations", "pl_test_evidence", "pl_receipt_links",
}


class Crash(BaseException):
    """Stands for a process death: not an Exception, so nothing may swallow it."""


# --------------------------------------------------------------------- helpers
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


def count(path, table):
    return rows(path, f"SELECT COUNT(*) FROM {table}")[0][0]


def tables(path):
    return {r[0] for r in rows(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}


def dump(path):
    """Independent restatement of 'the whole logical state': user_version, schema objects, all rows."""
    conn = sqlite3.connect(path)
    try:
        out = {"user_version": conn.execute("PRAGMA user_version").fetchone()[0]}
        out["objects"] = conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type, name"
        ).fetchall()
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall():
            out["rows:" + name] = conn.execute(f'SELECT rowid, * FROM "{name}" ORDER BY rowid').fetchall()
        return out
    finally:
        conn.close()


def without_pl(state):
    return {k: v for k, v in state.items() if not k.startswith("rows:pl_") and k != "objects"} | {
        "objects": [o for o in state["objects"] if not o[1].startswith("pl_")]
    }


def raises_kind(kind, fn, *args, **kwargs):
    with pytest.raises(StoreError) as exc:
        fn(*args, **kwargs)
    assert exc.value.kind == kind, (exc.value.kind, str(exc.value))
    return exc.value


def old_store(tmp_path, name="old.db"):
    """Store as it is before U5-3: schema version 7, a story, a task, a lease and a receipt, no pl_ table."""
    path = str(tmp_path / name)
    store, clock, epoch = new_env(path)
    lease(store, epoch)
    r = receipt("TestRun", epoch=epoch)
    store.append_receipt(r, STORY, KEY)
    store.close()
    return path, r["receipt_id"]


def current_epoch(path, story=STORY):
    return rows(path, "SELECT epoch FROM stories WHERE story_id = ?", (story,))[0][0]


def manifests(path):
    folder = path + pm.ROLLBACK_SUFFIX
    return sorted(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".manifest.json"))


def load(manifest_path):
    with open(manifest_path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8"))


def run_record(**kw):
    base = {
        "schema": "vst-patch-run-record-v1", "verdict": "ACCEPTED", "stage": "written",
        "worktree_state": "MODIFIED", "report_sha256": REPORT, "candidate_head": CAND, "diff_sha256": DIFF,
        "partial": False, "post_materialize_verified": True, "patched_paths": ["src/app.py"],
        "no_patch_paths": [], "applied": True, "attempted_proposal_hunks": {"src/app.py": [[1, 1]]},
        "attempted_proposal_lines": 2, "proposal_lines": 2, "model_lines": 0, "total_lines": 2,
        "proposal_fraction": 1.0, "model_fraction": 0.0, "files_touched_by_both": [], "model_only_paths": [],
        "overrides": [],
    }
    base.update(kw)
    return base


def honest_proof():
    props = []
    for name in wg.REQUIRED_PROPERTIES:
        status = "CALLER_ASSERTED" if name in wg.CALLER_ONLY_PROPERTIES else "VERIFIED"
        props.append({"property": name, "status": status, "detail": "d"})
    for name in wg.NOT_VERIFIED_PROPERTIES:
        props.append({"property": name, "status": "NOT_VERIFIED", "detail": "d"})
    return {"schema": "vst-worker-isolation-proof-v1", "isolation_mode": "windows-local-no-wsl", "properties": props}


def accepted_gate(proof=None):
    return {"verdict": "ACCEPTED", "reasons": [], "diff_evidence": {"paths": ["src/app.py"]},
            "isolation_proof": honest_proof() if proof is None else proof}


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / "state.db")
    store, clock, epoch = new_env(path)
    migrate_pipeline(path)
    ps = PipelineState(store)
    yield ps, store, clock, path, epoch
    store.close()


def start(ps, epoch, step="s-start-1", base=BASE):
    return ps.start_worker_attempt(STORY, epoch=epoch, step_id=step, base_head=base)


# --------------------------------------------------------------------- model round trips
def test_worker_attempt_roundtrip_and_numbering(env):
    ps, _, _, path, epoch = env
    first = start(ps, epoch)
    assert first.result == {"attempt_no": 1} and first.replayed is False
    attempt = ps.list_worker_attempts(STORY)[0]
    assert (attempt["attempt_no"], attempt["epoch"], attempt["base_head"], attempt["state"]) == (1, epoch, BASE, "STARTED")
    assert attempt["candidate_head"] is None
    done = ps.finish_worker_attempt(STORY, epoch=epoch, step_id="s-fin-1", attempt_no=1, state="SUCCEEDED", candidate_head=CAND)
    assert done.result == {"attempt_no": 1, "state": "SUCCEEDED"}
    attempt = ps.list_worker_attempts(STORY)[0]
    assert (attempt["state"], attempt["candidate_head"], attempt["finish_step_id"]) == ("SUCCEEDED", CAND, "s-fin-1")
    second = start(ps, epoch, "s-start-2", CAND)
    assert second.result == {"attempt_no": 2}


def test_worker_attempt_rules(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    raises_kind("pipeline", start, ps, epoch, "s-start-2")  # one open attempt at a time
    raises_kind("argument", ps.finish_worker_attempt, STORY, epoch=epoch, step_id="f1", attempt_no=1, state="SUCCEEDED")
    raises_kind("argument", ps.finish_worker_attempt, STORY, epoch=epoch, step_id="f1", attempt_no=1, state="STOPPED")
    raises_kind("pipeline", ps.finish_worker_attempt, STORY, epoch=epoch, step_id="f1", attempt_no=7, state="FAILED")
    ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f2", attempt_no=1, state="FAILED")
    raises_kind("pipeline", ps.finish_worker_attempt, STORY, epoch=epoch, step_id="f3", attempt_no=1, state="FAILED")
    raises_kind("argument", start, ps, epoch, "s-bad-head", "XYZ")
    assert count(path, "pl_worker_attempts") == 1


def test_patch_proposal_roundtrip_derives_counts_from_the_run_record(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    res = ps.record_patch_proposal(STORY, epoch=epoch, step_id="p1", attempt_no=1, proposal_id="prop-1",
                                   base_head=BASE, run_record=run_record())
    assert res.result == {"proposal_id": "prop-1", "verdict": "ACCEPTED", "applied_hunks": 1}
    row = ps.list_patch_proposals(STORY)[0]
    assert (row["proposal_document_sha256"], row["candidate_head"], row["base_head"]) == (REPORT, CAND, BASE)
    assert (row["verdict"], row["stage"], row["attempted_hunks"], row["applied_hunks"]) == ("ACCEPTED", "written", 1, 1)
    assert (row["proposal_lines"], row["model_lines"]) == (2, 0)
    assert row["run_record"]["attempted_proposal_hunks"] == {"src/app.py": [[1, 1]]}


def test_refused_patch_proposal_has_no_applied_hunks_and_inconsistent_records_are_refused(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    refused = run_record(verdict="REFUSED", stage="base_check", applied=False, candidate_head=None,
                         post_materialize_verified=None, proposal_lines=0, attempted_proposal_hunks={},
                         attempted_proposal_lines=0, total_lines=0, proposal_fraction=None, model_fraction=None)
    ps.record_patch_proposal(STORY, epoch=epoch, step_id="p1", attempt_no=1, proposal_id="prop-r", base_head=BASE, run_record=refused)
    row = ps.list_patch_proposals(STORY)[0]
    assert (row["verdict"], row["attempted_hunks"], row["applied_hunks"], row["candidate_head"]) == ("REFUSED", 0, 0, None)
    # built and gate-accepted but not verifiably written: attempted counted, applied stays 0
    unverified = run_record(applied=False, post_materialize_verified=False, proposal_lines=0)
    ps.record_patch_proposal(STORY, epoch=epoch, step_id="p2", attempt_no=1, proposal_id="prop-u", base_head=BASE, run_record=unverified)
    row = [r for r in ps.list_patch_proposals(STORY) if r["proposal_id"] == "prop-u"][0]
    assert (row["attempted_hunks"], row["applied_hunks"], row["proposal_lines"]) == (1, 0, 0)
    bad = {
        "applied but refused": run_record(verdict="REFUSED"),
        "lines without applied": run_record(applied=False, proposal_lines=2),
        "accepted without candidate": run_record(candidate_head=None),
        "accepted without report hash": run_record(report_sha256=None),
        "wrong schema": run_record(schema="other"),
        "unknown verdict": run_record(verdict="MAYBE"),
    }
    for label, record in bad.items():
        raises_kind("argument", ps.record_patch_proposal, STORY, epoch=epoch, step_id="x-" + label.replace(" ", "-"),
                    attempt_no=1, proposal_id="prop-x", base_head=BASE, run_record=record)
    assert count(path, "pl_patch_proposals") == 2


def test_diff_gate_roundtrip_keeps_proof_statuses_unpromoted(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    ps.record_patch_proposal(STORY, epoch=epoch, step_id="p1", attempt_no=1, proposal_id="prop-1", base_head=BASE, run_record=run_record())
    res = ps.record_diff_gate(STORY, epoch=epoch, step_id="g1", gate_id="gate-1", attempt_no=1, gate=accepted_gate(), proposal_id="prop-1")
    assert res.result == {"gate_id": "gate-1", "verdict": "ACCEPTED"}
    row = ps.list_diff_gates(STORY)[0]
    assert row["proposal_id"] == "prop-1" and row["reasons"] == []
    statuses = row["proof_statuses"]
    assert len(statuses) == 15  # 6 required + 9 never-verified properties
    assert sorted(statuses.values()).count("VERIFIED") == 3
    assert sorted(statuses.values()).count("CALLER_ASSERTED") == 3
    assert sorted(statuses.values()).count("NOT_VERIFIED") == 9
    assert statuses["base_commit_pinned"] == "CALLER_ASSERTED"
    assert row["isolation_proof"] == honest_proof()


def test_diff_gate_refusals_and_object_input(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    verdict = wg.WorkerGateVerdict("REFUSED", (("OUT_OF_SCOPE", "src/other.py"),), None, None)
    ps.record_diff_gate(STORY, epoch=epoch, step_id="g1", gate_id="gate-r", attempt_no=1, gate=verdict)
    row = ps.list_diff_gates(STORY)[0]
    assert row["verdict"] == "REFUSED" and row["reasons"] == [{"code": "OUT_OF_SCOPE", "detail": "src/other.py"}]
    assert row["isolation_proof"] is None and row["proof_statuses"] == {}
    promoted = honest_proof()
    promoted["properties"][1]["status"] = "VERIFIED"  # base_commit_pinned is caller-only
    failed = honest_proof()
    failed["properties"][0]["status"] = "FAILED"
    cases = {
        "no proof": {"verdict": "ACCEPTED", "reasons": [], "isolation_proof": None},
        "promoted": accepted_gate(promoted),
        "failed entry": accepted_gate(failed),
        "refused without reason": {"verdict": "REFUSED", "reasons": [], "isolation_proof": None},
        "bad verdict": {"verdict": "OK", "reasons": [], "isolation_proof": None},
        "bad status": accepted_gate(dict(honest_proof(), properties=[{"property": "p", "status": "GREAT"}])),
    }
    for label, gate in cases.items():
        raises_kind("argument", ps.record_diff_gate, STORY, epoch=epoch, step_id="x-" + label.replace(" ", "-"),
                    gate_id="gate-x", attempt_no=1, gate=gate)
    ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f1", attempt_no=1, state="FAILED")
    start(ps, epoch, "s2")
    ps.record_patch_proposal(STORY, epoch=epoch, step_id="p9", attempt_no=1, proposal_id="prop-old", base_head=BASE, run_record=run_record())
    raises_kind("pipeline", ps.record_diff_gate, STORY, epoch=epoch, step_id="g9", gate_id="gate-9", attempt_no=2,
                gate=accepted_gate(), proposal_id="prop-old")  # the proposal belongs to attempt 1
    assert count(path, "pl_diff_gates") == 1


def test_review_iterations_roundtrip_and_rules(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)

    def review(step, index, of, findings, coverage, verdict):
        return ps.record_review_iteration(STORY, epoch=epoch, step_id=step, attempt_no=1, iteration_index=index,
                                          iteration_of=of, findings_count=findings, coverage_declared=coverage, verdict=verdict)

    assert review("r1", 1, None, 3, ["R2", "R1"], "FINDINGS").result == {"iteration_index": 1, "verdict": "FINDINGS"}
    assert review("r2", 2, 1, 0, ["R1", "R2"], "CLEAN").result == {"iteration_index": 2, "verdict": "CLEAN"}
    first, second = ps.list_review_iterations(STORY)
    assert (first["iteration_of"], first["findings_count"], first["coverage_declared"], first["verdict"]) == (None, 3, ["R1", "R2"], "FINDINGS")
    assert (second["iteration_of"], second["findings_count"], second["verdict"]) == (1, 0, "CLEAN")
    raises_kind("pipeline", review, "r4", 4, 2, 0, ["R1"], "CLEAN")        # gap: next index is 3
    raises_kind("argument", review, "r5", 3, None, 0, ["R1"], "CLEAN")     # iteration_of required after the first
    raises_kind("argument", review, "r6", 3, 3, 0, ["R1"], "CLEAN")        # must point to an earlier one
    raises_kind("argument", review, "r7", 3, 2, 1, ["R1"], "CLEAN")        # CLEAN with findings
    raises_kind("argument", review, "r8", 3, 2, 0, [], "CLEAN")            # CLEAN without declared coverage
    raises_kind("argument", review, "r9", 3, 2, 0, ["R1"], "FINDINGS")     # FINDINGS without findings
    raises_kind("argument", review, "r10", 3, 2, 0, ["R1", "R1"], "PARTIAL")  # duplicate coverage entry
    assert count(path, "pl_review_iterations") == 2


def test_test_evidence_roundtrip_including_not_run(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    ps.record_test_evidence(STORY, epoch=epoch, step_id="t1", attempt_no=1, evidence_id="ev-1", test_id="tests/a::t1",
                            status="PASS", evidence_sha256=EVID)
    ps.record_test_evidence(STORY, epoch=epoch, step_id="t2", attempt_no=1, evidence_id="ev-2", test_id="tests/a::t2",
                            status="NOT_RUN", reason="prohibited by operator")
    got = {r["evidence_id"]: r for r in ps.list_test_evidence(STORY)}
    assert (got["ev-1"]["status"], got["ev-1"]["evidence_sha256"], got["ev-1"]["reason"]) == ("PASS", EVID, None)
    assert (got["ev-2"]["status"], got["ev-2"]["evidence_sha256"], got["ev-2"]["reason"]) == ("NOT_RUN", None, "prohibited by operator")
    raises_kind("argument", ps.record_test_evidence, STORY, epoch=epoch, step_id="t3", attempt_no=1, evidence_id="ev-3",
                test_id="x", status="PASS")
    raises_kind("argument", ps.record_test_evidence, STORY, epoch=epoch, step_id="t4", attempt_no=1, evidence_id="ev-4",
                test_id="x", status="NOT_RUN")
    raises_kind("argument", ps.record_test_evidence, STORY, epoch=epoch, step_id="t5", attempt_no=1, evidence_id="ev-5",
                test_id="x", status="GREEN", evidence_sha256=EVID)
    raises_kind("duplicate", ps.record_test_evidence, STORY, epoch=epoch, step_id="t6", attempt_no=1, evidence_id="ev-6",
                test_id="tests/a::t1", status="FAIL", evidence_sha256=EVID)  # one result per test per attempt
    assert count(path, "pl_test_evidence") == 2 and count(path, "pl_steps") == 3


def test_receipt_link_points_at_the_existing_receipt_and_copies_nothing(tmp_path):
    path = str(tmp_path / "state.db")
    store, _, epoch = new_env(path)
    migrate_pipeline(path)
    lease(store, epoch)
    r = receipt("TestRun", epoch=epoch)
    store.append_receipt(r, STORY, KEY)
    ps = PipelineState(store)
    start(ps, epoch)
    before = count(path, "receipts")
    res = ps.link_receipt(STORY, epoch=epoch, step_id="l1", receipt_id=r["receipt_id"], subject_kind="WORKER_ATTEMPT", subject_key="1")
    assert res.result == {"receipt_id": r["receipt_id"], "subject_kind": "WORKER_ATTEMPT", "subject_key": "1"}
    link = ps.list_receipt_links(STORY)[0]
    assert (link["receipt_id"], link["subject_kind"], link["subject_key"]) == (r["receipt_id"], "WORKER_ATTEMPT", "1")
    assert count(path, "receipts") == before == 1
    raises_kind("receipt", ps.link_receipt, STORY, epoch=epoch, step_id="l2", receipt_id="no-such", subject_kind="WORKER_ATTEMPT", subject_key="1")
    raises_kind("pipeline", ps.link_receipt, STORY, epoch=epoch, step_id="l3", receipt_id=r["receipt_id"], subject_kind="DIFF_GATE", subject_key="nope")
    raises_kind("pipeline", ps.link_receipt, STORY, epoch=epoch, step_id="l4", receipt_id=r["receipt_id"], subject_kind="WORKER_ATTEMPT", subject_key="9")
    raises_kind("argument", ps.link_receipt, STORY, epoch=epoch, step_id="l5", receipt_id=r["receipt_id"], subject_kind="OTHER", subject_key="1")
    assert count(path, "pl_receipt_links") == 1
    store.close()


# --------------------------------------------------------------------- epoch checks
def test_stale_and_future_epoch_are_refused_and_nothing_is_written(env):
    ps, store, clock, path, epoch = env
    start(ps, epoch)
    steps_before, attempts_before = count(path, "pl_steps"), count(path, "pl_worker_attempts")
    clock.advance(OWNER_TTL + 1)
    new_epoch = store.acquire_epoch(STORY, "owner-b", OWNER_TTL)
    assert new_epoch == epoch + 1
    raises_kind("epoch", start, ps, epoch, "s-stale")                      # stale
    raises_kind("epoch", start, ps, epoch + 5, "s-future")                 # not current either
    raises_kind("epoch", start, ps, epoch, "s-start-1")                    # even a replay of an old step is refused
    raises_kind("epoch", ps.stop_story, STORY, epoch=epoch, step_id="stop-stale", reason="stale stop")
    assert (count(path, "pl_steps"), count(path, "pl_worker_attempts")) == (steps_before, attempts_before)
    assert count(path, "pl_story_control") == 0
    ok = ps.finish_worker_attempt(STORY, epoch=new_epoch, step_id="f-new", attempt_no=1, state="FAILED")
    assert ok.replayed is False and count(path, "pl_steps") == steps_before + 1


def test_unknown_story_is_refused(env):
    ps, _, _, path, epoch = env
    raises_kind("story", ps.start_worker_attempt, "no-such-story", epoch=epoch, step_id="s1", base_head=BASE)
    assert count(path, "pl_steps") == 0


# --------------------------------------------------------------------- idempotency
def test_replay_returns_the_original_result_and_writes_nothing(env):
    ps, _, _, path, epoch = env
    first = start(ps, epoch)
    snapshot = dump(path)
    again = start(ps, epoch)
    assert again.replayed is True and again.result == first.result == {"attempt_no": 1}
    assert dump(path) == snapshot
    assert count(path, "pl_steps") == 1 and count(path, "pl_worker_attempts") == 1
    # a replay after the attempt moved on still returns the first answer, not the current state
    ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f1", attempt_no=1, state="FAILED")
    snapshot = dump(path)
    assert start(ps, epoch).result == {"attempt_no": 1}
    fin = ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f1", attempt_no=1, state="FAILED")
    assert fin.replayed is True and fin.result == {"attempt_no": 1, "state": "FAILED"}
    assert dump(path) == snapshot
    assert ps.get_step(STORY, "s-start-1")["result"] == {"attempt_no": 1}


def test_same_step_id_with_another_payload_or_kind_is_a_conflict(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    snapshot = dump(path)
    raises_kind("conflict", start, ps, epoch, "s-start-1", "a" * 40)
    raises_kind("conflict", ps.finish_worker_attempt, STORY, epoch=epoch, step_id="s-start-1", attempt_no=1, state="FAILED")
    raises_kind("conflict", ps.stop_story, STORY, epoch=epoch, step_id="s-start-1", reason="same id other kind")
    assert dump(path) == snapshot


def test_two_concurrent_requests_with_the_same_step_write_once(tmp_path):
    path = str(tmp_path / "state.db")
    store, _, epoch = new_env(path)
    migrate_pipeline(path)
    store.close()
    results, errors = [], []
    barrier = threading.Barrier(2)

    def worker():
        try:
            own = open_store(path, FakeClock())
            try:
                state = PipelineState(own)
                barrier.wait(timeout=30)
                results.append(state.start_worker_attempt(STORY, epoch=epoch, step_id="same", base_head=BASE))
            finally:
                own.close()
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == []
    assert sorted(r.replayed for r in results) == [False, True]
    assert all(r.result == {"attempt_no": 1} for r in results)
    assert count(path, "pl_worker_attempts") == 1 and count(path, "pl_steps") == 1


# --------------------------------------------------------------------- stop path
def test_stop_path(env):
    ps, store, _, path, epoch = env
    start(ps, epoch)
    first = ps.stop_story(STORY, epoch=epoch, step_id="stop-1", reason="operator stop")
    assert first.replayed is False
    assert first.result == {"stopped": True, "stop_step_id": "stop-1", "stop_epoch": epoch,
                            "already_stopped": False, "attempts_stopped": 1}
    assert ps.list_worker_attempts(STORY)[0]["state"] == "STOPPED"
    control = rows(path, "SELECT * FROM pl_story_control")[0]
    assert (control["story_id"], control["stop_step_id"], control["stop_epoch"], control["stop_reason"]) == (STORY, "stop-1", epoch, "operator stop")
    snapshot = dump(path)
    # idempotent: same step id, and another step id, both return the first stop and write nothing
    same = ps.stop_story(STORY, epoch=epoch, step_id="stop-1", reason="operator stop")
    other = ps.stop_story(STORY, epoch=epoch, step_id="stop-2", reason="second request")
    assert same.replayed is True and same.result == first.result
    assert other.replayed is True and other.result["stop_step_id"] == "stop-1" and other.result["already_stopped"] is True
    assert dump(path) == snapshot
    # no further step is accepted
    refused = [
        lambda: start(ps, epoch, "after-1"),
        lambda: ps.finish_worker_attempt(STORY, epoch=epoch, step_id="after-2", attempt_no=1, state="FAILED"),
        lambda: ps.record_test_evidence(STORY, epoch=epoch, step_id="after-3", attempt_no=1, evidence_id="e", test_id="t", status="PASS", evidence_sha256=EVID),
        lambda: ps.record_patch_proposal(STORY, epoch=epoch, step_id="after-4", attempt_no=1, proposal_id="p", base_head=BASE, run_record=run_record()),
        lambda: ps.record_diff_gate(STORY, epoch=epoch, step_id="after-5", gate_id="g", attempt_no=1, gate=accepted_gate()),
        lambda: ps.record_review_iteration(STORY, epoch=epoch, step_id="after-6", attempt_no=1, iteration_index=1, iteration_of=None, findings_count=0, coverage_declared=["R1"], verdict="CLEAN"),
        lambda: ps.link_receipt(STORY, epoch=epoch, step_id="after-7", receipt_id="r", subject_kind="WORKER_ATTEMPT", subject_key="1"),
    ]
    for call in refused:
        raises_kind("stopped", call)
    assert dump(path) == snapshot
    # reads and the stop acknowledgment are accepted
    status = ps.get_status(STORY)
    assert status["stopped"] is True and status["stop"]["stop_step_id"] == "stop-1" and status["epoch"] == epoch
    assert ps.list_test_evidence(STORY) == []
    ack = ps.acknowledge_stop(STORY, epoch=epoch, step_id="ack-1", actor="worker-1")
    assert ack.result == {"acknowledged_by": "worker-1", "stop_step_id": "stop-1"}
    assert ps.acknowledge_stop(STORY, epoch=epoch, step_id="ack-1", actor="worker-1").replayed is True
    assert count(path, "pl_steps") == 3  # start, stop, ack
    # the stop is per story
    store.open_story(STORY2, "proj", 4)
    other_epoch = store.acquire_epoch(STORY2, "owner-a", OWNER_TTL)
    assert ps.start_worker_attempt(STORY2, epoch=other_epoch, step_id="s-other", base_head=BASE).result == {"attempt_no": 1}


def test_acknowledge_requires_a_stop_and_stop_without_attempt_stops_nothing(env):
    ps, _, _, path, epoch = env
    raises_kind("pipeline", ps.acknowledge_stop, STORY, epoch=epoch, step_id="ack-early", actor="worker-1")
    assert count(path, "pl_steps") == 0
    res = ps.stop_story(STORY, epoch=epoch, step_id="stop-1", reason="nothing running")
    assert res.result["attempts_stopped"] == 0
    raises_kind("argument", ps.stop_story, STORY, epoch=epoch, step_id="stop-2", reason="  ")


def test_pipeline_rows_are_append_only_in_the_database(env):
    ps, _, _, path, epoch = env
    start(ps, epoch)
    ps.record_test_evidence(STORY, epoch=epoch, step_id="t1", attempt_no=1, evidence_id="ev-1", test_id="t", status="PASS", evidence_sha256=EVID)
    ps.finish_worker_attempt(STORY, epoch=epoch, step_id="f1", attempt_no=1, state="FAILED")
    conn = sqlite3.connect(path)
    try:
        for sql in (
            "UPDATE pl_steps SET kind = 'STOP'", "DELETE FROM pl_steps",
            "UPDATE pl_test_evidence SET status = 'FAIL'", "DELETE FROM pl_test_evidence",
            "UPDATE pl_worker_attempts SET state = 'SUCCEEDED'",  # a closed attempt cannot change
            "DELETE FROM pl_worker_attempts", "DELETE FROM pl_schema_version",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
    finally:
        conn.close()
    assert count(path, "pl_steps") == 3 and ps.list_worker_attempts(STORY)[0]["state"] == "FAILED"


def test_pipeline_state_refuses_a_store_without_the_pipeline_schema(tmp_path):
    path = str(tmp_path / "state.db")
    store, _, _ = new_env(path)
    try:
        raises_kind("schema", PipelineState, store)
        raises_kind("argument", PipelineState, object())
    finally:
        store.close()


# --------------------------------------------------------------------- migration
def test_previous_schema_fixture_has_no_pipeline_tables(tmp_path):
    path, _ = old_store(tmp_path)
    assert rows(path, "PRAGMA user_version")[0][0] == 7
    names = tables(path)
    assert {"stories", "tasks", "leases", "receipts", "events", "meta"} <= names
    assert not any(n.startswith("pl_") for n in names)
    assert migration_status(path)["state"] == "NOT_MIGRATED"
    assert migration_status(path)["pipeline_version"] == 0


def test_migration_adds_the_tables_and_preserves_every_existing_row(tmp_path):
    path, receipt_id = old_store(tmp_path)
    before = dump(path)
    result = migrate_pipeline(path)
    assert (result.from_version, result.to_version, result.performed) == (0, 1, True)
    after = dump(path)
    assert without_pl(after) == without_pl(before)          # user_version, schema, all rows unchanged
    assert after["user_version"] == 7
    assert PL_TABLES <= tables(path) and {n for n in tables(path) if n.startswith("pl_")} == PL_TABLES
    assert [tuple(r) for r in rows(path, "SELECT component, version FROM pl_schema_version")] == [("pipeline", 1)]
    assert migration_status(path)["state"] == "CURRENT"
    store = open_store(path, FakeClock())               # the unchanged Store opens the migrated file
    try:
        assert store.get_phase(STORY) == 4
        assert [r["receipt_id"] for r in rows(path, "SELECT receipt_id FROM receipts")] == [receipt_id]
    finally:
        store.close()


def test_migrating_twice_is_a_no_op_without_a_new_rollback_point(tmp_path):
    path, _ = old_store(tmp_path)
    migrate_pipeline(path)
    state = dump(path)
    again = migrate_pipeline(path)
    assert (again.from_version, again.to_version, again.performed, again.rollback_manifest) == (1, 1, False, None)
    assert dump(path) == state and len(manifests(path)) == 1


def test_rollback_point_is_written_before_the_migration_and_describes_the_old_state(tmp_path):
    path, _ = old_store(tmp_path)
    before = dump(path)
    result = migrate_pipeline(path)
    found = manifests(path)
    assert found == [result.rollback_manifest]
    manifest = load(found[0])
    assert (manifest["kind"], manifest["store_user_version"], manifest["pipeline_version"]) == ("pre-migration", 7, 0)
    backup = os.path.join(os.path.dirname(found[0]), manifest["backup_file"])
    with open(backup, "rb") as handle:
        data = handle.read()
    assert manifest["sha256"] == hashlib.sha256(data).hexdigest() and manifest["size"] == len(data)
    assert not any(n.startswith("pl_") for n in tables(backup))
    assert dump(backup) == before                          # the backup holds the previous schema and rows
    journal = load(os.path.join(path + pm.ROLLBACK_SUFFIX, pm.JOURNAL_NAME))
    assert (journal["state"], journal["from_version"], journal["to_version"]) == ("COMMITTED", 0, 1)
    assert journal["rollback_manifest"] == os.path.basename(found[0])
    assert not os.path.exists(path + pm.LOCK_SUFFIX)


def test_restore_returns_the_exact_previous_rows(tmp_path):
    path, _ = old_store(tmp_path)
    before = dump(path)
    result = migrate_pipeline(path)
    store = open_store(path, FakeClock())               # use the new schema, then roll it back
    epoch = current_epoch(path)
    PipelineState(store).start_worker_attempt(STORY, epoch=epoch, step_id="s1", base_head=BASE)
    store.close()
    migrated = dump(path)
    assert migrated != before
    restored = restore_rollback_point(path, result.rollback_manifest)
    assert restored.store_user_version == 7 and restored.pipeline_version == 0
    assert dump(path) == before
    assert not any(n.startswith("pl_") for n in tables(path))
    assert migration_status(path)["state"] == "NOT_MIGRATED"
    # the state before the restore was itself saved
    safety = load(restored.pre_restore_manifest)
    assert safety["kind"] == "pre-restore" and safety["pipeline_version"] == 1
    assert dump(os.path.join(os.path.dirname(restored.pre_restore_manifest), safety["backup_file"])) == migrated
    # and the migration can be run again from the restored state
    assert migrate_pipeline(path).performed is True
    assert migration_status(path)["state"] == "CURRENT"
    assert len(manifests(path)) == 3  # pre-migration, pre-restore, pre-migration


@pytest.mark.parametrize("stage", ["before_ddl", "mid_ddl", "before_commit"])
def test_failure_inside_the_migration_leaves_the_old_version(tmp_path, stage):
    path, _ = old_store(tmp_path)
    before = dump(path)

    def fault(name):
        if name == stage:
            raise RuntimeError("injected")

    err = raises_kind("migration", migrate_pipeline, path, fault=fault)
    assert "rolled back" in str(err)
    assert dump(path) == before                              # old version, no pl_ table, not half migrated
    assert not os.path.exists(path + pm.LOCK_SUFFIX)
    status = migration_status(path)
    assert (status["state"], status["pipeline_version"], status["journal_state"]) == ("NOT_MIGRATED", 0, "ABORTED")
    assert len(manifests(path)) == 1                          # the rollback point exists and is valid
    assert pm.load_rollback_point(manifests(path)[0]).pipeline_version == 0
    done = migrate_pipeline(path)                            # restartable
    assert (done.performed, done.to_version) == (True, 1)
    assert migration_status(path)["state"] == "CURRENT"


def test_crash_after_commit_is_detected_and_closed_by_the_next_run(tmp_path):
    path, _ = old_store(tmp_path)

    def fault(name):
        if name == "after_commit":
            raise Crash()

    with pytest.raises(Crash):
        migrate_pipeline(path, fault=fault)
    status = migration_status(path)
    assert (status["state"], status["journal_state"], status["pipeline_version"]) == ("COMMIT_UNRECORDED", "STARTED", 1)
    assert not os.path.exists(path + pm.LOCK_SUFFIX)       # the lock is released even on a crash
    again = migrate_pipeline(path)
    assert (again.performed, again.resumed) == (False, True)
    assert migration_status(path)["state"] == "CURRENT" and migration_status(path)["journal_state"] == "COMMITTED"
    assert len(manifests(path)) == 1


def test_interrupted_migration_is_detected_and_resumed(tmp_path):
    path, _ = old_store(tmp_path)
    before = dump(path)
    os.makedirs(path + pm.ROLLBACK_SUFFIX)
    pm._write_journal(path, "STARTED", 0, 1, "lost.manifest.json")   # as left by a killed process
    status = migration_status(path)
    assert (status["state"], status["pipeline_version"]) == ("INTERRUPTED", 0)
    assert dump(path) == before
    result = migrate_pipeline(path)
    assert (result.performed, result.resumed) == (True, True)
    assert migration_status(path)["state"] == "CURRENT"


def test_newer_unknown_store_schema_is_refused_before_anything_is_written(tmp_path):
    path, _ = old_store(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 8")
    conn.close()
    before = dump(path)
    raises_kind("newer", migrate_pipeline, path)
    assert dump(path) == before and not os.path.exists(path + pm.ROLLBACK_SUFFIX)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version = 6")
    conn.close()
    raises_kind("schema", migrate_pipeline, path)           # older store layouts are not migrated here either
    assert not os.path.exists(path + pm.ROLLBACK_SUFFIX)


def test_newer_unknown_pipeline_schema_is_refused(tmp_path):
    path, _ = old_store(tmp_path)
    migrate_pipeline(path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE pl_schema_version SET version = 2")
    conn.commit()
    conn.close()
    before = dump(path)
    raises_kind("newer", migrate_pipeline, path)
    assert dump(path) == before and len(manifests(path)) == 1
    store = open_store(path, FakeClock())
    try:
        raises_kind("newer", PipelineState, store)
    finally:
        store.close()


def test_partially_applied_pipeline_schema_is_detected_not_adopted(tmp_path):
    path, _ = old_store(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE pl_steps (x INT)")           # stray table, no version table
    conn.close()
    before = dump(path)
    raises_kind("partial", migrate_pipeline, path)
    raises_kind("partial", migration_status, path)
    assert dump(path) == before and not os.path.exists(path + pm.ROLLBACK_SUFFIX)
    other, _ = old_store(tmp_path, "other.db")
    migrate_pipeline(other)
    conn = sqlite3.connect(other)
    conn.execute("DROP TABLE pl_receipt_links")             # version row says 1 but a table is missing
    conn.close()
    raises_kind("partial", migrate_pipeline, other)
    raises_kind("partial", migration_status, other)


def test_missing_store_file_is_refused_and_not_created(tmp_path):
    path = str(tmp_path / "absent.db")
    raises_kind("schema", migrate_pipeline, path)
    assert not os.path.exists(path)


def test_corrupted_backup_is_refused_on_restore_and_the_store_is_untouched(tmp_path):
    path, _ = old_store(tmp_path)
    result = migrate_pipeline(path)
    manifest = load(result.rollback_manifest)
    backup = os.path.join(os.path.dirname(result.rollback_manifest), manifest["backup_file"])
    migrated = dump(path)
    with open(backup, "rb") as handle:
        data = bytearray(handle.read())
    data[len(data) // 2] ^= 0xFF
    with open(backup, "wb") as handle:
        handle.write(bytes(data))
    raises_kind("backup", restore_rollback_point, path, result.rollback_manifest)
    assert dump(path) == migrated and len(manifests(path)) == 1   # no pre-restore point for a refused restore
    assert not os.path.exists(path + pm.LOCK_SUFFIX)


def test_tampered_manifest_and_foreign_manifest_are_refused(tmp_path):
    path, _ = old_store(tmp_path)
    result = migrate_pipeline(path)
    migrated = dump(path)
    manifest = load(result.rollback_manifest)
    for field, value in (("sha256", "0" * 64), ("size", manifest["size"] + 1), ("content_sha256", "1" * 64),
                         ("store_user_version", 6), ("backup_file", "../escape.sqlite"), ("format", "other")):
        bad = dict(manifest, **{field: value})
        target = result.rollback_manifest + "." + field + ".json"
        with open(target, "wb") as handle:
            handle.write(json.dumps(bad).encode("utf-8"))
        raises_kind("backup", restore_rollback_point, path, target)
    with open(result.rollback_manifest + ".extra.json", "wb") as handle:
        handle.write(json.dumps(dict(manifest, extra=1)).encode("utf-8"))
    raises_kind("backup", restore_rollback_point, path, result.rollback_manifest + ".extra.json")
    other, _ = old_store(tmp_path, "other.db")
    foreign = migrate_pipeline(other).rollback_manifest      # a valid point, but of another store
    raises_kind("backup", restore_rollback_point, path, foreign)
    assert dump(path) == migrated


def test_concurrent_migration_is_refused_by_the_lock(tmp_path):
    path, _ = old_store(tmp_path)
    before = dump(path)
    with MigrationLock(path) as held:
        raises_kind("locked", migrate_pipeline, path)
        raises_kind("locked", restore_rollback_point, path, os.path.join(path + pm.ROLLBACK_SUFFIX, "x.manifest.json"))
        assert os.path.exists(path + pm.LOCK_SUFFIX)          # the refused caller did not remove the holder's lock
        raises_kind("locked", pm.clear_stale_lock, path, "wrong-token")
        assert os.path.exists(path + pm.LOCK_SUFFIX)
        token = held.token
    assert not os.path.exists(path + pm.LOCK_SUFFIX)          # released on exit
    assert dump(path) == before
    # a lock left by a dead process needs its token to be cleared
    with open(path + pm.LOCK_SUFFIX, "wb") as handle:
        handle.write(json.dumps({"pid": 1, "token": token}).encode("ascii"))
    raises_kind("locked", migrate_pipeline, path)
    pm.clear_stale_lock(path, token)
    assert not os.path.exists(path + pm.LOCK_SUFFIX)
    assert migrate_pipeline(path).performed is True


def test_two_simultaneous_migrations_apply_the_change_once(tmp_path):
    path, _ = old_store(tmp_path)
    outcomes, barrier = [], threading.Barrier(2)

    def worker():
        barrier.wait(timeout=30)
        try:
            outcomes.append(("ok", migrate_pipeline(path)))
        except MigrationError as exc:
            outcomes.append(("error", exc))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert len(outcomes) == 2
    performed = [o[1] for o in outcomes if o[0] == "ok" and o[1].performed]
    assert len(performed) == 1
    assert all(o[1].kind == "locked" for o in outcomes if o[0] == "error")
    assert migration_status(path)["state"] == "CURRENT" and len(manifests(path)) == 1
    assert not os.path.exists(path + pm.LOCK_SUFFIX)
