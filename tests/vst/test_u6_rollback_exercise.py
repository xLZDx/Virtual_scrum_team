"""U6-1: rollback exercise helper.

Acceptance text: "The rollback is exercised and the pre-change snapshot hash equals the post-rollback hash."

Expected values come from an independent formula restated in this file with `hashlib` and `pathlib`
(`expected_hash`): SHA-256 over the files sorted by relative POSIX path, each as
`<path UTF-8> 0x00 <decimal length> 0x00 <bytes>`, every entry named `.git` skipped. The helper is never used to
produce an expected value. Tests are written, NOT_RUN (operator ban).
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
from pathlib import Path

import pytest

from tools.vst import rollback_exercise as rx


def expected_hash(root: Path, *, include_git: bool = False) -> str:
    items = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if not include_git and ".git" in relative.split("/"):
            continue
        items.append((relative, path.read_bytes()))
    digest = hashlib.sha256()
    for relative, data in sorted(items, key=lambda item: item[0]):
        digest.update(relative.encode("utf-8") + b"\x00" + str(len(data)).encode("ascii") + b"\x00" + data)
    return digest.hexdigest()


def make_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "a.txt").write_bytes(b"alpha")
    (root / "a").mkdir(exist_ok=True)
    (root / "a" / "b.txt").write_bytes(b"bravo\r\nline2\n")
    (root / "sub" / "deeper").mkdir(parents=True, exist_ok=True)
    (root / "sub" / "deeper" / "c.bin").write_bytes(b"\x00\x01\x02")


def test_literal_single_file_formula(tmp_path):
    (tmp_path / "x.txt").write_bytes(b"hi")
    # sha256 of b"x.txt\x00" + b"2\x00" + b"hi", restated here by hand
    literal = hashlib.sha256(b"x.txt\x002\x00hi").hexdigest()
    assert rx.snapshot_hash(tmp_path) == literal
    assert expected_hash(tmp_path) == literal


def test_proven_rollback(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    seen = {}

    def change(root):
        (root / "a.txt").write_bytes(b"ALPHA CHANGED")
        (root / "new.txt").write_bytes(b"new")
        seen["after_change"] = expected_hash(root)

    def rollback(root):
        (root / "a.txt").write_bytes(b"alpha")
        (root / "new.txt").unlink()

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is True
    assert result.error_code is None
    assert result.snapshot_before == before
    assert result.snapshot_after_change == seen["after_change"]
    assert result.snapshot_after_change != before
    assert result.snapshot_after_rollback == before
    assert expected_hash(tmp_path) == before


def test_rollback_leaving_a_stray_file_is_not_proven(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    seen = {}

    def change(root):
        (root / "a.txt").write_bytes(b"changed")
        (root / "stray.txt").write_bytes(b"x")
        seen["after_change"] = expected_hash(root)

    def rollback(root):
        (root / "a.txt").write_bytes(b"alpha")  # stray.txt stays

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is False
    assert result.error_code == rx.ROLLBACK_INCOMPLETE
    assert result.snapshot_before == before
    assert result.snapshot_after_change == seen["after_change"]
    assert result.snapshot_after_rollback == expected_hash(tmp_path)
    assert result.snapshot_after_rollback != before


def test_change_that_changes_nothing_is_not_proven(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    calls = []

    def change(root):
        (root / "a.txt").write_bytes(b"alpha")  # same bytes as before

    def rollback(root):
        calls.append("rollback")

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is False
    assert result.error_code == rx.CHANGE_NO_EFFECT
    assert result.snapshot_before == before
    assert result.snapshot_after_change == before
    assert result.snapshot_after_rollback is None
    assert calls == []


def test_change_raising_is_a_result_not_an_exception(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    calls = []

    def change(root):
        raise RuntimeError("secret-looking message")

    def rollback(root):
        calls.append("rollback")

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is False
    assert result.error_code == rx.CHANGE_FAILED
    assert result.snapshot_before == before
    assert result.snapshot_after_change is None
    assert result.snapshot_after_rollback is None
    assert "RuntimeError" in result.error_detail
    assert "secret-looking" not in result.error_detail  # only the type name is echoed
    assert calls == []


def test_rollback_raising_is_a_result_not_an_exception(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)

    def change(root):
        (root / "a.txt").write_bytes(b"changed")

    def rollback(root):
        raise OSError("disk gone")

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is False
    assert result.error_code == rx.ROLLBACK_FAILED
    assert result.snapshot_before == before
    assert result.snapshot_after_change == expected_hash(tmp_path)  # the tree is still changed
    assert result.snapshot_after_change != before
    assert result.snapshot_after_rollback is None
    assert "OSError" in result.error_detail
    assert "disk gone" not in result.error_detail


def test_non_directory_root_is_refused_without_calling_anything(tmp_path):
    a_file = tmp_path / "file.txt"
    a_file.write_bytes(b"x")
    calls = []

    def change(root):
        calls.append("change")

    def rollback(root):
        calls.append("rollback")

    for bad in (a_file, tmp_path / "missing"):
        result = rx.exercise_rollback(bad, change, rollback)
        assert result.rollback_proven is False
        assert result.error_code == rx.ROOT_NOT_DIRECTORY
        assert result.snapshot_before is None
        assert result.snapshot_after_change is None
        assert result.snapshot_after_rollback is None
    assert calls == []
    assert a_file.read_bytes() == b"x"


def test_non_callable_arguments_are_refused(tmp_path):
    make_tree(tmp_path)
    for change, rollback in ((None, lambda root: None), (lambda root: None, "not callable")):
        result = rx.exercise_rollback(tmp_path, change, rollback)
        assert result.rollback_proven is False
        assert result.error_code == rx.BAD_CALLABLE
        assert result.snapshot_before is None
        assert result.snapshot_after_change is None
        assert result.snapshot_after_rollback is None


def test_coroutine_functions_are_refused(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)

    async def coroutine(root):
        (root / "never.txt").write_bytes(b"x")

    for change, rollback in ((coroutine, lambda root: None), (lambda root: None, coroutine)):
        result = rx.exercise_rollback(tmp_path, change, rollback)
        assert result.rollback_proven is False
        assert result.error_code == rx.BAD_CALLABLE
        assert result.snapshot_before is None
    assert expected_hash(tmp_path) == before


def test_bad_callable_with_bad_root_reports_the_root(tmp_path):
    result = rx.exercise_rollback(tmp_path / "missing", None, None)
    assert result.rollback_proven is False
    assert result.error_code == rx.ROOT_NOT_DIRECTORY


def test_root_that_is_not_a_path_is_refused():
    for bad in (None, 123):
        result = rx.exercise_rollback(bad, lambda root: None, lambda root: None)
        assert result.rollback_proven is False
        assert result.error_code == rx.ROOT_NOT_DIRECTORY


def test_str_root_is_accepted_and_callables_get_a_path(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    received = []

    def change(root):
        received.append(root)
        (root / "n.txt").write_bytes(b"1")

    def rollback(root):
        received.append(root)
        (root / "n.txt").unlink()

    result = rx.exercise_rollback(str(tmp_path), change, rollback)

    assert result.rollback_proven is True
    assert result.snapshot_before == before
    assert len(received) == 2
    assert all(isinstance(item, pathlib.Path) for item in received)
    assert all(item == tmp_path for item in received)


def test_git_directory_is_excluded(tmp_path):
    make_tree(tmp_path)
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (tmp_path / "sub" / ".git").write_bytes(b"gitdir: elsewhere\n")  # a .git file at depth is excluded too

    assert rx.snapshot_hash(tmp_path) == expected_hash(tmp_path)
    assert rx.snapshot_hash(tmp_path) != expected_hash(tmp_path, include_git=True)

    # a change that only touches .git changes nothing the snapshot sees
    def change(root):
        (root / ".git" / "HEAD").write_bytes(b"ref: refs/heads/other\n")
        (root / ".git" / "extra").write_bytes(b"x")

    result = rx.exercise_rollback(tmp_path, change, lambda root: None)
    assert result.rollback_proven is False
    assert result.error_code == rx.CHANGE_NO_EFFECT
    assert result.snapshot_before == result.snapshot_after_change == expected_hash(tmp_path)


def test_hash_does_not_depend_on_creation_order(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    files = {"a.txt": b"1", "a/b.txt": b"2", "z/y/x.txt": b"3", "m.txt": b"4"}
    for name in ("a.txt", "a/b.txt", "m.txt", "z/y/x.txt"):
        target = first / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[name])
    for name in ("z/y/x.txt", "m.txt", "a/b.txt", "a.txt"):
        target = second / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[name])

    digest = hashlib.sha256()
    for name in sorted(files):  # plain string order: "a.txt" < "a/b.txt" < "m.txt" < "z/y/x.txt"
        digest.update(name.encode("utf-8") + b"\x00" + b"1" + b"\x00" + files[name])
    literal = digest.hexdigest()

    assert rx.snapshot_hash(first) == rx.snapshot_hash(second) == literal


def test_hash_sees_content_and_path_changes(tmp_path):
    make_tree(tmp_path)
    base = rx.snapshot_hash(tmp_path)
    (tmp_path / "a.txt").write_bytes(b"alphb")
    assert rx.snapshot_hash(tmp_path) != base
    (tmp_path / "a.txt").write_bytes(b"alpha")
    assert rx.snapshot_hash(tmp_path) == base
    (tmp_path / "a.txt").rename(tmp_path / "renamed.txt")
    assert rx.snapshot_hash(tmp_path) != base


def test_result_is_frozen_and_guarded(tmp_path):
    make_tree(tmp_path)
    result = rx.exercise_rollback(tmp_path, lambda root: (root / "n").write_bytes(b"1"),
                                  lambda root: (root / "n").unlink())
    assert result.rollback_proven is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.rollback_proven = False
    # a result cannot claim a proof its snapshots do not support
    with pytest.raises(ValueError):
        rx.RollbackExerciseResult("a" * 64, "b" * 64, "c" * 64, True)
    with pytest.raises(ValueError):
        rx.RollbackExerciseResult(None, None, None, False)
    assert result.to_dict()["rollback_proven"] is True


def test_result_invariants_and_dict_keys():
    a, b = "a" * 64, "b" * 64
    ok = rx.RollbackExerciseResult(a, b, a, True)
    assert ok.to_dict() == {"snapshot_before": a, "snapshot_after_change": b, "snapshot_after_rollback": a,
                            "rollback_proven": True, "error_code": None, "error_detail": None}
    bad_cases = [
        ("XYZ", None, None, False, "E"),       # not hex
        (a.upper(), None, None, False, "E"),   # uppercase hex
        ("a" * 63, None, None, False, "E"),    # wrong length
        (a, a, a, True),                       # proven with after_change == before
        (a, b, a, True, "SOME_CODE"),          # proven with an error code
        (a, b, b, True),                       # proven with before != after_rollback
        (None, b, a, True),                    # proven without a snapshot
        (a, b, a, 1),                          # non-bool proven
        (None, None, None, False),             # not proven without an error code
    ]
    for args in bad_cases:
        with pytest.raises(ValueError):
            rx.RollbackExerciseResult(*args)


def test_nested_git_excluded_and_lookalikes_hashed(tmp_path):
    make_tree(tmp_path)
    (tmp_path / "sub" / ".git").mkdir()
    (tmp_path / "sub" / ".git" / "x").write_bytes(b"inside nested git")
    (tmp_path / ".gitignore").write_bytes(b"*.pyc\n")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "x").write_bytes(b"workflow")
    (tmp_path / "x.git").write_bytes(b"lookalike")
    base = rx.snapshot_hash(tmp_path)
    assert base == expected_hash(tmp_path)
    assert base != expected_hash(tmp_path, include_git=True)

    (tmp_path / "sub" / ".git" / "x").write_bytes(b"edited")
    assert rx.snapshot_hash(tmp_path) == base  # excluded
    for lookalike in (".gitignore", ".github/x", "x.git"):
        target = tmp_path / lookalike
        original = target.read_bytes()
        target.write_bytes(original + b"!")
        assert rx.snapshot_hash(tmp_path) != base, lookalike  # hashed
        target.write_bytes(original)
    assert rx.snapshot_hash(tmp_path) == base


def test_empty_directory_rules(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)

    # a change that only creates an empty directory changes nothing the hash sees
    result = rx.exercise_rollback(tmp_path, lambda root: (root / "empty").mkdir(), lambda root: None)
    assert result.rollback_proven is False
    assert result.error_code == rx.CHANGE_NO_EFFECT
    assert result.snapshot_before == result.snapshot_after_change == before

    # a rollback that leaves an empty directory behind is still proven
    def change(root):
        (root / "newdir").mkdir()
        (root / "newdir" / "f.txt").write_bytes(b"f")

    def rollback(root):
        (root / "newdir" / "f.txt").unlink()  # newdir stays, empty

    result = rx.exercise_rollback(tmp_path, change, rollback)
    assert result.rollback_proven is True
    assert result.snapshot_before == result.snapshot_after_rollback == before
    assert (tmp_path / "newdir").is_dir()


def test_change_that_mutates_then_raises_leaves_tree_changed(tmp_path):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    calls = []

    def change(root):
        (root / "a.txt").write_bytes(b"half done")
        raise RuntimeError("late failure")

    result = rx.exercise_rollback(tmp_path, change, lambda root: calls.append("rollback"))

    assert result.rollback_proven is False
    assert result.error_code == rx.CHANGE_FAILED
    assert result.snapshot_before == before
    assert result.snapshot_after_change is None
    assert result.snapshot_after_rollback is None
    assert calls == []
    assert expected_hash(tmp_path) != before  # the tree is left changed, as documented


def _fail_read_of(monkeypatch, name):
    original = pathlib.Path.read_bytes

    def failing(self):
        if self.name == name:
            raise PermissionError("locked by another process")
        return original(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", failing)


def test_snapshot_failure_before_the_change(tmp_path, monkeypatch):
    make_tree(tmp_path)
    calls = []
    _fail_read_of(monkeypatch, "a.txt")

    result = rx.exercise_rollback(tmp_path, lambda root: calls.append("change"), lambda root: calls.append("rollback"))

    assert result.rollback_proven is False
    assert result.error_code == rx.SNAPSHOT_FAILED
    assert result.snapshot_before is None
    assert result.snapshot_after_change is None
    assert result.snapshot_after_rollback is None
    assert "PermissionError" in result.error_detail
    assert "locked by another" not in result.error_detail
    assert calls == []


def test_snapshot_failure_after_the_change_skips_the_rollback(tmp_path, monkeypatch):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    calls = []

    def change(root):
        (root / "a" / "b.txt").write_bytes(b"changed")
        _fail_read_of(monkeypatch, "a.txt")

    result = rx.exercise_rollback(tmp_path, change, lambda root: calls.append("rollback"))

    assert result.rollback_proven is False
    assert result.error_code == rx.SNAPSHOT_FAILED
    assert result.snapshot_before == before
    assert result.snapshot_after_change is None
    assert result.snapshot_after_rollback is None
    assert calls == []
    monkeypatch.undo()
    assert (tmp_path / "a" / "b.txt").read_bytes() == b"changed"  # the tree is left changed


def test_snapshot_failure_after_the_rollback(tmp_path, monkeypatch):
    make_tree(tmp_path)
    before = expected_hash(tmp_path)
    seen = {}

    def change(root):
        (root / "a" / "b.txt").write_bytes(b"changed")
        seen["after_change"] = expected_hash(root)

    def rollback(root):
        (root / "a" / "b.txt").write_bytes(b"bravo\r\nline2\n")
        _fail_read_of(monkeypatch, "a.txt")

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is False
    assert result.error_code == rx.SNAPSHOT_FAILED
    assert result.snapshot_before == before
    assert result.snapshot_after_change == seen["after_change"]
    assert result.snapshot_after_rollback is None


def test_unlistable_directory_fails_the_snapshot(tmp_path, monkeypatch):
    make_tree(tmp_path)
    seen = {}

    def fake_walk(top, topdown=True, onerror=None, followlinks=False):
        seen["onerror"] = onerror
        if onerror is not None:
            onerror(PermissionError("cannot list"))  # what os.walk does when scandir fails
        return iter(())

    monkeypatch.setattr(os, "walk", fake_walk)

    with pytest.raises(ValueError):
        rx.snapshot_hash(tmp_path)
    assert seen["onerror"] is not None  # the helper must not let os.walk swallow listing errors

    calls = []
    result = rx.exercise_rollback(tmp_path, lambda root: calls.append("change"), lambda root: None)
    assert result.rollback_proven is False
    assert result.error_code == rx.SNAPSHOT_FAILED
    assert result.snapshot_before is None
    assert calls == []


def test_reparse_point_is_refused_for_root_directory_and_file(tmp_path, monkeypatch):
    make_tree(tmp_path)
    real = rx._is_reparse_or_link

    for flagged in (tmp_path.name, "sub", "a.txt"):  # the root, a directory, a file
        def fake(path, flagged=flagged):
            return path.name == flagged or real(path)

        monkeypatch.setattr(rx, "_is_reparse_or_link", fake)
        with pytest.raises(ValueError):
            rx.snapshot_hash(tmp_path)
        calls = []
        result = rx.exercise_rollback(tmp_path, lambda root: calls.append("change"), lambda root: None)
        assert result.rollback_proven is False, flagged
        assert result.error_code == rx.SNAPSHOT_FAILED, flagged
        assert result.snapshot_before is None, flagged
        assert calls == [], flagged

    monkeypatch.setattr(rx, "_is_reparse_or_link", real)
    assert rx.snapshot_hash(tmp_path) == expected_hash(tmp_path)  # a real tree without links is accepted


def test_reparse_attribute_is_detected(tmp_path, monkeypatch):
    (tmp_path / "f.txt").write_bytes(b"x")
    real_lstat = os.lstat

    class FakeStat:
        st_mode = 0o100644
        st_file_attributes = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT

    def fake_lstat(path, *args, **kwargs):
        if os.fspath(path).endswith("f.txt"):
            return FakeStat()
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", fake_lstat)
    assert rx._is_reparse_or_link(tmp_path / "f.txt") is True
    with pytest.raises(ValueError):
        rx.snapshot_hash(tmp_path)


def test_real_symlinks_are_refused(tmp_path):
    tree = tmp_path / "tree"
    make_tree(tree)
    outside = tmp_path / "outside"
    make_tree(outside)
    try:
        os.symlink(outside / "a.txt", tree / "link.txt")
        os.symlink(outside, tree / "dirlink", target_is_directory=True)
        os.symlink(tree, tmp_path / "rootlink", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here (Windows WinError 1314 without privilege)")

    with pytest.raises(ValueError):
        rx.snapshot_hash(tree)
    result = rx.exercise_rollback(tree, lambda root: None, lambda root: None)
    assert result.error_code == rx.SNAPSHOT_FAILED
    assert result.rollback_proven is False

    (tree / "link.txt").unlink()
    (tree / "dirlink").unlink()
    assert rx.snapshot_hash(tree) == expected_hash(tree)  # clean again
    root_result = rx.exercise_rollback(tmp_path / "rootlink", lambda root: None, lambda root: None)
    assert root_result.error_code == rx.SNAPSHOT_FAILED  # a linked root passes is_dir but is refused
    assert root_result.rollback_proven is False
