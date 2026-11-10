"""U3-5 tests: tools/qa/gate_bridge.py (QA no-skip verifier wired into the VST gate's artifact_resolver).

NOT_RUN: written statically; never executed by the author (pytest is forbidden for this sprint).

Everything is synthetic and in-process: a hand-built ValidatedRegistry, hand-built schema-3 lane records
encoded with the real tools.qa.report.encode_report, files in tmp_path. The runner is never started and
no real repository lane is touched. The evaluate()-level cases call the unchanged tools.vst.gate.evaluate.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tools.qa import gate_bridge as gb
from tools.qa.gate_check import APPROVABLE, NON_APPROVING
from tools.qa.registry import WINDOWS_PROFILE, WSL_PROFILE, ValidatedRegistry
from tools.qa.report import encode_report, sha256_bytes
from tools.vst import gate

from tests.vst.e1e4_helpers import (
    EPOCH, HEAD, KEY, OPERATOR_KEY, SUPERVISOR_KEY, manifest, receipt,
)

CATEGORIES = ("functional", "api", "qa-tooling")
ID_A = "tests/qa/test_x.py::test_a"
ID_B = "tests/qa/test_x.py::test_b"
STDOUT = b"PASS tests/qa/test_x.py::test_a\nPASS tests/qa/test_x.py::test_b\n"
STDERR = b"PASS stderr line one\n(no stderr)\n"
EVIDENCE = "docs/sdlc/evidence/qa"
FALLBACK_DIGEST = "f" * 64


def functional_path(kind: str = "report.jsonl") -> str:
    return f"{EVIDENCE}/functional.{kind}"


def make_registry() -> ValidatedRegistry:
    ids = [ID_A, ID_B]
    return ValidatedRegistry(
        data={
            "source_head": "5" * 40,
            "categories": {c: {"status": "SUPPORTED", "reason": None} for c in CATEGORIES},
        },
        sha256="c" * 64,
        candidate_head=HEAD,
        selectors_by_id={},
        category_test_ids={c: list(ids) for c in CATEGORIES},
        category_inventory_ids={c: list(ids) for c in CATEGORIES},
        category_not_run={c: {} for c in CATEGORIES},
        category_profile_test_ids={c: {WINDOWS_PROFILE: list(ids), WSL_PROFILE: []} for c in CATEGORIES},
        category_profile_not_run={c: {WINDOWS_PROFILE: {}, WSL_PROFILE: {}} for c in CATEGORIES},
        category_profile_unassigned_ids={c: {WINDOWS_PROFILE: [], WSL_PROFILE: []} for c in CATEGORIES},
        artifact_stage={},
    )


def make_record(registry, category="functional", head=HEAD, stdout=STDOUT, stderr=STDERR, prefix=(b"", b""), mutate=None):
    ids = [ID_A, ID_B]
    base = f"{EVIDENCE}/{category}"
    record = {
        "schema_version": 3, "category": category, "runtime_profile": WINDOWS_PROFILE,
        "candidate_head": head, "head_after": head, "registry_sha256": registry.sha256,
        "source_head": registry.data["source_head"], "lock_sha256": "ab" * 32,
        "expected_test_ids": list(ids), "unassigned_test_ids": [], "not_run_test_reasons": {},
        "executed_node_ids": list(ids), "passed_test_ids": list(ids), "failed_test_ids": [],
        "skipped_test_ids": [], "xfail_test_ids": [], "unexpected_node_ids": [], "uncollected_test_ids": [],
        "exit_code": 0, "profile_status": {WINDOWS_PROFILE: "EXECUTED"},
        "dirty_tree": {"before": False, "after": False, "before_paths": [], "after_paths": []},
        "git_state_unchanged": True, "evidence_unchanged": True,
        "dependency_content_verified_before": True, "dependency_content_verified_after": True,
        "artifact_paths": {
            "report": f"{base}.report.jsonl", "stdout": f"{base}.stdout.txt", "stderr": f"{base}.stderr.txt",
        },
        "artifact_digests": {"stdout": sha256_bytes(stdout), "stderr": sha256_bytes(stderr)},
        "artifact_sizes": {"stdout": len(stdout), "stderr": len(stderr)},
        "artifact_ranges": {
            "stdout": {"start": len(prefix[0]), "end": len(prefix[0]) + len(stdout)},
            "stderr": {"start": len(prefix[1]), "end": len(prefix[1]) + len(stderr)},
        },
        "result": "PASS", "command": ["<approved-python-base>/python.exe", "-m", "pytest"],
        "manifest_path": "docs/qa/categories.json", "normalized_sha256": None,
    }
    if mutate is not None:
        mutate(record)
    return record


def write_lane(root: Path, registry, category="functional", *, head=HEAD, mutate=None, file_stdout=None,
               file_stderr=None, prefix=(b"", b""), older_lines=(), record=None):
    """Write the three fixed artifacts of one lane. file_stdout/file_stderr override the bytes on disk (tampering)."""
    record = record if record is not None else make_record(registry, category, head, prefix=prefix, mutate=mutate)
    directory = root / EVIDENCE
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{category}.report.jsonl").write_bytes(b"".join(older_lines) + encode_report(record))
    (directory / f"{category}.stdout.txt").write_bytes(prefix[0] + (STDOUT if file_stdout is None else file_stdout))
    (directory / f"{category}.stderr.txt").write_bytes(prefix[1] + (STDERR if file_stderr is None else file_stderr))
    return record


def file_digest(root: Path, relative: str) -> str:
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


@pytest.fixture()
def registry():
    return make_registry()


def resolver(root, registry, head=HEAD, fallback=None):
    """A NEW resolver per call: a resolver instance memoizes one snapshot per category."""
    return gb.make_qa_artifact_resolver(root, expected_head=head, registry=registry, fallback=fallback)


def reasons(root, registry, head=HEAD, category="functional"):
    return gb.qa_gate_reasons(root, category, expected_head=head, registry=registry)


def skip_one(record):
    record["skipped_test_ids"] = [ID_B]
    record["passed_test_ids"] = [ID_A]


def uncollect_one(record):
    record["uncollected_test_ids"] = [ID_B]
    record["passed_test_ids"] = [ID_A]
    record["executed_node_ids"] = [ID_A]


class _StatWith:
    """A stat result copy with some attributes overridden."""

    def __init__(self, info, **over):
        self._info, self._over = info, over

    def __getattr__(self, name):
        return self._over[name] if name in self._over else getattr(self._info, name)


class _OsProxy:
    """Stands in for the os module inside gate_bridge only; delegates everything not overridden."""

    def __init__(self, **over):
        self._over = over

    def __getattr__(self, name):
        return self._over[name] if name in self._over else getattr(os, name)


# ------------------------------------------------------------------ approvable
def test_approvable_report_resolves_to_the_sha256_of_its_raw_bytes(tmp_path, registry):
    write_lane(tmp_path, registry)
    path = functional_path()
    assert resolver(tmp_path, registry)(path) == file_digest(tmp_path, path)
    check = reasons(tmp_path, registry)
    assert check.verdict == APPROVABLE and check.reasons == ()


def test_sibling_stdout_and_stderr_resolve_only_for_an_approvable_report(tmp_path, registry):
    write_lane(tmp_path, registry)
    resolve = resolver(tmp_path, registry)
    for kind in ("stdout.txt", "stderr.txt"):
        assert resolve(functional_path(kind)) == file_digest(tmp_path, functional_path(kind))


def test_append_only_artifacts_are_verified_by_their_recorded_range(tmp_path, registry):
    write_lane(tmp_path, registry, prefix=(b"older run stdout\n", b"older run stderr\n"))
    resolve = resolver(tmp_path, registry)
    assert resolve(functional_path()) == file_digest(tmp_path, functional_path())
    assert resolve(functional_path("stdout.txt")) == file_digest(tmp_path, functional_path("stdout.txt"))


def test_a_full_64_hex_head_is_accepted(tmp_path, registry):
    head = "ab" * 32
    write_lane(tmp_path, registry, head=head)
    assert resolver(tmp_path, registry, head=head)(functional_path()) == file_digest(tmp_path, functional_path())


def test_last_record_wins_so_a_newer_non_approving_run_withdraws_the_digest(tmp_path, registry):
    good = encode_report(make_record(registry))
    write_lane(tmp_path, registry, older_lines=(good,), mutate=skip_one)
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_older_bad_record_then_newer_good_record_is_approvable(tmp_path, registry):
    bad = encode_report(make_record(registry, mutate=skip_one))
    write_lane(tmp_path, registry, older_lines=(bad,))
    assert reasons(tmp_path, registry).verdict == APPROVABLE
    assert resolver(tmp_path, registry)(functional_path()) == file_digest(tmp_path, functional_path())


def test_a_garbage_line_anywhere_refuses_the_whole_file(tmp_path, registry):
    good = encode_report(make_record(registry))
    write_lane(tmp_path, registry, older_lines=(b"{garbage\n", good))
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert "REPORT_UNREADABLE" in reasons(tmp_path, registry).codes()


# ------------------------------------------------------------------ non-approving records
@pytest.mark.parametrize("mutate,code", [(skip_one, "SKIPPED_IDS"), (uncollect_one, "UNCOLLECTED_IDS")])
def test_skipped_or_uncollected_required_id_resolves_to_none(tmp_path, registry, mutate, code):
    write_lane(tmp_path, registry, mutate=mutate)
    resolve = resolver(tmp_path, registry)
    for kind in ("report.jsonl", "stdout.txt", "stderr.txt"):
        assert resolve(functional_path(kind)) is None
    check = reasons(tmp_path, registry)
    assert check.verdict == NON_APPROVING and code in check.codes()


def test_stale_candidate_head_resolves_to_none(tmp_path, registry):
    write_lane(tmp_path, registry, head="b" * 40)
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert "STALE_HEAD" in reasons(tmp_path, registry).codes()


def test_head_after_differing_alone_resolves_to_none(tmp_path, registry):
    write_lane(tmp_path, registry, mutate=lambda r: r.update(head_after="b" * 40))
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert reasons(tmp_path, registry).codes() == {"STALE_HEAD"}


def test_tampered_stdout_same_length_resolves_to_none_for_all_three_paths(tmp_path, registry):
    tampered = STDOUT.replace(b"PASS", b"FAIL")
    assert len(tampered) == len(STDOUT) and tampered != STDOUT
    write_lane(tmp_path, registry, file_stdout=tampered)
    resolve = resolver(tmp_path, registry)
    for kind in ("report.jsonl", "stdout.txt", "stderr.txt"):
        assert resolve(functional_path(kind)) is None
    assert "ARTIFACT_MISMATCH" in reasons(tmp_path, registry).codes()


def test_tampered_stderr_same_length_resolves_to_none_for_all_three_paths(tmp_path, registry):
    tampered = STDERR.replace(b"PASS", b"FAIL")
    assert len(tampered) == len(STDERR) and tampered != STDERR
    write_lane(tmp_path, registry, file_stderr=tampered)
    resolve = resolver(tmp_path, registry)
    for kind in ("report.jsonl", "stdout.txt", "stderr.txt"):
        assert resolve(functional_path(kind)) is None
    assert "ARTIFACT_MISMATCH" in reasons(tmp_path, registry).codes()


def test_missing_or_out_of_range_artifact_range_resolves_to_none(tmp_path, registry):
    def no_ranges(record):
        del record["artifact_ranges"]

    def past_end(record):
        record["artifact_ranges"]["stdout"] = {"start": 0, "end": 10_000}

    for mutate in (no_ranges, past_end):
        write_lane(tmp_path, registry, mutate=mutate)
        assert resolver(tmp_path, registry)(functional_path()) is None
        assert "ARTIFACT_UNVERIFIED" in reasons(tmp_path, registry).codes()


def test_bytes_after_the_recorded_range_are_refused(tmp_path, registry):
    write_lane(tmp_path, registry)
    with (tmp_path / functional_path("stdout.txt")).open("ab") as handle:
        handle.write(b"appended later\n")
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert "ARTIFACT_UNVERIFIED" in reasons(tmp_path, registry).codes()


def test_category_path_mismatch_is_the_only_extra_code(tmp_path, registry):
    # The record keeps the functional artifact paths and digests; only its category field changes.
    record = make_record(registry, "functional", mutate=lambda r: r.update(category="api"))
    write_lane(tmp_path, registry, "functional", record=record)
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert reasons(tmp_path, registry).codes() == {"CATEGORY_PATH_MISMATCH"}


def test_recorded_artifact_paths_must_be_the_fixed_category_paths(tmp_path, registry):
    def foreign_paths(record):
        record["artifact_paths"]["stdout"] = f"{EVIDENCE}/api.stdout.txt"

    write_lane(tmp_path, registry, mutate=foreign_paths)
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert reasons(tmp_path, registry).codes() == {"ARTIFACT_INVENTORY"}


def test_missing_files_and_unparseable_report_resolve_to_none(tmp_path, registry):
    assert resolver(tmp_path, registry)(functional_path()) is None  # nothing on disk
    write_lane(tmp_path, registry)
    (tmp_path / functional_path()).write_bytes(b"{not json\n")
    assert resolver(tmp_path, registry)(functional_path()) is None
    (tmp_path / functional_path()).write_bytes(b"")
    assert resolver(tmp_path, registry)(functional_path()) is None
    write_lane(tmp_path, registry)
    (tmp_path / functional_path("stderr.txt")).unlink()
    assert resolver(tmp_path, registry)(functional_path("stderr.txt")) is None


def test_bad_expected_head_resolves_to_none(tmp_path, registry):
    write_lane(tmp_path, registry)
    for head in ("", "A" * 40, "a" * 39, None):
        assert resolver(tmp_path, registry, head=head)(functional_path()) is None
    assert "BAD_EXPECTED_HEAD" in reasons(tmp_path, registry, head="zz").codes()


# ------------------------------------------------------------------ _range_slice
@pytest.mark.parametrize("rng", [
    {"start": True, "end": 3}, {"start": 0, "end": True}, {"start": "0", "end": 3}, {"start": 0.0, "end": 3},
    {"start": 2, "end": 1}, {"start": -1, "end": 3}, {"start": 0, "end": 2},  # end != len(data): not the tail
    {"start": 0, "end": 3, "extra": 1}, {"start": 0}, {}, [0, 3], "0-3", None, 3,
])
def test_range_slice_refuses_bad_inputs(rng):
    with pytest.raises(gb._BridgeReadError):
        gb._range_slice(b"abc", rng)


def test_range_slice_returns_the_tail_bytes():
    assert gb._range_slice(b"abc", {"start": 1, "end": 3}) == b"bc"
    assert gb._range_slice(bytearray(b"abc"), {"start": 0, "end": 3}) == b"abc"
    assert gb._range_slice(b"", {"start": 0, "end": 0}) == b""


# ------------------------------------------------------------------ path ownership
QA_OWNED_SPELLINGS = [
    f"{EVIDENCE}/../../../README.md",
    f"{EVIDENCE}/../qa/functional.report.jsonl",
    f"{EVIDENCE}/./functional.report.jsonl",
    f"{EVIDENCE}//functional.report.jsonl",
    f"{EVIDENCE}/sub/functional.report.jsonl",
    f"{EVIDENCE}/functional.report.jsonl/",
    f"{EVIDENCE}/functional.report.jsonl\n",
    f"{EVIDENCE}/Functional.report.jsonl",
    f"{EVIDENCE}/nope.report.jsonl",
    f"{EVIDENCE}/functional.other.txt",
    f"{EVIDENCE}/functional.report.jsonl.bak",
    "/abs/" + functional_path(),
    "C:/repo/" + functional_path(),
    "C:\\repo\\" + functional_path().replace("/", "\\"),
    functional_path().replace("/", "\\"),
    functional_path().upper(),
    "./" + functional_path(),
    f"{EVIDENCE}/",
    # normalization-only spellings (the raw form does not contain the QA segments in order)
    "docs/sdlc/evidence/x/../qa/functional.report.jsonl",
    "zzz/../docs/sdlc/evidence/qa/functional.stdout.txt",
    "docs/sdlc/evidence/qa/zzz/../functional.report.jsonl",
]
NOT_ELIGIBLE_FOR_FALLBACK = [
    # not owned by the QA directory but not canonical either: refused without calling the fallback
    "docs/sdlc/evidence/qa./functional.report.jsonl",
    "docs/sdlc/evidence/qa::$DATA/functional.report.jsonl",
    "docs/sdlc/evidence/qa::$INDEX_ALLOCATION/functional.report.jsonl",
    "docs/sdlc/evidence/qa /functional.report.jsonl",
    "docs/sdlc/evidence/qa~1/functional.report.jsonl",
    "a//b", "a/./b", "a/b/", "./a", "../a", "a/../b", "/a", "a\\b", "~x", "a~1/b", "a:b", "a b", "dir./x",
    "x.", "", ".", "..", "a/b\n", "\u0430/b",
]


@pytest.mark.parametrize("path", QA_OWNED_SPELLINGS + NOT_ELIGIBLE_FOR_FALLBACK)
def test_qa_owned_and_non_canonical_paths_resolve_to_none_and_never_reach_the_fallback(tmp_path, registry, path):
    write_lane(tmp_path, registry)
    seen = []

    def fallback(p):
        seen.append(p)
        return FALLBACK_DIGEST

    assert resolver(tmp_path, registry, fallback=fallback)(path) is None
    assert seen == []
    assert resolver(tmp_path, registry)(path) is None


def test_non_str_path_resolves_to_none(tmp_path, registry):
    resolve = resolver(tmp_path, registry, fallback=lambda p: FALLBACK_DIGEST)
    for bad in (None, 3, b"docs/x", ["a"]):
        assert resolve(bad) is None


def test_unknown_category_report_path_resolves_to_none_even_when_files_exist(tmp_path, registry):
    write_lane(tmp_path, registry)
    directory = tmp_path / EVIDENCE
    (directory / "regression.report.jsonl").write_bytes((directory / "functional.report.jsonl").read_bytes())
    assert resolver(tmp_path, registry)(f"{EVIDENCE}/regression.report.jsonl") is None
    check = reasons(tmp_path, registry, category="regression")
    assert check.verdict == NON_APPROVING and "UNKNOWN_CATEGORY" in check.codes()


def test_plain_non_qa_paths_use_the_fallback_when_given_and_none_otherwise(tmp_path, registry):
    write_lane(tmp_path, registry)
    assert resolver(tmp_path, registry)("src/a.py") is None
    assert resolver(tmp_path, registry, fallback=lambda p: FALLBACK_DIGEST if p == "src/a.py" else None)(
        "src/a.py") == FALLBACK_DIGEST
    assert resolver(tmp_path, registry, fallback=lambda p: None)("src/a.py") is None

    def boom(p):
        raise OSError("disk gone")

    assert resolver(tmp_path, registry, fallback=boom)("src/a.py") is None


def test_qa_other_directory_is_not_qa_owned_and_reaches_the_fallback(tmp_path, registry):
    seen = []

    def fallback(p):
        seen.append(p)
        return FALLBACK_DIGEST

    resolve = resolver(tmp_path, registry, fallback=fallback)
    assert resolve("docs/sdlc/evidence/qa-other/x.txt") == FALLBACK_DIGEST
    assert resolve("docs/sdlc/evidence/qax/functional.report.jsonl") == FALLBACK_DIGEST
    assert seen == ["docs/sdlc/evidence/qa-other/x.txt", "docs/sdlc/evidence/qax/functional.report.jsonl"]


@pytest.mark.parametrize("bad", ["x", "", "F" * 64, "f" * 63, "f" * 65, " " + "f" * 63, "f" * 64 + "\n", 5, None, b"f" * 64])
def test_fallback_result_must_be_64_lowercase_hex(tmp_path, registry, bad):
    assert resolver(tmp_path, registry, fallback=lambda p: bad)("src/a.py") is None


# ------------------------------------------------------------------ filesystem safety
def test_symlinked_report_is_refused(tmp_path, registry):
    write_lane(tmp_path, registry)
    target = tmp_path / functional_path()
    assert resolver(tmp_path, registry)(functional_path()) is not None  # positive control before the link
    real = tmp_path / "real.report.jsonl"
    real.write_bytes(target.read_bytes())
    target.unlink()
    try:
        os.symlink(real, target)
    except (OSError, NotImplementedError):
        pytest.skip("this platform or account cannot create symlinks; the deterministic link tests below cover the check")
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_hard_linked_report_is_refused(tmp_path, registry):
    write_lane(tmp_path, registry)
    assert resolver(tmp_path, registry)(functional_path()) is not None  # positive control before the link
    try:
        os.link(tmp_path / functional_path(), tmp_path / "alias.jsonl")
    except (OSError, NotImplementedError):
        pytest.skip("this platform or account cannot create hard links; the deterministic nlink tests cover the check")
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_link_like_component_is_refused_on_the_read_path(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    assert resolver(tmp_path, registry)(functional_path()) is not None
    monkeypatch.setattr(gb, "_is_link_like", lambda info: True)
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert resolver(tmp_path, registry)(functional_path("stdout.txt")) is None


def test_reparse_point_attribute_counts_as_a_link():
    class Info:
        st_mode = 0o100644
        st_file_attributes = 0x400

    assert gb._is_link_like(Info()) is True


def test_nlink_two_seen_by_lstat_is_refused(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    real = os.lstat

    def lstat(path, *a, **k):
        info = real(path, *a, **k)
        return _StatWith(info, st_nlink=2) if str(path).endswith(".report.jsonl") else info

    assert resolver(tmp_path, registry)(functional_path()) is not None  # positive control
    monkeypatch.setattr(gb, "os", _OsProxy(lstat=lstat))
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_nlink_two_seen_by_fstat_is_refused(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    real = os.fstat
    assert resolver(tmp_path, registry)(functional_path()) is not None  # positive control
    monkeypatch.setattr(gb, "os", _OsProxy(fstat=lambda fd: _StatWith(real(fd), st_nlink=2)))
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_file_swapped_between_lstat_and_open_is_refused(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    real = os.fstat
    monkeypatch.setattr(gb, "os", _OsProxy(fstat=lambda fd: _StatWith(real(fd), st_ino=real(fd).st_ino + 1)))
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_directory_in_place_of_a_file_is_refused(tmp_path, registry):
    write_lane(tmp_path, registry)
    target = tmp_path / functional_path("stderr.txt")
    target.unlink()
    target.mkdir()
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_public_reader_returns_bytes_and_refuses_links(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    root = tmp_path.resolve()
    assert bytes(gb.read_regular_file(root, functional_path("stdout.txt"), 1024)) == STDOUT
    monkeypatch.setattr(gb, "_is_link_like", lambda info: True)
    with pytest.raises(gb._BridgeReadError):
        gb.read_regular_file(root, functional_path("stdout.txt"), 1024)


# ------------------------------------------------------------------ size caps
def test_report_over_the_cap_is_a_typed_evidence_too_large(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    size = (tmp_path / functional_path()).stat().st_size
    assert resolver(tmp_path, registry)(functional_path()) is not None  # exactly at the limit is fine below
    monkeypatch.setattr(gb, "MAX_REPORT_BYTES", size)
    assert reasons(tmp_path, registry).verdict == APPROVABLE
    monkeypatch.setattr(gb, "MAX_REPORT_BYTES", size - 1)  # cap + 1
    check = reasons(tmp_path, registry)
    assert check.verdict == NON_APPROVING and check.codes() == {"EVIDENCE_TOO_LARGE"}
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_artifact_over_the_cap_is_a_typed_evidence_too_large(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    size = (tmp_path / functional_path("stdout.txt")).stat().st_size
    monkeypatch.setattr(gb, "MAX_ARTIFACT_FILE_BYTES", size - 1)
    assert reasons(tmp_path, registry).codes() == {"EVIDENCE_TOO_LARGE"}
    for kind in ("report.jsonl", "stdout.txt", "stderr.txt"):
        assert resolver(tmp_path, registry)(functional_path(kind)) is None


def test_file_larger_than_stat_size_is_treated_as_changed(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    real = os.fstat
    monkeypatch.setattr(gb, "os", _OsProxy(fstat=lambda fd: _StatWith(real(fd), st_size=real(fd).st_size - 1)))
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert reasons(tmp_path, registry).codes() == {"REPORT_UNREADABLE"}


def test_resolver_never_raises_for_a_bad_repo_root(tmp_path, registry):
    assert resolver(tmp_path / "does-not-exist", registry)(functional_path()) is None
    check = reasons(tmp_path / "does-not-exist", registry)
    assert check.verdict == NON_APPROVING


# ------------------------------------------------------------------ snapshot reuse
def test_one_snapshot_serves_the_three_digests_of_a_receipt(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    calls = []
    real = gb._load

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(gb, "_load", counting)
    resolve = resolver(tmp_path, registry)
    digests = [resolve(functional_path(kind)) for kind in ("report.jsonl", "stdout.txt", "stderr.txt")]
    assert all(d is not None for d in digests) and len(calls) == 1


def test_a_changed_file_invalidates_the_snapshot(tmp_path, registry):
    write_lane(tmp_path, registry)
    resolve = resolver(tmp_path, registry)
    assert resolve(functional_path()) is not None
    with (tmp_path / functional_path("stdout.txt")).open("ab") as handle:
        handle.write(b"x")
    assert resolve(functional_path()) is None
    assert resolve(functional_path("stdout.txt")) is None


# ------------------------------------------------------------------ reasons are bounded and redacted
def test_sanitize_bounds_and_redacts():
    text = "password=hunter2222 at C:\\Users\\bob\\secret.txt and /home/bob/x " + "y" * 500
    cleaned = gb._sanitize(text)
    assert len(cleaned) <= gb.MAX_DETAIL_CHARS
    assert "hunter2222" not in cleaned and "bob" not in cleaned


def test_reason_details_are_bounded(tmp_path, registry):
    write_lane(tmp_path, registry, mutate=lambda r: r.update(result="X" * 5000))
    check = reasons(tmp_path, registry)
    assert check.verdict == NON_APPROVING
    assert all(len(detail) <= gb.MAX_DETAIL_CHARS for _, detail in check.reasons)


# ------------------------------------------------------------------ gate level
def evaluate(receipts, artifact_resolver):
    return gate.evaluate(
        manifest(), receipts, HEAD, EPOCH, KEY,
        supervisor_key=SUPERVISOR_KEY, operator_key=OPERATOR_KEY, artifact_resolver=artifact_resolver,
    )


def receipts_for(digest):
    return [
        receipt("TestRun", artifact_digests={functional_path(): digest}),
        receipt("StaticAnalysis"),
        receipt("IndependentReview"),
    ]


def test_gate_accepts_a_receipt_listing_an_approvable_qa_report_digest(tmp_path, registry):
    write_lane(tmp_path, registry)
    digest = file_digest(tmp_path, functional_path())
    decision = evaluate(receipts_for(digest), resolver(tmp_path, registry))
    assert decision["verdict"] == "APPROVE", decision["reasons"]


def test_gate_hard_refuses_a_receipt_listing_a_non_approving_qa_report_digest(tmp_path, registry):
    write_lane(tmp_path, registry, mutate=skip_one)
    digest = file_digest(tmp_path, functional_path())  # the receipt cites the true bytes of the skipped report
    # Guard: a naive byte-hash resolver would accept it; the bridge must not.
    naive = evaluate(receipts_for(digest), lambda p: file_digest(tmp_path, p))
    assert naive["verdict"] == "APPROVE"
    decision = evaluate(receipts_for(digest), resolver(tmp_path, registry))
    assert decision["verdict"] == "MODIFY"
    text = " | ".join(decision["reasons"])
    assert "digest mismatch" in text and functional_path() in text
    assert "slot 'tests' latest attempt 1 rejected: artifact check failed" in decision["reasons"]


def test_gate_hard_refuses_a_stale_head_qa_report(tmp_path, registry):
    write_lane(tmp_path, registry, head="b" * 40)
    digest = file_digest(tmp_path, functional_path())
    decision = evaluate(receipts_for(digest), resolver(tmp_path, registry))
    assert decision["verdict"] == "MODIFY"
    assert "digest mismatch" in " | ".join(decision["reasons"])


def test_gate_still_denies_qa_digests_without_a_resolver(tmp_path, registry):
    write_lane(tmp_path, registry)
    decision = evaluate(receipts_for(file_digest(tmp_path, functional_path())), None)
    assert decision["verdict"] == "MODIFY"
    assert "artifact digests present but no artifact_resolver" in decision["reasons"]
