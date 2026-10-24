# 0070 S2 idempotent operation and breaker replay regressions

## What changed

- Added `tests/vst/test_s2_operation_recovery.py` with four functional regressions: external-operation intent/completion transaction boundaries, timeout leaving durable `PENDING` followed by same-key/same-payload recovery and changed-payload rejection, replay of legacy completed operation results, and rejection of a changed but validly signed manual-override record after restart when the action ID is already complete.
- Added `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md` with red/green history, exact source revisions, focused and combined commands, runtime counts, and explicit skip reasons.

## Why

The reliability review required proof that backend operations do not hold the Store transaction during external effects, that timeout/unknown outcomes remain pending and recover safely, that existing completed rows remain compatible, and that durable override replay cannot substitute a different signed record under the same action ID.

## Verification state

- Initial source HEAD `14bd1e85459d97c9caa90a62b117a41020200b9a`: 3 passed, 1 failed; the failure exposed external-operation history verification that rejected a new pending row during external-anchor synchronization. Fixed in change 0067.
- Intermediate source HEAD `cc30917644e762065a6afed3650ad890cf124e22`: the four focused regressions passed. A broader run exposed two E2E-owned failures: a thread-affinity error in the external-anchor fixture and a candidate commit unavailable to the bare remote. The test owner corrected its fixture; the synthetic publishing source binding was fixed in change 0069.
- Final source HEAD `c0e7e9ce15958b6c6de7811bcaf1020119ba169d` command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Final result: exit 0; 76 passed, 14 skipped, 1 pytest-asyncio deprecation warning. Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- The 14 skipped platform cases remain `NOT_RUN`; causes are listed in the evidence file. This commit does not claim full S2 runtime acceptance.

## Ownership

- Accountable task owner: operator.
- Functional test author/executor: functional-test-reviewer (`gpt-6-luna`).
- E2E callback and Git-timeout fixtures are separate additions owned by the E2E agent and are not included in this commit.

Agent-Attribution: functional-test-reviewer (`gpt-6-luna`); Codex executor
