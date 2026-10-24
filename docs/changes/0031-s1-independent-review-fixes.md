# 0031 S1 independent review fixes

## What
Fixes two MAJOR and one MINOR defect in `tools/vst/store.py` found by the independent review (verdict MODIFY), and records two deferred items.
- MAJOR-1: the per-epoch slot bound in `append_receipt` now counts only NON-PASS receipts of the slot in the current epoch (refuse when that count >= retry_cap + 1). PASS receipts never count, so re-attesting at a new head is never refused with kind 'retry' while the retry cap is not exhausted. Attempt numbers stay globally consecutive.
- MAJOR-2: `_budget_block_locked` lost its `strict` parameter. The budget blocks only when spent > cap or a BUDGET_EXCEEDED event exists. `acquire_lease` no longer commits a terminal BUDGET_EXCEEDED marker for a task that spent exactly its cap, so a lease attempt cannot invalidate a complete PASS set. `charge` still refuses to exceed the cap and commits the marker itself. A cost_cap 0 task with nothing spent still starts.
- MINOR-3: worker receipt ids starting with the reserved prefix `sup-` are rejected in `append_receipt` (kind 'validation'); supervisor markers use the new constant `SUPERVISOR_RECEIPT_PREFIX`, so a worker cannot pre-claim a marker id.
- MINOR-4 (docs): S2 plan section 9 and backlog VST-025, VST-026 record the mandatory-commands gap and the waiver-scope decision.

## Why
Retry_cap 1 example: head h1 tests FAIL, static/review PASS; head h2 tests PASS, static FAIL, review PASS; at h3 every slot had two receipts in the epoch and all were refused, so the story was stuck. Separately, strict budget equality turned a worker that spent exactly its cap into a permanent non-approval on any later lease call.

## Affected contracts and paths
- `tools/vst/store.py` (module docstring, `append_receipt`/`_append_locked`, `_budget_block_locked`, `_check_budget_locked`, `acquire_lease`, supervisor marker id)
- Store error kinds: 'retry' now fires only on non-PASS counts; new use of kind 'validation'; 'budget' from `acquire_lease` only for spent > cap or an existing event.
- `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`, `core/BACKLOG.md`, `core/LESSONS_LOG.md`, `core/DECISION_LOG.md`.
- Existing tests that pin the old behavior (acquire_lease refusing at spent == cap; slot bound counting PASS receipts) will need updating by the test agents.

## Verification
Test agents rewrote the tests that pinned the old behavior and added new ones (three heads with retry_cap 1; exact-cap spend then re-attestation, repeated acquire_lease and takeover; overspend still blocks; zero cap; worker receipt id with prefix `sup-`), then ran the complete files on the dirty tree at base HEAD 5427bb7 with C:\Python314\python.exe -m pytest:
- `test_e3_store.py`, `test_e1_contracts.py`, `test_e2_gate.py`: 1193 passed, 1 skipped (POSIX permission bits on Windows).
- `test_e4_runner.py`: 289 passed, 1 skipped (os.symlink not permitted on this machine; symlink-escape behavior unverified here).
- `test_e5_slice.py`, `test_e5_process_death.py`: 72 passed. The scenario catalogue grew to 23 scenarios (4 added, 1 renamed).
Not observed: the new tests were not run against the old store (no mutation runs by operator decision); their ability to fail on the old rules is argued from the assertions. The code was not re-reviewed after the fix; the GPT-PM gate covers the final head.
