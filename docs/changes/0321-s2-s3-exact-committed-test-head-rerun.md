# Change 0321 — Record exact committed-head S2/S3 regression reruns

## What changed

- Updated the S2/S3 regression evidence file with the post-commit reruns at exact repository HEAD `2eec05101abe38b7ec50aefcb3ec04788dc26195`.
- Updated S2 phase state, current project checkpoint, and VST-013/VST-029 backlog entries to distinguish committed-head test evidence from remaining `NOT_RUN` platform, STOP and resume scenarios.
- Added this per-change record and corresponding decision/lesson entries.

## Why

Change 0320 committed the new cleanup tests and evidence, so the prior test runs at source HEAD `5ae495c` had a dirty test file. Required test agents reran the applicable safe selectors at the resulting committed head and confirmed the same outcomes without edits. This closes that exact-test-source gap for the selected scenarios; it does not close the excluded runtime acceptance.

## Evidence and verification

- Exact committed repository/source/test HEAD before and after: `2eec05101abe38b7ec50aefcb3ec04788dc26195`.
- `functional-test-reviewer`: focused cleanup selectors, 12 passed / 290 deselected, exit 0.
- `e2e-runner`: S2 Store lifecycle 10 passed / 9 explicit POSIX skips; S2 operation recovery 4 passed; S3 adapter safe subset 8 passed / 1 resume deselected; S3 pilot safe subset 3 passed. All exit 0.
- Python 3.14.3; each invocation emitted one pytest-asyncio deprecation warning. The only pre/post dirty status entry was the preserved untracked `docs/sdlc/evidence/s2-functional-test-run.md`; no test agent edited files.
- Commands and case IDs: `docs/sdlc/evidence/s2-s3-current-source-regression-5ae495c.md`.
- No tests/checks were run by Codex in this documentation update.

## Remaining acceptance and owners

- S2 still needs fresh post-test specialist consensus and GPT-PM approval. Operator owns any authorization required for process-kill, POSIX sandbox, Windows Job Object nesting, and E8 crash/resume cases; Codex prepares and coordinates; designated test agents execute only if the gate permits.
- S3 still needs resume/STOP and sandbox-boundary acceptance; operator owns any required authorization, Codex coordinates, and `e2e-runner` executes allowed cases.
- No push/PR/merge is approved by this documentation change.

Change: 0321
Executor: Codex
