# Change 0155: Bound registry source indexing

## What changed

`tools/qa/registry.py` now stores compact sets of valid pytest node names instead of retaining parsed AST modules. One registry load is limited to 2,048 test IDs and 4 MiB of aggregate source bytes across unique source paths. The existing 1 MiB per-file read limit, per-load cache, path canonicalization, symlink checks, and tests-root containment checks remain in force. Exceeding the aggregate source budget rejects the registry with a specific `ContractError`.

## Why

Fresh code, security, and reliability reviews at `e52ec7f63fa7285ad0bb3910e8bfd31a9707f31e` independently found that a registry could reference many distinct test files, causing each file to be parsed and its full AST retained even though individual files and the registry were byte-capped. Compact indexes reduce retained state; the aggregate source-byte and ID ceilings bound parse work and index growth.

## Contracts and decisions

- Cache lifetime remains one registry validation; no parsed state is retained between runs.
- Every ID still revalidates canonical path, symlink components, and resolved containment before using a cached index.
- Direct private-helper calls that provide the prior plain-dictionary cache shape remain compatible; full aggregate budgeting is owned by `load_registry`'s typed per-load cache.
- The AST is temporary during each source parse; only top-level test functions and valid `Test*` class methods are retained.
- Test-ID or aggregate-source budget excess is fail-closed.
- No tests, checks, or builds were run during coding. Designated functional coverage and fresh review are pending.

## Affected paths

- `tools/qa/registry.py`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

Implemented; not runtime-verified. Required acceptance includes preserving direct and class-method node resolution, one parse per shared source, rejecting aggregate-source overflow, enforcing the ID limit, and retaining path/provenance fail-closed behavior.

## Provenance

Implemented by the GPT-6 Luna implementation agent in response to the independent reviews at the base HEAD above. The commit containing this record identifies the resulting source revision.
