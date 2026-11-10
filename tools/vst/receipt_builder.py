"""v3 StaticAnalysis receipt builder (sprint U2, task U2-3).

Turns one validated U1 ``uc.role-result.v1`` role entry plus the analyzer outputs that
``analyzer_adapter`` already produces into (a) the UNSIGNED v3 StaticAnalysis receipt body and
(b) the UNSIGNED analyzer payload for ``analyzer_authority.sign_analyzer_evidence``. Both carry
the SAME bridge facts: ``bridge_facts_from_role_result`` is called exactly once and independent
deep copies of that dict are merged into the two outputs.

Deterministic, stdlib only. Never signs (signing stays in analyzer_authority / signing.sign),
never calls a model, never touches the network. The only git access is the adapter's own
``source_tree_digest`` (HEAD == candidate head, clean tree incl. untracked files, reviewed paths
tracked regular files); no new git invocation style is introduced here.

Every refusal is a ``ContractError`` whose message starts with a stable ``RB_*`` code.
"""

from __future__ import annotations

import copy
import os
from typing import Any, Mapping, Sequence

from .analyzer_adapter import (
    AdapterError,
    AdapterResult,
    Limits,
    assemble_analyzer_payload,
    bridge_facts_from_role_result,
    source_tree_digest,
    static_analysis_fields,
)
from .contracts import ContractError, _req_hex, _req_plain_repo_path, derive_result

_STR_FIELDS = (
    "receipt_id", "task_id", "slot", "runner_id", "resolved_model", "invocation_id", "created_at",
    "run_id", "nonce",
)


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
    from ..uc.router import has_secret  # the single secret-shape definition; never copied here

    for text in _walk_strings(value):
        if has_secret(text):
            raise _refuse("RB_SECRET_LIKE_VALUE", f"{where} contains a value that looks like a secret")


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
    diff-gate changed-path list; every entry must lie inside ``reviewed_paths``.

    Refusals (ContractError, message starts with the code):
      RB_ARG_INVALID          a scalar argument has the wrong type/shape (non-empty str ids, int
                              epoch/attempt >= 1, prev hash null iff attempt == 1, 40/64 hex)
      RB_PATHS_INVALID        reviewed_paths / required_paths not a non-empty unique list of
                              plain repo-relative paths
      RB_REQUIRED_PATH_UNCOVERED  a required path is not in reviewed_paths
      RB_SECRET_LIKE_VALUE    router.has_secret matches any string in the role result, any
                              caller-supplied text, or any string of the produced outputs
      RB_BRIDGE_REFUSED       bridge_facts_from_role_result refused (message carries its reason)
      RB_TREE_NOT_CLEAN       adapter source_tree_digest refused the reviewed set (dirty or
                              untracked tree, HEAD != candidate_head, untracked/non-regular path)
      RB_ANALYZER_REFUSED     assemble_analyzer_payload refused (outcome not OK/PARTIAL, unknown
                              binding, head mismatch, bad bridge)
      RB_NON_CLEAN_PASS       defensive: a non-CLEAN role entry would have produced PASS
    A non-CLEAN (FINDINGS) role entry is not refused: ``result`` is then INCONCLUSIVE, which
    ``derive_result`` accepts as given and which can never be approving. For a CLEAN entry
    ``result`` is whatever ``derive_result`` computes (never hard-coded).
    """
    # ---- argument shape (cheap, before any git or role-result work)
    try:
        _req_hex(candidate_head, "candidate_head", 40)
        _req_hex(manifest_sha256, "manifest_sha256", 64)
        _req_hex(role_sha256, "role_sha256", 64)
    except ContractError as exc:
        raise _refuse("RB_ARG_INVALID", str(exc)) from exc
    scalars = {
        "receipt_id": receipt_id, "task_id": task_id, "slot": slot, "runner_id": runner_id,
        "resolved_model": resolved_model, "invocation_id": invocation_id, "created_at": created_at,
        "run_id": run_id, "nonce": nonce,
    }
    for name in _STR_FIELDS:
        if not isinstance(scalars[name], str) or not scalars[name]:
            raise _refuse("RB_ARG_INVALID", f"{name} must be a non-empty string")
    for name, number in (("epoch", epoch), ("attempt", attempt)):
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise _refuse("RB_ARG_INVALID", f"{name} must be an int >= 1")
    if attempt == 1:
        if prev_receipt_sha256 is not None:
            raise _refuse("RB_ARG_INVALID", "prev_receipt_sha256 must be null for attempt 1")
    else:
        try:
            _req_hex(prev_receipt_sha256, "prev_receipt_sha256", 64)
        except ContractError as exc:
            raise _refuse("RB_ARG_INVALID", str(exc)) from exc
    if (
        not isinstance(covered_acceptance, (list, tuple))
        or not all(isinstance(a, str) and a for a in covered_acceptance)
        or len(set(covered_acceptance)) != len(covered_acceptance)
    ):
        raise _refuse("RB_ARG_INVALID", "covered_acceptance must be a list of unique non-empty strings")
    reviewed = _path_list(reviewed_paths, "reviewed_paths")
    required = _path_list(required_paths, "required_paths")
    missing = sorted(set(required) - set(reviewed))
    if missing:
        raise _refuse("RB_REQUIRED_PATH_UNCOVERED", f"{len(missing)} required path(s) not reviewed; first: {missing[0]}")

    # ---- secrets in everything the caller handed us (outputs are scanned again below)
    _refuse_secrets("input", [role_result, role, list(scalars.values()), list(covered_acceptance), reviewed, required])

    # ---- bridge facts: derived ONCE from the role result, then copied into both outputs
    try:
        bridge = bridge_facts_from_role_result(
            role_result, role, reviewed, expected_base_revision=candidate_head
        )
    except ContractError as exc:
        raise _refuse("RB_BRIDGE_REFUSED", str(exc)) from exc
    entry = next(e for e in role_result["roles"] if e["role"] == role)  # exactly one: checked above

    # ---- clean working tree for the reviewed set at the candidate head (adapter's git approach)
    try:
        source_tree_digest(os.fspath(snapshot_root), sorted(reviewed), candidate_head, limits)
    except AdapterError as exc:
        raise _refuse("RB_TREE_NOT_CLEAN", str(exc)) from exc

    # ---- analyzer payload (unsigned) and receipt fields from the adapter's own helpers
    try:
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
    assert adapter_result.report is not None  # assemble_analyzer_payload refused otherwise
    fields = static_analysis_fields(adapter_result.report)

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
    # derive_result recomputes a given PASS/FAIL and accepts a non-approving given as is, so a
    # non-CLEAN entry can never be turned into PASS here.
    body["result"] = "PASS" if entry["status"] == "CLEAN" else "INCONCLUSIVE"
    body["result"] = derive_result(body)
    if body["result"] == "PASS" and entry["status"] != "CLEAN":
        raise _refuse("RB_NON_CLEAN_PASS", "a non-CLEAN role entry must not produce PASS")

    _refuse_secrets("output", [body, payload])
    return body, payload
