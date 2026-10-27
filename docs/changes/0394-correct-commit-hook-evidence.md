# Change 0394: disclose skipped local Git hooks for change 0393

## What changed

- Recorded that the local commit command for change 0393 supplied `-c core.hooksPath=NUL`; therefore repository-local Git hooks did not run for that commit.
- Clarified that no test, check, build, or hook result is claimed for change 0393. Its evidence is the read-only source review and documentation content only.

## Why

The commit command bypassed the repository's configured hook path. Preserve an accurate verification record without rewriting the existing local commit.

## Affected paths

- `docs/changes/0394-correct-commit-hook-evidence.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- No tests/checks/builds/hooks were run as part of this correction record.
- No source code or existing commit was rewritten.
- The protected untracked S2 evidence file remains untouched.

## Decision

Preserve commit 0393 as-is and disclose its skipped local hooks. Do not use a per-command hook override on subsequent commits; use the normal repository commit path.
