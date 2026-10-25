"""Bounded native pytest runner for the S4 category manifest."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import ntpath
import json
import os
import platform
import re
import socket
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
from .dependencies import (
    DependencyProvenanceError,
    locked_wheel_manifest,
    verify_dependency_environment,
)
from .registry import (
    RegistryError,
    RUNTIME_PROFILES,
    WINDOWS_PROFILE,
    WSL_PROFILE,
    WSL_ROOT_PROFILE,
    ValidatedRegistry,
    git_head,
    git_root,
    validate_registry,
)
from .report import canonical_lock_bytes, encode_report, sha256_bytes


MAX_TIMEOUT_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 900
MAX_CAPTURE_BYTES = 4 * 1024 * 1024
EXPECTED_PYTHON_EXE = r"C:\Python314\python.exe"
EXPECTED_WSL_PYTHON_EXE = "/usr/bin/python3.12"
ROOT_HARNESS_CAP_MASK = (1 << 0) | (1 << 6) | (1 << 7)  # CHOWN, SETGID, SETUID only.
ROOT_HARNESS_PROOF_AUTHORITY = "local-qa-preflight-non-authoritative"
ROOT_HARNESS_PROOF_VERSION = 4
ROOT_HARNESS_REPORT_SCOPE = (
    "local QA preflight only; not an S2 worker receipt or independent approval"
)
WSL_CANDIDATE_ROOT = Path("/tmp/vst-s4-candidate")
MAX_MOUNTINFO_BYTES = 4 * 1024 * 1024
ROOT_HARNESS_PROOF_FIELDS = {
    "schema_version", "authority", "run_id", "run_nonce", "candidate_head",
    "runtime_profile", "distribution_id", "distribution_version_id", "kernel_release", "uid", "gid",
    "supplementary_groups", "capability_mask", "automount_enabled",
    "interop_enabled", "private_network", "default_deny_egress",
    "external_canary_blocked", "loopback_canary_passed", "candidate_root",
    "mountinfo_sha256", "parent_network_namespace_inode", "helper_sha256",
}
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_RELATIVE = re.compile(r"[A-Za-z0-9_./-]+\Z")
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
    parser.add_argument("--dependency-target", required=True)
    parser.add_argument("--dependency-wheelhouse", required=True)
    parser.add_argument("--scratch-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output-cap-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--privileged-harness-proof")
    parser.add_argument("--run-nonce")
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
    args._dependency_target = Path(args.dependency_target).resolve(strict=False)
    args._dependency_wheelhouse = Path(args.dependency_wheelhouse).resolve(strict=False)
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
    } | {"docs/sdlc/evidence/qa/matrix.report.jsonl"}


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


def _wsl_distro_identity() -> tuple[bool, str, str]:
    if platform.system() != "Linux":
        return False, "", ""
    try:
        release = platform.freedesktop_os_release()
        kernel = platform.release()
        config = configparser.ConfigParser()
        with Path("/etc/wsl.conf").open(encoding="utf-8") as handle:
            config.read_file(handle)
        valid = (
            release.get("ID") == "ubuntu"
            and release.get("VERSION_ID") == "24.04"
            and "microsoft" in kernel.lower()
            and config.getboolean("automount", "enabled") is False
            and config.getboolean("interop", "enabled") is False
        )
        return valid, release.get("PRETTY_NAME", ""), kernel
    except (OSError, configparser.Error, ValueError):
        return False, "", ""


def _linux_capability_masks() -> tuple[int | None, int | None]:
    try:
        status = Path("/proc/self/status").read_text(encoding="ascii")
    except (OSError, UnicodeError):
        return None, None
    values: dict[str, int] = {}
    for line in status.splitlines():
        key, separator, raw = line.partition(":")
        if separator and key in {"CapEff", "CapBnd"}:
            try:
                values[key] = int(raw.strip(), 16)
            except ValueError:
                return None, None
    return values.get("CapEff"), values.get("CapBnd")


def _private_network_namespace(parent_namespace_inode: int | None = None) -> bool:
    """Compare against the parent namespace inode captured before capability drop."""
    if (
        not isinstance(parent_namespace_inode, int)
        or isinstance(parent_namespace_inode, bool)
        or parent_namespace_inode <= 0
    ):
        return False
    try:
        current = os.stat("/proc/self/ns/net").st_ino
    except OSError:
        return False
    return current != parent_namespace_inode


def _loopback_only_network() -> bool:
    """Prove that a root harness has no non-loopback interface to reach external networks."""
    try:
        interfaces = socket.if_nameindex()
    except OSError:
        return False
    return len(interfaces) == 1 and interfaces[0][1] == "lo"


def _loopback_canary_passed() -> bool:
    """Exercise an ephemeral in-process loopback listener without external network access."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.settimeout(1.0)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            with socket.create_connection(listener.getsockname(), timeout=1.0):
                connection, _ = listener.accept()
                connection.close()
        return True
    except OSError:
        return False


def _wsl_candidate_boundary(root: Path, profile: str | None) -> dict[str, Any] | None:
    if profile not in {WSL_PROFILE, WSL_ROOT_PROFILE}:
        return None
    candidate = root.resolve(strict=True)
    if WSL_CANDIDATE_ROOT.is_symlink():
        raise QARunError("WSL candidate test root cannot be a symbolic link")
    local_root = WSL_CANDIDATE_ROOT.resolve(strict=True)
    if local_root != WSL_CANDIDATE_ROOT:
        raise QARunError("WSL candidate test root must be the canonical distro-local path")
    if not candidate.is_relative_to(local_root):
        raise QARunError("WSL candidate root must resolve beneath /tmp/vst-s4-candidate")
    try:
        raw = Path("/proc/self/mountinfo").read_bytes()
    except OSError as exc:
        raise QARunError(f"WSL mount table is unavailable ({type(exc).__name__})") from None
    if not raw or len(raw) > MAX_MOUNTINFO_BYTES:
        raise QARunError("WSL mount table is empty or exceeds the inspection bound")
    def decode_mount_path(value: bytes) -> str:
        return (
            value.replace(b"\\134", b"\\")
            .replace(b"\\040", b" ")
            .replace(b"\\011", b"\t")
            .replace(b"\\012", b"\n")
            .decode("utf-8", errors="strict")
        )

    for line in raw.splitlines():
        left, separator, right = line.partition(b" - ")
        left_fields = left.split()
        right_fields = right.split()
        if not separator or len(left_fields) < 6 or len(right_fields) < 3:
            raise QARunError("WSL mount table contains a malformed entry")
        filesystem = right_fields[0].lower()
        source = right_fields[1].lower()
        windows_drive_source = bool(re.match(rb"^[a-z]:", source))
        try:
            mountpoint = decode_mount_path(left_fields[4])
        except UnicodeError:
            raise QARunError("WSL mount table contains an invalid mount path") from None
        candidate_path = candidate.as_posix()
        mount_intersects_candidate = (
            mountpoint == "/"
            or candidate_path == mountpoint.rstrip("/")
            or candidate_path.startswith(mountpoint.rstrip("/") + "/")
            or mountpoint == candidate_path
            or mountpoint.startswith(candidate_path.rstrip("/") + "/")
        )
        if (
            filesystem == b"drvfs"
            or b"drvfs" in source
            or windows_drive_source
            or (
                mount_intersects_candidate
                and (filesystem == b"9p" or b"9p" in source)
            )
        ):
            raise QARunError("WSL mount table contains a Windows-drive drvfs/9p mount")
    return {
        "candidate_root": candidate.as_posix(),
        "candidate_root_prefix": WSL_CANDIDATE_ROOT.as_posix(),
        "mountinfo_sha256": hashlib.sha256(raw).hexdigest(),
        "windows_drive_mounts_present": False,
    }


def _runtime_profile() -> str | None:
    if (
        os.name == "nt"
        and platform.system() == "Windows"
        and platform.python_implementation() == "CPython"
        and platform.python_version() == "3.14.3"
        and _canonical_interpreter_matches(WINDOWS_PROFILE)
    ):
        return WINDOWS_PROFILE
    wsl, _, _ = _wsl_distro_identity()
    if (
        not wsl
        or platform.python_implementation() != "CPython"
        or platform.python_version() != "3.12.3"
        or not _canonical_interpreter_matches(WSL_PROFILE)
    ):
        return None
    try:
        uid = os.geteuid()
        gid = os.getegid()
        groups = sorted(os.getgroups())
    except AttributeError:
        return None
    if uid == 997 and gid == 988 and groups == []:
        return WSL_PROFILE
    effective, bounding = _linux_capability_masks()
    if (
        uid == 0
        and gid == 0
        and groups == []
        and effective == ROOT_HARNESS_CAP_MASK
        and bounding == ROOT_HARNESS_CAP_MASK
    ):
        return WSL_ROOT_PROFILE
    return None


def _canonical_interpreter_matches(profile: str) -> bool:
    if profile == WINDOWS_PROFILE:
        actual = ntpath.normcase(ntpath.normpath(os.path.realpath(sys.executable)))
        expected = ntpath.normcase(ntpath.normpath(EXPECTED_PYTHON_EXE))
        return actual == expected
    if profile in {WSL_PROFILE, WSL_ROOT_PROFILE}:
        return os.path.realpath(sys.executable) == EXPECTED_WSL_PYTHON_EXE
    return False


def _runtime_report_identity(profile: str | None) -> dict[str, Any]:
    if profile == WINDOWS_PROFILE:
        return {
            "runtime_profile": profile,
            "interpreter": {
                "id": "CPython-3.14.3",
                "executable": "C:/Python314/python.exe",
                "version": "3.14.3",
            },
            "runtime_identity": {"uid": None, "gid": None, "supplementary_groups": []},
        }
    if profile in {WSL_PROFILE, WSL_ROOT_PROFILE}:
        groups = sorted(os.getgroups())
        return {
            "runtime_profile": profile,
            "interpreter": {
                "id": "CPython-3.12.3",
                "executable": EXPECTED_WSL_PYTHON_EXE,
                "version": "3.12.3",
            },
            "runtime_identity": {
                "uid": os.geteuid(),
                "gid": os.getegid(),
                "supplementary_groups": groups,
            },
        }
    return {
        "runtime_profile": None,
        "interpreter": {
            "id": f"{platform.python_implementation()}-{platform.python_version()}",
            "executable": None,
            "version": platform.python_version(),
        },
        "runtime_identity": {"uid": None, "gid": None, "supplementary_groups": []},
    }


def _validate_privileged_harness_proof(
    args: argparse.Namespace,
    root: Path,
    head: str,
    profile: str | None,
    boundary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    proof_arg = args.privileged_harness_proof
    nonce = args.run_nonce
    if profile != WSL_ROOT_PROFILE:
        if proof_arg is not None or nonce is not None:
            raise QARunError("privileged harness proof is valid only for the WSL root profile")
        return None
    if boundary is None:
        raise QARunError("WSL root profile lacks a validated distro-local candidate boundary")
    if proof_arg is None or nonce is None or _HEX64.fullmatch(nonce) is None:
        raise QARunError("WSL root profile requires a run nonce and privileged harness proof")
    if args.expected_head != head:
        raise QARunError("WSL root profile requires --expected-head bound to the current candidate")
    proof_path = Path(proof_arg)
    if not proof_path.is_absolute():
        raise QARunError("privileged harness proof must use an absolute external path")
    try:
        if proof_path.is_symlink():
            raise QARunError("privileged harness proof cannot be a symbolic link")
        resolved = proof_path.resolve(strict=True)
        if resolved.is_relative_to(root):
            raise QARunError("privileged harness proof must be outside the candidate repository")
        info = resolved.stat()
        if not resolved.is_file() or info.st_nlink != 1 or info.st_size > 16 * 1024:
            raise QARunError("privileged harness proof must be a small regular external file")
        proof_bytes = resolved.read_bytes()
        proof = json.loads(proof_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QARunError(f"privileged harness proof is unavailable or invalid ({type(exc).__name__})") from None
    if not isinstance(proof, dict) or set(proof) != ROOT_HARNESS_PROOF_FIELDS:
        raise QARunError("privileged harness proof has an invalid exact schema")
    distribution_ok, _, kernel = _wsl_distro_identity()
    effective, bounding = _linux_capability_masks()
    parent_namespace_inode = proof.get("parent_network_namespace_inode")
    helper_path = root / "tools" / "qa" / "root_harness.py"
    helper_sha256 = hashlib.sha256(helper_path.read_bytes()).hexdigest()
    supplied_helper_sha256 = proof.get("helper_sha256")
    isolated_network = _private_network_namespace(parent_namespace_inode) and _loopback_only_network()
    loopback_canary_passed = _loopback_canary_passed()
    expected_values = {
        "schema_version": ROOT_HARNESS_PROOF_VERSION,
        "authority": ROOT_HARNESS_PROOF_AUTHORITY,
        "run_id": args.run_id,
        "run_nonce": nonce,
        "candidate_head": head,
        "runtime_profile": WSL_ROOT_PROFILE,
        "distribution_id": "ubuntu",
        "distribution_version_id": "24.04",
        "kernel_release": kernel,
        "uid": 0,
        "gid": 0,
        "supplementary_groups": [],
        "capability_mask": f"0x{ROOT_HARNESS_CAP_MASK:x}",
        "automount_enabled": False,
        "interop_enabled": False,
        "private_network": isolated_network,
        "default_deny_egress": isolated_network,
        "external_canary_blocked": isolated_network,
        "loopback_canary_passed": loopback_canary_passed,
        "candidate_root": boundary["candidate_root"] if boundary else None,
        "mountinfo_sha256": boundary["mountinfo_sha256"] if boundary else None,
        "parent_network_namespace_inode": parent_namespace_inode,
        "helper_sha256": helper_sha256,
    }
    if (
        not distribution_ok
        or os.geteuid() != 0
        or os.getegid() != 0
        or sorted(os.getgroups()) != []
        or effective != ROOT_HARNESS_CAP_MASK
        or bounding != ROOT_HARNESS_CAP_MASK
        or not isolated_network
        or not loopback_canary_passed
        or proof != expected_values
    ):
        raise QARunError("privileged harness proof does not match this process, candidate, or WSL boundary")
    return {
        "authority": ROOT_HARNESS_PROOF_AUTHORITY,
        "scope": ROOT_HARNESS_REPORT_SCOPE,
        "sha256": hashlib.sha256(proof_bytes).hexdigest(),
        "run_nonce_sha256": hashlib.sha256(nonce.encode("ascii")).hexdigest(),
        "parent_network_namespace_inode": parent_namespace_inode,
        "helper_sha256": supplied_helper_sha256,
        "candidate_root": boundary["candidate_root"],
        "mountinfo_sha256": boundary["mountinfo_sha256"],
    }


def _lock_versions(root: Path) -> tuple[str, dict[str, str]]:
    lock_path = root / "tools" / "qa" / "requirements.lock"
    try:
        raw = lock_path.read_bytes()
    except OSError as exc:
        raise QARunError(f"QA dependency lock is missing ({type(exc).__name__})") from None
    canonical_lock = canonical_lock_bytes(raw)
    if b"\r" in canonical_lock:
        raise QARunError("QA dependency lock contains unsupported bare carriage returns")
    try:
        platform_name = "win32" if os.name == "nt" else "linux"
        versions = {
            row["name"]: row["version"]
            for row in locked_wheel_manifest(lock_path, platform_name)
        }
    except DependencyProvenanceError as exc:
        raise QARunError(str(exc)) from None
    return hashlib.sha256(canonical_lock).hexdigest(), versions


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
    runtime_profile = getattr(args, "_runtime_profile", None)
    runtime_fields = _runtime_report_identity(runtime_profile)
    not_run_reasons = registry.category_not_run.get(args.category, {}) if registry else {}
    if registry is not None and runtime_profile in RUNTIME_PROFILES:
        expected_ids = registry.category_profile_test_ids.get(args.category, {}).get(runtime_profile, [])
        unassigned_ids = registry.category_profile_unassigned_ids.get(args.category, {}).get(runtime_profile, [])
        unassigned_ids = [test_id for test_id in unassigned_ids if test_id not in not_run_reasons]
    else:
        expected_ids = []
        unassigned_ids = [
            test_id for test_id in registry.category_inventory_ids.get(args.category, [])
            if test_id not in not_run_reasons
        ] if registry else []
    return {
        "schema_version": 3,
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
        "expected_test_ids": expected_ids,
        "inventory_test_ids": registry.category_inventory_ids.get(args.category, []) if registry else [],
        "unassigned_test_ids": unassigned_ids,
        "not_run_test_reasons": not_run_reasons,
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
        "runtime_profile": runtime_fields["runtime_profile"],
        "interpreter": runtime_fields["interpreter"],
        "runtime_identity": runtime_fields["runtime_identity"],
        "runtime_boundary": getattr(args, "_runtime_boundary", None),
        "privileged_harness_preflight": getattr(args, "_privileged_harness_preflight", None),
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
        "dependency_execution_integrity": "NOT_VERIFIED",
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
    selectors: dict[str, dict[str, Any]],
    scratch_run: Path,
    repo_root: Path,
    dependency_target: Path,
) -> tuple[list[str], dict[str, str]]:
    if not expected_ids:
        raise QARunError("pytest cannot be invoked with an empty registered selector set")
    selection_path = scratch_run / "selection.json"
    events_path = scratch_run / "events.json"
    expected_selectors = {test_id: selectors[test_id]["selector"] for test_id in expected_ids}
    known_selectors = {test_id: row["selector"] for test_id, row in selectors.items()}
    source_paths = sorted({selector.split("::", 1)[0] for selector in expected_selectors.values()})
    selection = {
        "schema_version": 2,
        "expected_selectors": expected_selectors,
        "known_selectors": known_selectors,
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
        "--tb=short",
        "--disable-warnings",
        "--show-capture=no",
        "--color=no",
        "-p",
        "tools.qa.pytest_plugin",
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
    env["PYTHONPATH"] = os.fspath(dependency_target)
    temp_root = os.fspath(scratch_run)
    env["TEMP"] = temp_root
    env["TMP"] = temp_root
    env["TMPDIR"] = temp_root
    return argv, env


def _normalized_command(argv: list[str], scratch_run: Path) -> list[str]:
    result: list[str] = []
    python_token = (
        "<approved-python-base>/python.exe"
        if os.name == "nt"
        else "<approved-python-base>/python3.12"
    )
    for argument in argv:
        if argument == sys.executable:
            result.append(python_token)
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
        args._output_paths = output_paths
        head = git_head(root)
        args._runtime_boundary = _wsl_candidate_boundary(root, args._runtime_profile)
        if args.expected_head is not None and args.expected_head != head:
            raise QARunError("candidate HEAD does not match --expected-head")
        args._privileged_harness_preflight = _validate_privileged_harness_proof(
            args, root, head, args._runtime_profile, args._runtime_boundary
        )
        before_paths = _git_status_paths(root)
        registry = validate_registry(root, args.manifest)
        report = _report_base(
            args=args,
            root=root,
            registry=registry,
            candidate_head=head,
            before_paths=before_paths,
        )
        dependency_target: Path = args._dependency_target
        if (
            Path(args.dependency_target).is_symlink()
            or getattr(Path(args.dependency_target), "is_junction", lambda: False)()
            or not dependency_target.is_dir()
            or dependency_target.is_relative_to(root)
        ):
            raise QARunError("dependency-target must be an existing directory outside the candidate repository")
        wheelhouse: Path = args._dependency_wheelhouse
        if (
            Path(args.dependency_wheelhouse).is_symlink()
            or getattr(Path(args.dependency_wheelhouse), "is_junction", lambda: False)()
            or not wheelhouse.is_dir()
            or wheelhouse.is_relative_to(root)
            or wheelhouse == dependency_target
            or wheelhouse.is_relative_to(dependency_target)
            or dependency_target.is_relative_to(wheelhouse)
        ):
            raise QARunError("dependency-wheelhouse must be an existing directory outside the candidate and target")
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
        try:
            dependency_evidence = verify_dependency_environment(
                root / "tools" / "qa" / "requirements.lock", dependency_target, wheelhouse
            )
        except DependencyProvenanceError as exc:
            raise QARunError(f"locked QA dependency content verification failed: {exc}") from None
        report["lock_sha256"] = dependency_evidence["lock_sha256"]
        report["dependency_wheels"] = dependency_evidence["wheels"]
        report["dependency_target_sha256"] = dependency_evidence["target_sha256"]
        report["dependency_content_verified_before"] = True
        sys.path.insert(0, os.fspath(dependency_target))
        actual_versions = dependency_evidence["versions"]
        missing_versions: list[str] = []
        report["dependency_versions"] = actual_versions
        report["pytest_version"] = actual_versions.get("pytest")
        if report["pytest_version"] is None:
            missing_versions.append("pytest")
        reasons: list[str] = []
        if args._runtime_profile is None:
            reasons.append("runner process does not match an approved runtime profile and identity")
        if missing_versions:
            reasons.append("locked QA dependencies are missing or mismatched: " + ", ".join(sorted(missing_versions)))
        if _unexpected_candidate_paths(before_paths):
            reasons.append("candidate worktree has unrelated changes before execution")
        if args.category not in registry.category_test_ids:
            reasons.append(f"unknown category: {args.category}")
        profile = args._runtime_profile
        policy_not_run = registry.category_not_run.get(args.category, {})

        category_status = registry.data["categories"].get(args.category, {}).get("status")
        category_reason = registry.data["categories"].get(args.category, {}).get("reason")
        base_result, base_reasons = _base_status(category_status, args.category, category_reason)
        if base_result != "PASS":
            report["result"] = base_result
            report["dependency_target_sha256_after"] = dependency_evidence["target_sha256"]
            report["dependency_content_verified_after"] = True
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

        expected_ids = registry.category_profile_test_ids[args.category].get(profile, [])
        if not expected_ids:
            raise QARunError("category has no runnable selectors assigned to this runtime profile")
        selectors = registry.selectors_by_id
        scratch_run = _run_id_dir(scratch_root, args.run_id)
        argv, child_env = _pytest_command(
            expected_ids=expected_ids,
            selectors=selectors,
            scratch_run=scratch_run,
            repo_root=root,
            dependency_target=dependency_target,
        )
        if _wsl_candidate_boundary(root, profile) != args._runtime_boundary:
            raise QARunError("WSL candidate mount boundary changed before test execution")
        # Command evidence uses normalized temporary-root tokens to avoid writing
        # absolute host paths into a public repository report.
        report["command"] = _normalized_command(argv, scratch_run)
        try:
            final_preflight = verify_dependency_environment(
                root / "tools" / "qa" / "requirements.lock", dependency_target, wheelhouse
            )
        except DependencyProvenanceError as exc:
            raise QARunError(f"locked QA dependency changed while preparing pytest ({type(exc).__name__})") from None
        if (
            final_preflight["lock_sha256"] != dependency_evidence["lock_sha256"]
            or final_preflight["wheels"] != dependency_evidence["wheels"]
            or final_preflight["target_sha256"] != dependency_evidence["target_sha256"]
        ):
            raise QARunError("QA dependency provenance changed while preparing pytest")
        dependency_evidence = final_preflight
        started = time.monotonic()
        exit_code, stdout_raw, stderr_raw, capture = _run_bounded(
            argv,
            cwd=root,
            timeout=args.timeout_seconds,
            cap=args.output_cap_bytes,
            env=child_env,
        )
        duration = round(time.monotonic() - started, 3)
        if profile in {WSL_PROFILE, WSL_ROOT_PROFILE}:
            try:
                boundary_after = _wsl_candidate_boundary(root, profile)
            except (QARunError, OSError):
                reasons.append("WSL candidate mount boundary became invalid during test execution")
            else:
                if boundary_after != args._runtime_boundary:
                    reasons.append("WSL candidate mount boundary changed during test execution")
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

        try:
            dependency_after = verify_dependency_environment(
                root / "tools" / "qa" / "requirements.lock", dependency_target, wheelhouse
            )
        except DependencyProvenanceError:
            reasons.append("QA dependency target or wheelhouse changed during test execution")
        else:
            report["dependency_target_sha256_after"] = dependency_after["target_sha256"]
            report["dependency_content_verified_after"] = True
            if (
                dependency_after["lock_sha256"] != dependency_evidence["lock_sha256"]
                or dependency_after["wheels"] != dependency_evidence["wheels"]
                or dependency_after["target_sha256"] != dependency_evidence["target_sha256"]
            ):
                reasons.append("QA dependency provenance changed during test execution")

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
        if policy_not_run:
            reasons.append(policy_reason)
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

        # Do not persist an approving result until the final candidate-state
        # query has succeeded. If that query fails, the exception handler writes
        # a durable BLOCKED record instead of leaving a report that says PASS.
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
        DependencyProvenanceError,
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
