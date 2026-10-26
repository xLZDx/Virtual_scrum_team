"""S2 E6: deterministic diff gate rejects unsafe worker changes."""

import hashlib
import subprocess

import pytest

from tools.vst import diffgate, runner, signing
from tools.vst.contracts import ContractError, TRUSTED_PARSER_CATALOG
from tests.vst.e1e4_helpers import manifest as base_manifest


MANIFEST = "a" * 64
BASE = "b" * 40
HEAD = "c" * 40
RUNNER_KEY = b"s2-diff-evidence-runner-key-0123456789"


def check(paths, *, allowed=("src/app.py",), renames=(), symlinks=()):
    return diffgate.check_diff(
        manifest_sha256=MANIFEST, base_head=BASE, candidate_head=HEAD,
        changed_paths=paths, allowed_paths=allowed, diff_bytes=b"stable diff",
        rename_pairs=renames, symlink_paths=symlinks,
    )


def _init_git_candidate(path, *, ignored_patterns=()):
    path.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(path), *args], check=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        ).stdout.strip()

    git("init")
    git("config", "user.name", "Synthetic DiffGate")
    git("config", "user.email", "diffgate@example.invalid")
    if ignored_patterns:
        (path / ".gitignore").write_text(
            "".join(f"{pattern}\n" for pattern in ignored_patterns), encoding="utf-8",
        )
    (path / "tracked.txt").write_bytes(b"committed baseline\n")
    git("add", "--", "tracked.txt", *([".gitignore"] if ignored_patterns else []))
    git("commit", "-m", "synthetic baseline")
    return git("rev-parse", "--verify", "HEAD")


def _v2_diff_manifest(base_head, allowed_paths):
    parser_id, parser_version, parser_sha256 = next(iter(TRUSTED_PARSER_CATALOG))
    manifest = base_manifest()
    manifest.update({
        "base_head": base_head,
        "contract_version": 2,
        "reviewer_registry": {"version": "registry-1", "sha256": "d" * 64},
        "mandatory_commands": [{
            "slot": "tests", "argv": ["pytest", "-q"],
            "parser_id": parser_id, "parser_version": parser_version,
            "parser_sha256": parser_sha256,
        }],
        "change_scope": {"allowed_paths": list(allowed_paths)},
    })
    return manifest


def _signed_runner_diff(repo, base_head, allowed_paths):
    diff_bytes, changed_paths, rename_pairs, symlink_paths = runner._diff_paths(
        str(repo), base_head,
    )
    manifest = _v2_diff_manifest(base_head, allowed_paths)
    evidence = diffgate.git_diff_evidence(
        str(repo), manifest, runner._derive_head(str(repo)), diff_bytes, changed_paths,
        symlink_paths=symlink_paths, rename_pairs=rename_pairs,
    )
    signed = diffgate.sign_diff_evidence(evidence, RUNNER_KEY)
    assert signing.verify(signed, RUNNER_KEY, diffgate.DIFF_GATE_LABEL)
    assert signed["diff_sha256"] == hashlib.sha256(diff_bytes).hexdigest()
    return diff_bytes, signed


def test_runner_untracked_out_of_scope_file_is_in_signed_fail_evidence(tmp_path):
    base_head = _init_git_candidate(tmp_path / "candidate")
    outside = "docs/outside.md"
    (tmp_path / "candidate" / outside).parent.mkdir()
    (tmp_path / "candidate" / outside).write_bytes(b"out of scope\n")

    _diff_bytes, signed = _signed_runner_diff(
        tmp_path / "candidate", base_head, ["src/app.py"],
    )

    assert signed["verdict"] == "FAIL"
    assert signed["reason"] == "OUT_OF_SCOPE_PATH"
    assert signed["changed_paths"] == [outside]


def test_runner_untracked_blocked_file_is_in_signed_fail_evidence(tmp_path):
    base_head = _init_git_candidate(tmp_path / "candidate")
    blocked = "install.ps1"
    (tmp_path / "candidate" / blocked).write_bytes(b"synthetic installer\n")

    _diff_bytes, signed = _signed_runner_diff(
        tmp_path / "candidate", base_head, ["src/app.py"],
    )

    assert signed["verdict"] == "FAIL"
    assert signed["reason"] == "BLOCKED_PATH_CLASS"
    assert signed["changed_paths"] == [blocked]


def test_runner_allowed_untracked_file_content_is_bound_to_signed_digest(tmp_path):
    base_head = _init_git_candidate(tmp_path / "candidate")
    path = "src/app.txt"
    candidate_file = tmp_path / "candidate" / path
    candidate_file.parent.mkdir()
    candidate_file.write_bytes(b"first candidate bytes\n")

    first_diff, first_signed = _signed_runner_diff(
        tmp_path / "candidate", base_head, [path],
    )
    assert first_signed["verdict"] == "PASS"
    assert first_signed["changed_paths"] == [path]
    assert b"first candidate bytes\n" in first_diff

    candidate_file.write_bytes(b"different candidate bytes\n")
    second_diff, second_signed = _signed_runner_diff(
        tmp_path / "candidate", base_head, [path],
    )
    assert b"different candidate bytes\n" in second_diff
    assert first_signed["diff_sha256"] != second_signed["diff_sha256"]


def test_runner_includes_ignored_and_ordinary_untracked_files_in_scope_evidence(tmp_path):
    base_head = _init_git_candidate(tmp_path / "candidate", ignored_patterns=("ignored/",))
    ignored_path = "ignored/allowed.txt"
    ordinary_path = "src/ordinary.txt"
    ignored_file = tmp_path / "candidate" / ignored_path
    ordinary_file = tmp_path / "candidate" / ordinary_path
    ignored_file.parent.mkdir()
    ordinary_file.parent.mkdir()
    ignored_file.write_bytes(b"ignored bytes\n")
    ordinary_file.write_bytes(b"ordinary bytes\n")

    diff_bytes, signed = _signed_runner_diff(
        tmp_path / "candidate", base_head, [ignored_path, ordinary_path],
    )

    assert signed["verdict"] == "PASS"
    assert signed["changed_paths"] == sorted([ignored_path, ordinary_path])
    assert b"ignored bytes\n" in diff_bytes
    assert b"ordinary bytes\n" in diff_bytes


def test_runner_ignored_untracked_file_still_counts_against_manifest_scope(tmp_path):
    base_head = _init_git_candidate(tmp_path / "candidate", ignored_patterns=("ignored/",))
    ignored_path = "ignored/outside.txt"
    ignored_file = tmp_path / "candidate" / ignored_path
    ignored_file.parent.mkdir()
    ignored_file.write_bytes(b"ignored but out of scope\n")

    _diff_bytes, signed = _signed_runner_diff(
        tmp_path / "candidate", base_head, ["src/app.py"],
    )

    assert signed["verdict"] == "FAIL"
    assert signed["reason"] == "OUT_OF_SCOPE_PATH"
    assert signed["changed_paths"] == [ignored_path]


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
