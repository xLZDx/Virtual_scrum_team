"""Pure, default-deny gate verdict function (BD-4, R-2, R-4).

evaluate(manifest, receipts, current_head, current_epoch, key, *,
supervisor_key, operator_key=None, waiver=None, artifact_resolver=None)
returns a GateDecision dict (it always passes validate_gate_decision). It
never raises for bad data, never mutates its inputs, does no I/O, and collects
ALL reasons instead of stopping at the first problem.

Keys: worker receipts are verified with `key`; receipts in the reserved
SUPERVISOR_SLOT with `supervisor_key`; the waiver with `operator_key` and
WAIVER_LABEL. Every key must be bytes of length >= 32 (operator_key may be
None, which makes any waiver unusable). `key`, `supervisor_key` and
`operator_key` (when given) must be pairwise distinct (bytes comparison),
otherwise the verdict is NO_GO.

Rules, in order:

1. Inputs. current_head 40 lowercase hex, current_epoch an int >= 1 (not
   bool), key and supervisor_key valid keys, keys pairwise distinct, receipts
   a list, manifest valid per validate_task_manifest. Any failure is a hard
   reason and the verdict is NO_GO. An invalid manifest returns immediately
   (slots are unknown).
2. Per-receipt checks (a), applied to EVERY receipt. A receipt is "good" only
   if it validates, belongs to manifest.task_id, carries manifest_sha256 ==
   manifest_sha256(manifest) and role_sha256 == manifest.role_sha256, has
   epoch <= current_epoch (epoch > current_epoch is the hard reason 'future
   epoch'; in SUPERVISOR_SLOT the marker is still kept so a terminal marker is
   never dropped), has a valid signature and has result ==
   derive_result(receipt). Otherwise a hard reason is recorded and the receipt
   is excluded. An OLDER epoch is not a reason: it is history. The head match
   and the artifact checks (rule 3) are NOT per-receipt checks: they apply
   only to the deciding receipt of a slot (rule 5).
3. Head and artifacts (f), on the DECIDING receipt of each real slot only (the
   latest attempt of the slot chain, once the chain is intact). Its
   candidate_head must equal current_head, else the hard reason 'stale head'
   and the slot is unmet. A deciding TestRun receipt with non-empty
   artifact_digests and no artifact_resolver is a hard reason 'artifact
   digests present but no artifact_resolver' (default deny); with a resolver,
   every (path, digest) must equal artifact_resolver(path); a mismatch, None
   or a raising resolver is a hard reason. A rejected deciding receipt leaves
   its slot unmet. Older attempts are history: no head or artifact reason; an
   older attempt whose head differs from current_head is listed in
   unresolved_findings as 'history attempt at other head: <slot> attempt <n>'.
   SUPERVISOR_SLOT markers are exempt from the head check entirely.
4. Slot matching. A good receipt whose slot is neither in
   manifest.required_receipts nor SUPERVISOR_SLOT is the hard reason
   'unlisted receipt'; a receipt type different from the slot's declared type
   is a hard 'receipt type mismatch'. Both are excluded.
5. Chains (b). Per real slot the chain is the good receipts of the slot
   ordered by attempt across ALL epochs. Attempts must be exactly 1..n and
   each prev_receipt_sha256 must equal receipt_sha256 of the previous attempt
   (hard reason otherwise). The chain is built from signature-valid, bound
   receipts BEFORE the head and artifact checks of rule 3, which then run on
   its latest attempt. The LATEST attempt decides the slot; it must have
   epoch == current_epoch, else the slot is unmet (soft 'slot needs a
   current-epoch attempt'). A latest result other than PASS is an unmet slot
   (soft). Every earlier attempt with a result other than PASS is listed in
   unresolved_findings as 'earlier failure retained: ...' (informational,
   does not block APPROVE).
6. Supervisor chain (c). Receipts in SUPERVISOR_SLOT form their own chain with
   the same chain rule. check_description WORKER_LOST adds the informational
   finding 'worker lost: attempt N'; BUDGET_EXCEEDED and RETRY_EXHAUSTED are
   hard, never-waivable 'terminal marker ...' reasons; any other description is
   a hard reason. Markers never count toward acceptance.
7. Per-type checks on the LATEST attempt of a slot, when it is from the current
   epoch (d, e):
   - TestRun: set(expected_test_ids) must equal the manifest's required test
     ids for the slot, every command argv must equal one of the slot's
     allowed_commands argv, and the receipt's covered_acceptance must be a
     subset of manifest.acceptance (all hard). Acceptance contributed by a
     PASS = union of the `acceptance` lists of the manifest's required tests
     of that slot, NOT what the receipt claims.
   - StaticAnalysis: covered_rules must be a superset of the manifest's
     required rules for the slot (else the slot is unmet, soft). Acceptance =
     covered_acceptance restricted to manifest.acceptance.
   - IndependentReview: normalized author_principal must equal the manifest's
     normalized author_principal (hard) and reviewer must differ from author
     after normalization (hard). Each entry of `findings` becomes
     'review finding: <text>' in unresolved_findings. Acceptance =
     covered_acceptance restricted to manifest.acceptance.
   - Documentation (only possible in a declared Documentation slot): never
     contributes acceptance coverage.
8. Acceptance. acceptance_unmet = manifest.acceptance ids not covered (manifest
   order); each is a soft reason.
9. Verdict.
   - NO_GO: bad inputs (including non-distinct keys) / invalid manifest /
     every deciding receipt of this task stale by head or by future epoch
     (supervisor markers and older attempts do not count either way).
   - APPROVE: no reasons at all and acceptance_unmet empty.
   - APPROVED_WITH_WAIVER: no hard reasons and a valid waiver (g): exact keys
     record_id, operator, task_id, epoch (int), head, manifest_sha256,
     waived_slots (list of str), waived_acceptance (list of str),
     expires_epoch (int), signature (64 hex); signature verifies with
     operator_key and WAIVER_LABEL; task_id, epoch (== current_epoch), head and
     manifest_sha256 match; current_epoch <= expires_epoch; waived items cover
     EVERY unmet slot and acceptance id. waiver_record = record_id and
     human_approvals = [operator]. A waiver is ignored when nothing is unmet; an
     unusable waiver adds a reason and the verdict stays MODIFY.
   - MODIFY: everything else (fixable gaps).

Hard reasons are never waivable (this includes terminal markers, artifact
digests without a resolver, broken chains and forged or invalid receipts);
soft reasons are the unmet slots and unmet acceptance ids.
"""

from __future__ import annotations

import hashlib

from typing import Any, Callable

from .contracts import (
    SUPERVISOR_SLOT,
    ContractError,
    derive_result,
    manifest_sha256,
    normalize_principal,
    TRUSTED_PARSER_CATALOG,
    receipt_sha256,
    validate_gate_decision,
    validate_receipt,
    validate_task_manifest,
    canonical_bytes,
    normalize_principal,
)
from .signing import (MIN_KEY_BYTES, RECEIPT_LABEL, RECEIPT_V2_LABEL, WAIVER_LABEL, REVIEWER_LABEL,
    REVIEWER_REGISTRY_LABEL, DIFF_GATE_LABEL, SIGNING_REQUEST_LABEL, verify)

_WAIVER_V1_FIELDS = (
    "record_id",
    "operator",
    "task_id",
    "epoch",
    "head",
    "manifest_sha256",
    "waived_slots",
    "waived_acceptance",
    "expires_epoch",
    "signature",
)
_WAIVER_V2_FIELDS = _WAIVER_V1_FIELDS[:-2] + ("waived_results",) + _WAIVER_V1_FIELDS[-2:]
_WAIVABLE_RESULTS = frozenset({"NOT_RUN", "INCONCLUSIVE", "BLOCKED"})

_NO_RESOLVER_REASON = "artifact digests present but no artifact_resolver"
_TERMINAL_MARKERS = ("BUDGET_EXCEEDED", "RETRY_EXHAUSTED")


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _key_ok(key: Any) -> bool:
    return isinstance(key, (bytes, bytearray)) and len(key) >= MIN_KEY_BYTES


def _reviewer_registry_ok(registry: Any, manifest: dict, operator_key: Any,
                          reviewer_keys: Any, hard: list[str]) -> dict[str, str]:
    """Validate signed registry and return normalized principal -> key id."""
    if not isinstance(registry, dict) or set(registry) != {"version", "entries", "signature"}:
        hard.append("reviewer registry missing or has invalid fields")
        return {}
    if not isinstance(registry["version"], str) or registry["version"] != manifest["reviewer_registry"]["version"]:
        hard.append("reviewer registry version does not match manifest")
        return {}
    entries = registry["entries"]
    if not isinstance(entries, list):
        hard.append("reviewer registry entries must be a list")
        return {}
    if not _key_ok(operator_key) or not verify(registry, operator_key, REVIEWER_REGISTRY_LABEL):
        hard.append("reviewer registry signature invalid")
        return {}
    digest = hashlib.sha256(canonical_bytes({"version": registry["version"], "entries": entries})).hexdigest()
    if digest != manifest["reviewer_registry"]["sha256"]:
        hard.append("reviewer registry digest does not match manifest")
    result: dict[str, str] = {}
    key_ids: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"principal", "key_id"}:
            hard.append(f"reviewer registry entry {i} has invalid fields")
            continue
        try:
            principal = normalize_principal(entry["principal"])
            key_id = entry["key_id"]
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("key_id must be non-empty")
            if principal in result or key_id in key_ids:
                hard.append("reviewer registry contains duplicate principal or key id")
                continue
            result[principal] = key_id
            key_ids.add(key_id)
        except Exception as exc:
            hard.append(f"reviewer registry entry {i} invalid: {type(exc).__name__}")
    author = normalize_principal(manifest["author_principal"])
    if author in result:
        hard.append("manifest author principal is registered as a reviewer")
    if not isinstance(reviewer_keys, dict):
        hard.append("reviewer_keys must map key ids to trusted key bytes")
    else:
        for key_id in key_ids:
            if not _key_ok(reviewer_keys.get(key_id)):
                hard.append(f"reviewer key {key_id!r} is not trusted")
    return result


def _build_decision(
    task_id: Any,
    head: Any,
    epoch: Any,
    verdict: str,
    *,
    hashes: list[str],
    findings: list[str],
    approvals: list[str],
    waiver_record: str | None,
    acceptance_unmet: list[str],
    reasons: list[str],
) -> dict:
    decision = {
        "task_id": task_id if isinstance(task_id, str) else "",
        "candidate_head": head if isinstance(head, str) else "",
        "epoch": epoch if _is_int(epoch) and epoch >= 0 else 0,
        "required_receipt_hashes": list(hashes),
        "unresolved_findings": list(findings),
        "human_approvals": list(approvals),
        "verdict": verdict,
        "waiver_record": waiver_record,
        "acceptance_unmet": list(acceptance_unmet),
        "reasons": list(reasons),
    }
    return validate_gate_decision(decision)


def _check_receipt(
    index: int,
    raw: Any,
    manifest: dict,
    manifest_hash: str,
    epoch: int,
    key: bytes,
    supervisor_key: bytes,
    reviewer_keys: dict[str, bytes],
    v2: bool,
    signer_key: bytes | None,
    hard: list[str],
) -> tuple[dict | None, bool, bool]:
    """Return (good_receipt_or_None, belongs_to_task, is_future_epoch).

    Checks contract, task, manifest and role binding, future epoch, signature
    and derived result. The head and artifact checks are NOT done here: they
    apply only to the deciding receipt of a slot (see evaluate). A future-epoch
    receipt is a hard reason and is excluded, except in SUPERVISOR_SLOT where
    the marker is kept (so a terminal marker is never dropped) and the hard
    reason alone is recorded.
    """
    label = f"receipt[{index}]"
    try:
        receipt = validate_receipt(raw)
    except ContractError as exc:
        hard.append(f"{label} invalid: {exc}")
        return None, False, False
    label = f"receipt[{index}] ({receipt['receipt_id']})"
    if receipt["task_id"] != manifest["task_id"]:
        hard.append(f"{label} belongs to another task {receipt['task_id']!r}")
        return None, False, False
    if receipt["manifest_sha256"] != manifest_hash:
        hard.append(f"{label} manifest_sha256 does not match the manifest")
        return None, True, False
    if (receipt.get("contract_version") == 2) != v2:
        hard.append(f"{label} contract version does not match manifest")
        return None, True, False
    if receipt["role_sha256"] != manifest["role_sha256"]:
        hard.append(f"{label} role_sha256 does not match the manifest")
        return None, True, False
    is_supervisor = receipt["slot"] == SUPERVISOR_SLOT
    future = False
    if receipt["epoch"] > epoch:
        hard.append(f"{label} future epoch: {receipt['epoch']} > {epoch}")
        future = True
        if not is_supervisor:
            return None, True, True
    if receipt["receipt_type"] == "IndependentReview" and v2:
        signing_key = reviewer_keys.get(receipt["reviewer_key_id"])
        signature_label = REVIEWER_LABEL
    elif receipt["receipt_type"] == "TestRun" and v2:
        signing_key = signer_key
        signature_label = None
    else:
        signing_key = supervisor_key if is_supervisor else key
        signature_label = RECEIPT_V2_LABEL if v2 else RECEIPT_LABEL
    if receipt["receipt_type"] == "TestRun" and v2:
        att = receipt["runner_attestation"]
        signed_request = {**att["request"], "signature": att["signature"]}
        signature_ok = (
            receipt["signature"] == att["signature"] and _key_ok(signing_key)
            and verify(signed_request, signing_key, SIGNING_REQUEST_LABEL)
        )
    else:
        signature_ok = bool(_key_ok(signing_key) and verify(receipt, signing_key, signature_label))
    if not signature_ok:
        hard.append(f"{label} invalid signature")
        return None, True, False
    derived = derive_result(receipt)
    if derived != receipt["result"]:
        hard.append(
            f"{label} result {receipt['result']} does not match derived result {derived}"
        )
        return None, True, False
    return receipt, True, future and not is_supervisor


def _check_artifacts(
    receipt: dict,
    hard: list[str],
    artifact_resolver: Callable[[str], str | None] | None,
) -> bool:
    """Artifact-digest check of a deciding TestRun receipt; False = rejected."""
    if receipt["receipt_type"] != "TestRun" or not receipt["artifact_digests"]:
        return True
    label = f"receipt {receipt['receipt_id']}"
    if artifact_resolver is None:
        if _NO_RESOLVER_REASON not in hard:
            hard.append(_NO_RESOLVER_REASON)
        return False
    for path, digest in receipt["artifact_digests"].items():
        try:
            current = artifact_resolver(path)
        except Exception as exc:  # resolver is caller code: default-deny
            hard.append(
                f"{label} artifact {path!r} cannot be resolved: "
                f"{type(exc).__name__}"
            )
            return False
        if current != digest:
            hard.append(
                f"{label} artifact {path!r} digest mismatch: "
                f"artifact changed or missing"
            )
            return False
    return True


def _group_by_slot(
    good: list[dict], slot_types: dict[str, str], hard: list[str]
) -> tuple[dict[str, list[dict]], list[dict]]:
    """Return (real-slot groups, supervisor receipts)."""
    grouped: dict[str, list[dict]] = {name: [] for name in slot_types}
    supervisor: list[dict] = []
    for receipt in good:
        slot = receipt["slot"]
        label = f"receipt {receipt['receipt_id']}"
        if slot == SUPERVISOR_SLOT:
            supervisor.append(receipt)
        elif slot not in slot_types:
            hard.append(f"unlisted receipt: {label} has slot {slot!r} not in manifest")
        elif receipt["receipt_type"] != slot_types[slot]:
            hard.append(
                f"receipt type mismatch: {label} is {receipt['receipt_type']} "
                f"but slot {slot!r} requires {slot_types[slot]}"
            )
        else:
            grouped[slot].append(receipt)
    return grouped, supervisor


def _chain_intact(
    slot: str, chain: list[dict], hard: list[str],
    verified_successor_attempts: set[int] | None = None,
) -> bool:
    attempts = [r["attempt"] for r in chain]
    present = set(attempts)
    skipped = set(range(1, max(attempts, default=0) + 1)) - present
    if (len(present) != len(attempts)
            or not skipped <= (verified_successor_attempts or set())):
        hard.append(
            f"attempt chain broken for slot {slot!r}: attempts {attempts} "
            "have an unproven gap"
        )
        return False
    for previous, current in zip(chain, chain[1:]):
        if current["prev_receipt_sha256"] != receipt_sha256(previous):
            hard.append(
                f"attempt chain broken for slot {slot!r}: attempt "
                f"{current['attempt']} prev_receipt_sha256 does not match attempt "
                f"{previous['attempt']}"
            )
            return False
    return True


def _check_supervisor_chain(
    supervisor: list[dict], findings: list[str], hard: list[str]
) -> None:
    chain = sorted(supervisor, key=lambda r: r["attempt"])
    if not chain:
        return
    _chain_intact(SUPERVISOR_SLOT, chain, hard)
    for marker in chain:
        text = marker["check_description"]
        if text == "WORKER_LOST":
            findings.append(f"worker lost: attempt {marker['attempt']}")
        elif text in _TERMINAL_MARKERS:
            hard.append(f"terminal marker {text} (supervisor attempt {marker['attempt']})")
        else:
            hard.append(
                f"unknown supervisor marker {text!r} (supervisor attempt "
                f"{marker['attempt']})"
            )


def _check_latest(
    slot: str,
    latest: dict,
    manifest: dict,
    findings: list[str],
    hard: list[str],
    soft: list[str],
    parser_catalog: Any,
    signer_key: bytes | None,
) -> tuple[bool, set[str]]:
    """Per-type checks on the latest current-epoch attempt.

    Returns (slot_ok, acceptance_contribution). slot_ok is False when a hard or
    soft problem makes the slot unmet; the contribution is only used when the
    result is PASS and slot_ok.
    """
    rtype = latest["receipt_type"]
    manifest_acceptance = set(manifest["acceptance"])
    label = f"slot {slot!r}"
    if rtype == "TestRun":
        required_ids = {
            t["test_id"] for t in manifest["required_tests"] if t["slot"] == slot
        }
        allowed = [c["argv"] for c in manifest["allowed_commands"] if c["slot"] == slot]
        ok = True
        if set(latest["expected_test_ids"]) != required_ids:
            hard.append(f"{label}: expected_test_ids differ from the manifest required tests")
            ok = False
        for command in latest["commands"]:
            if command["argv"] not in allowed:
                hard.append(f"{label}: command {command['argv']!r} is not in allowed_commands")
                ok = False
        if "contract_version" in latest:
            required_commands = [c for c in manifest["mandatory_commands"] if c["slot"] == slot]
            actual = {(tuple(r["argv"]), r["parser_id"], r["parser_version"], r["parser_sha256"])
                      for r in latest["parser_results"]}
            expected = {(tuple(c["argv"]), c["parser_id"], c["parser_version"], c["parser_sha256"])
                        for c in required_commands}
            ran = {tuple(c["argv"]) for c in latest["commands"]}
            if (actual != expected or ran != {tuple(c["argv"]) for c in required_commands}
                    or len(latest["commands"]) != len(required_commands)):
                hard.append(f"{label}: mandatory command/parser set does not match manifest")
                ok = False
            parser_results = latest["parser_results"]
            executed = {test_id for item in parser_results for test_id in item["parser_result"]["executed_test_ids"]}
            skipped = {test_id for item in parser_results for test_id in item["parser_result"]["skipped_test_ids"]}
            xfailed = {test_id for item in parser_results for test_id in item["parser_result"]["xfail_test_ids"]}
            if (executed != set(latest["executed_test_ids"]) or
                    skipped != set(latest["skipped_test_ids"]) or
                    xfailed != set(latest["xfail_test_ids"])):
                hard.append(f"{label}: parser outcomes do not match TestRun test ids")
                ok = False
            for entry in required_commands:
                parser_key = (entry["parser_id"], entry["parser_version"], entry["parser_sha256"])
                if parser_key not in parser_catalog:
                    hard.append(f"{label}: parser {parser_key!r} is not in the trusted built-in catalog")
                    ok = False
            dg = latest["diff_gate"]
            if (dg["manifest_sha256"] != latest["manifest_sha256"] or
                    dg["candidate_head"] != latest["candidate_head"] or
                    dg["verdict"] != "PASS" or not verify(dg, signer_key or b"", DIFF_GATE_LABEL)):
                hard.append(f"{label}: diff gate evidence is absent, stale, failing, or unsigned")
                ok = False
            att = latest["runner_attestation"]
            req = att["request"]
            body = {k: v for k, v in req.items() if k != "signature"}
            if (att["signature"] != latest["signature"] or
                req["task_id"] != latest["task_id"] or req["slot"] != slot or
                req["attempt"] != latest["attempt"] or req["epoch"] != latest["epoch"] or
                req["manifest_sha256"] != latest["manifest_sha256"] or
                req["candidate_head"] != latest["candidate_head"] or
                req["commands"] != latest["commands"] or
                req["parser_results"] != latest["parser_results"] or
                req["artifact_digests"] != latest["artifact_digests"] or
                not verify({**body, "signature": att["signature"]}, signer_key or b"", SIGNING_REQUEST_LABEL)):
                hard.append(f"{label}: runner signing attestation does not bind receipt evidence")
                ok = False
        if not set(latest["covered_acceptance"]) <= manifest_acceptance:
            hard.append(f"{label}: covered_acceptance contains ids outside the manifest")
            ok = False
        contribution: set[str] = set()
        for test in manifest["required_tests"]:
            if test["slot"] == slot:
                contribution.update(test["acceptance"])
        return ok, contribution
    if rtype == "StaticAnalysis":
        required_rules = {
            r["rule_id"] for r in manifest["required_rules"] if r["slot"] == slot
        }
        missing = sorted(required_rules - set(latest["covered_rules"]))
        if missing:
            soft.append(f"{label}: required rules not covered: {', '.join(missing)}")
            return False, set()
        return True, set(latest["covered_acceptance"]) & manifest_acceptance
    if rtype == "IndependentReview":
        for finding in latest["findings"]:
            findings.append(f"review finding: {finding}")
        ok = True
        try:
            author = normalize_principal(latest["author_principal"])
            reviewer = normalize_principal(latest["reviewer_principal"])
            if author != normalize_principal(manifest["author_principal"]):
                hard.append(f"{label}: review author_principal does not match the manifest")
                ok = False
            if reviewer == author:
                hard.append(f"{label}: reviewer_principal equals author_principal")
                ok = False
            if "contract_version" in latest and reviewer == normalize_principal(manifest["author_principal"]):
                ok = False
        except ContractError as exc:
            hard.append(f"{label}: principal invalid: {exc}")
            ok = False
        return ok, set(latest["covered_acceptance"]) & manifest_acceptance
    return True, set()


def _evaluate_waiver(
    waiver: Any,
    operator_key: Any,
    manifest: dict,
    manifest_hash: str,
    head: str,
    epoch: int,
    unmet_slots: list[str],
    unmet_acceptance: list[str],
    unmet_results: list[str | None],
    v2: bool,
) -> tuple[bool, str | None, str | None, list[str]]:
    """Return (covers, record_id, operator, problems)."""
    if not isinstance(waiver, dict):
        return False, None, None, ["waiver rejected: must be an object (dict)"]
    problems: list[str] = []
    if not all(isinstance(k, str) for k in waiver):
        return False, None, None, ["waiver rejected: non-string key"]
    expected_fields = _WAIVER_V2_FIELDS if v2 else _WAIVER_V1_FIELDS
    missing = sorted(set(expected_fields) - set(waiver))
    unknown = sorted(set(waiver) - set(expected_fields))
    if missing:
        problems.append(f"waiver rejected: missing field(s): {', '.join(missing)}")
    if unknown:
        problems.append(f"waiver rejected: unknown field(s): {', '.join(unknown)}")
    if problems:
        return False, None, None, problems
    for name in ("record_id", "operator", "task_id", "head", "manifest_sha256"):
        value = waiver[name]
        if not isinstance(value, str) or not value.strip():
            problems.append(f"waiver rejected: {name} must be a non-empty string")
    for name in ("epoch", "expires_epoch"):
        if not _is_int(waiver[name]):
            problems.append(f"waiver rejected: {name} must be an integer")
    for name in ("waived_slots", "waived_acceptance"):
        value = waiver[name]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            problems.append(f"waiver rejected: {name} must be a list of strings")
    if not unmet_results or any(
        result is None or result not in _WAIVABLE_RESULTS for result in unmet_results
    ):
        problems.append("waiver rejected: missing, failed, or rejected evidence cannot be waived")
    if v2:
        value = waiver["waived_results"]
        if (not isinstance(value, list) or not value or
                not all(isinstance(v, str) and v in _WAIVABLE_RESULTS for v in value)):
            problems.append("waiver rejected: waived_results must contain only NOT_RUN, INCONCLUSIVE, or BLOCKED")
        if isinstance(value, list) and not set(unmet_results) <= set(value):
            problems.append("waiver rejected: waived_results does not cover every unmet result")
    if not _is_hex(waiver["signature"], 64):
        problems.append("waiver rejected: signature must be 64 lowercase hex characters")
    if problems:
        return False, None, None, problems
    if not _key_ok(operator_key):
        return False, None, None, ["waiver rejected: no valid operator_key"]
    if not verify(waiver, operator_key, WAIVER_LABEL):
        return False, None, None, ["waiver rejected: invalid signature"]
    if waiver["task_id"] != manifest["task_id"]:
        problems.append("waiver rejected: waiver task_id != manifest task_id")
    if waiver["epoch"] != epoch:
        problems.append("waiver rejected: waiver epoch != current epoch")
    if waiver["head"] != head:
        problems.append("waiver rejected: waiver head != current head")
    if waiver["manifest_sha256"] != manifest_hash:
        problems.append("waiver rejected: waiver manifest_sha256 != manifest")
    if epoch > waiver["expires_epoch"]:
        problems.append("waiver rejected: expired (current epoch > expires_epoch)")
    for slot in unmet_slots:
        if slot not in waiver["waived_slots"]:
            problems.append(f"waiver rejected: slot {slot!r} is not waived")
    for acc in unmet_acceptance:
        if acc not in waiver["waived_acceptance"]:
            problems.append(f"waiver rejected: acceptance {acc!r} is not waived")
    if problems:
        return False, None, None, problems
    return True, waiver["record_id"], waiver["operator"], []


def evaluate(
    manifest: dict,
    receipts: list[dict],
    current_head: str,
    current_epoch: int,
    key: bytes,
    *,
    supervisor_key: bytes,
    operator_key: bytes | None = None,
    waiver: dict | None = None,
    artifact_resolver: Callable[[str], str | None] | None = None,
    reviewer_registry: dict | None = None,
    reviewer_keys: dict[str, bytes] | None = None,
    parser_catalog: dict | None = None,
    signer_key: bytes | None = None,
    event_key: bytes | None = None,
    verified_successor_attempts: dict[str, set[int]] | None = None,
) -> dict:
    """Compute the GateDecision for one task candidate. See module docstring.

    artifact_resolver(path) returns the CURRENT sha256 hex of the artifact at
    path (or None when it is missing). TestRun receipts carrying artifact
    digests are rejected (hard) when no resolver is given.
    """
    hard: list[str] = []
    soft: list[str] = []
    findings: list[str] = []
    hashes: list[str] = []
    fatal = False
    if parser_catalog is not None and parser_catalog != TRUSTED_PARSER_CATALOG:
        hard.append("parser_catalog must be the trusted built-in catalog")
    if verified_successor_attempts is not None and (
            not isinstance(verified_successor_attempts, dict)
            or any(not isinstance(slot, str) or not isinstance(attempts, set)
                   or any(not _is_int(attempt) or attempt < 1 for attempt in attempts)
                   for slot, attempts in verified_successor_attempts.items())):
        hard.append("verified_successor_attempts: malformed Store evidence")
        fatal = True
        verified_successor_attempts = None

    task_id = manifest.get("task_id") if isinstance(manifest, dict) else None

    if not _is_hex(current_head, 40):
        hard.append("current_head: must be 40 lowercase hex characters")
        fatal = True
    if not _is_int(current_epoch) or current_epoch < 1:
        hard.append("current_epoch: must be an integer >= 1")
        fatal = True
    if not _key_ok(key):
        hard.append(f"key: must be bytes of length >= {MIN_KEY_BYTES}")
        fatal = True
    if not _key_ok(supervisor_key):
        hard.append(f"supervisor_key: must be bytes of length >= {MIN_KEY_BYTES}")
        fatal = True
    if signer_key is not None and not _key_ok(signer_key):
        hard.append(f"signer_key: must be bytes of length >= {MIN_KEY_BYTES}")
        fatal = True
    if event_key is not None and not _key_ok(event_key):
        hard.append(f"event_key: must be bytes of length >= {MIN_KEY_BYTES}")
        fatal = True
    if not isinstance(receipts, list):
        hard.append("receipts: must be a list")
        fatal = True
    supplied = [("key", key), ("supervisor_key", supervisor_key)]
    if operator_key is not None:
        supplied.append(("operator_key", operator_key))
    if signer_key is not None:
        supplied.append(("signer_key", signer_key))
    if event_key is not None:
        supplied.append(("event_key", event_key))
    for i, (name_a, value_a) in enumerate(supplied):
        for name_b, value_b in supplied[i + 1:]:
            if (
                isinstance(value_a, (bytes, bytearray))
                and isinstance(value_b, (bytes, bytearray))
                and bytes(value_a) == bytes(value_b)
            ):
                hard.append(f"keys must be pairwise distinct: {name_a} equals {name_b}")
                fatal = True

    try:
        valid_manifest = validate_task_manifest(manifest)
    except ContractError as exc:
        hard.append(f"manifest invalid: {exc}")
        return _build_decision(
            task_id, current_head, current_epoch, "NO_GO",
            hashes=[], findings=[], approvals=[], waiver_record=None,
            acceptance_unmet=[], reasons=hard,
        )

    if fatal:
        return _build_decision(
            task_id, current_head, current_epoch, "NO_GO",
            hashes=[], findings=[], approvals=[], waiver_record=None,
            acceptance_unmet=list(valid_manifest["acceptance"]), reasons=hard,
        )

    manifest_hash = manifest_sha256(valid_manifest)
    is_v2 = valid_manifest.get("contract_version") == 2
    registry_map: dict[str, str] = {}
    trusted_reviewers = reviewer_keys or {}
    if is_v2:
        if not _key_ok(event_key):
            hard.append("v2 gate requires event_key to enforce trust-root distinctness")
        if not _key_ok(signer_key):
            hard.append("v2 gate requires a trusted signer_key")
        elif bytes(signer_key) in (bytes(v) for v in trusted_reviewers.values() if _key_ok(v)):
            hard.append("signer key must differ from reviewer keys")
        registry_map = _reviewer_registry_ok(reviewer_registry, valid_manifest, operator_key, trusted_reviewers, hard)
        all_reviewer_keys = [bytes(v) for v in trusted_reviewers.values() if _key_ok(v)]
        if len(set(all_reviewer_keys)) != len(all_reviewer_keys):
            hard.append("reviewer keys must be pairwise distinct")
        if any(bytes(k) in all_reviewer_keys for k in (key, supervisor_key, operator_key, signer_key, event_key) if _key_ok(k)):
            hard.append("reviewer keys must differ from worker, supervisor, operator, signer, and event keys")
    good: list[dict] = []
    own_count = 0
    stale_count = 0
    for index, raw in enumerate(receipts):
        receipt, own, future = _check_receipt(
            index, raw, valid_manifest, manifest_hash, current_epoch,
            bytes(key), bytes(supervisor_key), trusted_reviewers, is_v2,
            bytes(signer_key) if _key_ok(signer_key) else None, hard,
        )
        own_count += 1 if own else 0
        stale_count += 1 if future else 0
        if receipt is not None:
            good.append(receipt)

    slot_types = {
        s["slot"]: s["receipt_type"] for s in valid_manifest["required_receipts"]
    }
    grouped, supervisor = _group_by_slot(good, slot_types, hard)
    if is_v2:
        for recs in grouped.values():
            for rec in recs:
                if rec["receipt_type"] == "IndependentReview":
                    try:
                        principal = normalize_principal(rec["reviewer_principal"])
                    except ContractError:
                        continue
                    if registry_map.get(principal) != rec["reviewer_key_id"]:
                        hard.append(f"receipt {rec['receipt_id']} reviewer principal/key does not match signed registry")
    _check_supervisor_chain(supervisor, findings, hard)
    # Supervisor markers and older attempts are history, not deciding receipts:
    # they never count toward the "all receipts stale" test below.
    own_count -= len(supervisor)

    covered: set[str] = set()
    unmet_slots: list[str] = []
    unmet_results: list[str | None] = []
    for slot in slot_types:
        chain = sorted(grouped[slot], key=lambda r: r["attempt"])
        if not chain:
            soft.append(f"missing receipt for slot {slot!r}")
            unmet_slots.append(slot)
            unmet_results.append(None)
            continue
        own_count -= len(chain) - 1
        for earlier in chain[:-1]:
            if earlier["result"] != "PASS":
                findings.append(
                    f"earlier failure retained: {slot} attempt "
                    f"{earlier['attempt']} {earlier['result']}"
                )
            if earlier["candidate_head"] != current_head:
                findings.append(
                    f"history attempt at other head: {slot} attempt "
                    f"{earlier['attempt']}"
                )
        verified_gaps = (
            verified_successor_attempts.get(slot, set())
            if isinstance(verified_successor_attempts, dict) else set()
        )
        if not _chain_intact(slot, chain, hard, verified_gaps):
            continue
        latest = chain[-1]
        if latest["candidate_head"] != current_head:
            hard.append(
                f"receipt {latest['receipt_id']} stale head: candidate_head != "
                f"current head (slot {slot!r} attempt {latest['attempt']})"
            )
            stale_count += 1
            soft.append(
                f"slot {slot!r} needs an attempt at the current head (latest "
                f"attempt {latest['attempt']} is at another head)"
            )
            unmet_slots.append(slot)
            unmet_results.append(latest["result"])
            continue
        if not _check_artifacts(latest, hard, artifact_resolver):
            soft.append(
                f"slot {slot!r} latest attempt {latest['attempt']} rejected: "
                f"artifact check failed"
            )
            unmet_slots.append(slot)
            unmet_results.append(latest["result"])
            continue
        hashes.append(receipt_sha256(latest))
        if latest["epoch"] != current_epoch:
            soft.append(
                f"slot {slot!r} needs a current-epoch attempt (latest attempt "
                f"{latest['attempt']} is from epoch {latest['epoch']})"
            )
            unmet_slots.append(slot)
            unmet_results.append(latest["result"])
            continue
        slot_ok, contribution = _check_latest(
            slot, latest, valid_manifest, findings, hard, soft,
            TRUSTED_PARSER_CATALOG, signer_key,
        )
        if latest["result"] != "PASS":
            soft.append(
                f"slot {slot!r} latest attempt {latest['attempt']} "
                f"result {latest['result']}"
            )
            unmet_slots.append(slot)
            unmet_results.append(latest["result"])
            continue
        if not slot_ok:
            unmet_slots.append(slot)
            unmet_results.append(latest["result"])
            continue
        covered.update(contribution)

    if own_count > 0 and stale_count == own_count:
        fatal = True
        hard.append(
            "all deciding receipts for this task are stale (head mismatch or "
            "future epoch)"
        )

    acceptance_unmet = [a for a in valid_manifest["acceptance"] if a not in covered]
    for acc in acceptance_unmet:
        soft.append(f"acceptance not covered: {acc!r}")

    approvals: list[str] = []
    waiver_record: str | None = None
    if fatal:
        verdict = "NO_GO"
    elif not hard and not soft:
        verdict = "APPROVE"
    elif hard or waiver is None:
        verdict = "MODIFY"
    else:
        ok, record_id, operator, problems = _evaluate_waiver(
            waiver, operator_key, valid_manifest, manifest_hash, current_head,
            current_epoch, unmet_slots, acceptance_unmet, unmet_results, is_v2,
        )
        if ok and record_id is not None and operator is not None:
            verdict = "APPROVED_WITH_WAIVER"
            waiver_record = record_id
            approvals = [operator]
        else:
            verdict = "MODIFY"
            soft.extend(problems)

    return _build_decision(
        valid_manifest["task_id"], current_head, current_epoch, verdict,
        hashes=hashes, findings=findings, approvals=approvals,
        waiver_record=waiver_record, acceptance_unmet=acceptance_unmet,
        reasons=hard + soft,
    )
