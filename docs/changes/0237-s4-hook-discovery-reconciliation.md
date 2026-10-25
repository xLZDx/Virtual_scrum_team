# Change 0237: Reconcile S4 Git hook-path overrides

## What changed

- Recorded explicit `core.hooksPath=NUL` overrides in commits `27b0bd7`, `a478d6e`, and `31f797a`.
- Added decision/lesson entries and regenerated the document registry.
- Preserved existing history and the pre-existing untracked `.codex-s4-final-review.patch`.

## Why

The active task prohibits bypassing Git hooks. A read-only inspection found no configured hook path and only `.sample` files, but `NUL` still explicitly suppressed discovery and should not have been set.

## Affected contracts and paths

- Git hook discovery and commit workflow.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`.
- Commits `27b0bd7`, `a478d6e`, and `31f797a`.

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 303 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Reconciliation commit uses ordinary `git commit` and retains hook discovery.
