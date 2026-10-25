# Change 0164: Correct S4 WSL runtime status in design records

## What changed

- Updated the S4 technical design and plan to distinguish the executed fresh source transfer and mapped POSIX E2E selectors from the still-unrun report-bound signer path.
- Recorded the exact WSL run ID and source HEAD already captured in change 0159.

## Why

The design and plan retained earlier `NOT_RUN` statements after run 0159 had established the fresh transfer, worker read-only boundary, and seven mapped POSIX selector results. Those statements could be read as contradicting the bilingual S4 status report. The correction preserves the remaining signer/report boundary as open.

## Affected paths and acceptance

- `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- S4 AC-2, AC-9, AC-10, and AC-14 evidence interpretation.

## Verification state

- Documentation reconciled to recorded change 0159 and current bilingual report.
- This change adds no product code and claims no new test/runtime evidence.
- `report_conform.py --check` exited 0 (`all reports carry the mandated block`); `tools/build_document_registry.py --check` exited 0 (`DOCUMENT_REGISTRY.md is current`).

## Ownership and next step

- Accountable task owner: operator (delegated S4 continuation).
- Executor: Codex.
- Next: run the report-conformance and registry freshness checks, then commit this correction before the final exact-head review request.
