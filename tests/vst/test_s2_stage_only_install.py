"""Isolated preflight checks extracted from the committed Windows/WSL stage-only scripts."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _powershell_bootstrap() -> str:
    script = (ROOT / "tools/qa/install_wsl_runtime.ps1").read_text(encoding="utf-8")
    match = re.search(r"\$bootstrap = @'\r?\n(.*?)\r?\n'@", script, re.DOTALL)
    assert match, "committed Windows handoff must retain one embedded bounded Python program"
    return match.group(1)


def _stage_guard(source: str = "host") -> ast.If | ast.Module:
    if source == "host":
        module = ast.parse(_powershell_bootstrap())
        matches = [node for node in module.body if isinstance(node, ast.If)
                   and isinstance(node.test, ast.Name) and node.test.id == "stage_only"]
        assert matches
        return min(matches, key=lambda node: node.lineno)

    assert source == "wsl"
    shell = (ROOT / "tools/qa/install_wsl_runner_runtime.sh").read_text(encoding="utf-8")
    snippets = re.findall(r"<<'PY'\r?\n(.*?)\r?\nPY", shell, re.DOTALL)
    for snippet in snippets:
        try:
            module = ast.parse(snippet)
        except SyntaxError:
            continue
        if ("validate_root_config_directory" not in snippet
                or "systemctl" not in snippet or "ControlGroup" not in snippet):
            continue
        units_index = next(
            index for index, node in enumerate(module.body)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "units"
                    for target in node.targets)
        )
        return ast.Module(body=module.body[units_index:], type_ignores=[])
    raise AssertionError("WSL stage-only systemd preflight Python block was not found")


def _run_guard(tmp_path: Path, *, configured: str | None = None,
               active_unit: str | None = None, jobs: str = "",
               populated_unit: str | None = None, guard_source: str = "host") -> None:
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir(exist_ok=True)
    units = (
        "vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
        "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
        "vst-dispatcher.service", "vst-runner.service",
        "vst-sandbox-probe.service", "vst-signer.service", "vst-supervisor.service",
    )
    for unit in units:
        group = cgroup_root / "system.slice" / unit
        group.mkdir(parents=True, exist_ok=True)
        (group / "cgroup.events").write_text(
            "populated " + ("1" if unit == populated_unit else "0") + "\nfrozen 0\n", encoding="ascii")

    class FakePath:
        @staticmethod
        def lexists(path: str) -> bool:
            return configured is not None and path == configured

        @staticmethod
        def join(left: str, right: str) -> str:
            if left == "/sys/fs/cgroup":
                return str(cgroup_root / right)
            return os.path.join(left, right)

        @staticmethod
        def isdir(path: str) -> bool:
            return Path(path).is_dir()

        @staticmethod
        def islink(path: str) -> bool:
            return Path(path).is_symlink()

    def fake_run(argv, **_kwargs):
        if argv[1] == "show" and "LoadState" in argv[2]:
            return SimpleNamespace(returncode=0, stdout="loaded\n")
        if argv[1] == "show" and "ActiveState" in argv[2]:
            return SimpleNamespace(returncode=0,
                                   stdout=("activating\n" if argv[-1] == active_unit else "inactive\n"))
        if argv[1] == "show" and "ControlGroup" in argv[2]:
            return SimpleNamespace(returncode=0, stdout="/system.slice/" + argv[-1] + "\n")
        if argv[1] == "list-jobs":
            return SimpleNamespace(returncode=0, stdout=jobs)
        raise AssertionError("unexpected systemctl command shape: " + repr(argv))

    fake_os = SimpleNamespace(path=FakePath, walk=os.walk)
    fake_subprocess = SimpleNamespace(run=fake_run, DEVNULL=-3, PIPE=-1)
    guard = _stage_guard(guard_source)
    body = guard.body if isinstance(guard, ast.Module) else [guard]
    namespace = {"stage_only": True, "units": units, "os": fake_os,
                 "subprocess": fake_subprocess, "SystemExit": SystemExit}
    exec(compile(ast.Module(body=body, type_ignores=[]), "stage-only-preflight", "exec"), namespace)


def test_embedded_python_programs_are_syntactically_valid():
    ast.parse(_powershell_bootstrap())
    shell = (ROOT / "tools/qa/install_wsl_runner_runtime.sh").read_text(encoding="utf-8")
    snippets = re.findall(r"<<'PY'\r?\n(.*?)\r?\nPY", shell, re.DOTALL)
    assert snippets
    for snippet in snippets:
        ast.parse(snippet)


def test_python_c_sys_argv_matches_host_argument_contract():
    head = "a" * 40
    plan_digest = "b" * 64
    inventory_digest = "e" * 64
    transfer_id = "c" * 32
    stage_only = "1"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c",
         "import json,sys; head,plan_digest,inventory_digest,transfer_id=sys.argv[1:5]; stage_only=sys.argv[5]; "
         "print(json.dumps(sys.argv))",
         head, plan_digest, inventory_digest, transfer_id, stage_only],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == ["-c", head, plan_digest, inventory_digest,
                                         transfer_id, stage_only]


def test_host_handoff_binds_inventory_path_digest_and_timestamp_from_reviewed_plan() -> None:
    script = (ROOT / "tools/qa/install_wsl_runtime.ps1").read_text(encoding="utf-8")

    assert '$inventoryRelativePath = [string]$sourcePlan.target_inventory.path' in script
    assert "^docs/sdlc/evidence/[A-Za-z0-9._-]+\\.json$" in script
    assert "(^|/)\\.\\.?(/|$)" in script
    assert "$sourcePlan.target_inventory.sha256 -cne $ExpectedInventorySha256" in script
    assert '"HEAD:$inventoryRelativePath"' in script
    assert "[string]$targetInventory.observed_utc -cne [string]$sourcePlan.target_inventory.observed_utc" in script
    assert 's2-runtime-target-inventory-$ExpectedHead.json' not in script


def _host_source_import_flags() -> list[str]:
    script = (ROOT / "tools/qa/install_wsl_runtime.ps1").read_text(encoding="utf-8")
    match = re.search(
        r"\$wslStart\.FileName = \$wsl\s*.*?"
        r"foreach \(\$argument in @\(\s*(.*?)\s*\)\)\s*\{\s*"
        r"\[void\]\$wslStart\.ArgumentList\.Add\(\$argument\)",
        script,
        re.DOTALL,
    )
    assert match, "host WSL process must keep its explicit argument list"
    arguments = re.findall(r"'([^']*)'", match.group(1))
    python_index = arguments.index("/usr/bin/python3.12")
    flags = arguments[python_index + 1:python_index + 4]
    assert flags == ["-I", "-B", "-S"], (
        "the host StageOnly package import must disable bytecode writes before exact bundle re-verification"
    )
    return flags


def _wsl_source_import_flags() -> list[str]:
    script = (ROOT / "tools/qa/install_wsl_runner_runtime.sh").read_text(encoding="utf-8")
    match = re.search(
        r"/usr/bin/python3\.12(?P<flags>(?:\s+-[A-Za-z]+)+)\s+-\s+\"\$bundle_root\" <<'PY'",
        script,
    )
    assert match, "WSL StageOnly must retain the bounded source-bundle validation program"
    flags = match.group("flags").split()
    assert flags == ["-I", "-B", "-S"], (
        "the WSL StageOnly package import must disable bytecode writes before exact bundle re-verification"
    )
    return flags


@pytest.mark.parametrize(
    ("path", "flags"),
    [
        ("host bootstrap", _host_source_import_flags),
        ("WSL StageOnly guard", _wsl_source_import_flags),
    ],
)
def test_stage_only_runtime_bundle_import_does_not_change_exact_source_members(
    tmp_path: Path, path: str, flags,
) -> None:
    bundle = tmp_path / "source-bundle"
    package = bundle / "tools" / "vst"
    package.mkdir(parents=True)
    (bundle / "tools" / "__init__.py").write_text("", encoding="ascii")
    (package / "__init__.py").write_text("", encoding="ascii")
    (package / "contracts.py").write_text("CONTRACT = True\n", encoding="ascii")
    (package / "runtime_bundle.py").write_text(
        "from .contracts import CONTRACT\n"
        "def validate_root_config_directory(path):\n"
        "    return CONTRACT and path == '/etc/vst-runner'\n",
        encoding="ascii",
    )
    expected_members = {
        "tools", "tools/__init__.py", "tools/vst", "tools/vst/__init__.py",
        "tools/vst/contracts.py", "tools/vst/runtime_bundle.py",
    }

    result = subprocess.run(
        [sys.executable, *flags(), "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); "
         "from tools.vst.runtime_bundle import validate_root_config_directory; "
         "assert validate_root_config_directory('/etc/vst-runner')",
         str(bundle)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"{path} StageOnly import failed: {result.stderr}"
    actual_members = {item.relative_to(bundle).as_posix() for item in bundle.rglob("*")}
    assert actual_members == expected_members, (
        f"{path} StageOnly import changed the exact source bundle member set"
    )


def _runner_main_python() -> str:
    shell = (ROOT / "tools/qa/install_wsl_runner_runtime.sh").read_text(encoding="utf-8")
    snippets = re.findall(r"<<'PY'\r?\n(.*?)\r?\nPY", shell, re.DOTALL)
    for snippet in snippets:
        try:
            module = ast.parse(snippet)
        except SyntaxError:
            continue
        unpacks_inventory = any(
            isinstance(node, ast.Assign)
            and node.targets and isinstance(node.targets[0], ast.Tuple)
            and any(isinstance(item, ast.Name) and item.id == "inventory_sha"
                    for item in node.targets[0].elts)
            for node in module.body
        )
        checks_existing_runtime = any(
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Name)
            and node.test.func.id == "path_exists"
            and len(node.test.args) == 1
            and isinstance(node.test.args[0], ast.Name)
            and node.test.args[0].id == "runtime"
            for node in module.body
        )
        if unpacks_inventory and checks_existing_runtime:
            return snippet
    raise AssertionError("runtime-validation heredoc with inventory pin was not found")


def test_runner_existing_runtime_argv_pins_inventory_at_matching_position() -> None:
    shell = (ROOT / "tools/qa/install_wsl_runner_runtime.sh").read_text(encoding="utf-8")
    assert re.search(
        r"""python3\.12 -I -S - "\$stage" "\$runtime_dir" "\$runtime_link" "\$unit_dir" "\$expected_head" "\$archive_sha" "\$stage_only" "\$plan_sha" "\$inventory_sha" "\$bundle_root" <<'PY'""",
        shell,
    )
    module = ast.parse(_runner_main_python())
    assignments = [node for node in module.body if isinstance(node, ast.Assign)
                   and node.targets and isinstance(node.targets[0], ast.Tuple)]
    unpack = next(node for node in assignments
                  if any(isinstance(item, ast.Name) and item.id == "inventory_sha"
                         for item in node.targets[0].elts))
    names = [item.id for item in unpack.targets[0].elts]
    assert names == ["stage", "runtime", "link", "unit_dir", "head", "digest",
                     "stage_only", "plan_sha", "inventory_sha", "bundle_root"]


def _existing_runtime_branch() -> ast.Module:
    module = ast.parse(_runner_main_python())
    index = next(
        index for index, node in enumerate(module.body)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Call)
        and isinstance(node.test.func, ast.Name)
        and node.test.func.id == "path_exists"
        and len(node.test.args) == 1
        and isinstance(node.test.args[0], ast.Name)
        and node.test.args[0].id == "runtime"
    )
    return ast.Module(body=module.body[:index + 1], type_ignores=[])


def _write_fixture_file(path: Path, payload: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    path.chmod(mode)


def _run_existing_runtime_branch(tmp_path: Path, marker_changes: dict | None = None) -> None:
    head = "a" * 40
    archive_sha = "b" * 64
    plan_sha = "c" * 64
    inventory_sha = "d" * 64
    compiler_sha = "e" * 64
    compiler = {
        "compiler_path": "/usr/bin/cc",
        "compiler_resolved_path": "/usr/bin/x86_64-linux-gnu-gcc-13",
        "compiler_sha256": compiler_sha,
        "compiler_symlink_target": "/etc/alternatives/cc",
    }
    source_files = {
        "tools/vst/runtime.py": b"runtime fixture",
        "docs/SANDBOX_SPEC.md": b"sandbox fixture",
    }
    members = {
        "tools": {"kind": "dir"},
        "tools/vst": {"kind": "dir"},
        "docs": {"kind": "dir"},
        **{
            name: {"kind": "file", "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}
            for name, payload in source_files.items()
        },
    }
    bundle_root = tmp_path / "bundle"
    bundle_root.mkdir()
    (bundle_root / ".vst-source-manifest.json").write_text(
        json.dumps({"archive_members": members, **compiler}, sort_keys=True), encoding="ascii")
    stage = tmp_path / "stage"
    runtime = tmp_path / "runtime"
    for root in (stage, runtime):
        root.mkdir(mode=0o755)
        for name, payload in source_files.items():
            _write_fixture_file(root / name, payload)
        for directory in (root / "tools", root / "tools/vst", root / "docs"):
            directory.mkdir(parents=True, exist_ok=True)
            directory.chmod(0o755)
        root.chmod(0o755)
    expected_marker = {
        "archive_sha256": archive_sha,
        **compiler,
        "head": head,
        "inventory_sha256": inventory_sha,
        "plan_sha256": plan_sha,
        "schema": 3,
    }
    _write_fixture_file(stage / ".vst-runtime-manifest.json",
                        json.dumps(expected_marker, sort_keys=True).encode("ascii"))
    actual_marker = {**expected_marker, **(marker_changes or {})}
    _write_fixture_file(runtime / ".vst-runtime-manifest.json",
                        json.dumps(actual_marker, sort_keys=True).encode("ascii"))
    argv = ["-", str(stage), str(runtime), str(tmp_path / "selector"), str(tmp_path / "units"),
            head, archive_sha, "1", plan_sha, inventory_sha, str(bundle_root)]
    previous_argv = sys.argv
    sys.argv = argv
    try:
        exec(compile(_existing_runtime_branch(), "existing-runtime-guard", "exec"), {})
    finally:
        sys.argv = previous_argv


@pytest.mark.skipif(
    os.name != "posix" or getattr(os, "geteuid", lambda: 1)() != 0,
    reason="existing-runtime validator requires root-owned POSIX fixtures",
)
def test_existing_runtime_accepts_matching_schema_three_provenance(tmp_path: Path) -> None:
    assert _run_existing_runtime_branch(tmp_path) is None


@pytest.mark.parametrize("field", ["inventory_sha256", "head"])
@pytest.mark.skipif(
    os.name != "posix" or getattr(os, "geteuid", lambda: 1)() != 0,
    reason="existing-runtime validator requires root-owned POSIX fixtures",
)
def test_existing_runtime_refuses_mismatched_schema_three_identity(
    tmp_path: Path, field: str,
) -> None:
    with pytest.raises(SystemExit, match="runtime destination manifest differs"):
        _run_existing_runtime_branch(tmp_path, {field: "f" * (40 if field == "head" else 64)})


@pytest.mark.parametrize("guard_source", ["host", "wsl"])
def test_stage_guard_accepts_complete_idle_inventory(tmp_path: Path, guard_source: str):
    assert _run_guard(tmp_path, guard_source=guard_source) is None


@pytest.mark.parametrize(("guard_source", "socket_path"), [
    ("host", "/run/vst-supervisor"),
    ("host", "/run/vst-runner"),
])
def test_stage_guard_refuses_existing_runtime_socket_path(
    tmp_path: Path, guard_source: str, socket_path: str,
):
    with pytest.raises(SystemExit, match="absent runtime socket paths"):
        _run_guard(tmp_path, configured=socket_path, guard_source=guard_source)


@pytest.mark.parametrize("guard_source", ["host", "wsl"])
def test_stage_guard_requires_exactly_inactive_state(tmp_path: Path, guard_source: str):
    with pytest.raises(SystemExit, match="loaded-inactive or not-found"):
        _run_guard(tmp_path, active_unit="vst-runner.service", guard_source=guard_source)


@pytest.mark.parametrize(("guard_source", "row"), [
    ("host", "1 vst-runner.service stop waiting\n"),
    ("host", "2 vst-dispatch-owner.socket start running\n"),
    ("wsl", "1 vst-runner.service stop waiting\n"),
    ("wsl", "2 vst-dispatch-owner.socket start running\n"),
])
def test_stage_guard_checks_systemd_unit_column_in_job_rows(
    tmp_path: Path, guard_source: str, row: str,
):
    with pytest.raises(SystemExit, match="no systemd job"):
        _run_guard(tmp_path, jobs=row, guard_source=guard_source)


@pytest.mark.parametrize("guard_source", ["host", "wsl"])
def test_stage_guard_refuses_populated_service_cgroup(tmp_path: Path, guard_source: str):
    with pytest.raises(SystemExit, match="empty S2 service cgroups"):
        _run_guard(tmp_path, populated_unit="vst-signer.service", guard_source=guard_source)


@pytest.mark.parametrize(("guard_source", "unit"), [
    (source, unit)
    for source in ("host", "wsl")
    for unit in ("vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
                 "vst-sandbox-probe.service")
])
def test_stage_guard_refuses_active_inventory_only_units(
    tmp_path: Path, guard_source: str, unit: str,
):
    with pytest.raises(SystemExit, match="loaded-inactive or not-found"):
        _run_guard(tmp_path, active_unit=unit, guard_source=guard_source)


@pytest.mark.parametrize(("guard_source", "unit"), [
    (source, unit)
    for source in ("host", "wsl")
    for unit in ("vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
                 "vst-sandbox-probe.service")
])
def test_stage_guard_checks_jobs_for_inventory_only_units(
    tmp_path: Path, guard_source: str, unit: str,
):
    with pytest.raises(SystemExit, match="no systemd job"):
        _run_guard(tmp_path, jobs=f"1 {unit} stop waiting\n", guard_source=guard_source)


@pytest.mark.parametrize(("guard_source", "unit"), [
    (source, unit)
    for source in ("host", "wsl")
    for unit in ("vst-assignment-bootstrap.service", "vst-dispatch-issuer.service",
                 "vst-sandbox-probe.service")
])
def test_stage_guard_refuses_populated_inventory_only_unit_cgroups(
    tmp_path: Path, guard_source: str, unit: str,
):
    with pytest.raises(SystemExit, match="empty S2 service cgroups"):
        _run_guard(tmp_path, populated_unit=unit, guard_source=guard_source)

