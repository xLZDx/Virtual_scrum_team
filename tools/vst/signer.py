"""Runner-authenticated signing service for sandbox receipts.

The service is intentionally POSIX Unix-domain-socket only. It authenticates
the connecting process with SO_PEERCRED and fails closed on platforms without
that kernel identity API. Provision the socket and key under a runner-only
directory; the worker account must not be a member of that directory's group.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import sqlite3
import stat
import struct
import threading
from typing import Any

from .contracts import ContractError, TRUSTED_PARSER_CATALOG, _validate_repo_path, canonical_bytes
from .signing import DIFF_GATE_LABEL, MIN_KEY_BYTES, SIGNING_REQUEST_LABEL, sign

PROBE_LABEL = b"vst-sandbox-probe-v2\0"
MAX_REQUEST_BYTES = 1024 * 1024
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
                 runner_gid: int | None = None):
        if os.name != "posix" or not hasattr(socket, "SO_PEERCRED"):
            raise ContractError("authenticated signer IPC requires POSIX SO_PEERCRED")
        self.socket_path = os.path.abspath(socket_path)
        self.key = _key_is_private(key_path)
        self.runner_uid = os.geteuid() if runner_uid is None else runner_uid
        self.runner_gid = os.getegid() if runner_gid is None else runner_gid
        self.ledger_path = self.socket_path + ".ledger"
        self._ledger: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._server: socket.socket | None = None

    def serve_forever(self) -> None:
        if os.path.lexists(self.socket_path):
            raise ContractError("signer socket path already exists")
        parent_stat = os.stat(os.path.dirname(self.socket_path), follow_symlinks=False)
        if parent_stat.st_mode & 0o007 or parent_stat.st_gid != self.runner_gid or not parent_stat.st_mode & 0o010:
            raise ContractError("signer socket directory must deny others and grant runner-group traversal")
        if os.path.lexists(self.ledger_path) and os.path.islink(self.ledger_path):
            raise ContractError("signer replay ledger must not be a symlink")
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
            while True:
                conn, _ = server.accept()
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
        creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", creds)
        if uid != self.runner_uid:
            conn.sendall(b'{"error":"unauthorized"}')
            return
        raw = bytearray()
        while len(raw) <= MAX_REQUEST_BYTES:
            chunk = conn.recv(min(65536, MAX_REQUEST_BYTES + 1 - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        try:
            if len(raw) > MAX_REQUEST_BYTES:
                raise ContractError("signing request exceeds size limit")
            message = json.loads(raw)
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
                encoded = canonical_bytes(message)
                signature = sign(body, self.key, DIFF_GATE_LABEL if purpose == "diff_gate" else PROBE_LABEL)
                request_id = message["request_id"]
            else:
                request = validate_signing_request(message)
                encoded = canonical_bytes(request)
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
            response = {"signature": signature}
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            response = {"error": "invalid_request", "detail": str(exc)[:200]}
        conn.sendall(canonical_bytes(response))


def sign_over_socket(socket_path: str, request: dict[str, Any]) -> str:
    """Submit one canonical request and return its signer-authorized signature."""
    validate_signing_request(request)
    payload = canonical_bytes(request)
    if len(payload) > MAX_REQUEST_BYTES:
        raise ContractError("signing request exceeds size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        response = json.loads(client.recv(4096))
    if not isinstance(response, dict) or set(response) != {"signature"}:
        raise ContractError("signer rejected request")
    signature = response["signature"]
    if not isinstance(signature, str) or len(signature) != hashlib.sha256().digest_size * 2:
        raise ContractError("signer returned malformed signature")
    return signature


def authorize_runner_over_socket(socket_path: str) -> None:
    """Prove IPC authentication before launching commands; invalid body cannot sign."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(b"{}")
        client.shutdown(socket.SHUT_WR)
        response = json.loads(client.recv(4096))
    if not isinstance(response, dict) or response.get("error") != "invalid_request":
        raise ContractError("signer did not authenticate runner identity")


def sign_diff_over_socket(socket_path: str, request_id: str, evidence: dict[str, Any]) -> str:
    """Ask the authenticated signer to sign one deterministic diff-gate body."""
    if not isinstance(request_id, str) or not request_id:
        raise ContractError("request_id must be non-empty")
    message = {"purpose": "diff_gate", "request_id": request_id, "body": evidence}
    payload = canonical_bytes(message)
    if len(payload) > MAX_REQUEST_BYTES:
        raise ContractError("diff signing request exceeds size limit")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(socket_path)
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        response = json.loads(client.recv(4096))
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
        client.connect(socket_path)
        client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        response = json.loads(client.recv(4096))
    if not isinstance(response, dict) or set(response) != {"signature"}:
        raise ContractError("signer rejected probe request")
    signature = response["signature"]
    if not isinstance(signature, str) or len(signature) != hashlib.sha256().digest_size * 2:
        raise ContractError("signer returned malformed signature")
    return signature
