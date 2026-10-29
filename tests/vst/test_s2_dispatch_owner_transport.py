"""Functional transport tests for the S2-DISPATCH-M01 source integration slice."""

from __future__ import annotations

import base64
import os
import socket as real_socket
import stat
import struct
import threading
from types import SimpleNamespace

import pytest

from tools.vst import dispatch_owner_transport as transport_module
from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.dispatch_owner_client import DispatchOutcomeUnknown
from tools.vst import dispatch_owner_service as owner_service_module


_HEADER = struct.Struct("!I")
_SOCKET_GID = 123
_SYSTEMD_PID = 1
_ROOT_UID = 0
_PEER_PIDFD = 789


def _envelope() -> dict:
    signature = base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")
    return {
        "version": 1,
        "algorithm": "Ed25519",
        "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
        "request_id": "a" * 32,
        "task_id": "task-transport",
        "slot": "tests",
        "attempt": 1,
        "epoch": 7,
        "run_id": "run-transport",
        "key_id": "fixture-key",
        "expires_at": "2099-01-01T00:00:00Z",
        "signature": signature,
    }


def _result(envelope: dict) -> dict:
    return {
        "instruction": envelope,
        "principal": "Codex",
        "key_id": envelope["key_id"],
        "request_id": envelope["request_id"],
        "task_id": envelope["task_id"],
        "slot": envelope["slot"],
        "attempt": envelope["attempt"],
        "epoch": envelope["epoch"],
        "run_id": envelope["run_id"],
        "event_seq": 9,
        "payload_digest": "b" * 64,
        "service_generation": "generation-fixture",
    }


def _frame(payload: bytes) -> bytes:
    return _HEADER.pack(len(payload)) + payload


class _Socket:
    def __init__(self, response: bytes = b"", *, connect_error: Exception | None = None,
                 send_error: Exception | None = None, peer_pid: int = _SYSTEMD_PID,
                 peer_uid: int = _ROOT_UID, peer_pidfd: bytes | None = struct.pack("i", _PEER_PIDFD)):
        self.response = bytearray(response)
        self.connect_error = connect_error
        self.send_error = send_error
        self.peer_pid = peer_pid
        self.peer_uid = peer_uid
        self.peer_pidfd = peer_pidfd
        self.connected_to: str | None = None
        self.timeout: float | None = None
        self.sent: list[bytes] = []
        self.shutdown_calls: list[int] = []
        self.getsockopt_calls: list[int] = []
        self.pidfd_inheritable: list[tuple[int, bool]] = []
        self.closed_fds: list[int] = []
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def connect(self, path: str) -> None:
        self.connected_to = path
        if self.connect_error is not None:
            raise self.connect_error

    def getsockopt(self, _level: int, option: int, _size: int) -> bytes:
        self.getsockopt_calls.append(option)
        if option == transport_module.socket.SO_PEERCRED:
            return struct.pack("3i", self.peer_pid, self.peer_uid, _SOCKET_GID)
        if option == transport_module.socket.SO_PEERPIDFD:
            return self.peer_pidfd or b""
        raise AssertionError(f"unexpected socket option: {option}")

    def sendall(self, payload: bytes) -> None:
        self.sent.append(payload)
        if self.send_error is not None:
            raise self.send_error

    def shutdown(self, how: int) -> None:
        self.shutdown_calls.append(how)

    def recv(self, size: int) -> bytes:
        assert self.shutdown_calls == [transport_module.socket.SHUT_WR], (
            "request write side must be closed before reading the relay response"
        )
        chunk = bytes(self.response[:size])
        del self.response[:size]
        return chunk

    def close(self) -> None:
        self.closed = True


class _SocketPairClient:
    """Mock kernel identity calls while delegating framing to a real AF_UNIX socketpair."""

    def __init__(self, client_socket) -> None:
        self.client_socket = client_socket
        self.connected_to: str | None = None
        self.sent: list[bytes] = []
        self.shutdown_calls: list[int] = []
        self.getsockopt_calls: list[int] = []
        self.pidfd_inheritable: list[tuple[int, bool]] = []
        self.closed_fds: list[int] = []
        self.closed = False

    def settimeout(self, timeout: float) -> None:
        self.client_socket.settimeout(timeout)

    def connect(self, path: str) -> None:
        # The socketpair is already connected. Retain the production fixed-path assertion.
        self.connected_to = path

    def getsockopt(self, _level: int, option: int, _size: int) -> bytes:
        self.getsockopt_calls.append(option)
        if option == transport_module.socket.SO_PEERCRED:
            return struct.pack("3i", _SYSTEMD_PID, _ROOT_UID, _SOCKET_GID)
        if option == transport_module.socket.SO_PEERPIDFD:
            return struct.pack("i", _PEER_PIDFD)
        raise AssertionError(f"unexpected socket option: {option}")

    def sendall(self, payload: bytes) -> None:
        self.sent.append(payload)
        self.client_socket.sendall(payload)

    def shutdown(self, how: int) -> None:
        self.shutdown_calls.append(how)
        self.client_socket.shutdown(how)

    def recv(self, size: int) -> bytes:
        assert self.shutdown_calls == [transport_module.socket.SHUT_WR]
        return self.client_socket.recv(size)

    def close(self) -> None:
        self.closed = True
        self.client_socket.close()


class _Poller:
    def register(self, _pidfd: int, _events: int) -> None:
        pass

    def poll(self, _timeout: int) -> list:
        return []


def _trusted_lstat(path: str):
    if path == os.path.dirname(transport_module.OWNER_SOCKET_PATH):
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o710, st_uid=_ROOT_UID, st_gid=_SOCKET_GID)
    if path == transport_module.OWNER_SOCKET_PATH:
        return SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=_ROOT_UID, st_gid=_SOCKET_GID)
    raise AssertionError(f"unexpected filesystem identity check: {path}")


def _patch_socket(monkeypatch, fake_socket: _Socket, *, lstat=None,
                  poll_error: Exception | None = None,
                  poll_events: list[tuple[int, int]] | None = None) -> list[tuple[int, int]]:
    creations: list[tuple[int, int]] = []
    socket_api = SimpleNamespace(
        AF_UNIX=1, SOCK_STREAM=2, SOL_SOCKET=3, SO_PEERCRED=4,
        SO_PEERPIDFD=5, SHUT_WR=real_socket.SHUT_WR,
    )

    def create(family: int, kind: int) -> _Socket:
        creations.append((family, kind))
        return fake_socket

    socket_api.socket = create
    class _Poller:
        def register(self, _pidfd: int, _events: int) -> None:
            pass

        def poll(self, _timeout: int) -> list:
            if poll_error is not None:
                raise poll_error
            return poll_events or []

    os_api = SimpleNamespace(
        name="posix",
        path=os.path,
        lstat=lstat or _trusted_lstat,
        set_inheritable=lambda fd, flag: fake_socket.pidfd_inheritable.append((fd, flag)),
        close=lambda fd: fake_socket.closed_fds.append(fd),
    )
    monkeypatch.setattr(transport_module, "socket", socket_api)
    monkeypatch.setattr(transport_module, "os", os_api)
    monkeypatch.setattr(
        transport_module, "select",
        SimpleNamespace(poll=_Poller, POLLIN=1, POLLHUP=2, POLLERR=4),
    )
    return creations


def _client(**kwargs):
    return transport_module.DispatchOwnerSocketClient(
        expected_principal="Codex", expected_socket_gid=_SOCKET_GID, **kwargs,
    )


def test_real_af_unix_socketpair_half_close_completes_owner_service_once(
    monkeypatch, dispatch_instruction_keypair,
):
    if not hasattr(real_socket, "AF_UNIX"):
        pytest.skip("real AF_UNIX socketpair requires designated POSIX/WSL runtime")

    keypair = dispatch_instruction_keypair
    fields = {
        "request_id": "d" * 32,
        "task_id": "task-socketpair",
        "slot": "tests",
        "attempt": 1,
        "epoch": 7,
        "run_id": "run-socketpair",
    }
    envelope = keypair.sign(fields)

    class _Supervisor:
        def __init__(self) -> None:
            self.submit_calls: list[dict] = []
            self.ack_calls: list[dict] = []
            self.replay_calls: list[dict] = []

        def submit_dispatch_intent(self, **kwargs) -> dict:
            self.submit_calls.append(kwargs)
            return _result(kwargs["instruction"])

        def ack_dispatch_intent(self, **kwargs) -> dict:
            self.ack_calls.append(kwargs)
            return kwargs

        def replay_dispatch_outcome(self, **kwargs):
            self.replay_calls.append(kwargs)
            return None

    supervisor = _Supervisor()
    owner_config = owner_service_module.DispatchOwnerServiceConfig(
        principal="Codex",
        openssl_path=owner_service_module.OPENSSL_PATH,
        trust_registry=keypair.trust_registry,
    )
    owner_service = owner_service_module.DispatchOwnerService(
        owner_config, supervisor=supervisor,
    )
    server_socket, client_socket = real_socket.socketpair(
        real_socket.AF_UNIX, real_socket.SOCK_STREAM,
    )
    caller_socket = _SocketPairClient(client_socket)
    _patch_socket(monkeypatch, caller_socket)
    outcomes: list[bool] = []
    errors: list[BaseException] = []

    def serve_one_request() -> None:
        try:
            outcomes.append(owner_service._handle(server_socket))
        except BaseException as exc:
            errors.append(exc)
        finally:
            server_socket.close()

    thread = threading.Thread(target=serve_one_request, daemon=True)
    thread.start()
    try:
        result = _client(timeout_sec=4.0).submit_signed_instruction(envelope)
        thread.join(timeout=5.0)
        assert not thread.is_alive(), "owner service deadlocked waiting for request EOF"
        assert errors == []
        assert outcomes == [False]
        assert result == _result(envelope)
        assert supervisor.submit_calls == [{"instruction": envelope}]
        assert len(supervisor.ack_calls) == 1
        assert supervisor.replay_calls == []
        assert len(caller_socket.sent) == 1
        assert caller_socket.shutdown_calls == [transport_module.socket.SHUT_WR]
    finally:
        if thread.is_alive():
            client_socket.close()
            thread.join(timeout=1.0)
        server_socket.close()
        client_socket.close()


def test_client_authenticates_systemd_peer_and_half_closes_before_read(monkeypatch):
    envelope = _envelope()
    result = _result(envelope)
    fake_socket = _Socket(_frame(canonical_bytes({"ok": True, "result": result})))
    creations = _patch_socket(monkeypatch, fake_socket)
    client = _client(timeout_sec=4.0)

    returned = client.submit_signed_instruction(envelope)

    assert returned == result
    assert fake_socket.connected_to == transport_module.OWNER_SOCKET_PATH
    assert fake_socket.timeout == 4.0
    assert fake_socket.sent == [_frame(canonical_bytes({"instruction": envelope}))]
    assert fake_socket.shutdown_calls == [transport_module.socket.SHUT_WR]
    assert fake_socket.getsockopt_calls == [
        transport_module.socket.SO_PEERCRED,
        transport_module.socket.SO_PEERPIDFD,
    ]
    assert fake_socket.pidfd_inheritable == [(_PEER_PIDFD, False)]
    assert fake_socket.closed_fds == [_PEER_PIDFD]
    assert creations == [(transport_module.socket.AF_UNIX, transport_module.socket.SOCK_STREAM)]
    assert fake_socket.closed


@pytest.mark.parametrize(
    ("socket_path", "timeout_sec"),
    [
        ("/tmp/other.sock", 1.0),
        (transport_module.OWNER_SOCKET_PATH, True),
        (transport_module.OWNER_SOCKET_PATH, 0.0),
        (transport_module.OWNER_SOCKET_PATH, 30.1),
    ],
)
def test_client_rejects_nonfixed_path_or_invalid_timeout(monkeypatch, socket_path, timeout_sec):
    _patch_socket(monkeypatch, _Socket())
    with pytest.raises(ContractError):
        _client(socket_path=socket_path, timeout_sec=timeout_sec)


def test_client_rejects_missing_peer_pidfd_support(monkeypatch):
    _patch_socket(monkeypatch, _Socket())
    monkeypatch.setattr(transport_module.socket, "SO_PEERPIDFD", None)

    with pytest.raises(ContractError, match="POSIX Unix-socket support"):
        _client()


@pytest.mark.parametrize(
    ("peer_pid", "peer_uid", "message"),
    [
        (222, _ROOT_UID, "not systemd"),
        (_SYSTEMD_PID, 1000, "not systemd"),
    ],
    ids=["wrong-peer-pid", "wrong-peer-uid"],
)
def test_client_rejects_wrong_kernel_peer_identity_without_sending(
    monkeypatch, peer_pid, peer_uid, message,
):
    fake_socket = _Socket(peer_pid=peer_pid, peer_uid=peer_uid)
    _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(ContractError, match=message):
        _client().submit_signed_instruction(_envelope())

    assert fake_socket.sent == []
    assert fake_socket.closed


def test_client_rejects_missing_or_malformed_peer_pidfd_without_sending(monkeypatch):
    fake_socket = _Socket(peer_pidfd=b"bad")
    _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(ContractError, match="did not return a peer pidfd"):
        _client().submit_signed_instruction(_envelope())

    assert fake_socket.getsockopt_calls == [
        transport_module.socket.SO_PEERCRED,
        transport_module.socket.SO_PEERPIDFD,
    ]
    assert fake_socket.sent == []


def test_client_closes_acquired_pidfd_if_peer_liveness_validation_raises(monkeypatch):
    fake_socket = _Socket()
    _patch_socket(monkeypatch, fake_socket, poll_error=OSError("injected pidfd poll failure"))

    with pytest.raises(ContractError, match="endpoint is unavailable"):
        _client().submit_signed_instruction(_envelope())

    assert fake_socket.pidfd_inheritable == [(_PEER_PIDFD, False)]
    assert fake_socket.closed_fds == [_PEER_PIDFD]
    assert fake_socket.sent == []
    assert fake_socket.closed


def test_client_rejects_exited_peer_when_pidfd_poll_reports_readiness(monkeypatch):
    fake_socket = _Socket()
    _patch_socket(monkeypatch, fake_socket, poll_events=[(_PEER_PIDFD, 1)])

    with pytest.raises(ContractError, match="peer has exited"):
        _client().submit_signed_instruction(_envelope())

    assert fake_socket.pidfd_inheritable == [(_PEER_PIDFD, False)]
    assert fake_socket.closed_fds == [_PEER_PIDFD]
    assert fake_socket.sent == []
    assert fake_socket.closed


@pytest.mark.parametrize(
    ("component", "metadata", "message"),
    [
        ("parent", {"st_uid": 1000}, "directory identity"),
        ("parent", {"st_mode": stat.S_IFDIR | 0o755}, "directory identity"),
        ("endpoint", {"st_uid": 1000}, "socket inode identity"),
        ("endpoint", {"st_mode": stat.S_IFREG | 0o660}, "socket inode identity"),
        ("endpoint", {"st_gid": _SOCKET_GID + 1}, "socket inode identity"),
    ],
    ids=["bad-directory-owner", "bad-directory-mode", "bad-socket-owner", "bad-socket-type", "bad-socket-group"],
)
def test_client_rejects_untrusted_socket_filesystem_identity(
    monkeypatch, component, metadata, message,
):
    parent = SimpleNamespace(st_mode=stat.S_IFDIR | 0o710, st_uid=_ROOT_UID, st_gid=_SOCKET_GID)
    endpoint = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o660, st_uid=_ROOT_UID, st_gid=_SOCKET_GID)
    target = parent if component == "parent" else endpoint
    for field, value in metadata.items():
        setattr(target, field, value)

    def lstat(path: str):
        if path == os.path.dirname(transport_module.OWNER_SOCKET_PATH):
            return parent
        if path == transport_module.OWNER_SOCKET_PATH:
            return endpoint
        raise AssertionError(f"unexpected filesystem identity check: {path}")

    fake_socket = _Socket()
    creations = _patch_socket(monkeypatch, fake_socket, lstat=lstat)
    with pytest.raises(ContractError, match=message):
        _client().submit_signed_instruction(_envelope())
    assert creations == []
    assert fake_socket.sent == []


def test_connect_failure_is_a_refusal_before_any_request_is_sent(monkeypatch):
    fake_socket = _Socket(connect_error=OSError("injected connect failure"))
    _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(ContractError, match="endpoint is unavailable"):
        _client().submit_signed_instruction(_envelope())

    assert fake_socket.sent == []
    assert fake_socket.closed


@pytest.mark.parametrize(
    "response",
    [
        _frame(canonical_bytes({"ok": False, "error": "reconciliation_required"})),
        _HEADER.pack(transport_module.MAX_RESPONSE_BYTES + 1),
        _frame(b'{"ok":true} '),
        _frame(b"{invalid-json"),
        _frame(canonical_bytes({"ok": True, "result": _result(_envelope())})) + b"trailing",
        _HEADER.pack(8) + b"{}",
    ],
    ids=[
        "reconciliation-required", "oversized", "noncanonical", "malformed-json",
        "trailing", "truncated",
    ],
)
def test_uncertain_or_invalid_post_submit_response_fails_closed_without_retry(monkeypatch, response):
    fake_socket = _Socket(response)
    creations = _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(DispatchOutcomeUnknown):
        _client().submit_signed_instruction(_envelope())

    assert len(creations) == 1
    assert len(fake_socket.sent) == 1
    assert fake_socket.shutdown_calls == [transport_module.socket.SHUT_WR]
    assert fake_socket.closed


def test_explicit_owner_refusal_is_not_retried(monkeypatch):
    fake_socket = _Socket(_frame(canonical_bytes({"ok": False, "error": "refused"})))
    _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(ContractError, match="refused"):
        _client().submit_signed_instruction(_envelope())

    assert len(fake_socket.sent) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("principal", "GPT-PM"),
        ("key_id", "other-key"),
        ("task_id", "other-task"),
        ("slot", "other-slot"),
        ("attempt", 2),
        ("epoch", 8),
        ("run_id", "other-run"),
        ("request_id", "c" * 32),
    ],
    ids=["principal", "key-id", "task-id", "slot", "attempt", "epoch", "run-id", "request-id"],
)
def test_result_binding_rejects_each_mismatched_identity_or_duplicated_field(
    monkeypatch, field, value,
):
    envelope = _envelope()
    result = {**_result(envelope), field: value}
    fake_socket = _Socket(_frame(canonical_bytes({"ok": True, "result": result})))
    _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(DispatchOutcomeUnknown, match="does not match"):
        _client().submit_signed_instruction(envelope)

    assert len(fake_socket.sent) == 1


def test_send_failure_after_submission_begins_is_unknown_and_not_retried(monkeypatch):
    fake_socket = _Socket(send_error=OSError("injected partial-send failure"))
    creations = _patch_socket(monkeypatch, fake_socket)

    with pytest.raises(DispatchOutcomeUnknown, match="do not retry"):
        _client().submit_signed_instruction(_envelope())

    assert len(creations) == 1
    assert len(fake_socket.sent) == 1
    assert fake_socket.closed
