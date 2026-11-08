"""U1-2: AEVE environment probe.

Most tests use a tiny fake AEVE checkout (a real git repository whose `python -m aeve` is a stub), so the
probe's decisions are exercised without the real analyzer.  ONE test at the bottom calls the real AEVE checkout
(D:/Repo/AEVE, about 20-40 s); it is marked `real_aeve` and skipped when AEVE is absent.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess
import sys

import pytest

from uc import aeve_probe

from tests.uc import ucsupport as S

REAL_AEVE = pathlib.Path("D:/Repo/AEVE")

FAKE_MAIN = '''\
import json, os, sys
mode = open(os.path.join(os.path.dirname(__file__), "mode.json"), encoding="utf-8").read()
mode = json.loads(mode)
cmd = sys.argv[1]
spec = mode.get(cmd, {})
if spec.get("sleep"):
    import time; time.sleep(spec["sleep"])
if spec.get("raw") is not None:
    sys.stdout.write(spec["raw"])
else:
    sys.stdout.write(json.dumps(spec.get("json")))
sys.exit(spec.get("exit", 0))
'''

GOOD_DOCTOR = {"agent_profiles": 57, "skill_contracts": 10, "llm_calls": 0, "executed_project_code": False}
GOOD_MATRIX = {"schema_version": "aeve.matrix.v1", "total_profiles": 2, "status_counts": {"PARTIAL": 1, "NOT_COVERED": 1},
               "rows": [{"id": "a"}, {"id": "b"}], "executors": ["e1", "e2", "e3"], "llm_calls": False,
               "executed_project_code": False}


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                    *args], check=True, capture_output=True, timeout=60)


def set_mode(root, **commands):
    (root / "src" / "aeve" / "mode.json").write_text(json.dumps(commands), encoding="utf-8")


@pytest.fixture()
def fake(tmp_path):
    root = tmp_path / "fake-aeve"
    pkg = root / "src" / "aeve"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text(FAKE_MAIN)
    (root / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True, timeout=60)
    set_mode(root, doctor={"json": GOOD_DOCTOR}, matrix={"json": GOOD_MATRIX})
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


def head_of(root):
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60).stdout.strip()


def blocked_reason(root, **kw):
    with pytest.raises(aeve_probe.AeveProbeError) as info:
        aeve_probe.probe(root, **kw)
    return info.value.reason


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


# ------------------------------------------------------------------ READY
def test_probe_ready_records_identity_fields(fake):
    rec = aeve_probe.probe(fake)
    assert rec["aeve_head"] == head_of(fake) and len(rec["aeve_head"]) == 40
    assert rec["tracked_dirty_paths"] == 0 and rec["untracked_paths"] == 0
    assert rec["interpreter"] == sys.executable
    assert rec["python"] == f"{sys.version_info[0]}.{sys.version_info[1]}"
    assert rec["probe_version"] == aeve_probe.PROBE_VERSION
    assert rec["doctor"] == {"agent_profiles": 57, "skill_contracts": 10, "llm_calls": 0, "executed_project_code": False}
    m = rec["matrix"]
    assert (m["total_profiles"], m["executor_count"], m["schema_version"]) == (2, 3, "aeve.matrix.v1")
    expected = hashlib.sha256(json.dumps(GOOD_MATRIX, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert m["digest_sha256"] == expected


def test_matrix_digest_changes_when_matrix_changes_and_is_key_order_independent(fake):
    d1 = aeve_probe.probe(fake)["matrix"]["digest_sha256"]
    reordered = dict(reversed(list(GOOD_MATRIX.items())))
    set_mode(fake, doctor={"json": GOOD_DOCTOR}, matrix={"json": reordered})
    assert aeve_probe.probe(fake)["matrix"]["digest_sha256"] == d1
    changed = dict(GOOD_MATRIX, executors=["e1", "e2"])
    set_mode(fake, doctor={"json": GOOD_DOCTOR}, matrix={"json": changed})
    assert aeve_probe.probe(fake)["matrix"]["digest_sha256"] != d1


def test_canonical_digest_known_vector():
    assert aeve_probe.canonical_digest({"b": 1, "a": [1, 2]}) == hashlib.sha256(b'{"a":[1,2],"b":1}').hexdigest()


def test_dirty_state_tracked_versus_untracked(fake):
    (fake / "src" / "aeve" / "__init__.py").write_text("# changed\n")
    (fake / "new_untracked.txt").write_text("x")
    rec = aeve_probe.probe(fake)
    assert rec["tracked_dirty_paths"] == 1 and rec["untracked_paths"] == 1


def test_probe_is_read_only_before_and_after_tree_hash_and_status_identical(fake):
    before_tree = tree_hash(fake)
    before_status = subprocess.run(["git", "-C", str(fake), "status", "--porcelain", "--ignored"], capture_output=True,
                                   text=True, timeout=60).stdout
    aeve_probe.probe(fake)
    aeve_probe.load_matrix(fake)
    after_status = subprocess.run(["git", "-C", str(fake), "status", "--porcelain", "--ignored"], capture_output=True,
                                  text=True, timeout=60).stdout
    assert tree_hash(fake) == before_tree
    assert after_status == before_status, "probe must not create bytecode or any file inside the AEVE checkout"


def test_child_env_is_minimal_and_isolated(fake, monkeypatch):
    monkeypatch.setenv("UC_SECRET_PROBE", "leak")
    env = aeve_probe.build_child_env(fake)
    assert "UC_SECRET_PROBE" not in env
    assert env["PYTHONPATH"] == str(fake / "src")
    assert env["PYTHONDONTWRITEBYTECODE"] == "1" and env["PYTHONNOUSERSITE"] == "1"
    assert set(env) <= set(aeve_probe._PASS_THROUGH_ENV) | {"PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE",
                                                            "PYTHONIOENCODING"}


# ------------------------------------------------------------------ BLOCKED rows
def test_wrong_path_is_not_an_aeve_checkout(tmp_path):
    assert blocked_reason(tmp_path) == "NOT_AN_AEVE_CHECKOUT"
    assert blocked_reason(tmp_path / "missing") == "NOT_AN_AEVE_CHECKOUT"
    with pytest.raises(aeve_probe.AeveProbeError) as info:
        aeve_probe.load_matrix(tmp_path)
    assert info.value.reason == "NOT_AN_AEVE_CHECKOUT"


def test_not_a_git_repository_is_blocked(tmp_path):
    root = tmp_path / "aeve-nogit"
    (root / "src" / "aeve").mkdir(parents=True)
    (root / "src" / "aeve" / "__main__.py").write_text(FAKE_MAIN)
    assert blocked_reason(root) == "GIT_FAILED"


@pytest.mark.skipif(os.name != "nt", reason="uses a .bat wrapper as a fake interpreter")
@pytest.mark.parametrize("printed,exit_code,reason", [("3 11", 0, "PYTHON_TOO_OLD"), ("3 11", 1, "INTERPRETER_FAILED"),
                                                      ("garbage", 0, "INTERPRETER_FAILED")])
def test_interpreter_checks(fake, tmp_path, printed, exit_code, reason):
    bat = tmp_path / "fakepython.bat"
    bat.write_text(f"@echo off\r\necho {printed}\r\nexit /b {exit_code}\r\n")
    assert blocked_reason(fake, python=str(bat)) == reason


def test_missing_interpreter_is_blocked(fake, tmp_path):
    assert blocked_reason(fake, python=str(tmp_path / "no-such-python.exe")) == "EXEC_FAILED"


def test_failing_doctor(fake):
    set_mode(fake, doctor={"json": GOOD_DOCTOR, "exit": 1}, matrix={"json": GOOD_MATRIX})
    assert blocked_reason(fake) == "DOCTOR_FAILED"


def test_failing_matrix(fake):
    set_mode(fake, doctor={"json": GOOD_DOCTOR}, matrix={"json": GOOD_MATRIX, "exit": 3})
    assert blocked_reason(fake) == "MATRIX_FAILED"
    with pytest.raises(aeve_probe.AeveProbeError) as info:
        aeve_probe.load_matrix(fake)
    assert info.value.reason == "MATRIX_FAILED"


@pytest.mark.parametrize("which", ["doctor", "matrix"])
@pytest.mark.parametrize("raw", ["not json", "", "[1, 2]", "5", "null"])
def test_malformed_output(fake, which, raw):
    spec = {"doctor": {"json": GOOD_DOCTOR}, "matrix": {"json": GOOD_MATRIX}}
    spec[which] = {"raw": raw}
    set_mode(fake, **spec)
    assert blocked_reason(fake) == "BAD_OUTPUT"


@pytest.mark.parametrize("missing", ["total_profiles", "status_counts", "rows", "executors"])
def test_matrix_missing_field(fake, missing):
    matrix = {k: v for k, v in GOOD_MATRIX.items() if k != missing}
    set_mode(fake, doctor={"json": GOOD_DOCTOR}, matrix={"json": matrix})
    assert blocked_reason(fake) == "BAD_OUTPUT"
    with pytest.raises(aeve_probe.AeveProbeError) as info:
        aeve_probe.load_matrix(fake)
    assert info.value.reason == "BAD_OUTPUT"


@pytest.mark.parametrize("doctor,matrix", [
    (dict(GOOD_DOCTOR, llm_calls=1), GOOD_MATRIX),
    (dict(GOOD_DOCTOR, executed_project_code=True), GOOD_MATRIX),
    ({k: v for k, v in GOOD_DOCTOR.items() if k != "llm_calls"}, GOOD_MATRIX),
    (GOOD_DOCTOR, dict(GOOD_MATRIX, llm_calls=True)),
    (GOOD_DOCTOR, dict(GOOD_MATRIX, llm_calls=2)),
    (GOOD_DOCTOR, dict(GOOD_MATRIX, executed_project_code=True)),
    (GOOD_DOCTOR, {k: v for k, v in GOOD_MATRIX.items() if k != "executed_project_code"}),
])
def test_model_or_execution_reported(fake, doctor, matrix):
    set_mode(fake, doctor={"json": doctor}, matrix={"json": matrix})
    assert blocked_reason(fake) == "MODEL_OR_EXECUTION_REPORTED"


def test_matrix_llm_calls_zero_or_false_is_accepted(fake):
    for value in (0, False):
        set_mode(fake, doctor={"json": GOOD_DOCTOR}, matrix={"json": dict(GOOD_MATRIX, llm_calls=value)})
        assert aeve_probe.probe(fake)["matrix"]["total_profiles"] == 2


def test_timeout_is_blocked_promptly(fake):
    set_mode(fake, doctor={"json": GOOD_DOCTOR, "sleep": 30}, matrix={"json": GOOD_MATRIX})
    import time
    start = time.monotonic()
    assert blocked_reason(fake, timeout=1.5) == "TIMEOUT"
    assert time.monotonic() - start < 15


# ------------------------------------------------------------------ CLI
def test_cli_ready_and_blocked_exit_codes(fake, tmp_path, capsys):
    assert aeve_probe.main(["--aeve-root", str(fake)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "READY" and out["aeve_head"] == head_of(fake)
    assert aeve_probe.main(["--aeve-root", str(tmp_path)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "BLOCKED" and out["reason"] == "NOT_AN_AEVE_CHECKOUT"


# ------------------------------------------------------------------ the ONE real-AEVE test
@pytest.mark.real_aeve
@pytest.mark.skipif(not (REAL_AEVE / "src" / "aeve" / "__main__.py").is_file(), reason="real AEVE checkout D:/Repo/AEVE not present")
def test_REAL_AEVE_probe_matrix_and_committed_role_table_validate_and_aeve_unchanged():
    """The only test that runs the real AEVE (U1-2 and U1-4 evidence).  ~20-40 s.

    Run `python -m pytest tests/uc -m "not real_aeve"` to skip it.
    """
    from uc import role_table

    def status():
        return subprocess.run(["git", "-C", str(REAL_AEVE), "status", "--porcelain", "--ignored"], capture_output=True,
                              text=True, timeout=120).stdout

    before = status()
    record = aeve_probe.probe(REAL_AEVE)
    matrix = aeve_probe.load_matrix(REAL_AEVE)
    assert status() == before, "AEVE checkout changed during the probe"
    assert record["python"] >= "3.12" or tuple(map(int, record["python"].split("."))) >= (3, 12)
    assert record["doctor"]["llm_calls"] == 0 and record["doctor"]["executed_project_code"] is False
    assert record["matrix"]["executor_count"] == len(matrix["executors"]) > 0
    assert aeve_probe.canonical_digest(matrix) == record["matrix"]["digest_sha256"]
    inventory = json.loads((S.REPO_ROOT / "catalog" / "inventory.json").read_text(encoding="utf-8"))
    problems = role_table.validate_role_table(S.real_table(), inventory, matrix, record)
    assert problems == [], problems


# ------------------------------------------------------------------ behaviour 7: git lookup and child interpreter flags
def test_find_git_ignores_relative_path_entries_and_the_current_directory(tmp_path, monkeypatch):
    trap = tmp_path / "trap"
    trap.mkdir()
    for name in ("git.exe", "git"):
        (trap / name).write_text("planted")
    monkeypatch.chdir(trap)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", "trap", str(pathlib.Path("."))]))
    assert aeve_probe._find_git() == "git"  # nothing absolute on PATH: bare fallback, never the planted file


def test_find_git_skips_relative_entry_but_takes_a_later_absolute_one(tmp_path, monkeypatch):
    trap = tmp_path / "trap"
    good = tmp_path / "good"
    trap.mkdir()
    good.mkdir()
    (trap / "git.exe").write_text("planted")
    (trap / "git").write_text("planted")
    (good / "git.exe").write_text("real")
    (good / "git").write_text("real")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", os.pathsep.join(["trap", str(good)]))
    found = aeve_probe._find_git()
    assert os.path.isabs(found) and pathlib.Path(found).parent == good


def test_find_git_takes_first_absolute_entry_in_path_order(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    for d in (first, second):
        d.mkdir()
        (d / "git.exe").write_text("x")
        (d / "git").write_text("x")
    monkeypatch.setenv("PATH", os.pathsep.join([str(first), str(second)]))
    assert pathlib.Path(aeve_probe._find_git()).parent == first


def test_find_git_without_any_git_on_absolute_path_falls_back(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert aeve_probe._find_git() == "git"


def _record_argv(monkeypatch):
    calls = []
    real = aeve_probe._run

    def spy(argv, **kw):
        calls.append(list(argv))
        return real(argv, **kw)

    monkeypatch.setattr(aeve_probe, "_run", spy)
    return calls


def test_probe_doctor_and_matrix_children_use_isolation_flags(fake, monkeypatch):
    calls = _record_argv(monkeypatch)
    aeve_probe.probe(fake)
    aeve_children = [c for c in calls if "-m" in c and "aeve" in c]
    assert [c[-1] for c in aeve_children] == ["doctor", "matrix"]
    for argv in aeve_children:
        assert argv[1:6] == ["-P", "-s", "-B", "-m", "aeve"], argv


def test_load_matrix_child_uses_isolation_flags(fake, monkeypatch):
    calls = _record_argv(monkeypatch)
    aeve_probe.load_matrix(fake)
    assert len(calls) == 1 and calls[0][1:6] == ["-P", "-s", "-B", "-m", "aeve"] and calls[0][-1] == "matrix"


def test_probe_children_do_not_import_from_the_scratch_directory(fake, monkeypatch, tmp_path):
    """-P keeps the child's working directory off sys.path: a planted aeve package in the scratch dir must not win."""
    scratch = tmp_path / "scratch"
    (scratch / "aeve").mkdir(parents=True)
    (scratch / "aeve" / "__init__.py").write_text("raise SystemExit(77)")
    (scratch / "aeve" / "__main__.py").write_text("raise SystemExit(77)")
    monkeypatch.setattr(aeve_probe.tempfile, "gettempdir", lambda: str(scratch))
    assert aeve_probe.probe(fake)["matrix"]["total_profiles"] == 2


# ------------------------------------------------------------------ untracked_source_paths
def test_untracked_source_paths_counts_only_untracked_under_src(fake):
    (fake / "reports" / "behavior-eval").mkdir(parents=True)
    (fake / "reports" / "behavior-eval" / "x.json").write_text("{}")
    (fake / "notes.txt").write_text("x")
    rec = aeve_probe.probe(fake)
    assert rec["untracked_paths"] == 2 and rec["untracked_source_paths"] == 0 and rec["tracked_dirty_paths"] == 0


def test_untracked_file_under_src_is_counted(fake):
    (fake / "src" / "x.py").write_text("x = 1")
    rec = aeve_probe.probe(fake)
    assert rec["untracked_source_paths"] == 1 and rec["untracked_paths"] == 1


def test_tracked_change_under_src_is_not_an_untracked_source_path(fake):
    (fake / "src" / "aeve" / "__init__.py").write_text("# changed2")
    rec = aeve_probe.probe(fake)
    assert rec["tracked_dirty_paths"] == 1 and rec["untracked_source_paths"] == 0


def test_untracked_directory_under_src_is_counted_once_per_status_line(fake):
    (fake / "src" / "newpkg").mkdir()
    (fake / "src" / "newpkg" / "m.py").write_text("x")
    assert aeve_probe.probe(fake)["untracked_source_paths"] == 1
