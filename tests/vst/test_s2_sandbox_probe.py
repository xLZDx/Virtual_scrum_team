"""Sandbox observation contract tests; synthetic data never proves host isolation."""
from __future__ import annotations

import json
import os
import pytest
from types import SimpleNamespace

from tools.vst import preflight
from tools.vst.store import Store, StoreError
from tools.vst.supervisor import Supervisor


EVENT_KEY = b"s2-event-root-key-0123456789-abcdef"
OPERATOR_KEY = b"s2-operator-root-key-0123456789-abcdef"
RUN_ID = "synthetic-supervisor-run"
NONCE = "synthetic-supervisor-nonce"
SPEC_SHA256 = "a" * 64
NETWORK_SHA256 = "b" * 64
NOW_NS = 5_000_000_000
EXPECTED_CHECKS = {
    "automount_disabled", "interop_disabled", "no_container_socket", "non_root",
    "egress_policy_isolated", "loopback_canary", "empty_external_allowlist",
    "no_unapproved_host_mounts", "expected_cgroup", "runtime_namespaces_observed",
}


def valid_observation(*, now_ns=NOW_NS) -> dict:
    return {
        "schema": "VST_S2_RUNTIME_OBSERVATION_V1",
        "checked_properties": {name: True for name in EXPECTED_CHECKS},
        "result": "PASS",
        "inventory": {
            "mount_table": ["rootfs / ext4 rw 0 0"],
            "windows_drive_mounts": [], "unapproved_host_mounts": [],
            "wsl_interop_present": False, "wsl_interop_enabled": False,
            "uid": 999, "gid": 989,
            "cgroup": ["0::/system.slice/vst-sandbox-probe.service"],
            "namespace_inodes": {"mount": 10, "network": 11, "cgroup": 12, "pid": 13},
            "network_interfaces": ["lo"], "network_routes": [],
            "container_socket_paths_present": [], "container_socket_inventory_complete": True,
            "environment_variable_names": [],
            "spec_sha256": SPEC_SHA256, "network_profile_sha256": NETWORK_SHA256,
            "observed_at_monotonic_ns": now_ns,
        },
    }


def test_runtime_observation_requires_exact_fresh_schema_and_all_environment_checks(monkeypatch):
    monkeypatch.setattr(preflight.time, "monotonic_ns", lambda: NOW_NS)
    observation = valid_observation()

    assert preflight.validate_fresh_probe(
        {**observation, "run_id": RUN_ID, "nonce": NONCE, "spec_sha256": SPEC_SHA256},
        run_id=RUN_ID, nonce=NONCE, spec_sha256=SPEC_SHA256,
    )

    for name in EXPECTED_CHECKS:
        bad = {**observation, "checked_properties": {**observation["checked_properties"], name: False}}
        assert not preflight.validate_fresh_probe(
            {**bad, "run_id": RUN_ID, "nonce": NONCE, "spec_sha256": SPEC_SHA256},
            run_id=RUN_ID, nonce=NONCE, spec_sha256=SPEC_SHA256,
        ), name


@pytest.mark.parametrize("change", ["run", "nonce", "spec", "age", "future", "signature"])
def test_runtime_observation_refuses_wrong_identity_staleness_or_extra_handoff(change, monkeypatch):
    monkeypatch.setattr(preflight.time, "monotonic_ns", lambda: NOW_NS)
    observation = valid_observation()
    value = {**observation, "run_id": RUN_ID, "nonce": NONCE, "spec_sha256": SPEC_SHA256}
    args = {"run_id": RUN_ID, "nonce": NONCE, "spec_sha256": SPEC_SHA256}
    if change == "run":
        value["run_id"] = "different-run"
    elif change == "nonce":
        value["nonce"] = "different-nonce"
    elif change == "spec":
        value["spec_sha256"] = "c" * 64
    elif change == "age":
        value["inventory"]["observed_at_monotonic_ns"] = NOW_NS - preflight.MAX_FRESH_PROBE_AGE_NS - 1
    elif change == "future":
        value["inventory"]["observed_at_monotonic_ns"] = NOW_NS + 1
    else:
        value["signature"] = "caller-supplied"

    assert not preflight.validate_fresh_probe(value, **args)


def test_supervisor_refuses_caller_supplied_observation_without_its_durable_consumption(tmp_path):
    store = Store(str(tmp_path / "unconsumed.db"), event_key=EVENT_KEY)
    store.sandbox_mode = True
    supervisor = Supervisor(
        store, operation_backend=object(), run_id=RUN_ID,
        probe_nonce=NONCE, operator_key=OPERATOR_KEY,
    )
    starts = []
    try:
        with pytest.raises(StoreError, match="Supervisor-owned runtime observation"):
            supervisor.start_worker(lambda: starts.append(True), probe=valid_observation())
        assert starts == []
    finally:
        store.close()


def _patch_collection_environment(monkeypatch, *, sockets=(), complete=True, mounts=None,
                                 empty_allowlist=True):
    root_mount = "1 0 0:1 / / rw - ext4 rootfs rw"
    mountinfo = "\n".join([root_mount, *(mounts or [])])
    profile = json.dumps({
        "external_allowlist": [] if empty_allowlist else ["example.invalid"],
        "probe_network_scope": "PrivateNetwork; only loopback interface/routes are allowed",
    })
    values = {
        "/proc/self/mountinfo": mountinfo,
        "/proc/self/cgroup": "0::/system.slice/vst-sandbox-probe.service\n",
        "/etc/vst-runner/network-profile.json": profile,
        str(preflight.SPEC_PATH): "synthetic specification",
    }
    class FakePath:
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return str(self.value)

        def exists(self):
            return False

    monkeypatch.setattr(preflight, "Path", FakePath)
    monkeypatch.setattr(preflight, "os", SimpleNamespace(
        name="posix", geteuid=lambda: 999, getegid=lambda: 989, environ={},
    ))
    monkeypatch.setattr(preflight, "_bounded_proc_text", lambda path, *_a, **_kw: values[str(path)])
    monkeypatch.setattr(preflight, "_network_namespace_inventory", lambda: (["lo"], [], [], True))
    monkeypatch.setattr(preflight, "_namespace_inode", lambda _name: 10)
    monkeypatch.setattr(preflight, "_container_socket_inventory", lambda: (list(sockets), complete))
    monkeypatch.setattr(preflight, "_loopback_canary", lambda: True)


def test_environment_collector_reports_only_observed_network_and_mount_properties(monkeypatch):
    _patch_collection_environment(monkeypatch)

    result = preflight.collect_inventory()

    assert result["schema"] == "VST_S2_RUNTIME_OBSERVATION_V1"
    assert result["result"] == "PASS"
    assert result["checked_properties"] == {name: True for name in EXPECTED_CHECKS}
    assert "run_id" not in result and "nonce" not in result
    assert "network_policy_attestation" not in result["inventory"]


def test_environment_collector_fails_closed_on_incomplete_socket_inventory(monkeypatch):
    _patch_collection_environment(monkeypatch, complete=False)

    result = preflight.collect_inventory()

    assert result["inventory"]["container_socket_inventory_complete"] is False
    assert result["checked_properties"]["no_container_socket"] is False
    assert result["result"] == "FAIL"


def test_environment_collector_fails_closed_for_nonempty_egress_allowlist(monkeypatch):
    _patch_collection_environment(monkeypatch, empty_allowlist=False)

    result = preflight.collect_inventory()

    assert result["checked_properties"]["empty_external_allowlist"] is False
    assert result["result"] == "FAIL"


@pytest.mark.parametrize(("mount_row", "expected"), [
    ("2 1 0:2 / /mnt/wslg rw - ext4 /dev/host rw", True),
    ("2 1 0:2 / /mnt/c rw - 9p C:\\ aname=drvfs;path=C:\\ rw", False),
    ("2 1 0:2 / /mnt/c rw - drvfs C:\\ rw", False),
])
def test_environment_collector_classifies_windows_drive_mounts(monkeypatch, mount_row, expected):
    _patch_collection_environment(monkeypatch, mounts=[mount_row])

    result = preflight.collect_inventory()

    assert result["checked_properties"]["automount_disabled"] is expected
    if not expected:
        assert result["checked_properties"]["no_unapproved_host_mounts"] is False
        assert mount_row in result["inventory"]["unapproved_host_mounts"]
        assert result["result"] == "FAIL"


def test_environment_collector_fails_closed_for_unlisted_host_mount(monkeypatch):
    host_mount = "2 1 0:2 /host/secrets /opt/private rw - ext4 /dev/other rw"
    _patch_collection_environment(monkeypatch, mounts=[host_mount])

    result = preflight.collect_inventory()

    assert result["checked_properties"]["no_unapproved_host_mounts"] is False
    assert result["inventory"]["unapproved_host_mounts"] == [host_mount]
    assert result["result"] == "FAIL"


def test_environment_collector_accepts_systemd_inaccessible_directory_mount_for_masked_wsl_path(
        monkeypatch):
    masked_mount = (
        "2 1 0:1 /run/systemd/inaccessible/dir /mnt rw - ext4 rootfs rw"
    )
    _patch_collection_environment(monkeypatch, mounts=[masked_mount])

    result = preflight.collect_inventory()

    assert result["checked_properties"]["no_unapproved_host_mounts"] is True
    assert result["inventory"]["unapproved_host_mounts"] == []
    assert masked_mount in result["inventory"]["mount_table"]


def test_network_namespace_observation_accepts_only_loopback_routes(monkeypatch):
    route4 = (
        "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
        "lo 0000007F 00000000 00000001 0 0 0 000000FF 0 0 0\n"
    )
    route6 = (
        "00000000000000000000000000000001 80 "
        "00000000000000000000000000000000 00 "
        "00000000000000000000000000000000 00000000 00000000 00000000 00000000 lo\n"
    )
    values = {"/proc/net/route": route4, "/proc/net/ipv6_route": route6}
    monkeypatch.setattr(preflight, "os", SimpleNamespace(listdir=lambda _path: ["lo"]))
    monkeypatch.setattr(preflight, "_bounded_proc_text", lambda path, *_a, **_kw: values[str(path)])

    interfaces, routes, _unused, isolated = preflight._network_namespace_inventory()

    assert interfaces == ["lo"]
    assert len(routes) == 2
    assert isolated is True


@pytest.mark.parametrize(("interfaces", "route_device"), [
    (["lo", "eth0"], "lo"), (["lo"], "eth0"),
])
def test_network_namespace_observation_rejects_external_interface_or_route(
        monkeypatch, interfaces, route_device):
    route4 = (
        "Iface Destination Gateway Flags RefCnt Use Metric Mask MTU Window IRTT\n"
        f"{route_device} 0000007F 00000000 00000001 0 0 0 000000FF 0 0 0\n"
    )
    values = {"/proc/net/route": route4, "/proc/net/ipv6_route": ""}
    monkeypatch.setattr(preflight, "os", SimpleNamespace(listdir=lambda _path: interfaces))
    monkeypatch.setattr(preflight, "_bounded_proc_text", lambda path, *_a, **_kw: values[str(path)])

    _observed_interfaces, _routes, _unused, isolated = preflight._network_namespace_inventory()

    assert isolated is False


def test_socket_inventory_finds_runtime_socket_under_nonstandard_uid(monkeypatch):
    user_paths = {"/run/user/1000", "/run/user/1001"}
    directories = {"/run/user", *user_paths}
    socket_path = "/run/user/1001/docker.sock"

    class Entry:
        def __init__(self, name):
            self.name = name
            self.path = f"/run/user/{name}"

        def is_symlink(self):
            return False

        def is_dir(self, *, follow_symlinks):
            return self.path in user_paths

    class PathEnumerator:
        def __enter__(self):
            return [Entry("1000"), Entry("1001")]

        def __exit__(self, *_exc):
            return False

    class FakePath:
        def __init__(self, _value):
            pass

        def read_text(self, *_args, **_kwargs):
            return "Num RefCount Protocol Flags Type St Inode Path\n"

    def lstat(path):
        if path in directories or path == socket_path:
            return object()
        raise FileNotFoundError(path)

    fake_path = SimpleNamespace(
        islink=lambda _path: False,
        isdir=lambda path: path in directories,
        join=lambda *parts: "/".join(parts),
        dirname=lambda path: path.rsplit("/", 1)[0],
    )
    monkeypatch.setattr(preflight, "os", SimpleNamespace(
        lstat=lstat, scandir=lambda _path: PathEnumerator(), path=fake_path,
    ))
    monkeypatch.setattr(preflight, "Path", FakePath)

    sockets, complete = preflight._container_socket_inventory()

    assert complete is True
    assert sockets == [socket_path]


def test_socket_inventory_fails_closed_when_proc_socket_evidence_is_unreadable(monkeypatch):
    fake_path = SimpleNamespace(
        islink=lambda _path: False,
        isdir=lambda _path: False,
        join=lambda *parts: "/".join(parts),
        dirname=lambda path: path.rsplit("/", 1)[0],
    )

    class UnreadableProcPath:
        def __init__(self, _path):
            pass

        def read_text(self, *_args, **_kwargs):
            raise PermissionError("proc socket inventory denied")

    monkeypatch.setattr(preflight, "os", SimpleNamespace(
        lstat=lambda _path: (_ for _ in ()).throw(FileNotFoundError()),
        scandir=lambda _path: pytest.fail("missing runtime root must not be enumerated"),
        path=fake_path,
    ))
    monkeypatch.setattr(preflight, "Path", UnreadableProcPath)

    sockets, complete = preflight._container_socket_inventory()

    assert sockets == []
    assert complete is False


@pytest.mark.skipif(os.name == "nt", reason="requires the real POSIX runtime account database")
def test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture():
    """Use the provisioned reviewer identity against disposable worker-owned resources."""
    import grp
    import json
    import pwd
    import shutil
    import tempfile
    from pathlib import Path
    import subprocess
    import sys

    assert os.geteuid() == 0, "run this identity-boundary test in the root test harness"
    worker = pwd.getpwnam("vst-worker")
    reviewer = pwd.getpwnam("vst-reviewer")
    worker_gid = grp.getgrnam("vst-worker").gr_gid
    reviewer_groups = set(os.getgrouplist(reviewer.pw_name, reviewer.pw_gid))
    assert reviewer.pw_uid != worker.pw_uid
    assert reviewer.pw_gid != worker_gid
    assert worker_gid not in reviewer_groups

    fixture_root = tempfile.mkdtemp(prefix="vst-reviewer-boundary-", dir="/tmp")
    os.chmod(fixture_root, 0o755)
    worktree = None
    try:
        worktree = os.path.join(fixture_root, "worktree")
        os.mkdir(worktree)
        worktree_file = os.path.join(worktree, "candidate.txt")
        with open(worktree_file, "w", encoding="utf-8") as stream:
            stream.write("disposable read-only candidate\n")
        db_path = os.path.join(fixture_root, "store.db")
        store = Store(db_path, event_key=EVENT_KEY)
        store.record_event("synthetic-task", "synthetic-actor", "NOTE", {"fixture": True})
        store.close()

        os.chmod(worktree, 0o555)
        os.chmod(worktree_file, 0o444)
        os.chmod(db_path, 0o440)
        os.chown(worktree_file, worker.pw_uid, worker_gid)
        os.chown(db_path, worker.pw_uid, worker_gid)
        os.chown(worktree, worker.pw_uid, worker_gid)

        child = r'''import json, os, sys
from tools.vst.sandbox import require_read_only_reviewer
worktree, store_path = sys.argv[1:3]
worker_uid = int(sys.argv[3])
require_read_only_reviewer(worktree, store_path, worker_uid=worker_uid)
checks = []
for label, path in (("worktree_file", os.path.join(worktree, "candidate.txt")),
                    ("store_file", store_path),
                    ("worktree_create", os.path.join(worktree, "new.txt"))):
    try:
        with open(path, "ab") as stream:
            stream.write(b"forbidden")
    except PermissionError:
        checks.append({"target": label, "write_denied": True})
    else:
        checks.append({"target": label, "write_denied": False})
print(json.dumps({"uid": os.getuid(), "gid": os.getgid(), "checks": checks}))
if len(checks) != 3 or not all(row["write_denied"] for row in checks):
    raise SystemExit(2)
'''

        def drop_to_reviewer():
            os.setgroups(os.getgrouplist(reviewer.pw_name, reviewer.pw_gid))
            os.setgid(reviewer.pw_gid)
            os.setuid(reviewer.pw_uid)

        repo_root = str(Path(__file__).resolve().parents[2])
        completed = subprocess.run(
            [sys.executable, "-c", child, worktree, db_path, str(worker.pw_uid)],
            cwd=repo_root,
            env={"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=False, preexec_fn=drop_to_reviewer,
        )
        assert completed.returncode == 0, "reviewer write-denial probe failed"
        observed = json.loads(completed.stdout)
        assert observed["uid"] == reviewer.pw_uid
        assert observed["gid"] == reviewer.pw_gid
        assert all(row["write_denied"] for row in observed["checks"])
    finally:
        if worktree is not None and os.path.isdir(worktree):
            os.chown(worktree, 0, 0)
            os.chmod(worktree, 0o700)
        shutil.rmtree(fixture_root)


@pytest.mark.skip(reason="NOT_RUN: provisioned POSIX sandbox evidence is required; a synthetic inventory cannot prove host isolation")
def test_real_sandbox_inventory_has_all_required_properties():
    assert preflight.collect_inventory()["result"] == "PASS"


@pytest.mark.parametrize("scenario", [
    "worker_crash_mid_edit", "STOP_injection_and_cleanup", "budget_exhaustion",
    "resume_with_fresh_epoch_and_receipt", "unauthorized_write_outside_scope",
    "blocked_egress_attempt",
])
@pytest.mark.skip(reason="NOT_RUN: E8 requires provisioned sandbox; process-kill and mutation runs are prohibited")
def test_e8_sandbox_bakeoff_scenarios_not_run(scenario):
    pytest.skip(scenario)
