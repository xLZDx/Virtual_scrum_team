"""Acceptance tests for the isolated S2 signed dispatch-owner service contract."""
from __future__ import annotations

import json
import hashlib
import os
import socket
import struct
import stat
from io import StringIO

import pytest

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst import dispatch_owner_service as service_module


_HEADER = struct.Struct("!I")


def _fields() -> dict:
    return {
        "request_id": "a" * 32,
        "task_id": "task-owner-service",
        "slot": "tests",
        "attempt": 1,
        "epoch": 7,
        "run_id": "run-owner-service",
    }


def _service(keypair, supervisor):
    config = service_module.DispatchOwnerServiceConfig(
        principal="Codex", openssl_path=keypair.openssl_path,
        trust_registry=keypair.trust_registry,
    )
    return service_module.DispatchOwnerService(config, supervisor=supervisor)


def _exchange(service, raw: bytes, *, half_close: bool = True, include_status: bool = False):
    """Send one framed request through the actual service socket handler."""
    server, client = socket.socketpair()
    try:
        client.sendall(raw)
        if half_close:
            client.shutdown(socket.SHUT_WR)
        outcome_unknown = service._handle(server)
        header = client.recv(_HEADER.size)
        assert len(header) == _HEADER.size
        size = _HEADER.unpack(header)[0]
        response = bytearray()
        while len(response) < size:
            chunk = client.recv(size - len(response))
            assert chunk
            response.extend(chunk)
        decoded = json.loads(response)
        return (decoded, outcome_unknown) if include_status else decoded
    finally:
        server.close()
        client.close()


def _frame(payload: bytes) -> bytes:
    return _HEADER.pack(len(payload)) + payload


class _Supervisor:
    def __init__(self, *, result=None, error=None, ack_error=None, replay_result=None):
        self.calls = []
        self.replay_calls = []
        self.ack_calls = []
        self.result = result
        self.error = error
        self.ack_error = ack_error
        self.replay_result = replay_result

    def submit_dispatch_intent(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result

    def ack_dispatch_intent(self, **kwargs):
        self.ack_calls.append(kwargs)
        if self.ack_error is not None:
            raise self.ack_error
        return kwargs

    def replay_dispatch_outcome(self, **kwargs):
        self.replay_calls.append(kwargs)
        return self.replay_result


def _bound_result(envelope, key_id):
    return {
        "instruction": envelope,
        "key_id": key_id,
        "principal": "Codex",
        "event_seq": 7,
        "payload_digest": "a" * 64,
        "service_generation": "generation-test",
        **{name: envelope[name] for name in (
            "request_id", "task_id", "slot", "attempt", "epoch", "run_id",
        )},
    }


def test_s2_owner_service_accepts_only_one_bounded_canonical_instruction_frame(
    dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    supervisor = _Supervisor(result=_bound_result(envelope, keypair.key_id))
    service = _service(keypair, supervisor)
    payload = canonical_bytes({"instruction": envelope})

    response = _exchange(service, _frame(payload))

    assert response == {"ok": True, "result": _bound_result(envelope, keypair.key_id)}
    assert supervisor.calls == [{"instruction": envelope}]
    result = _bound_result(envelope, keypair.key_id)
    assert supervisor.ack_calls == [{
        "request_id": result["request_id"],
        "payload_digest": result["payload_digest"],
        "event_seq": result["event_seq"],
        "result_sha256": hashlib.sha256(canonical_bytes(result)).hexdigest(),
        "service_generation": result["service_generation"],
    }]
    assert len(payload) <= service_module.MAX_REQUEST_BYTES


def test_relay_does_not_ack_when_local_response_forwarding_fails(dispatch_instruction_keypair):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    supervisor = _Supervisor(result=_bound_result(envelope, keypair.key_id))
    service = _service(keypair, supervisor)
    server, client = socket.socketpair()
    client.sendall(_frame(canonical_bytes({"instruction": envelope})))
    client.shutdown(socket.SHUT_WR)

    class FailingSend:
        def settimeout(self, timeout):
            server.settimeout(timeout)

        def recv(self, size):
            return server.recv(size)

        def sendall(self, _data):
            raise OSError("injected local forwarding failure")

    try:
        assert service._handle(FailingSend()) is True
        assert len(supervisor.calls) == 1
        assert supervisor.ack_calls == []
    finally:
        server.close()
        client.close()


def test_wrong_supervisor_result_principal_is_unknown_not_forwarded_or_acked(
    dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    result = {**_bound_result(envelope, keypair.key_id), "principal": "GPT-PM"}
    supervisor = _Supervisor(result=result)
    service = _service(keypair, supervisor)

    response, outcome_unknown = _exchange(
        service,
        _frame(canonical_bytes({"instruction": envelope})),
        include_status=True,
    )

    assert response == {"ok": False, "error": "reconciliation_required"}
    assert outcome_unknown is True
    assert supervisor.calls == [{"instruction": envelope}]
    assert supervisor.replay_calls == [{"instruction": envelope}]
    assert supervisor.ack_calls == []


@pytest.mark.parametrize("invalidity", ["expired", "revoked"])
def test_relay_recovers_expired_or_revoked_previously_accepted_result(
    dispatch_instruction_keypair, invalidity,
):
    keypair = dispatch_instruction_keypair
    if invalidity == "expired":
        envelope = keypair.sign(_fields(), expires_at="2000-01-01T00:00:00Z")
        registry = keypair.trust_registry
    else:
        envelope = keypair.sign(_fields())
        registry = {}
    historical_result = _bound_result(envelope, keypair.key_id)
    supervisor = _Supervisor(replay_result=historical_result)
    config = service_module.DispatchOwnerServiceConfig(
        principal="Codex", openssl_path=keypair.openssl_path,
        trust_registry=registry,
    )
    service = service_module.DispatchOwnerService(config, supervisor=supervisor)

    response, outcome_unknown = _exchange(
        service,
        _frame(canonical_bytes({"instruction": envelope})),
        include_status=True,
    )

    assert response == {"ok": True, "result": historical_result}
    assert outcome_unknown is False
    assert supervisor.calls == []
    assert supervisor.replay_calls == [{"instruction": envelope}]
    assert supervisor.ack_calls == [{
        "request_id": historical_result["request_id"],
        "payload_digest": historical_result["payload_digest"],
        "event_seq": historical_result["event_seq"],
        "result_sha256": hashlib.sha256(canonical_bytes(historical_result)).hexdigest(),
        "service_generation": historical_result["service_generation"],
    }]


@pytest.mark.parametrize("invalidity", ["expired", "revoked"])
def test_never_accepted_expired_or_revoked_instruction_never_reaches_admission(
    dispatch_instruction_keypair, invalidity,
):
    keypair = dispatch_instruction_keypair
    if invalidity == "expired":
        envelope = keypair.sign(_fields(), expires_at="2000-01-01T00:00:00Z")
        registry = keypair.trust_registry
    else:
        envelope = keypair.sign(_fields())
        registry = {}
    supervisor = _Supervisor()
    config = service_module.DispatchOwnerServiceConfig(
        principal="Codex", openssl_path=keypair.openssl_path,
        trust_registry=registry,
    )
    service = service_module.DispatchOwnerService(config, supervisor=supervisor)

    response, outcome_unknown = _exchange(
        service,
        _frame(canonical_bytes({"instruction": envelope})),
        include_status=True,
    )

    assert response == {"ok": False, "error": "refused"}
    assert outcome_unknown is False
    assert supervisor.calls == []
    assert supervisor.replay_calls == [{"instruction": envelope}]
    assert supervisor.ack_calls == []


def test_s2_owner_service_refuses_trailing_second_frame(dispatch_instruction_keypair):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    supervisor = _Supervisor(result=_bound_result(envelope, keypair.key_id))
    service = _service(keypair, supervisor)
    payload = canonical_bytes({"instruction": envelope})

    response = _exchange(service, _frame(payload) + _frame(canonical_bytes({"instruction": {}})))

    assert response == {"ok": False, "error": "refused"}
    assert supervisor.calls == []


def test_s2_owner_service_refuses_request_without_eof_before_supervisor_rpc(
    monkeypatch, dispatch_instruction_keypair,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    supervisor = _Supervisor(result=_bound_result(envelope, keypair.key_id))
    service = _service(keypair, supervisor)
    monkeypatch.setattr(service_module, "REQUEST_TIMEOUT_SEC", 0.01)

    response = _exchange(
        service, _frame(canonical_bytes({"instruction": envelope})), half_close=False,
    )

    assert response == {"ok": False, "error": "refused"}
    assert supervisor.calls == []


@pytest.mark.parametrize(
    ("wire", "case"),
    [
        (b'{"instruction":{},"instruction":{}}', "duplicate-key"),
        (b'{ "instruction":{} }', "noncanonical-json"),
        (b'{"instruction":{},"extra":1}', "extra-field"),
    ],
    ids=["duplicate-field", "noncanonical-frame", "extra-top-level-field"],
)
def test_s2_owner_service_refuses_duplicate_noncanonical_or_expanded_frames(
    dispatch_instruction_keypair, wire, case,
):
    supervisor = _Supervisor(result={})
    service = _service(dispatch_instruction_keypair, supervisor)

    response = _exchange(service, _frame(wire))

    assert response == {"ok": False, "error": "refused"}, case
    assert supervisor.calls == []


def test_s2_owner_service_refuses_oversized_request_before_read_or_rpc(
    dispatch_instruction_keypair,
):
    supervisor = _Supervisor(result={})
    service = _service(dispatch_instruction_keypair, supervisor)
    raw = _HEADER.pack(service_module.MAX_REQUEST_BYTES + 1)

    response = _exchange(service, raw)

    assert response == {"ok": False, "error": "refused"}
    assert supervisor.calls == []


@pytest.mark.parametrize("wire", [_HEADER.pack(40) + b"{}", b"\x00\x00"])
def test_s2_owner_service_refuses_truncated_header_or_body(
    dispatch_instruction_keypair, wire,
):
    supervisor = _Supervisor(result={})
    service = _service(dispatch_instruction_keypair, supervisor)

    response = _exchange(service, wire)

    assert response == {"ok": False, "error": "refused"}
    assert supervisor.calls == []


@pytest.mark.parametrize(
    "file_metadata",
    [
        {"uid": 99, "gid": 1501, "mode": 0o640, "size": 2},
        {"uid": 0, "gid": 77, "mode": 0o640, "size": 2},
        {"uid": 0, "gid": 1501, "mode": 0o600, "size": 2},
        {"uid": 0, "gid": 1501, "mode": 0o640, "size": 70000},
    ],
    ids=["nonroot-owner", "wrong-group", "wrong-mode", "oversized-file"],
)
def test_s2_owner_service_root_json_reader_enforces_owner_group_mode_and_size(
    monkeypatch, tmp_path, file_metadata,
):
    actual = tmp_path / "actual.json"
    actual.write_text('{"principal":"Codex"}', encoding="utf-8")
    real_open = service_module.os.open
    real_read = service_module.os.read
    real_close = service_module.os.close
    fake_path = "/etc/vst-runner/dispatch-owner-service.json"

    def fake_stat(path, *, follow_symlinks=True):
        assert path.startswith("/")
        return type("Info", (), {
            "st_mode": stat.S_IFDIR | 0o755,
            "st_uid": 0,
            "st_gid": 0,
        })()

    def fake_open(path, flags):
        assert path == fake_path
        assert flags & os.O_NOFOLLOW
        return real_open(str(actual), os.O_RDONLY)

    def fake_fstat(fd):
        return type("Info", (), {
            "st_mode": stat.S_IFREG | file_metadata["mode"],
            "st_uid": file_metadata["uid"],
            "st_gid": file_metadata["gid"],
            "st_size": file_metadata["size"],
        })()

    monkeypatch.setattr(service_module.os, "stat", fake_stat)
    monkeypatch.setattr(service_module.os, "open", fake_open)
    monkeypatch.setattr(service_module.os, "fstat", fake_fstat)
    monkeypatch.setattr(service_module.os, "read", real_read)
    monkeypatch.setattr(service_module.os, "close", real_close)

    with pytest.raises(ContractError, match="owner, mode, or size"):
        service_module._read_root_json(
            fake_path, expected_mode=0o640, expected_gid=1501, max_bytes=65536,
        )


def test_s2_owner_service_root_json_reader_accepts_exact_config_metadata(monkeypatch, tmp_path):
    actual = tmp_path / "actual.json"
    actual.write_text('{"principal":"Codex"}', encoding="utf-8")
    real_open = service_module.os.open
    real_read = service_module.os.read
    real_close = service_module.os.close
    fake_path = "/etc/vst-runner/dispatch-owner-service.json"

    def fake_stat(path, *, follow_symlinks=True):
        return type("Info", (), {
            "st_mode": stat.S_IFDIR | 0o755, "st_uid": 0, "st_gid": 0,
        })()

    monkeypatch.setattr(service_module.os, "stat", fake_stat)
    monkeypatch.setattr(service_module.os, "open", lambda path, flags: real_open(str(actual), os.O_RDONLY))
    monkeypatch.setattr(service_module.os, "fstat", lambda fd: type("Info", (), {
        "st_mode": stat.S_IFREG | 0o640, "st_uid": 0, "st_gid": 1501, "st_size": 21,
    })())
    monkeypatch.setattr(service_module.os, "read", real_read)
    monkeypatch.setattr(service_module.os, "close", real_close)

    assert service_module._read_root_json(
        fake_path, expected_mode=0o640, expected_gid=1501, max_bytes=65536,
    ) == {"principal": "Codex"}


def test_s2_owner_service_loader_uses_fixed_shared_registry_path_and_permissions(
    monkeypatch,
):
    registry = {"test-key": {
        "principal": "Codex", "purpose": service_module.DISPATCH_INSTRUCTION_PURPOSE,
        "public_key_path": "/etc/vst-runner/test-public.pem",
    }}
    calls = []
    monkeypatch.setattr(service_module.os.path, "lexists", lambda path: False)
    monkeypatch.setattr(service_module.os, "geteuid", lambda: 1500)
    monkeypatch.setattr(service_module.os, "getgid", lambda: 1501)
    monkeypatch.setattr(service_module, "_validate_trust_registry", lambda value: None)
    import builtins
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/self/cgroup":
            return StringIO("0::/system.slice/vst-dispatch-owner.service\n")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    def read_root_json(path, *, expected_mode, expected_gid, max_bytes):
        calls.append((path, expected_mode, expected_gid, max_bytes))
        return registry if path == service_module.TRUST_REGISTRY_PATH else {
            "principal": "Codex", "openssl_path": "/usr/bin/openssl",
        }

    monkeypatch.setattr(service_module, "_read_root_json", read_root_json)

    loaded = service_module.load_dispatch_owner_config()

    assert loaded.trust_registry == registry
    assert calls == [
        (service_module.DEFAULT_CONFIG_PATH, 0o640, 1501, 65536),
        (service_module.TRUST_REGISTRY_PATH, 0o644, 0, 65536),
    ]
    assert service_module.TRUST_REGISTRY_PATH == "/etc/vst-runner/dispatch-instruction-trust.json"


def _supervisor_service_schema_candidate():
    from tools.vst import supervisor_service

    path_fields = {
        "store_path", "anchor_path", "event_key_path", "startup_supervisor_key_path",
        "execution_grant_private_key_path", "operator_key_path",
        "preflight_record_path", "openssl_path", "generation_record_path",
        "dispatch_instruction_trust_registry_path", "runner_lock_path", "systemctl_path",
        "socket_path",
    }
    config = {key: "/tmp/placeholder" for key in path_fields}
    config.update({
        "allow_schema_upgrade": False,
        "execution_grant_key_id": "grant-test",
        "execution_grant_trust_keys": {"grant-test": "/tmp/grant-public.pem"},
        "execution_grant_audience": "gpt-6-luna",
        "runner_unit_name": "vst-runner.service",
        "runner_control_group": "/system.slice/vst-runner.service",
        "runner_lock_path": "/run/vst-runner/cgroup-admission.lock",
        "systemctl_path": "/usr/bin/systemctl",
        "dispatch_instruction_trust_registry_path": "/tmp/unshared-registry.json",
        "run_id": "run-test",
        "probe_nonce": "nonce-test",
        "model_provenance": {"gpt-6-luna": "a" * 64},
        "socket_gid": 1200,
        "peers": [
            {
                "role": "dispatch_owner", "uid": 1200, "gid": 1200,
                "cgroup": "/system.slice/vst-dispatch-owner.service",
                "operations": [
                    "submit_dispatch_intent", "replay_dispatch_outcome", "ack_dispatch_intent",
                ], "principal": "Codex",
            },
            {
                "role": "dispatcher", "uid": 1201, "gid": 1202,
                "cgroup": "/system.slice/vst-dispatcher.service",
                "operations": ["issue_dispatch_grant", "next_dispatch_intent"],
            },
            {
                "role": "runnerd", "uid": 997, "gid": 988,
                "cgroup": "/system.slice/vst-runner.service",
                "operations": [
                    "claim", "claim_status", "reserve", "complete", "generation",
                    "recover", "manifest", "previous_receipt", "no_execution",
                ],
            },
            {
                "role": "signer", "uid": 998, "gid": 988,
                "cgroup": "/system.slice/vst-signer.service",
                "operations": ["generation", "pending"],
            },
        ],
    })
    return supervisor_service, config


def test_s2_supervisor_service_requires_fixed_shared_trust_registry_path(monkeypatch):
    supervisor_service, config = _supervisor_service_schema_candidate()
    monkeypatch.setattr(supervisor_service, "_read_controlled_json", lambda *args, **kwargs: config)
    monkeypatch.setattr("tools.vst.execution_grant._trusted_root_file", lambda *args, **kwargs: None)

    with pytest.raises(ContractError, match="registry path is not fixed"):
        supervisor_service.load_supervisor_service()


def test_s2_supervisor_service_rejects_removed_probe_key_path(monkeypatch):
    supervisor_service, config = _supervisor_service_schema_candidate()
    config["probe_key_path"] = "/etc/vst-runner/removed-probe-key"
    monkeypatch.setattr(supervisor_service, "_read_controlled_json", lambda *args, **kwargs: config)

    with pytest.raises(ContractError, match="config fields do not match its schema"):
        supervisor_service.load_supervisor_service()


@pytest.mark.parametrize(
    "bad_config",
    [
        {"principal": "Codex", "openssl_path": "/usr/bin/openssl", "extra": True},
        {"principal": "Operator", "openssl_path": "/usr/bin/openssl"},
        {"principal": "Codex", "openssl_path": "/usr/bin/not-openssl"},
    ],
    ids=["unexpected-field", "principal-drift", "openssl-path-drift"],
)
def test_s2_owner_service_config_enforces_exact_fixed_schema(monkeypatch, bad_config):
    monkeypatch.setattr(service_module.os.path, "lexists", lambda path: False)
    monkeypatch.setattr(service_module.os, "geteuid", lambda: 1500)
    monkeypatch.setattr(service_module.os, "getgid", lambda: 1501)
    monkeypatch.setattr(service_module, "_read_root_json", lambda *args, **kwargs: bad_config)
    import builtins
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/self/cgroup":
            return StringIO("0::/system.slice/vst-dispatch-owner.service\n")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    with pytest.raises(ContractError, match="fixed schema|fixed trust boundary"):
        service_module.load_dispatch_owner_config()


@pytest.mark.parametrize(
    "registry",
    [
        {},
        {"bad key": {"principal": "Codex", "purpose": service_module.DISPATCH_INSTRUCTION_PURPOSE,
                     "public_key_path": "/etc/vst-runner/key.pem"}},
        {"key": {"principal": "GPT-PM", "purpose": service_module.DISPATCH_INSTRUCTION_PURPOSE,
                 "public_key_path": "/etc/vst-runner/key.pem"}},
        {"key": {"principal": "Codex", "purpose": "other", "public_key_path": "/etc/vst-runner/key.pem"}},
        {"key": {"principal": "Codex", "purpose": service_module.DISPATCH_INSTRUCTION_PURPOSE,
                 "public_key_path": "relative.pem"}},
        {"key": {"principal": "Codex", "purpose": service_module.DISPATCH_INSTRUCTION_PURPOSE,
                 "public_key_path": "/etc/vst-runner/key.pem", "extra": True}},
    ],
    ids=["empty", "invalid-key-id", "wrong-principal", "wrong-purpose", "relative-key-path", "extra-entry-field"],
)
def test_s2_owner_service_trust_registry_enforces_exact_shared_schema(
    monkeypatch, registry,
):
    paths = []
    monkeypatch.setattr(service_module, "_validate_root_public_key", paths.append)

    if registry and next(iter(registry.values())).get("public_key_path") == "/etc/vst-runner/key.pem" and set(next(iter(registry.values()))) == {"principal", "purpose", "public_key_path"} and next(iter(registry.values())).get("principal") == "Codex" and next(iter(registry.values())).get("purpose") == service_module.DISPATCH_INSTRUCTION_PURPOSE and next(iter(registry)) == "key":
        service_module._validate_trust_registry(registry)
        assert paths == ["/etc/vst-runner/key.pem"]
    else:
        with pytest.raises(ContractError):
            service_module._validate_trust_registry(registry)
        assert paths == []


@pytest.mark.parametrize(
    "metadata",
    [
        {"uid": 0, "gid": 0, "mode": 0o644, "regular": True},
        {"uid": 1, "gid": 0, "mode": 0o644},
        {"uid": 0, "gid": 1, "mode": 0o644},
        {"uid": 0, "gid": 0, "mode": 0o600},
        {"uid": 0, "gid": 0, "mode": 0o644, "regular": False},
    ],
    ids=[
        "root-owned-group-mode-accepted", "nonroot-key-owner", "wrong-key-group",
        "unsafe-key-mode", "key-not-regular",
    ],
)
def test_s2_owner_service_public_key_requires_root_owner_group_and_mode(
    monkeypatch, metadata,
):
    def fake_stat(path, *, follow_symlinks=True):
        if path == "/etc/vst-runner/key.pem":
            mode = stat.S_IFREG if metadata.get("regular", True) else stat.S_IFDIR
            mode |= metadata["mode"]
            return type("Info", (), {
                "st_mode": mode, "st_uid": metadata["uid"], "st_gid": metadata["gid"],
                "st_size": 32,
            })()
        return type("Info", (), {"st_mode": stat.S_IFDIR | 0o755, "st_uid": 0, "st_gid": 0})()

    monkeypatch.setattr(service_module.os, "stat", fake_stat)
    monkeypatch.setattr(service_module.os, "open", lambda path, flags: 13)
    monkeypatch.setattr(service_module.os, "fstat", lambda fd: type("Info", (), {
        "st_mode": (stat.S_IFREG if metadata.get("regular", True) else stat.S_IFDIR)
        | metadata["mode"], "st_uid": metadata["uid"],
        "st_gid": metadata["gid"], "st_size": 32,
    })())
    monkeypatch.setattr(service_module.os, "close", lambda fd: None)

    if metadata.get("uid") != 0 or metadata.get("gid") != 0 or metadata.get("mode") != 0o644 or not metadata.get("regular", True):
        with pytest.raises(ContractError, match="owner, mode, or size"):
            service_module._validate_root_public_key("/etc/vst-runner/key.pem")
    else:
        service_module._validate_root_public_key("/etc/vst-runner/key.pem")


@pytest.mark.parametrize(
    "env",
    [
        {"LISTEN_PID": "0", "LISTEN_FDS": "1", "LISTEN_FDNAMES": "dispatch-owner"},
        {"LISTEN_PID": "123", "LISTEN_FDS": "2", "LISTEN_FDNAMES": "dispatch-owner"},
        {"LISTEN_PID": "123", "LISTEN_FDS": "1", "LISTEN_FDNAMES": "wrong"},
    ],
    ids=["wrong-activation-pid", "extra-activation-fd", "wrong-activation-name"],
)
def test_s2_owner_service_rejects_untrusted_systemd_activation_descriptor(
    monkeypatch, env,
):
    monkeypatch.setattr(service_module.os, "getpid", lambda: 123)
    for name in ("LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ContractError, match="systemd socket activation"):
        service_module._systemd_listener()


def test_s2_owner_service_adopts_only_named_systemd_fd_three(monkeypatch):
    monkeypatch.setattr(service_module.os, "getpid", lambda: 123)
    monkeypatch.setenv("LISTEN_PID", "123")
    monkeypatch.setenv("LISTEN_FDS", "1")
    monkeypatch.setenv("LISTEN_FDNAMES", "dispatch-owner")
    observed = {}

    class ActivatedSocket:
        def __init__(self, *, fileno):
            observed["fd"] = fileno

        def set_inheritable(self, value):
            observed["inheritable"] = value

    monkeypatch.setattr(service_module.socket, "socket", ActivatedSocket)

    listener = service_module._systemd_listener()

    assert isinstance(listener, ActivatedSocket)
    assert observed == {"fd": 3, "inheritable": False}
    assert all(name not in service_module.os.environ for name in (
        "LISTEN_PID", "LISTEN_FDS", "LISTEN_FDNAMES",
    ))


def test_s2_owner_service_rejects_wrong_or_untrusted_cgroup(monkeypatch):
    monkeypatch.setattr(service_module.os.path, "lexists", lambda path: False)
    monkeypatch.setattr(service_module.os, "geteuid", lambda: 1500)
    monkeypatch.setattr(service_module.os, "getgid", lambda: 1501)
    monkeypatch.setattr(service_module, "_read_root_json", lambda *args, **kwargs: {})
    import builtins
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if path == "/proc/self/cgroup":
            return StringIO("0::/system.slice/unrelated.service\n")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    with pytest.raises(ContractError, match="fixed systemd cgroup"):
        service_module.load_dispatch_owner_config()


@pytest.mark.parametrize("path", ["relative.sock", "/tmp/attacker.sock"])
def test_s2_owner_service_rejects_nonfixed_activation_socket_path(
    dispatch_instruction_keypair, path,
):
    class Listener:
        family = socket.AF_UNIX

        def getsockopt(self, level, option):
            if option == socket.SO_TYPE:
                return socket.SOCK_STREAM
            return 1

        def getsockname(self):
            return path

    service = _service(dispatch_instruction_keypair, _Supervisor(result={}))
    with pytest.raises(ContractError, match="fixed local listener"):
        service.serve_forever(Listener())


@pytest.mark.parametrize(
    ("family", "socktype", "accepting"),
    [
        (socket.AF_INET, socket.SOCK_STREAM, 1),
        (socket.AF_UNIX, socket.SOCK_DGRAM, 1),
        (socket.AF_UNIX, socket.SOCK_STREAM, 0),
    ],
    ids=["non-unix-fd", "non-stream-fd", "not-listening-fd"],
)
def test_s2_owner_service_rejects_wrong_systemd_listener_fd(
    dispatch_instruction_keypair, family, socktype, accepting,
):
    class Listener:
        def getsockopt(self, level, option):
            return socktype if option == socket.SO_TYPE else accepting

        def getsockname(self):
            return service_module.OWNER_SOCKET_PATH

    listener = Listener()
    listener.family = family
    service = _service(dispatch_instruction_keypair, _Supervisor(result={}))
    with pytest.raises(ContractError, match="fixed local listener"):
        service.serve_forever(listener)


@pytest.mark.parametrize(
    "invalid",
    ["bad-signature", "expired", "wrong-principal", "revoked-key", "malformed"],
    ids=["signature", "expired-instruction", "wrong-principal", "revoked-key", "malformed-envelope"],
)
def test_s2_owner_service_refuses_invalid_instruction_before_supervisor_rpc(
    dispatch_instruction_keypair, invalid,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    registry = {key: dict(value) for key, value in keypair.trust_registry.items()}
    if invalid == "bad-signature":
        envelope = {**envelope, "signature": "A" * len(envelope["signature"])}
    elif invalid == "expired":
        from datetime import datetime, timedelta, timezone
        past = (datetime.now(timezone.utc) - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        envelope = keypair.sign(_fields(), expires_at=past)
    elif invalid == "wrong-principal":
        registry[keypair.key_id]["principal"] = "GPT-PM"
    elif invalid == "revoked-key":
        registry = {}
    elif invalid == "malformed":
        envelope = {**envelope, "worker": "vst-worker"}
    supervisor = _Supervisor(result=_bound_result(envelope, keypair.key_id))
    config = service_module.DispatchOwnerServiceConfig(
        principal="Codex", openssl_path=keypair.openssl_path,
        trust_registry=registry,
    )
    service = service_module.DispatchOwnerService(config, supervisor=supervisor)
    wire = _frame(canonical_bytes({"instruction": envelope}))

    response = _exchange(service, wire)

    assert response == {"ok": False, "error": "refused"}
    assert supervisor.calls == []


@pytest.mark.parametrize(
    "outcome",
    ["timeout", "explicit-error", "malformed-result", "response-binding-mismatch"],
    ids=["timeout", "explicit-error", "malformed-result", "response-binding-mismatch"],
)
def test_s2_owner_service_requires_reconciliation_after_ambiguous_supervisor_outcome(
    dispatch_instruction_keypair, outcome,
):
    keypair = dispatch_instruction_keypair
    envelope = keypair.sign(_fields())
    if outcome == "timeout":
        supervisor = _Supervisor(error=TimeoutError("response lost after possible acceptance"))
    elif outcome == "explicit-error":
        supervisor = _Supervisor(error=RuntimeError("Supervisor rejected after dispatch"))
    elif outcome == "malformed-result":
        supervisor = _Supervisor(result={"unexpected": True})
    else:
        wrong = {**envelope, "task_id": "different-task"}
        supervisor = _Supervisor(result=_bound_result(wrong, keypair.key_id))
    service = _service(keypair, supervisor)
    server_conn, client_conn = socket.socketpair()
    queued_server_conn, queued_client_conn = socket.socketpair()
    wire = _frame(canonical_bytes({"instruction": envelope}))
    client_conn.sendall(wire)
    client_conn.shutdown(socket.SHUT_WR)
    queued_client_conn.sendall(wire)
    queued_client_conn.shutdown(socket.SHUT_WR)

    class Listener:
        family = socket.AF_UNIX

        def __init__(self):
            self.accept_count = 0
            self.pending = [(server_conn, None), (queued_server_conn, None)]

        def getsockopt(self, level, option):
            return socket.SOCK_STREAM if option == socket.SO_TYPE else 1

        def getsockname(self):
            return service_module.OWNER_SOCKET_PATH

        def settimeout(self, timeout):
            pass

        def accept(self):
            self.accept_count += 1
            return self.pending.pop(0)

    listener = Listener()
    try:
        service.serve_forever(listener)
        header = client_conn.recv(_HEADER.size)
        assert len(header) == _HEADER.size
        size = _HEADER.unpack(header)[0]
        response_bytes = bytearray()
        while len(response_bytes) < size:
            chunk = client_conn.recv(size - len(response_bytes))
            assert chunk
            response_bytes.extend(chunk)
        response = json.loads(response_bytes)
        queued_client_conn.settimeout(0.01)
        with pytest.raises(socket.timeout):
            queued_client_conn.recv(1)
    finally:
        server_conn.close()
        client_conn.close()
        queued_server_conn.close()
        queued_client_conn.close()

    assert response == {"ok": False, "error": "reconciliation_required"}
    assert supervisor.calls == [{"instruction": envelope}]
    assert listener.accept_count == 1
    assert service._shutdown.is_set()

