"""Pure, default-deny gate verdict function (BD-4, R-2, R-4).

evaluate(manifest, receipts, current_head, current_epoch, key, waiver=None)
returns a GateDecision dict (it always passes validate_gate_decision). It
never raises for bad data, never mutates its inputs, does no I/O.

Rules, applied in this order; ALL reasons are collected, evaluation does not
stop at the first problem:

1. Inputs. current_head must be 40 lowercase hex, current_epoch an int >= 1
   (not bool), key non-empty bytes, receipts a list, manifest valid per
   validate_task_manifest. Any failure is a reason and the verdict is NO_GO.
   An invalid manifest returns immediately (slots are unknown).
2. Per-receipt checks. A receipt is "good" only if it (a) passes
   validate_receipt, (b) has task_id == manifest.task_id, (c) has
   candidate_head == current_head and epoch == current_epoch, (d) has a valid
   HMAC signature, (e) has result == derive_result(receipt). Every receipt
   failing a check yields a hard reason and is excluded from everything below.
   If at least one receipt belongs to this task and ALL of them fail (c), the
   verdict is NO_GO.
3. Slot matching. Good receipts are grouped by their `slot` field. A good
   receipt whose slot is not in manifest.required_receipts gives the hard
   reason 'unlisted receipt'; one whose receipt_type differs from the slot's
   type gives a hard 'receipt type mismatch'. Both are excluded.
4. Attempt chains. Per slot, attempts must be exactly 1..n without gaps or
   duplicates and attempt k>1 must carry prev_receipt_sha256 ==
   receipt_sha256(attempt k-1). Violation is a hard reason and the slot is
   unsatisfied. (attempt 1 must have prev null; enforced by validate_receipt.)
5. Slot satisfaction. The LATEST attempt of a slot decides. A slot with no
   good receipt ('missing receipt') or whose latest result is not PASS
   (FAIL, BLOCKED, NOT_RUN, INCONCLUSIVE) is unmet (a soft reason). An
   IndependentReview slot additionally needs reviewer_principal !=
   author_principal (hard reason otherwise).
6. Failures are never erased. Every earlier attempt (all but the latest) of a
   slot whose result is not PASS is listed in unresolved_findings as
   'earlier failure retained: ...', even when the latest attempt is PASS. These
   findings do not by themselves block APPROVE.
7. Acceptance coverage. covered = union of covered_acceptance over the latest
   PASS receipt of every satisfied slot. acceptance_unmet = manifest.acceptance
   ids not in covered (manifest order); each also yields a soft reason.
8. Verdict.
   - NO_GO: bad inputs / invalid manifest, or every receipt of this task is
     stale (wrong head or epoch).
   - APPROVE: no reasons at all and acceptance_unmet empty.
   - APPROVED_WITH_WAIVER: no hard reasons, and a valid waiver
     {record_id, operator, waived_slots, waived_acceptance, head,
     expires_epoch_or_date} (exact keys; non-empty strings; lists of str;
     head == current_head) lists every unmet slot and every unmet acceptance
     id. Nothing else may be wrong. waiver_record = record_id and
     human_approvals = [operator]. Expiry is an opaque string, not evaluated.
     A waiver is ignored when nothing is unmet; an unusable waiver adds a
     reason and the verdict stays MODIFY.
   - MODIFY: everything else (missing/invalid/unmet gaps that can be fixed).

Hard reasons are never waivable; soft reasons are the unmet slots and
unmet acceptance ids.
"""

from __future__ import annotations

from typing import Any

from .contracts import (
    ContractError,
    derive_result,
    receipt_sha256,
    validate_gate_decision,
    validate_receipt,
    validate_task_manifest,
)
from .signing import verify

_WAIVER_FIELDS = (
    "record_id",
    "operator",
    "waived_slots",
    "waived_acceptance",
    "head",
    "expires_epoch_or_date",
)


def _is_hex40(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(c in "0123456789abcdef" for c in value)
    )


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
        "epoch": epoch if isinstance(epoch, int) and not isinstance(epoch, bool) and epoch >= 0 else 0,
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
    task_id: str,
    head: str,
    epoch: int,
    key: bytes,
    hard: list[str],
) -> tuple[dict | None, bool, bool]:
    """Return (good_receipt_or_None, belongs_to_task, is_stale)."""
    label = f"receipt[{index}]"
    try:
        receipt = validate_receipt(raw)
    except ContractError as exc:
        hard.append(f"{label} invalid: {exc}")
        return None, False, False
    label = f"receipt[{index}] ({receipt['receipt_id']})"
    if receipt["task_id"] != task_id:
        hard.append(f"{label} belongs to another task {receipt['task_id']!r}")
        return None, False, False
    stale = False
    if receipt["candidate_head"] != head:
        hard.append(f"{label} stale head: candidate_head != current head")
        stale = True
    if receipt["epoch"] != epoch:
        hard.append(f"{label} stale epoch: {receipt['epoch']} != {epoch}")
        stale = True
    if stale:
        return None, True, True
    if not verify(receipt, key):
        hard.append(f"{label} invalid signature")
        return None, True, False
    derived = derive_result(receipt)
    if derived != receipt["result"]:
        hard.append(
            f"{label} result {receipt['result']} does not match derived result {derived}"
        )
        return None, True, False
    return receipt, True, False


def _group_by_slot(
    good: list[dict], slot_types: dict[str, str], hard: list[str]
) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {name: [] for name in slot_types}
    for receipt in good:
        slot = receipt["slot"]
        label = f"receipt {receipt['receipt_id']}"
        if slot not in slot_types:
            hard.append(f"unlisted receipt: {label} has slot {slot!r} not in manifest")
        elif receipt["receipt_type"] != slot_types[slot]:
            hard.append(
                f"receipt type mismatch: {label} is {receipt['receipt_type']} "
                f"but slot {slot!r} requires {slot_types[slot]}"
            )
        else:
            grouped[slot].append(receipt)
    return grouped


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


def _evaluate_waiver(
    waiver: Any, head: str, unmet_slots: list[str], unmet_acceptance: list[str]
) -> tuple[bool, str | None, str | None, list[str]]:
    """Return (covers, record_id, operator, problems)."""
    if not isinstance(waiver, dict):
        return False, None, None, ["waiver rejected: must be an object (dict)"]
    problems: list[str] = []
    missing = sorted(set(_WAIVER_FIELDS) - set(waiver))
    unknown = sorted(set(waiver) - set(_WAIVER_FIELDS))
    if missing:
        problems.append(f"waiver rejected: missing field(s): {', '.join(missing)}")
    if unknown:
        problems.append(f"waiver rejected: unknown field(s): {', '.join(unknown)}")
    if problems:
        return False, None, None, problems
    for name in ("record_id", "operator", "expires_epoch_or_date"):
        value = waiver[name]
        if not isinstance(value, str) or not value.strip():
            problems.append(f"waiver rejected: {name} must be a non-empty string")
    for name in ("waived_slots", "waived_acceptance"):
        value = waiver[name]
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            problems.append(f"waiver rejected: {name} must be a list of strings")
    if waiver["head"] != head:
        problems.append("waiver rejected: waiver head != current head")
    if problems:
        return False, None, None, problems
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
    waiver: dict | None = None,
) -> dict:
    """Compute the GateDecision for one task candidate. See module docstring."""
    hard: list[str] = []
    soft: list[str] = []
    findings: list[str] = []
    hashes: list[str] = []
    fatal = False

    task_id = manifest.get("task_id") if isinstance(manifest, dict) else None

    if not _is_hex40(current_head):
        hard.append("current_head: must be 40 lowercase hex characters")
        fatal = True
    if (
        not isinstance(current_epoch, int)
        or isinstance(current_epoch, bool)
        or current_epoch < 1
    ):
        hard.append("current_epoch: must be an integer >= 1")
        fatal = True
    if not isinstance(key, (bytes, bytearray)) or len(key) == 0:
        hard.append("key: must be non-empty bytes")
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

    good: list[dict] = []
    own_count = 0
    stale_count = 0
    for index, raw in enumerate(receipts):
        receipt, own, stale = _check_receipt(
            index, raw, valid_manifest["task_id"], current_head,
            current_epoch, bytes(key), hard,
        )
        own_count += 1 if own else 0
        stale_count += 1 if stale else 0
        if receipt is not None:
            good.append(receipt)
    if own_count > 0 and stale_count == own_count:
        fatal = True
        hard.append("all receipts for this task are stale (head or epoch mismatch)")

    slot_types = {
        s["slot"]: s["receipt_type"] for s in valid_manifest["required_receipts"]
    }
    grouped = _group_by_slot(good, slot_types, hard)

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
                    f"earlier failure retained: slot {slot!r} attempt "
                    f"{earlier['attempt']} result {earlier['result']}"
                )
        if not _chain_intact(slot, chain, hard):
            continue
        latest = chain[-1]
        hashes.append(receipt_sha256(latest))
        if latest["result"] != "PASS":
            soft.append(
                f"slot {slot!r} latest attempt {latest['attempt']} "
                f"result {latest['result']}"
            )
            unmet_slots.append(slot)
            continue
        if (
            latest["receipt_type"] == "IndependentReview"
            and latest["reviewer_principal"] == latest["author_principal"]
        ):
            hard.append(f"slot {slot!r}: reviewer_principal equals author_principal")
            continue
        covered.update(latest["covered_acceptance"])

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
            waiver, current_head, unmet_slots, acceptance_unmet
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
