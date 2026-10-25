# Change 0157: Re-run mapped S4 Windows E2E selectors

## What changed

- Recorded the seven mapped Windows E2E selectors at exact code/test HEAD `2dc6947e416b61103548285ec279d787c1027d8b`.
- Updated the S4 plan and backlog while preserving the separate current-head registry result and unresolved WSL/POSIX, signer, report, receipt, and gate work.
- Added exact command, interpreter, duration, warning, selector count, HEAD, and clean before/after status to the evidence file.

## Why

The mapped Windows E2E evidence at `cbdce020` preceded later registry source changes. This run re-established the seven accepted selectors after those changes without making any claim about the uncorrelated WSL transfer.

## Affected paths and contracts

- `docs/sdlc/evidence/s4-mapped-windows-e2e-2dc6947.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- generated `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Exact command: pinned CPython 3.14.3 with pytest 8.4.2, `-q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin`, followed by the seven selectors in the evidence file.
- Result: **7 passed, 0 failed, 0 skipped**, 25.47 seconds; one existing pytest-asyncio deprecation warning.
- Exact HEAD before/after: `2dc6947e416b61103548285ec279d787c1027d8b`; status clean before/after.
- No WSL transfer, POSIX symlink scenario, signer socket, report-bound runner, receipt, or authoritative gate was exercised.

## Decisions and ownership

- Keep Windows selector evidence distinct from WSL/POSIX acceptance.
- Do not inspect or retry the prior `RESULT_NOT_CAPTURED` WSL transfer.
- Accountable task owner: operator under delegated S4 work. Executor: Codex through `e2e-runner`.
- Technical WSL runner owner is not established in repository records.
