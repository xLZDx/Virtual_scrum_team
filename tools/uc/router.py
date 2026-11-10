"""Role router and result normalizer (sprint U1, tasks U1-6 and U1-7).

Resolves each requested role through the role table, sends one combined review to AEVE through
the isolated adapter, and normalizes the response into ``uc.role-result.v1``. The result carries
only enumerations, integers, hashes and paths from an allowlist; uncovered scope is reduced to
short tokens, so repository-controlled text cannot reach the orchestrator through it.

Entry command (U1-7):
    python tools/uc/router.py review --request <role-request.json> --aeve-root D:/Repo/AEVE \
        --table catalog/role_table.json --state-dir <dir> --allowed-root <repo root> [--allowed-root ...]
Prints a uc.role-result.v1 document, or a uc.blocked.v1 envelope when no result can be produced.
Exit codes: 0 every role CLEAN, 3 open items, 2 blocked or invalid (envelope on stdout).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from uc import adapter, aeve_probe, contracts  # noqa: E402
from uc.secret_patterns import _SECRET, has_secret  # noqa: E402,F401  (re-exported; defined side-effect free)

if os.name == "nt":
    import msvcrt
else:  # pragma: no cover - the project runs on Windows; kept so the module imports elsewhere
    import fcntl

# Roles whose full job includes running tests; only their static part exists until sprint U3.
TEST_ROLE_NAMES = frozenset({
    "e2e-runner", "e2e-testing-contract", "functional-test-reviewer", "functional-testing",
    "tdd-guide", "pr-test-analyzer",
})
LOCK_WAIT_SECONDS = 30.0
_TOKEN_CLEAN = re.compile(r"[^a-z0-9_.-]+")
# A result path is copied only when it is a plain short name; anything else becomes an opaque digest.
_SAFE_PATH = re.compile(r"^[A-Za-z0-9._@+/-]{1,120}$")
SEVERITY_RANK = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "NIT": 3}
_EXECUTOR_STATUS = {"COMPLETE": "COMPLETE", "PARTIAL": "PARTIAL", "BLOCKED": "BLOCKED",
                    "NOT_COVERED": "NOT_COVERED", "NOT_RUN": "NOT_RUN"}
_ROLE_CLASSES = ("LOCAL", "LOCAL_PLUS_MODEL", "MODEL_ONLY", "OUT_OF_SCOPE")
_COVERAGE_STATES = ("COVERED_PARTIAL", "NOT_COVERED_NO_EXECUTOR", "NOT_COVERED_NO_PROFILE", "NOT_APPLICABLE")


def to_token(text: object, fallback: str = "unspecified") -> str:
    """Reduce any text to a short lowercase token; only the part before the first ':' can survive."""
    if has_secret(text):
        return "redacted"
    head = str(text).split(":", 1)[0].strip().lower()
    token = _TOKEN_CLEAN.sub("-", head).strip("-_.")[:64]
    return token if re.match(r"^[a-z0-9][a-z0-9_.-]{0,63}$", token) else fallback


def load_table_with_digest(path: pathlib.Path) -> tuple[dict, str]:
    """Read the role table once: return the parsed table and the sha256 of the exact bytes that were parsed."""
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def load_table(path: pathlib.Path) -> dict:
    return load_table_with_digest(path)[0]


def check_table(table: object) -> None:
    """Refuse a role table whose shape the router cannot trust (run on every request)."""
    if not isinstance(table, dict) or not isinstance(table.get("entries"), list) or not isinstance(table.get("aeve_pin"), dict):
        raise adapter.AdapterBlocked("ROLE_TABLE_INVALID", "table lacks entries or aeve_pin")
    for entry in table["entries"]:
        ok = (isinstance(entry, dict) and isinstance(entry.get("name"), str) and isinstance(entry.get("canonical_role"), str)
              and entry.get("class") in _ROLE_CLASSES and entry.get("coverage_state") in _COVERAGE_STATES
              and isinstance(entry.get("executors"), list) and all(isinstance(x, str) for x in entry["executors"]))
        if ok and entry["coverage_state"] == "COVERED_PARTIAL":
            ok = bool(entry["executors"]) and entry["class"] in ("LOCAL", "LOCAL_PLUS_MODEL")
        if not ok:
            raise adapter.AdapterBlocked("ROLE_TABLE_INVALID", "a table entry is malformed or inconsistent")


def _lookup(table: dict, name: str) -> dict | None:
    for entry in table["entries"]:  # agents sort before skills, so an agent wins a shared name
        if entry["name"] == name:
            return entry
    return None


class _RequestLock:
    """Per-request OS file lock: released by the OS if the process dies, so no stale-lock logic exists."""

    def __init__(self, directory: pathlib.Path, request_id: str) -> None:
        self.handle = open(directory / f"{request_id}.lock", "a+b")
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                if os.name == "nt":
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover
                    fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.monotonic() > deadline:
                    self.handle.close()
                    raise adapter.AdapterBlocked("REQUEST_LOCKED", "another run with this request_id is in progress") from None
                time.sleep(0.1)

    def release(self) -> None:
        try:
            if os.name == "nt":
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover
                fcntl.flock(self.handle, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self.handle.close()


def _fingerprint_path(directory: pathlib.Path, request_id: str, iteration_of: str | None) -> pathlib.Path:
    return directory / f"{request_id}.{iteration_of or 'first'}.sha256"


def _identity_path(directory: pathlib.Path, request_id: str) -> pathlib.Path:
    return directory / f"{request_id}.identity.sha256"


def _read_record(path: pathlib.Path) -> str | None:
    """None when the record does not exist; a damaged record blocks (fail closed), it is never treated as absent."""
    if not path.exists():
        return None
    try:
        stored = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError) as exc:
        raise adapter.AdapterBlocked("FINGERPRINT_UNREADABLE", "a request record cannot be read; use a new request_id") from exc
    if not re.fullmatch(r"[0-9a-f]{64}", stored):
        raise adapter.AdapterBlocked("FINGERPRINT_CORRUPT", "a request record is damaged; use a new request_id")
    return stored


def _check_records(directory: pathlib.Path, request_id: str, iteration_of: str | None, content_sha: str,
                   identity_sha: str) -> None:
    """A request_id is bound to one reviewed root for good (whatever iteration_of says), and to one
    content per iteration: a retry with the same iteration_of must carry the same content."""
    identity = _read_record(_identity_path(directory, request_id))
    if identity is not None and identity != identity_sha:
        raise adapter.AdapterBlocked("REQUEST_ID_CONFLICT", "same request_id for a different reviewed root")
    stored = _read_record(_fingerprint_path(directory, request_id, iteration_of))
    if stored is not None and stored != content_sha:
        raise adapter.AdapterBlocked("REQUEST_ID_CONFLICT", "same request_id with different content")


def _write_record(path: pathlib.Path, value: str) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _map_finding(raw: object, where: str, request_paths: frozenset[str]) -> tuple[dict, tuple]:
    """Return the contract finding and its dedupe key (the key keeps the raw, untokenized rule id)."""
    if not isinstance(raw, dict):
        raise adapter.AdapterBlocked("AEVE_CONTRACT_VIOLATION", f"{where} is not an object")
    severity = raw.get("severity")
    if severity not in contracts.SEVERITIES:
        raise adapter.AdapterBlocked("UNKNOWN_SEVERITY", f"{where}")
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    evidence_hash = evidence.get("line_sha256") or evidence.get("source_sha256")
    if not isinstance(evidence_hash, str) or not re.match(r"^[0-9a-f]{64}$", evidence_hash):
        evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
    numbers = []
    for name in ("line", "column"):
        value = raw.get(name, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise adapter.AdapterBlocked("BAD_FINDING_POSITION", f"{where}.{name}")
        numbers.append(value)
    path = raw.get("file")
    try:
        contracts.validate_relative_posix_path(path, where)
    except contracts.ContractError as exc:
        raise adapter.AdapterBlocked("BAD_FINDING_PATH", exc.code) from exc
    shown = path
    if path not in request_paths or not _SAFE_PATH.match(path) or has_secret(path):
        # Not one of the requested paths, or not a plain short name: only an opaque digest leaves the router.
        shown = "masked/" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    finding = {
        "rule_id": to_token(raw.get("rule_id"), "unknown-rule"),
        "severity": severity,
        "path": shown,
        "line": numbers[0],
        "column": numbers[1],
        "evidence_hash": evidence_hash,
    }
    return finding, (str(raw.get("rule_id")), path, numbers[0], numbers[1], evidence_hash)


def normalize(role_request: dict, table: dict, response: dict | None, adapter_error: adapter.AdapterBlocked | None,
              *, role_table_sha256: str, aeve_head: str) -> dict:
    """Build the role result. ``response`` is the adapter-validated AEVE response, or None when blocked.

    ``role_table_sha256`` and ``aeve_head`` are the bridge facts (U2-1) and are copied into the result
    as given; the caller supplies the digest of the exact table bytes it loaded and the probed, pin-matched AEVE head.
    ``purpose`` and ``changed_paths_sha256`` (U2-3) are derived from the validated request itself.
    """
    snapshot = response["snapshot_sha256"] if response else "0" * 64
    results_by_executor = {r["executor_id"]: r for r in (response["results"] if response else [])}
    request_paths = frozenset(role_request["changed_paths"])
    aeve_gap = bool(response) and (response.get("status") == "PARTIAL" or bool(response.get("uncovered"))
                                   or bool(response.get("executor_gaps")))
    roles_out = []
    for role in role_request["roles"]:
        entry = _lookup(table, role)
        if entry is None:
            roles_out.append(_role_entry(role, role, "UNKNOWN", "NOT_COVERED", [], [], ["unknown-role"], []))
            continue
        canonical, klass, executors = entry["canonical_role"], entry["class"], entry["executors"]
        if entry["coverage_state"] != "COVERED_PARTIAL":
            token = {"NOT_COVERED_NO_PROFILE": "no-aeve-profile", "NOT_COVERED_NO_EXECUTOR": "no-executor",
                     "NOT_APPLICABLE": "model-only" if klass == "MODEL_ONLY" else "out-of-scope"}[entry["coverage_state"]]
            residual = ["authoring"] if klass == "MODEL_ONLY" else []
            roles_out.append(_role_entry(role, canonical, klass, "NOT_COVERED", [], [], [token], residual))
            continue
        uncovered: list[str] = []
        if role in TEST_ROLE_NAMES or canonical in TEST_ROLE_NAMES:
            uncovered.append("test-execution-not-available")
        if aeve_gap:
            uncovered.append("aeve-partial")  # AEVE itself reported partial coverage: never CLEAN
        residual = ["model-judgment"] if klass == "LOCAL_PLUS_MODEL" else []
        if response is None:
            roles_out.append(_role_entry(role, canonical, klass, "BLOCKED", [], [], uncovered, residual))
            continue
        exec_out, blocked = [], False
        for exec_id in executors:
            raw = results_by_executor.get(exec_id)
            status = _EXECUTOR_STATUS.get(raw.get("status"), "BLOCKED") if raw else "NOT_RUN"
            exec_out.append({"id": to_token(exec_id), "status": status, "snapshot_hash": snapshot})
            blocked = blocked or status == "BLOCKED"
            if raw:
                for item in raw.get("uncovered", []) if isinstance(raw.get("uncovered"), list) else []:
                    uncovered.append(to_token(item))
        best: dict[tuple, dict] = {}
        for raw_finding in response["findings"]:
            if raw_finding["executor_id"] in executors:
                finding, key = _map_finding(raw_finding, f"finding[{role}]", request_paths)
                kept = best.get(key)
                if kept is None or SEVERITY_RANK[finding["severity"]] < SEVERITY_RANK[kept["severity"]]:
                    best[key] = finding  # same place and evidence: the most severe report wins
        unique = sorted(best.values(), key=lambda f: (SEVERITY_RANK[f["severity"]], f["path"], f["line"], f["column"],
                                                      f["rule_id"], f["evidence_hash"]))
        if blocked:
            uncovered.append("executor-blocked")
        uncovered = sorted(set(uncovered))
        if blocked:
            status = "PARTIAL" if unique else "BLOCKED"  # findings are kept: they are real, but coverage is incomplete
        elif all(e["status"] == "NOT_RUN" for e in exec_out):
            status = "NOT_RUN"
        elif unique:
            status = "FINDINGS"
        elif any(e["status"] != "COMPLETE" for e in exec_out) or uncovered or residual:
            status = "PARTIAL"
        else:
            status = "CLEAN"
        roles_out.append(_role_entry(role, canonical, klass, status, exec_out, unique, uncovered, residual))
    all_clean = all(r["status"] == "CLEAN" for r in roles_out)
    return {
        "schema_version": contracts.RESULT_SCHEMA,
        "request_id": role_request["request_id"],
        "base_revision": role_request["base_revision"],
        "snapshot_hash": snapshot,
        "iteration_id": to_token(response["iteration_id"], "none") if response else f"blocked-{role_request['request_id']}"[:128],
        "exit_code": 0 if all_clean else 3,
        "roles": roles_out,
        "role_table_sha256": role_table_sha256,
        "aeve_head": aeve_head,
        "purpose": role_request["purpose"],
        "changed_paths_sha256": contracts.changed_paths_sha256(role_request["changed_paths"]),
    }


def _role_entry(role, canonical, klass, status, executors, findings, uncovered, residual) -> dict:
    return {"role": role, "canonical_role": canonical, "class": klass, "status": status, "executors": executors,
            "findings": findings, "uncovered": uncovered, "model_residual": residual}


def _inside(path: pathlib.Path, roots: list[str]) -> bool:
    target = os.path.normcase(str(path.resolve()))
    for root in roots:
        base = os.path.normcase(os.path.abspath(root))
        if target == base or target.startswith(base.rstrip("\\/") + os.sep):
            return True
    return False


def review(role_request: dict, *, table: dict, aeve_root: pathlib.Path, state_dir: pathlib.Path,
           allowed_roots: list[str], table_sha256: str | None = None, python: str | None = None,
           command_prefix: list[str] | None = None, timeout: float = adapter.DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Validate, check the AEVE pin, run one combined review and return a validated result or a blocked envelope.

    ``table_sha256`` is the digest of the exact role_table.json bytes ``table`` was parsed from (see
    ``load_table_with_digest``); without it, or with an all-zero or malformed value, no result is produced
    (BLOCKED ROLE_TABLE_HASH_MISSING), because the digest is never reconstructed from the parsed table.
    The exact-bytes guarantee holds only for the CLI path (``main`` uses ``load_table_with_digest``); a
    library caller of ``review()`` is trusted to pass the digest of the bytes it parsed ``table`` from.

    Never raises: any unexpected failure becomes a BLOCKED envelope with reason INTERNAL_ERROR.
    """
    request_id = role_request.get("request_id", "unknown") if isinstance(role_request, dict) else "unknown"
    try:
        doc = contracts.validate_request(role_request, allowed_roots, check_symlinks=True)
    except contracts.ContractError as exc:
        return _blocked(request_id, "INVALID_REQUEST", f"{exc.code} at {exc.where}")
    except Exception as exc:  # noqa: BLE001 - a malformed request must still yield an envelope
        return _blocked(request_id, "INVALID_REQUEST", type(exc).__name__)
    content_sha = hashlib.sha256(json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()
    lock = None
    try:
        check_table(table)
        if (not isinstance(table_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", table_sha256)
                or table_sha256 == "0" * 64):
            raise adapter.AdapterBlocked("ROLE_TABLE_HASH_MISSING", "the digest of the loaded role table bytes was not supplied")
        state_dir = pathlib.Path(state_dir)
        if not state_dir.is_absolute() or _inside(state_dir, allowed_roots):
            raise adapter.AdapterBlocked("BAD_STATE_DIR", "state_dir must be absolute and outside every allowed root")
        directory = state_dir / "uc-requests"
        directory.mkdir(parents=True, exist_ok=True)
        record = aeve_probe.probe(aeve_root, python=python, timeout=min(timeout, aeve_probe.DEFAULT_TIMEOUT_SECONDS))
        pin = table["aeve_pin"]
        if pin.get("head") != record["aeve_head"] or pin.get("matrix_digest_sha256") != record["matrix"]["digest_sha256"]:
            raise adapter.AdapterBlocked("AEVE_PIN_MISMATCH", "AEVE head or matrix digest differs from the role table pin")
        if record["tracked_dirty_paths"] or record.get("untracked_source_paths", 1):
            raise adapter.AdapterBlocked("AEVE_CHECKOUT_DIRTY", "the AEVE checkout differs from its pinned commit")
        lock = _RequestLock(directory, doc["request_id"])
        identity_sha = hashlib.sha256(os.path.normcase(os.path.abspath(doc["root"])).encode("utf-8")).hexdigest()
        _check_records(directory, doc["request_id"], doc.get("iteration_of"), content_sha, identity_sha)
        executor_ids = sorted({x for role in doc["roles"]
                               for e in [(_lookup(table, role) or {})] if e.get("coverage_state") == "COVERED_PARTIAL"
                               for x in e["executors"]})
        response = None
        if executor_ids:
            response = _call(doc, executor_ids, aeve_root=aeve_root, state_dir=state_dir, python=python,
                             command_prefix=command_prefix, timeout=timeout)
        result = normalize(doc, table, response, None, role_table_sha256=table_sha256, aeve_head=record["aeve_head"])
        contracts.validate_result(result)
        # recorded only after a result exists, so a failed run never poisons the id
        _write_record(_identity_path(directory, doc["request_id"]), identity_sha)
        _write_record(_fingerprint_path(directory, doc["request_id"], doc.get("iteration_of")), content_sha)
        return result
    except (adapter.AdapterBlocked, aeve_probe.AeveProbeError) as exc:
        return _blocked(doc["request_id"], exc.reason, exc.detail)
    except contracts.ContractError as exc:
        return _blocked(doc["request_id"], "RESULT_CONTRACT_VIOLATION", f"{exc.code} at {exc.where}")
    except Exception as exc:  # noqa: BLE001 - the 0/2/3 exit contract must hold whatever fails
        return _blocked(doc["request_id"], "INTERNAL_ERROR", type(exc).__name__)
    finally:
        if lock is not None:
            lock.release()


def _call(doc: dict, executor_ids: list[str], *, aeve_root, state_dir, python, command_prefix, timeout: float) -> dict:
    """One combined AEVE call with request v2 (v1 makes AEVE refuse 15+ executors outright; measured)."""
    aeve_request = adapter.build_aeve_request(
        request_id=doc["request_id"], root=doc["root"], base_revision=doc["base_revision"],
        changed_paths=doc["changed_paths"], executor_ids=executor_ids, criteria=doc.get("criteria"),
        iteration_of=doc.get("iteration_of"), allow_dirty=doc["purpose"] != "receipt")
    return adapter.run_review(aeve_request, aeve_root=aeve_root, state_dir=state_dir, python=python,
                              command_prefix=command_prefix, timeout=timeout,
                              require_clean_tree=doc["purpose"] == "receipt")


def _blocked(request_id: str, reason: str, detail: str) -> dict:
    safe_id = request_id if isinstance(request_id, str) and re.match(r"^[A-Za-z0-9._-]{1,128}$", request_id) else "invalid"
    safe_detail = "".join(ch for ch in str(detail)[:200] if ord(ch) >= 32 and ord(ch) != 127)
    if has_secret(safe_detail):
        safe_detail = "detail withheld: credential-shaped text"
    return {"schema_version": contracts.BLOCKED_SCHEMA, "request_id": safe_id, "status": "BLOCKED",
            "reason": re.sub(r"[^A-Z0-9_]", "_", str(reason).upper())[:64] or "UNSPECIFIED", "detail": safe_detail}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("review")
    cmd.add_argument("--request", required=True, type=pathlib.Path)
    cmd.add_argument("--aeve-root", required=True, type=pathlib.Path)
    cmd.add_argument("--table", required=True, type=pathlib.Path)
    cmd.add_argument("--state-dir", required=True, type=pathlib.Path)
    cmd.add_argument("--allowed-root", action="append", required=True)
    cmd.add_argument("--python", default=None)
    cmd.add_argument("--timeout", type=float, default=adapter.DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(json.dumps(_blocked("invalid", "UNREADABLE_REQUEST", "request file is not readable JSON"), sort_keys=True))
        return 2
    try:
        table, table_sha256 = load_table_with_digest(args.table)
    except (OSError, ValueError):
        print(json.dumps(_blocked(request.get("request_id", "invalid") if isinstance(request, dict) else "invalid",
                                  "UNREADABLE_TABLE", "role table is not readable JSON"), sort_keys=True))
        return 2
    result = review(request, table=table, aeve_root=args.aeve_root, state_dir=args.state_dir.resolve(),
                    allowed_roots=args.allowed_root, table_sha256=table_sha256, python=args.python,
                    timeout=args.timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("schema_version") == contracts.BLOCKED_SCHEMA:
        return 2
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
