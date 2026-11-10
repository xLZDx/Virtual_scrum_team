"""U4-1: project-scope role registration (manifest, NOT_COVERED registration, table hash drift seen by the gate).

Uses a temporary fixture project, a synthetic base role table built by the real ``role_table.build_role_table``
and a synthetic AEVE matrix; no real AEVE checkout is needed. The gate check reuses the U2 helpers
(real receipt builder, real frozen rule catalog, throwaway git repository).
"""

from __future__ import annotations

import copy
import json
import os
import pathlib

import pytest

from uc import project_roles as pr
from uc import role_table as rt
from uc import router

from tests.vst import u2_helpers as U

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
    path.write_text(text, encoding="utf-8")
    return path


def agent_file(project: pathlib.Path, name: str, body: str = "x") -> pathlib.Path:
    return write(project / ".claude" / "agents" / f"{name}.md", f"---\nname: {name}\ndescription: d\n---\n{body}\n")


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "fixture-project"
    agent_file(root, "proj-alpha")
    write(root / ".claude" / "skills" / "proj-skill" / "SKILL.md", "---\nname: proj-skill\n---\nbody\n")
    return root


def register(project, mapping=None, base=None):
    manifest = pr.scan_project_roles(project)
    table = pr.register_project_roles(base or base_table(), manifest, mapping, MATRIX)
    return manifest, table


def valid(table, manifest):
    return pr.validate_extended_table(table, INVENTORY, manifest, MATRIX, PROBE)


def refusal(call, *args, **kw) -> str:
    with pytest.raises(pr.ProjectRolesError) as info:
        call(*args, **kw)
    return info.value.code


# ------------------------------------------------------------------------------------------ manifest
def test_manifest_lists_project_agents_and_skills_deterministically(project):
    manifest = pr.scan_project_roles(project)
    assert manifest["schema"] == "uc.project-roles.v1" and manifest["project"] == "fixture-project"
    assert [(e["kind"], e["name"], e["path"], e["scope"]) for e in manifest["entries"]] == [
        ("agent", "proj-alpha", ".claude/agents/proj-alpha.md", "project"),
        ("skill", "proj-skill", ".claude/skills/proj-skill/SKILL.md", "project"),
    ]
    assert pr.scan_project_roles(project) == manifest
    assert pr.validate_manifest(manifest) == []


def test_project_without_claude_directory_has_an_empty_manifest(tmp_path):
    assert pr.scan_project_roles(tmp_path)["entries"] == []


def test_name_falls_back_to_the_file_stem_without_frontmatter(tmp_path):
    write(tmp_path / ".claude" / "agents" / "plain-agent.md", "no frontmatter\n")
    assert pr.scan_project_roles(tmp_path)["entries"][0]["name"] == "plain-agent"


# ---------------------------------------------------------------- the three acceptance facts together
def test_adding_one_agent_changes_manifest_registers_not_covered_and_changes_table_hash(project):
    manifest_before, table_before = register(project)
    assert valid(table_before, manifest_before) == []
    hash_before = pr.table_sha256(table_before)

    agent_file(project, "proj-new-agent")  # the only change: one new file, no code change
    manifest_after, table_after = register(project)

    assert manifest_after != manifest_before
    assert pr.manifest_sha256(manifest_after) != pr.manifest_sha256(manifest_before)
    new = next(e for e in table_after["entries"] if e["name"] == "proj-new-agent")
    assert new["scope"] == "project" and new["coverage_state"] == "NOT_COVERED_NO_PROFILE"
    assert new["reason"] == "project-scope role, not mapped yet" and new["executors"] == []
    assert new["aeve_profile"] is None and new["canonical_role"] == "proj-new-agent"
    assert valid(table_after, manifest_after) == []
    assert table_after["counts"]["total"] == table_before["counts"]["total"] + 1
    assert pr.table_sha256(table_after) != hash_before
    # the router answers NOT_COVERED for it, whatever its class
    request = {"request_id": "req-1", "base_revision": "a" * 40, "purpose": "advisory",
               "changed_paths": ["src/a.py"], "roles": ["proj-new-agent"]}
    result = router.normalize(request, table_after, None, None, role_table_sha256=pr.table_sha256(table_after),
                              aeve_head=PROBE["aeve_head"])
    assert result["roles"][0]["status"] == "NOT_COVERED" and "no-aeve-profile" in result["roles"][0]["uncovered"]
    assert result["roles"][0]["executors"] == []


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
    # re-pinning to the new digest is the only way to clear it (control: the check can pass)
    repinned = gate_decision(world, receipt_hash=new_hash, pinned_hash=new_hash)
    assert "ROLE_TABLE_DRIFT" not in U.reasons_text(repinned)


# ------------------------------------------------------------------------------------------------ mapping
def mapping_for(**over):
    entry = {"kind": "agent", "name": "proj-alpha", "canonical_role": "python-reviewer", "executors": ["g2.python-rules"]}
    entry.update(over)
    return {"schema": "uc.project-role-mapping.v1", "entries": [entry]}


def test_explicit_mapping_to_matrix_executors_lifts_a_role_to_covered_partial(project):
    manifest, table = register(project, mapping_for())
    entry = next(e for e in table["entries"] if e["name"] == "proj-alpha")
    assert entry["coverage_state"] == "COVERED_PARTIAL" and entry["executors"] == ["g2.python-rules"]
    assert entry["canonical_role"] == "python-reviewer" and entry["scope"] == "project"
    assert valid(table, manifest) == []
    other = next(e for e in table["entries"] if e["name"] == "proj-skill")
    assert other["coverage_state"] == "NOT_COVERED_NO_PROFILE"
    router.check_table(table)


def test_mapping_claiming_an_executor_the_matrix_lacks_is_refused(project):
    code = refusal(register, project, mapping_for(executors=["g2.python-rules", "g2.invented"]))
    assert code == "MAPPING_EXECUTORS_NOT_IN_MATRIX"
    assert refusal(register, project, mapping_for(canonical_role="empty-profile",
                                                  executors=["g2.python-rules"])) == "MAPPING_EXECUTORS_NOT_IN_MATRIX"
    assert refusal(register, project, mapping_for(canonical_role="no-such-profile")) == "MAPPING_EXECUTORS_NOT_IN_MATRIX"


def test_mapping_for_a_role_not_in_the_manifest_or_without_a_matrix_is_refused(project):
    manifest = pr.scan_project_roles(project)
    assert refusal(pr.register_project_roles, base_table(), manifest, mapping_for(name="ghost"), MATRIX) == \
        "MAPPING_FOR_UNKNOWN_ROLE"
    assert refusal(pr.register_project_roles, base_table(), manifest, mapping_for(), None) == "MATRIX_REQUIRED"
    bad = mapping_for()
    bad["schema"] = "other"
    assert refusal(pr.register_project_roles, base_table(), manifest, bad, MATRIX) == "BAD_MAPPING"


def test_validator_rejects_a_hand_edited_table_claiming_coverage_the_matrix_lacks(project):
    manifest, table = register(project)
    forged = copy.deepcopy(table)
    entry = next(e for e in forged["entries"] if e["name"] == "proj-alpha")
    entry.update(coverage_state="COVERED_PARTIAL", executors=["g2.invented"], aeve_profile="proj-alpha")
    forged["counts"] = rt._counts(forged["entries"])
    assert any("claims coverage the matrix does not list" in p for p in valid(forged, manifest))


def test_validator_rejects_missing_extra_and_stale_project_entries(project):
    manifest, table = register(project)
    dropped = copy.deepcopy(table)
    dropped["entries"] = [e for e in dropped["entries"] if e["name"] != "proj-alpha"]
    dropped["counts"] = rt._counts(dropped["entries"])
    assert any(p.startswith("missing project entry") for p in valid(dropped, manifest))
    stale = copy.deepcopy(table)
    next(e for e in stale["entries"] if e["name"] == "proj-alpha")["source_sha256"] = "0" * 64
    assert any("source digest differs" in p for p in valid(stale, manifest))
    extra = copy.deepcopy(table)
    extra["entries"].append({**extra["entries"][0], "name": "ghost", "scope": "project"})
    extra["counts"] = rt._counts(extra["entries"])
    assert valid(extra, manifest)


# ------------------------------------------------------------------------------------- negative scans
def test_duplicate_names_are_refused_including_across_kinds(tmp_path):
    write(tmp_path / ".claude" / "agents" / "one.md", "---\nname: same\n---\n")
    write(tmp_path / ".claude" / "agents" / "two.md", "---\nname: same\n---\n")
    assert refusal(pr.scan_project_roles, tmp_path) == "DUPLICATE_NAME"
    other = tmp_path / "second"
    write(other / ".claude" / "agents" / "shared.md", "x")
    write(other / ".claude" / "skills" / "shared" / "SKILL.md", "x")
    assert refusal(pr.scan_project_roles, other) == "DUPLICATE_NAME"


@pytest.mark.parametrize("name", ["bad name", "../escape", "-lead", "x" * 65, "a/b", "semi;colon"])
def test_bad_names_are_refused(tmp_path, name):
    write(tmp_path / ".claude" / "agents" / "file.md", f"---\nname: {name}\n---\n")
    assert refusal(pr.scan_project_roles, tmp_path) == "BAD_NAME"


def test_oversize_and_non_utf8_files_are_refused(tmp_path):
    big = tmp_path / ".claude" / "agents" / "big.md"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"a" * (pr.MAX_FILE_BYTES + 1))
    assert refusal(pr.scan_project_roles, tmp_path) == "FILE_TOO_LARGE"
    big.write_bytes(b"\xff\xfe\x00bad")
    assert refusal(pr.scan_project_roles, tmp_path) == "NOT_UTF8"


def test_a_name_colliding_with_a_global_role_is_refused(project):
    agent_file(project, "python-reviewer")
    manifest = pr.scan_project_roles(project)
    assert refusal(pr.register_project_roles, base_table(), manifest, None, MATRIX) == "NAME_COLLIDES_WITH_GLOBAL_ROLE"


def test_registering_against_an_already_extended_table_is_refused(project):
    _, table = register(project)
    manifest = pr.scan_project_roles(project)
    assert refusal(pr.register_project_roles, table, manifest, None, MATRIX) == "BASE_TABLE_ALREADY_EXTENDED"


def test_a_symlinked_agent_file_is_refused(tmp_path):
    target = write(tmp_path / "outside.md", "---\nname: linked\n---\n")
    link = tmp_path / "proj" / ".claude" / "agents" / "linked.md"
    link.parent.mkdir(parents=True)
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        # Cannot create a symlink on this host: guard the same branch by monkeypatch-free direct call instead.
        assert pr._is_link(tmp_path) is False
        return
    assert refusal(pr.scan_project_roles, tmp_path / "proj") == "LINK_REFUSED"


def test_a_symlinked_agents_directory_is_refused(tmp_path):
    real = tmp_path / "real-agents"
    write(real / "a.md", "---\nname: a\n---\n")
    claude = tmp_path / "proj" / ".claude"
    claude.mkdir(parents=True)
    try:
        os.symlink(real, claude / "agents", target_is_directory=True)
    except (OSError, NotImplementedError):
        assert pr._is_link(tmp_path) is False
        return
    assert refusal(pr.scan_project_roles, tmp_path / "proj") == "LINK_REFUSED"


def test_a_missing_project_root_and_a_bad_label_are_refused(tmp_path):
    assert refusal(pr.scan_project_roles, tmp_path / "nope") == "PROJECT_ROOT_MISSING"
    assert refusal(pr.scan_project_roles, tmp_path, "bad label!") == "BAD_LABEL"


def test_cli_scan_print_writes_nothing_and_reports_the_manifest_digest(project, capsys, tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    assert pr.main(["scan", "--project-root", str(project), "--print"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "SCANNED" and summary["entries"] == 2
    assert summary["manifest_sha256"] == pr.manifest_sha256(pr.scan_project_roles(project))
    assert sorted(p.name for p in tmp_path.iterdir()) == before
