"""v3 StaticAnalysis receipt builder (sprint U2, task U2-3).

Turns one validated U1 ``uc.role-result.v1`` role entry plus the analyzer outputs that
``analyzer_adapter`` already produces into (a) the UNSIGNED v3 StaticAnalysis receipt body and
(b) the UNSIGNED analyzer payload for ``analyzer_authority.sign_analyzer_evidence``. Both carry
the SAME bridge facts: ``bridge_facts_from_role_result`` is called exactly once and independent
deep copies of that dict are merged into the two outputs.

Deterministic, stdlib only. Never signs (signing stays in analyzer_authority), never calls a
model, never touches the network. The only git access is the adapter's own ``source_tree_digest``
(HEAD == candidate head, clean tree incl. untracked files, reviewed paths tracked regular files);
no new git invocation style is introduced here.

Every refusal is a ``ContractError`` whose message starts with a stable ``RB_*`` code; nothing else
escapes for malformed input (KeyError/TypeError/AttributeError/RecursionError are mapped).
"""

from __future__ import annotations

import copy
import dataclasses
import os
import re
from typing import Any, Mapping, Sequence

from ..uc.secret_patterns import has_secret  # side-effect free single definition; never copied here
from .analyzer_adapter import (
    AdapterError,
    AdapterResult,
    AnalysisReport,
    Limits,
    assemble_analyzer_payload,
    bridge_facts_from_role_result,
    source_tree_digest,
    static_analysis_fields,
)
from .analyzer_authority import MIN_NONCE_CHARS, validate_analyzer_payload
from .contracts import ContractError, _req_hex, _req_plain_repo_path, derive_result, validate_receipt

_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_RFC3339_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")
_ID_FIELDS = (
    "receipt_id", "task_id", "slot", "runner_id", "resolved_model", "invocation_id", "run_id",
)
# adapter codes that mean "the path list itself is unacceptable"; every other adapter code is tree state.
_PATH_CODES = frozenset({
    "SCOPE_INVALID", "SCOPE_PATH_REFUSED", "SCOPE_GLOB_REFUSED", "SCOPE_DUPLICATE", "SCOPE_UNSORTED",
    "SCOPE_CASE_MISMATCH",
})
_MAPPED = (KeyError, TypeError, AttributeError, ValueError, RecursionError)


def _refuse(code: str, message: str) -> ContractError:
    return ContractError(f"{code}: {message}")


def _walk_strings(value: Any):
    """Yield every string VALUE (keys are fixed contract names) in nested containers."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_strings(item)


def _refuse_secrets(where: str, value: Any) -> None:
    try:
        for text in _walk_strings(value):
            if has_secret(text):
                raise _refuse("RB_SECRET_LIKE_VALUE", f"{where} contains a value that looks like a secret")
    except RecursionError as exc:
        raise _refuse("RB_ARG_INVALID", f"{where} is nested too deeply to scan") from exc


def _path_list(value: object, name: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or not value:
        raise _refuse("RB_PATHS_INVALID", f"{name} must be a non-empty list of paths")
    for index, path in enumerate(value):
        try:
            _req_plain_repo_path(path, f"{name}[{index}]")
        except ContractError as exc:
            raise _refuse("RB_PATHS_INVALID", str(exc)) from exc
    if len(set(value)) != len(value):
        raise _refuse("RB_PATHS_INVALID", f"{name} must not contain duplicates")
    return list(value)


def _check_scalars(scalars: Mapping[str, Any], candidate_head: Any, manifest_sha256: Any, role_sha256: Any,
                   epoch: Any, attempt: Any, prev: Any, covered_acceptance: Any, created_at: Any) -> None:
    try:
        _req_hex(candidate_head, "candidate_head", 40)
        _req_hex(manifest_sha256, "manifest_sha256", 64)
        _req_hex(role_sha256, "role_sha256", 64)
    except ContractError as exc:
        raise _refuse("RB_ARG_INVALID", str(exc)) from exc
    for name in _ID_FIELDS:
        value = scalars[name]
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            raise _refuse("RB_ARG_INVALID", f"{name} must match [A-Za-z0-9._:-]{{1,128}}")
    nonce = scalars["nonce"]
    if not isinstance(nonce, str) or len(nonce) < MIN_NONCE_CHARS:
        raise _refuse("RB_ARG_INVALID", f"nonce must be a string of at least {MIN_NONCE_CHARS} characters")
    if not isinstance(created_at, str) or _RFC3339_UTC.fullmatch(created_at) is None:
        raise _refuse("RB_ARG_INVALID", "created_at must be an RFC 3339 UTC timestamp ending in 'Z'")
    for name, number in (("epoch", epoch), ("attempt", attempt)):
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise _refuse("RB_ARG_INVALID", f"{name} must be an int >= 1")
    if attempt == 1:
        if prev is not None:
            raise _refuse("RB_ARG_INVALID", "prev_receipt_sha256 must be null for attempt 1")
    else:
        try:
            _req_hex(prev, "prev_receipt_sha256", 64)
        except ContractError as exc:
            raise _refuse("RB_ARG_INVALID", str(exc)) from exc
    if (
        not isinstance(covered_acceptance, (list, tuple))
        or not all(isinstance(a, str) and _ID.fullmatch(a) is not None for a in covered_acceptance)
        or len(set(covered_acceptance)) != len(covered_acceptance)
    ):
        raise _refuse("RB_ARG_INVALID", "covered_acceptance must be a list of unique ids matching [A-Za-z0-9._:-]{1,128}")


def build_static_receipt(
    *,
    role_result: Mapping[str, Any],
    role: str,
    candidate_head: str,
    reviewed_paths: Sequence[str],
    required_paths: Sequence[str],
    snapshot_root: str | os.PathLike[str],
    adapter_result: AdapterResult,
    manifest_sha256: str,
    epoch: int,
    run_id: str,
    nonce: str,
    receipt_id: str,
    task_id: str,
    slot: str,
    attempt: int,
    prev_receipt_sha256: str | None,
    runner_id: str,
    role_sha256: str,
    resolved_model: str,
    invocation_id: str,
    created_at: str,
    covered_acceptance: Sequence[str],
    limits: Limits = Limits(),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(receipt_body, analyzer_payload)``, both unsigned.

    ``receipt_body`` is the exact v3 StaticAnalysis receipt field set minus ``signature`` (the
    caller signs it with ``signing.sign(..., label=RECEIPT_V3_LABEL)``); ``analyzer_payload`` is
    the argument for ``analyzer_authority.sign_analyzer_evidence``. ``required_paths`` is the
    diff-gate changed-path list; ``reviewed_paths`` must equal it exactly (no superset).

    Refusals (ContractError, message starts with the code):
      RB_ARG_INVALID          scalar/type problem: ids must match [A-Za-z0-9._:-]{1,128}, created_at
                              RFC 3339 UTC ('Z'), nonce >= MIN_NONCE_CHARS, int epoch/attempt >= 1,
                              prev hash null iff attempt == 1, 40/64 hex, covered_acceptance ids,
                              snapshot_root/adapter_result type, over-nested input
      RB_PATHS_INVALID        reviewed_paths / required_paths not a non-empty unique list of plain
                              repo-relative paths, or the adapter refused the path list itself
      RB_REQUIRED_PATH_UNCOVERED  a required path is not in reviewed_paths
      RB_REVIEWED_PATH_EXTRA  reviewed_paths holds a path that is not required (no superset)
      RB_SECRET_LIKE_VALUE    has_secret matches a string in the inputs or in the produced outputs
      RB_BRIDGE_REFUSED       bridge_facts_from_role_result refused (message carries its reason;
                              includes purpose != 'receipt' and a changed_paths_sha256 mismatch)
      RB_TREE_NOT_CLEAN       tree state: HEAD != candidate_head, dirty/untracked tree, a reviewed
                              path untracked or not a regular file, git failure
      RB_REPORT_TREE_MISMATCH the analyzer report is not bound to this reviewed set: adapter
                              candidate_head differs, tree digest of the reviewed paths differs from
                              adapter_result.source_tree_sha256 or the report, or sorted(reviewed) !=
                              report analysis_scope
      RB_ANALYZER_REFUSED     assemble_analyzer_payload/static_analysis_fields/payload validation refused
      RB_RECEIPT_INVALID      derive_result or validate_receipt (with a placeholder signature) refused
    Result is never hard-coded to PASS: it is ``derive_result`` of the body, and the value offered to it
    is INCONCLUSIVE whenever the role entry is not CLEAN, the role result or the report has any finding
    (any severity), or the role entry has a non-empty model_residual. Otherwise PASS is offered and
    derive_result decides (FULL coverage required).
    """
    # ---- argument shape (cheap, before any git or role-result work)
    scalars = {
        "receipt_id": receipt_id, "task_id": task_id, "slot": slot, "runner_id": runner_id,
        "resolved_model": resolved_model, "invocation_id": invocation_id, "run_id": run_id, "nonce": nonce,
    }
    _check_scalars(scalars, candidate_head, manifest_sha256, role_sha256, epoch, attempt, prev_receipt_sha256,
                   covered_acceptance, created_at)
    if not isinstance(adapter_result, AdapterResult):
        raise _refuse("RB_ARG_INVALID", "adapter_result must be an AdapterResult")
    if not isinstance(snapshot_root, (str, os.PathLike)):
        raise _refuse("RB_ARG_INVALID", "snapshot_root must be a path")
    if not isinstance(role, str) or not role:
        raise _refuse("RB_ARG_INVALID", "role must be a non-empty string")
    reviewed = _path_list(reviewed_paths, "reviewed_paths")
    required = _path_list(required_paths, "required_paths")
    if set(required) - set(reviewed):
        first = sorted(set(required) - set(reviewed))[0]
        raise _refuse("RB_REQUIRED_PATH_UNCOVERED", f"required path is not reviewed: {first}")
    if set(reviewed) - set(required):
        first = sorted(set(reviewed) - set(required))[0]
        raise _refuse("RB_REVIEWED_PATH_EXTRA", f"reviewed path is not required (no superset allowed): {first}")

    # ---- private copies, taken once; every later read uses these
    report_in = adapter_result.report
    if not isinstance(report_in, AnalysisReport):
        raise _refuse("RB_ANALYZER_REFUSED", "adapter_result has no analysis report")
    try:
        role_result = copy.deepcopy(role_result)
        report = AnalysisReport(body=copy.deepcopy(dict(report_in.body)))
        adapter_result = dataclasses.replace(adapter_result, report=report)
    except RecursionError as exc:
        raise _refuse("RB_ARG_INVALID", "input is nested too deeply") from exc
    except (TypeError, ValueError) as exc:
        raise _refuse("RB_ANALYZER_REFUSED", f"adapter report is not copyable ({type(exc).__name__})") from exc

    # ---- secrets in everything the caller handed us (outputs are scanned again below)
    _refuse_secrets("input", [role_result, role, list(scalars.values()), list(covered_acceptance), reviewed,
                              required, created_at])

    # ---- bridge facts: derived ONCE from the role result, then copied into both outputs
    try:
        bridge = bridge_facts_from_role_result(
            role_result, role, reviewed, expected_base_revision=candidate_head
        )
        entry = next(e for e in role_result["roles"] if e["role"] == role)  # exactly one: checked above
    except ContractError as exc:
        raise _refuse("RB_BRIDGE_REFUSED", str(exc)) from exc
    except _MAPPED as exc:
        raise _refuse("RB_BRIDGE_REFUSED", f"role result is malformed ({type(exc).__name__})") from exc

    # ---- clean working tree for the reviewed set at the candidate head (adapter's git approach)
    try:
        tree = source_tree_digest(os.fspath(snapshot_root), sorted(reviewed), candidate_head, limits)
    except AdapterError as exc:
        code = "RB_PATHS_INVALID" if exc.code in _PATH_CODES else "RB_TREE_NOT_CLEAN"
        raise _refuse(code, str(exc)) from exc
    except (TypeError, ValueError, OSError) as exc:
        raise _refuse("RB_TREE_NOT_CLEAN", f"tree check failed ({type(exc).__name__})") from exc

    # ---- bind the analyzer report to this reviewed set and head
    if adapter_result.candidate_head != candidate_head:
        raise _refuse("RB_REPORT_TREE_MISMATCH", "adapter_result is bound to a different candidate head")
    try:
        fields = static_analysis_fields(report)  # called once; feeds the receipt body
        payload = assemble_analyzer_payload(
            adapter_result,
            manifest_sha256=manifest_sha256,
            run_id=run_id,
            nonce=nonce,
            candidate_head=candidate_head,
            epoch=epoch,
            bridge=copy.deepcopy(bridge),
        )
    except AdapterError as exc:
        raise _refuse("RB_ANALYZER_REFUSED", str(exc)) from exc
    except ContractError as exc:
        raise _refuse("RB_ANALYZER_REFUSED", str(exc)) from exc
    except _MAPPED as exc:
        raise _refuse("RB_ANALYZER_REFUSED", f"analyzer report is malformed ({type(exc).__name__})") from exc
    if not (tree.sha256 == adapter_result.source_tree_sha256 == fields["source_tree_sha256"]):
        raise _refuse("RB_REPORT_TREE_MISMATCH", "reviewed-set tree digest differs from the analyzer's source tree")
    if sorted(reviewed) != list(fields["analysis_scope"]):
        raise _refuse("RB_REPORT_TREE_MISMATCH", "reviewed paths differ from the report analysis_scope")

    body: dict[str, Any] = {
        "receipt_id": receipt_id,
        "receipt_type": "StaticAnalysis",
        "task_id": task_id,
        "manifest_sha256": manifest_sha256,
        "slot": slot,
        "attempt": attempt,
        "prev_receipt_sha256": prev_receipt_sha256,
        "candidate_head": candidate_head,
        "epoch": epoch,
        "runner_id": runner_id,
        "role_sha256": role_sha256,
        "resolved_model": resolved_model,
        "invocation_id": invocation_id,
        "created_at": created_at,
        "contract_version": 3,
        "covered_acceptance": list(covered_acceptance),
        **fields,
        **copy.deepcopy(bridge),
    }
    # Only a CLEAN entry with no findings of any severity (role or report) and no model residual may be
    # offered PASS; derive_result then recomputes it (FULL coverage etc.). Everything else is INCONCLUSIVE,
    # which derive_result accepts as given and which can never be approving.
    clean = (
        entry["status"] == "CLEAN"
        and bridge["findings_count"] == 0
        and not bridge["model_residual"]
        and not fields["findings"]
    )
    body["result"] = "PASS" if clean else "INCONCLUSIVE"
    try:
        body["result"] = derive_result(body)
        validate_receipt({**body, "signature": "0" * 64})  # shape check only; the signature is a placeholder
    except ContractError as exc:
        raise _refuse("RB_RECEIPT_INVALID", str(exc)) from exc
    except _MAPPED as exc:
        raise _refuse("RB_RECEIPT_INVALID", f"receipt is malformed ({type(exc).__name__})") from exc
    try:
        validate_analyzer_payload(payload)
    except ContractError as exc:
        raise _refuse("RB_ANALYZER_REFUSED", str(exc)) from exc
    except _MAPPED as exc:
        raise _refuse("RB_ANALYZER_REFUSED", f"payload is malformed ({type(exc).__name__})") from exc

    _refuse_secrets("output", [body, payload])
    return body, payload
