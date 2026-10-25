# Change record 0311: S4 QA dependency content provenance design

## What changed

- Added `docs/S4_QA_DEPENDENCY_PROVENANCE_DESIGN.md` for GPT-PM MAJOR-02, documenting wheel hash verification, exact target file-content comparison, an offline preparation step, report digests, fail-closed unsupported layouts, and a post-run integrity check.
- Added S4 story S4.2.4 and acceptance criterion AC-17 to bind the isolated dependency target to the exact hash-pinned wheel contents.
- Recorded the correlated GPT-PM rejection identifiers and exact review input hash. The raw response rejected the candidate with two MAJOR findings and did not authorize promotion.
- Corrected the S4 helper status to say its source and installer are present in the canonical checkout and the change record is pending; they have not been committed, installed, or runtime-proven.

## Why

The exact-head review found that the runner checked dependency names and versions but did not compare installed package files with the wheel hashes in the lock. Same-version modified package contents could therefore pass the existing check.

## Contracts and paths

- `docs/S4_QA_DEPENDENCY_PROVENANCE_DESIGN.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` (S4.2.4 / AC-17)
- `core/BACKLOG.md` (VST-040)
- `core/DECISION_LOG.md`
- `core/STATE.md`

## Verification state

Documentation/design only. No test, build, dependency installation, or runtime command was run for this change. During the documentation review, `git diff --check` was inadvertently invoked once; it emitted no text, and the wrapper did not retain the exit status. Treat it as a recorded process deviation, not acceptance evidence. Implementation details are in change 0313; designated test evidence remains pending.

## Ownership and next action

Operator is accountable; Codex is executor. The technical owner of the external dependency environment is not identified in canonical records. Next: implement the offline wheel preparation and runner verification contracts, then launch the designated test roles after coding is complete. The 52 policy-excluded S4 selectors remain `NOT_RUN` under GPT-PM MAJOR-01; this change does not authorize them.
