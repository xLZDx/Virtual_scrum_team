"""Local runner-to-gate E2E journeys for exact IDs and signed artifacts.

These fixtures use the existing local HMAC runner and gate APIs. They do not
exercise the report-bound QA CLI, deployed signer service, or sandbox boundary.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from tools.qa.registry import load_registry
from tools.vst import gate, runner
from tests.vst.e1e4_helpers import (
    EPOCH, HEAD, HEAD2, KEY, SUPERVISOR_KEY, bound, manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _parse_pass_lines(stdout: str) -> tuple[list[str], list[str], list[str]]:
    executed = [
        line.removeprefix("PASSED ").strip()
        for line in stdout.splitlines()
        if line.startswith("PASSED ")
    ]
    return executed, [], []


def _signed_run_with_artifact(workdir: Path) -> tuple[dict, dict, Path]:
    artifact = workdir / "evidence.json"
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; Path('evidence.json').write_text('{\\\"state\\\":\\\"PASS\\\"}'); "
        "print('PASSED t1'); print('PASSED t2')",
    ]
    manifest_obj = manifest(allowed_commands=[{"slot": "tests", "argv": command}])
    test_receipt = runner.run_and_sign(
        manifest=manifest_obj,
        slot="tests",
        attempt=1,
        epoch=EPOCH,
        candidate_head=HEAD,
        resolved_model="fixture-model",
        invocation_id="s4-e2e-local-artifact",
        runner_id="fixture-runner",
        key=KEY,
        commands=[command],
        expected_test_ids=["t1", "t2"],
        test_result_parser=_parse_pass_lines,
        covered_acceptance=["AC-1"],
        artifact_paths=["evidence.json"],
        prev_receipt_sha256=None,
        cwd=str(workdir),
        created_at="2026-10-25T00:00:00Z",
    )
    return manifest_obj, test_receipt, artifact


def _gate(manifest_obj: dict, test_receipt: dict, artifact: Path, *, head: str = HEAD) -> dict:
    def resolve_artifact(relative_path: str) -> str | None:
        if relative_path != "evidence.json" or not artifact.is_file():
            return None
        return hashlib.sha256(artifact.read_bytes()).hexdigest()

    receipts = [
        test_receipt,
        bound(manifest_obj, "StaticAnalysis"),
        bound(manifest_obj, "IndependentReview"),
    ]
    return gate.evaluate(
        manifest_obj, receipts, head, EPOCH, KEY,
        supervisor_key=SUPERVISOR_KEY,
        artifact_resolver=resolve_artifact,
    )


def test_s4_native_pytest_discovery_accounts_exact_required_ids():
    registry, _registry_hash = load_registry(REPO_ROOT)
    expected_ids = sorted(registry["categories"]["e2e"]["test_ids"])
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        [
            sys.executable, "-m", "pytest", "--collect-only", "-q",
            "-p", "no:cacheprovider", *expected_ids,
        ],
        cwd=REPO_ROOT, env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, timeout=60, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    collected_ids = [
        line.strip() for line in completed.stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    ]
    assert collected_ids == expected_ids
    assert f"{len(expected_ids)} tests collected" in completed.stdout


def test_s4_signed_runner_receipt_and_artifact_gate_approve_at_exact_head(tmp_path):
    manifest_obj, receipt, artifact = _signed_run_with_artifact(tmp_path)
    expected_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert receipt["artifact_digests"]["evidence.json"] == expected_digest
    decision = _gate(manifest_obj, receipt, artifact)
    assert decision["verdict"] == "APPROVE", decision["reasons"]


def test_s4_gate_rejects_stale_signed_runner_receipt(tmp_path):
    manifest_obj, receipt, artifact = _signed_run_with_artifact(tmp_path)
    decision = _gate(manifest_obj, receipt, artifact, head=HEAD2)
    assert decision["verdict"] == "NO_GO"
    assert any("stale head" in reason for reason in decision["reasons"])


def test_s4_gate_rejects_missing_signed_artifact(tmp_path):
    manifest_obj, receipt, artifact = _signed_run_with_artifact(tmp_path)
    artifact.unlink()
    decision = _gate(manifest_obj, receipt, artifact)
    assert decision["verdict"] != "APPROVE"
    assert any("artifact" in reason.lower() for reason in decision["reasons"])


def test_s4_gate_rejects_corrupt_signed_artifact(tmp_path):
    manifest_obj, receipt, artifact = _signed_run_with_artifact(tmp_path)
    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    decision = _gate(manifest_obj, receipt, artifact)
    assert decision["verdict"] != "APPROVE"
    assert any("artifact" in reason.lower() for reason in decision["reasons"])
