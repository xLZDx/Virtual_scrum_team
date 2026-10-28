"""Socket-activated signed-instruction relay for the S2 root Supervisor."""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import socket
import stat
import struct
import sys
import threading
from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import ContractError, canonical_bytes
from .dispatch_instruction import (
    DISPATCH_INSTRUCTION_PURPOSE, DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH,
)
from .dispatch_owner_client import DispatchOutcomeUnknown, DispatchOwnerClient
from .supervisor_service import SupervisorClient

DEFAULT_CONFIG_PATH = "/etc/vst-runner/dispatch-owner-service.json"
TRUST_REGISTRY_PATH = DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH
SUPERVISOR_SOCKET_PATH = "/run/vst-supervisor/supervisor.sock"
OWNER_SOCKET_PATH = "/run/vst-supervisor/dispatch-owner.sock"
DISPATCH_OWNER_ADMISSION_LATCH_PATH = "/etc/vst-runner/dispatch-owner-admission-blocked.json"
OWNER_PRINCIPAL = "Codex"
OPENSSL_PATH = "/usr/bin/openssl"
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
REQUEST_TIMEOUT_SEC = 10.0
OUTCOME_UNKNOWN_EXIT = 75
_HEADER = struct.Struct("!I")
_LOGGER = logging.getLogger("vst.dispatch_owner")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("dispatch-owner JSON contains a duplicate field")
        result[key] = value
    return result


def _read_root_json(path: str, *, expected_mode: int, expected_gid: int,
                    max_bytes: int) -> dict[str, Any]:
    if os.name != "posix" or not os.path.isabs(path):
        raise ContractError("dispatch-owner trusted file path is invalid")
    parent = os.path.dirname(path)
    while True:
        try:
            info = os.stat(parent, follow_symlinks=False)
        except OSError as exc:
            raise ContractError("dispatch-owner trusted-file directory is unavailable") from exc
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("dispatch-owner trusted-file directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContractError("dispatch-owner trusted file is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_gid != expected_gid
                or stat.S_IMODE(info.st_mode) != expected_mode
                or info.st_size > max_bytes):
            raise ContractError("dispatch-owner trusted-file owner, mode, or size is invalid")
        raw = bytearray()
        while len(raw) <= max_bytes:
            chunk = os.read(fd, min(65536, max_bytes + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > max_bytes:
            raise ContractError("dispatch-owner trusted file exceeds its size limit")
    finally:
        os.close(fd)
    try:
        value = json.loads(raw, object_pairs_hook=_unique_json_object)
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise ContractError("dispatch-owner trusted file is malformed JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("dispatch-owner trusted file must be a JSON object")
    return value


def load_dispatch_owner_config(path: str = DEFAULT_CONFIG_PATH) -> "DispatchOwnerServiceConfig":
    if os.path.lexists(DISPATCH_OWNER_ADMISSION_LATCH_PATH):
        raise ContractError("dispatch-owner admission is blocked pending reconciliation")
    if os.geteuid() == 0 or os.getgid() < 1:
        raise ContractError("dispatch-owner service must run under its dedicated unprivileged identity")
    try:
        with open("/proc/self/cgroup", encoding="ascii") as stream:
            rows = [line.rstrip("\n").split(":", 2) for line in stream]
    except OSError as exc:
        raise ContractError("dispatch-owner service cgroup is unavailable") from exc
    cgroup = next((row[2] for row in rows if len(row) == 3 and row[:2] == ["0", ""]), None)
    if cgroup != "/system.slice/vst-dispatch-owner.service":
        raise ContractError("dispatch-owner service is outside its fixed systemd cgroup")
    config = _read_root_json(
        path, expected_mode=0o640, expected_gid=os.getgid(), max_bytes=65536,
    )
    if set(config) != {"principal", "openssl_path"}:
        raise ContractError("dispatch-owner config fields do not match its fixed schema")
    if config != {"principal": OWNER_PRINCIPAL, "openssl_path": OPENSSL_PATH}:
        raise ContractError("dispatch-owner config does not match its fixed trust boundary")
    registry = _read_root_json(
        TRUST_REGISTRY_PATH, expected_mode=0o644, expected_gid=0, max_bytes=65536,
    )
    _validate_trust_registry(registry)
    return DispatchOwnerServiceConfig(
        principal=config["principal"], openssl_path=config["openssl_path"],
        trust_registry=registry,
    )


def _validate_trust_registry(registry: Mapping[str, Any]) -> None:
    if not registry:
        raise ContractError("dispatch instruction public trust registry is empty")
    for key_id, entry in registry.items():
        if (not isinstance(key_id, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key_id)
                or not isinstance(entry, dict)
                or set(entry) != {"principal", "purpose", "public_key_path"}
                or entry.get("principal") != OWNER_PRINCIPAL
                or entry.get("purpose") != DISPATCH_INSTRUCTION_PURPOSE
                or not isinstance(entry.get("public_key_path"), str)
                or not os.path.isabs(entry["public_key_path"])):
            raise ContractError("dispatch instruction public trust registry is malformed")
        _validate_root_public_key(entry["public_key_path"])


def _validate_root_public_key(path: str) -> None:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not os.path.isabs(path):
        raise ContractError("dispatch instruction public key path is invalid")
    parent = os.path.dirname(os.path.abspath(path))
    while True:
        try:
            info = os.stat(parent, follow_symlinks=False)
        except OSError as exc:
            raise ContractError("dispatch instruction public-key directory is unavailable") from exc
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("dispatch instruction public-key directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContractError("dispatch instruction public key is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != 0o644 or info.st_size > 65536):
            raise ContractError("dispatch instruction public key owner, mode, or size is invalid")
    finally:
        os.close(fd)


@dataclass(frozen=True)
class DispatchOwnerServiceConfig:
    principal: str
    openssl_path: str
    trust_registry: Mapping[str, Mapping[str, str]]


class DispatchOwnerService:
    """Relay signed instructions; task assignment authority remains in Store/Supervisor."""

    def __init__(self, config: DispatchOwnerServiceConfig,
                 supervisor: Any | None = None) -> None:
        if config.principal != OWNER_PRINCIPAL or config.openssl_path != OPENSSL_PATH:
            raise ContractError("dispatch-owner service configuration is not fixed")
        self.client = DispatchOwnerClient(
            principal=config.principal,
            trust_registry=config.trust_registry,
            openssl_path=config.openssl_path,
            transport=(supervisor if supervisor is not None else SupervisorClient(
                SUPERVISOR_SOCKET_PATH, timeout_sec=REQUEST_TIMEOUT_SEC,
            )),
        )
        self._shutdown = threading.Event()
        self._outcome_unknown = False

    def shutdown(self) -> None:
        self._shutdown.set()

    def serve_forever(self, listener: socket.socket) -> None:
        if (listener.family != socket.AF_UNIX
                or listener.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_STREAM
                or listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) != 1
                or listener.getsockname() != OWNER_SOCKET_PATH):
            raise ContractError("dispatch-owner activation socket is not the fixed local listener")
        listener.settimeout(0.5)
        while not self._shutdown.is_set():
            try:
                conn, _ = listener.accept()
            except socket.timeout:
                continue
            with conn:
                if self._handle(conn):
                    self._outcome_unknown = True
                    self._shutdown.set()
                    return

    def _handle(self, conn: socket.socket) -> bool:
        conn.settimeout(REQUEST_TIMEOUT_SEC)
        outcome_unknown = False
        accepted_result: dict | None = None
        try:
            header = _recv_exact(conn, _HEADER.size)
            length = _HEADER.unpack(header)[0]
            if length < 2 or length > MAX_REQUEST_BYTES:
                raise ContractError("dispatch-owner request size is invalid")
            payload = _recv_exact(conn, length)
            if conn.recv(1) != b"":
                raise ContractError("dispatch-owner connection contains trailing request bytes")
            request = json.loads(payload, object_pairs_hook=_unique_json_object)
            if (not isinstance(request, dict) or set(request) != {"instruction"}
                    or canonical_bytes(request) != payload):
                raise ContractError("dispatch-owner request does not match the exact envelope")
            try:
                result = self.client.submit(request["instruction"])
            except DispatchOutcomeUnknown as exc:
                _LOGGER.error("dispatch-owner Supervisor outcome is unknown (%s)", type(exc).__name__)
                outcome_unknown = True
                response = {"ok": False, "error": "reconciliation_required"}
            else:
                accepted_result = result
                response = {"ok": True, "result": result}
        except Exception as exc:
            _LOGGER.warning("dispatch-owner request refused (%s)", type(exc).__name__)
            response = {"ok": False, "error": "refused"}
        encoded = canonical_bytes(response)
        if len(encoded) > MAX_RESPONSE_BYTES:
            encoded = canonical_bytes({"ok": False, "error": "response_too_large"})
            if accepted_result is not None:
                outcome_unknown = True
        try:
            conn.sendall(_HEADER.pack(len(encoded)) + encoded)
        except OSError:
            if accepted_result is not None:
                outcome_unknown = True
            return outcome_unknown
        if accepted_result is not None and not outcome_unknown:
            try:
                self.client.acknowledge_forwarded(accepted_result)
            except DispatchOutcomeUnknown as exc:
                _LOGGER.error("dispatch-owner outcome acknowledgement is unknown (%s)", type(exc).__name__)
                outcome_unknown = True
        return outcome_unknown


def _recv_exact(conn: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        part = conn.recv(count - len(chunks))
        if not part:
            raise ContractError("dispatch-owner request frame ended early")
        chunks.extend(part)
    return bytes(chunks)


def _systemd_listener() -> socket.socket:
    if (os.environ.get("LISTEN_PID") != str(os.getpid())
            or os.environ.get("LISTEN_FDS") != "1"
            or os.environ.get("LISTEN_FDNAMES") != "dispatch-owner"):
        raise ContractError("dispatch-owner requires its exact systemd socket activation descriptor")
    for key in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES"):
        os.environ.pop(key, None)
    try:
        listener = socket.socket(fileno=3)
    except OSError as exc:
        raise ContractError("dispatch-owner activation descriptor is unavailable") from exc
    listener.set_inheritable(False)
    return listener


def main() -> None:
    if os.name != "posix" or not hasattr(socket, "AF_UNIX"):
        raise ContractError("dispatch-owner requires POSIX Unix sockets")
    if len(sys.argv) != 1:
        raise ContractError("dispatch-owner does not accept command-line configuration")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    service = DispatchOwnerService(load_dispatch_owner_config())
    signal.signal(signal.SIGTERM, lambda _signum, _frame: service.shutdown())
    signal.signal(signal.SIGINT, lambda _signum, _frame: service.shutdown())
    listener = _systemd_listener()
    try:
        service.serve_forever(listener)
    finally:
        listener.close()
    if service._outcome_unknown:
        raise SystemExit(OUTCOME_UNKNOWN_EXIT)


if __name__ == "__main__":
    main()
