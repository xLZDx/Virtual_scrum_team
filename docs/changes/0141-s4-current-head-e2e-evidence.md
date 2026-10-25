# 0141 S4 current-head mapped E2E evidence

## What changed

- Recorded the exact current-head Windows-host run for the seven mapped S4/S3 E2E selectors.
- Recorded the exact source HEAD, environment versions, command, counts and warning.
- Preserved a first local invocation as `RESULT_NOT_CAPTURED` because its nested process session handle was not retained; it is not counted as a test result.
- Recorded the current-head WSL transfer as `RESULT_NOT_CAPTURED`, without inferring a run ID, clone, hash, permission boundary or POSIX result.
- Updated the S4 acceptance status in the plan and backlog, added a decision/lesson entry, and regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The previous successful transfer and seven-selector WSL run are bound to source HEAD `452c8ea`, while the current candidate is `c5289ca`. The current Windows-host run supplies exact-head evidence for the mapped selectors, but cannot substitute for POSIX snapshot acceptance. A missing correlated transfer response must remain explicit and must not be repaired by inspecting an unidentified destination.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-current-head-e2e-c5289ca.md`: execution and acceptance evidence.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: current S4 evidence summary.
- `core/BACKLOG.md`: S4 residual acceptance.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: exact-head decision and session-capture lesson.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Verification state

- At clean source HEAD `c5289cae2255b51e165ec8e65a322c752be0e99a`, the captured Windows-host run passed 7 selectors, with 0 failures and 0 skips; it emitted one existing pytest-asyncio deprecation warning.
- The current-head WSL transfer response/session result was not captured. POSIX transfer and runtime acceptance remain `NOT_RUN` / `NOT_VERIFIED` as detailed in the evidence file.
- No product or test source code changed in this evidence update.

## Decisions and ownership

- Keep the WSL run and worker-boundary claims tied to `452c8ea`; do not carry them forward to `c5289ca`.
- Do not inspect, clean, delete or retry a destination without correlated run metadata.
- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`). Technical service owner for the private WSL runner is not established in repository records.

## Next steps

1. Preserve the Windows-host 7/7 result as exact-head mapped-selector evidence only.
2. Keep WSL transfer, POSIX symlink, signer, report and gate acceptance open; no result is inferred from the uncaptured transfer or the earlier `452c8ea` run.
3. Continue S4 closure only with evidence permitted by the applicable no-metadata and approval rules.
