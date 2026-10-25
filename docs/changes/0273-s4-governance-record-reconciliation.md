# 0273 S4 governance record reconciliation

**Date:** 2026-10-25  
**Executor:** Codex  
**Baseline HEAD:** `a41810f6a5dfb47065955f4e280ed58f74f06a5e`

## What changed

- Added decision-log records for changes 0271 (exact-head QA evidence) and 0272 (the POSIX runtime-matrix design).
- Added a lesson documenting the missed workflow requirements found while re-reading the user's named S2–S5 task attachment.
- Regenerated the generated `governance/DOCUMENT_REGISTRY.md` after the Markdown changes.
- Preserved commits 0271 and 0272; no history rewrite was performed.

## Why

The original S2–S5 attachment requires a dated `core/DECISION_LOG.md` entry in every decision/evidence commit, a matching lesson entry, a terminal `Executor: Codex` commit-message attribution footer, and regeneration of the document registry when Markdown changes. Commits 0271 and 0272 were made before that attachment's full text was re-read, so both lack decision-log entries and the required footer. This follow-up records their evidence/design decisions and corrects the process without rewriting shared history.

## Verification state

- The current checkout and staged paths were inspected before this reconciliation; the untracked `docs/sdlc/evidence/s2-functional-test-run.md` is preserved and excluded.
- Command to regenerate the registry: `C:\Python314\python.exe tools/build_document_registry.py`. This is document generation, not a test or check.
- No product tests, checks, builds, CI, migrations, push, PR, or merge were run for this record.
- Future commit messages must include the change-record path and end with the exact line `Executor: Codex`.
