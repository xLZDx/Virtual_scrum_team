"""Acceptance tests for S2 admission fencing after an ambiguous relay outcome."""
from __future__ import annotations

import json
import os
import stat
from types import SimpleNamespace

import pytest

from tools.vst.contracts import ContractError
from tools.vst import dispatch_owner_latch as latch_module
from tools.vst import dispatch_owner_service as service_module


def test_s2_dispatch_owner_loader_refuses_existing_admission_latch(monkeypatch):
    reads = []
    monkeypatch.setattr(
        service_module.os.path, "lexists",
        lambda path: path == service_module.DISPATCH_OWNER_ADMISSION_LATCH_PATH,
    )
    monkeypatch.setattr(service_module, "_read_root_json", lambda *args, **kwargs: reads.append(args))

    with pytest.raises(ContractError, match="admission is blocked pending reconciliation"):
        service_module.load_dispatch_owner_config()

    assert reads == []


def test_s2_admission_latch_creation_is_exclusive_durable_root_root_and_0644(monkeypatch):
    events = []
    descriptors = iter((31, 32))

    def fake_stat(path, *, follow_symlinks=True):
        events.append(("stat", path, follow_symlinks))
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0, st_gid=0)

    def fake_open(path, flags, *args):
        fd = next(descriptors)
        events.append(("open", path, flags, args, fd))
        return fd

    def fake_write(fd, payload):
        events.append(("write", fd, bytes(payload)))
        return len(payload)

    monkeypatch.setattr(latch_module.os, "stat", fake_stat)
    monkeypatch.setattr(latch_module.os, "open", fake_open)
    monkeypatch.setattr(latch_module.os, "fchown", lambda fd, uid, gid: events.append(("fchown", fd, uid, gid)))
    monkeypatch.setattr(latch_module.os, "fchmod", lambda fd, mode: events.append(("fchmod", fd, mode)))
    monkeypatch.setattr(latch_module.os, "write", fake_write)
    monkeypatch.setattr(latch_module.os, "fsync", lambda fd: events.append(("fsync", fd)))
    monkeypatch.setattr(latch_module.os, "close", lambda fd: events.append(("close", fd)))

    latch_module._write_latch("timeout", "exited", "75")

    latch_open = next(event for event in events if event[0] == "open" and event[1] == latch_module.LATCH_PATH)
    assert latch_open[2] & os.O_CREAT
    assert latch_open[2] & os.O_EXCL
    assert latch_open[2] & getattr(os, "O_NOFOLLOW", 0)
    assert latch_open[3] == (0o644,)
    assert ("fchown", latch_open[4], 0, 0) in events
    assert ("fchmod", latch_open[4], 0o644) in events
    payload = next(event[2] for event in events if event[0] == "write" and event[1] == latch_open[4])
    assert json.loads(payload) == {
        "exit_code": "exited",
        "exit_status": "75",
        "service_result": "timeout",
        "state": "BLOCKED",
        "unit": "vst-dispatch-owner.service",
        "version": 1,
    }
    fsyncs = [event[1] for event in events if event[0] == "fsync"]
    assert fsyncs == [latch_open[4], 32]
    assert ("close", latch_open[4]) in events
    assert ("close", 32) in events


def test_s2_latch_main_requires_root_before_persistence_or_socket_stop(monkeypatch):
    calls = []
    monkeypatch.setattr(latch_module.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(latch_module, "_write_latch", lambda *args: calls.append(args))
    monkeypatch.setattr(latch_module.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    with pytest.raises(RuntimeError, match="requires root"):
        latch_module.main()

    assert calls == []


def test_s2_latch_main_stops_dispatch_socket_even_when_persistence_fails(monkeypatch):
    commands = []
    results = iter((
        SimpleNamespace(returncode=0, stdout=""),
        SimpleNamespace(returncode=0, stdout="inactive\n"),
    ))
    monkeypatch.setattr(latch_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(latch_module, "_write_latch", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(latch_module.subprocess, "run", lambda args, **kwargs: (
        commands.append((args, kwargs)) or next(results)
    ))

    with pytest.raises(RuntimeError, match="could not be durably fenced"):
        latch_module.main()

    assert [entry[0] for entry in commands] == [
        [latch_module.SYSTEMCTL_PATH, "stop", latch_module.SOCKET_UNIT],
        [latch_module.SYSTEMCTL_PATH, "show", "--property=ActiveState", "--value", latch_module.SOCKET_UNIT],
    ]
    assert all("--no-block" not in args for args, _kwargs in commands)
    assert all(kwargs["check"] is False for _args, kwargs in commands)
    assert all(kwargs["timeout"] == latch_module.SYSTEMCTL_TIMEOUT_SECONDS for _args, kwargs in commands)


def test_s2_socket_shutdown_retries_until_stop_and_inactive_state_are_confirmed(monkeypatch):
    commands = []
    sleeps = []
    results = iter((
        SimpleNamespace(returncode=1, stdout=""),
        SimpleNamespace(returncode=0, stdout="active\n"),
        SimpleNamespace(returncode=0, stdout=""),
        SimpleNamespace(returncode=0, stdout="inactive\n"),
    ))
    monkeypatch.setattr(latch_module.subprocess, "run", lambda args, **kwargs: (
        commands.append((args, kwargs)) or next(results)
    ))
    monkeypatch.setattr(latch_module.time, "sleep", sleeps.append)

    latch_module._stop_socket_and_confirm_inactive()

    assert [args[1] for args, _kwargs in commands] == ["stop", "show", "stop", "show"]
    assert all("--no-block" not in args for args, _kwargs in commands)
    assert all(kwargs["timeout"] == latch_module.SYSTEMCTL_TIMEOUT_SECONDS for _args, kwargs in commands)
    assert sleeps == [latch_module.SOCKET_STOP_RETRY_INITIAL_SECONDS]


def test_s2_latch_main_confirms_socket_off_before_touching_persistent_latch(monkeypatch):
    events = []
    results = iter((
        SimpleNamespace(returncode=0, stdout=""),
        SimpleNamespace(returncode=0, stdout="inactive\n"),
    ))
    monkeypatch.setattr(latch_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(latch_module.subprocess, "run", lambda args, **kwargs: (
        events.append(("systemctl", args)) or next(results)
    ))
    monkeypatch.setattr(latch_module, "_write_latch", lambda *args: events.append(("write_latch", args)))

    latch_module.main()

    assert [event[0] for event in events] == ["systemctl", "systemctl", "write_latch"]
    assert events[0][1][1] == "stop"
    assert events[1][1][1] == "show"


def test_s2_dispatch_owner_systemd_units_share_latch_condition_and_exec_stop_post():
    from pathlib import Path

    latch = service_module.DISPATCH_OWNER_ADMISSION_LATCH_PATH
    service = Path("tools/vst/systemd/vst-dispatch-owner.service").read_text(encoding="utf-8")
    socket_unit = Path("tools/vst/systemd/vst-dispatch-owner.socket").read_text(encoding="utf-8")

    condition = f"ConditionPathExists=!{latch}"
    assert condition in service
    assert condition in socket_unit
    assert "ExecStopPost=+" in service
    assert "tools.vst.dispatch_owner_latch import main; main()" in service
    assert "TimeoutStopSec=infinity" in service
