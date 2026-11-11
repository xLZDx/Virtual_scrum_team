"""U6-2: measured savings report (tokens and cost per role against the U1-1 baseline on paired tasks).

Nothing is estimated. A number appears only when it is computed from files that exist and whose SHA-256
matches the manifests that pin them. The token counting, the manifest verification and the role attribution
are NOT redone here: they come from ``token_baseline`` (U1-1); the optional per-task local-first verdict comes
from ``measure.compare`` (U1-8).

Inputs
  * baseline manifest  - the U1-1 manifest (``token_baseline.py build-manifest``), the "before" side;
  * current manifest   - a manifest of the "after" side (same format);
  * project dir        - the directory that holds the transcripts both manifests name;
  * paired tasks       - a non-empty list of objects
        {"task_id": str, "before_session": str, "after_session": str, "role_result": <optional path>}
    ``before_session`` must be a session of the baseline manifest, ``after_session`` of the current manifest.
    A session is the unit of pairing: the transcripts of a session must hold only the paired task, otherwise the
    numbers include unrelated work (stated in the limits);
  * price table        - optional JSON file, see below. Without it the cost is NOT_RUN.

Price table (JSON): {"source": "<where the prices come from>", "currency": "USD", "unit_tokens": 1000000,
"models": {"<model id>": {"input_tokens": n, "output_tokens": n, "cache_read_input_tokens": n,
"cache_creation_input_tokens": n}}}. ``source`` must be a non-empty string; every price is a non-negative
number. The cost of a role is computed only when all its paired transcripts used exactly one model and that
model has a price row; the prices are never guessed.

Rules
  * Hash mismatch, missing file, damaged records, a missing manifest ... -> status NOT_RUN, no numbers
    (the refusal code is the ``token_baseline`` reason, e.g. HASH_MISMATCH, FILE_MISSING, or MISSING_BASELINE).
  * No paired tasks -> NOT_RUN / NO_PAIRED_TASKS. The same session pinned on both sides, or a session used
    by two tasks -> NOT_RUN (PAIR_NOT_DISTINCT / DUPLICATE_SESSION).
  * Same-model requirement: a role is compared only when the set of models recorded in its paired transcripts is
    identical before and after. Otherwise the role is refused (MODEL_MISMATCH, or MODEL_UNKNOWN when a message
    has no model) and carries no numbers. If no role is left, the report is NOT_RUN.
  * The four token fields are reported separately (input, output, cache read, cache creation) and never summed
    into one number. Sums across tasks are made field by field.
  * Roles present on one side only are listed as unpaired and carry no numbers.
  * ``build_savings_report`` does not raise for expected failures; any unexpected exception becomes the code
    INTERNAL_ERROR (exception type name only).

CLI:
    python -s -m tools.uc.savings_report --baseline-manifest <file> --current-manifest <file> --project-dir <dir>
        --paired-tasks <file.json> [--price-table <file.json>] --out-json <file> --out-md <file>
Exit code 0 for MEASURED, 2 for NOT_RUN. Files are written with LF line endings.

Standard library plus tools.uc.token_baseline / tools.uc.measure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from tools.uc import measure
from tools.uc import token_baseline as tb

TOKEN_FIELDS = tb.TOKEN_FIELDS

# refusal codes of this module (token_baseline reason codes are passed through unchanged)
MISSING_BASELINE = "MISSING_BASELINE"
MISSING_CURRENT = "MISSING_CURRENT"
MANIFEST_UNREADABLE = "MANIFEST_UNREADABLE"
PROJECT_DIR_MISSING = "PROJECT_DIR_MISSING"
NO_PAIRED_TASKS = "NO_PAIRED_TASKS"
PAIRED_TASK_INVALID = "PAIRED_TASK_INVALID"
SESSION_NOT_IN_MANIFEST = "SESSION_NOT_IN_MANIFEST"
PAIR_NOT_DISTINCT = "PAIR_NOT_DISTINCT"
DUPLICATE_SESSION = "DUPLICATE_SESSION"
MODEL_MISMATCH = "MODEL_MISMATCH"
MODEL_UNKNOWN = "MODEL_UNKNOWN"
NO_COMMON_ROLES = "NO_COMMON_ROLES"
INTERNAL_ERROR = "INTERNAL_ERROR"
# cost reasons
PRICE_TABLE_NOT_SUPPLIED = "PRICE_TABLE_NOT_SUPPLIED"
PRICE_TABLE_INVALID = "PRICE_TABLE_INVALID"
COST_MODEL_UNPRICED = "COST_MODEL_UNPRICED"
COST_MULTIPLE_MODELS = "COST_MULTIPLE_MODELS"

MEASURED = "MEASURED"
NOT_RUN = "NOT_RUN"

Pairs = tuple[tuple[str, Any], ...]


@dataclass(frozen=True)
class RoleSavings:
    role: str
    paired_tasks: tuple[str, ...]
    models: tuple[str, ...]
    before: tuple[tuple[str, int], ...]  # the four fields, summed over the paired tasks, field by field
    after: tuple[tuple[str, int], ...]
    delta: tuple[tuple[str, int], ...]  # after - before; negative = fewer tokens
    verdicts: tuple[tuple[str, str], ...]  # task_id -> measure.compare verdict, or NOT_RUN
    cost_status: str  # MEASURED or NOT_RUN
    cost_reason: str
    cost: tuple[tuple[str, str], ...]  # (before, after, delta) as decimal strings; empty when NOT_RUN


@dataclass(frozen=True)
class SavingsReport:
    status: str  # MEASURED or NOT_RUN
    refusals: tuple[tuple[str, str], ...]  # (code, detail); partial refusals may exist next to MEASURED
    roles: tuple[RoleSavings, ...]
    paired_task_ids: tuple[str, ...]
    unpaired_roles: tuple[str, ...]
    cost_status: str
    cost_reason: str
    cost_source: str
    cost_currency: str
    limits: tuple[str, ...]
    inputs: tuple[tuple[str, str], ...]  # name -> sha256 of the input files that were read

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "token_fields": list(TOKEN_FIELDS),
            "refusals": [{"code": c, "detail": d} for c, d in self.refusals],
            "paired_task_ids": list(self.paired_task_ids),
            "unpaired_roles": list(self.unpaired_roles),
            "roles": {
                r.role: {
                    "paired_tasks": list(r.paired_tasks),
                    "models": list(r.models),
                    "before": dict(r.before),
                    "after": dict(r.after),
                    "delta": dict(r.delta),
                    "verdicts": dict(r.verdicts),
                    "cost": {"status": r.cost_status, "reason": r.cost_reason, **dict(r.cost)},
                }
                for r in self.roles
            },
            "cost": {"status": self.cost_status, "reason": self.cost_reason, "source": self.cost_source,
                     "currency": self.cost_currency},
            "limits": list(self.limits),
            "inputs": dict(self.inputs),
        }


class _Refuse(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


# ------------------------------------------------------------------ loading
def _load_manifest(path: object, missing_code: str) -> tuple[dict, str]:
    p = pathlib.Path(str(path)) if isinstance(path, (str, pathlib.Path)) else None
    if p is None or not p.is_file():
        raise _Refuse(missing_code, "file not found")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _Refuse(MANIFEST_UNREADABLE, f"{p.name}: {type(exc).__name__}") from exc
    if not isinstance(data, dict):
        raise _Refuse(MANIFEST_UNREADABLE, f"{p.name}: not an object")
    return data, tb.sha256_file(p)


def _verify(manifest: dict, project_dir: pathlib.Path, side: str) -> None:
    try:
        tb.verify_manifest(manifest, project_dir)
    except tb.BaselineNotRun as exc:
        raise _Refuse(exc.reason, f"{side} manifest: {exc.detail}") from exc


def _session(manifest: dict, session_id: str) -> dict | None:
    for session in manifest["sessions"]:
        if session.get("session_id") == session_id:
            return session
    return None


def _validate_pairs(paired_tasks: object, baseline: dict, current: dict) -> list[dict]:
    if not isinstance(paired_tasks, (list, tuple)) or not paired_tasks:
        raise _Refuse(NO_PAIRED_TASKS, "no paired tasks supplied")
    seen_tasks: set[str] = set()
    seen_before: set[str] = set()
    seen_after: set[str] = set()
    out = []
    for item in paired_tasks:
        if not isinstance(item, dict):
            raise _Refuse(PAIRED_TASK_INVALID, "a paired task is not an object")
        task_id, b_id, a_id = item.get("task_id"), item.get("before_session"), item.get("after_session")
        if not all(isinstance(v, str) and v for v in (task_id, b_id, a_id)):
            raise _Refuse(PAIRED_TASK_INVALID, "task_id, before_session and after_session must be non-empty strings")
        if task_id in seen_tasks:
            raise _Refuse(PAIRED_TASK_INVALID, f"duplicate task_id {task_id}")
        if b_id in seen_before or a_id in seen_after:
            raise _Refuse(DUPLICATE_SESSION, f"task {task_id}: a session is used by two tasks")
        b_session, a_session = _session(baseline, b_id), _session(current, a_id)
        if b_session is None or a_session is None:
            raise _Refuse(SESSION_NOT_IN_MANIFEST, f"task {task_id}")
        if b_session["files"] == a_session["files"]:
            raise _Refuse(PAIR_NOT_DISTINCT, f"task {task_id}: the same pinned transcripts on both sides")
        seen_tasks.add(task_id)
        seen_before.add(b_id)
        seen_after.add(a_id)
        out.append({"task_id": task_id, "before": b_session, "after": a_session,
                    "role_result": item.get("role_result")})
    return out


# ------------------------------------------------------------------ per-session measurement
def _sub_manifest(session: dict) -> dict:
    return {"version": tb.MANIFEST_VERSION, "token_fields": list(TOKEN_FIELDS),
            "attribution_rule": tb.ATTRIBUTION_RULE, "sessions": [session]}


def _models_by_role(session: dict, project_dir: pathlib.Path) -> dict[str, set[str]]:
    """role -> models of the counted messages; the empty string marks a counted message without a model."""
    models: dict[str, set[str]] = {}
    for entry in session["files"]:
        path = project_dir / entry["path"]
        if path.suffix != ".jsonl":
            continue
        in_sub = path.parent.name == "subagents"
        role = tb._role_of_subagent(path) if in_sub else tb.ORCHESTRATOR_ROLE
        last: dict[str, str] = {}
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                message = record.get("message") if isinstance(record, dict) else None
                if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                    continue
                if not isinstance(message.get("id"), str):
                    continue
                model = message.get("model")
                last[message["id"]] = model if isinstance(model, str) else ""
        if last:
            models.setdefault(role, set()).update(last.values())
    return models


def _measure_side(session: dict, project_dir: pathlib.Path, side: str) -> tuple[dict, dict[str, set[str]]]:
    try:
        report = tb.compute(_sub_manifest(session), project_dir)
    except tb.BaselineNotRun as exc:
        raise _Refuse(exc.reason, f"{side} session {session.get('session_id')}: {exc.detail}") from exc
    return report, _models_by_role(session, project_dir)


def _verdicts(role_result_path: object, before: dict, after: dict) -> dict[str, str]:
    if not isinstance(role_result_path, (str, pathlib.Path)):
        return {}
    try:
        doc = json.loads(pathlib.Path(role_result_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"": NOT_RUN}
    out = measure.compare(before, after, doc)
    if out.get("status") != "MEASURED":
        return {"": NOT_RUN}
    return {role: str(v.get("verdict")) for role, v in out["roles"].items()}


# ------------------------------------------------------------------ price table
def _load_prices(path: object) -> tuple[dict | None, str, str]:
    """-> (table or None, reason when None, sha256 or '')."""
    if path is None:
        return None, PRICE_TABLE_NOT_SUPPLIED, ""
    p = pathlib.Path(str(path))
    if not p.is_file():
        return None, PRICE_TABLE_INVALID, ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        digest = tb.sha256_file(p)
    except (OSError, ValueError):
        return None, PRICE_TABLE_INVALID, ""
    try:
        if not isinstance(data, dict) or not isinstance(data.get("source"), str) or not data["source"].strip():
            raise ValueError("source")
        if not isinstance(data.get("currency"), str) or not data["currency"]:
            raise ValueError("currency")
        unit = data.get("unit_tokens")
        if not isinstance(unit, int) or isinstance(unit, bool) or unit <= 0:
            raise ValueError("unit_tokens")
        models = data.get("models")
        if not isinstance(models, dict) or not models:
            raise ValueError("models")
        parsed: dict[str, dict[str, Decimal]] = {}
        for name, row in models.items():
            if not isinstance(row, dict):
                raise ValueError("row")
            prices = {}
            for field in TOKEN_FIELDS:
                value = row.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    raise ValueError(field)
                price = Decimal(str(value))
                if not price.is_finite() or price < 0:
                    raise ValueError(field)
                prices[field] = price
            parsed[name] = prices
    except (ValueError, InvalidOperation):
        return None, PRICE_TABLE_INVALID, digest
    return {"source": data["source"], "currency": data["currency"], "unit": unit, "models": parsed}, "", digest


def _cost(tokens: dict[str, int], prices: dict[str, Decimal], unit: int) -> Decimal:
    return sum((Decimal(tokens[f]) * prices[f] for f in TOKEN_FIELDS), Decimal(0)) / Decimal(unit)


def _fmt(value: Decimal) -> str:
    return format(value, "f")


# ------------------------------------------------------------------ the report
def _limits(n_tasks: int, unpaired: Sequence[str], refused: Sequence[str]) -> tuple[str, ...]:
    lines = [
        f"Number of paired tasks: {n_tasks}. Too few pairs to say anything about variance; no statistical claim is made.",
        "Same-model requirement: a role is compared only when the set of models in its transcripts is identical "
        "before and after; other roles are refused and carry no numbers.",
        "Cache effects: cache_read_input_tokens and cache_creation_input_tokens depend on cache warmth, session "
        "order and prompt prefix reuse, not only on the work done; they are reported separately and are never summed "
        "with input/output tokens or turned into one saving figure.",
        "The unit of pairing is a whole session: any unrelated work inside a paired session is counted.",
        "Usage is taken from the pinned transcripts as recorded; the orchestrator role holds all main-transcript "
        "usage of the session.",
        "Unpaired roles (present on one side only, no numbers): " + (", ".join(sorted(unpaired)) or "none") + ".",
        "Roles refused for model reasons (no numbers): " + (", ".join(sorted(refused)) or "none") + ".",
        "Cost is computed only from a supplied price table with a source; no price is built in.",
    ]
    return tuple(lines)


def _not_run(refusals: list[tuple[str, str]], inputs: list[tuple[str, str]], n_tasks: int = 0) -> SavingsReport:
    return SavingsReport(status=NOT_RUN, refusals=tuple(refusals), roles=(), paired_task_ids=(), unpaired_roles=(),
                         cost_status=NOT_RUN, cost_reason="NO_MEASUREMENT", cost_source="", cost_currency="",
                         limits=_limits(n_tasks, (), ()), inputs=tuple(inputs))


def build_savings_report(baseline_manifest_path: object, current_manifest_path: object, project_dir: object,
                         paired_tasks: object, price_table_path: object = None) -> SavingsReport:
    inputs: list[tuple[str, str]] = []
    try:
        return _build(baseline_manifest_path, current_manifest_path, project_dir, paired_tasks, price_table_path,
                      inputs)
    except _Refuse as exc:
        return _not_run([(exc.code, exc.detail)], inputs)
    except Exception as exc:  # fail closed: an unexpected error must never look like a measurement
        return _not_run([(INTERNAL_ERROR, type(exc).__name__)], inputs)


def _build(baseline_path: object, current_path: object, project_dir: object, paired_tasks: object,
           price_path: object, inputs: list[tuple[str, str]]) -> SavingsReport:
    pdir = pathlib.Path(str(project_dir)) if isinstance(project_dir, (str, pathlib.Path)) else None
    baseline, b_hash = _load_manifest(baseline_path, MISSING_BASELINE)
    inputs.append(("baseline_manifest_sha256", b_hash))
    current, c_hash = _load_manifest(current_path, MISSING_CURRENT)
    inputs.append(("current_manifest_sha256", c_hash))
    if pdir is None or not pdir.is_dir():
        raise _Refuse(PROJECT_DIR_MISSING, "project dir is not a directory")
    _verify(baseline, pdir, "baseline")
    _verify(current, pdir, "current")
    pairs = _validate_pairs(paired_tasks, baseline, current)

    prices, price_reason, price_hash = _load_prices(price_path)
    if price_hash:
        inputs.append(("price_table_sha256", price_hash))

    # role -> accumulated data; refused roles are kept out of the numbers
    sums: dict[str, dict] = {}
    refused: dict[str, tuple[str, str]] = {}
    unpaired: set[str] = set()
    for pair in pairs:
        b_report, b_models = _measure_side(pair["before"], pdir, "baseline")
        a_report, a_models = _measure_side(pair["after"], pdir, "current")
        verdicts = _verdicts(pair["role_result"], b_report, a_report)
        b_roles, a_roles = b_report["roles"], a_report["roles"]
        for role in sorted(set(b_roles) ^ set(a_roles)):
            unpaired.add(role)
        for role in sorted(set(b_roles) & set(a_roles)):
            bm, am = b_models.get(role, set()), a_models.get(role, set())
            if "" in bm or "" in am or not bm or not am:
                refused.setdefault(role, (MODEL_UNKNOWN, f"task {pair['task_id']}: a counted message has no model"))
                continue
            if bm != am:
                refused[role] = (MODEL_MISMATCH, f"task {pair['task_id']}: before {sorted(bm)} after {sorted(am)}")
                continue
            acc = sums.setdefault(role, {"tasks": [], "models": set(), "before": dict.fromkeys(TOKEN_FIELDS, 0),
                                         "after": dict.fromkeys(TOKEN_FIELDS, 0), "verdicts": {}, "per_task": []})
            acc["tasks"].append(pair["task_id"])
            acc["models"] |= bm
            for field in TOKEN_FIELDS:
                acc["before"][field] += b_roles[role][field]
                acc["after"][field] += a_roles[role][field]
            acc["verdicts"][pair["task_id"]] = verdicts.get(role) or verdicts.get("") or NOT_RUN
            acc["per_task"].append((bm, {f: b_roles[role][f] for f in TOKEN_FIELDS},
                                    {f: a_roles[role][f] for f in TOKEN_FIELDS}))
    for role in refused:  # a role refused in any task is refused as a whole: partial sums would mislead
        sums.pop(role, None)

    refusals = [(code, f"role {role}: {detail}") for role, (code, detail) in sorted(refused.items())]
    if not sums:
        no_roles = [(NO_COMMON_ROLES, "no role has tokens on both sides")]
        return SavingsReport(status=NOT_RUN, refusals=tuple(refusals or no_roles),
                             roles=(), paired_task_ids=tuple(p["task_id"] for p in pairs),
                             unpaired_roles=tuple(sorted(unpaired)), cost_status=NOT_RUN, cost_reason="NO_MEASUREMENT",
                             cost_source="", cost_currency="",
                             limits=_limits(len(pairs), unpaired, refused), inputs=tuple(inputs))

    roles = []
    any_cost = False
    for role in sorted(sums):
        acc = sums[role]
        delta = {f: acc["after"][f] - acc["before"][f] for f in TOKEN_FIELDS}
        cost_status, cost_reason, cost = NOT_RUN, price_reason, ()
        if prices is not None:
            if len(acc["models"]) != 1:
                cost_reason = COST_MULTIPLE_MODELS
            elif next(iter(acc["models"])) not in prices["models"]:
                cost_reason = COST_MODEL_UNPRICED
            else:
                row = prices["models"][next(iter(acc["models"]))]
                before_cost = _cost(acc["before"], row, prices["unit"])
                after_cost = _cost(acc["after"], row, prices["unit"])
                cost_status, cost_reason = MEASURED, ""
                cost = (("before", _fmt(before_cost)), ("after", _fmt(after_cost)),
                        ("delta", _fmt(after_cost - before_cost)))
                any_cost = True
        roles.append(RoleSavings(
            role=role, paired_tasks=tuple(acc["tasks"]), models=tuple(sorted(acc["models"])),
            before=tuple((f, acc["before"][f]) for f in TOKEN_FIELDS),
            after=tuple((f, acc["after"][f]) for f in TOKEN_FIELDS),
            delta=tuple((f, delta[f]) for f in TOKEN_FIELDS),
            verdicts=tuple(sorted(acc["verdicts"].items())),
            cost_status=cost_status, cost_reason=cost_reason, cost=cost))
    return SavingsReport(
        status=MEASURED, refusals=tuple(refusals), roles=tuple(roles),
        paired_task_ids=tuple(p["task_id"] for p in pairs), unpaired_roles=tuple(sorted(unpaired)),
        cost_status=MEASURED if any_cost else NOT_RUN,
        cost_reason="" if any_cost else (price_reason or "NO_ROLE_PRICED"),
        cost_source=prices["source"] if prices else "", cost_currency=prices["currency"] if prices else "",
        limits=_limits(len(pairs), unpaired, refused), inputs=tuple(inputs))


# ------------------------------------------------------------------ rendering and CLI
def render_markdown(report: SavingsReport) -> str:
    d = report.to_dict()
    out = ["# Measured savings report", "", f"Status: **{d['status']}**", ""]
    if d["refusals"]:
        out += ["## Refusals", ""] + [f"- `{r['code']}`: {r['detail']}" for r in d["refusals"]] + [""]
    if report.status != MEASURED:
        out += ["No numbers are shown: nothing was measured.", ""]
    else:
        out += [f"Paired tasks ({len(report.paired_task_ids)}): " + ", ".join(report.paired_task_ids), ""]
        for role in report.roles:
            out += [f"## Role `{role.role}`", "",
                    f"Tasks: {', '.join(role.paired_tasks)}; models: {', '.join(role.models)}; "
                    f"local-first verdicts: " + (", ".join(f"{t}={v}" for t, v in role.verdicts) or "NOT_RUN"), "",
                    "| token field | before | after | delta (after - before) |", "|---|---:|---:|---:|"]
            for (f, b), (_, a), (_, dl) in zip(role.before, role.after, role.delta):
                out.append(f"| {f} | {b} | {a} | {dl} |")
            if role.cost_status == MEASURED:
                c = dict(role.cost)
                out += ["", f"Cost ({report.cost_currency}, source: {report.cost_source}): before {c['before']}, "
                            f"after {c['after']}, delta {c['delta']}"]
            else:
                out += ["", f"Cost: NOT_RUN ({role.cost_reason})"]
            out.append("")
        out += [f"Cost overall: {report.cost_status}" + (f" ({report.cost_reason})" if report.cost_reason else ""), ""]
    out += ["## Limits", ""] + [f"- {line}" for line in report.limits] + [""]
    out += ["## Inputs (sha256)", ""] + [f"- {k}: `{v}`" for k, v in report.inputs] + [""]
    return "\n".join(out)


def _write(path: pathlib.Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("--baseline-manifest", "--current-manifest", "--project-dir", "--paired-tasks", "--out-json",
                 "--out-md"):
        parser.add_argument(flag, required=True, type=pathlib.Path)
    parser.add_argument("--price-table", type=pathlib.Path, default=None)
    args = parser.parse_args(argv)
    try:
        pairs: object = json.loads(args.paired_tasks.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pairs = None  # becomes NO_PAIRED_TASKS
    report = build_savings_report(args.baseline_manifest, args.current_manifest, args.project_dir, pairs,
                                  args.price_table)
    try:
        _write(args.out_json, json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
        _write(args.out_md, render_markdown(report))
    except OSError as exc:
        print(json.dumps({"status": NOT_RUN, "reason": "OUTPUT_UNWRITABLE", "detail": type(exc).__name__}))
        return 2
    print(json.dumps({"status": report.status, "refusals": [c for c, _ in report.refusals],
                      "out_json": str(args.out_json), "out_md": str(args.out_md)}, sort_keys=True))
    return 0 if report.status == MEASURED else 2


if __name__ == "__main__":
    sys.exit(main())
