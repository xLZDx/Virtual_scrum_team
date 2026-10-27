# Change 0467: Record bounded S2 Windows nested Job Object evidence

## What changed

- Recorded the exact-head Windows nested Job Object assignment probe and its bounded result.
- Updated the VST-013 acceptance matrix and S2 state/backlog to mark nested assignment as demonstrated while retaining strict launch, termination, kill-on-close, descendant cleanup, and ACL limits.
- Preserved S2 `NOT APPROVED`; this does not complete VST-013 or authorize restricted process-kill cases.

## Why

The S2 matrix previously had no actual nested Windows Job Object evidence. A safe bounded probe confirmed that the runner process can be placed in an outer job and the project's real `_JobObject.attach` can assign a normal-exit child to an inner job while both memberships are observable. The probe avoided termination APIs and does not establish cleanup or full Windows acceptance.

## Affected contracts and paths

- `docs/sdlc/evidence/s2-windows-nested-job-safe-a6ea0dc-20261027.md`
- `docs/sdlc/evidence/s2-task-acceptance-a6ea0dc-20261027.md`
- `core/BACKLOG.md`, `core/STATE.md`
- `docs/sdlc/STATE.md`, `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Exact source/test HEAD: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`.
- Designated `e2e-runner`, GPT-6 Luna / medium, ran the in-memory `C:\Python314\python.exe -c` probe with Python 3.14.3. PowerShell exited 0; the probe runtime was 1.626 seconds.
- The runner process was confirmed in an outer Job Object with no configured limits or kill-on-close. The actual project `_JobObject.attach(proc)` assignment returned true (WinError 0); `IsProcessInJob` confirmed the child in both outer and inner jobs. The child read one stdin byte, exited normally with code 0, and both handles closed successfully after exit.
- No `TerminateJobObject`, `taskkill`, other kill API, pytest selector, file write, network call, timeout, crash, descendant, or persistent system change occurred. Exact script and JSON output are in the evidence file.
- Strict suspended creation/assignment/resume, kill-on-close cleanup, descendant termination, timeout cleanup and Windows ACL/key isolation remain `NOT_VERIFIED` or `NOT_RUN`. The 20 policy-restricted/unavailable selectors remain `NOT_RUN`.
- No source/test files were changed. No tests/checks/build/CI/migration were run for this documentation update. The protected pre-existing untracked evidence file was not modified or staged.

## Decision and ownership

- Decision: mark only nested Job Object assignment as evidenced; retain VST-013 partial and S2 `NOT APPROVED`.
- Evidence record/local Git: Codex. Runtime execution: `e2e-runner`. GPT-PM owns exact-head gate adjudication. Operator owns any policy change or authorization for restricted scenarios.
- No S3 source work, push, PR, or merge is authorized by this record.

Executor: Codex
