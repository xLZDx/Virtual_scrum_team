"""Link mode switch: how VST works with AEVE (skeleton, see docs/sdlc/LINK_MODE.md).

Two modes are declared in `catalog/link_mode.json` (schema `vst.link_mode.v1`):

- `gates`: VST owns the gates, receipts and the review loop (the U1-U6 scheme). Available.
- `router`: AEVE does the checks and VST only routes AEVE reports. Declared but NOT available: it needs AEVE
  S20-T07 (task packet) and S20-T08 (handoff verifier). It refuses to be selected and no router behaviour exists.

Fail closed: a missing, unreadable, malformed or inconsistent file, a duplicate JSON key, an unknown key, a wrong
type, an unknown mode name, or a current mode that is not a known AVAILABLE mode raises `LinkModeError` with a
reason code. `set_mode` refuses an unknown or unavailable mode without touching the file, and writes the new file
atomically (temp file in the same directory, then `os.replace`, with a small bounded retry for the brief Windows
PermissionError winerror 5/32). Two concurrent `set_mode` calls are last-writer-wins; each write is whole.

The availability of `router` is pinned in CODE (`ROUTER_CAPABILITY_READY`), not in the data file: while it is False,
`load` rejects a file that marks router available, and `set_mode` refuses router before it reads the file's flag.
Strings that cannot be encoded as UTF-8 (lone surrogates) and a UTF-8 BOM are rejected. A symlink or junction at the
catalog path is followed on read (acceptable: the CLI path is a repo constant).

Reads and writes only the one given path (and its temp sibling). Standard library only; no network, no subprocess.
CLI: `python -m tools.vst.link_mode get` or `set <mode>`; prints one JSON line, exit 0 ok, 1 refusal, 2 usage, 3 internal error.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = "vst.link_mode.v1"
MODE_GATES = "gates"
MODE_ROUTER = "router"
KNOWN_MODES = (MODE_GATES, MODE_ROUTER)
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "catalog" / "link_mode.json"

# reason codes
UNKNOWN_MODE = "UNKNOWN_MODE"
MODE_UNAVAILABLE = "MODE_UNAVAILABLE"
CATALOG_UNREADABLE = "CATALOG_UNREADABLE"
CATALOG_INVALID = "CATALOG_INVALID"
WRITE_FAILED = "WRITE_FAILED"

# Flips to True only together with the reviewed router implementation (AEVE S20-T07 and S20-T08 in place).
# Never derive it from the data file.
ROUTER_CAPABILITY_READY = False
ROUTER_BLOCKED_REASON = "ROUTER_REQUIRES_AEVE_TASK_PACKET_AND_HANDOFF_VERIFIER"
ROUTER_REQUIRES = ("AEVE S20-T07", "AEVE S20-T08")

_TOP_KEYS = frozenset({"schema", "mode", "modes"})
_AVAILABLE_KEYS = frozenset({"available", "description"})
_BLOCKED_KEYS = frozenset({"available", "description", "blocked_reason", "requires"})
_RETRY_WINERRORS = (5, 32)
_RETRY_ATTEMPTS = 5
_RETRY_DELAY_SECONDS = 0.05


class LinkModeError(Exception):
    """A refusal or a failure; `code` is one of the reason codes above. Detail never holds file content."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ModeEntry:
    name: str
    available: bool
    description: str
    blocked_reason: str | None = None
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class LinkModeConfig:
    mode: str
    modes: tuple[ModeEntry, ...]

    def entry(self, name: str) -> ModeEntry | None:
        for item in self.modes:
            if item.name == name:
                return item
        return None


@dataclass(frozen=True)
class ResolvedMode:
    """The current mode. `reason` is None for an available mode (an unavailable one can never be current)."""

    mode: str
    available: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        return {"mode": self.mode, "available": self.available, "reason": self.reason}


def _invalid(detail: str) -> LinkModeError:
    return LinkModeError(CATALOG_INVALID, detail)


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_name: str) -> object:
    raise ValueError("non-finite number")


def _text(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _parse_entry(name: str, raw: object) -> ModeEntry:
    if not isinstance(raw, dict):
        raise _invalid(f"mode {name} must be an object")
    available = raw.get("available")
    if type(available) is not bool:
        raise _invalid(f"mode {name}: available must be a bool")
    expected = _AVAILABLE_KEYS if available else _BLOCKED_KEYS
    if set(raw) != expected:
        raise _invalid(f"mode {name}: keys must be exactly {sorted(expected)}")
    if not _text(raw["description"]):
        raise _invalid(f"mode {name}: description must be a non-empty string")
    if available:
        return ModeEntry(name, True, raw["description"])
    requires = raw["requires"]
    if not _text(raw["blocked_reason"]):
        raise _invalid(f"mode {name}: blocked_reason must be a non-empty string")
    if (not isinstance(requires, list) or not requires or not all(_text(item) for item in requires)
            or len(set(requires)) != len(requires)):
        raise _invalid(f"mode {name}: requires must be a non-empty list of distinct strings")
    if name == MODE_ROUTER and (raw["blocked_reason"] != ROUTER_BLOCKED_REASON or tuple(requires) != ROUTER_REQUIRES):
        raise _invalid("mode router: blocked_reason and requires must match the pinned values")
    return ModeEntry(name, False, raw["description"], raw["blocked_reason"], tuple(requires))


def _parse(text: str) -> LinkModeConfig:
    try:
        data = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise _invalid(f"not valid JSON without duplicate keys ({type(exc).__name__})") from None
    if not isinstance(data, dict) or set(data) != _TOP_KEYS:
        raise _invalid(f"top level must be an object with exactly the keys {sorted(_TOP_KEYS)}")
    if data["schema"] != SCHEMA:
        raise _invalid(f"schema must be {SCHEMA}")
    mode, modes = data["mode"], data["modes"]
    if not _text(mode):
        raise _invalid("mode must be a non-empty string that encodes as UTF-8")
    if not isinstance(modes, dict) or set(modes) != set(KNOWN_MODES):
        raise _invalid(f"modes must hold exactly {list(KNOWN_MODES)}")
    entries = tuple(_parse_entry(name, modes[name]) for name in KNOWN_MODES)
    if not entries[0].available:
        raise _invalid("mode gates must be available")
    if entries[1].available and not ROUTER_CAPABILITY_READY:
        raise _invalid("mode router cannot be available: the router capability is not ready in code")
    config = LinkModeConfig(mode, entries)
    current = config.entry(mode)
    if current is None:
        raise _invalid("the current mode is not a known mode")
    if not current.available:
        raise _invalid("the current mode is not an available mode")
    return config


def load(path: str | os.PathLike = DEFAULT_PATH) -> LinkModeConfig:
    """Read and validate the catalog file. Raises LinkModeError (CATALOG_UNREADABLE or CATALOG_INVALID)."""
    try:
        raw = Path(path).read_bytes()
    except (OSError, TypeError, ValueError) as exc:
        raise LinkModeError(CATALOG_UNREADABLE, f"the file could not be read ({type(exc).__name__})") from None
    if raw.startswith(b"\xef\xbb\xbf"):
        raise _invalid("the file starts with a UTF-8 BOM; write it without a BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _invalid("the file is not UTF-8") from None
    return _parse(text)


def resolve(path: str | os.PathLike = DEFAULT_PATH) -> ResolvedMode:
    """The current mode, its availability and the reason (None when available)."""
    config = load(path)
    current = config.entry(config.mode)
    assert current is not None  # load() guarantees it
    return ResolvedMode(current.name, current.available, current.blocked_reason)


def _replace_with_retry(source: str, target: Path) -> None:
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in _RETRY_WINERRORS or attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_DELAY_SECONDS)


def _write_atomic(path: Path, data: bytes) -> None:
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)  # bytes: LF endings on every platform
            stream.flush()
            os.fsync(stream.fileno())
        _replace_with_retry(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def set_mode(path: str | os.PathLike, new_mode: str) -> ResolvedMode:
    """Make `new_mode` current. Refuses (LinkModeError, file unchanged) with UNKNOWN_MODE or MODE_UNAVAILABLE.

    A file that does not validate is refused too (CATALOG_UNREADABLE / CATALOG_INVALID). A failed write raises
    WRITE_FAILED and leaves the old file in place.
    """
    if new_mode == MODE_ROUTER and not ROUTER_CAPABILITY_READY:
        raise LinkModeError(MODE_UNAVAILABLE, ROUTER_BLOCKED_REASON)
    config = load(path)
    if not isinstance(new_mode, str) or config.entry(new_mode) is None:
        raise LinkModeError(UNKNOWN_MODE, f"known modes: {', '.join(KNOWN_MODES)}")
    target = config.entry(new_mode)
    assert target is not None
    if not target.available:
        raise LinkModeError(MODE_UNAVAILABLE, target.blocked_reason or "")
    if config.mode != new_mode:
        document = {"schema": SCHEMA, "mode": new_mode, "modes": {}}
        for item in config.modes:
            body: dict = {"available": item.available, "description": item.description}
            if not item.available:
                body["blocked_reason"] = item.blocked_reason
                body["requires"] = list(item.requires)
            document["modes"][item.name] = body
        try:
            data = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
            _write_atomic(Path(path), data)
        except (OSError, ValueError) as exc:
            raise LinkModeError(WRITE_FAILED, f"the file could not be written ({type(exc).__name__})") from None
    return ResolvedMode(target.name, True, None)


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args == ["get"]:
            _emit({"ok": True, **resolve(DEFAULT_PATH).to_dict()})
            return 0
        if len(args) == 2 and args[0] == "set":
            _emit({"ok": True, **set_mode(DEFAULT_PATH, args[1]).to_dict()})
            return 0
    except LinkModeError as exc:
        _emit({"ok": False, "code": exc.code, "detail": exc.detail})
        return 1
    except Exception:  # noqa: BLE001 - fail closed, never echo the message
        _emit({"ok": False, "code": "INTERNAL", "detail": "unexpected internal error"})
        return 3
    _emit({"ok": False, "code": "USAGE", "detail": "usage: link_mode get | link_mode set <mode>"})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
