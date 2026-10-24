# Change record 0015: S1 review remediation A (contracts, signing, gate)

## What changed
- `tools/vst/signing.py`: keys must be bytes of length >= 32. `sign(obj, key, label=RECEIPT_LABEL)` and `verify(obj, key, label=RECEIPT_LABEL)` compute HMAC-SHA256 over `label + canonical_bytes(obj)`. New constants `RECEIPT_LABEL`, `WAIVER_LABEL`, `MIN_KEY_BYTES`. `verify` still returns False for malformed input and raises only for an invalid key or label.
- `tools/vst/contracts.py`: manifest gains required fields `author_principal`, `required_tests`, `allowed_commands`, `required_rules` plus cross-checks (TestRun and IndependentReview slots required, reserved slot `__supervisor__` = `SUPERVISOR_SLOT`, per-slot tests/commands/rules). New `manifest_sha256(manifest)` and `normalize_principal(value)`. Receipts gain the required `manifest_sha256`; a receipt in `SUPERVISOR_SLOT` must be Documentation. `derive_result`: StaticAnalysis PASS needs non-empty `covered_rules`; IndependentReview compares normalized principals.
- `tools/vst/gate.py`: new signature `evaluate(manifest, receipts, current_head, current_epoch, key, *, supervisor_key, operator_key=None, waiver=None, artifact_resolver=None)`. Receipts are bound to the manifest hash and role hash; older epochs become history (only the latest attempt must be current-epoch; a future epoch is hard); chains span epochs; supervisor chain with terminal markers (hard, never waivable); TestRun commands and expected tests checked against the manifest and acceptance taken from the manifest; StaticAnalysis required rules; reviewer/author bound to the manifest; artifact digests without a resolver are denied; waiver is operator-signed, bound to task, epoch, head and manifest hash, with expiry epoch.
- `tools/vst/schemas/README.md`: contract tables, signing labels, waiver fields, gate summary and an honest "Known limits" list.

## Why
Four independent S1 reviewers found forgeable or replayable evidence paths (unsigned waiver, receipts not bound to the manifest, worker-claimed acceptance and commands, same-key supervisor markers, weak keys, principal spoofing by case or whitespace, epoch takeover discarding history). Decisions are recorded in `core/DECISION_LOG.md` (2026-10-24, "S1 specialist review").

## Affected contracts and paths
Breaking: manifest and receipt schemas (new required fields), `signing.sign`/`verify` (min key length 32, domain label), `gate.evaluate` signature (keyword-only `supervisor_key`, `operator_key`; waiver format replaced). Paths: `tools/vst/contracts.py`, `signing.py`, `gate.py`, `schemas/README.md`. Callers in `store.py`, `runner.py`, `slice.py` and `tests/vst` need updating (part B and test agents).

## Verification state
Code changed only. Tests were NOT run or rerun by design; nothing was imported or executed. Not independently reviewed.
