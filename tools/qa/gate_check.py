"""S4-F: pure, typed verdict over one QA lane report record.

The runner (tools/qa/run.py) writes one append-only JSONL record per lane run. This
module decides whether such a record could ever support an approval. It never signs,
never waives and never changes the VST gate: it only answers APPROVABLE or
NON_APPROVING with typed reasons. Waivers stay governed by ADR-0001 and the
authoritative gate (tools/vst/gate.py); a NON_APPROVING record is simply not offered
to the gate as evidence (see approved_report_digests and the gate's existing
artifact_resolver hook).

Fail-closed rules (plan AC-14, AC-15): any missing, duplicate, skipped, xfailed,
failed, uncollected or unexpected ID, a result other than PASS, a stale or changed
head, a registry/hash/artifact mismatch, a dirty or unverified environment, an
unsupported or NOT_RUN category, or a secret / user-specific absolute path in the
record makes the record NON_APPROVING.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from tools.qa import run as _run
from tools.qa.registry import ValidatedRegistry
from tools.qa.report import canonical_json, normalized_report, sha256_bytes


APPROVABLE = "APPROVABLE"
NON_APPROVING = "NON_APPROVING"

NON_APPROVING_CODES = frozenset({
    "SCHEMA", "UNKNOWN_CATEGORY", "UNSUPPORTED_CATEGORY", "UNKNOWN_PROFILE",
    "PROFILE_NOT_EXECUTED", "RESULT_FAIL", "RESULT_NOT_RUN", "RESULT_INCONCLUSIVE",
    "RESULT_BLOCKED", "RESULT_UNSUPPORTED", "RESULT_UNKNOWN", "MISSING_ID", "UNKNOWN_ID",
    "DUPLICATE_ID", "NOT_RUN_IDS", "UNASSIGNED_IDS", "FAILED_IDS", "SKIPPED_IDS",
    "XFAIL_IDS", "UNCOLLECTED_IDS", "UNEXPECTED_CASES", "NOT_ALL_PASSED", "NO_EXECUTION",
    "EXIT_NONZERO", "STALE_HEAD", "REGISTRY_MISMATCH", "DIRTY_TREE", "STATE_CHANGED",
    "LOCK_MISSING", "DEPENDENCY_UNVERIFIED", "HASH_MISMATCH", "ARTIFACT_DIGEST_INVALID",
    "ARTIFACT_UNVERIFIED", "ARTIFACT_MISMATCH", "SECRET_OR_ABS_PATH",
})

REQUIRED_KEYS = (
    "schema_version", "category", "runtime_profile", "candidate_head", "head_after",
    "registry_sha256", "source_head", "lock_sha256", "expected_test_ids",
    "unassigned_test_ids", "not_run_test_reasons", "executed_node_ids", "passed_test_ids",
    "failed_test_ids", "skipped_test_ids", "xfail_test_ids", "unexpected_node_ids",
    "uncollected_test_ids", "exit_code", "profile_status", "dirty_tree",
    "git_state_unchanged", "evidence_unchanged", "dependency_content_verified_before",
    "dependency_content_verified_after", "artifact_paths", "artifact_digests",
    "artifact_sizes", "result", "command", "manifest_path", "normalized_sha256",
)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_ABS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/|\\\\)")
_ALLOWED_ABSOLUTE = frozenset({("interpreter", "executable")})


@dataclass(frozen=True)
class GateCheck:
    verdict: str
    reasons: tuple[tuple[str, str], ...]

    @property
    def approvable(self) -> bool:
        return self.verdict == APPROVABLE

    def codes(self) -> frozenset[str]:
        return frozenset(code for code, _ in self.reasons)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def select_record(lines: Iterable[bytes | str]) -> dict[str, Any]:
    """The authoritative record of an append-only report file is its last JSON line.

    Every non-empty line must decode as a JSON object without duplicate keys; any
    undecodable line refuses the whole file (a torn append never selects an older
    record silently).
    """
    records: list[dict[str, Any]] = []
    for raw in lines:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        text = text.strip()
        if not text:
            continue
        value = json.loads(text, object_pairs_hook=_no_duplicate_keys)
        if not isinstance(value, dict):
            raise ValueError("report line is not a JSON object")
        records.append(value)
    if not records:
        raise ValueError("report file holds no record")
    return records[-1]


def _is_hex_digest(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value)) and set(value) != {"0"}


def _strings(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key, path + ("<key>",))
            yield from _strings(item, path + (str(key),))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item, path)


def _secret_or_path_hits(report: dict[str, Any]) -> list[str]:
    hits: list[str] = []
    patterns = (_run._SENSITIVE, _run._BEARER, _run._TOKENS, _run._PEM_OPEN,
                _run._USER_PATH, _run._USER_PATH_FWD)
    for path, text in _strings(report):
        if any(pattern.search(text) for pattern in patterns):
            hits.append("/".join(path))
    for field in ("command", "artifact_paths", "manifest_path"):
        for path, text in _strings(report.get(field), (field,)):
            if _ABS_PATH.match(text) and path[:2] not in _ALLOWED_ABSOLUTE:
                hits.append("/".join(path))
    return sorted(set(hits))


def _dups(values: list[Any]) -> bool:
    return len(values) != len(set(values))


def check_report(
    report: Any,
    registry: ValidatedRegistry,
    *,
    expected_head: str,
    artifact_bytes: Mapping[str, bytes] | None = None,
) -> GateCheck:
    """Return APPROVABLE only if every rule below holds; otherwise list every failure."""
    reasons: list[tuple[str, str]] = []

    def fail(code: str, detail: str) -> None:
        assert code in NON_APPROVING_CODES, code
        reasons.append((code, detail))

    if not isinstance(report, dict):
        return GateCheck(NON_APPROVING, (("SCHEMA", "report is not an object"),))
    missing = [key for key in REQUIRED_KEYS if key not in report]
    if missing or report.get("schema_version") != 3:
        return GateCheck(NON_APPROVING, (("SCHEMA", f"schema_version 3 with keys required: missing {missing}"),))

    category, profile = report["category"], report["runtime_profile"]
    if category not in registry.category_profile_test_ids:
        return GateCheck(NON_APPROVING, (("UNKNOWN_CATEGORY", "category is not in the registry"),))
    status = registry.data["categories"].get(category, {}).get("status")
    if status not in {"SUPPORTED", "AGGREGATE"}:
        fail("UNSUPPORTED_CATEGORY", f"category status is {status}")
    registry_expected = registry.category_profile_test_ids[category].get(profile)
    if registry_expected is None:
        return GateCheck(NON_APPROVING, tuple(reasons) + (("UNKNOWN_PROFILE", "runtime profile unknown for the category"),))
    if report["profile_status"].get(profile) != "EXECUTED":
        fail("PROFILE_NOT_EXECUTED", f"profile {profile} was not executed")

    result = report["result"]
    if result != "PASS":
        known = {"FAIL", "NOT_RUN", "INCONCLUSIVE", "BLOCKED", "UNSUPPORTED"}
        fail(f"RESULT_{result}" if result in known else "RESULT_UNKNOWN", f"result is {result}")
    if report["exit_code"] != 0:
        fail("EXIT_NONZERO", f"exit code is {report['exit_code']}")

    expected, passed = report["expected_test_ids"], report["passed_test_ids"]
    if not (isinstance(expected, list) and isinstance(passed, list)):
        return GateCheck(NON_APPROVING, tuple(reasons) + (("SCHEMA", "ID lists are malformed"),))
    for name in ("expected_test_ids", "passed_test_ids", "executed_node_ids"):
        if _dups(report[name]):
            fail("DUPLICATE_ID", f"{name} holds a duplicate")
    if set(registry_expected) - set(expected):
        fail("MISSING_ID", f"{len(set(registry_expected) - set(expected))} registered ID(s) absent from the report")
    if set(expected) - set(registry_expected):
        fail("UNKNOWN_ID", f"{len(set(expected) - set(registry_expected))} reported ID(s) not in the registry")
    if set(passed) - set(registry_expected):
        fail("UNKNOWN_ID", "a passed ID is not in the registry")
    if set(expected) - set(passed):
        fail("NOT_ALL_PASSED", f"{len(set(expected) - set(passed))} expected ID(s) did not pass")
    if not report["executed_node_ids"]:
        fail("NO_EXECUTION", "no test case was executed")

    if registry.category_not_run.get(category) or report["not_run_test_reasons"]:
        fail("NOT_RUN_IDS", "the category holds declared NOT_RUN selectors")
    if report["unassigned_test_ids"]:
        fail("UNASSIGNED_IDS", "selectors are not assigned to this runtime profile")
    for name, code in (
        ("failed_test_ids", "FAILED_IDS"), ("skipped_test_ids", "SKIPPED_IDS"),
        ("xfail_test_ids", "XFAIL_IDS"), ("uncollected_test_ids", "UNCOLLECTED_IDS"),
        ("unexpected_node_ids", "UNEXPECTED_CASES"),
    ):
        if report[name]:
            fail(code, f"{name} is not empty ({len(report[name])})")

    if report["candidate_head"] != expected_head or report["head_after"] != expected_head:
        fail("STALE_HEAD", "candidate head differs from the expected head or moved during the run")
    if report["registry_sha256"] != registry.sha256 or report["source_head"] != registry.data.get("source_head"):
        fail("REGISTRY_MISMATCH", "report is bound to a different registry")
    dirty = report["dirty_tree"]
    if not isinstance(dirty, dict) or dirty.get("before") is not False or dirty.get("after") is not False:
        fail("DIRTY_TREE", "the candidate tree was dirty before or after the run")
    if report["git_state_unchanged"] is not True or report["evidence_unchanged"] is not True:
        fail("STATE_CHANGED", "git state or earlier evidence changed during the run")
    if not _is_hex_digest(report["lock_sha256"]):
        fail("LOCK_MISSING", "dependency lock digest is absent or invalid")
    if report["dependency_content_verified_before"] is not True or report["dependency_content_verified_after"] is not True:
        fail("DEPENDENCY_UNVERIFIED", "dependency content was not verified before and after")

    try:
        recomputed = sha256_bytes(canonical_json(normalized_report(report)))
    except (TypeError, ValueError):
        recomputed = None
    if recomputed != report["normalized_sha256"]:
        fail("HASH_MISMATCH", "normalized_sha256 does not match the record content")

    digests, sizes = report["artifact_digests"], report["artifact_sizes"]
    if not isinstance(digests, dict) or not digests or not all(_is_hex_digest(v) for v in digests.values()):
        fail("ARTIFACT_DIGEST_INVALID", "artifact digests are missing, malformed or all-zero")
    elif artifact_bytes is None:
        fail("ARTIFACT_UNVERIFIED", "raw artifact bytes were not supplied for digest verification")
    else:
        for key, digest in digests.items():
            data = artifact_bytes.get(key)
            if data is None or sha256_bytes(data) != digest or (
                isinstance(sizes, dict) and sizes.get(key) != len(data)
            ):
                fail("ARTIFACT_MISMATCH", f"artifact {key} differs from the recorded digest or size")

    hits = _secret_or_path_hits(report)
    if hits:
        fail("SECRET_OR_ABS_PATH", f"secret-like value or absolute path in field(s): {', '.join(hits[:6])}")

    return GateCheck(NON_APPROVING if reasons else APPROVABLE, tuple(reasons))


def approved_report_digests(
    items: Iterable[tuple[str, bytes, GateCheck]],
) -> dict[str, str]:
    """Map report path to the sha256 of its raw bytes, only for APPROVABLE checks.

    Feed this mapping to the gate's existing artifact_resolver hook: a TestRun receipt
    that lists a QA report digest then verifies only for a report that passed
    check_report. This does not change the gate, its keys or its authority model.
    """
    return {path: sha256_bytes(raw) for path, raw, check in items if check.approvable}
