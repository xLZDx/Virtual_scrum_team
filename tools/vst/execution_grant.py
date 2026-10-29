"""Signed, one-invocation authority for the persistent runner boundary.

This module validates grant shape and signature only. The caller must still
recheck current Store authority, claim and reserve the grant before spawning a child;
signature validity alone never authorizes execution.
"""

from __future__ import annotations

import base64
import hashlib
import math
import os
import re
import stat
import subprocess
import tempfile
import time
from collections.abc import Mapping
from typing import Any

from .contracts import ContractError, canonical_bytes

EXECUTION_GRANT_LABEL = b"VST_EXECUTION_GRANT_V1\0"
EXECUTION_GRANT_VERSION = 1
MAX_EXECUTION_DEADLINE_SEC = 1800
GRANT_CLAIM_WINDOW_SEC = 30
GRANT_COMPLETION_SLACK_SEC = 90
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = frozenset({
    "version", "key_id", "grant_id", "request_id", "audience",
    "service_generation", "manifest_sha256", "task_id", "slot", "attempt",
    "epoch", "run_id", "invocation_id", "runner_id", "resolved_model",
    "model_provenance_sha256", "execution_deadline_sec",
    "issued_at", "claim_expires_at", "expires_at", "signature",
})
_RUN_CONTEXT_FIELDS = frozenset({
    "manifest_sha256", "task_id", "slot", "attempt", "epoch", "run_id",
    "invocation_id", "request_id", "runner_id", "resolved_model",
    "model_provenance_sha256", "execution_deadline_sec", "service_generation",
})


class AmbiguousExecutionAuthorityError(ContractError):
    """A claim/reservation may be durable, so this daemon generation must exit."""


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ContractError(f"execution grant {field}: invalid identifier")
    return value


def validate_execution_grant(value: object) -> dict[str, Any]:
    """Validate the canonical grant envelope without trusting its signature."""
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ContractError("execution grant: fields do not match v1 contract")
    if type(value["version"]) is not int or value["version"] != EXECUTION_GRANT_VERSION:
        raise ContractError("execution grant: unsupported version")
    for field in (
        "key_id", "grant_id", "request_id", "audience", "service_generation",
        "task_id", "slot", "run_id", "invocation_id", "runner_id", "resolved_model",
    ):
        _identifier(value[field], field)
    for field in ("manifest_sha256", "model_provenance_sha256"):
        if not isinstance(value[field], str) or not _SHA256.fullmatch(value[field]):
            raise ContractError(f"execution grant {field}: expected lowercase SHA-256")
    for field in ("attempt", "epoch"):
        number = value[field]
        if type(number) is not int or number < 1 or number > 2**63 - 1:
            raise ContractError(f"execution grant {field}: expected positive bounded integer")
    for field in ("execution_deadline_sec",):
        number = value[field]
        if type(number) is not int or number < 1 or number > MAX_EXECUTION_DEADLINE_SEC:
            raise ContractError(
                f"execution grant {field}: expected integer in 1..{MAX_EXECUTION_DEADLINE_SEC}"
            )
    for field in ("issued_at", "claim_expires_at", "expires_at"):
        number = value[field]
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ContractError(f"execution grant {field}: expected finite timestamp")
        if not math.isfinite(number) or number < 0:
            raise ContractError(f"execution grant {field}: expected finite timestamp")
    if not (value["issued_at"] < value["claim_expires_at"] < value["expires_at"]):
        raise ContractError("execution grant: claim and completion expiries are out of order")
    signature = value["signature"]
    if not isinstance(signature, str) or not re.fullmatch(r"[A-Za-z0-9_-]{86}", signature):
        raise ContractError("execution grant: malformed Ed25519 signature")
    try:
        decoded = base64.urlsafe_b64decode(signature + "==")
    except (ValueError, base64.binascii.Error) as exc:
        raise ContractError("execution grant: malformed Ed25519 signature") from exc
    if len(decoded) != 64 or base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=") != signature:
        raise ContractError("execution grant: malformed Ed25519 signature")
    return value


def _trusted_root_file(path: str, *, private: bool) -> None:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not os.path.isabs(path):
        raise ContractError("execution grant keys require absolute POSIX paths without symlinks")
    parent = os.path.dirname(os.path.abspath(path))
    while True:
        try:
            info = os.stat(parent, follow_symlinks=False)
        except OSError as exc:
            raise ContractError("execution grant key directory is unavailable") from exc
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022):
            raise ContractError("execution grant key directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ContractError("execution grant key file is unavailable") from exc
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or (info.st_mode & 0o077 if private else info.st_mode & 0o022)):
            raise ContractError("execution grant key file permissions are unsafe")
    finally:
        os.close(fd)


def _trusted_openssl(path: str) -> str:
    if os.name != "posix" or not os.path.isabs(path):
        raise ContractError("execution grant OpenSSL path must be absolute on POSIX")
    path = os.path.realpath(path)
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise ContractError("execution grant OpenSSL executable is unavailable") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ContractError("execution grant OpenSSL executable is not root-controlled")
    parent = os.path.dirname(path)
    while True:
        try:
            directory = os.stat(parent, follow_symlinks=False)
        except OSError as exc:
            raise ContractError("execution grant OpenSSL directory is unavailable") from exc
        if (not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0
                or directory.st_mode & 0o022):
            raise ContractError("execution grant OpenSSL directory is not root-controlled")
        if parent == "/":
            break
        parent = os.path.dirname(parent)
    return path


def _input_file(data: bytes):
    stream = tempfile.TemporaryFile(mode="w+b")
    stream.write(data)
    stream.flush()
    stream.seek(0)
    return stream


def _openssl_signature(
    openssl_path: str, *, key_path: str, payload: bytes,
    signature: bytes | None = None, private: bool,
) -> bytes | bool:
    executable = _trusted_openssl(openssl_path)
    _trusted_root_file(key_path, private=private)
    data_file = _input_file(payload)
    signature_file = None if private else _input_file(signature or b"")
    try:
        argv = [executable, "pkeyutl", "-sign" if private else "-verify", "-rawin"]
        if not private:
            argv.append("-pubin")
        argv.extend(["-inkey", key_path])
        if private:
            argv.extend(["-in", f"/proc/self/fd/{data_file.fileno()}"])
        else:
            assert signature_file is not None
            argv.extend([
                "-in", f"/proc/self/fd/{data_file.fileno()}",
                "-sigfile", f"/proc/self/fd/{signature_file.fileno()}",
            ])
        inherited = (data_file.fileno(),) if signature_file is None else (
            data_file.fileno(), signature_file.fileno(),
        )
        try:
            result = subprocess.run(
                argv, cwd="/", env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True,
                pass_fds=inherited, timeout=5, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ContractError("execution grant Ed25519 operation is unavailable") from exc
        if private:
            if result.returncode != 0 or len(result.stdout) != 64:
                raise ContractError("execution grant Ed25519 signing failed")
            return result.stdout
        return result.returncode == 0
    finally:
        data_file.close()
        if signature_file is not None:
            signature_file.close()


def sign_execution_grant(
    grant_without_signature: dict[str, Any], *, key_id: str,
    private_key_path: str, openssl_path: str,
) -> dict[str, Any]:
    """Sign using root-owned Ed25519 issuer key; private bytes never enter argv."""
    if not isinstance(grant_without_signature, dict) or "signature" in grant_without_signature:
        raise ContractError("execution grant: signing input must omit signature")
    candidate = {**grant_without_signature, "key_id": _identifier(key_id, "key_id")}
    candidate["signature"] = base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")
    validate_execution_grant(candidate)
    body = {name: value for name, value in candidate.items() if name != "signature"}
    signature_bytes = _openssl_signature(
        openssl_path, key_path=private_key_path,
        payload=EXECUTION_GRANT_LABEL + canonical_bytes(body), private=True,
    )
    assert isinstance(signature_bytes, bytes)
    signature = base64.urlsafe_b64encode(signature_bytes).decode("ascii").rstrip("=")
    result = {**body, "signature": signature}
    validate_execution_grant(result)
    return result


def verify_execution_grant(
    grant: object,
    trusted_keys: Mapping[str, str],
    *,
    audience: str,
    service_generation: str,
    openssl_path: str,
    now: float | None = None,
    max_clock_skew_sec: float = 5.0,
    allow_expired: bool = False,
) -> dict[str, Any]:
    """Verify grant signature, audience, generation, and validity interval.

    The key mapping must come from root-controlled trust configuration. Unknown
    or revoked key IDs fail closed. This check does not replace the Store's
    immediate pre-dispatch authorization and durable pending claim.
    """
    valid = validate_execution_grant(grant)
    if not isinstance(trusted_keys, Mapping):
        raise ContractError("execution grant trust: key registry is invalid")
    key_path = trusted_keys.get(valid["key_id"])
    if not isinstance(key_path, str):
        raise ContractError("execution grant trust: unknown or revoked key id")
    if valid["audience"] != _identifier(audience, "expected audience"):
        raise ContractError("execution grant: audience mismatch")
    if valid["service_generation"] != _identifier(service_generation, "expected service generation"):
        raise ContractError("execution grant: service generation mismatch")
    timestamp = time.time() if now is None else now
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
        raise ContractError("execution grant verification time is invalid")
    if isinstance(max_clock_skew_sec, bool) or not isinstance(max_clock_skew_sec, (int, float)):
        raise ContractError("execution grant clock skew is invalid")
    if not math.isfinite(max_clock_skew_sec) or max_clock_skew_sec < 0:
        raise ContractError("execution grant clock skew is invalid")
    if type(allow_expired) is not bool:
        raise ContractError("execution grant expiry policy is invalid")
    if (valid["issued_at"] > timestamp + max_clock_skew_sec
            or (not allow_expired and valid["expires_at"] <= timestamp)):
        raise ContractError("execution grant is not currently valid")
    body = {name: item for name, item in valid.items() if name != "signature"}
    signature = base64.urlsafe_b64decode(valid["signature"] + "==")
    verified = _openssl_signature(
        openssl_path, key_path=key_path,
        payload=EXECUTION_GRANT_LABEL + canonical_bytes(body),
        signature=signature, private=False,
    )
    if verified is not True:
        raise ContractError("execution grant signature is invalid")
    return dict(valid)


class ExecutionAuthority:
    """One-process admission capability for the manifest runner.

    The trusted service creates this only after verifying the grant against its
    root-owned key ring. ``claim`` rechecks Store authority and inserts the
    one-time PENDING claim; ``claim_status`` resolves only that exact grant
    and generation after an uncertain claim reply; ``reserve`` atomically
    rechecks authority and commits EXECUTION_RESERVED before launch; ``complete``
    persists the exact final receipt. These callbacks are supplied by the
    privileged Supervisor/Store boundary, never by a socket request.
    """

    def __init__(
        self,
        grant: object,
        *,
        daemon_uid: int,
        service_generation: str,
        trusted_keys: Mapping[str, str],
        openssl_path: str,
        audience: str,
        daemon_boundary_check: Any,
        claim: Any,
        claim_status: Any,
        terminalize_no_execution: Any,
        reserve: Any,
        complete: Any,
    ) -> None:
        self.grant = verify_execution_grant(
            grant, trusted_keys, audience=audience,
            service_generation=service_generation, openssl_path=openssl_path,
        )
        if type(daemon_uid) is not int or daemon_uid < 1:
            raise ContractError("execution authority daemon UID is invalid")
        self.daemon_uid = daemon_uid
        self.service_generation = _identifier(service_generation, "service generation")
        if self.grant["service_generation"] != self.service_generation:
            raise ContractError("execution authority generation does not match grant")
        if (not callable(daemon_boundary_check) or not callable(claim)
                or not callable(claim_status) or not callable(terminalize_no_execution)
                or not callable(reserve) or not callable(complete)):
            raise ContractError("execution authority callbacks are invalid")
        self._daemon_boundary_check = daemon_boundary_check
        self._claim = claim
        self._claim_status = claim_status
        self._terminalize_no_execution = terminalize_no_execution
        self._reserve = reserve
        self._complete = complete
        self._claimed = False
        self._reserved = False
        self._completed = False
        self._no_execution_confirmed = False

    @property
    def reservation_confirmed(self) -> bool:
        """Whether this process received exact confirmation before child launch."""
        return self._reserved

    @property
    def completion_confirmed(self) -> bool:
        """Whether the Supervisor confirmed durable COMPLETE for this process."""
        return self._completed

    @property
    def no_execution_confirmed(self) -> bool:
        """Whether the exact claim has a durable terminal pre-spawn disposition."""
        return self._no_execution_confirmed

    @property
    def claim_confirmed(self) -> bool:
        """Whether this process confirmed the exact durable PENDING claim."""
        return self._claimed

    def authorize_and_claim(self, context: object) -> dict[str, Any] | None:
        """Enforce exact binding and return a stored receipt for safe COMPLETE replay."""
        if not isinstance(context, dict) or set(context) != _RUN_CONTEXT_FIELDS:
            raise ContractError("execution authority context does not match the runner contract")
        for field in _RUN_CONTEXT_FIELDS - {"attempt", "epoch", "execution_deadline_sec"}:
            _identifier(context[field], f"context {field}")
        for field in ("manifest_sha256", "model_provenance_sha256"):
            if not _SHA256.fullmatch(context[field]):
                raise ContractError(f"execution authority context {field} is malformed")
        for field in ("attempt", "epoch"):
            if type(context[field]) is not int or context[field] < 1:
                raise ContractError(f"execution authority context {field} is invalid")
        deadline = context["execution_deadline_sec"]
        if type(deadline) is not int or not 1 <= deadline <= MAX_EXECUTION_DEADLINE_SEC:
            raise ContractError("execution authority context deadline is invalid")
        expected = {
            "manifest_sha256": "manifest_sha256", "task_id": "task_id",
            "slot": "slot", "attempt": "attempt", "epoch": "epoch",
            "run_id": "run_id", "invocation_id": "invocation_id",
            "request_id": "request_id", "runner_id": "runner_id",
            "resolved_model": "resolved_model",
            "model_provenance_sha256": "model_provenance_sha256",
            "execution_deadline_sec": "execution_deadline_sec",
            "service_generation": "service_generation",
        }
        for context_field, grant_field in expected.items():
            if context[context_field] != self.grant[grant_field]:
                raise ContractError(f"execution authority {context_field} does not match grant")
        if self._claimed:
            raise ContractError("execution authority has already claimed a run")
        if os.name != "posix" or os.geteuid() != self.daemon_uid:
            raise ContractError("manifest execution is restricted to the configured daemon identity")
        if self._daemon_boundary_check() is not True:
            raise ContractError("manifest execution is outside the configured daemon boundary")
        try:
            result = self._claim(dict(self.grant))
        except Exception as claim_error:
            try:
                status = self._claim_status(dict(self.grant))
            except Exception as status_error:
                raise AmbiguousExecutionAuthorityError(
                    "execution claim outcome is unknown; refusing to launch"
                ) from status_error
            if (not isinstance(status, dict)
                    or status.get("service_generation") != self.service_generation):
                raise AmbiguousExecutionAuthorityError(
                    "execution claim status is not bound to this service generation"
                ) from claim_error
            if (status.get("state") == "NOT_FOUND"
                    and set(status) == {"state", "service_generation"}):
                # Exact current-generation absence proves this grant never
                # established durable claim state; refuse without recycling
                # the service generation.
                raise ContractError("execution claim was not found; refusing to launch") from claim_error
            if status.get("state") == "PENDING" and set(status) == {"state", "service_generation"}:
                # The exact one-time claim committed, but its RPC reply was lost.
                # Only this same still-live generation may advance it to reserve.
                result = None
            elif (status.get("state") == "COMPLETE"
                    and set(status) == {"state", "service_generation", "receipt"}
                    and isinstance(status["receipt"], dict)):
                self._claimed = True
                return dict(status["receipt"])
            else:
                raise AmbiguousExecutionAuthorityError(
                    "execution claim is absent, reserved, or terminal; refusing to reclaim or launch"
                ) from claim_error
        if result is not None and not isinstance(result, dict):
            raise AmbiguousExecutionAuthorityError("execution claim returned an invalid result")
        self._claimed = True
        if result is not None:
            if set(result) != {"state", "receipt"} or result["state"] != "COMPLETE":
                raise AmbiguousExecutionAuthorityError("execution claim returned an unsupported replay state")
            if not isinstance(result["receipt"], dict):
                raise AmbiguousExecutionAuthorityError("stored execution receipt is invalid")
            return dict(result["receipt"])
        return None

    def reserve(self) -> None:
        """Durably reserve the exact grant immediately before its first child launch."""
        if not self._claimed or self._reserved:
            raise ContractError("execution reservation requires one unreserved claim")
        if os.name != "posix" or os.geteuid() != self.daemon_uid:
            raise ContractError("manifest execution is restricted to the configured daemon identity")
        if self._daemon_boundary_check() is not True:
            raise ContractError("manifest execution is outside the configured daemon boundary")
        try:
            result = self._reserve(dict(self.grant))
        except Exception as reserve_error:
            try:
                status = self._claim_status(dict(self.grant))
            except Exception:
                raise AmbiguousExecutionAuthorityError(
                    "execution reservation outcome is unknown; refusing to launch"
                ) from reserve_error
            if (not isinstance(status, dict)
                    or status.get("service_generation") != self.service_generation):
                raise AmbiguousExecutionAuthorityError(
                    "execution reservation status is not generation-bound"
                ) from reserve_error
            # Even if the status proves reservation committed, the lost reserve
            # reply is ambiguous: this process must not infer ownership or spawn.
            raise AmbiguousExecutionAuthorityError(
                f"execution reservation was not confirmed (state={status.get('state')}); refusing to launch"
            ) from reserve_error
        expected_digest = hashlib.sha256(canonical_bytes(self.grant)).hexdigest()
        if (not isinstance(result, dict)
                or set(result) != {"state", "grant_id", "payload_sha256", "service_generation"}
                or result.get("state") != "EXECUTION_RESERVED"
                or result.get("grant_id") != self.grant["grant_id"]
                or result.get("payload_sha256") != expected_digest
                or result.get("service_generation") != self.service_generation):
            raise AmbiguousExecutionAuthorityError(
                "execution reservation response does not match the exact grant"
            )
        # The exact response proves that the durable reservation committed.
        # Any later local boundary failure is therefore an ambiguous reserved
        # run and must trigger the runner service's generation fail-stop.
        self._reserved = True
        if self._daemon_boundary_check() is not True:
            raise AmbiguousExecutionAuthorityError(
                "runner service generation changed after launch reservation"
            )

    def terminalize_no_execution(self, reason_code: str) -> None:
        """Close a claimed run only when this process has not confirmed reservation."""
        if not self._claimed or self._reserved or self._completed:
            raise AmbiguousExecutionAuthorityError(
                "pre-spawn terminalization is unavailable after reservation or without a claim"
            )
        try:
            result = self._terminalize_no_execution(dict(self.grant), reason_code)
        except Exception as terminalize_error:
            try:
                status = self._claim_status(dict(self.grant))
            except Exception as status_error:
                raise AmbiguousExecutionAuthorityError(
                    "pre-spawn terminalization outcome is unknown"
                ) from status_error
            if (not isinstance(status, dict)
                    or status.get("service_generation") != self.service_generation
                    or status.get("state") != "INDETERMINATE"
                    or status.get("reason_code") != reason_code):
                raise AmbiguousExecutionAuthorityError(
                    "pre-spawn terminalization was not confirmed by exact claim status"
                ) from terminalize_error
        else:
            digest = hashlib.sha256(canonical_bytes(self.grant)).hexdigest()
            if (not isinstance(result, dict)
                    or set(result) != {"state", "grant_id", "payload_sha256", "service_generation"}
                    or result.get("state") != "NO_EXECUTION"
                    or result.get("grant_id") != self.grant["grant_id"]
                    or result.get("payload_sha256") != digest
                    or result.get("service_generation") != self.service_generation):
                raise AmbiguousExecutionAuthorityError(
                    "pre-spawn terminal response does not match the exact claim"
                )
        self._no_execution_confirmed = True

    def complete(self, receipt: object) -> None:
        """Persist exactly one receipt after the runner returned a complete result."""
        if not self._reserved:
            raise ContractError("execution cannot complete before its durable launch reservation")
        if not isinstance(receipt, dict):
            raise ContractError("execution completion receipt must be an object")
        self._complete(dict(self.grant), dict(receipt))
        self._completed = True
