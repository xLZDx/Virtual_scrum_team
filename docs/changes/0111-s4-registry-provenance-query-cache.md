# 0111 S4 registry provenance and Git-query cache

## What changed

- Cached tracked-file, commit-existence, and ancestry results once per unique value during one `load_registry` call to avoid repeating equivalent Git subprocess queries for each test ID/category.
- Reconciled the top-level and supported-category source heads to the in-scope committed test-source head that contains every declared node.
- Added the committed-registry loader regression to the API denominator and kept all category coverage explicitly partial where required journeys remain absent.
- Renumbered the functional loader regression detail record to 0109 because E2E already used 0107; history is preserved.

## Why

The first real-registry loader regression encountered a tracked-file false negative while identical Git lookups were repeated for many test IDs. The worktree command confirmed the source was tracked; the helper converts subprocess timeouts to `False`, so repeated lookups could turn temporary contention into a misleading missing-file rejection. Per-call caching keeps fail-closed behavior while eliminating redundant queries.

## Affected contracts and paths

- `tools/qa/registry.py`: per-load cache for Git provenance and tracked source checks; source-level pytest-node resolution remains the authoritative selector check.
- `docs/qa/categories.json`: exact candidate-ancestor provenance plus final committed loader API ID.
- `docs/changes/0109-s4-committed-registry-loader-regression.md`: unique detail-record numbering.
- S4 plan, backlog, decision/lessons logs and generated document registry: current partial test and runtime state.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- `source_head` points to `4913425c9327b2416ac7cc1e421268223ee43ae1`, an in-scope S4 ancestor containing all declared test-node definitions. It is not the separate S3 test-run commit `58088c8`, which is not an ancestor of the S4 candidate.
- Git query errors and timeouts still fail closed. A successful result is cached only for the current registry load; later calls observe later repository state.
- Functional and E2E tests remain owned by the respective test agents; no source test is executed by Codex.

## Verification state

- The functional-test-reviewer reported 9 passed on a dirty working tree at HEAD `666d6e3d3063c8cf5323088f58cd94d01db03d7f` after the cache/provenance edits. This is provisional evidence, not an exact committed-tree pass.
- E2E-owned local cases passed 2/2 on their committed test revisions; full S4 exact-head acceptance is pending a clean rerun after this commit.
- No tests, checks, builds, CI, migrations, or WSL transfer were run by Codex.
- Native source transfer, signer/report/gate integration, and the isolated WSL identity/root remain `NOT_RUN`/`NOT_VERIFIED`.

## Follow-up

1. Functional-test-reviewer reruns the full 9-case registry suite on this clean exact committed head and retains its evidence.
2. E2E-runner reruns the local E2E module on the same final candidate; then reconcile all S4 mapped tests and specialist reviews.
3. Obtain and record the exact private S4 runner account, worker group, snapshot root and signer socket before attempting native WSL execution.
