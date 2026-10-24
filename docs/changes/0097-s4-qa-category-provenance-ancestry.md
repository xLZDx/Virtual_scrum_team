# 0097 S4 QA category provenance ancestry

## What changed

- Added bounded Git ancestry validation for the registry's source head and every supported category's source head.
- The registry loader now resolves the current full candidate HEAD and rejects provenance commits that are missing, unreachable from the candidate, or outside its history.
- Updated the S4 technical design, acceptance plan, decision log, and lessons log.

## Why

Checking that a source commit exists is not enough. A commit can remain in the object database while not belonging to the candidate's history, or it can describe a stale selector set. The registry and each supported category must derive from commits included in the candidate line before their test IDs can enter a report-bound run.

## Affected contracts and paths

- `tools/qa/registry.py`: source-provenance validation.
- `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md` and `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: AC-3 and provenance rule.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: design decision and provenance lesson.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- Each Git ancestry query has a five-second timeout; inability to establish ancestry fails closed.
- The signed v2 receipt and authoritative gate remain responsible for binding evidence to the exact candidate HEAD.
- Technical owner for QA category maintenance remains `UNKNOWN` in the repository's canonical ownership sources.

## Verification state

- Manual source inspection only. No tests, checks, builds, CI, dependency installation, migration, or QA execution were run.
- Exact WSL runtime and signer execution are `NOT_RUN`; functional and E2E owners must exercise ancestor, unrelated-commit, and stale-head cases after all S4 coding is complete.

## Follow-up

1. Continue implementation through the remaining S4 source scope.
2. After code completion, have the designated functional/E2E agents author and execute registry-provenance rejection cases with exact-head evidence.
