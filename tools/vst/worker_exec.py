"""Drop inherited Linux capabilities before executing an authorized worker argv.

This file is invoked with ``python -I -S`` after the parent has applied the
worker UID/GID. It uses only the standard library, verifies the resulting
identity, clears inheritable/permitted/effective/ambient capabilities, enables
no-new-privileges, and then execs the exact argv selected by the manifest.
"""

from __future__ import annotations

import ctypes
import os
import sys


_CAP_VERSION_3 = 0x20080522
_PR_SET_NO_NEW_PRIVS = 38
_PR_GET_NO_NEW_PRIVS = 39
_PR_CAP_AMBIENT = 47
_PR_CAP_AMBIENT_CLEAR_ALL = 4


class _CapHeader(ctypes.Structure):
    _fields_ = (("version", ctypes.c_uint32), ("pid", ctypes.c_int))


class _CapData(ctypes.Structure):
    _fields_ = (
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    )


def _call_prctl(libc: ctypes.CDLL, option: int, argument: int) -> int:
    result = libc.prctl(option, argument, 0, 0, 0)
    if result == -1:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return result


def _clear_worker_capabilities() -> None:
    if not sys.platform.startswith("linux"):
        raise RuntimeError("worker capability isolation requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)

    # Set this before exec: an ambient capability must never be reacquired from
    # an executable's file capabilities or setuid bits by the worker process.
    _call_prctl(libc, _PR_SET_NO_NEW_PRIVS, 1)
    _call_prctl(libc, _PR_CAP_AMBIENT, _PR_CAP_AMBIENT_CLEAR_ALL)

    header = _CapHeader(_CAP_VERSION_3, 0)
    data = (_CapData * 2)()
    if libc.capset(ctypes.byref(header), data) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))

    if libc.capget(ctypes.byref(header), data) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if any(item.effective or item.permitted or item.inheritable for item in data):
        raise RuntimeError("worker retains effective, permitted, or inheritable capabilities")
    if _call_prctl(libc, _PR_GET_NO_NEW_PRIVS, 0) != 1:
        raise RuntimeError("worker no-new-privileges state is not enabled")


def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[2] != "--":
        raise SystemExit("worker isolation helper received malformed arguments")
    try:
        expected_uid, expected_gid = int(argv[0]), int(argv[1])
        if expected_uid < 1 or expected_gid < 1:
            raise ValueError("worker identity must use positive ids")
        if os.getresuid() != (expected_uid, expected_uid, expected_uid):
            raise RuntimeError("worker UID transition did not match the requested identity")
        if os.getresgid() != (expected_gid, expected_gid, expected_gid) or os.getgroups():
            raise RuntimeError("worker group transition did not match the requested identity")
        _clear_worker_capabilities()
        command = argv[3:]
        if not command or not command[0]:
            raise ValueError("worker command must be non-empty")
        os.execvpe(command[0], command, os.environ)
    except Exception as exc:  # fail closed before any manifest command is exec'd
        print(f"worker identity isolation refused: {type(exc).__name__}", file=sys.stderr)
        return 126
    return 126


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
