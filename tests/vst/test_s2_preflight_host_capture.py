"""Synthetic fail-closed coverage for the one-shot S2 root probe wrapper.

These tests exercise local contract logic only; they are not runtime evidence.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import hashlib
import stat
from types import SimpleNamespace

import pytest

from tools.vst import preflight_host_capture as capture
from tools.vst.contracts import ContractError


def _result(stdout: str = "", *, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, "")


def _unit(*, active: str = "inactive", pid: str = "0", invocation: str = "",
          result: str = "success") -> dict[str, str]:
    return {
        "LoadState": "loaded", "ActiveState": active,
        "SubState": "start" if active == "activating" else "dead",
        "Result": result, "MainPID": pid, "InvocationID": invocation,
        "ControlGroup": "/system.slice/vst-sandbox-probe.service",
        "PrivateNetwork": "yes",
    }


def test_typed_systemd_unit_argument_rejects_shell_fragment_before_execution() -> None:
    calls: list[list[str]] = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return _result()

    with pytest.raises(ContractError, match="unit name"):
        capture._systemctl_show("vst-probe.service; poweroff", run=run)
    assert calls == []


def test_socket_unit_properties_accept_systemd_omitting_main_pid() -> None:
    properties = _unit()
    properties.pop("MainPID")
    properties["PrivateNetwork"] = "no"

    def run(_argv, **_kwargs):
        return _result("".join(f"{key}={value}\n" for key, value in properties.items()))

    assert capture._systemctl_show("vst-dispatch-owner.socket", run=run) == properties


def test_service_unit_still_requires_main_pid_property() -> None:
    properties = _unit()
    properties.pop("MainPID")

    def run(_argv, **_kwargs):
        return _result("".join(f"{key}={value}\n" for key, value in properties.items()))

    with pytest.raises(ContractError, match="properties are incomplete"):
        capture._systemctl_show("vst-sandbox-probe.service", run=run)


def test_socket_unit_still_requires_other_requested_properties() -> None:
    properties = _unit()
    properties.pop("MainPID")
    properties.pop("PrivateNetwork")

    def run(_argv, **_kwargs):
        return _result("".join(f"{key}={value}\n" for key, value in properties.items()))

    with pytest.raises(ContractError, match="properties are incomplete"):
        capture._systemctl_show("vst-dispatch-owner.socket", run=run)


@pytest.mark.parametrize("state", ["degraded", "stopping", "starting"])
def test_systemd_must_be_fully_running_before_probe_start(monkeypatch, state: str) -> None:
    calls: list[list[str]] = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return _result(state + "\n")

    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)
    with pytest.raises(ContractError, match="not in the running state"):
        capture._systemd_ready(run=run)
    assert len(calls) == 1
    assert calls[0][:3] == [capture.SYSTEMCTL, "is-system-running"]


def test_systemd_pending_unrelated_job_is_rejected(monkeypatch) -> None:
    answers = iter([_result("running\n"), _result("12 unrelated.service start waiting\n")])
    calls = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return next(answers)

    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)
    with pytest.raises(ContractError, match="unexpected pending job"):
        capture._systemd_ready(run=run)
    assert len(calls) == 2


def test_probe_start_job_is_the_only_pending_job_allowed_during_observation(monkeypatch) -> None:
    answers = iter([_result("running\n"), _result("12 vst-sandbox-probe.service start running\n")])
    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)
    monkeypatch.setattr(capture, "_pid1_identity", lambda: {"boot_id": "boot-a"})
    result = capture._systemd_ready(
        run=lambda *_args, **_kwargs: next(answers), allow_probe_start_job=True,
    )
    assert result == {"boot_id": "boot-a"}


def test_probe_start_job_rejects_any_additional_systemd_job(monkeypatch) -> None:
    answers = iter([_result("running\n"), _result(
        "12 vst-sandbox-probe.service start running\n13 unrelated.service stop waiting\n")])
    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)
    with pytest.raises(ContractError, match="unexpected pending job"):
        capture._systemd_ready(run=lambda *_args, **_kwargs: next(answers),
                               allow_probe_start_job=True)


def test_scheduled_shutdown_is_rejected_before_probe_start(monkeypatch) -> None:
    monkeypatch.setattr(capture.os.path, "lexists", lambda path: path == "/run/systemd/shutdown/scheduled")
    answers = iter([_result("running\n"), _result("No jobs running.\n")])
    with pytest.raises(ContractError, match="shutdown is already scheduled"):
        capture._systemd_ready(run=lambda *_args, **_kwargs: next(answers))


def test_recent_shutdown_and_unstable_boot_are_rejected(monkeypatch) -> None:
    original = pathlib.Path

    class FakePath:
        def __init__(self, value): self.value = str(value)
        def read_text(self, *, encoding=None): return "12.5 0.0\n"

    monkeypatch.setattr(capture, "Path", FakePath)
    with pytest.raises(ContractError, match="stable for 60 seconds"):
        capture._assert_no_recent_shutdown(run=lambda *_args, **_kwargs: _result())

    class StablePath:
        def __init__(self, value): self.value = str(value)
        def read_text(self, *, encoding=None): return "120.0 0.0\n"

    monkeypatch.setattr(capture, "Path", StablePath)
    monkeypatch.setattr(capture, "_run", lambda *_args, **_kwargs: _result("The system is powering down\n"))
    with pytest.raises(ContractError, match="recent systemd-logind shutdown"):
        capture._assert_no_recent_shutdown(run=lambda *_args, **_kwargs: _result())


def _map_proc_path(monkeypatch, pid: int, root: pathlib.Path) -> None:
    original = capture.Path

    def mapped(value):
        raw = str(value)
        if raw == "/proc/sys/kernel/osrelease":
            return SimpleNamespace(read_text=lambda *, encoding=None: "6.6.114.1-microsoft-standard-WSL2")
        prefix = f"/proc/{pid}"
        if raw == prefix:
            return root
        if raw.startswith(prefix + "/"):
            return root / raw[len(prefix) + 1:]
        return original(value)

    monkeypatch.setattr(capture, "Path", mapped)


def _write_process_tree(root: pathlib.Path, pid: int = 4242) -> None:
    proc = root
    proc.mkdir(parents=True, exist_ok=True)
    tail = ["S"] + [str(n) for n in range(1, 24)]
    (proc / "stat").write_text(f"{pid} (probe worker) " + " ".join(tail), encoding="ascii")
    (proc / "status").write_text("Name:\tpython3\nUid:\t999\t999\t999\t999\nGid:\t989\t989\t989\t989\n", encoding="ascii")
    (proc / "cgroup").write_text("0::/system.slice/vst-sandbox-probe.service\n", encoding="ascii")
    (proc / "ns/net").mkdir(parents=True)
    (proc / "ns/mnt").mkdir(parents=True)
    (proc / "root").mkdir()
    (proc / "net").mkdir()
    (proc / "net/unix").write_text("Num RefCount Protocol Flags Type St Inode Path\n", encoding="ascii")


def test_process_identity_pins_worker_uid_gid_cgroup_and_namespaces(tmp_path, monkeypatch) -> None:
    pid = 4242
    proc = tmp_path / "proc" / str(pid)
    _write_process_tree(proc, pid)
    _map_proc_path(monkeypatch, pid, proc)
    identity = capture._process_identity(pid)
    assert identity["pid"] == pid
    assert identity["uid"] == [999, 999, 999, 999]
    assert identity["gid"] == [989, 989, 989, 989]
    assert identity["cgroup"] == "/system.slice/vst-sandbox-probe.service"
    assert identity["net_ns_inode"] != identity["mount_ns_inode"]


@pytest.mark.parametrize("pid", [0, 1, -1])
def test_process_identity_rejects_missing_or_pid1(pid: int) -> None:
    with pytest.raises(ContractError, match="MainPID"):
        capture._process_identity(pid)


def test_process_identity_rejects_other_cgroup(tmp_path, monkeypatch) -> None:
    pid = 4242
    proc = tmp_path / "proc" / str(pid)
    _write_process_tree(proc, pid)
    (proc / "cgroup").write_text("0::/system.slice/unrelated.service\n", encoding="ascii")
    _map_proc_path(monkeypatch, pid, proc)
    with pytest.raises(ContractError, match="exact systemd cgroup"):
        capture._process_identity(pid)


@pytest.mark.parametrize("field,index", [(field, index) for field in ("Uid", "Gid") for index in range(4)])
def test_process_identity_rejects_each_unpinned_uid_or_gid_position(
        tmp_path, monkeypatch, field, index) -> None:
    pid = 4242
    proc = tmp_path / "proc" / str(pid)
    _write_process_tree(proc, pid)
    values = ([999] * 4) if field == "Uid" else ([989] * 4)
    values[index] += 1
    lines = (proc / "status").read_text(encoding="ascii").splitlines()
    lines = [f"{field}:\t" + "\t".join(map(str, values)) if line.startswith(field + ":") else line
             for line in lines]
    (proc / "status").write_text("\n".join(lines) + "\n", encoding="ascii")
    _map_proc_path(monkeypatch, pid, proc)
    expected_uid = values if field == "Uid" else [999, 999, 999, 999]
    expected_gid = values if field == "Gid" else [989, 989, 989, 989]
    with pytest.raises(ContractError, match="configured worker") as error:
        capture._process_identity(pid)
    assert f"uid={expected_uid!r}, gid={expected_gid!r}" in str(error.value)
    assert "expected uid=[999, 999, 999, 999], gid=[989, 989, 989, 989]" in str(error.value)


def _probe_identity(*, uid=None, gid=None, start_ticks=9,
                    cgroup="/system.slice/vst-sandbox-probe.service"):
    return {"pid": 123, "start_ticks": start_ticks,
            "uid": uid if uid is not None else [999, 999, 999, 999],
            "gid": gid if gid is not None else [989, 989, 989, 989],
            "net_ns_inode": 33, "mount_ns_inode": 44, "cgroup": cgroup}


def _patch_probe_identity_wait(monkeypatch, identities, *, unit_states=None,
                               generations=None):
    invocation = "a" * 32
    boot = {"boot_id": "boot-a", "pid": 1, "start_ticks": 7,
            "net_ns_inode": 3, "mount_ns_inode": 4}
    clock = [0.0]
    identity_iter = iter(identities)
    unit_iter = iter(unit_states or [])
    generation_iter = iter(generations or [])
    unit_calls = []
    generation_calls = []

    def process(_pid, **_kwargs):
        return next(identity_iter)

    def show(unit_name, **_kwargs):
        unit_calls.append(unit_name)
        if unit_name != capture.PROBE_UNIT:
            return _unit()
        try:
            return next(unit_iter)
        except StopIteration:
            return _unit(active="activating", pid="123", invocation=invocation)

    def generation(**_kwargs):
        generation_calls.append(True)
        try:
            return next(generation_iter)
        except StopIteration:
            return boot

    monkeypatch.setattr(capture, "_process_identity", process)
    monkeypatch.setattr(capture, "_systemctl_show", show)
    monkeypatch.setattr(capture, "_systemd_ready", generation)
    return {"invocation": invocation, "boot": boot, "clock": clock,
            "unit_calls": unit_calls, "generation_calls": generation_calls,
            "sleep": lambda seconds: clock.__setitem__(0, clock[0] + seconds),
            "monotonic": lambda: clock[0]}


def test_wait_for_probe_worker_identity_accepts_only_same_root_to_worker_transition(monkeypatch) -> None:
    state = _patch_probe_identity_wait(monkeypatch, [
        _probe_identity(uid=[0, 0, 0, 0], gid=[0, 0, 0, 0]),
        _probe_identity(),
    ])

    identity = capture._wait_for_probe_worker_identity(
        123, state["invocation"], state["boot"], run=lambda *_a, **_kw: _result(),
        monotonic=state["monotonic"], sleep=state["sleep"])

    assert identity == _probe_identity()
    assert state["clock"][0] == pytest.approx(0.05)
    assert state["unit_calls"] == [capture.PROBE_UNIT, capture.PROBE_UNIT]
    assert state["generation_calls"] == [True, True]


def test_wait_for_probe_worker_identity_fails_closed_when_root_never_settles(monkeypatch) -> None:
    root = _probe_identity(uid=[0, 0, 0, 0], gid=[0, 0, 0, 0])
    state = _patch_probe_identity_wait(monkeypatch, [root] * 200)

    with pytest.raises(ContractError, match="did not settle to the configured worker"):
        capture._wait_for_probe_worker_identity(
            123, state["invocation"], state["boot"], run=lambda *_a, **_kw: _result(),
            monotonic=state["monotonic"], sleep=state["sleep"])

    assert state["clock"][0] == pytest.approx(5.0)
    assert state["generation_calls"]


def test_wait_for_probe_worker_identity_passes_decreasing_nested_command_timeouts(
        monkeypatch) -> None:
    boot = {"boot_id": "boot-a", "pid": 1, "start_ticks": 7,
            "net_ns_inode": 3, "mount_ns_inode": 4}
    invocation = "a" * 32
    identities = iter([
        _probe_identity(uid=[0, 0, 0, 0], gid=[0, 0, 0, 0]),
        _probe_identity(),
    ])
    clock = [0.0]
    command_timeouts = []
    properties = "".join((
        "LoadState=loaded\n", "ActiveState=activating\n", "SubState=start\n",
        "Result=success\n", "MainPID=123\n", f"InvocationID={invocation}\n",
        "ControlGroup=/system.slice/vst-sandbox-probe.service\n",
        "PrivateNetwork=yes\n",
    ))

    def run(argv, *, timeout, **_kwargs):
        command_timeouts.append(timeout)
        clock[0] += 0.1
        if argv[1] == "show":
            stdout = properties
        elif argv[1] == "is-system-running":
            stdout = "running\n"
        else:
            stdout = ""
        return _result(stdout)

    monkeypatch.setattr(capture, "_process_identity", lambda _pid, **_kwargs: next(identities))
    monkeypatch.setattr(capture, "_pid1_identity", lambda: boot)
    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)
    identity = capture._wait_for_probe_worker_identity(
        123, invocation, boot, run=run, monotonic=lambda: clock[0],
        sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    assert identity == _probe_identity()
    assert len(command_timeouts) == 6
    assert all(timeout > 0 for timeout in command_timeouts)
    assert all(later < earlier for earlier, later in zip(command_timeouts, command_timeouts[1:]))


def test_wait_for_probe_worker_identity_fails_closed_when_nested_command_exhausts_deadline(
        monkeypatch) -> None:
    boot = {"boot_id": "boot-a", "pid": 1, "start_ticks": 7,
            "net_ns_inode": 3, "mount_ns_inode": 4}
    clock = [0.0]
    command_timeouts = []

    def run(_argv, *, timeout, **_kwargs):
        command_timeouts.append(timeout)
        clock[0] += timeout
        return _result("LoadState=loaded\nActiveState=activating\nSubState=start\n"
                       "Result=success\nMainPID=123\nInvocationID=" + "a" * 32 + "\n"
                       "ControlGroup=/system.slice/vst-sandbox-probe.service\n"
                       "PrivateNetwork=yes\n")

    root = _probe_identity(uid=[0, 0, 0, 0], gid=[0, 0, 0, 0])
    monkeypatch.setattr(capture, "_process_identity", lambda _pid, **_kwargs: root)
    monkeypatch.setattr(capture, "_pid1_identity", lambda: boot)
    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)

    with pytest.raises(ContractError, match="did not settle before its deadline"):
        capture._wait_for_probe_worker_identity(
            123, "a" * 32, boot, run=run, monotonic=lambda: clock[0], sleep=lambda _seconds: None)

    assert clock[0] == pytest.approx(5.0)
    assert command_timeouts == [5.0]


def test_wait_for_probe_worker_identity_fails_closed_when_worker_validation_exceeds_deadline(
        monkeypatch) -> None:
    boot = {"boot_id": "boot-a", "pid": 1, "start_ticks": 7,
            "net_ns_inode": 3, "mount_ns_inode": 4}
    clock = [0.0]
    command_timeouts = []
    properties = "".join((
        "LoadState=loaded\n", "ActiveState=activating\n", "SubState=start\n",
        "Result=success\n", "MainPID=123\n", f"InvocationID={'a' * 32}\n",
        "ControlGroup=/system.slice/vst-sandbox-probe.service\n",
        "PrivateNetwork=yes\n",
    ))

    def run(argv, *, timeout, **_kwargs):
        command_timeouts.append(timeout)
        elapsed = min(1.7, timeout)
        clock[0] += elapsed
        if argv[1] == "show":
            stdout = properties
        elif argv[1] == "is-system-running":
            stdout = "running\n"
        else:
            stdout = ""
        return _result(stdout)

    def pid1_identity_after_deadline():
        clock[0] += 0.01
        return boot

    worker = _probe_identity()
    monkeypatch.setattr(capture, "_process_identity", lambda _pid, **_kwargs: worker)
    monkeypatch.setattr(capture, "_pid1_identity", pid1_identity_after_deadline)
    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)

    with pytest.raises(ContractError, match="did not settle to the configured worker"):
        capture._wait_for_probe_worker_identity(
            123, "a" * 32, boot, run=run, monotonic=lambda: clock[0], sleep=lambda _seconds: None)

    assert clock[0] == pytest.approx(5.01)
    assert command_timeouts == pytest.approx([5.0, 3.3, 1.6])


@pytest.mark.parametrize("uid,gid", [
    ([1000, 1000, 1000, 1000], [989, 989, 989, 989]),
    ([999, 999, 999, 999], [1000, 1000, 1000, 1000]),
    ([0, 0, 999, 999], [0, 0, 989, 989]),
])
def test_wait_for_probe_worker_identity_rejects_any_other_credentials_immediately(
        monkeypatch, uid, gid) -> None:
    state = _patch_probe_identity_wait(monkeypatch, [_probe_identity(uid=uid, gid=gid)])

    with pytest.raises(ContractError, match="identity differs from the configured worker"):
        capture._wait_for_probe_worker_identity(
            123, state["invocation"], state["boot"], run=lambda *_a, **_kw: _result(),
            monotonic=state["monotonic"], sleep=state["sleep"])

    assert state["clock"][0] == 0
    assert state["unit_calls"] == []


@pytest.mark.parametrize("change", ["start_ticks", "cgroup", "main_pid", "invocation", "boot"])
def test_wait_for_probe_worker_identity_rejects_identity_change_during_transition(
        monkeypatch, change) -> None:
    root = _probe_identity(uid=[0, 0, 0, 0], gid=[0, 0, 0, 0])
    worker = _probe_identity()
    units = []
    generations = []
    if change == "start_ticks":
        worker["start_ticks"] += 1
        error = "PID changed"
    elif change == "cgroup":
        error = "outside its exact systemd cgroup"
    elif change == "main_pid":
        units = [_unit(active="activating", pid="123", invocation="a" * 32),
                 _unit(active="activating", pid="124", invocation="a" * 32)]
        error = "PID, invocation, or systemd generation changed"
    elif change == "invocation":
        units = [_unit(active="activating", pid="123", invocation="a" * 32),
                 _unit(active="activating", pid="123", invocation="b" * 32)]
        error = "PID, invocation, or systemd generation changed"
    else:
        generations = [
            {"boot_id": "boot-a", "pid": 1, "start_ticks": 7,
             "net_ns_inode": 3, "mount_ns_inode": 4},
            {"boot_id": "boot-b", "pid": 1, "start_ticks": 7,
             "net_ns_inode": 3, "mount_ns_inode": 4},
        ]
        error = "PID, invocation, or systemd generation changed"

    identities = [root, worker]
    if change == "cgroup":
        identities = [root]
    state = _patch_probe_identity_wait(monkeypatch, identities,
                                       unit_states=units, generations=generations)
    if change == "cgroup":
        process = iter([root])

        def outside_cgroup(_pid, **_kwargs):
            try:
                return next(process)
            except StopIteration:
                raise ContractError("probe process is outside its exact systemd cgroup")
        monkeypatch.setattr(capture, "_process_identity", outside_cgroup)

    with pytest.raises(ContractError, match=error):
        capture._wait_for_probe_worker_identity(
            123, state["invocation"], state["boot"], run=lambda *_a, **_kw: _result(),
            monotonic=state["monotonic"], sleep=state["sleep"])


def test_network_observation_accepts_only_loopback_addresses_and_routes() -> None:
    responses = [
        json.dumps([{"ifname": "lo", "flags": ["LOOPBACK", "UP"], "addr_info": [
            {"local": "127.0.0.1"}, {"local": "::1"},
        ]}]),
        json.dumps([{"dst": "127.0.0.0/8", "dev": "lo"}]),
        json.dumps([{"dst": "::1/128", "dev": "lo"}]),
    ]
    calls: list[list[str]] = []

    def run(argv, **_kwargs):
        calls.append(argv)
        return _result(responses[len(calls) - 1])

    observed = capture._network_observation(4242, run=run)
    assert len(calls) == 3
    assert all(call[1:5] == ["--target", "4242", "--net", "--"] for call in calls)
    assert observed["addresses"][0]["ifname"] == "lo"


@pytest.mark.parametrize("addresses,routes4,routes6", [
    ([{"ifname": "eth0", "flags": ["UP"], "addr_info": [{"local": "10.0.0.2"}]}], [], []),
    ([{"ifname": "lo", "flags": ["UP"], "addr_info": [{"local": "127.0.0.1"}]}],
     [{"dst": "default", "dev": "eth0", "gateway": "10.0.0.1"}], []),
])
def test_network_observation_rejects_external_interface_or_route(addresses, routes4, routes6) -> None:
    responses = iter([json.dumps(addresses), json.dumps(routes4), json.dumps(routes6)])
    with pytest.raises(ContractError, match="unexpected interface|non-loopback route"):
        capture._network_observation(4242, run=lambda *_args, **_kwargs: _result(next(responses)))


def _mount_line(mount_id: int, target: str, filesystem: str, source: str,
                *, root: str = "/", device: str = "8:1", options: str = "rw") -> str:
    return f"{mount_id} 1 {device} {root} {target} {options} - {filesystem} {source} rw"


def _mount_fixture(tmp_path: pathlib.Path, pid: int, mount_lines: list[str]) -> pathlib.Path:
    proc = tmp_path / "proc" / str(pid)
    proc.mkdir(parents=True)
    (proc / "mountinfo").write_text("\n".join(mount_lines) + "\n", encoding="utf-8")
    (proc / "net").mkdir()
    (proc / "net/unix").write_text("Num RefCount Protocol Flags Type St Inode Path\n", encoding="utf-8")
    (proc / "root").mkdir()
    return proc


def test_mount_inventory_accepts_pinned_root_only_mount(tmp_path, monkeypatch) -> None:
    pid = 4242
    proc = _mount_fixture(tmp_path, pid, [_mount_line(1, "/", "ext4", "/dev/sda")])
    _map_proc_path(monkeypatch, pid, proc)
    result = capture._mount_and_socket_observation(pid)
    assert result["windows_drive_mounts"] == []
    assert result["unapproved_host_mounts"] == []
    assert result["container_socket_paths_present"] == []
    assert result["mount_contract"] == "VST_S2_PROBE_SYSTEMD_ALLOWLIST_V1"


def _observe_mounts_with_kernel_release(tmp_path, monkeypatch, mount_lines: list[str]) -> dict:
    pid = 4242
    proc = _mount_fixture(tmp_path, pid, mount_lines)
    _map_proc_path(monkeypatch, pid, proc)
    return capture._mount_and_socket_observation(pid)


def test_mount_inventory_accepts_exact_read_only_wsl_modules_overlay(tmp_path, monkeypatch) -> None:
    kernel_release = "6.6.114.1-microsoft-standard-WSL2"
    result = _observe_mounts_with_kernel_release(tmp_path, monkeypatch, [
        _mount_line(1, "/", "ext4", "/dev/sda"),
        _mount_line(2, "/usr/lib/modules/" + kernel_release, "overlay", "none",
                    root="/", device="0:42", options="ro,relatime"),
    ])
    assert result["windows_drive_mounts"] == []
    assert result["unapproved_host_mounts"] == []


@pytest.mark.parametrize("overlay", [
    _mount_line(2, "/usr/lib/modules/6.6.114.1-microsoft-standard-WSL2",
                "overlay", "C:", root="/", device="0:42", options="ro,relatime"),
    _mount_line(2, "/usr/lib/modules/6.6.114.1-microsoft-standard-WSL2",
                "overlay", "none", root="/host/modules", device="0:42", options="ro,relatime"),
    _mount_line(2, "/usr/lib/modules/6.6.114.1-microsoft-standard-WSL2",
                "overlay", "none", root="/", device="0:42", options="rw,relatime"),
])
def test_mount_inventory_rejects_inexact_wsl_modules_overlay(tmp_path, monkeypatch, overlay) -> None:
    with pytest.raises(ContractError, match="unapproved Windows or host mount"):
        _observe_mounts_with_kernel_release(
            tmp_path, monkeypatch, [_mount_line(1, "/", "ext4", "/dev/sda"), overlay],
        )


@pytest.mark.parametrize("bad_mount", [
    _mount_line(2, "/mnt/c", "drvfs", "C:", options="rw,aname=drvfs"),
    _mount_line(2, "/opt/unexpected", "ext4", "/dev/other", root="/host/secrets", device="8:9"),
    _mount_line(2, "/etc", "ext4", "/dev/host", root="/host/etc", device="8:9", options="ro"),
])
def test_mount_inventory_rejects_windows_drive_and_unlisted_host_mount(tmp_path, monkeypatch, bad_mount) -> None:
    pid = 4242
    proc = _mount_fixture(tmp_path, pid, [
        _mount_line(1, "/", "ext4", "/dev/sda"), bad_mount,
    ])
    _map_proc_path(monkeypatch, pid, proc)
    with pytest.raises(ContractError, match="unapproved Windows or host mount"):
        capture._mount_and_socket_observation(pid)


def test_mount_inventory_refusal_reports_sanitized_mount_classification(tmp_path, monkeypatch) -> None:
    pid = 4242
    proc = _mount_fixture(tmp_path, pid, [
        _mount_line(1, "/", "ext4", "/dev/sda"),
        "2 1 8:1 / /mnt/d rw - 9p D: rw,aname=drvfs",
        _mount_line(3, "/home/alice/private", "ext4", "/dev/private-source",
                    root="/host/home/alice/private", device="8:9"),
    ])
    _map_proc_path(monkeypatch, pid, proc)

    with pytest.raises(ContractError, match="unapproved Windows or host mount") as exc_info:
        capture._mount_and_socket_observation(pid)

    message = str(exc_info.value)
    assert "Windows-drive mount target=/mnt/<nested> filesystem=9p" in message
    assert "unlisted mount target=/home/<nested> filesystem=ext4" in message
    assert "D:" not in message
    assert "alice" not in message
    assert "/dev/private-source" not in message
    assert "/host/home" not in message


def test_mount_inventory_deduplicates_repeated_findings_before_suffix_count(tmp_path, monkeypatch) -> None:
    pid = 4242
    drvfs_mount = "2 1 8:1 / /mnt/d rw - 9p D: rw,aname=drvfs"
    proc = _mount_fixture(tmp_path, pid, [
        _mount_line(1, "/", "ext4", "/dev/sda"),
        drvfs_mount,
        *[drvfs_mount.replace("2 1", f"{mount_id} 1") for mount_id in range(3, 12)],
    ])
    _map_proc_path(monkeypatch, pid, proc)

    with pytest.raises(ContractError, match="unapproved Windows or host mount") as exc_info:
        capture._mount_and_socket_observation(pid)

    message = str(exc_info.value)
    assert "Windows-drive mount target=/mnt/<nested> filesystem=9p" in message
    assert "unlisted mount target=/mnt/<nested> filesystem=9p" in message
    assert "duplicate target=/mnt/<nested>" in message
    assert "additional mount findings" not in message


def test_socket_inventory_fails_closed_for_known_container_socket(tmp_path, monkeypatch) -> None:
    pid = 4242
    proc = _mount_fixture(tmp_path, pid, [_mount_line(1, "/", "ext4", "/dev/sda")])
    socket_path = proc / "root/run/docker.sock"
    socket_path.parent.mkdir(parents=True)
    socket_path.write_text("synthetic socket placeholder", encoding="ascii")
    _map_proc_path(monkeypatch, pid, proc)
    with pytest.raises(ContractError, match="container-engine socket"):
        capture._mount_and_socket_observation(pid)


def test_mount_socket_inventory_fails_closed_when_proc_evidence_is_unreadable(tmp_path, monkeypatch) -> None:
    pid = 4242
    proc = _mount_fixture(tmp_path, pid, [_mount_line(1, "/", "ext4", "/dev/sda")])
    (proc / "mountinfo").unlink()
    _map_proc_path(monkeypatch, pid, proc)
    with pytest.raises(ContractError, match="inventory is incomplete"):
        capture._mount_and_socket_observation(pid)


def _patch_rollback_file_identity(monkeypatch, path: pathlib.Path) -> tuple[int, int, str]:
    original_stat = path.stat()
    real_open = capture.os.open
    directory_fd = real_open(path.parent / "rollback-dir-fd", os.O_CREAT | os.O_RDWR, 0o600)
    def open_target(target, flags, *args, **kwargs):
        if str(target) == str(path.parent):
            return directory_fd
        return real_open(target, flags, *args, **kwargs)

    monkeypatch.setattr(capture.os, "open", open_target)
    monkeypatch.setattr(capture.os, "fstat", lambda _fd: SimpleNamespace(
        st_dev=original_stat.st_dev, st_ino=original_stat.st_ino,
        st_mode=stat.S_IFREG | 0o640, st_uid=0, st_gid=989,
    ))
    monkeypatch.setattr(capture.os, "fsync", lambda _fd: None)
    monkeypatch.setattr(capture, "ATTESTATION_PATH", str(path))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    identity = (original_stat.st_dev, original_stat.st_ino, digest)
    return identity


def test_rollback_removes_exact_published_attestation_identity(tmp_path, monkeypatch) -> None:
    path = tmp_path / "network-policy.json"
    path.write_bytes(b"synthetic exact attestation\n")
    identity = _patch_rollback_file_identity(monkeypatch, path)
    assert capture._rollback_published_attestation(identity) is True
    assert not path.exists()


@pytest.mark.parametrize("identity_field", ["inode", "digest"])
def test_rollback_preserves_attestation_when_published_identity_mismatches(
        tmp_path, monkeypatch, identity_field) -> None:
    path = tmp_path / "network-policy.json"
    original = b"synthetic replacement attestation\n"
    path.write_bytes(original)
    identity = list(_patch_rollback_file_identity(monkeypatch, path))
    if identity_field == "inode":
        identity[1] += 1
    else:
        identity[2] = "0" * 64
    assert capture._rollback_published_attestation(tuple(identity)) is False
    assert path.read_bytes() == original


@pytest.mark.parametrize("probe", [
    _unit(active="activating", pid="4242", invocation="a" * 32),
    _unit(active="inactive", pid="0", invocation="b" * 32),
])
def test_rollback_guard_refuses_active_or_replaced_probe(monkeypatch, probe) -> None:
    monkeypatch.setattr(capture, "_systemctl_show", lambda _unit_name, **_kw: probe)
    assert capture._probe_inactive_for_rollback("a" * 32) is False


def test_source_identity_accepts_untracked_helper_with_exact_local_digest() -> None:
    head = "a" * 40
    local_bytes = pathlib.Path(capture.__file__).read_bytes()
    expected_digest = hashlib.sha256(local_bytes).hexdigest()
    calls: list[list[str]] = []

    def run(argv, **_kwargs):
        calls.append(argv)
        if argv[3:5] == ["rev-parse", "--verify"]:
            return _result(head + "\n")
        if "ls-tree" in argv:
            return _result("")
        raise AssertionError(f"unexpected git command: {argv}")

    capture._verify_source_identity(head, expected_digest, run=run)
    assert ["ls-tree" if "ls-tree" in argv else argv[3] for argv in calls] == [
        "rev-parse", "ls-tree",
    ]
    assert calls[1][:4] == ["git", "--no-replace-objects", "-C", str(capture.REPOSITORY)]


def test_source_identity_rejects_tracked_blob_digest_mismatch() -> None:
    head = "b" * 40
    local_digest = hashlib.sha256(pathlib.Path(capture.__file__).read_bytes()).hexdigest()
    calls: list[list[str]] = []

    def run(argv, **_kwargs):
        calls.append(argv)
        if argv[3:5] == ["rev-parse", "--verify"]:
            return _result(head + "\n")
        if "ls-tree" in argv:
            return _result(capture.SOURCE_RELATIVE_PATH + "\n")
        if "show" in argv:
            return subprocess.CompletedProcess(argv, 0, b"different tracked helper bytes", b"")
        raise AssertionError(f"unexpected git command: {argv}")

    with pytest.raises(ContractError, match="source blob differs from the pinned helper digest"):
        capture._verify_source_identity(head, local_digest, run=run)
    assert ["show" if "show" in argv else "ls-tree" if "ls-tree" in argv else argv[3]
            for argv in calls] == [
        "rev-parse", "ls-tree", "show",
    ]
    assert calls[1][:4] == ["git", "--no-replace-objects", "-C", str(capture.REPOSITORY)]
    assert "--no-replace-objects" in calls[2]
    assert calls[2][:4] == ["git", "--no-replace-objects", "-C", str(capture.REPOSITORY)]
    assert calls[2][4] == "show"


@pytest.mark.parametrize("failure_point", ["directory-fsync", "temporary-unlink"])
def test_publish_post_link_failure_propagates_exact_artifact_identity(
        tmp_path, monkeypatch, failure_point) -> None:
    path = tmp_path / "network-policy.json"
    monkeypatch.setattr(capture, "ATTESTATION_PATH", str(path))
    real_open = capture.os.open
    real_stat = capture.os.stat
    real_fstat = capture.os.fstat
    directory_fd = real_open(tmp_path / "directory-fd", os.O_CREAT | os.O_RDWR, 0o600)

    def open_target(target, flags, *args, **kwargs):
        if str(target) == str(tmp_path):
            return directory_fd
        return real_open(target, flags, *args, **kwargs)

    def stat_target(target, *args, **kwargs):
        result = real_stat(target, *args, **kwargs)
        if str(target) == str(tmp_path):
            return SimpleNamespace(st_uid=0, st_gid=989, st_mode=stat.S_IFDIR | 0o710,
                                   st_dev=result.st_dev, st_ino=result.st_ino)
        if str(target) == str(path):
            return SimpleNamespace(st_uid=0, st_gid=989, st_mode=stat.S_IFREG | 0o640,
                                   st_dev=result.st_dev, st_ino=result.st_ino)
        return result

    def fstat_target(fd):
        result = real_fstat(fd)
        return SimpleNamespace(st_uid=0, st_gid=989, st_mode=stat.S_IFREG | 0o640,
                               st_dev=result.st_dev, st_ino=result.st_ino)

    real_fsync = capture.os.fsync
    sync_count = 0

    def fsync_target(fd):
        nonlocal sync_count
        sync_count += 1
        if failure_point == "directory-fsync" and sync_count == 2:
            raise OSError("synthetic directory fsync failure after link")
        return real_fsync(fd)

    real_unlink = capture.os.unlink

    def unlink_target(target, *args, **kwargs):
        if (failure_point == "temporary-unlink"
                and str(target).startswith(str(tmp_path / ".network-policy-"))):
            raise OSError("synthetic temporary unlink failure after link")
        return real_unlink(target, *args, **kwargs)

    monkeypatch.setattr(capture.os, "open", open_target)
    monkeypatch.setattr(capture.os, "stat", stat_target)
    monkeypatch.setattr(capture.os, "fstat", fstat_target)
    monkeypatch.setattr(capture.os, "fchown", lambda *_args: None, raising=False)
    monkeypatch.setattr(capture.os, "fsync", fsync_target)
    monkeypatch.setattr(capture.os, "unlink", unlink_target)
    with pytest.raises(capture.AttestationPublishError) as error:
        capture._publish_attestation({"run_id": "synthetic-run", "nonce": "synthetic-nonce"})

    assert path.exists()
    contents = path.read_bytes()
    published = real_stat(path)
    identity = error.value.published_identity
    assert identity == (published.st_dev, published.st_ino, hashlib.sha256(contents).hexdigest())
    if failure_point == "temporary-unlink":
        temporary_links = list(tmp_path.glob(".network-policy-*"))
        assert len(temporary_links) == 1
        assert real_stat(temporary_links[0]).st_ino == published.st_ino
        real_unlink(temporary_links[0])


def _patch_run_probe_prerequisites(monkeypatch, *, unit_states=None, systemd_states=None,
                                   identities=None, preflight_result=None, start_calls=None,
                                   published=None, captures=None, systemd_generation=None,
                                   retry_cap_value=0):
    request_id = "c" * 32
    run_id = "s2-new-run-123"
    nonce = "n" * 32
    head = "a" * 40
    digest_values = {
        capture.DEFAULT_CONFIG_PATH: b"supervisor-config",
        capture.NETWORK_PROFILE_PATH: b"network-profile",
        capture.BOOTSTRAP_REQUEST_PATH: b"bootstrap-request",
        str(capture.SPEC_PATH): b"sandbox-spec",
        "/etc/os-release": b"ID=ubuntu\nVERSION_ID=24.04\n",
    }
    bootstrap_template = json.loads((pathlib.Path(__file__).resolve().parents[2]
                                     / "docs/sdlc/runtime-config/bootstrap-request.json").read_text(encoding="utf-8"))
    manifest = bootstrap_template["task_manifest"]
    manifest["retry_cap"] = retry_cap_value
    assert manifest["required_tests"][0]["test_id"] == (
        "tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment"
    )
    config = {"run_id": run_id, "probe_nonce": nonce,
              "store_path": "/var/lib/vst-runner/private/store.sqlite3",
              "preflight_record_path": "/var/lib/vst-runner/private/preflight.json",
              "operator_key_path": "/etc/vst-runner/network-policy.key"}
    bootstrap = {"request_id": request_id, "run_id": run_id,
                 "task_id": "S2-4-runtime-owner-runner-qualification", "task_manifest": manifest}
    profile = {"probe_unit": capture.PROBE_UNIT, "external_allowlist": [],
               "environment_id": "Ubuntu-24.04:S2:" + run_id}
    expected_digests = {
        capture.DEFAULT_CONFIG_PATH: hashlib.sha256(digest_values[capture.DEFAULT_CONFIG_PATH]).hexdigest(),
        capture.NETWORK_PROFILE_PATH: hashlib.sha256(digest_values[capture.NETWORK_PROFILE_PATH]).hexdigest(),
        capture.BOOTSTRAP_REQUEST_PATH: hashlib.sha256(digest_values[capture.BOOTSTRAP_REQUEST_PATH]).hexdigest(),
    }
    manifest_digest = capture.manifest_sha256(manifest)
    monkeypatch.setattr(capture.os, "name", "posix")
    monkeypatch.setattr(capture.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    monkeypatch.setattr(capture.os.path, "realpath", lambda _path: "/opt/vst-runtime-" + capture.RUNTIME_SOURCE_HEAD)
    monkeypatch.setattr(capture.os.path, "isabs", lambda path: isinstance(path, str) and path.startswith("/"))
    monkeypatch.setattr(capture.os.path, "lexists", lambda _path: False)
    monkeypatch.setattr(capture, "_verify_source_identity", lambda *_a, **_kw: None)
    monkeypatch.setattr(capture, "_read_controlled_json", lambda path: config if path == capture.DEFAULT_CONFIG_PATH else profile)
    monkeypatch.setattr(capture, "_read_root_controlled_json", lambda path, **_kw: bootstrap if path == capture.BOOTSTRAP_REQUEST_PATH else {"run_id": run_id, "nonce": nonce})
    monkeypatch.setattr(capture, "_read_root_key", lambda _path: b"synthetic-root-policy-key-0123456789")
    class FakePath:
        def __init__(self, value):
            self.value = str(value)

        def is_dir(self):
            return False

        def read_bytes(self):
            return digest_values[self.value]

        def read_text(self, *, encoding=None):
            if self.value == "/etc/os-release":
                return "ID=ubuntu\nVERSION_ID=24.04\n"
            if self.value == "/proc/sys/kernel/osrelease":
                return "6.6.114.1-microsoft-standard-WSL2"
            return ""

    monkeypatch.setattr(capture, "Path", FakePath)
    generation = systemd_generation or {"boot_id": "boot-a", "pid": 1,
                                        "start_ticks": 7, "net_ns_inode": 3, "mount_ns_inode": 4}
    states = iter(systemd_states or [generation] * 20)
    monkeypatch.setattr(capture, "_systemd_ready", lambda **_kw: next(states))
    monkeypatch.setattr(capture, "_assert_no_recent_shutdown", lambda **_kw: None)
    monkeypatch.setattr(capture, "_verify_probe_unit_files", lambda: None)
    current = iter(unit_states or [])
    default_probe = _unit()

    def show(unit, **_kw):
        if unit != capture.PROBE_UNIT:
            return _unit()
        try:
            return next(current)
        except StopIteration:
            return default_probe

    monkeypatch.setattr(capture, "_systemctl_show", show)
    identity_values = iter(identities or [{"pid": 123, "start_ticks": 9,
                                          "uid": [999, 999, 999, 999],
                                          "gid": [989, 989, 989, 989],
                                          "net_ns_inode": 33, "mount_ns_inode": 44,
                                          "cgroup": "/system.slice/vst-sandbox-probe.service"}] * 10)
    monkeypatch.setattr(capture, "_process_identity",
                        lambda _pid, **_kwargs: next(identity_values))
    monkeypatch.setattr(capture, "_network_observation", lambda *_a, **_kw: {
        "addresses": [{"ifname": "lo"}], "routes_v4": [], "routes_v6": []})
    monkeypatch.setattr(capture, "_mount_and_socket_observation", lambda _pid: {
        "mount_table": ["root"], "mount_contract": "VST_S2_PROBE_SYSTEMD_ALLOWLIST_V1",
        "windows_drive_mounts": [], "unapproved_host_mounts": [],
        "container_socket_paths_present": []})
    monkeypatch.setattr(capture, "sign_network_policy_attestation", lambda body, _key: {**body, "signature": "synthetic"})
    published = published if published is not None else []
    monkeypatch.setattr(capture, "_publish_attestation", lambda body: published.append(body))
    captures = captures if captures is not None else []

    def capture_invocation(invocation):
        captures.append(invocation)
        if preflight_result is not None:
            return preflight_result
        return {"run_id": run_id, "invocation_id": invocation, "probe_sha256": "d" * 64}

    monkeypatch.setattr(capture, "capture_probe_invocation", capture_invocation)
    start_calls = start_calls if start_calls is not None else []

    def command(argv, **_kw):
        if argv[:3] == [capture.SYSTEMCTL, "start", "--no-block"]:
            start_calls.append(argv)
        if argv == [capture.SYSTEMCTL, "--version"]:
            return _result("systemd 255 (255.4-1ubuntu8)\n")
        return _result()

    monkeypatch.setattr(capture, "_run", command)
    monkeypatch.setattr(capture, "_claim_attempt", lambda *_a, **_kw: "attempt-key")
    monkeypatch.setattr(capture.time, "monotonic", lambda: 0.0)
    return {
        "args": {"run_id": run_id, "nonce": nonce, "request_id": request_id,
                 "expected_head": head, "expected_sha256": "b" * 64,
                 "expected_supervisor_sha256": expected_digests[capture.DEFAULT_CONFIG_PATH],
                 "expected_profile_sha256": expected_digests[capture.NETWORK_PROFILE_PATH],
                 "expected_bootstrap_sha256": expected_digests[capture.BOOTSTRAP_REQUEST_PATH],
                 "expected_manifest_sha256": manifest_digest},
        "start_calls": start_calls, "published": published, "captures": captures,
        "generation": generation,
    }


def test_run_probe_starts_once_and_captures_only_exact_success(monkeypatch) -> None:
    invocation = "f" * 32
    state = _patch_run_probe_prerequisites(monkeypatch, unit_states=[
        _unit(), _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="inactive", result="success", invocation=invocation),
    ])
    result = capture.run_probe(**state["args"], sleep=lambda _seconds: None)
    assert result["invocation_id"] == invocation
    assert len(state["start_calls"]) == 1
    assert state["start_calls"][0] == [capture.SYSTEMCTL, "start", "--no-block", capture.PROBE_UNIT]
    assert len(state["published"]) == 1
    assert result["host_environment"]["os_release_sha256"] == hashlib.sha256(
        b"ID=ubuntu\nVERSION_ID=24.04\n").hexdigest()
    assert len(result["observation_sha256"]) == 64
    assert result["observation_sha256"] != result["host_environment"]["os_release_sha256"]
    assert state["captures"] == [invocation]
    assert "vst-assignment-bootstrap.service" not in state["start_calls"]
    assert "vst-runner.service" not in state["start_calls"]


def test_run_probe_rejects_boolean_retry_cap_before_probe_start(monkeypatch) -> None:
    monkeypatch.setattr(capture, "manifest_sha256", lambda _manifest: "e" * 64)
    state = _patch_run_probe_prerequisites(monkeypatch, retry_cap_value=True)
    with pytest.raises(ContractError, match="single permitted TestRun selector"):
        capture.run_probe(**state["args"], sleep=lambda _seconds: None)
    assert state["start_calls"] == []
    assert state["published"] == []
    assert state["captures"] == []


def test_run_probe_rejects_systemd_generation_change_before_attestation(monkeypatch) -> None:
    invocation = "e" * 32
    first = {"boot_id": "boot-a", "pid": 1, "start_ticks": 7,
             "net_ns_inode": 3, "mount_ns_inode": 4}
    changed = {**first, "start_ticks": 8}
    state = _patch_run_probe_prerequisites(monkeypatch, unit_states=[
        _unit(), _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
    ], systemd_states=[first, first, first, changed])
    with pytest.raises(ContractError, match="boot or systemd generation changed"):
        capture.run_probe(**state["args"], sleep=lambda _seconds: None)
    assert len(state["start_calls"]) == 1
    assert state["published"] == []
    assert state["captures"] == []


def test_run_probe_rejects_worker_identity_drift_before_attestation(monkeypatch) -> None:
    invocation = "d" * 32
    identity = {"pid": 123, "start_ticks": 9, "uid": [999, 999, 999, 999],
                "gid": [989, 989, 989, 989],
                "net_ns_inode": 33, "mount_ns_inode": 44,
                "cgroup": "/system.slice/vst-sandbox-probe.service"}
    changed = {**identity, "mount_ns_inode": 45}
    state = _patch_run_probe_prerequisites(monkeypatch, unit_states=[
        _unit(), _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
    ], identities=[identity, changed])
    with pytest.raises(ContractError, match="PID, cgroup, namespace, or invocation changed"):
        capture.run_probe(**state["args"], sleep=lambda _seconds: None)
    assert state["published"] == []
    assert state["captures"] == []


def test_run_probe_rejects_interrupted_invocation_without_capture_or_downstream_start(monkeypatch) -> None:
    invocation = "c" * 32
    state = _patch_run_probe_prerequisites(monkeypatch, unit_states=[
        _unit(), _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="inactive", result="signal", invocation=invocation),
    ])
    with pytest.raises(ContractError, match="did not complete successfully"):
        capture.run_probe(**state["args"], sleep=lambda _seconds: None)
    assert len(state["start_calls"]) == 1
    assert state["captures"] == []
    # This helper only starts the probe; downstream services/TestRun are gated by its success.
    assert all(call[3] == capture.PROBE_UNIT for call in state["start_calls"])


def test_run_probe_rejects_invocation_replacement_before_attestation(monkeypatch) -> None:
    invocation = "a" * 32
    replacement = "b" * 32
    state = _patch_run_probe_prerequisites(monkeypatch, unit_states=[
        _unit(), _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=invocation),
        _unit(active="activating", pid="123", invocation=replacement),
    ])
    with pytest.raises(ContractError, match="PID, cgroup, namespace, or invocation changed"):
        capture.run_probe(**state["args"], sleep=lambda _seconds: None)
    assert state["published"] == []
    assert state["captures"] == []


def test_attempt_claim_refuses_a_previous_run_identity_before_any_new_start(tmp_path, monkeypatch) -> None:
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    marker = private_dir / ".probe-attempt-existing.json"
    marker.write_text(json.dumps({
        "schema": "VST_S2_PROBE_ATTEMPT_CLAIM_V1", "request_id": "1" * 32,
        "run_id": "s2-used-run", "nonce": "2" * 32,
        "manifest_sha256": "3" * 64,
    }), encoding="ascii")
    real_stat = os.stat
    monkeypatch.setattr(capture.os, "stat", lambda path, **_kw: SimpleNamespace(
        st_uid=0, st_gid=0, st_mode=0o40700) if pathlib.Path(path) == private_dir else real_stat(path))
    with pytest.raises(ContractError, match="already consumed"):
        capture._claim_attempt("1" * 32, "s2-used-run", "2" * 32, "3" * 64,
                               {"preflight_record_path": str(private_dir / "preflight.json")})


def test_attempt_claim_retires_interrupted_original_identity(monkeypatch) -> None:
    with pytest.raises(ContractError, match="permanently retired"):
        capture._claim_attempt(
            "3e56a61c5b1e45aea089c305b25e3187",
            "s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8",
            "0d2bb2c5f977478a924f7ec6629a339d", "4" * 64,
            {"preflight_record_path": "/var/lib/vst-runner/private/preflight.json"},
        )


def test_attempt_claim_retires_socket_mismatch_run_identity_before_marker_creation(
        tmp_path, monkeypatch) -> None:
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    real_stat = os.stat
    monkeypatch.setattr(capture.os, "stat", lambda path, **_kw: SimpleNamespace(
        st_uid=0, st_gid=0, st_mode=0o40700) if pathlib.Path(path) == private_dir else real_stat(path))

    with pytest.raises(ContractError, match="permanently retired"):
        capture._claim_attempt(
            "c63842aefcf74f57af70a1b2f93b8271",
            "s2-runtime-20261030-8102de64e7b4472ca2b5d2d56ed48510",
            "5f5820a7cfc348cfa89de31af6c6d1a7", "4" * 64,
            {"preflight_record_path": str(private_dir / "preflight.json")},
        )

    assert list(private_dir.iterdir()) == []


def test_attempt_claim_retires_latest_consumed_identity_before_marker_creation(
        tmp_path, monkeypatch) -> None:
    private_dir = tmp_path / "private"
    private_dir.mkdir(mode=0o700)
    real_stat = os.stat
    monkeypatch.setattr(capture.os, "stat", lambda path, **_kw: SimpleNamespace(
        st_uid=0, st_gid=0, st_mode=0o40700) if pathlib.Path(path) == private_dir else real_stat(path))

    with pytest.raises(ContractError, match="permanently retired"):
        capture._claim_attempt(
            "212a23e66ee94a7d87355b11e07e34fe",
            "s2-runtime-20261030-334296bd0779488d837a27e283b50b6a",
            "b57520d076e1acd355d310ed18364907", "4" * 64,
            {"preflight_record_path": str(private_dir / "preflight.json")},
        )

    assert list(private_dir.iterdir()) == []


def test_run_probe_rejects_malformed_run_id_before_start(monkeypatch) -> None:
    # No source, runtime, or WSL command may run for shell-like identity input.
    monkeypatch.setattr(capture.os, "name", "posix")
    monkeypatch.setattr(capture.os, "geteuid", lambda: 0, raising=False)
    with pytest.raises(ContractError, match="run identity"):
        capture.run_probe("bad;poweroff", "n" * 32, request_id="c" * 32,
                          expected_head="a" * 40, expected_sha256="b" * 64,
                          expected_supervisor_sha256="c" * 64,
                          expected_profile_sha256="d" * 64,
                          expected_bootstrap_sha256="e" * 64,
                          expected_manifest_sha256="f" * 64)
