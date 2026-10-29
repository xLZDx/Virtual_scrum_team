#!/usr/bin/env python3
"""Map secret-redacted PM review diff lines to exact Git source positions.

This verifier is read-only. It never prints or writes source-line contents or masked
values; its report contains only commit/blob identities, line numbers and SHA-256s.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REDACTED = "[REDACTED]"
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
FILE_RE = re.compile(r"^diff --git a/(.+) b/(.+)$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class VerificationError(Exception):
    """A source identity or structure check failed without exposing source text."""


@dataclass(frozen=True)
class DiffLine:
    file_path: str
    kind: str
    old_line: int | None
    new_line: int | None
    hunk: str
    attachment_line: int


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise VerificationError(f"git operation failed (exit {result.returncode}); details withheld")
    return result.stdout


def resolve_full_commit(repo: Path, supplied: str, label: str) -> str:
    if not FULL_SHA_RE.fullmatch(supplied):
        raise VerificationError(f"{label} must be a full lowercase 40-character Git commit ID")
    resolved = git(repo, "rev-parse", "--verify", f"{supplied}^{{commit}}").decode("ascii").strip()
    if resolved != supplied:
        raise VerificationError(f"{label} does not resolve to the supplied exact commit")
    return resolved


def source_blob(repo: Path, revision: str, file_path: str) -> tuple[str, list[bytes]]:
    if file_path.startswith("/") or "\\" in file_path or any(part in {"", ".", ".."} for part in file_path.split("/")):
        raise VerificationError("diff contains a non-canonical repository path")
    blob = git(repo, "rev-parse", "--verify", f"{revision}:{file_path}").decode("ascii").strip()
    content = git(repo, "show", f"{revision}:{file_path}")
    # Split only on LF so CRLF remains part of the exact blob line identity.
    return blob, content.split(b"\n")[:-1] if content.endswith(b"\n") else content.split(b"\n")


def normalize_redaction(line: str) -> str:
    """Replace only the known marker with a non-newline wildcard."""
    return "^" + re.escape(line).replace(re.escape(REDACTED), ".*") + "$"


def parse_diff_positions(lines: Sequence[str], diff_start: int, diff_end: int) -> list[DiffLine]:
    entries: list[DiffLine] = []
    file_path: str | None = None
    old_cursor: int | None = None
    new_cursor: int | None = None
    current_hunk = ""

    for offset in range(diff_start, diff_end):
        line = lines[offset]
        file_match = FILE_RE.match(line.rstrip("\r"))
        if file_match:
            if file_match.group(1) != file_match.group(2):
                raise VerificationError("renamed file paths are not accepted by this verifier")
            file_path = file_match.group(2)
            old_cursor = new_cursor = None
            current_hunk = ""
            continue

        hunk_match = HUNK_RE.match(line.rstrip("\r"))
        if hunk_match:
            old_cursor = int(hunk_match.group(1))
            new_cursor = int(hunk_match.group(3))
            current_hunk = line.rstrip("\r").split(" @@", 2)[0]
            continue

        if file_path is None or old_cursor is None or new_cursor is None:
            continue
        if line.startswith("\\"):
            continue
        if not line or line[0] not in {" ", "+", "-"}:
            raise VerificationError(
                f"unexpected unified-diff structure at attachment line {offset + 1} in {file_path}"
            )

        kind = line[0]
        old_line = old_cursor if kind in {" ", "-"} else None
        new_line = new_cursor if kind in {" ", "+"} else None
        if REDACTED in line:
            if line.count(REDACTED) != 1:
                raise VerificationError("multiple redaction markers on one diff line are unsupported")
            entries.append(DiffLine(file_path, kind, old_line, new_line, current_hunk, offset + 1))
        if kind in {" ", "-"}:
            old_cursor += 1
        if kind in {" ", "+"}:
            new_cursor += 1

    return entries


def verify_source_line(
    repo: Path, revision: str, file_path: str, line_number: int | None
) -> tuple[str, bytes]:
    if line_number is None or line_number < 1:
        raise VerificationError("redacted line has no valid source-side line number")
    blob, lines = source_blob(repo, revision, file_path)
    if line_number > len(lines):
        raise VerificationError("redacted line position is outside its exact Git blob")
    raw_line = lines[line_number - 1]
    if REDACTED.encode("ascii") in raw_line:
        raise VerificationError("exact source blob contains the redaction marker at a mapped line")
    return blob, raw_line


def build_report(args: argparse.Namespace) -> dict[str, object]:
    repo = args.repo.resolve(strict=True)
    base = resolve_full_commit(repo, args.base, "base")
    head = resolve_full_commit(repo, args.head, "head")
    ancestor = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", base, head],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if ancestor.returncode != 0:
        raise VerificationError("base is not an ancestor of head")

    supplied_attachment = args.attachment.absolute()
    attachment_stat = supplied_attachment.lstat()
    if not supplied_attachment.is_file() or supplied_attachment.is_symlink() or attachment_stat.st_nlink != 1:
        raise VerificationError("attachment must be a regular single-link file")
    attachment_path = supplied_attachment.resolve(strict=True)
    attachment_bytes = attachment_path.read_bytes()
    attachment_hash = hashlib.sha256(attachment_bytes).hexdigest()
    if len(attachment_bytes) != args.attachment_size:
        raise VerificationError("attachment byte length does not match the expected length")
    if attachment_hash != args.attachment_sha256:
        raise VerificationError("attachment SHA-256 does not match the expected digest")
    try:
        attachment_text = attachment_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise VerificationError("attachment is not strict UTF-8") from exc

    attachment_lines = attachment_text.split("\n")
    diff_start = next(
        (i for i, line in enumerate(attachment_lines) if FILE_RE.match(line.rstrip("\r"))),
        None,
    )
    if diff_start is None:
        raise VerificationError("attachment has no unified Git diff")
    raw_diff_bytes = git(
        repo,
        "diff",
        "--no-color",
        "--no-ext-diff",
        "--unified=3",
        f"{base}...{head}",
        "--",
        ".",
        ":(exclude)reports",
    )
    try:
        raw_diff = raw_diff_bytes.decode("utf-8", errors="strict").split("\n")
    except UnicodeDecodeError as exc:
        raise VerificationError("raw Git diff is not strict UTF-8") from exc

    if raw_diff and raw_diff[-1] == "":
        raw_diff.pop()

    diff_end = diff_start + len(raw_diff)
    if diff_end > len(attachment_lines):
        raise VerificationError("attachment ends before the exact raw Git diff")
    attached_diff = attachment_lines[diff_start:diff_end]
    tail = attachment_lines[diff_end:]
    if tail and tail[0] == "":
        tail = tail[1:]
    if not tail or tail[0].rstrip("\r") != chr(96) * 3:
        raise VerificationError("exact raw diff is not followed by its closing attachment fence")

    masked_lines = 0
    for index, (attached, source) in enumerate(zip(attached_diff, raw_diff), start=1):
        if attached == source:
            continue
        if REDACTED not in attached or not re.fullmatch(normalize_redaction(attached), source):
            raise VerificationError(f"diff structure/source mismatch at diff line {index}; values withheld")
        masked_lines += 1

    positions = parse_diff_positions(attachment_lines, diff_start, diff_end)
    if masked_lines != sum(line.count(REDACTED) for line in attached_diff):
        raise VerificationError("redaction marker accounting mismatch")
    if len(positions) != masked_lines:
        raise VerificationError("redacted line position accounting mismatch")

    records: list[dict[str, object]] = []
    for entry in positions:
        record: dict[str, object] = {
            "file": entry.file_path,
            "diff_side": {"+": "added", "-": "removed", " ": "context"}[entry.kind],
            "diff_hunk": entry.hunk,
            "attachment_line": entry.attachment_line,
            "source_identity": "PASS",
            "security_invariant": "INCONCLUSIVE_PENDING_INDEPENDENT_REVIEW",
            "behavioral_test": "NOT_RUN",
        }
        if entry.kind == "+":
            blob, _ = verify_source_line(repo, head, entry.file_path, entry.new_line)
            record.update({"head_blob": blob, "head_line": entry.new_line})
        elif entry.kind == "-":
            blob, _ = verify_source_line(repo, base, entry.file_path, entry.old_line)
            record.update({"base_blob": blob, "base_line": entry.old_line})
        else:
            base_blob, base_line = verify_source_line(repo, base, entry.file_path, entry.old_line)
            head_blob, head_line = verify_source_line(repo, head, entry.file_path, entry.new_line)
            if base_line != head_line:
                raise VerificationError("redacted context line differs across base and head")
            record.update({
                "base_blob": base_blob,
                "base_line": entry.old_line,
                "head_blob": head_blob,
                "head_line": entry.new_line,
            })
        records.append(record)

    by_file = {str(record["file"]) for record in records}
    return {
        "schema": "S2_REVIEW_REDACTION_SOURCE_FIDELITY_V1",
        "repository": str(repo),
        "base": base,
        "head": head,
        "attachment": {
            "path": str(attachment_path),
            "size_bytes": len(attachment_bytes),
            "sha256": attachment_hash,
        },
        "raw_git_diff_sha256": hashlib.sha256(raw_diff_bytes).hexdigest(),
        "redaction_markers": masked_lines,
        "redacted_source_files": len(by_file),
        "line_identity_pass_count": len(records),
        "line_identity_fail_count": 0,
        "security_invariants": "INCONCLUSIVE_PENDING_INDEPENDENT_REVIEW",
        "behavioral_tests": "NOT_RUN; assign only if independent review cannot establish behavior statically",
        "source_lines_or_masked_values_emitted": False,
        "records": records,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--attachment", type=Path, required=True)
    parser.add_argument("--attachment-size", type=int, required=True)
    parser.add_argument("--attachment-sha256", required=True)
    parser.add_argument("--expect-markers", type=int, default=41)
    parser.add_argument("--expect-files", type=int, default=15)
    parser.add_argument("--output", type=Path, help="Write sanitized JSON report; default is stdout")
    args = parser.parse_args(argv)
    if args.attachment_size <= 0 or not re.fullmatch(r"[0-9a-f]{64}", args.attachment_sha256):
        parser.error("attachment size and SHA-256 must be positive/canonical")
    if args.expect_markers < 0 or args.expect_files < 0:
        parser.error("expected counts must be non-negative")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(args)
        if report["line_identity_fail_count"] != 0 or report["line_identity_pass_count"] != report["redaction_markers"]:
            raise VerificationError("not every redacted line was mapped to exact source")
        if report["redaction_markers"] != args.expect_markers or report["redacted_source_files"] != args.expect_files:
            raise VerificationError("the expected review packet redaction inventory changed")
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            output_path = args.output.resolve()
            if not output_path.parent.is_dir():
                raise VerificationError("report output directory must already exist")
            with output_path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(rendered)
        return 0
    except (OSError, VerificationError, subprocess.SubprocessError) as exc:
        print(f"SOURCE_FIDELITY_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
