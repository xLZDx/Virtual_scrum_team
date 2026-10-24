# 0122 S4 mapped native E2E run

## What changed

- Added `docs/sdlc/evidence/s4-native-e2e-a198f0af.md` with the mapped native E2E command, exact environment, per-ID outcome, failure classification, read-only confirmation, and remaining gates.
- Updated the S4 backlog and lessons to record the POSIX-versus-Windows platform-guard test defect.

## Why

After the successful source transfer and worker-boundary verification in change 0123, the coordinator authorized only the mapped native pytest/E2E scenarios as a read-only worker, without signer, report, or gate execution.

## Affected contracts and paths

- `docs/qa/categories.json`: source E2E ID selectors and category argv contract.
- `tools/qa/registry.py`: exact pytest argv projection from the committed E2E IDs.
- `tests/qa/test_s4_qa_e2e.py`: one assertion expects the Windows distro-validation error while running under POSIX.
- `docs/sdlc/evidence/s4-native-e2e-a198f0af.md`: native result separate from transfer evidence 0123.
- `core/BACKLOG.md` and `core/LESSONS_LOG.md`: E2E defect and next step.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`).
- The mapped tests ran as the provisioned non-root worker against only the returned snapshot run ID. Temporary files were bounded under `/dev/shm`; the checkout was not writable by the worker.
- The assertion failure is a test defect: POSIX host validation correctly precedes wrong-distro validation. The test oracle must be made platform-aware while retaining both guard assertions.
- No quarantine, assertion weakening, product-source mutation, signer use, report generation, receipt, or gate evaluation occurred.

## Verification state

- Snapshot: run `a198f0afd1c64dc2b960a08f757eff9c`, candidate HEAD `e43329f0d8312c94a0e4316a4d54ece605a79dec`.
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4, non-root worker.
- Exact pinned pytest argv run: 6 passed, 1 failed in 4.29 seconds, no warnings. A prior run with an extra `--basetemp` argument had the same 6/1 result in 3.51 seconds; the exact argv run is the primary evidence.
- Failure file/line: `tests/qa/test_s4_qa_e2e.py:64`; observed `snapshot transfer must be invoked from the Windows host`, expected `distribution must be the named Ubuntu-24.04 WSL distro`.
- Post-run worker Git status for this run returned clean with exit code 0 and no output. No snapshot changes were made.
- Native report-bound execution, signer, receipt, and gate remain `NOT_RUN`.

## Follow-up

1. E2E owner updates the assertion to test the POSIX host guard on POSIX and the wrong-distro guard on Windows, without weakening either.
2. Commit the test correction with a dedicated detail record.
3. Create a new clean snapshot and rerun the mapped native E2E category; preserve 0122 as the original failure evidence.
4. Resolve the signer socket separately before report-bound QA and exact-head gate acceptance.
