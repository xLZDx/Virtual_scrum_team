"""Launch the S4 WSL root QA profile inside a restricted network namespace."""

from __future__ import annotations

import argparse
import configparser
import json
import hashlib
import os
import platform
import re
import secrets
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


PROFILE = "wsl-ubuntu-24.04-root-harness"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
MAX_TIMEOUT_SECONDS = 3600
MAX_OUTPUT_CAP_BYTES = 4 * 1024 * 1024
INSTALLED_HELPER = Path("/usr/local/libexec/vst-s4-root-harness.py")
PYTHON = "/usr/bin/python3.12"
UNSHARE = "/usr/bin/unshare"
IP = "/usr/sbin/ip"
SETPRIV = "/usr/bin/setpriv"
GIT = "/usr/bin/git"
WSL_CANDIDATE_ROOT = Path("/tmp/vst-s4-candidate")
MINIMAL_ENV = {
    "GIT_CONFIG_COUNT": "0",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/root",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "TMPDIR": "/tmp",
}


def _distribution() -> bool:
    try:
        release = platform.freedesktop_os_release()
        config = configparser.ConfigParser()
        with open("/etc/wsl.conf", encoding="utf-8") as handle:
            config.read_file(handle)
        return (
            platform.system() == "Linux"
            and "microsoft" in platform.release().lower()
            and release.get("ID") == "ubuntu"
            and release.get("VERSION_ID") == "24.04"
            and config.getboolean("automount", "enabled") is False
            and config.getboolean("interop", "enabled") is False
        )
    except (OSError, configparser.Error, ValueError):
        return False


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument(
        "--category",
        required=True,
        choices=("functional", "integration", "api", "e2e", "regression", "seeded-failure"),
    )
    parser.add_argument("--dependency-target", required=True)
    parser.add_argument("--scratch-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--report-path", required=True)
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--stderr-path", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--output-cap-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--parent-ns-fd", type=int, help=argparse.SUPPRESS)
    return parser.parse_args()


def _trusted_installed_helper() -> bool:
    try:
        path = Path(__file__).resolve(strict=True)
        info = path.stat()
        parent = INSTALLED_HELPER.parent.stat()
        return (
            path == INSTALLED_HELPER
            and stat.S_ISREG(info.st_mode)
            and info.st_uid == 0
            and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            and parent.st_uid == 0
            and not parent.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        )
    except OSError:
        return False


def _candidate_boundary(repo: Path) -> dict[str, str]:
    if WSL_CANDIDATE_ROOT.is_symlink():
        raise SystemExit("WSL candidate test root cannot be a symbolic link")
    local_root = WSL_CANDIDATE_ROOT.resolve(strict=True)
    if local_root != WSL_CANDIDATE_ROOT:
        raise SystemExit("WSL candidate test root must be the canonical distro-local path")
    candidate = repo.resolve(strict=True)
    if not candidate.is_relative_to(local_root):
        raise SystemExit("candidate root must resolve beneath /tmp/vst-s4-candidate")
    try:
        raw = Path("/proc/self/mountinfo").read_bytes()
    except OSError:
        raise SystemExit("WSL mount table is unavailable") from None
    if not raw or len(raw) > 4 * 1024 * 1024:
        raise SystemExit("WSL mount table is empty or exceeds the inspection bound")

    def decode(value: bytes) -> str:
        return (value.replace(b"\\134", b"\\").replace(b"\\040", b" ")
                .replace(b"\\011", b"\t").replace(b"\\012", b"\n").decode("utf-8", errors="strict"))

    candidate_path = candidate.as_posix()
    for line in raw.splitlines():
        left, separator, right = line.partition(b" - ")
        left_fields, right_fields = left.split(), right.split()
        if not separator or len(left_fields) < 6 or len(right_fields) < 3:
            raise SystemExit("WSL mount table contains a malformed entry")
        filesystem, source = right_fields[0].lower(), right_fields[1].lower()
        try:
            mountpoint = decode(left_fields[4])
        except UnicodeError:
            raise SystemExit("WSL mount table contains an invalid mount path") from None
        intersects = (mountpoint == "/" or candidate_path == mountpoint.rstrip("/")
                      or candidate_path.startswith(mountpoint.rstrip("/") + "/")
                      or mountpoint.startswith(candidate_path.rstrip("/") + "/"))
        windows_drive = bool(re.match(rb"^[a-z]:", source))
        if (filesystem == b"drvfs" or b"drvfs" in source or windows_drive
                or (intersects and (filesystem == b"9p" or b"9p" in source))):
            raise SystemExit("WSL mount table contains a Windows-drive drvfs/9p mount")
    return {"candidate_root": candidate_path, "mountinfo_sha256": hashlib.sha256(raw).hexdigest()}


def _git_head(repo: Path) -> str:
    result = subprocess.run([GIT, "-c", "safe.directory=", "-c", f"safe.directory={repo}",
                             "-C", str(repo), "rev-parse", "--verify", "HEAD"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=True, shell=False,
                            env=MINIMAL_ENV)
    head = result.stdout.decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise SystemExit("git returned an invalid candidate HEAD")
    return head


def _loopback_canary_passed() -> bool:
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


def _main() -> int:
    if not sys.flags.isolated:
        raise SystemExit("root harness requires isolated Python startup (-I)")
    args = _args()
    if not RUN_ID.fullmatch(args.run_id):
        raise SystemExit("run-id is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_head):
        raise SystemExit("expected-head must be a full lowercase Git commit id")
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise SystemExit("timeout-seconds is outside the supported bound")
    if not 1 <= args.output_cap_bytes <= MAX_OUTPUT_CAP_BYTES:
        raise SystemExit("output-cap-bytes is outside the supported bound")
    if not _distribution():
        raise SystemExit("root harness requires Ubuntu 24.04 under WSL with automount and interop disabled")
    if not _trusted_installed_helper():
        raise SystemExit("privileged root harness must be the root-owned installed helper at /usr/local/libexec/vst-s4-root-harness.py")
    repo = Path(args.repo_root).resolve(strict=True)
    installed_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    candidate_helper = repo / "tools" / "qa" / "root_harness.py"
    try:
        candidate_digest = hashlib.sha256(candidate_helper.read_bytes()).hexdigest()
    except OSError:
        raise SystemExit("candidate root harness source is unavailable") from None
    if installed_digest != candidate_digest:
        raise SystemExit("installed root harness does not match candidate source")
    if args.parent_ns_fd is None:
        if os.geteuid() != 0:
            raise SystemExit("root harness must be invoked as root")
        if _git_head(repo) != args.expected_head:
            raise SystemExit("candidate HEAD does not match --expected-head")
        namespace_fd = os.open("/proc/self/ns/net", os.O_RDONLY | os.O_CLOEXEC)
        command = [UNSHARE, "--net", "--", PYTHON, "-I", str(INSTALLED_HELPER),
                   *sys.argv[1:], "--parent-ns-fd", str(namespace_fd)]
        try:
            return subprocess.run(command, cwd=repo, check=False, shell=False,
                                  pass_fds=(namespace_fd,), env=MINIMAL_ENV).returncode
        finally:
            os.close(namespace_fd)

    if os.geteuid() != 0 or args.parent_ns_fd is None:
        raise SystemExit("invalid root namespace child invocation")
    try:
        parent_inode = os.fstat(args.parent_ns_fd).st_ino
        namespace_target = os.readlink(f"/proc/self/fd/{args.parent_ns_fd}")
        os.close(args.parent_ns_fd)
    except OSError:
        raise SystemExit("invalid root namespace child invocation") from None
    match = re.fullmatch(r"net:\[(\d+)\]", namespace_target)
    if match is None or int(match.group(1)) != parent_inode or parent_inode <= 0:
        raise SystemExit("invalid root namespace child invocation")
    if os.stat("/proc/self/ns/net").st_ino == parent_inode:
        raise SystemExit("unshare did not create a distinct network namespace")
    subprocess.run([IP, "link", "set", "dev", "lo", "up"], check=True,
                   shell=False, env=MINIMAL_ENV)
    interfaces = socket.if_nameindex()
    if len(interfaces) != 1 or interfaces[0][1] != "lo":
        raise SystemExit("network namespace must contain only loopback")

    if _git_head(repo) != args.expected_head:
        raise SystemExit("candidate HEAD does not match --expected-head")
    boundary = _candidate_boundary(repo)
    nonce = secrets.token_hex(32)
    scratch = Path(tempfile.mkdtemp(prefix="vst-root-qa-", dir="/tmp"))
    os.chmod(scratch, 0o700)
    proof_path = scratch / "proof.json"
    proof = {
        "schema_version": 4,
        "authority": "local-qa-preflight-non-authoritative",
        "helper_sha256": installed_digest,
        "run_id": args.run_id,
        "run_nonce": nonce,
        "candidate_head": args.expected_head,
        "runtime_profile": PROFILE,
        "distribution_id": "ubuntu",
        "distribution_version_id": "24.04",
        "kernel_release": platform.release(),
        "uid": 0,
        "gid": 0,
        "supplementary_groups": [],
        "capability_mask": "0xc1",
        "automount_enabled": False,
        "interop_enabled": False,
        "private_network": True,
        "default_deny_egress": True,
        "external_canary_blocked": True,
        "loopback_canary_passed": _loopback_canary_passed(),
        "candidate_root": boundary["candidate_root"],
        "mountinfo_sha256": boundary["mountinfo_sha256"],
        "parent_network_namespace_inode": parent_inode,
    }
    if not proof["loopback_canary_passed"]:
        raise SystemExit("loopback canary failed")
    proof_path.write_text(json.dumps(proof, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.chmod(proof_path, 0o400)
    qa_launcher = (
        "import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); "
        "runpy.run_module('tools.qa.run',run_name='__main__')"
    )
    qa_args = [PYTHON, "-I", "-c", qa_launcher, str(repo), "--category", args.category,
               "--repo-root", str(repo), "--dependency-target", args.dependency_target,
               "--scratch-root", args.scratch_root, "--run-id", args.run_id,
               "--expected-head", args.expected_head, "--privileged-harness-proof", str(proof_path),
               "--run-nonce", nonce, "--report-path", args.report_path,
               "--stdout-path", args.stdout_path, "--stderr-path", args.stderr_path,
               "--timeout-seconds", str(args.timeout_seconds), "--output-cap-bytes", str(args.output_cap_bytes)]
    restricted = [SETPRIV, "--reuid=0", "--regid=0", "--clear-groups",
                  "--bounding-set=-all,+chown,+setgid,+setuid", "--inh-caps=-all", "--ambient-caps=-all", "--", *qa_args]
    return subprocess.run(restricted, cwd=repo, check=False, shell=False,
                          env=MINIMAL_ENV).returncode


if __name__ == "__main__":
    raise SystemExit(_main())
