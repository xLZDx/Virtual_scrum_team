# Change record 0025: S1 fourth check fixes

## What changed
- `tools/vst/store.py`: `_budget_block_locked` strict check (used by `acquire_lease`) requires `spent > 0`, so a task with `cost_cap` 0 and nothing spent can start; module docstring updated.
- `tools/vst/contracts.py`: `normalize_principal` also rejects U+2800 (braille blank).
- `tests/vst/test_e3_store.py`, `tests/vst/test_e1_contracts.py`: the test that pinned a terminal marker for `cost_cap` 0 replaced; new tests for the zero-cap lifecycle; U+2800 added to the invisible-character list.
- `tools/vst/schemas/README.md`: per-epoch slot bound in the receipt-check list, full `normalize_principal` reject list. `docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md` (BD-2 wording), `core/STATE.md` (status), `docs/sdlc/evidence/s1-third-round-e3-e4-test-run.md` (section "Fourth-check fixes").
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: entries for the fourth check.

## Why
The fourth specialist check (head 176a095) found one MAJOR regression (zero-cap tasks unstartable) and four documentation minors; no other BLOCKER or MAJOR. The two earlier MAJORs and the `extra_env` finding were confirmed closed.

## Verification state
Test agent ran on the working tree over 176a095: E1+E2+E3+E5 files 1205 passed, 1 skipped (E4 not rerun, unaffected by these changes). The coordinator ran no tests. Not verified: POSIX behaviour, Job Object nesting, mutation checks (NOT_RUN by operator decision). The final independent review on an allowed model is still pending.
