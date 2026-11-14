"""LINK-2 T2: router request builder and packet validation (`tools/vst/router_request.py`), AC-4 to AC-7.

Acceptance criteria (docs/sdlc/LINK2_ROUTER_DESIGN.md section 5):
- AC-4 the same story twice gives identical bytes;
- AC-5 a bad `task_id` or an empty `acceptance` gives ROUTER_BAD_REQUEST and no process is started;
- AC-6 a packet with another role or task_id, or `llm_calls` not 0, gives ROUTER_PACKET_INVALID;
- AC-7 a packet over 1 MiB gives ROUTER_SIZE_CAP.
Expected bytes and digests are written out here from the design text (sorted compact ASCII JSON plus one LF);
the packet fixture has the shape of AEVE's own `tests/fixtures/handoff_verify/packet.json` at the pin.
"""

from __future__ import annotations

import copy
import json
import subprocess

import pytest

from tools.vst import router_request as rr
from tools.vst.router_request import RouterError

STORY = dict(role="planner", task_id="T-1", title="Plan", scope_paths=["docs"], acceptance=["Done"])
# sorted keys: acceptance, files, forbidden_paths, role, schema_version, scope_paths, task_id, title
STORY_BYTES = (b'{"acceptance":["Done"],"files":[],"forbidden_paths":[],"role":"planner",'
               b'"schema_version":"aeve.task_packet.request.v1","scope_paths":["docs"],"task_id":"T-1","title":"Plan"}\n')


def request():
    return rr.build_request(role="implementation-engineer", task_id="S20-T08", title="Handoff fixture packet",
                            scope_paths=["src/aeve", "tests"], forbidden_paths=["src/aeve/review.py"],
                            acceptance=["Result stays inside scope."])


def packet(**over):
    doc = {
        "schema_version": "aeve.task_packet.v1", "status": "COMPLETE", "role": "implementation-engineer",
        "task_id": "S20-T08", "title": "Handoff fixture packet", "request_sha256": "1bb9db8e" + "0" * 56,
        "acceptance": [{"id": "AC-1", "text": "Result stays inside scope."}],
        "scope": {"allowed_paths": ["src/aeve", "tests"], "forbidden_paths": ["src/aeve/review.py"]},
        "files": {"declared": [], "logic": [], "outside_scope": [], "tests": []},
        "risks": [], "llm_calls": 0, "executed_project_code": False, "source_modified": False,
    }
    doc.update(over)
    return doc


def raw(doc) -> bytes:
    return json.dumps(doc).encode("utf-8")


def code_of(func, *args, **kwargs) -> RouterError:
    with pytest.raises(RouterError) as info:
        func(*args, **kwargs)
    return info.value


# ------------------------------------------------------------------ AC-4 canonical bytes
def test_request_has_the_exact_documented_shape():
    assert rr.build_request(**STORY) == {
        "schema_version": "aeve.task_packet.request.v1", "role": "planner", "task_id": "T-1", "title": "Plan",
        "scope_paths": ["docs"], "files": [], "forbidden_paths": [], "acceptance": ["Done"]}


def test_canonical_bytes_match_the_written_out_example():
    assert rr.request_bytes(rr.build_request(**STORY)) == STORY_BYTES


def test_same_story_twice_gives_identical_bytes():  # AC-4
    first = rr.request_bytes(rr.build_request(**STORY))
    second = rr.request_bytes(rr.build_request(**copy.deepcopy(STORY)))
    assert first == second


def test_bytes_do_not_depend_on_dict_insertion_order():
    forward = {"b": 1, "a": 2}
    backward = {"a": 2, "b": 1}
    assert rr.request_bytes(forward) == rr.request_bytes(backward) == b'{"a":2,"b":1}\n'


def test_bytes_are_ascii_with_one_trailing_lf_and_no_cr():
    data = rr.request_bytes(rr.build_request(**dict(STORY, title="café ☃")))
    assert data.isascii() and data.endswith(b"}\n") and data.count(b"\n") == 1 and b"\r" not in data
    assert json.loads(data)["title"] == "café ☃"
    assert b"\\u00e9" in data


def test_list_order_is_kept_because_it_is_part_of_the_story():
    one = rr.request_bytes(rr.build_request(**dict(STORY, scope_paths=["a", "b"])))
    two = rr.request_bytes(rr.build_request(**dict(STORY, scope_paths=["b", "a"])))
    assert one != two


def test_sha256_hex_of_a_known_value():
    assert rr.sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_builder_does_not_mutate_or_alias_its_inputs():
    scope = ["docs"]
    built = rr.build_request(**dict(STORY, scope_paths=scope))
    scope.append("x")
    assert built["scope_paths"] == ["docs"]


# ------------------------------------------------------------------ AC-5 bad requests, no process
@pytest.fixture()
def no_process(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a process was started")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)


@pytest.mark.parametrize("task_id", ["", " a", "a b", "../x", "a/b", "a\\b", "-a", ".a", "_a", "é", "a" * 65,
                                     None, 5, ["a"]])
def test_bad_task_id_is_refused_before_any_call(no_process, task_id):  # AC-5
    err = code_of(rr.build_request, **dict(STORY, task_id=task_id))
    assert err.reason == "ROUTER_BAD_REQUEST"


@pytest.mark.parametrize("task_id", ["a\n", "a\r\n", "a\n\n"])
def test_task_id_with_a_trailing_line_feed_is_refused(no_process, task_id):  # AC-5
    # task_id becomes a directory name and a log field; a bare "$" in the pattern lets one trailing LF through
    assert code_of(rr.build_request, **dict(STORY, task_id=task_id)).reason == "ROUTER_BAD_REQUEST"


RESERVED = ["con", "nul", "com1", "lpt9", "Aux", "PRN", "CON", "com9", "LPT1", "con.txt", "NUL.tar.gz"]  # Windows device names


@pytest.mark.parametrize("task_id", RESERVED + ["a.", "story.", "a.b.", "T-1."])
def test_windows_reserved_names_and_a_trailing_dot_are_refused(no_process, task_id):  # AC-5: the id is a directory name
    assert code_of(rr.build_request, **dict(STORY, task_id=task_id)).reason == "ROUTER_BAD_REQUEST"
    assert rr.valid_task_id(task_id) is False


@pytest.mark.parametrize("task_id", ["com10", "lpt10", "com0", "console", "nulx", "a.con", "my-con", "S20-T08", "a", "a" * 64])
def test_near_miss_names_are_still_accepted(task_id):
    assert rr.valid_task_id(task_id) is True
    assert rr.build_request(**dict(STORY, task_id=task_id))["task_id"] == task_id


@pytest.mark.parametrize("task_id", [None, 5, b"a", ["a"], "", "a\n"])
def test_valid_task_id_is_false_for_a_non_string_or_a_bad_pattern(task_id):
    assert rr.valid_task_id(task_id) is False


@pytest.mark.parametrize("task_id", ["a", "A", "0", "a.b_c-d", "S20-T08", "a" * 64])
def test_task_id_boundary_values_that_are_allowed(task_id):
    assert rr.build_request(**dict(STORY, task_id=task_id))["task_id"] == task_id


@pytest.mark.parametrize("acceptance", [[], (), "Done", b"Done", None, [""], ["  "], [5], ["ok", None], ["x" * 501],
                                        ["x"] * 201])
def test_empty_or_bad_acceptance_is_refused(no_process, acceptance):  # AC-5
    assert code_of(rr.build_request, **dict(STORY, acceptance=acceptance)).reason == "ROUTER_BAD_REQUEST"


def test_acceptance_boundaries_are_accepted():
    assert len(rr.build_request(**dict(STORY, acceptance=["x" * 500] * 200))["acceptance"]) == 200


@pytest.mark.parametrize("role", ["loop-operator", "rosetta", "", "Planner", None, "planner "])
def test_role_outside_the_five_is_refused(role):
    assert code_of(rr.build_request, **dict(STORY, role=role)).reason == "ROUTER_BAD_REQUEST"


def test_the_five_handoff_assisted_roles_are_the_documented_set():  # AC-3 side: the T2 constant
    assert rr.ROUTER_ROLES == ("implementation-engineer", "ml-engineer", "planner", "product-ux-reviewer",
                               "ux-design-contract")
    for role in rr.ROUTER_ROLES:
        assert rr.build_request(**dict(STORY, role=role))["role"] == role


@pytest.mark.parametrize("field,value", [
    ("title", ""), ("title", "   "), ("title", 7), ("title", "t" * 501),
    ("scope_paths", []), ("scope_paths", "docs"), ("scope_paths", [""]), ("scope_paths", ["p"] * 201),
    ("files", "a.py"), ("files", [3]), ("files", ["f"] * 201),
    ("forbidden_paths", "x"), ("forbidden_paths", [None]), ("forbidden_paths", ["f"] * 201),
])
def test_other_bad_fields_are_refused(field, value):
    assert code_of(rr.build_request, **dict(STORY, **{field: value})).reason == "ROUTER_BAD_REQUEST"


def test_optional_lists_may_be_empty_and_title_boundary_is_allowed():
    built = rr.build_request(**dict(STORY, title="t" * 500, files=[], forbidden_paths=[]))
    assert len(built["title"]) == 500 and built["files"] == [] and built["forbidden_paths"] == []


# ------------------------------------------------------------------ packet validation happy path
def test_valid_packet_is_returned_parsed():
    assert rr.validate_packet(raw(packet()), request()) == packet()


# ------------------------------------------------------------------ AC-6 packet contract
@pytest.mark.parametrize("over", [
    {"role": "planner"},
    {"role": None},
    {"task_id": "S20-T09"},
    {"task_id": None},
    {"llm_calls": 1},
    {"llm_calls": False},
    {"llm_calls": 0.0},
    {"llm_calls": "0"},
    {"llm_calls": None},
    {"executed_project_code": True},
    {"executed_project_code": None},
    {"executed_project_code": 0},
    {"source_modified": True},
    {"source_modified": "false"},
    {"schema_version": "aeve.task_packet.v2"},
    {"schema_version": None},
    {"status": "PARTIAL"},
    {"status": None},
    {"request_sha256": "A" * 64},
    {"request_sha256": "a" * 63},
    {"request_sha256": "a" * 65},
    {"request_sha256": "a" * 64 + "\n"},
    {"acceptance": [{"id": "AC-1\n", "text": "x"}]},
    {"request_sha256": 5},
    {"request_sha256": None},
    {"acceptance": []},
    {"acceptance": [{"id": "AC-1", "text": "a"}, {"id": "AC-2", "text": "b"}]},
    {"acceptance": [{"id": "AC-2", "text": "x"}]},
    {"acceptance": [{"id": "AC-0", "text": "x"}]},
    {"acceptance": [{"id": "ac-1", "text": "x"}]},
    {"acceptance": [{"id": "AC-01", "text": "x"}]},
    {"acceptance": [{"text": "x"}]},
    {"acceptance": ["AC-1"]},
    {"acceptance": "AC-1"},
    {"scope": []},
    {"scope": None},
    {"files": []},
    {"files": "x"},
])
def test_packet_that_breaks_the_contract_is_invalid(over):  # AC-6
    err = code_of(rr.validate_packet, raw(packet(**over)), request())
    assert err.reason == "ROUTER_PACKET_INVALID"


@pytest.mark.parametrize("key", ["llm_calls", "executed_project_code", "source_modified", "role", "task_id",
                                 "request_sha256", "acceptance", "scope", "files", "schema_version", "status"])
def test_packet_missing_a_required_key_is_invalid(key):
    doc = packet()
    del doc[key]
    assert code_of(rr.validate_packet, raw(doc), request()).reason == "ROUTER_PACKET_INVALID"


def test_acceptance_ids_must_run_one_to_n_in_order():
    two = rr.build_request(role="planner", task_id="T-2", title="t", scope_paths=["d"], acceptance=["a", "b"])
    good = packet(role="planner", task_id="T-2",
                  acceptance=[{"id": "AC-1", "text": "a"}, {"id": "AC-2", "text": "b"}])
    assert rr.validate_packet(raw(good), two)["task_id"] == "T-2"
    swapped = packet(role="planner", task_id="T-2",
                     acceptance=[{"id": "AC-2", "text": "b"}, {"id": "AC-1", "text": "a"}])
    assert code_of(rr.validate_packet, raw(swapped), two).reason == "ROUTER_PACKET_INVALID"


def test_aeve_invalid_packet_reports_its_reason_ascii_escaped_and_truncated():
    long_reason = "BAD_SCOPE é☃ " + "x" * 400
    err = code_of(rr.validate_packet, raw({"schema_version": "aeve.task_packet.v1", "status": "INVALID",
                                          "reason": long_reason}), request())
    assert err.reason == "ROUTER_PACKET_INVALID"
    assert err.detail.isascii() and "\\xe9" in err.detail and "\\u2603" in err.detail
    assert "x" * 200 not in err.detail  # the 400-character tail is cut


def test_packet_that_fails_the_guard_is_not_rescued_by_other_valid_fields():
    err = code_of(rr.validate_packet, raw(packet(llm_calls=3)), request())
    assert "llm_calls" in err.detail


# ------------------------------------------------------------------ strict parsing
@pytest.mark.parametrize("data", [
    b"", b"not json", b"[]", b'"x"', b"null", b"5", b'{"a": 1} trailing', b"\xff\xfe{}",
    b'{"status": NaN}', b'{"status": Infinity}', b'{"a": 1, "a": 2}',
    b'{"status": "COMPLETE", "status": "COMPLETE"}', b"\xef\xbb\xbf{}", b'{"a": "\x00"}',
    pytest.param(b"{" * 100000, id="deeply-nested"),
])
def test_malformed_packet_bytes_are_bad_output(data):
    assert code_of(rr.validate_packet, data, request()).reason == "ROUTER_BAD_OUTPUT"


def test_duplicate_key_is_refused_even_when_the_values_are_equal():
    text = json.dumps(packet())
    duplicated = text[:-1] + ', "task_id": "S20-T08"}'
    assert code_of(rr.validate_packet, duplicated.encode("utf-8"), request()).reason == "ROUTER_BAD_OUTPUT"


def test_parse_strict_json_object_labels_and_returns_objects():
    assert rr.parse_strict_json_object(b'{"a": [1, 2]}', "x") == {"a": [1, 2]}
    err = code_of(rr.parse_strict_json_object, b"[1]", "report")
    assert err.reason == "ROUTER_BAD_OUTPUT" and "report" in err.detail


# ------------------------------------------------------------------ AC-7 size cap
def padded(size: int) -> bytes:
    base = raw(packet())
    return base + b" " * (size - len(base))  # trailing whitespace keeps the JSON valid


def test_packet_of_exactly_one_mib_is_still_parsed():
    data = padded(1024 * 1024)
    assert len(data) == 1048576
    assert rr.validate_packet(data, request())["task_id"] == "S20-T08"


def test_packet_over_one_mib_is_size_cap():  # AC-7
    data = padded(1024 * 1024 + 1)
    assert code_of(rr.validate_packet, data, request()).reason == "ROUTER_SIZE_CAP"


def test_size_cap_comes_before_parsing():
    assert code_of(rr.validate_packet, b"x" * (1024 * 1024 + 1), request()).reason == "ROUTER_SIZE_CAP"


# ------------------------------------------------------------------ helpers
def test_is_zero_accepts_only_the_integer_zero():
    assert rr.is_zero(0) is True
    for value in (False, True, 0.0, "0", None, 1, -0.0):
        assert rr.is_zero(value) is False


def test_check_guards_names_the_failing_guard_and_uses_the_given_code():
    ok = {"llm_calls": 0, "executed_project_code": False, "source_modified": False}
    rr.check_guards(ok, "ANY", "x")
    for key, bad in (("llm_calls", 2), ("executed_project_code", True), ("source_modified", True)):
        err = code_of(rr.check_guards, dict(ok, **{key: bad}), "ROUTER_BAD_OUTPUT", "report")
        assert err.reason == "ROUTER_BAD_OUTPUT" and key in err.detail


def test_ascii_excerpt_truncates_and_escapes():
    assert rr.ascii_excerpt("abc", 2) == "ab"
    assert rr.ascii_excerpt("é") == "\\xe9"
    assert rr.ascii_excerpt("☃") == "\\u2603"
