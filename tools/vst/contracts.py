"""Strict validators for the Virtual Scrum Team control-plane contracts.

Contracts: TaskManifest, four receipt types (TestRun, StaticAnalysis,
IndependentReview, Documentation) and GateDecision.

Rules shared by every validator:
- the input must be a dict whose key set is EXACTLY the required key set
  (missing and unknown fields are both rejected);
- there are no defaults of any kind;
- bool is never accepted where an int is required;
- enums are closed (see RESULT, COVERAGE, VERDICT, RECEIPT_TYPES);
- hashes are lowercase hex (40 chars for git heads, 64 for sha256);
- dates are opaque non-empty strings (no timezone logic);
- validators never mutate their input and return a deep copy.

Standard library only; deterministic; no I/O.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

RESULT = frozenset({"PASS", "FAIL", "BLOCKED", "NOT_RUN", "INCONCLUSIVE"})
NON_APPROVING_RESULTS = frozenset({"BLOCKED", "INCONCLUSIVE", "NOT_RUN"})
COVERAGE = frozenset({"FULL", "PARTIAL", "NOT_COVERED"})
VERDICT = frozenset({"APPROVE", "APPROVED_WITH_WAIVER", "MODIFY", "NO_GO"})
RECEIPT_TYPES = frozenset(
    {"TestRun", "StaticAnalysis", "IndependentReview", "Documentation"}
)

# Verdicts a reviewer may sign inside an IndependentReview receipt.
REVIEW_SIGNED_VERDICTS = frozenset({"MODIFY", "NO_GO", "APPROVE"})

_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")

# Digest recorded for an artifact that does not exist after the commands ran.
MISSING_ARTIFACT_DIGEST = "0" * 64

MANIFEST_FIELDS = (
    "task_id",
    "project_id",
    "phase",
    "story_id",
    "base_head",
    "scope",
    "forbidden_actions",
    "owner_role",
    "role_sha256",
    "skills",
    "model_policy",
    "tools",
    "acceptance",
    "required_receipts",
    "author_principal",
    "required_tests",
    "allowed_commands",
    "required_rules",
    "timeout_sec",
    "cost_cap",
    "retry_cap",
)

# Reserved slot name for supervisor-written receipts (WORKER_LOST,
# RETRY_EXHAUSTED, BUDGET_EXCEEDED). Never a manifest slot; receipts in it are
# always Documentation receipts signed with the supervisor key.
SUPERVISOR_SLOT = "__supervisor__"

RECEIPT_COMMON_FIELDS = (
    "receipt_id",
    "receipt_type",
    "task_id",
    "manifest_sha256",
    "slot",
    "attempt",
    "prev_receipt_sha256",
    "candidate_head",
    "epoch",
    "runner_id",
    "role_sha256",
    "resolved_model",
    "invocation_id",
    "result",
    "created_at",
    "signature",
)

RECEIPT_TYPE_FIELDS = {
    "TestRun": (
        "expected_test_ids",
        "executed_test_ids",
        "skipped_test_ids",
        "xfail_test_ids",
        "commands",
        "covered_acceptance",
        "artifact_digests",
    ),
    "StaticAnalysis": (
        "coverage",
        "covered_rules",
        "unsupported_rules",
        "covered_acceptance",
    ),
    "IndependentReview": (
        "reviewer_principal",
        "author_principal",
        "covered_acceptance",
        "findings",
        "signed_verdict",
    ),
    "Documentation": ("check_description", "covered_acceptance"),
}

GATE_DECISION_FIELDS = (
    "task_id",
    "candidate_head",
    "epoch",
    "required_receipt_hashes",
    "unresolved_findings",
    "human_approvals",
    "verdict",
    "waiver_record",
    "acceptance_unmet",
    "reasons",
)


class ContractError(ValueError):
    """Raised when an object violates a contract."""


# ---------------------------------------------------------------- primitives


def _check_keys(obj: Any, required: tuple[str, ...], ctx: str) -> None:
    if not isinstance(obj, dict):
        raise ContractError(f"{ctx}: must be an object (dict)")
    for key in obj:
        if not isinstance(key, str):
            raise ContractError(f"{ctx}: non-string key {key!r}")
    missing = sorted(set(required) - set(obj))
    if missing:
        raise ContractError(f"{ctx}: missing field(s): {', '.join(missing)}")
    unknown = sorted(set(obj) - set(required))
    if unknown:
        raise ContractError(f"{ctx}: unknown field(s): {', '.join(unknown)}")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _req_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name}: must be a non-empty string")
    return value


def _req_int(value: Any, name: str, minimum: int, maximum: int | None = None) -> int:
    if not _is_int(value):
        raise ContractError(f"{name}: must be an integer (bool is not accepted)")
    if value < minimum:
        raise ContractError(f"{name}: must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ContractError(f"{name}: must be <= {maximum}")
    return value


def _req_hex(value: Any, name: str, length: int) -> str:
    pattern = _HEX40 if length == 40 else _HEX64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ContractError(f"{name}: must be {length} lowercase hex characters")
    return value


def _req_enum(value: Any, allowed: frozenset[str], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ContractError(f"{name}: must be one of {sorted(allowed)}")
    return value


def _req_str_list(
    value: Any, name: str, *, nonempty: bool = False, unique: bool = False
) -> list[str]:
    if not isinstance(value, list):
        raise ContractError(f"{name}: must be a list")
    if nonempty and not value:
        raise ContractError(f"{name}: must not be empty")
    for index, item in enumerate(value):
        _req_str(item, f"{name}[{index}]")
    if unique and len(set(value)) != len(value):
        raise ContractError(f"{name}: must not contain duplicates")
    return value


def _validate_repo_path(value: Any, name: str) -> str:
    _req_str(value, name)
    if value != value.strip():
        raise ContractError(f"{name}: must not have surrounding whitespace")
    if value.startswith("/") or value.startswith("\\"):
        raise ContractError(f"{name}: must be repo-relative, not absolute")
    if ":" in value:
        raise ContractError(f"{name}: must not contain ':' (drive letter)")
    for segment in re.split(r"[\\/]", value):
        if segment == "":
            raise ContractError(f"{name}: must not contain empty path segments")
        if segment == "..":
            raise ContractError(f"{name}: must not contain '..'")
        if segment == ".":
            raise ContractError(f"{name}: must not contain '.' segments")
    return value


# ------------------------------------------------------------- canonical form


def canonical_bytes(obj: Any) -> bytes:
    """Canonical JSON bytes: sorted keys, compact separators, ASCII, UTF-8."""
    try:
        text = json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"canonical_bytes: not serialisable: {exc}") from exc
    return text.encode("utf-8")


def receipt_sha256(receipt: dict) -> str:
    """sha256 hex over canonical bytes of the FULL receipt (with signature)."""
    return hashlib.sha256(canonical_bytes(receipt)).hexdigest()


def manifest_sha256(manifest: dict) -> str:
    """sha256 hex over canonical bytes of the VALIDATED manifest.

    Raises ContractError when the manifest is invalid.
    """
    return hashlib.sha256(canonical_bytes(validate_task_manifest(manifest))).hexdigest()


def normalize_principal(value: Any) -> str:
    """Strip + casefold a principal name; empty after normalization is an error."""
    if not isinstance(value, str):
        raise ContractError("principal: must be a string")
    normalized = value.strip().casefold()
    if not normalized:
        raise ContractError("principal: must not be empty after normalization")
    return normalized


# ------------------------------------------------------------------ manifest


def validate_task_manifest(obj: Any) -> dict:
    """Validate a TaskManifest and return a deep copy."""
    _check_keys(obj, MANIFEST_FIELDS, "task_manifest")
    _req_str(obj["task_id"], "task_id")
    _req_str(obj["project_id"], "project_id")
    _req_int(obj["phase"], "phase", 1, 10)
    _req_str(obj["story_id"], "story_id")
    _req_hex(obj["base_head"], "base_head", 40)

    scope = obj["scope"]
    if not isinstance(scope, list) or not scope:
        raise ContractError("scope: must be a non-empty list")
    for index, path in enumerate(scope):
        _validate_repo_path(path, f"scope[{index}]")
    if len(set(scope)) != len(scope):
        raise ContractError("scope: must not contain duplicates")

    _req_str_list(obj["forbidden_actions"], "forbidden_actions", unique=True)
    _req_str(obj["owner_role"], "owner_role")
    _req_hex(obj["role_sha256"], "role_sha256", 64)
    _validate_skills(obj["skills"])
    _req_str(obj["model_policy"], "model_policy")
    _req_str_list(obj["tools"], "tools", unique=True)
    _req_str_list(obj["acceptance"], "acceptance", nonempty=True, unique=True)
    slot_types = _validate_required_receipts(obj["required_receipts"])
    normalize_principal(_req_str(obj["author_principal"], "author_principal"))
    _validate_required_tests(obj["required_tests"], slot_types, obj["acceptance"])
    _validate_allowed_commands(obj["allowed_commands"], slot_types)
    _validate_required_rules(obj["required_rules"], slot_types)
    _validate_slot_coverage(obj, slot_types)
    _req_int(obj["timeout_sec"], "timeout_sec", 1)
    _req_int(obj["cost_cap"], "cost_cap", 0)
    _req_int(obj["retry_cap"], "retry_cap", 0)
    return copy.deepcopy(obj)


def _validate_skills(skills: Any) -> None:
    if not isinstance(skills, list):
        raise ContractError("skills: must be a list")
    seen: set[str] = set()
    for index, skill in enumerate(skills):
        ctx = f"skills[{index}]"
        _check_keys(skill, ("id", "sha256"), ctx)
        skill_id = _req_str(skill["id"], f"{ctx}.id")
        _req_hex(skill["sha256"], f"{ctx}.sha256", 64)
        if skill_id in seen:
            raise ContractError(f"{ctx}.id: duplicate skill id {skill_id!r}")
        seen.add(skill_id)


def _validate_required_receipts(slots: Any) -> dict[str, str]:
    """Validate required_receipts; return {slot name: receipt_type}."""
    if not isinstance(slots, list) or not slots:
        raise ContractError("required_receipts: must be a non-empty list")
    seen: dict[str, str] = {}
    for index, slot in enumerate(slots):
        ctx = f"required_receipts[{index}]"
        _check_keys(slot, ("slot", "receipt_type"), ctx)
        name = _req_str(slot["slot"], f"{ctx}.slot")
        rtype = _req_enum(slot["receipt_type"], RECEIPT_TYPES, f"{ctx}.receipt_type")
        if name == SUPERVISOR_SLOT:
            raise ContractError(f"{ctx}.slot: {SUPERVISOR_SLOT!r} is a reserved slot name")
        if name in seen:
            raise ContractError(f"{ctx}.slot: duplicate slot {name!r}")
        seen[name] = rtype
    types = set(seen.values())
    if "TestRun" not in types:
        raise ContractError("required_receipts: must contain at least one TestRun slot")
    if "IndependentReview" not in types:
        raise ContractError(
            "required_receipts: must contain at least one IndependentReview slot"
        )
    return seen


def _slot_of_type(value: Any, slot_types: dict[str, str], rtype: str, ctx: str) -> str:
    slot = _req_str(value, f"{ctx}.slot")
    if slot_types.get(slot) != rtype:
        raise ContractError(f"{ctx}.slot: {slot!r} is not a {rtype} slot of required_receipts")
    return slot


def _validate_required_tests(
    tests: Any, slot_types: dict[str, str], acceptance: list[str]
) -> None:
    if not isinstance(tests, list):
        raise ContractError("required_tests: must be a list")
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(tests):
        ctx = f"required_tests[{index}]"
        _check_keys(item, ("slot", "test_id", "acceptance"), ctx)
        slot = _slot_of_type(item["slot"], slot_types, "TestRun", ctx)
        test_id = _req_str(item["test_id"], f"{ctx}.test_id")
        _req_str_list(item["acceptance"], f"{ctx}.acceptance", nonempty=True)
        for acc in item["acceptance"]:
            if acc not in acceptance:
                raise ContractError(
                    f"{ctx}.acceptance: {acc!r} is not in manifest acceptance"
                )
        if (slot, test_id) in seen:
            raise ContractError(f"{ctx}.test_id: duplicate test id {test_id!r} for slot {slot!r}")
        seen.add((slot, test_id))


def _validate_allowed_commands(commands: Any, slot_types: dict[str, str]) -> None:
    if not isinstance(commands, list):
        raise ContractError("allowed_commands: must be a list")
    for index, item in enumerate(commands):
        ctx = f"allowed_commands[{index}]"
        _check_keys(item, ("slot", "argv"), ctx)
        _slot_of_type(item["slot"], slot_types, "TestRun", ctx)
        _req_str_list(item["argv"], f"{ctx}.argv", nonempty=True)


def _validate_required_rules(rules: Any, slot_types: dict[str, str]) -> None:
    if not isinstance(rules, list):
        raise ContractError("required_rules: must be a list")
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(rules):
        ctx = f"required_rules[{index}]"
        _check_keys(item, ("slot", "rule_id"), ctx)
        slot = _slot_of_type(item["slot"], slot_types, "StaticAnalysis", ctx)
        rule_id = _req_str(item["rule_id"], f"{ctx}.rule_id")
        if (slot, rule_id) in seen:
            raise ContractError(f"{ctx}.rule_id: duplicate rule {rule_id!r} for slot {slot!r}")
        seen.add((slot, rule_id))


def _validate_slot_coverage(obj: dict, slot_types: dict[str, str]) -> None:
    """Every TestRun slot needs tests and commands; every StaticAnalysis slot rules."""
    test_slots = {t["slot"] for t in obj["required_tests"]}
    command_slots = {c["slot"] for c in obj["allowed_commands"]}
    rule_slots = {r["slot"] for r in obj["required_rules"]}
    for slot, rtype in slot_types.items():
        if rtype == "TestRun":
            if slot not in test_slots:
                raise ContractError(f"required_tests: TestRun slot {slot!r} has no test")
            if slot not in command_slots:
                raise ContractError(
                    f"allowed_commands: TestRun slot {slot!r} has no allowed command"
                )
        elif rtype == "StaticAnalysis" and slot not in rule_slots:
            raise ContractError(f"required_rules: StaticAnalysis slot {slot!r} has no rule")


# ------------------------------------------------------------------- receipts


def validate_receipt(obj: Any) -> dict:
    """Validate a receipt of any of the four types and return a deep copy."""
    if not isinstance(obj, dict):
        raise ContractError("receipt: must be an object (dict)")
    receipt_type = obj.get("receipt_type")
    if not isinstance(receipt_type, str) or receipt_type not in RECEIPT_TYPES:
        raise ContractError(f"receipt_type: must be one of {sorted(RECEIPT_TYPES)}")
    fields = RECEIPT_COMMON_FIELDS + RECEIPT_TYPE_FIELDS[receipt_type]
    _check_keys(obj, fields, f"receipt({receipt_type})")
    _validate_common(obj)
    _TYPE_VALIDATORS[receipt_type](obj)
    if obj["slot"] == SUPERVISOR_SLOT and receipt_type != "Documentation":
        raise ContractError(
            f"slot: {SUPERVISOR_SLOT!r} is reserved for Documentation receipts"
        )
    return copy.deepcopy(obj)


def _validate_common(obj: dict) -> None:
    _req_str(obj["receipt_id"], "receipt_id")
    _req_str(obj["task_id"], "task_id")
    _req_hex(obj["manifest_sha256"], "manifest_sha256", 64)
    _req_str(obj["slot"], "slot")
    attempt = _req_int(obj["attempt"], "attempt", 1)
    prev = obj["prev_receipt_sha256"]
    if attempt == 1:
        if prev is not None:
            raise ContractError("prev_receipt_sha256: must be null when attempt == 1")
    else:
        _req_hex(prev, "prev_receipt_sha256", 64)
    _req_hex(obj["candidate_head"], "candidate_head", 40)
    _req_int(obj["epoch"], "epoch", 1)
    _req_str(obj["runner_id"], "runner_id")
    _req_hex(obj["role_sha256"], "role_sha256", 64)
    _req_str(obj["resolved_model"], "resolved_model")
    _req_str(obj["invocation_id"], "invocation_id")
    _req_enum(obj["result"], RESULT, "result")
    _req_str(obj["created_at"], "created_at")
    _req_hex(obj["signature"], "signature", 64)


def _validate_commands(commands: Any) -> None:
    if not isinstance(commands, list) or not commands:
        raise ContractError("commands: must be a non-empty list")
    for index, command in enumerate(commands):
        ctx = f"commands[{index}]"
        _check_keys(command, ("argv", "exit_code"), ctx)
        _req_str_list(command["argv"], f"{ctx}.argv", nonempty=True)
        if not _is_int(command["exit_code"]):
            raise ContractError(f"{ctx}.exit_code: must be an integer")


def _validate_test_run(obj: dict) -> None:
    for name in (
        "expected_test_ids",
        "executed_test_ids",
        "skipped_test_ids",
        "xfail_test_ids",
        "covered_acceptance",
    ):
        _req_str_list(obj[name], name)
    _validate_commands(obj["commands"])
    _validate_artifact_digests(obj["artifact_digests"])


def _validate_artifact_digests(digests: Any) -> None:
    if not isinstance(digests, dict):
        raise ContractError("artifact_digests: must be an object (dict)")
    for path, digest in digests.items():
        if not isinstance(path, str) or not path.strip():
            raise ContractError("artifact_digests: keys must be non-empty strings")
        _req_hex(digest, f"artifact_digests[{path!r}]", 64)


def _validate_static_analysis(obj: dict) -> None:
    _req_enum(obj["coverage"], COVERAGE, "coverage")
    for name in ("covered_rules", "unsupported_rules", "covered_acceptance"):
        _req_str_list(obj[name], name)


def _validate_independent_review(obj: dict) -> None:
    normalize_principal(_req_str(obj["reviewer_principal"], "reviewer_principal"))
    normalize_principal(_req_str(obj["author_principal"], "author_principal"))
    _req_str_list(obj["covered_acceptance"], "covered_acceptance")
    _req_str_list(obj["findings"], "findings")
    _req_enum(obj["signed_verdict"], REVIEW_SIGNED_VERDICTS, "signed_verdict")


def _validate_documentation(obj: dict) -> None:
    _req_str(obj["check_description"], "check_description")
    _req_str_list(obj["covered_acceptance"], "covered_acceptance")


_TYPE_VALIDATORS = {
    "TestRun": _validate_test_run,
    "StaticAnalysis": _validate_static_analysis,
    "IndependentReview": _validate_independent_review,
    "Documentation": _validate_documentation,
}


# --------------------------------------------------------------- derive_result


def derive_result(receipt: dict) -> str:
    """Return what receipt['result'] MUST be, computed from the evidence fields.

    Expects a receipt that already passed validate_receipt.

    A given result of BLOCKED, INCONCLUSIVE or NOT_RUN is accepted as given for
    every receipt type: these results can never produce an approval, and the
    supervisor must be able to record WORKER_LOST / RETRY_EXHAUSTED / budget
    outcomes. A given PASS or FAIL is compared with the computed value.
    """
    receipt_type = receipt.get("receipt_type")
    given = receipt.get("result")
    if given in NON_APPROVING_RESULTS:
        return given
    if receipt_type == "TestRun":
        return _derive_test_run(receipt)
    if receipt_type == "StaticAnalysis":
        return _derive_static_analysis(receipt)
    if receipt_type == "IndependentReview":
        return _derive_independent_review(receipt)
    if receipt_type == "Documentation":
        return given if given in ("PASS", "FAIL") else "INCONCLUSIVE"
    raise ContractError(f"derive_result: unknown receipt_type {receipt_type!r}")


def _derive_test_run(receipt: dict) -> str:
    # A missing artifact after the run is recorded as the all-zero digest.
    if MISSING_ARTIFACT_DIGEST in receipt["artifact_digests"].values():
        return "FAIL"
    executed = set(receipt["executed_test_ids"])
    expected = set(receipt["expected_test_ids"])
    if not executed:
        return "INCONCLUSIVE"
    commands = receipt["commands"]
    ok = (
        bool(commands)
        and all(c["exit_code"] == 0 for c in commands)
        and bool(expected)
        and executed == expected
        and not receipt["skipped_test_ids"]
        and not receipt["xfail_test_ids"]
    )
    return "PASS" if ok else "FAIL"


def _derive_static_analysis(receipt: dict) -> str:
    if (
        receipt["coverage"] == "FULL"
        and not receipt["unsupported_rules"]
        and receipt["covered_rules"]
    ):
        return "PASS"
    return "INCONCLUSIVE"


def _derive_independent_review(receipt: dict) -> str:
    if (
        receipt["signed_verdict"] == "APPROVE"
        and normalize_principal(receipt["reviewer_principal"])
        != normalize_principal(receipt["author_principal"])
    ):
        return "PASS"
    return "FAIL"


# --------------------------------------------------------------- gate decision


def validate_gate_decision(obj: Any) -> dict:
    """Validate a GateDecision and return a deep copy.

    task_id and candidate_head are echoes of the gate inputs and are only
    required to be strings (the gate must be able to emit NO_GO for malformed
    inputs); epoch is an int >= 0.
    """
    _check_keys(obj, GATE_DECISION_FIELDS, "gate_decision")
    if not isinstance(obj["task_id"], str):
        raise ContractError("task_id: must be a string")
    if not isinstance(obj["candidate_head"], str):
        raise ContractError("candidate_head: must be a string")
    _req_int(obj["epoch"], "epoch", 0)
    hashes = obj["required_receipt_hashes"]
    if not isinstance(hashes, list):
        raise ContractError("required_receipt_hashes: must be a list")
    for index, value in enumerate(hashes):
        _req_hex(value, f"required_receipt_hashes[{index}]", 64)
    _req_str_list(obj["unresolved_findings"], "unresolved_findings")
    _req_str_list(obj["human_approvals"], "human_approvals")
    verdict = _req_enum(obj["verdict"], VERDICT, "verdict")
    waiver_record = obj["waiver_record"]
    if verdict == "APPROVED_WITH_WAIVER":
        _req_str(waiver_record, "waiver_record")
    elif waiver_record is not None:
        raise ContractError("waiver_record: must be null unless verdict is APPROVED_WITH_WAIVER")
    _req_str_list(obj["acceptance_unmet"], "acceptance_unmet")
    _req_str_list(obj["reasons"], "reasons")
    if verdict == "APPROVE" and (obj["reasons"] or obj["acceptance_unmet"]):
        raise ContractError("verdict APPROVE requires empty reasons and acceptance_unmet")
    return copy.deepcopy(obj)
