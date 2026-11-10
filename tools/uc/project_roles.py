"""Project-scope role registration (sprint U4, task U4-1).

A project may ship its own ``.claude/agents/*.md`` and ``.claude/skills/*/SKILL.md`` definitions. This module
turns them into data, never code:

1. ``scan_project_roles`` builds a deterministic manifest (schema ``uc.project-roles.v1``) of those files.
2. ``register_project_roles`` extends a validated base role table with one entry per manifest item. Every
   new role is ``NOT_COVERED_NO_PROFILE`` ("project-scope role, not mapped yet") until an explicit mapping
   entry names a canonical role and executors that the AEVE matrix really lists. Adding a role file needs
   no code change.
3. ``table_sha256`` is the sha256 of the exact serialized table bytes (``serialize_table``), the same digest
   ``router.load_table_with_digest`` reports for a table file. Any added, removed or edited project role
   changes the digest, so a receipt carrying the new digest fails the gate's ``ROLE_TABLE_DRIFT`` check
   against an old pin until the pin is deliberately re-issued.
4. ``validate_extended_table`` requires exactly the shape the builder produces, so a project entry can never
   claim coverage or classification the matrix does not support.

Usage:
    python tools/uc/project_roles.py scan --project-root <repo> --project-label <label> (--print | --out F)
    python tools/uc/project_roles.py register --project-root <repo> --project-label <label> \
        --base-table catalog/role_table.json --aeve-root D:/Repo/AEVE --inventory catalog/inventory.json \
        [--mapping mapping.json] (--print | --out role_table.extended.json)
    python tools/uc/project_roles.py validate --project-root <repo> --project-label <label> \
        --table role_table.extended.json --aeve-root D:/Repo/AEVE --inventory catalog/inventory.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import re
import stat
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import aeve_probe, role_table  # noqa: E402
from uc.secret_patterns import has_secret  # noqa: E402

MANIFEST_SCHEMA = "uc.project-roles.v1"
MAPPING_SCHEMA = "uc.project-role-mapping.v1"
SCOPE = "project"
KINDS = ("agent", "skill")
UNMAPPED_REASON = "project-scope role, not mapped yet"
MAPPED_REASON = "project-scope role mapped to AEVE executors by an explicit mapping entry"
PROJECT_CLASS = "LOCAL_PLUS_MODEL"
MAX_FILE_BYTES = 256 * 1024
MAX_ENTRIES = 2000
# no trailing '.', no spaces: such names collide with their stripped form on Windows
NAME_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9_-])?$")
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_AGENT_PATH = re.compile(r"^\.claude/agents/([^/\\]+)\.md$")
_SKILL_PATH = re.compile(r"^\.claude/skills/([^/\\]+)/SKILL\.md$")
_MANIFEST_KEYS = {"schema", "project", "entries"}
_ENTRY_KEYS = {"kind", "name", "path", "source_sha256", "scope"}
_MAPPING_KEYS = {"kind", "name", "source_sha256", "canonical_role", "executors"}
_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT: junctions and other reparse points on Windows
_LINE_SEPARATORS = "\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"
_MALFORMED = (KeyError, TypeError, ValueError, AttributeError, IndexError, RecursionError)


class ProjectRolesError(Exception):
    """A project role cannot be turned into a trustworthy manifest or table entry."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _safe(value: object) -> str:
    """Printable form of untrusted text: short plain text as repr, otherwise length plus a sha256 prefix."""
    text = value if isinstance(value, str) else repr(value)
    if len(text) <= 40 and text.isprintable() and not has_secret(text):
        return repr(text)
    digest = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]
    return f"<len={len(text)} sha256={digest}>"


def _norm(name: str) -> str:
    """Comparison form of a role name: casefolded with trailing dots and spaces removed."""
    return name.casefold().rstrip(". ")


# ------------------------------------------------------------------------------------------------ scanning
def _is_link(path: pathlib.Path) -> bool:
    """True for symlinks and Windows junctions / reparse points (lstat only, never follows)."""
    if path.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return True
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & _REPARSE_POINT)


def _read_regular(path: pathlib.Path, rel: str) -> bytes:
    """Open once, validate the descriptor (regular, single link, not a reparse point), read at most the cap."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ProjectRolesError("IO_ERROR", _safe(rel)) from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ProjectRolesError("NOT_A_REGULAR_FILE", _safe(rel))
        if getattr(info, "st_file_attributes", 0) & _REPARSE_POINT or info.st_nlink != 1:
            raise ProjectRolesError("LINK_REFUSED", _safe(rel))
        if info.st_size > MAX_FILE_BYTES:
            raise ProjectRolesError("FILE_TOO_LARGE", f"{_safe(rel)} is {info.st_size} bytes, limit {MAX_FILE_BYTES}")
        chunks: list[bytes] = []
        total = 0
        while total <= MAX_FILE_BYTES:
            chunk = os.read(fd, min(65536, MAX_FILE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > MAX_FILE_BYTES:
            raise ProjectRolesError("FILE_TOO_LARGE", _safe(rel))
        return b"".join(chunks)
    except OSError as exc:
        raise ProjectRolesError("IO_ERROR", _safe(rel)) from exc
    finally:
        os.close(fd)


def _frontmatter_name(text: str, rel: str) -> str | None:
    """Value of the ``name`` key in a leading ``---`` block, or None when there is no such key.

    Fails closed (BAD_NAME) on anything a different parser could read differently: bare CR, Unicode line
    separators in the block, an unterminated block, a quoted or oddly spelled key that normalizes to ``name``,
    and a duplicated ``name`` key.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    if re.search(r"\r(?!\n)", text):
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: bare CR line ending")
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: unterminated frontmatter")
    block = lines[1:end]
    if any(ch in line for line in block for ch in _LINE_SEPARATORS):
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: line separator in frontmatter")
    found: list[str] = []
    for line in block:
        if line[:1] in (" ", "\t") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip().strip("\"'").strip().casefold() == "name":
            if key != "name":
                raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: irregular name key")
            found.append(value.strip())
    if len(found) > 1:
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: duplicate name key")
    if not found:
        return None
    value = found[0]
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


def _entry(kind: str, path: pathlib.Path, root: pathlib.Path, default_name: str) -> dict:
    rel = path.relative_to(root).as_posix()
    if _is_link(path) or _is_link(path.parent):
        raise ProjectRolesError("LINK_REFUSED", _safe(rel))
    raw = _read_regular(path, rel)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProjectRolesError("NOT_UTF8", _safe(rel)) from exc
    declared = _frontmatter_name(text, rel)
    if not NAME_PATTERN.fullmatch(default_name):
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: file or directory name {_safe(default_name)}")
    name = default_name if declared is None else declared
    if not NAME_PATTERN.fullmatch(name):
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: declared name {_safe(name)}")
    if name != default_name:
        raise ProjectRolesError("BAD_NAME", f"{_safe(rel)}: declared name differs from the file or directory name")
    return {"kind": kind, "name": name, "path": rel, "source_sha256": content_sha256(text), "scope": SCOPE}


def content_sha256(text: str) -> str:
    """sha256 of newline-normalized content: a leading BOM is dropped and CRLF / CR become LF, so the digest
    does not depend on the checkout's line-ending convention."""
    if text.startswith("\ufeff"):
        text = text[1:]
    return hashlib.sha256(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()


def _candidates(project_claude: pathlib.Path, root: pathlib.Path) -> list[tuple[str, pathlib.Path, str]]:
    """(kind, file, default_name) for exact ``*.md`` agents and ``<dir>/SKILL.md`` skills; bounded, case-sensitive."""
    found: list[tuple[str, pathlib.Path, str]] = []
    agents_dir, skills_dir = project_claude / "agents", project_claude / "skills"
    for directory in (agents_dir, skills_dir):
        if _is_link(directory):
            raise ProjectRolesError("LINK_REFUSED", _safe(directory.relative_to(root).as_posix()))
    if agents_dir.is_dir():
        with os.scandir(agents_dir) as it:
            for item in it:
                if item.name.endswith(".md") and len(item.name) > 3:
                    found.append(("agent", agents_dir / item.name, item.name[:-3]))
                    if len(found) > MAX_ENTRIES:
                        raise ProjectRolesError("TOO_MANY_ENTRIES", f"more than {MAX_ENTRIES}")
    if skills_dir.is_dir():
        with os.scandir(skills_dir) as it:
            for item in it:
                sub = skills_dir / item.name
                if _is_link(sub):
                    raise ProjectRolesError("LINK_REFUSED", _safe(sub.relative_to(root).as_posix()))
                if item.is_dir(follow_symlinks=False) and "SKILL.md" in os.listdir(sub):
                    found.append(("skill", sub / "SKILL.md", item.name))
                    if len(found) > MAX_ENTRIES:
                        raise ProjectRolesError("TOO_MANY_ENTRIES", f"more than {MAX_ENTRIES}")
    return sorted(found, key=lambda c: (c[0], c[2]))


def scan_project_roles(project_root: pathlib.Path, project_label: str) -> dict:
    """Return the deterministic manifest of ``<project_root>/.claude`` agents and skills.

    ``project_label`` is an explicit required input (it never defaults from the folder name), so the manifest does
    not depend on where the checkout lives. Refuses symlinks, junctions, hard-linked and non-regular files,
    oversize or non-UTF-8 files, irregular frontmatter, names outside ``NAME_PATTERN`` or differing from the file
    or directory name, and duplicate names (compared casefolded, across agents and skills, because the router
    resolves roles by name only). A project without agents/skills directories yields an empty manifest.
    """
    try:
        return _scan(pathlib.Path(project_root), project_label)
    except OSError as exc:
        raise ProjectRolesError("IO_ERROR", type(exc).__name__) from exc


def _scan(project_root: pathlib.Path, project_label: str) -> dict:
    if not isinstance(project_label, str) or not LABEL_PATTERN.fullmatch(project_label):
        raise ProjectRolesError("BAD_LABEL", _safe(project_label))
    if not project_root.is_dir():
        raise ProjectRolesError("PROJECT_ROOT_MISSING", _safe(str(project_root)))
    root = project_root.resolve()
    claude = root / ".claude"
    entries: list[dict] = []
    if _is_link(claude):
        raise ProjectRolesError("LINK_REFUSED", ".claude")
    if claude.is_dir():
        for kind, path, default_name in _candidates(claude, root):
            entries.append(_entry(kind, path, root, default_name))
    seen: dict[str, str] = {}
    for item in entries:
        key = _norm(item["name"])
        if key in seen:
            raise ProjectRolesError("DUPLICATE_NAME", f"{_safe(item['name'])}: {_safe(seen[key])} and {_safe(item['path'])}")
        seen[key] = item["path"]
    entries.sort(key=lambda e: (e["kind"], e["name"]))
    return {"schema": MANIFEST_SCHEMA, "project": project_label, "entries": entries}


def validate_manifest(manifest: object) -> list[str]:
    """Return problems with a manifest (shape, patterns, kind/path/name agreement, sorting, unique names).

    Never raises. An empty list means valid.
    """
    try:
        return _validate_manifest(manifest)
    except _MALFORMED as exc:
        return [f"manifest: malformed ({type(exc).__name__})"]


def _validate_manifest(manifest: object) -> list[str]:
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS or manifest.get("schema") != MANIFEST_SCHEMA:
        return ["manifest: wrong shape or schema"]
    problems: list[str] = []
    label = manifest["project"]
    if not isinstance(label, str) or not LABEL_PATTERN.fullmatch(label):
        problems.append("manifest: bad project label")
    entries = manifest["entries"]
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        return problems + ["manifest: entries is not a bounded list"]
    names: set[str] = set()
    keys: list[tuple[str, str]] = []
    for item in entries:
        if not isinstance(item, dict) or set(item) != _ENTRY_KEYS:
            problems.append("manifest: an entry has the wrong shape")
            continue
        name, kind, path = item["name"], item["kind"], item["path"]
        if kind not in KINDS or item["scope"] != SCOPE:
            problems.append(f"manifest: {_safe(name)} has a bad kind or scope")
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            problems.append(f"manifest: bad name {_safe(name)}")
            continue
        match = None
        if isinstance(path, str):
            match = (_AGENT_PATH if kind == "agent" else _SKILL_PATH if kind == "skill" else re.compile("(?!)")).fullmatch(path)
        if match is None:
            problems.append(f"manifest: {_safe(name)} has a path that does not fit its kind")
        elif match.group(1) != name:
            problems.append(f"manifest: {_safe(name)} differs from the file or directory name in its path")
        if not isinstance(item["source_sha256"], str) or not _HASH.fullmatch(item["source_sha256"]):
            problems.append(f"manifest: {_safe(name)} has a bad source_sha256")
        if _norm(name) in names:
            problems.append(f"manifest: duplicate name {_safe(name)}")
        names.add(_norm(name))
        keys.append((kind, name))
    if keys != sorted(keys):
        problems.append("manifest: entries are not sorted by (kind, name)")
    return problems


def manifest_sha256(manifest: dict) -> str:
    return hashlib.sha256(_canonical(manifest)).hexdigest()


def _canonical(doc: object) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------------------------- registration
def _mapping_index(mapping: dict | None) -> dict[tuple[str, str], dict]:
    if mapping is None:
        return {}
    if (not isinstance(mapping, dict) or mapping.get("schema") != MAPPING_SCHEMA
            or not isinstance(mapping.get("entries"), list)):
        raise ProjectRolesError("BAD_MAPPING", "expected schema uc.project-role-mapping.v1 with an entries list")
    index: dict[tuple[str, str], dict] = {}
    for item in mapping["entries"]:
        if (not isinstance(item, dict) or set(item) != _MAPPING_KEYS
                or item["kind"] not in KINDS or not isinstance(item["name"], str)
                or not isinstance(item["source_sha256"], str) or not _HASH.fullmatch(item["source_sha256"])
                or not isinstance(item["canonical_role"], str)
                or not isinstance(item["executors"], list) or not item["executors"]
                or not all(isinstance(x, str) for x in item["executors"])):
            raise ProjectRolesError("BAD_MAPPING", "a mapping entry is malformed")
        key = (item["kind"], item["name"])
        if key in index:
            raise ProjectRolesError("BAD_MAPPING", f"duplicate mapping entry {_safe(item['name'])}")
        index[key] = item
    return index


def _unmapped_entry(item: dict) -> dict:
    return {
        "kind": item["kind"], "name": item["name"], "scope": SCOPE, "path": item["path"],
        "source_sha256": item["source_sha256"], "class": PROJECT_CLASS, "draft_class": PROJECT_CLASS,
        "class_upgraded_by_evidence": False, "model_remainder_hint": "",
        "canonical_role": item["name"], "aeve_profile": None, "executors": [],
        "coverage_state": "NOT_COVERED_NO_PROFILE", "reason": UNMAPPED_REASON,
    }


def _covered_entry(item: dict, canonical: str, executors: list[str]) -> dict:
    return {**_unmapped_entry(item), "canonical_role": canonical, "aeve_profile": canonical,
            "executors": list(executors), "coverage_state": "COVERED_PARTIAL", "reason": MAPPED_REASON}


def register_project_roles(base_table: dict, manifest: dict, mapping: dict | None = None,
                           matrix: dict | None = None) -> dict:
    """Return a new table: ``base_table`` plus one ``scope: project`` entry per manifest item.

    Unmapped roles are ``NOT_COVERED_NO_PROFILE``. A mapping entry (data, ``uc.project-role-mapping.v1``, carrying
    the manifest entry's ``source_sha256``) may lift a role to ``COVERED_PARTIAL`` only when ``matrix`` lists
    exactly the stated executors for the stated canonical role. Refused: mapping without a matrix, mapping for an
    unknown role or a stale digest, a project name equal (casefolded) to a base-table name, an unmapped project
    name equal to an AEVE profile id, and a base table that already holds project entries. ``base_table`` is not
    modified. Never raises anything but ``ProjectRolesError``.
    """
    try:
        return _register(base_table, manifest, mapping, matrix)
    except _MALFORMED as exc:
        raise ProjectRolesError("MALFORMED_INPUT", type(exc).__name__) from exc


def _register(base_table: dict, manifest: dict, mapping: dict | None, matrix: dict | None) -> dict:
    problems = validate_manifest(manifest)
    if problems:
        raise ProjectRolesError("BAD_MANIFEST", "; ".join(problems[:3]))
    if not isinstance(base_table, dict) or not isinstance(base_table.get("entries"), list):
        raise ProjectRolesError("BAD_BASE_TABLE", "entries is not a list")
    if any(isinstance(e, dict) and "scope" in e for e in base_table["entries"]):
        raise ProjectRolesError("BASE_TABLE_ALREADY_EXTENDED", "register against the global base table only")
    index = _mapping_index(mapping)
    wanted = {(e["kind"], e["name"]): e for e in manifest["entries"]}
    for key, mapped in sorted(index.items()):
        if key not in wanted:
            raise ProjectRolesError("MAPPING_FOR_UNKNOWN_ROLE", f"{key[0]} {_safe(key[1])}")
        if mapped["source_sha256"] != wanted[key]["source_sha256"]:
            raise ProjectRolesError("BAD_MAPPING", f"{key[0]} {_safe(key[1])}: source_sha256 differs from the manifest")
    if index and matrix is None:
        raise ProjectRolesError("MATRIX_REQUIRED", "a mapping needs the AEVE matrix to prove the executors")
    matrix_index = role_table._matrix_index(matrix) if matrix is not None else None
    base_names = {_norm(e["name"]) for e in base_table["entries"]}
    new_entries = []
    for item in manifest["entries"]:
        label = f"{item['kind']} {_safe(item['name'])}"
        if _norm(item["name"]) in base_names:
            raise ProjectRolesError("NAME_COLLIDES_WITH_GLOBAL_ROLE", label)
        mapped = index.get((item["kind"], item["name"]))
        if mapped is None:
            if matrix_index is not None and item["name"] in matrix_index:
                raise ProjectRolesError("NAME_EQUALS_AEVE_PROFILE", f"{label}: map it explicitly")
            new_entries.append(_unmapped_entry(item))
            continue
        canonical = mapped["canonical_role"]
        listed = matrix_index.get(canonical, [])
        if not listed or sorted(mapped["executors"]) != listed:
            raise ProjectRolesError("MAPPING_EXECUTORS_NOT_IN_MATRIX", f"{label}: the matrix lists {listed} for {_safe(canonical)}")
        new_entries.append(_covered_entry(item, canonical, listed))
    entries = sorted([*copy.deepcopy(base_table["entries"]), *new_entries], key=lambda e: (e["kind"], e["name"]))
    extended = {k: copy.deepcopy(v) for k, v in base_table.items() if k not in ("entries", "counts", "project_roles")}
    extended["project_roles"] = {"schema": MANIFEST_SCHEMA, "project": manifest["project"],
                                 "manifest_sha256": manifest_sha256(manifest)}
    extended["counts"] = role_table._counts(entries)
    extended["entries"] = entries
    return extended


# ---------------------------------------------------------------------------------------------- hash + checks
def serialize_table(table: dict) -> bytes:
    """Canonical file bytes of a table (identical to what ``role_table.py build`` writes)."""
    return (json.dumps(table, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def table_sha256(table: dict) -> str:
    """sha256 of ``serialize_table(table)``: the value the router puts in ``role_table_sha256`` once the table
    is written with ``serialize_table`` and loaded by ``router.load_table_with_digest``."""
    return hashlib.sha256(serialize_table(table)).hexdigest()


def validate_extended_table(table: object, inventory: dict, manifest: dict, matrix: dict,
                            probe_record: dict) -> list[str]:
    """Return problems with an extended table; empty means valid. Never raises on malformed input.

    The global part must pass ``role_table.validate_role_table`` unchanged. Every manifest item must appear
    exactly once as a ``scope: project`` entry that equals, key for key, what the builder produces: unmapped
    (``NOT_COVERED_NO_PROFILE``, class and draft_class ``LOCAL_PLUS_MODEL``, exact reason, no executors) or
    mapped (``COVERED_PARTIAL`` with exactly the matrix's executors for its canonical role).
    """
    try:
        return _validate_extended(table, inventory, manifest, matrix, probe_record)
    except _MALFORMED as exc:
        return [f"validator: malformed input ({type(exc).__name__})"]


def _validate_extended(table: object, inventory: dict, manifest: dict, matrix: dict, probe_record: dict) -> list[str]:
    problems = [f"manifest: {p}" for p in validate_manifest(manifest)]
    if problems:
        return problems
    if not isinstance(table, dict) or not isinstance(table.get("entries"), list):
        return ["table: entries is not a list"]
    entries = [e for e in table["entries"] if isinstance(e, dict)]
    if len(entries) != len(table["entries"]):
        problems.append("table: an entry is not an object")
    global_entries = [e for e in entries if "scope" not in e]
    project_entries = [e for e in entries if "scope" in e]
    base_view = {k: v for k, v in table.items() if k not in ("project_roles", "counts", "entries")}
    base_view["entries"] = global_entries
    base_view["counts"] = role_table._counts(global_entries)
    problems += role_table.validate_role_table(base_view, inventory, matrix, probe_record)
    if table.get("counts") != role_table._counts(entries):
        problems.append("counts: stored counts differ from the recomputed counts")
    if table.get("project_roles") != {"schema": MANIFEST_SCHEMA, "project": manifest["project"],
                                      "manifest_sha256": manifest_sha256(manifest)}:
        problems.append("project_roles: stamp differs from the manifest")
    index = role_table._matrix_index(matrix)
    base_names = {_norm(str(e.get("name"))) for e in global_entries}
    wanted = {(m["kind"], m["name"]): m for m in manifest["entries"]}
    seen: set[tuple[object, object]] = set()
    for entry in project_entries:
        key = (entry.get("kind"), entry.get("name"))
        label = f"project {_safe(key[0])} {_safe(key[1])}"
        if key in seen:
            problems.append(f"{label}: duplicate entry")
        seen.add(key)
        source = wanted.get(key) if isinstance(key[0], str) and isinstance(key[1], str) else None
        if entry.get("scope") != SCOPE or source is None:
            problems.append(f"{label}: not in the manifest or bad scope")
            continue
        if entry.get("source_sha256") != source["source_sha256"] or entry.get("path") != source["path"]:
            problems.append(f"{label}: path or source digest differs from the manifest")
        if _norm(key[1]) in base_names:
            problems.append(f"{label}: name collides with a global role")
        state = entry.get("coverage_state")
        if state == "COVERED_PARTIAL":
            canonical = entry.get("canonical_role")
            listed = index.get(canonical) if isinstance(canonical, str) else None
            if not listed or entry.get("executors") != listed:
                problems.append(f"{label}: claims coverage the matrix does not list")
                continue
            expected = _covered_entry(source, canonical, listed)
        else:
            if state not in ("NOT_COVERED_NO_PROFILE", "NOT_COVERED_NO_EXECUTOR"):
                problems.append(f"{label}: bad coverage_state for a project role")
            elif entry.get("executors"):
                problems.append(f"{label}: {state} but executors are listed")
            if key[1] in index:
                problems.append(f"{label}: name equals an AEVE profile; map it explicitly instead")
            expected = _unmapped_entry(source)
        if entry != expected:
            differing = sorted(str(k) for k in set(entry) | set(expected) if entry.get(k, object()) != expected.get(k, object()))
            problems.append(f"{label}: differs from the builder shape in: {', '.join(differing)}")
    for key in sorted(set(wanted) - seen):
        problems.append(f"missing project entry {key[0]} {_safe(key[1])}")
    return problems


# --------------------------------------------------------------------------------------------------- CLI
def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _same_path(a: pathlib.Path, b: pathlib.Path) -> bool:
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _check_out(out: pathlib.Path | None, inputs: list[pathlib.Path], project_root: pathlib.Path) -> None:
    if out is None:
        return
    for other in inputs:
        if _same_path(out, other):
            raise ProjectRolesError("OUT_IS_INPUT", _safe(str(out)))
    claude = os.path.normcase(os.path.realpath(project_root / ".claude"))
    target = os.path.normcase(os.path.realpath(out))
    if target == claude or target.startswith(claude + os.sep):
        raise ProjectRolesError("OUT_INSIDE_ROLE_DIRECTORY", _safe(str(out)))


def _write_atomic(path: pathlib.Path, payload: bytes) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _line(text: object) -> str:
    """One printable output line with no control characters and no credential-shaped text."""
    cleaned = "".join(ch for ch in str(text)[:300] if ch.isprintable())
    return "<line withheld: credential-shaped text>" if has_secret(cleaned) else cleaned


def _print_problems(problems: list[str]) -> None:
    for line in problems:
        print(_line(line))
    print(f"INVALID: {len(problems)} problem(s)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan, reg, val = sub.add_parser("scan"), sub.add_parser("register"), sub.add_parser("validate")
    for cmd in (scan, reg, val):
        cmd.add_argument("--project-root", required=True, type=pathlib.Path)
        cmd.add_argument("--project-label", required=True)
    for cmd in (scan, reg):
        mode = cmd.add_mutually_exclusive_group(required=True)
        mode.add_argument("--print", action="store_true", dest="print_only", help="print a summary; write nothing")
        mode.add_argument("--out", type=pathlib.Path)
    for cmd in (reg, val):
        cmd.add_argument("--aeve-root", required=True, type=pathlib.Path)
        cmd.add_argument("--inventory", required=True, type=pathlib.Path)
    reg.add_argument("--base-table", required=True, type=pathlib.Path)
    reg.add_argument("--mapping", type=pathlib.Path)
    val.add_argument("--table", required=True, type=pathlib.Path)
    return parser


def _run(args: argparse.Namespace) -> int:
    out = getattr(args, "out", None)
    inputs = [p for p in (getattr(args, n, None) for n in ("base_table", "mapping", "inventory", "table")) if p]
    _check_out(out, inputs, args.project_root)
    manifest = scan_project_roles(args.project_root, args.project_label)
    if args.command == "scan":
        payload = (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        summary = {"status": "SCANNED", "project": manifest["project"], "entries": len(manifest["entries"]),
                   "manifest_sha256": manifest_sha256(manifest)}
    else:
        try:
            record = aeve_probe.probe(args.aeve_root)
            matrix = aeve_probe.load_matrix(args.aeve_root)
        except aeve_probe.AeveProbeError as exc:
            print(_line(json.dumps({"status": "BLOCKED", "reason": exc.reason, "detail": exc.detail}, sort_keys=True)))
            return 2
        inventory = _load(args.inventory)
        if args.command == "register":
            mapping = _load(args.mapping) if args.mapping else None
            table = register_project_roles(_load(args.base_table), manifest, mapping, matrix)
            payload = serialize_table(table)
        else:
            raw = args.table.read_bytes()
            table, payload = json.loads(raw.decode("utf-8")), None
        problems = validate_extended_table(table, inventory, manifest, matrix, record)
        if problems:
            _print_problems(problems)
            return 1
        if payload is None:
            digest = hashlib.sha256(raw).hexdigest()
            if digest != table_sha256(table):
                _print_problems(["table: file bytes are not the canonical serialization of the table"])
                return 1
        else:
            digest = table_sha256(table)
        summary = {"status": "REGISTERED" if args.command == "register" else "VALID", "role_table_sha256": digest,
                   "counts": table["counts"], "project_roles": table["project_roles"]}
    if out is not None and payload is not None:
        _write_atomic(out, payload)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _run(args)
    except ProjectRolesError as exc:
        print(json.dumps({"status": "REFUSED", "code": exc.code, "detail": _line(exc.detail)}, sort_keys=True))
        return 1
    except (OSError, *_MALFORMED) as exc:
        print(json.dumps({"status": "REFUSED", "code": "INPUT_ERROR", "detail": type(exc).__name__}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
