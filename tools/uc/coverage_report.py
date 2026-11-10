"""Truthful coverage report (sprint U2, task U2-5).

Turns a validated ``uc.role-result.v1`` plus the role table into a ``uc.coverage-report.v1`` document
that says, per role, what the code covered and what remains for a model, and renders it as text or
markdown. Deterministic, stdlib only, no model, no network, no file writes.

Honesty rule: a pass-like word may appear in a rendering only when every role in the report is fully
clean (status CLEAN, class LOCAL, empty model residual, empty uncovered). A rendering is scanned for pass
tokens before it is returned; the only exemption is the exact verdict word CLEAN_LOCAL of a fully clean
role, at the verdict cell position of that role's own body row, recorded while the rendering is built.

Usage:
    python -m tools.uc.coverage_report --result result.json --table role_table.json [--format text|markdown|json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import unicodedata

try:
    from tools.uc import contracts
except ModuleNotFoundError as _exc:  # run as a script from tools/uc: mirror the router's import style
    if _exc.name not in ("tools", "tools.uc"):
        raise
    sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
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
# Labels used in the renderings; a role with one of these names is refused (fail closed).
_RESERVED_ROLE_NAMES = frozenset({"request", "role", "coverage", "base", "snapshot", "role_table_sha256"})

# Case-insensitive pass-like words (regex sources, matched as whole words; see scan_pass_tokens).
PASS_TOKENS = (
    r"PASS", r"PASSES", r"PASSED", r"PASSING", r"OK", r"OKAY", r"SUCCESS", r"SUCCESSFUL", r"SUCCEEDED",
    r"GREEN", r"APPROVE", r"APPROVED", r"ALL\s+CLEAR", r"CLEAN", r"COMPLETE", r"COMPLETED", r"DONE", r"LGTM",
    r"SAFE", r"VERIFIED", r"FIXED", r"READY", r"GOOD", r"FINE",
    r"пройден", r"пройдено", r"пройдена", r"пройдены", r"успешно", r"успешный", r"зелёный", r"зеленый",
    r"одобрено", r"одобрен", r"чисто", r"чистый", r"ок", r"окей", r"готово", r"завершено", r"выполнено",
    r"проверено", r"безопасно",
)

# Whole word: not adjacent to a Unicode LETTER. Digits, underscore, hyphen and every other character are
# separators, so CLEAN inside CLEAN_LOCAL, clean-code, OK1 and pass2 are hits ([^\W\d_] is "a letter", and
# works for Cyrillic in a str pattern).
_PASS_RE = re.compile(
    r"(?<![^\W\d_])(?:" + "|".join(sorted(PASS_TOKENS, key=len, reverse=True)) + r")(?![^\W\d_])",
    re.IGNORECASE,
)


class CoverageReportError(ValueError):
    """Typed failure; ``code`` is stable, ``where`` names the field or location."""

    def __init__(self, code: str, where: str = "", cause: str = "") -> None:
        super().__init__(f"{code} at {where}" if where else code)
        self.code = code
        self.where = where
        self.cause = cause


def _verdict_word(status: str, role_class: str, findings_count: int, residual: list, uncovered: list) -> str:
    if status == "CLEAN" and role_class != "LOCAL":
        raise CoverageReportError("BAD_REPORT", "status CLEAN needs class LOCAL")
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


def render_coverage_report(role_result: dict, role_table: dict, table_sha256: str | None = None) -> dict:
    """Build the report; re-validates the result and checks every role against the table.

    When ``table_sha256`` (sha256 of the exact table bytes) is given it must equal ``role_table_sha256`` of the
    result, otherwise TABLE_DIGEST_MISMATCH.
    """
    try:
        result = contracts.validate_result(role_result)
    except contracts.ContractError as exc:
        raise CoverageReportError("INVALID_RESULT", exc.where, exc.code) from exc
    if table_sha256 is not None and (not isinstance(table_sha256, str) or table_sha256 != result["role_table_sha256"]):
        raise CoverageReportError("TABLE_DIGEST_MISMATCH", "result.role_table_sha256")
    severity_rank = {name: index for index, name in enumerate(contracts.SEVERITIES)}
    roles = []
    for index, entry in enumerate(result["roles"]):
        where = f"result.roles[{index}]"
        _lookup(role_table, entry["role"], entry["canonical_role"], entry["class"], where)
        findings = entry["findings"]
        highest = None
        if findings:
            highest = max((f["severity"] for f in findings), key=severity_rank.__getitem__)
        residual = list(entry["model_residual"])
        uncovered = list(entry["uncovered"])
        roles.append({
            "role": entry["role"],
            "canonical_role": entry["canonical_role"],
            "class": entry["class"],
            "status": entry["status"],
            "covered_by_code": [e["id"] for e in entry["executors"] if e["status"] == "COMPLETE"],
            "uncovered": uncovered,
            "model_residual": residual,
            "findings_count": len(findings),
            "highest_severity": highest,
            "verdict_word": _verdict_word(entry["status"], entry["class"], len(findings), residual, uncovered),
        })
    report = {
        "schema_version": REPORT_SCHEMA,
        "request_id": result["request_id"],
        "base_revision": result["base_revision"],
        "snapshot_hash": result["snapshot_hash"],
        "role_table_sha256": result["role_table_sha256"],
        "roles": roles,
    }
    return _check_report(report)


def _ident(value: object, pattern, where: str) -> str:
    """A report string: str, pure printable ASCII, no pipe, and a full match of the contract pattern."""
    if (not isinstance(value, str) or not value.isascii() or "|" in value
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value) or not pattern.fullmatch(value)):
        raise CoverageReportError("BAD_REPORT", where)
    if value.casefold() == CLEAN_VERDICT.casefold():
        raise CoverageReportError("BAD_REPORT", where)
    return value


def _id_list(value: object, where: str) -> list:
    if not isinstance(value, list) or len(value) > contracts.MAX_LIST:
        raise CoverageReportError("BAD_REPORT", where)
    for index, item in enumerate(value):
        _ident(item, contracts._TOKEN, f"{where}[{index}]")
    return value


def _check_report(report: object) -> dict:
    """Strict check of ANY report dict: shape, every string against its contract pattern, verdict recomputed."""
    if not isinstance(report, dict) or set(report) != _REPORT_KEYS:
        raise CoverageReportError("BAD_REPORT", "report")
    if report["schema_version"] != REPORT_SCHEMA:
        raise CoverageReportError("WRONG_SCHEMA", "report.schema_version")
    _ident(report["request_id"], contracts._ID, "report.request_id")
    _ident(report["base_revision"], contracts._HEAD, "report.base_revision")
    _ident(report["snapshot_hash"], contracts._HASH, "report.snapshot_hash")
    _ident(report["role_table_sha256"], contracts._HASH, "report.role_table_sha256")
    roles = report["roles"]
    if not isinstance(roles, list) or not roles or len(roles) > contracts.MAX_ROLES:
        raise CoverageReportError("BAD_REPORT", "report.roles")
    seen: set = set()
    for index, entry in enumerate(roles):
        where = f"report.roles[{index}]"
        if not isinstance(entry, dict) or set(entry) != _ROLE_KEYS:
            raise CoverageReportError("BAD_REPORT", where)
        role = _ident(entry["role"], contracts._ROLE, f"{where}.role")
        _ident(entry["canonical_role"], contracts._ROLE, f"{where}.canonical_role")
        if role in seen or role in _RESERVED_ROLE_NAMES:
            raise CoverageReportError("BAD_REPORT", f"{where}.role")
        seen.add(role)
        if entry["status"] not in contracts.ROLE_STATUSES or entry["class"] not in _TABLE_CLASSES:
            raise CoverageReportError("BAD_REPORT", where)
        for field in ("covered_by_code", "uncovered", "model_residual"):
            _id_list(entry[field], f"{where}.{field}")
        residual = entry["model_residual"]
        if len(residual) > contracts.MAX_MODEL_RESIDUAL or residual != sorted(set(residual)):
            raise CoverageReportError("BAD_REPORT", f"{where}.model_residual")
        count = entry["findings_count"]
        if not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= contracts.MAX_FINDINGS_PER_ROLE:
            raise CoverageReportError("BAD_REPORT", f"{where}.findings_count")
        severity = entry["highest_severity"]
        if severity is not None and severity not in contracts.SEVERITIES:
            raise CoverageReportError("BAD_REPORT", f"{where}.highest_severity")
        if (severity is None) != (count == 0):
            raise CoverageReportError("BAD_REPORT", f"{where}.highest_severity")
        if entry["status"] == "CLEAN" and (count or residual or entry["uncovered"]):
            raise CoverageReportError("BAD_REPORT", where)
        expected = _verdict_word(entry["status"], entry["class"], count, residual, entry["uncovered"])
        if entry["verdict_word"] not in VERDICT_WORDS or entry["verdict_word"] != expected:
            raise CoverageReportError("BAD_VERDICT_WORD", f"{where}.verdict_word")
    return report


def scan_pass_tokens(text: str) -> list[tuple[str, int]]:
    """Return (matched text, offset) for every whole-word pass token; see the module comment for the boundary."""
    return [(m.group(0), m.start()) for m in _PASS_RE.finditer(text)]


def _scan_check(text: str, report: dict, exempt: frozenset | set) -> None:
    """Raise if a pass token appears while any role is not fully clean; ``exempt`` are structural offsets."""
    if all(is_fully_clean(e) for e in report["roles"]):
        return
    for token, offset in scan_pass_tokens(text):
        if offset in exempt and text.startswith(CLEAN_VERDICT, offset) and token == "CLEAN":
            continue
        raise CoverageReportError("PASS_TOKEN_IN_PARTIAL_REPORT", f"offset {offset}")
    # Second pass on NFKC-normalized, case-folded text (belt and braces for non-ASCII input). Offsets only
    # line up when the length is unchanged; otherwise nothing is exempt.
    normal = unicodedata.normalize("NFKC", text).casefold()
    aligned = len(normal) == len(text)
    for token, offset in scan_pass_tokens(normal):
        if aligned and offset in exempt and text.startswith(CLEAN_VERDICT, offset) and token == "clean":
            continue
        raise CoverageReportError("PASS_TOKEN_IN_PARTIAL_REPORT", f"offset {offset} (normalized)")


def _cell(items: list) -> str:
    return ",".join(items) if items else "-"


def _rows(report: dict) -> list[list[str]]:
    return [[
        e["role"], e["verdict_word"], e["class"], e["canonical_role"], _cell(e["covered_by_code"]),
        _cell(e["uncovered"]), _cell(e["model_residual"]), str(e["findings_count"]), e["highest_severity"] or "-",
    ] for e in report["roles"]]


# The verdict word is the second cell of every row (the structural exemption uses that known position). The raw
# status is not printed: it is derivable, and the status value CLEAN is itself a pass token.
_HEADERS = ["role", "verdict", "class", "canonical", "covered_by_code", "uncovered", "model_residual",
            "findings", "highest_severity"]


def _layout_text(report: dict) -> tuple[str, set]:
    rows = _rows(report)
    table = [_HEADERS] + rows
    widths = [max(len(row[i]) for row in table) for i in range(len(_HEADERS))]
    lines = [
        f"coverage report {report['schema_version']}",
        f"request {report['request_id']} base {report['base_revision']} snapshot {report['snapshot_hash']}",
        f"role_table_sha256 {report['role_table_sha256']}",
    ]
    position = sum(len(line) + 1 for line in lines)
    exempt: set = set()
    for index, row in enumerate(table):
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()
        if index > 0 and is_fully_clean(report["roles"][index - 1]):  # header (index 0) is never exempt
            exempt.add(position + widths[0] + 2)
        lines.append(line)
        position += len(line) + 1
    return "\n".join(lines) + "\n", exempt


def _layout_markdown(report: dict) -> tuple[str, set]:
    lines = [
        f"# Coverage report {report['schema_version']}",
        "",
        f"- request: {report['request_id']}",
        f"- base revision: {report['base_revision']}",
        f"- snapshot: {report['snapshot_hash']}",
        f"- role_table_sha256: {report['role_table_sha256']}",
        "",
        "| " + " | ".join(_HEADERS) + " |",
        "|" + "|".join("---" for _ in _HEADERS) + "|",
    ]
    position = sum(len(line) + 1 for line in lines)
    exempt: set = set()
    for index, row in enumerate(_rows(report)):
        line = "| " + " | ".join(row) + " |"
        if is_fully_clean(report["roles"][index]):
            exempt.add(position + 2 + len(row[0]) + 3)
        lines.append(line)
        position += len(line) + 1
    return "\n".join(lines) + "\n", exempt


def render_text(report: dict) -> str:
    checked = _check_report(report)
    text, exempt = _layout_text(checked)
    _scan_check(text, checked, exempt)
    return text


def render_markdown(report: dict) -> str:
    checked = _check_report(report)
    text, exempt = _layout_markdown(checked)
    _scan_check(text, checked, exempt)
    return text


def assert_no_pass_token(rendering: str, report: dict) -> None:
    """Raise PASS_TOKEN_IN_PARTIAL_REPORT if a pass token appears while any role is not fully clean.

    Rule: when every role is fully clean nothing is checked. Otherwise every scanner hit is a violation, except
    CLEAN_LOCAL at the verdict cell of a fully clean role's body row. That position is known only structurally:
    the rendering must be byte-identical to the text or markdown layout built from this report; any other string
    gets no exemption at all. There is no substring whitelist.
    """
    checked = _check_report(report)
    if not isinstance(rendering, str):
        raise CoverageReportError("BAD_REPORT", "rendering")
    exempt: set = set()
    for build in (_layout_text, _layout_markdown):
        text, offsets = build(checked)
        if text == rendering:
            exempt = offsets
            break
    _scan_check(rendering, checked, exempt)


def check_ids_have_no_pass_word(report: dict) -> None:
    """Fail closed on any id (request, role, executor, uncovered, residual) that itself contains a pass word."""
    checked = _check_report(report)
    values = [checked["request_id"]]
    for entry in checked["roles"]:
        values += [entry["role"], entry["canonical_role"], *entry["covered_by_code"], *entry["uncovered"],
                   *entry["model_residual"]]
    for value in values:
        if scan_pass_tokens(value) or scan_pass_tokens(unicodedata.normalize("NFKC", value).casefold()):
            raise CoverageReportError("PASS_WORD_IN_ID", "report")


def _load_json(path: pathlib.Path) -> tuple[object, bytes]:
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8-sig")), raw
    except (OSError, ValueError, RecursionError) as exc:
        raise CoverageReportError("UNREADABLE_INPUT", type(exc).__name__) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a truthful coverage report; writes no files.")
    parser.add_argument("--result", required=True, type=pathlib.Path)
    parser.add_argument("--table", required=True, type=pathlib.Path)
    parser.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    args = parser.parse_args(argv)  # argparse usage errors exit with status 2, like a typed report error
    try:
        result, _ = _load_json(args.result)
        table, table_bytes = _load_json(args.table)
        try:
            report = render_coverage_report(result, table, hashlib.sha256(table_bytes).hexdigest())
            check_ids_have_no_pass_word(report)
        except RecursionError as exc:
            raise CoverageReportError("INVALID_RESULT", "nesting", "RecursionError") from exc
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
