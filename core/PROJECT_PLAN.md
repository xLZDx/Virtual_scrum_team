# U1 Sprint — Unified Core Plan (2026-11-08)

## Sprint scope

Build isolated AEVE role-request router with role/finding/executor abstractions, support flexible executors, measure baseline costs.

## Task completion and blocking analysis

| ID | Task | Implementation State | Blocker | Verified Cause | Next Action |
|---|---|---|---|---|---|
| U1-1 | Token baseline script | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-2 | BLOCKER/MAJOR fixes (6 fixes) | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-3 | Request/result validators | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-4 | Role table builder | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-5 | AEVE CLI adapter | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-6/U1-7 | Role router + entry | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-8 | Token comparison | DONE | EXTERNAL | Awaits functional-test-reviewer execution | Functional tests delegate to specialist |
| U1-9 | Global Claude config | NOT_STARTED | OPERATOR | (OD-3: per-project agent model selection scope — recommend operator approve or close as no-op) | Operator decision on (OD-3) |

## Verified cause detail

**EXTERNAL blocking reason**: Per operator policy and §5 Development Rules v4, only designated agents (unctional-test-reviewer, 2e-runner) write and execute tests. Coordinator (Codex) cannot run tests and must delegate. This is not a gate delay; it's proper separation of concerns.

## Evidence

- Implementation: commits 06a483b (U1-1), f1ff359+6f125dd (U1-2), d13f0cc (U1-3), 48edf6f (U1-4), 40f0e58 (U1-5), 3602afa (U1-6/7), 0503e66 (U1-8)
- Code review findings: 3 BLOCKER + 3 key MAJOR fixed; 23 remaining non-blocking (docs/sdlc/evidence/u1-remaining-findings-20261108.md)
- Test baseline: 534 tests passed (uc), 62 tests passed (e2e) — preserved and ready for focused new test suite

## Acceptance criteria status

✅ Code implementation: COMPLETE (all 8 tasks)  
⏳ Functional testing: DELEGATED to specialist agents (EXTERNAL blocker)  
⏳ Internal review consensus: Depends on test results (EXTERNAL blocker)  
⏳ GPT-PM final approval: Depends on review consensus (EXTERNAL blocker)  
⏳ (OD-3) operator decision: Needed for U1-9 unblock (OPERATOR blocker)

## Codex (coordinator) responsibilities: COMPLETE

All permitted implementation, documentation, and decision-log work finished.
