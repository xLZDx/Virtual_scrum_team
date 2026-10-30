"""S2 root-captured probe contract checks; fixtures are not host-isolation evidence."""
from __future__ import annotations

import hashlib
import os
import time
from types import SimpleNamespace

import pytest

from tools.vst import preflight
from tools.vst.store import Store, StoreError
from tools.vst.supervisor import Supervisor

WORKER_KEY = b"s2-worker-root-key-0123456789-abcdef"
SUPERVISOR_KEY = b"s2-supervisor-root-key-0123456789-abcdef"
OPERATOR_KEY = b"s2-operator-root-key-0123456789-abcdef"
EVENT_KEY = b"s2-event-root-key-0123456789-abcdef"
REVIEWER_KEY = b"s2-reviewer-root-key-0123456789-abcdef"
_DEFAULT_ATTESTATION = object()
PROPERTIES = {
    "automount_disabled", "interop_disabled", "no_container_socket", "non_root",
    "external_egress_blocked", "loopback_canary", "empty_external_allowlist",
}


def operator_attestation(*, key=OPERATOR_KEY, run_id="run-1", nonce="nonce-1", **overrides):
    body = {
        "run_id": run_id,
        "spec_sha256": hashlib.sha256(preflight.SPEC_PATH.read_bytes()).hexdigest(),
        "nonce": nonce,
        "environment_id": "synthetic-fixture-environment",
        "policy_sha256": "a" * 64,
        "evidence_sha256": "b" * 64,
        "empty_external_allowlist": True,
        "no_container_socket": True,
        "no_unapproved_host_paths": True,
    }
    body.update(overrides)
    return preflight.sign_network_policy_attestation(body, key)


def valid_probe(attestation=_DEFAULT_ATTESTATION):
    attestation = operator_attestation() if attestation is _DEFAULT_ATTESTATION else attestation
    body = {
        "run_id": "run-1",
        "spec_sha256": hashlib.sha256(preflight.SPEC_PATH.read_bytes()).hexdigest(),
        "nonce": "nonce-1",
        "checked_properties": {name: True for name in PROPERTIES},
        "result": "PASS",
        "inventory": {
            "mount_table": ["rootfs / ext4 rw,relatime 0 0"],
            "windows_drive_mounts": [],
            "wsl_interop_present": False,
            "wsl_interop_enabled": False,
            "uid": 1001,
            "gid": 1001,
            "container_socket_paths_present": [],
            "container_socket_inventory_complete": True,
            "blocked_egress_target": ["198.51.100.1", 9],
            "blocked_egress_probe_scope": "single reserved-target smoke probe; does not prove egress policy",
            "network_policy_attestation": attestation,
            "environment_variable_names": [],
            "observed_at_monotonic_ns": time.monotonic_ns(),
        },
    }
    # No Runner/probe signature: the Supervisor accepts only this exact record
    # from its root-owned preflight path and verifies the separate root policy attestation.
    return body


def test_five_sandbox_trust_roots_are_pairwise_distinct():
    roots = [WORKER_KEY, SUPERVISOR_KEY, OPERATOR_KEY, EVENT_KEY, REVIEWER_KEY]
    assert all(len(key) >= 32 for key in roots)
    assert len(set(roots)) == 5


def test_probe_and_operator_attestation_bind_run_spec_nonce_and_every_check():
    probe = valid_probe()
    args = dict(
        run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1",
    )
    assert "signature" not in probe
    assert preflight.validate_fresh_probe(probe, **args)
    attestation = probe["inventory"]["network_policy_attestation"]
    operator_args = dict(
        run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1", key=OPERATOR_KEY,
    )
    assert preflight.verify_network_policy_attestation(attestation, **operator_args)
    for changed in (
        {**probe, "run_id": "other"}, {**probe, "nonce": "other"},
        {**probe, "spec_sha256": "0" * 64}, {**probe, "result": "FAIL"},
    ):
        assert not preflight.validate_fresh_probe(changed, **args)
    for name in sorted(PROPERTIES):
        bad = {**probe, "checked_properties": {**probe["checked_properties"], name: False}}
        assert not preflight.validate_fresh_probe(bad, **args), name
    for bad_args in (
        {**operator_args, "run_id": "other"},
        {**operator_args, "nonce": "other"},
        {**operator_args, "spec_sha256": "0" * 64},
        {**operator_args, "key": b"x" * 32},
    ):
        assert not preflight.verify_network_policy_attestation(attestation, **bad_args)


@pytest.mark.parametrize(
    "mutate",
    ["missing_run_id", "missing_inventory", "extra_field", "extra_signature",
     "missing_check", "non_boolean_check", "missing_inventory_field", "extra_inventory_field"],
)
def test_probe_inventory_requires_exact_unambiguous_schema_without_signature(mutate):
    probe = valid_probe()
    assert preflight.validate_fresh_probe(
        probe, run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1",
    )
    bad = {**probe, "inventory": dict(probe["inventory"]),
           "checked_properties": dict(probe["checked_properties"])}
    if mutate == "missing_run_id":
        bad.pop("run_id")
    elif mutate == "missing_inventory":
        bad.pop("inventory")
    elif mutate == "extra_field":
        bad["unexpected"] = True
    elif mutate == "extra_signature":
        bad["signature"] = "a" * 64
    elif mutate == "missing_check":
        bad["checked_properties"].pop("loopback_canary")
    elif mutate == "non_boolean_check":
        bad["checked_properties"]["loopback_canary"] = 1
    elif mutate == "missing_inventory_field":
        bad["inventory"].pop("mount_table")
    elif mutate == "extra_inventory_field":
        bad["inventory"]["unexpected"] = True
    assert not preflight.validate_fresh_probe(
        bad, run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1",
    )


@pytest.mark.parametrize("age_ns", [preflight.MAX_FRESH_PROBE_AGE_NS + 1, -1])
def test_probe_rejects_stale_or_future_observation(monkeypatch, age_ns):
    now_ns = 5_000_000_000
    monkeypatch.setattr(preflight.time, "monotonic_ns", lambda: now_ns)
    probe = valid_probe()
    probe["inventory"]["observed_at_monotonic_ns"] = now_ns - age_ns

    assert not preflight.validate_fresh_probe(
        probe, run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("uid", 0), ("container_socket_inventory_complete", False),
     ("container_socket_paths_present", ["/run/docker.sock"]),
     ("wsl_interop_enabled", True),
     ("windows_drive_mounts", ["C:\\ /mnt/c drvfs rw 0 0"]),
     ("mount_table", [1]),
     ("blocked_egress_target", ["203.0.113.1", 9]),
     ("blocked_egress_probe_scope", "unbounded network evidence"),
     ("environment_variable_names", [1]),
     ("observed_at_monotonic_ns", True)],
    ids=["root-uid", "incomplete-socket-inventory", "present-container-socket",
         "interop-enabled", "windows-drive-mount", "malformed-mount-row",
         "wrong-blocked-target", "wrong-target-scope", "malformed-environment-name",
         "invalid-observation-time"],
)
def test_probe_inventory_rejects_root_or_unverified_socket_boundary(field, value):
    probe = valid_probe()
    bad = {**probe, "inventory": {**probe["inventory"], field: value}}
    assert not preflight.validate_fresh_probe(
        bad, run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1",
    )


@pytest.mark.parametrize(
    "mutate",
    ["wrong_run", "wrong_spec", "wrong_nonce", "missing_field", "extra_field",
     "bad_signature", "wrong_key", "nonempty_allowlist"],
)
def test_root_network_policy_attestation_rejects_invalid_binding_or_signature(mutate):
    probe = valid_probe()
    attestation = dict(probe["inventory"]["network_policy_attestation"])
    args = dict(run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1", key=OPERATOR_KEY)
    if mutate == "wrong_run":
        attestation = operator_attestation(run_id="other")
    elif mutate == "wrong_spec":
        attestation = operator_attestation(spec_sha256="0" * 64)
    elif mutate == "wrong_nonce":
        attestation = operator_attestation(nonce="other")
    elif mutate == "missing_field":
        attestation.pop("evidence_sha256")
    elif mutate == "extra_field":
        attestation["unexpected"] = True
    elif mutate == "bad_signature":
        attestation["signature"] = "0" * 64
    elif mutate == "wrong_key":
        args["key"] = b"wrong-operator-key-0123456789-abcdef"
    elif mutate == "nonempty_allowlist":
        attestation = operator_attestation(empty_external_allowlist=False)
    assert not preflight.verify_network_policy_attestation(attestation, **args)


def _supervisor(tmp_path):
    store = Store(str(tmp_path / "synthetic-sandbox.db"), event_key=EVENT_KEY)
    store.sandbox_mode = True  # Protocol fixture only; does not claim host isolation.
    supervisor = Supervisor(
        store,
        operation_backend=object(),
        run_id="run-1",
        probe_nonce="nonce-1",
        operator_key=OPERATOR_KEY,
    )
    return store, supervisor


def test_supervisor_accepts_a_valid_synthetic_operator_attestation(tmp_path):
    store, supervisor = _supervisor(tmp_path)
    started = []
    try:
        assert supervisor.start_worker(lambda: started.append(True) or "started", probe=valid_probe()) == "started"
        assert started == [True]
    finally:
        store.close()


@pytest.mark.parametrize(
    "mutation",
    ["wrong_run", "wrong_spec", "wrong_nonce", "missing_field", "extra_field",
     "failed_check", "root_uid", "incomplete_socket_inventory", "present_socket"],
)
def test_supervisor_refuses_invalid_root_captured_probe_before_worker_start(tmp_path, mutation):
    probe = valid_probe()
    if mutation == "wrong_run":
        probe["run_id"] = "other"
    elif mutation == "wrong_spec":
        probe["spec_sha256"] = "0" * 64
    elif mutation == "wrong_nonce":
        probe["nonce"] = "other"
    elif mutation == "missing_field":
        probe.pop("inventory")
    elif mutation == "extra_field":
        probe["signature"] = "a" * 64
    elif mutation == "failed_check":
        probe["checked_properties"]["external_egress_blocked"] = False
    elif mutation == "root_uid":
        probe["inventory"]["uid"] = 0
    elif mutation == "incomplete_socket_inventory":
        probe["inventory"]["container_socket_inventory_complete"] = False
    elif mutation == "present_socket":
        probe["inventory"]["container_socket_paths_present"] = ["/run/docker.sock"]

    store, supervisor = _supervisor(tmp_path)
    started = []
    try:
        with pytest.raises(StoreError, match="fresh passing root-captured preflight"):
            supervisor.start_worker(lambda: started.append(True), probe=probe)
        assert started == []
    finally:
        store.close()


@pytest.mark.parametrize("failure", ["missing", "wrong_key", "tampered", "nonempty_allowlist"])
def test_supervisor_refuses_untrusted_operator_attestation_before_worker_start(tmp_path, failure):
    attestation = operator_attestation()
    if failure == "missing":
        attestation = None
    elif failure == "wrong_key":
        attestation = operator_attestation(key=b"wrong-operator-key-0123456789-abcdef")
    elif failure == "tampered":
        attestation = operator_attestation()
        attestation["evidence_sha256"] = "c" * 64
    elif failure == "nonempty_allowlist":
        attestation = operator_attestation(empty_external_allowlist=False)

    store, supervisor = _supervisor(tmp_path)
    started = []
    try:
        with pytest.raises(StoreError, match="fresh passing root-captured preflight|operator-root-signed"):
            supervisor.start_worker(lambda: started.append(True), probe=valid_probe(attestation))
        assert not started
    finally:
        store.close()


def _patch_collect_inventory(monkeypatch, *, sockets, complete, mounts=""):
    class FakePath:
        def __init__(self, value):
            self.value = value

        def read_text(self, *args, **kwargs):
            return mounts

        def exists(self):
            return False

    fake_os = SimpleNamespace(
        name="posix", geteuid=lambda: 1001, getegid=lambda: 1001, environ={},
    )
    monkeypatch.setattr(preflight, "os", fake_os)
    monkeypatch.setattr(preflight, "Path", FakePath)
    monkeypatch.setattr(preflight, "_container_socket_inventory", lambda: (sockets, complete))
    monkeypatch.setattr(preflight, "_blocked_egress", lambda: True)
    monkeypatch.setattr(preflight, "_loopback_canary", lambda: True)


def test_collect_inventory_cannot_claim_empty_allowlist_without_operator_attestation(monkeypatch):
    _patch_collect_inventory(monkeypatch, sockets=[], complete=True)
    result = preflight.collect_inventory("run-1", "nonce-1")
    assert result["result"] == "FAIL"
    assert result["checked_properties"]["empty_external_allowlist"] is False
    assert result["inventory"]["network_policy_attestation"] is None


def test_collect_inventory_fails_closed_when_socket_enumeration_is_incomplete(monkeypatch):
    _patch_collect_inventory(monkeypatch, sockets=[], complete=False)
    attestation = operator_attestation()
    result = preflight.collect_inventory(
        "run-1", "nonce-1", network_policy_attestation=attestation,
    )
    assert result["inventory"]["container_socket_inventory_complete"] is False
    assert result["checked_properties"]["no_container_socket"] is False
    assert result["result"] == "FAIL"


@pytest.mark.parametrize(
    "mount_row, expected",
    [
        ("/dev/something /mnt/wslg ext4 rw 0 0", True),
        ("C:\\ /mnt/c 9p rw,aname=drvfs;path=C:\\ 0 0", False),
        ("C:\\ /mnt/c drvfs rw 0 0", False),
    ],
)
def test_mount_classification_only_rejects_windows_drive_mounts(monkeypatch, mount_row, expected):
    _patch_collect_inventory(monkeypatch, sockets=[], complete=True, mounts=mount_row)
    inventory = preflight.collect_inventory("run-1", "nonce-1")
    assert inventory["checked_properties"]["automount_disabled"] is expected


def test_socket_inventory_discovers_runtime_socket_under_non_1000_uid(monkeypatch):
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
        def __init__(self, values):
            self.values = values

        def __enter__(self):
            return self.values

        def __exit__(self, *exc):
            return False

    class FakePath:
        def __init__(self, value):
            self.value = value

        def read_text(self, *args, **kwargs):
            return "Num RefCount Protocol Flags Type St Inode Path\n"

    def lstat(path):
        if path in directories or path == socket_path:
            return object()
        raise FileNotFoundError(path)

    fake_path = SimpleNamespace(
        islink=lambda path: False,
        isdir=lambda path: path in directories,
        join=lambda *parts: "/".join(parts),
        dirname=lambda path: path.rsplit("/", 1)[0],
    )
    fake_os = SimpleNamespace(
        lstat=lstat,
        scandir=lambda path: PathEnumerator([Entry("1000"), Entry("1001")]),
        path=fake_path,
    )
    monkeypatch.setattr(preflight, "os", fake_os)
    monkeypatch.setattr(preflight, "Path", FakePath)

    sockets, complete = preflight._container_socket_inventory()
    assert complete is True
    assert sockets == [socket_path]


@pytest.mark.skipif(os.name == "nt", reason="NOT_RUN: POSIX reviewer credentials are unavailable on Windows")
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


@pytest.mark.skip(reason="NOT_RUN: actual WSL/VM sandbox inventory and egress probe require operator-provisioned POSIX sandbox; synthetic inventories do not prove platform isolation")
def test_real_sandbox_inventory_has_all_required_properties():
    inventory = preflight.collect_inventory("operator-provisioned-run")
    assert inventory["result"] == "PASS"


@pytest.mark.parametrize("scenario", [
    "worker_crash_mid_edit",
    "STOP_injection_and_cleanup",
    "budget_exhaustion",
    "resume_with_fresh_epoch_and_receipt",
    "unauthorized_write_outside_scope",
    "blocked_egress_attempt",
])
@pytest.mark.skip(reason="NOT_RUN: E8 bake-off requires operator-provisioned sandbox; process-kill and mutation runs are prohibited, and no synthetic result can prove isolation")
def test_e8_sandbox_bakeoff_scenarios_not_run(scenario):
    pytest.skip(scenario)
