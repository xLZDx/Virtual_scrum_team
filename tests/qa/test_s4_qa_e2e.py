"""S4 synthetic end-to-end checks that do not require private WSL inputs.

These checks exercise the existing local VST slice and the WSL transfer
command's public refusal boundary. They do not claim native S4 runner,
signer-socket, or snapshot-transfer acceptance.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from tools.qa.wsl_snapshot import main as snapshot_main


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_s4_e5_synthetic_slice_cli_journey_preserves_gate_and_restart_evidence(tmp_path):
    """S4 E4/E5/E6: execute the synthetic story flow through its CLI boundary."""
    workdir = tmp_path / "slice-run"
    completed = subprocess.run(
        [sys.executable, "-m", "tools.vst.slice", str(workdir)],
        cwd=REPO_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=90,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert len(report) == 23
    assert report["happy_path"]["verdict"] == "APPROVE"
    assert report["happy_path"]["extra"]["event_chain_ok"] is True
    assert report["retry_after_fail"]["verdict"] == "APPROVE"
    assert report["retry_after_fail"]["unresolved_findings"] == [
        "earlier failure retained: tests attempt 1 FAIL"
    ]
    assert report["budget_exceeded"]["verdict"] == "MODIFY"
    assert "terminal marker BUDGET_EXCEEDED" in report["budget_exceeded"]["reasons"][0]
    assert (workdir / "happy_path" / "state.db").is_file()
    assert (workdir / "retry_after_fail" / "state.db").is_file()


def test_s4_e6_qa_snapshot_cli_refuses_an_unapproved_distribution(tmp_path, capsys):
    """S4 E6: wrong distro is rejected before WSL, Git bundle, or signer access."""
    exit_code = snapshot_main([
        "--cwd", str(tmp_path),
        "--distribution", "Unapproved-Distro",
        "--wsl-user", "unused-test-value",
        "--worker-gid", "0",
        "--snapshot-root", "/unused/test-snapshot-root",
    ])

    captured = capsys.readouterr()
    assert exit_code == 2
    payload = json.loads(captured.out)
    assert payload["state"] == "BLOCKED"
    assert payload["reason"] == "distribution must be the named Ubuntu-24.04 WSL distro"
    assert captured.err == ""
