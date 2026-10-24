# S1 second round: E5 test run (slice scenarios and process death)

## Run

- Command (repo root): `C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e5_slice.py tests/vst/test_e5_process_death.py -rA`
- Git HEAD: `5a749ee620cb65fc09ba36575c27d1999dfa215e`. The working tree was DIRTY: the second-round code (`tools/vst/slice.py`, `store.py`, `gate.py`, `contracts.py`, `runner.py`, change records 0019 and 0020) and the other test agents' files were uncommitted; this evidence proves that working-tree state on top of the HEAD above, not a commit.
- Result: `52 passed, 1 warning in 77.43s` (warning: third-party pytest_asyncio deprecation, unrelated). No skip, no xfail, no failure. Run once in the final form; the files were first run in two partial runs (slice file 31 passed; process-death file 10 passed before additions, 21 passed after).
- Counts: `tests/vst/test_e5_slice.py` 31 tests; `tests/vst/test_e5_process_death.py` 21 tests.

## Per-scenario results (all 17 scenarios of tools/vst/slice.py)

| Scenario | Verdict asserted | Rows checked |
| --- | --- | --- |
| happy_path | APPROVE, no reasons | 1 lease RELEASED, 3 receipts, no marker, events |
| worker_death_before_receipt | MODIFY, worker lost finding | EXPIRED lease marked, signed WORKER_LOST row |
| zombie_late_write | MODIFY | FENCED lease, no receipt stored |
| stale_head | NO_GO (message now "all deciding receipts ... stale", per-slot "needs an attempt at the current head"; test updated) | n/a |
| retry_after_fail | APPROVE with earlier-failure finding | chain links, 2 leases |
| forged_receipt | MODIFY | n/a |
| partial_static_coverage | MODIFY | static body PARTIAL |
| missing_required_receipt | MODIFY | 2 receipts |
| not_run_with_waiver | MODIFY / APPROVED_WITH_WAIVER only with a correct operator waiver | n/a |
| budget_exceeded | MODIFY (updated: marker written by `charge`, refused `begin` kind budget, exact extra key set, no lease row) | budget row 5/3, one BUDGET_EXCEEDED and one BUDGET_BLOCKED event |
| real_run_and_sign | APPROVE | stored body, argv, signature |
| retry_exhausted | MODIFY, single RETRY_EXHAUSTED marker | 2 leases |
| forged_supervisor_receipt | MODIFY | 0 rows stored |
| manifest_swap | MODIFY | 0 receipts, 1 task |
| retry_across_head_change (new) | APPROVE, findings "earlier failure retained: tests attempt 1 FAIL" and "history attempt at other head: tests attempt 1" | attempt 1 FAIL at base head, attempt 2 PASS and static/review at new head, prev link intact, no marker |
| worker_lost_before_first_receipt (new) | APPROVE, finding "worker lost: attempt 1" | WORKER_LOST marker at base head, signed with the supervisor key; worker receipts only at the new head; leases (1 EXPIRED marked, 2 RELEASED); no LEASE_EXPIRED_PARTIAL |
| takeover_does_not_exhaust_retry_cap (new) | APPROVE, three worker-lost findings | 3 FENCED leases then a fourth RELEASED, `failed_attempts` 0, markers at epochs 3, 4, 5, 3 LEASE_FENCED and 4 LEASE_ACQUIRED events, no RETRY_EXHAUSTED |

Other slice-file tests: catalogue (exactly 17 names, no duplicates), six approving scenarios (the original three plus the three new), per-scenario event chain verified with the right key and rejected with a wrong key, fixture key tests, CLI end to end (17 scenarios, deterministic output, equals the in-process report, usage errors exit 2).

## Process-death file (real child interpreter, os._exit(1))

Original 10 tests unchanged and green. 11 added for the second-round store: schema `user_version` 3 and `leases.receipt_count`; a version 2 file refused with kind `schema` and left untouched; budget row seeded from the manifest `cost_cap`; `LEASE_EXPIRED_PARTIAL` event (exact payload `attempt`, `lease_id`, `receipts`, directly after `LEASE_EXPIRED`, written once) for a lease that wrote a receipt before dying, and no such event plus a WORKER_LOST marker for a lease that wrote nothing; three fenced takeovers keep `failed_attempts` 0 and a fourth lease is granted; two expired leases without receipts count 2 and trip the cap (kind `retry`, RETRY_EXHAUSTED marker); a worker FAIL receipt counts once; `charge` (keyword-only `supervisor_key`, `TypeError` otherwise, event key refused with kind `key`), `set_budget` (unknown task kind `task`, above `cost_cap` kind `budget`, below spent kind `argument`), `record_event` (only `NOTE`; `OPERATOR_ACTION`, `LEASE_EXPIRED_PARTIAL`, `BUDGET_EXCEEDED` refused); `charge` over cap commits the signed marker and events despite the raise, visible to a second Store, and then `acquire_lease` is refused with kind `budget` without a lease row; a deleted event anchor gives kind `integrity` on append and `event_anchor`, `verify_event_chain` false, nothing recomputed.
Concurrency tests (two Store instances, 25 rounds each, epoch and lease races) unchanged and green.

## Defects

- Product bugs found: none. No file under `tools/vst` was changed by this agent.
- Test defects: 2 stale expectations from the old behavior fixed in `test_e5_slice.py` (approving-scenario set, stale-head reason wording); no assertion was weakened.
- Environment: none.

## Not verified

- Mutation checks (NOT_RUN by operator decision): no proof here that each assertion turns red when its guarded behavior is broken.
- POSIX behavior (permission bits, process-group kill); the run is on Windows only.
- The `taskkill /T` post-exit path and the runner capture-incomplete exit code -4 (E4 files, not covered here).
- The other agents' E1 to E4 files were not run by this agent.
- Wall-clock-free: the real process death uses a fake clock injected by argument, so real lease timeouts were not observed.

## Re-run after runner.py change (Windows Job Object, change record 0021)

- Command: `C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e5_slice.py tests/vst/test_e5_process_death.py`
- Git HEAD `5a749ee620cb65fc09ba36575c27d1999dfa215e`, working tree dirty (26 changed or untracked paths at run time, including the new runner.py).
- Result: 31 tests in `test_e5_slice.py` and 21 in `test_e5_process_death.py`, 52 in total. No test changes were needed; the `real_run_and_sign` scenario asserts only specific report keys (`stdout_truncated`), so the new per-command `job_object` key did not affect it. No product bug found.
- Verbatim last line: `52 passed, 1 warning in 74.22s (0:01:14)`
- Not verified: the Job Object behavior itself (E4 scope); this run only proves the runner still produces a valid signed receipt for the slice.
