"""Functional acceptance for S4 report normalization and per-run artifact chunks."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from tools.qa import report, run


def test_s4_normalized_report_digest_ignores_only_declared_run_volatile_fields():
    first = {
        "schema_version": 1,
        "candidate_head": "a" * 40,
        "result": "FAIL",
        "reasons": ["required case skipped"],
        "artifact_digests": {"stdout": "b" * 64},
        "artifact_ranges": {"stdout": {"start": 0, "end": 8}},
        "run_id": "run-one",
        "duration_seconds": 1.25,
        "created_utc": "2026-10-25T00:00:00Z",
        "normalized_sha256": None,
    }
    second = copy.deepcopy(first)
    second.update(
        artifact_ranges={"stdout": {"start": 8, "end": 16}},
        run_id="run-two",
        duration_seconds=9.5,
        created_utc="2026-10-26T00:00:00Z",
    )

    first_bytes = report.encode_report(first)
    second_bytes = report.encode_report(second)

    assert first["normalized_sha256"] == second["normalized_sha256"]
    assert report.normalized_report(first) == report.normalized_report(second)
    assert json.loads(first_bytes)["result"] == "FAIL"
    assert first_bytes.endswith(b"\n") and second_bytes.endswith(b"\n")


def test_s4_normalized_digest_excludes_raw_artifact_hashes_but_preserves_range_integrity(
    tmp_path: Path,
):
    payloads = (b"stdout A\n", b"stdout B has more bytes\n")
    reports = []
    artifact_paths = []
    for index, payload in enumerate(payloads):
        artifact_path = tmp_path / f"capture-{index}.stdout"
        capture = run._append_raw_artifact(artifact_path, payload)
        artifact_paths.append(artifact_path)
        reports.append({
            "schema_version": 1,
            "candidate_head": "a" * 40,
            "result": "PASS",
            "reasons": [],
            "artifact_digests": {"stdout": capture["sha256"]},
            "artifact_sizes": {"stdout": capture["size"]},
            "artifact_ranges": {
                "stdout": {"start": capture["start"], "end": capture["end"]}
            },
            "run_id": "same-run-shape",
            "duration_seconds": 1.0,
            "created_utc": "2026-10-25T00:00:00Z",
            "normalized_sha256": None,
        })

    for artifact_path, report_row in zip(artifact_paths, reports):
        byte_range = report_row["artifact_ranges"]["stdout"]
        captured_bytes = artifact_path.read_bytes()[byte_range["start"]:byte_range["end"]]
        assert hashlib.sha256(captured_bytes).hexdigest() == report_row["artifact_digests"]["stdout"]
        assert len(captured_bytes) == report_row["artifact_sizes"]["stdout"]
        assert byte_range["end"] - byte_range["start"] == report_row["artifact_sizes"]["stdout"]

    first_bytes = report.encode_report(reports[0])
    second_bytes = report.encode_report(reports[1])

    assert reports[0]["artifact_digests"] != reports[1]["artifact_digests"]
    assert reports[0]["artifact_sizes"] != reports[1]["artifact_sizes"]
    assert reports[0]["normalized_sha256"] == reports[1]["normalized_sha256"]
    assert json.loads(first_bytes)["artifact_digests"] == reports[0]["artifact_digests"]
    assert json.loads(second_bytes)["artifact_digests"] == reports[1]["artifact_digests"]
    assert json.loads(first_bytes)["artifact_sizes"] == reports[0]["artifact_sizes"]
    assert json.loads(second_bytes)["artifact_sizes"] == reports[1]["artifact_sizes"]


def test_s4_artifact_chunk_hashes_are_stable_and_ranges_bind_each_append(tmp_path: Path):
    payload = b"PASS tests/qa/test_contract.py::test_example\n"
    path = tmp_path / "stdout.txt"

    first = run._append_raw_artifact(path, payload)
    second = run._append_raw_artifact(path, payload)

    expected_digest = hashlib.sha256(payload).hexdigest()
    assert first["sha256"] == second["sha256"] == expected_digest
    assert first["size"] == second["size"] == len(payload)
    assert (first["start"], first["end"]) == (0, len(payload))
    assert (second["start"], second["end"]) == (len(payload), 2 * len(payload))
    assert path.read_bytes() == payload + payload


def test_s4_run_output_records_reproducible_digests_for_stdout_and_stderr(tmp_path: Path):
    first_report: dict = {}
    second_report: dict = {}
    stdout_one = tmp_path / "one.stdout"
    stderr_one = tmp_path / "one.stderr"
    stdout_two = tmp_path / "two.stdout"
    stderr_two = tmp_path / "two.stderr"

    run._append_run_outputs(first_report, stdout_one, b"stable output", stderr_one, b"stable error")
    run._append_run_outputs(second_report, stdout_two, b"stable output", stderr_two, b"stable error")

    assert first_report["artifact_digests"] == second_report["artifact_digests"]
    assert first_report["artifact_sizes"] == second_report["artifact_sizes"]
    assert first_report["artifact_ranges"] == second_report["artifact_ranges"]
    assert first_report["artifact_digests"] == {
        "stdout": hashlib.sha256(b"stable output\n").hexdigest(),
        "stderr": hashlib.sha256(b"stable error\n").hexdigest(),
    }


def test_s4_report_redacts_candidate_scratch_user_paths_and_credentials(tmp_path: Path, monkeypatch):
    repo = tmp_path / "candidate"
    scratch = tmp_path / "scratch"
    monkeypatch.setenv("TEMP", r"C:\Users\PrivateUser\Temp")
    raw = (
        fr"repo={repo}; scratch={scratch}; home=C:\Users\PrivateUser\project; "
        "api_key=secret-value bearer abcdefghijklmnop"
    ).encode()

    redacted = run._redact(raw, repo_root=repo, scratch_root=scratch).decode()

    assert str(repo) not in redacted
    assert str(scratch) not in redacted
    assert "PrivateUser" not in redacted
    assert "secret-value" not in redacted
    assert "abcdefghijklmnop" not in redacted
    assert "<candidate-root>" in redacted
    assert "<scratch-root>" in redacted


def test_s4_runner_command_selection_is_exact_and_does_not_install_packages(tmp_path: Path):
    repo = tmp_path / "candidate"
    dependency_target = tmp_path / "target"
    dependency_wheelhouse = tmp_path / "wheelhouse"
    dependency_target.mkdir()
    ids = [
        "tests/qa/test_case.py::test_function",
        "tests/qa/test_case.py::TestCases::test_method",
    ]
    selectors = {test_id: {"selector": test_id} for test_id in ids}
    invocations = []
    selections = []
    for run_id in ("run-1", "run-2"):
        scratch_run = tmp_path / "scratch" / run_id
        scratch_run.mkdir(parents=True)
        argv, child_env = run._pytest_command(
            expected_ids=ids,
            selectors=selectors,
            scratch_run=scratch_run,
            repo_root=repo,
            dependency_target=dependency_target,
            dependency_wheelhouse=dependency_wheelhouse,
        )
        selection = json.loads((scratch_run / "selection.json").read_text(encoding="utf-8"))
        invocations.append((argv, child_env))
        selections.append(selection)

    expected_map = {test_id: test_id for test_id in ids}
    assert selections[0] == selections[1] == {
        "schema_version": 2,
        "expected_selectors": expected_map,
        "known_selectors": expected_map,
    }
    for argv, child_env in invocations:
        assert argv[-1:] == ["tests/qa/test_case.py"]
        assert not set(ids).intersection(argv)
        assert argv[1:4] == ["-m", "pytest", "-q"]
        assert child_env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
        assert child_env["PYTHONPATH"] == str(dependency_target)
        assert child_env["VST_QA_DEPENDENCY_WHEELHOUSE"] == str(dependency_wheelhouse)
        assert not any(token.lower() in {"install", "pip", "download"} for token in argv)


def test_s4_runner_rejects_empty_selector_invocation(tmp_path: Path):
    scratch_run = tmp_path / "run"
    scratch_run.mkdir()

    try:
        run._pytest_command(
            expected_ids=[], selectors={}, scratch_run=scratch_run,
            repo_root=tmp_path, dependency_target=tmp_path / "target",
            dependency_wheelhouse=tmp_path / "wheelhouse",
        )
    except run.QARunError as exc:
        assert "empty registered selector set" in str(exc)
    else:
        raise AssertionError("empty required selector set must fail closed")


def test_s4_base_status_keeps_unknown_and_unrun_categories_non_approving():
    assert run._base_status("NOT_RUN", "e2e", "sandbox unavailable")[0] == "NOT_RUN"
    assert run._base_status("UNSUPPORTED", "api", "no HTTP route contract")[0] == "UNSUPPORTED"
    assert run._base_status(None, "unknown", None)[0] == "BLOCKED"
