"""S2 E6: deterministic diff gate rejects unsafe worker changes."""

import pytest

from tools.vst import diffgate
from tools.vst.contracts import ContractError


MANIFEST = "a" * 64
BASE = "b" * 40
HEAD = "c" * 40


def check(paths, *, allowed=("src/app.py",), renames=(), symlinks=()):
    return diffgate.check_diff(
        manifest_sha256=MANIFEST, base_head=BASE, candidate_head=HEAD,
        changed_paths=paths, allowed_paths=allowed, diff_bytes=b"stable diff",
        rename_pairs=renames, symlink_paths=symlinks,
    )


def test_allowed_change_passes_with_stable_digest_and_normalized_order():
    first = check(["src\\app.py", "src/app.py"])
    second = check(["src/app.py"])
    assert first == second
    assert first["verdict"] == "PASS"
    assert first["changed_paths"] == ["src/app.py"]
    import hashlib
    assert first["diff_sha256"] == hashlib.sha256(b"stable diff").hexdigest()


@pytest.mark.parametrize("path", [
    ".github/workflows/ci.yml", ".husky/pre-commit", "hooks/pre-commit",
    "package-lock.json", "vendor.lock", "setup.py", "install.ps1",
])
def test_blocked_file_classes_fail_when_manifest_does_not_list_them(path):
    result = check(["src/app.py", path])
    assert result["verdict"] == "FAIL"
    assert result["reason"] == "BLOCKED_PATH_CLASS"


def test_explicitly_scoped_blocked_class_is_permitted_by_manifest():
    result = check([".github/workflows/ci.yml"], allowed=(".github/workflows/ci.yml",))
    assert result["verdict"] == "PASS"


@pytest.mark.parametrize("path", ["../secret", "src//app.py", "/etc/passwd", "C:/outside"])
def test_escaping_or_ambiguous_paths_are_rejected(path):
    with pytest.raises(ContractError):
        check([path])


def test_path_outside_manifest_scope_fails():
    result = check(["src/app.py", "docs/other.md"])
    assert result["verdict"] == "FAIL"
    assert result["reason"] == "OUT_OF_SCOPE_PATH"


def test_rename_from_allowed_file_into_blocked_hook_fails():
    result = check([".husky/pre-commit"], renames=(("src/app.py", ".husky/pre-commit"),))
    assert result["verdict"] == "FAIL"
    assert result["reason"] == "RENAME_INTO_BLOCKED_PATH"


def test_symlink_change_fails_even_when_target_path_is_allowed():
    result = check(["src/app.py"], symlinks=["src/app.py"])
    assert result["verdict"] == "FAIL"
    assert result["reason"] == "SYMLINK_CHANGE"


def test_diff_evidence_is_bound_to_manifest_and_candidate_head():
    result = check(["src/app.py"])
    assert result["manifest_sha256"] == MANIFEST
    assert result["candidate_head"] == HEAD
    assert result["diff_sha256"] != "0" * 64
