"""LINK-2 T3a: generic AEVE runner (`adapter.run_aeve_command`) and `aeve_probe.checkout_is_clean`, AC-8 to AC-11.

Per-command accepted exit codes (design T3a): review (0, 3), packet (0, 3), verify-handoff (0, 1, 2, 3); any other exit
is AEVE_EXIT. A stub interpreter command stands in for AEVE; the checkout for AC-11 is a real tiny git repository.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from uc import adapter, aeve_probe

from tests.uc import ucsupport as S

EXIT_STUB = [sys.executable, "-s", "-B", "-c",
             "import sys; sys.stdout.write('{\"ok\": true}'); sys.exit(int(sys.argv[-1]))"]


@pytest.fixture()
def dirs(tmp_path):
    aeve = tmp_path / "aeve"
    (aeve / "src").mkdir(parents=True)
    return aeve, tmp_path / "state"


def run(dirs, command, code, **kw):
    aeve, state = dirs
    return adapter.run_aeve_command(command, [str(code)], aeve_root=aeve, state_dir=state, command_prefix=EXIT_STUB, **kw)


@pytest.mark.parametrize("command,accepted", [("review", (0, 3)), ("packet", (0, 3)), ("verify-handoff", (0, 1, 2, 3))])
def test_exit_table_per_command(dirs, command, accepted):  # AC-10
    for code in range(0, 6):
        if code in accepted:
            assert run(dirs, command, code) == (code, b'{"ok": true}')
        else:
            with pytest.raises(adapter.AdapterBlocked) as info:
                run(dirs, command, code)
            assert info.value.reason == "AEVE_EXIT"


def test_unknown_command_without_explicit_codes_is_refused_and_explicit_codes_win(dirs):
    with pytest.raises(adapter.AdapterBlocked) as info:
        run(dirs, "bogus", 0)
    assert info.value.reason == "UNKNOWN_COMMAND"
    assert run(dirs, "bogus", 4, ok_exit_codes=(4,))[0] == 4


def test_argv_is_prefix_command_then_args(dirs, tmp_path):
    out = tmp_path / "argv.json"
    prefix = [sys.executable, "-s", "-B", "-c",
              f"import json,sys; open({str(out)!r},'w').write(json.dumps(sys.argv[1:]))"]
    adapter.run_aeve_command("packet", ["--request", "X"], aeve_root=dirs[0], state_dir=dirs[1], command_prefix=prefix)
    assert json.loads(out.read_text()) == ["packet", "--request", "X"]


def test_run_review_still_uses_review_argv_and_exit_0_and_3(dirs, tmp_path):  # AC-8
    capture = tmp_path / "cap.json"
    body = f"""
    import pathlib
    pathlib.Path({str(capture)!r}).write_text(json.dumps({{'argv': sys.argv[1:-1]}}))
    emit(good(), 0)
    """
    prefix = S.write_stub(tmp_path / "stubs", body)
    request = adapter.build_aeve_request(request_id="r1", root=str(tmp_path), base_revision=S.HEAD,
                                         changed_paths=["a.py"], executor_ids=["g2.python-rules"])
    adapter.run_review(request, aeve_root=dirs[0], state_dir=dirs[1], command_prefix=prefix)
    assert json.loads(capture.read_text())["argv"][-2:] == ["review", "--request"]
    for code in (1, 2, 4):
        prefix = S.write_stub(tmp_path / f"s{code}", "emit(good(), %d)" % code)
        with pytest.raises(adapter.AdapterBlocked) as info:
            adapter.run_review(request, aeve_root=dirs[0], state_dir=dirs[1], command_prefix=prefix)
        assert info.value.reason == "AEVE_EXIT"


def test_run_review_bad_output_and_timeout_and_cap_unchanged(dirs, tmp_path):  # AC-9
    request = adapter.build_aeve_request(request_id="r1", root=str(tmp_path), base_revision=S.HEAD, changed_paths=["a"])
    cases = [("sys.stdout.write('nope'); sys.exit(0)", "BAD_OUTPUT"),
             ("sys.stdout.write('x' * 5000); sys.exit(0)", "OUTPUT_TOO_LARGE"),
             ("time.sleep(30)", "TIMEOUT")]
    for index, (body, reason) in enumerate(cases):
        prefix = S.write_stub(tmp_path / f"c{index}", body)
        with pytest.raises(adapter.AdapterBlocked) as info:
            adapter.run_review(request, aeve_root=dirs[0], state_dir=dirs[1], command_prefix=prefix,
                               timeout=1.5, stdout_cap=1000)
        assert info.value.reason == reason
        if reason == "TIMEOUT":
            assert info.value.tree_dead is True


# ---- AC-11
def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                    *args], check=True, capture_output=True, timeout=60)


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "a.txt").write_text("a\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True, timeout=60)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "i")
    return root


def test_checkout_is_clean_true_for_empty_status(repo):
    assert aeve_probe.checkout_is_clean(repo) is True


def test_checkout_is_clean_false_for_one_untracked_file(repo):
    (repo / "new.txt").write_text("x")
    assert aeve_probe.checkout_is_clean(repo) is False


def test_checkout_is_clean_false_for_one_tracked_change(repo):
    (repo / "a.txt").write_text("changed\n")
    assert aeve_probe.checkout_is_clean(repo) is False


def test_checkout_is_clean_raises_when_git_cannot_answer(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(aeve_probe.AeveProbeError):
        aeve_probe.checkout_is_clean(plain)
