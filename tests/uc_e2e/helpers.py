"""Fixture builders and the CLI runner for the U1 router end-to-end tests.

Every real run goes through the public entry command (a subprocess), never through an
in-process import of the router. Fixture repositories are real git repositories in temp dirs.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ROUTER = REPO_ROOT / "tools" / "uc" / "router.py"
TABLE = REPO_ROOT / "catalog" / "role_table.json"
AEVE_ROOT = pathlib.Path("D:/Repo/AEVE")
PYTHON = "C:/Python314/python.exe"
CLI_TIMEOUT = 150

# Seeded fake secret: appears only in fixture source and must never reach any output.
FAKE_SECRET = "sk_live_FAKE7Q9ZxSEEDSECRET00112233"

APP_SOURCE = (
    f"# Legacy credential kept for reference only: {FAKE_SECRET}\n"
    "import os\n"
    "\n"
    "\n"
    "def read_text(path):\n"
    "    try:\n"
    "        with open(path, encoding=\"utf-8\") as handle:\n"
    "            return handle.read()\n"
    "    except Exception:\n"
    "        pass\n"
)
APP_EXCEPT_LINE = APP_SOURCE.splitlines().index("    except Exception:") + 1
APP_PATH = "src/app.py"


def git(cwd: pathlib.Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(cwd), "-c", "commit.gpgsign=false", *args],
                          capture_output=True, text=True, encoding="utf-8", check=True, timeout=60)
    return done.stdout.strip()


def make_repo(root: pathlib.Path, files: dict[str, str]) -> str:
    """Create a git repository with ``files`` committed; return the HEAD commit id."""
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "uc-e2e")
    git(root, "config", "user.email", "uc-e2e@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    for rel, text in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "fixture")
    return git(root, "rev-parse", "HEAD")


def hostile_files(sentinel_dir: pathlib.Path) -> dict[str, str]:
    """Modules that would write a sentinel and call SystemExit if anything imported them."""
    def payload(name: str) -> str:
        target = str(sentinel_dir / name).replace("\\", "/")
        return (f"open({target!r}, 'w').write('executed')\n"
                f"raise SystemExit(99)\n")
    return {
        APP_PATH: APP_SOURCE,
        "json.py": payload("json_py.txt"),
        "aeve/__init__.py": payload("aeve_init.txt"),
        "aeve/__main__.py": payload("aeve_main.txt"),
        "sitecustomize.py": payload("sitecustomize.txt"),
        "usercustomize.py": payload("usercustomize.txt"),
    }


def request(root: pathlib.Path, head: str, request_id: str, roles: list[str], changed: list[str],
            **extra) -> dict:
    doc = {"schema_version": "uc.role-request.v1", "request_id": request_id, "root": str(root),
           "base_revision": head, "changed_paths": changed, "roles": roles, "purpose": "advisory"}
    doc.update(extra)
    return doc


def run_router(request_doc, work: pathlib.Path, *, state_dir: pathlib.Path | None, allowed_roots: list[str],
               cwd: pathlib.Path | None = None, aeve_root: pathlib.Path = AEVE_ROOT,
               request_file: pathlib.Path | None = None, extra_args: list[str] | None = None,
               omit_state_dir: bool = False, with_python: bool = True,
               table: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    """Run the entry command exactly as an orchestrator would and return the completed process."""
    work.mkdir(parents=True, exist_ok=True)
    if request_file is None:
        request_file = work / f"request-{abs(hash(json.dumps(request_doc, sort_keys=True, default=str))) % 10**8}.json"
        request_file.write_text(json.dumps(request_doc), encoding="utf-8")
    argv = [PYTHON, str(ROUTER), "review", "--request", str(request_file), "--aeve-root", str(aeve_root),
            "--table", str(table or TABLE)]
    if not omit_state_dir:
        argv += ["--state-dir", str(state_dir)]  # str(): a relative Path stays relative, as an orchestrator might pass it
    for item in allowed_roots:
        argv += ["--allowed-root", item]
    if with_python:
        argv += ["--python", PYTHON]
    argv += extra_args or []
    return subprocess.run(argv, cwd=str(cwd or work), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=CLI_TIMEOUT, env=dict(os.environ))


def parse_stdout(done: subprocess.CompletedProcess) -> dict:
    """stdout must be exactly one JSON document."""
    return json.loads(done.stdout)


def tree_contains(directory: pathlib.Path, needle: str) -> list[str]:
    """Paths of files under ``directory`` whose bytes contain ``needle`` (UTF-8 and UTF-16LE)."""
    hits = []
    forms = (needle.encode("utf-8"), needle.encode("utf-16-le"))
    for path in directory.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            if any(form in data for form in forms):
                hits.append(str(path))
    return hits


def role(result: dict, name: str) -> dict:
    return next(r for r in result["roles"] if r["role"] == name)
