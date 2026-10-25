"""WSL-only functional selector for the fixed S4 runner-to-worker boundary (AC-16)."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import subprocess
from pathlib import Path

import pytest


HELPER = Path("/usr/local/libexec/vst-s4-worker-exec")
SOURCE = Path(__file__).resolve().parents[2] / "tools" / "qa" / "worker_exec.c"


@pytest.mark.skipif(os.name != "posix", reason="AC-16 is assigned only to the Ubuntu 24.04 WSL profile")
def test_s4_worker_helper_drops_runner_identity_and_denies_runner_sentinels(tmp_path: Path):
    assert os.getuid() == 997 and os.getgid() == 988
    helper_stat = HELPER.stat()
    assert stat.S_ISREG(helper_stat.st_mode)
    assert (helper_stat.st_uid, helper_stat.st_gid, stat.S_IMODE(helper_stat.st_mode)) == (0, 988, 0o4750)

    repo = SOURCE.parents[2]
    candidate_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()
    source_sha256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    version = subprocess.run(
        [str(HELPER), "--version"], check=True, text=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()
    assert version == f"schema=1 head={candidate_head} source_sha256={source_sha256}"

    # Keep private sentinels in a runner-only directory; the worker must fail closed on both.
    sentinel = tmp_path / "runner-secret"
    sentinel.write_text("runner-only\n", encoding="utf-8")
    sentinel.chmod(0o600)
    server_path = tmp_path / "runner.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(server_path))
    server_path.chmod(0o600)
    listener.listen(1)
    tmp_path.chmod(0o711)
    read_fd, write_fd = os.pipe()
    try:
        os.set_inheritable(read_fd, True)
        script = "\n".join((
            "import ctypes, json, os, socket, sys",
            "fd = int(sys.argv[3])",
            "try:",
            "    open(sys.argv[1], 'rb').close()",
            "    file_denied = False",
            "except PermissionError:",
            "    file_denied = True",
            "sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)",
            "try:",
            "    sock.connect(sys.argv[2])",
            "    socket_denied = False",
            "except PermissionError:",
            "    socket_denied = True",
            "finally:",
            "    sock.close()",
            "print(json.dumps({'uid': os.getuid(), 'euid': os.geteuid(), 'gid': os.getgid(),",
            "    'egid': os.getegid(), 'groups': os.getgroups(),",
            "    'no_new_privs': ctypes.CDLL(None).prctl(39, 0, 0, 0, 0),",
            "    'fd_closed': not os.path.exists('/proc/self/fd/' + str(fd)),",
            "    'file_denied': file_denied, 'socket_denied': socket_denied}))",
        ))
        result = subprocess.run(
            [str(HELPER), "-I", "-c", script, str(sentinel), str(server_path), str(read_fd)],
            check=True, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=False, pass_fds=(read_fd,), timeout=10,
        )
    finally:
        os.close(read_fd)
        os.close(write_fd)
        listener.close()

    observed = json.loads(result.stdout)
    assert observed == {
        "uid": 999, "euid": 999, "gid": 989, "egid": 989, "groups": [],
        "no_new_privs": 1, "fd_closed": True, "file_denied": True, "socket_denied": True,
    }
