"""Read-only Git snapshot validation and durable namespace transaction primitives.

This module is embedded by the root-side S2 applier only after its exact Git blob
and SHA-256 have been checked. It never removes a candidate, predecessor, journal,
or marker; ambiguous recovery state is intentionally preserved for an explicit
recovery invocation.
"""
from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

TASK_HEAD = "67361bb4aa23355d9a6bc7877a987ba688559eda"
TASK_TREE = "0c4a8440a38027563d2455024af6b58072fe3b57"
TASK_OBJECT_COUNT = 804
TASK_PACK_SHA256 = "2ce52ec7dfd3b1eb16c0704f133b491e8c571753ba8e3f6c9bfc931dd0328bd3"
TASK_PACK_BYTES = 2_666_915
EXPECTED_PREDECESSOR_HEAD = "a600774649527ff0b33eb81f4d431f8226119b2c"
TASK_REPOSITORY_ROOT = "/var/lib/vst-runner/repository"
PREINSTALLED_GUARD_PATHS = {
    "/etc/systemd/system/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    "/etc/systemd/system/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
}
CONFIGURATION_PATHS = frozenset({
    "/etc/systemd/system/vst-assignment-bootstrap.service",
    "/etc/systemd/system/vst-dispatch-issuer.service",
    "/etc/systemd/system/vst-dispatcher.service.d/90-s2-snapshot-recovery-guard.conf",
    "/etc/systemd/system/vst-runner.service.d/90-s2-host-path-mask.conf",
    "/etc/systemd/system/vst-runner.service.d/90-s2-snapshot-recovery-guard.conf",
    "/etc/systemd/system/vst-runner.service.d/rate-limits.conf",
    "/etc/systemd/system/vst-sandbox-probe.service",
    "/etc/systemd/system/vst-sandbox-probe.service.d/90-s2-host-path-mask.conf",
    "/etc/systemd/system/vst-signer.service.d/rate-limits.conf",
    "/etc/systemd/system/vst-supervisor.service.d/rate-limits.conf",
    "/etc/vst-runner/assignment-delegation-policy.json",
    "/etc/vst-runner/bootstrap-request.json",
    "/etc/vst-runner/dispatch-instruction-public.pem",
    "/etc/vst-runner/dispatch-instruction-trust.json",
    "/etc/vst-runner/dispatch-owner-service.json",
    "/etc/vst-runner/dispatcher-service.json",
    "/etc/vst-runner/execution-grant-public.pem",
    "/etc/vst-runner/fence.json",
    "/etc/vst-runner/model-provenance.json",
    "/etc/vst-runner/network-profile.json",
    "/etc/vst-runner/probe-entrypoint.py",
    "/etc/vst-runner/reviewer-registry.json",
    "/etc/vst-runner/reviewer-use-policy.json",
    "/etc/vst-runner/runner-service.json",
    "/etc/vst-runner/signer-service.json",
    "/etc/vst-runner/supervisor-service.json",
    "/etc/vst-runner/task-manifest.json",
})
RUNTIME_PATHS = {
    "repository_root": TASK_REPOSITORY_ROOT,
    "private_root": "/var/lib/vst-runner/private",
    "journal_root": "/var/lib/vst-runner/private/snapshot-transactions",
    "marker_path": "/var/lib/vst-runner/private/snapshot-transaction-incomplete.json",
    "recovery_prefix": "/var/lib/vst-runner/repository-recovery-",
}
TASK_BASE_HEAD = "67361bb4aa23355d9a6bc7877a987ba688559eda"
MAX_PACK_BYTES = 8 * 1024 * 1024
MAX_JOURNAL_BYTES = 4 * 1024 * 1024
RUNNER_FENCE_BOOTSTRAP_COMMIT = "ee69f9fbf074a4c73d2d5d1da81c627a57d06071"
RUNNER_FENCE_SOURCE_SHA256 = "32c682eddb78747b91e319cee365e2e12c54edda3096316992e5d0fe025d67ab"
RUNNER_CONTRACTS_SOURCE_SHA256 = "bf01d990a94cd71887f8d9f81019333f3bf43d5950a655de3646e9bb3d585ea4"
_FENCE_CONFIG = "/etc/vst-runner/fence.json"
_FENCE_LEDGER = "/var/lib/vst-runner/private/fence-ledger.json"
_FENCE_GENERATION = "/var/lib/vst-runner/generation.json"
_STORE_PATH = "/var/lib/vst-runner/private/store.sqlite3"
_ROLE_UNITS = ("vst-runner.service", "vst-dispatcher.service")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TRANSITIONS = {
    "GUARDS_VERIFIED": {"RECOVERY_REQUIRED"},
    "MARKER_DURABLE": {"FENCING", "RECOVERY_REQUIRED"},
    "FENCING": {"FENCED", "RECOVERY_REQUIRED"},
    "FENCED": {"DISPATCHER_DRAINED", "RECOVERY_REQUIRED"},
    "DISPATCHER_DRAINED": {"RUNNER_STOPPED_EMPTY", "RUNNER_BOOTSTRAP_EMPTY", "RECOVERY_REQUIRED"},
    "RUNNER_STOPPED_EMPTY": {"EXCHANGED", "RECOVERY_REQUIRED"},
    "RUNNER_BOOTSTRAP_EMPTY": {"EXCHANGED", "RECOVERY_REQUIRED"},
    "EXCHANGED": {"OLD_RETAINED", "RECOVERY_REQUIRED", "ROLLBACK_EXCHANGED"},
    "OLD_RETAINED": {"TARGET_VERIFIED", "RECOVERY_REQUIRED", "ROLLBACK_EXCHANGED"},
    "TARGET_VERIFIED": {"ACTIVATION_READY", "RECOVERY_REQUIRED", "ROLLBACK_EXCHANGED"},
    "ROLLBACK_EXCHANGED": {"ACTIVATION_READY", "RECOVERY_REQUIRED"},
    "MARKER_CLEARED": {"ACTIVATION_RESTORED", "RECOVERY_REQUIRED"},
    "ACTIVATION_READY": {"MARKER_CLEARED", "RECOVERY_REQUIRED"},
    "RECOVERY_REQUIRED": {"ACTIVATION_READY", "ROLLBACK_EXCHANGED", "FENCING"},
}
_TRANSACTION_FIELDS = {
    "transaction_id", "deployment_commit", "task_source_head", "task_source_tree_sha1",
    "live_path", "stage_path", "old_device", "old_inode", "old_head", "old_tree_sha1", "old_mode",
    "candidate_device", "candidate_inode", "candidate_readonly_git_proof",
    "activation_state", "configuration_state",
    "journal_path", "journal_root", "private_root", "marker_path", "recovery_prefix", "format",
}


class SnapshotContractError(RuntimeError):
    pass


def _run(argv: list[str], *, cwd: str | None = None, input_bytes: bytes | None = None,
         user: tuple[int, int] | None = None) -> bytes:
    def demote() -> None:
        if user is not None:
            os.setgroups([])
            os.setgid(user[1])
            os.setuid(user[0])

    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_")}
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    result = subprocess.run(
        argv, cwd=cwd, input=input_bytes, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=30,
        preexec_fn=demote if user is not None and os.geteuid() == 0 else None,
        env=environment,
    )
    if result.returncode:
        raise SnapshotContractError("read-only Git verification failed: " + " ".join(argv[:3]))
    return result.stdout


def _git_output(root: str, *args: str, user: tuple[int, int] | None = None) -> str:
    return _run(["/usr/bin/git", "-C", root, "--no-replace-objects", *args],
                user=user).decode("ascii").strip()


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SnapshotContractError("snapshot contains a linked or non-regular file")
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)
    finally:
        os.close(fd)


def _tree_identity(root: str) -> tuple[str, str, str]:
    worker = (997, 988)
    head = _git_output(root, "rev-parse", "--verify", "HEAD", user=worker)
    tree = _git_output(root, "rev-parse", "--verify", "HEAD^{tree}", user=worker)
    shallow = _git_output(root, "rev-parse", "--is-shallow-repository", user=worker)
    if not _HEX40.fullmatch(head) or not _HEX40.fullmatch(tree) or shallow != "true":
        raise SnapshotContractError("staged snapshot is not the exact shallow Git repository")
    return head, tree, shallow


def _inventory(root: str) -> dict[str, tuple[str, int, int]]:
    result: dict[str, tuple[str, int, int]] = {}
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories.sort()
        files.sort()
        for name in directories + files:
            path = os.path.join(current, name)
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_gid != 0:
                raise SnapshotContractError("snapshot contains a link or non-root-owned path")
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            digest = _hash_file(path) if stat.S_ISREG(info.st_mode) else "directory"
            result[relative] = (digest, info.st_size, stat.S_IMODE(info.st_mode))
    return result


def validate_pack(snapshot: dict[str, Any]) -> bytes:
    if (snapshot.get("head") != TASK_HEAD or snapshot.get("tree_sha1") != TASK_TREE
            or snapshot.get("format") != "git-pack-shallow-v1"
            or snapshot.get("object_count") != TASK_OBJECT_COUNT
            or snapshot.get("shallow_commits") != [TASK_HEAD]
            or snapshot.get("sha256") != TASK_PACK_SHA256
            or snapshot.get("size") != TASK_PACK_BYTES):
        raise SnapshotContractError("task-source pack identity differs from the fixed contract")
    import base64
    try:
        packed = base64.b64decode(snapshot.get("pack_b64", ""), validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise SnapshotContractError("task-source pack encoding is malformed") from exc
    if (len(packed) > MAX_PACK_BYTES or len(packed) != TASK_PACK_BYTES
            or not packed.startswith(b"PACK")
            or hashlib.sha256(packed).hexdigest() != TASK_PACK_SHA256):
        raise SnapshotContractError("task-source pack bytes differ from the fixed contract")
    return packed


def _verify_git_readonly(root: str) -> dict[str, Any]:
    before = _inventory(root)
    head, tree, shallow = _tree_identity(root)
    if head != TASK_HEAD or tree != TASK_TREE:
        raise SnapshotContractError("Git snapshot HEAD/tree differs from the pinned task source")
    status = _git_output(root, "status", "--porcelain=v1", user=(997, 988))
    diff = _run(["/usr/bin/git", "-C", root, "--no-replace-objects", "diff", "--binary",
                 "--find-renames", TASK_BASE_HEAD],
                user=(997, 988))
    untracked = _git_output(root, "ls-files", "--others", "--exclude-standard", user=(997, 988))
    ignored = _git_output(root, "ls-files", "--others", "--ignored", "--exclude-standard", user=(997, 988))
    if status or diff or untracked or ignored:
        raise SnapshotContractError("read-only worker Git checks found changes or untracked content")
    after = _inventory(root)
    if before != after:
        raise SnapshotContractError("worker Git checks mutated the complete staged snapshot")
    return {"head": head, "tree_sha1": tree, "shallow": shallow,
            "inventory_sha256": hashlib.sha256(json.dumps(
                sorted((key, *value) for key, value in after.items()),
                separators=(",", ":")).encode("utf-8")).hexdigest(),
            "worker_uid": 997, "worker_gid": 988, "status_clean": True, "diff_empty": True,
            "untracked_empty": True, "ignored_empty": True}


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        count = os.write(fd, view)
        if count <= 0:
            raise SnapshotContractError("durable transaction write made no progress")
        view = view[count:]


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _unique_json(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SnapshotContractError("transaction metadata contains a duplicate field")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise SnapshotContractError("transaction metadata is not a JSON object")
    return value


def _read_journal(journal_path: str) -> list[dict[str, Any]]:
    fd = os.open(journal_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_JOURNAL_BYTES):
            raise SnapshotContractError("transaction journal metadata is unsafe")
        raw = bytearray()
        while len(raw) <= MAX_JOURNAL_BYTES:
            part = os.read(fd, min(65536, MAX_JOURNAL_BYTES + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
    finally:
        os.close(fd)
    if not raw or len(raw) > MAX_JOURNAL_BYTES or not raw.endswith(b"\n"):
        raise SnapshotContractError("transaction journal is empty, oversized or has a partial tail")
    records: list[dict[str, Any]] = []
    previous = "0" * 64
    for sequence, line in enumerate(bytes(raw).splitlines(), start=1):
        record = _unique_json(line)
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        if (record.get("sequence") != sequence
                or record.get("previous_record_sha256") != previous
                or record.get("record_sha256") != digest
                or not isinstance(record.get("transaction_id"), str)
                or not isinstance(record.get("state"), str)):
            raise SnapshotContractError("transaction journal hash chain or sequence is invalid")
        records.append(record)
        previous = digest
    return records


def _append_journal(journal_path: str, transaction: dict[str, Any], state: str,
                    **facts: Any) -> dict[str, Any]:
    try:
        records = _read_journal(journal_path)
    except FileNotFoundError:
        records = []
    previous = records[-1]["record_sha256"] if records else "0" * 64
    immutable = {key: transaction[key] for key in _TRANSACTION_FIELDS if key in transaction}
    if set(immutable) != _TRANSACTION_FIELDS:
        raise SnapshotContractError("transaction journal base identity is incomplete")
    body = {**immutable, **facts, "state": state, "sequence": len(records) + 1,
            "previous_record_sha256": previous,
            "recorded_at": datetime.now(timezone.utc).isoformat()}
    record = {**body, "record_sha256": hashlib.sha256(_canonical(body)).hexdigest()}
    encoded = _canonical(record) + b"\n"
    if len(encoded) + (os.path.getsize(journal_path) if os.path.exists(journal_path) else 0) > MAX_JOURNAL_BYTES:
        raise SnapshotContractError("transaction journal exceeds its fixed size limit")
    parent = os.path.dirname(journal_path)
    temporary = os.path.join(parent, ".journal-next-" + str(uuid.uuid4()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise SnapshotContractError("transaction journal replacement file has unsafe metadata")
        prior_bytes = b"".join(_canonical(record) + b"\n" for record in records)
        _write_all(fd, prior_bytes + encoded)
        os.fsync(fd)
    finally:
        os.close(fd)
    if records:
        current = os.open(journal_path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            current_info = os.fstat(current)
            if (not stat.S_ISREG(current_info.st_mode) or current_info.st_uid != 0
                    or current_info.st_gid != 0 or stat.S_IMODE(current_info.st_mode) != 0o600
                    or current_info.st_nlink != 1):
                raise SnapshotContractError("transaction journal changed during atomic replacement")
            observed = bytearray()
            while len(observed) <= MAX_JOURNAL_BYTES:
                part = os.read(current, min(65536, MAX_JOURNAL_BYTES + 1 - len(observed)))
                if not part:
                    break
                observed.extend(part)
        finally:
            os.close(current)
        if bytes(observed) != prior_bytes:
            raise SnapshotContractError("transaction journal changed before atomic replacement")
        os.replace(temporary, journal_path)
    else:
        _renameat2_file(temporary, journal_path, 1)
    _fsync_dir(parent)
    return record


def read_fence_ledger(path: str, *, allow_empty: bool = False) -> list[dict[str, Any]]:
    if path != "/var/lib/vst-runner/private/fence-ledger.json":
        raise SnapshotContractError("Runner fence ledger path differs from the fixed contract")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > MAX_JOURNAL_BYTES):
            raise SnapshotContractError("Runner fence ledger has unsafe identity or size")
        raw = bytearray()
        while len(raw) <= MAX_JOURNAL_BYTES:
            part = os.read(fd, min(65536, MAX_JOURNAL_BYTES + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
        final_info = os.fstat(fd)
        path_info = os.stat(path, follow_symlinks=False)
        if ((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) !=
                (final_info.st_dev, final_info.st_ino, final_info.st_size, final_info.st_mtime_ns)
                or (path_info.st_dev, path_info.st_ino) != (info.st_dev, info.st_ino)
                or len(raw) != final_info.st_size):
            raise SnapshotContractError("Runner fence ledger changed during its bounded read")
    finally:
        os.close(fd)
    if not raw and allow_empty:
        return []
    if not raw or not raw.endswith(b"\n"):
        raise SnapshotContractError("Runner fence ledger is empty or has a partial tail")
    required = {
        "version", "state", "unit", "invocation_id", "control_group",
        "cgroup_device", "cgroup_inode", "lock_device", "lock_inode",
        "generation", "predecessor_outcome", "sequence", "recorded_at",
        "previous_record_sha256", "record_sha256",
    }
    records: list[dict[str, Any]] = []
    previous = "0" * 64
    for sequence, line in enumerate(bytes(raw).splitlines(), start=1):
        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise SnapshotContractError("Runner fence ledger contains a duplicate key")
                result[key] = value
            return result
        record = json.loads(line, object_pairs_hook=unique)
        if (not isinstance(record, dict) or set(record) != required
                or record.get("sequence") != sequence
                or record.get("previous_record_sha256") != previous
                or not isinstance(record.get("record_sha256"), str)):
            raise SnapshotContractError("Runner fence ledger record shape or order is invalid")
        body = {key: value for key, value in record.items() if key != "record_sha256"}
        digest = hashlib.sha256(_canonical(body)).hexdigest()
        if digest != record["record_sha256"]:
            raise SnapshotContractError("Runner fence ledger hash chain is invalid")
        if record.get("state") not in {"BOOTSTRAP_EMPTY", "RUNNING", "STOPPED_EMPTY", "UNVERIFIED"}:
            raise SnapshotContractError("Runner fence ledger contains an unknown state")
        records.append(record)
        previous = digest
    return records


def create_durable_marker(marker_path: str, transaction: dict[str, Any]) -> tuple[int, int]:
    if not marker_path.endswith("/snapshot-transaction-incomplete.json"):
        raise SnapshotContractError("transaction marker path differs from the fixed contract")
    parent = os.path.dirname(marker_path)
    info = os.lstat(parent)
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_uid != 0 or info.st_gid != 0 or stat.S_IMODE(info.st_mode) & 0o022):
        raise SnapshotContractError("transaction marker parent is not root-controlled")
    payload = _canonical(transaction)
    if len(payload) > 16 * 1024:
        raise SnapshotContractError("transaction marker exceeds its fixed size limit")
    temporary = marker_path + ".pending-" + str(uuid.uuid4())
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o600)
        _write_all(fd, payload)
        os.fsync(fd)
        info = os.fstat(fd)
        identity = (info.st_dev, info.st_ino)
    finally:
        os.close(fd)
    _renameat2_file(temporary, marker_path, 1)
    _fsync_dir(parent)
    published = os.lstat(marker_path)
    if ((published.st_dev, published.st_ino) != identity or published.st_uid != 0
            or published.st_gid != 0 or stat.S_IMODE(published.st_mode) != 0o600
            or published.st_nlink != 1):
        raise SnapshotContractError("published transaction marker differs from its durable inode identity")
    return identity


def verify_durable_marker(marker_path: str, transaction_id: str,
                          marker_identity: tuple[int, int]) -> None:
    if marker_path != RUNTIME_PATHS["marker_path"]:
        raise SnapshotContractError("transaction marker path differs from the fixed contract")
    fd = os.open(marker_path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        raw = os.read(fd, 16 * 1024 + 1)
        if ((info.st_dev, info.st_ino) != marker_identity or info.st_uid != 0
                or info.st_gid != 0 or stat.S_IMODE(info.st_mode) != 0o600
                or len(raw) > 16 * 1024 or _unique_json(raw).get("transaction_id") != transaction_id):
            raise SnapshotContractError("transaction marker identity/content is not owned by this transaction")
    finally:
        os.close(fd)


def clear_durable_marker(marker_path: str, transaction_id: str,
                         marker_identity: tuple[int, int]) -> None:
    verify_durable_marker(marker_path, transaction_id, marker_identity)
    parent = os.path.dirname(marker_path)
    parent_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                        | getattr(os, "O_NOFOLLOW", 0))
    try:
        current = os.stat(os.path.basename(marker_path), dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != marker_identity:
            raise SnapshotContractError("transaction marker changed before unlink")
        os.unlink(os.path.basename(marker_path), dir_fd=parent_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def exchange_directories(left: str, right: str) -> None:
    if os.path.dirname(left) != os.path.dirname(right) or os.path.basename(left) in ("", ".", ".."):
        raise SnapshotContractError("atomic exchange paths must be sibling directories")
    left_info, right_info = os.lstat(left), os.lstat(right)
    if (not stat.S_ISDIR(left_info.st_mode) or stat.S_ISLNK(left_info.st_mode)
            or not stat.S_ISDIR(right_info.st_mode) or stat.S_ISLNK(right_info.st_mode)
            or left_info.st_dev != right_info.st_dev):
        raise SnapshotContractError("atomic exchange requires existing same-device directories")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise SnapshotContractError("libc renameat2 is unavailable; sequential rename is forbidden")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    result = renameat2(at_fdcwd, os.fsencode(left), at_fdcwd, os.fsencode(right), 2)
    if result != 0:
        error = ctypes.get_errno()
        raise SnapshotContractError("atomic RENAME_EXCHANGE failed without fallback: " + os.strerror(error))
    _fsync_dir(os.path.dirname(left))


def build_git_stage(pack: bytes, stage: str) -> dict[str, Any]:
    """Import the exact bounded shallow pack into an exclusive disposable path."""
    if not _HEX40.fullmatch(TASK_HEAD) or not _HEX40.fullmatch(TASK_TREE):
        raise SnapshotContractError("fixed Git task identities are malformed")
    if os.path.lexists(stage):
        raise SnapshotContractError("staging destination is occupied; it will not be replaced")
    os.mkdir(stage, 0o700)
    os.chown(stage, 0, 0)
    os.chmod(stage, 0o700)
    git_dir = os.path.join(stage, ".git")
    _run(["/usr/bin/git", "init", "--quiet", stage])
    _run(["/usr/bin/git", "-C", stage, "index-pack", "--stdin"], input_bytes=pack)
    _run(["/usr/bin/git", "-C", stage, "update-ref", "refs/heads/s2-task-source", TASK_HEAD])
    shallow_path = os.path.join(git_dir, "shallow")
    fd = os.open(shallow_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        _write_all(fd, (TASK_HEAD + "\n").encode("ascii"))
        os.fsync(fd)
    finally:
        os.close(fd)
    _run(["/usr/bin/git", "-C", stage, "config", "core.bare", "false"])
    _run(["/usr/bin/git", "-C", stage, "symbolic-ref", "HEAD", "refs/heads/s2-task-source"])
    _run(["/usr/bin/git", "-C", stage, "checkout", "--detach", TASK_HEAD])
    expected_objects = _git_output(stage, "count-objects", "-v").splitlines()
    packed_count = [line for line in expected_objects if line.startswith("in-pack: ")]
    if packed_count != ["in-pack: " + str(TASK_OBJECT_COUNT)]:
        raise SnapshotContractError("task-source pack object closure differs from the fixed count")
    readme = _git_output(stage, "rev-parse", "--show-toplevel")
    if os.path.realpath(readme) != os.path.realpath(stage):
        raise SnapshotContractError("Git stage root resolves outside its exclusive transaction path")
    for current, directories, files in os.walk(stage, topdown=False, followlinks=False):
        for name in files:
            path = os.path.join(current, name)
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SnapshotContractError("Git stage contains a non-regular file")
            os.chown(path, 0, 0)
            os.chmod(path, 0o555 if info.st_mode & 0o111 else 0o444)
            file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(file_fd)
            finally:
                os.close(file_fd)
        for name in directories:
            path = os.path.join(current, name)
            info = os.lstat(path)
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise SnapshotContractError("Git stage contains a link or special directory")
            os.chown(path, 0, 0)
            os.chmod(path, 0o555)
            _fsync_dir(path)
    os.chown(stage, 0, 0)
    os.chmod(stage, 0o555)
    _fsync_dir(stage)
    proof = _verify_git_readonly(stage)
    if proof["head"] != TASK_HEAD or proof["tree_sha1"] != TASK_TREE:
        raise SnapshotContractError("read-only Git proof returned an unexpected identity")
    return proof


def transaction_identity(old_root: str, stage: str, transaction_id: str | None = None) -> dict[str, Any]:
    transaction_id = transaction_id or uuid.uuid4().hex
    if not re.fullmatch(r"[0-9a-f]{32}", transaction_id):
        raise SnapshotContractError("transaction ID must be 128-bit lowercase hex")
    old = os.lstat(old_root)
    new = os.lstat(stage)
    if (not stat.S_ISDIR(old.st_mode) or stat.S_ISLNK(old.st_mode)
            or not stat.S_ISDIR(new.st_mode) or stat.S_ISLNK(new.st_mode)
            or old.st_dev != new.st_dev):
        raise SnapshotContractError("old and candidate snapshots are not safe same-device directories")
    if (old.st_uid != 0 or old.st_gid != 0
            or new.st_uid != 0 or new.st_gid != 0 or stat.S_IMODE(new.st_mode) != 0o555):
        raise SnapshotContractError("old or candidate snapshot has unexpected root identity or mode")
    old_head = _git_output(old_root, "rev-parse", "--verify", "HEAD")
    if old_head not in {EXPECTED_PREDECESSOR_HEAD, TASK_HEAD}:
        raise SnapshotContractError("existing predecessor HEAD is outside the reviewed runtime lineage")
    old_mode = stat.S_IMODE(old.st_mode)
    allowed_old_modes = {0o755, 0o555} if old_head == TASK_HEAD else {0o755}
    if old_mode not in allowed_old_modes:
        raise SnapshotContractError("existing predecessor mode differs from its exact Git identity")
    old_tree = _git_output(old_root, "rev-parse", "--verify", "HEAD^{tree}")
    if not _HEX40.fullmatch(old_tree):
        raise SnapshotContractError("existing predecessor tree identity is malformed")
    candidate_proof = _verify_git_readonly(stage)
    if (candidate_proof.get("head") != TASK_HEAD
            or candidate_proof.get("tree_sha1") != TASK_TREE
            or candidate_proof.get("worker_uid") != 997
            or candidate_proof.get("worker_gid") != 988):
        raise SnapshotContractError("candidate is not the exact bounded read-only task Git snapshot")
    return {"transaction_id": transaction_id, "task_source_head": TASK_HEAD,
            "task_source_tree_sha1": TASK_TREE, "live_path": old_root, "stage_path": stage,
            "old_device": old.st_dev, "old_inode": old.st_ino,
            "old_head": old_head, "old_tree_sha1": old_tree, "old_mode": old_mode,
            "candidate_device": new.st_dev, "candidate_inode": new.st_ino,
            "candidate_readonly_git_proof": candidate_proof,
            "format": "vst-snapshot-transaction-v1"}


def _ensure_private_parent(path: str, private_root: str) -> None:
    """Create only the fixed root-owned metadata directories, never arbitrary paths."""
    if os.path.dirname(path) != private_root:
        raise SnapshotContractError("transaction journal root differs from its fixed parent")
    for directory, mode in ((private_root, 0o700), (path, 0o700)):
        try:
            os.mkdir(directory, mode)
            os.chown(directory, 0, 0)
            os.chmod(directory, mode)
            _fsync_dir(os.path.dirname(directory))
        except FileExistsError:
            pass
        info = os.lstat(directory)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != mode):
            raise SnapshotContractError("transaction metadata directory has unexpected identity")


def create_transaction(root: str, stage: str, *, deployment_commit: str,
                       activation_state: dict[str, Any], configuration_state: dict[str, Any],
                       marker_path: str,
                       paths: dict[str, str] | None = None) -> dict[str, Any]:
    """Durably journal the prepared source and create the reboot-persistent guard marker.

    Caller must already have installed and verified both persistent systemd guards.
    This function deliberately accepts no unit controls or target paths from payload.
    """
    paths = RUNTIME_PATHS if paths is None else paths
    if (set(paths) != set(RUNTIME_PATHS)
            or root != paths["repository_root"] or marker_path != paths["marker_path"]):
        raise SnapshotContractError("transaction target/marker differs from the fixed contract")
    if not _HEX40.fullmatch(deployment_commit):
        raise SnapshotContractError("deployment source commit is not a full Git object ID")
    parent = os.path.dirname(root)
    parent_info = os.lstat(parent)
    if (not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode)
            or parent_info.st_uid != 0 or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) != 0o755):
        raise SnapshotContractError("task repository parent has unexpected identity")
    stage_name = os.path.basename(stage)
    expected_prefix = ".vst-task-source-stage-" + TASK_HEAD + "-"
    if (os.path.dirname(stage) != parent or not stage_name.startswith(expected_prefix)
            or not re.fullmatch(re.escape(expected_prefix) + r"[0-9a-f]{32}", stage_name)):
        raise SnapshotContractError("staging path differs from its fixed sibling naming contract")
    transaction_id = stage_name[len(expected_prefix):]
    ident = transaction_identity(root, stage, transaction_id)
    if (set(activation_state) != {"vst-runner.service", "vst-dispatcher.service"}
            or any(type(value) is not bool for value in activation_state.values())):
        raise SnapshotContractError("captured service activation state is incomplete")
    if not isinstance(configuration_state, dict) or set(configuration_state) != CONFIGURATION_PATHS:
        raise SnapshotContractError("configuration transaction lacks the exact 27-path state set")
    for destination, state in configuration_state.items():
        if (not isinstance(destination, str)
                or not (destination.startswith("/etc/vst-runner/")
                        or destination.startswith("/etc/systemd/system/"))
                or os.path.normpath(destination) != destination
                or ".." in destination.split("/")
                or not isinstance(state, dict)
                or set(state) != {"expected_current", "expected_new"}):
            raise SnapshotContractError("configuration transaction contains an unsafe path/state")
    private_root = paths["private_root"]
    journal_root = paths["journal_root"]
    _ensure_private_parent(journal_root, private_root)
    journal_dir = os.path.join(journal_root, ident["transaction_id"])
    os.mkdir(journal_dir, 0o700)
    os.chown(journal_dir, 0, 0)
    os.chmod(journal_dir, 0o700)
    _fsync_dir(private_root)
    journal_path = os.path.join(journal_dir, "journal.jsonl")
    marker_transaction = {
        "transaction_id": ident["transaction_id"],
        "deployment_commit": deployment_commit,
        "task_source_head": TASK_HEAD,
        "task_source_tree_sha1": TASK_TREE,
        "live_path": root,
        "stage_path": stage,
        "old_device": ident["old_device"],
        "old_inode": ident["old_inode"],
        "old_head": ident["old_head"],
        "old_tree_sha1": ident["old_tree_sha1"],
        "old_mode": ident["old_mode"],
        "candidate_device": ident["candidate_device"],
        "candidate_inode": ident["candidate_inode"],
        "candidate_readonly_git_proof": ident["candidate_readonly_git_proof"],
        "activation_state": activation_state,
        "configuration_state": configuration_state,
        "journal_path": journal_path,
        "journal_root": journal_root,
        "private_root": private_root,
        "marker_path": marker_path,
        "recovery_prefix": paths["recovery_prefix"],
        "format": "vst-snapshot-transaction-v1",
    }
    _append_journal(journal_path, marker_transaction, "GUARDS_VERIFIED")
    marker_identity = create_durable_marker(marker_path, marker_transaction)
    _append_journal(journal_path, marker_transaction, "MARKER_DURABLE",
                    marker_device=marker_identity[0], marker_inode=marker_identity[1])
    return {**marker_transaction, "journal_dir": journal_dir,
            "marker_identity": marker_identity, "state": "MARKER_DURABLE"}


def load_transaction_for_recovery(transaction_id: str,
                                 paths: dict[str, str] | None = None) -> dict[str, Any]:
    """Load only a root-owned, hash-chained transaction addressed by its fixed ID."""
    paths = RUNTIME_PATHS if paths is None else paths
    if (set(paths) != set(RUNTIME_PATHS) or paths["repository_root"] != TASK_REPOSITORY_ROOT
            or not _HEX32.fullmatch(transaction_id)):
        raise SnapshotContractError("recovery identity differs from the fixed contract")
    private_root, journal_root = paths["private_root"], paths["journal_root"]
    journal_dir = os.path.join(journal_root, transaction_id)
    for directory, expected_mode in ((private_root, 0o700), (journal_root, 0o700),
                                     (journal_dir, 0o700)):
        info = os.lstat(directory)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != expected_mode):
            raise SnapshotContractError("recovery metadata directory identity is unsafe")
    journal_path = os.path.join(journal_dir, "journal.jsonl")
    records = _read_journal(journal_path)
    first = records[0]
    expected_fields = _TRANSACTION_FIELDS
    if (first.get("state") != "GUARDS_VERIFIED" or first.get("transaction_id") != transaction_id
            or set(first).difference({"state", "sequence", "previous_record_sha256",
                                     "recorded_at", "record_sha256"}) != expected_fields):
        raise SnapshotContractError("recovery journal does not begin with the exact transaction record")
    base = {key: first[key] for key in expected_fields}
    for record in records:
        if any(record.get(key) != value for key, value in base.items()):
            raise SnapshotContractError("recovery journal changes an immutable transaction identity")
    transaction = base
    stage_name = ".vst-task-source-stage-" + TASK_HEAD + "-" + transaction_id
    recovery_path = paths["recovery_prefix"] + base["old_head"] + "-" + transaction_id
    if (base["format"] != "vst-snapshot-transaction-v1"
            or base["live_path"] != paths["repository_root"]
            or base["stage_path"] != os.path.join(os.path.dirname(base["live_path"]), stage_name)
            or base["journal_root"] != journal_root or base["private_root"] != private_root
            or base["journal_path"] != journal_path or base["marker_path"] != paths["marker_path"]
            or base["recovery_prefix"] != paths["recovery_prefix"]
            or base["task_source_head"] != TASK_HEAD
            or base["task_source_tree_sha1"] != TASK_TREE
            or not _HEX40.fullmatch(base["deployment_commit"])
            or not _HEX40.fullmatch(base["old_head"])
            or not _HEX40.fullmatch(base["old_tree_sha1"])
            or base["old_head"] not in {EXPECTED_PREDECESSOR_HEAD, TASK_HEAD}
            or base["old_mode"] not in ({0o755, 0o555} if base["old_head"] == TASK_HEAD else {0o755})
            or not isinstance(base["activation_state"], dict)
            or set(base["activation_state"]) != {"vst-runner.service", "vst-dispatcher.service"}
            or any(type(value) is not bool for value in base["activation_state"].values())
            or not isinstance(base["configuration_state"], dict)
            or set(base["configuration_state"]) != CONFIGURATION_PATHS
            or not isinstance(base["candidate_readonly_git_proof"], dict)
            or set(base["candidate_readonly_git_proof"]) != {
                "head", "tree_sha1", "shallow", "inventory_sha256", "worker_uid", "worker_gid",
                "status_clean", "diff_empty", "untracked_empty", "ignored_empty"}
            or base["candidate_readonly_git_proof"].get("head") != TASK_HEAD
            or base["candidate_readonly_git_proof"].get("tree_sha1") != TASK_TREE
            or base["candidate_readonly_git_proof"].get("shallow") != "true"
            or base["candidate_readonly_git_proof"].get("worker_uid") != 997
            or base["candidate_readonly_git_proof"].get("worker_gid") != 988
            or not _HEX64.fullmatch(str(base["candidate_readonly_git_proof"].get(
                "inventory_sha256", "")))
            or any(base["candidate_readonly_git_proof"].get(key) is not True
                   for key in ("status_clean", "diff_empty", "untracked_empty", "ignored_empty"))):
        raise SnapshotContractError("recovery journal has an out-of-contract transaction identity")
    marker_records = [record for record in records
                      if "marker_device" in record and "marker_inode" in record]
    marker_identity = None
    if marker_records:
        marker_identity = (marker_records[-1].get("marker_device"), marker_records[-1].get("marker_inode"))
        if any(type(part) is not int or part < 0 for part in marker_identity):
            raise SnapshotContractError("recovery journal marker inode identity is malformed")
    marker_present = False
    try:
        marker_fd = os.open(paths["marker_path"], os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        if marker_records and records[-1].get("state") not in {
                "ACTIVATION_READY", "MARKER_CLEARED", "ACTIVATION_RESTORED"}:
            raise SnapshotContractError("transaction marker is absent without a durable clearance record")
        if not marker_records and records[-1].get("state") not in {
                "GUARDS_VERIFIED", "ACTIVATION_READY", "MARKER_CLEARED", "ACTIVATION_RESTORED"}:
            raise SnapshotContractError("transaction marker is absent outside the pre-marker state")
    else:
        try:
            marker_info = os.fstat(marker_fd)
            marker_raw = os.read(marker_fd, 16 * 1024 + 1)
            marker_payload = _unique_json(marker_raw)
            observed_marker_identity = (marker_info.st_dev, marker_info.st_ino)
            if (marker_info.st_uid != 0 or marker_info.st_gid != 0
                    or stat.S_IMODE(marker_info.st_mode) != 0o600
                    or len(marker_raw) > 16 * 1024 or marker_payload != base):
                raise SnapshotContractError("recovery marker differs from its journaled transaction identity")
            if marker_identity is not None and observed_marker_identity != marker_identity:
                if records[-1].get("state") not in {
                        "ACTIVATION_READY", "MARKER_CLEARED", "RECOVERY_REQUIRED", "FENCING"}:
                    raise SnapshotContractError("recovery marker inode changed outside an explicit recovery state")
            marker_identity = observed_marker_identity
            marker_present = True
        finally:
            os.close(marker_fd)
    backup_records = next((record.get("configuration_backups") for record in reversed(records)
                           if isinstance(record.get("configuration_backups"), dict)), {})
    return {**transaction, "journal_dir": journal_dir, "journal_path": journal_path,
            "marker_identity": marker_identity, "marker_present": marker_present,
            "state": records[-1]["state"], "records": records,
            "configuration_backup_records": backup_records,
            "recovery_path": recovery_path}


def reconcile_snapshot_paths(transaction: dict[str, Any]) -> dict[str, Any]:
    """Identify old/candidate snapshots by inode and Git identity without mutation."""
    expected = {"live": transaction["live_path"], "stage": transaction["stage_path"],
                "recovery": transaction["recovery_path"]}
    found: dict[str, list[str]] = {"old": [], "candidate": []}
    identities = {"old": (transaction["old_device"], transaction["old_inode"]),
                  "candidate": (transaction["candidate_device"], transaction["candidate_inode"])}
    for label, path in expected.items():
        if not os.path.lexists(path):
            continue
        info = os.lstat(path)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != 0 or info.st_gid != 0):
            raise SnapshotContractError("recovery snapshot path has unsafe type or ownership")
        inode = (info.st_dev, info.st_ino)
        matches = [name for name, identity in identities.items() if inode == identity]
        if len(matches) != 1:
            raise SnapshotContractError("recovery snapshot path is not an exact recorded inode")
        name = matches[0]
        expected_mode = (0o555 if name == "candidate" else transaction["old_mode"])
        if stat.S_IMODE(info.st_mode) != expected_mode:
            raise SnapshotContractError("recovery snapshot mode differs from its recorded role")
        git_identity = _tree_identity(path)
        expected_git = ((TASK_HEAD, TASK_TREE) if name == "candidate"
                        else (transaction["old_head"], transaction["old_tree_sha1"]))
        if git_identity[:2] != expected_git:
            raise SnapshotContractError("recovery snapshot Git identity differs from its exact pin")
        found[name].append(label)
    if any(len(locations) != 1 for locations in found.values()):
        raise SnapshotContractError("recovery cannot uniquely locate both retained snapshots")
    if "live" not in found["old"] + found["candidate"]:
        raise SnapshotContractError("live snapshot path has an unknown identity")
    return {"live": "candidate" if "live" in found["candidate"] else "old",
            "old_path": expected[found["old"][0]],
            "candidate_path": expected[found["candidate"][0]],
            "old_location": found["old"][0], "candidate_location": found["candidate"][0]}


def _read_root_json(path: str, *, mode: int, limit: int = 4 * 1024 * 1024
                    ) -> tuple[dict[str, Any], bytes]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) != mode or info.st_size > limit):
            raise SnapshotContractError("bootstrap metadata has unsafe identity, mode, or size")
        raw = bytearray()
        while len(raw) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(raw)))
            if not part:
                break
            raw.extend(part)
    finally:
        os.close(fd)
    if len(raw) > limit:
        raise SnapshotContractError("bootstrap metadata exceeds its bounded read")
    return _unique_json(bytes(raw)), bytes(raw)


def _verify_root_directory_chain(path: str) -> None:
    if not os.path.isabs(path) or os.path.normpath(path) != path:
        raise SnapshotContractError("privileged metadata parent is not a normalized absolute path")
    current = "/"
    for part in (path.strip("/").split("/") if path != "/" else ()):
        current = os.path.join(current, part)
        info = os.lstat(current)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise SnapshotContractError("privileged metadata parent path is not root-controlled")


def _bootstrap_cgroup(path: str) -> dict[str, Any]:
    expected = {
        "/sys/fs/cgroup/system.slice/vst-runner.service": "vst-runner.service",
        "/sys/fs/cgroup/system.slice/vst-dispatcher.service": "vst-dispatcher.service",
    }
    if path not in expected:
        raise SnapshotContractError("protected cgroup path differs from the fixed unit inventory")
    root_fd = os.open("/sys/fs/cgroup", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    slice_fd = target_fd = -1
    try:
        root_info = os.fstat(root_fd)
        if not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != 0 or root_info.st_gid != 0:
            raise SnapshotContractError("cgroup v2 root is not root-controlled")
        slice_fd = os.open("system.slice", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                           dir_fd=root_fd)
        slice_info = os.fstat(slice_fd)
        if not stat.S_ISDIR(slice_info.st_mode) or slice_info.st_uid != 0 or slice_info.st_gid != 0:
            raise SnapshotContractError("system.slice cgroup directory is not root-controlled")
        try:
            target_fd = os.open(expected[path], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=slice_fd)
        except FileNotFoundError:
            return {"state": "absent"}
        info = os.fstat(target_fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != 0:
            raise SnapshotContractError("protected cgroup directory is not root-owned")
        events_fd = os.open("cgroup.events", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=target_fd)
        try:
            events_info = os.fstat(events_fd)
            if not stat.S_ISREG(events_info.st_mode):
                raise SnapshotContractError("cgroup.events is not a regular pseudo-file")
            events_raw = os.read(events_fd, 4096).decode("ascii")
        finally:
            os.close(events_fd)
        procs_fd = os.open("cgroup.procs", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=target_fd)
        try:
            procs_info = os.fstat(procs_fd)
            if not stat.S_ISREG(procs_info.st_mode):
                raise SnapshotContractError("cgroup.procs is not a regular pseudo-file")
            procs_raw = os.read(procs_fd, 1024 * 1024).decode("ascii")
        finally:
            os.close(procs_fd)
        events = dict(line.split() for line in events_raw.splitlines() if line.strip())
        pids = [line for line in procs_raw.splitlines() if line.strip()]
        entries = list(os.scandir(target_fd))
    except (OSError, UnicodeError, ValueError) as exc:
        raise SnapshotContractError("protected cgroup quiescence cannot be read") from exc
    finally:
        if target_fd >= 0:
            os.close(target_fd)
        if slice_fd >= 0:
            os.close(slice_fd)
        os.close(root_fd)
    if (events.get("populated") != "0" or pids
            or any(entry.is_symlink() or entry.is_dir(follow_symlinks=False) for entry in entries)):
        raise SnapshotContractError("protected cgroup is populated or contains child scopes")
    return {"state": "empty", "device": info.st_dev, "inode": info.st_ino,
            "populated": "0", "processes": 0, "children": 0}


def _bootstrap_process_counts(role_uids: set[int]) -> dict[str, int]:
    counts = {str(uid): 0 for uid in role_uids}
    try:
        entries = list(os.scandir("/proc"))
    except OSError as exc:
        raise SnapshotContractError("process inventory cannot be opened") from exc
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            fd = os.open(os.path.join(entry.path, "status"), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise SnapshotContractError("process identity inventory is incomplete") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise SnapshotContractError("process status is not a regular proc file")
            raw = os.read(fd, 65536).decode("ascii")
        except (OSError, UnicodeError) as exc:
            raise SnapshotContractError("process identity inventory is unreadable") from exc
        finally:
            os.close(fd)
        uid_line = next((line for line in raw.splitlines() if line.startswith("Uid:")), None)
        if uid_line is None:
            raise SnapshotContractError("process status has no UID identity")
        try:
            uids = [int(value) for value in uid_line.split()[1:5]]
        except ValueError as exc:
            raise SnapshotContractError("process status UID identity is malformed") from exc
        if len(uids) != 4:
            raise SnapshotContractError("process status UID identity is incomplete")
        for uid in set(uids) & role_uids:
            counts[str(uid)] += 1
    if any(counts.values()):
        raise SnapshotContractError("a reserved Runner role identity has live processes")
    return counts


def _validate_bootstrap_record(record: dict[str, Any]) -> None:
    if (set(record) != {
            "version", "state", "unit", "invocation_id", "control_group",
            "cgroup_device", "cgroup_inode", "lock_device", "lock_inode",
            "generation", "predecessor_outcome", "sequence", "recorded_at",
            "previous_record_sha256", "record_sha256"}
            or record.get("version") != 1 or record.get("state") != "BOOTSTRAP_EMPTY"
            or record.get("unit") != "vst-runner.service"
            or record.get("invocation_id") != "BOOTSTRAP"
            or record.get("control_group") != "/system.slice/vst-runner.service"
            or record.get("generation") != "BOOTSTRAP"
            or record.get("predecessor_outcome") != "NONE"
            or type(record.get("sequence")) is not int or record["sequence"] != 1
            or record.get("previous_record_sha256") != "0" * 64
            or any(type(record.get(field)) is not int for field in
                   ("cgroup_device", "cgroup_inode", "lock_device", "lock_inode"))
            or record.get("lock_device") != -1 or record.get("lock_inode") != -1
            or ((record.get("cgroup_device") == -1) != (record.get("cgroup_inode") == -1))
            or record.get("cgroup_device", -1) < -1 or record.get("cgroup_inode", -1) < -1
            or not isinstance(record.get("recorded_at"), str)
            or not _HEX64.fullmatch(str(record.get("record_sha256", "")))):
        raise SnapshotContractError("fence ledger is not an authentic BOOTSTRAP_EMPTY record")
    body = {key: value for key, value in record.items() if key != "record_sha256"}
    if hashlib.sha256(_canonical(body)).hexdigest() != record["record_sha256"]:
        raise SnapshotContractError("BOOTSTRAP_EMPTY record hash is invalid")


def observe_bootstrap_predecessor(*, allow_missing_ledger: bool = False,
                                 allow_candidate_root: bool = False) -> dict[str, Any]:
    """Read fresh cold-start evidence without changing the Runner lifecycle state."""
    for parent in ("/etc/vst-runner", "/var/lib/vst-runner/private",
                   "/var/lib/vst-runner", "/opt"):
        _verify_root_directory_chain(parent)
    config, config_raw = _read_root_json(_FENCE_CONFIG, mode=0o600, limit=65536)
    required = {"unit_name", "systemctl_path", "ledger_path", "runtime_dir", "daemon_uid",
                "daemon_gid", "dispatcher_uid", "dispatcher_gid", "worker_uid", "worker_gid",
                "control_group", "generation_record_path"}
    role_uids = [config.get(name) for name in ("daemon_uid", "dispatcher_uid", "worker_uid")]
    if (set(config) != required or config.get("unit_name") != "vst-runner.service"
            or config.get("systemctl_path") != "/usr/bin/systemctl"
            or config.get("ledger_path") != _FENCE_LEDGER
            or config.get("generation_record_path") != _FENCE_GENERATION
            or config.get("control_group") != "/system.slice/vst-runner.service"
            or any(type(uid) is not int or uid < 1 for uid in role_uids)
            or len(set(role_uids)) != 3):
        raise SnapshotContractError("fence configuration does not match the fixed cold-start contract")
    ledger_absent = False
    ledger_empty = False
    try:
        records = read_fence_ledger(_FENCE_LEDGER, allow_empty=True)
    except FileNotFoundError:
        ledger_absent = True
        records = []
    ledger_empty = not ledger_absent and not records
    ledger_identity = None
    if not ledger_absent:
        ledger_info = os.lstat(_FENCE_LEDGER)
        if not stat.S_ISREG(ledger_info.st_mode) or stat.S_ISLNK(ledger_info.st_mode):
            raise SnapshotContractError("Runner ledger path is not a regular non-link file")
        ledger_identity = {"device": ledger_info.st_dev, "inode": ledger_info.st_ino}
    generation_absent = False
    generation_record: dict[str, Any] | None = None
    try:
        generation_record, _generation_raw = _read_root_json(_FENCE_GENERATION, mode=0o644)
    except FileNotFoundError:
        generation_absent = True
    if (ledger_absent or ledger_empty) and not allow_missing_ledger:
        raise SnapshotContractError("Runner lifecycle ledger is absent or has no authoritative record")
    if (ledger_absent or ledger_empty) and not generation_absent:
        raise SnapshotContractError("generation snapshot exists without its authoritative lifecycle ledger")
    if not ledger_absent and not ledger_empty:
        if len(records) != 1:
            raise SnapshotContractError("cold bootstrap accepts only the one-record initial ledger")
        _validate_bootstrap_record(records[0])
        if not generation_absent and generation_record != records[0]:
            raise SnapshotContractError("generation snapshot differs from its authoritative ledger record")
    store_sidecars = [_STORE_PATH, _STORE_PATH + "-wal", _STORE_PATH + "-shm",
                      _STORE_PATH + "-journal"]
    store_states = {}
    for path in store_sidecars:
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            store_states[path] = "absent"
        else:
            if stat.S_ISLNK(info.st_mode):
                raise SnapshotContractError("Store metadata path is a symlink")
            raise SnapshotContractError("Store or SQLite sidecar already exists")
    units: dict[str, Any] = {}
    for unit in _ROLE_UNITS:
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", unit,
             "--property=ActiveState", "--property=SubState",
             "--property=InvocationID", "--property=ControlGroup", "--no-pager"],
            cwd="/", env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
            timeout=8, check=False)
        try:
            lines = result.stdout.decode("ascii").splitlines()
        except UnicodeError as exc:
            raise SnapshotContractError("protected systemd properties are not ASCII") from exc
        expected_properties = {"ActiveState", "SubState", "InvocationID", "ControlGroup"}
        values: dict[str, str] = {}
        for line in lines:
            key, separator, value = line.partition("=")
            if not separator or key not in expected_properties or key in values:
                raise SnapshotContractError("protected systemd properties are malformed or duplicated")
            values[key] = value
        if (result.returncode != 0 or values.get("ActiveState") != "inactive"
                or values.get("SubState") != "dead" or values.get("InvocationID") != ""
                or values.get("ControlGroup") != "" or set(values) != expected_properties):
            raise SnapshotContractError("protected systemd unit is not exactly inactive without identity")
        units[unit] = {"active_state": "inactive", "sub_state": "dead",
                       "invocation_id": "", "control_group": ""}
    jobs = subprocess.run(
        ["/usr/bin/systemctl", "list-jobs", "--no-legend", "--no-pager"],
        cwd="/", env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
        timeout=8, check=False)
    if jobs.returncode != 0:
        raise SnapshotContractError("systemd job inventory is unavailable")
    try:
        job_units = [line.split()[1] for line in jobs.stdout.decode("ascii").splitlines()
                     if len(line.split()) >= 2]
    except UnicodeError as exc:
        raise SnapshotContractError("systemd job inventory is malformed") from exc
    if set(job_units) & set(_ROLE_UNITS):
        raise SnapshotContractError("a protected systemd unit has a pending job")
    cgroups = {
        "vst-runner.service": _bootstrap_cgroup("/sys/fs/cgroup/system.slice/vst-runner.service"),
        "vst-dispatcher.service": _bootstrap_cgroup("/sys/fs/cgroup/system.slice/vst-dispatcher.service"),
    }
    process_counts = _bootstrap_process_counts(set(role_uids))
    boot_fd = os.open("/proc/sys/kernel/random/boot_id", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        boot_id = os.read(boot_fd, 128).decode("ascii").strip()
    finally:
        os.close(boot_fd)
    pid1_fd = os.open("/proc/1/stat", os.O_RDONLY | os.O_NOFOLLOW)
    try:
        pid1_stat = os.read(pid1_fd, 4096).decode("ascii").strip()
    finally:
        os.close(pid1_fd)
    pid1_tail = pid1_stat.rsplit(")", 1)[-1].split()
    if len(pid1_tail) < 20 or not _HEX32.fullmatch(boot_id.replace("-", "")):
        raise SnapshotContractError("kernel boot or PID 1 start-time identity is malformed")
    repo = os.lstat(TASK_REPOSITORY_ROOT)
    if (not stat.S_ISDIR(repo.st_mode) or stat.S_ISLNK(repo.st_mode)
            or repo.st_uid != 0 or repo.st_gid != 0):
        raise SnapshotContractError("live snapshot root is not a root-owned directory")
    root_mode = stat.S_IMODE(repo.st_mode)
    head = _git_output(TASK_REPOSITORY_ROOT, "rev-parse", "--verify", "HEAD")
    tree = _git_output(TASK_REPOSITORY_ROOT, "rev-parse", "--verify", "HEAD^{tree}")
    if (head, tree, root_mode) == (
            EXPECTED_PREDECESSOR_HEAD, "38a0a60b6170d068beb370c62f25b008d246902f", 0o755):
        root_kind = "predecessor"
        readonly_git_proof = None
    elif (head, tree, root_mode) == (TASK_HEAD, TASK_TREE, 0o555):
        if not allow_candidate_root:
            raise SnapshotContractError("candidate root is accepted only during explicit cold recovery")
        root_kind = "candidate"
        readonly_git_proof = _verify_git_readonly(TASK_REPOSITORY_ROOT)
    else:
        raise SnapshotContractError("live root is neither the exact predecessor nor exact readonly candidate")
    record = records[0] if records else None
    return {
        "schema": "VST_RUNNER_COLD_PREDECESSOR_PROOF_V1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "boot_id": boot_id, "pid1_start_ticks": pid1_tail[19],
        "fence_config_sha256": hashlib.sha256(config_raw).hexdigest(),
        "ledger_absent": ledger_absent, "ledger_empty": ledger_empty,
        "ledger_identity": ledger_identity,
        "generation_absent": generation_absent,
        "ledger_record": record,
        "ledger_record_sha256": None if record is None else record["record_sha256"],
        "generation_matches_ledger": bool(record is not None and generation_record == record),
        "role_process_counts": process_counts, "units": units, "cgroups": cgroups,
        "protected_jobs": [],
        "store_paths": store_states,
        "live_root": {"kind": root_kind, "device": repo.st_dev, "inode": repo.st_ino,
                      "mode": root_mode, "head": head, "tree_sha1": tree,
                      "readonly_git_proof": readonly_git_proof},
    }


def _cold_proof_current(proof: dict[str, Any], *, allow_missing: bool) -> dict[str, Any]:
    proof_fields = {"schema", "observed_at", "boot_id", "pid1_start_ticks",
                    "fence_config_sha256", "ledger_absent", "ledger_empty", "generation_absent",
                    "ledger_identity", "ledger_record", "ledger_record_sha256", "generation_matches_ledger",
                    "role_process_counts", "units", "cgroups", "protected_jobs",
                    "store_paths", "live_root"}
    if (not isinstance(proof, dict) or set(proof) != proof_fields
            or proof.get("schema") != "VST_RUNNER_COLD_PREDECESSOR_PROOF_V1"):
        raise SnapshotContractError("cold-start proof schema is invalid")
    current = observe_bootstrap_predecessor(
        allow_missing_ledger=allow_missing,
        allow_candidate_root=proof.get("live_root", {}).get("kind") == "candidate")
    for field in proof_fields - {"observed_at"}:
        if current.get(field) != proof.get(field):
            raise SnapshotContractError("cold-start proof is stale for field " + field)
    return current


def _journal_masks(transaction: dict[str, Any]) -> dict[str, Any]:
    records = _read_journal(transaction["journal_path"])
    masks = next((record.get("runtime_masks") for record in reversed(records)
                  if isinstance(record.get("runtime_masks"), dict)), None)
    units = set(_ROLE_UNITS)
    if not isinstance(masks, dict) or set(masks) != units:
        raise SnapshotContractError("bootstrap requires both transaction-owned runtime masks")
    for unit in units:
        mask = masks[unit]
        if (not isinstance(mask, dict) or set(mask) != {"device", "inode", "target"}
                or mask.get("target") != "/dev/null"):
            raise SnapshotContractError("bootstrap mask journal identity is malformed")
        path = "/run/systemd/system/" + unit
        info = os.lstat(path)
        if (not stat.S_ISLNK(info.st_mode) or (info.st_dev, info.st_ino) !=
                (mask.get("device"), mask.get("inode")) or os.readlink(path) != "/dev/null"):
            raise SnapshotContractError("bootstrap lacks the exact transaction-owned unit mask")
    return masks


def _verify_bootstrap_guards(transaction: dict[str, Any]) -> None:
    for path in PREINSTALLED_GUARD_PATHS:
        state = transaction["configuration_state"].get(path)
        if not isinstance(state, dict) or _config_fingerprint(path)[0] != state.get("expected_new"):
            raise SnapshotContractError("bootstrap persistent guard is not the exact pinned configuration")
    required = "ConditionPathExists=!/var/lib/vst-runner/private/snapshot-transaction-incomplete.json"
    for unit in _ROLE_UNITS:
        result = subprocess.run(
            ["/usr/bin/systemctl", "show", unit, "--property=Conditions", "--no-pager"],
            cwd="/", env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
            timeout=8, check=False)
        if result.returncode != 0 or required.encode("ascii") not in result.stdout:
            raise SnapshotContractError("systemd has not loaded the exact persistent transaction guard")


def _verify_pinned_runtime() -> str:
    runtime = "/opt/vst-runtime-" + RUNNER_FENCE_BOOTSTRAP_COMMIT
    module_path = runtime + "/tools/vst/runner_fence.py"
    contracts_path = runtime + "/tools/vst/contracts.py"
    current = "/"
    for part in ("opt", "vst-runtime-" + RUNNER_FENCE_BOOTSTRAP_COMMIT,
                 "tools", "vst"):
        current = os.path.join(current, part)
        info = os.lstat(current)
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise SnapshotContractError("immutable Runner runtime path is not root-controlled")
    for path, expected in ((module_path, RUNNER_FENCE_SOURCE_SHA256),
                           (contracts_path, RUNNER_CONTRACTS_SOURCE_SHA256)):
        info = os.lstat(path)
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1
                or info.st_uid != 0 or info.st_gid != 0
                or stat.S_IMODE(info.st_mode) & 0o022):
            raise SnapshotContractError("immutable Runner source file is not root-controlled")
        actual = _hash_file(path)
        if actual != expected:
            raise SnapshotContractError("immutable Runner fence source digest differs from its pinned runtime")
    return runtime


def _invoke_pinned_bootstrap(expected_config_sha256: str, *, ledger_was_absent: bool,
                             expected_ledger_identity: dict[str, int] | None) -> None:
    runtime = _verify_pinned_runtime()
    bootstrap = '''
import hashlib, json, os, stat, sys
fd = os.open('/etc/vst-runner/fence.json', os.O_RDONLY | os.O_NOFOLLOW)
try:
    raw = os.read(fd, 65537)
finally:
    os.close(fd)
if hashlib.sha256(raw).hexdigest() != EXPECTED_CONFIG_SHA256:
    raise RuntimeError('fence configuration changed before bootstrap')
sys.path.insert(0, RUNTIME_PATH)
from tools.vst.runner_fence import bootstrap_empty, _load_root_json, _lock_path
config = _load_root_json('/etc/vst-runner/fence.json')
if config.get('ledger_path') != LEDGER_PATH or config.get('generation_record_path') != GENERATION_PATH:
    raise RuntimeError('fence paths differ from the cold-start contract')
lock_fd = _lock_path(config['ledger_path'])
ledger_fd = -1
try:
    try:
        ledger_fd = os.open(LEDGER_PATH, os.O_RDWR | os.O_NOFOLLOW)
        created = False
    except FileNotFoundError:
        if not LEDGER_WAS_ABSENT:
            raise RuntimeError('expected empty ledger disappeared')
        ledger_fd = os.open(LEDGER_PATH,
                            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created = True
        os.fchown(ledger_fd, 0, 0)
        os.fchmod(ledger_fd, 0o600)
    info = os.fstat(ledger_fd)
    path_info = os.lstat(LEDGER_PATH)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != 0 or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != 0
            or stat.S_ISLNK(path_info.st_mode)
            or (path_info.st_dev, path_info.st_ino) != (info.st_dev, info.st_ino)):
        raise RuntimeError('ledger is not the exact safe empty file')
    if not created and LEDGER_WAS_ABSENT:
        raise RuntimeError('ledger appeared after the absent-ledger observation')
    if (not created and EXPECTED_LEDGER_IDENTITY is not None
            and {'device': info.st_dev, 'inode': info.st_ino} != EXPECTED_LEDGER_IDENTITY):
        raise RuntimeError('empty ledger inode changed after its observation')
    os.fsync(ledger_fd)
    parent_fd = os.open(os.path.dirname(LEDGER_PATH), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    if os.path.lexists(GENERATION_PATH):
        raise RuntimeError('generation appeared before baseline bootstrap')
finally:
    os.close(lock_fd)
record = bootstrap_empty()
after = os.fstat(ledger_fd)
path_after = os.lstat(LEDGER_PATH)
if ((after.st_dev, after.st_ino) != (info.st_dev, info.st_ino)
        or (path_after.st_dev, path_after.st_ino) != (info.st_dev, info.st_ino)
        or not stat.S_ISREG(path_after.st_mode) or stat.S_ISLNK(path_after.st_mode)
        or path_after.st_uid != 0 or path_after.st_gid != 0
        or stat.S_IMODE(path_after.st_mode) != 0o600 or after.st_size <= 0):
    raise RuntimeError('bootstrap replaced or failed to durably append to the prepared ledger')
os.close(ledger_fd)
print(json.dumps(record, sort_keys=True, separators=(',', ':')))
'''
    replacements = {
        "EXPECTED_CONFIG_SHA256": repr(expected_config_sha256),
        "RUNTIME_PATH": repr(runtime),
        "LEDGER_PATH": repr(_FENCE_LEDGER),
        "GENERATION_PATH": repr(_FENCE_GENERATION),
        "LEDGER_WAS_ABSENT": repr(ledger_was_absent),
        "EXPECTED_LEDGER_IDENTITY": repr(expected_ledger_identity),
    }
    for name, value in replacements.items():
        bootstrap = bootstrap.replace(name, value)
    code = "exec(" + repr(bootstrap) + ")"
    result = subprocess.run(
        ["/usr/bin/python3.12", "-I", "-B", "-S", "-c", code], cwd="/",
        env={"LC_ALL": "C", "PATH": ""}, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
        timeout=30, check=False)
    if result.returncode != 0:
        raise SnapshotContractError("pinned Runner bootstrap primitive failed closed")
    try:
        emitted = _unique_json(result.stdout.strip())
    except (ValueError, UnicodeError) as exc:
        raise SnapshotContractError("pinned Runner bootstrap returned malformed evidence") from exc
    _validate_bootstrap_record(emitted)


def ensure_bootstrap_predecessor(transaction: dict[str, Any], *,
                                 create_baseline: bool = True) -> dict[str, Any]:
    if transaction.get("activation_state") != {
            "vst-runner.service": False, "vst-dispatcher.service": False}:
        raise SnapshotContractError("cold bootstrap is limited to transactions with both services originally inactive")
    verify_durable_marker(transaction["marker_path"], transaction["transaction_id"],
                          transaction.get("marker_identity"))
    _journal_masks(transaction)
    _verify_bootstrap_guards(transaction)
    proof = observe_bootstrap_predecessor(allow_missing_ledger=True,
                                         allow_candidate_root=not create_baseline)
    if proof["ledger_absent"] or proof["ledger_empty"]:
        if not create_baseline:
            return proof
        _invoke_pinned_bootstrap(
            proof["fence_config_sha256"], ledger_was_absent=proof["ledger_absent"],
            expected_ledger_identity=proof["ledger_identity"])
    elif proof["generation_absent"]:
        # Only repair this one derived file when its exact authoritative ledger record exists.
        record = proof["ledger_record"]
        _validate_bootstrap_record(record)
        runtime = _verify_pinned_runtime()
        contracts_module = runtime + "/tools/vst/contracts.py"
        fence_module = runtime + "/tools/vst/runner_fence.py"
        if (_hash_file(fence_module) != RUNNER_FENCE_SOURCE_SHA256
                or _hash_file(contracts_module) != RUNNER_CONTRACTS_SOURCE_SHA256):
            raise SnapshotContractError("immutable Runner fence source digest differs from its pinned runtime")
        code = ("import hashlib,os,sys; fd=os.open('/etc/vst-runner/fence.json',os.O_RDONLY|os.O_NOFOLLOW); "
                "raw=os.read(fd,65537); os.close(fd); "
                "assert hashlib.sha256(raw).hexdigest()==" + repr(proof["fence_config_sha256"]) + "; "
                "sys.path.insert(0, " + repr(runtime) + "); "
                "from tools.vst.runner_fence import (_publish_generation,_load_root_json,"
                "_lock_path,_read_records); "
                "c=_load_root_json('/etc/vst-runner/fence.json'); "
                "fd=_lock_path(c['ledger_path']); "
                "r=_read_records(c['ledger_path']); "
                "assert len(r)==1 and r[0]==" + repr(record) + "; "
                "assert not os.path.lexists(c['generation_record_path']); "
                "_publish_generation(c,r[0]); os.close(fd)")
        result = subprocess.run(["/usr/bin/python3.12", "-I", "-B", "-S", "-c", code],
                                cwd="/", env={"LC_ALL": "C", "PATH": ""},
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, close_fds=True, timeout=30, check=False)
        if result.returncode != 0:
            raise SnapshotContractError("pinned generation repair failed closed")
    return observe_bootstrap_predecessor(allow_missing_ledger=not create_baseline)


def record_dispatcher_bootstrap_quiescent(transaction: dict[str, Any], *,
                                          proof: dict[str, Any]) -> None:
    current = _cold_proof_current(proof, allow_missing=False)
    record_state(transaction, "FENCED", "DISPATCHER_DRAINED",
                 dispatcher_inactive=True, dispatcher_cgroup_empty=True,
                 dispatcher_invocation_id_absent=True, cold_predecessor_proof=current)


def record_runner_bootstrap_empty(transaction: dict[str, Any], *,
                                  proof: dict[str, Any]) -> None:
    current = _cold_proof_current(proof, allow_missing=False)
    if (transaction.get("activation_state") != {
            "vst-runner.service": False, "vst-dispatcher.service": False}
            or current.get("ledger_absent") or current.get("ledger_record") is None
            or current.get("generation_matches_ledger") is not True):
        raise SnapshotContractError("Runner bootstrap state lacks the exact cold BOOTSTRAP_EMPTY record")
    _journal_masks(transaction)
    _verify_bootstrap_guards(transaction)
    record_state(transaction, "DISPATCHER_DRAINED", "RUNNER_BOOTSTRAP_EMPTY",
                 runner_inactive=True, runner_cgroup_empty=True,
                 runner_invocation_id_absent=True,
                 runner_fence_record_sha256=current["ledger_record_sha256"],
                 cold_predecessor_proof=current)


def recover_snapshot_transaction(transaction: dict[str, Any], *,
                                 guards_verified: dict[str, bool],
                                 runtime_masks_owned: dict[str, dict[str, Any]],
                                 services_quiesced: dict[str, bool],
                                 bootstrap_proof: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reconcile an exact terminal snapshot state; never starts services or deletes snapshots."""
    units = {"vst-runner.service", "vst-dispatcher.service"}
    if guards_verified != {unit: True for unit in units}:
        raise SnapshotContractError("recovery requires both exact persistent guards to be effective")
    if services_quiesced != {unit: True for unit in units}:
        raise SnapshotContractError("recovery requires both protected service cgroups to be quiescent")
    if bootstrap_proof is not None:
        if transaction.get("activation_state") != {unit: False for unit in units}:
            raise SnapshotContractError("cold-start recovery proof is valid only for originally inactive services")
        bootstrap_proof = _cold_proof_current(bootstrap_proof, allow_missing=True)
    recorded_masks = next((record.get("runtime_masks") for record in reversed(
        transaction.get("records", [])) if isinstance(record.get("runtime_masks"), dict)), None)
    if transaction.get("marker_present") or transaction.get("state") in {
            "MARKER_CLEARED", "RECOVERY_REQUIRED"}:
        if not isinstance(recorded_masks, dict) or set(recorded_masks) != units:
            raise SnapshotContractError("marker clearance requires both journaled transaction mask identities")
        for unit in units:
            expected_mask = recorded_masks[unit]
            if (not isinstance(expected_mask, dict) or set(expected_mask) != {"device", "inode", "target"}
                    or expected_mask.get("target") != "/dev/null"
                    or type(expected_mask.get("device")) is not int
                    or type(expected_mask.get("inode")) is not int
                    or runtime_masks_owned.get(unit) != expected_mask):
                raise SnapshotContractError("runtime mask identity is not the exact transaction-owned inode")
    layout = reconcile_snapshot_paths(transaction)
    if bootstrap_proof is not None and layout["live"] == "candidate":
        cold_records = [record for record in transaction.get("records", [])
                        if record.get("state") == "RUNNER_BOOTSTRAP_EMPTY"]
        if (bootstrap_proof.get("live_root", {}).get("kind") != "candidate"
                or not cold_records or bootstrap_proof.get("ledger_absent")
                or bootstrap_proof.get("generation_matches_ledger") is not True
                or not any(record.get("runner_fence_record_sha256") ==
                           bootstrap_proof.get("ledger_record_sha256")
                           for record in cold_records)):
            raise SnapshotContractError("candidate-live recovery lacks its durable authentic cold bootstrap receipt")
    configuration_state = transaction["configuration_state"]
    observed_configurations = {path: _config_fingerprint(path)[0] for path in configuration_state}
    backup_records = transaction.get("configuration_backup_records")
    if not isinstance(backup_records, dict):
        raise SnapshotContractError("recovery configuration journal is malformed")
    if layout["live"] == "candidate":
        if any(observed_configurations[path] != state["expected_new"]
               for path, state in configuration_state.items()):
            raise SnapshotContractError(
                "candidate snapshot is live but its complete candidate configuration set is not exact")
    else:
        # The candidate is not live, so restore the exact predecessor configuration set.
        # This handles a crash between sequential per-file installs without guessing forward.
        if backup_records:
            if set(backup_records) != set(configuration_state):
                raise SnapshotContractError("recovery has an incomplete per-file predecessor journal")
            restore_predecessor_configurations(transaction)
            observed_configurations = {path: _config_fingerprint(path)[0]
                                       for path in configuration_state}
        for path, state in configuration_state.items():
            expected = state["expected_current"]
            if path in PREINSTALLED_GUARD_PATHS and expected.get("state") == "absent":
                expected = state["expected_new"]
            if observed_configurations[path] != expected:
                raise SnapshotContractError("predecessor configuration recovery did not reach its exact state")
    safe_head, safe_tree = ((TASK_HEAD, TASK_TREE) if layout["live"] == "candidate"
                            else (transaction["old_head"], transaction["old_tree_sha1"]))
    proof = _verify_git_readonly(transaction["live_path"]) if layout["live"] == "candidate" else {
        "head": safe_head, "tree_sha1": safe_tree, "status_clean": True,
    }
    if (proof.get("head"), proof.get("tree_sha1")) != (safe_head, safe_tree):
        raise SnapshotContractError("recovery live tree changed during exact identity verification")
    if transaction.get("marker_present"):
        identity = transaction.get("marker_identity")
        if not isinstance(identity, tuple) or len(identity) != 2:
            raise SnapshotContractError("recovery lacks an exact marker inode identity")
        if not any((record.get("marker_device"), record.get("marker_inode")) == identity
                   for record in transaction.get("records", [])):
            if transaction.get("state") != "GUARDS_VERIFIED":
                raise SnapshotContractError("unrecorded marker appeared after transaction mutation began")
            _append_journal(
                transaction["journal_path"], transaction, "MARKER_DURABLE",
                marker_device=identity[0], marker_inode=identity[1],
                recovery_observed_marker=True)
            transaction["state"] = "MARKER_DURABLE"
        if transaction.get("state") not in {"ACTIVATION_READY", "RECOVERY_REQUIRED"}:
            record_state(transaction, transaction["state"], "RECOVERY_REQUIRED",
                         reason="explicit recovery reconciled the exact safe configuration and snapshot")
        if transaction.get("state") == "RECOVERY_REQUIRED":
            record_state(
                transaction, "RECOVERY_REQUIRED", "ACTIVATION_READY",
            safe_tree=layout["live"], safe_head=safe_head, safe_tree_sha1=safe_tree,
            recovery_reconciled=True, live_location=layout["live"],
            old_location=layout["old_location"], candidate_location=layout["candidate_location"],
            runtime_masks_retained=True, configuration_set_sha256=hashlib.sha256(
                _canonical(observed_configurations)).hexdigest())
        elif transaction.get("state") != "ACTIVATION_READY":
            raise SnapshotContractError("recovery cannot advance the durable transaction state")
        clear_durable_marker(transaction["marker_path"], transaction["transaction_id"], identity)
        transaction["marker_present"] = False
        record = _append_journal(transaction["journal_path"], transaction, "MARKER_CLEARED",
                                 marker_absent=True, runtime_masks_retained=True,
                                 safe_tree=layout["live"])
        transaction["state"] = record["state"]
    elif transaction.get("state") == "RECOVERY_REQUIRED":
        record_state(transaction, "RECOVERY_REQUIRED", "ACTIVATION_READY",
                     recovery_reconciled=True, safe_tree=layout["live"],
                     safe_head=safe_head, safe_tree_sha1=safe_tree,
                     runtime_masks_retained=True,
                     configuration_set_sha256=hashlib.sha256(
                         _canonical(observed_configurations)).hexdigest())
        record = _append_journal(transaction["journal_path"], transaction, "MARKER_CLEARED",
                                 marker_absent=True, runtime_masks_retained=True,
                                 recovery_observed_marker_absence=True, safe_tree=layout["live"])
        transaction["state"] = record["state"]
    elif transaction.get("state") == "ACTIVATION_READY":
        record = _append_journal(transaction["journal_path"], transaction, "MARKER_CLEARED",
                                 marker_absent=True, runtime_masks_retained=True,
                                 recovery_observed_marker_absence=True,
                                 safe_tree=layout["live"])
        transaction["state"] = record["state"]
    return {"safe_tree": layout["live"], "safe_head": safe_head, "safe_tree_sha1": safe_tree,
            "marker_present": transaction.get("marker_present", False),
            "runtime_masks_must_remain": True,
            "old_location": layout["old_location"],
            "candidate_location": layout["candidate_location"]}


def record_state(transaction: dict[str, Any], expected_state: str, next_state: str,
                 **facts: Any) -> None:
    if transaction.get("state") != expected_state:
        raise SnapshotContractError("transaction state transition is not permitted")
    if next_state not in _TRANSITIONS.get(expected_state, set()):
        raise SnapshotContractError("transaction transition is absent from the reviewed state machine")
    _append_journal(transaction["journal_path"], transaction, next_state, **facts)
    transaction["state"] = next_state


def record_fenced(transaction: dict[str, Any], masks: dict[str, Any]) -> None:
    if set(masks) != {"vst-runner.service", "vst-dispatcher.service"}:
        raise SnapshotContractError("transaction mask inventory is incomplete")
    for value in masks.values():
        if (not isinstance(value, dict) or set(value) != {"device", "inode", "target"}
                or value.get("target") != "/dev/null"
                or type(value.get("device")) is not int or value["device"] < 0
                or type(value.get("inode")) is not int or value["inode"] < 0):
            raise SnapshotContractError("runtime mask lacks its exact filesystem inode identity")
    record_state(transaction, "FENCING", "FENCED", runtime_masks=masks,
                 configuration_backups=transaction.get("configuration_backup_records", {}))


def ensure_runtime_mask(transaction: dict[str, Any], unit: str,
                        runtime_mask_paths_before: dict[str, Any]) -> dict[str, Any]:
    """Publish one exact transaction mask only after its inode is durably journaled."""
    units = {"vst-runner.service", "vst-dispatcher.service"}
    if (unit not in units or set(runtime_mask_paths_before) != units
            or transaction.get("state") != "FENCING"
            or not _HEX32.fullmatch(str(transaction.get("transaction_id", "")))):
        raise SnapshotContractError("runtime mask publication is outside the exact FENCING transaction")
    parent = "/run/systemd/system"
    parent_info = os.lstat(parent)
    if (not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode)
            or parent_info.st_uid != 0 or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) & 0o022):
        raise SnapshotContractError("systemd runtime directory is not root-controlled")
    destination = os.path.join(parent, unit)
    staged = os.path.join(parent, ".vst-s2-mask-" + transaction["transaction_id"]
                          + "-" + unit + ".pending")

    def identity(path: str) -> dict[str, Any] | None:
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return None
        if (not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
                or info.st_nlink != 1 or os.readlink(path) != "/dev/null"):
            raise SnapshotContractError("runtime mask or transaction staging symlink is not exact")
        return {"device": info.st_dev, "inode": info.st_ino, "target": "/dev/null"}

    records = _read_journal(transaction["journal_path"])
    intents = [record.get("runtime_mask_paths_before") for record in records
               if record.get("state") == "FENCING"
               and isinstance(record.get("runtime_mask_paths_before"), dict)]
    if not intents or intents[-1] != runtime_mask_paths_before:
        raise SnapshotContractError("runtime mask publication lacks its exact durable fence intent")
    latest_fencing = next((record for record in reversed(records)
                           if record.get("state") == "FENCING"), None)
    prior_prepared = (latest_fencing.get("prepared_runtime_masks", {})
                      if isinstance(latest_fencing, dict) else {})
    prepared = dict(prior_prepared)
    existing = identity(destination)
    if existing is not None:
        expected = prepared.get(unit, runtime_mask_paths_before[unit])
        if existing != expected:
            raise SnapshotContractError("runtime mask inode is not the recorded predecessor or staged inode")
        return existing

    staged_identity = identity(staged)
    staged_preexisting = staged_identity is not None
    if staged_identity is None:
        os.symlink("/dev/null", staged)
        _fsync_dir(parent)
        staged_identity = identity(staged)
        if staged_identity is None:
            raise SnapshotContractError("staged runtime mask disappeared before durable identity capture")
    if unit in prepared and prepared[unit] != staged_identity:
        if staged_preexisting:
            raise SnapshotContractError("staged runtime mask differs from its durable inode identity")
        # A reboot may clear the volatile directory after the prior inode was journaled.
        # Persistent start guards remain effective; bind the replacement before publication.
        prepared[unit] = staged_identity
        _append_journal(transaction["journal_path"], transaction, "FENCING",
                        runtime_mask_paths_before=runtime_mask_paths_before,
                        prepared_runtime_masks=prepared,
                        reboot_replaced_runtime_mask=True)
    elif unit not in prepared:
        prepared[unit] = staged_identity
        _append_journal(transaction["journal_path"], transaction, "FENCING",
                        runtime_mask_paths_before=runtime_mask_paths_before,
                        prepared_runtime_masks=prepared)

    _renameat2_file(staged, destination, 1)
    published = identity(destination)
    if published != prepared[unit]:
        raise SnapshotContractError("published runtime mask differs from its durable staged inode")
    latest_fencing = next((record for record in reversed(records)
                           if record.get("state") == "FENCING"), None)
    published_masks = (latest_fencing.get("published_runtime_masks", {})
                       if isinstance(latest_fencing, dict) else {})
    published_masks = dict(published_masks)
    published_masks[unit] = published
    _append_journal(transaction["journal_path"], transaction, "FENCING",
                    runtime_mask_paths_before=runtime_mask_paths_before,
                    prepared_runtime_masks=prepared,
                    published_runtime_masks=published_masks)
    return published


def _config_fingerprint(path: str) -> tuple[dict[str, Any], bytes | None]:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return {"state": "absent"}, None
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_nlink != 1):
        raise SnapshotContractError("configuration backup source is linked or non-regular")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                or opened.st_nlink != 1):
            raise SnapshotContractError("configuration source changed while opening for backup")
        chunks = bytearray()
        while len(chunks) <= 1024 * 1024:
            part = os.read(fd, min(65536, 1024 * 1024 + 1 - len(chunks)))
            if not part:
                break
            chunks.extend(part)
        if len(chunks) > 1024 * 1024:
            raise SnapshotContractError("configuration backup source exceeds the one-MiB per-file limit")
        data = bytes(chunks)
        final = os.fstat(fd)
        if ((final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) !=
                (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
                or len(data) != final.st_size):
            raise SnapshotContractError("configuration source changed during backup")
    finally:
        os.close(fd)
    return ({"state": "file", "uid": info.st_uid, "gid": info.st_gid,
             "mode": stat.S_IMODE(info.st_mode), "size": len(data),
             "sha256": hashlib.sha256(data).hexdigest()}, data)


def backup_configurations(transaction: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    if transaction.get("state") != "MARKER_DURABLE" or len(files) != 27:
        raise SnapshotContractError("configuration backup requires a durable marker and exact file set")
    expected_paths = set(transaction["configuration_state"])
    if {item.get("destination") for item in files} != expected_paths:
        raise SnapshotContractError("configuration backup input differs from the journaled path set")
    backup_root = os.path.join(transaction["journal_dir"], "config-backups")
    try:
        os.mkdir(backup_root, 0o700)
        os.chown(backup_root, 0, 0)
        os.chmod(backup_root, 0o700)
        _fsync_dir(transaction["journal_dir"])
    except FileExistsError:
        pass
    backup_info = os.lstat(backup_root)
    if (not stat.S_ISDIR(backup_info.st_mode) or stat.S_ISLNK(backup_info.st_mode)
            or backup_info.st_uid != 0 or backup_info.st_gid != 0
            or stat.S_IMODE(backup_info.st_mode) != 0o700):
        raise SnapshotContractError("configuration backup directory is unsafe")
    import base64
    records: dict[str, Any] = {}
    staged_total = 0
    backup_total = 0
    for item in files:
        path = item["destination"]
        state = transaction["configuration_state"][path]
        prior = state["expected_current"]
        target = state["expected_new"]
        try:
            new_data = base64.b64decode(item["content_b64"], validate=True)
        except (KeyError, ValueError, base64.binascii.Error) as exc:
            raise SnapshotContractError("candidate configuration bytes are malformed") from exc
        if (len(new_data) != target.get("size")
                or hashlib.sha256(new_data).hexdigest() != target.get("sha256")
                or b"PRIVATE KEY-----" in new_data):
            raise SnapshotContractError("candidate configuration differs from its exact non-secret pin")
        staged_total += len(new_data)
        if staged_total > 8 * 1024 * 1024:
            raise SnapshotContractError("configuration transaction payload exceeds its fixed aggregate limit")
        path_digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        candidate_path = os.path.join(backup_root, path_digest + ".new")
        try:
            candidate_fd = os.open(candidate_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            candidate_state, candidate_data = _config_fingerprint(candidate_path)
            if (candidate_data != new_data or candidate_state.get("uid") != 0
                    or candidate_state.get("gid") != 0 or candidate_state.get("mode") != 0o600):
                raise SnapshotContractError("existing candidate configuration payload differs")
        else:
            try:
                os.fchown(candidate_fd, 0, 0)
                os.fchmod(candidate_fd, 0o600)
                _write_all(candidate_fd, new_data)
                os.fsync(candidate_fd)
            finally:
                os.close(candidate_fd)
            _fsync_dir(backup_root)
        current, data = _config_fingerprint(path)
        predecessor_backup: str | None = None
        if current == prior and prior != target:
            if prior.get("state") == "file":
                if data is None or b"PRIVATE KEY-----" in data:
                    raise SnapshotContractError("configuration predecessor is absent or contains private-key material")
                backup_total += len(data)
                if backup_total > 8 * 1024 * 1024:
                    raise SnapshotContractError("configuration predecessor backups exceed their fixed aggregate limit")
                backup_path = os.path.join(backup_root, path_digest + ".old")
                try:
                    fd = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                except FileExistsError:
                    backup_state, old_data = _config_fingerprint(backup_path)
                    if (old_data != data or backup_state.get("uid") != 0 or backup_state.get("gid") != 0
                            or backup_state.get("mode") != 0o600):
                        raise SnapshotContractError("existing config backup differs from the exact predecessor")
                else:
                    try:
                        os.fchown(fd, 0, 0)
                        os.fchmod(fd, 0o600)
                        _write_all(fd, data)
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    _fsync_dir(backup_root)
                predecessor_backup = backup_path
            elif prior.get("state") != "absent":
                raise SnapshotContractError("configuration predecessor state is invalid")
        elif current == target and prior != target:
            if (prior.get("state") == "absent"
                    and path not in PREINSTALLED_GUARD_PATHS):
                raise SnapshotContractError(
                    "candidate configuration appeared at a non-guard path before this transaction installed it")
            if prior.get("state") == "file":
                backup_path = os.path.join(backup_root, path_digest + ".old")
                backup_state, backup_data = _config_fingerprint(backup_path)
                if (backup_data is None or backup_state.get("sha256") != prior.get("sha256")
                        or backup_state.get("size") != prior.get("size")
                        or backup_state.get("uid") != 0 or backup_state.get("gid") != 0
                        or backup_state.get("mode") != 0o600):
                    raise SnapshotContractError("configuration predecessor backup differs from its exact journal pin")
                backup_total += len(backup_data)
                if backup_total > 8 * 1024 * 1024:
                    raise SnapshotContractError("configuration predecessor backups exceed their fixed aggregate limit")
                predecessor_backup = backup_path
            elif prior.get("state") != "absent":
                raise SnapshotContractError("configuration predecessor state is invalid")
        elif current != prior or current != target:
            raise SnapshotContractError("configuration source is outside its journaled old/new state: " + path)
        records[path] = {"predecessor_backup": predecessor_backup,
                         "expected_current": prior, "candidate_payload": candidate_path,
                         "candidate_sha256": target["sha256"],
                         "candidate_size": target["size"],
                         "expected_new": target}
    transaction["configuration_backup_records"] = records
    _append_journal(transaction["journal_path"], transaction, "MARKER_DURABLE",
                    configuration_backups=records)
    return records


def _renameat2_file(source: str, destination: str, flags: int) -> None:
    if os.path.dirname(source) != os.path.dirname(destination):
        raise SnapshotContractError("configuration publication must stay in one parent directory")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise SnapshotContractError("libc renameat2 is unavailable for safe config publication")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), flags) != 0:
        error = ctypes.get_errno()
        raise SnapshotContractError("atomic configuration publication failed: " + os.strerror(error))
    _fsync_dir(os.path.dirname(source))


def _install_recovery_configuration(transaction: dict[str, Any], destination: str) -> None:
    records = transaction.get("configuration_backup_records")
    if not isinstance(records, dict) or destination not in records:
        raise SnapshotContractError("recovery lacks its durable candidate configuration payload")
    record = records[destination]
    state = transaction["configuration_state"][destination]
    prior, target = state["expected_current"], state["expected_new"]
    payload_path = record.get("candidate_payload")
    payload_state, payload = _config_fingerprint(payload_path)
    if (payload is None or payload_state.get("uid") != 0 or payload_state.get("gid") != 0
            or payload_state.get("mode") != 0o600 or len(payload) != target["size"]
            or hashlib.sha256(payload).hexdigest() != target["sha256"]
            or record.get("candidate_sha256") != target["sha256"]
            or record.get("candidate_size") != target["size"]):
        raise SnapshotContractError("durable candidate configuration payload differs from its pin")
    parent = os.path.dirname(destination)
    parent_info = os.lstat(parent)
    if (not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode)
            or parent_info.st_uid != 0 or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) & 0o022):
        raise SnapshotContractError("recovery configuration parent is not root-controlled")
    path_digest = hashlib.sha256(destination.encode("utf-8")).hexdigest()
    temporary = os.path.join(parent, ".vst-s2-recovery-" + transaction["transaction_id"]
                             + "-" + path_digest + ".tmp")
    current = _config_fingerprint(destination)[0]
    temporary_state: dict[str, Any] | None = None
    temporary_info = None
    if os.path.lexists(temporary):
        temporary_state, temporary_data = _config_fingerprint(temporary)
        temporary_info = os.lstat(temporary)
        if (temporary_data not in (payload, None)
                or temporary_state.get("uid") != 0 or temporary_state.get("gid") != 0
                or temporary_state.get("mode") not in (0o600, target["mode"], prior.get("mode"))):
            raise SnapshotContractError("recovery temporary path contains unexpected data")
    if current == target:
        if temporary_info is not None and temporary_state == prior:
            backup_path = record.get("predecessor_backup")
            backup_state, backup_data = _config_fingerprint(backup_path) if backup_path else ({"state": "absent"}, None)
            if (prior.get("state") != "file" or backup_data is None
                    or backup_state.get("sha256") != prior.get("sha256")
                    or backup_state.get("size") != prior.get("size")):
                raise SnapshotContractError("retained predecessor is not backed by its exact journal copy")
            os.unlink(temporary)
            _fsync_dir(parent)
        elif temporary_info is not None:
            raise SnapshotContractError("recovery temporary path is not the exact displaced predecessor")
        return
    if current != prior:
        raise SnapshotContractError("configuration changed outside the exact old/new recovery states")
    if temporary_info is None:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchown(fd, target["uid"], target["gid"])
            os.fchmod(fd, target["mode"])
            _write_all(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(parent)
        temporary_info = os.lstat(temporary)
    elif temporary_state != target:
        raise SnapshotContractError("recovery staging file is neither exact new content nor a retained old file")
    if prior.get("state") == "absent":
        _renameat2_file(temporary, destination, 1)
        if _config_fingerprint(destination)[0] != target:
            raise SnapshotContractError("recovered absent-only configuration differs after publication")
        return
    backup_path = record.get("predecessor_backup")
    backup_state, backup_data = _config_fingerprint(backup_path) if backup_path else ({"state": "absent"}, None)
    if (backup_data is None or backup_state.get("sha256") != prior.get("sha256")
            or backup_state.get("size") != prior.get("size")
            or backup_state.get("uid") != 0 or backup_state.get("gid") != 0
            or backup_state.get("mode") != 0o600):
        raise SnapshotContractError("configuration predecessor backup is not durable or exact")
    predecessor_info = os.lstat(destination)
    new_info = os.lstat(temporary)
    _renameat2_file(temporary, destination, 2)
    published = os.lstat(destination)
    displaced = os.lstat(temporary)
    if ((published.st_dev, published.st_ino) != (new_info.st_dev, new_info.st_ino)
            or (displaced.st_dev, displaced.st_ino) != (predecessor_info.st_dev, predecessor_info.st_ino)
            or _config_fingerprint(destination)[0] != target
            or _config_fingerprint(temporary)[0] != prior):
        raise SnapshotContractError("configuration exchange is ambiguous; both versions are retained")
    os.unlink(temporary)
    _fsync_dir(parent)


def finish_candidate_configurations(transaction: dict[str, Any]) -> None:
    records = transaction.get("configuration_backup_records")
    if not isinstance(records, dict) or set(records) != set(transaction["configuration_state"]):
        raise SnapshotContractError("recovery journal lacks all 27 candidate configuration payloads")
    for destination in sorted(records):
        _install_recovery_configuration(transaction, destination)


def _install_predecessor_configuration(transaction: dict[str, Any], destination: str) -> None:
    records = transaction.get("configuration_backup_records")
    if not isinstance(records, dict) or destination not in records:
        raise SnapshotContractError("recovery lacks the exact predecessor configuration record")
    record = records[destination]
    state = transaction["configuration_state"][destination]
    prior, target = state["expected_current"], state["expected_new"]
    if destination in PREINSTALLED_GUARD_PATHS and prior.get("state") == "absent":
        prior = target
    parent = os.path.dirname(destination)
    parent_info = os.lstat(parent)
    if (not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode)
            or parent_info.st_uid != 0 or parent_info.st_gid != 0
            or stat.S_IMODE(parent_info.st_mode) & 0o022):
        raise SnapshotContractError("recovery configuration parent is not root-controlled")
    path_digest = hashlib.sha256(destination.encode("utf-8")).hexdigest()
    temporary = os.path.join(
        parent, ".vst-s2-rollback-" + transaction["transaction_id"] + "-" + path_digest + ".tmp")
    quarantine = os.path.join(
        parent, ".vst-s2-recovery-" + transaction["transaction_id"] + "-" + path_digest + ".rollback")
    current = _config_fingerprint(destination)[0]
    if current == prior:
        leftover = quarantine if prior.get("state") == "absent" else temporary
        if os.path.lexists(leftover):
            leftover_state, _ = _config_fingerprint(leftover)
            if leftover_state != target:
                raise SnapshotContractError("recovery cleanup path contains data outside the exact candidate")
            os.unlink(leftover)
            _fsync_dir(parent)
        return
    if current != target:
        raise SnapshotContractError("configuration differs from both exact predecessor and candidate")
    if prior.get("state") == "absent":
        if os.path.lexists(quarantine):
            raise SnapshotContractError("predecessor rollback quarantine path is occupied")
        original = os.lstat(destination)
        _renameat2_file(destination, quarantine, 1)
        moved = os.lstat(quarantine)
        if ((moved.st_dev, moved.st_ino) != (original.st_dev, original.st_ino)
                or _config_fingerprint(quarantine)[0] != target):
            try:
                _renameat2_file(quarantine, destination, 1)
            except SnapshotContractError:
                pass
            raise SnapshotContractError("rollback moved an unexpected concurrent configuration; preserved")
        os.unlink(quarantine)
        _fsync_dir(parent)
        if _config_fingerprint(destination)[0] != {"state": "absent"}:
            raise SnapshotContractError("candidate-only configuration remains after rollback")
        return
    backup_path = record.get("predecessor_backup")
    backup_state, backup_data = _config_fingerprint(backup_path) if isinstance(backup_path, str) else ({"state": "absent"}, None)
    if (backup_data is None or backup_state.get("uid") != 0 or backup_state.get("gid") != 0
            or backup_state.get("mode") != 0o600
            or backup_state.get("size") != prior.get("size")
            or backup_state.get("sha256") != prior.get("sha256")):
        raise SnapshotContractError("durable predecessor bytes differ from the exact journal pin")
    if os.path.lexists(temporary):
        staged_state, staged_data = _config_fingerprint(temporary)
        if (staged_data != backup_data or staged_state.get("uid") != prior.get("uid")
                or staged_state.get("gid") != prior.get("gid")
                or staged_state.get("mode") != prior.get("mode")):
            raise SnapshotContractError("rollback staging path contains unexpected data")
    else:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchown(fd, prior["uid"], prior["gid"])
            os.fchmod(fd, prior["mode"])
            _write_all(fd, backup_data)
            os.fsync(fd)
        finally:
            os.close(fd)
        _fsync_dir(parent)
    displaced_before = os.lstat(destination)
    staged_before = os.lstat(temporary)
    _renameat2_file(temporary, destination, 2)
    displaced_after = os.lstat(temporary)
    installed_after = os.lstat(destination)
    if ((displaced_after.st_dev, displaced_after.st_ino) !=
            (displaced_before.st_dev, displaced_before.st_ino)
            or (installed_after.st_dev, installed_after.st_ino) !=
            (staged_before.st_dev, staged_before.st_ino)
            or _config_fingerprint(temporary)[0] != target
            or _config_fingerprint(destination)[0] != prior):
        raise SnapshotContractError("rollback exchange is ambiguous; both versions are retained")
    os.unlink(temporary)
    _fsync_dir(parent)


def restore_predecessor_configurations(transaction: dict[str, Any]) -> None:
    records = transaction.get("configuration_backup_records")
    if not isinstance(records, dict) or set(records) != set(transaction["configuration_state"]):
        raise SnapshotContractError("recovery journal lacks all 27 predecessor configuration records")
    for destination in sorted(records):
        _install_predecessor_configuration(transaction, destination)


def record_dispatcher_drained(transaction: dict[str, Any], *, inactive: bool,
                              cgroup_empty: bool, invocation_id: str) -> None:
    if not inactive or not cgroup_empty or not invocation_id:
        raise SnapshotContractError("Dispatcher drain is not positively verified")
    record_state(transaction, "FENCED", "DISPATCHER_DRAINED",
                 dispatcher_inactive=True, dispatcher_cgroup_empty=True,
                 dispatcher_invocation_id=invocation_id)


def record_runner_stopped_empty(transaction: dict[str, Any], *, inactive: bool,
                                cgroup_empty: bool, fence_record: dict[str, Any]) -> None:
    if (not inactive or not cgroup_empty or fence_record.get("state") != "STOPPED_EMPTY"
            or fence_record.get("unit") != "vst-runner.service"
            or not _HEX32.fullmatch(str(fence_record.get("invocation_id", "")))):
        raise SnapshotContractError("Runner has no exact fresh STOPPED_EMPTY fence evidence")
    record_state(transaction, "DISPATCHER_DRAINED", "RUNNER_STOPPED_EMPTY",
                 runner_inactive=True, runner_cgroup_empty=True,
                 runner_fence_record_sha256=hashlib.sha256(_canonical(fence_record)).hexdigest(),
                 runner_invocation_id=fence_record["invocation_id"])


def _rename_noreplace(source: str, destination: str) -> None:
    if os.path.dirname(source) != os.path.dirname(destination) or os.path.lexists(destination):
        raise SnapshotContractError("retention path is occupied or not a direct sibling")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise SnapshotContractError("libc renameat2 is unavailable; no-replace rename is forbidden")
    renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise SnapshotContractError("predecessor retention failed without overwrite: " + os.strerror(error))
    _fsync_dir(os.path.dirname(source))


def exchange_candidate(transaction: dict[str, Any], *, recovery_path: str,
                       marker_path: str) -> None:
    """Exchange once, retain old root, prove both identities, and journal activation readiness."""
    source_state = transaction.get("state")
    if source_state not in {"RUNNER_STOPPED_EMPTY", "RUNNER_BOOTSTRAP_EMPTY"}:
        raise SnapshotContractError("snapshot exchange requires an exact Runner empty-state receipt")
    receipt = None
    if source_state == "RUNNER_BOOTSTRAP_EMPTY":
        if transaction.get("activation_state") != {
                "vst-runner.service": False, "vst-dispatcher.service": False}:
            raise SnapshotContractError("cold snapshot exchange requires both services originally inactive")
        records = _read_journal(transaction["journal_path"])
        receipt = next((record for record in reversed(records)
                        if record.get("state") == "RUNNER_BOOTSTRAP_EMPTY"), None)
        if receipt is None:
            raise SnapshotContractError("cold snapshot exchange lacks its durable bootstrap receipt")
        current = _cold_proof_current(receipt.get("cold_predecessor_proof"), allow_missing=False)
        if (receipt.get("runner_fence_record_sha256") != current.get("ledger_record_sha256")
                or current.get("generation_matches_ledger") is not True):
            raise SnapshotContractError("cold snapshot exchange evidence no longer matches the authentic ledger")
        _journal_masks(transaction)
        _verify_bootstrap_guards(transaction)
    transaction_id = transaction["transaction_id"]
    expected_recovery = (transaction["recovery_prefix"] +
                         transaction["old_head"] + "-" + transaction_id)
    if recovery_path != expected_recovery:
        raise SnapshotContractError("predecessor path differs from the fixed retention contract")
    old_identity = (transaction["old_device"], transaction["old_inode"])
    candidate_identity = (transaction["candidate_device"], transaction["candidate_inode"])
    if os.path.lexists(recovery_path):
        raise SnapshotContractError("predecessor retention path is occupied")
    exchange_directories(transaction["live_path"], transaction["stage_path"])
    record_state(transaction, source_state, "EXCHANGED",
                 exchange_syscall="renameat2(RENAME_EXCHANGE)",
                 cold_bootstrap_record_sha256=(None if receipt is None else
                                               receipt.get("runner_fence_record_sha256")))
    live = os.lstat(transaction["live_path"])
    stage = os.lstat(transaction["stage_path"])
    if ((live.st_dev, live.st_ino) != candidate_identity
            or (stage.st_dev, stage.st_ino) != old_identity):
        record_state(transaction, "EXCHANGED", "RECOVERY_REQUIRED",
                     reason="exchange path identities do not match the exact preflight")
        raise SnapshotContractError("exchange result is ambiguous; both trees and guard remain")
    try:
        proof = _verify_git_readonly(transaction["live_path"])
    except BaseException as exc:
        record_state(transaction, "EXCHANGED", "RECOVERY_REQUIRED",
                     reason="post-exchange read-only Git verification raised " + type(exc).__name__)
        raise SnapshotContractError("post-exchange Git verification failed; marker and both trees remain") from exc
    if proof["head"] != TASK_HEAD or proof["tree_sha1"] != TASK_TREE:
        record_state(transaction, "EXCHANGED", "RECOVERY_REQUIRED",
                     reason="post-exchange candidate failed exact Git verification")
        raise SnapshotContractError("post-exchange candidate failed verification; marker and both trees remain")
    _rename_noreplace(transaction["stage_path"], recovery_path)
    retained = os.lstat(recovery_path)
    if (retained.st_dev, retained.st_ino) != old_identity:
        record_state(transaction, "EXCHANGED", "RECOVERY_REQUIRED",
                     reason="retained predecessor identity differs")
        raise SnapshotContractError("predecessor retention identity is ambiguous")
    record_state(transaction, "EXCHANGED", "OLD_RETAINED", recovery_path=recovery_path,
                 recovery_device=retained.st_dev, recovery_inode=retained.st_ino,
                 candidate_readonly_git_proof=proof)
    try:
        current_identity = _tree_identity(transaction["live_path"])
    except BaseException as exc:
        record_state(transaction, "OLD_RETAINED", "RECOVERY_REQUIRED",
                     reason="retained target Git identity raised " + type(exc).__name__)
        raise SnapshotContractError("candidate identity is ambiguous; marker and both trees remain") from exc
    if current_identity[:2] != (TASK_HEAD, TASK_TREE):
        record_state(transaction, "OLD_RETAINED", "RECOVERY_REQUIRED",
                     reason="candidate identity changed after predecessor retention")
        raise SnapshotContractError("candidate identity is ambiguous; marker and both trees remain")
    record_state(transaction, "OLD_RETAINED", "TARGET_VERIFIED",
                 target_verified=True, predecessor_retained=True)
    record_state(transaction, "TARGET_VERIFIED", "ACTIVATION_READY",
                 safe_tree="candidate", safe_head=TASK_HEAD, safe_tree_sha1=TASK_TREE)
    marker_identity = transaction.get("marker_identity")
    if not isinstance(marker_identity, tuple) or len(marker_identity) != 2:
        raise SnapshotContractError("transaction does not own the exact durable marker identity")
    clear_durable_marker(marker_path, transaction_id, marker_identity)
    transaction["state"] = "MARKER_CLEARED"
    _append_journal(transaction["journal_path"], transaction, "MARKER_CLEARED",
                    marker_absent=True, runtime_masks_retained=True)


def rollback_candidate(transaction: dict[str, Any], *, recovery_path: str,
                       marker_path: str, guards_verified: dict[str, bool],
                       runtime_masks_owned: dict[str, dict[str, Any]],
                       services_quiesced: dict[str, bool]) -> None:
    """Restore only the exact predecessor with one exchange; retain the failed candidate."""
    state = transaction.get("state")
    if state not in {"EXCHANGED", "OLD_RETAINED", "TARGET_VERIFIED", "RECOVERY_REQUIRED"}:
        raise SnapshotContractError("rollback is not valid from this durable transaction state")
    units = {"vst-runner.service", "vst-dispatcher.service"}
    recorded_masks = next((record.get("runtime_masks") for record in reversed(
        transaction.get("records", [])) if isinstance(record.get("runtime_masks"), dict)), None)
    masks_match = isinstance(recorded_masks, dict) and set(recorded_masks) == units
    if masks_match:
        masks_match = all(runtime_masks_owned.get(unit) == recorded_masks[unit]
                          and isinstance(recorded_masks[unit], dict)
                          and set(recorded_masks[unit]) == {"device", "inode", "target"}
                          and recorded_masks[unit].get("target") == "/dev/null"
                          for unit in units)
    if (guards_verified != {unit: True for unit in units}
            or not masks_match or services_quiesced != {unit: True for unit in units}):
        raise SnapshotContractError("rollback requires verified persistent guards, owned masks and quiescence")
    for destination, state_record in transaction["configuration_state"].items():
        expected_config = state_record["expected_current"]
        if (destination in PREINSTALLED_GUARD_PATHS
                and expected_config.get("state") == "absent"):
            expected_config = state_record["expected_new"]
        if _config_fingerprint(destination)[0] != expected_config:
            raise SnapshotContractError("rollback refuses a mixed or changed configuration set")
    if marker_path != transaction["marker_path"] or recovery_path != transaction["recovery_path"]:
        raise SnapshotContractError("rollback marker or predecessor path differs from the journal")
    marker_identity = transaction.get("marker_identity")
    if not isinstance(marker_identity, tuple) or len(marker_identity) != 2:
        raise SnapshotContractError("rollback lacks the exact durable marker identity")
    verify_durable_marker(marker_path, transaction["transaction_id"], marker_identity)
    layout = reconcile_snapshot_paths(transaction)
    if layout["live"] != "candidate":
        raise SnapshotContractError("rollback requires the exact candidate at the live path")
    old_path = layout["old_path"]
    failed_path = old_path
    old = os.lstat(old_path)
    live = os.lstat(transaction["live_path"])
    if ((old.st_dev, old.st_ino) != (transaction["old_device"], transaction["old_inode"])
            or (live.st_dev, live.st_ino) !=
               (transaction["candidate_device"], transaction["candidate_inode"])):
        record_state(transaction, state, "RECOVERY_REQUIRED",
                     reason="rollback paths do not uniquely match old/candidate inode identities")
        raise SnapshotContractError("rollback identity is ambiguous; both snapshots and marker remain")
    exchange_directories(transaction["live_path"], old_path)
    restored = os.lstat(transaction["live_path"])
    failed = os.lstat(failed_path)
    if ((restored.st_dev, restored.st_ino) != (transaction["old_device"], transaction["old_inode"])
            or (failed.st_dev, failed.st_ino) !=
               (transaction["candidate_device"], transaction["candidate_inode"])):
        record_state(transaction, state, "RECOVERY_REQUIRED",
                     reason="rollback exchange result does not match recorded inode identities")
        raise SnapshotContractError("rollback exchange is ambiguous; marker and paths remain")
    old_identity = _tree_identity(transaction["live_path"])
    if old_identity[:2] != (transaction["old_head"], transaction["old_tree_sha1"]):
        record_state(transaction, state, "RECOVERY_REQUIRED",
                     reason="restored predecessor Git identity differs from its recorded baseline")
        raise SnapshotContractError("restored predecessor does not match the recorded Git identity")
    record_state(transaction, state, "ROLLBACK_EXCHANGED",
                 safe_tree="predecessor", failed_candidate_path=failed_path,
                 failed_candidate_device=failed.st_dev, failed_candidate_inode=failed.st_ino,
                 restored_head=transaction["old_head"],
                 restored_tree_sha1=transaction["old_tree_sha1"])
    record_state(transaction, "ROLLBACK_EXCHANGED", "ACTIVATION_READY",
                 safe_tree="predecessor", safe_head=transaction["old_head"],
                 safe_tree_sha1=transaction["old_tree_sha1"])
    clear_durable_marker(marker_path, transaction["transaction_id"], marker_identity)
    transaction["state"] = "MARKER_CLEARED"
    _append_journal(transaction["journal_path"], transaction, "MARKER_CLEARED",
                    marker_absent=True, runtime_masks_retained=True, safe_tree="predecessor")


def mark_activation_restored(transaction: dict[str, Any], *, runner_verified: bool,
                             dispatcher_verified: bool, original_activation: dict[str, bool]) -> None:
    if transaction.get("state") != "MARKER_CLEARED":
        raise SnapshotContractError("service restoration requires durable marker clearance")
    if set(original_activation) != {"vst-runner.service", "vst-dispatcher.service"}:
        raise SnapshotContractError("original service activation state is incomplete")
    if original_activation["vst-runner.service"] and not runner_verified:
        raise SnapshotContractError("previously active Runner did not verify its new generation")
    if original_activation["vst-dispatcher.service"] and not dispatcher_verified:
        raise SnapshotContractError("previously active Dispatcher was not verified after Runner")
    _append_journal(transaction["journal_path"], transaction, "ACTIVATION_RESTORED",
                    runner_verified=runner_verified, dispatcher_verified=dispatcher_verified,
                    original_activation=original_activation)
    transaction["state"] = "ACTIVATION_RESTORED"

