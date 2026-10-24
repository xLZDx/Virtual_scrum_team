"""S5 functional coverage for the opt-in v3 analyzer evidence contract."""

from __future__ import annotations

import copy
import hashlib
import os
from pathlib import Path

import pytest

from tests.vst.e1e4_helpers import (
    EPOCH,
    HEAD,
    KEY,
    OPERATOR_KEY,
    SUPERVISOR_KEY,
    manifest as v1_manifest,
    receipt as v1_receipt,
    unsigned_receipt,
)
from tests.vst.test_s2_contract_gate import _v2_manifest, _valid_v2_receipt
from tools.vst import contracts, gate, signing, source_tree
from tools.vst.contracts import ContractError


ANALYZER_KEY = b"analyzer-attestor-key-0123456789-abcdef"
REVIEWER_KEY = b"reviewer-key-0123456789-abcdefghij"
SIGNER_KEY = b"runner-signer-key-0123456789-abcdef"
EVENT_KEY = b"event-trust-key-0123456789-abcdefghij"
SOURCE_DIGEST = "a" * 64
REPORT_DIGEST = "b" * 64
EVIDENCE_DIGEST = "c" * 64
ANALYZER_ID = "analyzer-main"
ANALYZER_KEY_ID = "analyzer-key-1"
SCOPE = ["src/app.py"]


def v3_manifest(*, required_rules: tuple[str, ...] = ("R1",), acceptance_ids=("AC-2",)) -> dict:
    manifest = _v2_manifest()
    manifest["contract_version"] = 3
    manifest["required_rules"] = [
        {"slot": "static", "rule_id": rule_id} for rule_id in required_rules
    ]
    manifest["analysis_policy"] = {
        "slot": "static",
        "analyzer_key_id": ANALYZER_KEY_ID,
        "analyzer_id": ANALYZER_ID,
        "analyzer_version": "1.4.2",
        "analyzer_sha256": "d" * 64,
        "profile_id": "bounded-default",
        "profile_sha256": "e" * 64,
        "analysis_scope": list(SCOPE),
        "acceptance_ids": list(acceptance_ids),
        "source_tree_scheme": contracts.SOURCE_TREE_SCHEME,
    }
    registry_body = {
        "version": manifest["reviewer_registry"]["version"],
        "entries": [{"principal": "reviewer-x", "key_id": "reviewer-key-1"}],
    }
    manifest["reviewer_registry"]["sha256"] = hashlib.sha256(
        contracts.canonical_bytes(registry_body)
    ).hexdigest()
    return manifest


def analyzer_receipt(
    manifest: dict | None = None,
    *,
    analysis_rules: tuple[str, ...] = ("R1",),
    checked_rules: tuple[str, ...] = ("R1",),
    required_rules: tuple[str, ...] | None = None,
    findings: list[dict] | None = None,
    coverage: str | None = None,
    signature_key: bytes = ANALYZER_KEY,
    **overrides,
) -> dict:
    manifest = manifest or v3_manifest()
    policy = manifest["analysis_policy"]
    required = tuple(required_rules) if required_rules is not None else tuple(
        item["rule_id"] for item in manifest["required_rules"]
        if item["slot"] == policy["slot"]
    )
    checked = set(checked_rules)
    analysis = set(analysis_rules)
    unsupported = analysis - checked
    if coverage is None:
        required_unsupported = set(required) & unsupported
        required_checked = set(required) & checked
        coverage = (
            "FULL" if not required_unsupported
            else "PARTIAL" if required_checked
            else "NOT_COVERED"
        )
    run_id = "analysis-run-1"
    receipt = unsigned_receipt(
        "StaticAnalysis",
        contract_version=3,
        manifest_sha256=contracts.manifest_sha256(manifest),
        candidate_head=HEAD,
        epoch=EPOCH,
        invocation_id=run_id,
        analyzer_key_id=policy["analyzer_key_id"],
        analyzer_id=policy["analyzer_id"],
        analyzer_version=policy["analyzer_version"],
        analyzer_sha256=policy["analyzer_sha256"],
        profile_id=policy["profile_id"],
        profile_sha256=policy["profile_sha256"],
        source_tree_sha256=SOURCE_DIGEST,
        analysis_scope=list(policy["analysis_scope"]),
        source_tree_scheme=policy["source_tree_scheme"],
        report_path="reports/analysis.json",
        report_sha256=REPORT_DIGEST,
        analysis_run_id=run_id,
        analysis_rule_ids=list(analysis_rules),
        required_rule_ids=list(required),
        rule_statuses=[
            {"rule_id": rule_id,
             "status": "SUPPORTED_AND_CHECKED" if rule_id in checked else "UNSUPPORTED"}
            for rule_id in analysis_rules
        ],
        coverage=coverage,
        covered_rules=sorted(checked),
        unsupported_rules=sorted(unsupported),
        covered_acceptance=list(policy["acceptance_ids"]),
        findings=copy.deepcopy(findings or []),
        **overrides,
    )
    receipt["result"] = contracts.derive_result(receipt)
    receipt["signature"] = signing.sign(
        {key: value for key, value in receipt.items() if key != "signature"},
        signature_key,
        signing.ANALYZER_V3_LABEL,
    )
    return receipt


def gate_inputs(manifest: dict | None = None):
    manifest = manifest or v3_manifest()
    entries = [{"principal": "reviewer-x", "key_id": "reviewer-key-1"}]
    registry_body = {"version": manifest["reviewer_registry"]["version"], "entries": entries}
    manifest["reviewer_registry"]["sha256"] = hashlib.sha256(
        contracts.canonical_bytes(registry_body)
    ).hexdigest()
    registry = dict(registry_body)
    registry["signature"] = signing.sign(registry, OPERATOR_KEY, signing.REVIEWER_REGISTRY_LABEL)
    return manifest, registry


def evaluate_analyzer(
    receipt: dict,
    *,
    manifest: dict | None = None,
    analyzer_key: bytes = ANALYZER_KEY,
    artifact_resolver=None,
    source_tree_resolver=None,
    current_head: str = HEAD,
    current_epoch: int = EPOCH,
    receipts: list[dict] | None = None,
) -> dict:
    manifest, reviewer_registry = gate_inputs(manifest)
    if artifact_resolver is None:
        artifact_resolver = lambda path: {
            "reports/analysis.json": REPORT_DIGEST,
            "reports/evidence.json": EVIDENCE_DIGEST,
        }.get(path)
    if source_tree_resolver is None:
        source_tree_resolver = lambda head, scope: SOURCE_DIGEST
    return gate.evaluate(
        manifest,
        list(receipts) if receipts is not None else [receipt],
        current_head,
        current_epoch,
        KEY,
        supervisor_key=SUPERVISOR_KEY,
        operator_key=OPERATOR_KEY,
        reviewer_registry=reviewer_registry,
        reviewer_keys={"reviewer-key-1": REVIEWER_KEY},
        signer_key=SIGNER_KEY,
        event_key=EVENT_KEY,
        analyzer_keys={ANALYZER_KEY_ID: analyzer_key},
        artifact_resolver=artifact_resolver,
        source_tree_resolver=source_tree_resolver,
    )


def resign_analyzer(receipt: dict, key: bytes = ANALYZER_KEY) -> dict:
    unsigned = {name: value for name, value in receipt.items() if name != "signature"}
    return {**unsigned, "signature": signing.sign(unsigned, key, signing.ANALYZER_V3_LABEL)}


def test_v1_v2_manifest_and_signed_receipt_golden_hashes_remain_unchanged():
    v1_m = v1_manifest()
    v1_r = v1_receipt()
    v2_m = _v2_manifest()
    v2_r = _valid_v2_receipt("TestRun")

    assert contracts.manifest_sha256(v1_m) == "c9ae62f530a28a7fe646ba35e30b2cb8e7b713726115e04647eb9bd61a4248f9"
    assert contracts.receipt_sha256(v1_r) == "03915b97115b52c815110092ed67648e596dfc80f9e95c055a46b146c1bc1f9a"
    assert v1_r["signature"] == "79cb83a1b275c70b7b0e60d3676c18a7e4904e08344ddd37d903caf25f87892b"
    assert contracts.manifest_sha256(v2_m) == "5204a3f36fab0c0ef1e1971353d9e23690be97dc0d0f5a292c5cc89e88566184"
    assert contracts.receipt_sha256(v2_r) == "16fc200d4d4aca667681fef138197014d52c51a1589376dbdec34170fad2f856"
    assert v2_r["signature"] == "4e99854fd0806c719eb1ed880f73fb228d35c8a9030b9e9ad136b0ba1860a75c"
    assert contracts.validate_task_manifest(v1_m) == v1_m
    assert contracts.validate_task_manifest(v2_m) == v2_m
    assert contracts.validate_receipt(v1_r) == v1_r
    assert contracts.validate_receipt(v2_r) == v2_r


def test_v2_manifest_cannot_be_upgraded_with_v3_analyzer_policy():
    manifest = _v2_manifest()
    manifest["analysis_policy"] = v3_manifest()["analysis_policy"]
    with pytest.raises(ContractError, match=r"unknown field\(s\): analysis_policy"):
        contracts.validate_task_manifest(manifest)


@pytest.mark.parametrize("mutation, expected", [
    ("missing", "missing field"),
    ("extra", "unknown field"),
    ("wrong_version", "analysis_policy"),
    ("bad_digest", "analyzer_sha256"),
    ("bad_scope", "analysis_scope"),
    ("bad_acceptance", "acceptance_ids"),
    ("bad_scheme", "source_tree_scheme"),
])
def test_v3_manifest_rejects_malformed_or_unbound_policy(mutation, expected):
    manifest = v3_manifest()
    if mutation == "missing":
        del manifest["analysis_policy"]["profile_sha256"]
    elif mutation == "extra":
        manifest["analysis_policy"]["unexpected"] = True
    elif mutation == "wrong_version":
        manifest["contract_version"] = 2
    elif mutation == "bad_digest":
        manifest["analysis_policy"]["analyzer_sha256"] = "not-a-digest"
    elif mutation == "bad_scope":
        manifest["analysis_policy"]["analysis_scope"] = ["../outside.py"]
    elif mutation == "bad_acceptance":
        manifest["analysis_policy"]["acceptance_ids"] = ["AC-UNKNOWN"]
    elif mutation == "bad_scheme":
        manifest["analysis_policy"]["source_tree_scheme"] = "unversioned"

    with pytest.raises(ContractError, match=expected):
        contracts.validate_task_manifest(manifest)


def test_v3_receipt_requires_exact_rule_partition_and_derived_coverage():
    baseline = analyzer_receipt(analysis_rules=("R1", "R2"), checked_rules=("R1",))
    assert contracts.validate_receipt(baseline) == baseline
    assert baseline["coverage"] == "FULL"  # R2 is optional and unsupported.
    assert baseline["result"] == "PASS"

    omitted = copy.deepcopy(baseline)
    omitted["rule_statuses"].pop()
    with pytest.raises(ContractError, match="exactly match analysis_rule_ids"):
        contracts.validate_receipt(omitted)

    duplicate = copy.deepcopy(baseline)
    duplicate["rule_statuses"].append(dict(duplicate["rule_statuses"][0]))
    with pytest.raises(ContractError, match="duplicate rule status"):
        contracts.validate_receipt(duplicate)

    contradictory = copy.deepcopy(baseline)
    contradictory["covered_rules"].append("R2")
    with pytest.raises(ContractError, match="must match rule_statuses"):
        contracts.validate_receipt(contradictory)

    lying_coverage = copy.deepcopy(baseline)
    lying_coverage["coverage"] = "PARTIAL"
    with pytest.raises(ContractError, match="coverage: must be FULL"):
        contracts.validate_receipt(lying_coverage)


def test_v3_receipt_rejects_missing_extra_and_inconsistent_provenance_fields():
    receipt = analyzer_receipt()
    missing = copy.deepcopy(receipt)
    del missing["profile_sha256"]
    with pytest.raises(ContractError, match="missing field.*profile_sha256"):
        contracts.validate_receipt(missing)

    extra = copy.deepcopy(receipt)
    extra["untrusted_claim"] = "ignored?"
    with pytest.raises(ContractError, match="unknown field.*untrusted_claim"):
        contracts.validate_receipt(extra)

    wrong_run = copy.deepcopy(receipt)
    wrong_run["analysis_run_id"] = "other-run"
    with pytest.raises(ContractError, match="must equal the signed invocation_id"):
        contracts.validate_receipt(wrong_run)


def test_v3_required_unsupported_rule_is_non_approving():
    manifest = v3_manifest(required_rules=("R1", "R2"))
    receipt = analyzer_receipt(
        manifest,
        analysis_rules=("R1", "R2"),
        checked_rules=("R1",),
    )
    validated = contracts.validate_receipt(receipt)
    assert validated["coverage"] == "PARTIAL"
    assert validated["result"] == "INCONCLUSIVE"

    uncovered_manifest = v3_manifest(required_rules=("R1",))
    uncovered = analyzer_receipt(
        uncovered_manifest,
        analysis_rules=("R1", "R2"),
        checked_rules=("R2",),
    )
    uncovered_valid = contracts.validate_receipt(uncovered)
    assert uncovered_valid["coverage"] == "NOT_COVERED"
    assert uncovered_valid["result"] == "INCONCLUSIVE"


def test_v3_finding_is_typed_in_scope_and_derives_failure():
    finding = {
        "finding_id": "F-1",
        "rule_id": "R1",
        "severity": "HIGH",
        "evidence_path": "reports/evidence.json",
        "evidence_sha256": EVIDENCE_DIGEST,
        "path": "src/app.py",
        "line": 7,
    }
    receipt = analyzer_receipt(findings=[finding])
    assert contracts.validate_receipt(receipt)["result"] == "FAIL"
    decision = evaluate_analyzer(receipt)
    assert decision["verdict"] != "APPROVE"
    assert any(
        "analysis finding: F-1 R1 HIGH src/app.py:7" in finding_text
        for finding_text in decision["unresolved_findings"]
    )

    outside_scope = copy.deepcopy(receipt)
    outside_scope["findings"][0]["path"] = "src/other.py"
    with pytest.raises(ContractError, match="included in analysis_scope"):
        contracts.validate_receipt(outside_scope)

    bad_severity = copy.deepcopy(receipt)
    bad_severity["findings"][0]["severity"] = "SEVERE"
    with pytest.raises(ContractError, match="severity"):
        contracts.validate_receipt(bad_severity)

    duplicate = copy.deepcopy(receipt)
    duplicate["findings"].append(dict(duplicate["findings"][0]))
    with pytest.raises(ContractError, match="duplicate finding ID"):
        contracts.validate_receipt(duplicate)


@pytest.mark.parametrize("signature_role", ["worker", "supervisor", "operator", "signer", "event", "reviewer"])
def test_analyzer_receipt_rejects_every_non_analyzer_signature_root(signature_role):
    other_roots = {
        "worker": KEY,
        "supervisor": SUPERVISOR_KEY,
        "operator": OPERATOR_KEY,
        "signer": SIGNER_KEY,
        "event": EVENT_KEY,
        "reviewer": REVIEWER_KEY,
    }
    receipt = analyzer_receipt(signature_key=other_roots[signature_role])

    decision = evaluate_analyzer(receipt)
    assert decision["verdict"] != "APPROVE"
    assert any("invalid signature" in reason for reason in decision["reasons"])


def test_analyzer_receipt_signature_requires_its_domain_label():
    receipt = analyzer_receipt()
    body = {key: value for key, value in receipt.items() if key != "signature"}
    receipt["signature"] = signing.sign(body, ANALYZER_KEY, signing.RECEIPT_V2_LABEL)

    decision = evaluate_analyzer(receipt)
    assert decision["verdict"] != "APPROVE"
    assert any("invalid signature" in reason for reason in decision["reasons"])


def test_exact_v3_analyzer_receipt_contributes_only_policy_acceptance():
    manifest = v3_manifest(acceptance_ids=("AC-2",))
    receipt = analyzer_receipt(manifest)
    decision = evaluate_analyzer(receipt, manifest=manifest)

    assert decision["verdict"] != "APPROVE"  # TestRun/review receipts are still absent.
    assert "AC-2" not in decision["acceptance_unmet"]
    assert "AC-1" in decision["acceptance_unmet"]
    assert any("missing receipt for slot 'tests'" in reason for reason in decision["reasons"])


@pytest.mark.parametrize("mutation", [
    "head", "manifest", "analyzer_id", "analyzer_digest", "profile", "scope",
    "source_digest", "report", "epoch",
])
def test_v3_gate_rejects_replayed_or_policy_mismatched_evidence(mutation):
    manifest = v3_manifest()
    receipt = analyzer_receipt(manifest)
    receipt.pop("signature")
    if mutation == "head":
        receipt["candidate_head"] = "f" * 40
    elif mutation == "manifest":
        receipt["manifest_sha256"] = "f" * 64
    elif mutation == "analyzer_id":
        receipt["analyzer_id"] = "untrusted-analyzer"
    elif mutation == "analyzer_digest":
        receipt["analyzer_sha256"] = "f" * 64
    elif mutation == "profile":
        receipt["profile_sha256"] = "f" * 64
    elif mutation == "report":
        receipt["report_sha256"] = "f" * 64
    elif mutation == "scope":
        receipt["analysis_scope"] = ["src/other.py"]
    elif mutation == "source_digest":
        receipt["source_tree_sha256"] = "f" * 64
    elif mutation == "epoch":
        receipt["epoch"] = EPOCH - 1
    receipt = resign_analyzer(receipt)

    decision = evaluate_analyzer(receipt, manifest=manifest)
    assert decision["verdict"] != "APPROVE"
    if mutation == "head":
        assert any("stale head" in reason for reason in decision["reasons"])
    elif mutation == "manifest":
        assert any("manifest_sha256 does not match" in reason for reason in decision["reasons"])
    elif mutation in {"analyzer_id", "analyzer_digest", "profile", "scope"}:
        assert any("provenance does not match manifest policy" in reason for reason in decision["reasons"])
    elif mutation == "report":
        assert any("report artifact digest does not match" in reason for reason in decision["reasons"])
    elif mutation == "source_digest":
        assert any("source-tree digest does not match" in reason for reason in decision["reasons"])
    elif mutation == "epoch":
        assert any("current-epoch attempt" in reason for reason in decision["reasons"])


@pytest.mark.parametrize("resolver_case", [
    "missing", "wrong_digest", "raises",
])
def test_v3_gate_fails_closed_when_report_or_source_resolver_is_unavailable(resolver_case):
    receipt = analyzer_receipt()
    if resolver_case == "missing":
        manifest, reviewer_registry = gate_inputs(v3_manifest())
        decision = gate.evaluate(
            manifest, [receipt], HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
            operator_key=OPERATOR_KEY, reviewer_registry=reviewer_registry,
            reviewer_keys={"reviewer-key-1": REVIEWER_KEY}, signer_key=SIGNER_KEY,
            event_key=EVENT_KEY, analyzer_keys={ANALYZER_KEY_ID: ANALYZER_KEY},
        )
        assert decision["verdict"] != "APPROVE"
        assert any("no artifact_resolver" in reason or "no source_tree_resolver" in reason
                   for reason in decision["reasons"])
        return
    if resolver_case == "wrong_digest":
        artifact_resolver = lambda path: "f" * 64
        source_tree_resolver = lambda head, scope: "f" * 64
    else:
        def artifact_resolver(path):
            raise OSError("fixture artifact unavailable")

        source_tree_resolver = lambda head, scope: SOURCE_DIGEST

    decision = evaluate_analyzer(
        receipt,
        artifact_resolver=artifact_resolver,
        source_tree_resolver=source_tree_resolver,
    )
    assert decision["verdict"] != "APPROVE"
    if resolver_case == "wrong_digest":
        assert any("report artifact digest does not match" in reason for reason in decision["reasons"])
    else:
        assert any("report artifact resolver failed" in reason for reason in decision["reasons"])


def test_v3_gate_fails_closed_when_source_resolver_raises_or_mismatches():
    receipt = analyzer_receipt()
    decision = evaluate_analyzer(
        receipt, source_tree_resolver=lambda head, scope: "f" * 64
    )
    assert decision["verdict"] != "APPROVE"
    assert any("source-tree digest does not match" in reason for reason in decision["reasons"])

    def broken_source(head, scope):
        raise OSError("snapshot unavailable")

    decision = evaluate_analyzer(receipt, source_tree_resolver=broken_source)
    assert decision["verdict"] != "APPROVE"
    assert any("source-tree resolver failed" in reason for reason in decision["reasons"])

    manifest, reviewer_registry = gate_inputs(v3_manifest())
    decision = gate.evaluate(
        manifest, [receipt], HEAD, EPOCH, KEY, supervisor_key=SUPERVISOR_KEY,
        operator_key=OPERATOR_KEY, reviewer_registry=reviewer_registry,
        reviewer_keys={"reviewer-key-1": REVIEWER_KEY}, signer_key=SIGNER_KEY,
        event_key=EVENT_KEY, analyzer_keys={ANALYZER_KEY_ID: ANALYZER_KEY},
        artifact_resolver=lambda path: {
            "reports/analysis.json": REPORT_DIGEST,
            "reports/evidence.json": EVIDENCE_DIGEST,
        }.get(path),
    )
    assert decision["verdict"] != "APPROVE"
    assert any("no source_tree_resolver" in reason for reason in decision["reasons"])


def test_v3_gate_rejects_replayed_receipt_attempt():
    receipt = analyzer_receipt()
    decision = evaluate_analyzer(receipt, receipts=[receipt, copy.deepcopy(receipt)])
    assert decision["verdict"] != "APPROVE"
    assert any("attempts [1, 1] are not consecutive" in reason for reason in decision["reasons"])


def test_v3_gate_rechecks_finding_evidence_artifact_digest():
    finding = {
        "finding_id": "F-1",
        "rule_id": "R1",
        "severity": "HIGH",
        "evidence_path": "reports/evidence.json",
        "evidence_sha256": EVIDENCE_DIGEST,
        "path": "src/app.py",
        "line": 7,
    }
    receipt = analyzer_receipt(findings=[finding])
    decision = evaluate_analyzer(
        receipt,
        artifact_resolver=lambda path: (
            REPORT_DIGEST if path == "reports/analysis.json" else "f" * 64
        ),
    )
    assert decision["verdict"] != "APPROVE"
    assert any("finding evidence digest does not match" in reason for reason in decision["reasons"])


def test_source_tree_digest_is_order_independent_and_changes_with_content(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_bytes(b"alpha\n")
    (tmp_path / "src" / "b.py").write_bytes(b"beta\n")
    paths = ["src/a.py", "src/b.py"]

    first = source_tree.source_tree_sha256(tmp_path, paths)
    reordered = source_tree.source_tree_sha256(tmp_path, list(reversed(paths)))
    assert first == reordered

    (tmp_path / "src" / "a.py").write_bytes(b"changed\n")
    assert source_tree.source_tree_sha256(tmp_path, paths) != first


def test_source_tree_digest_rejects_traversal_missing_and_byte_bound(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_bytes(b"123")

    with pytest.raises(ContractError, match="invalid path segment"):
        source_tree.source_tree_sha256(tmp_path, ["../outside.py"])
    with pytest.raises(ContractError, match="cannot hash"):
        source_tree.source_tree_sha256(tmp_path, ["src/missing.py"])
    with pytest.raises(ContractError, match="exceeds 2 bytes"):
        source_tree.source_tree_sha256(tmp_path, ["src/app.py"], max_total_bytes=2)
    with pytest.raises(ContractError, match="exceeds 4096 files"):
        source_tree.source_tree_sha256(tmp_path, [f"missing/{i}.py" for i in range(4097)])


def test_source_tree_digest_rejects_symlink_scope(tmp_path):
    target = tmp_path / "actual.py"
    target.write_bytes(b"immutable")
    link = tmp_path / "linked.py"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(
            "symlink creation is unavailable in this Windows environment: "
            f"{type(exc).__name__}, winerror={getattr(exc, 'winerror', None)}, "
            f"errno={getattr(exc, 'errno', None)}"
        )

    with pytest.raises(ContractError, match="symbolic link"):
        source_tree.source_tree_sha256(tmp_path, ["linked.py"])


def test_source_tree_digest_detects_file_mutation_during_read(monkeypatch, tmp_path):
    target = tmp_path / "changing.py"
    target.write_bytes(b"before")
    original_read = os.read
    mutated = False

    def mutate_after_read(fd, count):
        nonlocal mutated
        data = original_read(fd, count)
        if not mutated:
            before = os.fstat(fd)
            target.write_bytes(b"after!")
            os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
            mutated = True
        return data

    monkeypatch.setattr(source_tree.os, "read", mutate_after_read)
    with pytest.raises(ContractError, match="file changed while hashing"):
        source_tree.source_tree_sha256(tmp_path, ["changing.py"])

