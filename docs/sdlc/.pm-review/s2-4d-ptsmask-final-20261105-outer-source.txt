"""Run one authorized, mount-free S2-4 Owner→Runner/TestRun qualification.

Input schema VST_S2_RUNTIME_AUTH_INPUT_V1 is deliberately closed. It contains
only correlated authorization metadata, immutable source/configuration pins,
and one test selector; it must never contain credentials or private key bytes.
The launcher validates the complete input before it creates an exclusive
attempt record or starts WSL. Any started attempt is consumed even if its
outcome is unknown: this command never retries.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

MAX_INPUT_BYTES = 128 * 1024
MAX_WSL_SCRIPT_BYTES = 512 * 1024
MAX_WSL_STDOUT_BYTES = 2 * 1024 * 1024
MAX_WSL_STDERR_BYTES = 256 * 1024
MAX_GIT_BLOB_BYTES = 4 * 1024 * 1024
SYSTEMD_STARTUP_SHUTDOWN_GRACE_SEC = 30
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{15,127}$")
REQUEST_ID = re.compile(r"^(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$")
SELECTOR_NODE = re.compile(r"^test_[A-Za-z0-9_]+(?:\[[A-Za-z0-9_.:-]+\])?$")
AUTH_FIELDS = frozenset({
    "source", "correlated", "verdict", "request_id", "job_id", "user_turn_id",
    "reply_id", "payload_sha256", "retry_cap", "allowed_operation",
})
TOP_FIELDS = frozenset({"schema", "authorization", "identity", "source_pins"})
IDENTITY_FIELDS = frozenset({
    "runtime_source_head", "qualification_source_head", "run_id", "bootstrap_request_id",
    "nonce", "runtime_selector", "bundle_sha256", "config_bundle_sha256",
    "task_manifest_sha256", "selector_test_id", "config_sha256",
})
SOURCE_MAP_FIELDS = frozenset({"runtime", "qualification"})
REQUIRED_RUNTIME_PINS = frozenset({
    "tools/vst/assignment_basis.py", "tools/vst/contracts.py",
    "tools/vst/dispatch_instruction.py", "tools/vst/dispatch_issuance.py",
    "tools/vst/dispatch_owner_client.py", "tools/vst/dispatch_owner_service.py",
    "tools/vst/dispatch_owner_transport.py", "tools/vst/dispatcher_service.py",
    "tools/vst/root_dispatch_issuer.py", "tools/vst/runner.py",
    "tools/vst/runner_service.py", "tools/vst/store.py",
    "tools/vst/supervisor.py", "tools/vst/supervisor_service.py",
})
REQUIRED_QUALIFICATION_PINS = frozenset({
    "tools/qa/run_s2_runtime_qualification.py",
    "tools/qa/s2_runtime_qualification_wsl.py",
})
REQUIRED_CONFIG_PINS = frozenset({
    "/etc/vst-runner/supervisor-service.json", "/etc/vst-runner/runner-service.json",
    "/etc/vst-runner/signer-service.json", "/etc/vst-runner/dispatcher-service.json",
    "/etc/vst-runner/dispatch-owner-service.json", "/etc/vst-runner/fence.json",
    "/etc/vst-runner/assignment-delegation-policy.json",
    "/etc/vst-runner/dispatch-instruction-trust.json",
    "/etc/vst-runner/bootstrap-request.json", "/etc/vst-runner/execution-grant-public.pem",
    "/etc/vst-runner/dispatch-instruction-public.pem", "/etc/vst-runner/network-profile.json",
    "/etc/vst-runner/model-provenance.json", "/etc/vst-runner/reviewer-registry.json",
    "/etc/vst-runner/task-manifest.json", "/etc/vst-runner/reviewer-use-policy.json",
    "/etc/vst-runner/store-event.key", "/etc/vst-runner/startup-supervisor.key",
    "/var/lib/vst-signer/receipt.key",
    "/etc/vst-runner/execution-grant-private.pem",
    "/etc/vst-runner/dispatch-instruction-private.pem", "/var/lib/vst-reviewer/review.key",
    "/etc/systemd/system/vst-supervisor.service", "/etc/systemd/system/vst-signer.service",
    "/etc/systemd/system/vst-runner.service", "/etc/systemd/system/vst-dispatcher.service",
    "/etc/systemd/system/vst-dispatch-owner.service",
    "/etc/systemd/system/vst-dispatch-owner.socket",
    "/etc/systemd/system/vst-assignment-bootstrap.service",
    "/etc/systemd/system/vst-dispatch-issuer.service",
    "/etc/systemd/system/vst-sandbox-probe.service",
    "/etc/systemd/system/vst-supervisor.service.d/rate-limits.conf",
    "/etc/systemd/system/vst-runner.service.d/rate-limits.conf",
    "/etc/systemd/system/vst-runner.service.d/90-s2-host-path-mask.conf",
    "/etc/systemd/system/vst-signer.service.d/rate-limits.conf",
    "/etc/systemd/system/vst-sandbox-probe.service.d/90-s2-host-path-mask.conf",
})
ALLOWED_CONFIG_ROOTS = (
    "/etc/vst-runner/", "/etc/systemd/system/", "/usr/local/libexec/",
    "/var/lib/vst-runner/", "/var/lib/vst-signer/", "/var/lib/vst-reviewer/",
)
WSL_DISTRIBUTION = "Ubuntu-24.04"
WSL_HELPER = Path(__file__).with_name("s2_runtime_qualification_wsl.py")
MOUNT_AUDIT_BASELINE = "788ea48fd48f8c4a78a3c7bed50d7b0776ef2b1d"
SYSTEMD_MASK_TARGETS = (
    "/dev/hugepages", "/dev/pts", "/dev/shm", "/home", "/init", "/mnt", "/proc/acpi", "/proc/bus",
    "/proc/fs", "/proc/irq", "/proc/kallsyms", "/proc/kcore", "/proc/kmsg",
    "/proc/latency_stats", "/proc/mtrr", "/proc/scsi", "/proc/sys/fs/binfmt_misc",
    "/root", "/run/WSL", "/run/credentials", "/run/lock", "/run/shm", "/run/user",
    "/sys/fs/bpf", "/sys/fs/fuse/connections", "/sys/fs/selinux", "/sys/kernel/config",
    "/sys/kernel/debug", "/sys/kernel/tracing", "/tmp/.X11-unix", "/usr/lib/modules",
    "/usr/lib/wsl",
)


class QualificationError(ValueError):
    """A fail-closed input, source, or process-boundary error."""


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError("authorization JSON contains duplicate fields")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise QualificationError("authorization JSON contains a non-finite number")


def _read_json(path: Path, *, maximum: int) -> tuple[dict[str, Any], bytes]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise QualificationError("authorization input is unavailable") from exc
    if not path.is_file() or path.is_symlink() or before.st_size < 2 or before.st_size > maximum:
        raise QualificationError("authorization input must be a bounded regular file")
    # `os.read` uses the CRT descriptor mode on Windows. Keep it binary so
    # CRLF bytes are not translated before the size and identity checks.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise QualificationError("authorization input could not be opened safely") from exc
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise QualificationError("authorization input changed while opening")
        chunks = bytearray()
        while len(chunks) <= maximum:
            piece = os.read(fd, min(65536, maximum + 1 - len(chunks)))
            if not piece:
                break
            chunks.extend(piece)
        after = os.fstat(fd)
        if (len(chunks) > maximum or len(chunks) != opened.st_size
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)):
            raise QualificationError("authorization input changed or exceeded its size limit")
    finally:
        os.close(fd)
    raw = bytes(chunks)
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationError("authorization input is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise QualificationError("authorization input must be a JSON object")
    return value, raw


def _read_bounded_regular(path: Path, *, maximum: int) -> bytes:
    try:
        before = path.lstat()
    except OSError as exc:
        raise QualificationError("pinned source file is unavailable") from exc
    if path.is_symlink() or not path.is_file() or before.st_size > maximum:
        raise QualificationError("pinned source must be a bounded regular file")
    try:
        fd = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise QualificationError("pinned source could not be opened safely") from exc
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise QualificationError("pinned source changed while opening")
        data = bytearray()
        while len(data) <= maximum:
            piece = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not piece:
                break
            data.extend(piece)
        after = os.fstat(fd)
        if (len(data) > maximum or len(data) != opened.st_size
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)):
            raise QualificationError("pinned source changed or exceeded its size limit")
        return bytes(data)
    finally:
        os.close(fd)


def _exact_object(value: Any, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise QualificationError(f"{name} fields do not match the closed schema")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise QualificationError(f"{name} must be lowercase SHA-256 hex")
    return value


def _head(value: Any, name: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise QualificationError(f"{name} must be a full lowercase Git commit ID")
    return value


def _relative_git_path(value: Any, name: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or value.startswith("/")
            or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise QualificationError(f"{name} is not a canonical repository-relative path")
    return value


def _test_selector(value: Any) -> str:
    if not isinstance(value, str) or "\\" in value or "\x00" in value:
        raise QualificationError("identity.selector_test_id is not a canonical pytest selector")
    path, separator, node = value.partition("::")
    parts = path.split("/")
    if (separator != "::" or not path.startswith("tests/")
            or any(part in {"", ".", ".."} for part in parts)
            or not SELECTOR_NODE.fullmatch(node)):
        raise QualificationError("identity.selector_test_id must be one exact canonical pytest node")
    return value


def validate_input(value: Any) -> dict[str, Any]:
    record = _exact_object(value, TOP_FIELDS, "authorization input")
    if record["schema"] != "VST_S2_RUNTIME_AUTH_INPUT_V1":
        raise QualificationError("authorization input schema is not supported")

    auth = _exact_object(record["authorization"], AUTH_FIELDS, "authorization")
    if (auth["source"] != "PM_BRIDGE" or auth["correlated"] is not True
            or auth["verdict"] != "AUTHORIZE_ONE_SHOT"
            or type(auth["retry_cap"]) is not int or auth["retry_cap"] != 0
            or auth["allowed_operation"] != "S2-4_OWNER_RUNNER_TESTRUN"):
        raise QualificationError("authorization is not a correlated one-shot S2-4 grant")
    if not isinstance(auth["request_id"], str) or not REQUEST_ID.fullmatch(auth["request_id"]):
        raise QualificationError("authorization request_id is malformed")
    if not isinstance(auth["job_id"], str) or not OPAQUE_ID.fullmatch(auth["job_id"]):
        raise QualificationError("authorization job_id is malformed")
    if not isinstance(auth["user_turn_id"], str) or not OPAQUE_ID.fullmatch(auth["user_turn_id"]):
        raise QualificationError("authorization user_turn_id is malformed")
    if not isinstance(auth["reply_id"], str) or not OPAQUE_ID.fullmatch(auth["reply_id"]):
        raise QualificationError("authorization reply_id is malformed")
    _digest(auth["payload_sha256"], "authorization.payload_sha256")

    identity = _exact_object(record["identity"], IDENTITY_FIELDS, "identity")
    runtime_head = _head(identity["runtime_source_head"], "identity.runtime_source_head")
    qualification_head = _head(
        identity["qualification_source_head"], "identity.qualification_source_head")
    run_id = identity["run_id"]
    if not isinstance(run_id, str) or not OPAQUE_ID.fullmatch(run_id):
        raise QualificationError("identity.run_id is malformed")
    bootstrap_id = identity["bootstrap_request_id"]
    if not isinstance(bootstrap_id, str) or not REQUEST_ID.fullmatch(bootstrap_id):
        raise QualificationError("identity.bootstrap_request_id is malformed")
    nonce = identity["nonce"]
    if not isinstance(nonce, str) or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise QualificationError("identity.nonce is malformed")
    selector = identity["runtime_selector"]
    if selector != "/opt/vst-runtime-" + runtime_head:
        raise QualificationError("identity.runtime_selector does not name the pinned runtime")
    for name in ("bundle_sha256", "config_bundle_sha256", "task_manifest_sha256"):
        _digest(identity[name], "identity." + name)
    selector_test = _test_selector(identity["selector_test_id"])

    config_hashes = identity["config_sha256"]
    if not isinstance(config_hashes, dict) or not 1 <= len(config_hashes) <= 128:
        raise QualificationError("identity.config_sha256 is missing or exceeds its path bound")
    for path, digest in config_hashes.items():
        if (not isinstance(path, str) or not path.startswith(ALLOWED_CONFIG_ROOTS)
                or "\x00" in path):
            raise QualificationError("configuration hash path is outside the fixed target roots")
        if ".." in PurePosixPath(path).parts or "\\" in path:
            raise QualificationError("configuration hash path is not canonical")
        _digest(digest, "identity.config_sha256 entry")
    if not REQUIRED_CONFIG_PINS <= config_hashes.keys():
        raise QualificationError("configuration pins omit required runtime or key files")
    expected_config_bundle = hashlib.sha256(
        json.dumps(config_hashes, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True, allow_nan=False).encode("ascii")
    ).hexdigest()
    if identity["config_bundle_sha256"] != expected_config_bundle:
        raise QualificationError("config_bundle_sha256 does not bind the complete config hash map")

    source_pins = _exact_object(record["source_pins"], SOURCE_MAP_FIELDS, "source_pins")
    pins: dict[str, dict[str, str]] = {}
    expected_heads = {
        "runtime": runtime_head,
        "qualification": qualification_head,
    }
    for source_name, expected_head in expected_heads.items():
        source_map = source_pins[source_name]
        if not isinstance(source_map, dict) or not 1 <= len(source_map) <= 512:
            raise QualificationError(f"source_pins.{source_name} is missing or too large")
        pins[source_name] = {}
        for path, digest in source_map.items():
            canonical = _relative_git_path(path, f"source_pins.{source_name} path")
            pins[source_name][canonical] = _digest(digest, f"source_pins.{source_name}.{canonical}")
        required_paths = (REQUIRED_RUNTIME_PINS if source_name == "runtime"
                          else REQUIRED_QUALIFICATION_PINS)
        if not required_paths <= pins[source_name].keys():
            raise QualificationError(f"source_pins.{source_name} omits a required implementation file")
        if source_name == "qualification" and pins[source_name].keys() != REQUIRED_QUALIFICATION_PINS:
            raise QualificationError("qualification source pins must cover exactly the two launcher files")
        # The HEAD is consumed below during exact blob verification; retaining it
        # here makes the identity association explicit in the normalized result.
        if not HEX40.fullmatch(expected_head):
            raise QualificationError("source pin revision is malformed")

    return {"authorization": dict(auth), "identity": dict(identity), "source_pins": pins}


def _git(root: Path, *args: str, maximum: int = MAX_GIT_BLOB_BYTES) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
         "-C", str(root), "--no-replace-objects", *args],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=30,
    )
    if result.returncode != 0 or len(result.stdout) > maximum:
        raise QualificationError("exact Git source inspection failed or exceeded its bound")
    return result.stdout


def verify_source_pins(root: Path, validated: dict[str, Any]) -> None:
    identity = validated["identity"]
    for source_name, revision in (("runtime", identity["runtime_source_head"]),):
        resolved = _git(root, "rev-parse", "--verify", revision + "^{commit}", maximum=1024)
        if resolved.decode("ascii", "strict").strip() != revision:
            raise QualificationError(f"{source_name} Git revision does not resolve exactly")
    archive_paths = (
        "tools/vst", "tools/qa/install_wsl_runner_runtime.sh",
        "tools/qa/install_wsl_worker_helper.sh", "tools/qa/verify_wsl_source_bundle.py",
        "tools/qa/verify_wsl_runtime_stage.py",
        "tools/qa/worker_exec.c", "docs/SANDBOX_SPEC.md",
    )
    archive = _git(root, "archive", "--format=tar", identity["runtime_source_head"],
                   "--", *archive_paths, maximum=64 * 1024 * 1024)
    if hashlib.sha256(archive).hexdigest() != identity["bundle_sha256"]:
        raise QualificationError("runtime bundle digest does not match the exact pinned Git archive")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        runtime_files = {
            member.name: hashlib.sha256(bundle.extractfile(member).read()).hexdigest()
            for member in bundle.getmembers() if member.isfile()
        }
    archive_pins = validated["source_pins"]["runtime"]
    if runtime_files != archive_pins:
        raise QualificationError("runtime source pins do not exactly cover the reviewed source archive")
    qualification_head = identity["qualification_source_head"]
    resolved_head = _git(root, "rev-parse", "--verify", "HEAD", maximum=1024)
    if resolved_head.decode("ascii", "strict").strip() != qualification_head:
        raise QualificationError("qualification source HEAD differs from the authorized exact repository HEAD")
    for path, expected in validated["source_pins"]["qualification"].items():
        blob = _git(root, "show", f"{qualification_head}:{path}")
        working = _read_bounded_regular(root / Path(*path.split("/")), maximum=MAX_WSL_SCRIPT_BYTES)
        if hashlib.sha256(blob).hexdigest() != expected or working != blob:
            raise QualificationError("qualification launcher differs from its exact committed Git blob")


def refuse_historical_identity(root: Path, validated: dict[str, Any]) -> None:
    """Reject any run/request/nonce already recorded by an earlier S2 attempt."""
    identity = validated["identity"]
    forbidden = {
        identity["run_id"], identity["bootstrap_request_id"], identity["nonce"],
        validated["authorization"]["request_id"],
    }
    evidence = root / "docs" / "sdlc" / "evidence"
    for path in evidence.glob("s2-runtime-qual-*.attempt.json"):
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                continue
            old, _raw = _read_json(path, maximum=2 * 1024 * 1024)
        except (OSError, QualificationError) as exc:
            raise QualificationError("historical attempt identity inventory is incomplete") from exc
        seen: set[str] = set()
        stack: list[Any] = [old]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    if key in {"run_id", "request_id", "bootstrap_request_id", "nonce"} and isinstance(value, str):
                        seen.add(value)
                    stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
        if forbidden & seen:
            raise QualificationError("authorization reuses an identity present in historical attempt evidence")


def _exclusive_record(path: Path, initial: dict[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise QualificationError("attempt output already exists or cannot be created exclusively") from exc
    _write_record(fd, initial)
    return fd


def _write_record(fd: int, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, sort_keys=True, ensure_ascii=True, indent=2) + "\n").encode("ascii")
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    view = memoryview(encoded)
    while view:
        count = os.write(fd, view)
        view = view[count:]
    os.fsync(fd)


def _load_wsl_script() -> bytes:
    try:
        content = _read_bounded_regular(WSL_HELPER, maximum=MAX_WSL_SCRIPT_BYTES)
    except (OSError, QualificationError) as exc:
        raise QualificationError("mount-free WSL protocol is unavailable") from exc
    return content


def _transient_unit_name(run_id: str) -> str:
    if not OPAQUE_ID.fullmatch(run_id):
        raise QualificationError("transient unit identity input is malformed")
    return "vst-s2-qual-" + hashlib.sha256(run_id.encode("ascii")).hexdigest()[:16] + ".service"


def _run_bounded_wsl(script: bytes, *, unit_name: str, runtime_max_sec: int) -> dict[str, Any]:
    """Run one helper in its own exact transient systemd mount namespace."""
    if not re.fullmatch(r"vst-s2-qual-[0-9a-f]{16}\.service", unit_name):
        raise QualificationError("transient unit name is not deterministic and bounded")
    if runtime_max_sec not in {60, 2400}:
        raise QualificationError("transient unit runtime limit is outside the approved profiles")
    mask_paths = list(SYSTEMD_MASK_TARGETS)
    mask_paths.append("/sys/fs/cgroup/system.slice/" + unit_name + "/memory.pressure")
    isolation = [
        "--wait", "--collect", "--pipe", "--quiet", "--unit=" + unit_name,
        "--property=PrivateDevices=yes", "--property=ProtectSystem=strict",
        "--property=ProtectKernelTunables=yes", "--property=ProtectKernelModules=yes",
        "--property=ProtectKernelLogs=yes", "--property=ProtectControlGroups=yes",
        "--property=NoNewPrivileges=yes",
        "--property=RuntimeMaxSec=" + str(runtime_max_sec) + "s",
        "--property=InaccessiblePaths=" + " ".join(sorted(mask_paths)),
    ]
    process = subprocess.Popen(
        ["wsl.exe", "--distribution", WSL_DISTRIBUTION, "--user", "root",
         "--exec", "/usr/bin/systemd-run", *isolation, "--",
         "/usr/bin/python3.12", "-I", "-B", "-S", "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        bufsize=0, close_fds=True,
    )

    class Capture:
        def __init__(self, cap: int):
            self.cap = cap
            self.prefix = bytearray()
            self.digest = hashlib.sha256()
            self.total = 0

        def drain(self, stream) -> None:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                self.total += len(chunk)
                self.digest.update(chunk)
                if len(self.prefix) < self.cap:
                    self.prefix.extend(chunk[:self.cap - len(self.prefix)])

        def result(self) -> dict[str, Any]:
            return {"bytes": self.total, "sha256": self.digest.hexdigest(),
                    "prefix": bytes(self.prefix), "truncated": self.total > len(self.prefix)}

    out = Capture(MAX_WSL_STDOUT_BYTES)
    err = Capture(MAX_WSL_STDERR_BYTES)
    import threading
    readers = [threading.Thread(target=out.drain, args=(process.stdout,), daemon=True),
               threading.Thread(target=err.drain, args=(process.stderr,), daemon=True)]
    for thread in readers:
        thread.start()

    writer_error: list[str] = []
    def write_input() -> None:
        try:
            assert process.stdin is not None
            view = memoryview(script)
            while view:
                count = process.stdin.write(view)
                if count is None or count <= 0:
                    raise BrokenPipeError("WSL stdin closed before the bounded protocol was sent")
                view = view[count:]
            process.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            writer_error.append(type(exc).__name__)
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass

    writer = threading.Thread(target=write_input, daemon=True)
    writer.start()
    timed_out = False
    try:
        process.wait(timeout=runtime_max_sec + SYSTEMD_STARTUP_SHUTDOWN_GRACE_SEC)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
    writer.join(timeout=10)
    for thread in readers:
        thread.join(timeout=10)
    out_result, err_result = out.result(), err.result()
    if writer.is_alive() or any(thread.is_alive() for thread in readers):
        raise QualificationError("bounded WSL pipe handlers did not terminate")
    return {
        "exit_code": process.returncode, "timed_out": timed_out,
        "writer_error": writer_error[0] if writer_error else None,
        "stdout": out_result, "stderr": err_result,
        "unit_name": unit_name, "runtime_max_sec": runtime_max_sec,
        "systemd_properties": isolation[5:],
    }


def _baseline_mount_decoder(root: Path) -> tuple[str, str]:
    resolved = _git(root, "rev-parse", "--verify", MOUNT_AUDIT_BASELINE + "^{commit}", maximum=1024)
    if resolved.decode("ascii", "strict").strip() != MOUNT_AUDIT_BASELINE:
        raise QualificationError("unchanged mount parser baseline does not resolve to its exact reviewed commit")
    source = _git(root, "show", MOUNT_AUDIT_BASELINE + ":tools/qa/s2_runtime_qualification_wsl.py",
                  maximum=MAX_WSL_SCRIPT_BYTES).decode("utf-8", "strict")
    tree = ast.parse(source)
    decoder = next((node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "_decode_mountinfo"), None)
    if decoder is None:
        raise QualificationError("unchanged mount parser is absent from the approved baseline")
    segment = ast.get_source_segment(source, decoder)
    if not segment:
        raise QualificationError("unchanged mount parser source could not be extracted exactly")
    return segment, hashlib.sha256(segment.encode("utf-8")).hexdigest()


def _inject_protocol_values(prefix: bytes, helper: bytes) -> bytes:
    marker = b"AUTH = json.loads(AUTH)\n"
    if helper.count(marker) != 1:
        raise QualificationError("WSL protocol value-injection point is not unique")
    # Keep module docstring, future imports, and standard-library imports before
    # the injected assignments so the streamed program remains valid Python.
    offset = helper.index(marker)
    return helper[:offset] + prefix + helper[offset:]


def _python_literal(value: str | bool) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    raise QualificationError("WSL protocol value has no safe Python literal encoding")


def run_read_only_mount_audit(*, root: Path, experiment_id: str,
                              expected_launcher_sha256: str,
                              expected_helper_sha256: str) -> int:
    """Run the single adjudicated mount-only experiment; it creates no attempt file."""
    if not experiment_id or not OPAQUE_ID.fullmatch(experiment_id):
        raise QualificationError("read-only experiment identity is malformed")
    sha256_input = re.compile(r"^[0-9a-fA-F]{64}$")
    if (not isinstance(expected_launcher_sha256, str)
            or not isinstance(expected_helper_sha256, str)
            or not sha256_input.fullmatch(expected_launcher_sha256)
            or not sha256_input.fullmatch(expected_helper_sha256)):
        raise QualificationError("exact reviewed source hashes are required for the mount-only experiment")
    # Digest hex is case-insensitive; normalize before exact byte-digest comparison.
    expected_launcher_sha256 = expected_launcher_sha256.lower()
    expected_helper_sha256 = expected_helper_sha256.lower()
    launcher = _read_bounded_regular(Path(__file__), maximum=MAX_WSL_SCRIPT_BYTES)
    helper = _read_bounded_regular(WSL_HELPER, maximum=MAX_WSL_SCRIPT_BYTES)
    launcher_hash, helper_hash = hashlib.sha256(launcher).hexdigest(), hashlib.sha256(helper).hexdigest()
    if launcher_hash != expected_launcher_sha256 or helper_hash != expected_helper_sha256:
        raise QualificationError("mount-only experiment source differs from the exact reviewed file hashes")
    baseline_source, baseline_hash = _baseline_mount_decoder(root)
    unit_name = _transient_unit_name(experiment_id)
    values = {
        "AUTH": "{}", "TRANSIENT_UNIT": unit_name, "MOUNT_AUDIT_ONLY": True,
        "BASELINE_DECODER_SOURCE": baseline_source,
        "BASELINE_DECODER_SHA256": baseline_hash,
        "BASELINE_DECODER_REVISION": MOUNT_AUDIT_BASELINE,
    }
    prefix = "".join(key + " = " + _python_literal(value) + "\n"
                     for key, value in values.items()).encode("ascii")
    script = _inject_protocol_values(prefix, helper)
    if len(script) > MAX_WSL_SCRIPT_BYTES:
        raise QualificationError("mount-only protocol exceeded its bounded transfer size")
    outer: dict[str, Any] = {"unit_name": unit_name, "runtime_max_sec": 60}
    source_identity = {
        "launcher_sha256": launcher_hash, "helper_sha256": helper_hash,
        "baseline_revision": MOUNT_AUDIT_BASELINE, "baseline_decoder_sha256": baseline_hash,
    }

    def emit_hold(reason: str, *, terminal: str = "HOLD") -> int:
        report = {
            "schema": "VST_S2_RUNTIME_MOUNT_AUDIT_OUTER_V1",
            "terminal": terminal, "reason": reason,
            "source_identity": source_identity, "outer_process": outer,
            "experiment_id": experiment_id,
        }
        print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
        return 2

    try:
        result = _run_bounded_wsl(script, unit_name=unit_name, runtime_max_sec=60)
    except (QualificationError, OSError, subprocess.SubprocessError) as exc:
        outer["runner_error_type"] = type(exc).__name__
        return emit_hold("bounded WSL runner ended without a complete result; do not retry",
                         terminal="UNKNOWN")
    stdout, stderr = result["stdout"], result["stderr"]
    outer.update({
        "exit_code": result["exit_code"], "timed_out": result["timed_out"],
        "writer_error": result["writer_error"], "unit_name": result["unit_name"],
        "runtime_max_sec": result["runtime_max_sec"],
        "systemd_properties": result["systemd_properties"],
        "stdout_bytes": stdout["bytes"], "stdout_sha256": stdout["sha256"],
        "stdout_truncated": stdout["truncated"],
        "stdout_prefix": stdout["prefix"][:16384].decode("utf-8", "replace"),
        "stderr_bytes": stderr["bytes"], "stderr_sha256": stderr["sha256"],
        "stderr_truncated": stderr["truncated"],
        "stderr_prefix": stderr["prefix"][:16384].decode("utf-8", "replace"),
    })
    if result["timed_out"] or result["writer_error"] or stdout["truncated"] or stderr["truncated"]:
        return emit_hold("bounded process result is incomplete; do not retry", terminal="UNKNOWN")
    try:
        protocol = json.loads(stdout["prefix"], object_pairs_hook=_no_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, QualificationError):
        return emit_hold("read-only experiment did not return bounded JSON evidence")
    if not isinstance(protocol, dict) or protocol.get("schema") != "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1":
        return emit_hold("read-only experiment returned an unexpected evidence schema")
    audit = protocol.get("mount_audit")
    if isinstance(audit, dict) and audit.get("schema") == "VST_S2_RUNTIME_MOUNT_AUDIT_V1":
        protocol_terminal, audit_terminal = protocol.get("terminal"), audit.get("terminal")
        if protocol_terminal not in {"PASS", "HOLD"} or audit_terminal not in {"PASS", "HOLD"}:
            audit["terminal"] = "HOLD"
            audit["reason"] = "protocol terminal status is invalid"
        elif protocol_terminal != audit_terminal:
            audit["terminal"] = "HOLD"
            audit["reason"] = "protocol and mount-audit terminal statuses disagree"
        elif result["exit_code"] != 0 and audit_terminal == "PASS":
            audit["terminal"] = "HOLD"
            audit["reason"] = "outer transient unit exited nonzero despite helper PASS"
        audit["source_identity"] = {
            "launcher_sha256": launcher_hash, "helper_sha256": helper_hash,
            "baseline_revision": MOUNT_AUDIT_BASELINE, "baseline_decoder_sha256": baseline_hash,
        }
        audit["outer_process"] = outer
        report = audit
    else:
        report = {"schema": "VST_S2_RUNTIME_MOUNT_AUDIT_OUTER_V1",
                  "terminal": "HOLD", "reason": protocol.get("reason", "helper stopped before mount audit"),
                  "protocol": protocol, "source_identity": source_identity,
                  "outer_process": outer, "experiment_id": experiment_id}
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
    return 0 if result["exit_code"] == 0 and report.get("terminal") == "PASS" else 2


def run_once(input_path: Path, output_path: Path, *, root: Path) -> int:
    if not input_path.is_absolute() or not output_path.is_absolute():
        raise QualificationError("authorization input and attempt output paths must be absolute")
    if not input_path.resolve().is_relative_to(root) or not output_path.resolve().is_relative_to(root):
        raise QualificationError("authorization input and attempt output must stay in the project")
    if not output_path.resolve().is_relative_to(root / "docs" / "sdlc" / "evidence"):
        raise QualificationError("attempt output must be under docs/sdlc/evidence")
    raw_record, raw_bytes = _read_json(input_path, maximum=MAX_INPUT_BYTES)
    validated = validate_input(raw_record)
    verify_source_pins(root, validated)
    refuse_historical_identity(root, validated)
    wsl_code = _load_wsl_script()
    if hashlib.sha256(wsl_code).hexdigest() != validated["source_pins"]["qualification"][
            "tools/qa/s2_runtime_qualification_wsl.py"]:
        raise QualificationError("streamed WSL protocol differs from its exact qualification source pin")
    # The authorization and deterministic unit identity are embedded as
    # bounded Python literals. Neither crosses a shell parser or command line.
    compact = json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    unit_name = _transient_unit_name(validated["identity"]["run_id"])
    prefix = ("AUTH = " + json.dumps(compact, ensure_ascii=True) + "\n"
              + "TRANSIENT_UNIT = " + json.dumps(unit_name) + "\n"
              + "MOUNT_AUDIT_ONLY = False\n"
              + "BASELINE_DECODER_SOURCE = \"\"\n"
              + "BASELINE_DECODER_SHA256 = \"\"\n"
              + "BASELINE_DECODER_REVISION = \"\"\n").encode("ascii")
    script = _inject_protocol_values(prefix, wsl_code)
    if len(script) > MAX_WSL_SCRIPT_BYTES:
        raise QualificationError("authorization plus WSL protocol exceeded its transfer bound")
    initial = {
        "schema": "VST_S2_RUNTIME_QUALIFICATION_ATTEMPT_V1",
        "state": "STARTING",
        "authorization_input_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "authorization_request_id": validated["authorization"]["request_id"],
        "authorization_reply_id": validated["authorization"]["reply_id"],
        "identity": {key: validated["identity"][key] for key in (
            "runtime_source_head", "qualification_source_head", "run_id", "bootstrap_request_id",
            "nonce", "runtime_selector", "bundle_sha256", "config_bundle_sha256",
            "task_manifest_sha256", "selector_test_id",
        )},
        "source_pins_verified": True,
        "wsl_distribution": WSL_DISTRIBUTION,
        "transient_unit": unit_name,
        "retry_cap": 0,
    }
    fd = _exclusive_record(output_path, initial)
    try:
        initial["state"] = "INDETERMINATE_UNTIL_TERMINAL_RECORD"
        _write_record(fd, initial)
        try:
            result = _run_bounded_wsl(script, unit_name=unit_name, runtime_max_sec=2400)
        except OSError as exc:
            initial.update(state="INDETERMINATE", error_type=type(exc).__name__, retry="PROHIBITED")
            _write_record(fd, initial)
            raise QualificationError("the one permitted WSL invocation has an unknown outcome; no retry") from exc
        stdout, stderr = result["stdout"], result["stderr"]
        if (result["timed_out"] or result["writer_error"]
                or stdout["truncated"] or stderr["truncated"]):
            initial.update(
                state="INDETERMINATE", exit_code=result["exit_code"],
                stdout_bytes=stdout["bytes"], stderr_bytes=stderr["bytes"],
                stdout_sha256=stdout["sha256"], stderr_sha256=stderr["sha256"],
                retry="PROHIBITED",
            )
            _write_record(fd, initial)
            raise QualificationError("WSL output exceeded evidence bounds; attempt is consumed")
        try:
            protocol = json.loads(stdout["prefix"], object_pairs_hook=_no_duplicate_pairs)
        except (UnicodeDecodeError, json.JSONDecodeError, QualificationError) as exc:
            initial.update(
                state="INDETERMINATE", exit_code=result["exit_code"],
                stdout_bytes=stdout["bytes"], stdout_sha256=stdout["sha256"],
                stderr_bytes=stderr["bytes"], stderr_sha256=stderr["sha256"],
                retry="PROHIBITED",
            )
            _write_record(fd, initial)
            raise QualificationError("WSL did not return a valid one-shot evidence record") from exc
        if not isinstance(protocol, dict) or protocol.get("schema") != "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1":
            initial.update(
                state="INDETERMINATE", exit_code=result["exit_code"],
                stdout_bytes=stdout["bytes"], stdout_sha256=stdout["sha256"],
                stderr_bytes=stderr["bytes"], stderr_sha256=stderr["sha256"],
                retry="PROHIBITED",
            )
            _write_record(fd, initial)
            raise QualificationError("WSL returned an unrecognized protocol record")
        initial.update(
            state="COMPLETE" if result["exit_code"] == 0 and protocol.get("terminal") == "PASS" else "HOLD",
            exit_code=result["exit_code"],
            protocol=protocol,
            stdout_bytes=stdout["bytes"], stdout_sha256=stdout["sha256"],
            stderr_bytes=stderr["bytes"], stderr_sha256=stderr["sha256"],
            retry="PROHIBITED",
        )
        _write_record(fd, initial)
        print(json.dumps({"attempt": str(output_path), "state": initial["state"],
                          "exit_code": result["exit_code"]}, sort_keys=True))
        return result["exit_code"]
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization-input", type=Path)
    parser.add_argument("--attempt-output", type=Path)
    parser.add_argument("--mount-audit-only", action="store_true")
    parser.add_argument("--experiment-id")
    parser.add_argument("--expected-launcher-sha256")
    parser.add_argument("--expected-helper-sha256")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        if args.mount_audit_only:
            if (args.authorization_input is not None or args.attempt_output is not None
                    or not args.experiment_id or not args.expected_launcher_sha256
                    or not args.expected_helper_sha256):
                raise QualificationError("mount-only mode requires an experiment ID and both exact source hashes only")
            return run_read_only_mount_audit(
                root=root, experiment_id=args.experiment_id,
                expected_launcher_sha256=args.expected_launcher_sha256,
                expected_helper_sha256=args.expected_helper_sha256)
        if (args.authorization_input is None or args.attempt_output is None
                or args.experiment_id is not None or args.expected_launcher_sha256 is not None
                or args.expected_helper_sha256 is not None):
            raise QualificationError("runtime mode requires exactly authorization input and attempt output")
        return run_once(args.authorization_input, args.attempt_output, root=root)
    except (QualificationError, OSError, subprocess.SubprocessError) as exc:
        print("S2 runtime qualification refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
