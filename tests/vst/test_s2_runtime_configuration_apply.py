"""S2-4.11 contract tests for the pinned non-secret WSL config installer."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/qa/apply_s2_runtime_configuration.py"
BUNDLE = ROOT / "docs/sdlc/runtime-config"
SOURCE_COMMIT = "943ee9af3361df74f513e5c4f361a57ca1b2df8f"
SPEC = importlib.util.spec_from_file_location("s2_config_apply", SCRIPT)
assert SPEC and SPEC.loader
APPLY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLY)


@pytest.fixture(autouse=True)
def candidate_runtime_config_blobs(monkeypatch):
    read_blob = APPLY._git_blob

    def read_candidate(commit, relative_path):
        if relative_path.startswith("docs/sdlc/runtime-config/"):
            return (ROOT / relative_path).read_bytes()
        return read_blob(commit, relative_path)

    monkeypatch.setattr(APPLY, "_git_blob", read_candidate)
    # These tests exercise candidate payload construction; the production pushed-HEAD
    # guard is a separate boundary and the local candidate is intentionally uncommitted.
    monkeypatch.setattr(APPLY, "_validate_deployment_commit", lambda _commit: None)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inventory() -> dict:
    bundle = json.loads((BUNDLE / "bundle-manifest.json").read_text(encoding="utf-8"))
    layout = json.loads((BUNDLE / "installation-layout.json").read_text(encoding="utf-8"))
    entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
    entries += [item for item in bundle["units"] if item["publication"].startswith("new absent-only")]
    files = {}
    for entry in entries:
        files[entry["destination"]] = {
            "state": "PRESENT",
            "kind": "regular",
            "uid": entry["uid"],
            "gid": entry["gid"],
            "mode": entry["mode"] if isinstance(entry["mode"], str) else format(entry["mode"], "04o"),
            "size": 17,
            "sha256": "a" * 64,
        }
    return {
        "schema": APPLY.INVENTORY_SCHEMA,
        "captured_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "boot_id": "270cd88b-183f-426c-8add-872d9e98bcec",
        "source_head": "ee69f9fbf074a4c73d2d5d1da81c627a57d06071",
        "runtime_selector": {
            "state": "PRESENT",
            "kind": "symlink",
            "link_target": "/opt/vst-runtime-ee69f9fbf074a4c73d2d5d1da81c627a57d06071",
        },
        "configuration_files": files,
    }


def _write_inventory(tmp_path: Path, inventory: dict) -> tuple[Path, str]:
    path = tmp_path / "inventory.json"
    raw = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return path, _sha(raw)


def _candidate_config_overrides(mutation: str) -> dict[str, bytes]:
    """Build a re-pinned candidate with exactly one broken cross-binding."""
    names = ("task-manifest.json", "assignment-delegation-policy.json",
             "supervisor-service.json")
    values = {name: json.loads((BUNDLE / name).read_bytes()) for name in names}
    bundle = json.loads((BUNDLE / "bundle-manifest.json").read_bytes())
    task = values["task-manifest.json"]
    policy = values["assignment-delegation-policy.json"]
    supervisor = values["supervisor-service.json"]

    if mutation == "task-schema":
        values["task-manifest.json"] = []
    elif mutation == "policy-schema":
        values["assignment-delegation-policy.json"] = []
    elif mutation == "supervisor-schema":
        values["supervisor-service.json"] = []
    elif mutation == "task-base-head":
        task["base_head"] = "f" * 40
    elif mutation == "task-scope":
        task["scope"] = ["tests/another-selector.py"]
    elif mutation == "policy-source-head":
        policy["source_head"] = "f" * 40
    elif mutation == "policy-source-binding":
        policy["manifest_sha256"] = "f" * 64
    elif mutation == "allowed-task-digest":
        policy["allowed_assignments"][0]["task_manifest_sha256"] = "f" * 64
    elif mutation == "supervisor-policy-digest":
        supervisor["assignment_policy_sha256"] = "f" * 64
    elif mutation == "bundle-task-source-head":
        bundle["task_source_head"] = "f" * 40
    else:
        raise AssertionError(f"unknown test mutation: {mutation}")

    if mutation not in {"task-schema", "policy-schema", "supervisor-schema"}:
        task_digest = _sha(json.dumps(
            task, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False).encode("utf-8"))
        bundle["task_manifest_sha256"] = task_digest
        if mutation != "allowed-task-digest":
            policy["allowed_assignments"][0]["task_manifest_sha256"] = task_digest
        policy_digest = _sha(json.dumps(
            policy, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False).encode("utf-8"))
        bundle["assignment_policy_sha256"] = policy_digest
        if mutation != "supervisor-policy-digest":
            supervisor["assignment_policy_sha256"] = policy_digest

    overrides = {}
    records = {item["path"]: item for item in bundle["files"]}
    for name in names:
        raw = json.dumps(values[name], indent=2, ensure_ascii=False) + "\n"
        encoded = raw.encode("utf-8")
        overrides[name] = encoded
        records[name]["size"] = len(encoded)
        records[name]["sha256"] = _sha(encoded)
    bundle_raw = (json.dumps(bundle, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    overrides["bundle-manifest.json"] = bundle_raw
    return overrides


def _use_candidate_overrides(monkeypatch, overrides: dict[str, bytes]) -> None:
    read_blob = APPLY._git_blob

    def read_candidate(commit: str, relative_path: str) -> bytes:
        if relative_path.startswith("docs/sdlc/runtime-config/"):
            name = relative_path.removeprefix("docs/sdlc/runtime-config/")
            if name in overrides:
                return overrides[name]
            return (BUNDLE / name).read_bytes()
        return read_blob(commit, relative_path)

    bundle_digest = _sha(overrides["bundle-manifest.json"])
    monkeypatch.setattr(APPLY, "_git_blob", read_candidate)
    monkeypatch.setattr(APPLY, "BUNDLE_MANIFEST_SHA256", bundle_digest)
    # These tests isolate payload identity validation from the separate pushed-HEAD guard.
    monkeypatch.setattr(APPLY, "_validate_deployment_commit", lambda _commit: None)


def test_payload_contains_exact_non_secret_candidate_and_pins_current_state(tmp_path, monkeypatch):
    path, digest = _write_inventory(tmp_path, _inventory())
    git_blobs = []
    read_blob = APPLY._git_blob

    def record_git_blob(commit, relative_path):
        git_blobs.append((commit, relative_path))
        if relative_path.startswith("docs/sdlc/runtime-config/"):
            return (ROOT / relative_path).read_bytes()
        return read_blob(commit, relative_path)

    monkeypatch.setattr(APPLY, "_git_blob", record_git_blob)

    raw_payload = APPLY.build_payload(path, digest, SOURCE_COMMIT)
    payload = json.loads(raw_payload)

    bundle = json.loads((BUNDLE / "bundle-manifest.json").read_text(encoding="utf-8"))
    layout = json.loads((BUNDLE / "installation-layout.json").read_text(encoding="utf-8"))
    expected = {item["destination"] for item in bundle["configuration_installation"]}
    expected.update(item["destination"] for item in layout["unit_overrides"])
    expected.update(item["destination"] for item in bundle["units"] if item["publication"].startswith("new absent-only"))

    assert payload["schema"] == "VST_S2_RUNTIME_CONFIG_APPLY_V2"
    assert len(payload["files"]) == 27
    assert payload["source_head"] == APPLY.RUNTIME_SOURCE_HEAD
    assert payload["task_source_head"] == APPLY.TASK_SOURCE_HEAD
    assert payload["source_head"] != payload["task_source_head"]
    assert {item["destination"] for item in payload["files"]} == expected
    assert "selected_runtime_path" not in json.loads(path.read_bytes())
    assert payload["selected_runtime_path"] == json.loads(path.read_bytes())["runtime_selector"]["link_target"]
    assert payload["bundle_manifest_sha256"] == APPLY.BUNDLE_MANIFEST_SHA256
    assert payload["installation_layout_sha256"] == APPLY.INSTALLATION_LAYOUT_SHA256
    assert _sha(base64.b64decode(payload["bundle_manifest_b64"])) == APPLY.BUNDLE_MANIFEST_SHA256
    assert _sha(base64.b64decode(payload["installation_layout_b64"])) == APPLY.INSTALLATION_LAYOUT_SHA256
    assert base64.b64decode(payload["inventory_b64"]) == path.read_bytes()
    assert _sha(base64.b64decode(payload["inventory_b64"])) == digest
    assert git_blobs and all(commit == SOURCE_COMMIT for commit, _ in git_blobs)
    assert {name for _, name in git_blobs} == {
        "docs/sdlc/runtime-config/bundle-manifest.json",
        "docs/sdlc/runtime-config/installation-layout.json",
        "docs/sdlc/runtime-config/deployment-source-manifest.json",
        "docs/sdlc/runtime-config/task-manifest.json",
        "docs/sdlc/runtime-config/assignment-delegation-policy.json",
        "docs/sdlc/runtime-config/supervisor-service.json",
        "tools/qa/runtime_snapshot_transaction.py",
        *("docs/sdlc/runtime-config/" + item["source"] for item in
          list(bundle["configuration_installation"]) + list(layout["unit_overrides"]) + [
              item for item in bundle["units"] if item["publication"].startswith("new absent-only")
          ]),
    }
    for item in payload["files"]:
        candidate = base64.b64decode(item["content_b64"], validate=True)
        assert _sha(candidate) == item["expected_new"]["sha256"]
        assert item["expected_current"]["state"] == "file"
        assert b"PRIVATE KEY" not in candidate
        assert "private" not in item["destination"].lower()


def test_installer_pins_current_candidate_in_local_and_root_checks():
    bundle_bytes = (BUNDLE / "bundle-manifest.json").read_bytes()
    layout_bytes = (BUNDLE / "installation-layout.json").read_bytes()
    bundle_digest = _sha(bundle_bytes)
    layout_digest = _sha(layout_bytes)

    assert bundle_digest == APPLY.BUNDLE_MANIFEST_SHA256
    assert layout_digest == APPLY.INSTALLATION_LAYOUT_SHA256
    assert f'BUNDLE_SHA256 = "{bundle_digest}"' in APPLY._REMOTE
    assert f'LAYOUT_SHA256 = "{layout_digest}"' in APPLY._REMOTE


@pytest.mark.parametrize("name", ["task-schema", "policy-schema", "supervisor-schema"])
def test_payload_rejects_malformed_task_identity_schema_before_digest_acceptance(
        tmp_path, monkeypatch, name):
    path, digest = _write_inventory(tmp_path, _inventory())
    _use_candidate_overrides(monkeypatch, _candidate_config_overrides(name))

    error = ("task manifest does not satisfy the VST contract" if name == "task-schema"
             else "task identity configuration must be JSON objects")
    with pytest.raises(ValueError, match=error):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


@pytest.mark.parametrize("mutation", [
    "task-base-head", "task-scope", "policy-source-head", "policy-source-binding",
    "allowed-task-digest", "supervisor-policy-digest", "bundle-task-source-head",
])
def test_payload_rejects_task_runtime_identity_cross_binding_mismatch(
        tmp_path, monkeypatch, mutation):
    path, digest = _write_inventory(tmp_path, _inventory())
    _use_candidate_overrides(monkeypatch, _candidate_config_overrides(mutation))

    expected_error = (
        "task-source identity differs|task manifest, assignment policy and runtime bundle identities disagree"
    )
    with pytest.raises(ValueError, match=expected_error):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


def test_payload_refuses_bundle_bytes_that_do_not_match_the_pinned_digest(
    tmp_path, monkeypatch
):
    path, digest = _write_inventory(tmp_path, _inventory())
    read_blob = APPLY._git_blob
    pinned_bundle = (BUNDLE / "bundle-manifest.json").read_bytes()

    def changed_bundle(commit, relative_path):
        if relative_path == "docs/sdlc/runtime-config/bundle-manifest.json":
            return pinned_bundle + b" "
        if relative_path.startswith("docs/sdlc/runtime-config/"):
            return (ROOT / relative_path).read_bytes()
        return read_blob(commit, relative_path)

    monkeypatch.setattr(APPLY, "_git_blob", changed_bundle)

    with pytest.raises(ValueError, match="committed config bundle differs"):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


def test_payload_rejects_changed_inventory_digest_before_transfer(tmp_path):
    path, _ = _write_inventory(tmp_path, _inventory())

    with pytest.raises(ValueError, match="exact SHA-256 pin"):
        APPLY.build_payload(path, "0" * 64, SOURCE_COMMIT)


def test_payload_rejects_stale_inventory(tmp_path):
    inventory = _inventory()
    inventory["captured_utc"] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    path, digest = _write_inventory(tmp_path, inventory)

    with pytest.raises(ValueError, match="five-minute freshness"):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


@pytest.mark.parametrize("mutation", ["missing", "unknown-kind", "invalid-fingerprint"])
def test_payload_refuses_unknown_target_state_before_transfer(tmp_path, mutation):
    inventory = _inventory()
    destination = next(iter(inventory["configuration_files"]))
    if mutation == "missing":
        del inventory["configuration_files"][destination]
    elif mutation == "unknown-kind":
        inventory["configuration_files"][destination] = {"state": "symlink", "target": "/tmp/other"}
    else:
        inventory["configuration_files"][destination]["sha256"] = "not-a-hash"
    path, digest = _write_inventory(tmp_path, inventory)

    with pytest.raises(ValueError):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


def test_payload_accepts_exact_absent_state_and_octal_inventory_mode(tmp_path):
    inventory = _inventory()
    destination = next(iter(inventory["configuration_files"]))
    inventory["configuration_files"][destination] = {"state": "ABSENT"}
    path, digest = _write_inventory(tmp_path, inventory)

    payload = json.loads(APPLY.build_payload(path, digest, SOURCE_COMMIT))
    absent = next(item for item in payload["files"] if item["destination"] == destination)
    assert absent["expected_current"] == {"state": "absent"}
    assert absent["expected_new"]["mode"] == int(
        json.loads((BUNDLE / "bundle-manifest.json").read_text(encoding="utf-8"))["configuration_installation"][0]["mode"], 8
    )


def test_payload_rejects_inventory_selecting_another_runtime(tmp_path):
    inventory = _inventory()
    inventory["runtime_selector"]["link_target"] = "/opt/vst-runtime-a600774649527ff0b33eb81f4d431f8226119b2c"
    path, digest = _write_inventory(tmp_path, inventory)

    with pytest.raises(ValueError, match="selected S2 runtime"):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


@pytest.mark.parametrize("source_commit", ["cb7e2ed", "z" * 40])
def test_payload_rejects_non_full_or_nonexistent_source_commit(tmp_path, source_commit):
    path, digest = _write_inventory(tmp_path, _inventory())

    with pytest.raises(ValueError):
        APPLY.build_payload(path, digest, source_commit)


def test_wsl_source_loader_preserves_long_utf8_source_binary_payload_and_argv():
    import subprocess
    import sys

    source = "import json,sys\nraw=sys.stdin.buffer.read()\nsys.stdout.buffer.write(json.dumps({'argv':sys.argv[1:],'raw':raw.hex()}).encode())\n" + "#\n" * 18000
    payload = b"\x00\xffpayload\r\n\x80"
    framed = APPLY._remote_stdin(source, payload)
    completed = subprocess.run(
        [sys.executable, "-I", "-c", APPLY._WSL_SOURCE_LOADER, "kept-arg", "second"],
        input=framed, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert len(source) > 32767
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    observed = json.loads(completed.stdout)
    assert observed["argv"] == ["kept-arg", "second"]
    assert bytes.fromhex(observed["raw"]) == payload


@pytest.mark.parametrize("frame, message", [
    (b"short", "header is truncated"),
    ((0).to_bytes(8, "big"), "size is invalid"),
    ((512 * 1024 + 1).to_bytes(8, "big"), "size is invalid"),
    ((4).to_bytes(8, "big") + b"ab", "frame is truncated"),
])
def test_wsl_source_loader_rejects_invalid_frame_before_source_execution(frame, message):
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, "-I", "-c", APPLY._WSL_SOURCE_LOADER],
        input=frame, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    assert completed.returncode != 0
    if frame == b"short":
        assert completed.stdout == b""
    else:
        assert message.encode() in completed.stderr
    assert b"source executed" not in completed.stderr


def _run_embedded_repo_mount_guard(*, existing=None, remount_exit=0, capture_exit=False,
                                  replace_mount_id_after_remount=False):
    """Execute the actual apply-child mount guard with host I/O represented by a fake runner."""
    import ast
    import io
    from types import SimpleNamespace

    tree = ast.parse(APPLY._REMOTE)
    start = next(index for index, node in enumerate(tree.body)
                 if isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "created_repo_mount"
                     for target in node.targets))
    end = next(index for index, node in enumerate(tree.body)
               if isinstance(node, ast.Assign) and any(
                   isinstance(target, ast.Name) and target.id == "bundle_raw"
                   for target in node.targets))
    nodes = tree.body[start:end]
    state = dict(existing) if existing is not None else None
    calls = []
    callbacks = []
    remount_completed = False

    class Completed:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(argv, **_kwargs):
        nonlocal state, remount_completed
        calls.append(list(argv))
        if argv[0] == "/usr/bin/mountpoint":
            return Completed(0 if state is not None else 32)
        if argv[0] == "/usr/bin/findmnt":
            if state is None:
                return Completed(1)
            if replace_mount_id_after_remount and remount_completed:
                state["id"] = "999"
            fields = [state[name] for name in ("id", "target", "source", "filesystem", "options")]
            return Completed(stdout=" ".join(fields) + "\n")
        if argv[0] == "/usr/bin/mount" and "-t" in argv:
            state = {"id": "501", "target": "/mnt/d", "source": "D:",
                     "filesystem": "9p", "options": "rw,relatime"}
            return Completed()
        if argv[0] == "/usr/bin/mount" and "remount,ro" in argv:
            if remount_exit == 0 and state is not None:
                state["options"] = "ro,relatime"
                remount_completed = True
            return Completed(remount_exit)
        if argv[0] == "/usr/bin/umount":
            if (state is not None and argv[-1] == state["target"]
                    and state["id"] == "501"):
                state = None
            return Completed()
        raise AssertionError(f"unexpected command in mount preflight: {argv!r}")

    namespace = {
        "atexit": SimpleNamespace(register=callbacks.append),
        "os": SimpleNamespace(path=SimpleNamespace(isdir=lambda _path: True,
                                                    islink=lambda _path: False)),
        "subprocess": SimpleNamespace(run=fake_run, PIPE=object()),
        "sys": SimpleNamespace(stderr=io.StringIO()),
    }
    try:
        exec(compile(ast.Module(body=nodes, type_ignores=[]),
                     "<embedded-repo-mount-guard>", "exec"), namespace)
    except SystemExit as exc:
        if not capture_exit:
            raise
        namespace["preflight_error"] = exc
    return namespace, calls, callbacks, lambda: state


def test_remote_apply_mount_is_exact_readonly_and_owned_cleanup_runs():
    namespace, calls, callbacks, state = _run_embedded_repo_mount_guard()

    assert namespace["created_repo_mount"] is True
    assert namespace["owned_repo_mount_id"] == "501"
    assert state() == {"id": "501", "target": "/mnt/d", "source": "D:",
                       "filesystem": "9p", "options": "ro,relatime"}
    assert len(callbacks) == 1
    assert [call for call in calls if call[:2] == ["/usr/bin/mount", "-t"]] == [
        ["/usr/bin/mount", "-t", "drvfs", "D:", "/mnt/d", "-o", "ro"]]
    assert [call for call in calls if "remount,ro" in call] == [
        ["/usr/bin/mount", "-o", "remount,ro", "/mnt/d"]]

    namespace["cleanup_repo_mount"]()

    assert state() is None
    assert [call for call in calls if call[0] == "/usr/bin/umount"] == [
        ["/usr/bin/umount", "/mnt/d"]]
    # The independent exact-Git source checks remain in the remote apply contract.
    assert 'deployment_commit + ":docs/sdlc/runtime-config/deployment-source-manifest.json"' in APPLY._REMOTE
    assert 'deployment_commit + ":" + relative' in APPLY._REMOTE
    assert '"merge-base", "--is-ancestor", deployment_commit, "@{upstream}"' in APPLY._REMOTE


def test_remote_apply_owned_rw_mount_is_normally_cleaned_when_ro_remount_fails():
    namespace, calls, _callbacks, state = _run_embedded_repo_mount_guard(
        remount_exit=1, capture_exit=True)

    assert str(namespace["preflight_error"]) == "repository mount could not be remounted read-only"
    assert state() is None
    assert [call for call in calls if call[0] == "/usr/bin/umount"] == [
        ["/usr/bin/umount", "/mnt/d"]]


def test_remote_apply_fails_closed_when_mount_id_changes_after_remount():
    namespace, calls, callbacks, state = _run_embedded_repo_mount_guard(
        capture_exit=True, replace_mount_id_after_remount=True)

    assert str(namespace["preflight_error"]) == (
        "repository mount identity changed during read-only remount")
    assert namespace["owned_repo_mount_id"] == "501"
    assert state() == {"id": "999", "target": "/mnt/d", "source": "D:",
                       "filesystem": "9p", "options": "ro,relatime"}
    assert len(callbacks) == 1
    assert [call for call in calls if call[0] == "/usr/bin/umount"] == []
    assert "S2_REPO_MOUNT_CLEANUP=refused-mount-changed" in (
        namespace["sys"].stderr.getvalue())
    # The embedded guard is extracted only up to bundle_raw, so no inventory or
    # configuration payload can be consumed after the identity mismatch.


@pytest.mark.parametrize("existing, message", [
    ({"id": "31", "target": "/mnt/d", "source": "D:", "filesystem": "9p",
      "options": "rw,relatime"}, "pre-existing repository mount is writable"),
    ({"id": "32", "target": "/mnt/d", "source": "E:", "filesystem": "9p",
      "options": "ro,relatime"}, "repository mount source or filesystem"),
], ids=["preexisting-rw", "wrong-source"])
def test_remote_apply_mount_guard_refuses_preexisting_rw_or_wrong_source(existing, message):
    with pytest.raises(SystemExit, match=message):
        _run_embedded_repo_mount_guard(existing=existing)


def test_remote_apply_cleanup_refuses_replaced_mount_id():
    namespace, calls, _callbacks, state = _run_embedded_repo_mount_guard()
    state()["id"] = "999"

    namespace["cleanup_repo_mount"]()

    assert state()["id"] == "999"
    assert not [call for call in calls if call[0] == "/usr/bin/umount"]
    assert "S2_REPO_MOUNT_CLEANUP=refused-mount-changed" in namespace["sys"].stderr.getvalue()


def test_remote_apply_cleanup_reports_metadata_check_failure():
    namespace, _calls, _callbacks, _state = _run_embedded_repo_mount_guard()

    def fail_metadata_check():
        raise OSError("mount table unavailable")

    namespace["repo_mount_record"] = fail_metadata_check
    namespace["cleanup_repo_mount"]()

    assert "S2_REPO_MOUNT_CLEANUP=check-failed-OSError" in namespace["sys"].stderr.getvalue()


def _run_embedded_manifest_pin_checks(payload):
    import ast
    import base64

    tree = ast.parse(APPLY._REMOTE)
    start = next(index for index, node in enumerate(tree.body)
                 if isinstance(node, ast.Assign) and any(
                     isinstance(target, ast.Name) and target.id == "bundle_raw"
                     for target in node.targets))
    end = next(index for index, node in enumerate(tree.body)
               if isinstance(node, ast.Assign) and any(
                   isinstance(child, ast.Name) and child.id == "bundle"
                   for target in node.targets for child in ast.walk(target)))
    namespace = {"base64": base64, "hashlib": hashlib, "json": json,
                 "BUNDLE_SHA256": APPLY.BUNDLE_MANIFEST_SHA256,
                 "LAYOUT_SHA256": APPLY.INSTALLATION_LAYOUT_SHA256,
                 "p": payload}
    exec(compile(ast.Module(body=tree.body[start:end + 1], type_ignores=[]),
                 "<embedded-manifest-hash-guard>", "exec"), namespace)
    return namespace


def test_remote_apply_accepts_exact_pinned_manifests_without_git_read():
    bundle_raw = (BUNDLE / "bundle-manifest.json").read_bytes()
    layout_raw = (BUNDLE / "installation-layout.json").read_bytes()
    payload = {
        "bundle_manifest_b64": base64.b64encode(bundle_raw).decode("ascii"),
        "bundle_manifest_sha256": APPLY.BUNDLE_MANIFEST_SHA256,
        "installation_layout_b64": base64.b64encode(layout_raw).decode("ascii"),
        "installation_layout_sha256": APPLY.INSTALLATION_LAYOUT_SHA256,
    }

    namespace = _run_embedded_manifest_pin_checks(payload)

    assert namespace["bundle"]["state"] == "PREPARED_NOT_INSTALLED"
    assert namespace["layout"]["unit_overrides"]


@pytest.mark.parametrize("field, mutation", [
    ("bundle_manifest_b64", lambda raw: base64.b64encode(base64.b64decode(raw) + b" ").decode("ascii")),
    ("bundle_manifest_sha256", lambda _value: "0" * 64),
    ("installation_layout_b64", lambda raw: base64.b64encode(base64.b64decode(raw) + b" ").decode("ascii")),
    ("installation_layout_sha256", lambda _value: "0" * 64),
], ids=["bundle-bytes", "bundle-digest", "layout-bytes", "layout-digest"])
def test_remote_apply_rejects_tampered_bundle_or_layout_hash(field, mutation):
    bundle_raw = (BUNDLE / "bundle-manifest.json").read_bytes()
    layout_raw = (BUNDLE / "installation-layout.json").read_bytes()
    payload = {
        "bundle_manifest_b64": base64.b64encode(bundle_raw).decode("ascii"),
        "bundle_manifest_sha256": APPLY.BUNDLE_MANIFEST_SHA256,
        "installation_layout_b64": base64.b64encode(layout_raw).decode("ascii"),
        "installation_layout_sha256": APPLY.INSTALLATION_LAYOUT_SHA256,
    }
    payload[field] = mutation(payload[field])

    with pytest.raises(SystemExit, match="configuration manifest differs from the independently pinned candidate"):
        _run_embedded_manifest_pin_checks(payload)


def test_remote_stdin_rejects_source_and_payload_over_bounds():
    with pytest.raises(ValueError, match="source exceeds"):
        APPLY._remote_stdin("x" * (APPLY.MAX_REMOTE_SOURCE_BYTES + 1), b"")
    with pytest.raises(ValueError, match="payload exceeds"):
        APPLY._remote_stdin("pass", b"x" * (APPLY.MAX_APPLY_PAYLOAD_BYTES + 1))


@pytest.mark.parametrize("recovery", [False, True], ids=["normal-apply", "recovery"])
def test_main_wsl_call_uses_short_loader_and_framed_remote_source(
        monkeypatch, tmp_path, recovery, capsys):
    import sys

    approved_commit = "a" * 40
    payload = b"known-payload\x00\xff"
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_bytes(b"inventory")
    calls = []

    class Completed:
        returncode = 0
        stdout = b""
        stderr = b""

    def fake_run(argv, **kwargs):
        if argv[0] == "git":
            if "hash-object" in argv:
                result = Completed()
                result.stdout = "f" * 40 + "\n"
                return result
            if "rev-parse" in argv:
                result = Completed()
                if "tools/qa/apply_s2_runtime_configuration.py" in argv[-1]:
                    result.stdout = "f" * 40 + "\n"
                else:
                    result.stdout = approved_commit + "\n" if kwargs.get("text") else b"b" * 40
                return result
        if argv[0] == "wsl.exe":
            calls.append((argv, kwargs))
            return Completed()
        raise AssertionError(f"unexpected subprocess: {argv!r}")

    monkeypatch.setattr(APPLY.subprocess, "run", fake_run)
    if recovery:
        monkeypatch.setattr(APPLY, "_git_blob", lambda _commit, _path: b"committed helper")
        monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--approved-deployment-commit", approved_commit,
                                           "--recover-transaction", "c" * 32])
        expected_source = APPLY._RECOVERY_REMOTE
        expected_payload = json.dumps({
            "schema": "VST_S2_RUNTIME_TRANSACTION_RECOVERY_V1",
            "transaction_id": "c" * 32,
            "transaction_helper_b64": base64.b64encode(b"committed helper").decode("ascii"),
            "transaction_helper_sha256": _sha(b"committed helper"),
        }, sort_keys=True, separators=(",", ":")).encode("ascii")
        expected_args = [APPLY._sha(expected_payload), approved_commit,
                         APPLY.WSL_REPOSITORY_ROOT, "c" * 32]
    else:
        monkeypatch.setattr(APPLY, "_current_inventory_validation_identity", lambda: ("d" * 40, "e" * 64))
        monkeypatch.setattr(APPLY, "build_payload", lambda *_args, **_kwargs: payload)
        monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--approved-deployment-commit", approved_commit,
                                           "--inventory", str(inventory_path), "--inventory-sha256", "f" * 64])
        expected_source = APPLY._REMOTE
        expected_payload = payload
        expected_args = [APPLY._sha(payload), approved_commit, APPLY.WSL_REPOSITORY_ROOT]

    assert APPLY.main() == 0
    capsys.readouterr()
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == ["wsl.exe", "--distribution", "Ubuntu-24.04", "--user", "root", "--exec",
                    "/usr/bin/python3.12", "-I", "-B", "-S", "-c", APPLY._WSL_SOURCE_LOADER,
                    *expected_args]
    assert len(APPLY._WSL_SOURCE_LOADER.encode("utf-8")) < 32767
    assert kwargs["input"] == APPLY._remote_stdin(expected_source, expected_payload)
    assert kwargs["input"][8:8 + len(expected_source.encode("utf-8"))] == expected_source.encode("utf-8")
    assert kwargs["input"][8 + len(expected_source.encode("utf-8")):] == expected_payload


def test_main_fails_closed_when_owned_repo_mount_cleanup_marker_reports_failure(
        monkeypatch, tmp_path, capsys):
    import sys

    approved_commit = "a" * 40
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_bytes(b"inventory")

    class Completed:
        returncode = 0
        stdout = b""
        stderr = b"S2_REPO_MOUNT_CLEANUP=umount-failed\n"

    def fake_run(argv, **_kwargs):
        if argv[0] == "git":
            result = Completed()
            result.stderr = ""
            if "hash-object" in argv:
                result.stdout = "f" * 40 + "\n"
            elif "rev-parse" in argv:
                result.stdout = "f" * 40 + "\n" if "tools/qa/apply_s2_runtime_configuration.py" in argv[-1] else approved_commit + "\n"
            else:
                raise AssertionError(f"unexpected Git command: {argv!r}")
            return result
        if argv[0] == "wsl.exe":
            return Completed()
        raise AssertionError(f"unexpected subprocess: {argv!r}")

    monkeypatch.setattr(APPLY.subprocess, "run", fake_run)
    monkeypatch.setattr(APPLY, "_current_inventory_validation_identity",
                        lambda: ("d" * 40, "e" * 64))
    monkeypatch.setattr(APPLY, "build_payload", lambda *_args, **_kwargs: b"payload")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--approved-deployment-commit", approved_commit,
                                       "--inventory", str(inventory_path), "--inventory-sha256", "f" * 64])

    assert APPLY.main() == 2
    assert "S2_REPO_MOUNT_CLEANUP=umount-failed" in capsys.readouterr().err


def _run_embedded_unit_admission(output, *, unit="vst-supervisor.service",
                                 protected_units=("vst-supervisor.service",)):
    import ast
    from types import SimpleNamespace

    tree = ast.parse(APPLY._REMOTE)
    parser = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == "parse_unit_identity")
    admission = next(node for node in tree.body
                     if isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                     and node.target.id == "unit")
    calls = []

    class Completed:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if "--property=LoadState" in argv:
            return Completed("loaded\n")
        if "--property=ActiveState,SubState,InvocationID,ControlGroup,UnitFileState" in argv:
            return Completed(output)
        raise AssertionError(f"unexpected systemd command: {argv!r}")

    namespace = {
        "subprocess": SimpleNamespace(run=fake_run, DEVNULL=object(), PIPE=object()),
        "units": (unit,),
        "protected_units": protected_units,
        "unit_before": {},
    }
    exec(compile(ast.Module(body=[parser, admission], type_ignores=[]),
                 "<embedded-unit-admission>", "exec"), namespace)
    return namespace["unit_before"], calls


def _named_unit_output(*, active="inactive", sub="dead", invocation="",
                       control_group="", file_state="disabled", order=None):
    values = {
        "ActiveState": active,
        "SubState": sub,
        "InvocationID": invocation,
        "ControlGroup": control_group,
        "UnitFileState": file_state,
    }
    keys = order or ["ControlGroup", "ActiveState", "SubState", "UnitFileState", "InvocationID"]
    return "".join(f"{key}={values[key]}\n" for key in keys)


def test_embedded_unit_admission_reads_named_reordered_empty_systemd_properties():
    before, calls = _run_embedded_unit_admission(_named_unit_output())

    assert before["vst-supervisor.service"] == {
        "active": False,
        "substate": "dead",
        "invocation_id": "",
        "control_group": "",
        "unit_file_state": "disabled",
    }
    property_call = calls[1]
    assert property_call == [
        "/usr/bin/systemctl", "show",
        "--property=ActiveState,SubState,InvocationID,ControlGroup,UnitFileState",
        "vst-supervisor.service",
    ]
    assert "--value" not in property_call


@pytest.mark.parametrize("bad_output", [
    "ActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\n",
    "ActiveState=inactive\nActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\nUnitFileState=disabled\n",
    "ActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\nUnitFileState=disabled\nUnexpected=x\n",
    "ActiveState=inactive\nSubState=dead\nInvocationID=\nControlGroup=\nUnitFileState\n",
], ids=["missing", "duplicate", "unknown", "malformed"])
def test_embedded_unit_admission_rejects_ambiguous_properties_before_target_actions(bad_output):
    with pytest.raises(SystemExit, match="unit activation properties"):
        _run_embedded_unit_admission(bad_output)


@pytest.mark.parametrize("active", ["active", "inactive"])
def test_embedded_unit_admission_preserves_allowed_protected_active_states(active):
    before, _calls = _run_embedded_unit_admission(
        _named_unit_output(active=active, sub="running" if active == "active" else "dead",
                           invocation="1" * 32 if active == "active" else ""))

    assert before["vst-supervisor.service"]["active"] is (active == "active")


@pytest.mark.parametrize("active, file_state, message", [
    ("failed", "disabled", "transitioning or failed"),
    ("activating", "disabled", "transitioning or failed"),
    ("inactive", "masked", "unowned mask"),
    ("inactive", "masked-runtime", "unowned mask"),
])
def test_embedded_unit_admission_keeps_failed_transition_and_mask_guards(
        active, file_state, message):
    with pytest.raises(SystemExit, match=message):
        _run_embedded_unit_admission(
            _named_unit_output(active=active, file_state=file_state))


def test_embedded_unit_admission_rejects_active_unrelated_service():
    with pytest.raises(SystemExit, match="unrelated S2 service is active"):
        _run_embedded_unit_admission(
            _named_unit_output(active="active", invocation="2" * 32), protected_units=())


def test_normal_apply_persistent_guard_check_delegates_to_typed_helper():
    import ast

    tree = ast.parse(APPLY._REMOTE)
    verify = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "verify_persistent_guard")
    calls = []
    namespace = {"helper_ns": {"persistent_guard_loaded": lambda unit: calls.append(unit) or True}}
    exec(compile(ast.Module(body=[verify], type_ignores=[]),
                 "<embedded-apply-guard-check>", "exec"), namespace)

    namespace["verify_persistent_guard"]("vst-runner.service")
    namespace["verify_persistent_guard"]("vst-dispatcher.service")

    assert calls == ["vst-runner.service", "vst-dispatcher.service"]
    calls.clear()
    namespace["helper_ns"]["persistent_guard_loaded"] = lambda unit: calls.append(unit) or False
    with pytest.raises(SystemExit, match="systemd did not load the exact persistent snapshot guard"):
        namespace["verify_persistent_guard"]("vst-runner.service")
    assert calls == ["vst-runner.service"]


@pytest.mark.parametrize("guard_results, expected_failure", [
    ({"vst-runner.service": True, "vst-dispatcher.service": True}, False),
    ({"vst-runner.service": True, "vst-dispatcher.service": False}, True),
], ids=["both-effective", "dispatcher-missing"])
def test_recovery_guard_check_delegates_to_typed_helper_and_requires_both_units(
        guard_results, expected_failure):
    import ast

    tree = ast.parse(APPLY._RECOVERY_REMOTE)
    guard_assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == "guards"
                                    for target in node.targets))
    guard_loop = next(node for node in tree.body if isinstance(node, ast.For)
                      and isinstance(node.target, ast.Name) and node.target.id == "unit"
                      and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Subscript)
                              and isinstance(child.func.value, ast.Name)
                              and child.func.value.id == "helper"
                              and isinstance(child.func.slice, ast.Constant)
                              and child.func.slice.value == "persistent_guard_loaded"
                              for child in ast.walk(node)))
    guard_check = next(node for node in tree.body if isinstance(node, ast.If)
                       and any(isinstance(child, ast.Name) and child.id == "guards"
                               for child in ast.walk(node.test)))
    calls = []

    def loaded(unit):
        calls.append(unit)
        return guard_results[unit]

    namespace = {"units": ("vst-runner.service", "vst-dispatcher.service"),
                 "helper": {"persistent_guard_loaded": loaded}}
    isolated = ast.Module(body=[guard_assignment, guard_loop, guard_check], type_ignores=[])
    if expected_failure:
        with pytest.raises(SystemExit, match="both exact persistent recovery guards"):
            exec(compile(isolated, "<embedded-recovery-guard-check>", "exec"), namespace)
    else:
        exec(compile(isolated, "<embedded-recovery-guard-check>", "exec"), namespace)

    assert calls == ["vst-runner.service", "vst-dispatcher.service"]


def _run_embedded_bootstrap_admission(unit_properties, cold_proof=None):
    """Execute the actual cold-admission statements with all target I/O replaced."""
    import ast
    from types import SimpleNamespace

    tree = ast.parse(APPLY._REMOTE)
    by_name = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    units_assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == "units"
                                    for target in node.targets))
    protected_assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                                and any(isinstance(target, ast.Name) and target.id == "protected_units"
                                        for target in node.targets))
    unit_loop = next(node for node in tree.body if isinstance(node, ast.For)
                     and isinstance(node.target, ast.Name) and node.target.id == "unit")
    bootstrap_nodes = [node for node in tree.body
                       if isinstance(node, ast.Assign) and any(
                           isinstance(target, ast.Name) and target.id == "bootstrap_predecessor"
                           for target in node.targets)]
    bootstrap_check = next(node for node in tree.body if isinstance(node, ast.If)
                           and any(isinstance(target, ast.Name)
                                   and target.id == "bootstrap_predecessor"
                                   for child in ast.walk(node) if isinstance(child, ast.Assign)
                                   for target in child.targets))
    calls = []
    observations = []

    class Completed:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if "--property=LoadState" in argv:
            return Completed("loaded\n")
        if "--property=ActiveState,SubState,InvocationID,ControlGroup,UnitFileState" in argv:
            return Completed(unit_properties[argv[-1]])
        raise AssertionError(f"unexpected target command during admission: {argv!r}")

    def observe(**kwargs):
        observations.append(kwargs)
        return cold_proof or {"live_root": {"kind": "predecessor"}}

    units = ("vst-supervisor.service", "vst-signer.service", "vst-runner.service",
             "vst-dispatcher.service", "vst-dispatch-owner.service",
             "vst-dispatch-owner.socket", "vst-assignment-bootstrap.service",
             "vst-dispatch-issuer.service", "vst-sandbox-probe.service")
    namespace = {
        "subprocess": SimpleNamespace(run=fake_run, DEVNULL=object(), PIPE=object()),
        "units": units,
        "protected_units": ("vst-runner.service", "vst-dispatcher.service"),
        "unit_before": {},
        "bootstrap_predecessor": False,
        "helper_ns": {"observe_bootstrap_predecessor": observe},
        "TASK_HEAD": APPLY.TASK_SOURCE_HEAD,
        "TASK_TREE": _embedded_task_tree(),
    }
    body = [by_name["parse_unit_identity"], by_name["verify_cold_refresh"],
            units_assignment, protected_assignment,
            unit_loop, *bootstrap_nodes, bootstrap_check]
    exec(compile(ast.Module(body=body, type_ignores=[]),
                 "<embedded-cold-bootstrap-admission>", "exec"), namespace)
    return namespace, observations, calls


def test_embedded_admission_observes_only_exact_prestart_cold_pair():
    cold = _named_unit_output()
    properties = {unit: cold for unit in (
        "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
        "vst-dispatcher.service", "vst-dispatch-owner.service",
        "vst-dispatch-owner.socket", "vst-assignment-bootstrap.service",
        "vst-dispatch-issuer.service", "vst-sandbox-probe.service")}

    namespace, observations, calls = _run_embedded_bootstrap_admission(properties)

    assert namespace["bootstrap_predecessor"] is True
    assert observations == [{"allow_missing_ledger": True,
                             "allow_candidate_root": True}]
    assert len(calls) == 18


def _candidate_cold_proof(**overrides):
    task_tree = _embedded_task_tree()
    proof = {
        "live_root": {"kind": "candidate", "device": 3, "inode": 4, "mode": 0o555,
                      "head": APPLY.TASK_SOURCE_HEAD, "tree_sha1": task_tree},
        "ledger_absent": False,
        "ledger_empty": False,
        "ledger_record": {"state": "BOOTSTRAP_EMPTY", "record_sha256": "a" * 64},
        "generation_absent": False,
        "generation_matches_ledger": True,
    }
    proof.update(overrides)
    return proof


def _embedded_task_tree():
    import ast

    tree = ast.parse(APPLY._REMOTE)
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "TASK_TREE"
                              for target in node.targets))
    return ast.literal_eval(assignment.value)


def _run_embedded_cold_refresh_check(proof, transaction=None):
    import ast

    tree = ast.parse(APPLY._REMOTE)
    check = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "verify_cold_refresh")
    namespace = {"TASK_HEAD": APPLY.TASK_SOURCE_HEAD, "TASK_TREE": _embedded_task_tree()}
    exec(compile(ast.Module(body=[check], type_ignores=[]),
                 "<embedded-cold-refresh-proof-check>", "exec"), namespace)
    return namespace["verify_cold_refresh"](proof, transaction)


def test_cold_refresh_proof_accepts_exact_readonly_candidate_with_existing_bootstrap_record():
    assert _run_embedded_cold_refresh_check(_candidate_cold_proof()) is True
    assert _run_embedded_cold_refresh_check(
        {"live_root": {"kind": "predecessor"}}) is False


@pytest.mark.parametrize("mutation", [
    {"root": {"head": "f" * 40}},
    {"root": {"tree_sha1": "f" * 40}},
    {"root": {"mode": 0o755}},
    {"ledger_absent": True},
    {"ledger_empty": True},
    {"ledger_record": None},
    {"generation_absent": True},
    {"generation_matches_ledger": False},
], ids=["wrong-head", "wrong-tree", "writable-root", "absent-ledger",
       "empty-ledger", "missing-bootstrap-record", "missing-generation",
       "generation-mismatch"])
def test_cold_refresh_proof_rejects_missing_or_nonmatching_candidate_receipt(mutation):
    proof = _candidate_cold_proof()
    if "root" in mutation:
        proof["live_root"].update(mutation["root"])
    else:
        proof.update(mutation)
    with pytest.raises(SystemExit, match="exact existing candidate and ledger"):
        _run_embedded_cold_refresh_check(proof)


@pytest.mark.parametrize("field", ["device", "inode", "mode", "head", "tree_sha1"])
def test_cold_refresh_proof_must_match_recorded_transaction_root_identity(field):
    proof = _candidate_cold_proof()
    transaction = {"old_" + name: proof["live_root"][name]
                   for name in ("device", "inode", "mode", "head", "tree_sha1")}
    transaction["old_" + field] = "mismatch" if field in {"head", "tree_sha1"} else -1

    with pytest.raises(SystemExit, match="differs from the transaction predecessor"):
        _run_embedded_cold_refresh_check(proof, transaction)


def test_embedded_candidate_admission_opts_into_candidate_observation_only_for_cold_pair():
    cold = _named_unit_output()
    properties = {unit: cold for unit in (
        "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
        "vst-dispatcher.service", "vst-dispatch-owner.service",
        "vst-dispatch-owner.socket", "vst-assignment-bootstrap.service",
        "vst-dispatch-issuer.service", "vst-sandbox-probe.service")}
    namespace, observations, _calls = _run_embedded_bootstrap_admission(
        properties, _candidate_cold_proof())

    assert namespace["bootstrap_predecessor"] is True
    assert namespace["bootstrap_candidate_refresh"] is True
    assert observations == [{"allow_missing_ledger": True, "allow_candidate_root": True}]


@pytest.mark.parametrize("field", ["device", "inode", "mode", "head", "tree_sha1"])
def test_embedded_candidate_refresh_rechecks_root_binding_before_journaling(field):
    import ast

    proof = _candidate_cold_proof()
    transaction = {"old_" + name: proof["live_root"][name]
                   for name in ("device", "inode", "mode", "head", "tree_sha1")}
    events = []
    rechecked = dict(proof, live_root=dict(proof["live_root"]))
    rechecked["live_root"][field] = "changed" if field in {"head", "tree_sha1"} else -1

    tree = ast.parse(APPLY._REMOTE)
    refresh = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                   and any(isinstance(child, ast.Call)
                           and isinstance(child.func, ast.Subscript)
                           and isinstance(child.func.value, ast.Name)
                           and child.func.value.id == "helper_ns"
                           and isinstance(child.func.slice, ast.Constant)
                           and child.func.slice.value == "ensure_bootstrap_predecessor"
                           for child in ast.walk(node)))
    check = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "verify_cold_refresh")
    helper = {
        "_cold_proof_current": lambda _proof, **kwargs: events.append(
            ("recheck", kwargs)) or rechecked,
        "ensure_bootstrap_predecessor": lambda *_args, **kwargs: events.append(
            ("ensure", kwargs)) or proof,
        "record_dispatcher_bootstrap_quiescent": lambda *_args, **_kwargs: events.append(
            ("dispatcher-receipt", None)),
        "record_runner_bootstrap_empty": lambda *_args, **_kwargs: events.append(
            ("runner-receipt", None)),
    }
    namespace = {"TASK_HEAD": APPLY.TASK_SOURCE_HEAD, "TASK_TREE": _embedded_task_tree(),
                 "bootstrap_predecessor": True, "bootstrap_candidate_refresh": True,
                 "bootstrap_initial_proof": proof, "transaction": transaction,
                 "helper_ns": helper}
    with pytest.raises(SystemExit):
        exec(compile(ast.Module(body=[check, refresh], type_ignores=[]),
                     "<embedded-cold-refresh-transaction>", "exec"), namespace)

    assert events == [("recheck", {"allow_missing": False})]


def test_embedded_candidate_refresh_uses_existing_ledger_without_bootstrap_creation():
    import ast

    proof = _candidate_cold_proof()
    transaction = {"old_" + name: proof["live_root"][name]
                   for name in ("device", "inode", "mode", "head", "tree_sha1")}
    events = []
    tree = ast.parse(APPLY._REMOTE)
    refresh = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                   and any(isinstance(child, ast.Call)
                           and isinstance(child.func, ast.Subscript)
                           and isinstance(child.func.value, ast.Name)
                           and child.func.value.id == "helper_ns"
                           and isinstance(child.func.slice, ast.Constant)
                           and child.func.slice.value == "ensure_bootstrap_predecessor"
                           for child in ast.walk(node)))
    check = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "verify_cold_refresh")
    helper = {
        "_cold_proof_current": lambda _proof, **kwargs: events.append(
            ("recheck", kwargs)) or proof,
        "ensure_bootstrap_predecessor": lambda *_args, **kwargs: events.append(
            ("ensure", kwargs)) or proof,
        "record_dispatcher_bootstrap_quiescent": lambda *_args, **_kwargs: events.append(
            ("dispatcher-receipt", None)),
        "record_runner_bootstrap_empty": lambda *_args, **_kwargs: events.append(
            ("runner-receipt", None)),
    }
    namespace = {"TASK_HEAD": APPLY.TASK_SOURCE_HEAD, "TASK_TREE": _embedded_task_tree(),
                 "bootstrap_predecessor": True, "bootstrap_candidate_refresh": True,
                 "bootstrap_initial_proof": proof, "transaction": transaction,
                 "helper_ns": helper}
    exec(compile(ast.Module(body=[check, refresh], type_ignores=[]),
                 "<embedded-cold-refresh-transaction>", "exec"), namespace)

    assert events == [
        ("recheck", {"allow_missing": False}),
        ("ensure", {"create_baseline": False}),
        ("dispatcher-receipt", None),
        ("runner-receipt", None),
    ]


def test_embedded_candidate_refresh_rejects_changed_root_returned_by_helper_before_receipts():
    import ast

    proof = _candidate_cold_proof()
    transaction = {"old_" + name: proof["live_root"][name]
                   for name in ("device", "inode", "mode", "head", "tree_sha1")}
    post_ensure = dict(proof, live_root=dict(proof["live_root"]))
    post_ensure["live_root"]["inode"] += 1
    events = []
    tree = ast.parse(APPLY._REMOTE)
    refresh = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                   and any(isinstance(child, ast.Call)
                           and isinstance(child.func, ast.Subscript)
                           and isinstance(child.func.value, ast.Name)
                           and child.func.value.id == "helper_ns"
                           and isinstance(child.func.slice, ast.Constant)
                           and child.func.slice.value == "ensure_bootstrap_predecessor"
                           for child in ast.walk(node)))
    check = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "verify_cold_refresh")
    helper = {
        "_cold_proof_current": lambda _proof, **kwargs: events.append(
            ("recheck", kwargs)) or proof,
        "ensure_bootstrap_predecessor": lambda *_args, **kwargs: events.append(
            ("ensure", kwargs)) or post_ensure,
        "record_dispatcher_bootstrap_quiescent": lambda *_args, **_kwargs: events.append(
            ("dispatcher-receipt", None)),
        "record_runner_bootstrap_empty": lambda *_args, **_kwargs: events.append(
            ("runner-receipt", None)),
    }
    namespace = {"TASK_HEAD": APPLY.TASK_SOURCE_HEAD, "TASK_TREE": _embedded_task_tree(),
                 "bootstrap_predecessor": True, "bootstrap_candidate_refresh": True,
                 "bootstrap_initial_proof": proof, "transaction": transaction,
                 "helper_ns": helper}

    with pytest.raises(SystemExit, match="differs from the transaction predecessor"):
        exec(compile(ast.Module(body=[check, refresh], type_ignores=[]),
                     "<embedded-cold-refresh-after-helper>", "exec"), namespace)

    assert events == [
        ("recheck", {"allow_missing": False}),
        ("ensure", {"create_baseline": False}),
    ]


@pytest.mark.parametrize("changed_unit, mutation", [
    ("vst-runner.service", {"InvocationID": "a" * 32}),
    ("vst-dispatcher.service", {"ControlGroup": "/system.slice/vst-dispatcher.service"}),
    ("vst-runner.service", {"ActiveState": "active", "InvocationID": "b" * 32,
                             "ControlGroup": "/system.slice/vst-runner.service"}),
])
def test_embedded_admission_rejects_mixed_or_started_pair_without_cold_observation(
        changed_unit, mutation):
    values = {"ActiveState": "inactive", "SubState": "dead", "InvocationID": "",
              "ControlGroup": "", "UnitFileState": "disabled"}
    values.update(mutation)
    properties = {unit: _named_unit_output() for unit in (
        "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
        "vst-dispatcher.service", "vst-dispatch-owner.service",
        "vst-dispatch-owner.socket", "vst-assignment-bootstrap.service",
        "vst-dispatch-issuer.service", "vst-sandbox-probe.service")}
    properties[changed_unit] = "".join(f"{key}={value}\n" for key, value in values.items())

    with pytest.raises(SystemExit, match="invocation identity is unavailable"):
        _run_embedded_bootstrap_admission(properties)
