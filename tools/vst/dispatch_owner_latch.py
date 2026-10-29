"""Root-only persistent admission fence for ambiguous dispatch-owner outcomes."""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import time

LATCH_PATH = "/etc/vst-runner/dispatch-owner-admission-blocked.json"
SOCKET_UNIT = "vst-dispatch-owner.socket"
SYSTEMCTL_PATH = "/usr/bin/systemctl"
SYSTEMCTL_TIMEOUT_SECONDS = 10
SOCKET_STOP_RETRY_INITIAL_SECONDS = 1
SOCKET_STOP_RETRY_MAX_SECONDS = 30
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


def _stop_socket_and_confirm_inactive() -> None:
    """Keep the service stop hook alive until socket admission is actually closed."""
    delay = SOCKET_STOP_RETRY_INITIAL_SECONDS
    while True:
        try:
            stopped = subprocess.run(
                [SYSTEMCTL_PATH, "stop", SOCKET_UNIT],
                check=False,
                timeout=SYSTEMCTL_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            state = subprocess.run(
                [SYSTEMCTL_PATH, "show", "--property=ActiveState", "--value", SOCKET_UNIT],
                check=False,
                timeout=SYSTEMCTL_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            active_state = state.stdout.strip() if state.returncode == 0 else "unknown"
            if stopped.returncode == 0 and active_state == "inactive":
                _LOGGER.info("dispatch-owner socket is confirmed inactive")
                return
            _LOGGER.critical(
                "dispatch-owner socket stop is not confirmed (stop=%s, state=%s); retrying",
                stopped.returncode,
                active_state,
            )
        except Exception:
            _LOGGER.exception("dispatch-owner socket stop could not be confirmed; retrying")
        time.sleep(delay)
        delay = min(delay * 2, SOCKET_STOP_RETRY_MAX_SECONDS)


def main() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("dispatch-owner admission fence requires root")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    result = os.environ.get("SERVICE_RESULT", "")
    if result not in _ALLOWED_RESULTS:
        result = "resources"
    # Close the live admission path before touching /etc: parent stat/open/fsync can block on
    # unhealthy storage. A confirmed stop protects this boot even if persistence then fails.
    _stop_socket_and_confirm_inactive()
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
    if latch_error is not None:
        raise RuntimeError("dispatch-owner admission could not be durably fenced") from latch_error


if __name__ == "__main__":
    main()
