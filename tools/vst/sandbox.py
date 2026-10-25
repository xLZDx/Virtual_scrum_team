"""OS-boundary helpers used by the isolated runner and read-only reviewer."""
from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from .contracts import ContractError


_NO_XATTR = frozenset(
    value for value in (getattr(errno, "ENODATA", None), getattr(errno, "ENOATTR", None))
    if value is not None
)
_UNSUPPORTED_XATTR = frozenset(
    value for value in (getattr(errno, "ENOTSUP", None), getattr(errno, "EOPNOTSUPP", None))
    if value is not None
)


def _require_no_extended_acl(
    path: Path, *, include_default_acl: bool = False, follow_symlinks: bool = True
) -> None:
    """Reject POSIX ACL xattrs; ignore only absent ACLs or unsupported ACL xattrs."""
    getxattr = getattr(os, "getxattr", None)
    if getxattr is None:
        raise ContractError("signer IPC ACL inspection is unavailable")
    attributes = ["system.posix_acl_access"]
    if include_default_acl:
        attributes.append("system.posix_acl_default")
    for attribute in attributes:
        try:
            getxattr(path, attribute, follow_symlinks=follow_symlinks)
        except OSError as exc:
            if exc.errno in _NO_XATTR or exc.errno in _UNSUPPORTED_XATTR:
                continue
            raise ContractError("signer IPC ACL inspection failed") from exc
        except (NotImplementedError, TypeError) as exc:
            raise ContractError("signer IPC ACL inspection is unavailable") from exc
        raise ContractError("signer IPC has an extended ACL")


def _require_worker_cannot_replace_entry(
    directory_st: os.stat_result, child_st: os.stat_result, *,
    worker_uid: int, worker_gid: int, runner_uid: int,
) -> None:
    """Reject worker-controlled path components, allowing protected sticky entries."""
    if not stat.S_ISDIR(directory_st.st_mode):
        raise ContractError("signer IPC parent path contains a non-directory")
    if directory_st.st_uid == worker_uid:
        raise ContractError("worker identity owns a signer IPC parent directory")
    mode = stat.S_IMODE(directory_st.st_mode)
    worker_writable = (
        (directory_st.st_gid == worker_gid and bool(mode & stat.S_IWGRP))
        or bool(mode & stat.S_IWOTH)
    )
    if not worker_writable:
        return
    if mode & stat.S_ISVTX and child_st.st_uid == runner_uid:
        return
    raise ContractError("signer IPC path has a worker-writable directory component")


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
    """Require parent/socket mode bits and POSIX ACLs to exclude the worker."""
    if os.name != "posix":
        raise ContractError("signer IPC ACL verification is unavailable")
    socket_file = Path(os.path.abspath(socket_path))
    parent = socket_file.parent
    try:
        lexical_directories = [*reversed(parent.parents), parent]
        resolved_parent = parent.resolve(strict=True)
        resolved_directories = [*reversed(resolved_parent.parents), resolved_parent]
        resolved_socket = resolved_parent / socket_file.name
        socket_st = socket_file.stat(follow_symlinks=False)
        resolved_socket_st = resolved_socket.stat(follow_symlinks=False)
        if (socket_st.st_dev, socket_st.st_ino) != (resolved_socket_st.st_dev, resolved_socket_st.st_ino):
            raise ContractError("signer IPC path changed during inspection")
        for directories, endpoint in (
            (lexical_directories, socket_file),
            (resolved_directories, resolved_socket),
        ):
            for index, directory in enumerate(directories):
                directory_st = directory.stat()
                child = directories[index + 1] if index + 1 < len(directories) else endpoint
                child_st = child.stat(follow_symlinks=False)
                _require_worker_cannot_replace_entry(
                    directory_st, child_st, worker_uid=worker_uid,
                    worker_gid=worker_gid, runner_uid=os.geteuid(),
                )
                _require_no_extended_acl(directory)
        _require_no_extended_acl(parent, include_default_acl=True)
        parent_st = parent.stat()
    except OSError as exc:
        raise ContractError(f"signer IPC is unavailable: {exc}") from exc
    if not stat.S_ISSOCK(socket_st.st_mode):
        raise ContractError("signer IPC endpoint is not a Unix socket")
    _require_no_extended_acl(socket_file, follow_symlinks=False)
    if socket_st.st_mode & (stat.S_IROTH | stat.S_IWOTH):
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
