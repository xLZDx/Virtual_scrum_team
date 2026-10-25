"""S4 AC-4/AC-11/AC-14: profile assignment, WSL boundary, and matrix evidence contracts (VST-032/033/037)."""

from __future__ import annotations

import hashlib
import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qa import matrix, registry, report, run


HEAD = "a" * 40
LOCK = b"fixture-lock\n"
RUNNABLE_ID = "tests/qa/test_s4_functional_fixture.py::test_functional"
ROOT_ID = "tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file"
NOT_RUN_ID = "tests/vst/test_e4_runner.py::test_timeout_records_exit_minus_one_and_fails"
WSL_ROOT = "/tmp/vst-s4-candidate/candidate"
WSL_PREFIX = "/tmp/vst-s4-candidate"
MOUNT_HASH = "b" * 64
REPO_ROOT = Path(__file__).resolve().parents[2]


def _report_registry(
    profile: str, *, test_id: str = RUNNABLE_ID, category: str = "functional"
):
    profile_ids = {
        profile_name: [test_id] if profile_name == profile else []
        for profile_name in registry.RUNTIME_PROFILES
    }
    return SimpleNamespace(
        candidate_head=HEAD,
        sha256="c" * 64,
        data={"source_head": HEAD},
        category_profile_test_ids={category: profile_ids},
        category_profile_unassigned_ids={
            category: {
                profile_name: [] if profile_name == profile else [test_id]
                for profile_name in registry.RUNTIME_PROFILES
            }
        },
        category_profile_not_run={
            category: {profile_name: {} for profile_name in registry.RUNTIME_PROFILES}
        },
        category_inventory_ids={category: [test_id]},
        category_not_run={category: {}},
        category_test_ids={category: [test_id]},
        selectors_by_id={
            test_id: {
                "runtime_profiles": [profile],
                "primary_category": category,
            }
        },
    )


def _write_category_report(
    tmp_path: Path,
    profile: str,
    *,
    root_proof_mismatch: bool = False,
    root_helper_mismatch: bool = False,
):
    """Create exact category report/artifact inputs for the matrix validator."""
    candidate = tmp_path / "candidate"
    root = candidate
    qa_root = root / "docs" / "sdlc" / "evidence" / "qa"
    qa_root.mkdir(parents=True, exist_ok=True)
    (root / "tools" / "qa").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "qa" / "requirements.lock").write_bytes(LOCK)
    helper_bytes = b"candidate root harness fixture\n"
    (root / "tools" / "qa" / "root_harness.py").write_bytes(helper_bytes)
    helper_sha256 = hashlib.sha256(helper_bytes).hexdigest()
    selected_id = ROOT_ID if profile == registry.WSL_ROOT_PROFILE else RUNNABLE_ID
    category = "integration" if profile == registry.WSL_ROOT_PROFILE else "functional"
    registry_view = _report_registry(profile, test_id=selected_id, category=category)
    runtime_boundary = None
    if profile in {registry.WSL_PROFILE, registry.WSL_ROOT_PROFILE}:
        runtime_boundary = {
            "candidate_root": WSL_ROOT,
            "candidate_root_prefix": WSL_PREFIX,
            "mountinfo_sha256": MOUNT_HASH,
            "windows_drive_mounts_present": False,
        }
    proof = None
    if profile == registry.WSL_ROOT_PROFILE:
        proof = {
            "authority": run.ROOT_HARNESS_PROOF_AUTHORITY,
            "scope": run.ROOT_HARNESS_REPORT_SCOPE,
            "sha256": "d" * 64,
            "run_nonce_sha256": "e" * 64,
            "candidate_root": WSL_ROOT + ("/mismatch" if root_proof_mismatch else ""),
            "mountinfo_sha256": MOUNT_HASH,
            "parent_network_namespace_inode": 4321,
            "helper_sha256": "f" * 64 if root_helper_mismatch else helper_sha256,
        }
    identity = {
        registry.WINDOWS_PROFILE: {
            "interpreter": {"id": "CPython-3.14.3", "executable": "C:/Python314/python.exe", "version": "3.14.3"},
            "runtime_identity": {"uid": None, "gid": None, "supplementary_groups": []},
        },
        registry.WSL_PROFILE: {
            "interpreter": {"id": "CPython-3.12.3", "executable": "/usr/bin/python3.12", "version": "3.12.3"},
            "runtime_identity": {"uid": 997, "gid": 988, "supplementary_groups": []},
        },
        registry.WSL_ROOT_PROFILE: {
            "interpreter": {"id": "CPython-3.12.3", "executable": "/usr/bin/python3.12", "version": "3.12.3"},
            "runtime_identity": {"uid": 0, "gid": 0, "supplementary_groups": []},
        },
    }[profile]
    run_id = f"run-{profile.split('-')[0]}"
    stdout = b"PASS selector\n"
    stderr = b""
    stdout_path = qa_root / f"{category}.stdout.txt"
    stderr_path = qa_root / f"{category}.stderr.txt"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    node_id = f"{selected_id}::case"
    row = {
        "schema_version": 2,
        "category": category,
        "run_id": run_id,
        "candidate_head": HEAD,
        "registry_sha256": "c" * 64,
        "lock_sha256": hashlib.sha256(LOCK).hexdigest(),
        "runtime_profile": profile,
        **identity,
        "runtime_boundary": runtime_boundary,
        "privileged_harness_preflight": proof,
        "expected_test_ids": [selected_id],
        "inventory_test_ids": [selected_id],
        "unassigned_test_ids": [],
        "not_run_test_reasons": {},
        "passed_test_ids": [selected_id],
        "failed_test_ids": [],
        "skipped_test_ids": [],
        "xfail_test_ids": [],
        "unexpected_node_ids": [],
        "uncollected_test_ids": [],
        "collected_node_ids": [node_id],
        "executed_node_ids": [node_id],
        "case_outcomes": [{"node_id": node_id, "selector_id": selected_id, "outcome": "passed"}],
        "result": "PASS",
        "exit_code": 0,
        "capture": {
            "capture_incomplete": False,
            "timed_out": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        },
        "artifact_paths": {
            "report": f"docs/sdlc/evidence/qa/{category}.report.jsonl",
            "stdout": f"docs/sdlc/evidence/qa/{category}.stdout.txt",
            "stderr": f"docs/sdlc/evidence/qa/{category}.stderr.txt",
        },
        "artifact_ranges": {
            "stdout": {"start": 0, "end": len(stdout)},
            "stderr": {"start": 0, "end": len(stderr)},
        },
        "artifact_sizes": {"stdout": len(stdout), "stderr": len(stderr)},
        "artifact_digests": {
            "stdout": hashlib.sha256(stdout).hexdigest(),
            "stderr": hashlib.sha256(stderr).hexdigest(),
        },
    }
    row["normalized_sha256"] = report.sha256_bytes(
        report.canonical_json(report.normalized_report(row))
    )
    (qa_root / f"{category}.report.jsonl").write_bytes(report.canonical_json(row) + b"\n")
    return root, registry_view, run_id


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        ("tests/vst/test_e3_store.py::test_database_file_is_owner_only_on_posix", [registry.WSL_PROFILE]),
        (ROOT_ID, [registry.WSL_ROOT_PROFILE]),
        ("tests/vst/test_e4_runner.py::test_job_is_closed_when_thread_start_fails", [registry.WINDOWS_PROFILE]),
        (RUNNABLE_ID, [registry.WINDOWS_PROFILE, registry.WSL_PROFILE]),
    ],
)
def test_s4_runtime_registry_assigns_each_selector_to_its_supported_profile(selector, expected):
    """S4 AC-4/VST-032: platform assignment makes selector inclusion deterministic."""
    assert registry.required_runtime_profiles(selector) == expected


def test_s4_committed_registry_binds_profiles_and_preserves_policy_not_run():
    """S4 AC-4/AC-11/AC-14/VST-032: committed denominator binds every selector to its profile."""
    loaded = registry.validate_registry(REPO_ROOT)

    assert loaded.selectors_by_id[ROOT_ID]["runtime_profiles"] == [registry.WSL_ROOT_PROFILE]
    assert loaded.selectors_by_id[NOT_RUN_ID]["runtime_profiles"] == []
    assert NOT_RUN_ID in loaded.category_not_run["api"]
    assert loaded.category_profile_test_ids["functional"][registry.WINDOWS_PROFILE]
    assert loaded.category_profile_test_ids["functional"][registry.WSL_PROFILE]


def test_s4_dependency_lock_hash_is_line_ending_invariant_and_rejects_bare_carriage_return(
    tmp_path: Path,
):
    """S4 AC-4/VST-033: CRLF normalizes to LF; a bare CR cannot enter the dependency contract."""
    lock_path = tmp_path / "tools" / "qa" / "requirements.lock"
    lock_path.parent.mkdir(parents=True)
    lf_lock = (
        b"# Wheel-only, exact hashes for CPython 3.14 QA execution.\n"
        b"pytest==9.0.3 \\\n"
        + b"    --hash=sha256:" + b"a" * 64 + b"\n"
    )
    lock_path.write_bytes(lf_lock)
    lf_digest, lf_versions = run._lock_versions(tmp_path)

    lock_path.write_bytes(lf_lock.replace(b"\n", b"\r\n"))
    crlf_digest, crlf_versions = run._lock_versions(tmp_path)

    assert crlf_digest == lf_digest == hashlib.sha256(lf_lock).hexdigest()
    assert crlf_versions == lf_versions == {"pytest": "9.0.3"}

    lock_path.write_bytes(lf_lock + b"\r")
    with pytest.raises(run.QARunError, match="unsupported bare carriage returns"):
        run._lock_versions(tmp_path)


def test_s4_matrix_normalizes_crlf_lock_and_rejects_bare_carriage_return(tmp_path: Path):
    """S4 AC-4/VST-037: matrix report and run validation share canonical lock bytes."""
    root, registry_view, run_id = _write_category_report(tmp_path, registry.WINDOWS_PROFILE)
    lock_path = root / "tools" / "qa" / "requirements.lock"
    lock_path.write_bytes(LOCK.replace(b"\n", b"\r\n"))

    normalized = matrix._matrix_report(root, registry_view, {}, set())
    _, crlf_reasons = matrix._validate_run(
        root, registry_view, registry.WINDOWS_PROFILE, "functional", run_id
    )

    assert normalized["lock_sha256"] == hashlib.sha256(LOCK).hexdigest()
    assert "category report dependency-lock hash is stale" not in crlf_reasons

    lock_path.write_bytes(LOCK + b"\r")
    _, bare_cr_reasons = matrix._validate_run(
        root, registry_view, registry.WINDOWS_PROFILE, "functional", run_id
    )
    assert "category report dependency-lock hash is stale" in bare_cr_reasons


@pytest.mark.parametrize(
    ("uid", "gid", "groups", "caps", "expected"),
    [
        (997, 988, [], None, registry.WSL_PROFILE),
        (997, 988, [988], None, None),
        (0, 0, [], run.ROOT_HARNESS_CAP_MASK, registry.WSL_ROOT_PROFILE),
        (997, 988, [988, 1001], None, None),
        (0, 0, [], run.ROOT_HARNESS_CAP_MASK | (1 << 13), None),
    ],
)
def test_s4_runtime_profile_rejects_identity_and_capability_drift(
    monkeypatch, uid, gid, groups, caps, expected
):
    """S4 AC-4/AC-14/VST-033: profile identity is derived from runtime facts."""
    fake_os = SimpleNamespace(
        name="posix",
        geteuid=lambda: uid,
        getegid=lambda: gid,
        getgroups=lambda: groups,
    )
    monkeypatch.setattr(run, "os", fake_os)
    monkeypatch.setattr(run.platform, "system", lambda: "Linux")
    monkeypatch.setattr(run.platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(run.platform, "python_version", lambda: "3.12.3")
    monkeypatch.setattr(run, "_wsl_distro_identity", lambda: (True, "Ubuntu", "microsoft-wsl"))
    monkeypatch.setattr(run, "_canonical_interpreter_matches", lambda _profile: True)
    monkeypatch.setattr(run, "_linux_capability_masks", lambda: (caps, caps))

    assert run._runtime_profile() == expected


@pytest.mark.parametrize("mount_record", [
    b"31 25 0:41 / /mnt/c rw - drvfs C:\\ rw\n",
    b"31 25 0:41 / /tmp/vst-s4-candidate rw - 9p C:\\ rw\n",
])
def test_s4_wsl_boundary_rejects_windows_drive_mounts(monkeypatch, tmp_path: Path, mount_record: bytes):
    """S4 AC-11/AC-14/VST-037: Windows-drive mounts cannot back a POSIX candidate."""
    fixed_root = tmp_path / "distro-local"
    candidate = fixed_root / "candidate"
    candidate.mkdir(parents=True)
    monkeypatch.setattr(run, "WSL_CANDIDATE_ROOT", fixed_root)
    original_read_bytes = Path.read_bytes

    def read_mountinfo(path: Path):
        if path == Path("/proc/self/mountinfo"):
            return b"25 1 0:40 / / rw - ext4 /dev/sdf rw\n" + mount_record
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_mountinfo)

    with pytest.raises(run.QARunError, match="Windows-drive drvfs/9p mount"):
        run._wsl_candidate_boundary(candidate, registry.WSL_PROFILE)


def test_s4_wsl_boundary_allows_unrelated_wslg_9p_mount(monkeypatch, tmp_path: Path):
    """S4 AC-11/VST-037: an unrelated WSLg 9p mount does not invalidate distro-local evidence."""
    fixed_root = tmp_path / "distro-local"
    candidate = fixed_root / "candidate"
    candidate.mkdir(parents=True)
    monkeypatch.setattr(run, "WSL_CANDIDATE_ROOT", fixed_root)
    original_read_bytes = Path.read_bytes
    mountinfo = (
        b"25 1 0:40 / / rw - ext4 /dev/sdf rw\n"
        b"26 25 0:41 / /mnt/wslg rw - 9p drivers rw\n"
    )

    def read_mountinfo(path: Path):
        return mountinfo if path == Path("/proc/self/mountinfo") else original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_mountinfo)

    boundary = run._wsl_candidate_boundary(candidate, registry.WSL_PROFILE)

    assert boundary["windows_drive_mounts_present"] is False
    assert boundary["candidate_root_prefix"] == fixed_root.as_posix()
    assert boundary["mountinfo_sha256"] == hashlib.sha256(mountinfo).hexdigest()


def test_s4_wsl_boundary_rejects_nine_p_mount_covering_candidate(monkeypatch, tmp_path: Path):
    """S4 AC-11/AC-14/VST-037: candidate storage cannot be backed by a 9p mount."""
    fixed_root = tmp_path / "distro-local"
    candidate = fixed_root / "candidate"
    candidate.mkdir(parents=True)
    monkeypatch.setattr(run, "WSL_CANDIDATE_ROOT", fixed_root)
    mountpoint = candidate.as_posix().encode()
    mountinfo = (
        b"25 1 0:40 / / rw - ext4 /dev/sdf rw\n"
        + b"26 25 0:41 / " + mountpoint + b" rw - 9p drivers rw\n"
    )
    original_read_bytes = Path.read_bytes

    def read_mountinfo(path: Path):
        return mountinfo if path == Path("/proc/self/mountinfo") else original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_mountinfo)

    with pytest.raises(run.QARunError, match="Windows-drive drvfs/9p mount"):
        run._wsl_candidate_boundary(candidate, registry.WSL_PROFILE)


@pytest.mark.parametrize(
    ("has_only_loopback", "loopback_canary_passed", "parent_namespace_inode"),
    [
        (False, True, 4321),
        (True, False, 4321),
        (True, True, 4321),
        (True, True, None),
        (True, True, True),
        (True, True, 0),
    ],
)
def test_s4_root_harness_requires_observed_private_loopback_network(
    monkeypatch,
    tmp_path: Path,
    has_only_loopback: bool,
    loopback_canary_passed: bool,
    parent_namespace_inode,
):
    """S4 AC-14/VST-033: root proof booleans must match observed namespace/socket facts."""
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    helper_bytes = b"candidate root harness fixture\n"
    helper_path = candidate / "tools" / "qa" / "root_harness.py"
    helper_path.parent.mkdir(parents=True)
    helper_path.write_bytes(helper_bytes)
    helper_sha256 = hashlib.sha256(helper_bytes).hexdigest()
    proof_path = tmp_path / "harness-proof.json"
    boundary = {
        "candidate_root": WSL_ROOT,
        "candidate_root_prefix": WSL_PREFIX,
        "mountinfo_sha256": MOUNT_HASH,
        "windows_drive_mounts_present": False,
    }
    head = "f" * 40
    nonce = "1" * 64
    proof = {
        "schema_version": run.ROOT_HARNESS_PROOF_VERSION,
        "authority": run.ROOT_HARNESS_PROOF_AUTHORITY,
        "helper_sha256": helper_sha256,
        "run_id": "root-run",
        "run_nonce": nonce,
        "candidate_head": head,
        "runtime_profile": registry.WSL_ROOT_PROFILE,
        "distribution_id": "ubuntu",
        "distribution_version_id": "24.04",
        "kernel_release": "microsoft-wsl",
        "uid": 0,
        "gid": 0,
        "supplementary_groups": [],
        "capability_mask": f"0x{run.ROOT_HARNESS_CAP_MASK:x}",
        "automount_enabled": False,
        "interop_enabled": False,
        "private_network": True,
        "default_deny_egress": True,
        "external_canary_blocked": True,
        "loopback_canary_passed": loopback_canary_passed,
        "candidate_root": WSL_ROOT,
        "mountinfo_sha256": MOUNT_HASH,
        "parent_network_namespace_inode": parent_namespace_inode,
    }
    proof_path.write_text(json.dumps(proof), encoding="utf-8")
    fake_os = SimpleNamespace(
        geteuid=lambda: 0,
        getegid=lambda: 0,
        getgroups=lambda: [],
        stat=lambda _path: SimpleNamespace(st_ino=4322),
    )
    monkeypatch.setattr(run, "os", fake_os)
    monkeypatch.setattr(run, "_wsl_distro_identity", lambda: (True, "Ubuntu", "microsoft-wsl"))
    monkeypatch.setattr(run, "_linux_capability_masks", lambda: (run.ROOT_HARNESS_CAP_MASK, run.ROOT_HARNESS_CAP_MASK))
    monkeypatch.setattr(run, "_loopback_only_network", lambda: has_only_loopback)
    monkeypatch.setattr(run, "_loopback_canary_passed", lambda: loopback_canary_passed)
    args = Namespace(
        privileged_harness_proof=str(proof_path),
        run_nonce=nonce,
        expected_head=head,
        run_id="root-run",
    )

    if has_only_loopback and loopback_canary_passed and parent_namespace_inode == 4321:
        accepted = run._validate_privileged_harness_proof(
            args, candidate, head, registry.WSL_ROOT_PROFILE, boundary
        )
        assert accepted["candidate_root"] == WSL_ROOT
        assert accepted["mountinfo_sha256"] == MOUNT_HASH
        assert accepted["helper_sha256"] == helper_sha256
    else:
        with pytest.raises(run.QARunError, match="does not match this process, candidate, or WSL boundary"):
            run._validate_privileged_harness_proof(
                args, candidate, head, registry.WSL_ROOT_PROFILE, boundary
            )


@pytest.mark.parametrize(
    ("interfaces", "expected"),
    [([(1, "lo")], True), ([(1, "lo"), (2, "eth0")], False), ([], False)],
)
def test_s4_root_network_guard_requires_loopback_only_interface_set(
    monkeypatch, interfaces, expected
):
    """S4 AC-14/VST-033: root preflight requires no non-loopback network interface."""
    monkeypatch.setattr(run.socket, "if_nameindex", lambda: interfaces)

    assert run._loopback_only_network() is expected


def test_s4_root_network_guard_proves_only_ephemeral_loopback_connectivity():
    """S4 AC-14/VST-033: the root harness can use local loopback without external access."""
    assert run._loopback_canary_passed()


@pytest.mark.parametrize(
    ("parent_inode", "current_inode", "expected"),
    [(41, 42, True), (41, 41, False)],
)
def test_s4_root_network_guard_compares_to_captured_parent_namespace(
    monkeypatch, parent_inode: int, current_inode: int, expected: bool
):
    """S4 AC-14/VST-033: network isolation is relative to the pre-drop parent namespace."""
    observed_paths = []
    fake_os = SimpleNamespace(
        stat=lambda path: observed_paths.append(path) or SimpleNamespace(st_ino=current_inode)
    )
    monkeypatch.setattr(run, "os", fake_os)

    assert run._private_network_namespace(parent_inode) is expected
    assert observed_paths == ["/proc/self/ns/net"]


@pytest.mark.parametrize("parent_inode", [None, True, 0, -1, "41"])
def test_s4_root_network_guard_fails_closed_for_invalid_parent_namespace_inode(
    monkeypatch, parent_inode
):
    """S4 AC-14/VST-033: absent, boolean, nonpositive, or noninteger parent inode is rejected."""
    fake_os = SimpleNamespace(
        stat=lambda _path: pytest.fail("invalid parent namespace must be rejected before stat")
    )
    monkeypatch.setattr(run, "os", fake_os)

    assert run._private_network_namespace(parent_inode) is False


def test_s4_matrix_refuses_root_proof_bound_to_another_candidate(tmp_path: Path):
    """S4 AC-11/AC-14/VST-037: a passing root row must bind proof and report to one candidate."""
    root, report_registry, run_id = _write_category_report(
        tmp_path, registry.WSL_ROOT_PROFILE, root_proof_mismatch=True
    )

    _, reasons = matrix._validate_run(
        root, report_registry, registry.WSL_ROOT_PROFILE, "integration", run_id
    )

    assert any("root-profile report lacks a validated run-bound" in reason for reason in reasons)


def test_s4_matrix_refuses_root_proof_bound_to_another_helper_digest(tmp_path: Path):
    """S4 AC-11/AC-14/VST-037: root proof helper digest must match candidate source bytes."""
    root, report_registry, run_id = _write_category_report(
        tmp_path, registry.WSL_ROOT_PROFILE, root_helper_mismatch=True
    )

    _, reasons = matrix._validate_run(
        root, report_registry, registry.WSL_ROOT_PROFILE, "integration", run_id
    )

    assert any("root-profile report lacks a validated run-bound" in reason for reason in reasons)


@pytest.mark.parametrize(
    "profile", [registry.WINDOWS_PROFILE, registry.WSL_PROFILE, registry.WSL_ROOT_PROFILE]
)
def test_s4_matrix_accepts_report_with_matching_candidate_and_profile_bindings(
    tmp_path: Path, profile: str
):
    """S4 AC-11/AC-14/VST-033/037: valid profile reports satisfy their exact evidence contract."""
    root, report_registry, run_id = _write_category_report(tmp_path, profile)

    category = "integration" if profile == registry.WSL_ROOT_PROFILE else "functional"
    _, reasons = matrix._validate_run(root, report_registry, profile, category, run_id)

    assert reasons == []


def test_s4_matrix_rejects_missing_profile_report_references(tmp_path: Path):
    """S4 AC-11/VST-037: a required profile/category report cannot be omitted."""
    root = tmp_path / "candidate"
    (root / "tools" / "qa").mkdir(parents=True)
    (root / "tools" / "qa" / "requirements.lock").write_bytes(LOCK)
    profile_ids = {
        profile: [RUNNABLE_ID] if profile in {registry.WINDOWS_PROFILE, registry.WSL_PROFILE} else []
        for profile in registry.RUNTIME_PROFILES
    }
    registry_view = SimpleNamespace(
        candidate_head=HEAD,
        sha256="c" * 64,
        category_profile_test_ids={"functional": profile_ids},
        category_not_run={},
    )
    expected = matrix._expected_report_refs(registry_view)

    output = matrix._matrix_report(root, registry_view, {}, expected)

    assert output["result"] == "BLOCKED"
    assert any("reports are not referenced" in reason for reason in output["reasons"])


def test_s4_matrix_never_promotes_a_policy_not_run_selector(tmp_path: Path):
    """S4 AC-11/AC-14/VST-032/037: policy NOT_RUN stays outside every passing denominator."""
    profile_ids = {profile: [] for profile in registry.RUNTIME_PROFILES}
    registry_view = SimpleNamespace(
        candidate_head=HEAD,
        sha256="c" * 64,
        category_profile_test_ids={"api": profile_ids},
        category_profile_not_run={"api": {profile: {} for profile in registry.RUNTIME_PROFILES}},
        category_inventory_ids={"api": [NOT_RUN_ID]},
        category_not_run={"api": {NOT_RUN_ID: "policy restriction"}},
        category_test_ids={"api": []},
        selectors_by_id={NOT_RUN_ID: {"runtime_profiles": [], "primary_category": "api"}},
    )
    root = tmp_path / "candidate"
    lock_path = root / "tools" / "qa" / "requirements.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_bytes(LOCK)

    output = matrix._matrix_report(root, registry_view, {}, set())

    assert output["result"] == "FAIL"
    assert any("policy NOT_RUN" in reason for reason in output["reasons"])


def test_s4_matrix_rejects_skipped_required_concrete_cases():
    """S4 AC-11/AC-14/VST-037: a skipped assigned case cannot become selector pass evidence."""
    node_id = f"{RUNNABLE_ID}::case"
    row = {
        "passed_test_ids": [],
        "failed_test_ids": [],
        "skipped_test_ids": [RUNNABLE_ID],
        "xfail_test_ids": [],
        "uncollected_test_ids": [],
        "unexpected_node_ids": [],
        "result": "FAIL",
        "exit_code": 1,
        "capture": {
            "capture_incomplete": False,
            "timed_out": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
        },
        "case_outcomes": [{"node_id": node_id, "selector_id": RUNNABLE_ID, "outcome": "skipped"}],
        "collected_node_ids": [node_id],
        "executed_node_ids": [node_id],
    }

    reasons, _ = matrix._verify_case_accounting([RUNNABLE_ID], row)

    assert any("skipped_test_ids" in reason for reason in reasons)
    assert any("non-approving" in reason for reason in reasons)


def test_s4_matrix_rejects_stale_candidate_and_corrupt_artifact_range(tmp_path: Path):
    """S4 AC-11/AC-14/VST-037: exact-head and byte-range evidence are independently checked."""
    root, registry_view, run_id = _write_category_report(tmp_path / "stale", registry.WINDOWS_PROFILE)
    report_path = root / "docs" / "sdlc" / "evidence" / "qa" / "functional.report.jsonl"
    row = json.loads(report_path.read_text(encoding="utf-8"))
    row["candidate_head"] = "f" * 40
    row["normalized_sha256"] = report.sha256_bytes(
        report.canonical_json(report.normalized_report(row))
    )
    report_path.write_bytes(report.canonical_json(row) + b"\n")
    _, stale_reasons = matrix._validate_run(
        root, registry_view, registry.WINDOWS_PROFILE, "functional", run_id
    )
    assert any("candidate HEAD is stale" in reason for reason in stale_reasons)

    root, registry_view, run_id = _write_category_report(tmp_path / "corrupt", registry.WINDOWS_PROFILE)
    (root / "docs" / "sdlc" / "evidence" / "qa" / "functional.stdout.txt").write_bytes(
        b"FAIL selector\n"
    )
    _, corrupt_reasons = matrix._validate_run(
        root, registry_view, registry.WINDOWS_PROFILE, "functional", run_id
    )
    assert any("stdout byte range digest does not match" in reason for reason in corrupt_reasons)
