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


def test_read_json_preserves_raw_crlf_bytes(tmp_path):
    path = tmp_path / "attempt.json"
    raw = b'{\r\n  "value": "line1\\r\\nline2"\r\n}\r\n'
    path.write_bytes(raw)

    value, actual = harness._read_json(path, maximum=1024)

    assert actual == raw
    assert value == {"value": "line1\r\nline2"}


def test_read_bounded_regular_preserves_raw_crlf_bytes(tmp_path):
    path = tmp_path / "pinned-source.txt"
    raw = b"first line\r\nsecond line\r\n"
    path.write_bytes(raw)

    assert harness._read_bounded_regular(path, maximum=1024) == raw


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


def _wsl_mount_audit_functions(*, unit="vst-s2-qual-0123456789abcdef.service"):
    """Load only the exact WSL mount decoder and its independent audit helpers."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    constants = {
        "SYSTEMD_MASK_DIRS", "SYSTEMD_MASK_FILES", "SYSTEMD_MASK_TARGETS",
        "SYSTEMD_INACCESSIBLE_PATHS", "MASK_BASES", "EXACT_MOUNTS",
    }
    functions = {
        "_unescape_mountinfo", "_decode_mountinfo", "_verify_execution_unit",
        "_verify_private_dev", "_verify_effective_masks",
    }
    nodes = [node for node in tree.body if (
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in constants
                for target in node.targets)
    ) or (isinstance(node, ast.FunctionDef) and node.name in functions)]
    found_constants = {
        target.id for node in nodes if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    found_functions = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    assert found_constants == constants
    assert found_functions == functions

    class Hold(Exception):
        pass

    runtime = {"terminal": None, "reason": None}

    def stop(reason):
        runtime["terminal"] = "HOLD"
        runtime["reason"] = reason
        raise Hold()

    namespace = {
        "hashlib": hashlib, "re": re, "os": __import__("os"),
        "stat": __import__("stat"), "pathlib": pathlib,
        "TRANSIENT_UNIT": unit, "MOUNT_AUDIT_ONLY": True,
        "R": runtime, "Hold": Hold, "stop": stop,
        "_systemd_unit_properties": lambda: {},
        "_expected_runtime_timeout": lambda: "1min",
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), "exec"),
         namespace)
    return namespace


def _mountinfo_line(mount_id, parent_id, device, root, target, mount_options,
                    filesystem, source, super_options):
    return (f"{mount_id} {parent_id} {device} {root} {target} {mount_options} "
            f"- {filesystem} {source} {super_options}")


def _complete_mountinfo(unit="vst-s2-qual-0123456789abcdef.service"):
    """Synthetic namespace with the exact required system mounts, masks and unit."""
    functions = _wsl_mount_audit_functions(unit=unit)
    rows = []
    ids = {}
    next_id = 1

    def parent_id(target):
        candidates = [(len(path), mount_id) for path, mount_ids in ids.items()
                      if path != target and (path == "/" or target.startswith(path.rstrip("/") + "/"))
                      for mount_id in mount_ids]
        assert candidates, target
        greatest = max(length for length, _ in candidates)
        same = [mount_id for length, mount_id in candidates if length == greatest]
        assert len(same) == 1, (target, same)
        return same[0]

    def add(target, *, root, device, filesystem, source, options, super_options,
            parent=None):
        nonlocal next_id
        mount_id = next_id
        next_id += 1
        if target == "/":
            parent = mount_id
        else:
            parent = parent_id(target) if parent is None else ids[parent][0]
        rows.append(_mountinfo_line(mount_id, parent, device, root, target,
                                    options, filesystem, source, super_options))
        ids.setdefault(target, []).append(mount_id)
        return mount_id

    add("/", root="/", device="8:1", filesystem="ext4", source="/dev/vda",
        options="ro,nosuid,relatime", super_options="rw,errors=remount-ro")
    add("/run", root="/", device="0:2", filesystem="tmpfs", source="none",
        options="rw,nosuid,nodev", super_options="rw,mode=755")
    add("/dev", root="/", device="0:3", filesystem="tmpfs", source="tmpfs",
        options="ro,nosuid,noexec",
        super_options="rw,size=4096k,nr_inodes=65536,mode=755")
    add("/sys", root="/", device="0:4", filesystem="sysfs", source="sysfs",
        options="rw,nosuid,nodev,noexec,noatime", super_options="rw")
    add("/proc", root="/", device="0:5", filesystem="proc", source="proc",
        options="rw,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/dev/pts", root="/", device="0:6", filesystem="devpts", source="devpts",
        options="rw,nosuid,noexec,noatime", super_options="rw,mode=620")
    add("/dev/mqueue", root="/", device="0:7", filesystem="mqueue", source="mqueue",
        options="rw,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/sys/fs/cgroup", root="/", device="0:8", filesystem="cgroup2", source="cgroup2",
        options="ro,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/proc/sys", root="/sys", device="0:5", filesystem="proc", source="proc",
        options="ro,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/proc/sysrq-trigger", root="/sysrq-trigger", device="0:5", filesystem="proc",
        source="proc", options="ro,nosuid,nodev,noexec,relatime", super_options="rw")

    # Each pre-mask mount is placed before its systemd inaccessible overlay.
    for target in sorted(functions["SYSTEMD_MASK_TARGETS"]):
        expected = functions["MASK_BASES"].get(target)
        if expected:
            filesystem, root, source, options, parent = expected
            add(target, root=root, device="0:2", filesystem=filesystem, source=source,
                options=",".join(sorted(options)), super_options="rw", parent=parent)
        inaccessible_root = (
            "/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
            else "/systemd/inaccessible/dir"
        )
        add(target, root=inaccessible_root, device="0:2", filesystem="tmpfs", source="none",
            options="ro,nosuid,nodev,noexec", super_options="rw,mode=755")

    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    add(cgroup_target, root="/system.slice/" + unit + "/memory.pressure", device="0:8",
        filesystem="cgroup2", source="cgroup2",
        options="rw,nosuid,nodev,noexec,relatime", super_options="rw")
    add(cgroup_target, root="/systemd/inaccessible/reg", device="0:2", filesystem="tmpfs",
        source="none", options="ro,nosuid,nodev,noexec", super_options="rw,mode=755")
    add("/run/systemd/incoming", root="/systemd/propagate/" + unit, device="0:2",
        filesystem="tmpfs", source="none", options="ro,nosuid,nodev",
        super_options="rw,mode=755")
    return "\n".join(rows), functions


def test_pm08_mount_decoder_accepts_exact_masks_incoming_and_current_cgroup_unit():
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)

    rows, windows, rejected = functions["_decode_mountinfo"](mountinfo, expected_unit=unit)

    assert windows == []
    assert rejected == [], [item["reason"] for item in rejected]
    by_path = {}
    for row in rows:
        by_path.setdefault(row["mountpoint"], []).append(row)
    root = by_path["/"][0]
    run = by_path["/run"][0]
    assert (root["filesystem"], root["source"], root["device"], root["mount_root"]) == (
        "ext4", "/dev/vda", "8:1", "/")
    assert set(root["mount_options"]) == {"ro", "nosuid", "relatime"}
    assert (run["filesystem"], run["source"], run["device"], run["mount_root"]) == (
        "tmpfs", "none", "0:2", "/")
    expected_targets = set(functions["SYSTEMD_MASK_TARGETS"])
    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    expected_targets.add(cgroup_target)
    masks = {
        target: [row for row in group if row["filesystem"] == "tmpfs"
                 and row["source"] == "none"
                 and row["mount_root"].startswith("/systemd/inaccessible/")]
        for target, group in by_path.items()
    }
    assert {target for target, group in masks.items() if group} == expected_targets
    for target in expected_targets:
        mask = masks[target]
        assert len(mask) == 1
        assert mask[0]["device"] == run["device"]
        assert set(mask[0]["mount_options"]) == {"ro", "nosuid", "nodev", "noexec"}
        assert set(mask[0]["super_options"]) == {"rw", "mode=755"}
        expected_root = ("/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
                         or target == cgroup_target else "/systemd/inaccessible/dir")
        assert mask[0]["mount_root"] == expected_root
    incoming = by_path["/run/systemd/incoming"]
    assert len(incoming) == 1
    assert incoming[0]["mount_root"] == "/systemd/propagate/" + unit
    assert incoming[0]["device"] == run["device"]
    assert set(incoming[0]["mount_options"]) == {"ro", "nosuid", "nodev"}
    assert set(incoming[0]["super_options"]) == {"rw", "mode=755"}
    assert not any("other-unit" in row["mount_root"] for row in rows)


@pytest.mark.parametrize("mutation", ["generic", "wrong-root", "wrong-source", "wrong-device",
                                      "wrong-mount-flags", "wrong-super-flags", "missing-mask",
                                      "nested-mask-child", "wrong-unit-incoming", "windows-drive"])
def test_pm08_mount_decoder_rejects_generic_or_malformed_mounts(mutation):
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    lines = mountinfo.splitlines()

    if mutation == "generic":
        lines.append(_mountinfo_line(900, 1, "8:9", "/", "/srv/host", "rw,relatime",
                                     "ext4", "/dev/sdb", "rw"))
    elif mutation in {"wrong-root", "wrong-source", "wrong-device", "wrong-mount-flags",
                      "wrong-super-flags"}:
        target = "/home"
        for index, line in enumerate(lines):
            before, separator, after = line.partition(" - ")
            left, right = before.split(), after.split()
            if left[4] == target and left[3] == "/systemd/inaccessible/dir":
                if mutation == "wrong-root":
                    left[3] = "/unapproved-root"
                elif mutation == "wrong-source":
                    right[1] = "unapproved-source"
                elif mutation == "wrong-device":
                    left[2] = "9:9"
                elif mutation == "wrong-mount-flags":
                    left[5] = "ro,nosuid,nodev"
                else:
                    right[2] = "rw,mode=700"
                lines[index] = " ".join(left) + separator + " ".join(right)
                break
        else:
            pytest.fail("fixture did not contain the expected /home mask")
    elif mutation == "missing-mask":
        lines = [line for line in lines if not (
            line.split(" - ")[0].split()[4] == "/home"
            and line.split(" - ")[0].split()[3] == "/systemd/inaccessible/dir")]
    elif mutation == "nested-mask-child":
        home = next(line for line in lines if line.split(" - ")[0].split()[4] == "/home"
                    and line.split(" - ")[0].split()[3] == "/systemd/inaccessible/dir")
        parent = home.split(" - ")[0].split()[0]
        lines.append(_mountinfo_line(901, int(parent), "8:1", "/", "/home/nested", "ro,nosuid",
                                     "ext4", "/dev/vda", "rw"))
    elif mutation == "wrong-unit-incoming":
        for index, line in enumerate(lines):
            before, separator, after = line.partition(" - ")
            left = before.split()
            if left[4] == "/run/systemd/incoming":
                left[3] = "/systemd/propagate/vst-s2-qual-ffffffffffffffff.service"
                lines[index] = " ".join(left) + separator + after
                break
        else:
            pytest.fail("fixture did not contain the incoming mount")
    else:
        lines.append(_mountinfo_line(
            902, next(row["mount_id"] for row in functions["_decode_mountinfo"](
                mountinfo, expected_unit=unit)[0] if row["mountpoint"] == "/mnt"),
            "0:55", "/", "/mnt/c", "rw,relatime", "9p", "C:\\",
            "aname=drvfs;path=C:\\;symlinkroot=/mnt/"))

    # Contract violations are reported in the third return value; malformed
    # duplicate IDs raise directly and are covered separately below.
    rows, windows, rejected = functions["_decode_mountinfo"]("\n".join(lines), expected_unit=unit)
    assert rejected, mutation
    if mutation == "windows-drive":
        assert windows


def test_pm08_mount_decoder_rejects_duplicate_mount_ids():
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    rows = mountinfo.splitlines()
    duplicate = rows[0].split()
    duplicate[4] = "/duplicate"

    _, _, rejected = functions["_decode_mountinfo"](
        mountinfo + "\n" + " ".join(duplicate), expected_unit=unit)
    assert any("duplicated" in item["reason"] for item in rejected)


def test_pm08_execution_unit_requires_exact_unit_identity_and_mount_namespace():
    unit = "vst-s2-qual-0123456789abcdef.service"
    functions = _wsl_mount_audit_functions(unit=unit)
    expected_inaccessible = set(functions["SYSTEMD_INACCESSIBLE_PATHS"])
    expected_inaccessible.add("/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure")
    properties = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "Result": "success",
        "MainPID": "4321", "ControlGroup": "/system.slice/" + unit,
        "PrivateDevices": "yes", "ProtectSystem": "strict",
        "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
        "ProtectKernelLogs": "yes", "ProtectControlGroups": "yes",
        "NoNewPrivileges": "yes", "RuntimeMaxUSec": "1min",
        "InaccessiblePaths": " ".join("-" + path for path in sorted(expected_inaccessible)),
    }

    class FakePath:
        def __init__(self, value):
            self.value = str(value)
            self.name = self.value.rsplit("/", 1)[-1]

        def read_bytes(self):
            assert self.value == "/proc/self/cmdline"
            return b"/usr/bin/python3.12\0-I\0-B\0-S\0-\0"

        def read_text(self, encoding=None):
            assert self.value == "/proc/self/cgroup"
            return "0::/system.slice/" + unit + "\n"

        def iterdir(self):
            assert self.value == "/proc/self/fd"
            return [FakePath("/proc/self/fd/" + name) for name in ("0", "1", "2")]

    fake_os = SimpleNamespace(
        geteuid=lambda: 0,
        getpid=lambda: 4321,
        stat=lambda path: SimpleNamespace(
            st_dev=1, st_ino=100 if path == "/proc/self/ns/mnt" else 200),
    )
    functions["os"] = fake_os
    functions["pathlib"] = SimpleNamespace(Path=FakePath)
    functions["_systemd_unit_properties"] = lambda: properties
    result = functions["_verify_execution_unit"]()
    assert result["unit"] == unit
    assert result["mount_namespace_distinct_from_pid1"] is True
    assert result["properties"] == properties
    assert result["open_fds"] == ["0", "1", "2"]

    properties["ControlGroup"] = "/system.slice/vst-s2-qual-ffffffffffffffff.service"
    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()
    assert functions["R"]["reason"] == (
        "transient-unit identity or hardening properties differ from the exact profile")


def test_pm08_effective_masks_verify_mount_id_type_and_root_ownership():
    unit = "vst-s2-qual-0123456789abcdef.service"
    functions = _wsl_mount_audit_functions(unit=unit)
    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    targets = sorted(set(functions["SYSTEMD_MASK_TARGETS"]) | {cgroup_target})
    rows = []
    for mount_id, target in enumerate(targets, 100):
        root = ("/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
                or target == cgroup_target else "/systemd/inaccessible/dir")
        rows.append({"mountpoint": target, "mount_id": mount_id,
                     "mount_root": root, "filesystem": "tmpfs", "source": "none"})

    fd_mount_ids = {}
    opened = []

    class FakePath:
        def __init__(self, value):
            self.value = str(value)

        def read_text(self, encoding=None):
            fd = int(self.value.rsplit("/", 1)[-1])
            return "pos:\t0\nmnt_id:\t" + str(fd_mount_ids[fd]) + "\n"

    wrong_mount_for = []

    def fake_open(path, flags):
        assert flags == (0x200000 | 0x80000)  # Linux O_PATH | O_CLOEXEC.
        target = str(path)
        row = next(item for item in rows if item["mountpoint"] == target)
        fd = row["mount_id"]
        fd_mount_ids[fd] = row["mount_id"] + (1 if target in wrong_mount_for else 0)
        opened.append(target)
        return fd

    def fake_fstat(fd):
        target = opened[fd - 100]
        regular = target in functions["SYSTEMD_MASK_FILES"] or target == cgroup_target
        return SimpleNamespace(
            st_mode=(functions["stat"].S_IFREG if regular else functions["stat"].S_IFDIR),
            st_uid=0, st_gid=0,
        )

    functions["os"] = SimpleNamespace(
        O_PATH=0x200000, O_CLOEXEC=0x80000,
        open=fake_open, fstat=fake_fstat, close=lambda _fd: None,
    )
    functions["pathlib"] = SimpleNamespace(Path=FakePath)
    verified, failures = functions["_verify_effective_masks"](rows)

    assert failures == []
    assert set(verified) == set(targets)
    assert len(opened) == len(targets)
    for item in verified.values():
        assert item["uid"] == item["gid"] == item["mode"] == 0
        assert item["type"] in {"regular", "directory"}

    wrong_mount_for.append(targets[0])
    verified, failures = functions["_verify_effective_masks"](rows)
    assert failures
    assert any("different mount" in failure for failure in failures)


def _private_dev_fixture(*, char_extra=False, masked_extra=False, wrong_null_mode=False,
                         pts_extra=False, mqueue_extra=False):
    functions = _wsl_mount_audit_functions()
    links = {
        "core": "/proc/kcore", "fd": "/proc/self/fd", "log": "/run/systemd/journal/dev-log",
        "stdin": "/proc/self/fd/0", "stdout": "/proc/self/fd/1", "stderr": "/proc/self/fd/2",
    }
    devices = {"tty": (5, 0), "urandom": (1, 9), "random": (1, 8),
               "full": (1, 7), "zero": (1, 5), "null": (1, 3), "ptmx": (5, 2)}
    directories = {"char": (0o755, 0, 0), "hugepages": (0, 0, 0),
                   "mqueue": (0o1777, 0, 0), "pts": (0o755, 0, 0), "shm": (0, 0, 0)}
    names = set(links) | set(devices) | set(directories)
    stats = {}
    link_targets = {}
    for name, target in links.items():
        stats["/dev/" + name] = SimpleNamespace(st_mode=functions["stat"].S_IFLNK | 0o777,
                                                st_uid=0, st_gid=0, st_rdev=0)
        link_targets["/dev/" + name] = target
    for name, (major, minor) in devices.items():
        mode = 0o600 if name == "null" and wrong_null_mode else 0o666
        stats["/dev/" + name] = SimpleNamespace(st_mode=functions["stat"].S_IFCHR | mode,
                                                st_uid=0, st_gid=0, st_rdev=(major, minor))
    for name, (mode, uid, gid) in directories.items():
        stats["/dev/" + name] = SimpleNamespace(st_mode=functions["stat"].S_IFDIR | mode,
                                                st_uid=uid, st_gid=gid, st_rdev=0)

    children = {name: [] for name in ("char", "hugepages", "mqueue", "pts", "shm")}
    aliases = {"1:3": "../null", "1:5": "../zero", "1:7": "../full",
               "1:8": "../random", "1:9": "../urandom", "5:0": "../tty", "5:2": "../ptmx"}
    for alias, target in aliases.items():
        children["char"].append(SimpleNamespace(
            name=alias, path="/dev/char/" + alias,
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFLNK | 0o777, st_uid=0, st_gid=0, st_rdev=0)))
        link_targets["/dev/char/" + alias] = target
    children["pts"].append(SimpleNamespace(
        name="ptmx", path="/dev/pts/ptmx",
        stat=lambda *, follow_symlinks=False: SimpleNamespace(
            st_mode=functions["stat"].S_IFCHR, st_uid=0, st_gid=0, st_rdev=(5, 2))))
    if pts_extra:
        children["pts"].append(SimpleNamespace(
            name="unexpected-device", path="/dev/pts/unexpected-device",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFCHR | 0o600, st_uid=0, st_gid=0, st_rdev=(1, 3))))
    if mqueue_extra:
        children["mqueue"].append(SimpleNamespace(
            name="unexpected-device", path="/dev/mqueue/unexpected-device",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFCHR | 0o600, st_uid=0, st_gid=0, st_rdev=(1, 3))))
    if char_extra:
        children["char"].append(SimpleNamespace(
            name="9:9", path="/dev/char/9:9",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFLNK | 0o777, st_uid=0, st_gid=0, st_rdev=0)))
        link_targets["/dev/char/9:9"] = "../null"
    if masked_extra:
        children["shm"].append(SimpleNamespace(
            name="unexpected", path="/dev/shm/unexpected",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFREG | 0o600, st_uid=0, st_gid=0, st_rdev=0)))

    class Dir:
        def __init__(self, rows):
            self.rows = rows
        def __enter__(self):
            return iter(self.rows)
        def __exit__(self, *_args):
            return False

    fake_os = SimpleNamespace(
        scandir=lambda path: Dir([SimpleNamespace(name=name) for name in sorted(names)])
        if path == "/dev" else Dir(children[path.rsplit("/", 1)[-1]]),
        lstat=lambda path: stats[path],
        readlink=lambda path: link_targets[path],
        major=lambda value: value[0], minor=lambda value: value[1],
    )
    functions["os"] = fake_os
    mount_rows = [{"mountpoint": "/dev/pts"}, {"mountpoint": "/dev/mqueue"},
                  {"mountpoint": "/dev/hugepages"}, {"mountpoint": "/dev/shm"}]
    return functions, mount_rows


def test_pm08_private_dev_requires_exact_metadata_aliases_and_empty_masked_dirs():
    functions, mount_rows = _private_dev_fixture()
    result, failures = functions["_verify_private_dev"](mount_rows)
    assert failures == []
    assert result["entries"]["null"] == {
        "uid": 0, "gid": 0, "mode": 0o666, "type": "character", "major": 1, "minor": 3,
    }
    assert set(result["nested_entries"]["char"]) == {
        "1:3", "1:5", "1:7", "1:8", "1:9", "5:0", "5:2",
    }
    assert result["nested_entries"]["hugepages"] == {}
    assert result["nested_entries"]["shm"] == {}


@pytest.mark.parametrize("kwargs", [
    {"char_extra": True}, {"masked_extra": True}, {"wrong_null_mode": True},
    {"pts_extra": True}, {"mqueue_extra": True},
])
def test_pm08_private_dev_rejects_alias_nested_content_and_wrong_device_mode(kwargs):
    functions, mount_rows = _private_dev_fixture(**kwargs)
    _, failures = functions["_verify_private_dev"](mount_rows)
    assert failures


@pytest.mark.parametrize(("runtime_max_sec", "expected_wait_timeout"), [(60, 90), (2400, 2430)])
def test_pm08_run_bounded_wsl_uses_exact_unit_and_systemd_isolation_properties(
        monkeypatch, runtime_max_sec, expected_wait_timeout):
    run_id = "run-s2-4-pm08-fixture"
    expected_unit = "vst-s2-qual-" + hashlib.sha256(run_id.encode("ascii")).hexdigest()[:16] + ".service"
    script = b"synthetic protocol source\r\n"
    captured = {}

    class CapturingInput:
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

    class MockProcess:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.stdin = CapturingInput()
            self.stdout = io.BytesIO(b"bounded stdout")
            self.stderr = io.BytesIO(b"")
            self.returncode = 0
            captured["stdin"] = self.stdin
        def wait(self, *, timeout):
            captured["wait_timeout"] = timeout
            return self.returncode

    monkeypatch.setattr(harness.subprocess, "Popen", MockProcess)
    result = harness._run_bounded_wsl(
        script, unit_name=expected_unit, runtime_max_sec=runtime_max_sec)

    expected_mask_paths = sorted(set(harness.SYSTEMD_MASK_TARGETS) | {
        "/sys/fs/cgroup/system.slice/" + expected_unit + "/memory.pressure",
    })
    expected_properties = [
        "--property=PrivateDevices=yes", "--property=ProtectSystem=strict",
        "--property=ProtectKernelTunables=yes", "--property=ProtectKernelModules=yes",
        "--property=ProtectKernelLogs=yes", "--property=ProtectControlGroups=yes",
        "--property=NoNewPrivileges=yes", "--property=RuntimeMaxSec=" + str(runtime_max_sec) + "s",
        "--property=InaccessiblePaths=" + " ".join("-" + path for path in expected_mask_paths),
    ]
    assert captured["argv"] == [
        "wsl.exe", "--distribution", harness.WSL_DISTRIBUTION, "--user", "root",
        "--exec", "/usr/bin/systemd-run", "--wait", "--collect", "--pipe", "--quiet",
        "--unit=" + expected_unit, *expected_properties, "--",
        "/usr/bin/python3.12", "-I", "-B", "-S", "-",
    ]
    assert result["unit_name"] == expected_unit
    assert result["runtime_max_sec"] == runtime_max_sec
    assert captured["wait_timeout"] == expected_wait_timeout
    assert result["systemd_properties"] == expected_properties
    assert captured["stdin"].data == script
    assert captured["stdin"].closed
    assert captured["kwargs"]["close_fds"] is True
    assert captured["kwargs"]["bufsize"] == 0
    assert captured["kwargs"]["stdin"] == harness.subprocess.PIPE
    assert captured["kwargs"]["stdout"] == harness.subprocess.PIPE
    assert captured["kwargs"]["stderr"] == harness.subprocess.PIPE
    assert harness.SYSTEMD_STARTUP_SHUTDOWN_GRACE_SEC == 30
    assert harness._transient_unit_name(run_id) == harness._transient_unit_name(run_id)
    assert harness._transient_unit_name(run_id + "-different") != expected_unit


@pytest.mark.parametrize("uppercase_hashes", [False, True])
def test_pm08_mount_audit_binds_sources_baseline_and_creates_no_auth_or_attempt_files(
        monkeypatch, tmp_path, capsys, uppercase_hashes):
    launcher_bytes = b"exact launcher source bytes\n"
    helper_bytes = b"exact helper source bytes\n"
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    baseline_sha = _sha(baseline_source.encode("utf-8"))
    protocol = json.dumps({
        "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
        "terminal": "PASS", "mount_audit": {
            "schema": "VST_S2_RUNTIME_MOUNT_AUDIT_V1", "terminal": "PASS",
            "reason": "synthetic read-only mount audit",
        },
    }, separators=(",", ":")).encode("ascii")
    launched = []

    def read_source(path, *, maximum):
        assert maximum == harness.MAX_WSL_SCRIPT_BYTES
        return launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes

    def fake_git(_root, *args, maximum):
        assert maximum in {1024, harness.MAX_WSL_SCRIPT_BYTES}
        if args[0] == "rev-parse":
            return (baseline + "\n").encode("ascii")
        assert args[0] == "show"
        return baseline_source.encode("utf-8")

    def fake_wsl(script, *, unit_name, runtime_max_sec):
        launched.append((script, unit_name, runtime_max_sec))
        return {
            "exit_code": 0, "timed_out": False, "writer_error": None,
            "runtime_max_sec": runtime_max_sec, "systemd_properties": [],
            "stdout": {"bytes": len(protocol), "sha256": _sha(protocol),
                       "prefix": protocol, "truncated": False},
            "stderr": {"bytes": 0, "sha256": _sha(b""), "prefix": b"", "truncated": False},
        }

    monkeypatch.setattr(harness, "_read_bounded_regular", read_source)
    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", fake_wsl)
    experiment_id = "s2-4-pm08-readonly-01"
    expected_unit = harness._transient_unit_name(experiment_id)
    launcher_hash = _sha(launcher_bytes)
    helper_hash = _sha(helper_bytes)
    if uppercase_hashes:
        launcher_hash = launcher_hash.upper()
        helper_hash = helper_hash.upper()

    exit_code = harness.run_read_only_mount_audit(
        root=tmp_path, experiment_id=experiment_id,
        expected_launcher_sha256=launcher_hash,
        expected_helper_sha256=helper_hash,
    )

    assert exit_code == 0
    assert len(launched) == 1
    script, unit_name, runtime_max_sec = launched[0]
    prefix = script[:script.index(helper_bytes)].decode("ascii")
    assert 'AUTH = "{}"\n' in prefix
    assert 'TRANSIENT_UNIT = ' + json.dumps(expected_unit) in prefix
    assert "MOUNT_AUDIT_ONLY = true" in prefix
    assert 'BASELINE_DECODER_SOURCE = ' + json.dumps(baseline_source) in prefix
    assert 'BASELINE_DECODER_SHA256 = ' + json.dumps(baseline_sha) in prefix
    assert 'BASELINE_DECODER_REVISION = ' + json.dumps(baseline) in prefix
    assert script.endswith(helper_bytes)
    assert "attempt" not in prefix
    assert "docs/sdlc/evidence" not in prefix
    assert unit_name == expected_unit
    assert runtime_max_sec == 60
    report = json.loads(capsys.readouterr().out)
    assert report["source_identity"] == {
        "launcher_sha256": _sha(launcher_bytes),
        "helper_sha256": _sha(helper_bytes),
        "baseline_revision": baseline,
        "baseline_decoder_sha256": baseline_sha,
    }
    assert report["terminal"] == "PASS"
    assert len(launched) == 1  # Uppercase valid digests must reach the mock executor.
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize("failure", ["launcher-hash", "helper-hash", "baseline-revision"])
def test_pm08_mount_audit_fails_closed_before_wsl_on_source_or_baseline_mismatch(
        monkeypatch, tmp_path, failure):
    launcher_bytes, helper_bytes = b"launcher\n", b"helper\n"
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    calls = []

    monkeypatch.setattr(harness, "_read_bounded_regular", lambda path, **_kwargs:
                        launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes)

    def fake_git(_root, *args, maximum):
        if args[0] == "rev-parse":
            revision = "f" * 40 if failure == "baseline-revision" else baseline
            return (revision + "\n").encode("ascii")
        return baseline_source.encode("utf-8")

    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl",
                        lambda *_args, **_kwargs: calls.append(True))
    expected_launcher = "0" * 64 if failure == "launcher-hash" else _sha(launcher_bytes)
    expected_helper = "0" * 64 if failure == "helper-hash" else _sha(helper_bytes)

    with pytest.raises(harness.QualificationError):
        harness.run_read_only_mount_audit(
            root=tmp_path, experiment_id="s2-4-pm08-readonly-02",
            expected_launcher_sha256=expected_launcher,
            expected_helper_sha256=expected_helper,
        )
    assert calls == []
    assert list(tmp_path.rglob("*")) == []


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
