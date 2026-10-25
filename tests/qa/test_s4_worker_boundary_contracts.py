"""S4 regression coverage for signer ACLs and worker-group inheritance.

These selectors cover the POSIX boundaries used by the report-bound QA runner:
the worker must not reach an ACL-exposed signer socket, and transferred/output
directories must inherit the dedicated worker group without runner chown.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import socket
import stat
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from tools.qa import run as qa_run
from tools.qa.run import _safe_output_dir
from tools.qa.wsl_snapshot import _WSL_RECEIVER
from tools.vst import sandbox
from tools.vst.contracts import ContractError


_LINUX = sys.platform.startswith("linux")
_WORKER_UID = 998
_WORKER_GID = 987


def _source_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "qa-source"
    root.mkdir()
    tracked = root / "tracked.txt"
    tracked.write_text("source remains immutable\n", encoding="utf-8")
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
    initialized = subprocess.run(
        ["git", "init", "--quiet", "-b", "acl-fixture"], cwd=root, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=15, check=False,
    )
    assert initialized.returncode == 0, initialized.stderr.decode("utf-8", errors="replace")
    added = subprocess.run(
        ["git", "add", "tracked.txt"], cwd=root, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=15, check=False,
    )
    assert added.returncode == 0, added.stderr.decode("utf-8", errors="replace")
    return root, tracked


def _no_acl(path, _attribute, *, follow_symlinks=True):
    raise OSError(errno.ENODATA, "no ACL xattr", os.fspath(path))


def _isolate_mode_bits(monkeypatch):
    # These selectors falsify the ACL guard independently of the mode-bit
    # fallback; dedicated sandbox runs exercise real POSIX permissions.
    monkeypatch.setattr(qa_run, "_worker_writable", lambda *_args: False)


@pytest.mark.parametrize("acl_kind", ["named-user", "named-group"])
def test_s4_qa_preflight_rejects_named_worker_acl_on_tracked_source(
    tmp_path, monkeypatch, acl_kind
):
    root, tracked = _source_tree(tmp_path)
    _isolate_mode_bits(monkeypatch)

    def getxattr(path, attribute, *, follow_symlinks=True):
        if Path(path) == tracked and attribute == "system.posix_acl_access":
            return f"synthetic-{acl_kind}-acl-grants-worker-write".encode()
        return _no_acl(path, attribute, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(sandbox.os, "getxattr", getxattr)
    with pytest.raises(ContractError, match="extended POSIX ACL"):
        qa_run._require_worker_source_read_only(root, _WORKER_UID, _WORKER_GID)


def test_s4_qa_preflight_rejects_directory_default_acl(tmp_path, monkeypatch):
    root, _tracked = _source_tree(tmp_path)
    _isolate_mode_bits(monkeypatch)

    def getxattr(path, attribute, *, follow_symlinks=True):
        if Path(path) == root and attribute == "system.posix_acl_default":
            return b"synthetic-default-acl-grants-worker-write-to-children"
        return _no_acl(path, attribute, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(sandbox.os, "getxattr", getxattr)
    with pytest.raises(ContractError, match="extended POSIX ACL"):
        qa_run._require_worker_source_read_only(root, _WORKER_UID, _WORKER_GID)


def test_s4_qa_preflight_fails_closed_when_acl_inspection_is_denied(tmp_path, monkeypatch):
    root, _tracked = _source_tree(tmp_path)
    _isolate_mode_bits(monkeypatch)

    def denied(path, _attribute, *, follow_symlinks=True):
        raise OSError(errno.EPERM, "ACL inspection denied", os.fspath(path))

    monkeypatch.setattr(sandbox.os, "getxattr", denied)
    with pytest.raises(ContractError, match="ACL inspection failed"):
        qa_run._require_worker_source_read_only(root, _WORKER_UID, _WORKER_GID)


def test_s4_qa_preflight_accepts_source_without_extended_acls(tmp_path, monkeypatch):
    root, _tracked = _source_tree(tmp_path)
    _isolate_mode_bits(monkeypatch)
    monkeypatch.setattr(sandbox.os, "getxattr", _no_acl)

    assert qa_run._require_worker_source_read_only(
        root, _WORKER_UID, _WORKER_GID,
    ) is None


def _signer_socket(tmp_path: Path) -> tuple[socket.socket, Path]:
    socket_dir = tmp_path / "synthetic-signer"
    socket_dir.mkdir(mode=0o750)
    os.chmod(socket_dir, 0o750)
    socket_path = socket_dir / "signer.sock"
    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    endpoint.bind(str(socket_path))
    endpoint.listen(1)
    os.chmod(socket_path, 0o660)
    return endpoint, socket_path


def _no_acl_xattr(_path, _attribute, *, follow_symlinks=True):
    raise OSError(errno.ENODATA, "no ACL xattr")


@pytest.mark.skipif(not _LINUX, reason="POSIX ACL checks require Linux")
def test_s4_signer_guard_rejects_access_acl_on_socket(tmp_path, monkeypatch):
    endpoint, socket_path = _signer_socket(tmp_path)
    try:
        def getxattr(path, attribute, *, follow_symlinks=True):
            if (os.fspath(path) == str(socket_path) and
                    attribute == "system.posix_acl_access"):
                return b"synthetic-access-acl"
            return _no_acl_xattr(path, attribute, follow_symlinks=follow_symlinks)

        monkeypatch.setattr(sandbox.os, "getxattr", getxattr)
        with pytest.raises(ContractError, match="extended ACL"):
            sandbox.require_worker_cannot_access_signer(
                str(socket_path), worker_uid=_WORKER_UID, worker_gid=_WORKER_GID,
            )
    finally:
        endpoint.close()


@pytest.mark.skipif(not _LINUX, reason="POSIX ACL checks require Linux")
def test_s4_signer_guard_rejects_default_acl_on_socket_parent(tmp_path, monkeypatch):
    endpoint, socket_path = _signer_socket(tmp_path)
    try:
        def getxattr(path, attribute, *, follow_symlinks=True):
            if (os.fspath(path) == str(socket_path.parent) and
                    attribute == "system.posix_acl_default"):
                return b"synthetic-default-acl"
            return _no_acl_xattr(path, attribute, follow_symlinks=follow_symlinks)

        monkeypatch.setattr(sandbox.os, "getxattr", getxattr)
        with pytest.raises(ContractError, match="extended ACL"):
            sandbox.require_worker_cannot_access_signer(
                str(socket_path), worker_uid=_WORKER_UID, worker_gid=_WORKER_GID,
            )
    finally:
        endpoint.close()


@pytest.mark.skipif(not _LINUX, reason="POSIX ACL checks require Linux")
def test_s4_signer_guard_rejects_access_acl_on_traversed_ancestor(tmp_path, monkeypatch):
    endpoint, socket_path = _signer_socket(tmp_path)
    ancestor = socket_path.parent.parent
    try:
        def getxattr(path, attribute, *, follow_symlinks=True):
            if (os.fspath(path) == str(ancestor) and
                    attribute == "system.posix_acl_access"):
                return b"synthetic-ancestor-acl"
            return _no_acl_xattr(path, attribute, follow_symlinks=follow_symlinks)

        monkeypatch.setattr(sandbox.os, "getxattr", getxattr)
        with pytest.raises(ContractError, match="extended ACL"):
            sandbox.require_worker_cannot_access_signer(
                str(socket_path), worker_uid=_WORKER_UID, worker_gid=_WORKER_GID,
            )
    finally:
        endpoint.close()


@pytest.mark.skipif(not _LINUX, reason="POSIX signer path checks require Linux")
def test_s4_signer_guard_rejects_nonsticky_world_writable_ancestor(tmp_path, monkeypatch):
    unsafe_ancestor = tmp_path / "u"
    unsafe_ancestor.mkdir()
    os.chmod(unsafe_ancestor, 0o777)
    socket_parent = unsafe_ancestor / "r"
    socket_parent.mkdir(mode=0o750)
    os.chmod(socket_parent, 0o750)
    socket_path = socket_parent / "s"
    endpoint = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    endpoint.bind(str(socket_path))
    endpoint.listen(1)
    os.chmod(socket_path, 0o660)
    try:
        monkeypatch.setattr(sandbox.os, "getxattr", _no_acl_xattr)
        with pytest.raises(ContractError, match="worker-writable directory component"):
            sandbox.require_worker_cannot_access_signer(
                str(socket_path), worker_uid=_WORKER_UID, worker_gid=_WORKER_GID,
            )
    finally:
        endpoint.close()


@pytest.mark.skipif(not _LINUX, reason="POSIX signer path checks require Linux")
def test_s4_signer_guard_allows_runner_owned_entry_under_sticky_tmp(tmp_path, monkeypatch):
    endpoint, socket_path = _signer_socket(tmp_path)
    try:
        tmp_stat = Path("/tmp").stat()
        assert tmp_stat.st_mode & stat.S_ISVTX
        resolved_socket = socket_path.resolve()
        assert Path("/tmp") in resolved_socket.parents
        first_tmp_entry = Path("/tmp") / resolved_socket.relative_to("/tmp").parts[0]
        assert first_tmp_entry.stat().st_uid == os.geteuid()
        monkeypatch.setattr(sandbox.os, "getxattr", _no_acl_xattr)
        assert sandbox.require_worker_cannot_access_signer(
            str(socket_path), worker_uid=_WORKER_UID, worker_gid=_WORKER_GID,
        ) is None
    finally:
        endpoint.close()


@pytest.mark.skipif(not _LINUX, reason="POSIX ACL checks require Linux")
def test_s4_signer_guard_fails_closed_when_acl_inspection_is_denied(tmp_path, monkeypatch):
    endpoint, socket_path = _signer_socket(tmp_path)
    try:
        def denied(_path, _attribute, *, follow_symlinks=True):
            raise OSError(errno.EPERM, "ACL inspection denied")

        monkeypatch.setattr(sandbox.os, "getxattr", denied)
        with pytest.raises(ContractError, match="ACL inspection failed"):
            sandbox.require_worker_cannot_access_signer(
                str(socket_path), worker_uid=_WORKER_UID, worker_gid=_WORKER_GID,
            )
    finally:
        endpoint.close()


@pytest.mark.skipif(not _LINUX, reason="POSIX group inheritance requires Linux")
def test_s4_snapshot_and_qa_output_directories_inherit_worker_group(tmp_path):
    """Run the WSL receiver and output allocator through their real POSIX paths."""
    worker_gid = os.getegid()
    assert worker_gid > 0

    source = tmp_path / "source-repository"
    source.mkdir()
    env = os.environ.copy()
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "S4 Synthetic Fixture",
        "GIT_AUTHOR_EMAIL": "s4-fixture@invalid.example",
        "GIT_COMMITTER_NAME": "S4 Synthetic Fixture",
        "GIT_COMMITTER_EMAIL": "s4-fixture@invalid.example",
    })

    def git(*args: str, cwd: Path, binary: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
            check=False, text=not binary,
        )

    initialized = git("init", "--quiet", "-b", "s4-worker-group-test", cwd=source)
    assert initialized.returncode == 0, initialized.stderr
    (source / "fixture.txt").write_text("synthetic snapshot fixture\n", encoding="utf-8")
    assert git("add", "fixture.txt", cwd=source).returncode == 0
    committed = git("commit", "--quiet", "-m", "synthetic snapshot fixture", cwd=source)
    assert committed.returncode == 0, committed.stderr
    head_result = git("rev-parse", "--verify", "HEAD", cwd=source)
    assert head_result.returncode == 0, head_result.stderr
    expected_head = head_result.stdout.strip()
    bundle = git("bundle", "create", "-", "refs/heads/s4-worker-group-test", cwd=source, binary=True)
    assert bundle.returncode == 0, bundle.stderr
    assert bundle.stdout

    snapshot_root = tmp_path / "snapshot-root"
    snapshot_root.mkdir(mode=0o2710)
    os.chmod(snapshot_root, 0o2710)
    run_id = uuid.uuid4().hex
    received = subprocess.run(
        [sys.executable, "-c", _WSL_RECEIVER, str(snapshot_root), run_id,
         expected_head, "s4-worker-group-test", str(worker_gid), str(1024 * 1024)],
        cwd=tmp_path, env=env, input=bundle.stdout, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=90, check=False,
    )
    assert received.returncode == 0, received.stderr.decode("utf-8", errors="replace")
    response = json.loads(received.stdout)
    assert response == {
        "schema_version": 1,
        "run_id": run_id,
        "candidate_head": expected_head,
        "bundle_sha256": hashlib.sha256(bundle.stdout).hexdigest(),
        "bundle_bytes": len(bundle.stdout),
    }

    snapshot_run = snapshot_root / run_id
    snapshot_repo = snapshot_run / "repo"
    run_stat = snapshot_run.stat(follow_symlinks=False)
    repo_stat = snapshot_repo.stat(follow_symlinks=False)
    assert run_stat.st_gid == worker_gid
    assert stat.S_IMODE(run_stat.st_mode) == 0o2710
    assert repo_stat.st_gid == worker_gid
    assert stat.S_IMODE(repo_stat.st_mode) == 0o2750

    output_dir, relative_output = _safe_output_dir(snapshot_repo, worker_gid)
    output_base = snapshot_repo / ".vst-qa-runs"
    base_stat = output_base.stat(follow_symlinks=False)
    output_stat = output_dir.stat(follow_symlinks=False)
    assert relative_output == f".vst-qa-runs/{output_dir.name}"
    assert base_stat.st_gid == worker_gid
    assert stat.S_IMODE(base_stat.st_mode) == 0o2710
    assert output_stat.st_gid == worker_gid
    assert stat.S_IMODE(output_stat.st_mode) == 0o730
