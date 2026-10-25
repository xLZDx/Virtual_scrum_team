# 0197 — Map S4 ancestry outcome tests to functional category

## What changed

Registered five selectors from test-source commit `173a7f25966fdbd92a36e0705be6fa2b2537aae7` in the functional category: return code 0 is true, return code 1 is false, another exit code raises `ContractError`, the second timeout after one bounded retry raises `ContractError`, and `OSError` raises invocation `ContractError`. The functional category now contains 19 selectors. Its coverage explanation names the five ancestry outcomes. Top-level registry `source_head` and functional `source_head` now point to the committed test-source head `173a7f25966fdbd92a36e0705be6fa2b2537aae7`. Other category IDs and sources were preserved.

SHA-256 of the committed category-registry content prepared by this change: `37ec1a8009bae72f7fab7c933385cfaafe1395ea667b7d387a27faad4ad765db`. This hash is recorded as provenance in this change record; the registry schema does not add a parallel self-hash field.

## Why

The registry ancestry behavior was changed at source HEAD `7b8200c0180a904f048acb93b7d04201d2d8c58c` to distinguish a valid non-ancestor from indeterminate Git invocation results. AC-7 requires applicable valid/invalid/error behavior to have falsifying selectors; functional testing also needs to prove bounded retry and fail-closed invocation behavior. These tests use deterministic monkeypatches and do not depend on actual repository ancestry.

## Verification state

No tests were run before this mapping commit. The exact affected functional, integration, seeded-failure, API, and E2E selector sets will run only after all test and mapping edits are committed. Product source is unchanged by changes 0196 and 0197.

## Scope

Only the functional category mapping, its provenance/hash explanation, and linked governance/change documentation changed. API and seeded selector IDs were not edited. E2E remains PARTIAL; external v2 signer and sandbox remain NOT_RUN. The intentionally untracked `.codex-s4-final-review.patch` remains untouched.

Executor: Codex
