"""Focused S2 inactive bootstrap selector behavior in disposable POSIX fixtures.

These tests never invoke the production CLI or use /etc, /opt, /run, the real Store,
or systemd. They skip on Windows because the production contract depends on POSIX links,
UID/GID/modes, fcntl, and root-owned fixture artifacts.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.vst import bootstrap_runtime as runtime
from tools.vst import runtime_bundle as bundle
from tools.vst.contracts import ContractError

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX filesystem identity contract")

HEAD_OLD = "1" * 40
HEAD_NEW = "2" * 40
HELPER_HEAD = "3" * 40
ARCHIVE_SHA = "4" * 64
SOURCE_PLAN_SHA = "7" * 64
INVENTORY_SHA = "8" * 64
COMPILER_SHA = "9" * 64
SPEC_SHA = "5" * 64
HELPER_SOURCE_SHA = "6" * 64
UNITS = bundle.UNITS


def _write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def _make_tree(path: Path, head: str, archive: str, *, unit_tag: bytes) -> None:
    path.mkdir(parents=True)
    (path / "tools/vst/systemd").mkdir(parents=True)
    (path / "docs").mkdir()
    for unit in UNITS:
        _write(path / "tools/vst/systemd" / unit, unit_tag + unit.encode())
    _write(path / "docs/SANDBOX_SPEC.md", b"spec fixture")
    marker = {
        "archive_sha256": archive,
        "compiler_path": "/usr/bin/cc",
        "compiler_resolved_path": "/usr/bin/x86_64-linux-gnu-gcc-13",
        "compiler_sha256": COMPILER_SHA,
        "compiler_symlink_target": "/etc/alternatives/cc",
        "head": head,
        "inventory_sha256": INVENTORY_SHA,
        "plan_sha256": SOURCE_PLAN_SHA,
        "schema": 3,
    }
    _write(path / ".vst-runtime-manifest.json", json.dumps(marker, sort_keys=True, separators=(",", ":")).encode())
    for directory in sorted((p for p in path.rglob("*") if p.is_dir()), reverse=True):
        directory.chmod(0o755)
    path.chmod(0o755)


class _PathMap:
    """Map only the selector's fixed /opt namespace into a disposable fixture."""
    def __init__(self, root: Path):
        self.root = str(root)

    def _map(self, value):
        if isinstance(value, str) and (value == "/opt" or value.startswith("/opt/")):
            return self.root + value
        return value

    def __getattr__(self, name):
        import posixpath
        attr = getattr(posixpath, name)
        if name in {"exists", "lexists", "isdir", "isfile", "islink", "getsize"}:
            return lambda path, *args, **kwargs: attr(self._map(path), *args, **kwargs)
        return attr


class _OSMap:
    def __init__(self, root: Path):
        self._root = str(root)
        self.path = _PathMap(root)

    def _map(self, value):
        if isinstance(value, str) and (value == "/opt" or value.startswith("/opt/")):
            return self._root + value
        return value

    def __getattr__(self, name):
        attr = getattr(os, name)
        if name in {"lstat", "stat", "open", "readlink", "listdir", "scandir",
                    "chmod", "chown", "mkdir", "remove", "unlink", "rmdir"}:
            return lambda path, *args, **kwargs: attr(self._map(path), *args, **kwargs)
        if name in {"replace", "rename", "symlink", "link"}:
            if name == "symlink":
                return lambda target, link_name, *args, **kwargs: attr(
                    target, self._map(link_name), *args, **kwargs)
            return lambda src, dst, *args, **kwargs: attr(self._map(src), self._map(dst), *args, **kwargs)
        if name == "walk":
            def walk(path, *args, **kwargs):
                physical = self._map(path)
                prefix = self._root
                for current, dirs, files in attr(physical, *args, **kwargs):
                    logical = ("/opt" + current[len(prefix) + len("/opt"):]
                               if current.startswith(prefix + "/opt") else current)
                    yield logical, dirs, files
            return walk
        return attr


@pytest.fixture
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if os.geteuid() != 0:
        pytest.skip("fixture requires root to model root-owned runtime artifacts")
    root = tmp_path / "host"
    opt = root / "opt"
    units_dir = root / "etc/systemd/system"
    helper_dir = root / "usr/local/libexec"
    for directory in (opt, units_dir, helper_dir):
        directory.mkdir(parents=True)
        directory.chmod(0o755)

    old_path = opt / ("vst-runtime-" + HEAD_OLD)
    new_path = opt / ("vst-runtime-" + HEAD_NEW)
    _make_tree(old_path, HEAD_OLD, "7" * 64, unit_tag=b"old:")
    _make_tree(new_path, HEAD_NEW, ARCHIVE_SHA, unit_tag=b"new:")
    selector = opt / "vst-runtime"
    # Preserve the real fixed target spelling while the path adapter redirects /opt.
    selector.symlink_to("/opt/" + old_path.name)

    for unit in UNITS:
        _write(units_dir / unit, b"old:" + unit.encode())

    helper = helper_dir / ("vst-s4-worker-exec-" + HELPER_HEAD)
    _write(helper, b"synthetic helper bytes", 0o4750)
    os.chown(helper, 0, 988)
    helper.chmod(0o4750)

    parents = {str(opt): (0, 0, 0o755), str(units_dir): (0, 0, 0o755),
               str(helper_dir): (0, 0, 0o755)}
    monkeypatch.setattr(bundle, "PARENTS", parents)
    monkeypatch.setattr(bundle, "UNIT_DIR", str(units_dir))
    monkeypatch.setattr(bundle, "RUNTIME_LINK", str(selector))
    monkeypatch.setattr(bundle, "HELPER_BASE", str(helper_dir))
    monkeypatch.setattr(runtime, "PARENTS", parents)
    monkeypatch.setattr(runtime, "UNIT_DIR", str(units_dir))
    monkeypatch.setattr(runtime, "RUNTIME_LINK", str(selector))
    monkeypatch.setattr(runtime, "HELPER_BASE", str(helper_dir))
    # Production paths remain fixed; module-local filesystem adapters redirect only /opt
    # into this disposable fixture so apply/recover execute their real logic safely.
    monkeypatch.setattr(bundle, "os", _OSMap(root))
    monkeypatch.setattr(runtime, "os", _OSMap(root))
    original_bundle_fingerprint = bundle._fingerprint
    def mapped_fingerprint(path: str, *, absent: bool = False):
        if path == "/opt" or path.startswith("/opt/"):
            path = str(root) + path
        return original_bundle_fingerprint(path, absent=absent)
    monkeypatch.setattr(bundle, "_fingerprint", mapped_fingerprint)
    monkeypatch.setattr(bundle, "_read_small_json",
                        lambda _path: json.loads((new_path / ".vst-runtime-manifest.json").read_bytes()))
    journal = root / "var/lib/vst-bootstrap-transitions"
    journal.parent.mkdir(parents=True)
    monkeypatch.setattr(runtime, "JOURNAL_ROOT", str(journal))
    monkeypatch.setattr(runtime, "_require_root", lambda: None)
    monkeypatch.setattr(runtime, "_require_fixed_parents", lambda: None)
    monkeypatch.setattr(runtime, "_require_unconfigured_and_inactive", lambda: None)
    monkeypatch.setattr(runtime, "_sync_dir", lambda _path: None)

    helper_fp = bundle._fingerprint(str(helper))
    assert (helper_fp["kind"], helper_fp["uid"], helper_fp["gid"], helper_fp["mode"],
            helper_fp["nlink"]) == ("file", 0, 988, 0o4750, 1)
    manifest = bundle.build_manifest(source_head=HEAD_NEW, archive_sha256=ARCHIVE_SHA,
                                     source_plan_sha256=SOURCE_PLAN_SHA,
                                     target_inventory_sha256=INVENTORY_SHA,
                                     compiler_sha256=COMPILER_SHA,
                                     spec_sha256=hashlib.sha256(b"spec fixture").hexdigest(),
                                     helper_head=HELPER_HEAD, helper_source_sha256=HELPER_SOURCE_SHA)
    return SimpleNamespace(root=root, selector=selector, old=old_path, new=new_path,
                           units=units_dir, helper=helper, journal=journal,
                           manifest=manifest, digest=bundle.manifest_sha256(manifest))


def test_apply_requires_exact_external_manifest_pin(host):
    before = os.readlink(host.selector)
    with pytest.raises(ContractError, match="review pin"):
        runtime.apply(host.manifest, "0" * 64)
    assert os.readlink(host.selector) == before
    assert not host.journal.exists()


def test_selector_allows_existing_root_config_dir_but_still_requires_inactive_units(monkeypatch):
    validated = []
    unit_queries = []

    def validate_existing_config():
        # The production validator inspects only /etc/vst-runner's metadata.
        # This spy makes it explicit that the selector does not read config files.
        validated.append(True)

    class Result:
        returncode = 0

        def __init__(self, stdout):
            self.stdout = stdout

    def systemctl(arguments, **_kwargs):
        if arguments[1] == "list-jobs":
            return Result("No jobs running.\n")
        if "--property=ActiveState" in arguments:
            unit_queries.append(arguments[2])
            return Result("inactive\n")
        if "--property=ControlGroup" in arguments:
            return Result("\n")
        raise AssertionError(f"unexpected systemctl query: {arguments!r}")

    monkeypatch.setattr(runtime, "validate_root_config_directory", validate_existing_config)
    monkeypatch.setattr(runtime.os.path, "lexists", lambda _path: False)
    monkeypatch.setattr(runtime.subprocess, "run", systemctl)
    runtime._require_unconfigured_and_inactive()

    assert validated == [True]
    assert set(unit_queries) == set(UNITS)


def test_selector_fails_closed_before_systemctl_when_existing_config_dir_is_unsafe(monkeypatch):
    def reject_unsafe_config():
        raise ContractError("unsafe root configuration directory")

    monkeypatch.setattr(runtime, "validate_root_config_directory", reject_unsafe_config)
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("systemctl queried after config validation failed"),
    )

    with pytest.raises(ContractError, match="unsafe root configuration directory"):
        runtime._require_unconfigured_and_inactive()


def test_apply_selects_exact_staged_tree_without_starting_services(host, capsys):
    runtime.apply(host.manifest, host.digest)
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_NEW
    for unit in UNITS:
        assert (host.units / unit).read_bytes() == (host.new / "tools/vst/systemd" / unit).read_bytes()
    output = capsys.readouterr().out
    assert "services_started_or_reloaded=false" in output
    assert "store_opened_or_changed=false" in output
    state = json.loads((host.journal / host.digest[:32] / "state.json").read_bytes())
    assert state["status"] == "complete"
    assert all(item["state"] == "complete" for item in state["units"].values())


def test_recovery_restores_old_selector_and_units_and_retains_new_files(host):
    runtime.apply(host.manifest, host.digest)
    txid = host.digest[:32]
    runtime.recover(txid, host.digest)
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_OLD
    for unit in UNITS:
        assert (host.units / unit).read_bytes() == b"old:" + unit.encode()
    retained = host.units / ".vst-bootstrap-retained"
    for unit in UNITS:
        copies = list(retained.glob(unit + "-new-" + host.digest[:16] + "-*"))
        assert len(copies) == 1
        assert copies[0].read_bytes() == (host.new / "tools/vst/systemd" / unit).read_bytes()
    assert host.new.exists()


def test_recovery_preflights_whole_set_before_any_restore(host):
    runtime.apply(host.manifest, host.digest)
    damaged = host.units / UNITS[-1]
    damaged.write_bytes(b"third-party bytes")
    with pytest.raises(ContractError, match="unknown state"):
        runtime.recover(host.digest[:32], host.digest)
    # Selector and earlier paths stay on the selected revision: no partial rollback occurred.
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_NEW
    assert all((host.units / unit).read_bytes() == (host.new / "tools/vst/systemd" / unit).read_bytes()
               for unit in UNITS[:-1])
    assert damaged.read_bytes() == b"third-party bytes"


def test_interrupted_apply_is_recovered_from_actual_fingerprints(host, monkeypatch):
    original = runtime._atomic_file
    calls = 0

    def fail_once(path: str, data: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected ordinary exception before unit rename")
        original(path, data)

    monkeypatch.setattr(runtime, "_atomic_file", fail_once)
    with pytest.raises(OSError, match="injected"):
        runtime.apply(host.manifest, host.digest)
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_NEW
    monkeypatch.setattr(runtime, "_atomic_file", original)
    runtime.recover(host.digest[:32], host.digest)
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_OLD
    assert all((host.units / unit).read_bytes() == b"old:" + unit.encode() for unit in UNITS)


def test_partial_journal_state_write_does_not_strand_next_apply(host, monkeypatch):
    original_write = runtime.os.write
    injected = False

    def partial_state_write(fd: int, data: bytes) -> int:
        nonlocal injected
        opened_path = os.readlink(f"/proc/self/fd/{fd}")
        if not injected and "/.state-" in opened_path:
            injected = True
            original_write(fd, data[:max(1, len(data) // 2)])
            raise OSError("injected ordinary exception during journal state write")
        return original_write(fd, data)

    monkeypatch.setattr(runtime.os, "write", partial_state_write)
    with pytest.raises(OSError, match="during journal state write"):
        runtime.apply(host.manifest, host.digest)
    assert injected

    monkeypatch.setattr(runtime.os, "write", original_write)
    runtime.apply(host.manifest, host.digest)
    state = json.loads((host.journal / host.digest[:32] / "state.json").read_bytes())
    assert state["status"] == "complete"
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_NEW


def test_partial_retained_copy_does_not_strand_recovery(host, monkeypatch):
    runtime.apply(host.manifest, host.digest)
    original_write = runtime.os.write
    injected = False

    def partial_retained_write(fd: int, data: bytes) -> int:
        nonlocal injected
        opened_path = os.readlink(f"/proc/self/fd/{fd}")
        if not injected and "/.vst-bootstrap-retained/" in opened_path:
            injected = True
            original_write(fd, data[:max(1, len(data) // 2)])
            raise OSError("injected ordinary exception during retained copy")
        return original_write(fd, data)

    monkeypatch.setattr(runtime.os, "write", partial_retained_write)
    with pytest.raises(OSError, match="during retained copy"):
        runtime.recover(host.digest[:32], host.digest)
    assert injected

    monkeypatch.setattr(runtime.os, "write", original_write)
    runtime.recover(host.digest[:32], host.digest)
    assert os.readlink(host.selector) == "/opt/vst-runtime-" + HEAD_OLD
    retained = host.units / ".vst-bootstrap-retained"
    for unit in UNITS:
        assert (host.units / unit).read_bytes() == b"old:" + unit.encode()
        copies = list(retained.glob(unit + "-new-" + host.digest[:16] + "-*"))
        expected = (host.new / "tools/vst/systemd" / unit).read_bytes()
        if unit == UNITS[0]:
            # The injected partial artifact is retained; retry uses a fresh exclusive name.
            assert len(copies) == 2
            assert any(copy.read_bytes() == expected[:max(1, len(expected) // 2)] for copy in copies)
        else:
            assert len(copies) == 1
        assert any(copy.read_bytes() == expected for copy in copies)


def test_runtime_manifest_rejects_unknown_fields_and_wrong_old_tree(host):
    extra = dict(host.manifest, surprise=True)
    with pytest.raises(ContractError, match="fields"):
        bundle.validate_manifest(extra)
    stale = dict(host.manifest)
    stale["old_runtime_tree_sha256"] = "0" * 64
    assert bundle.validate_manifest(stale) == stale
    with pytest.raises(ContractError, match="previous immutable runtime"):
        runtime._current_old_state(stale)

