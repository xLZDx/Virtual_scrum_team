"""S2-4D contract tests for authentic cold Runner transaction receipts."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
from pathlib import Path

import pytest

pytest.importorskip("fcntl", reason="runtime transaction helper requires the POSIX fcntl module")

from tools.vst import runner_fence as FENCE


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/qa/runtime_snapshot_transaction.py"
SPEC = importlib.util.spec_from_file_location("s2_snapshot_transaction_bootstrap", SCRIPT)
assert SPEC and SPEC.loader
TX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TX)


def _bootstrap_record(**overrides):
    record = {
        "version": 1,
        "state": "BOOTSTRAP_EMPTY",
        "unit": "vst-runner.service",
        "invocation_id": "BOOTSTRAP",
        "control_group": "/system.slice/vst-runner.service",
        "cgroup_device": -1,
        "cgroup_inode": -1,
        "lock_device": -1,
        "lock_inode": -1,
        "generation": "BOOTSTRAP",
        "predecessor_outcome": "NONE",
        "sequence": 1,
        "recorded_at": "2026-11-05T10:00:00+00:00",
        "previous_record_sha256": "0" * 64,
    }
    record.update(overrides)
    body = dict(record)
    record["record_sha256"] = hashlib.sha256(TX._canonical(body)).hexdigest()
    return record


def _proof(*, record=None, ledger_absent=False, generation_absent=False,
           ledger_empty=None, ledger_identity=None, generation_matches=True):
    if ledger_empty is None:
        ledger_empty = not ledger_absent and record is None
    if ledger_identity is None and not ledger_absent:
        ledger_identity = {"device": 1, "inode": 2}
    return {
        "schema": "VST_RUNNER_COLD_PREDECESSOR_PROOF_V1",
        "observed_at": "2026-11-05T10:00:00+00:00",
        "boot_id": "a" * 8 + "-" + "b" * 4 + "-" + "c" * 4 + "-" + "d" * 4 + "-" + "e" * 12,
        "pid1_start_ticks": "12345",
        "fence_config_sha256": "1" * 64,
        "ledger_absent": ledger_absent,
        "ledger_empty": ledger_empty,
        "ledger_identity": ledger_identity,
        "generation_absent": generation_absent,
        "ledger_record": record,
        "ledger_record_sha256": None if record is None else record["record_sha256"],
        "generation_matches_ledger": generation_matches,
        "role_process_counts": {"997": 0, "981": 0, "999": 0},
        "units": {
            "vst-runner.service": {"active_state": "inactive", "sub_state": "dead",
                                   "invocation_id": "", "control_group": ""},
            "vst-dispatcher.service": {"active_state": "inactive", "sub_state": "dead",
                                       "invocation_id": "", "control_group": ""},
        },
        "cgroups": {"vst-runner.service": {"state": "absent"},
                    "vst-dispatcher.service": {"state": "absent"}},
        "protected_jobs": [],
        "store_paths": {path: "absent" for path in (
            TX._STORE_PATH, TX._STORE_PATH + "-wal", TX._STORE_PATH + "-shm",
            TX._STORE_PATH + "-journal")},
        "live_root": {"device": 1, "inode": 2, "mode": 0o755,
                      "head": TX.EXPECTED_PREDECESSOR_HEAD,
                      "tree_sha1": "38a0a60b6170d068beb370c62f25b008d246902f",
                      "kind": "predecessor", "readonly_git_proof": None},
    }


def test_bootstrap_record_requires_exact_initial_authentic_runner_fence():
    record = _bootstrap_record()

    TX._validate_bootstrap_record(record)

    malformed = dict(record, unit="vst-dispatcher.service")
    body = {key: value for key, value in malformed.items() if key != "record_sha256"}
    malformed["record_sha256"] = hashlib.sha256(TX._canonical(body)).hexdigest()
    with pytest.raises(TX.SnapshotContractError, match="authentic BOOTSTRAP_EMPTY"):
        TX._validate_bootstrap_record(malformed)


@pytest.mark.parametrize("mutation", [
    {"sequence": 2},
    {"previous_record_sha256": "f" * 64},
    {"generation": "1"},
    {"lock_inode": 1},
])
def test_bootstrap_record_rejects_noninitial_or_nonempty_predecessor(mutation):
    with pytest.raises(TX.SnapshotContractError, match="authentic BOOTSTRAP_EMPTY"):
        TX._validate_bootstrap_record(_bootstrap_record(**mutation))


def test_bootstrap_record_rejects_tampered_canonical_hash():
    record = _bootstrap_record()
    record["recorded_at"] = "2026-11-05T10:00:01+00:00"

    with pytest.raises(TX.SnapshotContractError, match="record hash is invalid"):
        TX._validate_bootstrap_record(record)


def test_cold_proof_requires_exact_schema_and_a_fresh_full_recheck(monkeypatch):
    record = _bootstrap_record()
    prior = _proof(record=record)
    current = dict(prior, observed_at="2026-11-05T10:00:01+00:00")
    calls = []
    monkeypatch.setattr(TX, "observe_bootstrap_predecessor",
                        lambda **kwargs: calls.append(kwargs) or current)

    checked = TX._cold_proof_current(prior, allow_missing=False)

    assert checked is current
    assert calls == [{"allow_missing_ledger": False, "allow_candidate_root": False}]

    changed = dict(current, live_root=dict(current["live_root"], inode=99))
    monkeypatch.setattr(TX, "observe_bootstrap_predecessor", lambda **_kwargs: changed)
    with pytest.raises(TX.SnapshotContractError, match="proof is stale for field live_root"):
        TX._cold_proof_current(prior, allow_missing=False)

    unknown = dict(prior, historical_stopped=True)
    with pytest.raises(TX.SnapshotContractError, match="proof schema is invalid"):
        TX._cold_proof_current(unknown, allow_missing=False)


def _fence_config():
    return {
        "unit_name": "vst-runner.service",
        "systemctl_path": "/usr/bin/systemctl",
        "ledger_path": TX._FENCE_LEDGER,
        "runtime_dir": "/run/vst-runner",
        "daemon_uid": 997,
        "daemon_gid": 997,
        "dispatcher_uid": 981,
        "dispatcher_gid": 981,
        "worker_uid": 999,
        "worker_gid": 999,
        "control_group": "/system.slice/vst-runner.service",
        "generation_record_path": TX._FENCE_GENERATION,
    }


def test_fence_config_fixture_matches_the_pinned_runner_fence_contract(monkeypatch):
    import stat as stat_module
    from types import SimpleNamespace

    def stat_path(path, *, follow_symlinks=True):
        mode = (stat_module.S_IFREG | 0o755
                if path == "/usr/bin/systemctl"
                else stat_module.S_IFDIR | 0o755)
        return SimpleNamespace(st_mode=mode, st_uid=0)

    monkeypatch.setattr(FENCE.os, "stat", stat_path)

    FENCE._validate_config(_fence_config())


def _wire_bootstrap_observer(monkeypatch, tmp_path, unit_output, *, jobs=b"No jobs running.\n",
                             cgroup_result=None, store_path=None,
                             ledger_records=None, root_kind="predecessor"):
    import os as os_module
    import stat as stat_module
    from types import SimpleNamespace

    config_path = tmp_path / "fence.json"
    ledger_path = tmp_path / "fence-ledger.json"
    generation_path = tmp_path / "generation.json"
    store_base = str(tmp_path / "store.sqlite3")
    repository = tmp_path / "live-repository"
    repository.mkdir()
    os_module.chmod(repository, 0o555 if root_kind == "candidate" else 0o755)
    boot_id_path = tmp_path / "boot_id"
    boot_id_path.write_text("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee\n", encoding="ascii")
    pid1_path = tmp_path / "pid1.stat"
    pid1_path.write_text("1 (init) " + " ".join(["R"] + ["1"] * 25), encoding="ascii")
    config = _fence_config()
    config["ledger_path"] = str(ledger_path)
    config["generation_record_path"] = str(generation_path)
    config_raw = TX._canonical(config)
    config_path.write_bytes(config_raw)
    if ledger_records is not None:
        ledger_bytes = b"".join(TX._canonical(item) + b"\n" for item in ledger_records)
        ledger_path.write_bytes(ledger_bytes)
        os_module.chmod(ledger_path, 0o600)

    monkeypatch.setattr(TX, "_FENCE_CONFIG", str(config_path))
    monkeypatch.setattr(TX, "_FENCE_LEDGER", str(ledger_path))
    monkeypatch.setattr(TX, "_FENCE_GENERATION", str(generation_path))
    monkeypatch.setattr(TX, "_STORE_PATH", store_base)
    monkeypatch.setattr(TX, "_verify_root_directory_chain", lambda _path: None)
    def read_root_json(path, **_kwargs):
        if path == str(config_path):
            return config, config_raw
        raise FileNotFoundError(path)
    monkeypatch.setattr(TX, "_read_root_json", read_root_json)
    def read_ledger(_path, *, allow_empty=False):
        if ledger_records is None:
            raise FileNotFoundError(str(ledger_path))
        return ledger_records
    monkeypatch.setattr(TX, "read_fence_ledger", read_ledger)

    original_lstat = os_module.lstat
    def lstat(path, *args, **kwargs):
        raw_path = os_module.fspath(path)
        if raw_path == TX.TASK_REPOSITORY_ROOT:
            return original_lstat(repository)
        if raw_path == (store_path or store_base) or raw_path in {
                store_base + "-wal", store_base + "-shm", store_base + "-journal"}:
            if store_path == raw_path:
                return SimpleNamespace(st_mode=stat_module.S_IFREG | 0o600)
            raise FileNotFoundError(raw_path)
        return original_lstat(path, *args, **kwargs)
    monkeypatch.setattr(TX.os, "lstat", lstat)

    original_open = os_module.open
    def open_path(path, flags, *args, **kwargs):
        remap = {"/proc/sys/kernel/random/boot_id": boot_id_path,
                 "/proc/1/stat": pid1_path}
        return original_open(remap.get(path, path), flags, *args, **kwargs)
    monkeypatch.setattr(TX.os, "open", open_path)

    systemd_calls = []
    class Completed:
        returncode = 0
        stderr = b""
        def __init__(self, stdout):
            self.stdout = stdout.encode("ascii") if isinstance(stdout, str) else stdout
    def run(argv, **_kwargs):
        systemd_calls.append(argv)
        if argv[1:2] == ["show"]:
            return Completed(unit_output[argv[2]])
        if argv[1:2] == ["list-jobs"]:
            return Completed(jobs)
        raise AssertionError(f"unexpected subprocess in cold observer: {argv!r}")
    monkeypatch.setattr(TX.subprocess, "run", run)
    monkeypatch.setattr(TX, "_bootstrap_cgroup", lambda _path: cgroup_result or {"state": "absent"})
    monkeypatch.setattr(TX, "_bootstrap_process_counts", lambda _uids: {
        "997": 0, "981": 0, "999": 0})
    head = TX.TASK_HEAD if root_kind == "candidate" else TX.EXPECTED_PREDECESSOR_HEAD
    tree = TX.TASK_TREE if root_kind == "candidate" else "38a0a60b6170d068beb370c62f25b008d246902f"
    monkeypatch.setattr(TX, "_git_output", lambda _root, *args:
                        head if args[-1] == "HEAD" else tree)
    monkeypatch.setattr(TX, "_verify_git_readonly", lambda _root: {
        "head": TX.TASK_HEAD, "tree_sha1": TX.TASK_TREE, "status_clean": True})
    return systemd_calls, repository


def _valid_systemd_identity():
    return "ActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\n"


def _observer_unit_output():
    return {unit: _valid_systemd_identity() for unit in TX._ROLE_UNITS}


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cold observer validates root-owned files and repository metadata")
def test_bootstrap_observer_returns_real_cold_receipt_inputs_from_isolated_posix_fixture(
        tmp_path, monkeypatch):
    calls, _repository = _wire_bootstrap_observer(
        monkeypatch, tmp_path, _observer_unit_output())

    proof = TX.observe_bootstrap_predecessor(allow_missing_ledger=True)

    assert proof["ledger_absent"] is True
    assert proof["ledger_empty"] is False
    assert proof["generation_absent"] is True
    assert proof["live_root"]["kind"] == "predecessor"
    assert proof["role_process_counts"] == {"997": 0, "981": 0, "999": 0}
    assert set(proof["store_paths"].values()) == {"absent"}
    assert len(calls) == 3


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cold observer validates root-owned files and repository metadata")
def test_bootstrap_observer_accepts_only_exact_readonly_candidate_identity(tmp_path, monkeypatch):
    _wire_bootstrap_observer(monkeypatch, tmp_path, _observer_unit_output(),
                             root_kind="candidate")

    proof = TX.observe_bootstrap_predecessor(allow_missing_ledger=True,
                                             allow_candidate_root=True)

    assert proof["live_root"]["kind"] == "candidate"
    assert proof["live_root"]["mode"] == 0o555
    assert proof["live_root"]["readonly_git_proof"] == {
        "head": TX.TASK_HEAD, "tree_sha1": TX.TASK_TREE, "status_clean": True}


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cold observer validates root-owned files and repository metadata")
def test_bootstrap_observer_distinguishes_durable_empty_ledger_from_absent_ledger(
        tmp_path, monkeypatch):
    _wire_bootstrap_observer(monkeypatch, tmp_path, _observer_unit_output(),
                             ledger_records=[])

    proof = TX.observe_bootstrap_predecessor(allow_missing_ledger=True)

    assert proof["ledger_absent"] is False
    assert proof["ledger_empty"] is True
    assert proof["ledger_record"] is None
    assert proof["generation_absent"] is True


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cold observer validates root-owned files and repository metadata")
def test_bootstrap_observer_does_not_treat_empty_ledger_as_missing_permission(
        tmp_path, monkeypatch):
    _wire_bootstrap_observer(monkeypatch, tmp_path, _observer_unit_output(),
                             ledger_records=[])

    with pytest.raises(TX.SnapshotContractError, match="absent or has no authoritative record"):
        TX.observe_bootstrap_predecessor(allow_missing_ledger=False)


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cold observer validates root-owned files and repository metadata")
@pytest.mark.parametrize("bad_output", [
    "ActiveState=inactive\nActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\n",
    "ActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\nUnexpected=value\n",
    "ActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\nMalformed\n",
])
def test_bootstrap_observer_rejects_duplicate_unknown_and_malformed_systemd_properties(
        tmp_path, monkeypatch, bad_output):
    unit_output = _observer_unit_output()
    unit_output[TX._ROLE_UNITS[0]] = bad_output
    _wire_bootstrap_observer(monkeypatch, tmp_path, unit_output)

    with pytest.raises(TX.SnapshotContractError,
                       match="protected systemd properties are malformed or duplicated"):
        TX.observe_bootstrap_predecessor(allow_missing_ledger=True)


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cold observer validates root-owned files and repository metadata")
@pytest.mark.parametrize("mutation, message", [
    ("pending-job", "pending job"),
    ("existing-store", "Store or SQLite sidecar already exists"),
    ("multi-record-ledger", "one-record initial ledger"),
])
def test_bootstrap_observer_refuses_active_job_store_process_or_history(
        tmp_path, monkeypatch, mutation, message):
    kwargs = {}
    records = None
    if mutation == "pending-job":
        kwargs["jobs"] = b"1 vst-runner.service start waiting\n"
    elif mutation == "existing-store":
        kwargs["store_path"] = str(tmp_path / "store.sqlite3")
    elif mutation == "multi-record-ledger":
        records = [_bootstrap_record(), _bootstrap_record(sequence=2)]
        kwargs["ledger_records"] = records
    _wire_bootstrap_observer(monkeypatch, tmp_path, _observer_unit_output(), **kwargs)

    with pytest.raises(TX.SnapshotContractError, match=message):
        TX.observe_bootstrap_predecessor(allow_missing_ledger=True)


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="cgroup fixture uses POSIX directory descriptors")
def test_bootstrap_cgroup_uses_fixed_empty_scope_and_refuses_populated_or_nested_scope(
        tmp_path, monkeypatch):
    cgroup_root = tmp_path / "cgroup"
    service_dir = cgroup_root / "system.slice" / "vst-runner.service"
    service_dir.mkdir(parents=True)
    events = service_dir / "cgroup.events"
    procs = service_dir / "cgroup.procs"
    events.write_text("populated 0\nfrozen 0\n", encoding="ascii")
    procs.write_text("", encoding="ascii")
    original_open = os.open
    monkeypatch.setattr(TX.os, "open", lambda path, flags, *args, **kwargs:
                        original_open(cgroup_root if path == "/sys/fs/cgroup" else path,
                                      flags, *args, **kwargs))

    result = TX._bootstrap_cgroup("/sys/fs/cgroup/system.slice/vst-runner.service")
    assert result["state"] == "empty"
    assert result["populated"] == "0"
    assert result["processes"] == result["children"] == 0

    events.write_text("populated 1\nfrozen 0\n", encoding="ascii")
    with pytest.raises(TX.SnapshotContractError, match="populated or contains child scopes"):
        TX._bootstrap_cgroup("/sys/fs/cgroup/system.slice/vst-runner.service")

    events.write_text("populated 0\nfrozen 0\n", encoding="ascii")
    (service_dir / "child.scope").mkdir()
    with pytest.raises(TX.SnapshotContractError, match="populated or contains child scopes"):
        TX._bootstrap_cgroup("/sys/fs/cgroup/system.slice/vst-runner.service")


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="process inventory fixture uses POSIX process-status files")
def test_bootstrap_process_inventory_proves_reserved_uid_absence_and_rejects_live_owner(
        tmp_path, monkeypatch):
    proc_root = tmp_path / "proc"
    process_dir = proc_root / "123"
    process_dir.mkdir(parents=True)
    status = process_dir / "status"
    status.write_text("Name:\ttest\nUid:\t1000\t1000\t1000\t1000\n", encoding="ascii")
    original_scandir = os.scandir
    monkeypatch.setattr(TX.os, "scandir", lambda path: original_scandir(
        proc_root if path == "/proc" else path))

    assert TX._bootstrap_process_counts({997, 981, 999}) == {
        "997": 0, "981": 0, "999": 0}

    status.write_text("Name:\ttest\nUid:\t997\t997\t997\t997\n", encoding="ascii")
    with pytest.raises(TX.SnapshotContractError, match="reserved Runner role identity has live processes"):
        TX._bootstrap_process_counts({997, 981, 999})


def test_bootstrap_generation_repair_reuses_only_the_authoritative_single_record(
        monkeypatch):
    tx = {"activation_state": {"vst-runner.service": False,
                               "vst-dispatcher.service": False},
          "marker_path": "/isolated/marker", "transaction_id": "c" * 32,
          "marker_identity": (3, 4)}
    record = _bootstrap_record()
    events = []
    observations = iter([
        _proof(record=record, generation_absent=True),
        _proof(record=record, generation_absent=False, generation_matches=True),
    ])
    monkeypatch.setattr(TX, "verify_durable_marker", lambda *_args: None)
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: None)
    monkeypatch.setattr(TX, "_verify_bootstrap_guards", lambda _tx: None)
    monkeypatch.setattr(TX, "observe_bootstrap_predecessor",
                        lambda **_kwargs: next(observations))
    monkeypatch.setattr(TX, "_verify_pinned_runtime",
                        lambda: "/isolated/pinned-ee")
    monkeypatch.setattr(TX, "_hash_file", lambda path: (
        TX.RUNNER_FENCE_SOURCE_SHA256 if path.endswith("runner_fence.py")
        else TX.RUNNER_CONTRACTS_SOURCE_SHA256))
    class Completed:
        returncode = 0
        stdout = b""
        stderr = b""
    def fake_run(argv, **kwargs):
        events.append((argv, kwargs))
        return Completed()
    monkeypatch.setattr(TX.subprocess, "run", fake_run)

    result = TX.ensure_bootstrap_predecessor(tx)

    assert result["generation_matches_ledger"] is True
    assert len(events) == 1
    assert "/isolated/pinned-ee" in events[0][0][-1]
    assert "_publish_generation" in events[0][0][-1]
    assert "bootstrap_empty" not in events[0][0][-1]


def test_pinned_bootstrap_invokes_only_the_pinned_primitive_and_validates_its_receipt(
        monkeypatch):
    import ast

    record = _bootstrap_record()
    commands = []
    monkeypatch.setattr(TX, "_verify_pinned_runtime", lambda: "/isolated/pinned-ee")
    class Completed:
        returncode = 0
        stdout = TX._canonical(record) + b"\n"
        stderr = b""
    def fake_run(argv, **kwargs):
        commands.append((argv, kwargs))
        return Completed()
    monkeypatch.setattr(TX.subprocess, "run", fake_run)

    TX._invoke_pinned_bootstrap("a" * 64, ledger_was_absent=True,
                                expected_ledger_identity=None)

    assert len(commands) == 1
    argv = commands[0][0]
    assert argv[:5] == ["/usr/bin/python3.12", "-I", "-B", "-S", "-c"]
    assert len(argv) == 6
    wrapper = ast.parse(argv[5])
    embedded_source = ast.literal_eval(wrapper.body[0].value.args[0])
    assert "import hashlib, json, os, stat, sys" in embedded_source
    assert "from tools.vst.runner_fence import bootstrap_empty" in embedded_source
    assert "a" * 64 in embedded_source
    assert commands[0][1]["cwd"] == "/"


def _isolated_pinned_bootstrap_harness(monkeypatch, tmp_path, *, ledger_initial="absent",
                                      fail_parent_fsync=False, race=None):
    """Run the actual embedded bootstrap preflight against only temporary paths."""
    import ast
    import contextlib
    import fcntl
    import io
    import json
    import sys
    import types

    private = tmp_path / "ledger-parent"
    private.mkdir(mode=0o700)
    os.chmod(private, 0o700)
    ledger = private / "fence-ledger.json"
    generation = tmp_path / "generation.json"
    config_file = tmp_path / "fence.json"
    config = {"ledger_path": str(ledger), "generation_record_path": str(generation)}
    config_raw = TX._canonical(config)
    config_file.write_bytes(config_raw)
    os.chmod(config_file, 0o600)
    sentinel = tmp_path / "sentinel.bin"
    sentinel.write_bytes(b"preserve-me\n")
    if ledger_initial == "empty":
        ledger.write_bytes(b"")
        os.chmod(ledger, 0o600)
    elif ledger_initial == "nonempty":
        ledger.write_bytes(b"preserve-ledger-bytes\n")
        os.chmod(ledger, 0o600)
    elif ledger_initial != "absent":
        raise AssertionError(f"unknown ledger setup: {ledger_initial}")

    monkeypatch.setattr(TX, "_FENCE_LEDGER", str(ledger))
    monkeypatch.setattr(TX, "_FENCE_GENERATION", str(generation))
    record = _bootstrap_record()
    events = []
    callback_started = {"value": False}
    original_open, original_fsync = os.open, os.fsync
    original_close, original_readlink = os.close, os.readlink
    original_replace = os.replace

    def open_path(path, flags, *args, **kwargs):
        if path == "/etc/vst-runner/fence.json":
            path = config_file
        return original_open(path, flags, *args, **kwargs)

    def fsync(fd):
        try:
            path = original_readlink(f"/proc/self/fd/{fd}")
        except OSError:
            path = ""
        if path == str(ledger):
            events.append("ledger-fsync-after-primitive" if callback_started["value"]
                          else "ledger-fsync-before-primitive")
        elif path == str(private):
            events.append("parent-fsync-after-primitive" if callback_started["value"]
                          else "parent-fsync-before-primitive")
            if fail_parent_fsync and not callback_started["value"]:
                raise OSError("injected parent directory fsync failure")
        elif path == str(generation):
            events.append("generation-fsync")
        return original_fsync(fd)

    monkeypatch.setattr(TX.os, "open", open_path)
    monkeypatch.setattr(TX.os, "fsync", fsync)

    def lock_path(_path):
        fd = open_path(str(ledger) + ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        events.append("lifecycle-lock-acquired")
        return fd

    def bootstrap_empty():
        callback_started["value"] = True
        events.append("bootstrap-callback")
        fd = lock_path(str(ledger))
        try:
            ledger_fd = open_path(str(ledger), os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            try:
                os.write(ledger_fd, TX._canonical(record) + b"\n")
                os.fsync(ledger_fd)
            finally:
                os.close(ledger_fd)
            gen_fd = open_path(str(generation), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                               | os.O_NOFOLLOW, 0o644)
            try:
                os.write(gen_fd, TX._canonical(record) + b"\n")
                os.fsync(gen_fd)
            finally:
                os.close(gen_fd)
            parent_fd = open_path(str(private), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        finally:
            os.close(fd)
        return record

    pinned_module = types.ModuleType("tools.vst.runner_fence")
    pinned_module.bootstrap_empty = bootstrap_empty
    pinned_module._load_root_json = lambda _path: config
    pinned_module._lock_path = lock_path
    monkeypatch.setitem(sys.modules, "tools.vst.runner_fence", pinned_module)
    import tools.vst as vst_package
    monkeypatch.setattr(vst_package, "runner_fence", pinned_module, raising=False)

    def verify_runtime():
        if race == "replace-inode":
            replacement = tmp_path / "replacement-ledger"
            replacement.write_bytes(b"")
            os.chmod(replacement, 0o600)
            original_replace(replacement, ledger)
        elif race == "replace-with-nonempty":
            replacement = tmp_path / "replacement-ledger"
            replacement.write_bytes(b"do-not-truncate\n")
            os.chmod(replacement, 0o600)
            original_replace(replacement, ledger)
        elif race == "replace-with-symlink":
            ledger.unlink()
            ledger.symlink_to(sentinel)
        return "/isolated/pinned-runtime"
    monkeypatch.setattr(TX, "_verify_pinned_runtime", verify_runtime)

    class Completed:
        def __init__(self, returncode, stdout=b"", stderr=b""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def local_subprocess(argv, **_kwargs):
        wrapper = ast.parse(argv[-1])
        source = ast.literal_eval(wrapper.body[0].value.args[0])
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                exec(compile(source, "<isolated-pinned-bootstrap>", "exec"), {})
        except BaseException as exc:
            return Completed(1, stderr=(type(exc).__name__ + ": " + str(exc)).encode())
        return Completed(0, output.getvalue().encode("utf-8"))
    monkeypatch.setattr(TX.subprocess, "run", local_subprocess)

    def observe(**_kwargs):
        exists = ledger.exists() and not ledger.is_symlink()
        if not exists:
            proof = _proof(ledger_absent=True, ledger_empty=False, generation_absent=True)
        else:
            info = ledger.lstat()
            if info.st_size == 0:
                proof = _proof(ledger_absent=False, ledger_empty=True,
                               ledger_identity={"device": info.st_dev, "inode": info.st_ino},
                               generation_absent=not generation.exists())
            else:
                proof = _proof(record=record, ledger_absent=False, ledger_empty=False,
                               ledger_identity={"device": info.st_dev, "inode": info.st_ino},
                               generation_absent=not generation.exists(),
                               generation_matches=generation.exists())
        proof["fence_config_sha256"] = hashlib.sha256(config_raw).hexdigest()
        if generation.exists():
            proof["generation_absent"] = False
        return proof
    monkeypatch.setattr(TX, "observe_bootstrap_predecessor", observe)
    monkeypatch.setattr(TX, "verify_durable_marker", lambda *_args: None)
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: {})
    monkeypatch.setattr(TX, "_verify_bootstrap_guards", lambda _tx: None)
    tx = {"activation_state": {"vst-runner.service": False,
                               "vst-dispatcher.service": False},
          "marker_path": str(tmp_path / "transaction.marker"),
          "transaction_id": "f" * 32, "marker_identity": (1, 2)}
    return tx, ledger, generation, sentinel, events, observe, record


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="embedded bootstrap durability test requires POSIX root and flock")
@pytest.mark.parametrize("ledger_initial", ["absent", "empty"])
def test_empty_ledger_and_parent_are_fsynced_before_pinned_primitive_and_record(
        tmp_path, monkeypatch, ledger_initial):
    tx, ledger, generation, _sentinel, events, _observe, record = \
        _isolated_pinned_bootstrap_harness(monkeypatch, tmp_path, ledger_initial=ledger_initial)

    proof = TX.ensure_bootstrap_predecessor(tx)

    assert proof["ledger_empty"] is False
    assert proof["ledger_record"] == record
    assert ledger.stat().st_size > 0
    assert generation.exists()
    assert events.index("ledger-fsync-before-primitive") < events.index("parent-fsync-before-primitive")
    assert events.index("parent-fsync-before-primitive") < events.index("bootstrap-callback")
    assert events.index("bootstrap-callback") < events.index("ledger-fsync-after-primitive")
    assert events.index("ledger-fsync-after-primitive") < events.index("generation-fsync")
    assert events.count("lifecycle-lock-acquired") == 2


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="embedded bootstrap durability test requires POSIX root and flock")
def test_parent_fsync_failure_leaves_empty_old_only_state_and_never_calls_primitive(
        tmp_path, monkeypatch):
    tx, ledger, generation, _sentinel, events, observe, _record = \
        _isolated_pinned_bootstrap_harness(monkeypatch, tmp_path, fail_parent_fsync=True)

    with pytest.raises(TX.SnapshotContractError, match="pinned Runner bootstrap primitive failed"):
        TX.ensure_bootstrap_predecessor(tx)

    identity_before_recovery = ledger.lstat()
    assert ledger.read_bytes() == b""
    assert not generation.exists()
    assert "bootstrap-callback" not in events
    empty_proof = TX.ensure_bootstrap_predecessor(tx, create_baseline=False)
    identity_after_recovery = ledger.lstat()
    assert empty_proof["ledger_empty"] is True
    assert empty_proof["ledger_record"] is None
    assert (identity_after_recovery.st_dev, identity_after_recovery.st_ino) == (
        identity_before_recovery.st_dev, identity_before_recovery.st_ino)
    assert not generation.exists()
    assert "bootstrap-callback" not in events
    assert observe()["live_root"]["kind"] == "predecessor"


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="embedded bootstrap race test requires POSIX root and flock")
@pytest.mark.parametrize("race, expected_bytes", [
    ("replace-inode", b""),
    ("replace-with-nonempty", b"do-not-truncate\n"),
    ("replace-with-symlink", b"preserve-me\n"),
])
def test_ledger_inode_race_nonempty_or_symlink_is_refused_without_overwrite(
        tmp_path, monkeypatch, race, expected_bytes):
    tx, ledger, generation, sentinel, events, _observe, _record = \
        _isolated_pinned_bootstrap_harness(monkeypatch, tmp_path,
                                           ledger_initial="empty", race=race)

    with pytest.raises(TX.SnapshotContractError, match="pinned Runner bootstrap primitive failed"):
        TX.ensure_bootstrap_predecessor(tx)

    assert "bootstrap-callback" not in events
    assert not generation.exists()
    if race == "replace-with-symlink":
        assert ledger.is_symlink()
        assert ledger.resolve() == sentinel
        assert sentinel.read_bytes() == expected_bytes
    else:
        assert not ledger.is_symlink()
        assert ledger.read_bytes() == expected_bytes


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="partial ledger validation requires POSIX root metadata")
def test_nonempty_partial_ledger_is_rejected_without_replacement_or_truncation(
        tmp_path, monkeypatch):
    ledger = tmp_path / "fence-ledger.json"
    raw = b'{"state":"BOOTSTRAP_EMPTY"'
    ledger.write_bytes(raw)
    os.chmod(ledger, 0o600)
    original_open = os.open
    monkeypatch.setattr(TX.os, "open", lambda path, flags, *args, **kwargs:
                        original_open(ledger if path == TX._FENCE_LEDGER else path,
                                      flags, *args, **kwargs))
    original_stat = os.stat
    monkeypatch.setattr(TX.os, "stat", lambda path, *args, **kwargs:
                        original_stat(ledger if path == TX._FENCE_LEDGER else path,
                                      *args, **kwargs))

    with pytest.raises(TX.SnapshotContractError, match="partial tail"):
        TX.read_fence_ledger(TX._FENCE_LEDGER, allow_empty=True)

    assert ledger.read_bytes() == raw


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="runtime masks are root-owned POSIX symlinks")
def test_bootstrap_requires_both_exact_journal_owned_runtime_masks(tmp_path, monkeypatch):
    import os as os_module

    mask_root = tmp_path / "systemd"
    mask_root.mkdir()
    units = ("vst-runner.service", "vst-dispatcher.service")
    masks = {}
    for index, unit in enumerate(units, start=1):
        link = mask_root / unit
        link.symlink_to("/dev/null")
        info = link.lstat()
        masks[unit] = {"device": info.st_dev, "inode": info.st_ino, "target": "/dev/null"}
    record = {"runtime_masks": masks}
    original_lstat, original_readlink = os_module.lstat, os_module.readlink
    monkeypatch.setattr(TX, "_read_journal", lambda _path: [record])
    monkeypatch.setattr(TX.os, "lstat", lambda path, *args, **kwargs:
                        original_lstat(mask_root / path.rsplit("/", 1)[-1])
                        if path.startswith("/run/systemd/system/")
                        else original_lstat(path, *args, **kwargs))
    monkeypatch.setattr(TX.os, "readlink", lambda path, *args, **kwargs:
                        original_readlink(mask_root / path.rsplit("/", 1)[-1])
                        if path.startswith("/run/systemd/system/")
                        else original_readlink(path, *args, **kwargs))

    assert TX._journal_masks({"journal_path": "isolated"}) == masks
    wrong = {**record, "runtime_masks": {**masks,
             "vst-runner.service": {**masks["vst-runner.service"], "inode": -1}}}
    monkeypatch.setattr(TX, "_read_journal", lambda _path: [wrong])
    with pytest.raises(TX.SnapshotContractError, match="exact transaction-owned unit mask"):
        TX._journal_masks({"journal_path": "isolated"})


def test_bootstrap_persistent_guards_must_match_all_pinned_files_and_loaded_conditions(
        tmp_path, monkeypatch):
    guard = str(tmp_path / "runner.conf")
    expected = {"state": "file", "sha256": "a" * 64}
    monkeypatch.setattr(TX, "PREINSTALLED_GUARD_PATHS", (guard,))
    monkeypatch.setattr(TX, "_config_fingerprint", lambda path: (
        expected if path == guard else {"state": "absent"}, b"pinned"))
    tx = {"configuration_state": {guard: {"expected_new": expected}}}
    calls = []
    class Completed:
        returncode = 0
        stdout = b"Conditions=ConditionPathExists=!/var/lib/vst-runner/private/snapshot-transaction-incomplete.json\n"
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return Completed()
    monkeypatch.setattr(TX.subprocess, "run", fake_run)

    TX._verify_bootstrap_guards(tx)

    assert len(calls) == 2
    assert all("show" in call and "--property=Conditions" in call for call in calls)

    class MissingCondition(Completed):
        stdout = b"Conditions=ConditionPathExists=/tmp/other\n"
    monkeypatch.setattr(TX.subprocess, "run", lambda *_args, **_kwargs: MissingCondition())
    with pytest.raises(TX.SnapshotContractError, match="persistent transaction guard"):
        TX._verify_bootstrap_guards(tx)


def test_bootstrap_predecessor_emits_one_pinned_baseline_then_requires_ledger_match(monkeypatch):
    tx = {"activation_state": {"vst-runner.service": False,
                               "vst-dispatcher.service": False},
          "marker_path": "/isolated/marker", "transaction_id": "a" * 32,
          "marker_identity": (1, 2)}
    events = []
    record = _bootstrap_record()
    observations = iter([
        _proof(ledger_absent=True, generation_absent=True),
        _proof(record=record, generation_matches=True),
    ])
    monkeypatch.setattr(TX, "verify_durable_marker",
                        lambda *args: events.append(("marker", args)))
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: events.append(("masks", None)))
    monkeypatch.setattr(TX, "_verify_bootstrap_guards",
                        lambda _tx: events.append(("guards", None)))
    monkeypatch.setattr(TX, "observe_bootstrap_predecessor",
                        lambda **kwargs: events.append(("observe", kwargs)) or next(observations))
    monkeypatch.setattr(TX, "_invoke_pinned_bootstrap",
                        lambda digest, **kwargs: events.append(("bootstrap", digest, kwargs)))

    result = TX.ensure_bootstrap_predecessor(tx)

    assert result["ledger_record_sha256"] == record["record_sha256"]
    assert [event[0] for event in events] == [
        "marker", "masks", "guards", "observe", "bootstrap", "observe"]
    assert events[3][1] == {"allow_missing_ledger": True, "allow_candidate_root": False}
    assert events[4][1] == "1" * 64
    assert events[4][2] == {"ledger_was_absent": True, "expected_ledger_identity": None}


@pytest.mark.parametrize("activation", [
    {"vst-runner.service": True, "vst-dispatcher.service": False},
    {"vst-runner.service": False, "vst-dispatcher.service": True},
])
def test_bootstrap_refuses_hot_or_mixed_predecessor_before_any_target_access(monkeypatch, activation):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("cold proof or bootstrap was accessed before activation rejection")

    monkeypatch.setattr(TX, "verify_durable_marker", unexpected)
    tx = {"activation_state": activation}

    with pytest.raises(TX.SnapshotContractError, match="both services originally inactive"):
        TX.ensure_bootstrap_predecessor(tx)


def test_cold_runner_receipt_is_distinct_and_requires_generation_bound_fence(monkeypatch):
    record = _bootstrap_record()
    proof = _proof(record=record)
    tx = {"state": "FENCED", "journal_path": "isolated-journal", "activation_state": {
        "vst-runner.service": False, "vst-dispatcher.service": False}}
    facts = []
    monkeypatch.setattr(TX, "_cold_proof_current", lambda _proof, **_kwargs: proof)
    monkeypatch.setattr(TX, "_append_journal",
                        lambda _path, transaction, state, **extra:
                        facts.append((state, extra)) or transaction.update(state=state))
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: facts.append(("masks", {})))
    monkeypatch.setattr(TX, "_verify_bootstrap_guards", lambda _tx: facts.append(("guards", {})))

    TX.record_dispatcher_bootstrap_quiescent(tx, proof=proof)
    TX.record_runner_bootstrap_empty(tx, proof=proof)

    assert tx["state"] == "RUNNER_BOOTSTRAP_EMPTY"
    assert [state for state, _ in facts] == ["DISPATCHER_DRAINED", "masks", "guards",
                                            "RUNNER_BOOTSTRAP_EMPTY"]
    runner_receipt = facts[-1][1]
    assert runner_receipt["runner_fence_record_sha256"] == record["record_sha256"]
    assert runner_receipt["runner_invocation_id_absent"] is True


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="real root-owned journal publication requires POSIX root")
def test_cold_receipts_are_published_as_a_real_root_owned_hash_chained_journal(
        tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    os.chmod(private, 0o700)
    journal = private / "journal.jsonl"
    tx = {
        "transaction_id": "a" * 32,
        "deployment_commit": "b" * 40,
        "task_source_head": TX.TASK_HEAD,
        "task_source_tree_sha1": TX.TASK_TREE,
        "live_path": "/isolated/live",
        "stage_path": "/isolated/stage",
        "old_device": 1,
        "old_inode": 2,
        "old_head": TX.EXPECTED_PREDECESSOR_HEAD,
        "old_tree_sha1": "38a0a60b6170d068beb370c62f25b008d246902f",
        "old_mode": 0o755,
        "candidate_device": 3,
        "candidate_inode": 4,
        "candidate_readonly_git_proof": {"status_clean": True},
        "activation_state": {"vst-runner.service": False,
                              "vst-dispatcher.service": False},
        "configuration_state": {},
        "journal_path": str(journal),
        "journal_root": str(private),
        "private_root": str(private),
        "marker_path": "/isolated/marker",
        "recovery_prefix": "/isolated/old-",
        "format": "vst-snapshot-transaction-v1",
        "state": "FENCED",
    }
    TX._append_journal(str(journal), tx, "FENCED")
    record = _bootstrap_record()
    proof = _proof(record=record)
    monkeypatch.setattr(TX, "_cold_proof_current", lambda _proof, **_kwargs: proof)
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: None)
    monkeypatch.setattr(TX, "_verify_bootstrap_guards", lambda _tx: None)

    TX.record_dispatcher_bootstrap_quiescent(tx, proof=proof)
    TX.record_runner_bootstrap_empty(tx, proof=proof)

    journal_info = journal.stat()
    assert stat.S_IMODE(journal_info.st_mode) == 0o600
    assert journal_info.st_uid == 0 and journal_info.st_gid == 0
    records = TX._read_journal(str(journal))
    assert [item["state"] for item in records] == [
        "FENCED", "DISPATCHER_DRAINED", "RUNNER_BOOTSTRAP_EMPTY"]
    assert records[-1]["runner_fence_record_sha256"] == record["record_sha256"]
    assert records[-1]["sequence"] == 3
    assert records[-1]["previous_record_sha256"] == records[-2]["record_sha256"]


def test_cold_runner_receipt_rejects_missing_or_derived_generation_evidence(monkeypatch):
    tx = {"state": "DISPATCHER_DRAINED", "journal_path": "isolated-journal",
          "activation_state": {
        "vst-runner.service": False, "vst-dispatcher.service": False}}
    monkeypatch.setattr(TX, "_cold_proof_current", lambda _proof, **_kwargs:
                        _proof)
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: None)
    monkeypatch.setattr(TX, "_verify_bootstrap_guards", lambda _tx: None)
    no_generation = _proof(record=_bootstrap_record(), generation_matches=False)

    with pytest.raises(TX.SnapshotContractError, match="exact cold BOOTSTRAP_EMPTY"):
        TX.record_runner_bootstrap_empty(tx, proof=no_generation)
    assert tx["state"] == "DISPATCHER_DRAINED"


def test_durable_empty_ledger_proof_cannot_be_recorded_as_runner_bootstrap_receipt(
        monkeypatch):
    tx = {"state": "DISPATCHER_DRAINED", "journal_path": "isolated-journal",
          "activation_state": {"vst-runner.service": False,
                               "vst-dispatcher.service": False}}
    empty_proof = _proof(ledger_absent=False, ledger_empty=True,
                         ledger_identity={"device": 9, "inode": 10},
                         generation_absent=True)
    monkeypatch.setattr(TX, "_cold_proof_current", lambda _proof, **_kwargs: empty_proof)
    monkeypatch.setattr(TX, "_journal_masks",
                        lambda _tx: pytest.fail("empty ledger must not advance to a Runner receipt"))
    monkeypatch.setattr(TX, "_verify_bootstrap_guards",
                        lambda _tx: pytest.fail("empty ledger must not advance to a Runner receipt"))

    with pytest.raises(TX.SnapshotContractError, match="exact cold BOOTSTRAP_EMPTY"):
        TX.record_runner_bootstrap_empty(tx, proof=empty_proof)
    assert tx["state"] == "DISPATCHER_DRAINED"


def test_bootstrap_exchange_requires_a_durable_cold_receipt_before_path_mutation(monkeypatch):
    tx = {"state": "RUNNER_BOOTSTRAP_EMPTY", "activation_state": {
        "vst-runner.service": False, "vst-dispatcher.service": False},
        "journal_path": "isolated-journal"}
    monkeypatch.setattr(TX, "_read_journal", lambda _path: [])
    monkeypatch.setattr(TX, "exchange_directories",
                        lambda *_args: pytest.fail("snapshot exchange ran without durable cold receipt"))

    with pytest.raises(TX.SnapshotContractError, match="lacks its durable bootstrap receipt"):
        TX.exchange_candidate(tx, recovery_path="/isolated/old", marker_path="/isolated/marker")


def _candidate_live_recovery_transaction(receipt_records):
    return {
        "state": "ACTIVATION_READY",
        "activation_state": {"vst-runner.service": False,
                              "vst-dispatcher.service": False},
        "marker_present": False,
        "records": receipt_records,
        "configuration_state": {"/isolated/config.json": {
            "expected_current": {"state": "file", "sha256": "2" * 64},
            "expected_new": {"state": "file", "sha256": "3" * 64},
        }},
        "configuration_backup_records": {},
        "journal_path": "isolated-journal",
        "live_path": "/isolated/live",
        "old_head": TX.EXPECTED_PREDECESSOR_HEAD,
        "old_tree_sha1": "38a0a60b6170d068beb370c62f25b008d246902f",
    }


def _candidate_proof(record):
    proof = _proof(record=record, generation_matches=True)
    proof["live_root"] = {
        "kind": "candidate", "device": 3, "inode": 4, "mode": 0o555,
        "head": TX.TASK_HEAD, "tree_sha1": TX.TASK_TREE,
        "readonly_git_proof": {"head": TX.TASK_HEAD, "tree_sha1": TX.TASK_TREE,
                                "status_clean": True},
    }
    return proof


def _isolate_candidate_live_recovery(monkeypatch, proof):
    monkeypatch.setattr(TX, "_cold_proof_current", lambda _proof, **_kwargs: proof)
    monkeypatch.setattr(TX, "reconcile_snapshot_paths", lambda _tx: {
        "live": "candidate", "old_location": "recovery", "candidate_location": "live"})
    monkeypatch.setattr(TX, "_config_fingerprint", lambda _path: (
        {"state": "file", "sha256": "3" * 64}, b"candidate-config"))
    monkeypatch.setattr(TX, "_verify_git_readonly", lambda _path: {
        "head": TX.TASK_HEAD, "tree_sha1": TX.TASK_TREE, "status_clean": True})
    monkeypatch.setattr(TX, "_append_journal", lambda _path, transaction, state, **facts: {
        "state": state, **facts})


def test_candidate_live_recovery_accepts_fresh_proof_bound_to_durable_cold_receipt(monkeypatch):
    record = _bootstrap_record()
    proof = _candidate_proof(record)
    receipt = {"state": "RUNNER_BOOTSTRAP_EMPTY",
               "runner_fence_record_sha256": record["record_sha256"]}
    tx = _candidate_live_recovery_transaction([receipt])
    _isolate_candidate_live_recovery(monkeypatch, proof)

    result = TX.recover_snapshot_transaction(
        tx,
        guards_verified={"vst-runner.service": True, "vst-dispatcher.service": True},
        runtime_masks_owned={},
        services_quiesced={"vst-runner.service": True, "vst-dispatcher.service": True},
        bootstrap_proof=proof,
    )

    assert result["safe_tree"] == "candidate"
    assert result["safe_head"] == TX.TASK_HEAD
    assert result["marker_present"] is False
    assert result["runtime_masks_must_remain"] is True


def test_candidate_live_recovery_refuses_absent_or_unmatched_cold_receipt(monkeypatch):
    record = _bootstrap_record()
    proof = _candidate_proof(record)
    tx = _candidate_live_recovery_transaction([])
    _isolate_candidate_live_recovery(monkeypatch, proof)

    with pytest.raises(TX.SnapshotContractError,
                       match="lacks its durable authentic cold bootstrap receipt"):
        TX.recover_snapshot_transaction(
            tx,
            guards_verified={"vst-runner.service": True, "vst-dispatcher.service": True},
            runtime_masks_owned={},
            services_quiesced={"vst-runner.service": True, "vst-dispatcher.service": True},
            bootstrap_proof=proof,
        )


def test_candidate_live_recovery_refuses_cold_proof_when_original_activation_was_hot(monkeypatch):
    record = _bootstrap_record()
    proof = _candidate_proof(record)
    tx = _candidate_live_recovery_transaction([{
        "state": "RUNNER_BOOTSTRAP_EMPTY",
        "runner_fence_record_sha256": record["record_sha256"]}])
    tx["activation_state"]["vst-runner.service"] = True
    monkeypatch.setattr(TX, "_cold_proof_current",
                        lambda *_args, **_kwargs: pytest.fail("cold proof accepted for hot predecessor"))

    with pytest.raises(TX.SnapshotContractError,
                       match="valid only for originally inactive services"):
        TX.recover_snapshot_transaction(
            tx,
            guards_verified={"vst-runner.service": True, "vst-dispatcher.service": True},
            runtime_masks_owned={},
            services_quiesced={"vst-runner.service": True, "vst-dispatcher.service": True},
            bootstrap_proof=proof,
        )


def _real_snapshot_transaction(tmp_path, live, stage, *, old_identity, candidate_identity,
                               configuration_state=None, backup_records=None):
    private = tmp_path / "transaction-private"
    private.mkdir(mode=0o700)
    os.chmod(private, 0o700)
    journal = private / "journal.jsonl"
    transaction_id = "d" * 32
    recovery_prefix = str(tmp_path / "retained-")
    old_head = TX.EXPECTED_PREDECESSOR_HEAD
    old_tree = "38a0a60b6170d068beb370c62f25b008d246902f"
    return {
        "transaction_id": transaction_id,
        "deployment_commit": "e" * 40,
        "task_source_head": TX.TASK_HEAD,
        "task_source_tree_sha1": TX.TASK_TREE,
        "live_path": str(live),
        "stage_path": str(stage),
        "recovery_path": recovery_prefix + old_head + "-" + transaction_id,
        "old_device": old_identity.st_dev,
        "old_inode": old_identity.st_ino,
        "old_head": old_head,
        "old_tree_sha1": old_tree,
        "old_mode": 0o755,
        "candidate_device": candidate_identity.st_dev,
        "candidate_inode": candidate_identity.st_ino,
        "candidate_readonly_git_proof": {"head": TX.TASK_HEAD,
                                          "tree_sha1": TX.TASK_TREE,
                                          "status_clean": True},
        "activation_state": {"vst-runner.service": False,
                              "vst-dispatcher.service": False},
        "configuration_state": configuration_state or {},
        "configuration_backup_records": backup_records or {},
        "journal_path": str(journal),
        "journal_root": str(private),
        "private_root": str(private),
        "marker_path": str(tmp_path / "marker.json"),
        "marker_identity": (11, 12),
        "recovery_prefix": recovery_prefix,
        "format": "vst-snapshot-transaction-v1",
    }


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="snapshot exchange requires POSIX root and renameat2")
def test_cold_exchange_atomically_swaps_and_retains_real_snapshot_directories(
        tmp_path, monkeypatch):
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    stage.mkdir()
    (live / "snapshot.txt").write_text("predecessor", encoding="ascii")
    (stage / "snapshot.txt").write_text("candidate", encoding="ascii")
    os.chmod(live, 0o755)
    os.chmod(stage, 0o555)
    old_identity, candidate_identity = live.lstat(), stage.lstat()
    tx = _real_snapshot_transaction(tmp_path, live, stage,
                                    old_identity=old_identity,
                                    candidate_identity=candidate_identity)
    tx.update({"state": "RUNNER_BOOTSTRAP_EMPTY", "marker_present": True})
    record = _bootstrap_record()
    proof = _proof(record=record, generation_matches=True)
    masks = {unit: {"device": 1, "inode": index, "target": "/dev/null"}
             for index, unit in enumerate(("vst-runner.service", "vst-dispatcher.service"), 1)}
    TX._append_journal(tx["journal_path"], tx, "FENCED", runtime_masks=masks)
    TX._append_journal(tx["journal_path"], tx, "DISPATCHER_DRAINED")
    TX._append_journal(tx["journal_path"], tx, "RUNNER_BOOTSTRAP_EMPTY",
                       runner_fence_record_sha256=record["record_sha256"],
                       cold_predecessor_proof=proof)
    cleared = []
    monkeypatch.setattr(TX, "_cold_proof_current", lambda _proof, **_kwargs: proof)
    monkeypatch.setattr(TX, "_journal_masks", lambda _tx: masks)
    monkeypatch.setattr(TX, "_verify_bootstrap_guards", lambda _tx: None)
    monkeypatch.setattr(TX, "_verify_git_readonly", lambda _root: {
        "head": TX.TASK_HEAD, "tree_sha1": TX.TASK_TREE, "status_clean": True})
    def tree_identity(path):
        info = os.lstat(path)
        if (info.st_dev, info.st_ino) == (candidate_identity.st_dev, candidate_identity.st_ino):
            return TX.TASK_HEAD, TX.TASK_TREE, "true"
        return TX.EXPECTED_PREDECESSOR_HEAD, "38a0a60b6170d068beb370c62f25b008d246902f", "false"
    monkeypatch.setattr(TX, "_tree_identity", tree_identity)
    monkeypatch.setattr(TX, "clear_durable_marker",
                        lambda path, identifier, identity:
                        cleared.append((path, identifier, identity)))

    TX.exchange_candidate(tx, recovery_path=tx["recovery_path"], marker_path=tx["marker_path"])

    recovery = Path(tx["recovery_path"])
    assert (live / "snapshot.txt").read_text(encoding="ascii") == "candidate"
    assert (recovery / "snapshot.txt").read_text(encoding="ascii") == "predecessor"
    assert not stage.exists()
    assert (os.lstat(live).st_dev, os.lstat(live).st_ino) == (
        candidate_identity.st_dev, candidate_identity.st_ino)
    assert (os.lstat(recovery).st_dev, os.lstat(recovery).st_ino) == (
        old_identity.st_dev, old_identity.st_ino)
    assert tx["state"] == "MARKER_CLEARED"
    assert cleared == [(tx["marker_path"], tx["transaction_id"], tx["marker_identity"])]
    journal_states = [item["state"] for item in TX._read_journal(tx["journal_path"])]
    assert journal_states[-5:] == ["EXCHANGED", "OLD_RETAINED", "TARGET_VERIFIED",
                                   "ACTIVATION_READY", "MARKER_CLEARED"]


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="predecessor recovery requires POSIX root and renameat2")
def test_interrupted_partial_configuration_restore_uses_real_backup_and_snapshot_filesystems(
        tmp_path, monkeypatch):
    live = tmp_path / "live"
    stage = tmp_path / "stage"
    live.mkdir()
    stage.mkdir()
    (live / "tree.txt").write_text("predecessor", encoding="ascii")
    (stage / "tree.txt").write_text("candidate", encoding="ascii")
    os.chmod(live, 0o755)
    os.chmod(stage, 0o555)
    old_identity, candidate_identity = live.lstat(), stage.lstat()

    config_dir = tmp_path / "configuration"
    config_dir.mkdir(mode=0o700)
    first = config_dir / "first.conf"
    second = config_dir / "second.conf"
    first.write_bytes(b"candidate-first\n")
    second.write_bytes(b"predecessor-second\n")
    os.chmod(first, 0o600)
    os.chmod(second, 0o640)
    backup_dir = tmp_path / "predecessor-backups"
    backup_dir.mkdir(mode=0o700)
    backups = {}
    states = {}
    for path, old_payload, new_payload in (
            (first, b"predecessor-first\n", b"candidate-first\n"),
            (second, b"predecessor-second\n", b"candidate-second\n")):
        backup = backup_dir / (path.name + ".old")
        backup.write_bytes(old_payload)
        os.chmod(backup, 0o600)
        prior = {"state": "file", "uid": 0, "gid": 0, "mode": 0o640,
                 "size": len(old_payload), "sha256": hashlib.sha256(old_payload).hexdigest()}
        new_mode = 0o600
        target = {"state": "file", "uid": 0, "gid": 0, "mode": new_mode,
                  "size": len(new_payload), "sha256": hashlib.sha256(new_payload).hexdigest()}
        states[str(path)] = {"expected_current": prior, "expected_new": target}
        backups[str(path)] = {"predecessor_backup": str(backup)}
    tx = _real_snapshot_transaction(tmp_path, live, stage,
                                    old_identity=old_identity,
                                    candidate_identity=candidate_identity,
                                    configuration_state=states,
                                    backup_records=backups)
    tx.update({"state": "RECOVERY_REQUIRED", "marker_present": False})
    masks = {unit: {"device": 7, "inode": index, "target": "/dev/null"}
             for index, unit in enumerate(("vst-runner.service", "vst-dispatcher.service"), 1)}
    TX._append_journal(tx["journal_path"], tx, "FENCED", runtime_masks=masks)
    TX._append_journal(tx["journal_path"], tx, "RECOVERY_REQUIRED",
                       reason="simulated interruption during per-file configuration publication")
    tx["records"] = TX._read_journal(tx["journal_path"])
    monkeypatch.setattr(TX, "_tree_identity", lambda path: (
        (TX.EXPECTED_PREDECESSOR_HEAD, "38a0a60b6170d068beb370c62f25b008d246902f", "false")
        if path == str(live) else (TX.TASK_HEAD, TX.TASK_TREE, "true")))

    result = TX.recover_snapshot_transaction(
        tx,
        guards_verified={"vst-runner.service": True, "vst-dispatcher.service": True},
        runtime_masks_owned=masks,
        services_quiesced={"vst-runner.service": True, "vst-dispatcher.service": True},
    )

    assert first.read_bytes() == b"predecessor-first\n"
    assert second.read_bytes() == b"predecessor-second\n"
    assert stat.S_IMODE(first.stat().st_mode) == 0o640
    assert stat.S_IMODE(second.stat().st_mode) == 0o640
    assert (live / "tree.txt").read_text(encoding="ascii") == "predecessor"
    assert (stage / "tree.txt").read_text(encoding="ascii") == "candidate"
    assert result["safe_tree"] == "old"
    assert result["safe_head"] == TX.EXPECTED_PREDECESSOR_HEAD
    assert result["marker_present"] is False
    assert tx["state"] == "MARKER_CLEARED"
