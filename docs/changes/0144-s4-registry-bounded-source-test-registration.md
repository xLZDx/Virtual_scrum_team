# 0144 S4 register bounded-source registry regressions

## What changed

- Registered the two new bounded-source and parser-recursion selectors in the API category.
- Pinned top-level registry and API category `source_head` to test-source commit `ad6ddb075b2a9f2beefcf2595bd47c9bbcd1650a`.
- Updated the partial API coverage explanation to include these behaviors.

## Why

The committed registry resolves test IDs from source history. The source commit must precede the registry entry so provenance remains valid and the real loader can validate the exact added IDs.

## Affected contracts and paths

- `docs/qa/categories.json`: API selector denominator and provenance.
- `tests/qa/test_s4_registry_contracts.py`: source nodes registered here.

## Verification state

- Registration is committed; the focused registry module has not yet run on this head. Run it only after this commit, on the clean exact head, and record all outcomes.
- No product source changed.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for the QA registry trust boundary is not separately identified in canonical ownership records.
- Run the exact focused functional module and commit the detailed results with regenerated document registry.
