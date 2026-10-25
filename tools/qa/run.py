"""Manifest-driven pytest runner that delegates v2 evidence signing to VST."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tools.vst.contracts import ContractError
from tools.vst.runner import run_manifest_commands

from .registry import (
    PRIMARY_CATEGORIES,
    REGRESSION_CATEGORIES,
    load_manifest,
    load_registry,
    load_seeded_failure_catalog,
    validate_projection,
    SEEDED_CATALOG_PATH,
)


PINNED_PYTHON_VERSION = "3.12.3"
PINNED_PYTEST_VERSION = "7.4.4"
PINNED_RUNTIME_ID = "Ubuntu-24.04"
DEFAULT_REGISTRY = "docs/qa/categories.json"
DEFAULT_LOCK = "tools/qa/requirements.lock"
MAX_LOCK_BYTES = 64 * 1024


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


def _os_release_id() -> str:
    try:
        data = platform.freedesktop_os_release()
    except (AttributeError, OSError):
        return "UNKNOWN"
    name = data.get("ID", "").lower()
    version = data.get("VERSION_ID", "")
    if name == "ubuntu" and version == "24.04":
        return PINNED_RUNTIME_ID
    return f"{name or 'UNKNOWN'}-{version or 'UNKNOWN'}"


def _read_lock(root: Path, relative_path: str) -> tuple[bytes, str, dict[str, str]]:
    if os.path.isabs(relative_path) or ".." in Path(relative_path).parts:
        raise ContractError("dependency lock path must be repository-relative")
    path = root / relative_path
    if path.is_symlink() or not path.is_file():
        raise ContractError("dependency lock is missing or linked")
    with path.open("rb") as handle:
        raw = handle.read(MAX_LOCK_BYTES + 1)
    if len(raw) > MAX_LOCK_BYTES:
        raise ContractError("dependency lock exceeds size limit")
    digest = hashlib.sha256(raw).hexdigest()
    pinned: dict[str, str] = {}
    current: tuple[str, str] | None = None
    hashes: list[str] = []
    def finish_entry() -> None:
        nonlocal current, hashes
        if current is None:
            return
        name, version = current
        if not hashes:
            raise ContractError(f"dependency lock entry lacks a SHA-256 hash: {name}")
        if name in pinned:
            raise ContractError(f"dependency lock has a duplicate package: {name}")
        pinned[name] = version
        current, hashes = None, []
    for raw_line in raw.decode("utf-8").splitlines():
        text = raw_line.strip()
        if not text or text.startswith("#"):
            continue
        if "==" in text:
            finish_entry()
            package_version = text.split("\\", 1)[0].strip()
            name, version = package_version.split("==", 1)
            current = (name.lower().replace("_", "-"), version)
        elif current is None:
            raise ContractError("dependency lock hash is not attached to a pinned package")
        hashes.extend(re.findall(r"--hash=sha256:([0-9a-f]{64})", text))
        if not text.endswith("\\"):
            finish_entry()
    finish_entry()
    if not pinned:
        raise ContractError("dependency lock has no packages")
    return raw, digest, pinned


def _check_runtime(root: Path, lock_path: str) -> tuple[str, str, str]:
    if os.name != "posix":
        raise ContractError("S4 v2 QA execution requires the named POSIX WSL runtime")
    python_version = platform.python_version()
    runtime_id = _os_release_id()
    if python_version != PINNED_PYTHON_VERSION or runtime_id != PINNED_RUNTIME_ID:
        raise ContractError(
            f"runtime is NOT_RUN: expected {PINNED_RUNTIME_ID}/Python {PINNED_PYTHON_VERSION}; "
            f"found {runtime_id}/Python {python_version}"
        )
    _, lock_hash, pinned = _read_lock(root, lock_path)
    try:
        installed = {
            item.metadata["Name"].lower().replace("_", "-"): item.version
            for item in importlib.metadata.distributions()
            if item.metadata.get("Name")
        }
    except importlib.metadata.PackageNotFoundError as exc:
        raise ContractError(f"installed QA dependency inventory is unavailable: {exc}") from exc
    missing_or_changed = {
        name: {"required": version, "installed": installed.get(name)}
        for name, version in pinned.items()
        if installed.get(name) != version
    }
    if missing_or_changed:
        raise ContractError(f"locked QA dependencies are missing or changed: {missing_or_changed}")
    pytest_version = installed.get("pytest")
    if pytest_version != PINNED_PYTEST_VERSION:
        raise ContractError(f"expected pytest {PINNED_PYTEST_VERSION}; found {pytest_version}")
    return python_version, pytest_version, lock_hash


def _safe_output_dir(root: Path, worker_gid: int) -> tuple[Path, str]:
    base = root / ".vst-qa-runs"
    if base.is_symlink():
        raise ContractError("QA output directory must not be a symlink")
    if not base.exists():
        base.mkdir(mode=0o2710)
        os.chmod(base, 0o2710)
    base_stat = base.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(base_stat.st_mode) or base_stat.st_uid != os.geteuid() or
            base_stat.st_gid != worker_gid or stat.S_IMODE(base_stat.st_mode) != 0o2710):
        raise ContractError("QA output base must be runner-owned worker-group mode 2710")
    run_path = base / uuid.uuid4().hex
    run_path.mkdir(mode=0o730)
    try:
        os.chmod(run_path, 0o730)
    except OSError as exc:
        raise ContractError(f"cannot grant the isolated worker group access to run artifacts: {exc}") from exc
    run_stat = run_path.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(run_stat.st_mode) or run_stat.st_uid != os.geteuid() or
            run_stat.st_gid != worker_gid or stat.S_IMODE(run_stat.st_mode) != 0o730):
        raise ContractError("QA run artifact directory did not receive the bounded worker-group mode")
    relative = run_path.relative_to(root).as_posix()
    return run_path, relative


def _worker_writable(path: Path, worker_uid: int, worker_gid: int) -> bool:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    mode = stat.S_IMODE(info.st_mode)
    if info.st_uid == worker_uid:
        return bool(mode & stat.S_IWUSR)
    if info.st_gid == worker_gid:
        return bool(mode & stat.S_IWGRP)
    return bool(mode & stat.S_IWOTH)


def _require_worker_source_read_only(root: Path, worker_uid: int, worker_gid: int) -> None:
    """Refuse QA execution if worker identity can write source, registry, or Git state."""
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False,
        )
        git_dirs = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir", "--git-common-dir"], cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=5, check=False, text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"cannot verify read-only QA source boundary: {exc}") from exc
    if listed.returncode != 0 or git_dirs.returncode != 0:
        raise ContractError("cannot enumerate tracked QA source for the read-only boundary")
    candidates = {root, root / ".git"}
    cursor = root
    while True:
        candidates.add(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    output_base = root / ".vst-qa-runs"
    pending_source = [root]
    visited_source: set[Path] = set()
    while pending_source:
        directory = pending_source.pop()
        if directory in visited_source:
            continue
        visited_source.add(directory)
        if len(visited_source) > 200000:
            raise ContractError("repository source tree exceeds the bounded permission walk")
        if directory == output_base or output_base in directory.parents:
            continue
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    child = Path(entry.path)
                    if child == root / ".git" or child == output_base:
                        continue
                    candidates.add(child)
                    if entry.is_dir(follow_symlinks=False):
                        pending_source.append(child)
        except OSError as exc:
            raise ContractError("cannot inspect the complete repository source tree") from exc
    for raw_path in listed.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            relative = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError("tracked source path is not UTF-8") from exc
        file_path = root / relative
        candidates.add(file_path)
        parent = file_path.parent
        while parent != root and root in parent.parents:
            candidates.add(parent)
            parent = parent.parent
    metadata_roots = []
    for value in git_dirs.stdout.splitlines():
        metadata_path = Path(value.strip())
        if not metadata_path.is_absolute():
            metadata_path = root / metadata_path
        metadata_path = Path(os.path.abspath(metadata_path))
        chain = []
        cursor = metadata_path
        while True:
            chain.append(cursor)
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
        for component in reversed(chain):
            try:
                component_info = component.lstat()
            except OSError as exc:
                raise ContractError("Git metadata path is missing or unreadable") from exc
            if stat.S_ISLNK(component_info.st_mode):
                raise ContractError("Git metadata path contains a symbolic link")
            candidates.add(component)
        metadata_roots.append(metadata_path)
    if len(metadata_roots) != 2:
        raise ContractError("Git did not identify both worktree and common metadata directories")
    for metadata_root in metadata_roots:
        cursor = metadata_root
        while True:
            candidates.add(cursor)
            if cursor.parent == cursor:
                break
            cursor = cursor.parent
    pending = list(metadata_roots)
    visited: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        candidates.add(path)
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ContractError("Git metadata tree contains a symbolic link")
            if stat.S_ISDIR(info.st_mode):
                with os.scandir(path) as entries:
                    for entry in entries:
                        if len(visited) + len(pending) > 200000:
                            raise ContractError("Git metadata tree exceeds the bounded traversal limit")
                        pending.append(Path(entry.path))
        except OSError as exc:
            raise ContractError("cannot inspect the complete Git metadata tree") from exc
    for path in candidates:
        if path == output_base or output_base in path.parents:
            continue
        if not path.exists() and not path.is_symlink():
            raise ContractError(f"tracked QA source path is missing: {path.relative_to(root) if root in path.parents else '.git'}")
        if _worker_writable(path, worker_uid, worker_gid):
            label = path.relative_to(root).as_posix() if root in path.parents else ".git"
            raise ContractError(f"QA worker identity can write source or Git state: {label}")


def _current_head(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False, text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def _category_receipt(
    *, root: Path, category: str, registry: dict, registry_hash: str,
    registry_path: str, manifest: dict, manifest_hash: str,
    lock_path: str, lock_hash: str, python_version: str,
    pytest_version: str, runtime_id: str, signer_socket: str,
    seeded_catalog: dict, seeded_catalog_hash: str,
    runner_id: str, worker_uid: int, worker_gid: int,
    attempt: int, epoch: int, resolved_model: str,
) -> dict:
    entry = registry["categories"][category]
    if entry["state"] == "NOT_RUN":
        return {
            "state": "NOT_RUN", "category": category,
            "reason": entry["reason"], "next_step": entry["next_step"],
            "owner": entry["owner_role"],
        }
    validate_projection(registry, manifest)
    if entry["coverage_state"] != "COMPLETE":
        return {
            "state": "INCONCLUSIVE", "category": category,
            "reason": "The committed category denominator is provisional/partial; no signed receipt may be produced.",
            "coverage_state": entry["coverage_state"],
            "category_source_head": entry["source_head"],
        }
    _require_worker_source_read_only(root, worker_uid, worker_gid)
    run_dir, relative_run_dir = _safe_output_dir(root, worker_gid)
    events_relative = f"{relative_run_dir}/{category}-events.json"
    report_relative = f"{relative_run_dir}/{category}-report.json"
    invocation_id = uuid.uuid4().hex
    stdout_ref_relative = f"{relative_run_dir}/{category}-stdout-ref.json"
    stderr_ref_relative = f"{relative_run_dir}/{category}-stderr-ref.json"
    artifacts = [registry_path, SEEDED_CATALOG_PATH, lock_path, events_relative, report_relative,
                 stdout_ref_relative, stderr_ref_relative]
    receipt = run_manifest_commands(
        manifest=manifest, slot=category, attempt=attempt, epoch=epoch,
        resolved_model=resolved_model, invocation_id=invocation_id,
        runner_id=runner_id, signer_socket=signer_socket, cwd=str(root),
        worker_uid=worker_uid, worker_gid=worker_gid,
        created_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        artifact_paths=artifacts, extra_env={"VST_QA_EVENTS_PATH": events_relative},
        report_artifact_path=report_relative, test_events_path=events_relative,
        report_metadata={
            "category": category,
            "coverage_state": entry["coverage_state"],
            "category_source_head": entry["source_head"],
            "category_registry_path": registry_path,
            "category_registry_sha256": registry_hash,
            "seeded_catalog_path": SEEDED_CATALOG_PATH,
            "seeded_catalog_sha256": seeded_catalog_hash,
            "seeded_failure_fixtures": (
                seeded_catalog["fixtures"] if category == "seeded-failure" else []
            ),
            "stdout_artifact_path": stdout_ref_relative,
            "stderr_artifact_path": stderr_ref_relative,
            "dependency_lock_path": lock_path,
            "dependency_lock_sha256": lock_hash,
            "interpreter_version": python_version,
            "pytest_version": pytest_version,
            "runtime_id": runtime_id,
        },
    )
    return {"state": receipt["result"], "category": category, "receipt": receipt}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="in-scope repository snapshot root")
    parser.add_argument("--manifest", required=True, help="repository-relative validated VST v2 task manifest")
    parser.add_argument("--category", required=True, choices=(*PRIMARY_CATEGORIES, "regression"))
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--lock", default=DEFAULT_LOCK)
    parser.add_argument("--signer-socket", required=True)
    parser.add_argument("--runner-id", required=True)
    parser.add_argument("--worker-uid", required=True, type=int)
    parser.add_argument("--worker-gid", required=True, type=int)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--epoch", required=True, type=int)
    parser.add_argument("--resolved-model", required=True)
    args = parser.parse_args(argv)
    try:
        root = Path(args.cwd).resolve(strict=True)
        if not root.is_dir():
            raise ContractError("cwd is not a repository directory")
        python_version, pytest_version, lock_hash = _check_runtime(root, args.lock)
        runtime_id = _os_release_id()
        registry, registry_hash = load_registry(root, args.registry)
        seeded_catalog, seeded_catalog_hash = load_seeded_failure_catalog(root, registry)
        manifest, manifest_hash = load_manifest(root, args.manifest)
        results = []
        categories = (
            REGRESSION_CATEGORIES if args.category == "regression" else (args.category,)
        )
        for category in categories:
            results.append(_category_receipt(
                root=root, category=category, registry=registry,
                registry_hash=registry_hash, registry_path=args.registry,
                manifest=manifest, manifest_hash=manifest_hash,
                lock_path=args.lock, lock_hash=lock_hash,
                python_version=python_version, pytest_version=pytest_version,
                runtime_id=runtime_id, signer_socket=args.signer_socket,
                seeded_catalog=seeded_catalog, seeded_catalog_hash=seeded_catalog_hash,
                runner_id=args.runner_id, worker_uid=args.worker_uid,
                worker_gid=args.worker_gid, attempt=args.attempt, epoch=args.epoch,
                resolved_model=args.resolved_model,
            ))
        _emit({
            "schema_version": 1,
            "category": args.category,
            "manifest_sha256": manifest_hash,
            "category_registry_sha256": registry_hash,
            "candidate_head": next(
                (item["receipt"]["candidate_head"] for item in results if "receipt" in item),
                _current_head(root),
            ),
            "results": results,
        })
        if all(result["state"] == "PASS" for result in results):
            return 0
        return 2
    except (ContractError, OSError, ValueError) as exc:
        _emit({"schema_version": 1, "category": args.category, "state": "BLOCKED", "reason": str(exc)[:1024]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
