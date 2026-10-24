"""stdlib-only sandbox pre-flight inventory; no third-party packages required."""
from __future__ import annotations

import hashlib
import os
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
    "/run/podman/podman.sock", "/run/user/1000/podman/podman.sock",
)


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


def collect_inventory(run_id: str, nonce: str | None = None) -> dict[str, Any]:
    if not isinstance(run_id, str) or not run_id.strip():
        raise ContractError("run_id must be non-empty")
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise ContractError("sandbox probe requires a POSIX sandbox")
    mounts = Path("/proc/self/mounts").read_text(encoding="utf-8", errors="replace")
    interop_path = Path("/proc/sys/fs/binfmt_misc/WSLInterop")
    interop_present = interop_path.exists()
    interop_enabled = False
    if interop_present:
        try:
            interop_enabled = "enabled" in interop_path.read_text(encoding="ascii", errors="ignore").lower()
        except OSError:
            interop_enabled = True  # unknown is unsafe
    automount_lines = [line for line in mounts.splitlines() if "/mnt/" in line and len(line.split()) >= 2]
    sockets = sorted(path for path in CONTAINER_SOCKETS if os.path.exists(path))
    uid = os.geteuid()
    checks = {
        "automount_disabled": not automount_lines,
        "interop_disabled": not interop_enabled,
        "no_container_socket": not sockets,
        "non_root": uid != 0,
        "external_egress_blocked": _blocked_egress(),
        "loopback_canary": _loopback_canary(),
        "empty_external_allowlist": True,
    }
    spec_bytes = SPEC_PATH.read_bytes()
    return {
        "run_id": run_id,
        "spec_sha256": hashlib.sha256(spec_bytes).hexdigest(),
        "nonce": nonce or uuid.uuid4().hex,
        "checked_properties": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
        "inventory": {
            "mount_table": mounts.splitlines(),
            "wsl_interop_present": interop_present,
            "wsl_interop_enabled": interop_enabled,
            "uid": uid,
            "gid": os.getegid(),
            "container_socket_paths_present": sockets,
            "blocked_egress_target": list(BLOCKED_EGRESS_TARGET),
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
        and verify(probe, key, PROBE_LABEL)
    )
