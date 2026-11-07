"""stdlib-only sandbox pre-flight inventory; no third-party packages required."""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import stat
import time
from pathlib import Path
from typing import Any

from .contracts import ContractError
SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "SANDBOX_SPEC.md"
PROBE_PROFILE_PATH = Path("/etc/vst-runner/network-profile.json")
BLOCKED_EGRESS_TARGET = ("198.51.100.1", 9)
MAX_FRESH_PROBE_AGE_NS = 120_000_000_000
CONTAINER_SOCKETS = (
    "/run/docker.sock", "/var/run/docker.sock", "/run/containerd/containerd.sock",
    "/run/podman/podman.sock",
)
SYSTEMD_MASKED_WSL_PATHS = frozenset({
    "/init", "/home", "/mnt", "/root", "/run/WSL", "/usr/lib/wsl",
    "/tmp/.X11-unix",
})

def _container_socket_inventory() -> tuple[list[str], bool]:
    """Enumerate known engine sockets across all runtime UIDs; unknown is unsafe."""
    paths = list(CONTAINER_SOCKETS)
    observed_proc_sockets: list[str] = []
    found: list[str] = []
    complete = True
    def observe(path: str) -> None:
        """Record present paths; permission/metadata errors make the scan incomplete."""
        nonlocal complete
        try:
            os.lstat(path)
        except FileNotFoundError:
            return
        except OSError:
            complete = False
            return
        found.append(path)

    # /run/user is the canonical runtime root. Do not follow it or UID entries
    # when symlinked: they are part of the host boundary being inventoried.
    runtime_root = "/run/user"
    try:
        root_stat = os.lstat(runtime_root)
    except FileNotFoundError:
        root_stat = None
    except OSError:
        root_stat = None
        complete = False
    if root_stat is not None:
        if os.path.islink(runtime_root) or not os.path.isdir(runtime_root):
            complete = False
        else:
            try:
                with os.scandir(runtime_root) as entries:
                    user_entries = list(entries)
            except OSError:
                user_entries = []
                complete = False
            for entry in user_entries:
                if not entry.name.isdigit():
                    complete = False
                    continue
                try:
                    if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
                        complete = False
                        continue
                except OSError:
                    complete = False
                    continue
                user_dir = entry.path
                for relative in ("docker.sock", "containerd/containerd.sock", "podman/podman.sock"):
                    candidate = os.path.join(user_dir, relative)
                    parent = os.path.dirname(candidate)
                    if parent != user_dir:
                        try:
                            parent_stat = os.lstat(parent)
                        except FileNotFoundError:
                            continue
                        except OSError:
                            complete = False
                            continue
                        if os.path.islink(parent) or not os.path.isdir(parent):
                            complete = False
                            continue
                    observe(candidate)

    for path in paths:
        observe(path)
    try:
        unix_sockets = Path("/proc/net/unix").read_text(encoding="utf-8").splitlines()
        observed_proc_sockets.extend(line.split()[-1] for line in unix_sockets[1:]
                                     if line.split() and any(token in line.split()[-1].lower()
                                     for token in ("docker.sock", "podman.sock", "containerd.sock")))
    except OSError:
        complete = False
    return sorted(set(found + observed_proc_sockets)), complete


def _loopback_canary() -> bool:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.settimeout(2.0)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2.0)
    try:
        client.connect(server.getsockname())
        accepted, _ = server.accept()
        accepted.close()
        return True
    except OSError:
        return False
    finally:
        client.close()
        server.close()


def _blocked_egress() -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(1.0)
    try:
        probe.connect(BLOCKED_EGRESS_TARGET)
    except OSError:
        return True
    finally:
        probe.close()
    return False


def _bounded_proc_text(path: str, limit: int = 8 * 1024 * 1024) -> str:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise ContractError("required runtime observation is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_size > limit):
            raise ContractError("runtime observation exceeds its bounded regular-file contract")
        result = bytearray()
        while len(result) <= limit:
            chunk = os.read(fd, min(65536, limit + 1 - len(result)))
            if not chunk:
                break
            result.extend(chunk)
        if len(result) > limit:
            raise ContractError("runtime observation exceeds its size limit")
        return result.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ContractError("runtime observation is not valid UTF-8") from exc
    finally:
        os.close(fd)


def _network_namespace_inventory() -> tuple[list[str], list[str], list[str], bool]:
    try:
        interfaces = sorted(os.listdir("/sys/class/net"))
        ipv4 = _bounded_proc_text("/proc/net/route", 1024 * 1024).splitlines()
        ipv6 = _bounded_proc_text("/proc/net/ipv6_route", 1024 * 1024).splitlines()
    except (OSError, ContractError):
        return [], [], [], False
    routes: list[str] = []
    valid = interfaces == ["lo"] and bool(ipv4) and ipv4[0].split()[:3] == ["Iface", "Destination", "Gateway"]
    for line in ipv4[1:]:
        fields = line.split()
        if len(fields) < 8:
            valid = False
            continue
        device, destination, gateway = fields[0], fields[1], fields[2]
        routes.append("ipv4:" + line)
        # Only a loopback route is valid; no default route or gateway can
        # provide an egress path from the unit's private network namespace.
        if device != "lo" or gateway != "00000000" or destination == "00000000":
            valid = False
    for line in ipv6:
        fields = line.split()
        if len(fields) != 10:
            valid = False
            continue
        routes.append("ipv6:" + line)
        if (fields[9] != "lo" or fields[4] != "00" * 16
                or (fields[0] == "00" * 16 and fields[1] == "00")):
            valid = False
    return interfaces, routes, [], valid


def _namespace_inode(name: str) -> int:
    if name not in {"mnt", "net", "cgroup", "pid"}:
        raise ContractError("unsupported runtime namespace name")
    path = "/proc/self/ns/" + name
    try:
        link = os.readlink(path)
        info = os.stat(path)
    except OSError as exc:
        raise ContractError("runtime namespace identity cannot be inspected") from exc
    if not re.fullmatch(re.escape(name) + r":\[[0-9]+\]", link) or info.st_ino <= 0:
        raise ContractError("runtime namespace link has an invalid procfs identity")
    return info.st_ino


def collect_inventory() -> dict[str, Any]:
    """Measure the isolated worker directly; no signed/file handoff is accepted."""
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise ContractError("sandbox probe requires a POSIX sandbox")
    mountinfo = _bounded_proc_text("/proc/self/mountinfo")
    interop_path = Path("/proc/sys/fs/binfmt_misc/WSLInterop")
    interop_present = interop_path.exists()
    interop_enabled = False
    if interop_present:
        try:
            interop_enabled = "enabled" in interop_path.read_text(encoding="ascii", errors="ignore").lower()
        except OSError:
            interop_enabled = True  # unknown is unsafe
    windows_drive_mounts = []
    host_mounts = []
    decoded_mounts = []
    root_device = None
    root_filesystem = None
    root_source = None
    for line in mountinfo.splitlines():
        left, separator, right = line.partition(" - ")
        fields = left.split()
        filesystem_fields = right.split()
        if not separator or len(fields) < 6 or not filesystem_fields:
            raise ContractError("full mountinfo inventory contains a malformed row")
        target = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4])
        filesystem = filesystem_fields[0].lower()
        source = filesystem_fields[1] if len(filesystem_fields) > 1 else ""
        options = ",".join((fields[5], filesystem_fields[2] if len(filesystem_fields) > 2 else ""))
        wsl_drvfs_9p = filesystem == "9p" and re.search(
            r"(?:^|[;,])aname=drvfs(?:$|[;,])", options
        ) is not None
        if (filesystem == "drvfs" or wsl_drvfs_9p) or re.fullmatch(r"[A-Za-z]:\\?", source):
            windows_drive_mounts.append(line)
        root_path = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[3])
        decoded_mounts.append((line, fields[2], root_path, target, filesystem, source,
                               fields[5].split(",")))
        if len(line) > 16384:
            raise ContractError("mountinfo row exceeds the observation limit")
    roots = [row for row in decoded_mounts if row[3] == "/"]
    if len(roots) != 1:
        raise ContractError("mount namespace must expose exactly one root filesystem")
    root_device, root_source, _root_mount, root_filesystem = roots[0][1:5]
    for line, device, mount_root, target, filesystem, source, mount_options in decoded_mounts:
        wsl_path = (target == "/mnt" or target.startswith("/mnt/")
                    or target in SYSTEMD_MASKED_WSL_PATHS)
        valid_source = False
        if filesystem in {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "ramfs",
                          "cgroup2", "mqueue"}:
            permitted_roots = {"/"}
            if target == "/proc/sys":
                permitted_roots.add("/sys")
            if target == "/proc/sysrq-trigger":
                permitted_roots.add("/sysrq-trigger")
            valid_source = mount_root in permitted_roots and source == filesystem
        elif target in SYSTEMD_MASKED_WSL_PATHS:
            valid_source = (device == root_device and filesystem == root_filesystem
                            and mount_root == "/run/systemd/inaccessible/dir")
        elif target in {"/tmp", "/var/tmp"}:
            private_parent = "/tmp/systemd-private-" if target == "/tmp" else "/var/tmp/systemd-private-"
            valid_source = (device == root_device and filesystem == root_filesystem
                            and mount_root.startswith(private_parent)
                            and "vst-sandbox-probe.service" in mount_root
                            and mount_root.endswith("/tmp"))
        elif target == "/usr/lib/modules" or target.startswith("/usr/lib/modules/"):
            valid_source = (filesystem == "overlay" and source == "none" and mount_root == "/"
                            and "ro" in mount_options)
        else:
            valid_source = (device == root_device and filesystem == root_filesystem
                            and mount_root == target)
            if target in {"/usr", "/boot", "/etc", "/var", "/opt"}:
                valid_source = valid_source and "ro" in mount_options
        if target == "/":
            valid_source = mount_root == "/" and device == root_device
        # Accept a WSL integration path only when it is one of the exact
        # systemd-masked targets above and uses the inaccessible backing dir.
        # Any other /mnt child remains unapproved even if it resembles a root
        # filesystem bind mount.
        if not valid_source or (wsl_path and target not in SYSTEMD_MASKED_WSL_PATHS):
            host_mounts.append(line)
    sockets, socket_inventory_complete = _container_socket_inventory()
    interfaces, routes, _unused, isolated_network = _network_namespace_inventory()
    profile_path = Path("/etc/vst-runner/network-profile.json")
    try:
        profile_bytes = _bounded_proc_text(str(profile_path), 65536).encode("utf-8")
        profile = json.loads(profile_bytes)
        empty_allowlist = (isinstance(profile, dict) and profile.get("external_allowlist") == []
                           and profile.get("probe_network_scope") ==
                           "PrivateNetwork; only loopback interface/routes are allowed")
    except (OSError, ValueError, ContractError):
        profile_bytes = b""
        empty_allowlist = False
    spec_bytes = _bounded_proc_text(str(SPEC_PATH), 2 * 1024 * 1024).encode("utf-8")
    uid = os.geteuid()
    mount_namespace = _namespace_inode("mnt")
    network_namespace = _namespace_inode("net")
    cgroup_namespace = _namespace_inode("cgroup")
    pid_namespace = _namespace_inode("pid")
    cgroup = _bounded_proc_text("/proc/self/cgroup", 65536).splitlines()
    cgroup_expected = cgroup == ["0::/system.slice/vst-sandbox-probe.service"]
    checks = {
        "automount_disabled": not windows_drive_mounts,
        "interop_disabled": not interop_enabled,
        "no_container_socket": socket_inventory_complete and not sockets,
        "non_root": uid != 0,
        "egress_policy_isolated": isolated_network,
        "loopback_canary": _loopback_canary(),
        "empty_external_allowlist": empty_allowlist,
        "no_unapproved_host_mounts": not host_mounts,
        "expected_cgroup": cgroup_expected,
        "runtime_namespaces_observed": all(type(value) is int and value > 0 for value in
                                            (mount_namespace, network_namespace, cgroup_namespace, pid_namespace)),
    }
    probe = {
        "schema": "VST_S2_RUNTIME_OBSERVATION_V1",
        "checked_properties": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
        "inventory": {
            "mount_table": mountinfo.splitlines(),
            "windows_drive_mounts": windows_drive_mounts,
            "unapproved_host_mounts": host_mounts,
            "wsl_interop_present": interop_present,
            "wsl_interop_enabled": interop_enabled,
            "uid": uid,
            "gid": os.getegid(),
            "cgroup": cgroup,
            "namespace_inodes": {"mount": mount_namespace, "network": network_namespace,
                                  "cgroup": cgroup_namespace, "pid": pid_namespace},
            "network_interfaces": interfaces,
            "network_routes": routes,
            "container_socket_paths_present": sockets,
            "container_socket_inventory_complete": socket_inventory_complete,
            "environment_variable_names": sorted(os.environ.keys()),
            "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
            "network_profile_sha256": hashlib.sha256(profile_bytes).hexdigest(),
            "observed_at_monotonic_ns": time.monotonic_ns(),
        },
    }
    return probe


def validate_fresh_probe(probe: dict[str, Any], *, run_id: str, spec_sha256: str, nonce: str) -> bool:
    """Validate the exact in-memory Supervisor observation and its freshness."""
    if not isinstance(probe, dict):
        return False
    if set(probe) != {"schema", "run_id", "spec_sha256", "nonce", "checked_properties", "result", "inventory"}:
        return False
    checks = probe.get("checked_properties")
    inventory = probe.get("inventory")
    observed_at = inventory.get("observed_at_monotonic_ns") if isinstance(inventory, dict) else None
    age_ns = time.monotonic_ns() - observed_at if type(observed_at) is int else -1
    expected_checks = {
        "automount_disabled", "interop_disabled", "no_container_socket", "non_root",
        "egress_policy_isolated", "loopback_canary", "empty_external_allowlist",
        "no_unapproved_host_mounts", "expected_cgroup", "runtime_namespaces_observed",
    }
    inventory_fields = {
        "mount_table", "windows_drive_mounts", "unapproved_host_mounts", "wsl_interop_present",
        "wsl_interop_enabled", "uid", "gid", "cgroup", "namespace_inodes",
        "network_interfaces", "network_routes", "container_socket_paths_present",
        "container_socket_inventory_complete", "environment_variable_names", "spec_sha256",
        "network_profile_sha256", "observed_at_monotonic_ns",
    }
    return (
        probe.get("schema") == "VST_S2_RUNTIME_OBSERVATION_V1"
        and probe.get("run_id") == run_id and probe.get("spec_sha256") == spec_sha256
        and probe.get("nonce") == nonce and probe.get("result") == "PASS"
        and isinstance(checks, dict) and set(checks) == expected_checks
        and all(value is True for value in checks.values())
        and isinstance(inventory, dict) and set(inventory) == inventory_fields
        and isinstance(inventory.get("mount_table"), list)
        and all(isinstance(line, str) for line in inventory["mount_table"])
        and isinstance(inventory.get("windows_drive_mounts"), list)
        and all(isinstance(line, str) for line in inventory["windows_drive_mounts"])
        and not inventory["windows_drive_mounts"]
        and type(inventory.get("wsl_interop_present")) is bool
        and isinstance(inventory.get("unapproved_host_mounts"), list)
        and not inventory["unapproved_host_mounts"]
        and inventory.get("wsl_interop_enabled") is False
        and type(inventory.get("uid")) is int and inventory["uid"] == 999
        and type(inventory.get("gid")) is int and inventory["gid"] == 989
        and inventory.get("container_socket_paths_present") == []
        and inventory.get("container_socket_inventory_complete") is True
        and inventory.get("cgroup") == ["0::/system.slice/vst-sandbox-probe.service"]
        and isinstance(inventory.get("namespace_inodes"), dict)
        and set(inventory["namespace_inodes"]) == {"mount", "network", "cgroup", "pid"}
        and all(type(value) is int and value > 0 for value in inventory["namespace_inodes"].values())
        and inventory.get("network_interfaces") == ["lo"]
        and isinstance(inventory.get("network_routes"), list)
        and isinstance(inventory.get("spec_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", inventory["spec_sha256"])
        and isinstance(inventory.get("network_profile_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", inventory["network_profile_sha256"])
        and inventory["spec_sha256"] == spec_sha256
        and isinstance(inventory.get("environment_variable_names"), list)
        and all(isinstance(name, str) for name in inventory["environment_variable_names"])
        and type(inventory.get("observed_at_monotonic_ns")) is int
        and 0 <= age_ns <= MAX_FRESH_PROBE_AGE_NS
    )
