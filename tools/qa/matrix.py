"""Validate exact-head S4 platform-matrix reports without executing tests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .registry import (
    ALL_CATEGORIES,
    RUNTIME_PROFILES,
    WSL_ROOT_PROFILE,
    RegistryError,
    ValidatedRegistry,
    git_root,
    validate_registry,
)
from .report import canonical_json, normalized_report, sha256_bytes


MATRIX_SCHEMA_VERSION = 1
MATRIX_PATH = "docs/sdlc/evidence/qa/matrix.report.jsonl"
MAX_REPORT_FILE_BYTES = 32 * 1024 * 1024
MAX_ARTIFACT_CHUNK_BYTES = 4 * 1024 * 1024
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_REFERENCE = re.compile(
    r"(?P<profile>[A-Za-z0-9.-]+):(?P<category>[A-Za-z0-9-]+):(?P<run_id>[A-Za-z0-9][A-Za-z0-9._-]{0,63})\Z"
)


class MatrixError(ValueError):
    """Raised when supplied matrix references cannot be validated safely."""


def _args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--manifest", default="docs/qa/categories.json")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--run-ref",
        action="append",
        required=True,
        help="profile:category:run-id; provide one for every assigned runnable category/profile pair",
    )
    parser.add_argument("--output-path", default=MATRIX_PATH)
    return parser.parse_args(argv)


def _expected_report_refs(registry: ValidatedRegistry) -> set[tuple[str, str]]:
    return {
        (profile, category)
        for profile in RUNTIME_PROFILES
        for category in sorted(ALL_CATEGORIES)
        if registry.category_profile_test_ids.get(category, {}).get(profile)
    }


def _parse_refs(values: list[str]) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for value in values:
        match = _REFERENCE.fullmatch(value)
        if match is None:
            raise MatrixError("run-ref must be profile:category:run-id with canonical values")
        profile = match.group("profile")
        category = match.group("category")
        run_id = match.group("run_id")
        if profile not in RUNTIME_PROFILES or category not in ALL_CATEGORIES or not _RUN_ID.fullmatch(run_id):
            raise MatrixError("run-ref contains an unknown profile/category or invalid run id")
        key = (profile, category)
        if key in result:
            raise MatrixError("more than one run-ref was supplied for a profile/category pair")
        result[key] = run_id
    return result


def _read_report(path: Path, run_id: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise MatrixError("category report path is missing or not a regular file")
    for parent in path.parents:
        if parent.is_symlink() or getattr(parent, "isjunction", lambda: False)():
            raise MatrixError("category report path crosses a link")
    info = path.stat()
    if info.st_nlink != 1 or info.st_size > MAX_REPORT_FILE_BYTES:
        raise MatrixError("category report file is linked or exceeds the input bound")
    matches: list[tuple[dict[str, Any], bytes]] = []
    try:
        for line in path.read_bytes().splitlines(keepends=True):
            if not line.endswith(b"\n"):
                raise MatrixError("category JSONL report has an incomplete final line")
            try:
                row = json.loads(line.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                raise MatrixError("category JSONL report contains invalid JSON") from None
            if isinstance(row, dict) and row.get("run_id") == run_id:
                matches.append((row, line))
    except OSError as exc:
        raise MatrixError(f"category report cannot be read ({type(exc).__name__})") from None
    if len(matches) != 1:
        raise MatrixError("run-id must identify exactly one report row in its category JSONL")
    return matches[0]


def _verify_artifacts(root: Path, category: str, report: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    expected_paths = {
        "report": f"docs/sdlc/evidence/qa/{category}.report.jsonl",
        "stdout": f"docs/sdlc/evidence/qa/{category}.stdout.txt",
        "stderr": f"docs/sdlc/evidence/qa/{category}.stderr.txt",
    }
    if report.get("artifact_paths") != expected_paths:
        return ["category report artifact paths do not match the fixed evidence contract"]
    ranges = report.get("artifact_ranges")
    digests = report.get("artifact_digests")
    sizes = report.get("artifact_sizes")
    if not isinstance(ranges, dict) or set(ranges) != {"stdout", "stderr"}:
        return ["category report artifact ranges are missing or malformed"]
    if not isinstance(digests, dict) or set(digests) != {"stdout", "stderr"}:
        return ["category report artifact digests are missing or malformed"]
    if not isinstance(sizes, dict) or set(sizes) != {"stdout", "stderr"}:
        return ["category report artifact sizes are missing or malformed"]
    for kind in ("stdout", "stderr"):
        value = ranges[kind]
        if not isinstance(value, dict) or set(value) != {"start", "end"}:
            reasons.append(f"{kind} range is malformed")
            continue
        start, end = value["start"], value["end"]
        digest = digests[kind]
        size = sizes[kind]
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end < start
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size != end - start
            or size > MAX_ARTIFACT_CHUNK_BYTES
            or not isinstance(digest, str)
            or _HEX64.fullmatch(digest) is None
        ):
            reasons.append(f"{kind} range, size, or digest fields are invalid")
            continue
        path = root / expected_paths[kind]
        current = root
        crossed_link = False
        for part in Path(expected_paths[kind]).parts:
            current = current / part
            if current.is_symlink() or getattr(current, "isjunction", lambda: False)():
                crossed_link = True
                break
        if crossed_link or not path.is_file() or path.stat().st_nlink != 1:
            reasons.append(f"{kind} artifact is missing or not a regular file")
            continue
        try:
            with path.open("rb") as handle:
                handle.seek(start)
                chunk = handle.read(size)
        except OSError:
            reasons.append(f"{kind} artifact cannot be read")
            continue
        if len(chunk) != size:
            reasons.append(f"{kind} range extends beyond the artifact")
            continue
        if hashlib.sha256(chunk).hexdigest() != digest:
            reasons.append(f"{kind} byte range digest does not match the report")
    return reasons


def _verify_case_accounting(expected: list[str], report: dict[str, Any]) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    expected_set = set(expected)
    for field in (
        "passed_test_ids", "failed_test_ids", "skipped_test_ids", "xfail_test_ids",
        "uncollected_test_ids",
    ):
        values = report.get(field)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            reasons.append(f"{field} is missing or malformed")
            continue
        if len(values) != len(set(values)):
            reasons.append(f"{field} contains duplicates")
    passed = report.get("passed_test_ids", [])
    if isinstance(passed, list) and set(passed) != expected_set:
        reasons.append("passing selector set does not exactly cover assigned expected selectors")
    for field in ("failed_test_ids", "skipped_test_ids", "xfail_test_ids", "uncollected_test_ids"):
        values = report.get(field)
        if isinstance(values, list) and values:
            reasons.append(f"assigned selectors include {field}")
    if report.get("unexpected_node_ids") != []:
        reasons.append("category report contains unexpected concrete nodes")
    if report.get("result") != "PASS":
        reasons.append(f"category result is non-approving: {report.get('result')}")
    if report.get("exit_code") != 0:
        reasons.append("category pytest exit code is not zero")
    capture = report.get("capture")
    if not isinstance(capture, dict) or any(
        capture.get(field) is not False
        for field in ("capture_incomplete", "timed_out", "stdout_truncated", "stderr_truncated")
    ):
        reasons.append("category output capture is incomplete, timed out, truncated, or unverified")
    rows = report.get("case_outcomes")
    cases_by_selector: dict[str, list[str]] = {test_id: [] for test_id in expected}
    node_ids: set[str] = set()
    if not isinstance(rows, list):
        reasons.append("concrete case outcomes are missing")
    else:
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"node_id", "selector_id", "outcome"}:
                reasons.append("concrete case outcome has invalid fields")
                continue
            node_id, selector_id, outcome = row["node_id"], row["selector_id"], row["outcome"]
            if not isinstance(node_id, str) or not node_id or node_id in node_ids:
                reasons.append("concrete node ids are invalid or duplicated")
                continue
            node_ids.add(node_id)
            if selector_id not in cases_by_selector:
                reasons.append("concrete node references an unassigned selector")
                continue
            if outcome != "passed":
                reasons.append("assigned concrete case did not pass")
            cases_by_selector[selector_id].append(outcome)
        missing_cases = sorted(test_id for test_id, outcomes in cases_by_selector.items() if not outcomes)
        if missing_cases:
            reasons.append("one or more assigned selectors have no concrete passing case")
    for field in ("collected_node_ids", "executed_node_ids"):
        values = report.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            reasons.append(f"{field} is missing or malformed")
        elif values != sorted(node_ids):
            reasons.append(f"{field} does not match the concrete case outcome nodes")
    return reasons, sorted(node_ids)


def _validate_run(
    root: Path,
    registry: ValidatedRegistry,
    profile: str,
    category: str,
    run_id: str,
) -> tuple[dict[str, Any], list[str]]:
    report_path = root / f"docs/sdlc/evidence/qa/{category}.report.jsonl"
    report, line = _read_report(report_path, run_id)
    expected = registry.category_profile_test_ids[category][profile]
    expected_unassigned = registry.category_profile_unassigned_ids[category][profile]
    expected_not_run = registry.category_profile_not_run[category][profile]
    expected_inventory = registry.category_inventory_ids[category]
    reasons: list[str] = []
    if report.get("schema_version") != 2:
        reasons.append("category report schema version is stale or unsupported")
    if report.get("category") != category or report.get("runtime_profile") != profile:
        reasons.append("category report category/runtime profile does not match its reference")
    if report.get("run_id") != run_id:
        reasons.append("category report run id does not match its reference")
    if report.get("candidate_head") != registry.candidate_head:
        reasons.append("category report candidate HEAD is stale")
    if report.get("registry_sha256") != registry.sha256:
        reasons.append("category report registry hash is stale")
    if report.get("lock_sha256") != hashlib.sha256((root / "tools/qa/requirements.lock").read_bytes()).hexdigest():
        reasons.append("category report dependency-lock hash is stale")
    if report.get("expected_test_ids") != expected:
        reasons.append("category report expected selectors do not match profile assignment")
    if report.get("inventory_test_ids") != expected_inventory:
        reasons.append("category report inventory selectors do not match the committed registry")
    if report.get("unassigned_test_ids") != expected_unassigned:
        reasons.append("category report unassigned selectors do not match the committed registry")
    if report.get("not_run_test_reasons") != expected_not_run:
        reasons.append("category report policy NOT_RUN rows do not match the committed registry")
    identity = report.get("interpreter")
    expected_identity = {
        "windows-cpython-3.14.3": ("CPython-3.14.3", "C:/Python314/python.exe", "3.14.3"),
        "wsl-ubuntu-24.04-cpython-3.12.3": ("CPython-3.12.3", "/usr/bin/python3.12", "3.12.3"),
        "wsl-ubuntu-24.04-root-harness": ("CPython-3.12.3", "/usr/bin/python3.12", "3.12.3"),
    }[profile]
    if not isinstance(identity, dict) or (identity.get("id"), identity.get("executable"), identity.get("version")) != expected_identity:
        reasons.append("category report interpreter identity does not match the approved profile")
    runtime_identity = report.get("runtime_identity")
    if profile == "windows-cpython-3.14.3":
        if runtime_identity != {"uid": None, "gid": None, "supplementary_groups": []}:
            reasons.append("Windows profile runtime identity fields are invalid")
    elif profile == "wsl-ubuntu-24.04-cpython-3.12.3":
        if runtime_identity != {"uid": 997, "gid": 988, "supplementary_groups": []}:
            reasons.append("unprivileged WSL profile identity is not UID 997/GID 988 with cleared groups")
    elif runtime_identity != {"uid": 0, "gid": 0, "supplementary_groups": []}:
        reasons.append("privileged WSL profile identity is not the bounded root harness identity")
    runtime_boundary = report.get("runtime_boundary")
    if profile == "windows-cpython-3.14.3":
        if runtime_boundary is not None:
            reasons.append("Windows report unexpectedly contains a WSL mount boundary")
    else:
        if (
            not isinstance(runtime_boundary, dict)
            or set(runtime_boundary) != {
                "candidate_root", "candidate_root_prefix", "mountinfo_sha256",
                "windows_drive_mounts_present",
            }
        ):
            reasons.append("WSL report lacks the exact distro-local candidate boundary")
        else:
            candidate_root = runtime_boundary["candidate_root"]
            candidate_prefix = runtime_boundary["candidate_root_prefix"]
            try:
                candidate_path = PurePosixPath(candidate_root)
                prefix_path = PurePosixPath(candidate_prefix)
                path_is_local = (
                    candidate_path.is_absolute()
                    and ".." not in candidate_path.parts
                    and prefix_path == PurePosixPath("/tmp/vst-s4-candidate")
                    and (candidate_path == prefix_path or prefix_path in candidate_path.parents)
                )
            except (TypeError, ValueError):
                path_is_local = False
            if not path_is_local:
                reasons.append("WSL candidate path is not beneath the fixed distro-local test root")
            if runtime_boundary.get("windows_drive_mounts_present") is not False:
                reasons.append("WSL report does not prove the Windows-drive mount scan was clear")
            if not isinstance(runtime_boundary.get("mountinfo_sha256"), str) or _HEX64.fullmatch(
                runtime_boundary["mountinfo_sha256"]
            ) is None:
                reasons.append("WSL report mountinfo digest is missing or invalid")
    if report.get("normalized_sha256") != sha256_bytes(canonical_json(normalized_report(report))):
        reasons.append("category report normalized digest does not match its content")
    reasons.extend(_verify_artifacts(root, category, report))
    accounting_reasons, node_ids = _verify_case_accounting(expected, report)
    reasons.extend(accounting_reasons)
    if expected_not_run:
        reasons.append(f"profile has {len(expected_not_run)} policy NOT_RUN assigned selectors")
    if profile == WSL_ROOT_PROFILE:
        proof = report.get("privileged_harness_preflight")
        if (
            not isinstance(proof, dict)
            or set(proof) != {
                "authority", "scope", "sha256", "run_nonce_sha256",
                "candidate_root", "mountinfo_sha256",
            }
            or proof.get("authority") != "local-qa-preflight-non-authoritative"
            or proof.get("scope") != (
                "local QA preflight only; not an S2 worker receipt or independent approval"
            )
            or not isinstance(proof.get("sha256"), str)
            or _HEX64.fullmatch(proof["sha256"]) is None
            or not isinstance(proof.get("run_nonce_sha256"), str)
            or _HEX64.fullmatch(proof["run_nonce_sha256"]) is None
            or not isinstance(runtime_boundary, dict)
            or proof.get("candidate_root") != runtime_boundary.get("candidate_root")
            or proof.get("mountinfo_sha256") != runtime_boundary.get("mountinfo_sha256")
        ):
            reasons.append("root-profile report lacks a validated run-bound local sandbox preflight hash")
    elif report.get("privileged_harness_preflight") is not None:
        reasons.append("unprivileged profile contains a privileged harness proof")
    return {
        "profile": profile,
        "category": category,
        "run_id": run_id,
        "report_line_sha256": sha256_bytes(line),
        "expected_test_ids": expected,
        "passed_test_ids": report.get("passed_test_ids", []),
        "failed_test_ids": report.get("failed_test_ids", []),
        "skipped_test_ids": report.get("skipped_test_ids", []),
        "policy_not_run_test_ids": sorted(expected_not_run),
        "runtime_boundary": runtime_boundary,
        "concrete_node_ids": node_ids,
        "reasons": sorted(set(reasons)),
        "result": "PASS" if not reasons else "FAIL",
    }, reasons


def _matrix_report(
    root: Path,
    registry: ValidatedRegistry,
    run_refs: dict[tuple[str, str], str],
    expected_refs: set[tuple[str, str]],
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": MATRIX_SCHEMA_VERSION,
        "sprint": "S4",
        "run_id": "",
        "candidate_head": registry.candidate_head,
        "registry_sha256": registry.sha256,
        "lock_sha256": hashlib.sha256((root / "tools/qa/requirements.lock").read_bytes()).hexdigest(),
        "runtime_profiles": list(RUNTIME_PROFILES),
        "expected_report_refs": [
            {"profile": profile, "category": category, "run_id": run_refs.get((profile, category))}
            for profile, category in sorted(expected_refs)
        ],
        "reports": [],
        "selector_coverage": [],
        "policy_not_run_test_ids": sorted(
            {
                test_id
                for category in ALL_CATEGORIES
                for test_id in registry.category_not_run.get(category, {})
            }
        ),
        "result": "BLOCKED",
        "reasons": [],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "normalized_sha256": None,
    }
    reasons: list[str] = []
    missing_refs = sorted(expected_refs - set(run_refs))
    extra_refs = sorted(set(run_refs) - expected_refs)
    if missing_refs:
        reasons.append("one or more assigned profile/category reports are not referenced")
    if extra_refs:
        reasons.append("run refs include a profile/category pair with no runnable assigned selectors")
    if reasons:
        report["reasons"] = reasons
        return report
    for profile, category in sorted(expected_refs):
        run_id = run_refs[(profile, category)]
        try:
            row, row_reasons = _validate_run(root, registry, profile, category, run_id)
        except (MatrixError, OSError, KeyError, TypeError) as exc:
            row = {
                "profile": profile,
                "category": category,
                "run_id": run_id,
                "result": "BLOCKED",
                "reasons": [f"report validation failed ({type(exc).__name__})"],
            }
            row_reasons = row["reasons"]
        report["reports"].append(row)
        reasons.extend(f"{profile}/{category}: {reason}" for reason in row_reasons)

    wsl_roots = {
        item.get("runtime_boundary", {}).get("candidate_root")
        for item in report["reports"]
        if item["profile"] in {"wsl-ubuntu-24.04-cpython-3.12.3", WSL_ROOT_PROFILE}
        and isinstance(item.get("runtime_boundary"), dict)
    }
    if len(wsl_roots) != 1:
        reasons.append("WSL profile reports do not share one exact distro-local candidate root")

    for category in sorted(registry.category_test_ids):
        for test_id in registry.category_inventory_ids[category]:
            profiles = [
                profile
                for profile in RUNTIME_PROFILES
                if test_id in registry.selectors_by_id
                and profile in registry.selectors_by_id[test_id]["runtime_profiles"]
            ]
            if category == "regression":
                continue
            if not profiles:
                reasons.append(f"{category}: required selector {test_id} has no runtime profile")
                policy_reason = registry.category_not_run.get(category, {}).get(test_id)
                if policy_reason is not None:
                    reasons.append(f"{category}: required selector {test_id} is policy NOT_RUN")
            for profile in profiles:
                if test_id in registry.category_profile_not_run.get(category, {}).get(profile, {}):
                    reasons.append(f"{category}/{profile}: required selector {test_id} is policy NOT_RUN")
                    continue
                ref = (profile, category)
                selected = next(
                    (item for item in report["reports"] if item["profile"] == profile and item["category"] == category),
                    None,
                )
                if selected is None or test_id not in selected.get("passed_test_ids", []):
                    reasons.append(f"{category}/{profile}: required selector {test_id} did not pass")
            report["selector_coverage"].append(
                {"category": category, "test_id": test_id, "assigned_profiles": profiles}
            )

    report["reasons"] = sorted(set(reasons))
    report["result"] = "PASS" if not report["reasons"] else "FAIL"
    return report


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    if not _RUN_ID.fullmatch(args.run_id):
        print("QA_MATRIX_RESULT BLOCKED: run-id is invalid")
        return 2
    if args.output_path != MATRIX_PATH:
        print("QA_MATRIX_RESULT BLOCKED: output path must match the fixed matrix artifact path")
        return 2
    try:
        root = git_root(args.repo_root)
        if root != Path(args.repo_root).resolve(strict=True):
            raise MatrixError("repo-root must be the candidate repository root")
        registry = validate_registry(root, args.manifest)
        run_refs = _parse_refs(args.run_ref)
        expected_refs = _expected_report_refs(registry)
        report = _matrix_report(root, registry, run_refs, expected_refs)
        report["run_id"] = args.run_id
        report["normalized_sha256"] = sha256_bytes(canonical_json(normalized_report(report)))
        output = root / MATRIX_PATH
        if not output.resolve(strict=False).is_relative_to(root):
            raise MatrixError("matrix output path escapes the candidate repository")
        current = root
        for part in Path(MATRIX_PATH).parts[:-1]:
            current = current / part
            if current.is_symlink() or getattr(current, "isjunction", lambda: False)():
                raise MatrixError("matrix output path crosses a link")
        if output.is_symlink() or (output.exists() and (not output.is_file() or output.stat().st_nlink != 1)):
            raise MatrixError("matrix output artifact is linked or not a regular file")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("ab") as handle:
            handle.write(canonical_json(report) + b"\n")
    except (MatrixError, RegistryError, OSError, ValueError, TypeError) as exc:
        print(f"QA_MATRIX_RESULT BLOCKED: {type(exc).__name__}: {exc}")
        return 2
    print(f"QA_MATRIX_RESULT {report['result']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":  # pragma: no cover - exercised through the native CLI lane
    raise SystemExit(main())
