# 0108 S4 E2E placeholder-hardening rerun

## What changed

- Extended the S4 local E2E evidence with the exact post-commit rerun after replacing unused snapshot CLI inputs with visibly inert placeholders.

## Why

E2E change record 0107 left its post-commit verification open. The rerun confirms the input cleanup preserves the observable refusal behavior at the committed test revision.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-e2e-local-1cd868b.md`: exact revision, command, count, duration, environment, and dirty-worktree limitation.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- The wrong-distro input is rejected before any WSL invocation; placeholder user, group, and root values are never consumed as environment identities or paths.

## Verification state

- Revision: `b8128461ec20c0b05f8172f5599e5be80ed626f9`.
- Command: `python -m pytest -q tests/qa/test_s4_qa_e2e.py`.
- Result: 2 passed, 0 failed in 6.61 seconds on Windows Python 3.14.3 / pytest 8.4.2; one existing `pytest-asyncio` deprecation warning.
- Shared category and generated-document-registry files were modified concurrently but not staged in the test commit. Native S4 snapshot/signing/gate acceptance remains `NOT_RUN`.

## Follow-up

1. Coordinator records the two E2E IDs in `docs/qa/categories.json` with valid ancestor provenance.
2. Run the full mapped category only on a clean exact-head Ubuntu-24.04 source snapshot after S4 private provisioning values are established.
