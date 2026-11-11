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

    def change(root):
        (root / "a.txt").write_bytes(b"changed")
        (root / "stray.txt").write_bytes(b"x")

    def rollback(root):
        (root / "a.txt").write_bytes(b"alpha")  # stray.txt stays

    result = rx.exercise_rollback(tmp_path, change, rollback)

    assert result.rollback_proven is False
    assert result.error_code == rx.ROLLBACK_INCOMPLETE
    assert result.snapshot_before == before
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
    result = rx.exercise_rollback(tmp_path, None, lambda root: None)
    assert result.rollback_proven is False
    assert result.error_code == rx.BAD_CALLABLE
    result = rx.exercise_rollback(tmp_path, lambda root: None, "not callable")
    assert result.rollback_proven is False
    assert result.error_code == rx.BAD_CALLABLE


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
