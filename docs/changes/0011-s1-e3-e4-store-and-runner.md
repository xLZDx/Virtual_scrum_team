# Change record 0011: S1 E3 state store and E4 runner

## What changed
- New `tools/vst/store.py`: SQLite `Store` (epoch compare-and-swap, leases with slots in one transaction, append-only hash-chained receipts and events enforced by triggers, budget ledger, supervisor receipts, markdown state renderer) and `StoreError(kind)`.
- New `tools/vst/runner.py`: `run_and_sign`, `file_sha256`, `artifact_digests`.
- Fix to E1: `contracts.derive_result` now accepts a given BLOCKED, INCONCLUSIVE or NOT_RUN result as given for every receipt type (new constant `NON_APPROVING_RESULTS`); a given PASS or FAIL is still compared with the computed value. `gate.py` is unchanged: such receipts are consistent and, as non-PASS latest attempts, leave the slot unmet.
- `tools/vst/schemas/README.md`: updated derive_result rules, reason codes carried in `check_description` of supervisor Documentation receipts, new Store and Runner sections.

## Why
Sprint S1 epics E3 and E4 (BD-5 failures never erased, BD-6 limits enforced by the store; risks R-4, R-6). The derive_result fix lets the supervisor record INCONCLUSIVE(WORKER_LOST) and BLOCKED(RETRY_EXHAUSTED) without weakening the gate.

## Affected contracts and paths
`tools/vst/store.py`, `tools/vst/runner.py` (new); `tools/vst/contracts.py`, `tools/vst/schemas/README.md` (edited). Standard library only; no network, no provider calls. Schema additions beyond the minimal design: `stories.owner_expires_at`, `leases.marked`, `receipts.story_id`.

## Verification state
Code written only. No tests, linters, type checks or imports were run, by design (build phase). Tests are written and run by the separate test agents next. Not independently reviewed.
