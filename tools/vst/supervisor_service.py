"""Narrow, pidfd-pinned local RPC between the Supervisor and runner services."""

from __future__ import annotations

import json
import hashlib
import os
import select
import secrets
import signal
import socket
import stat
import struct
import threading
import sys
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from .peer_pidfd import peer_pidfd_socket_option
from .contracts import ContractError, canonical_bytes
from .dispatch_instruction import DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH
from .store import StoreError

MAX_SUPERVISOR_MESSAGE_BYTES = 1024 * 1024
_HEADER = struct.Struct("!I")


class SupervisorRPCError(RuntimeError):
    """A bounded refusal from the trusted Supervisor RPC endpoint."""

    def __init__(self, message: str, *, kind: str | None = None):
        super().__init__(message)
        self.kind = kind


def _notify_systemd_ready() -> None:
    """Tell a Type=notify Supervisor unit it is ready only after its socket listens."""
    notify_path = os.environ.get("NOTIFY_SOCKET")
    if not notify_path:
        return
    if len(notify_path) > 107 or not (notify_path.startswith("/") or notify_path.startswith("@")):
        raise ContractError("systemd notification socket path is malformed")
    address = "\0" + notify_path[1:] if notify_path.startswith("@") else notify_path
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.settimeout(2.0)
        client.sendto(b"READY=1\nSTATUS=Runtime observation accepted; Supervisor API is listening", address)
    except OSError as exc:
        raise ContractError("systemd readiness notification failed") from exc
    finally:
        client.close()


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("Supervisor RPC JSON contains a duplicate object key")
        result[key] = value
    return result


@dataclass(frozen=True)
class SupervisorPeer:
    role: str
    uid: int
    gid: int
    cgroup: str
    operations: frozenset[str]
    principal: str | None = None


def _recv_exact(conn: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        part = conn.recv(count - len(chunks))
        if not part:
            raise ContractError("Supervisor RPC frame ended early")
        chunks.extend(part)
    return bytes(chunks)


def _peer_pidfd(conn: socket.socket, pid: int, *, require: bool) -> int | None:
    option = peer_pidfd_socket_option(socket)
    if option is None:
        if require:
            raise ContractError("kernel peer pidfd support is unavailable")
        return None
    raw = conn.getsockopt(socket.SOL_SOCKET, option, struct.calcsize("i"))
    if not isinstance(raw, bytes) or len(raw) != struct.calcsize("i"):
        raise ContractError("kernel did not return a peer pidfd")
    pidfd = struct.unpack("i", raw)[0]
    if pidfd < 0:
        raise ContractError("kernel returned an invalid peer pidfd")
    os.set_inheritable(pidfd, False)
    poller = select.poll()
    poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    if poller.poll(0):
        os.close(pidfd)
        raise ContractError("Supervisor RPC peer has exited")
    return pidfd


def _pidfd_alive(pidfd: int | None) -> bool:
    if pidfd is None:
        return False
    poller = select.poll()
    poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
    return not poller.poll(0)


def _read_peer_cgroup(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cgroup", encoding="ascii") as stream:
            rows = [line.rstrip("\n").split(":", 2) for line in stream]
    except OSError as exc:
        raise ContractError("Supervisor RPC peer cgroup is unavailable") from exc
    path = next((row[2] for row in rows if len(row) == 3 and row[:2] == ["0", ""]), None)
    if not path or ".." in path.split("/"):
        raise ContractError("Supervisor RPC peer lacks a unified cgroup")
    return os.path.normpath(path)


class AuthenticatedSupervisorAPI:
    """Root-owned API; callers receive narrow operations, never Store credentials."""

    def __init__(
        self, supervisor: Any, socket_path: str, *, peers: tuple[SupervisorPeer, ...],
        socket_gid: int, require_peer_pidfd: bool = True,
    ) -> None:
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise ContractError("Supervisor RPC requires POSIX peer credentials")
        if require_peer_pidfd and peer_pidfd_socket_option(socket) is None:
            raise ContractError("Supervisor RPC requires kernel peer pidfd support")
        if os.geteuid() != 0:
            raise ContractError("Supervisor RPC server must run as root")
        if not os.path.isabs(socket_path):
            raise ContractError("Supervisor RPC socket path must be absolute")
        if type(socket_gid) is not int or socket_gid < 0:
            raise ContractError("Supervisor RPC socket group is invalid")
        if not peers or len({peer.role for peer in peers}) != len(peers):
            raise ContractError("Supervisor RPC peer policy is empty or duplicated")
        if len({(peer.uid, peer.gid) for peer in peers}) != len(peers):
            raise ContractError("Supervisor RPC peer credentials must map to one role")
        self.supervisor = supervisor
        self.socket_path = socket_path
        self.peers = {(peer.uid, peer.gid): peer for peer in peers}
        self.socket_gid = socket_gid
        self.require_peer_pidfd = require_peer_pidfd
        self._server: socket.socket | None = None
        self._shutdown = threading.Event()

    def shutdown(self) -> None:
        """Stop accepting new RPCs and let the active request finish."""
        self._shutdown.set()

    def serve_forever(self) -> None:
        parent = os.path.dirname(self.socket_path)
        parent_stat = os.stat(parent, follow_symlinks=False)
        if (not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != 0
                or parent_stat.st_gid != self.socket_gid
                or stat.S_IMODE(parent_stat.st_mode) != 0o710):
            raise ContractError("Supervisor RPC directory must be root-owned mode 0710")
        if os.path.lexists(self.socket_path):
            raise ContractError("Supervisor RPC socket path already exists")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server = server
        try:
            server.bind(self.socket_path)
            os.chown(self.socket_path, 0, self.socket_gid)
            os.chmod(self.socket_path, 0o660)
            server.listen(8)
            _notify_systemd_ready()
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
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass

    def _handle(self, conn: socket.socket) -> None:
        pidfd = None
        try:
            conn.settimeout(10.0)
            raw_creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, gid = struct.unpack("3i", raw_creds)
            peer = self.peers.get((uid, gid))
            if peer is None:
                raise ContractError("Supervisor RPC peer identity is not authorized")
            pidfd = _peer_pidfd(conn, pid, require=self.require_peer_pidfd)
            if _read_peer_cgroup(pid) != peer.cgroup or not _pidfd_alive(pidfd):
                raise ContractError("Supervisor RPC peer process boundary is not authorized")
            header = _recv_exact(conn, _HEADER.size)
            length = _HEADER.unpack(header)[0]
            if length < 2 or length > MAX_SUPERVISOR_MESSAGE_BYTES:
                raise ContractError("Supervisor RPC request size is invalid")
            message = json.loads(
                _recv_exact(conn, length), object_pairs_hook=_unique_json_object,
            )
            if (not isinstance(message, dict) or set(message) != {"operation", "body"}
                    or not isinstance(message["operation"], str)
                    or message["operation"] not in peer.operations
                    or not isinstance(message["body"], dict)):
                raise ContractError("Supervisor RPC operation is not authorized")
            result = self._dispatch(message["operation"], message["body"], peer)
            if not _pidfd_alive(pidfd):
                raise ContractError("Supervisor RPC peer exited during request")
            response = {"ok": True, "result": result}
        except Exception as exc:
            kind = exc.kind if isinstance(exc, StoreError) else "refused"
            response = {"ok": False, "error": str(kind)[:40]}
        finally:
            if pidfd is not None:
                os.close(pidfd)
        encoded = canonical_bytes(response)
        if len(encoded) > MAX_SUPERVISOR_MESSAGE_BYTES:
            encoded = canonical_bytes({"ok": False, "error": "response_too_large"})
        try:
            conn.sendall(_HEADER.pack(len(encoded)) + encoded)
        except OSError:
            return

    def _dispatch(self, operation: str, body: dict, peer: SupervisorPeer | None = None) -> Any:
        if operation == "bootstrap_assignment":
            from .assignment_basis import validate_bootstrap_request
            if (peer is None or peer.role != "assignment_bootstrap"
                    or peer.operations != frozenset({"bootstrap_assignment"})):
                raise ContractError("assignment-bootstrap request is not authorized")
            policy = self.supervisor.assignment_policy
            if policy is None:
                raise ContractError("assignment-bootstrap policy is not provisioned")
            validate_bootstrap_request(body, policy=policy)
            return self.supervisor.bootstrap_assignment(body, peer=peer)
        if operation == "assignment_basis":
            from .assignment_basis import validate_request
            if (peer is None or peer.role != "delegated_issuer"
                    or "assignment_basis" not in peer.operations):
                raise ContractError("assignment-basis request is not authorized")
            operation_id = validate_request(body)
            return self.supervisor.assignment_basis(assignment_operation_id=operation_id)
        if operation == "issue_root_dispatch_instruction":
            from .assignment_basis import REQUEST_SCHEMA, validate_request
            if (peer is None or peer.role != "delegated_issuer"
                    or "issue_root_dispatch_instruction" not in peer.operations
                    or set(body) != {"assignment_operation_id"}):
                raise ContractError("root dispatch issuance request is not authorized")
            operation_id = validate_request({
                "schema": REQUEST_SCHEMA,
                "assignment_operation_id": body["assignment_operation_id"],
            })
            return self.supervisor.issue_root_dispatch_instruction(
                assignment_operation_id=operation_id,
            )
        if operation == "submit_dispatch_intent":
            if (peer is None or peer.role != "dispatch_owner" or not peer.principal
                    or set(body) != {"instruction"}):
                raise ContractError("dispatch intent request is not authorized")
            # Verify at the authenticated root RPC boundary; Supervisor repeats this
            # verification before Store authority checks and append.
            from .dispatch_instruction import verify_dispatch_instruction
            verify_dispatch_instruction(
                body["instruction"], self.supervisor.dispatch_instruction_trust_keys or {},
                expected_principal=peer.principal,
                openssl_path=self.supervisor.dispatch_instruction_openssl_path or "",
            )
            return self.supervisor.accept_dispatch_intent(
                principal=peer.principal, instruction=body["instruction"],
            )
        if operation == "replay_dispatch_outcome":
            if (peer is None or peer.role != "dispatch_owner" or not peer.principal
                    or set(body) != {"instruction"}):
                raise ContractError("dispatch outcome replay is not authorized")
            # Historical acceptance is read from verified Store history. This
            # operation does not validate current expiry or admit new work.
            return self.supervisor.replay_dispatch_outcome(
                principal=peer.principal, instruction=body["instruction"],
            )
        if operation == "ack_dispatch_intent":
            fields = {"request_id", "payload_digest", "event_seq", "result_sha256", "service_generation"}
            if (peer is None or peer.role != "dispatch_owner" or not peer.principal
                    or set(body) != fields):
                raise ContractError("dispatch outcome acknowledgement is not authorized")
            return self.supervisor.ack_dispatch_intent(principal=peer.principal, **body)
        if operation == "next_dispatch_intent":
            if (peer is None or peer.role != "dispatcher" or set(body) != {"cursor"}
                    or (body["cursor"] is not None and not isinstance(body["cursor"], dict))):
                raise ContractError("dispatch subscription request is not authorized")
            audience = f"{peer.uid}:{peer.gid}:{peer.cgroup}"
            return self.supervisor.next_dispatch_intent(cursor=body["cursor"], audience=audience)
        if operation == "issue_dispatch_grant":
            if (peer is None or peer.role != "dispatcher" or set(body) != {"request_id"}
                    or not isinstance(body["request_id"], str)):
                raise ContractError("dispatch grant request is not authorized")
            return self.supervisor.issue_dispatch_intent_grant(request_id=body["request_id"])
        if operation == "claim":
            if set(body) != {"grant"} or not isinstance(body["grant"], dict):
                raise ContractError("claim request fields are invalid")
            receipt = self.supervisor.claim_runner_execution(body["grant"])
            if receipt is None:
                return None
            if not isinstance(receipt, dict):
                raise ContractError("Supervisor claim returned an invalid replay receipt")
            # Keep Store and in-process Supervisor APIs backward-compatible
            # (they return the raw stored receipt), while giving the runner's
            # execution-authority callback its explicit replay-state contract.
            return {"state": "COMPLETE", "receipt": receipt}
        if operation == "claim_status":
            if set(body) != {"grant"} or not isinstance(body["grant"], dict):
                raise ContractError("claim-status request fields are invalid")
            return self.supervisor.runner_execution_claim_status(body["grant"])
        if operation == "no_execution":
            if set(body) != {"grant", "reason_code"} or not isinstance(body["grant"], dict):
                raise ContractError("pre-spawn terminal request fields are invalid")
            return self.supervisor.mark_runner_prespawn_no_execution(
                body["grant"], reason_code=body["reason_code"],
            )
        if operation == "reserve":
            if set(body) != {"grant"} or not isinstance(body["grant"], dict):
                raise ContractError("reservation request fields are invalid")
            return self.supervisor.reserve_runner_execution(body["grant"])
        if operation == "pending":
            if set(body) != {"grant"} or not isinstance(body["grant"], dict):
                raise ContractError("pending request fields are invalid")
            return {"pending": self.supervisor.verify_pending_runner_execution(body["grant"])}
        if operation == "complete":
            if set(body) != {"grant", "receipt"} or not all(
                isinstance(body[name], dict) for name in ("grant", "receipt")
            ):
                raise ContractError("completion request fields are invalid")
            self.supervisor.complete_runner_execution(body["grant"], body["receipt"])
            return {"state": "COMPLETE"}
        if operation == "recover":
            if body:
                raise ContractError("recovery request must be empty")
            return {"indeterminate": self.supervisor.recover_predecessor_runner_claims()}
        if operation == "manifest":
            if set(body) != {"task_id", "manifest_sha256"}:
                raise ContractError("manifest request fields are invalid")
            return self.supervisor.store.get_manifest_by_digest(
                body["task_id"], body["manifest_sha256"],
            )
        if operation == "previous_receipt":
            if set(body) != {"task_id", "slot"}:
                raise ContractError("receipt-tip request fields are invalid")
            return {"receipt_sha256": self.supervisor.store.previous_receipt_sha256(
                body["task_id"], body["slot"],
            )}
        if operation == "reconcile_runner_execution":
            if (set(body) != {"version", "resolution"} or type(body.get("version")) is not int
                    or body.get("version") != 1 \
                    or not isinstance(body.get("resolution"), dict)):
                raise ContractError("operator reconciliation request fields are invalid")
            result = self.supervisor.reconcile_runner_execution(body["resolution"])
            if not isinstance(result, dict) or result.get("state") != "RECONCILED":
                raise ContractError("operator reconciliation returned an invalid result")
            return result
        if operation == "generation":
            if body:
                raise ContractError("generation request must be empty")
            provider = getattr(self.supervisor, "service_generation_provider", None)
            if not callable(provider):
                raise ContractError("active runner generation provider is unavailable")
            return {"service_generation": provider()}
        raise ContractError("unknown Supervisor RPC operation")


class SupervisorClient:
    """Small framed client that pins the root Supervisor peer before RPC."""

    def __init__(self, socket_path: str, *, expected_server_uid: int = 0, timeout_sec: float = 5.0):
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise ContractError("Supervisor RPC client requires POSIX peer credentials")
        if peer_pidfd_socket_option(socket) is None:
            raise ContractError("Supervisor RPC client requires kernel peer pidfd support")
        if not os.path.isabs(socket_path) or type(expected_server_uid) is not int:
            raise ContractError("Supervisor RPC client configuration is invalid")
        self.socket_path = socket_path
        self.expected_server_uid = expected_server_uid
        self.timeout_sec = timeout_sec

    def call(self, operation: str, body: dict) -> Any:
        if not isinstance(operation, str) or not isinstance(body, dict):
            raise ContractError("Supervisor RPC call is malformed")
        payload = canonical_bytes({"operation": operation, "body": body})
        if len(payload) > MAX_SUPERVISOR_MESSAGE_BYTES:
            raise ContractError("Supervisor RPC request exceeds its size limit")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(self.timeout_sec)
            client.connect(self.socket_path)
            raw_creds = client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            pid, uid, _gid = struct.unpack("3i", raw_creds)
            if uid != self.expected_server_uid:
                raise SupervisorRPCError("Supervisor RPC server identity is unauthorized")
            pidfd = _peer_pidfd(client, pid, require=True)
            try:
                client.sendall(_HEADER.pack(len(payload)) + payload)
                length = _HEADER.unpack(_recv_exact(client, _HEADER.size))[0]
                if length > MAX_SUPERVISOR_MESSAGE_BYTES:
                    raise SupervisorRPCError("Supervisor RPC response exceeds its size limit")
                response = json.loads(_recv_exact(client, length))
                if not _pidfd_alive(pidfd):
                    raise SupervisorRPCError("Supervisor RPC server exited during request")
            finally:
                if pidfd is not None:
                    os.close(pidfd)
        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
            raise SupervisorRPCError("Supervisor RPC response is malformed")
        if response["ok"] is True:
            if set(response) != {"ok", "result"}:
                raise SupervisorRPCError("Supervisor RPC success response is malformed")
            return response["result"]
        if set(response) != {"ok", "error"}:
            raise SupervisorRPCError("Supervisor RPC error response is malformed")
        else:
            error = response.get("error")
            if not isinstance(error, str) or not error:
                raise SupervisorRPCError("Supervisor RPC refusal is malformed")
            raise SupervisorRPCError(f"Supervisor RPC refused request ({error})", kind=error)

    def submit_dispatch_intent(self, **body: Any) -> dict:
        result = self.call("submit_dispatch_intent", body)
        if (not isinstance(result, dict) or set(result) != {
                "event_seq", "principal", "task_id", "slot", "attempt", "epoch", "run_id",
                "request_id", "service_generation", "lease_id", "payload_digest", "manifest_digest",
                "instruction", "key_id",
        } or type(result["event_seq"]) is not int or result["event_seq"] < 1
                or type(result["lease_id"]) is not int or result["lease_id"] < 1
                or any(type(result[field]) is not int or result[field] < 1
                       for field in ("attempt", "epoch"))
                or any(not isinstance(result[field], str) or not result[field]
                       for field in ("principal", "task_id", "slot", "run_id", "service_generation"))
                or not isinstance(result["request_id"], str)
                or not re.fullmatch(r"[0-9a-f]{32}", result["request_id"])
                or any(not isinstance(result[field], str) or not _SHA256.fullmatch(result[field])
                       for field in ("payload_digest", "manifest_digest"))):
            raise SupervisorRPCError("Supervisor returned a malformed dispatch intent")
        from .dispatch_instruction import validate_dispatch_instruction
        instruction = validate_dispatch_instruction(result["instruction"])
        if (instruction["key_id"] != result["key_id"]
                or any(instruction[field] != result[field] for field in (
                    "task_id", "slot", "attempt", "epoch", "run_id", "request_id",
                ))):
            raise SupervisorRPCError("Supervisor response differs from signed dispatch instruction")
        return result

    def replay_dispatch_outcome(self, **body: Any) -> dict | None:
        if set(body) != {"instruction"}:
            raise SupervisorRPCError("dispatch outcome replay request is malformed")
        result = self.call("replay_dispatch_outcome", body)
        if result is not None and not isinstance(result, dict):
            raise SupervisorRPCError("Supervisor returned a malformed historical dispatch outcome")
        return result

    def ack_dispatch_intent(self, **body: Any) -> dict:
        required = {"request_id", "payload_digest", "event_seq", "result_sha256", "service_generation"}
        if set(body) != required:
            raise SupervisorRPCError("dispatch acknowledgement request is malformed")
        result = self.call("ack_dispatch_intent", body)
        if result != body:
            raise SupervisorRPCError("Supervisor acknowledged a different dispatch outcome")
        return result

    def next_dispatch_intent(self, cursor: dict | None) -> dict:
        result = self.call("next_dispatch_intent", {"cursor": cursor})
        if (not isinstance(result, dict) or set(result) != {"intent", "cursor_after", "cursor_idle"}
                or (result["intent"] is not None and not isinstance(result["intent"], dict))
                or not isinstance(result["cursor_after"], dict)
                or not isinstance(result["cursor_idle"], dict)):
            raise SupervisorRPCError("Supervisor returned a malformed dispatch subscription result")
        for name in ("cursor_after", "cursor_idle"):
            token = result[name]
            if (set(token) != {"version", "sequence", "service_generation", "audience", "mac"}
                    or type(token["version"]) is not int or token["version"] != 1
                    or type(token["sequence"]) is not int or token["sequence"] < 0
                    or not isinstance(token["service_generation"], str)
                    or not token["service_generation"]
                    or not isinstance(token["audience"], str) or not token["audience"]
                    or not isinstance(token["mac"], str) or not _SHA256.fullmatch(token["mac"])):
                raise SupervisorRPCError("Supervisor returned a malformed dispatch cursor")
        intent = result["intent"]
        if intent is not None:
            required = {
                "event_seq", "principal", "task_id", "slot", "attempt", "epoch", "run_id",
                "request_id", "service_generation", "lease_id", "payload_digest", "manifest_digest",
            }
            if (set(intent) != required
                    or type(intent["event_seq"]) is not int or intent["event_seq"] < 1
                    or any(not isinstance(intent[field], str) or not intent[field]
                           for field in ("principal", "task_id", "slot", "run_id", "service_generation"))
                    or any(type(intent[field]) is not int or intent[field] < 1
                           for field in ("attempt", "epoch", "lease_id"))
                    or not isinstance(intent["request_id"], str)
                    or not re.fullmatch(r"[0-9a-f]{32}", intent["request_id"])
                    or any(not isinstance(intent[field], str) or not _SHA256.fullmatch(intent[field])
                           for field in ("payload_digest", "manifest_digest"))
                    or result["cursor_after"]["sequence"] != intent["event_seq"]):
                raise SupervisorRPCError("Supervisor returned a malformed dispatch intent")
        return result

    def issue_dispatch_grant(self, request_id: str) -> dict:
        result = self.call("issue_dispatch_grant", {"request_id": request_id})
        if not isinstance(result, dict):
            raise SupervisorRPCError("Supervisor returned a malformed dispatch grant")
        try:
            from .execution_grant import validate_execution_grant
            return validate_execution_grant(result)
        except ContractError as exc:
            raise SupervisorRPCError("Supervisor returned an invalid dispatch grant") from exc

    def claim(self, grant: dict) -> dict | None:
        result = self.call("claim", {"grant": grant})
        if result is not None and not isinstance(result, dict):
            raise SupervisorRPCError("Supervisor returned a malformed claim result")
        return result

    def claim_status(self, grant: dict) -> dict:
        result = self.call("claim_status", {"grant": grant})
        if (not isinstance(result, dict)
                or result.get("state") not in {
                    "NOT_FOUND", "PENDING", "EXECUTION_RESERVED",
                    "COMPLETE", "INDETERMINATE", "RECONCILED",
                }
                or not isinstance(result.get("service_generation"), str)):
            raise SupervisorRPCError("Supervisor returned a malformed claim status")
        if result["state"] == "COMPLETE":
            if set(result) != {"state", "service_generation", "receipt"} or not isinstance(result["receipt"], dict):
                raise SupervisorRPCError("Supervisor returned a malformed completed claim status")
        elif (result["state"] == "INDETERMINATE"
              and set(result) == {"state", "service_generation", "reason_code"}):
            if result["reason_code"] != "RUNNER_PRESPAWN_FAILURE":
                raise SupervisorRPCError("Supervisor returned an unknown terminal reason")
        elif set(result) != {"state", "service_generation"}:
            raise SupervisorRPCError("Supervisor returned unexpected claim status fields")
        return result

    def terminalize_no_execution(self, grant: dict, reason_code: str) -> dict:
        result = self.call("no_execution", {"grant": grant, "reason_code": reason_code})
        if (not isinstance(result, dict)
                or set(result) != {"state", "grant_id", "payload_sha256", "service_generation"}
                or result.get("state") != "NO_EXECUTION"):
            raise SupervisorRPCError("Supervisor returned a malformed pre-spawn terminal result")
        return result

    def reconcile_runner_execution(self, resolution: dict) -> dict:
        result = self.call("reconcile_runner_execution", {"version": 1, "resolution": resolution})
        if not isinstance(result, dict) or result.get("state") != "RECONCILED":
            raise SupervisorRPCError("Supervisor returned a malformed reconciliation result")
        return result

    def reserve(self, grant: dict) -> dict:
        result = self.call("reserve", {"grant": grant})
        if (not isinstance(result, dict)
                or set(result) != {"state", "grant_id", "payload_sha256", "service_generation"}
                or result.get("state") != "EXECUTION_RESERVED"):
            raise SupervisorRPCError("Supervisor returned a malformed reservation")
        return result

    def pending(self, grant: dict) -> bool:
        result = self.call("pending", {"grant": grant})
        return isinstance(result, dict) and result.get("pending") is True

    def generation(self) -> str:
        result = self.call("generation", {})
        if (not isinstance(result, dict) or set(result) != {"service_generation"}
                or not isinstance(result["service_generation"], str)
                or not result["service_generation"]):
            raise SupervisorRPCError("Supervisor returned a malformed generation")
        return result["service_generation"]

    def complete(self, grant: dict, receipt: dict) -> None:
        result = self.call("complete", {"grant": grant, "receipt": receipt})
        if not isinstance(result, dict) or result.get("state") != "COMPLETE":
            raise SupervisorRPCError("Supervisor did not confirm completion")

    def recover(self) -> int:
        result = self.call("recover", {})
        if not isinstance(result, dict) or type(result.get("indeterminate")) is not int:
            raise SupervisorRPCError("Supervisor returned a malformed recovery result")
        return result["indeterminate"]

    def manifest(self, task_id: str, manifest_sha256: str) -> dict:
        result = self.call("manifest", {"task_id": task_id, "manifest_sha256": manifest_sha256})
        if not isinstance(result, dict):
            raise SupervisorRPCError("Supervisor returned a malformed manifest")
        return result

    def previous_receipt(self, task_id: str, slot: str) -> str | None:
        result = self.call("previous_receipt", {"task_id": task_id, "slot": slot})
        if not isinstance(result, dict) or set(result) != {"receipt_sha256"}:
            raise SupervisorRPCError("Supervisor returned a malformed receipt tip")
        return result["receipt_sha256"]


DEFAULT_CONFIG_PATH = "/etc/vst-runner/supervisor-service.json"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,127}$")
_PRINCIPAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _read_controlled_json(path: str, *, max_bytes: int = 262144) -> dict:
    if os.name != "posix" or not os.path.isabs(path):
        raise ContractError("Supervisor config path must be absolute on POSIX")
    parent = os.path.dirname(path)
    while True:
        info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("Supervisor config path is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o022 or info.st_size > max_bytes):
            raise ContractError("Supervisor config is not a bounded root-controlled file")
        raw = bytearray()
        while len(raw) <= max_bytes:
            chunk = os.read(fd, min(65536, max_bytes + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > max_bytes:
            raise ContractError("Supervisor config exceeds its size limit")
    finally:
        os.close(fd)
    def unique(pairs: list[tuple[str, Any]]) -> dict:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ContractError("duplicate Supervisor config key")
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ContractError("Supervisor config must be a JSON object")
    return value


def _current_root_dispatch_issuer_config(config_path: str, openssl_path: str) -> dict | None:
    """Reload issuer metadata from its root-controlled source for each authority check."""
    root_config = _read_controlled_json(config_path)
    raw = root_config.get("root_dispatch_issuer")
    if raw is None:
        return None
    fields = {"enabled", "key_id", "public_key_fingerprint",
              "maximum_ttl_seconds", "minimum_safety_slack_seconds"}
    if not isinstance(raw, dict) or set(raw) != fields or type(raw.get("enabled")) is not bool:
        raise ContractError("live root dispatch issuer configuration is malformed")
    return {
        **raw,
        "private_key_path": "/etc/vst-runner/dispatch-instruction-private.pem",
        "public_key_path": "/etc/vst-runner/dispatch-instruction-public.pem",
        "openssl_path": openssl_path,
        "signer": {
            "key_id": raw.get("key_id"), "key_class": "DELEGATED_V1",
            "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
            "public_key_fingerprint": raw.get("public_key_fingerprint"),
        },
    }


def _current_dispatch_instruction_trust_registry() -> dict:
    info = os.stat(DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH, follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != 0o644):
        raise ContractError("live dispatch-instruction trust registry is unsafe")
    return _read_controlled_json(DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH, max_bytes=65536)


def _read_root_key(path: str) -> bytes:
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ContractError("Supervisor secret key path must be absolute")
    parent = os.path.dirname(path)
    while True:
        info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("Supervisor secret key directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size < 32 or info.st_size > 4096):
            raise ContractError("Supervisor secret key has unsafe owner, mode, or size")
        data = bytearray()
        while len(data) <= 4096:
            chunk = os.read(fd, 4097 - len(data))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) < 32 or len(data) > 4096:
            raise ContractError("Supervisor secret key has invalid length")
        return bytes(data)
    finally:
        os.close(fd)


def _runtime_observation_identity(config_path: str, config: dict) -> dict[str, str]:
    """Hash the exact loaded source and non-secret runtime contract inputs safely."""
    source_root = os.path.realpath(str(Path(__file__).resolve().parents[2]))
    source_paths = {
        "supervisor_service": str(Path(__file__).resolve()),
        "supervisor": str(Path(__file__).resolve().with_name("supervisor.py")),
        "preflight": str(Path(__file__).resolve().with_name("preflight.py")),
        "preflight_capture": str(Path(__file__).resolve().with_name("preflight_capture.py")),
    }
    config_paths = {
        "supervisor_config": config_path,
        "network_profile": "/etc/vst-runner/network-profile.json",
        "bootstrap_request": "/etc/vst-runner/bootstrap-request.json",
        "probe_entrypoint": "/etc/vst-runner/probe-entrypoint.py",
        "supervisor_unit": "/etc/systemd/system/vst-supervisor.service",
        "probe_unit": "/etc/systemd/system/vst-sandbox-probe.service",
        "task_manifest": "/etc/vst-runner/task-manifest.json",
        "sandbox_spec": str(Path(__file__).resolve().parents[2] / "docs" / "SANDBOX_SPEC.md"),
        "dispatch_trust": config.get("dispatch_instruction_trust_registry_path"),
    }
    if "assignment_policy_path" in config:
        config_paths["assignment_policy"] = config["assignment_policy_path"]

    # Pin every installed input that systemd actually executes or applies. The
    # runtime bundle manifest is in the exact selected archive; compare installed
    # bytes to its source digests before the one-shot service can be started.
    runtime_bundle_path = os.path.join(source_root, "docs", "sdlc", "runtime-config", "bundle-manifest.json")
    runtime_layout_path = os.path.join(source_root, "docs", "sdlc", "runtime-config", "installation-layout.json")
    config_paths["runtime_bundle_manifest"] = runtime_bundle_path
    config_paths["runtime_installation_layout"] = runtime_layout_path
    bundle = _read_controlled_json(runtime_bundle_path, max_bytes=2 * 1024 * 1024)
    layout = _read_controlled_json(runtime_layout_path, max_bytes=2 * 1024 * 1024)
    bundle_files = {item.get("path"): item for item in bundle.get("files", [])
                    if isinstance(item, dict)}
    bundle_units = {item.get("name"): item for item in bundle.get("units", [])
                    if isinstance(item, dict)}
    required_units = {"vst-supervisor.service", "vst-sandbox-probe.service"}
    if not required_units <= set(bundle_units):
        raise ContractError("runtime bundle does not pin both Supervisor and probe units")
    runtime_head = os.path.basename(source_root).removeprefix("vst-runtime-")
    if (bundle.get("runtime_source_head") != runtime_head
            or bundle.get("state") != "PREPARED_NOT_INSTALLED"):
        raise ContractError("runtime bundle identity does not match the selected versioned archive")
    expected_installed = {
        config_paths["probe_entrypoint"]: bundle_files.get("probe-entrypoint.py", {}).get("sha256"),
        config_paths["supervisor_unit"]: bundle_units["vst-supervisor.service"].get("sha256"),
        config_paths["probe_unit"]: bundle_units["vst-sandbox-probe.service"].get("sha256"),
    }
    from .preflight_capture import PROBE_UNIT, _systemctl_properties
    dropin_properties = _systemctl_properties(PROBE_UNIT, ("DropInPaths",))
    installed_probe_dropins = dropin_properties["DropInPaths"].split()
    expected_probe_dropins = []
    expected_supervisor_dropins = []
    for entry in layout.get("unit_overrides", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("destination"), str):
            raise ContractError("runtime layout contains a malformed systemd drop-in record")
        destination = entry["destination"]
        if destination.startswith("/etc/systemd/system/vst-sandbox-probe.service.d/"):
            expected_probe_dropins.append(destination)
        elif destination.startswith("/etc/systemd/system/vst-supervisor.service.d/"):
            expected_supervisor_dropins.append(destination)
    if not expected_probe_dropins or installed_probe_dropins != sorted(expected_probe_dropins):
        raise ContractError("effective probe drop-ins differ from the exact runtime layout")
    supervisor_dropins = _systemctl_properties(
        "vst-supervisor.service", ("DropInPaths",))["DropInPaths"].split()
    if supervisor_dropins != sorted(expected_supervisor_dropins):
        raise ContractError("effective Supervisor drop-ins differ from the exact runtime layout")
    for prefix, paths_for_unit in (("probe_dropin", expected_probe_dropins),
                                   ("supervisor_dropin", expected_supervisor_dropins)):
        for index, destination in enumerate(sorted(paths_for_unit)):
            basename = os.path.basename(destination)
            layout_record = next(item for item in layout["unit_overrides"]
                                 if item["destination"] == destination)
            source_record = bundle_files.get(layout_record.get("source"))
            expected_digest = layout_record.get("sha256")
            if (not isinstance(source_record, dict) or source_record.get("sha256") != expected_digest
                    or not isinstance(expected_digest, str) or not _SHA256.fullmatch(expected_digest)):
                raise ContractError("runtime bundle does not exactly pin an effective systemd drop-in")
            config_paths[f"{prefix}_{index}_{basename}"] = destination
            expected_installed[destination] = expected_digest
    paths = {**source_paths, **config_paths}
    marker_path = os.path.join(source_root, ".vst-runtime-manifest.json")
    if os.path.realpath("/opt/vst-runtime") != source_root:
        raise ContractError("running Supervisor source is outside the active versioned runtime selector")
    paths["runtime_manifest"] = marker_path
    result: dict[str, str] = {}
    for label, file_path in paths.items():
        if not isinstance(file_path, str) or not os.path.isabs(file_path):
            raise ContractError("runtime observation source/config path is invalid")
        parent = os.path.dirname(file_path)
        while True:
            try:
                parent_info = os.stat(parent, follow_symlinks=False)
            except OSError as exc:
                raise ContractError("runtime observation source/config parent is unavailable") from exc
            if (not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != 0
                    or parent_info.st_mode & 0o022):
                raise ContractError("runtime observation source/config parent is not root-controlled")
            if parent == "/":
                break
            parent = os.path.dirname(parent)
        try:
            fd = os.open(file_path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            raise ContractError("runtime observation source/config file is unavailable") from exc
        try:
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
                    or info.st_size > 8 * 1024 * 1024):
                raise ContractError("runtime observation source/config file is not bounded and root-controlled")
            raw = bytearray()
            while len(raw) <= 8 * 1024 * 1024:
                chunk = os.read(fd, min(65536, 8 * 1024 * 1024 + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            if len(raw) > 8 * 1024 * 1024:
                raise ContractError("runtime observation source/config file exceeds its size limit")
            result[label] = hashlib.sha256(raw).hexdigest()
        finally:
            os.close(fd)
    if len(result) != len(paths):
        raise ContractError("runtime observation source/config inventory is incomplete")
    for installed_path, expected_digest in expected_installed.items():
        if not isinstance(expected_digest, str) or not _SHA256.fullmatch(expected_digest):
            raise ContractError("runtime bundle contains a malformed installed source pin")
        if result.get(next((label for label, candidate in paths.items()
                            if candidate == installed_path), "")) != expected_digest:
            raise ContractError("installed probe or systemd bytes differ from the exact runtime bundle")
    runtime_manifest = _read_controlled_json(marker_path, max_bytes=65536)
    if (runtime_manifest.get("schema") != 3 or runtime_manifest.get("head") != runtime_head
            or not isinstance(runtime_head, str) or not re.fullmatch(r"[0-9a-f]{40}", runtime_head)
            or not isinstance(runtime_manifest.get("archive_sha256"), str)
            or not _SHA256.fullmatch(runtime_manifest["archive_sha256"])):
        raise ContractError("active runtime marker does not bind a full source head and archive digest")
    result["runtime_identity"] = hashlib.sha256(canonical_bytes({
        "head": runtime_head, "archive_sha256": runtime_manifest["archive_sha256"],
    })).hexdigest()
    return result


def _validate_root_data_path(path: str, *, max_existing_mode: int = 0o600) -> None:
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ContractError("Supervisor data path must be absolute")
    parent = os.path.dirname(path)
    while True:
        info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ContractError("Supervisor data directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    try:
        info = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ContractError("Supervisor data path cannot be inspected") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) & ~max_existing_mode):
        raise ContractError("existing Supervisor data file has unsafe type, owner, or mode")


def _active_runner_generation(config: dict) -> str:
    from .runner_fence import _manager_unit

    invocation, control_group = _manager_unit({
        "systemctl_path": config["systemctl_path"],
        "unit_name": config["runner_unit_name"],
    })
    record = _read_controlled_json(config["generation_record_path"], max_bytes=65536)
    required = {
        "version", "state", "unit", "invocation_id", "control_group",
        "cgroup_device", "cgroup_inode", "lock_device", "lock_inode",
        "generation", "predecessor_outcome", "sequence", "recorded_at",
        "previous_record_sha256", "record_sha256",
    }
    if not isinstance(record, dict) or set(record) != required:
        raise ContractError("published runner generation record has an invalid schema")
    record_stat = os.stat(config["generation_record_path"], follow_symlinks=False)
    if (not stat.S_ISREG(record_stat.st_mode) or record_stat.st_uid != 0
            or stat.S_IMODE(record_stat.st_mode) != 0o644):
        raise ContractError("published runner generation record is not root-owned and read-only")
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    if record["record_sha256"] != hashlib.sha256(canonical_bytes(body)).hexdigest():
        raise ContractError("published runner generation record hash is invalid")
    if (record["version"] != 1 or record["state"] != "RUNNING"
            or record["unit"] != config["runner_unit_name"]
            or record["invocation_id"] != invocation or record["generation"] != invocation
            or record["control_group"] != control_group
            or control_group != config["runner_control_group"]):
        raise ContractError("published runner generation is not the active manager invocation")
    cgroup = os.path.realpath(os.path.join("/sys/fs/cgroup", control_group.lstrip("/")))
    cgroup_root = os.path.realpath("/sys/fs/cgroup")
    if os.path.commonpath((cgroup_root, cgroup)) != cgroup_root:
        raise ContractError("published runner cgroup escaped the unified hierarchy")
    lock_path = config["runner_lock_path"]
    cgroup_stat = os.stat(cgroup, follow_symlinks=False)
    lock_stat = os.stat(lock_path, follow_symlinks=False)
    if (cgroup_stat.st_dev != record["cgroup_device"]
            or cgroup_stat.st_ino != record["cgroup_inode"]
            or lock_stat.st_dev != record["lock_device"]
            or lock_stat.st_ino != record["lock_inode"]):
        raise ContractError("published runner generation resource identity changed")
    return invocation


def load_supervisor_service(path: str = DEFAULT_CONFIG_PATH) -> tuple[AuthenticatedSupervisorAPI, Any]:
    """Build the root Supervisor from a strict root-owned deployment contract."""
    value = _read_controlled_json(path)
    required = {
        "store_path", "anchor_path", "event_key_path", "startup_supervisor_key_path",
        "execution_grant_key_id", "execution_grant_private_key_path", "execution_grant_trust_keys", "openssl_path",
        "dispatch_instruction_trust_registry_path",
        "run_id", "probe_nonce", "operator_key_path",
        "execution_grant_audience", "generation_record_path", "runner_unit_name",
        "runner_control_group", "runner_lock_path", "systemctl_path", "model_provenance",
        "socket_path", "socket_gid", "peers",
        "allow_schema_upgrade",
    }
    optional_keys = {"assignment_policy_path", "assignment_policy_sha256", "root_dispatch_issuer"}
    if (not required <= set(value) or set(value) - required - optional_keys
            or ("assignment_policy_path" in value) != ("assignment_policy_sha256" in value)):
        raise ContractError("Supervisor service config fields do not match its schema")
    root_dispatch_issuer = None
    if "root_dispatch_issuer" in value:
        issuer = value["root_dispatch_issuer"]
        issuer_fields = {"enabled", "key_id", "public_key_fingerprint",
                         "maximum_ttl_seconds", "minimum_safety_slack_seconds"}
        if not isinstance(issuer, dict) or set(issuer) != issuer_fields or type(issuer["enabled"]) is not bool:
            raise ContractError("root dispatch issuer configuration is malformed")
        if (not isinstance(issuer["key_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", issuer["key_id"])
                or issuer["key_id"] == value["execution_grant_key_id"]
                or not isinstance(issuer["public_key_fingerprint"], str)
                or not _SHA256.fullmatch(issuer["public_key_fingerprint"])
                or type(issuer["maximum_ttl_seconds"]) is not int
                or issuer["maximum_ttl_seconds"] < 1
                or type(issuer["minimum_safety_slack_seconds"]) is not int
                or issuer["minimum_safety_slack_seconds"] < 1):
            raise ContractError("root dispatch issuer limits or identity are invalid")
        private_path = "/etc/vst-runner/dispatch-instruction-private.pem"
        public_path = "/etc/vst-runner/dispatch-instruction-public.pem"
        from .execution_grant import _trusted_root_file
        from .root_dispatch_issuer import public_key_fingerprint
        if issuer["enabled"]:
            _trusted_root_file(private_path, private=True)
            _trusted_root_file(public_path, private=False)
            if public_key_fingerprint(public_path) != issuer["public_key_fingerprint"]:
                raise ContractError("root dispatch public key does not match its configured fingerprint")
        root_dispatch_issuer = {
            **issuer, "private_key_path": private_path, "public_key_path": public_path,
            "openssl_path": value["openssl_path"],
            "signer": {
                "key_id": issuer["key_id"], "key_class": "DELEGATED_V1",
                "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
                "public_key_fingerprint": issuer["public_key_fingerprint"],
            },
        }
    assignment_policy = None
    if "assignment_policy_path" in value:
        from .assignment_basis import POLICY_PATH, validate_policy
        if value["assignment_policy_path"] != POLICY_PATH:
            raise ContractError("assignment delegation policy path is not fixed")
        if not isinstance(value["assignment_policy_sha256"], str) or not _SHA256.fullmatch(
                value["assignment_policy_sha256"]):
            raise ContractError("assignment policy digest pin is malformed")
        assignment_policy, policy_digest = validate_policy(
            _read_controlled_json(POLICY_PATH, max_bytes=65536),
        )
        if policy_digest != value["assignment_policy_sha256"]:
            raise ContractError("assignment policy does not match its root configuration digest pin")
    if type(value["allow_schema_upgrade"]) is not bool:
        raise ContractError("Supervisor schema-upgrade authorization must be a boolean")
    for field in ("store_path", "anchor_path", "event_key_path", "startup_supervisor_key_path",
                  "execution_grant_private_key_path", "operator_key_path",
                  "openssl_path", "generation_record_path",
                  "dispatch_instruction_trust_registry_path",
                  "runner_lock_path", "systemctl_path", "socket_path"):
        if not isinstance(value[field], str) or not os.path.isabs(value[field]):
            raise ContractError(f"Supervisor service {field} must be an absolute path")
    if (not isinstance(value["execution_grant_key_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value["execution_grant_key_id"])
            or not isinstance(value["execution_grant_audience"], str)
            or not _MODEL_ID.fullmatch(value["execution_grant_audience"])
            or not isinstance(value["runner_unit_name"], str)
            or not value["runner_unit_name"].endswith(".service")
            or not isinstance(value["runner_control_group"], str)
            or not value["runner_control_group"].startswith("/")
            or ".." in value["runner_control_group"].split("/")
            or os.path.normpath(value["runner_control_group"]) != value["runner_control_group"]):
        raise ContractError("Supervisor service identity configuration is malformed")
    if (value["runner_unit_name"] != "vst-runner.service"
            or value["runner_control_group"] != "/system.slice/vst-runner.service"
            or value["systemctl_path"] != "/usr/bin/systemctl"
            or value["runner_lock_path"] != "/run/vst-runner/cgroup-admission.lock"):
        raise ContractError("Supervisor service accepts only the fixed runner manager boundary")
    trust_keys = value["execution_grant_trust_keys"]
    if (not isinstance(trust_keys, dict) or not trust_keys
            or any(not isinstance(key_id, str)
                   or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key_id)
                   or not isinstance(key_path, str) or not os.path.isabs(key_path)
                   for key_id, key_path in trust_keys.items())):
        raise ContractError("Supervisor execution-grant trust registry is malformed")
    from .execution_grant import _trusted_root_file
    for key_path in trust_keys.values():
        _trusted_root_file(key_path, private=False)
    if root_dispatch_issuer is not None and root_dispatch_issuer["enabled"]:
        from .root_dispatch_issuer import public_key_fingerprint
        if root_dispatch_issuer["public_key_fingerprint"] in {
                public_key_fingerprint(key_path) for key_path in trust_keys.values()}:
            raise ContractError("root dispatch key must be distinct from execution-grant trust keys")
    if value["dispatch_instruction_trust_registry_path"] != DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH:
        raise ContractError("Supervisor dispatch-instruction registry path is not fixed")
    dispatch_registry_stat = os.stat(
        DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH, follow_symlinks=False,
    )
    if (not stat.S_ISREG(dispatch_registry_stat.st_mode)
            or dispatch_registry_stat.st_uid != 0 or dispatch_registry_stat.st_gid != 0
            or stat.S_IMODE(dispatch_registry_stat.st_mode) != 0o644):
        raise ContractError("Supervisor dispatch-instruction trust registry must be root-owned mode 0644")
    dispatch_trust = _read_controlled_json(DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH, max_bytes=65536)
    if (not isinstance(dispatch_trust, dict) or not dispatch_trust
            or any(not isinstance(key_id, str)
                   or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key_id)
                   or not isinstance(entry, dict)
                   or set(entry) != {"principal", "purpose", "public_key_path"}
                   or not isinstance(entry["principal"], str)
                   or not _PRINCIPAL_ID.fullmatch(entry["principal"])
                   or entry["purpose"] != "VST_S2_DISPATCH_INSTRUCTION_V1"
                   or not isinstance(entry["public_key_path"], str)
                   or not os.path.isabs(entry["public_key_path"])
                   for key_id, entry in dispatch_trust.items())):
        raise ContractError("Supervisor dispatch-instruction trust registry is malformed")
    for entry in dispatch_trust.values():
        _trusted_root_file(entry["public_key_path"], private=False)
    socket_gid = value["socket_gid"]
    if type(socket_gid) is not int or socket_gid < 1:
        raise ContractError("Supervisor service socket group is invalid")
    model_provenance = value["model_provenance"]
    if (not isinstance(model_provenance, dict) or not model_provenance
            or any(not isinstance(model, str) or not _MODEL_ID.fullmatch(model)
                   or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                   for model, digest in model_provenance.items())):
        raise ContractError("Supervisor model provenance registry is malformed")
    peers_value = value["peers"]
    if not isinstance(peers_value, list):
        raise ContractError("Supervisor peer policy must be a list")
    peers = []
    role_operations = {
        "dispatcher": frozenset({"issue_dispatch_grant", "next_dispatch_intent"}),
        "dispatch_owner": frozenset({
            "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
        }),
        "runnerd": frozenset({
            "claim", "claim_status", "reserve", "complete", "generation",
            "recover", "manifest", "previous_receipt", "no_execution",
        }),
        "signer": frozenset({"generation", "pending"}),
        # Optional, separately provisioned principal. No deployment config
        # enables it by default; it receives only signed reconciliation.
        "operator": frozenset({"reconcile_runner_execution"}),
    }
    if assignment_policy is not None:
        role_operations["delegated_issuer"] = frozenset(
            {"assignment_basis", "issue_root_dispatch_instruction"}
            if root_dispatch_issuer is not None and root_dispatch_issuer["enabled"]
            else {"assignment_basis"}
        )
        role_operations["assignment_bootstrap"] = frozenset({"bootstrap_assignment"})
    for item in peers_value:
        if not isinstance(item, dict):
            raise ContractError("Supervisor peer policy entry is malformed")
        role = item.get("role")
        expected_fields = {"role", "uid", "gid", "cgroup", "operations"}
        if role == "dispatch_owner":
            expected_fields.add("principal")
        if (set(item) != expected_fields
                or not isinstance(item["role"], str) or not item["role"]
                or type(item["uid"]) is not int or item["uid"] < 1
                or type(item["gid"]) is not int or item["gid"] < 1
                or not isinstance(item["cgroup"], str) or not item["cgroup"].startswith("/")
                or ".." in item["cgroup"].split("/")
                or os.path.normpath(item["cgroup"]) != item["cgroup"]
                or item["role"] not in role_operations
                or not isinstance(item["operations"], list)
                or frozenset(item["operations"]) != role_operations[item["role"]]
                or len(item["operations"]) != len(set(item["operations"]))
                or (role == "dispatch_owner" and (not isinstance(item.get("principal"), str)
                                                   or not _PRINCIPAL_ID.fullmatch(item["principal"])))):
            raise ContractError("Supervisor peer policy entry is malformed")
        peers.append(SupervisorPeer(
            role=item["role"], uid=item["uid"], gid=item["gid"], cgroup=item["cgroup"],
            operations=frozenset(item["operations"]), principal=item.get("principal"),
        ))
    if (not peers or len({peer.role for peer in peers}) != len(peers)
            or len({(peer.uid, peer.gid) for peer in peers}) != len(peers)):
        raise ContractError("Supervisor peer identities or roles are duplicated")
    roles = {peer.role for peer in peers}
    required_roles = {"dispatch_owner", "dispatcher", "runnerd", "signer"}
    if not required_roles <= roles or not roles <= set(role_operations):
        raise ContractError("Supervisor peer policy must define dispatcher, runnerd, and signer")
    if "delegated_issuer" in roles and assignment_policy is None:
        raise ContractError("delegated issuer requires its exact pinned root assignment policy")
    by_role = {peer.role: peer for peer in peers}
    runner_peer = by_role["runnerd"]
    signer_peer = by_role["signer"]
    dispatcher_peer = by_role["dispatcher"]
    owner_peer = by_role["dispatch_owner"]
    if assignment_policy is not None:
        issuer_peer = by_role.get("delegated_issuer")
        if issuer_peer is not None:
            expected_issuer = assignment_policy["issuer_peer"]
            if (issuer_peer.uid != expected_issuer["uid"] or issuer_peer.gid != expected_issuer["gid"]
                    or issuer_peer.cgroup != expected_issuer["cgroup"]
                    or expected_issuer["role"] != "delegated_issuer"):
                raise ContractError("delegated issuer peer differs from the root assignment policy")
            if (issuer_peer.uid in {runner_peer.uid, signer_peer.uid, dispatcher_peer.uid, owner_peer.uid, 999}
                    or issuer_peer.gid in {runner_peer.gid, signer_peer.gid, dispatcher_peer.gid, owner_peer.gid, 989}
                    or issuer_peer.cgroup in {runner_peer.cgroup, signer_peer.cgroup, dispatcher_peer.cgroup,
                                              owner_peer.cgroup}):
                raise ContractError("delegated issuer identity is not independently pinned")
        bootstrap_peer = by_role.get("assignment_bootstrap")
        if bootstrap_peer is not None:
            issuer_uids = {issuer_peer.uid} if issuer_peer is not None else set()
            issuer_gids = {issuer_peer.gid} if issuer_peer is not None else set()
            issuer_cgroups = {issuer_peer.cgroup} if issuer_peer is not None else set()
            expected_bootstrap = assignment_policy["bootstrap_peer"]
            if (bootstrap_peer.uid != expected_bootstrap["uid"]
                    or bootstrap_peer.gid != expected_bootstrap["gid"]
                    or bootstrap_peer.cgroup != expected_bootstrap["cgroup"]
                    or expected_bootstrap["role"] != "assignment_bootstrap"):
                raise ContractError("assignment bootstrap peer differs from root policy")
            reserved_uids = {runner_peer.uid, signer_peer.uid, dispatcher_peer.uid, owner_peer.uid, 999}
            reserved_gids = {
                runner_peer.gid, signer_peer.gid, dispatcher_peer.gid, owner_peer.gid, 989,
            }
            reserved_cgroups = {
                runner_peer.cgroup, signer_peer.cgroup, dispatcher_peer.cgroup, owner_peer.cgroup,
            }
            if (bootstrap_peer.uid in reserved_uids | issuer_uids
                    or bootstrap_peer.gid in reserved_gids | issuer_gids
                    or bootstrap_peer.cgroup in reserved_cgroups | issuer_cgroups):
                raise ContractError("assignment bootstrap identity is not independently pinned")
    if (runner_peer.uid != 997 or runner_peer.gid != 988
            or runner_peer.cgroup != value["runner_control_group"]
            or dispatcher_peer.cgroup != "/system.slice/vst-dispatcher.service"
            or signer_peer.uid in {runner_peer.uid, dispatcher_peer.uid, 999}
            or signer_peer.gid != 988
            or signer_peer.cgroup == runner_peer.cgroup
            or dispatcher_peer.uid in {runner_peer.uid, signer_peer.uid, 999}
            or dispatcher_peer.gid in {988, 989}
            or owner_peer.uid in {runner_peer.uid, signer_peer.uid, dispatcher_peer.uid, 999}
            or owner_peer.gid in {runner_peer.gid, signer_peer.gid, dispatcher_peer.gid, 989}
            or owner_peer.cgroup in {runner_peer.cgroup, signer_peer.cgroup, dispatcher_peer.cgroup}
            or socket_gid == 989):
        raise ContractError("Supervisor peer identities violate fixed runner, dispatcher, or worker separation")
    operator_peer = by_role.get("operator")
    if operator_peer is not None and (
            operator_peer.uid in {runner_peer.uid, signer_peer.uid, dispatcher_peer.uid, 999}
            or operator_peer.gid != socket_gid
            or operator_peer.gid in {runner_peer.gid, signer_peer.gid, dispatcher_peer.gid, 989}
            or operator_peer.cgroup in {runner_peer.cgroup, signer_peer.cgroup, dispatcher_peer.cgroup}):
        raise ContractError("Supervisor operator identity must be independently pinned")
    if operator_peer is not None and (
            operator_peer.uid == owner_peer.uid or operator_peer.gid == owner_peer.gid
            or operator_peer.cgroup == owner_peer.cgroup):
        raise ContractError("Supervisor owner and operator identities must be independently pinned")
    if operator_peer is not None and assignment_policy is not None:
        for role_name in ("delegated_issuer", "assignment_bootstrap"):
            peer = by_role.get(role_name)
            if peer is not None and (
                    operator_peer.uid == peer.uid or operator_peer.gid == peer.gid
                    or operator_peer.cgroup == peer.cgroup):
                raise ContractError("Supervisor operator identity must differ from assignment peers")
    for path_key in ("store_path", "anchor_path"):
        _validate_root_data_path(value[path_key])
    event_key = _read_root_key(value["event_key_path"])
    supervisor_key = _read_root_key(value["startup_supervisor_key_path"])
    if event_key == supervisor_key:
        raise ContractError("Store event and startup supervisor keys must be distinct")
    if root_dispatch_issuer is not None and root_dispatch_issuer["enabled"]:
        dispatch_private = _read_root_key(root_dispatch_issuer["private_key_path"])
        execution_private = _read_root_key(value["execution_grant_private_key_path"])
        if dispatch_private in {event_key, execution_private}:
            raise ContractError("root dispatch private key must be distinct from Store and execution keys")
    run_id, probe_nonce = value["run_id"], value["probe_nonce"]
    if (not isinstance(run_id, str) or not run_id.strip()
            or not isinstance(probe_nonce, str) or not probe_nonce.strip()):
        raise ContractError("Supervisor run id and runtime-observation nonce must be non-empty")
    operator_key = _read_root_key(value["operator_key_path"])
    if len({event_key, supervisor_key, operator_key}) != 3:
        raise ContractError("Store, startup-supervisor, and execution-resolution keys must be distinct")
    from .preflight import SPEC_PATH, _namespace_inode
    from .preflight_capture import (
        assert_runtime_services_inactive, assert_supervisor_readiness_barrier,
        classify_store_targets, observe_runtime_once,
        runtime_observation_binding_digest, verify_existing_observation_claim,
    )

    store_mode = classify_store_targets(value["store_path"], value["anchor_path"])
    assert_supervisor_readiness_barrier()
    spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    source_config_before = _runtime_observation_identity(path, value)
    host_namespaces = {name: _namespace_inode(name) for name in ("mnt", "net", "cgroup", "pid")}
    if store_mode == "fresh":
        probe = observe_runtime_once(
            run_id, probe_nonce, source_config_before,
            store_path=value["store_path"], anchor_path=value["anchor_path"],
        )
        if (probe["inventory"].get("spec_sha256") != spec_sha256
                or probe["inventory"].get("network_profile_sha256") != source_config_before.get("network_profile")
                or probe.get("result") != "PASS"):
            raise ContractError("runtime observation did not PASS with the exact spec or egress-profile identity")
        child_namespaces = probe["inventory"].get("namespace_inodes")
        if (not isinstance(child_namespaces, dict)
                or child_namespaces.get("mount") == host_namespaces["mnt"]
                or child_namespaces.get("network") == host_namespaces["net"]
                or child_namespaces.get("pid") != host_namespaces["pid"]):
            raise ContractError("probe did not use distinct mount and network namespaces")
        probe["inventory"]["supervisor_namespaces"] = host_namespaces
        probe["inventory"]["source_config_sha256"] = source_config_before
        claim_sha256 = probe["inventory"].get("observation_claim_sha256")
        if not isinstance(claim_sha256, str) or not _SHA256.fullmatch(claim_sha256):
            raise ContractError("fresh runtime observation claim identity is malformed")
        source_config_after = _runtime_observation_identity(path, value)
        if source_config_after != source_config_before:
            raise ContractError("source or runtime configuration changed during direct observation")
    else:
        if value["allow_schema_upgrade"]:
            raise ContractError("runtime recovery never authorizes Store schema migration")
        claim_sha256 = verify_existing_observation_claim(
            run_id, probe_nonce, spec_sha256, source_config_before,
        )
        # The durable claim proves which observation initialized this Store; it
        # does not prove the environment is still safe after a service restart.
        # Capture a fresh, invocation-bound observation before restoring readiness.
        probe = observe_runtime_once(
            run_id, secrets.token_hex(32), source_config_before,
            store_path=value["store_path"], anchor_path=value["anchor_path"],
            require_fresh_store=False, persist_one_start_claim=False,
        )
        if (probe["inventory"].get("spec_sha256") != spec_sha256
                or probe["inventory"].get("network_profile_sha256") != source_config_before.get("network_profile")
                or probe.get("result") != "PASS"):
            raise ContractError("recovery runtime observation did not PASS with the exact spec or egress-profile identity")
        child_namespaces = probe["inventory"].get("namespace_inodes")
        if (not isinstance(child_namespaces, dict)
                or child_namespaces.get("mount") == host_namespaces["mnt"]
                or child_namespaces.get("network") == host_namespaces["net"]
                or child_namespaces.get("pid") != host_namespaces["pid"]):
            raise ContractError("recovery probe did not use distinct mount and network namespaces")
        probe["inventory"]["supervisor_namespaces"] = host_namespaces
        probe["inventory"]["source_config_sha256"] = source_config_before
        source_config_after = _runtime_observation_identity(path, value)
        if source_config_after != source_config_before:
            raise ContractError("source or runtime configuration changed during recovery binding")
    probe_digest = runtime_observation_binding_digest(
        run_id, probe_nonce, spec_sha256, source_config_before, claim_sha256,
    )
    from .store import Store
    from .supervisor import Supervisor

    if classify_store_targets(value["store_path"], value["anchor_path"]) != store_mode:
        raise ContractError("runtime Store state changed before Store initialization")
    store = Store(
        value["store_path"], event_key=event_key,
        busy_timeout_sec=5.0,
        anchor_path=value["anchor_path"], sandbox_mode=True,
        supervisor_key=supervisor_key,
        execution_resolution_key=operator_key,
        supervisor_runner_id="persistent-runner-supervisor",
        allow_schema_upgrade=(value["allow_schema_upgrade"] if store_mode == "fresh" else False),
    )
    supervisor = Supervisor(
        store, operation_backend=None,
        run_id=run_id, probe_nonce=probe_nonce,
        operator_key=operator_key,
        execution_grant_key_id=value["execution_grant_key_id"],
        execution_grant_private_key_path=value["execution_grant_private_key_path"],
        execution_grant_openssl_path=value["openssl_path"],
        execution_grant_trust_keys=trust_keys,
        dispatch_instruction_trust_keys=dispatch_trust,
        dispatch_instruction_openssl_path=value["openssl_path"],
        execution_grant_audience=value["execution_grant_audience"],
        service_generation_provider=lambda: _active_runner_generation(value),
        model_provenance_verifier=lambda model, digest: model_provenance.get(model) == digest,
        model_provenance_digest_provider=lambda model: model_provenance.get(model),
        assignment_policy=assignment_policy,
        assignment_policy_provider=(
            lambda: _read_controlled_json(POLICY_PATH, max_bytes=65536)
        ) if assignment_policy is not None else None,
        root_dispatch_issuer=root_dispatch_issuer,
        root_dispatch_issuer_provider=(
            lambda: _current_root_dispatch_issuer_config(path, value["openssl_path"])
        ) if root_dispatch_issuer is not None and root_dispatch_issuer["enabled"] else None,
        dispatch_instruction_trust_provider=(
            _current_dispatch_instruction_trust_registry
        ) if root_dispatch_issuer is not None and root_dispatch_issuer["enabled"] else None,
    )
    source_config_after_store = _runtime_observation_identity(path, value)
    if source_config_after_store != source_config_before:
        raise ContractError("source or runtime configuration changed during Store initialization")
    assert_runtime_services_inactive()
    if store_mode == "fresh":
        store.ensure_preflight_consumed(run_id, probe_nonce, spec_sha256, probe_digest)
    else:
        store.require_existing_preflight_consumed(run_id, probe_nonce, spec_sha256, probe_digest)
    supervisor._probe_consumed = True
    api = AuthenticatedSupervisorAPI(
        supervisor, value["socket_path"], peers=tuple(peers), socket_gid=socket_gid,
        require_peer_pidfd=True,
    )
    return api, supervisor


def main() -> None:
    if os.geteuid() != 0:
        raise ContractError("Supervisor service must run as root")
    config_path = DEFAULT_CONFIG_PATH
    if len(sys.argv) == 2:
        config_path = sys.argv[1]
    elif len(sys.argv) > 2:
        raise ContractError("Supervisor service accepts only one fixed config path")
    api, supervisor = load_supervisor_service(config_path)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: api.shutdown())
    signal.signal(signal.SIGINT, lambda _signum, _frame: api.shutdown())
    try:
        api.serve_forever()
    finally:
        supervisor.store.close()


if __name__ == "__main__":
    main()
