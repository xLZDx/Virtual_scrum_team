"""Collect and sign root observations for one live systemd sandbox probe."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

if Path("/opt/vst-runtime").is_dir():
    sys.path.insert(0, "/opt/vst-runtime")

from tools.vst.contracts import ContractError, canonical_bytes, manifest_sha256
from tools.vst.preflight import SPEC_PATH, sign_network_policy_attestation
from tools.vst.runner_service import _read_root_controlled_json
from tools.vst.supervisor_service import DEFAULT_CONFIG_PATH, _read_controlled_json, _read_root_key
from tools.vst.preflight_capture import capture_probe_invocation

PROBE_UNIT = "vst-sandbox-probe.service"
PROBE_REQUEST_PATH = "/etc/vst-runner/probe-request.json"
ATTESTATION_PATH = "/run/vst-preflight/network-policy-attestation.json"
NETWORK_PROFILE_PATH = "/etc/vst-runner/network-profile.json"
BOOTSTRAP_REQUEST_PATH = "/etc/vst-runner/bootstrap-request.json"
PROBE_UNIT_PATH = "/etc/systemd/system/vst-sandbox-probe.service"
PROBE_DROPIN_PATH = "/etc/systemd/system/vst-sandbox-probe.service.d/90-s2-host-path-mask.conf"
SYSTEMCTL = "/usr/bin/systemctl"
NSENTER = "/usr/bin/nsenter"
IP = "/usr/sbin/ip"
RUNTIME_SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"
PROBE_UNIT_SHA256 = "d80c171238985ffcc7f19c6eac74276c7ea7615ebf85d63391b6f2dbf097f33f"
PROBE_DROPIN_SHA256 = "8cb6b2fa46e2eaea1854cfc29a1d12725da3dfefb3383cbcb302b76e3b4b0062"
DEPENDENT_UNITS = (
    "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
    "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
    "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
)
REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_RELATIVE_PATH = "tools/vst/preflight_host_capture.py"
GIT_OID = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AttestationPublishError(ContractError):
    def __init__(self, message: str, identity: tuple[int, int, str]):
        super().__init__(message)
        self.published_identity = identity
RETIRED_RUN_IDENTITIES = {
    ("3e56a61c5b1e45aea089c305b25e3187",
     "s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8",
     "0d2bb2c5f977478a924f7ec6629a339d"),
}
INVOCATION_ID = re.compile(r"^[0-9a-f]{32}$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
NONCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CONTAINER_SOCKET_NAMES = (
    "/run/docker.sock", "/var/run/docker.sock", "/run/containerd/containerd.sock",
    "/run/podman/podman.sock",
)
MASKED_HOST_PATHS = ("/init", "/home", "/mnt", "/root", "/usr/lib/wsl",
                     "/run/WSL", "/tmp/.X11-unix")


def _run(argv: list[str], *, timeout: float = 5.0,
         run: Callable[..., Any] = subprocess.run) -> subprocess.CompletedProcess[str]:
    if not argv or any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise ContractError("invalid typed command arguments")
    try:
        result = run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                     check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError("required observation command failed") from exc
    if result.returncode != 0:
        raise ContractError("required observation command returned non-zero")
    return result


def _systemctl_show(unit: str, *, run: Callable[..., Any] = subprocess.run) -> dict[str, str]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_.@-]{0,127}", unit):
        raise ContractError("invalid systemd unit name")
    raw = _run([SYSTEMCTL, "show", unit,
                "--property=LoadState,ActiveState,SubState,Result,MainPID,InvocationID,ControlGroup,PrivateNetwork"],
               run=run).stdout
    values: dict[str, str] = {}
    for line in raw.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key in values:
            raise ContractError("systemd unit properties are malformed or duplicated")
        values[key] = value
    required = {"LoadState", "ActiveState", "SubState", "Result",
                "InvocationID", "ControlGroup", "PrivateNetwork"}
    # systemd socket units have no process of their own and omit MainPID.
    # Keep the field mandatory for services, including the probe unit.
    if not unit.endswith(".socket"):
        required.add("MainPID")
    if set(values) != required:
        raise ContractError("systemd unit properties are incomplete")
    return values


def _systemd_ready(*, run: Callable[..., Any] = subprocess.run,
                   allow_probe_start_job: bool = False) -> dict[str, Any]:
    state = _run([SYSTEMCTL, "is-system-running"], run=run).stdout.strip()
    if state != "running":
        raise ContractError("systemd is not in the running state")
    jobs = _run([SYSTEMCTL, "list-jobs", "--no-legend", "--plain"], run=run).stdout.strip()
    if jobs not in ("", "No jobs running."):
        rows = [line.split() for line in jobs.splitlines()]
        valid_probe_job = (allow_probe_start_job and len(rows) == 1 and len(rows[0]) == 4
                           and rows[0][0].isdigit() and rows[0][1] == PROBE_UNIT
                           and rows[0][2] == "start"
                           and rows[0][3] in {"waiting", "running"})
        if not valid_probe_job:
            raise ContractError("systemd has an unexpected pending job")
    if os.path.lexists("/run/systemd/shutdown/scheduled"):
        raise ContractError("systemd shutdown is already scheduled")
    return _pid1_identity()


def _verify_probe_unit_files() -> None:
    for path, expected_sha256 in ((PROBE_UNIT_PATH, PROBE_UNIT_SHA256),
                                  (PROBE_DROPIN_PATH, PROBE_DROPIN_SHA256)):
        try:
            info = os.stat(path, follow_symlinks=False)
            if (not os.path.isfile(path) or os.path.islink(path) or info.st_uid != 0
                    or info.st_gid != 0 or (info.st_mode & 0o777) != 0o644):
                raise ContractError("installed probe unit file has unsafe metadata")
            raw = Path(path).read_bytes()
        except OSError as exc:
            raise ContractError("pinned probe unit file is unavailable") from exc
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ContractError("installed probe unit differs from the pinned systemd contract")


def _assert_dependents_inactive(*, run: Callable[..., Any] = subprocess.run) -> None:
    for unit in DEPENDENT_UNITS:
        props = _systemctl_show(unit, run=run)
        if props["LoadState"] != "loaded" or props["ActiveState"] != "inactive":
            raise ContractError("runtime dependent is missing or no longer inactive: " + unit)


def _probe_inactive_for_rollback(invocation_id: str,
                                *, run: Callable[..., Any] = subprocess.run) -> bool:
    try:
        props = _systemctl_show(PROBE_UNIT, run=run)
    except ContractError:
        return False
    return (props["LoadState"] == "loaded" and props["ActiveState"] == "inactive"
            and props["MainPID"] in ("", "0")
            and props["InvocationID"] in ("", invocation_id))


def _pid1_identity() -> dict[str, Any]:
    try:
        comm = Path("/proc/1/comm").read_text(encoding="ascii").strip()
        stat_raw = Path("/proc/1/stat").read_text(encoding="ascii")
        tail = stat_raw[stat_raw.rfind(")") + 2:].split()
        start_ticks = int(tail[19])
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        net_ns_inode = os.stat("/proc/1/ns/net").st_ino
        mount_ns_inode = os.stat("/proc/1/ns/mnt").st_ino
    except (OSError, ValueError, IndexError) as exc:
        raise ContractError("WSL PID 1 identity cannot be established") from exc
    if comm != "systemd" or not INVOCATION_ID.fullmatch(boot_id.replace("-", "")):
        raise ContractError("systemd PID 1 or boot identity is invalid")
    return {"boot_id": boot_id, "pid": 1, "start_ticks": start_ticks,
            "net_ns_inode": net_ns_inode, "mount_ns_inode": mount_ns_inode}


def _assert_no_recent_shutdown(*, run: Callable[..., Any] = subprocess.run) -> None:
    try:
        uptime_fields = Path("/proc/uptime").read_text(encoding="ascii").split()
        stable_seconds = float(uptime_fields[0])
    except (OSError, ValueError, IndexError) as exc:
        raise ContractError("WSL uptime cannot be established") from exc
    if stable_seconds < 60:
        raise ContractError("WSL boot has not remained stable for 60 seconds")
    journal = _run(["/usr/bin/journalctl", "--unit=systemd-logind.service",
                    "--since=-60s", "--output=cat", "--no-pager"], run=run).stdout.casefold()
    shutdown_markers = ("powering down", "will power off now", "power-off.target",
                        "shutdown.target", "system is shutting down")
    if any(marker in journal for marker in shutdown_markers):
        raise ContractError("recent systemd-logind shutdown activity blocks probe start")


def _host_environment_observation(*, run: Callable[..., Any] = subprocess.run) -> dict[str, str]:
    try:
        release_bytes = Path("/etc/os-release").read_bytes()
        kernel_release = Path("/proc/sys/kernel/osrelease").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise ContractError("host distribution or kernel identity cannot be observed") from exc
    try:
        release_text = release_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractError("host distribution metadata is not UTF-8") from exc
    release_values: dict[str, str] = {}
    for line in release_text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            release_values[key] = value.strip().strip('"')
    systemd_lines = _run([SYSTEMCTL, "--version"], run=run).stdout.splitlines()
    if not systemd_lines:
        raise ContractError("systemd version is unavailable")
    systemd_line = systemd_lines[0]
    systemd_match = re.fullmatch(r"systemd ([0-9]+)(?:\.[0-9]+)*.*", systemd_line)
    wsl_distro = os.environ.get("WSL_DISTRO_NAME", "")
    if (release_values.get("ID") != "ubuntu" or release_values.get("VERSION_ID") != "24.04"
            or "microsoft-standard-wsl2" not in kernel_release.casefold()
            or wsl_distro != "Ubuntu-24.04" or systemd_match is None):
        raise ContractError("target is not the authorized Ubuntu 24.04 WSL2/systemd environment")
    return {"os_release_sha256": hashlib.sha256(release_bytes).hexdigest(),
            "distribution_id": release_values["ID"],
            "distribution_version": release_values["VERSION_ID"],
            "kernel_release": kernel_release, "wsl_distro_name": wsl_distro,
            "systemd_version": systemd_match.group(1)}


def _process_identity(pid: int) -> dict[str, Any]:
    if type(pid) is not int or pid <= 1:
        raise ContractError("probe MainPID is missing or invalid")
    root = Path(f"/proc/{pid}")
    try:
        stat_raw = (root / "stat").read_text(encoding="ascii")
        tail = stat_raw[stat_raw.rfind(")") + 2:].split()
        start_ticks = int(tail[19])
        status = (root / "status").read_text(encoding="ascii")
        uid_values = [int(value) for line in status.splitlines() if line.startswith("Uid:")
                      for value in line.split()[1:]]
        gid_values = [int(value) for line in status.splitlines() if line.startswith("Gid:")
                      for value in line.split()[1:]]
        cgroup = (root / "cgroup").read_text(encoding="ascii")
        net_ns = os.stat(root / "ns/net").st_ino
        mount_ns = os.stat(root / "ns/mnt").st_ino
    except (OSError, ValueError, StopIteration, IndexError) as exc:
        raise ContractError("probe process identity cannot be established") from exc
    if uid_values != [999, 999, 999, 999] or gid_values != [989, 989, 989, 989]:
        raise ContractError(
            "probe process identity differs from the configured worker "
            f"(uid={uid_values!r}, gid={gid_values!r}; "
            "expected uid=[999, 999, 999, 999], gid=[989, 989, 989, 989])")
    if not any(line.rsplit(":", 1)[-1] == "/system.slice/vst-sandbox-probe.service"
               for line in cgroup.splitlines()):
        raise ContractError("probe process is outside its exact systemd cgroup")
    return {"pid": pid, "start_ticks": start_ticks, "uid": uid_values,
            "gid": gid_values,
            "net_ns_inode": net_ns, "mount_ns_inode": mount_ns,
            "cgroup": "/system.slice/vst-sandbox-probe.service"}


def _network_observation(pid: int, *, run: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    def ip_json(*args: str) -> Any:
        raw = _run([NSENTER, "--target", str(pid), "--net", "--", IP, "-j", *args],
                   timeout=5, run=run).stdout
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError("network namespace output is invalid JSON") from exc

    addresses = ip_json("address")
    routes_v4 = ip_json("route", "show", "table", "all")
    routes_v6 = ip_json("-6", "route", "show", "table", "all")
    if not isinstance(addresses, list) or not isinstance(routes_v4, list) or not isinstance(routes_v6, list):
        raise ContractError("network namespace observation has an invalid shape")
    if len(addresses) != 1 or addresses[0].get("ifname") != "lo" or "UP" not in addresses[0].get("flags", []):
        raise ContractError("probe network namespace has an unexpected interface")
    address_info = addresses[0].get("addr_info")
    if not isinstance(address_info, list) or any(
        item.get("local") not in ("127.0.0.1", "::1") for item in address_info
    ):
        raise ContractError("probe loopback has an unexpected address")
    if any(route.get("dev") != "lo" or route.get("gateway") for route in routes_v4 + routes_v6):
        raise ContractError("probe network namespace has a non-loopback route")
    return {"addresses": addresses, "routes_v4": routes_v4, "routes_v6": routes_v6}


def _mount_and_socket_observation(pid: int) -> dict[str, Any]:
    root = Path(f"/proc/{pid}/root")
    try:
        mount_lines = Path(f"/proc/{pid}/mountinfo").read_text(encoding="utf-8").splitlines()
        unix_lines = Path(f"/proc/{pid}/net/unix").read_text(encoding="utf-8").splitlines()[1:]
    except OSError as exc:
        raise ContractError("probe mount or socket inventory is incomplete") from exc
    windows_mounts: list[str] = []
    unapproved_host_mounts: list[str] = []
    try:
        kernel_release = Path("/proc/sys/kernel/osrelease").read_text(encoding="ascii").strip()
    except (OSError, UnicodeError) as exc:
        raise ContractError("kernel module mount identity cannot be established") from exc
    if not re.fullmatch(r"[A-Za-z0-9._+-]{1,128}", kernel_release):
        raise ContractError("kernel release is not a safe mount identity")
    kernel_modules_target = "/usr/lib/modules/" + kernel_release
    allowed_mounts = {
        "/": {"ext4", "overlay"}, "/proc": {"proc"}, "/sys": {"sysfs"},
        "/dev": {"devtmpfs"}, "/dev/pts": {"devpts"}, "/dev/shm": {"tmpfs"},
        "/dev/mqueue": {"mqueue"}, "/run": {"tmpfs"}, "/run/lock": {"tmpfs"},
        "/run/user": {"tmpfs"}, "/tmp": {"tmpfs"}, "/var/tmp": {"tmpfs"},
        "/usr": {"ext4", "overlay"}, "/boot": {"ext4"}, "/etc": {"ext4", "overlay"},
        "/var": {"ext4", "overlay"}, "/opt": {"ext4", "overlay"},
        "/home": {"tmpfs", "ramfs"}, "/root": {"tmpfs", "ramfs"},
        "/mnt": {"tmpfs", "ramfs"}, "/init": {"tmpfs", "ramfs"},
        "/usr/lib/wsl": {"tmpfs", "ramfs"}, "/run/WSL": {"tmpfs", "ramfs"},
        "/tmp/.X11-unix": {"tmpfs", "ramfs"}, "/proc/sys": {"proc"},
        "/proc/sysrq-trigger": {"proc"}, "/sys/fs/cgroup": {"cgroup2"},
        "/usr/lib/modules": {"ext4", "overlay"},
        kernel_modules_target: {"overlay"},
    }
    for masked_path in MASKED_HOST_PATHS:
        allowed_mounts[masked_path] = {"ext4", "overlay"}
    decoded: list[tuple[str, str, list[str], str, str, str, str]] = []
    for line in mount_lines:
        fields = line.split()
        if len(fields) < 10 or "-" not in fields:
            raise ContractError("probe mount table is malformed")
        separator = fields.index("-")
        if separator + 2 >= len(fields):
            raise ContractError("probe mount table is truncated")
        decode = lambda value: re.sub(
            r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value
        )
        root_source, target = decode(fields[3]), decode(fields[4])
        filesystem, source = fields[separator + 1], fields[separator + 2]
        options = fields[separator + 3] if separator + 3 < len(fields) else ""
        decoded.append((line, target, fields, root_source, filesystem.lower(), decode(source), options))

    roots = [entry for entry in decoded if entry[1] == "/"]
    if len(roots) != 1 or roots[0][3] != "/":
        raise ContractError("probe root mount identity is ambiguous")
    root_device, root_filesystem = roots[0][2][2], roots[0][4]
    seen_targets: set[str] = set()
    for line, target, fields, root_source, filesystem, source, options in decoded:
        if target in seen_targets:
            unapproved_host_mounts.append("duplicate mount target: " + target)
            continue
        seen_targets.add(target)
        is_drvfs = filesystem.lower() == "drvfs" or (
            filesystem == "9p" and re.search(r"(?:^|[,;])aname=drvfs(?:$|[,;])", options) is not None
        )
        if is_drvfs and re.fullmatch(r"[A-Za-z]:\\?", source):
            windows_mounts.append(line)
        expected_fs = allowed_mounts.get(target)
        if expected_fs is None or filesystem not in expected_fs:
            unapproved_host_mounts.append(line)
            continue
        is_virtual = filesystem in {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs",
                                    "ramfs", "cgroup2", "mqueue"}
        if is_virtual:
            permitted_virtual_roots = {"/"}
            if target == "/proc/sys":
                permitted_virtual_roots.add("/sys")
            if target == "/proc/sysrq-trigger":
                permitted_virtual_roots.add("/sysrq-trigger")
            valid_source = root_source in permitted_virtual_roots and source == filesystem
        elif target in MASKED_HOST_PATHS:
            valid_source = (fields[2] == root_device and filesystem == root_filesystem
                            and root_source == "/run/systemd/inaccessible/dir")
        elif target in {"/tmp", "/var/tmp"}:
            private_tmp_parent = "/tmp/systemd-private-" if target == "/tmp" else "/var/tmp/systemd-private-"
            valid_source = (fields[2] == root_device and filesystem == root_filesystem
                            and root_source.startswith(private_tmp_parent)
                            and "vst-sandbox-probe.service" in root_source
                            and root_source.endswith("/tmp"))
        elif target == kernel_modules_target:
            # WSL exposes its current kernel modules through a per-kernel
            # overlay. In the probe's ProtectSystem=strict namespace it must
            # be read-only and cannot be a Windows/DrvFs source.
            valid_source = (filesystem == "overlay" and source == "none"
                            and root_source == "/" and "ro" in fields[5].split(","))
        else:
            # A ProtectSystem bind must stay on the root filesystem and name
            # the exact source subtree. This rejects a second host disk or an
            # arbitrary bind mount placed at an otherwise familiar target.
            valid_source = (fields[2] == root_device and filesystem == root_filesystem
                            and root_source == target)
            if target in {"/usr", "/boot", "/etc", "/var", "/opt", "/usr/lib/modules"}:
                valid_source = valid_source and "ro" in fields[5].split(",")
        if target == "/":
            valid_source = root_source == "/" and fields[2] == root_device
        is_unapproved = not valid_source
        if is_unapproved:
            unapproved_host_mounts.append(line)
    if windows_mounts or unapproved_host_mounts:
        raise ContractError("probe namespace exposes an unapproved Windows or host mount")

    sockets = sorted({line.split()[-1] for line in unix_lines if line.split()
                      and any(token in line.split()[-1].lower()
                              for token in ("docker.sock", "podman.sock", "containerd.sock"))})
    for path in CONTAINER_SOCKET_NAMES:
        candidate = root / path.lstrip("/")
        try:
            os.lstat(candidate)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ContractError("probe container-socket path cannot be inspected") from exc
        sockets.append(path)

    runtime_users = root / "run/user"
    try:
        runtime_info = os.lstat(runtime_users)
    except FileNotFoundError:
        runtime_info = None
    except OSError as exc:
        raise ContractError("probe per-user runtime socket inventory is incomplete") from exc
    if runtime_info is not None:
        if not os.path.isdir(runtime_users) or os.path.islink(runtime_users):
            raise ContractError("probe per-user runtime root is not a plain directory")
        try:
            with os.scandir(runtime_users) as entries:
                user_entries = list(entries)
        except OSError as exc:
            raise ContractError("probe per-user runtime directory cannot be enumerated") from exc
        for entry in user_entries:
            if not entry.name.isdigit():
                raise ContractError("probe per-user runtime inventory has an unknown entry")
            try:
                if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                    raise ContractError("probe per-user runtime entry is not a plain directory")
            except OSError as exc:
                raise ContractError("probe per-user runtime entry cannot be inspected") from exc
            for relative in ("docker.sock", "containerd/containerd.sock", "podman/podman.sock"):
                candidate = Path(entry.path) / relative
                if "/" in relative:
                    parent = candidate.parent
                    try:
                        parent_info = os.lstat(parent)
                    except FileNotFoundError:
                        continue
                    except OSError as exc:
                        raise ContractError("probe per-user socket parent cannot be inspected") from exc
                    if os.path.islink(parent) or not os.path.isdir(parent):
                        raise ContractError("probe per-user socket parent is not a plain directory")
                try:
                    os.lstat(candidate)
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise ContractError("probe per-user socket path cannot be inspected") from exc
                sockets.append(str(candidate.relative_to(root)))
    if sockets:
        raise ContractError("probe namespace exposes a container-engine socket")
    return {"mount_table": mount_lines, "windows_drive_mounts": windows_mounts,
            "mount_contract": "VST_S2_PROBE_SYSTEMD_ALLOWLIST_V1",
            "unapproved_host_mounts": unapproved_host_mounts,
            "container_socket_paths_present": sorted(set(sockets))}


def _publish_attestation(attestation: dict[str, Any]) -> tuple[int, int, str]:
    path = Path(ATTESTATION_PATH)
    parent = path.parent
    try:
        parent_info = os.stat(parent, follow_symlinks=False)
    except OSError as exc:
        raise ContractError("preflight attestation directory is unavailable") from exc
    if (not os.path.isdir(parent) or parent_info.st_uid != 0 or parent_info.st_gid != 989
            or (parent_info.st_mode & 0o777) != 0o710):
        raise ContractError("preflight attestation directory is not root controlled")
    if os.path.lexists(path):
        raise ContractError("refusing to reuse an existing network attestation")
    payload = canonical_bytes(attestation) + b"\n"
    temporary = parent / (".network-policy-" + os.urandom(12).hex())
    directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    published_identity: tuple[int, int, str] | None = None
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            os.fchown(stream.fileno(), 0, 989)
            os.fchmod(stream.fileno(), 0o640)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            temporary_identity = os.fstat(stream.fileno())
            if (not stat.S_ISREG(temporary_identity.st_mode) or temporary_identity.st_uid != 0
                    or temporary_identity.st_gid != 989
                    or stat.S_IMODE(temporary_identity.st_mode) != 0o640):
                raise ContractError("temporary network attestation metadata is unsafe")
            published_identity = (temporary_identity.st_dev, temporary_identity.st_ino,
                                  hashlib.sha256(payload).hexdigest())
        os.link(temporary, path, follow_symlinks=False)
        published = os.stat(path, follow_symlinks=False)
        if (not os.path.isfile(path) or os.path.islink(path)
                or published.st_dev != published_identity[0]
                or published.st_ino != published_identity[1] or published.st_uid != 0
                or published.st_gid != 989 or (published.st_mode & 0o777) != 0o640):
            raise ContractError("published network attestation metadata changed")
        if hashlib.sha256(path.read_bytes()).hexdigest() != published_identity[2]:
            raise ContractError("published network attestation bytes changed")
        os.fsync(directory_fd)
        return published_identity
    except FileExistsError as exc:
        raise ContractError("refusing to overwrite a network attestation") from exc
    except OSError as exc:
        if published_identity is not None and os.path.lexists(path):
            raise AttestationPublishError(
                "network attestation could not be published durably",
                published_identity,
            ) from exc
        raise ContractError("network attestation could not be published durably") from exc
    except ContractError as exc:
        if published_identity is not None and os.path.lexists(path):
            raise AttestationPublishError(str(exc), published_identity) from exc
        raise
    finally:
        cleanup_error: OSError | None = None
        try:
            os.close(directory_fd)
        except OSError as exc:
            cleanup_error = exc
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        except OSError as exc:
            cleanup_error = cleanup_error or exc
        if cleanup_error is not None:
            if published_identity is not None:
                raise AttestationPublishError(
                    "network attestation publication cleanup was incomplete",
                    published_identity,
                ) from cleanup_error
            raise ContractError("network attestation temporary cleanup failed") from cleanup_error


def _rollback_published_attestation(identity: tuple[int, int, str]) -> bool:
    """Remove only the exact root-owned attestation created by this attempt."""
    if (not isinstance(identity, tuple) or len(identity) != 3
            or type(identity[0]) is not int or type(identity[1]) is not int
            or not isinstance(identity[2], str) or not SHA256.fullmatch(identity[2])):
        return False
    parent = Path(ATTESTATION_PATH).parent
    directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        try:
            fd = os.open(ATTESTATION_PATH, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except OSError:
            return False
        with os.fdopen(fd, "rb", closefd=True) as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev != identity[0] or current.st_ino != identity[1]
                    or not stat.S_ISREG(current.st_mode) or current.st_uid != 0
                    or current.st_gid != 989 or stat.S_IMODE(current.st_mode) != 0o640):
                return False
            digest = hashlib.sha256(stream.read()).hexdigest()
        if digest != identity[2]:
            return False
        os.unlink(ATTESTATION_PATH)
        os.fsync(directory_fd)
        return True
    finally:
        os.close(directory_fd)


def _verify_source_identity(expected_head: str, expected_sha256: str, *,
                            run: Callable[..., Any] = subprocess.run) -> None:
    if (not isinstance(expected_head, str) or not isinstance(expected_sha256, str)
            or not GIT_OID.fullmatch(expected_head) or not SHA256.fullmatch(expected_sha256)):
        raise ContractError("authorized source identity is malformed")
    head = _run(["git", "-C", str(REPOSITORY), "rev-parse", "--verify", "HEAD"],
                timeout=10, run=run).stdout.strip()
    if head != expected_head:
        raise ContractError("repository HEAD differs from the authorized source head")
    tree = _run(["git", "--no-replace-objects", "-C", str(REPOSITORY),
                 "ls-tree", "--name-only",
                 expected_head, "--", SOURCE_RELATIVE_PATH], timeout=10, run=run).stdout.splitlines()
    if tree:
        if tree != [SOURCE_RELATIVE_PATH]:
            raise ContractError("authorized source tree path is ambiguous")
        try:
            result = run(["git", "--no-replace-objects", "-C", str(REPOSITORY), "show",
                          expected_head + ":" + SOURCE_RELATIVE_PATH], stdin=subprocess.DEVNULL,
                         capture_output=True, check=False, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ContractError("authorized source blob cannot be read") from exc
        if (result.returncode != 0 or not isinstance(result.stdout, bytes)
                or hashlib.sha256(result.stdout).hexdigest() != expected_sha256):
            raise ContractError("authorized source blob differs from the pinned helper digest")
    try:
        local = Path(__file__).read_bytes()
    except OSError as exc:
        raise ContractError("authorized helper file is unavailable") from exc
    if hashlib.sha256(local).hexdigest() != expected_sha256:
        raise ContractError("executed helper bytes differ from the pinned helper digest")


def _claim_attempt(request_id: str, run_id: str, nonce: str, manifest_sha256_value: str,
                   config: dict[str, Any]) -> str:
    if (not isinstance(request_id, str) or not isinstance(manifest_sha256_value, str)
            or not re.fullmatch(r"[0-9a-f]{32}", request_id)
            or not SHA256.fullmatch(manifest_sha256_value)):
        raise ContractError("fresh authorization identity is malformed")
    if (request_id, run_id, nonce) in RETIRED_RUN_IDENTITIES:
        raise ContractError("interrupted S2-4 run identity is permanently retired")
    private_dir = Path(config["preflight_record_path"]).parent
    try:
        info = os.stat(private_dir, follow_symlinks=False)
    except OSError as exc:
        raise ContractError("root attempt-marker directory is unavailable") from exc
    if (not os.path.isdir(private_dir) or os.path.islink(private_dir) or info.st_uid != 0
            or info.st_gid != 0 or (info.st_mode & 0o777) != 0o700):
        raise ContractError("root attempt-marker directory is unsafe")
    try:
        with os.scandir(private_dir) as entries:
            marker_entries = [entry for entry in entries if entry.name.startswith(".probe-attempt-")
                              and entry.name.endswith(".json")]
    except OSError as exc:
        raise ContractError("existing one-start authorization markers cannot be inventoried") from exc
    for entry in marker_entries:
        try:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                raise ContractError("existing one-start marker is not a regular file")
            raw = Path(entry.path).read_bytes()
            marker_body = json.loads(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ContractError("existing one-start marker is malformed or unreadable") from exc
        if (not isinstance(marker_body, dict)
                or marker_body.get("schema") != "VST_S2_PROBE_ATTEMPT_CLAIM_V1"):
            raise ContractError("existing one-start marker has an unknown contract")
        if (marker_body.get("request_id") == request_id or marker_body.get("run_id") == run_id
                or marker_body.get("nonce") == nonce):
            raise ContractError("run/request/nonce identity was already consumed")
    key = hashlib.sha256(canonical_bytes({"request_id": request_id, "run_id": run_id,
                                          "nonce": nonce, "manifest_sha256": manifest_sha256_value})).hexdigest()
    marker = private_dir / (".probe-attempt-" + key + ".json")
    body = canonical_bytes({"schema": "VST_S2_PROBE_ATTEMPT_CLAIM_V1", "request_id": request_id,
                            "run_id": run_id, "nonce": nonce,
                            "manifest_sha256": manifest_sha256_value}) + b"\n"
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError as exc:
        raise ContractError("this run authorization already consumed its one probe start") from exc
    except OSError as exc:
        raise ContractError("cannot create the durable one-start attempt marker") from exc
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(private_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise ContractError("durable one-start marker could not be committed") from exc
    return key


def _drain_started_probe(invocation_id: str | None, *,
                         run: Callable[..., Any], monotonic: Callable[[], float],
                         sleep: Callable[[float], None]) -> None:
    deadline = monotonic() + 62
    while monotonic() < deadline:
        try:
            current = _systemctl_show(PROBE_UNIT, run=run)
        except ContractError:
            return
        if invocation_id is None:
            if (current["ActiveState"] != "activating" or not current["MainPID"].isdigit()
                    or not INVOCATION_ID.fullmatch(current["InvocationID"])):
                return
            invocation_id = current["InvocationID"]
        if current["InvocationID"] not in (invocation_id, "") or current["ActiveState"] == "inactive":
            return
        sleep(0.1)


def run_probe(run_id: str, nonce: str, *, request_id: str, expected_head: str,
              expected_sha256: str, expected_supervisor_sha256: str,
              expected_profile_sha256: str, expected_bootstrap_sha256: str,
              expected_manifest_sha256: str,
              run: Callable[..., Any] = subprocess.run,
              monotonic: Callable[[], float] = time.monotonic,
              sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    if os.name != "posix" or os.geteuid() != 0:
        raise ContractError("live probe capture requires root on POSIX")
    if (not isinstance(run_id, str) or not isinstance(nonce, str)
            or not RUN_ID.fullmatch(run_id) or not NONCE.fullmatch(nonce)):
        raise ContractError("run identity is malformed")
    _verify_source_identity(expected_head, expected_sha256, run=run)

    config = _read_controlled_json(DEFAULT_CONFIG_PATH)
    request = _read_root_controlled_json(PROBE_REQUEST_PATH, max_bytes=65536)
    profile = _read_controlled_json(NETWORK_PROFILE_PATH)
    bootstrap = _read_root_controlled_json(BOOTSTRAP_REQUEST_PATH, max_bytes=262144)
    digest_paths = {
        DEFAULT_CONFIG_PATH: expected_supervisor_sha256,
        NETWORK_PROFILE_PATH: expected_profile_sha256,
        BOOTSTRAP_REQUEST_PATH: expected_bootstrap_sha256,
    }
    for path, expected in digest_paths.items():
        if not isinstance(expected, str) or not SHA256.fullmatch(expected):
            raise ContractError("fresh runtime authorization digest is malformed")
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ContractError("runtime config differs from the fresh authorization digest")
    manifest = bootstrap.get("task_manifest")
    if (not isinstance(manifest, dict) or not isinstance(expected_manifest_sha256, str)
            or not SHA256.fullmatch(expected_manifest_sha256)
            or manifest_sha256(manifest) != expected_manifest_sha256):
        raise ContractError("task manifest differs from the fresh authorization digest")
    if (bootstrap.get("request_id") != request_id or bootstrap.get("run_id") != run_id
            or bootstrap.get("task_id") != "S2-4-runtime-owner-runner-qualification"):
        raise ContractError("bootstrap request identity differs from the fresh authorization")
    allowed_test = ("tests/vst/test_s2_assignment_basis.py::"
                    "test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment")
    required_tests = manifest.get("required_tests")
    if (type(manifest.get("retry_cap")) is not int or manifest.get("retry_cap") != 0
            or not isinstance(required_tests, list)
            or len(required_tests) != 1 or not isinstance(required_tests[0], dict)
            or required_tests[0].get("test_id") != allowed_test):
        raise ContractError("fresh authorization changed the single permitted TestRun selector")

    for field in ("store_path", "preflight_record_path", "operator_key_path"):
        value = config.get(field)
        if not isinstance(value, str) or not os.path.isabs(value):
            raise ContractError("Supervisor configuration path is missing or invalid: " + field)
    if config.get("run_id") != run_id or config.get("probe_nonce") != nonce:
        raise ContractError("requested run identity differs from pinned Supervisor configuration")
    if request != {"run_id": run_id, "nonce": nonce}:
        raise ContractError("probe request differs from the exact run identity")
    if (profile.get("probe_unit") != PROBE_UNIT or profile.get("external_allowlist") != []
            or profile.get("environment_id") != "Ubuntu-24.04:S2:" + run_id):
        raise ContractError("network profile differs from the exact probe contract")
    if os.path.realpath("/opt/vst-runtime") != "/opt/vst-runtime-" + RUNTIME_SOURCE_HEAD:
        raise ContractError("selected runtime differs from the pinned source")
    if os.path.lexists(config["store_path"]):
        raise ContractError("fresh S2 runtime requires an absent Store target")
    if os.path.lexists(config["preflight_record_path"]):
        raise ContractError("refusing an existing root preflight record")
    if os.path.lexists(ATTESTATION_PATH):
        raise ContractError("stale run-bound attestation exists; this attempt requires a fresh WSL boot")

    host_environment = _host_environment_observation(run=run)

    boot_before = _systemd_ready(run=run)
    _assert_no_recent_shutdown(run=run)
    _verify_probe_unit_files()
    probe_props = _systemctl_show(PROBE_UNIT, run=run)
    if probe_props["LoadState"] != "loaded" or probe_props["ActiveState"] != "inactive":
        raise ContractError("runtime probe unit is missing or not inactive")
    _assert_dependents_inactive(run=run)

    attempt_key = _claim_attempt(request_id, run_id, nonce, expected_manifest_sha256, config)
    invocation: str | None = None
    try:
        _run([SYSTEMCTL, "start", "--no-block", PROBE_UNIT], timeout=10, run=run)
        deadline = monotonic() + 8
        props: dict[str, str] | None = None
        while monotonic() < deadline:
            if _systemd_ready(run=run, allow_probe_start_job=True) != boot_before:
                raise ContractError("WSL boot or systemd generation changed during probe start")
            candidate = _systemctl_show(PROBE_UNIT, run=run)
            if (candidate["ActiveState"] == "activating" and candidate["MainPID"].isdigit()
                    and int(candidate["MainPID"]) > 1
                    and INVOCATION_ID.fullmatch(candidate["InvocationID"])):
                props = candidate
                break
            if candidate["ActiveState"] not in ("activating", "inactive"):
                raise ContractError("probe entered an unexpected systemd state")
            sleep(0.1)
        if props is None:
            raise ContractError("probe did not expose one live invocation")
    except Exception:
        _drain_started_probe(None, run=run, monotonic=monotonic, sleep=sleep)
        raise

    invocation = props["InvocationID"]
    pid = int(props["MainPID"])
    published_identity: tuple[int, int, str] | None = None
    try:
        if (props["PrivateNetwork"] != "yes"
                or props["ControlGroup"] != "/system.slice/vst-sandbox-probe.service"):
            raise ContractError("probe systemd isolation properties differ from the pinned unit")
        identity_before = _process_identity(pid)
        if (identity_before["net_ns_inode"] == boot_before["net_ns_inode"]
                or identity_before["mount_ns_inode"] == boot_before["mount_ns_inode"]):
            raise ContractError("probe is not isolated in distinct network and mount namespaces")
        networks = _network_observation(pid, run=run)
        mounts = _mount_and_socket_observation(pid)
        identity_after = _process_identity(pid)
        props_after = _systemctl_show(PROBE_UNIT, run=run)
        if (identity_after != identity_before or props_after["MainPID"] != str(pid)
                or props_after["InvocationID"] != invocation
                or props_after["ActiveState"] != "activating"):
            raise ContractError("probe PID, cgroup, namespace, or invocation changed during observation")
        if _systemd_ready(run=run, allow_probe_start_job=True) != boot_before:
            raise ContractError("WSL boot or systemd generation changed during observation")
        _assert_no_recent_shutdown(run=run)

        observation = {"host_environment": host_environment,
                       "pid1": boot_before, "systemd": props_after,
                       "process": identity_after, "network": networks, "filesystem": mounts}
        spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
        policy_sha256 = hashlib.sha256(Path(NETWORK_PROFILE_PATH).read_bytes()).hexdigest()
        evidence_sha256 = hashlib.sha256(canonical_bytes(observation)).hexdigest()
        # Re-hash every authorized contract immediately before signing/publishing.
        for path, expected in digest_paths.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ContractError("authorized runtime configuration changed during observation")
        if manifest_sha256(_read_root_controlled_json(BOOTSTRAP_REQUEST_PATH,
                max_bytes=262144)["task_manifest"]) != expected_manifest_sha256:
            raise ContractError("authorized task manifest changed during observation")
        body = {"run_id": run_id, "spec_sha256": spec_sha256, "nonce": nonce,
                "environment_id": profile["environment_id"], "policy_sha256": policy_sha256,
                "evidence_sha256": evidence_sha256, "empty_external_allowlist": True,
                "no_container_socket": not mounts["container_socket_paths_present"],
                "no_unapproved_host_paths": not mounts["unapproved_host_mounts"]}
        if not body["no_container_socket"] or not body["no_unapproved_host_paths"]:
            raise ContractError("root policy evidence is incomplete")
        operator_key = _read_root_key(config["operator_key_path"])
        attestation = sign_network_policy_attestation(body, operator_key)
        if (_systemd_ready(run=run, allow_probe_start_job=True) != boot_before
                or _process_identity(pid) != identity_before
                or _systemctl_show(PROBE_UNIT, run=run)["InvocationID"] != invocation):
            raise ContractError("runtime identity changed before attestation publication")
        _assert_dependents_inactive(run=run)
        _assert_no_recent_shutdown(run=run)
        for path, expected in digest_paths.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise ContractError("authorized runtime configuration changed before attestation publication")
        try:
            published_identity = _publish_attestation(attestation)
        except AttestationPublishError as exc:
            published_identity = exc.published_identity
            raise
        if (_systemd_ready(run=run, allow_probe_start_job=True) != boot_before
                or _systemctl_show(PROBE_UNIT, run=run)["InvocationID"] != invocation):
            raise ContractError("runtime identity changed immediately after attestation publication")
        probe_deadline = monotonic() + 90
        while monotonic() < probe_deadline:
            if _systemd_ready(run=run, allow_probe_start_job=True) != boot_before:
                raise ContractError("WSL boot or systemd generation changed before probe completion")
            current = _systemctl_show(PROBE_UNIT, run=run)
            if current["InvocationID"] not in (invocation, ""):
                raise ContractError("systemd probe invocation was replaced")
            if current["ActiveState"] == "inactive":
                if current["Result"] != "success":
                    raise ContractError("exact probe invocation did not complete successfully")
                _assert_dependents_inactive(run=run)
                for path, expected in digest_paths.items():
                    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                        raise ContractError("authorized runtime configuration changed before preflight capture")
                current_bootstrap = _read_root_controlled_json(BOOTSTRAP_REQUEST_PATH,
                                                               max_bytes=262144)
                current_manifest = current_bootstrap.get("task_manifest")
                if (current_bootstrap.get("request_id") != request_id
                        or current_bootstrap.get("run_id") != run_id
                        or not isinstance(current_manifest, dict)
                        or manifest_sha256(current_manifest) != expected_manifest_sha256):
                    raise ContractError("authorized bootstrap request changed before preflight capture")
                current_host = _host_environment_observation(run=run)
                if current_host != host_environment:
                    raise ContractError("host environment identity changed during the probe invocation")
                if _systemd_ready(run=run) != boot_before:
                    raise ContractError("WSL boot or systemd generation changed before root preflight capture")
                _assert_no_recent_shutdown(run=run)
                capture = capture_probe_invocation(invocation)
                return {"run_id": run_id, "invocation_id": invocation, "attempt_key": attempt_key,
                        "observation_sha256": evidence_sha256, "host_environment": host_environment,
                        **capture}
            if current["ActiveState"] != "activating" or current["MainPID"] != str(pid):
                raise ContractError("probe left its exact live process before successful completion")
            sleep(0.1)
        raise ContractError("probe completion exceeded its bounded deadline")
    except Exception:
        # Do not stop, kill, or restart the service. Let the one bounded
        # invocation finish while keeping the WSL caller alive.
        _drain_started_probe(invocation, run=run, monotonic=monotonic, sleep=sleep)
        if (published_identity is not None
                and not os.path.lexists(config["preflight_record_path"])
                and _probe_inactive_for_rollback(invocation, run=run)):
            try:
                _assert_dependents_inactive(run=run)
            except ContractError:
                pass
            else:
                try:
                    _rollback_published_attestation(published_identity)
                except OSError:
                    pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--expected-supervisor-sha256", required=True)
    parser.add_argument("--expected-profile-sha256", required=True)
    parser.add_argument("--expected-bootstrap-sha256", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = run_probe(args.run_id, args.nonce, request_id=args.request_id,
                           expected_head=args.expected_head, expected_sha256=args.expected_sha256,
                           expected_supervisor_sha256=args.expected_supervisor_sha256,
                           expected_profile_sha256=args.expected_profile_sha256,
                           expected_bootstrap_sha256=args.expected_bootstrap_sha256,
                           expected_manifest_sha256=args.expected_manifest_sha256)
    except (ContractError, OSError, KeyError, ValueError) as exc:
        print("probe capture refused: " + str(exc), file=sys.stderr)
        return 2
    print("captured successful root-bound probe " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
