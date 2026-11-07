"""Run and capture one isolated runtime observation in Supervisor memory."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import threading
import time
from typing import Any

from .contracts import ContractError, canonical_bytes
from .preflight import MAX_FRESH_PROBE_AGE_NS, PROBE_PROFILE_PATH, SPEC_PATH, validate_fresh_probe

PROBE_UNIT = "vst-sandbox-probe.service"
INACTIVE_DEPENDENT_UNITS = (
    "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
    "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
    "vst-dispatcher.service", "vst-runner.service", "vst-signer.service",
)
JOURNALCTL_PATH = "/usr/bin/journalctl"
SYSTEMCTL_PATH = "/usr/bin/systemctl"
MAX_OUTPUT_BYTES = 1024 * 1024
INVOCATION_ID = re.compile(r"^[0-9a-f]{32}$")
PROBE_EXECUTABLE = "/usr/bin/python3.12"
PROBE_ENTRYPOINT = "/etc/vst-runner/probe-entrypoint.py"
PROBE_DROPIN = "/etc/systemd/system/vst-sandbox-probe.service.d/90-s2-host-path-mask.conf"
PROBE_SANDBOX_PROPERTIES = {
    "Type": "oneshot", "User": "vst-worker", "Group": "vst-worker",
    "Restart": "no", "PrivateTmp": "yes", "PrivateNetwork": "yes",
    "PrivateDevices": "yes", "RestrictAddressFamilies": "AF_UNIX AF_INET",
    "RestrictNamespaces": "yes", "ProtectHome": "yes", "ProtectSystem": "strict",
    "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
    "ProtectControlGroups": "yes", "NoNewPrivileges": "yes",
    "RestrictSUIDSGID": "yes", "CapabilityBoundingSet": "",
    "AmbientCapabilities": "", "UMask": "0077",
    "TimeoutStartUSec": "90s",
    "InaccessiblePaths": "-/init -/home -/mnt -/root -/usr/lib/wsl -/run/WSL -/tmp/.X11-unix",
    "TemporaryFileSystem": "/run/user:ro,mode=0755",
    "DropInPaths": PROBE_DROPIN,
}


def _bounded_command(argv: list[str], *, timeout: float) -> bytes:
    """Drain command output while retaining at most MAX_OUTPUT_BYTES per stream."""
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        raise ContractError("runtime observation command could not start") from exc
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    overflow = {"stdout": False, "stderr": False}

    def drain(name: str, stream) -> None:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            remaining = MAX_OUTPUT_BYTES - len(captured[name])
            if remaining > 0:
                captured[name].extend(chunk[:remaining])
            if len(chunk) > remaining:
                overflow[name] = True

    readers = [threading.Thread(target=drain, args=(name, getattr(process, name)), daemon=True)
               for name in ("stdout", "stderr")]
    for reader in readers:
        reader.start()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # Terminate only the client process; never stop or signal the systemd unit.
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                pass
        for reader in readers:
            reader.join(timeout=2)
        raise ContractError("runtime observation command timed out; outcome is indeterminate and retry is forbidden") from exc
    finally:
        for reader in readers:
            reader.join(timeout=2)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
    if any(overflow.values()):
        raise ContractError("runtime observation command output exceeded its bounded capture")
    if returncode != 0:
        raise ContractError("runtime observation command returned non-zero")
    return bytes(captured["stdout"])


def _validate_probe_exec_start(value: str) -> None:
    path = re.search(r"(?:^|[;{]\s*)path=([^;]+?)\s*;", value)
    argv = re.search(r"(?:^|[;{]\s*)argv\[\]=([^;]+?)\s*;", value)
    if path is None or argv is None:
        raise ContractError("effective probe ExecStart is not inspectable")
    try:
        parsed_argv = shlex.split(argv.group(1).strip())
    except ValueError as exc:
        raise ContractError("effective probe ExecStart argv is malformed") from exc
    expected_argv = [PROBE_EXECUTABLE, "-I", "-S", PROBE_ENTRYPOINT]
    if path.group(1).strip() != PROBE_EXECUTABLE or parsed_argv != expected_argv:
        raise ContractError("effective probe ExecStart differs from the pinned installed executable")


def _timeout_seconds(value: str) -> int | None:
    if value.isdigit():
        microseconds = int(value)
        return microseconds // 1_000_000 if microseconds % 1_000_000 == 0 else None
    matches = list(re.finditer(r"(\d+)(min|s)(?:\s+|$)", value))
    if not matches or "".join(match.group(0) for match in matches).strip() != value.strip():
        return None
    units = {"min": 60, "s": 1}
    return sum(int(match.group(1)) * units[match.group(2)] for match in matches)


def _systemctl_properties(unit: str, properties: tuple[str, ...]) -> dict[str, str]:
    if not unit.endswith((".service", ".socket")) or not properties:
        raise ContractError("systemd unit/property request is malformed")
    raw = _bounded_command([SYSTEMCTL_PATH, "show", unit,
                            "--property=" + ",".join(properties)], timeout=5)
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeError as exc:
        raise ContractError("systemd returned non-text unit properties") from exc
    observed: dict[str, str] = {}
    for line in lines:
        name, separator, value = line.partition("=")
        if not separator or name not in properties or name in observed:
            raise ContractError("systemd returned an ambiguous unit property set")
        observed[name] = value
    if set(observed) != set(properties):
        raise ContractError("systemd returned an incomplete unit property set")
    return observed


def _systemctl_show() -> dict[str, str]:
    properties = (
        "LoadState", "ActiveState", "SubState", "Result", "ExecMainStatus",
        "MainPID", "InvocationID", "ControlGroup", "ExecStart", "Type", "User", "Group",
        "FragmentPath", "NeedDaemonReload",
        "Restart", "TimeoutStartUSec", "PrivateTmp", "PrivateNetwork", "PrivateDevices",
        "RestrictAddressFamilies", "RestrictNamespaces", "ProtectHome", "ProtectSystem",
        "ProtectKernelTunables", "ProtectKernelModules", "ProtectControlGroups",
        "NoNewPrivileges", "RestrictSUIDSGID", "CapabilityBoundingSet",
        "AmbientCapabilities", "UMask", "InaccessiblePaths", "TemporaryFileSystem",
        "DropInPaths",
    )
    observed = _systemctl_properties(PROBE_UNIT, properties)
    _validate_probe_exec_start(observed["ExecStart"])
    for name, expected in PROBE_SANDBOX_PROPERTIES.items():
        if name == "InaccessiblePaths":
            actual_paths = {item.removeprefix("-") for item in observed[name].split()}
            expected_paths = {item.removeprefix("-") for item in expected.split()}
            valid = actual_paths == expected_paths
        elif name == "RestrictAddressFamilies":
            valid = set(observed[name].split()) == set(expected.split())
        elif name == "TimeoutStartUSec":
            valid = _timeout_seconds(observed[name]) == 90
        else:
            valid = observed[name] == expected
        if not valid:
            raise ContractError("effective probe sandbox property differs from its pinned value: " + name)
    if (observed["ControlGroup"] != "/system.slice/vst-sandbox-probe.service"
            or observed["FragmentPath"] != "/etc/systemd/system/vst-sandbox-probe.service"
            or observed["NeedDaemonReload"] != "no"):
        raise ContractError("effective probe fragment, reload state, or ControlGroup differs from its pin")
    return observed


def _assert_units_inactive() -> None:
    for unit in INACTIVE_DEPENDENT_UNITS:
        raw = _bounded_command([
            SYSTEMCTL_PATH, "show", unit,
            "--property=LoadState,ActiveState,SubState,MainPID", "--value",
        ], timeout=5)
        try:
            fields = raw.decode("utf-8", errors="strict").splitlines()
        except UnicodeError as exc:
            raise ContractError("systemd returned invalid dependent-unit state") from exc
        if (len(fields) != 4 or fields[0] != "loaded" or fields[1] != "inactive"
                or fields[2] != "dead" or fields[3] not in {"", "0"}):
            raise ContractError("dependent services must remain inactive before runtime observation")


def _assert_manager_quiescent() -> None:
    raw = _bounded_command([SYSTEMCTL_PATH, "list-jobs", "--no-legend", "--no-pager"], timeout=5)
    if raw.strip() in {b"", b"No jobs running."}:
        return
    try:
        lines = [line.split() for line in raw.decode("utf-8", errors="strict").splitlines() if line.strip()]
    except UnicodeError as exc:
        raise ContractError("systemd job inventory is not text") from exc
    for fields in lines:
        if len(fields) < 4 or not fields[0].isdigit():
            raise ContractError("systemd job inventory contains an unparseable row")
        # Type=notify intentionally keeps this single start job active until the
        # Supervisor has consumed the observation and bound its API listener.
        if (fields[1] == "vst-supervisor.service" and fields[2] == "start"
                and fields[3] in {"running", "waiting"}):
            continue
        raise ContractError("unrelated systemd job is pending during runtime observation")


def classify_store_targets(store_path: str, anchor_path: str) -> str:
    """Classify only a wholly fresh target or a complete, root-controlled Store pair."""
    paths = (store_path, anchor_path)
    if any(not isinstance(path, str) or not path.startswith("/") or "\x00" in path
           or os.path.normpath(path) != path for path in paths):
        raise ContractError("fresh runtime Store and anchor paths must be canonical absolute paths")
    store_path, anchor_path = paths
    targets = (
        store_path, store_path + "-wal", store_path + "-shm", store_path + "-journal",
        anchor_path, anchor_path + ".coord.lock",
    )
    if len(targets) != len(set(targets)):
        raise ContractError("fresh runtime Store paths and sidecars collide")
    state: dict[str, os.stat_result | None] = {}
    for target in targets:
        parent = os.path.dirname(target)
        while True:
            try:
                parent_info = os.stat(parent, follow_symlinks=False)
            except OSError as exc:
                raise ContractError("fresh runtime Store parent is unavailable") from exc
            if (not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != 0
                    or parent_info.st_mode & 0o022):
                raise ContractError("fresh runtime Store parent is not root-controlled")
            if parent == "/":
                break
            parent = os.path.dirname(parent)
        try:
            info = os.lstat(target)
        except FileNotFoundError:
            state[target] = None
            continue
        except OSError as exc:
            raise ContractError("fresh runtime Store state cannot be inspected safely") from exc
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & ~0o600):
            raise ContractError("existing runtime Store material is not one root-owned private regular file")
        state[target] = info

    store_exists = state[store_path] is not None
    anchor_exists = state[anchor_path] is not None
    if store_exists != anchor_exists:
        raise ContractError("runtime Store and external anchor must either both exist or both be absent")
    auxiliary = targets[1:4] + (targets[5],)
    if not store_exists:
        if any(state[target] is not None for target in auxiliary):
            raise ContractError("orphan runtime Store sidecar or coordinator lock exists")
        return "fresh"
    return "recovery"


def _require_fresh_store_targets(store_path: str, anchor_path: str) -> None:
    if classify_store_targets(store_path, anchor_path) != "fresh":
        raise ContractError("one-shot runtime observation requires a fresh Store and anchor")


def assert_runtime_services_inactive() -> None:
    """Recheck the manager and every downstream unit before Store consumption."""
    _assert_manager_quiescent()
    probe = _systemctl_show()
    if (probe["LoadState"] != "loaded" or probe["ActiveState"] != "inactive"
            or probe["SubState"] != "dead" or probe["MainPID"] not in {"", "0"}):
        raise ContractError("one-shot probe is not inactive before Store consumption")
    _assert_units_inactive()


def assert_supervisor_readiness_barrier() -> None:
    """Require systemd to wait for an explicit post-bind READY=1 notification."""
    properties = _systemctl_properties(
        "vst-supervisor.service",
        ("Type", "NotifyAccess", "TimeoutStartUSec", "Before", "FragmentPath",
         "NeedDaemonReload", "MainPID"))
    if (properties["Type"] != "notify" or properties["NotifyAccess"] != "main"
            or _timeout_seconds(properties["TimeoutStartUSec"]) != 360
            or properties["MainPID"] != str(os.getpid())
            or "vst-runner.service" not in properties["Before"].split()
            or properties["FragmentPath"] != "/etc/systemd/system/vst-supervisor.service"
            or properties["NeedDaemonReload"] != "no"):
        raise ContractError("Supervisor unit does not enforce the runtime-readiness barrier")


def _journal_probe(raw: bytes, *, invocation_id: str, run_id: str, nonce: str,
                   spec_sha256: str) -> dict[str, Any]:
    try:
        entries = [json.loads(line) for line in raw.decode("utf-8", errors="strict").splitlines() if line]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("probe journal is not bounded structured JSON") from exc
    if len(entries) != 1 or not isinstance(entries[0], dict):
        raise ContractError("probe invocation must produce exactly one journal record")
    entry = entries[0]
    if (entry.get("_SYSTEMD_UNIT") != PROBE_UNIT
            or entry.get("_SYSTEMD_INVOCATION_ID") != invocation_id
            or entry.get("_UID") != "999" or entry.get("_GID") != "989"
            or not isinstance(entry.get("_PID"), str)
            or not entry["_PID"].isdigit() or int(entry["_PID"]) <= 1
            or not isinstance(entry.get("MESSAGE"), str)):
        raise ContractError("probe journal identity does not match the exact worker invocation")
    try:
        observation = json.loads(entry["MESSAGE"])
    except json.JSONDecodeError as exc:
        raise ContractError("probe journal message is not one runtime observation") from exc
    if not isinstance(observation, dict) or set(observation) != {
            "schema", "checked_properties", "result", "inventory"}:
        raise ContractError("probe observation fields differ from the strict in-memory schema")
    probe = {**observation, "run_id": run_id, "nonce": nonce, "spec_sha256": spec_sha256}
    if not validate_fresh_probe(probe, run_id=run_id, nonce=nonce, spec_sha256=spec_sha256):
        raise ContractError("fresh runtime observation failed its exact schema or identity checks")
    inventory = dict(probe["inventory"])
    inventory["supervisor_probe_pid"] = int(entry["_PID"])
    probe["inventory"] = inventory
    return probe


def _observation_claim_identity(run_id: str, nonce: str, spec_sha256: str,
                                source_config_sha256: dict[str, str]) -> tuple[str, str, bytes, str]:
    private_dir = "/var/lib/vst-runner/private"
    try:
        info = os.stat(private_dir, follow_symlinks=False)
    except OSError as exc:
        raise ContractError("runtime observation marker directory is unavailable") from exc
    if (not os.path.isdir(private_dir) or os.path.islink(private_dir) or info.st_uid != 0
            or info.st_gid != 0 or (info.st_mode & 0o777) != 0o700):
        raise ContractError("runtime observation marker directory is not root-controlled mode 0700")
    body = {"schema": "VST_S2_RUNTIME_OBSERVATION_CLAIM_V1", "run_id": run_id,
            "nonce": nonce, "spec_sha256": spec_sha256,
            "source_config_sha256": source_config_sha256}
    payload = canonical_bytes(body) + b"\n"
    marker_digest = hashlib.sha256(payload).hexdigest()
    marker_name = ".runtime-observation-" + marker_digest + ".json"
    return private_dir, os.path.join(private_dir, marker_name), payload, marker_digest


def verify_existing_observation_claim(run_id: str, nonce: str, spec_sha256: str,
                                      source_config_sha256: dict[str, str]) -> str:
    """Read the exact durable claim for restart recovery without creating or replaying it."""
    _private_dir, marker, expected, marker_digest = _observation_claim_identity(
        run_id, nonce, spec_sha256, source_config_sha256,
    )
    try:
        fd = os.open(marker, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContractError("exact prior runtime observation claim is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1
                or info.st_size != len(expected)):
            raise ContractError("prior runtime observation claim has unsafe identity or size")
        raw = bytearray()
        while len(raw) <= len(expected):
            chunk = os.read(fd, min(65536, len(expected) + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if bytes(raw) != expected:
            raise ContractError("prior runtime observation claim differs from current exact inputs")
    except OSError as exc:
        raise ContractError("prior runtime observation claim could not be read safely") from exc
    finally:
        os.close(fd)
    return marker_digest


def runtime_observation_binding_digest(run_id: str, nonce: str, spec_sha256: str,
                                       source_config_sha256: dict[str, str],
                                       claim_sha256: str) -> str:
    """Deterministic accepted-observation identity; excludes PID, invocation, and monotonic time."""
    if (not isinstance(run_id, str) or not run_id.strip()
            or not isinstance(nonce, str) or not nonce.strip()
            or not re.fullmatch(r"[0-9a-f]{64}", spec_sha256)
            or not re.fullmatch(r"[0-9a-f]{64}", claim_sha256)
            or not isinstance(source_config_sha256, dict) or not source_config_sha256
            or any(not isinstance(key, str) or not key
                   or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for key, value in source_config_sha256.items())):
        raise ContractError("runtime observation binding inputs are malformed")
    return hashlib.sha256(canonical_bytes({
        "schema": "VST_S2_RUNTIME_OBSERVATION_BINDING_V1",
        "result": "PASS",
        "run_id": run_id,
        "nonce": nonce,
        "spec_sha256": spec_sha256,
        "source_config_sha256": source_config_sha256,
        "observation_claim_sha256": claim_sha256,
    })).hexdigest()


def _claim_observation(run_id: str, nonce: str, spec_sha256: str,
                       source_config_sha256: dict[str, str]) -> str:
    private_dir, marker, payload, marker_digest = _observation_claim_identity(
        run_id, nonce, spec_sha256, source_config_sha256,
    )
    try:
        with os.scandir(private_dir) as entries:
            prior = [entry for entry in entries if entry.name.startswith(".runtime-observation-")
                     and entry.name.endswith(".json")]
    except OSError as exc:
        raise ContractError("runtime observation claims cannot be inventoried") from exc
    for entry in prior:
        try:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                raise ContractError("prior runtime observation claim is not a plain file")
            fd = os.open(entry.path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                prior_stat = os.fstat(fd)
                if (prior_stat.st_uid != 0 or prior_stat.st_gid != 0
                        or (prior_stat.st_mode & 0o777) != 0o600 or prior_stat.st_size > 65536):
                    raise ContractError("prior runtime observation claim has unsafe ownership or size")
                raw = os.read(fd, 65537)
            finally:
                os.close(fd)
            previous = json.loads(raw)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ContractError("prior runtime observation claim is malformed") from exc
        if not isinstance(previous, dict) or previous.get("schema") != "VST_S2_RUNTIME_OBSERVATION_CLAIM_V1":
            raise ContractError("prior runtime observation claim has an unknown schema")
        if previous.get("run_id") == run_id or previous.get("nonce") == nonce:
            raise ContractError("run or nonce already has a one-start runtime observation claim")
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        raise ContractError("runtime observation claim already exists; retry is forbidden") from exc
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o600)
        written = os.write(fd, payload)
        if written != len(payload):
            raise ContractError("short write while persisting runtime observation claim")
        os.fsync(fd)
    except OSError as exc:
        raise ContractError("runtime observation claim could not be durably written") from exc
    finally:
        os.close(fd)
    directory_fd = os.open(private_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return marker_digest


def observe_runtime_once(run_id: str, nonce: str,
                         source_config_sha256: dict[str, str], *,
                         store_path: str, anchor_path: str,
                         require_fresh_store: bool = True,
                         persist_one_start_claim: bool = True) -> dict[str, Any]:
    """Start one isolated probe and return its exact evidence in Supervisor memory.

    Fresh installation persists a one-start claim before touching the fresh Store.
    Recovery still runs a new observation, but binds it to the captured systemd
    invocation rather than reusing or rewriting the original durable claim.
    """
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise ContractError("Supervisor runtime observation requires the root POSIX boundary")
    if not isinstance(run_id, str) or not run_id.strip() or not isinstance(nonce, str) or not nonce.strip():
        raise ContractError("Supervisor run identity is malformed")
    if not SPEC_PATH.is_file() or not PROBE_PROFILE_PATH.is_file():
        raise ContractError("runtime observation spec or network profile is unavailable")
    spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    if (not isinstance(source_config_sha256, dict) or not source_config_sha256
            or any(not isinstance(key, str) or not isinstance(value, str)
                   or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for key, value in source_config_sha256.items())):
        raise ContractError("runtime source/config digest binding is malformed")

    systemd_state = _bounded_command([SYSTEMCTL_PATH, "is-system-running"], timeout=5)
    if systemd_state.strip() != b"running":
        raise ContractError("systemd manager is not in the exact running state")
    _assert_units_inactive()
    _assert_manager_quiescent()
    before = _systemctl_show()
    if (before["LoadState"] != "loaded" or before["ActiveState"] != "inactive"
            or before["SubState"] != "dead" or before["MainPID"] not in {"", "0"}
            or before["PrivateNetwork"] != "yes" or before["User"] != "vst-worker"
            or before["Group"] != "vst-worker"
            or before["ControlGroup"] != "/system.slice/vst-sandbox-probe.service"):
        raise ContractError("isolated probe unit is not in its exact loaded/inactive sandbox configuration")

    if require_fresh_store:
        _require_fresh_store_targets(store_path, anchor_path)
    claim_digest = (
        _claim_observation(run_id, nonce, spec_sha256, source_config_sha256)
        if persist_one_start_claim else None
    )
    # One bounded start only. The unit itself has Restart=no and a finite timeout.
    _bounded_command([SYSTEMCTL_PATH, "start", PROBE_UNIT], timeout=95)
    after = _systemctl_show()
    invocation_id = after["InvocationID"]
    if (after["LoadState"] != "loaded" or after["ActiveState"] != "inactive"
            or after["SubState"] != "dead" or after["Result"] != "success"
            or after["ExecMainStatus"] != "0" or after["MainPID"] not in {"", "0"}
            or not INVOCATION_ID.fullmatch(invocation_id)):
        raise ContractError("one-shot probe did not finish successfully under one exact invocation")
    journal = _bounded_command([
        JOURNALCTL_PATH, "--no-pager", "--output=json",
        f"_SYSTEMD_UNIT={PROBE_UNIT}", f"_SYSTEMD_INVOCATION_ID={invocation_id}",
    ], timeout=15)
    result_journal = _bounded_command([
        JOURNALCTL_PATH, "--no-pager", "--output=json", f"UNIT={PROBE_UNIT}",
        f"INVOCATION_ID={invocation_id}", "_PID=1", "_UID=0",
    ], timeout=15)
    try:
        results = [json.loads(line) for line in result_journal.decode("utf-8", "strict").splitlines() if line]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("probe result journal is malformed") from exc
    if (len(results) != 1 or not isinstance(results[0], dict)
            or results[0].get("UNIT") != PROBE_UNIT
            or results[0].get("INVOCATION_ID") != invocation_id
            or results[0].get("_PID") != "1" or results[0].get("_UID") != "0"
            or results[0].get("UNIT_RESULT") != "success"):
        raise ContractError("root systemd result does not attest the exact successful probe invocation")
    final = _systemctl_show()
    if final != after:
        raise ContractError("probe unit identity changed while its journal was captured")
    _assert_manager_quiescent()
    _assert_units_inactive()
    probe = _journal_probe(journal, invocation_id=invocation_id, run_id=run_id,
                           nonce=nonce, spec_sha256=spec_sha256)
    probe["inventory"]["systemd_probe"] = {"unit": PROBE_UNIT, **after}
    probe["inventory"]["source_config_sha256"] = source_config_sha256
    if claim_digest is not None:
        probe["inventory"]["observation_claim_sha256"] = claim_digest
    return probe
