"""Capture one exact probe invocation from systemd's journal into a root-owned record."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Callable

from .contracts import ContractError, canonical_bytes
from .preflight import (
    MAX_FRESH_PROBE_AGE_NS,
    SPEC_PATH,
    validate_fresh_probe,
    verify_network_policy_attestation,
)
from .runner_service import _read_root_controlled_json
from .supervisor_service import (
    DEFAULT_CONFIG_PATH,
    _read_controlled_json,
    _read_root_key,
)

PROBE_UNIT = "vst-sandbox-probe.service"
PROBE_REQUEST_PATH = "/etc/vst-runner/probe-request.json"
NETWORK_ATTESTATION_PATH = "/run/vst-preflight/network-policy-attestation.json"
JOURNALCTL_PATH = "/usr/bin/journalctl"
SYSTEMCTL_PATH = "/usr/bin/systemctl"
MAX_JOURNAL_BYTES = 1024 * 1024
MAX_CAPTURE_AGE_NS = MAX_FRESH_PROBE_AGE_NS
INVOCATION_ID = re.compile(r"^[0-9a-f]{32}$")


def _read_probe_message(raw: bytes, *, invocation_id: str, run_id: str, nonce: str,
                        spec_sha256: str) -> dict:
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ContractError("probe journal output exceeds the capture limit")
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
        entries = [json.loads(line) for line in lines if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("probe journal output is not valid JSON records") from exc
    if not entries or any(not isinstance(entry, dict) for entry in entries):
        raise ContractError("probe journal returned no structured records")

    messages = []
    for entry in entries:
        if (entry.get("_SYSTEMD_UNIT") != PROBE_UNIT
                or entry.get("_SYSTEMD_INVOCATION_ID") != invocation_id):
            raise ContractError("probe journal includes a record outside the requested invocation")
        if (entry.get("_UID") != "999" or entry.get("_GID") != "989"
                or not isinstance(entry.get("_PID"), str)
                or not entry["_PID"].isdigit() or int(entry["_PID"]) <= 0):
            raise ContractError("probe journal record is not from the configured worker identity")
        message = entry.get("MESSAGE")
        if not isinstance(message, str):
            raise ContractError("probe journal record has no textual message")
        messages.append(message)

    if len(messages) != 1:
        raise ContractError("probe invocation must emit exactly one stdout record")
    try:
        probe = json.loads(messages[0])
    except json.JSONDecodeError as exc:
        raise ContractError("probe output is not one JSON inventory") from exc
    if not validate_fresh_probe(
        probe, run_id=run_id, nonce=nonce, spec_sha256=spec_sha256,
    ):
        raise ContractError("probe output failed exact run/spec/nonce or inventory validation")
    return probe


def _validate_invocation_result(raw: bytes, *, invocation_id: str) -> None:
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ContractError("probe service result journal exceeds the capture limit")
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
        entries = [json.loads(line) for line in lines if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("probe service result is not valid journal JSON") from exc
    if not entries or any(not isinstance(entry, dict) for entry in entries):
        raise ContractError("probe service result journal has no structured records")
    results = []
    for entry in entries:
        if (entry.get("UNIT") != PROBE_UNIT
                or entry.get("INVOCATION_ID") != invocation_id
                or entry.get("_PID") != "1" or entry.get("_UID") != "0"):
            raise ContractError("probe result journal is not from the exact root systemd invocation")
        result = entry.get("UNIT_RESULT")
        if result is not None:
            results.append(result)
    if results != ["success"]:
        raise ContractError("probe systemd invocation did not record one successful unit result")


def _ensure_root_capture_directory(path: str) -> str:
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ContractError("preflight record path must be absolute")
    parent = os.path.dirname(path)
    current = parent
    while True:
        try:
            directory_stat = os.stat(current, follow_symlinks=False)
        except OSError as exc:
            raise ContractError("preflight record parent is unavailable") from exc
        if (not stat.S_ISDIR(directory_stat.st_mode) or directory_stat.st_uid != 0
                or directory_stat.st_mode & 0o022):
            raise ContractError("preflight record parents must be root-controlled")
        if current == "/":
            break
        current = os.path.dirname(current)
    parent_stat = os.stat(parent, follow_symlinks=False)
    if stat.S_IMODE(parent_stat.st_mode) != 0o700:
        raise ContractError("preflight record parent must be root-owned mode 0700")
    try:
        os.lstat(path)
    except FileNotFoundError:
        return parent
    except OSError as exc:
        raise ContractError("preflight record path cannot be inspected") from exc
    raise ContractError("refusing to replace an existing preflight record")


def _write_root_record(path: str, record: dict) -> str:
    parent = _ensure_root_capture_directory(path)
    payload = canonical_bytes(record) + b"\n"
    descriptor, temporary_path = tempfile.mkstemp(prefix=".preflight-capture-", dir=parent)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            os.fchown(stream.fileno(), 0, 0)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # link() publishes atomically and fails if another record already exists.
            os.link(temporary_path, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise ContractError("refusing to replace an existing preflight record") from exc
        directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
    info = os.stat(path, follow_symlinks=False)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o600):
        raise ContractError("captured preflight record has unexpected ownership or mode")
    return hashlib.sha256(payload).hexdigest()


def capture_probe_invocation(invocation_id: str, *,
                             config_path: str = DEFAULT_CONFIG_PATH,
                             journalctl_path: str = JOURNALCTL_PATH,
                             run: Callable = subprocess.run) -> dict[str, str]:
    """Validate one journal invocation and publish its exact inventory without overwriting."""
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise ContractError("root probe capture requires POSIX")
    if os.geteuid() != 0:
        raise ContractError("root-owned probe capture must run as UID 0")
    if not isinstance(invocation_id, str) or not INVOCATION_ID.fullmatch(invocation_id):
        raise ContractError("systemd invocation id is malformed")

    config = _read_controlled_json(config_path)
    request = _read_root_controlled_json(PROBE_REQUEST_PATH, max_bytes=65536)
    if set(request) != {"run_id", "nonce"}:
        raise ContractError("probe request fields do not match the exact run contract")
    run_id, nonce = config.get("run_id"), config.get("probe_nonce")
    if (not isinstance(run_id, str) or not run_id.strip()
            or not isinstance(nonce, str) or not nonce.strip()
            or request != {"run_id": run_id, "nonce": nonce}):
        raise ContractError("probe request does not match the root Supervisor run binding")

    spec_sha256 = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    operator_key = _read_root_key(config["operator_key_path"])
    attestation = _read_root_controlled_json(NETWORK_ATTESTATION_PATH, max_bytes=65536)
    if not verify_network_policy_attestation(
        attestation, run_id=run_id, spec_sha256=spec_sha256, nonce=nonce, key=operator_key,
    ):
        raise ContractError("root network-policy attestation is invalid for this run")

    try:
        journal = run(
            [journalctl_path, "--no-pager", "--output=json",
             f"_SYSTEMD_UNIT={PROBE_UNIT}",
             f"_SYSTEMD_INVOCATION_ID={invocation_id}"],
            check=False, capture_output=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError("cannot read the exact probe invocation from systemd journal") from exc
    if journal.returncode != 0:
        raise ContractError("systemd journal query for the probe invocation failed")
    try:
        result_journal = run(
            [journalctl_path, "--no-pager", "--output=json",
             f"UNIT={PROBE_UNIT}", f"INVOCATION_ID={invocation_id}",
             "_PID=1", "_UID=0"],
            check=False, capture_output=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError("cannot verify the exact probe invocation result") from exc
    if result_journal.returncode != 0:
        raise ContractError("systemd journal query for the exact probe result failed")
    _validate_invocation_result(result_journal.stdout, invocation_id=invocation_id)
    probe = _read_probe_message(
        journal.stdout, invocation_id=invocation_id, run_id=run_id,
        nonce=nonce, spec_sha256=spec_sha256,
    )
    age_ns = time.monotonic_ns() - probe["inventory"]["observed_at_monotonic_ns"]
    if not 0 <= age_ns <= MAX_CAPTURE_AGE_NS:
        raise ContractError("probe inventory is stale or from a different monotonic clock")
    if probe["inventory"].get("network_policy_attestation") != attestation:
        raise ContractError("captured probe does not contain the verified root attestation")

    digest = _write_root_record(config["preflight_record_path"], probe)
    return {"run_id": run_id, "invocation_id": invocation_id, "probe_sha256": digest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("invocation_id", help="exact 32-character systemd InvocationID captured while active")
    args = parser.parse_args(argv)
    try:
        result = capture_probe_invocation(args.invocation_id)
    except (ContractError, OSError, KeyError, ValueError) as exc:
        print(f"probe capture refused: {exc}", file=sys.stderr)
        return 2
    print("captured root-owned probe record " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
