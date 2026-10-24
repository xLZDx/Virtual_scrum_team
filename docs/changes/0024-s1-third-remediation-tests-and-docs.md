# Change record 0024: S1 third remediation round, tests and documentation

## What changed
- Code of the third round is recorded in `docs/changes/0023` (store, runner, slice) and in this round's `tools/vst/contracts.py` change (`normalize_principal` also rejects invisible, variation-selector and filler characters).
- `tests/vst/test_e1_contracts.py`, `test_e2_gate.py`, `test_e3_store.py`, `test_e4_runner.py`, `test_e5_slice.py`, `test_e5_process_death.py`: updated and extended (budget boundary and single marker, per-epoch slot bound, `failed_attempts` over every non-PASS result and released leases, `acquire_epoch` reaping, `heartbeat` refusal after a terminal marker, worker key versus `event_key`, `receipts_for_task` integrity cross-check, `extra_env` allowlist, reader exceptions and a surviving root giving exit -4, thread-start failure cleanup, invisible characters in principals, two new slice scenarios and the 19-scenario catalogue).
- `docs/sdlc/evidence/s1-third-round-e1-e2-test-run.md`, `s1-third-round-e3-e4-test-run.md`, `s1-third-round-e5-test-run.md`: test-agent run evidence.
- `CLAUDE.md`, `docs/SDLC_PROCESS.md`, `core/STATE.md`, `docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md` (BD-2 row): state-authority wording, status line, labels and artifact resolver.
- `tools/vst/store.py`: module docstring only, updated to the new retry, budget and slot-bound rules (no code change).
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: entries for the third round.

## Why
Four specialist reviewers returned MODIFY on f1956e2; two MAJOR findings were shared by several reviewers. Items deferred to S2 stay deferred; the authenticated reviewer key is recorded as an S2 item.

## Verification state
Test agents ran their complete sets on the working tree over f1956e2: E1+E2 863 passed; E3+E4 593 passed and 2 skipped; E5 64 passed. The coordinator ran no tests. Not verified: POSIX behaviour, Job Object nesting under a parent job, naturally unkillable processes, mutation checks (NOT_RUN by operator decision). Not independently reviewed after this round.
