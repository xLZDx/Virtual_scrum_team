"""Mock-only S2-4 runtime harness contract tests.

Maps to the bounded authorization, exact source-pin, one-shot WSL, and terminal
attempt-evidence gates. No test in this module launches WSL or a runtime service.
"""
from __future__ import annotations

import hashlib
import io
import json
import ast
import pathlib
import re
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qa import run_s2_runtime_qualification as harness


RUNTIME_HEAD = "1" * 40
QUALIFICATION_HEAD = "b" * 40
HEX = "a" * 64
WSL_HELPER = "tools/qa/s2_runtime_qualification_wsl.py"
OUTER_HELPER = "tools/qa/run_s2_runtime_qualification.py"
FAILURE_PROTOCOL = json.dumps({
    "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
    "terminal": "HOLD",
    "reason": "synthetic bounded refusal",
}, separators=(",", ":")).encode("ascii")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _auth_input(*, streamed_wsl: bytes = b"# mocked WSL helper\n") -> dict:
    config_hashes = {path: HEX for path in harness.REQUIRED_CONFIG_PINS}
    config_bundle_hash = _sha(json.dumps(
        config_hashes, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii"))
    source_hashes = {path: HEX for path in harness.REQUIRED_RUNTIME_PINS}
    return {
        "schema": "VST_S2_RUNTIME_AUTH_INPUT_V1",
        "authorization": {
            "source": "PM_BRIDGE",
            "correlated": True,
            "verdict": "AUTHORIZE_ONE_SHOT",
            "request_id": "2" * 32,
            "job_id": "job-0123456789abcdef",
            "user_turn_id": "turn-0123456789abcdef",
            "reply_id": "reply-0123456789abcdef",
            "payload_sha256": "3" * 64,
            "retry_cap": 0,
            "allowed_operation": "S2-4_OWNER_RUNNER_TESTRUN",
        },
        "identity": {
            "runtime_source_head": RUNTIME_HEAD,
            "qualification_source_head": QUALIFICATION_HEAD,
            "run_id": "run-0123456789abcdef",
            "bootstrap_request_id": "4" * 32,
            "nonce": "5" * 32,
            "runtime_selector": "/opt/vst-runtime-" + RUNTIME_HEAD,
            "bundle_sha256": HEX,
            "config_bundle_sha256": config_bundle_hash,
            "task_manifest_sha256": "6" * 64,
            "selector_test_id": (
                "tests/vst/test_s2_runtime_qualification_harness.py::"
                "test_runtime_handoff_contract"
            ),
            "config_sha256": config_hashes,
        },
        "source_pins": {
            "runtime": source_hashes,
            "qualification": {
                OUTER_HELPER: HEX,
                WSL_HELPER: _sha(streamed_wsl),
            },
        },
    }


def _write_input(root: Path, value: dict | bytes) -> tuple[Path, Path]:
    input_path = root / "authorization.json"
    output_path = root / "docs" / "sdlc" / "evidence" / "attempt.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        input_path.write_bytes(value)
    else:
        input_path.write_text(json.dumps(value), encoding="utf-8")
    return input_path, output_path


def _wsl_prestart_functions():
    """Load only the exact WSL mount-preflight functions, without running its protocol."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    wanted = {"Hold", "stop", "_decode_mountinfo", "_prestart_inventory"}
    nodes = [node for node in tree.body
             if ((isinstance(node, ast.ClassDef) or isinstance(node, ast.FunctionDef))
                 and node.name in wanted)]
    assert {node.name for node in nodes} == wanted
    module = ast.Module(body=nodes, type_ignores=[])
    namespace = {
        "hashlib": hashlib,
        "os": SimpleNamespace(geteuid=lambda: 0),
        "pathlib": pathlib,
        "re": re,
        "R": {"prestart": {}},
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace


def _approved_mountinfo() -> str:
    return "\n".join((
        "36 25 8:1 / / rw,relatime - ext4 /dev/sda1 rw,errors=remount-ro",
        "37 36 0:4 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw",
        "38 36 0:5 / /sys rw,nosuid,nodev,noexec,relatime - sysfs sysfs rw",
        "39 36 0:6 / /dev rw,nosuid - devtmpfs devtmpfs rw,size=65536k",
        "40 39 0:8 / /dev/pts rw,nosuid,noexec,relatime - devpts devpts rw,gid=5,mode=620",
        "41 36 0:30 / /sys/fs/cgroup rw,nosuid,nodev,noexec,relatime - cgroup2 cgroup2 rw",
        "42 36 0:27 / /run rw,nosuid,nodev - tmpfs tmpfs rw,size=65536k",
        "43 36 8:1 /run/systemd/inaccessible/dir /mnt rw,nosuid,nodev - ext4 /dev/sda1 rw",
        "44 36 0:44 / /usr/lib/modules rw,relatime - overlay none rw,lowerdir=/modules,ro",
    ))


@pytest.mark.parametrize("invalid", ["un correlated", "oversized"])
def test_bounded_or_unauthorized_input_refuses_before_wsl(monkeypatch, tmp_path, invalid):
    value: dict | bytes = _auth_input()
    if invalid == "un correlated":
        value["authorization"]["correlated"] = False
    else:
        value = b" " * (harness.MAX_INPUT_BYTES + 1)
    input_path, output_path = _write_input(tmp_path, value)
    called = []

    def unexpected_wsl(_script):
        called.append(True)
        pytest.fail("invalid authorization must be rejected before WSL")

    monkeypatch.setattr(harness, "_run_bounded_wsl", unexpected_wsl)
    with pytest.raises(harness.QualificationError):
        harness.run_once(input_path, output_path, root=tmp_path)

    assert called == []
    assert not output_path.exists()


def test_closed_identity_schema_requires_qualification_source_head():
    value = _auth_input()
    del value["identity"]["qualification_source_head"]

    with pytest.raises(harness.QualificationError, match="identity.*fields"):
        harness.validate_input(value)


def test_qualification_source_pins_cover_exactly_the_two_launcher_paths():
    value = _auth_input()
    value["source_pins"]["qualification"]["tools/qa/unapproved.py"] = HEX

    with pytest.raises(harness.QualificationError,
                       match="qualification source pins must cover exactly the two launcher files"):
        harness.validate_input(value)


def test_source_pin_verification_accepts_exact_archive_and_rejects_worktree_drift(
        monkeypatch, tmp_path):
    launchers = {OUTER_HELPER, WSL_HELPER}
    archived_files = {
        path: ("pinned source " + path).encode("utf-8")
        for path in harness.REQUIRED_RUNTIME_PINS - launchers
    }
    launcher_files = {
        OUTER_HELPER: b"# exact committed outer launcher\n",
        WSL_HELPER: b"# exact committed WSL helper\n",
    }
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:") as archive:
        for name, data in archived_files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    archive_bytes = archive_buffer.getvalue()

    value = _auth_input(streamed_wsl=launcher_files[WSL_HELPER])
    value["identity"]["bundle_sha256"] = _sha(archive_bytes)
    for path, data in archived_files.items():
        value["source_pins"]["runtime"][path] = _sha(data)
    value["source_pins"]["qualification"] = {
        path: _sha(data) for path, data in launcher_files.items()
    }
    assert not (set(value["source_pins"]["runtime"]) & launchers)
    assert set(value["source_pins"]["runtime"]) == set(archived_files)
    assert set(value["source_pins"]["qualification"]) == launchers
    for path, data in launcher_files.items():
        target = tmp_path / Path(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    validated = harness.validate_input(value)

    def fake_git(_root, *args, **_kwargs):
        if args[0] == "rev-parse":
            revision = args[-1]
            if revision == "HEAD":
                return (QUALIFICATION_HEAD + "\n").encode("ascii")
            return (RUNTIME_HEAD + "\n").encode("ascii")
        if args[0] == "archive":
            return archive_bytes
        if args[0] == "show":
            revision, path = args[1].split(":", 1)
            assert revision == QUALIFICATION_HEAD
            return launcher_files[path]
        pytest.fail(f"unexpected Git command: {args!r}")

    monkeypatch.setattr(harness, "_git", fake_git)
    harness.verify_source_pins(tmp_path, validated)

    (tmp_path / Path(*WSL_HELPER.split("/"))).write_bytes(b"tampered helper\n")
    with pytest.raises(harness.QualificationError, match="differs from its exact committed Git blob"):
        harness.verify_source_pins(tmp_path, validated)


def test_wrong_expected_qualification_head_refuses_before_attempt_or_wsl(
        monkeypatch, tmp_path):
    archived_files = {
        path: ("pinned source " + path).encode("utf-8")
        for path in harness.REQUIRED_RUNTIME_PINS
    }
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:") as archive:
        for name, data in archived_files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    archive_bytes = archive_buffer.getvalue()
    launcher_files = {
        OUTER_HELPER: b"# committed outer launcher\n",
        WSL_HELPER: b"# committed WSL launcher\n",
    }
    value = _auth_input(streamed_wsl=launcher_files[WSL_HELPER])
    value["identity"]["bundle_sha256"] = _sha(archive_bytes)
    value["source_pins"]["runtime"] = {
        path: _sha(data) for path, data in archived_files.items()
    }
    value["source_pins"]["qualification"] = {
        path: _sha(data) for path, data in launcher_files.items()
    }
    value["identity"]["qualification_source_head"] = "c" * 40
    input_path, output_path = _write_input(tmp_path, value)
    wsl_calls = []

    def fake_git(_root, *args, **_kwargs):
        if args[0] == "rev-parse":
            revision = args[-1]
            return ((QUALIFICATION_HEAD if revision == "HEAD" else RUNTIME_HEAD)
                    + "\n").encode("ascii")
        if args[0] == "archive":
            return archive_bytes
        pytest.fail(f"unexpected Git command: {args!r}")

    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", lambda *_args: wsl_calls.append(True))

    with pytest.raises(harness.QualificationError,
                       match="qualification source HEAD differs from the authorized exact repository HEAD"):
        harness.run_once(input_path, output_path, root=tmp_path)

    assert not output_path.exists()
    assert wsl_calls == []


def test_run_once_starts_one_mock_wsl_child_and_persists_terminal_hold(
        monkeypatch, tmp_path, capsys):
    script = b"# mocked exact WSL protocol source\n"
    value = _auth_input(streamed_wsl=script)
    input_path, output_path = _write_input(tmp_path, value)
    monkeypatch.setattr(harness, "verify_source_pins", lambda *_args: None)
    monkeypatch.setattr(harness, "refuse_historical_identity", lambda *_args: None)
    monkeypatch.setattr(harness, "_load_wsl_script", lambda: script)

    calls = []

    class CapturedInput:
        def __init__(self):
            self.data = bytearray()
            self.closed = False

        def write(self, data):
            self.data.extend(data)
            return len(data)

        def flush(self):
            pass

        def close(self):
            self.closed = True

    class MockWslProcess:
        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))
            self.stdin = CapturedInput()
            self.stdout = io.BytesIO(FAILURE_PROTOCOL)
            self.stderr = io.BytesIO(b"synthetic stderr")
            self.returncode = 2

        def wait(self, *, timeout):
            assert timeout == 2400
            return self.returncode

    monkeypatch.setattr(harness.subprocess, "Popen", MockWslProcess)

    exit_code = harness.run_once(input_path, output_path, root=tmp_path)

    assert exit_code == 2
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[:3] == ["wsl.exe", "--distribution", harness.WSL_DISTRIBUTION]
    assert kwargs["close_fds"] is True
    assert len(calls[0][1:]) == 1
    attempt = json.loads(output_path.read_text(encoding="utf-8"))
    assert attempt["state"] == "HOLD"
    assert attempt["protocol"]["terminal"] == "HOLD"
    assert attempt["retry"] == "PROHIBITED"
    assert attempt["retry_cap"] == 0
    assert attempt["stdout_sha256"] == _sha(FAILURE_PROTOCOL)
    assert attempt["stderr_sha256"] == _sha(b"synthetic stderr")
    assert capsys.readouterr().out


def test_wsl_mount_allowlist_accepts_only_expected_mounts(monkeypatch):
    functions = _wsl_prestart_functions()
    rows, windows_mounts, unapproved_mounts = functions["_decode_mountinfo"](
        _approved_mountinfo())

    assert len(rows) == 9
    assert windows_mounts == []
    assert unapproved_mounts == []


@pytest.mark.parametrize(("label", "extra", "reason"), [
    ("unknown host filesystem",
     "80 36 8:2 / /srv/host rw,relatime - ext4 /dev/sdb1 rw",
     "unapproved host mount detected"),
    ("Windows drive under /mnt",
     "80 36 0:55 / /mnt/c rw,relatime - 9p C:\\ aname=drvfs;path=C:\\;symlinkroot=/mnt/",
     "Windows drive mount detected"),
    ("unsupported proc source",
     "80 36 0:4 / /proc/host rw,relatime - proc hostproc rw",
     "unapproved host mount detected"),
    ("mismatched bind mount root",
     "80 36 8:1 /etc /srv/host rw,relatime - ext4 /dev/sda1 rw",
     "unapproved host mount detected"),
    ("overlay with an unapproved prefixed target",
     "80 36 0:55 / /srv/unapproved/usr/lib/modules ro,relatime - overlay none ro,lowerdir=/modules",
     "unapproved host mount detected"),
])
def test_wsl_prestart_refuses_unapproved_mounts(monkeypatch, label, extra, reason):
    functions = _wsl_prestart_functions()
    mountinfo = _approved_mountinfo() + "\n" + extra

    original_read_text = pathlib.Path.read_text

    def read_text(path, *args, **kwargs):
        if path.as_posix() == "/proc/self/mountinfo":
            return mountinfo
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)
    with pytest.raises(functions["Hold"]):
        functions["_prestart_inventory"]({})

    assert functions["R"]["terminal"] == "HOLD", label
    assert reason in functions["R"]["reason"], label


def test_unknown_protocol_persists_indeterminate_record_without_retry(
        monkeypatch, tmp_path):
    script = b"# mocked exact WSL protocol source\n"
    unknown_protocol = b'{"schema":"VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V999"}'
    value = _auth_input(streamed_wsl=script)
    input_path, output_path = _write_input(tmp_path, value)
    monkeypatch.setattr(harness, "verify_source_pins", lambda *_args: None)
    monkeypatch.setattr(harness, "refuse_historical_identity", lambda *_args: None)
    monkeypatch.setattr(harness, "_load_wsl_script", lambda: script)

    calls = []

    def one_wsl_attempt(_script):
        calls.append(True)
        return {
            "exit_code": 2,
            "timed_out": False,
            "writer_error": None,
            "stdout": {"bytes": len(unknown_protocol), "sha256": _sha(unknown_protocol),
                       "prefix": unknown_protocol, "truncated": False},
            "stderr": {"bytes": 0, "sha256": _sha(b""),
                       "prefix": b"", "truncated": False},
        }

    monkeypatch.setattr(harness, "_run_bounded_wsl", one_wsl_attempt)

    with pytest.raises(harness.QualificationError, match="unrecognized protocol"):
        harness.run_once(input_path, output_path, root=tmp_path)

    attempt = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert attempt["state"] == "INDETERMINATE"
    assert attempt["exit_code"] == 2
    assert attempt["stdout_bytes"] == len(unknown_protocol)
    assert attempt["stdout_sha256"] == _sha(unknown_protocol)
    assert attempt["stderr_bytes"] == 0
    assert attempt["stderr_sha256"] == _sha(b"")
    assert attempt["retry"] == "PROHIBITED"
    assert attempt["retry_cap"] == 0
