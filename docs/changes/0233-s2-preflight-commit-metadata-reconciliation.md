# Change 0233: Reconcile S2 preflight commit metadata

## What changed

- Recorded that five observed S2 preflight commits contain change-record files but omit their links from the commit messages and omit the required `Executor: Codex` footer.
- Added the decision/lesson entries and this explicit reconciliation record.
- Regenerated the document registry. No original commit was rewritten.

## Why

A bounded audit of the latest fifteen S2 commits compared complete commit messages to changed `docs/changes/` paths and the attribution rule. It found the described gaps. Available evidence does not establish the original commit authors/executors or why the messages were incomplete, so no attribution is inferred.

## Affected contracts and paths

- Commit-message change-record link and attribution convention.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`.
- Commits `7acb30d`, `f1eef32`, `2785528`, `deed6ab`, `6ee97cb` and their existing detailed change records.

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 194 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Full exact reconciliation commit message will be verified after commit. Existing history remains unchanged.
