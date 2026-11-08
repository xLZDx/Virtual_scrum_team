"""Validate the committed QA registry and bind it to source files and Git HEAD."""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PRIMARY_CATEGORIES = frozenset(
    {"functional", "integration", "api", "e2e", "identity", "qa-tooling", "seeded-failure"}
)
ALL_CATEGORIES = PRIMARY_CATEGORIES | {"regression"}
WINDOWS_PROFILE = "windows-cpython-3.14.3"
WSL_PROFILE = "wsl-ubuntu-24.04-cpython-3.12.3"
WSL_ROOT_PROFILE = "wsl-ubuntu-24.04-root-harness"
RUNTIME_PROFILES = (WINDOWS_PROFILE, WSL_PROFILE, WSL_ROOT_PROFILE)
IDENTITY_SELECTOR = "tests/qa/test_s4_functional_worker_identity.py::test_s4_worker_helper_drops_runner_identity_and_denies_runner_sentinels"
POSIX_ONLY_SELECTORS = frozenset({
    "tests/qa/test_s4_functional_worker_identity.py::test_s4_worker_helper_drops_runner_identity_and_denies_runner_sentinels",
    "tests/vst/test_e3_store.py::test_database_file_is_owner_only_on_posix",
    "tests/vst/test_e4_runner.py::test_link_created_by_the_command_itself_gets_a_zero_digest",
    "tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork",
    "tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes",
    "tests/vst/test_s2_store_lifecycle.py::test_exactly_one_event_ahead_is_recovered_before_mutation",
    "tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed",
    "tests/vst/test_s2_store_lifecycle.py::test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append",
})
WSL_ROOT_ONLY_SELECTORS = frozenset({
    "tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file",
    "tests/vst/test_s2_sandbox_probe.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture",
})
WINDOWS_ONLY_SELECTORS = frozenset({
    "tests/vst/test_e4_runner.py::test_job_is_closed_when_thread_start_fails",
})
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SELECTOR = re.compile(
    r"(?P<path>tests/[A-Za-z0-9_./-]+\.py)::"
    r"(?:(?P<class>[A-Za-z_][A-Za-z0-9_]*)::)?(?P<function>test_[A-Za-z0-9_]+)\Z"
)
_TEST_FILE = re.compile(r"test_[A-Za-z0-9_]+\.py\Z")


def required_runtime_profiles(selector: str) -> list[str]:
    """Return the committed S4 profile assignment contract for one selector."""
    if selector in WSL_ROOT_ONLY_SELECTORS:
        return [WSL_ROOT_PROFILE]
    if selector in POSIX_ONLY_SELECTORS:
        return [WSL_PROFILE]
    if selector in WINDOWS_ONLY_SELECTORS:
        return [WINDOWS_PROFILE]
    return [WINDOWS_PROFILE, WSL_PROFILE]


class RegistryError(ValueError):
    """Raised when the committed registry cannot prove its exact denominator."""


class MissingSourceError(RegistryError):
    """A repository file does not exist (as opposed to being unreadable or unsafe)."""


@dataclass(frozen=True)
class ValidatedRegistry:
    data: dict[str, Any]
    sha256: str
    candidate_head: str
    selectors_by_id: dict[str, dict[str, Any]]
    category_test_ids: dict[str, list[str]]
    category_inventory_ids: dict[str, list[str]]
    category_not_run: dict[str, dict[str, str]]
    category_profile_test_ids: dict[str, dict[str, list[str]]]
    category_profile_not_run: dict[str, dict[str, dict[str, str]]]
    category_profile_unassigned_ids: dict[str, dict[str, list[str]]]
    artifact_stage: dict[str, Any]


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError(f"manifest contains a duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _exact_keys(value: object, keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RegistryError(f"{context}: expected exact fields {sorted(keys)}")
    if any(not isinstance(key, str) for key in value):
        raise RegistryError(f"{context}: keys must be strings")
    return value


_GIT_ENV_ALLOWLIST = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP", "TMPDIR",
    "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
    "LANG", "LC_ALL",
)
_GIT_EXE: str | None = None


def git_executable() -> str:
    """Absolute path of git, resolved once per process (never re-resolved from a changed PATH)."""
    global _GIT_EXE
    if _GIT_EXE is None:
        found = shutil.which("git")
        if not found:
            raise RegistryError("git executable cannot be resolved")
        _GIT_EXE = os.path.abspath(found)
    return _GIT_EXE


def _git_env() -> dict[str, str]:
    """Allowlisted environment: no GIT_* variable is inherited; optional locks are disabled."""
    env = {name: os.environ[name] for name in _GIT_ENV_ALLOWLIST if name in os.environ}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _git_command(root: Path, *args: str) -> list[str]:
    return [
        git_executable(),
        "--no-replace-objects",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "safe.directory=",
        "-c",
        f"safe.directory={os.fspath(root)}",
        *args,
    ]


def safe_git(root: Path, *args: str) -> bytes:
    """Public wrapper: run one git query with the pinned executable and the allowlisted environment."""
    return _safe_git(root, *args)


def _safe_git(root: Path, *args: str) -> bytes:
    command = _git_command(root, *args)
    try:
        result = subprocess.run(
            command,
            cwd=root,
            env=_git_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RegistryError(f"Git provenance query failed ({type(exc).__name__})") from None
    if result.returncode != 0:
        raise RegistryError("Git provenance query failed")
    return result.stdout


def git_root(path: str | os.PathLike[str]) -> Path:
    try:
        candidate = Path(path).resolve(strict=True)
    except (OSError, TypeError, ValueError) as exc:
        raise RegistryError(f"candidate root cannot be resolved ({type(exc).__name__})") from None
    if not candidate.is_dir():
        raise RegistryError("candidate root must be a directory")
    root_bytes = _safe_git(candidate, "rev-parse", "--show-toplevel")
    try:
        root = Path(os.fsdecode(root_bytes).strip()).resolve(strict=True)
    except OSError:
        raise RegistryError("Git returned an invalid repository root") from None
    return root


def git_head(root: Path) -> str:
    head = os.fsdecode(_safe_git(root, "rev-parse", "--verify", "HEAD")).strip()
    if _HEX40.fullmatch(head) is None:
        raise RegistryError("candidate HEAD is not a canonical commit id")
    return head


def _latest_path_commit(root: Path, relative: str) -> str:
    output = os.fsdecode(
        _safe_git(root, "log", "-1", "--format=%H", "--", relative)
    ).strip()
    if _HEX40.fullmatch(output) is None:
        raise RegistryError(f"source path has no committed provenance: {relative}")
    return output


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    command = _git_command(root, "merge-base", "--is-ancestor", ancestor, descendant)
    try:
        result = subprocess.run(
            command,
            cwd=root,
            env=_git_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RegistryError(f"Git ancestry query failed ({type(exc).__name__})") from None
    if result.returncode not in (0, 1):
        raise RegistryError("Git ancestry query failed")
    return result.returncode == 0


def _check_relative(relative: object) -> str:
    if (
        not isinstance(relative, str)
        or not relative
        or "\x00" in relative
        or relative.startswith("/")
        or "\\" in relative
        or ".." in relative.split("/")
    ):
        raise RegistryError(f"non-canonical repository path: {relative!r}")
    return relative


def _read_repo_file(root: Path, relative: str) -> bytes:
    _check_relative(relative)
    path = root.joinpath(*relative.split("/"))
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        raise MissingSourceError(f"required source file is missing: {relative}") from None
    except (OSError, ValueError) as exc:
        raise RegistryError(f"cannot resolve source file: {relative} ({type(exc).__name__})") from None
    if not resolved.is_relative_to(root) or path.is_symlink():
        raise RegistryError(f"source path escapes the repository: {relative}")
    try:
        return resolved.read_bytes()
    except OSError as exc:
        raise RegistryError(f"cannot read source file: {relative} ({type(exc).__name__})") from None


def _read_head_blob(root: Path, relative: str) -> bytes:
    """Return the committed bytes of a file at HEAD (never the working-tree copy)."""
    _check_relative(relative)
    return _safe_git(root, "cat-file", "blob", f"HEAD:{relative}")


_SCOPED_IGNORED_PREFIXES = ("tests/", "docs/qa/", "tools/qa/")


def _ignored_entry_ok(root: Path, relative: str) -> bool:
    """Only interpreter/pytest caches may be ignored inside the scoped trees."""
    is_dir = relative.endswith("/")
    parts = relative.rstrip("/").split("/")
    if ".pytest_cache" in parts:
        return True
    if "__pycache__" not in parts:
        return False
    if is_dir:
        if parts[-1] != "__pycache__":
            return False
        directory = root.joinpath(*parts)
        try:
            with os.scandir(directory) as entries:
                return all(
                    entry.is_file(follow_symlinks=False) and entry.name.endswith(".pyc") for entry in entries
                )
        except OSError:
            return False
    return len(parts) >= 2 and parts[-2] == "__pycache__" and parts[-1].endswith(".pyc")


_ROOT_DANGEROUS_NAMES = frozenset(
    {"conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", "setup.py"}
)
_ROOT_DANGEROUS_SUFFIXES = (".py", ".pyc", ".pyd", ".pth")
_ROOT_DANGEROUS_STEMS = ("sitecustomize", "usercustomize")
_MAX_ROOT_DIR_WALK = 200_000


def _root_ignored_is_dangerous(root: Path, relative: str) -> bool:
    """Root-level ignored entry that could change pytest behavior or shadow the dependency target.

    Other root-level ignored files (temp files, editor droppings) are harmless and never block.
    """
    name = relative.rstrip("/")
    if not relative.endswith("/"):
        lowered = name.lower()
        return (
            lowered in _ROOT_DANGEROUS_NAMES
            or lowered.endswith(_ROOT_DANGEROUS_SUFFIXES)
            or lowered.startswith(_ROOT_DANGEROUS_STEMS)
        )
    if name in {".pytest_cache", "__pycache__"}:
        return not _ignored_entry_ok(root, relative)
    seen = 0
    for _current, directories, files in os.walk(root / name, followlinks=False):
        for filename in files:
            if filename in {"conftest.py", "__init__.py"}:
                return True
        seen += len(directories) + len(files)
        if seen > _MAX_ROOT_DIR_WALK:
            return True  # fail closed: too large to prove free of importable packages
    return False


def worktree_binding_violations(root: Path) -> list[str]:
    """Ignored files and skip-worktree/assume-unchanged flags that could hide candidate content."""
    violations: list[str] = []
    output = _safe_git(root, "status", "--porcelain", "--ignored=matching", "--untracked-files=all", "-z")
    for entry in output.split(b"\x00"):
        if not entry.startswith(b"!! "):
            continue
        relative = os.fsdecode(entry[3:]).replace("\\", "/")
        if relative.startswith(_SCOPED_IGNORED_PREFIXES):
            if not _ignored_entry_ok(root, relative):
                violations.append(f"ignored path: {relative}")
        elif "/" not in relative.rstrip("/") and _root_ignored_is_dangerous(root, relative):
            violations.append(f"ignored root path that can alter pytest or shadow dependencies: {relative}")
    flags = _safe_git(root, "ls-files", "-v", "-z")
    for entry in flags.split(b"\x00"):
        if entry and entry[:1] != b"H":
            violations.append(f"index flag {entry[:1].decode('ascii', 'replace')!r}: {os.fsdecode(entry[2:])}")
    return violations


def check_worktree_clean(root: Path) -> None:
    """Fail closed when tests/, docs/qa/ or tools/qa/ have dirty or untracked paths.

    Also rejects ignored files (except interpreter/pytest caches) under tests/, docs/qa/,
    tools/qa/ and the repository root level, and any non-'H' `git ls-files -v` flag
    (skip-worktree / assume-unchanged), which would hide candidate content from git status.
    """
    output = _safe_git(
        root, "status", "--porcelain", "--untracked-files=all", "-z", "--", "tests", "docs/qa", "tools/qa"
    )
    entries = [entry for entry in output.split(b"\x00") if entry]
    if entries:
        sample = ", ".join(os.fsdecode(entry) for entry in entries[:5])
        raise RegistryError(
            "working tree has uncommitted or untracked paths under tests/, docs/qa/ or tools/qa/"
            f" (count={len(entries)}): {sample}"
        )
    violations = worktree_binding_violations(root)
    if violations:
        raise RegistryError(
            f"working tree has ignored or hidden paths (count={len(violations)}): {', '.join(violations[:5])}"
        )


def check_tests_unchanged_since(
    root: Path, source_head: str, head: str, inventory_paths: set[str]
) -> None:
    """Files under tests/ changed after source_head must be inventoried (hash-checked at HEAD)."""
    output = _safe_git(root, "diff", "--name-only", "-z", source_head, head, "--", "tests")
    changed = [os.fsdecode(entry) for entry in output.split(b"\x00") if entry]
    unlisted = sorted(path for path in changed if path not in inventory_paths)
    if unlisted:
        raise RegistryError(
            f"tests/ files changed after source_head without a manifest entry (count={len(unlisted)}): "
            f"{', '.join(unlisted[:5])}"
        )


_UNITTEST_CASE_NAMES = frozenset({"TestCase", "IsolatedAsyncioTestCase"})
_UNITTEST_MODULES = frozenset({"unittest", "unittest.case", "unittest.async_case"})


def _contains_collectable(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.ClassDef)
        or (isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test"))
        for child in ast.walk(node)
    )


def _contains_test_def(node: ast.AST) -> bool:
    return any(
        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test")
        for child in ast.walk(node)
    )


def _function_selectors(source_path: str, content: bytes) -> set[str]:
    """Statically list the selectors pytest collects from one test module.

    Collected (pytest defaults): top-level functions whose name starts with "test";
    top-level plain classes named Test* that define no __init__/__new__ (own or
    inherited); top-level classes deriving (directly or through local classes) from
    unittest.TestCase, whatever their name. Methods are those starting with "test",
    including inherited ones of local bases. Anything not statically resolvable
    (non-local/non-TestCase base, nested classes with tests, test defs under
    compound statements) raises RegistryError instead of being skipped.
    """
    try:
        source = content.decode("utf-8")
        tree = ast.parse(source, filename=source_path)
    except (UnicodeError, SyntaxError, ValueError, RecursionError) as exc:
        raise RegistryError(
            f"test source cannot be statically parsed: {source_path} ({type(exc).__name__})"
        ) from None

    def unresolved(what: str) -> RegistryError:
        return RegistryError(f"{source_path}: {what}; pytest collection cannot be proven statically")

    unittest_aliases: dict[str, str] = {}
    testcase_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    if alias.name in _UNITTEST_MODULES:
                        unittest_aliases[alias.asname] = alias.name
                elif alias.name == "unittest" or alias.name.startswith("unittest."):
                    unittest_aliases["unittest"] = "unittest"
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module in _UNITTEST_MODULES:
            for alias in node.names:
                if alias.name in _UNITTEST_CASE_NAMES:
                    testcase_names.add(alias.asname or alias.name)

    classes: dict[str, ast.ClassDef] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes[node.name] = node
        elif not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _contains_collectable(node):
            raise unresolved("collectable definition nested in a module-level compound statement")

    def base_kind(base: ast.expr, class_name: str) -> tuple[str, str]:
        if isinstance(base, ast.Name):
            if base.id in classes:
                return "local", base.id
            if base.id in testcase_names:
                return "testcase", ""
            if isinstance(getattr(builtins, base.id, None), type):
                return "plain", base.id
        elif isinstance(base, ast.Attribute):
            parts: list[str] = []
            cursor: ast.expr = base
            while isinstance(cursor, ast.Attribute):
                parts.append(cursor.attr)
                cursor = cursor.value
            if isinstance(cursor, ast.Name):
                parts.append(cursor.id)
                parts.reverse()
                if parts[-1] in _UNITTEST_CASE_NAMES and parts[0] in unittest_aliases:
                    module = ".".join([unittest_aliases[parts[0]], *parts[1:-1]])
                    if module in _UNITTEST_MODULES:
                        return "testcase", ""
        raise unresolved(f"class {class_name} has a base that cannot be resolved")

    def is_testcase(class_name: str, visited: frozenset[str] = frozenset()) -> bool:
        if class_name in visited:
            return False
        visited = visited | {class_name}
        result = False
        for base in classes[class_name].bases:
            kind, local = base_kind(base, class_name)
            if kind == "testcase" or (kind == "local" and is_testcase(local, visited)):
                result = True
        return result

    def has_init(class_name: str, seen: frozenset[str] = frozenset()) -> bool:
        if class_name in seen:
            return False
        seen = seen | {class_name}
        node = classes[class_name]
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if member.name in ("__init__", "__new__"):
                    return True
            elif isinstance(member, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = member.targets if isinstance(member, ast.Assign) else [member.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in ("__init__", "__new__"):
                        return True
        for base in node.bases:
            kind, name = base_kind(base, class_name)
            if kind == "local" and has_init(name, seen):
                return True
            if kind == "plain":
                builtin = getattr(builtins, name)
                if builtin.__init__ is not object.__init__ or builtin.__new__ is not object.__new__:
                    return True
        return False

    def collect_methods(class_name: str, seen: frozenset[str] = frozenset()) -> set[str]:
        if class_name in seen:
            return set()
        seen = seen | {class_name}
        node = classes[class_name]
        methods: set[str] = set()
        for member in node.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if member.name.startswith("test"):
                    methods.add(member.name)
            elif isinstance(member, ast.ClassDef):
                if _contains_test_def(member):
                    raise unresolved(f"nested class {member.name} in {class_name} contains test methods")
            elif _contains_collectable(member):
                raise unresolved(f"collectable definition in a compound statement of class {class_name}")
        for base in node.bases:
            kind, local = base_kind(base, class_name)
            if kind == "local":
                methods.update(collect_methods(local, seen))
        return methods

    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            found.add(f"{source_path}::{node.name}")
    for class_name in sorted(classes):
        # is_testcase() also resolves (or rejects) every base of every top-level class.
        derives_testcase = is_testcase(class_name)
        if derives_testcase or (class_name.startswith("Test") and not has_init(class_name)):
            for method_name in sorted(collect_methods(class_name)):
                found.add(f"{source_path}::{class_name}::{method_name}")
    return found


def inventory_test_files(root: Path) -> list[str]:
    tests_root = root / "tests"
    if not tests_root.is_dir():
        raise RegistryError("tests directory is missing")
    files = sorted(
        path.relative_to(root).as_posix()
        for path in tests_root.rglob("*.py")
        if _TEST_FILE.fullmatch(path.name)
    )
    if not files:
        raise RegistryError("no committed test modules were found")
    return files


def check_artifact_stage(root: Path, artifacts: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Optional evidence-artifact stage, kept apart from the registry proof.

    The registry itself never needs report files. Reports are produced by later
    stages; while none exist the stage is reported as SKIPPED (never as passed),
    when all exist and are non-empty it is PRESENT (existence and non-emptiness
    only; content is validated by the report stage), and a partial set fails
    closed. Only a missing file counts as absent; an unreadable, unsafe or empty
    file raises RegistryError.
    """
    if not isinstance(artifacts, dict):
        raise RegistryError("artifacts must be an object")
    expected: list[str] = []
    for category in sorted(artifacts):
        entry = artifacts[category]
        if not isinstance(category, str) or not isinstance(entry, dict):
            raise RegistryError("artifacts entries must map categories to path objects")
        for kind in ("report", "stdout", "stderr"):
            if not isinstance(entry.get(kind), str):
                raise RegistryError(f"artifacts.{category}.{kind} must be a path string")
            expected.append(entry[kind])
    present: list[str] = []
    absent: list[str] = []
    for relative in expected:
        try:
            content = _read_repo_file(root, relative)
        except MissingSourceError:
            absent.append(relative)
            continue
        if not content:
            raise RegistryError(f"evidence artifact is empty: {relative}")
        present.append(relative)
    if present and absent:
        raise RegistryError(
            f"evidence artifacts are partially present (present={len(present)}, absent={len(absent)})"
        )
    if absent:
        return {
            "status": "SKIPPED",
            "reason": "no evidence artifacts exist yet; this is not evidence of a passing run",
            "expected": len(expected),
            "present": 0,
        }
    return {
        "status": "PRESENT",
        "scope": "existence-only",
        "reason": None,
        "expected": len(expected),
        "present": len(present),
    }


def denominator(registry: ValidatedRegistry) -> dict[str, dict[str, Any]]:
    """Expected selector counts per category. Nothing here counts as passed.

    `complete` is True only for a non-empty category in which every selector is
    runnable (no NOT_RUN); an empty or NOT_RUN-bearing category is never complete.
    """
    result: dict[str, dict[str, Any]] = {}
    for category in sorted(registry.category_inventory_ids):
        expected = len(registry.category_inventory_ids[category])
        runnable = len(registry.category_test_ids[category])
        not_run = len(registry.category_not_run[category])
        result[category] = {
            "expected": expected,
            "runnable": runnable,
            "not_run": not_run,
            "complete": expected > 0 and not_run == 0 and runnable == expected,
        }
    return result


def count_passed(
    registry: ValidatedRegistry, outcomes: dict[str, dict[str, str]]
) -> dict[str, dict[str, Any]]:
    """Count passes against the denominator; fail closed on unknown profiles/selectors.

    `outcomes` is {runtime_profile: {selector: outcome}}. A selector counts as
    passed only if it is runnable and EVERY profile in
    required_runtime_profiles(selector) reports the exact outcome "passed".
    Missing, skipped, xfailed, errored or NOT_RUN selectors stay in the
    denominator without being counted. A parametrized function counts as passed
    only if all its cases passed; the caller aggregates the cases into one
    "passed" outcome per selector and profile. Any other value shape raises.
    `complete` is False when the category is empty or passed != expected.
    """
    if not isinstance(outcomes, dict):
        raise RegistryError("outcomes must map runtime profiles to selector outcome maps")
    for profile, per_profile in outcomes.items():
        if not isinstance(profile, str) or profile not in RUNTIME_PROFILES:
            raise RegistryError("outcomes contain an unknown runtime profile")
        if not isinstance(per_profile, dict):
            raise RegistryError("outcomes for a runtime profile must map selectors to outcomes")
        unknown = [
            selector for selector in per_profile
            if not isinstance(selector, str) or selector not in registry.selectors_by_id
        ]
        if unknown:
            raise RegistryError(
                f"outcomes contain selectors absent from the registry (count={len(unknown)})"
            )
        if any(not isinstance(outcome, str) for outcome in per_profile.values()):
            raise RegistryError("outcome values must be strings")

    def selector_passed(selector: str) -> bool:
        return all(
            outcomes.get(profile, {}).get(selector) == "passed"
            for profile in required_runtime_profiles(selector)
        )

    result: dict[str, dict[str, Any]] = {}
    for category, expected in sorted(registry.category_inventory_ids.items()):
        runnable = set(registry.category_test_ids[category])
        passed = sum(1 for test_id in expected if test_id in runnable and selector_passed(test_id))
        result[category] = {
            "expected": len(expected),
            "passed": passed,
            "not_passed": len(expected) - passed,
            "complete": len(expected) > 0 and passed == len(expected),
        }
    return result


def validate_registry(
    root_path: str | os.PathLike[str],
    manifest_path: str = "docs/qa/categories.json",
    *,
    check_artifacts: bool = True,
) -> ValidatedRegistry:
    root = git_root(root_path)
    check_worktree_clean(root)
    manifest_bytes = _read_repo_file(root, manifest_path)
    try:
        data = json.loads(manifest_bytes, object_pairs_hook=_no_duplicate_keys)
    except RegistryError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise RegistryError("category manifest is not valid UTF-8 JSON") from None

    data = _exact_keys(
        data,
        {
            "schema_version",
            "registry_version",
            "runtime_profiles",
            "artifacts",
            "source_head",
            "source_inventory",
            "tests",
            "categories",
            "aggregates",
            "unsupported_apis",
        },
        "manifest",
    )
    if (
        type(data["schema_version"]) is not int
        or data["schema_version"] != 2
        or not isinstance(data["registry_version"], str)
        or data["registry_version"] != "2"
    ):
        raise RegistryError("manifest schema or registry version is unsupported")
    profiles = data["runtime_profiles"]
    if profiles != list(RUNTIME_PROFILES):
        raise RegistryError("manifest runtime profiles do not match the supported profile matrix")
    artifacts = data["artifacts"]
    expected_artifacts = {
        category: {
            "report": f"docs/sdlc/evidence/qa/{category}.report.jsonl",
            "stdout": f"docs/sdlc/evidence/qa/{category}.stdout.txt",
            "stderr": f"docs/sdlc/evidence/qa/{category}.stderr.txt",
        }
        for category in ALL_CATEGORIES | {"seeded-failure"}
    }
    if artifacts != expected_artifacts:
        raise RegistryError("manifest artifact paths do not match the fixed append-only category paths")
    source_head = data["source_head"]
    if not isinstance(source_head, str) or _HEX40.fullmatch(source_head) is None:
        raise RegistryError("source_head must be a canonical commit id")
    head = git_head(root)
    if not _is_ancestor(root, source_head, head):
        raise RegistryError("registry source_head is not an ancestor of candidate HEAD")

    inventory = data["source_inventory"]
    if not isinstance(inventory, list):
        raise RegistryError("source_inventory must be a list")
    inventory_by_path: dict[str, dict[str, Any]] = {}
    actual_selectors: set[str] = set()
    for index, raw_item in enumerate(inventory):
        item = _exact_keys(raw_item, {"path", "source_commit", "sha256"}, f"source_inventory[{index}]")
        path = item["path"]
        commit = item["source_commit"]
        digest = item["sha256"]
        if not isinstance(path, str) or not _TEST_FILE.fullmatch(Path(path).name):
            raise RegistryError(f"source_inventory[{index}].path is not a test module")
        if path in inventory_by_path:
            raise RegistryError(f"duplicate source inventory path: {path}")
        if not isinstance(commit, str) or _HEX40.fullmatch(commit) is None:
            raise RegistryError(f"source_inventory[{index}].source_commit is invalid")
        if not isinstance(digest, str) or _HEX64.fullmatch(digest) is None:
            raise RegistryError(f"source_inventory[{index}].sha256 is invalid")
        content = _read_head_blob(root, path)
        normalized_content = content.replace(b"\r\n", b"\n")
        if hashlib.sha256(normalized_content).hexdigest() != digest:
            raise RegistryError(f"test source changed after registry generation: {path}")
        if _latest_path_commit(root, path) != commit:
            raise RegistryError(f"test source provenance is stale: {path}")
        actual_selectors.update(_function_selectors(path, content))
        inventory_by_path[path] = item

    expected_files = set(inventory_test_files(root))
    if set(inventory_by_path) != expected_files:
        raise RegistryError("source_inventory does not cover every committed test module")
    check_tests_unchanged_since(root, source_head, head, set(inventory_by_path))

    categories = data["categories"]
    if not isinstance(categories, dict) or set(categories) != ALL_CATEGORIES:
        raise RegistryError("categories must declare all six primary categories and regression")
    tests = data["tests"]
    if not isinstance(tests, list):
        raise RegistryError("tests must be a list")
    selectors_by_id: dict[str, dict[str, Any]] = {}
    selectors: set[str] = set()
    categorized_ids: dict[str, list[str]] = {name: [] for name in PRIMARY_CATEGORIES}
    categorized_profiles: dict[str, dict[str, list[str]]] = {
        category: {profile: [] for profile in RUNTIME_PROFILES}
        for category in PRIMARY_CATEGORIES
    }
    for index, raw_test in enumerate(tests):
        item = _exact_keys(
            raw_test,
            {
                "test_id", "selector", "source_path", "source_commit",
                "primary_category", "runtime_profiles",
            },
            f"tests[{index}]",
        )
        test_id = item["test_id"]
        selector = item["selector"]
        source_path = item["source_path"]
        source_commit = item["source_commit"]
        category = item["primary_category"]
        runtime_profiles = item["runtime_profiles"]
        match = _SELECTOR.fullmatch(selector) if isinstance(selector, str) else None
        if match is None or test_id != selector:
            raise RegistryError(f"tests[{index}] selector or test_id is not canonical")
        if selector in selectors or test_id in selectors_by_id:
            raise RegistryError(f"duplicate selector/test id: {selector}")
        if source_path != match.group("path") or source_path not in inventory_by_path:
            raise RegistryError(f"tests[{index}] source_path does not match its selector")
        if source_commit != inventory_by_path[source_path]["source_commit"]:
            raise RegistryError(f"tests[{index}] source_commit is stale")
        if not isinstance(category, str) or category not in PRIMARY_CATEGORIES:
            raise RegistryError(f"tests[{index}] primary category is invalid")
        if (
            not isinstance(runtime_profiles, list)
            or any(not isinstance(profile, str) for profile in runtime_profiles)
            or runtime_profiles != sorted(set(runtime_profiles))
            or any(profile not in RUNTIME_PROFILES for profile in runtime_profiles)
        ):
            raise RegistryError(f"tests[{index}] runtime_profiles is invalid")
        if runtime_profiles and runtime_profiles != sorted(required_runtime_profiles(selector)):
            raise RegistryError(f"tests[{index}] runtime_profiles violates the selector platform contract")
        selectors.add(selector)
        selectors_by_id[test_id] = {
            "selector": selector,
            "primary_category": category,
            "runtime_profiles": runtime_profiles,
        }
        categorized_ids[category].append(test_id)
        for profile in runtime_profiles:
            categorized_profiles[category][profile].append(test_id)

    if selectors != actual_selectors:
        missing = sorted(actual_selectors - selectors)
        extra = sorted(selectors - actual_selectors)
        raise RegistryError(
            f"registry selector inventory differs from source (missing={len(missing)}, extra={len(extra)})"
        )

    for selector in sorted(
        POSIX_ONLY_SELECTORS | WSL_ROOT_ONLY_SELECTORS | WINDOWS_ONLY_SELECTORS
    ):
        module = selector.split("::", 1)[0]
        if module in inventory_by_path and selector not in actual_selectors:
            raise RegistryError(f"platform contract names a selector absent from source: {selector}")

    # The identity module is optional: it only exists once the S4 QA tests land.
    identity_module_selectors = {
        selector for selector in actual_selectors
        if selector.startswith("tests/qa/test_s4_functional_worker_identity.py::")
    }
    if identity_module_selectors not in (set(), {IDENTITY_SELECTOR}):
        raise RegistryError("identity test module must contain exactly the committed identity selector")
    categorized_identity = {
        test_id for test_id, item in selectors_by_id.items()
        if item["primary_category"] == "identity"
    }
    if categorized_identity != identity_module_selectors:
        raise RegistryError("identity category must contain exactly the committed identity selector")

    category_test_ids: dict[str, list[str]] = {}
    category_inventory_ids: dict[str, list[str]] = {}
    category_not_run: dict[str, dict[str, str]] = {}
    category_profile_test_ids: dict[str, dict[str, list[str]]] = {}
    category_profile_not_run: dict[str, dict[str, dict[str, str]]] = {}
    category_profile_unassigned_ids: dict[str, dict[str, list[str]]] = {}
    for category in sorted(PRIMARY_CATEGORIES):
        entry = _exact_keys(
            categories[category],
            {"status", "test_ids", "not_run_reasons", "reason"},
            f"categories.{category}",
        )
        status, ids, reason = entry["status"], entry["test_ids"], entry["reason"]
        if not isinstance(status, str) or status not in {"SUPPORTED", "NOT_RUN", "UNSUPPORTED"}:
            raise RegistryError(f"categories.{category}.status is invalid")
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise RegistryError(f"categories.{category}.test_ids must be a string list")
        if len(ids) != len(set(ids)) or sorted(ids) != sorted(categorized_ids[category]):
            raise RegistryError(f"categories.{category}.test_ids disagree with test assignments")
        not_run_reasons = entry["not_run_reasons"]
        if (
            not isinstance(not_run_reasons, dict)
            or any(test_id not in ids for test_id in not_run_reasons)
            or any(not isinstance(value, str) or not value.strip() for value in not_run_reasons.values())
        ):
            raise RegistryError(f"categories.{category}.not_run_reasons is invalid")
        if status == "SUPPORTED" and not (set(ids) - set(not_run_reasons)):
            raise RegistryError(f"categories.{category} cannot be SUPPORTED without a runnable selector")
        if status != "SUPPORTED" and ids:
            raise RegistryError(f"categories.{category} with status {status} must have empty test_ids")
        if status != "SUPPORTED" and (not isinstance(reason, str) or not reason.strip()):
            raise RegistryError(f"categories.{category} requires an exact non-approving reason")
        category_inventory_ids[category] = list(ids)
        category_not_run[category] = dict(not_run_reasons)
        category_test_ids[category] = sorted(set(ids) - set(not_run_reasons))
        category_profile_test_ids[category] = {}
        category_profile_not_run[category] = {}
        category_profile_unassigned_ids[category] = {}
        for profile in RUNTIME_PROFILES:
            profile_inventory = sorted(categorized_profiles[category][profile])
            profile_not_run = {
                test_id: not_run_reasons[test_id]
                for test_id in profile_inventory
                if test_id in not_run_reasons
            }
            category_profile_test_ids[category][profile] = sorted(
                set(profile_inventory) - set(profile_not_run)
            )
            category_profile_not_run[category][profile] = profile_not_run
            category_profile_unassigned_ids[category][profile] = sorted(
                set(ids) - set(profile_inventory)
            )

    for test_id, selector in selectors_by_id.items():
        category = selector["primary_category"]
        unassigned = not selector["runtime_profiles"]
        policy_not_run = test_id in category_not_run[category]
        if unassigned != policy_not_run:
            raise RegistryError(
                f"selector assignment and category NOT_RUN policy disagree: {test_id}"
            )

    regression = _exact_keys(
        categories["regression"],
        {"status", "test_ids", "not_run_reasons", "reason"},
        "categories.regression",
    )
    expected_regression = sorted(
        test_id
        for category in ("functional", "integration", "api", "e2e")
        for test_id in category_test_ids[category]
    )
    expected_regression_not_run = {
        selector: reason
        for category in ("functional", "integration", "api", "e2e")
        for selector, reason in category_not_run[category].items()
    }
    if (
        regression["status"] != "AGGREGATE"
        or regression["test_ids"] != expected_regression
        or regression["reason"] is not None
        or regression["not_run_reasons"] != expected_regression_not_run
    ):
        raise RegistryError("regression must exactly aggregate functional/integration/api/e2e IDs")
    category_test_ids["regression"] = expected_regression
    category_inventory_ids["regression"] = sorted(
        test_id
        for category in ("functional", "integration", "api", "e2e")
        for test_id in category_inventory_ids[category]
    )
    category_not_run["regression"] = expected_regression_not_run
    category_profile_test_ids["regression"] = {
        profile: sorted(
            test_id
            for category in ("functional", "integration", "api", "e2e")
            for test_id in category_profile_test_ids[category][profile]
        )
        for profile in RUNTIME_PROFILES
    }
    category_profile_not_run["regression"] = {
        profile: {
            test_id: reason
            for category in ("functional", "integration", "api", "e2e")
            for test_id, reason in category_profile_not_run[category][profile].items()
        }
        for profile in RUNTIME_PROFILES
    }
    category_profile_unassigned_ids["regression"] = {
        profile: sorted(
            test_id
            for category in ("functional", "integration", "api", "e2e")
            for test_id in category_profile_unassigned_ids[category][profile]
        )
        for profile in RUNTIME_PROFILES
    }

    aggregates = _exact_keys(data["aggregates"], {"regression_members"}, "aggregates")
    if aggregates["regression_members"] != ["functional", "integration", "api", "e2e"]:
        raise RegistryError("regression_members has an unsupported ordering or membership")
    unsupported = _exact_keys(data["unsupported_apis"], {"http"}, "unsupported_apis")
    http = _exact_keys(unsupported["http"], {"status", "reason", "evidence_paths"}, "unsupported_apis.http")
    if http["status"] != "UNSUPPORTED" or not isinstance(http["reason"], str) or not http["reason"].strip():
        raise RegistryError("HTTP API must remain explicitly UNSUPPORTED with a reason")
    evidence_paths = http["evidence_paths"]
    if not isinstance(evidence_paths, list) or not evidence_paths or any(not isinstance(path, str) for path in evidence_paths):
        raise RegistryError("HTTP API requires repository evidence paths")
    for path in evidence_paths:
        if not _read_repo_file(root, path):
            raise RegistryError(f"HTTP API evidence path is empty: {path}")

    if check_artifacts:
        artifact_stage = check_artifact_stage(root, artifacts)
    else:
        # The bounded runner appends one category's evidence at a time, so a
        # partial artifact set is its normal state; it never counts as evidence.
        artifact_stage = {
            "status": "NOT_CHECKED",
            "reason": "artifact stage skipped by the runner; not evidence of a passing run",
            "expected": 0,
            "present": 0,
        }

    return ValidatedRegistry(
        data=data,
        sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        candidate_head=head,
        selectors_by_id=selectors_by_id,
        category_test_ids=category_test_ids,
        category_inventory_ids=category_inventory_ids,
        category_not_run=category_not_run,
        category_profile_test_ids=category_profile_test_ids,
        category_profile_not_run=category_profile_not_run,
        category_profile_unassigned_ids=category_profile_unassigned_ids,
        artifact_stage=artifact_stage,
    )
