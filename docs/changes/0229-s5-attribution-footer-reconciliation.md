# Change 0229: Reconcile S5 attribution footer omission

## What changed

- Recorded that commit `8a0b426` omitted the required `Executor: Codex` footer.
- Added this explicit reconciliation record and corresponding decision/lesson entries.
- Regenerated the document registry; the earlier commit was not rewritten.

## Why

The project attribution convention requires a terminal executor footer. The omission is observable in the full commit message. The history remains intact while this follow-up records and corrects the process gap.

## Affected contracts and paths

- Commit-message attribution convention.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and `governance/DOCUMENT_REGISTRY.md`.
- Commit `8a0b426` (change 0226).

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 205 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Full exact commit message will be verified after the reconciliation commit; the original history remains intact.
