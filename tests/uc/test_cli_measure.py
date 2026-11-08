"""U1-8 command line: real subprocess runs of `python tools/uc/measure.py compare`."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from tests.uc import ucsupport as S

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "tools" / "uc" / "measure.py"
FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def toks(i, o, cr, cw):
    return dict(zip(FIELDS, (i, o, cr, cw)), messages=1)


def report(**roles):
    return {"status": "MEASURED", "token_fields": list(FIELDS), "roles": roles}


RESULT = S.valid_result(roles=[S.valid_role_entry(role="python-reviewer", canonical_role="python-reviewer", status="PARTIAL"),
                               S.valid_role_entry(role="business-analyst", canonical_role="business-analyst",
                                                  **{"class": "MODEL_ONLY"}, status="NOT_COVERED", executors=[],
                                                  model_residual=["authoring"], uncovered=["model-only"])])
BEFORE = report(**{"python-reviewer": toks(1000, 500, 8000, 4000), "business-analyst": toks(100, 100, 100, 100)})
AFTER = report(**{"python-reviewer": toks(100, 50, 800, 400), "business-analyst": toks(100, 100, 100, 100)})


def write(path, doc):
    if isinstance(doc, bytes):
        path.write_bytes(doc)
    elif isinstance(doc, str):
        path.write_text(doc, encoding="utf-8")
    elif doc is not None:
        path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def run(tmp_path, before=BEFORE, after=AFTER, result=RESULT):
    paths = [write(tmp_path / n, d) for n, d in (("before.json", before), ("after.json", after), ("result.json", result))]
    res = subprocess.run([sys.executable, "-I", str(SCRIPT), "compare", "--before", str(paths[0]), "--after", str(paths[1]),
                          "--result", str(paths[2])], capture_output=True, text=True, timeout=60)
    assert "Traceback" not in res.stderr, f"CLI crashed with a traceback:\n{res.stderr[-800:]}"
    return res


def doc_of(res):
    return json.loads(res.stdout)


# ------------------------------------------------------------------ valid
def test_valid_compare_exit_zero_with_per_role_verdicts(tmp_path):
    res = run(tmp_path)
    assert res.returncode == 0, res.stderr
    doc = doc_of(res)
    assert doc["status"] == "MEASURED"
    assert doc["roles"]["python-reviewer"] == {
        "verdict": "LOCAL_FIRST", "local_ran": True,
        "delta_by_field": {"input_tokens": -900, "output_tokens": -450, "cache_read_input_tokens": -7200,
                           "cache_creation_input_tokens": -3600}}
    assert doc["roles"]["business-analyst"]["verdict"] == "NO_GAIN" and doc["roles"]["business-analyst"]["local_ran"] is False


def test_valid_compare_no_gain_still_exit_zero(tmp_path):
    grown = report(**{"python-reviewer": toks(2000, 500, 8000, 4000), "business-analyst": toks(100, 100, 100, 100)})
    res = run(tmp_path, after=grown)
    assert res.returncode == 0 and doc_of(res)["roles"]["python-reviewer"]["verdict"] == "NO_GAIN"


def test_role_missing_from_a_report_is_not_measured_with_exit_zero(tmp_path):
    res = run(tmp_path, after=report(**{"business-analyst": toks(100, 100, 100, 100)}))
    assert res.returncode == 0
    assert doc_of(res)["roles"]["python-reviewer"]["verdict"] == "NOT_MEASURED"


# ------------------------------------------------------------------ malformed token values
@pytest.mark.parametrize("bad", ["abc", None, -5, 1.5, True, [3], {"x": 1}])
def test_malformed_token_value_is_not_measured_not_a_crash(tmp_path, bad):
    after = report(**{"python-reviewer": dict(toks(100, 50, 800, 400), cache_read_input_tokens=bad),
                      "business-analyst": toks(100, 100, 100, 100)})
    res = run(tmp_path, after=after)
    assert res.returncode == 0, res.stderr
    verdict = doc_of(res)["roles"]["python-reviewer"]
    assert verdict["verdict"] == "NOT_MEASURED" and "cache_read_input_tokens" in verdict["reason"]


def test_missing_token_field_is_not_measured(tmp_path):
    partial = {k: v for k, v in toks(100, 50, 800, 400).items() if k != "cache_creation_input_tokens"}
    res = run(tmp_path, after=report(**{"python-reviewer": partial, "business-analyst": toks(100, 100, 100, 100)}))
    assert res.returncode == 0 and doc_of(res)["roles"]["python-reviewer"]["verdict"] == "NOT_MEASURED"


# ------------------------------------------------------------------ NOT_RUN
@pytest.mark.parametrize("bad", [{"status": "NOT_RUN", "reason": "HASH_MISMATCH"}, {"status": "ESTIMATED", "roles": {}},
                                 {"status": "MEASURED"}, {"status": "MEASURED", "roles": []}, [], None, "text", 5])
@pytest.mark.parametrize("which", ["before", "after"])
def test_non_measured_report_is_not_run_exit_two(tmp_path, bad, which):
    res = run(tmp_path, **{which: bad})
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN" and doc["roles"] == {} and doc["reason"]


@pytest.mark.parametrize("bad", [
    {"schema_version": "uc.role-result.v1"}, [], None, "x",
    dict(RESULT, exit_code=0),                       # exit 0 with open items
    dict(RESULT, extra="field"),                     # unknown field
    dict(RESULT, roles=[]),
], ids=["incomplete", "list", "null", "string", "exit-zero-open-items", "unknown-field", "no-roles"])
def test_invalid_role_result_is_not_run_exit_two(tmp_path, bad):
    res = run(tmp_path, result=bad)
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN" and doc["roles"] == {}


@pytest.mark.parametrize("which", ["before", "after", "result"])
@pytest.mark.parametrize("content", [b"{oops", b"", b"\xff\xfe\x00", b"\xef\xbb\xbf{}"], ids=["syntax", "empty", "binary", "bom"])
def test_unreadable_or_unparsable_file_is_not_run_exit_two(tmp_path, which, content):
    res = run(tmp_path, **{which: content})
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN" and doc["roles"] == {}
    assert doc["reason"].startswith("unreadable input")


@pytest.mark.parametrize("which", ["before", "after", "result"])
def test_missing_file_is_not_run_exit_two(tmp_path, which):
    res = run(tmp_path, **{which: None})
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN" and "unreadable input" in doc["reason"]


def test_directory_instead_of_file_is_not_run_exit_two(tmp_path):
    (tmp_path / "before.json").mkdir()
    after, result = write(tmp_path / "after.json", AFTER), write(tmp_path / "result.json", RESULT)
    res = subprocess.run([sys.executable, "-I", str(SCRIPT), "compare", "--before", str(tmp_path / "before.json"),
                          "--after", str(after), "--result", str(result)], capture_output=True, text=True, timeout=60)
    assert "Traceback" not in res.stderr
    assert res.returncode == 2 and json.loads(res.stdout)["status"] == "NOT_RUN"


def test_missing_required_flag_and_no_subcommand_are_argparse_errors(tmp_path):
    for argv in (["compare", "--before", "x"], []):
        res = subprocess.run([sys.executable, "-I", str(SCRIPT), *argv], capture_output=True, text=True, timeout=60)
        assert res.returncode == 2 and res.stdout == ""


def test_not_run_never_contains_verdicts_and_stdout_is_single_json(tmp_path):
    res = run(tmp_path, before={"status": "NOT_RUN"})
    assert res.stderr == ""
    assert doc_of(res)["roles"] == {}
