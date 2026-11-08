"""U1-5: AEVE CLI adapter, driven with stub 'aeve' scripts through command_prefix (no real AEVE)."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time

import pytest

from uc import adapter

from tests.uc import ucsupport as S

HEAD = S.HEAD


@pytest.fixture()
def env(tmp_path):
    root = tmp_path / "reviewed"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n")
    aeve_root = tmp_path / "aeve"
    (aeve_root / "src").mkdir(parents=True)
    return {"root": root, "aeve": aeve_root, "state": tmp_path / "state", "stubs": tmp_path / "stubs",
            "tmp": tmp_path}


def make_request(env, **over):
    kw = dict(request_id="r1", root=str(env["root"]), base_revision=HEAD, changed_paths=["a.py"],
              executor_ids=["g2.python-rules"])
    kw.update(over)
    return adapter.build_aeve_request(**kw)


def run(env, body, request=None, **kw):
    prefix = S.write_stub(env["stubs"], body)
    return adapter.run_review(request or make_request(env), aeve_root=env["aeve"], state_dir=env["state"],
                              command_prefix=prefix, **kw)


def blocked(env, body, request=None, **kw):
    with pytest.raises(adapter.AdapterBlocked) as info:
        run(env, body, request, **kw)
    return info.value


# ------------------------------------------------------------------ request builder
def test_build_request_is_v2_with_all_fields_and_defaults():
    r = adapter.build_aeve_request(request_id="x", root="/r", base_revision=HEAD, changed_paths=["a"])
    assert r == {
        "schema_version": "aeve.review.request.v2", "request_id": "x", "root": "/r", "base_revision": HEAD,
        "changed_paths": ["a"], "review_domains": [], "profile_ids": [], "executor_ids": [], "criteria": [],
        "iteration_of": None, "allow_dirty": False,
    }


def test_build_request_copies_lists_and_coerces_allow_dirty():
    paths = ["a"]
    r = adapter.build_aeve_request(request_id="x", root="/r", base_revision=HEAD, changed_paths=paths,
                                   executor_ids=["e"], criteria=["c"], iteration_of="p", allow_dirty=1)
    paths.append("b")
    assert r["changed_paths"] == ["a"] and r["allow_dirty"] is True and r["iteration_of"] == "p"


# ------------------------------------------------------------------ happy path
def test_happy_path_returns_validated_response(env):
    resp = run(env, "emit(good())")
    assert resp["status"] == "COMPLETE" and resp["request_id"] == "r1" and resp["head"] == HEAD
    assert resp["executor_ids"] == ["g2.python-rules"]


def test_exit_three_with_findings_is_accepted(env):
    body = "emit(good(status='PARTIAL', findings=[{'executor_id': 'g2.python-rules', 'severity': 'MAJOR'}]), 3)"
    resp = run(env, body)
    assert resp["status"] == "PARTIAL" and len(resp["findings"]) == 1


def test_child_receives_v2_request_in_private_dir_outside_reviewed_root_and_cleans_up(env):
    capture = env["tmp"] / "capture.json"
    body = f"""
    import pathlib
    pathlib.Path({str(capture)!r}).write_text(json.dumps({{'req': req, 'path': req_path, 'cwd': os.getcwd(),
        'argv': sys.argv[1:-1]}}))
    emit(good())
    """
    run(env, body)
    cap = json.loads(capture.read_text())
    root = env["root"].resolve()
    assert cap["req"]["schema_version"] == "aeve.review.request.v2"
    assert cap["argv"] == ["review", "--request"]
    for p in (cap["path"], cap["cwd"]):
        resolved = pathlib.Path(p).resolve()
        assert root != resolved and root not in resolved.parents, p
    assert pathlib.Path(cap["cwd"]).resolve() == pathlib.Path(cap["path"]).resolve().parent
    assert not pathlib.Path(cap["path"]).exists(), "private request directory must be removed after the run"


def test_child_environment_is_minimal_pinned_and_isolated(env):
    capture = env["tmp"] / "env.json"
    body = f"""
    import pathlib
    pathlib.Path({str(capture)!r}).write_text(json.dumps(dict(os.environ)))
    emit(good())
    """
    os.environ["UC_SECRET_PROBE"] = "must-not-leak"
    try:
        run(env, body)
    finally:
        del os.environ["UC_SECRET_PROBE"]
    child = json.loads(capture.read_text())
    assert "UC_SECRET_PROBE" not in child
    assert child["PYTHONPATH"] == str(env["aeve"].resolve() / "src")
    assert child["PYTHONDONTWRITEBYTECODE"] == "1" and child["PYTHONNOUSERSITE"] == "1"
    assert child["LOCALAPPDATA"] == str(env["state"]) and child["APPDATA"] == str(env["state"])
    allowed = {"PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "PYTHONPATH",
               "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE", "PYTHONIOENCODING", "LOCALAPPDATA", "APPDATA"}
    assert {k.upper() for k in child} <= {k.upper() for k in allowed} | {"SYSTEMDRIVE", "PROCESSOR_ARCHITECTURE"}


def test_stdin_is_closed(env):
    body = "emit(good(uncovered=[sys.stdin.read()]))"
    assert run(env, body)["uncovered"] == [""]


# ------------------------------------------------------------------ failure rows
def test_timeout_returns_promptly_and_reports_timeout(env):
    start = time.monotonic()
    err = blocked(env, "time.sleep(60)", timeout=1.5)
    elapsed = time.monotonic() - start
    assert err.reason == "TIMEOUT"
    assert elapsed < 12, f"timeout must kill and return, took {elapsed:.1f}s"


def test_timeout_kills_grandchild_process_tree(env):
    marker = env["tmp"] / "grandchild-survived.txt"
    body = f"""
    import subprocess
    code = "import time, pathlib; time.sleep(5); pathlib.Path({str(marker)!r}).write_text('alive')"
    subprocess.Popen([sys.executable, '-c', code])
    time.sleep(60)
    """
    assert blocked(env, body, timeout=1.5).reason == "TIMEOUT"
    time.sleep(7)
    assert not marker.exists(), "grandchild survived the timeout kill (process tree not terminated)"


def test_stdout_cap_exceeded_is_blocked(env):
    body = "sys.stdout.write('x' * 5000); sys.stdout.flush()"
    err = blocked(env, body, stdout_cap=1000)
    assert err.reason == "OUTPUT_TOO_LARGE"


def test_stdout_cap_boundary_exact_size_passes_one_less_fails(env):
    size_file = env["tmp"] / "size.txt"
    body = f"""
    import pathlib
    text = json.dumps(good())
    pathlib.Path({str(size_file)!r}).write_text(str(len(text.encode())))
    sys.stdout.write(text); sys.stdout.flush()
    """
    run(env, body, stdout_cap=1 << 20)
    n = int(size_file.read_text())
    assert n > 100
    assert run(env, body, stdout_cap=n)["status"] == "COMPLETE"
    assert blocked(env, body, stdout_cap=n - 1).reason == "OUTPUT_TOO_LARGE"


def test_stderr_flood_is_blocked_even_with_valid_stdout(env):
    body = "sys.stderr.write('e' * 300000); sys.stderr.flush(); emit(good())"
    assert blocked(env, body).reason == "OUTPUT_TOO_LARGE"


@pytest.mark.parametrize("code", [1, 2, 4, 255])
def test_unexpected_exit_codes_are_blocked(env, code):
    err = blocked(env, f"sys.stdout.write(json.dumps(good())); sys.exit({code})")
    assert err.reason == "AEVE_EXIT" and str(code) in err.detail


def test_non_json_output(env):
    assert blocked(env, "print('hello, not json')").reason == "BAD_OUTPUT"


def test_empty_output(env):
    assert blocked(env, "pass").reason == "BAD_OUTPUT"


def test_nul_byte_in_output(env):
    body = "sys.stdout.buffer.write(json.dumps(good()).encode() + b'\\x00'); sys.stdout.flush()"
    err = blocked(env, body)
    assert err.reason == "BAD_OUTPUT" and "NUL" in err.detail


def test_invalid_utf8_output(env):
    assert blocked(env, "sys.stdout.buffer.write(b'\\xff\\xfe{}')").reason == "BAD_OUTPUT"


@pytest.mark.parametrize("payload", ["[]", "5", "null", '"text"'])
def test_json_that_is_not_an_object(env, payload):
    err = blocked(env, f"sys.stdout.write({payload!r})")
    assert err.reason == "BAD_OUTPUT"


def test_missing_executable(env):
    with pytest.raises(adapter.AdapterBlocked) as info:
        adapter.run_review(make_request(env), aeve_root=env["aeve"], state_dir=env["state"],
                           command_prefix=[str(env["tmp"] / "no-such-binary.exe")])
    assert info.value.reason == "EXEC_FAILED"


def test_response_claiming_model_calls(env):
    for over in ("llm_calls=1", "llm_calls=None", "executed_project_code=True", "executed_project_code=None",
                 "source_modified=True", "source_modified=None"):
        err = blocked(env, f"emit(good({over}))")
        assert err.reason == "AEVE_CONTRACT_VIOLATION", over


def test_head_mismatch(env):
    err = blocked(env, "emit(good(head='f' * 40))")
    assert err.reason == "HEAD_MOVED"


def test_request_id_mismatch(env):
    err = blocked(env, "emit(good(request_id='someone-else'))")
    assert err.reason == "AEVE_CONTRACT_VIOLATION" and "request_id" in err.detail


@pytest.mark.parametrize("missing", list(adapter.REQUIRED_RESPONSE_KEYS))
def test_every_required_response_key_is_enforced(env, missing):
    body = f"d = good(); d.pop({missing!r}); emit(d)"
    err = blocked(env, body)
    assert err.reason in ("AEVE_CONTRACT_VIOLATION",) and missing in err.detail


@pytest.mark.parametrize("field", ["results", "findings", "executor_ids"])
def test_list_fields_must_be_lists(env, field):
    assert blocked(env, f"emit(good({field}='oops'))").reason == "AEVE_CONTRACT_VIOLATION"


def test_exit_zero_requires_complete_status_and_no_findings(env):
    assert blocked(env, "emit(good(status='PARTIAL'), 0)").reason == "AEVE_CONTRACT_VIOLATION"
    assert blocked(env, "emit(good(findings=[{'x': 1}]), 0)").reason == "AEVE_CONTRACT_VIOLATION"


# ------------------------------------------------------------------ dirty tree and receipts
def test_dirty_response_allowed_for_advisory(env):
    assert run(env, "emit(good(dirty=True))")["dirty"] is True


def test_dirty_response_blocked_for_receipt(env):
    req = make_request(env, allow_dirty=False)
    err = blocked(env, "emit(good(dirty=True))", req, require_clean_tree=True)
    assert err.reason == "DIRTY_TREE"


def test_receipt_clean_tree_passes(env):
    assert run(env, "emit(good(dirty=False))", require_clean_tree=True)["dirty"] is False


@pytest.mark.parametrize("value", [None, 0, "false", ""])
def test_receipt_requires_dirty_to_be_exactly_false(env, value):
    err = blocked(env, f"emit(good(dirty={value!r}))", require_clean_tree=True)
    assert err.reason == "DIRTY_TREE"


def test_receipt_with_allow_dirty_is_refused_before_anything_runs(env):
    marker = env["tmp"] / "ran.txt"
    body = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran'); emit(good())"
    req = make_request(env, allow_dirty=True)
    err = blocked(env, body, req, require_clean_tree=True)
    assert err.reason == "DIRTY_NOT_ALLOWED_FOR_RECEIPT"
    assert not marker.exists(), "no child may be started for a refused receipt request"


# ------------------------------------------------------------------ short refusal envelopes
@pytest.mark.parametrize("status", ["NOT_COVERED", "BLOCKED", "INVALID"])
def test_short_refusal_envelope_raises_aeve_refused(env, status):
    body = f"emit({{'schema_version': 'aeve.review.result.v1', 'status': {status!r}, 'reason': 'REQUIRES_REQUEST_V2', " \
           "'llm_calls': 0, 'executed_project_code': False, 'source_modified': False}, 3)"
    with pytest.raises(adapter.AeveRefused) as info:
        run(env, body)
    err = info.value
    assert (err.aeve_status, err.aeve_reason, err.reason) == (status, "REQUIRES_REQUEST_V2", "AEVE_REFUSED")
    assert isinstance(err, adapter.AdapterBlocked)


def test_refusal_without_optional_flags_or_request_id_still_refused(env):
    with pytest.raises(adapter.AeveRefused):
        run(env, "emit({'status': 'INVALID', 'reason': 'REVIEW_REQUEST_FILE_INVALID'}, 3)")


@pytest.mark.parametrize("extra", ["'findings': []", "'results': []", "'findings': [{'a': 1}], 'results': [1]"])
def test_refusal_envelope_carrying_review_output_is_a_contract_violation(env, extra):
    body = f"emit({{'status': 'BLOCKED', 'reason': 'X', {extra}}}, 3)"
    err = blocked(env, body)
    assert err.reason == "AEVE_CONTRACT_VIOLATION" and not isinstance(err, adapter.AeveRefused)


def test_refusal_with_other_request_id_is_a_contract_violation(env):
    err = blocked(env, "emit({'status': 'BLOCKED', 'reason': 'X', 'request_id': 'other'}, 3)")
    assert err.reason == "AEVE_CONTRACT_VIOLATION" and not isinstance(err, adapter.AeveRefused)


@pytest.mark.parametrize("flags", ["'llm_calls': 2", "'executed_project_code': True", "'source_modified': True"])
def test_refusal_reporting_model_or_execution_is_a_contract_violation(env, flags):
    err = blocked(env, f"emit({{'status': 'BLOCKED', 'reason': 'X', {flags}}}, 3)")
    assert err.reason == "AEVE_CONTRACT_VIOLATION" and not isinstance(err, adapter.AeveRefused)


@pytest.mark.parametrize("reason", ["lower_case", "", "A" * 65, 5, None, "BAD REASON", "REASON\nINJECT"])
def test_refusal_reason_must_be_a_well_formed_code(env, reason):
    err = blocked(env, f"emit({{'status': 'BLOCKED', 'reason': {reason!r}}}, 3)")
    assert err.reason == "AEVE_CONTRACT_VIOLATION" and not isinstance(err, adapter.AeveRefused)


def test_complete_status_without_head_is_not_treated_as_a_refusal(env):
    err = blocked(env, "d = good(); d.pop('head'); emit(d)")
    assert err.reason == "AEVE_CONTRACT_VIOLATION" and "head" in err.detail


def test_blocked_status_with_head_goes_through_full_checks(env):
    """A response that carries a head is a review response; wrong head must be HEAD_MOVED, not a refusal."""
    err = blocked(env, "emit(good(status='BLOCKED', head='e' * 40), 3)")
    assert err.reason == "HEAD_MOVED"


# ------------------------------------------------------------------ hostile reviewed root and default argv
FAKE_AEVE_MAIN = """\
import json, os, sys
req = json.load(open(sys.argv[-1], encoding='utf-8'))
import json as _j
report = {'json_file': _j.__file__, 'cwd': os.getcwd(), 'no_user_site': sys.flags.no_user_site,
          'dont_write_bytecode': sys.flags.dont_write_bytecode, 'safe_path': getattr(sys.flags, 'safe_path', None),
          'argv': sys.argv[1:], 'pythonpath': os.environ.get('PYTHONPATH')}
open(@@REPORT@@, 'w').write(json.dumps(report))
ids = req['executor_ids']
print(json.dumps({'status': 'COMPLETE', 'request_id': req['request_id'], 'head': req['base_revision'],
  'snapshot_sha256': 'b' * 64, 'iteration_id': 'it', 'executor_ids': ids, 'results': [], 'findings': [],
  'uncovered': [], 'llm_calls': 0, 'executed_project_code': False, 'source_modified': False, 'dirty': False}))
"""


def test_default_command_uses_isolation_flags_and_hostile_root_is_not_imported(env):
    """Default argv is `python -P -s -B -m aeve review ...` with PYTHONPATH=<aeve>/src. The reviewed root contains
    json.py and an aeve/ package that kill the process on import; neither may be imported by the child."""
    hostile = env["root"]
    (hostile / "json.py").write_text("import os\nos._exit(77)\n")
    (hostile / "aeve").mkdir()
    (hostile / "aeve" / "__init__.py").write_text("import os\nos._exit(78)\n")
    (hostile / "aeve" / "__main__.py").write_text("import os\nos._exit(79)\n")
    report = env["tmp"] / "report.json"
    pkg = env["aeve"] / "src" / "aeve"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "__main__.py").write_text(FAKE_AEVE_MAIN.replace("@@REPORT@@", repr(str(report))))
    # the process cwd is the hostile root, as it would be for a caller sitting inside the reviewed repository
    old = os.getcwd()
    os.chdir(hostile)
    try:
        resp = adapter.run_review(make_request(env), aeve_root=env["aeve"], state_dir=env["state"])
    finally:
        os.chdir(old)
    assert resp["status"] == "COMPLETE"
    seen = json.loads(report.read_text())
    assert str(hostile) not in seen["json_file"], seen
    assert pathlib.Path(seen["cwd"]).resolve() != hostile.resolve() and hostile.resolve() not in pathlib.Path(seen["cwd"]).resolve().parents
    assert seen["no_user_site"] == 1 and seen["dont_write_bytecode"] == 1
    if seen["safe_path"] is not None:
        assert seen["safe_path"] is True or seen["safe_path"] == 1
    assert seen["argv"][0] == "review" and seen["argv"][1] == "--request"
    assert seen["pythonpath"] == str(env["aeve"].resolve() / "src")


def test_stub_child_is_not_run_from_the_reviewed_root(env):
    """Even for custom prefixes the child cwd is a private dir outside the reviewed root (planted json.py is inert)."""
    (env["root"] / "json.py").write_text("raise SystemExit(77)\n")
    body = "import json as j, sysconfig; emit(good(uncovered=['stdlib' if os.path.normcase(j.__file__).startswith(os.path.normcase(sysconfig.get_paths()['stdlib'])) else 'planted']))"
    old = os.getcwd()
    os.chdir(env["root"])
    try:
        resp = run(env, body)
    finally:
        os.chdir(old)
    assert resp["uncovered"] == ["stdlib"]


def test_state_dir_is_created(env):
    assert not env["state"].exists()
    run(env, "emit(good())")
    assert env["state"].is_dir()


def test_check_response_is_pure_and_rejects_non_dict():
    with pytest.raises(adapter.AdapterBlocked) as info:
        adapter.check_response([1], {"request_id": "r1", "base_revision": HEAD}, 0)
    assert info.value.reason == "BAD_OUTPUT"
