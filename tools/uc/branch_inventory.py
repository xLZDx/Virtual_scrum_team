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


def _git_code(repo: pathlib.Path, *args: str) -> tuple[int, bytes, bytes]:
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
    return done.returncode, done.stdout, done.stderr


def _git(repo: pathlib.Path, *args: str) -> bytes:
    code, out, err = _git_code(repo, *args)
    if code != 0:
        raise InventoryError("GIT_FAILED", err.decode("utf-8", "replace")[:200])
    return out


def _tree(repo: pathlib.Path, ref: str) -> dict[str, tuple[str, str]]:
    """path -> (mode, blob id) for every file of a ref."""
    out = _git(repo, "ls-tree", "-r", "-z", "--full-tree", ref)
    tree: dict[str, tuple[str, str]] = {}
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        parts = meta.split()
        if len(parts) != 3:
            raise InventoryError("TREE_PARSE", rec[:80].decode("utf-8", "replace"))
        tree[path.decode("utf-8", "surrogateescape")] = (parts[0].decode("ascii"), parts[2].decode("ascii"))
    return tree


def _changed(repo: pathlib.Path, base: str, ref: str) -> dict[str, str]:
    """path -> status letter (A, M, D, T) of what the branch changed since the merge base."""
    out = _git(repo, "diff-tree", "-r", "--no-renames", "--name-status", "-z", base, ref)
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


MAX_GLOB_LENGTH = 200
MAX_GLOB_WILDCARDS = 6


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
    return re.compile(out, re.DOTALL)


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
        if len(rule["glob"]) > MAX_GLOB_LENGTH or rule["glob"].count("*") > MAX_GLOB_WILDCARDS:
            raise InventoryError("RULES_INVALID", f"rule {n} glob is too long or has too many wildcards")
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


_REF_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._/-]{0,199}$")


def _checked_name(kind: str, name: str) -> str:
    """A branch or target name must be a plain ref name: no revision syntax, no option-like start."""
    if (not isinstance(name, str) or not _REF_NAME.match(name) or ".." in name or name.endswith((".lock", "/", "."))
            or "//" in name or name == "HEAD" or name.endswith("/HEAD")):
        raise InventoryError("BAD_REF_NAME", f"{kind} name {str(name)[:60]!r} is not a plain ref name")
    return name


def _resolve(repo: pathlib.Path, full_ref: str) -> str:
    code, out, err = _git_code(repo, "rev-parse", "--verify", "--end-of-options", f"{full_ref}^{{commit}}")
    if code != 0:
        raise InventoryError("GIT_FAILED", err.decode("utf-8", "replace")[:200])
    return out.decode().strip()


def build_map(repo: pathlib.Path, rules: list[dict], target: str, branches: list[str]) -> dict:
    target = _checked_name("target", target)
    if target.startswith("origin/"):
        target_full = f"refs/remotes/{target}"
    else:
        target_full = f"refs/heads/{target}"
    target_sha = _resolve(repo, target_full)
    if target_full.startswith("refs/heads/"):
        code, out, _ = _git_code(repo, "rev-parse", "--verify", "--quiet", "--end-of-options",
                                 f"refs/remotes/origin/{target}^{{commit}}")
        remote_sha = out.decode().strip() if code == 0 else None
        if remote_sha is not None and remote_sha != target_sha:
            raise InventoryError("TARGET_STALE", f"local {target} differs from origin/{target}; use origin/{target}")
    target_tree = _tree(repo, target_sha)
    result = {"version": 1, "target": target, "target_head": target_sha, "branches": {}}
    refs = {}
    for name in branches:
        refs[name] = _resolve(repo, f"refs/remotes/origin/{_checked_name('branch', name)}")
    for name, ref in refs.items():
        base = _git(repo, "merge-base", target_sha, ref).decode().strip()
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
    code, _, err = _git_code(repo, "merge-base", "--is-ancestor", a, b)
    if code not in (0, 1):
        raise InventoryError("GIT_FAILED", err.decode("utf-8", "replace")[:200])
    return code == 0


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
    m.add_argument("--target", default="origin/main")
    m.add_argument("--branches", required=True)
    m.add_argument("--out", type=pathlib.Path)
    c = sub.add_parser("check")
    c.add_argument("--map", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "map":
            branches = [b.strip() for b in args.branches.split(",") if b.strip()]
            if args.out:
                try:
                    args.out.unlink(missing_ok=True)  # a failed run must not leave an older COMPLETE map behind
                except OSError:
                    pass
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
