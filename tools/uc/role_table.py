"""Role table builder and validator (sprint U1, task U1-4).

The role table maps every agent and skill definition to a class, a canonical role (for aliases),
the AEVE profile and executors that really exist, and an honest coverage state. It pins the AEVE
head and matrix digest it was built against. The validator makes the table stricter than the
AEVE matrix, never looser: a role may claim coverage only when the matrix lists executors for
its canonical role, and the listed executors must equal the matrix's.

Usage:
    python tools/uc/role_table.py build --aeve-root D:/Repo/AEVE --inventory catalog/inventory.json \
        --draft catalog/roles.json --out catalog/role_table.json
    python tools/uc/role_table.py validate --aeve-root D:/Repo/AEVE --inventory catalog/inventory.json \
        --table catalog/role_table.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import aeve_probe  # noqa: E402

TABLE_VERSION = 1
CLASSES = ("LOCAL", "LOCAL_PLUS_MODEL", "MODEL_ONLY", "OUT_OF_SCOPE")
COVERAGE_STATES = (
    "COVERED_PARTIAL",
    "NOT_COVERED_NO_EXECUTOR",
    "NOT_COVERED_NO_PROFILE",
    "NOT_APPLICABLE",
)
_DECISION_TO_CLASS = {
    "check": "LOCAL",
    "check_plus_model": "LOCAL_PLUS_MODEL",
    "model_only": "MODEL_ONLY",
    "drop": "OUT_OF_SCOPE",
}


def _matrix_index(matrix: dict) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for row in matrix["rows"]:
        index[row["id"]] = sorted(row.get("deterministic_executors") or [])
    return index


def _canonical_name(entry: dict) -> str:
    return entry.get("merged_into") or entry["name"]


def build_role_table(inventory: dict, draft: dict, matrix: dict, probe_record: dict) -> dict:
    index = _matrix_index(matrix)
    draft_by_key = {(e["kind"], e["name"]): e for e in draft["entries"]}
    finals: dict[str, dict] = {}
    for entry in draft["entries"]:
        if entry["decision"] in _DECISION_TO_CLASS and entry["name"] not in finals:
            finals[entry["name"]] = entry
    entries = []
    for item in inventory["entries"]:
        key = (item["kind"], item["name"])
        if key not in draft_by_key:
            raise ValueError(f"inventory item without a draft decision: {key}")
        source = draft_by_key[key]
        canonical = _canonical_name(source)
        target = finals.get(canonical) if source["decision"] == "merge" else source
        if target is None:
            raise ValueError(f"merge target is not a final role: {key} -> {canonical}")
        intended = _DECISION_TO_CLASS[target["decision"]]
        draft_class = intended
        executors = index.get(canonical, [])
        has_profile = canonical in index
        upgraded = False
        if intended in ("MODEL_ONLY", "OUT_OF_SCOPE") and executors:
            intended, upgraded = "LOCAL_PLUS_MODEL", True
        if intended in ("MODEL_ONLY", "OUT_OF_SCOPE"):
            state, reason = "NOT_APPLICABLE", target["rationale"]
        elif executors:
            state, reason = "COVERED_PARTIAL", "AEVE lists deterministic executors for this role"
        elif has_profile:
            state, reason = "NOT_COVERED_NO_EXECUTOR", "AEVE has a profile but no deterministic executor"
        else:
            state, reason = "NOT_COVERED_NO_PROFILE", "no AEVE profile"
        entries.append({
            "kind": item["kind"],
            "name": item["name"],
            "class": intended,
            "draft_class": draft_class,
            "class_upgraded_by_evidence": upgraded,
            "canonical_role": canonical,
            "aeve_profile": canonical if has_profile else None,
            "executors": executors,
            "coverage_state": state,
            "reason": reason,
            "model_remainder_hint": target.get("model_remainder", ""),
        })
    entries.sort(key=lambda e: (e["kind"], e["name"]))
    return {
        "version": TABLE_VERSION,
        "aeve_pin": {"head": probe_record["aeve_head"], "matrix_digest_sha256": probe_record["matrix"]["digest_sha256"]},
        "counts": _counts(entries),
        "entries": entries,
    }


def _counts(entries: list[dict]) -> dict:
    counts: dict = {"total": len(entries), "by_class": {}, "by_coverage_state": {}}
    for entry in entries:
        counts["by_class"][entry["class"]] = counts["by_class"].get(entry["class"], 0) + 1
        counts["by_coverage_state"][entry["coverage_state"]] = counts["by_coverage_state"].get(entry["coverage_state"], 0) + 1
    counts["by_class"] = dict(sorted(counts["by_class"].items()))
    counts["by_coverage_state"] = dict(sorted(counts["by_coverage_state"].items()))
    return counts


def validate_role_table(table: object, inventory: dict, matrix: dict, probe_record: dict) -> list[str]:
    """Return a list of problems; an empty list means the table is valid."""
    problems: list[str] = []
    if not isinstance(table, dict) or table.get("version") != TABLE_VERSION:
        return ["table: missing or wrong version"]
    pin = table.get("aeve_pin") or {}
    if pin.get("head") != probe_record["aeve_head"]:
        problems.append("pin: AEVE head differs from the probed checkout")
    if pin.get("matrix_digest_sha256") != probe_record["matrix"]["digest_sha256"]:
        problems.append("pin: AEVE matrix digest differs from the probed matrix")
    entries = table.get("entries")
    if not isinstance(entries, list):
        return problems + ["table: entries is not a list"]
    index = _matrix_index(matrix)
    by_key: dict[tuple[str, str], dict] = {}
    for entry in entries:
        key = (entry.get("kind"), entry.get("name"))
        if key in by_key:
            problems.append(f"duplicate entry {key}")
        by_key[key] = entry
    inv_keys = {(i["kind"], i["name"]) for i in inventory["entries"]}
    for key in sorted(inv_keys - set(by_key)):
        problems.append(f"missing entry {key}")
    for key in sorted(set(by_key) - inv_keys):
        problems.append(f"unknown entry {key}")
    names = {name for _, name in by_key}
    for key, entry in sorted(by_key.items()):
        label = f"{key[0]} {key[1]}"
        if entry.get("class") not in CLASSES:
            problems.append(f"{label}: bad class")
        if entry.get("coverage_state") not in COVERAGE_STATES:
            problems.append(f"{label}: bad coverage_state")
        canonical = entry.get("canonical_role")
        if canonical not in names:
            problems.append(f"{label}: canonical_role {canonical!r} is not a known role name")
        else:
            peers = [e for k, e in by_key.items() if k[1] == canonical]
            if canonical != key[1] and any(p.get("canonical_role") != canonical for p in peers):
                problems.append(f"{label}: canonical_role chain through {canonical!r}")
            if canonical != key[1] and any(p.get("class") != entry.get("class") for p in peers):
                problems.append(f"{label}: class differs from its canonical role")
        executors = entry.get("executors")
        if not isinstance(executors, list):
            problems.append(f"{label}: executors is not a list")
            continue
        matrix_executors = index.get(canonical, [])
        if sorted(executors) != matrix_executors:
            problems.append(f"{label}: executors differ from the matrix for {canonical!r}")
        state = entry.get("coverage_state")
        if state == "COVERED_PARTIAL" and not matrix_executors:
            problems.append(f"{label}: claims coverage but the matrix lists no executor")
        if state in ("NOT_COVERED_NO_EXECUTOR", "NOT_COVERED_NO_PROFILE", "NOT_APPLICABLE") and executors:
            problems.append(f"{label}: {state} but executors are listed")
        if state == "NOT_COVERED_NO_PROFILE" and canonical in index:
            problems.append(f"{label}: says no AEVE profile but the matrix has one")
        if entry.get("class") in ("LOCAL", "LOCAL_PLUS_MODEL") and state == "NOT_APPLICABLE":
            problems.append(f"{label}: local class cannot be NOT_APPLICABLE")
        if entry.get("class") in ("MODEL_ONLY", "OUT_OF_SCOPE") and state != "NOT_APPLICABLE":
            problems.append(f"{label}: non-local class must be NOT_APPLICABLE")
    if table.get("counts") != _counts([e for e in entries if isinstance(e, dict)]):
        problems.append("counts: stored counts differ from the recomputed counts")
    return problems


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "validate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--aeve-root", required=True, type=pathlib.Path)
        cmd.add_argument("--inventory", required=True, type=pathlib.Path)
        if name == "build":
            cmd.add_argument("--draft", required=True, type=pathlib.Path)
            cmd.add_argument("--out", required=True, type=pathlib.Path)
        else:
            cmd.add_argument("--table", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        record = aeve_probe.probe(args.aeve_root)
        matrix = aeve_probe.load_matrix(args.aeve_root)
    except aeve_probe.AeveProbeError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": exc.reason, "detail": exc.detail}, sort_keys=True))
        return 2
    inventory = _load(args.inventory)
    if args.command == "build":
        table = build_role_table(inventory, _load(args.draft), matrix, record)
        args.out.write_bytes((json.dumps(table, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
        problems = validate_role_table(table, inventory, matrix, record)
        if problems:
            for line in problems:
                print(line)
            print(f"INVALID: {len(problems)} problem(s)")
            return 1
        args.out.write_bytes((json.dumps(table, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
        table = _load(args.table)
        problems = validate_role_table(table, inventory, matrix, record)
    if problems:
        for line in problems:
            print(line)
        print(f"INVALID: {len(problems)} problem(s)")
        return 1
    print(json.dumps({"status": "VALID", "counts": table["counts"], "aeve_pin": table["aeve_pin"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
