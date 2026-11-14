"""LINK-2 T4b: routing matrix, final-package router section and the U5 driver stage, AC-19 to AC-23.

- AC-19: for router outcome x review verdict, READY is reachable only for ROUTED_VERIFIED with CLEAN; every other cell
  of {VERIFIED, REJECTED, UNKNOWN, INVALID} x {CLEAN, FINDINGS, PARTIAL, BLOCKED} is BLOCKED.
- AC-20: UNKNOWN never produces READY in any cell.
- AC-21: `router_required` True with no row gives ROUTER_NOT_VERIFIED; `router_required` False leaves the package
  byte-identical to the package built before router mode existed.
- AC-22: link mode `gates` makes no AEVE call and skips `stage_router` (the router_mode side is in test_router_mode.py).
- AC-23: mode `router` with a role outside the five skips `stage_router`.
The package inputs are the hand-built dictionaries of tests/vst/test_u5_final_package.py (same module helpers).
"""

from __future__ import annotations

import copy
import itertools
import types

import pytest

from tools.vst import final_package as fp
from tools.vst import link_mode
from tools.vst import router_mode as rm
from tools.vst import router_request as rr
from tools.vst import u5_real_change_driver as drv
from tools.vst.router_request import RouterError

from tests.vst import test_u5_final_package as FP

PIN = "35e5de868edaa37e021955147afb587011ca39c0"
OTHER_PIN = "8a9f6c1a684e03eac252b285a96a11d363dbc9e6"  # the pin before LINK2-T1
OUTCOMES = {"VERIFIED": "ROUTED_VERIFIED", "REJECTED": "ROUTED_REJECTED", "UNKNOWN": "ROUTED_UNKNOWN",
            "INVALID": "ROUTER_INVALID_INPUT"}
VERDICTS = ("CLEAN", "FINDINGS", "PARTIAL", "BLOCKED")
RESULT = "c" * 64


def row(status="VERIFIED", **over):
    doc = {"outcome": OUTCOMES.get(status, "ROUTED_VERIFIED") if isinstance(status, str) else "ROUTED_VERIFIED", "status": status, "task_id": "LINK2-DEMO-1", "request_sha256": "a" * 64,
           "packet_sha256": "b" * 64, "result_sha256": RESULT, "report_sha256": "d" * 64, "pin_head": PIN,
           "result_sha256_recomputed": RESULT}
    doc.update(over)
    return doc


def build(**over):
    return fp.build_final_package(**FP.args(**over))


def reasons(result):
    return [code for code, _ in result.reasons]


# ============================================================ AC-19, AC-20: the routing matrix
@pytest.mark.parametrize("status,verdict", list(itertools.product(OUTCOMES, VERDICTS)))
def test_route_gate_matrix_only_verified_with_clean_is_eligible(status, verdict):  # AC-19
    expected = "ELIGIBLE" if (status, verdict) == ("VERIFIED", "CLEAN") else "BLOCKED"
    assert rm.route_gate(OUTCOMES[status], verdict) == expected


def test_exactly_one_cell_of_the_sixteen_is_eligible():
    cells = [rm.route_gate(o, v) for o in OUTCOMES.values() for v in VERDICTS]
    assert cells.count("ELIGIBLE") == 1 and cells.count("BLOCKED") == 15


@pytest.mark.parametrize("verdict", VERDICTS)
def test_unknown_is_never_eligible_in_any_cell(verdict):  # AC-20
    assert rm.route_gate("ROUTED_UNKNOWN", verdict) == "BLOCKED"


@pytest.mark.parametrize("outcome,verdict", [
    (None, "CLEAN"), ("ROUTED_VERIFIED", None), (None, None), ("ROUTED_VERIFIED", "clean"),
    ("routed_verified", "CLEAN"), ("VERIFIED", "CLEAN"), ("ROUTED_VERIFIED ", "CLEAN"), ("ROUTED_VERIFIED", "CLEAN "),
    ("", ""), (True, True), (["ROUTED_VERIFIED"], ["CLEAN"]), ("ROUTED_BOGUS", "CLEAN"), ("ROUTED_VERIFIED", "OK"),
    ("ROUTED_VERIFIED", "ACCEPTED"), (0, 0),
])
def test_no_verdict_or_an_unknown_word_is_blocked(outcome, verdict):  # AC-19
    assert rm.route_gate(outcome, verdict) == "BLOCKED"


def test_the_outcome_names_used_by_the_matrix_are_the_ones_the_wrapper_produces():
    assert rm.ROUTER_OUTCOMES == tuple(OUTCOMES.values())
    assert rm.REVIEW_VERDICTS == VERDICTS and (rm.ELIGIBLE, rm.BLOCKED) == ("ELIGIBLE", "BLOCKED")


# ============================================================ AC-21: the package builder
BASELINE_KEYS = {"schema", "story_id", "head", "base_head", "valid_for_head", "created_at", "diff", "tests",
                 "not_run", "allow_not_run", "review", "receipts", "isolation", "patch_origin_share",
                 "evidence_digests", "declared_limits", "derived_limits"}
BASELINE_DIGESTS = {"diff_sha256", "tests", "review_result_sha256", "receipts", "isolation_proof_sha256",
                    "patch_origin_share_sha256"}


def test_without_router_arguments_the_package_has_no_router_keys():  # AC-21
    result = build()
    assert result.ready
    assert set(result.package) == BASELINE_KEYS
    assert set(result.package["evidence_digests"]) == BASELINE_DIGESTS


def test_router_not_required_and_no_row_is_byte_identical_to_the_default_call():  # AC-21
    plain = build()
    explicit = build(router_required=False, router_report=None, router_pin_head=None)
    assert explicit.package == plain.package and explicit.package_sha256 == plain.package_sha256
    assert explicit.package_sha256 == FP.canon_sha(plain.package)


def test_required_without_a_row_is_refused_with_router_not_verified():  # AC-21
    result = build(router_required=True)
    assert result.verdict == fp.REFUSED and reasons(result) == ["ROUTER_NOT_VERIFIED"]
    assert result.package is None


def test_required_with_a_verified_row_is_ready_and_records_the_row_and_its_digest():
    result = build(router_required=True, router_report=row(aeve_request_sha256="e" * 64))
    assert result.verdict == fp.READY, result.reasons
    section = result.package["router"]
    assert section == {**row(aeve_request_sha256="e" * 64)}
    assert result.package["evidence_digests"]["router_report_sha256"] == FP.canon_sha(section)
    assert result.package_sha256 == FP.canon_sha(result.package)
    assert FP.verify(result)[0] is True  # the router keys do not break the invalidation check


def test_optional_aeve_digest_may_be_absent_and_the_row_is_still_recorded():
    result = build(router_required=True, router_report=row())
    assert result.ready and result.package["router"]["aeve_request_sha256"] is None


@pytest.mark.parametrize("status", ["REJECTED", "UNKNOWN", "INVALID"])
def test_required_with_any_other_outcome_is_refused_never_ready(status):  # AC-20, AC-21
    result = build(router_required=True, router_report=row(status))
    assert result.verdict == fp.REFUSED and reasons(result) == ["ROUTER_NOT_VERIFIED"]
    assert status in dict(result.reasons)["ROUTER_NOT_VERIFIED"] or OUTCOMES[status] in dict(result.reasons)["ROUTER_NOT_VERIFIED"]


@pytest.mark.parametrize("over", [
    {"status": "UNKNOWN"}, {"status": "REJECTED"}, {"status": "verified"}, {"status": "VERIFIED "},
    {"outcome": "ROUTED_UNKNOWN"}, {"outcome": "ROUTED_REJECTED"}, {"outcome": "ROUTER_INVALID_INPUT"},
])
def test_outcome_and_status_must_both_say_verified(over):  # AC-20
    result = build(router_required=True, router_report=row(**over))
    assert result.verdict in (fp.REFUSED, fp.BLOCKED) and not result.ready


def test_required_row_at_another_pin_is_refused():
    result = build(router_required=True, router_report=row(pin_head=OTHER_PIN))
    assert result.verdict == fp.REFUSED and reasons(result) == ["ROUTER_NOT_VERIFIED"]


def test_the_expected_pin_defaults_to_the_pin_of_the_shipped_role_table():
    assert build(router_required=True, router_report=row(pin_head=PIN)).ready
    explicit = build(router_required=True, router_report=row(pin_head=OTHER_PIN), router_pin_head=OTHER_PIN)
    assert explicit.ready
    assert build(router_required=True, router_report=row(pin_head=PIN), router_pin_head=OTHER_PIN).verdict == fp.REFUSED


def test_result_copy_that_hashes_differently_now_is_a_digest_mismatch():  # AC-27 at package time
    result = build(router_required=True, router_report=row(result_sha256_recomputed="0" * 64))
    assert result.verdict == fp.REFUSED and reasons(result) == ["ROUTER_RESULT_DIGEST_MISMATCH"]


def test_digest_mismatch_is_refused_even_when_the_router_is_not_required():
    result = build(router_required=False, router_report=row(result_sha256_recomputed="0" * 64))
    assert result.verdict == fp.REFUSED and reasons(result) == ["ROUTER_RESULT_DIGEST_MISMATCH"]


def test_both_reasons_are_listed_together():
    result = build(router_required=True, router_report=row("UNKNOWN", result_sha256_recomputed="0" * 64))
    assert sorted(reasons(result)) == ["ROUTER_NOT_VERIFIED", "ROUTER_RESULT_DIGEST_MISMATCH"]


def test_a_row_without_the_requirement_is_recorded_and_does_not_refuse():
    result = build(router_required=False, router_report=row("REJECTED"))
    assert result.ready and result.package["router"]["outcome"] == "ROUTED_REJECTED"
    assert "router_report_sha256" in result.package["evidence_digests"]


@pytest.mark.parametrize("label,doc", [
    ("missing key", {k: v for k, v in row().items() if k != "report_sha256"}),
    ("unknown key", dict(row(), extra=1)),
    ("not an object", ["x"]),
    ("short digest", row(packet_sha256="a" * 63)),
    ("upper case digest", row(request_sha256="A" * 64)),
    ("digest with a trailing line feed", row(result_sha256="c" * 64 + "\n")),
    ("short pin", row(pin_head="abc")),
    ("pin with a trailing line feed", row(pin_head=PIN + "\n")),
    ("unknown outcome", row(outcome="ROUTED_MAYBE")),
    ("status not text", row(status=5)),
    ("empty task", row(task_id="")),
    ("bad optional digest", row(aeve_request_sha256="zz")),
    ("recomputed digest missing", {k: v for k, v in row().items() if k != "result_sha256_recomputed"}),
])
def test_malformed_router_rows_block_the_package(label, doc):
    result = build(router_required=True, router_report=doc)
    assert result.verdict == fp.BLOCKED and not result.ready and result.package is None, label


@pytest.mark.parametrize("value", [1, "yes", None, 0])
def test_router_required_must_be_a_real_bool(value):
    assert build(router_required=value).verdict == fp.BLOCKED


def test_builder_does_not_mutate_the_router_row():
    doc = row()
    before = copy.deepcopy(doc)
    build(router_required=True, router_report=doc)
    assert doc == before


@pytest.mark.parametrize("status,verdict", list(itertools.product(OUTCOMES, VERDICTS)))
def test_package_is_ready_only_for_a_verified_row_and_a_clean_review(status, verdict):  # AC-19, AC-20
    review = FP.review_ok(verdict=verdict) if verdict == "CLEAN" else FP.review_ok(
        verdict="BLOCKED", reasons=["REVIEW_BLOCKED"])
    result = build(router_required=True, router_report=row(status), review_results=review)
    assert (result.verdict == fp.READY) == (status == "VERIFIED" and verdict == "CLEAN")


# ============================================================ AC-22, AC-23: the driver stage
def args(**over):
    base = dict(router_role="implementation-engineer", router_title=None, router_scope_path=None,
                router_acceptance=["It works."], router_result=None, router_state_root=None,
                target_file="docs/a.md", aeve="D:/aeve", worktree="D:/wt", state_dir="D:/state")
    base.update(over)
    return types.SimpleNamespace(**base)


def fake_row():
    return rm.RouterRow(state="DONE", outcome="ROUTED_VERIFIED", status="VERIFIED", task_id=drv.STORY,
                        request_sha256="a" * 64, aeve_request_sha256="e" * 64, packet_sha256="b" * 64,
                        result_sha256=RESULT, report_sha256="d" * 64, pin_head=PIN, packet_path="p", work_dir="w",
                        resume="none", reason="")


@pytest.fixture()
def set_mode(monkeypatch):
    def apply(mode):
        monkeypatch.setattr(link_mode, "resolve", lambda *a, **k: link_mode.ResolvedMode(mode, True, None))

    return apply


@pytest.fixture()
def no_route(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("route_task must not be called")

    monkeypatch.setattr(rm, "route_task", refuse)


def test_stage_is_skipped_in_gates_mode_and_nothing_is_routed(set_mode, no_route):  # AC-22
    set_mode("gates")
    ev: dict = {}
    assert drv.stage_router(args(), object(), ev) == (False, None)
    assert ev["router"] == {"skipped": "link mode is not router", "mode": "gates"}


def test_the_shipped_catalog_is_gates_so_the_stage_is_skipped_by_default(no_route):  # AC-22
    ev: dict = {}
    assert drv.stage_router(args(), object(), ev) == (False, None)
    assert ev["router"]["mode"] == "gates"


@pytest.mark.parametrize("role", ["loop-operator", "rosetta", None, "", "Planner"])
def test_router_mode_with_a_role_outside_the_five_skips_the_stage(set_mode, no_route, role):  # AC-23
    set_mode("router")
    ev: dict = {}
    assert drv.stage_router(args(router_role=role), object(), ev) == (False, None)
    assert ev["router"] == {"skipped": "the story role is not a HANDOFF_ASSISTED role", "role": role}


@pytest.mark.parametrize("role", rr.ROUTER_ROLES)
def test_router_mode_with_each_of_the_five_roles_routes_the_story(set_mode, monkeypatch, role):
    set_mode("router")
    seen = {}

    def fake_route(request, **kwargs):
        seen.update(request=request, kwargs=kwargs)
        return fake_row()

    monkeypatch.setattr(rm, "route_task", fake_route)
    ev: dict = {}
    active, result_row = drv.stage_router(args(router_role=role, router_result="D:/host/result.json",
                                               router_state_root="D:/router-state"), object(), ev)
    assert active is True and result_row == fake_row()
    assert seen["request"]["role"] == role and seen["request"]["task_id"] == drv.STORY
    assert seen["request"]["scope_paths"] == ["docs/a.md"]  # default scope is the target file
    assert seen["request"]["acceptance"] == ["It works."]
    assert str(seen["kwargs"]["state_root"]) == "D:/router-state" and seen["kwargs"]["result_source"] == "D:/host/result.json"
    assert ev["router"]["outcome"] == "ROUTED_VERIFIED" and ev["router"]["row"] == fake_row().to_report()


def test_state_root_defaults_to_the_driver_state_dir(set_mode, monkeypatch):
    set_mode("router")
    seen = {}
    monkeypatch.setattr(rm, "route_task", lambda request, **kw: seen.update(kw) or fake_row())
    drv.stage_router(args(), object(), {})
    assert seen["state_root"] == "D:/state"


def test_a_router_refusal_is_recorded_and_blocks_the_flow_without_falling_back(set_mode, monkeypatch):
    set_mode("router")

    def refuse(request, **kwargs):
        raise RouterError("ROUTER_PIN_DRIFT", "AEVE HEAD differs from the pinned head")

    monkeypatch.setattr(rm, "route_task", refuse)
    ev: dict = {}
    assert drv.stage_router(args(), object(), ev) == (True, None)  # active, no row: the caller must stop
    assert ev["router"] == {"blocked": "ROUTER_PIN_DRIFT", "detail": "AEVE HEAD differs from the pinned head"}


def test_empty_acceptance_in_router_mode_is_a_bad_request_not_a_crash(set_mode, no_route):
    set_mode("router")
    ev: dict = {}
    assert drv.stage_router(args(router_acceptance=None), object(), ev) == (True, None)
    assert ev["router"]["blocked"] == "ROUTER_BAD_REQUEST"


def test_unreadable_link_mode_blocks_instead_of_guessing(monkeypatch, no_route):
    def broken(*a, **k):
        raise link_mode.LinkModeError(link_mode.CATALOG_INVALID, "x")

    monkeypatch.setattr(link_mode, "resolve", broken)
    ev: dict = {}
    assert drv.stage_router(args(), object(), ev) == (True, None)
    assert ev["router"] == {"blocked": "LINK_MODE_UNREADABLE", "code": "CATALOG_INVALID"}
