"""Disposable Ed25519 fixtures for the POSIX-only S2 dispatch trust boundary."""
from __future__ import annotations

import base64
import datetime as dt
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterator

import pytest

from tools.vst.contracts import canonical_bytes
from tools.vst.dispatch_instruction import (
    DISPATCH_INSTRUCTION_DOMAIN,
    DISPATCH_INSTRUCTION_PURPOSE,
    dispatch_instruction_signing_bytes,
)
from tools.vst.execution_grant import _openssl_signature


class DispatchInstructionKeyPair:
    """Temporary synthetic-only issuer key; never use it as runtime evidence."""

    def __init__(self, directory: tempfile.TemporaryDirectory[str], openssl_path: str):
        self._directory = directory
        self.root = Path(directory.name)
        self.openssl_path = openssl_path
        self.private_key_path = str(self.root / "synthetic-instruction-private.pem")
        self.public_key_path = str(self.root / "synthetic-instruction-public.pem")
        self.key_id = "synthetic-instruction-key"
        self.principal = "Codex"
        self.purpose = DISPATCH_INSTRUCTION_PURPOSE
        self._signed_by_request: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
        self._expiry_by_request: dict[str, str] = {}
        self.trust_registry = {
            self.key_id: {
                "principal": self.principal,
                "purpose": self.purpose,
                "public_key_path": self.public_key_path,
            },
        }

    def close(self) -> None:
        self._directory.cleanup()

    def sign(self, dispatch_fields: dict[str, Any], **overrides: Any) -> dict[str, Any]:
        request_id = dispatch_fields["request_id"]
        cache_key = tuple(dispatch_fields[field] for field in (
            "request_id", "task_id", "slot", "attempt", "epoch", "run_id",
        )) + tuple(sorted(overrides.items()))
        cached = self._signed_by_request.get(request_id, {}).get(cache_key)
        if cached is not None:
            return dict(cached)
        now = dt.datetime.now(dt.timezone.utc)
        body = {
            "version": 1,
            "algorithm": "Ed25519",
            "purpose": self.purpose,
            "request_id": dispatch_fields["request_id"],
            "task_id": dispatch_fields["task_id"],
            "slot": dispatch_fields["slot"],
            "attempt": dispatch_fields["attempt"],
            "epoch": dispatch_fields["epoch"],
            "run_id": dispatch_fields["run_id"],
            "key_id": self.key_id,
            "expires_at": self._expiry_by_request.setdefault(
                request_id,
                (now + dt.timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        }
        body.update(overrides)
        candidate = {**body, "signature": base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")}
        payload = dispatch_instruction_signing_bytes(candidate)
        result = self._sign_payload(body, payload)
        self._signed_by_request.setdefault(request_id, {})[cache_key] = dict(result)
        return result

    def sign_arbitrary_envelope(self, body: dict[str, Any]) -> dict[str, Any]:
        """Sign an intentionally malformed-schema envelope for negative tests."""
        return self._sign_payload(body, DISPATCH_INSTRUCTION_DOMAIN + canonical_bytes(body))

    def _sign_payload(self, body: dict[str, Any], payload: bytes) -> dict[str, Any]:
        signature = _openssl_signature(
            self.openssl_path, key_path=self.private_key_path,
            payload=payload, private=True,
        )
        assert isinstance(signature, bytes)
        return {
            **body,
            "signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        }


@pytest.fixture
def dispatch_instruction_keypair() -> Iterator[DispatchInstructionKeyPair]:
    """Make/delete synthetic keys beneath protected WSL `/root`, not production storage."""
    if (os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0):
        pytest.skip("S2 Ed25519 trust-boundary tests require the designated root-owned POSIX test environment")
    openssl_path = shutil.which("openssl")
    if not openssl_path:
        pytest.skip("OpenSSL is unavailable for the synthetic Ed25519 fixture")
    root = Path("/root")
    try:
        info = root.stat()
    except OSError:
        pytest.skip("protected temporary root is unavailable")
    if info.st_uid != 0 or info.st_mode & 0o022:
        pytest.skip("/root is not root-controlled for disposable test keys")

    directory = tempfile.TemporaryDirectory(prefix="vst-s2-dispatch-test-", dir=str(root))
    try:
        private_key_path = Path(directory.name) / "synthetic-instruction-private.pem"
        public_key_path = Path(directory.name) / "synthetic-instruction-public.pem"
        subprocess.run(
            [openssl_path, "genpkey", "-algorithm", "ED25519", "-out", str(private_key_path)],
            check=True, cwd="/", stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        )
        os.chmod(private_key_path, 0o600)
        subprocess.run(
            [openssl_path, "pkey", "-in", str(private_key_path), "-pubout", "-out", str(public_key_path)],
            check=True, cwd="/", stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
        )
        os.chmod(public_key_path, 0o644)
        yield DispatchInstructionKeyPair(directory, openssl_path)
    except (OSError, subprocess.SubprocessError) as exc:
        directory.cleanup()
        pytest.skip(f"synthetic Ed25519 test key setup is unavailable: {type(exc).__name__}")
    finally:
        directory.cleanup()
