"""Stream an exact clean Git branch into a pre-provisioned isolated WSL root.

This module is a Windows-host preparation command. It sends a self-contained
Git bundle through ``wsl.exe`` stdin; it never mounts or opens a WSL filesystem
path from Windows. It does not create the destination root or provision WSL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path, PurePosixPath


MAX_STATUS_BYTES = 2 * 1024 * 1024
STATUS_TIMEOUT_SEC = 10
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024
TRANSFER_TIMEOUT_SEC = 300
_HEAD_RE = re.compile(r"[0-9a-f]{40}")
_BRANCH_RE = re.compile(r"[A-Za-z0-9._/-]{1,240}")
PINNED_DISTRIBUTION = "Ubuntu-24.04"

# Executed by the already-installed WSL Python. The destination root must
# exist and be owned by the requested unprivileged runner account.
_WSL_RECEIVER = r'''
import hashlib, json, os, pathlib, re, stat, subprocess, sys

root = pathlib.PurePosixPath(sys.argv[1])
run_id, expected_head, branch = sys.argv[2], sys.argv[3], sys.argv[4]
worker_gid, max_bytes = int(sys.argv[5]), int(sys.argv[6])
if not root.is_absolute() or ".." in root.parts or not re.fullmatch(r"[0-9a-f]{32}", run_id):
    raise SystemExit("invalid snapshot destination or run id")
if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
    raise SystemExit("invalid expected candidate head")
if not re.fullmatch(r"[A-Za-z0-9._/-]{1,240}", branch):
    raise SystemExit("invalid source branch")
if worker_gid < 1:
    raise SystemExit("invalid QA worker group")
root_path = pathlib.Path(str(root))
cursor = pathlib.Path("/")
for component in root.parts[1:]:
    cursor = cursor / component
    if cursor.is_symlink():
        raise SystemExit("snapshot root cannot traverse a symbolic link")
if root_path.is_symlink() or not root_path.is_dir():
    raise SystemExit("snapshot root must be a pre-provisioned real directory")
root_info = root_path.stat(follow_symlinks=False)
if (root_info.st_uid != os.geteuid() or root_info.st_gid != worker_gid or
        stat.S_IMODE(root_info.st_mode) != 0o2710):
    raise SystemExit("snapshot root must be runner-owned, worker-group mode 2710")
os.umask(0o027)
run_path = root_path / run_id
run_path.mkdir(mode=0o2710)
run_info = run_path.stat(follow_symlinks=False)
if run_info.st_uid != os.geteuid() or run_info.st_gid != worker_gid:
    raise SystemExit("snapshot run directory did not inherit the worker group")
if stat.S_IMODE(run_path.stat(follow_symlinks=False).st_mode) != 0o2710:
    raise SystemExit("snapshot run directory did not receive mode 2710")
bundle_part = run_path / "source.bundle.part"
bundle_path = run_path / "source.bundle"
repo_path = run_path / "repo"
flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
digest, total = hashlib.sha256(), 0
try:
    fd = os.open(bundle_part, flags, 0o600)
    with os.fdopen(fd, "wb") as output:
        while True:
            chunk = sys.stdin.buffer.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise SystemExit("source bundle exceeds the configured transfer limit")
            output.write(chunk)
            digest.update(chunk)
        output.flush()
        os.fsync(output.fileno())
    if total == 0:
        raise SystemExit("source bundle is empty")
    os.replace(bundle_part, bundle_path)
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(run_path),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }
    clone = subprocess.run(
        ["git", "-c", "init.templateDir=/dev/null", "clone", "--quiet", "--branch", branch,
         "--single-branch", str(bundle_path), str(repo_path)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        timeout=60, check=False, env=environment,
    )
    if clone.returncode != 0:
        raise SystemExit("Git could not clone the received bundle")
    for directory, subdirectories, filenames in os.walk(repo_path, followlinks=False):
        directory_path = pathlib.Path(directory)
        for name in subdirectories:
            child = directory_path / name
            if child.is_symlink():
                raise SystemExit("source snapshot contains a symbolic-link directory")
            os.chmod(child, 0o750)
            child_info = child.stat(follow_symlinks=False)
            if child_info.st_uid != os.geteuid() or child_info.st_gid != worker_gid:
                raise SystemExit("source snapshot directory has an unexpected owner or group")
        for name in filenames:
            child = directory_path / name
            if child.is_symlink():
                raise SystemExit("source snapshot contains a symbolic-link file")
            current_mode = stat.S_IMODE(child.stat(follow_symlinks=False).st_mode)
            os.chmod(child, (current_mode & 0o110) | 0o640)
            child_info = child.stat(follow_symlinks=False)
            if child_info.st_uid != os.geteuid() or child_info.st_gid != worker_gid:
                raise SystemExit("source snapshot file has an unexpected owner or group")
    # The repository root is runner-owned and worker-group-readable, but the
    # worker must not be able to create files there. setgid carries the worker
    # group to the private QA output subtree created later by tools.qa.run.
    os.chmod(repo_path, 0o2750)
    repo_info = repo_path.stat(follow_symlinks=False)
    if (repo_info.st_uid != os.geteuid() or repo_info.st_gid != worker_gid or
            stat.S_IMODE(repo_info.st_mode) != 0o2750):
        raise SystemExit("source snapshot repository has an unexpected owner or group")
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], cwd=repo_path,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=5, check=False, text=True, env=environment,
    )
    actual_head = head.stdout.strip()
    if head.returncode != 0 or actual_head != expected_head:
        raise SystemExit("received snapshot HEAD does not match the source candidate")
    print(json.dumps({
        "schema_version": 1,
        "run_id": run_id,
        "candidate_head": actual_head,
        "bundle_sha256": digest.hexdigest(),
        "bundle_bytes": total,
    }, sort_keys=True, separators=(",", ":")))
finally:
    try:
        bundle_part.unlink()
    except FileNotFoundError:
        pass
'''


def _git(root: Path, *args: str, timeout: int = 10, binary: bool = False):
    try:
        return subprocess.run(
            ["git", *args], cwd=root, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
            check=False, text=not binary,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Git command could not complete: {exc}") from exc


def _source_identity(root: Path) -> tuple[str, str]:
    try:
        status_process = subprocess.Popen(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise ValueError("cannot establish a bounded clean source worktree") from exc
    assert status_process.stdout is not None
    status_bytes = bytearray()

    def stop_status() -> None:
        try:
            status_process.kill()
        except OSError:
            pass

    status_timer = threading.Timer(STATUS_TIMEOUT_SEC, stop_status)
    status_timer.daemon = True
    status_timer.start()
    try:
        while True:
            chunk = status_process.stdout.read(64 * 1024)
            if not chunk:
                break
            if len(status_bytes) + len(chunk) > MAX_STATUS_BYTES:
                stop_status()
                status_process.wait()
                raise ValueError("source worktree status exceeds the bounded path limit")
            status_bytes.extend(chunk)
        status_code = status_process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        stop_status()
        status_process.wait()
        raise ValueError("source worktree status could not be collected within its time bound") from exc
    finally:
        status_timer.cancel()
        status_process.stdout.close()
    if status_code != 0:
        raise ValueError("cannot establish a bounded clean source worktree")
    if status_bytes:
        raise ValueError("source worktree must be clean; commit or safely resolve all changes first")
    head = _git(root, "rev-parse", "--verify", "HEAD")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if head.returncode != 0 or branch.returncode != 0:
        raise ValueError("source must be on a named branch with a valid HEAD")
    candidate_head, branch_name = head.stdout.strip(), branch.stdout.strip()
    if not _HEAD_RE.fullmatch(candidate_head) or not _BRANCH_RE.fullmatch(branch_name):
        raise ValueError("source candidate identity is malformed")
    ref_check = _git(root, "check-ref-format", "--branch", branch_name)
    if ref_check.returncode != 0:
        raise ValueError("source branch name is not a valid Git branch")
    return candidate_head, branch_name


def _drain_bounded(stream, limit: int) -> bytearray:
    """Drain to EOF while retaining only a bounded diagnostic/response prefix."""
    captured = bytearray()
    while True:
        chunk = stream.read(64 * 1024)
        if not chunk:
            break
        if len(captured) < limit:
            captured.extend(chunk[:limit - len(captured)])
    return captured


def transfer_snapshot(
    *, root: Path, distribution: str, wsl_user: str, worker_gid: int,
    snapshot_root: str,
) -> dict:
    """Transfer the current clean branch and verify the exact WSL clone HEAD."""
    if os.name != "nt":
        raise ValueError("snapshot transfer must be invoked from the Windows host")
    if distribution != PINNED_DISTRIBUTION:
        raise ValueError(f"distribution must be the named {PINNED_DISTRIBUTION} WSL distro")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", wsl_user):
        raise ValueError("WSL user must be an unprivileged account name")
    if not isinstance(worker_gid, int) or isinstance(worker_gid, bool) or worker_gid < 1:
        raise ValueError("worker_gid must be the dedicated positive POSIX group id")
    posix_root = PurePosixPath(snapshot_root)
    if (not posix_root.is_absolute() or str(posix_root) != snapshot_root or
            ".." in posix_root.parts or "\\" in snapshot_root or "\x00" in snapshot_root):
        raise ValueError("snapshot root must be a normalized absolute POSIX path")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source root is not a directory")
    candidate_head, branch = _source_identity(root)
    wsl_executable = shutil.which("wsl.exe")
    if not wsl_executable:
        raise ValueError("wsl.exe is unavailable on the Windows host")
    run_id = uuid.uuid4().hex
    command = [
        wsl_executable, "--distribution", distribution, "--user", wsl_user,
        "--cd", "/",
        "--exec", "python3", "-c", _WSL_RECEIVER,
        snapshot_root, run_id, candidate_head, branch, str(worker_gid),
        str(MAX_BUNDLE_BYTES),
    ]
    source = subprocess.Popen(
        ["git", "bundle", "create", "-", f"refs/heads/{branch}"], cwd=root,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert source.stdout is not None
    try:
        receiver = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as exc:
        source.kill()
        if source.stdout is not None:
            source.stdout.close()
        if source.stderr is not None:
            source.stderr.close()
        source.wait(timeout=5)
        raise ValueError("WSL snapshot receiver could not be started") from exc
    assert receiver.stdin is not None and receiver.stdout is not None and receiver.stderr is not None
    assert source.stderr is not None
    receiver_out = bytearray()
    receiver_err = bytearray()
    drain_threads = [
        threading.Thread(target=lambda: receiver_out.extend(_drain_bounded(receiver.stdout, MAX_RESPONSE_BYTES + 1))),
        threading.Thread(target=lambda: receiver_err.extend(_drain_bounded(receiver.stderr, MAX_RESPONSE_BYTES + 1))),
        threading.Thread(target=lambda: _drain_bounded(source.stderr, 0)),
    ]
    for thread in drain_threads:
        thread.start()
    bundle_digest = hashlib.sha256()
    bundle_bytes = 0
    timed_out = threading.Event()

    def terminate_transfer() -> None:
        timed_out.set()
        for process in (receiver, source):
            try:
                process.kill()
            except OSError:
                pass

    timeout_timer = threading.Timer(TRANSFER_TIMEOUT_SEC, terminate_transfer)
    timeout_timer.daemon = True
    timeout_timer.start()
    try:
        while True:
            chunk = source.stdout.read(1024 * 1024)
            if not chunk:
                break
            bundle_bytes += len(chunk)
            if bundle_bytes > MAX_BUNDLE_BYTES:
                raise ValueError("source bundle exceeds the configured transfer limit")
            bundle_digest.update(chunk)
            receiver.stdin.write(chunk)
        receiver.stdin.close()
        source.stdout.close()
        source.wait(timeout=TRANSFER_TIMEOUT_SEC)
        receiver.wait(timeout=TRANSFER_TIMEOUT_SEC)
    except (BrokenPipeError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
        if isinstance(exc, BrokenPipeError):
            # Preserve the receiver's bounded diagnostic before deciding whether
            # the transport itself or receiver validation closed the pipe.
            try:
                receiver.stdin.close()
            except OSError:
                pass
            try:
                source.kill()
            except OSError:
                pass
            if source.stdout is not None:
                source.stdout.close()
            source.wait(timeout=5)
            try:
                receiver.wait(timeout=5)
            except subprocess.TimeoutExpired:
                receiver.kill()
                receiver.wait(timeout=5)
            for thread in drain_threads:
                thread.join(timeout=5)
            if any(thread.is_alive() for thread in drain_threads):
                reason = "WSL receiver closed the stream; diagnostic capture timed out"
            else:
                reason = receiver_err.decode("utf-8", errors="replace").strip()
                reason = reason.replace(snapshot_root, "[snapshot-root]")
                reason = reason.replace(wsl_user, "[runner]")
                reason = reason.replace(str(worker_gid), "[worker-gid]")
                reason = reason or "WSL receiver closed the bundle stream"
        else:
            terminate_transfer()
            receiver.wait(timeout=5)
            source.wait(timeout=5)
            reason = (
                "WSL snapshot transfer timed out"
                if isinstance(exc, subprocess.TimeoutExpired)
                else str(exc) or "WSL snapshot receiver closed the transfer stream"
            )
        raise ValueError(reason) from exc
    finally:
        timeout_timer.cancel()
        for thread in drain_threads:
            thread.join(timeout=TRANSFER_TIMEOUT_SEC)
    if timed_out.is_set():
        raise ValueError("WSL snapshot transfer timed out")
    if any(thread.is_alive() for thread in drain_threads):
        raise ValueError("snapshot transfer output capture did not complete")
    if len(receiver_out) > MAX_RESPONSE_BYTES or len(receiver_err) > MAX_RESPONSE_BYTES:
        raise ValueError("snapshot transfer response exceeded its bound")
    if source.returncode != 0:
        raise ValueError("Git could not create the source bundle")
    if receiver.returncode != 0:
        # Preserve only a bounded diagnostic category, never echo host paths.
        reason = receiver_err.decode("utf-8", errors="replace").strip()
        raise ValueError(f"WSL snapshot transfer failed: {reason[:512] or 'receiver exited nonzero'}")
    try:
        response = json.loads(receiver_out.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("WSL snapshot receiver returned malformed metadata") from exc
    if (not isinstance(response, dict) or set(response) != {
            "schema_version", "run_id", "candidate_head", "bundle_sha256", "bundle_bytes"} or
            not isinstance(response["schema_version"], int) or isinstance(response["schema_version"], bool) or
            response["schema_version"] != 1 or response["run_id"] != run_id or
            response["candidate_head"] != candidate_head or
            not re.fullmatch(r"[0-9a-f]{64}", str(response["bundle_sha256"])) or
            not isinstance(response["bundle_bytes"], int) or isinstance(response["bundle_bytes"], bool) or
            response["bundle_bytes"] != bundle_bytes or response["bundle_bytes"] <= 0 or
            response["bundle_bytes"] > MAX_BUNDLE_BYTES or
            response["bundle_sha256"] != bundle_digest.hexdigest()):
        raise ValueError("WSL snapshot receiver metadata failed validation")
    return response


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="clean committed Windows checkout root")
    parser.add_argument("--distribution", required=True, help="explicit WSL distribution name")
    parser.add_argument("--wsl-user", required=True, help="unprivileged WSL runner account")
    parser.add_argument("--worker-gid", required=True, type=int, help="dedicated POSIX QA worker group id")
    parser.add_argument("--snapshot-root", required=True, help="pre-provisioned private POSIX destination root")
    args = parser.parse_args(argv)
    try:
        result = transfer_snapshot(
            root=Path(args.cwd), distribution=args.distribution,
            wsl_user=args.wsl_user, worker_gid=args.worker_gid,
            snapshot_root=args.snapshot_root,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"schema_version": 1, "state": "BLOCKED", "reason": str(exc)[:512]},
                         sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps({"schema_version": 1, "state": "TRANSFERRED", **result},
                     sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
