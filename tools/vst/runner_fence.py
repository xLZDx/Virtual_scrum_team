"""Root-only systemd predecessor fence for the persistent runner unit.

The helper is intended for a fixed root-owned ExecStartPre/ExecStopPost wrapper.
It never kills a process. Unknown or populated scopes leave the ledger
UNVERIFIED and prevent the next generation from starting.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

from .contracts import ContractError, canonical_bytes

DEFAULT_CONFIG = "/etc/vst-runner/fence.json"
_COMMAND_SCOPE = re.compile(r"^vst-command-[0-9]+-[0-9a-f]{32}$")
_UNIT_NAME = re.compile(r"^[A-Za-z0-9_.@:-]+\.service$")
_RECORD_FIELDS = frozenset({
    "version", "state", "unit", "invocation_id", "control_group",
    "cgroup_device", "cgroup_inode", "lock_device", "lock_inode",
    "generation", "predecessor_outcome", "sequence", "recorded_at",
    "previous_record_sha256", "record_sha256",
})


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key in runner fence record")
        result[key] = value
    return result


def _load_root_json(path: str, max_bytes: int = 65536) -> dict:
    if os.name != "posix" or not os.path.isabs(path):
        raise ContractError("runner fence config path must be absolute on POSIX")
    parent = os.path.dirname(path)
    while True:
        info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("runner fence config directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_size > max_bytes):
            raise ContractError("runner fence config is not a bounded root-owned regular file")
        raw = bytearray()
        while len(raw) <= max_bytes:
            part = os.read(fd, min(65536, max_bytes + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        if len(raw) > max_bytes:
            raise ContractError("runner fence config exceeds its size limit")
    finally:
        os.close(fd)
    value = json.loads(raw, object_pairs_hook=_unique_pairs)
    if not isinstance(value, dict):
        raise ContractError("runner fence config must be a JSON object")
    return value


def _validate_config(config: dict) -> None:
    required = {
        "unit_name", "systemctl_path", "ledger_path", "runtime_dir", "daemon_uid",
        "daemon_gid", "dispatcher_uid", "dispatcher_gid", "worker_uid", "worker_gid",
        "control_group", "generation_record_path",
    }
    if set(config) != required:
        raise ContractError("runner fence configuration fields do not match its schema")
    if config["unit_name"] != "vst-runner.service":
        raise ContractError("runner fence accepts only the fixed vst-runner.service unit")
    for name in ("systemctl_path", "ledger_path", "runtime_dir", "generation_record_path"):
        if not isinstance(config[name], str) or not os.path.isabs(config[name]):
            raise ContractError(f"runner fence {name} must be an absolute path")
    if not isinstance(config["control_group"], str):
        raise ContractError("runner fence cgroup identity is invalid")
    group = config["control_group"]
    if (not group.startswith("/") or group == "/" or ".." in group.split("/")
            or os.path.normpath(group) != group):
        raise ContractError("runner fence cgroup identity is not normalized")
    if group != "/system.slice/vst-runner.service" or config["systemctl_path"] != "/usr/bin/systemctl":
        raise ContractError("runner fence manager and service cgroup must match the fixed unit")
    ids = [config[name] for name in (
        "daemon_uid", "daemon_gid", "dispatcher_uid", "dispatcher_gid", "worker_uid", "worker_gid",
    )]
    if any(type(value) is not int or value < 1 for value in ids):
        raise ContractError("runner fence role identities must be positive integers")
    if len({config["daemon_uid"], config["dispatcher_uid"], config["worker_uid"]}) != 3:
        raise ContractError("runner fence role UIDs must be distinct")
    if config["generation_record_path"] == config["ledger_path"]:
        raise ContractError("runner fence public snapshot and private ledger must be separate")
    for path in (config["systemctl_path"], config["ledger_path"],
                 config["generation_record_path"]):
        parent = os.path.dirname(path)
        while True:
            info = os.stat(parent, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise ContractError("runner fence privileged path has an uncontrolled directory")
            if parent == "/":
                break
            parent = os.path.dirname(parent)


def _ensure_root_directory(path: str, *, mode: int = 0o700) -> None:
    info = os.stat(path, follow_symlinks=False)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != mode):
        raise ContractError("runner fence state directory has unsafe owner or mode")


def _manager_unit(config: dict, *, allow_inactive: bool = False) -> tuple[str, str]:
    executable = config["systemctl_path"]
    info = os.stat(executable, follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
            or not info.st_mode & 0o111):
        raise ContractError("systemctl executable is not root-controlled")
    parent = os.path.dirname(executable)
    while True:
        directory = os.stat(parent, follow_symlinks=False)
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0
                or directory.st_mode & 0o022):
            raise ContractError("systemctl executable path has an uncontrolled directory")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    try:
        result = subprocess.run(
            [executable, "show", config["unit_name"], "--property=InvocationID",
             "--property=ControlGroup", "--no-pager"],
            cwd="/", env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True,
            timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError("systemd manager identity query failed") from exc
    if result.returncode != 0:
        raise ContractError("systemd manager refused unit identity query")
    values: dict[str, str] = {}
    try:
        for line in result.stdout.decode("ascii").splitlines():
            name, value = line.split("=", 1)
            if name in values or name not in {"InvocationID", "ControlGroup"}:
                raise ValueError("unexpected manager property")
            values[name] = value
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractError("systemd manager returned malformed unit identity") from exc
    invocation = values.get("InvocationID", "")
    control_group = values.get("ControlGroup", "")
    if allow_inactive and invocation == "" and control_group == "":
        return invocation, control_group
    if (not re.fullmatch(r"[0-9a-f]{32}", invocation)
            or not control_group.startswith("/") or ".." in control_group.split("/")):
        raise ContractError("systemd unit has no valid invocation or cgroup identity")
    return invocation, control_group


def _cgroup_path(control_group: str) -> str:
    root = os.path.realpath("/sys/fs/cgroup")
    path = os.path.realpath(os.path.join(root, control_group.lstrip("/")))
    if os.path.commonpath((root, path)) != root:
        raise ContractError("systemd cgroup escaped the unified hierarchy")
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise ContractError("systemd ControlGroup is not a cgroup directory")
    return path


def _current_cgroup() -> str:
    with open("/proc/self/cgroup", encoding="ascii") as stream:
        rows = [line.rstrip("\n").split(":", 2) for line in stream]
    path = next((row[2] for row in rows if len(row) == 3 and row[:2] == ["0", ""]), None)
    if not path or ".." in path.split("/"):
        raise ContractError("runner fence helper is not in a unified cgroup")
    return os.path.normpath(path)


def _read_populated(path: str) -> tuple[str, list[str]]:
    try:
        with open(os.path.join(path, "cgroup.events"), encoding="ascii") as stream:
            events = dict(line.split() for line in stream if line.strip())
        with open(os.path.join(path, "cgroup.procs"), encoding="ascii") as stream:
            pids = [line.strip() for line in stream if line.strip()]
    except (OSError, ValueError) as exc:
        raise ContractError("runner cgroup population cannot be verified") from exc
    populated = events.get("populated")
    if populated not in {"0", "1"}:
        raise ContractError("runner cgroup population record is malformed")
    if any(not pid.isdecimal() or int(pid) < 1 for pid in pids) or len(pids) != len(set(pids)):
        raise ContractError("runner cgroup process inventory is malformed")
    return populated, pids


def _child_cgroup_directories(path: str) -> list[os.DirEntry[str]]:
    try:
        entries = list(os.scandir(path))
    except OSError as exc:
        raise ContractError("runner cgroup children cannot be inventoried") from exc
    children = []
    for entry in entries:
        if entry.is_symlink():
            raise ContractError("runner cgroup contains an unexpected symlink")
        if entry.is_dir(follow_symlinks=False):
            children.append(entry)
    return children


def _remove_empty_command_scopes(parent: str, current_pid: int) -> None:
    populated, pids = _read_populated(parent)
    if str(current_pid) not in pids or any(pid != str(current_pid) for pid in pids):
        raise ContractError("runner service cgroup has unknown processes")
    for entry in _child_cgroup_directories(parent):
        if not _COMMAND_SCOPE.fullmatch(entry.name):
            raise ContractError("unknown child cgroup blocks runner lifecycle admission")
        if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
            raise ContractError("runner command scope is not a real cgroup")
        scope = os.path.join(parent, entry.name)
        if os.path.dirname(os.path.realpath(scope)) != parent:
            raise ContractError("runner command scope escaped its unit cgroup")
        scope_populated, scope_pids = _read_populated(scope)
        if scope_populated != "0" or scope_pids:
            raise ContractError("populated runner command scope blocks restart; no process was killed")
        try:
            os.rmdir(scope)
        except OSError as exc:
            raise ContractError("empty runner command scope could not be removed") from exc
    if populated != "1":
        raise ContractError("runner lifecycle helper is missing from the unit cgroup")


def _hash_record(record_without_hash: dict) -> str:
    return hashlib.sha256(canonical_bytes(record_without_hash)).hexdigest()


def _read_records(path: str) -> list[dict]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise ContractError("runner fence ledger is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 4 * 1024 * 1024):
            raise ContractError("runner fence ledger has unsafe owner, mode, or size")
        chunks = bytearray()
        while len(chunks) <= 4 * 1024 * 1024:
            part = os.read(fd, min(65536, 4 * 1024 * 1024 + 1 - len(chunks)))
            if not part:
                break
            chunks.extend(part)
        if len(chunks) > 4 * 1024 * 1024 or (chunks and not chunks.endswith(b"\n")):
            raise ContractError("runner fence ledger is oversized or has a partial tail")
    finally:
        os.close(fd)
    records = []
    previous_hash = "0" * 64
    for expected_sequence, line in enumerate(chunks.splitlines(), start=1):
        record = json.loads(line, object_pairs_hook=_unique_pairs)
        if not isinstance(record, dict) or set(record) != _RECORD_FIELDS:
            raise ContractError("runner fence ledger record has unknown or missing fields")
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        if (record.get("sequence") != expected_sequence
                or record.get("previous_record_sha256") != previous_hash
                or record.get("record_sha256") != _hash_record(body)):
            raise ContractError("runner fence ledger hash chain is invalid")
        if record.get("state") not in {"BOOTSTRAP_EMPTY", "RUNNING", "STOPPED_EMPTY", "UNVERIFIED"}:
            raise ContractError("runner fence ledger contains an unknown lifecycle state")
        records.append(record)
        previous_hash = record["record_sha256"]
    return records


def _append_record(path: str, record: dict) -> dict:
    previous = _read_records(path)
    previous_hash = "0" * 64 if not previous else previous[-1]["record_sha256"]
    body = {**record, "sequence": len(previous) + 1,
            "previous_record_sha256": previous_hash}
    full = {**body, "record_sha256": _hash_record(body)}
    encoded = canonical_bytes(full) + b"\n"
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o600):
            raise ContractError("runner fence ledger is not root-only")
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise ContractError("runner fence ledger append was incomplete")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return full


def _publish_generation(config: dict, record: dict) -> None:
    """Atomically publish a read-only generation snapshot to the runner UID."""
    path = config["generation_record_path"]
    parent = os.path.dirname(path)
    current = parent
    while True:
        info = os.stat(current, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("runner generation directory is not root-controlled")
        if current == "/":
            break
        current = os.path.dirname(current)
    temp_path = f"{path}.tmp-{os.getpid()}"
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o644)
        data = canonical_bytes(record)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise ContractError("runner generation snapshot write was incomplete")
            view = view[written:]
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    else:
        os.close(fd)
    os.replace(temp_path, path)
    dir_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _lock_path(path: str):
    lock_path = path + ".lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o600):
        os.close(fd)
        raise ContractError("runner fence lock is not root-only")
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _base_record(config: dict, *, state: str, invocation: str, control_group: str,
                 cgroup_stat: os.stat_result | None, lock_stat: os.stat_result | None,
                 generation: str, predecessor: str) -> dict:
    return {
        "version": 1, "state": state, "unit": config["unit_name"],
        "invocation_id": invocation, "control_group": control_group,
        "cgroup_device": -1 if cgroup_stat is None else cgroup_stat.st_dev,
        "cgroup_inode": -1 if cgroup_stat is None else cgroup_stat.st_ino,
        "lock_device": -1 if lock_stat is None else lock_stat.st_dev,
        "lock_inode": -1 if lock_stat is None else lock_stat.st_ino,
        "generation": generation, "predecessor_outcome": predecessor,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def _ensure_runtime_and_lock(config: dict) -> os.stat_result:
    runtime = config["runtime_dir"]
    info = os.stat(runtime, follow_symlinks=False)
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != config["daemon_uid"]
            or info.st_gid not in {config["daemon_gid"], config["dispatcher_gid"]}
            or stat.S_IMODE(info.st_mode) not in {0o700, 0o710}):
        raise ContractError("runner runtime directory identity or mode is invalid")
    os.chown(runtime, config["daemon_uid"], config["dispatcher_gid"])
    os.chmod(runtime, 0o710)
    lock_path = os.path.join(runtime, "cgroup-admission.lock")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, config["daemon_uid"], config["daemon_gid"])
        os.fchmod(fd, 0o600)
        lock_stat = os.fstat(fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != config["daemon_uid"]:
            raise ContractError("runner admission lock identity is invalid")
        return lock_stat
    finally:
        os.close(fd)


def _capture_manager_identity(config: dict) -> tuple[str, str, str, os.stat_result]:
    invocation, cgroup = _manager_unit(config)
    if _current_cgroup() != cgroup:
        raise ContractError("runner fence helper is not executing inside the manager ControlGroup")
    cgroup_path = _cgroup_path(cgroup)
    _remove_empty_command_scopes(cgroup_path, os.getpid())
    lock_stat = _ensure_runtime_and_lock(config)
    return invocation, cgroup, cgroup_path, lock_stat


def _transition(config: dict, operation: str) -> dict:
    ledger = config["ledger_path"]
    _ensure_root_directory(os.path.dirname(ledger))
    lock_fd = _lock_path(ledger)
    try:
        prior = _read_records(ledger)
        invocation = "UNKNOWN"
        control_group = "UNKNOWN"
        cgroup_stat = None
        lock_stat = None
        try:
            invocation, control_group, cgroup_path, lock_stat = _capture_manager_identity(config)
            cgroup_stat = os.stat(cgroup_path, follow_symlinks=False)
            if os.geteuid() != 0:
                raise ContractError("runner lifecycle helper must run as root")
            if operation == "start":
                if not prior or prior[-1]["state"] not in {"BOOTSTRAP_EMPTY", "STOPPED_EMPTY"}:
                    raise ContractError("runner predecessor is not verified empty")
                if prior[-1]["unit"] != config["unit_name"]:
                    raise ContractError("runner fence ledger belongs to a different unit")
                if prior[-1]["state"] == "STOPPED_EMPTY":
                    if (prior[-1]["lock_device"] != lock_stat.st_dev
                            or prior[-1]["lock_inode"] != lock_stat.st_ino):
                        raise ContractError("runner admission lock identity changed across restart")
                if prior[-1]["generation"] == invocation:
                    raise ContractError("runner service generation must change for every restart")
                record = _append_record(
                    ledger, _base_record(
                        config, state="RUNNING", invocation=invocation,
                        control_group=control_group, cgroup_stat=cgroup_stat,
                        lock_stat=lock_stat, generation=invocation,
                        predecessor=prior[-1]["state"],
                    ),
                )
                _publish_generation(config, record)
                return record
            if operation != "stop":
                raise ContractError("runner fence operation is unsupported")
            if (not prior or prior[-1]["state"] != "RUNNING"
                    or prior[-1]["invocation_id"] != invocation
                    or prior[-1]["generation"] != invocation
                    or prior[-1]["unit"] != config["unit_name"]):
                raise ContractError("ExecStopPost has no exact matching RUNNING predecessor")
            if (prior[-1]["lock_device"] != lock_stat.st_dev
                    or prior[-1]["lock_inode"] != lock_stat.st_ino):
                raise ContractError("runner lock identity changed during one service generation")
            record = _append_record(
                ledger, _base_record(
                    config, state="STOPPED_EMPTY", invocation=invocation,
                    control_group=control_group, cgroup_stat=cgroup_stat,
                    lock_stat=lock_stat, generation=invocation,
                    predecessor="RUNNING",
                ),
            )
            _publish_generation(config, record)
            return record
        except BaseException:
            # An UNVERIFIED append can only make restart more restrictive. If it
            # fails, the preceding RUNNING/STOPPED state still prevents a false
            # clean transition on the next start.
            try:
                unverified = _append_record(
                    ledger, _base_record(
                        config, state="UNVERIFIED", invocation=invocation,
                        control_group=control_group, cgroup_stat=cgroup_stat,
                        lock_stat=lock_stat, generation=invocation,
                        predecessor="UNKNOWN" if not prior else prior[-1]["state"],
                    ),
                )
                _publish_generation(config, unverified)
            except BaseException:
                pass
            raise
    finally:
        os.close(lock_fd)


def bootstrap_empty(config_path: str = DEFAULT_CONFIG) -> dict:
    """Create the one-time baseline only after process and cgroup inventory is empty."""
    config = _load_root_json(config_path)
    _validate_config(config)
    if os.geteuid() != 0:
        raise ContractError("runner bootstrap inventory must run as root")
    ledger = config["ledger_path"]
    _ensure_root_directory(os.path.dirname(ledger))
    lock_fd = _lock_path(ledger)
    try:
        if _read_records(ledger):
            raise ContractError("runner bootstrap refuses a non-empty lifecycle ledger")
        systemctl = config["systemctl_path"]
        try:
            status = subprocess.run(
                [systemctl, "is-active", config["unit_name"]], cwd="/",
                env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True, timeout=5, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ContractError("systemd unit state cannot be inventoried") from exc
        if status.returncode != 3 or status.stdout.strip() != b"inactive":
            raise ContractError("runner bootstrap refuses an active unit")
        process_ids = []
        for entry in os.scandir("/proc"):
            if not entry.name.isdecimal():
                continue
            pid = int(entry.name)
            if pid == os.getpid():
                continue
            try:
                with open(os.path.join(entry.path, "status"), encoding="ascii") as stream:
                    uid_line = next(line for line in stream if line.startswith("Uid:"))
                uids = [int(value) for value in uid_line.split()[1:5]]
            except FileNotFoundError:
                continue
            except (OSError, StopIteration, ValueError) as exc:
                raise ContractError("runner bootstrap could not inventory every process identity") from exc
            if len(uids) != 4:
                raise ContractError("runner bootstrap found a malformed process UID record")
            if any(uid in {config["daemon_uid"], config["dispatcher_uid"], config["worker_uid"]}
                   for uid in uids):
                process_ids.append(pid)
        if process_ids:
            raise ContractError("runner bootstrap inventory found processes in reserved identities")
        invocation, cgroup, cgroup_path = "BOOTSTRAP", config["control_group"], None
        current_invocation, current_cgroup = _manager_unit(config, allow_inactive=True)
        if current_invocation or current_cgroup:
            raise ContractError("inactive runner unit returned a live manager identity")
        try:
            cgroup_path = _cgroup_path(cgroup)
        except FileNotFoundError:
            cgroup_path = None
        if cgroup_path is not None:
            populated, pids = _read_populated(cgroup_path)
            if populated != "0" or pids:
                raise ContractError("runner bootstrap cgroup inventory is populated")
            if _child_cgroup_directories(cgroup_path):
                raise ContractError("runner bootstrap cgroup contains unexplained child scopes")
        cgroup_stat = None if cgroup_path is None else os.stat(cgroup_path, follow_symlinks=False)
        record = _append_record(
            ledger, _base_record(
                config, state="BOOTSTRAP_EMPTY", invocation=invocation,
                control_group=cgroup, cgroup_stat=cgroup_stat, lock_stat=None,
                generation="BOOTSTRAP", predecessor="NONE",
            ),
        )
        _publish_generation(config, record)
        return record
    finally:
        os.close(lock_fd)


def main() -> None:
    if os.geteuid() != 0:
        raise ContractError("runner fence helper must run as root")
    if len(sys.argv) != 2 or sys.argv[1] not in {"start", "stop", "bootstrap"}:
        raise ContractError("runner fence helper accepts start, stop, or bootstrap")
    config = _load_root_json(DEFAULT_CONFIG)
    _validate_config(config)
    if sys.argv[1] == "bootstrap":
        bootstrap_empty(DEFAULT_CONFIG)
    else:
        _transition(config, sys.argv[1])


if __name__ == "__main__":
    main()
