"""S4-F gate-check tests (plan E6, AC-14, AC-15).

ONE real end-to-end S4-B runner invocation builds a genuinely approvable baseline in a tiny
throw-away git repo (real lane record, real validate_registry, real stdout/stderr artifacts).
Every other case deep-copies that record/registry and mutates exactly one thing; the runner is
never re-run. The real repository lanes are never executed (the real committed records are only
read).
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_s4b_runner as s4b  # noqa: E402
from test_s4b_runner import deps, git, run_qa  # noqa: E402,F401  (deps is a session fixture)
from tools.qa import gate_check as gc  # noqa: E402
from tools.qa.registry import RegistryError, validate_registry  # noqa: E402
from tools.qa.report import set_normalized_digest  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
F = "tests/qa/test_s4_functional_a.py"
OK_SRC = "def test_ok():\n    assert True\n\n\ndef test_two():\n    assert 1 + 1 == 2\n"
ZERO = "0" * 64
GOOD = "ab" * 32


@pytest.fixture(scope="module")
def baseline(tmp_path_factory, deps):
    """The single end-to-end run: tiny repo, all functional selectors pass."""
    base = tmp_path_factory.mktemp("s4f")
    repo = s4b.build_template(base / "repo", {F: OK_SRC}, deps.lock_text).resolve()
    run = run_qa(repo, deps, "functional", run_id="s4f", proc_timeout=540)
    assert run.rc == 0, run.out + run.proc.stderr
    record = gc.select_record((repo / s4b.EVIDENCE / "functional.report.jsonl").read_bytes().splitlines())
    registry = validate_registry(repo)
    artifacts = {
        "stdout": (repo / s4b.EVIDENCE / "functional.stdout.txt").read_bytes(),
        "stderr": (repo / s4b.EVIDENCE / "functional.stderr.txt").read_bytes(),
    }
    head = git(repo, "rev-parse", "HEAD").strip()
    return {"record": record, "registry": registry, "artifacts": artifacts, "head": head, "run": run}


def check(baseline, mutate=None, *, registry=None, head=None, artifacts="default", rehash=False):
    record = copy.deepcopy(baseline["record"])
    if mutate is not None:
        mutate(record)
    if rehash:
        set_normalized_digest(record)
    arts = baseline["artifacts"] if artifacts == "default" else artifacts
    return gc.check_report(
        record, registry or baseline["registry"],
        expected_head=head or baseline["head"], artifact_bytes=arts,
    )


def assert_fires(result, *codes):
    assert result.verdict == gc.NON_APPROVING and not result.approvable
    for code in codes:
        assert code in result.codes(), (code, result.reasons)


def assert_only_schema(result):
    """A type-invalid record yields exactly one SCHEMA reason (the type pre-validation)."""
    assert result.verdict == gc.NON_APPROVING and not result.approvable
    assert [code for code, _ in result.reasons] == ["SCHEMA"], result.reasons


# ------------------------------------------------------------------ baseline


def test_baseline_real_runner_record_is_approvable_with_no_reasons(baseline):
    rec = baseline["record"]
    assert rec["result"] == "PASS" and rec["category"] == "functional" and rec["exit_code"] == 0
    assert len(rec["expected_test_ids"]) == 2 and rec["passed_test_ids"] == rec["expected_test_ids"]
    result = check(baseline)
    assert result.reasons == () and result.verdict == gc.APPROVABLE and result.approvable


def test_baseline_interpreter_absolute_executable_alone_is_not_secret_or_abs_path(baseline):
    rec = baseline["record"]
    assert rec["interpreter"]["executable"] == "C:/Python314/python.exe"  # absolute, allowed
    assert gc._secret_or_path_hits(rec) == []
    rec2 = copy.deepcopy(rec)
    rec2["interpreter"]["executable"] = "C:\\Python314\\python.exe"
    assert gc._secret_or_path_hits(rec2) == []
    assert check(baseline, lambda r: r["interpreter"].update(executable="C:/Python314/python.exe")).approvable


# ------------------------------------------------------------------ schema / category / profile


def test_schema_missing_key_and_wrong_version_and_non_object(baseline):
    def drop(r):
        del r["result"]
    assert_fires(check(baseline, drop), "SCHEMA")
    assert_fires(check(baseline, lambda r: r.update(schema_version=2)), "SCHEMA")
    assert_fires(check(baseline, lambda r: r.update(schema_version="3")), "SCHEMA")
    for bad in ([], "x", None, 3):
        res = gc.check_report(bad, baseline["registry"], expected_head=baseline["head"])
        assert_fires(res, "SCHEMA")


def test_unknown_category_and_unknown_profile(baseline):
    assert_fires(check(baseline, lambda r: r.update(category="nope")), "UNKNOWN_CATEGORY")
    assert_fires(check(baseline, lambda r: r.update(runtime_profile="mars")), "UNKNOWN_PROFILE")


def test_unsupported_category_status_in_registry(baseline):
    registry = copy.deepcopy(baseline["registry"])
    registry.data["categories"]["functional"]["status"] = "NOT_RUN"
    assert_fires(check(baseline, registry=registry), "UNSUPPORTED_CATEGORY")


def test_profile_not_executed(baseline):
    profile = baseline["record"]["runtime_profile"]
    assert_fires(check(baseline, lambda r: r["profile_status"].update({profile: "NOT_RUN"})), "PROFILE_NOT_EXECUTED")
    assert_fires(check(baseline, lambda r: r["profile_status"].pop(profile)), "PROFILE_NOT_EXECUTED")


# ------------------------------------------------------------------ result / exit


@pytest.mark.parametrize("value,code", [
    ("FAIL", "RESULT_FAIL"), ("NOT_RUN", "RESULT_NOT_RUN"), ("INCONCLUSIVE", "RESULT_INCONCLUSIVE"),
    ("BLOCKED", "RESULT_BLOCKED"), ("UNSUPPORTED", "RESULT_UNSUPPORTED"),
    ("MAYBE", "RESULT_UNKNOWN"), ("", "RESULT_UNKNOWN"),
])
def test_every_non_pass_result_is_typed_and_non_approving(baseline, value, code):
    assert_fires(check(baseline, lambda r: r.update(result=value)), code)


@pytest.mark.parametrize("value", [1, 2, -1])
def test_exit_code_nonzero(baseline, value):
    assert_fires(check(baseline, lambda r: r.update(exit_code=value)), "EXIT_NONZERO")


@pytest.mark.parametrize("value", [None, True, False, "0", 0.0])
def test_exit_code_wrong_type_is_schema(baseline, value):
    assert_only_schema(check(baseline, lambda r: r.update(exit_code=value)))


# ------------------------------------------------------------------ ID accounting


def test_missing_unknown_duplicate_and_not_all_passed_ids(baseline):
    exp = baseline["record"]["expected_test_ids"]
    assert_fires(check(baseline, lambda r: r.update(expected_test_ids=exp[:1], passed_test_ids=exp[:1])), "MISSING_ID")
    assert_fires(check(baseline, lambda r: r["expected_test_ids"].append(F + "::test_ghost")), "UNKNOWN_ID")
    assert_fires(check(baseline, lambda r: r["passed_test_ids"].append(F + "::test_ghost")), "UNKNOWN_ID")
    assert_fires(check(baseline, lambda r: r["expected_test_ids"].append(exp[0])), "DUPLICATE_ID")
    assert_fires(check(baseline, lambda r: r["passed_test_ids"].append(exp[0])), "DUPLICATE_ID")
    assert_fires(check(baseline, lambda r: r["executed_node_ids"].append(r["executed_node_ids"][0])), "DUPLICATE_ID")
    assert_fires(check(baseline, lambda r: r.update(passed_test_ids=exp[:1])), "NOT_ALL_PASSED")
    assert_fires(check(baseline, lambda r: r.update(passed_test_ids=[])), "NOT_ALL_PASSED")


def test_malformed_id_lists_are_schema_not_a_crash(baseline):
    assert_fires(check(baseline, lambda r: r.update(passed_test_ids="x")), "SCHEMA")
    assert_fires(check(baseline, lambda r: r.update(expected_test_ids=None)), "SCHEMA")


def test_no_execution(baseline):
    assert_fires(check(baseline, lambda r: r.update(executed_node_ids=[])), "NO_EXECUTION")


def test_not_run_unassigned_failed_skipped_xfail_uncollected_unexpected(baseline):
    sel = baseline["record"]["expected_test_ids"][0]
    assert_fires(check(baseline, lambda r: r.update(not_run_test_reasons={sel: "NOT_RUN: x"})), "NOT_RUN_IDS")
    assert_fires(check(baseline, lambda r: r.update(unassigned_test_ids=[sel])), "UNASSIGNED_IDS")
    for field, code in (
        ("failed_test_ids", "FAILED_IDS"), ("skipped_test_ids", "SKIPPED_IDS"), ("xfail_test_ids", "XFAIL_IDS"),
        ("uncollected_test_ids", "UNCOLLECTED_IDS"), ("unexpected_node_ids", "UNEXPECTED_CASES"),
    ):
        assert_fires(check(baseline, lambda r, f=field: r.update({f: [sel]})), code)


def test_registry_level_not_run_selectors_block_even_if_report_claims_none(baseline):
    registry = copy.deepcopy(baseline["registry"])
    registry.category_not_run["functional"] = {"x": "NOT_RUN: y"}
    assert_fires(check(baseline, registry=registry), "NOT_RUN_IDS")


# ------------------------------------------------------------------ binding / environment


def test_stale_head_wrong_expected_and_head_after_moved(baseline):
    assert_fires(check(baseline, head="1" * 40), "STALE_HEAD")
    assert_fires(check(baseline, lambda r: r.update(head_after="2" * 40)), "STALE_HEAD")
    assert_fires(check(baseline, lambda r: r.update(candidate_head="3" * 40)), "STALE_HEAD")
    assert_only_schema(check(baseline, lambda r: r.update(head_after=None)))  # null head is a type error


def test_registry_mismatch_on_digest_and_source_head(baseline):
    assert_fires(check(baseline, lambda r: r.update(registry_sha256=GOOD)), "REGISTRY_MISMATCH")
    assert_fires(check(baseline, lambda r: r.update(source_head="4" * 40)), "REGISTRY_MISMATCH")
    assert_only_schema(check(baseline, lambda r: r.update(registry_sha256=None)))


def test_dirty_tree_before_after_and_malformed(baseline):
    assert_fires(check(baseline, lambda r: r["dirty_tree"].update(before=True)), "DIRTY_TREE")
    assert_fires(check(baseline, lambda r: r["dirty_tree"].update(after=True)), "DIRTY_TREE")
    assert_fires(check(baseline, lambda r: r["dirty_tree"].pop("after")), "DIRTY_TREE")
    assert_only_schema(check(baseline, lambda r: r.update(dirty_tree=None)))  # not a mapping: type error


def test_state_changed(baseline):
    assert_fires(check(baseline, lambda r: r.update(git_state_unchanged=False)), "STATE_CHANGED")
    assert_fires(check(baseline, lambda r: r.update(git_state_unchanged=None)), "STATE_CHANGED")
    assert_fires(check(baseline, lambda r: r.update(evidence_unchanged=False)), "STATE_CHANGED")


@pytest.mark.parametrize("value", ["", ZERO, "ABCD", "ab" * 31, "g" * 64])
def test_lock_missing_or_invalid(baseline, value):
    assert_fires(check(baseline, lambda r: r.update(lock_sha256=value)), "LOCK_MISSING")


def test_lock_null_is_schema(baseline):
    assert_only_schema(check(baseline, lambda r: r.update(lock_sha256=None)))


def test_dependency_unverified_before_or_after(baseline):
    assert_fires(check(baseline, lambda r: r.update(dependency_content_verified_before=False)), "DEPENDENCY_UNVERIFIED")
    assert_fires(check(baseline, lambda r: r.update(dependency_content_verified_after=False)), "DEPENDENCY_UNVERIFIED")
    assert_fires(check(baseline, lambda r: r.update(dependency_content_verified_after=None)), "DEPENDENCY_UNVERIFIED")


# ------------------------------------------------------------------ hash / artifacts


def test_hash_mismatch_on_edit_without_rehash_and_clears_when_rehashed(baseline):
    def edit(r):
        r["duration_seconds"] = 12345.0
        r["pytest_version"] = "0.0.0-edited"
    res = check(baseline, edit)
    assert_fires(res, "HASH_MISMATCH")
    # the digest check is real: recomputing the digest removes exactly this code
    assert "HASH_MISMATCH" not in check(baseline, edit, rehash=True).codes()
    assert_fires(check(baseline, lambda r: r.update(normalized_sha256=GOOD)), "HASH_MISMATCH")
    assert_only_schema(check(baseline, lambda r: r.update(normalized_sha256=None)))


@pytest.mark.parametrize("bad", [ZERO, "", "xyz", "AB" * 32])
def test_artifact_digest_invalid(baseline, bad):
    assert_fires(check(baseline, lambda r: r["artifact_digests"].update(stdout=bad)), "ARTIFACT_DIGEST_INVALID")


def test_artifact_digest_null_value_is_schema(baseline):
    assert_only_schema(check(baseline, lambda r: r["artifact_digests"].update(stdout=None)))


def test_artifact_digest_empty_is_invalid_and_inventory_and_non_mapping_is_schema(baseline):
    assert_fires(check(baseline, lambda r: r.update(artifact_digests={})), "ARTIFACT_DIGEST_INVALID", "ARTIFACT_INVENTORY")
    assert_only_schema(check(baseline, lambda r: r.update(artifact_digests=None)))
    assert_only_schema(check(baseline, lambda r: r.update(artifact_digests=[])))


def test_artifact_unverified_when_bytes_not_supplied(baseline):
    assert_fires(check(baseline, artifacts=None), "ARTIFACT_UNVERIFIED")


def test_artifact_mismatch_altered_truncated_missing_and_wrong_size(baseline):
    arts = baseline["artifacts"]
    assert_fires(check(baseline, artifacts={**arts, "stdout": arts["stdout"] + b"x"}), "ARTIFACT_MISMATCH")
    assert_fires(check(baseline, artifacts={**arts, "stderr": arts["stderr"][:-1]}), "ARTIFACT_MISMATCH")
    assert_fires(check(baseline, artifacts={"stdout": arts["stdout"]}), "ARTIFACT_MISMATCH")
    assert_fires(check(baseline, lambda r: r["artifact_sizes"].update(stdout=1)), "ARTIFACT_MISMATCH")


def test_artifact_inventory_missing_extra_or_malformed_keys(baseline):
    assert_fires(check(baseline, lambda r: r["artifact_digests"].pop("stderr")), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r["artifact_digests"].pop("stdout")), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r["artifact_sizes"].pop("stderr")), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r["artifact_sizes"].pop("stdout")), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r["artifact_paths"].pop("stderr")), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r["artifact_digests"].update(extra=GOOD)), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r["artifact_sizes"].update(extra=1)), "ARTIFACT_INVENTORY")
    # malformed size mapping: empty, or keyed by names other than the two raw outputs
    assert_fires(check(baseline, lambda r: r.update(artifact_sizes={})), "ARTIFACT_INVENTORY")
    assert_fires(check(baseline, lambda r: r.update(artifact_sizes={"out": 1, "err": 2})), "ARTIFACT_INVENTORY")


# ------------------------------------------------------------------ type pre-validation (never raises)


@pytest.mark.parametrize("value", [None, [], ["x"], 0, 7, "EXECUTED"])
def test_profile_status_non_mapping_is_schema(baseline, value):
    assert_only_schema(check(baseline, lambda r: r.update(profile_status=value)))


@pytest.mark.parametrize("value", [["functional"], {"a": 1}, 5, None])
def test_category_wrong_type_is_schema_not_a_crash(baseline, value):
    assert_only_schema(check(baseline, lambda r: r.update(category=value)))


@pytest.mark.parametrize("field", list(gc.ID_LIST_FIELDS))
@pytest.mark.parametrize("element", [["nested"], {"k": "v"}, 5, None])
def test_id_list_with_non_string_or_unhashable_element_is_schema(baseline, field, element):
    assert_only_schema(check(baseline, lambda r: r[field].append(element)))


@pytest.mark.parametrize("value", [None, [], 5, "x"])
def test_artifact_sizes_non_mapping_is_schema(baseline, value):
    assert_only_schema(check(baseline, lambda r: r.update(artifact_sizes=value)))


def test_artifact_sizes_bad_value_types_are_schema(baseline):
    for bad in (True, -1, "5", None, 1.5):
        assert_only_schema(check(baseline, lambda r, b=bad: r["artifact_sizes"].update(stdout=b)))


def test_other_mapping_and_list_fields_wrong_type_are_schema(baseline):
    assert_only_schema(check(baseline, lambda r: r.update(not_run_test_reasons=[])))
    assert_only_schema(check(baseline, lambda r: r.update(artifact_paths=None)))
    assert_only_schema(check(baseline, lambda r: r["artifact_paths"].update(stdout=5)))
    assert_only_schema(check(baseline, lambda r: r.update(command="pytest -q")))
    assert_only_schema(check(baseline, lambda r: r["command"].append(3)))
    assert_only_schema(check(baseline, lambda r: r.update(manifest_path=None)))


# ------------------------------------------------------------------ secret / absolute path


def test_secret_like_value_user_path_and_absolute_command_path(baseline):
    token = "ghp_" + "A1b2C3d4" * 5
    assert_fires(check(baseline, lambda r: r["reasons"].append("leaked " + token)), "SECRET_OR_ABS_PATH")
    assert_fires(check(baseline, lambda r: r["reasons"].append("see C:\\Users\\alice\\proj\\x.py")), "SECRET_OR_ABS_PATH")
    assert_fires(check(baseline, lambda r: r["reasons"].append("see C:/Users/alice/proj/x.py")), "SECRET_OR_ABS_PATH")
    assert_fires(check(baseline, lambda r: r.update(command=["python", "D:\\work\\x.py"])), "SECRET_OR_ABS_PATH")
    assert_fires(check(baseline, lambda r: r.update(command=["/usr/bin/python"])), "SECRET_OR_ABS_PATH")
    assert_fires(check(baseline, lambda r: r["artifact_paths"].update(stdout="C:/abs/out.txt")), "SECRET_OR_ABS_PATH")
    assert_fires(check(baseline, lambda r: r.update(manifest_path="/etc/manifest.json")), "SECRET_OR_ABS_PATH")


@pytest.mark.parametrize("extra", [
    ["--rootdir=C:\\Users\\alice\\project"],
    ["--qa-selection-file=D:\\private\\selection.json"],
    ["--config=/home/alice/config.json"],
    ["--rootdir", "/home/alice/project"],
    ["--qa-selection-file", "D:\\private\\selection.json"],
    ["--rootdir=\\\\server\\share\\x"],
    ["--opt 'C:/data/x'"],
])
def test_absolute_path_in_command_in_every_form_is_flagged(baseline, extra):
    result = check(baseline, lambda r: r.update(command=r["command"] + extra))
    assert_fires(result, "SECRET_OR_ABS_PATH")
    rec = copy.deepcopy(baseline["record"])
    rec["command"] = rec["command"] + extra
    assert any(hit.startswith("command") for hit in gc._secret_or_path_hits(rec))


def test_placeholder_arguments_do_not_trigger_secret_or_abs_path(baseline):
    placeholders = ["--rootdir=<candidate-root>", "--confcutdir=<candidate-root>/tests",
                    "--qa-repo-root=<candidate-root>", "<scratch>\\pytest.ini", "<scratch>/pytest.ini"]
    rec = copy.deepcopy(baseline["record"])
    rec["command"] = rec["command"] + placeholders
    assert gc._secret_or_path_hits(rec) == []
    assert gc._ABS_PATH.search("--rootdir=<candidate-root>/tests") is None
    assert gc._ABS_PATH.search("<scratch>\\pytest.ini") is None
    assert gc._ABS_PATH.search("--rootdir=C:\\Users\\x") is not None


# ------------------------------------------------------------------ select_record / digests


def _line(**kw):
    return json.dumps(kw)


def test_select_record_takes_last_line_and_skips_blank_lines():
    lines = [_line(a=1).encode(), b"", _line(a=2), b"   \n", _line(a=3).encode() + b"\n"]
    assert gc.select_record(lines) == {"a": 3}


def test_select_record_refuses_undecodable_non_object_duplicate_keys_and_empty():
    with pytest.raises(ValueError):
        gc.select_record([_line(a=1), "{not json"])  # torn append never falls back to an older line
    with pytest.raises(ValueError):
        gc.select_record([_line(a=1), b"\xff\xfe\x00bad"])
    with pytest.raises(ValueError):
        gc.select_record([_line(a=1), "[1, 2]"])
    with pytest.raises(ValueError):
        gc.select_record(['{"a": 1, "a": 2}'])
    with pytest.raises(ValueError):
        gc.select_record(["", "  "])
    with pytest.raises(ValueError):
        gc.select_record([])


def test_approved_report_digests_only_for_approvable_checks(baseline):
    good, bad = check(baseline), check(baseline, lambda r: r.update(result="FAIL"))
    assert good.approvable and not bad.approvable
    out = gc.approved_report_digests([("a.jsonl", b"AAA", good), ("b.jsonl", b"BBB", bad)])
    assert out == {"a.jsonl": gc.sha256_bytes(b"AAA")} and "b.jsonl" not in out
    assert gc.approved_report_digests([("b.jsonl", b"BBB", bad)]) == {}


# ------------------------------------------------------------------ real committed records (read-only)


def test_real_committed_fail_records_are_all_non_approving(baseline):
    evidence = REPO_ROOT / "docs" / "sdlc" / "evidence" / "qa"
    files = sorted(evidence.glob("*.report.jsonl"))
    if not files:
        pytest.skip("no committed QA report records")
    try:
        registry = validate_registry(REPO_ROOT)
    except RegistryError:
        # validate_registry fails closed on a dirty tests/ or tools/qa tree (uncommitted work in
        # progress). Fall back to the baseline registry: a FAIL record must be NON_APPROVING
        # against any registry, so the assertion below stays meaningful.
        registry = baseline["registry"]
    head = git(REPO_ROOT, "rev-parse", "HEAD").strip()
    for path in files:
        record = gc.select_record(path.read_bytes().splitlines())
        stem = path.name[: -len(".report.jsonl")]
        arts = {}
        for key in ("stdout", "stderr"):
            raw = evidence / f"{stem}.{key}.txt"
            arts[key] = raw.read_bytes() if raw.exists() else b""
        result = gc.check_report(record, registry, expected_head=head, artifact_bytes=arts)
        assert result.verdict == gc.NON_APPROVING and result.reasons, path.name
        assert record.get("result") != "PASS", path.name
