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
    monkeypatch.setattr(service_module.os, "lexists", lambda path: path == service_module.DISPATCH_OWNER_ADMISSION_LATCH_PATH)
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
    monkeypatch.setattr(latch_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(latch_module, "_write_latch", lambda *args: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr(latch_module.subprocess, "run", lambda args, **kwargs: (
        commands.append((args, kwargs)) or SimpleNamespace(returncode=0)
    ))

    with pytest.raises(RuntimeError, match="could not be durably fenced"):
        latch_module.main()

    assert len(commands) == 1
    args, kwargs = commands[0]
    assert args == [latch_module.SYSTEMCTL_PATH, "--no-block", "stop", "vst-dispatch-owner.socket"]
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 10


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
