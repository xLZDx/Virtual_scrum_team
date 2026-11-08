# U1 Sprint — Unified Core Plan (2026-11-08)

## Sprint scope and acceptance

Build isolated AEVE role-request router with role/finding/executor abstractions, support flexible executors, and establish measurement baselines for unified core cost.

**Definition of Done**: All 8 tasks CODE_COMPLETE with focused functional tests passing, internal review consensus, and GPT-PM final approval before push.

## Task status summary

| Task | Description | State | Evidence | Blocker |
|------|-------------|-------|----------|---------|
| U1-1 | Token baseline script | CODE_COMPLETE | Commit 06a483b; token script added | None |
| U1-2 | BLOCKER/MAJOR fixes (6 critical issues) | CODE_COMPLETE | Commit f1ff359, 6f125dd; B1-B3, M1-M3 fixed | PROHIBITED (test execution by specialist agents) |
| U1-3 | Request/result validators | CODE_COMPLETE | Commit d13f0cc; validators implemented | PROHIBITED (agent tests blocked) |
| U1-4 | Role table builder | CODE_COMPLETE | Commit 48edf6f; builder + loader added | PROHIBITED (agent tests blocked) |
| U1-5 | AEVE CLI adapter | CODE_COMPLETE | Commit 40f0e58; isolated adapter v2 | PROHIBITED (agent tests blocked) |
| U1-6/U1-7 | Role router + single entry | CODE_COMPLETE | Commit 3602afa; router and entry command | PROHIBITED (agent tests blocked) |
| U1-8 | Token comparison script | CODE_COMPLETE | Commit 0503e66; synthetic tests pass | PROHIBITED (real measurement NOT_RUN) |
| U1-9 | Global Claude config scope | NOT_STARTED | Blocked on decision | OPERATOR — (OD-3: should agent model config be per-project operator choice, or globally fixed? — recommend operator approval before coding starts) |

## Current phase: Verification

All 8 tasks at CODE_COMPLETE awaiting:
1. **Functional test execution** by unctional-test-reviewer and 2e-runner (baseline: 534+62 tests, focused new tests for U1-2 fixes)
2. **Internal review consensus** across relevant specialist agents (architect, code-explorer, security-reviewer if applicable)
3. **GPT-PM final code/contract approval** before push to PR

## Remaining findings (non-blocking)

23 items (8 MAJOR + 15 MINOR) documented in docs/sdlc/evidence/u1-remaining-findings-20261108.md for backlog prioritization.

## Next action

Await functional-test-reviewer and e2e-runner to write and execute focused functional tests per U1-2 acceptance criteria; once green, return for internal review consensus and GPT-PM gate.

U1-9 unblocks after operator decision on (OD-3).
