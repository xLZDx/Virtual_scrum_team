"""LINK-2 T3b: the router wrappers for `aeve packet` and `aeve verify-handoff` (`tools/vst/router_aeve_cli.py`).

Acceptance criteria (docs/sdlc/LINK2_ROUTER_DESIGN.md section 5): AC-12 to AC-17 (and AC-10, AC-15 pin checks).
A stub script stands in for `python -m aeve` (through `command_prefix`); the AEVE checkout for the pin check is a
tiny real git repository, because the pin check runs real git. Report statuses follow the design rule "the status is
the worst check (FAIL gives REJECTED, else UNKNOWN gives UNKNOWN, else VERIFIED)" and the exit table
0 VERIFIED, 1 REJECTED, 2 UNKNOWN, 3 INVALID (design section 2, D2 step 7).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from tools.uc import adapter
from tools.vst import router_aeve_cli as rac
from tools.vst import router_request as rr
from tools.vst.router_request import RouterError

from tests.vst import router_support as S

FAST = dict(timeout=20.0, jitter=(0.0, 0.0))


@pytest.fixture(scope="module")
def shared_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("aeve-shared") / "aeve"
    head = S.make_aeve_repo(root)
    return root, head


@pytest.fixture()
def aeve(shared_repo):
    return shared_repo  # (root, head); never dirtied by a test


@pytest.fixture()
def own_repo(tmp_path):
    root = tmp_path / "aeve-own"
    head = S.make_aeve_repo(root)
    return root, head


@pytest.fixture()
def stub(tmp_path):
    return S.Stub(tmp_path / "stub")


@pytest.fixture()
def state(tmp_path):
    return tmp_path / "state"


def packet_run(aeve, stub, state, request=None, **kw):
    root, head = aeve
    kwargs = dict(aeve_root=root, state_dir=state, pin_head=head, command_prefix=stub.prefix, **FAST)
    kwargs.update(kw)
    return rac.run_packet(request or S.sample_request(), **kwargs)


def code_of(func, *args, **kwargs) -> RouterError:
    with pytest.raises(RouterError) as info:
        func(*args, **kwargs)
    return info.value


@pytest.fixture()
def files(tmp_path, aeve, stub, state):
    """A validated packet plus VST-owned copies of the packet and the host result, ready for verify-handoff."""
    packet = packet_run(aeve, stub, state)
    stub.reset()
    packet_path = tmp_path / "work" / "packet.json"
    result_path = tmp_path / "work" / "result.json"
    packet_path.parent.mkdir()
    packet_path.write_bytes(packet.packet_bytes)
    result_path.write_text(json.dumps(S.HOST_RESULT), encoding="utf-8")
    return packet, packet_path, result_path


def verify_run(aeve, stub, state, files, tmp_path, **kw):
    packet, packet_path, result_path = files
    root, head = aeve
    kwargs = dict(root=tmp_path / "worktree", aeve_root=root, state_dir=state, pin_head=head,
                  command_prefix=stub.prefix, **FAST)
    kwargs.update(kw)
    return rac.run_verify_handoff(packet_path, result_path, packet.packet, **kwargs)


# ============================================================ run_packet
def test_packet_happy_path_returns_the_validated_packet(aeve, stub, state):
    request = S.sample_request()
    result = packet_run(aeve, stub, state, request)
    assert result.exit_code == 0 and result.retry_count == 0
    assert result.packet["task_id"] == S.TASK and result.packet["role"] == S.ROLE
    assert result.packet["request_sha256"] == S.expected_request_sha256(request)
    assert result.packet_sha256 == rr.sha256_hex(result.packet_bytes)
    assert json.loads(result.packet_bytes) == result.packet
    assert result.packet["scope"]["allowed_paths"] == ["src", "tests"]  # the stub built it from the request VST wrote


def test_packet_runs_aeve_exactly_once_with_the_documented_argv(aeve, stub, state):
    packet_run(aeve, stub, state)
    calls = stub.calls("packet")
    assert len(calls) == 1
    argv = calls[0]["argv"]
    assert argv[0] == "--request" and len(argv) == 2 and argv[1].endswith("request.json")


def test_packet_is_deterministic_for_the_same_request(aeve, stub, state):
    first = packet_run(aeve, stub, state)
    second = packet_run(aeve, stub, state)
    assert first.packet_bytes == second.packet_bytes and first.packet_sha256 == second.packet_sha256


def test_packet_request_file_is_removed_after_the_call(aeve, stub, state):
    packet_run(aeve, stub, state)
    path = pathlib.Path(stub.calls("packet")[0]["argv"][1])
    assert not path.exists()


# ---- pin and checkout (AC-15)
def test_head_mismatch_is_pin_drift_and_no_aeve_call(aeve, stub, state):
    root, head = aeve
    other = "0" * 40 if head != "0" * 40 else "1" * 40
    err = code_of(packet_run, aeve, stub, state, pin_head=other)
    assert err.reason == "ROUTER_PIN_DRIFT"
    assert stub.calls() == []


@pytest.mark.parametrize("pin", ["", "abc", "A" * 40, "g" * 40, "a" * 41, None, 5])
def test_malformed_pin_is_pin_drift_and_no_aeve_call(aeve, stub, state, pin):
    assert code_of(packet_run, aeve, stub, state, pin_head=pin).reason == "ROUTER_PIN_DRIFT"
    assert stub.calls() == []


def test_untracked_file_in_the_checkout_is_pin_drift_and_no_aeve_call(own_repo, stub, state):  # AC-15
    root, head = own_repo
    (root / "stray.txt").write_text("x", encoding="utf-8")
    err = code_of(packet_run, own_repo, stub, state)
    assert err.reason == "ROUTER_PIN_DRIFT" and "untracked" in err.detail
    assert stub.calls() == []


def test_tracked_change_in_the_checkout_is_pin_drift_and_no_aeve_call(own_repo, stub, state):  # AC-15
    root, head = own_repo
    (root / "src" / "marker.txt").write_text("changed\n", encoding="utf-8")
    assert code_of(packet_run, own_repo, stub, state).reason == "ROUTER_PIN_DRIFT"
    assert stub.calls() == []


def test_staged_change_in_the_checkout_is_pin_drift(own_repo, stub, state):
    root, head = own_repo
    (root / "src" / "marker.txt").write_text("changed\n", encoding="utf-8")
    S.git(root, "add", "-A")
    assert code_of(packet_run, own_repo, stub, state).reason == "ROUTER_PIN_DRIFT"


def test_new_commit_moves_head_and_the_old_pin_is_drift(own_repo, stub, state):
    root, head = own_repo
    (root / "src" / "more.txt").write_text("m\n", encoding="utf-8")
    S.git(root, "add", "-A")
    S.git(root, "commit", "-q", "-m", "second")
    assert code_of(packet_run, own_repo, stub, state).reason == "ROUTER_PIN_DRIFT"
    assert packet_run((root, S.git(root, "rev-parse", "HEAD")), stub, state).exit_code == 0  # the new head, clean tree


def test_clean_checkout_with_an_ignored_file_is_accepted(own_repo, stub, state):
    root, head = own_repo
    (root / ".git" / "info" / "exclude").write_text("*.cache\n", encoding="utf-8")
    (root / "x.cache").write_text("ignored", encoding="utf-8")
    assert packet_run(own_repo, stub, state).exit_code == 0


def test_aeve_root_that_is_not_a_directory_is_missing(tmp_path, stub, state):  # AC-15
    err = code_of(rac.run_packet, S.sample_request(), aeve_root=tmp_path / "nowhere", state_dir=state,
                  pin_head="a" * 40, command_prefix=stub.prefix)
    assert err.reason == "ROUTER_AEVE_MISSING" and stub.calls() == []


def test_not_a_git_checkout_is_pin_drift(tmp_path, stub, state):
    plain = tmp_path / "plain"
    plain.mkdir()
    err = code_of(rac.run_packet, S.sample_request(), aeve_root=plain, state_dir=state, pin_head="a" * 40,
                  command_prefix=stub.prefix)
    assert err.reason == "ROUTER_PIN_DRIFT" and stub.calls() == []


def test_unknown_executable_is_aeve_missing(aeve, state):  # AC-15
    root, head = aeve
    err = code_of(rac.run_packet, S.sample_request(), aeve_root=root, state_dir=state, pin_head=head,
                  command_prefix=["definitely-not-an-executable-link2"], timeout=10.0)
    assert err.reason == "ROUTER_AEVE_MISSING"


# ---- exit codes and statuses of `packet`
def test_packet_exit_one_is_bad_exit(aeve, stub, state):  # AC-10 side: packet accepts only 0 and 3
    stub.set("packet", exit=1)
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_BAD_EXIT"
    assert len(stub.calls("packet")) == 1  # no retry for another code


@pytest.mark.parametrize("exit_code", [2, 4, 64, 255])
def test_packet_other_exit_codes_are_bad_exit(aeve, stub, state, exit_code):
    stub.set("packet", exit=exit_code)
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_BAD_EXIT"


def test_packet_exit_zero_with_invalid_status_is_bad_exit(aeve, stub, state):
    stub.set("packet", set={"status": "INVALID", "reason": "X"}, exit=0)
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_BAD_EXIT"


def test_packet_exit_three_with_complete_status_is_bad_exit(aeve, stub, state):
    stub.set("packet", exit=3)
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_BAD_EXIT"


def test_packet_invalid_with_exit_three_is_packet_invalid_with_the_reason(aeve, stub, state):
    stub.set("packet", raw=json.dumps({"schema_version": "aeve.task_packet.v1", "status": "INVALID",
                                       "reason": "SCOPE_PATH_INVALID"}), exit=3)
    err = code_of(packet_run, aeve, stub, state)
    assert err.reason == "ROUTER_PACKET_INVALID" and "SCOPE_PATH_INVALID" in err.detail


def test_packet_for_another_task_is_packet_invalid(aeve, stub, state):  # AC-6 through the wrapper
    stub.set("packet", set={"task_id": "OTHER-1"})
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_PACKET_INVALID"


def test_packet_with_a_model_call_is_packet_invalid(aeve, stub, state):
    stub.set("packet", set={"llm_calls": 2})
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_PACKET_INVALID"


@pytest.mark.parametrize("raw", ["", "not json", "[]", '{"status": "COMPLETE", "status": "COMPLETE"}',
                                 '{"status": NaN}', "\x00"])
def test_packet_stdout_that_is_not_a_strict_json_object_is_bad_output(aeve, stub, state, raw):  # AC-14
    stub.set("packet", raw=raw, exit=0)
    assert code_of(packet_run, aeve, stub, state).reason == "ROUTER_BAD_OUTPUT"


def test_packet_stdout_over_the_cap_is_size_cap(aeve, stub, state):
    stub.set("packet", flood=5000)
    assert code_of(packet_run, aeve, stub, state, stdout_cap=1000).reason == "ROUTER_SIZE_CAP"
    assert len(stub.calls("packet")) == 1


# ---- timeout and retry (AC-12, AC-17)
def test_timeout_is_retried_at_most_twice_then_fails_with_the_tree_dead(aeve, stub, state):  # AC-12
    stub.set("packet", sleep=60)
    pauses: list[float] = []
    err = code_of(packet_run, aeve, stub, state, timeout=1.5, sleep=pauses.append, jitter=(0.5, 2.0))
    assert err.reason == "ROUTER_TIMEOUT"
    assert err.retry_count == 2 and err.tree_dead is True
    assert len(stub.calls("packet")) == 3  # the first try and two retries, never more
    assert len(pauses) == 2 and all(0.5 <= p <= 2.0 for p in pauses)
    for call in stub.calls("packet"):
        assert S.wait_until(lambda pid=call["pid"]: not S.pid_alive(pid), 15), "a timed out child is still alive"


def test_jitter_pause_comes_from_the_configured_range(aeve, stub, state):
    stub.set("packet", sleep=60)
    pauses: list[float] = []
    code_of(packet_run, aeve, stub, state, timeout=1.0, sleep=pauses.append, jitter=(0.25, 0.25), max_retries=1)
    assert pauses == [0.25]


def test_timeout_then_success_returns_the_packet_and_counts_one_retry(aeve, stub, state):
    stub.set("packet", calls=[{"sleep": 60}, {}])
    pauses: list[float] = []
    result = packet_run(aeve, stub, state, timeout=2.0, sleep=pauses.append)
    assert result.retry_count == 1 and result.exit_code == 0
    assert len(stub.calls("packet")) == 2 and len(pauses) == 1


def test_no_retry_when_max_retries_is_zero(aeve, stub, state):
    stub.set("packet", sleep=60)
    err = code_of(packet_run, aeve, stub, state, timeout=1.0, max_retries=0, sleep=lambda s: None)
    assert err.reason == "ROUTER_TIMEOUT" and err.retry_count == 0
    assert len(stub.calls("packet")) == 1


@pytest.mark.parametrize("tree_dead", [False, None])
def test_timeout_with_an_unconfirmed_dead_tree_is_never_retried(aeve, stub, state, monkeypatch, tree_dead):  # AC-17
    calls = []

    def hanging(command, args, **kwargs):
        calls.append(command)
        blocked = adapter.AdapterBlocked("TIMEOUT", "exceeded; the child ignored the kill")
        blocked.tree_dead = tree_dead
        raise blocked

    monkeypatch.setattr(rac.adapter, "run_aeve_command", hanging)
    pauses: list[float] = []
    err = code_of(packet_run, aeve, stub, state, sleep=pauses.append)
    assert err.reason == "ROUTER_TIMEOUT" and err.tree_dead is tree_dead and err.retry_count == 0
    assert calls == ["packet"] and pauses == []
    assert "not confirmed dead" in err.detail


def test_a_non_timeout_failure_is_not_retried_even_with_retries_available(aeve, stub, state):
    stub.set("packet", exit=1)
    pauses: list[float] = []
    code_of(packet_run, aeve, stub, state, sleep=pauses.append, max_retries=5)
    assert len(stub.calls("packet")) == 1 and pauses == []


# ============================================================ run_verify_handoff
def test_verified_report_is_routed_verified(aeve, stub, state, files, tmp_path):
    result = verify_run(aeve, stub, state, files, tmp_path)
    assert (result.outcome, result.status, result.exit_code, result.reason) == ("ROUTED_VERIFIED", "VERIFIED", 0, "")
    assert result.report["status"] == "VERIFIED" and result.retry_count == 0
    assert result.report_sha256 == rr.sha256_hex(result.report_bytes)
    assert json.loads(result.report_bytes) == result.report  # stored unmodified
    assert [c["id"] for c in result.report["checks"]] == sorted(S.CHECK_IDS)


def test_verify_handoff_always_passes_root_and_the_given_copies(aeve, stub, state, files, tmp_path):
    verify_run(aeve, stub, state, files, tmp_path)
    (call,) = stub.calls("verify-handoff")
    _packet, packet_path, result_path = files
    assert call["argv"] == ["--packet", str(packet_path), "--result", str(result_path), "--root",
                            str(tmp_path / "worktree")]
    assert call["result_sha256_seen"] == rr.sha256_hex(result_path.read_bytes())


@pytest.mark.parametrize("checks,outcome,status,exit_code", [
    ({"CHANGES_INSIDE_SCOPE": "FAIL"}, "ROUTED_REJECTED", "REJECTED", 1),
    ({"TESTS_FOR_LOGIC": "FAIL", "FORBIDDEN_UNTOUCHED": "FAIL"}, "ROUTED_REJECTED", "REJECTED", 1),
    ({"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN"}, "ROUTED_UNKNOWN", "UNKNOWN", 2),
    ({"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN", "TESTS_FOR_LOGIC": "UNKNOWN"}, "ROUTED_UNKNOWN", "UNKNOWN", 2),
    ({"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN", "TESTS_FOR_LOGIC": "FAIL"}, "ROUTED_REJECTED", "REJECTED", 1),
])
def test_status_is_the_worst_check_and_routes_without_raising(aeve, stub, state, files, tmp_path, checks, outcome,
                                                              status, exit_code):
    stub.set("verify-handoff", checks=checks)
    result = verify_run(aeve, stub, state, files, tmp_path)
    assert (result.outcome, result.status, result.exit_code) == (outcome, status, exit_code)
    failing = {c["id"] for c in result.report["checks"] if c["status"] == "FAIL"}
    assert failing == {k for k, v in checks.items() if v == "FAIL"}
    assert len(stub.calls("verify-handoff")) == 1  # a verdict is never retried


def test_unknown_is_never_routed_as_verified(aeve, stub, state, files, tmp_path):
    stub.set("verify-handoff", checks={"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN"})
    result = verify_run(aeve, stub, state, files, tmp_path)
    assert result.outcome != "ROUTED_VERIFIED" and result.status != "VERIFIED"


INVALID_REPORT = {"executed_project_code": False, "llm_calls": 0, "reason": "PATH_INVALID:changed",
                  "schema_version": "aeve.handoff_verify.v1", "source_modified": False, "status": "INVALID"}


def test_invalid_report_with_exit_three_is_routed_as_invalid_input_with_its_reason(aeve, stub, state, files, tmp_path):
    stub.set("verify-handoff", raw=json.dumps(INVALID_REPORT), exit=3)
    result = verify_run(aeve, stub, state, files, tmp_path)
    assert (result.outcome, result.status, result.exit_code) == ("ROUTER_INVALID_INPUT", "INVALID", 3)
    assert result.reason == "PATH_INVALID:changed"
    assert len(stub.calls("verify-handoff")) == 1  # no retry, no auto-correction


@pytest.mark.parametrize("report,exit_code", [
    (dict(INVALID_REPORT, checks=[]), 3),  # INVALID carries no checks
    ({k: v for k, v in INVALID_REPORT.items() if k != "reason"}, 3),
    (dict(INVALID_REPORT, reason=5), 3),
    (dict(INVALID_REPORT, llm_calls=1), 3),
    (dict(INVALID_REPORT, source_modified=True), 3),
])
def test_malformed_invalid_report_is_bad_output(aeve, stub, state, files, tmp_path, report, exit_code):
    stub.set("verify-handoff", raw=json.dumps(report), exit=exit_code)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path).reason == "ROUTER_BAD_OUTPUT"


@pytest.mark.parametrize("checks,exit_code", [
    ({"CHANGES_INSIDE_SCOPE": "FAIL"}, 0),   # REJECTED printed with exit 0
    ({"CHANGES_INSIDE_SCOPE": "FAIL"}, 2),
    ({"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN"}, 0),
    ({"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN"}, 1),
    ({}, 1),                                  # VERIFIED printed with exit 1
    ({}, 2),
    ({}, 3),
])
def test_exit_code_that_disagrees_with_the_status_is_bad_exit(aeve, stub, state, files, tmp_path, checks, exit_code):  # AC-13
    stub.set("verify-handoff", checks=checks, exit=exit_code)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path).reason == "ROUTER_BAD_EXIT"


@pytest.mark.parametrize("exit_code", [4, 5, 64, 255])
def test_verify_exit_codes_outside_the_table_are_bad_exit(aeve, stub, state, files, tmp_path, exit_code):  # AC-10
    stub.set("verify-handoff", exit=exit_code)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path).reason == "ROUTER_BAD_EXIT"


def checks_with(status_by_id):
    return [{"id": cid, "status": status_by_id.get(cid, "PASS"), "reason": "r", "paths": []} for cid in S.CHECK_IDS]


@pytest.mark.parametrize("label,doc_set,exit_code", [
    ("VERIFIED with one UNKNOWN check", {"status": "VERIFIED", "checks": checks_with({"TESTS_FOR_LOGIC": "UNKNOWN"})}, 0),
    ("VERIFIED with one FAIL check", {"status": "VERIFIED", "checks": checks_with({"TESTS_FOR_LOGIC": "FAIL"})}, 0),
    ("REJECTED without a FAIL check", {"status": "REJECTED", "checks": checks_with({})}, 1),
    ("REJECTED with only an UNKNOWN check", {"status": "REJECTED", "checks": checks_with({"TESTS_FOR_LOGIC": "UNKNOWN"})}, 1),
    ("UNKNOWN with a FAIL check", {"status": "UNKNOWN", "checks": checks_with({"TESTS_FOR_LOGIC": "FAIL"})}, 2),
    ("UNKNOWN with all PASS", {"status": "UNKNOWN", "checks": checks_with({})}, 2),
])
def test_status_that_is_not_the_worst_check_is_bad_output(aeve, stub, state, files, tmp_path, label, doc_set,
                                                          exit_code):  # AC-16
    stub.set("verify-handoff", set=doc_set, exit=exit_code)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path).reason == "ROUTER_BAD_OUTPUT", label


def broken_check(change):
    checks = checks_with({})
    change(checks)
    return {"checks": checks}


@pytest.mark.parametrize("label,doc_set,drop", [
    ("wrong schema", {"schema_version": "aeve.handoff_verify.v2"}, []),
    ("missing schema", {}, ["schema_version"]),
    ("status not a string", {"status": 5}, []),
    ("status unknown word", {"status": "PASS"}, []),
    ("basis other", {"basis": "INDEPENDENTLY_DIFFED"}, []),
    ("basis missing", {}, ["basis"]),
    ("task id differs", {"task_id": "OTHER-9"}, []),
    ("role differs", {"role": "planner"}, []),
    ("llm calls", {"llm_calls": 1}, []),
    ("llm calls false", {"llm_calls": False}, []),
    ("executed project code", {"executed_project_code": True}, []),
    ("source modified", {"source_modified": True}, []),
    ("guard missing", {}, ["source_modified"]),
    ("checks missing", {}, ["checks"]),
    ("checks empty", {"checks": []}, []),
    ("checks not a list", {"checks": {"a": 1}}, []),
    ("check not an object", broken_check(lambda c: c.__setitem__(0, "PASS")), []),
    ("unknown check id", broken_check(lambda c: c[0].update(id="EXTRA_CHECK")), []),
    ("repeated check id", broken_check(lambda c: c[1].update(id=c[0]["id"])), []),
    ("one check missing", broken_check(lambda c: c.pop()), []),
    ("sixth check", broken_check(lambda c: c.append({"id": "TASK_ID_MATCH", "status": "PASS", "reason": "r", "paths": []})), []),
    ("check status word", broken_check(lambda c: c[0].update(status="OK")), []),
    ("check without reason", broken_check(lambda c: c[0].pop("reason")), []),
    ("check reason not text", broken_check(lambda c: c[0].update(reason=3)), []),
    ("check paths not a list", broken_check(lambda c: c[0].update(paths="a")), []),
    ("check path not text", broken_check(lambda c: c[0].update(paths=[1])), []),
])
def test_report_that_breaks_the_contract_is_bad_output(aeve, stub, state, files, tmp_path, label, doc_set, drop):
    stub.set("verify-handoff", set=doc_set, drop=drop)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path).reason == "ROUTER_BAD_OUTPUT", label


@pytest.mark.parametrize("raw", ["", "not json", "[]", "5", '{"status": "VERIFIED", "status": "VERIFIED"}',
                                 '{"status": Infinity}', "\x00{}"])
def test_verify_stdout_that_is_not_a_strict_json_object_is_bad_output(aeve, stub, state, files, tmp_path, raw):  # AC-14
    stub.set("verify-handoff", raw=raw, exit=0)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path).reason == "ROUTER_BAD_OUTPUT"


def test_verify_stdout_over_the_cap_is_size_cap(aeve, stub, state, files, tmp_path):
    stub.set("verify-handoff", flood=5000)
    assert code_of(verify_run, aeve, stub, state, files, tmp_path, stdout_cap=1000).reason == "ROUTER_SIZE_CAP"


def test_verify_timeout_is_retried_twice_and_reports_the_retries(aeve, stub, state, files, tmp_path):  # AC-12
    stub.set("verify-handoff", sleep=60)
    err = code_of(verify_run, aeve, stub, state, files, tmp_path, timeout=1.5, sleep=lambda s: None)
    assert err.reason == "ROUTER_TIMEOUT" and err.retry_count == 2
    assert len(stub.calls("verify-handoff")) == 3


def test_verify_timeout_then_success_gives_the_verdict(aeve, stub, state, files, tmp_path):
    stub.set("verify-handoff", calls=[{"sleep": 60}, {}])
    result = verify_run(aeve, stub, state, files, tmp_path, timeout=2.0, sleep=lambda s: None)
    assert result.outcome == "ROUTED_VERIFIED" and result.retry_count == 1


def test_verify_pin_drift_makes_no_aeve_call(aeve, stub, state, files, tmp_path):
    assert code_of(verify_run, aeve, stub, state, files, tmp_path, pin_head="0" * 40).reason == "ROUTER_PIN_DRIFT"
    assert stub.calls() == []


def test_verify_in_a_dirty_checkout_makes_no_aeve_call(own_repo, stub, state, tmp_path):
    root, head = own_repo
    packet = packet_run(own_repo, stub, state)
    stub.reset()
    packet_path, result_path = tmp_path / "p.json", tmp_path / "r.json"
    packet_path.write_bytes(packet.packet_bytes)
    result_path.write_text(json.dumps(S.HOST_RESULT), encoding="utf-8")
    (root / "stray.txt").write_text("x", encoding="utf-8")
    err = code_of(rac.run_verify_handoff, packet_path, result_path, packet.packet, root=tmp_path, aeve_root=root,
                  state_dir=state, pin_head=head, command_prefix=stub.prefix, timeout=10.0)
    assert err.reason == "ROUTER_PIN_DRIFT" and stub.calls("verify-handoff") == []


@pytest.mark.parametrize("root", [None, ""])
def test_verify_without_a_root_is_refused_before_any_call(aeve, stub, state, files, tmp_path, root):
    assert code_of(verify_run, aeve, stub, state, files, tmp_path, root=root).reason == "ROUTER_BAD_REQUEST"
    assert stub.calls() == []


def test_verify_unknown_executable_is_aeve_missing(aeve, state, files, tmp_path):
    packet, packet_path, result_path = files
    root, head = aeve
    err = code_of(rac.run_verify_handoff, packet_path, result_path, packet.packet, root=tmp_path, aeve_root=root,
                  state_dir=state, pin_head=head, command_prefix=["definitely-not-an-executable-link2"], timeout=10.0)
    assert err.reason == "ROUTER_AEVE_MISSING"


# ============================================================ small pure functions
@pytest.mark.parametrize("statuses,expected", [
    (["PASS"] * 5, "VERIFIED"),
    (["PASS", "UNKNOWN"], "UNKNOWN"),
    (["PASS", "FAIL"], "REJECTED"),
    (["UNKNOWN", "FAIL", "PASS"], "REJECTED"),
    (["UNKNOWN"] * 5, "UNKNOWN"),
])
def test_worst_status_follows_the_design_rule(statuses, expected):
    assert rac.worst_status([{"status": s} for s in statuses]) == expected


def test_outcome_table_and_exit_table_match_the_design():
    assert rac.OUTCOME_FOR_STATUS == {"VERIFIED": "ROUTED_VERIFIED", "REJECTED": "ROUTED_REJECTED",
                                      "UNKNOWN": "ROUTED_UNKNOWN", "INVALID": "ROUTER_INVALID_INPUT"}
    assert rac.EXIT_FOR_STATUS == {"VERIFIED": 0, "REJECTED": 1, "UNKNOWN": 2, "INVALID": 3}


def test_defaults_match_the_design_constants():
    assert rac.DEFAULT_TIMEOUT_SECONDS == 120.0 and rac.DEFAULT_MAX_RETRIES == 2
    assert rac.DEFAULT_STDOUT_CAP == 1024 * 1024 and rac.DEFAULT_JITTER_SECONDS == (0.5, 2.0)


def test_load_pin_head_reads_the_pinned_head_of_the_shipped_role_table():
    table = json.loads(rac.DEFAULT_ROLE_TABLE.read_text(encoding="utf-8"))
    assert rac.load_pin_head() == table["aeve_pin"]["head"] == "35e5de868edaa37e021955147afb587011ca39c0"


@pytest.mark.parametrize("content", [None, "", "not json", "[]", "{}", '{"aeve_pin": {}}',
                                     '{"aeve_pin": {"head": "short"}}', '{"aeve_pin": {"head": 5}}',
                                     '{"aeve_pin": {"head": "' + "A" * 40 + '"}}', '{"aeve_pin": []}'])
def test_unreadable_or_malformed_pin_file_fails_closed_as_pin_drift(tmp_path, content):
    path = tmp_path / "role_table.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    assert code_of(rac.load_pin_head, path).reason == "ROUTER_PIN_DRIFT"


def test_load_pin_head_accepts_a_forty_hex_head(tmp_path):
    path = tmp_path / "role_table.json"
    path.write_text(json.dumps({"aeve_pin": {"head": "ab" * 20}}), encoding="utf-8")
    assert rac.load_pin_head(path) == "ab" * 20
