# S1 retrospective (control-plane core)

Branch `s1-control-plane-core`, head at writing time `5427bb7`. Date: 2026-10-24.
Sources: `core/LESSONS_LOG.md` (entries of 2026-10-24), `core/DECISION_LOG.md` (S1 entries), `git log`, `git show --stat`, `docs/sdlc/evidence/*.md`.

Labels: MEASURED = taken from a git or evidence-file result; INFERRED = derived by the author of this report from those sources; REVIEWER = a claim made by a reviewer agent and recorded in the logs, not measured here.

## 1. Timeline and counts

Commit times are from `git show --stat` (MEASURED, all 2026-10-24, +03:00).

| Step | Commit | Time | Files | Lines +/- | What |
|---|---|---|---|---|---|
| Build | 768dff9 | 13:03 | 9 | +964/-3 | E1/E2 contracts, signing, gate (untested) |
| Build | e0ea991 | 13:07 | 7 | +932/-1 | E3/E4 store, runner (untested) |
| Build | c786755 | 13:09 | 7 | +603/-11 | E5 slice harness, store gap fixes (untested) |
| Test phase | 63e0e35 | 13:34 | 20 | +4702/-18 | defect fixes, first focused tests, evidence |
| Remediation 1 | 3e27720 | 14:17 | 25 | +7088/-1612 | manifest-bound gate, signed appends, hardened runner |
| Remediation 2 | f1956e2 | 14:52 | 29 | +2947/-369 | deciding-attempt head rule, retry cap, anchor, Job Object |
| Remediation 3 | 176a095 | 15:28 | 23 | +1535/-163 | budget boundary, per-epoch slot bound, env allowlist |
| Fourth-check fixes | 4ce6f8a | 15:42 | 14 | +115/-65 | zero cost_cap, U+2800, docs |

Other commits on the branch: `f664888` (E6 state authority wording), `5a749ee` (remediation status report), `45653fc` (review request stored in the repo), `5427bb7` (full status report). MEASURED: `git rev-list --count 9b5b597..HEAD` = 13 commits since the design baseline; 8 are code-or-test commits in the table, 5 are documentation or report commits (INFERRED split).

Review rounds: 4 (MEASURED from the decision log: reviews of 63e0e35, 3e27720, f1956e2, 176a095). Elapsed from first S1 code commit to the last fix commit: about 2 h 40 min (INFERRED from commit times).

### Findings by round (REVIEWER claims, confirmed by the coordinator where stated)

| Round | Head reviewed | Reviewers | Outcome | Findings recorded |
|---|---|---|---|---|
| 1 | 63e0e35 | 4 (silent-failure, security, reliability, architect) | 4 x MODIFY | chain definition mismatch store vs gate; artifact check optional; unauthenticated waiver; self-referential success conditions; `INSERT OR REPLACE` on leases; retry_cap unchecked at lease. Six decision groups (1)-(6) |
| 2 | 3e27720 | 4 (same roles) | 4 x MODIFY | 1 MAJOR found by all four (head check applied to history and markers, so retry on a new commit could never APPROVE); retry cap consumed by takeovers; budget not tied to `cost_cap`; event anchor re-signable; key distinctness only in test fixture; minor items |
| 3 | f1956e2 | 4 | 4 x MODIFY | 2 MAJOR, each by two or more reviewers: budget boundary (`spent == cap`); slot bound counting earlier epochs. Plus non-PASS counting, reaping, `extra_env`, key checks, integrity cross-check, invisible characters |
| 4 | 176a095 | 2 (reliability; security with architecture and documents) | both previous MAJORs closed; 1 new MAJOR | zero `cost_cap` tasks unstartable (regression from the round-3 fix); minor doc items |

Note: the logs record the round-4 result as "one new MAJOR, no open BLOCKER/MAJOR after the fix", not as a MODIFY verdict by name (INFERRED: it is a MODIFY-level result because a MAJOR was found).

### Test counts per round (MEASURED from `docs/sdlc/evidence/*.md`)

All runs were on working trees over the named base commit, not on a clean committed head.

| Run | Base | E1-E4 | E5 | Skipped |
|---|---|---|---|---|
| Test phase, before fixes | c786755 | 522 passed, 1 failed (of 523) | 18 passed | 0 |
| Test phase, after fixes | c786755 + fixes | 603 passed | 18 passed | 0 |
| Remediation 1 | 63e0e35 | 1105 passed | 38 passed | 2 (POSIX permission bits; `os.symlink` not permitted) |
| Remediation 2 | 5a749ee | 813 (E1+E2) + 506 (E3+E4) = 1319 passed | 52 passed | 2 |
| Remediation 3 | f1956e2 | 863 (E1+E2) + 593 (E3+E4) = 1456 passed | 64 passed | 2 |
| Fourth check | 176a095 | 1205 passed (E1+E2+E3+E5 files, one run), E4 not rerun (last full run 593 with E3) | included | 1 |

Defects found by tests (MEASURED from evidence): test phase 1 product defect (cwd error class) plus 2 design gaps; remediation 1 none; remediation 2 one (Windows post-exit descendant kill); remediation 3 none; fourth check none (one test defect of the author's own).

## 2. Why four rounds each found a MODIFY-level defect

Each cause below is grouped by what repeated across rounds.

1. A rule written separately in the gate and in the store.
   - Round 1: chain definition differed between `store.py` and `gate.py` (LESSONS_LOG "S1 specialist review").
   - Round 3: the budget limit was `spent == cap` in `charge` and `spent >= cap` in `append_receipt`/`acquire_lease` (`tools/vst/store.py:995`; LESSONS_LOG "S1 third review").
   - Early signal: BD-3 (derived results) and BD-5 (supervisor receipts) were specified apart and conflicted (LESSONS_LOG "E1/E2").

2. Test fixtures with one value in a dimension that is a history.
   - Round 2: every slice scenario used a single head, so the head check on history receipts was never exercised (`tools/vst/gate.py:200-207`; 1105 tests green).
   - Round 3: no scenario for a takeover after a full PASS set, so the slot bound across epochs was never exercised.

3. Boundary values not enumerated.
   - Round 3: spend exactly the cap was untested (cap-1, cap, cap+1 missing).
   - Round 4: `cost_cap` 0 is allowed by the manifest contract (`int >= 0`) but the decision text covered only the exact-cap case (`tools/vst/store.py:1030`).

4. A fix specified without listing the contract boundaries.
   - Round 4 is the direct case: the round-3 decision (A) changed `acquire_lease` to refuse at `spent >= cap` without checking zero cap. Round 3 also shows the earlier decision `spent >= cap` (round 2, decision 3) had been flagged as a risk in the decision log and not resolved.

5. Tests that pinned current behaviour.
   - Round 4: the E3 test "acquire_lease at cap 0 commits one marker" encoded the defect; its expectation came from the new code, not from the manifest contract.
   - Round 1: 603 tests were written from plan acceptance sentences and were green while chain mismatch, optional artifact check and unsigned waiver existed.

Contributing factors recorded in the logs: the baseline left the manifest without the fields that define success (round 1); no state-transition table was written before the store (E3/E4 entry); the Windows kill claim was documented as best effort with no test holding a live grandchild (round 2).

## 3. What worked

- Parallel independent reviewers finding the same defect: all four round-2 reviewers found the head-check defect separately; round 3 had two MAJORs each found by two or more reviewers (LESSONS_LOG rules: same finding from several reviewers is MAJOR by default).
- Tests written from findings: the round-2 test for a live grandchild exposed the Windows `taskkill` defect, fixed with a Job Object; the test phase turned each plan acceptance sentence into a test and found the missing artifact-binding path.
- Decision log recording risks and gaps at discovery: E3/E4 gaps were written down and closed in the very next sub-step (E5); the `>=` risk was recorded (it was not resolved in time, see section 4).
- Coordinator re-verification against files: each contested MAJOR was confirmed at a file and line before it entered a decision.
- Test agents told to report defects, not fix them, and to compare expected and executed test ids.
- A bounded stop: review rounds ended after round 4 by decision once no BLOCKER/MAJOR remained.

## 4. Process changes for S2 (checklist)

- [ ] Before specifying a fix, enumerate zero, one and max values from the manifest contract for every field the fix touches, and write the expected behaviour for each.
- [ ] For each history dimension (epoch, head, attempt), include a scenario where that dimension changes between attempts.
- [ ] Define each limit once (one helper) and test both sides: cap-1, cap, cap+1, and cap 0.
- [ ] A risk written in the decision log is a work item; resolve or explicitly reschedule it before the next gate.
- [ ] A test that pins a terminal side effect names the contract sentence it proves.
- [ ] Reconcile `core/BACKLOG.md` and `core/STATE.md` with the logs in each sprint-closing commit (at writing time BACKLOG lists VST-007/VST-008 as open and STATE.md still describes the zero-cap fix as pending; MEASURED by the status report entry).
- [ ] Start next-sprint documentation when testing of the current sprint starts (v4 item 7 was not done in S1).
- [ ] Split agent tasks per epic so each fits the turn limit; give reviewers an explicit "write the report before the last tool calls" instruction.
- [ ] Run tests on the committed head, not a working tree, so evidence names the exact head.

## 5. Metrics

| Metric | Value | Label |
|---|---|---|
| S1 code/test commits | 8 | MEASURED |
| Commits since baseline 9b5b597 | 13 | MEASURED |
| Change records in `docs/changes/` | 27 (0001-0027) | MEASURED |
| Review rounds | 4 | MEASURED |
| Reviewer runs | 14 (4+4+4+2) | INFERRED from the logs |
| Round verdicts MODIFY | 12 of 14 reviewer runs explicit; round 4 recorded as one new MAJOR | INFERRED |
| Latest E1-E4 + E5 passing | 1456 + 64 (round 3); 1205 in the fourth-check partial run | MEASURED |
| Skipped tests | 2 (POSIX bits, symlink) then 1 | MEASURED |
| Product defects found by tests | 2 (cwd error class; Windows post-exit kill) | MEASURED |
| MAJOR defects found by reviewers across rounds | at least 5 distinct root causes (chain, head check, budget boundary, slot bound, zero cap) | INFERRED |
| Mutation checks | NOT_RUN by operator decision | MEASURED |
| Independent review, push, PR | not done; operator-owned | MEASURED |

Not verified in S1: POSIX behaviour, Job Object nesting, naturally unkillable processes, mutation checks. Deferred to S2: authenticated reviewer key, runner-derived candidate_head, signing-key isolation, whole-database rollback detection.
