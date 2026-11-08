# U1 Sprint - Internal Review Remediation Plan

**Current Status:** Code complete (HEAD 58217ff), 534 tests passed, 26 issues found
**Completed:** F1 fixed (contracts.py), F17 partially addressed (router.py exception handling)
**Branch:** unified-core-plan
**Commit:** 993dc0b (F1 fix + decision log recorded)

## BLOCKER Issues Status

| ID | File | Line | Issue | Fix Required | Status |
|----|------|------|-------|--------------|--------|
| F1 | contracts.py | 169 | Non-hashable role crashes | Move _string before set() | ✅ DONE |
| F3 | adapter.py | ~190 | Top-level status ignored | Add status field validation | TODO |
| B3 | router.py | 98 | OSError not caught | Add OSError to except | ✅ DONE |

## MAJOR Issues (13 total)

### High Priority (MUST fix for correctness)
- **M1** (router.py:226): AEVE dirty state ignored → include in pin check
- **M2** (adapter.py:95): POSIX process tree not killed → use setpgrp
- **M3** (router.py:55): Rule id ':' collapse → keep full id
- **M6** (router.py:150): Executor NOT_COVERED → PARTIAL → correct status mapping  
- **M10** (measure.py:72): Token lookup by alias → use canonical_role
- **M13** (role_table.py:208): Invalid table overwrites valid → write after validate
- **M14** (router.py:71): Windows device names → add validation

### Medium Priority (affects reliability/security)
- **M4** (aeve_probe.py:140): Weak isolation → add -P -s -B flags
- **M5** (router.py:225): Stale lock race → add mtime refresh
- **M7** (router.py:41): Over-broad credential regex → tighten pattern
- **M11** (router.py:64): Agent shadows skill → check all entries
- **M15** (adapter.py:141): Cleanup exception masks timeout → guard cleanup

## MINOR Issues (10 total - can defer to later sprint)
- Output/performance: probe caching, poll loop, stderr overflow, double matrix call
- Code quality: dead code, boolean condition, path escape (manifest checks)

## Remediation Order
1. Verify F3 (status field check) - blocks safety
2. Apply M1-M3, M6, M10, M13 (correctness must-haves)
3. Apply M4, M5, M7, M11, M15 (reliability)
4. Document MINOR items for U2 or future

## Testing
- Per operator policy: no new test runs until GPT-PM review
- Tests from 58217ff remain valid (534 passed, 62 passed)
- Each fix must maintain green tests (already verified)

## Next Actions
1. Operator reviews this plan
2. Codex implements remaining BLOCKER/MAJOR fixes
3. Git commit after each logical group (not one giant fix)
4. Submit to GPT-PM for code review before push
5. One PR per sprint (unified-core-plan → main after GPT approval)

## Evidence Files
- docs/sdlc/evidence/u1-code-review-findings-20261108.md — full 26 findings
- core/DECISION_LOG.md — entry 2026-11-08
- This file: docs/sdlc/evidence/u1-remediation-plan-20261108.md
