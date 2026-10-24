"""Deterministic digesting for bounded, read-only analyzer snapshots."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from .contracts import ContractError, SOURCE_TREE_SCHEME, canonical_bytes

MAX_SCOPE_FILES = 4096
MAX_SCOPE_BYTES = 64 * 1024 * 1024


def source_tree_sha256(
    snapshot_root: str | os.PathLike[str],
    analysis_scope: list[str],
    *,
    max_total_bytes: int = MAX_SCOPE_BYTES,
) -> str:
    """Hash exact regular files from a trusted immutable snapshot.

    The digest is SHA-256 over canonical JSON containing the versioned scheme
    and a path-sorted list of each file's raw-byte SHA-256 and size. Scope paths
    use forward slashes and cannot traverse, be absolute, or resolve through a
    symbolic link. This function hashes a supplied snapshot; it does not create
    or make that snapshot read-only.
    """
    if not isinstance(analysis_scope, list) or not analysis_scope:
        raise ContractError("analysis_scope: must be a non-empty list")
    if len(analysis_scope) > MAX_SCOPE_FILES:
        raise ContractError(f"analysis_scope: exceeds {MAX_SCOPE_FILES} files")
    if not isinstance(max_total_bytes, int) or isinstance(max_total_bytes, bool):
        raise ContractError("max_total_bytes: must be an integer")
    if max_total_bytes < 1 or max_total_bytes > MAX_SCOPE_BYTES:
        raise ContractError(f"max_total_bytes: must be between 1 and {MAX_SCOPE_BYTES}")
    if any(not isinstance(path, str) or not path for path in analysis_scope):
        raise ContractError("analysis_scope: paths must be non-empty strings")
    if len(set(analysis_scope)) != len(analysis_scope):
        raise ContractError("analysis_scope: duplicate paths are not allowed")

    root = Path(snapshot_root)
    try:
        if root.is_symlink():
            raise ContractError("snapshot_root: symbolic links are not allowed")
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ContractError(f"snapshot_root: cannot resolve ({type(exc).__name__})") from exc
    if not resolved_root.is_dir():
        raise ContractError("snapshot_root: must be a directory")

    total_bytes = 0
    records: list[dict[str, Any]] = []
    for index, path in enumerate(sorted(analysis_scope)):
        if (path != path.strip() or "\\" in path or path.startswith("/") or
                ":" in path or any(char in path for char in "*?[]")):
            raise ContractError(f"analysis_scope[{index}]: must be a normalized relative path")
        parts = path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ContractError(f"analysis_scope[{index}]: invalid path segment")
        target = resolved_root.joinpath(*parts)
        cursor = resolved_root
        try:
            for part in parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ContractError(f"analysis_scope[{index}]: symbolic link is not allowed")
            resolved_target = target.resolve(strict=True)
            if resolved_root not in resolved_target.parents:
                raise ContractError(f"analysis_scope[{index}]: path escapes the snapshot")
            before = resolved_target.stat(follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise ContractError(f"analysis_scope[{index}]: must name a regular file")
            total_bytes += before.st_size
            if total_bytes > max_total_bytes:
                raise ContractError(f"analysis_scope: exceeds {max_total_bytes} bytes")
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            descriptor = os.open(resolved_target, flags)
            try:
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode) or (
                    opened.st_dev, opened.st_ino, opened.st_size
                ) != (before.st_dev, before.st_ino, before.st_size):
                    raise ContractError(f"analysis_scope[{index}]: file changed during open")
                digest = hashlib.sha256()
                read_bytes = 0
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    read_bytes += len(chunk)
                    if read_bytes > max_total_bytes:
                        raise ContractError(f"analysis_scope: exceeds {max_total_bytes} bytes")
                    digest.update(chunk)
                after = os.fstat(descriptor)
                if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
                    opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns
                ) or read_bytes != opened.st_size:
                    raise ContractError(f"analysis_scope[{index}]: file changed while hashing")
            finally:
                os.close(descriptor)
        except ContractError:
            raise
        except (OSError, RuntimeError) as exc:
            raise ContractError(
                f"analysis_scope[{index}]: cannot hash ({type(exc).__name__})"
            ) from exc
        records.append({"path": path, "size": read_bytes, "sha256": digest.hexdigest()})

    payload = {"scheme": SOURCE_TREE_SCHEME, "files": records}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
