"""Shared fixtures-as-functions for the tools/uc tests (no network, no real AEVE)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TABLE_PATH = REPO_ROOT / "catalog" / "role_table.json"
HEAD = "a" * 40
HASH_A = "b" * 64
HASH_C = "c" * 64


def real_table() -> dict:
    return json.loads(TABLE_PATH.read_text(encoding="utf-8"))


def real_table_sha256() -> str:
    """sha256 of the exact bytes of the committed catalog/role_table.json (what router.load_table_with_digest reports)."""
    import hashlib
    return hashlib.sha256(TABLE_PATH.read_bytes()).hexdigest()


def valid_request(root: str, **over) -> dict:
    doc = {
        "schema_version": "uc.role-request.v1",
        "request_id": "req-1",
        "root": root,
        "base_revision": HEAD,
        "changed_paths": ["src/a.py", "docs/b.md"],
        "roles": ["python-reviewer"],
        "purpose": "advisory",
    }
    doc.update(over)
    return doc


def valid_role_entry(**over) -> dict:
    entry = {
        "role": "python-reviewer", "canonical_role": "python-reviewer", "class": "LOCAL_PLUS_MODEL",
        "status": "PARTIAL",
        "executors": [{"id": "g2.python-rules", "status": "COMPLETE", "snapshot_hash": HASH_A}],
        "findings": [], "uncovered": [], "model_residual": ["model-judgment"],
    }
    entry.update(over)
    return entry


def valid_finding(**over) -> dict:
    f = {"rule_id": "py-silent-except-swallow", "severity": "MAJOR", "path": "src/a.py", "line": 3,
         "column": 1, "evidence_hash": HASH_C}
    f.update(over)
    return f


def valid_result(**over) -> dict:
    doc = {
        "schema_version": "uc.role-result.v1", "request_id": "req-1", "base_revision": HEAD,
        "snapshot_hash": HASH_A, "iteration_id": "it-1", "exit_code": 3, "roles": [valid_role_entry()],
        "role_table_sha256": HASH_C, "aeve_head": "d" * 40,
    }
    doc.update(over)
    return doc


def aeve_response(request_id="req-1", head=HEAD, executor_ids=("g2.python-rules",), status="COMPLETE",
                  results=None, findings=None, uncovered=None, **over) -> dict:
    doc = {
        "status": status, "request_id": request_id, "head": head, "snapshot_sha256": HASH_A,
        "iteration_id": "iter-9", "executor_ids": list(executor_ids),
        "results": results if results is not None else
        [{"executor_id": e, "status": "COMPLETE", "uncovered": []} for e in executor_ids],
        "findings": findings or [], "uncovered": uncovered or [], "llm_calls": 0,
        "executed_project_code": False, "source_modified": False, "dirty": False,
    }
    doc.update(over)
    return doc


def aeve_finding(executor_id="g2.python-rules", file="src/a.py", rule_id="py-silent-except-swallow",
                 severity="MAJOR", line=3, column=1, **over) -> dict:
    f = {"executor_id": executor_id, "rule_id": rule_id, "severity": severity, "file": file, "line": line,
         "column": column, "evidence": {"line_sha256": HASH_C}}
    f.update(over)
    return f


def write_stub(directory: pathlib.Path, body: str, name: str = "stub_aeve.py") -> list[str]:
    """Write a stub 'aeve' script and return a command_prefix that runs it with this interpreter.

    The body runs with ``req`` (the parsed request) and ``req_path`` defined; helper ``emit(obj)`` prints JSON.
    """
    directory.mkdir(parents=True, exist_ok=True)
    source = "import json, os, sys, time\n" + textwrap.dedent("""\
        req_path = sys.argv[-1]
        with open(req_path, encoding='utf-8') as _h:
            req = json.load(_h)
        def emit(obj, code=0):
            sys.stdout.write(json.dumps(obj))
            sys.stdout.flush()
            sys.exit(code)
        def good(**over):
            ids = req['executor_ids']
            doc = {'status': 'COMPLETE', 'request_id': req['request_id'], 'head': req['base_revision'],
                   'snapshot_sha256': 'b' * 64, 'iteration_id': 'iter-9', 'executor_ids': ids,
                   'results': [{'executor_id': e, 'status': 'COMPLETE', 'uncovered': []} for e in ids],
                   'findings': [], 'uncovered': [], 'llm_calls': 0, 'executed_project_code': False,
                   'source_modified': False, 'dirty': False}
            doc.update(over)
            return doc
        """) + textwrap.dedent(body)
    script = directory / name
    script.write_text(source, encoding="utf-8")
    return [sys.executable, str(script)]


def make_junction(link: pathlib.Path, target: pathlib.Path) -> bool:
    """Create an NTFS junction (no privilege needed). Returns False when it cannot be created."""
    if os.name != "nt":
        return False
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    return result.returncode == 0 and link.exists()


def remove_junction(link: pathlib.Path) -> None:
    try:
        os.rmdir(link)
    except OSError:
        pass
