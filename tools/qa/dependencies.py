"""Offline preparation and content verification for the S4 QA wheel set."""

from __future__ import annotations

import base64
import csv
import email.parser
import hashlib
import io
import json
import os
import re
import stat
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_LOCK_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[A-Za-z0-9_.+-]+)(?:;\s*sys_platform\s*==\s*\"(?P<platform>[A-Za-z0-9_]+)\")?\s+\\$"
)
_HASH_LINE = re.compile(r"^\s+--hash=sha256:([0-9a-f]{64})\s*$")
_WHEEL_NAME = re.compile(r"[A-Za-z0-9_.+-]+\.whl\Z")
MAX_WHEEL_BYTES = 64 * 1024 * 1024
MAX_TARGET_FILE_BYTES = 64 * 1024 * 1024


class DependencyProvenanceError(ValueError):
    """Raised when the locked wheel set or installed target is not exact."""


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def is_link_or_junction(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _canonical_lock(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n")


@dataclass(frozen=True)
class LockedWheel:
    name: str
    version: str
    platform: str | None
    sha256: str


@dataclass(frozen=True)
class VerifiedWheel:
    name: str
    version: str
    sha256: str
    files: dict[str, bytes]


def _locked_wheels(lock_path: Path, platform_name: str = sys.platform) -> tuple[str, list[LockedWheel]]:
    try:
        raw = lock_path.read_bytes()
        lines = raw.decode("utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise DependencyProvenanceError(f"QA dependency lock is unavailable ({type(exc).__name__})") from None
    if not lines or not lines[0].startswith("# Wheel-only, exact hashes"):
        raise DependencyProvenanceError("QA dependency lock header is invalid")
    rows: list[LockedWheel] = []
    pending: tuple[str, str, str | None] | None = None
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            continue
        if pending is None:
            match = _LOCK_LINE.fullmatch(line)
            if match is None:
                raise DependencyProvenanceError("QA dependency lock syntax is invalid")
            pending = (
                _normalize_name(match.group("name")),
                match.group("version"),
                match.group("platform"),
            )
            continue
        hash_match = _HASH_LINE.fullmatch(line)
        if hash_match is None:
            raise DependencyProvenanceError("every locked wheel must have exactly one SHA-256 pin")
        rows.append(LockedWheel(*pending, hash_match.group(1)))
        pending = None
    if pending is not None:
        raise DependencyProvenanceError("QA dependency lock ends without a wheel hash")
    selected = [row for row in rows if row.platform is None or row.platform == platform_name]
    names = [row.name for row in selected]
    if len(names) != len(set(names)) or "pytest" not in names:
        raise DependencyProvenanceError("QA dependency lock has duplicate packages or no pytest pin")
    return hashlib.sha256(_canonical_lock(raw)).hexdigest(), selected


def locked_wheel_manifest(lock_path: Path, platform_name: str) -> list[dict[str, str]]:
    _, rows = _locked_wheels(lock_path, platform_name)
    return [
        {"name": row.name, "version": row.version, "sha256": row.sha256}
        for row in rows
    ]


def _safe_member(name: str) -> str:
    if (
        not name
        or "\\" in name
        or name.startswith("/")
        or "\x00" in name
        or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
        or ":" in name
    ):
        raise DependencyProvenanceError("wheel contains a non-canonical member path")
    return name.rstrip("/")


def _wheel_snapshot(path: Path) -> tuple[str, bytes]:
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise DependencyProvenanceError("wheelhouse entry is not a unique regular file")
            if info.st_size < 0 or info.st_size > MAX_WHEEL_BYTES:
                raise DependencyProvenanceError("wheel archive exceeds the supported size bound")
            content = handle.read(MAX_WHEEL_BYTES + 1)
            if len(content) != info.st_size or len(content) > MAX_WHEEL_BYTES:
                raise DependencyProvenanceError("wheel archive changed while being read")
    except OSError as exc:
        raise DependencyProvenanceError(f"locked wheel is unavailable ({type(exc).__name__})") from None
    return hashlib.sha256(content).hexdigest(), content


def _wheel_file_map(filename: str, content: bytes, locked: LockedWheel) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members: dict[str, bytes] = {}
            for info in archive.infolist():
                relative = _safe_member(info.filename)
                if not relative:
                    continue
                if ".data/" in relative or relative.startswith(".data/"):
                    raise DependencyProvenanceError("wheel layout requires unsupported .data relocation")
                if (
                    relative.lower().endswith((".pyc", ".pyd", ".so", ".dll", ".dylib"))
                    or relative.rsplit("/", 1)[-1].lower().endswith((".pth", ".egg-link"))
                ):
                    raise DependencyProvenanceError("wheel contains unsupported executable or path-injection content")
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or info.is_dir():
                    if info.is_dir():
                        continue
                    raise DependencyProvenanceError("wheel contains a link")
                if relative in members:
                    raise DependencyProvenanceError("wheel contains duplicate member paths")
                members[relative] = archive.read(info)
    except (OSError, zipfile.BadZipFile, RuntimeError, KeyError) as exc:
        raise DependencyProvenanceError(f"locked wheel archive is invalid ({type(exc).__name__})") from None

    dist_info = sorted({name.split("/", 1)[0] for name in members if name.endswith(".dist-info/METADATA")})
    if len(dist_info) != 1:
        raise DependencyProvenanceError("wheel must contain exactly one dist-info metadata directory")
    metadata_root = dist_info[0]
    if metadata_root.endswith(".data") or ".data." in metadata_root:
        raise DependencyProvenanceError("wheel metadata directory is invalid")
    metadata_path = f"{metadata_root}/METADATA"
    wheel_path = f"{metadata_root}/WHEEL"
    record_path = f"{metadata_root}/RECORD"
    if not {metadata_path, wheel_path, record_path}.issubset(members):
        raise DependencyProvenanceError("wheel is missing required dist-info metadata")
    metadata = email.parser.BytesParser().parsebytes(members[metadata_path])
    if _normalize_name(metadata.get("Name", "")) != locked.name or metadata.get("Version") != locked.version:
        raise DependencyProvenanceError("wheel metadata does not match the dependency lock")
    wheel_metadata = email.parser.BytesParser().parsebytes(members[wheel_path])
    tags = wheel_metadata.get_all("Tag", [])
    if wheel_metadata.get("Root-Is-Purelib", "").lower() != "true" or not tags:
        raise DependencyProvenanceError("only purelib wheels with explicit tags are supported")

    def expand_supported_tags(values: list[str]) -> set[str]:
        expanded: set[str] = set()
        for value in values:
            parts = value.split("-")
            python_tags = parts[0].split(".") if len(parts) == 3 else []
            if (
                len(parts) != 3
                or not python_tags
                or any(tag not in {"py2", "py3"} for tag in python_tags)
                or len(set(python_tags)) != len(python_tags)
                or parts[1:] != ["none", "any"]
            ):
                raise DependencyProvenanceError("wheel contains an unsupported Python/platform tag")
            expanded.update(f"{tag}-none-any" for tag in python_tags)
        return expanded

    metadata_tags = expand_supported_tags(tags)
    wheel_parts = filename[:-4].split("-") if filename.endswith(".whl") else []
    if len(wheel_parts) < 5 or _normalize_name(wheel_parts[0]) != locked.name or wheel_parts[1] != locked.version:
        raise DependencyProvenanceError("wheel filename does not match locked package metadata")
    filename_tags = expand_supported_tags(["-".join(wheel_parts[-3:])])
    if filename_tags != metadata_tags:
        raise DependencyProvenanceError("wheel filename has an unsupported Python/platform tag")

    record_rows: dict[str, tuple[str, str]] = {}
    try:
        for row in csv.reader(io.StringIO(members[record_path].decode("utf-8"))):
            if len(row) != 3 or not row[0] or row[0] in record_rows:
                raise DependencyProvenanceError("wheel RECORD is malformed or contains duplicate paths")
            relative = _safe_member(row[0])
            record_rows[relative] = (row[1], row[2])
    except (UnicodeError, csv.Error) as exc:
        raise DependencyProvenanceError(f"wheel RECORD is invalid ({type(exc).__name__})") from None
    if set(record_rows) != set(members):
        raise DependencyProvenanceError("wheel RECORD does not describe the exact archive inventory")
    for name, content in members.items():
        digest_text, size_text = record_rows[name]
        if name == record_path:
            if digest_text or size_text:
                raise DependencyProvenanceError("wheel RECORD self-entry must not claim a digest")
            continue
        expected_hash = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode("ascii").rstrip("=")
        if digest_text != expected_hash or size_text != str(len(content)):
            raise DependencyProvenanceError("wheel RECORD does not match its file contents")
    return members


def _verified_wheels(lock_path: Path, wheelhouse: Path) -> tuple[str, list[VerifiedWheel]]:
    lock_digest, locked = _locked_wheels(lock_path)
    if not wheelhouse.is_dir() or is_link_or_junction(wheelhouse):
        raise DependencyProvenanceError("dependency wheelhouse must be an existing real directory")
    candidates = [path for path in wheelhouse.iterdir() if path.name.lower().endswith(".whl")]
    selected: list[VerifiedWheel] = []
    matched_paths: set[Path] = set()
    for row in locked:
        matches: list[tuple[Path, bytes]] = []
        for path in candidates:
            if (
                not _WHEEL_NAME.fullmatch(path.name)
                or is_link_or_junction(path)
                or not path.is_file()
                or path.stat().st_nlink != 1
            ):
                continue
            digest, content = _wheel_snapshot(path)
            if digest == row.sha256:
                matches.append((path, content))
        if len(matches) != 1:
            raise DependencyProvenanceError(f"locked wheel selection is ambiguous or missing for {row.name}")
        wheel_path, wheel_bytes = matches[0]
        matched_paths.add(wheel_path)
        selected.append(
            VerifiedWheel(
                row.name,
                row.version,
                row.sha256,
                _wheel_file_map(wheel_path.name, wheel_bytes, row),
            )
        )
    extra = sorted(path.name for path in candidates if path not in matched_paths)
    if extra:
        raise DependencyProvenanceError(
            f"wheelhouse contains {len(extra)} wheel file(s) that match no lock row (extra unlocked wheel rejected)"
        )
    return lock_digest, selected


def _target_inventory(target: Path) -> dict[str, bytes]:
    if not target.is_dir() or is_link_or_junction(target):
        raise DependencyProvenanceError("dependency target must be an existing real directory")
    result: dict[str, bytes] = {}
    for base, directories, files in os.walk(target, followlinks=False):
        base_path = Path(base)
        for directory in list(directories):
            child = base_path / directory
            if is_link_or_junction(child):
                raise DependencyProvenanceError("dependency target contains a linked directory")
        for filename in files:
            path = base_path / filename
            relative = path.relative_to(target).as_posix()
            _safe_member(relative)
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise DependencyProvenanceError("dependency target contains a non-regular or linked file")
                if info.st_size > MAX_TARGET_FILE_BYTES:
                    raise DependencyProvenanceError("dependency target file exceeds the supported size bound")
                with path.open("rb") as handle:
                    content = handle.read(MAX_TARGET_FILE_BYTES + 1)
                if len(content) != info.st_size:
                    raise DependencyProvenanceError("dependency target file changed while being read")
                result[relative] = content
            except OSError as exc:
                raise DependencyProvenanceError(f"dependency target cannot be read ({type(exc).__name__})") from None
    return result


def verify_dependency_environment(lock_path: Path, target: Path, wheelhouse: Path) -> dict[str, Any]:
    lock_digest, wheels = _verified_wheels(lock_path, wheelhouse)
    expected: dict[str, bytes] = {}
    versions: dict[str, str] = {}
    wheel_rows: list[dict[str, str]] = []
    for wheel in wheels:
        versions[wheel.name] = wheel.version
        wheel_rows.append({"name": wheel.name, "version": wheel.version, "sha256": wheel.sha256})
        for relative, content in wheel.files.items():
            if relative in expected:
                raise DependencyProvenanceError("locked wheels contain overlapping installed paths")
            expected[relative] = content
    actual = _target_inventory(target)
    if set(actual) != set(expected):
        raise DependencyProvenanceError("dependency target inventory differs from the locked wheel inventory")
    for relative, content in expected.items():
        if actual[relative] != content:
            raise DependencyProvenanceError("dependency target file content differs from its locked wheel")
    rows = [
        {"path": name, "sha256": hashlib.sha256(actual[name]).hexdigest(), "size": len(actual[name])}
        for name in sorted(actual)
    ]
    target_digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "lock_sha256": lock_digest,
        "versions": versions,
        "wheels": wheel_rows,
        "target_sha256": target_digest,
    }


def prepare_dependency_target(lock_path: Path, wheelhouse: Path, target: Path) -> dict[str, Any]:
    """Create a new target by unpacking only hash-verified purelib wheel files.

    The target directory is created exclusively. If preparation fails part-way,
    the partial directory is left in place and cannot be mistaken for a valid
    environment or silently overwritten by a retry.
    """
    target = target.resolve(strict=False)
    wheelhouse = wheelhouse.resolve(strict=True)
    if target.exists() or is_link_or_junction(target):
        raise DependencyProvenanceError("dependency target already exists; preparation never overlays a target")
    if target == wheelhouse or wheelhouse.is_relative_to(target) or target.is_relative_to(wheelhouse):
        raise DependencyProvenanceError("dependency target cannot contain its wheelhouse")
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_digest, wheels = _verified_wheels(lock_path, wheelhouse)
    try:
        target.mkdir(mode=0o700)
    except FileExistsError:
        raise DependencyProvenanceError("dependency target already exists; preparation never overlays a target") from None
    try:
        for wheel in wheels:
            for relative, content in wheel.files.items():
                destination = target.joinpath(*relative.split("/"))
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as handle:
                    handle.write(content)
    except OSError as exc:
        raise DependencyProvenanceError(
            f"dependency target preparation stopped with a partial target ({type(exc).__name__}); do not reuse it"
        ) from None
    verified = verify_dependency_environment(lock_path, target, wheelhouse)
    if verified["lock_sha256"] != lock_digest:
        raise DependencyProvenanceError("dependency lock changed during preparation")
    return verified
