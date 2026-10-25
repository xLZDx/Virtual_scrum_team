# 0303 Restore required lesson entries for S4 changes 0301 and 0302

**Date:** 2026-10-25  
**Executor:** Codex

## What changed

Added the missing `core/LESSONS_LOG.md` entry for changes 0301 and 0302. Those commits carried their own change records and `core/DECISION_LOG.md` entries but omitted the separately required lesson record.

## Why

The source request requires every commit to update the decision log and lessons log, with the lesson recording the failure, root cause, catching layer and rule for next time. After re-reading the source request, the coordinator found that this requirement had not been included in the stage checklist for changes 0301 and 0302.

## Verification state

- Documentation-only correction; no tests or checks were run.
- This follow-up does not rewrite prior commits. It records the omission and correction in a new commit.

## Next

Include `core/LESSONS_LOG.md` as a required pre-commit path in every subsequent S2-S5 change. Keep the next focused S4 tests delegated to the designated functional-test reviewer at the exact registry HEAD.
