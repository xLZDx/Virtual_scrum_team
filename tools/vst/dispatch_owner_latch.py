"""Root-only persistent admission fence for ambiguous dispatch-owner outcomes."""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess

LATCH_PATH = "/etc/vst-runner/dispatch-owner-admission-blocked.json"
SOCKET_UNIT = "vst-dispatch-owner.socket"
SYSTEMCTL_PATH = "/usr/bin/systemctl"
_LOGGER = logging.getLogger("vst.dispatch_owner_latch")
_ALLOWED_RESULTS = frozenset({
    "protocol", "timeout", "exit-code", "signal", "core-dump", "watchdog",
    "exec-condition", "oom-kill", "killed", "start-limit-hit", "resources", "success",
})


def _check_root_parent(path: str) -> str:
    parent = os.path.dirname(path)
    current = parent
    while True:
        info = os.stat(current, follow_symlinks=False)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise RuntimeError("dispatch-owner admission directory is not root-controlled")
        if current == "/":
            break
        current = os.path.dirname(current)
    return parent


def _write_latch(result: str, exit_code: str, exit_status: str) -> None:
    parent = _check_root_parent(LATCH_PATH)
    payload = json.dumps({
        "exit_code": exit_code[:32],
        "exit_status": exit_status[:32],
        "service_result": result,
        "state": "BLOCKED",
        "unit": "vst-dispatch-owner.service",
        "version": 1,
    }, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(LATCH_PATH, flags, 0o644)
    except FileExistsError:
        info = os.stat(LATCH_PATH, follow_symlinks=False)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o644):
            raise RuntimeError("existing dispatch-owner admission fence is invalid")
        return
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o644)
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written < 1:
                raise OSError("short write while persisting dispatch-owner admission fence")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    dir_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def main() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("dispatch-owner admission fence requires root")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    result = os.environ.get("SERVICE_RESULT", "")
    if result not in _ALLOWED_RESULTS:
        result = "resources"
    latch_error: Exception | None = None
    try:
        _write_latch(
            result,
            os.environ.get("EXIT_CODE", "unknown"),
            os.environ.get("EXIT_STATUS", "unknown"),
        )
        _LOGGER.error("dispatch-owner admission fenced after service termination (%s)", result)
    except Exception as exc:
        latch_error = exc
        _LOGGER.exception("dispatch-owner admission latch could not be persisted")
    finally:
        # Any inability to persist the fence still stops the active listener for this
        # boot. The persistent file blocks activation across service and host restart.
        try:
            stopped = subprocess.run(
                [SYSTEMCTL_PATH, "--no-block", "stop", SOCKET_UNIT],
                check=False,
                timeout=10,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            _LOGGER.exception("dispatch-owner socket stop request failed")
            raise
        if stopped.returncode != 0:
            _LOGGER.error("dispatch-owner socket stop request returned %s", stopped.returncode)
        else:
            _LOGGER.info("dispatch-owner socket stop requested")
    if latch_error is not None:
        raise RuntimeError("dispatch-owner admission could not be durably fenced") from latch_error


if __name__ == "__main__":
    main()
