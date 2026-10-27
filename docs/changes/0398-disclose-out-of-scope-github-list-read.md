# Change 0398: disclose out-of-scope GitHub repository-list read

## What changed

- Recorded an accidental read-only call to the GitHub connector's repository-list tool while working on the in-scope S3 review.
- Stopped the cross-project branch immediately; no result was used as project evidence and no further repository-listing action was taken.

## Why

The active scope permits inspection of `D:\Repo\Virtual_scrum_team` and its named evidence sources only. Reading the user's general GitHub repository list crossed that boundary.

## Affected paths

- `docs/changes/0398-disclose-out-of-scope-github-list-read.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Tool invoked: `mcp__codex_apps__github_list_repositories({})`, read-only.
- The connector returned repository metadata; the calling code displayed only a bounded 1,000-character prefix. No repository content was opened, no remote state was changed, and no returned metadata was used for S2–S5 decisions.
- No further GitHub connector call was made after noticing the scope error.

## Decision

Do not use the repository listing or inspect any unrelated repository. Continue only with the canonical local project and explicitly named evidence sources.
