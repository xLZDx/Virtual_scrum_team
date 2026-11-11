"""U5-5: final package builder for GPT-PM.

Acceptance text: "Builds the package with the exact diff, test evidence, review results and head identity;
refuses stale evidence; a new commit invalidates it."

The builder is pure, so every test calls the public API with plain dicts. Inputs are built by hand in this
file (the review result has the shape of `ReviewLoopResult.to_dict`, the proof the shape of
`worker_gate.build_isolation_proof`, the run record the shape of `patch_proposals.build_run_record`).
Expected values are restated with stdlib formulas (sha256 of the bytes, canonical JSON via `json.dumps`) or
taken from the data written here and from docs/sdlc/u5/FINAL_PACKAGE.md. Nothing touches git, a file, the
network or a clock. Tests are written, NOT_RUN (operator ban).
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from tools.vst import final_package as fp
from tools.vst import worker_gate as wg
from tools.vst.patch_proposals import RUN_RECORD_SCHEMA


def h(n: int) -> str:
    return f"{n:040x}"


BASE = h(1)
HEAD = h(2)
OTHER = h(3)
STORY = "U5-5-demo"
NOW = "2026-11-11T10:00:00Z"
EVID = "d" * 64
EVID2 = "e" * 64
RECEIPT_SHA = "b" * 64
COVERAGE = ["g2.python-rules"]
T1 = "tests/vst/test_a.py::test_one"
T2 = "tests/vst/test_a.py::test_two"


def diff_for(*paths: str) -> bytes:
    return "".join(
        f"diff --git a/{p} b/{p}\nindex 1111111..2222222 100644\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-a\n+b\n"
        for p in paths).encode("utf-8")


PATHS = ["docs/a.md", "src/app.py"]
DIFF = diff_for(*PATHS)
DIFF_SHA = hashlib.sha256(DIFF).hexdigest()
# sha256 of the UTF-8 text ["docs/a.md","src/app.py"] (sorted paths, compact JSON), computed once with plain hashlib
PATHS_SHA_LITERAL = "f71a2128e164fd4c08b3f50cf6520b5b839a6d22dfa311c431dfb6796c1f6642"


def canon_sha(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def paths_sha(paths) -> str:
    """The expected changed-paths digest, restated here: sha256 of the compact JSON of the sorted paths."""
    return canon_sha(sorted(paths))


PATHS_SHA = paths_sha(PATHS)


def tests_ok():
    return [
        {"test_id": T1, "status": "PASS", "evidence_sha256": EVID, "head": HEAD},
        {"test_id": T2, "status": "PASS", "evidence_sha256": EVID2, "head": HEAD},
    ]


def not_run_record(test_id="t-skip", status="NOT_RUN", **extra):
    return dict({"test_id": test_id, "status": status, "evidence_sha256": None, "head": None}, **extra)


def review_ok(**over):
    doc = {
        "verdict": "CLEAN", "reasons": [], "iteration_count": 1,
        "iterations": [{
            "local_index": 1, "iteration_index": 1, "step_id": "rl-a1-i1", "iteration_id": "it-1",
            "iteration_of": None, "head": HEAD, "findings_count": 0, "findings": [],
            "finding_set_sha256": "f" * 64, "coverage": ["g2.python-rules", "g3.extra"], "missing_coverage": [],
            "verdict": "CLEAN", "reasons": [], "truncated": False, "replayed": False,
            "started_at": 1.0, "finished_at": 2.0}],
        "story_id": STORY, "attempt_no": 1, "declared_coverage": list(COVERAGE), "cap_requested": 3,
        "cap_effective": 3, "cap_clamped": False, "final_head": HEAD, "submit_calls": 1, "fixer_calls": 0,
        "gates": [], "replayed": False, "changed_paths_sha256": PATHS_SHA,
    }
    doc.update(over)
    return doc


def review_at(head):
    review = review_ok(final_head=head)
    review["iterations"][0]["head"] = head
    return review


def receipts_ok():
    return [{"receipt_id": "rcpt-1", "head": HEAD, "receipt_sha256": RECEIPT_SHA, "receipt_type": "StaticAnalysis",
             "result": "PASS"}]


def proof_ok(head=HEAD, **status_over):
    statuses = {
        "worktree_separate_from_main_checkout": "VERIFIED", "base_commit_pinned": "CALLER_ASSERTED",
        "worktree_head_matches_candidate": "CALLER_ASSERTED", "network_flag_not_requested": "CALLER_ASSERTED",
        "paths_normalized": "VERIFIED", "link_and_reparse_point_check_on_changed_paths": "VERIFIED",
    }
    statuses.update(status_over)
    props = [{"property": name, "status": statuses[name], "detail": "checked"} for name in wg.REQUIRED_PROPERTIES]
    props += [{"property": name, "status": "NOT_VERIFIED", "detail": reason}
              for name, reason in wg.NOT_VERIFIED_PROPERTIES.items()]
    return {"schema": wg.PROOF_SCHEMA, "isolation_mode": wg.ISOLATION_MODE, "worktree_head_reported": ascii(head),
            "candidate_head": ascii(head), "properties": props}


def share_ok(**over):
    doc = {
        "schema": RUN_RECORD_SCHEMA, "verdict": "ACCEPTED", "stage": "done", "worktree_state": "written",
        "report_sha256": "1" * 64, "candidate_head": HEAD, "diff_sha256": DIFF_SHA, "partial": False,
        "post_materialize_verified": True, "patched_paths": ["src/app.py"], "no_patch_paths": [], "applied": True,
        "attempted_proposal_hunks": {}, "attempted_proposal_lines": 0, "proposal_lines": 6, "model_lines": 2,
        "total_lines": 8, "proposal_fraction": 0.75, "model_fraction": 0.25, "files_touched_by_both": [],
        "model_only_paths": ["docs/a.md"], "overrides": [],
    }
    doc.update(over)
    return doc


def args(**over):
    base = dict(
        story_id=STORY, base_head=BASE, head=HEAD, diff_bytes=DIFF, diff_sha256=DIFF_SHA, changed_paths=list(PATHS),
        test_evidence=tests_ok(), required_test_ids=[T1, T2], review_results=review_ok(), receipts=receipts_ok(),
        isolation_proof=proof_ok(), patch_origin_share=share_ok(), now=NOW,
        declared_limits=["signatures: not verified here"])
    base.update(over)
    if "review_results" not in over and "changed_paths" in over:
        # the review of a differently declared path set carries that set's digest, unless a test says otherwise
        try:
            base["review_results"] = review_ok(changed_paths_sha256=paths_sha(over["changed_paths"]))
        except TypeError:
            pass
    return base


def build(**over):
    return fp.build_final_package(**args(**over))


def codes(result):
    return [code for code, _ in result.reasons]


def detail(result, code):
    return " ".join(d for c, d in result.reasons if c == code)


def verify(result, head=HEAD, diff=DIFF_SHA, package=None, sha=None):
    return fp.verify_package_current(result.package if package is None else package, head, diff,
                                     result.package_sha256 if sha is None else sha)


# ----------------------------------------------------------------------------- READY
def test_ready_on_consistent_input_with_exact_fields():
    result = build()
    assert result.verdict == fp.READY and result.reasons == () and result.ready
    pkg = result.package
    assert pkg["schema"] == "vst-final-package-v1"
    assert (pkg["story_id"], pkg["head"], pkg["base_head"], pkg["valid_for_head"], pkg["created_at"]) == (
        STORY, HEAD, BASE, HEAD, NOW)
    assert pkg["diff"]["sha256"] == DIFF_SHA and pkg["diff"]["bytes"] == len(DIFF)
    assert pkg["diff"]["changed_paths"] == PATHS and pkg["diff"]["path_count"] == 2 and pkg["diff"]["renames"] == []
    assert pkg["tests"]["passed"] == [T1, T2] and pkg["tests"]["required_test_ids"] == [T1, T2]
    assert pkg["tests"]["failed"] == [] and pkg["not_run"] == [] and pkg["tests"]["not_run"] == []
    assert pkg["tests"]["counts"] == {"PASS": 2, "FAIL": 0, "NOT_RUN": 0, "SKIPPED": 0}
    assert pkg["review"]["verdict"] == "CLEAN" and pkg["review"]["final_head"] == HEAD
    assert pkg["review"]["replayed"] is False and pkg["review"]["iteration_count"] == 1
    assert pkg["review"]["result_sha256"] == canon_sha(review_ok())
    assert pkg["review"]["changed_paths_sha256"] == PATHS_SHA == PATHS_SHA_LITERAL
    assert pkg["diff"]["changed_paths_sha256"] == PATHS_SHA_LITERAL
    assert pkg["receipts"] == [{"receipt_id": "rcpt-1", "head": HEAD, "receipt_sha256": RECEIPT_SHA,
                                "receipt_type": "StaticAnalysis", "result": "PASS"}]
    assert pkg["isolation"]["proof_sha256"] == canon_sha(proof_ok())
    assert pkg["patch_origin_share"]["proposal_fraction"] == 0.75
    assert pkg["evidence_digests"] == {
        "diff_sha256": DIFF_SHA, "tests": {T1: EVID, T2: EVID2},
        "review_result_sha256": canon_sha(review_ok()), "receipts": {"rcpt-1": RECEIPT_SHA},
        "isolation_proof_sha256": canon_sha(proof_ok()), "patch_origin_share_sha256": canon_sha(share_ok())}
    assert pkg["declared_limits"] == ["signatures: not verified here"]
    assert any("worktree_head_matches_candidate: CALLER_ASSERTED" in item for item in pkg["derived_limits"])
    assert any("os_sandbox: NOT_VERIFIED" in item for item in pkg["derived_limits"])
    assert result.package_sha256 == canon_sha(pkg)


def test_share_and_receipts_may_be_absent_and_are_declared_as_such():
    result = build(patch_origin_share=None, receipts=[])
    assert result.ready
    assert result.package["patch_origin_share"] is None
    assert result.package["evidence_digests"]["patch_origin_share_sha256"] is None
    assert "receipts: none were supplied" in result.package["derived_limits"]
    assert "patch_origin_share: no run record was supplied" in result.package["derived_limits"]


def test_isolation_proof_head_may_be_the_plain_head():
    proof = proof_ok()
    proof["candidate_head"] = HEAD
    assert build(isolation_proof=proof).ready


def test_rename_only_diff_end_to_end():
    text = ("diff --git a/old/name.py b/new/name.py\nsimilarity index 100%\nrename from old/name.py\n"
            "rename to new/name.py\n").encode()
    sha = hashlib.sha256(text).hexdigest()
    result = build(diff_bytes=text, diff_sha256=sha, changed_paths=["new/name.py", "old/name.py"],
                   patch_origin_share=share_ok(diff_sha256=sha))
    assert result.ready
    assert result.package["diff"]["changed_paths"] == ["new/name.py", "old/name.py"]
    assert result.package["diff"]["renames"] == [["old/name.py", "new/name.py"]]
    assert "- rename: old/name.py -> new/name.py" in fp.render_scope_note(result.package)
    assert codes(build(diff_bytes=text, diff_sha256=sha, changed_paths=["new/name.py"],
                       patch_origin_share=share_ok(diff_sha256=sha))) == [fp.PATHS_UNDERSTATED]


def test_identifiers_are_not_secret_scanned_but_validated_by_shape():
    token_id = "tests/vst/test_token_validation.py::test_x"
    param_id = "tests/x.py::test_a[some case-1]"
    path = "tools/uc/secret_patterns.py"
    text = diff_for(path)
    sha = hashlib.sha256(text).hexdigest()
    records = [{"test_id": token_id, "status": "PASS", "evidence_sha256": EVID, "head": HEAD},
               {"test_id": param_id, "status": "PASS", "evidence_sha256": EVID2, "head": HEAD}]
    result = build(story_id="token_validation-1",
                   review_results=review_ok(story_id="token_validation-1", changed_paths_sha256=paths_sha([path])),
                   test_evidence=records, required_test_ids=[token_id, param_id], diff_bytes=text, diff_sha256=sha,
                   changed_paths=[path], patch_origin_share=share_ok(diff_sha256=sha))
    assert result.verdict == fp.READY, result.reasons
    assert result.package["tests"]["passed"] == sorted([token_id, param_id])


# ----------------------------------------------------------------------------- stale evidence
@pytest.mark.parametrize("name, over, item", [
    ("test", dict(test_evidence=[dict(tests_ok()[0], head=OTHER), tests_ok()[1]]), f"test:{T1}"),
    ("review final_head", dict(review_results=review_ok(final_head=OTHER)), "review_results.final_head"),
    ("review last iteration", None, "review_results.iterations[-1].head"),
    ("receipt", dict(receipts=[dict(receipts_ok()[0], head=OTHER)]), "receipt:rcpt-1"),
    ("proof", dict(isolation_proof=proof_ok(head=OTHER)), "isolation_proof.candidate_head"),
    ("share", dict(patch_origin_share=share_ok(candidate_head=OTHER)), "patch_origin_share.candidate_head"),
    ("share missing head", dict(patch_origin_share=share_ok(candidate_head=None)), "patch_origin_share.candidate_head"),
])
def test_stale_item_is_refused_and_named(name, over, item):
    if over is None:
        review = review_ok()
        review["iterations"][0]["head"] = OTHER
        over = dict(review_results=review)
    result = build(**over)
    assert result.verdict == fp.REFUSED and result.package is None and result.package_sha256 is None
    assert codes(result) == [fp.STALE_EVIDENCE]
    assert item in detail(result, fp.STALE_EVIDENCE)


def test_every_stale_item_is_listed_not_only_the_first():
    result = build(test_evidence=[dict(tests_ok()[0], head=OTHER), dict(tests_ok()[1], head=OTHER)],
                   receipts=[dict(receipts_ok()[0], head=OTHER)])
    text = detail(result, fp.STALE_EVIDENCE)
    assert "test_one" in text and "test_two" in text and "rcpt-1" in text


# ----------------------------------------------------------------------------- diff
def test_diff_bytes_that_do_not_match_the_recorded_digest_are_refused():
    result = build(diff_sha256="0" * 64)
    assert result.verdict == fp.REFUSED and fp.DIFF_HASH_MISMATCH in codes(result)


def test_changed_diff_bytes_with_the_old_digest_are_refused_with_one_reason():
    result = build(diff_bytes=DIFF.replace(b"+b", b"+c"))
    assert result.verdict == fp.REFUSED and result.reasons == (
        (fp.DIFF_HASH_MISMATCH, "diff_bytes do not hash to the recorded diff digest"),)
    unparsable_and_wrong = build(diff_bytes=b"not a diff\n")
    assert unparsable_and_wrong.verdict == fp.REFUSED
    assert codes(unparsable_and_wrong) == [fp.DIFF_HASH_MISMATCH, fp.DIFF_UNPARSABLE]


def test_share_record_with_another_diff_digest_is_refused():
    result = build(patch_origin_share=share_ok(diff_sha256="9" * 64))
    assert codes(result) == [fp.DIFF_HASH_MISMATCH]
    assert "patch_origin_share" in detail(result, fp.DIFF_HASH_MISMATCH)


def test_understated_changed_paths_are_refused():
    result = build(changed_paths=["src/app.py"])
    assert result.verdict == fp.REFUSED and codes(result) == [fp.PATHS_UNDERSTATED]
    assert "docs/a.md" in detail(result, fp.PATHS_UNDERSTATED)


def test_extra_changed_paths_are_refused():
    result = build(changed_paths=PATHS + ["src/other.py"])
    assert result.verdict == fp.REFUSED and codes(result) == [fp.PATHS_EXTRA]
    assert "src/other.py" in detail(result, fp.PATHS_EXTRA)


def test_path_hazard_is_refused():
    bad = "src/a:stream.py"
    result = build(diff_bytes=diff_for(bad), diff_sha256=hashlib.sha256(diff_for(bad)).hexdigest(),
                   changed_paths=[bad])
    assert fp.PATH_HAZARD in codes(result)


@pytest.mark.parametrize("bad", ["src/`x`.py", "src/a\nb.py"])
def test_path_with_backtick_or_newline_is_blocked(bad):
    result = build(changed_paths=[bad])
    assert result.verdict == fp.BLOCKED and codes(result) == [fp.BAD_INPUT]


def test_backtick_path_in_the_diff_is_a_hazard():
    bad = "src/`x`.py"
    text = diff_for(bad)
    sha = hashlib.sha256(text).hexdigest()
    result = build(diff_bytes=text, diff_sha256=sha, changed_paths=["src/ok.py"],
                   patch_origin_share=share_ok(diff_sha256=sha))
    assert fp.PATH_HAZARD in codes(result)


def test_symlink_mode_is_refused():
    text = ("diff --git a/ln b/ln\nnew file mode 120000\nindex 0000000..2222222\n--- /dev/null\n+++ b/ln\n"
            "@@ -0,0 +1 @@\n+target\n").encode()
    result = build(diff_bytes=text, diff_sha256=hashlib.sha256(text).hexdigest(), changed_paths=["ln"])
    assert fp.DIFF_SPECIAL_MODE in codes(result)


def test_unparsable_diff_is_blocked():
    junk = b"this is not a diff\n"
    result = build(diff_bytes=junk, diff_sha256=hashlib.sha256(junk).hexdigest())
    assert result.verdict == fp.BLOCKED and codes(result) == [fp.DIFF_UNPARSABLE]


# ----------------------------------------------------------------------------- review
def test_blocked_review_is_refused_with_its_reason_codes():
    review = review_ok(verdict="BLOCKED", reasons=[{"code": "ITERATION_CAP", "detail": "cap"}])
    result = build(review_results=review)
    assert result.verdict == fp.REFUSED and fp.REVIEW_NOT_CLEAN in codes(result)
    assert "ITERATION_CAP" in detail(result, fp.REVIEW_NOT_CLEAN)


def test_clean_claim_without_proof_is_refused():
    def with_last(**fields):
        review = review_ok()
        review["iterations"][0].update(fields)
        return review

    assert codes(build(review_results=with_last(findings_count=1))) == [fp.REVIEW_INCONSISTENT]
    assert codes(build(review_results=with_last(coverage=[]))) == [fp.REVIEW_INCONSISTENT]
    assert codes(build(review_results=with_last(findings=[{"rule_id": "r"}]))) == [fp.REVIEW_INCONSISTENT]
    assert codes(build(review_results=with_last(truncated=True))) == [fp.REVIEW_INCONSISTENT]
    assert codes(build(review_results=review_ok(iteration_count=2))) == [fp.REVIEW_INCONSISTENT]
    assert codes(build(review_results=review_ok(iterations=[]))) == [fp.REVIEW_INCONSISTENT]
    assert codes(build(review_results=review_ok(declared_coverage=[]))) == [fp.REVIEW_INCONSISTENT]
    missing_count = review_ok()
    del missing_count["iteration_count"]
    assert codes(build(review_results=missing_count)) == [fp.REVIEW_INCONSISTENT]


def test_replayed_review_is_refused_unless_store_facts_are_confirmed():
    result = build(review_results=review_ok(replayed=True))
    assert result.verdict == fp.REFUSED and codes(result) == [fp.REVIEW_REPLAYED]
    confirmed = build(review_results=review_ok(replayed=True), replay_store_verified=True)
    assert confirmed.ready
    assert confirmed.package["review"]["replayed"] is True and confirmed.package["review"]["replay_store_verified"] is True
    assert any("replayed" in item for item in confirmed.package["derived_limits"])


@pytest.mark.parametrize("story", ["other-story", None])
def test_review_for_another_or_no_story_is_refused(story):
    assert codes(build(review_results=review_ok(story_id=story))) == [fp.REVIEW_STORY_MISMATCH]
    no_key = review_ok()
    del no_key["story_id"]
    assert codes(build(review_results=no_key)) == [fp.REVIEW_STORY_MISMATCH]


def test_known_digest_of_a_tiny_path_list_matches_the_helper_formula():
    assert paths_sha(["src/app.py", "docs/a.md"]) == PATHS_SHA_LITERAL        # the formula sorts
    assert paths_sha(["a.py"]) == "af814d93ee8ccb244bb6b153bb98b03c31e6bf49933db489abd21730c75d9c80"


@pytest.mark.parametrize("value", [
    "0" * 64,                      # well formed but another digest
    paths_sha(["docs/a.md"]),      # digest of a smaller path set
    paths_sha(PATHS + ["x.py"]),   # digest of a larger path set
])
def test_review_for_other_paths_is_refused(value):
    result = build(review_results=review_ok(changed_paths_sha256=value))
    assert result.verdict == fp.REFUSED and codes(result) == [fp.REVIEW_PATHS_MISMATCH]
    assert result.package is None and result.package_sha256 is None
    assert "differs" in detail(result, fp.REVIEW_PATHS_MISMATCH)


@pytest.mark.parametrize("value", [None, "", "xyz", "A" * 64, PATHS_SHA[:63], PATHS_SHA + "0", 5, ["x"]])
def test_review_with_a_malformed_paths_digest_is_refused(value):
    result = build(review_results=review_ok(changed_paths_sha256=value))
    assert result.verdict == fp.REFUSED and codes(result) == [fp.REVIEW_PATHS_MISMATCH]
    assert "missing or malformed" in detail(result, fp.REVIEW_PATHS_MISMATCH)


def test_review_without_a_paths_digest_is_refused_not_skipped():
    review = review_ok()
    del review["changed_paths_sha256"]
    result = build(review_results=review)
    assert result.verdict == fp.REFUSED and codes(result) == [fp.REVIEW_PATHS_MISMATCH]
    assert result.package is None


def test_review_with_the_matching_paths_digest_is_ready_and_the_package_records_it():
    result = build(review_results=review_ok(changed_paths_sha256=PATHS_SHA_LITERAL))
    assert result.ready
    assert result.package["review"]["changed_paths_sha256"] == PATHS_SHA_LITERAL
    assert result.package["diff"]["changed_paths_sha256"] == PATHS_SHA_LITERAL


def test_the_paths_digest_does_not_depend_on_the_order_of_changed_paths():
    forward = build()
    reordered = build(changed_paths=list(reversed(PATHS)))
    assert forward.ready and reordered.ready
    assert reordered.package["review"]["changed_paths_sha256"] == PATHS_SHA_LITERAL
    assert reordered.package["diff"]["changed_paths"] == PATHS
    assert reordered.package_sha256 == forward.package_sha256


def test_a_paths_digest_mismatch_is_listed_next_to_other_refusals():
    result = build(review_results=review_ok(changed_paths_sha256="0" * 64, final_head=OTHER))
    assert set(codes(result)) == {fp.REVIEW_PATHS_MISMATCH, fp.STALE_EVIDENCE}


def test_the_scope_note_lists_the_reviewed_paths_digest():
    note = fp.render_scope_note(build().package)
    assert f"- Reviewed paths sha256: `{PATHS_SHA_LITERAL}`" in note


# ----------------------------------------------------------------------------- tests
def test_failed_test_is_refused_and_listed():
    records = tests_ok() + [{"test_id": "tests/vst/test_b.py::test_bad", "status": "FAIL", "evidence_sha256": EVID,
                             "head": HEAD}]
    result = build(test_evidence=records)
    assert result.verdict == fp.REFUSED and codes(result) == [fp.TEST_FAILED]
    assert "test_bad" in detail(result, fp.TEST_FAILED)


def test_not_run_required_test_without_acknowledgement_is_refused():
    result = build(test_evidence=tests_ok() + [not_run_record()], required_test_ids=[T1, T2, "t-skip"])
    assert result.verdict == fp.REFUSED and codes(result) == [fp.NOT_RUN_UNACKNOWLEDGED]
    assert "t-skip" in detail(result, fp.NOT_RUN_UNACKNOWLEDGED)
    skipped = tests_ok() + [not_run_record(status="SKIPPED")]
    assert codes(build(test_evidence=skipped, required_test_ids=[T1, T2, "t-skip"])) == [fp.NOT_RUN_UNACKNOWLEDGED]


def test_acknowledged_required_not_run_is_ready_and_listed_verbatim():
    records = tests_ok() + [not_run_record(reason="operator banned the run")]
    result = build(test_evidence=records, required_test_ids=[T1, T2, "t-skip"],
                   allow_not_run={"t-skip": "operator accepted: banned run"})
    assert result.ready
    expected = {"test_id": "t-skip", "status": "NOT_RUN", "required": True, "reason": "operator banned the run",
                "acknowledged_reason": "operator accepted: banned run"}
    assert result.package["not_run"] == [expected] and result.package["tests"]["not_run"] == [expected]
    assert "t-skip" not in result.package["tests"]["passed"]
    assert result.package["tests"]["counts"]["PASS"] == 2 and result.package["tests"]["counts"]["NOT_RUN"] == 1
    assert result.package["allow_not_run"] == {"t-skip": "operator accepted: banned run"}
    assert any("NOT_RUN: t-skip" in item for item in result.package["derived_limits"])


def test_informational_not_run_outside_the_required_list_is_listed_without_acknowledgement():
    result = build(test_evidence=tests_ok() + [not_run_record("t-opt")])
    assert result.ready and result.package["not_run"][0]["test_id"] == "t-opt"
    assert result.package["not_run"][0]["required"] is False
    assert result.package["not_run"][0]["acknowledged_reason"] is None


def test_record_cannot_downgrade_its_own_required_flag():
    result = build(test_evidence=tests_ok() + [not_run_record(required=False)], required_test_ids=[T1, T2, "t-skip"])
    assert result.verdict == fp.BLOCKED and codes(result) == [fp.BAD_INPUT]
    assert build(test_evidence=[dict(tests_ok()[0], required=False), tests_ok()[1]]).verdict == fp.BLOCKED


def test_required_test_without_a_record_is_refused():
    result = build(required_test_ids=[T1, T2, "tests/x.py::missing"])
    assert result.verdict == fp.REFUSED and codes(result) == [fp.MISSING_REQUIRED_TEST]
    assert "tests/x.py::missing" in detail(result, fp.MISSING_REQUIRED_TEST)


def test_no_records_means_missing_required_tests_and_no_pass_evidence():
    assert codes(build(test_evidence=[])) == [fp.MISSING_REQUIRED_TEST, fp.NO_PASS_EVIDENCE]


def test_all_required_tests_not_run_and_acknowledged_is_still_refused_for_no_pass_evidence():
    result = build(test_evidence=[not_run_record("t1")], required_test_ids=["t1"], allow_not_run={"t1": "banned"})
    assert result.verdict == fp.REFUSED and codes(result) == [fp.NO_PASS_EVIDENCE]


def test_required_test_ids_must_be_a_non_empty_list_of_unique_ids():
    for bad in ([], "x", None, [T1, T1], [""], [1]):
        result = build(required_test_ids=bad)
        assert result.verdict == fp.BLOCKED and codes(result) == [fp.BAD_INPUT]


def test_allow_not_run_for_a_test_that_ran_or_with_an_empty_reason_is_blocked():
    assert codes(build(allow_not_run={T1: "x"})) == [fp.BAD_INPUT]
    records = tests_ok() + [not_run_record()]
    assert codes(build(test_evidence=records, required_test_ids=[T1, T2, "t-skip"],
                       allow_not_run={"t-skip": ""})) == [fp.BAD_INPUT]


# ----------------------------------------------------------------------------- receipts, proof, share
@pytest.mark.parametrize("receipt", [
    dict(receipts_ok()[0], result="FAIL"), dict(receipts_ok()[0], result="pass"),
    {k: v for k, v in receipts_ok()[0].items() if k != "result"},
])
def test_receipt_result_must_be_exactly_pass(receipt):
    result = build(receipts=[receipt])
    assert result.verdict == fp.REFUSED and codes(result) == [fp.RECEIPT_NOT_PASS]
    assert "rcpt-1" in detail(result, fp.RECEIPT_NOT_PASS)
    if "result" not in receipt:
        assert "result missing" in detail(result, fp.RECEIPT_NOT_PASS)


def test_failed_isolation_property_is_refused():
    result = build(isolation_proof=proof_ok(network_flag_not_requested="FAILED"))
    assert fp.ISOLATION_FAILED in codes(result)
    assert "network_flag_not_requested" in detail(result, fp.ISOLATION_FAILED)


def test_promoted_isolation_property_is_refused_as_dishonest():
    result = build(isolation_proof=proof_ok(base_commit_pinned="VERIFIED"))
    assert fp.PROOF_DISHONEST in codes(result)
    proof = proof_ok()
    proof["properties"][-1]["status"] = "VERIFIED"  # a not-checked property promoted
    assert fp.PROOF_DISHONEST in codes(build(isolation_proof=proof))


def test_share_record_without_head_or_diff_digest_is_refused():
    result = build(patch_origin_share=share_ok(candidate_head=None, diff_sha256=None))
    assert codes(result) == [fp.DIFF_HASH_MISMATCH, fp.STALE_EVIDENCE] or codes(result) == [
        fp.STALE_EVIDENCE, fp.DIFF_HASH_MISMATCH]
    assert "patch_origin_share.diff_sha256" in detail(result, fp.DIFF_HASH_MISMATCH)


@pytest.mark.parametrize("over", [dict(verdict="REFUSED"), dict(applied=False), dict(partial=True)])
def test_share_record_that_is_not_an_accepted_complete_run_is_refused(over):
    result = build(patch_origin_share=share_ok(**over))
    assert result.verdict == fp.REFUSED and codes(result) == [fp.SHARE_NOT_ACCEPTED]


# ----------------------------------------------------------------------------- secrets
SECRET_ROWS = [
    ("test_evidence", lambda: dict(test_evidence=[dict(tests_ok()[0], reason="key sk_live_A1b2C3d4E5f6")]
                                   + tests_ok()[1:])),
    ("allow_not_run", lambda: dict(test_evidence=tests_ok() + [not_run_record("t1")],
                                   required_test_ids=[T1, T2, "t1"], allow_not_run={"t1": "password=hunter2hunter2"})),
    ("review_results", lambda: dict(review_results=review_ok(
        reasons=[{"code": "X", "detail": "ghp_abcdefghij1234"}]))),
    ("receipts", lambda: dict(receipts=[dict(receipts_ok()[0], receipt_type="AKIAABCDEFGH1234")])),
    ("isolation_proof", lambda: dict(isolation_proof=_proof_with_detail("password=abcdefgh1234"))),
    ("patch_origin_share", lambda: dict(patch_origin_share=share_ok(overrides=[{"reason": "api_key=abcdefgh12345"}]))),
    ("declared_limits", lambda: dict(declared_limits=["see -----BEGIN PRIVATE KEY"])),
]


def _proof_with_detail(text):
    proof = proof_ok()
    proof["properties"][0]["detail"] = text
    return proof


@pytest.mark.parametrize("where, make", SECRET_ROWS, ids=[row[0] for row in SECRET_ROWS])
def test_secret_in_free_text_is_refused_and_the_section_is_named(where, make):
    result = build(**make())
    assert result.verdict == fp.REFUSED and codes(result) == [fp.SECRET_IN_EVIDENCE]
    assert where in detail(result, fp.SECRET_IN_EVIDENCE)
    assert result.package is None
    assert "sk_live" not in str(result.reasons) and "hunter2" not in str(result.reasons)


def test_secret_wins_over_other_problems_and_is_never_echoed():
    result = build(head="xyz", declared_limits=["token=abcdefgh12345"])
    assert result.verdict == fp.REFUSED and codes(result) == [fp.SECRET_IN_EVIDENCE]
    assert "abcdefgh12345" not in str(result.reasons)


# ----------------------------------------------------------------------------- invalidation
def test_verify_package_current_same_head_and_diff_is_ok():
    result = build()
    assert verify(result) == (True, ())


def test_verify_package_current_new_head_is_not_ok():
    result = build()
    ok, reasons = verify(result, head=OTHER)
    assert ok is False and [c for c, _ in reasons] == [fp.HEAD_CHANGED]
    assert HEAD in reasons[0][1] and OTHER in reasons[0][1]


def test_verify_package_current_changed_diff_is_not_ok():
    ok, reasons = verify(build(), diff="7" * 64)
    assert ok is False and [c for c, _ in reasons] == [fp.DIFF_CHANGED]


def test_verify_package_current_new_head_and_diff_lists_both():
    ok, reasons = verify(build(), head=OTHER, diff="7" * 64)
    assert ok is False and [c for c, _ in reasons] == [fp.HEAD_CHANGED, fp.DIFF_CHANGED]


def test_verify_package_current_requires_the_package_digest_and_detects_tampering():
    result = build()
    for missing in (None, "", "short", 5):
        ok, reasons = fp.verify_package_current(result.package, HEAD, DIFF_SHA, missing)
        assert ok is False and [c for c, _ in reasons] == [fp.BAD_INPUT]
    with pytest.raises(TypeError):
        fp.verify_package_current(result.package, HEAD, DIFF_SHA)
    tampered = result.package
    tampered["tests"]["passed"].append("tests/x.py::forged")
    ok, reasons = verify(result, package=tampered)
    assert ok is False and [c for c, _ in reasons] == [fp.PACKAGE_TAMPERED]


@pytest.mark.parametrize("path", [("review", "changed_paths_sha256"), ("diff", "changed_paths_sha256")])
def test_verify_package_current_detects_a_tampered_paths_digest(path):
    package = build().package
    package[path[0]][path[1]] = "0" * 64
    # digest recomputed for the edited package: only the digest coherence can fail
    ok, reasons = fp.verify_package_current(package, HEAD, DIFF_SHA, canon_sha(package))
    assert ok is False and [c for c, _ in reasons] == [fp.PACKAGE_INCONSISTENT]
    assert ".".join(path) in reasons[0][1]
    # without recomputing, the package digest catches it as well
    result = build()
    stale = result.package
    stale[path[0]][path[1]] = "0" * 64
    ok, reasons = verify(result, package=stale)
    assert ok is False and fp.PACKAGE_TAMPERED in [c for c, _ in reasons]


def test_verify_package_current_detects_changed_paths_edited_without_their_digest():
    package = build().package
    package["diff"]["changed_paths"] = ["docs/a.md", "src/app.py", "src/extra.py"]
    ok, reasons = fp.verify_package_current(package, HEAD, DIFF_SHA, canon_sha(package))
    assert ok is False and [c for c, _ in reasons] == [fp.PACKAGE_INCONSISTENT, fp.PACKAGE_INCONSISTENT]


def test_verify_package_current_refuses_a_package_without_the_paths_digests():
    package = build().package
    del package["review"]["changed_paths_sha256"]
    del package["diff"]["changed_paths_sha256"]
    ok, reasons = fp.verify_package_current(package, HEAD, DIFF_SHA, canon_sha(package))
    assert ok is False and [c for c, _ in reasons] == [fp.PACKAGE_INCONSISTENT, fp.PACKAGE_INCONSISTENT]


@pytest.mark.parametrize("path, item", [
    (("review", "last_iteration", "head"), "review.last_iteration.head"),
    (("review", "final_head"), "review.final_head"),
    (("patch_origin_share", "candidate_head"), "patch_origin_share.candidate_head"),
    (("isolation", "candidate_head"), "isolation.candidate_head"),
])
def test_verify_package_current_checks_every_embedded_head(path, item):
    package = build().package
    node = package
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = OTHER
    # the digest is recomputed for the edited package so that only the head coherence can fail
    ok, reasons = fp.verify_package_current(package, HEAD, DIFF_SHA, canon_sha(package))
    assert ok is False and [c for c, _ in reasons] == [fp.PACKAGE_INCONSISTENT]
    assert item in reasons[0][1]


def test_verify_package_current_refuses_a_ran_test_without_head_and_a_moved_receipt():
    package = build().package
    package["tests"]["records"][0]["head"] = None
    package["receipts"][0]["head"] = OTHER
    package["valid_for_head"] = OTHER
    ok, reasons = fp.verify_package_current(package, HEAD, DIFF_SHA, canon_sha(package))
    assert ok is False
    text = " ".join(d for _, d in reasons)
    assert {c for c, _ in reasons} == {fp.PACKAGE_INCONSISTENT, fp.HEAD_CHANGED}
    assert f"test:{T1}" in text and "receipt:rcpt-1" in text


def test_verify_package_current_rejects_foreign_objects_and_does_not_mutate():
    for junk in (None, [], {}, {"schema": "other"}, "text"):
        assert fp.verify_package_current(junk, HEAD, DIFF_SHA, "0" * 64)[0] is False
    result = build()
    assert fp.verify_package_current(result.package, "short", DIFF_SHA, result.package_sha256)[0] is False
    package = result.package
    before = copy.deepcopy(package)
    fp.verify_package_current(package, OTHER, "7" * 64, result.package_sha256)
    assert package == before


# ----------------------------------------------------------------------------- determinism, mutation, immutability
def test_package_sha256_is_deterministic_and_input_order_independent():
    first = build()
    second = build(test_evidence=list(reversed(tests_ok())), required_test_ids=[T2, T1], receipts=receipts_ok())
    assert first.package_sha256 == second.package_sha256 and first.package == second.package
    assert first.package_sha256 == canon_sha(first.package)


def test_package_sha256_changes_when_an_evidence_digest_changes():
    base = build().package_sha256
    changed_test = build(test_evidence=[dict(tests_ok()[0], evidence_sha256="1" * 64), tests_ok()[1]]).package_sha256
    changed_receipt = build(receipts=[dict(receipts_ok()[0], receipt_sha256="2" * 64)]).package_sha256
    changed_review = build(review_results=review_ok(cap_requested=4)).package_sha256
    changed_now = build(now="2026-11-11T10:00:01Z").package_sha256
    changed_head = build(head=OTHER, test_evidence=[dict(r, head=OTHER) for r in tests_ok()],
                         review_results=review_at(OTHER), receipts=[dict(receipts_ok()[0], head=OTHER)],
                         isolation_proof=proof_ok(head=OTHER), patch_origin_share=share_ok(candidate_head=OTHER)
                         ).package_sha256
    assert len({base, changed_test, changed_receipt, changed_review, changed_now, changed_head}) == 6


def test_inputs_are_not_mutated():
    kwargs = args(test_evidence=tests_ok() + [not_run_record("t1")], allow_not_run={"t1": "banned"})
    before = copy.deepcopy(kwargs)
    result = fp.build_final_package(**kwargs)
    assert result.ready and kwargs == before
    refused = dict(kwargs, head=OTHER)
    before_refused = copy.deepcopy(refused)
    assert fp.build_final_package(**refused).verdict == fp.REFUSED and refused == before_refused


def test_same_input_twice_gives_the_same_result():
    assert build().to_dict() == build().to_dict()


def test_result_is_immutable_and_has_no_aliasing():
    result = build(test_evidence=tests_ok() + [not_run_record("t1")], allow_not_run={"t1": "banned"})
    first = result.package
    assert first["tests"]["not_run"] == first["not_run"] and first["tests"]["not_run"] is not first["not_run"]
    first["tests"]["passed"].append("x")
    first["not_run"].append({"forged": True})
    first["head"] = OTHER
    fresh = result.package
    assert fresh is not first and canon_sha(fresh) == result.package_sha256
    assert fresh["head"] == HEAD and fresh["tests"]["passed"] == [T1, T2] and len(fresh["not_run"]) == 1
    with pytest.raises(AttributeError):
        result.verdict = fp.REFUSED
    with pytest.raises(AttributeError):
        result.package = {}


# ----------------------------------------------------------------------------- render
def _note_package(**over):
    records = tests_ok() + [not_run_record(reason="operator banned the run")]
    kwargs = dict(test_evidence=records, required_test_ids=[T1, T2, "t-skip"],
                  allow_not_run={"t-skip": "operator accepted"},
                  declared_limits=["unsigned facts: receipts are not signature checked"])
    kwargs.update(over)
    result = build(**kwargs)
    assert result.ready, result.reasons
    return result.package


def test_render_is_deterministic_and_states_the_data():
    package = _note_package()
    before = copy.deepcopy(package)
    note = fp.render_scope_note(package)
    assert note == fp.render_scope_note(copy.deepcopy(package)) and package == before
    assert note.endswith("\n") and "\r" not in note
    assert HEAD in note and BASE in note and DIFF_SHA in note and NOW in note
    assert "- docs/a.md" in note and "- src/app.py" in note
    assert "- unsigned facts: receipts are not signature checked" in note
    assert "a new commit invalidates it" in note
    assert "NOT_RUN 1" in note and "- t-skip: NOT_RUN" in note


def test_render_never_claims_a_pass_for_a_not_run_test():
    note = fp.render_scope_note(_note_package())
    assert "passed" not in note.lower()
    for line in note.splitlines():
        if "t-skip" in line:
            assert "pass" not in line.lower()
    assert "PASS record: " + fp.escape_markdown(T1) in note


def test_render_escapes_hostile_evidence_text():
    hostile = "# heading `code` | pipe [x](http://e) <b>x</b>"
    note = fp.render_scope_note(_note_package(declared_limits=[hostile]))
    assert r"- \# heading \`code\` \| pipe \[x\](http://e) \<b\>x\</b\>" in note
    assert not any(line.startswith("#") and "heading" in line for line in note.splitlines())
    forged = _note_package()
    forged["declared_limits"] = ["a\n# injected\r\n- fake item"]
    forged["not_run"][0]["acknowledged_reason"] = "ok\n## Receipts"
    note = fp.render_scope_note(forged)
    assert "\n# injected" not in note and not any(line.startswith("# injected") for line in note.splitlines())
    assert "- a # injected - fake item" in note
    assert note.count("\n## Receipts") == 1


def test_escape_markdown_unit_cases():
    assert fp.escape_markdown("a\nb\tc") == "a b c"
    assert fp.escape_markdown("1. x") == "1\\. x"
    assert fp.escape_markdown("> q") == "\\> q"
    assert fp.escape_markdown("- x") == "\\- x"
    assert fp.escape_markdown("a_b*c") == "a\\_b\\*c"
    assert fp.escape_markdown("a\\b") == "a\\\\b"
    assert fp.escape_markdown("<i>&") == "\\<i\\>\\&"
    assert fp.escape_markdown("plain/path.py") == "plain/path.py"


def test_render_rejects_a_foreign_object():
    for junk in (None, {}, {"schema": "other"}, []):
        with pytest.raises(ValueError):
            fp.render_scope_note(junk)
    with pytest.raises(ValueError):
        fp.render_scope_note({"schema": fp.PACKAGE_SCHEMA})


# ----------------------------------------------------------------------------- caps and malformed input
def test_size_caps_are_blocked():
    many = [{"test_id": f"t{i}", "status": "PASS", "evidence_sha256": EVID, "head": HEAD}
            for i in range(fp.MAX_TESTS + 1)]
    assert codes(build(test_evidence=many)) == [fp.SIZE_CAP]
    assert build(test_evidence=many).verdict == fp.BLOCKED
    assert codes(build(declared_limits=["x" * (fp.MAX_TEXT + 1)])) == [fp.SIZE_CAP]
    assert codes(build(declared_limits=["x"] * (fp.MAX_LIMITS + 1))) == [fp.SIZE_CAP]
    too_many = [f"f{i}.py" for i in range(wg.MAX_CHANGED_PATHS + 1)]
    assert codes(build(changed_paths=too_many)) == [fp.SIZE_CAP]
    big = b"x" * (wg.MAX_DIFF_BYTES + 1)
    over = build(diff_bytes=big, diff_sha256=hashlib.sha256(big).hexdigest())
    assert over.verdict == fp.BLOCKED and codes(over) == [fp.DIFF_UNPARSABLE]


def test_package_over_the_byte_cap_is_blocked(monkeypatch):
    monkeypatch.setattr(fp, "MAX_PACKAGE_BYTES", 100)
    result = build()
    assert result.verdict == fp.BLOCKED and codes(result) == [fp.PACKAGE_TOO_LARGE] and result.package is None


@pytest.mark.parametrize("over", [
    dict(head="xyz"), dict(base_head=HEAD), dict(base_head="G" * 40), dict(story_id=""), dict(story_id="a b"),
    dict(now="2026-11-11 10:00:00"), dict(now=None), dict(diff_bytes="text"), dict(diff_sha256="abc"),
    dict(changed_paths=[]), dict(changed_paths=["a", "a"]), dict(changed_paths=[1]), dict(changed_paths="src/app.py"),
    dict(test_evidence="x"), dict(test_evidence=[{"test_id": "t", "status": "PASS"}]),
    dict(test_evidence=[dict(tests_ok()[0], extra=1)]),
    dict(test_evidence=[dict(tests_ok()[0], status="MAYBE")]),
    dict(test_evidence=[dict(tests_ok()[0], evidence_sha256=None)]),
    dict(test_evidence=[dict(tests_ok()[0], head=None)]),
    dict(test_evidence=[tests_ok()[0], tests_ok()[0]]),
    dict(test_evidence=[dict(tests_ok()[0], test_id="bad\nid")]),
    dict(review_results=None), dict(review_results=review_ok(verdict="MAYBE")),
    dict(review_results=review_ok(replayed="no")), dict(review_results=review_ok(iterations="x")),
    dict(review_results=review_ok(final_head="short")), dict(review_results=review_ok(story_id=5)),
    dict(receipts="x"), dict(receipts=[{"receipt_id": "r"}]), dict(receipts=[receipts_ok()[0], receipts_ok()[0]]),
    dict(isolation_proof=None), dict(isolation_proof=dict(proof_ok(), schema="other")),
    dict(isolation_proof=dict(proof_ok(), properties="x")),
    dict(patch_origin_share={"schema": "other"}), dict(patch_origin_share=share_ok(applied="yes")),
    dict(patch_origin_share=share_ok(proposal_lines=-1)),
    dict(patch_origin_share=share_ok(proposal_fraction=float("nan"))),
    dict(patch_origin_share=share_ok(files_touched_by_both=[1])),
    dict(patch_origin_share=share_ok(model_only_paths=["a`b"])),
    dict(patch_origin_share=share_ok(overrides=["x"])),
    dict(patch_origin_share=share_ok(overrides=[{"reason": 5}])),
    dict(allow_not_run=["t"]), dict(declared_limits="text"), dict(declared_limits=[1]), dict(declared_limits=["a\nb"]),
    dict(replay_store_verified="yes"),
])
def test_malformed_input_is_blocked_without_a_package(over):
    result = build(**over)
    assert result.verdict == fp.BLOCKED and result.package is None and result.package_sha256 is None
    assert result.reasons and result.reasons[0][0] in (fp.BAD_INPUT, fp.SIZE_CAP)


def test_hostile_object_inputs_are_blocked_not_raised():
    class Boom:
        def __deepcopy__(self, memo):
            raise TypeError("no copy")

    assert build(test_evidence=Boom()).verdict == fp.BLOCKED
    deep = []
    node = deep
    for _ in range(5000):
        child = []
        node.append(child)
        node = child
    assert build(declared_limits=deep).verdict == fp.BLOCKED


def test_blocked_and_refused_results_cannot_carry_a_package():
    with pytest.raises(ValueError):
        fp.PackageResult(fp.READY, (), None, None)
    with pytest.raises(ValueError):
        fp.PackageResult(fp.REFUSED, (("X", "y"),), {"a": 1}, "0" * 64)
    with pytest.raises(ValueError):
        fp.PackageResult(fp.BLOCKED, (), None, None)
    with pytest.raises(ValueError):
        fp.PackageResult("MAYBE", (("X", "y"),), None, None)


def test_module_is_pure():
    import ast
    import pathlib

    source = pathlib.Path(fp.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0] if node.level == 0 else "." + (node.module or ""))
    forbidden = {"subprocess", "socket", "urllib", "http", "requests", "time", "datetime", "os", "sqlite3", "random"}
    assert not (imported & forbidden), imported & forbidden
