"""S4 CLI/E2E tests over disposable synthetic repositories.

The candidate fixture copies only the committed QA/VST implementation from
BASELINE_HEAD, then adds one synthetic test selector and a minimal registry.
All Git writes and runner artifacts stay below pytest's temporary directory.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

import pytest

from tools.qa.registry import (
    RUNTIME_PROFILES,
    WSL_PROFILE,
    required_runtime_profiles,
)


BASELINE_HEAD = "7929bc01d8f0a09975e319c8357c6497b9aba04e"
FIXTURE_TEST_PATH = "tests/qa/test_native_fixture.py"
FIXTURE_TEST_ID = f"{FIXTURE_TEST_PATH}::test_native_fixture"
NOT_RUN_TEST_ID = f"{FIXTURE_TEST_PATH}::test_sandbox_dependent_fixture"
QA_ARTIFACT_ROOT = "docs/sdlc/evidence/qa"
LOCKED_ARTIFACTS = {
    category: {
        "report": f"{QA_ARTIFACT_ROOT}/{category}.report.jsonl",
        "stdout": f"{QA_ARTIFACT_ROOT}/{category}.stdout.txt",
        "stderr": f"{QA_ARTIFACT_ROOT}/{category}.stderr.txt",
    }
    for category in (
        "functional", "integration", "api", "e2e", "identity", "regression",
        "seeded-failure",
    )
}
VOLATILE_REPORT_FIELDS = {
    "created_utc", "duration_seconds", "run_id", "artifact_ranges",
    "artifact_digests", "artifact_sizes", "normalized_sha256",
}
SYNTHETIC_SECRET = "s4-e2e-private-token-must-not-be-recorded"
S4_WORKER_HELPER_TEST_ID = (
    "tests/qa/test_s4_functional_worker_identity.py::"
    "test_s4_worker_helper_drops_runner_identity_and_denies_runner_sentinels"
)
S4_WORKER_HELPER_TEST_PATH = "tests/qa/test_s4_functional_worker_identity.py"
WSL_TEST_FIXTURE_PARENT = Path("/tmp/vst-s4-candidate/test-fixtures")


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
        shell=False,
    )


def _fixture_test_source(outcome: str, *, include_not_run: bool = False) -> str:
    if outcome == "skip":
        body = '    import pytest\n    pytest.skip("synthetic required selector skip")\n'
    elif outcome == "xfail":
        body = '    import pytest\n    pytest.xfail("synthetic required selector xfail")\n'
    elif outcome == "spam":
        body = (
            "    import os\n"
            "    with capfd.disabled():\n"
            "        os.write(1, b'x' * 32768)\n"
        )
    elif outcome == "sleep":
        body = "    import time\n    time.sleep(30)\n"
    else:
        body = "    assert True\n"
    source = "def test_native_fixture(capfd):\n" + body
    if include_not_run:
        source += (
            "\n\n"
            "def test_sandbox_dependent_fixture():\n"
            "    raise AssertionError('NOT_RUN selectors must never be invoked')\n"
        )
    return source


def _collector_source(mode: str) -> str | None:
    if mode == "duplicate":
        return (
            "def pytest_collection_modifyitems(session, config, items):\n"
            "    if items:\n"
            "        items.append(items[0])\n"
        )
    if mode == "uncollected":
        return (
            "def pytest_collection_modifyitems(session, config, items):\n"
            "    items[:] = [item for item in items if item.name != 'test_native_fixture']\n"
        )
    return None


def _git_commit(root: Path, message: str, *, paths: tuple[str, ...] = ()) -> str:
    if paths:
        _git(root, "add", "--", *paths)
    else:
        _git(root, "add", "-A")
    _git(
        root,
        "-c", "user.name=S4 synthetic fixture",
        "-c", "user.email=s4-fixture@example.invalid",
        "-c", "commit.gpgsign=false",
        "commit", "--quiet", "-m", message,
    )
    return _git(root, "rev-parse", "--verify", "HEAD").stdout.decode().strip()


def _extract_committed_runner(candidate: Path) -> None:
    source_root = Path(__file__).resolve().parents[2]
    exists = _git(source_root, "cat-file", "-e", f"{BASELINE_HEAD}^{{commit}}", check=False)
    assert exists.returncode == 0, "the committed S4 source baseline is unavailable"
    archive = subprocess.run(
        [
            "git", "archive", "--format=tar", BASELINE_HEAD,
            "tools/qa", "tools/vst", "tests/qa/test_s4_functional_worker_identity.py",
            "docs/QA_RUNNER_DESIGN.md",
        ],
        cwd=source_root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        shell=False,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts:
                raise AssertionError("committed fixture archive contains an unsafe path")
            target = candidate.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                assert source is not None
                with source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination)
            else:
                raise AssertionError("committed fixture archive contains a non-regular entry")


def _category_manifest(
    source_commit: str,
    source_sha256: str,
    identity_sha256: str,
    *,
    include_not_run: bool = False,
) -> dict:
    inventory_ids = [FIXTURE_TEST_ID]
    not_run_reasons = {}
    if include_not_run:
        inventory_ids.append(NOT_RUN_TEST_ID)
        not_run_reasons[NOT_RUN_TEST_ID] = (
            "Sandbox-dependent S3 acceptance lacks a run-bound platform proof."
        )
    categories = {
        category: {
            "status": "NOT_RUN",
            "test_ids": [],
            "not_run_reasons": {},
            "reason": f"The synthetic CLI fixture does not exercise {category}.",
        }
        for category in ("functional", "integration", "api", "seeded-failure")
    }
    categories["identity"] = {
        "status": "SUPPORTED",
        "test_ids": [S4_WORKER_HELPER_TEST_ID],
        "not_run_reasons": {},
        "reason": None,
    }
    categories["e2e"] = {
        "status": "SUPPORTED",
        "test_ids": inventory_ids,
        "not_run_reasons": not_run_reasons,
        "reason": None,
    }
    categories["regression"] = {
        "status": "AGGREGATE",
        "test_ids": [FIXTURE_TEST_ID],
        "not_run_reasons": not_run_reasons,
        "reason": None,
    }
    return {
        "schema_version": 2,
        "registry_version": "2",
        "runtime_profiles": list(RUNTIME_PROFILES),
        "artifacts": LOCKED_ARTIFACTS,
        "source_head": source_commit,
        "source_inventory": [
            {
                "path": FIXTURE_TEST_PATH,
                "source_commit": source_commit,
                "sha256": source_sha256,
            },
            {
                "path": S4_WORKER_HELPER_TEST_PATH,
                "source_commit": source_commit,
                "sha256": identity_sha256,
            },
        ],
        "tests": [
            {
                "test_id": test_id,
                "selector": test_id,
                "source_path": (
                    S4_WORKER_HELPER_TEST_PATH
                    if test_id == S4_WORKER_HELPER_TEST_ID
                    else FIXTURE_TEST_PATH
                ),
                "source_commit": source_commit,
                "primary_category": (
                    "identity" if test_id == S4_WORKER_HELPER_TEST_ID else "e2e"
                ),
                "runtime_profiles": (
                    []
                    if test_id in not_run_reasons
                    else sorted(
                        required_runtime_profiles(
                            S4_WORKER_HELPER_TEST_ID
                            if test_id == S4_WORKER_HELPER_TEST_ID
                            else FIXTURE_TEST_ID
                        )
                    )
                ),
            }
            for test_id in [*inventory_ids, S4_WORKER_HELPER_TEST_ID]
        ],
        "categories": categories,
        "aggregates": {"regression_members": ["functional", "integration", "api", "e2e"]},
        "unsupported_apis": {
            "http": {
                "status": "UNSUPPORTED",
                "reason": "This synthetic fixture exposes no HTTP route.",
                "evidence_paths": ["docs/QA_RUNNER_DESIGN.md"],
            }
        },
    }


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _make_candidate(
    tmp_path: Path,
    *,
    outcome: str = "pass",
    collector: str = "normal",
    include_not_run: bool = False,
) -> tuple[Path, str]:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    assert candidate.resolve().is_relative_to(tmp_path.resolve())
    _extract_committed_runner(candidate)
    _git(candidate, "init", "--quiet", "--initial-branch=qa-synthetic")
    (candidate / ".gitignore").write_text(
        "__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8", newline="\n"
    )
    (candidate / "tests").mkdir(parents=True, exist_ok=True)
    test_file = candidate / FIXTURE_TEST_PATH
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(
        _fixture_test_source(outcome, include_not_run=include_not_run),
        encoding="utf-8",
        newline="\n",
    )
    collector_text = _collector_source(collector)
    if collector_text is not None:
        (candidate / "tests" / "conftest.py").write_text(
            collector_text, encoding="utf-8", newline="\n"
        )
    (candidate / "docs" / "qa").mkdir(parents=True, exist_ok=True)
    (candidate / "docs" / "qa" / "fixtures.json").write_text(
        json.dumps({
            "schema_version": 1,
            "status": "NOT_RUN",
            "reason": "The E2E fixture has no seeded-failure inputs.",
            "fixtures": [],
        }, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    identity_test_file = candidate / S4_WORKER_HELPER_TEST_PATH
    assert identity_test_file.is_file()
    source_commit = _git_commit(candidate, "add synthetic native selector")
    source_sha256 = hashlib.sha256(test_file.read_bytes()).hexdigest()
    identity_sha256 = hashlib.sha256(identity_test_file.read_bytes()).hexdigest()
    manifest_path = candidate / "docs" / "qa" / "categories.json"
    _write_json(
        manifest_path,
        _category_manifest(
            source_commit,
            source_sha256,
            identity_sha256,
            include_not_run=include_not_run,
        ),
    )
    _git_commit(candidate, "bind synthetic selector registry")
    head = _git(candidate, "rev-parse", "--verify", "HEAD").stdout.decode().strip()
    assert not _git(candidate, "remote").stdout
    return candidate, head


def _is_wsl() -> bool:
    return platform.system() == "Linux" and "microsoft" in platform.release().lower()


@pytest.fixture
def candidate_tmp_path(tmp_path: Path):
    """Put WSL candidates on distro-local storage; keep artifacts under pytest tmp_path."""
    if not _is_wsl():
        yield tmp_path
        return

    if os.geteuid() != 997:
        pytest.fail("WSL E2E candidate fixtures must run as UID 997 (vst-runner)")
    try:
        parent_info = WSL_TEST_FIXTURE_PARENT.lstat()
    except OSError as exc:
        pytest.fail(
            "WSL E2E fixture parent is unavailable; provision "
            "/tmp/vst-s4-candidate/test-fixtures as UID 997 with mode 0700 "
            f"before running this suite ({type(exc).__name__})"
        )
    if (
        not stat.S_ISDIR(parent_info.st_mode)
        or parent_info.st_uid != 997
        or stat.S_IMODE(parent_info.st_mode) != 0o700
        or not os.access(WSL_TEST_FIXTURE_PARENT, os.W_OK | os.X_OK)
    ):
        pytest.fail(
            "WSL E2E fixture parent must be a real directory owned by UID 997, "
            "mode 0700, and writable/searchable by the runner; expected "
            "/tmp/vst-s4-candidate/test-fixtures"
        )

    fixture_root = Path(
        tempfile.mkdtemp(prefix="s4-e2e-", dir=WSL_TEST_FIXTURE_PARENT)
    )
    try:
        yield fixture_root
    finally:
        # The private 0700 parent limits replacement to this runner identity;
        # remove only the exact unique child created above, never its parent.
        if (
            fixture_root.parent != WSL_TEST_FIXTURE_PARENT
            or not fixture_root.name.startswith("s4-e2e-")
            or fixture_root.is_symlink()
        ):
            pytest.fail("refusing unsafe cleanup of the WSL E2E candidate fixture")
        shutil.rmtree(fixture_root)


def _write_manifest_variant(candidate: Path, variant: str) -> None:
    path = candidate / "docs" / "qa" / "categories.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if variant == "missing":
        manifest["tests"] = []
    elif variant == "duplicate":
        manifest["tests"].append(dict(manifest["tests"][0]))
    else:
        raise AssertionError(f"unknown registry fixture: {variant}")
    _write_json(path, manifest)
    _git_commit(
        candidate,
        f"inject {variant} synthetic selector registry",
        paths=("docs/qa/categories.json",),
    )


def _dependency_target() -> Path:
    target = Path(pytest.__file__).resolve(strict=True).parent.parent
    assert target.is_dir() and (target / "pytest").is_dir()
    return target


def _run_cli(
    candidate: Path,
    tmp_path: Path,
    dependency_target: Path,
    *,
    run_id: str,
    expected_head: str | None = None,
    timeout_seconds: int = 20,
    output_cap_bytes: int = 1024 * 1024,
    report_path: str = f"{QA_ARTIFACT_ROOT}/e2e.report.jsonl",
) -> subprocess.CompletedProcess:
    dependency_wheelhouse = os.environ.get("VST_QA_DEPENDENCY_WHEELHOUSE")
    if not dependency_wheelhouse:
        raise RuntimeError(
            "VST_QA_DEPENDENCY_WHEELHOUSE is required for nested QA runner tests"
        )
    args = [
        sys.executable, "-m", "tools.qa.run",
        "--category", "e2e",
        "--repo-root", str(candidate),
        "--manifest", "docs/qa/categories.json",
        "--fixtures", "docs/qa/fixtures.json",
        "--dependency-target", str(dependency_target),
        "--dependency-wheelhouse", dependency_wheelhouse,
        "--scratch-root", str(tmp_path / "scratch"),
        "--run-id", run_id,
        "--timeout-seconds", str(timeout_seconds),
        "--output-cap-bytes", str(output_cap_bytes),
        "--report-path", report_path,
        "--stdout-path", f"{QA_ARTIFACT_ROOT}/e2e.stdout.txt",
        "--stderr-path", f"{QA_ARTIFACT_ROOT}/e2e.stderr.txt",
    ]
    if expected_head is not None:
        args.extend(("--expected-head", expected_head))
    env = {
        name: os.environ[name]
        for name in ("PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR")
        if name in os.environ
    }
    env.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": os.fspath(tmp_path / "pycache"),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PIP_NO_INDEX": "1",
        "QA_E2E_SECRET_TOKEN": SYNTHETIC_SECRET,
    })
    result = subprocess.run(
        args,
        cwd=candidate,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=False,
        shell=False,
    )
    return result


def test_s4_e2e_child_runner_disables_dependency_bytecode(monkeypatch, tmp_path):
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs["env"]
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    monkeypatch.delenv("VST_QA_DEPENDENCY_WHEELHOUSE", raising=False)
    dependency_target = tmp_path / "dependency-target"
    with pytest.raises(RuntimeError, match="VST_QA_DEPENDENCY_WHEELHOUSE"):
        _run_cli(tmp_path, tmp_path, dependency_target, run_id="missing-wheelhouse")

    dependency_wheelhouse = tmp_path / "wheelhouse"
    monkeypatch.setenv("VST_QA_DEPENDENCY_WHEELHOUSE", os.fspath(dependency_wheelhouse))
    result = _run_cli(
        tmp_path, tmp_path, dependency_target, run_id="bytecode-disabled"
    )

    assert result.returncode == 0
    assert captured["args"][captured["args"].index("--dependency-wheelhouse") + 1] == str(
        dependency_wheelhouse
    )
    assert captured["env"]["PYTHONDONTWRITEBYTECODE"] == "1"
    cache_prefix = Path(captured["env"]["PYTHONPYCACHEPREFIX"])
    assert cache_prefix == tmp_path / "pycache"
    assert not cache_prefix.is_relative_to(dependency_target)


def _last_report(candidate: Path) -> tuple[dict, bytes]:
    path = candidate / LOCKED_ARTIFACTS["e2e"]["report"]
    lines = path.read_bytes().splitlines(keepends=True)
    assert lines and lines[-1].endswith(b"\n")
    report_line = lines[-1]
    return json.loads(report_line), report_line


def _assert_report_hashes(candidate: Path, report: dict, report_line: bytes) -> None:
    exact_report_bytes = json.dumps(
        report, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    assert report_line == exact_report_bytes
    normalized = {key: value for key, value in report.items() if key not in VOLATILE_REPORT_FIELDS}
    normalized_bytes = json.dumps(
        normalized, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert hashlib.sha256(normalized_bytes).hexdigest() == report["normalized_sha256"]

    for stream_name in ("stdout", "stderr"):
        artifact = candidate / report["artifact_paths"][stream_name]
        data = artifact.read_bytes()
        byte_range = report["artifact_ranges"][stream_name]
        chunk = data[byte_range["start"]:byte_range["end"]]
        assert len(chunk) == report["artifact_sizes"][stream_name]
        assert hashlib.sha256(chunk).hexdigest() == report["artifact_digests"][stream_name]


def _assert_report_private(report: dict, *, candidate: Path, target: Path, tmp_path: Path) -> None:
    report_for_privacy_check = dict(report)
    candidate_root = None
    if report["runtime_profile"] == WSL_PROFILE:
        boundary = report["runtime_boundary"]
        candidate_root = boundary["candidate_root"]
        candidate_path = candidate.resolve().as_posix()
        assert candidate_path.startswith("/tmp/vst-s4-candidate/")
        assert candidate_root == candidate_path
        report_for_privacy_check["runtime_boundary"] = dict(boundary)
        report_for_privacy_check["runtime_boundary"]["candidate_root"] = "<approved-wsl-candidate-root>"

    rendered = json.dumps(report_for_privacy_check, sort_keys=True)
    private_paths = (str(candidate), str(target), str(tmp_path))
    if candidate_root is not None:
        private_paths += (candidate_root,)
    for private_path in private_paths:
        assert private_path not in rendered
    assert "C:/Users/" not in rendered
    assert "C:\\Users\\" not in rendered
    assert SYNTHETIC_SECRET not in rendered


def _assert_nonapproving(result: subprocess.CompletedProcess, report: dict) -> None:
    assert result.returncode != 0
    assert report["result"] in {"BLOCKED", "FAIL", "NOT_RUN", "UNSUPPORTED", "INCONCLUSIVE"}


def _assert_pytest_module_invocation(report: dict) -> None:
    command = report["command"]
    if report["runtime_profile"] == WSL_PROFILE:
        approved_python = "<approved-python-base>/python3.12"
    else:
        approved_python = "<approved-python-base>/python.exe"
    assert command[:3] == [approved_python, "-m", "pytest"]
    assert command[-1] == FIXTURE_TEST_PATH
    assert FIXTURE_TEST_ID not in command
    assert NOT_RUN_TEST_ID not in command


def test_s4_e2e_cli_native_collection_binds_candidate_and_repeatable_artifact_chunks(
    tmp_path, candidate_tmp_path
):
    target = _dependency_target()
    candidate, expected_head = _make_candidate(candidate_tmp_path)
    assert _git(candidate, "status", "--porcelain").stdout == b""
    assert _git(candidate, "remote").stdout == b""
    assert not target.is_relative_to(candidate.resolve())

    first = _run_cli(candidate, tmp_path, target, run_id="native-pass-1", expected_head=expected_head)
    assert first.returncode == 0, first.stderr.decode("utf-8", errors="replace")
    report1, report_line1 = _last_report(candidate)
    _assert_report_hashes(candidate, report1, report_line1)
    _assert_report_private(report1, candidate=candidate, target=target, tmp_path=tmp_path)
    assert report1["result"] == "PASS"
    assert report1["candidate_head"] == expected_head
    assert report1["expected_test_ids"] == [FIXTURE_TEST_ID]
    assert report1["inventory_test_ids"] == [FIXTURE_TEST_ID]
    _assert_pytest_module_invocation(report1)
    assert report1["collected_node_ids"] == [FIXTURE_TEST_ID]
    assert report1["executed_node_ids"] == [FIXTURE_TEST_ID]
    assert report1["passed_test_ids"] == [FIXTURE_TEST_ID]
    assert report1["dirty_tree"]["after"] is False
    assert report1["environment"]["dependency_target"] == "isolated-external-target"

    second = _run_cli(candidate, tmp_path, target, run_id="native-pass-2", expected_head=expected_head)
    assert second.returncode == 0, second.stderr.decode("utf-8", errors="replace")
    report2, report_line2 = _last_report(candidate)
    _assert_report_hashes(candidate, report2, report_line2)
    assert report2["candidate_head"] == expected_head
    _assert_pytest_module_invocation(report2)
    assert report2["collected_node_ids"] == [FIXTURE_TEST_ID]
    assert report2["executed_node_ids"] == [FIXTURE_TEST_ID]
    assert report2["normalized_sha256"] == report1["normalized_sha256"]


def test_s4_e2e_cli_preserves_sandbox_dependent_selector_as_not_run(
    tmp_path, candidate_tmp_path
):
    target = _dependency_target()
    candidate, _ = _make_candidate(candidate_tmp_path, include_not_run=True)

    result = _run_cli(candidate, tmp_path, target, run_id="sandbox-not-run")
    report, report_line = _last_report(candidate)
    _assert_nonapproving(result, report)
    _assert_report_hashes(candidate, report, report_line)
    assert report["result"] == "INCONCLUSIVE"
    assert report["expected_test_ids"] == [FIXTURE_TEST_ID]
    assert report["inventory_test_ids"] == sorted([FIXTURE_TEST_ID, NOT_RUN_TEST_ID])
    assert report["not_run_test_reasons"] == {
        NOT_RUN_TEST_ID: "Sandbox-dependent S3 acceptance lacks a run-bound platform proof."
    }
    _assert_pytest_module_invocation(report)
    assert report["collected_node_ids"] == [FIXTURE_TEST_ID]
    assert report["executed_node_ids"] == [FIXTURE_TEST_ID]
    assert NOT_RUN_TEST_ID not in report["collected_node_ids"]
    assert NOT_RUN_TEST_ID not in report["executed_node_ids"]


def test_s4_pytest_argv_size_depends_on_source_files_not_selector_count(tmp_path):
    from tools.qa.run import _pytest_command

    source_path = "tests/qa/test_many_registered_selectors.py"
    dependency_target = tmp_path / "dependencies"
    dependency_wheelhouse = tmp_path / "wheelhouse"

    def command_for(selector_count: int) -> tuple[list[str], dict[str, str], Path]:
        expected_ids = [f"{source_path}::test_registered_{index:04d}" for index in range(selector_count)]
        selectors = {test_id: {"selector": test_id} for test_id in expected_ids}
        scratch_run = tmp_path / f"scratch-{selector_count}"
        scratch_run.mkdir()
        argv, child_env = _pytest_command(
            expected_ids=expected_ids,
            selectors=selectors,
            scratch_run=scratch_run,
            repo_root=tmp_path,
            dependency_target=dependency_target,
            dependency_wheelhouse=dependency_wheelhouse,
        )
        return argv, child_env, scratch_run

    one_selector_argv, one_selector_env, one_selector_scratch = command_for(1)
    many_selectors_argv, many_selectors_env, many_selectors_scratch = command_for(1000)

    assert len(many_selectors_argv) == len(one_selector_argv)
    assert many_selectors_argv[-1] == source_path
    assert not any("::" in argument for argument in many_selectors_argv)
    for child_env, scratch_run in (
        (one_selector_env, one_selector_scratch),
        (many_selectors_env, many_selectors_scratch),
    ):
        cache_prefix = Path(child_env["PYTHONPYCACHEPREFIX"])
        assert cache_prefix == scratch_run / "pycache"
        assert not cache_prefix.is_relative_to(dependency_target)
        assert child_env["VST_QA_DEPENDENCY_WHEELHOUSE"] == str(dependency_wheelhouse)


def test_s4_e2e_cli_refuses_candidate_head_and_registry_selector_mismatches(
    tmp_path, candidate_tmp_path
):
    empty_target = tmp_path / "empty-dependencies"
    empty_target.mkdir()
    candidate, expected_head = _make_candidate(candidate_tmp_path)
    wrong_head = "f" * 40

    mismatch = _run_cli(
        candidate, tmp_path, empty_target, run_id="wrong-head", expected_head=wrong_head
    )
    mismatch_report, _ = _last_report(candidate)
    _assert_nonapproving(mismatch, mismatch_report)
    assert any("does not match --expected-head" in reason for reason in mismatch_report["reasons"])
    assert mismatch_report["candidate_head"] == expected_head

    _write_manifest_variant(candidate, "duplicate")
    duplicate = _run_cli(candidate, tmp_path, empty_target, run_id="duplicate-selector")
    duplicate_report, _ = _last_report(candidate)
    _assert_nonapproving(duplicate, duplicate_report)
    assert any("duplicate selector/test id" in reason for reason in duplicate_report["reasons"])
    assert duplicate_report["command"] == []


def test_s4_e2e_cli_refuses_registry_with_a_missing_selector(tmp_path, candidate_tmp_path):
    empty_target = tmp_path / "empty-dependencies"
    empty_target.mkdir()
    candidate, _ = _make_candidate(candidate_tmp_path)
    _write_manifest_variant(candidate, "missing")

    result = _run_cli(candidate, tmp_path, empty_target, run_id="missing-selector")
    report, _ = _last_report(candidate)
    _assert_nonapproving(result, report)
    assert any("selector inventory differs from source" in reason for reason in report["reasons"])
    assert report["command"] == []


@pytest.mark.parametrize(
    ("outcome", "collector", "report_field"),
    [
        ("pass", "uncollected", "uncollected_test_ids"),
        ("skip", "normal", "skipped_test_ids"),
        ("xfail", "normal", "xfail_test_ids"),
        ("pass", "duplicate", "reasons"),
    ],
)
def test_s4_e2e_cli_rejects_uncollected_duplicate_skipped_or_xfailed_selector(
    tmp_path, candidate_tmp_path, outcome, collector, report_field
):
    target = _dependency_target()
    candidate, _ = _make_candidate(candidate_tmp_path, outcome=outcome, collector=collector)
    result = _run_cli(candidate, tmp_path, target, run_id=f"case-{collector}-{outcome}")
    report, report_line = _last_report(candidate)
    _assert_nonapproving(result, report)
    _assert_report_hashes(candidate, report, report_line)
    assert report["expected_test_ids"] == [FIXTURE_TEST_ID]
    assert report["inventory_test_ids"] == [FIXTURE_TEST_ID]
    _assert_pytest_module_invocation(report)
    if report_field == "reasons":
        assert "pytest emitted duplicate node IDs" in report["reasons"]
        assert report["collected_node_ids"] == [FIXTURE_TEST_ID]
        assert report["executed_node_ids"] == [FIXTURE_TEST_ID]
        assert report["failed_test_ids"] == [FIXTURE_TEST_ID]
    else:
        assert report[report_field] == [FIXTURE_TEST_ID]
        if collector == "uncollected":
            assert report["collected_node_ids"] == []
            assert report["executed_node_ids"] == []
        else:
            assert report["collected_node_ids"] == [FIXTURE_TEST_ID]
            assert report["executed_node_ids"] == [FIXTURE_TEST_ID]
        assert FIXTURE_TEST_ID not in report["passed_test_ids"]
    assert report["result"] == "FAIL"


def test_s4_e2e_cli_fails_closed_on_output_truncation(tmp_path, candidate_tmp_path):
    target = _dependency_target()
    candidate, _ = _make_candidate(candidate_tmp_path, outcome="spam")
    result = _run_cli(
        candidate, tmp_path, target, run_id="truncated-output", output_cap_bytes=128
    )
    report, report_line = _last_report(candidate)
    _assert_nonapproving(result, report)
    _assert_report_hashes(candidate, report, report_line)
    assert report["expected_test_ids"] == [FIXTURE_TEST_ID]
    assert report["collected_node_ids"] == [FIXTURE_TEST_ID]
    assert report["executed_node_ids"] == [FIXTURE_TEST_ID]
    assert report["passed_test_ids"] == [FIXTURE_TEST_ID]
    _assert_pytest_module_invocation(report)
    assert report["exit_code"] == -3
    assert report["capture"]["timed_out"] is False
    assert report["capture"]["stdout_truncated"] or report["capture"]["stderr_truncated"]
    assert any("output exceeded the configured cap" in reason for reason in report["reasons"])
    assert report["result"] == "FAIL"


def test_s4_e2e_cli_reports_missing_dependency_without_fallback_or_child_invocation(
    tmp_path, candidate_tmp_path
):
    missing_target = tmp_path / "empty-dependency-target"
    missing_target.mkdir()
    candidate, _ = _make_candidate(candidate_tmp_path)
    result = _run_cli(candidate, tmp_path, missing_target, run_id="missing-dependency")
    report, report_line = _last_report(candidate)
    _assert_nonapproving(result, report)
    _assert_report_hashes(candidate, report, report_line)
    assert any("locked QA dependencies are missing or mismatched" in reason for reason in report["reasons"])
    assert report["command"] == []
    assert report["exit_code"] is None


def test_s4_e2e_cli_blocks_dirty_tracked_candidate_before_native_collection(
    tmp_path, candidate_tmp_path
):
    target = _dependency_target()
    candidate, _ = _make_candidate(candidate_tmp_path)
    tracked_source = candidate / "tools" / "vst" / "runner.py"
    tracked_source.write_bytes(tracked_source.read_bytes() + b"\n# dirty synthetic fixture\n")

    result = _run_cli(candidate, tmp_path, target, run_id="dirty-candidate")
    report, report_line = _last_report(candidate)
    _assert_nonapproving(result, report)
    _assert_report_hashes(candidate, report, report_line)
    assert report["dirty_tree"]["before"] is True
    assert report["dirty_tree"]["before_paths"] == ["tools/vst/runner.py"]
    assert any("unrelated changes before execution" in reason for reason in report["reasons"])
    assert report["command"] == []
    assert report["exit_code"] is None
    assert report["collected_node_ids"] == []
    assert report["executed_node_ids"] == []


def test_s4_e2e_cli_rejects_artifact_path_outside_fixed_contract(tmp_path, candidate_tmp_path):
    target = tmp_path / "empty-dependency-target"
    target.mkdir()
    candidate, _ = _make_candidate(candidate_tmp_path)
    outside_path = "docs/sdlc/evidence/qa/../../outside.report.jsonl"

    result = _run_cli(
        candidate, tmp_path, target, run_id="wrong-artifact-path", report_path=outside_path
    )
    assert result.returncode == 2
    assert b"artifact paths must match the fixed append-only category paths" in result.stdout
    assert not (candidate / "docs" / "sdlc" / "evidence" / "qa" / "e2e.report.jsonl").exists()


def test_s4_e2e_cli_requires_explicit_dependency_wheelhouse():
    result = subprocess.run(
        [
            sys.executable, "-m", "tools.qa.run",
            "--category", "e2e",
            "--repo-root", os.fspath(Path(__file__).resolve().parents[2]),
            "--dependency-target", "unused-target",
            "--scratch-root", "unused-scratch",
            "--run-id", "missing-wheelhouse-argument",
            "--report-path", f"{QA_ARTIFACT_ROOT}/e2e.report.jsonl",
            "--stdout-path", f"{QA_ARTIFACT_ROOT}/e2e.stdout.txt",
            "--stderr-path", f"{QA_ARTIFACT_ROOT}/e2e.stderr.txt",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )

    assert result.returncode == 2
    assert b"--dependency-wheelhouse" in result.stderr
    assert b"required" in result.stderr


def test_s4_worker_helper_selector_is_wsl_only():
    assert required_runtime_profiles(S4_WORKER_HELPER_TEST_ID) == [WSL_PROFILE]


@pytest.mark.skip(
    reason=(
        "NOT_RUN: exercising the runner timeout calls process-tree termination; "
        "the S4 execution assignment prohibits process-kill scenarios"
    )
)
def test_s4_e2e_cli_timeout_is_nonapproving_without_install_or_fallback(
    tmp_path, candidate_tmp_path
):
    target = _dependency_target()
    candidate, _ = _make_candidate(candidate_tmp_path, outcome="sleep")
    result = _run_cli(
        candidate,
        tmp_path,
        target,
        run_id="bounded-timeout",
        timeout_seconds=1,
    )
    report, _ = _last_report(candidate)
    _assert_nonapproving(result, report)
    assert report["capture"]["timed_out"] is True
    assert report["result"] == "FAIL"
