"""S5 VST integration journey across the durable Store and authoritative Gate.

These tests use deterministic, local synthetic analyzer evidence. They exercise
VST receipt persistence and gate verification; they do not execute AEVE.
"""

from __future__ import annotations

import copy
import hashlib
import json

from tests.vst.e1e4_helpers import (
    EPOCH,
    HEAD,
    KEY,
    OPERATOR_KEY,
    STORY,
    SUPERVISOR_KEY,
    TASK,
    FakeClock,
)
from tests.vst.test_s5_v3_evidence import (
    ANALYZER_KEY,
    ANALYZER_KEY_ID,
    EVENT_KEY,
    REVIEWER_KEY,
    SIGNER_KEY,
    EVIDENCE_DIGEST,
    analyzer_receipt,
    gate_inputs,
    resign_analyzer,
    v3_manifest,
)
from tools.vst import contracts, gate, source_tree
from tools.vst.signing import sign, REVIEWER_REGISTRY_LABEL
from tools.vst.store import Store


def _stored_v3_receipt(tmp_path, *, candidate_head=HEAD, findings=None):
    manifest = v3_manifest(acceptance_ids=("AC-2",))
    manifest, reviewer_registry = gate_inputs(manifest)
    db_path = tmp_path / "state.sqlite"
    store = Store(str(db_path), FakeClock(), event_key=EVENT_KEY)
    store.init_slots(2)
    store.open_story(STORY, "proj", 4)
    epoch = store.acquire_epoch(STORY, "owner-a", 100)
    assert epoch == EPOCH
    manifest_digest = store.register_task(manifest)

    source_root = tmp_path / "candidate"
    (source_root / "src").mkdir(parents=True)
    (source_root / "src" / "app.py").write_bytes(b"synthetic candidate\n")
    source_digest = source_tree.source_tree_sha256(source_root, ["src/app.py"])

    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    report_path = artifact_root / "analysis.json"
    report_path.write_bytes(b'{"fixture":"s5-vst-e2e","findings":[]}\n')
    report_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    evidence_path = artifact_root / "evidence.json"
    evidence_path.write_bytes(b'{"fixture":"evidence"}\n')
    evidence_digest = hashlib.sha256(evidence_path.read_bytes()).hexdigest()

    receipt = analyzer_receipt(
        manifest,
        findings=copy.deepcopy(findings),
    )
    unsigned = {key: value for key, value in receipt.items() if key != "signature"}
    unsigned["candidate_head"] = candidate_head
    unsigned["manifest_sha256"] = manifest_digest
    unsigned["source_tree_sha256"] = source_digest
    unsigned["report_sha256"] = report_digest
    if findings:
        for finding in unsigned["findings"]:
            finding["evidence_sha256"] = evidence_digest
    receipt = resign_analyzer(unsigned)

    store.acquire_lease(
        TASK, STORY, "runner-1", epoch, 1, 30, supervisor_key=SUPERVISOR_KEY
    )
    store.append_receipt(receipt, STORY, ANALYZER_KEY)
    persisted = store.receipts_for_task(TASK)
    assert persisted == [receipt]

    def artifact_resolver(relative_path):
        if relative_path == "reports/analysis.json":
            return hashlib.sha256(report_path.read_bytes()).hexdigest()
        if relative_path == "reports/evidence.json":
            return hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        return None

    def source_resolver(candidate, scope):
        assert candidate == receipt["candidate_head"]
        return source_tree.source_tree_sha256(source_root, scope)

    return store, manifest, reviewer_registry, persisted, artifact_resolver, source_resolver


def _evaluate(manifest, reviewer_registry, receipts, artifact_resolver, source_resolver, *, head=HEAD):
    return gate.evaluate(
        manifest,
        receipts,
        head,
        EPOCH,
        KEY,
        supervisor_key=SUPERVISOR_KEY,
        operator_key=OPERATOR_KEY,
        reviewer_registry=reviewer_registry,
        reviewer_keys={"reviewer-key-1": REVIEWER_KEY},
        signer_key=SIGNER_KEY,
        event_key=EVENT_KEY,
        analyzer_keys={ANALYZER_KEY_ID: ANALYZER_KEY},
        artifact_resolver=artifact_resolver,
        source_tree_resolver=source_resolver,
    )


def test_s5_store_round_trips_v3_receipt_and_gate_accepts_only_static_acceptance(tmp_path):
    store, manifest, reviewer_registry, receipts, artifact_resolver, source_resolver = (
        _stored_v3_receipt(tmp_path)
    )
    try:
        assert receipts[0]["contract_version"] == 3
        assert receipts[0]["receipt_type"] == "StaticAnalysis"
        assert contracts.receipt_sha256(receipts[0])
        decision = _evaluate(
            manifest, reviewer_registry, receipts, artifact_resolver, source_resolver
        )
        assert "AC-2" not in decision["acceptance_unmet"]
        assert "AC-1" in decision["acceptance_unmet"]
        assert decision["verdict"] != "APPROVE"  # Test and review evidence is absent.
        assert any("missing receipt for slot" in reason for reason in decision["reasons"])
    finally:
        store.close()


def test_s5_store_persisted_stale_v3_receipt_does_not_satisfy_current_head(tmp_path):
    store, manifest, reviewer_registry, receipts, artifact_resolver, source_resolver = (
        _stored_v3_receipt(tmp_path, candidate_head="f" * 40)
    )
    try:
        decision = _evaluate(
            manifest, reviewer_registry, receipts, artifact_resolver, source_resolver, head=HEAD
        )
        assert decision["verdict"] != "APPROVE"
        assert "AC-2" in decision["acceptance_unmet"]
        assert any("stale head" in reason for reason in decision["reasons"])
    finally:
        store.close()


def test_s5_store_persisted_finding_remains_failure_at_authoritative_gate(tmp_path):
    finding = {
        "finding_id": "F-1",
        "rule_id": "R1",
        "severity": "HIGH",
        "evidence_path": "reports/evidence.json",
        "evidence_sha256": EVIDENCE_DIGEST,
        "path": "src/app.py",
        "line": 1,
    }
    store, manifest, reviewer_registry, receipts, artifact_resolver, source_resolver = (
        _stored_v3_receipt(tmp_path, findings=[finding])
    )
    try:
        assert receipts[0]["result"] == "FAIL"
        decision = _evaluate(
            manifest, reviewer_registry, receipts, artifact_resolver, source_resolver
        )
        assert decision["verdict"] != "APPROVE"
        assert "AC-2" in decision["acceptance_unmet"]
        assert any("FAIL" in reason or "finding" in reason.lower() for reason in decision["reasons"])
    finally:
        store.close()
