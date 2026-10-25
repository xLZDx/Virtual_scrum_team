# Change record 0312: document registry follows the Git index

## What changed

- Updated `tools/build_document_registry.py` to enumerate Markdown documents from `git ls-files --cached`, so the generated registry describes documents included in the current or upcoming commit and ignores unrelated untracked files.
- Added a transparent follow-up to change 0311: its commit omitted the required lesson-log entry, generated registry refresh, and `Change` / `Executor` attribution lines.
- Added the omission, cause, and prevention rule to the decision and lessons logs. The earlier commit remains unchanged.

## Why

Change 0311 was committed before checking every commit artifact required by the original operator prompt. The audit also found a pre-existing untracked S2 evidence Markdown file that must remain untouched. Scanning the Git index keeps unrelated untracked user artifacts out of committed generated documentation while including newly staged documents.

## Contracts and paths

- `tools/build_document_registry.py`
- `governance/DOCUMENT_REGISTRY.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `docs/changes/0312-s4-document-registry-commit-scope-correction.md`

## Verification state

Registry generation is a documentation-generation command, not test or runtime evidence. The change 0311 omission is recorded as a process shortcoming. No test, check, build, or runtime command is claimed here.

## Ownership and next action

Operator is accountable for the delegated program; Codex is executor. Next: stage the exact documentation artifacts, regenerate the registry from that index, inspect the staged diff, and commit this follow-up without including unrelated untracked evidence.
