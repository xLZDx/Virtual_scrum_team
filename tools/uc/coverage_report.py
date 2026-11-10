"""Truthful coverage report (sprint U2, task U2-5).

Turns a validated ``uc.role-result.v1`` plus the role table into a ``uc.coverage-report.v1`` document
that says, per role, what the code covered and what remains for a model, and renders it as text or
markdown. Deterministic, stdlib only, no model, no network, no file writes.

Honesty rule: a pass-like word may appear in a rendering only when every role in the report is fully
clean (status CLEAN, class LOCAL, empty model residual, empty uncovered). A rendering is scanned for pass
tokens before it is returned; the only exemption is the exact verdict word CLEAN_LOCAL of a fully clean
role, in the verdict cell of that role's own row.

Usage:
    python -m tools.uc.coverage_report --result result.json --table role_table.json [--format text|markdown|json]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

try:
    from tools.uc import contracts
except ImportError:  # run as a script from tools/uc: mirror the router's import style
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from uc import contracts  # type: ignore[no-redef]

REPORT_SCHEMA = "uc.coverage-report.v1"

# Closed vocabulary. CLEAN_LOCAL is the only word that may be read as a pass, and only for a fully clean role.
VERDICT_WORDS = ("CLEAN_LOCAL", "FINDINGS", "PARTIAL_CODE_ONLY", "MODEL_RESIDUAL_OPEN", "BLOCKED", "NOT_COVERED")
CLEAN_VERDICT = "CLEAN_LOCAL"

_TABLE_CLASSES = ("LOCAL", "LOCAL_PLUS_MODEL", "MODEL_ONLY", "OUT_OF_SCOPE")
_REPORT_KEYS = {"schema_version", "request_id", "base_revision", "snapshot_hash", "role_table_sha256", "roles"}
_ROLE_KEYS = {
    "role", "canonical_role", "class", "status", "covered_by_code", "uncovered", "model_residual",
    "findings_count", "highest_severity", "verdict_word",
}

# Case-insensitive pass-like words (regex sources, matched as whole words; see scan_pass_tokens).
# Includes a few inflections of the Russian words (e/yo spelling, gender and number endings).
PASS_TOKENS = (
    r"PASS", r"PASSED", r"OK", r"SUCCESS", r"GREEN", r"APPROVED", r"ALL\s+CLEAR", r"CLEAN", r"COMPLETE",
    r"DONE", r"LGTM", r"SAFE", r"VERIFIED",
    r"пройден", r"пройдено", r"пройдена", r"пройдены", r"успешно", r"зелёный", r"зеленый", r"одобрено", r"чисто",
)

# Whole word: not preceded and not followed by a Unicode letter or digit. The underscore, the hyphen and
# every other non-alphanumeric character count as separators, so CLEAN inside CLEAN_LOCAL or clean-code is a
# hit (the lookarounds use [^\W_], which is "letter or digit" and works for Cyrillic in a str pattern).
_PASS_RE = re.compile(
    r"(?<![^\W_])(?:" + "|".join(sorted(PASS_TOKENS, key=len, reverse=True)) + r")(?![^\W_])",
    re.IGNORECASE,
)


class CoverageReportError(ValueError):
    """Typed failure; ``code`` is stable, ``where`` names the field or location."""

    def __init__(self, code: str, where: str = "", cause: str = "") -> None:
        super().__init__(f"{code} at {where}" if where else code)
        self.code = code
        self.where = where
        self.cause = cause


def _verdict_word(status: str, findings_count: int, residual: list, uncovered: list) -> str:
    if status == "BLOCKED":
        return "BLOCKED"
    if status in ("NOT_COVERED", "NOT_RUN"):
        return "NOT_COVERED"
    if status == "FINDINGS" or findings_count > 0:
        return "FINDINGS"
    if status == "CLEAN" and not residual and not uncovered:
        return CLEAN_VERDICT
    if residual:
        return "MODEL_RESIDUAL_OPEN"
    return "PARTIAL_CODE_ONLY"


def is_fully_clean(entry: dict) -> bool:
    """The single definition of a role that may carry a pass-like word."""
    return (
        entry["status"] == "CLEAN" and entry["class"] == "LOCAL"
        and not entry["model_residual"] and not entry["uncovered"]
        and entry["verdict_word"] == CLEAN_VERDICT
    )


def _lookup(table: object, role: str, canonical: str, role_class: str, where: str) -> None:
    if not isinstance(table, dict) or not isinstance(table.get("entries"), list):
        raise CoverageReportError("BAD_ROLE_TABLE", "table.entries")
    same_name = [e for e in table["entries"] if isinstance(e, dict) and e.get("name") == role]
    if not same_name:
        raise CoverageReportError("UNKNOWN_ROLE", where)
    if role_class not in _TABLE_CLASSES:
        raise CoverageReportError("UNKNOWN_CLASS", where)
    if not any(e.get("class") == role_class and e.get("canonical_role") == canonical for e in same_name):
        raise CoverageReportError("TABLE_MISMATCH", where)


def render_coverage_report(role_result: dict, role_table: dict) -> dict:
    """Build the report; re-validates the result and checks every role against the table."""
    try:
        result = contracts.validate_result(role_result)
    except contracts.ContractError as exc:
        raise CoverageReportError("INVALID_RESULT", exc.where, exc.code) from exc
    severity_rank = {name: index for index, name in enumerate(contracts.SEVERITIES)}
    roles = []
    for index, entry in enumerate(result["roles"]):
        where = f"result.roles[{index}]"
        _lookup(role_table, entry["role"], entry["canonical_role"], entry["class"], where)
        findings = entry["findings"]
        highest = None
        if findings:
            highest = max((f["severity"] for f in findings), key=severity_rank.__getitem__)
        covered = [e["id"] for e in entry["executors"] if e["status"] == "COMPLETE"]
        residual = list(entry["model_residual"])
        uncovered = list(entry["uncovered"])
        roles.append({
            "role": entry["role"],
            "canonical_role": entry["canonical_role"],
            "class": entry["class"],
            "status": entry["status"],
            "covered_by_code": covered,
            "uncovered": uncovered,
            "model_residual": residual,
            "findings_count": len(findings),
            "highest_severity": highest,
            "verdict_word": _verdict_word(entry["status"], len(findings), residual, uncovered),
        })
    return {
        "schema_version": REPORT_SCHEMA,
        "request_id": result["request_id"],
        "base_revision": result["base_revision"],
        "snapshot_hash": result["snapshot_hash"],
        "role_table_sha256": result["role_table_sha256"],
        "roles": roles,
    }


def _check_report(report: object) -> dict:
    """Strict shape check of a report dict; the verdict word is recomputed, never trusted."""
    if not isinstance(report, dict) or set(report) != _REPORT_KEYS:
        raise CoverageReportError("BAD_REPORT", "report")
    if report["schema_version"] != REPORT_SCHEMA:
        raise CoverageReportError("WRONG_SCHEMA", "report.schema_version")
    roles = report["roles"]
    if not isinstance(roles, list) or not roles:
        raise CoverageReportError("BAD_REPORT", "report.roles")
    for index, entry in enumerate(roles):
        where = f"report.roles[{index}]"
        if not isinstance(entry, dict) or set(entry) != _ROLE_KEYS:
            raise CoverageReportError("BAD_REPORT", where)
        if entry["status"] not in contracts.ROLE_STATUSES or entry["class"] not in _TABLE_CLASSES:
            raise CoverageReportError("BAD_REPORT", where)
        for field in ("covered_by_code", "uncovered", "model_residual"):
            if not isinstance(entry[field], list) or not all(isinstance(x, str) for x in entry[field]):
                raise CoverageReportError("BAD_REPORT", f"{where}.{field}")
        count = entry["findings_count"]
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise CoverageReportError("BAD_REPORT", f"{where}.findings_count")
        if entry["highest_severity"] is not None and entry["highest_severity"] not in contracts.SEVERITIES:
            raise CoverageReportError("BAD_REPORT", f"{where}.highest_severity")
        for field in ("role", "canonical_role"):
            if not isinstance(entry[field], str):
                raise CoverageReportError("BAD_REPORT", f"{where}.{field}")
        expected = _verdict_word(entry["status"], count, entry["model_residual"], entry["uncovered"])
        if entry["verdict_word"] not in VERDICT_WORDS or entry["verdict_word"] != expected:
            raise CoverageReportError("BAD_VERDICT_WORD", f"{where}.verdict_word")
    return report


def scan_pass_tokens(text: str) -> list[tuple[str, int]]:
    """Return (matched text, offset) for every whole-word pass token; see the module comment for the boundary."""
    return [(m.group(0), m.start()) for m in _PASS_RE.finditer(text)]


def _exempt_spans(rendering: str, report: dict) -> set[int]:
    """Offsets of CLEAN_LOCAL that are the verdict cell (second cell) of a fully clean role's own row."""
    clean_roles = {e["role"] for e in report["roles"] if is_fully_clean(e)}
    exempt: set[int] = set()
    position = 0
    for line in rendering.splitlines(keepends=True):
        cells = list(re.finditer(r"[^\s|]+", line))
        if len(cells) >= 2 and cells[0].group(0) in clean_roles and cells[1].group(0) == CLEAN_VERDICT:
            exempt.add(position + cells[1].start())
        position += len(line)
    return exempt


def assert_no_pass_token(rendering: str, report: dict) -> None:
    """Raise PASS_TOKEN_IN_PARTIAL_REPORT if a pass token appears while any role is not fully clean.

    Rule: when every role is fully clean, nothing is checked. Otherwise every scanner hit is a violation,
    except a CLEAN_LOCAL hit at the verdict cell of the row of a fully clean role. No substring whitelist.
    """
    checked = _check_report(report)
    if all(is_fully_clean(e) for e in checked["roles"]):
        return
    exempt = _exempt_spans(rendering, checked)
    for token, offset in scan_pass_tokens(rendering):
        if offset in exempt and token == "CLEAN":
            continue
        raise CoverageReportError("PASS_TOKEN_IN_PARTIAL_REPORT", f"offset {offset}")


def _cell(items: list) -> str:
    return ",".join(items) if items else "-"


def _rows(report: dict) -> list[list[str]]:
    rows = []
    for e in report["roles"]:
        rows.append([
            e["role"], e["verdict_word"], e["class"], e["canonical_role"], _cell(e["covered_by_code"]),
            _cell(e["uncovered"]), _cell(e["model_residual"]), str(e["findings_count"]),
            e["highest_severity"] or "-",
        ])
    return rows


# The verdict word comes second in every row (the scanner exemption relies on it). The raw status is not
# printed: it is derivable, and the status value CLEAN is itself a pass token.
_HEADERS = ["role", "verdict", "class", "canonical", "covered_by_code", "uncovered", "model_residual",
            "findings", "highest_severity"]


def render_text(report: dict) -> str:
    checked = _check_report(report)
    table = [_HEADERS] + _rows(checked)
    widths = [max(len(row[i]) for row in table) for i in range(len(_HEADERS))]
    lines = [
        f"coverage report {checked['schema_version']}",
        f"request {checked['request_id']} base {checked['base_revision']} snapshot {checked['snapshot_hash']}",
        f"role_table_sha256 {checked['role_table_sha256']}",
    ]
    for row in table:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip())
    text = "\n".join(lines) + "\n"
    assert_no_pass_token(text, checked)
    return text


def render_markdown(report: dict) -> str:
    checked = _check_report(report)
    lines = [
        f"# Coverage report {checked['schema_version']}",
        "",
        f"- request: {checked['request_id']}",
        f"- base revision: {checked['base_revision']}",
        f"- snapshot: {checked['snapshot_hash']}",
        f"- role_table_sha256: {checked['role_table_sha256']}",
        "",
        "| " + " | ".join(_HEADERS) + " |",
        "|" + "|".join("---" for _ in _HEADERS) + "|",
    ]
    for row in _rows(checked):
        lines.append("| " + " | ".join(row) + " |")
    text = "\n".join(lines) + "\n"
    assert_no_pass_token(text, checked)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a truthful coverage report; writes no files.")
    parser.add_argument("--result", required=True, type=pathlib.Path)
    parser.add_argument("--table", required=True, type=pathlib.Path)
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        try:
            result = json.loads(args.result.read_text(encoding="utf-8"))
            table = json.loads(args.table.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CoverageReportError("UNREADABLE_INPUT", type(exc).__name__) from exc
        report = render_coverage_report(result, table)
        if args.format == "json":
            # Machine form: enumerated field values only, not a human rendering; the scanner does not apply.
            output = json.dumps(report, indent=2, sort_keys=True) + "\n"
        elif args.format == "markdown":
            output = render_markdown(report)
        else:
            output = render_text(report)
    except CoverageReportError as exc:
        print(json.dumps({"status": "ERROR", "code": exc.code, "where": exc.where}, sort_keys=True), file=sys.stderr)
        return 3 if exc.code == "UNREADABLE_INPUT" else 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
