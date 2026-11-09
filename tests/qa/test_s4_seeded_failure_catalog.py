"""S4-E bounded synthetic seeded-failure fixture catalog (S4.5.2, AC-12, AC-13).

Each fixture in tests/qa/seeded_failure/catalog.json is a controlled INPUT RECORD that is
fed to the UNCHANGED product interface (tools.vst gate / diffgate / store, and the QA
accounting function tools.qa.run._resolve_cases). The test asserts the observed rejection
equals the committed expected_rejection and is non-approving. The catalog pins each input
by the sha256 of its canonical JSON, so an edited fixture cannot drift silently.

This is NOT mutation testing. No product source is patched, monkeypatched or edited, and no
real failing product test is relabeled as a seed. The module proves only that these eight
fixtures are rejected by the product interface as recorded; it makes no claim about any
other defect class. Temp dirs only, no network.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1]))  # repo root (tools.*)
sys.path.insert(0, str(_HERE.parent))  # tests/ (vst.e1e4_helpers)

from tools.qa import run as qa_run  # noqa: E402
from tools.vst import contracts as c  # noqa: E402
from tools.vst import diffgate, gate  # noqa: E402
from vst.e1e4_helpers import (  # noqa: E402
    EPOCH, HEAD, HEAD2, KEY, OPERATOR_KEY, SUPERVISOR_KEY, WRONG_KEY, FakeClock,
    happy_receipts, manifest, mhash, open_store, receipt,
)

CATALOG_PATH = _HERE / "seeded_failure" / "catalog.json"
APPROVING = {"APPROVE", "APPROVED_WITH_WAIVER", "PASS"}
ART = "a" * 64
M = manifest()


# ------------------------------------------------------------------ helpers

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def input_digest(record) -> str:
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _entry(fixture_id: str) -> dict:
    return next(e for e in _catalog()["fixtures"] if e["fixture_id"] == fixture_id)


def _evaluate(receipts, *, head=HEAD, epoch=EPOCH, resolver=None):
    return gate.evaluate(
        M, receipts, head, epoch, KEY,
        supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY, artifact_resolver=resolver,
    )


def _gate_observation(decision: dict, reason_fragment: str) -> str:
    """'<VERDICT>: <fragment>' where the fragment must appear in the gate reasons."""
    joined = " | ".join(decision["reasons"])
    assert reason_fragment in joined, joined
    return f"{decision['verdict']}: {reason_fragment}"


def _check(fixture_id: str, record, observed: str, verdict: str) -> None:
    entry = _entry(fixture_id)
    assert input_digest(record) == entry["input_sha256"], "catalog input drifted"
    assert verdict not in APPROVING
    assert observed == entry["expected_rejection"]


# ------------------------------------------------------- input record builders

def record_sf001() -> dict:  # stale HEAD: receipts bound to HEAD, gate evaluates HEAD2
    return {"gate_head": HEAD2, "receipts": happy_receipts()}


def record_sf002() -> dict:  # review receipt absent
    return {"receipts": [r for r in happy_receipts() if r["slot"] != "review"]}


def record_sf003() -> dict:  # TestRun receipt signed with a key that is not the worker key
    return {"receipts": [receipt("TestRun", key=WRONG_KEY), receipt("StaticAnalysis"),
                         receipt("IndependentReview")]}


def record_sf004() -> dict:  # diff touches a path outside change_scope.allowed_paths
    return {
        "manifest_sha256": mhash(M), "base_head": HEAD, "candidate_head": HEAD2,
        "changed_paths": ["src/app.py", "src/other.py"], "allowed_paths": ["src/app.py"],
        "diff_text": "diff --git a/src/other.py b/src/other.py\n+evil\n",
    }


def record_sf005() -> dict:  # required selector T-REQ reported skipped by pytest events
    return {
        "expected_ids": ["T-REQ"],
        "selectors": {"T-REQ": {"selector": "tests/qa/test_x.py::test_required"}},
        "events": {"collected": [{
            "node_id": "tests/qa/test_x.py::test_required",
            "selector": "T-REQ", "outcome": "skipped"}]},
    }


def record_sf006() -> dict:  # receipt claims artifact digest ART; artifact on disk differs
    return {"artifact_path": "out/report.txt", "claimed_sha256": ART,
            "artifact_bytes_hex": b"tampered artifact".hex(),
            "receipts": [receipt("TestRun", artifact_digests={"out/report.txt": ART}),
                         receipt("StaticAnalysis"), receipt("IndependentReview")]}


def record_sf007() -> dict:  # event row payload edited after the chain was written
    return {"event_key_label": "EVENT_KEY", "events": [["NOTE", {"n": 1}], ["NOTE", {"n": 2}]],
            "tamper_sql": ["DROP TRIGGER events_no_update",
                          "UPDATE events SET payload = '{\"n\":999}' WHERE seq = 2"]}


def record_sf008() -> dict:  # all receipts from an older epoch, gate in the current epoch
    return {"gate_epoch": EPOCH, "receipt_epoch": EPOCH - 1,
            "receipts": [receipt("TestRun", epoch=EPOCH - 1),
                         receipt("StaticAnalysis", epoch=EPOCH - 1),
                         receipt("IndependentReview", epoch=EPOCH - 1)]}


# ------------------------------------------------------------ product callers

def run_sf001():
    rec = record_sf001()
    d = _evaluate(rec["receipts"], head=rec["gate_head"])
    return rec, _gate_observation(d, "stale head"), d["verdict"]


def run_sf002():
    rec = record_sf002()
    d = _evaluate(rec["receipts"])
    return rec, _gate_observation(d, "missing receipt for slot 'review'"), d["verdict"]


def run_sf003():
    rec = record_sf003()
    d = _evaluate(rec["receipts"])
    return rec, _gate_observation(d, "invalid signature"), d["verdict"]


def run_sf004():
    rec = record_sf004()
    ev = diffgate.check_diff(
        manifest_sha256=rec["manifest_sha256"], base_head=rec["base_head"],
        candidate_head=rec["candidate_head"], changed_paths=rec["changed_paths"],
        allowed_paths=rec["allowed_paths"], diff_bytes=rec["diff_text"].encode("utf-8"))
    return rec, f"{ev['verdict']}: {ev['reason']}", ev["verdict"]


def run_sf005():
    rec = record_sf005()
    out = qa_run._resolve_cases(rec["events"], rec["expected_ids"], rec["selectors"])
    assert out["passed_test_ids"] == []
    assert out["skipped_test_ids"] == ["T-REQ"]
    return rec, "NOT_PASSED: skipped_test_ids=T-REQ", "PASSED" if out["passed_test_ids"] else "NOT_PASSED"


def run_sf006():
    rec = record_sf006()
    actual = hashlib.sha256(bytes.fromhex(rec["artifact_bytes_hex"])).hexdigest()
    assert actual != rec["claimed_sha256"]
    d = _evaluate(rec["receipts"], resolver=lambda p: actual)
    return rec, _gate_observation(d, "digest mismatch"), d["verdict"]


def run_sf007(tmp_path):
    rec = record_sf007()
    path = str(tmp_path / "chain.db")
    with open_store(path, FakeClock()) as s:
        for kind, payload in rec["events"]:
            s.record_event("T1", "actor", kind, payload)
        assert s.verify_event_chain() is True  # control: intact before tampering
    conn = sqlite3.connect(path)
    try:
        # offline attacker with file access: remove the append-only trigger, then edit a row
        conn.execute(rec["tamper_sql"][0])
        cur = conn.execute(rec["tamper_sql"][1])
        conn.commit()
        changed = cur.rowcount
    finally:
        conn.close()
    assert changed == 1
    with open_store(path, FakeClock()) as s:
        ok = s.verify_event_chain()
    return rec, f"verify_event_chain={ok}", "ACCEPTED" if ok else "REJECTED"


def run_sf008():
    rec = record_sf008()
    d = _evaluate(rec["receipts"], epoch=rec["gate_epoch"])
    return rec, _gate_observation(d, "slot 'tests' needs a current-epoch attempt"), d["verdict"]


# ---------------------------------------------------------------------- tests

def test_sf001_stale_head_evidence_is_not_approved():
    _check("SF-001", *run_sf001())


def test_sf002_missing_required_receipt_is_not_approved():
    _check("SF-002", *run_sf002())


def test_sf003_invalid_signature_receipt_is_not_approved():
    _check("SF-003", *run_sf003())


def test_sf004_out_of_scope_diff_fails_the_diff_gate():
    _check("SF-004", *run_sf004())


def test_sf005_skipped_required_test_id_is_not_counted_as_passed():
    _check("SF-005", *run_sf005())


def test_sf006_artifact_digest_mismatch_is_not_approved():
    _check("SF-006", *run_sf006())


def test_sf007_tampered_event_chain_fails_verification(tmp_path):
    _check("SF-007", *run_sf007(tmp_path))


def test_sf008_stale_epoch_receipts_are_not_approved():
    _check("SF-008", *run_sf008())


def test_catalog_shape_unique_ids_and_linked_tests_exist():
    cat = _catalog()
    fixtures = cat["fixtures"]
    assert len(fixtures) == 8
    ids = [e["fixture_id"] for e in fixtures]
    assert len(set(ids)) == 8
    required = {"fixture_id", "failure_class", "input_sha256", "expected_rejection", "test_id"}
    for e in fixtures:
        assert set(e) == required
        assert len(e["input_sha256"]) == 64
        assert e["expected_rejection"] and e["failure_class"]
    names = {n.name for n in ast.parse(Path(__file__).read_text(encoding="utf-8")).body
             if isinstance(n, ast.FunctionDef)}
    selectors = [e["test_id"] for e in fixtures]
    assert len(set(selectors)) == 8
    for sel in selectors:
        path, _, func = sel.partition("::")
        assert path == "tests/qa/test_s4_seeded_failure_catalog.py"
        assert func in names, sel


def _generate_catalog() -> dict:
    """Helper used once to write catalog.json from observed behavior (not a test)."""
    mod = "tests/qa/test_s4_seeded_failure_catalog.py::"
    plan = [
        ("SF-001", "stale-head-evidence", run_sf001, "test_sf001_stale_head_evidence_is_not_approved"),
        ("SF-002", "missing-required-receipt", run_sf002, "test_sf002_missing_required_receipt_is_not_approved"),
        ("SF-003", "invalid-signature", run_sf003, "test_sf003_invalid_signature_receipt_is_not_approved"),
        ("SF-004", "out-of-scope-diff", run_sf004, "test_sf004_out_of_scope_diff_fails_the_diff_gate"),
        ("SF-005", "skipped-required-test-id", run_sf005, "test_sf005_skipped_required_test_id_is_not_counted_as_passed"),
        ("SF-006", "artifact-digest-mismatch", run_sf006, "test_sf006_artifact_digest_mismatch_is_not_approved"),
        ("SF-007", "tampered-event-chain", None, "test_sf007_tampered_event_chain_fails_verification"),
        ("SF-008", "stale-epoch", run_sf008, "test_sf008_stale_epoch_receipts_are_not_approved"),
    ]
    import tempfile
    out = []
    for fid, cls, fn, tname in plan:
        if fn is None:
            with tempfile.TemporaryDirectory() as td:
                rec, obs, _ = run_sf007(Path(td))
        else:
            rec, obs, _ = fn()
        out.append({"fixture_id": fid, "failure_class": cls, "input_sha256": input_digest(rec),
                    "expected_rejection": obs, "test_id": mod + tname})
    return {"schema_version": 1, "note": "Synthetic seeded-failure fixtures; not mutation testing.",
            "fixtures": out}
