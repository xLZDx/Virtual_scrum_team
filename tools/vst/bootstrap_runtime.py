#!/usr/bin/env python3.12
"""Select or recover one reviewed S2 runtime on a pristine bootstrap host.

This root-only command never starts/reloads units and never opens the Store.
Its manifest digest is an external review pin, not a signature or self-approval.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from typing import Any

from .contracts import ContractError, canonical_bytes
from .runtime_bundle import (
    HELPER_BASE, PARENTS, RUNTIME_LINK, SCHEMA, UNIT_DIR, UNITS,
    build_manifest, load_canonical_manifest, manifest_sha256, tree_sha256,
)

CONFIG_SENTINELS = ("/etc/vst-runner", "/run/vst-supervisor", "/run/vst-runner")
JOURNAL_ROOT = "/var/lib/vst-bootstrap-transitions"
SYSTEMCTL = "/usr/bin/systemctl"
CGROUP_ROOT = "/sys/fs/cgroup"
SYSTEM_SLICE = "/sys/fs/cgroup/system.slice"
MAX_FILE = 64 * 1024 * 1024
PREPARING_PREFIX = ".preparing-"


def refuse(message: str) -> None:
    raise ContractError("bootstrap transition refused: " + message)


def _sync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextlib.contextmanager
def _transition_lock(create: bool):
    root = _safe_journal_root(create=create)
    path = os.path.join(root, ".lock")
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if not create:
            refuse("transition lock is absent")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.fsync(fd)
        os.close(fd)
        _sync_dir(root)
    else:
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
            refuse("transition lock has unexpected metadata")
    import fcntl
    fd = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_regular(path: str, *, uid: int, mode: int, maximum: int = MAX_FILE) -> bytes:
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode or info.st_size > maximum:
        refuse("unexpected file type, owner, mode, or size at " + path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            refuse("file changed while opening " + path)
        data = b""
        while len(data) <= maximum:
            chunk = os.read(fd, min(65536, maximum + 1 - len(data)))
            if not chunk:
                break
            data += chunk
        if len(data) > maximum:
            refuse("file exceeded its read limit at " + path)
        return data
    finally:
        os.close(fd)


def _fingerprint(path: str, *, absent: bool = False) -> dict[str, Any]:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        if absent:
            return {"kind": "absent"}
        raise
    base = {"uid": info.st_uid, "gid": info.st_gid, "mode": stat.S_IMODE(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):
        return {"kind": "symlink", "target": os.readlink(path), **base}
    if not stat.S_ISREG(info.st_mode):
        refuse("path has a directory or special-file type: " + path)
    digest = hashlib.sha256(_read_regular(path, uid=info.st_uid, mode=stat.S_IMODE(info.st_mode))).hexdigest()
    return {"kind": "file", "sha256": digest, "uid": info.st_uid, "gid": info.st_gid,
            "mode": stat.S_IMODE(info.st_mode), "size": info.st_size, "nlink": info.st_nlink}


def _require_fixed_parents() -> None:
    for path in ("/", "/usr", "/usr/local", "/usr/local/lib", HELPER_BASE,
                 "/etc", "/etc/systemd",
                 UNIT_DIR, "/var", "/var/lib", "/run", "/opt", "/sys", "/sys/fs", CGROUP_ROOT):
        info = os.lstat(path)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            refuse("installation parent changed or is not root-controlled: " + path)
    for path, expected in PARENTS.items():
        info = os.lstat(path)
        if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != expected:
            refuse("installation parent mode/group differs from fixed contract: " + path)


def _require_unconfigured_and_inactive() -> None:
    for path in CONFIG_SENTINELS:
        if os.path.lexists(path):
            refuse("configured/runtime path exists: " + path)
    for unit in UNITS:
        result = subprocess.run([SYSTEMCTL, "show", unit, "--property=ActiveState", "--value"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False, text=True, timeout=10)
        if result.returncode != 0 or result.stdout.strip() != "inactive":
            refuse("unit is not verifiably inactive: " + unit)
    jobs = subprocess.run([SYSTEMCTL, "list-jobs", "--no-legend", "--no-pager"],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False, text=True, timeout=10)
    if jobs.returncode != 0:
        refuse("systemd jobs could not be enumerated")
    for line in jobs.stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        if line.strip() == "No jobs running.":
            continue
        if len(fields) < 4 or not fields[0].isdigit():
            refuse("systemd returned an unparsable job row")
        if fields[1] in UNITS:
            refuse("systemd has a pending job for " + fields[1])
    for unit in UNITS:
        result = subprocess.run([SYSTEMCTL, "show", unit, "--property=ControlGroup", "--value"],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False, text=True, timeout=10)
        if result.returncode != 0:
            refuse("unit cgroup could not be inspected: " + unit)
        cgroup = result.stdout.strip()
        if not cgroup:
            continue
        if not cgroup.startswith("/") or any(part in (".", "..") for part in cgroup.split("/")):
            refuse("systemd returned an invalid cgroup path")
        path = os.path.join(CGROUP_ROOT, cgroup.lstrip("/"))
        if os.path.lexists(path):
            _require_empty_cgroup(path, unit)
    # An inactive unit can still leave a stale cgroup that systemd no longer reports.
    if os.path.isdir(SYSTEM_SLICE) and not os.path.islink(SYSTEM_SLICE):
        for unit in UNITS:
            path = os.path.join(SYSTEM_SLICE, unit)
            if os.path.lexists(path):
                _require_empty_cgroup(path, unit)


def _require_empty_cgroup(path: str, unit: str) -> None:
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode):
        refuse("service cgroup path is not a real directory: " + unit)
    def onerror(error: OSError) -> None:
        raise error
    for root, dirs, files in os.walk(path, followlinks=False, onerror=onerror):
        if any(os.path.islink(os.path.join(root, name)) for name in dirs + files):
            refuse("symlink found in service cgroup inventory")
        procs = os.path.join(root, "cgroup.procs")
        if os.path.exists(procs):
            procs_info = os.lstat(procs)
            if not stat.S_ISREG(procs_info.st_mode) or procs_info.st_uid != 0:
                refuse("cgroup process inventory is not a root-controlled read-only file")
            fd = os.open(procs, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                data = os.read(fd, 65537)
            finally:
                os.close(fd)
            if len(data) > 65536:
                refuse("cgroup process inventory exceeded its bound")
            if data.strip():
                refuse("S2 service cgroup is populated: " + unit)


def _verify_manifest_artifacts(manifest: dict[str, Any]) -> None:
    runtime = manifest["runtime_path"]
    if tree_sha256(runtime) != manifest["runtime_tree_sha256"]:
        refuse("staged runtime tree digest differs from reviewed manifest")
    marker_path = os.path.join(runtime, ".vst-runtime-manifest.json")
    marker = json.loads(_read_regular(marker_path, uid=0, mode=0o644, maximum=4096))
    expected_marker = {
        "archive_sha256": manifest["archive_sha256"],
        "compiler_path": manifest["compiler_path"],
        "compiler_resolved_path": manifest["compiler_resolved_path"],
        "compiler_sha256": manifest["compiler_sha256"],
        "compiler_symlink_target": manifest["compiler_symlink_target"],
        "head": manifest["source_head"],
        "inventory_sha256": manifest["target_inventory_sha256"],
        "plan_sha256": manifest["source_plan_sha256"],
        "schema": 3,
    }
    if marker != expected_marker:
        refuse("runtime marker differs from reviewed manifest")
    spec = os.path.join(runtime, "docs", "SANDBOX_SPEC.md")
    if hashlib.sha256(_read_regular(spec, uid=0, mode=0o644)).hexdigest() != manifest["spec_sha256"]:
        refuse("staged sandbox specification digest differs")
    helper = manifest["helper_path"]
    fp = _fingerprint(helper)
    if (fp["kind"] != "file" or fp["uid"] != 0 or fp["gid"] != manifest["helper_gid"]
            or fp["mode"] != manifest["helper_mode"] or fp["sha256"] != manifest["helper_binary_sha256"]
            or os.lstat(helper).st_nlink != manifest["helper_nlink"]):
        refuse("staged worker helper differs from reviewed identity/digest")
    for unit in UNITS:
        path = os.path.join(runtime, "tools/vst/systemd", unit)
        if _fingerprint(path) != manifest["units"][unit]["new"]:
            refuse("staged unit differs from reviewed digest: " + unit)


def _current_old_state(manifest: dict[str, Any]) -> None:
    if _fingerprint(RUNTIME_LINK) != manifest["old_selector"]:
        refuse("runtime selector differs from reviewed old fingerprint")
    if tree_sha256(manifest["old_selector"]["target"]) != manifest["old_runtime_tree_sha256"]:
        refuse("previous immutable runtime tree differs from reviewed baseline")
    for unit in UNITS:
        if _fingerprint(os.path.join(UNIT_DIR, unit), absent=True) != manifest["units"][unit]["old"]:
            refuse("fixed unit differs from reviewed old fingerprint: " + unit)
    if os.path.lexists(manifest["runtime_path"]):
        # Stage-only may have created this exact immutable destination.
        _verify_manifest_artifacts(manifest)
    else:
        refuse("reviewed staged runtime is absent")


def _write_exclusive(path: str, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                refuse("short write while creating retained transition record")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _journal_state(directory: str, state: dict[str, Any]) -> None:
    encoded = canonical_bytes(state) + b"\n"
    temp = os.path.join(directory, ".state-" + secrets.token_hex(8))
    _write_exclusive(temp, encoded, 0o600)
    os.replace(temp, os.path.join(directory, "state.json"))
    _sync_dir(directory)


def _safe_journal_root(create: bool) -> str:
    try:
        info = os.lstat(JOURNAL_ROOT)
    except FileNotFoundError:
        if not create:
            refuse("transition journal root is absent")
        os.mkdir(JOURNAL_ROOT, 0o700)
        _sync_dir("/var/lib")
        info = os.lstat(JOURNAL_ROOT)
    if not stat.S_ISDIR(info.st_mode) or (info.st_uid, stat.S_IMODE(info.st_mode)) != (0, 0o700):
        refuse("journal root must be a root-owned mode-0700 directory")
    return JOURNAL_ROOT


def _prepare_journal(manifest: dict[str, Any], digest: str) -> tuple[str, dict[str, Any]]:
    root = _safe_journal_root(create=True)
    txid = digest[:32]
    directory = os.path.join(root, txid)
    if os.path.lexists(directory):
        refuse("journal already exists; inspect or recover it explicitly")
    preparation = os.path.join(root, PREPARING_PREFIX + txid + "-" + secrets.token_hex(12))
    try:
        os.mkdir(preparation, 0o700)
    except FileExistsError:
        refuse("unique preparation directory unexpectedly exists")
    _sync_dir(root)
    snapshots: dict[str, Any] = {}
    # Persist the exact transition identity and snapshot plan before snapshot I/O. This
    # directory is not a recovery journal until atomically published under its txid.
    _write_exclusive(os.path.join(preparation, "manifest.json"), canonical_bytes(manifest) + b"\n", 0o600)
    prep_state = {"schema": 1, "manifest_sha256": digest, "txid": txid,
                  "status": "preparing",
                  "snapshot_plan": {unit: ("old-" + unit if manifest["units"][unit]["old"]["kind"] == "file" else None)
                                    for unit in UNITS}}
    _write_exclusive(os.path.join(preparation, "state.json"), canonical_bytes(prep_state) + b"\n", 0o600)
    _sync_dir(preparation)
    for unit in UNITS:
        path = os.path.join(UNIT_DIR, unit)
        fp = manifest["units"][unit]["old"]
        if fp["kind"] == "file":
            raw = _read_regular(path, uid=0, mode=fp["mode"])
            if hashlib.sha256(raw).hexdigest() != fp["sha256"] or len(raw) != fp["size"]:
                refuse("old unit changed while preparing its recovery snapshot: " + unit)
            name = "old-" + unit
            _write_exclusive(os.path.join(preparation, name), raw, 0o600)
            snapshots[unit] = name
        else:
            snapshots[unit] = None
    _sync_dir(preparation)
    state = {
        "schema": 1, "manifest_sha256": digest, "status": "prepared",
        "old_selector": manifest["old_selector"], "new_selector": manifest["runtime_path"],
        "units": {unit: {"old": manifest["units"][unit]["old"],
                          "new": manifest["units"][unit]["new"],
                          "snapshot": snapshots[unit], "state": "pending"}
                  for unit in UNITS},
        "selector_state": "pending",
    }
    # Final journal state and directory entry are durable before publication.
    _journal_state(preparation, state)
    _rename_noreplace(preparation, directory)
    _sync_dir(root)
    return directory, state


def _rename_noreplace(source: str, destination: str) -> None:
    """Publish a prepared journal without replacing any existing path."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = getattr(libc, "renameat2", None)
    if operation is None:
        refuse("kernel libc does not expose renameat2 no-replace publication")
    operation.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    operation.restype = ctypes.c_int
    result = operation(-100, os.fsencode(source), -100, os.fsencode(destination), 1)  # AT_FDCWD, RENAME_NOREPLACE
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


def _require_no_pending_journal() -> None:
    root = _safe_journal_root(create=False)
    with os.scandir(root) as entries:
        names = [entry.name for entry in entries]
    for name in names:
        if name == ".lock":
            continue
        if re.fullmatch(r"\.preparing-[0-9a-f]{32}-[0-9a-f]{24}", name):
            directory = os.path.join(root, name)
            info = os.lstat(directory)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
                refuse("unpublished preparation entry has unexpected metadata")
            # It has never been armed for path mutation. Retain it and allow a fresh prepare.
            continue
        if not re.fullmatch(r"[0-9a-f]{32}", name):
            refuse("unexpected entry in transition journal root")
        directory = os.path.join(root, name)
        info = os.lstat(directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
            refuse("unexpected journal entry metadata")
        state_path = os.path.join(directory, "state.json")
        state = json.loads(_read_regular(state_path, uid=0, mode=0o600, maximum=1024 * 1024))
        if not isinstance(state, dict) or state.get("status") not in ("complete", "recovered"):
            refuse("an unfinished transition journal requires explicit recovery")


def _retained_dir() -> str:
    path = os.path.join(UNIT_DIR, ".vst-bootstrap-retained")
    try:
        os.mkdir(path, 0o700)
        _sync_dir(UNIT_DIR)
    except FileExistsError:
        pass
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        refuse("retained-unit quarantine has unexpected metadata")
    return path


def _atomic_symlink(path: str, target: str) -> None:
    parent = os.path.dirname(path)
    temporary = os.path.join(parent, ".vst-link-" + secrets.token_hex(8))
    os.symlink(target, temporary)
    try:
        os.replace(temporary, path)
        _sync_dir(parent)
    except BaseException:
        # A temp symlink is retained for inspection instead of removed.
        raise


def _atomic_file(path: str, data: bytes) -> None:
    parent = os.path.dirname(path)
    temporary = os.path.join(parent, ".vst-unit-" + secrets.token_hex(8))
    _write_exclusive(temporary, data, 0o644)
    os.chown(temporary, 0, 0)
    os.chmod(temporary, 0o644)
    fd = os.open(temporary, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(temporary, path)
        _sync_dir(parent)
    except BaseException:
        # Keep an uninstalled temp file for diagnosis.
        raise


def _retain_current(path: str, target_name: str) -> None:
    retained = _retained_dir()
    target = os.path.join(retained, target_name)
    if os.path.lexists(target):
        refuse("retention destination already exists")
    os.rename(path, target)
    _sync_dir(os.path.dirname(path))
    _sync_dir(retained)


def _apply_one(directory: str, state: dict[str, Any], key: str, path: str,
               item_state: dict[str, Any],
               expected_old: dict[str, Any], expected_new: dict[str, Any],
               new_bytes: bytes | None, new_link: str | None) -> None:
    current = _fingerprint(path, absent=True)
    if current != expected_old:
        refuse("path changed after journal preparation: " + path)
    if (new_bytes is None) == (new_link is None):
        refuse("internal replacement must be exactly one file or link")
    _require_unconfigured_and_inactive()
    item_state[key] = "intent"
    _journal_state(directory, state)
    _require_unconfigured_and_inactive()
    if new_bytes is not None:
        _atomic_file(path, new_bytes)
    else:
        _atomic_symlink(path, new_link or "")
    if _fingerprint(path) != expected_new:
        refuse("new fingerprint did not verify after replacement: " + path)
    item_state[key] = "complete"
    _journal_state(directory, state)


def apply(manifest: dict[str, Any], digest: str) -> None:
    _require_root()
    if manifest_sha256(manifest) != digest:
        refuse("manifest digest does not match externally supplied review pin")
    _require_fixed_parents()
    with _transition_lock(create=True):
        _require_fixed_parents()
        _require_unconfigured_and_inactive()
        _verify_manifest_artifacts(manifest)
        _current_old_state(manifest)
        _require_no_pending_journal()
        directory, state = _prepare_journal(manifest, digest)
        try:
            _require_unconfigured_and_inactive()
            _verify_manifest_artifacts(manifest)
            _current_old_state(manifest)
            state["status"] = "applying"
            _journal_state(directory, state)
            _apply_one(directory, state, "selector_state", RUNTIME_LINK,
                       state,
                       manifest["old_selector"],
                       {"kind": "symlink", "target": manifest["runtime_path"], "uid": 0, "gid": 0, "mode": 0o777},
                       None, manifest["runtime_path"])
            for unit in UNITS:
                path = os.path.join(UNIT_DIR, unit)
                old = manifest["units"][unit]["old"]
                new = manifest["units"][unit]["new"]
                data = _read_regular(os.path.join(manifest["runtime_path"], "tools/vst/systemd", unit), uid=0, mode=0o644)
                _apply_one(directory, state, "state", path, state["units"][unit], old, new, data, None)
            _require_unconfigured_and_inactive()
            if _fingerprint(RUNTIME_LINK) != {"kind": "symlink", "target": manifest["runtime_path"], "uid": 0, "gid": 0, "mode": 0o777}:
                refuse("final selector verification failed")
            state["status"] = "complete"
            _journal_state(directory, state)
        except BaseException:
            state["status"] = "recovery-required"
            _journal_state(directory, state)
            raise
    print("bootstrap_selection=complete")
    print("services_started_or_reloaded=false")
    print("store_opened_or_changed=false")


def _require_root() -> None:
    if os.geteuid() != 0 or os.name != "posix":
        refuse("must run as root on POSIX")


def _load_journal(txid: str, digest: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{32}", txid):
        refuse("invalid journal id")
    root = _safe_journal_root(create=False)
    directory = os.path.join(root, txid)
    info = os.lstat(directory)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        refuse("journal directory metadata is invalid")
    raw_manifest = _read_regular(os.path.join(directory, "manifest.json"), uid=0, mode=0o600, maximum=1024 * 1024)
    manifest = _strict_json(raw_manifest, "journal manifest")
    if manifest_sha256(manifest) != digest or txid != digest[:32]:
        refuse("journal and external manifest digest do not agree")
    raw_state = _read_regular(os.path.join(directory, "state.json"), uid=0, mode=0o600, maximum=1024 * 1024)
    state = _strict_json(raw_state, "journal state")
    required_state_fields = {
        "schema", "manifest_sha256", "status", "old_selector", "new_selector", "units", "selector_state"
    }
    if not isinstance(state, dict) or set(state) != required_state_fields:
        refuse("journal state fields are invalid")
    if (type(state.get("schema")) is not int or state["schema"] != 1
            or state.get("manifest_sha256") != digest
            or state.get("old_selector") != manifest["old_selector"]
            or state.get("new_selector") != manifest["runtime_path"]
            or state.get("status") not in ("prepared", "applying", "recovery-required", "recovering", "complete", "recovered")):
        refuse("journal state does not bind the reviewed manifest")
    if state.get("selector_state") not in ("pending", "intent", "complete", "restore-intent", "restored"):
        refuse("journal selector progress is invalid")
    unit_state = state.get("units")
    if not isinstance(unit_state, dict) or set(unit_state) != set(UNITS):
        refuse("journal unit set is invalid")
    for unit in UNITS:
        item = unit_state[unit]
        expected = manifest["units"][unit]
        if (not isinstance(item, dict) or set(item) != {"old", "new", "snapshot", "state"}
                or item["old"] != expected["old"] or item["new"] != expected["new"]
                or item["snapshot"] not in (None, "old-" + unit)
                or item["state"] not in ("pending", "intent", "complete", "restore-intent", "restored")
                or (expected["old"]["kind"] == "file") != (item["snapshot"] == "old-" + unit)):
            refuse("journal unit snapshot/progress does not bind its reviewed path")
    return directory, manifest, state


def _strict_json(raw: bytes, description: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in items:
            if key in result:
                refuse(description + " contains duplicate fields")
            result[key] = item
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: refuse(description + " contains non-finite values"))
        if canonical_bytes(value) + b"\n" != raw:
            refuse(description + " is not canonical JSON")
        return value
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(description + " is invalid JSON") from exc


def _restore_one(directory: str, journal_state: dict[str, Any], state: dict[str, Any], key: str, path: str,
                 old: dict[str, Any], new: dict[str, Any], snapshot: str | None) -> None:
    current = _fingerprint(path, absent=True)
    if current == old:
        state[key] = "restored"
        _journal_state(directory, journal_state)
        return
    if current != new:
        refuse("recovery refuses third-party/unknown path bytes: " + path)
    state[key] = "restore-intent"
    _journal_state(directory, journal_state)
    _require_unconfigured_and_inactive()
    if old["kind"] == "absent":
        # Preserve the newly selected file by moving it into the retained quarantine.
        retained = _retained_dir()
        name = os.path.basename(path) + "-" + state.get("manifest_sha256", "")[:16]
        destination = os.path.join(retained, name)
        if os.path.lexists(destination):
            refuse("retained artifact already exists")
        os.rename(path, destination)
        _sync_dir(os.path.dirname(path))
        _sync_dir(retained)
    elif old["kind"] == "symlink":
        retained = _retained_dir()
        retained_link = os.path.join(retained, os.path.basename(path) + "-new-link-" + journal_state["manifest_sha256"][:16])
        if os.path.lexists(retained_link):
            info = os.lstat(retained_link)
            if not stat.S_ISLNK(info.st_mode) or os.readlink(retained_link) != current["target"]:
                refuse("retained symlink destination differs from the selected link")
        else:
            os.symlink(current["target"], retained_link)
            _sync_dir(retained)
        _atomic_symlink(path, old["target"])
    elif old["kind"] == "file":
        if not snapshot:
            refuse("old file snapshot is missing")
        raw = _read_regular(os.path.join(directory, snapshot), uid=0, mode=0o600)
        if hashlib.sha256(raw).hexdigest() != old["sha256"] or len(raw) != old["size"]:
            refuse("old-file snapshot does not match reviewed fingerprint")
        new_bytes = _read_regular(path, uid=0, mode=new["mode"])
        if hashlib.sha256(new_bytes).hexdigest() != new["sha256"] or len(new_bytes) != new["size"]:
            refuse("selected unit changed while preserving it")
        retained = _retained_dir()
        # Each recovery attempt gets a fresh no-replace name. A failed partial copy
        # stays retained; it cannot poison the next attempt or overwrite another file.
        retained_path = os.path.join(
            retained,
            os.path.basename(path) + "-new-" + journal_state["manifest_sha256"][:16]
            + "-" + secrets.token_hex(8),
        )
        _write_exclusive(retained_path, new_bytes, 0o600)
        if hashlib.sha256(_read_regular(retained_path, uid=0, mode=0o600)).hexdigest() != new["sha256"]:
            refuse("retained copy of selected unit failed verification")
        _sync_dir(retained)
        _atomic_file(path, raw)
        os.chown(path, old["uid"], old["gid"])
        os.chmod(path, old["mode"])
        _sync_dir(os.path.dirname(path))
    if _fingerprint(path, absent=True) != old:
        refuse("restored path does not match old fingerprint: " + path)
    state[key] = "restored"
    _journal_state(directory, journal_state)


def recover(txid: str, digest: str) -> None:
    _require_root()
    _require_fixed_parents()
    with _transition_lock(create=False):
        _require_fixed_parents()
        _require_unconfigured_and_inactive()
        directory, manifest, state = _load_journal(txid, digest)
        if tree_sha256(manifest["old_selector"]["target"]) != manifest["old_runtime_tree_sha256"]:
            refuse("old runtime has changed; recovery cannot restore a verified prior selection")
        # Compare the entire transition set before performing ANY restoration.
        paths = [(RUNTIME_LINK, manifest["old_selector"],
                  {"kind": "symlink", "target": manifest["runtime_path"], "uid": 0, "gid": 0, "mode": 0o777})]
        paths += [(os.path.join(UNIT_DIR, unit), manifest["units"][unit]["old"],
                   manifest["units"][unit]["new"]) for unit in UNITS]
        for path, old, new in paths:
            current = _fingerprint(path, absent=True)
            if current not in (old, new):
                refuse("recovery preflight found third-party/unknown state; no paths changed: " + path)
        state["status"] = "recovering"
        _journal_state(directory, state)
        _restore_one(directory, state, state, "selector_state", RUNTIME_LINK,
                     manifest["old_selector"], paths[0][2], None)
        for unit in UNITS:
            info = state["units"][unit]
            _restore_one(directory, state, info, "state", os.path.join(UNIT_DIR, unit),
                         info["old"], info["new"], info["snapshot"])
        state["status"] = "recovered"
        _journal_state(directory, state)
    print("bootstrap_selection=recovered_to_old")
    print("new_artifacts=retained")
    print("services_started_or_reloaded=false")


def _parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare", help="emit candidate manifest after stage-only")
    for name in ("source_head", "archive_sha256", "source_plan_sha256",
                 "target_inventory_sha256", "compiler_sha256", "spec_sha256",
                 "helper_head", "helper_source_sha256"):
        prepare.add_argument("--" + name.replace("_", "-"), required=True)
    run = sub.add_parser("apply", help="select reviewed staged artifacts without activating services")
    run.add_argument("--manifest", required=True)
    run.add_argument("--approved-sha256", required=True)
    rollback = sub.add_parser("recover", help="restore the exact prior selector/unit set")
    rollback.add_argument("--journal-id", required=True)
    rollback.add_argument("--approved-sha256", required=True)
    args = parser.parse_args()
    if hasattr(args, "approved_sha256") and not re.fullmatch(r"[0-9a-f]{64}", args.approved_sha256):
        parser.error("--approved-sha256 must be 64 lowercase hex characters")
    if args.command == "apply":
        match = re.fullmatch(r"/run/vst-deploy-([0-9a-f]{40})-([0-9a-f]{32})/\.vst-bootstrap-manifest\.json", args.manifest)
        if not match:
            parser.error("--manifest must be the fixed non-secret manifest inside a head-bound /run/vst-deploy staging directory")
        directory = "/run/vst-deploy-" + match.group(1) + "-" + match.group(2)
        info = os.lstat(directory)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
            parser.error("staged source bundle must be root-owned mode 0700")
    return args


def main() -> int:
    args = _parse()
    try:
        if args.command == "prepare":
            _require_root()
            _require_fixed_parents()
            _require_unconfigured_and_inactive()
            value = build_manifest(source_head=args.source_head, archive_sha256=args.archive_sha256,
                                   source_plan_sha256=args.source_plan_sha256,
                                   target_inventory_sha256=args.target_inventory_sha256,
                                   compiler_sha256=args.compiler_sha256,
                                   spec_sha256=args.spec_sha256, helper_head=args.helper_head,
                                   helper_source_sha256=args.helper_source_sha256)
            print(canonical_bytes(value).decode("ascii"))
            print("candidate_manifest_sha256=" + manifest_sha256(value), file=sys.stderr)
        elif args.command == "apply":
            _require_root()
            _require_fixed_parents()
            manifest = load_canonical_manifest(args.manifest)
            match = re.fullmatch(r"/run/vst-deploy-([0-9a-f]{40})-[0-9a-f]{32}/\.vst-bootstrap-manifest\.json", args.manifest)
            if match is None or match.group(1) != manifest["source_head"]:
                refuse("manifest does not match its fixed staged-source directory")
            apply(manifest, args.approved_sha256)
        else:
            recover(args.journal_id, args.approved_sha256)
    except (ContractError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
