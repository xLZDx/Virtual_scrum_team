"""U6-2: measured savings report (tools/uc/savings_report.py).

Acceptance text (plan row U6-2): "Tokens and cost per role against the U1-1 baseline on paired tasks, with limits;
no measurement means NOT_RUN."

Expected values come from hand arithmetic written next to the fixtures (never from the module under test):
  baseline session b1: orchestrator tokens (10, 20, 300, 4000), python-reviewer tokens (100, 200, 3000, 40000)
  current session  a1: orchestrator tokens (4, 5, 60, 700),     python-reviewer tokens (10, 20, 300, 4000)
  (input, output, cache read, cache creation); every message uses the model "model-x".
  Prices per 1,000,000 tokens for model-x: input 3, output 15, cache read 0.3, cache creation 3.75.
  Cost orchestrator: before (10*3 + 20*15 + 300*0.3 + 4000*3.75)/1e6 = 15420/1e6 = 0.01542
                     after  (4*3 + 5*15 + 60*0.3 + 700*3.75)/1e6 = 2730/1e6 = 0.00273
  Cost reviewer:     before (100*3 + 200*15 + 3000*0.3 + 40000*3.75)/1e6 = 154200/1e6 = 0.1542
                     after  (10*3 + 20*15 + 300*0.3 + 4000*3.75)/1e6 = 15420/1e6 = 0.01542
  Delta = after - before; saving = before - after, both per field.
Tests are written, NOT_RUN (operator ban).
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess
import sys
from decimal import Decimal

import pytest

from tests.uc import ucsupport as S
from tools.uc import savings_report as sr
from tools.uc import token_baseline as tb

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def usage(i, o, cr, cw):
    return dict(zip(FIELDS, (i, o, cr, cw)))


def line(message_id, u, model="model-x"):
    message = {"id": message_id, "usage": u}
    if model is not None:
        message["model"] = model
    return json.dumps({"type": "assistant", "message": message})


def write_lines(path: pathlib.Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_session(proj, sid, orch, reviewer, model="model-x", reviewer_model=None, extra_role=None):
    # the first orchestrator line is superseded by the last line of the same message id
    write_lines(proj / f"{sid}.jsonl", [line("o0", usage(1, 1, 1, 1), model), line("o0", usage(*orch), model)])
    sub = proj / sid / "subagents"
    write_lines(sub / "agent-r.jsonl", [line("r1", usage(*reviewer), reviewer_model or model)])
    (sub / "agent-r.meta.json").write_text(json.dumps({"agentType": "python-reviewer"}), encoding="utf-8")
    if extra_role:
        write_lines(sub / "agent-x.jsonl", [line("x1", usage(7, 7, 7, 7), model)])
        (sub / "agent-x.meta.json").write_text(json.dumps({"agentType": extra_role}), encoding="utf-8")


def manifest_file(proj, sid, out):
    out.write_text(json.dumps(tb.build_manifest(proj, [sid])), encoding="utf-8")
    return out


PAIR = [{"task_id": "T1", "before_session": "b1", "after_session": "a1"}]


class Env:  # tiny holder, keeps the fixture readable
    def __init__(self, proj, base, cur, tmp):
        self.proj, self.base, self.cur, self.tmp = proj, base, cur, tmp


@pytest.fixture()
def env(tmp_path):
    proj = tmp_path / "proj"
    write_session(proj, "b1", (10, 20, 300, 4000), (100, 200, 3000, 40000))
    write_session(proj, "a1", (4, 5, 60, 700), (10, 20, 300, 4000))
    return Env(proj, manifest_file(proj, "b1", tmp_path / "base.json"),
               manifest_file(proj, "a1", tmp_path / "cur.json"), tmp_path)


def price_file(tmp, **over):
    table = {"source": "operator-supplied price list, test fixture", "currency": "USD", "unit_tokens": 1000000,
             "models": {"model-x": {"input_tokens": 3, "output_tokens": 15, "cache_read_input_tokens": 0.3,
                                    "cache_creation_input_tokens": 3.75}}}
    table.update(over)
    path = tmp / "prices.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    return path


def run(env, pairs=PAIR, prices=None):
    return sr.build_savings_report(env.base, env.cur, env.proj, pairs, prices)


def role(report, name):
    return next(r for r in report.roles if r.role == name)


def register(env, base_ids, cur_ids):
    """Rebuild both manifests (they pin the current bytes) for the given session ids."""
    env.base.write_text(json.dumps(tb.build_manifest(env.proj, list(base_ids))), encoding="utf-8")
    env.cur.write_text(json.dumps(tb.build_manifest(env.proj, list(cur_ids))), encoding="utf-8")


def two_tasks(env):
    """T1 = b1/a1 (fixture); T2 = b2/a2: orchestrator (1,2,3,4) -> (0,1,1,1), reviewer (5,6,7,8) -> (1,1,1,1)."""
    write_session(env.proj, "b2", (1, 2, 3, 4), (5, 6, 7, 8))
    write_session(env.proj, "a2", (0, 1, 1, 1), (1, 1, 1, 1))
    register(env, ["b1", "b2"], ["a1", "a2"])
    return PAIR + [{"task_id": "T2", "before_session": "b2", "after_session": "a2"}]


def all_ints(node):
    if isinstance(node, bool):
        return set()
    if isinstance(node, int):
        return {node}
    if isinstance(node, dict):
        return set().union(*[all_ints(v) for v in node.values()]) if node else set()
    if isinstance(node, list):
        return set().union(*[all_ints(v) for v in node]) if node else set()
    return set()


# ------------------------------------------------------------------ measured
def test_measured_two_roles_with_per_field_deltas(env):
    report = run(env)
    assert report.status == "MEASURED" and report.refusals == ()
    assert [r.role for r in report.roles] == ["orchestrator", "python-reviewer"]
    orch, rev = role(report, "orchestrator"), role(report, "python-reviewer")
    assert dict(orch.before) == usage(10, 20, 300, 4000) and dict(orch.after) == usage(4, 5, 60, 700)
    assert dict(orch.delta) == usage(-6, -15, -240, -3300)
    assert dict(rev.before) == usage(100, 200, 3000, 40000) and dict(rev.after) == usage(10, 20, 300, 4000)
    assert dict(rev.delta) == usage(-90, -180, -2700, -36000)
    assert orch.models == ("model-x",) and rev.paired_tasks == ("T1",)


def test_token_fields_are_never_combined(env):
    report = run(env, prices=price_file(env.tmp))
    document = report.to_dict()
    for name, entry in document["roles"].items():
        for key in ("before", "after", "delta", "saving"):
            assert list(entry[key]) == list(FIELDS), (name, key)
    # every integer anywhere in the JSON is one of the expected per-field values; a combined sum would be extra
    expected = {10, 20, 300, 4000, 4, 5, 60, 700, -6, -15, -240, -3300, 6, 15, 240, 3300,
                100, 200, 3000, 40000, -90, -180, -2700, -36000, 90, 180, 2700, 36000}
    assert all_ints(document) == expected
    assert "total" not in json.dumps(document).lower() and "total" not in sr.render_markdown(report).lower()


def test_delta_convention_and_saving_are_reported_per_field(env):
    document = run(env).to_dict()
    assert document["delta_convention"] == "after - before; negative means fewer tokens/lower cost after"
    assert document["roles"]["orchestrator"]["saving"] == usage(6, 15, 240, 3300)
    assert document["roles"]["python-reviewer"]["saving"] == usage(90, 180, 2700, 36000)


def test_sums_over_two_tasks_are_made_field_by_field(env):
    report = run(env, two_tasks(env))
    orch, rev = role(report, "orchestrator"), role(report, "python-reviewer")
    assert dict(orch.before) == usage(11, 22, 303, 4004)   # (10+1, 20+2, 300+3, 4000+4)
    assert dict(orch.after) == usage(4, 6, 61, 701)        # (4+0, 5+1, 60+1, 700+1)
    assert dict(rev.before) == usage(105, 206, 3007, 40008)  # (100+5, 200+6, 3000+7, 40000+8)
    assert dict(rev.after) == usage(11, 21, 301, 4001)       # (10+1, 20+1, 300+1, 4000+1)
    assert orch.paired_tasks == ("T1", "T2") and rev.paired_tasks == ("T1", "T2")


def test_cost_sums_over_two_tasks(env):
    # orchestrator before: 15420 + (1*3 + 2*15 + 3*0.3 + 4*3.75 = 48.9) = 15468.9 per 1e6
    # orchestrator after:  2730 + (0 + 1*15 + 1*0.3 + 1*3.75 = 19.05) = 2749.05 per 1e6
    # reviewer before: 154200 + (5*3 + 6*15 + 7*0.3 + 8*3.75 = 137.1) = 154337.1 per 1e6
    # reviewer after:  15420 + (1*3 + 1*15 + 1*0.3 + 1*3.75 = 22.05) = 15442.05 per 1e6
    report = run(env, two_tasks(env), prices=price_file(env.tmp))
    orch, rev = dict(role(report, "orchestrator").cost), dict(role(report, "python-reviewer").cost)
    assert Decimal(orch["before"]) == Decimal("0.0154689") and Decimal(orch["after"]) == Decimal("0.00274905")
    assert Decimal(rev["before"]) == Decimal("0.1543371") and Decimal(rev["after"]) == Decimal("0.01544205")
    assert Decimal(orch["delta"]) == Decimal("0.00274905") - Decimal("0.0154689")
    assert Decimal(orch["saving"]) == Decimal("0.0154689") - Decimal("0.00274905")


def test_after_larger_than_before_and_zero_before_field(env):
    # orchestrator (0, 20, 300, 4000) -> (5, 20, 0, 5000): the zero-before field grows, one field is unchanged
    write_session(env.proj, "b1", (0, 20, 300, 4000), (100, 200, 3000, 40000))
    write_session(env.proj, "a1", (5, 20, 0, 5000), (200, 200, 3000, 40000))
    register(env, ["b1"], ["a1"])
    report = run(env, prices=price_file(env.tmp))
    orch, rev = role(report, "orchestrator"), role(report, "python-reviewer")
    assert dict(orch.delta) == usage(5, 0, -300, 1000) and dict(orch.saving) == usage(-5, 0, 300, -1000)
    assert dict(rev.delta) == usage(100, 0, 0, 0) and dict(rev.saving) == usage(-100, 0, 0, 0)
    # orchestrator cost: before 0 + 300 + 90 + 15000 = 15390, after 15 + 300 + 0 + 18750 = 19065, per 1e6
    cost = dict(role(report, "orchestrator").cost)
    assert Decimal(cost["delta"]) == Decimal("0.003675") and Decimal(cost["saving"]) == Decimal("-0.003675")


def test_report_is_a_frozen_value(env):
    report = run(env)
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.status = "NOT_RUN"  # type: ignore[misc]


def test_limits_state_the_required_caveats(env):
    text = " ".join(run(env).limits)
    assert "Number of paired tasks: 1" in text
    assert "Same-model requirement" in text and "Cache effects" in text and "Unpaired roles" in text


# ------------------------------------------------------------------ NOT_RUN
def test_hash_mismatch_is_not_run_without_numbers(env):
    with (env.proj / "b1.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line("o9", usage(1, 1, 1, 1)) + "\n")  # changed after the manifest pinned it
    report = run(env)
    assert report.status == "NOT_RUN"
    assert report.refusals[0][0] == "HASH_MISMATCH"
    assert report.roles == () and report.to_dict()["roles"] == {}


def test_hash_mismatch_on_the_current_side_is_also_not_run(env):
    (env.proj / "a1" / "subagents" / "agent-r.jsonl").write_text(line("r1", usage(0, 0, 0, 0)) + "\n", encoding="utf-8")
    report = run(env)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "HASH_MISMATCH" and report.roles == ()


def test_missing_baseline_manifest(env):
    report = sr.build_savings_report(env.tmp / "absent.json", env.cur, env.proj, PAIR)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "MISSING_BASELINE" and report.roles == ()


def test_missing_current_manifest(env):
    report = sr.build_savings_report(env.base, env.tmp / "absent.json", env.proj, PAIR)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "MISSING_CURRENT"


def test_missing_transcript_is_not_run(env):
    (env.proj / "a1.jsonl").unlink()
    report = run(env)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "FILE_MISSING" and report.roles == ()


@pytest.mark.parametrize("pairs", [[], None, "x", [1], [{"task_id": "T1"}]])
def test_no_or_bad_paired_tasks_is_not_run(env, pairs):
    report = run(env, pairs)
    assert report.status == "NOT_RUN" and report.roles == ()
    assert report.refusals[0][0] == ("PAIRED_TASK_INVALID" if pairs in ([1], [{"task_id": "T1"}]) else "NO_PAIRED_TASKS")


def test_unknown_session_in_a_pair_is_not_run(env):
    report = run(env, [{"task_id": "T1", "before_session": "b1", "after_session": "nope"}])
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "SESSION_NOT_IN_MANIFEST"


def test_same_pinned_transcripts_on_both_sides_is_not_run(env):
    report = sr.build_savings_report(env.base, env.base, env.proj,
                                     [{"task_id": "T1", "before_session": "b1", "after_session": "b1"}])
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "PAIR_NOT_DISTINCT"


def test_bad_project_dir_is_not_run(env):
    report = sr.build_savings_report(env.base, env.cur, env.tmp / "nodir", PAIR)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "PROJECT_DIR_MISSING"


def test_session_used_by_two_tasks_is_not_run(env):
    report = run(env, PAIR + [{"task_id": "T2", "before_session": "b1", "after_session": "a1"}])
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "DUPLICATE_SESSION" and report.roles == ()


def test_duplicate_task_id_is_not_run(env):
    report = run(env, PAIR + PAIR)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "PAIRED_TASK_INVALID"
    assert "duplicate task_id" in report.refusals[0][1]


@pytest.mark.parametrize("text", ["{not json", "[]", ""])
def test_unreadable_manifest_is_not_run(env, text):
    env.base.write_text(text, encoding="utf-8")
    report = run(env)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "MANIFEST_UNREADABLE" and report.roles == ()


def test_transcript_not_in_the_manifest_is_not_run(env):
    write_lines(env.proj / "b1" / "subagents" / "agent-zz.jsonl", [line("z1", usage(1, 1, 1, 1))])
    report = run(env)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "UNEXPECTED_TRANSCRIPT" and report.roles == ()


def test_unreadable_paired_task_marker_is_its_own_code(env):
    report = run(env, sr.PairedTasksUnreadable())
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "PAIRED_TASKS_UNREADABLE"


def test_counts_and_models_must_describe_the_same_bytes(env, monkeypatch):
    original = sr._models_by_role

    def read_then_change(session, project_dir):
        result = original(session, project_dir)
        with (project_dir / "b1.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line("o9", usage(1, 1, 1, 1)) + "\n")  # the file changes after the models were read
        return result

    monkeypatch.setattr(sr, "_models_by_role", read_then_change)
    report = run(env)
    assert report.status == "NOT_RUN" and report.refusals[0][0] == "HASH_MISMATCH" and report.roles == ()


# ------------------------------------------------------------------ model rules
def test_model_mismatch_on_every_role_is_not_run(env):
    write_session(env.proj, "a1", (4, 5, 60, 700), (10, 20, 300, 4000), model="model-y")
    manifest_file(env.proj, "a1", env.cur)
    report = run(env)
    assert report.status == "NOT_RUN" and report.roles == ()
    assert {c for c, _ in report.refusals} == {"MODEL_MISMATCH"} and len(report.refusals) == 2


def test_model_mismatch_on_one_role_refuses_only_that_role(env):
    write_session(env.proj, "a1", (4, 5, 60, 700), (10, 20, 300, 4000), reviewer_model="model-y")
    manifest_file(env.proj, "a1", env.cur)
    report = run(env)
    assert report.status == "MEASURED"
    assert [r.role for r in report.roles] == ["orchestrator"]
    assert [c for c, _ in report.refusals] == ["MODEL_MISMATCH"] and "python-reviewer" in report.refusals[0][1]
    assert "python-reviewer" in " ".join(report.limits)


def test_message_without_model_is_refused_as_unknown(env):
    write_lines(env.proj / "a1.jsonl", [line("o0", usage(4, 5, 60, 700), None)])
    manifest_file(env.proj, "a1", env.cur)
    report = run(env)
    assert report.status == "MEASURED" and [r.role for r in report.roles] == ["python-reviewer"]
    assert [c for c, _ in report.refusals] == ["MODEL_UNKNOWN"]


@pytest.mark.parametrize("reverse", [False, True])
def test_refusal_priority_is_independent_of_task_order(env, reverse):
    # T1: the reviewer has no model after (MODEL_UNKNOWN); T2: the reviewer model differs (MODEL_MISMATCH)
    write_lines(env.proj / "a1" / "subagents" / "agent-r.jsonl", [line("r1", usage(10, 20, 300, 4000), None)])
    write_session(env.proj, "b2", (1, 2, 3, 4), (5, 6, 7, 8))
    write_session(env.proj, "a2", (0, 1, 1, 1), (1, 1, 1, 1), reviewer_model="model-y")
    register(env, ["b1", "b2"], ["a1", "a2"])
    pairs = PAIR + [{"task_id": "T2", "before_session": "b2", "after_session": "a2"}]
    report = run(env, pairs[::-1] if reverse else pairs)
    assert report.status == "MEASURED" and [r.role for r in report.roles] == ["orchestrator"]
    assert report.refusals == (("MODEL_MISMATCH",
                                "role python-reviewer: task T2: before ['model-x'] after ['model-y']"),)


# ------------------------------------------------------------------ roles
def test_role_on_one_side_only_is_unpaired_and_has_no_numbers(env):
    write_session(env.proj, "a1", (4, 5, 60, 700), (10, 20, 300, 4000), extra_role="silent-failure-hunter")
    manifest_file(env.proj, "a1", env.cur)
    report = run(env)
    assert report.unpaired_roles == ("silent-failure-hunter",)
    assert "silent-failure-hunter" not in [r.role for r in report.roles]
    assert "silent-failure-hunter" in " ".join(report.limits)


def test_role_without_meta_file_is_unknown_subagent_and_still_paired(env):
    for sid in ("b1", "a1"):
        (env.proj / sid / "subagents" / "agent-r.meta.json").unlink()
    register(env, ["b1"], ["a1"])
    report = run(env)
    assert report.status == "MEASURED" and [r.role for r in report.roles] == ["orchestrator", "unknown-subagent"]
    unknown = role(report, "unknown-subagent")
    assert dict(unknown.before) == usage(100, 200, 3000, 40000)
    assert dict(unknown.delta) == usage(-90, -180, -2700, -36000)


@pytest.mark.parametrize("reverse", [False, True])
def test_role_paired_in_one_task_and_one_sided_in_another_is_refused_whole(env, reverse):
    # T1 pairs the reviewer; T2 has the reviewer before only (the after session holds the orchestrator only)
    write_session(env.proj, "b2", (1, 2, 3, 4), (5, 6, 7, 8))
    write_lines(env.proj / "a2.jsonl", [line("o0", usage(0, 1, 1, 1))])
    register(env, ["b1", "b2"], ["a1", "a2"])
    pairs = PAIR + [{"task_id": "T2", "before_session": "b2", "after_session": "a2"}]
    report = run(env, pairs[::-1] if reverse else pairs)
    assert report.status == "MEASURED" and [r.role for r in report.roles] == ["orchestrator"]
    assert [c for c, _ in report.refusals] == ["ROLE_ONE_SIDED"] and "python-reviewer" in report.refusals[0][1]
    assert "python-reviewer" in report.unpaired_roles
    assert dict(role(report, "orchestrator").before) == usage(11, 22, 303, 4004)


# ------------------------------------------------------------------ cost
def test_cost_is_not_run_without_a_price_table(env):
    report = run(env)
    assert report.cost_status == "NOT_RUN" and report.cost_reason == "PRICE_TABLE_NOT_SUPPLIED"
    for r in report.roles:
        assert r.cost_status == "NOT_RUN" and r.cost == () and r.cost_reason == "PRICE_TABLE_NOT_SUPPLIED"
    assert report.status == "MEASURED"  # tokens are still measured


def test_cost_from_a_price_table_with_source(env):
    report = run(env, prices=price_file(env.tmp))
    assert report.cost_status == "MEASURED" and report.cost_currency == "USD"
    assert report.cost_source == "operator-supplied price list, test fixture"
    orch, rev = dict(role(report, "orchestrator").cost), dict(role(report, "python-reviewer").cost)
    assert Decimal(orch["before"]) == Decimal("0.01542") and Decimal(orch["after"]) == Decimal("0.00273")
    assert Decimal(orch["delta"]) == Decimal("-0.01269") and Decimal(orch["saving"]) == Decimal("0.01269")
    assert Decimal(rev["before"]) == Decimal("0.1542") and Decimal(rev["after"]) == Decimal("0.01542")
    assert Decimal(rev["delta"]) == Decimal("-0.13878")
    assert "price_table_sha256" in dict(report.inputs)


@pytest.mark.parametrize("over", [{"source": ""}, {"source": None}, {"currency": ""}, {"unit_tokens": 0},
                                  {"models": {}}, {"models": {"model-x": {"input_tokens": 1}}},
                                  {"models": {"model-x": {f: -1 for f in FIELDS}}}, {"source": "   "},
                                  {"models": {"model-x": {**{f: 1 for f in FIELDS}, "input_tokens": float("nan")}}},
                                  {"models": {"model-x": {**{f: 1 for f in FIELDS}, "input_tokens": True}}},
                                  {"unit_tokens": True}])
def test_invalid_price_table_keeps_tokens_but_cost_is_not_run(env, over):
    report = run(env, prices=price_file(env.tmp, **over))
    assert report.status == "MEASURED" and report.cost_status == "NOT_RUN"
    assert report.cost_reason == "PRICE_TABLE_INVALID" and all(r.cost == () for r in report.roles)
    assert report.cost_source == "" and report.cost_currency == ""


def test_unpriced_model_gives_no_cost(env):
    table = {"model-z": {f: 1 for f in FIELDS}}
    report = run(env, prices=price_file(env.tmp, models=table))
    assert report.cost_status == "NOT_RUN" and report.cost_reason == "NO_ROLE_PRICED"
    assert {r.cost_reason for r in report.roles} == {"COST_MODEL_UNPRICED"}


def test_missing_price_table_file_is_cost_not_run(env):
    report = run(env, prices=env.tmp / "none.json")
    assert report.status == "MEASURED" and report.cost_status == "NOT_RUN" and report.cost_reason == "PRICE_TABLE_INVALID"


def test_role_with_two_models_has_no_cost_while_the_other_role_is_priced(env):
    write_lines(env.proj / "b1.jsonl", [line("o0", usage(10, 20, 300, 4000), "model-x"),
                                        line("o1", usage(1, 1, 1, 1), "model-y")])
    write_lines(env.proj / "a1.jsonl", [line("o0", usage(4, 5, 60, 700), "model-x"),
                                        line("o1", usage(1, 1, 1, 1), "model-y")])
    register(env, ["b1"], ["a1"])
    models = {m: {f: 1 for f in FIELDS} for m in ("model-x", "model-y")}
    report = run(env, prices=price_file(env.tmp, models=models))
    orch, rev = role(report, "orchestrator"), role(report, "python-reviewer")
    assert orch.models == ("model-x", "model-y") and orch.cost_reason == "COST_MULTIPLE_MODELS" and orch.cost == ()
    assert dict(orch.before) == usage(11, 21, 301, 4001)
    assert rev.cost_status == "MEASURED"
    assert report.cost_status == "PARTIAL" and report.cost_reason == "SOME_ROLES_UNPRICED"


def test_mixed_priced_and_unpriced_roles_report_partial_cost(env):
    write_session(env.proj, "b1", (10, 20, 300, 4000), (100, 200, 3000, 40000), reviewer_model="model-z")
    write_session(env.proj, "a1", (4, 5, 60, 700), (10, 20, 300, 4000), reviewer_model="model-z")
    register(env, ["b1"], ["a1"])
    report = run(env, prices=price_file(env.tmp))
    assert role(report, "orchestrator").cost_status == "MEASURED"
    assert role(report, "python-reviewer").cost_reason == "COST_MODEL_UNPRICED"
    assert report.cost_status == "PARTIAL" and report.cost_reason == "SOME_ROLES_UNPRICED"


# ------------------------------------------------------------------ role_result verdicts (measure.compare)
def write_role_result(env, doc):
    path = env.tmp / "role-result.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def with_role_result(path):
    return [{**PAIR[0], "role_result": str(path)}]


def test_role_result_gives_per_role_verdicts(env):
    result = S.valid_result(exit_code=3, roles=[S.valid_role_entry()])  # python-reviewer, local part ran
    report = run(env, with_role_result(write_role_result(env, result)))
    assert dict(role(report, "python-reviewer").verdicts) == {"T1": "LOCAL_FIRST"}  # every field shrank
    assert dict(role(report, "orchestrator").verdicts) == {"T1": "NOT_RUN"}  # not in the role result


def test_unreadable_role_result_gives_not_run_verdicts_but_keeps_tokens(env):
    report = run(env, with_role_result(env.tmp / "absent-role-result.json"))
    assert report.status == "MEASURED"
    assert {v for r in report.roles for _, v in r.verdicts} == {"NOT_RUN"}


def test_invalid_role_result_gives_not_run_verdicts(env):
    report = run(env, with_role_result(write_role_result(env, {"schema_version": "wrong"})))
    assert report.status == "MEASURED"
    assert {v for r in report.roles for _, v in r.verdicts} == {"NOT_RUN"}


# ------------------------------------------------------------------ CLI
def cli(env, *extra, pairs=PAIR, pairs_text=None, out_md=None):
    pairs_file = env.tmp / "pairs.json"
    pairs_file.write_text(json.dumps(pairs) if pairs_text is None else pairs_text, encoding="utf-8")
    out_json, out_md = env.tmp / "out.json", out_md or env.tmp / "out.md"
    proc = subprocess.run(
        [sys.executable, "-s", "-m", "tools.uc.savings_report", "--baseline-manifest", str(env.base),
         "--current-manifest", str(env.cur), "--project-dir", str(env.proj), "--paired-tasks", str(pairs_file),
         "--out-json", str(out_json), "--out-md", str(out_md), *extra],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    return proc, out_json, out_md


def test_cli_measured_writes_json_and_markdown_with_lf(env):
    proc, out_json, out_md = cli(env)
    assert proc.returncode == 0, proc.stderr
    document = json.loads(out_json.read_text(encoding="utf-8"))
    assert document["status"] == "MEASURED"
    assert document["roles"]["orchestrator"]["delta"] == usage(-6, -15, -240, -3300)
    assert document["delta_convention"].startswith("after - before")
    markdown = out_md.read_bytes()
    assert b"\r\n" not in markdown and b"\r\n" not in out_json.read_bytes()
    assert b"| input_tokens | 10 | 4 | -6 | 6 |" in markdown and b"## Limits" in markdown
    assert b"Cost: NOT_RUN (PRICE_TABLE_NOT_SUPPLIED)" in markdown
    assert sorted(p.name for p in env.tmp.iterdir() if ".tmp" in p.name) == []  # no temp file is left behind


def test_cli_with_price_table_reports_cost(env):
    proc, out_json, out_md = cli(env, "--price-table", str(price_file(env.tmp)))
    assert proc.returncode == 0, proc.stderr
    cost = json.loads(out_json.read_text(encoding="utf-8"))["roles"]["orchestrator"]["cost"]
    assert cost["status"] == "MEASURED"
    assert Decimal(cost["delta"]) == Decimal("-0.01269") and Decimal(cost["saving"]) == Decimal("0.01269")
    assert b"saving" in out_md.read_bytes()


def test_cli_not_run_exit_code_and_no_numbers(env):
    proc, out_json, out_md = cli(env, pairs=[])
    assert proc.returncode == 2
    document = json.loads(out_json.read_text(encoding="utf-8"))
    assert document["status"] == "NOT_RUN" and document["roles"] == {}
    assert document["refusals"][0]["code"] == "NO_PAIRED_TASKS"
    assert b"No numbers are shown" in out_md.read_bytes()


def test_cli_unreadable_paired_task_file_has_its_own_code(env):
    proc, out_json, _ = cli(env, pairs_text="{not json")
    assert proc.returncode == 2
    assert json.loads(out_json.read_text(encoding="utf-8"))["refusals"][0]["code"] == "PAIRED_TASKS_UNREADABLE"


def test_cli_unwritable_output_leaves_neither_file(env):
    proc, out_json, _ = cli(env, out_md=env.tmp / "no-such-dir" / "out.md")
    assert proc.returncode == 2 and "OUTPUT_UNWRITABLE" in proc.stdout
    assert not out_json.exists()
    assert sorted(p.name for p in env.tmp.iterdir() if p.name.startswith("out.")) == []
