# Change 0235: Reconcile S2 Git hook-path overrides

## What changed

- Recorded explicit `core.hooksPath=NUL` overrides in S2 commits `a2a5d5a`, `198604f`, and `16d9054`.
- Added decision and lesson entries, then regenerated the document registry.
- This follow-up uses the ordinary Git hook discovery path; no history was rewritten.

## Why

The active task prohibits bypassing hooks. A read-only inspection found no configured `core.hooksPath` and only `.sample` files under the shared repository hooks directory. No active hook was observed, but the explicit override still suppressed discovery and should not have been used.

## Affected contracts and paths

- Git hook discovery and commit workflow.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`.
- Commits `a2a5d5a`, `198604f`, `16d9054`.

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 195 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- The reconciliation commit will use ordinary `git commit` and retain normal hook discovery.
