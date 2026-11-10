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
STDERR = b"(no stderr)\n"
EVIDENCE = "docs/sdlc/evidence/qa"


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
               prefix=(b"", b""), older_lines=(), record=None):
    """Write the three fixed artifacts of one lane. file_stdout overrides the bytes on disk (tampering)."""
    record = record if record is not None else make_record(registry, category, head, prefix=prefix, mutate=mutate)
    directory = root / EVIDENCE
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{category}.report.jsonl").write_bytes(b"".join(older_lines) + encode_report(record))
    (directory / f"{category}.stdout.txt").write_bytes(prefix[0] + (STDOUT if file_stdout is None else file_stdout))
    (directory / f"{category}.stderr.txt").write_bytes(prefix[1] + STDERR)
    return record


def file_digest(root: Path, relative: str) -> str:
    return hashlib.sha256((root / relative).read_bytes()).hexdigest()


@pytest.fixture()
def registry():
    return make_registry()


def resolver(root, registry, head=HEAD, fallback=None):
    return gb.make_qa_artifact_resolver(root, expected_head=head, registry=registry, fallback=fallback)


def skip_one(record):
    record["skipped_test_ids"] = [ID_B]
    record["passed_test_ids"] = [ID_A]


def uncollect_one(record):
    record["uncollected_test_ids"] = [ID_B]
    record["passed_test_ids"] = [ID_A]
    record["executed_node_ids"] = [ID_A]


# ------------------------------------------------------------------ approvable
def test_approvable_report_resolves_to_the_sha256_of_its_raw_bytes(tmp_path, registry):
    write_lane(tmp_path, registry)
    resolve = resolver(tmp_path, registry)
    path = functional_path()
    assert resolve(path) == file_digest(tmp_path, path)
    check = gb.qa_gate_reasons(tmp_path, "functional", expected_head=HEAD, registry=registry)
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


def test_last_record_wins_so_a_newer_non_approving_run_withdraws_the_digest(tmp_path, registry):
    good = encode_report(make_record(registry))
    write_lane(tmp_path, registry, older_lines=(good,), mutate=skip_one)
    assert resolver(tmp_path, registry)(functional_path()) is None


# ------------------------------------------------------------------ non-approving records
@pytest.mark.parametrize("mutate,code", [(skip_one, "SKIPPED_IDS"), (uncollect_one, "UNCOLLECTED_IDS")])
def test_skipped_or_uncollected_required_id_resolves_to_none(tmp_path, registry, mutate, code):
    write_lane(tmp_path, registry, mutate=mutate)
    resolve = resolver(tmp_path, registry)
    for kind in ("report.jsonl", "stdout.txt", "stderr.txt"):
        assert resolve(functional_path(kind)) is None
    check = gb.qa_gate_reasons(tmp_path, "functional", expected_head=HEAD, registry=registry)
    assert check.verdict == NON_APPROVING and code in check.codes()


def test_stale_head_resolves_to_none(tmp_path, registry):
    write_lane(tmp_path, registry, head="b" * 40)
    assert resolver(tmp_path, registry)(functional_path()) is None
    check = gb.qa_gate_reasons(tmp_path, "functional", expected_head=HEAD, registry=registry)
    assert "STALE_HEAD" in check.codes()


def test_tampered_stdout_resolves_to_none(tmp_path, registry):
    write_lane(tmp_path, registry, file_stdout=b"PASS something else entirely\nxx\n")
    resolve = resolver(tmp_path, registry)
    assert resolve(functional_path()) is None
    assert resolve(functional_path("stdout.txt")) is None
    assert "ARTIFACT_MISMATCH" in gb.qa_gate_reasons(
        tmp_path, "functional", expected_head=HEAD, registry=registry).codes()


def test_missing_or_out_of_range_artifact_range_resolves_to_none(tmp_path, registry):
    def no_ranges(record):
        del record["artifact_ranges"]

    def past_end(record):
        record["artifact_ranges"]["stdout"] = {"start": 0, "end": 10_000}

    for mutate in (no_ranges, past_end):
        write_lane(tmp_path, registry, mutate=mutate)
        assert resolver(tmp_path, registry)(functional_path()) is None


def test_category_path_mismatch_resolves_to_none(tmp_path, registry):
    # An approvable "api" record planted at the functional report path.
    record = make_record(registry, category="api")
    write_lane(tmp_path, registry, "functional", record=record)
    assert resolver(tmp_path, registry)(functional_path()) is None
    check = gb.qa_gate_reasons(tmp_path, "functional", expected_head=HEAD, registry=registry)
    assert "CATEGORY_PATH_MISMATCH" in check.codes()


def test_recorded_artifact_paths_must_be_the_fixed_category_paths(tmp_path, registry):
    def foreign_paths(record):
        record["artifact_paths"]["stdout"] = f"{EVIDENCE}/api.stdout.txt"

    write_lane(tmp_path, registry, mutate=foreign_paths)
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_missing_files_and_unparseable_report_resolve_to_none(tmp_path, registry):
    resolve = resolver(tmp_path, registry)
    assert resolve(functional_path()) is None  # nothing on disk
    write_lane(tmp_path, registry)
    (tmp_path / functional_path()).write_bytes(b"{not json\n")
    assert resolve(functional_path()) is None
    (tmp_path / functional_path()).write_bytes(b"")
    assert resolve(functional_path()) is None
    (tmp_path / functional_path("stderr.txt")).unlink()
    assert resolve(functional_path("stderr.txt")) is None


def test_bad_expected_head_resolves_to_none(tmp_path, registry):
    write_lane(tmp_path, registry)
    for head in ("", "A" * 40, "a" * 39, None):
        assert resolver(tmp_path, registry, head=head)(functional_path()) is None


# ------------------------------------------------------------------ path handling
@pytest.mark.parametrize("path", [
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
])
def test_non_report_and_traversal_spellings_resolve_to_none_and_never_reach_the_fallback(tmp_path, registry, path):
    write_lane(tmp_path, registry)
    seen = []

    def fallback(p):
        seen.append(p)
        return "f" * 64

    # Every spelling here names the QA directory: strict-or-None, the fallback must never see it.
    assert resolver(tmp_path, registry, fallback=fallback)(path) is None
    assert seen == []
    assert resolver(tmp_path, registry)(path) is None


def test_non_str_path_resolves_to_none(tmp_path, registry):
    resolve = resolver(tmp_path, registry, fallback=lambda p: "f" * 64)
    for bad in (None, 3, b"docs/x", ["a"]):
        assert resolve(bad) is None


def test_unknown_category_report_path_resolves_to_none_even_when_files_exist(tmp_path, registry):
    write_lane(tmp_path, registry)
    directory = tmp_path / EVIDENCE
    (directory / "regression.report.jsonl").write_bytes((directory / "functional.report.jsonl").read_bytes())
    assert resolver(tmp_path, registry)(f"{EVIDENCE}/regression.report.jsonl") is None
    check = gb.qa_gate_reasons(tmp_path, "regression", expected_head=HEAD, registry=registry)
    assert check.verdict == NON_APPROVING and "UNKNOWN_CATEGORY" in check.codes()


def test_non_qa_path_uses_the_fallback_when_given_and_none_otherwise(tmp_path, registry):
    write_lane(tmp_path, registry)
    assert resolver(tmp_path, registry)("src/a.py") is None
    assert resolver(tmp_path, registry, fallback=lambda p: "e" * 64 if p == "src/a.py" else None)("src/a.py") == "e" * 64
    assert resolver(tmp_path, registry, fallback=lambda p: None)("src/a.py") is None
    assert resolver(tmp_path, registry, fallback=lambda p: 5)("src/a.py") is None

    def boom(p):
        raise OSError("disk gone")

    assert resolver(tmp_path, registry, fallback=boom)("src/a.py") is None


# ------------------------------------------------------------------ filesystem safety
def test_symlinked_report_is_refused_when_the_platform_can_create_one(tmp_path, registry):
    write_lane(tmp_path, registry)
    target = tmp_path / functional_path()
    real = tmp_path / "real.report.jsonl"
    real.write_bytes(target.read_bytes())
    target.unlink()
    try:
        os.symlink(real, target)
    except (OSError, NotImplementedError):
        return  # no symlink privilege here; the deterministic link test below still guards the code path
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_link_like_component_is_refused_on_the_read_path(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    assert resolver(tmp_path, registry)(functional_path()) is not None
    monkeypatch.setattr(gb, "_is_link_like", lambda info: True)
    assert resolver(tmp_path, registry)(functional_path()) is None
    assert resolver(tmp_path, registry)(functional_path("stdout.txt")) is None


def test_hard_linked_report_is_refused(tmp_path, registry):
    write_lane(tmp_path, registry)
    try:
        os.link(tmp_path / functional_path(), tmp_path / "alias.jsonl")
    except (OSError, NotImplementedError):
        return
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_directory_in_place_of_a_file_is_refused(tmp_path, registry):
    write_lane(tmp_path, registry)
    target = tmp_path / functional_path("stderr.txt")
    target.unlink()
    target.mkdir()
    assert resolver(tmp_path, registry)(functional_path()) is None


def test_oversized_report_and_artifact_resolve_to_none(tmp_path, registry, monkeypatch):
    write_lane(tmp_path, registry)
    resolve = resolver(tmp_path, registry)
    assert resolve(functional_path()) is not None
    monkeypatch.setattr(gb, "MAX_REPORT_BYTES", 16)
    assert resolve(functional_path()) is None
    monkeypatch.undo()
    assert resolve(functional_path()) is not None
    monkeypatch.setattr(gb, "MAX_ARTIFACT_FILE_BYTES", 16)
    assert resolve(functional_path()) is None
    assert resolve(functional_path("stdout.txt")) is None


def test_resolver_never_raises_for_a_bad_repo_root(tmp_path, registry):
    resolve = resolver(tmp_path / "does-not-exist", registry)
    assert resolve(functional_path()) is None
    check = gb.qa_gate_reasons(tmp_path / "does-not-exist", "functional", expected_head=HEAD, registry=registry)
    assert check.verdict == NON_APPROVING


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
