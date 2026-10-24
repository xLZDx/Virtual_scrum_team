# S1 remediation: E5 test run evidence

Date: 2026-10-24. Branch: s1-control-plane-core.

## Revision
- `git rev-parse HEAD`: 63e0e3515801b707b67352ed1122559199aeb616
- Dirty state: yes. The remediation code (parts A and B: `tools/vst/*.py`, `schemas/README.md`), change records 0015 and 0016 (untracked), and the E1-E4 test files were uncommitted/modified at run time (20 entries in `git status --short`). The result below proves the working tree, not the bare HEAD commit.

## Command
Run from the repository root:

    C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e5_slice.py tests/vst/test_e5_process_death.py

## Counts
| File | Tests |
|---|---|
| tests/vst/test_e5_slice.py | 28 |
| tests/vst/test_e5_process_death.py | 10 |
| Total | 38 |

Final run: `38 passed, 1 warning in 47.35s` (warning: pytest_asyncio DeprecationWarning from a user-site plugin, unrelated to the code).
The first run had 37 passed, 1 failed (see Defects). The complete set was rerun after the fix.

## Per-scenario results (tools/vst/slice.py, 14 scenarios, each asserted on verdict, reasons and database rows)
| Scenario | Verdict | Key asserted reasons / state |
|---|---|---|
| happy_path | APPROVE | no reasons; 3 receipts; lease RELEASED wrote=1; slot freed; event chain valid |
| worker_death_before_receipt | MODIFY | unresolved "worker lost: attempt 1"; lease EXPIRED wrote=0 marked=1; one WORKER_LOST INCONCLUSIVE marker signed by supervisor key only |
| zombie_late_write | MODIFY | append kind=epoch; heartbeat kind=lease; lease FENCED; 0 receipts stored; gate "needs a current-epoch attempt" |
| stale_head | NO_GO | 3 "stale head" reasons plus "all receipts ... stale" |
| retry_after_fail | APPROVE | attempt 1 FAIL retained as finding; attempt 2 chained by prev hash; 2 leases RELEASED |
| forged_receipt | MODIFY | "invalid signature" for wrong key and for post-signing tamper |
| partial_static_coverage | MODIFY | static INCONCLUSIVE |
| missing_required_receipt | MODIFY | exactly "missing receipt for slot 'review'" |
| not_run_with_waiver | MODIFY / APPROVED_WITH_WAIVER | no waiver MODIFY; valid operator waiver APPROVED_WITH_WAIVER (WV-1, operator-1); wrong-head and worker-key waivers rejected with MODIFY |
| budget_exceeded | MODIFY | BLOCKED BUDGET_EXCEEDED marker, idempotent, one marker, spent stays 3 |
| real_run_and_sign | APPROVE | real subprocess; unallowed command and wrong expected ids refused; receipt PASS, bound to manifest hash |
| retry_exhausted | MODIFY | third attempt kind=retry twice; one RETRY_EXHAUSTED marker; no third lease row |
| forged_supervisor_receipt | MODIFY | store supervisor path kind=signature; worker path kind=supervisor; nothing stored; gate "invalid signature" |
| manifest_swap | MODIFY | append kind=manifest; re-register kind=manifest; nothing stored; gate manifest hash reason |

Additional E5 slice tests: fixture key rules (four keys distinct and >= 32 bytes, every equal pair refused, short keys refused), lease/epoch/registered-manifest flow, supervisor and operator signing domains, event chain valid for all 14 databases and invalid under the wrong event key, CLI end-to-end (`python -m tools.vst.slice <dir>` exits 0, reports all 14 scenarios with the expected verdicts, deterministic across two runs, equals the in-process report, one database per scenario, exit 2 on missing/extra arguments).

Process death (real separate interpreter killed with `os._exit(1)` mid-lease; child pid differs from parent): state survives in the file and a live lease is neither reaped nor marked; reap frees the slot but a retry is refused until the lost attempt is marked; WORKER_LOST written only for a lease with wrote=0; no marker for a lease that wrote a receipt before dying; mixed history marks only the lease that never wrote and attempt 3 is refused with RETRY_EXHAUSTED; takeover fences the dead lease and the marker carries the new epoch; the dead worker's old-epoch write is refused by both store instances; new attempt receipt must chain to the dead attempt's receipt. Concurrency (two Store instances, 25 rounds each): exactly one epoch winner per story and exactly one live lease per task.

## Defects and fixes
- 1 test defect (fixed in `tests/vst/test_e5_process_death.py`): an attempt-2 receipt with `prev_receipt_sha256=None` raises `ContractError` at contract validation, before the store chain check; the test expected `StoreError(kind='chain')`. The test now asserts the ContractError for the unlinked receipt and the chain error for a receipt with a wrong prev hash.
- Product bugs found in `tools/vst`: none. No file under `tools/vst` was changed by this work.

## Not verified
- Behaviour on non-Windows platforms (process-tree kill, file permissions).
- Event-log tampering tests, schema-version refusal and runner output caps are E3/E4 test scope, not covered here.
- The real_run_and_sign scenario ran only one tiny allowed command; timeout and process-tree kill paths are not exercised by E5.
- No mutation or red/green checks were run by design; assertions were justified by the observable verdicts and database rows.
- Evidence is for the dirty working tree described above, not a committed head.
