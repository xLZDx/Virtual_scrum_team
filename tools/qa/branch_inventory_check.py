"""Deterministic completeness check for the U3 branch inventory.

Read-only: it runs a fixed set of git plumbing commands (no shell, no network,
no checkout, no fetch), computes the file universe of each pushed branch as
``git diff --name-status --no-renames <main-sha>...<branch-sha> --`` and verifies
that every file is matched by exactly one classification rule.

Exit codes: 0 = complete, 1 = inventory check failed, 2 = usage, git or
rules-file error, 3 = unexpected internal error. A failure prints one typed JSON
object on stderr; success prints a JSON summary on stdout. ``--print-header``
prints the exact text that must be the first fenced block of the inventory.
This is an inventory check, not a test suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ALLOWED_CLASSES = ("LAND", "EVIDENCE_ONLY", "DROPPED", "ALREADY_ON_MAIN")
# identical: same mode+blob as main. differs_conflict: main has the path with other content and
# main changed it since the merge-base (or it was added on both sides). differs_clean: branch
# edited it, main still holds the merge-base content. absent_new: not on main and not at the
# merge-base. absent_removed_on_main: at the merge-base, removed on main.
ALLOWED_MAIN_STATES = ("identical", "differs_conflict", "differs_clean", "absent_new",
                       "absent_removed_on_main", "deleted_in_branch")
CONFLICT_STATES = ("differs_conflict", "absent_removed_on_main")
ALLOWED_LANDS_IN = ("U3-3", "U3-4", "U3-5", "U3-6")
ALLOWED_REFERENCE_FOR = ("U3-2", "U3-3", "U3-4", "U3-5", "U3-6")
ALLOWED_FLAGS = ("CONFLICT_WITH_MAIN", "DUPLICATES_MAIN_TOOLS_QA", "REMOVED_ON_MAIN",
                 "CLEAN_EDIT_NOT_LANDED")
RULE_KEYS = {"rule_id", "branch", "globs", "exclude", "main_state", "class", "reason",
             "lands_in", "reference_for", "flags"}
REQUIRED_RULE_KEYS = {"rule_id", "branch", "globs", "main_state", "class", "reason", "lands_in"}
REF_PATTERN = re.compile(r"origin/[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
FENCE_PATTERN = re.compile(r"^```[A-Za-z]*\n(.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)
GIT_TIMEOUT_SECONDS = 120
MAX_GIT_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_LISTED_PATHS = 500
MAX_RULES = 500

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = "docs/sdlc/u3/branch_inventory_rules.json"


class CheckError(Exception):
    """A typed failure; ``kind`` becomes the ``error`` field of the stderr JSON."""

    def __init__(self, kind: str, detail: str, items: list[Any] | None = None, code: int = 1):
        super().__init__(detail)
        self.kind = kind
        self.detail = detail
        self.items = (items or [])[:MAX_LISTED_PATHS]
        self.code = code


def git(*args: str) -> bytes:
    """Run one read-only git command with a fixed argv, a timeout, a size bound and no shell."""
    argv = ["git", "-C", str(REPO_ROOT), *args]
    try:
        proc = subprocess.run(argv, capture_output=True, shell=False, timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise CheckError("GIT_FAILURE", f"git {args[0]} timed out", code=2) from exc
    except OSError as exc:
        raise CheckError("GIT_FAILURE", f"cannot start git: {exc}", code=2) from exc
    if len(proc.stdout) > MAX_GIT_OUTPUT_BYTES:
        raise CheckError("GIT_FAILURE", f"git {args[0]} output exceeds the byte bound", code=2)
    if proc.returncode != 0:
        raise CheckError("GIT_FAILURE", f"git {args[0]} failed: {proc.stderr[:2000].decode('utf-8', 'replace').strip()}",
                         code=2)
    return proc.stdout


def require_ref(ref: Any) -> str:
    if not isinstance(ref, str) or not REF_PATTERN.match(ref) or ".." in ref or ref.endswith(".lock"):
        raise CheckError("BAD_REF", f"ref must be a plain origin/ ref: {ref!r}", code=2)
    return ref


def resolve(ref: str) -> str:
    """Resolve ``origin/x`` through refs/remotes/ to a commit SHA, once."""
    sha = git("rev-parse", "--verify", "--quiet", "refs/remotes/" + ref + "^{commit}").decode().strip()
    if not SHA_PATTERN.match(sha):
        raise CheckError("BAD_REF", f"ref does not resolve to a commit: {ref}", code=2)
    return sha


def tree_entries(sha: str) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    out = git("ls-tree", "-r", "-z", "--full-tree", sha, "--").decode("utf-8", "surrogateescape")
    for entry in out.split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            mode, _kind, blob = meta.split()
            entries[path] = (mode, blob)
    return entries


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """``**`` matches anything including '/', ``*`` and ``?`` do not cross '/'."""
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z", re.DOTALL)


def load_rules(rules_path: Path) -> tuple[dict[str, Any], str]:
    raw = rules_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckError("BAD_RULES", f"rules file is not valid UTF-8 JSON: {exc}", code=2) from exc
    if not isinstance(doc, dict) or doc.get("schema_version") != SCHEMA_VERSION:
        raise CheckError("BAD_RULES", f"schema_version must be {SCHEMA_VERSION}", code=2)
    if set(doc) != {"schema_version", "base_ref", "branches", "rules"}:
        raise CheckError("BAD_RULES", "top-level keys must be schema_version, base_ref, branches, rules", code=2)
    require_ref(doc["base_ref"])
    if doc["base_ref"] != "origin/main":
        raise CheckError("BAD_REF", "base_ref must be origin/main", code=2)
    branches = doc["branches"]
    if not isinstance(branches, list) or not branches:
        raise CheckError("BAD_RULES", "branches must be a non-empty list", code=2)
    for ref in branches:
        require_ref(ref)
    if len(set(branches)) != len(branches):
        raise CheckError("BAD_RULES", "branches must be unique", code=2)
    if not isinstance(doc["rules"], list) or not doc["rules"] or len(doc["rules"]) > MAX_RULES:
        raise CheckError("BAD_RULES", "rules must be a non-empty bounded list", code=2)
    return doc, digest


def _str_list(value: Any, allowed: tuple[str, ...] | None = None, allow_empty: bool = True) -> bool:
    if not isinstance(value, list) or (not allow_empty and not value):
        return False
    if not all(isinstance(v, str) and v for v in value) or len(set(value)) != len(value):
        return False
    return allowed is None or all(v in allowed for v in value)


def validate_rules(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Type-safe static validation; returns error records (empty when well-formed)."""
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, rule in enumerate(doc["rules"]):
        if not isinstance(rule, dict):
            errors.append({"type": "BAD_RULE", "rule": f"#{idx}", "detail": "rule is not an object"})
            continue
        rid = rule.get("rule_id")
        label = rid if isinstance(rid, str) and rid else f"#{idx}"

        def bad(detail: str, kind: str = "BAD_RULE") -> None:
            errors.append({"type": kind, "rule": label, "detail": detail})

        keys = set(rule)
        if not REQUIRED_RULE_KEYS <= keys or not keys <= RULE_KEYS:
            bad(f"keys {sorted(keys)} not allowed")
            continue
        if not isinstance(rid, str) or not rid or rid in seen:
            bad("rule_id must be a unique non-empty string")
        else:
            seen.add(rid)
        if not isinstance(rule["class"], str) or rule["class"] not in ALLOWED_CLASSES:
            bad(repr(rule["class"]), "BAD_CLASS")
        if not isinstance(rule["reason"], str) or not rule["reason"].strip():
            bad("reason is empty or not a string", "EMPTY_REASON")
        branch = rule["branch"]
        if not isinstance(branch, str) or (branch != "*" and branch not in doc["branches"]):
            bad(f"unknown branch {branch!r}")
        if not _str_list(rule["globs"], allow_empty=False):
            bad("globs must be a non-empty list of unique non-empty strings")
        if not _str_list(rule.get("exclude", [])):
            bad("exclude must be a list of unique non-empty strings")
        states = rule["main_state"]
        states_ok = _str_list(states, ALLOWED_MAIN_STATES, allow_empty=False)
        if not states_ok:
            bad(f"main_state must be a non-empty list drawn from {ALLOWED_MAIN_STATES}")
        elif (rule["class"] == "ALREADY_ON_MAIN") != (states == ["identical"]):
            bad("ALREADY_ON_MAIN is allowed only for, and requires, main_state [identical]")
        if not _str_list(rule.get("flags", []), ALLOWED_FLAGS):
            bad(f"flags must be drawn from {ALLOWED_FLAGS}")
        ref_for = rule.get("reference_for")
        if ref_for is not None and ref_for not in ALLOWED_REFERENCE_FOR:
            bad(f"reference_for must be null or one of {ALLOWED_REFERENCE_FOR}")
        if rule["class"] == "LAND":
            if rule["lands_in"] not in ALLOWED_LANDS_IN:
                bad(f"LAND needs lands_in in {ALLOWED_LANDS_IN}")
        elif rule["lands_in"] is not None:
            bad("lands_in must be null unless class is LAND")
    return errors


def branch_universe(base_sha: str, sha: str, main_tree: dict[str, tuple[str, str]],
                    base_tree: dict[str, tuple[str, str]]) -> list[dict[str, Any]]:
    branch_tree = tree_entries(sha)
    parts = git("diff", "--name-status", "--no-renames", "-z", f"{base_sha}...{sha}", "--").decode(
        "utf-8", "surrogateescape").split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) % 2:
        raise CheckError("GIT_FAILURE", "unexpected name-status output", code=2)
    files = []
    for i in range(0, len(parts), 2):
        status, path = parts[i], parts[i + 1]
        entry, on_main, at_base = branch_tree.get(path), main_tree.get(path), base_tree.get(path)
        if entry is None:
            state = "deleted_in_branch"
        elif on_main is None:
            state = "absent_removed_on_main" if at_base is not None else "absent_new"
        elif on_main == entry:
            state = "identical"
        else:
            state = "differs_conflict" if on_main != at_base else "differs_clean"
        files.append({"path": path, "status": status, "main_state": state})
    return files


def build_header(summary: dict[str, Any]) -> str:
    """The exact text that must be the first fenced block of the inventory."""
    lines = [f"rules_sha256: {summary['rules_sha256']}",
             f"base_ref: {summary['base_ref']}",
             f"base_tip: {summary['base_tip']}"]
    for ref, b in summary["branches"].items():
        c = b["class_counts"]
        lines.append(
            f"branch {ref} tip={b['tip']} merge_base={b['merge_base']} files={b['files']} "
            f"LAND={c['LAND']} EVIDENCE_ONLY={c['EVIDENCE_ONLY']} DROPPED={c['DROPPED']} "
            f"ALREADY_ON_MAIN={c['ALREADY_ON_MAIN']} conflict_prone={b['conflict_prone_count']}")
    return "\n".join(lines)


def verify_inventory(inventory_path: Path, summary: dict[str, Any]) -> None:
    text = inventory_path.read_text(encoding="utf-8")
    match = FENCE_PATTERN.search(text)
    if not match:
        raise CheckError("STALE_INVENTORY", "inventory has no fenced header block")
    recorded, live = match.group(1).split("\n"), build_header(summary).split("\n")
    if recorded[0] != live[0]:
        raise CheckError("HASH_MISMATCH", "inventory header rules_sha256 does not match the rules file",
                         [{"recorded": recorded[0], "live": live[0]}])
    if recorded != live:
        diff = [{"recorded": r, "live": l} for r, l in zip(recorded + [""] * len(live), live + [""] * len(recorded))
                if r != l]
        raise CheckError("STALE_INVENTORY", "inventory header differs from the live run (tips, merge-bases or totals)",
                         diff)


def check(rules_path: Path, inventory_path: Path | None) -> dict[str, Any]:
    doc, digest = load_rules(rules_path)
    errors = validate_rules(doc)
    if errors:
        raise CheckError("BAD_RULE", "rules file failed static validation", errors, code=2)
    compiled = [(rule, [(g, glob_to_regex(g)) for g in rule["globs"]],
                 [(g, glob_to_regex(g)) for g in rule.get("exclude", [])]) for rule in doc["rules"]]
    base_ref = doc["base_ref"]
    main_sha = resolve(base_ref)
    main_tree = tree_entries(main_sha)
    shas = {ref: resolve(ref) for ref in doc["branches"]}
    merge_bases = {ref: git("merge-base", main_sha, shas[ref]).decode().strip() for ref in doc["branches"]}
    base_trees: dict[str, dict[str, tuple[str, str]]] = {}
    problems: list[dict[str, Any]] = []
    matched_rules: set[str] = set()
    glob_hits: dict[tuple[str, str, str], int] = {}
    by_id = {r["rule_id"]: r for r in doc["rules"]}
    branches_out: dict[str, Any] = {}
    for ref in doc["branches"]:
        mb = merge_bases[ref]
        if mb not in base_trees:
            base_trees[mb] = tree_entries(mb)
        files = branch_universe(mb, shas[ref], main_tree, base_trees[mb])
        if not files:
            problems.append({"type": "EMPTY_BRANCH", "branch": ref, "detail": "branch has no files ahead of main"})
        class_counts = {c: 0 for c in ALLOWED_CLASSES}
        rule_counts: dict[str, int] = {}
        unclassified, multi = [], []
        for f in files:
            hits = []
            for rule, inc, exc in compiled:
                if rule["branch"] not in ("*", ref) or f["main_state"] not in rule["main_state"]:
                    continue
                inc_hit = [g for g, rx in inc if rx.match(f["path"])]
                if not inc_hit:
                    continue
                exc_hit = [g for g, rx in exc if rx.match(f["path"])]
                for g in inc_hit:
                    glob_hits[(rule["rule_id"], "globs", g)] = glob_hits.get((rule["rule_id"], "globs", g), 0) + 1
                for g in exc_hit:
                    glob_hits[(rule["rule_id"], "exclude", g)] = glob_hits.get((rule["rule_id"], "exclude", g), 0) + 1
                if not exc_hit:
                    hits.append(rule["rule_id"])
            if not hits:
                unclassified.append(f"{f['status']} {f['main_state']} {f['path']}")
            elif len(hits) > 1:
                multi.append({"path": f["path"], "rules": hits})
            else:
                matched_rules.add(hits[0])
                class_counts[by_id[hits[0]]["class"]] += 1
                rule_counts[hits[0]] = rule_counts.get(hits[0], 0) + 1
        if unclassified:
            problems.append({"type": "UNCLASSIFIED", "branch": ref, "count": len(unclassified),
                             "items": unclassified[:MAX_LISTED_PATHS]})
        if multi:
            problems.append({"type": "MULTI_MATCH", "branch": ref, "count": len(multi), "items": multi[:MAX_LISTED_PATHS]})
        conflicts = sorted(f["path"] for f in files if f["main_state"] in CONFLICT_STATES)
        state_counts: dict[str, int] = {}
        for f in files:
            state_counts[f["main_state"]] = state_counts.get(f["main_state"], 0) + 1
        branches_out[ref] = {
            "tip": shas[ref], "merge_base": mb, "files": len(files), "class_counts": class_counts,
            "main_state_counts": dict(sorted(state_counts.items())),
            "rule_counts": dict(sorted(rule_counts.items())),
            "conflict_prone_count": len(conflicts),
            "conflict_prone_paths": conflicts[:MAX_LISTED_PATHS],
            "conflict_prone_truncated": len(conflicts) > MAX_LISTED_PATHS,
        }
    unused = [r["rule_id"] for r in doc["rules"] if r["rule_id"] not in matched_rules]
    if unused:
        problems.append({"type": "RULE_MATCHES_NOTHING", "count": len(unused), "items": unused})
    dead = [f"{rid}:{kind}:{g}" for rid, kind, g in
            ((r["rule_id"], k, g) for r in doc["rules"] for k in ("globs", "exclude") for g in r.get(k, []))
            if glob_hits.get((rid, kind, g), 0) == 0]
    if dead:
        problems.append({"type": "DEAD_GLOB", "count": len(dead), "items": dead})
    if problems:
        raise CheckError(problems[0]["type"], f"{len(problems)} problem group(s)", problems)
    summary = {"schema_version": SCHEMA_VERSION, "ok": True, "rules_sha256": digest,
               "base_ref": base_ref, "base_tip": main_sha, "rule_count": len(doc["rules"]),
               "branches": branches_out}
    if inventory_path is not None:
        verify_inventory(inventory_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U3 branch inventory completeness check (read-only).")
    parser.add_argument("--rules", default=DEFAULT_RULES, help="rules file, relative to the repo root")
    parser.add_argument("--inventory", default=None,
                        help="inventory markdown whose first fenced block must equal the live header")
    parser.add_argument("--print-header", action="store_true", help="print the header block text and exit")
    args = parser.parse_args(argv)
    try:
        rules_path = (REPO_ROOT / args.rules).resolve()
        inventory = (REPO_ROOT / args.inventory).resolve() if args.inventory else None
        for p in (rules_path, inventory):
            if p is not None and REPO_ROOT not in p.parents:
                raise CheckError("BAD_PATH", "paths must stay inside the repository", code=2)
        summary = check(rules_path, inventory)
    except CheckError as exc:
        print(json.dumps({"error": exc.kind, "detail": exc.detail, "items": exc.items}, indent=2), file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(json.dumps({"error": "IO_ERROR", "detail": str(exc), "items": []}), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - typed last resort so no traceback escapes
        print(json.dumps({"error": "INTERNAL", "detail": f"{type(exc).__name__}: {exc}", "items": []}), file=sys.stderr)
        return 3
    if args.print_header:
        print(build_header(summary))
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
