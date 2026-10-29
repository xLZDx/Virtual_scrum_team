"""stdlib-only sandbox pre-flight inventory; no third-party packages required."""
from __future__ import annotations

import hashlib
import os
import re
import socket
import time
import uuid
from pathlib import Path
from typing import Any

from .contracts import ContractError
from .signing import sign

PROBE_LABEL = b"vst-sandbox-probe-v2\0"
SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "SANDBOX_SPEC.md"
BLOCKED_EGRESS_TARGET = ("198.51.100.1", 9)
CONTAINER_SOCKETS = (
    "/run/docker.sock", "/var/run/docker.sock", "/run/containerd/containerd.sock",
    "/run/podman/podman.sock",
)

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


def collect_inventory(run_id: str, nonce: str | None = None, *,
                      network_policy_attestation: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ContractError("run_id must be non-empty")
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise ContractError("sandbox probe requires a POSIX sandbox")
    nonce = nonce or uuid.uuid4().hex
    mounts = Path("/proc/self/mounts").read_text(encoding="utf-8", errors="replace")
    interop_path = Path("/proc/sys/fs/binfmt_misc/WSLInterop")
    interop_present = interop_path.exists()
    interop_enabled = False
    if interop_present:
        try:
            interop_enabled = "enabled" in interop_path.read_text(encoding="ascii", errors="ignore").lower()
        except OSError:
            interop_enabled = True  # unknown is unsafe
    windows_drive_mounts = []
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        source, _target, filesystem = fields[:3]
        options = fields[3] if len(fields) >= 4 else ""
        wsl_drvfs_9p = filesystem.lower() == "9p" and re.search(
            r"(?:^|[;,])aname=drvfs(?:$|[;,])", options
        ) is not None
        # WSL exposes automounted Windows volumes as drvfs mounts, either
        # directly or through 9p with aname=drvfs. Other /mnt mounts such as
        # WSLg are not evidence of Windows-drive automount.
        if (filesystem.lower() == "drvfs" or wsl_drvfs_9p) and re.fullmatch(
            r"[A-Za-z]:\\?", source
        ):
            windows_drive_mounts.append(line)
    sockets, socket_inventory_complete = _container_socket_inventory()
    attestation = network_policy_attestation
    attestation_valid_shape = isinstance(attestation, dict) and set(attestation) == {
        "run_id", "spec_sha256", "nonce", "environment_id", "policy_sha256",
        "evidence_sha256", "empty_external_allowlist", "no_container_socket",
        "no_unapproved_host_paths", "signature",
    } and attestation.get("run_id") == run_id and attestation.get("spec_sha256") == hashlib.sha256(
        SPEC_PATH.read_bytes()
    ).hexdigest() and attestation.get("nonce") == nonce
    uid = os.geteuid()
    checks = {
        "automount_disabled": not windows_drive_mounts,
        "interop_disabled": not interop_enabled,
        "no_container_socket": socket_inventory_complete and not sockets and attestation_valid_shape
            and attestation.get("no_container_socket") is True,
        "non_root": uid != 0,
        "external_egress_blocked": _blocked_egress(),  # limited smoke probe only
        "loopback_canary": _loopback_canary(),
        "empty_external_allowlist": attestation_valid_shape and attestation.get("empty_external_allowlist") is True,
    }
    spec_bytes = SPEC_PATH.read_bytes()
    return {
        "run_id": run_id,
        "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
        "nonce": nonce,
        "checked_properties": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
        "inventory": {
            "mount_table": mounts.splitlines(),
            "windows_drive_mounts": windows_drive_mounts,
            "wsl_interop_present": interop_present,
            "wsl_interop_enabled": interop_enabled,
            "uid": uid,
            "gid": os.getegid(),
            "container_socket_paths_present": sockets,
            "container_socket_inventory_complete": socket_inventory_complete,
            "blocked_egress_target": list(BLOCKED_EGRESS_TARGET),
            "blocked_egress_probe_scope": "single reserved-target smoke probe; does not prove egress policy",
            "network_policy_attestation": attestation,
            "environment_variable_names": sorted(os.environ.keys()),
            "observed_at_monotonic_ns": time.monotonic_ns(),
        },
    }


def sign_inventory(inventory: dict[str, Any], runner_key: bytes) -> dict[str, Any]:
    required = {"run_id", "spec_sha256", "nonce", "checked_properties", "result", "inventory"}
    if not isinstance(inventory, dict) or set(inventory) != required:
        raise ContractError("probe inventory fields do not match contract")
    signed = dict(inventory)
    signed["signature"] = sign(inventory, runner_key, PROBE_LABEL)
    return signed


def sign_network_policy_attestation(attestation: dict[str, Any], operator_key: bytes) -> dict[str, Any]:
    """Operator-side helper; keep the operator root outside runner/worker processes."""
    from .signing import OPERATOR_NETWORK_POLICY_LABEL, sign
    required = {"run_id", "spec_sha256", "nonce", "environment_id", "policy_sha256",
                "evidence_sha256", "empty_external_allowlist", "no_container_socket",
                "no_unapproved_host_paths"}
    if not isinstance(attestation, dict) or set(attestation) != required:
        raise ContractError("network policy attestation fields do not match contract")
    signed = dict(attestation)
    signed["signature"] = sign(attestation, operator_key, OPERATOR_NETWORK_POLICY_LABEL)
    return signed


def sign_inventory_with_service(inventory: dict[str, Any], *, signer_socket: str) -> dict[str, Any]:
    """Return an inventory signed by the authenticated runner-only signer."""
    from .signer import sign_probe_over_socket
    required = {"run_id", "spec_sha256", "nonce", "checked_properties", "result", "inventory"}
    if not isinstance(inventory, dict) or set(inventory) != required:
        raise ContractError("probe inventory fields do not match contract")
    signed = dict(inventory)
    signed["signature"] = sign_probe_over_socket(signer_socket, inventory["nonce"], inventory)
    return signed


def verify_fresh_probe(probe: dict[str, Any], *, run_id: str, spec_sha256: str, nonce: str, key: bytes) -> bool:
    from .signing import verify
    if not isinstance(probe, dict):
        return False
    checks = probe.get("checked_properties")
    expected_checks = {
        "automount_disabled", "interop_disabled", "no_container_socket", "non_root",
        "external_egress_blocked", "loopback_canary", "empty_external_allowlist",
    }
    return (
        probe.get("run_id") == run_id and probe.get("spec_sha256") == spec_sha256
        and probe.get("nonce") == nonce and probe.get("result") == "PASS"
        and isinstance(checks, dict) and set(checks) == expected_checks
        and all(value is True for value in checks.values())
        and isinstance(probe.get("inventory"), dict)
        and probe["inventory"].get("container_socket_inventory_complete") is True
        and isinstance(probe["inventory"].get("network_policy_attestation"), dict)
        and verify(probe, key, PROBE_LABEL)
    )


def verify_network_policy_attestation(attestation: object, *, run_id: str, spec_sha256: str,
                                      nonce: str, key: bytes) -> bool:
    from .signing import OPERATOR_NETWORK_POLICY_LABEL, verify
    fields = {"run_id", "spec_sha256", "nonce", "environment_id", "policy_sha256",
              "evidence_sha256", "empty_external_allowlist", "no_container_socket",
              "no_unapproved_host_paths", "signature"}
    if not isinstance(attestation, dict) or set(attestation) != fields:
        return False
    import re
    return (attestation.get("run_id") == run_id and attestation.get("spec_sha256") == spec_sha256
            and attestation.get("nonce") == nonce
            and isinstance(attestation.get("environment_id"), str) and bool(attestation["environment_id"].strip())
            and all(isinstance(attestation.get(k), str) and re.fullmatch(r"[0-9a-f]{64}", attestation[k])
                    for k in ("policy_sha256", "evidence_sha256"))
            and all(attestation.get(k) is True for k in
                    ("empty_external_allowlist", "no_container_socket", "no_unapproved_host_paths"))
            and verify(attestation, key, OPERATOR_NETWORK_POLICY_LABEL))
