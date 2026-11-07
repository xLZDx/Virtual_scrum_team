"""Create disposable, test-only Owner -> Runner inputs for the Windows SCM E2E.

This helper is invoked only by the elevated, one-shot local provisioner. It
does not install or start Windows services and it does not create production
keys, assignments, preflight evidence, or credentials.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from tools.vst.contracts import manifest_sha256
from tools.vst.dispatch_instruction import (
    DISPATCH_INSTRUCTION_PURPOSE,
    dispatch_instruction_signing_bytes,
    validate_dispatch_instruction,
)
from tools.vst.store import Store


def _write_json(path: Path, value: dict) -> None:
    with path.open("xb") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n")


def _run(argv: list[str]) -> None:
    result = subprocess.run(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=10,
        env={"SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"), "PATH": ""},
    )
    if result.returncode:
        raise RuntimeError(f"test-only key operation failed ({result.returncode})")


def _ed25519_pair(openssl: Path, private: Path, public: Path) -> None:
    _run([str(openssl), "genpkey", "-algorithm", "ED25519", "-out", str(private)])
    _run([str(openssl), "pkey", "-in", str(private), "-pubout", "-out", str(public)])


def seed(root: Path, repo: Path, openssl: Path, owner_sid: str, run_id: str) -> dict:
    if os.name != "nt" or not root.is_absolute() or not repo.is_absolute():
        raise RuntimeError("Windows provisioner requires absolute Windows paths")
    data = root
    store_root = root / "store"
    signer_root = root / "signer"
    issuer_root = root / "issuer-private"
    for directory in (data, store_root, signer_root, issuer_root):
        directory.mkdir(parents=True, exist_ok=True)

    source_manifest = repo / "docs" / "sdlc" / "runtime-config" / "task-manifest.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    if (manifest.get("task_id") != "S2-4E-WINDOWS-OWNER-RUNNER"
            or manifest.get("retry_cap") != 0
            or manifest.get("acceptance") != ["REQ-003"]):
        raise RuntimeError("current task manifest is not the authorized S2-4E one-shot manifest")

    owner_key_id = "s2e-owner-test-key"
    grant_key_id = "s2e-runner-test-grant"
    owner_private = issuer_root / "owner-private.pem"
    owner_public = data / "owner-public.pem"
    grant_private = store_root / "grant-private.pem"
    grant_public = data / "grant-public.pem"
    _ed25519_pair(openssl, owner_private, owner_public)
    _ed25519_pair(openssl, grant_private, grant_public)

    event_key = secrets.token_bytes(32)
    startup_key = secrets.token_bytes(32)
    resolution_key = secrets.token_bytes(32)
    receipt_key = secrets.token_bytes(32)
    event_key_path = store_root / "event.key"
    startup_key_path = store_root / "startup.key"
    resolution_key_path = store_root / "resolution.key"
    receipt_key_path = signer_root / "receipt.key"
    for path, payload in (
        (event_key_path, event_key), (startup_key_path, startup_key),
        (resolution_key_path, resolution_key), (receipt_key_path, receipt_key),
    ):
        with path.open("xb") as stream:
            stream.write(payload)

    store_path = store_root / "store.sqlite3"
    anchor_path = store_root / "store.anchor"
    ledger_path = signer_root / "signing.sqlite3"
    model = manifest["model_policy"]
    model_digest = hashlib.sha256(b"S2-4E local test-only model provenance").hexdigest()
    audience = "vst-runner-service-v1"
    owner_registry = {
        owner_key_id: {
            "principal": "Codex",
            "purpose": DISPATCH_INSTRUCTION_PURPOSE,
            "public_key_path": str(owner_public),
        },
    }

    runtime = {
        "data_root": str(data), "store_root": str(store_root),
        "signer_root": str(signer_root),
    }
    owner_config = {
        "principal": "Codex", "openssl_path": str(openssl),
        "trust_registry": owner_registry, "interactive_owner_sid": owner_sid,
    }
    supervisor_config = {
        "store_path": str(store_path), "anchor_path": str(anchor_path),
        "event_key_path": str(event_key_path),
        "startup_supervisor_key_path": str(startup_key_path),
        "execution_resolution_key_path": str(resolution_key_path),
        "execution_grant_key_id": grant_key_id,
        "execution_grant_private_key_path": str(grant_private),
        "execution_grant_trust_keys": {grant_key_id: str(grant_public)},
        "openssl_path": str(openssl), "execution_grant_audience": audience,
        "dispatch_instruction_trust_keys": owner_registry,
        "model_provenance": {model: model_digest}, "run_id": run_id,
        "dispatch_owner_principal": "Codex",
    }
    runner_config = {"repository_root": str(root / "app"), "runner_id": "VSTRunner"}
    signer_config = {"receipt_key_path": str(receipt_key_path), "ledger_path": str(ledger_path)}
    for name, value in (
        ("runtime.json", runtime), ("owner.json", owner_config),
        ("supervisor.json", supervisor_config), ("runner.json", runner_config),
        ("signer.json", signer_config),
    ):
        _write_json(data / name, value)

    manifest_digest = manifest_sha256(manifest)
    with Store(
        str(store_path), event_key=event_key, anchor_path=str(anchor_path),
        sandbox_mode=False, supervisor_key=startup_key,
        execution_resolution_key=resolution_key, supervisor_runner_id="VSTSupervisor",
    ) as store:
        store.init_slots(1)
        story_id = manifest["story_id"]
        store.open_story(story_id, manifest["project_id"], manifest["phase"])
        # The Runner claim/reserve/complete each require
        # min(owner, lease) expiry - now >= manifest timeout_sec + completion margin.
        # The operator starts the E2E task some time after seeding, so keep ample slack.
        epoch = store.acquire_epoch(story_id, "Codex", ttl_sec=7200)
        store.register_task(manifest)
        store.acquire_lease(
            manifest["task_id"], story_id, "VSTRunner", epoch, 1, 5400,
            supervisor_key=startup_key,
        )

    unsigned = {
        "version": 1, "algorithm": "Ed25519", "purpose": DISPATCH_INSTRUCTION_PURPOSE,
        "request_id": secrets.token_hex(16), "task_id": manifest["task_id"],
        "slot": "runtime-tests", "attempt": 1, "epoch": epoch, "run_id": run_id,
        "key_id": owner_key_id,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=90)).replace(
            microsecond=0,
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    payload_path = issuer_root / "owner-instruction-signing-input.bin"
    signature_path = issuer_root / "owner-instruction-signature.bin"
    # The signing-bytes helper validates the complete v1 envelope (signature included)
    # and then drops the signature, so a well-formed placeholder is required here.
    placeholder = {**unsigned, "signature": "A" * 86}
    with payload_path.open("xb") as stream:
        stream.write(dispatch_instruction_signing_bytes(placeholder))
    _run([
        str(openssl), "pkeyutl", "-sign", "-rawin", "-inkey", str(owner_private),
        "-in", str(payload_path), "-out", str(signature_path),
    ])
    signature = base64.urlsafe_b64encode(signature_path.read_bytes()).decode("ascii").rstrip("=")
    instruction = validate_dispatch_instruction({**unsigned, "signature": signature})
    _write_json(data / "owner-instruction.json", instruction)
    payload_path.unlink()
    signature_path.unlink()

    result = {
        "project_id": "Virtual_scrum_team", "run_id": run_id,
        "task_id": manifest["task_id"],
        "manifest_sha256": manifest_digest, "owner_key_id": owner_key_id,
        "grant_key_id": grant_key_id, "instruction_request_id": instruction["request_id"],
        "service_names": ["VSTOwner", "VSTSupervisor", "VSTDispatcher", "VSTRunner", "VSTSigner", "VSTWorker"],
        "runtime_root": str(root), "instruction_path": str(data / "owner-instruction.json"),
        "manifest_path": str(source_manifest), "test_only": True,
    }
    _write_json(root / "provisioned.json", result)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--openssl", type=Path, required=True)
    parser.add_argument("--owner-sid", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        seed(args.root, args.repo, args.openssl, args.owner_sid, args.run_id)
    except Exception as exc:
        # Exception text carries useful path/contract context but never key bytes;
        # OpenSSL stderr is intentionally omitted by _run to avoid leaking material.
        print(f"S2-4E test setup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
