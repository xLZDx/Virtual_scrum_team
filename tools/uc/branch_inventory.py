"""Read-only inventory and landing map of pushed branches (sprint U3, task U3-1).

For every branch the tool lists the files the branch changed since its merge base with the target
(main) and states for each file how the branch version relates to the target (ALREADY_IN_MAIN,
NEW, DIVERGED, BRANCH_DELETES, BRANCH_DELETES_ABSENT), then assigns exactly one landing class from
an ordered rules file: LAND, EVIDENCE_ONLY or DROP (ALREADY_IN_MAIN needs no action). The check
fails (exit 3) when any file stays unclassified, so a new file can never be silently skipped.

LAND means "candidate to land after its own per-task review", never "reviewed"; the class comes from
the path category in the rules file, not from reading the file. Nothing is merged, checked out or
written inside the repository except the optional --out file.

Usage:
    python tools/uc/branch_inventory.py map --repo <dir> --rules <json> --target main --branches a,b --out <json>
    python tools/uc/branch_inventory.py check --map <json>
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import aeve_probe  # noqa: E402

CLASSES = ("LAND", "EVIDENCE_ONLY", "DROP")
FINAL_CLASSES = CLASSES + ("ALREADY_IN_MAIN",)
RELATIONS = ("ALREADY_IN_MAIN", "NEW", "DIVERGED", "BRANCH_DELETES", "BRANCH_DELETES_ABSENT")
GIT_TIMEOUT = 120


class InventoryError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _git(repo: pathlib.Path, *args: str) -> bytes:
    git = aeve_probe._find_git(exclude=repo)
    if git is None:
        raise InventoryError("GIT_NOT_FOUND")
    env = {k: v for k, v in os.environ.items() if k in ("SYSTEMROOT", "PATH", "TEMP", "TMP", "HOME", "USERPROFILE")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        done = subprocess.run([git, "-C", str(repo), *args], capture_output=True, timeout=GIT_TIMEOUT, env=env,
                              shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InventoryError("GIT_FAILED", type(exc).__name__) from exc
    if done.returncode != 0:
        raise InventoryError("GIT_FAILED", done.stderr.decode("utf-8", "replace")[:200])
    return done.stdout


def _tree(repo: pathlib.Path, ref: str) -> dict[str, str]:
    """path -> blob id for every file of a ref."""
    out = _git(repo, "ls-tree", "-r", "-z", "--full-tree", ref)
    tree: dict[str, str] = {}
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        parts = meta.split()
        if len(parts) != 3:
            raise InventoryError("TREE_PARSE", rec[:80].decode("utf-8", "replace"))
        tree[path.decode("utf-8", "surrogateescape")] = parts[2].decode("ascii")
    return tree


def _changed(repo: pathlib.Path, base: str, ref: str) -> dict[str, str]:
    """path -> status letter (A, M, D, T) of what the branch changed since the merge base."""
    out = _git(repo, "diff", "--name-status", "-z", "--no-renames", f"{base}..{ref}")
    fields = [f for f in out.split(b"\0")]
    changed: dict[str, str] = {}
    i = 0
    while i + 1 < len(fields):
        status = fields[i].decode("ascii", "replace")
        path = fields[i + 1].decode("utf-8", "surrogateescape")
        if not status:
            break
        changed[path] = status[0]
        i += 2
    return changed


def _glob_to_regex(glob: str) -> re.Pattern:
    out, i = "", 0
    while i < len(glob):
        c = glob[i]
        if glob[i:i + 3] == "**/":
            out += "(?:.*/)?"
            i += 3
        elif glob[i:i + 2] == "**":
            out += ".*"
            i += 2
        elif c == "*":
            out += "[^/]*"
            i += 1
        elif c == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(c)
            i += 1
    return re.compile(out)


def load_rules(path: pathlib.Path) -> list[dict]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InventoryError("RULES_UNREADABLE", type(exc).__name__) from exc
    rules = doc.get("rules") if isinstance(doc, dict) else None
    if not isinstance(rules, list) or not rules:
        raise InventoryError("RULES_INVALID", "no rules list")
    compiled = []
    for n, rule in enumerate(rules):
        if (not isinstance(rule, dict) or rule.get("class") not in CLASSES
                or not isinstance(rule.get("glob"), str) or not rule["glob"]
                or not isinstance(rule.get("reason"), str) or not rule["reason"].strip()):
            raise InventoryError("RULES_INVALID", f"rule {n} needs glob, class in {CLASSES} and a reason")
        compiled.append({"glob": rule["glob"], "class": rule["class"], "reason": rule["reason"],
                         "regex": _glob_to_regex(rule["glob"])})
    return compiled


def classify(path: str, relation: str, rules: list[dict]) -> dict:
    if relation == "ALREADY_IN_MAIN":
        return {"class": "ALREADY_IN_MAIN", "reason": "identical content already in the target branch", "rule": None}
    if relation in ("BRANCH_DELETES", "BRANCH_DELETES_ABSENT"):
        return {"class": "DROP", "reason": "a deletion on the branch is never landed; the target keeps its file",
                "rule": "built-in:deletion"}
    for rule in rules:
        if rule["regex"].fullmatch(path):
            return {"class": rule["class"], "reason": rule["reason"], "rule": rule["glob"]}
    return {"class": "UNCLASSIFIED", "reason": "no rule matches this path", "rule": None}


def build_map(repo: pathlib.Path, rules: list[dict], target: str, branches: list[str]) -> dict:
    target_tree = _tree(repo, target)
    target_sha = _git(repo, "rev-parse", target).decode().strip()
    result = {"version": 1, "target": target, "target_head": target_sha, "branches": {}}
    refs = {}
    for name in branches:
        refs[name] = _git(repo, "rev-parse", "--verify", f"refs/remotes/origin/{name}^{{commit}}").decode().strip()
    for name, ref in refs.items():
        base = _git(repo, "merge-base", target, ref).decode().strip()
        branch_tree = _tree(repo, ref)
        changed = _changed(repo, base, ref)
        files = {}
        for path in sorted(changed):
            status = changed[path]
            if status == "D":
                relation = "BRANCH_DELETES" if path in target_tree else "BRANCH_DELETES_ABSENT"
            elif path not in target_tree:
                relation = "NEW"
            elif target_tree[path] == branch_tree.get(path):
                relation = "ALREADY_IN_MAIN"
            else:
                relation = "DIVERGED"
            files[path] = {"status": status, "relation": relation, **classify(path, relation, rules)}
        subsumed_by = [other for other, oref in refs.items()
                       if other != name and _is_ancestor(repo, ref, oref)]
        result["branches"][name] = {"head": ref, "merge_base": base, "file_count": len(files),
                                    "subsumed_by": sorted(subsumed_by), "files": files}
    result["summary"] = summarize(result)
    return result


def _is_ancestor(repo: pathlib.Path, a: str, b: str) -> bool:
    git = aeve_probe._find_git(exclude=repo)
    if git is None:
        raise InventoryError("GIT_NOT_FOUND")
    done = subprocess.run([git, "-C", str(repo), "merge-base", "--is-ancestor", a, b], capture_output=True,
                          timeout=GIT_TIMEOUT, shell=False)
    if done.returncode not in (0, 1):
        raise InventoryError("GIT_FAILED", done.stderr.decode("utf-8", "replace")[:200])
    return done.returncode == 0


def summarize(doc: dict) -> dict:
    summary: dict[str, dict] = {}
    for name, branch in doc["branches"].items():
        counts: dict[str, int] = {}
        needs_merge = 0
        for entry in branch["files"].values():
            counts[entry["class"]] = counts.get(entry["class"], 0) + 1
            if entry["class"] == "LAND" and entry["relation"] == "DIVERGED":
                needs_merge += 1
        summary[name] = {"files": branch["file_count"], "by_class": dict(sorted(counts.items())),
                         "land_needs_manual_merge": needs_merge}
    return summary


def check_map(doc: object) -> list[str]:
    """Return a list of problems; an empty list means every file is classified exactly once."""
    problems: list[str] = []
    if not isinstance(doc, dict) or not isinstance(doc.get("branches"), dict) or not doc["branches"]:
        return ["map has no branches"]
    for name, branch in doc["branches"].items():
        files = branch.get("files") if isinstance(branch, dict) else None
        if not isinstance(files, dict):
            problems.append(f"{name}: no files object")
            continue
        if branch.get("file_count") != len(files):
            problems.append(f"{name}: file_count {branch.get('file_count')} != {len(files)} listed files")
        for path, entry in files.items():
            if not isinstance(entry, dict) or entry.get("class") not in FINAL_CLASSES:
                problems.append(f"{name}: {path} is {entry.get('class') if isinstance(entry, dict) else entry!r}")
            elif not str(entry.get("reason", "")).strip():
                problems.append(f"{name}: {path} has no reason")
            elif entry.get("relation") not in RELATIONS:
                problems.append(f"{name}: {path} has an unknown relation {entry.get('relation')!r}")
            elif (entry["class"] == "ALREADY_IN_MAIN") != (entry["relation"] == "ALREADY_IN_MAIN"):
                problems.append(f"{name}: {path} has class {entry['class']} that contradicts relation {entry['relation']}")
            elif entry["relation"] in ("BRANCH_DELETES", "BRANCH_DELETES_ABSENT") and entry["class"] != "DROP":
                problems.append(f"{name}: {path} is a branch deletion but has class {entry['class']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("map")
    m.add_argument("--repo", required=True, type=pathlib.Path)
    m.add_argument("--rules", required=True, type=pathlib.Path)
    m.add_argument("--target", default="main")
    m.add_argument("--branches", required=True)
    m.add_argument("--out", type=pathlib.Path)
    c = sub.add_parser("check")
    c.add_argument("--map", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "map":
            branches = [b.strip() for b in args.branches.split(",") if b.strip()]
            doc = build_map(args.repo, load_rules(args.rules), args.target, branches)
            problems = check_map(doc)
            text = json.dumps(doc, indent=1, sort_keys=True)
            if args.out:
                try:
                    args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
                except OSError as exc:
                    print(json.dumps({"status": "NOT_RUN", "reason": "OUTPUT_UNWRITABLE", "detail": type(exc).__name__}))
                    return 2
            print(json.dumps({"status": "COMPLETE" if not problems else "INCOMPLETE", "problems": problems[:20],
                              "problem_count": len(problems), "summary": doc["summary"]}, indent=1, sort_keys=True))
            return 0 if not problems else 3
        try:
            doc = json.loads(args.map.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(json.dumps({"status": "NOT_RUN", "reason": "MAP_UNREADABLE", "detail": type(exc).__name__}))
            return 2
        problems = check_map(doc)
        print(json.dumps({"status": "COMPLETE" if not problems else "INCOMPLETE", "problems": problems[:20],
                          "problem_count": len(problems)}, indent=1, sort_keys=True))
        return 0 if not problems else 3
    except InventoryError as exc:
        print(json.dumps({"status": "NOT_RUN", "reason": exc.reason, "detail": exc.detail[:200]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
