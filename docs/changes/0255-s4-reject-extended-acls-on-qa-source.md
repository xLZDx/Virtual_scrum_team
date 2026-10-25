# Change 0255: Reject extended ACLs on QA source and Git state

## What changed

- Generalized the shared POSIX ACL inspector in `tools/vst/sandbox.py` with scope-neutral errors.
- Extended the `tools/qa/run.py` read-only preflight to reject extended access ACLs on every inspected source/Git candidate and default ACLs on directories, failing closed when ACL inspection is unavailable or errors.
- Updated the S4 plan and current state to reflect 7b0 report-bound functional evidence and the remaining gates.

## Why

Fresh security review found a conditional MAJOR: `_worker_writable()` checked only owner/group/other mode bits. A named POSIX ACL could grant worker UID 999 write access to a source or Git metadata path while the mode check passed. A worker can modify that state during a run, invalidating the exact-source and report-integrity assumptions. The preflight now rejects extended ACLs before testing.

## Decisions and ownership

- Fail closed on any extended ACL for source/Git preflight paths rather than attempting platform-specific ACL permission calculation. Directory default ACLs are also rejected to prevent inherited worker grants.
- Accountable task owner: operator. Coordinator/executor: Codex. Production-code implementation: `implementation-engineer`. Security review: `security-reviewer`.

## Affected contracts and paths

- `tools/qa/run.py`: source/Git read-only boundary preflight.
- `tools/vst/sandbox.py`: shared ACL inspection helper used by signer and QA-source guards.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`, `core/STATE.md`.

## Verification state

- Finding source: fresh static `security-reviewer` report, GPT-6 Luna low, reviewed target product/test HEAD `7b0fe2339980b6b5d7278c0aeaaa58cc5fab8b71`; current repository HEAD at review was `18a800d` with documentation-only differences. Finding location: `tools/qa/run.py` old lines 159–168 and 281–288.
- Code fix is implemented; mapped named-ACL regression tests and fresh security review are pending. No tests/checks were run for this change by the implementation agent or coordinator.
- S4 report-bound functional evidence remains scoped to HEAD `7b0fe23`; this fix invalidates that as exact-final-head acceptance until the mapped tests and relevant functional path are rerun.
- PM Bridge health and mode status returned `Transport closed`; exact-head GPT-PM approval remains outstanding.

Executor: Codex
