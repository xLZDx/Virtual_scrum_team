"""Deterministic completeness check for the U3 branch inventory.

Read-only: it runs a fixed set of git plumbing commands (no shell, no network,
no checkout, no fetch), computes the file universe of each pushed branch as
``git diff --name-status --no-renames origin/main...<branch>`` and verifies that
every file is matched by exactly one classification rule.

Exit codes: 0 = complete, 1 = inventory check failed, 2 = usage or rules-file error.
A failure prints one typed JSON object on stderr; success prints a JSON summary
on stdout. This is an inventory check, not a test suite.
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
ALLOWED_MAIN_STATES = ("identical", "differs", "absent")
ALLOWED_LANDS_IN = ("U3-3", "U3-4", "U3-5", "U3-6")
RULE_KEYS = {"rule_id", "branch", "globs", "exclude", "main_state", "class", "reason",
             "lands_in", "reference_for", "flags"}
REQUIRED_RULE_KEYS = {"rule_id", "branch", "globs", "main_state", "class", "reason", "lands_in"}
REF_PATTERN = re.compile(r"origin/[A-Za-z0-9][A-Za-z0-9._/-]{0,127}\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
HEADER_PATTERN = re.compile(r"^rules_sha256:\s*`?([0-9a-f]{64})`?\s*$", re.MULTILINE)
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
    """Run one read-only git command with a fixed argv, bounded output and no shell."""
    argv = ["git", "-C", str(REPO_ROOT), *args]
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    except OSError as exc:
        raise CheckError("GIT_FAILURE", f"cannot start git: {exc}", code=2) from exc
    try:
        out = proc.stdout.read(MAX_GIT_OUTPUT_BYTES + 1)
        if len(out) > MAX_GIT_OUTPUT_BYTES:
            proc.kill()
            raise CheckError("GIT_FAILURE", "git output exceeds the byte bound", code=2)
        proc.wait(timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        raise CheckError("GIT_FAILURE", "git timed out", code=2) from exc
    if proc.returncode != 0:
        err = proc.stderr.read(2000).decode("utf-8", "replace")
        raise CheckError("GIT_FAILURE", f"git {args[0]} failed: {err.strip()}", code=2)
    return out


def require_ref(ref: str) -> str:
    if not isinstance(ref, str) or not REF_PATTERN.match(ref) or ".." in ref or ref.endswith(".lock"):
        raise CheckError("BAD_REF", f"ref must be a plain origin/ ref: {ref!r}", code=2)
    return ref


def rev_parse(ref: str) -> str:
    sha = git("rev-parse", "--verify", "--quiet", ref + "^{commit}").decode().strip()
    if not SHA_PATTERN.match(sha):
        raise CheckError("BAD_REF", f"ref does not resolve to a commit: {ref}", code=2)
    return sha


def tree_blobs(rev: str) -> dict[str, str]:
    blobs: dict[str, str] = {}
    for entry in git("ls-tree", "-r", "-z", rev).decode("utf-8", "surrogateescape").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            blobs[path] = meta.split()[2]
    return blobs


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
    if not isinstance(doc["branches"], list) or not doc["branches"] or len(set(doc["branches"])) != len(doc["branches"]):
        raise CheckError("BAD_RULES", "branches must be a non-empty list of unique refs", code=2)
    for ref in doc["branches"]:
        require_ref(ref)
    if not isinstance(doc["rules"], list) or not doc["rules"] or len(doc["rules"]) > MAX_RULES:
        raise CheckError("BAD_RULES", "rules must be a non-empty bounded list", code=2)
    return doc, digest


def validate_rules(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Static rule validation; returns error records (empty when the rules are well-formed)."""
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, rule in enumerate(doc["rules"]):
        rid = rule.get("rule_id") if isinstance(rule, dict) else None
        label = rid if isinstance(rid, str) and rid else f"#{idx}"
        if not isinstance(rule, dict):
            errors.append({"type": "BAD_RULE", "rule": label, "detail": "rule is not an object"})
            continue
        keys = set(rule)
        if not REQUIRED_RULE_KEYS <= keys or not keys <= RULE_KEYS:
            errors.append({"type": "BAD_RULE", "rule": label, "detail": f"keys {sorted(keys)} not allowed"})
            continue
        if not isinstance(rid, str) or not rid or rid in seen:
            errors.append({"type": "BAD_RULE", "rule": label, "detail": "rule_id must be unique and non-empty"})
        seen.add(str(rid))
        if rule["class"] not in ALLOWED_CLASSES:
            errors.append({"type": "BAD_CLASS", "rule": label, "detail": repr(rule["class"])})
        if not isinstance(rule["reason"], str) or not rule["reason"].strip():
            errors.append({"type": "EMPTY_REASON", "rule": label})
        branch = rule["branch"]
        if branch != "*" and branch not in doc["branches"]:
            errors.append({"type": "BAD_RULE", "rule": label, "detail": f"unknown branch {branch!r}"})
        for key in ("globs", "exclude"):
            value = rule.get(key, [])
            if not isinstance(value, list) or (key == "globs" and not value) or not all(
                    isinstance(g, str) and g for g in value):
                errors.append({"type": "BAD_RULE", "rule": label, "detail": f"{key} must be a list of non-empty strings"})
        states = rule["main_state"]
        if (not isinstance(states, list) or not states or len(set(states)) != len(states)
                or not set(states) <= set(ALLOWED_MAIN_STATES)):
            errors.append({"type": "BAD_RULE", "rule": label, "detail": "main_state must list identical/differs/absent"})
        elif (rule["class"] == "ALREADY_ON_MAIN") != (states == ["identical"]):
            errors.append({"type": "BAD_RULE", "rule": label,
                           "detail": "ALREADY_ON_MAIN is allowed only for, and requires, main_state [identical]"})
        if rule["class"] == "LAND":
            if rule["lands_in"] not in ALLOWED_LANDS_IN:
                errors.append({"type": "BAD_RULE", "rule": label, "detail": f"LAND needs lands_in in {ALLOWED_LANDS_IN}"})
        elif rule["lands_in"] is not None:
            errors.append({"type": "BAD_RULE", "rule": label, "detail": "lands_in must be null unless class is LAND"})
    return errors


def branch_universe(base_ref: str, ref: str, main_blobs: dict[str, str], base_blobs: dict[str, str]) -> list[dict[str, Any]]:
    branch_blobs = tree_blobs(ref)
    parts = git("diff", "--name-status", "--no-renames", "-z", f"{base_ref}...{ref}").decode(
        "utf-8", "surrogateescape").split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) % 2:
        raise CheckError("GIT_FAILURE", "unexpected name-status output", code=2)
    files = []
    for i in range(0, len(parts), 2):
        status, path = parts[i], parts[i + 1]
        blob = branch_blobs.get(path)
        if blob is None:
            state = "deleted_in_branch"
        elif path not in main_blobs:
            state = "absent"
        else:
            state = "identical" if main_blobs[path] == blob else "differs"
        conflict = (state == "differs" and main_blobs[path] != base_blobs.get(path))
        files.append({"path": path, "status": status, "main_state": state, "conflict_prone": conflict})
    return files


def check(rules_path: Path, inventory_path: Path | None) -> dict[str, Any]:
    doc, digest = load_rules(rules_path)
    errors = validate_rules(doc)
    if errors:
        raise CheckError("BAD_RULE", "rules file failed static validation", errors, code=2)
    if inventory_path is not None:
        match = HEADER_PATTERN.search(inventory_path.read_text(encoding="utf-8"))
        if not match or match.group(1) != digest:
            raise CheckError("HASH_MISMATCH", "inventory header rules_sha256 does not match the rules file",
                             [{"rules_file_sha256": digest, "inventory_header": match.group(1) if match else None}])
    compiled = []
    for rule in doc["rules"]:
        compiled.append((rule, [glob_to_regex(g) for g in rule["globs"]],
                         [glob_to_regex(g) for g in rule.get("exclude", [])]))
    base_ref = doc["base_ref"]
    main_sha = rev_parse(base_ref)
    main_blobs = tree_blobs(main_sha)
    problems: list[dict[str, Any]] = []
    matched_rules: set[str] = set()
    branches_out: dict[str, Any] = {}
    merge_bases: dict[str, str] = {}
    for ref in doc["branches"]:
        tip = rev_parse(ref)
        merge_base = git("merge-base", base_ref, ref).decode().strip()
        merge_bases[ref] = merge_base
    base_blobs_cache: dict[str, dict[str, str]] = {}
    for ref in doc["branches"]:
        tip = rev_parse(ref)
        mb = merge_bases[ref]
        if mb not in base_blobs_cache:
            base_blobs_cache[mb] = tree_blobs(mb)
        files = branch_universe(base_ref, ref, main_blobs, base_blobs_cache[mb])
        class_counts = {c: 0 for c in ALLOWED_CLASSES}
        rule_counts: dict[str, int] = {}
        unclassified, multi = [], []
        for f in files:
            hits = []
            for rule, inc, exc in compiled:
                if rule["branch"] not in ("*", ref):
                    continue
                if f["main_state"] not in rule["main_state"]:
                    continue
                if any(p.match(f["path"]) for p in inc) and not any(p.match(f["path"]) for p in exc):
                    hits.append(rule["rule_id"])
            if not hits:
                unclassified.append(f"{f['status']} {f['main_state']} {f['path']}")
            elif len(hits) > 1:
                multi.append({"path": f["path"], "rules": hits})
            else:
                rule = next(r for r, _, _ in compiled if r["rule_id"] == hits[0])
                matched_rules.add(hits[0])
                class_counts[rule["class"]] += 1
                rule_counts[hits[0]] = rule_counts.get(hits[0], 0) + 1
        if unclassified:
            problems.append({"type": "UNCLASSIFIED", "branch": ref, "count": len(unclassified),
                             "items": unclassified[:MAX_LISTED_PATHS]})
        if multi:
            problems.append({"type": "MULTI_MATCH", "branch": ref, "count": len(multi), "items": multi[:MAX_LISTED_PATHS]})
        conflicts = sorted(f["path"] for f in files if f["conflict_prone"])
        state_counts: dict[str, int] = {}
        for f in files:
            state_counts[f["main_state"]] = state_counts.get(f["main_state"], 0) + 1
        branches_out[ref] = {
            "tip": tip, "merge_base": mb, "files": len(files), "class_counts": class_counts,
            "main_state_counts": dict(sorted(state_counts.items())),
            "rule_counts": dict(sorted(rule_counts.items())),
            "conflict_prone_count": len(conflicts),
            "conflict_prone_paths": conflicts[:MAX_LISTED_PATHS],
            "conflict_prone_truncated": len(conflicts) > MAX_LISTED_PATHS,
        }
    unused = [r["rule_id"] for r in doc["rules"] if r["rule_id"] not in matched_rules]
    if unused:
        problems.append({"type": "RULE_MATCHES_NOTHING", "count": len(unused), "items": unused})
    if problems:
        raise CheckError(problems[0]["type"], f"{len(problems)} problem group(s)", problems)
    return {"schema_version": SCHEMA_VERSION, "ok": True, "rules_sha256": digest,
            "base_ref": base_ref, "base_tip": main_sha, "rule_count": len(doc["rules"]),
            "branches": branches_out}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="U3 branch inventory completeness check (read-only).")
    parser.add_argument("--rules", default=DEFAULT_RULES, help="rules file, relative to the repo root")
    parser.add_argument("--inventory", default=None, help="inventory markdown whose rules_sha256 header is verified")
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
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
