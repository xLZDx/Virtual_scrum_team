# 0182 — Add S4 seeded failure test cases

## What changed

Added `tests/qa/test_s4_seeded_failures.py` with six bounded test functions for unchanged-product failure behavior: stale candidate HEAD, missing required receipt, invalid signature, out-of-scope diff, skipped required ID, and artifact digest mismatch. Each function will load its own committed catalog input, verify the canonical input hash and exact test ID, assert the product outcome, then emit one plugin observation. Test IDs and input hashes are not yet added to the catalog/primary-category manifest in this source commit; that will be a separate mapping commit with updated provenance.

No product code changed. The tests use direct Python interfaces with temporary in-memory/local state; no network, production, mutation injection, or source monkeypatching is used.

## Why

S4.5.2 explicitly names these failure classes as examples for controlled seeded fixtures. AC-12 requires each catalog fixture to bind input hash, expected rejection, observed rejection, and one committed test ID. AC-13 excludes mutation-score claims.

## Verification state

No test was run. This source commit precedes the registry/catalog mapping commit; the focused functional, integration, and seeded sets will run only after all selectors and provenance are committed.

## Decision and remaining scope

The fixture inputs encode deterministic parameters passed to existing `tools.vst` APIs; each expected outcome is derived from the returned VST decision/reason or contract result before an observation is recorded. The catalog will retain the original `invalid-task-manifest` fixture and add exactly these six known classes. Report-bound signer/socket and authoritative gate runtime remain separate dependencies.

Executor: Codex
