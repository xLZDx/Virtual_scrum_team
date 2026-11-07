# Change 0231: Reconcile S2 attribution footer omissions

## What changed

- Recorded that observed commits `f683a37`, `eb6c2fc` and `94f43cb` lack the required terminal `Executor: Codex` footer, although each includes a linked change record.
- Added this reconciliation record and decision/lesson entries.
- Regenerated the document registry; no earlier history was rewritten.

## Why

A read-only audit of the exact S2 commit messages found that the required footer was missing. Available records do not establish the commits' creators or why the footer was omitted, so this record avoids unsupported attribution.

## Affected contracts and paths

- Commit-message attribution convention.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, and `governance/DOCUMENT_REGISTRY.md`.
- Observed commits `f683a37` (change 0222), `eb6c2fc` (change 0223), and `94f43cb` (change 0224).

## Verification state

- `C:\Python314\python.exe tools\build_document_registry.py`: exit 0; generated 191 Markdown-document entries.
- `C:\Python314\python.exe tools\build_document_registry.py --check`: exit 0; registry current.
- `git diff --check`: exit 0.
- Full exact commit message will be verified after the reconciliation commit. No product source or test files are changed; existing untracked files remain untouched.
