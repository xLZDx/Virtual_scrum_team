"""Pure, default-deny gate verdict function (BD-4, R-2, R-4).

evaluate(manifest, receipts, current_head, current_epoch, key, *,
supervisor_key, operator_key=None, waiver=None, artifact_resolver=None)
returns a GateDecision dict (it always passes validate_gate_decision). It
never raises for bad data, never mutates its inputs, does no I/O, and collects
ALL reasons instead of stopping at the first problem.

Keys: worker receipts are verified with `key`; receipts in the reserved
SUPERVISOR_SLOT with `supervisor_key`; the waiver with `operator_key` and
WAIVER_LABEL. Every key must be bytes of length >= 32 (operator_key may be
None, which makes any waiver unusable).

Rules, in order:

1. Inputs. current_head 40 lowercase hex, current_epoch an int >= 1 (not
   bool), key and supervisor_key valid keys, receipts a list, manifest valid
   per validate_task_manifest. Any failure is a hard reason and the verdict is
   NO_GO. An invalid manifest returns immediately (slots are unknown).
2. Per-receipt checks (a). A receipt is "good" only if it validates, belongs
   to manifest.task_id, carries manifest_sha256 == manifest_sha256(manifest)
   and role_sha256 == manifest.role_sha256, has candidate_head ==
   current_head, has epoch <= current_epoch (epoch > current_epoch is the hard
   reason 'future epoch'), has a valid signature and has result ==
   derive_result(receipt). Otherwise a hard reason is recorded and the receipt
   is excluded. An OLDER epoch is not a reason: it is history. If at least one
   receipt belongs to this task and ALL of those fail the head or future-epoch
   check, the verdict is NO_GO.
3. Artifacts (f). A good TestRun receipt with non-empty artifact_digests and
   no artifact_resolver is a hard reason 'artifact digests present but no
   artifact_resolver' (default deny) and is excluded. With a resolver, every
   (path, digest) must equal artifact_resolver(path); a mismatch, None or a
   raising resolver is a hard reason and the receipt is excluded.
4. Slot matching. A good receipt whose slot is neither in
   manifest.required_receipts nor SUPERVISOR_SLOT is the hard reason
   'unlisted receipt'; a receipt type different from the slot's declared type
   is a hard 'receipt type mismatch'. Both are excluded.
5. Chains (b). Per real slot the chain is the good receipts of the slot
   ordered by attempt across ALL epochs. Attempts must be exactly 1..n and
   each prev_receipt_sha256 must equal receipt_sha256 of the previous attempt
   (hard reason otherwise). The LATEST attempt decides the slot; it must have
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
   - NO_GO: bad inputs / invalid manifest / every receipt of this task stale
     by head or by future epoch.
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

from typing import Any, Callable

from .contracts import (
    SUPERVISOR_SLOT,
    ContractError,
    derive_result,
    manifest_sha256,
    normalize_principal,
    receipt_sha256,
    validate_gate_decision,
    validate_receipt,
    validate_task_manifest,
)
from .signing import MIN_KEY_BYTES, RECEIPT_LABEL, WAIVER_LABEL, verify

_WAIVER_FIELDS = (
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
    head: str,
    epoch: int,
    key: bytes,
    supervisor_key: bytes,
    hard: list[str],
    artifact_resolver: Callable[[str], str | None] | None,
) -> tuple[dict | None, bool, bool]:
    """Return (good_receipt_or_None, belongs_to_task, is_stale)."""
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
    if receipt["role_sha256"] != manifest["role_sha256"]:
        hard.append(f"{label} role_sha256 does not match the manifest")
        return None, True, False
    stale = False
    if receipt["candidate_head"] != head:
        hard.append(f"{label} stale head: candidate_head != current head")
        stale = True
    if receipt["epoch"] > epoch:
        hard.append(f"{label} future epoch: {receipt['epoch']} > {epoch}")
        stale = True
    if stale:
        return None, True, True
    signing_key = supervisor_key if receipt["slot"] == SUPERVISOR_SLOT else key
    if not verify(receipt, signing_key, RECEIPT_LABEL):
        hard.append(f"{label} invalid signature")
        return None, True, False
    derived = derive_result(receipt)
    if derived != receipt["result"]:
        hard.append(
            f"{label} result {receipt['result']} does not match derived result {derived}"
        )
        return None, True, False
    if receipt["receipt_type"] == "TestRun" and receipt["artifact_digests"]:
        if artifact_resolver is None:
            if _NO_RESOLVER_REASON not in hard:
                hard.append(_NO_RESOLVER_REASON)
            return None, True, False
        for path, digest in receipt["artifact_digests"].items():
            try:
                current = artifact_resolver(path)
            except Exception as exc:  # resolver is caller code: default-deny
                hard.append(
                    f"{label} artifact {path!r} cannot be resolved: "
                    f"{type(exc).__name__}"
                )
                return None, True, False
            if current != digest:
                hard.append(
                    f"{label} artifact {path!r} digest mismatch: "
                    f"artifact changed or missing"
                )
                return None, True, False
    return receipt, True, False


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


def _chain_intact(slot: str, chain: list[dict], hard: list[str]) -> bool:
    attempts = [r["attempt"] for r in chain]
    if attempts != list(range(1, len(chain) + 1)):
        hard.append(
            f"attempt chain broken for slot {slot!r}: attempts {attempts} "
            f"are not consecutive from 1"
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
) -> tuple[bool, str | None, str | None, list[str]]:
    """Return (covers, record_id, operator, problems)."""
    if not isinstance(waiver, dict):
        return False, None, None, ["waiver rejected: must be an object (dict)"]
    problems: list[str] = []
    if not all(isinstance(k, str) for k in waiver):
        return False, None, None, ["waiver rejected: non-string key"]
    missing = sorted(set(_WAIVER_FIELDS) - set(waiver))
    unknown = sorted(set(waiver) - set(_WAIVER_FIELDS))
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
    if not isinstance(receipts, list):
        hard.append("receipts: must be a list")
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
    good: list[dict] = []
    own_count = 0
    stale_count = 0
    for index, raw in enumerate(receipts):
        receipt, own, stale = _check_receipt(
            index, raw, valid_manifest, manifest_hash, current_head,
            current_epoch, bytes(key), bytes(supervisor_key), hard,
            artifact_resolver,
        )
        own_count += 1 if own else 0
        stale_count += 1 if stale else 0
        if receipt is not None:
            good.append(receipt)
    if own_count > 0 and stale_count == own_count:
        fatal = True
        hard.append(
            "all receipts for this task are stale (head mismatch or future epoch)"
        )

    slot_types = {
        s["slot"]: s["receipt_type"] for s in valid_manifest["required_receipts"]
    }
    grouped, supervisor = _group_by_slot(good, slot_types, hard)
    _check_supervisor_chain(supervisor, findings, hard)

    covered: set[str] = set()
    unmet_slots: list[str] = []
    for slot in slot_types:
        chain = sorted(grouped[slot], key=lambda r: r["attempt"])
        if not chain:
            soft.append(f"missing receipt for slot {slot!r}")
            unmet_slots.append(slot)
            continue
        for earlier in chain[:-1]:
            if earlier["result"] != "PASS":
                findings.append(
                    f"earlier failure retained: {slot} attempt "
                    f"{earlier['attempt']} {earlier['result']}"
                )
        if not _chain_intact(slot, chain, hard):
            continue
        latest = chain[-1]
        hashes.append(receipt_sha256(latest))
        if latest["epoch"] != current_epoch:
            soft.append(
                f"slot {slot!r} needs a current-epoch attempt (latest attempt "
                f"{latest['attempt']} is from epoch {latest['epoch']})"
            )
            unmet_slots.append(slot)
            continue
        slot_ok, contribution = _check_latest(
            slot, latest, valid_manifest, findings, hard, soft
        )
        if latest["result"] != "PASS":
            soft.append(
                f"slot {slot!r} latest attempt {latest['attempt']} "
                f"result {latest['result']}"
            )
            unmet_slots.append(slot)
            continue
        if not slot_ok:
            unmet_slots.append(slot)
            continue
        covered.update(contribution)

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
            current_epoch, unmet_slots, acceptance_unmet,
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
