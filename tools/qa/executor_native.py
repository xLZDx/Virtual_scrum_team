"""U3-2 executor A: the VST native runner (tools.qa.run + tools.qa.gate_check) behind the common interface.

Call style (decision): a SUBPROCESS with a fixed argv and no shell, not an in-process run.main().
Reasons: run.main() binds the runtime profile to sys.executable (it must be CPython 3.14.3 at
C:\\Python314\\python.exe), parses argv with argparse (a bad argument raises SystemExit), prints to the
caller's stdout, holds a per-repository lock and kills only its own pytest tree. A child with the pinned
interpreter reproduces exactly how the runner is documented to be invoked (`python -m tools.qa.run`),
isolates SystemExit and the lock from the caller, and lets this module enforce an outer wall-clock bound.
The runner module is the candidate's own tools/qa (PYTHONPATH = repo root, -P so cwd is not on sys.path).

Trust: the runner and the registry come from the candidate, so an unpinned native record is
CANDIDATE-ATTESTED and judge() caps it at COARSE_ONLY. Only when the caller supplies BOTH
expected_registry_sha256 and expected_runner_tree_sha256 and both match (the runner tree digest is
computed here from the git blob list of tools/qa at the expected head) is the report not candidate-attested
and eligible for APPROVABLE.

The record is selected by run_id and category from the bytes this call appended to
docs/sdlc/evidence/qa/<category>.report.jsonl (read from a saved offset, capped), then checked with
gate_check.check_report. HEAD and the worktree are re-read by this module after the child exits; the
record's own head_after is never trusted. This module does nothing at import time.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from tools.qa import gate_check
from tools.qa import run as qa_run
from tools.qa.executor import (
    EXECUTOR_NATIVE, PASS_THROUGH_ENV, RESULTS, ExecutorError, ExecutorReport, assert_trusted_git,
    build_report, loads_strict, require_category, require_head, require_options, run_child,
)
from tools.qa.registry import RegistryError, git_head, git_root, safe_git, validate_registry

_REQUIRED = ("dependency_target", "dependency_wheelhouse", "scratch_root", "run_id")
_OPTIONAL = ("timeout_seconds", "output_cap_bytes", "expected_registry_sha256", "expected_runner_tree_sha256")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
RUNNER_TREE_PREFIX = "tools/qa"
CHILD_GRACE_SECONDS = 300          # dependency verification and evidence commit around the pytest bound
CHILD_STDOUT_CAP = 1024 * 1024     # the runner prints PASS lines and one QA_RESULT line
CHILD_STDERR_CAP = 256 * 1024
MAX_APPENDED_BYTES = 8 * 1024 * 1024


def _abs_path(value: Any, name: str) -> Path:
    try:
        path = Path(value)
    except TypeError:
        raise ExecutorError("OPTION_INVALID", f"{name} must be a path") from None
    if not path.is_absolute():
        raise ExecutorError("OPTION_INVALID", f"{name} must be an absolute path")
    return path


def _outside(path: Path, root: Path, name: str) -> Path:
    real, real_root = Path(os.path.realpath(path)), Path(os.path.realpath(root))
    if real == real_root or real.is_relative_to(real_root) or real_root.is_relative_to(real):
        raise ExecutorError("PATH_INSIDE_REPOSITORY", f"{name} must resolve outside the candidate repository")
    return real


def _bounded_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ExecutorError("OPTION_INVALID", f"{name} must be an int in {low}..{high}")
    return value


def _pin(options: dict[str, Any], name: str) -> str | None:
    value = options.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not _HEX64.fullmatch(value) or set(value) == {"0"}:
        raise ExecutorError("OPTION_INVALID", f"{name} must be a non-zero lowercase sha256 hex digest")
    return value


def _fixed_paths(category: str) -> dict[str, str]:
    base = f"{qa_run.EVIDENCE_DIR}/{category}"
    return {"report": f"{base}.report.jsonl", "stdout": f"{base}.stdout.txt", "stderr": f"{base}.stderr.txt"}


def _size(path: Path) -> int:
    try:
        return path.lstat().st_size
    except FileNotFoundError:
        return 0


def runner_tree_sha256(root: Path, head: str) -> str:
    """sha256 over the sorted 'path\\0blobsha\\n' lines of every entry under tools/qa at commit `head`.

    Read-only git (ls-tree of the commit, not of the worktree); the same value a caller can compute
    independently and pin as expected_runner_tree_sha256.
    """
    try:
        raw = safe_git(root, "ls-tree", "-r", "-z", head, "--", RUNNER_TREE_PREFIX)
    except RegistryError as exc:
        raise ExecutorError("REPO_UNUSABLE", f"tools/qa tree could not be listed: {str(exc)[:120]}") from None
    rows: list[str] = []
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        fields = meta.split(b" ")
        if len(fields) != 3 or not _HEX40.fullmatch(fields[2].decode("ascii", "replace")):
            raise ExecutorError("REPO_UNUSABLE", "unreadable ls-tree entry under tools/qa")
        rows.append(f"{os.fsdecode(path)}\0{fields[2].decode('ascii')}\n")
    if not rows:
        raise ExecutorError("REPO_UNUSABLE", "tools/qa has no tracked files at the expected head")
    return hashlib.sha256("".join(sorted(rows)).encode("utf-8", "surrogateescape")).hexdigest()


def _unexpected_paths(root: Path, category: str) -> list[str]:
    try:
        return qa_run._unexpected_candidate_paths(qa_run._git_status_paths(root), category)
    except (ValueError, RegistryError):
        raise ExecutorError("REPO_UNUSABLE", "worktree state could not be determined") from None


def _select_record(path: Path, offset: int, run_id: str, category: str) -> tuple[dict[str, Any], int]:
    """The record of THIS run among the bytes appended since `offset` (seek, capped, torn tail dropped)."""
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(MAX_APPENDED_BYTES + 1)
    except OSError:
        data = b""
    if len(data) > MAX_APPENDED_BYTES:
        raise ExecutorError("NATIVE_RECORD_TOO_LARGE", "appended evidence exceeds the 8 MiB bound")
    if not data.endswith(b"\n"):
        data = data[: data.rfind(b"\n") + 1]     # a partial last line from another writer is ignored
    mine: list[dict[str, Any]] = []
    for line in data.split(b"\n"):
        if not line.strip():
            continue
        try:
            record = loads_strict(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError, MemoryError):
            continue
        if isinstance(record, dict) and record.get("run_id") == run_id and record.get("category") == category:
            mine.append(record)
    if not mine:
        raise ExecutorError("NATIVE_NO_RECORD", "no complete record for this run_id and category was appended")
    # Exactly one record, unless the runner's documented superseding BLOCKED record follows its first.
    if len(mine) > 1 and mine[-1].get("result") != "BLOCKED":
        raise ExecutorError("NATIVE_RECORD_AMBIGUOUS", f"{len(mine)} records share this run_id")
    return mine[-1], len(mine)


def _artifact_bytes(
    root: Path, paths: dict[str, str], record: dict[str, Any], cap: int
) -> dict[str, bytes] | None:
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
        if end - start > 2 * cap + 4096:        # redaction can lengthen text; anything larger is not ours
            return None
        try:
            with (root / Path(*paths[key].split("/"))).open("rb") as handle:
                if end > os.fstat(handle.fileno()).st_size:
                    return None
                handle.seek(start)
                data = handle.read(end - start)
        except OSError:
            return None
        if len(data) != end - start:
            return None
        result[key] = data
    return result


class NativeExecutor:
    """Executor A (`vst-native`): per-id accounting; APPROVABLE only with matching caller pins."""

    executor_id = EXECUTOR_NATIVE

    def run(self, category: str, *, repo_root: Any, expected_head: str, **options: Any) -> ExecutorReport:
        """Required options: dependency_target, dependency_wheelhouse, scratch_root, run_id.
        Optional: timeout_seconds (1..3600, default 900), output_cap_bytes (1..4 MiB, default 1 MiB),
        expected_registry_sha256 and expected_runner_tree_sha256 (lift the candidate-attested cap)."""
        category = require_category(category)
        expected_head = require_head(expected_head)
        require_options(options, required=_REQUIRED, optional=_OPTIONAL)
        target = _abs_path(options["dependency_target"], "dependency_target")
        wheelhouse = _abs_path(options["dependency_wheelhouse"], "dependency_wheelhouse")
        scratch = _abs_path(options["scratch_root"], "scratch_root")
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
        registry_pin = _pin(options, "expected_registry_sha256")
        runner_pin = _pin(options, "expected_runner_tree_sha256")

        if os.name != "nt":
            raise ExecutorError("PLATFORM_UNSUPPORTED", "the native runner supports the Windows profile only")
        python = qa_run.EXPECTED_PYTHON_EXE
        if not os.path.isfile(python):
            raise ExecutorError("INTERPRETER_MISSING", "the pinned CPython 3.14.3 interpreter is absent")
        try:
            root = git_root(repo_root)
            if root != Path(repo_root).resolve(strict=True):
                raise ExecutorError("NOT_REPO_ROOT", "repo_root must be the repository root")
            assert_trusted_git(root)
            if git_head(root) != expected_head:
                raise ExecutorError("STALE_HEAD", "repository HEAD differs from expected_head; nothing was run")
        except RegistryError as exc:
            raise ExecutorError("REPO_UNUSABLE", str(exc)[:200]) from None
        _outside(target, root, "dependency_target")
        _outside(wheelhouse, root, "dependency_wheelhouse")
        _outside(scratch, root, "scratch_root")

        # Precondition: only this category's own three artifacts may be dirty (no earlier category's evidence).
        dirty = _unexpected_paths(root, category)
        if dirty:
            raise ExecutorError(
                "CANDIDATE_DIRTY_BEFORE_RUN",
                f"{len(dirty)} path(s) outside this category's artifacts are modified or untracked: {dirty[:8]}",
            )

        tree_sha = runner_tree_sha256(root, expected_head)
        if runner_pin is not None and runner_pin != tree_sha:
            raise ExecutorError("RUNNER_PIN_MISMATCH", "tools/qa tree digest at expected_head differs from the pin")
        if registry_pin is not None:
            try:
                pre_registry = validate_registry(root, qa_run.MANIFEST_PATH, check_artifacts=False)
            except RegistryError as exc:
                raise ExecutorError("REGISTRY_UNAVAILABLE", str(exc)[:160]) from None
            if pre_registry.sha256 != registry_pin:
                raise ExecutorError("REGISTRY_PIN_MISMATCH", "registry sha256 at expected_head differs from the pin")

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

        try:
            if git_head(root) != expected_head:       # immediately before launch
                raise ExecutorError("STALE_HEAD", "HEAD moved before launch; nothing was run")
        except RegistryError as exc:
            raise ExecutorError("REPO_UNUSABLE", str(exc)[:200]) from None
        child = run_child(
            argv, cwd=os.fspath(root), env=env, timeout=timeout + CHILD_GRACE_SECONDS,
            stdout_cap=CHILD_STDOUT_CAP, stderr_cap=CHILD_STDERR_CAP,
        )
        if child.timed_out:
            raise ExecutorError("NATIVE_CHILD_TIMEOUT", "the runner exceeded its outer bound; tree killed")
        if child.output_incomplete:
            raise ExecutorError("NATIVE_OUTPUT_TRUNCATED", "runner console output was truncated or incomplete")

        # Re-read HEAD and the worktree here; the record's own head_after is not trusted.
        try:
            head_now = git_head(root)
        except RegistryError as exc:
            raise ExecutorError("REPO_UNUSABLE", str(exc)[:200]) from None
        if head_now != expected_head:
            raise ExecutorError("STALE_HEAD", "HEAD differs from expected_head after the run")
        dirty_after = _unexpected_paths(root, category)
        if dirty_after:
            raise ExecutorError(
                "CANDIDATE_DIRTY_AFTER_RUN", f"{len(dirty_after)} unexpected path(s) after the run: {dirty_after[:8]}"
            )

        try:
            record, record_count = _select_record(report_path, offset, run_id, category)
        except ExecutorError as exc:
            if exc.code == "NATIVE_NO_RECORD":
                tail = child.stdout.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
                raise ExecutorError(
                    "NATIVE_NO_RECORD", f"{exc.detail} (runner exit {child.returncode}): {tail[0][:160]}"
                ) from None
            raise

        result = record.get("result")
        if result == "UNSUPPORTED":
            raise ExecutorError("UNSUPPORTED_CATEGORY", "the registry marks this category UNSUPPORTED")
        if not isinstance(result, str) or result not in RESULTS:
            raise ExecutorError("RESULT_UNMAPPED", f"native result {str(result)[:40]!r} has no mapping")
        if (child.returncode == 0) != (result == "PASS"):
            raise ExecutorError(
                "NATIVE_EXIT_INCONSISTENT", f"runner exit {child.returncode} disagrees with result {result}"
            )
        strict = result == "PASS"
        notes: list[str] = []
        if record_count > 1:
            notes.append(f"{record_count} records share this run_id; the last (BLOCKED) supersedes the earlier ones")

        def head_field(key: str) -> str | None:
            value = record.get(key)
            if isinstance(value, str) and _HEX40.fullmatch(value):
                return value
            if strict:
                raise ExecutorError("NATIVE_RECORD_INVALID", f"{key} is not a commit id in a PASS record")
            notes.append(f"{key} is absent or malformed in the record")
            return None

        def id_field(key: str) -> tuple[str, ...] | None:
            value = record.get(key)
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return tuple(value)
            if strict:
                raise ExecutorError("NATIVE_RECORD_INVALID", f"{key} is missing or not a list of strings")
            notes.append(f"{key} is absent or malformed in the record; NOT_AVAILABLE")
            return None

        candidate_head = head_field("candidate_head")
        record_head_after = record.get("head_after")
        if record_head_after is not None and record_head_after != head_now:
            notes.append("record head_after differs from the HEAD re-read by the executor")
        exit_code = record.get("exit_code")
        if exit_code is not None and (isinstance(exit_code, bool) or not isinstance(exit_code, int)):
            raise ExecutorError("NATIVE_RECORD_INVALID", "exit_code is not an int")
        digests = record.get("artifact_digests", {})
        raw_reasons = record.get("not_run_test_reasons", {})
        texts = record.get("reasons", [])
        if not isinstance(digests, dict) or not isinstance(raw_reasons, dict) or not isinstance(texts, list):
            raise ExecutorError("NATIVE_RECORD_INVALID", "digest, not-run or reason fields have the wrong type")
        not_run = {
            str(key): value if isinstance(value, str) else _json_text(value)
            for key, value in raw_reasons.items()
        }
        ids = {
            "expected_ids": id_field("expected_test_ids"),
            "collected_ids": id_field("collected_node_ids"),
            "passed_ids": id_field("passed_test_ids"),
            "skipped_ids": id_field("skipped_test_ids"),
            "failed_ids": id_field("failed_test_ids"),
            "uncollected_ids": id_field("uncollected_test_ids"),
            "xfail_ids": id_field("xfail_test_ids"),
        }

        record_registry = record.get("registry_sha256")
        if registry_pin is not None and record_registry != registry_pin:
            raise ExecutorError("REGISTRY_PIN_MISMATCH", "the record is bound to a different registry than the pin")
        try:
            registry = validate_registry(root, qa_run.MANIFEST_PATH, check_artifacts=False)
        except RegistryError as exc:
            verdict, codes = "NON_APPROVING", ("REGISTRY_UNAVAILABLE",)
            notes.append(f"registry could not be validated after the run: {str(exc)[:120]}")
        else:
            if registry_pin is not None and registry.sha256 != registry_pin:
                raise ExecutorError("REGISTRY_PIN_MISMATCH", "registry sha256 after the run differs from the pin")
            check = gate_check.check_report(
                record, registry, expected_head=expected_head,
                artifact_bytes=_artifact_bytes(root, paths, record, cap),
            )
            verdict, codes = check.verdict, tuple(sorted(check.codes()))

        attested = not (registry_pin is not None and runner_pin is not None)
        all_digests = dict(digests)
        all_digests["runner_tree_sha256"] = tree_sha
        if isinstance(record_registry, str) and _HEX64.fullmatch(record_registry):
            all_digests["registry_sha256"] = record_registry
        try:
            return build_report(
                category=category, executor_id=EXECUTOR_NATIVE, expected_head=expected_head,
                candidate_head=candidate_head, head_after=head_now, result=result, exit_code=exit_code,
                ids=ids, artifact_digests=all_digests, not_run_reasons=not_run,
                reasons=[*[t for t in texts if isinstance(t, str)], *notes],
                native_verdict=verdict, native_reason_codes=codes, raw_record=record,
                candidate_attested=attested,
            )
        except ExecutorError as exc:
            if exc.code == "REPORT_INVALID":
                raise ExecutorError("NATIVE_RECORD_INVALID", exc.detail) from None
            raise


def _json_text(value: Any) -> str:
    import json

    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True)
    except (TypeError, ValueError, RecursionError):
        return "<unrepresentable>"
