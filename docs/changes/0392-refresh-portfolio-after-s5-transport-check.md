# Change 0392: refresh portfolio after S5 transport check

## What changed

- Updated `core/STATE.md` and related logs to include the S5 AEVE router result `NOT_COVERED: AEVE_PROFILE_TRANSPORT_UNAVAILABLE`.
- Refreshed the document registry from the staged Markdown index.

## Why

The portfolio checkpoint needed to include the latest bounded S5 transport investigation and current verified repository baseline.

## Affected paths

- `core/STATE.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Baseline branch `s4-canonical-continuation`, HEAD `9a0767bcf6dbb431797c603777b22386f6ff09db`, 237 commits ahead of `origin/main`.
- The only untracked path is the pre-existing `docs/sdlc/evidence/s2-functional-test-run.md`; it was not changed or staged.
- No source/test code or sprint worktrees were changed or created; no tests/checks/builds ran.
- No push, PR, merge, or external repository inspection occurred.

## Decision

Keep S5 blocked until AEVE transport or a specifically authorized source is available and S2/S4 prerequisites are met. Do not infer acceptance from a fresh documentation HEAD.
