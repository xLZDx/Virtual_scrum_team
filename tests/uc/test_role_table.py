"""U1-4: role table builder and validator, tested with a small synthetic matrix/inventory (no AEVE call)
plus structural checks of the committed catalog/role_table.json that need no AEVE."""

from __future__ import annotations

import copy
import json
import pathlib

import pytest

from uc import role_table as rt

from tests.uc import ucsupport as S

PIN_HEAD = "1" * 40
PIN_DIGEST = "2" * 64
PROBE = {"aeve_head": PIN_HEAD, "matrix": {"digest_sha256": PIN_DIGEST}}

MATRIX = {"rows": [
    {"id": "python-reviewer", "deterministic_executors": ["g2.b", "g2.a"]},   # unsorted on purpose
    {"id": "architect", "deterministic_executors": ["g1.graph"]},
    {"id": "profile-no-exec", "deterministic_executors": []},
    {"id": "profile-none-key"},
]}


def inv(*pairs):
    return {"entries": [{"kind": k, "name": n} for k, n in pairs]}


def draft(*rows):
    out = []
    for kind, name, decision, merged, rationale, rem in rows:
        out.append({"kind": kind, "name": name, "decision": decision, "merged_into": merged,
                    "rationale": rationale, "model_remainder": rem})
    return {"entries": out}


INVENTORY = inv(("agent", "python-reviewer"), ("agent", "code-architect"), ("agent", "architect"),
                ("agent", "business-analyst"), ("agent", "profile-no-exec"), ("agent", "writer"),
                ("agent", "stale"), ("skill", "python-reviewer"), ("agent", "profile-none-key"))
DRAFT = draft(
    ("agent", "python-reviewer", "check_plus_model", None, "r", "judge"),
    ("agent", "code-architect", "merge", "architect", "r", ""),
    ("agent", "architect", "model_only", None, "design judgment", "tradeoffs"),   # upgraded by evidence
    ("agent", "business-analyst", "model_only", None, "Domain authoring.", "elicit"),
    ("agent", "profile-no-exec", "check", None, "r", ""),
    ("agent", "writer", "check", None, "r", ""),                                  # no profile at all
    ("agent", "stale", "drop", None, "obsolete", ""),
    ("skill", "python-reviewer", "merge", "python-reviewer", "r", ""),
    ("agent", "profile-none-key", "check_plus_model", None, "r", ""),
)


@pytest.fixture()
def built():
    return rt.build_role_table(INVENTORY, DRAFT, MATRIX, PROBE)


def by_key(table):
    return {(e["kind"], e["name"]): e for e in table["entries"]}


# ------------------------------------------------------------------ builder
def test_build_pins_head_and_digest(built):
    assert built["aeve_pin"] == {"head": PIN_HEAD, "matrix_digest_sha256": PIN_DIGEST}
    assert built["version"] == rt.TABLE_VERSION


def test_build_covered_role_gets_sorted_matrix_executors(built):
    e = by_key(built)[("agent", "python-reviewer")]
    assert (e["class"], e["coverage_state"], e["executors"]) == ("LOCAL_PLUS_MODEL", "COVERED_PARTIAL", ["g2.a", "g2.b"])
    assert e["aeve_profile"] == "python-reviewer" and e["class_upgraded_by_evidence"] is False


def test_build_model_only_draft_with_executors_is_upgraded_by_evidence(built):
    e = by_key(built)[("agent", "architect")]
    assert e["class"] == "LOCAL_PLUS_MODEL" and e["draft_class"] == "MODEL_ONLY"
    assert e["class_upgraded_by_evidence"] is True and e["executors"] == ["g1.graph"]


def test_build_draft_class_not_supported_by_evidence_is_not_local(built):
    """A MODEL_ONLY draft with no executors stays MODEL_ONLY/NOT_APPLICABLE and never claims coverage."""
    e = by_key(built)[("agent", "business-analyst")]
    assert (e["class"], e["coverage_state"], e["executors"]) == ("MODEL_ONLY", "NOT_APPLICABLE", [])
    assert e["class_upgraded_by_evidence"] is False and e["reason"] == "Domain authoring."


def test_build_drop_is_out_of_scope(built):
    e = by_key(built)[("agent", "stale")]
    assert (e["class"], e["coverage_state"]) == ("OUT_OF_SCOPE", "NOT_APPLICABLE")


def test_build_profile_without_executor_and_no_profile_states(built):
    a = by_key(built)[("agent", "profile-no-exec")]
    assert (a["class"], a["coverage_state"], a["aeve_profile"]) == ("LOCAL", "NOT_COVERED_NO_EXECUTOR", "profile-no-exec")
    b = by_key(built)[("agent", "profile-none-key")]
    assert b["coverage_state"] == "NOT_COVERED_NO_EXECUTOR" and b["executors"] == []
    w = by_key(built)[("agent", "writer")]
    assert (w["coverage_state"], w["aeve_profile"]) == ("NOT_COVERED_NO_PROFILE", None)


def test_build_alias_inherits_canonical_role_class_and_executors(built):
    e = by_key(built)[("agent", "code-architect")]
    assert e["canonical_role"] == "architect" and e["class"] == "LOCAL_PLUS_MODEL"
    assert e["executors"] == ["g1.graph"] and e["coverage_state"] == "COVERED_PARTIAL"
    s = by_key(built)[("skill", "python-reviewer")]
    assert s["canonical_role"] == "python-reviewer" and s["executors"] == ["g2.a", "g2.b"]


def test_build_entries_sorted_and_counts_generated(built):
    keys = [(e["kind"], e["name"]) for e in built["entries"]]
    assert keys == sorted(keys)
    assert built["counts"]["total"] == len(INVENTORY["entries"])
    assert sum(built["counts"]["by_class"].values()) == len(keys)
    assert sum(built["counts"]["by_coverage_state"].values()) == len(keys)
    assert built["counts"] == rt._counts(built["entries"])


def test_build_is_deterministic():
    assert rt.build_role_table(INVENTORY, DRAFT, MATRIX, PROBE) == rt.build_role_table(INVENTORY, DRAFT, MATRIX, PROBE)


def test_build_refuses_inventory_item_without_draft_decision():
    with pytest.raises(ValueError, match="without a draft decision"):
        rt.build_role_table(inv(("agent", "ghost")), DRAFT, MATRIX, PROBE)


def test_build_refuses_merge_into_non_final_role():
    d = draft(("agent", "a", "merge", "b", "r", ""), ("agent", "b", "merge", "a", "r", ""))
    with pytest.raises(ValueError, match="merge target"):
        rt.build_role_table(inv(("agent", "a"), ("agent", "b")), d, MATRIX, PROBE)


def test_build_refuses_merge_into_unknown_role():
    d = draft(("agent", "a", "merge", "nowhere", "r", ""))
    with pytest.raises(ValueError, match="merge target"):
        rt.build_role_table(inv(("agent", "a")), d, MATRIX, PROBE)


def test_built_synthetic_table_validates_clean(built):
    assert rt.validate_role_table(built, INVENTORY, MATRIX, PROBE) == []


# ------------------------------------------------------------------ validator: stricter, never looser
def problems(table, inventory=INVENTORY, matrix=MATRIX, probe=PROBE):
    return rt.validate_role_table(table, inventory, matrix, probe)


def mutate(built, key, **changes):
    table = copy.deepcopy(built)
    for e in table["entries"]:
        if (e["kind"], e["name"]) == key:
            e.update(changes)
    table["counts"] = rt._counts(table["entries"])
    return table


def has(problem_list, fragment):
    return any(fragment in p for p in problem_list)


def test_validator_flags_head_and_digest_drift(built):
    assert has(problems(built, probe={"aeve_head": "9" * 40, "matrix": {"digest_sha256": PIN_DIGEST}}), "head differs")
    assert has(problems(built, probe={"aeve_head": PIN_HEAD, "matrix": {"digest_sha256": "9" * 64}}), "digest differs")


@pytest.mark.parametrize("bad", [None, [], "x", {"version": 99}, {}])
def test_validator_rejects_wrong_version_or_shape(bad):
    assert problems(bad) == ["table: missing or wrong version"]


def test_validator_entries_not_a_list(built):
    t = dict(built, entries="nope")
    assert has(problems(t), "entries is not a list")


def test_validator_claiming_coverage_for_a_role_without_executors(built):
    t = mutate(built, ("agent", "profile-no-exec"), coverage_state="COVERED_PARTIAL")
    assert has(problems(t), "claims coverage but the matrix lists no executor")


def test_validator_executor_list_must_equal_matrix(built):
    t = mutate(built, ("agent", "python-reviewer"), executors=["g2.a"])
    assert has(problems(t), "executors differ from the matrix")
    t = mutate(built, ("agent", "python-reviewer"), executors=["g2.a", "g2.b", "g9.invented"])
    assert has(problems(t), "executors differ from the matrix")


def test_validator_executor_order_does_not_matter(built):
    t = mutate(built, ("agent", "python-reviewer"), executors=["g2.b", "g2.a"])
    assert problems(t) == []


def test_validator_not_covered_with_executors_listed(built):
    t = mutate(built, ("agent", "business-analyst"), executors=["g2.a"])
    assert has(problems(t), "executors differ") and has(problems(t), "NOT_APPLICABLE but executors are listed")


def test_validator_no_profile_claim_contradicted_by_matrix(built):
    t = mutate(built, ("agent", "profile-no-exec"), coverage_state="NOT_COVERED_NO_PROFILE")
    assert has(problems(t), "says no AEVE profile but the matrix has one")


def test_validator_local_class_cannot_be_not_applicable(built):
    t = mutate(built, ("agent", "python-reviewer"), coverage_state="NOT_APPLICABLE", executors=[])
    assert has(problems(t), "local class cannot be NOT_APPLICABLE")


def test_validator_non_local_class_must_be_not_applicable(built):
    t = mutate(built, ("agent", "business-analyst"), coverage_state="NOT_COVERED_NO_PROFILE")
    assert has(problems(t), "non-local class must be NOT_APPLICABLE")


def test_validator_bad_class_and_state(built):
    t = mutate(built, ("agent", "stale"), **{"class": "WIZARD"})
    assert has(problems(t), "bad class")
    t = mutate(built, ("agent", "stale"), coverage_state="MAYBE")
    assert has(problems(t), "bad coverage_state")


def test_validator_missing_unknown_and_duplicate_entries(built):
    t = copy.deepcopy(built)
    dropped = t["entries"].pop(0)
    t["counts"] = rt._counts(t["entries"])
    assert has(problems(t), f"missing entry ('{dropped['kind']}', '{dropped['name']}')")
    t = copy.deepcopy(built)
    t["entries"].append(dict(t["entries"][0], name="intruder", canonical_role="intruder"))
    t["counts"] = rt._counts(t["entries"])
    assert has(problems(t), "unknown entry")
    t = copy.deepcopy(built)
    t["entries"].append(copy.deepcopy(t["entries"][0]))
    t["counts"] = rt._counts(t["entries"])
    assert has(problems(t), "duplicate entry")


def test_validator_counts_drift(built):
    t = copy.deepcopy(built)
    t["counts"]["total"] += 1
    assert has(problems(t), "stored counts differ")
    t = copy.deepcopy(built)
    t["counts"]["by_class"]["LOCAL"] = t["counts"]["by_class"].get("LOCAL", 0) + 1
    assert has(problems(t), "stored counts differ")


def test_validator_canonical_role_must_be_known_name(built):
    t = mutate(built, ("agent", "code-architect"), canonical_role="ghost")
    assert has(problems(t), "not a known role name")


def test_validator_alias_class_must_match_canonical(built):
    t = mutate(built, ("agent", "code-architect"), **{"class": "LOCAL"})
    assert has(problems(t), "class differs from its canonical role")


def test_validator_canonical_chain_detected(built):
    # alias pointing at an alias
    t = mutate(built, ("skill", "python-reviewer"), canonical_role="code-architect")
    assert has(problems(t), "canonical_role chain")


def test_validator_executors_not_a_list(built):
    t = mutate(built, ("agent", "stale"), executors="g2.a")
    assert has(problems(t), "executors is not a list")


def test_class_describes_the_role_and_coverage_state_what_the_matrix_covers(built):
    """Operator decision: a LOCAL class with a NOT_COVERED_* state is valid; the router answers NOT_COVERED for it."""
    from uc import router
    entry = by_key(built)[("agent", "profile-no-exec")]
    assert entry["coverage_state"].startswith("NOT_COVERED") and entry["class"] == "LOCAL"
    assert problems(built) == []
    result = router.normalize({"request_id": "r", "base_revision": HEAD_FOR_ROUTER, "changed_paths": ["a.py"], "roles": ["profile-no-exec"]}, built, None, None)
    assert result["roles"][0]["status"] == "NOT_COVERED" and result["roles"][0]["uncovered"] == ["no-executor"]


HEAD_FOR_ROUTER = "a" * 40


# ------------------------------------------------------------------ committed catalog/role_table.json (no AEVE)
@pytest.fixture(scope="module")
def committed():
    return S.real_table()


@pytest.fixture(scope="module")
def inventory():
    return json.loads((S.REPO_ROOT / "catalog" / "inventory.json").read_text(encoding="utf-8"))


def test_committed_counts_match_recomputed(committed):
    assert committed["counts"] == rt._counts(committed["entries"])
    assert committed["counts"]["total"] == len(committed["entries"]) == 93


def test_committed_table_covers_exactly_the_inventory(committed, inventory):
    got = sorted((e["kind"], e["name"]) for e in committed["entries"])
    want = sorted((i["kind"], i["name"]) for i in inventory["entries"])
    assert got == want
    assert len(set(got)) == len(got)


def test_committed_pin_shape(committed):
    pin = committed["aeve_pin"]
    assert len(pin["head"]) == 40 and len(pin["matrix_digest_sha256"]) == 64


def test_committed_state_class_executor_invariants(committed):
    names = {e["name"] for e in committed["entries"]}
    for e in committed["entries"]:
        label = (e["kind"], e["name"])
        assert e["class"] in rt.CLASSES and e["coverage_state"] in rt.COVERAGE_STATES, label
        assert e["canonical_role"] in names, label
        if e["coverage_state"] == "COVERED_PARTIAL":
            assert e["executors"], label
        else:
            assert e["executors"] == [], label
        if e["class"] in ("MODEL_ONLY", "OUT_OF_SCOPE"):
            assert e["coverage_state"] == "NOT_APPLICABLE" and e["executors"] == [], label
        if e["class"] in ("LOCAL", "LOCAL_PLUS_MODEL"):
            assert e["coverage_state"] != "NOT_APPLICABLE", label
        if e["coverage_state"] == "NOT_COVERED_NO_PROFILE":
            assert e["aeve_profile"] is None, label


def test_committed_aliases_share_class_and_executors_with_their_canonical_role(committed):
    canon = {}
    for e in committed["entries"]:
        if e["name"] == e["canonical_role"]:
            canon.setdefault(e["name"], []).append(e)
    for e in committed["entries"]:
        if e["name"] != e["canonical_role"]:
            peers = canon[e["canonical_role"]]
            assert any(p["class"] == e["class"] and p["executors"] == e["executors"] for p in peers), e["name"]


def test_committed_upgrades_record_evidence(committed):
    for e in committed["entries"]:
        if e["class_upgraded_by_evidence"]:
            assert e["draft_class"] in ("MODEL_ONLY", "OUT_OF_SCOPE") and e["class"] == "LOCAL_PLUS_MODEL" and e["executors"]


def test_committed_table_loaded_by_router_lookup_resolves_agent_first(committed):
    from uc import router
    assert router._lookup(committed, "ml-engineer")["kind"] == "agent"
    assert router._lookup(committed, "no-such-role") is None
