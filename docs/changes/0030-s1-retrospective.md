# 0030 S1 retrospective

## What
Adds `docs/sdlc/S1_RETROSPECTIVE.md`: timeline and counts of the S1 commits, four review rounds with findings and test counts, grouped root causes, what worked, an S2 process checklist and a metrics table. Numbers are labelled MEASURED or INFERRED.

## Why
The S1 lessons are spread over `core/LESSONS_LOG.md`, `core/DECISION_LOG.md` and ten evidence files. One document is needed as input for S2 planning.

## Paths
- `docs/sdlc/S1_RETROSPECTIVE.md` (new)
- `docs/changes/0030-s1-retrospective.md` (new)

No product code, tests, logs or state files changed.

## Verification
Documentation only. No tests were run. Counts were read from git (log, show --stat, rev-list) and from `docs/sdlc/evidence/*.md`; reviewer findings are quoted from the logs as reviewer claims.
