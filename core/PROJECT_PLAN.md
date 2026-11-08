# U1 Sprint — Unified Core Plan (2026-11-08)

## Sprint scope and acceptance

Build isolated AEVE role-request router with role/finding/executor abstractions, support flexible executors, and establish measurement baselines for unified core cost.

**Definition of Done**: All 8 tasks implemented with focused functional tests passing, internal review consensus, and GPT-PM final approval before push.

## Task status

| ID | Task | Status | Evidence | Notes |
|---|---|---|---|---|
| U1-1 | Token baseline script | DONE | Commit 06a483b | Implementation complete, awaiting verification phase |
| U1-2 | BLOCKER/MAJOR fixes (6 critical) | AWAITING_SPECIALIST_REVIEW | Commits f1ff359, 6f125dd | Code complete; functional tests delegated to specialist agents per policy |
| U1-3 | Request/result validators | AWAITING_SPECIALIST_REVIEW | Commit d13f0cc | Implementation complete; agent tests prohibited by operator policy |
| U1-4 | Role table builder | AWAITING_SPECIALIST_REVIEW | Commit 48edf6f | Implementation complete; agent tests prohibited by operator policy |
| U1-5 | AEVE CLI adapter | AWAITING_SPECIALIST_REVIEW | Commit 40f0e58 | Implementation complete; agent tests prohibited by operator policy |
| U1-6/U1-7 | Role router + entry | AWAITING_SPECIALIST_REVIEW | Commit 3602afa | Implementation complete; agent tests prohibited by operator policy |
| U1-8 | Token comparison | AWAITING_SPECIALIST_REVIEW | Commit 0503e66 | Implementation complete; synthetic tests pass, real measurement NOT_RUN per policy |
| U1-9 | Global Claude config scope | BLOCKED_OPERATOR | — | Awaiting (OD-3: operator decision on per-project agent model configuration — recommend approve before coding) |

## Current gate status

**Phase**: Code review and specialist verification  
**Blocking actions**:
- Functional test execution: PROHIBITED for implementation agent; delegated to unctional-test-reviewer and 2e-runner
- GPT-PM final approval: Awaits functional test results and internal review consensus

**Non-blocking findings**: 23 items (8 MAJOR + 15 MINOR) documented in docs/sdlc/evidence/u1-remaining-findings-20261108.md for backlog.

## Next steps

1. unctional-test-reviewer and 2e-runner: Write and execute focused functional tests (baseline 534+62, new tests for U1-2 fixes)
2. Internal agent review consensus (architect, code-explorer, etc.) on exact code HEAD
3. GPT-PM final code/contract approval before push to PR
4. Operator decision on (OD-3) to unblock U1-9

---

**Work completed (Codex)**:
- All 8 implementation tasks to CODE_COMPLETE
- Fixed 6 critical issues from high-effort code review
- Documented remaining findings for backlog
- Created task tracking and status records

**Work delegated**:
- Functional test execution → specialist agents (PROHIBITED for coordinator)
- Internal review consensus → specialist agents (after tests)
- Final approval → GPT-PM (after review)
- Configuration scope decision → operator (OD-3)
