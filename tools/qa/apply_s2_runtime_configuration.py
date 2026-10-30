#!/usr/bin/env python3
"""Apply only the reviewed non-secret S2 runtime configuration to Ubuntu-24.04 WSL."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BUNDLE = REPO / "docs/sdlc/runtime-config"
INVENTORY_SCHEMA = "VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1"
CONFIG_ROOT = "/etc/vst-runner"
SYSTEMD_ROOT = "/etc/systemd/system"
RUNTIME_SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"
BUNDLE_MANIFEST_SHA256 = "05530c73ea583f0f7f60963ba9e196082dfb7abf92f86f0a0e2a0ae9ad10f91f"
INSTALLATION_LAYOUT_SHA256 = "47d3e66f1d765c0b078428708d2d9bf6c0218085714878e11395d164d57d1c19"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _git_blob(commit: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(REPO), "--no-replace-objects", "show", f"{commit}:{relative_path}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise ValueError("committed S2 configuration blob is unavailable: " + relative_path)
    return result.stdout


def _current_inventory_validation_identity() -> tuple[str, str]:
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True,
    )
    repo_head = head.stdout.strip()
    if head.returncode or not _HEX40.fullmatch(repo_head):
        raise ValueError("cannot establish the exact committed inventory-validation HEAD")
    helper_path = "tools/vst/preflight_host_capture.py"
    committed_helper = _git_blob(repo_head, helper_path)
    working_helper = (REPO / helper_path).read_bytes()
    if committed_helper != working_helper:
        raise ValueError("runtime helper differs from the committed inventory-validation HEAD")
    return repo_head, _sha(committed_helper)


def _load_committed_inventory_validator(repo_head: str):
    relative_path = "tools/qa/verify_s2_runtime_config_inventory.py"
    committed_source = _git_blob(repo_head, relative_path)
    working_path = REPO / relative_path
    if working_path.read_bytes() != committed_source:
        raise ValueError("runtime inventory validator differs from the exact committed Git blob")
    namespace = {"__file__": str(working_path), "__name__": "_vst_s2_inventory_validator"}
    exec(compile(committed_source, str(working_path), "exec", dont_inherit=True), namespace)
    validator = namespace.get("validate_inventory")
    if not callable(validator):
        raise ValueError("committed runtime inventory validator has no validation entry point")
    return validator


def _inventory_fingerprint(value: dict[str, Any]) -> dict[str, Any]:
    state = value.get("state")
    if state in ("absent", "ABSENT"):
        return {"state": "absent"}
    if state not in ("file", "PRESENT") or value.get("kind", "regular") not in ("regular", "file"):
        raise ValueError("target inventory contains a non-regular configuration destination")
    mode = value.get("mode")
    if isinstance(mode, str):
        try:
            mode = int(mode, 8)
        except ValueError as exc:
            raise ValueError("target inventory mode is invalid") from exc
    return {"state": "file", "uid": value.get("uid"), "gid": value.get("gid"),
            "mode": mode, "size": value.get("size"), "sha256": value.get("sha256")}


def build_payload(
        inventory_path: Path, expected_inventory_sha256: str, source_commit: str, *,
        expected_repo_head: str | None = None,
        expected_helper_sha256: str | None = None) -> bytes:
    if not _HEX64.fullmatch(expected_inventory_sha256):
        raise ValueError("expected inventory digest must be lowercase SHA-256")
    if not _HEX40.fullmatch(source_commit):
        raise ValueError("source commit must be a full lowercase Git object id")
    bundle_bytes = _git_blob(source_commit, "docs/sdlc/runtime-config/bundle-manifest.json")
    layout_bytes = _git_blob(source_commit, "docs/sdlc/runtime-config/installation-layout.json")
    if _sha(bundle_bytes) != BUNDLE_MANIFEST_SHA256 or _sha(layout_bytes) != INSTALLATION_LAYOUT_SHA256:
        raise ValueError("committed config bundle differs from the pinned S2 candidate")
    inventory_bytes = inventory_path.read_bytes()
    if _sha(inventory_bytes) != expected_inventory_sha256:
        raise ValueError("target inventory differs from its exact SHA-256 pin")
    inventory = json.loads(inventory_bytes)
    if (expected_repo_head is None) != (expected_helper_sha256 is None):
        raise ValueError("inventory validator HEAD and helper digest must be supplied together")
    if expected_repo_head is not None and expected_helper_sha256 is not None:
        validate_inventory = _load_committed_inventory_validator(expected_repo_head)
        validate_inventory(
            inventory,
            expected_repo_head=expected_repo_head,
            expected_helper_sha256=expected_helper_sha256,
        )
    if (not isinstance(inventory, dict)
            or inventory.get("schema") != INVENTORY_SCHEMA
            or inventory.get("source_head", inventory.get("runtime_source_head")) != RUNTIME_SOURCE_HEAD
            or not isinstance(inventory.get("configuration_files"), dict)):
        raise ValueError("target inventory schema or configuration map is invalid")
    runtime_selector = inventory.get("runtime_selector")
    selected = runtime_selector.get("link_target") if isinstance(runtime_selector, dict) else None
    if selected != "/opt/vst-runtime-" + RUNTIME_SOURCE_HEAD:
        raise ValueError("target inventory does not identify the selected S2 runtime")
    captured = datetime.fromisoformat(str(inventory["captured_utc"]).replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
    if age < -30 or age > 300:
        raise ValueError("target inventory is outside the five-minute freshness window")

    bundle = json.loads(bundle_bytes)
    layout = json.loads(layout_bytes)
    source_head = bundle.get("runtime_source_head")
    if (bundle.get("schema") != "VST_S2_NON_SECRET_CONFIG_BUNDLE_V1"
            or bundle.get("state") != "PREPARED_NOT_INSTALLED"
            or source_head != RUNTIME_SOURCE_HEAD):
        raise ValueError("configuration bundle is not a pinned S2 preparation candidate")

    records = {item["path"]: item for item in bundle["files"]}
    entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
    entries += [item for item in bundle["units"]
                if item["publication"] == "new absent-only configuration unit; no enable/start during installation"]
    if len(entries) != 26 or len({item["destination"] for item in entries}) != len(entries):
        raise ValueError("configuration bundle does not contain the exact 26 unique destinations")

    files: list[dict[str, Any]] = []
    inventory_map = inventory["configuration_files"]
    for item in entries:
        destination, source = item["destination"], item["source"]
        if not (destination.startswith(CONFIG_ROOT + "/") or destination.startswith(SYSTEMD_ROOT + "/")):
            raise ValueError("destination is outside the fixed configuration roots")
        record = records.get(source)
        if record is None:
            raise ValueError("configuration source is absent from the bundle manifest")
        if not isinstance(source, str) or source.startswith("/") or ".." in Path(source).parts:
            raise ValueError("configuration source path is not a fixed bundle-relative path")
        data = _git_blob(source_commit, "docs/sdlc/runtime-config/" + source)
        if len(data) != record["size"] or _sha(data) != record["sha256"]:
            raise ValueError("configuration source differs from the pinned bundle: " + source)
        if b"PRIVATE KEY-----" in data:
            raise ValueError("private-key material is forbidden in the configuration transfer")
        inventory_entry = inventory_map.get(destination)
        if not isinstance(inventory_entry, dict):
            raise ValueError("target inventory lacks destination: " + destination)
        current = _inventory_fingerprint(inventory_entry)
        if current["state"] == "file":
            if (not _HEX64.fullmatch(str(current.get("sha256", "")))
                    or any(type(current.get(key)) is not int for key in ("uid", "gid", "mode", "size"))):
                raise ValueError("target inventory fingerprint is incomplete: " + destination)
        mode = int(item["mode"], 8) if isinstance(item["mode"], str) else item["mode"]
        if current.get("state") == "file" and (
                current["uid"] != item["uid"] or current["gid"] != item["gid"]
                or current["mode"] != mode or current["size"] > 1024 * 1024):
            raise ValueError("target inventory metadata differs from the fixed destination contract: " + destination)
        expected_new = {"state": "file", "uid": item["uid"], "gid": item["gid"],
                        "mode": mode, "size": len(data), "sha256": _sha(data)}
        files.append({"destination": destination, "expected_current": current,
                      "expected_new": expected_new, "content_b64": base64.b64encode(data).decode("ascii")})

    payload = {
        "schema": "VST_S2_RUNTIME_CONFIG_APPLY_V1",
        "source_head": source_head,
        "expected_boot_id": inventory["boot_id"],
        "selected_runtime_path": "/opt/vst-runtime-" + source_head,
        "inventory_sha256": expected_inventory_sha256,
        "inventory_b64": base64.b64encode(inventory_bytes).decode("ascii"),
        "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
        "installation_layout_sha256": INSTALLATION_LAYOUT_SHA256,
        "bundle_manifest_b64": base64.b64encode(bundle_bytes).decode("ascii"),
        "installation_layout_b64": base64.b64encode(layout_bytes).decode("ascii"),
        "files": files,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii")


_REMOTE = r'''import base64, fcntl, hashlib, json, os, platform, re, stat, subprocess, sys, tempfile
from datetime import datetime, timezone

BUNDLE_SHA256 = "05530c73ea583f0f7f60963ba9e196082dfb7abf92f86f0a0e2a0ae9ad10f91f"
LAYOUT_SHA256 = "47d3e66f1d765c0b078428708d2d9bf6c0218085714878e11395d164d57d1c19"
SOURCE_HEAD = "80c2b81deac364ed6466600fd46af47aafe805e2"

expected_sha = sys.argv[1]
raw = sys.stdin.buffer.read(2 * 1024 * 1024 + 1)
if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha:
    raise SystemExit("configuration transfer digest/size invalid")
try:
    p = json.loads(raw)
except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    raise SystemExit("configuration transfer is invalid JSON") from exc
if os.geteuid() != 0 or platform.system() != "Linux":
    raise SystemExit("configuration apply requires root on Linux")
if (p.get("schema") != "VST_S2_RUNTIME_CONFIG_APPLY_V1" or len(p.get("files", [])) != 26
        or p.get("source_head") != SOURCE_HEAD):
    raise SystemExit("configuration transfer schema/count invalid")
bundle_raw = base64.b64decode(p.get("bundle_manifest_b64", ""), validate=True)
layout_raw = base64.b64decode(p.get("installation_layout_b64", ""), validate=True)
if (hashlib.sha256(bundle_raw).hexdigest() != BUNDLE_SHA256
        or p.get("bundle_manifest_sha256") != BUNDLE_SHA256
        or hashlib.sha256(layout_raw).hexdigest() != LAYOUT_SHA256
        or p.get("installation_layout_sha256") != LAYOUT_SHA256):
    raise SystemExit("configuration manifest differs from the independently pinned candidate")
bundle, layout = json.loads(bundle_raw), json.loads(layout_raw)
if bundle.get("runtime_source_head") != SOURCE_HEAD or bundle.get("state") != "PREPARED_NOT_INSTALLED":
    raise SystemExit("pinned bundle source/state is invalid")
manifest_files = {item["path"]: item for item in bundle["files"]}
expected_entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
expected_entries += [item for item in bundle["units"] if item["publication"].startswith("new absent-only configuration unit")]
expected = {}
for entry in expected_entries:
    mode = int(entry["mode"], 8) if isinstance(entry["mode"], str) else entry["mode"]
    source = manifest_files[entry["source"]]
    expected[entry["destination"]] = {
        "uid": entry["uid"], "gid": entry["gid"], "mode": mode,
        "size": source["size"], "sha256": source["sha256"], "source": entry["source"],
    }
if len(expected) != 26:
    raise SystemExit("pinned manifest destination map is not the exact 26-file set")
inventory_raw = base64.b64decode(p.get("inventory_b64", ""), validate=True)
if hashlib.sha256(inventory_raw).hexdigest() != p.get("inventory_sha256"):
    raise SystemExit("target inventory differs from its exact SHA-256 pin")
inventory = json.loads(inventory_raw)
if (inventory.get("schema") != "VST_S2_RUNTIME_CONFIG_TARGET_INVENTORY_V1"
        or inventory.get("source_head") != SOURCE_HEAD
        or inventory.get("boot_id") != p.get("expected_boot_id")):
    raise SystemExit("target inventory identity differs from the pinned source/boot")
captured = datetime.fromisoformat(str(inventory["captured_utc"]).replace("Z", "+00:00"))
age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
if age < -30 or age > 300:
    raise SystemExit("target inventory is outside the five-minute freshness window")
if inventory.get("runtime_selector", {}).get("link_target") != p.get("selected_runtime_path"):
    raise SystemExit("inventory does not identify the selected candidate runtime")
received = {item.get("destination"): item for item in p["files"]}
if len(received) != 26 or set(received) != set(expected):
    raise SystemExit("configuration payload destination set differs from the pinned manifest")
for path, contract in expected.items():
    item = received[path]
    observed = inventory.get("configuration_files", {}).get(path)
    if not isinstance(observed, dict):
        raise SystemExit("target inventory lacks configuration destination: " + path)
    state = observed.get("state")
    if state == "ABSENT":
        current = {"state": "absent"}
    elif state == "PRESENT" and observed.get("kind") == "regular":
        current = {"state":"file", "uid":observed.get("uid"), "gid":observed.get("gid"),
                   "mode":int(observed["mode"], 8), "size":observed.get("size"),
                   "sha256":observed.get("sha256")}
    else:
        raise SystemExit("target inventory contains a non-regular path: " + path)
    if current != item.get("expected_current"):
        raise SystemExit("payload old fingerprint differs from exact target inventory: " + path)
    target = item.get("expected_new", {})
    if any(target.get(k) != contract[k] for k in ("uid", "gid", "mode", "size", "sha256")):
        raise SystemExit("destination metadata/hash differs from pinned manifest: " + path)
with open("/proc/sys/kernel/osrelease", encoding="ascii") as stream:
    if "microsoft" not in stream.read().lower():
        raise SystemExit("configuration apply requires WSL")
release = {}
with open("/etc/os-release", encoding="ascii") as stream:
    for line in stream:
        k, sep, v = line.rstrip("\n").partition("=")
        if sep: release[k] = v.strip('"')
if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
    raise SystemExit("configuration apply requires Ubuntu 24.04")
with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as stream:
    if stream.read().strip() != p["expected_boot_id"]:
        raise SystemExit("WSL boot identity changed since inventory")
if os.readlink("/opt/vst-runtime") != p["selected_runtime_path"]:
    raise SystemExit("the exact candidate runtime is not selected")
if p["selected_runtime_path"] != "/opt/vst-runtime-" + SOURCE_HEAD:
    raise SystemExit("selected runtime path differs from pinned source")

roots = ("/etc/vst-runner", "/etc/systemd/system")
for root in roots:
    info = os.lstat(root)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
        raise SystemExit("configuration parent is not root-controlled: " + root)

units = ("vst-supervisor.service", "vst-signer.service", "vst-runner.service",
         "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
         "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service", "vst-sandbox-probe.service")
for unit in units:
    result = subprocess.run(["/usr/bin/systemctl", "show", "--property=LoadState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    if result.returncode != 0 or result.stdout.strip() not in ("loaded", "not-found"):
        raise SystemExit("cannot establish unit load state: " + unit)
    if result.stdout.strip() == "loaded":
        active = subprocess.run(["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", unit],
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, check=False, timeout=10)
        if active.returncode != 0 or active.stdout.strip() != "inactive":
            raise SystemExit("configuration apply requires inactive services: " + unit)
jobs = subprocess.run(["/usr/bin/systemctl", "list-jobs", "--no-legend", "--plain"],
                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                      text=True, check=False, timeout=10)
if jobs.returncode != 0:
    raise SystemExit("cannot establish systemd job inventory")
for line in jobs.stdout.splitlines():
    fields = line.split()
    if len(fields) < 4 or not fields[0].isdigit():
        if line.strip() != "No jobs running.": raise SystemExit("unparseable systemd job row")
    elif fields[1] in units:
        raise SystemExit("configuration apply refuses a pending S2 systemd job")

def fingerprint(path):
    try: info = os.lstat(path)
    except FileNotFoundError: return {"state": "absent"}
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise SystemExit("destination is not a single-link regular file: " + path)
    h = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise SystemExit("destination changed while opening: " + path)
        while True:
            chunk = os.read(fd, 65536)
            if not chunk: break
            h.update(chunk)
    finally: os.close(fd)
    return {"state": "file", "uid": info.st_uid, "gid": info.st_gid,
            "mode": stat.S_IMODE(info.st_mode), "size": info.st_size, "sha256": h.hexdigest()}

def allowed_path(path):
    return ((path.startswith("/etc/vst-runner/") and "/../" not in path and not path.endswith("/.."))
            or (path.startswith("/etc/systemd/system/") and "/../" not in path and not path.endswith("/..")))

# Preflight the complete set before any write; retries may see only the pinned old or exact new bytes.
seen = set()
for item in p["files"]:
    path = item.get("destination", "")
    if not allowed_path(path) or path in seen: raise SystemExit("invalid/duplicate destination")
    seen.add(path)
    parent = os.path.dirname(path)
    info = os.lstat(parent)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
        raise SystemExit("destination parent is not root-controlled: " + path)
    actual = fingerprint(path)
    if actual not in (item["expected_current"], item["expected_new"]):
        raise SystemExit("destination differs from pinned old/new state: " + path)
    data = base64.b64decode(item["content_b64"], validate=True)
    new = item["expected_new"]
    if (len(data) != new["size"] or hashlib.sha256(data).hexdigest() != new["sha256"]
            or b"PRIVATE KEY-----" in data):
        raise SystemExit("candidate bytes differ from their non-secret manifest")

lock_path = "/run/vst-s2-config-apply.lock"
fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
lock_info = os.fstat(fd)
if (not stat.S_ISREG(lock_info.st_mode) or lock_info.st_uid != 0 or lock_info.st_gid != 0
        or stat.S_IMODE(lock_info.st_mode) != 0o600 or lock_info.st_nlink != 1):
    raise SystemExit("configuration apply lock is unsafe")
fcntl.flock(fd, fcntl.LOCK_EX)
results = []
for item in p["files"]:
    path = item["destination"]
    parent = os.path.dirname(path)
    data = base64.b64decode(item["content_b64"], validate=True)
    target = item["expected_new"]
    current = fingerprint(path)
    if current == target:
        results.append({"path": path, "sha256": target["sha256"], "result": "already-exact"})
        continue
    if current != item["expected_current"]:
        raise SystemExit("destination changed after preflight: " + path)
    fd_tmp, temporary = tempfile.mkstemp(prefix=".vst-s2-config-", dir=parent)
    try:
        with os.fdopen(fd_tmp, "wb", closefd=True) as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chown(temporary, target["uid"], target["gid"])
        os.chmod(temporary, target["mode"])
        # Recheck immediately before replacement. Parent directories are root-controlled.
        if fingerprint(path) != item["expected_current"]:
            raise SystemExit("destination changed immediately before replacement: " + path)
        os.replace(temporary, path)
        dfd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    if fingerprint(path) != target:
        raise SystemExit("installed destination does not match candidate: " + path)
    results.append({"path": path, "sha256": target["sha256"], "result": "installed"})
reload = subprocess.run(["/usr/bin/systemctl", "daemon-reload"], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        check=False, timeout=30)
if reload.returncode != 0:
    raise SystemExit("systemd did not reload the exact installed unit files")
for unit in units:
    loaded = subprocess.run(["/usr/bin/systemctl", "show", "--property=LoadState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    active = subprocess.run(["/usr/bin/systemctl", "show", "--property=ActiveState", "--value", unit],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=10)
    if loaded.returncode != 0 or active.returncode != 0 or loaded.stdout.strip() != "loaded" or active.stdout.strip() != "inactive":
        raise SystemExit("post-reload unit state is not loaded-inactive: " + unit)
print(json.dumps({"schema":"VST_S2_RUNTIME_CONFIG_APPLY_RESULT_V1", "source_head":p["source_head"],
                  "inventory_sha256":p["inventory_sha256"], "boot_id":p["expected_boot_id"],
                  "daemon_reload":"success", "files":results}, sort_keys=True, separators=(",",":")))
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--inventory-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--distribution", default="Ubuntu-24.04")
    args = parser.parse_args()
    try:
        head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--verify", "HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
        if head.returncode or head.stdout.strip() != args.source_commit:
            raise ValueError("source commit does not equal the current exact checkout HEAD")
        committed_tool = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--verify", "HEAD:tools/qa/apply_s2_runtime_configuration.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True)
        working_tool = subprocess.run(
            ["git", "-C", str(REPO), "hash-object", "--", "tools/qa/apply_s2_runtime_configuration.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, text=True, cwd=REPO)
        if (committed_tool.returncode or working_tool.returncode
                or committed_tool.stdout.strip() != working_tool.stdout.strip()):
            raise ValueError("installer source differs from the exact committed Git blob")
        expected_repo_head, expected_helper_sha256 = _current_inventory_validation_identity()
        payload = build_payload(
            args.inventory, args.inventory_sha256, args.source_commit,
            expected_repo_head=expected_repo_head,
            expected_helper_sha256=expected_helper_sha256,
        )
        digest = _sha(payload)
        wsl = subprocess.run(
            ["wsl.exe", "--distribution", args.distribution, "--user", "root", "--exec",
             "/usr/bin/python3.12", "-I", "-B", "-S", "-c", _REMOTE, digest],
            input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if wsl.stdout:
            print(wsl.stdout.decode("utf-8", errors="replace").rstrip())
        if wsl.returncode:
            print(wsl.stderr.decode("utf-8", errors="replace").rstrip(), file=sys.stderr)
            return wsl.returncode
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
