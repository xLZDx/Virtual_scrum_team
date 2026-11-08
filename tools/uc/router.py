"""Role router and result normalizer (sprint U1, tasks U1-6 and U1-7).

Resolves each requested role through the role table, sends one combined review to AEVE through
the isolated adapter, and normalizes the response into ``uc.role-result.v1``. The result carries
only enumerations, integers, hashes and validated paths; uncovered scope is reduced to short
tokens, so repository-controlled text cannot reach the orchestrator through it.

Entry command (U1-7):
    python tools/uc/router.py review --request <role-request.json> --aeve-root D:/Repo/AEVE \
        --table catalog/role_table.json --state-dir <dir> --allowed-root <repo root> [--allowed-root ...]
Prints a uc.role-result.v1 document, or a uc.blocked.v1 envelope when no result can be produced.
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

# Roles whose full job includes running tests; only their static part exists until sprint U3.
TEST_ROLE_NAMES = frozenset({
    "e2e-runner", "e2e-testing-contract", "functional-test-reviewer", "functional-testing",
    "tdd-guide", "pr-test-analyzer",
})
LOCK_WAIT_SECONDS = 30.0
LOCK_STALE_SECONDS = 600.0
_TOKEN_CLEAN = re.compile(r"[^a-z0-9_.-]+")
# Shapes of well-known credentials; text that matches is never copied into a result.
_SECRET = re.compile(
    r"sk_(?:live|test)_[A-Za-z0-9]+|sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{8,}|gh[pousr]_[A-Za-z0-9]{10,}"
    r"|xox[abprs]-[A-Za-z0-9-]+|AIza[0-9A-Za-z_-]{10,}|-----BEGIN"
    r"|(?i:secret|passwd|password|api[_-]?key|token)[=_:-]*[A-Za-z0-9]{8,}")
SEVERITY_RANK = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "NIT": 3}


def has_secret(text: object) -> bool:
    return _SECRET.search(str(text)) is not None
_EXECUTOR_STATUS = {"COMPLETE": "COMPLETE", "PARTIAL": "PARTIAL", "BLOCKED": "BLOCKED",
                    "NOT_COVERED": "NOT_COVERED", "NOT_RUN": "NOT_RUN"}


def to_token(text: object, fallback: str = "unspecified") -> str:
    """Reduce any text to a short lowercase token; nothing else from the text survives."""
    if has_secret(text):
        return "redacted"
    head = str(text).strip().lower()
    token = _TOKEN_CLEAN.sub("-", head).strip("-_.")[:64]
    return token if re.match(r"^[a-z0-9][a-z0-9_.-]{0,63}$", token) else fallback


def load_table(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _lookup(table: dict, name: str) -> dict | None:
    for entry in table["entries"]:  # agents sort before skills, so an agent wins a shared name
        if entry["name"] == name:
            return entry
    return None


def _acquire(state_dir: pathlib.Path, request_id: str, content_sha: str) -> pathlib.Path:
    """Take the per-request lock, then check the fingerprint while holding it."""
    directory = state_dir / "uc-requests"
    directory.mkdir(parents=True, exist_ok=True)
    seen = directory / f"{request_id}.sha256"
    lock = directory / f"{request_id}.lock"
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    while True:
        try:
            os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
                    lock.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise adapter.AdapterBlocked("REQUEST_LOCKED", "another run with this request_id is in progress")
            time.sleep(0.1)
            continue
        try:
            if seen.is_file():
                if seen.read_text(encoding="utf-8").strip() != content_sha:
                    raise adapter.AdapterBlocked("REQUEST_ID_CONFLICT", "same request_id with different content")
            else:
                try:
                    seen.write_text(content_sha, encoding="utf-8")
                except OSError as exc:
                    raise adapter.AdapterBlocked("STATE_IO_ERROR", f"cannot write request state: {exc}") from exc
        except BaseException:
            try:
                lock.unlink()
            except OSError:
                pass
            raise
        return lock


def _map_finding(raw: object, where: str) -> dict:
    if not isinstance(raw, dict):
        raise adapter.AdapterBlocked("AEVE_CONTRACT_VIOLATION", f"{where} is not an object")
    severity = raw.get("severity")
    if severity not in contracts.SEVERITIES:
        raise adapter.AdapterBlocked("UNKNOWN_SEVERITY", f"{where}")
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    evidence_hash = evidence.get("line_sha256") or evidence.get("source_sha256")
    if not isinstance(evidence_hash, str) or not re.match(r"^[0-9a-f]{64}$", evidence_hash):
        evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode("utf-8")).hexdigest()
    line = raw.get("line", 0)
    column = raw.get("column", 0)
    finding = {
        "rule_id": to_token(raw.get("rule_id"), "unknown-rule"),
        "severity": severity,
        "path": raw.get("file"),
        "line": line if isinstance(line, int) and not isinstance(line, bool) and line >= 0 else 0,
        "column": column if isinstance(column, int) and not isinstance(column, bool) and column >= 0 else 0,
        "evidence_hash": evidence_hash,
    }
    try:
        contracts.validate_relative_posix_path(finding["path"], where)
    except contracts.ContractError as exc:
        raise adapter.AdapterBlocked("BAD_FINDING_PATH", exc.code) from exc
    if has_secret(finding["path"]):
        # Keep the finding, drop the credential-shaped name: the path is replaced by a stable digest.
        digest = hashlib.sha256(finding["path"].encode("utf-8")).hexdigest()[:16]
        finding["path"] = f"masked/{digest}"
    return finding


def normalize(role_request: dict, table: dict, response: dict | None, adapter_error: adapter.AdapterBlocked | None) -> dict:
    """Build the role result. ``response`` is the validated AEVE response, or None when blocked."""
    snapshot = response["snapshot_sha256"] if response else "0" * 64
    results_by_executor = {r.get("executor_id"): r for r in (response["results"] if response else [])
                           if isinstance(r, dict)}
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
        residual = ["model-judgment"] if klass == "LOCAL_PLUS_MODEL" else []
        if response is None:
            roles_out.append(_role_entry(role, canonical, klass, "BLOCKED", [], [], uncovered, residual))
            continue
        exec_out, findings, blocked = [], [], False
        for exec_id in executors:
            raw = results_by_executor.get(exec_id)
            status = _EXECUTOR_STATUS.get(raw.get("status"), "BLOCKED") if raw else "NOT_RUN"
            exec_out.append({"id": to_token(exec_id), "status": status, "snapshot_hash": snapshot})
            blocked = blocked or status == "BLOCKED"
            if raw:
                for item in raw.get("uncovered", []) if isinstance(raw.get("uncovered"), list) else []:
                    uncovered.append(to_token(item))
        for raw_finding in response["findings"]:
            if isinstance(raw_finding, dict) and raw_finding.get("executor_id") in executors:
                findings.append(_map_finding(raw_finding, f"finding[{role}]"))
        seen, unique = set(), []
        for f in findings:
            key = (f["rule_id"], f["path"], f["line"], f["column"])
            if key not in seen:
                seen.add(key)
                unique.append(f)
        unique.sort(key=lambda f: (SEVERITY_RANK[f["severity"]], f["path"], f["line"], f["column"], f["rule_id"]))
        if blocked:
            uncovered.append("executor-blocked")
        uncovered = sorted(set(uncovered))
        if blocked:
            status = "PARTIAL" if unique else "BLOCKED"  # findings are kept: they are real, but coverage is incomplete
        elif response and response.get("status") and response.get("status") != "COMPLETE":
            # AEVE returned PARTIAL/ERROR; report that coverage is incomplete
            if response.get("uncovered"):
                uncovered.extend([x for x in response.get("uncovered", []) if isinstance(x, str)])
            status = "PARTIAL"
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
    }


def _role_entry(role, canonical, klass, status, executors, findings, uncovered, residual) -> dict:
    return {"role": role, "canonical_role": canonical, "class": klass, "status": status, "executors": executors,
            "findings": findings, "uncovered": uncovered, "model_residual": residual}


def review(role_request: dict, *, table: dict, aeve_root: pathlib.Path, state_dir: pathlib.Path,
           allowed_roots: list[str], python: str | None = None, command_prefix: list[str] | None = None,
           timeout: float = adapter.DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Validate, check the AEVE pin, run one combined review and return a validated result."""
    request_id = role_request.get("request_id", "unknown") if isinstance(role_request, dict) else "unknown"
    try:
        doc = contracts.validate_request(role_request, allowed_roots, check_symlinks=True)
    except contracts.ContractError as exc:
        return _blocked(request_id, "INVALID_REQUEST", f"{exc.code} at {exc.where}")
    content_sha = hashlib.sha256(json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()
    lock = None
    try:
        record = aeve_probe.probe(aeve_root, python=python)
        pin = table.get("aeve_pin", {})
        if pin.get("head") != record["aeve_head"] or pin.get("matrix_digest_sha256") != record["matrix"]["digest_sha256"]:
            raise adapter.AdapterBlocked("AEVE_PIN_MISMATCH", "AEVE head or matrix digest differs from the role table pin")
        lock = _acquire(state_dir, doc["request_id"], content_sha)
        executor_ids = sorted({x for role in doc["roles"]
                               for e in [(_lookup(table, role) or {})] if e.get("coverage_state") == "COVERED_PARTIAL"
                               for x in e["executors"]})
        response = None
        if executor_ids:
            response = _collect(doc, executor_ids, aeve_root=aeve_root, state_dir=state_dir, python=python,
                                command_prefix=command_prefix, timeout=timeout)
        result = normalize(doc, table, response, None)
        contracts.validate_result(result)
        return result
    except (adapter.AdapterBlocked, aeve_probe.AeveProbeError) as exc:
        return _blocked(doc["request_id"], exc.reason, exc.detail)
    except contracts.ContractError as exc:
        return _blocked(doc["request_id"], "RESULT_CONTRACT_VIOLATION", f"{exc.code} at {exc.where}")
    finally:
        if lock is not None:
            try:
                lock.unlink()
            except OSError:
                pass


def _call(doc: dict, request_id: str, executor_ids: list[str], *, aeve_root, state_dir, python, command_prefix,
          timeout: float) -> dict:
    aeve_request = adapter.build_aeve_request(
        request_id=request_id, root=doc["root"], base_revision=doc["base_revision"],
        changed_paths=doc["changed_paths"], executor_ids=executor_ids, criteria=doc.get("criteria"),
        iteration_of=doc.get("iteration_of"), allow_dirty=doc["purpose"] != "receipt")
    return adapter.run_review(aeve_request, aeve_root=aeve_root, state_dir=state_dir, python=python,
                              command_prefix=command_prefix, timeout=timeout,
                              require_clean_tree=doc["purpose"] == "receipt")


def _collect(doc: dict, executor_ids: list[str], *, aeve_root, state_dir, python, command_prefix,
             timeout: float) -> dict:
    """One combined AEVE call (request v2). A refusal blocks the request; no per-executor retry loop.

    Measured: request v1 made AEVE refuse 15+ executors outright ("requires request v2"), and a
    per-executor retry loop cost 15-30 s per call, so the adapter sends v2, where an executor with
    missing input is reported NOT_COVERED inside a normal response instead of refusing the batch.
    """
    return _call(doc, doc["request_id"], executor_ids, aeve_root=aeve_root, state_dir=state_dir, python=python,
                 command_prefix=command_prefix, timeout=timeout)


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
        table = load_table(args.table)
    except (OSError, ValueError):
        print(json.dumps(_blocked(request.get("request_id", "invalid") if isinstance(request, dict) else "invalid",
                                  "UNREADABLE_TABLE", "role table is not readable JSON"), sort_keys=True))
        return 2
    result = review(request, table=table, aeve_root=args.aeve_root, state_dir=args.state_dir,
                    allowed_roots=args.allowed_root, python=args.python, timeout=args.timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("schema_version") == contracts.BLOCKED_SCHEMA:
        return 2
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
