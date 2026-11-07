"""Focused real-process E2E for the provisioned Windows Owner -> Worker path.

This standalone harness consumes (and never creates) an existing signed Owner
instruction and its already-authorized task manifest. It requires the six VST
SCM services and protected Windows runtime to be provisioned and running. It
does not install, start, stop, or reconfigure services, create signing keys, or
edit the manifest.

Inputs (set only on the provisioned Windows test host):
  VST_S2E_INSTRUCTION_INPUT  Path to the existing one-shot signed envelope JSON.
  VST_S2E_MANIFEST_INPUT     Path to its existing v2 manifest JSON in this repo.

Run only after provisioned: python tests/vst/test_s2_owner_runner_windows_e2e.py
The current unprovisioned developer host must report this journey as NOT_RUN.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
import unittest
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
_HEADER = struct.Struct("!I")
_MAX_OWNER_REQUEST = 64 * 1024
_MAX_OWNER_RESPONSE = 256 * 1024
_POLL_MARGIN_SEC = 120.0
_MAX_MANIFEST_TIMEOUT_SEC = 3600
_POLL_INTERVAL_SEC = 0.25
_OWNER_ROLE_CONFIG_FIELDS = {
    "principal", "openssl_path", "trust_registry", "interactive_owner_sid",
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _read_json(path: Path, *, max_bytes: int) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError(f"input exceeds {max_bytes} bytes: {path.name}")
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError(f"input must be a JSON object: {path.name}")
    return value


def _read_exact(connection: Any, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise OSError("Owner named pipe closed before the complete response frame")
        data.extend(chunk)
    return bytes(data)


def _poll_deadline_sec(manifest: dict[str, Any]) -> float:
    """Poll window = manifest execution timeout + margin (provisioner assumes +120 s)."""
    timeout_sec = manifest.get("timeout_sec")
    if (type(timeout_sec) is not int
            or not 1 <= timeout_sec <= _MAX_MANIFEST_TIMEOUT_SEC):
        raise ValueError(
            f"manifest timeout_sec must be an int in 1..{_MAX_MANIFEST_TIMEOUT_SEC}, "
            f"got {timeout_sec!r}"
        )
    return timeout_sec + _POLL_MARGIN_SEC


def _owner_rpc(runtime: Any, message: dict[str, Any]) -> Any:
    """Make one real authenticated request to the installed Owner SCM service."""
    from tools.vst.contracts import canonical_bytes
    from tools.vst.windows_named_pipe import WindowsNamedPipeClient

    owner = runtime.identity("owner")
    client = WindowsNamedPipeClient(
        runtime.pipe_name("owner"), expected_server_sid=owner.service_sid,
        expected_server_service=owner.service_name, timeout_sec=10.0,
    )
    payload = canonical_bytes(message)
    if not 2 <= len(payload) <= _MAX_OWNER_REQUEST:
        raise ValueError("Owner request is outside the bounded frame size")
    with client.connect() as connection:
        connection.sendall(_HEADER.pack(len(payload)) + payload)
        size = _HEADER.unpack(_read_exact(connection, _HEADER.size))[0]
        if not 2 <= size <= _MAX_OWNER_RESPONSE:
            raise ValueError("Owner response is outside the bounded frame size")
        response = json.loads(
            _read_exact(connection, size), object_pairs_hook=_unique_object,
        )
    if not isinstance(response, dict) or type(response.get("ok")) is not bool:
        raise ValueError("Owner returned a malformed response frame")
    if response["ok"] is not True:
        raise RuntimeError("Owner refused the signed instruction or receipt poll")
    if set(response) != {"ok", "result"}:
        raise ValueError("Owner success response has unexpected fields")
    return response["result"]


class S2OwnerRunnerWindowsProcessE2E(unittest.TestCase):
    """One authorized instruction across actual Windows service boundaries."""

    def _preflight(self) -> tuple[Any, dict[str, Any], dict[str, Any], str]:
        if os.name != "nt":
            self.skipTest("NOT_RUN: this process E2E requires Windows SCM and named pipes")

        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.IsUserAnAdmin.restype = ctypes.c_bool
        if not shell32.IsUserAnAdmin():
            self.skipTest(
                "NOT_RUN: elevated Windows identity is required to read the protected "
                "runtime/manifest inputs; the harness will not self-elevate"
            )

        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        runtime_path = Path(program_data) / "VST" / "runtime.json"
        if not runtime_path.is_file():
            self.skipTest("NOT_RUN: provisioned VST runtime.json is missing")

        instruction_path_text = os.environ.get("VST_S2E_INSTRUCTION_INPUT")
        manifest_path_text = os.environ.get("VST_S2E_MANIFEST_INPUT")
        if not instruction_path_text or not manifest_path_text:
            self.skipTest(
                "NOT_RUN: set VST_S2E_INSTRUCTION_INPUT and VST_S2E_MANIFEST_INPUT "
                "to existing provisioned inputs; this harness never creates them"
            )
        instruction_path = Path(instruction_path_text).resolve(strict=False)
        manifest_path = Path(manifest_path_text).resolve(strict=False)
        try:
            manifest_path.relative_to(ROOT)
        except ValueError:
            self.fail("the task manifest input must be inside this project checkout")
        if not instruction_path.is_file():
            self.skipTest("NOT_RUN: existing signed Owner instruction input is missing")
        if not manifest_path.is_file():
            self.skipTest("NOT_RUN: existing authorized task manifest input is missing")

        try:
            from tools.vst.windows_service_host import (
                WindowsRuntimeConfig, role_names, read_runtime_json,
            )
            from tools.vst.windows_named_pipe import _service_process_id
            from tools.vst.dispatch_instruction import (
                validate_dispatch_instruction, verify_dispatch_instruction,
            )
            from tools.vst.contracts import manifest_sha256, validate_task_manifest

            runtime = WindowsRuntimeConfig.load(str(runtime_path))
        except (OSError, ValueError) as exc:
            self.skipTest(f"NOT_RUN: protected Windows runtime is unavailable: {exc}")

        # Do not start or stop services. Verify all six real SCM instances are
        # already running before sending the one-shot signed instruction.
        for role, service_name in role_names().items():
            try:
                pid = _service_process_id(service_name)
            except (OSError, ValueError) as exc:
                self.skipTest(
                    f"NOT_RUN: required installed service {service_name} is not running: {exc}"
                )
            if pid <= 0:
                self.skipTest(f"NOT_RUN: required installed service {service_name} has no PID")

        owner_config = read_runtime_json(runtime, "owner.json")
        if set(owner_config) != _OWNER_ROLE_CONFIG_FIELDS:
            self.fail("provisioned Owner config does not match its fixed schema")
        instruction = validate_dispatch_instruction(_read_json(
            instruction_path, max_bytes=_MAX_OWNER_REQUEST,
        ))
        if instruction["task_id"] == "" or instruction["slot"] == "":
            self.fail("signed instruction is not bound to a task and receipt slot")
        verify_dispatch_instruction(
            instruction, owner_config["trust_registry"],
            expected_principal=owner_config["principal"],
            openssl_path=owner_config["openssl_path"],
        )

        manifest = validate_task_manifest(_read_json(manifest_path, max_bytes=1024 * 1024))
        manifest_digest = manifest_sha256(manifest)
        if manifest["task_id"] != instruction["task_id"]:
            self.fail("signed instruction task_id differs from the existing manifest")
        slot_types = {
            item["slot"]: item["receipt_type"] for item in manifest["required_receipts"]
        }
        if slot_types.get(instruction["slot"]) != "TestRun":
            self.fail("signed instruction slot is not a manifest-authorized TestRun slot")
        commands = [
            item for item in manifest["mandatory_commands"]
            if item["slot"] == instruction["slot"]
        ]
        if len(commands) != 1:
            self.fail("focused E2E requires exactly one existing mandatory command for the slot")
        return runtime, instruction, manifest, manifest_digest

    def test_signed_owner_instruction_completes_in_real_windows_worker_job(self) -> None:
        """Submit once, then poll only for its exact durable Store completion."""
        from tools.vst.contracts import derive_result, validate_receipt

        runtime, instruction, manifest, manifest_digest = self._preflight()

        # Validate before the one-shot submit so a bad manifest never burns the instruction.
        try:
            poll_window_sec = _poll_deadline_sec(manifest)
        except ValueError as exc:
            self.fail(str(exc))

        # Refuse to re-submit an instruction whose receipt already exists.
        existing = _owner_rpc(runtime, {
            "operation": "completed_receipt", "instruction": instruction,
        })
        if existing is not None:
            self.skipTest(
                "NOT_RUN: this one-shot signed instruction already has a completed receipt; "
                "refusing replay"
            )

        # Exactly one mutation-capable Owner request. Never retry an ambiguous result.
        accepted = _owner_rpc(runtime, {"instruction": instruction})
        self.assertIsInstance(accepted, dict)
        self.assertEqual(accepted.get("instruction"), instruction)
        for field in ("task_id", "slot", "attempt", "epoch", "run_id", "request_id"):
            self.assertEqual(accepted.get(field), instruction[field], field)
        self.assertEqual(accepted.get("manifest_digest"), manifest_digest)

        deadline = time.monotonic() + poll_window_sec
        completed: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            result = _owner_rpc(runtime, {
                "operation": "completed_receipt", "instruction": instruction,
            })
            if result is not None:
                self.assertIsInstance(result, dict)
                completed = result
                break
            threading.Event().wait(_POLL_INTERVAL_SEC)
        self.assertIsNotNone(
            completed,
            "Owner did not expose a durable COMPLETE receipt before the bounded deadline",
        )

        # The Owner instruction ID and Runner grant ID are intentionally distinct.
        # The dispatch wrapper binds the accepted Owner request; the execution
        # wrapper binds the exact one-use grant whose attestation is in the receipt.
        self.assertEqual(set(completed), {"dispatch", "execution"})
        dispatch = completed["dispatch"]
        self.assertEqual(set(dispatch), {
            "principal", "task_id", "slot", "attempt", "epoch", "run_id",
            "request_id", "service_generation",
        })
        for field in (
                "principal", "task_id", "slot", "attempt", "epoch", "run_id",
                "request_id", "service_generation"):
            self.assertEqual(dispatch[field], accepted[field], f"dispatch.{field}")
        execution = completed["execution"]
        self.assertEqual(set(execution), {"request_id", "receipt"})
        grant_request_id = execution["request_id"]
        self.assertIsInstance(grant_request_id, str)
        self.assertTrue(grant_request_id)
        receipt = execution["receipt"]
        self.assertIsInstance(receipt, dict)
        valid = validate_receipt(receipt)
        self.assertEqual(valid["receipt_type"], "TestRun")
        for field in ("task_id", "slot", "attempt", "epoch"):
            self.assertEqual(valid[field], instruction[field], field)
        self.assertEqual(valid["manifest_sha256"], manifest_digest)
        self.assertEqual(valid["result"], "PASS")
        self.assertEqual(derive_result(valid), "PASS")

        # The read-only Owner poll returns only a Store-validated durable COMPLETE
        # receipt. Store verifies the HMAC before appending it; this harness checks
        # the signed request/receipt identity without exporting the Signer secret.
        attestation = valid["runner_attestation"]
        request = attestation["request"]
        self.assertEqual(valid["signature"], attestation["signature"])
        self.assertEqual(request["request_id"], grant_request_id)
        self.assertEqual(request["task_id"], accepted["task_id"])
        self.assertEqual(request["slot"], accepted["slot"])
        self.assertEqual(request["attempt"], accepted["attempt"])
        self.assertEqual(request["epoch"], accepted["epoch"])
        self.assertEqual(request["manifest_sha256"], manifest_digest)

        pinned_argv = [
            item["argv"] for item in manifest["mandatory_commands"]
            if item["slot"] == instruction["slot"]
        ]
        self.assertEqual(len(valid["commands"]), 1)
        self.assertEqual(valid["commands"][0]["argv"], pinned_argv[0])
        self.assertEqual(valid["commands"][0]["exit_code"], 0)
        self.assertIs(valid["commands"][0].get("job_object"), True)
        self.assertEqual(request["commands"], valid["commands"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
