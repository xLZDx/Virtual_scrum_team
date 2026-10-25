# Change 0228: Reconcile S4 attribution footer omissions

## What changed

- Recorded that commits `27b0bd7` and `a478d6e` omitted the required `Executor: Codex` footer.
- Added this explicit reconciliation record and corresponding decision/lesson entries.
- Regenerated the document registry; no earlier commit was rewritten.

## Why

The S4 lesson log requires the project attribution footer and explicitly directs the coordinator to preserve history and reconcile any omission in a later commit. The omission was observable in the full messages from `git log -3 --format="%h %s%n%b"`.

## Affected contracts and paths

- Commit-message attribution convention.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and `governance/DOCUMENT_REGISTRY.md`.
- Commits `27b0bd7` (change 0225) and `a478d6e` (change 0227).

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 302 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Full exact commit message will be verified after the reconciliation commit; the original history remains intact.
