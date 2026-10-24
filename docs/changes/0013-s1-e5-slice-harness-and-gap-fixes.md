# Change record 0013: S1 E5 slice harness and store gap fixes

## What changed
- New `tools/vst/slice.py`: synthetic vertical-slice driver (`build_synthetic_manifest`, `FakeClock`, `SliceFixture`, `run_scenarios`, CLI). Ten scenarios: happy path, worker death before receipt, zombie late write, stale head, retry after FAIL, forged receipt, partial static coverage, missing required receipt, NOT_RUN with and without waiver, budget exceeded.
- `tools/vst/store.py`: (1) `sqlite3.IntegrityError` raised by the append-only triggers inside a Store transaction becomes `StoreError(kind='append_only')`; (2) new `Store.mark_budget_exceeded` (signed supervisor BLOCKED receipt, `check_description` `BUDGET_EXCEEDED`, event `BUDGET_BLOCKED`), sharing a new private `_write_supervisor_receipt` with the existing WORKER_LOST / RETRY_EXHAUSTED path (behaviour unchanged); (3) new `Store.renew_epoch` and `Store.release_epoch`.
- `tools/vst/schemas/README.md`: Store additions and a "Slice harness" section.

## Why
Sprint S1 epic E5 (BD-5 failures never erased, BD-6 limits enforced by the store; risks R-4, R-6) needs a deterministic harness that exercises the real store and gate end to end, plus three gaps found while designing it: unwrapped trigger errors, no supervisor marker for budget overrun, no way to renew or release epoch ownership.

## Affected contracts and paths
`tools/vst/slice.py` (new); `tools/vst/store.py`, `tools/vst/schemas/README.md` (edited). Standard library only; no network, no provider calls. No contract or gate change. No test hooks were added to the Store.

## Verification state
Code written only. No tests, linters, type checks, imports or smoke runs were executed, by design (build phase). The test agents write and run the focused tests next. Not independently reviewed.
