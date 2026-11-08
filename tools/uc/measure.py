"""Measured effect on paired tasks (sprint U1, task U1-8).

Compares two token reports produced by ``token_baseline.py report`` for the same paired task:
``before`` (all review roles done by model reviewers) and ``after`` (the entry command ran first
and the model handled only the residual slice), together with the role result that the entry
command returned. Nothing is estimated: a missing or non-MEASURED report, or a role absent from
either report, gives NOT_RUN or NOT_MEASURED and no verdict.

A role is LOCAL_FIRST only when all of the following hold:
  * the role result lists it with class LOCAL or LOCAL_PLUS_MODEL and a status other than
    NOT_COVERED, NOT_RUN or BLOCKED (the local part really ran);
  * both reports have tokens for the role;
  * every token field of ``after`` is at most the same field of ``before`` and at least one is lower.
Otherwise it is NO_GAIN. Token fields are compared one by one and never summed into one number.

Usage:
    python tools/uc/measure.py compare --before <report.json> --after <report.json> --result <role-result.json>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import contracts  # noqa: E402

TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
LOCAL_RAN_CLASSES = ("LOCAL", "LOCAL_PLUS_MODEL")
LOCAL_DID_NOT_RUN = ("NOT_COVERED", "NOT_RUN", "BLOCKED")


def _report_roles(report: object, where: str) -> dict:
    if not isinstance(report, dict) or report.get("status") != "MEASURED" or not isinstance(report.get("roles"), dict):
        raise ValueError(f"{where} is not a MEASURED token report")
    return report["roles"]


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _verdict(b: object, a: object, local_ran: bool) -> dict:
    if not isinstance(b, dict) or not isinstance(a, dict):
        return {"verdict": "NOT_MEASURED", "reason": "role missing from the before or after report", "local_ran": local_ran}
    deltas = {}
    for field in TOKEN_FIELDS:
        before_value, after_value = _count(b.get(field)), _count(a.get(field))
        if before_value is None or after_value is None:
            return {"verdict": "NOT_MEASURED", "reason": f"{field} missing or not a non-negative integer",
                    "local_ran": local_ran}
        deltas[field] = after_value - before_value
    shrunk = all(d <= 0 for d in deltas.values()) and any(d < 0 for d in deltas.values())
    return {"verdict": "LOCAL_FIRST" if local_ran and shrunk else "NO_GAIN", "local_ran": local_ran,
            "delta_by_field": deltas}


def compare(before: object, after: object, result: object) -> dict:
    """Return the per-role verdicts, or a NOT_RUN document with the reason."""
    try:
        before_roles = _report_roles(before, "before")
        after_roles = _report_roles(after, "after")
        role_result = contracts.validate_result(result)
    except (ValueError, contracts.ContractError) as exc:
        return {"status": "NOT_RUN", "reason": str(exc)[:200], "roles": {}}
    verdicts: dict[str, dict] = {}
    priority = {"NOT_MEASURED": 2, "NO_GAIN": 1, "LOCAL_FIRST": 0}
    for entry in role_result["roles"]:
        name = entry["canonical_role"]
        local_ran = entry["class"] in LOCAL_RAN_CLASSES and entry["status"] not in LOCAL_DID_NOT_RUN
        verdict = _verdict(before_roles.get(name), after_roles.get(name), local_ran)
        previous = verdicts.get(name)
        if previous is None or priority[verdict["verdict"]] > priority[previous["verdict"]]:
            verdicts[name] = verdict  # aliases of one role: the weakest verdict wins, whatever the row order
    return {"status": "MEASURED", "roles": verdicts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("compare")
    for flag in ("--before", "--after", "--result"):
        cmd.add_argument(flag, required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    try:
        docs = [json.loads(p.read_text(encoding="utf-8")) for p in (args.before, args.after, args.result)]
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "NOT_RUN", "reason": f"unreadable input: {type(exc).__name__}", "roles": {}},
                         sort_keys=True))
        return 2
    out = compare(*docs)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if out["status"] == "MEASURED" else 2


if __name__ == "__main__":
    sys.exit(main())
