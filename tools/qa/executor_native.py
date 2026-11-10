"""U3-2 executor A: the VST native runner (tools.qa.run + tools.qa.gate_check) behind the common interface.

Call style (decision): a SUBPROCESS with a fixed argv and no shell, not an in-process run.main().
Reasons: run.main() binds the runtime profile to sys.executable (it must be CPython 3.14.3 at
C:\\Python314\\python.exe), parses argv with argparse (a bad argument raises SystemExit), prints to the
caller's stdout, holds a per-repository lock and kills only its own pytest tree. A child with the pinned
interpreter reproduces exactly how the runner is documented to be invoked (`python -m tools.qa.run`),
isolates SystemExit and the lock from the caller, and lets this module enforce an outer wall-clock bound.
The runner module is the candidate's own tools/qa (PYTHONPATH = repo root, -P so cwd is not on sys.path):
the runner already requires tools/qa/ to be clean at the candidate head.

The record is the LAST JSON line appended to docs/sdlc/evidence/qa/<category>.report.jsonl by this
run (selected with gate_check.select_record over the bytes appended since the call started), then
checked with gate_check.check_report against the registry the repo already validates. Nothing is
invented: a missing or ill-typed field, an unknown result string, or an exit code that disagrees
with the result is a typed refusal. This module does not run anything at import time.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tools.qa import gate_check
from tools.qa import run as qa_run
from tools.qa.executor import (
    EXECUTOR_NATIVE, PASS_THROUGH_ENV, RESULTS, ExecutorError, ExecutorReport, build_report,
    require_category, require_head, require_options, run_child,
)
from tools.qa.registry import RegistryError, git_head, git_root, validate_registry

_REQUIRED = ("dependency_target", "dependency_wheelhouse", "scratch_root", "run_id")
_OPTIONAL = ("timeout_seconds", "output_cap_bytes")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
CHILD_GRACE_SECONDS = 300          # dependency verification and evidence commit around the pytest bound
CHILD_STDOUT_CAP = 1024 * 1024     # the runner prints PASS lines and one QA_RESULT line
CHILD_STDERR_CAP = 256 * 1024


def _external_dir(value: Any, name: str) -> Path:
    try:
        path = Path(value)
    except TypeError:
        raise ExecutorError("OPTION_INVALID", f"{name} must be a path") from None
    if not path.is_absolute():
        raise ExecutorError("OPTION_INVALID", f"{name} must be an absolute path")
    return path


def _bounded_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ExecutorError("OPTION_INVALID", f"{name} must be an int in {low}..{high}")
    return value


def _str_list(record: dict[str, Any], key: str) -> tuple[str, ...]:
    value = record.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ExecutorError("NATIVE_RECORD_INVALID", f"{key} is missing or not a list of strings")
    return tuple(value)


def _fixed_paths(category: str) -> dict[str, str]:
    base = f"{qa_run.EVIDENCE_DIR}/{category}"
    return {"report": f"{base}.report.jsonl", "stdout": f"{base}.stdout.txt", "stderr": f"{base}.stderr.txt"}


def _size(path: Path) -> int:
    try:
        return path.lstat().st_size
    except FileNotFoundError:
        return 0


def _artifact_bytes(root: Path, paths: dict[str, str], record: dict[str, Any]) -> dict[str, bytes] | None:
    """Bytes of this run's stdout/stderr slices from the recorded ranges, or None if they cannot be read."""
    ranges = record.get("artifact_ranges")
    if not isinstance(ranges, dict):
        return None
    result: dict[str, bytes] = {}
    for key in ("stdout", "stderr"):
        span = ranges.get(key)
        if not isinstance(span, dict):
            return None
        start, end = span.get("start"), span.get("end")
        if any(isinstance(v, bool) or not isinstance(v, int) for v in (start, end)) or not 0 <= start <= end:
            return None
        try:
            with (root / Path(*paths[key].split("/"))).open("rb") as handle:
                handle.seek(start)
                data = handle.read(end - start)
        except OSError:
            return None
        if len(data) != end - start:
            return None
        result[key] = data
    return result


class NativeExecutor:
    """Executor A (`vst-native`): per-id accounting, native gate verdict carried through."""

    executor_id = EXECUTOR_NATIVE

    def run(self, category: str, *, repo_root: Any, expected_head: str, **options: Any) -> ExecutorReport:
        """Options: dependency_target, dependency_wheelhouse, scratch_root, run_id (required);
        timeout_seconds (1..3600, default 900), output_cap_bytes (1..4 MiB, default 1 MiB)."""
        category = require_category(category)
        expected_head = require_head(expected_head)
        require_options(options, required=_REQUIRED, optional=_OPTIONAL)
        target = _external_dir(options["dependency_target"], "dependency_target")
        wheelhouse = _external_dir(options["dependency_wheelhouse"], "dependency_wheelhouse")
        scratch = _external_dir(options["scratch_root"], "scratch_root")
        run_id = options["run_id"]
        if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
            raise ExecutorError("OPTION_INVALID", "run_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,63}")
        timeout = _bounded_int(
            options.get("timeout_seconds", qa_run.DEFAULT_TIMEOUT_SECONDS), "timeout_seconds",
            1, qa_run.MAX_TIMEOUT_SECONDS,
        )
        cap = _bounded_int(
            options.get("output_cap_bytes", 1024 * 1024), "output_cap_bytes", 1, qa_run.MAX_CAPTURE_BYTES
        )

        if os.name != "nt":
            raise ExecutorError("PLATFORM_UNSUPPORTED", "the native runner supports the Windows profile only")
        python = qa_run.EXPECTED_PYTHON_EXE
        if not os.path.isfile(python):
            raise ExecutorError("INTERPRETER_MISSING", "the pinned CPython 3.14.3 interpreter is absent")
        try:
            root = git_root(repo_root)
            if root != Path(repo_root).resolve(strict=True):
                raise ExecutorError("NOT_REPO_ROOT", "repo_root must be the repository root")
            head = git_head(root)
        except RegistryError as exc:
            raise ExecutorError("REPO_UNUSABLE", str(exc)[:200]) from None
        if head != expected_head:
            raise ExecutorError("STALE_HEAD", "repository HEAD differs from expected_head; nothing was run")

        paths = _fixed_paths(category)
        argv = [
            python, "-P", "-s", "-B", "-m", "tools.qa.run",
            "--category", category,
            "--repo-root", os.fspath(root),
            "--manifest", qa_run.MANIFEST_PATH,
            "--dependency-target", os.fspath(target),
            "--dependency-wheelhouse", os.fspath(wheelhouse),
            "--scratch-root", os.fspath(scratch),
            "--run-id", run_id,
            "--expected-head", expected_head,
            "--timeout-seconds", str(timeout),
            "--output-cap-bytes", str(cap),
            "--report-path", paths["report"],
            "--stdout-path", paths["stdout"],
            "--stderr-path", paths["stderr"],
        ]
        env = {key: os.environ[key] for key in PASS_THROUGH_ENV if key in os.environ}
        env.update({
            "PYTHONPATH": os.fspath(root),
            "PYTHONDONTWRITEBYTECODE": "1",   # no __pycache__ may appear in the candidate tree
            "PYTHONNOUSERSITE": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        report_path = root / Path(*paths["report"].split("/"))
        offset = _size(report_path)

        child = run_child(
            argv, cwd=os.fspath(root), env=env, timeout=timeout + CHILD_GRACE_SECONDS,
            stdout_cap=CHILD_STDOUT_CAP, stderr_cap=CHILD_STDERR_CAP,
        )
        if child.timed_out:
            raise ExecutorError("NATIVE_CHILD_TIMEOUT", "the runner exceeded its outer bound; tree killed")
        if child.stdout_truncated or child.stderr_truncated:
            raise ExecutorError("NATIVE_OUTPUT_TRUNCATED", "runner console output exceeded its cap")

        try:
            appended = report_path.read_bytes()[offset:]
        except OSError:
            appended = b""
        try:
            record = gate_check.select_record(appended.splitlines())
        except (ValueError, UnicodeDecodeError):
            excerpt = child.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
            raise ExecutorError(
                "NATIVE_NO_RECORD", f"no readable record appended by this run (rc={child.returncode}): {excerpt[0][:160]}"
            ) from None
        if record.get("run_id") != run_id or record.get("category") != category:
            raise ExecutorError("NATIVE_RECORD_MISMATCH", "appended record belongs to a different run or category")

        result = record.get("result")
        if result == "UNSUPPORTED":
            raise ExecutorError("UNSUPPORTED_CATEGORY", "the registry marks this category UNSUPPORTED")
        if result not in RESULTS:
            raise ExecutorError("RESULT_UNMAPPED", f"native result {str(result)[:40]!r} has no mapping")
        if (child.returncode == 0) != (result == "PASS"):
            raise ExecutorError(
                "NATIVE_EXIT_INCONSISTENT", f"runner exit {child.returncode} disagrees with result {result}"
            )

        exit_code = record.get("exit_code")
        if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
            raise ExecutorError("NATIVE_RECORD_INVALID", "exit_code is not an int")
        digests = record.get("artifact_digests")
        raw_reasons = record.get("not_run_test_reasons")
        texts = record.get("reasons", [])
        if not isinstance(digests, dict) or not isinstance(raw_reasons, dict) or not isinstance(texts, list):
            raise ExecutorError("NATIVE_RECORD_INVALID", "digest, not-run or reason fields have the wrong type")
        not_run = {
            str(key): value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
            for key, value in raw_reasons.items()
        }

        try:
            registry = validate_registry(root, qa_run.MANIFEST_PATH, check_artifacts=False)
        except RegistryError as exc:
            verdict, codes = "NON_APPROVING", ("REGISTRY_UNAVAILABLE",)
            texts = [*texts, f"registry could not be validated after the run: {str(exc)[:120]}"]
        else:
            check = gate_check.check_report(
                record, registry, expected_head=expected_head,
                artifact_bytes=_artifact_bytes(root, paths, record),
            )
            verdict, codes = check.verdict, tuple(sorted(check.codes()))

        try:
            return build_report(
                category=category, executor_id=EXECUTOR_NATIVE, expected_head=expected_head,
                candidate_head=record.get("candidate_head"), head_after=record.get("head_after"),
                result=result, exit_code=exit_code,
                ids={
                    "expected_ids": _str_list(record, "expected_test_ids"),
                    "collected_ids": _str_list(record, "collected_node_ids"),
                    "passed_ids": _str_list(record, "passed_test_ids"),
                    "skipped_ids": _str_list(record, "skipped_test_ids"),
                    "failed_ids": _str_list(record, "failed_test_ids"),
                    "uncollected_ids": _str_list(record, "uncollected_test_ids"),
                    "xfail_ids": _str_list(record, "xfail_test_ids"),
                },
                artifact_digests=digests, not_run_reasons=not_run,
                reasons=[t for t in texts if isinstance(t, str)],
                native_verdict=verdict, native_reason_codes=codes, raw_record=record,
            )
        except ExecutorError as exc:
            if exc.code == "REPORT_INVALID":
                raise ExecutorError("NATIVE_RECORD_INVALID", exc.detail) from None
            raise
