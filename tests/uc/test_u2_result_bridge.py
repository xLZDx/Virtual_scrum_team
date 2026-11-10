"""U2-6 (B): negative cases for the U2 bridge fields of uc.role-result.v1.

Covers role_table_sha256, aeve_head (40 lowercase hex only), purpose and changed_paths_sha256 (missing,
malformed, unknown key), the per-role model_residual rule (sorted, unique, at most 8), the router refusal
ROLE_TABLE_HASH_MISSING (no probe and no executor run), and the exact-bytes meaning of role_table_sha256.
Synthetic inputs only; stub 'aeve' scripts; no real AEVE, no network.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from uc import contracts, router

from tests.uc import ucsupport as S

TABLE = S.real_table()
TABLE_SHA = S.real_table_sha256()
PIN = TABLE["aeve_pin"]

BRIDGE_FIELDS = ("role_table_sha256", "aeve_head", "purpose", "changed_paths_sha256")


def refused(doc):
    with pytest.raises(contracts.ContractError) as info:
        contracts.validate_result(doc)
    return info.value


def test_the_baseline_result_is_valid():
    assert contracts.validate_result(S.valid_result())["role_table_sha256"] == S.HASH_C


# ------------------------------------------------------------------------------ missing / unknown
@pytest.mark.parametrize("field", BRIDGE_FIELDS)
def test_a_result_without_a_bridge_field_is_refused(field):
    doc = S.valid_result()
    del doc[field]
    err = refused(doc)
    assert (err.code, err.where) == ("MISSING_FIELD", f"result.{field}")


def test_a_result_without_any_bridge_field_names_the_first_missing_one():
    doc = S.valid_result()
    for field in BRIDGE_FIELDS:
        del doc[field]
    assert refused(doc).code == "MISSING_FIELD"


@pytest.mark.parametrize("extra", ["role_table_sha", "aeve_pin", "purposes", "changed_paths", "Purpose", "signature", ""])
def test_a_result_with_an_unknown_top_level_key_is_refused(extra):
    doc = S.valid_result()
    doc[extra] = S.HASH_A
    err = refused(doc)
    assert (err.code, err.where) == ("UNKNOWN_FIELD", "result.[unknown field]")


def test_a_v0_result_without_bridge_fields_is_not_accepted_under_the_v1_schema_name():
    doc = S.valid_result()
    for field in BRIDGE_FIELDS:
        del doc[field]
    assert refused(doc).code in ("MISSING_FIELD", "UNKNOWN_FIELD")


# ------------------------------------------------------------------------------------- hash fields
BAD_HASHES = [
    ("empty", ""), ("short", "b" * 63), ("long", "b" * 65), ("upper", "B" * 64), ("mixed-case", "b" * 63 + "F"),
    ("non-hex", "g" * 64), ("prefix", "sha256:" + "b" * 64), ("padded", " " + "b" * 63),
    ("trailing-newline", "b" * 64 + "\n"), ("trailing-space", "b" * 64 + " "), ("embedded-nul", "b" * 63 + "\x00"),
    ("unicode-digit", "٢" * 64), ("fullwidth", "ｂ" * 64),
]
BAD_TYPES = [("none", None), ("int", 7), ("bool", True), ("list", ["b" * 64]), ("dict", {"x": "b" * 64}), ("bytes", b"b" * 64)]


@pytest.mark.parametrize("field", ["role_table_sha256", "changed_paths_sha256"])
@pytest.mark.parametrize("label,value", BAD_HASHES, ids=[b[0] for b in BAD_HASHES])
def test_a_malformed_hash_is_refused(field, label, value):
    doc = S.valid_result(**{field: value})
    err = refused(doc)
    assert err.where == f"result.{field}" and err.code in ("BAD_FORMAT", "BAD_STRING")


@pytest.mark.parametrize("field", ["role_table_sha256", "changed_paths_sha256", "aeve_head", "purpose"])
@pytest.mark.parametrize("label,value", BAD_TYPES, ids=[b[0] for b in BAD_TYPES])
def test_a_wrongly_typed_bridge_field_is_refused(field, label, value):
    err = refused(S.valid_result(**{field: value}))
    assert err.where == f"result.{field}"
    assert err.code in ("NOT_A_STRING", "NOT_ALLOWED_VALUE")


# ------------------------------------------------------------------------- aeve_head: 40-hex only
@pytest.mark.parametrize("label,value", [
    ("64-hex", "d" * 64), ("39", "d" * 39), ("41", "d" * 41), ("upper", "D" * 40), ("empty", ""),
    ("non-hex", "z" * 40), ("newline", "d" * 40 + "\n"), ("space", " " + "d" * 39), ("symbolic", "HEAD"),
    ("branch", "main"),
])
def test_aeve_head_accepts_only_a_40_character_lowercase_hex_commit(label, value):
    err = refused(S.valid_result(aeve_head=value))
    assert err.where == "result.aeve_head" and err.code in ("BAD_FORMAT", "BAD_STRING")


def test_aeve_head_accepts_a_real_40_hex_head_while_base_revision_still_takes_64_hex():
    assert contracts.validate_result(S.valid_result(aeve_head="0123456789abcdef" * 2 + "01234567"))
    assert contracts.validate_result(S.valid_result(base_revision="e" * 64))  # unchanged rule for the other head


# ---------------------------------------------------------------------------------------- purpose
@pytest.mark.parametrize("purpose", ["advisory", "receipt"])
def test_both_purposes_are_accepted(purpose):
    assert contracts.validate_result(S.valid_result(purpose=purpose))["purpose"] == purpose


@pytest.mark.parametrize("value", ["", "Receipt", "RECEIPT", "advisory ", " receipt", "audit", "receipt\n", "advisory,receipt"])
def test_an_unknown_purpose_is_refused(value):
    err = refused(S.valid_result(purpose=value))
    assert (err.code, err.where) == ("NOT_ALLOWED_VALUE", "result.purpose")


# --------------------------------------------------------------------------------- model_residual
def _with_residual(residual, **role_over):
    return S.valid_result(roles=[S.valid_role_entry(model_residual=residual, **role_over)])


@pytest.mark.parametrize("residual", [
    ["b-two", "a-one"],                       # unsorted
    ["a-one", "a-one"],                       # duplicate
    ["a-one", "b-two", "a-one"],              # duplicate, unsorted
    ["a_b", "a-b"],                           # '_' sorts after '-': descending
    [f"r{i}" for i in range(9)],              # nine > MAX_MODEL_RESIDUAL
    [f"r{i}" for i in range(8, -1, -1)],      # nine and unsorted
])
def test_a_model_residual_that_is_not_sorted_unique_and_at_most_eight_is_refused(residual):
    err = refused(_with_residual(residual))
    assert (err.code, err.where) == ("BAD_MODEL_RESIDUAL", "result.roles[0].model_residual")


@pytest.mark.parametrize("residual", [[], ["a-one"], ["a-b", "a_b"], [f"r{i}" for i in range(8)]])
def test_a_sorted_unique_residual_of_up_to_eight_tokens_is_accepted(residual):
    assert contracts.validate_result(_with_residual(residual))["roles"][0]["model_residual"] == residual


def test_the_residual_is_never_repaired_or_reordered():
    doc = _with_residual(["b-two", "a-one"])
    before = copy.deepcopy(doc)
    refused(doc)
    assert doc == before


@pytest.mark.parametrize("bad", ["Upper", "has space", "", "-lead", "a" * 65, "ü", "a|b"])
def test_a_residual_token_outside_the_token_pattern_is_refused(bad):
    err = refused(_with_residual([bad]))
    assert err.where == "result.roles[0].model_residual[0]" and err.code in ("BAD_FORMAT", "BAD_STRING")


@pytest.mark.parametrize("bad", [None, "model-judgment", {"a": 1}, 3])
def test_a_residual_that_is_not_a_list_is_refused(bad):
    assert refused(_with_residual(bad)).code == "NOT_A_LIST"


@pytest.mark.parametrize("bad", [None, 1, True, ["x"]])
def test_a_residual_token_that_is_not_a_string_is_refused(bad):
    assert refused(_with_residual([bad])).code == "NOT_A_STRING"


def test_a_clean_role_with_a_residual_is_refused():
    entry = S.valid_role_entry(**{"class": "LOCAL"}, status="CLEAN", model_residual=["model-judgment"],
                               executors=[{"id": "g2.python-rules", "status": "COMPLETE", "snapshot_hash": S.HASH_A}])
    err = refused(S.valid_result(roles=[entry], exit_code=0))
    assert err.code == "CLEAN_WITH_OPEN_ITEMS"


# ---------------------------------------------------------------- router.review: ROLE_TABLE_HASH_MISSING
@pytest.fixture()
def world(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    probe_calls = []

    def fake_probe(aeve_root, python=None, timeout=60.0):
        probe_calls.append(str(aeve_root))
        return {"aeve_head": "9" * 40, "matrix": {"digest_sha256": PIN["matrix_digest_sha256"]},
                "tracked_dirty_paths": 0, "untracked_paths": 0, "untracked_source_paths": 0}

    monkeypatch.setattr(router.aeve_probe, "probe", fake_probe)
    marker = tmp_path / "executor-ran.marker"
    stub = S.write_stub(tmp_path / "stubs", f"open({str(marker)!r}, 'w').write('ran')\nemit(good())")
    return {"root": root, "aeve": tmp_path / "aeve", "state": tmp_path / "state", "probe_calls": probe_calls,
            "marker": marker, "stub": stub}


def _review(world, table_sha, request=None):
    request = request or S.valid_request(str(world["root"]), changed_paths=["a.py"], roles=["python-reviewer"])
    return router.review(request, table=TABLE, table_sha256=table_sha, aeve_root=world["aeve"],
                         state_dir=world["state"], allowed_roots=[str(world["root"])],
                         command_prefix=world["stub"], timeout=20.0)


MISSING_DIGESTS = [
    ("none", None), ("empty", ""), ("zero", "0" * 64), ("short", TABLE_SHA[:63]), ("long", TABLE_SHA + "0"),
    ("upper", TABLE_SHA.upper()), ("non-hex", "g" * 64), ("int", 5), ("bytes", TABLE_SHA.encode()),
    ("prefixed", "sha256:" + TABLE_SHA), ("newline", TABLE_SHA + "\n"),
]


@pytest.mark.parametrize("label,digest", MISSING_DIGESTS, ids=[d[0] for d in MISSING_DIGESTS])
def test_review_without_a_valid_table_digest_blocks_before_any_probe_or_executor(world, label, digest):
    out = _review(world, digest)
    assert out["schema_version"] == contracts.BLOCKED_SCHEMA
    assert out["status"] == "BLOCKED" and out["reason"] == "ROLE_TABLE_HASH_MISSING"
    assert contracts.validate_blocked(out) == out
    assert world["probe_calls"] == []  # the AEVE probe was never started
    assert not world["marker"].exists()  # the executor stub never ran
    assert not (world["state"] / "uc-requests").exists()  # nothing was recorded for this request id


def test_review_omitting_table_sha256_entirely_blocks_the_same_way(world):
    request = S.valid_request(str(world["root"]), changed_paths=["a.py"], roles=["python-reviewer"])
    out = router.review(request, table=TABLE, aeve_root=world["aeve"], state_dir=world["state"],
                        allowed_roots=[str(world["root"])], command_prefix=world["stub"], timeout=20.0)
    assert out["reason"] == "ROLE_TABLE_HASH_MISSING" and world["probe_calls"] == [] and not world["marker"].exists()


def test_a_blocked_missing_digest_does_not_poison_the_request_id(world):
    assert _review(world, None)["reason"] == "ROLE_TABLE_HASH_MISSING"
    # same id, now with the digest: the request reaches the probe (which here reports a different AEVE head)
    out = _review(world, TABLE_SHA)
    assert out["reason"] == "AEVE_PIN_MISMATCH"
    assert len(world["probe_calls"]) == 1 and not world["marker"].exists()


def test_the_digest_check_comes_after_request_validation_and_before_the_probe(world):
    bad = S.valid_request(str(world["root"]), roles=[])
    out = _review(world, None, request=bad)
    assert out["reason"] == "INVALID_REQUEST"  # request problems are reported first, still without a probe
    assert world["probe_calls"] == []


# ------------------------------------------------------------- the digest is the digest of the file bytes
def test_load_table_with_digest_hashes_the_exact_file_bytes():
    table, digest = router.load_table_with_digest(S.TABLE_PATH)
    assert digest == hashlib.sha256(S.TABLE_PATH.read_bytes()).hexdigest() == TABLE_SHA
    assert table == json.loads(S.TABLE_PATH.read_text(encoding="utf-8"))


def test_the_digest_is_not_a_digest_of_the_parsed_table(tmp_path):
    raw = S.TABLE_PATH.read_bytes()
    reformatted = json.dumps(json.loads(raw.decode("utf-8")), indent=1, sort_keys=True).encode("utf-8")
    assert reformatted != raw
    path = tmp_path / "role_table.json"
    path.write_bytes(reformatted)
    table, digest = router.load_table_with_digest(path)
    assert table == TABLE  # identical content ...
    assert digest == hashlib.sha256(reformatted).hexdigest() != TABLE_SHA  # ... different bytes, different digest
    assert digest != hashlib.sha256(json.dumps(table, sort_keys=True).encode("utf-8")).hexdigest()


def test_a_one_byte_change_to_the_table_file_changes_the_digest(tmp_path):
    path = tmp_path / "role_table.json"
    path.write_bytes(S.TABLE_PATH.read_bytes() + b" ")
    assert router.load_table_with_digest(path)[1] != TABLE_SHA


def test_load_table_with_digest_refuses_a_file_that_is_not_utf8_json(tmp_path):
    path = tmp_path / "role_table.json"
    path.write_bytes(b"\xff\xfe{")
    with pytest.raises(ValueError):
        router.load_table_with_digest(path)


# ------------------------------------------------------------------- normalize copies the bridge facts
def _norm(paths, purpose="advisory", sha=TABLE_SHA, head=None):
    request = {"request_id": "req-1", "base_revision": S.HEAD, "changed_paths": list(paths), "roles": ["python-reviewer"],
               "purpose": purpose}
    ids = sorted({x for e in TABLE["entries"] if e["name"] == "python-reviewer" for x in e["executors"]})
    response = S.aeve_response(executor_ids=ids)
    return router.normalize(request, TABLE, response, None, role_table_sha256=sha, aeve_head=head or PIN["head"])


@pytest.mark.parametrize("purpose", ["advisory", "receipt"])
def test_normalize_copies_purpose_and_the_table_and_aeve_pins(purpose):
    result = _norm(["src/a.py"], purpose)
    assert contracts.validate_result(result)
    assert (result["purpose"], result["role_table_sha256"], result["aeve_head"]) == (purpose, TABLE_SHA, PIN["head"])


def test_changed_paths_sha256_is_order_independent_and_matches_the_vst_canonical_digest():
    from tools.vst import contracts as vst_contracts

    forward = _norm(["docs/b.md", "src/a.py"])["changed_paths_sha256"]
    backward = _norm(["src/a.py", "docs/b.md"])["changed_paths_sha256"]
    assert forward == backward
    assert forward == hashlib.sha256(vst_contracts.canonical_bytes(["docs/b.md", "src/a.py"])).hexdigest()


def test_changed_paths_sha256_differs_for_a_narrower_or_different_path_set():
    full = _norm(["docs/b.md", "src/a.py"])["changed_paths_sha256"]
    assert _norm(["src/a.py"])["changed_paths_sha256"] != full
    assert _norm(["docs/b.md", "src/c.py"])["changed_paths_sha256"] != full
    assert _norm(["docs/b.md", "src/a.py", "src/c.py"])["changed_paths_sha256"] != full


def test_normalize_never_emits_a_result_the_contract_would_refuse_for_a_bad_pin():
    # a malformed pin passed by a (buggy) library caller is caught by the contract check that review() runs
    for bad in ("", "0x" + "1" * 62, "B" * 64):
        with pytest.raises(contracts.ContractError):
            contracts.validate_result(_norm(["src/a.py"], sha=bad))
    with pytest.raises(contracts.ContractError):
        contracts.validate_result(_norm(["src/a.py"], head="d" * 64))
