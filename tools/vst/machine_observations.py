"""Read-only S2 machine-observation candidates.

The records produced here are observations, not E5 attestations. This module never signs, returns
PASS, or integrates with the Supervisor's human E5 verifier. Full effective firewall-policy
normalization is deliberately unsupported until its collectors and policy are reviewed.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .contracts import ContractError, canonical_bytes

BUNDLE_SCHEMA = "VST_S2_MACHINE_NETWORK_OBSERVATION_BUNDLE_V1"
RECEIPT_SCHEMA = "VST_S2_MACHINE_OBSERVATION_RECEIPT_V1"
EVALUATION_SCHEMA = "VST_S2_MACHINE_NETWORK_EVALUATION_V1"
MAX_COMMAND_OUTPUT = 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 5
MAX_TOTAL_OUTPUT = 4 * 1024 * 1024
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_NONCE = re.compile(r"^[0-9a-f]{32}$")
_UTC = "%Y-%m-%dT%H:%M:%SZ"

BUNDLE_FIELDS = frozenset({
    "schema", "run_id", "nonce", "source_head", "sandbox_spec_sha256", "started_at_utc",
    "finished_at_utc", "sources", "raw_observations", "bundle_sha256",
})
RECEIPT_FIELDS = frozenset({
    "schema", "source_id", "collector_path", "collector_head", "collector_sha256", "os_id",
    "os_build", "principal", "privilege_boundary", "observation_schema", "collected_at_utc",
    "raw_sha256", "signature",
})
WINDOWS_FIELDS = frozenset({
    "os_id", "os_build", "firewall_profiles", "effective_firewall_rules",
    "wsl_hyperv_firewall_profiles", "effective_wsl_hyperv_firewall_rules", "wsl_distributions",
    "wsl_network_configuration", "host_endpoints", "host_path_exposures", "collection_complete",
    "errors", "raw_command_outputs",
})
WSL_FIELDS = frozenset({
    "os_id", "os_build", "kernel_release", "nft_ruleset_raw", "ipv4_routes_raw",
    "ipv6_routes_raw", "ipv4_rules_raw", "ipv6_rules_raw", "namespaces_raw", "interfaces_raw",
    "mounts_raw", "windows_drive_mounts", "wsl_interop_present", "wsl_interop_enabled",
    "container_socket_paths", "container_socket_inventory_complete", "listeners_raw", "uid", "gid",
    "collection_complete", "errors",
})


def _time(value: object, name: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ContractError(f"{name}: expected canonical UTC timestamp")
    try:
        parsed = dt.datetime.strptime(value, _UTC).replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ContractError(f"{name}: expected canonical YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.strftime(_UTC) != value:
        raise ContractError(f"{name}: timestamp is not canonical")
    return parsed


def _source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _run_fixed(argv: tuple[str, ...], *, name: str,
               windows_module_path: str | None = None) -> tuple[str, dict[str, Any] | None]:
    """Run a constant argv with no shell and bounded time/output."""
    if not argv or not os.path.isabs(argv[0]):
        return "", {"command": name, "status": "UNSUPPORTED", "reason": "fixed executable unavailable"}
    try:
        windows = os.name == "nt"
        process = subprocess.Popen(
            list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=(r"C:\Windows\System32" if windows and windows_module_path is not None else "/"),
            env=({"SystemRoot": r"C:\Windows", "WINDIR": r"C:\Windows",
                  "SystemDrive": "C:", "PATH": "", "TEMP": r"C:\Windows\Temp",
                  "TMP": r"C:\Windows\Temp", "PSModulePath": windows_module_path}
                 if windows and windows_module_path is not None
                 else {"LC_ALL": "C", "PATH": ""}),
            close_fds=True, creationflags=(subprocess.CREATE_NO_WINDOW if windows else 0),
        )
    except OSError:
        return "", {"command": name, "status": "UNKNOWN", "reason": "command unavailable"}
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = threading.Event()

    def drain(label: str, stream: Any) -> None:
        assert stream is not None
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            buffer = outputs[label]
            remaining = MAX_COMMAND_OUTPUT + 1 - len(buffer)
            if remaining > 0:
                buffer.extend(chunk[:remaining])
            if len(chunk) > remaining or len(buffer) > MAX_COMMAND_OUTPUT:
                overflow.set()

    readers = [threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
               threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True)]
    for reader in readers:
        reader.start()
    started = time.monotonic()
    timed_out = False
    while process.poll() is None:
        if overflow.is_set():
            process.kill()
            break
        if time.monotonic() - started >= COMMAND_TIMEOUT_SECONDS:
            timed_out = True
            process.kill()
            break
        time.sleep(0.01)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    for reader in readers:
        reader.join(timeout=1)
    if any(reader.is_alive() for reader in readers):
        return "", {"command": name, "status": "UNKNOWN", "reason": "output stream did not close"}
    if overflow.is_set():
        return "", {"command": name, "status": "UNKNOWN", "reason": "command output exceeded limit"}
    if timed_out:
        return "", {"command": name, "status": "UNKNOWN", "reason": "command timed out"}
    output = outputs["stdout"].decode("utf-8", errors="replace")
    if process.returncode != 0:
        return output, {"command": name, "status": "UNKNOWN", "exit_code": process.returncode,
                        "reason": "command returned nonzero exit status",
                        "stderr": outputs["stderr"].decode("utf-8", errors="replace")}
    return output, None


def _read_bounded(path: str, *, limit: int = MAX_COMMAND_OUTPUT) -> tuple[str, dict[str, Any] | None]:
    try:
        with open(path, "rb") as stream:
            data = stream.read(limit + 1)
    except OSError:
        return "", {"command": path, "status": "UNKNOWN", "reason": "read unavailable"}
    if len(data) > limit:
        return "", {"command": path, "status": "UNKNOWN", "reason": "file exceeds limit"}
    return data.decode("utf-8", errors="replace"), None


def _windows_raw_template() -> dict[str, Any]:
    """Return a structurally exact but explicitly incomplete host observation."""
    return {
        "os_id": platform.system(), "os_build": platform.version(),
        "firewall_profiles": [], "effective_firewall_rules": [],
        "wsl_hyperv_firewall_profiles": [], "effective_wsl_hyperv_firewall_rules": [],
        "wsl_distributions": [], "wsl_network_configuration": [], "host_endpoints": [],
        "host_path_exposures": [], "collection_complete": False,
        "errors": [{"command": "Windows effective-policy collector", "status": "UNSUPPORTED",
                    "reason": "full ActiveStore and WSL/Hyper-V effective-rule normalization is not implemented"}],
        "raw_command_outputs": {},
    }


def collect_windows_observations(*, profile: str = "windows-powershell-5") -> dict[str, Any]:
    """Capture bounded raw Windows output using an explicitly selected PowerShell profile.

    The PowerShell 7 profile is opt-in and has distinct provenance. Neither profile normalizes
    effective policy or can produce a PASS.
    """
    raw = _windows_raw_template()
    raw["raw_command_outputs"] = {"collector_profile": str(profile)}
    if os.name != "nt":
        raw["errors"] = [{"command": "Windows effective-policy collector", "status": "UNSUPPORTED",
                          "reason": "collector requires Windows"}]
        return raw
    # This fixed read-only script obtains ActiveStore profile/rule and WSL-Hyper-V command output.
    # It intentionally does not translate that output into complete effective rules. Filter joins,
    # build support, endpoint/path inventories and cross-checks need a reviewed normalizer first.
    script = r'''
$ErrorActionPreference = 'Stop'
$snapshot = [ordered]@{}
$snapshot.os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber
$snapshot.profiles = Get-NetFirewallProfile -PolicyStore ActiveStore | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction,PolicyStoreSource,PolicyStoreSourceType
$snapshot.rules = Get-NetFirewallRule -PolicyStore ActiveStore | ForEach-Object {
  $r = $_
  [ordered]@{ rule = ($r | Select-Object Name,DisplayName,Enabled,Direction,Action,Profile,PolicyStoreSource,PolicyStoreSourceType);
    address = @(Get-NetFirewallAddressFilter -AssociatedNetFirewallRule $r | Select-Object LocalAddress,RemoteAddress);
    port = @(Get-NetFirewallPortFilter -AssociatedNetFirewallRule $r | Select-Object Protocol,LocalPort,RemotePort);
    application = @(Get-NetFirewallApplicationFilter -AssociatedNetFirewallRule $r | Select-Object Program,Package) }
}
if (Get-Command Get-NetFirewallHyperVVMSetting -ErrorAction SilentlyContinue) {
  $snapshot.hypervProfiles = Get-NetFirewallHyperVVMSetting | Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction
} else { $snapshot.hypervProfiles = $null }
if (Get-Command Get-NetFirewallHyperVRule -ErrorAction SilentlyContinue) {
  $snapshot.hypervRules = Get-NetFirewallHyperVRule | Select-Object Name,Enabled,Direction,Action,Protocol,LocalAddresses,RemoteAddresses,LocalPorts,RemotePorts
} else { $snapshot.hypervRules = $null }
$snapshot.wsl = & wsl.exe --list --verbose 2>&1
$snapshot.wslExitCode = $LASTEXITCODE
$snapshot | ConvertTo-Json -Depth 8 -Compress
'''
    executables = {
        "windows-powershell-5": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "powershell-7": r"C:\Program Files\PowerShell\7\pwsh.exe",
    }
    module_paths = {
        "windows-powershell-5": r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules",
        "powershell-7": (
            r"C:\Program Files\PowerShell\7\Modules;"
            r"C:\Windows\System32\WindowsPowerShell\v1.0\Modules"
        ),
    }
    if not isinstance(profile, str) or profile not in executables:
        raw["errors"] = [{"command": "Windows effective-policy collector",
                          "status": "UNSUPPORTED", "reason": "unknown explicit collector profile"}]
        return raw
    executable = executables[profile]
    # Keep the script fixed and use an absolute executable path for WSL. PATH remains empty.
    script = script.replace("wsl.exe --list", r"C:\Windows\System32\wsl.exe --list")
    output, error = _run_fixed((executable, "-NoLogo", "-NoProfile", "-NonInteractive",
                                "-ExecutionPolicy", "Restricted", "-Command", script),
                               name="Windows ActiveStore/WSL-HyperV read-only snapshot",
                               windows_module_path=module_paths[profile])
    if output:
        raw["raw_command_outputs"] = {"collector_profile": profile, "powershell_snapshot": output}
    else:
        raw["raw_command_outputs"] = {"collector_profile": profile}
    raw["errors"] = ([error] if error else []) + [{
        "command": "Windows observation normalizer", "status": "UNKNOWN",
        "reason": "complete effective-rule, endpoint, path and Windows-WSL correlation normalization is not implemented",
    }]
    return raw


def _read_uid() -> int | None:
    try:
        return os.geteuid()
    except AttributeError:
        return None


def _read_gid() -> int | None:
    try:
        return os.getegid()
    except AttributeError:
        return None


def _collect_mounts() -> tuple[str, list[str], bool, list[dict[str, Any]]]:
    mounts, error = _read_bounded("/proc/self/mounts")
    errors = [error] if error else []
    drives: list[str] = []
    complete = error is None
    for line in mounts.splitlines():
        fields = line.split()
        if len(fields) < 3:
            complete = False
            errors.append({"command": "/proc/self/mounts", "status": "UNKNOWN",
                           "reason": "malformed mount row"})
            continue
        source, _target, filesystem = fields[:3]
        options = fields[3] if len(fields) > 3 else ""
        if filesystem.lower() == "drvfs" or (
            filesystem.lower() == "9p" and re.search(r"(?:^|[;,])aname=drvfs(?:$|[;,])", options)
        ):
            drives.append(line)
    return mounts, drives, complete, errors


def collect_wsl_observations() -> dict[str, Any]:
    """Collect bounded read-only POSIX metadata. Incomplete sources remain explicit UNKNOWN."""
    if os.name != "posix" or not Path("/proc/sys/kernel/osrelease").exists():
        raise ContractError("WSL collector requires a POSIX /proc environment")
    kernel, kernel_error = _read_bounded("/proc/sys/kernel/osrelease")
    release, release_error = _read_bounded("/etc/os-release")
    release_values: dict[str, str] = {}
    for line in release.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            release_values[key] = value.strip().strip('"')
    errors = [item for item in (kernel_error, release_error) if item]
    mounts, drive_mounts, mount_complete, mount_errors = _collect_mounts()
    errors.extend(mount_errors)
    command_outputs: dict[str, str] = {}
    command_map = {
        "nft_ruleset_raw": ("/usr/sbin/nft", "list", "ruleset"),
        "ipv4_routes_raw": ("/usr/sbin/ip", "-4", "route", "show", "table", "all"),
        "ipv6_routes_raw": ("/usr/sbin/ip", "-6", "route", "show", "table", "all"),
        "ipv4_rules_raw": ("/usr/sbin/ip", "-4", "rule", "show"),
        "ipv6_rules_raw": ("/usr/sbin/ip", "-6", "rule", "show"),
        "namespaces_raw": ("/usr/bin/lsns", "--noheadings", "--output", "NS,TYPE,PATH"),
        "interfaces_raw": ("/usr/sbin/ip", "-details", "address", "show"),
        "listeners_raw": ("/usr/bin/ss", "-H", "-lntup"),
    }
    for field, argv in command_map.items():
        output, error = _run_fixed(argv, name=field)
        command_outputs[field] = output
        if error:
            errors.append(error)
    total_output = sum(len(value.encode("utf-8")) for value in command_outputs.values())
    if total_output > MAX_TOTAL_OUTPUT:
        command_outputs = {key: "" for key in command_outputs}
        errors.append({"command": "WSL observation bundle", "status": "UNKNOWN",
                       "reason": "combined command output exceeded limit"})
    interop_path = "/proc/sys/fs/binfmt_misc/WSLInterop"
    interop_present = os.path.lexists(interop_path)
    interop_enabled = False
    if interop_present:
        interop_text, interop_error = _read_bounded(interop_path)
        if interop_error:
            errors.append(interop_error)
        else:
            interop_enabled = "enabled" in interop_text.lower()
    try:
        from .preflight import _container_socket_inventory
        socket_paths, socket_inventory_complete = _container_socket_inventory()
    except Exception:
        socket_paths, socket_inventory_complete = [], False
        errors.append({"command": "container socket inventory", "status": "UNKNOWN",
                       "reason": "bounded socket inventory failed"})
    os_id = release_values.get("ID", "UNKNOWN")
    os_build = release_values.get("VERSION_ID", "UNKNOWN")
    if "microsoft" not in kernel.lower() or os_id != "ubuntu" or os_build != "24.04":
        errors.append({"command": "OS identity", "status": "UNSUPPORTED",
                       "reason": "expected Ubuntu 24.04 on WSL"})
    complete = not errors and mount_complete and socket_inventory_complete
    return {
        "os_id": os_id, "os_build": os_build, "kernel_release": kernel.strip(),
        "nft_ruleset_raw": command_outputs["nft_ruleset_raw"],
        "ipv4_routes_raw": command_outputs["ipv4_routes_raw"],
        "ipv6_routes_raw": command_outputs["ipv6_routes_raw"],
        "ipv4_rules_raw": command_outputs["ipv4_rules_raw"],
        "ipv6_rules_raw": command_outputs["ipv6_rules_raw"],
        "namespaces_raw": command_outputs["namespaces_raw"],
        "interfaces_raw": command_outputs["interfaces_raw"], "mounts_raw": mounts,
        "windows_drive_mounts": drive_mounts, "wsl_interop_present": interop_present,
        "wsl_interop_enabled": interop_enabled, "container_socket_paths": socket_paths,
        "container_socket_inventory_complete": socket_inventory_complete,
        "listeners_raw": command_outputs["listeners_raw"],
        "uid": _read_uid(), "gid": _read_gid(), "collection_complete": complete,
        "errors": errors,
    }


def _source_receipt(source_id: str, raw: dict[str, Any], *, source_head: str,
                    observed_at: str) -> dict[str, Any]:
    raw_digest = hashlib.sha256(canonical_bytes(raw)).hexdigest()
    return {
        "schema": RECEIPT_SCHEMA, "source_id": source_id,
        "collector_path": "tools/vst/machine_observations.py", "collector_head": source_head,
        "collector_sha256": _source_sha256(), "os_id": str(raw.get("os_id", "UNKNOWN")),
        "os_build": str(raw.get("os_build", "UNKNOWN")),
        "principal": str(os.getuid()) if hasattr(os, "getuid") else "UNKNOWN",
        "privilege_boundary": "current-process identity; not an independent trust claim",
        "observation_schema": ("VST_S2_WINDOWS_HOST_OBSERVATION_V1" if source_id == "windows-host"
                               else "VST_S2_WSL_GUEST_OBSERVATION_V1"),
        "collected_at_utc": observed_at, "raw_sha256": raw_digest,
        "signature": None,
    }


def build_observation_bundle(run_id: str, source_head: str, sandbox_spec_sha256: str,
                             windows_raw: dict[str, Any], wsl_raw: dict[str, Any], *,
                             nonce: str | None = None,
                             now: dt.datetime | None = None) -> dict[str, Any]:
    """Bind supplied read-only observations; this does not make them trusted or complete."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise ContractError("observation bundle run_id must be non-empty")
    if len(run_id) > 128 or not run_id[0].isalnum() or any(
            not (char.isalnum() or char in "_.:-") for char in run_id):
        raise ContractError("observation bundle run_id has an invalid format")
    if not isinstance(source_head, str) or not _HEX40.fullmatch(source_head):
        raise ContractError("observation bundle source_head must be a full Git SHA")
    if not isinstance(sandbox_spec_sha256, str) or not _HEX64.fullmatch(sandbox_spec_sha256):
        raise ContractError("observation bundle sandbox digest must be SHA-256")
    nonce = nonce or uuid.uuid4().hex
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise ContractError("observation bundle nonce must be 32 lowercase hex")
    if not isinstance(windows_raw, dict) or set(windows_raw) != WINDOWS_FIELDS:
        raise ContractError("Windows observation does not match its exact schema")
    if not isinstance(wsl_raw, dict) or set(wsl_raw) != WSL_FIELDS:
        raise ContractError("WSL observation does not match its exact schema")
    _validate_windows_raw(windows_raw)
    _validate_wsl_raw(wsl_raw)
    if len(canonical_bytes(windows_raw)) + len(canonical_bytes(wsl_raw)) > MAX_TOTAL_OUTPUT:
        raise ContractError("observation bundle exceeds the combined raw-output limit")
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
        raise ContractError("observation bundle clock must be UTC")
    stamp = current.strftime(_UTC)
    sources = [
        _source_receipt("windows-host", windows_raw, source_head=source_head, observed_at=stamp),
        _source_receipt("wsl-guest", wsl_raw, source_head=source_head, observed_at=stamp),
    ]
    unsigned = {
        "schema": BUNDLE_SCHEMA, "run_id": run_id, "nonce": nonce,
        "source_head": source_head, "sandbox_spec_sha256": sandbox_spec_sha256,
        "started_at_utc": stamp, "finished_at_utc": stamp, "sources": sources,
        "raw_observations": {"windows-host": windows_raw, "wsl-guest": wsl_raw},
    }
    return {**unsigned, "bundle_sha256": hashlib.sha256(canonical_bytes(unsigned)).hexdigest()}


def validate_observation_bundle(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != BUNDLE_FIELDS:
        raise ContractError("machine observation bundle fields do not match the closed schema")
    if value["schema"] != BUNDLE_SCHEMA:
        raise ContractError("machine observation bundle schema is unsupported")
    if not isinstance(value["run_id"], str) or not value["run_id"].strip():
        raise ContractError("machine observation bundle run_id is invalid")
    if not isinstance(value["source_head"], str) or not _HEX40.fullmatch(value["source_head"]):
        raise ContractError("machine observation bundle source_head is invalid")
    if not isinstance(value["sandbox_spec_sha256"], str) or not _HEX64.fullmatch(value["sandbox_spec_sha256"]):
        raise ContractError("machine observation bundle spec digest is invalid")
    if not isinstance(value["nonce"], str) or not _NONCE.fullmatch(value["nonce"]):
        raise ContractError("machine observation bundle nonce is invalid")
    started = _time(value["started_at_utc"], "bundle started_at_utc")
    finished = _time(value["finished_at_utc"], "bundle finished_at_utc")
    if finished < started:
        raise ContractError("machine observation bundle time order is invalid")
    sources = value["sources"]
    raw = value["raw_observations"]
    if not isinstance(sources, list) or not isinstance(raw, dict) or set(raw) != {"windows-host", "wsl-guest"}:
        raise ContractError("machine observation bundle must contain both named sources")
    if len(sources) != 2:
        raise ContractError("machine observation bundle must contain exactly two source receipts")
    by_source = {}
    for source in sources:
        if not isinstance(source, dict) or set(source) != RECEIPT_FIELDS or source.get("schema") != RECEIPT_SCHEMA:
            raise ContractError("machine observation source receipt fields are invalid")
        source_id = source["source_id"]
        if source_id not in {"windows-host", "wsl-guest"} or source_id in by_source:
            raise ContractError("machine observation source ID is missing, duplicated, or unknown")
        for key in ("collector_sha256", "raw_sha256"):
            if not isinstance(source[key], str) or not _HEX64.fullmatch(source[key]):
                raise ContractError(f"machine source receipt {key} is invalid")
        if not isinstance(source["collector_head"], str) or not _HEX40.fullmatch(source["collector_head"]):
            raise ContractError("machine source receipt collector_head is invalid")
        if source["signature"] is not None:
            raise ContractError("unsigned candidate observation receipts are required in this source scope")
        collected = _time(source["collected_at_utc"], "source collected_at_utc")
        if not started <= collected <= finished:
            raise ContractError("machine source receipt timestamp falls outside bundle interval")
        for field in ("collector_path", "os_id", "os_build", "principal", "privilege_boundary"):
            if not isinstance(source[field], str) or not source[field]:
                raise ContractError(f"machine source receipt {field} is invalid")
        if source["collector_head"] != value["source_head"]:
            raise ContractError("machine source receipt head does not match bundle source")
        if source["raw_sha256"] != hashlib.sha256(canonical_bytes(raw[source_id])).hexdigest():
            raise ContractError("machine source receipt does not bind the raw observation")
        by_source[source_id] = source
    if set(by_source) != {"windows-host", "wsl-guest"}:
        raise ContractError("machine observation bundle is missing a source")
    if not isinstance(raw["windows-host"], dict) or set(raw["windows-host"]) != WINDOWS_FIELDS:
        raise ContractError("Windows raw observation fields are invalid")
    if not isinstance(raw["wsl-guest"], dict) or set(raw["wsl-guest"]) != WSL_FIELDS:
        raise ContractError("WSL raw observation fields are invalid")
    _validate_windows_raw(raw["windows-host"])
    _validate_wsl_raw(raw["wsl-guest"])
    unsigned = {key: value[key] for key in BUNDLE_FIELDS if key != "bundle_sha256"}
    expected = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    if value["bundle_sha256"] != expected:
        raise ContractError("machine observation bundle digest is invalid")
    return value


def _validate_error_list(value: object, *, name: str) -> None:
    if not isinstance(value, list):
        raise ContractError(f"{name}: expected an array")
    for error in value:
        if not isinstance(error, dict) or not {"command", "status", "reason"} <= set(error):
            raise ContractError(f"{name}: malformed collection error")
        if set(error) - {"command", "status", "reason", "exit_code", "stderr"}:
            raise ContractError(f"{name}: unknown collection error field")
        if not all(isinstance(error[key], str) for key in ("command", "status", "reason")):
            raise ContractError(f"{name}: malformed collection error value")
        if "exit_code" in error and type(error["exit_code"]) is not int:
            raise ContractError(f"{name}: malformed exit code")
        if "stderr" in error and not isinstance(error["stderr"], str):
            raise ContractError(f"{name}: malformed stderr")


def _validate_windows_raw(value: dict[str, Any]) -> None:
    if not all(isinstance(value[field], str) for field in ("os_id", "os_build")):
        raise ContractError("Windows observation OS identity is invalid")
    if type(value["collection_complete"]) is not bool:
        raise ContractError("Windows observation collection_complete must be boolean")
    _validate_error_list(value["errors"], name="Windows observation errors")
    outputs = value["raw_command_outputs"]
    if not isinstance(outputs, dict) or any(not isinstance(key, str) or not isinstance(item, str)
                                            for key, item in outputs.items()):
        raise ContractError("Windows observation raw command output map is invalid")
    if sum(len(item.encode("utf-8")) for item in outputs.values()) > MAX_TOTAL_OUTPUT:
        raise ContractError("Windows observation raw output exceeds limit")
    for field in ("firewall_profiles", "effective_firewall_rules", "wsl_hyperv_firewall_profiles",
                  "effective_wsl_hyperv_firewall_rules", "wsl_distributions",
                  "wsl_network_configuration", "host_endpoints", "host_path_exposures"):
        if not isinstance(value[field], list):
            raise ContractError(f"Windows observation {field} must be an array")
    if value["collection_complete"]:
        raise ContractError("Windows effective policy normalization is not authorized in this source scope")


def _validate_wsl_raw(value: dict[str, Any]) -> None:
    text_fields = ("os_id", "os_build", "kernel_release", "nft_ruleset_raw", "ipv4_routes_raw",
                   "ipv6_routes_raw", "ipv4_rules_raw", "ipv6_rules_raw", "namespaces_raw",
                   "interfaces_raw", "mounts_raw", "listeners_raw")
    if not all(isinstance(value[field], str) for field in text_fields):
        raise ContractError("WSL observation text field is invalid")
    if not all(isinstance(value[field], list) for field in ("windows_drive_mounts", "container_socket_paths")):
        raise ContractError("WSL observation path lists are invalid")
    if not all(isinstance(item, str) for field in ("windows_drive_mounts", "container_socket_paths")
               for item in value[field]):
        raise ContractError("WSL observation path list contains a non-string")
    for field in ("wsl_interop_present", "wsl_interop_enabled", "container_socket_inventory_complete",
                  "collection_complete"):
        if type(value[field]) is not bool:
            raise ContractError(f"WSL observation {field} must be boolean")
    for field in ("uid", "gid"):
        if value[field] is not None and (type(value[field]) is not int or value[field] < 0):
            raise ContractError(f"WSL observation {field} is invalid")
    _validate_error_list(value["errors"], name="WSL observation errors")
    if value["collection_complete"] and (not value["container_socket_inventory_complete"]
                                          or value["uid"] is None or value["gid"] is None):
        raise ContractError("WSL collection cannot be complete with unknown identity or socket scan")


def evaluate_observation_completeness(value: object, *, expected_run_id: str,
                                      expected_nonce: str, expected_source_head: str,
                                      expected_spec_sha256: str) -> dict[str, Any]:
    """Return only metadata completeness; never an egress verdict or E5 PASS."""
    bundle = validate_observation_bundle(value)
    if (bundle["run_id"] != expected_run_id or bundle["nonce"] != expected_nonce
            or bundle["source_head"] != expected_source_head
            or bundle["sandbox_spec_sha256"] != expected_spec_sha256):
        raise ContractError("machine observation bundle freshness or source binding mismatch")
    missing: list[str] = []
    for source_id, observation in bundle["raw_observations"].items():
        if observation.get("collection_complete") is not True:
            missing.append(source_id)
        if observation.get("errors"):
            missing.append(source_id + ":errors")
    # Both source receipts are unsigned and Windows policy normalization is intentionally held.
    # Caller-provided completeness booleans cannot authenticate either source or yield PASS.
    if not missing:
        missing.extend(("windows-host:unsigned-and-unparsed", "wsl-guest:unsigned-source"))
    unsigned = {"schema": EVALUATION_SCHEMA, "bundle_sha256": bundle["bundle_sha256"],
                "evaluator_sha256": _source_sha256(), "status": "UNKNOWN",
                "predicates": [
                    {"id": "both-sources-complete", "status": "UNKNOWN",
                     "evidence": [{"source_id": "windows-host", "raw_field_path": "collection_complete"},
                                  {"source_id": "wsl-guest", "raw_field_path": "collection_complete"}]},
                    {"id": "authenticated-source-provenance", "status": "UNKNOWN",
                     "evidence": [{"source_id": "windows-host", "raw_field_path": "signature"},
                                  {"source_id": "wsl-guest", "raw_field_path": "signature"}]},
                    {"id": "effective-network-policy", "status": "UNKNOWN",
                     "evidence": [{"source_id": "windows-host",
                                   "raw_field_path": "effective_firewall_rules"}]},
                ],
                "missing_sources": missing, "unmatched_rules": [],
                "limitations": ["unsigned observations", "no approved network policy evaluator",
                                "not an E5 attestation", "no comprehensive egress verdict"]}
    return {**unsigned, "result_sha256": hashlib.sha256(canonical_bytes(unsigned)).hexdigest()}
