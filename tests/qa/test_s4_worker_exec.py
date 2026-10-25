"""Exercise the POSIX worker trampoline at the credential boundary."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import socket
import subprocess
import sys

import pytest

from tools.vst import runner
from tools.vst.sandbox import require_runner_can_access_signer, require_worker_cannot_access_signer


RUNNER_UID = 997
WORKER_UID = 999
WORKER_GID = 989
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_WORKER_PROBE = r'''import ctypes, errno, json, os
libc = ctypes.CDLL(None, use_errno=True)
nnp = libc.prctl(39, 0, 0, 0, 0)
keys = ("CapInh", "CapPrm", "CapEff", "CapAmb")
caps = {key: next(line.split()[1] for line in open("/proc/self/status") if line.startswith(key + ":")) for key in keys}
before = {"uid": os.getuid(), "euid": os.geteuid(), "resuid": os.getresuid(),
          "gid": os.getgid(), "egid": os.getegid(), "resgid": os.getresgid(),
          "groups": os.getgroups()}
setuid_errno = None
try:
    os.setuid(997)
except OSError as exc:
    setuid_errno = exc.errno
after = os.geteuid()
print(json.dumps({"identity": before, "caps": caps, "no_new_privs": nnp,
                  "setuid_errno": setuid_errno, "uid_after_setuid_attempt": after}))'''


def _assert_worker_record(record: dict) -> None:
    identity = record["identity"]
    assert identity["uid"] == WORKER_UID
    assert identity["euid"] == WORKER_UID
    assert identity["resuid"] == [WORKER_UID, WORKER_UID, WORKER_UID]
    assert identity["gid"] == WORKER_GID
    assert identity["egid"] == WORKER_GID
    assert identity["resgid"] == [WORKER_GID, WORKER_GID, WORKER_GID]
    assert identity["groups"] == []
    assert record["caps"] == {
        "CapInh": "0000000000000000",
        "CapPrm": "0000000000000000",
        "CapEff": "0000000000000000",
        "CapAmb": "0000000000000000",
    }
    assert record["no_new_privs"] == 1
    assert record["setuid_errno"] == errno.EPERM
    assert record["uid_after_setuid_attempt"] == WORKER_UID


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux POSIX worker boundary")
def test_s4_worker_trampoline_drops_capabilities_before_manifest_exec():
    """Prove both the direct runner launch and QA-worker execution boundary."""
    euid = os.geteuid()
    if euid == WORKER_UID:
        # Normal tools.qa.run category execution: the pytest selector itself
        # starts only after worker_exec.py has dropped inherited privileges.
        own_identity = {
            "uid": os.getuid(), "euid": os.geteuid(), "resuid": list(os.getresuid()),
            "gid": os.getgid(), "egid": os.getegid(), "resgid": list(os.getresgid()),
            "groups": os.getgroups(),
        }
        assert own_identity == {
            "uid": WORKER_UID, "euid": WORKER_UID,
            "resuid": [WORKER_UID, WORKER_UID, WORKER_UID],
            "gid": WORKER_GID, "egid": WORKER_GID,
            "resgid": [WORKER_GID, WORKER_GID, WORKER_GID], "groups": [],
        }
        assert _read_caps() == _EMPTY_CAPS
        assert _pr_get_no_new_privs() == 1
        # Check regain denial in a disposable child so a regression cannot
        # change the pytest process's own identity before the assertion fires.
        completed = subprocess.run(
            [sys.executable, "-c", _WORKER_PROBE],
            cwd=REPO_ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=5, check=False,
        )
        assert completed.returncode == 0, completed.stderr
        records = [line for line in completed.stdout.splitlines() if line.strip()]
        assert len(records) == 1, completed.stdout
        _assert_worker_record(json.loads(records[0]))
        return

    assert euid == RUNNER_UID, f"focused probe must run as runner or worker; got UID {euid}"
    exit_code, stdout, info = runner._run_one(
        [sys.executable, "-c", _WORKER_PROBE],
        REPO_ROOT,
        10.0,
        os.environ.copy(),
        16 * 1024,
        worker_uid=WORKER_UID,
        worker_gid=WORKER_GID,
    )
    assert exit_code == 0, info
    records = [line for line in stdout.splitlines() if line.strip()]
    assert len(records) == 1, stdout
    _assert_worker_record(json.loads(records[0]))


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux POSIX signer boundary")
def test_s4_worker_cannot_traverse_synthetic_signer_socket(tmp_path):
    """Focused runner-owned probe; deliberately not part of the recursive QA selector map."""
    assert os.geteuid() == RUNNER_UID
    socket_dir = tmp_path / "signer-boundary"
    socket_dir.mkdir(mode=0o700)
    os.chmod(socket_dir, 0o750)
    socket_path = socket_dir / "signer.sock"
    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        endpoint.bind(str(socket_path))
        os.chmod(socket_path, 0o660)
        endpoint.listen(1)
        require_runner_can_access_signer(str(socket_path))
        require_worker_cannot_access_signer(
            str(socket_path), worker_uid=WORKER_UID, worker_gid=WORKER_GID,
        )
        probe = r'''import errno, json, socket, sys
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    client.connect(sys.argv[1])
    print(json.dumps({"connected": True, "errno": None}))
except OSError as exc:
    print(json.dumps({"connected": False, "errno": exc.errno}))
finally:
    client.close()'''
        exit_code, stdout, info = runner._run_one(
            [sys.executable, "-c", probe, str(socket_path)],
            REPO_ROOT, 10.0, os.environ.copy(), 16 * 1024,
            worker_uid=WORKER_UID, worker_gid=WORKER_GID,
        )
        assert exit_code == 0, info
        records = [line for line in stdout.splitlines() if line.strip()]
        assert len(records) == 1, stdout
        result = json.loads(records[0])
        assert result == {"connected": False, "errno": errno.EACCES}
    finally:
        endpoint.close()


_EMPTY_CAPS = {
    "CapInh": "0000000000000000",
    "CapPrm": "0000000000000000",
    "CapEff": "0000000000000000",
    "CapAmb": "0000000000000000",
}


def _read_caps() -> dict[str, str]:
    return {
        key: next(line.split()[1] for line in open("/proc/self/status")
                  if line.startswith(key + ":"))
        for key in _EMPTY_CAPS
    }


def _pr_get_no_new_privs() -> int:
    return ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0)
