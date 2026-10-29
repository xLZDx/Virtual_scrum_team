"""E4 runner and signing (remediation A+B): manifest-bound run_and_sign.

Real subprocesses run real (tiny) python commands. Covered contract:
- the manifest drives everything: allowed_commands equality, expected test ids
  equality, manifest_sha256 binding, retry_cap / timeout bounds;
- execution safety: per-stream output cap (exit -3), process-tree kill on
  timeout, overall deadline, minimal child environment, stdin closed;
- artifact containment (no traversal / absolute / symlink or junction);
- label-scoped HMAC (receipt label), keys >= 32 bytes;
- the gate accepts exactly what the runner produced and rejects replay/forgery.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

from tools.vst import contracts as c
from tools.vst import gate, runner, signing

from .e1e4_helpers import (
    EPOCH,
    HEAD,
    HEAD2,
    KEY,
    OPERATOR_KEY,
    SUPERVISOR_KEY,
    TASK,
    WRONG_KEY,
    bound,
    manifest,
    mhash,
    receipt,
)

PY = sys.executable
SECRET = b"TOP-SECRET-KEY-MATERIAL-9f3a-0123456789-abcdef"
assert len(SECRET) >= 32


def line_parser(stdout):
    """Tiny real parser: 'PASSED id', 'SKIPPED id', 'XFAIL id' lines."""
    executed, skipped, xfail = [], [], []
    for line in stdout.splitlines():
        word, _, ident = line.strip().partition(" ")
        if not ident:
            continue
        if word == "PASSED":
            executed.append(ident)
        elif word == "SKIPPED":
            skipped.append(ident)
        elif word == "XFAIL":
            xfail.append(ident)
    return executed, skipped, xfail


def printer(*lines, exit_code=0):
    code = "import sys\n" + "".join(f"print({ln!r})\n" for ln in lines) + f"sys.exit({exit_code})\n"
    return [PY, "-c", code]


def pycmd(code):
    return [PY, "-c", code]


PASS_CMD = printer("PASSED t1", "PASSED t2")
ALL_IDS = lambda s: (["t1", "t2"], [], [])  # noqa: E731 - parser that reports both ids


def mf(commands, **kw):
    """Manifest whose slot 'tests' allows exactly `commands` (argv lists)."""
    kw.setdefault("allowed_commands", [{"slot": "tests", "argv": list(a)} for a in commands])
    return manifest(**kw)


@pytest.fixture
def work(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return str(d)


_UNSET = object()


def run(work, *, m=_UNSET, allowed=None, **over):
    """run_and_sign with valid defaults; `allowed` (default: commands) feeds the manifest."""
    commands = over.get("commands", [PASS_CMD])
    kw = dict(
        slot="tests",
        attempt=1,
        epoch=EPOCH,
        candidate_head=HEAD,
        resolved_model="sonnet-5.5",
        invocation_id="inv-1",
        runner_id="runner-1",
        key=KEY,
        commands=commands,
        expected_test_ids=["t1", "t2"],
        test_result_parser=line_parser,
        covered_acceptance=["AC-1"],
        artifact_paths=[],
        prev_receipt_sha256=None,
        cwd=work,
        timeout_sec=30,
        created_at="2026-10-24T00:00:00Z",
    )
    kw.update(over)
    if m is _UNSET:
        m = mf(allowed if allowed is not None else (commands if isinstance(commands, list) else [PASS_CMD]))
    kw["manifest"] = m
    return runner.run_and_sign(**kw)


def tree_bytes(root):
    out = {}
    for base, _, files in os.walk(root):
        for f in files:
            p = os.path.join(base, f)
            with open(p, "rb") as fh:
                out[p] = fh.read()
    return out


def marker_cmd(path):
    return pycmd(f"open({path!r}, 'w').write('x')")


def captured(work, code, **over):
    """Run `code` once and return (receipt, stdout_seen_by_the_parser)."""
    seen = []

    def parser(stdout):
        seen.append(stdout)
        return ["t1", "t2"], [], []

    r = run(work, commands=[pycmd(code)], test_result_parser=parser, **over)
    return r, seen[0]


def _try_dir_link(link, target):
    """Create a directory symlink (or a Windows junction); False when impossible."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        res = subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True)
        return res.returncode == 0 and os.path.exists(link)
    return False


def _can_symlink(tmp_path):
    probe = tmp_path / "probe-link"
    target = tmp_path / "probe-target"
    target.mkdir()
    try:
        os.symlink(str(target), str(probe), target_is_directory=True)
    except (OSError, NotImplementedError):
        return False
    return True


# ------------------------------------------------------------ happy / failure


def test_harmless_command_produces_signed_passing_testrun(work):
    cmd = pycmd("print(1)")
    m = mf([cmd])
    r = run(work, m=m, commands=[cmd], test_result_parser=ALL_IDS)
    assert r["result"] == "PASS"
    assert r["receipt_type"] == "TestRun"
    assert r["commands"] == [{"argv": cmd, "exit_code": 0}]
    assert r["executed_test_ids"] == ["t1", "t2"] and r["expected_test_ids"] == ["t1", "t2"]
    assert r["receipt_id"] == f"{TASK}:tests:1:inv-1"
    assert r["prev_receipt_sha256"] is None
    assert signing.verify(r, KEY)
    assert c.validate_receipt(r) == r
    assert c.derive_result(r) == r["result"]


def test_receipt_is_bound_to_the_manifest_not_to_caller_supplied_ids(work):
    m = mf([PASS_CMD], task_id="TASK-X", role_sha256="9" * 64)
    r = run(work, m=m)
    assert r["task_id"] == "TASK-X"
    assert r["role_sha256"] == "9" * 64
    assert r["manifest_sha256"] == mhash(m) == c.manifest_sha256(m)
    sig = inspect.signature(runner.run_and_sign).parameters
    assert "manifest" in sig and "task_id" not in sig and "role_sha256" not in sig


def test_manifest_hash_changes_when_the_manifest_changes(work):
    a = run(work, m=mf([PASS_CMD], scope=["src/a.py"]))
    b = run(work, m=mf([PASS_CMD], scope=["src/b.py"]))
    assert a["manifest_sha256"] != b["manifest_sha256"]
    assert a["signature"] != b["signature"]


def test_receipt_carries_every_caller_supplied_field(work):
    r = run(
        work, attempt=2, prev_receipt_sha256="e" * 64, epoch=7, candidate_head=HEAD2,
        runner_id="rr", resolved_model="mm", invocation_id="ii",
        covered_acceptance=["AC-1", "AC-2"], created_at="2030-01-01T00:00:00Z",
    )
    assert (r["attempt"], r["prev_receipt_sha256"], r["epoch"], r["candidate_head"]) == (2, "e" * 64, 7, HEAD2)
    assert (r["runner_id"], r["resolved_model"], r["invocation_id"]) == ("rr", "mm", "ii")
    assert r["covered_acceptance"] == ["AC-1", "AC-2"] and r["created_at"] == "2030-01-01T00:00:00Z"
    assert r["task_id"] == TASK and r["slot"] == "tests"


def test_failing_command_nonzero_exit_gives_fail(work):
    r = run(work, commands=[printer("PASSED t1", "PASSED t2", exit_code=3)])
    assert r["commands"][0]["exit_code"] == 3
    assert r["result"] == "FAIL"
    assert signing.verify(r, KEY)


def test_all_commands_run_and_recorded_even_after_a_failure(work):
    r = run(work, commands=[printer("PASSED t1", exit_code=1), printer("PASSED t2")])
    assert [x["exit_code"] for x in r["commands"]] == [1, 0]
    assert r["executed_test_ids"] == ["t1", "t2"]  # the second command really ran
    assert r["result"] == "FAIL"


def test_parser_receives_joined_stdout_in_order(work):
    seen = []

    def parser(stdout):
        seen.append(stdout)
        return ["t1", "t2"], [], []

    run(work, commands=[printer("FIRST"), printer("SECOND")], test_result_parser=parser)
    assert len(seen) == 1
    # each command's stdout joined with a newline, in order (a child may emit CRLF on Windows)
    assert seen[0].replace("\r\n", "\n") == "FIRST\n\nSECOND\n"


def test_timeout_records_exit_minus_one_and_fails(work):
    sleeper = pycmd("import time; time.sleep(60)")
    started = time.monotonic()
    r = run(work, commands=[sleeper], timeout_sec=1, test_result_parser=ALL_IDS)
    assert time.monotonic() - started < 30  # killed, not waited out
    assert r["commands"][0]["exit_code"] == runner.EXIT_TIMEOUT == -1
    assert r["result"] == "FAIL"  # all ids reported executed, only the exit code can fail it
    assert signing.verify(r, KEY)


def test_missing_executable_records_exit_minus_two(work):
    cmd = ["definitely-not-an-installed-program-xyz"]
    r = run(work, commands=[cmd], test_result_parser=ALL_IDS)
    assert r["commands"][0]["exit_code"] == runner.EXIT_MISSING_EXECUTABLE == -2
    assert r["result"] == "FAIL"


def test_missing_cwd_records_exit_minus_two(work):
    r = run(work, cwd=os.path.join(work, "no-such-dir"), commands=[pycmd("print(1)")])
    assert r["commands"][0]["exit_code"] == -2


def test_cwd_that_is_a_file_maps_to_exit_minus_two(work):
    f = os.path.join(work, "a-file")
    with open(f, "wb") as fh:
        fh.write(b"x")
    r = run(work, cwd=f, test_result_parser=ALL_IDS)
    assert r["commands"][0]["exit_code"] == -2 and r["result"] == "FAIL"


def test_no_shell_metacharacters_are_not_interpreted(work):
    payload = "a && echo INJECTED; $(x) | y"
    cmd = pycmd("import sys; print(sys.argv[1])") + [payload]
    seen = []
    run(work, commands=[cmd], test_result_parser=lambda s: (seen.append(s) or ["t1", "t2"], [], []))
    assert seen[0].strip() == payload


def test_command_runs_in_the_given_cwd(work):
    r, out = captured(work, "import os; print(os.getcwd())")
    assert os.path.realpath(out.strip()) == os.path.realpath(work)


def test_stdin_is_closed_so_a_reading_command_cannot_hang(work):
    r, out = captured(work, "import sys; print(repr(sys.stdin.read()))")
    assert out.strip() == "''"
    assert r["commands"][0]["exit_code"] == 0


def test_non_utf8_output_does_not_crash_the_runner(work):
    r, out = captured(work, "import sys; sys.stdout.buffer.write(b'\\xff\\xfe bad bytes\\n')")
    assert r["commands"][0]["exit_code"] == 0 and "bad bytes" in out


def test_report_dict_describes_each_command(work):
    report = {}
    run(work, commands=[PASS_CMD, printer("PASSED t1")], report=report,
        allowed=[PASS_CMD, printer("PASSED t1")])
    assert len(report["commands"]) == 2
    assert report["capture_incomplete"] is False
    for info in report["commands"]:
        assert info == {
            "stdout_truncated": False, "stderr_truncated": False,
            "timed_out": False, "capture_incomplete": False,
            "job_object": (os.name == "nt"), "skipped_by_deadline": False,
        }


# ---------------------------------------------------- allowed_commands equality


def test_command_must_equal_an_allowed_command_exactly(work):
    marker = os.path.join(work, "ran.txt")
    allowed = marker_cmd(marker)
    variants = [
        allowed + ["--extra"],
        allowed[:-1],  # prefix
        allowed[:-1] + [allowed[-1] + " "],  # trailing whitespace
        [allowed[0].upper() if allowed[0].lower() != allowed[0].upper() else allowed[0] + "x"] + allowed[1:],
        list(reversed(allowed)),
        [PY, "-c", "print(1)"],
    ]
    for bad in variants:
        with pytest.raises(c.ContractError, match="allowed_commands"):
            run(work, m=mf([allowed]), commands=[bad])
    assert not os.path.exists(marker)  # nothing was executed
    run(work, m=mf([allowed]), commands=[allowed], test_result_parser=ALL_IDS)
    assert os.path.exists(marker)  # the exactly-equal argv does run


def test_one_disallowed_command_blocks_the_whole_run_before_any_starts(work):
    marker = os.path.join(work, "first-ran.txt")
    first = marker_cmd(marker)
    with pytest.raises(c.ContractError, match="allowed_commands"):
        run(work, m=mf([first]), commands=[first, pycmd("print('not allowed')")])
    assert not os.path.exists(marker)


def test_command_allowed_for_another_slot_is_refused(work):
    other = pycmd("print('only for tests2')")
    m = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "tests2", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        allowed_commands=[
            {"slot": "tests", "argv": PASS_CMD},
            {"slot": "tests2", "argv": other},
        ],
    )
    with pytest.raises(c.ContractError, match="allowed_commands"):
        run(work, m=m, commands=[other])
    r = run(work, m=m, commands=[PASS_CMD])
    assert r["result"] == "PASS"


def test_several_allowed_commands_may_all_run_and_repeat(work):
    a, b = printer("PASSED t1"), printer("PASSED t2")
    r = run(work, m=mf([a, b]), commands=[a, b, a])
    assert [x["argv"] for x in r["commands"]] == [a, b, a]
    assert r["result"] == "PASS"


def test_runner_never_executes_a_command_missing_from_the_manifest_even_if_receipt_would_fail(work):
    marker = os.path.join(work, "should-not-exist.txt")
    with pytest.raises(c.ContractError):
        run(work, m=mf([PASS_CMD]), commands=[marker_cmd(marker)])
    assert not os.path.exists(marker)


# ------------------------------------------------------ expected ids / slot / acceptance


@pytest.mark.parametrize(
    "ids",
    [["t1"], ["t1", "t2", "t3"], ["t1", "other"], [], ["t1", "t1", "t2"], ["T1", "T2"], "t1,t2"],
)
def test_expected_test_ids_must_equal_the_manifest_required_tests(work, ids):
    marker = os.path.join(work, "ran.txt")
    with pytest.raises(c.ContractError, match="expected_test_ids"):
        run(work, m=mf([marker_cmd(marker)]), commands=[marker_cmd(marker)], expected_test_ids=ids)
    assert not os.path.exists(marker)


def test_expected_test_ids_are_compared_as_a_set_not_by_order(work):
    r = run(work, expected_test_ids=["t2", "t1"])
    assert r["expected_test_ids"] == ["t2", "t1"] and r["result"] == "PASS"


def test_expected_ids_come_from_the_slot_of_the_manifest(work):
    m = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "tests2", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        required_tests=[
            {"slot": "tests", "test_id": "t1", "acceptance": ["AC-1"]},
            {"slot": "tests", "test_id": "t2", "acceptance": ["AC-1"]},
            {"slot": "tests2", "test_id": "u1", "acceptance": ["AC-2"]},
        ],
        allowed_commands=[
            {"slot": "tests", "argv": PASS_CMD},
            {"slot": "tests2", "argv": PASS_CMD},
        ],
    )
    with pytest.raises(c.ContractError, match="expected_test_ids"):
        run(work, m=m, slot="tests2", expected_test_ids=["t1", "t2"])
    r = run(work, m=m, slot="tests2", expected_test_ids=["u1"], test_result_parser=lambda s: (["u1"], [], []))
    assert r["slot"] == "tests2" and r["result"] == "PASS"


@pytest.mark.parametrize("slot", ["static", "review", "unknown", "__supervisor__", "", " "])
def test_slot_must_be_a_testrun_slot_of_the_manifest(work, slot):
    with pytest.raises(c.ContractError):
        run(work, slot=slot)


def test_covered_acceptance_must_be_a_subset_of_manifest_acceptance(work):
    with pytest.raises(c.ContractError, match="acceptance"):
        run(work, covered_acceptance=["AC-1", "AC-404"])
    assert run(work, covered_acceptance=[])["covered_acceptance"] == []
    assert run(work, covered_acceptance=["AC-2", "AC-1"])["result"] == "PASS"


def test_runner_does_not_bound_the_attempt_by_retry_cap_the_store_does(work):
    # Attempt numbers are global across epochs; the per-epoch bound lives in the store.
    m = mf([PASS_CMD], retry_cap=1)
    for attempt in (2, 3, 9):
        r = run(work, m=m, attempt=attempt, prev_receipt_sha256="e" * 64)
        assert r["attempt"] == attempt and r["result"] == "PASS" and signing.verify(r, KEY)
    m0 = mf([PASS_CMD], retry_cap=0)
    assert run(work, m=m0, attempt=2, prev_receipt_sha256="e" * 64)["attempt"] == 2
    assert run(work, m=m0)["attempt"] == 1
    with pytest.raises(c.ContractError, match="prev_receipt_sha256"):
        run(work, m=m0, attempt=2, prev_receipt_sha256=None)  # the chain rule is still enforced


def test_timeouts_are_bounded_by_the_manifest(work):
    m = mf([PASS_CMD], timeout_sec=5)
    assert run(work, m=m, timeout_sec=5)["result"] == "PASS"  # equal to the limit is fine
    assert run(work, m=m, timeout_sec=None)["result"] == "PASS"  # defaults to the manifest value
    for bad in (6, 0, -1, True, "5", 1.5):
        with pytest.raises(c.ContractError, match="timeout_sec"):
            run(work, m=m, timeout_sec=bad)
    for bad in (6, 0, True, "5"):
        with pytest.raises(c.ContractError, match="deadline_sec"):
            run(work, m=m, timeout_sec=None, deadline_sec=bad)
    assert run(work, m=m, timeout_sec=None, deadline_sec=5)["result"] == "PASS"


def test_invalid_or_foreign_manifests_are_rejected_before_running(work):
    marker = os.path.join(work, "ran.txt")
    good = mf([marker_cmd(marker)])
    broken = copy.deepcopy(good)
    del broken["allowed_commands"]
    extra = dict(good, surprise=1)
    no_review = copy.deepcopy(good)
    no_review["required_receipts"] = [{"slot": "tests", "receipt_type": "TestRun"}]
    for bad in (broken, extra, no_review, {}, None, "manifest", [good]):
        with pytest.raises(c.ContractError):
            run(work, m=bad, commands=[marker_cmd(marker)])
    assert not os.path.exists(marker)


def test_runner_does_not_mutate_the_manifest(work):
    m = mf([PASS_CMD])
    before = copy.deepcopy(m)
    run(work, m=m)
    assert m == before


# ---------------------------------------------------- invalid arguments (matrix)


INVALID_OVERRIDES = [
    {"slot": ""}, {"slot": " "}, {"slot": "nope"}, {"slot": "review"},
    {"resolved_model": ""}, {"invocation_id": None}, {"runner_id": 3}, {"created_at": ""},
    {"attempt": 0}, {"attempt": True}, {"attempt": "1"}, {"attempt": 2**31, "prev_receipt_sha256": "e" * 64},
    {"epoch": 0}, {"epoch": True}, {"epoch": 2**31},
    {"candidate_head": "xyz"}, {"candidate_head": "A" * 40},
    {"attempt": 2, "prev_receipt_sha256": None}, {"attempt": 2, "prev_receipt_sha256": "zz"},
    {"attempt": 1, "prev_receipt_sha256": "e" * 64},
    {"key": b""}, {"key": b"short"}, {"key": b"k" * 31}, {"key": "text" * 20}, {"key": None},
    {"commands": []}, {"commands": [[]]}, {"commands": [["x", ""]]}, {"commands": None},
    {"commands": "python"}, {"commands": [[1]]},
    {"expected_test_ids": "t1"}, {"expected_test_ids": [""]}, {"expected_test_ids": ["t1"]},
    {"covered_acceptance": [1]}, {"covered_acceptance": ["AC-9"]}, {"covered_acceptance": "AC-1"},
    {"artifact_paths": "a.txt"}, {"artifact_paths": [1]}, {"artifact_paths": [""]},
    {"artifact_paths": None}, {"artifact_paths": ["../x"]}, {"artifact_paths": ["a/../../x"]},
    {"artifact_paths": ["/abs.txt"]}, {"artifact_paths": ["\\abs.txt"]}, {"artifact_paths": ["C:/x.txt"]},
    {"artifact_paths": ["a", "a"]}, {"artifact_paths": ["a/./b"]}, {"artifact_paths": ["a//b"]},
    {"timeout_sec": 0}, {"timeout_sec": True}, {"timeout_sec": "5"}, {"timeout_sec": 10**6},
    {"deadline_sec": 0}, {"deadline_sec": True}, {"deadline_sec": 10**6},
    {"max_output_bytes": 0}, {"max_output_bytes": True}, {"max_output_bytes": runner.MAX_OUTPUT_BYTES_LIMIT + 1},
    {"cwd": None}, {"cwd": 5}, {"cwd": ""},
    {"test_result_parser": None}, {"test_result_parser": "x"},
    {"extra_env": "A=B"}, {"extra_env": {"A=B": "1"}}, {"extra_env": {"A": 1}}, {"extra_env": {"A": "x\0"}},
    {"extra_env": {"": "1"}},
    {"extra_env": {"A": "1"}}, {"extra_env": {"VST_ok": "1"}}, {"extra_env": {"vst_ok": "1"}},
    {"extra_env": {"PYTHONPYCACHEPREFIX": "/x"}}, {"extra_env": {"PYTHONUSERBASE": "/x"}},
    {"extra_env": {"PYTHONBREAKPOINT": "os.system"}}, {"extra_env": {"VST-X": "1"}},
    {"extra_env": {"VST_": "1"}}, {"extra_env": {" VST_X": "1"}}, {"extra_env": {"VST_X\n": "1"}},
]


@pytest.mark.parametrize(
    "over", INVALID_OVERRIDES, ids=[f"{i}-{next(iter(o))}" for i, o in enumerate(INVALID_OVERRIDES)]
)
def test_invalid_inputs_raise_before_any_subprocess_starts(work, over):
    marker = os.path.join(work, "ran.marker")
    cmd = marker_cmd(marker)
    kw = {"commands": [cmd], "allowed": [cmd], **over}
    with pytest.raises(c.ContractError):
        run(work, **kw)
    assert not os.path.exists(marker)


# ------------------------------------------------------ output cap (exit -3)


def test_output_over_the_cap_gives_exit_minus_three_and_fail(work):
    report = {}
    r, seen = captured(work, "import sys; sys.stdout.write('x' * 1001)", max_output_bytes=1000, report=report)
    assert r["commands"][0]["exit_code"] == runner.EXIT_OUTPUT_TRUNCATED == -3
    assert r["result"] == "FAIL"  # the parser reported both ids; only the truncation can fail it
    assert len(seen) == 1000  # the parser saw at most the cap
    assert report["commands"][0]["stdout_truncated"] is True
    assert report["commands"][0]["stderr_truncated"] is False
    assert signing.verify(r, KEY)


def test_output_exactly_at_the_cap_is_not_truncated(work):
    report = {}
    r, seen = captured(work, "import sys; sys.stdout.write('x' * 1000)", max_output_bytes=1000, report=report)
    assert r["commands"][0]["exit_code"] == 0 and r["result"] == "PASS"
    assert len(seen) == 1000 and report["commands"][0]["stdout_truncated"] is False


def test_stderr_has_its_own_cap(work):
    report = {}
    r, _ = captured(work, "import sys; sys.stderr.write('e' * 5000)", max_output_bytes=1000, report=report)
    assert r["commands"][0]["exit_code"] == -3 and r["result"] == "FAIL"
    assert report["commands"][0]["stderr_truncated"] is True
    assert report["commands"][0]["stdout_truncated"] is False


def test_stderr_within_cap_does_not_fail_a_passing_run(work):
    r, _ = captured(work, "import sys; sys.stderr.write('warning\\n')", max_output_bytes=1000)
    assert r["commands"][0]["exit_code"] == 0 and r["result"] == "PASS"


def test_truncated_exit_code_wins_over_a_failing_exit_code(work):
    r, _ = captured(work, "import sys; sys.stdout.write('x' * 5000); sys.exit(4)", max_output_bytes=1000)
    assert r["commands"][0]["exit_code"] == -3  # never trust a verdict derived from partial output


def test_default_cap_is_one_mebibyte(work):
    assert runner.DEFAULT_MAX_OUTPUT_BYTES == 1024 * 1024
    ok, seen = captured(work, f"import sys; sys.stdout.write('x' * {1024 * 1024})")
    assert ok["commands"][0]["exit_code"] == 0 and len(seen) == 1024 * 1024
    over, seen2 = captured(work, f"import sys; sys.stdout.write('x' * {1024 * 1024 + 1})")
    assert over["commands"][0]["exit_code"] == -3 and len(seen2) == 1024 * 1024


def test_output_flood_is_drained_without_deadlock_and_memory_is_bounded(work):
    started = time.monotonic()
    r, seen = captured(
        work,
        "import sys\nchunk = 'y' * 65536\nfor _ in range(80): sys.stdout.write(chunk); sys.stderr.write(chunk)",
        max_output_bytes=100,
    )
    assert time.monotonic() - started < 60
    assert r["commands"][0]["exit_code"] == -3 and len(seen) == 100


def test_ids_hidden_beyond_the_cap_cannot_produce_a_pass(work):
    code = "import sys; sys.stdout.write('z' * 2000); print('PASSED t1'); print('PASSED t2')"
    r = run(work, commands=[pycmd(code)], max_output_bytes=1000)
    assert r["commands"][0]["exit_code"] == -3
    assert r["executed_test_ids"] == [] and r["result"] == "INCONCLUSIVE"  # never PASS


# ------------------------------------------------- process tree kill / deadline


def test_timeout_kills_the_whole_process_tree(work, tmp_path):
    beat = str(tmp_path / "beat.txt")
    grandchild = (
        "import time\n"
        "while True:\n"
        f"    open({beat!r}, 'a').write('.')\n"
        "    time.sleep(0.2)\n"
    )
    parent = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}],"
        " stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "time.sleep(60)\n"
    )
    started = time.monotonic()
    r = run(work, commands=[pycmd(parent)], timeout_sec=3, test_result_parser=ALL_IDS)
    assert time.monotonic() - started < 40
    assert r["commands"][0]["exit_code"] == -1
    assert os.path.exists(beat) and os.path.getsize(beat) > 0, "grandchild never started; test proves nothing"
    time.sleep(1.0)  # five heartbeat periods: a surviving grandchild would keep writing
    size = os.path.getsize(beat)
    time.sleep(1.0)
    assert os.path.getsize(beat) == size, "grandchild survived the timeout kill"


def test_posix_worker_timeout_kills_descendant_across_uid_boundary():
    """VST-013 / E4.1: the runner must clean up worker descendants across UIDs."""
    if os.name != "posix":
        pytest.skip("POSIX process-group acceptance runs only inside the provisioned sandbox distro")

    import pwd
    try:
        runner_account = pwd.getpwnam("vst-runner")
        worker_account = pwd.getpwnam("vst-worker")
    except KeyError as exc:
        pytest.skip(f"provisioned S2 runner/worker account is unavailable: {exc}")
    if os.geteuid() != runner_account.pw_uid:
        pytest.skip("must run as the provisioned vst-runner identity")
    try:
        with open("/proc/self/status", encoding="ascii") as status_file:
            cap_eff_line = next(line for line in status_file if line.startswith("CapEff:"))
    except (OSError, StopIteration) as exc:
        pytest.skip(f"runner effective capabilities are unavailable: {exc}")
    cap_eff = int(cap_eff_line.split(":", 1)[1].strip(), 16)
    required_caps = (1 << 6) | (1 << 7)  # CAP_SETGID and CAP_SETUID for Popen identity switch
    if cap_eff & required_caps != required_caps:
        pytest.skip("runner lacks the provisioned CAP_SETGID/CAP_SETUID profile")
    if not os.path.isfile("/usr/bin/setpriv"):
        pytest.skip("the approved fixed-path /usr/bin/setpriv helper is unavailable")

    # Use a unique child of the sandbox's private tmpfs; the runner-created
    # directory is shared only so the switched worker can write its marker.
    if not os.path.isdir("/tmp") or os.stat("/tmp").st_mode & 0o1777 != 0o1777:
        pytest.skip("sandbox /tmp is not the expected private, sticky temporary filesystem")
    work = tempfile.mkdtemp(prefix="vst-s2-posix-cleanup-", dir="/tmp")
    os.chmod(work, 0o777)
    beat = os.path.join(work, "descendant-beat.txt")
    grandchild = (
        "import time\n"
        "deadline = time.monotonic() + 6\n"
        "while time.monotonic() < deadline:\n"
        f"    with open({beat!r}, 'a', encoding='ascii') as stream: stream.write('x')\n"
        "    time.sleep(0.1)\n"
    )
    parent = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}],"
        " stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        f"deadline = time.monotonic() + 2\nwhile not os.path.exists({beat!r}) and time.monotonic() < deadline:\n"
        "    time.sleep(0.02)\n"
        "print('WORKER_UID', os.geteuid(), flush=True)\n"
        "time.sleep(3.2)\n"
    )

    try:
        code, stdout, info = runner._run_one(
            pycmd(parent),
            work,
            3,
            {"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"},
            4096,
            worker_uid=worker_account.pw_uid,
            worker_gid=worker_account.pw_gid,
        )

        assert f"WORKER_UID {worker_account.pw_uid}" in stdout
        assert info["timed_out"] is True
        assert info["capture_incomplete"] is False, f"runner did not confirm cleanup: {info!r}"
        assert code == runner.EXIT_TIMEOUT
        assert os.path.exists(beat), "worker descendant never started; test proves nothing"
        final_size = os.path.getsize(beat)
        deadline = time.monotonic() + 0.8
        while time.monotonic() < deadline:
            assert os.path.getsize(beat) == final_size, (
                "worker descendant survived POSIX process-group timeout cleanup"
            )
            time.sleep(0.05)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_overall_deadline_stops_later_commands_without_running_them(work):
    marker = os.path.join(work, "second-ran.txt")
    slow = pycmd("import time; time.sleep(60)")
    second = marker_cmd(marker)
    m = mf([slow, second], timeout_sec=30)
    report = {}
    started = time.monotonic()
    r = run(work, m=m, commands=[slow, second], timeout_sec=30, deadline_sec=1, report=report,
            test_result_parser=ALL_IDS)
    assert time.monotonic() - started < 40
    assert [x["exit_code"] for x in r["commands"]] == [-1, -1]
    assert report["commands"][0]["timed_out"] is True
    assert report["commands"][1]["skipped_by_deadline"] is True
    assert not os.path.exists(marker)  # the second command never started
    assert r["result"] == "FAIL"


def test_deadline_limits_a_command_below_its_own_timeout(work):
    slow = pycmd("import time; time.sleep(60)")
    started = time.monotonic()
    r = run(work, m=mf([slow], timeout_sec=60), commands=[slow], timeout_sec=60, deadline_sec=1,
            test_result_parser=ALL_IDS)
    assert time.monotonic() - started < 40
    assert r["commands"][0]["exit_code"] == -1


def test_timeout_does_not_prevent_following_commands_within_the_deadline(work):
    slow = pycmd("import time; time.sleep(60)")
    ok = printer("PASSED t1", "PASSED t2")
    r = run(work, m=mf([slow, ok], timeout_sec=20), commands=[slow, ok], timeout_sec=1, deadline_sec=20)
    assert [x["exit_code"] for x in r["commands"]] == [-1, 0]
    assert r["result"] == "FAIL"  # but the failed command is on record


# ------------------------------------------------------------ minimal environment


def test_child_environment_is_minimal_and_secrets_do_not_leak(work, monkeypatch):
    monkeypatch.setenv("VST_FAKE_TOKEN", "leak-token-123")
    monkeypatch.setenv("GITHUB_TOKEN", "leak-github-456")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "leak-anthropic-789")
    monkeypatch.setenv("VST_WORKER_KEY", SECRET.decode())
    r, out = captured(work, "import os, json; print(json.dumps(sorted(os.environ)))")
    names = {n.upper() for n in json.loads(out.strip())}
    allowed = {n.upper() for n in runner.ENV_ALLOWLIST} | {"PYTHONIOENCODING"}
    assert names <= allowed | {"SYSTEMROOT"}, sorted(names - allowed)
    for secret in ("VST_FAKE_TOKEN", "GITHUB_TOKEN", "ANTHROPIC_API_KEY", "VST_WORKER_KEY"):
        assert secret not in names
    assert "PYTHONIOENCODING" in names
    r2, out2 = captured(work, "import os; print(dict(os.environ))")
    for leaked in ("leak-token-123", "leak-github-456", "leak-anthropic-789", SECRET.decode()):
        assert leaked not in out2


def test_extra_env_is_passed_explicitly_and_only_that(work, monkeypatch):
    monkeypatch.setenv("VST_NOT_PASSED", "no")
    r, out = captured(
        work, "import os; print(os.environ.get('VST_EXTRA'), os.environ.get('VST_NOT_PASSED'))",
        extra_env={"VST_EXTRA": "yes"},
    )
    assert out.strip() == "yes None"


def test_build_environment_unit(monkeypatch):
    monkeypatch.setenv("PATH", "/some/path")
    monkeypatch.setenv("VST_SECRET", "s")
    env = runner.build_environment({"VST_EXTRA": "1"})
    assert env["PATH"] == "/some/path" and env["VST_EXTRA"] == "1" and env["PYTHONIOENCODING"] == "utf-8"
    assert "VST_SECRET" not in env
    assert set(env) <= set(runner.ENV_ALLOWLIST) | {"PYTHONIOENCODING", "VST_EXTRA"}
    assert runner.build_environment() == runner.build_environment(None) == runner.build_environment({})


# ---------------------------------------------------- parser / test-id honesty


def test_mismatched_executed_vs_expected_is_not_pass(work):
    for executed in (["t1"], ["t1", "t2", "t3"], ["t1", "other"]):
        r = run(work, test_result_parser=lambda s, e=executed: (e, [], []))
        assert r["result"] == "FAIL", executed


def test_output_injection_of_extra_test_ids_does_not_make_pass(work):
    r = run(work, commands=[printer("PASSED t1", "PASSED t2", "PASSED t-forged")])
    assert "t-forged" in r["executed_test_ids"]
    assert r["result"] == "FAIL"


def test_output_injection_of_missing_ids_cannot_be_hidden(work):
    assert run(work, commands=[printer("PASSED t1")])["result"] == "FAIL"


def test_skipped_or_xfail_ids_prevent_pass(work):
    r1 = run(work, test_result_parser=lambda s: (["t1", "t2"], ["t3"], []))
    r2 = run(work, test_result_parser=lambda s: (["t1", "t2"], [], ["t4"]))
    assert r1["result"] == "FAIL" and r2["result"] == "FAIL"
    assert r1["skipped_test_ids"] == ["t3"] and r2["xfail_test_ids"] == ["t4"]


def test_zero_executed_is_inconclusive_not_pass(work):
    r = run(work, test_result_parser=lambda s: ([], [], []))
    assert r["result"] == "INCONCLUSIVE"
    assert signing.verify(r, KEY)


def test_parser_returning_blank_ids_is_rejected(work):
    with pytest.raises(c.ContractError):
        run(work, test_result_parser=lambda s: ([""], [], []))


def test_parser_exception_propagates_instead_of_silent_pass(work):
    def boom(_):
        raise RuntimeError("parser failed")

    with pytest.raises(RuntimeError):
        run(work, test_result_parser=boom)


def test_result_is_computed_not_caller_controlled(work):
    assert "result" not in inspect.signature(runner.run_and_sign).parameters
    r = run(work, commands=[printer("PASSED t1", "PASSED t2", exit_code=9)])
    assert r["result"] == "FAIL" and c.derive_result(r) == "FAIL"


# ------------------------------------------------------------- key hygiene


def test_key_never_appears_in_receipt(work):
    r = run(work, key=SECRET)
    blob = c.canonical_bytes(r)
    assert SECRET not in blob
    assert SECRET.hex().encode() not in blob
    assert base64.b64encode(SECRET) not in blob
    assert signing.verify(r, SECRET) and not signing.verify(r, KEY)


def test_runner_writes_nothing_under_cwd_and_key_not_on_disk(work):
    before = tree_bytes(work)
    run(work, key=SECRET)
    assert tree_bytes(work) == before == {}


def test_key_does_not_leak_into_cwd_even_with_preexisting_files(work):
    decoy = os.path.join(work, "key.txt")
    with open(decoy, "wb") as fh:
        fh.write(b"WRONG-KEY-FROM-WORKER-DIR-0123456789")
    before = tree_bytes(work)
    r = run(work, key=SECRET)
    after = tree_bytes(work)
    assert after == before
    assert all(SECRET not in blob for blob in after.values())
    assert signing.verify(r, SECRET)
    assert not signing.verify(r, b"WRONG-KEY-FROM-WORKER-DIR-0123456789")


def test_key_is_not_visible_to_the_child_process(work):
    r, out = captured(work, "import os,sys; print(os.environ); print(sys.argv)", key=SECRET)
    assert "TOP-SECRET" not in out


@pytest.mark.parametrize("key", [b"", b"short", b"k" * 31, "string-key" * 10, None, 12345])
def test_weak_or_non_bytes_keys_are_rejected_before_running(work, key):
    marker = os.path.join(work, "ran.txt")
    with pytest.raises(c.ContractError):
        run(work, key=key, commands=[marker_cmd(marker)])
    assert not os.path.exists(marker)


def test_exactly_32_byte_key_and_bytearray_are_accepted(work):
    k = b"k" * 32
    assert signing.verify(run(work, key=k), k)
    assert signing.verify(run(work, key=bytearray(k)), k)


# --------------------------------------------- signing semantics (label-scoped)


def _mutate(v):
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + 1
    if isinstance(v, str):
        return v + "x"
    if isinstance(v, list):
        return v + ["extra"]
    if isinstance(v, dict):
        return {**v, "extra-path": "a" * 64}
    if v is None:
        return "x"
    raise AssertionError(type(v))


def test_signature_verifies_and_is_64_hex(work):
    r = run(work)
    assert signing.verify(r, KEY)
    assert len(r["signature"]) == 64 and set(r["signature"]) <= set("0123456789abcdef")


def test_signature_is_deterministic_for_same_inputs(work):
    assert run(work)["signature"] == run(work)["signature"]


def test_every_field_tamper_breaks_verification(work):
    r = run(work, attempt=2, prev_receipt_sha256="e" * 64)
    assert "manifest_sha256" in r
    for field in r:
        t = copy.deepcopy(r)
        t[field] = _mutate(t[field])
        assert not signing.verify(t, KEY), field


def test_nested_command_tamper_breaks_verification(work):
    r = run(work)
    t1 = copy.deepcopy(r)
    t1["commands"][0]["exit_code"] = 1
    t2 = copy.deepcopy(r)
    t2["commands"][0]["argv"].append("--more")
    assert not signing.verify(t1, KEY) and not signing.verify(t2, KEY)


def test_signature_is_scoped_to_the_receipt_label(work):
    r = run(work)
    body = runner.receipt_without_signature(r)
    expected = hmac.new(KEY, signing.RECEIPT_LABEL + c.canonical_bytes(body), hashlib.sha256).hexdigest()
    assert r["signature"] == expected
    unlabeled = hmac.new(KEY, c.canonical_bytes(body), hashlib.sha256).hexdigest()
    assert r["signature"] != unlabeled
    assert signing.verify(r, KEY, signing.RECEIPT_LABEL)
    assert not signing.verify(r, KEY, signing.WAIVER_LABEL)  # a receipt is never a waiver
    # a receipt body signed under the waiver label does not verify as a receipt
    cross = dict(body, signature=signing.sign(body, KEY, signing.WAIVER_LABEL))
    assert not signing.verify(cross, KEY)
    # and the old unlabeled scheme is dead
    assert not signing.verify(dict(body, signature=unlabeled), KEY)


def test_labels_are_distinct_domain_separators():
    assert signing.RECEIPT_LABEL != signing.WAIVER_LABEL
    assert signing.RECEIPT_LABEL and signing.WAIVER_LABEL
    body = runner.receipt_without_signature(receipt())
    assert len({signing.sign(body, KEY), signing.sign(body, KEY, signing.WAIVER_LABEL),
                signing.sign(body, KEY, b"custom-label\0")}) == 3


def test_wrong_key_fails_and_bad_key_raises(work):
    r = run(work)
    assert not signing.verify(r, WRONG_KEY)
    assert not signing.verify(r, OPERATOR_KEY) and not signing.verify(r, SUPERVISOR_KEY)
    for bad in (b"", b"short", b"k" * 31, "text", None):
        with pytest.raises(c.ContractError):
            signing.verify(r, bad)
        with pytest.raises(c.ContractError):
            signing.sign(runner.receipt_without_signature(r), bad)


def test_bad_label_raises():
    body = runner.receipt_without_signature(receipt())
    for bad in (b"", "text", None):
        with pytest.raises(c.ContractError):
            signing.sign(body, KEY, bad)
        with pytest.raises(c.ContractError):
            signing.verify(receipt(), KEY, bad)


def test_min_key_bytes_boundary():
    assert signing.MIN_KEY_BYTES == 32
    body = runner.receipt_without_signature(receipt())
    with pytest.raises(c.ContractError):
        signing.sign(body, b"k" * 31)
    assert len(signing.sign(body, b"k" * 32)) == 64


def test_verify_non_dict_or_bad_signature_is_false_not_error():
    assert signing.verify("x", KEY) is False
    r = receipt()
    for bad in (None, 5, ["a"]):
        assert signing.verify(dict(r, signature=bad), KEY) is False
    no_sig = {k: v for k, v in r.items() if k != "signature"}
    assert signing.verify(no_sig, KEY) is False


def test_sign_refuses_receipt_that_already_has_signature():
    with pytest.raises(c.ContractError):
        signing.sign(receipt(), KEY)
    with pytest.raises(c.ContractError):
        signing.sign("not-a-dict", KEY)


def test_sign_matches_independent_hmac_over_label_and_canonical_bytes():
    body = runner.receipt_without_signature(receipt())
    expected = hmac.new(KEY, b"vst-receipt-v1\0" + c.canonical_bytes(body), hashlib.sha256).hexdigest()
    assert signing.sign(body, KEY) == expected
    assert signing.sign(body, bytearray(KEY)) == expected


def test_receipt_without_signature_helper_does_not_mutate():
    r = receipt()
    body = runner.receipt_without_signature(r)
    assert "signature" not in body and "signature" in r


# ------------------------------------- gate integration (replay, forgery, chain)


def gate_eval(m, receipts, *, head=HEAD, epoch=EPOCH, key=KEY, **kw):
    return gate.evaluate(m, receipts, head, epoch, key, supervisor_key=SUPERVISOR_KEY, **kw)


def full_set(m, run_receipt):
    """The runner's TestRun receipt plus the other slots of manifest m (bound to m)."""
    return [run_receipt, bound(m, "StaticAnalysis"), bound(m, "IndependentReview")]


def test_runner_receipt_is_approved_by_gate_at_its_head_and_epoch(work):
    m = mf([PASS_CMD])
    r = run(work, m=m)
    d = gate_eval(m, full_set(m, r))
    assert d["verdict"] == "APPROVE", d["reasons"]
    assert c.receipt_sha256(r) in d["required_receipt_hashes"]


def test_replay_against_another_head_is_rejected(work):
    m = mf([PASS_CMD])
    d = gate_eval(m, full_set(m, run(work, m=m)), head=HEAD2)
    assert d["verdict"] == "NO_GO" and "stale head" in " ".join(d["reasons"])


def test_replay_against_another_epoch_is_rejected(work):
    m = mf([PASS_CMD])
    d = gate_eval(m, full_set(m, run(work, m=m)), epoch=EPOCH - 1)
    assert d["verdict"] != "APPROVE" and "future epoch" in " ".join(d["reasons"])


def test_replay_against_another_task_is_rejected(work):
    m = mf([PASS_CMD])
    other = mf([PASS_CMD], task_id="OTHER")
    d = gate_eval(other, full_set(m, run(work, m=m)))
    assert d["verdict"] != "APPROVE"
    assert "belongs to another task" in " ".join(d["reasons"])


def test_replay_against_a_changed_manifest_is_rejected(work):
    m = mf([PASS_CMD])
    r = run(work, m=m)
    changed = mf([PASS_CMD], scope=["src/changed.py"])  # same task, different manifest
    d = gate_eval(changed, [r, bound(changed, "StaticAnalysis"), bound(changed, "IndependentReview")])
    assert d["verdict"] != "APPROVE"
    assert "manifest_sha256 does not match" in " ".join(d["reasons"])


def test_manifest_swapped_to_widen_allowed_commands_is_rejected_by_hash(work):
    m = mf([PASS_CMD])
    r = run(work, m=m)
    widened = mf([PASS_CMD, pycmd("print('extra power')")])
    d = gate_eval(widened, [r, bound(widened, "StaticAnalysis"), bound(widened, "IndependentReview")])
    assert d["verdict"] != "APPROVE"
    assert "manifest_sha256 does not match" in " ".join(d["reasons"])


def test_forged_unsigned_and_wrong_key_receipts_are_rejected(work):
    m = mf([PASS_CMD])
    r = run(work, m=m)
    forged = dict(r, signature="0" * 64)
    other_key = run(work, m=m, key=b"attacker-key-0123456789-abcdefghijk")
    for bad in (forged, other_key):
        d = gate_eval(m, full_set(m, bad))
        assert d["verdict"] == "MODIFY"
        assert "invalid signature" in " ".join(d["reasons"])


def test_worker_receipt_cannot_masquerade_as_supervisor_or_waiver_signed(work):
    m = mf([PASS_CMD])
    r = run(work, m=m)
    body = runner.receipt_without_signature(r)
    relabeled = dict(body, signature=signing.sign(body, KEY, signing.WAIVER_LABEL))
    d = gate_eval(m, full_set(m, relabeled))
    assert d["verdict"] == "MODIFY" and "invalid signature" in " ".join(d["reasons"])
    d2 = gate_eval(m, full_set(m, r), key=WRONG_KEY)  # gate holding the wrong worker key
    assert "invalid signature" in " ".join(d2["reasons"])
    # a gate whose worker key equals the supervisor key is refused outright (NO_GO)
    d3 = gate_eval(m, full_set(m, r), key=SUPERVISOR_KEY)
    assert d3["verdict"] == "NO_GO"


def test_edited_exit_code_after_signing_is_rejected(work):
    failing = printer("PASSED t1", "PASSED t2", exit_code=1)
    m = mf([failing])
    r = run(work, m=m, commands=[failing])
    assert r["result"] == "FAIL"
    t = copy.deepcopy(r)
    t["commands"][0]["exit_code"] = 0
    t["result"] = "PASS"
    d = gate_eval(m, full_set(m, t))
    assert d["verdict"] == "MODIFY" and "invalid signature" in " ".join(d["reasons"])


def test_retry_after_fail_through_runner_is_approved_with_retained_failure(work):
    bad_cmd = printer("PASSED t1", exit_code=1)
    m = mf([bad_cmd, PASS_CMD], retry_cap=1)
    first = run(work, m=m, commands=[bad_cmd], invocation_id="i1")
    assert first["result"] == "FAIL"
    second = run(work, m=m, attempt=2, prev_receipt_sha256=c.receipt_sha256(first), invocation_id="i2")
    d = gate_eval(m, [first, second, bound(m, "StaticAnalysis"), bound(m, "IndependentReview")])
    assert d["verdict"] == "APPROVE", d["reasons"]
    assert d["unresolved_findings"] == ["earlier failure retained: tests attempt 1 FAIL"]


def test_retry_with_wrong_prev_hash_is_rejected(work):
    bad_cmd = printer("PASSED t1", exit_code=1)
    m = mf([bad_cmd, PASS_CMD])
    first = run(work, m=m, commands=[bad_cmd], invocation_id="i1")
    second = run(work, m=m, attempt=2, prev_receipt_sha256="e" * 64, invocation_id="i2")
    d = gate_eval(m, [first, second, bound(m, "StaticAnalysis"), bound(m, "IndependentReview")])
    assert d["verdict"] == "MODIFY" and "attempt chain broken" in " ".join(d["reasons"])


def test_zero_executed_receipt_never_satisfies_gate(work):
    m = mf([PASS_CMD])
    d = gate_eval(m, full_set(m, run(work, m=m, test_result_parser=lambda s: ([], [], []))))
    assert d["verdict"] == "MODIFY"
    assert "slot 'tests' latest attempt 1 result INCONCLUSIVE" in d["reasons"]


# ------------------------------------------------------------- file digests


def test_file_sha256_known_vectors(tmp_path):
    p = tmp_path / "abc.bin"
    p.write_bytes(b"abc")
    assert runner.file_sha256(str(p)) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    e = tmp_path / "empty.bin"
    e.write_bytes(b"")
    assert runner.file_sha256(str(e)) == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("size", [1, 65535, 65536, 65537, 200_000])
def test_file_sha256_chunk_boundaries_match_hashlib(tmp_path, size):
    data = bytes((i * 7 + 3) % 256 for i in range(size))
    p = tmp_path / f"f{size}.bin"
    p.write_bytes(data)
    assert runner.file_sha256(str(p)) == hashlib.sha256(data).hexdigest()


def test_file_sha256_detects_one_byte_modification(tmp_path):
    p = tmp_path / "artifact.bin"
    data = b"x" * 100_000
    p.write_bytes(data)
    before = runner.file_sha256(str(p))
    p.write_bytes(data[:50_000] + b"y" + data[50_001:])
    assert runner.file_sha256(str(p)) != before


def test_file_sha256_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        runner.file_sha256(str(tmp_path / "nope"))


def test_artifact_digests_maps_each_path(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_bytes(b"AAA")
    b.write_bytes(b"BBB")
    out = runner.artifact_digests([str(a), str(b)])
    assert out == {str(a): hashlib.sha256(b"AAA").hexdigest(), str(b): hashlib.sha256(b"BBB").hexdigest()}
    assert runner.artifact_digests([]) == {}
    b.write_bytes(b"BBC")
    assert runner.artifact_digests([str(a), str(b)])[str(b)] != out[str(b)]
    assert runner.artifact_digests([str(a), str(b)])[str(a)] == out[str(a)]


# --------------------------------------------------- artifacts and containment


def test_artifacts_are_hashed_after_the_commands_ran(work):
    build = pycmd("open('out.txt','wb').write(b'built-by-command')")
    r = run(work, m=mf([build, PASS_CMD]), commands=[build, PASS_CMD], artifact_paths=["out.txt"])
    assert r["artifact_digests"] == {"out.txt": hashlib.sha256(b"built-by-command").hexdigest()}
    assert r["result"] == "PASS" and signing.verify(r, KEY)


def test_nested_relative_artifact_is_hashed(work):
    build = pycmd("import os; os.makedirs('sub/dir'); open('sub/dir/o.bin','wb').write(b'nested')")
    r = run(work, m=mf([build, PASS_CMD]), commands=[build, PASS_CMD], artifact_paths=["sub/dir/o.bin"])
    assert r["artifact_digests"] == {"sub/dir/o.bin": hashlib.sha256(b"nested").hexdigest()}


def test_empty_artifact_paths_gives_empty_digests(work):
    assert run(work)["artifact_digests"] == {}


def test_missing_artifact_gets_zero_digest_and_fail(work):
    r = run(work, artifact_paths=["never-built.bin"])
    assert r["artifact_digests"] == {"never-built.bin": "0" * 64}
    assert r["result"] == "FAIL"  # everything else would pass
    assert signing.verify(r, KEY)


def test_artifact_in_missing_directory_is_zero_digest(work):
    r = run(work, artifact_paths=["no/such/dir/x.bin"])
    assert r["artifact_digests"]["no/such/dir/x.bin"] == "0" * 64 and r["result"] == "FAIL"


def test_directory_is_not_an_artifact_and_gets_zero_digest(work):
    os.mkdir(os.path.join(work, "adir"))
    r = run(work, artifact_paths=["adir"])
    assert r["artifact_digests"] == {"adir": "0" * 64} and r["result"] == "FAIL"


@pytest.mark.parametrize(
    "path",
    ["../escape.txt", "a/../../escape.txt", "/etc/passwd", "\\windows\\win.ini", "C:/Windows/win.ini",
     "C:rel.txt", "a/./b", "a//b", " lead.txt", "trail.txt "],
)
def test_traversal_absolute_and_malformed_artifact_paths_are_refused_before_running(work, path):
    marker = os.path.join(work, "ran.txt")
    cmd = marker_cmd(marker)
    with pytest.raises(c.ContractError):
        run(work, m=mf([cmd]), commands=[cmd], artifact_paths=[path])
    assert not os.path.exists(marker)


def test_absolute_path_inside_the_run_directory_is_still_refused(work):
    inside = os.path.join(work, "inside.bin")
    with open(inside, "wb") as fh:
        fh.write(b"abs")
    with pytest.raises(c.ContractError):
        run(work, artifact_paths=[inside])


def test_artifact_through_a_symlink_or_junction_to_outside_is_refused(work, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"outside secret")
    link = os.path.join(work, "linkdir")
    if not _try_dir_link(link, str(outside)):
        pytest.skip("cannot create a symlink or junction on this machine")
    marker = os.path.join(work, "ran.txt")
    cmd = marker_cmd(marker)
    with pytest.raises(c.ContractError, match="symlink|escapes"):
        run(work, m=mf([cmd]), commands=[cmd], artifact_paths=["linkdir/secret.txt"])
    assert not os.path.exists(marker)  # refused before any command ran
    assert runner.contained_artifact_path(work, "linkdir/secret.txt") is None
    assert runner.contained_artifact_path(work, "linkdir") is None


def test_artifact_through_an_internal_symlink_is_also_refused(work):
    real = os.path.join(work, "real")
    os.mkdir(real)
    with open(os.path.join(real, "f.txt"), "wb") as fh:
        fh.write(b"inside")
    link = os.path.join(work, "inner-link")
    if not _try_dir_link(link, real):
        pytest.skip("cannot create a symlink or junction on this machine")
    with pytest.raises(c.ContractError):
        run(work, artifact_paths=["inner-link/f.txt"])  # links are refused even if they stay inside
    r = run(work, artifact_paths=["real/f.txt"])
    assert r["artifact_digests"] == {"real/f.txt": hashlib.sha256(b"inside").hexdigest()}


def test_link_created_by_the_command_itself_gets_a_zero_digest(work, tmp_path):
    if not _can_symlink(tmp_path):
        pytest.skip("os.symlink is not permitted on this machine")
    outside = tmp_path / "outside2"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"outside secret")
    code = f"import os; os.symlink({str(outside)!r}, 'late-link', target_is_directory=True)"
    cmd = pycmd(code)
    r = run(work, m=mf([cmd, PASS_CMD]), commands=[cmd, PASS_CMD], artifact_paths=["late-link/secret.txt"])
    assert r["artifact_digests"] == {"late-link/secret.txt": "0" * 64}
    assert r["result"] == "FAIL"


def test_contained_artifact_path_unit(work):
    assert runner.contained_artifact_path(work, "new.bin") == os.path.join(os.path.realpath(work), "new.bin")
    assert runner.contained_artifact_path(work, "a/b/c.bin") is not None  # not yet existing is fine
    open(os.path.join(work, "f"), "wb").close()
    assert runner.contained_artifact_path(work, "f") is not None


def test_modified_artifact_is_rejected_by_gate_resolver(work):
    m = mf([PASS_CMD])
    art = os.path.join(work, "art.bin")
    with open(art, "wb") as fh:
        fh.write(b"v1")
    r = run(work, m=m, artifact_paths=["art.bin"])

    def resolver(p):
        return runner.file_sha256(os.path.join(work, p))

    ok = gate_eval(m, full_set(m, r), artifact_resolver=resolver)
    assert ok["verdict"] == "APPROVE", ok["reasons"]
    with open(art, "wb") as fh:
        fh.write(b"v2-tampered")
    bad = gate_eval(m, full_set(m, r), artifact_resolver=resolver)
    assert bad["verdict"] == "MODIFY" and "digest mismatch" in " ".join(bad["reasons"])


def test_deleted_artifact_is_rejected_by_gate_resolver(work):
    m = mf([PASS_CMD])
    art = os.path.join(work, "art.bin")
    with open(art, "wb") as fh:
        fh.write(b"v1")
    r = run(work, m=m, artifact_paths=["art.bin"])
    os.remove(art)

    def resolver(p):
        try:
            return runner.file_sha256(os.path.join(work, p))
        except OSError:
            return None

    assert gate_eval(m, full_set(m, r), artifact_resolver=resolver)["verdict"] == "MODIFY"


def test_artifact_digest_receipt_is_denied_without_a_resolver(work):
    m = mf([PASS_CMD])
    art = os.path.join(work, "art.bin")
    with open(art, "wb") as fh:
        fh.write(b"v1")
    r = run(work, m=m, artifact_paths=["art.bin"])
    d = gate_eval(m, full_set(m, r))  # no artifact_resolver
    assert d["verdict"] != "APPROVE"
    assert "artifact digests present but no artifact_resolver" in d["reasons"]


def test_artifact_digest_tamper_after_signing_is_rejected(work):
    m = mf([PASS_CMD])
    with open(os.path.join(work, "art.bin"), "wb") as fh:
        fh.write(b"v1")
    r = run(work, m=m, artifact_paths=["art.bin"])
    t = copy.deepcopy(r)
    t["artifact_digests"]["art.bin"] = hashlib.sha256(b"forged").hexdigest()
    assert not signing.verify(t, KEY)
    d = gate_eval(m, full_set(m, t), artifact_resolver=lambda p: hashlib.sha256(b"forged").hexdigest())
    assert d["verdict"] == "MODIFY" and "invalid signature" in " ".join(d["reasons"])


# --------------------------------------------------------------- OS errors


@pytest.mark.parametrize(
    "exc",
    [FileNotFoundError("x"), NotADirectoryError("x"), PermissionError("x"), OSError("other"), OSError(22, "invalid")],
    ids=["FileNotFound", "NotADirectory", "Permission", "OSError", "OSError22"],
)
def test_os_errors_starting_a_process_map_to_exit_minus_two(work, monkeypatch, exc):
    def fake_popen(*a, **k):
        raise exc

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    r = run(work, test_result_parser=ALL_IDS)
    assert r["commands"][0]["exit_code"] == -2
    assert r["result"] == "FAIL" and signing.verify(r, KEY)


def test_non_os_errors_from_subprocess_propagate(work, monkeypatch):
    def fake_popen(*a, **k):
        raise RuntimeError("not an OS error")

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    with pytest.raises(RuntimeError):
        run(work)


# ----------------------------------------------------- extra_env shadowing (C2)

SHADOW_NAMES = [
    "PYTHONPYCACHEPREFIX", "PYTHONUSERBASE", "PYTHONBREAKPOINT", "PYTHONWARNINGS", "PYTHONSAFEPATH",
    "Vst_Mixed", "vst_lower", "VST_lower", "VST_", "VST", "VSTX", "XVST_A", "VST-A", "VST_A B",
    "VST_\u00c9", "PATH", "path", "Path", "PYTHONPATH", "pythonpath", "PyThOnPaTh", "PYTHONSTARTUP",
    "PYTHONHOME", "PYTEST_ADDOPTS", "pytest_plugins", "LD_PRELOAD", "ld_library_path",
    "DYLD_INSERT_LIBRARIES", "dyld_library_path", "DYLD_X", "dyld_",
    "PATHEXT", "SYSTEMROOT", "SystemRoot", "SYSTEMDRIVE", "WINDIR", "TEMP", "tmp", "TMPDIR",
    "LANG", "lc_all",
]


@pytest.mark.parametrize("name", SHADOW_NAMES)
def test_extra_env_that_shadows_loader_or_allowlisted_names_is_refused_before_running(work, name):
    marker = os.path.join(work, "ran.txt")
    cmd = marker_cmd(marker)
    parsed = []

    def parser(stdout):
        parsed.append(stdout)
        return ["t1", "t2"], [], []

    with pytest.raises(c.ContractError) as exc:
        run(work, m=mf([cmd]), commands=[cmd], extra_env={name: "x"}, test_result_parser=parser)
    assert isinstance(exc.value, ValueError)
    assert not os.path.exists(marker), "the command ran although extra_env was invalid"
    assert parsed == []


def test_extra_env_with_one_forbidden_key_among_good_ones_is_refused_as_a_whole(work):
    marker = os.path.join(work, "ran.txt")
    cmd = marker_cmd(marker)
    with pytest.raises(c.ContractError):
        run(work, m=mf([cmd]), commands=[cmd], extra_env={"VST_OK": "1", "PYTHONPATH": "/evil"})
    with pytest.raises(c.ContractError):
        run(work, m=mf([cmd]), commands=[cmd], extra_env={"VST_OK": "1", "vst_bad": "1"})
    assert not os.path.exists(marker)


@pytest.mark.parametrize("name", ["MYPATH", "PATH_EXTRA", "PYTHONPATHX", "XDYLD_FOO", "LANGUAGE_X"])
def test_extra_env_names_outside_the_vst_namespace_are_refused_even_if_harmless(work, name):
    marker = os.path.join(work, "ran.txt")
    cmd = marker_cmd(marker)
    with pytest.raises(c.ContractError, match=r"VST_\[A-Z0-9_\]\+"):
        run(work, m=mf([cmd]), commands=[cmd], extra_env={name: "x"})
    assert not os.path.exists(marker)


@pytest.mark.parametrize("name", ["VST_LANG", "VST_A", "VST_A1_B2", "VST_0", "VST___"])
def test_extra_env_vst_upper_case_names_are_passed_to_the_child(work, name):
    r, out = captured(
        work, f"import os; print(os.environ.get({name!r}))", extra_env={name: "kept"}
    )
    assert out.strip() == "kept" and r["commands"][0]["exit_code"] == 0


def test_extra_env_allowlist_is_the_documented_pattern():
    assert runner._EXTRA_ENV_NAME.pattern == "VST_[A-Z0-9_]+"
    assert runner._EXTRA_ENV_NAME.fullmatch("VST_A") and not runner._EXTRA_ENV_NAME.fullmatch("VST_A\n")


def test_forbidden_env_name_sets_cover_the_documented_names():
    assert set(runner.ENV_ALLOWLIST) <= set(runner.FORBIDDEN_ENV_NAMES)
    for name in ("PATH", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTEST_ADDOPTS",
                 "PYTEST_PLUGINS", "LD_PRELOAD", "LD_LIBRARY_PATH"):
        assert name in runner.FORBIDDEN_ENV_NAMES
    assert "DYLD_" in runner.FORBIDDEN_ENV_PREFIXES


def test_malformed_extra_env_is_still_a_contract_error(work):
    for bad in ({"A=B": "x"}, {"": "x"}, {"A": 1}, {1: "x"}, {"A\0": "x"}, {"A": "v\0"}, ["A"], "A=1",
                {"VST_A": 1}, {"VST_A": "v\0"}, {"VST_A=B": "x"}):
        with pytest.raises(c.ContractError):
            run(work, extra_env=bad)


# ---------------------------------------------- capture completeness (-4) (C2)


def _holder_command(hold_sec, flood_bytes=0):
    """Child that leaves a background process holding stdout/stderr, then exits 0.

    The background process starts in its own session on POSIX (so the runner's
    process-group kill cannot reach it). On Windows the Job Object would kill
    it, so tests that need it to survive use the no_stray_kill fixture (job and
    taskkill disabled). It prints its pid so the test can clean up, and ends by itself after
    `hold_sec` seconds (no leak even if the test fails).
    """
    holder = f"import time; time.sleep({hold_sec})"
    return pycmd(
        "import subprocess, sys, os\n"
        f"sys.stdout.write('x' * {flood_bytes}); sys.stdout.flush()\n"
        "kw = {'start_new_session': True} if os.name != 'nt' else {}\n"
        f"p = subprocess.Popen([sys.executable, '-c', {holder!r}], stdin=subprocess.DEVNULL,"
        " stdout=sys.stdout, stderr=sys.stderr, **kw)\n"
        "print('HOLDER_PID', p.pid); sys.stdout.flush()\n"
        "sys.exit(0)\n"
    )


def _kill_holder(stdout):
    for line in stdout.splitlines():
        if "HOLDER_PID " in line:
            try:
                os.kill(int(line.split("HOLDER_PID ")[1].split()[0]), 9)
            except (OSError, ValueError, IndexError):
                pass


@pytest.fixture
def no_stray_kill(monkeypatch):
    """Hermetic capture-incomplete setup: the post-exit kill and the Windows Job
    Object are disabled and the reader join is short, so a background holder reliably outlives the join on
    every platform (independent of how well the OS finds descendants)."""
    monkeypatch.setattr(runner, "_JOIN_SEC", 0.5)
    monkeypatch.setattr(runner, "_taskkill_tree", lambda pid: None)
    monkeypatch.setattr(runner.os, "killpg", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(runner._JobObject, "attach", classmethod(lambda cls, proc: None))


def test_background_process_holding_the_pipe_gives_exit_minus_four_and_capture_incomplete(
    work, no_stray_kill
):
    cmd = _holder_command(hold_sec=8)
    seen = []

    def parser(stdout):
        seen.append(stdout)
        return ["t1", "t2"], [], []

    report = {}
    started = time.monotonic()
    m = mf([cmd])
    try:
        r = run(work, m=m, commands=[cmd], test_result_parser=parser, report=report)
    finally:
        if seen:
            _kill_holder(seen[0])
    assert time.monotonic() - started < 30
    assert r["commands"][0]["exit_code"] == runner.EXIT_CAPTURE_INCOMPLETE == -4
    assert report["capture_incomplete"] is True
    assert report["commands"][0]["capture_incomplete"] is True
    assert report["commands"][0]["timed_out"] is False
    # fail-closed: the parser reported every id, yet the result is not PASS
    assert r["result"] == "FAIL"
    assert signing.verify(r, KEY)
    assert gate_eval(m, full_set(m, r))["verdict"] != "APPROVE"


def test_capture_incomplete_takes_precedence_over_output_truncation(work, no_stray_kill):
    cmd = _holder_command(hold_sec=8, flood_bytes=5000)
    seen = []

    def parser(stdout):
        seen.append(stdout)
        return ["t1", "t2"], [], []

    report = {}
    try:
        r = run(work, m=mf([cmd]), commands=[cmd], test_result_parser=parser,
                report=report, max_output_bytes=100)
    finally:
        if seen:
            _kill_holder(seen[0])
    assert report["commands"][0]["stdout_truncated"] is True
    assert r["commands"][0]["exit_code"] == -4  # not -3
    assert report["capture_incomplete"] is True


def test_a_short_lived_background_holder_is_fully_captured_and_not_flagged(work):
    cmd = _holder_command(hold_sec=1)
    report = {}
    seen = []

    def parser(stdout):
        seen.append(stdout)
        return ["t1", "t2"], [], []

    r = run(work, m=mf([cmd]), commands=[cmd], test_result_parser=parser, report=report)
    assert r["commands"][0]["exit_code"] == 0
    assert report["capture_incomplete"] is False
    assert "HOLDER_PID" in seen[0]
    assert r["result"] == "PASS"


def test_report_capture_incomplete_is_false_for_every_normal_outcome(work):
    report = {}
    run(work, commands=[printer("PASSED t1", "PASSED t2", exit_code=3)], report=report)
    assert report["capture_incomplete"] is False
    report = {}
    slow = pycmd("import time; time.sleep(60)")
    run(work, m=mf([slow], timeout_sec=20), commands=[slow], timeout_sec=1, deadline_sec=5,
        report=report, test_result_parser=ALL_IDS)
    assert report["commands"][0]["timed_out"] is True
    assert report["capture_incomplete"] is False  # a killed tree closes its pipes


# --------------------------------------------- post-exit tree kill (Windows) (C2)


def test_stray_descendant_is_killed_after_the_root_command_exited_normally(work, tmp_path):
    beat = str(tmp_path / "beat-after-exit.txt")
    grandchild = (
        "import time\n"
        "for _ in range(150):\n"  # bounded: ends by itself after ~30 s even if never killed
        f"    open({beat!r}, 'a').write('.')\n"
        "    time.sleep(0.2)\n"
    )
    parent = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {grandchild!r}],"
        " stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "t0 = time.time()\n"
        f"while not os.path.exists({beat!r}) and time.time() - t0 < 20:\n"
        "    time.sleep(0.05)\n"
        "sys.exit(0)\n"  # the root exits normally while the grandchild is alive
    )
    report = {}
    r = run(work, commands=[pycmd(parent)], test_result_parser=ALL_IDS, report=report)
    assert r["commands"][0]["exit_code"] == 0
    if os.name == "nt":
        assert report["commands"][0]["job_object"] is True, "Windows Job Object was not attached"
    assert os.path.exists(beat) and os.path.getsize(beat) > 0, "grandchild never started; test proves nothing"
    time.sleep(1.5)  # grace for the OS to finish terminating the tree
    size = os.path.getsize(beat)
    time.sleep(1.5)  # seven heartbeat periods: a surviving grandchild would keep writing
    assert os.path.getsize(beat) == size, "a stray descendant outlived the command after a normal exit"


# ------------------------------------------- third round: capture and cleanup


class _BoomStream:
    """Wraps the real pipe; read() raises `exc`, close() closes the real pipe."""

    def __init__(self, real, exc):
        self._real, self._exc = real, exc

    def read(self, n=-1):
        raise self._exc

    def close(self):
        self._real.close()


def _patch_popen(monkeypatch, wrap):
    real_popen = subprocess.Popen
    made = []

    def fake(*a, **k):
        proc = real_popen(*a, **k)
        made.append(proc)
        wrap(proc)
        return proc

    monkeypatch.setattr(runner.subprocess, "Popen", fake)
    return made


@pytest.mark.parametrize(
    "exc", [RuntimeError("boom"), KeyError("k"), MemoryError(), TypeError("t")],
    ids=["RuntimeError", "KeyError", "MemoryError", "TypeError"],
)
def test_reader_exception_other_than_oserror_marks_capture_incomplete(work, monkeypatch, exc):
    _patch_popen(monkeypatch, lambda p: setattr(p, "stdout", _BoomStream(p.stdout, exc)))
    report = {}
    r = run(work, test_result_parser=ALL_IDS, report=report)
    assert r["commands"][0]["exit_code"] == runner.EXIT_CAPTURE_INCOMPLETE == -4
    assert report["capture_incomplete"] is True and report["commands"][0]["capture_incomplete"] is True
    assert r["result"] == "FAIL" and signing.verify(r, KEY)  # the parser claimed both ids: still not PASS


@pytest.mark.parametrize("exc", [OSError("io"), ValueError("closed file")], ids=["OSError", "ValueError"])
def test_reader_oserror_and_valueerror_also_mark_capture_incomplete(work, monkeypatch, exc):
    _patch_popen(monkeypatch, lambda p: setattr(p, "stderr", _BoomStream(p.stderr, exc)))
    report = {}
    r = run(work, test_result_parser=ALL_IDS, report=report)
    assert r["commands"][0]["exit_code"] == -4 and report["capture_incomplete"] is True


def test_a_healthy_capture_is_not_flagged_when_nothing_raises(work):
    report = {}
    r = run(work, report=report)
    assert r["commands"][0]["exit_code"] == 0 and report["capture_incomplete"] is False


def test_root_that_survives_the_kill_gives_exit_minus_four(work, monkeypatch):
    # The kill is neutralised and the root ignores the timeout: wait(10) after the kill
    # also times out, so the output cannot be trusted.
    class _NoOpJob:
        def terminate_and_close(self):
            pass

    monkeypatch.setattr(runner, "_kill_tree", lambda proc: None)
    monkeypatch.setattr(runner, "_JOIN_SEC", 0.5)
    monkeypatch.setattr(
        runner._JobObject,
        "attach",
        classmethod(lambda cls, proc: _NoOpJob()),
    )
    real_wait = subprocess.Popen.wait
    calls = []

    def fake_wait(self, timeout=None):
        calls.append(timeout)
        if timeout is not None and len(calls) <= 2:
            raise subprocess.TimeoutExpired("x", timeout)  # first: command timeout; second: after kill
        return real_wait(self, timeout)

    monkeypatch.setattr(subprocess.Popen, "wait", fake_wait)
    sleeper = pycmd("import time; time.sleep(4)")
    report = {}
    try:
        r = run(work, m=mf([sleeper]), commands=[sleeper], test_result_parser=ALL_IDS,
                timeout_sec=1, report=report)
    finally:
        monkeypatch.undo()
    assert calls[:2] == [1.0, 10] or calls[1] == 10
    assert r["commands"][0]["exit_code"] == -4  # not -1: the timeout is outranked
    assert report["commands"][0]["timed_out"] is True
    assert report["commands"][0]["capture_incomplete"] is True and report["capture_incomplete"] is True
    assert r["result"] == "FAIL"


def test_thread_start_failure_kills_the_child_and_cleans_up(work, monkeypatch):
    made = _patch_popen(monkeypatch, lambda p: None)
    marker = os.path.join(work, "child-alive.txt")
    child = pycmd(
        "import time\n"
        "for _ in range(100):\n"
        f"    open({marker!r}, 'a').write('.'); time.sleep(0.1)\n"
    )
    real_start = runner.threading.Thread.start
    state = {"n": 0}

    def failing_start(self):
        state["n"] += 1
        if state["n"] == 2:  # the stderr reader fails to start
            raise RuntimeError("can't start new thread")
        return real_start(self)

    monkeypatch.setattr(runner.threading.Thread, "start", failing_start)
    with pytest.raises(RuntimeError, match="start new thread"):
        run(work, m=mf([child]), commands=[child], test_result_parser=ALL_IDS)
    monkeypatch.undo()
    proc = made[0]
    assert proc.poll() is not None, "the child was left running after the thread-start failure"
    assert proc.stdout.closed and proc.stderr.closed
    time.sleep(1.0)
    size = os.path.getsize(marker) if os.path.exists(marker) else 0
    time.sleep(1.0)
    assert (os.path.getsize(marker) if os.path.exists(marker) else 0) == size, "child kept running"


def test_thread_start_failure_for_the_first_reader_also_cleans_up(work, monkeypatch):
    made = _patch_popen(monkeypatch, lambda p: None)
    real_start = runner.threading.Thread.start

    def failing_start(self):
        raise RuntimeError("no threads")

    sleeper = pycmd("import time; time.sleep(30)")
    monkeypatch.setattr(runner.threading.Thread, "start", failing_start)
    with pytest.raises(RuntimeError, match="no threads"):
        run(work, m=mf([sleeper]), commands=[sleeper], test_result_parser=ALL_IDS)
    monkeypatch.setattr(runner.threading.Thread, "start", real_start)
    assert made[0].poll() is not None and made[0].stdout.closed and made[0].stderr.closed


@pytest.mark.skipif(os.name != "nt", reason="Job Object is Windows only")
def test_job_is_closed_when_thread_start_fails(work, monkeypatch):
    closed = []
    real_term = runner._JobObject.terminate_and_close

    def spy(self):
        closed.append(self._handle is not None)
        return real_term(self)

    monkeypatch.setattr(runner._JobObject, "terminate_and_close", spy)
    monkeypatch.setattr(
        runner.threading.Thread, "start", lambda self: (_ for _ in ()).throw(RuntimeError("x"))
    )
    sleeper = pycmd("import time; time.sleep(30)")
    with pytest.raises(RuntimeError):
        run(work, m=mf([sleeper]), commands=[sleeper], test_result_parser=ALL_IDS)
    assert closed and closed[0] is True  # the job was terminated on the exception path


# ------------------------------------------ Windows Job Object API failures


@pytest.mark.parametrize("terminate", [False, RuntimeError("terminate failed")], ids=["false", "raises"])
@pytest.mark.parametrize("close", [True, False, RuntimeError("close failed")], ids=["true", "false", "raises"])
def test_job_cleanup_failure_is_never_confirmed_and_fallback_runs(monkeypatch, terminate, close):
    """Mock Win32 outcomes only; no child process or kill-table scenario is used."""
    calls = []

    def outcome(name, value):
        calls.append(name)
        if isinstance(value, Exception):
            raise value
        return value

    api = type("Api", (), {"k32": type("Kernel32", (), {
        "TerminateJobObject": staticmethod(lambda *args: outcome("terminate", terminate)),
        "CloseHandle": staticmethod(lambda *args: outcome("close", close)),
    })()})
    job = runner._JobObject(api, 123)
    fallback = []
    monkeypatch.setattr(runner, "_taskkill_tree", lambda pid: fallback.append(pid))

    result = job.terminate_and_close()
    if terminate is not True or close is not True:
        assert result is False
        runner._kill_tree(type("Proc", (), {"pid": 456, "kill": lambda self: None})())
        assert fallback == [456]
    else:
        assert result is True
        assert fallback == []
    assert calls == ["terminate", "close"]
    assert (job._handle is None) is (close is True)


@pytest.mark.parametrize("close", [False, RuntimeError("close failed")], ids=["false", "raises"])
def test_failed_job_handle_close_is_retried(monkeypatch, close):
    calls = []

    def close_handle(handle):
        calls.append(handle)
        if len(calls) == 1:
            if isinstance(close, Exception):
                raise close
            return close
        return True

    api = type("Api", (), {"k32": type("Kernel32", (), {
        "TerminateJobObject": staticmethod(lambda *args: True),
        "CloseHandle": staticmethod(close_handle),
    })()})
    job = runner._JobObject(api, 789)
    assert job.terminate_and_close() is False
    assert job._handle == 789
    assert job.terminate_and_close() is True
    assert job._handle is None
    assert calls == [789, 789]


@pytest.mark.parametrize("api_name", ["TerminateJobObject", "CloseHandle"], ids=["terminate", "close"])
@pytest.mark.parametrize("failure", ["false", "raises"], ids=["false", "raises"])
def test_run_receipt_fails_closed_when_job_cleanup_is_unconfirmed(
    work, monkeypatch, api_name, failure
):
    """Exercise runner-to-receipt propagation with mocked Win32 APIs and no real kill."""
    calls = []

    def failed_api(*args):
        calls.append(api_name)
        if failure == "raises":
            raise RuntimeError(f"{api_name} failed")
        return False

    class Kernel32:
        TerminateJobObject = staticmethod(lambda *args: True)
        CloseHandle = staticmethod(lambda *args: True)

    setattr(Kernel32, api_name, staticmethod(failed_api))
    api = type("Api", (), {"k32": Kernel32()})
    fake_job = runner._JobObject(api, 321)
    monkeypatch.setattr(runner._JobObject, "attach", classmethod(lambda cls, proc: fake_job))
    monkeypatch.setattr(runner, "_spawn_kwargs", lambda **kwargs: {})
    fallback = []
    monkeypatch.setattr(runner, "_kill_tree", lambda proc: fallback.append(proc.pid))
    monkeypatch.setattr(runner.os, "name", "nt")

    report = {}
    r = run(work, report=report, test_result_parser=ALL_IDS)

    assert r["commands"][0]["exit_code"] == runner.EXIT_CAPTURE_INCOMPLETE == -4
    assert report["capture_incomplete"] is True
    assert report["commands"][0]["capture_incomplete"] is True
    assert r["result"] == "FAIL" and signing.verify(r, KEY)
    assert calls.count(api_name) == (1 if api_name == "TerminateJobObject" else 2)
    assert len(fallback) >= 1
    assert len(set(fallback)) == 1
