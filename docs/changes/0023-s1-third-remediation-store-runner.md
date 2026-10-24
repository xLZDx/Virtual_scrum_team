# Change record 0023: S1 third remediation, store, runner, slice

## What changed
- `tools/vst/store.py`: `append_receipt` refuses on budget only at `spent > cap` or an existing BUDGET_EXCEEDED event/marker; `acquire_lease` keeps `spent >= cap` but commits the signed BUDGET_EXCEEDED marker (event once) before raising `kind='budget'`; the slot-chain bound counts only attempts of the current epoch (`retry_cap + 1`), attempt numbers stay globally consecutive; `failed_attempts` counts every non-PASS worker result plus EXPIRED and RELEASED leases that wrote nothing; `acquire_epoch` reaps expired leases before fencing; `heartbeat` refuses after a terminal marker or exceeded budget; `append_receipt` rejects a worker key equal to the event key (`kind='key'`); `receipts_for_task` verifies the anchor and cross-checks RECEIPT_APPENDED event shas against receipt rows (`kind='integrity'`).
- `tools/vst/runner.py`: `extra_env` is an allowlist (`VST_[A-Z0-9_]+`); the capture reader catches any Exception; a root that survives the kill gives exit -4; the tree is killed on any exception and pipes are closed after the readers are joined; `_Capture` is built inside the try; the `attempt <= retry_cap + 1` check was removed from `_prepare` because attempts are global and the bound is per epoch (enforced by the store).
- `tools/vst/slice.py`: scenarios `budget_exact_cap_allows_final_receipts` and `takeover_after_full_pass_set` (retry_cap 0 via the new optional `retry_cap` of `build_synthetic_manifest` and `SliceFixture`).
- `tools/vst/schemas/README.md`: Store, Runner and Slice sections updated; new paragraph on what the store enforces vs the gate.

## Why
Third-round decisions A-F in `core/DECISION_LOG.md` (budget boundary, per-epoch retry bound, retry counting, epoch reaping, runner hardening, store integrity).

## Verification state
Code changed; tests were NOT rerun. Existing tests expecting `spent >= cap` refusal in `append_receipt`, the runner `attempt > retry_cap + 1` ContractError, the old `extra_env` shadow rules (lower-case or non-VST names now rejected), RELEASED/NOT_RUN/BLOCKED not counted in `failed_attempts`, the seventeen-scenario count, and tests that tamper with receipt rows or events before calling `receipts_for_task` need updating.
