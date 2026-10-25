# Change 0195: Distinguish ancestry failures from verification errors

## What changed

- `_git_commit_is_ancestor` returns `True` for Git exit status 0 and `False` only for status 1, which means the revision is not an ancestor.
- Git statuses above 1 now raise `ContractError` with the status, instead of being reported as stale/out-of-scope provenance.
- Retry exhaustion and `OSError` now raise `ContractError` with clear verification/invocation diagnostics. The existing bound remains two attempts maximum at five seconds each.

## Why

The ancestry helper previously collapsed timeout, invocation errors, Git fatal errors, and a genuine non-ancestor result into `False`. `load_registry` then reported all such failures as missing, stale, or outside candidate history. This change preserves fail-closed behavior while distinguishing inability to verify from a proven non-ancestor result.

## Affected contracts and paths

- `tools/qa/registry.py`: ancestry result classification and diagnostics.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`: record the fail-closed diagnostic contract.
- `governance/DOCUMENT_REGISTRY.md`: regenerated document index.

## Decisions and ownership

- Only exit code 1 is interpreted as a valid negative ancestry answer; all other nonzero codes are verification failures.
- Accountable task owner: operator under delegated S4 continuation; executor: Codex. The technical service owner is not established in the inspected project records.

## Verification state

- Implemented; no tests, checks, builds, CI, migrations, or runtime probes were run as instructed.
- Functional-test-reviewer should exercise return codes 0, 1, greater than 1, timeout exhaustion, and invocation error, plus the committed registry load contract.

## Provenance

Implemented by Codex from the bounded diagnostic requirement assigned at base HEAD `713065dfd10c8a04587e571f9be889bccc09fe67`.
