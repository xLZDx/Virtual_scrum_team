# Change 0389: S3 static candidate comparison

## What changed

- Added a bounded static comparison of the hand-written worker, BMad Loop, and pinned Temporal candidate using existing in-repository evidence.
- Updated the S3 plan, backlog, and current state to distinguish this comparison from the required same-fixture runtime experiment.

## Why

The S3 task requires candidate comparison, while S2, legal/provenance, and acquisition gates still prevent the shared runtime fixture. A source/evidence matrix is independently useful if it does not claim a winner or runtime result.

## Affected paths

- `docs/sdlc/evidence/s3-static-candidate-comparison-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `core/STATE.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Comparison rows cite the recorded immutable pins and in-repository S2/S3 evidence.
- No candidate source or artifact was acquired, built, installed, or executed.
- Same-fixture runtime comparison remains `NOT_RUN`; prohibited process-kill, crash, and mutation scenarios remain `NOT_RUN`.

## Decision

Do not name a final winner or `TOP` candidate from static evidence. Keep Temporal as the provisional audit comparator only; wait for accepted prerequisites before the authorized runtime comparison.
