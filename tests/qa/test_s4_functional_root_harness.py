"""S4 AC-4/AC-11/AC-14 and VST-032/033/037: privileged root harness contracts."""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import stat
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qa import root_harness

EXPECTED_MINIMAL_ENV = {
    "GIT_CONFIG_COUNT": "0",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_OPTIONAL_LOCKS": "0",
    "GIT_TERMINAL_PROMPT": "0",
    "HOME": "/root",
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": "/usr/sbin:/usr/bin:/sbin:/bin",
    "TMPDIR": "/tmp",
}


def _args(repo: Path, **overrides) -> Namespace:
    values = {
        "repo_root": str(repo),
        "category": "functional",
        "dependency_target": str(repo / "deps"),
        "scratch_root": str(repo / "scratch"),
        "run_id": "root-harness-contract",
        "expected_head": "a" * 40,
        "report_path": "report.jsonl",
        "stdout_path": "stdout.txt",
        "stderr_path": "stderr.txt",
        "timeout_seconds": 900,
        "output_cap_bytes": 1024 * 1024,
        "parent_ns_fd": None,
    }
    values.update(overrides)
    return Namespace(**values)


def _enable_isolated_mode(monkeypatch):
    monkeypatch.setattr(
        root_harness.sys,
        "flags",
        SimpleNamespace(isolated=True, ignore_environment=False, verbose=0),
    )


def test_s4_root_harness_requires_trusted_installed_root_owned_helper(monkeypatch):
    installed = Path("/usr/local/libexec/vst-s4-root-harness.py")
    monkeypatch.setattr(root_harness, "INSTALLED_HELPER", installed)
    monkeypatch.setattr(root_harness, "__file__", str(installed))
    monkeypatch.setattr(Path, "resolve", lambda self, **kwargs: installed)

    for owner, mode, expected in (
        (0, stat.S_IFREG | 0o755, True),
        (1000, stat.S_IFREG | 0o755, False),
        (0, stat.S_IFREG | 0o775, False),
        (0, stat.S_IFREG | 0o777, False),
    ):
        monkeypatch.setattr(Path, "stat", lambda self: SimpleNamespace(st_uid=owner, st_mode=mode))
        assert root_harness._trusted_installed_helper() is expected

    monkeypatch.setattr(root_harness, "__file__", "/tmp/untrusted-root-harness.py")
    monkeypatch.setattr(Path, "resolve", lambda self, **kwargs: Path("/tmp/untrusted-root-harness.py"))
    assert root_harness._trusted_installed_helper() is False


@pytest.mark.parametrize(
    ("parent_owner", "parent_mode", "expected"),
    [(0, stat.S_IFDIR | 0o755, True), (1000, stat.S_IFDIR | 0o755, False),
     (0, stat.S_IFDIR | 0o775, False), (0, stat.S_IFDIR | 0o777, False)],
)
def test_s4_root_harness_requires_root_owned_nonwritable_libexec_parent(
    monkeypatch, parent_owner, parent_mode, expected
):
    installed = Path("/usr/local/libexec/vst-s4-root-harness.py")
    monkeypatch.setattr(root_harness, "INSTALLED_HELPER", installed)
    monkeypatch.setattr(root_harness, "__file__", str(installed))
    monkeypatch.setattr(Path, "resolve", lambda self, **kwargs: installed)

    def fake_stat(path):
        if path == installed:
            return SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o755)
        assert path == installed.parent
        return SimpleNamespace(st_uid=parent_owner, st_mode=parent_mode)

    monkeypatch.setattr(Path, "stat", fake_stat)

    assert root_harness._trusted_installed_helper() is expected


def test_s4_root_harness_outer_preflights_candidate_then_reexecs_fixed_installed_helper(
    tmp_path: Path, monkeypatch
):
    repo = tmp_path / "candidate"
    repo.mkdir()
    candidate_helper = repo / "tools" / "qa" / "root_harness.py"
    candidate_helper.parent.mkdir(parents=True)
    candidate_helper.write_bytes(Path(root_harness.__file__).read_bytes())
    args = _args(repo)
    _enable_isolated_mode(monkeypatch)
    calls = []
    events = []
    closed = []
    monkeypatch.setattr(root_harness, "_args", lambda: args)
    monkeypatch.setattr(root_harness, "_distribution", lambda: True)
    monkeypatch.setattr(root_harness, "_trusted_installed_helper", lambda: True)
    monkeypatch.setattr(root_harness, "_git_head", lambda path: events.append("git") or args.expected_head)
    monkeypatch.setenv("PATH", "/untrusted/path")
    monkeypatch.setattr(root_harness.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(root_harness.os, "open", lambda path, flags: 41)
    monkeypatch.setattr(root_harness.os, "close", closed.append)
    monkeypatch.setattr(
        root_harness.subprocess,
        "run",
        lambda *a, **kw: events.append("unshare") or calls.append((a, kw)) or SimpleNamespace(returncode=17),
    )
    monkeypatch.setattr(root_harness.sys, "argv", ["root_harness.py", "--category", "functional"])

    result = root_harness._main()

    command, options = calls[0][0][0], calls[0][1]
    assert result == 17
    assert events == ["git", "unshare"]
    assert command[:6] == ["/usr/bin/unshare", "--net", "--", "/usr/bin/python3.12", "-I", "/usr/local/libexec/vst-s4-root-harness.py"]
    assert command[-2:] == ["--parent-ns-fd", "41"]
    assert options["shell"] is False
    assert options["pass_fds"] == (41,)
    assert options["cwd"] == repo.resolve()
    assert root_harness.MINIMAL_ENV == EXPECTED_MINIMAL_ENV
    assert options["env"] == EXPECTED_MINIMAL_ENV
    assert closed == [41]


def test_s4_root_harness_rejects_candidate_helper_mismatch_before_unshare(
    tmp_path: Path, monkeypatch
):
    repo = tmp_path / "candidate"
    (repo / "tools" / "qa").mkdir(parents=True)
    (repo / "tools" / "qa" / "root_harness.py").write_bytes(b"different candidate helper\n")
    args = _args(repo)
    launched = []
    monkeypatch.setattr(root_harness, "_args", lambda: args)
    _enable_isolated_mode(monkeypatch)
    monkeypatch.setattr(root_harness, "_distribution", lambda: True)
    monkeypatch.setattr(root_harness, "_trusted_installed_helper", lambda: True)
    monkeypatch.setattr(root_harness.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(root_harness, "_git_head", lambda _repo: args.expected_head)
    monkeypatch.setattr(root_harness.subprocess, "run", lambda *a, **kw: launched.append(a))

    with pytest.raises(SystemExit, match="does not match candidate source"):
        root_harness._main()

    assert launched == []


def _prepare_child(monkeypatch, tmp_path: Path, *, parent_inode=111, current_inode=222):
    repo = tmp_path / "candidate"
    repo.mkdir()
    candidate_helper = repo / "tools" / "qa" / "root_harness.py"
    candidate_helper.parent.mkdir(parents=True)
    helper_bytes = Path(root_harness.__file__).read_bytes()
    candidate_helper.write_bytes(helper_bytes)
    args = _args(repo, parent_ns_fd=41)
    _enable_isolated_mode(monkeypatch)
    calls = []
    monkeypatch.setattr(root_harness, "_args", lambda: args)
    monkeypatch.setattr(root_harness, "_distribution", lambda: True)
    monkeypatch.setattr(root_harness, "_trusted_installed_helper", lambda: True)
    monkeypatch.setenv("PATH", "/untrusted/path")
    monkeypatch.setattr(root_harness.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(root_harness.os, "fstat", lambda fd: SimpleNamespace(st_ino=parent_inode))
    monkeypatch.setattr(root_harness.os, "readlink", lambda path: f"net:[{parent_inode}]")
    monkeypatch.setattr(root_harness.os, "close", lambda fd: None)
    real_stat = root_harness.os.stat
    monkeypatch.setattr(
        root_harness.os,
        "stat",
        lambda path, *a, **kw: SimpleNamespace(st_ino=current_inode)
        if os.fspath(path) == "/proc/self/ns/net"
        else real_stat(path, *a, **kw),
    )
    monkeypatch.setattr(root_harness.subprocess, "run", lambda *a, **kw: calls.append((a[0], kw)) or SimpleNamespace(returncode=0))
    monkeypatch.setattr(root_harness.socket, "if_nameindex", lambda: [(1, "lo")])
    monkeypatch.setattr(root_harness.tempfile, "mkdtemp", lambda **kw: str(tmp_path / "proof-dir"))
    monkeypatch.setattr(root_harness.os, "chmod", lambda path, mode: None)
    (tmp_path / "proof-dir").mkdir()
    monkeypatch.setattr(root_harness, "_git_head", lambda path: args.expected_head)
    boundary = {"candidate_root": "/tmp/vst-s4-candidate/checkout", "mountinfo_sha256": "b" * 64}
    boundary_calls = []
    monkeypatch.setattr(root_harness, "_candidate_boundary", lambda path: boundary_calls.append(path) or boundary)
    monkeypatch.setattr(root_harness, "_loopback_canary_passed", lambda: True)
    monkeypatch.setattr(root_harness.platform, "release", lambda: "6.8-wsl")
    return args, calls, boundary_calls, boundary


def test_s4_root_harness_child_binds_mount_and_parent_proof_then_launches_qa_through_setpriv(
    tmp_path: Path, monkeypatch
):
    args, calls, boundary_calls, boundary = _prepare_child(monkeypatch, tmp_path)
    imported_tools = []
    original_import = builtins.__import__

    def observe_import(name, *a, **kw):
        if name == "tools" or name.startswith("tools."):
            imported_tools.append(name)
        return original_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", observe_import)

    assert root_harness._main() == 0

    assert imported_tools == []
    assert boundary_calls == [Path(args.repo_root).resolve()]
    assert calls[0][0] == ["/usr/sbin/ip", "link", "set", "dev", "lo", "up"]
    assert calls[0][1]["env"] == EXPECTED_MINIMAL_ENV
    restricted, options = calls[1]
    assert restricted[0] == "/usr/bin/setpriv"
    launcher = restricted[restricted.index("--") + 1 :]
    assert launcher[:3] == ["/usr/bin/python3.12", "-I", "-c"]
    insertion = launcher[3].find("sys.path.insert(0,sys.argv.pop(1))")
    module_run = launcher[3].find("runpy.run_module('tools.qa.run',run_name='__main__')")
    assert insertion >= 0
    assert module_run > insertion
    assert launcher[4] == str(Path(args.repo_root).resolve())
    assert "--bounding-set=-all,+chown,+setgid,+setuid" in restricted
    assert options["shell"] is False
    assert options["env"] == EXPECTED_MINIMAL_ENV
    proof_path = Path(restricted[restricted.index("--privileged-harness-proof") + 1])
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    assert proof["parent_network_namespace_inode"] == 111
    assert proof["schema_version"] == 4
    assert proof["helper_sha256"] == hashlib.sha256(
        Path(root_harness.__file__).read_bytes()
    ).hexdigest()
    assert proof["candidate_root"] == boundary["candidate_root"]
    assert proof["mountinfo_sha256"] == boundary["mountinfo_sha256"]
    assert proof["candidate_head"] == args.expected_head


@pytest.mark.parametrize(
    ("parent_inode", "current_inode", "target"),
    [(111, 111, "net:[111]"), (111, 222, "net:[112]"), (0, 222, "net:[0]")],
)
def test_s4_root_harness_child_rejects_unproven_or_non_private_namespace_before_qa(
    tmp_path: Path, monkeypatch, parent_inode, current_inode, target
):
    _args_value, calls, _boundary_calls, _boundary = _prepare_child(
        monkeypatch, tmp_path, parent_inode=parent_inode, current_inode=current_inode
    )
    monkeypatch.setattr(root_harness.os, "readlink", lambda path: target)

    with pytest.raises(SystemExit, match="invalid root namespace child invocation|distinct network namespace"):
        root_harness._main()

    assert calls == []


@pytest.mark.parametrize(
    ("option", "value"),
    [("--category", "unknown"), ("--timeout-seconds", "0"), ("--output-cap-bytes", "0")],
)
def test_s4_root_harness_rejects_invalid_cli_contract_before_process_launch(
    tmp_path: Path, monkeypatch, option, value
):
    repo = tmp_path / "candidate"
    repo.mkdir()
    argv = [
        "root_harness", "--repo-root", str(repo), "--category", "functional",
        "--dependency-target", str(repo), "--scratch-root", str(repo), "--run-id", "valid-id",
        "--expected-head", "a" * 40, "--report-path", "report", "--stdout-path", "stdout",
        "--stderr-path", "stderr",
    ]
    index = argv.index(option) if option in argv else -1
    if index >= 0:
        argv[index + 1] = value
    else:
        argv.extend([option, value])
    launched = []
    monkeypatch.setattr(root_harness.sys, "argv", argv)
    _enable_isolated_mode(monkeypatch)
    monkeypatch.setattr(root_harness.subprocess, "run", lambda *a, **kw: launched.append(a))

    with pytest.raises(SystemExit):
        root_harness._main()

    assert launched == []


def test_s4_root_harness_requires_isolated_python_before_git_or_process_launch(
    monkeypatch,
):
    launched = []
    monkeypatch.setattr(root_harness.sys, "flags", SimpleNamespace(isolated=False))
    monkeypatch.setattr(root_harness, "_git_head", lambda _repo: launched.append("git"))
    monkeypatch.setattr(root_harness.subprocess, "run", lambda *a, **kw: launched.append("process"))

    with pytest.raises(SystemExit, match="isolated Python startup"):
        root_harness._main()

    assert launched == []


def test_s4_root_harness_rejects_untrusted_install_before_git_or_process_launch(
    tmp_path: Path, monkeypatch
):
    repo = tmp_path / "candidate"
    repo.mkdir()
    args = _args(repo)
    launched = []
    monkeypatch.setattr(root_harness, "_args", lambda: args)
    _enable_isolated_mode(monkeypatch)
    monkeypatch.setattr(root_harness, "_distribution", lambda: True)
    monkeypatch.setattr(root_harness, "_trusted_installed_helper", lambda: False)
    monkeypatch.setattr(root_harness, "_git_head", lambda _path: launched.append("git"))
    monkeypatch.setattr(root_harness.subprocess, "run", lambda *a, **kw: launched.append("process"))

    with pytest.raises(SystemExit, match="root-owned installed helper"):
        root_harness._main()

    assert launched == []


def test_s4_root_harness_git_preflight_uses_fixed_absolute_executable(monkeypatch):
    calls = []
    monkeypatch.setenv("PATH", "/untrusted/path")
    monkeypatch.setattr(
        root_harness.subprocess,
        "run",
        lambda command, **options: calls.append((command, options)) or SimpleNamespace(stdout=b"a" * 40 + b"\n"),
    )

    assert root_harness._git_head(Path("/tmp/candidate")) == "a" * 40

    command, options = calls[0]
    candidate = Path("/tmp/candidate")
    assert command == [
        "/usr/bin/git", "-c", "safe.directory=", "-c", f"safe.directory={candidate}",
        "-C", str(candidate), "rev-parse", "--verify", "HEAD",
    ]
    assert options["shell"] is False
    assert root_harness.MINIMAL_ENV == EXPECTED_MINIMAL_ENV
    assert options["env"] == EXPECTED_MINIMAL_ENV


@pytest.mark.parametrize(
    ("filesystem", "source", "allowed"),
    [(b"ext4", b"/dev/sda", True), (b"9p", b"drvfs", False), (b"drvfs", b"C:", False)],
)
def test_s4_root_harness_candidate_mount_boundary_rejects_windows_backing(
    tmp_path: Path, monkeypatch, filesystem, source, allowed
):
    candidate_root = tmp_path / "vst-s4-candidate"
    repo = candidate_root / "checkout"
    repo.mkdir(parents=True)
    monkeypatch.setattr(root_harness, "WSL_CANDIDATE_ROOT", candidate_root)
    mountpoint = candidate_root.as_posix().encode().replace(b" ", b"\\040")
    mountinfo = b"36 25 8:1 / " + mountpoint + b" rw,relatime - " + filesystem + b" " + source + b" rw\n"
    original_read_bytes = Path.read_bytes

    def read_mountinfo(path: Path):
        if path.as_posix() == "/proc/self/mountinfo":
            return mountinfo
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_mountinfo)

    if allowed:
        result = root_harness._candidate_boundary(repo)
        assert result["candidate_root"] == repo.resolve().as_posix()
        assert result["mountinfo_sha256"] == hashlib.sha256(mountinfo).hexdigest()
    else:
        with pytest.raises(SystemExit, match="Windows-drive drvfs/9p"):
            root_harness._candidate_boundary(repo)
