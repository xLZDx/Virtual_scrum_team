"""Transport-only client for submitting an already signed dispatch instruction."""

from __future__ import annotations

import json
import os
import select
import socket
import stat
import struct
from typing import Any

from .contracts import ContractError, canonical_bytes
from .dispatch_instruction import validate_dispatch_instruction
from .dispatch_owner_client import DispatchOutcomeUnknown

OWNER_SOCKET_PATH = "/run/vst-supervisor/dispatch-owner.sock"
REQUEST_TIMEOUT_SEC = 10.0
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
_HEADER = struct.Struct("!I")


class DispatchOwnerSocketClient:
    """Forward one exact signed envelope; never select, sign, or retry work."""

    def __init__(self, *, expected_principal: str, expected_socket_gid: int,
                 socket_path: str = OWNER_SOCKET_PATH,
                 timeout_sec: float = REQUEST_TIMEOUT_SEC) -> None:
        if (os.name != "posix" or not hasattr(socket, "AF_UNIX")
                or not hasattr(socket, "SO_PEERCRED")
                or getattr(socket, "SO_PEERPIDFD", None) is None):
            raise ContractError("dispatch-owner transport requires POSIX Unix-socket support")
        if socket_path != OWNER_SOCKET_PATH:
            raise ContractError("dispatch-owner socket path is fixed")
        if not isinstance(expected_principal, str) or not expected_principal.strip():
            raise ContractError("dispatch-owner principal is invalid")
        if type(expected_socket_gid) is not int or expected_socket_gid < 0:
            raise ContractError("dispatch-owner socket group is invalid")
        if (isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float))
                or not 0.1 <= timeout_sec <= 30.0):
            raise ContractError("dispatch-owner socket timeout is outside its allowed range")
        self.socket_path = socket_path
        self.expected_principal = expected_principal
        self.expected_socket_gid = expected_socket_gid
        self.timeout_sec = float(timeout_sec)

    def submit_signed_instruction(self, instruction: object) -> dict[str, Any]:
        envelope = validate_dispatch_instruction(instruction)
        request = canonical_bytes({"instruction": envelope})
        if len(request) > MAX_REQUEST_BYTES:
            raise ContractError("dispatch-owner request exceeds its size limit")
        self._validate_socket_path()

        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.timeout_sec)
        pidfd: int | None = None
        try:
            try:
                client.connect(self.socket_path)
                raw_creds = client.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"),
                )
                if not isinstance(raw_creds, bytes) or len(raw_creds) != struct.calcsize("3i"):
                    raise ContractError("kernel returned malformed dispatch-owner peer credentials")
                peer_pid, peer_uid, _peer_gid = struct.unpack("3i", raw_creds)
                if peer_pid != 1 or peer_uid != 0:
                    raise ContractError("dispatch-owner socket peer is not systemd PID 1")
                pidfd = self._peer_pidfd(client, peer_pid)
            except OSError as exc:
                raise ContractError("dispatch-owner socket endpoint is unavailable or unauthenticated") from exc
            except ContractError:
                raise

            try:
                client.sendall(_HEADER.pack(len(request)) + request)
                client.shutdown(socket.SHUT_WR)
                response = self._read_response(client)
            except (OSError, ContractError) as exc:
                raise DispatchOutcomeUnknown(
                    "dispatch-owner outcome is unknown; do not retry the submission"
                ) from exc
            if not self._peer_is_alive(pidfd):
                raise DispatchOutcomeUnknown(
                    "dispatch-owner systemd socket peer exited during submission"
                )
        finally:
            client.close()
            if pidfd is not None:
                os.close(pidfd)

        if response == {"ok": False, "error": "refused"}:
            raise ContractError("dispatch-owner refused the signed instruction")
        if response == {"ok": False, "error": "reconciliation_required"}:
            raise DispatchOutcomeUnknown(
                "dispatch-owner requires reconciliation; do not retry the submission"
            )
        if (not isinstance(response, dict) or set(response) != {"ok", "result"}
                or response["ok"] is not True or not isinstance(response["result"], dict)):
            raise DispatchOutcomeUnknown("dispatch-owner returned an unrecognized outcome")

        result = response["result"]
        if (result.get("principal") != self.expected_principal
                or result.get("instruction") != envelope
                or result.get("key_id") != envelope["key_id"]
                or any(result.get(field) != envelope[field] for field in (
                    "task_id", "slot", "attempt", "epoch", "run_id", "request_id",
                ))):
            raise DispatchOutcomeUnknown("dispatch-owner result does not match the submitted envelope")
        return result

    def _validate_socket_path(self) -> None:
        try:
            parent = os.lstat(os.path.dirname(self.socket_path))
            endpoint = os.lstat(self.socket_path)
        except OSError as exc:
            raise ContractError("dispatch-owner socket path is unavailable") from exc
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0
                or parent.st_gid != self.expected_socket_gid
                or stat.S_IMODE(parent.st_mode) != 0o710):
            raise ContractError("dispatch-owner socket directory identity is unauthorized")
        if (not stat.S_ISSOCK(endpoint.st_mode) or endpoint.st_uid != 0
                or endpoint.st_gid != self.expected_socket_gid
                or stat.S_IMODE(endpoint.st_mode) != 0o660):
            raise ContractError("dispatch-owner socket inode identity is unauthorized")

    @staticmethod
    def _peer_pidfd(client: socket.socket, peer_pid: int) -> int:
        option = getattr(socket, "SO_PEERPIDFD", None)
        if option is None:
            raise ContractError("kernel peer pidfd support is unavailable")
        raw = client.getsockopt(socket.SOL_SOCKET, option, struct.calcsize("i"))
        if not isinstance(raw, bytes) or len(raw) != struct.calcsize("i"):
            raise ContractError("kernel did not return a peer pidfd")
        pidfd = struct.unpack("i", raw)[0]
        if pidfd < 0:
            raise ContractError("kernel returned an invalid peer pidfd")
        try:
            os.set_inheritable(pidfd, False)
            if not DispatchOwnerSocketClient._peer_is_alive(pidfd):
                raise ContractError("dispatch-owner systemd socket peer has exited")
        except Exception:
            os.close(pidfd)
            raise
        return pidfd

    @staticmethod
    def _peer_is_alive(pidfd: int | None) -> bool:
        if pidfd is None:
            return False
        poller = select.poll()
        poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        return not poller.poll(0)

    @staticmethod
    def _read_response(client: socket.socket) -> dict[str, Any]:
        header = DispatchOwnerSocketClient._recv_exact(client, _HEADER.size)
        length = _HEADER.unpack(header)[0]
        if length < 2 or length > MAX_RESPONSE_BYTES:
            raise ContractError("dispatch-owner response size is invalid")
        payload = DispatchOwnerSocketClient._recv_exact(client, length)
        if client.recv(1) != b"":
            raise ContractError("dispatch-owner response contains trailing bytes")
        try:
            response = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError("dispatch-owner response is malformed JSON") from exc
        if not isinstance(response, dict) or canonical_bytes(response) != payload:
            raise ContractError("dispatch-owner response is not canonical JSON")
        return response

    @staticmethod
    def _recv_exact(client: socket.socket, size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            chunk = client.recv(size - len(result))
            if not chunk:
                raise ContractError("dispatch-owner response ended early")
            result.extend(chunk)
        return bytes(result)
