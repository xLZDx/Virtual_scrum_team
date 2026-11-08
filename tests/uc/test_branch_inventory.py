"""U3-1: branch inventory / landing map (tools/uc/branch_inventory.py), library and in-process main().

Every test builds a throwaway git repository in tmp_path with `main`, feature branches and
refs/remotes/origin/<branch> refs created by `git update-ref`.  No network, no AEVE.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import subprocess

import pytest

from uc import branch_inventory as bi

IDENT = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]
UNICODE_PATH = "dir with space/файл é.txt"


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *IDENT, *args], capture_output=True, timeout=120)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    return done.stdout.decode("utf-8", "replace").strip()


def write(repo, rel, text):
    path = pathlib.Path(repo, *rel.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def publish(repo, name, sha=None):
    """Create refs/remotes/origin/<name> the way a fetch would."""
    git(repo, "update-ref", f"refs/remotes/origin/{name}", sha or git(repo, "rev-parse", "HEAD"))


RULES = [
    {"glob": "docs/**", "class": "EVIDENCE_ONLY", "reason": "history"},
    {"glob": "new/**", "class": "LAND", "reason": "new code"},
    {"glob": "**/*.txt", "class": "LAND", "reason": "text files"},
]


def write_rules(path, rules=None, **extra):
    doc = {"version": 1, "rules": RULES if rules is None else rules}
    doc.update(extra)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture()
def world(tmp_path, _template):
    """Fresh copy of the template repository for every test (tests mutate their own copy only)."""
    import shutil
    shutil.copytree(_template["repo"], tmp_path / "repo")
    return {"repo": tmp_path / "repo", "tmp": tmp_path, "rules": write_rules(tmp_path / "rules.json"),
            "base": _template["base"], "b1": _template["b1"], "b2": _template["b2"], "bu": _template["bu"],
            "m1": _template["m1"], "out": tmp_path / "map.json"}


@pytest.fixture(scope="module")
def _template(tmp_path_factory):
    """main (M0 -> M1); b1 forks at M0; b2 extends b1; b_unmatched forks at M0 with a file no rule matches."""
    tmp_path = tmp_path_factory.mktemp("bi-template")
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "checkout", "-q", "-b", "main")
    for name, text in (("common.txt", "v0"), ("mod.txt", "v0"), ("del.txt", "v0"), ("gone.txt", "v0"), ("same.txt", "v0")):
        write(repo, name, text)
    base = commit_all(repo, "base")

    git(repo, "checkout", "-q", "-b", "b1")
    write(repo, "new/file.py", "print(1)")
    write(repo, "mod.txt", "b1")
    write(repo, "same.txt", "same-new")
    write(repo, "same-add.txt", "shared")
    write(repo, "docs/readme.md", "# doc")
    write(repo, UNICODE_PATH, "unicode")
    (repo / "del.txt").unlink()
    (repo / "gone.txt").unlink()
    b1 = commit_all(repo, "b1")
    publish(repo, "b1")

    git(repo, "checkout", "-q", "-b", "b2")
    write(repo, "new/more.py", "print(2)")
    b2 = commit_all(repo, "b2")
    publish(repo, "b2")

    git(repo, "checkout", "-q", "-b", "b_unmatched", base)
    write(repo, "weird.zzz", "x")
    write(repo, "new/ok.py", "ok")
    bu = commit_all(repo, "unmatched")
    publish(repo, "b_unmatched")

    git(repo, "checkout", "-q", "main")
    write(repo, "mod.txt", "main")
    write(repo, "same.txt", "same-new")
    write(repo, "same-add.txt", "shared")
    (repo / "gone.txt").unlink()
    m1 = commit_all(repo, "main moves on")
    return {"repo": repo, "base": base, "b1": b1, "b2": b2, "bu": bu, "m1": m1}


def files_of(doc, branch):
    return doc["branches"][branch]["files"]


def build(world, branches=("b1",), rules=None):
    return bi.build_map(world["repo"], bi.load_rules(rules or world["rules"]), "main", list(branches))


def run_main(world, capsys, *extra, branches="b1", rules=None, out=None, target="main"):
    argv = ["map", "--repo", str(world["repo"]), "--rules", str(rules or world["rules"]), "--target", target,
            "--branches", branches]
    out = world["out"] if out is None else out
    if out:
        argv += ["--out", str(out)]
    code = bi.main([*argv, *extra])
    return code, json.loads(capsys.readouterr().out)


# ------------------------------------------------------------------ _glob_to_regex
def matches(glob, path):
    return bool(bi._glob_to_regex(glob).fullmatch(path))


@pytest.mark.parametrize("glob,path,expected", [
    ("docs/**", "docs/a.md", True),
    ("docs/**", "docs/a/b/c.md", True),
    ("docs/**", "docs", False),
    ("docs/**", "docsx/a.md", False),
    ("docs/**", "other/docs/a.md", False),
    ("**/*.py", "a.py", True),
    ("**/*.py", "x/y/z/a.py", True),
    ("**/*.py", "x/a.pyc", False),
    ("**/*.py", "x/.py", True),
    ("src/**/x.py", "src/x.py", True),
    ("src/**/x.py", "src/a/b/x.py", True),
    ("src/**/x.py", "srcx.py", False),
    ("src/**/x.py", "src/a/y.py", False),
    ("*.md", "README.md", True),
    ("*.md", "docs/README.md", False),
    ("docs/*.md", "docs/a.md", True),
    ("docs/*.md", "docs/sub/a.md", False),
    ("a?c", "abc", True),
    ("a?c", "a/c", False),
    ("a?c", "ac", False),
    ("exact/file.txt", "exact/file.txt", True),
    ("exact/file.txt", "exact/file_txt", False),
    ("a.b", "a.b", True),
    ("a.b", "axb", False),
    ("a+b(1).txt", "a+b(1).txt", True),
    ("a+b(1).txt", "aab1.txt", False),
    ("[ab].txt", "[ab].txt", True),
    ("[ab].txt", "a.txt", False),
    ("a$b^c|d", "a$b^c|d", True),
    ("dir with space/*.txt", "dir with space/f.txt", True),
    ("файл/**", "файл/é.txt", True),
    ("tools/**", "tools/uc/x.py", True),
    ("**", "anything/at/all", True),
    ("**", "root", True),
    ("*", "root", True),
    ("*", "a/b", False),
    ("Docs/**", "docs/a.md", False),
], ids=lambda v: str(v)[:30])
def test_glob_to_regex(glob, path, expected):
    assert matches(glob, path) is expected


def test_glob_regex_is_anchored_at_both_ends():
    assert not matches("a.txt", "xa.txt") and not matches("a.txt", "a.txtx")
    assert not matches("a.txt", "a.txt\n")


def test_glob_double_star_without_slash_crosses_directories():
    assert matches("a**b", "a/x/y/b") and not matches("a*b", "a/x/y/b")


# ------------------------------------------------------------------ rules loading
def rules_error(tmp_path, content):
    path = tmp_path / "r.json"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    with pytest.raises(bi.InventoryError) as info:
        bi.load_rules(path)
    return info.value.reason


GOOD_RULE = {"glob": "a/**", "class": "LAND", "reason": "r"}


@pytest.mark.parametrize("content", [
    {"rules": [{"glob": "a/**", "class": "LAND"}]},                              # missing reason
    {"rules": [{"glob": "a/**", "class": "LAND", "reason": ""}]},
    {"rules": [{"glob": "a/**", "class": "LAND", "reason": "   "}]},
    {"rules": [{"glob": "a/**", "class": "land", "reason": "r"}]},                 # wrong case
    {"rules": [{"glob": "a/**", "class": "KEEP", "reason": "r"}]},                 # unknown class
    {"rules": [{"glob": "a/**", "class": "ALREADY_IN_MAIN", "reason": "r"}]},      # relation-derived class not allowed
    {"rules": [{"glob": "a/**", "class": "UNCLASSIFIED", "reason": "r"}]},
    {"rules": [{"glob": "", "class": "LAND", "reason": "r"}]},
    {"rules": [{"glob": 5, "class": "LAND", "reason": "r"}]},
    {"rules": [{"class": "LAND", "reason": "r"}]},
    {"rules": [{"glob": "a", "class": "LAND", "reason": 7}]},
    {"rules": ["a/**"]},
    {"rules": [None]},
    {"rules": [GOOD_RULE, {"glob": "b", "class": "DROP"}]},                        # second rule bad
    {"rules": []},
    {"rules": {}},
    {"rules": "a/**"},
    {},
    [],
    [GOOD_RULE],
    "null",
    "5",
], ids=lambda v: json.dumps(v)[:45])
def test_load_rules_invalid(tmp_path, content):
    assert rules_error(tmp_path, content) == "RULES_INVALID"


@pytest.mark.parametrize("content", ["{not json", "", b"\xff\xfe\x00", b"\xef\xbb\xbf{}"], ids=["syntax", "empty", "binary", "bom"])
def test_load_rules_unreadable_content(tmp_path, content):
    assert rules_error(tmp_path, content) == "RULES_UNREADABLE"


def test_load_rules_missing_file_and_directory(tmp_path):
    with pytest.raises(bi.InventoryError) as info:
        bi.load_rules(tmp_path / "nope.json")
    assert info.value.reason == "RULES_UNREADABLE"
    with pytest.raises(bi.InventoryError) as info:
        bi.load_rules(tmp_path)
    assert info.value.reason == "RULES_UNREADABLE"


def test_load_rules_accepts_valid_and_keeps_order_and_ignores_extra_keys(tmp_path):
    rules = bi.load_rules(write_rules(tmp_path / "r.json", [GOOD_RULE, dict(GOOD_RULE, glob="b", **{"class": "DROP"})],
                                      note="hello"))
    assert [r["glob"] for r in rules] == ["a/**", "b"] and [r["class"] for r in rules] == ["LAND", "DROP"]
    assert all(hasattr(r["regex"], "match") for r in rules)


def test_committed_rules_file_loads_and_every_rule_has_a_reason():
    path = pathlib.Path(bi.__file__).resolve().parents[2] / "catalog" / "branch_landing_rules.json"
    rules = bi.load_rules(path)
    assert len(rules) >= 10 and all(r["reason"].strip() for r in rules)


# ------------------------------------------------------------------ classify (pure)
def test_first_match_wins_and_order_matters():
    rules = [{"glob": "new/**", "class": "DROP", "reason": "first", "regex": bi._glob_to_regex("new/**")},
             {"glob": "new/file.py", "class": "LAND", "reason": "second", "regex": bi._glob_to_regex("new/file.py")}]
    got = bi.classify("new/file.py", "NEW", rules)
    assert (got["class"], got["reason"], got["rule"]) == ("DROP", "first", "new/**")
    got = bi.classify("new/file.py", "NEW", list(reversed(rules)))
    assert (got["class"], got["reason"], got["rule"]) == ("LAND", "second", "new/file.py")


def test_classify_relation_overrides_rules():
    rules = bi.load_rules(pathlib.Path(bi.__file__).resolve().parents[2] / "catalog" / "branch_landing_rules.json")
    assert bi.classify("tools/uc/x.py", "ALREADY_IN_MAIN", rules)["class"] == "ALREADY_IN_MAIN"
    for rel in ("BRANCH_DELETES", "BRANCH_DELETES_ABSENT"):
        got = bi.classify("tools/uc/x.py", rel, rules)
        assert got["class"] == "DROP" and got["rule"] == "built-in:deletion" and got["reason"].strip()
    assert bi.classify("tools/uc/x.py", "NEW", rules)["class"] == "LAND"


def test_classify_unmatched_is_unclassified_with_reason():
    got = bi.classify("weird.zzz", "NEW", bi.load_rules(_rules_file_for_unit()))
    assert got["class"] == "UNCLASSIFIED" and got["rule"] is None and got["reason"]


def _rules_file_for_unit(_cache={}):
    import tempfile
    if "p" not in _cache:
        d = pathlib.Path(tempfile.mkdtemp(prefix="bi-rules-"))
        _cache["p"] = write_rules(d / "r.json")
    return _cache["p"]


# ------------------------------------------------------------------ build_map: relations
def test_relations_status_class_and_reason_for_every_kind(world):
    doc = build(world)
    files = files_of(doc, "b1")
    expect = {
        "new/file.py": ("A", "NEW", "LAND"),
        "docs/readme.md": ("A", "NEW", "EVIDENCE_ONLY"),
        UNICODE_PATH: ("A", "NEW", "LAND"),
        "mod.txt": ("M", "DIVERGED", "LAND"),
        "same.txt": ("M", "ALREADY_IN_MAIN", "ALREADY_IN_MAIN"),
        "same-add.txt": ("A", "ALREADY_IN_MAIN", "ALREADY_IN_MAIN"),
        "del.txt": ("D", "BRANCH_DELETES", "DROP"),
        "gone.txt": ("D", "BRANCH_DELETES_ABSENT", "DROP"),
    }
    assert set(files) == set(expect)
    for path, (status, relation, klass) in expect.items():
        entry = files[path]
        assert (entry["status"], entry["relation"], entry["class"]) == (status, relation, klass), path
        assert entry["reason"].strip(), path
    assert files["new/file.py"]["rule"] == "new/**" and files["docs/readme.md"]["rule"] == "docs/**"
    assert files["del.txt"]["rule"] == "built-in:deletion" and files["same.txt"]["rule"] is None


def test_unchanged_files_are_not_listed(world):
    assert "common.txt" not in files_of(build(world), "b1")


def test_changes_are_measured_from_the_merge_base_not_from_main_head(world):
    """main's own later change to mod.txt must not appear as a branch change; b1 changed mod.txt itself."""
    doc = build(world)
    assert doc["branches"]["b1"]["merge_base"] == world["base"]
    assert doc["target_head"] == world["m1"] and doc["branches"]["b1"]["head"] == world["b1"]


def test_file_count_matches_listed_files_and_summary(world):
    doc = build(world, ("b1", "b2"))
    for name in ("b1", "b2"):
        branch = doc["branches"][name]
        assert branch["file_count"] == len(branch["files"])
    s = doc["summary"]["b1"]
    assert s["files"] == 8 and sum(s["by_class"].values()) == 8
    assert s["by_class"] == {"ALREADY_IN_MAIN": 2, "DROP": 2, "EVIDENCE_ONLY": 1, "LAND": 3}
    assert s["land_needs_manual_merge"] == 1  # only mod.txt is LAND and DIVERGED


def test_branch_with_no_changes_has_zero_files(world):
    publish(world["repo"], "same_as_main", world["m1"])
    doc = build(world, ("same_as_main",))
    assert doc["branches"]["same_as_main"]["file_count"] == 0 and doc["branches"]["same_as_main"]["files"] == {}
    assert bi.check_map(doc) == []


def test_subsumed_by_when_one_branch_is_an_ancestor_of_another(world):
    doc = build(world, ("b1", "b2"))
    assert doc["branches"]["b1"]["subsumed_by"] == ["b2"]
    assert doc["branches"]["b2"]["subsumed_by"] == []
    assert set(files_of(doc, "b2")) == set(files_of(doc, "b1")) | {"new/more.py"}


def test_unrelated_branches_are_not_subsumed(world):
    doc = build(world, ("b1", "b_unmatched"))
    assert doc["branches"]["b1"]["subsumed_by"] == [] and doc["branches"]["b_unmatched"]["subsumed_by"] == []


def test_identical_heads_subsume_each_other(world):
    publish(world["repo"], "b1_twin", world["b1"])
    doc = build(world, ("b1", "b1_twin"))
    assert doc["branches"]["b1"]["subsumed_by"] == ["b1_twin"] and doc["branches"]["b1_twin"]["subsumed_by"] == ["b1"]


def test_same_content_added_on_both_sides_is_already_in_main_but_different_content_is_diverged(world):
    repo = world["repo"]
    git(repo, "checkout", "-q", "-b", "c1", world["base"])
    write(repo, "x1.txt", "one")
    write(repo, "x2.txt", "branch-side")
    c1 = commit_all(repo, "c1")
    publish(repo, "c1", c1)
    git(repo, "checkout", "-q", "main")
    write(repo, "x1.txt", "one")
    write(repo, "x2.txt", "main-side")
    commit_all(repo, "main adds x")
    files = files_of(build(world, ("c1",)), "c1")
    assert files["x1.txt"]["relation"] == "ALREADY_IN_MAIN" and files["x2.txt"]["relation"] == "DIVERGED"


def test_file_deleted_on_branch_but_changed_on_main_is_branch_deletes(world):
    files = files_of(build(world), "b1")
    assert files["del.txt"]["relation"] == "BRANCH_DELETES"


def test_unicode_and_space_paths_survive_exactly(world):
    doc = build(world)
    assert UNICODE_PATH in files_of(doc, "b1")
    again = json.loads(json.dumps(doc, ensure_ascii=False))
    assert UNICODE_PATH in files_of(again, "b1")


def test_files_are_listed_in_sorted_order(world):
    assert list(files_of(build(world), "b1")) == sorted(files_of(build(world), "b1"))


def test_branch_rules_change_class_not_relation(world, tmp_path):
    rules = write_rules(tmp_path / "other.json", [{"glob": "**", "class": "DROP", "reason": "everything dropped"}])
    files = files_of(build(world, rules=rules), "b1")
    assert files["new/file.py"]["class"] == "DROP" and files["new/file.py"]["relation"] == "NEW"
    assert files["same.txt"]["class"] == "ALREADY_IN_MAIN"


# ------------------------------------------------------------------ check_map: every file classified exactly once
def good_doc(world):
    return build(world, ("b1", "b2"))


def test_check_accepts_a_generated_map(world):
    assert bi.check_map(good_doc(world)) == []


def test_unmatched_file_is_unclassified_and_check_reports_it(world):
    doc = build(world, ("b_unmatched",))
    entry = files_of(doc, "b_unmatched")["weird.zzz"]
    assert entry["class"] == "UNCLASSIFIED" and entry["rule"] is None
    assert files_of(doc, "b_unmatched")["new/ok.py"]["class"] == "LAND"
    problems = bi.check_map(doc)
    assert len(problems) == 1 and "weird.zzz" in problems[0] and "UNCLASSIFIED" in problems[0]


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: files_of(d, "b1")["mod.txt"].pop("reason"), "has no reason"),
    (lambda d: files_of(d, "b1")["mod.txt"].update(reason=""), "has no reason"),
    (lambda d: files_of(d, "b1")["mod.txt"].update(reason="   "), "has no reason"),
    (lambda d: files_of(d, "b1")["mod.txt"].update(**{"class": "KEEP"}), "mod.txt is 'KEEP'"),
    (lambda d: files_of(d, "b1")["mod.txt"].pop("class"), "mod.txt is None"),
    (lambda d: files_of(d, "b1")["mod.txt"].update(**{"class": "UNCLASSIFIED"}), "UNCLASSIFIED"),
    (lambda d: files_of(d, "b1")["mod.txt"].update(relation="SIDEWAYS"), "unknown relation"),
    (lambda d: files_of(d, "b1")["mod.txt"].pop("relation"), "unknown relation"),
    (lambda d: files_of(d, "b1").__setitem__("mod.txt", "LAND"), "mod.txt is 'LAND'"),
    (lambda d: files_of(d, "b1").__setitem__("mod.txt", None), "mod.txt is None"),
    (lambda d: d["branches"]["b1"].update(file_count=99), "file_count 99 != 8"),
    (lambda d: d["branches"]["b1"].pop("file_count"), "file_count None"),
    (lambda d: files_of(d, "b1").pop("mod.txt"), "file_count 8 != 7"),
    (lambda d: files_of(d, "b1").__setitem__("extra.txt", copy.deepcopy(files_of(d, "b1")["mod.txt"])), "file_count 8 != 9"),
    (lambda d: d["branches"]["b1"].update(files=[]), "no files object"),
    (lambda d: d["branches"].update(b1=None), "no files object"),
    (lambda d: d["branches"].update(b1="x"), "no files object"),
], ids=lambda v: v if isinstance(v, str) else "")
def test_check_detects_hand_edited_maps(world, mutate, fragment):
    doc = good_doc(world)
    mutate(doc)
    problems = bi.check_map(doc)
    assert problems and any(fragment in p for p in problems), problems


@pytest.mark.parametrize("doc", [None, [], "x", 5, {}, {"branches": {}}, {"branches": []}, {"branches": None}, {"files": {}}])
def test_check_map_without_branches_is_a_problem(doc):
    assert bi.check_map(doc) == ["map has no branches"]


def test_check_reports_problems_per_branch(world):
    doc = good_doc(world)
    files_of(doc, "b1")["mod.txt"]["reason"] = ""
    files_of(doc, "b2")["mod.txt"]["reason"] = ""
    problems = bi.check_map(doc)
    assert any(p.startswith("b1:") for p in problems) and any(p.startswith("b2:") for p in problems)


def test_check_rejects_a_class_that_contradicts_the_relation_in_both_directions(world):
    doc = good_doc(world)
    files_of(doc, "b1")["new/file.py"]["class"] = "ALREADY_IN_MAIN"          # NEW file claimed as already in main
    problems = bi.check_map(doc)
    assert len(problems) == 1 and "new/file.py" in problems[0] and "contradicts relation NEW" in problems[0]
    doc = good_doc(world)
    files_of(doc, "b1")["same.txt"]["class"] = "LAND"                        # identical file claimed as landable
    problems = bi.check_map(doc)
    assert len(problems) == 1 and "same.txt" in problems[0] and "contradicts relation ALREADY_IN_MAIN" in problems[0]


@pytest.mark.parametrize("path,bad_class", [("del.txt", "LAND"), ("del.txt", "EVIDENCE_ONLY"), ("gone.txt", "LAND"),
                                            ("gone.txt", "EVIDENCE_ONLY")])
def test_check_rejects_a_branch_deletion_that_is_not_drop(world, path, bad_class):
    doc = good_doc(world)
    files_of(doc, "b1")[path]["class"] = bad_class
    problems = bi.check_map(doc)
    assert len(problems) == 1 and path in problems[0] and "branch deletion" in problems[0]


def test_check_still_accepts_valid_maps_with_every_relation(world):
    doc = good_doc(world)
    relations = {e["relation"] for e in files_of(doc, "b1").values()}
    assert relations == {"NEW", "DIVERGED", "ALREADY_IN_MAIN", "BRANCH_DELETES", "BRANCH_DELETES_ABSENT"}
    assert bi.check_map(doc) == []
    assert bi.check_map(build(world, ("b_unmatched",))) != []  # only because of the unclassified file


def test_path_with_trailing_newline_does_not_match_a_rule_for_the_clean_name():
    nl = chr(10)
    rules = [{"glob": "a.txt", "class": "LAND", "reason": "r", "regex": bi._glob_to_regex("a.txt")}]
    assert bi.classify("a.txt", "NEW", rules)["class"] == "LAND"
    assert bi.classify("a.txt" + nl, "NEW", rules)["class"] == "UNCLASSIFIED"
    assert not matches("a.txt", "a.txt" + nl)
    assert not matches("**/*.txt", "x/a.txt" + nl)
    assert not matches("docs/*", "docs/a" + nl + "b/c")
    assert not matches("docs/**", "docs/a" + nl + "b")  # a newline anywhere fails closed: such a path stays UNCLASSIFIED


# ------------------------------------------------------------------ main(): map
def test_main_map_complete_writes_out_and_prints_summary(world, capsys):
    code, printed = run_main(world, capsys, branches="b1,b2")
    assert code == 0
    assert printed["status"] == "COMPLETE" and printed["problem_count"] == 0 and printed["problems"] == []
    assert printed["summary"]["b1"]["files"] == 8
    written = json.loads(world["out"].read_text(encoding="utf-8"))
    assert written["target"] == "main" and written["target_head"] == world["m1"]
    assert written["summary"] == printed["summary"]
    assert bi.check_map(written) == []
    assert b"\r\n" not in world["out"].read_bytes() and world["out"].read_bytes().endswith(b"\n")


def test_main_map_without_out_writes_nothing_and_succeeds(world, capsys):
    before = sorted(p.name for p in world["tmp"].iterdir())
    code, printed = run_main(world, capsys, out="")
    assert code == 0 and printed["status"] == "COMPLETE"
    assert sorted(p.name for p in world["tmp"].iterdir()) == before


def test_main_map_unclassified_file_exit_3_but_out_still_written(world, capsys):
    code, printed = run_main(world, capsys, branches="b_unmatched")
    assert code == 3 and printed["status"] == "INCOMPLETE" and printed["problem_count"] == 1
    assert "weird.zzz" in printed["problems"][0]
    written = json.loads(world["out"].read_text(encoding="utf-8"))
    assert files_of(written, "b_unmatched")["weird.zzz"]["class"] == "UNCLASSIFIED"
    assert bi.check_map(written)  # the saved map fails the machine check as well


def test_main_map_empty_branch_list_is_incomplete_exit_3(world, capsys):
    for branches in ("", " ", ",,"):
        code, printed = run_main(world, capsys, branches=branches)
        assert code == 3 and printed["problems"] == ["map has no branches"]


def test_main_map_branch_list_whitespace_is_trimmed(world, capsys):
    code, printed = run_main(world, capsys, branches=" b1 , b2 ,")
    assert code == 0 and sorted(printed["summary"]) == ["b1", "b2"]


def test_main_map_unknown_branch_is_not_run_git_failed(world, capsys):
    code, printed = run_main(world, capsys, branches="b1,does-not-exist")
    assert code == 2 and printed["status"] == "NOT_RUN" and printed["reason"] == "GIT_FAILED"
    assert not world["out"].exists()


def test_main_map_local_only_branch_without_origin_ref_is_not_found(world, capsys):
    git(world["repo"], "branch", "local-only", world["b1"])
    code, printed = run_main(world, capsys, branches="local-only")
    assert code == 2 and printed["reason"] == "GIT_FAILED"


def test_main_map_unknown_target_is_git_failed(world, capsys):
    code, printed = run_main(world, capsys, target="no-such-target")
    assert code == 2 and printed["reason"] == "GIT_FAILED" and not world["out"].exists()


def test_main_map_not_a_repository_and_missing_directory(world, capsys, tmp_path):
    (tmp_path / "plain").mkdir()
    for repo in (tmp_path / "plain", tmp_path / "missing"):
        argv = ["map", "--repo", str(repo), "--rules", str(world["rules"]), "--branches", "b1"]
        assert bi.main(argv) == 2
        printed = json.loads(capsys.readouterr().out)
        assert printed["reason"] == "GIT_FAILED"


def test_main_map_unrelated_histories_is_git_failed(world, capsys):
    repo = world["repo"]
    git(repo, "checkout", "-q", "--orphan", "island")
    git(repo, "rm", "-rf", "-q", ".")
    write(repo, "island.txt", "x")
    sha = commit_all(repo, "island")
    publish(repo, "island", sha)
    git(repo, "checkout", "-q", "main")
    code, printed = run_main(world, capsys, branches="island")
    assert code == 2 and printed["reason"] == "GIT_FAILED"


@pytest.mark.parametrize("bad,reason", [
    ({"rules": [{"glob": "a", "class": "LAND"}]}, "RULES_INVALID"),
    ({"rules": [{"glob": "a", "class": "NOPE", "reason": "r"}]}, "RULES_INVALID"),
    ({"rules": []}, "RULES_INVALID"),
    ("{not json", "RULES_UNREADABLE"),
])
def test_main_map_invalid_rules_is_not_run_and_writes_nothing(world, capsys, tmp_path, bad, reason):
    path = tmp_path / "bad-rules.json"
    path.write_text(bad if isinstance(bad, str) else json.dumps(bad), encoding="utf-8")
    code, printed = run_main(world, capsys, rules=path)
    assert code == 2 and printed["status"] == "NOT_RUN" and printed["reason"] == reason
    assert not world["out"].exists()


def test_main_map_missing_rules_file_is_rules_unreadable(world, capsys, tmp_path):
    code, printed = run_main(world, capsys, rules=tmp_path / "gone.json")
    assert code == 2 and printed["reason"] == "RULES_UNREADABLE"


def test_main_map_unwritable_out_is_output_unwritable_exit_2(world, capsys, tmp_path):
    code, printed = run_main(world, capsys, out=tmp_path / "no-such-dir" / "map.json")
    assert code == 2 and printed["status"] == "NOT_RUN" and printed["reason"] == "OUTPUT_UNWRITABLE"


def test_main_map_out_is_a_directory_is_output_unwritable(world, capsys, tmp_path):
    target = tmp_path / "adir"
    target.mkdir()
    code, printed = run_main(world, capsys, out=target)
    assert code == 2 and printed["reason"] == "OUTPUT_UNWRITABLE"


def test_main_map_overwrites_an_existing_out_file(world, capsys):
    world["out"].write_text("old", encoding="utf-8")
    code, _ = run_main(world, capsys)
    assert code == 0 and json.loads(world["out"].read_text(encoding="utf-8"))["version"] == 1


def test_map_output_is_deterministic(world, capsys):
    run_main(world, capsys, branches="b1,b2")
    first = world["out"].read_bytes()
    run_main(world, capsys, branches="b1,b2")
    assert world["out"].read_bytes() == first
    run_main(world, capsys, branches="b2,b1")
    assert json.loads(world["out"].read_bytes())["branches"] == json.loads(first)["branches"]


# ------------------------------------------------------------------ read-only guarantee
def snapshot(repo):
    git(repo, "status", "--porcelain")  # settle racy index timestamps once, before anything is measured
    status = git(repo, "--no-optional-locks", "status", "--porcelain", "--untracked-files=all")
    refs = git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    index = pathlib.Path(repo, ".git", "index")
    tree = {}
    for p in sorted(pathlib.Path(repo).rglob("*")):
        rel = p.relative_to(repo)
        if p.is_file() and ".git" not in rel.parts:
            tree[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"head": git(repo, "rev-parse", "HEAD"), "branch": git(repo, "branch", "--show-current"), "status": status,
            "refs": refs, "index": hashlib.sha256(index.read_bytes()).hexdigest(),
            "tree": tree, "stash": git(repo, "stash", "list")}


def test_map_leaves_head_index_refs_and_working_tree_unchanged_even_when_dirty(world, capsys):
    repo = world["repo"]
    write(repo, "mod.txt", "locally modified, not committed")
    write(repo, "untracked file.txt", "u")
    git(repo, "add", "untracked file.txt")  # staged
    write(repo, "another untracked.bin", "u2")
    before = snapshot(repo)
    assert before["status"]  # the repo really is dirty
    code, _ = run_main(world, capsys, branches="b1,b2,b_unmatched")
    assert code == 3
    assert snapshot(repo) == before


def test_map_with_clean_repo_leaves_status_empty_and_checked_out_branch(world, capsys):
    repo = world["repo"]
    before = snapshot(repo)
    assert before["status"] == "" and before["branch"] == "main"
    run_main(world, capsys, branches="b1,b2")
    assert snapshot(repo) == before


def test_map_with_out_inside_the_repo_adds_only_that_file(world, capsys):
    repo = world["repo"]
    before = snapshot(repo)
    out = repo / "inventory-map.json"
    code, _ = run_main(world, capsys, out=out)
    assert code == 0 and out.is_file()
    after = snapshot(repo)
    assert after["head"] == before["head"] and after["refs"] == before["refs"] and after["index"] == before["index"]
    assert set(after["tree"]) - set(before["tree"]) == {"inventory-map.json"}
    assert after["status"] == "?? inventory-map.json"


def test_map_does_not_create_objects_branches_or_tags(world, capsys):
    repo = world["repo"]
    count_before = git(repo, "count-objects", "-v")
    run_main(world, capsys, branches="b1,b2")
    assert git(repo, "for-each-ref", "--format=%(refname)") == "\n".join(sorted(git(repo, "for-each-ref", "--format=%(refname)").splitlines()))
    assert git(repo, "count-objects", "-v") == count_before


# ------------------------------------------------------------------ main(): check
def run_check(path, capsys):
    code = bi.main(["check", "--map", str(path)])
    return code, json.loads(capsys.readouterr().out)


def test_main_check_ok_on_generated_map(world, capsys):
    run_main(world, capsys, branches="b1,b2")
    code, printed = run_check(world["out"], capsys)
    assert code == 0 and printed == {"status": "COMPLETE", "problems": [], "problem_count": 0}


def test_main_check_exit_3_on_unclassified(world, capsys):
    run_main(world, capsys, branches="b_unmatched")
    code, printed = run_check(world["out"], capsys)
    assert code == 3 and printed["status"] == "INCOMPLETE" and "weird.zzz" in printed["problems"][0]


def test_main_check_hand_edited_map_missing_reason_unknown_class_wrong_count(world, capsys):
    run_main(world, capsys, branches="b1")
    doc = json.loads(world["out"].read_text(encoding="utf-8"))
    files = files_of(doc, "b1")
    files["mod.txt"].pop("reason")
    files["new/file.py"]["class"] = "KEEP"
    doc["branches"]["b1"]["file_count"] = 3
    world["out"].write_text(json.dumps(doc), encoding="utf-8")
    code, printed = run_check(world["out"], capsys)
    assert code == 3 and printed["problem_count"] == 3
    text = " ".join(printed["problems"])
    assert "has no reason" in text and "'KEEP'" in text and "file_count 3 != 8" in text


def test_main_check_no_branches_is_exit_3(world, capsys):
    world["out"].write_text(json.dumps({"version": 1, "branches": {}}), encoding="utf-8")
    code, printed = run_check(world["out"], capsys)
    assert code == 3 and printed["problems"] == ["map has no branches"]


@pytest.mark.parametrize("content", [b"{oops", b"", b"\xff\xfe\x00"], ids=["syntax", "empty", "binary"])
def test_main_check_unreadable_map_is_not_run_exit_2(world, capsys, content):
    world["out"].write_bytes(content)
    code, printed = run_check(world["out"], capsys)
    assert code == 2 and printed["status"] == "NOT_RUN" and printed["reason"] == "MAP_UNREADABLE"


def test_main_check_missing_map_file_is_not_run(world, capsys):
    code, printed = run_check(world["tmp"] / "nope.json", capsys)
    assert code == 2 and printed["reason"] == "MAP_UNREADABLE"


@pytest.mark.parametrize("payload", ["[]", "null", "5", '"x"'])
def test_main_check_non_object_map_is_a_problem_not_a_crash(world, capsys, payload):
    world["out"].write_text(payload, encoding="utf-8")
    code, printed = run_check(world["out"], capsys)
    assert code == 3 and printed["problems"] == ["map has no branches"]


def test_check_problem_list_is_capped_in_output_but_counted(world, capsys):
    doc = good_doc(world)
    template = files_of(doc, "b1")["mod.txt"]
    for n in range(30):
        files_of(doc, "b1")[f"extra/{n}.txt"] = dict(template, reason="")
    doc["branches"]["b1"]["file_count"] = len(files_of(doc, "b1"))
    world["out"].write_text(json.dumps(doc), encoding="utf-8")
    code, printed = run_check(world["out"], capsys)
    assert code == 3 and printed["problem_count"] == 30 and len(printed["problems"]) == 20
