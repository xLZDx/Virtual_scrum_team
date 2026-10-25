# 0145 S4 bounded registry source regression evidence

## What changed

- Recorded two exact-head runs of the focused S4 registry module after adding 1 MiB source-bound and `RecursionError` cases.
- Preserved the repeated committed-registry loader failure and direct Git-object existence checks; did not convert the partial pass count into a green acceptance claim.
- Recorded the Windows symlink skip, environment, command, exact revisions, test-to-criterion map, and warning in `docs/sdlc/evidence/s4-bounded-registry-source-64b8bb1.md`.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The two requested source-resolution behaviors are individually exercised and pass, but exact committed-registry acceptance still fails while resolving existing Git source-head objects. The evidence retains both runs and the limitation for implementation-owner follow-up.

## Affected contracts and paths

- `docs/sdlc/evidence/s4-bounded-registry-source-64b8bb1.md`: detailed execution evidence.
- `core/LESSONS_LOG.md`: bounded registry source lesson and current runtime status.
- `governance/DOCUMENT_REGISTRY.md`: generated inventory.

## Verification state

- Exact test HEAD `64b8bb1f2d847ce3ba33fafb1a75e7b2e81b71b7`.
- Each of two focused runs: 14 passed, 1 skipped, 1 failed. The failure is `test_s4_committed_registry_loads_with_resolved_nodes`, with loader rejection of a source-head commit that direct `git cat-file` verified exists.
- New bounded-source and recursion cases passed both times. Symlink runtime remains `NOT_RUN` because Windows denied link creation (WinError 1314).
- No product code changed in this test-owned commit. The specific cause inside `_git_commit_exists` remains unknown; its helper suppresses subprocess stderr and returns false for timeout or nonzero exit.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for the QA registry implementation is not separately identified in canonical ownership records.
- Implementation owner should investigate why the bounded Git commit-existence query reports existing objects as absent. After a product fix, rerun this focused module on the resulting clean committed HEAD. Do not claim full registry acceptance until it passes.
