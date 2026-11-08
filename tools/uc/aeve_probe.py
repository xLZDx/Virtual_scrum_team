"""Environment probe for a local AEVE checkout (sprint U1, task U1-2).

Runs AEVE from its checkout without installing anything into the AEVE repository, records its
identity (git HEAD, dirty state, interpreter, matrix digest) and refuses to report a usable
environment unless the registry check and the matrix command both succeed. No model, no
network and no project code is involved; AEVE itself only reads.

Usage:
    python tools/uc/aeve_probe.py --aeve-root D:/Repo/AEVE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

PROBE_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 60.0
_MIN_PYTHON = (3, 12)
_PASS_THROUGH_ENV = ("PATH", "SYSTEMROOT", "SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT")


class AeveProbeError(Exception):
    """The AEVE environment is not usable; ``reason`` is a stable machine-readable code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def build_child_env(aeve_root: pathlib.Path) -> dict[str, str]:
    """Minimal child environment: AEVE source on PYTHONPATH, no bytecode written, no user site."""
    env = {key: os.environ[key] for key in _PASS_THROUGH_ENV if key in os.environ}
    env["PYTHONPATH"] = str(aeve_root / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(argv: list[str], *, cwd: pathlib.Path, env: dict[str, str], timeout: float) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AeveProbeError("TIMEOUT", f"{argv[:3]} exceeded {timeout}s") from exc
    except OSError as exc:
        raise AeveProbeError("EXEC_FAILED", f"{argv[0]}: {exc}") from exc


def _git(aeve_root: pathlib.Path, args: list[str], env: dict[str, str], timeout: float) -> str:
    result = _run(["git", "-C", str(aeve_root), *args], cwd=aeve_root, env=env, timeout=timeout)
    if result.returncode != 0:
        raise AeveProbeError("GIT_FAILED", (result.stderr or "").strip()[:200])
    return result.stdout


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_json(text: str, label: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise AeveProbeError("BAD_OUTPUT", f"{label} did not print JSON") from exc
    if not isinstance(value, dict):
        raise AeveProbeError("BAD_OUTPUT", f"{label} JSON is not an object")
    return value


def probe(
    aeve_root: pathlib.Path,
    *,
    python: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Return the identity record of a usable AEVE checkout or raise AeveProbeError."""
    aeve_root = aeve_root.resolve()
    if not (aeve_root / "src" / "aeve" / "__main__.py").is_file():
        raise AeveProbeError("NOT_AN_AEVE_CHECKOUT", str(aeve_root))
    interpreter = python or sys.executable
    env = build_child_env(aeve_root)
    scratch = pathlib.Path(tempfile.gettempdir())

    version_run = _run([interpreter, "-c", "import sys;print(sys.version_info[0],sys.version_info[1])"],
                       cwd=scratch, env=env, timeout=timeout)
    if version_run.returncode != 0:
        raise AeveProbeError("INTERPRETER_FAILED", (version_run.stderr or "").strip()[:200])
    try:
        major, minor = (int(part) for part in version_run.stdout.split())
    except ValueError as exc:
        raise AeveProbeError("INTERPRETER_FAILED", "unreadable interpreter version") from exc
    if (major, minor) < _MIN_PYTHON:
        raise AeveProbeError("PYTHON_TOO_OLD", f"{major}.{minor} < {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}")

    head = _git(aeve_root, ["rev-parse", "HEAD"], env, timeout).strip()
    status_lines = [line for line in _git(aeve_root, ["status", "--porcelain"], env, timeout).splitlines() if line]
    tracked_dirty = [line for line in status_lines if not line.startswith("??")]

    doctor_run = _run([interpreter, "-m", "aeve", "doctor"], cwd=scratch, env=env, timeout=timeout)
    if doctor_run.returncode != 0:
        raise AeveProbeError("DOCTOR_FAILED", f"exit {doctor_run.returncode}: {(doctor_run.stderr or '').strip()[:200]}")
    doctor = _parse_json(doctor_run.stdout, "aeve doctor")

    matrix_run = _run([interpreter, "-m", "aeve", "matrix"], cwd=scratch, env=env, timeout=timeout)
    if matrix_run.returncode != 0:
        raise AeveProbeError("MATRIX_FAILED", f"exit {matrix_run.returncode}: {(matrix_run.stderr or '').strip()[:200]}")
    matrix = _parse_json(matrix_run.stdout, "aeve matrix")
    for field in ("total_profiles", "status_counts", "rows", "executors"):
        if field not in matrix:
            raise AeveProbeError("BAD_OUTPUT", f"matrix lacks {field}")

    if doctor.get("llm_calls") != 0 or doctor.get("executed_project_code") is not False:
        raise AeveProbeError("MODEL_OR_EXECUTION_REPORTED", "doctor reports model calls or project code execution")
    if matrix.get("llm_calls") not in (False, 0) or matrix.get("executed_project_code") is not False:
        raise AeveProbeError("MODEL_OR_EXECUTION_REPORTED", "matrix reports model calls or project code execution")

    return {
        "probe_version": PROBE_VERSION,
        "aeve_root": str(aeve_root),
        "aeve_head": head,
        "tracked_dirty_paths": len(tracked_dirty),
        "untracked_paths": len(status_lines) - len(tracked_dirty),
        "interpreter": interpreter,
        "python": f"{major}.{minor}",
        "doctor": {
            "agent_profiles": doctor.get("agent_profiles"),
            "skill_contracts": doctor.get("skill_contracts"),
            "llm_calls": doctor.get("llm_calls"),
            "executed_project_code": doctor.get("executed_project_code"),
        },
        "matrix": {
            "schema_version": matrix.get("schema_version"),
            "total_profiles": matrix["total_profiles"],
            "status_counts": matrix["status_counts"],
            "executor_count": len(matrix["executors"]),
            "digest_sha256": canonical_digest(matrix),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aeve-root", required=True, type=pathlib.Path)
    parser.add_argument("--python", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        record = probe(args.aeve_root, python=args.python, timeout=args.timeout)
    except AeveProbeError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": exc.reason, "detail": exc.detail}, sort_keys=True))
        return 2
    print(json.dumps({"status": "READY", **record}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
