"""Deterministic, fail-closed path and patch gate for worker changes."""
from __future__ import annotations

import hashlib
import os
import re
from typing import Iterable

from .contracts import ContractError
from .signing import sign

DIFF_GATE_LABEL = b"vst-diff-gate-v2\0"
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_BLOCKED_PARTS = {".git", ".github", ".hooks", "hooks", ".husky"}
_BLOCKED_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "poetry.lock", "uv.lock", "pipfile.lock", "requirements.lock"}
_BLOCKED_PREFIXES = (".github/", ".gitlab/", ".circleci/", ".buildkite/", "hooks/", ".husky/")
_BLOCKED_SUFFIXES = (".lock", ".lockb")


def normalize_path(path: str) -> str:
    if not isinstance(path, str) or not path or "\0" in path:
        raise ContractError("diff path must be a non-empty string")
    value = path.replace("\\", "/")
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ContractError("diff path must be repository-relative")
    parts = value.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ContractError("diff path contains traversal or empty components")
    return "/".join(parts)


def is_blocked_path(path: str) -> bool:
    lower = path.lower()
    parts = set(lower.split("/"))
    name = lower.rsplit("/", 1)[-1]
    return bool(
        parts & _BLOCKED_PARTS
        or lower.startswith(_BLOCKED_PREFIXES)
        or name in _BLOCKED_NAMES
        or name.endswith(_BLOCKED_SUFFIXES)
        or name in {"dockerfile", "install.sh", "install.ps1", "setup.py", "setup.cfg", "pyproject.toml"}
        or name.startswith("dockerfile.")
    )


def check_diff(
    *, manifest_sha256: str, base_head: str, candidate_head: str,
    changed_paths: Iterable[str], allowed_paths: Iterable[str], diff_bytes: bytes,
    symlink_paths: Iterable[str] = (), rename_pairs: Iterable[tuple[str, str]] = (),
) -> dict:
    """Return reproducible PASS/FAIL evidence; every path failure is a FAIL."""
    if not isinstance(manifest_sha256, str) or not _HEX64.fullmatch(manifest_sha256):
        raise ContractError("manifest_sha256 must be lowercase SHA-256")
    if not isinstance(base_head, str) or not _HEX40.fullmatch(base_head):
        raise ContractError("base_head must be a lowercase git object id")
    if not isinstance(candidate_head, str) or not _HEX40.fullmatch(candidate_head):
        raise ContractError("candidate_head must be a lowercase git object id")
    if not isinstance(diff_bytes, bytes):
        raise ContractError("diff_bytes must be bytes")
    try:
        changed = sorted({normalize_path(path) for path in changed_paths})
        allowed = {normalize_path(path) for path in allowed_paths}
        symlinks = {normalize_path(path) for path in symlink_paths}
        renames = [(normalize_path(a), normalize_path(b)) for a, b in rename_pairs]
    except (TypeError, ValueError) as exc:
        raise ContractError(f"invalid diff path evidence: {exc}") from exc
    reason = "PASS"
    if symlinks:
        reason = "SYMLINK_CHANGE"
    elif any(src in allowed and is_blocked_path(dst) for src, dst in renames):
        reason = "RENAME_INTO_BLOCKED_PATH"
    elif any(is_blocked_path(path) and path not in allowed for path in changed):
        reason = "BLOCKED_PATH_CLASS"
    elif any(path not in allowed for path in changed):
        reason = "OUT_OF_SCOPE_PATH"
    return {
        "manifest_sha256": manifest_sha256,
        "candidate_head": candidate_head,
        "diff_sha256": hashlib.sha256(diff_bytes).hexdigest(),
        "changed_paths": changed,
        "verdict": "PASS" if reason == "PASS" else "FAIL",
        "reason": reason,
    }


def sign_diff_evidence(evidence: dict, runner_key: bytes) -> dict:
    fields = {"manifest_sha256", "candidate_head", "diff_sha256", "changed_paths", "verdict", "reason"}
    if not isinstance(evidence, dict) or set(evidence) != fields:
        raise ContractError("diff evidence fields do not match contract")
    signed = dict(evidence)
    signed["signature"] = sign(evidence, runner_key, DIFF_GATE_LABEL)
    return signed


def git_diff_evidence(repo: str, manifest: dict, candidate_head: str, diff_bytes: bytes, changed_paths: Iterable[str], *, symlink_paths: Iterable[str] = (), rename_pairs: Iterable[tuple[str, str]] = ()) -> dict:
    """Bind a caller-collected deterministic diff to manifest scope and heads."""
    scope = manifest.get("change_scope")
    if not isinstance(scope, dict) or set(scope) != {"allowed_paths"}:
        raise ContractError("manifest change_scope is missing or malformed")
    from .contracts import manifest_sha256
    return check_diff(
        manifest_sha256=manifest_sha256(manifest), base_head=manifest.get("base_head"),
        candidate_head=candidate_head, changed_paths=changed_paths,
        allowed_paths=scope["allowed_paths"], diff_bytes=diff_bytes,
        symlink_paths=symlink_paths, rename_pairs=rename_pairs,
    )
