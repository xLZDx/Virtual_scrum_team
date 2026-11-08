"""Deterministic inventory of agent and skill definitions (sprint A, task A-1).

Reads every agent (``agents/*.md``) and skill (``skills/*/SKILL.md``) definition from a
Claude configuration root and writes a stable JSON inventory. No model is involved: the
output depends only on the files on disk.

Usage:
    python tools/catalog/extract_inventory.py --root <claude root> --out catalog/inventory.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

INVENTORY_VERSION = 1
_FRONTMATTER_FENCE = "---"


class InventoryError(Exception):
    """A definition file cannot be turned into a trustworthy inventory entry."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> dict[str, str]:
    """Return top-level ``key: value`` pairs of a leading ``---`` block.

    Only scalar top-level keys are read; nested blocks and list items are ignored. Folded
    or literal multi-line values (``>``/``|``) are joined with single spaces.
    """
    lines = text.lstrip("﻿").replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return {}
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_FENCE:
            end = index
            break
    if end is None:
        return {}
    result: dict[str, str] = {}
    key = None
    for line in lines[1:end]:
        if line[:1] in (" ", "\t"):
            if key is not None and line.strip() and not line.lstrip().startswith("- "):
                result[key] = (result[key] + " " + line.strip()).strip()
            continue
        if ":" not in line:
            key = None
            continue
        name, _, value = line.partition(":")
        key = name.strip()
        value = value.strip()
        result[key] = "" if value in (">", "|", ">-", "|-") else _unquote(value)
    return result


def _entry(kind: str, path: pathlib.Path, root: pathlib.Path) -> dict[str, object]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InventoryError(f"{path}: not valid UTF-8 ({exc})") from exc
    meta = parse_frontmatter(text)
    default_name = path.parent.name if kind == "skill" else path.stem
    name = meta.get("name") or default_name
    return {
        "kind": kind,
        "name": name,
        "path": path.relative_to(root).as_posix(),
        "description": meta.get("description", ""),
        "tools": meta.get("tools", ""),
        "model": meta.get("model", ""),
        "deprecated": meta.get("deprecated", "").lower() == "true",
        "has_frontmatter": bool(meta),
        "source_sha256": _sha256(raw),
        "size_bytes": len(raw),
    }


def build_inventory(root: pathlib.Path) -> dict[str, object]:
    root = root.resolve()
    agents_dir = root / "agents"
    skills_dir = root / "skills"
    entries: list[dict[str, object]] = []
    if agents_dir.is_dir():
        for path in sorted(agents_dir.glob("*.md")):
            if path.is_file():
                entries.append(_entry("agent", path, root))
    if skills_dir.is_dir():
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            if path.is_file():
                entries.append(_entry("skill", path, root))
    seen: dict[tuple[str, str], str] = {}
    for item in entries:
        key = (str(item["kind"]), str(item["name"]))
        if key in seen:
            raise InventoryError(
                f"duplicate {key[0]} name {key[1]!r}: {seen[key]} and {item['path']}"
            )
        seen[key] = str(item["path"])
    entries.sort(key=lambda item: (str(item["kind"]), str(item["name"])))
    return {
        "version": INVENTORY_VERSION,
        "counts": {
            "agent": sum(1 for e in entries if e["kind"] == "agent"),
            "skill": sum(1 for e in entries if e["kind"] == "skill"),
            "total": len(entries),
        },
        "entries": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        inventory = build_inventory(args.root)
    except InventoryError as exc:
        print(f"inventory failed: {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(inventory, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    args.out.write_bytes(payload.encode("utf-8"))
    counts = inventory["counts"]
    print(f"wrote {args.out} agents={counts['agent']} skills={counts['skill']} total={counts['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
