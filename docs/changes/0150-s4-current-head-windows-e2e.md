# 0150 S4 current-head Windows mapped E2E

## What changed

- Recorded the seven registered mapped E2E selectors at exact repository HEAD `cbdce020fbd8030e7518285526831c2932f879a2`.
- Captured the pinned interpreter/plugin command, 7-pass result, warning, exact HEAD and clean before/after status.
- Updated the S4 plan and backlog while retaining historical WSL and failed-test records.
- Added decision/lesson entries and regenerated the document registry.

## Why

The previous mapped Windows run was tied to `c5289ca`, before the latest S4 source and test changes. The new run establishes the seven mapped selector results at the current exact HEAD without changing or retrying the uncorrelated WSL transfer.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-mapped-windows-e2e-cbdce020.md`: current exact-head Windows execution evidence.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: S4 evidence status.
- `core/BACKLOG.md`: current mapped-selector state and WSL residual.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: exact-head result and evidence separation.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Verification state

- Exact command: `C:\Python314\python.exe -m pytest -q -p no:cacheprovider -p tools.qa.pytest_pass_plugin` followed by the seven selectors in the evidence file.
- Result: **7 passed, 0 failed, 0 skipped**, 66.94 seconds, one existing pytest-asyncio deprecation warning.
- HEAD before/after: `cbdce020fbd8030e7518285526831c2932f879a2`; status before/after was clean.
- No WSL, other test module, or additional check was run.
- WSL transfer, POSIX symlink, signer, report, receipt and gate remain `NOT_RUN` or `NOT_VERIFIED` as applicable; prior `RESULT_NOT_CAPTURED` state is unchanged.

## Decisions and ownership

- Treat this as Windows mapped-selector evidence only; keep WSL/POSIX acceptance distinct.
- Preserve prior evidence and the no-retry/no-inspection rule for the unidentified WSL destination.
- Accountable task owner: operator under delegated S4 work. Executor: Codex (`e2e-runner`). Technical WSL runner owner is not established in repository records.

## Next steps

1. Retain the 7/7 Windows result at `cbdce020` as exact-head mapped-selector evidence.
2. Keep the current WSL/POSIX, signer, report and gate criteria open; do not infer acceptance from Windows execution.
