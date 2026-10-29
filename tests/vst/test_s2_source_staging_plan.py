"""TP-18: immutable source staging-plan generation and truthful unknowns."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from tools.qa import prepare_wsl_runtime_plan as plan_module


def archive_bytes(files: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def required_files() -> dict[str, bytes]:
    result = {
        "docs/SANDBOX_SPEC.md": b"sandbox contract",
        "tools/qa/worker_exec.c": b"int main(void) { return 0; }",
        "tools/qa/install_wsl_worker_helper.sh": b"fixed compiler recipe",
        "tools/qa/install_wsl_runner_runtime.sh": b"fixed runtime recipe",
        "tools/qa/verify_wsl_source_bundle.py": b"source verifier",
        "tools/qa/verify_wsl_runtime_stage.py": b"stage verifier",
    }
    result.update({f"tools/vst/systemd/{unit}": unit.encode() for unit in plan_module.UNITS})
    return result


def install_fake_git(monkeypatch: pytest.MonkeyPatch, expected: str, payload: bytes) -> None:
    calls = []

    def fake_git(root: Path, *arguments: str) -> bytes:
        calls.append(arguments)
        if arguments[:2] == ("rev-parse", "--verify"):
            return (expected + "\n").encode("ascii")
        if arguments[:2] == ("archive", "--format=tar"):
            return payload
        raise AssertionError(f"unexpected git invocation: {arguments!r}")

    monkeypatch.setattr(plan_module, "_git", fake_git)


def test_prepare_plan_is_deterministic_and_binds_all_runtime_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path.resolve()
    head = "a" * 40
    files = required_files()
    payload = archive_bytes(files)
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", root)
    install_fake_git(monkeypatch, head, payload)

    first = plan_module.prepare_source_plan(root, head)
    second = plan_module.prepare_source_plan(root, head)

    assert first == second
    assert first["schema"] == "VST_S2_RUNTIME_SOURCE_PLAN_V2"
    assert first["status"] == "UNSIGNED_REVIEW_CANDIDATE"
    assert first["source_head"] == head
    assert first["sandbox_spec_sha256"] == __import__("hashlib").sha256(
        files["docs/SANDBOX_SPEC.md"]
    ).hexdigest()
    assert first["unit_sha256"] == {
        unit: __import__("hashlib").sha256(files[f"tools/vst/systemd/{unit}"]).hexdigest()
        for unit in plan_module.UNITS
    }
    assert first["helper"]["binary_sha256"] is None
    assert first["helper"]["compiler_provenance"] == "NOT_VERIFIED"
    assert first["target_inventory"] == "NOT_VERIFIED"
    assert first["store_disposition"] == "UNKNOWN"
    assert first["activation"] == "NOT_AUTHORIZED_BY_THIS_PLAN"
    assert not any(secret in repr(first).lower() for secret in ("private_key", "password", "token"))
    assert set(first["archive_files"]) == set(files)
    assert first["archive_members"] == {
        name: {"kind": "file", "sha256": __import__("hashlib").sha256(payload).hexdigest(),
               "size": len(payload)}
        for name, payload in files.items()
    }
    assert not list(root.iterdir())


def test_archive_input_change_changes_bound_plan_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path.resolve()
    head = "b" * 40
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", root)
    files = required_files()
    install_fake_git(monkeypatch, head, archive_bytes(files))
    original = plan_module.prepare_source_plan(root, head)

    files["docs/SANDBOX_SPEC.md"] = b"changed sandbox contract"
    install_fake_git(monkeypatch, head, archive_bytes(files))
    changed = plan_module.prepare_source_plan(root, head)

    assert original["archive_sha256"] != changed["archive_sha256"]
    assert original["sandbox_spec_sha256"] != changed["sandbox_spec_sha256"]


def test_source_plan_rejects_wrong_canonical_root_before_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_root = tmp_path / "canonical"
    wrong_root = tmp_path / "neighbor"
    expected_root.mkdir()
    wrong_root.mkdir()
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", expected_root.resolve())

    def unexpected_git(*_args: object) -> bytes:
        raise AssertionError("Git must not inspect a noncanonical checkout")

    monkeypatch.setattr(plan_module, "_git", unexpected_git)
    with pytest.raises(ValueError, match="canonical project checkout"):
        plan_module.prepare_source_plan(wrong_root, "c" * 40)


@pytest.mark.parametrize("head", ["c" * 39, "G" * 40, "d" * 40 + "0"])
def test_source_plan_rejects_malformed_or_mismatched_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, head: str,
) -> None:
    root = tmp_path.resolve()
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", root)
    with pytest.raises(ValueError, match="40 lowercase hex"):
        plan_module.prepare_source_plan(root, head)


def test_source_plan_rejects_checkout_head_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path.resolve()
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", root)
    install_fake_git(monkeypatch, "e" * 40, archive_bytes(required_files()))

    with pytest.raises(ValueError, match="checkout HEAD differs"):
        plan_module.prepare_source_plan(root, "f" * 40)


def test_source_plan_rejects_missing_runtime_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path.resolve()
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", root)
    files = required_files()
    del files["tools/vst/systemd/vst-runner.service"]
    install_fake_git(monkeypatch, "9" * 40, archive_bytes(files))

    with pytest.raises(ValueError, match="lacks a required runtime artifact"):
        plan_module.prepare_source_plan(root, "9" * 40)


@pytest.mark.parametrize("missing", [
    "tools/qa/verify_wsl_source_bundle.py",
    "tools/qa/verify_wsl_runtime_stage.py",
    "tools/vst/systemd/vst-runner.service",
])
def test_source_plan_rejects_missing_required_verifier_or_runtime_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    root = tmp_path.resolve()
    root.mkdir(exist_ok=True)
    monkeypatch.setattr(plan_module, "CANONICAL_ROOT", root)
    files = required_files()
    del files[missing]
    install_fake_git(monkeypatch, "9" * 40, archive_bytes(files))

    with pytest.raises(ValueError, match="lacks a required runtime artifact"):
        plan_module.prepare_source_plan(root, "9" * 40)
