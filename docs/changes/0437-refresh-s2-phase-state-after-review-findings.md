# Change 0437: refresh S2 phase state after exact-source review findings

## What changed

- Updated the canonical S2 state to distinguish the last fully tested source head `f0bbac8` from the current correction commit `324f901`, whose focused regression tests and specialist re-reviews are pending.
- Recorded the new exact-source review findings and corrections without changing Phase 8 from `NOT APPROVED`.
- Updated the Build, Verify, and Gate phase rows to show the current code/test provenance and preserved policy exclusions.

## Why

The current-turn specialist review of `6117ba24..f0bbac8` found a capability-boundary BLOCKER (exploitability inferred, not runtime-reproduced), an external-anchor tail MAJOR, and a bounded Git cleanup MAJOR. The corrections were committed at `324f901`; until exact-head tests and fresh reviews finish, the prior `f0bbac8` results cannot be attributed to the corrected code.

## Affected paths

- `docs/sdlc/STATE.md`
- `docs/changes/0437-refresh-s2-phase-state-after-review-findings.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and review

- Starting repository HEAD: `324f901`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Reviewers used GPT-6 Luna at medium effort: `security-reviewer`, `database-reviewer`, `reliability-reviewer`, `silent-failure-hunter`, and `architect`. Their current-turn reports found the listed issues; they ran no tests and modified no files.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.
- This is a documentation-only state reconciliation. No tests, checks, builds, CI, migrations, or runtime acceptance scenarios were run.

## Acceptance and next steps

- Phase 8 remains `NOT APPROVED`; current S2 source corrections are not runtime-proven.
- `functional-test-reviewer` owns the three focused regression cases; `e2e-runner` owns their permitted execution on the exact corrected head. Do not run policy-excluded process-kill, crash/resume, mutation, or timeout/restart scenarios.
- After focused results, relevant specialists must re-review the corrected source; GPT-PM owns the later exact-head gate.

## Attribution

Change: 0437
Executor: Codex
