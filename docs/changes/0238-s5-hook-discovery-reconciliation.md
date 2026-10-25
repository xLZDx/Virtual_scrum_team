# Change 0238: Reconcile S5 Git hook-path overrides

## What changed

- Recorded explicit `core.hooksPath=NUL` overrides in commits `8a0b426`, `6bd6a4e`, and `0a18a22`.
- Added decision/lesson entries and regenerated the document registry.
- Preserved existing history; no source or test files changed.

## Why

The active task prohibits bypassing Git hooks. A read-only inspection found no configured hook path and only `.sample` files, but `NUL` still explicitly suppressed hook discovery and should not have been set.

## Affected contracts and paths

- Git hook discovery and commit workflow.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`.
- Commits `8a0b426`, `6bd6a4e`, and `0a18a22`.

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 207 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Reconciliation commit uses ordinary `git commit` and retains hook discovery.
