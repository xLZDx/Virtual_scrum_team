"""OS-boundary helpers used by the isolated runner and read-only reviewer."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from .contracts import ContractError


def current_identity() -> dict[str, int | str]:
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise ContractError("identity inspection requires POSIX credentials")
    return {"uid": os.getuid(), "euid": os.geteuid(), "gid": os.getgid(), "egid": os.getegid()}


def require_distinct_worker_identity(worker_uid: int) -> None:
    if os.name != "posix" or not hasattr(os, "geteuid"):
        raise ContractError("worker identity isolation cannot be proven on this platform")
    if worker_uid == os.geteuid():
        raise ContractError("worker and trusted runner must use distinct OS identities")


def require_worker_cannot_access_signer(socket_path: str, *, worker_uid: int, worker_gid: int) -> None:
    """Require parent/socket mode bits to exclude the worker principal."""
    if os.name != "posix":
        raise ContractError("signer IPC ACL verification is unavailable")
    socket_file = Path(socket_path)
    parent = socket_file.parent
    try:
        parent_st = parent.stat()
        socket_st = socket_file.stat(follow_symlinks=False)
    except OSError as exc:
        raise ContractError(f"signer IPC is unavailable: {exc}") from exc
    if not stat.S_ISSOCK(socket_st.st_mode):
        raise ContractError("signer IPC endpoint is not a Unix socket")
    if parent_st.st_mode & stat.S_IWOTH or socket_st.st_mode & (stat.S_IROTH | stat.S_IWOTH):
        raise ContractError("signer IPC grants access to other identities")
    if worker_uid in (parent_st.st_uid, socket_st.st_uid):
        raise ContractError("worker identity owns signer IPC path")
    if worker_gid in (parent_st.st_gid, socket_st.st_gid):
        raise ContractError("worker primary group can access signer IPC")


def require_runner_can_access_signer(socket_path: str) -> None:
    if os.name != "posix":
        raise ContractError("signer IPC access verification is unavailable")
    socket_file = Path(socket_path)
    try:
        parent_st = socket_file.parent.stat()
        socket_st = socket_file.stat(follow_symlinks=False)
    except OSError as exc:
        raise ContractError(f"signer IPC is unavailable: {exc}") from exc
    groups = set(os.getgroups()) | {os.getegid()}
    if not stat.S_ISSOCK(socket_st.st_mode):
        raise ContractError("signer IPC endpoint is not a Unix socket")
    parent_access = (
        os.geteuid() == parent_st.st_uid and parent_st.st_mode & stat.S_IXUSR
    ) or (parent_st.st_gid in groups and parent_st.st_mode & stat.S_IXGRP)
    if not parent_access:
        raise ContractError("runner cannot traverse signer socket directory")
    socket_access = (
        os.geteuid() == socket_st.st_uid and socket_st.st_mode & stat.S_IWUSR
    ) or (socket_st.st_gid in groups and socket_st.st_mode & stat.S_IWGRP)
    if not socket_access:
        raise ContractError("runner cannot connect to signer socket")


def require_private_key(path: str, *, owner_uid: int | None = None) -> None:
    st = os.stat(path, follow_symlinks=False)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ContractError("key must be a regular non-symlink file")
    if os.name != "posix":
        raise ContractError("key ACL verification is unavailable; refusing to start")
    expected_owner = os.geteuid() if owner_uid is None else owner_uid
    if st.st_uid != expected_owner or stat.S_IMODE(st.st_mode) != 0o600:
        raise ContractError("key must be owned by trusted identity and have mode 0600")


def require_read_only_tree(path: str, *, worker_uid: int | None = None) -> None:
    """Check the credential's effective write bit on every tree entry."""
    root = Path(path)
    if os.name != "posix":
        raise ContractError("read-only reviewer ACL verification is unavailable")
    if os.geteuid() == 0:
        raise ContractError("reviewer must not run as root")
    if worker_uid is not None and (not isinstance(worker_uid, int) or worker_uid == os.geteuid()):
        raise ContractError("reviewer identity must differ from worker identity")
    if not root.exists():
        raise ContractError("read-only resource does not exist")
    if stat.S_ISLNK(root.lstat().st_mode):
        raise ContractError("read-only resource root must not be a symlink")
    entries = [root] if not root.is_dir() else None
    if entries is not None:
        parents = [(root.parent, [], [root.name])]
    else:
        parents = os.walk(root, followlinks=False)
    for parent, dirs, files in parents:
        for name in ([root.name] if entries is not None else [".", *dirs, *files]):
            item = root if entries is not None else (Path(parent) if name == "." else Path(parent) / name)
            st = item.lstat()
            if stat.S_ISLNK(st.st_mode):
                raise ContractError(f"review tree contains symlink: {item}")
            if st.st_uid == os.geteuid() and st.st_mode & stat.S_IWUSR:
                raise ContractError(f"review identity can write tree entry: {item}")
            try:
                writable = os.access(item, os.W_OK, effective_ids=True)
            except (NotImplementedError, TypeError):
                writable = os.access(item, os.W_OK)
            if writable:
                raise ContractError(f"review identity can write tree entry: {item}")


def require_read_only_reviewer(worktree: str, store_path: str, *, worker_uid: int) -> None:
    """Prove reviewer identity differs from worker and cannot mutate either resource."""
    require_read_only_tree(worktree, worker_uid=worker_uid)
    require_read_only_tree(store_path, worker_uid=worker_uid)
