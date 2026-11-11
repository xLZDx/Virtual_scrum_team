"""U6-1: rollback exercise (proves that a rollback restores the exact pre-change tree).

The runbook (docs/sdlc/u6/RUNBOOK.md) says a rollback is only trusted after it was exercised. This helper does
the exercise on a directory tree: snapshot, apply a caller-supplied change, snapshot, run a caller-supplied
rollback, snapshot, and compare. It makes one claim and nothing stronger: the file contents and relative paths
under `root` after the rollback hash to the same value as before the change, and the change did alter them.

Snapshot hash (deterministic, documented so a test can restate it): SHA-256 over every regular file under `root`,
excluding any entry named `.git` (file or directory, at any depth), in the order of the sorted relative POSIX
paths (plain string order). Per file the hashed bytes are
`<path as UTF-8> 0x00 <decimal byte length> 0x00 <file bytes>`. Empty directories, timestamps, permissions and
line-ending conversions are not part of the hash: bytes are hashed as they are on disk.

Fail closed, no raise for expected failures: a root that is not a directory, an unreadable tree, a symlink or other
non-regular entry, a non-callable argument, an exception in the change or in the rollback, a change that changed
nothing and a rollback that left a different tree all give a result with `rollback_proven` False and an error code.
Exception messages are never echoed (only the exception type name), because they may hold file content or paths.
`KeyboardInterrupt` and `SystemExit` are not caught. The helper reads and writes nothing itself and uses no
network; the callables may do anything, so run them only against a scratch copy.

Standard library only. Details: docs/sdlc/u6/RUNBOOK.md.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# error codes
ROOT_NOT_DIRECTORY = "ROOT_NOT_DIRECTORY"
BAD_CALLABLE = "BAD_CALLABLE"
SNAPSHOT_FAILED = "SNAPSHOT_FAILED"
CHANGE_FAILED = "CHANGE_FAILED"
CHANGE_NO_EFFECT = "CHANGE_NO_EFFECT"
ROLLBACK_FAILED = "ROLLBACK_FAILED"
ROLLBACK_INCOMPLETE = "ROLLBACK_INCOMPLETE"

GIT_DIR_NAME = ".git"
_HEX64 = frozenset("0123456789abcdef")


class _SnapshotError(Exception):
    """Internal: the tree cannot be hashed safely."""


def _is_hash(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX64


@dataclass(frozen=True)
class RollbackExerciseResult:
    """Outcome of `exercise_rollback`. `rollback_proven` is True only when no error code is set, the snapshot
    after the rollback equals the snapshot before the change, and the snapshot after the change differs."""

    snapshot_before: str | None
    snapshot_after_change: str | None
    snapshot_after_rollback: str | None
    rollback_proven: bool
    error_code: str | None = None
    error_detail: str | None = None

    def __post_init__(self) -> None:
        for name in ("snapshot_before", "snapshot_after_change", "snapshot_after_rollback"):
            value = getattr(self, name)
            if value is not None and not _is_hash(value):
                raise ValueError(f"{name} must be None or 64 lowercase hex characters")
        if type(self.rollback_proven) is not bool:
            raise ValueError("rollback_proven must be a bool")
        if self.rollback_proven:
            if (self.error_code is not None or self.snapshot_before is None
                    or self.snapshot_after_change is None or self.snapshot_after_rollback is None
                    or self.snapshot_before != self.snapshot_after_rollback
                    or self.snapshot_after_change == self.snapshot_before):
                raise ValueError("a proven rollback needs three snapshots, before == after_rollback, "
                                 "after_change != before and no error")
        elif self.error_code is None:
            raise ValueError("a result that is not proven must carry an error code")

    def to_dict(self) -> dict:
        return {
            "snapshot_before": self.snapshot_before, "snapshot_after_change": self.snapshot_after_change,
            "snapshot_after_rollback": self.snapshot_after_rollback, "rollback_proven": self.rollback_proven,
            "error_code": self.error_code, "error_detail": self.error_detail,
        }


def _walk_files(root: Path) -> list[tuple[str, Path]]:
    """(relative POSIX path, absolute path) of every regular file, `.git` excluded, sorted by the relative path."""
    found: list[tuple[str, Path]] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(current)
        kept = []
        for name in dirnames:
            if name == GIT_DIR_NAME:
                continue
            if (here / name).is_symlink():
                raise _SnapshotError("a directory link is not allowed in the tree")
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            if name == GIT_DIR_NAME:
                continue
            path = here / name
            if path.is_symlink() or not path.is_file():
                raise _SnapshotError("a link or a non-regular file is not allowed in the tree")
            found.append((path.relative_to(root).as_posix(), path))
    found.sort(key=lambda item: item[0])
    return found


def snapshot_hash(root: str | os.PathLike) -> str:
    """Deterministic SHA-256 of the tree under `root` (format in the module docstring).

    Raises NotADirectoryError when `root` is not a directory and OSError or ValueError when the tree cannot be read
    or holds a link; `exercise_rollback` turns every one of them into an error code.
    """
    base = Path(root)
    if not base.is_dir():
        raise NotADirectoryError("root is not a directory")
    digest = hashlib.sha256()
    try:
        for relative, path in _walk_files(base):
            data = path.read_bytes()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\x00")
            digest.update(str(len(data)).encode("ascii"))
            digest.update(b"\x00")
            digest.update(data)
    except _SnapshotError as exc:
        raise ValueError(str(exc)) from None
    return digest.hexdigest()


def _failure(code: str, detail: str, before: str | None = None, changed: str | None = None,
             rolled: str | None = None) -> RollbackExerciseResult:
    return RollbackExerciseResult(before, changed, rolled, False, code, detail)


def _snap(root: Path) -> tuple[str | None, str | None]:
    """(hash, None) or (None, detail); never raises."""
    try:
        return snapshot_hash(root), None
    except (OSError, ValueError) as exc:
        return None, f"the tree could not be hashed ({type(exc).__name__})"
    except Exception as exc:  # noqa: BLE001 - fail closed
        return None, f"the tree could not be hashed ({type(exc).__name__})"


def exercise_rollback(root: str | os.PathLike, change: Callable[[Path], object],
                      rollback: Callable[[Path], object]) -> RollbackExerciseResult:
    """Run `change(root)` then `rollback(root)` and report whether the tree is byte-identical to the start.

    Both callables receive `root` as a `pathlib.Path`. Order: snapshot, change, snapshot, rollback, snapshot.
    The rollback is run only after a change that raised nothing and altered the tree; when the change raises or
    changes nothing, the result is not proven and the rollback callable is NOT called (the tree may then be left
    in a half-changed state: restore it with the real rollback procedure). Never raises for these expected failures.
    """
    try:
        base = Path(root)
        is_dir = base.is_dir()
    except Exception:  # noqa: BLE001 - not a path at all
        return _failure(ROOT_NOT_DIRECTORY, "root is not a usable path")
    if not is_dir:
        return _failure(ROOT_NOT_DIRECTORY, "root is not an existing directory")
    if not callable(change) or not callable(rollback):
        return _failure(BAD_CALLABLE, "change and rollback must be callable")

    before, problem = _snap(base)
    if before is None:
        return _failure(SNAPSHOT_FAILED, "before the change: " + str(problem))

    try:
        change(base)
    except Exception as exc:  # noqa: BLE001 - the change is caller code
        return _failure(CHANGE_FAILED, f"the change raised {type(exc).__name__}; the rollback was not run", before)

    changed, problem = _snap(base)
    if changed is None:
        return _failure(SNAPSHOT_FAILED, "after the change: " + str(problem), before)
    if changed == before:
        return _failure(CHANGE_NO_EFFECT, "the change did not alter the tree, so a rollback proves nothing",
                        before, changed)

    try:
        rollback(base)
    except Exception as exc:  # noqa: BLE001 - the rollback is caller code
        return _failure(ROLLBACK_FAILED, f"the rollback raised {type(exc).__name__}; the tree may still be changed",
                        before, changed)

    rolled, problem = _snap(base)
    if rolled is None:
        return _failure(SNAPSHOT_FAILED, "after the rollback: " + str(problem), before, changed)
    if rolled != before:
        return _failure(ROLLBACK_INCOMPLETE, "the tree after the rollback differs from the tree before the change",
                        before, changed, rolled)
    return RollbackExerciseResult(before, changed, rolled, True)
