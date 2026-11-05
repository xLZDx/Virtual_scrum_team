"""Bounded WSL-side protocol for one S2-4 runtime qualification attempt.

This file is streamed to a single isolated Python process by
run_s2_runtime_qualification.py. It uses only standard-library modules until
the installed runtime source has been verified and all pre-start checks pass.
"""
from __future__ import annotations

import datetime
import errno
import grp
import hashlib
import json
import os
import pathlib
import re
import socket
import sqlite3
import stat
import struct
import subprocess
import sys
import time
import urllib.parse

AUTH = json.loads(AUTH)
TRANSIENT_UNIT = TRANSIENT_UNIT
MOUNT_AUDIT_ONLY = MOUNT_AUDIT_ONLY
BASELINE_DECODER_SOURCE = BASELINE_DECODER_SOURCE
BASELINE_DECODER_SHA256 = BASELINE_DECODER_SHA256
BASELINE_DECODER_REVISION = BASELINE_DECODER_REVISION
MAX_COMMAND_CAPTURE = 256 * 1024
MAX_REPORT_BYTES = 1_800_000
OWNER_SOCKET = "/run/vst-supervisor/dispatch-owner.sock"
EXPECTED_UNITS = (
    "vst-sandbox-probe.service", "vst-assignment-bootstrap.service",
    "vst-dispatch-issuer.service", "vst-supervisor.service", "vst-signer.service",
    "vst-runner.service", "vst-dispatcher.service", "vst-dispatch-owner.socket",
    "vst-dispatch-owner.service",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class Hold(Exception):
    pass


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def record(label: str, argv: list[str], *, timeout: float = 30.0,
           maximum: int = MAX_COMMAND_CAPTURE) -> dict:
    """Run one command once and retain only a bounded prefix plus full hashes."""
    started = utc()
    try:
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True,
        )
        out = bytearray()
        err = bytearray()
        out_hash = hashlib.sha256()
        err_hash = hashlib.sha256()
        totals = {"stdout": 0, "stderr": 0}

        def drain(stream, kept, digest, name):
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                totals[name] += len(chunk)
                digest.update(chunk)
                if len(kept) < maximum:
                    kept.extend(chunk[:maximum - len(kept)])

        import threading
        out_thread = threading.Thread(target=drain, args=(process.stdout, out, out_hash, "stdout"), daemon=True)
        err_thread = threading.Thread(target=drain, args=(process.stderr, err, err_hash, "stderr"), daemon=True)
        out_thread.start()
        err_thread.start()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
        out_thread.join(timeout=10)
        err_thread.join(timeout=10)
        if out_thread.is_alive() or err_thread.is_alive():
            raise RuntimeError("bounded output drain did not terminate")
        return {
            "id": label, "argv": argv, "started_utc": started, "finished_utc": utc(),
            "exit_code": process.returncode, "timed_out": timed_out,
            "stdout_bytes": totals["stdout"], "stdout_sha256": out_hash.hexdigest(),
            "stdout_truncated": totals["stdout"] > len(out),
            "stderr_bytes": totals["stderr"], "stderr_sha256": err_hash.hexdigest(),
            "stderr_truncated": totals["stderr"] > len(err),
            "_stdout": bytes(out), "_stderr": bytes(err),
        }
    except Exception as exc:
        return {
            "id": label, "argv": argv, "started_utc": started, "finished_utc": utc(),
            "exit_code": None, "error_type": type(exc).__name__,
            "stdout_bytes": 0, "stderr_bytes": 0, "_stdout": b"", "_stderr": b"",
        }


def _prefix(result: dict, stream: str = "stdout") -> bytes:
    return result.pop("_" + stream, b"")


def _text(result: dict) -> str:
    return _prefix(result).decode("utf-8", "replace")


def _require_command(result: dict, name: str) -> bytes:
    if (result.get("exit_code") != 0 or result.get("timed_out")
            or result.get("stdout_truncated") or result.get("stderr_truncated")):
        _prefix(result)
        _prefix(result, "stderr")
        R["commands"].append(result)
        stop(name + " failed, timed out, or exceeded its output bound")
    output = _prefix(result)
    _prefix(result, "stderr")
    R["commands"].append(result)
    return output


def stop(reason: str) -> None:
    R["terminal"] = "HOLD"
    R["reason"] = reason[:512]
    raise Hold()


SYSTEMD_MASK_DIRS = frozenset({
    "/dev/hugepages", "/dev/shm", "/home", "/mnt", "/proc/acpi", "/proc/bus",
    "/proc/fs", "/proc/irq", "/proc/scsi",
    "/proc/sys/fs/binfmt_misc", "/root", "/run/WSL", "/run/credentials",
    "/run/lock", "/run/shm", "/run/user", "/sys/fs/bpf", "/sys/fs/selinux",
    "/sys/fs/fuse/connections", "/sys/kernel/config", "/sys/kernel/debug",
    "/sys/kernel/tracing", "/tmp/.X11-unix", "/usr/lib/modules", "/usr/lib/wsl",
})
SYSTEMD_MASK_FILES = frozenset({
    "/init", "/proc/kallsyms", "/proc/kcore", "/proc/kmsg",
    "/proc/latency_stats", "/proc/mtrr",
})
SYSTEMD_MASK_TARGETS = SYSTEMD_MASK_DIRS | SYSTEMD_MASK_FILES
SYSTEMD_INACCESSIBLE_PATHS = tuple(sorted(SYSTEMD_MASK_TARGETS))

# Only mount rows present in the independently captured PM-07 inventory can be
# treated as an underlying row below a mask. Absence is allowed; a new row is not.
MASK_BASES = {
    "/dev/shm": ("tmpfs", "/", "none", {"rw", "nosuid", "nodev", "noatime"}, "/dev"),
    "/run/lock": ("tmpfs", "/", "none", {"rw", "nosuid", "nodev", "noexec", "noatime"}, "/run"),
    "/run/shm": ("tmpfs", "/", "none", {"rw", "nosuid", "nodev", "noatime"}, "/run"),
    "/proc/acpi": ("proc", "/acpi", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/bus": ("proc", "/bus", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/fs": ("proc", "/fs", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/irq": ("proc", "/irq", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/latency_stats": ("proc", "/latency_stats", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/mtrr": ("proc", "/mtrr", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/scsi": ("proc", "/scsi", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}, "/proc"),
    "/proc/sys/fs/binfmt_misc": ("binfmt_misc", "/", "binfmt_misc", {"rw", "nosuid", "relatime"}, "/proc"),
    "/sys/fs/bpf": ("sysfs", "/fs/bpf", "sysfs", {"ro", "nosuid", "nodev", "noexec", "noatime"}, "/sys"),
    "/sys/fs/selinux": ("sysfs", "/fs/selinux", "sysfs", {"rw", "nosuid", "nodev", "noexec", "noatime"}, "/sys"),
}

EXACT_MOUNTS = {
    "/run": ("tmpfs", "/", "none", {"rw", "nosuid", "nodev"}),
    "/dev/pts": ("devpts", "/", "devpts", {"rw", "nosuid", "noexec", "noatime"}),
    "/dev/mqueue": ("mqueue", "/", "mqueue", {"rw", "nosuid", "nodev", "noexec", "relatime"}),
    "/sys": ("sysfs", "/", "sysfs", {"rw", "nosuid", "nodev", "noexec", "noatime"}),
    "/sys/fs/cgroup": ("cgroup2", "/", "cgroup2", {"ro", "nosuid", "nodev", "noexec", "relatime"}),
    "/proc": ("proc", "/", "proc", {"rw", "nosuid", "nodev", "noexec", "relatime"}),
    "/proc/sys": ("proc", "/sys", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}),
    "/proc/sysrq-trigger": ("proc", "/sysrq-trigger", "proc", {"ro", "nosuid", "nodev", "noexec", "relatime"}),
}


def _unescape_mountinfo(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t").replace(
        "\\012", "\n").replace("\\134", "\\")


def _decode_mountinfo(raw: str, *, expected_unit: str | None = None) -> tuple[list[dict], list[str], list[dict]]:
    """Accept only the measured system mounts and exact current-unit masks."""
    rows: list[dict] = []
    windows_mounts: list[dict] = []
    unapproved_mounts: list[dict] = []
    seen_ids: set[int] = set()
    for number, line in enumerate(raw.splitlines(), 1):
        before, separator, after = line.partition(" - ")
        if not separator or len(line) > 16384:
            unapproved_mounts.append({"line": number, "reason": "mountinfo row is malformed",
                                      "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                                      "line_prefix": line[:512]})
            continue
        left, right = before.split(), after.split()
        if len(left) < 6 or len(right) != 3:
            unapproved_mounts.append({"line": number, "reason": "mountinfo fields are malformed",
                                      "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                                      "line_prefix": line[:512]})
            continue
        try:
            mount_id, parent_id = int(left[0]), int(left[1])
        except ValueError:
            unapproved_mounts.append({"line": number, "reason": "mountinfo identifiers are malformed",
                                      "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                                      "line_prefix": line[:512]})
            continue
        if mount_id <= 0 or parent_id <= 0 or mount_id in seen_ids:
            unapproved_mounts.append({"line": number, "mount_id": mount_id,
                                      "reason": "mountinfo identifiers are invalid or duplicated",
                                      "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                                      "line_prefix": line[:512]})
            continue
        seen_ids.add(mount_id)
        mountpoint = _unescape_mountinfo(left[4])
        mount_root = _unescape_mountinfo(left[3])
        if not mountpoint.startswith("/") or "/../" in mountpoint or mountpoint.endswith("/.."):
            unapproved_mounts.append({"line": number, "mount_id": mount_id,
                                      "reason": "mountinfo target is not a canonical absolute path",
                                      "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                                      "line_prefix": line[:512]})
            continue
        fstype, source = right[0].lower(), _unescape_mountinfo(right[1])
        mount_options, super_options = left[5].split(","), right[2].split(",")
        if (len(set(mount_options)) != len(mount_options)
                or len(set(super_options)) != len(super_options)):
            unapproved_mounts.append({"line": number, "mount_id": mount_id,
                                      "reason": "mountinfo contains duplicate options",
                                      "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                                      "line_prefix": line[:512]})
        row = {
            "line": number, "mount_id": mount_id, "parent_id": parent_id,
            "mountpoint": mountpoint, "filesystem": fstype, "source": source,
            "device": left[2], "mount_root": mount_root,
            "mount_options": mount_options, "super_options": super_options,
            "optional_fields": left[6:],
            "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
        }
        rows.append(row)
        options = mount_options + super_options
        wsl_drvfs_9p = fstype == "9p" and re.search(
            r"(?:^|[;,])aname=drvfs(?:$|[;,])", ",".join(options), re.IGNORECASE,
        ) is not None
        if fstype == "drvfs" or wsl_drvfs_9p or re.fullmatch(r"[A-Za-z]:\\?", source):
            windows_mounts.append(row)

    by_path: dict[str, list[dict]] = {}
    for row in rows:
        by_path.setdefault(row["mountpoint"], []).append(row)
    root_rows = by_path.get("/", [])
    run_rows = by_path.get("/run", [])
    if len(root_rows) != 1 or len(run_rows) != 1:
        for row in rows:
            reject(row, "mount inventory cannot be classified without unique root and /run")
        unapproved_mounts.append({"reason": "mount namespace root and /run must each be unique",
                                  "root_rows": len(root_rows), "run_rows": len(run_rows)})
        return rows, windows_mounts, unapproved_mounts
    root, run = root_rows[0], run_rows[0]
    run_device = run["device"]
    handled: set[int] = set()

    def reject(row: dict, reason: str) -> None:
        unapproved_mounts.append({"row": row["mount_id"], "reason": reason, **row})

    def nearest_parent_mount(target: str) -> dict | None:
        parents = [row for row in rows if row["mountpoint"] != target
                   and (row["mountpoint"] == "/" or target.startswith(
                       row["mountpoint"].rstrip("/") + "/"))]
        if not parents:
            return None
        deepest = max(len(row["mountpoint"]) for row in parents)
        candidates = [row for row in parents if len(row["mountpoint"]) == deepest]
        # A stacked ancestor is ambiguous unless it is an explicitly understood
        # systemd mask; callers reject ambiguity rather than guessing the top.
        return max(candidates, key=lambda row: row["mount_id"]) if len(candidates) == 1 else None

    def check_parent(row: dict, target: str) -> bool:
        parent = nearest_parent_mount(target)
        return parent is not None and row["parent_id"] == parent["mount_id"]

    if expected_unit is not None and not re.fullmatch(r"vst-s2-qual-[0-9a-f]{16}\.service", expected_unit):
        for row in rows:
            reject(row, "transient unit identity is malformed")
        unapproved_mounts.append({"reason": "transient unit identity is malformed"})
        return rows, windows_mounts, unapproved_mounts
    cgroup_target = None
    if expected_unit is not None:
        cgroup_target = "/sys/fs/cgroup/system.slice/" + expected_unit + "/memory.pressure"
    mask_targets = set(SYSTEMD_MASK_TARGETS)
    if cgroup_target:
        mask_targets.add(cgroup_target)

    for target in sorted(mask_targets):
        group = by_path.get(target, [])
        expected_root = ("/systemd/inaccessible/reg" if target in SYSTEMD_MASK_FILES
                         or target == cgroup_target else "/systemd/inaccessible/dir")
        masks = [row for row in group if (
            row["filesystem"] == "tmpfs" and row["source"] == "none"
            and row["mount_root"] == expected_root and row["device"] == run_device
            and set(row["mount_options"]) == {"ro", "nosuid", "nodev", "noexec"}
            and set(row["super_options"]) == {"rw", "mode=755"}
        )]
        if len(masks) != 1:
            for row in group:
                reject(row, "exact systemd inaccessible mask is missing or ambiguous")
            if not group:
                unapproved_mounts.append({"mountpoint": target,
                                          "reason": "required inaccessible mask has no mount row"})
            continue
        mask = masks[0]
        bases = [row for row in group if row["mount_id"] != mask["mount_id"]]
        if len(bases) > 1:
            for row in bases:
                reject(row, "multiple underlying rows below one inaccessible mask")
            reject(mask, "inaccessible mask overlays multiple underlying rows")
            continue
        if not check_parent(mask, target):
            reject(mask, "inaccessible mask is not attached to the exact target parent")
        handled.add(mask["mount_id"])
        expected_base = MASK_BASES.get(target)
        if target == cgroup_target:
            expected_base = (
                "cgroup2", "/system.slice/" + expected_unit + "/memory.pressure",
                "cgroup2", {"rw", "nosuid", "nodev", "noexec", "relatime"},
                "/sys/fs/cgroup",
            )
        for base in bases:
            if expected_base is None:
                reject(base, "unapproved underlying mount below inaccessible mask")
                continue
            fstype, mount_root, source, options, parent_path = expected_base
            parent = by_path.get(parent_path, [])
            same = (base["filesystem"] == fstype and base["mount_root"] == mount_root
                    and base["source"] == source and set(base["mount_options"]) == options
                    and set(base["super_options"]) == {"rw"}
                    and len(parent) == 1 and base["parent_id"] == parent[0]["mount_id"]
                    and base["mount_id"] < mask["mount_id"])
            if not same:
                reject(base, "underlying mount below mask differs from its exact measured contract")
            else:
                handled.add(base["mount_id"])
        nested = [row for row in rows if row["mount_id"] not in handled
                  and row["mountpoint"].startswith(target.rstrip("/") + "/")]
        for row in nested:
            reject(row, "unexpected nested mount remains below inaccessible target")

    incoming_path = "/run/systemd/incoming"
    incoming = by_path.get(incoming_path, [])
    expected_incoming_root = "/systemd/propagate/" + expected_unit if expected_unit else None
    if len(incoming) != 1:
        for row in incoming:
            reject(row, "current-unit propagation mount is missing or ambiguous")
        if not incoming:
            unapproved_mounts.append({"mountpoint": incoming_path,
                                      "reason": "required current-unit propagation mount is absent"})
    else:
        row = incoming[0]
        valid = (expected_unit is not None and row["filesystem"] == "tmpfs"
                 and row["source"] == "none" and row["device"] == run_device
                 and row["mount_root"] == expected_incoming_root
                 and set(row["mount_options"]) == {"ro", "nosuid", "nodev"}
                 and set(row["super_options"]) == {"rw", "mode=755"}
                 and check_parent(row, incoming_path))
        if valid:
            handled.add(row["mount_id"])
        else:
            reject(row, "propagation mount is not bound to this exact transient unit")

    exact = dict(EXACT_MOUNTS)
    exact["/"] = ("ext4", "/", root["source"], {"ro", "nosuid", "relatime"})
    exact["/dev"] = ("tmpfs", "/", "tmpfs", {"ro", "nosuid", "noexec"})
    for target, (fstype, mount_root, source, options) in exact.items():
        group = by_path.get(target, [])
        if len(group) != 1:
            for row in group:
                if row["mount_id"] not in handled:
                    reject(row, "approved system mount is missing or ambiguous")
            if not group:
                unapproved_mounts.append({"mountpoint": target,
                                          "reason": "required system mount is absent"})
            continue
        row = group[0]
        valid = (row["filesystem"] == fstype and row["mount_root"] == mount_root
                 and row["source"] == source and set(row["mount_options"]) == options)
        if target == "/":
            valid = valid and row["device"] == root["device"]
        elif target == "/run":
            valid = (valid and row["device"] == run_device
                     and set(row["super_options"]) == {"rw", "mode=755"})
        elif target == "/dev":
            valid = (valid and set(row["super_options"]) == {
                "rw", "size=4096k", "nr_inodes=65536", "mode=755"})
        else:
            valid = valid and check_parent(row, target)
        if valid:
            handled.add(row["mount_id"])
        else:
            reject(row, "system mount does not match its measured exact semantics")

    if cgroup_target:
        group = by_path.get(cgroup_target, [])
        mask = next((row for row in group if row["mount_id"] in handled
                     and row["mount_root"] == "/systemd/inaccessible/reg"), None)
        bases = [row for row in group if mask is None or row["mount_id"] != mask["mount_id"]]
        if mask is None:
            unapproved_mounts.append({"mountpoint": cgroup_target,
                                      "reason": "current-unit memory.pressure is not masked"})
        if len(bases) > 1:
            for row in bases:
                reject(row, "multiple current-unit memory.pressure base mounts")
        for row in bases:
            expected_root = "/system.slice/" + expected_unit + "/memory.pressure"
            parent = by_path.get("/sys/fs/cgroup", [])
            valid = (row["filesystem"] == "cgroup2" and row["source"] == "cgroup2"
                     and row["device"] == (parent[0]["device"] if len(parent) == 1 else None)
                     and row["mount_root"] == expected_root
                     and set(row["mount_options"]) == {"rw", "nosuid", "nodev", "noexec", "relatime"}
                     and len(parent) == 1 and row["parent_id"] == parent[0]["mount_id"]
                     and mask is not None and row["mount_id"] < mask["mount_id"])
            if valid:
                handled.add(row["mount_id"])
            else:
                reject(row, "current-unit memory.pressure base mount is unexpected")

    for row in rows:
        if row["mount_id"] not in handled and not any(
                item.get("row") == row["mount_id"] for item in unapproved_mounts):
            reject(row, "unrecognized mount row")
    return rows, windows_mounts, unapproved_mounts


def _systemd_unit_properties() -> dict[str, str]:
    props = ("LoadState", "ActiveState", "SubState", "Result", "MainPID", "ControlGroup",
             "PrivateDevices", "ProtectSystem",
             "ProtectKernelTunables", "ProtectKernelModules", "ProtectKernelLogs",
             "ProtectControlGroups", "NoNewPrivileges", "RuntimeMaxUSec", "InaccessiblePaths")
    result = record("current_transient_unit", ["/usr/bin/systemctl", "show", TRANSIENT_UNIT,
                   "--no-pager", *["--property=" + prop for prop in props]])
    output = _require_command(result, "transient-unit property verification")
    values = {}
    for line in output.decode("utf-8", "strict").splitlines():
        key, separator, value = line.partition("=")
        if not separator or key not in props or key in values:
            stop("systemd returned unknown or duplicate transient-unit properties")
        values[key] = value
    if set(values) != set(props):
        stop("systemd omitted a required transient-unit property")
    return values


def _verify_execution_unit() -> dict:
    if not re.fullmatch(r"vst-s2-qual-[0-9a-f]{16}\.service", TRANSIENT_UNIT):
        stop("transient unit identity is malformed")
    if os.geteuid() != 0:
        stop("isolated helper is not running as root")
    current_ns, init_ns = os.stat("/proc/self/ns/mnt"), os.stat("/proc/1/ns/mnt")
    if (current_ns.st_dev, current_ns.st_ino) == (init_ns.st_dev, init_ns.st_ino):
        stop("helper does not run in a distinct mount namespace")
    argv = pathlib.Path("/proc/self/cmdline").read_bytes().split(b"\0")
    if argv[-1:] == [b""]:
        argv.pop()
    if argv != [b"/usr/bin/python3.12", b"-I", b"-B", b"-S", b"-"]:
        stop("helper process command line differs from the approved interpreter")
    props = _systemd_unit_properties()
    expected_inaccessible = set(SYSTEMD_INACCESSIBLE_PATHS)
    expected_inaccessible.add(
        "/sys/fs/cgroup/system.slice/" + TRANSIENT_UNIT + "/memory.pressure")
    actual_inaccessible = {item.removeprefix("-") for item in props["InaccessiblePaths"].split()}
    expected = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "Result": "success", "MainPID": str(os.getpid()),
        "ControlGroup": "/system.slice/" + TRANSIENT_UNIT,
        "PrivateDevices": "yes", "ProtectSystem": "strict",
        "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
        "ProtectKernelLogs": "yes", "ProtectControlGroups": "yes",
        "NoNewPrivileges": "yes", "RuntimeMaxUSec": _expected_runtime_timeout(),
    }
    if any(props.get(key) != value for key, value in expected.items()):
        R["transient_unit_property_mismatch"] = {
            "expected": expected,
            "observed": {key: props.get(key) for key in expected},
        }
        stop("transient-unit identity or hardening properties differ from the exact profile")
    if actual_inaccessible != expected_inaccessible:
        R["inaccessible_path_mismatch"] = {
            "expected": sorted(expected_inaccessible),
            "observed": sorted(actual_inaccessible),
            "missing": sorted(expected_inaccessible - actual_inaccessible),
            "unexpected": sorted(actual_inaccessible - expected_inaccessible),
        }
        # In the read-only diagnostic mode, retain the mismatch but continue to
        # collect mountinfo. The audit result remains HOLD below; this does not
        # relax runtime qualification or permit a selector/service operation.
        if not MOUNT_AUDIT_ONLY:
            stop("transient-unit inaccessible path set differs from the exact approved target set")
    cgroup = pathlib.Path("/proc/self/cgroup").read_text(encoding="ascii").splitlines()
    if "0::/system.slice/" + TRANSIENT_UNIT not in cgroup:
        stop("helper cgroup does not identify its exact transient unit")
    try:
        candidate_fd_names = os.listdir("/proc/self/fd")
    except OSError as exc:
        stop("open file descriptors could not be enumerated: " + type(exc).__name__)
    fd_names = []
    for name in candidate_fd_names:
        if not name.isascii() or not name.isdecimal():
            stop("open file descriptor inventory contains a malformed entry")
        try:
            os.fstat(int(name))
        except OSError as exc:
            # The procfs enumeration can include its own temporary directory
            # descriptor. It is no longer open once listdir returns; ignore
            # only that EBADF snapshot race, never a descriptor still open.
            if exc.errno == errno.EBADF:
                continue
            stop("open file descriptor could not be inspected: " + type(exc).__name__)
        fd_names.append(name)
    fd_names.sort(key=int)
    if fd_names != ["0", "1", "2"]:
        R["open_fds_mismatch"] = {"expected": ["0", "1", "2"], "observed": fd_names}
        stop("helper has unexpected open file descriptors")
    return {"mount_namespace_distinct_from_pid1": True, "uid": os.geteuid(),
            "pid": os.getpid(), "unit": TRANSIENT_UNIT, "properties": props,
            "open_fds": fd_names, "cmdline": [item.decode("ascii") for item in argv]}


def _verify_private_dev(mount_rows: list[dict]) -> tuple[dict, list[str]]:
    expected_links = {
        "core": "/proc/kcore", "fd": "/proc/self/fd", "log": "/run/systemd/journal/dev-log",
        "stdin": "/proc/self/fd/0", "stdout": "/proc/self/fd/1", "stderr": "/proc/self/fd/2",
    }
    expected_devices = {"tty": (5, 0), "urandom": (1, 9), "random": (1, 8),
                        "full": (1, 7), "zero": (1, 5), "null": (1, 3), "ptmx": (5, 2)}
    expected_directories = {"char": (0o755, 0, 0), "hugepages": (0, 0, 0),
                            "mqueue": (0o1777, 0, 0), "pts": (0o755, 0, 0),
                            "shm": (0, 0, 0)}
    expected_char_aliases = {
        "1:3": "../null", "1:5": "../zero", "1:7": "../full",
        "1:8": "../random", "1:9": "../urandom", "5:0": "../tty", "5:2": "../ptmx",
    }
    expected_names = set(expected_links) | set(expected_devices) | set(expected_directories)
    entries = {}
    with os.scandir("/dev") as directory:
        names = {entry.name for entry in directory}
    failures = []
    if names != expected_names:
        failures.append("private /dev entry set differs from the exact allowlist")
    for name in sorted(expected_names - names):
        failures.append("private /dev allowlisted entry is missing: " + name)
    for name in sorted(names):
        path = "/dev/" + name
        info = os.lstat(path)
        metadata = {"uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)}
        if name in expected_links:
            if (not stat.S_ISLNK(info.st_mode) or os.readlink(path) != expected_links[name]
                    or metadata != {"uid": 0, "gid": 0, "mode": 0o777}):
                failures.append("private /dev symlink differs from its exact link/owner/mode: " + name)
            metadata["target"] = expected_links[name]
            metadata["type"] = "symlink"
        elif name in expected_devices:
            major, minor = expected_devices[name]
            if (not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != major
                    or os.minor(info.st_rdev) != minor
                    or metadata != {"uid": 0, "gid": 0, "mode": 0o666}):
                failures.append("private /dev device differs from its exact type/id/owner/mode: " + name)
            metadata.update(type="character", major=major, minor=minor)
        elif name in expected_directories:
            mode, uid, gid = expected_directories[name]
            if (not stat.S_ISDIR(info.st_mode) or metadata != {"uid": uid, "gid": gid, "mode": mode}):
                failures.append("private /dev directory differs from its exact type/owner/mode: " + name)
            metadata["type"] = "directory"
        else:
            failures.append("unexpected private /dev entry: " + name)
            metadata["type"] = "unexpected"
        entries[name] = metadata
    nested_entries = {}
    for directory_name in ("char", "hugepages", "mqueue", "pts", "shm"):
        path = "/dev/" + directory_name
        if directory_name not in names:
            continue
        observed = {}
        try:
            with os.scandir(path) as directory:
                children = sorted(directory, key=lambda entry: entry.name)
            for child in children:
                info = child.stat(follow_symlinks=False)
                child_metadata = {
                    "uid": info.st_uid, "gid": info.st_gid,
                    "mode": stat.S_IMODE(info.st_mode),
                    "type": ("character" if stat.S_ISCHR(info.st_mode) else
                             "block" if stat.S_ISBLK(info.st_mode) else
                             "symlink" if stat.S_ISLNK(info.st_mode) else
                             "directory" if stat.S_ISDIR(info.st_mode) else
                             "regular" if stat.S_ISREG(info.st_mode) else "other"),
                }
                if stat.S_ISCHR(info.st_mode) or stat.S_ISBLK(info.st_mode):
                    child_metadata.update(major=os.major(info.st_rdev), minor=os.minor(info.st_rdev))
                if stat.S_ISLNK(info.st_mode):
                    child_metadata["target"] = os.readlink(child.path)
                observed[child.name] = child_metadata
                if directory_name in {"hugepages", "shm"}:
                    failures.append("masked private /dev directory is not empty: " + directory_name)
                elif directory_name == "char":
                    if (child.name not in expected_char_aliases or not stat.S_ISLNK(info.st_mode)
                            or child_metadata.get("target") != expected_char_aliases.get(child.name)
                            or (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (0, 0, 0o777)):
                        failures.append("private /dev/char contains an unexpected alias: " + child.name)
                elif directory_name == "pts":
                    ptmx_ok = (child.name == "ptmx" and stat.S_ISCHR(info.st_mode)
                               and (os.major(info.st_rdev), os.minor(info.st_rdev)) == (5, 2)
                               and (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) == (0, 0, 0))
                    if not ptmx_ok:
                        failures.append("private /dev/pts contains an unexpected entry: " + child.name)
                elif directory_name == "mqueue" and not stat.S_ISREG(info.st_mode):
                    failures.append("private /dev/mqueue contains a non-regular entry: " + child.name)
        except OSError as exc:
            failures.append("private /dev directory could not be inspected: "
                            + directory_name + ": " + type(exc).__name__)
        nested_entries[directory_name] = observed
    dev_mountpoints = {row["mountpoint"] for row in mount_rows
                       if row["mountpoint"].startswith("/dev/")}
    allowed_mountpoints = {"/dev/pts", "/dev/mqueue", "/dev/hugepages", "/dev/shm"}
    if not dev_mountpoints <= allowed_mountpoints or not {"/dev/pts", "/dev/mqueue"} <= dev_mountpoints:
        failures.append("private /dev contains an unexpected or missing nested mount")
    return ({"entry_count": len(entries), "entries": entries,
             "nested_entries": nested_entries,
             "nested_mountpoints": sorted(dev_mountpoints)}, failures)


def _verify_effective_masks(mount_rows: list[dict]) -> tuple[dict, list[str]]:
    targets = set(SYSTEMD_MASK_TARGETS)
    if TRANSIENT_UNIT:
        targets.add("/sys/fs/cgroup/system.slice/" + TRANSIENT_UNIT + "/memory.pressure")
    by_path: dict[str, list[dict]] = {}
    for row in mount_rows:
        by_path.setdefault(row["mountpoint"], []).append(row)
    verified = {}
    failures = []
    for target in sorted(targets):
        expected_root = ("/systemd/inaccessible/reg" if target in SYSTEMD_MASK_FILES
                         or target.endswith("/memory.pressure") else "/systemd/inaccessible/dir")
        candidates = [row for row in by_path.get(target, [])
                      if row["mount_root"] == expected_root and row["filesystem"] == "tmpfs"
                      and row["source"] == "none"]
        if len(candidates) != 1:
            failures.append("effective inaccessible target is missing or ambiguous: " + target)
            continue
        row = candidates[0]
        flags = os.O_PATH | getattr(os, "O_CLOEXEC", 0)
        try:
            fd = os.open(target, flags)
        except OSError as exc:
            failures.append("effective inaccessible target cannot be opened: " + target + ": " + type(exc).__name__)
            continue
        try:
            info = os.fstat(fd)
            expected_type = stat.S_ISREG if expected_root.endswith("/reg") else stat.S_ISDIR
            if (not expected_type(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                    or stat.S_IMODE(info.st_mode) != 0):
                failures.append("effective inaccessible path has the wrong type/owner/mode: " + target)
                continue
            fdinfo = pathlib.Path("/proc/self/fdinfo/" + str(fd)).read_text(encoding="ascii")
            mount_id = None
            for line in fdinfo.splitlines():
                if line.startswith("mnt_id:"):
                    mount_id = int(line.partition(":")[2].strip())
                    break
            if mount_id != row["mount_id"]:
                failures.append("path resolves through a different mount than its mask row: " + target)
                continue
            verified[target] = {"mount_id": mount_id, "type": "regular" if expected_root.endswith("/reg") else "directory",
                                "uid": info.st_uid, "gid": info.st_gid,
                                "mode": stat.S_IMODE(info.st_mode)}
        except (OSError, ValueError) as exc:
            failures.append("effective inaccessible path metadata is unavailable: " + target + ": " + type(exc).__name__)
        finally:
            os.close(fd)
    return verified, failures


def _read_only_mount_audit() -> None:
    if not MOUNT_AUDIT_ONLY or not TRANSIENT_UNIT:
        stop("read-only mount audit identity is absent")
    unit = _verify_execution_unit()
    mountinfo = pathlib.Path("/proc/self/mountinfo").read_bytes()
    if len(mountinfo) > 8 * 1024 * 1024:
        stop("mount inventory exceeds its byte bound")
    raw = mountinfo.decode("utf-8", "strict")
    baseline_sha256 = hashlib.sha256(BASELINE_DECODER_SOURCE.encode("utf-8")).hexdigest()
    if (not BASELINE_DECODER_SOURCE or baseline_sha256 != BASELINE_DECODER_SHA256
            or not re.fullmatch(r"[0-9a-f]{40}", BASELINE_DECODER_REVISION)):
        stop("exact unchanged baseline parser is missing or not hash-bound")
    baseline_namespace = {"hashlib": hashlib, "re": re}
    exec(compile(BASELINE_DECODER_SOURCE, "<pinned-baseline-mount-decoder>", "exec"),
         baseline_namespace, baseline_namespace)
    try:
        baseline_rows, baseline_windows, baseline_rejections = baseline_namespace["_decode_mountinfo"](raw)
        baseline = {"row_count": len(baseline_rows), "windows_drive_rows": baseline_windows,
                    "rejected_rows": baseline_rejections}
    except Exception as exc:
        baseline_rows, baseline_windows = [], []
        baseline = {"row_count": 0, "windows_drive_rows": [], "rejected_rows": [],
                    "parser_error_type": type(exc).__name__,
                    "parser_error": str(exc)[:256]}
    rows, windows, rejected = _decode_mountinfo(raw, expected_unit=TRANSIENT_UNIT)
    effective_masks, mask_failures = _verify_effective_masks(rows)
    devices, device_failures = _verify_private_dev(rows)
    isolation_failures = mask_failures + device_failures
    inaccessible_path_mismatch = R.get("inaccessible_path_mismatch")
    audit_passed = (not inaccessible_path_mismatch and not windows and not rejected
                    and not isolation_failures)
    result = {
        "schema": "VST_S2_RUNTIME_MOUNT_AUDIT_V1",
        "terminal": "PASS" if audit_passed else "HOLD",
        "reason": ("candidate parser and effective-mask proofs passed"
                   if audit_passed else
                   "transient-unit inaccessible path set differs; mount inventory retained for diagnosis"
                   if inaccessible_path_mismatch else
                   "candidate parser or independent isolation proof rejected evidence"),
        "experiment_unit": unit, "baseline_revision": BASELINE_DECODER_REVISION,
        "baseline_parser_sha256": baseline_sha256,
        "mountinfo_sha256": hashlib.sha256(mountinfo).hexdigest(),
        "mountinfo_bytes": len(mountinfo), "mount_rows": rows,
        "inaccessible_path_mismatch": inaccessible_path_mismatch,
        "baseline": baseline,
        "candidate": {"row_count": len(rows), "windows_drive_rows": windows,
                      "rejected_rows": rejected},
        "isolation_failures": isolation_failures,
        "effective_masks": effective_masks, "private_dev": devices,
        "execution": unit,
        "runtime_selector_invocations": 0, "vst_service_starts": 0,
        "authorization_or_attempt_files_created": 0,
        "persistent_configuration_changes": 0,
    }
    R["mount_audit"] = result
    R["terminal"] = result["terminal"]
    R["reason"] = result["reason"]
    R["finished_utc"] = utc()


def _expected_runtime_timeout() -> str:
    return "1min" if MOUNT_AUDIT_ONLY else "40min"


def _secure_bytes(path: str, maximum: int = 8 * 1024 * 1024) -> bytes:
    before = os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_mode & 0o022 or before.st_size < 1 or before.st_size > maximum):
        raise ValueError("trusted file type, mode, link count, or size is invalid: " + path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("trusted file changed while opening: " + path)
        chunks = bytearray()
        while len(chunks) <= maximum:
            part = os.read(fd, min(65536, maximum + 1 - len(chunks)))
            if not part:
                break
            chunks.extend(part)
        after = os.fstat(fd)
        if (len(chunks) != opened.st_size or len(chunks) > maximum
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)):
            raise ValueError("trusted file changed while reading: " + path)
        return bytes(chunks)
    finally:
        os.close(fd)


def _json_file(path: str, maximum: int = 2 * 1024 * 1024) -> dict:
    value = json.loads(_secure_bytes(path, maximum), object_pairs_hook=_pairs,
                       parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: " + path)
    return value


def _tree_digest(root: str, expected: dict[str, str]) -> None:
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != 0 or root_info.st_mode & 0o022:
        raise ValueError("versioned runtime root is not root-controlled")
    for rel, digest in expected.items():
        path = os.path.join(root, *rel.split("/"))
        data = _secure_bytes(path, 16 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("runtime source hash mismatch: " + rel)


def _config_identity(identity: dict) -> tuple[dict, dict, dict]:
    for path, expected in identity["config_sha256"].items():
        data = _secure_bytes(path)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("configuration hash mismatch: " + path)
    config = _json_file("/etc/vst-runner/supervisor-service.json")
    bootstrap = _json_file("/etc/vst-runner/bootstrap-request.json")
    task_manifest = _json_file("/etc/vst-runner/task-manifest.json")
    profile = _json_file("/etc/vst-runner/network-profile.json")
    policy = _json_file("/etc/vst-runner/assignment-delegation-policy.json")
    selector = identity["selector_test_id"]
    if (config.get("run_id") != identity["run_id"]
            or config.get("probe_nonce") != identity["nonce"]
            or config.get("store_path") != "/var/lib/vst-runner/private/store.sqlite3"
            or bootstrap.get("request_id") != identity["bootstrap_request_id"]
            or bootstrap.get("run_id") != identity["run_id"]
            or task_manifest.get("task_id") != "S2-4-runtime-owner-runner-qualification"
            or task_manifest.get("story_id") != "S2-4"
            or task_manifest.get("retry_cap") != 0
            or task_manifest.get("required_tests") != [
                {"slot": "runtime-tests", "test_id": selector,
                 "acceptance": task_manifest.get("acceptance")}
            ]
            or bootstrap.get("task_manifest") != task_manifest
            or task_manifest.get("task_id") != bootstrap.get("task_id")
            or task_manifest.get("story_id") != bootstrap.get("story_id")
            or profile.get("external_allowlist") != []
            or profile.get("environment_id") != "Ubuntu-24.04:S2:" + identity["run_id"]
            or policy.get("source_head") != identity["runtime_source_head"]
            or policy.get("allowed_assignments", [{}])[0].get("task_manifest_sha256")
               != identity["task_manifest_sha256"]):
        raise ValueError("runtime configuration does not match the one-shot authorization tuple")
    manifest_hash = hashlib.sha256(_canonical(task_manifest)).hexdigest()
    config_bundle_hash = hashlib.sha256(_canonical(identity["config_sha256"])).hexdigest()
    if (manifest_hash != identity["task_manifest_sha256"]
            or config_bundle_hash != identity["config_bundle_sha256"]):
        raise ValueError("task manifest or complete configuration hash map differs")
    return config, bootstrap, task_manifest


def _runtime_identity(identity: dict) -> None:
    selector = identity["runtime_selector"]
    if selector != "/opt/vst-runtime-" + identity["runtime_source_head"]:
        raise ValueError("runtime selector is not the full-hash versioned identity")
    marker = _json_file(selector + "/.vst-runtime-manifest.json", 65536)
    if (marker.get("schema") != 3 or marker.get("head") != identity["runtime_source_head"]
            or marker.get("archive_sha256") != identity["bundle_sha256"]):
        raise ValueError("installed runtime marker differs from the authorized runtime bundle")
    link = os.lstat("/opt/vst-runtime")
    if not stat.S_ISLNK(link.st_mode) or os.readlink("/opt/vst-runtime") != selector:
        raise ValueError("active runtime symlink does not select the distinct authorized runtime")
    _tree_digest(selector, AUTH["source_pins"]["runtime"])


def _systemd_show(unit: str) -> dict:
    raw = _require_command(record("unit:" + unit, [
        "/usr/bin/systemctl", "show", unit, "--property=LoadState", "--property=ActiveState",
        "--property=SubState", "--property=Result", "--property=MainPID", "--value",
    ]), "systemd inventory")
    lines = raw.decode("utf-8", "replace").splitlines()
    if len(lines) != 5:
        stop("systemd returned a malformed unit inventory")
    return dict(zip(("LoadState", "ActiveState", "SubState", "Result", "MainPID"), lines))


def _prestart_inventory(identity: dict) -> dict:
    execution = _verify_execution_unit()
    try:
        mountinfo_bytes = pathlib.Path("/proc/self/mountinfo").read_bytes()
        if len(mountinfo_bytes) > 8 * 1024 * 1024:
            raise ValueError("complete mount inventory exceeds its byte bound")
        mountinfo = mountinfo_bytes.decode("utf-8", "strict")
        mount_rows, windows_mounts, unapproved_mounts = _decode_mountinfo(
            mountinfo, expected_unit=TRANSIENT_UNIT)
        effective_masks, mask_failures = _verify_effective_masks(mount_rows)
        private_dev, device_failures = _verify_private_dev(mount_rows)
    except Exception as exc:
        stop("complete mount inventory is unavailable: " + type(exc).__name__ + ": " + str(exc)[:256])
    R["prestart"]["mount_inventory"] = {
        "rows": mount_rows, "row_count": len(mount_rows),
        "unapproved_host_mounts": unapproved_mounts,
        "sha256": hashlib.sha256(mountinfo_bytes).hexdigest(),
        "execution_unit": execution,
        "effective_masks": effective_masks,
        "private_dev": private_dev,
    }
    if windows_mounts:
        stop("Windows drive mount detected in complete mount inventory")
    if unapproved_mounts:
        stop("unapproved host mount detected in complete mount inventory")
    if mask_failures or device_failures:
        stop("independent mask/device verification failed: "
             + "; ".join((mask_failures + device_failures)[:8]))
    if len(mount_rows) < 4:
        stop("mount inventory is outside expected bounds")

    if pathlib.Path("/proc/1/comm").read_text(encoding="ascii").strip() != "systemd":
        stop("WSL PID 1 is not systemd")
    # No runtime, service, key, or configuration path is read until every
    # mountinfo row has been inspected for Windows-backed mounts.
    config = _json_file("/etc/vst-runner/supervisor-service.json")
    runtime = identity["runtime_selector"]
    _runtime_identity(identity)
    _config_identity(identity)
    # Verify the deployment plan's complete no-symlink source inventory.
    source_manifest = _json_file(runtime + "/.vst-source-manifest.json", 8 * 1024 * 1024)
    runtime_manifest = _json_file(runtime + "/.vst-runtime-manifest.json", 65536)
    verify = ["/usr/bin/python3.12", "-I", "-B", "-S",
              runtime + "/tools/qa/verify_wsl_source_bundle.py",
              "--root", runtime, "--expected-head", identity["runtime_source_head"],
              "--archive-sha256", identity["bundle_sha256"],
              "--plan-sha256", runtime_manifest["plan_sha256"],
              "--inventory-sha256", runtime_manifest["inventory_sha256"]]
    _require_command(record("full_runtime_source_verification", verify, timeout=120),
                     "complete installed source verification")
    R["prestart"]["runtime_source_manifest"] = {
        "schema": source_manifest.get("schema"),
        "archive_sha256": runtime_manifest.get("archive_sha256"),
        "head": runtime_manifest.get("head"),
        "inventory_sha256": runtime_manifest.get("inventory_sha256"),
        "plan_sha256": runtime_manifest.get("plan_sha256"),
    }

    unit_rows = {}
    for unit in EXPECTED_UNITS:
        unit_rows[unit] = _systemd_show(unit)
        row = unit_rows[unit]
        if (row["LoadState"] != "loaded" or row["ActiveState"] != "inactive"
                or row["SubState"] != "dead" or row["MainPID"] not in {"", "0"}):
            stop("all runtime and preflight units must be loaded and inactive before activation")
    jobs = _require_command(record("systemd_jobs", [
        "/usr/bin/systemctl", "list-jobs", "--no-legend", "--no-pager",
    ]), "systemd job inventory")
    if jobs.strip():
        stop("systemd has a pending job before activation")
    manager = _require_command(record("systemd_manager_state", [
        "/usr/bin/systemctl", "is-system-running",
    ]), "systemd manager state")
    if manager.strip() != b"running":
        stop("systemd manager is not in the exact running state")
    R["prestart"]["units"] = unit_rows
    R["prestart"]["systemd_jobs"] = 0

    forbidden_paths = [
        config["store_path"],
        "/run/vst-supervisor/supervisor.sock", OWNER_SOCKET,
        "/run/vst-runner/runner.sock", "/etc/vst-runner/issuance-request.json",
    ]
    presence = {path: os.path.lexists(path) for path in forbidden_paths}
    R["prestart"]["path_presence"] = presence
    if any(presence.values()):
        stop("Store, socket, or derived issuer-request state already exists")
    R["prestart"]["verdict"] = "PASS_BEFORE_ANY_RUNTIME_SERVICE_START"
    return config


def _start_service(unit: str, timeout: float = 45.0) -> dict:
    result = record("start:" + unit, ["/usr/bin/systemctl", "start", unit], timeout=timeout)
    _require_command(result, "one-time service start for " + unit)
    state = _systemd_show(unit)
    if state["LoadState"] != "loaded" or state["ActiveState"] != "active":
        stop("service did not become active after its one allowed start: " + unit)
    R["stages"].setdefault("service_starts", []).append({"unit": unit, "state": state})
    return state


def _journal_objects(unit: str, since: str) -> list[dict]:
    result = record("journal:" + unit, [
        "/usr/bin/journalctl", "-u", unit, "--no-pager", "-o", "cat", "--since", since,
    ], timeout=30)
    raw = _require_command(result, "bounded journal capture")
    values = []
    for line in raw.splitlines():
        try:
            item = json.loads(line, object_pairs_hook=_pairs)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(item, dict):
            values.append(item)
    return values


def _one_match(rows: list[dict], predicate, label: str) -> dict:
    selected = [row for row in rows if predicate(row)]
    if len(selected) != 1:
        stop(label + " was absent or ambiguous; no replacement operation will be attempted")
    return selected[0]


def _run_bootstrap(identity: dict, manifest: dict) -> dict:
    since = "@" + str(time.time() - 2)
    result = record("start:assignment-bootstrap", [
        "/usr/bin/systemctl", "start", "vst-assignment-bootstrap.service",
    ], timeout=45)
    _require_command(result, "single authenticated assignment bootstrap")
    objects = _journal_objects("vst-assignment-bootstrap.service", since)
    handoff = _one_match(objects, lambda row:
        row.get("run_id") == identity["run_id"]
        and row.get("bootstrap_request", {}).get("request_id") == identity["bootstrap_request_id"],
        "authenticated bootstrap handoff")
    if (handoff.get("task_id") != manifest.get("task_id")
            or handoff.get("story_id") != manifest.get("story_id")
            or handoff.get("slot") != "runtime-tests" or handoff.get("attempt") != 1
            or handoff.get("run_id") != identity["run_id"]
            or handoff.get("bootstrap_request", {}).get("task_manifest") != manifest
            or not isinstance(handoff.get("assignment_operation_id"), str)
            or not HEX64.fullmatch(handoff["assignment_operation_id"])):
        R["stages"]["bootstrap_handoff"] = {"sha256": hashlib.sha256(_canonical(handoff)).hexdigest()}
        stop("bootstrap handoff differs from the exact authorized task and identity")
    R["stages"]["bootstrap"] = {
        "handoff": handoff,
        "handoff_sha256": hashlib.sha256(_canonical(handoff)).hexdigest(),
        "verdict": "PASS",
    }
    return handoff


def _create_issuer_request(handoff: dict) -> dict:
    path = "/etc/vst-runner/issuance-request.json"
    if os.path.lexists(path):
        stop("derived issuer request already exists; refusing overwrite")
    issuer = __import__("pwd").getpwnam("vst-dispatch-issuer")
    issuer_group = grp.getgrnam("vst-dispatch-issuer")
    body = _canonical({"assignment_operation_id": handoff["assignment_operation_id"]})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fchown(fd, 0, issuer_group.gr_gid)
        os.fchmod(fd, 0o640)
        written = os.write(fd, body)
        if written != len(body):
            stop("short write while creating one-shot issuer input")
        os.fsync(fd)
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if info.st_uid != 0 or info.st_gid != issuer_group.gr_gid or stat.S_IMODE(info.st_mode) != 0o640:
        stop("derived issuer input ownership does not match the provisioned layout")
    result = {"path": path, "uid": info.st_uid, "gid": info.st_gid,
              "mode": format(stat.S_IMODE(info.st_mode), "04o"),
              "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
              "issuer_uid": issuer.pw_uid}
    R["stages"]["issuer_request"] = result
    return result


def _run_issuer(handoff: dict, identity: dict) -> dict:
    _create_issuer_request(handoff)
    since = "@" + str(time.time() - 2)
    result = record("start:dispatch-issuer", [
        "/usr/bin/systemctl", "start", "vst-dispatch-issuer.service",
    ], timeout=45)
    _require_command(result, "single root-bound dispatch issuance")
    objects = _journal_objects("vst-dispatch-issuer.service", since)
    instruction = _one_match(objects, lambda row:
        row.get("task_id") == handoff["task_id"]
        and row.get("run_id") == identity["run_id"]
        and row.get("slot") == handoff["slot"]
        and row.get("attempt") == handoff["attempt"], "signed dispatch instruction")
    if (not isinstance(instruction.get("signature"), str) or not instruction["signature"]
            or instruction.get("epoch") != handoff.get("epoch")
            or instruction.get("run_id") != identity["run_id"]
            or instruction.get("slot") != "runtime-tests"
            or instruction.get("attempt") != 1
            or not isinstance(instruction.get("request_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", instruction["request_id"])):
        stop("issuer result is not a signed instruction for this exact handoff")
    R["stages"]["dispatch_instruction"] = {
        "instruction": instruction,
        "sha256": hashlib.sha256(_canonical(instruction)).hexdigest(),
    }
    return instruction


def _owner_submit(instruction: dict, identity: dict) -> dict:
    runtime = identity["runtime_selector"]
    sys.path.insert(0, runtime)
    from tools.vst.assignment_basis import validate_policy
    from tools.vst.dispatch_issuance import issuance_identity
    from tools.vst.dispatch_instruction import validate_dispatch_instruction
    from tools.vst.dispatch_owner_transport import DispatchOwnerSocketClient

    policy = validate_policy(_json_file("/etc/vst-runner/assignment-delegation-policy.json"))[0]
    expected = issuance_identity(
        R["stages"]["bootstrap"]["handoff"], policy={
            "policy": policy,
            "policy_sha256": hashlib.sha256(_canonical(policy)).hexdigest(),
        }, now=datetime.datetime.now(datetime.timezone.utc),
    )
    envelope = validate_dispatch_instruction(instruction)
    if (envelope["request_id"] != expected["request_id"]
            or envelope["task_id"] != R["stages"]["bootstrap"]["handoff"]["task_id"]
            or envelope["run_id"] != identity["run_id"]
            or envelope["slot"] != "runtime-tests" or envelope["attempt"] != 1):
        stop("signed instruction is not the exact issuance for the authenticated handoff")
    owner_config = _json_file("/etc/vst-runner/dispatch-owner-service.json")
    socket_stat = os.stat(os.path.dirname(OWNER_SOCKET), follow_symlinks=False)
    client = DispatchOwnerSocketClient(
        expected_principal=owner_config["principal"], expected_socket_gid=socket_stat.st_gid,
    )
    # This is the sole Owner submission. The transport returns a durable,
    # correlated Supervisor acceptance or raises an unknown outcome; no retry.
    accepted = client.submit_signed_instruction(envelope)
    if (accepted.get("instruction") != envelope
            or accepted.get("request_id") != envelope["request_id"]
            or accepted.get("run_id") != identity["run_id"]):
        stop("dispatch owner response does not prove acceptance of the exact instruction")
    R["stages"]["owner_submission"] = {
        "request_id": envelope["request_id"],
        "instruction_sha256": hashlib.sha256(_canonical(envelope)).hexdigest(),
        "event_seq": accepted.get("event_seq"),
        "payload_digest": accepted.get("payload_digest"),
        "service_generation": accepted.get("service_generation"),
        "verdict": "DURABLY_ACCEPTED",
    }
    return accepted


def _read_task_rows(store_path: str, task_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    uri = "file:" + urllib.parse.quote(store_path, safe="/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=1)
    db.row_factory = sqlite3.Row
    try:
        claims = [dict(row) for row in db.execute(
            "SELECT grant_id,invocation_id,request_id,task_id,slot,runner_id,attempt,epoch,run_id,"
            "service_generation,manifest_sha256,payload_sha256,grant_body,claimed_at "
            "FROM runner_execution_claims WHERE task_id=?", (task_id,))]
        events = []
        receipts = []
        if claims:
            events = [dict(row) for row in db.execute(
                "SELECT grant_id,state,payload,created_at FROM runner_execution_events "
                "WHERE grant_id IN (SELECT grant_id FROM runner_execution_claims WHERE task_id=?) "
                "ORDER BY seq", (task_id,))]
            receipts = [dict(row) for row in db.execute(
                "SELECT slot,attempt,epoch,receipt_sha256,prev_receipt_sha256,body "
                "FROM receipts WHERE task_id=? ORDER BY seq", (task_id,))]
        return claims, events, receipts
    finally:
        db.close()


def _wait_for_test_run(config: dict, manifest: dict, instruction: dict,
                       identity: dict) -> dict:
    runtime = identity["runtime_selector"]
    sys.path.insert(0, runtime)
    from tools.vst.contracts import canonical_bytes, receipt_sha256, validate_receipt
    from tools.vst.execution_grant import validate_execution_grant
    from tools.vst.supervisor_service import SupervisorClient

    deadline = time.monotonic() + min(600.0, float(manifest.get("timeout_sec", 120)) + 60.0)
    task_id = manifest["task_id"]
    claim = None
    events = []
    receipts = []
    snapshots = []
    while time.monotonic() < deadline:
        claims, events, receipts = _read_task_rows(config["store_path"], task_id)
        snapshots.append({"utc": utc(), "claims": len(claims),
                          "event_states": [row["state"] for row in events],
                          "receipts": len(receipts)})
        if len(claims) > 1 or len(receipts) > 1:
            stop("multiple durable claims or TestRun receipts exist; no retry")
        if claims:
            claim = claims[0]
            try:
                grant = validate_execution_grant(json.loads(claim["grant_body"], object_pairs_hook=_pairs))
                grant_bytes = canonical_bytes(grant)
                grant_digest = hashlib.sha256(grant_bytes).hexdigest()
                event_payloads = [json.loads(row["payload"], object_pairs_hook=_pairs) for row in events]
            except Exception as exc:
                stop("durable Runner claim or execution grant is malformed: " + type(exc).__name__)
            fields = ("grant_id", "invocation_id", "request_id", "task_id", "slot", "runner_id",
                      "attempt", "epoch", "run_id", "service_generation", "manifest_sha256")
            column_binding = all(claim.get(field) == grant.get(field) for field in fields)
            handoff = R["stages"]["bootstrap"]["handoff"]
            tuple_binding = (
                grant.get("request_id") == instruction.get("request_id")
                and grant.get("task_id") == task_id
                and grant.get("slot") == "runtime-tests"
                and grant.get("runner_id") == handoff.get("runner_id")
                and grant.get("attempt") == 1
                and grant.get("epoch") == handoff.get("epoch")
                and grant.get("run_id") == identity["run_id"]
                and grant.get("manifest_sha256") == identity["task_manifest_sha256"]
                and grant.get("service_generation") == claim.get("service_generation")
                and claim.get("payload_sha256") == grant_digest
                and claim.get("claimed_at") is not None
            )
            states = [row["state"] for row in events]
            pending = {
                "event": "RUNNER_EXECUTION_PENDING", "state": "PENDING",
                "grant_id": grant.get("grant_id"), "invocation_id": grant.get("invocation_id"),
                "request_id": grant.get("request_id"), "task_id": grant.get("task_id"),
                "slot": grant.get("slot"), "runner_id": grant.get("runner_id"),
                "attempt": grant.get("attempt"), "epoch": grant.get("epoch"),
                "service_generation": grant.get("service_generation"),
                "run_id": grant.get("run_id"), "payload_sha256": grant_digest,
            }
            reserved = {
                "event": "RUNNER_EXECUTION_RESERVED", "state": "EXECUTION_RESERVED",
                "grant_id": grant.get("grant_id"), "payload_sha256": grant_digest,
                "invocation_id": grant.get("invocation_id"),
                "request_id": grant.get("request_id"),
                "service_generation": grant.get("service_generation"),
            }
            event_binding = (
                states in (["PENDING"], ["PENDING", "EXECUTION_RESERVED"])
                and event_payloads[0] == pending
                and (len(event_payloads) == 1 or event_payloads[1] == reserved)
            )
            client = SupervisorClient(config.get("socket_path", "/run/vst-supervisor/supervisor.sock"))
            live_generation = client.generation()
            claim_status = client.claim_status(grant)
            status_binding = (
                live_generation == grant.get("service_generation")
                and claim_status.get("service_generation") == grant.get("service_generation")
                and claim_status.get("state") in {"PENDING", "EXECUTION_RESERVED"}
            )
            R["stages"]["runner_claim"] = {
                "claim": claim, "grant": grant, "event_states": states,
                "event_payloads": event_payloads, "live_generation": live_generation,
                "claim_status": claim_status, "column_binding": column_binding,
                "tuple_binding": tuple_binding, "event_binding": event_binding,
                "status_binding": status_binding,
            }
            if not all((column_binding, tuple_binding, event_binding, status_binding)):
                stop("durable Runner claim is not bound to the exact authorization tuple")
            R["stages"]["runner_claim"]["verdict"] = "PASS"
            break
        time.sleep(0.25)
    if claim is None:
        R["stages"]["claim_observations"] = snapshots[-16:]
        stop("no durable Runner claim appeared before the bounded deadline; no retry")

    # Dispatcher/Runner owns execution. This code only observes the one durable
    # receipt and never directly invokes pytest or launches a child test process.
    while time.monotonic() < deadline:
        _claims, events, receipts = _read_task_rows(config["store_path"], task_id)
        if len(receipts) > 1:
            stop("multiple TestRun receipts appeared; no retry")
        if len(receipts) == 1:
            break
        state = _systemd_show("vst-runner.service")
        R["commands"].append({"id": "runner_status_poll", "state": state, "utc": utc()})
        if state.get("LoadState") != "loaded" or state.get("ActiveState") != "active":
            stop("Runner became inactive before producing the terminal TestRun receipt")
        time.sleep(0.25)
    else:
        stop("report-bound TestRun did not finish before the bounded deadline; no retry")

    row = receipts[0]
    receipt = validate_receipt(json.loads(row["body"], object_pairs_hook=_pairs))
    computed = receipt_sha256(receipt)
    selector = identity["selector_test_id"]
    expected_candidate_head = manifest.get("base_head")
    if not isinstance(expected_candidate_head, str) or not HEX40.fullmatch(expected_candidate_head):
        stop("authorized TaskManifest base_head is not a valid candidate revision")
    diff_gate = receipt["diff_gate"]
    attestation_request = receipt["runner_attestation"]["request"]
    accepted = (
        computed == row["receipt_sha256"]
        and receipt.get("receipt_type") == "TestRun"
        and receipt.get("result") == "PASS"
        and receipt.get("task_id") == task_id
        and receipt.get("slot") == "runtime-tests"
        and receipt.get("attempt") == 1
        and receipt.get("candidate_head") == expected_candidate_head
        and receipt.get("run_id") == identity["run_id"]
        and receipt.get("manifest_sha256") == identity["task_manifest_sha256"]
        and diff_gate["verdict"] == "PASS"
        and diff_gate["candidate_head"] == expected_candidate_head
        and diff_gate["manifest_sha256"] == identity["task_manifest_sha256"]
        and attestation_request["candidate_head"] == expected_candidate_head
        and attestation_request["manifest_sha256"] == identity["task_manifest_sha256"]
        and receipt.get("expected_test_ids") == [selector]
        and receipt.get("executed_test_ids") == [selector]
        and receipt.get("skipped_test_ids") == []
        and receipt.get("xfail_test_ids") == []
    )
    R["stages"]["test_run"] = {
        "verdict": "PASS" if accepted else "FAIL", "receipt": receipt,
        "stored_receipt_sha256": row["receipt_sha256"],
        "computed_receipt_sha256": computed, "selector": selector,
        "runner_event_states": [event["state"] for event in events],
    }
    if not accepted:
        stop("one report-bound TestRun did not produce the exact authorized PASS receipt")
    return receipt


_identity = AUTH.get("identity", {}) if isinstance(AUTH, dict) else {}
_authorization = AUTH.get("authorization", {}) if isinstance(AUTH, dict) else {}
R = {
    "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
    "authorization_request_id": _authorization.get("request_id"),
    "authorization_reply_id": _authorization.get("reply_id"),
    "identity": {key: _identity[key] for key in (
        "runtime_source_head", "run_id", "bootstrap_request_id",
        "nonce", "runtime_selector", "bundle_sha256", "config_bundle_sha256",
        "task_manifest_sha256", "selector_test_id") if key in _identity},
    "started_utc": utc(), "commands": [], "prestart": {}, "stages": {},
    "terminal": None, "retry_cap": 0,
}

try:
    if MOUNT_AUDIT_ONLY:
        _read_only_mount_audit()
    else:
        if not isinstance(AUTH, dict) or "identity" not in AUTH or "authorization" not in AUTH:
            stop("runtime authorization tuple is absent")
        supervisor_config = _prestart_inventory(AUTH["identity"])
        # Source/config/host observations and inactive checks are the
        # qualification boundary; no Runner-signed probe is a prerequisite here.
        _start_service("vst-supervisor.service")
        _start_service("vst-signer.service")
        _start_service("vst-runner.service")
        _start_service("vst-dispatch-owner.socket")
        _start_service("vst-dispatcher.service")
        handoff = _run_bootstrap(AUTH["identity"], _json_file("/etc/vst-runner/task-manifest.json"))
        instruction = _run_issuer(handoff, AUTH["identity"])
        _owner_submit(instruction, AUTH["identity"])
        _wait_for_test_run(supervisor_config,
                           _json_file("/etc/vst-runner/task-manifest.json"),
                           instruction, AUTH["identity"])
        R["terminal"] = "PASS"
        R["reason"] = "Exact one-shot mount-free host checks and real Owner-to-Runner TestRun completed."
except Hold:
    pass
except BaseException as exc:
    R["terminal"] = "HOLD"
    R["reason"] = "protocol exception: " + type(exc).__name__ + ": " + str(exc)[:384]
finally:
    R["finished_utc"] = utc()
    R["zero_retry_confirmed"] = True
    R["top_level_wsl_processes"] = 1

encoded = _canonical(R)
if len(encoded) > MAX_REPORT_BYTES:
    minimal = {
        "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
        "terminal": "HOLD", "reason": "protocol evidence exceeded its output bound",
        "report_bytes": len(encoded), "report_sha256": hashlib.sha256(encoded).hexdigest(),
        "started_utc": R["started_utc"], "finished_utc": R["finished_utc"],
        "zero_retry_confirmed": True, "top_level_wsl_processes": 1,
    }
    R = minimal
    encoded = _canonical(R)
sys.stdout.buffer.write(encoded)
sys.stdout.buffer.flush()
raise SystemExit(0 if R.get("terminal") == "PASS" else 2)
