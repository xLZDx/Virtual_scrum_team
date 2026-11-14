"""Router mode, state and concurrency side (LINK2-T5, design docs/sdlc/LINK2_ROUTER_DESIGN.md D2, D4, D5, D6).

`route_task` carries one story through the router flow and returns a `RouterRow`:

    NEW -> (aeve packet) -> AWAITING_RESULT -> (host result copied) -> RESULT_COPIED -> (aeve verify-handoff) -> DONE

- It refuses with ROUTER_NOT_SELECTED unless `link_mode.resolve(mode_path).mode` is `router`.
- Work directory: `<state_root>/router/<task_id>/<request_sha256[:16]>-pending/` holds `claim.lock`, `state.json`,
  `request.json` and `packet.json`; the host result is copied to `<task_id>/<request_sha256[:16]>-<result_sha256[:16]>/
  result.json` and the AEVE report is written beside the copy as `report.json`. `request_sha256` here is the SHA-256 of
  the canonical request bytes computed by VST; the opaque value AEVE puts in the packet is stored as `aeve_request_sha256`.
- Claim: `claim.lock` is created with O_CREAT|O_EXCL, content `{owner, created_at}` (owner is a random token, never a
  pid). A claim older than `claim_stale_seconds` is renamed to a unique name (atomic) and the taker creates its own claim;
  the takeover is logged. The wait is bounded (`lock_wait_seconds`), expiry is ROUTER_LOCK_TIMEOUT. The loser of two
  concurrent runs therefore waits, then finds the recorded state and adopts it.
- Slots: at most `max_slots` AEVE subprocesses at once across callers, counted with slot files taken by the same rule.
- Result intake: the host result is read once (size cap), written as a VST-owned copy and the COPY is hashed; AEVE only
  ever sees the copies. A copy that changes afterwards gives ROUTER_RESULT_DIGEST_MISMATCH.
- Resume: a recorded verdict is adopted only when the packet, result copy and report digests and the pin head ALL match
  the files and the current pin; otherwise verify-handoff is re-run (read only). Each resume logs `adopted` or `rerun`.
  A step error never changes the recorded state (it only adds `last_error`), so a retry resumes where it stopped.
- `router.log.jsonl`: one line per step with task_id, request_sha256, step, outcome, retry_count, resume, claim_takeover.
  No packet, result or environment content.

Atomic writes use `link_mode.replace_with_retry`. Standard library only, besides the router modules.
"""

from __future__ import annotations

import json
import os
import pathlib
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Mapping

from . import link_mode
from . import router_aeve_cli as rac
from . import router_request as rr
from .router_request import RouterError

STATE_SCHEMA = "vst.router_state.v1"
NEW = "NEW"
AWAITING_RESULT = "AWAITING_RESULT"
RESULT_COPIED = "RESULT_COPIED"
DONE = "DONE"
STATES = (NEW, AWAITING_RESULT, RESULT_COPIED, DONE)

ROUTER_NOT_SELECTED = "ROUTER_NOT_SELECTED"
ROUTER_LOCK_TIMEOUT = "ROUTER_LOCK_TIMEOUT"
ROUTER_RESULT_DIGEST_MISMATCH = "ROUTER_RESULT_DIGEST_MISMATCH"

ROUTER_DIRNAME = "router"
CLAIM_NAME = "claim.lock"
STATE_NAME = "state.json"
LOG_NAME = "router.log.jsonl"
SLOTS_DIRNAME = "_slots"
AEVE_STATE_DIRNAME = "_aeve_state"
MAX_RESULT_BYTES = 1024 * 1024  # D5 cap for the host result


@dataclass(frozen=True)
class RouterConfig:
    """Tunables (design D4, D5: configuration, not contracts). The injectable callables exist for tests."""

    python: str | None = None
    command_prefix: list[str] | None = None
    timeout: float = rac.DEFAULT_TIMEOUT_SECONDS
    max_retries: int = rac.DEFAULT_MAX_RETRIES
    jitter: tuple[float, float] = rac.DEFAULT_JITTER_SECONDS
    claim_stale_seconds: float = 600.0
    lock_wait_seconds: float = 60.0
    poll_seconds: float = 0.5
    max_slots: int = 2
    tmp_max_age_seconds: float = 3600.0
    blocked_retention_seconds: float = 14 * 86400.0
    max_result_bytes: int = MAX_RESULT_BYTES
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False)
    clock: Callable[[], float] = field(default=time.time, compare=False)
    monotonic: Callable[[], float] = field(default=time.monotonic, compare=False)


@dataclass(frozen=True)
class RouterRow:
    """The routed result of one story. `state` is AWAITING_RESULT (no verdict yet) or DONE (verdict recorded)."""

    state: str
    outcome: str | None  # ROUTED_VERIFIED, ROUTED_REJECTED, ROUTED_UNKNOWN, ROUTER_INVALID_INPUT; None while awaiting
    status: str | None  # the AEVE status as reported
    task_id: str
    request_sha256: str
    aeve_request_sha256: str | None
    packet_sha256: str | None
    result_sha256: str | None
    report_sha256: str | None
    pin_head: str
    packet_path: str
    work_dir: str
    resume: str  # adopted, rerun or none
    reason: str  # AEVE reason for INVALID, else ""

    def to_report(self) -> dict[str, Any]:
        """The row for `build_final_package(router_report=...)` (design D2, pinned in T4a)."""
        return {
            "outcome": self.outcome, "status": self.status, "task_id": self.task_id,
            "request_sha256": self.request_sha256, "packet_sha256": self.packet_sha256,
            "result_sha256": self.result_sha256, "report_sha256": self.report_sha256, "pin_head": self.pin_head,
        }


# ------------------------------------------------------------------ files
def _sha(data: bytes) -> str:
    return rr.sha256_hex(data)


def _write_atomic(path: pathlib.Path, data: bytes) -> None:
    """Temp file in the same directory, flush, fsync, os.replace through link_mode.replace_with_retry."""
    temp = path.with_name(f"{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        with open(temp, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        link_mode.replace_with_retry(str(temp), path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def _read_bytes(path: pathlib.Path, cap: int) -> bytes | None:
    """Bytes of a file, None when missing; ROUTER_SIZE_CAP when longer than `cap`."""
    try:
        with open(path, "rb") as stream:
            data = stream.read(cap + 1)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RouterError(rac.ROUTER_STATE_DIR_UNUSABLE, f"cannot read a router file ({type(exc).__name__})") from exc
    if len(data) > cap:
        raise RouterError(rr.ROUTER_SIZE_CAP, f"a router file exceeds {cap} bytes")
    return data


def _file_sha(path: pathlib.Path) -> str | None:
    data = _read_bytes(path, rr.MAX_PACKET_BYTES)
    return None if data is None else _sha(data)


def _mkdir(path: pathlib.Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RouterError(rac.ROUTER_STATE_DIR_UNUSABLE, f"cannot create a router directory ({type(exc).__name__})") from exc


def _unlink(path: pathlib.Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ------------------------------------------------------------------ claim and slots (O_EXCL files with an owner token)
def _create_exclusive(path: pathlib.Path, token: str, now: float) -> bool:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    except OSError as exc:
        raise RouterError(rac.ROUTER_STATE_DIR_UNUSABLE, f"cannot create a lock file ({type(exc).__name__})") from exc
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(json.dumps({"owner": token, "created_at": now}).encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        _unlink(path)
        raise
    return True


def _read_claim(path: pathlib.Path) -> dict[str, Any] | None:
    """{owner, created_at} of a lock file; None when it is gone. A torn file falls back to its mtime (owner None)."""
    try:
        raw = path.read_bytes()
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return None
    except OSError:
        return {"owner": None, "created_at": time.time()}
    try:
        data = json.loads(raw.decode("ascii"))
        owner, created = data["owner"], float(data["created_at"])
        if isinstance(owner, str):
            return {"owner": owner, "created_at": created}
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        pass
    return {"owner": None, "created_at": mtime}


def _try_acquire(path: pathlib.Path, token: str, cfg: RouterConfig) -> tuple[bool, bool]:
    """One non-blocking attempt: (got it, took over a stale claim). A stale claim is renamed away atomically first."""
    takeover = False
    for _ in range(3):
        if _create_exclusive(path, token, cfg.clock()):
            return True, takeover
        seen = _read_claim(path)
        if seen is None:
            continue
        if cfg.clock() - seen["created_at"] <= cfg.claim_stale_seconds:
            return False, False
        unique = path.with_name(f"{path.name}.stale-{token}")
        try:
            link_mode.replace_with_retry(str(path), unique)
        except FileNotFoundError:
            continue
        except OSError:
            return False, False
        if _read_claim(unique) != seen:  # we renamed a claim that was taken fresh in between: put it back
            try:
                os.link(unique, path)
            except OSError:
                pass
            _unlink(unique)
            return False, False
        _unlink(unique)
        takeover = True
    return False, takeover


def _release(path: pathlib.Path, token: str) -> None:
    seen = _read_claim(path)
    if seen is not None and seen["owner"] == token:
        _unlink(path)


@contextmanager
def _held(paths: list[pathlib.Path], cfg: RouterConfig, what: str) -> Iterator[tuple[pathlib.Path, bool]]:
    """Hold the first free lock file of `paths`; wait (bounded) for one. Yields (path, took_over_a_stale_claim)."""
    token = secrets.token_hex(16)
    deadline = cfg.monotonic() + cfg.lock_wait_seconds
    while True:
        for path in paths:
            got, takeover = _try_acquire(path, token, cfg)
            if got:
                try:
                    yield path, takeover
                finally:
                    _release(path, token)
                return
        if cfg.monotonic() >= deadline:
            raise RouterError(ROUTER_LOCK_TIMEOUT, f"{what}: no lock within {cfg.lock_wait_seconds:g} s")
        cfg.sleep(cfg.poll_seconds)


# ------------------------------------------------------------------ log, sweep, retention
def _log(router_root: pathlib.Path, cfg: RouterConfig, **fields: Any) -> None:
    """One JSON line; never raises (a log failure must not change a routing result)."""
    line = {"at": round(cfg.clock(), 3), **fields}
    try:
        with open(router_root / LOG_NAME, "ab") as stream:
            stream.write((json.dumps(line, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii"))
    except OSError:
        pass


def _is_link(path: str) -> bool:
    return os.path.islink(path) or bool(getattr(os.path, "isjunction", lambda _p: False)(path))


def _remove_tree(path: pathlib.Path, router_root: pathlib.Path) -> bool:
    """Delete `path` only when it lies strictly inside `router_root` and holds no link or junction. True when gone."""
    try:
        root = router_root.resolve()
        target = path.resolve()
        if target == root or root not in target.parents or _is_link(str(path)):
            return False
        walk = list(os.walk(path, topdown=False, followlinks=False))
        if any(_is_link(os.path.join(base, name)) for base, dirs, files in walk for name in dirs + files):
            return False
        for base, dirs, files in walk:
            for name in files:
                os.unlink(os.path.join(base, name))
            for name in dirs:
                os.rmdir(os.path.join(base, name))
        os.rmdir(path)
        return True
    except OSError:
        return False


def _is_blocked(state: Mapping[str, Any]) -> bool:
    return bool(state.get("last_error")) or (state.get("state") == DONE and state.get("outcome") != "ROUTED_VERIFIED")


def sweep(router_root: pathlib.Path, cfg: RouterConfig) -> dict[str, int]:
    """Remove `*.tmp` files older than `tmp_max_age_seconds` and BLOCKED work directories older than
    `blocked_retention_seconds`. Touches only paths under `router_root`; a directory with a claim is skipped."""
    counts = {"tmp": 0, "blocked_dirs": 0}
    now = cfg.clock()
    try:
        for base, dirs, files in os.walk(router_root, followlinks=False):
            dirs[:] = [name for name in dirs if name != AEVE_STATE_DIRNAME]  # AEVE's own files are not ours to sweep
            for name in files:
                full = os.path.join(base, name)
                if name.endswith(".tmp") and not _is_link(full) and now - os.stat(full).st_mtime > cfg.tmp_max_age_seconds:
                    os.unlink(full)
                    counts["tmp"] += 1
        for task_dir in list(router_root.iterdir()):
            if task_dir.name.startswith("_") or not task_dir.is_dir() or _is_link(str(task_dir)):
                continue
            for pending in list(task_dir.iterdir()):
                if not pending.name.endswith("-pending") or (pending / CLAIM_NAME).exists():
                    continue
                state_path = pending / STATE_NAME
                if not state_path.is_file() or now - state_path.stat().st_mtime <= cfg.blocked_retention_seconds:
                    continue
                try:
                    state = json.loads(state_path.read_text(encoding="ascii"))
                except (OSError, ValueError):
                    continue
                if not isinstance(state, dict) or not _is_blocked(state):
                    continue
                prefix = pending.name[: -len("pending")]
                for sibling in list(task_dir.iterdir()):
                    if sibling.name.startswith(prefix) and _remove_tree(sibling, router_root):
                        counts["blocked_dirs"] += 1
    except OSError:
        pass
    return counts


def release_work_dir(state_root: str | os.PathLike, task_id: str, request_sha256: str,
                     cfg: RouterConfig = RouterConfig()) -> int:
    """Delete the work directories of one request after the story's final package is built (D5). Returns how many."""
    if not isinstance(task_id, str) or not rr.TASK_ID_RE.match(task_id) or len(request_sha256) != 64:
        raise RouterError(rr.ROUTER_BAD_REQUEST, "task_id or request_sha256 is malformed")
    router_root = pathlib.Path(state_root) / ROUTER_DIRNAME
    task_dir = router_root / task_id
    removed = 0
    if task_dir.is_dir():
        for child in list(task_dir.iterdir()):
            if child.name.startswith(request_sha256[:16] + "-") and _remove_tree(child, router_root):
                removed += 1
        try:
            task_dir.rmdir()
        except OSError:
            pass
    return removed


# ------------------------------------------------------------------ the flow
class _Run:
    def __init__(self, request: Mapping[str, Any], payload: bytes, state_root: pathlib.Path, aeve_root: pathlib.Path,
                 root: pathlib.Path, result_source: pathlib.Path | None, pin_head: str, cfg: RouterConfig) -> None:
        self.request, self.payload, self.cfg = request, payload, cfg
        self.task_id = request["task_id"]
        self.request_sha = _sha(payload)
        self.aeve_root, self.root, self.result_source, self.pin_head = aeve_root, root, result_source, pin_head
        self.router_root = state_root / ROUTER_DIRNAME
        self.task_dir = self.router_root / self.task_id
        self.base = self.task_dir / f"{self.request_sha[:16]}-pending"
        self.takeover = False
        self.resume = "none"
        self.state: dict[str, Any] = {}

    # -- state file
    def _log(self, step: str, outcome: str, retries: int = 0) -> None:
        _log(self.router_root, self.cfg, task_id=self.task_id, request_sha256=self.request_sha, step=step,
             outcome=outcome, retry_count=retries, resume=self.resume, claim_takeover=self.takeover)

    def _load(self) -> None:
        raw = _read_bytes(self.base / STATE_NAME, 64 * 1024)
        state = None
        if raw is not None:
            try:
                parsed = rr.parse_strict_json_object(raw, "state")
                if (parsed.get("schema") == STATE_SCHEMA and parsed.get("state") in STATES
                        and parsed.get("task_id") == self.task_id and parsed.get("request_sha256") == self.request_sha):
                    state = parsed
            except RouterError:
                state = None
            if state is None:
                self._log("state", "STATE_TORN_TREATED_AS_NEW")
        self.state = state or {"schema": STATE_SCHEMA, "state": NEW, "task_id": self.task_id,
                               "request_sha256": self.request_sha, "pin_head": self.pin_head, "last_error": None}

    def _save(self, **updates: Any) -> None:
        self.state.update(updates)
        self.state["updated_at"] = round(self.cfg.clock(), 3)
        _write_atomic(self.base / STATE_NAME, (json.dumps(self.state, ensure_ascii=True, sort_keys=True) + "\n").encode("ascii"))

    def _advance(self, **updates: Any) -> None:
        self._save(last_error=None, **updates)

    def _fail(self, exc: RouterError) -> None:
        try:
            self._save(last_error={"reason": exc.reason, "at": round(self.cfg.clock(), 3)})
        except (OSError, RouterError):
            pass

    def _slot_paths(self) -> list[pathlib.Path]:
        slots = self.router_root / SLOTS_DIRNAME
        _mkdir(slots)
        return [slots / f"slot-{i}.lock" for i in range(self.cfg.max_slots)]

    # -- steps
    def _packet_ok(self) -> bool:
        recorded = self.state.get("packet_sha256")
        return bool(recorded) and _file_sha(self.base / "packet.json") == recorded

    def _step_packet(self, next_state: str = AWAITING_RESULT) -> None:
        recorded_packet, recorded_aeve = self.state.get("packet_sha256"), self.state.get("aeve_request_sha256")
        try:
            with _held(self._slot_paths(), self.cfg, "aeve slot"):
                result = rac.run_packet(
                    self.request, aeve_root=self.aeve_root, state_dir=self.router_root / AEVE_STATE_DIRNAME,
                    pin_head=self.pin_head, python=self.cfg.python, command_prefix=self.cfg.command_prefix,
                    timeout=self.cfg.timeout, max_retries=self.cfg.max_retries, jitter=self.cfg.jitter,
                    sleep=self.cfg.sleep)
        except RouterError as exc:
            self._log("packet", exc.reason, exc.retry_count)
            raise
        if (recorded_packet and recorded_packet != result.packet_sha256) or (
                recorded_aeve and recorded_aeve != result.packet["request_sha256"]):
            self._log("packet", rr.ROUTER_BAD_OUTPUT, result.retry_count)
            raise RouterError(rr.ROUTER_BAD_OUTPUT, "a re-run packet differs from the recorded packet (not deterministic)")
        _write_atomic(self.base / "packet.json", result.packet_bytes)
        self._advance(state=next_state, packet_sha256=result.packet_sha256,
                      aeve_request_sha256=result.packet["request_sha256"], pin_head=self.pin_head)
        self._log("packet", "OK", result.retry_count)

    def _result_dir(self, result_sha: str) -> pathlib.Path:
        return self.task_dir / f"{self.request_sha[:16]}-{result_sha[:16]}"

    def _step_copy(self) -> bool:
        """Copy the host result when a new one is present. True when a copy was made."""
        source = self.result_source
        if source is None:
            return False
        data = _read_bytes(pathlib.Path(source), self.cfg.max_result_bytes)
        if data is None:
            return False
        wanted = _sha(data)
        if self.state.get("state") == DONE and wanted == self.state.get("result_sha256"):
            return False  # the recorded verdict is for this very result
        directory = self._result_dir(wanted)
        _mkdir(directory)
        copy = directory / "result.json"
        _write_atomic(copy, data)
        copied = _file_sha(copy)  # hash THE COPY
        if copied is None:
            raise RouterError(rac.ROUTER_STATE_DIR_UNUSABLE, "the result copy is missing after the write")
        self._advance(state=RESULT_COPIED, result_sha256=copied, result_dir=directory.name, report_sha256=None,
                      outcome=None, status=None, reason="")
        self._log("result_copy", "OK")
        return True

    def _result_path(self) -> pathlib.Path:
        return self.task_dir / self.state["result_dir"] / "result.json"

    def _ensure_packet(self) -> dict[str, Any]:
        if not self._packet_ok():
            self._step_packet(self.state["state"])  # a re-run packet must not move the recorded state
        raw = _read_bytes(self.base / "packet.json", rr.MAX_PACKET_BYTES)
        assert raw is not None
        return rr.validate_packet(raw, self.request)

    def _step_verify(self) -> None:
        packet = self._ensure_packet()
        result_path = self._result_path()
        if _file_sha(result_path) != self.state.get("result_sha256"):
            self._log("verify", ROUTER_RESULT_DIGEST_MISMATCH)
            raise RouterError(ROUTER_RESULT_DIGEST_MISMATCH, "the result copy differs from the recorded digest")
        result_raw = _read_bytes(result_path, self.cfg.max_result_bytes)
        assert result_raw is not None
        try:
            rr.parse_strict_json_object(result_raw, "result")
        except RouterError as exc:
            self._log("verify", exc.reason)
            raise
        try:
            with _held(self._slot_paths(), self.cfg, "aeve slot"):
                verdict = rac.run_verify_handoff(
                    self.base / "packet.json", result_path, packet, root=self.root, aeve_root=self.aeve_root,
                    state_dir=self.router_root / AEVE_STATE_DIRNAME, pin_head=self.pin_head, python=self.cfg.python,
                    command_prefix=self.cfg.command_prefix, timeout=self.cfg.timeout, max_retries=self.cfg.max_retries,
                    jitter=self.cfg.jitter, sleep=self.cfg.sleep)
        except RouterError as exc:
            self._log("verify", exc.reason, exc.retry_count)
            raise
        if _file_sha(result_path) != self.state.get("result_sha256"):  # changed while AEVE read it
            self._log("verify", ROUTER_RESULT_DIGEST_MISMATCH, verdict.retry_count)
            raise RouterError(ROUTER_RESULT_DIGEST_MISMATCH, "the result copy changed during verify-handoff")
        _write_atomic(result_path.with_name("report.json"), verdict.report_bytes)
        self._advance(state=DONE, outcome=verdict.outcome, status=verdict.status, report_sha256=verdict.report_sha256,
                      reason=verdict.reason, pin_head=self.pin_head)
        self._log("verify", verdict.outcome, verdict.retry_count)

    def _done_matches(self) -> list[str]:
        """Names of the recorded facts that no longer match the files and the current pin (empty: adopt)."""
        bad = []
        if self.state.get("pin_head") != self.pin_head:
            bad.append("pin_head")
        if not self._packet_ok():
            bad.append("packet_sha256")
        result_dir = self.state.get("result_dir")
        if not isinstance(result_dir, str) or "/" in result_dir or "\\" in result_dir or ".." in result_dir:
            return bad + ["result_dir"]
        base = self.task_dir / result_dir
        if _file_sha(base / "result.json") != self.state.get("result_sha256"):
            bad.append("result_sha256")
        if _file_sha(base / "report.json") != self.state.get("report_sha256"):
            bad.append("report_sha256")
        if self.state.get("outcome") not in rac.OUTCOME_FOR_STATUS.values() or self.state.get("status") not in rac.EXIT_FOR_STATUS:
            bad.append("row")
        return bad

    def run(self) -> RouterRow:
        self._load()
        if self.state["state"] == NEW:
            self._step_packet()
        copied = False
        if self.state["state"] in (AWAITING_RESULT, DONE):
            copied = self._step_copy()
        if self.state["state"] == RESULT_COPIED:
            # RESULT_COPIED found on entry means a crash between copy and verdict: verify-handoff is re-run (read only)
            self.resume = "none" if copied else "rerun"
            if self.resume == "rerun":
                self._log("resume", "rerun")
            self._step_verify()
        elif self.state["state"] == DONE:
            mismatched = self._done_matches()
            self.resume = "rerun" if mismatched else "adopted"
            self._log("resume", self.resume)
            if mismatched:
                self._step_verify()
        return self._row()

    def _row(self) -> RouterRow:
        state = self.state
        done = state["state"] == DONE
        result_dir = state.get("result_dir")
        return RouterRow(
            state=DONE if done else AWAITING_RESULT, outcome=state.get("outcome") if done else None,
            status=state.get("status") if done else None, task_id=self.task_id, request_sha256=self.request_sha,
            aeve_request_sha256=state.get("aeve_request_sha256"), packet_sha256=state.get("packet_sha256"),
            result_sha256=state.get("result_sha256") if done else None,
            report_sha256=state.get("report_sha256") if done else None, pin_head=self.pin_head,
            packet_path=str(self.base / "packet.json"),
            work_dir=str(self.task_dir / result_dir) if done and isinstance(result_dir, str) else str(self.base),
            resume=self.resume, reason=state.get("reason") or "" if done else "")


def route_task(
    request: Mapping[str, Any],
    *,
    state_root: str | os.PathLike,
    aeve_root: str | os.PathLike,
    root: str | os.PathLike,
    result_source: str | os.PathLike | None = None,
    pin_head: str | None = None,
    mode_path: str | os.PathLike = link_mode.DEFAULT_PATH,
    config: RouterConfig = RouterConfig(),
) -> RouterRow:
    """Carry one story one step further and return its row. Raises RouterError (ROUTER_* code) when a step fails.

    `request` comes from `router_request.build_request`. `root` is the worktree given to `--root`. `result_source` is the
    host session's result file (read once, copied); None or a missing file leaves the row AWAITING_RESULT, which is a
    normal wait and makes no AEVE call.
    """
    try:
        selected = link_mode.resolve(mode_path).mode == link_mode.MODE_ROUTER
    except link_mode.LinkModeError as exc:
        raise RouterError(ROUTER_NOT_SELECTED, f"link mode unreadable ({exc.code})") from exc
    if not selected:
        raise RouterError(ROUTER_NOT_SELECTED, "the current link mode is not router")
    if (not isinstance(request, Mapping) or request.get("schema_version") != rr.REQUEST_SCHEMA
            or request.get("role") not in rr.ROUTER_ROLES or not isinstance(request.get("task_id"), str)
            or not rr.TASK_ID_RE.match(request["task_id"])):
        raise RouterError(rr.ROUTER_BAD_REQUEST, "request is not a router task packet request")
    pin = pin_head if pin_head is not None else rac.load_pin_head()
    run = _Run(request, rr.request_bytes(request), pathlib.Path(state_root), pathlib.Path(aeve_root),
               pathlib.Path(root), None if result_source is None else pathlib.Path(result_source), pin, config)
    _mkdir(run.base)
    _mkdir(run.router_root / AEVE_STATE_DIRNAME)
    sweep(run.router_root, config)
    with _held([run.base / CLAIM_NAME], config, "claim") as (_path, takeover):
        run.takeover = takeover
        if takeover:
            run._log("claim", "STALE_CLAIM_TAKEN_OVER")
        try:
            return run.run()
        except RouterError as exc:
            run._fail(exc)
            raise
        except OSError as exc:
            blocked = RouterError(rac.ROUTER_STATE_DIR_UNUSABLE, f"router file error ({type(exc).__name__})")
            run._fail(blocked)
            raise blocked from exc
