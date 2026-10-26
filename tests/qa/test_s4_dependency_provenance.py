"""Functional contracts for locked offline QA dependencies (AC-4..6, AC-17)."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import subprocess
from argparse import Namespace
import zipfile
from pathlib import Path

import pytest

from tools.qa import build_registry, dependencies, registry, run


def _wheel_bytes(
    *,
    include_relocation: bool = False,
    project: str = "pytest",
    version: str = "9.0.3",
    tags: tuple[str, ...] = ("py3-none-any",),
) -> bytes:
    dist_info = f"{project}-{version}.dist-info"
    files = {
        f"{project}/__init__.py": f"__version__ = '{version}'\n".encode(),
        f"{dist_info}/METADATA": (
            f"Metadata-Version: 2.1\nName: {project}\nVersion: {version}\n\n".encode()
        ),
        f"{dist_info}/WHEEL": (
            "Wheel-Version: 1.0\nGenerator: s4-test\nRoot-Is-Purelib: true\n"
            + "".join(f"Tag: {tag}\n" for tag in tags)
            + "\n"
        ).encode(),
    }
    if include_relocation:
        files[f"{project}-{version}.data/purelib/relocated.py"] = b"value = 1\n"
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for name, content in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
        writer.writerow((name, f"sha256={digest}", str(len(content))))
    writer.writerow((f"{dist_info}/RECORD", "", ""))
    files[f"{dist_info}/RECORD"] = record.getvalue().encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()


def test_s4_dependency_accepts_equivalent_expanded_python_wheel_tags(tmp_path: Path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    pytest_wheel = _wheel_bytes()
    (wheelhouse / "pytest-9.0.3-py3-none-any.whl").write_bytes(pytest_wheel)
    wheel = _wheel_bytes(
        project="colorama",
        version="0.4.6",
        tags=("py2-none-any", "py3-none-any"),
    )
    (wheelhouse / "colorama-0.4.6-py2.py3-none-any.whl").write_bytes(wheel)
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "# Wheel-only, exact hashes for a synthetic runner test.\n"
        "pytest==9.0.3 \\\n"
        f"    --hash=sha256:{hashlib.sha256(pytest_wheel).hexdigest()}\n"
        "colorama==0.4.6 \\\n"
        f"    --hash=sha256:{hashlib.sha256(wheel).hexdigest()}\n",
        encoding="utf-8",
    )

    target = tmp_path / "target"
    prepared = dependencies.prepare_dependency_target(lock, wheelhouse, target)

    assert prepared["versions"] == {"colorama": "0.4.6", "pytest": "9.0.3"}
    assert dependencies.verify_dependency_environment(lock, target, wheelhouse)["versions"] == {
        "colorama": "0.4.6",
        "pytest": "9.0.3",
    }

    for tags, reason in (
        (("py3-none-any",), "wheel filename has an unsupported Python/platform tag"),
        (("cp314-cp314-win_amd64",), "wheel contains an unsupported Python/platform tag"),
    ):
        rejected_wheel = _wheel_bytes(project="colorama", version="0.4.6", tags=tags)
        rejected_wheelhouse = tmp_path / f"wheelhouse-{tags[0]}"
        rejected_wheelhouse.mkdir()
        (rejected_wheelhouse / "pytest-9.0.3-py3-none-any.whl").write_bytes(pytest_wheel)
        (rejected_wheelhouse / "colorama-0.4.6-py2.py3-none-any.whl").write_bytes(rejected_wheel)
        rejected_lock = tmp_path / f"requirements-{tags[0]}.lock"
        rejected_lock.write_text(
            "# Wheel-only, exact hashes for a synthetic runner test.\n"
            "pytest==9.0.3 \\\n"
            f"    --hash=sha256:{hashlib.sha256(pytest_wheel).hexdigest()}\n"
            "colorama==0.4.6 \\\n"
            f"    --hash=sha256:{hashlib.sha256(rejected_wheel).hexdigest()}\n",
            encoding="utf-8",
        )

        with pytest.raises(dependencies.DependencyProvenanceError, match=reason):
            dependencies.prepare_dependency_target(
                rejected_lock,
                rejected_wheelhouse,
                tmp_path / f"target-{tags[0]}",
            )


def _locked_fixture(tmp_path: Path, *, include_relocation: bool = False):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _wheel_bytes(include_relocation=include_relocation)
    (wheelhouse / "pytest-9.0.3-py3-none-any.whl").write_bytes(wheel)
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "# Wheel-only, exact hashes for a synthetic runner test.\n"
        "pytest==9.0.3 \\\n"
        f"    --hash=sha256:{hashlib.sha256(wheel).hexdigest()}\n",
        encoding="utf-8",
    )
    target = tmp_path / "target"
    evidence = dependencies.prepare_dependency_target(lock, wheelhouse, target)
    return lock, wheelhouse, target, evidence


def test_s4_dependency_target_bytes_must_match_locked_same_version_wheel(tmp_path: Path):
    lock, wheelhouse, target, prepared = _locked_fixture(tmp_path)
    installed_module = target / "pytest" / "__init__.py"
    installed_module.write_bytes(b"__version__ = '9.0.3'\n# substituted bytes\n")

    with pytest.raises(dependencies.DependencyProvenanceError, match="file content differs"):
        dependencies.verify_dependency_environment(lock, target, wheelhouse)

    assert prepared["versions"] == {"pytest": "9.0.3"}
    assert installed_module.exists()


def test_s4_dependency_wheel_must_match_lock_hash(tmp_path: Path):
    lock, wheelhouse, target, _ = _locked_fixture(tmp_path)
    wheel = next(wheelhouse.glob("*.whl"))
    wheel.write_bytes(wheel.read_bytes() + b"changed")

    with pytest.raises(dependencies.DependencyProvenanceError, match="selection is ambiguous or missing"):
        dependencies.verify_dependency_environment(lock, target, wheelhouse)


def test_s4_dependency_target_rejects_extra_importable_file(tmp_path: Path):
    lock, wheelhouse, target, _ = _locked_fixture(tmp_path)
    extra = target / "rogue_import.py"
    extra.write_text("value = 'unlocked'\n", encoding="utf-8")

    with pytest.raises(dependencies.DependencyProvenanceError, match="inventory differs"):
        dependencies.verify_dependency_environment(lock, target, wheelhouse)

    assert extra.read_text(encoding="utf-8") == "value = 'unlocked'\n"


def test_s4_dependency_preparation_rejects_unsupported_wheel_relocation(tmp_path: Path):
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _wheel_bytes(include_relocation=True)
    (wheelhouse / "pytest-9.0.3-py3-none-any.whl").write_bytes(wheel)
    lock = tmp_path / "requirements.lock"
    lock.write_text(
        "# Wheel-only, exact hashes for a synthetic runner test.\n"
        "pytest==9.0.3 \\\n"
        f"    --hash=sha256:{hashlib.sha256(wheel).hexdigest()}\n",
        encoding="utf-8",
    )

    with pytest.raises(dependencies.DependencyProvenanceError, match="unsupported .data relocation"):
        dependencies.prepare_dependency_target(lock, wheelhouse, tmp_path / "target")

    assert not (tmp_path / "target" / "pytest").exists()


def test_s4_dependency_execution_integrity_is_explicitly_not_verified():
    report = run._report_base(
        args=type("Args", (), {
            "run_id": "integrity-contract", "category": "functional", "manifest": "docs/qa/categories.json",
            "_output_paths": {}, "_runtime_profile": None,
        })(),
        root=Path("."), registry=None, candidate_head="a" * 40, before_paths=[],
    )

    assert report["schema_version"] == 3
    assert report["dependency_execution_integrity"] == "NOT_VERIFIED"
    assert report["dependency_content_verified_before"] is False
    assert report["dependency_content_verified_after"] is False


def test_s4_runner_cli_requires_explicit_dependency_wheelhouse(monkeypatch):
    from tools.qa import run

    monkeypatch.setattr(__import__("sys"), "argv", [
        "qa-runner", "--category", "functional", "--repo-root", ".",
        "--dependency-target", "target", "--scratch-root", "scratch", "--run-id", "cli-contract",
        "--report-path", "docs/sdlc/evidence/qa/functional.report.jsonl",
        "--stdout-path", "docs/sdlc/evidence/qa/functional.stdout.txt",
        "--stderr-path", "docs/sdlc/evidence/qa/functional.stderr.txt",
    ])

    with pytest.raises(SystemExit) as error:
        run._args()

    assert error.value.code == 2


def test_s4_runner_reports_post_execution_dependency_mutation(tmp_path: Path, monkeypatch, capsys):
    candidate = tmp_path / "candidate"
    (candidate / "tests" / "qa").mkdir(parents=True)
    (candidate / "docs" / "qa").mkdir(parents=True)
    (candidate / "tools" / "qa").mkdir(parents=True)
    (candidate / "tools" / "vst").mkdir(parents=True)
    for category in ("functional", "integration", "api", "e2e"):
        (candidate / "tests" / "qa" / f"test_s4_{category}_fixture.py").write_text(
            f"def test_{category}_fixture_node():\n    return None\n", encoding="utf-8"
        )
    identity_relative = registry.IDENTITY_SELECTOR.split("::", 1)[0]
    identity_source = Path(__file__).resolve().parents[2] / identity_relative
    identity_target = candidate / identity_relative
    identity_target.parent.mkdir(parents=True, exist_ok=True)
    identity_target.write_bytes(identity_source.read_bytes())
    (candidate / "docs" / "S4_QA_AUTOMATION_PLAN_2026-10-24.md").write_text(
        "# Synthetic candidate\n", encoding="utf-8"
    )
    (candidate / "docs" / "qa" / "fixtures.json").write_text(json.dumps({
        "schema_version": 1, "status": "NOT_RUN", "reason": "no seeded fixtures", "fixtures": [],
    }), encoding="utf-8")
    (candidate / "tools" / "vst" / "__init__.py").write_text("\"\"\"Synthetic package.\"\"\"\n", encoding="utf-8")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _wheel_bytes()
    (wheelhouse / "pytest-9.0.3-py3-none-any.whl").write_bytes(wheel)
    (candidate / "tools" / "qa" / "requirements.lock").write_text(
        "# Wheel-only, exact hashes for a synthetic runner test.\n"
        "pytest==9.0.3 \\\n"
        f"    --hash=sha256:{hashlib.sha256(wheel).hexdigest()}\n", encoding="utf-8",
    )

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=candidate, check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)

    git("init")
    git("config", "user.name", "S4 functional test")
    git("config", "user.email", "s4-functional@example.invalid")
    git("add", "tests", "docs", "tools")
    git("commit", "-m", "synthetic dependency provenance candidate")
    manifest = build_registry.build_registry(candidate)
    manifest_path = candidate / "docs" / "qa" / "categories.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    git("add", "docs/qa/categories.json")
    git("commit", "-m", "add synthetic selector registry")

    target = tmp_path / "target"
    dependencies.prepare_dependency_target(candidate / "tools" / "qa" / "requirements.lock", wheelhouse, target)
    args = Namespace(
        category="functional", repo_root=str(candidate), manifest="docs/qa/categories.json",
        fixtures="docs/qa/fixtures.json", dependency_target=str(target),
        dependency_wheelhouse=str(wheelhouse), scratch_root=str(tmp_path / "scratch"),
        run_id="post-mutation", expected_head=None, timeout_seconds=30, output_cap_bytes=4096,
        report_path="docs/sdlc/evidence/qa/functional.report.jsonl",
        stdout_path="docs/sdlc/evidence/qa/functional.stdout.txt",
        stderr_path="docs/sdlc/evidence/qa/functional.stderr.txt",
        privileged_harness_proof=None, run_nonce=None,
    )

    def mutate_dependency_during_run(argv, *, cwd, timeout, cap, env):
        scratch = Path(env["TEMP"])
        selection = json.loads((scratch / "selection.json").read_text(encoding="utf-8"))
        collected = [
            {"node_id": test_id, "selector": selector, "outcome": "passed"}
            for test_id, selector in selection["expected_selectors"].items()
        ]
        (scratch / "events.json").write_text(json.dumps({
            "schema_version": 1, "collected": collected, "duplicates": [],
            "collection_errors": [], "fixture_observations": [],
        }), encoding="utf-8")
        (target / "pytest" / "__init__.py").write_bytes(b"changed after pytest began\n")
        return 0, b"synthetic test pass", b"", {
            "timed_out": False, "stdout_truncated": False, "stderr_truncated": False,
            "capture_incomplete": False,
        }

    monkeypatch.setattr(run, "_args", lambda: args)
    monkeypatch.setattr(run, "_runtime_profile", lambda: registry.WINDOWS_PROFILE)
    monkeypatch.setattr(run, "_git_status_paths", lambda _root: [])
    monkeypatch.setattr(run, "_run_bounded", mutate_dependency_during_run)
    monkeypatch.setattr(run.sys, "executable", run.EXPECTED_PYTHON_EXE)
    monkeypatch.setattr(run.sys, "path", list(run.sys.path))

    exit_code = run.main()
    report = json.loads((candidate / args.report_path).read_text(encoding="utf-8").splitlines()[-1])

    assert exit_code == 1
    assert "QA_RESULT FAIL" in capsys.readouterr().out
    assert report["schema_version"] == 3
    assert report["dependency_content_verified_before"] is True
    assert report["dependency_content_verified_after"] is False
    assert report["dependency_target_sha256_after"] is None
    assert report["dependency_execution_integrity"] == "NOT_VERIFIED"
    assert "QA dependency target or wheelhouse changed during test execution" in report["reasons"]
    assert report["dependency_wheels"] == [{
        "name": "pytest", "version": "9.0.3", "sha256": hashlib.sha256(wheel).hexdigest(),
    }]
    rendered = json.dumps(report, sort_keys=True)
    assert str(target) not in rendered
    assert str(wheelhouse) not in rendered
