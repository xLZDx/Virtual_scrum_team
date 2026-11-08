"""Bounded native pytest runner for one registry category (S4-B, Windows profile only).

Scope: runs the registry selectors of ONE category assigned to the
windows-cpython-3.14.3 profile under a wall-clock timeout, kills the whole
process tree on timeout, and appends a JSON Lines report plus raw stdout/stderr
artifacts at the fixed paths docs/sdlc/evidence/qa/<category>.*. WSL profiles
are out of scope (operator decision) and are recorded NOT_RUN in every report.
Every refusal is fail-closed: a durable BLOCKED/NOT_RUN record is written when
the artifact paths are known, and the exit code is non-zero.
"""

from __future__ import annotations

import argparse
import ntpath
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.vst.runner import (
    EXIT_CAPTURE_INCOMPLETE,
    EXIT_MISSING_EXECUTABLE,
    EXIT_OUTPUT_TRUNCATED,
    EXIT_TIMEOUT,
    _Capture,
    _JobObject,
    _kill_tree,
    _resume_suspended_primary_thread,
    _spawn_kwargs,
    build_environment,
)

from .dependencies import DependencyProvenanceError, verify_dependency_environment
from .registry import (
    ALL_CATEGORIES,
    WINDOWS_PROFILE,
    WSL_PROFILE,
    WSL_ROOT_PROFILE,
    RegistryError,
    ValidatedRegistry,
    git_head,
    git_root,
    validate_registry,
)
from .report import encode_report, sha256_bytes


MAX_TIMEOUT_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 900
MAX_CAPTURE_BYTES = 4 * 1024 * 1024
EXPECTED_PYTHON_EXE = r"C:\Python314\python.exe"
WSL_NOT_RUN_REASON = (
    "WSL execution is out of scope for S4-B (operator decision); recorded NOT_RUN, never faked"
)
CATEGORIES = ALL_CATEGORIES | {"seeded-failure"}
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SAFE_RELATIVE = re.compile(r"[A-Za-z0-9_./-]+\Z")
_SENSITIVE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|authorization)"
    r"\s*[:=]\s*[^\s,;]{4,}"
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_USER_PATH = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s\"']+(?:\\[^\\\s\"']+)*")


class QARunError(ValueError):
    """Raised for invalid CLI contracts or unsafe state before test code can start."""


def _args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--manifest", default="docs/qa/categories.json")
    parser.add_argument("--dependency-target", required=True,
                        help="directory prepared by tools.qa.prepare_dependencies (outside the repo)")
    parser.add_argument("--dependency-wheelhouse", required=True,
                        help="directory holding the locked wheels (outside the repo)")
    parser.add_argument("--scratch-root", required=True, help="existing-or-new directory outside the repo")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output-cap-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--stderr-path", required=True)
    return parser.parse_args(argv)


def _canonical_relative(value: str, context: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or value.startswith("/")
        or ":" in value
        or not _SAFE_RELATIVE.fullmatch(value)
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise QARunError(f"{context} must be a canonical relative path")
    return value


def _safe_target(root: Path, relative: str) -> Path:
    rel = _canonical_relative(relative, "artifact path")
    path = root.joinpath(*rel.split("/"))
    current = root
    for part in rel.split("/")[:-1]:
        current = current / part
        if current.exists() and (current.is_symlink() or getattr(current, "is_junction", lambda: False)()):
            raise QARunError("artifact path crosses a link")
    if not path.resolve(strict=False).is_relative_to(root):
        raise QARunError("artifact path escapes its root")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise QARunError("artifact target is not a regular file")
    if path.exists() and path.stat().st_nlink != 1:
        raise QARunError("artifact target has unexpected hard links")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _repo_paths(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Path]]:
    repo_root = git_root(args.repo_root)
    if repo_root != Path(args.repo_root).resolve(strict=True):
        raise QARunError("repo-root must be the candidate repository root")
    scratch = Path(args.scratch_root).resolve(strict=False)
    if scratch == repo_root or scratch.is_relative_to(repo_root) or repo_root.is_relative_to(scratch):
        raise QARunError("scratch-root must be outside the candidate repository")
    if not _RUN_ID.fullmatch(args.run_id):
        raise QARunError("run-id is invalid")
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise QARunError("timeout-seconds is outside the supported bound")
    if not 1 <= args.output_cap_bytes <= MAX_CAPTURE_BYTES:
        raise QARunError("output-cap-bytes is outside the supported bound")
    base = f"docs/sdlc/evidence/qa/{args.category}"
    expected = {
        "report": f"{base}.report.jsonl",
        "stdout": f"{base}.stdout.txt",
        "stderr": f"{base}.stderr.txt",
    }
    supplied = {"report": args.report_path, "stdout": args.stdout_path, "stderr": args.stderr_path}
    if supplied != expected:
        raise QARunError("artifact paths must match the fixed append-only category paths")
    return repo_root, scratch, {key: _safe_target(repo_root, rel) for key, rel in expected.items()}


def _git_status_paths(root: Path) -> list[str]:
    command = [
        "git", "-c", "safe.directory=", "-c", f"safe.directory={os.fspath(root)}",
        "status", "--porcelain=v1", "-z", "--untracked-files=all",
    ]
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    try:
        result = subprocess.run(
            command, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=30, check=False, shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise QARunError("could not determine candidate worktree state") from None
    if result.returncode != 0:
        raise QARunError("could not determine candidate worktree state")
    tokens = result.stdout.decode("utf-8", errors="replace").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        paths.append((token[3:] if len(token) >= 4 else "").replace("\\", "/"))
        if token[:2].strip() and ("R" in token[:2] or "C" in token[:2]) and index < len(tokens):
            if tokens[index]:
                paths.append(tokens[index].replace("\\", "/"))
            index += 1
    return sorted(set(paths))


def _known_artifact_paths() -> set[str]:
    return {
        f"docs/sdlc/evidence/qa/{category}.{kind}"
        for category in CATEGORIES
        for kind in ("report.jsonl", "stdout.txt", "stderr.txt")
    } | {"docs/sdlc/evidence/qa/matrix.report.jsonl"}


def _unexpected_candidate_paths(paths: list[str]) -> list[str]:
    return sorted(set(paths) - _known_artifact_paths())


def _append_raw_artifact(path: Path, data: bytes) -> dict[str, Any]:
    payload = data if not data or data.endswith(b"\n") else data + b"\n"
    start = path.stat().st_size if path.exists() else 0
    with path.open("ab") as handle:
        handle.write(payload)
    end = path.stat().st_size
    return {"start": start, "end": end, "size": end - start, "sha256": sha256_bytes(payload)}


def _append_run_outputs(
    report: dict[str, Any], stdout_path: Path, stdout: bytes, stderr_path: Path, stderr: bytes
) -> None:
    # check_artifact_stage rejects empty artifact files, so never leave one empty.
    out = _append_raw_artifact(stdout_path, stdout or b"(no stdout)")
    err = _append_raw_artifact(stderr_path, stderr or b"(no stderr)")
    report["artifact_digests"] = {"stdout": out["sha256"], "stderr": err["sha256"]}
    report["artifact_ranges"] = {
        "stdout": {"start": out["start"], "end": out["end"]},
        "stderr": {"start": err["start"], "end": err["end"]},
    }
    report["artifact_sizes"] = {"stdout": out["size"], "stderr": err["size"]}


def _append_report(path: Path, report: dict[str, Any]) -> None:
    with path.open("ab") as handle:
        handle.write(encode_report(report))


def _runtime_profile() -> str | None:
    """Windows profile only: CPython 3.14.3 at the pinned interpreter path."""
    if (
        os.name == "nt"
        and platform.system() == "Windows"
        and platform.python_implementation() == "CPython"
        and platform.python_version() == "3.14.3"
        and ntpath.normcase(ntpath.normpath(os.path.realpath(sys.executable)))
        == ntpath.normcase(ntpath.normpath(EXPECTED_PYTHON_EXE))
    ):
        return WINDOWS_PROFILE
    return None


def _run_bounded(
    argv: list[str], *, cwd: Path, timeout: int, cap: int, env: dict[str, str]
) -> tuple[int, bytes, bytes, dict[str, Any]]:
    """Run pytest with bounded pipes; on timeout the whole process tree is killed.

    On Windows the child starts suspended, is attached to a kill-on-close Job
    Object before it runs, and the job is terminated on timeout and after exit.
    """
    info: dict[str, Any] = {
        "timed_out": False,
        "capture_incomplete": False,
        "stdout_truncated": False,
        "stderr_truncated": False,
        "job_object": False,
    }
    process: subprocess.Popen[bytes] | None = None
    job = None
    stdout_capture = None
    stderr_capture = None
    completed = False
    kill_failed = False
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, bufsize=0,
            **_spawn_kwargs(suspended=os.name == "nt"),
        )
        if os.name == "nt":
            job = _JobObject.attach(process)
            info["job_object"] = job is not None
            if job is None or not _resume_suspended_primary_thread(process.pid):
                if job is not None:
                    job.terminate_and_close()
                    job = None
                info["capture_incomplete"] = True
                _kill_tree(process)
                process.wait(timeout=10)
                completed = True
                return EXIT_CAPTURE_INCOMPLETE, b"", b"", info
        stdout_capture = _Capture(process.stdout, cap)
        stderr_capture = _Capture(process.stderr, cap)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            info["timed_out"] = True
            if job is not None:
                job.terminate_and_close()
                job = None
            _kill_tree(process)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                kill_failed = True
        else:
            if job is not None:
                job.terminate_and_close()
                job = None
            else:
                _kill_tree(process)
        completed = True
    except (OSError, subprocess.TimeoutExpired):
        info["capture_incomplete"] = True
        if process is None:
            return EXIT_MISSING_EXECUTABLE, b"", b"", info
        _kill_tree(process)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            kill_failed = True
    finally:
        if job is not None:
            job.terminate_and_close()
        if process is not None and not completed:
            _kill_tree(process)
        for capture in (stdout_capture, stderr_capture):
            if capture is not None:
                capture.finish()
        if process is not None:
            for capture, stream in ((stdout_capture, process.stdout), (stderr_capture, process.stderr)):
                if stream is not None and (capture is None or not capture.alive):
                    try:
                        stream.close()
                    except Exception:  # noqa: BLE001
                        pass
    if stdout_capture is None or stderr_capture is None:
        return EXIT_CAPTURE_INCOMPLETE, b"", b"", {**info, "capture_incomplete": True}
    info["stdout_truncated"] = stdout_capture.truncated
    info["stderr_truncated"] = stderr_capture.truncated
    info["capture_incomplete"] = (
        info["capture_incomplete"] or stdout_capture.incomplete or stderr_capture.incomplete or kill_failed
    )
    if info["capture_incomplete"]:
        code = EXIT_CAPTURE_INCOMPLETE
    elif info["timed_out"]:
        code = EXIT_TIMEOUT
    elif stdout_capture.truncated or stderr_capture.truncated:
        code = EXIT_OUTPUT_TRUNCATED
    else:
        code = process.returncode if process.returncode is not None else EXIT_TIMEOUT
    return code, bytes(stdout_capture.data), bytes(stderr_capture.data), info


def _redact(data: bytes, *, repo_root: Path, scratch_root: Path) -> bytes:
    text = data.decode("utf-8", errors="replace")
    paths = [(repo_root, "<candidate-root>"), (scratch_root, "<scratch-root>")]
    temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp:
        paths.append((Path(temp), "<system-temp>"))
    for path, replacement in paths:
        text = text.replace(os.fspath(path), replacement)
        text = text.replace(os.fspath(path).replace("\\", "/"), replacement)
    text = _USER_PATH.sub("<user-path>", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} <redacted>", text)
    text = _SENSITIVE.sub(lambda m: f"{m.group(1)}=<redacted>", text)
    return text.encode("utf-8")


def _run_id_dir(scratch_root: Path, run_id: str) -> Path:
    path = scratch_root / run_id
    if path.exists() or path.is_symlink():
        raise QARunError("scratch run directory already exists; refusing to overwrite it")
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve(strict=True)


def _report_base(
    *, args: argparse.Namespace, root: Path, registry: ValidatedRegistry | None,
    head: str | None, before_paths: list[str], output_paths: dict[str, Path],
) -> dict[str, Any]:
    profile = args._runtime_profile
    not_run = registry.category_not_run.get(args.category, {}) if registry else {}
    inventory = registry.category_inventory_ids.get(args.category, []) if registry else []
    if registry is not None and profile == WINDOWS_PROFILE:
        expected = registry.category_profile_test_ids[args.category][profile]
        unassigned = [
            t for t in registry.category_profile_unassigned_ids[args.category][profile] if t not in not_run
        ]
    else:
        expected, unassigned = [], [t for t in inventory if t not in not_run]
    return {
        "schema_version": 3,
        "sprint": "S4",
        "run_id": args.run_id,
        "category": args.category,
        "candidate_head": head,
        "branch": None,
        "dirty_tree": {
            "before": bool(_unexpected_candidate_paths(before_paths)),
            "before_paths": _unexpected_candidate_paths(before_paths),
            "after": None,
            "after_paths": [],
        },
        "registry_sha256": registry.sha256 if registry else None,
        "source_head": registry.data["source_head"] if registry else None,
        "lock_sha256": None,
        "manifest_path": args.manifest,
        "expected_test_ids": expected,
        "inventory_test_ids": inventory,
        "unassigned_test_ids": unassigned,
        "not_run_test_reasons": not_run,
        "collected_node_ids": [],
        "executed_node_ids": [],
        "passed_test_ids": [],
        "failed_test_ids": [],
        "skipped_test_ids": [],
        "xfail_test_ids": [],
        "unexpected_node_ids": [],
        "uncollected_test_ids": [],
        "case_outcomes": [],
        "command": [],
        "exit_code": None,
        "duration_seconds": None,
        "runtime_profile": profile,
        "interpreter": {
            "id": f"{platform.python_implementation()}-{platform.python_version()}",
            "executable": "C:/Python314/python.exe" if profile == WINDOWS_PROFILE else None,
            "version": platform.python_version(),
        },
        "profile_status": {
            WINDOWS_PROFILE: "EXECUTED" if profile == WINDOWS_PROFILE else "NOT_RUN",
            WSL_PROFILE: "NOT_RUN",
            WSL_ROOT_PROFILE: "NOT_RUN",
        },
        "profile_not_run_reason": WSL_NOT_RUN_REASON,
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "dependency_target": "isolated-external-target",
        },
        "pytest_version": None,
        "dependency_versions": {},
        "dependency_wheels": [],
        "dependency_target_sha256": None,
        "dependency_target_sha256_after": None,
        "dependency_content_verified_before": False,
        "dependency_content_verified_after": False,
        "artifact_paths": {key: path.relative_to(root).as_posix() for key, path in output_paths.items()},
        "artifact_digests": {},
        "artifact_ranges": {},
        "artifact_sizes": {},
        "capture": {},
        "result": "BLOCKED",
        "reasons": [],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "normalized_sha256": None,
    }


def _resolve_cases(
    events: dict[str, Any], expected_ids: list[str], selectors: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Map concrete pytest cases to registry selectors; a selector with no case is NOT passed."""
    rows = events.get("collected")
    if not isinstance(rows, list):
        raise QARunError("pytest event file has no collected case list")
    ids = [row.get("node_id") for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        raise QARunError("pytest event file contains invalid or duplicate concrete node IDs")
    selector_cases: dict[str, list[dict[str, str]]] = {test_id: [] for test_id in expected_ids}
    unexpected: list[str] = []
    case_outcomes: list[dict[str, str]] = []
    for row in rows:
        node_id, selector, outcome = row.get("node_id"), row.get("selector"), row.get("outcome")
        if not isinstance(node_id, str) or outcome not in {
            "passed", "failed", "skipped", "xfailed", "xpassed", "not_run"
        }:
            raise QARunError("pytest event contains invalid case fields")
        if not isinstance(selector, str) or selector not in selectors or selector not in selector_cases:
            unexpected.append(node_id)
            selector_id = ""
        else:
            selector_id = selector
            selector_cases[selector].append({"node_id": node_id, "outcome": outcome})
        case_outcomes.append({"node_id": node_id, "selector_id": selector_id, "outcome": outcome})
    case_outcomes.sort(key=lambda row: row["node_id"])
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    xfailed: list[str] = []
    executed: list[str] = []
    for test_id, cases in sorted(selector_cases.items()):
        outcomes = {case["outcome"] for case in cases}
        executed.extend(case["node_id"] for case in cases if case["outcome"] != "not_run")
        if "failed" in outcomes or "xpassed" in outcomes:
            failed.append(test_id)
        elif "skipped" in outcomes:
            skipped.append(test_id)
        elif "xfailed" in outcomes:
            xfailed.append(test_id)
        elif cases and outcomes == {"passed"}:
            passed.append(test_id)
        elif cases and "not_run" in outcomes:
            failed.append(test_id)
    return {
        "collected_node_ids": sorted(ids),
        "executed_node_ids": sorted(executed),
        "passed_test_ids": passed,
        "failed_test_ids": failed,
        "skipped_test_ids": skipped,
        "xfail_test_ids": xfailed,
        "unexpected_node_ids": sorted(unexpected),
        "uncollected_test_ids": sorted(t for t, cases in selector_cases.items() if not cases),
        "case_outcomes": case_outcomes,
        "duplicates": events.get("duplicates", []),
        "collection_errors": events.get("collection_errors", []),
    }


def _pytest_command(
    *, expected_ids: list[str], selectors: dict[str, dict[str, Any]], scratch_run: Path,
    repo_root: Path, dependency_target: Path, dependency_wheelhouse: Path,
) -> tuple[list[str], dict[str, str]]:
    if not expected_ids:
        raise QARunError("pytest cannot be invoked with an empty registered selector set")
    selection_path = scratch_run / "selection.json"
    events_path = scratch_run / "events.json"
    expected_selectors = {t: selectors[t]["selector"] for t in expected_ids}
    known_selectors = {t: row["selector"] for t, row in selectors.items()}
    source_paths = sorted({s.split("::", 1)[0] for s in expected_selectors.values()})
    with selection_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(
            {"schema_version": 2, "expected_selectors": expected_selectors, "known_selectors": known_selectors},
            handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        handle.write("\n")
    argv = [
        sys.executable, "-m", "pytest", "-q", "--no-header", "--no-summary", "--tb=short",
        "--disable-warnings", "--show-capture=no", "--color=no",
        "-p", "tools.qa.pytest_plugin",
        f"--qa-selection-file={os.fspath(selection_path)}",
        f"--qa-events-file={os.fspath(events_path)}",
        f"--qa-repo-root={os.fspath(repo_root)}",
        *source_paths,
    ]
    env = build_environment()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = os.fspath(scratch_run / "pycache")
    env["PYTHONPATH"] = os.fspath(dependency_target)
    env["VST_QA_DEPENDENCY_WHEELHOUSE"] = os.fspath(dependency_wheelhouse)
    for name in ("TEMP", "TMP", "TMPDIR"):
        env[name] = os.fspath(scratch_run)
    return argv, env


def _normalized_command(argv: list[str], scratch_run: Path) -> list[str]:
    scratch = os.fspath(scratch_run)
    result: list[str] = []
    for argument in argv:
        if argument == sys.executable:
            result.append("<approved-python-base>/python.exe")
        elif argument.startswith("--qa-repo-root="):
            result.append("--qa-repo-root=<candidate-root>")
        elif scratch in argument or scratch.replace("\\", "/") in argument:
            result.append(argument.replace(scratch, "<scratch>").replace(scratch.replace("\\", "/"), "<scratch>"))
        else:
            result.append(argument)
    return result


def _is_link(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _check_external_dir(supplied: str, resolved: Path, root: Path, what: str) -> None:
    if _is_link(Path(supplied)) or not resolved.is_dir() or resolved.is_relative_to(root):
        raise QARunError(f"{what} must be an existing real directory outside the candidate repository")


def _blocked_record(
    report: dict[str, Any], output_paths: dict[str, Path], result: str, reasons: list[str], root: Path,
    before_paths: list[str],
) -> None:
    report["result"] = result
    report["reasons"] = reasons
    report["dirty_tree"]["after_paths"] = _unexpected_candidate_paths(before_paths)
    report["dirty_tree"]["after"] = bool(report["dirty_tree"]["after_paths"])
    _append_run_outputs(report, output_paths["stdout"], b"", output_paths["stderr"], "\n".join(reasons).encode())
    _append_report(output_paths["report"], report)


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    args._runtime_profile = _runtime_profile()
    root: Path | None = None
    scratch_root: Path | None = None
    output_paths: dict[str, Path] | None = None
    report: dict[str, Any] | None = None
    before_paths: list[str] = []
    head: str | None = None
    report_saved = False
    if not _RUN_ID.fullmatch(args.run_id):
        print("QA_RESULT BLOCKED: run-id is invalid")
        return 2
    try:
        root, scratch_root, output_paths = _repo_paths(args)
        head = git_head(root)
        if args.expected_head is not None and args.expected_head != head:
            raise QARunError("candidate HEAD does not match --expected-head")
        before_paths = _git_status_paths(root)
        # Fail closed: tests/, docs/qa/ and tools/qa/ must be clean and the registry exact.
        # Artifact completeness is intentionally not checked (a partial set is this runner's normal state).
        registry = validate_registry(root, args.manifest, check_artifacts=False)
        report = _report_base(
            args=args, root=root, registry=registry, head=head, before_paths=before_paths,
            output_paths=output_paths,
        )
        dependency_target = Path(args.dependency_target).resolve(strict=False)
        wheelhouse = Path(args.dependency_wheelhouse).resolve(strict=False)
        _check_external_dir(args.dependency_target, dependency_target, root, "dependency-target")
        _check_external_dir(args.dependency_wheelhouse, wheelhouse, root, "dependency-wheelhouse")
        if (
            wheelhouse == dependency_target
            or wheelhouse.is_relative_to(dependency_target)
            or dependency_target.is_relative_to(wheelhouse)
        ):
            raise QARunError("dependency-wheelhouse and dependency-target must be disjoint")
        report["branch"] = os.fsdecode(
            subprocess.run(
                ["git", "-c", "safe.directory=", "-c", f"safe.directory={os.fspath(root)}",
                 "branch", "--show-current"],
                cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=10, check=True, shell=False,
            ).stdout
        ).strip()
        lock_path = root / "tools" / "qa" / "requirements.lock"
        try:
            evidence = verify_dependency_environment(lock_path, dependency_target, wheelhouse)
        except DependencyProvenanceError as exc:
            raise QARunError(f"locked QA dependency content verification failed: {exc}") from None
        report["lock_sha256"] = evidence["lock_sha256"]
        report["dependency_wheels"] = evidence["wheels"]
        report["dependency_target_sha256"] = evidence["target_sha256"]
        report["dependency_content_verified_before"] = True
        report["dependency_versions"] = evidence["versions"]
        report["pytest_version"] = evidence["versions"].get("pytest")

        entry = registry.data["categories"][args.category]
        status, category_reason = entry["status"], entry["reason"]
        if status in {"NOT_RUN", "UNSUPPORTED"}:
            report["dependency_target_sha256_after"] = evidence["target_sha256"]
            report["dependency_content_verified_after"] = True
            _blocked_record(
                report, output_paths, status,
                [category_reason or f"category is committed as {status} without a reason"], root, before_paths,
            )
            report_saved = True
            print(f"QA_RESULT {status}")
            return 2

        reasons: list[str] = []
        if args._runtime_profile is None:
            reasons.append("runner process is not CPython 3.14.3 at C:\\Python314\\python.exe on Windows")
        if report["pytest_version"] is None:
            reasons.append("locked QA dependencies do not include pytest")
        if _unexpected_candidate_paths(before_paths):
            reasons.append("candidate worktree has unrelated changes before execution")
        expected_ids = report["expected_test_ids"]
        if not reasons and not expected_ids:
            report["dependency_target_sha256_after"] = evidence["target_sha256"]
            report["dependency_content_verified_after"] = True
            _blocked_record(
                report, output_paths, "NOT_RUN",
                ["no runnable selector of this category is assigned to the Windows profile"], root, before_paths,
            )
            report_saved = True
            print("QA_RESULT NOT_RUN")
            return 2
        if reasons:
            _blocked_record(report, output_paths, "BLOCKED", reasons, root, before_paths)
            report_saved = True
            print("QA_RESULT BLOCKED")
            return 2

        selectors = registry.selectors_by_id
        scratch_run = _run_id_dir(scratch_root, args.run_id)
        argv_child, child_env = _pytest_command(
            expected_ids=expected_ids, selectors=selectors, scratch_run=scratch_run, repo_root=root,
            dependency_target=dependency_target, dependency_wheelhouse=wheelhouse,
        )
        report["command"] = _normalized_command(argv_child, scratch_run)
        try:
            preflight = verify_dependency_environment(lock_path, dependency_target, wheelhouse)
        except DependencyProvenanceError as exc:
            raise QARunError(f"locked QA dependency changed while preparing pytest ({type(exc).__name__})") from None
        if preflight != evidence:
            raise QARunError("QA dependency provenance changed while preparing pytest")

        started = time.monotonic()
        exit_code, stdout_raw, stderr_raw, capture = _run_bounded(
            argv_child, cwd=root, timeout=args.timeout_seconds, cap=args.output_cap_bytes, env=child_env,
        )
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        _append_run_outputs(
            report,
            output_paths["stdout"], _redact(stdout_raw, repo_root=root, scratch_root=scratch_root),
            output_paths["stderr"], _redact(stderr_raw, repo_root=root, scratch_root=scratch_root),
        )
        report["exit_code"] = exit_code
        report["capture"] = capture
        if capture.get("capture_incomplete"):
            reasons.append("pytest process output capture was incomplete")
        if capture.get("timed_out"):
            reasons.append(f"pytest exceeded the {args.timeout_seconds}s wall-clock bound; process tree killed")
        if capture.get("stdout_truncated") or capture.get("stderr_truncated"):
            reasons.append("pytest output exceeded the configured cap")

        try:
            after = verify_dependency_environment(lock_path, dependency_target, wheelhouse)
        except DependencyProvenanceError:
            reasons.append("QA dependency target or wheelhouse changed during test execution")
        else:
            report["dependency_target_sha256_after"] = after["target_sha256"]
            report["dependency_content_verified_after"] = True
            if after != evidence:
                reasons.append("QA dependency provenance changed during test execution")

        events_path = scratch_run / "events.json"
        events: dict[str, Any] | None = None
        if events_path.is_file() and not events_path.is_symlink():
            try:
                events = json.loads(events_path.read_text(encoding="utf-8"))
                if set(events) != {"schema_version", "collected", "duplicates", "collection_errors"} or events[
                    "schema_version"
                ] != 1:
                    raise ValueError("event schema mismatch")
            except (OSError, UnicodeError, ValueError, TypeError):
                reasons.append("pytest event artifact is missing or invalid")
                events = None
        else:
            reasons.append("pytest did not emit its event artifact")
        if events is not None:
            try:
                accounted = _resolve_cases(events, expected_ids, selectors)
            except (QARunError, AttributeError, TypeError) as exc:
                reasons.append(f"pytest event accounting failed: {type(exc).__name__}")
                accounted = None
            if accounted is not None:
                for key in (
                    "collected_node_ids", "executed_node_ids", "passed_test_ids", "failed_test_ids",
                    "skipped_test_ids", "xfail_test_ids", "unexpected_node_ids", "uncollected_test_ids",
                    "case_outcomes",
                ):
                    report[key] = accounted[key]
                if accounted["duplicates"]:
                    reasons.append("pytest emitted duplicate node IDs")
                if accounted["collection_errors"]:
                    reasons.append("pytest collection produced errors")
                if accounted["unexpected_node_ids"]:
                    reasons.append("pytest collected unmapped node IDs")
                if accounted["uncollected_test_ids"]:
                    reasons.append("one or more registered selectors collected no cases (not passed)")
                if accounted["failed_test_ids"]:
                    reasons.append("one or more concrete test cases failed or unexpectedly passed xfail")
                if accounted["skipped_test_ids"]:
                    reasons.append("one or more required selectors contain skipped cases (not passed)")
                if accounted["xfail_test_ids"]:
                    reasons.append("one or more required selectors contain expected-failure cases")
                if not report["executed_node_ids"]:
                    reasons.append("pytest executed no registered cases")
                if set(report["passed_test_ids"]) != set(expected_ids):
                    reasons.append("not every expected selector passed")
        if exit_code != 0:
            reasons.append(f"pytest exited with non-zero status {exit_code}")

        final_paths = _git_status_paths(root)
        unexpected = _unexpected_candidate_paths(final_paths)
        if unexpected:
            reasons.append("pytest changed candidate paths beyond the declared evidence artifacts")
        report["dirty_tree"]["after_paths"] = unexpected
        report["dirty_tree"]["after"] = bool(unexpected)

        # Policy NOT_RUN selectors (and unassigned WSL-only ones) can never produce a plain PASS
        # for the category: the Windows-only success is INCONCLUSIVE at category level.
        policy_reason = "category has selectors that are NOT_RUN by policy or not assigned to the Windows profile"
        incomplete = bool(report["not_run_test_reasons"] or report["unassigned_test_ids"])
        if incomplete and not reasons:
            report["result"] = "INCONCLUSIVE"
            reasons.append(policy_reason)
        else:
            report["result"] = "PASS" if not reasons else "FAIL"
        report["reasons"] = reasons

        _append_report(output_paths["report"], report)
        report_saved = True
        for test_id in report["passed_test_ids"]:
            print(f"PASS {test_id}")
        print(f"QA_RESULT {report['result']} (windows profile only; WSL profiles NOT_RUN)")
        return 0 if report["result"] == "PASS" else 1
    except (
        QARunError, RegistryError, DependencyProvenanceError, OSError, subprocess.SubprocessError,
        TypeError, KeyError,
    ) as exc:
        if root is not None and output_paths is not None and not report_saved:
            try:
                if report is None:
                    report = _report_base(
                        args=args, root=root, registry=None, head=head, before_paths=before_paths,
                        output_paths=output_paths,
                    )
                detail = _redact(
                    f"{type(exc).__name__}: {exc}".encode("utf-8", errors="replace"),
                    repo_root=root, scratch_root=scratch_root or root,
                ).decode("utf-8", errors="replace")
                _blocked_record(report, output_paths, "BLOCKED", [detail], root, before_paths)
            except (OSError, KeyError, TypeError):
                pass
        print(f"QA_RESULT BLOCKED: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the native CLI lane
    raise SystemExit(main())
