"""Bounded WSL-side protocol for one S2-4 runtime qualification attempt.

This file is streamed to a single isolated Python process by
run_s2_runtime_qualification.py. It uses only standard-library modules until
the installed runtime source has been verified and all pre-start checks pass.
"""
from __future__ import annotations

import datetime
import grp
import hashlib
import json
import os
import pathlib
import re
import socket
import sqlite3
import stat
import struct
import subprocess
import sys
import time
import urllib.parse

AUTH = json.loads(AUTH)
MAX_COMMAND_CAPTURE = 256 * 1024
MAX_REPORT_BYTES = 1_800_000
OWNER_SOCKET = "/run/vst-supervisor/dispatch-owner.sock"
EXPECTED_UNITS = (
    "vst-sandbox-probe.service", "vst-assignment-bootstrap.service",
    "vst-dispatch-issuer.service", "vst-supervisor.service", "vst-signer.service",
    "vst-runner.service", "vst-dispatcher.service", "vst-dispatch-owner.socket",
    "vst-dispatch-owner.service",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class Hold(Exception):
    pass


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def record(label: str, argv: list[str], *, timeout: float = 30.0,
           maximum: int = MAX_COMMAND_CAPTURE) -> dict:
    """Run one command once and retain only a bounded prefix plus full hashes."""
    started = utc()
    try:
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True,
        )
        out = bytearray()
        err = bytearray()
        out_hash = hashlib.sha256()
        err_hash = hashlib.sha256()
        totals = {"stdout": 0, "stderr": 0}

        def drain(stream, kept, digest, name):
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                totals[name] += len(chunk)
                digest.update(chunk)
                if len(kept) < maximum:
                    kept.extend(chunk[:maximum - len(kept)])

        import threading
        out_thread = threading.Thread(target=drain, args=(process.stdout, out, out_hash, "stdout"), daemon=True)
        err_thread = threading.Thread(target=drain, args=(process.stderr, err, err_hash, "stderr"), daemon=True)
        out_thread.start()
        err_thread.start()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait()
        out_thread.join(timeout=10)
        err_thread.join(timeout=10)
        if out_thread.is_alive() or err_thread.is_alive():
            raise RuntimeError("bounded output drain did not terminate")
        return {
            "id": label, "argv": argv, "started_utc": started, "finished_utc": utc(),
            "exit_code": process.returncode, "timed_out": timed_out,
            "stdout_bytes": totals["stdout"], "stdout_sha256": out_hash.hexdigest(),
            "stdout_truncated": totals["stdout"] > len(out),
            "stderr_bytes": totals["stderr"], "stderr_sha256": err_hash.hexdigest(),
            "stderr_truncated": totals["stderr"] > len(err),
            "_stdout": bytes(out), "_stderr": bytes(err),
        }
    except Exception as exc:
        return {
            "id": label, "argv": argv, "started_utc": started, "finished_utc": utc(),
            "exit_code": None, "error_type": type(exc).__name__,
            "stdout_bytes": 0, "stderr_bytes": 0, "_stdout": b"", "_stderr": b"",
        }


def _prefix(result: dict, stream: str = "stdout") -> bytes:
    return result.pop("_" + stream, b"")


def _text(result: dict) -> str:
    return _prefix(result).decode("utf-8", "replace")


def _require_command(result: dict, name: str) -> bytes:
    if (result.get("exit_code") != 0 or result.get("timed_out")
            or result.get("stdout_truncated") or result.get("stderr_truncated")):
        _prefix(result)
        _prefix(result, "stderr")
        R["commands"].append(result)
        stop(name + " failed, timed out, or exceeded its output bound")
    output = _prefix(result)
    _prefix(result, "stderr")
    R["commands"].append(result)
    return output


def stop(reason: str) -> None:
    R["terminal"] = "HOLD"
    R["reason"] = reason[:512]
    raise Hold()


def _decode_mountinfo(raw: str) -> tuple[list[dict], list[str], list[dict]]:
    rows = []
    windows_mounts = []
    unapproved_mounts = []
    decoded = []
    for number, line in enumerate(raw.splitlines(), 1):
        before, separator, after = line.partition(" - ")
        left, right = before.split(), after.split()
        if separator != " - " or len(left) < 6 or len(right) < 3 or len(line) > 16384:
            raise ValueError("mountinfo row is malformed")
        def unescape(value):
            return value.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n").replace("\\134", "\\")
        mountpoint = unescape(left[4])
        mount_root = unescape(left[3])
        device = left[2]
        fstype = right[0].lower()
        source = unescape(right[1])
        mount_options = left[5].split(",")
        super_options = right[2].split(",") if len(right) > 2 else []
        all_options = mount_options + super_options
        row = {"mountpoint": mountpoint, "filesystem": fstype,
               "source": source, "device": device, "mount_root": mount_root,
               "mount_options": mount_options,
               "line_sha256": hashlib.sha256(line.encode()).hexdigest()}
        rows.append(row)
        wsl_drvfs_9p = fstype == "9p" and re.search(
            r"(?:^|[;,])aname=drvfs(?:$|[;,])", ",".join(all_options), re.IGNORECASE,
        ) is not None
        if (fstype == "drvfs" or wsl_drvfs_9p
                or re.fullmatch(r"[A-Za-z]:\\?", source)):
            windows_mounts.append(row)
        decoded.append((number, row, device, mount_root, source, all_options))

    roots = [item for item in decoded if item[1]["mountpoint"] == "/"]
    if len(roots) != 1:
        raise ValueError("mount namespace must expose exactly one root filesystem")
    _root_number, root_row, root_device, _root_mount, _root_source, _root_options = roots[0]
    root_filesystem = root_row["filesystem"]
    systemd_masked_wsl_paths = {
        "/init", "/home", "/mnt", "/root", "/run/WSL", "/usr/lib/wsl",
        "/tmp/.X11-unix",
    }
    for number, row, device, mount_root, source, mount_options in decoded:
        target = row["mountpoint"]
        filesystem = row["filesystem"]
        wsl_path = (target == "/mnt" or target.startswith("/mnt/")
                    or target in systemd_masked_wsl_paths)
        valid_source = False
        if filesystem in {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "ramfs",
                          "cgroup2", "mqueue"}:
            permitted_roots = {"/"}
            if target == "/proc/sys":
                permitted_roots.add("/sys")
            if target == "/proc/sysrq-trigger":
                permitted_roots.add("/sysrq-trigger")
            valid_source = mount_root in permitted_roots and source == filesystem
        elif target in systemd_masked_wsl_paths:
            valid_source = (device == root_device and filesystem == root_filesystem
                            and mount_root == "/run/systemd/inaccessible/dir")
        elif target in {"/tmp", "/var/tmp"}:
            private_parent = "/tmp/systemd-private-" if target == "/tmp" else "/var/tmp/systemd-private-"
            valid_source = (device == root_device and filesystem == root_filesystem
                            and mount_root.startswith(private_parent)
                            and "vst-sandbox-probe.service" in mount_root
                            and mount_root.endswith("/tmp"))
        elif target == "/usr/lib/modules" or target.startswith("/usr/lib/modules/"):
            valid_source = (filesystem == "overlay" and source == "none" and mount_root == "/"
                            and "ro" in mount_options)
        else:
            valid_source = (device == root_device and filesystem == root_filesystem
                            and mount_root == target)
            if target in {"/usr", "/boot", "/etc", "/var", "/opt"}:
                valid_source = valid_source and "ro" in mount_options
        if target == "/":
            valid_source = mount_root == "/" and device == root_device
        if not valid_source or (wsl_path and target not in systemd_masked_wsl_paths):
            unapproved_mounts.append({"row": number, **row})
    return rows, windows_mounts, unapproved_mounts


def _secure_bytes(path: str, maximum: int = 8 * 1024 * 1024) -> bytes:
    before = os.lstat(path)
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or before.st_mode & 0o022 or before.st_size < 1 or before.st_size > maximum):
        raise ValueError("trusted file type, mode, link count, or size is invalid: " + path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("trusted file changed while opening: " + path)
        chunks = bytearray()
        while len(chunks) <= maximum:
            part = os.read(fd, min(65536, maximum + 1 - len(chunks)))
            if not part:
                break
            chunks.extend(part)
        after = os.fstat(fd)
        if (len(chunks) != opened.st_size or len(chunks) > maximum
                or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)):
            raise ValueError("trusted file changed while reading: " + path)
        return bytes(chunks)
    finally:
        os.close(fd)


def _json_file(path: str, maximum: int = 2 * 1024 * 1024) -> dict:
    value = json.loads(_secure_bytes(path, maximum), object_pairs_hook=_pairs,
                       parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object: " + path)
    return value


def _tree_digest(root: str, expected: dict[str, str]) -> None:
    root_info = os.lstat(root)
    if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != 0 or root_info.st_mode & 0o022:
        raise ValueError("versioned runtime root is not root-controlled")
    for rel, digest in expected.items():
        path = os.path.join(root, *rel.split("/"))
        data = _secure_bytes(path, 16 * 1024 * 1024)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("runtime source hash mismatch: " + rel)


def _config_identity(identity: dict) -> tuple[dict, dict, dict]:
    for path, expected in identity["config_sha256"].items():
        data = _secure_bytes(path)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("configuration hash mismatch: " + path)
    config = _json_file("/etc/vst-runner/supervisor-service.json")
    bootstrap = _json_file("/etc/vst-runner/bootstrap-request.json")
    task_manifest = _json_file("/etc/vst-runner/task-manifest.json")
    profile = _json_file("/etc/vst-runner/network-profile.json")
    policy = _json_file("/etc/vst-runner/assignment-delegation-policy.json")
    selector = identity["selector_test_id"]
    if (config.get("run_id") != identity["run_id"]
            or config.get("probe_nonce") != identity["nonce"]
            or config.get("store_path") != "/var/lib/vst-runner/private/store.sqlite3"
            or bootstrap.get("request_id") != identity["bootstrap_request_id"]
            or bootstrap.get("run_id") != identity["run_id"]
            or task_manifest.get("task_id") != "S2-4-runtime-owner-runner-qualification"
            or task_manifest.get("story_id") != "S2-4"
            or task_manifest.get("retry_cap") != 0
            or task_manifest.get("required_tests") != [
                {"slot": "runtime-tests", "test_id": selector,
                 "acceptance": task_manifest.get("acceptance")}
            ]
            or bootstrap.get("task_manifest") != task_manifest
            or task_manifest.get("task_id") != bootstrap.get("task_id")
            or task_manifest.get("story_id") != bootstrap.get("story_id")
            or profile.get("external_allowlist") != []
            or profile.get("environment_id") != "Ubuntu-24.04:S2:" + identity["run_id"]
            or policy.get("source_head") != identity["runtime_source_head"]
            or policy.get("allowed_assignments", [{}])[0].get("task_manifest_sha256")
               != identity["task_manifest_sha256"]):
        raise ValueError("runtime configuration does not match the one-shot authorization tuple")
    manifest_hash = hashlib.sha256(_canonical(task_manifest)).hexdigest()
    config_bundle_hash = hashlib.sha256(_canonical(identity["config_sha256"])).hexdigest()
    if (manifest_hash != identity["task_manifest_sha256"]
            or config_bundle_hash != identity["config_bundle_sha256"]):
        raise ValueError("task manifest or complete configuration hash map differs")
    return config, bootstrap, task_manifest


def _runtime_identity(identity: dict) -> None:
    selector = identity["runtime_selector"]
    if selector != "/opt/vst-runtime-" + identity["runtime_source_head"]:
        raise ValueError("runtime selector is not the full-hash versioned identity")
    marker = _json_file(selector + "/.vst-runtime-manifest.json", 65536)
    if (marker.get("schema") != 3 or marker.get("head") != identity["runtime_source_head"]
            or marker.get("archive_sha256") != identity["bundle_sha256"]):
        raise ValueError("installed runtime marker differs from the authorized runtime bundle")
    link = os.lstat("/opt/vst-runtime")
    if not stat.S_ISLNK(link.st_mode) or os.readlink("/opt/vst-runtime") != selector:
        raise ValueError("active runtime symlink does not select the distinct authorized runtime")
    _tree_digest(selector, AUTH["source_pins"]["runtime"])


def _systemd_show(unit: str) -> dict:
    raw = _require_command(record("unit:" + unit, [
        "/usr/bin/systemctl", "show", unit, "--property=LoadState", "--property=ActiveState",
        "--property=SubState", "--property=Result", "--property=MainPID", "--value",
    ]), "systemd inventory")
    lines = raw.decode("utf-8", "replace").splitlines()
    if len(lines) != 5:
        stop("systemd returned a malformed unit inventory")
    return dict(zip(("LoadState", "ActiveState", "SubState", "Result", "MainPID"), lines))


def _prestart_inventory(identity: dict) -> dict:
    if os.geteuid() != 0:
        stop("launcher is not root in the selected WSL distribution")
    try:
        mountinfo = pathlib.Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        mount_rows, windows_mounts, unapproved_mounts = _decode_mountinfo(mountinfo)
    except Exception as exc:
        stop("complete mount inventory is unavailable: " + type(exc).__name__)
    R["prestart"]["mount_inventory"] = {
        "rows": mount_rows, "row_count": len(mount_rows),
        "unapproved_host_mounts": unapproved_mounts,
        "sha256": hashlib.sha256(mountinfo.encode()).hexdigest(),
    }
    if windows_mounts:
        stop("Windows drive mount detected in complete mount inventory")
    if unapproved_mounts:
        stop("unapproved host mount detected in complete mount inventory")
    if len(mountinfo.encode()) > 8 * 1024 * 1024 or len(mount_rows) < 4:
        stop("mount inventory is outside expected bounds")

    if pathlib.Path("/proc/1/comm").read_text(encoding="ascii").strip() != "systemd":
        stop("WSL PID 1 is not systemd")
    # No runtime, service, key, or configuration path is read until every
    # mountinfo row has been inspected for Windows-backed mounts.
    config = _json_file("/etc/vst-runner/supervisor-service.json")
    runtime = identity["runtime_selector"]
    _runtime_identity(identity)
    _config_identity(identity)
    # Verify the deployment plan's complete no-symlink source inventory.
    source_manifest = _json_file(runtime + "/.vst-source-manifest.json", 8 * 1024 * 1024)
    runtime_manifest = _json_file(runtime + "/.vst-runtime-manifest.json", 65536)
    verify = ["/usr/bin/python3.12", "-I", "-B", "-S",
              runtime + "/tools/qa/verify_wsl_source_bundle.py",
              "--root", runtime, "--expected-head", identity["runtime_source_head"],
              "--archive-sha256", identity["bundle_sha256"],
              "--plan-sha256", runtime_manifest["plan_sha256"],
              "--inventory-sha256", runtime_manifest["inventory_sha256"]]
    _require_command(record("full_runtime_source_verification", verify, timeout=120),
                     "complete installed source verification")
    R["prestart"]["runtime_source_manifest"] = {
        "schema": source_manifest.get("schema"),
        "archive_sha256": runtime_manifest.get("archive_sha256"),
        "head": runtime_manifest.get("head"),
        "inventory_sha256": runtime_manifest.get("inventory_sha256"),
        "plan_sha256": runtime_manifest.get("plan_sha256"),
    }

    unit_rows = {}
    for unit in EXPECTED_UNITS:
        unit_rows[unit] = _systemd_show(unit)
        row = unit_rows[unit]
        if (row["LoadState"] != "loaded" or row["ActiveState"] != "inactive"
                or row["SubState"] != "dead" or row["MainPID"] not in {"", "0"}):
            stop("all runtime and preflight units must be loaded and inactive before activation")
    jobs = _require_command(record("systemd_jobs", [
        "/usr/bin/systemctl", "list-jobs", "--no-legend", "--no-pager",
    ]), "systemd job inventory")
    if jobs.strip():
        stop("systemd has a pending job before activation")
    manager = _require_command(record("systemd_manager_state", [
        "/usr/bin/systemctl", "is-system-running",
    ]), "systemd manager state")
    if manager.strip() != b"running":
        stop("systemd manager is not in the exact running state")
    R["prestart"]["units"] = unit_rows
    R["prestart"]["systemd_jobs"] = 0

    forbidden_paths = [
        config["store_path"],
        "/run/vst-supervisor/supervisor.sock", OWNER_SOCKET,
        "/run/vst-runner/runner.sock", "/etc/vst-runner/issuance-request.json",
    ]
    presence = {path: os.path.lexists(path) for path in forbidden_paths}
    R["prestart"]["path_presence"] = presence
    if any(presence.values()):
        stop("Store, socket, or derived issuer-request state already exists")
    R["prestart"]["verdict"] = "PASS_BEFORE_ANY_RUNTIME_SERVICE_START"
    return config


def _start_service(unit: str, timeout: float = 45.0) -> dict:
    result = record("start:" + unit, ["/usr/bin/systemctl", "start", unit], timeout=timeout)
    _require_command(result, "one-time service start for " + unit)
    state = _systemd_show(unit)
    if state["LoadState"] != "loaded" or state["ActiveState"] != "active":
        stop("service did not become active after its one allowed start: " + unit)
    R["stages"].setdefault("service_starts", []).append({"unit": unit, "state": state})
    return state


def _journal_objects(unit: str, since: str) -> list[dict]:
    result = record("journal:" + unit, [
        "/usr/bin/journalctl", "-u", unit, "--no-pager", "-o", "cat", "--since", since,
    ], timeout=30)
    raw = _require_command(result, "bounded journal capture")
    values = []
    for line in raw.splitlines():
        try:
            item = json.loads(line, object_pairs_hook=_pairs)
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(item, dict):
            values.append(item)
    return values


def _one_match(rows: list[dict], predicate, label: str) -> dict:
    selected = [row for row in rows if predicate(row)]
    if len(selected) != 1:
        stop(label + " was absent or ambiguous; no replacement operation will be attempted")
    return selected[0]


def _run_bootstrap(identity: dict, manifest: dict) -> dict:
    since = "@" + str(time.time() - 2)
    result = record("start:assignment-bootstrap", [
        "/usr/bin/systemctl", "start", "vst-assignment-bootstrap.service",
    ], timeout=45)
    _require_command(result, "single authenticated assignment bootstrap")
    objects = _journal_objects("vst-assignment-bootstrap.service", since)
    handoff = _one_match(objects, lambda row:
        row.get("run_id") == identity["run_id"]
        and row.get("bootstrap_request", {}).get("request_id") == identity["bootstrap_request_id"],
        "authenticated bootstrap handoff")
    if (handoff.get("task_id") != manifest.get("task_id")
            or handoff.get("story_id") != manifest.get("story_id")
            or handoff.get("slot") != "runtime-tests" or handoff.get("attempt") != 1
            or handoff.get("run_id") != identity["run_id"]
            or handoff.get("bootstrap_request", {}).get("task_manifest") != manifest
            or not isinstance(handoff.get("assignment_operation_id"), str)
            or not HEX64.fullmatch(handoff["assignment_operation_id"])):
        R["stages"]["bootstrap_handoff"] = {"sha256": hashlib.sha256(_canonical(handoff)).hexdigest()}
        stop("bootstrap handoff differs from the exact authorized task and identity")
    R["stages"]["bootstrap"] = {
        "handoff": handoff,
        "handoff_sha256": hashlib.sha256(_canonical(handoff)).hexdigest(),
        "verdict": "PASS",
    }
    return handoff


def _create_issuer_request(handoff: dict) -> dict:
    path = "/etc/vst-runner/issuance-request.json"
    if os.path.lexists(path):
        stop("derived issuer request already exists; refusing overwrite")
    issuer = __import__("pwd").getpwnam("vst-dispatch-issuer")
    issuer_group = grp.getgrnam("vst-dispatch-issuer")
    body = _canonical({"assignment_operation_id": handoff["assignment_operation_id"]})
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.fchown(fd, 0, issuer_group.gr_gid)
        os.fchmod(fd, 0o640)
        written = os.write(fd, body)
        if written != len(body):
            stop("short write while creating one-shot issuer input")
        os.fsync(fd)
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if info.st_uid != 0 or info.st_gid != issuer_group.gr_gid or stat.S_IMODE(info.st_mode) != 0o640:
        stop("derived issuer input ownership does not match the provisioned layout")
    result = {"path": path, "uid": info.st_uid, "gid": info.st_gid,
              "mode": format(stat.S_IMODE(info.st_mode), "04o"),
              "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
              "issuer_uid": issuer.pw_uid}
    R["stages"]["issuer_request"] = result
    return result


def _run_issuer(handoff: dict, identity: dict) -> dict:
    _create_issuer_request(handoff)
    since = "@" + str(time.time() - 2)
    result = record("start:dispatch-issuer", [
        "/usr/bin/systemctl", "start", "vst-dispatch-issuer.service",
    ], timeout=45)
    _require_command(result, "single root-bound dispatch issuance")
    objects = _journal_objects("vst-dispatch-issuer.service", since)
    instruction = _one_match(objects, lambda row:
        row.get("task_id") == handoff["task_id"]
        and row.get("run_id") == identity["run_id"]
        and row.get("slot") == handoff["slot"]
        and row.get("attempt") == handoff["attempt"], "signed dispatch instruction")
    if (not isinstance(instruction.get("signature"), str) or not instruction["signature"]
            or instruction.get("epoch") != handoff.get("epoch")
            or instruction.get("run_id") != identity["run_id"]
            or instruction.get("slot") != "runtime-tests"
            or instruction.get("attempt") != 1
            or not isinstance(instruction.get("request_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", instruction["request_id"])):
        stop("issuer result is not a signed instruction for this exact handoff")
    R["stages"]["dispatch_instruction"] = {
        "instruction": instruction,
        "sha256": hashlib.sha256(_canonical(instruction)).hexdigest(),
    }
    return instruction


def _owner_submit(instruction: dict, identity: dict) -> dict:
    runtime = identity["runtime_selector"]
    sys.path.insert(0, runtime)
    from tools.vst.assignment_basis import validate_policy
    from tools.vst.dispatch_issuance import issuance_identity
    from tools.vst.dispatch_instruction import validate_dispatch_instruction
    from tools.vst.dispatch_owner_transport import DispatchOwnerSocketClient

    policy = validate_policy(_json_file("/etc/vst-runner/assignment-delegation-policy.json"))[0]
    expected = issuance_identity(
        R["stages"]["bootstrap"]["handoff"], policy={
            "policy": policy,
            "policy_sha256": hashlib.sha256(_canonical(policy)).hexdigest(),
        }, now=datetime.datetime.now(datetime.timezone.utc),
    )
    envelope = validate_dispatch_instruction(instruction)
    if (envelope["request_id"] != expected["request_id"]
            or envelope["task_id"] != R["stages"]["bootstrap"]["handoff"]["task_id"]
            or envelope["run_id"] != identity["run_id"]
            or envelope["slot"] != "runtime-tests" or envelope["attempt"] != 1):
        stop("signed instruction is not the exact issuance for the authenticated handoff")
    owner_config = _json_file("/etc/vst-runner/dispatch-owner-service.json")
    socket_stat = os.stat(os.path.dirname(OWNER_SOCKET), follow_symlinks=False)
    client = DispatchOwnerSocketClient(
        expected_principal=owner_config["principal"], expected_socket_gid=socket_stat.st_gid,
    )
    # This is the sole Owner submission. The transport returns a durable,
    # correlated Supervisor acceptance or raises an unknown outcome; no retry.
    accepted = client.submit_signed_instruction(envelope)
    if (accepted.get("instruction") != envelope
            or accepted.get("request_id") != envelope["request_id"]
            or accepted.get("run_id") != identity["run_id"]):
        stop("dispatch owner response does not prove acceptance of the exact instruction")
    R["stages"]["owner_submission"] = {
        "request_id": envelope["request_id"],
        "instruction_sha256": hashlib.sha256(_canonical(envelope)).hexdigest(),
        "event_seq": accepted.get("event_seq"),
        "payload_digest": accepted.get("payload_digest"),
        "service_generation": accepted.get("service_generation"),
        "verdict": "DURABLY_ACCEPTED",
    }
    return accepted


def _read_task_rows(store_path: str, task_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    uri = "file:" + urllib.parse.quote(store_path, safe="/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True, timeout=1)
    db.row_factory = sqlite3.Row
    try:
        claims = [dict(row) for row in db.execute(
            "SELECT grant_id,invocation_id,request_id,task_id,slot,runner_id,attempt,epoch,run_id,"
            "service_generation,manifest_sha256,payload_sha256,grant_body,claimed_at "
            "FROM runner_execution_claims WHERE task_id=?", (task_id,))]
        events = []
        receipts = []
        if claims:
            events = [dict(row) for row in db.execute(
                "SELECT grant_id,state,payload,created_at FROM runner_execution_events "
                "WHERE grant_id IN (SELECT grant_id FROM runner_execution_claims WHERE task_id=?) "
                "ORDER BY seq", (task_id,))]
            receipts = [dict(row) for row in db.execute(
                "SELECT slot,attempt,epoch,receipt_sha256,prev_receipt_sha256,body "
                "FROM receipts WHERE task_id=? ORDER BY seq", (task_id,))]
        return claims, events, receipts
    finally:
        db.close()


def _wait_for_test_run(config: dict, manifest: dict, instruction: dict,
                       identity: dict) -> dict:
    runtime = identity["runtime_selector"]
    sys.path.insert(0, runtime)
    from tools.vst.contracts import canonical_bytes, receipt_sha256, validate_receipt
    from tools.vst.execution_grant import validate_execution_grant
    from tools.vst.supervisor_service import SupervisorClient

    deadline = time.monotonic() + min(600.0, float(manifest.get("timeout_sec", 120)) + 60.0)
    task_id = manifest["task_id"]
    claim = None
    events = []
    receipts = []
    snapshots = []
    while time.monotonic() < deadline:
        claims, events, receipts = _read_task_rows(config["store_path"], task_id)
        snapshots.append({"utc": utc(), "claims": len(claims),
                          "event_states": [row["state"] for row in events],
                          "receipts": len(receipts)})
        if len(claims) > 1 or len(receipts) > 1:
            stop("multiple durable claims or TestRun receipts exist; no retry")
        if claims:
            claim = claims[0]
            try:
                grant = validate_execution_grant(json.loads(claim["grant_body"], object_pairs_hook=_pairs))
                grant_bytes = canonical_bytes(grant)
                grant_digest = hashlib.sha256(grant_bytes).hexdigest()
                event_payloads = [json.loads(row["payload"], object_pairs_hook=_pairs) for row in events]
            except Exception as exc:
                stop("durable Runner claim or execution grant is malformed: " + type(exc).__name__)
            fields = ("grant_id", "invocation_id", "request_id", "task_id", "slot", "runner_id",
                      "attempt", "epoch", "run_id", "service_generation", "manifest_sha256")
            column_binding = all(claim.get(field) == grant.get(field) for field in fields)
            handoff = R["stages"]["bootstrap"]["handoff"]
            tuple_binding = (
                grant.get("request_id") == instruction.get("request_id")
                and grant.get("task_id") == task_id
                and grant.get("slot") == "runtime-tests"
                and grant.get("runner_id") == handoff.get("runner_id")
                and grant.get("attempt") == 1
                and grant.get("epoch") == handoff.get("epoch")
                and grant.get("run_id") == identity["run_id"]
                and grant.get("manifest_sha256") == identity["task_manifest_sha256"]
                and grant.get("service_generation") == claim.get("service_generation")
                and claim.get("payload_sha256") == grant_digest
                and claim.get("claimed_at") is not None
            )
            states = [row["state"] for row in events]
            pending = {
                "event": "RUNNER_EXECUTION_PENDING", "state": "PENDING",
                "grant_id": grant.get("grant_id"), "invocation_id": grant.get("invocation_id"),
                "request_id": grant.get("request_id"), "task_id": grant.get("task_id"),
                "slot": grant.get("slot"), "runner_id": grant.get("runner_id"),
                "attempt": grant.get("attempt"), "epoch": grant.get("epoch"),
                "service_generation": grant.get("service_generation"),
                "run_id": grant.get("run_id"), "payload_sha256": grant_digest,
            }
            reserved = {
                "event": "RUNNER_EXECUTION_RESERVED", "state": "EXECUTION_RESERVED",
                "grant_id": grant.get("grant_id"), "payload_sha256": grant_digest,
                "invocation_id": grant.get("invocation_id"),
                "request_id": grant.get("request_id"),
                "service_generation": grant.get("service_generation"),
            }
            event_binding = (
                states in (["PENDING"], ["PENDING", "EXECUTION_RESERVED"])
                and event_payloads[0] == pending
                and (len(event_payloads) == 1 or event_payloads[1] == reserved)
            )
            client = SupervisorClient(config.get("socket_path", "/run/vst-supervisor/supervisor.sock"))
            live_generation = client.generation()
            claim_status = client.claim_status(grant)
            status_binding = (
                live_generation == grant.get("service_generation")
                and claim_status.get("service_generation") == grant.get("service_generation")
                and claim_status.get("state") in {"PENDING", "EXECUTION_RESERVED"}
            )
            R["stages"]["runner_claim"] = {
                "claim": claim, "grant": grant, "event_states": states,
                "event_payloads": event_payloads, "live_generation": live_generation,
                "claim_status": claim_status, "column_binding": column_binding,
                "tuple_binding": tuple_binding, "event_binding": event_binding,
                "status_binding": status_binding,
            }
            if not all((column_binding, tuple_binding, event_binding, status_binding)):
                stop("durable Runner claim is not bound to the exact authorization tuple")
            R["stages"]["runner_claim"]["verdict"] = "PASS"
            break
        time.sleep(0.25)
    if claim is None:
        R["stages"]["claim_observations"] = snapshots[-16:]
        stop("no durable Runner claim appeared before the bounded deadline; no retry")

    # Dispatcher/Runner owns execution. This code only observes the one durable
    # receipt and never directly invokes pytest or launches a child test process.
    while time.monotonic() < deadline:
        _claims, events, receipts = _read_task_rows(config["store_path"], task_id)
        if len(receipts) > 1:
            stop("multiple TestRun receipts appeared; no retry")
        if len(receipts) == 1:
            break
        state = _systemd_show("vst-runner.service")
        R["commands"].append({"id": "runner_status_poll", "state": state, "utc": utc()})
        if state.get("LoadState") != "loaded" or state.get("ActiveState") != "active":
            stop("Runner became inactive before producing the terminal TestRun receipt")
        time.sleep(0.25)
    else:
        stop("report-bound TestRun did not finish before the bounded deadline; no retry")

    row = receipts[0]
    receipt = validate_receipt(json.loads(row["body"], object_pairs_hook=_pairs))
    computed = receipt_sha256(receipt)
    selector = identity["selector_test_id"]
    accepted = (
        computed == row["receipt_sha256"]
        and receipt.get("receipt_type") == "TestRun"
        and receipt.get("result") == "PASS"
        and receipt.get("task_id") == task_id
        and receipt.get("slot") == "runtime-tests"
        and receipt.get("attempt") == 1
        and receipt.get("run_id") == identity["run_id"]
        and receipt.get("manifest_sha256") == identity["task_manifest_sha256"]
        and receipt.get("expected_test_ids") == [selector]
        and receipt.get("executed_test_ids") == [selector]
        and receipt.get("skipped_test_ids") == []
        and receipt.get("xfail_test_ids") == []
    )
    R["stages"]["test_run"] = {
        "verdict": "PASS" if accepted else "FAIL", "receipt": receipt,
        "stored_receipt_sha256": row["receipt_sha256"],
        "computed_receipt_sha256": computed, "selector": selector,
        "runner_event_states": [event["state"] for event in events],
    }
    if not accepted:
        stop("one report-bound TestRun did not produce the exact authorized PASS receipt")
    return receipt


R = {
    "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
    "authorization_request_id": AUTH["authorization"]["request_id"],
    "authorization_reply_id": AUTH["authorization"]["reply_id"],
    "identity": {key: AUTH["identity"][key] for key in (
        "runtime_source_head", "run_id", "bootstrap_request_id",
        "nonce", "runtime_selector", "bundle_sha256", "config_bundle_sha256",
        "task_manifest_sha256", "selector_test_id")},
    "started_utc": utc(), "commands": [], "prestart": {}, "stages": {},
    "terminal": None, "retry_cap": 0,
}

try:
    if os.geteuid() != 0:
        stop("WSL protocol requires the existing root execution boundary")
    supervisor_config = _prestart_inventory(AUTH["identity"])
    # Direct source/config/host observations and inactive checks are the
    # qualification boundary; no Runner-signed probe is a prerequisite here.
    _start_service("vst-supervisor.service")
    _start_service("vst-signer.service")
    _start_service("vst-runner.service")
    _start_service("vst-dispatch-owner.socket")
    _start_service("vst-dispatcher.service")
    handoff = _run_bootstrap(AUTH["identity"], _json_file("/etc/vst-runner/task-manifest.json"))
    instruction = _run_issuer(handoff, AUTH["identity"])
    _owner_submit(instruction, AUTH["identity"])
    _wait_for_test_run(supervisor_config,
                       _json_file("/etc/vst-runner/task-manifest.json"),
                       instruction, AUTH["identity"])
    R["terminal"] = "PASS"
    R["reason"] = "Exact one-shot mount-free host checks and real Owner-to-Runner TestRun completed."
except Hold:
    pass
except BaseException as exc:
    R["terminal"] = "HOLD"
    R["reason"] = "protocol exception: " + type(exc).__name__ + ": " + str(exc)[:384]
finally:
    R["finished_utc"] = utc()
    R["zero_retry_confirmed"] = True
    R["top_level_wsl_processes"] = 1

encoded = _canonical(R)
if len(encoded) > MAX_REPORT_BYTES:
    minimal = {
        "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
        "terminal": "HOLD", "reason": "protocol evidence exceeded its output bound",
        "report_bytes": len(encoded), "report_sha256": hashlib.sha256(encoded).hexdigest(),
        "started_utc": R["started_utc"], "finished_utc": R["finished_utc"],
        "zero_retry_confirmed": True, "top_level_wsl_processes": 1,
    }
    R = minimal
    encoded = _canonical(R)
sys.stdout.buffer.write(encoded)
sys.stdout.buffer.flush()
raise SystemExit(0 if R.get("terminal") == "PASS" else 2)
