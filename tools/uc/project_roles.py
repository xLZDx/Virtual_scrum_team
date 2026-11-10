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
4. ``validate_extended_table`` keeps the table stricter than the matrix: a project entry can never claim
   coverage the matrix does not list.

Usage:
    python tools/uc/project_roles.py scan --project-root <repo> --print
    python tools/uc/project_roles.py register --project-root <repo> --base-table catalog/role_table.json \
        --aeve-root D:/Repo/AEVE --inventory catalog/inventory.json [--mapping mapping.json] \
        (--print | --out role_table.extended.json)
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import aeve_probe, role_table  # noqa: E402

MANIFEST_SCHEMA = "uc.project-roles.v1"
MAPPING_SCHEMA = "uc.project-role-mapping.v1"
SCOPE = "project"
KINDS = ("agent", "skill")
UNMAPPED_REASON = "project-scope role, not mapped yet"
MAPPED_REASON = "project-scope role mapped to AEVE executors by an explicit mapping entry"
MAX_FILE_BYTES = 256 * 1024
MAX_ENTRIES = 2000
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_PATH = re.compile(r"^\.claude/(agents/[^/\\]+\.md|skills/[^/\\]+/SKILL\.md)$")
_MANIFEST_KEYS = {"schema", "project", "entries"}
_ENTRY_KEYS = {"kind", "name", "path", "source_sha256", "scope"}
_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT: junctions and other reparse points on Windows


class ProjectRolesError(Exception):
    """A project role cannot be turned into a trustworthy manifest or table entry."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


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


def _frontmatter_name(text: str) -> str | None:
    """Top-level ``name:`` of a leading ``---`` block, mirroring catalog/extract_inventory.parse_frontmatter."""
    lines = text.lstrip("﻿").replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line[:1] in (" ", "\t") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip() == "name":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    return None


def _entry(kind: str, path: pathlib.Path, root: pathlib.Path) -> dict:
    if _is_link(path) or _is_link(path.parent):
        raise ProjectRolesError("LINK_REFUSED", path.relative_to(root).as_posix())
    rel = path.relative_to(root).as_posix()
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ProjectRolesError("NOT_A_REGULAR_FILE", rel)
    if info.st_size > MAX_FILE_BYTES:
        raise ProjectRolesError("FILE_TOO_LARGE", f"{rel} is {info.st_size} bytes, limit {MAX_FILE_BYTES}")
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ProjectRolesError("FILE_TOO_LARGE", rel)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProjectRolesError("NOT_UTF8", rel) from exc
    default_name = path.parent.name if kind == "skill" else path.stem
    name = _frontmatter_name(text) or default_name
    if not NAME_PATTERN.fullmatch(name):
        raise ProjectRolesError("BAD_NAME", f"{rel}: {name!r}")
    return {"kind": kind, "name": name, "path": rel, "source_sha256": hashlib.sha256(raw).hexdigest(), "scope": SCOPE}


def scan_project_roles(project_root: pathlib.Path, project_label: str | None = None) -> dict:
    """Return the deterministic manifest of ``<project_root>/.claude`` agents and skills.

    Refuses symlinks and junctions, oversize or non-UTF-8 files, names outside ``NAME_PATTERN`` and duplicate
    names (a name must be unique across agents AND skills, because the router looks roles up by name only).
    A project without a ``.claude`` agents/skills directory yields an empty manifest.
    """
    project_root = pathlib.Path(project_root)
    if not project_root.is_dir():
        raise ProjectRolesError("PROJECT_ROOT_MISSING", str(project_root))
    label = project_label if project_label is not None else project_root.resolve().name
    if not LABEL_PATTERN.fullmatch(label):
        raise ProjectRolesError("BAD_LABEL", repr(label))
    root = project_root.resolve()
    claude = root / ".claude"
    entries: list[dict] = []
    if claude.exists() or _is_link(claude):
        if _is_link(claude):
            raise ProjectRolesError("LINK_REFUSED", ".claude")
        agents_dir, skills_dir = claude / "agents", claude / "skills"
        for directory in (agents_dir, skills_dir):
            if _is_link(directory):
                raise ProjectRolesError("LINK_REFUSED", directory.relative_to(root).as_posix())
        if agents_dir.is_dir():
            for path in sorted(agents_dir.glob("*.md")):
                entries.append(_entry("agent", path, root))
        if skills_dir.is_dir():
            for path in sorted(skills_dir.glob("*/SKILL.md")):
                entries.append(_entry("skill", path, root))
    if len(entries) > MAX_ENTRIES:
        raise ProjectRolesError("TOO_MANY_ENTRIES", str(len(entries)))
    seen: dict[str, str] = {}
    for item in entries:
        if item["name"] in seen:
            raise ProjectRolesError("DUPLICATE_NAME", f"{item['name']!r}: {seen[item['name']]} and {item['path']}")
        seen[item["name"]] = item["path"]
    entries.sort(key=lambda e: (e["kind"], e["name"]))
    return {"schema": MANIFEST_SCHEMA, "project": label, "entries": entries}


def validate_manifest(manifest: object) -> list[str]:
    """Return problems with a manifest (shape, patterns, sorting, unique names); empty means valid."""
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
            problems.append(f"manifest: {name!r} has a bad kind or scope")
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            problems.append(f"manifest: bad name {name!r}")
            continue
        if not isinstance(path, str) or not _PATH.fullmatch(path):
            problems.append(f"manifest: {name!r} has a bad path")
        if not isinstance(item["source_sha256"], str) or not _HASH.fullmatch(item["source_sha256"]):
            problems.append(f"manifest: {name!r} has a bad source_sha256")
        if name in names:
            problems.append(f"manifest: duplicate name {name!r}")
        names.add(name)
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
        if (not isinstance(item, dict) or set(item) != {"kind", "name", "canonical_role", "executors"}
                or item["kind"] not in KINDS or not isinstance(item["name"], str)
                or not isinstance(item["canonical_role"], str)
                or not isinstance(item["executors"], list) or not item["executors"]
                or not all(isinstance(x, str) for x in item["executors"])):
            raise ProjectRolesError("BAD_MAPPING", "a mapping entry is malformed")
        key = (item["kind"], item["name"])
        if key in index:
            raise ProjectRolesError("BAD_MAPPING", f"duplicate mapping entry {key}")
        index[key] = item
    return index


def _project_entry(item: dict, mapped: dict | None, matrix_index: dict[str, list[str]] | None) -> dict:
    base = {
        "kind": item["kind"], "name": item["name"], "scope": SCOPE, "path": item["path"],
        "source_sha256": item["source_sha256"], "class": "LOCAL_PLUS_MODEL", "draft_class": "LOCAL_PLUS_MODEL",
        "class_upgraded_by_evidence": False, "model_remainder_hint": "",
    }
    if mapped is None:
        return {**base, "canonical_role": item["name"], "aeve_profile": None, "executors": [],
                "coverage_state": "NOT_COVERED_NO_PROFILE", "reason": UNMAPPED_REASON}
    canonical = mapped["canonical_role"]
    listed = (matrix_index or {}).get(canonical, [])
    if sorted(mapped["executors"]) != listed or not listed:
        raise ProjectRolesError(
            "MAPPING_EXECUTORS_NOT_IN_MATRIX",
            f"{item['kind']} {item['name']}: the matrix lists {listed} for {canonical!r}")
    return {**base, "canonical_role": canonical, "aeve_profile": canonical, "executors": listed,
            "coverage_state": "COVERED_PARTIAL", "reason": MAPPED_REASON}


def register_project_roles(base_table: dict, manifest: dict, mapping: dict | None = None,
                           matrix: dict | None = None) -> dict:
    """Return a new table: ``base_table`` plus one ``scope: project`` entry per manifest item.

    Unmapped roles are ``NOT_COVERED_NO_PROFILE``. A mapping entry (data, ``uc.project-role-mapping.v1``) may
    lift a role to ``COVERED_PARTIAL`` only when ``matrix`` lists exactly the stated executors for the stated
    canonical role; mapping without a ``matrix`` is refused. A project name equal to any base-table name is
    refused, because the router resolves roles by name. ``base_table`` is not modified.
    """
    problems = validate_manifest(manifest)
    if problems:
        raise ProjectRolesError("BAD_MANIFEST", "; ".join(problems[:3]))
    if not isinstance(base_table, dict) or not isinstance(base_table.get("entries"), list):
        raise ProjectRolesError("BAD_BASE_TABLE", "entries is not a list")
    if any(isinstance(e, dict) and e.get("scope") == SCOPE for e in base_table["entries"]):
        raise ProjectRolesError("BASE_TABLE_ALREADY_EXTENDED", "register against the global base table only")
    index = _mapping_index(mapping)
    manifest_keys = {(e["kind"], e["name"]) for e in manifest["entries"]}
    for key in sorted(set(index) - manifest_keys):
        raise ProjectRolesError("MAPPING_FOR_UNKNOWN_ROLE", f"{key[0]} {key[1]}")
    if index and matrix is None:
        raise ProjectRolesError("MATRIX_REQUIRED", "a mapping needs the AEVE matrix to prove the executors")
    matrix_index = role_table._matrix_index(matrix) if matrix is not None else None
    base_names = {e.get("name") for e in base_table["entries"] if isinstance(e, dict)}
    new_entries = []
    for item in manifest["entries"]:
        if item["name"] in base_names:
            raise ProjectRolesError("NAME_COLLIDES_WITH_GLOBAL_ROLE", f"{item['kind']} {item['name']}")
        new_entries.append(_project_entry(item, index.get((item["kind"], item["name"])), matrix_index))
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
    """Return problems with an extended table; empty means valid.

    The global part must pass ``role_table.validate_role_table`` unchanged. Every manifest item must appear
    exactly once as a ``scope: project`` entry with matching path and source digest; a project entry may be
    ``COVERED_PARTIAL`` only with the matrix's exact executors for its canonical role, otherwise it must be
    a ``NOT_COVERED_*`` entry with no executors. Stricter than the matrix, never looser.
    """
    problems = [f"manifest: {p}" for p in validate_manifest(manifest)]
    if not isinstance(table, dict) or not isinstance(table.get("entries"), list):
        return problems + ["table: entries is not a list"]
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
    if problems and any(p.startswith("manifest:") for p in problems):
        return problems
    stamp = table.get("project_roles")
    if stamp != {"schema": MANIFEST_SCHEMA, "project": manifest["project"], "manifest_sha256": manifest_sha256(manifest)}:
        problems.append("project_roles: stamp differs from the manifest")
    index = role_table._matrix_index(matrix)
    base_names = {e.get("name") for e in global_entries}
    wanted = {(m["kind"], m["name"]): m for m in manifest["entries"]}
    seen: set[tuple[str, str]] = set()
    for entry in project_entries:
        key = (entry.get("kind"), entry.get("name"))
        label = f"project {key[0]} {key[1]}"
        if key in seen:
            problems.append(f"{label}: duplicate entry")
        seen.add(key)
        source = wanted.get(key)
        if entry.get("scope") != SCOPE or source is None:
            problems.append(f"{label}: not in the manifest or bad scope")
            continue
        if entry.get("path") != source["path"] or entry.get("source_sha256") != source["source_sha256"]:
            problems.append(f"{label}: path or source digest differs from the manifest")
        if key[1] in base_names:
            problems.append(f"{label}: name collides with a global role")
        if entry.get("class") not in role_table.CLASSES or entry.get("class") in ("MODEL_ONLY", "OUT_OF_SCOPE"):
            problems.append(f"{label}: project class must be LOCAL or LOCAL_PLUS_MODEL")
        canonical, state, executors = entry.get("canonical_role"), entry.get("coverage_state"), entry.get("executors")
        if not isinstance(executors, list):
            problems.append(f"{label}: executors is not a list")
            continue
        if state == "COVERED_PARTIAL":
            listed = index.get(canonical, [])
            if not listed or sorted(executors) != listed:
                problems.append(f"{label}: claims coverage the matrix does not list for {canonical!r}")
            if entry.get("aeve_profile") != canonical:
                problems.append(f"{label}: aeve_profile differs from canonical_role")
        elif state in ("NOT_COVERED_NO_PROFILE", "NOT_COVERED_NO_EXECUTOR"):
            if executors:
                problems.append(f"{label}: {state} but executors are listed")
            if canonical != key[1]:
                problems.append(f"{label}: an unmapped project role must be its own canonical role")
            if canonical in index:
                problems.append(f"{label}: name equals an AEVE profile; map it explicitly instead")
            if state == "NOT_COVERED_NO_EXECUTOR" or entry.get("aeve_profile") is not None:
                problems.append(f"{label}: an unmapped project role must be NOT_COVERED_NO_PROFILE without a profile")
        else:
            problems.append(f"{label}: bad coverage_state for a project role")
    for key in sorted(set(wanted) - seen):
        problems.append(f"missing project entry {key}")
    return problems


# --------------------------------------------------------------------------------------------------- CLI
def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: pathlib.Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    reg = sub.add_parser("register")
    for cmd in (scan, reg):
        cmd.add_argument("--project-root", required=True, type=pathlib.Path)
        cmd.add_argument("--project-label")
        mode = cmd.add_mutually_exclusive_group(required=True)
        mode.add_argument("--print", action="store_true", dest="print_only", help="print a summary; write nothing")
        mode.add_argument("--out", type=pathlib.Path)
    reg.add_argument("--base-table", required=True, type=pathlib.Path)
    reg.add_argument("--aeve-root", required=True, type=pathlib.Path)
    reg.add_argument("--inventory", required=True, type=pathlib.Path)
    reg.add_argument("--mapping", type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
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
                print(json.dumps({"status": "BLOCKED", "reason": exc.reason, "detail": exc.detail}, sort_keys=True))
                return 2
            inventory = _load(args.inventory)
            mapping = _load(args.mapping) if args.mapping else None
            table = register_project_roles(_load(args.base_table), manifest, mapping, matrix)
            problems = validate_extended_table(table, inventory, manifest, matrix, record)
            if problems:
                for line in problems:
                    print(line)
                print(f"INVALID: {len(problems)} problem(s)")
                return 1
            payload = serialize_table(table)
            summary = {"status": "REGISTERED", "role_table_sha256": table_sha256(table), "counts": table["counts"],
                       "project_roles": table["project_roles"]}
    except ProjectRolesError as exc:
        print(json.dumps({"status": "REFUSED", "code": exc.code, "detail": exc.detail}, sort_keys=True))
        return 1
    if args.out is not None:
        _write_atomic(args.out, payload)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
