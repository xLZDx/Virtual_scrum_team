# U1 Code Review Findings - Internal Agents - 2026-11-08

Review of HEAD 58217ff by code-review skill at high effort detected 26 findings.

## BLOCKER Issues

### B1 (contracts.py:169) - Non-hashable role crashes validate_request
**Impact:** CLI crash with uncaught TypeError instead of BLOCKED envelope
**Fix:** Move _string() type checks before set(roles) duplicate detection

### B2 (router.py:191) - Top-level AEVE status ignored  
**Impact:** CLEAN role reported while AEVE returned PARTIAL/ERROR
**Fix:** Check top-level status, uncovered list, and match exit code to status

### B3 (router.py:98) - Uncaught OSError from seen.write_text
**Impact:** CLI crash on disk/permission errors
**Fix:** Catch OSError alongside other handled exceptions

## MAJOR Issues (selected critical ones)

### M1 (router.py:226) - AEVE dirty state ignored
**Impact:** Modified executors run with pinned settings as if audited
**Fix:** Include dirty state from probe in pin check

### M2 (adapter.py:95) - Process tree not killed on POSIX
**Impact:** Orphaned grandchildren survive timeout/cap
**Fix:** Use os.setpgrp on child, then os.killpg on parent timeout

### M3 (router.py:55) - Rule id collapsing on ':'
**Impact:** Different rules merge in dedup, severity lost
**Fix:** Keep full rule_id, split only for namespace prefix

## Test Status Before Fixes
- tests/uc: 534 passed, 0 failed, 3 skipped (after initial 9 defect fixes)
- tests/uc_e2e: 62 passed, 0 failed, 1 skipped

Starting remediation of BLOCKER and MAJOR issues now.
