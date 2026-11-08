"""U1-1: token baseline manifest, hashing, NOT_RUN rules, dedupe and role attribution."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from uc import token_baseline as tb

FIELDS = tb.TOKEN_FIELDS


def usage(i, o, cr, cw):
    return {"input_tokens": i, "output_tokens": o, "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw}


def line(message_id, u, **extra):
    rec = {"type": "assistant", "message": {"id": message_id, "usage": u}}
    rec.update(extra)
    return json.dumps(rec)


def write_lines(path: pathlib.Path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture()
def project(tmp_path):
    """Session s1: orchestrator m1 (streamed twice) + m2; sub-agents reviewer (m3) and an unattributed one (m4)."""
    d = tmp_path / "proj"
    write_lines(d / "s1.jsonl", [
        line("m1", usage(1, 1, 1, 1)),                     # superseded by the later line of the same message
        line("m1", usage(10, 20, 300, 4000)),              # last usage of m1
        line("m2", usage(5, 6, 7, 8)),
        json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}),   # no usage
        json.dumps([1, 2]),                                                             # not an object: ignored
    ])
    write_lines(d / "s1" / "subagents" / "agent-a1.jsonl", [line("m3", usage(100, 200, 3000, 40000))])
    (d / "s1" / "subagents" / "agent-a1.meta.json").write_text(json.dumps({"agentType": "python-reviewer"}), encoding="utf-8")
    write_lines(d / "s1" / "subagents" / "agent-a2.jsonl", [line("m4", usage(1, 2, 3, 4))])
    return d


# ------------------------------------------------------------------ manifest
def test_build_manifest_pins_every_file_with_hash_and_size(project):
    manifest = tb.build_manifest(project, ["s1"])
    paths = [f["path"] for f in manifest["sessions"][0]["files"]]
    assert paths == ["s1.jsonl", "s1/subagents/agent-a1.jsonl", "s1/subagents/agent-a1.meta.json",
                     "s1/subagents/agent-a2.jsonl"]
    for entry in manifest["sessions"][0]["files"]:
        assert entry["sha256"] == tb.sha256_file(project / entry["path"])
        assert entry["bytes"] == (project / entry["path"]).stat().st_size
    assert manifest["token_fields"] == list(FIELDS)
    assert manifest["attribution_rule"] == tb.ATTRIBUTION_RULE
    assert manifest["version"] == tb.MANIFEST_VERSION


def test_manifest_is_deterministic(project):
    assert tb.build_manifest(project, ["s1"]) == tb.build_manifest(project, ["s1"])


def test_sha256_file_known_value(tmp_path):
    p = tmp_path / "x"
    p.write_bytes(b"abc")
    assert tb.sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_build_manifest_missing_session_is_not_run(project):
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.build_manifest(project, ["s1", "nope"])
    assert info.value.reason == "SESSION_MISSING"


def test_build_manifest_empty_session_set_is_not_run(project):
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.build_manifest(project, [])
    assert info.value.reason == "EMPTY_SESSION_SET"


def test_session_without_subagents_dir(tmp_path):
    write_lines(tmp_path / "solo.jsonl", [line("m1", usage(1, 2, 3, 4))])
    report = tb.compute(tb.build_manifest(tmp_path, ["solo"]), tmp_path)
    assert report["roles"] == {"orchestrator": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3,
                                                "cache_creation_input_tokens": 4, "messages": 1}}


# ------------------------------------------------------------------ computation
def test_compute_hand_computed_totals_by_role(project):
    report = tb.compute(tb.build_manifest(project, ["s1"]), project)
    assert report["status"] == "MEASURED"
    assert report["token_fields"] == list(FIELDS)
    roles = report["roles"]
    assert sorted(roles) == ["orchestrator", "python-reviewer", "unknown-subagent"]
    # m1 counted ONCE with its last usage (10,20,300,4000) + m2 (5,6,7,8)
    assert roles["orchestrator"] == {"input_tokens": 15, "output_tokens": 26, "cache_read_input_tokens": 307,
                                     "cache_creation_input_tokens": 4008, "messages": 2}
    assert roles["python-reviewer"] == {"input_tokens": 100, "output_tokens": 200, "cache_read_input_tokens": 3000,
                                        "cache_creation_input_tokens": 40000, "messages": 1}
    # meta file missing -> never guessed from the file name
    assert roles["unknown-subagent"] == {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3,
                                         "cache_creation_input_tokens": 4, "messages": 1}


def test_four_fields_stay_separate_no_combined_total(project):
    report = tb.compute(tb.build_manifest(project, ["s1"]), project)
    for bucket in report["roles"].values():
        assert set(bucket) == set(FIELDS) | {"messages"}
    assert "total" not in json.dumps(report).lower().replace("total_", "")


def test_message_deduped_across_lines_uses_last_usage_not_max_or_first(tmp_path):
    write_lines(tmp_path / "d.jsonl", [line("m1", usage(50, 50, 50, 50)), line("m1", usage(7, 7, 7, 7))])
    roles = tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)["roles"]
    assert roles["orchestrator"]["input_tokens"] == 7 and roles["orchestrator"]["messages"] == 1


def test_same_message_id_in_two_roles_counts_in_each_role(tmp_path):
    write_lines(tmp_path / "d.jsonl", [line("m1", usage(1, 1, 1, 1))])
    write_lines(tmp_path / "d" / "subagents" / "agent-x.jsonl", [line("m1", usage(2, 2, 2, 2))])
    (tmp_path / "d" / "subagents" / "agent-x.meta.json").write_text(json.dumps({"agentType": "tdd-guide"}))
    roles = tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)["roles"]
    assert roles["orchestrator"]["input_tokens"] == 1 and roles["tdd-guide"]["input_tokens"] == 2


def test_two_subagents_with_same_type_are_summed(tmp_path):
    write_lines(tmp_path / "d.jsonl", [line("m0", usage(1, 0, 0, 0))])
    for n in ("a", "b"):
        write_lines(tmp_path / "d" / "subagents" / f"agent-{n}.jsonl", [line(f"m-{n}", usage(10, 0, 0, 0))])
        (tmp_path / "d" / "subagents" / f"agent-{n}.meta.json").write_text(json.dumps({"agentType": "architect"}))
    roles = tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)["roles"]
    assert roles["architect"]["input_tokens"] == 20 and roles["architect"]["messages"] == 2


@pytest.mark.parametrize("meta", ["{not json", json.dumps({"agentType": ""}), json.dumps({"agentType": 5}),
                                  json.dumps(["agentType"]), json.dumps({})])
def test_unreadable_or_malformed_meta_falls_back_to_unknown_subagent(tmp_path, meta):
    write_lines(tmp_path / "d.jsonl", [line("m0", usage(1, 0, 0, 0))])
    write_lines(tmp_path / "d" / "subagents" / "agent-z.jsonl", [line("mz", usage(3, 0, 0, 0))])
    (tmp_path / "d" / "subagents" / "agent-z.meta.json").write_text(meta)
    roles = tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)["roles"]
    assert roles["unknown-subagent"]["input_tokens"] == 3


def damaged(tmp_path, lines, **counts):
    write_lines(tmp_path / "d.jsonl", lines)
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)
    assert info.value.reason == "DAMAGED_RECORDS"
    defects = json.loads(info.value.detail)
    expected = {"unparsable_lines": 0, "usage_without_id": 0, "usage_missing_fields": 0, **counts}
    assert defects == expected


def test_clean_transcript_with_ignorable_records_is_still_measured(tmp_path):
    write_lines(tmp_path / "d.jsonl", [json.dumps({"type": "user", "message": {"content": "x"}}), json.dumps([1]),
                                       "", line("m1", usage(1, 2, 3, 4))])
    assert tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)["status"] == "MEASURED"


def test_unparsable_line_makes_baseline_not_run_even_with_good_usage_elsewhere(tmp_path):
    damaged(tmp_path, [line("m1", usage(1, 1, 1, 1)), "not json at all"], unparsable_lines=1)


def test_usage_block_without_message_id_makes_baseline_not_run(tmp_path):
    damaged(tmp_path, [line("m1", usage(1, 1, 1, 1)), json.dumps({"message": {"usage": usage(99, 99, 99, 99)}})],
            usage_without_id=1)


def test_usage_not_dict_or_id_not_string_makes_baseline_not_run(tmp_path):
    damaged(tmp_path, [json.dumps({"message": {"id": "m1", "usage": "lots"}}),
                       json.dumps({"message": {"id": 7, "usage": usage(1, 1, 1, 1)}}), line("m9", usage(2, 0, 0, 0))],
            usage_without_id=2)


@pytest.mark.parametrize("bad", [-5, True, "7", 1.5, None])
def test_invalid_token_value_makes_baseline_not_run(tmp_path, bad):
    damaged(tmp_path, [line("m1", usage(bad, 4, 0, 0))], usage_missing_fields=1)


@pytest.mark.parametrize("field", list(FIELDS))
def test_each_missing_token_field_makes_baseline_not_run(tmp_path, field):
    u = usage(1, 1, 1, 1)
    del u[field]
    damaged(tmp_path, [line("m1", u)], usage_missing_fields=1)


def test_damage_in_a_subagent_transcript_also_makes_baseline_not_run(project):
    with (project / "s1" / "subagents" / "agent-a2.jsonl").open("a", encoding="utf-8") as h:
        h.write("garbage" + chr(10))
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(tb.build_manifest(project, ["s1"]), project)
    assert info.value.reason == "DAMAGED_RECORDS"


def test_zero_tokens_are_valid_not_damaged(tmp_path):
    write_lines(tmp_path / "d.jsonl", [line("m1", usage(0, 0, 0, 0))])
    assert tb.compute(tb.build_manifest(tmp_path, ["d"]), tmp_path)["roles"]["orchestrator"]["messages"] == 1


def test_two_sessions_are_summed(tmp_path):
    write_lines(tmp_path / "a.jsonl", [line("m1", usage(1, 0, 0, 0))])
    write_lines(tmp_path / "b.jsonl", [line("m1", usage(2, 0, 0, 0))])
    roles = tb.compute(tb.build_manifest(tmp_path, ["a", "b"]), tmp_path)["roles"]
    assert roles["orchestrator"]["input_tokens"] == 3 and roles["orchestrator"]["messages"] == 2


# ------------------------------------------------------------------ NOT_RUN rules
def test_hash_mismatch_is_not_run_no_numbers(project):
    manifest = tb.build_manifest(project, ["s1"])
    with (project / "s1.jsonl").open("a", encoding="utf-8") as h:
        h.write(line("m77", usage(1, 1, 1, 1)) + "\n")
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, project)
    assert info.value.reason == "HASH_MISMATCH"


def test_meta_file_change_is_also_detected(project):
    manifest = tb.build_manifest(project, ["s1"])
    (project / "s1" / "subagents" / "agent-a1.meta.json").write_text(json.dumps({"agentType": "architect"}))
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, project)
    assert info.value.reason == "HASH_MISMATCH"


def test_missing_file_is_not_run(project):
    manifest = tb.build_manifest(project, ["s1"])
    (project / "s1" / "subagents" / "agent-a2.jsonl").unlink()
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, project)
    assert info.value.reason == "FILE_MISSING"


def test_empty_transcripts_without_usage_is_not_run(tmp_path):
    (tmp_path / "e.jsonl").write_text("", encoding="utf-8")
    manifest = tb.build_manifest(tmp_path, ["e"])
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, tmp_path)
    assert info.value.reason == "NO_USAGE_FOUND"


def test_empty_session_set_manifest_is_not_run(project):
    manifest = tb.build_manifest(project, ["s1"])
    manifest["sessions"] = []
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, project)
    assert info.value.reason == "EMPTY_SESSION_SET"


def test_session_without_files_is_not_run(project):
    manifest = tb.build_manifest(project, ["s1"])
    manifest["sessions"][0]["files"] = []
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, project)
    assert info.value.reason == "MANIFEST_INVALID"


@pytest.mark.parametrize("bad", [None, [], "x", {"version": 2}, {}])
def test_invalid_manifest_is_not_run(project, bad):
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(bad, project)
    assert info.value.reason == "MANIFEST_INVALID"


def test_changed_rules_is_not_run(project):
    for key, value in (("attribution_rule", "everything is the orchestrator"), ("token_fields", ["input_tokens"])):
        manifest = tb.build_manifest(project, ["s1"])
        manifest[key] = value
        with pytest.raises(tb.BaselineNotRun) as info:
            tb.compute(manifest, project)
        assert info.value.reason == "MANIFEST_RULES_CHANGED"


def test_manifest_path_traversal_outside_project_is_refused(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    outside = tmp_path / "outside.jsonl"
    write_lines(outside, [line("m1", usage(1, 1, 1, 1))])
    write_lines(proj / "ok.jsonl", [line("m2", usage(1, 1, 1, 1))])
    manifest = tb.build_manifest(proj, ["ok"])
    manifest["sessions"][0]["files"][0] = {"path": "../outside.jsonl", "sha256": tb.sha256_file(outside), "bytes": 1}
    with pytest.raises(tb.BaselineNotRun) as info:
        tb.compute(manifest, proj)
    assert info.value.reason == "PATH_OUTSIDE_PROJECT"


def test_manifest_entry_that_is_not_an_object_is_not_run_not_a_crash(project):
    manifest = tb.build_manifest(project, ["s1"])
    manifest["sessions"][0]["files"][0] = "s1.jsonl"
    with pytest.raises(tb.BaselineNotRun):
        tb.compute(manifest, project)


def test_session_entry_that_is_not_an_object_is_not_run(project):
    manifest = tb.build_manifest(project, ["s1"])
    manifest["sessions"] = ["s1"]
    with pytest.raises(tb.BaselineNotRun):
        tb.compute(manifest, project)


# ------------------------------------------------------------------ CLI (real process, real files)
def run_cli(*args):
    return subprocess.run([sys.executable, "-I", str(pathlib.Path(tb.__file__)), *args],
                          capture_output=True, text=True, timeout=60)


def test_cli_build_then_report_round_trip(project, tmp_path):
    out = tmp_path / "manifest.json"
    built = run_cli("build-manifest", "--project-dir", str(project), "--sessions", "s1", "--out", str(out))
    assert built.returncode == 0, built.stderr
    assert json.loads(built.stdout)["status"] == "WRITTEN"
    report = run_cli("report", "--manifest", str(out), "--project-dir", str(project))
    assert report.returncode == 0, report.stderr
    doc = json.loads(report.stdout)
    assert doc["status"] == "MEASURED" and doc["roles"]["python-reviewer"]["output_tokens"] == 200


def test_cli_report_not_run_exit_2_with_reason(project, tmp_path):
    out = tmp_path / "manifest.json"
    run_cli("build-manifest", "--project-dir", str(project), "--sessions", "s1", "--out", str(out))
    (project / "s1.jsonl").write_text("tampered\n", encoding="utf-8")
    report = run_cli("report", "--manifest", str(out), "--project-dir", str(project))
    assert report.returncode == 2
    doc = json.loads(report.stdout)
    assert doc["status"] == "NOT_RUN" and doc["reason"] == "HASH_MISMATCH" and "roles" not in doc


def test_cli_damaged_records_exit_2_without_numbers(project, tmp_path):
    with (project / "s1.jsonl").open("a", encoding="utf-8") as h:
        h.write("garbage" + chr(10))
    out = tmp_path / "manifest.json"
    assert run_cli("build-manifest", "--project-dir", str(project), "--sessions", "s1", "--out", str(out)).returncode == 0
    report = run_cli("report", "--manifest", str(out), "--project-dir", str(project))
    doc = json.loads(report.stdout)
    assert report.returncode == 2 and doc["reason"] == "DAMAGED_RECORDS" and "roles" not in doc


def test_cli_unreadable_manifest_not_run(project, tmp_path):
    bad = tmp_path / "m.json"
    bad.write_text("{oops", encoding="utf-8")
    report = run_cli("report", "--manifest", str(bad), "--project-dir", str(project))
    assert report.returncode == 2 and json.loads(report.stdout)["reason"] == "MANIFEST_UNREADABLE"


def test_cli_missing_session_not_run(project, tmp_path):
    res = run_cli("build-manifest", "--project-dir", str(project), "--sessions", "ghost", "--out", str(tmp_path / "m.json"))
    assert res.returncode == 2 and json.loads(res.stdout)["reason"] == "SESSION_MISSING"
    assert not (tmp_path / "m.json").exists()


def test_compute_empty_subagent_transcript_is_not_run(project, tmp_path):
    """Empty subagent files should cause NOT_RUN, not silently undercount."""
    (project / "s.jsonl").write_text(line("m", usage(1, 2, 3, 4)), encoding="utf-8")
    (project / "s" / "subagents").mkdir(parents=True)
    (project / "s" / "subagents" / "agent-a.jsonl").write_text("", encoding="utf-8")
    manifest, _ = build(project, tmp_path, sessions="s")
    
    # Verify the manifest was created successfully with both files
    doc = manifest_doc(manifest)
    assert len(doc["sessions"][0]["files"]) == 2
    
    # Try to report using the manifest - should fail due to empty subagent
    res = run_report(tmp_path / "manifest.json", project)
    assert res.returncode == 2
    doc = json.loads(res.stdout)
    assert doc["status"] == "NOT_RUN"
    assert doc["reason"] == "EMPTY_SUBAGENT_TRANSCRIPT"


def test_compute_unexpected_transcript_after_manifest_created_is_not_run(project, tmp_path):
    """Transcripts added after manifest creation should be detected."""
    (project / "s.jsonl").write_text(line("m", usage(1, 2, 3, 4)), encoding="utf-8")
    manifest, _ = build(project, tmp_path, sessions="s")
    
    # Verify the manifest was created
    doc = manifest_doc(manifest)
    assert doc["status"] == "WRITTEN"
    
    # Now add a new subagent transcript that wasn't in the manifest
    (project / "s" / "subagents").mkdir(parents=True, exist_ok=True)
    (project / "s" / "subagents" / "agent-b.jsonl").write_text(line("m2", usage(10, 20, 30, 40)), encoding="utf-8")
    
    # Try to report using the original manifest - should fail
    res = run_report(tmp_path / "manifest.json", project)
    assert res.returncode == 2
    doc = json.loads(res.stdout)
    assert doc["status"] == "NOT_RUN"
    assert doc["reason"] == "UNEXPECTED_TRANSCRIPT"

