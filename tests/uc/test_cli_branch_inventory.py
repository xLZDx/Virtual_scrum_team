"""U3-1 command line: real subprocess runs of `python tools/uc/branch_inventory.py map|check`, plus ONE real-data check
of `map` on this repository against docs/sdlc/evidence/u3-1-branch-inventory.json."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from tests.uc.test_branch_inventory import (UNICODE_PATH, commit_all, git, publish, write, write_rules)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "uc" / "branch_inventory.py"
NL = chr(10)


def cli(*args, cwd=None, env=None):
    res = subprocess.run([sys.executable, "-I", str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                         timeout=300, cwd=cwd, env=env)
    return res


def doc_of(res):
    assert "Traceback" not in res.stderr, f"CLI crashed with a traceback:{NL}{res.stderr[-800:]}"
    return json.loads(res.stdout)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    """Read-only throwaway repository shared by the CLI tests (no test mutates it)."""
    tmp = tmp_path_factory.mktemp("cli-inventory")
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "checkout", "-q", "-b", "main")
    for name, text in (("mod.txt", "v0"), ("del.txt", "v0"), ("same.txt", "v0")):
        write(repo, name, text)
    base = commit_all(repo, "base")
    git(repo, "checkout", "-q", "-b", "b1")
    write(repo, "new/file.py", "print(1)")
    write(repo, "mod.txt", "b1")
    write(repo, "same.txt", "same-new")
    write(repo, "docs/readme.md", "# doc")
    write(repo, UNICODE_PATH, "unicode")
    (repo / "del.txt").unlink()
    publish(repo, "b1", commit_all(repo, "b1"))
    git(repo, "checkout", "-q", "-b", "b_unmatched", base)
    write(repo, "weird.zzz", "x")
    publish(repo, "b_unmatched", commit_all(repo, "unmatched"))
    git(repo, "checkout", "-q", "main")
    write(repo, "mod.txt", "main")
    write(repo, "same.txt", "same-new")
    commit_all(repo, "main moves on")
    rules = write_rules(tmp / "rules.json")
    return {"repo": repo, "rules": rules, "tmp": tmp}


def map_args(world, branches, out, rules=None):
    return ["map", "--repo", world["repo"], "--rules", rules or world["rules"], "--target", "main", "--branches", branches,
            "--out", out]


# ------------------------------------------------------------------ map
def test_map_valid_run_exit_0_prints_json_and_writes_out(world, tmp_path):
    out = tmp_path / "map.json"
    res = cli(*map_args(world, "b1", out))
    assert res.returncode == 0, res.stderr
    printed = doc_of(res)
    assert printed["status"] == "COMPLETE" and printed["problem_count"] == 0
    assert printed["summary"]["b1"] == {"by_class": {"ALREADY_IN_MAIN": 1, "DROP": 1, "EVIDENCE_ONLY": 1, "LAND": 3},
                                        "files": 6, "land_needs_manual_merge": 1}
    written = json.loads(out.read_text(encoding="utf-8"))
    assert UNICODE_PATH in written["branches"]["b1"]["files"]
    assert res.stderr == ""


def test_map_unclassified_file_exit_3(world, tmp_path):
    out = tmp_path / "map.json"
    res = cli(*map_args(world, "b_unmatched", out))
    printed = doc_of(res)
    assert res.returncode == 3 and printed["status"] == "INCOMPLETE" and "weird.zzz" in printed["problems"][0]
    assert out.is_file()


def test_check_round_trip_ok_and_failure(world, tmp_path):
    ok, bad = tmp_path / "ok.json", tmp_path / "bad.json"
    assert cli(*map_args(world, "b1", ok)).returncode == 0
    res = cli("check", "--map", ok)
    assert res.returncode == 0 and doc_of(res) == {"status": "COMPLETE", "problems": [], "problem_count": 0}
    assert cli(*map_args(world, "b_unmatched", bad)).returncode == 3
    res = cli("check", "--map", bad)
    assert res.returncode == 3 and doc_of(res)["status"] == "INCOMPLETE"


def test_check_hand_edited_map(world, tmp_path):
    out = tmp_path / "map.json"
    cli(*map_args(world, "b1", out))
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["branches"]["b1"]["files"]["mod.txt"]["reason"] = ""
    doc["branches"]["b1"]["files"]["new/file.py"]["class"] = "KEEP"
    doc["branches"]["b1"]["file_count"] = 1
    out.write_text(json.dumps(doc), encoding="utf-8")
    res = cli("check", "--map", out)
    assert res.returncode == 3 and doc_of(res)["problem_count"] == 3


def test_check_unreadable_and_missing_map_exit_2(world, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    for target in (bad, tmp_path / "missing.json"):
        res = cli("check", "--map", target)
        assert res.returncode == 2 and doc_of(res)["reason"] == "MAP_UNREADABLE"


def test_map_invalid_rules_not_run_exit_2_no_out(world, tmp_path):
    out = tmp_path / "map.json"
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"rules": [{"glob": "a", "class": "LAND"}]}), encoding="utf-8")
    res = cli(*map_args(world, "b1", out, rules=rules))
    assert res.returncode == 2 and doc_of(res)["reason"] == "RULES_INVALID" and not out.exists()
    rules.write_text("{oops", encoding="utf-8")
    res = cli(*map_args(world, "b1", out, rules=rules))
    assert res.returncode == 2 and doc_of(res)["reason"] == "RULES_UNREADABLE" and not out.exists()


def test_map_unknown_branch_exit_2_git_failed(world, tmp_path):
    out = tmp_path / "map.json"
    res = cli(*map_args(world, "b1,ghost", out))
    assert res.returncode == 2 and doc_of(res)["reason"] == "GIT_FAILED" and not out.exists()


def test_map_unwritable_out_exit_2(world, tmp_path):
    res = cli(*map_args(world, "b1", tmp_path / "no-dir" / "map.json"))
    assert res.returncode == 2 and doc_of(res)["reason"] == "OUTPUT_UNWRITABLE"


def test_map_from_a_different_working_directory_does_not_matter(world, tmp_path):
    out = tmp_path / "map.json"
    res = cli(*map_args(world, "b1", out), cwd=tmp_path)
    assert res.returncode == 0 and out.is_file()


def test_map_does_not_touch_the_repository(world, tmp_path):
    repo = world["repo"]
    before = (git(repo, "rev-parse", "HEAD"), git(repo, "status", "--porcelain", "--untracked-files=all"),
              git(repo, "for-each-ref"))
    cli(*map_args(world, "b1,b_unmatched", tmp_path / "map.json"))
    assert (git(repo, "rev-parse", "HEAD"), git(repo, "status", "--porcelain", "--untracked-files=all"),
            git(repo, "for-each-ref")) == before


def test_argparse_errors_exit_2_with_no_stdout(world, tmp_path):
    for argv in ([], ["frobnicate"], ["map", "--repo", str(world["repo"])], ["check"]):
        res = cli(*argv)
        assert res.returncode == 2 and res.stdout == "" and "Traceback" not in res.stderr


# ------------------------------------------------------------------ the ONE real-data check
REAL_BRANCHES = ["s4-canonical-continuation", "s4-native-qa-runner", "s4-reproducible-qa-automation",
                 "s4-e2e-snapshot-20261025-180e330", "s5-bounded-aeve-evidence"]
EXPECTED_COUNTS = {"s4-canonical-continuation": 724, "s4-native-qa-runner": 197, "s4-reproducible-qa-automation": 175,
                   "s4-e2e-snapshot-20261025-180e330": 194, "s5-bounded-aeve-evidence": 69}
EVIDENCE = REPO_ROOT / "docs" / "sdlc" / "evidence" / "u3-1-branch-inventory.json"


def _have_remote_refs():
    try:
        done = subprocess.run(["git", "-C", str(REPO_ROOT), "for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
                              capture_output=True, text=True, timeout=60)
    except OSError:
        return False
    have = set(done.stdout.split())
    return all(f"refs/remotes/origin/{b}" in have for b in REAL_BRANCHES)


@pytest.mark.skipif(not _have_remote_refs(), reason="refs/remotes/origin/<branch> for the S4/S5 branches are absent in this clone")
@pytest.mark.skipif(not EVIDENCE.is_file(), reason="docs/sdlc/evidence/u3-1-branch-inventory.json is absent")
def test_REAL_DATA_map_of_the_s4_s5_branches_matches_the_committed_evidence(tmp_path):
    out = tmp_path / "real-map.json"
    before = (git(REPO_ROOT, "rev-parse", "HEAD"), git(REPO_ROOT, "status", "--porcelain"))
    res = cli("map", "--repo", REPO_ROOT, "--rules", REPO_ROOT / "catalog" / "branch_landing_rules.json", "--branches", ",".join(REAL_BRANCHES), "--out", out, cwd=REPO_ROOT)
    assert doc_of(res)["status"] == "COMPLETE", res.stdout[:600]
    assert res.returncode == 0
    assert (git(REPO_ROOT, "rev-parse", "HEAD"), git(REPO_ROOT, "status", "--porcelain")) == before
    fresh = json.loads(out.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert {b: fresh["branches"][b]["file_count"] for b in REAL_BRANCHES} == EXPECTED_COUNTS
    assert {b: evidence["branches"][b]["file_count"] for b in REAL_BRANCHES} == EXPECTED_COUNTS
    for b in REAL_BRANCHES:
        assert fresh["branches"][b]["head"] == evidence["branches"][b]["head"], f"{b} head moved since the evidence"
        assert fresh["branches"][b]["subsumed_by"] == evidence["branches"][b]["subsumed_by"]
    assert fresh["target"] == "origin/main" == evidence["target"]
    assert fresh["target_head"] == evidence["target_head"], "origin/main moved since the evidence was generated"
    assert evidence["target_head"].startswith("83cfd64")
    assert fresh["branches"] == evidence["branches"] and fresh["summary"] == evidence["summary"]
    check = cli("check", "--map", out)
    assert check.returncode == 0 and doc_of(check)["status"] == "COMPLETE"


def test_caller_git_dir_environment_does_not_change_the_result(world, tmp_path):
    import os
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    git(decoy, "init", "-q")
    write(decoy, "other.txt", "x")
    commit_all(decoy, "decoy commit")
    env = dict(os.environ, GIT_DIR=str(decoy / ".git"), GIT_WORK_TREE=str(decoy), GIT_INDEX_FILE=str(decoy / ".git" / "index"))
    plain, hijacked = tmp_path / "plain.json", tmp_path / "hijacked.json"
    res1 = cli(*map_args(world, "b1", plain))
    res2 = cli(*map_args(world, "b1", hijacked), env=env)
    assert res1.returncode == 0 and res2.returncode == 0, res2.stdout + res2.stderr
    assert json.loads(plain.read_text(encoding="utf-8")) == json.loads(hijacked.read_text(encoding="utf-8"))
    assert doc_of(res1) == doc_of(res2)


def test_cli_bad_ref_name_and_stale_out(world, tmp_path):
    out = tmp_path / "map.json"
    assert cli(*map_args(world, "b1", out)).returncode == 0 and out.is_file()
    res = cli("map", "--repo", world["repo"], "--rules", world["rules"], "--target", "main", "--branches=-x",
              "--out", out)
    assert res.returncode == 2 and doc_of(res)["reason"] == "BAD_REF_NAME"
    assert not out.exists()
