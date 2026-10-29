"""S2-3 AC-1/2: exact bundle and fresh staged-tree source-map verification."""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest

from tools.qa import verify_wsl_runtime_stage as stage_verifier
from tools.qa import verify_wsl_source_bundle as bundle_verifier

pytestmark = pytest.mark.skipif(
    os.name != "posix" or getattr(os, "geteuid", lambda: 1)() != 0,
    reason="S2 installer verifier contract requires root-owned POSIX fixtures",
)

HEAD = "a" * 40
ARCHIVE_SHA = "b" * 64
PLAN_SHA = "c" * 64
INVENTORY_SHA = "d" * 64
COMPILER_SHA = "e" * 64
COMPILER_PATH = "/usr/bin/cc"
COMPILER_RESOLVED_PATH = "/usr/bin/x86_64-linux-gnu-gcc-13"
COMPILER_LINK = "/etc/alternatives/cc"

VST_FILES = {
    "tools/vst/runner.py", "tools/vst/signer.py", "tools/vst/store.py",
    "tools/vst/supervisor.py", "tools/vst/runner_service.py",
    "tools/vst/supervisor_service.py", "tools/vst/execution_grant.py",
    "tools/vst/runner_fence.py", "tools/vst/dispatcher_service.py",
    "tools/vst/dispatch_instruction.py", "tools/vst/dispatch_owner_client.py",
    "tools/vst/dispatch_owner_service.py", "tools/vst/dispatch_owner_latch.py",
}
UNIT_FILES = {"tools/vst/systemd/" + name for name in bundle_verifier.UNITS}


def _source_payloads() -> dict[str, bytes]:
    names = set(bundle_verifier.ALLOWED_FILES) | VST_FILES | UNIT_FILES
    return {name: ("fixture:" + name).encode("ascii") for name in names}


def _source_map(files: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    directories = {"tools", "tools/vst", "tools/qa", "tools/vst/systemd", "docs"}
    for name in files:
        parent = Path(name).parent
        while str(parent) != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    members: dict[str, dict[str, Any]] = {name: {"kind": "dir"} for name in directories}
    members.update({
        name: {"kind": "file", "sha256": hashlib.sha256(payload).hexdigest(),
               "size": len(payload)}
        for name, payload in files.items()
    })
    return members


def _write_file(path: Path, payload: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)


def _make_bundle(root: Path) -> tuple[dict[str, bytes], dict[str, dict[str, Any]], Path]:
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    files = _source_payloads()
    members = _source_map(files)
    for name, payload in files.items():
        _write_file(root / name, payload, 0o644)
    for name, entry in members.items():
        if entry["kind"] == "dir":
            (root / name).mkdir(parents=True, exist_ok=True)
            (root / name).chmod(0o755)
    manifest = {
        "archive_members": members,
        "archive_sha256": ARCHIVE_SHA,
        "compiler_path": COMPILER_PATH,
        "compiler_resolved_path": COMPILER_RESOLVED_PATH,
        "compiler_sha256": COMPILER_SHA,
        "compiler_symlink_target": COMPILER_LINK,
        "head": HEAD,
        "inventory_sha256": INVENTORY_SHA,
        "plan_sha256": PLAN_SHA,
        "schema": 3,
    }
    manifest_path = root / ".vst-source-manifest.json"
    _write_file(manifest_path, json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(), 0o600)
    return files, members, manifest_path


def _verify_bundle(root: Path) -> dict[str, Any]:
    return bundle_verifier.verify_source_bundle(
        root, expected_head=HEAD, expected_archive_sha256=ARCHIVE_SHA,
        expected_plan_sha256=PLAN_SHA, expected_inventory_sha256=INVENTORY_SHA,
    )


@pytest.mark.parametrize("mutation", ["modified", "missing", "extra", "symlink", "hardlink", "fifo"])
def test_source_bundle_rejects_any_extracted_tree_difference(
    tmp_path: Path, mutation: str,
) -> None:
    root = tmp_path / "source-bundle"
    files, _members, _manifest = _make_bundle(root)
    victim = root / "tools/vst/store.py"
    if mutation == "modified":
        victim.write_bytes(b"altered after approved plan")
    elif mutation == "missing":
        victim.unlink()
    elif mutation == "extra":
        _write_file(root / "tools/vst/unreviewed.py", b"unexpected", 0o644)
    elif mutation == "symlink":
        victim.unlink()
        victim.symlink_to(root / "tools/vst/runner.py")
    elif mutation == "hardlink":
        victim.unlink()
        os.link(root / "tools/vst/runner.py", victim)
    else:
        victim.unlink()
        os.mkfifo(victim)

    with pytest.raises(SystemExit, match="source tree|member map|changed type or identity while opening"):
        _verify_bundle(root)


def _make_stage(root: Path, source_root: Path, files: dict[str, bytes],
                members: dict[str, dict[str, Any]]) -> None:
    root.mkdir(mode=0o755)
    runtime_members = {
        name: entry for name, entry in members.items()
        if name in {"tools", "tools/vst", "docs"}
        or name.startswith("tools/vst/") or name.startswith("docs/")
    }
    for name, entry in runtime_members.items():
        path = root / name
        if entry["kind"] == "dir":
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(0o755)
        else:
            _write_file(path, files[name], 0o644)
    marker = {
        "archive_sha256": ARCHIVE_SHA,
        "compiler_path": COMPILER_PATH,
        "compiler_resolved_path": COMPILER_RESOLVED_PATH,
        "compiler_sha256": COMPILER_SHA,
        "compiler_symlink_target": COMPILER_LINK,
        "head": HEAD,
        "inventory_sha256": INVENTORY_SHA,
        "plan_sha256": PLAN_SHA,
        "schema": 3,
    }
    _write_file(root / ".vst-runtime-manifest.json",
                json.dumps(marker, sort_keys=True, separators=(",", ":")).encode(), 0o644)
    root.chmod(0o755)


def _verify_stage(stage: Path, manifest_path: Path) -> dict[str, Any]:
    return stage_verifier.verify_staged_runtime(
        stage, manifest_path, expected_head=HEAD, archive_sha256=ARCHIVE_SHA,
        plan_sha256=PLAN_SHA, inventory_sha256=INVENTORY_SHA,
    )


def test_fresh_stage_accepts_exact_reviewed_source_map(tmp_path: Path) -> None:
    source_root = tmp_path / "source-bundle"
    files, members, manifest_path = _make_bundle(source_root)
    stage = tmp_path / "fresh-stage"
    _make_stage(stage, source_root, files, members)

    marker = _verify_stage(stage, manifest_path)

    assert marker["head"] == HEAD
    assert marker["archive_sha256"] == ARCHIVE_SHA
    assert marker["plan_sha256"] == PLAN_SHA
    assert marker["inventory_sha256"] == INVENTORY_SHA
    assert marker["compiler_sha256"] == COMPILER_SHA


@pytest.mark.parametrize("mutation", ["modified", "missing", "extra", "symlink", "hardlink", "fifo"])
def test_fresh_stage_refuses_tree_that_differs_from_reviewed_source_map(
    tmp_path: Path, mutation: str,
) -> None:
    source_root = tmp_path / "source-bundle"
    files, members, manifest_path = _make_bundle(source_root)
    stage = tmp_path / "fresh-stage"
    _make_stage(stage, source_root, files, members)
    victim = stage / "tools/vst/store.py"
    if mutation == "modified":
        victim.write_bytes(b"altered after source verification")
    elif mutation == "missing":
        victim.unlink()
    elif mutation == "extra":
        _write_file(stage / "tools/vst/unreviewed.py", b"unexpected", 0o644)
    elif mutation == "symlink":
        victim.unlink()
        victim.symlink_to(stage / "tools/vst/runner.py")
    elif mutation == "hardlink":
        victim.unlink()
        os.link(stage / "tools/vst/runner.py", victim)
    else:
        victim.unlink()
        os.mkfifo(victim)

    with pytest.raises(SystemExit, match=(
        "staged tree|tree differs|symlink or special|changed type or identity while opening|link count is invalid"
    )):
        _verify_stage(stage, manifest_path)
