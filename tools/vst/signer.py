"""Runner-authenticated signing service for sandbox receipts.

The service is intentionally POSIX Unix-domain-socket only. It authenticates
the connecting process with SO_PEERCRED and fails closed on platforms without
that kernel identity API. Provision the socket and key under a runner-only
directory; the worker account must not be a member of that directory's group.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import select
import socket
import sqlite3
import stat
import struct
import threading
from typing import Any, Callable, Mapping
import sys

from .peer_pidfd import peer_pidfd_socket_option
from .contracts import ContractError, TRUSTED_PARSER_CATALOG, _validate_repo_path, canonical_bytes
from .signing import DIFF_GATE_LABEL, MIN_KEY_BYTES, SIGNING_REQUEST_LABEL, sign

PROBE_LABEL = b"vst-sandbox-probe-v2\0"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_SIGNER_RESPONSE_BYTES = 4096
SIGNER_SOCKET_TIMEOUT_SEC = 10.0
REQUEST_FIELDS = frozenset({
    "request_id", "task_id", "slot", "attempt", "epoch", "manifest_sha256",
    "candidate_head", "commands", "parser_results", "artifact_digests",
})


def validate_signing_request(request: object) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise ContractError("signing request: fields do not match v2 request contract")
    if any(not isinstance(request[k], str) or not request[k] for k in
           ("request_id", "task_id", "slot", "manifest_sha256", "candidate_head")):
        raise ContractError("signing request: required identifiers must be non-empty strings")
    if not isinstance(request["attempt"], int) or isinstance(request["attempt"], bool) or request["attempt"] < 1:
        raise ContractError("signing request: attempt must be a positive integer")
    if not isinstance(request["epoch"], int) or isinstance(request["epoch"], bool) or request["epoch"] < 1:
        raise ContractError("signing request: epoch must be a positive integer")
    if not re.fullmatch(r"[0-9a-f]{64}", request["manifest_sha256"]):
        raise ContractError("signing request: manifest_sha256 must be lowercase SHA-256")
    if not re.fullmatch(r"[0-9a-f]{40}", request["candidate_head"]):
        raise ContractError("signing request: candidate_head must be lowercase git object id")
    commands = request["commands"]
    parsers = request["parser_results"]
    artifacts = request["artifact_digests"]
    if not isinstance(commands, list) or not commands or not isinstance(parsers, list) or not parsers or not isinstance(artifacts, dict):
        raise ContractError("signing request: evidence fields have invalid types")
    command_argvs = []
    for item in commands:
        if (not isinstance(item, dict) or set(item) != {"argv", "exit_code"} or
                not isinstance(item["argv"], list) or not item["argv"] or
                any(not isinstance(arg, str) or not arg for arg in item["argv"]) or
                not isinstance(item["exit_code"], int) or isinstance(item["exit_code"], bool)):
            raise ContractError("signing request: malformed command evidence")
        command_argvs.append(item["argv"])
    parser_argvs = []
    for item in parsers:
        if (not isinstance(item, dict) or set(item) != {
                "argv", "parser_id", "parser_version", "parser_sha256", "parser_result"}):
            raise ContractError("signing request: malformed parser evidence")
        argv = item["argv"]
        if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg for arg in argv):
            raise ContractError("signing request: malformed parser argv")
        for key in ("parser_id", "parser_version"):
            if not isinstance(item[key], str) or not item[key]:
                raise ContractError(f"signing request: {key} must be non-empty")
        if not isinstance(item["parser_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["parser_sha256"]):
            raise ContractError("signing request: malformed parser digest")
        if (item["parser_id"], item["parser_version"], item["parser_sha256"]) not in TRUSTED_PARSER_CATALOG:
            raise ContractError("signing request: parser pin is not in trusted built-in catalog")
        outcome = item["parser_result"]
        if not isinstance(outcome, dict) or set(outcome) != {
                "executed_test_ids", "skipped_test_ids", "xfail_test_ids"}:
            raise ContractError("signing request: malformed parser outcomes")
        for ids in outcome.values():
            if not isinstance(ids, list) or any(not isinstance(test_id, str) or not test_id for test_id in ids):
                raise ContractError("signing request: parser outcomes must be string lists")
            if len(ids) != len(set(ids)):
                raise ContractError("signing request: duplicate parser outcome id")
        parser_argvs.append(argv)
    if command_argvs != parser_argvs or len(set(tuple(argv) for argv in command_argvs)) != len(command_argvs):
        raise ContractError("signing request: command and parser evidence is inconsistent")
    for path, digest in artifacts.items():
        try:
            _validate_repo_path(path, "signing request artifact path")
        except ContractError as exc:
            raise ContractError("signing request: malformed artifact path") from exc
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ContractError("signing request: malformed artifact digest evidence")
    return request


def request_signature(request: dict[str, Any], key: bytes) -> str:
    return sign(validate_signing_request(request), key, SIGNING_REQUEST_LABEL)


def _key_is_private(path: str) -> bytes:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise ContractError("signing key ACL verification requires POSIX O_NOFOLLOW")
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ContractError("signing key path must be absolute")
    parent = os.path.dirname(path)
    while True:
        info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022:
            raise ContractError("signing key directory is writable by group or other")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ContractError("signing key must be a regular non-symlink file")
        if st.st_uid != os.geteuid() or st.st_mode & 0o077:
            raise ContractError("signing key must be owned by signer and mode 0600")
        chunks = bytearray()
        while True:
            part = os.read(fd, 65536)
            if not part:
                break
            chunks.extend(part)
        key = bytes(chunks)
    finally:
        os.close(fd)
    if len(key) < MIN_KEY_BYTES:
        raise ContractError("signing key is too short")
    return key


class AuthenticatedSigner:
    """Small synchronous signer server with kernel-authenticated runner UID."""

    def __init__(self, socket_path: str, key_path: str, runner_uid: int | None = None,
                 runner_gid: int | None = None, *, require_pinned_daemon: bool = False,
                 service_cgroup: str | None = None,
                 grant_trust_keys: Mapping[str, str] | None = None,
                 grant_openssl_path: str | None = None,
                 grant_audience: str = "vst-runner-service-v1",
                 active_service_generation: Callable[[], str] | None = None,
                 pending_grant_checker: Callable[[dict], bool] | None = None,
                 ledger_path: str | None = None):
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise ContractError("authenticated signer IPC requires POSIX SO_PEERCRED")
        self.socket_path = os.path.abspath(socket_path)
        self.key = _key_is_private(key_path)
        self.runner_uid = os.geteuid() if runner_uid is None else runner_uid
        self.runner_gid = os.getegid() if runner_gid is None else runner_gid
        self.require_pinned_daemon = require_pinned_daemon
        self.service_cgroup = service_cgroup
        self.grant_trust_keys = grant_trust_keys
        self.grant_openssl_path = grant_openssl_path
        self.grant_audience = grant_audience
        self.active_service_generation = active_service_generation
        self.pending_grant_checker = pending_grant_checker
        if require_pinned_daemon and (
            peer_pidfd_socket_option(socket) is None
            or not isinstance(service_cgroup, str) or not service_cgroup.startswith("/")
            or not isinstance(grant_trust_keys, Mapping)
            or not isinstance(grant_openssl_path, str)
            or not callable(active_service_generation)
            or not callable(pending_grant_checker)
        ):
            raise ContractError("pinned runner signer policy is incomplete or unsupported")
        self.ledger_path = os.path.abspath(ledger_path) if ledger_path is not None else self.socket_path + ".ledger"
        self._ledger: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._server: socket.socket | None = None
        self._shutdown = threading.Event()

    def shutdown(self) -> None:
        """Stop accepting requests after the current bounded signing call."""
        self._shutdown.set()

    def serve_forever(self) -> None:
        if os.path.lexists(self.socket_path):
            raise ContractError("signer socket path already exists")
        parent_stat = os.stat(os.path.dirname(self.socket_path), follow_symlinks=False)
        if (not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.geteuid()
                or parent_stat.st_gid != self.runner_gid
                or stat.S_IMODE(parent_stat.st_mode) != 0o710):
            raise ContractError("signer socket directory must deny others and grant runner-group traversal")
        ledger_parent = os.path.dirname(self.ledger_path)
        parent_stat = os.stat(ledger_parent, follow_symlinks=False)
        if (not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.geteuid()
                or stat.S_IMODE(parent_stat.st_mode) != 0o700):
            raise ContractError("signer replay ledger directory must be private and signer-owned")
        if os.path.lexists(self.ledger_path):
            ledger_stat = os.stat(self.ledger_path, follow_symlinks=False)
            if (not stat.S_ISREG(ledger_stat.st_mode) or ledger_stat.st_uid != os.geteuid()
                    or stat.S_IMODE(ledger_stat.st_mode) != 0o600):
                raise ContractError("signer replay ledger must be a private signer-owned regular file")
        ledger = sqlite3.connect(self.ledger_path)
        os.chmod(self.ledger_path, 0o600)
        ledger.execute("CREATE TABLE IF NOT EXISTS requests (request_id TEXT PRIMARY KEY, payload BLOB NOT NULL, signature TEXT NOT NULL)")
        ledger.commit()
        self._ledger = ledger
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server = server
        try:
            server.bind(self.socket_path)
            os.chown(self.socket_path, -1, self.runner_gid)
            os.chmod(self.socket_path, 0o660)
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
            if self._ledger is not None:
                self._ledger.close()
                self._ledger = None
            try:
                os.unlink(self.socket_path)
            except FileNotFoundError:
                pass

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(SIGNER_SOCKET_TIMEOUT_SEC)
        creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", creds)
        pidfd = None
        try:
            if uid != self.runner_uid or (self.runner_gid is not None and gid != self.runner_gid):
                conn.sendall(b'{"error":"unauthorized"}')
                return
            if self.require_pinned_daemon:
                pidfd = self._pin_and_check_peer(conn, pid, uid, gid)
            raw = bytearray()
            while len(raw) <= MAX_REQUEST_BYTES:
                chunk = conn.recv(min(65536, MAX_REQUEST_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            if len(raw) > MAX_REQUEST_BYTES:
                raise ContractError("signing request exceeds size limit")
            wire_message = json.loads(raw)
            message = self._unwrap_granted_message(wire_message, pid, uid, gid, pidfd) if self.require_pinned_daemon else wire_message
            if self.require_pinned_daemon and message.get("purpose") == "runner_authorize":
                conn.sendall(canonical_bytes({"authorized": True}))
                return
            encoded_message = canonical_bytes(wire_message)
            if isinstance(message, dict) and message.get("purpose") in {"diff_gate", "probe"}:
                purpose = message["purpose"]
                if set(message) != {"purpose", "request_id", "body"}:
                    raise ContractError("typed signing request has unknown or missing fields")
                if not isinstance(message["request_id"], str) or not message["request_id"]:
                    raise ContractError("diff signing request_id must be non-empty")
                body = message["body"]
                if not isinstance(body, dict):
                    raise ContractError("typed signing body must be an object")
                if purpose == "diff_gate" and set(body) != {
                    "manifest_sha256", "candidate_head", "diff_sha256", "changed_paths", "verdict", "reason"
                }:
                    raise ContractError("diff signing body has unknown or missing fields")
                if purpose == "diff_gate":
                    if (not isinstance(body["manifest_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["manifest_sha256"]) or
                        not isinstance(body["candidate_head"], str) or not re.fullmatch(r"[0-9a-f]{40}", body["candidate_head"]) or
                        not isinstance(body["diff_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["diff_sha256"]) or
                        body["verdict"] not in {"PASS", "FAIL"} or
                        not isinstance(body["changed_paths"], list) or
                        any(not isinstance(path, str) or not path for path in body["changed_paths"]) or
                        len(body["changed_paths"]) != len(set(body["changed_paths"]))):
                        raise ContractError("diff signing body is malformed")
                if purpose == "probe" and set(body) != {
                    "run_id", "spec_sha256", "nonce", "checked_properties", "result", "inventory"
                }:
                    raise ContractError("probe signing body has unknown or missing fields")
                if purpose == "probe" and (
                    not isinstance(body["run_id"], str) or not body["run_id"] or
                    not isinstance(body["nonce"], str) or not body["nonce"] or
                    not isinstance(body["spec_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", body["spec_sha256"]) or
                    body["result"] not in {"PASS", "FAIL"} or
                    not isinstance(body["checked_properties"], dict) or
                    set(body["checked_properties"]) != {
                        "automount_disabled", "interop_disabled", "no_container_socket",
                        "non_root", "external_egress_blocked", "loopback_canary",
                        "empty_external_allowlist",
                    } or
                    any(not isinstance(value, bool) for value in body["checked_properties"].values()) or
                    not isinstance(body["inventory"], dict)):
                    raise ContractError("probe signing body is malformed")
                encoded = encoded_message
                signature = sign(body, self.key, DIFF_GATE_LABEL if purpose == "diff_gate" else PROBE_LABEL)
                request_id = message["request_id"]
            else:
                request = validate_signing_request(message)
                encoded = encoded_message
                signature = request_signature(request, self.key)
                request_id = request["request_id"]
            with self._lock:
                assert self._ledger is not None
                self._ledger.execute("BEGIN IMMEDIATE")
                prior = self._ledger.execute(
                    "SELECT payload, signature FROM requests WHERE request_id=?", (request_id,)
                ).fetchone()
                if prior is not None:
                    if bytes(prior[0]) != encoded:
                        self._ledger.rollback()
                        raise ContractError("request_id replayed with a different payload")
                    signature = str(prior[1])
                else:
                    self._ledger.execute(
                        "INSERT INTO requests(request_id,payload,signature) VALUES(?,?,?)",
                        (request_id, encoded, signature),
                    )
                self._ledger.commit()
            if self.require_pinned_daemon:
                self._ensure_peer_alive(pidfd)
            response = {"signature": signature}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            response = {"error": "invalid_request", "detail": str(exc)[:200]}
        except ContractError:
            response = {"error": "unauthorized" if self.require_pinned_daemon else "invalid_request"}
        except Exception:
            logging.getLogger(__name__).warning("signer request refused")
            response = {"error": "unauthorized" if self.require_pinned_daemon else "invalid_request"}
        finally:
            if pidfd is not None:
                os.close(pidfd)
        try:
            conn.sendall(canonical_bytes(response))
        except OSError:
            return

    def _pin_and_check_peer(self, conn: socket.socket, pid: int, uid: int, gid: int) -> int:
        option = peer_pidfd_socket_option(socket)
        if option is None:
            raise ContractError("kernel peer pidfd support is unavailable")
        raw_pidfd = conn.getsockopt(socket.SOL_SOCKET, option, struct.calcsize("i"))
        if not isinstance(raw_pidfd, bytes) or len(raw_pidfd) != struct.calcsize("i"):
            raise ContractError("kernel did not return a pinned peer pidfd")
        pidfd = struct.unpack("i", raw_pidfd)[0]
        if pidfd < 0:
            raise ContractError("kernel returned an invalid peer pidfd")
        os.set_inheritable(pidfd, False)
        try:
            self._ensure_peer_alive(pidfd)
            cgroup = self._peer_cgroup(pid)
            if cgroup != self.service_cgroup:
                raise ContractError("signing peer is outside the configured service cgroup")
            self._ensure_peer_alive(pidfd)
            return pidfd
        except BaseException:
            os.close(pidfd)
            raise

    @staticmethod
    def _ensure_peer_alive(pidfd: int | None) -> None:
        if pidfd is None:
            raise ContractError("pinned peer identity is unavailable")
        poller = select.poll()
        poller.register(pidfd, select.POLLIN | select.POLLHUP | select.POLLERR)
        if poller.poll(0):
            raise ContractError("signing peer exited during request handling")

    @staticmethod
    def _peer_cgroup(pid: int) -> str:
        try:
            with open(f"/proc/{pid}/cgroup", encoding="ascii") as stream:
                entries = [line.rstrip("\n").split(":", 2) for line in stream]
        except OSError as exc:
            raise ContractError("pinned signing peer cgroup cannot be read") from exc
        unified = next((entry[2] for entry in entries if len(entry) == 3 and entry[:2] == ["0", ""]), None)
        if not unified or ".." in unified.split("/"):
            raise ContractError("signing peer is not in a verified unified cgroup")
        return os.path.normpath(unified)

    def _unwrap_granted_message(self, wire: object, pid: int, uid: int, gid: int, pidfd: int | None) -> dict:
        if not isinstance(wire, dict):
            raise ContractError("signed runner envelope must be an object")
        purpose = wire.get("purpose")
        if purpose == "runner_authorize" and set(wire) == {"purpose", "grant"}:
            grant = wire["grant"]
            message = {"purpose": "runner_authorize"}
        elif purpose == "runner_sign" and set(wire) == {"purpose", "grant", "request"}:
            grant = wire["grant"]
            message = wire["request"]
            validate_signing_request(message)
        elif purpose == "runner_diff" and set(wire) == {"purpose", "grant", "request_id", "body"}:
            grant = wire["grant"]
            message = {"purpose": "diff_gate", "request_id": wire["request_id"], "body": wire["body"]}
        else:
            raise ContractError("unsupported or ungranted signer request")
        self._ensure_peer_alive(pidfd)
        generation = self.active_service_generation()
        from .execution_grant import verify_execution_grant

        valid = verify_execution_grant(
            grant, self.grant_trust_keys, audience=self.grant_audience,
            service_generation=generation, openssl_path=self.grant_openssl_path,
        )
        if purpose == "runner_sign":
            if any(message.get(name) != valid[field] for name, field in (
                ("request_id", "request_id"), ("task_id", "task_id"),
                ("slot", "slot"), ("attempt", "attempt"), ("epoch", "epoch"),
                ("manifest_sha256", "manifest_sha256"),
            )):
                raise ContractError("signing payload does not match its execution grant")
        elif purpose == "runner_diff" and wire["request_id"] != f"{valid['request_id']}:diff":
            raise ContractError("diff signing request does not match its execution grant")
        if self.pending_grant_checker(valid) is not True:
            raise ContractError("Store has no current PENDING claim for this execution grant")
        self._ensure_peer_alive(pidfd)
        return message


def sign_over_socket(
    socket_path: str, request: dict[str, Any], *, execution_grant: dict | None = None,
) -> str:
    """Submit one canonical request and return its signer-authorized signature."""
    validate_signing_request(request)
    message = request if execution_grant is None else {
        "purpose": "runner_sign", "grant": execution_grant, "request": request,
    }
    payload = canonical_bytes(message)
    if len(payload) > MAX_REQUEST_BYTES:
        raise ContractError("signing request exceeds size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(SIGNER_SOCKET_TIMEOUT_SEC)
        client.connect(socket_path)
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        response = _recv_signer_response(client)
    if not isinstance(response, dict) or set(response) != {"signature"}:
        raise ContractError("signer rejected request")
    signature = response["signature"]
    if not isinstance(signature, str) or len(signature) != hashlib.sha256().digest_size * 2:
        raise ContractError("signer returned malformed signature")
    return signature


DEFAULT_SERVICE_CONFIG = "/etc/vst-runner/signer-service.json"


def load_signer_service(path: str = DEFAULT_SERVICE_CONFIG) -> AuthenticatedSigner:
    """Load the strict daemon-pinned signer from root-controlled configuration."""
    from .supervisor_service import SupervisorClient, _read_controlled_json

    config = _read_controlled_json(path)
    required = {
        "socket_path", "key_path", "ledger_path", "runner_uid", "runner_gid", "runner_cgroup",
        "grant_trust_keys", "openssl_path", "grant_audience", "supervisor_socket",
    }
    if set(config) != required:
        raise ContractError("signer service config fields do not match its schema")
    for name in ("socket_path", "key_path", "ledger_path", "openssl_path", "supervisor_socket"):
        if not isinstance(config[name], str) or not os.path.isabs(config[name]):
            raise ContractError(f"signer service {name} must be an absolute path")
    if (type(config["runner_uid"]) is not int or config["runner_uid"] != 997
            or type(config["runner_gid"]) is not int or config["runner_gid"] != 988
            or not isinstance(config["runner_cgroup"], str)
            or not config["runner_cgroup"].startswith("/")
            or ".." in config["runner_cgroup"].split("/")
            or os.path.normpath(config["runner_cgroup"]) != config["runner_cgroup"]):
        raise ContractError("signer runner identity or cgroup does not match its fixed policy")
    keys = config["grant_trust_keys"]
    if (not isinstance(keys, dict) or not keys
            or any(not isinstance(key_id, str)
                   or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key_id)
                   or not isinstance(key_path, str) or not os.path.isabs(key_path)
                   for key_id, key_path in keys.items())):
        raise ContractError("signer execution-grant trust registry is malformed")
    if (not isinstance(config["grant_audience"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", config["grant_audience"])):
        raise ContractError("signer grant audience is malformed")
    supervisor = SupervisorClient(config["supervisor_socket"])
    return AuthenticatedSigner(
        config["socket_path"], config["key_path"],
        runner_uid=config["runner_uid"], runner_gid=config["runner_gid"],
        require_pinned_daemon=True, service_cgroup=config["runner_cgroup"],
        grant_trust_keys=keys, grant_openssl_path=config["openssl_path"],
        grant_audience=config["grant_audience"],
        active_service_generation=supervisor.generation,
        pending_grant_checker=supervisor.pending,
        ledger_path=config["ledger_path"],
    )


def main() -> None:
    config_path = DEFAULT_SERVICE_CONFIG
    if len(sys.argv) == 2:
        config_path = sys.argv[1]
    elif len(sys.argv) > 2:
        raise ContractError("signer service accepts only one config path")
    service = load_signer_service(config_path)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: service.shutdown())
    signal.signal(signal.SIGINT, lambda _signum, _frame: service.shutdown())
    service.serve_forever()


def authorize_runner_over_socket(socket_path: str, *, grant: dict | None = None) -> None:
    """Prove signer admission for the exact Store-claimed execution grant."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(SIGNER_SOCKET_TIMEOUT_SEC)
        client.connect(socket_path)
        message = {"purpose": "runner_authorize", "grant": grant} if grant is not None else {}
        client.sendall(canonical_bytes(message))
        client.shutdown(socket.SHUT_WR)
        response = _recv_signer_response(client)
    if grant is None:
        if not isinstance(response, dict) or response.get("error") != "invalid_request":
            raise ContractError("signer did not authenticate runner identity")
    elif not isinstance(response, dict) or response != {"authorized": True}:
        raise ContractError("signer did not authorize the claimed execution grant")


def sign_diff_over_socket(
    socket_path: str, request_id: str, evidence: dict[str, Any], *,
    execution_grant: dict | None = None,
) -> str:
    """Ask the authenticated signer to sign one deterministic diff-gate body."""
    if not isinstance(request_id, str) or not request_id:
        raise ContractError("request_id must be non-empty")
    message = (
        {"purpose": "diff_gate", "request_id": request_id, "body": evidence}
        if execution_grant is None else
        {"purpose": "runner_diff", "grant": execution_grant,
         "request_id": request_id, "body": evidence}
    )
    payload = canonical_bytes(message)
    if len(payload) > MAX_REQUEST_BYTES:
        raise ContractError("diff signing request exceeds size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(SIGNER_SOCKET_TIMEOUT_SEC)
        client.connect(socket_path)
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        response = _recv_signer_response(client)
    if not isinstance(response, dict) or set(response) != {"signature"}:
        raise ContractError("signer rejected diff request")
    signature = response["signature"]
    if not isinstance(signature, str) or len(signature) != hashlib.sha256().digest_size * 2:
        raise ContractError("signer returned malformed signature")
    return signature


def sign_probe_over_socket(socket_path: str, request_id: str, inventory: dict[str, Any]) -> str:
    """Ask the authenticated signer to sign the exact run-bound probe body."""
    if not isinstance(request_id, str) or not request_id:
        raise ContractError("request_id must be non-empty")
    expected = {"run_id", "spec_sha256", "nonce", "checked_properties", "result", "inventory"}
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise ContractError("probe body has unknown or missing fields")
    message = {"purpose": "probe", "request_id": request_id, "body": inventory}
    payload = canonical_bytes(message)
    if len(payload) > MAX_REQUEST_BYTES:
        raise ContractError("probe signing request exceeds size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(SIGNER_SOCKET_TIMEOUT_SEC)
        client.connect(socket_path)
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        response = _recv_signer_response(client)
    if not isinstance(response, dict) or set(response) != {"signature"}:
        raise ContractError("signer rejected probe request")
    signature = response["signature"]
    if not isinstance(signature, str) or len(signature) != hashlib.sha256().digest_size * 2:
        raise ContractError("signer returned malformed signature")
    return signature


def _recv_signer_response(client: socket.socket) -> dict:
    """Read the complete bounded JSON reply; stream sockets may return partial data."""
    raw = bytearray()
    while len(raw) <= MAX_SIGNER_RESPONSE_BYTES:
        chunk = client.recv(min(1024, MAX_SIGNER_RESPONSE_BYTES + 1 - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
    if not raw or len(raw) > MAX_SIGNER_RESPONSE_BYTES:
        raise ContractError("signer response is empty or exceeds its size limit")
    try:
        response = json.loads(bytes(raw))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ContractError("signer response is malformed JSON") from exc
    if not isinstance(response, dict):
        raise ContractError("signer response must be a JSON object")
    return response


if __name__ == "__main__":
    main()
