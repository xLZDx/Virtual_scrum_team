"""Persistent manifest-only runner service for the delegated systemd unit."""

from __future__ import annotations

import json
import hashlib
import logging
import os
import re
import socket
import signal
import stat
import struct
import subprocess
import sys
import time
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from .peer_pidfd import peer_pidfd_socket_option
from .contracts import (
    ContractError, canonical_bytes, manifest_sha256, validate_receipt,
    validate_task_manifest,
)
from .execution_grant import (
    AmbiguousExecutionAuthorityError, ExecutionAuthority, verify_execution_grant,
)
from .supervisor_service import (
    SupervisorClient, _peer_pidfd,
    _pidfd_alive, _read_peer_cgroup,
)

MAX_RUNNER_REQUEST_BYTES = 1024 * 1024
MAX_RUNNER_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_DISPATCH_TIMEOUT_SEC = 1900.0
DEFAULT_CONFIG_PATH = "/etc/vst-runner/runner-service.json"
_HEADER = struct.Struct("!I")
_WORKER_EXEC_HELPER_PREFIX = "/usr/local/libexec/vst-s4-worker-exec-"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_HEAD = re.compile(r"^[0-9a-f]{40}$")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON object key")
        result[key] = value
    return result


def _read_root_controlled_json(path: str, *, max_bytes: int) -> dict:
    if os.name != "posix" or not os.path.isabs(path):
        raise ContractError("runner trusted files require absolute POSIX paths")
    current = os.path.dirname(path)
    while True:
        try:
            directory = os.stat(current, follow_symlinks=False)
        except OSError as exc:
            raise ContractError("runner trusted-file directory is unavailable") from exc
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0
                or directory.st_mode & 0o022):
            raise ContractError("runner trusted-file directory is not root-controlled")
        if current == "/":
            break
        current = os.path.dirname(current)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContractError("runner trusted file is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_size > max_bytes):
            raise ContractError("runner trusted file has unsafe type, owner, mode, or size")
        content = bytearray()
        while len(content) <= max_bytes:
            chunk = os.read(fd, min(65536, max_bytes + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > max_bytes:
            raise ContractError("runner trusted file exceeds its size limit")
    finally:
        os.close(fd)
    try:
        value = json.loads(content, object_pairs_hook=_unique_json_object)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ContractError("runner trusted file is malformed JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("runner trusted file must contain a JSON object")
    return value


@dataclass(frozen=True)
class WindowsWorkerServiceConfig:
    """Pinned Worker service settings; it contains no signing material."""

    pipe_name: str
    worker_sid: str
    worker_service: str
    runner_sid: str
    runner_service: str
    repository_root: str
    max_request_bytes: int = MAX_RUNNER_REQUEST_BYTES
    max_response_bytes: int = MAX_RUNNER_RESPONSE_BYTES
    max_timeout_sec: int = 1800
    max_output_bytes: int = 1024 * 1024

    @classmethod
    def from_runtime(cls, runtime: Any, *, repository_root: str) -> "WindowsWorkerServiceConfig":
        from .windows_service_host import WindowsRuntimeConfig
        if not isinstance(runtime, WindowsRuntimeConfig):
            raise ContractError("Windows Worker requires the shared WindowsRuntimeConfig")
        worker = runtime.identity("worker")
        runner = runtime.identity("runner")
        return cls(
            pipe_name="runner-worker", worker_sid=worker.service_sid,
            worker_service=worker.service_name, runner_sid=runner.service_sid,
            runner_service=runner.service_name, repository_root=repository_root,
        )

    def validate(self) -> None:
        if os.name != "nt":
            raise ContractError("Windows Worker service is available only on Windows")
        if (not isinstance(self.pipe_name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", self.pipe_name)
                or not isinstance(self.worker_sid, str) or not re.fullmatch(r"S-1-\d+(?:-\d+){1,15}", self.worker_sid)
                or not isinstance(self.runner_sid, str) or not re.fullmatch(r"S-1-\d+(?:-\d+){1,15}", self.runner_sid)
                or self.worker_sid == self.runner_sid
                or self.worker_service != "VSTWorker" or self.runner_service != "VSTRunner"):
            raise ContractError("Windows Worker service identity configuration is invalid")
        if not isinstance(self.repository_root, str) or not os.path.isabs(self.repository_root):
            raise ContractError("Windows Worker repository root must be absolute")
        for name, value, maximum in (
            ("max_request_bytes", self.max_request_bytes, MAX_RUNNER_REQUEST_BYTES),
            ("max_response_bytes", self.max_response_bytes, MAX_RUNNER_RESPONSE_BYTES),
            ("max_timeout_sec", self.max_timeout_sec, 1800),
            ("max_output_bytes", self.max_output_bytes, 16 * 1024 * 1024),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ContractError(f"Windows Worker {name} is outside its bound")


class WindowsWorkerService:
    """Execute one Runner-authorized manifest command under the Worker SID.

    The service receives no Store mutation callback and no Signer/key access.
    Its two injected trust callbacks are supplied by the SCM composition root:
    one verifies the grant with the configured public-key ring, the other reads
    (but cannot change) the exact grant's RESERVED state from Supervisor.
    """

    def __init__(
        self, config: WindowsWorkerServiceConfig, *,
        verify_grant: Callable[[dict], dict],
        reserved_check: Callable[[dict], dict[str, Any]],
        listener: Any | None = None,
    ) -> None:
        config.validate()
        if not callable(verify_grant) or not callable(reserved_check):
            raise ContractError("Windows Worker trust callbacks are incomplete")
        from .windows_named_pipe import WindowsNamedPipeListener
        from .windows_service_host import WindowsRoleIdentity, assert_current_service_identity

        self.config = config
        self._verify_grant = verify_grant
        self._reserved_check = reserved_check
        self._shutdown = threading.Event()
        self._listener = listener or WindowsNamedPipeListener(
            config.pipe_name, server_sid=config.worker_sid,
            server_service=config.worker_service,
            allowed_client_services={config.runner_sid: config.runner_service},
            timeout_sec=1.0,
        )
        identity = WindowsRoleIdentity("worker", config.worker_service, config.worker_sid, None)
        assert_current_service_identity(identity)

    def shutdown(self) -> None:
        self._shutdown.set()
        self._listener.close()

    def serve_forever(self) -> None:
        while not self._shutdown.is_set():
            connection = self._listener.accept(timeout_sec=0.5)
            if connection is None:
                continue
            with connection:
                self._handle(connection)

    def _handle(self, connection: Any) -> None:
        request_id: str | None = None
        try:
            connection.settimeout(30.0)
            size = _HEADER.unpack(_recv_exact(connection, _HEADER.size))[0]
            if size < 2 or size > self.config.max_request_bytes:
                raise ContractError("Windows Worker request exceeds its size limit")
            payload = _recv_exact(connection, size)
            request = json.loads(payload, object_pairs_hook=_unique_json_object)
            if (not isinstance(request, dict) or set(request) != {
                    "version", "grant", "manifest", "slot", "argv", "timeout_sec", "max_output_bytes",
                } or type(request["version"]) is not int or request["version"] != 1
                    or canonical_bytes(request) != payload):
                raise ContractError("Windows Worker request does not match its canonical contract")
            grant = self._verify_grant(request["grant"])
            if not isinstance(grant, dict) or grant != request["grant"]:
                raise ContractError("Windows Worker grant verifier did not preserve the exact signed grant")
            request_id = grant.get("request_id")
            manifest = validate_task_manifest(request["manifest"])
            digest = manifest_sha256(manifest)
            slot = request["slot"]
            argv = request["argv"]
            timeout_sec = request["timeout_sec"]
            cap = request["max_output_bytes"]
            if (not isinstance(slot, str) or not isinstance(argv, list) or not argv
                    or any(not isinstance(part, str) or not part for part in argv)
                    or type(timeout_sec) is not int or not 1 <= timeout_sec <= self.config.max_timeout_sec
                    or type(cap) is not int or not 1 <= cap <= self.config.max_output_bytes):
                raise ContractError("Windows Worker command request is malformed")
            if (grant.get("manifest_sha256") != digest
                    or grant.get("task_id") != manifest.get("task_id")
                    or grant.get("slot") != slot
                    or type(grant.get("execution_deadline_sec")) is not int
                    or timeout_sec > grant["execution_deadline_sec"]
                    or grant.get("service_generation") is None):
                raise ContractError("Windows Worker grant does not bind the manifest command")
            pinned = [item["argv"] for item in manifest["mandatory_commands"]
                      if item["slot"] == slot]
            if argv not in pinned:
                raise ContractError("Windows Worker command is not an exact mandatory manifest argv")
            reservation = self._reserved_check(grant)
            if (not isinstance(reservation, dict) or set(reservation) != {
                    "reserved", "service_generation", "grant_id", "payload_sha256",
                } or reservation.get("reserved") is not True
                    or reservation.get("service_generation") != grant["service_generation"]
                    or reservation.get("grant_id") != grant["grant_id"]
                    or reservation.get("payload_sha256") != hashlib.sha256(canonical_bytes(grant)).hexdigest()):
                raise ContractError("Supervisor has not durably reserved this exact grant and generation")
            if os.path.normcase(os.path.realpath(self.config.repository_root)) != os.path.normcase(self.config.repository_root):
                raise ContractError("Windows Worker repository root must be canonical")
            from .runner import _run_one, build_environment
            code, stdout, info = _run_one(
                argv, self.config.repository_root, float(timeout_sec), build_environment({}), cap,
                require_job_object=True,
            )
            if info.get("job_object") is not True or info.get("capture_incomplete") is True:
                raise ContractError("Windows Worker process containment or output capture was not confirmed")
            response = {"ok": True, "exit_code": code, "stdout": stdout, "info": info,
                        "request_id": request_id, "service_generation": grant["service_generation"]}
        except Exception:
            response = {"ok": False, "error": "worker_refused"}
        encoded = canonical_bytes(response)
        if len(encoded) > self.config.max_response_bytes:
            encoded = canonical_bytes({"ok": False, "error": "response_too_large"})
        try:
            connection.sendall(_HEADER.pack(len(encoded)) + encoded)
        except OSError:
            return


class WindowsWorkerClient:
    """Runner-side one-command client for the SCM Worker service pipe."""

    def __init__(self, pipe_name: str, *, worker_sid: str, worker_service: str,
                 timeout_sec: float = MAX_DISPATCH_TIMEOUT_SEC) -> None:
        from .windows_named_pipe import WindowsNamedPipeClient
        self._pipe = WindowsNamedPipeClient(
            pipe_name, expected_server_sid=worker_sid,
            expected_server_service=worker_service, timeout_sec=timeout_sec,
        )

    def run(self, *, grant: dict, manifest: dict, slot: str, argv: list[str],
            timeout_sec: int, max_output_bytes: int) -> tuple[int, str, dict]:
        payload = canonical_bytes({
            "version": 1, "grant": grant, "manifest": manifest, "slot": slot,
            "argv": argv, "timeout_sec": timeout_sec, "max_output_bytes": max_output_bytes,
        })
        if len(payload) > MAX_RUNNER_REQUEST_BYTES:
            raise ContractError("Windows Worker request exceeds its size limit")
        with self._pipe.connect() as connection:
            connection.sendall(_HEADER.pack(len(payload)) + payload)
            size = _HEADER.unpack(_recv_exact(connection, _HEADER.size))[0]
            if size < 2 or size > MAX_RUNNER_RESPONSE_BYTES:
                raise ContractError("Windows Worker response exceeds its size limit")
            response = json.loads(_recv_exact(connection, size), object_pairs_hook=_unique_json_object)
        if (not isinstance(response, dict) or set(response) != {
                "ok", "exit_code", "stdout", "info", "request_id", "service_generation",
            } or response.get("ok") is not True or type(response["exit_code"]) is not int
                or not isinstance(response["stdout"], str) or not isinstance(response["info"], dict)
                or response["request_id"] != grant.get("request_id")
                or response["service_generation"] != grant.get("service_generation")
                or response["info"].get("job_object") is not True):
            raise ContractError("Windows Worker did not confirm the exact job-contained command")
        return response["exit_code"], response["stdout"], response["info"]


class WindowsRunnerService:
    """SCM-hosted Runner endpoint for Dispatcher-authenticated local grants."""

    def __init__(
        self, *, pipe_name: str, runner_sid: str, dispatcher_sid: str,
        supervisor: Any, worker_client: WindowsWorkerClient,
        signer_pipe_name: str, signer_sid: str, repository_root: str,
        runner_id: str, audience: str, grant_verifier: Callable[[dict], dict],
        service_identity: Any, listener: Any | None = None,
        max_request_bytes: int = MAX_RUNNER_REQUEST_BYTES,
    ) -> None:
        if os.name != "nt":
            raise ContractError("Windows Runner service is available only on Windows")
        from .windows_named_pipe import WindowsNamedPipeListener
        from .windows_service_host import WindowsRoleIdentity, assert_current_service_identity

        for value, label in ((runner_sid, "Runner"), (dispatcher_sid, "Dispatcher"),
                             (signer_sid, "Signer")):
            if not isinstance(value, str) or not re.fullmatch(r"S-1-\d+(?:-\d+){1,15}", value):
                raise ContractError(f"Windows {label} service SID is invalid")
        if len({runner_sid, dispatcher_sid, signer_sid}) != 3:
            raise ContractError("Windows Runner, Dispatcher, and Signer identities must be distinct")
        if (not isinstance(repository_root, str) or not os.path.isabs(repository_root)
                or not isinstance(runner_id, str) or not runner_id
                or not isinstance(audience, str) or not audience
                or not callable(grant_verifier)
                or not callable(getattr(supervisor, "claim", None))
                or not callable(getattr(supervisor, "reserve", None))
                or not callable(getattr(supervisor, "complete", None))
                or not callable(getattr(supervisor, "worker_reservation", None))
                or not callable(getattr(worker_client, "run", None))):
            raise ContractError("Windows Runner service composition is incomplete")
        if type(max_request_bytes) is not int or not 1024 <= max_request_bytes <= MAX_RUNNER_REQUEST_BYTES:
            raise ContractError("Windows Runner request limit is invalid")
        assert_current_service_identity(service_identity)
        self.pipe_name = pipe_name
        self.runner_sid = runner_sid
        self.dispatcher_sid = dispatcher_sid
        self.supervisor = supervisor
        self.worker_client = worker_client
        self.signer_pipe_name = signer_pipe_name
        self.signer_sid = signer_sid
        self.repository_root = repository_root
        self.runner_id = runner_id
        self.audience = audience
        self.grant_verifier = grant_verifier
        self.service_identity = service_identity
        self.max_request_bytes = max_request_bytes
        self._listener = listener or WindowsNamedPipeListener(
            pipe_name, server_sid=runner_sid, server_service="VSTRunner",
            allowed_client_services={dispatcher_sid: "VSTDispatcher"}, timeout_sec=1.0,
        )
        self._shutdown = threading.Event()
        self._fatal_error: BaseException | None = None

    def shutdown(self) -> None:
        self._shutdown.set()
        self._listener.close()

    def serve_forever(self) -> None:
        while not self._shutdown.is_set():
            try:
                connection = self._listener.accept(timeout_sec=0.5)
            except OSError:
                if self._shutdown.is_set():
                    break
                raise
            if connection is None:
                continue
            with connection:
                self._handle(connection)
            if self._fatal_error is not None:
                raise ContractError("Windows Runner stopped after an ambiguous grant outcome") from self._fatal_error

    def _handle(self, connection: Any) -> None:
        grant: dict | None = None
        try:
            connection.settimeout(30.0)
            size = _HEADER.unpack(_recv_exact(connection, _HEADER.size))[0]
            if size < 2 or size > self.max_request_bytes:
                raise ContractError("Windows Runner request exceeds its size limit")
            payload = _recv_exact(connection, size)
            request = json.loads(payload, object_pairs_hook=_unique_json_object)
            if (not isinstance(request, dict) or set(request) != {"version", "grant", "artifact_paths"}
                    or type(request["version"]) is not int or request["version"] != 1
                    or not isinstance(request["grant"], dict)
                    or not isinstance(request["artifact_paths"], list)
                    or any(not isinstance(path, str) for path in request["artifact_paths"])
                    or canonical_bytes(request) != payload):
                raise ContractError("Windows Runner request does not match its canonical contract")
            grant = request["grant"]
            manifest = self.supervisor.manifest(grant.get("task_id"), grant.get("manifest_sha256"))
            receipt = self._run_grant(grant, manifest, request["artifact_paths"])
            response = {"status": "COMPLETE", "receipt": receipt}
        except AmbiguousExecutionAuthorityError as exc:
            self._fatal_error = exc
            self._shutdown.set()
            response = {"status": "REFUSED", "error_code": "AMBIGUOUS_AUTHORITY"}
        except Exception:
            response = {"status": "REFUSED", "error_code": "EXECUTION_REFUSED"}
        encoded = canonical_bytes(response)
        if len(encoded) > MAX_RUNNER_RESPONSE_BYTES:
            encoded = canonical_bytes({"status": "REFUSED", "error_code": "RESPONSE_TOO_LARGE"})
        try:
            connection.sendall(_HEADER.pack(len(encoded)) + encoded)
        except OSError:
            return

    def _run_grant(self, grant: dict, manifest: dict, artifact_paths: list[str]) -> dict:
        from .execution_grant import ExecutionAuthority
        from .runner import run_manifest_commands
        from .windows_service_host import assert_current_service_identity

        generation = self.supervisor.generation()
        authority = ExecutionAuthority(
            grant, daemon_uid=None, service_generation=generation,
            trusted_keys={}, openssl_path="", audience=self.audience,
            daemon_identity_check=lambda: (assert_current_service_identity(self.service_identity) is None),
            grant_verifier=self.grant_verifier,
            daemon_boundary_check=lambda: self.supervisor.generation() == generation,
            claim=lambda value: self.supervisor.claim(value),
            claim_status=lambda value: self.supervisor.claim_status(value),
            terminalize_no_execution=lambda value, reason: self.supervisor.terminalize_no_execution(value, reason),
            reserve=lambda value: self.supervisor.reserve(value),
            complete=lambda value, receipt: self.supervisor.complete(value, receipt),
        )
        deadline = grant.get("execution_deadline_sec")
        if type(deadline) is not int or not 1 <= deadline <= MAX_DISPATCH_TIMEOUT_SEC:
            raise ContractError("Windows Runner grant deadline is invalid")
        previous = self.supervisor.previous_receipt(grant["task_id"], grant["slot"])
        if grant["attempt"] == 1 and previous is not None:
            raise ContractError("first execution attempt unexpectedly has a prior receipt")
        report: dict = {}
        try:
            return run_manifest_commands(
                manifest=manifest, slot=grant["slot"], attempt=grant["attempt"],
                epoch=grant["epoch"], resolved_model=grant["resolved_model"],
                invocation_id=grant["invocation_id"], runner_id=self.runner_id,
                signer_socket="runner-signer", cwd=self.repository_root,
                worker_uid=0, worker_gid=0, worker_exec_helper_head="",
                worker_exec_helper_path="", verify_worker_exec_helper=lambda: None,
                run_id=grant["run_id"], model_provenance_sha256=grant["model_provenance_sha256"],
                execution_authority=authority, created_at=datetime.now(timezone.utc).isoformat(),
                prev_receipt_sha256=previous, artifact_paths=artifact_paths,
                timeout_sec=deadline, deadline_sec=deadline,
                worker_executor=self.worker_client, signer_server_sid=self.signer_sid,
                signer_server_service="VSTSigner", report=report,
            )
        except Exception as exc:
            if authority.reservation_confirmed and not authority.completion_confirmed:
                raise AmbiguousExecutionAuthorityError(
                    "Windows reserved execution failed before durable COMPLETE; terminating service generation"
                ) from exc
            if authority.claim_confirmed and not authority.no_execution_confirmed:
                authority.terminalize_no_execution("RUNNER_PRESPAWN_FAILURE")
            raise


class WindowsRunnerClient:
    """Dispatcher-side framed client for the SCM Runner endpoint."""

    def __init__(self, pipe_name: str, *, runner_sid: str, runner_service: str = "VSTRunner",
                 timeout_sec: float = MAX_DISPATCH_TIMEOUT_SEC) -> None:
        from .windows_named_pipe import WindowsNamedPipeClient
        self._pipe = WindowsNamedPipeClient(
            pipe_name, expected_server_sid=runner_sid,
            expected_server_service=runner_service, timeout_sec=timeout_sec,
        )

    def dispatch(self, grant: dict, *, artifact_paths: list[str] | None = None,
                 timeout_sec: float = MAX_DISPATCH_TIMEOUT_SEC) -> dict:
        paths = [] if artifact_paths is None else artifact_paths
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            raise ContractError("Windows Runner artifact paths are malformed")
        payload = canonical_bytes({"version": 1, "grant": grant, "artifact_paths": paths})
        if len(payload) > MAX_RUNNER_REQUEST_BYTES:
            raise ContractError("Windows Runner request exceeds its size limit")
        with self._pipe.connect() as connection:
            connection.settimeout(timeout_sec)
            connection.sendall(_HEADER.pack(len(payload)) + payload)
            size = _HEADER.unpack(_recv_exact(connection, _HEADER.size))[0]
            if size < 2 or size > MAX_RUNNER_RESPONSE_BYTES:
                raise ContractError("Windows Runner response exceeds its size limit")
            response = json.loads(_recv_exact(connection, size), object_pairs_hook=_unique_json_object)
        if not isinstance(response, dict) or response.get("status") != "COMPLETE" or not isinstance(response.get("receipt"), dict):
            raise ContractError("Windows Runner refused the dispatch or returned no complete receipt")
        receipt = validate_receipt(response["receipt"])
        for field in ("task_id", "manifest_sha256", "slot", "attempt", "epoch", "runner_id", "invocation_id"):
            if receipt[field] != grant.get(field):
                raise ContractError("Windows Runner receipt does not match the exact dispatched grant")
        return receipt


def read_service_generation_record(config: "RunnerServiceConfig") -> dict:
    """Read the exact manager generation established by the root lifecycle helper."""
    record = _read_root_controlled_json(config.generation_record_path, max_bytes=65536)
    required = {
        "version", "state", "unit", "invocation_id", "control_group",
        "cgroup_device", "cgroup_inode", "lock_device", "lock_inode",
        "generation", "predecessor_outcome", "sequence", "recorded_at",
        "previous_record_sha256", "record_sha256",
    }
    if set(record) != required:
        raise ContractError("runner lifecycle record fields do not match the service contract")
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    expected_hash = hashlib.sha256(canonical_bytes(body)).hexdigest()
    if record["record_sha256"] != expected_hash:
        raise ContractError("runner lifecycle record hash is invalid")
    try:
        file_stat = os.stat(config.generation_record_path, follow_symlinks=False)
    except OSError as exc:
        raise ContractError("runner lifecycle record identity is unavailable") from exc
    if (file_stat.st_uid != 0 or stat.S_IMODE(file_stat.st_mode) != 0o644
            or not stat.S_ISREG(file_stat.st_mode)):
        raise ContractError("runner lifecycle record must be root-owned and read-only")
    invocation_id = os.environ.get("INVOCATION_ID")
    if (type(record["version"]) is not int or record["version"] != 1
            or record["state"] != "RUNNING" or record["unit"] != config.unit_name
            or not isinstance(invocation_id, str) or not invocation_id
            or record["invocation_id"] != invocation_id or record["generation"] != invocation_id
            or record["control_group"] != config.service_cgroup
            or record["predecessor_outcome"] not in {"BOOTSTRAP_EMPTY", "STOPPED_EMPTY"}
            or type(record["sequence"]) is not int or record["sequence"] < 1):
        raise ContractError("runner lifecycle record does not authorize this manager invocation")
    for field in ("cgroup_device", "cgroup_inode", "lock_device", "lock_inode"):
        if type(record[field]) is not int or record[field] < 0:
            raise ContractError("runner lifecycle record identity is malformed")
    cgroup_path = os.path.realpath(os.path.join("/sys/fs/cgroup", config.service_cgroup.lstrip("/")))
    cgroup_root = os.path.realpath("/sys/fs/cgroup")
    if os.path.commonpath((cgroup_root, cgroup_path)) != cgroup_root:
        raise ContractError("runner lifecycle cgroup escaped the unified hierarchy")
    try:
        cgroup_stat = os.stat(cgroup_path, follow_symlinks=False)
        lock_stat = os.stat(
            os.path.join(config.runtime_dir, "cgroup-admission.lock"), follow_symlinks=False,
        )
    except OSError as exc:
        raise ContractError("runner lifecycle resource identity is unavailable") from exc
    if (cgroup_stat.st_dev != record["cgroup_device"]
            or cgroup_stat.st_ino != record["cgroup_inode"]
            or lock_stat.st_dev != record["lock_device"]
            or lock_stat.st_ino != record["lock_inode"]):
        raise ContractError("runner lifecycle cgroup or lock identity changed")
    return record


def read_service_generation(config: "RunnerServiceConfig") -> str:
    return str(read_service_generation_record(config)["generation"])


def load_runner_service_config(path: str = DEFAULT_CONFIG_PATH) -> "RunnerServiceConfig":
    value = _read_root_controlled_json(path, max_bytes=262144)
    required = {
        "socket_path", "runtime_dir", "supervisor_socket", "generation_record_path", "unit_name",
        "socket_gid", "dispatcher_uid", "dispatcher_gid", "dispatcher_cgroup", "daemon_uid", "daemon_gid",
        "service_cgroup", "audience", "runner_id", "repository_root", "signer_socket",
        "openssl_path", "grant_trust_keys", "worker_uid", "worker_gid",
        "worker_exec_helper_head", "worker_exec_helper_source_sha256", "worker_exec_helper_binary_sha256",
        "worker_exec_helper_path",
    }
    optional = {
        "max_request_bytes", "max_response_bytes", "timeout_sec", "deadline_sec", "max_output_bytes",
    }
    if set(value) - required - optional or not required.issubset(value):
        raise ContractError("runner service configuration fields do not match its schema")
    return RunnerServiceConfig(**value)


@dataclass(frozen=True)
class RunnerServiceConfig:
    socket_path: str
    runtime_dir: str
    supervisor_socket: str
    generation_record_path: str
    unit_name: str
    socket_gid: int
    dispatcher_uid: int
    dispatcher_gid: int
    dispatcher_cgroup: str
    daemon_uid: int
    daemon_gid: int
    service_cgroup: str
    audience: str
    runner_id: str
    repository_root: str
    signer_socket: str
    openssl_path: str
    grant_trust_keys: Mapping[str, str]
    worker_uid: int
    worker_gid: int
    worker_exec_helper_head: str
    worker_exec_helper_source_sha256: str
    worker_exec_helper_binary_sha256: str
    worker_exec_helper_path: str
    max_request_bytes: int = MAX_RUNNER_REQUEST_BYTES
    max_response_bytes: int = MAX_RUNNER_RESPONSE_BYTES
    timeout_sec: int = 600
    deadline_sec: int = 1800
    max_output_bytes: int = 1024 * 1024

    def validate(self) -> None:
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise ContractError("persistent runner service requires POSIX peer credentials")
        if peer_pidfd_socket_option(socket) is None:
            raise ContractError("persistent runner service requires kernel peer pidfd support")
        paths = (self.socket_path, self.runtime_dir, self.supervisor_socket,
                 self.generation_record_path, self.repository_root,
                 self.signer_socket, self.openssl_path)
        if any(not isinstance(path, str) or not os.path.isabs(path) for path in paths):
            raise ContractError("runner service paths must be absolute")
        if os.path.dirname(self.socket_path) != self.runtime_dir:
            raise ContractError("runner socket must be under its fixed runtime directory")
        if (type(self.socket_gid) is not int or type(self.dispatcher_uid) is not int
                or type(self.dispatcher_gid) is not int or type(self.daemon_uid) is not int
                or type(self.daemon_gid) is not int
                or type(self.worker_uid) is not int or type(self.worker_gid) is not int
                or self.daemon_uid < 1 or self.worker_uid < 1 or self.dispatcher_uid < 1
                or self.worker_uid == self.daemon_uid or self.worker_uid == self.dispatcher_uid
                or self.dispatcher_uid == self.daemon_uid
                or self.socket_gid != self.dispatcher_gid or self.worker_gid == self.socket_gid):
            raise ContractError("runner service identities are invalid or not distinct")
        if (not isinstance(self.service_cgroup, str) or not self.service_cgroup.startswith("/")
                or not isinstance(self.dispatcher_cgroup, str) or not self.dispatcher_cgroup.startswith("/")):
            raise ContractError("runner service cgroup paths are invalid")
        if (self.unit_name != "vst-runner.service"
                or self.service_cgroup != "/system.slice/vst-runner.service"
                or ".." in self.dispatcher_cgroup.split("/")
                or os.path.normpath(self.dispatcher_cgroup) != self.dispatcher_cgroup):
            raise ContractError("runner service unit or peer cgroup is not the fixed manager boundary")
        if not isinstance(self.grant_trust_keys, Mapping) or not self.grant_trust_keys:
            raise ContractError("runner service grant trust root is empty")
        for value, name in (
            (self.audience, "audience"), (self.runner_id, "runner_id"),
            (self.unit_name, "unit_name"),
        ):
            if not isinstance(value, str) or not value:
                raise ContractError(f"runner service {name} is invalid")
        for value, name, maximum in (
            (self.max_request_bytes, "max_request_bytes", MAX_RUNNER_REQUEST_BYTES),
            (self.max_response_bytes, "max_response_bytes", MAX_RUNNER_RESPONSE_BYTES),
            (self.timeout_sec, "timeout_sec", 3600),
            (self.deadline_sec, "deadline_sec", 1800),
            (self.max_output_bytes, "max_output_bytes", 16 * 1024 * 1024),
        ):
            if type(value) is not int or value < 1 or value > maximum:
                raise ContractError(f"runner service {name} is outside its bound")
        if ((self.daemon_uid, self.daemon_gid, self.worker_uid, self.worker_gid)
                != (997, 988, 999, 989)):
            raise ContractError("runner worker identity does not match the fixed helper contract")
        if self.dispatcher_gid == self.daemon_gid:
            raise ContractError("runner dispatcher group must be distinct from the daemon group")
        if (not isinstance(self.worker_exec_helper_head, str)
                or not _GIT_HEAD.fullmatch(self.worker_exec_helper_head)
                or not isinstance(self.worker_exec_helper_source_sha256, str)
                or not _SHA256.fullmatch(self.worker_exec_helper_source_sha256)
                or not isinstance(self.worker_exec_helper_binary_sha256, str)
                or not _SHA256.fullmatch(self.worker_exec_helper_binary_sha256)):
            raise ContractError("runner helper build identity is malformed")
        if (not isinstance(self.worker_exec_helper_path, str)
                or self.worker_exec_helper_path != _versioned_worker_exec_helper_path(
                    self.worker_exec_helper_head
                )):
            raise ContractError("runner helper path is not bound to the exact configured build head")
        _verify_worker_exec_helper(self)


def _versioned_worker_exec_helper_path(head: str) -> str:
    if not isinstance(head, str) or not _GIT_HEAD.fullmatch(head):
        raise ContractError("worker helper path requires a full lowercase commit id")
    return _WORKER_EXEC_HELPER_PREFIX + head


def _verify_worker_exec_helper(config: RunnerServiceConfig) -> tuple[int, int, int, int, int, int, str]:
    expected_path = _versioned_worker_exec_helper_path(config.worker_exec_helper_head)
    if config.worker_exec_helper_path != expected_path:
        raise ContractError("worker helper path is not the configured exact-version path")
    parent = os.path.dirname(config.worker_exec_helper_path)
    while True:
        info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("worker helper directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    fd = os.open(config.worker_exec_helper_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_gid != config.daemon_gid
                or stat.S_IMODE(info.st_mode) != 0o4750
                or info.st_nlink != 1):
            raise ContractError("worker helper owner, group, or setuid mode is invalid")
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_uid,
                    info.st_gid, stat.S_IMODE(info.st_mode))
        digest = hashlib.sha256()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.close(fd)
    if digest.hexdigest() != config.worker_exec_helper_binary_sha256:
        raise ContractError("worker helper binary digest does not match the root config")
    try:
        result = subprocess.run(
            [config.worker_exec_helper_path, "--version"], cwd="/",
            env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            close_fds=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError("worker helper build identity cannot be queried") from exc
    expected = (
        f"schema=1 head={config.worker_exec_helper_head} "
        f"source_sha256={config.worker_exec_helper_source_sha256}\n"
    ).encode("ascii")
    if result.returncode != 0 or result.stdout != expected:
        raise ContractError("worker helper build identity does not match the root config")
    try:
        current = os.stat(config.worker_exec_helper_path, follow_symlinks=False)
    except OSError as exc:
        raise ContractError("worker helper path identity changed during verification") from exc
    if (not stat.S_ISREG(current.st_mode)
            or (current.st_dev, current.st_ino, current.st_size, current.st_uid,
                current.st_gid, stat.S_IMODE(current.st_mode)) != identity):
        raise ContractError("worker helper path identity changed during verification")
    return (*identity, digest.hexdigest())


def _recv_exact(conn: socket.socket, count: int) -> bytes:
    result = bytearray()
    while len(result) < count:
        part = conn.recv(count - len(result))
        if not part:
            raise ContractError("runner request frame ended early")
        result.extend(part)
    return bytes(result)


class PersistentRunnerService:
    """Serves signed manifest grants serially from one stable systemd cgroup."""

    def __init__(
        self,
        config: RunnerServiceConfig,
        supervisor: SupervisorClient,
        *,
        service_generation_provider: Callable[[], str],
    ) -> None:
        config.validate()
        if not callable(service_generation_provider):
            raise ContractError("runner service generation provider is unavailable")
        self.config = config
        self.worker_exec_helper_identity = _verify_worker_exec_helper(config)
        self.supervisor = supervisor
        self.service_generation_provider = service_generation_provider
        self._server: socket.socket | None = None
        self._shutdown = threading.Event()

    def shutdown(self) -> None:
        """Stop accepting work and finish the current bounded request before exit."""
        self._shutdown.set()

    def _require_local_boundary(self) -> str:
        if os.geteuid() != self.config.daemon_uid:
            raise ContractError("runner service process has the wrong daemon identity")
        if _read_peer_cgroup(os.getpid()) != self.config.service_cgroup:
            raise ContractError("runner service is outside its manager-owned cgroup")
        generation = self.service_generation_provider()
        record = read_service_generation_record(self.config)
        if generation != record["generation"]:
            raise ContractError("runner generation provider disagrees with its published fence")
        invocation_id = os.environ.get("INVOCATION_ID")
        if not isinstance(generation, str) or not generation or invocation_id != generation:
            raise ContractError("runner service generation does not match the manager invocation")
        lock_path = os.path.join(self.config.runtime_dir, "cgroup-admission.lock")
        try:
            fd = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            raise ContractError("runner admission lock is unavailable") from exc
        try:
            lock_stat = os.fstat(fd)
            if (not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_uid != self.config.daemon_uid
                    or lock_stat.st_dev != record["lock_device"]
                    or lock_stat.st_ino != record["lock_inode"]
                    or lock_stat.st_mode & 0o077):
                raise ContractError("runner admission lock identity changed")
        finally:
            os.close(fd)
        return generation

    def _check_runtime_directory(self) -> None:
        info = os.stat(self.config.runtime_dir, follow_symlinks=False)
        mode = stat.S_IMODE(info.st_mode)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != self.config.daemon_uid
                or info.st_gid != self.config.socket_gid or mode != 0o710):
            raise ContractError("runner runtime directory must be daemon-owned mode 0710")

    def serve_forever(self) -> None:
        self._require_local_boundary()
        self._check_runtime_directory()
        from .runner import _posix_cgroup_process_lock

        with _posix_cgroup_process_lock(time.monotonic() + 30.0):
            self._require_local_boundary()
        self.supervisor.recover()
        if os.path.lexists(self.config.socket_path):
            raise ContractError("runner service socket path already exists")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server = server
        try:
            server.bind(self.config.socket_path)
            os.chown(self.config.socket_path, self.config.daemon_uid, self.config.socket_gid)
            os.chmod(self.config.socket_path, 0o660)
            server.listen(8)
            server.settimeout(0.5)
            while not self._shutdown.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._shutdown.is_set():
                        break
                    raise
                with conn:
                    self._handle(conn)
        finally:
            server.close()
            self._server = None
            try:
                os.unlink(self.config.socket_path)
            except FileNotFoundError:
                pass

    def _handle(self, conn: socket.socket) -> None:
        pidfd = None
        fatal_error: AmbiguousExecutionAuthorityError | None = None
        try:
            conn.settimeout(10.0)
            raw_creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, gid = struct.unpack("3i", raw_creds)
            if uid != self.config.dispatcher_uid or gid != self.config.dispatcher_gid:
                raise ContractError("runner request peer identity is unauthorized")
            pidfd = _peer_pidfd(conn, pid, require=True)
            if (_read_peer_cgroup(pid) != self.config.dispatcher_cgroup
                    or not _pidfd_alive(pidfd)):
                raise ContractError("runner request peer process boundary is unauthorized")
            length = _HEADER.unpack(_recv_exact(conn, _HEADER.size))[0]
            if length < 2 or length > self.config.max_request_bytes:
                raise ContractError("runner request exceeds its size limit")
            request = json.loads(_recv_exact(conn, length))
            if (not isinstance(request, dict) or set(request) != {"version", "grant", "artifact_paths"}
                    or type(request["version"]) is not int or request["version"] != 1
                    or not isinstance(request["grant"], dict)
                    or not isinstance(request["artifact_paths"], list)
                    or any(not isinstance(path, str) for path in request["artifact_paths"])):
                raise ContractError("runner request does not match the manifest-only contract")
            generation = self._require_local_boundary()
            grant = verify_execution_grant(
                request["grant"], self.config.grant_trust_keys,
                audience=self.config.audience, service_generation=generation,
                openssl_path=self.config.openssl_path,
            )
            if not _pidfd_alive(pidfd):
                raise ContractError("runner dispatcher exited before request admission")
            conn.settimeout(None)
            manifest = self.supervisor.manifest(grant["task_id"], grant["manifest_sha256"])
            valid_manifest = validate_task_manifest(manifest)
            if manifest_sha256(valid_manifest) != grant["manifest_sha256"]:
                raise ContractError("Supervisor manifest differs from the signed grant")
            receipt = self._run_grant(grant, valid_manifest, request["artifact_paths"], generation)
            if not _pidfd_alive(pidfd):
                raise ContractError("runner dispatcher exited before result delivery")
            response = {"status": "COMPLETE", "receipt": receipt}
        except AmbiguousExecutionAuthorityError as exc:
            logging.getLogger(__name__).warning(
                "persistent runner authority outcome is ambiguous; refusing and terminating generation"
            )
            fatal_error = exc
            response = {"status": "REFUSED", "error_code": "EXECUTION_REFUSED"}
        except Exception:
            logging.getLogger(__name__).warning("persistent runner request refused", exc_info=True)
            response = {"status": "REFUSED", "error_code": "EXECUTION_REFUSED"}
        finally:
            if pidfd is not None:
                os.close(pidfd)
        encoded = canonical_bytes(response)
        if len(encoded) > self.config.max_response_bytes:
            encoded = canonical_bytes({"status": "REFUSED", "error_code": "RESPONSE_TOO_LARGE"})
        try:
            conn.settimeout(30.0)
            conn.sendall(_HEADER.pack(len(encoded)) + encoded)
        except OSError:
            pass
        if fatal_error is not None:
            raise fatal_error

    def _run_grant(self, grant: dict, manifest: dict, artifact_paths: list[str], generation: str) -> dict:
        from .runner import run_manifest_commands

        deadline_sec = grant.get("execution_deadline_sec")
        if (type(deadline_sec) is not int or deadline_sec < 1
                or deadline_sec > self.config.deadline_sec
                or deadline_sec > self.config.timeout_sec
                or deadline_sec > int(manifest["timeout_sec"])):
            raise ContractError("grant execution deadline exceeds the configured run boundary")
        timeout_sec = deadline_sec

        authority = ExecutionAuthority(
            grant, daemon_uid=self.config.daemon_uid,
            service_generation=generation, trusted_keys=self.config.grant_trust_keys,
            openssl_path=self.config.openssl_path, audience=self.config.audience,
            daemon_boundary_check=lambda: self._require_local_boundary() == generation,
            claim=lambda value: self.supervisor.claim(value),
            claim_status=lambda value: self.supervisor.claim_status(value),
            terminalize_no_execution=lambda value, reason: self.supervisor.terminalize_no_execution(
                value, reason,
            ),
            reserve=lambda value: self.supervisor.reserve(value),
            complete=lambda value, receipt: self.supervisor.complete(value, receipt),
        )
        report: dict = {}
        expected_helper_identity = self.worker_exec_helper_identity

        def verify_worker_helper_before_spawn() -> None:
            if _verify_worker_exec_helper(self.config) != expected_helper_identity:
                raise ContractError("configured worker helper identity changed after service startup")

        previous = self.supervisor.previous_receipt(grant["task_id"], grant["slot"])
        if grant["attempt"] == 1 and previous is not None:
            raise ContractError("first execution attempt unexpectedly has a prior receipt")
        try:
            return run_manifest_commands(
                manifest=manifest, slot=grant["slot"], attempt=grant["attempt"],
                epoch=grant["epoch"], resolved_model=grant["resolved_model"],
                invocation_id=grant["invocation_id"], runner_id=grant["runner_id"],
                signer_socket=self.config.signer_socket, cwd=self.config.repository_root,
                worker_uid=self.config.worker_uid, worker_gid=self.config.worker_gid,
                worker_exec_helper_head=self.config.worker_exec_helper_head,
                worker_exec_helper_path=self.config.worker_exec_helper_path,
                verify_worker_exec_helper=verify_worker_helper_before_spawn,
                run_id=grant["run_id"], model_provenance_sha256=grant["model_provenance_sha256"],
                execution_authority=authority,
                created_at=datetime.now(timezone.utc).isoformat(),
                prev_receipt_sha256=previous, artifact_paths=artifact_paths,
                timeout_sec=timeout_sec, deadline_sec=deadline_sec,
                max_output_bytes=self.config.max_output_bytes, report=report,
            )
        except Exception as exc:
            if authority.reservation_confirmed and not authority.completion_confirmed:
                raise AmbiguousExecutionAuthorityError(
                    "reserved execution failed before durable COMPLETE; terminating service generation"
                ) from exc
            if authority.claim_confirmed and not authority.no_execution_confirmed:
                try:
                    authority.terminalize_no_execution("RUNNER_PRESPAWN_FAILURE")
                except Exception as terminalize_exc:
                    raise AmbiguousExecutionAuthorityError(
                        "pre-spawn refusal could not be durably terminalized; terminating service generation"
                    ) from terminalize_exc
            raise


def dispatch_manifest_run(
    socket_path: str, grant: dict, *, artifact_paths: list[str] | None = None,
    timeout_sec: float = 1900.0,
) -> dict:
    """Send one signed grant to the persistent daemon and return its receipt."""
    if os.name != "posix" or not hasattr(socket, "AF_UNIX"):
        raise ContractError("persistent runner dispatch requires a POSIX Unix socket")
    if not isinstance(socket_path, str) or not os.path.isabs(socket_path):
        raise ContractError("runner service socket path must be absolute")
    if (isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float))
            or timeout_sec <= 0):
        raise ContractError("runner client timeout must be positive")
    paths = [] if artifact_paths is None else artifact_paths
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise ContractError("runner artifact paths must be strings")
    payload = canonical_bytes({"version": 1, "grant": grant, "artifact_paths": paths})
    if len(payload) > MAX_RUNNER_REQUEST_BYTES:
        raise ContractError("runner request exceeds its size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout_sec)
        client.connect(socket_path)
        client.sendall(_HEADER.pack(len(payload)) + payload)
        length = _HEADER.unpack(_recv_exact(client, _HEADER.size))[0]
        if length < 2 or length > MAX_RUNNER_RESPONSE_BYTES:
            raise ContractError("runner response exceeds its size limit")
        response = json.loads(_recv_exact(client, length))
    if not isinstance(response, dict) or response.get("status") != "COMPLETE":
        raise ContractError("persistent runner refused execution or returned an invalid response")
    receipt = response.get("receipt")
    if not isinstance(receipt, dict):
        raise ContractError("persistent runner response lacks a receipt")
    validated = validate_receipt(receipt)
    bound_fields = (
        "task_id", "manifest_sha256", "slot", "attempt", "epoch", "runner_id", "invocation_id",
    )
    if any(validated[field] != grant[field] for field in bound_fields):
        raise ContractError("persistent runner receipt does not match the dispatched grant")
    return validated


def dispatch_authorized_manifest_run(
    *, supervisor_socket: str, runner_socket: str,
    request_id: str, timeout_sec: float = 1900.0,
) -> dict:
    """Forward one previously accepted intent using its Supervisor-issued grant.

    The dispatcher cannot choose task, slot, model, or artifact paths here.
    Supervisor resolves those values from the durable intent, Store, and
    root-owned model provenance configuration.
    """
    if not isinstance(request_id, str) or not request_id:
        raise ContractError("dispatch request id must be non-empty")
    supervisor = SupervisorClient(supervisor_socket)
    grant = supervisor.issue_dispatch_grant(request_id)
    deadline = grant.get("execution_deadline_sec")
    if type(deadline) is not int or deadline < 1:
        raise ContractError("Supervisor returned a grant with an invalid execution deadline")
    if (isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float))
            or timeout_sec <= 0):
        raise ContractError("dispatch timeout must be positive")
    bounded_timeout = min(MAX_DISPATCH_TIMEOUT_SEC, float(timeout_sec), float(deadline + 120))
    return dispatch_manifest_run(
        runner_socket, grant, timeout_sec=bounded_timeout,
    )


def main() -> None:
    if os.name == "nt":
        if sys.argv[1:] not in (["--windows-scm", "runner"], ["--windows-scm", "worker"]):
            raise ContractError(
                "Windows Runner host requires --windows-scm runner or --windows-scm worker"
            )
        from .windows_service_host import (
            WindowsRuntimeConfig, assert_path_acl, read_runtime_json,
            run_scm_service, service_name_for_role,
        )
        from .supervisor_service import WindowsSupervisorClient
        from .execution_grant import verify_execution_grant

        runtime = WindowsRuntimeConfig.load()
        security = read_runtime_json(runtime, "supervisor.json")
        trust_keys = security.get("execution_grant_trust_keys")
        openssl_path = security.get("openssl_path")
        audience = security.get("execution_grant_audience")
        if (not isinstance(trust_keys, dict) or not trust_keys
                or not isinstance(openssl_path, str) or not os.path.isabs(openssl_path)
                or not isinstance(audience, str) or not audience):
            raise ContractError("Windows execution grant trust configuration is incomplete")
        service_sids = {item.service_sid for item in runtime.role_identities.values()}
        for key_path in trust_keys.values():
            if not isinstance(key_path, str) or not os.path.isabs(key_path):
                raise ContractError("Windows execution grant trust key path is invalid")
            assert_path_acl(
                key_path, allowed_sids={"S-1-5-18", "S-1-5-32-544", *service_sids},
                writable_sids={"S-1-5-18", "S-1-5-32-544"},
            )
        runner_config = read_runtime_json(runtime, "runner.json")
        if set(runner_config) != {"repository_root", "runner_id"}:
            raise ContractError("Windows Runner config fields do not match its schema")
        repository_root, runner_id = runner_config["repository_root"], runner_config["runner_id"]
        if (not isinstance(repository_root, str) or not os.path.isabs(repository_root)
                or os.path.normcase(os.path.realpath(repository_root)) != os.path.normcase(repository_root)
                or not isinstance(runner_id, str) or runner_id != "VSTRunner"):
            raise ContractError("Windows Runner repository or identity is invalid")

        def verify_grant(grant: dict, *, expected_generation: str | None = None) -> dict:
            generation = expected_generation
            if generation is None:
                generation = supervisor.generation()
            return verify_execution_grant(
                grant, trust_keys, audience=audience,
                service_generation=generation, openssl_path=openssl_path,
            )

        if sys.argv[2] == "worker":
            identity = runtime.identity("worker")
            supervisor = WindowsSupervisorClient(
                runtime.pipe_name("supervisor_worker"),
                expected_server_sid=runtime.identity("supervisor").service_sid,
                expected_server_service=runtime.identity("supervisor").service_name,
                timeout_sec=5.0,
            )
            config = WindowsWorkerServiceConfig.from_runtime(
                runtime, repository_root=repository_root,
            )
            def make_worker() -> WindowsWorkerService:
                def verify_worker_grant(grant: dict) -> dict:
                    generation = grant.get("service_generation")
                    if not isinstance(generation, str) or not generation:
                        raise ContractError("Windows Worker grant generation is missing")
                    return verify_grant(grant, expected_generation=generation)

                return WindowsWorkerService(
                    config, verify_grant=verify_worker_grant,
                    reserved_check=supervisor.worker_reservation,
                )
            run_scm_service(service_name_for_role("worker"), make_worker)
            return

        identity = runtime.identity("runner")
        supervisor = WindowsSupervisorClient(
            runtime.pipe_name("supervisor_runner"),
            expected_server_sid=runtime.identity("supervisor").service_sid,
            expected_server_service=runtime.identity("supervisor").service_name,
            timeout_sec=5.0,
        )
        worker_identity = runtime.identity("worker")
        worker = WindowsWorkerClient(
            runtime.pipe_name("runner_worker"), worker_sid=worker_identity.service_sid,
            worker_service=worker_identity.service_name, timeout_sec=MAX_DISPATCH_TIMEOUT_SEC,
        )
        target = lambda: WindowsRunnerService(
            pipe_name=runtime.pipe_name("runner_dispatch"),
            runner_sid=identity.service_sid,
            dispatcher_sid=runtime.identity("dispatcher").service_sid,
            supervisor=supervisor, worker_client=worker,
            signer_pipe_name=runtime.pipe_name("runner_signer"),
            signer_sid=runtime.identity("signer").service_sid,
            repository_root=repository_root, runner_id=runner_id,
            audience=audience, grant_verifier=verify_grant,
            service_identity=identity,
        )
        run_scm_service(service_name_for_role("runner"), target)
        return
    config_path = DEFAULT_CONFIG_PATH
    if len(sys.argv) == 2:
        config_path = sys.argv[1]
    elif len(sys.argv) > 2:
        raise ContractError("runner service accepts only one fixed config path")
    config = load_runner_service_config(config_path)
    supervisor = SupervisorClient(config.supervisor_socket)
    service = PersistentRunnerService(
        config, supervisor,
        service_generation_provider=lambda: read_service_generation(config),
    )
    signal.signal(signal.SIGTERM, lambda _signum, _frame: service.shutdown())
    signal.signal(signal.SIGINT, lambda _signum, _frame: service.shutdown())
    service.serve_forever()


if __name__ == "__main__":
    main()
