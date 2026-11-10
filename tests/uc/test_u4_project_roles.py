"""U4-1: project-scope role registration (manifest, NOT_COVERED registration, table hash drift seen by the gate).

Uses a temporary fixture project, a synthetic base role table built by the real ``role_table.build_role_table``
and a synthetic AEVE matrix; no real AEVE checkout is needed (the AEVE probe is stubbed for CLI tests). The gate
check reuses the U2 helpers (real receipt builder, real frozen rule catalog, throwaway git repository).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import subprocess

import pytest

from uc import project_roles as pr
from uc import role_table as rt
from uc import router

from tests.vst import u2_helpers as U

LABEL = "fixture-project"
PROBE = {"aeve_head": "d4" * 20, "matrix": {"digest_sha256": "e5" * 32}}
MATRIX = {"rows": [
    {"id": "python-reviewer", "deterministic_executors": ["g2.python-rules"]},
    {"id": "security-reviewer", "deterministic_executors": ["g2.secrets", "g2.python-rules"]},
    {"id": "empty-profile", "deterministic_executors": []},
]}
INVENTORY = {"entries": [{"kind": "agent", "name": "python-reviewer"}, {"kind": "agent", "name": "doc-writer"}]}
DRAFT = {"entries": [
    {"kind": "agent", "name": "python-reviewer", "decision": "check_plus_model", "rationale": "r", "model_remainder": "m"},
    {"kind": "agent", "name": "doc-writer", "decision": "model_only", "rationale": "authoring", "model_remainder": ""},
]}


def base_table() -> dict:
    return rt.build_role_table(INVENTORY, DRAFT, MATRIX, PROBE)


def write(path: pathlib.Path, text: str = "# role\n") -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def agent_file(project: pathlib.Path, name: str, body: str = "x") -> pathlib.Path:
    return write(project / ".claude" / "agents" / f"{name}.md", f"---\nname: {name}\ndescription: d\n---\n{body}\n")


def skill_file(project: pathlib.Path, name: str, body: str = "body") -> pathlib.Path:
    return write(project / ".claude" / "skills" / name / "SKILL.md", f"---\nname: {name}\n---\n{body}\n")


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "fixture-project"
    agent_file(root, "proj-alpha")
    skill_file(root, "proj-skill")
    return root


def scan(project):
    return pr.scan_project_roles(project, LABEL)


def register(project, mapping=None, base=None):
    manifest = scan(project)
    table = pr.register_project_roles(base or base_table(), manifest, mapping, MATRIX)
    return manifest, table


def valid(table, manifest, mapping=None):
    return pr.validate_extended_table(table, INVENTORY, manifest, MATRIX, PROBE, mapping)


def refusal(call, *args, **kw) -> str:
    with pytest.raises(pr.ProjectRolesError) as info:
        call(*args, **kw)
    return info.value.code


def project_entry(table, name):
    return next(e for e in table["entries"] if e["name"] == name)


# ------------------------------------------------------------------------------------------ manifest
def test_manifest_lists_project_agents_and_skills_deterministically(project):
    manifest = scan(project)
    assert manifest["schema"] == "uc.project-roles.v1" and manifest["project"] == LABEL
    assert [(e["kind"], e["name"], e["path"], e["scope"]) for e in manifest["entries"]] == [
        ("agent", "proj-alpha", ".claude/agents/proj-alpha.md", "project"),
        ("skill", "proj-skill", ".claude/skills/proj-skill/SKILL.md", "project"),
    ]
    assert scan(project) == manifest
    assert pr.validate_manifest(manifest) == []


def test_label_is_explicit_and_independent_of_the_folder_name(tmp_path):
    first, second = tmp_path / "one-folder", tmp_path / "another-folder"
    for root in (first, second):
        agent_file(root, "same-agent")
    assert pr.scan_project_roles(first, "lbl") == pr.scan_project_roles(second, "lbl")
    assert pr.scan_project_roles(first, "lbl")["project"] == "lbl"
    with pytest.raises(TypeError):
        pr.scan_project_roles(first)  # no default label


def test_project_without_claude_directory_has_an_empty_manifest(tmp_path):
    assert scan(tmp_path)["entries"] == []


def test_name_falls_back_to_the_file_stem_without_frontmatter(tmp_path):
    write(tmp_path / ".claude" / "agents" / "plain-agent.md", "no frontmatter\n")
    assert scan(tmp_path)["entries"][0]["name"] == "plain-agent"


def test_source_digest_does_not_depend_on_line_endings_or_bom(tmp_path):
    text = "---\nname: eol-agent\n---\nline one\nline two\n"
    digests = set()
    for index, variant in enumerate([text, text.replace("\n", "\r\n"), "﻿" + text]):
        root = tmp_path / f"p{index}"
        write(root / ".claude" / "agents" / "eol-agent.md", variant)
        digests.add(scan(root)["entries"][0]["source_sha256"])
    assert digests == {hashlib.sha256(text.encode("utf-8")).hexdigest()}


def test_case_sensitive_filters_ignore_other_spellings(tmp_path):
    write(tmp_path / ".claude" / "agents" / "Upper.MD", "x")
    write(tmp_path / ".claude" / "skills" / "s" / "skill.md", "x")
    write(tmp_path / ".claude" / "skills" / "t" / "README.md", "x")
    assert scan(tmp_path)["entries"] == []


def test_every_scanned_manifest_passes_its_own_validator(project):
    assert pr.validate_manifest(scan(project)) == []


def test_validate_manifest_cross_checks_kind_path_and_name_and_never_raises(project):
    manifest = scan(project)
    wrong_kind = copy.deepcopy(manifest)
    wrong_kind["entries"][0]["path"] = ".claude/skills/proj-alpha/SKILL.md"
    assert any("does not fit its kind" in p for p in pr.validate_manifest(wrong_kind))
    wrong_name = copy.deepcopy(manifest)
    wrong_name["entries"][0]["path"] = ".claude/agents/other.md"
    assert any("differs from the file or directory name" in p for p in pr.validate_manifest(wrong_name))
    for junk in (None, 7, [], {"schema": pr.MANIFEST_SCHEMA, "project": {}, "entries": [[]]},
                 {"schema": pr.MANIFEST_SCHEMA, "project": "p", "entries": [{"kind": [], "name": {}, "path": 1,
                                                                             "source_sha256": 2, "scope": 3}]}):
        assert pr.validate_manifest(junk)


# ---------------------------------------------------------------- the three acceptance facts together
def test_adding_one_agent_changes_manifest_registers_not_covered_and_changes_table_hash(project):
    manifest_before, table_before = register(project)
    assert valid(table_before, manifest_before) == []
    hash_before = pr.table_sha256(table_before)

    agent_file(project, "proj-new-agent")  # the only change: one new file, no code change
    manifest_after, table_after = register(project)

    assert manifest_after != manifest_before
    assert pr.manifest_sha256(manifest_after) != pr.manifest_sha256(manifest_before)
    new = project_entry(table_after, "proj-new-agent")
    assert new["scope"] == "project" and new["coverage_state"] == "NOT_COVERED_NO_PROFILE"
    assert new["reason"] == "project-scope role, not mapped yet" and new["executors"] == []
    assert new["aeve_profile"] is None and new["canonical_role"] == "proj-new-agent"
    assert valid(table_after, manifest_after) == []
    assert table_after["counts"]["total"] == table_before["counts"]["total"] + 1
    assert pr.table_sha256(table_after) != hash_before
    request = {"request_id": "req-1", "base_revision": "a" * 40, "purpose": "advisory",
               "changed_paths": ["src/a.py"], "roles": ["proj-new-agent"]}
    result = router.normalize(request, table_after, None, None, role_table_sha256=pr.table_sha256(table_after),
                              aeve_head=PROBE["aeve_head"])
    assert result["roles"][0]["status"] == "NOT_COVERED" and "no-aeve-profile" in result["roles"][0]["uncovered"]
    assert result["roles"][0]["executors"] == []


def test_adding_a_skill_editing_a_body_and_deleting_a_role_each_change_both_hashes(project):
    manifest0, table0 = register(project)

    def hashes():
        manifest, table = register(project)
        return pr.manifest_sha256(manifest), pr.table_sha256(table)

    seen = {(pr.manifest_sha256(manifest0), pr.table_sha256(table0))}
    skill_file(project, "proj-second-skill")
    after_add = hashes()
    assert after_add not in seen
    seen.add(after_add)
    agent_file(project, "proj-alpha", body="a different body")
    after_edit = hashes()
    assert after_edit not in seen
    seen.add(after_edit)
    (project / ".claude" / "agents" / "proj-alpha.md").unlink()
    after_delete = hashes()
    assert after_delete not in seen
    assert all(a != b for a, b in zip(after_delete, after_edit))


def test_table_hash_equals_the_digest_of_the_written_file_bytes(project, tmp_path):
    _, table = register(project)
    out = tmp_path / "extended.json"
    out.write_bytes(pr.serialize_table(table))
    parsed, digest = router.load_table_with_digest(out)
    assert digest == pr.table_sha256(table) and parsed == table
    router.check_table(parsed)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    return U.make_world(tmp_path_factory.mktemp("u4-roles-gate"))


def gate_decision(world, receipt_hash: str, pinned_hash: str):
    receipt, payload = U.static_run(world, role_res=U.role_result(world.head, table_sha=receipt_hash))
    trust = U.make_trust(world, receipt, payload, pinned_edit=lambda p: {**p, "role_table_sha256": pinned_hash})
    return U.evaluate(world, receipt, trust)


def test_gate_reports_role_table_drift_for_the_old_pin_after_a_role_is_added(project, world):
    _, table_before = register(project)
    old_pin = pr.table_sha256(table_before)
    agent_file(project, "proj-new-agent")
    _, table_after = register(project)
    new_hash = pr.table_sha256(table_after)
    assert new_hash != old_pin
    drifted = gate_decision(world, receipt_hash=new_hash, pinned_hash=old_pin)
    assert drifted["verdict"] == "MODIFY" and "ROLE_TABLE_DRIFT" in U.reasons_text(drifted)
    repinned = gate_decision(world, receipt_hash=new_hash, pinned_hash=new_hash)
    assert "ROLE_TABLE_DRIFT" not in U.reasons_text(repinned)


# ------------------------------------------------------------------------------------------------ mapping
def mapping_for(project, **over):
    manifest = scan(project)
    digest = next(e["source_sha256"] for e in manifest["entries"] if e["name"] == "proj-alpha")
    entry = {"kind": "agent", "name": "proj-alpha", "source_sha256": digest,
             "canonical_role": "python-reviewer", "executors": ["g2.python-rules"]}
    entry.update(over)
    return {"schema": "uc.project-role-mapping.v1", "entries": [entry]}


def test_explicit_mapping_to_matrix_executors_lifts_a_role_to_covered_partial(project):
    mapping = mapping_for(project)
    manifest, table = register(project, mapping)
    entry = project_entry(table, "proj-alpha")
    assert entry["coverage_state"] == "COVERED_PARTIAL" and entry["executors"] == ["g2.python-rules"]
    assert entry["canonical_role"] == "python-reviewer" and entry["scope"] == "project"
    assert valid(table, manifest, mapping) == []
    assert project_entry(table, "proj-skill")["coverage_state"] == "NOT_COVERED_NO_PROFILE"
    router.check_table(table)


def test_a_mapped_table_validates_only_with_the_same_mapping(project):
    mapping = mapping_for(project)
    manifest, table = register(project, mapping)
    assert valid(table, manifest, mapping) == []
    for missing in (None, {"schema": pr.MAPPING_SCHEMA, "entries": []}):
        assert any("COVERED_PARTIAL without a matching mapping entry" in p for p in valid(table, manifest, missing))
    for field, value in (("canonical_role", "security-reviewer"), ("source_sha256", "0" * 64),
                         ("executors", ["g2.python-rules", "g2.secrets"])):
        other = mapping_for(project, **{field: value})
        assert valid(table, manifest, other), field


def test_hand_promoting_an_unmapped_role_to_covered_partial_is_rejected(project):
    manifest, table = register(project)
    forged = copy.deepcopy(table)
    project_entry(forged, "proj-alpha").update(
        coverage_state="COVERED_PARTIAL", canonical_role="python-reviewer", aeve_profile="python-reviewer",
        executors=["g2.python-rules"], reason=pr.MAPPED_REASON)
    forged["counts"] = rt._counts(forged["entries"])
    problems = valid(forged, manifest)
    assert any("COVERED_PARTIAL without a matching mapping entry" in p for p in problems)
    assert valid(forged, manifest, {"schema": pr.MAPPING_SCHEMA, "entries": []})


def test_a_mapping_entry_matching_no_manifest_entry_or_no_applied_entry_is_a_problem(project):
    mapping = mapping_for(project)
    manifest, table = register(project, mapping)
    ghost = copy.deepcopy(mapping)
    ghost["entries"].append({**ghost["entries"][0], "name": "ghost"})
    assert any("matches no manifest entry" in p for p in valid(table, manifest, ghost))
    manifest_u, table_u = register(project)
    assert any("is not applied by the table" in p for p in valid(table_u, manifest_u, mapping))
    assert valid(table, manifest, {"schema": "bad"})  # a malformed mapping is a problem string, not an exception


def test_mapping_claiming_an_executor_the_matrix_lacks_is_refused(project):
    assert refusal(register, project, mapping_for(project, executors=["g2.python-rules", "g2.invented"])) == \
        "MAPPING_EXECUTORS_NOT_IN_MATRIX"
    assert refusal(register, project, mapping_for(project, canonical_role="empty-profile",
                                                  executors=["g2.python-rules"])) == "MAPPING_EXECUTORS_NOT_IN_MATRIX"
    assert refusal(register, project, mapping_for(project, canonical_role="no-such-profile")) == \
        "MAPPING_EXECUTORS_NOT_IN_MATRIX"


def test_mapping_must_carry_the_manifest_source_digest(project):
    assert refusal(register, project, mapping_for(project, source_sha256="0" * 64)) == "BAD_MAPPING"
    stale = mapping_for(project)
    del stale["entries"][0]["source_sha256"]
    assert refusal(register, project, stale) == "BAD_MAPPING"
    written_before_edit = mapping_for(project)
    agent_file(project, "proj-alpha", body="edited after the mapping was written")
    assert refusal(register, project, written_before_edit) == "BAD_MAPPING"


def test_mapping_for_a_role_not_in_the_manifest_or_without_a_matrix_is_refused(project):
    manifest = scan(project)
    assert refusal(pr.register_project_roles, base_table(), manifest, mapping_for(project, name="ghost"), MATRIX) == \
        "MAPPING_FOR_UNKNOWN_ROLE"
    assert refusal(pr.register_project_roles, base_table(), manifest, mapping_for(project), None) == "MATRIX_REQUIRED"
    bad = mapping_for(project)
    bad["schema"] = "other"
    assert refusal(pr.register_project_roles, base_table(), manifest, bad, MATRIX) == "BAD_MAPPING"


def test_unmapped_project_name_equal_to_an_aeve_profile_is_refused(tmp_path):
    agent_file(tmp_path, "security-reviewer")
    manifest = scan(tmp_path)
    assert refusal(pr.register_project_roles, base_table(), manifest, None, MATRIX) == "NAME_EQUALS_AEVE_PROFILE"


# ------------------------------------------------------------------------------- validator strictness
def test_validator_rejects_a_hand_edited_table_claiming_coverage_the_matrix_lacks(project):
    manifest, table = register(project)
    forged = copy.deepcopy(table)
    project_entry(forged, "proj-alpha").update(coverage_state="COVERED_PARTIAL", executors=["g2.invented"],
                                               aeve_profile="proj-alpha")
    forged["counts"] = rt._counts(forged["entries"])
    assert any("claims coverage the matrix does not list" in p for p in valid(forged, manifest))


FORGERIES = {
    "class": ("class", "LOCAL"),
    "class-model-only": ("class", "MODEL_ONLY"),
    "draft_class": ("draft_class", "LOCAL"),
    "upgraded": ("class_upgraded_by_evidence", True),
    "reason": ("reason", "AEVE lists deterministic executors for this role"),
    "hint": ("model_remainder_hint", "anything"),
    "extra-key": ("surprise", 1),
    "aeve_profile": ("aeve_profile", "python-reviewer"),
    "canonical": ("canonical_role", "python-reviewer"),
    "path": ("path", ".claude/agents/elsewhere.md"),
    "scope-removed": ("scope", None),
}


@pytest.mark.parametrize("label", list(FORGERIES))
def test_validator_requires_exactly_the_builder_shape(project, label):
    manifest, table = register(project)
    forged = copy.deepcopy(table)
    field, value = FORGERIES[label]
    entry = project_entry(forged, "proj-alpha")
    entry[field] = value
    forged["counts"] = rt._counts(forged["entries"])
    assert valid(forged, manifest), label


def test_validator_rejects_a_project_entry_without_a_class_without_raising(project):
    manifest, table = register(project)
    forged = copy.deepcopy(table)
    del project_entry(forged, "proj-alpha")["class"]
    problems = valid(forged, manifest)
    assert problems and any("differs from the builder shape" in p for p in problems)


@pytest.mark.parametrize("junk", [None, 5, "text", [], {"entries": None}, {"entries": [1, None]},
                                  {"entries": [{"scope": "project"}]}, {"entries": [{"scope": "project", "kind": []}]}])
def test_validator_returns_problems_and_never_raises_on_malformed_tables(project, junk):
    manifest = scan(project)
    assert pr.validate_extended_table(junk, INVENTORY, manifest, MATRIX, PROBE)
    assert pr.validate_extended_table(register(project)[1], None, manifest, MATRIX, PROBE)
    assert pr.validate_extended_table(register(project)[1], INVENTORY, manifest, None, PROBE)


def test_register_raises_only_project_roles_error_on_malformed_input(project):
    manifest = scan(project)
    for base in (None, 5, {"entries": [1]}, {"entries": [{"kind": "agent"}]}, {"entries": [{"name": []}]}):
        assert refusal(pr.register_project_roles, base, manifest, None, MATRIX) in (
            "BAD_BASE_TABLE", "MALFORMED_INPUT")
    assert refusal(pr.register_project_roles, base_table(), {"junk": 1}, None, MATRIX) == "BAD_MANIFEST"
    assert refusal(pr.register_project_roles, base_table(), manifest, {"schema": pr.MAPPING_SCHEMA, "entries": [5]},
                   MATRIX) == "BAD_MAPPING"


def test_validator_rejects_missing_extra_and_stale_project_entries(project):
    manifest, table = register(project)
    dropped = copy.deepcopy(table)
    dropped["entries"] = [e for e in dropped["entries"] if e["name"] != "proj-alpha"]
    dropped["counts"] = rt._counts(dropped["entries"])
    assert any(p.startswith("missing project entry") for p in valid(dropped, manifest))
    stale = copy.deepcopy(table)
    project_entry(stale, "proj-alpha")["source_sha256"] = "0" * 64
    assert any("source digest differs" in p for p in valid(stale, manifest))
    extra = copy.deepcopy(table)
    extra["entries"].append({**project_entry(extra, "proj-alpha"), "name": "ghost"})
    extra["counts"] = rt._counts(extra["entries"])
    assert any("ghost" in p and "not in the manifest or bad scope" in p for p in valid(extra, manifest))


# ------------------------------------------------------------------------------------- negative scans
def test_duplicate_names_are_refused_including_across_kinds_and_case(tmp_path):
    one = tmp_path / "one"
    write(one / ".claude" / "agents" / "shared.md", "x")
    write(one / ".claude" / "skills" / "shared" / "SKILL.md", "x")
    assert refusal(pr.scan_project_roles, one, LABEL) == "DUPLICATE_NAME"
    two = tmp_path / "two"
    write(two / ".claude" / "agents" / "Mixed.md", "x")
    write(two / ".claude" / "skills" / "mixed" / "SKILL.md", "x")
    assert refusal(pr.scan_project_roles, two, LABEL) == "DUPLICATE_NAME"


def test_a_name_equal_to_a_global_role_ignoring_case_is_refused_at_registration(tmp_path):
    for name in ("python-reviewer", "Python-Reviewer"):
        root = tmp_path / name
        agent_file(root, name)
        assert refusal(pr.register_project_roles, base_table(), scan(root), None, MATRIX) == \
            "NAME_COLLIDES_WITH_GLOBAL_ROLE"


@pytest.mark.parametrize("name", ["bad name", "../escape", "-lead", "x" * 65, "a/b", "semi;colon", "trailing.", "dot ."])
def test_bad_names_are_refused(tmp_path, name):
    write(tmp_path / ".claude" / "agents" / "file.md", f"---\nname: {name}\n---\n")
    assert refusal(pr.scan_project_roles, tmp_path, LABEL) == "BAD_NAME"


IRREGULAR = {
    "quoted-key": '---\n"name": file\n---\n',
    "single-quoted-key": "---\n'name': file\n---\n",
    "upper-key": "---\nName: file\n---\n",
    "spaced-key": "---\nname : file\n---\n",
    "duplicate-key": "---\nname: file\nname: file\n---\n",
    "mismatch": "---\nname: other\n---\n",
    "bare-cr": "---\rname: file\r---\r",
    "line-separator": "---\nname: file \n---\n",
    "next-line": "---\nname: file\x85\n---\n",
    "unterminated": "---\nname: file\n",
    "empty-value": "---\nname:\n---\n",
}


@pytest.mark.parametrize("label", list(IRREGULAR))
def test_irregular_frontmatter_fails_closed(tmp_path, label):
    write(tmp_path / ".claude" / "agents" / "file.md", IRREGULAR[label])
    assert refusal(pr.scan_project_roles, tmp_path, LABEL) == "BAD_NAME"


def test_a_quoted_key_cannot_hide_a_global_name(tmp_path):
    write(tmp_path / ".claude" / "agents" / "python-reviewer.md", '---\n"name": python-reviewer\n---\n')
    assert refusal(pr.scan_project_roles, tmp_path, LABEL) == "BAD_NAME"


def test_error_details_never_echo_raw_names(tmp_path):
    long_name = "n" * 100
    write(tmp_path / ".claude" / "agents" / "file.md", f"---\nname: {long_name}\n---\n")
    with pytest.raises(pr.ProjectRolesError) as info:
        pr.scan_project_roles(tmp_path, LABEL)
    assert long_name not in info.value.detail and "sha256=" in info.value.detail
    with pytest.raises(pr.ProjectRolesError) as label_info:
        pr.scan_project_roles(tmp_path, "l" * 300)
    assert "l" * 300 not in label_info.value.detail


def test_oversize_and_non_utf8_files_are_refused(tmp_path):
    big = tmp_path / ".claude" / "agents" / "big.md"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"a" * (pr.MAX_FILE_BYTES + 1))
    assert refusal(pr.scan_project_roles, tmp_path, LABEL) == "FILE_TOO_LARGE"
    big.write_bytes(b"\xff\xfe\x00bad")
    assert refusal(pr.scan_project_roles, tmp_path, LABEL) == "NOT_UTF8"


def test_too_many_entries_abort_the_scan(tmp_path, monkeypatch):
    for index in range(3):
        write(tmp_path / ".claude" / "agents" / f"a{index}.md", "x")
    monkeypatch.setattr(pr, "MAX_ENTRIES", 2)
    assert refusal(pr.scan_project_roles, tmp_path, LABEL) == "TOO_MANY_ENTRIES"


def test_registering_against_an_already_extended_table_is_refused(project):
    _, table = register(project)
    assert refusal(pr.register_project_roles, table, scan(project), None, MATRIX) == "BASE_TABLE_ALREADY_EXTENDED"


def test_a_missing_project_root_and_a_bad_label_are_refused(tmp_path):
    assert refusal(pr.scan_project_roles, tmp_path / "nope", LABEL) == "PROJECT_ROOT_MISSING"
    assert refusal(pr.scan_project_roles, tmp_path, "bad label!") == "BAD_LABEL"
    assert refusal(pr.scan_project_roles, tmp_path, None) == "BAD_LABEL"


# ---------------------------------------------------------------------------------------------- links
def make_symlink(target: pathlib.Path, link: pathlib.Path, directory: bool) -> None:
    try:
        os.symlink(target, link, target_is_directory=directory)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"cannot create a symlink on this host: {type(exc).__name__}")


def make_junction(target: pathlib.Path, link: pathlib.Path) -> None:
    if os.name != "nt":
        pytest.skip("junctions exist only on Windows")
    done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    if done.returncode != 0:
        pytest.skip(f"mklink /J failed: {done.stderr.strip()[:80]}")


def test_a_symlinked_agent_file_is_refused(tmp_path):
    target = write(tmp_path / "outside.md", "---\nname: linked\n---\n")
    link = tmp_path / "proj" / ".claude" / "agents" / "linked.md"
    link.parent.mkdir(parents=True)
    make_symlink(target, link, False)
    assert refusal(pr.scan_project_roles, tmp_path / "proj", LABEL) == "LINK_REFUSED"


def test_a_symlinked_agents_directory_is_refused(tmp_path):
    real = tmp_path / "real-agents"
    write(real / "a.md", "---\nname: a\n---\n")
    claude = tmp_path / "proj" / ".claude"
    claude.mkdir(parents=True)
    make_symlink(real, claude / "agents", True)
    assert refusal(pr.scan_project_roles, tmp_path / "proj", LABEL) == "LINK_REFUSED"


def test_a_symlinked_claude_directory_is_refused(tmp_path):
    real = tmp_path / "real-claude"
    write(real / "agents" / "a.md", "---\nname: a\n---\n")
    proj = tmp_path / "proj"
    proj.mkdir()
    make_symlink(real, proj / ".claude", True)
    assert refusal(pr.scan_project_roles, proj, LABEL) == "LINK_REFUSED"


def test_a_symlinked_skill_directory_is_refused(tmp_path):
    real = tmp_path / "real-skill"
    write(real / "SKILL.md", "x")
    skills = tmp_path / "proj" / ".claude" / "skills"
    skills.mkdir(parents=True)
    make_symlink(real, skills / "linked-skill", True)
    assert refusal(pr.scan_project_roles, tmp_path / "proj", LABEL) == "LINK_REFUSED"


@pytest.mark.parametrize("where", ["agents", "claude", "skill"])
def test_a_windows_junction_is_refused(tmp_path, where):
    real = tmp_path / "real"
    write(real / "a.md", "---\nname: a\n---\n")
    write(real / "SKILL.md", "x")
    proj = tmp_path / "proj"
    if where == "claude":
        proj.mkdir()
        write(real / "agents" / "a.md", "x")
        make_junction(real, proj / ".claude")
    elif where == "agents":
        (proj / ".claude").mkdir(parents=True)
        make_junction(real, proj / ".claude" / "agents")
    else:
        (proj / ".claude" / "skills").mkdir(parents=True)
        make_junction(real, proj / ".claude" / "skills" / "jn")
    assert refusal(pr.scan_project_roles, proj, LABEL) == "LINK_REFUSED"


def test_a_hard_linked_agent_file_is_refused(tmp_path):
    original = write(tmp_path / "original.md", "---\nname: hard\n---\n")
    link = tmp_path / "proj" / ".claude" / "agents" / "hard.md"
    link.parent.mkdir(parents=True)
    try:
        os.link(original, link)
    except (OSError, NotImplementedError, AttributeError) as exc:
        pytest.skip(f"cannot create a hard link on this host: {type(exc).__name__}")
    assert refusal(pr.scan_project_roles, tmp_path / "proj", LABEL) == "LINK_REFUSED"


# ---------------------------------------------------------------------------------------------- CLI
def stub_probe(monkeypatch):
    monkeypatch.setattr(pr.aeve_probe, "probe", lambda *a, **k: PROBE)
    monkeypatch.setattr(pr.aeve_probe, "load_matrix", lambda *a, **k: MATRIX)


def cli_inputs(tmp_path):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "base.json").write_bytes(pr.serialize_table(base_table()))
    (inputs / "inventory.json").write_text(json.dumps(INVENTORY), encoding="utf-8")
    (tmp_path / "out").mkdir()
    return inputs


def register_args(project, tmp_path, inputs, *tail):
    return ["register", "--project-root", str(project), "--project-label", LABEL, "--base-table",
            str(inputs / "base.json"), "--aeve-root", str(tmp_path), "--inventory", str(inputs / "inventory.json"),
            *tail]


def test_cli_scan_print_writes_nothing_and_reports_the_manifest_digest(project, capsys, tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    assert pr.main(["scan", "--project-root", str(project), "--project-label", LABEL, "--print"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "SCANNED" and summary["entries"] == 2
    assert summary["manifest_sha256"] == pr.manifest_sha256(scan(project))
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_cli_scan_requires_an_explicit_label(project):
    with pytest.raises(SystemExit):
        pr.main(["scan", "--project-root", str(project), "--print"])


def test_cli_register_out_writes_the_table_and_the_summary_digest_equals_the_file_digest(project, tmp_path, capsys,
                                                                                         monkeypatch):
    stub_probe(monkeypatch)
    inputs = cli_inputs(tmp_path)
    out = tmp_path / "out" / "extended.json"
    assert pr.main(register_args(project, tmp_path, inputs, "--out", str(out))) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "REGISTERED"
    assert summary["role_table_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert sorted(p.name for p in out.parent.iterdir()) == ["extended.json"]  # no temporary file left behind
    assert pr.main(["validate", "--project-root", str(project), "--project-label", LABEL, "--table", str(out),
                    "--aeve-root", str(tmp_path), "--inventory", str(inputs / "inventory.json")]) == 0
    assert json.loads(capsys.readouterr().out)["role_table_sha256"] == summary["role_table_sha256"]


def test_cli_validate_with_and_without_the_mapping(project, tmp_path, capsys, monkeypatch):
    stub_probe(monkeypatch)
    inputs = cli_inputs(tmp_path)
    mapping_path = inputs / "mapping.json"
    mapping_path.write_text(json.dumps(mapping_for(project)), encoding="utf-8")
    out = tmp_path / "out" / "mapped.json"
    assert pr.main(register_args(project, tmp_path, inputs, "--mapping", str(mapping_path), "--out", str(out))) == 0
    registered = json.loads(capsys.readouterr().out)
    common = ["validate", "--project-root", str(project), "--project-label", LABEL, "--table", str(out),
              "--aeve-root", str(tmp_path), "--inventory", str(inputs / "inventory.json")]
    assert pr.main([*common, "--mapping", str(mapping_path)]) == 0
    assert json.loads(capsys.readouterr().out)["role_table_sha256"] == registered["role_table_sha256"]
    assert pr.main(common) == 1
    assert "COVERED_PARTIAL without a matching mapping entry" in capsys.readouterr().out


def test_cli_validate_reports_drift_after_a_role_is_added(project, tmp_path, capsys, monkeypatch):
    stub_probe(monkeypatch)
    inputs = cli_inputs(tmp_path)
    out = tmp_path / "out" / "extended.json"
    assert pr.main(register_args(project, tmp_path, inputs, "--out", str(out))) == 0
    capsys.readouterr()
    agent_file(project, "proj-late-agent")
    code = pr.main(["validate", "--project-root", str(project), "--project-label", LABEL, "--table", str(out),
                    "--aeve-root", str(tmp_path), "--inventory", str(inputs / "inventory.json")])
    assert code == 1 and "INVALID" in capsys.readouterr().out


def test_cli_refuses_an_output_equal_to_an_input_and_leaves_it_untouched(project, tmp_path, capsys, monkeypatch):
    stub_probe(monkeypatch)
    inputs = cli_inputs(tmp_path)
    before = (inputs / "base.json").read_bytes()
    assert pr.main(register_args(project, tmp_path, inputs, "--out", str(inputs / "base.json"))) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "OUT_IS_INPUT"
    assert (inputs / "base.json").read_bytes() == before


def test_cli_refuses_an_output_inside_the_role_directory(project, tmp_path, capsys, monkeypatch):
    stub_probe(monkeypatch)
    inputs = cli_inputs(tmp_path)
    assert pr.main(register_args(project, tmp_path, inputs, "--out",
                                 str(project / ".claude" / "agents" / "zzz.md"))) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "OUT_INSIDE_ROLE_DIRECTORY"


def test_cli_turns_unreadable_input_into_a_refused_line_not_a_traceback(project, tmp_path, capsys, monkeypatch):
    stub_probe(monkeypatch)
    inputs = cli_inputs(tmp_path)
    (inputs / "base.json").write_text("{not json", encoding="utf-8")
    assert pr.main(register_args(project, tmp_path, inputs, "--print")) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "REFUSED"
    (inputs / "base.json").unlink()
    assert pr.main(register_args(project, tmp_path, inputs, "--print")) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "INPUT_ERROR"
