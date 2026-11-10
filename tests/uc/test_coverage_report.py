"""U2-6 (A): negative-case catalog for tools/uc/coverage_report.py (task U2-5 product code).

Every refusal code of CoverageReportError is provoked by a synthetic input, the verdict-word table is pinned,
and every rendering (text and markdown) is scanned for pass-like tokens over all status / class / residual /
uncovered / findings combinations the U1 result contract accepts. No product code is mutated, no model, no network.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import pathlib
import unicodedata

import pytest

from tools.uc import contracts, coverage_report as cr

from tests.uc import ucsupport as S

TABLE = S.real_table()
TABLE_SHA = S.real_table_sha256()
LOCAL_ROLE = "opensource-sanitizer"  # class LOCAL in catalog/role_table.json (asserted below)
FINDING = S.valid_finding(severity="MAJOR")


def _exec(status="COMPLETE", ident="g2.python-rules"):
    return {"id": ident, "status": status, "snapshot_hash": S.HASH_A}


def entry(role, klass, status, *, findings=(), uncovered=(), residual=(), executors=None, canonical=None):
    return S.valid_role_entry(
        role=role, canonical_role=canonical or role, **{"class": klass}, status=status,
        executors=executors if executors is not None else [_exec()],
        findings=list(findings), uncovered=list(uncovered), model_residual=list(residual),
    )


def result_of(*entries, table_sha=TABLE_SHA, **over):
    clean = all(e["status"] == "CLEAN" for e in entries)
    doc = S.valid_result(roles=list(entries), exit_code=0 if clean else 3, role_table_sha256=table_sha)
    doc.update(over)
    return doc


def clean_local(role=LOCAL_ROLE):
    return entry(role, "LOCAL", "CLEAN")


# One factory per accepted (status, class, residual, uncovered, findings) shape; names are distinct per slot.
SHAPES = {
    "local-clean": lambda: clean_local(),
    "local-findings": lambda: entry(LOCAL_ROLE, "LOCAL", "FINDINGS", findings=[FINDING]),
    "local-partial-uncovered": lambda: entry(LOCAL_ROLE, "LOCAL", "PARTIAL", uncovered=["unit-gap"]),
    "local-blocked": lambda: entry(LOCAL_ROLE, "LOCAL", "BLOCKED", executors=[_exec("BLOCKED")]),
    "lpm-partial-residual": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["model-judgment"]),
    "lpm-partial-nothing-open": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL"),
    "lpm-partial-uncovered": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", uncovered=["unit-gap"]),
    "lpm-partial-findings-residual": lambda: entry(
        "python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", findings=[FINDING], residual=["model-judgment"]),
    "lpm-findings": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "FINDINGS", findings=[FINDING],
                                  residual=["a-one", "b-two"]),
    "lpm-not-covered": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "NOT_COVERED", uncovered=["all"],
                                     executors=[_exec("NOT_COVERED")]),
    "lpm-not-run": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "NOT_RUN", executors=[_exec("NOT_RUN")]),
    "lpm-blocked": lambda: entry("python-reviewer", "LOCAL_PLUS_MODEL", "BLOCKED", executors=[]),
    "model-only-not-covered": lambda: entry("planner", "MODEL_ONLY", "NOT_COVERED", executors=[],
                                            residual=["whole-role"]),
    "out-of-scope-not-covered": lambda: entry("loop-operator", "OUT_OF_SCOPE", "NOT_COVERED", executors=[]),
}


def role_name_of(shape: str) -> str:
    return SHAPES[shape]()["role"]


def _combos():
    names = list(SHAPES)
    singles = [(n,) for n in names]
    pairs = [p for p in itertools.combinations(names, 2) if role_name_of(p[0]) != role_name_of(p[1])]
    return singles + pairs


COMBOS = _combos()


def _combo_id(combo):
    return "+".join(combo)


def report_of(*shapes):
    return cr.render_coverage_report(result_of(*[SHAPES[s]() for s in shapes]), TABLE)


def _row_start(text: str, offset: int) -> str:
    return text[text.rfind("\n", 0, offset) + 1:]


def test_fixture_role_classes_match_the_committed_table():
    classes = {e["name"]: (e["class"], e["canonical_role"]) for e in TABLE["entries"]}
    assert classes[LOCAL_ROLE] == ("LOCAL", LOCAL_ROLE)
    assert classes["python-reviewer"][0] == "LOCAL_PLUS_MODEL"
    assert classes["planner"][0] == "MODEL_ONLY"
    assert classes["loop-operator"][0] == "OUT_OF_SCOPE"


# --------------------------------------------------------------------------- scan every rendering
@pytest.mark.parametrize("combo", COMBOS, ids=_combo_id)
def test_every_rendering_carries_a_pass_word_only_at_a_fully_clean_verdict_cell(combo):
    report = report_of(*combo)
    clean_roles = [e["role"] for e in report["roles"] if cr.is_fully_clean(e)]
    for render, prefix in ((cr.render_text, ""), (cr.render_markdown, "| ")):
        text = render(report)  # must not raise: a built report is honest by construction
        hits = cr.scan_pass_tokens(text)
        assert len(hits) == len(clean_roles)  # nothing but the verdict word of each fully clean role
        for token, offset in hits:
            assert token == "CLEAN"
            assert text[offset:offset + len(cr.CLEAN_VERDICT)] == cr.CLEAN_VERDICT
            row = _row_start(text, offset)
            assert any(row.startswith(prefix + name) for name in clean_roles)
        # same answer from the second (NFKC) pass: nothing hidden in the normalized text either
        normal = unicodedata.normalize("NFKC", text).casefold()
        assert len(cr.scan_pass_tokens(normal)) == len(clean_roles)
        if not clean_roles:
            assert cr.CLEAN_VERDICT not in text and hits == []
        cr.assert_no_pass_token(text, report)


@pytest.mark.parametrize("combo", [c for c in COMBOS if len(c) == 1 and c != ("local-clean",)], ids=_combo_id)
def test_a_not_fully_clean_report_never_gets_clean_local_from_a_forged_rendering(combo):
    report = report_of(*combo)
    text = cr.render_text(report)
    for forged in (text + "all checks PASS\n", text.replace(report["roles"][0]["verdict_word"], cr.CLEAN_VERDICT),
                   text + "CLEAN_LOCAL\n"):
        with pytest.raises(cr.CoverageReportError) as info:
            cr.assert_no_pass_token(forged, report)
        assert info.value.code == "PASS_TOKEN_IN_PARTIAL_REPORT"


def test_the_clean_exemption_is_positional_not_a_substring_whitelist():
    report = report_of("local-clean", "lpm-partial-residual")
    text = cr.render_text(report)
    cr.assert_no_pass_token(text, report)  # exact layout: the clean row's own verdict cell is exempt
    # the same words one character to the side, appended, or moved into the partial role's row are all refused
    moved = text.replace("MODEL_RESIDUAL_OPEN", "CLEAN_LOCAL", 1)
    for forged in (moved, text + "CLEAN_LOCAL", " " + text, text.replace("\n", "\r\n")):
        with pytest.raises(cr.CoverageReportError) as info:
            cr.assert_no_pass_token(forged, report)
        assert info.value.code == "PASS_TOKEN_IN_PARTIAL_REPORT"


def test_a_non_string_rendering_is_refused_as_bad_report():
    with pytest.raises(cr.CoverageReportError) as info:
        cr.assert_no_pass_token(b"CLEAN_LOCAL", report_of("local-clean"))
    assert info.value.code == "BAD_REPORT"


# ------------------------------------------------------------------ scanner boundaries (pass words)
@pytest.mark.parametrize("text", [
    "PASS", "pass", "Passed", "ok", "OK1", "pass2", "clean-code", "CLEAN_LOCAL", "all  clear", "ALL\tCLEAR",
    "x_done", "done.", "(good)", "LGTM", "success", "Succeeded",
    "готово", "ГОТОВО", "Пройдено", "успешно", "ок", "чисто", "проверено", "безопасно", "зелёный",
])
def test_scanner_hits_pass_words_including_separators_and_cyrillic(text):
    assert cr.scan_pass_tokens(text), text


@pytest.mark.parametrize("text", [
    "compass", "passive", "bypass", "okapi", "token", "greenfield", "abandoned", "goodwill", "finest", "fineness",
    "cleanse", "readyness", "unsafe", "fixedpoint", "completeness", "oksana",
    "прохожий", "пройденный", "окно", "чистота", "готовность", "зелёнка", "неок",
    "findings", "uncovered", "model_residual", "highest_severity", "canonical", "snapshot",
])
def test_scanner_ignores_neutral_lookalikes(text):
    assert cr.scan_pass_tokens(text) == [], text


def test_neutral_lookalike_ids_render_without_raising_for_a_partial_report():
    result = result_of(entry("compass-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["greenfield", "okapi"],
                             uncovered=["bypass-gap"]))
    table = {"entries": [{"name": "compass-reviewer", "class": "LOCAL_PLUS_MODEL", "canonical_role": "compass-reviewer"}]}
    report = cr.render_coverage_report(result, table)
    cr.check_ids_have_no_pass_word(report)
    assert cr.scan_pass_tokens(cr.render_text(report)) == []
    assert cr.scan_pass_tokens(cr.render_markdown(report)) == []


@pytest.mark.parametrize("field,value", [
    ("model_residual", ["model-ok"]), ("uncovered", ["pass-1"]), ("uncovered", ["all.done"]),
    ("model_residual", ["is-clean"]), ("uncovered", ["verified_gap"]),
])
def test_pass_word_in_an_identifier_is_refused_by_the_id_check_and_the_rendering(field, value):
    table = {"entries": [{"name": "python-reviewer", "class": "LOCAL_PLUS_MODEL", "canonical_role": "python-reviewer"}]}
    e = entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", **{("residual" if field == "model_residual" else field): value})
    report = cr.render_coverage_report(result_of(e), table)
    with pytest.raises(cr.CoverageReportError) as info:
        cr.check_ids_have_no_pass_word(report)
    assert info.value.code == "PASS_WORD_IN_ID"
    for render in (cr.render_text, cr.render_markdown):
        with pytest.raises(cr.CoverageReportError) as info:
            render(report)
        assert info.value.code == "PASS_TOKEN_IN_PARTIAL_REPORT"


def test_pass_word_in_request_id_and_executor_id_is_refused():
    for over in ({"request_id": "run-ok"}, {"request_id": "pass"}):
        report = cr.render_coverage_report(result_of(SHAPES["lpm-partial-residual"](), **over), TABLE)
        with pytest.raises(cr.CoverageReportError) as info:
            cr.check_ids_have_no_pass_word(report)
        assert info.value.code == "PASS_WORD_IN_ID"
    e = entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["model-judgment"],
              executors=[_exec(ident="g2.done-rules")])
    report = cr.render_coverage_report(result_of(e), TABLE)
    with pytest.raises(cr.CoverageReportError) as info:
        cr.check_ids_have_no_pass_word(report)
    assert info.value.code == "PASS_WORD_IN_ID"


def test_a_pass_word_in_a_fully_clean_report_id_is_still_caught_by_the_id_check():
    report = cr.render_coverage_report(result_of(clean_local(), request_id="all-ok"), TABLE)
    with pytest.raises(cr.CoverageReportError) as info:
        cr.check_ids_have_no_pass_word(report)
    assert info.value.code == "PASS_WORD_IN_ID"


@pytest.mark.parametrize("hidden", ["ＰＡＳＳ", "ｏｋ", "ＤＯＮＥ"])
def test_nfkc_folded_pass_words_in_a_forged_rendering_are_caught_on_the_second_pass(hidden):
    report = report_of("lpm-partial-residual")
    assert cr.scan_pass_tokens(hidden) == []  # invisible to the plain scanner ...
    with pytest.raises(cr.CoverageReportError) as info:  # ... but not to the normalized one
        cr.assert_no_pass_token(cr.render_text(report) + hidden, report)
    assert info.value.code == "PASS_TOKEN_IN_PARTIAL_REPORT" and "normalized" in info.value.where


@pytest.mark.parametrize("bad_id", ["готово", "ок", "Пройдено"])
def test_cyrillic_ids_are_refused_at_both_contract_and_report_level(bad_id):
    with pytest.raises(cr.CoverageReportError) as info:
        cr.render_coverage_report(result_of(entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", residual=[bad_id])), TABLE)
    assert info.value.code == "INVALID_RESULT"
    report = report_of("lpm-partial-residual")
    forged = copy.deepcopy(report)
    forged["roles"][0]["model_residual"] = [bad_id]
    for fn in (cr.render_text, cr.render_markdown, cr.check_ids_have_no_pass_word):
        with pytest.raises(cr.CoverageReportError) as info:
            fn(forged)
        assert info.value.code == "BAD_REPORT"


# --------------------------------------------------------------------------- verdict word table
VERDICT_TABLE = [
    # shape, expected word
    ("local-clean", "CLEAN_LOCAL"),
    ("local-findings", "FINDINGS"),
    ("local-partial-uncovered", "PARTIAL_CODE_ONLY"),
    ("local-blocked", "BLOCKED"),
    ("lpm-partial-residual", "MODEL_RESIDUAL_OPEN"),
    ("lpm-partial-nothing-open", "PARTIAL_CODE_ONLY"),
    ("lpm-partial-uncovered", "PARTIAL_CODE_ONLY"),
    ("lpm-partial-findings-residual", "FINDINGS"),
    ("lpm-findings", "FINDINGS"),
    ("lpm-not-covered", "NOT_COVERED"),
    ("lpm-not-run", "NOT_COVERED"),
    ("lpm-blocked", "BLOCKED"),
    ("model-only-not-covered", "NOT_COVERED"),
    ("out-of-scope-not-covered", "NOT_COVERED"),
]


def test_every_shape_has_a_verdict_row():
    assert {s for s, _ in VERDICT_TABLE} == set(SHAPES)


@pytest.mark.parametrize("shape,word", VERDICT_TABLE)
def test_verdict_word_table(shape, word):
    report = report_of(shape)
    assert report["roles"][0]["verdict_word"] == word
    assert word in cr.VERDICT_WORDS
    assert cr.is_fully_clean(report["roles"][0]) is (word == "CLEAN_LOCAL")


def test_clean_local_is_reachable_only_for_a_fully_clean_local_role():
    reached = {s for s, w in VERDICT_TABLE if w == "CLEAN_LOCAL"}
    assert reached == {"local-clean"}


def test_a_local_plus_model_role_can_never_be_clean_local():
    # status CLEAN for a non-LOCAL class is refused by the U1 contract and by the report's own word computation
    with pytest.raises(cr.CoverageReportError) as info:
        cr.render_coverage_report(result_of(entry("python-reviewer", "LOCAL_PLUS_MODEL", "CLEAN")), TABLE)
    assert info.value.code == "INVALID_RESULT" and info.value.cause == "CLEAN_FOR_NON_LOCAL_CLASS"
    forged = copy.deepcopy(report_of("lpm-partial-nothing-open"))
    forged["roles"][0].update(status="CLEAN", verdict_word="CLEAN_LOCAL")
    with pytest.raises(cr.CoverageReportError) as info:
        cr.render_text(forged)
    assert info.value.code == "BAD_REPORT"


def test_highest_severity_and_covered_by_code_are_derived_from_the_result():
    findings = [S.valid_finding(severity="NIT"), S.valid_finding(severity="BLOCKER", line=9),
                S.valid_finding(severity="MINOR", line=11)]
    e = entry("python-reviewer", "LOCAL_PLUS_MODEL", "FINDINGS", findings=findings, residual=["model-judgment"],
              executors=[_exec(ident="g2.python-rules"), _exec("PARTIAL", "g2.other-rules")])
    role = cr.render_coverage_report(result_of(e), TABLE)["roles"][0]
    assert role["highest_severity"] == "BLOCKER"
    assert role["findings_count"] == 3
    assert role["covered_by_code"] == ["g2.python-rules"]  # the PARTIAL executor is not "covered by code"
    none = report_of("lpm-partial-residual")["roles"][0]
    assert none["highest_severity"] is None and none["findings_count"] == 0


# --------------------------------------------------------------------------- forged verdict_word
@pytest.mark.parametrize("shape", [s for s in SHAPES if s != "local-clean"])
def test_a_forged_clean_local_word_is_refused_everywhere(shape):
    forged = copy.deepcopy(report_of(shape))
    forged["roles"][0]["verdict_word"] = "CLEAN_LOCAL"
    for fn in (cr.render_text, cr.render_markdown, cr.check_ids_have_no_pass_word):
        with pytest.raises(cr.CoverageReportError) as info:
            fn(forged)
        assert info.value.code == "BAD_VERDICT_WORD"
        assert info.value.where == "report.roles[0].verdict_word"
    with pytest.raises(cr.CoverageReportError) as info:
        cr.assert_no_pass_token("anything", forged)
    assert info.value.code == "BAD_VERDICT_WORD"


@pytest.mark.parametrize("word", ["pass", "PASS", "OK", "clean_local", "Clean_Local", "", None, 3, ["CLEAN_LOCAL"], True])
def test_a_word_outside_the_closed_vocabulary_is_refused(word):
    forged = copy.deepcopy(report_of("lpm-partial-residual"))
    forged["roles"][0]["verdict_word"] = word
    with pytest.raises(cr.CoverageReportError) as info:
        cr.render_text(forged)
    assert info.value.code == "BAD_VERDICT_WORD"


def test_a_wrong_but_vocabulary_valid_word_is_refused():
    forged = copy.deepcopy(report_of("local-clean"))
    forged["roles"][0]["verdict_word"] = "PARTIAL_CODE_ONLY"  # understating is also a forgery
    with pytest.raises(cr.CoverageReportError) as info:
        cr.render_markdown(forged)
    assert info.value.code == "BAD_VERDICT_WORD"


# ------------------------------------------------------------------------ one test per error code
def _code(call, *args, **kw):
    with pytest.raises(cr.CoverageReportError) as info:
        call(*args, **kw)
    return info.value


@pytest.mark.parametrize("bad", [{}, [], None, "text", 7, S.valid_result(schema_version="uc.role-result.v0"),
                                 S.valid_result(aeve_head="d" * 64), S.valid_result(purpose="other"),
                                 S.valid_result(roles=[])])
def test_INVALID_RESULT(bad):
    err = _code(cr.render_coverage_report, bad, TABLE)
    assert err.code == "INVALID_RESULT" and err.cause


def test_INVALID_RESULT_carries_the_contract_code_as_cause():
    err = _code(cr.render_coverage_report, {}, TABLE)
    assert err.cause == "MISSING_FIELD"
    err = _code(cr.render_coverage_report, [], TABLE)
    assert err.cause == "NOT_AN_OBJECT"


@pytest.mark.parametrize("bad", [None, {}, [], {"entries": None}, {"entries": "x"}, {"entries": {}}, "table"])
def test_BAD_ROLE_TABLE(bad):
    assert _code(cr.render_coverage_report, result_of(clean_local()), bad).code == "BAD_ROLE_TABLE"


def test_UNKNOWN_ROLE():
    e = entry("no-such-role", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["model-judgment"])
    err = _code(cr.render_coverage_report, result_of(e), TABLE)
    assert (err.code, err.where) == ("UNKNOWN_ROLE", "result.roles[0]")
    # table entries that are not objects do not match and do not crash
    assert _code(cr.render_coverage_report, result_of(clean_local()), {"entries": [1, None, "x"]}).code == "UNKNOWN_ROLE"


def test_UNKNOWN_CLASS():
    e = entry("python-reviewer", "UNKNOWN", "NOT_COVERED", executors=[])
    assert contracts.validate_result(result_of(e))  # the U1 contract accepts UNKNOWN ...
    assert _code(cr.render_coverage_report, result_of(e), TABLE).code == "UNKNOWN_CLASS"  # ... the report does not


@pytest.mark.parametrize("klass,canonical", [("LOCAL", "python-reviewer"), ("MODEL_ONLY", "python-reviewer"),
                                             ("LOCAL_PLUS_MODEL", "architect"), ("LOCAL_PLUS_MODEL", "planner")])
def test_TABLE_MISMATCH(klass, canonical):
    e = entry("python-reviewer", klass, "NOT_COVERED", canonical=canonical, executors=[])
    assert _code(cr.render_coverage_report, result_of(e), TABLE).code == "TABLE_MISMATCH"


def test_TABLE_MISMATCH_for_an_alias_with_the_wrong_canonical_role():
    # code-architect is an alias of architect in the table; reporting it as its own canonical role is a mismatch
    e = entry("code-architect", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["model-judgment"], canonical="code-architect")
    assert _code(cr.render_coverage_report, result_of(e), TABLE).code == "TABLE_MISMATCH"
    ok = entry("code-architect", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["model-judgment"], canonical="architect")
    assert cr.render_coverage_report(result_of(ok), TABLE)["roles"][0]["canonical_role"] == "architect"


@pytest.mark.parametrize("digest", ["f" * 64, "", "0" * 64, 123, b"x"])
def test_TABLE_DIGEST_MISMATCH(digest):
    err = _code(cr.render_coverage_report, result_of(clean_local()), TABLE, digest)
    assert (err.code, err.where) == ("TABLE_DIGEST_MISMATCH", "result.role_table_sha256")
    assert cr.render_coverage_report(result_of(clean_local()), TABLE, TABLE_SHA)["role_table_sha256"] == TABLE_SHA


def _mutations():
    def role0(**kw):
        return lambda r: r["roles"][0].update(kw)

    return {
        "not-a-dict": None,
        "missing-key": lambda r: r.pop("snapshot_hash"),
        "extra-key": lambda r: r.update(extra=1),
        "roles-empty": lambda r: r.update(roles=[]),
        "roles-not-list": lambda r: r.update(roles="x"),
        "role-extra-key": role0(note="x"),
        "role-missing-key": lambda r: r["roles"][0].pop("class"),
        "request-id-non-ascii": lambda r: r.update(request_id="req-é"),
        "request-id-pipe": lambda r: r.update(request_id="req|1"),
        "request-id-newline": lambda r: r.update(request_id="req-1\n"),
        "request-id-equals-verdict": lambda r: r.update(request_id="clean_local"),
        "request-id-equals-verdict-case": lambda r: r.update(request_id="Clean_Local"),
        "base-short": lambda r: r.update(base_revision="a" * 39),
        "snapshot-upper": lambda r: r.update(snapshot_hash="B" * 64),
        "table-sha-short": lambda r: r.update(role_table_sha256="b" * 63),
        "role-reserved-name": role0(role="request"),
        "role-reserved-name-sha": role0(role="role_table_sha256"),
        "role-uppercase": role0(role="Python-Reviewer"),
        "role-pipe": role0(role="a|b"),
        "role-non-ascii": role0(role="róle"),
        "status-unknown": role0(status="DONE"),
        "class-unknown": role0(**{"class": "UNKNOWN"}),
        "list-not-list": role0(uncovered="x"),
        "list-bad-item": role0(uncovered=["Bad Token"]),
        "list-item-pipe": role0(uncovered=["a|b"]),
        "list-too-long": role0(uncovered=[f"u{i}" for i in range(contracts.MAX_LIST + 1)]),
        "residual-unsorted": role0(model_residual=["b-two", "a-one"]),
        "residual-duplicate": role0(model_residual=["a-one", "a-one"]),
        "residual-nine": role0(model_residual=[f"r{i}" for i in range(contracts.MAX_MODEL_RESIDUAL + 1)]),
        "count-bool": role0(findings_count=True),
        "count-negative": role0(findings_count=-1),
        "count-float": role0(findings_count=0.0),
        "count-too-big": role0(findings_count=contracts.MAX_FINDINGS_PER_ROLE + 1),
        "severity-unknown": role0(highest_severity="SEVERE"),
        "severity-without-findings": role0(highest_severity="MAJOR"),
        "findings-without-severity": role0(findings_count=1, highest_severity=None),
        "clean-with-residual": lambda r: r["roles"][0].update(status="CLEAN", model_residual=["x-open"]),
        "duplicate-role": lambda r: r["roles"].append(copy.deepcopy(r["roles"][0])),
    }


@pytest.mark.parametrize("name", list(_mutations()))
def test_BAD_REPORT(name):
    report = copy.deepcopy(report_of("lpm-partial-residual"))
    mutate = _mutations()[name]
    forged = "not a dict" if mutate is None else report
    if mutate is not None:
        mutate(report)
    for fn in (cr.render_text, cr.render_markdown, cr.check_ids_have_no_pass_word):
        err = _code(fn, forged)
        assert err.code == "BAD_REPORT", (name, err.code)


def test_BAD_REPORT_from_the_word_computation_itself():
    forged = copy.deepcopy(report_of("lpm-partial-nothing-open"))
    forged["roles"][0]["status"] = "CLEAN"  # class stays LOCAL_PLUS_MODEL
    assert _code(cr.render_text, forged).code == "BAD_REPORT"


def test_BAD_REPORT_roles_over_the_limit():
    base = report_of("local-clean")
    forged = copy.deepcopy(base)
    forged["roles"] = [dict(copy.deepcopy(base["roles"][0]), role=f"r{i}") for i in range(contracts.MAX_ROLES + 1)]
    assert _code(cr.render_text, forged).code == "BAD_REPORT"


@pytest.mark.parametrize("schema", ["uc.coverage-report.v0", "uc.coverage-report.v2", "", None, 1])
def test_WRONG_SCHEMA(schema):
    forged = copy.deepcopy(report_of("lpm-partial-residual"))
    forged["schema_version"] = schema
    for fn in (cr.render_text, cr.render_markdown, cr.check_ids_have_no_pass_word):
        err = _code(fn, forged)
        assert (err.code, err.where) == ("WRONG_SCHEMA", "report.schema_version")


def test_BAD_VERDICT_WORD_is_reported_with_the_role_index():
    forged = copy.deepcopy(report_of("local-clean", "lpm-partial-residual"))
    forged["roles"][1]["verdict_word"] = "CLEAN_LOCAL"
    err = _code(cr.render_text, forged)
    assert (err.code, err.where) == ("BAD_VERDICT_WORD", "report.roles[1].verdict_word")


def test_PASS_TOKEN_IN_PARTIAL_REPORT_names_the_offset():
    report = report_of("lpm-partial-residual")
    text = cr.render_text(report)
    err = _code(cr.assert_no_pass_token, text + "OK", report)
    assert err.code == "PASS_TOKEN_IN_PARTIAL_REPORT" and err.where == f"offset {len(text)}"


def test_PASS_WORD_IN_ID_is_a_distinct_code_from_the_rendering_check():
    report = cr.render_coverage_report(
        result_of(entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["done-soon"])), TABLE)
    assert _code(cr.check_ids_have_no_pass_word, report).code == "PASS_WORD_IN_ID"


# ----------------------------------------------------------------------- determinism / no mutation
def test_rendering_is_deterministic_and_does_not_mutate_inputs():
    result = result_of(clean_local(), SHAPES["lpm-partial-findings-residual"](), SHAPES["model-only-not-covered"]())
    table = copy.deepcopy(TABLE)
    before_result, before_table = copy.deepcopy(result), copy.deepcopy(table)
    first = cr.render_coverage_report(result, table, TABLE_SHA)
    second = cr.render_coverage_report(copy.deepcopy(result), copy.deepcopy(table), TABLE_SHA)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert cr.render_text(first) == cr.render_text(second)
    assert cr.render_markdown(first) == cr.render_markdown(second)
    assert result == before_result and table == before_table


def test_report_does_not_alias_the_result_and_rendering_does_not_mutate_the_report():
    result = result_of(SHAPES["lpm-findings"]())
    report = cr.render_coverage_report(result, TABLE)
    snapshot = copy.deepcopy(report)
    cr.render_text(report), cr.render_markdown(report), cr.check_ids_have_no_pass_word(report)
    assert report == snapshot
    report["roles"][0]["model_residual"].append("z-extra")
    assert result["roles"][0]["model_residual"] == ["a-one", "b-two"]


def test_role_order_of_the_result_is_preserved():
    report = report_of("lpm-partial-residual", "model-only-not-covered")
    assert [r["role"] for r in report["roles"]] == ["python-reviewer", "planner"]


def test_render_coverage_report_output_matches_the_report_contract_keys():
    report = report_of("local-clean")
    assert set(report) == cr._REPORT_KEYS and set(report["roles"][0]) == cr._ROLE_KEYS
    assert report["schema_version"] == cr.REPORT_SCHEMA


# --------------------------------------------------------------------------------------- the CLI
def _write(tmp_path: pathlib.Path, result, table_bytes: bytes | None = None):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    table_path = tmp_path / "role_table.json"
    table_path.write_bytes(S.TABLE_PATH.read_bytes() if table_bytes is None else table_bytes)
    return ["--result", str(result_path), "--table", str(table_path)]


def test_cli_exit_0_for_a_legit_clean_local_role_in_every_format(tmp_path, capsys):
    args = _write(tmp_path, result_of(clean_local()))
    for fmt in ("text", "markdown", "json"):
        assert cr.main(args + ["--format", fmt]) == 0
        out = capsys.readouterr()
        assert out.err == ""
        assert "CLEAN_LOCAL" in out.out
    assert json.loads(out.out)["roles"][0]["verdict_word"] == "CLEAN_LOCAL"


def test_cli_exit_0_prints_no_pass_word_for_a_partial_role(tmp_path, capsys):
    args = _write(tmp_path, result_of(SHAPES["lpm-partial-residual"]()))
    assert cr.main(args) == 0
    out = capsys.readouterr().out
    assert "MODEL_RESIDUAL_OPEN" in out and cr.scan_pass_tokens(out) == []


def test_cli_writes_no_files(tmp_path, capsys):
    args = _write(tmp_path, result_of(clean_local()))
    before = sorted(p.name for p in tmp_path.iterdir())
    cr.main(args)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def _stderr_code(capsys):
    return json.loads(capsys.readouterr().err)


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_cli_exit_2_when_the_table_bytes_differ_from_the_result_pin(tmp_path, capsys, fmt):
    args = _write(tmp_path, result_of(clean_local()), table_bytes=S.TABLE_PATH.read_bytes() + b"\n")
    assert cr.main(args + ["--format", fmt]) == 2
    captured = _stderr_code(capsys)
    assert captured == {"status": "ERROR", "code": "TABLE_DIGEST_MISMATCH", "where": "result.role_table_sha256"}


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_cli_exit_2_for_a_pass_word_in_an_identifier_even_in_json(tmp_path, capsys, fmt):
    e = entry("python-reviewer", "LOCAL_PLUS_MODEL", "PARTIAL", uncovered=["all-done"], residual=["model-judgment"])
    assert cr.main(_write(tmp_path, result_of(e)) + ["--format", fmt]) == 2
    assert _stderr_code(capsys)["code"] == "PASS_WORD_IN_ID"


def test_cli_exit_2_for_an_invalid_result_and_prints_nothing_on_stdout(tmp_path, capsys):
    assert cr.main(_write(tmp_path, {"schema_version": "uc.role-result.v1"})) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and json.loads(captured.err)["code"] == "INVALID_RESULT"


def test_cli_exit_2_for_a_role_the_table_does_not_know(tmp_path, capsys):
    e = entry("no-such-role", "LOCAL_PLUS_MODEL", "PARTIAL", residual=["model-judgment"])
    assert cr.main(_write(tmp_path, result_of(e))) == 2
    assert _stderr_code(capsys)["code"] == "UNKNOWN_ROLE"


def test_cli_exit_2_for_a_table_without_entries(tmp_path, capsys):
    table = json.dumps({"version": 1}).encode()
    assert cr.main(_write(tmp_path, result_of(clean_local(), table_sha=hashlib.sha256(table).hexdigest()),
                          table_bytes=table)) == 2
    assert _stderr_code(capsys)["code"] == "BAD_ROLE_TABLE"


def test_cli_exit_2_on_a_usage_error():
    with pytest.raises(SystemExit) as info:
        cr.main(["--table", "x.json"])
    assert info.value.code == 2
    with pytest.raises(SystemExit) as info:
        cr.main(["--result", "a", "--table", "b", "--format", "html"])
    assert info.value.code == 2


def test_cli_exit_3_when_an_input_file_is_missing(tmp_path, capsys):
    args = _write(tmp_path, result_of(clean_local()))
    args[1] = str(tmp_path / "absent.json")
    assert cr.main(args) == 3
    captured = _stderr_code(capsys)
    assert captured["code"] == "UNREADABLE_INPUT" and captured["where"] == "FileNotFoundError"
    args = _write(tmp_path, result_of(clean_local()))
    args[3] = str(tmp_path / "absent-table.json")
    assert cr.main(args) == 3


@pytest.mark.parametrize("payload", [b"", b"{not json", b"\xff\xfe\x00\x00", b"[" * 200000])
def test_cli_exit_3_when_the_result_is_not_json(tmp_path, capsys, payload):
    result_path = tmp_path / "result.json"
    result_path.write_bytes(payload)
    table_path = tmp_path / "t.json"
    table_path.write_bytes(S.TABLE_PATH.read_bytes())
    assert cr.main(["--result", str(result_path), "--table", str(table_path)]) == 3
    assert _stderr_code(capsys)["code"] == "UNREADABLE_INPUT"


def test_cli_exit_3_when_the_table_is_a_directory(tmp_path, capsys):
    args = _write(tmp_path, result_of(clean_local()))
    args[3] = str(tmp_path)
    assert cr.main(args) == 3


def test_cli_accepts_a_utf8_bom_result(tmp_path, capsys):
    args = _write(tmp_path, result_of(clean_local()))
    path = pathlib.Path(args[1])
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert cr.main(args) == 0
