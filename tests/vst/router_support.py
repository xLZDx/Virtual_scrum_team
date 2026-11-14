"""Shared fixtures for the LINK-2 router tests (not a test module).

- `make_aeve_repo`: a tiny real git repository that plays the AEVE checkout (the pin check runs real git).
- `write_stub`: a stand-in for `python -m aeve` that is started through `command_prefix`. It answers `packet` and
  `verify-handoff` from a JSON spec file that the test can change between calls, and appends one JSON line per
  call to a log file, so a test can count AEVE calls, read the argv and measure overlapping calls.

The stub's packet digest and report status follow the formulas of the design document (LINK2_ROUTER_DESIGN.md
section 2: `request_sha256` is the SHA-256 of the canonical request JSON; the report status is the worst check),
written out here once, independently of the code under test.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import textwrap
import time

from tools.vst import router_request as rr

ROLE = "implementation-engineer"
TASK = "LINK2-DEMO-1"
CHECK_IDS = ("CHANGES_INSIDE_SCOPE", "EVIDENCE_DOCUMENTS_EXIST", "FORBIDDEN_UNTOUCHED", "TASK_ID_MATCH",
             "TESTS_FOR_LOGIC")
EXIT_OF = {"VERIFIED": 0, "REJECTED": 1, "UNKNOWN": 2, "INVALID": 3}
HOST_RESULT = {"schema_version": "aeve.handoff_result.v1", "task_id": TASK, "changed": ["src/app.py", "tests/test_app.py"],
               "tests_added": ["tests/test_app.py"], "evidence_documents": []}


def git(root: pathlib.Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, timeout=60)
    return done.stdout.decode("utf-8", "replace").strip()


def make_aeve_repo(root: pathlib.Path, marker: str = "aeve stand-in") -> str:
    """A clean git repository with one commit; returns its HEAD (a different `marker` gives a different HEAD)."""
    (root / "src").mkdir(parents=True)
    (root / "src" / "marker.txt").write_text(marker + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True, timeout=60)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return git(root, "rev-parse", "HEAD")


def sample_request(task_id: str = TASK, **over):
    kw = dict(role=ROLE, task_id=task_id, title="Demo story", scope_paths=["src", "tests"],
              acceptance=["Result stays inside scope.", "Tests cover the logic."], forbidden_paths=["src/secret"])
    kw.update(over)
    return rr.build_request(**kw)


def expected_request_sha256(request) -> str:
    """AEVE's formula (design section 2, task_packet.py line 218): SHA-256 of the sorted compact ASCII JSON."""
    blob = json.dumps(request, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def worst_of(statuses) -> str:
    statuses = set(statuses)
    if "FAIL" in statuses:
        return "REJECTED"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "VERIFIED"


STUB_SOURCE = '''
import hashlib, json, os, sys, time

SPEC_PATH = {spec!r}
LOG_PATH = {log!r}
command = sys.argv[1]
argv = sys.argv[2:]
with open(SPEC_PATH, encoding="utf-8") as handle:
    spec = json.load(handle)
cmd_spec = dict(spec.get(command, {{}}))
prior = []
if os.path.exists(LOG_PATH):
    with open(LOG_PATH, encoding="utf-8") as handle:
        prior = [line for line in handle.read().splitlines() if line]
calls_before = sum(1 for line in prior if json.loads(line)["command"] == command and json.loads(line)["event"] == "start")
per_call = cmd_spec.pop("calls", None)
if per_call and calls_before < len(per_call):
    cmd_spec.update(per_call[calls_before])


def log(event, **extra):
    with open(LOG_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({{"command": command, "event": event, "pid": os.getpid(), "time": time.time(),
                                  "argv": argv, **extra}}) + "\\n")


def arg(name):
    return argv[argv.index(name) + 1] if name in argv else None


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


extra = {{}}
if command == "verify-handoff":
    res_path = arg("--result")
    if res_path and os.path.exists(res_path):
        extra["result_sha256_seen"] = hashlib.sha256(read(res_path)).hexdigest()
        extra["result_path"] = res_path
        extra["packet_path"] = arg("--packet")
        extra["root"] = arg("--root")
log("start", **extra)
if cmd_spec.get("sleep"):
    time.sleep(cmd_spec["sleep"])
if cmd_spec.get("mutate_result") and arg("--result"):
    with open(arg("--result"), "ab") as handle:
        handle.write(b" ")
if cmd_spec.get("raw") is not None:
    sys.stdout.write(cmd_spec["raw"])
    sys.stdout.flush()
    log("end")
    sys.exit(cmd_spec.get("exit", 0))
if cmd_spec.get("flood"):
    sys.stdout.write("x" * cmd_spec["flood"])
    sys.stdout.flush()
    log("end")
    sys.exit(0)

if command == "packet":
    request = json.loads(read(arg("--request")).decode("utf-8"))
    blob = json.dumps(request, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    doc = {{
        "schema_version": "aeve.task_packet.v1", "status": "COMPLETE", "role": request["role"],
        "task_id": request["task_id"], "title": request["title"],
        "request_sha256": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "scope": {{"allowed_paths": request["scope_paths"], "forbidden_paths": request["forbidden_paths"]}},
        "files": {{"declared": request["files"], "logic": [], "outside_scope": [], "tests": []}},
        "acceptance": [{{"id": "AC-%d" % (i + 1), "text": text}} for i, text in enumerate(request["acceptance"])],
        "risks": [], "objective": "stand-in", "required_evidence": [],
        "llm_calls": 0, "executed_project_code": False, "source_modified": False,
    }}
    exit_code = 0
elif command == "verify-handoff":
    packet = json.loads(read(arg("--packet")).decode("utf-8"))
    checks_spec = {{cid: "PASS" for cid in {check_ids!r}}}
    checks_spec.update(cmd_spec.get("checks", {{}}))
    checks = [{{"id": cid, "status": status, "reason": "stand-in " + status, "paths": []}}
              for cid, status in sorted(checks_spec.items())]
    statuses = {{c["status"] for c in checks}}
    status = "REJECTED" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "VERIFIED"
    doc = {{
        "schema_version": "aeve.handoff_verify.v1", "status": status,
        "basis": "CLAIMED_RESULT_NOT_INDEPENDENTLY_DIFFED", "task_id": packet["task_id"], "role": packet["role"],
        "checks": checks, "llm_calls": 0, "executed_project_code": False, "source_modified": False,
    }}
    exit_code = {{"VERIFIED": 0, "REJECTED": 1, "UNKNOWN": 2}}[status]
else:
    sys.stderr.write("unknown command")
    sys.exit(64)
for key in cmd_spec.get("drop", []):
    doc.pop(key, None)
doc.update(cmd_spec.get("set", {{}}))
exit_code = cmd_spec.get("exit", exit_code)
sys.stdout.write(json.dumps(doc, sort_keys=True))
sys.stdout.flush()
log("end")
sys.exit(exit_code)
'''


class Stub:
    """A stand-in AEVE: `prefix` goes to `command_prefix`; `set(...)` changes the behaviour between calls."""

    def __init__(self, directory: pathlib.Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.spec_path = directory / "stub_spec.json"
        self.log_path = directory / "stub_calls.jsonl"
        self.script = directory / "stub_aeve.py"
        self.spec: dict = {}
        self.script.write_text(STUB_SOURCE.format(spec=str(self.spec_path), log=str(self.log_path),
                                                  check_ids=CHECK_IDS), encoding="utf-8")
        self.write_spec()
        self.prefix = [sys.executable, "-s", "-B", str(self.script)]

    def write_spec(self) -> None:
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

    def set(self, command: str, **behaviour) -> None:
        self.spec[command] = behaviour
        self.write_spec()

    def clear_spec(self) -> None:
        """Default behaviour again; the call log is kept."""
        self.spec = {}
        self.write_spec()

    def reset(self) -> None:
        """Back to the default behaviour and an empty call log."""
        self.spec = {}
        self.write_spec()
        if self.log_path.exists():
            self.log_path.unlink()

    def calls(self, command: str | None = None, event: str = "start") -> list[dict]:
        if not self.log_path.exists():
            return []
        rows = [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line]
        return [r for r in rows if r["event"] == event and (command is None or r["command"] == command)]

    def max_overlap(self, command: str) -> int:
        """The most calls of `command` that were running at the same moment (from the start and end log lines)."""
        starts = [(r["time"], 1) for r in self.calls(command, "start")]
        ends = [(r["time"], -1) for r in self.calls(command, "end")]
        level = best = 0
        for _when, step in sorted(starts + ends, key=lambda item: (item[0], item[1])):
            level += step
            best = max(best, level)
        return best


def read_log_lines(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines() if line]


def wait_until(predicate, seconds: float = 10.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def pid_alive(pid: int) -> bool:
    """tasklist-based liveness (os.kill(pid, 0) is not a probe on Windows)."""
    done = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True, text=True,
                          timeout=30)
    return f'"{pid}"' in done.stdout


def link_mode_file(directory: pathlib.Path, mode: str) -> pathlib.Path:
    """A catalog copy whose current mode is `mode` (the shipped catalog is only read)."""
    from tools.vst import link_mode

    source = json.loads(link_mode.DEFAULT_PATH.read_text(encoding="utf-8"))
    source["mode"] = mode
    path = directory / "link_mode.json"
    path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    return path


def dedent(text: str) -> str:
    return textwrap.dedent(text)
