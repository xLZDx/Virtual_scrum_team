"""E4 runner and signing: run_and_sign, HMAC signing, key hygiene, file digests."""

from __future__ import annotations

import copy
import hashlib
import os
import sys

import pytest

from tools.vst import contracts as c
from tools.vst import gate, runner, signing

from .e1e4_helpers import EPOCH, HEAD, HEAD2, KEY, ROLE, TASK, manifest, receipt

PY = sys.executable
SECRET = b"TOP-SECRET-KEY-MATERIAL-9f3a"
ONE_SLOT = manifest(
    required_receipts=[{"slot": "tests", "receipt_type": "TestRun"}], acceptance=["AC-1"]
)


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


@pytest.fixture
def work(tmp_path):
    d = tmp_path / "work"
    d.mkdir()
    return str(d)


def run(work, **over):
    kw = dict(
        task_id=TASK,
        slot="tests",
        attempt=1,
        epoch=EPOCH,
        candidate_head=HEAD,
        role_sha256=ROLE,
        resolved_model="sonnet-5.5",
        invocation_id="inv-1",
        runner_id="runner-1",
        key=KEY,
        commands=[printer("PASSED t1", "PASSED t2")],
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
    return runner.run_and_sign(**kw)


def tree_bytes(root):
    out = {}
    for base, _, files in os.walk(root):
        for f in files:
            p = os.path.join(base, f)
            with open(p, "rb") as fh:
                out[p] = fh.read()
    return out


# ------------------------------------------------------------ happy / failure


def test_harmless_command_produces_signed_passing_testrun(work):
    r = run(work, commands=[[PY, "-c", "print(1)"]], test_result_parser=lambda s: (["t1", "t2"], [], []))
    assert r["result"] == "PASS"
    assert r["receipt_type"] == "TestRun"
    assert r["commands"] == [{"argv": [PY, "-c", "print(1)"], "exit_code": 0}]
    assert r["executed_test_ids"] == ["t1", "t2"] and r["expected_test_ids"] == ["t1", "t2"]
    assert r["receipt_id"] == f"{TASK}:tests:1:inv-1"
    assert r["prev_receipt_sha256"] is None
    assert signing.verify(r, KEY)
    assert c.validate_receipt(r) == r
    assert c.derive_result(r) == r["result"]


def test_receipt_carries_every_caller_supplied_field(work):
    r = run(work, attempt=2, prev_receipt_sha256="e" * 64, epoch=7, candidate_head=HEAD2,
            runner_id="rr", resolved_model="mm", invocation_id="ii", covered_acceptance=["AC-1", "AC-2"],
            created_at="2030-01-01T00:00:00Z")
    assert (r["attempt"], r["prev_receipt_sha256"], r["epoch"], r["candidate_head"]) == (2, "e" * 64, 7, HEAD2)
    assert (r["runner_id"], r["resolved_model"], r["invocation_id"]) == ("rr", "mm", "ii")
    assert r["covered_acceptance"] == ["AC-1", "AC-2"] and r["created_at"] == "2030-01-01T00:00:00Z"
    assert r["role_sha256"] == ROLE and r["task_id"] == TASK and r["slot"] == "tests"


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
    assert seen[0] == "FIRST\n\nSECOND\n"  # each command's stdout joined with a newline, in order


def test_timeout_records_exit_minus_one_and_fails(work):
    r = run(work, commands=[[PY, "-c", "import time; time.sleep(60)"]], timeout_sec=1,
            test_result_parser=lambda s: (["t1", "t2"], [], []))
    assert r["commands"][0]["exit_code"] == runner.EXIT_TIMEOUT == -1
    assert r["result"] == "FAIL"  # all ids reported executed, only the exit code can fail it
    assert signing.verify(r, KEY)


def test_missing_executable_records_exit_minus_two(work):
    r = run(work, commands=[["definitely-not-an-installed-program-xyz"]],
            test_result_parser=lambda s: (["t1", "t2"], [], []))
    assert r["commands"][0]["exit_code"] == runner.EXIT_MISSING_EXECUTABLE == -2
    assert r["result"] == "FAIL"


def test_missing_cwd_records_exit_minus_two(work):
    r = run(work, cwd=os.path.join(work, "no-such-dir"), commands=[[PY, "-c", "print(1)"]])
    assert r["commands"][0]["exit_code"] == -2


def test_no_shell_metacharacters_are_not_interpreted(work):
    seen = []
    run(work, commands=[[PY, "-c", "import sys; print(sys.argv[1])", "a && echo INJECTED; $(x) | y"]],
        test_result_parser=lambda s: (seen.append(s) or ["t1", "t2"], [], []))
    assert seen[0].strip() == "a && echo INJECTED; $(x) | y"


def test_command_runs_in_the_given_cwd(work):
    seen = []
    run(work, commands=[[PY, "-c", "import os; print(os.getcwd())"]],
        test_result_parser=lambda s: (seen.append(s) or ["t1", "t2"], [], []))
    assert os.path.realpath(seen[0].strip()) == os.path.realpath(work)


# --------------------------------------------------------- invalid arguments


@pytest.mark.parametrize("bad", [[], None, "python", [[]], [["python", ""]], [[1]], [["a"], []], "x", (("a",),)])
def test_empty_or_malformed_commands_rejected(work, bad):
    with pytest.raises(c.ContractError):
        run(work, commands=bad)


def test_rejected_commands_do_not_execute_anything(work):
    marker = os.path.join(work, "ran.txt")
    code = f"open({marker!r}, 'w').write('x')"
    with pytest.raises(c.ContractError):
        run(work, commands=[[PY, "-c", code], []])
    assert not os.path.exists(marker)  # validation precedes any execution


@pytest.mark.parametrize(
    "over",
    [
        {"attempt": 0},
        {"attempt": True},
        {"epoch": 0},
        {"candidate_head": "xyz"},
        {"role_sha256": "short"},
        {"attempt": 2, "prev_receipt_sha256": None},
        {"attempt": 1, "prev_receipt_sha256": "e" * 64},
        {"task_id": ""},
    ],
)
def test_invalid_receipt_fields_rejected(work, over):
    with pytest.raises(c.ContractError):
        run(work, **over)


@pytest.mark.parametrize("key", [b"", "string-key", None])
def test_invalid_key_rejected(work, key):
    with pytest.raises(c.ContractError):
        run(work, key=key)


# ---------------------------------------------------- parser / test-id honesty


def test_mismatched_executed_vs_expected_is_not_pass(work):
    for executed in (["t1"], ["t1", "t2", "t3"], ["t1", "other"]):
        r = run(work, test_result_parser=lambda s, e=executed: (e, [], []))
        assert r["result"] == "FAIL", executed


def test_output_injection_of_extra_test_ids_does_not_make_pass(work):
    # The command prints a forged extra line; a line parser reports it as executed.
    r = run(work, commands=[printer("PASSED t1", "PASSED t2", "PASSED t-forged")])
    assert "t-forged" in r["executed_test_ids"]
    assert r["result"] == "FAIL"


def test_output_injection_of_missing_ids_cannot_be_hidden(work):
    r = run(work, commands=[printer("PASSED t1")])
    assert r["result"] == "FAIL"


def test_skipped_or_xfail_ids_prevent_pass(work):
    r1 = run(work, test_result_parser=lambda s: (["t1", "t2"], ["t3"], []))
    r2 = run(work, test_result_parser=lambda s: (["t1", "t2"], [], ["t4"]))
    assert r1["result"] == "FAIL" and r2["result"] == "FAIL"
    assert r1["skipped_test_ids"] == ["t3"] and r2["xfail_test_ids"] == ["t4"]


def test_zero_executed_is_inconclusive_not_pass(work):
    r = run(work, test_result_parser=lambda s: ([], [], []))
    assert r["result"] == "INCONCLUSIVE"
    assert signing.verify(r, KEY)


def test_empty_expected_never_passes(work):
    r = run(work, expected_test_ids=[], test_result_parser=lambda s: (["t1"], [], []))
    assert r["result"] == "FAIL"


def test_parser_returning_blank_ids_is_rejected(work):
    with pytest.raises(c.ContractError):
        run(work, test_result_parser=lambda s: ([""], [], []))


def test_parser_exception_propagates_instead_of_silent_pass(work):
    def boom(_):
        raise RuntimeError("parser failed")

    with pytest.raises(RuntimeError):
        run(work, test_result_parser=boom)


def test_result_is_computed_not_caller_controlled(work):
    import inspect

    assert "result" not in inspect.signature(runner.run_and_sign).parameters
    r = run(work, commands=[printer("PASSED t1", "PASSED t2", exit_code=9)])
    assert r["result"] == "FAIL" and c.derive_result(r) == "FAIL"


# ------------------------------------------------------------- key hygiene


def test_key_never_appears_in_receipt(work):
    r = run(work, key=SECRET)
    blob = c.canonical_bytes(r)
    assert SECRET not in blob
    assert SECRET.hex().encode() not in blob
    import base64

    assert base64.b64encode(SECRET) not in blob
    assert signing.verify(r, SECRET) and not signing.verify(r, KEY)


def test_runner_writes_nothing_under_cwd_and_key_not_on_disk(work):
    before = tree_bytes(work)
    run(work, key=SECRET)
    after = tree_bytes(work)
    assert after == before == {}


def test_key_does_not_leak_into_cwd_even_with_preexisting_files(work):
    decoy = os.path.join(work, "key.txt")
    with open(decoy, "wb") as fh:
        fh.write(b"WRONG-KEY-FROM-WORKER-DIR")
    before = tree_bytes(work)
    r = run(work, key=SECRET)
    after = tree_bytes(work)
    assert after == before
    assert all(SECRET not in blob for blob in after.values())
    # The runner signs with the key argument; it never looks the key up in cwd.
    assert signing.verify(r, SECRET)
    assert not signing.verify(r, b"WRONG-KEY-FROM-WORKER-DIR")


def test_key_is_not_visible_to_the_child_process(work):
    seen = []
    run(work, key=SECRET, commands=[[PY, "-c", "import os,sys; print(os.environ); print(sys.argv)"]],
        test_result_parser=lambda s: (seen.append(s) or ["t1", "t2"], [], []))
    assert "TOP-SECRET" not in seen[0]


# --------------------------------------------------------- signing semantics


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


def test_wrong_key_fails_and_bad_key_raises(work):
    r = run(work)
    assert not signing.verify(r, b"other-key")
    for bad in (b"", "text", None):
        with pytest.raises(c.ContractError):
            signing.verify(r, bad)
        with pytest.raises(c.ContractError):
            signing.sign(runner.receipt_without_signature(r), bad)


def test_verify_non_dict_or_bad_signature_is_false_not_error():
    assert signing.verify("x", KEY) is False
    r = receipt()
    for bad in (None, 5, ["a"]):
        t = dict(r, signature=bad)
        assert signing.verify(t, KEY) is False
    no_sig = {k: v for k, v in r.items() if k != "signature"}
    assert signing.verify(no_sig, KEY) is False


def test_sign_refuses_receipt_that_already_has_signature():
    with pytest.raises(c.ContractError):
        signing.sign(receipt(), KEY)
    with pytest.raises(c.ContractError):
        signing.sign("not-a-dict", KEY)


def test_sign_matches_independent_hmac_over_canonical_bytes():
    import hmac

    body = runner.receipt_without_signature(receipt())
    expected = hmac.new(KEY, c.canonical_bytes(body), hashlib.sha256).hexdigest()
    assert signing.sign(body, KEY) == expected
    assert signing.sign(body, bytearray(KEY)) == expected


def test_receipt_without_signature_helper_does_not_mutate():
    r = receipt()
    body = runner.receipt_without_signature(r)
    assert "signature" not in body and "signature" in r


# ------------------------------------- gate integration (replay, forgery, chain)


def gate_eval(receipts, *, head=HEAD, epoch=EPOCH, key=KEY, m=None):
    return gate.evaluate(ONE_SLOT if m is None else m, receipts, head, epoch, key)


def test_runner_receipt_is_approved_by_gate_at_its_head_and_epoch(work):
    r = run(work)
    d = gate_eval([r])
    assert d["verdict"] == "APPROVE"
    assert d["required_receipt_hashes"] == [c.receipt_sha256(r)]


def test_replay_against_another_head_is_rejected(work):
    d = gate_eval([run(work)], head=HEAD2)
    assert d["verdict"] == "NO_GO" and "stale head" in " ".join(d["reasons"])


def test_replay_against_another_epoch_is_rejected(work):
    d = gate_eval([run(work)], epoch=EPOCH + 1)
    assert d["verdict"] == "NO_GO" and "stale epoch" in " ".join(d["reasons"])


def test_replay_against_another_task_is_rejected(work):
    d = gate_eval([run(work)], m=manifest(task_id="OTHER", required_receipts=ONE_SLOT["required_receipts"],
                                          acceptance=["AC-1"]))
    assert d["verdict"] != "APPROVE"
    assert "belongs to another task" in " ".join(d["reasons"])


def test_forged_unsigned_and_wrong_key_receipts_are_rejected(work):
    r = run(work)
    forged = dict(r, signature="0" * 64)
    other_key = run(work, key=b"attacker-key")
    for bad in (forged, other_key):
        d = gate_eval([bad])
        assert d["verdict"] == "MODIFY"
        assert "invalid signature" in " ".join(d["reasons"])


def test_edited_exit_code_after_signing_is_rejected(work):
    r = run(work, commands=[printer("PASSED t1", "PASSED t2", exit_code=1)])
    assert r["result"] == "FAIL"
    t = copy.deepcopy(r)
    t["commands"][0]["exit_code"] = 0
    t["result"] = "PASS"
    d = gate_eval([t])
    assert d["verdict"] == "MODIFY" and "invalid signature" in " ".join(d["reasons"])


def test_retry_after_fail_through_runner_is_approved_with_retained_failure(work):
    first = run(work, commands=[printer("PASSED t1", exit_code=1)], invocation_id="i1")
    assert first["result"] == "FAIL"
    second = run(work, attempt=2, prev_receipt_sha256=c.receipt_sha256(first), invocation_id="i2")
    d = gate_eval([first, second])
    assert d["verdict"] == "APPROVE"
    assert d["unresolved_findings"] == ["earlier failure retained: slot 'tests' attempt 1 result FAIL"]


def test_retry_with_wrong_prev_hash_is_rejected(work):
    first = run(work, commands=[printer("PASSED t1", exit_code=1)], invocation_id="i1")
    second = run(work, attempt=2, prev_receipt_sha256="e" * 64, invocation_id="i2")
    d = gate_eval([first, second])
    assert d["verdict"] == "MODIFY" and "attempt chain broken" in " ".join(d["reasons"])


def test_zero_executed_receipt_never_satisfies_gate(work):
    d = gate_eval([run(work, test_result_parser=lambda s: ([], [], []))])
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


# ------------------------------------------------- artifacts and validation


def test_artifacts_are_hashed_after_the_commands_ran(work):
    code = "open('out.txt','wb').write(b'built-by-command')"
    r = run(work, commands=[[PY, "-c", code], printer("PASSED t1", "PASSED t2")], artifact_paths=["out.txt"])
    assert r["artifact_digests"] == {"out.txt": hashlib.sha256(b"built-by-command").hexdigest()}
    assert r["result"] == "PASS" and signing.verify(r, KEY)


def test_absolute_artifact_path_is_hashed(work, tmp_path):
    p = tmp_path / "abs.bin"
    p.write_bytes(b"abs")
    r = run(work, artifact_paths=[str(p)])
    assert r["artifact_digests"] == {str(p): hashlib.sha256(b"abs").hexdigest()}


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


def _write(path, data):
    with open(path, "wb") as fh:
        fh.write(data)


def test_modified_artifact_is_rejected_by_gate_resolver(work):
    art = os.path.join(work, "art.bin")
    _write(art, b"v1")
    r = run(work, artifact_paths=["art.bin"])

    def resolver(p):
        return runner.file_sha256(os.path.join(work, p))

    ok = gate.evaluate(ONE_SLOT, [r], HEAD, EPOCH, KEY, artifact_resolver=resolver)
    assert ok["verdict"] == "APPROVE"
    _write(art, b"v2-tampered")
    bad = gate.evaluate(ONE_SLOT, [r], HEAD, EPOCH, KEY, artifact_resolver=resolver)
    assert bad["verdict"] == "MODIFY" and "digest mismatch" in " ".join(bad["reasons"])


def test_deleted_artifact_is_rejected_by_gate_resolver(work):
    art = os.path.join(work, "art.bin")
    _write(art, b"v1")
    r = run(work, artifact_paths=["art.bin"])
    os.remove(art)

    def resolver(p):
        try:
            return runner.file_sha256(os.path.join(work, p))
        except OSError:
            return None

    assert gate.evaluate(ONE_SLOT, [r], HEAD, EPOCH, KEY, artifact_resolver=resolver)["verdict"] == "MODIFY"


def test_artifact_digest_tamper_after_signing_is_rejected(work):
    _write(os.path.join(work, "art.bin"), b"v1")
    r = run(work, artifact_paths=["art.bin"])
    t = copy.deepcopy(r)
    t["artifact_digests"]["art.bin"] = hashlib.sha256(b"forged").hexdigest()
    assert not signing.verify(t, KEY)
    d = gate_eval([t])
    assert d["verdict"] == "MODIFY" and "invalid signature" in " ".join(d["reasons"])


INVALID_OVERRIDES = [
    {"task_id": ""}, {"slot": " "}, {"resolved_model": ""}, {"invocation_id": None},
    {"runner_id": 3}, {"created_at": ""},
    {"attempt": 0}, {"attempt": True}, {"epoch": 0}, {"epoch": True},
    {"candidate_head": "xyz"}, {"role_sha256": "short"},
    {"attempt": 2, "prev_receipt_sha256": None}, {"attempt": 1, "prev_receipt_sha256": "e" * 64},
    {"key": b""}, {"key": "text"}, {"key": None},
    {"commands": []}, {"commands": [[]]}, {"commands": [["x", ""]]},
    {"expected_test_ids": "t1"}, {"expected_test_ids": [""]},
    {"covered_acceptance": [1]}, {"artifact_paths": "a.txt"}, {"artifact_paths": [1]},
    {"artifact_paths": [""]}, {"artifact_paths": None},
    {"timeout_sec": 0}, {"timeout_sec": True}, {"timeout_sec": "5"},
    {"cwd": None}, {"cwd": 5}, {"test_result_parser": None}, {"test_result_parser": "x"},
]


@pytest.mark.parametrize("over", INVALID_OVERRIDES, ids=[str(i) + "-" + next(iter(o)) for i, o in enumerate(INVALID_OVERRIDES)])
def test_invalid_inputs_raise_before_any_subprocess_starts(work, over):
    marker = os.path.join(work, "ran.marker")
    code = f"open({marker!r}, 'w').write('x')"
    with pytest.raises(c.ContractError):
        run(work, **{"commands": [[PY, "-c", code]], **over})
    assert not os.path.exists(marker)


@pytest.mark.parametrize(
    "exc",
    [FileNotFoundError("x"), NotADirectoryError("x"), PermissionError("x"), OSError("other"), OSError(22, "invalid")],
    ids=["FileNotFound", "NotADirectory", "Permission", "OSError", "OSError22"],
)
def test_os_errors_starting_a_process_map_to_exit_minus_two(work, monkeypatch, exc):
    def fake_run(*a, **k):
        raise exc

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    r = run(work, test_result_parser=lambda s: (["t1", "t2"], [], []))
    assert r["commands"][0]["exit_code"] == -2
    assert r["result"] == "FAIL" and signing.verify(r, KEY)


def test_non_os_errors_from_subprocess_propagate(work, monkeypatch):
    def fake_run(*a, **k):
        raise RuntimeError("not an OS error")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError):
        run(work)


def test_cwd_that_is_a_file_maps_to_exit_minus_two(work):
    f = os.path.join(work, "a-file")
    _write(f, b"x")
    r = run(work, cwd=f, test_result_parser=lambda s: (["t1", "t2"], [], []))
    assert r["commands"][0]["exit_code"] == -2 and r["result"] == "FAIL"
