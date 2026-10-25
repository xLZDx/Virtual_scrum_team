# 0183 — Map S4 functional, integration, and seeded-failure selectors

## What changed

Extended `docs/qa/categories.json` with six AC-7 functional selectors and five local integration selectors. The functional category now has 14 unique primary IDs and is marked COMPLETE for the bounded local AC-7 contract described in its manifest reason. Integration now has six unique IDs and its selector denominator is COMPLETE; trusted signer OS identity and report-bound runner execution remain NOT_RUN as separate runtime evidence. The existing API and E2E ID lists were preserved.

Added six fixtures to `docs/qa/seeded_failures.json` for stale candidate HEAD, missing required receipt, invalid signature, out-of-scope diff, skipped required test ID, and artifact digest mismatch. Each fixture contains canonical JSON input, SHA-256 input hash, expected rejection code, and one unique selector in `tests/qa/test_s4_seeded_failures.py`. The seeded category now maps all seven declared fixtures (including the pre-existing invalid-manifest case), with COMPLETE scoped to that catalog rather than exhaustive failure coverage.

The six focused tests were already added in source commit `a73e87a3c4b414f0c97ac1d09fdedf037ec17dde`; this mapping commit imports the missing `EPOCH` test helper needed by the existing test module and binds the selectors to their committed catalog records. No product source changed.

## Why

S4 AC-7 requires valid and invalid inputs, stale evidence, and signature failures where applicable, with each required test ID represented once. AC-9 requires local integration seams with isolated temporary state and synthetic repositories. AC-12 requires each seeded fixture to bind its input hash, expected and observed rejection, and exactly one committed test ID; AC-13 disallows mutation-score claims. This mapping preserves category ownership and records unsupported signer/report runtime as NOT_RUN rather than inferring acceptance.

## Verification state

No test command was run before this mapping commit. Static preparation confirmed that the selected node names are present as named test functions in tracked source, all primary category IDs are unique, and the six fixture hashes are generated from canonical compact sorted JSON. Runtime execution and observed plugin records remain pending.

## Decision and remaining scope

Keep functional coverage COMPLETE only for the manifest's bounded local AC-7 set. Keep integration selector mapping COMPLETE for the six accepted local selectors; track trusted signer socket identity and report-bound runner runtime separately as NOT_RUN. Seeded coverage is COMPLETE only for the seven explicitly declared fixtures. API and E2E categories are unchanged.

Executor: Codex
