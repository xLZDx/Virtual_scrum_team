# Change 0160: Record mapped functional and integration results

## What changed

- Ran exactly the eight functional IDs and one integration ID listed in the S4 QA registry at a clean exact HEAD.
- Recorded category-separated commands, results, environment, and limitations in `docs/sdlc/evidence/s4-functional-integration-mapped-views-b741dc2.md`.
- Updated the S4 backlog, decision log, lessons log, and generated document registry.

## Why

These are the remaining currently mapped primary-category selectors without a rerun at the current code HEAD. Their owner role is `functional-test-reviewer`; they are distinct from the seven mapped E2E selectors and from S4 registry module evidence.

## Affected paths

- `docs/sdlc/evidence/s4-functional-integration-mapped-views-b741dc2.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

At clean exact code HEAD `b741dc205a111e56bb984c59a63af2801870e4fc`, Windows/Python 3.14.3/pytest 8.4.2: functional category 8 passed; integration category 1 passed; no skips or failures. One pytest-asyncio deprecation warning per command. See linked evidence for exact commands.

## Provenance

Test owner: functional-test-reviewer (GPT-6 Luna, medium). No product source was changed in this evidence commit.
