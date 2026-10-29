# Change 0469: Record safe S2 Windows strict Job Object launch evidence

## What changed

- Recorded one E4.2 probe using the actual project suspended process-creation, Job Object
  assignment, and primary-thread resume helpers.
- Updated the VST-013 task matrix to distinguish strict launch sequencing from cleanup/termination
  acceptance.
- Kept kill-on-close, descendant cleanup, timeout/crash, Windows ACL, and prohibited scenarios
  `NOT_VERIFIED` or `NOT_RUN`.

## Why

The prior bounded probe established nested assignment for an already-running child. This safe
follow-up establishes the separate strict ordering: create suspended, assign to both observed
jobs, resume, and exit normally. It does not test process termination or the cleanup guarantee.

## Affected contracts and paths

- `docs/sdlc/evidence/s2-windows-strict-suspended-launch-a6ea0dc-20261027.md`
- `docs/sdlc/evidence/s2-task-acceptance-a6ea0dc-20261027.md`
- `core/BACKLOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Designated `e2e-runner`, GPT-6 Luna / low, executed the exact in-memory script in the linked
  evidence record on Windows CPython 3.14.3, source/test HEAD `a6ea0dc`.
- Child normal exit: code 0. Outer and inner memberships were confirmed; both handles closed after
  exit. The executor wrapper did not preserve its own exit code or exact duration; both are
  recorded `NOT_RECORDED`.
- No termination API, pytest, file, or network operation was used.
- This remains partial VST-013 evidence and does not approve S2 Phase 8.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not
  modified or staged.

## Decision and ownership

- Decision: accept only the normal-exit strict launch sequencing result for the exact source/test
  head; keep cleanup and other acceptance limits open.
- Codex owns evidence reconciliation; GPT-PM owns the exact-head gate; the operator owns any
  scope/authorization change for prohibited process-termination scenarios.

Executor: Codex
