"""Mock-only S2-4 runtime harness contract tests.

Maps to the bounded authorization, exact source-pin, one-shot WSL, and terminal
attempt-evidence gates. No test in this module launches WSL or a runtime service.
"""
from __future__ import annotations

import errno
import hashlib
import io
import json
import ast
import os
import pathlib
import re
import stat
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.qa import run_s2_runtime_qualification as harness


RUNTIME_HEAD = "1" * 40
QUALIFICATION_HEAD = "b" * 40
HEX = "a" * 64
WSL_HELPER = "tools/qa/s2_runtime_qualification_wsl.py"
OUTER_HELPER = "tools/qa/run_s2_runtime_qualification.py"
FAILURE_PROTOCOL = json.dumps({
    "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
    "terminal": "HOLD",
    "reason": "synthetic bounded refusal",
}, separators=(",", ":")).encode("ascii")
MOCK_WSL_SOURCE = (
    b'"""Synthetic WSL helper."""\n'
    b"from __future__ import annotations\n"
    b"import json\n"
    b"AUTH = json.loads(AUTH)\n"
    b"# mocked protocol body\n"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


RUNTIME_ARCHIVE_PATHS = (
    "tools/vst", "tools/qa/install_wsl_runner_runtime.sh",
    "tools/qa/install_wsl_worker_helper.sh", "tools/qa/verify_wsl_source_bundle.py",
    "tools/qa/verify_wsl_runtime_stage.py", "tools/qa/worker_exec.c",
    "docs/SANDBOX_SPEC.md",
)
RUNTIME_ARCHIVE_EXTRA_FILES = tuple(
    f"tools/vst/archive-extra-{index:02d}.py" for index in range(27))
RUNTIME_ARCHIVE_STANDALONE_FILES = (
    "tools/qa/install_wsl_runner_runtime.sh", "tools/qa/install_wsl_worker_helper.sh",
    "tools/qa/verify_wsl_source_bundle.py", "tools/qa/verify_wsl_runtime_stage.py",
    "tools/qa/worker_exec.c", "docs/SANDBOX_SPEC.md",
)


def _runtime_archive_fixture_files():
    paths = set(harness.REQUIRED_RUNTIME_PINS) | set(RUNTIME_ARCHIVE_EXTRA_FILES)
    paths.update(RUNTIME_ARCHIVE_STANDALONE_FILES)
    assert len(paths) == 47
    return {path: (f"# archive fixture: {path}\n".encode("ascii")
                   + b"second line\n") for path in paths}


@pytest.fixture
def hostile_git_archive_fixture(tmp_path, monkeypatch):
    repo = tmp_path / "git-source"
    repo.mkdir()
    home = tmp_path / "git-home"
    home.mkdir()
    global_config = home / "global.gitconfig"
    global_config.write_bytes(b"[core]\r\n\tautocrlf = true\r\n\teol = crlf\r\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)

    git("init", "--quiet")
    git("config", "--local", "core.autocrlf", "true")
    git("config", "--local", "core.eol", "crlf")
    attribute_file = repo / ".gitattributes"
    attribute_file.write_bytes(b"*.py text=auto\n*.sh text=auto\n*.md text=auto\n*.c text=auto\n")
    runtime_files = _runtime_archive_fixture_files()
    for relative, raw in runtime_files.items():
        path = repo / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    qualification_files = {
        OUTER_HELPER: b"# qualification outer source\n",
        WSL_HELPER: b"# qualification WSL source\n",
    }
    for relative, raw in qualification_files.items():
        path = repo / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    git("add", "--all")
    git("-c", "user.name=S2 fixture", "-c", "user.email=s2-fixture@example.invalid",
        "commit", "--quiet", "-m", "isolated source fixture")
    head = git("rev-parse", "HEAD").stdout.decode("ascii").strip()
    local_config = repo / ".git" / "config"
    return {
        "repo": repo,
        "head": head,
        "runtime_files": runtime_files,
        "qualification_files": qualification_files,
        "global_config": global_config,
        "local_config": local_config,
        "attributes": attribute_file,
        "archive_paths": RUNTIME_ARCHIVE_PATHS,
    }


def _runtime_pins_from_archive(archive_bytes):
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as bundle:
        return {
            member.name: _sha(bundle.extractfile(member).read())
            for member in bundle.getmembers() if member.isfile()
        }


def _validated_archive_input(fixture, archive_bytes, runtime_pins):
    value = _auth_input(streamed_wsl=fixture["qualification_files"][WSL_HELPER])
    value["identity"]["runtime_source_head"] = fixture["head"]
    value["identity"]["qualification_source_head"] = fixture["head"]
    value["identity"]["runtime_selector"] = "/opt/vst-runtime-" + fixture["head"]
    value["identity"]["bundle_sha256"] = _sha(archive_bytes)
    value["source_pins"]["runtime"] = dict(runtime_pins)
    value["source_pins"]["qualification"] = {
        path: _sha(raw) for path, raw in fixture["qualification_files"].items()
    }
    return value, harness.validate_input(value)


def _auth_input(*, streamed_wsl: bytes = b"# mocked WSL helper\n") -> dict:
    config_hashes = {path: HEX for path in harness.REQUIRED_CONFIG_PINS}
    config_bundle_hash = _sha(json.dumps(
        config_hashes, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii"))
    source_hashes = {path: HEX for path in harness.REQUIRED_RUNTIME_PINS}
    return {
        "schema": "VST_S2_RUNTIME_AUTH_INPUT_V1",
        "authorization": {
            "source": "PM_BRIDGE",
            "correlated": True,
            "verdict": "AUTHORIZE_ONE_SHOT",
            "request_id": "2" * 32,
            "job_id": "job-0123456789abcdef",
            "user_turn_id": "turn-0123456789abcdef",
            "reply_id": "reply-0123456789abcdef",
            "payload_sha256": "3" * 64,
            "retry_cap": 0,
            "allowed_operation": "S2-4_OWNER_RUNNER_TESTRUN",
        },
        "identity": {
            "runtime_source_head": RUNTIME_HEAD,
            "qualification_source_head": QUALIFICATION_HEAD,
            "run_id": "run-0123456789abcdef",
            "bootstrap_request_id": "4" * 32,
            "nonce": "5" * 32,
            "runtime_selector": "/opt/vst-runtime-" + RUNTIME_HEAD,
            "bundle_sha256": HEX,
            "config_bundle_sha256": config_bundle_hash,
            "task_manifest_sha256": "6" * 64,
            "selector_test_id": (
                "tests/vst/test_s2_runtime_qualification_harness.py::"
                "test_runtime_handoff_contract"
            ),
            "config_sha256": config_hashes,
        },
        "source_pins": {
            "runtime": source_hashes,
            "qualification": {
                OUTER_HELPER: HEX,
                WSL_HELPER: _sha(streamed_wsl),
            },
        },
    }


def _operator_auth_input(*, streamed_wsl: bytes = b"# mocked WSL helper\n") -> dict:
    value = _auth_input(streamed_wsl=streamed_wsl)
    statement = "Operator authorizes one S2-4D REQ-003 run through the exact existing selector, retry_cap=0."
    value["authorization"] = {
        "source": "OPERATOR",
        "operator_principal": "operator",
        "operator_authorization_id": "operator-s2-4d-req003-20261106-01",
        "operator_statement": statement,
        "operator_statement_sha256": _sha(statement.encode("utf-8")),
        "verdict": "AUTHORIZE_ONE_SHOT",
        "retry_cap": 0,
        "allowed_operation": "S2-4_OWNER_RUNNER_TESTRUN",
    }
    value["identity"]["selector_test_id"] = harness.OPERATOR_REQ003_SELECTOR
    return value


def _write_input(root: Path, value: dict | bytes) -> tuple[Path, Path]:
    input_path = root / "authorization.json"
    output_path = root / "docs" / "sdlc" / "evidence" / "attempt.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, bytes):
        input_path.write_bytes(value)
    else:
        input_path.write_text(json.dumps(value), encoding="utf-8")
    return input_path, output_path


def test_read_json_preserves_raw_crlf_bytes(tmp_path):
    path = tmp_path / "attempt.json"
    raw = b'{\r\n  "value": "line1\\r\\nline2"\r\n}\r\n'
    path.write_bytes(raw)

    value, actual = harness._read_json(path, maximum=1024)

    assert actual == raw
    assert value == {"value": "line1\r\nline2"}


def test_read_bounded_regular_preserves_raw_crlf_bytes(tmp_path):
    path = tmp_path / "pinned-source.txt"
    raw = b"first line\r\nsecond line\r\n"
    path.write_bytes(raw)

    assert harness._read_bounded_regular(path, maximum=1024) == raw


def _wsl_prestart_functions():
    """Load only the exact WSL mount-preflight functions, without running its protocol."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    wanted = {"Hold", "stop", "_unescape_mountinfo", "_decode_mountinfo",
              "_prestart_inventory"}
    constants = {"SYSTEMD_MASK_DIRS", "SYSTEMD_MASK_FILES", "SYSTEMD_MASK_TARGETS",
                 "MASK_BASES", "EXACT_MOUNTS"}
    nodes = [node for node in tree.body if (
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in constants
                for target in node.targets)
    ) or (((isinstance(node, ast.ClassDef) or isinstance(node, ast.FunctionDef))
           and node.name in wanted))]
    assert {node.name for node in nodes
            if isinstance(node, (ast.ClassDef, ast.FunctionDef))} == wanted
    assert {target.id for node in nodes if isinstance(node, ast.Assign)
            for target in node.targets if isinstance(target, ast.Name)} == constants
    module = ast.Module(body=nodes, type_ignores=[])
    namespace = {
        "hashlib": hashlib,
        "os": SimpleNamespace(geteuid=lambda: 0),
        "pathlib": pathlib,
        "re": re,
        "TRANSIENT_UNIT": "vst-s2-qual-0123456789abcdef.service",
        "R": {"prestart": {}},
        # These external boundaries are stubbed so the fixture only exercises
        # mountinfo allowlisting and never inspects or starts a runtime.
        "_verify_execution_unit": lambda: {"unit": "synthetic"},
        "_verify_effective_masks": lambda _rows: ({}, []),
        "_verify_private_dev": lambda _rows: ({}, []),
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace


def _wsl_identity_functions(*, config_json=None, config_bytes=None, runtime_json=None,
                            runtime_bytes=None, runtime_pins=None, unit_outputs=None,
                            tree_digest=None):
    """Load only identity and named-systemd functions with isolated file/command boundaries."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    wanted = {"_config_identity", "_runtime_identity", "_tree_digest", "_systemd_show"}
    constant = next(node for node in tree.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "EXPECTED_UNITS"
                            for target in node.targets))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in wanted]
    assert {node.name for node in functions} == wanted
    calls = []
    config_json = {} if config_json is None else config_json
    config_bytes = {} if config_bytes is None else config_bytes
    runtime_json = {} if runtime_json is None else runtime_json
    runtime_bytes = {} if runtime_bytes is None else runtime_bytes
    unit_outputs = {} if unit_outputs is None else unit_outputs

    class Hold(Exception):
        pass

    def record(label, argv):
        calls.append((label, argv))
        return {"stdout": unit_outputs[argv[2]]}

    def stop(reason):
        raise Hold(reason)

    def secure_bytes(path, _maximum=2 * 1024 * 1024):
        if path in config_bytes:
            return config_bytes[path]
        return runtime_bytes[path]

    def json_file(path, _maximum=2 * 1024 * 1024):
        if path in config_json:
            return config_json[path]
        return runtime_json[path]

    def fake_lstat(path):
        if path == "/opt/vst-runtime":
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0)
        return SimpleNamespace(st_mode=stat.S_IFDIR | 0o555, st_uid=0)

    namespace = {
        "hashlib": hashlib,
        "json": json,
        "re": re,
        "os": SimpleNamespace(lstat=fake_lstat, readlink=lambda _path: "/opt/vst-runtime-" + RUNTIME_HEAD,
                              path=os.path),
        "stat": stat,
        "EXPECTED_UNITS": (),
        "AUTH": {"source_pins": {"runtime": runtime_pins or {}}},
        "record": record,
        "_require_command": lambda result, _name: result["stdout"],
        "_secure_bytes": secure_bytes,
        "_json_file": json_file,
        "_canonical": lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False).encode("ascii"),
        "stop": stop,
    }
    module = ast.Module(body=[constant, *functions], type_ignores=[])
    exec(compile(module, str(source_path), "exec"), namespace)
    if tree_digest is not None:
        namespace["_tree_digest"] = tree_digest
    namespace["systemd_calls"] = calls
    namespace["Hold"] = Hold
    return namespace


def _canonical_fixture_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _runtime_marker_fixture():
    return {
        "schema": 3,
        "head": RUNTIME_HEAD,
        "archive_sha256": HEX,
        "plan_sha256": "2" * 64,
        "inventory_sha256": "3" * 64,
        "compiler_path": "/usr/bin/cc",
        "compiler_resolved_path": "/usr/bin/gcc-13",
        "compiler_sha256": "4" * 64,
        "compiler_symlink_target": "/etc/alternatives/cc",
    }


RUNTIME_ARCHIVE_ONLY = frozenset({
    "tools/qa/install_wsl_runner_runtime.sh",
    "tools/qa/install_wsl_worker_helper.sh",
    "tools/qa/verify_wsl_source_bundle.py",
    "tools/qa/verify_wsl_runtime_stage.py",
    "tools/qa/worker_exec.c",
})
POSIX_ROOT = os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0


def _wsl_runtime_tree_functions(runtime_root, selector_link, expected_pins):
    """Load the real secure-read/runtime-tree functions with OS paths translated into tmp_path."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    wanted = {"_secure_bytes", "_json_file", "_tree_digest", "_runtime_identity"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in wanted]
    assert {node.name for node in functions} == wanted
    selector = "/opt/vst-runtime-" + RUNTIME_HEAD
    real_os = os

    def translate(path):
        value = str(path)
        if value == selector:
            return str(runtime_root)
        if value.startswith(selector + "/"):
            return str(runtime_root / Path(*value[len(selector) + 1:].split("/")))
        if value == "/opt/vst-runtime":
            return str(selector_link)
        return value

    path_ops = SimpleNamespace(
        join=lambda root, *parts: real_os.path.join(translate(root), *parts),
        relpath=lambda path, start: real_os.path.relpath(translate(path), translate(start)),
        sep=real_os.path.sep,
    )
    os_ops = SimpleNamespace(
        lstat=lambda path: real_os.lstat(translate(path)),
        readlink=lambda path: real_os.readlink(translate(path)),
        walk=lambda root, *args, **kwargs: real_os.walk(translate(root), *args, **kwargs),
        open=lambda path, flags: real_os.open(translate(path), flags),
        fstat=real_os.fstat, read=real_os.read, close=real_os.close,
        O_RDONLY=real_os.O_RDONLY,
        O_NOFOLLOW=getattr(real_os, "O_NOFOLLOW", 0), path=path_ops, sep=real_os.sep,
    )

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    namespace = {
        "hashlib": hashlib, "json": json, "os": os_ops, "stat": stat, "re": re,
        "_pairs": unique_pairs, "_canonical": _canonical_fixture_json,
        "AUTH": {"source_pins": {"runtime": expected_pins}},
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source_path), "exec"),
         namespace)
    return namespace


def _runtime_tree_fixture(tmp_path):
    runtime_root = tmp_path / "installed-runtime"
    runtime_root.mkdir(mode=0o755)
    os.chmod(runtime_root, 0o755)
    selector_link = tmp_path / "active-runtime"
    os.symlink("/opt/vst-runtime-" + RUNTIME_HEAD, selector_link)
    runtime_files = _runtime_archive_fixture_files()
    empty_source = "tools/vst/archive-extra-00.py"
    runtime_files[empty_source] = b""
    pins = {path: _sha(raw) for path, raw in runtime_files.items()}
    deployed = {path: raw for path, raw in runtime_files.items()
                if path not in RUNTIME_ARCHIVE_ONLY}
    assert len(pins) == 47 and len(deployed) == 42
    for relative, raw in deployed.items():
        path = runtime_root / Path(*relative.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        path.write_bytes(raw)
        os.chmod(path, 0o644)
    for path in runtime_root.rglob("*"):
        if path.is_dir():
            os.chmod(path, 0o755)

    marker = _runtime_marker_fixture()
    marker_path = runtime_root / ".vst-runtime-manifest.json"
    marker_path.write_bytes(_canonical_fixture_json(marker))
    os.chmod(marker_path, 0o644)
    functions = _wsl_runtime_tree_functions(runtime_root, selector_link, pins)
    identity = {
        "runtime_selector": "/opt/vst-runtime-" + RUNTIME_HEAD,
        "runtime_source_head": RUNTIME_HEAD,
        "qualification_source_head": QUALIFICATION_HEAD,
        "bundle_sha256": HEX,
    }
    return {
        "root": runtime_root, "selector_link": selector_link, "marker_path": marker_path,
        "marker": marker, "identity": identity, "pins": pins, "deployed": deployed,
        "functions": functions,
    }


@pytest.mark.skipif(not POSIX_ROOT, reason="installed runtime metadata checks require POSIX root")
def test_wsl_runtime_tree_accepts_exact_installed_projection_and_empty_source(tmp_path):
    fixture = _runtime_tree_fixture(tmp_path)

    assert fixture["functions"]["_runtime_identity"](fixture["identity"]) == fixture["marker"]
    assert not (fixture["root"] / "tools" / "qa").exists()
    assert not (fixture["root"] / ".vst-source-manifest.json").exists()
    assert len(fixture["pins"]) == 47
    assert len(fixture["deployed"]) == 42

    config = tmp_path / "empty-config.json"
    config.write_bytes(b"")
    os.chmod(config, 0o644)
    with pytest.raises(ValueError):
        fixture["functions"]["_secure_bytes"](str(config))


@pytest.mark.skipif(not POSIX_ROOT, reason="installed runtime metadata checks require POSIX root")
@pytest.mark.parametrize("mutation", [
    "missing", "extra", "changed", "symlink", "hardlink", "wrong-mode", "wrong-owner",
], ids=["missing-source", "extra-file", "changed-source", "symlink-source",
       "hardlink-source", "wrong-file-mode", "wrong-owner"])
def test_wsl_runtime_tree_refuses_modified_or_unsafe_projection(tmp_path, mutation):
    fixture = _runtime_tree_fixture(tmp_path)
    rel = "tools/vst/archive-extra-00.py"
    source = fixture["root"] / rel
    if mutation == "missing":
        source.unlink()
    elif mutation == "extra":
        extra = fixture["root"] / "unexpected.txt"
        extra.write_bytes(b"extra")
        os.chmod(extra, 0o644)
    elif mutation == "changed":
        source.write_bytes(b"changed")
        os.chmod(source, 0o644)
    elif mutation == "symlink":
        source.unlink()
        source.symlink_to("/etc/passwd")
    elif mutation == "hardlink":
        source.write_bytes(b"hardlink source")
        os.chmod(source, 0o644)
        os.link(source, tmp_path / "outside-link")
    elif mutation == "wrong-mode":
        os.chmod(source, 0o600)
    else:
        os.chown(source, 1, 1)

    with pytest.raises((OSError, ValueError)):
        fixture["functions"]["_runtime_identity"](fixture["identity"])


@pytest.mark.skipif(not POSIX_ROOT, reason="installed runtime metadata checks require POSIX root")
@pytest.mark.parametrize("mutation", ["missing-key", "extra-key", "invalid-digest", "noncanonical"],
                         ids=["missing-marker-field", "extra-marker-field", "bad-marker-digest",
                              "noncanonical-marker"])
def test_wsl_runtime_tree_refuses_malformed_runtime_marker(tmp_path, mutation):
    fixture = _runtime_tree_fixture(tmp_path)
    marker = dict(fixture["marker"])
    if mutation == "missing-key":
        del marker["inventory_sha256"]
    elif mutation == "extra-key":
        marker["unexpected"] = True
    elif mutation == "invalid-digest":
        marker["compiler_sha256"] = "not-a-digest"
    if mutation == "noncanonical":
        fixture["marker_path"].write_text(json.dumps(marker, indent=2), encoding="ascii")
    else:
        fixture["marker_path"].write_bytes(_canonical_fixture_json(marker))
    os.chmod(fixture["marker_path"], 0o644)

    with pytest.raises((OSError, ValueError)):
        fixture["functions"]["_runtime_identity"](fixture["identity"])


def _config_identity_fixture(*, task_base_head="9" * 40, policy_source_head=None,
                              policy_manifest_sha256=None, identity_manifest_sha256=None):
    selector = "tests/vst/test_s2_runtime_qualification_harness.py::test_runtime_handoff_contract"
    acceptance = "one authorized runtime test"
    task_manifest = {
        "base_head": task_base_head,
        "task_id": "S2-4-runtime-owner-runner-qualification",
        "story_id": "S2-4",
        "retry_cap": 0,
        "acceptance": acceptance,
        "required_tests": [{"slot": "runtime-tests", "test_id": selector,
                            "acceptance": acceptance}],
    }
    canonical = lambda value: json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode("ascii")
    task_digest = _sha(canonical(task_manifest))
    config_json = {
        "/etc/vst-runner/supervisor-service.json": {
            "run_id": "run-0123456789abcdef", "probe_nonce": "5" * 32,
            "store_path": "/var/lib/vst-runner/private/store.sqlite3",
        },
        "/etc/vst-runner/bootstrap-request.json": {
            "request_id": "4" * 32, "run_id": "run-0123456789abcdef",
            "task_manifest": task_manifest, "task_id": task_manifest["task_id"],
            "story_id": task_manifest["story_id"],
        },
        "/etc/vst-runner/task-manifest.json": task_manifest,
        "/etc/vst-runner/network-profile.json": {
            "external_allowlist": [], "environment_id": "Ubuntu-24.04:S2:run-0123456789abcdef",
        },
        "/etc/vst-runner/assignment-delegation-policy.json": {
            "source_head": task_base_head if policy_source_head is None else policy_source_head,
            "allowed_assignments": [{"task_manifest_sha256": (
                task_digest if policy_manifest_sha256 is None else policy_manifest_sha256)}],
        },
    }
    config_bytes = {path: canonical(value) for path, value in config_json.items()}
    config_sha256 = {path: _sha(raw) for path, raw in config_bytes.items()}
    return {
        "identity": {
            "runtime_source_head": RUNTIME_HEAD,
            "qualification_source_head": QUALIFICATION_HEAD,
            "run_id": "run-0123456789abcdef", "nonce": "5" * 32,
            "bootstrap_request_id": "4" * 32, "selector_test_id": selector,
            "task_manifest_sha256": (task_digest if identity_manifest_sha256 is None
                                      else identity_manifest_sha256),
            "config_sha256": config_sha256,
            "config_bundle_sha256": _sha(canonical(config_sha256)),
        },
        "config_json": config_json,
        "config_bytes": config_bytes,
        "task_head": task_base_head,
    }


def _named_systemd_output(properties, order):
    return "".join(f"{name}={properties[name]}\n" for name in order).encode("ascii")


def _wsl_prestart_unit_gate(functions):
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    prestart = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_prestart_inventory")
    rows_assignment = next(node for node in prestart.body if isinstance(node, ast.Assign)
                           and any(isinstance(target, ast.Name) and target.id == "unit_rows"
                                   for target in node.targets))
    unit_loop = next(node for node in ast.walk(prestart) if isinstance(node, ast.For)
                     and isinstance(node.target, ast.Name) and node.target.id == "unit"
                     and any(isinstance(child, ast.Constant) and child.value == "ControlPID"
                             for child in ast.walk(node)))
    isolated = ast.Module(body=[rows_assignment, unit_loop], type_ignores=[])
    exec(compile(isolated, str(source_path), "exec"), functions)
    return functions["unit_rows"]


def test_wsl_config_identity_binds_policy_to_task_manifest_head_not_runtime_or_qualifier():
    fixture = _config_identity_fixture()
    functions = _wsl_identity_functions(
        config_json=fixture["config_json"], config_bytes=fixture["config_bytes"])

    _config, _bootstrap, task_manifest = functions["_config_identity"](fixture["identity"])

    assert fixture["identity"]["runtime_source_head"] == RUNTIME_HEAD
    assert fixture["identity"]["qualification_source_head"] == QUALIFICATION_HEAD
    assert task_manifest["base_head"] == fixture["task_head"] == "9" * 40
    assert task_manifest["base_head"] not in {
        fixture["identity"]["runtime_source_head"],
        fixture["identity"]["qualification_source_head"],
    }


@pytest.mark.parametrize("wrong_policy_head", [RUNTIME_HEAD, QUALIFICATION_HEAD],
                         ids=["runtime-head", "qualification-head"])
def test_wsl_config_identity_rejects_policy_head_that_is_not_task_manifest_base(
        wrong_policy_head):
    fixture = _config_identity_fixture(policy_source_head=wrong_policy_head)
    functions = _wsl_identity_functions(
        config_json=fixture["config_json"], config_bytes=fixture["config_bytes"])

    with pytest.raises(ValueError):
        functions["_config_identity"](fixture["identity"])


@pytest.mark.parametrize("bad_base_head", [None, "9" * 39, "g" * 40, 900],
                         ids=["missing", "short", "non-hex", "wrong-type"])
def test_wsl_config_identity_rejects_malformed_authorized_task_manifest_base_head(
        bad_base_head):
    fixture = _config_identity_fixture(task_base_head=bad_base_head)
    functions = _wsl_identity_functions(
        config_json=fixture["config_json"], config_bytes=fixture["config_bytes"])

    with pytest.raises(ValueError):
        functions["_config_identity"](fixture["identity"])


@pytest.mark.parametrize("mismatch", ["authorized-task-hash", "policy-task-hash"],
                         ids=["manifest-digest", "policy-assignment-digest"])
def test_wsl_config_identity_rejects_task_manifest_hash_mismatch(mismatch):
    fixture_options = {}
    if mismatch == "authorized-task-hash":
        fixture_options["identity_manifest_sha256"] = "f" * 64
    else:
        fixture_options["policy_manifest_sha256"] = "f" * 64
    fixture = _config_identity_fixture(**fixture_options)
    functions = _wsl_identity_functions(
        config_json=fixture["config_json"], config_bytes=fixture["config_bytes"])

    with pytest.raises(ValueError):
        functions["_config_identity"](fixture["identity"])


def test_wsl_runtime_identity_keeps_runtime_marker_and_source_pins_separate():
    selector = "/opt/vst-runtime-" + RUNTIME_HEAD
    marker_path = selector + "/.vst-runtime-manifest.json"
    marker = _runtime_marker_fixture()
    pins = {"tools/vst/runtime-check.py": _sha(b"pinned runtime source\n"),
            "docs/SANDBOX_SPEC.md": _sha(b"pinned docs\n")}
    observed = []
    functions = _wsl_identity_functions(
        runtime_json={marker_path: marker},
        runtime_bytes={marker_path: _canonical_fixture_json(marker)}, runtime_pins=pins,
        tree_digest=lambda root, expected: observed.append((root, expected)))
    identity = {"runtime_selector": selector, "runtime_source_head": RUNTIME_HEAD,
                "qualification_source_head": QUALIFICATION_HEAD, "bundle_sha256": HEX}

    assert functions["_runtime_identity"](identity) == marker
    assert observed == [(selector, pins)]


@pytest.mark.parametrize("mismatch", ["selector", "marker-head", "marker-archive", "source-pin"],
                         ids=["selector", "marker-head", "archive-pin", "runtime-source-pin"])
def test_wsl_runtime_identity_still_refuses_runtime_marker_or_pin_mismatch(mismatch):
    selector = "/opt/vst-runtime-" + RUNTIME_HEAD
    marker_path = selector + "/.vst-runtime-manifest.json"
    marker = _runtime_marker_fixture()
    identity = {"runtime_selector": selector, "runtime_source_head": RUNTIME_HEAD,
                "qualification_source_head": QUALIFICATION_HEAD, "bundle_sha256": HEX}
    pins = {"tools/vst/runtime-check.py": _sha(b"runtime source bytes\n"),
            "docs/SANDBOX_SPEC.md": _sha(b"docs bytes\n")}
    if mismatch == "selector":
        identity["runtime_selector"] = "/opt/vst-runtime-" + QUALIFICATION_HEAD
    elif mismatch == "marker-head":
        marker["head"] = QUALIFICATION_HEAD
    elif mismatch == "marker-archive":
        marker["archive_sha256"] = "f" * 64
    else:
        pins["tools/vst/runtime-check.py"] = "f" * 64
    functions = _wsl_identity_functions(
        runtime_json={marker_path: marker},
        runtime_bytes={marker_path: _canonical_fixture_json(marker)}, runtime_pins=pins,
        tree_digest=lambda _root, expected: (_ for _ in ()).throw(ValueError("pin mismatch"))
        if mismatch == "source-pin" else (lambda _root, _expected: None))

    with pytest.raises(ValueError):
        functions["_runtime_identity"](identity)


def _service_unit_properties():
    return {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
            "Result": "success", "MainPID": "0", "ControlPID": "0"}


def _socket_unit_properties():
    return {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead",
            "Result": "success", "ControlPID": "0"}


def test_wsl_systemd_show_parses_reordered_named_service_and_socket_properties():
    service = "vst-runner.service"
    socket = "vst-dispatch-owner.socket"
    outputs = {
        service: _named_systemd_output(_service_unit_properties(),
                                      ["Result", "MainPID", "ActiveState", "ControlPID",
                                       "SubState", "LoadState"]),
        socket: _named_systemd_output(_socket_unit_properties(),
                                     ["ControlPID", "SubState", "LoadState", "Result",
                                      "ActiveState"]),
    }
    functions = _wsl_identity_functions(unit_outputs=outputs)

    service_result = functions["_systemd_show"](service)
    socket_result = functions["_systemd_show"](socket)

    assert service_result == _service_unit_properties()
    assert socket_result == _socket_unit_properties()
    assert "MainPID" not in socket_result
    assert [label for label, _argv in functions["systemd_calls"]] == [
        "unit:" + service, "unit:" + socket,
    ]


@pytest.mark.parametrize("raw", [
    b"ActiveState=inactive\nSubState=dead\nResult=success\nControlPID=0\nLoadState=loaded\n",
    b"LoadState=loaded\nActiveState=inactive\nSubState=dead\nResult=success\nMainPID=0\n",
    b"LoadState=loaded\nActiveState=inactive\nSubState=dead\nResult=success\nMainPID=0\nControlPID=0\nUnexpected=yes\n",
    b"LoadState=loaded\nActiveState=inactive\nActiveState=inactive\nSubState=dead\nResult=success\nMainPID=0\nControlPID=0\n",
    b"LoadState\nActiveState=inactive\nSubState=dead\nResult=success\nMainPID=0\nControlPID=0\n",
    b"LoadState=loaded\nActiveState=inactive\nSubState=dead\nResult=success\nMainPID=not-a-pid\nControlPID=0\n",
    b"LoadState=loaded\nActiveState=inactive\nSubState=dead\nResult=success\nMainPID=0\nControlPID=-1\n",
], ids=["missing-controlpid", "missing-mainpid", "unknown", "duplicate", "malformed",
       "nonnumeric-mainpid", "nonnumeric-controlpid"])
def test_wsl_systemd_show_rejects_missing_ambiguous_or_malformed_named_properties(raw):
    functions = _wsl_identity_functions(unit_outputs={"vst-runner.service": raw})

    with pytest.raises(functions["Hold"]):
        functions["_systemd_show"]("vst-runner.service")


def test_wsl_systemd_show_rejects_units_outside_exact_qualification_allowlist():
    functions = _wsl_identity_functions()

    with pytest.raises(functions["Hold"]):
        functions["_systemd_show"]("unrelated.service")

    assert functions["systemd_calls"] == []


def _inactive_systemd_outputs(units):
    outputs = {}
    for unit in units:
        properties = (_socket_unit_properties() if unit.endswith(".socket")
                      else _service_unit_properties())
        outputs[unit] = _named_systemd_output(properties, list(reversed(properties)))
    return outputs


def test_wsl_prestart_unit_gate_accepts_named_inactive_services_and_socket_without_mainpid():
    outputs = _inactive_systemd_outputs((
        "vst-sandbox-probe.service", "vst-assignment-bootstrap.service",
        "vst-dispatch-issuer.service", "vst-supervisor.service", "vst-signer.service",
        "vst-runner.service", "vst-dispatcher.service", "vst-dispatch-owner.socket",
        "vst-dispatch-owner.service",
    ))
    functions = _wsl_identity_functions(unit_outputs=outputs)

    rows = _wsl_prestart_unit_gate(functions)

    assert rows["vst-runner.service"]["MainPID"] == "0"
    assert rows["vst-runner.service"]["ControlPID"] == "0"
    assert rows["vst-dispatch-owner.socket"]["ControlPID"] == "0"
    assert "MainPID" not in rows["vst-dispatch-owner.socket"]
    assert len(rows) == len(functions["EXPECTED_UNITS"])


@pytest.mark.parametrize(("unit", "field", "value"), [
    ("vst-runner.service", "MainPID", "4321"),
    ("vst-dispatch-owner.socket", "ControlPID", "7"),
], ids=["active-service-pid", "active-socket-control-pid"])
def test_wsl_prestart_unit_gate_refuses_nonzero_service_or_socket_pid(
        unit, field, value):
    fixture = _wsl_identity_functions(unit_outputs={})
    outputs = _inactive_systemd_outputs(fixture["EXPECTED_UNITS"])
    base = _socket_unit_properties() if unit.endswith(".socket") else _service_unit_properties()
    base[field] = value
    outputs[unit] = _named_systemd_output(base, list(reversed(base)))
    functions = _wsl_identity_functions(unit_outputs=outputs)

    with pytest.raises(functions["Hold"]):
        _wsl_prestart_unit_gate(functions)


class _WslTestRunHold(Exception):
    pass


def _wsl_test_run_function():
    """Load only the WSL TestRun observer with isolated dependency stubs."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "_wait_for_test_run")
    imports = {
        (node.module, tuple(alias.name for alias in node.names))
        for node in function.body if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        ("tools.vst.contracts", ("canonical_bytes", "receipt_sha256", "validate_receipt")),
        ("tools.vst.execution_grant", ("validate_execution_grant",)),
        ("tools.vst.supervisor_service", ("SupervisorClient",)),
    }
    function.body = [node for node in function.body if not isinstance(node, ast.ImportFrom)]

    namespace = {
        "hashlib": hashlib,
        "json": json,
        "HEX40": re.compile(r"^[0-9a-f]{40}$"),
        "sys": __import__("sys"),
        "time": __import__("time"),
        "_pairs": dict,
        "canonical_bytes": lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii"),
        "receipt_sha256": lambda value: _sha(json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")),
        "validate_receipt": lambda value: value,
        "validate_execution_grant": lambda value: value,
        "stop": lambda reason: (_ for _ in ()).throw(_WslTestRunHold(reason)),
        "utc": lambda: "2026-11-04T00:00:00Z",
        "R": {"stages": {"bootstrap": {"handoff": {
            "runner_id": "runner-1", "epoch": 3,
        }}}, "commands": []},
        "_read_task_rows": lambda _store_path, _task_id: ([], [], []),
        "_systemd_show": lambda _unit: {
            "LoadState": "loaded", "ActiveState": "active", "ControlPID": "0",
        },
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]),
                 str(source_path), "exec"), namespace)
    return namespace["_wait_for_test_run"], namespace, _WslTestRunHold


def _wsl_mount_audit_functions(*, unit="vst-s2-qual-0123456789abcdef.service"):
    """Load only the exact WSL mount decoder and its independent audit helpers."""
    source_path = Path(__file__).resolve().parents[2] / WSL_HELPER
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    constants = {
        "SYSTEMD_MASK_DIRS", "SYSTEMD_MASK_FILES", "SYSTEMD_MASK_TARGETS",
        "SYSTEMD_INACCESSIBLE_PATHS", "MASK_BASES", "EXACT_MOUNTS",
    }
    functions = {
        "_unescape_mountinfo", "_decode_mountinfo", "_verify_execution_unit",
        "_verify_private_dev", "_verify_effective_masks", "_read_only_mount_audit",
    }
    nodes = [node for node in tree.body if (
        isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in constants
                for target in node.targets)
    ) or (isinstance(node, ast.FunctionDef) and node.name in functions)]
    found_constants = {
        target.id for node in nodes if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }
    found_functions = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    assert found_constants == constants
    assert found_functions == functions

    class Hold(Exception):
        pass

    runtime = {"terminal": None, "reason": None}

    def stop(reason):
        runtime["terminal"] = "HOLD"
        runtime["reason"] = reason
        raise Hold()

    namespace = {
        "errno": errno, "hashlib": hashlib, "re": re, "os": __import__("os"),
        "stat": __import__("stat"), "pathlib": pathlib,
        "TRANSIENT_UNIT": unit, "MOUNT_AUDIT_ONLY": True,
        "R": runtime, "Hold": Hold, "stop": stop,
        "_systemd_unit_properties": lambda: {},
        "_expected_runtime_timeout": lambda: "1min",
        "BASELINE_DECODER_SOURCE": "",
        "BASELINE_DECODER_SHA256": "",
        "BASELINE_DECODER_REVISION": "0" * 40,
        "utc": lambda: "2026-11-01T00:00:00Z",
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), "exec"),
         namespace)
    return namespace


def _verify_effective_masks_fixture(*, missing=(), unmasked=()):
    """Verify a synthetic effective-mask inventory with selected missing/bad rows."""
    unit = "vst-s2-qual-0123456789abcdef.service"
    functions = _wsl_mount_audit_functions(unit=unit)
    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    targets = sorted(set(functions["SYSTEMD_MASK_TARGETS"]) | {cgroup_target})
    missing = set(missing)
    unmasked = set(unmasked)
    rows = []
    for mount_id, target in enumerate(targets, 100):
        if target in missing:
            continue
        root = ("/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
                or target == cgroup_target else "/systemd/inaccessible/dir")
        if target in unmasked:
            root = "/unmasked"
        rows.append({"mountpoint": target, "mount_id": mount_id,
                     "mount_root": root, "filesystem": "tmpfs", "source": "none"})

    fd_mount_ids = {}
    fd_targets = {}

    class FakePath:
        def __init__(self, value):
            self.value = str(value)

        def read_text(self, encoding=None):
            fd = int(self.value.rsplit("/", 1)[-1])
            return "pos:\t0\nmnt_id:\t" + str(fd_mount_ids[fd]) + "\n"

    def fake_open(path, flags):
        assert flags == (0x200000 | 0x80000)  # Linux O_PATH | O_CLOEXEC.
        target = str(path)
        row = next(item for item in rows if item["mountpoint"] == target)
        fd = row["mount_id"]
        fd_mount_ids[fd] = row["mount_id"]
        fd_targets[fd] = target
        return fd

    def fake_fstat(fd):
        target = fd_targets[fd]
        regular = target in functions["SYSTEMD_MASK_FILES"] or target == cgroup_target
        return SimpleNamespace(
            st_mode=(functions["stat"].S_IFREG if regular else functions["stat"].S_IFDIR),
            st_uid=0, st_gid=0,
        )

    functions["os"] = SimpleNamespace(
        O_PATH=0x200000, O_CLOEXEC=0x80000,
        open=fake_open, fstat=fake_fstat, close=lambda _fd: None,
    )
    functions["pathlib"] = SimpleNamespace(Path=FakePath)
    return functions["_verify_effective_masks"](rows)


def _configure_fake_transient_unit(functions, *, inaccessible_paths,
                                   fd_entries=("0", "1", "2"), closed_fds=()):
    unit = functions["TRANSIENT_UNIT"]
    properties = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "Result": "success", "MainPID": "4321", "ControlGroup": "/system.slice/" + unit,
        "PrivateDevices": "yes", "ProtectSystem": "strict",
        "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
        "ProtectKernelLogs": "yes", "ProtectControlGroups": "yes",
        "NoNewPrivileges": "yes", "RuntimeMaxUSec": "1min",
        "InaccessiblePaths": " ".join("-" + path for path in sorted(inaccessible_paths)),
    }

    class FakePath:
        def __init__(self, value):
            self.value = str(value)
            self.name = self.value.rsplit("/", 1)[-1]

        def read_bytes(self):
            if self.value == "/proc/self/cmdline":
                return b"/usr/bin/python3.12\0-I\0-B\0-S\0-\0"
            if self.value == "/proc/self/mountinfo":
                return b"synthetic mount inventory\n"
            raise AssertionError(self.value)

        def read_text(self, encoding=None):
            assert self.value == "/proc/self/cgroup"
            return "0::/system.slice/" + unit + "\n"

    def fake_listdir(path):
        assert path == "/proc/self/fd"
        return list(fd_entries)

    def fake_fstat(fd):
        if fd in closed_fds:
            raise OSError(errno.EBADF, "descriptor closed after procfs enumeration")
        return SimpleNamespace(st_mode=0)

    functions["os"] = SimpleNamespace(
        geteuid=lambda: 0,
        getpid=lambda: 4321,
        stat=lambda path: SimpleNamespace(
            st_dev=1, st_ino=100 if path == "/proc/self/ns/mnt" else 200),
        listdir=fake_listdir,
        fstat=fake_fstat,
    )
    functions["pathlib"] = SimpleNamespace(Path=FakePath)
    functions["_systemd_unit_properties"] = lambda: properties
    return properties


def _mountinfo_line(mount_id, parent_id, device, root, target, mount_options,
                    filesystem, source, super_options):
    return (f"{mount_id} {parent_id} {device} {root} {target} {mount_options} "
            f"- {filesystem} {source} {super_options}")


def _complete_mountinfo(unit="vst-s2-qual-0123456789abcdef.service"):
    """Synthetic namespace with the exact required system mounts, masks and unit."""
    functions = _wsl_mount_audit_functions(unit=unit)
    rows = []
    ids = {}
    next_id = 1

    def parent_id(target):
        candidates = [(len(path), mount_id) for path, mount_ids in ids.items()
                      if path != target and (path == "/" or target.startswith(path.rstrip("/") + "/"))
                      for mount_id in mount_ids]
        assert candidates, target
        greatest = max(length for length, _ in candidates)
        same = [mount_id for length, mount_id in candidates if length == greatest]
        assert len(same) == 1, (target, same)
        return same[0]

    def add(target, *, root, device, filesystem, source, options, super_options,
            parent=None):
        nonlocal next_id
        mount_id = next_id
        next_id += 1
        if target == "/":
            parent = mount_id
        else:
            parent = parent_id(target) if parent is None else ids[parent][0]
        rows.append(_mountinfo_line(mount_id, parent, device, root, target,
                                    options, filesystem, source, super_options))
        ids.setdefault(target, []).append(mount_id)
        return mount_id

    add("/", root="/", device="8:1", filesystem="ext4", source="/dev/vda",
        options="ro,nosuid,relatime", super_options="rw,errors=remount-ro")
    add("/run", root="/", device="0:2", filesystem="tmpfs", source="none",
        options="rw,nosuid,nodev", super_options="rw,mode=755")
    add("/dev", root="/", device="0:3", filesystem="tmpfs", source="tmpfs",
        options="ro,nosuid,noexec",
        super_options="rw,size=4096k,nr_inodes=65536,mode=755")
    add("/sys", root="/", device="0:4", filesystem="sysfs", source="sysfs",
        options="rw,nosuid,nodev,noexec,noatime", super_options="rw")
    add("/proc", root="/", device="0:5", filesystem="proc", source="proc",
        options="rw,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/dev/mqueue", root="/", device="0:7", filesystem="mqueue", source="mqueue",
        options="rw,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/sys/fs/cgroup", root="/", device="0:8", filesystem="cgroup2", source="cgroup2",
        options="ro,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/proc/sys", root="/sys", device="0:5", filesystem="proc", source="proc",
        options="ro,nosuid,nodev,noexec,relatime", super_options="rw")
    add("/proc/sysrq-trigger", root="/sysrq-trigger", device="0:5", filesystem="proc",
        source="proc", options="ro,nosuid,nodev,noexec,relatime", super_options="rw")

    # Each pre-mask mount is placed before its systemd inaccessible overlay.
    for target in sorted(functions["SYSTEMD_MASK_TARGETS"]):
        expected = functions["MASK_BASES"].get(target)
        if expected:
            filesystem, root, source, options, parent = expected
            add(target, root=root, device="0:2", filesystem=filesystem, source=source,
                options=",".join(sorted(options)),
                super_options=("rw,gid=5,mode=620,ptmxmode=000" if target == "/dev/pts"
                               else "rw"), parent=parent)
        inaccessible_root = (
            "/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
            else "/systemd/inaccessible/dir"
        )
        add(target, root=inaccessible_root, device="0:2", filesystem="tmpfs", source="none",
            options="ro,nosuid,nodev,noexec", super_options="rw,mode=755")

    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    add(cgroup_target, root="/system.slice/" + unit + "/memory.pressure", device="0:8",
        filesystem="cgroup2", source="cgroup2",
        options="rw,nosuid,nodev,noexec,relatime", super_options="rw")
    add(cgroup_target, root="/systemd/inaccessible/reg", device="0:2", filesystem="tmpfs",
        source="none", options="ro,nosuid,nodev,noexec", super_options="rw,mode=755")
    add("/run/systemd/incoming", root="/systemd/propagate/" + unit, device="0:2",
        filesystem="tmpfs", source="none", options="ro,nosuid,nodev",
        super_options="rw,mode=755")
    return "\n".join(rows), functions


def test_pm08_mount_decoder_accepts_exact_masks_incoming_and_current_cgroup_unit():
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)

    rows, windows, rejected = functions["_decode_mountinfo"](mountinfo, expected_unit=unit)

    assert windows == []
    assert rejected == [], [item["reason"] for item in rejected]
    by_path = {}
    for row in rows:
        by_path.setdefault(row["mountpoint"], []).append(row)
    root = by_path["/"][0]
    run = by_path["/run"][0]
    assert (root["filesystem"], root["source"], root["device"], root["mount_root"]) == (
        "ext4", "/dev/vda", "8:1", "/")
    assert set(root["mount_options"]) == {"ro", "nosuid", "relatime"}
    assert (run["filesystem"], run["source"], run["device"], run["mount_root"]) == (
        "tmpfs", "none", "0:2", "/")
    pts_base = next(row for row in by_path["/dev/pts"] if row["mount_root"] == "/")
    pts_mask = next(row for row in by_path["/dev/pts"]
                    if row["mount_root"] == "/systemd/inaccessible/dir")
    dev = by_path["/dev"][0]
    assert (pts_base["filesystem"], pts_base["source"], pts_base["device"]) == (
        "devpts", "devpts", "0:2")
    assert set(pts_base["mount_options"]) == {"rw", "nosuid", "noexec", "noatime"}
    assert set(pts_base["super_options"]) == {"rw", "gid=5", "mode=620", "ptmxmode=000"}
    assert pts_base["parent_id"] == dev["mount_id"]
    assert pts_base["mount_id"] < pts_mask["mount_id"]
    expected_targets = set(functions["SYSTEMD_MASK_TARGETS"])
    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    expected_targets.add(cgroup_target)
    masks = {
        target: [row for row in group if row["filesystem"] == "tmpfs"
                 and row["source"] == "none"
                 and row["mount_root"].startswith("/systemd/inaccessible/")]
        for target, group in by_path.items()
    }
    assert {target for target, group in masks.items() if group} == expected_targets
    for target in expected_targets:
        mask = masks[target]
        assert len(mask) == 1
        assert mask[0]["device"] == run["device"]
        assert set(mask[0]["mount_options"]) == {"ro", "nosuid", "nodev", "noexec"}
        assert set(mask[0]["super_options"]) == {"rw", "mode=755"}
        expected_root = ("/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
                         or target == cgroup_target else "/systemd/inaccessible/dir")
        assert mask[0]["mount_root"] == expected_root
    incoming = by_path["/run/systemd/incoming"]
    assert len(incoming) == 1
    assert incoming[0]["mount_root"] == "/systemd/propagate/" + unit
    assert incoming[0]["device"] == run["device"]
    assert set(incoming[0]["mount_options"]) == {"ro", "nosuid", "nodev"}
    assert set(incoming[0]["super_options"]) == {"rw", "mode=755"}
    assert not any("other-unit" in row["mount_root"] for row in rows)


@pytest.mark.parametrize("target", ["/proc/latency_stats", "/proc/mtrr", "/init", "/dev/pts"])
def test_pm08_mount_decoder_rejects_missing_required_masks(target):
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    lines = [line for line in mountinfo.splitlines()
             if line.split(" - ")[0].split()[4] != target]

    _, _, unapproved = functions["_decode_mountinfo"]("\n".join(lines), expected_unit=unit)

    assert any(item.get("mountpoint") == target
               and "required inaccessible mask has no mount row" in item["reason"]
               for item in unapproved)


@pytest.mark.parametrize("target", ["/proc/latency_stats", "/proc/mtrr", "/dev/pts"])
def test_pm08_mount_decoder_rejects_unmasked_required_path(target):
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    lines = [line for line in mountinfo.splitlines()
             if not (line.split(" - ")[0].split()[4] == target
                     and line.split(" - ")[0].split()[3].startswith("/systemd/inaccessible/"))]

    _, _, unapproved = functions["_decode_mountinfo"]("\n".join(lines), expected_unit=unit)

    assert any(item.get("mountpoint") == target
               and "exact systemd inaccessible mask is missing or ambiguous" in item["reason"]
               for item in unapproved)


@pytest.mark.parametrize("mutation", [
    "wrong-gid", "wrong-mode", "wrong-ptmxmode", "wrong-mount-flags",
    "wrong-parent", "base-after-mask", "extra-nested-mount",
], ids=["gid", "mode", "ptmxmode", "mount-options", "parent", "mount-order",
       "nested-mount"])
def test_pm08_mount_decoder_rejects_unapproved_devpts_base_or_child(mutation):
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    lines = mountinfo.splitlines()
    base_index = next(i for i, line in enumerate(lines)
                      if line.split(" - ")[0].split()[4] == "/dev/pts"
                      and line.split(" - ")[0].split()[3] == "/")
    mask_index = next(i for i, line in enumerate(lines)
                      if line.split(" - ")[0].split()[4] == "/dev/pts"
                      and line.split(" - ")[0].split()[3] == "/systemd/inaccessible/dir")
    if mutation in {"wrong-gid", "wrong-mode", "wrong-ptmxmode", "wrong-mount-flags",
                    "wrong-parent"}:
        left, separator, right = lines[base_index].partition(" - ")
        left_fields, right_fields = left.split(), right.split()
        if mutation == "wrong-gid":
            right_fields[2] = "rw,gid=4,mode=620,ptmxmode=000"
        elif mutation == "wrong-mode":
            right_fields[2] = "rw,gid=5,mode=621,ptmxmode=000"
        elif mutation == "wrong-ptmxmode":
            right_fields[2] = "rw,gid=5,mode=620,ptmxmode=0666"
        elif mutation == "wrong-mount-flags":
            left_fields[5] = "rw,nosuid,noexec"
        else:
            left_fields[1] = next(line.split()[0] for line in lines
                                  if line.split(" - ")[0].split()[4] == "/")
        lines[base_index] = " ".join(left_fields) + separator + " ".join(right_fields)
    elif mutation == "base-after-mask":
        left, separator, right = lines[base_index].partition(" - ")
        fields = left.split()
        fields[0] = str(max(int(line.split()[0]) for line in lines) + 1)
        lines[base_index] = " ".join(fields) + separator + right
    elif mutation == "extra-nested-mount":
        mask_id = int(lines[mask_index].split()[0])
        lines.append(_mountinfo_line(max(int(line.split()[0]) for line in lines) + 1,
                                     mask_id, "0:6", "/", "/dev/pts/extra",
                                     "rw,nosuid,noexec,noatime", "devpts", "devpts",
                                     "rw,gid=5,mode=620,ptmxmode=000"))

    _rows, _windows, rejected = functions["_decode_mountinfo"]("\n".join(lines),
                                                                expected_unit=unit)
    assert rejected, mutation


def test_pm08_mount_decoder_rejects_nested_mount_below_missing_required_directory():
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    lines = [line for line in mountinfo.splitlines()
             if line.split(" - ")[0].split()[4] != "/proc/bus"]
    proc_id = next(int(line.split()[0]) for line in lines
                   if line.split(" - ")[0].split()[4] == "/proc")
    lines.append(_mountinfo_line(
        900, proc_id, "0:5", "/bus/child", "/proc/bus/child",
        "ro,nosuid,nodev,noexec,relatime", "proc", "proc", "rw"))

    _, _, unapproved = functions["_decode_mountinfo"]("\n".join(lines), expected_unit=unit)

    assert any(item.get("mountpoint") == "/proc/bus/child" for item in unapproved)


@pytest.mark.parametrize("target", ["/proc/latency_stats", "/proc/mtrr", "/init"])
def test_pm08_effective_masks_reject_missing_required_targets(target):
    verified, failures = _verify_effective_masks_fixture(missing={target})

    assert target not in verified
    assert any("effective inaccessible target is missing or ambiguous: " + target in failure
               for failure in failures)


@pytest.mark.parametrize("target", ["/proc/latency_stats", "/proc/mtrr", "/init"])
def test_pm08_effective_masks_reject_unmasked_targets(target):
    verified, failures = _verify_effective_masks_fixture(unmasked={target})

    assert target not in verified
    assert any("effective inaccessible target is missing or ambiguous: " + target in failure
               for failure in failures)


@pytest.mark.parametrize("mutation", ["generic", "wrong-root", "wrong-source", "wrong-device",
                                      "wrong-mount-flags", "wrong-super-flags", "missing-mask",
                                      "nested-mask-child", "wrong-unit-incoming", "windows-drive"])
def test_pm08_mount_decoder_rejects_generic_or_malformed_mounts(mutation):
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    lines = mountinfo.splitlines()

    if mutation == "generic":
        lines.append(_mountinfo_line(900, 1, "8:9", "/", "/srv/host", "rw,relatime",
                                     "ext4", "/dev/sdb", "rw"))
    elif mutation in {"wrong-root", "wrong-source", "wrong-device", "wrong-mount-flags",
                      "wrong-super-flags"}:
        target = "/home"
        for index, line in enumerate(lines):
            before, separator, after = line.partition(" - ")
            left, right = before.split(), after.split()
            if left[4] == target and left[3] == "/systemd/inaccessible/dir":
                if mutation == "wrong-root":
                    left[3] = "/unapproved-root"
                elif mutation == "wrong-source":
                    right[1] = "unapproved-source"
                elif mutation == "wrong-device":
                    left[2] = "9:9"
                elif mutation == "wrong-mount-flags":
                    left[5] = "ro,nosuid,nodev"
                else:
                    right[2] = "rw,mode=700"
                lines[index] = " ".join(left) + separator + " ".join(right)
                break
        else:
            pytest.fail("fixture did not contain the expected /home mask")
    elif mutation == "missing-mask":
        lines = [line for line in lines if not (
            line.split(" - ")[0].split()[4] == "/home"
            and line.split(" - ")[0].split()[3] == "/systemd/inaccessible/dir")]
    elif mutation == "nested-mask-child":
        home = next(line for line in lines if line.split(" - ")[0].split()[4] == "/home"
                    and line.split(" - ")[0].split()[3] == "/systemd/inaccessible/dir")
        parent = home.split(" - ")[0].split()[0]
        lines.append(_mountinfo_line(901, int(parent), "8:1", "/", "/home/nested", "ro,nosuid",
                                     "ext4", "/dev/vda", "rw"))
    elif mutation == "wrong-unit-incoming":
        for index, line in enumerate(lines):
            before, separator, after = line.partition(" - ")
            left = before.split()
            if left[4] == "/run/systemd/incoming":
                left[3] = "/systemd/propagate/vst-s2-qual-ffffffffffffffff.service"
                lines[index] = " ".join(left) + separator + after
                break
        else:
            pytest.fail("fixture did not contain the incoming mount")
    else:
        lines.append(_mountinfo_line(
            902, next(row["mount_id"] for row in functions["_decode_mountinfo"](
                mountinfo, expected_unit=unit)[0] if row["mountpoint"] == "/mnt"),
            "0:55", "/", "/mnt/c", "rw,relatime", "9p", "C:\\",
            "aname=drvfs;path=C:\\;symlinkroot=/mnt/"))

    # Contract violations are reported in the third return value; malformed
    # duplicate IDs raise directly and are covered separately below.
    rows, windows, rejected = functions["_decode_mountinfo"]("\n".join(lines), expected_unit=unit)
    assert rejected, mutation
    if mutation == "windows-drive":
        assert windows


def test_pm08_mount_decoder_rejects_duplicate_mount_ids():
    unit = "vst-s2-qual-0123456789abcdef.service"
    mountinfo, functions = _complete_mountinfo(unit)
    rows = mountinfo.splitlines()
    duplicate = rows[0].split()
    duplicate[4] = "/duplicate"

    _, _, rejected = functions["_decode_mountinfo"](
        mountinfo + "\n" + " ".join(duplicate), expected_unit=unit)
    assert any("duplicated" in item["reason"] for item in rejected)


def test_pm08_execution_unit_requires_exact_unit_identity_and_mount_namespace():
    unit = "vst-s2-qual-0123456789abcdef.service"
    functions = _wsl_mount_audit_functions(unit=unit)
    expected_inaccessible = set(functions["SYSTEMD_INACCESSIBLE_PATHS"])
    expected_inaccessible.add("/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure")
    properties = {
        "LoadState": "loaded", "ActiveState": "active", "SubState": "running",
        "Result": "success",
        "MainPID": "4321", "ControlGroup": "/system.slice/" + unit,
        "PrivateDevices": "yes", "ProtectSystem": "strict",
        "ProtectKernelTunables": "yes", "ProtectKernelModules": "yes",
        "ProtectKernelLogs": "yes", "ProtectControlGroups": "yes",
        "NoNewPrivileges": "yes", "RuntimeMaxUSec": "1min",
        "InaccessiblePaths": " ".join("-" + path for path in sorted(expected_inaccessible)),
    }

    class FakePath:
        def __init__(self, value):
            self.value = str(value)
            self.name = self.value.rsplit("/", 1)[-1]

        def read_bytes(self):
            assert self.value == "/proc/self/cmdline"
            return b"/usr/bin/python3.12\0-I\0-B\0-S\0-\0"

        def read_text(self, encoding=None):
            assert self.value == "/proc/self/cgroup"
            return "0::/system.slice/" + unit + "\n"

    fake_os = SimpleNamespace(
        geteuid=lambda: 0,
        getpid=lambda: 4321,
        stat=lambda path: SimpleNamespace(
            st_dev=1, st_ino=100 if path == "/proc/self/ns/mnt" else 200),
        listdir=lambda path: ["0", "1", "2"],
        fstat=lambda fd: None,
    )
    functions["os"] = fake_os
    functions["pathlib"] = SimpleNamespace(Path=FakePath)
    functions["_systemd_unit_properties"] = lambda: properties
    result = functions["_verify_execution_unit"]()
    assert result["unit"] == unit
    assert result["mount_namespace_distinct_from_pid1"] is True
    assert result["properties"] == properties
    assert result["open_fds"] == ["0", "1", "2"]

    # A hardening mismatch is retained as bounded expected/observed fields.
    properties["ProtectSystem"] = "full"
    functions["R"].clear()
    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()
    assert functions["R"]["reason"] == (
        "transient-unit identity or hardening properties differ from the exact profile")
    property_mismatch = functions["R"]["transient_unit_property_mismatch"]
    assert set(property_mismatch) == {"expected", "observed"}
    assert set(property_mismatch["expected"]) == {
        "LoadState", "ActiveState", "SubState", "Result", "MainPID", "ControlGroup",
        "PrivateDevices", "ProtectSystem", "ProtectKernelTunables", "ProtectKernelModules",
        "ProtectKernelLogs", "ProtectControlGroups", "NoNewPrivileges", "RuntimeMaxUSec",
    }
    assert property_mismatch["expected"]["ProtectSystem"] == "strict"
    assert property_mismatch["observed"] == {
        key: properties[key] for key in property_mismatch["expected"]
    }
    assert property_mismatch["observed"]["ProtectSystem"] == "full"

    properties["ProtectSystem"] = "strict"
    properties["ControlGroup"] = "/system.slice/vst-s2-qual-ffffffffffffffff.service"
    functions["R"].clear()
    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()
    assert functions["R"]["reason"] == (
        "transient-unit identity or hardening properties differ from the exact profile")
    assert functions["R"]["transient_unit_property_mismatch"]["expected"]["ControlGroup"] == (
        "/system.slice/" + unit)
    assert functions["R"]["transient_unit_property_mismatch"]["observed"]["ControlGroup"] == (
        "/system.slice/vst-s2-qual-ffffffffffffffff.service")

    properties["ControlGroup"] = "/system.slice/" + unit
    functions["MOUNT_AUDIT_ONLY"] = False
    expected_paths = sorted(expected_inaccessible)
    missing_path = expected_paths[0]
    properties["InaccessiblePaths"] = " ".join("-" + path for path in expected_paths[1:])
    functions["R"].clear()
    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()
    assert functions["R"]["reason"] == (
        "transient-unit inaccessible path set differs from the exact approved target set")
    assert functions["R"]["inaccessible_path_mismatch"] == {
        "expected": expected_paths,
        "observed": expected_paths[1:],
        "missing": [missing_path],
        "unexpected": [],
    }

    unexpected_path = "/tmp/unexpected-mask-target"
    properties["InaccessiblePaths"] = " ".join(
        "-" + path for path in expected_paths + [unexpected_path])
    functions["R"].clear()
    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()
    assert functions["R"]["reason"] == (
        "transient-unit inaccessible path set differs from the exact approved target set")
    assert functions["R"]["inaccessible_path_mismatch"] == {
        "expected": expected_paths,
        "observed": sorted(expected_paths + [unexpected_path]),
        "missing": [],
        "unexpected": [unexpected_path],
    }


def test_pm08_readonly_audit_keeps_mount_inventory_when_init_property_is_missing():
    functions = _wsl_mount_audit_functions()
    expected = set(functions["SYSTEMD_INACCESSIBLE_PATHS"])
    expected.add("/sys/fs/cgroup/system.slice/" + functions["TRANSIENT_UNIT"]
                 + "/memory.pressure")
    properties = _configure_fake_transient_unit(
        functions, inaccessible_paths=expected - {"/init"})
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []\n"
    functions["BASELINE_DECODER_SOURCE"] = baseline_source
    functions["BASELINE_DECODER_SHA256"] = _sha(baseline_source.encode("utf-8"))
    functions["BASELINE_DECODER_REVISION"] = "0" * 40
    functions["_decode_mountinfo"] = lambda raw, expected_unit=None: ([], [], [])
    functions["_verify_effective_masks"] = lambda rows: ({}, [])
    functions["_verify_private_dev"] = lambda rows: ({}, [])

    functions["_read_only_mount_audit"]()

    mismatch = functions["R"]["inaccessible_path_mismatch"]
    assert mismatch["missing"] == ["/init"]
    assert mismatch["unexpected"] == []
    audit = functions["R"]["mount_audit"]
    assert audit["terminal"] == "HOLD"
    assert audit["inaccessible_path_mismatch"] == mismatch
    assert audit["mountinfo_bytes"] > 0
    assert audit["execution"]["properties"] == properties


def test_pm08_runtime_preflight_still_stops_on_missing_init_property():
    functions = _wsl_mount_audit_functions()
    expected = set(functions["SYSTEMD_INACCESSIBLE_PATHS"])
    expected.add("/sys/fs/cgroup/system.slice/" + functions["TRANSIENT_UNIT"]
                 + "/memory.pressure")
    functions["MOUNT_AUDIT_ONLY"] = False
    _configure_fake_transient_unit(functions, inaccessible_paths=expected - {"/init"})

    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()

    assert functions["R"]["inaccessible_path_mismatch"]["missing"] == ["/init"]
    assert functions["R"]["terminal"] == "HOLD"


def test_pm08_open_fd_snapshot_ignores_closed_procfs_entry():
    functions = _wsl_mount_audit_functions()
    expected = set(functions["SYSTEMD_INACCESSIBLE_PATHS"])
    expected.add("/sys/fs/cgroup/system.slice/" + functions["TRANSIENT_UNIT"]
                 + "/memory.pressure")
    _configure_fake_transient_unit(
        functions, inaccessible_paths=expected, fd_entries=("0", "1", "2", "17"),
        closed_fds=(17,))
    result = functions["_verify_execution_unit"]()

    assert result["open_fds"] == ["0", "1", "2"]
    assert functions["R"].get("open_fds_mismatch") is None


def test_pm08_open_fd_snapshot_rejects_still_open_extra_descriptor():
    functions = _wsl_mount_audit_functions()
    expected = set(functions["SYSTEMD_INACCESSIBLE_PATHS"])
    expected.add("/sys/fs/cgroup/system.slice/" + functions["TRANSIENT_UNIT"]
                 + "/memory.pressure")
    _configure_fake_transient_unit(
        functions, inaccessible_paths=expected, fd_entries=("0", "1", "2", "17"))

    with pytest.raises(functions["Hold"]):
        functions["_verify_execution_unit"]()

    assert functions["R"]["open_fds_mismatch"] == {
        "expected": ["0", "1", "2"], "observed": ["0", "1", "2", "17"]}


def test_pm08_effective_masks_verify_mount_id_type_and_root_ownership():
    unit = "vst-s2-qual-0123456789abcdef.service"
    functions = _wsl_mount_audit_functions(unit=unit)
    assert {"/proc/latency_stats", "/proc/mtrr"} <= functions["SYSTEMD_MASK_FILES"]
    assert not ({"/proc/latency_stats", "/proc/mtrr"} & functions["SYSTEMD_MASK_DIRS"])
    cgroup_target = "/sys/fs/cgroup/system.slice/" + unit + "/memory.pressure"
    targets = sorted(set(functions["SYSTEMD_MASK_TARGETS"]) | {cgroup_target})
    rows = []
    for mount_id, target in enumerate(targets, 100):
        root = ("/systemd/inaccessible/reg" if target in functions["SYSTEMD_MASK_FILES"]
                or target == cgroup_target else "/systemd/inaccessible/dir")
        rows.append({"mountpoint": target, "mount_id": mount_id,
                     "mount_root": root, "filesystem": "tmpfs", "source": "none"})

    fd_mount_ids = {}
    opened = []

    class FakePath:
        def __init__(self, value):
            self.value = str(value)

        def read_text(self, encoding=None):
            fd = int(self.value.rsplit("/", 1)[-1])
            return "pos:\t0\nmnt_id:\t" + str(fd_mount_ids[fd]) + "\n"

    wrong_mount_for = []

    def fake_open(path, flags):
        assert flags == (0x200000 | 0x80000)  # Linux O_PATH | O_CLOEXEC.
        target = str(path)
        row = next(item for item in rows if item["mountpoint"] == target)
        fd = row["mount_id"]
        fd_mount_ids[fd] = row["mount_id"] + (1 if target in wrong_mount_for else 0)
        opened.append(target)
        return fd

    def fake_fstat(fd):
        target = opened[fd - 100]
        regular = target in functions["SYSTEMD_MASK_FILES"] or target == cgroup_target
        return SimpleNamespace(
            st_mode=(functions["stat"].S_IFREG if regular else functions["stat"].S_IFDIR),
            st_uid=0, st_gid=0,
        )

    functions["os"] = SimpleNamespace(
        O_PATH=0x200000, O_CLOEXEC=0x80000,
        open=fake_open, fstat=fake_fstat, close=lambda _fd: None,
    )
    functions["pathlib"] = SimpleNamespace(Path=FakePath)
    verified, failures = functions["_verify_effective_masks"](rows)

    assert failures == []
    assert set(verified) == set(targets)
    assert len(opened) == len(targets)
    for item in verified.values():
        assert item["uid"] == item["gid"] == item["mode"] == 0
        assert item["type"] in {"regular", "directory"}

    wrong_mount_for.append(targets[0])
    verified, failures = functions["_verify_effective_masks"](rows)
    assert failures
    assert any("different mount" in failure for failure in failures)


def test_runtime_and_wsl_helper_mask_target_sets_match():
    functions = _wsl_mount_audit_functions()

    assert set(harness.SYSTEMD_MASK_TARGETS) == functions["SYSTEMD_MASK_TARGETS"]
    assert "/dev/pts" in harness.SYSTEMD_MASK_TARGETS
    assert "/dev/pts" in functions["SYSTEMD_INACCESSIBLE_PATHS"]
    assert "/init" in harness.SYSTEMD_MASK_TARGETS


def _private_dev_fixture(*, char_extra=False, masked_extra=False, wrong_null_mode=False,
                         pts_extra=False, pts_ptmx=False, wrong_pts_mode=False,
                         wrong_pts_owner=False, mqueue_extra=False):
    functions = _wsl_mount_audit_functions()
    links = {
        "core": "/proc/kcore", "fd": "/proc/self/fd", "log": "/run/systemd/journal/dev-log",
        "stdin": "/proc/self/fd/0", "stdout": "/proc/self/fd/1", "stderr": "/proc/self/fd/2",
    }
    devices = {"tty": (5, 0), "urandom": (1, 9), "random": (1, 8),
               "full": (1, 7), "zero": (1, 5), "null": (1, 3), "ptmx": (5, 2)}
    directories = {"char": (0o755, 0, 0), "hugepages": (0, 0, 0),
                   "mqueue": (0o1777, 0, 0),
                   "pts": (0o755 if wrong_pts_mode else 0,
                          1 if wrong_pts_owner else 0, 0),
                   "shm": (0, 0, 0)}
    names = set(links) | set(devices) | set(directories)
    stats = {}
    link_targets = {}
    for name, target in links.items():
        stats["/dev/" + name] = SimpleNamespace(st_mode=functions["stat"].S_IFLNK | 0o777,
                                                st_uid=0, st_gid=0, st_rdev=0)
        link_targets["/dev/" + name] = target
    for name, (major, minor) in devices.items():
        mode = 0o600 if name == "null" and wrong_null_mode else 0o666
        stats["/dev/" + name] = SimpleNamespace(st_mode=functions["stat"].S_IFCHR | mode,
                                                st_uid=0, st_gid=0, st_rdev=(major, minor))
    for name, (mode, uid, gid) in directories.items():
        stats["/dev/" + name] = SimpleNamespace(st_mode=functions["stat"].S_IFDIR | mode,
                                                st_uid=uid, st_gid=gid, st_rdev=0)

    children = {name: [] for name in ("char", "hugepages", "mqueue", "pts", "shm")}
    aliases = {"1:3": "../null", "1:5": "../zero", "1:7": "../full",
               "1:8": "../random", "1:9": "../urandom", "5:0": "../tty", "5:2": "../ptmx"}
    for alias, target in aliases.items():
        children["char"].append(SimpleNamespace(
            name=alias, path="/dev/char/" + alias,
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFLNK | 0o777, st_uid=0, st_gid=0, st_rdev=0)))
        link_targets["/dev/char/" + alias] = target
    if pts_ptmx:
        children["pts"].append(SimpleNamespace(
            name="ptmx", path="/dev/pts/ptmx",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFCHR, st_uid=0, st_gid=0, st_rdev=(5, 2))))
    if pts_extra:
        children["pts"].append(SimpleNamespace(
            name="unexpected-device", path="/dev/pts/unexpected-device",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFCHR | 0o600, st_uid=0, st_gid=0, st_rdev=(1, 3))))
    if mqueue_extra:
        children["mqueue"].append(SimpleNamespace(
            name="unexpected-device", path="/dev/mqueue/unexpected-device",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFCHR | 0o600, st_uid=0, st_gid=0, st_rdev=(1, 3))))
    if char_extra:
        children["char"].append(SimpleNamespace(
            name="9:9", path="/dev/char/9:9",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFLNK | 0o777, st_uid=0, st_gid=0, st_rdev=0)))
        link_targets["/dev/char/9:9"] = "../null"
    if masked_extra:
        children["shm"].append(SimpleNamespace(
            name="unexpected", path="/dev/shm/unexpected",
            stat=lambda *, follow_symlinks=False: SimpleNamespace(
                st_mode=functions["stat"].S_IFREG | 0o600, st_uid=0, st_gid=0, st_rdev=0)))

    class Dir:
        def __init__(self, rows):
            self.rows = rows
        def __enter__(self):
            return iter(self.rows)
        def __exit__(self, *_args):
            return False

    fake_os = SimpleNamespace(
        scandir=lambda path: Dir([SimpleNamespace(name=name) for name in sorted(names)])
        if path == "/dev" else Dir(children[path.rsplit("/", 1)[-1]]),
        lstat=lambda path: stats[path],
        readlink=lambda path: link_targets[path],
        major=lambda value: value[0], minor=lambda value: value[1],
    )
    functions["os"] = fake_os
    mount_rows = [{"mountpoint": "/dev/pts"}, {"mountpoint": "/dev/mqueue"},
                  {"mountpoint": "/dev/hugepages"}, {"mountpoint": "/dev/shm"}]
    return functions, mount_rows


def test_pm08_private_dev_requires_exact_metadata_aliases_and_empty_masked_dirs():
    functions, mount_rows = _private_dev_fixture()
    result, failures = functions["_verify_private_dev"](mount_rows)
    assert failures == []
    assert result["entries"]["null"] == {
        "uid": 0, "gid": 0, "mode": 0o666, "type": "character", "major": 1, "minor": 3,
    }
    assert set(result["nested_entries"]["char"]) == {
        "1:3", "1:5", "1:7", "1:8", "1:9", "5:0", "5:2",
    }
    assert result["nested_entries"]["hugepages"] == {}
    assert result["entries"]["pts"] == {
        "uid": 0, "gid": 0, "mode": 0, "type": "directory",
    }
    assert result["nested_entries"]["pts"] == {}
    assert result["nested_entries"]["shm"] == {}


@pytest.mark.parametrize("kwargs", [
    {"char_extra": True}, {"masked_extra": True}, {"wrong_null_mode": True},
    {"pts_extra": True}, {"pts_ptmx": True}, {"wrong_pts_mode": True},
    {"wrong_pts_owner": True}, {"mqueue_extra": True},
])
def test_pm08_private_dev_rejects_alias_nested_content_and_wrong_device_mode(kwargs):
    functions, mount_rows = _private_dev_fixture(**kwargs)
    _, failures = functions["_verify_private_dev"](mount_rows)
    assert failures


@pytest.mark.parametrize(("runtime_max_sec", "expected_wait_timeout"), [(60, 90), (2400, 2430)])
def test_pm08_run_bounded_wsl_uses_exact_unit_and_systemd_isolation_properties(
        monkeypatch, runtime_max_sec, expected_wait_timeout):
    run_id = "run-s2-4-pm08-fixture"
    expected_unit = "vst-s2-qual-" + hashlib.sha256(run_id.encode("ascii")).hexdigest()[:16] + ".service"
    script = b"synthetic protocol source\r\n"
    captured = {}

    class CapturingInput:
        def __init__(self):
            self.data = bytearray()
            self.closed = False
        def write(self, data):
            self.data.extend(data)
            return len(data)
        def flush(self):
            pass
        def close(self):
            self.closed = True

    class MockProcess:
        def __init__(self, argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            self.stdin = CapturingInput()
            self.stdout = io.BytesIO(b"bounded stdout")
            self.stderr = io.BytesIO(b"")
            self.returncode = 0
            captured["stdin"] = self.stdin
        def wait(self, *, timeout):
            captured["wait_timeout"] = timeout
            return self.returncode

    monkeypatch.setattr(harness.subprocess, "Popen", MockProcess)
    result = harness._run_bounded_wsl(
        script, unit_name=expected_unit, runtime_max_sec=runtime_max_sec)

    expected_mask_paths = sorted(set(harness.SYSTEMD_MASK_TARGETS) | {
        "/sys/fs/cgroup/system.slice/" + expected_unit + "/memory.pressure",
    })
    inaccessible_paths = expected_mask_paths
    assert "/init" in inaccessible_paths
    assert all(not path.startswith("-") for path in inaccessible_paths)
    expected_properties = [
        "--property=PrivateDevices=yes", "--property=ProtectSystem=strict",
        "--property=ProtectKernelTunables=yes", "--property=ProtectKernelModules=yes",
        "--property=ProtectKernelLogs=yes", "--property=ProtectControlGroups=yes",
        "--property=NoNewPrivileges=yes", "--property=RuntimeMaxSec=" + str(runtime_max_sec) + "s",
        "--property=InaccessiblePaths=" + " ".join(expected_mask_paths),
    ]
    assert captured["argv"] == [
        "wsl.exe", "--distribution", harness.WSL_DISTRIBUTION, "--user", "root",
        "--exec", "/usr/bin/systemd-run", "--wait", "--collect", "--pipe", "--quiet",
        "--unit=" + expected_unit, *expected_properties, "--",
        "/usr/bin/python3.12", "-I", "-B", "-S", "-",
    ]
    assert result["unit_name"] == expected_unit
    assert result["runtime_max_sec"] == runtime_max_sec
    assert captured["wait_timeout"] == expected_wait_timeout
    assert result["systemd_properties"] == expected_properties
    assert captured["stdin"].data == script
    assert captured["stdin"].closed
    assert captured["kwargs"]["close_fds"] is True
    assert captured["kwargs"]["bufsize"] == 0
    assert captured["kwargs"]["stdin"] == harness.subprocess.PIPE
    assert captured["kwargs"]["stdout"] == harness.subprocess.PIPE
    assert captured["kwargs"]["stderr"] == harness.subprocess.PIPE
    assert harness.SYSTEMD_STARTUP_SHUTDOWN_GRACE_SEC == 30
    assert harness._transient_unit_name(run_id) == harness._transient_unit_name(run_id)
    assert harness._transient_unit_name(run_id + "-different") != expected_unit


@pytest.mark.parametrize("uppercase_hashes", [False, True])
def test_pm08_mount_audit_binds_sources_baseline_and_creates_no_auth_or_attempt_files(
        monkeypatch, tmp_path, capsys, uppercase_hashes):
    launcher_bytes = b"exact launcher source bytes\n"
    helper_bytes = MOCK_WSL_SOURCE
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    baseline_sha = _sha(baseline_source.encode("utf-8"))
    protocol = json.dumps({
        "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
        "terminal": "PASS", "mount_audit": {
            "schema": "VST_S2_RUNTIME_MOUNT_AUDIT_V1", "terminal": "PASS",
            "reason": "synthetic read-only mount audit",
        },
    }, separators=(",", ":")).encode("ascii")
    launched = []

    def read_source(path, *, maximum):
        assert maximum == harness.MAX_WSL_SCRIPT_BYTES
        return launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes

    def fake_git(_root, *args, maximum):
        assert maximum in {1024, harness.MAX_WSL_SCRIPT_BYTES}
        if args[0] == "rev-parse":
            return (baseline + "\n").encode("ascii")
        assert args[0] == "show"
        return baseline_source.encode("utf-8")

    def fake_wsl(script, *, unit_name, runtime_max_sec):
        launched.append((script, unit_name, runtime_max_sec))
        return {
            "exit_code": 0, "timed_out": False, "writer_error": None,
            "unit_name": unit_name,
            "runtime_max_sec": runtime_max_sec, "systemd_properties": [],
            "stdout": {"bytes": len(protocol), "sha256": _sha(protocol),
                       "prefix": protocol, "truncated": False},
            "stderr": {"bytes": 0, "sha256": _sha(b""), "prefix": b"", "truncated": False},
        }

    monkeypatch.setattr(harness, "_read_bounded_regular", read_source)
    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", fake_wsl)
    experiment_id = "s2-4-pm08-readonly-01"
    expected_unit = harness._transient_unit_name(experiment_id)
    launcher_hash = _sha(launcher_bytes)
    helper_hash = _sha(helper_bytes)
    if uppercase_hashes:
        launcher_hash = launcher_hash.upper()
        helper_hash = helper_hash.upper()

    exit_code = harness.run_read_only_mount_audit(
        root=tmp_path, experiment_id=experiment_id,
        expected_launcher_sha256=launcher_hash,
        expected_helper_sha256=helper_hash,
    )

    assert exit_code == 0
    assert len(launched) == 1
    script, unit_name, runtime_max_sec = launched[0]
    marker = b"AUTH = json.loads(AUTH)\n"
    marker_offset = helper_bytes.index(marker)
    injected = (
        b'AUTH = "{}"\n'
        + ("TRANSIENT_UNIT = " + json.dumps(expected_unit) + "\n").encode("ascii")
        + b"MOUNT_AUDIT_ONLY = True\n"
        + ("BASELINE_DECODER_SOURCE = " + json.dumps(baseline_source) + "\n").encode("ascii")
        + ("BASELINE_DECODER_SHA256 = " + json.dumps(baseline_sha) + "\n").encode("ascii")
        + ("BASELINE_DECODER_REVISION = " + json.dumps(baseline) + "\n").encode("ascii")
    )
    expected_script = helper_bytes[:marker_offset] + injected + helper_bytes[marker_offset:]
    assert script == expected_script
    compile(script, "<mock-mount-audit-script>", "exec")
    audit_tree = ast.parse(script.decode("ascii"))
    audit_mode = next(ast.literal_eval(node.value) for node in audit_tree.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name)
                              and target.id == "MOUNT_AUDIT_ONLY" for target in node.targets))
    assert audit_mode is True
    assert script.index(b"from __future__ import annotations\n") < script.index(b'AUTH = "{}"\n')
    assert script.index(b"import json\n") < script.index(b'AUTH = "{}"\n')
    assert script.count(marker) == 1
    assert script.index(marker) > script.index(b'AUTH = "{}"\n')
    prefix = script[:script.index(b"# mocked protocol body")].decode("ascii")
    assert 'AUTH = "{}"\n' in prefix
    assert 'TRANSIENT_UNIT = ' + json.dumps(expected_unit) in prefix
    assert "MOUNT_AUDIT_ONLY = True" in prefix
    assert 'BASELINE_DECODER_SOURCE = ' + json.dumps(baseline_source) in prefix
    assert 'BASELINE_DECODER_SHA256 = ' + json.dumps(baseline_sha) in prefix
    assert 'BASELINE_DECODER_REVISION = ' + json.dumps(baseline) in prefix
    assert script[script.index(marker):].endswith(helper_bytes[marker_offset:])
    assert "attempt" not in prefix
    assert "docs/sdlc/evidence" not in prefix
    assert unit_name == expected_unit
    assert runtime_max_sec == 60
    report = json.loads(capsys.readouterr().out)
    assert report["source_identity"] == {
        "launcher_sha256": _sha(launcher_bytes),
        "helper_sha256": _sha(helper_bytes),
        "baseline_revision": baseline,
        "baseline_decoder_sha256": baseline_sha,
    }
    assert report["terminal"] == "PASS"
    assert len(launched) == 1  # Uppercase valid digests must reach the mock executor.
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize("failure", ["launcher-hash", "helper-hash", "baseline-revision"])
def test_pm08_mount_audit_fails_closed_before_wsl_on_source_or_baseline_mismatch(
        monkeypatch, tmp_path, failure):
    launcher_bytes, helper_bytes = b"launcher\n", MOCK_WSL_SOURCE
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    calls = []

    monkeypatch.setattr(harness, "_read_bounded_regular", lambda path, **_kwargs:
                        launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes)

    def fake_git(_root, *args, maximum):
        if args[0] == "rev-parse":
            revision = "f" * 40 if failure == "baseline-revision" else baseline
            return (revision + "\n").encode("ascii")
        return baseline_source.encode("utf-8")

    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl",
                        lambda *_args, **_kwargs: calls.append(True))
    expected_launcher = "0" * 64 if failure == "launcher-hash" else _sha(launcher_bytes)
    expected_helper = "0" * 64 if failure == "helper-hash" else _sha(helper_bytes)

    with pytest.raises(harness.QualificationError):
        harness.run_read_only_mount_audit(
            root=tmp_path, experiment_id="s2-4-pm08-readonly-02",
            expected_launcher_sha256=expected_launcher,
            expected_helper_sha256=expected_helper,
        )
    assert calls == []
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize("marker_case", ["missing", "duplicate"])
def test_pm08_mount_audit_refuses_nonunique_injection_marker_before_runner(
        monkeypatch, tmp_path, marker_case):
    marker = b"AUTH = json.loads(AUTH)\n"
    launcher_bytes = b"exact launcher source bytes\n"
    if marker_case == "missing":
        helper_bytes = MOCK_WSL_SOURCE.replace(marker, b"AUTH = {}\n")
    else:
        helper_bytes = MOCK_WSL_SOURCE + marker
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    calls = []

    def read_source(path, *, maximum):
        assert maximum == harness.MAX_WSL_SCRIPT_BYTES
        return launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes

    def fake_git(_root, *args, maximum):
        if args[0] == "rev-parse":
            return (baseline + "\n").encode("ascii")
        assert args[0] == "show"
        return baseline_source.encode("utf-8")

    monkeypatch.setattr(harness, "_read_bounded_regular", read_source)
    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl",
                        lambda *_args, **_kwargs: calls.append(True))

    with pytest.raises(harness.QualificationError, match="value-injection point is not unique"):
        harness.run_read_only_mount_audit(
            root=tmp_path, experiment_id="s2-4-pm08-marker-refusal-01",
            expected_launcher_sha256=_sha(launcher_bytes),
            expected_helper_sha256=_sha(helper_bytes),
        )

    assert calls == []
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize(("failure", "expected_terminal"), [
    ("invalid-utf8", "HOLD"),
    ("invalid-json", "HOLD"),
    ("timeout", "UNKNOWN"),
    ("stdout-truncated", "UNKNOWN"),
    ("stderr-truncated", "UNKNOWN"),
    ("wrong-protocol-schema", "HOLD"),
])
def test_pm08_mount_audit_emits_bounded_structured_hold_without_attempt_files(
        monkeypatch, tmp_path, capsys, failure, expected_terminal):
    launcher_bytes, helper_bytes = b"exact launcher source bytes\n", MOCK_WSL_SOURCE
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    if failure == "invalid-utf8":
        stdout_prefix = b"\xffnot-json"
    elif failure == "invalid-json":
        stdout_prefix = b'{"schema":'
    elif failure == "wrong-protocol-schema":
        stdout_prefix = json.dumps({
            "schema": "UNEXPECTED_PROTOCOL_V0", "terminal": "PASS",
        }, separators=(",", ":")).encode("ascii")
    elif failure == "stdout-truncated":
        stdout_prefix = b"x" * 20000
    else:
        stdout_prefix = b'{"schema":"VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1"}'
    stderr_prefix = b"y" * 20000 if failure == "stderr-truncated" else b"synthetic diagnostic"
    stdout_truncated = failure == "stdout-truncated"
    stderr_truncated = failure == "stderr-truncated"
    timed_out = failure == "timeout"
    launched = []

    def read_source(path, *, maximum):
        assert maximum == harness.MAX_WSL_SCRIPT_BYTES
        return launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes

    def fake_git(_root, *args, maximum):
        if args[0] == "rev-parse":
            return (baseline + "\n").encode("ascii")
        assert args[0] == "show"
        return baseline_source.encode("utf-8")

    def fake_wsl(_script, *, unit_name, runtime_max_sec):
        launched.append((unit_name, runtime_max_sec))
        return {
            "exit_code": 0 if not timed_out else None,
            "timed_out": timed_out, "writer_error": None,
            "unit_name": unit_name, "runtime_max_sec": runtime_max_sec,
            "systemd_properties": ["RuntimeMaxSec=60"],
            "stdout": {
                "bytes": len(stdout_prefix), "sha256": _sha(stdout_prefix),
                "prefix": stdout_prefix, "truncated": stdout_truncated,
            },
            "stderr": {
                "bytes": len(stderr_prefix), "sha256": _sha(stderr_prefix),
                "prefix": stderr_prefix, "truncated": stderr_truncated,
            },
        }

    monkeypatch.setattr(harness, "_read_bounded_regular", read_source)
    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", fake_wsl)
    experiment_id = "s2-4-pm08-failure-01"
    expected_unit = harness._transient_unit_name(experiment_id)

    exit_code = harness.run_read_only_mount_audit(
        root=tmp_path, experiment_id=experiment_id,
        expected_launcher_sha256=_sha(launcher_bytes),
        expected_helper_sha256=_sha(helper_bytes),
    )

    assert exit_code == 2
    assert launched == [(expected_unit, 60)]
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == "VST_S2_RUNTIME_MOUNT_AUDIT_OUTER_V1"
    assert report["terminal"] == expected_terminal
    assert report["terminal"] != "PASS"
    assert report["experiment_id"] == experiment_id
    assert report["source_identity"] == {
        "launcher_sha256": _sha(launcher_bytes),
        "helper_sha256": _sha(helper_bytes),
        "baseline_revision": baseline,
        "baseline_decoder_sha256": _sha(baseline_source.encode("utf-8")),
    }
    outer = report["outer_process"]
    assert outer["unit_name"] == expected_unit
    assert outer["runtime_max_sec"] == 60
    assert outer["timed_out"] is timed_out
    assert outer["stdout_bytes"] == len(stdout_prefix)
    assert outer["stdout_sha256"] == _sha(stdout_prefix)
    assert outer["stdout_truncated"] is stdout_truncated
    assert outer["stderr_bytes"] == len(stderr_prefix)
    assert outer["stderr_sha256"] == _sha(stderr_prefix)
    assert outer["stderr_truncated"] is stderr_truncated
    assert len(outer["stdout_prefix"]) <= 16384
    assert len(outer["stderr_prefix"]) <= 16384
    assert set(outer) == {
        "exit_code", "timed_out", "writer_error", "unit_name", "runtime_max_sec",
        "systemd_properties", "stdout_bytes", "stdout_sha256", "stdout_truncated",
        "stdout_prefix", "stderr_bytes", "stderr_sha256", "stderr_truncated",
        "stderr_prefix",
    }
    assert not any("auth" in key.lower() or "attempt" in key.lower()
                   for key in report.keys() | outer.keys())
    assert list(tmp_path.rglob("*")) == []


def test_pm08_mount_audit_downgrades_helper_pass_when_outer_exit_is_nonzero(
        monkeypatch, tmp_path, capsys):
    launcher_bytes, helper_bytes = b"exact launcher source bytes\n", MOCK_WSL_SOURCE
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    protocol = json.dumps({
        "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
        "terminal": "PASS", "mount_audit": {
            "schema": "VST_S2_RUNTIME_MOUNT_AUDIT_V1",
            "terminal": "PASS", "reason": "synthetic helper PASS",
        },
    }, separators=(",", ":")).encode("ascii")
    launched = []

    def read_source(path, *, maximum):
        assert maximum == harness.MAX_WSL_SCRIPT_BYTES
        return launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes

    def fake_git(_root, *args, maximum):
        if args[0] == "rev-parse":
            return (baseline + "\n").encode("ascii")
        assert args[0] == "show"
        return baseline_source.encode("utf-8")

    def fake_wsl(_script, *, unit_name, runtime_max_sec):
        launched.append((unit_name, runtime_max_sec))
        stderr = b"synthetic outer failure"
        return {
            "exit_code": 17, "timed_out": False, "writer_error": None,
            "unit_name": unit_name, "runtime_max_sec": runtime_max_sec,
            "systemd_properties": ["RuntimeMaxSec=60"],
            "stdout": {
                "bytes": len(protocol), "sha256": _sha(protocol),
                "prefix": protocol, "truncated": False,
            },
            "stderr": {
                "bytes": len(stderr), "sha256": _sha(stderr),
                "prefix": stderr, "truncated": False,
            },
        }

    monkeypatch.setattr(harness, "_read_bounded_regular", read_source)
    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", fake_wsl)
    experiment_id = "s2-4-pm08-nonzero-outer-01"
    expected_unit = harness._transient_unit_name(experiment_id)

    exit_code = harness.run_read_only_mount_audit(
        root=tmp_path, experiment_id=experiment_id,
        expected_launcher_sha256=_sha(launcher_bytes),
        expected_helper_sha256=_sha(helper_bytes),
    )

    assert exit_code == 2
    assert launched == [(expected_unit, 60)]
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == "VST_S2_RUNTIME_MOUNT_AUDIT_V1"
    assert report["terminal"] == "HOLD"
    assert report["reason"] == "outer transient unit exited nonzero despite helper PASS"
    assert report["terminal"] != "PASS"
    assert report["outer_process"]["exit_code"] == 17
    assert report["outer_process"]["timed_out"] is False
    assert report["source_identity"]["launcher_sha256"] == _sha(launcher_bytes)
    assert report["source_identity"]["helper_sha256"] == _sha(helper_bytes)
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.parametrize(("case", "protocol_terminal", "expected_reason"), [
    ("terminal-mismatch", "HOLD", "protocol and mount-audit terminal statuses disagree"),
    ("invalid-top-terminal", "SUCCESS", "protocol terminal status is invalid"),
    ("runner-error", "PASS", "bounded WSL runner ended without a complete result; do not retry"),
])
def test_pm08_mount_audit_rejects_protocol_terminal_conflicts_and_runner_errors(
        monkeypatch, tmp_path, capsys, case, protocol_terminal, expected_reason):
    launcher_bytes, helper_bytes = b"exact launcher source bytes\n", MOCK_WSL_SOURCE
    baseline = harness.MOUNT_AUDIT_BASELINE
    baseline_source = "def _decode_mountinfo(raw):\n    return [], [], []"
    experiment_id = "s2-4-pm08-terminal-check-01"
    nested_terminal = "PASS"
    protocol = json.dumps({
        "schema": "VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V1",
        "terminal": protocol_terminal,
        "mount_audit": {
            "schema": "VST_S2_RUNTIME_MOUNT_AUDIT_V1",
            "terminal": nested_terminal,
            "reason": "synthetic nested PASS",
            "experiment_id": experiment_id,
        },
    }, separators=(",", ":")).encode("ascii")

    def read_source(path, *, maximum):
        assert maximum == harness.MAX_WSL_SCRIPT_BYTES
        return launcher_bytes if Path(path) == Path(harness.__file__) else helper_bytes

    def fake_git(_root, *args, maximum):
        if args[0] == "rev-parse":
            return (baseline + "\n").encode("ascii")
        assert args[0] == "show"
        return baseline_source.encode("utf-8")

    def fake_wsl(_script, *, unit_name, runtime_max_sec):
        if case == "runner-error":
            raise harness.QualificationError("synthetic runner failure")
        stderr = b""
        return {
            "exit_code": 0, "timed_out": False, "writer_error": None,
            "unit_name": unit_name, "runtime_max_sec": runtime_max_sec,
            "systemd_properties": ["RuntimeMaxSec=60"],
            "stdout": {
                "bytes": len(protocol), "sha256": _sha(protocol),
                "prefix": protocol, "truncated": False,
            },
            "stderr": {
                "bytes": len(stderr), "sha256": _sha(stderr),
                "prefix": stderr, "truncated": False,
            },
        }

    monkeypatch.setattr(harness, "_read_bounded_regular", read_source)
    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", fake_wsl)

    exit_code = harness.run_read_only_mount_audit(
        root=tmp_path, experiment_id=experiment_id,
        expected_launcher_sha256=_sha(launcher_bytes),
        expected_helper_sha256=_sha(helper_bytes),
    )

    assert exit_code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["terminal"] in {"HOLD", "UNKNOWN"}
    assert report["terminal"] != "PASS"
    assert report["reason"] == expected_reason
    if case == "runner-error":
        assert report["schema"] == "VST_S2_RUNTIME_MOUNT_AUDIT_OUTER_V1"
        assert report["terminal"] == "UNKNOWN"
        assert report["experiment_id"] == experiment_id
        assert report["outer_process"]["runner_error_type"] == "QualificationError"
        assert report["outer_process"]["unit_name"] == harness._transient_unit_name(experiment_id)
    else:
        assert report["schema"] == "VST_S2_RUNTIME_MOUNT_AUDIT_V1"
        assert report["terminal"] == "HOLD"
        assert report["experiment_id"] == experiment_id
    assert list(tmp_path.rglob("*")) == []


def _approved_mountinfo() -> str:
    return "\n".join((
        "36 25 8:1 / / rw,relatime - ext4 /dev/sda1 rw,errors=remount-ro",
        "37 36 0:4 / /proc rw,nosuid,nodev,noexec,relatime - proc proc rw",
        "38 36 0:5 / /sys rw,nosuid,nodev,noexec,relatime - sysfs sysfs rw",
        "39 36 0:6 / /dev rw,nosuid - devtmpfs devtmpfs rw,size=65536k",
        "40 39 0:8 / /dev/pts rw,nosuid,noexec,relatime - devpts devpts rw,gid=5,mode=620",
        "41 36 0:30 / /sys/fs/cgroup rw,nosuid,nodev,noexec,relatime - cgroup2 cgroup2 rw",
        "42 36 0:27 / /run rw,nosuid,nodev - tmpfs tmpfs rw,size=65536k",
        "43 36 8:1 /run/systemd/inaccessible/dir /mnt rw,nosuid,nodev - ext4 /dev/sda1 rw",
        "44 36 0:44 / /usr/lib/modules rw,relatime - overlay none rw,lowerdir=/modules,ro",
    ))


@pytest.mark.parametrize("invalid", ["un correlated", "oversized"])
def test_bounded_or_unauthorized_input_refuses_before_wsl(monkeypatch, tmp_path, invalid):
    value: dict | bytes = _auth_input()
    if invalid == "un correlated":
        value["authorization"]["correlated"] = False
    else:
        value = b" " * (harness.MAX_INPUT_BYTES + 1)
    input_path, output_path = _write_input(tmp_path, value)
    called = []

    def unexpected_wsl(_script):
        called.append(True)
        pytest.fail("invalid authorization must be rejected before WSL")

    monkeypatch.setattr(harness, "_run_bounded_wsl", unexpected_wsl)
    with pytest.raises(harness.QualificationError):
        harness.run_once(input_path, output_path, root=tmp_path)

    assert called == []
    assert not output_path.exists()


def test_closed_identity_schema_requires_qualification_source_head():
    value = _auth_input()
    del value["identity"]["qualification_source_head"]

    with pytest.raises(harness.QualificationError, match="identity.*fields"):
        harness.validate_input(value)


def test_operator_authorization_accepts_only_exact_one_shot_req003_contract():
    value = _operator_auth_input()

    validated = harness.validate_input(value)

    assert validated["authorization"] == {
        "source": "OPERATOR",
        "request_id": "operator-s2-4d-req003-20261106-01",
        "operator_principal": "operator",
        "operator_statement_sha256": value["authorization"]["operator_statement_sha256"],
        "verdict": "AUTHORIZE_ONE_SHOT",
        "retry_cap": 0,
        "allowed_operation": "S2-4_OWNER_RUNNER_TESTRUN",
    }
    assert validated["identity"]["selector_test_id"] == harness.OPERATOR_REQ003_SELECTOR
    assert "reply_id" not in validated["authorization"]
    assert "payload_sha256" not in validated["authorization"]


@pytest.mark.parametrize("mutation", [
    "wrong-statement-digest",
    "retry-enabled",
    "wrong-operation",
    "wrong-selector",
    "mixed-pm-metadata",
])
def test_operator_authorization_rejects_scope_or_provenance_widening(mutation):
    value = _operator_auth_input()
    if mutation == "wrong-statement-digest":
        value["authorization"]["operator_statement_sha256"] = "0" * 64
    elif mutation == "retry-enabled":
        value["authorization"]["retry_cap"] = 1
    elif mutation == "wrong-operation":
        value["authorization"]["allowed_operation"] = "S2-4_ANY_TEST"
    elif mutation == "wrong-selector":
        value["identity"]["selector_test_id"] = (
            "tests/vst/test_s2_runtime_qualification_harness.py::test_runtime_handoff_contract"
        )
    else:
        value["authorization"]["reply_id"] = "invented-pm-reply-0123456789"

    with pytest.raises(harness.QualificationError):
        harness.validate_input(value)


def test_pm_bridge_authorization_contract_remains_unchanged():
    value = _auth_input()

    validated = harness.validate_input(value)

    assert validated["authorization"]["source"] == "PM_BRIDGE"
    assert validated["authorization"]["request_id"] == "2" * 32
    assert validated["authorization"]["reply_id"] == "reply-0123456789abcdef"
    assert validated["authorization"]["retry_cap"] == 0


def test_qualification_source_pins_cover_exactly_the_two_launcher_paths():
    value = _auth_input()
    value["source_pins"]["qualification"]["tools/qa/unapproved.py"] = HEX

    with pytest.raises(harness.QualificationError,
                       match="qualification source pins must cover exactly the two launcher files"):
        harness.validate_input(value)


def test_git_source_inspection_uses_canonical_lf_archive_under_hostile_config(
        hostile_git_archive_fixture, monkeypatch):
    fixture = hostile_git_archive_fixture
    repo = fixture["repo"]
    archive_args = ["archive", "--format=tar", fixture["head"], "--",
                    *fixture["archive_paths"]]
    explicit_argv = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
                     "-C", str(repo), "--no-replace-objects", *archive_args]
    real_run = subprocess.run
    explicit = real_run(explicit_argv, cwd=repo, env=dict(os.environ),
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    assert explicit.returncode == 0, explicit.stderr.decode("utf-8", "replace")
    canonical_archive = explicit.stdout
    before = {
        "global_config": fixture["global_config"].read_bytes(),
        "local_config": fixture["local_config"].read_bytes(),
        "attributes": fixture["attributes"].read_bytes(),
        "global_path": os.environ["GIT_CONFIG_GLOBAL"],
        "system_path": os.environ["GIT_CONFIG_SYSTEM"],
    }
    helper_git_argv = []

    def capture_git_argv(argv, *args, **kwargs):
        if isinstance(argv, (list, tuple)) and argv and argv[0] == "git":
            helper_git_argv.append(list(argv))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(harness.subprocess, "run", capture_git_argv)
    helper_archive = harness._git(
        repo, *archive_args, maximum=64 * 1024 * 1024)

    assert helper_archive == canonical_archive
    with tarfile.open(fileobj=io.BytesIO(helper_archive), mode="r:") as bundle:
        contracts = bundle.extractfile("tools/vst/contracts.py").read()
    assert contracts == fixture["runtime_files"]["tools/vst/contracts.py"]
    assert b"\r\n" not in contracts
    assert helper_git_argv
    assert all(argv[1:5] == ["-c", "core.autocrlf=false", "-c", "core.eol=lf"]
               for argv in helper_git_argv)

    pins = _runtime_pins_from_archive(helper_archive)
    assert len(pins) == 47
    _value, validated = _validated_archive_input(
        fixture, helper_archive, pins)
    harness.verify_source_pins(repo, validated)

    assert fixture["global_config"].read_bytes() == before["global_config"]
    assert fixture["local_config"].read_bytes() == before["local_config"]
    assert fixture["attributes"].read_bytes() == before["attributes"]
    assert os.environ["GIT_CONFIG_GLOBAL"] == before["global_path"]
    assert os.environ["GIT_CONFIG_SYSTEM"] == before["system_path"]


def test_source_pin_verification_requires_exact_full_archive_closure(
        hostile_git_archive_fixture):
    fixture = hostile_git_archive_fixture
    archive = harness._git(
        fixture["repo"], "archive", "--format=tar", fixture["head"], "--",
        *fixture["archive_paths"], maximum=64 * 1024 * 1024)
    complete_pins = _runtime_pins_from_archive(archive)
    assert len(complete_pins) == 47

    reduced_to_minimum = {
        path: complete_pins[path] for path in harness.REQUIRED_RUNTIME_PINS
    }
    extra_pin = {**complete_pins, "tools/vst/not-in-archive.py": "f" * 64}
    tampered_pin = dict(complete_pins)
    tampered_pin[next(iter(harness.REQUIRED_RUNTIME_PINS))] = "0" * 64
    variants = {
        "minimum-only": reduced_to_minimum,
        "extra-path": extra_pin,
        "wrong-digest": tampered_pin,
    }
    for _label, runtime_pins in variants.items():
        _value, validated = _validated_archive_input(fixture, archive, runtime_pins)
        with pytest.raises(harness.QualificationError,
                           match="runtime source pins do not exactly cover the reviewed source archive"):
            harness.verify_source_pins(fixture["repo"], validated)


def test_source_pin_verification_accepts_exact_archive_and_rejects_worktree_drift(
        monkeypatch, tmp_path):
    launchers = {OUTER_HELPER, WSL_HELPER}
    archived_files = _runtime_archive_fixture_files()
    launcher_files = {
        OUTER_HELPER: b"# exact committed outer launcher\n",
        WSL_HELPER: b"# exact committed WSL helper\n",
    }
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:") as archive:
        for name, data in archived_files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    archive_bytes = archive_buffer.getvalue()

    value = _auth_input(streamed_wsl=launcher_files[WSL_HELPER])
    value["identity"]["bundle_sha256"] = _sha(archive_bytes)
    for path, data in archived_files.items():
        value["source_pins"]["runtime"][path] = _sha(data)
    value["source_pins"]["qualification"] = {
        path: _sha(data) for path, data in launcher_files.items()
    }
    assert not (set(value["source_pins"]["runtime"]) & launchers)
    assert set(value["source_pins"]["runtime"]) == set(archived_files)
    assert set(value["source_pins"]["qualification"]) == launchers
    for path, data in launcher_files.items():
        target = tmp_path / Path(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    validated = harness.validate_input(value)

    def fake_git(_root, *args, **_kwargs):
        if args[0] == "rev-parse":
            revision = args[-1]
            if revision == "HEAD":
                return (QUALIFICATION_HEAD + "\n").encode("ascii")
            return (RUNTIME_HEAD + "\n").encode("ascii")
        if args[0] == "archive":
            return archive_bytes
        if args[0] == "show":
            revision, path = args[1].split(":", 1)
            assert revision == QUALIFICATION_HEAD
            return launcher_files[path]
        pytest.fail(f"unexpected Git command: {args!r}")

    monkeypatch.setattr(harness, "_git", fake_git)
    harness.verify_source_pins(tmp_path, validated)

    (tmp_path / Path(*WSL_HELPER.split("/"))).write_bytes(b"tampered helper\n")
    with pytest.raises(harness.QualificationError, match="differs from its exact committed Git blob"):
        harness.verify_source_pins(tmp_path, validated)


def test_wrong_expected_qualification_head_refuses_before_attempt_or_wsl(
        monkeypatch, tmp_path):
    archived_files = _runtime_archive_fixture_files()
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w:") as archive:
        for name, data in archived_files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    archive_bytes = archive_buffer.getvalue()
    launcher_files = {
        OUTER_HELPER: b"# committed outer launcher\n",
        WSL_HELPER: b"# committed WSL launcher\n",
    }
    value = _auth_input(streamed_wsl=launcher_files[WSL_HELPER])
    value["identity"]["bundle_sha256"] = _sha(archive_bytes)
    value["source_pins"]["runtime"] = {
        path: _sha(data) for path, data in archived_files.items()
    }
    value["source_pins"]["qualification"] = {
        path: _sha(data) for path, data in launcher_files.items()
    }
    value["identity"]["qualification_source_head"] = "c" * 40
    input_path, output_path = _write_input(tmp_path, value)
    wsl_calls = []

    def fake_git(_root, *args, **_kwargs):
        if args[0] == "rev-parse":
            revision = args[-1]
            return ((QUALIFICATION_HEAD if revision == "HEAD" else RUNTIME_HEAD)
                    + "\n").encode("ascii")
        if args[0] == "archive":
            return archive_bytes
        pytest.fail(f"unexpected Git command: {args!r}")

    monkeypatch.setattr(harness, "_git", fake_git)
    monkeypatch.setattr(harness, "_run_bounded_wsl", lambda *_args: wsl_calls.append(True))

    with pytest.raises(harness.QualificationError,
                       match="qualification source HEAD differs from the authorized exact repository HEAD"):
        harness.run_once(input_path, output_path, root=tmp_path)

    assert not output_path.exists()
    assert wsl_calls == []


def test_run_once_starts_one_mock_wsl_child_and_persists_terminal_hold(
        monkeypatch, tmp_path, capsys):
    script = MOCK_WSL_SOURCE
    value = _auth_input(streamed_wsl=script)
    input_path, output_path = _write_input(tmp_path, value)
    monkeypatch.setattr(harness, "verify_source_pins", lambda *_args: None)
    monkeypatch.setattr(harness, "refuse_historical_identity", lambda *_args: None)
    monkeypatch.setattr(harness, "_load_wsl_script", lambda: script)

    calls = []
    captured_inputs = []

    class CapturedInput:
        def __init__(self):
            self.data = bytearray()
            self.closed = False

        def write(self, data):
            self.data.extend(data)
            return len(data)

        def flush(self):
            pass

        def close(self):
            self.closed = True

    class MockWslProcess:
        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))
            self.stdin = CapturedInput()
            captured_inputs.append(self.stdin)
            self.stdout = io.BytesIO(FAILURE_PROTOCOL)
            self.stderr = io.BytesIO(b"synthetic stderr")
            self.returncode = 2

        def wait(self, *, timeout):
            assert timeout == 2400 + harness.SYSTEMD_STARTUP_SHUTDOWN_GRACE_SEC
            return self.returncode

    monkeypatch.setattr(harness.subprocess, "Popen", MockWslProcess)

    exit_code = harness.run_once(input_path, output_path, root=tmp_path)

    assert exit_code == 2
    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv[:3] == ["wsl.exe", "--distribution", harness.WSL_DISTRIBUTION]
    assert kwargs["close_fds"] is True
    assert len(calls[0][1:]) == 1
    injected_script = bytes(captured_inputs[0].data)
    compile(injected_script, "<mock-runtime-script>", "exec")
    runtime_tree = ast.parse(injected_script.decode("ascii"))
    runtime_mode = next(ast.literal_eval(node.value) for node in runtime_tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name)
                                and target.id == "MOUNT_AUDIT_ONLY" for target in node.targets))
    assert runtime_mode is False
    assert injected_script.index(b"from __future__ import annotations\n") < injected_script.index(
        b'AUTH = "{')
    assert injected_script.count(b"AUTH = json.loads(AUTH)\n") == 1
    assert injected_script.index(b"AUTH = json.loads(AUTH)\n") > injected_script.index(
        b'AUTH = "{')
    attempt = json.loads(output_path.read_text(encoding="utf-8"))
    assert attempt["state"] == "HOLD"
    assert attempt["protocol"]["terminal"] == "HOLD"
    assert attempt["retry"] == "PROHIBITED"
    assert attempt["retry_cap"] == 0
    assert attempt["stdout_sha256"] == _sha(FAILURE_PROTOCOL)
    assert attempt["stderr_sha256"] == _sha(b"synthetic stderr")
    assert capsys.readouterr().out


def test_operator_one_shot_run_records_provenance_and_refuses_replay(
        monkeypatch, tmp_path, capsys):
    script = MOCK_WSL_SOURCE
    value = _operator_auth_input(streamed_wsl=script)
    input_path, default_output_path = _write_input(tmp_path, value)
    output_path = default_output_path.with_name("s2-runtime-qual-operator-001.attempt.json")
    monkeypatch.setattr(harness, "verify_source_pins", lambda *_args: None)
    monkeypatch.setattr(harness, "_load_wsl_script", lambda: script)
    calls = []

    def fake_wsl(injected_script, *, unit_name, runtime_max_sec):
        calls.append((injected_script, unit_name, runtime_max_sec))
        return {
            "exit_code": 2,
            "timed_out": False,
            "writer_error": None,
            "unit_name": unit_name,
            "runtime_max_sec": runtime_max_sec,
            "systemd_properties": ["RuntimeMaxSec=2400"],
            "stdout": {
                "bytes": len(FAILURE_PROTOCOL), "sha256": _sha(FAILURE_PROTOCOL),
                "prefix": FAILURE_PROTOCOL, "truncated": False,
            },
            "stderr": {
                "bytes": 0, "sha256": _sha(b""),
                "prefix": b"", "truncated": False,
            },
        }

    monkeypatch.setattr(harness, "_run_bounded_wsl", fake_wsl)

    exit_code = harness.run_once(input_path, output_path, root=tmp_path)

    assert exit_code == 2
    assert len(calls) == 1
    injected_tree = ast.parse(calls[0][0].decode("ascii"))
    auth_literal = next(ast.literal_eval(node.value) for node in injected_tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == "AUTH"
                                for target in node.targets))
    injected = json.loads(auth_literal)
    assert injected["authorization"] == harness.validate_input(value)["authorization"]
    assert "reply_id" not in injected["authorization"]

    attempt = json.loads(output_path.read_text(encoding="utf-8"))
    assert attempt["authorization_source"] == "OPERATOR"
    assert attempt["authorization_request_id"] == "operator-s2-4d-req003-20261106-01"
    assert attempt["authorization_reply_id"] is None
    assert attempt["authorization_operator_reference"] == "operator"
    assert attempt["authorization_operator_statement_sha256"] == value[
        "authorization"]["operator_statement_sha256"]
    assert attempt["identity"]["selector_test_id"] == harness.OPERATOR_REQ003_SELECTOR
    assert attempt["retry_cap"] == 0

    replay_output = output_path.with_name("attempt-replay.json")
    with pytest.raises(harness.QualificationError,
                       match="authorization reuses an identity present"):
        harness.run_once(input_path, replay_output, root=tmp_path)
    assert len(calls) == 1
    assert not replay_output.exists()
    assert capsys.readouterr().out


@pytest.mark.parametrize("unsupported", [1, None, [], {}])
def test_pm08_python_literal_refuses_unsupported_value_types(unsupported):
    with pytest.raises(harness.QualificationError, match="no safe Python literal encoding"):
        harness._python_literal(unsupported)


def test_wsl_mount_allowlist_accepts_only_expected_mounts(monkeypatch):
    functions = _wsl_prestart_functions()
    mountinfo, _ = _complete_mountinfo(functions["TRANSIENT_UNIT"])
    rows, windows_mounts, unapproved_mounts = functions["_decode_mountinfo"](
        mountinfo, expected_unit=functions["TRANSIENT_UNIT"])

    assert len(rows) > 9
    assert windows_mounts == []
    assert unapproved_mounts == []


@pytest.mark.parametrize(("label", "extra", "reason"), [
    ("unknown host filesystem",
     "80 36 8:2 / /srv/host rw,relatime - ext4 /dev/sdb1 rw",
     "unapproved host mount detected"),
    ("Windows drive under /mnt",
     "80 36 0:55 / /mnt/c rw,relatime - 9p C:\\ aname=drvfs;path=C:\\;symlinkroot=/mnt/",
     "Windows drive mount detected"),
    ("unsupported proc source",
     "80 36 0:4 / /proc/host rw,relatime - proc hostproc rw",
     "unapproved host mount detected"),
    ("mismatched bind mount root",
     "80 36 8:1 /etc /srv/host rw,relatime - ext4 /dev/sda1 rw",
     "unapproved host mount detected"),
    ("overlay with an unapproved prefixed target",
     "80 36 0:55 / /srv/unapproved/usr/lib/modules ro,relatime - overlay none ro,lowerdir=/modules",
     "unapproved host mount detected"),
])
def test_wsl_prestart_refuses_unapproved_mounts(monkeypatch, label, extra, reason):
    functions = _wsl_prestart_functions()
    mountinfo, _ = _complete_mountinfo(functions["TRANSIENT_UNIT"])
    mountinfo += "\n" + extra

    original_read_bytes = pathlib.Path.read_bytes

    def read_bytes(path, *args, **kwargs):
        if path.as_posix() == "/proc/self/mountinfo":
            return mountinfo.encode("utf-8")
        return original_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_bytes", read_bytes)
    with pytest.raises(functions["Hold"]):
        functions["_prestart_inventory"]({})

    assert functions["R"]["terminal"] == "HOLD", label
    assert reason in functions["R"]["reason"], label


def test_unknown_protocol_persists_indeterminate_record_without_retry(
        monkeypatch, tmp_path):
    script = MOCK_WSL_SOURCE
    unknown_protocol = b'{"schema":"VST_S2_RUNTIME_QUALIFICATION_PROTOCOL_V999"}'
    value = _auth_input(streamed_wsl=script)
    input_path, output_path = _write_input(tmp_path, value)
    monkeypatch.setattr(harness, "verify_source_pins", lambda *_args: None)
    monkeypatch.setattr(harness, "refuse_historical_identity", lambda *_args: None)
    monkeypatch.setattr(harness, "_load_wsl_script", lambda: script)

    calls = []

    def one_wsl_attempt(_script, **_kwargs):
        calls.append(True)
        return {
            "exit_code": 2,
            "timed_out": False,
            "writer_error": None,
            "stdout": {"bytes": len(unknown_protocol), "sha256": _sha(unknown_protocol),
                       "prefix": unknown_protocol, "truncated": False},
            "stderr": {"bytes": 0, "sha256": _sha(b""),
                       "prefix": b"", "truncated": False},
        }

    monkeypatch.setattr(harness, "_run_bounded_wsl", one_wsl_attempt)

    with pytest.raises(harness.QualificationError, match="unrecognized protocol"):
        harness.run_once(input_path, output_path, root=tmp_path)

    attempt = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(calls) == 1
    assert attempt["state"] == "INDETERMINATE"
    assert attempt["exit_code"] == 2
    assert attempt["stdout_bytes"] == len(unknown_protocol)
    assert attempt["stdout_sha256"] == _sha(unknown_protocol)
    assert attempt["stderr_bytes"] == 0
    assert attempt["stderr_sha256"] == _sha(b"")
    assert attempt["retry"] == "PROHIBITED"
    assert attempt["retry_cap"] == 0


def _report_bound_test_run_fixture(monkeypatch, receipt_mutation=None):
    wait_for_test_run, namespace, hold_type = _wsl_test_run_function()
    task_id = "S2-4-runtime-owner-runner-qualification"
    selector = (
        "tests/vst/test_s2_assignment_basis.py::"
        "test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment"
    )
    task_source_head = "9" * 40
    qualification_source_head = "a" * 40
    manifest_sha256 = "8" * 64
    service_generation = "generation-0123456789abcdef"
    identity = {
        "runtime_selector": "/opt/vst-runtime-" + RUNTIME_HEAD,
        "qualification_source_head": qualification_source_head,
        "run_id": "run-0123456789abcdef",
        "task_manifest_sha256": manifest_sha256,
        "selector_test_id": selector,
    }
    instruction = {"request_id": "request-0123456789abcdef"}
    grant = {
        "grant_id": "grant-0123456789abcdef",
        "invocation_id": "invocation-0123456789abcdef",
        "request_id": instruction["request_id"],
        "task_id": task_id,
        "slot": "runtime-tests",
        "runner_id": "runner-1",
        "attempt": 1,
        "epoch": 3,
        "run_id": identity["run_id"],
        "service_generation": service_generation,
        "manifest_sha256": manifest_sha256,
    }
    grant_bytes = namespace["canonical_bytes"](grant)
    grant_digest = _sha(grant_bytes)
    claim = {
        **{key: grant[key] for key in (
            "grant_id", "invocation_id", "request_id", "task_id", "slot",
            "runner_id", "attempt", "epoch", "run_id", "service_generation",
            "manifest_sha256",
        )},
        "payload_sha256": grant_digest,
        "grant_body": json.dumps(grant),
        "claimed_at": "2026-11-04T00:00:00Z",
    }
    pending = {
        "event": "RUNNER_EXECUTION_PENDING", "state": "PENDING",
        "grant_id": grant["grant_id"], "invocation_id": grant["invocation_id"],
        "request_id": grant["request_id"], "task_id": grant["task_id"],
        "slot": grant["slot"], "runner_id": grant["runner_id"],
        "attempt": grant["attempt"], "epoch": grant["epoch"],
        "service_generation": grant["service_generation"],
        "run_id": grant["run_id"], "payload_sha256": grant_digest,
    }
    events = [{"state": "PENDING", "payload": json.dumps(pending)}]

    receipt = {
        "receipt_type": "TestRun", "result": "PASS", "task_id": task_id,
        "slot": "runtime-tests", "attempt": 1,
        "candidate_head": task_source_head, "run_id": identity["run_id"],
        "manifest_sha256": manifest_sha256,
        "diff_gate": {
            "verdict": "PASS", "candidate_head": task_source_head,
            "manifest_sha256": manifest_sha256,
        },
        "runner_attestation": {"request": {
            "candidate_head": task_source_head,
            "manifest_sha256": manifest_sha256,
        }},
        "expected_test_ids": [selector], "executed_test_ids": [selector],
        "skipped_test_ids": [], "xfail_test_ids": [],
    }
    if receipt_mutation is not None:
        path, value = receipt_mutation
        target = receipt
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = value
    receipt_bytes = namespace["canonical_bytes"](receipt)
    receipt_row = {
        "body": json.dumps(receipt),
        "receipt_sha256": _sha(receipt_bytes),
    }

    class FakeSupervisorClient:
        def __init__(self, _socket_path):
            pass

        def generation(self):
            return service_generation

        def claim_status(self, _grant):
            return {"service_generation": service_generation, "state": "PENDING"}

    namespace["SupervisorClient"] = FakeSupervisorClient
    namespace["_read_task_rows"] = lambda _store_path, _task: (
        [claim], events, [receipt_row],
    )
    result = (wait_for_test_run(
        {"store_path": "/tmp/store.sqlite3"},
        {"task_id": task_id, "timeout_sec": 1, "base_head": task_source_head},
        instruction, identity,
    ), namespace, hold_type, receipt)
    return result


def test_report_bound_test_run_accepts_exact_candidate_and_manifest_tuple(monkeypatch):
    result, namespace, _hold_type, expected_receipt = _report_bound_test_run_fixture(monkeypatch)

    assert result == expected_receipt
    assert result["candidate_head"] == "9" * 40  # TaskManifest.base_head
    assert result["candidate_head"] != "a" * 40  # qualification_source_head
    assert namespace["R"]["stages"]["test_run"]["verdict"] == "PASS"


@pytest.mark.parametrize(("field", "invalid_value"), [
    ("candidate_head", "7" * 40),
    ("diff_gate.candidate_head", "7" * 40),
    ("runner_attestation.request.candidate_head", "7" * 40),
    ("manifest_sha256", "7" * 64),
    ("diff_gate.manifest_sha256", "7" * 64),
    ("runner_attestation.request.manifest_sha256", "7" * 64),
    ("diff_gate.verdict", "FAIL"),
])
def test_report_bound_test_run_refuses_mismatched_identity_or_nonpass_diff_gate(
        monkeypatch, field, invalid_value):
    with pytest.raises(_wsl_test_run_function()[2],
                       match="one report-bound TestRun did not produce the exact authorized PASS receipt"):
        _report_bound_test_run_fixture(monkeypatch, (field, invalid_value))
