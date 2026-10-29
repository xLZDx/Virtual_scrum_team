"""Isolated preflight checks extracted from the committed Windows/WSL stage-only scripts."""
from __future__ import annotations

import ast
import json
import os
import re
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


def _stage_guard() -> ast.If:
    module = ast.parse(_powershell_bootstrap())
    matches = [node for node in module.body if isinstance(node, ast.If)
               and isinstance(node.test, ast.Name) and node.test.id == "stage_only"]
    assert matches
    return min(matches, key=lambda node: node.lineno)


def _run_guard(tmp_path: Path, *, configured: str | None = None,
               active_unit: str | None = None, jobs: str = "",
               populated_unit: str | None = None) -> None:
    cgroup_root = tmp_path / "cgroup"
    cgroup_root.mkdir(exist_ok=True)
    units = (
        "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
        "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
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
    namespace = {"stage_only": True, "units": units, "os": fake_os,
                 "subprocess": fake_subprocess, "SystemExit": SystemExit}
    exec(compile(ast.Module(body=[_stage_guard()], type_ignores=[]), "stage-only-preflight", "exec"), namespace)


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


def test_stage_guard_accepts_complete_idle_inventory(tmp_path: Path):
    assert _run_guard(tmp_path) is None


def test_stage_guard_refuses_existing_configuration_path(tmp_path: Path):
    with pytest.raises(SystemExit, match="absent runtime configuration/socket"):
        _run_guard(tmp_path, configured="/etc/vst-runner")


def test_stage_guard_requires_exactly_inactive_state(tmp_path: Path):
    with pytest.raises(SystemExit, match="loaded-inactive or not-found"):
        _run_guard(tmp_path, active_unit="vst-runner.service")


@pytest.mark.parametrize("row", [
    "1 vst-runner.service stop waiting\n",
    "2 vst-dispatch-owner.socket start running\n",
])
def test_stage_guard_checks_systemd_unit_column_in_job_rows(tmp_path: Path, row: str):
    with pytest.raises(SystemExit, match="no systemd job"):
        _run_guard(tmp_path, jobs=row)


def test_stage_guard_refuses_populated_service_cgroup(tmp_path: Path):
    with pytest.raises(SystemExit, match="empty S2 service cgroups"):
        _run_guard(tmp_path, populated_unit="vst-signer.service")

