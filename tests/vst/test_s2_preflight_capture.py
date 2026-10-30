"""Supervisor-owned runtime observation contract tests; no fixture is host evidence."""
from __future__ import annotations

import hashlib
import json
import posixpath
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.vst import preflight, preflight_capture as capture
from tools.vst.contracts import ContractError


RUN_ID = "s2-runtime-observation-test"
NONCE = "s2-runtime-observation-nonce"
INVOCATION_ID = "a" * 32
NOW_NS = 50_000_000_000_000
SOURCE_CONFIG = {"probe_unit": "1" * 64, "network_profile": "2" * 64}


def _observation(spec_sha256: str) -> dict:
    checks = {
        "automount_disabled": True,
        "interop_disabled": True,
        "no_container_socket": True,
        "non_root": True,
        "egress_policy_isolated": True,
        "loopback_canary": True,
        "empty_external_allowlist": True,
        "no_unapproved_host_mounts": True,
        "expected_cgroup": True,
        "runtime_namespaces_observed": True,
    }
    return {
        "schema": "VST_S2_RUNTIME_OBSERVATION_V1",
        "checked_properties": checks,
        "result": "PASS",
        "inventory": {
            "mount_table": ["rootfs / ext4 rw 0 0"],
            "windows_drive_mounts": [],
            "unapproved_host_mounts": [],
            "wsl_interop_present": False,
            "wsl_interop_enabled": False,
            "uid": 999,
            "gid": 989,
            "cgroup": ["0::/system.slice/vst-sandbox-probe.service"],
            "namespace_inodes": {"mount": 10, "network": 11, "cgroup": 12, "pid": 13},
            "network_interfaces": ["lo"],
            "network_routes": [],
            "container_socket_paths_present": [],
            "container_socket_inventory_complete": True,
            "environment_variable_names": [],
            "spec_sha256": spec_sha256,
            "network_profile_sha256": SOURCE_CONFIG["network_profile"],
            "observed_at_monotonic_ns": NOW_NS,
        },
    }


def _journal_entry(observation: dict) -> bytes:
    entry = {
        "_SYSTEMD_UNIT": capture.PROBE_UNIT,
        "_SYSTEMD_INVOCATION_ID": INVOCATION_ID,
        "_UID": "999",
        "_GID": "989",
        "_PID": "123",
        "MESSAGE": json.dumps(observation, separators=(",", ":")),
    }
    return json.dumps(entry, separators=(",", ":")).encode()


def test_supervisor_observes_exact_probe_once_and_returns_bound_evidence_in_memory(monkeypatch):
    spec_bytes = b"synthetic sandbox specification\n"
    spec_sha256 = hashlib.sha256(spec_bytes).hexdigest()
    raw_observation = _observation(spec_sha256)
    commands: list[list[str]] = []
    sequence = [
        b"running\n",
        b"",
        _journal_entry(raw_observation),
        json.dumps({
            "UNIT": capture.PROBE_UNIT,
            "INVOCATION_ID": INVOCATION_ID,
            "_PID": "1",
            "_UID": "0",
            "UNIT_RESULT": "success",
        }, separators=(",", ":")).encode(),
    ]
    claim_order: list[str] = []
    unit_state = {
        "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
        "Result": "success", "ExecMainStatus": "0", "MainPID": "0",
        "InvocationID": INVOCATION_ID,
        "PrivateNetwork": "yes", "User": "vst-worker", "Group": "vst-worker",
        "ControlGroup": "/system.slice/vst-sandbox-probe.service",
    }

    monkeypatch.setattr(capture, "os", SimpleNamespace(name="posix", geteuid=lambda: 0))
    monkeypatch.setattr(capture, "SPEC_PATH", SimpleNamespace(
        is_file=lambda: True, read_bytes=lambda: spec_bytes,
    ))
    monkeypatch.setattr(capture, "PROBE_PROFILE_PATH", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(capture, "_assert_units_inactive", lambda: claim_order.append("units-inactive"))
    monkeypatch.setattr(capture, "_assert_manager_quiescent", lambda: None)
    monkeypatch.setattr(capture, "_systemctl_show", lambda: dict(unit_state))
    monkeypatch.setattr(capture, "_require_fresh_store_targets", lambda store, anchor: (
        claim_order.append("fresh-targets"), (store, anchor)
    )[1])
    monkeypatch.setattr(capture, "_claim_observation", lambda *args: (
        claim_order.append("claim"), "c" * 64
    )[1])

    def bounded_command(argv, *, timeout):
        commands.append(list(argv))
        assert timeout in {5, 15, 95}
        return sequence.pop(0)

    monkeypatch.setattr(capture, "_bounded_command", bounded_command)
    monkeypatch.setattr(preflight.time, "monotonic_ns", lambda: NOW_NS)

    probe = capture.observe_runtime_once(
        RUN_ID, NONCE, SOURCE_CONFIG,
        store_path="/var/lib/vst-runner/private/store.sqlite3",
        anchor_path="/var/lib/vst-runner/private/store.anchor",
    )

    assert probe["run_id"] == RUN_ID and probe["nonce"] == NONCE
    assert probe["spec_sha256"] == spec_sha256 and probe["result"] == "PASS"
    assert probe["inventory"]["systemd_probe"]["unit"] == capture.PROBE_UNIT
    assert probe["inventory"]["systemd_probe"]["InvocationID"] == INVOCATION_ID
    assert probe["inventory"]["observation_claim_sha256"] == "c" * 64
    assert probe["inventory"]["source_config_sha256"] == SOURCE_CONFIG
    assert claim_order.index("fresh-targets") < claim_order.index("claim")
    assert commands == [
        [capture.SYSTEMCTL_PATH, "is-system-running"],
        [capture.SYSTEMCTL_PATH, "start", capture.PROBE_UNIT],
        [capture.JOURNALCTL_PATH, "--no-pager", "--output=json",
         f"_SYSTEMD_UNIT={capture.PROBE_UNIT}", f"_SYSTEMD_INVOCATION_ID={INVOCATION_ID}"],
        [capture.JOURNALCTL_PATH, "--no-pager", "--output=json",
         f"UNIT={capture.PROBE_UNIT}", f"INVOCATION_ID={INVOCATION_ID}", "_PID=1", "_UID=0"],
    ]
    assert sequence == []
    assert "signature" not in probe and "network_policy_attestation" not in probe["inventory"]


def test_probe_unit_identity_mismatch_refuses_before_claim_or_start(monkeypatch):
    monkeypatch.setattr(capture, "os", SimpleNamespace(name="posix", geteuid=lambda: 0))
    monkeypatch.setattr(capture, "SPEC_PATH", SimpleNamespace(
        is_file=lambda: True, read_bytes=lambda: b"spec",
    ))
    monkeypatch.setattr(capture, "PROBE_PROFILE_PATH", SimpleNamespace(is_file=lambda: True))
    monkeypatch.setattr(capture, "_assert_units_inactive", lambda: None)
    monkeypatch.setattr(capture, "_assert_manager_quiescent", lambda: None)
    monkeypatch.setattr(capture, "_require_fresh_store_targets", lambda *_: None)
    claims: list[tuple] = []
    monkeypatch.setattr(capture, "_claim_observation", lambda *args: claims.append(args))
    monkeypatch.setattr(capture, "_systemctl_show", lambda: {
        "LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
        "MainPID": "0", "PrivateNetwork": "yes", "User": "vst-worker",
        "Group": "vst-worker", "ControlGroup": "/system.slice/unexpected.service",
    })
    commands: list[list[str]] = []
    monkeypatch.setattr(capture, "_bounded_command", lambda argv, **_kw: (
        commands.append(list(argv)), b"running\n"
    )[1])

    with pytest.raises(ContractError, match="exact loaded/inactive sandbox configuration"):
        capture.observe_runtime_once(RUN_ID, NONCE, SOURCE_CONFIG,
                                     store_path="/var/lib/vst/store.db",
                                     anchor_path="/var/lib/vst/store.anchor")

    assert len(commands) == 1
    assert commands[0] == [capture.SYSTEMCTL_PATH, "is-system-running"]
    assert claims == []


def test_only_supervisor_type_notify_start_job_may_remain_pending(monkeypatch):
    monkeypatch.setattr(capture, "_bounded_command", lambda *_args, **_kwargs: (
        b"12 vst-supervisor.service start running\n"
    ))

    capture._assert_manager_quiescent()


@pytest.mark.parametrize("job", [
    "12 unrelated.service start running\n",
    "12 vst-supervisor.service stop waiting\n",
])
def test_unrelated_or_nonstart_manager_job_blocks_runtime_observation(monkeypatch, job):
    monkeypatch.setattr(capture, "_bounded_command", lambda *_args, **_kwargs: job.encode())

    with pytest.raises(ContractError, match="unrelated systemd job is pending"):
        capture._assert_manager_quiescent()


def test_dependent_services_must_be_inactive_before_runtime_observation(monkeypatch):
    calls = []

    def command(argv, **_kwargs):
        calls.append(argv)
        if "vst-runner.service" in argv:
            return b"loaded\nactive\nrunning\n123\n"
        return b"loaded\ninactive\ndead\n0\n"

    monkeypatch.setattr(capture, "_bounded_command", command)

    with pytest.raises(ContractError, match="dependent services must remain inactive"):
        capture._assert_units_inactive()

    assert len(calls) == 6
    assert "vst-runner.service" in calls[-1]


def _fake_root_fs(monkeypatch, existing: set[str]):
    fake_os = SimpleNamespace(
        path=posixpath,
        stat=lambda _path, **_kwargs: SimpleNamespace(
            st_mode=stat.S_IFDIR | 0o700, st_uid=0,
        ),
        lstat=lambda path: (
            SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0, st_nlink=1)
            if path in existing else (_raise_missing(path))
        ),
    )
    monkeypatch.setattr(capture, "os", fake_os)


def _raise_missing(path):
    raise FileNotFoundError(path)


def test_fresh_store_requires_all_six_state_paths_to_be_absent(monkeypatch):
    store = "/var/lib/vst-runner/private/store.sqlite3"
    anchor = "/var/lib/vst-runner/private/store.anchor"
    _fake_root_fs(monkeypatch, set())

    assert capture.classify_store_targets(store, anchor) == "fresh"


@pytest.mark.parametrize("existing_suffix", [
    "", "-wal", "-shm", "-journal", ".anchor", ".anchor.coord.lock",
], ids=["store", "wal", "shm", "journal", "anchor", "coord-lock"])
def test_any_partial_store_or_anchor_state_refuses_fresh_qualification(
        monkeypatch, existing_suffix):
    store = "/var/lib/vst-runner/private/store.sqlite3"
    anchor = "/var/lib/vst-runner/private/store.anchor"
    if existing_suffix == ".anchor":
        existing = {anchor}
    elif existing_suffix == ".anchor.coord.lock":
        existing = {anchor + ".coord.lock"}
    else:
        existing = {store + existing_suffix}
    _fake_root_fs(monkeypatch, existing)

    expected_error = (
        "Store and external anchor must either both exist or both be absent"
        if existing_suffix in {"", ".anchor"}
        else "orphan runtime Store sidecar or coordinator lock exists"
    )
    with pytest.raises(ContractError, match=expected_error):
        capture.classify_store_targets(store, anchor)


def test_complete_root_controlled_store_and_anchor_pair_is_recovery_state(monkeypatch):
    store = "/var/lib/vst-runner/private/store.sqlite3"
    anchor = "/var/lib/vst-runner/private/store.anchor"
    _fake_root_fs(monkeypatch, {store, anchor})

    assert capture.classify_store_targets(store, anchor) == "recovery"


@pytest.mark.skipif(__import__("os").name == "nt", reason="durable marker contract requires POSIX file descriptors")
def test_runtime_observation_claim_is_durable_single_use_and_exact(tmp_path, monkeypatch):
    import os as real_os

    private_dir = tmp_path / "private"
    private_dir.mkdir()
    marker = private_dir / "claim.json"
    payload = capture.canonical_bytes({
        "schema": "VST_S2_RUNTIME_OBSERVATION_CLAIM_V1",
        "run_id": RUN_ID, "nonce": NONCE, "spec_sha256": "a" * 64,
        "source_config_sha256": SOURCE_CONFIG,
    }) + b"\n"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(
        capture, "_observation_claim_identity",
        lambda *_args: (str(private_dir), str(marker), payload, digest),
    )

    def trusted_fstat(fd):
        info = real_os.fstat(fd)
        return SimpleNamespace(
            st_mode=info.st_mode, st_uid=0, st_gid=0,
            st_size=info.st_size, st_nlink=1,
        )

    monkeypatch.setattr(capture, "os", SimpleNamespace(
        O_RDONLY=real_os.O_RDONLY, O_WRONLY=real_os.O_WRONLY, O_CREAT=real_os.O_CREAT,
        O_EXCL=real_os.O_EXCL, O_NOFOLLOW=getattr(real_os, "O_NOFOLLOW", 0),
        O_DIRECTORY=getattr(real_os, "O_DIRECTORY", 0),
        scandir=real_os.scandir, open=real_os.open, close=real_os.close,
        read=real_os.read, write=real_os.write, fsync=real_os.fsync,
        fstat=trusted_fstat, fchown=lambda *_args: None, fchmod=real_os.fchmod,
    ))

    assert capture._claim_observation(RUN_ID, NONCE, "a" * 64, SOURCE_CONFIG) == digest
    assert marker.read_bytes() == payload
    assert capture.verify_existing_observation_claim(
        RUN_ID, NONCE, "a" * 64, SOURCE_CONFIG,
    ) == digest
    with pytest.raises(ContractError, match="already has a one-start runtime observation claim"):
        capture._claim_observation(RUN_ID, NONCE, "a" * 64, SOURCE_CONFIG)

    marker.write_bytes(payload + b" ")
    with pytest.raises(ContractError, match="claim differs from current exact inputs"):
        capture.verify_existing_observation_claim(RUN_ID, NONCE, "a" * 64, SOURCE_CONFIG)


def test_supervisor_readiness_barrier_requires_notify_and_before_runner(monkeypatch):
    properties = {
        "Type": "notify", "NotifyAccess": "main", "TimeoutStartUSec": "360s",
        "Before": "vst-runner.service", "FragmentPath": "/etc/systemd/system/vst-supervisor.service",
        "NeedDaemonReload": "no", "MainPID": "123",
    }
    monkeypatch.setattr(capture, "os", SimpleNamespace(getpid=lambda: 123))
    monkeypatch.setattr(capture, "_systemctl_properties", lambda unit, names: (
        assert_systemd_request(unit, names, properties)
    ))

    capture.assert_supervisor_readiness_barrier()


def assert_systemd_request(unit, names, properties):
    assert unit == "vst-supervisor.service"
    assert set(names) == set(properties)
    return properties


@pytest.mark.parametrize("changed", ["run", "nonce", "spec", "source_config", "claim"])
def test_deterministic_observation_binding_changes_with_every_authority_input(changed):
    values = {
        "run": RUN_ID, "nonce": NONCE, "spec": "a" * 64,
        "source_config": SOURCE_CONFIG, "claim": "c" * 64,
    }
    original = capture.runtime_observation_binding_digest(
        values["run"], values["nonce"], values["spec"], values["source_config"], values["claim"],
    )
    altered = dict(values)
    if changed in {"run", "nonce"}:
        altered[changed] = "different-" + changed
    elif changed == "source_config":
        altered[changed] = {**SOURCE_CONFIG, "network_profile": "f" * 64}
    else:
        altered[changed] = "d" * 64

    assert capture.runtime_observation_binding_digest(
        altered["run"], altered["nonce"], altered["spec"],
        altered["source_config"], altered["claim"],
    ) != original


def _supervisor_loader_harness(monkeypatch, *, store_mode, source_drift=False,
                               observation_override=None):
    import posixpath as path_module
    from tools.vst import store as store_module
    from tools.vst import supervisor as supervisor_module
    from tools.vst import supervisor_service as service

    config = json.loads((
        Path(__file__).resolve().parents[2]
        / "docs" / "sdlc" / "runtime-config" / "supervisor-service.json"
    ).read_text(encoding="utf-8"))
    config.pop("root_dispatch_issuer", None)
    config.pop("assignment_policy_path", None)
    config.pop("assignment_policy_sha256", None)
    config["peers"] = [peer for peer in config["peers"] if peer["role"] in {
        "dispatch_owner", "dispatcher", "runnerd", "signer",
    }]
    registry = {
        "s2-test-key": {
            "principal": "Codex", "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
            "public_key_path": "/etc/vst-runner/dispatch-instruction-public.pem",
        },
    }
    source_hashes = {"network_profile": "d" * 64, "supervisor_unit": "e" * 64}
    identity_calls: list[dict[str, str]] = []
    observation_calls: list[tuple] = []
    claim_checks: list[tuple] = []
    call_order: list[str] = []
    store_calls: list[tuple[str, tuple]] = []
    store_instances = []
    expected_spec = hashlib.sha256(preflight.SPEC_PATH.read_bytes()).hexdigest()

    def read_config(path, **_kwargs):
        if path == service.DEFAULT_CONFIG_PATH:
            return config
        if path == service.DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH:
            return registry
        raise AssertionError(f"unexpected controlled config read: {path}")

    def source_identity(_path, _config):
        value = dict(source_hashes)
        if source_drift and identity_calls:
            value["network_profile"] = "f" * 64
        identity_calls.append(value)
        return value

    def verify_claim(run_id, nonce, spec_sha, hashes):
        call_order.append("verify_existing_claim")
        claim_checks.append((run_id, nonce, spec_sha, dict(hashes)))
        return "c" * 64

    def observe(run_id, nonce, hashes, *, store_path, anchor_path, **options):
        call_order.append("observe_runtime_once")
        observation_calls.append((run_id, nonce, dict(hashes), store_path, anchor_path, options))
        result = {
            "run_id": run_id, "nonce": nonce, "spec_sha256": expected_spec, "result": "PASS",
            "inventory": {
                "spec_sha256": expected_spec,
                "network_profile_sha256": hashes["network_profile"],
                "namespace_inodes": {"mount": 20, "network": 21, "cgroup": 22, "pid": 13},
                "observation_claim_sha256": "c" * 64,
            },
        }
        if observation_override:
            observation_override(result, hashes)
        return result

    class FakeStore:
        def __init__(self, *_args, **_kwargs):
            store_instances.append(self)

        def ensure_preflight_consumed(self, *args):
            store_calls.append(("fresh", args))
            return True

        def require_existing_preflight_consumed(self, *args):
            store_calls.append(("recovery", args))

    class FakeSupervisor:
        def __init__(self, store, **_kwargs):
            self.store = store
            self._probe_consumed = False

    class FakeAPI:
        def __init__(self, *args, **_kwargs):
            self.args = args

    def fake_stat(path, *, follow_symlinks=False):
        del follow_symlinks
        if path == service.DISPATCH_INSTRUCTION_TRUST_REGISTRY_PATH:
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0, st_gid=0)
        raise AssertionError(f"unexpected stat request: {path}")

    monkeypatch.setattr(service, "os", SimpleNamespace(path=path_module, stat=fake_stat))
    monkeypatch.setattr(service, "_read_controlled_json", read_config)
    monkeypatch.setattr(service, "_runtime_observation_identity", source_identity)
    monkeypatch.setattr(service, "_validate_root_data_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_read_root_key", lambda path: hashlib.sha256(path.encode()).digest())
    monkeypatch.setattr(service, "AuthenticatedSupervisorAPI", FakeAPI)
    monkeypatch.setattr("tools.vst.execution_grant._trusted_root_file", lambda *_a, **_kw: None)
    monkeypatch.setattr(preflight, "_namespace_inode", lambda name: {"mnt": 10, "net": 11, "cgroup": 12, "pid": 13}[name])
    monkeypatch.setattr(capture, "classify_store_targets", lambda *_args: store_mode)
    monkeypatch.setattr(capture, "assert_supervisor_readiness_barrier", lambda: None)
    monkeypatch.setattr(capture, "assert_runtime_services_inactive", lambda: None)
    monkeypatch.setattr(capture, "observe_runtime_once", observe)
    monkeypatch.setattr(capture, "verify_existing_observation_claim", verify_claim)
    monkeypatch.setattr(store_module, "Store", FakeStore)
    monkeypatch.setattr(supervisor_module, "Supervisor", FakeSupervisor)
    return SimpleNamespace(
        service=service, config=config, hashes=source_hashes, identity_calls=identity_calls,
        observation_calls=observation_calls, claim_checks=claim_checks,
        call_order=call_order,
        store_calls=store_calls, store_instances=store_instances,
        expected_spec=expected_spec,
    )


@pytest.mark.skipif(capture.os.name == "nt", reason="Supervisor service contract requires POSIX path semantics")
def test_supervisor_fresh_start_consumes_direct_observation_before_api_is_returned(monkeypatch):
    harness = _supervisor_loader_harness(monkeypatch, store_mode="fresh")

    api, supervisor = harness.service.load_supervisor_service()

    assert len(harness.observation_calls) == 1
    observed_run, observed_nonce, observed_hashes, _store_path, _anchor_path, options = harness.observation_calls[0]
    assert (observed_run, observed_nonce, observed_hashes, options) == (
        harness.config["run_id"], harness.config["probe_nonce"], harness.hashes, {},
    )
    assert harness.claim_checks == []
    assert len(harness.store_instances) == 1
    assert harness.store_calls[0][0] == "fresh"
    run_id, nonce, spec_sha, probe_sha = harness.store_calls[0][1]
    assert (run_id, nonce, spec_sha) == (
        harness.config["run_id"], harness.config["probe_nonce"], harness.expected_spec,
    )
    assert probe_sha == capture.runtime_observation_binding_digest(
        run_id, nonce, spec_sha, harness.hashes, "c" * 64,
    )
    assert supervisor._probe_consumed is True
    assert api.args[0] is supervisor
    assert api.args[1] == harness.config["socket_path"]


@pytest.mark.skipif(capture.os.name == "nt", reason="Supervisor service contract requires POSIX path semantics")
def test_supervisor_restart_revalidates_environment_without_replaying_one_start_claim(monkeypatch):
    harness = _supervisor_loader_harness(monkeypatch, store_mode="recovery")

    _api, supervisor = harness.service.load_supervisor_service()

    assert len(harness.observation_calls) == 1
    observed_run, fresh_nonce, hashes, _store_path, _anchor_path, options = harness.observation_calls[0]
    assert observed_run == harness.config["run_id"]
    assert fresh_nonce != harness.config["probe_nonce"]
    assert len(fresh_nonce) == 64
    assert hashes == harness.hashes
    assert options == {"require_fresh_store": False, "persist_one_start_claim": False}
    assert harness.claim_checks == [(
        harness.config["run_id"], harness.config["probe_nonce"], harness.expected_spec,
        harness.hashes,
    )]
    assert harness.call_order == ["verify_existing_claim", "observe_runtime_once"]
    assert len(harness.store_instances) == 1
    assert harness.store_calls[0][0] == "recovery"
    run_id, nonce, spec_sha, probe_sha = harness.store_calls[0][1]
    assert (run_id, nonce, spec_sha) == (
        harness.config["run_id"], harness.config["probe_nonce"], harness.expected_spec,
    )
    assert probe_sha == capture.runtime_observation_binding_digest(
        run_id, nonce, spec_sha, harness.hashes, "c" * 64,
    )
    assert harness.identity_calls == [harness.hashes, harness.hashes, harness.hashes]
    assert supervisor._probe_consumed is True


@pytest.mark.skipif(capture.os.name == "nt", reason="Supervisor service contract requires POSIX path semantics")
def test_supervisor_restart_refuses_source_or_config_hash_drift_before_store_open(monkeypatch):
    harness = _supervisor_loader_harness(monkeypatch, store_mode="recovery", source_drift=True)

    with pytest.raises(ContractError, match="source or runtime configuration changed during recovery binding"):
        harness.service.load_supervisor_service()

    assert harness.call_order == ["verify_existing_claim", "observe_runtime_once"]
    assert len(harness.observation_calls) == 1
    assert harness.store_instances == []


@pytest.mark.skipif(capture.os.name == "nt", reason="Supervisor service contract requires POSIX path semantics")
@pytest.mark.parametrize("invalid", ["result", "spec", "network_profile", "mount_namespace", "network_namespace", "pid_namespace"])
def test_supervisor_restart_refuses_invalid_fresh_observation_before_store_open(monkeypatch, invalid):
    def invalidate(probe, hashes):
        if invalid == "result":
            probe["result"] = "FAIL"
        elif invalid == "spec":
            probe["inventory"]["spec_sha256"] = "f" * 64
        elif invalid == "network_profile":
            probe["inventory"]["network_profile_sha256"] = "f" * 64
        elif invalid == "mount_namespace":
            probe["inventory"]["namespace_inodes"]["mount"] = 10
        elif invalid == "network_namespace":
            probe["inventory"]["namespace_inodes"]["network"] = 11
        else:
            probe["inventory"]["namespace_inodes"]["pid"] = 99

    harness = _supervisor_loader_harness(
        monkeypatch, store_mode="recovery", observation_override=invalidate,
    )

    with pytest.raises(ContractError):
        harness.service.load_supervisor_service()

    assert harness.call_order == ["verify_existing_claim", "observe_runtime_once"]
    assert len(harness.observation_calls) == 1
    assert harness.store_instances == []
