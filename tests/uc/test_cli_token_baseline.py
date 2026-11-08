"""U1-1 command line: real subprocess runs of `python tools/uc/token_baseline.py build-manifest|report`.

Library functions are covered in test_token_baseline.py; these tests exist because a broken main() can pass every
library test.  No AEVE, no network.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "tools" / "uc" / "token_baseline.py"
FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
NL = chr(10)
BACKSLASH = chr(92)


def run(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True, timeout=60)


def doc_of(res):
    """stdout must be exactly one JSON document; a traceback on stderr is a contract failure."""
    assert "Traceback" not in res.stderr, f"CLI crashed with a traceback:{NL}{res.stderr[-800:]}"
    return json.loads(res.stdout)


def usage(i, o, cr, cw):
    return dict(zip(FIELDS, (i, o, cr, cw)))


def line(mid, u):
    return json.dumps({"type": "assistant", "message": {"id": mid, "usage": u}})


@pytest.fixture()
def project(tmp_path):
    d = tmp_path / "proj"
    (d / "s1" / "subagents").mkdir(parents=True)
    (d / "s1.jsonl").write_text(NL.join([line("m1", usage(1, 1, 1, 1)), line("m1", usage(10, 20, 300, 4000)),
                                         line("m2", usage(5, 6, 7, 8))]) + NL, encoding="utf-8")
    (d / "s1" / "subagents" / "agent-a1.jsonl").write_text(line("m3", usage(100, 200, 3000, 40000)) + NL, encoding="utf-8")
    (d / "s1" / "subagents" / "agent-a1.meta.json").write_text(json.dumps({"agentType": "python-reviewer"}), encoding="utf-8")
    (d / "s2.jsonl").write_text(line("n1", usage(2, 2, 2, 2)) + NL, encoding="utf-8")
    return d


def build(project, tmp_path, sessions="s1"):
    out = tmp_path / "manifest.json"
    res = run("build-manifest", "--project-dir", project, "--sessions", sessions, "--out", out)
    return res, out


# ------------------------------------------------------------------ build-manifest
def test_build_manifest_valid_run(project, tmp_path):
    res, out = build(project, tmp_path)
    assert res.returncode == 0, res.stderr
    assert doc_of(res) == {"status": "WRITTEN", "sessions": 1, "out": str(out)}
    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert [f["path"] for f in manifest["sessions"][0]["files"]] == [
        "s1.jsonl", "s1/subagents/agent-a1.jsonl", "s1/subagents/agent-a1.meta.json"]
    assert manifest["token_fields"] == list(FIELDS)


def test_build_manifest_two_sessions_and_whitespace_in_list(project, tmp_path):
    res, out = build(project, tmp_path, sessions=" s1 , s2 ,")
    assert res.returncode == 0 and doc_of(res)["sessions"] == 2
    assert [s["session_id"] for s in json.loads(out.read_text(encoding="utf-8"))["sessions"]] == ["s1", "s2"]


@pytest.mark.parametrize("sessions", ["", " ", ",,"])
def test_build_manifest_empty_session_set_is_not_run(project, tmp_path, sessions):
    res, out = build(project, tmp_path, sessions=sessions)
    assert res.returncode == 2
    assert doc_of(res) == {"status": "NOT_RUN", "reason": "EMPTY_SESSION_SET", "detail": ""}
    assert not out.exists()


def test_build_manifest_unknown_session_is_not_run_and_writes_nothing(project, tmp_path):
    res, out = build(project, tmp_path, sessions="s1,ghost")
    assert res.returncode == 2
    doc = doc_of(res)
    assert doc["status"] == "NOT_RUN" and doc["reason"] == "SESSION_MISSING" and doc["detail"] == "ghost"
    assert not out.exists()


def test_build_manifest_missing_project_dir_is_not_run(tmp_path):
    res, out = build(tmp_path / "no-such-dir", tmp_path)
    assert res.returncode == 2 and doc_of(res)["reason"] == "SESSION_MISSING"


def test_build_manifest_session_id_outside_the_project_is_refused(project, tmp_path):
    (tmp_path / "outside.jsonl").write_text(line("m", usage(1, 1, 1, 1)) + NL, encoding="utf-8")
    res, out = build(project, tmp_path, sessions="../outside")
    doc = doc_of(res)  # asserts no traceback
    assert res.returncode == 2 and doc["status"] == "NOT_RUN" and doc["reason"] == "BAD_SESSION_ID"
    assert not out.exists()


@pytest.mark.parametrize("session", ["..", "a/b", "a" + BACKSLASH + "b", ".hidden", "a b", "x" * 129, "C:evil"])
def test_build_manifest_bad_session_ids_are_refused(project, tmp_path, session):
    res, out = build(project, tmp_path, sessions=session)
    assert res.returncode == 2 and doc_of(res)["reason"] == "BAD_SESSION_ID"
    assert not out.exists()


def test_build_manifest_session_id_starting_with_dash_is_refused(project, tmp_path):
    out = tmp_path / "manifest.json"
    res = run("build-manifest", "--project-dir", project, "--sessions=-x", "--out", out)
    assert res.returncode == 2 and doc_of(res)["reason"] == "BAD_SESSION_ID" and not out.exists()


def test_build_manifest_good_session_id_boundaries(project, tmp_path):
    (project / ("a" * 128 + ".jsonl")).write_text(line("m", usage(1, 1, 1, 1)) + NL, encoding="utf-8")
    (project / "_x.y-z.jsonl").write_text(line("m", usage(1, 1, 1, 1)) + NL, encoding="utf-8")
    res, _ = build(project, tmp_path, sessions="a" * 128 + ",_x.y-z")
    assert res.returncode == 0 and doc_of(res)["sessions"] == 2


def test_build_manifest_unwritable_output_is_not_a_traceback(project, tmp_path):
    res = run("build-manifest", "--project-dir", project, "--sessions", "s1", "--out", tmp_path / "missing-dir" / "m.json")
    doc = doc_of(res)  # asserts no traceback
    assert res.returncode == 2 and doc["status"] == "NOT_RUN" and doc["reason"] == "OUTPUT_UNWRITABLE"


def test_build_manifest_output_path_is_a_directory_is_unwritable(project, tmp_path):
    target = tmp_path / "is-a-dir"
    target.mkdir()
    res = run("build-manifest", "--project-dir", project, "--sessions", "s1", "--out", target)
    assert res.returncode == 2 and doc_of(res)["reason"] == "OUTPUT_UNWRITABLE"


def test_build_manifest_missing_required_argument_is_an_argparse_error(project, tmp_path):
    res = run("build-manifest", "--project-dir", project)
    assert res.returncode == 2 and "required" in res.stderr and res.stdout == ""


def test_unknown_subcommand_and_no_subcommand_are_argparse_errors():
    assert run("frobnicate").returncode == 2
    assert run().returncode == 2


# ------------------------------------------------------------------ report
def test_report_valid_run_hand_computed_totals(project, tmp_path):
    _, manifest = build(project, tmp_path)
    res = run("report", "--manifest", manifest, "--project-dir", project)
    assert res.returncode == 0, res.stderr
    doc = doc_of(res)
    assert doc["status"] == "MEASURED" and doc["token_fields"] == list(FIELDS)
    assert doc["roles"] == {
        "orchestrator": {"input_tokens": 15, "output_tokens": 26, "cache_read_input_tokens": 307,
                         "cache_creation_input_tokens": 4008, "messages": 2},
        "python-reviewer": {"input_tokens": 100, "output_tokens": 200, "cache_read_input_tokens": 3000,
                            "cache_creation_input_tokens": 40000, "messages": 1},
    }


def test_report_hash_mismatch_is_not_run_without_numbers(project, tmp_path):
    _, manifest = build(project, tmp_path)
    (project / "s1.jsonl").write_text(line("m9", usage(9, 9, 9, 9)) + NL, encoding="utf-8")
    res = run("report", "--manifest", manifest, "--project-dir", project)
    doc = doc_of(res)
    assert res.returncode == 2
    assert doc["status"] == "NOT_RUN" and doc["reason"] == "HASH_MISMATCH" and doc["detail"] == "s1.jsonl"
    assert "roles" not in doc


def test_report_missing_file_is_not_run(project, tmp_path):
    _, manifest = build(project, tmp_path)
    (project / "s1" / "subagents" / "agent-a1.jsonl").unlink()
    res = run("report", "--manifest", manifest, "--project-dir", project)
    assert res.returncode == 2 and doc_of(res)["reason"] == "FILE_MISSING"


def test_report_wrong_project_dir_is_not_run(project, tmp_path):
    _, manifest = build(project, tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    res = run("report", "--manifest", manifest, "--project-dir", empty)
    assert res.returncode == 2 and doc_of(res)["reason"] == "FILE_MISSING"


def test_report_empty_transcript_has_no_usage_not_run(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    (d / "e.jsonl").write_text("", encoding="utf-8")
    _, manifest = build(d, tmp_path, sessions="e")
    res = run("report", "--manifest", manifest, "--project-dir", d)
    assert res.returncode == 2 and doc_of(res)["reason"] == "NO_USAGE_FOUND"


def test_report_empty_session_set_in_manifest_is_not_run(project, tmp_path):
    _, manifest = build(project, tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["sessions"] = []
    manifest.write_text(json.dumps(data), encoding="utf-8")
    res = run("report", "--manifest", manifest, "--project-dir", project)
    assert res.returncode == 2 and doc_of(res)["reason"] == "EMPTY_SESSION_SET"


def test_report_changed_rules_is_not_run(project, tmp_path):
    _, manifest = build(project, tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["attribution_rule"] = "all tokens belong to the orchestrator"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    res = run("report", "--manifest", manifest, "--project-dir", project)
    assert res.returncode == 2 and doc_of(res)["reason"] == "MANIFEST_RULES_CHANGED"


@pytest.mark.parametrize("content", [b"{oops", b"", b"\xff\xfe\x00junk", b"\xef\xbb\xbf{\"version\": 1}"])
def test_report_unreadable_manifest_is_not_run(project, tmp_path, content):
    bad = tmp_path / "bad.json"
    bad.write_bytes(content)
    res = run("report", "--manifest", bad, "--project-dir", project)
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN"
    assert doc["reason"] in ("MANIFEST_UNREADABLE", "MANIFEST_INVALID")


def test_report_missing_manifest_file_is_not_run(project, tmp_path):
    res = run("report", "--manifest", tmp_path / "nope.json", "--project-dir", project)
    assert res.returncode == 2 and doc_of(res)["reason"] == "MANIFEST_UNREADABLE"


@pytest.mark.parametrize("payload", ["[]", "null", "5", '"text"', "{}", '{"version": 1}'])
def test_report_manifest_of_the_wrong_shape_is_not_run_not_a_crash(project, tmp_path, payload):
    bad = tmp_path / "shape.json"
    bad.write_text(payload, encoding="utf-8")
    res = run("report", "--manifest", bad, "--project-dir", project)
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN"


@pytest.mark.parametrize("mutation", [
    lambda m: m["sessions"].__setitem__(0, "s1"),
    lambda m: m["sessions"][0].__setitem__("files", ["s1.jsonl"]),
    lambda m: m["sessions"][0]["files"][0].pop("sha256"),
    lambda m: m["sessions"][0]["files"][0].__setitem__("path", "../../escape.jsonl"),
    lambda m: m["sessions"][0]["files"][0].__setitem__("path", None),
], ids=["session-not-object", "file-not-object", "no-sha", "path-escape", "path-null"])
def test_report_tampered_manifest_structure_is_not_run_not_a_crash(project, tmp_path, mutation):
    _, manifest = build(project, tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    mutation(data)
    manifest.write_text(json.dumps(data), encoding="utf-8")
    res = run("report", "--manifest", manifest, "--project-dir", project)
    doc = doc_of(res)
    assert res.returncode == 2 and doc["status"] == "NOT_RUN"


def test_report_output_is_valid_json_only_on_stdout(project, tmp_path):
    _, manifest = build(project, tmp_path)
    res = run("report", "--manifest", manifest, "--project-dir", project)
    assert res.stderr == ""
    json.loads(res.stdout)
