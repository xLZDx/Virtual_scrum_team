# S1 third round: E5 test run (slice and process death)

## Run

- Command (repo root): `C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e5_slice.py tests/vst/test_e5_process_death.py`
- Head: `f1956e24933ca4a89cb215b7ce174d65ea263f49` (branch `s1-control-plane-core`), working tree DIRTY: uncommitted third-remediation changes in `tools/vst/slice.py`, `store.py`, `runner.py`, `contracts.py` and tests of other epics; the result applies to that working tree, not to the bare head.
- Final result: `64 passed, 1 warning in 98.54s` (33 tests in `test_e5_slice.py`, 31 in `test_e5_process_death.py`). The warning is a pytest_asyncio deprecation notice, unrelated.
- Runs: first run on the unchanged tests: 6 failed, 46 passed (expected, see below); after test updates 63 passed, 1 failed (test defect); final run all green.

## Per-scenario results (19 slice scenarios)

All 19 scenarios run in their own SQLite file; verdicts asserted exactly (reasons and database rows for the two new ones).

| Scenario | Verdict |
|---|---|
| happy_path | APPROVE |
| worker_death_before_receipt | MODIFY |
| zombie_late_write | MODIFY |
| stale_head | NO_GO |
| retry_after_fail | APPROVE |
| forged_receipt | MODIFY |
| partial_static_coverage | MODIFY |
| missing_required_receipt | MODIFY |
| not_run_with_waiver | MODIFY (with waiver: APPROVED_WITH_WAIVER) |
| budget_exceeded | MODIFY |
| real_run_and_sign | APPROVE |
| retry_exhausted | MODIFY |
| forged_supervisor_receipt | MODIFY |
| manifest_swap | MODIFY |
| retry_across_head_change | APPROVE |
| worker_lost_before_first_receipt | APPROVE |
| takeover_does_not_exhaust_retry_cap | APPROVE |
| budget_exact_cap_allows_final_receipts (new) | APPROVE before the marker; MODIFY after (`terminal marker BUDGET_EXCEEDED (supervisor attempt 1)`) |
| takeover_after_full_pass_set (new) | APPROVE after the first PASS set and after both takeovers |

New-scenario assertions:
- budget exact cap: remaining 0 after charging exactly the cap; full PASS set appended (3 receipts); two `acquire_lease` calls both raise kind `budget`; exactly one BUDGET_EXCEEDED marker (result BLOCKED, runner `store-supervisor`, verifies under the supervisor key only); one BUDGET_EXCEEDED event; budget row cap 5 / spent 5; one lease row (RELEASED, wrote 1), no slot held; 4 RECEIPT_APPENDED events; event chain intact.
- takeover after full PASS set (retry_cap 0): receipts per slot at epochs 2, 3, 4 with attempts 1, 2, 3; exactly one attempt per slot per epoch in the database; failed_attempts 0; no supervisor marker; three RELEASED leases; 2 EPOCH_RELEASED, 9 RECEIPT_APPENDED, 3 LEASE_ACQUIRED events.

## Tests changed or added

`tests/vst/test_e5_slice.py`: catalogue, approving-set, CLI verdict table and counts moved from 17 to 19 scenarios (approving set is now 8); `zombie_late_write` expectation changed (lease is EXPIRED with a LEASE_EXPIRED event, no LEASE_FENCED, because `acquire_epoch` reaps expired leases first); two new detailed tests for the new scenarios.

`tests/vst/test_e5_process_death.py`:
- changed: takeover of an expired dead lease now expects EXPIRED, WORKER_LOST at the new epoch, `failed_attempts` 1; the fenced-takeover/retry-cap test now makes the owner step down (`release_epoch`) so the lease is still LIVE at takeover and is FENCED and not counted.
- added: takeover of a still-live lease is FENCED and not counted (events); `failed_attempts` counts a RELEASED lease that wrote nothing, does not count a RELEASED lease that wrote a PASS, counts each non-PASS result (FAIL, INCONCLUSIVE, NOT_RUN, BLOCKED) once and PASS zero, is a per-slot maximum, and adds lost leases to receipt failures; heartbeat baseline extends the lease, is refused with kind `budget` after budget exceeded (expiry not extended, lease later reaped), refused with kind `terminal` after a RETRY_EXHAUSTED marker, and still allowed at exactly the cap.

## Defects

- Product bugs found: none.
- Test defects (fixed): 6 stale expectations in the first run (17-scenario counts, FENCED vs EXPIRED after reaping, `failed_attempts` of expired leases); one wrong assumption in a new test (runner id of the marker written by `acquire_lease` is `store-supervisor`, not the slice supervisor runner).

## Not verified

- Heartbeat refusal for `spent > cap` cannot be reached through the public API (`charge` writes the marker instead of exceeding the cap); only the marker/event paths are exercised.
- Combined fenced and expired leases of two tasks in one `acquire_epoch` call are not tested (the slice has one task).
- Mutation checks were not run (operator decision). Flake rate was not measured (single final run).
- Other epics (E1-E4) are covered by other evidence files.
