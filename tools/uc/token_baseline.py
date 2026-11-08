"""Token baseline capture (sprint U1, task U1-1).

Computes tokens per role from Claude Code session transcripts against a manifest that pins
the exact transcript files by SHA-256. A missing, empty or hash-mismatched baseline yields
NOT_RUN and no numbers: nothing is ever estimated.

Attribution rule (stated in every manifest): usage recorded in a session's main transcript
belongs to role "orchestrator"; usage recorded in a sub-agent transcript
(<session>/subagents/agent-<id>.jsonl) belongs to the role named by agentType in the sibling
agent-<id>.meta.json, or "unknown-subagent" when the meta file is missing or unreadable.
A message that appears on several transcript lines (streaming rewrites) is counted once,
using its last recorded usage.

Token fields are summed separately and never combined into one number:
input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens.

Usage:
    python tools/uc/token_baseline.py build-manifest --project-dir <dir> --sessions <id,id> --out <file>
    python tools/uc/token_baseline.py report --manifest <file> --project-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

MANIFEST_VERSION = 1
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
ORCHESTRATOR_ROLE = "orchestrator"
UNKNOWN_SUBAGENT_ROLE = "unknown-subagent"
ATTRIBUTION_RULE = (
    "main transcript usage -> role orchestrator; sub-agent transcript usage -> agentType from the sibling "
    "meta file, else unknown-subagent; a message id on several lines is counted once with its last usage"
)


class BaselineNotRun(Exception):
    """The baseline cannot be computed; ``reason`` is a stable code, never an estimate."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def session_files(project_dir: pathlib.Path, session_id: str) -> list[pathlib.Path]:
    """Main transcript, then the sub-agent transcripts and their meta files, in stable order."""
    main = project_dir / f"{session_id}.jsonl"
    if not main.is_file():
        raise BaselineNotRun("SESSION_MISSING", session_id)
    files = [main]
    sub_dir = project_dir / session_id / "subagents"
    if sub_dir.is_dir():
        files.extend(sorted(p for p in sub_dir.iterdir() if p.is_file() and p.suffix in (".jsonl", ".json")))
    return files


def build_manifest(project_dir: pathlib.Path, session_ids: list[str]) -> dict:
    if not session_ids:
        raise BaselineNotRun("EMPTY_SESSION_SET")
    sessions = []
    for session_id in session_ids:
        entries = []
        for path in session_files(project_dir, session_id):
            entries.append({
                "path": path.relative_to(project_dir).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            })
        sessions.append({"session_id": session_id, "files": entries})
    return {
        "version": MANIFEST_VERSION,
        "token_fields": list(TOKEN_FIELDS),
        "attribution_rule": ATTRIBUTION_RULE,
        "sessions": sessions,
    }


def verify_manifest(manifest: object, project_dir: pathlib.Path) -> None:
    if not isinstance(manifest, dict) or manifest.get("version") != MANIFEST_VERSION:
        raise BaselineNotRun("MANIFEST_INVALID", "missing or wrong version")
    if manifest.get("token_fields") != list(TOKEN_FIELDS) or manifest.get("attribution_rule") != ATTRIBUTION_RULE:
        raise BaselineNotRun("MANIFEST_RULES_CHANGED", "token fields or attribution rule differ from this script")
    sessions = manifest.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise BaselineNotRun("EMPTY_SESSION_SET")
    for session in sessions:
        files = session.get("files") if isinstance(session, dict) else None
        if not isinstance(files, list) or not files:
            raise BaselineNotRun("MANIFEST_INVALID", "session without files")
        for entry in files:
            path = (project_dir / str(entry.get("path", ""))).resolve()
            try:
                path.relative_to(project_dir.resolve())
            except ValueError as exc:
                raise BaselineNotRun("PATH_OUTSIDE_PROJECT", str(entry.get("path"))) from exc
            if not path.is_file():
                raise BaselineNotRun("FILE_MISSING", str(entry.get("path")))
            if sha256_file(path) != entry.get("sha256"):
                raise BaselineNotRun("HASH_MISMATCH", str(entry.get("path")))


def _last_usage_per_message(path: pathlib.Path) -> dict[str, dict]:
    """message id -> usage of its last occurrence; lines without a message id or usage are skipped."""
    last: dict[str, dict] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            message = record.get("message") if isinstance(record, dict) else None
            if not isinstance(message, dict):
                continue
            usage = message.get("usage")
            message_id = message.get("id")
            if isinstance(usage, dict) and isinstance(message_id, str):
                last[message_id] = usage
    return last


def _role_of_subagent(jsonl_path: pathlib.Path) -> str:
    meta = jsonl_path.with_suffix(".meta.json")
    try:
        value = json.loads(meta.read_text(encoding="utf-8"))
        role = value.get("agentType") if isinstance(value, dict) else None
    except (OSError, ValueError):
        role = None
    return role if isinstance(role, str) and role else UNKNOWN_SUBAGENT_ROLE


def _add(totals: dict[str, dict[str, int]], role: str, usage: dict) -> None:
    bucket = totals.setdefault(role, {field: 0 for field in TOKEN_FIELDS} | {"messages": 0})
    bucket["messages"] += 1
    for field in TOKEN_FIELDS:
        value = usage.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            bucket[field] += value


def compute(manifest: dict, project_dir: pathlib.Path) -> dict:
    verify_manifest(manifest, project_dir)
    totals: dict[str, dict[str, int]] = {}
    for session in manifest["sessions"]:
        for entry in session["files"]:
            path = project_dir / entry["path"]
            if path.suffix != ".jsonl":
                continue
            in_subagents = path.parent.name == "subagents"
            role = _role_of_subagent(path) if in_subagents else ORCHESTRATOR_ROLE
            for usage in _last_usage_per_message(path).values():
                _add(totals, role, usage)
    if not totals:
        raise BaselineNotRun("NO_USAGE_FOUND", "no message with a usage block in the pinned transcripts")
    return {
        "status": "MEASURED",
        "token_fields": list(TOKEN_FIELDS),
        "attribution_rule": ATTRIBUTION_RULE,
        "roles": {role: totals[role] for role in sorted(totals)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build-manifest")
    build.add_argument("--project-dir", required=True, type=pathlib.Path)
    build.add_argument("--sessions", required=True)
    build.add_argument("--out", required=True, type=pathlib.Path)
    report = sub.add_parser("report")
    report.add_argument("--manifest", required=True, type=pathlib.Path)
    report.add_argument("--project-dir", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build-manifest":
            ids = [s.strip() for s in args.sessions.split(",") if s.strip()]
            manifest = build_manifest(args.project_dir, ids)
            args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": "WRITTEN", "sessions": len(ids), "out": str(args.out)}))
            return 0
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BaselineNotRun("MANIFEST_UNREADABLE", str(exc)) from exc
        print(json.dumps(compute(manifest, args.project_dir), indent=2, sort_keys=True))
        return 0
    except BaselineNotRun as exc:
        print(json.dumps({"status": "NOT_RUN", "reason": exc.reason, "detail": exc.detail}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
