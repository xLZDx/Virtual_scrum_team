"""S2 capture contract tests; synthetic journal rows are not runtime evidence."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.vst import preflight, preflight_capture as capture
from tools.vst.contracts import ContractError, canonical_bytes


RUN_ID = "s2-capture-run"
NONCE = "s2-capture-nonce"
INVOCATION_ID = "a" * 32
OPERATOR_KEY = b"s2-capture-operator-root-key-0123456789"
SPEC_BYTES = b"synthetic sandbox spec for capture test\n"
SPEC_SHA256 = hashlib.sha256(SPEC_BYTES).hexdigest()
NOW_NS = 50_000_000_000_000
PROPERTIES = {
    "automount_disabled", "interop_disabled", "no_container_socket", "non_root",
    "external_egress_blocked", "loopback_canary", "empty_external_allowlist",
}


def _attestation(*, run_id=RUN_ID, nonce=NONCE, spec_sha256=SPEC_SHA256,
                 key=OPERATOR_KEY, **overrides):
    body = {
        "run_id": run_id,
        "spec_sha256": spec_sha256,
        "nonce": nonce,
        "environment_id": "synthetic-capture-environment",
        "policy_sha256": "a" * 64,
        "evidence_sha256": "b" * 64,
        "empty_external_allowlist": True,
        "no_container_socket": True,
        "no_unapproved_host_paths": True,
    }
    body.update(overrides)
    return preflight.sign_network_policy_attestation(body, key)


def _probe(*, run_id=RUN_ID, nonce=NONCE, spec_sha256=SPEC_SHA256,
           observed_at_ns=NOW_NS, attestation=None):
    return {
        "run_id": run_id,
        "spec_sha256": spec_sha256,
        "nonce": nonce,
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
            "blocked_egress_probe_scope": (
                "single reserved-target smoke probe; does not prove egress policy"
            ),
            "network_policy_attestation": attestation or _attestation(),
            "environment_variable_names": [],
            "observed_at_monotonic_ns": observed_at_ns,
        },
    }


def _message_entry(probe, *, unit=capture.PROBE_UNIT, invocation_id=INVOCATION_ID,
                   uid="999", gid="989", pid="123"):
    return {
        "_SYSTEMD_UNIT": unit,
        "_SYSTEMD_INVOCATION_ID": invocation_id,
        "_UID": uid,
        "_GID": gid,
        "_PID": pid,
        "MESSAGE": json.dumps(probe, separators=(",", ":")),
    }


def _result_entry(*, unit=capture.PROBE_UNIT, invocation_id=INVOCATION_ID,
                  uid="0", pid="1", result="success"):
    return {
        "UNIT": unit,
        "INVOCATION_ID": invocation_id,
        "_PID": pid,
        "_UID": uid,
        "UNIT_RESULT": result,
    }


def _json_lines(*entries):
    return ("\n".join(json.dumps(entry, separators=(",", ":")) for entry in entries)).encode()


@pytest.fixture
def capture_case(monkeypatch):
    probe = _probe()
    attestation = probe["inventory"]["network_policy_attestation"]
    config = {
        "run_id": RUN_ID,
        "probe_nonce": NONCE,
        "operator_key_path": "/etc/vst-runner/operator.key",
        "preflight_record_path": "/run/vst-preflight/record.json",
    }
    request = {"run_id": RUN_ID, "nonce": NONCE}
    root_reads = []
    published = []
    calls = []
    root_values = {"request": request, "attestation": attestation}
    responses = [
        SimpleNamespace(returncode=0, stdout=_json_lines(_message_entry(probe))),
        SimpleNamespace(returncode=0, stdout=_json_lines(_result_entry())),
    ]

    monkeypatch.setattr(capture, "SPEC_PATH", SimpleNamespace(read_bytes=lambda: SPEC_BYTES))
    monkeypatch.setattr(capture, "_read_controlled_json", lambda path: config)
    def read_root(path, *, max_bytes):
        root_reads.append((path, max_bytes))
        if path == capture.PROBE_REQUEST_PATH:
            return root_values["request"]
        if path == capture.NETWORK_ATTESTATION_PATH:
            return root_values["attestation"]
        raise AssertionError(f"unexpected root-controlled read: {path}")
    monkeypatch.setattr(capture, "_read_root_controlled_json", read_root)
    monkeypatch.setattr(capture, "_read_root_key", lambda path: OPERATOR_KEY)
    monkeypatch.setattr(capture, "_write_root_record", lambda path, value: published.append((path, value)) or "c" * 64)
    monkeypatch.setattr(capture, "os", SimpleNamespace(name="posix", geteuid=lambda: 0))
    monkeypatch.setattr(capture, "time", SimpleNamespace(monotonic_ns=lambda: NOW_NS))
    monkeypatch.setattr(preflight.time, "monotonic_ns", lambda: NOW_NS)

    def run(argv, **kwargs):
        calls.append((list(argv), kwargs))
        assert len(calls) <= len(responses), "unexpected extra journal query"
        return responses[len(calls) - 1]

    def invoke(invocation_id=INVOCATION_ID):
        return capture.capture_probe_invocation(
            invocation_id, config_path="/etc/vst-runner/supervisor-service.json",
            journalctl_path="/usr/bin/journalctl", run=run,
        )

    return SimpleNamespace(
        probe=probe, attestation=attestation, config=config, request=request,
        root_reads=root_reads, root_values=root_values, published=published,
        calls=calls, responses=responses,
        invoke=invoke,
    )


def test_capture_binds_exact_invocation_identity_and_single_probe_message(capture_case):
    case = capture_case
    result = case.invoke()

    assert result == {"run_id": RUN_ID, "invocation_id": INVOCATION_ID, "probe_sha256": "c" * 64}
    assert case.calls[0][0] == [
        "/usr/bin/journalctl", "--no-pager", "--output=json",
        f"_SYSTEMD_UNIT={capture.PROBE_UNIT}", f"_SYSTEMD_INVOCATION_ID={INVOCATION_ID}",
    ]
    assert case.calls[1][0] == [
        "/usr/bin/journalctl", "--no-pager", "--output=json",
        f"UNIT={capture.PROBE_UNIT}", f"INVOCATION_ID={INVOCATION_ID}", "_PID=1", "_UID=0",
    ]
    assert case.root_reads == [
        (capture.PROBE_REQUEST_PATH, 65536), (capture.NETWORK_ATTESTATION_PATH, 65536),
    ]
    assert case.published == [(case.config["preflight_record_path"], case.probe)]
    assert [kwargs for _, kwargs in case.calls] == [
        {"check": False, "capture_output": True, "timeout": 15},
        {"check": False, "capture_output": True, "timeout": 15},
    ]


@pytest.mark.parametrize(
    "field,value",
    [("UNIT", "other.service"), ("INVOCATION_ID", "b" * 32),
     ("_PID", "42"), ("_UID", "999"), ("UNIT_RESULT", "failed")],
)
def test_capture_rejects_non_root_or_non_success_exact_service_result(capture_case, field, value):
    case = capture_case
    result = _result_entry()
    result[field] = value
    case.responses[1] = SimpleNamespace(returncode=0, stdout=_json_lines(result))

    with pytest.raises(ContractError, match="exact root systemd invocation|did not record one successful"):
        case.invoke()
    assert not case.published


def test_capture_rejects_duplicate_success_result_records(capture_case):
    case = capture_case
    case.responses[1] = SimpleNamespace(returncode=0, stdout=_json_lines(_result_entry(), _result_entry()))
    with pytest.raises(ContractError, match="one successful unit result"):
        case.invoke()
    assert not case.published


@pytest.mark.parametrize("field,value", [
    ("_SYSTEMD_UNIT", "other.service"), ("_SYSTEMD_INVOCATION_ID", "b" * 32),
    ("_UID", "0"), ("_GID", "988"), ("_PID", "0"),
])
def test_capture_rejects_probe_message_from_wrong_service_invocation_or_identity(capture_case, field, value):
    case = capture_case
    message = _message_entry(case.probe)
    message[field] = value
    case.responses[0] = SimpleNamespace(returncode=0, stdout=_json_lines(message))

    with pytest.raises(ContractError, match="outside the requested invocation|configured worker identity"):
        case.invoke()
    assert not case.published


@pytest.mark.parametrize("mutation", ["run_id", "spec_sha256", "nonce"])
def test_capture_rejects_probe_with_wrong_run_spec_or_nonce(capture_case, mutation):
    case = capture_case
    probe = dict(case.probe)
    probe[mutation] = "wrong"
    case.responses[0] = SimpleNamespace(
        returncode=0, stdout=_json_lines(_message_entry(probe)),
    )
    with pytest.raises(ContractError, match="run/spec/nonce or inventory validation"):
        case.invoke()
    assert not case.published


@pytest.mark.parametrize("mutation", ["wrong_run", "wrong_spec", "wrong_nonce", "bad_signature"])
def test_capture_rejects_invalid_root_network_attestation(capture_case, mutation):
    case = capture_case
    kwargs = {}
    if mutation == "wrong_run":
        kwargs["run_id"] = "other-run"
    elif mutation == "wrong_spec":
        kwargs["spec_sha256"] = "d" * 64
    elif mutation == "wrong_nonce":
        kwargs["nonce"] = "other-nonce"
    attestation = _attestation(**kwargs)
    if mutation == "bad_signature":
        attestation["signature"] = "0" * 64
    case.root_values["attestation"] = attestation
    with pytest.raises(ContractError, match="root network-policy attestation is invalid"):
        case.invoke()
    assert not case.calls
    assert not case.published


@pytest.mark.parametrize("age_ns", [capture.MAX_CAPTURE_AGE_NS + 1, -1])
def test_capture_rejects_probe_that_is_stale_or_from_future_clock(capture_case, monkeypatch, age_ns):
    case = capture_case
    case.probe["inventory"]["observed_at_monotonic_ns"] = NOW_NS
    case.responses[0] = SimpleNamespace(
        returncode=0, stdout=_json_lines(_message_entry(case.probe)),
    )
    # Validation sees a fresh record; advance only the capture clock to exercise
    # the publication-time guard independently.
    monkeypatch.setattr(preflight.time, "monotonic_ns", lambda: NOW_NS)
    monkeypatch.setattr(capture.time, "monotonic_ns", lambda: NOW_NS + age_ns)
    with pytest.raises(ContractError, match="stale or from a different monotonic clock"):
        case.invoke()
    assert not case.published


@pytest.mark.parametrize("mutation", ["wrong_run", "wrong_nonce", "extra_field"])
def test_capture_rejects_root_request_that_does_not_match_service_binding(capture_case, mutation):
    case = capture_case
    if mutation == "wrong_run":
        case.root_values["request"] = {"run_id": "other", "nonce": NONCE}
    elif mutation == "wrong_nonce":
        case.root_values["request"] = {"run_id": RUN_ID, "nonce": "other"}
    else:
        case.root_values["request"] = {"run_id": RUN_ID, "nonce": NONCE, "extra": True}
    with pytest.raises(ContractError, match="exact run contract|does not match the root Supervisor run binding"):
        case.invoke()
    assert not case.calls


@pytest.mark.parametrize(
    "raw,match",
    [(b"not-json", "not valid JSON records"), (b"", "no structured records"),
     (bytes([0xff]), "not valid JSON records")],
)
def test_probe_journal_rejects_malformed_or_empty_output(capture_case, raw, match):
    case = capture_case
    case.responses[0] = SimpleNamespace(returncode=0, stdout=raw)
    with pytest.raises(ContractError, match=match):
        case.invoke()
    assert not case.published


def test_probe_journal_requires_one_and_only_one_message(capture_case):
    case = capture_case
    entry = _message_entry(case.probe)
    case.responses[0] = SimpleNamespace(returncode=0, stdout=_json_lines(entry, entry))
    with pytest.raises(ContractError, match="exactly one stdout record"):
        case.invoke()
    assert not case.published


@pytest.mark.parametrize("query", [0, 1])
def test_capture_fails_closed_on_journal_command_error(capture_case, query):
    case = capture_case
    case.responses[query] = SimpleNamespace(returncode=1, stdout=b"")
    with pytest.raises(ContractError, match="journal query"):
        case.invoke()
    assert not case.published


@pytest.mark.parametrize("query", [0, 1])
def test_capture_normalizes_journal_timeout_and_os_error(capture_case, query):
    case = capture_case
    count = 0
    def fail_run(*_args, **_kwargs):
        nonlocal count
        count += 1
        if count == query + 1:
            if query == 0:
                raise OSError("journalctl unavailable")
            raise subprocess.TimeoutExpired("journalctl", 15)
        return case.responses[count - 1]
    with pytest.raises(ContractError, match="cannot read the exact probe invocation|cannot verify the exact probe invocation result"):
        capture.capture_probe_invocation(INVOCATION_ID, run=fail_run)
    assert not case.published


def _patch_record_os(monkeypatch, target, *, fail_on=None):
    real_os = os
    calls = []
    directory_fd = 987654
    def fake_stat(path, *, follow_symlinks=True):
        if os.fspath(path) == str(target):
            return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0)
        return real_os.stat(path, follow_symlinks=follow_symlinks)
    def fake_open(path, flags, *args, **kwargs):
        if os.fspath(path) == str(target.parent):
            return directory_fd
        return real_os.open(path, flags, *args, **kwargs)
    def fake_fsync(fd):
        if fd != directory_fd:
            return real_os.fsync(fd)
        calls.append(("fsync-directory", fd))
    def fake_fchown(fd, uid, gid):
        calls.append(("fchown", uid, gid))
        if fail_on == "fchown":
            raise OSError("chown failed")
    def fake_fchmod(fd, mode):
        calls.append(("fchmod", mode))
        if fail_on == "fchmod":
            raise OSError("chmod failed")
    def fake_link(source, destination, *, follow_symlinks=True):
        calls.append(("link", os.fspath(source), os.fspath(destination)))
        if fail_on == "link":
            raise OSError("link failed")
        return real_os.link(source, destination, follow_symlinks=follow_symlinks)
    shim = SimpleNamespace(
        path=real_os.path, fchown=fake_fchown, fchmod=fake_fchmod, fdopen=real_os.fdopen,
        fsync=fake_fsync, link=fake_link, open=fake_open,
        O_RDONLY=getattr(real_os, "O_RDONLY", 0), O_DIRECTORY=getattr(real_os, "O_DIRECTORY", 0),
        close=lambda fd: None if fd == directory_fd else real_os.close(fd),
        unlink=real_os.unlink, stat=fake_stat,
    )
    monkeypatch.setattr(capture, "os", shim)
    monkeypatch.setattr(capture, "_ensure_root_capture_directory", lambda _path: str(target.parent))
    return calls


def test_root_record_is_canonical_hard_link_published_with_root_0600_contract(tmp_path, monkeypatch):
    target = tmp_path / "record.json"
    calls = _patch_record_os(monkeypatch, target)
    record = {"run_id": RUN_ID, "observed": True}

    digest = capture._write_root_record(str(target), record)

    payload = canonical_bytes(record) + b"\n"
    assert target.read_bytes() == payload
    assert digest == hashlib.sha256(payload).hexdigest()
    assert ("fchown", 0, 0) in calls
    assert ("fchmod", 0o600) in calls
    link_call = next(call for call in calls if call[0] == "link")
    assert link_call[2] == str(target)
    assert not os.path.exists(link_call[1])
    assert ("fsync-directory", 987654) in calls


def test_root_record_refuses_existing_destination_without_overwrite(tmp_path, monkeypatch):
    target = tmp_path / "record.json"
    target.write_bytes(b"operator-owned prior record")
    calls = _patch_record_os(monkeypatch, target)

    with pytest.raises(ContractError, match="refusing to replace an existing preflight record"):
        capture._write_root_record(str(target), {"run_id": RUN_ID})

    assert target.read_bytes() == b"operator-owned prior record"
    link_call = next(call for call in calls if call[0] == "link")
    assert not os.path.exists(link_call[1])


@pytest.mark.parametrize("failure", ["fchown", "fchmod", "link"])
def test_root_record_cleans_temporary_file_when_atomic_publish_step_fails(
    tmp_path, monkeypatch, failure,
):
    target = tmp_path / "record.json"
    calls = _patch_record_os(monkeypatch, target, fail_on=failure)
    temporary_paths = []
    real_mkstemp = capture.tempfile.mkstemp
    def tracked_mkstemp(*args, **kwargs):
        descriptor, path = real_mkstemp(*args, **kwargs)
        temporary_paths.append(path)
        return descriptor, path
    monkeypatch.setattr(capture.tempfile, "mkstemp", tracked_mkstemp)

    with pytest.raises(OSError, match="failed"):
        capture._write_root_record(str(target), {"run_id": RUN_ID})

    assert temporary_paths and not os.path.exists(temporary_paths[0])
    assert not target.exists()
    assert not any(call[0] == "fsync-directory" for call in calls)


@pytest.mark.skipif(os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0,
                    reason="root-owned filesystem publication requires POSIX UID 0")
def test_posix_record_has_real_root_owner_mode_0600_and_never_overwrites():
    parent = tempfile.mkdtemp(prefix="s2-preflight-capture-", dir="/run")
    os.chown(parent, 0, 0)
    os.chmod(parent, 0o700)
    path = os.path.join(parent, "record.json")
    try:
        payload_record = {"run_id": RUN_ID, "observed": True}
        digest = capture._write_root_record(path, payload_record)
        info = os.stat(path, follow_symlinks=False)
        payload = canonical_bytes(payload_record) + b"\n"
        assert info.st_uid == 0
        assert stat.S_IMODE(info.st_mode) == 0o600
        assert Path(path).read_bytes() == payload
        assert digest == hashlib.sha256(payload).hexdigest()
        with pytest.raises(ContractError, match="refusing to replace an existing preflight record"):
            capture._write_root_record(path, {"run_id": "replacement"})
        assert Path(path).read_bytes() == payload
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        os.rmdir(parent)
