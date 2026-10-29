# Change 0559: Plan permitted final S2 selectors

## What changed

- Added `docs/sdlc/S2_FINAL_PERMITTED_SELECTOR_PLAN.md` with a static, explicit pytest node-ID candidate plan, mapped to original S2 epics/deferred items and TP coverage.
- Kept TP-29–TP-38 pending authorship and exact IDs; documented platform separation, fixture limits, prohibited selectors, runtime holds, and the final code-freeze/GO execution gate.

## Why

The original S2 acceptance denominator remains E1–E8 plus D1–D2. A final run must select permitted tests by exact node ID and avoid modules that also contain restricted process, crash, recovery, E8 or policy cases. Historical counts belong to their recorded heads and cannot be added across revisions.

## Evidence and boundaries

Planning-only. Consulted public project docs and explicit selector records, including `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`, `docs/sdlc/S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md`, `docs/sdlc/test-plan.md`, and the public 4c1692d exact-head selector evidence. Did not read protected `docs/sdlc/evidence/s2-functional-test-run.md` or private raw Git evidence. Existing TP-29–TP-38 test code is not authored by this change and exact node IDs do not yet exist.

No tests, collection, checks, builds, CI, AST/import scripts, runtime commands, provisioning, migration, service activation, or production dispatch were performed. Candidate node count and current collection are `NOT_VERIFIED`. The working tree had concurrent source and documentation changes before this edit; this change owns only the two named documents and does not claim those concurrent edits.

## Acceptance state and next actions

| Item | State / evidence | Remaining acceptance | Owner / next action |
|---|---|---|---|
| Static permitted-selector plan | Implemented in `docs/sdlc/S2_FINAL_PERMITTED_SELECTOR_PLAN.md`; no runtime verification | Test owner must revalidate literal IDs against frozen source and parameters | Codex: after all S2 coding, declare final freeze and issue explicit test GO |
| TP-29–TP-38 | Coverage planned in `docs/sdlc/test-plan.md`; test code and IDs pending | Author and map exact fixture tests; no fake node IDs | Functional-test-reviewer: author after GO, then provide exact node IDs |
| Restricted/process/runtime scope | Explicit NOT_RUN/HOLD boundaries documented | Any permitted runtime evidence and final carried-scope decision | Operator: provide genuine human E5/host authorization where required; GPT-PM: adjudicate exact final package and residuals |

## Ordered next steps

1. Codex completes all S2 source coding and freezes the delivery tree; consequence: before this point no test selectors may execute.
2. Root issues explicit GO; functional-test-reviewer authors TP-29–TP-38 and validates IDs/parameter groups; consequence: fixtures remain source-level evidence only.
3. e2e-runner executes only the final authorized allowlist on the stated platforms and records exact results; consequence: restricted selectors stay NOT_RUN and skips stay unverified.
4. Codex reconciles original E1–E8/D1–D2 denominator and current S2 stories; GPT-PM adjudicates exact final package. Operator supplies any genuinely reserved human/runtime attestation; assignment of an owner is not evidence of completion.
