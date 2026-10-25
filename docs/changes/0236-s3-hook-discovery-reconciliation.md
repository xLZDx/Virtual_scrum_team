# Change 0236: Reconcile S3 Git hook-path override

## What changed

- Recorded explicit `core.hooksPath=NUL` in S3 commit `98f118b`.
- Added decision/lesson entries and regenerated the document registry.
- This reconciliation uses ordinary hook discovery; no history was rewritten.

## Why

The active task prohibits bypassing hooks. The shared hooks directory had no configured override and only `.sample` files at inspection, but the explicit `NUL` override still suppressed hook discovery.

## Affected contracts and paths

- Git hook discovery and commit workflow.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`.
- Commit `98f118b`.

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 210 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Reconciliation commit uses ordinary `git commit` and retains hook discovery.
