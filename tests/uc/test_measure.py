"""U1-8: measured effect on paired tasks (tools/uc/measure.py)."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from uc import measure

from tests.uc import ucsupport as S

FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def toks(i, o, cr, cw, messages=1):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw,
            "messages": messages}


def report(**roles):
    return {"status": "MEASURED", "token_fields": list(FIELDS), "roles": roles}


def entry(role, status="PARTIAL", cls="LOCAL_PLUS_MODEL", canonical=None, **over):
    base = dict(role=role, canonical_role=canonical or role, status=status, **{"class": cls})
    if status == "CLEAN":
        base.update(model_residual=[], uncovered=[])
    if status == "FINDINGS":
        base["findings"] = [S.valid_finding()]
    if status in ("MODEL_ONLY",):
        pass
    base.update(over)
    return S.valid_role_entry(**base)


def result(*entries):
    exit_code = 0 if all(e["status"] == "CLEAN" for e in entries) else 3
    return S.valid_result(exit_code=exit_code, roles=list(entries))


def verdict(before, after, *entries, role="python-reviewer"):
    out = measure.compare(before, after, result(*entries))
    assert out["status"] == "MEASURED", out
    return out["roles"][role]


# ------------------------------------------------------------------ LOCAL_FIRST
def test_local_first_when_local_part_ran_and_every_field_shrank():
    v = verdict(report(**{"python-reviewer": toks(1000, 500, 8000, 4000)}),
                report(**{"python-reviewer": toks(100, 50, 800, 400)}), entry("python-reviewer"))
    assert v["verdict"] == "LOCAL_FIRST" and v["local_ran"] is True
    assert v["delta_by_field"] == {"input_tokens": -900, "output_tokens": -450, "cache_read_input_tokens": -7200,
                                   "cache_creation_input_tokens": -3600}


def test_local_first_when_some_fields_equal_and_one_lower():
    v = verdict(report(**{"python-reviewer": toks(10, 10, 10, 10)}), report(**{"python-reviewer": toks(10, 10, 10, 9)}),
                entry("python-reviewer"))
    assert v["verdict"] == "LOCAL_FIRST"


def test_local_class_findings_status_counts_as_ran():
    v = verdict(report(**{"python-reviewer": toks(10, 10, 10, 10)}), report(**{"python-reviewer": toks(5, 5, 5, 5)}),
                entry("python-reviewer", status="FINDINGS"))
    assert v["verdict"] == "LOCAL_FIRST"


def test_local_class_clean_counts_as_ran():
    v = verdict(report(**{"html-report": toks(10, 10, 10, 10)}), report(**{"html-report": toks(0, 0, 0, 0)}),
                entry("html-report", status="CLEAN", cls="LOCAL"), role="html-report")
    assert v["verdict"] == "LOCAL_FIRST"


# ------------------------------------------------------------------ NO_GAIN
@pytest.mark.parametrize("cls,status", [("MODEL_ONLY", "NOT_COVERED"), ("OUT_OF_SCOPE", "NOT_COVERED"),
                                        ("LOCAL_PLUS_MODEL", "NOT_COVERED"), ("LOCAL_PLUS_MODEL", "NOT_RUN"),
                                        ("LOCAL_PLUS_MODEL", "BLOCKED"), ("LOCAL", "BLOCKED"), ("UNKNOWN", "NOT_COVERED")])
def test_no_gain_when_local_part_did_not_run_even_if_tokens_shrank(cls, status):
    v = verdict(report(**{"python-reviewer": toks(100, 100, 100, 100)}), report(**{"python-reviewer": toks(1, 1, 1, 1)}),
                entry("python-reviewer", status=status, cls=cls))
    assert v["verdict"] == "NO_GAIN" and v["local_ran"] is False


@pytest.mark.parametrize("model_only_status", ["PARTIAL"])
def test_model_only_class_is_never_local_first_even_with_ran_status(model_only_status):
    v = verdict(report(**{"python-reviewer": toks(100, 100, 100, 100)}), report(**{"python-reviewer": toks(1, 1, 1, 1)}),
                entry("python-reviewer", status=model_only_status, cls="MODEL_ONLY"))
    assert v["verdict"] == "NO_GAIN"


def test_no_gain_when_tokens_grew():
    v = verdict(report(**{"python-reviewer": toks(10, 10, 10, 10)}), report(**{"python-reviewer": toks(11, 11, 11, 11)}),
                entry("python-reviewer"))
    assert v["verdict"] == "NO_GAIN" and v["delta_by_field"]["input_tokens"] == 1


def test_no_gain_when_tokens_identical():
    v = verdict(report(**{"python-reviewer": toks(10, 10, 10, 10)}), report(**{"python-reviewer": toks(10, 10, 10, 10)}),
                entry("python-reviewer"))
    assert v["verdict"] == "NO_GAIN" and set(v["delta_by_field"].values()) == {0}


# ------------------------------------------------------------------ fields never summed
def test_one_field_up_another_down_is_not_local_first_even_if_the_sum_shrank():
    v = verdict(report(**{"python-reviewer": toks(1000, 10, 10, 10)}), report(**{"python-reviewer": toks(10, 500, 10, 10)}),
                entry("python-reviewer"))  # summed: 1030 -> 530 would look like a gain
    assert v["verdict"] == "NO_GAIN"
    assert v["delta_by_field"]["input_tokens"] == -990 and v["delta_by_field"]["output_tokens"] == 490


def test_cache_read_growth_blocks_gain_despite_input_savings():
    v = verdict(report(**{"python-reviewer": toks(1000, 10, 10, 10)}), report(**{"python-reviewer": toks(1, 10, 11, 10)}),
                entry("python-reviewer"))
    assert v["verdict"] == "NO_GAIN"


def test_verdict_document_contains_no_summed_total():
    out = measure.compare(report(**{"python-reviewer": toks(5, 5, 5, 5)}), report(**{"python-reviewer": toks(1, 1, 1, 1)}),
                          result(entry("python-reviewer")))
    text = json.dumps(out)
    assert "total" not in text and "sum" not in text
    assert set(out["roles"]["python-reviewer"]["delta_by_field"]) == set(FIELDS)


def test_messages_count_is_not_a_token_field():
    v = verdict(report(**{"python-reviewer": toks(10, 10, 10, 10, messages=1)}),
                report(**{"python-reviewer": toks(10, 10, 10, 10, messages=99)}), entry("python-reviewer"))
    assert "messages" not in v["delta_by_field"] and v["verdict"] == "NO_GAIN"


# ------------------------------------------------------------------ NOT_MEASURED
def test_role_missing_from_after_or_before_is_not_measured():
    b, a = report(**{"python-reviewer": toks(10, 10, 10, 10)}), report(**{"other": toks(1, 1, 1, 1)})
    v = verdict(b, a, entry("python-reviewer"))
    assert v["verdict"] == "NOT_MEASURED" and "delta_by_field" not in v
    v = verdict(a, b, entry("python-reviewer"))
    assert v["verdict"] == "NOT_MEASURED"


def test_not_measured_still_reports_whether_local_ran():
    v = verdict(report(), report(), entry("python-reviewer", status="BLOCKED"))
    assert v["verdict"] == "NOT_MEASURED" and v["local_ran"] is False


def test_alias_roles_use_canonical_role_for_the_token_lookup():
    v = verdict(report(**{"architect": toks(10, 10, 10, 10)}), report(**{"architect": toks(1, 1, 1, 1)}),
                entry("code-architect", canonical="architect"), role="architect")
    assert v["verdict"] == "LOCAL_FIRST"


def test_alias_order_does_not_change_the_verdict():
    """tdd-guide and functional-test-reviewer share a canonical role; the verdict must not depend on row order."""
    before = report(**{"functional-test-reviewer": toks(10, 10, 10, 10)})
    after = report(**{"functional-test-reviewer": toks(1, 1, 1, 1)})
    ran = entry("functional-test-reviewer")
    blocked = entry("tdd-guide", status="BLOCKED", canonical="functional-test-reviewer")
    a = measure.compare(before, after, result(ran, blocked))["roles"]["functional-test-reviewer"]
    b = measure.compare(before, after, result(blocked, ran))["roles"]["functional-test-reviewer"]
    assert a["verdict"] == b["verdict"]


# ------------------------------------------------------------------ NOT_RUN
VALID = result(entry("python-reviewer"))


@pytest.mark.parametrize("bad", [None, [], "x", {}, {"status": "NOT_RUN", "reason": "HASH_MISMATCH"},
                                 {"status": "MEASURED"}, {"status": "MEASURED", "roles": []},
                                 {"status": "ESTIMATED", "roles": {}}])
def test_non_measured_before_or_after_is_not_run_without_verdicts(bad):
    good = report(**{"python-reviewer": toks(1, 1, 1, 1)})
    for before, after in ((bad, good), (good, bad)):
        out = measure.compare(before, after, VALID)
        assert out["status"] == "NOT_RUN" and out["roles"] == {} and out["reason"]


def test_invalid_role_result_is_not_run():
    good = report(**{"python-reviewer": toks(1, 1, 1, 1)})
    broken = dict(VALID, exit_code=0)  # exit 0 with open items violates the contract
    for doc in (broken, {"schema_version": "x"}, None, "str"):
        out = measure.compare(good, good, doc)
        assert out["status"] == "NOT_RUN" and out["roles"] == {}


def test_not_run_reason_is_bounded():
    out = measure.compare(None, None, None)
    assert len(out["reason"]) <= 200


@pytest.mark.parametrize("bad", ["abc", None, -5, 1.5, True])
def test_malformed_token_value_does_not_crash_or_claim_a_gain(bad):
    before = report(**{"python-reviewer": toks(10, 10, 10, 10)})
    after = report(**{"python-reviewer": dict(toks(5, 5, 5, 5), cache_read_input_tokens=bad)})
    try:
        out = measure.compare(before, after, VALID)
    except (ValueError, TypeError) as exc:
        pytest.fail(f"compare crashed on a malformed token value {bad!r}: {exc!r}")
    if out["status"] == "MEASURED":
        assert out["roles"]["python-reviewer"]["verdict"] != "LOCAL_FIRST"


def test_missing_token_field_in_after_report_is_not_a_saving():
    before = report(**{"python-reviewer": toks(10, 10, 10, 10)})
    partial = {"input_tokens": 5, "output_tokens": 5, "cache_read_input_tokens": 5}  # cache_creation absent
    out = measure.compare(before, report(**{"python-reviewer": partial}), VALID)
    if out["status"] == "MEASURED":
        v = out["roles"]["python-reviewer"]
        assert v["verdict"] != "LOCAL_FIRST", "a field that was not measured must not count as zero tokens"


# ------------------------------------------------------------------ CLI
def run_cli(tmp_path, before, after, res):
    paths = []
    for name, doc in (("b", before), ("a", after), ("r", res)):
        p = tmp_path / f"{name}.json"
        if isinstance(doc, str):
            p.write_text(doc, encoding="utf-8")
        elif doc is not None:
            p.write_text(json.dumps(doc), encoding="utf-8")
        paths.append(p)
    return subprocess.run([sys.executable, "-I", str(pathlib.Path(measure.__file__)), "compare", "--before", str(paths[0]),
                           "--after", str(paths[1]), "--result", str(paths[2])], capture_output=True, text=True, timeout=60)


def test_cli_measured_exit_zero(tmp_path):
    res = run_cli(tmp_path, report(**{"python-reviewer": toks(10, 10, 10, 10)}),
                  report(**{"python-reviewer": toks(1, 1, 1, 1)}), VALID)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["roles"]["python-reviewer"]["verdict"] == "LOCAL_FIRST"


def test_cli_not_run_exit_two(tmp_path):
    res = run_cli(tmp_path, {"status": "NOT_RUN"}, report(), VALID)
    assert res.returncode == 2 and json.loads(res.stdout)["status"] == "NOT_RUN"


def test_cli_missing_and_unparsable_inputs_are_not_run(tmp_path):
    res = run_cli(tmp_path, report(), report(), None)
    assert res.returncode == 2 and json.loads(res.stdout)["status"] == "NOT_RUN"
    res = run_cli(tmp_path, "{oops", report(), VALID)
    assert res.returncode == 2 and json.loads(res.stdout)["status"] == "NOT_RUN"


# ------------------------------------------------------------------ behaviour 6: COMPLETE executor required, no BLOCKED one
SHRUNK = (report(**{"python-reviewer": toks(100, 100, 100, 100)}), report(**{"python-reviewer": toks(1, 1, 1, 1)}))


def ex(status, ident="g2.python-rules"):
    return {"id": ident, "status": status, "snapshot_hash": S.HASH_A}


@pytest.mark.parametrize("statuses", [["PARTIAL"], ["NOT_RUN"], ["NOT_COVERED"], ["PARTIAL", "NOT_RUN"], []])
def test_no_gain_without_any_complete_executor(statuses):
    executors = [ex(s, f"g2.x{i}") for i, s in enumerate(statuses)]
    v = verdict(*SHRUNK, entry("python-reviewer", status="PARTIAL", executors=executors))
    assert v["verdict"] == "NO_GAIN" and v["local_ran"] is False


@pytest.mark.parametrize("other", ["BLOCKED"])
def test_no_gain_when_one_executor_is_blocked_even_if_another_completed(other):
    executors = [ex("COMPLETE", "g2.a"), ex(other, "g2.b")]
    v = verdict(*SHRUNK, entry("python-reviewer", status="PARTIAL", executors=executors))
    assert v["verdict"] == "NO_GAIN" and v["local_ran"] is False


def test_local_first_with_complete_and_partial_executors_and_no_blocked_one():
    executors = [ex("COMPLETE", "g2.a"), ex("PARTIAL", "g2.b"), ex("NOT_RUN", "g2.c")]
    v = verdict(*SHRUNK, entry("python-reviewer", status="PARTIAL", executors=executors))
    assert v["verdict"] == "LOCAL_FIRST" and v["local_ran"] is True


def test_blocked_executor_with_findings_role_status_partial_is_not_local_first():
    executors = [ex("COMPLETE", "g2.a"), ex("BLOCKED", "g2.b")]
    v = verdict(*SHRUNK, entry("python-reviewer", status="FINDINGS", executors=executors))
    assert v["verdict"] == "NO_GAIN"
