"""External event anchoring and lifecycle transition contracts (stdlib only)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from typing import Protocol

from .contracts import canonical_bytes
from .signing import MIN_KEY_BYTES

CHECKPOINT_LABEL = b"vst-external-checkpoint-v1\0"
_anchor_lock = threading.Lock()


class AnchorError(Exception):
    """An unavailable, invalid, or conflicting external checkpoint."""


class ExternalAnchor(Protocol):
    def read_latest(self) -> dict | None: ...
    def compare_and_append(self, expected: dict | None, checkpoint: dict) -> dict: ...


def signed_checkpoint(count: int, head: str, event_key: bytes) -> dict:
    body = {"count": count, "head": head}
    mac = hmac.new(event_key, CHECKPOINT_LABEL + canonical_bytes(body), hashlib.sha256).hexdigest()
    return {**body, "signature": mac}


def verify_checkpoint(checkpoint: dict, event_key: bytes) -> bool:
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"count", "head", "signature"}:
        return False
    count, head, signature = checkpoint["count"], checkpoint["head"], checkpoint["signature"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return False
    if not isinstance(head, str) or len(head) != 64 or not isinstance(signature, str):
        return False
    expected = signed_checkpoint(count, head, event_key)["signature"]
    return hmac.compare_digest(signature, expected)


class FileExternalAnchor:
    """Append-only JSONL anchor file; configure its path outside the worker mount."""

    def __init__(self, path: str, event_key: bytes):
        if not isinstance(path, str) or not path:
            raise ValueError("anchor path must be a non-empty string")
        if not isinstance(event_key, (bytes, bytearray)) or len(event_key) < MIN_KEY_BYTES:
            raise ValueError("event_key must be bytes of length >= 32")
        self.path = os.path.abspath(path)
        self._key = bytes(event_key)

    def read_latest(self) -> dict | None:
        try:
            with open(self.path, "rb") as stream:
                lines = stream.read().splitlines()
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise AnchorError(f"external anchor unavailable: {exc}") from exc
        latest = None
        for index, line in enumerate(lines, 1):
            try:
                item = json.loads(line)
            except (ValueError, TypeError) as exc:
                raise AnchorError(f"malformed external checkpoint at line {index}") from exc
            if not verify_checkpoint(item, self._key):
                raise AnchorError(f"invalid external checkpoint at line {index}")
            if latest is not None and item["count"] != latest["count"] + 1:
                raise AnchorError("external checkpoint count is not strictly consecutive")
            latest = item
        return latest

    def compare_and_append(self, expected: dict | None, checkpoint: dict) -> dict:
        if not verify_checkpoint(checkpoint, self._key):
            raise AnchorError("refusing unsigned or invalid checkpoint")
        with _anchor_lock:
            latest = self.read_latest()
            if latest == checkpoint:
                return latest
            if latest != expected:
                if latest is not None and latest["count"] == checkpoint["count"]:
                    raise AnchorError("same checkpoint count has a different head")
                raise AnchorError("external checkpoint compare-and-append conflict")
            wanted_count = 0 if expected is None else expected["count"] + 1
            if checkpoint["count"] != wanted_count:
                raise AnchorError("checkpoint is not the immediate successor")
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            try:
                with open(self.path, "a+b") as stream:
                    os.chmod(self.path, 0o600)
                    if os.name == "nt":
                        import msvcrt

                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                        unlock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                        unlock = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                    try:
                        latest = self.read_latest()
                        if latest == checkpoint:
                            return latest
                        if latest != expected:
                            if latest is not None and latest["count"] == checkpoint["count"]:
                                raise AnchorError("same checkpoint count has a different head")
                            raise AnchorError("external checkpoint compare-and-append conflict")
                        stream.seek(0, os.SEEK_END)
                        stream.write(canonical_bytes(checkpoint) + b"\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                    finally:
                        unlock()
            except OSError as exc:
                raise AnchorError(f"external checkpoint append failed: {exc}") from exc
            return checkpoint


# S7.1: table is data as well as documentation. Unknown pairs are rejected.
STOP_TRANSITIONS = {
    ("RUNNING", "STOP"): {
        "next_state": "STOPPING", "cleanup_action": "terminate process group", "trigger": "supervisor",
    },
    ("STOPPING", "CLEANUP_COMPLETE"): {
        "next_state": "STOPPED", "cleanup_action": "release lease", "trigger": "supervisor",
    },
    ("STOPPED", "RESUME"): {
        "next_state": "READY", "cleanup_action": "increment epoch and require fresh receipt", "trigger": "supervisor",
    },
    ("RUNNING", "ROLLBACK"): {
        "next_state": "ROLLING_BACK", "cleanup_action": "restore scoped worktree snapshot", "trigger": "supervisor",
    },
    ("ROLLING_BACK", "CLEANUP_COMPLETE"): {
        "next_state": "STOPPED", "cleanup_action": "release lease", "trigger": "supervisor",
    },
    ("READY", "START"): {
        "next_state": "RUNNING", "cleanup_action": "start isolated worker", "trigger": "supervisor",
    },
}


def transition(state: str, event: str) -> tuple[str, str]:
    try:
        row = STOP_TRANSITIONS[(state, event)]
        if row["trigger"] != "supervisor":
            raise ValueError("transition trigger is not the supervisor")
        return row["next_state"], row["cleanup_action"]
    except KeyError as exc:
        raise ValueError(f"unsupported lifecycle transition: {state!r} + {event!r}") from exc
