# Change 0329 — Record the missed lesson entry for change 0328

## What changed

- Added the missing lesson-log entry for commit `965c475` / change 0328.
- Added a decision-log follow-up pointing to this correction.
- Regenerated the document registry from the staged index.

## Why

The original task requires a lesson entry for each commit. The preceding documentation commit had its change record and decision log but omitted the lesson entry. Preserve commit history and record the process gap transparently.

## Evidence and verification

- Audited commit: `965c475` (`docs: record PM Bridge and wheelhouse evidence (0328)`).
- Corrective lesson: `core/LESSONS_LOG.md`, 2026-10-26 entry referencing change 0328.
- Documentation-only correction. No code changed; no tests, checks, builds, or migrations were run.

## Remaining acceptance and owner

- This correction closes the missing per-commit lesson-record item for 0328.
- The S2/S3/S4/S5 acceptance blockers remain as listed in `core/STATE.md` and `core/BACKLOG.md`.
- Codex owns following the full per-commit artifact checklist for subsequent commits. No push, PR, merge, or external environment change is authorized by this record.

Change: 0329  
Executor: Codex
