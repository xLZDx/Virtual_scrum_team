# Change record 0309: authorize one report-bound WSL worker identity test

## What changed

- Recorded the operator-authorized `vst-runner` 997:988 to `vst-worker` 999:989 child-process boundary in the S4 plan as S4.2.3 / AC-16.
- Added an implementation design that keeps the QA runner and its report/scratch artifacts in UID 997, with one fixed helper and one report-bound functional selector.
- Added backlog item VST-038 and the append-only decision entry.
- Kept all existing process-kill, timeout, process-death, mutation, and E8 policy exclusions `NOT_RUN`.

## Why

The operator authorized a narrow WSL helper to enable one real report-bound child identity check. The current bounded QA runner launches pytest as its current identity and has no 997-to-999 helper. A separate restricted-root harness exists, but it serves a different runtime profile. The implementation should prove the requested identity boundary without changing the whole runner's process or artifact ownership.

## Contracts and paths

- `docs/S4_WSL_WORKER_UID_HELPER_DESIGN.md` defines the fixed caller, target identity, interpreter, environment, installation path/permissions, failure handling, and verification scope.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` adds S4.2.3 and AC-16.
- `core/BACKLOG.md` tracks VST-038.
- `core/DECISION_LOG.md` records the operator authorization and non-expansion of policy exclusions.

## Verification state

Documentation design only. No helper source, installed binary, selector, test run, process-kill scenario, build, or platform proof is claimed by this record. The existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not used as provenance for this change.

## Ownership and next action

Operator is accountable; Codex executes. The WSL infrastructure owner is not identified in canonical records. Next: implement the helper source and installer, then delegate the report-bound selector and execution to the designated test roles.
