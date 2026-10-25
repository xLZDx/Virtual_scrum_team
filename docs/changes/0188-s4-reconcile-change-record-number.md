# Change 0188: Reconcile duplicate S4 change-record number

## What changed

- Renumbered the later functional/integration/seeded evidence record from 0186 to 0187 so the record sequence matches commit order and remains unique.
- Updated the document registry and evidence references in the decision and lesson logs.
- Preserved both original commits and their content history; no commit was rewritten.

## Why

- The ancestry source fix and its subsequent test-evidence commit independently used 0186. The duplicate identifier made the current audit trail ambiguous.

## Affected paths and contracts

- `docs/changes/0186-s4-mapped-denominator-pass.md` was moved to `docs/changes/0187-s4-mapped-denominator-pass.md`.
- `governance/DOCUMENT_REGISTRY.md`, `core/DECISION_LOG.md`, and `core/LESSONS_LOG.md` now point to the unique identifier.
- No product code or runtime acceptance changed.

## Verification state

- Documentation and references were reconciled by inspection; no tests or checks were run.
- The underlying 27-selector evidence remains at exact HEAD `97c39000331c96b0184b1fb18d9ac2ba65c5658d` as recorded in change 0187.

Executor: Codex
