"""Bounded native pytest runner for the S4 category manifest."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
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

from .fixtures import FixtureCatalogError, load_fixture_catalog
from .registry import (
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
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_SAFE_RELATIVE = re.compile(r"[A-Za-z0-9_./-]+\Z")
_LOCK_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[A-Za-z0-9_.+-]+)(?:;\s*sys_platform\s*==\s*\"(?P<platform>[A-Za-z0-9_]+)\")?\s+\\$"
)
_HASH_LINE = re.compile(r"^\s+--hash=sha256:([0-9a-f]{64})\s*$")
_SENSITIVE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|authorization)"
    r"\s*[:=]\s*[^\s,;]{4,}"
)
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_USER_PATH = re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\s\"']+(?:\\[^\\\s\"']+)*")


class QARunError(ValueError):
    """Raised for invalid CLI contracts before test code can start."""


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", required=True)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--manifest", default="docs/qa/categories.json")
    parser.add_argument("--fixtures", default="docs/qa/fixtures.json")
    parser.add_argument("--scratch-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output-cap-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--stderr-path", required=True)
    return parser.parse_args()


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


def _safe_target(root: Path, relative: str, *, create_parent: bool = False) -> Path:
    rel = _canonical_relative(relative, "artifact path")
    path = root.joinpath(*rel.split("/"))
    current = root
    for part in rel.split("/")[:-1]:
        current = current / part
        if current.exists() and (current.is_symlink() or getattr(current, "isjunction", lambda: False)()):
            raise QARunError("artifact path crosses a link")
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise QARunError("artifact path escapes its root")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise QARunError("artifact target is not a regular file")
    if path.exists() and path.stat().st_nlink != 1:
        raise QARunError("artifact target has unexpected hard links")
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _repo_paths(args: argparse.Namespace) -> tuple[Path, Path, dict[str, Path]]:
    repo_root = git_root(args.repo_root)
    if repo_root != Path(args.repo_root).resolve(strict=True):
        raise QARunError("repo-root must be the candidate repository root")
    scratch = Path(args.scratch_root).resolve(strict=False)
    if scratch.is_relative_to(repo_root):
        raise QARunError("scratch-root must be outside the candidate repository")
    if not _RUN_ID.fullmatch(args.run_id):
        raise QARunError("run-id is invalid")
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise QARunError("timeout-seconds is outside the supported bound")
    if not 1 <= args.output_cap_bytes <= MAX_CAPTURE_BYTES:
        raise QARunError("output-cap-bytes is outside the supported bound")
    if args.category not in {"functional", "integration", "api", "e2e", "regression", "seeded-failure"}:
        raise QARunError("category is not a registered QA category")
    base = f"docs/sdlc/evidence/qa/{args.category}"
    expected_paths = {
        "report": f"{base}.report.jsonl",
        "stdout": f"{base}.stdout.txt",
        "stderr": f"{base}.stderr.txt",
    }
    supplied_paths = {"report": args.report_path, "stdout": args.stdout_path, "stderr": args.stderr_path}
    if supplied_paths != expected_paths:
        raise QARunError("artifact paths must match the fixed append-only category paths")
    output_paths = {
        "report": _safe_target(repo_root, args.report_path, create_parent=True),
        "stdout": _safe_target(repo_root, args.stdout_path, create_parent=True),
        "stderr": _safe_target(repo_root, args.stderr_path, create_parent=True),
    }
    if len(set(output_paths.values())) != len(output_paths):
        raise QARunError("report/stdout/stderr artifact paths must be unique")
    if output_paths["report"].suffixes[-2:] != [".report", ".jsonl"]:
        raise QARunError("report artifact must use the JSON Lines suffix")
    return repo_root, scratch, output_paths


def _git_status_paths(root: Path) -> list[str]:
    command = [
        "git", "-c", "safe.directory=", "-c", f"safe.directory={os.fspath(root)}",
        "status", "--porcelain=v1", "-z", "--untracked-files=all",
    ]
    result = subprocess.run(
        command,
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
        shell=False,
    )
    if result.returncode != 0:
        raise QARunError("could not determine candidate worktree state")
    tokens = result.stdout.decode("utf-8", errors="replace").split("\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token:
            index += 1
            continue
        path = token[3:] if len(token) >= 4 else ""
        paths.append(path.replace("\\", "/"))
        if token[:2].strip() and ("R" in token[:2] or "C" in token[:2]):
            index += 1
            if index < len(tokens) and tokens[index]:
                paths.append(tokens[index].replace("\\", "/"))
        index += 1
    return sorted(set(paths))


def _known_artifact_paths() -> set[str]:
    return {
        f"docs/sdlc/evidence/qa/{category}.{kind}"
        for category in ("functional", "integration", "api", "e2e", "regression", "seeded-failure")
        for kind in ("report.jsonl", "stdout.txt", "stderr.txt")
    }


def _unexpected_candidate_paths(paths: list[str]) -> list[str]:
    return sorted(set(paths) - _known_artifact_paths())


def _append_raw_artifact(path: Path, data: bytes) -> dict[str, Any]:
    payload = data if not data or data.endswith(b"\n") else data + b"\n"
    start = path.stat().st_size if path.exists() else 0
    with path.open("ab") as handle:
        handle.write(payload)
    end = path.stat().st_size
    return {
        "start": start,
        "end": end,
        "size": end - start,
        "sha256": sha256_bytes(payload),
    }


def _append_run_outputs(
    report: dict[str, Any],
    stdout_path: Path,
    stdout: bytes,
    stderr_path: Path,
    stderr: bytes,
) -> None:
    stdout_record = _append_raw_artifact(stdout_path, stdout)
    stderr_record = _append_raw_artifact(stderr_path, stderr)
    report["artifact_digests"] = {
        "stdout": stdout_record["sha256"],
        "stderr": stderr_record["sha256"],
    }
    report["artifact_ranges"] = {
        "stdout": {"start": stdout_record["start"], "end": stdout_record["end"]},
        "stderr": {"start": stderr_record["start"], "end": stderr_record["end"]},
    }
    report["artifact_sizes"] = {
        "stdout": stdout_record["size"],
        "stderr": stderr_record["size"],
    }


def _canonical_interpreter_matches() -> bool:
    actual = ntpath.normcase(ntpath.normpath(os.path.realpath(sys.executable)))
    expected = ntpath.normcase(ntpath.normpath(EXPECTED_PYTHON_EXE))
    return actual == expected


def _lock_versions(root: Path) -> tuple[str, dict[str, str]]:
    lock_path = root / "tools" / "qa" / "requirements.lock"
    try:
        raw = lock_path.read_bytes()
        lines = raw.decode("utf-8").splitlines()
    except OSError as exc:
        raise QARunError(f"QA dependency lock is missing ({type(exc).__name__})") from None
    if not lines or not lines[0].startswith("# Wheel-only, exact hashes"):
        raise QARunError("QA dependency lock header is invalid")
    versions: dict[str, str] = {}
    pending: tuple[str, str, str | None] | None = None
    saw_hash = False
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            continue
        if pending is None:
            match = _LOCK_LINE.fullmatch(line)
            if match is None:
                raise QARunError("QA dependency lock syntax is invalid")
            pending = (match.group("name").lower().replace("_", "-"), match.group("version"), match.group("platform"))
            saw_hash = False
        else:
            hash_match = _HASH_LINE.fullmatch(line)
            if hash_match is None:
                raise QARunError("every locked wheel must have a SHA-256 pin")
            saw_hash = True
            name, version, platform_name = pending
            if platform_name is None or (platform_name == "win32" and os.name == "nt"):
                if name in versions:
                    raise QARunError(f"duplicate locked package: {name}")
                versions[name] = version
            pending = None
    if pending is not None or not saw_hash:
        raise QARunError("QA dependency lock ends without a wheel hash")
    if "pytest" not in versions:
        raise QARunError("pytest is absent from the QA lock")
    return hashlib.sha256(raw).hexdigest(), versions


def _installed_versions(expected: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    actual: dict[str, str] = {}
    missing: list[str] = []
    for package, required in sorted(expected.items()):
        try:
            installed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(package)
            continue
        actual[package] = installed
        if installed != required:
            missing.append(f"{package} (expected {required}, found {installed})")
    return actual, missing


def _run_bounded(
    argv: list[str], *, cwd: Path, timeout: int, cap: int, env: dict[str, str]
) -> tuple[int, bytes, bytes, dict[str, Any]]:
    """Run pytest with bounded pipes and the VST runner's process-tree containment primitives."""
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
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            bufsize=0,
            **_spawn_kwargs(suspended=os.name == "nt"),
        )
        if os.name == "nt":
            job = _JobObject.attach(process)
            info["job_object"] = job is not None
            if job is None:
                info["capture_incomplete"] = True
                _kill_tree(process)
                process.wait(timeout=10)
                completed = True
                return EXIT_CAPTURE_INCOMPLETE, b"", b"", info
            if not _resume_suspended_primary_thread(process.pid):
                job.terminate_and_close()
                job = None
                _kill_tree(process)
                process.wait(timeout=10)
                completed = True
                info["capture_incomplete"] = True
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
    except (OSError, subprocess.TimeoutExpired) as exc:
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
            for capture, stream in (
                (stdout_capture, process.stdout),
                (stderr_capture, process.stderr),
            ):
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
        info["capture_incomplete"]
        or stdout_capture.incomplete
        or stderr_capture.incomplete
        or kill_failed
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
    text = _BEARER.sub(lambda match: f"{match.group(1)} <redacted>", text)
    text = _SENSITIVE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    return text.encode("utf-8")


def _run_id_dir(scratch_root: Path, run_id: str) -> Path:
    path = scratch_root / run_id
    if path.exists() or path.is_symlink():
        raise QARunError("scratch run directory already exists; refusing to overwrite it")
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve(strict=True)


def _report_base(
    *,
    args: argparse.Namespace,
    root: Path,
    registry: ValidatedRegistry | None,
    candidate_head: str | None,
    before_paths: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "sprint": "S4",
        "run_id": args.run_id,
        "category": args.category,
        "candidate_head": candidate_head,
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
        "expected_test_ids": registry.category_test_ids.get(args.category, []) if registry else [],
        "inventory_test_ids": registry.category_inventory_ids.get(args.category, []) if registry else [],
        "not_run_test_reasons": registry.category_not_run.get(args.category, {}) if registry else {},
        "collected_node_ids": [],
        "executed_node_ids": [],
        "passed_test_ids": [],
        "failed_test_ids": [],
        "skipped_test_ids": [],
        "xfail_test_ids": [],
        "unexpected_node_ids": [],
        "uncollected_test_ids": [],
        "case_outcomes": [],
        "fixture_results": [],
        "command": [],
        "exit_code": None,
        "duration_seconds": None,
        "interpreter": {
            "id": f"{platform.python_implementation()}-{sys.version_info.major}.{sys.version_info.minor}",
            "executable": "C:/Python314/python.exe",
            "base": "C:/Python314",
            "version": platform.python_version(),
        },
        "environment": {
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
        },
        "pytest_version": None,
        "dependency_versions": {},
        "artifact_paths": {
            key: path.relative_to(root).as_posix() for key, path in (getattr(args, "_output_paths", {}) or {}).items()
        },
        "artifact_digests": {},
        "artifact_ranges": {},
        "capture": {},
        "result": "BLOCKED",
        "reasons": [],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "normalized_sha256": None,
    }


def _fixture_results(
    catalog: dict[str, Any],
    registry: ValidatedRegistry,
    events: dict[str, Any],
) -> tuple[list[dict[str, str]], list[str]]:
    observed = events.get("fixture_observations", [])
    if not isinstance(observed, list):
        return [], ["fixture observations are not a list"]
    observed_by_id: dict[str, list[dict[str, str]]] = {}
    for row in observed:
        if (
            not isinstance(row, dict)
            or set(row) != {"fixture_id", "test_node_id", "observed_rejection"}
            or not isinstance(row["fixture_id"], str)
            or not isinstance(row["test_node_id"], str)
            or row["observed_rejection"] not in {"FAIL", "BLOCKED", "NOT_RUN", "INCONCLUSIVE"}
        ):
            return [], ["fixture observation has invalid fields or result"]
        observed_by_id.setdefault(row["fixture_id"], []).append(row)
    results: list[dict[str, str]] = []
    errors: list[str] = []
    for fixture in catalog["fixtures"]:
        matches = observed_by_id.get(fixture["fixture_id"], [])
        if len(matches) != 1:
            errors.append(f"fixture {fixture['fixture_id']} observation count is {len(matches)}")
            continue
        node_id = matches[0]["test_node_id"]
        test_event = next((row for row in events["collected"] if row["node_id"] == node_id), None)
        if test_event is None or test_event["selector"] != fixture["test_id"]:
            errors.append(f"fixture {fixture['fixture_id']} observation came from the wrong test")
            continue
        observed_rejection = matches[0]["observed_rejection"]
        passed = observed_rejection == fixture["expected_rejection"] and test_event["outcome"] == "passed"
        results.append(
            {
                "fixture_id": fixture["fixture_id"],
                "input_sha256": fixture["input_sha256"],
                "test_id": fixture["test_id"],
                "test_node_id": node_id,
                "expected_rejection": fixture["expected_rejection"],
                "observed_rejection": observed_rejection,
                "result": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            errors.append(f"fixture {fixture['fixture_id']} did not observe its expected rejection")
    if set(observed_by_id) != {row["fixture_id"] for row in catalog["fixtures"]}:
        errors.append("fixture observations do not exactly match the committed catalog")
    return results, errors


def _resolve_cases(
    events: dict[str, Any], expected_ids: list[str], selectors: dict[str, dict[str, str]]
) -> dict[str, Any]:
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
        node_id = row.get("node_id")
        selector = row.get("selector")
        outcome = row.get("outcome")
        if not isinstance(node_id, str) or outcome not in {
            "passed", "failed", "skipped", "xfailed", "xpassed", "not_run"
        }:
            raise QARunError("pytest event contains invalid case fields")
        if selector not in selectors or selector not in selector_cases:
            unexpected.append(node_id)
            selector_id = None
        else:
            selector_id = selector
            selector_cases[selector].append({"node_id": node_id, "outcome": outcome})
        case_outcomes.append(
            {"node_id": node_id, "selector_id": selector_id or "", "outcome": outcome}
        )
    case_outcomes.sort(key=lambda row: row["node_id"])
    missing = sorted(test_id for test_id, cases in selector_cases.items() if not cases)
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    xfailed: list[str] = []
    executed_node_ids: list[str] = []
    for test_id, cases in sorted(selector_cases.items()):
        outcomes = {case["outcome"] for case in cases}
        executed_node_ids.extend(
            case["node_id"] for case in cases if case["outcome"] != "not_run"
        )
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
        "executed_node_ids": sorted(executed_node_ids),
        "passed_test_ids": passed,
        "failed_test_ids": failed,
        "skipped_test_ids": skipped,
        "xfail_test_ids": xfailed,
        "unexpected_node_ids": sorted(unexpected),
        "uncollected_test_ids": missing,
        "case_outcomes": case_outcomes,
        "duplicates": events.get("duplicates", []),
        "collection_errors": events.get("collection_errors", []),
        "selector_cases": selector_cases,
    }


def _pytest_command(
    *,
    expected_ids: list[str],
    selectors: dict[str, dict[str, str]],
    scratch_run: Path,
    repo_root: Path,
) -> tuple[list[str], dict[str, str]]:
    if not expected_ids:
        raise QARunError("pytest cannot be invoked with an empty registered selector set")
    selection_path = scratch_run / "selection.json"
    events_path = scratch_run / "events.json"
    selection = {
        "schema_version": 1,
        "selectors": {test_id: selectors[test_id]["selector"] for test_id in expected_ids},
    }
    with selection_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(selection, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--no-header",
        "--no-summary",
        "--tb=no",
        "--disable-warnings",
        "--show-capture=no",
        "--color=no",
        "-p",
        "tools.qa.pytest_plugin",
        f"--qa-selection-file={os.fspath(selection_path)}",
        f"--qa-events-file={os.fspath(events_path)}",
        f"--qa-repo-root={os.fspath(repo_root)}",
        *[selectors[test_id]["selector"] for test_id in expected_ids],
    ]
    env = build_environment()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["PYTHONUTF8"] = "1"
    temp_root = os.fspath(scratch_run)
    env["TEMP"] = temp_root
    env["TMP"] = temp_root
    env["TMPDIR"] = temp_root
    return argv, env


def _normalized_command(argv: list[str], scratch_run: Path) -> list[str]:
    result: list[str] = []
    for argument in argv:
        if argument == sys.executable:
            result.append("<approved-python-base>/python.exe")
        elif os.fspath(scratch_run) in argument:
            result.append(argument.replace(os.fspath(scratch_run), "<scratch>").replace(os.fspath(scratch_run).replace("\\", "/"), "<scratch>"))
        elif argument.startswith("--qa-repo-root="):
            result.append("--qa-repo-root=<candidate-root>")
        else:
            result.append(argument)
    return result


def _base_status(category_status: str | None, category: str, reason: str | None) -> tuple[str, list[str]]:
    if category not in {"functional", "integration", "api", "e2e", "regression", "seeded-failure"}:
        return "BLOCKED", [f"unknown category: {category}"]
    if category_status == "NOT_RUN":
        return "NOT_RUN", [reason or "category is committed as NOT_RUN without a reason"]
    if category_status == "UNSUPPORTED":
        return "UNSUPPORTED", [reason or "category is committed as unsupported without a reason"]
    return "PASS", []


def _append_report(path: Path, report: dict[str, Any]) -> None:
    data = encode_report(report)
    with path.open("ab") as handle:
        handle.write(data)


def main() -> int:
    args = _args()
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
        args._output_paths = output_paths
        head = git_head(root)
        if args.expected_head is not None and args.expected_head != head:
            raise QARunError("candidate HEAD does not match --expected-head")
        before_paths = _git_status_paths(root)
        registry = validate_registry(root, args.manifest)
        report = _report_base(
            args=args,
            root=root,
            registry=registry,
            candidate_head=head,
            before_paths=before_paths,
        )
        try:
            catalog, catalog_hash = load_fixture_catalog(root, registry, args.fixtures)
        except FixtureCatalogError as exc:
            raise QARunError(str(exc)) from None
        report["fixture_catalog_sha256"] = catalog_hash
        report["branch"] = os.fsdecode(
            subprocess.run(
                ["git", "-c", "safe.directory=", "-c", f"safe.directory={os.fspath(root)}", "branch", "--show-current"],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=True,
                shell=False,
            ).stdout
        ).strip()
        lock_hash, locked_versions = _lock_versions(root)
        report["lock_sha256"] = lock_hash
        actual_versions, missing_versions = _installed_versions(locked_versions)
        report["dependency_versions"] = actual_versions
        try:
            report["pytest_version"] = importlib.metadata.version("pytest")
        except importlib.metadata.PackageNotFoundError:
            report["pytest_version"] = None
            missing_versions.append("pytest")
        reasons: list[str] = []
        if sys.implementation.name != "CPython" or sys.version_info[:2] != (3, 14):
            reasons.append("runner requires the pinned CPython 3.14 interpreter")
        if not _canonical_interpreter_matches():
            reasons.append("runner executable is not the approved C:/Python314/python.exe")
        if missing_versions:
            reasons.append("locked QA dependencies are missing or mismatched: " + ", ".join(sorted(missing_versions)))
        if _unexpected_candidate_paths(before_paths):
            reasons.append("candidate worktree has unrelated changes before execution")
        if args.category not in registry.category_test_ids:
            reasons.append(f"unknown category: {args.category}")
        policy_not_run = registry.category_not_run.get(args.category, {})
        if policy_not_run:
            reasons.append("one or more inventory selectors are explicitly NOT_RUN by policy")

        category_status = registry.data["categories"].get(args.category, {}).get("status")
        category_reason = registry.data["categories"].get(args.category, {}).get("reason")
        base_result, base_reasons = _base_status(category_status, args.category, category_reason)
        if base_result != "PASS":
            report["result"] = base_result
            report["reasons"] = base_reasons
            report["exit_code"] = None
            report["dirty_tree"]["after_paths"] = _unexpected_candidate_paths(before_paths)
            report["dirty_tree"]["after"] = bool(report["dirty_tree"]["after_paths"])
            _append_run_outputs(
                report, output_paths["stdout"], b"", output_paths["stderr"],
                "\n".join(base_reasons).encode("utf-8"),
            )
            _append_report(output_paths["report"], report)
            report_saved = True
            print(f"QA_RESULT {base_result}")
            return 2

        if reasons:
            report["result"] = "BLOCKED"
            report["reasons"] = reasons
            report["exit_code"] = None
            report["dirty_tree"]["after_paths"] = _unexpected_candidate_paths(before_paths)
            report["dirty_tree"]["after"] = bool(report["dirty_tree"]["after_paths"])
            _append_run_outputs(
                report, output_paths["stdout"], b"", output_paths["stderr"],
                "\n".join(reasons).encode("utf-8"),
            )
            _append_report(output_paths["report"], report)
            report_saved = True
            print("QA_RESULT BLOCKED")
            return 2

        expected_ids = registry.category_test_ids[args.category]
        selectors = registry.selectors_by_id
        scratch_run = _run_id_dir(scratch_root, args.run_id)
        argv, child_env = _pytest_command(
            expected_ids=expected_ids,
            selectors=selectors,
            scratch_run=scratch_run,
            repo_root=root,
        )
        # Command evidence uses normalized temporary-root tokens to avoid writing
        # absolute host paths into a public repository report.
        report["command"] = _normalized_command(argv, scratch_run)
        started = time.monotonic()
        exit_code, stdout_raw, stderr_raw, capture = _run_bounded(
            argv,
            cwd=root,
            timeout=args.timeout_seconds,
            cap=args.output_cap_bytes,
            env=child_env,
        )
        duration = round(time.monotonic() - started, 3)
        stdout = _redact(stdout_raw, repo_root=root, scratch_root=scratch_root)
        stderr = _redact(stderr_raw, repo_root=root, scratch_root=scratch_root)
        _append_run_outputs(report, output_paths["stdout"], stdout, output_paths["stderr"], stderr)
        report["exit_code"] = exit_code
        report["duration_seconds"] = duration
        report["capture"] = capture
        if capture.get("capture_incomplete"):
            reasons.append("pytest process output capture was incomplete")
        if capture.get("timed_out"):
            reasons.append("pytest exceeded the bounded runtime")
        if capture.get("stdout_truncated") or capture.get("stderr_truncated"):
            reasons.append("pytest output exceeded the configured cap")

        events_path = scratch_run / "events.json"
        events: dict[str, Any] | None = None
        if events_path.is_file() and not events_path.is_symlink():
            try:
                events = json.loads(events_path.read_text(encoding="utf-8"))
                if set(events) != {"schema_version", "collected", "duplicates", "collection_errors", "fixture_observations"} or events["schema_version"] != 1:
                    raise ValueError("event schema mismatch")
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
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
                    "collected_node_ids", "executed_node_ids", "passed_test_ids",
                    "failed_test_ids", "skipped_test_ids", "xfail_test_ids",
                    "unexpected_node_ids", "uncollected_test_ids", "case_outcomes",
                ):
                    report[key] = accounted[key]
                if accounted["duplicates"]:
                    reasons.append("pytest emitted duplicate node IDs")
                if accounted["collection_errors"]:
                    reasons.append("pytest collection produced errors")
                if accounted["unexpected_node_ids"]:
                    reasons.append("pytest collected unmapped node IDs")
                if accounted["uncollected_test_ids"]:
                    reasons.append("one or more registered selectors collected no cases")
                if accounted["failed_test_ids"]:
                    reasons.append("one or more concrete test cases failed or unexpectedly passed xfail")
                if accounted["skipped_test_ids"]:
                    reasons.append("one or more required selectors contain skipped cases")
                if accounted["xfail_test_ids"]:
                    reasons.append("one or more required selectors contain expected-failure cases")
                if expected_ids and len(report["executed_node_ids"]) == 0:
                    reasons.append("pytest executed no registered cases")
                if args.category == "seeded-failure":
                    fixture_rows, fixture_errors = _fixture_results(catalog, registry, events)
                    report["fixture_results"] = fixture_rows
                    reasons.extend(fixture_errors)
                elif events.get("fixture_observations"):
                    reasons.append("non-seeded category emitted seeded-fixture observations")
        if exit_code != 0:
            reasons.append(f"pytest exited with non-zero status {exit_code}")

        paths_after_tests = _git_status_paths(root)
        allowed_changes = _known_artifact_paths()
        unexpected_changes = sorted(set(paths_after_tests) - allowed_changes)
        if unexpected_changes:
            reasons.append("pytest changed candidate paths beyond the declared evidence artifacts")
        report["dirty_tree"]["after_paths"] = unexpected_changes
        report["dirty_tree"]["after"] = bool(unexpected_changes)
        report["unexpected_candidate_changes"] = unexpected_changes
        report["collected_node_ids"] = sorted(report["collected_node_ids"])
        policy_reason = "one or more inventory selectors are explicitly NOT_RUN by policy"
        if (
            policy_not_run
            and not unexpected_changes
            and exit_code == 0
            and all(reason == policy_reason for reason in reasons)
        ):
            report["result"] = "INCONCLUSIVE"
        else:
            report["result"] = "PASS" if not reasons and exit_code == 0 else "FAIL"
        report["reasons"] = reasons
        _append_report(output_paths["report"], report)
        report_saved = True

        # Verify no concurrent or test-driven mutation occurred while writing the
        # fixed-path artifacts. Only those exact artifact paths may be dirty.
        final_paths = _git_status_paths(root)
        if set(final_paths) - allowed_changes:
            report["result"] = "BLOCKED"
            report["reasons"].append("candidate worktree changed concurrently during report finalization")
            unexpected_final = _unexpected_candidate_paths(final_paths)
            report["dirty_tree"]["after"] = bool(unexpected_final)
            report["dirty_tree"]["after_paths"] = unexpected_final
            _append_report(output_paths["report"], report)
            report_saved = True

        for test_id in report["passed_test_ids"]:
            print(f"PASS {test_id}")
        print(f"QA_RESULT {report['result']}")
        return 0 if report["result"] == "PASS" else 1
    except (
        QARunError,
        RegistryError,
        FixtureCatalogError,
        OSError,
        subprocess.SubprocessError,
        TypeError,
        KeyError,
    ) as exc:
        if root is not None and output_paths is not None and not report_saved:
            if report is None:
                report = _report_base(
                    args=args,
                    root=root,
                    registry=None,
                    candidate_head=head,
                    before_paths=before_paths,
                )
            detail = _redact(
                f"{type(exc).__name__}: {exc}".encode("utf-8", errors="replace"),
                repo_root=root,
                scratch_root=scratch_root or root,
            ).decode("utf-8", errors="replace")
            report["result"] = "BLOCKED"
            report["reasons"] = [detail]
            try:
                _append_run_outputs(
                    report,
                    output_paths["stdout"],
                    b"",
                    output_paths["stderr"],
                    detail.encode("utf-8"),
                )
                _append_report(output_paths["report"], report)
            except OSError:
                pass
        print(f"QA_RESULT BLOCKED: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised through the native CLI lane
    raise SystemExit(main())
