# S1 third round: E3 store and E4 runner test run

## Command
`C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e3_store.py tests/vst/test_e4_runner.py` (repo root, Windows, Python 3.14).

## Revision
HEAD `f1956e24933ca4a89cb215b7ce174d65ea263f49` plus an uncommitted working tree (19 changed or untracked paths, including the third-round `tools/vst/store.py`, `tools/vst/runner.py`, change record 0023 and these test files). The result applies to that working tree, not to a commit.

## Result
593 passed, 2 skipped (POSIX-only permission test and one Windows-skipped case), 0 failed.
Before the test updates the same files gave 16 failed, 490 passed: all 16 were old expectations (spent >= cap in append_receipt, released/NOT_RUN/BLOCKED not counted, runner attempt bound, old extra_env shadow rules).

## Tests changed or added
- E3 (`tests/vst/test_e3_store.py`): updated failed_attempts and retry expectations (every non-PASS result counts; RELEASED leases that wrote nothing count; FENCED never), replaced the old budget refusal tests. Added tests for: acquire_lease at cap 0 and at spent == cap committing exactly one signed marker and one BUDGET_EXCEEDED event across repeated calls; append_receipt allowed at spent == cap (gate APPROVE) and refused only above the cap; per-epoch slot bound after takeover with retry_cap 0 and 1 (attempt numbers stay global, chain error on restart); acquire_epoch reaping (EXPIRED plus WORKER_LOST, not FENCED); heartbeat refusals (RETRY_EXHAUSTED -> terminal, BUDGET_EXCEEDED or spent > cap -> budget, allowed at spent == cap); worker key equal to event_key -> kind 'key'; receipts_for_task integrity (all anchor tampers, missing, injected, duplicated rows, malformed or wrong event payloads, per-task isolation).
- E4 (`tests/vst/test_e4_runner.py`): extra_env allowlist cases and messages, attempt bound removed from the runner, reader exceptions (RuntimeError, KeyError, MemoryError, TypeError, OSError, ValueError) -> -4, root surviving the kill -> -4 (kill neutralised by monkeypatch), thread-start failure cleanup (child dead, pipes closed; Job Object closed on Windows).
- `tests/vst/e1e4_helpers.py`: unchanged.

## Product defects
None found in `tools/vst`. Observation only: the `tools/vst/store.py` module docstring (retry-cap and receipts paragraphs, budget paragraph) still describes the pre-third-round rules (FAIL/INCONCLUSIVE only, `attempt <= retry_cap + 1`, `spent >= cap` for append_receipt).

## Not verified
POSIX behaviour; mutation checks (NOT_RUN by operator decision); the root-survives-kill and reader-exception tests use monkeypatched seams (real child process, injected failure), not a naturally unkillable process; real thread exhaustion; Job Object nesting.
