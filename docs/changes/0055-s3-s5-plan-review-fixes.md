# 0055 S3-S5 plan review fixes

## What changed

- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: clarified that every test ID has one `primary_category`; the regression suite is a separate aggregate manifest referencing functional, integration, API, and E2E IDs without assigning a second primary category. Updated the regression denominator language.
- `docs/S5_AEVE_GATE_PLAN_2026-10-24.md`: limited mandatory AEVE rule IDs to rules linked to committed seeded-defect evidence, as required by blueprint section 13.3. The S4 seeded-failure catalog is an explicit S5 prerequisite; optional analyzer rules cannot silently enlarge the required denominator.
- `core/DECISION_LOG.md` and `core/LESSONS_LOG.md`: recorded the decision, evidence, and rule for future planning.
- `docs/S2_SANDBOX_PROVISIONING_GUIDE.md`: reviewed the cited trust-root item; current step 5 already enumerates worker, supervisor, operator, event, reviewer, and runner-signer roots, so no correction was necessary.

## Why

The S4 plan required one category per test ID but also treated regression as the union of IDs from other categories. The S5 plan required every manifest rule even though blueprint section 13.3 makes AEVE mandatory only for rule IDs with seeded-defect evidence. These clarifications preserve explicit, non-overlapping test classification and make S5's acceptance denominator traceable to evidence.

## Verification state

This is a documentation-only change. No tests, checks, builds, CI, migrations, or runtime probes were run. The document registry is regenerated as a documentation artifact.

## Ownership and next action

- Accountable task owner: operator. Executor: Codex.
- Technical service owner for the future S4/S5 implementation: UNKNOWN in current canonical records.
- Next: at S4 start, commit the test-ID catalog and regression aggregate; before S5 implementation, derive and commit the required rule-to-seeded-fixture mapping from the accepted S4 catalog.

Agent-Attribution: Codex executor
