"""Validator for the check catalog (sprint A, task A-3).

Fails on a missing, duplicate, unknown or unclassified item, on a mechanical check that
lacks input, output or verdict states, and on inconsistent decisions. Optionally verifies
that the inventory still matches the definition files on disk (``--root``).

Usage:
    python tools/catalog/validate_catalog.py --inventory catalog/inventory.json \
        --roles catalog/roles.json [--root <claude root>]

Exit code 0 = valid, 1 = violations (printed one per line), 2 = unreadable input.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

DECISIONS = {"check", "check_plus_model", "model_only", "merge", "drop"}
SCOPES = {"core", "domain_pack", "infrastructure"}
REQUIRED_VERDICTS = {"pass", "fail", "not_run"}
KINDS = {"agent", "skill"}


def _key(entry: dict) -> tuple[str, str]:
    return (str(entry.get("kind", "")), str(entry.get("name", "")))


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_checks(vocab: object) -> list[str]:
    problems: list[str] = []
    if not isinstance(vocab, dict) or not vocab:
        return ["checks: missing or empty vocabulary"]
    for check_id, spec in sorted(vocab.items()):
        if not isinstance(spec, dict):
            problems.append(f"check {check_id}: definition is not an object")
            continue
        for field in ("summary", "input", "output"):
            if not _nonempty(spec.get(field)):
                problems.append(f"check {check_id}: missing {field}")
        verdicts = spec.get("verdicts")
        if not isinstance(verdicts, list) or not REQUIRED_VERDICTS.issubset(set(map(str, verdicts))):
            problems.append(f"check {check_id}: verdicts must include pass, fail and not_run")
        code = spec.get("existing_code")
        if code is not None and not _nonempty(code):
            problems.append(f"check {check_id}: existing_code must be a path or null")
    return problems


def validate(inventory: dict, roles: dict) -> list[str]:
    problems: list[str] = []
    vocab = roles.get("checks")
    problems.extend(validate_checks(vocab))
    vocab_ids = set(vocab) if isinstance(vocab, dict) else set()

    inv_entries = inventory.get("entries")
    role_entries = roles.get("entries")
    if not isinstance(inv_entries, list) or not isinstance(role_entries, list):
        return problems + ["inventory or roles has no entries list"]

    inv_keys: dict[tuple[str, str], int] = {}
    for entry in inv_entries:
        inv_keys[_key(entry)] = inv_keys.get(_key(entry), 0) + 1
    for key, count in sorted(inv_keys.items()):
        if count > 1:
            problems.append(f"inventory: duplicate {key[0]} {key[1]}")

    role_by_key: dict[tuple[str, str], dict] = {}
    for entry in role_entries:
        key = _key(entry)
        if key[0] not in KINDS or not key[1]:
            problems.append(f"roles: entry with invalid kind or name: {key}")
            continue
        if key in role_by_key:
            problems.append(f"roles: duplicate {key[0]} {key[1]}")
            continue
        role_by_key[key] = entry

    for key in sorted(set(inv_keys) - set(role_by_key)):
        problems.append(f"unclassified: {key[0]} {key[1]} is in the inventory but not in roles")
    for key in sorted(set(role_by_key) - set(inv_keys)):
        problems.append(f"unknown: {key[0]} {key[1]} is in roles but not in the inventory")

    final_roles = {
        key for key, e in role_by_key.items()
        if e.get("decision") in ("check", "check_plus_model", "model_only")
    }

    for key, entry in sorted(role_by_key.items()):
        label = f"{key[0]} {key[1]}"
        decision = entry.get("decision")
        if decision not in DECISIONS:
            problems.append(f"{label}: decision {decision!r} is not one of {sorted(DECISIONS)}")
            continue
        if entry.get("scope") not in SCOPES:
            problems.append(f"{label}: scope {entry.get('scope')!r} is not one of {sorted(SCOPES)}")
        if not _nonempty(entry.get("rationale")):
            problems.append(f"{label}: missing rationale")
        checks = entry.get("mechanical_checks")
        if not isinstance(checks, list) or any(not isinstance(c, str) for c in checks):
            problems.append(f"{label}: mechanical_checks must be a list of check ids")
            checks = []
        for check_id in checks:
            if check_id not in vocab_ids:
                problems.append(f"{label}: unknown check id {check_id}")
        if len(set(checks)) != len(checks):
            problems.append(f"{label}: duplicate check id")
        if decision in ("check", "check_plus_model") and not checks:
            problems.append(f"{label}: decision {decision} needs at least one mechanical check")
        if decision in ("check_plus_model", "model_only") and not _nonempty(entry.get("model_remainder")):
            problems.append(f"{label}: decision {decision} needs a model_remainder")
        if decision == "check" and _nonempty(entry.get("model_remainder")):
            problems.append(f"{label}: decision check must not keep a model_remainder")
        if decision == "model_only" and checks:
            problems.append(f"{label}: decision model_only must not list mechanical checks")
        if decision == "drop" and checks:
            problems.append(f"{label}: decision drop must not list mechanical checks")
        merged = entry.get("merged_into")
        if decision == "merge":
            if not _nonempty(merged):
                problems.append(f"{label}: decision merge needs merged_into")
            else:
                targets = [k for k in final_roles if k[1] == merged and k != key]
                if len(targets) != 1:
                    problems.append(f"{label}: merged_into {merged!r} must name exactly one final role (found {len(targets)})")
        elif merged not in (None, ""):
            problems.append(f"{label}: merged_into is only allowed with decision merge")
    return problems


def check_inventory_fresh(inventory: dict, root: pathlib.Path) -> list[str]:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from extract_inventory import build_inventory  # noqa: PLC0415

    current = build_inventory(root)
    problems: list[str] = []
    old = {_key(e): e for e in inventory.get("entries", [])}
    new = {_key(e): e for e in current["entries"]}
    for key in sorted(set(new) - set(old)):
        problems.append(f"stale inventory: {key[0]} {key[1]} exists on disk but not in the inventory")
    for key in sorted(set(old) - set(new)):
        problems.append(f"stale inventory: {key[0]} {key[1]} is in the inventory but not on disk")
    for key in sorted(set(old) & set(new)):
        if old[key].get("source_sha256") != new[key]["source_sha256"]:
            problems.append(f"stale inventory: {key[0]} {key[1]} changed on disk")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=pathlib.Path)
    parser.add_argument("--roles", required=True, type=pathlib.Path)
    parser.add_argument("--root", type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        roles = json.loads(args.roles.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read input: {exc}", file=sys.stderr)
        return 2
    problems = validate(inventory, roles)
    if args.root is not None:
        problems.extend(check_inventory_fresh(inventory, args.root))
    if problems:
        for line in problems:
            print(line)
        print(f"INVALID: {len(problems)} problem(s)")
        return 1
    entries = roles["entries"]
    by_decision: dict[str, int] = {}
    for entry in entries:
        by_decision[entry["decision"]] = by_decision.get(entry["decision"], 0) + 1
    print(f"VALID: {len(entries)} items, decisions {dict(sorted(by_decision.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
