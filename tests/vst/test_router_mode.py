"""LINK-2 T5: router state, claim, concurrency and recovery (`tools/vst/router_mode.py`), AC-22 to AC-32.

Real boundaries are used: a real git repository stands in for the AEVE checkout (the pin check runs git), a stub
script stands in for `python -m aeve`, the claim and slot files are real O_EXCL files, concurrent callers are real
threads. Expected values come from the design document: the request digest is the SHA-256 of the canonical request
bytes (D4/D5), the recorded AEVE digest follows AEVE's formula, the stale claim age is 600 s, the temp-file age is 1 h,
the retention of a BLOCKED directory is 14 days, the slot cap is 2 (D4, D5).
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import threading
import time

import pytest

from tools.vst import router_mode as rm
from tools.vst import router_request as rr
from tools.vst.router_request import RouterError

from tests.vst import router_support as S

HOST_MARKER = "HOST-RESULT-MARKER-7c1e"  # must never reach the log


@pytest.fixture(scope="module")
def shared_repo(tmp_path_factory):
    root = tmp_path_factory.mktemp("aeve-mode") / "aeve"
    return root, S.make_aeve_repo(root)


class Env:
    def __init__(self, tmp_path, repo):
        self.tmp = tmp_path
        self.aeve_root, self.head = repo
        self.stub = S.Stub(tmp_path / "stub")
        self.state_root = tmp_path / "state"
        self.worktree = tmp_path / "worktree"
        self.worktree.mkdir()
        self.mode_path = S.link_mode_file(tmp_path, "router")
        self.host_result = tmp_path / "host" / "result.json"
        self.host_result.parent.mkdir()
        self.write_host(S.HOST_RESULT)
        self.cfg = rm.RouterConfig(command_prefix=self.stub.prefix, timeout=20.0, jitter=(0.0, 0.0),
                                   poll_seconds=0.05, lock_wait_seconds=30.0)

    def write_host(self, doc) -> bytes:
        data = json.dumps(doc).encode("utf-8") if not isinstance(doc, bytes) else doc
        self.host_result.write_bytes(data)
        return data

    def route(self, request=None, *, result="host", pin=None, cfg=None):
        source = self.host_result if result == "host" else result
        return rm.route_task(request or S.sample_request(), state_root=self.state_root, aeve_root=self.aeve_root,
                             root=self.worktree, result_source=source, pin_head=pin or self.head,
                             mode_path=self.mode_path, config=cfg or self.cfg)

    def with_cfg(self, **changes):
        return dataclasses.replace(self.cfg, **changes)

    # -- paths
    @property
    def router_root(self) -> pathlib.Path:
        return self.state_root / "router"

    def pending(self, request=None) -> pathlib.Path:
        request = request or S.sample_request()
        sha = rr.sha256_hex(rr.request_bytes(request))
        return self.router_root / request["task_id"] / f"{sha[:16]}-pending"

    def log(self) -> list[dict]:
        return S.read_log_lines(self.router_root / rm.LOG_NAME)

    def state_json(self, request=None) -> dict:
        return json.loads((self.pending(request) / rm.STATE_NAME).read_text(encoding="ascii"))


@pytest.fixture()
def env(tmp_path, shared_repo):
    return Env(tmp_path, shared_repo)


def code_of(func, *args, **kwargs) -> RouterError:
    with pytest.raises(RouterError) as info:
        func(*args, **kwargs)
    return info.value


# -- real OS locks (design D4): byte 0 of the file, msvcrt.locking on Windows, fcntl.flock elsewhere. These helpers are
# independent of the code under test: they speak to the operating system directly.
def os_lock(path: pathlib.Path):
    """Open (create) `path` and take the OS lock on byte 0 in this process: the descriptor, or None when held."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


HOLDER_SCRIPT = (
    "import os, sys\n"
    "fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)\n"
    "if os.name == 'nt':\n"
    "    import msvcrt\n"
    "    os.lseek(fd, 0, 0)\n"
    "    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)\n"
    "else:\n"
    "    import fcntl\n"
    "    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
    "print('held', flush=True)\n"
    "sys.stdin.readline()\n"
)


@pytest.fixture()
def holder():
    """Start a separate process that holds the OS lock of a file; yields start(path). Every process is killed at the end."""
    import subprocess
    import sys

    procs = []

    def start(path: pathlib.Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([sys.executable, "-I", "-c", HOLDER_SCRIPT, str(path)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True)
        procs.append(proc)
        assert proc.stdout.readline().strip() == "held"
        return proc

    yield start
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
        proc.wait(30)
        proc.stdin.close()
        proc.stdout.close()


# ============================================================ selection and request checks (AC-22, AC-23)
def test_gates_mode_makes_no_aeve_call_and_creates_nothing(env):  # AC-22
    (env.tmp / "gates").mkdir()
    env.mode_path = S.link_mode_file(env.tmp / "gates", "gates")
    err = code_of(env.route)
    assert err.reason == "ROUTER_NOT_SELECTED"
    assert env.stub.calls() == []
    assert not env.state_root.exists()


@pytest.mark.parametrize("content", [None, "", "not json", "[]"])
def test_unreadable_mode_file_is_not_selected_and_makes_no_call(env, content):
    path = env.tmp / "broken_mode.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    env.mode_path = path
    assert code_of(env.route).reason == "ROUTER_NOT_SELECTED"
    assert env.stub.calls() == []


def test_role_outside_the_five_is_refused_before_any_call(env):  # AC-23
    request = dict(S.sample_request(), role="loop-operator")
    assert code_of(env.route, request).reason == "ROUTER_BAD_REQUEST"
    assert env.stub.calls() == [] and not env.state_root.exists()


@pytest.mark.parametrize("change", [
    {"task_id": "../escape"}, {"task_id": "a/b"}, {"task_id": ""}, {"task_id": None}, {"task_id": 5},
    {"schema_version": "other"}, {"role": None},
])
def test_request_that_does_not_come_from_the_builder_is_refused(env, change):
    request = dict(S.sample_request(), **change)
    assert code_of(env.route, request).reason == "ROUTER_BAD_REQUEST"
    assert env.stub.calls() == []
    assert not (env.tmp / "escape").exists()


def test_a_non_mapping_request_is_refused(env):
    assert code_of(env.route, ["not", "a", "mapping"]).reason == "ROUTER_BAD_REQUEST"


def test_task_id_with_a_trailing_line_feed_cannot_become_a_directory_name(env):
    request = dict(S.sample_request(), task_id="LINK2-DEMO-1\n")
    assert code_of(env.route, request).reason == "ROUTER_BAD_REQUEST"
    assert env.stub.calls() == []


def test_state_root_that_is_a_file_is_state_dir_unusable(env):
    env.state_root.write_text("i am a file", encoding="utf-8")
    assert code_of(env.route).reason == "ROUTER_STATE_DIR_UNUSABLE"
    assert env.stub.calls() == []


# ============================================================ the normal flow
def test_without_a_result_the_row_waits_and_a_repeat_makes_no_aeve_call(env):
    row = env.route(result=None)
    assert row.state == "AWAITING_RESULT" and row.outcome is None and row.status is None
    assert row.result_sha256 is None and row.report_sha256 is None
    assert row.packet_sha256 and pathlib.Path(row.packet_path).is_file()
    assert rr.sha256_hex(pathlib.Path(row.packet_path).read_bytes()) == row.packet_sha256
    again = env.route(result=env.tmp / "host" / "not-yet.json")  # a missing host file is a normal wait
    assert again.state == "AWAITING_RESULT" and again.packet_sha256 == row.packet_sha256
    assert len(env.stub.calls("packet")) == 1 and env.stub.calls("verify-handoff") == []


def test_full_flow_records_every_digest_and_the_copy(env):
    request = S.sample_request()
    host_bytes = env.host_result.read_bytes()
    row = env.route(request)
    assert (row.state, row.outcome, row.status, row.task_id) == ("DONE", "ROUTED_VERIFIED", "VERIFIED", S.TASK)
    assert row.request_sha256 == rr.sha256_hex(rr.request_bytes(request))
    assert row.aeve_request_sha256 == S.expected_request_sha256(request)
    assert row.result_sha256 == rr.sha256_hex(host_bytes)
    assert row.pin_head == env.head and row.resume == "none" and row.reason == ""
    work = pathlib.Path(row.work_dir)
    assert (work / "result.json").read_bytes() == host_bytes
    assert rr.sha256_hex((work / "report.json").read_bytes()) == row.report_sha256
    assert work.name == f"{row.request_sha256[:16]}-{row.result_sha256[:16]}"
    assert work.parent == env.router_root / S.TASK
    assert len(env.stub.calls("packet")) == 1 and len(env.stub.calls("verify-handoff")) == 1


def test_aeve_only_ever_sees_the_vst_owned_copies_never_the_host_path(env):  # AC-27
    host_bytes = env.host_result.read_bytes()
    env.route()
    (call,) = env.stub.calls("verify-handoff")
    seen = pathlib.Path(call["result_path"]).resolve()
    assert seen != env.host_result.resolve()
    assert env.router_root.resolve() in seen.parents
    assert call["result_sha256_seen"] == rr.sha256_hex(host_bytes)
    assert env.router_root.resolve() in pathlib.Path(call["packet_path"]).resolve().parents
    assert call["root"] == str(env.worktree)


@pytest.mark.parametrize("checks,outcome,status", [
    ({"CHANGES_INSIDE_SCOPE": "FAIL"}, "ROUTED_REJECTED", "REJECTED"),
    ({"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN"}, "ROUTED_UNKNOWN", "UNKNOWN"),
])
def test_rejected_and_unknown_are_recorded_as_done_rows_not_errors(env, checks, outcome, status):
    env.stub.set("verify-handoff", checks=checks)
    row = env.route()
    assert (row.state, row.outcome, row.status) == ("DONE", outcome, status)
    assert row.outcome != "ROUTED_VERIFIED"


def test_invalid_input_is_a_done_row_with_the_reason_and_is_not_retried(env):
    env.stub.set("verify-handoff", raw=json.dumps({
        "executed_project_code": False, "llm_calls": 0, "reason": "PATH_INVALID:changed",
        "schema_version": "aeve.handoff_verify.v1", "source_modified": False, "status": "INVALID"}), exit=3)
    row = env.route()
    assert (row.outcome, row.status, row.reason) == ("ROUTER_INVALID_INPUT", "INVALID", "PATH_INVALID:changed")
    env.route()
    assert len(env.stub.calls("verify-handoff")) == 1  # the recorded verdict is adopted, not asked again


def test_new_host_result_gets_a_new_verdict_in_a_new_directory(env):
    first = env.route()
    env.write_host(dict(S.HOST_RESULT, changed=["src/other.py"]))
    env.stub.set("verify-handoff", checks={"TESTS_FOR_LOGIC": "FAIL"})
    second = env.route()
    assert first.outcome == "ROUTED_VERIFIED" and second.outcome == "ROUTED_REJECTED"
    assert first.work_dir != second.work_dir and first.result_sha256 != second.result_sha256
    assert len(env.stub.calls("verify-handoff")) == 2 and len(env.stub.calls("packet")) == 1
    assert pathlib.Path(first.work_dir, "result.json").is_file()  # the earlier copy is kept as evidence


def test_same_host_result_again_is_adopted_without_an_aeve_call(env):  # AC-28
    first = env.route()
    second = env.route()
    assert second.resume == "adopted"
    assert (second.outcome, second.result_sha256, second.report_sha256, second.work_dir) == (
        first.outcome, first.result_sha256, first.report_sha256, first.work_dir)
    assert len(env.stub.calls("packet")) == 1 and len(env.stub.calls("verify-handoff")) == 1
    assert [l["outcome"] for l in env.log() if l["step"] == "resume"] == ["adopted"]


def test_host_result_over_the_size_cap_is_refused_and_exactly_the_cap_is_taken(env):
    cfg = env.with_cfg(max_result_bytes=2000)
    base = json.dumps(S.HOST_RESULT).encode("utf-8")
    env.write_host(base + b" " * (2001 - len(base)))
    assert code_of(env.route, cfg=cfg).reason == "ROUTER_SIZE_CAP"
    assert env.stub.calls("verify-handoff") == []
    env.write_host(base + b" " * (2000 - len(base)))
    assert env.route(cfg=cfg).outcome == "ROUTED_VERIFIED"


# ============================================================ errors keep the state (retry, crash half-way)
def test_packet_timeout_leaves_state_new_and_a_retry_call_succeeds(env):
    env.stub.set("packet", sleep=60)
    err = code_of(env.route, cfg=env.with_cfg(timeout=1.0, max_retries=0))
    assert err.reason == "ROUTER_TIMEOUT"
    state = env.state_json()
    assert state["state"] == "NEW" and state["last_error"]["reason"] == "ROUTER_TIMEOUT"
    env.stub.reset()
    row = env.route()
    assert row.outcome == "ROUTED_VERIFIED"
    assert env.state_json()["last_error"] is None


def test_crash_after_packet_before_verify_never_reruns_packet(env):  # AC-26
    env.route(result=None)  # the process "dies" here: packet recorded, no result yet
    fd = os_lock(env.pending() / rm.CLAIM_NAME)  # the claim file stays, but the run must have let go of the OS lock
    assert fd is not None
    os.close(fd)
    row = env.route()
    assert row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("packet")) == 1 and len(env.stub.calls("verify-handoff")) == 1


def test_crash_while_a_process_holds_the_claim_resumes_at_once_after_it_is_killed(env, holder):  # AC-26, AC-25
    env.route(result=None)
    proc = holder(env.pending() / rm.CLAIM_NAME)  # a run that holds the claim ...
    assert code_of(env.route, cfg=env.with_cfg(lock_wait_seconds=0.3)).reason == "ROUTER_LOCK_TIMEOUT"
    proc.kill()  # ... and crashes: no release call, the OS drops the lock
    proc.wait(30)
    started = time.monotonic()
    row = env.route()
    assert time.monotonic() - started < 10  # at once: no age rule to wait out
    assert row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("packet")) == 1 and len(env.stub.calls("verify-handoff")) == 1
    assert not any("takeover" in json.dumps(l) for l in env.log())


@pytest.mark.parametrize("planted", [
    json.dumps({"owner": "dead-process", "created_at": 1.0}).encode("ascii"),
    json.dumps({"owner": "someone-else", "created_at": 9_999_999_999.0}).encode("ascii"),  # looks very fresh
    b"{torn", b"",
])
def test_a_pre_existing_claim_file_without_a_held_lock_never_blocks(env, planted):  # AC-25: no age rule at all
    env.route(result=None)
    claim = env.pending() / rm.CLAIM_NAME
    claim.write_bytes(planted)
    old = time.time() - 100_000
    os.utime(claim, (old, old))
    started = time.monotonic()
    row = env.route(cfg=env.with_cfg(lock_wait_seconds=0.5))
    assert time.monotonic() - started < 10 and row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("packet")) == 1


def test_crash_between_copy_and_verdict_reverifies_once_and_logs_rerun(env):  # AC-26
    env.stub.set("verify-handoff", sleep=60)
    assert code_of(env.route, cfg=env.with_cfg(timeout=1.0, max_retries=0)).reason == "ROUTER_TIMEOUT"
    state = env.state_json()
    assert state["state"] == "RESULT_COPIED" and state["last_error"]["reason"] == "ROUTER_TIMEOUT"
    env.stub.clear_spec()
    row = env.route()
    assert row.outcome == "ROUTED_VERIFIED" and row.resume == "rerun"
    assert len(env.stub.calls("packet")) == 1  # the recorded packet step is never repeated
    assert len(env.stub.calls("verify-handoff")) == 2
    assert [l["outcome"] for l in env.log() if l["step"] == "resume"] == ["rerun"]


def test_torn_state_file_is_treated_as_new_and_logged(env):
    env.route(result=None)
    state_path = env.pending() / rm.STATE_NAME
    state_path.write_bytes(state_path.read_bytes()[:25])  # a write cut in half
    row = env.route(result=None)
    assert row.state == "AWAITING_RESULT" and row.packet_sha256
    assert any(l["outcome"] == "STATE_TORN_TREATED_AS_NEW" for l in env.log())
    assert env.state_json()["state"] == "AWAITING_RESULT"


@pytest.mark.parametrize("bad_state", [
    {"schema": "other", "state": "DONE"},
    {"schema": rm.STATE_SCHEMA, "state": "BOGUS"},
    {"schema": rm.STATE_SCHEMA, "state": "DONE", "task_id": "OTHER", "request_sha256": "0" * 64},
])
def test_state_file_for_another_request_or_with_an_unknown_state_is_not_trusted(env, bad_state):
    env.route(result=None)
    (env.pending() / rm.STATE_NAME).write_text(json.dumps(bad_state), encoding="ascii")
    row = env.route()
    assert row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("verify-handoff")) == 1  # a forged DONE was not adopted


# ============================================================ tampering and digests (AC-27, AC-28, AC-29)
def test_copy_altered_by_the_verifier_run_gives_digest_mismatch_and_no_verdict(env):  # AC-27
    env.stub.set("verify-handoff", mutate_result=True)
    err = code_of(env.route)
    assert err.reason == "ROUTER_RESULT_DIGEST_MISMATCH"
    state = env.state_json()
    assert state["state"] == "RESULT_COPIED" and state.get("outcome") is None
    assert not list(env.router_root.glob(f"{S.TASK}/*/report.json"))


def test_copy_altered_between_calls_is_caught_before_any_aeve_call(env):  # AC-27
    env.stub.set("verify-handoff", sleep=60)
    code_of(env.route, cfg=env.with_cfg(timeout=1.0, max_retries=0))
    calls_before = len(env.stub.calls("verify-handoff"))
    (copy,) = env.router_root.glob(f"{S.TASK}/*/result.json")
    copy.write_bytes(copy.read_bytes() + b"\n")
    env.stub.clear_spec()
    assert code_of(env.route).reason == "ROUTER_RESULT_DIGEST_MISMATCH"
    assert len(env.stub.calls("verify-handoff")) == calls_before


def test_copy_altered_after_the_verdict_never_yields_a_verdict_again(env):  # AC-27, AC-28
    first = env.route()
    copy = pathlib.Path(first.work_dir) / "result.json"
    copy.write_bytes(copy.read_bytes().replace(b"src/app.py", b"src/evil.py"))
    assert code_of(env.route).reason == "ROUTER_RESULT_DIGEST_MISMATCH"
    report = rm.report_for_package(first)  # the package builder gets a digest that differs from the recorded one
    assert report["result_sha256_recomputed"] != report["result_sha256"]


@pytest.mark.parametrize("raw", [b'{"task_id": "x"', b"", b"[]", b"not json", b'{"a": 1, "a": 2}', b"\x00{}", b"\xff\xfe"])
def test_torn_or_malformed_host_result_is_bad_output_and_aeve_is_never_asked(env, raw):  # AC-29
    env.write_host(raw)
    assert code_of(env.route).reason == "ROUTER_BAD_OUTPUT"
    assert env.stub.calls("verify-handoff") == []
    assert env.state_json()["state"] == "RESULT_COPIED"


def test_corrected_host_result_after_a_torn_one_is_picked_up(env):
    """The host session may have been mid-write when VST copied; the story must not stay blocked on the torn copy."""
    env.write_host(b'{"task_id": "x"')
    assert code_of(env.route).reason == "ROUTER_BAD_OUTPUT"
    fixed = env.write_host(S.HOST_RESULT)
    row = env.route()
    assert row.outcome == "ROUTED_VERIFIED"
    assert row.result_sha256 == rr.sha256_hex(fixed)


def test_adopt_only_when_every_digest_matches_report_tamper_reruns(env):  # AC-28
    first = env.route()
    report = pathlib.Path(first.work_dir) / "report.json"
    original = report.read_bytes()
    report.write_bytes(original + b"\n")
    row = env.route()
    assert row.resume == "rerun" and row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("verify-handoff")) == 2
    assert rr.sha256_hex(report.read_bytes()) == row.report_sha256  # the report was rewritten from the new run
    assert [l["outcome"] for l in env.log() if l["step"] == "resume"] == ["rerun"]


def test_packet_tamper_reruns_the_packet_and_the_verification(env):  # AC-28
    first = env.route()
    packet = pathlib.Path(first.packet_path)
    packet.write_bytes(packet.read_bytes() + b" ")
    row = env.route()
    assert row.resume == "rerun" and row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("packet")) == 2 and len(env.stub.calls("verify-handoff")) == 2
    assert row.packet_sha256 == first.packet_sha256  # deterministic packet, same recorded digest


def test_a_changed_pin_head_reruns_the_verification_and_logs_rerun(env, tmp_path):  # AC-28
    first = env.route()
    moved = tmp_path / "aeve-moved"
    other_head = S.make_aeve_repo(moved, marker="a later aeve")
    assert other_head != env.head
    env.aeve_root = moved  # same state directory, another pin and the checkout at that pin
    row = env.route(pin=other_head)
    assert row.resume == "rerun" and row.pin_head == other_head and row.outcome == "ROUTED_VERIFIED"
    assert len(env.stub.calls("verify-handoff")) == 2
    assert first.pin_head == env.head
    assert env.state_json()["pin_head"] == other_head


def test_state_file_forged_to_verified_is_not_adopted(env):  # tampered result, UNKNOWN never passes
    env.stub.set("verify-handoff", checks={"EVIDENCE_DOCUMENTS_EXIST": "UNKNOWN"})
    first = env.route()
    assert first.outcome == "ROUTED_UNKNOWN"
    state_path = env.pending() / rm.STATE_NAME
    state = json.loads(state_path.read_text(encoding="ascii"))
    state.update(outcome="ROUTED_VERIFIED", status="VERIFIED")  # digests untouched: only the verdict is forged
    state_path.write_text(json.dumps(state), encoding="ascii")
    row = env.route()
    assert row.outcome != "ROUTED_VERIFIED", "a forged verdict in state.json was adopted"
    assert row.outcome == "ROUTED_UNKNOWN"


@pytest.mark.parametrize("tampered", [
    "../../../escape", "x", "", None, 7, "ABCDEF0123456789-0123456789abcdef",  # wrong prefix / shape
    "{prefix}-{short}", "{prefix}-{upper}", "{prefix}-{long}", "{prefix}/{hex16}", "{prefix}\\{hex16}",
])
def test_result_dir_tamper_fails_the_exact_name_check_on_rerun(env, tampered):  # D5: '<request16>-<result16 hex>'
    row = env.route()
    prefix = row.request_sha256[:16]
    hex16 = row.result_sha256[:16]
    if isinstance(tampered, str):
        tampered = tampered.format(prefix=prefix, hex16=hex16, short=hex16[:15], upper=hex16.upper() + "G"[:0] + "Z",
                                   long=hex16 + "0")
    state = env.state_json()
    assert state["result_dir"] == f"{prefix}-{hex16}"  # the exact form the design names
    state["result_dir"] = tampered
    (env.pending() / rm.STATE_NAME).write_bytes(json.dumps(state).encode("ascii"))
    calls_before = len(env.stub.calls("verify-handoff"))
    assert code_of(env.route).reason == "ROUTER_STATE_DIR_UNUSABLE"
    assert len(env.stub.calls("verify-handoff")) == calls_before  # nothing was verified through a forged path


def test_unknown_is_never_a_pass_through_the_whole_flow(env):
    env.stub.set("verify-handoff", checks={"TESTS_FOR_LOGIC": "UNKNOWN"})
    rows = [env.route(), env.route()]  # the second is an adoption
    for row in rows:
        assert row.outcome == "ROUTED_UNKNOWN" and row.status == "UNKNOWN"
        assert rm.route_gate(row.outcome, "CLEAN") == "BLOCKED"


# ============================================================ claim and concurrency (AC-24, AC-25, AC-30)
def run_threads(targets):
    results, errors = [None] * len(targets), [None] * len(targets)

    def wrap(index, target):
        try:
            results[index] = target()
        except BaseException as exc:  # noqa: BLE001 - the test inspects it
            errors[index] = exc

    threads = [threading.Thread(target=wrap, args=(i, t)) for i, t in enumerate(targets)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    return results, errors


def test_two_concurrent_runs_of_one_task_call_aeve_once_per_command_and_agree(env):  # AC-24
    env.stub.set("packet", sleep=1.0)
    results, errors = run_threads([env.route, env.route])
    assert errors == [None, None]
    first, second = results
    assert len(env.stub.calls("packet")) == 1 and len(env.stub.calls("verify-handoff")) == 1
    for field in ("state", "outcome", "status", "request_sha256", "packet_sha256", "result_sha256", "report_sha256",
                  "work_dir", "pin_head"):
        assert getattr(first, field) == getattr(second, field), field
    assert sorted(r.resume for r in results) == ["adopted", "none"]


def test_four_concurrent_runs_of_one_task_still_call_aeve_once(env):  # AC-24
    env.stub.set("packet", sleep=0.5)
    results, errors = run_threads([env.route] * 4)
    assert errors == [None] * 4
    assert len(env.stub.calls("packet")) == 1 and len(env.stub.calls("verify-handoff")) == 1
    assert len({r.report_sha256 for r in results}) == 1


def test_claim_held_by_another_process_makes_the_caller_wait_then_lock_timeout_then_acquire_at_once(env, holder):  # AC-25
    env.route(result=None)
    claim = env.pending() / rm.CLAIM_NAME
    proc = holder(claim)
    started = time.monotonic()
    err = code_of(env.route, cfg=env.with_cfg(lock_wait_seconds=0.6))
    assert err.reason == "ROUTER_LOCK_TIMEOUT"
    waited = time.monotonic() - started
    assert 0.6 <= waited < 20  # it waited the bounded time, no longer
    assert len(env.stub.calls("packet")) == 1 and env.stub.calls("verify-handoff") == []  # no AEVE call while blocked
    proc.stdin.write("\n")  # the holder ends normally: the lock is released
    proc.stdin.flush()
    proc.wait(30)
    started = time.monotonic()
    assert env.route().outcome == "ROUTED_VERIFIED"
    assert time.monotonic() - started < 10


def test_two_concurrent_claim_attempts_one_holds_the_other_times_out_in_a_thread(env):  # AC-25 (in-process holder)
    env.route(result=None)
    claim = env.pending() / rm.CLAIM_NAME
    fd = os_lock(claim)
    assert fd is not None
    try:
        results, errors = run_threads([lambda: env.route(cfg=env.with_cfg(lock_wait_seconds=0.5))])
        assert results == [None] and errors[0].reason == "ROUTER_LOCK_TIMEOUT"
    finally:
        os.close(fd)
    assert env.route().outcome == "ROUTED_VERIFIED"


def test_the_claim_is_held_for_the_whole_aeve_call_and_released_after(env):  # AC-24, AC-25
    env.stub.set("packet", sleep=1.5)
    claim = env.pending() / rm.CLAIM_NAME
    seen = []

    def probe():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not env.stub.calls("packet"):
            time.sleep(0.05)
        fd = os_lock(claim)  # while AEVE runs, the claim must be held
        seen.append(fd is not None)
        if fd is not None:
            os.close(fd)

    results, errors = run_threads([lambda: env.route(result=None), probe])
    assert errors == [None, None] and seen == [False]
    fd = os_lock(claim)
    assert fd is not None  # released after the run
    os.close(fd)


def test_claim_is_released_after_success_and_after_failure(env):
    claim = env.pending() / rm.CLAIM_NAME
    env.route()
    fd = os_lock(claim)
    assert fd is not None
    os.close(fd)
    env.stub.set("verify-handoff", exit=1)
    env.write_host(dict(S.HOST_RESULT, changed=["x.py"]))
    code_of(env.route)
    fd = os_lock(claim)
    assert fd is not None
    os.close(fd)


def test_slot_locks_are_released(env):
    env.route()
    slots = env.router_root / rm.SLOTS_DIRNAME
    assert slots.is_dir()
    for path in slots.glob("*.lock"):
        fd = os_lock(path)
        assert fd is not None, path.name
        os.close(fd)


def test_third_concurrent_aeve_call_waits_on_the_two_slot_cap(env):  # AC-30
    env.stub.set("packet", sleep=1.5)
    requests = [S.sample_request(task_id=f"LINK2-SLOT-{n}") for n in range(3)]
    results, errors = run_threads([(lambda r=r: env.route(r, result=None)) for r in requests])
    assert errors == [None, None, None]
    assert len(env.stub.calls("packet")) == 3
    assert env.stub.max_overlap("packet") <= 2  # never 3 at once
    starts = sorted(c["time"] for c in env.stub.calls("packet"))
    ends = sorted(c["time"] for c in env.stub.calls("packet", "end"))
    assert starts[2] >= ends[0]  # the third call started only after one of the first two had finished
    assert {r.task_id for r in results} == {r["task_id"] for r in requests}


def test_one_slot_config_serialises_the_calls(env):
    env.stub.set("packet", sleep=0.8)
    requests = [S.sample_request(task_id=f"LINK2-ONE-{n}") for n in range(2)]
    cfg = env.with_cfg(max_slots=1)
    results, errors = run_threads([(lambda r=r: env.route(r, result=None, cfg=cfg)) for r in requests])
    assert errors == [None, None] and env.stub.max_overlap("packet") == 1


def test_waiting_for_a_slot_is_bounded(env):
    slots = env.router_root / rm.SLOTS_DIRNAME
    slots.mkdir(parents=True)
    fds = [os_lock(slots / f"slot-{index}.lock") for index in range(2)]
    try:
        assert None not in fds
        err = code_of(env.route, result=None, cfg=env.with_cfg(lock_wait_seconds=0.4))
        assert err.reason == "ROUTER_LOCK_TIMEOUT"
        assert env.stub.calls() == []
    finally:
        for fd in fds:
            os.close(fd)
    assert env.route(result=None).state == "AWAITING_RESULT"  # slots free again: acquired at once


# ============================================================ sweep and retention (AC-31)
def age(path: pathlib.Path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def test_stale_tmp_files_are_swept_and_fresh_ones_kept(env):  # AC-31
    env.route(result=None)
    old, young = env.router_root / S.TASK / "old.json.tmp", env.router_root / S.TASK / "young.json.tmp"
    old.write_text("x")
    young.write_text("x")
    age(old, 3601)
    age(young, 3500)
    env.route(result=None)
    assert not old.exists() and young.exists()


def test_sweep_returns_the_counts_and_touches_nothing_outside_the_router_root(env):  # AC-31
    env.route(result=None)
    outside = env.state_root / "outside.tmp"
    sibling = env.state_root / "other"
    sibling.mkdir()
    nested = sibling / "keep.tmp"
    outside.write_text("x")
    nested.write_text("x")
    for path in (outside, nested):
        age(path, 10 * 3600)
    inside = env.router_root / "inside.tmp"
    inside.write_text("x")
    age(inside, 10 * 3600)
    counts = rm.sweep(env.router_root, env.cfg)
    assert counts["tmp"] == 1 and not inside.exists()
    assert outside.exists() and nested.exists()


def test_blocked_directory_older_than_14_days_is_removed_and_healthy_ones_stay(env):  # AC-31
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    blocked_request = S.sample_request(task_id="LINK2-OLD-BLOCKED")
    blocked = env.route(blocked_request)
    assert blocked.outcome == "ROUTED_REJECTED"
    env.stub.reset()
    good_request = S.sample_request(task_id="LINK2-OLD-GOOD")
    good = env.route(good_request)
    waiting_request = S.sample_request(task_id="LINK2-OLD-WAIT")
    env.route(waiting_request, result=None)
    for request in (blocked_request, good_request, waiting_request):
        age(env.pending(request) / rm.STATE_NAME, 15 * 86400)
    env.route(S.sample_request(task_id="LINK2-TRIGGER"), result=None)  # any run sweeps first
    assert not env.pending(blocked_request).exists()
    assert not pathlib.Path(blocked.work_dir).exists()
    assert env.pending(good_request).exists() and pathlib.Path(good.work_dir).exists()
    assert env.pending(waiting_request).exists()


def test_blocked_directory_younger_than_14_days_stays(env):  # AC-31
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    request = S.sample_request(task_id="LINK2-YOUNG-BLOCKED")
    row = env.route(request)
    age(env.pending(request) / rm.STATE_NAME, 13 * 86400)
    rm.sweep(env.router_root, env.cfg)
    assert env.pending(request).exists() and pathlib.Path(row.work_dir).exists()


def test_a_directory_with_a_claim_is_never_swept(env):  # AC-31
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    request = S.sample_request(task_id="LINK2-CLAIMED")
    env.route(request)
    age(env.pending(request) / rm.STATE_NAME, 20 * 86400)
    fd = os_lock(env.pending(request) / rm.CLAIM_NAME)  # a live run holds the claim
    assert fd is not None
    try:
        rm.sweep(env.router_root, env.cfg)
        assert env.pending(request).exists()  # the held claim protects the directory
    finally:
        os.close(fd)
    rm.sweep(env.router_root, env.cfg)
    assert not env.pending(request).exists()  # once the claim is free the old BLOCKED directory goes


def test_a_pre_existing_free_claim_file_does_not_protect_an_old_blocked_directory(env):  # AC-31, AC-25
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    request = S.sample_request(task_id="LINK2-FREECLAIM")
    env.route(request)
    age(env.pending(request) / rm.STATE_NAME, 20 * 86400)
    (env.pending(request) / rm.CLAIM_NAME).write_text(json.dumps({"owner": "x", "created_at": time.time()}))
    rm.sweep(env.router_root, env.cfg)
    assert not env.pending(request).exists()


def test_sweep_skips_a_held_claim_held_by_another_process(env, holder):  # AC-31
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    request = S.sample_request(task_id="LINK2-HELDPROC")
    env.route(request)
    age(env.pending(request) / rm.STATE_NAME, 20 * 86400)
    proc = holder(env.pending(request) / rm.CLAIM_NAME)
    rm.sweep(env.router_root, env.cfg)
    assert env.pending(request).exists()
    proc.kill()
    proc.wait(30)
    rm.sweep(env.router_root, env.cfg)  # crashed holder: the OS dropped the lock, the sweep may remove it now
    assert not env.pending(request).exists()


def test_release_work_dir_refuses_while_the_claim_is_held_and_works_after(env, holder):  # D4
    first = env.route(S.sample_request(task_id="LINK2-REL-HELD"))
    claim = env.pending(S.sample_request(task_id="LINK2-REL-HELD")) / rm.CLAIM_NAME
    proc = holder(claim)
    assert code_of(rm.release_work_dir, env.state_root, "LINK2-REL-HELD", first.request_sha256).reason == \
        "ROUTER_LOCK_TIMEOUT"
    assert pathlib.Path(first.work_dir).exists() and env.pending(S.sample_request(task_id="LINK2-REL-HELD")).exists()
    proc.kill()
    proc.wait(30)
    assert rm.release_work_dir(env.state_root, "LINK2-REL-HELD", first.request_sha256) == 2
    assert not (env.router_root / "LINK2-REL-HELD").exists()


def snapshot(root: pathlib.Path) -> dict[str, bytes]:
    """Every file under `root` (relative posix path -> bytes), claim.lock excluded: the claim file is the lock itself."""
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*"))
            if path.is_file() and path.name != rm.CLAIM_NAME}


def test_release_work_dir_with_a_foreign_held_claim_deletes_nothing_at_all(env, holder):  # AC-25, D4 (LINK2-FIX3)
    request = S.sample_request(task_id="LINK2-REL-INTACT")
    row = env.route(request)  # full flow: pending dir (state, packet) and a result dir
    task_dir = env.router_root / "LINK2-REL-INTACT"
    before = snapshot(task_dir)
    assert any(name.endswith(rm.STATE_NAME) for name in before) and len(before) >= 3
    proc = holder(env.pending(request) / rm.CLAIM_NAME)
    err = code_of(rm.release_work_dir, env.state_root, "LINK2-REL-INTACT", row.request_sha256)
    assert err.reason == "ROUTER_LOCK_TIMEOUT"
    assert snapshot(task_dir) == before  # every file, byte for byte; nothing half-deleted
    assert pathlib.Path(row.work_dir).is_dir() and pathlib.Path(row.packet_path).is_file()
    assert (env.pending(request) / rm.CLAIM_NAME).exists()
    proc.kill()
    proc.wait(30)


def test_release_work_dir_on_a_free_claim_removes_everything_including_claim_lock(env):  # D4
    request = S.sample_request(task_id="LINK2-REL-FREE")
    row = env.route(request)
    assert (env.pending(request) / rm.CLAIM_NAME).exists()  # a run leaves its claim file behind
    assert rm.release_work_dir(env.state_root, "LINK2-REL-FREE", row.request_sha256) == 2
    assert not env.pending(request).exists() and not pathlib.Path(row.work_dir).exists()
    assert not (env.router_root / "LINK2-REL-FREE").exists()  # claim.lock and the task directory are gone too
    assert list(env.router_root.rglob(rm.CLAIM_NAME)) == []


def test_sweep_skips_a_foreign_held_claim_and_leaves_every_file_intact(env, holder):  # AC-31, AC-25 (LINK2-FIX3)
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    request = S.sample_request(task_id="LINK2-SWEEP-INTACT")
    env.route(request)
    age(env.pending(request) / rm.STATE_NAME, 20 * 86400)
    task_dir = env.router_root / "LINK2-SWEEP-INTACT"
    before = snapshot(task_dir)
    proc = holder(env.pending(request) / rm.CLAIM_NAME)
    counts = rm.sweep(env.router_root, env.cfg)
    assert counts["blocked_dirs"] == 0
    assert snapshot(task_dir) == before
    proc.kill()
    proc.wait(30)
    counts = rm.sweep(env.router_root, env.cfg)  # the OS dropped the dead holder's lock: now it goes, claim.lock too
    assert counts["blocked_dirs"] >= 1 and not env.pending(request).exists()


def test_old_blocked_directory_with_a_free_claim_is_swept_with_its_claim_file(env):  # AC-31
    env.stub.set("verify-handoff", checks={"CHANGES_INSIDE_SCOPE": "FAIL"})
    request = S.sample_request(task_id="LINK2-SWEEP-FREE")
    row = env.route(request)
    age(env.pending(request) / rm.STATE_NAME, 20 * 86400)
    rm.sweep(env.router_root, env.cfg)
    assert not env.pending(request).exists() and not pathlib.Path(row.work_dir).exists()
    assert list((env.router_root / "LINK2-SWEEP-FREE").rglob(rm.CLAIM_NAME)) == []


def _slow_unlink(monkeypatch, releaser_thread_name: str, started: threading.Event, pause: float) -> None:
    """Test-side seam: make every unlink done by the releasing thread slow, so the deletion window is wide. This slows the
    cleanup only; the claim logic under test is untouched."""
    real = os.unlink

    def slow(path, *args, **kwargs):
        if threading.current_thread().name == releaser_thread_name:
            started.set()
            time.sleep(pause)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", slow)


def _release_while_another_run_arrives(env, monkeypatch, acquirer_cfg):
    """Fill the pending directory with many files, start release_work_dir in a thread with slow unlinks and, once the
    deletion began, let another caller (same process, own file handle: the OS lock still conflicts) call route_task for
    the same request. Returns (release outcome, acquirer outcome)."""
    request = S.sample_request(task_id="LINK2-REL-RACE")
    row = env.route(request)  # state DONE, a verdict, a result dir: valid state a half-read would adopt
    for index in range(40):
        (env.pending(request) / f"filler-{index:02d}.bin").write_bytes(b"x" * 64)
    started = threading.Event()
    _slow_unlink(monkeypatch, "releaser", started, 0.03)  # about 1.2 s of deletion
    outcome: dict[str, object] = {}

    def release():
        try:
            outcome["released"] = rm.release_work_dir(env.state_root, "LINK2-REL-RACE", row.request_sha256)
        except BaseException as exc:  # recorded and asserted by the caller
            outcome["release_error"] = exc

    def acquire():
        try:
            outcome["row"] = env.route(request, result=None, cfg=acquirer_cfg)
        except RouterError as exc:
            outcome["acquire_error"] = exc

    releaser = threading.Thread(target=release, name="releaser")
    releaser.start()
    assert started.wait(10), "the deletion never started"
    acquirer = threading.Thread(target=acquire, name="acquirer")
    acquirer.start()
    releaser.join(60)
    acquirer.join(60)
    assert not releaser.is_alive() and not acquirer.is_alive()
    return row, outcome


def test_a_caller_arriving_during_the_deletion_times_out_and_sees_no_half_deleted_state(env, monkeypatch):  # AC-25
    impatient = env.with_cfg(lock_wait_seconds=0.3)  # shorter than the deletion: cannot wait it out
    row, outcome = _release_while_another_run_arrives(env, monkeypatch, impatient)
    assert outcome.get("released") == 2, outcome  # the deletion was not disturbed
    err = outcome.get("acquire_error")
    assert isinstance(err, RouterError) and err.reason == "ROUTER_LOCK_TIMEOUT", outcome
    assert "row" not in outcome  # no row built from a half-deleted state
    assert not (env.router_root / "LINK2-REL-RACE").exists()  # and the caller left nothing behind


def test_a_caller_arriving_during_the_deletion_waits_then_starts_fresh_never_adopts_the_old_row(env, monkeypatch):  # AC-25
    patient = env.with_cfg(lock_wait_seconds=30.0)
    row, outcome = _release_while_another_run_arrives(env, monkeypatch, patient)
    assert outcome.get("released") == 2, outcome
    assert "acquire_error" not in outcome, outcome
    fresh = outcome["row"]
    # the old request was DONE with a verdict; after the cleanup the same request starts from nothing: it waits for a
    # result again and carries no digest of the deleted run
    assert fresh.state == "AWAITING_RESULT" and fresh.outcome is None and fresh.report_sha256 is None
    assert fresh.result_sha256 is None
    assert pathlib.Path(fresh.packet_path).is_file()  # a new packet exists on disk, not a dangling path


def test_release_work_dir_has_no_config_parameter():
    import inspect

    assert list(inspect.signature(rm.release_work_dir).parameters) == ["state_root", "task_id", "request_sha256"]


def test_config_has_no_claim_stale_seconds_any_more():
    assert not hasattr(rm.RouterConfig(), "claim_stale_seconds")


def test_release_work_dir_removes_only_the_requests_directories(env):
    one, two = S.sample_request(task_id="LINK2-REL-1"), S.sample_request(task_id="LINK2-REL-2")
    first = env.route(one)
    second = env.route(two)
    removed = rm.release_work_dir(env.state_root, "LINK2-REL-1", first.request_sha256)
    assert removed == 2  # the pending directory and the result directory
    assert not (env.router_root / "LINK2-REL-1").exists()
    assert pathlib.Path(second.work_dir).exists() and env.pending(two).exists()
    assert (env.router_root / rm.LOG_NAME).exists()


@pytest.mark.parametrize("task_id,sha", [("../x", "a" * 64), ("a/b", "a" * 64), ("", "a" * 64), ("ok", "short"),
                                        (None, "a" * 64)])
def test_release_work_dir_refuses_malformed_arguments(env, task_id, sha):
    assert code_of(rm.release_work_dir, env.state_root, task_id, sha).reason == "ROUTER_BAD_REQUEST"


def test_release_work_dir_cannot_be_pointed_outside_the_router_root(env):
    victim = env.state_root / "victim"
    victim.mkdir(parents=True)
    (victim / "keep.txt").write_text("x")
    code_of(rm.release_work_dir, env.state_root, "..", "a" * 64)
    assert (victim / "keep.txt").exists()


# ============================================================ log (AC-32)
LOG_FIELDS = {"at", "task_id", "request_sha256", "step", "outcome", "retry_count", "resume"}


def test_every_step_writes_one_log_line_with_the_design_fields_and_no_content(env):  # AC-32
    env.write_host(dict(S.HOST_RESULT, note=HOST_MARKER))
    row = env.route()
    lines = env.log()
    assert [l["step"] for l in lines] == ["packet", "result_copy", "verify"]
    for line in lines:
        assert set(line) == LOG_FIELDS
        assert line["task_id"] == S.TASK and line["request_sha256"] == row.request_sha256
        assert line["retry_count"] == 0 and line["resume"] == "none"
    assert [l["outcome"] for l in lines] == ["OK", "OK", "ROUTED_VERIFIED"]
    text = (env.router_root / rm.LOG_NAME).read_text(encoding="ascii")
    assert HOST_MARKER not in text and "src/app.py" not in text and "Result stays inside scope" not in text
    assert text.count("\n") == 3


def test_failed_step_is_logged_with_its_reason_and_retry_count(env):
    env.stub.set("packet", sleep=60)
    code_of(env.route, cfg=env.with_cfg(timeout=1.0, max_retries=1, sleep=lambda s: None))
    (line,) = env.log()
    assert (line["step"], line["outcome"], line["retry_count"]) == ("packet", "ROUTER_TIMEOUT", 1)


def test_log_failure_never_changes_the_routing_result(env, monkeypatch):
    env.router_root.mkdir(parents=True)
    (env.router_root / rm.LOG_NAME).mkdir()  # a directory where the log file should be: every write fails
    assert env.route().outcome == "ROUTED_VERIFIED"


# ============================================================ package row
def test_report_for_package_carries_the_row_and_the_digest_hashed_now(env):
    row = env.route()
    report = rm.report_for_package(row)
    assert report == dict(row.to_report(), result_sha256_recomputed=row.result_sha256,
                          aeve_request_sha256=row.aeve_request_sha256)
    assert set(row.to_report()) == {"outcome", "status", "task_id", "request_sha256", "packet_sha256",
                                    "result_sha256", "report_sha256", "pin_head"}


def test_report_for_package_without_a_verdict_is_not_verified(env):
    row = env.route(result=None)
    assert code_of(rm.report_for_package, row).reason == "ROUTER_NOT_VERIFIED"


def test_report_for_package_with_a_missing_copy_can_never_match(env):
    row = env.route()
    (pathlib.Path(row.work_dir) / "result.json").unlink()
    assert rm.report_for_package(row)["result_sha256_recomputed"] == "0" * 64


# ============================================================ constants
def test_defaults_match_the_design():
    cfg = rm.RouterConfig()
    assert (cfg.lock_wait_seconds, cfg.poll_seconds, cfg.max_slots) == (60.0, 0.5, 2)
    assert (cfg.tmp_max_age_seconds, cfg.blocked_retention_seconds) == (3600.0, 14 * 86400.0)
    assert cfg.max_result_bytes == 1024 * 1024 and cfg.timeout == 120.0 and cfg.max_retries == 2
