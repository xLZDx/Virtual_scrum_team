# Change 0450: reconcile S2 exact-head selector counts

## What changed

- Updated S2 phase state to report four regression selectors at `dc1741b` and three bounded-Git selectors at `79155fd`.
- Corrected the Phase 8 summary from five to seven selector executions across the two exact source/test revisions.
- Fixed the linked evidence list for current-head bounded-Git regressions.

## Why

Change 0449 added two successful exact-head reruns after the constructor-failure regression had already passed at `79155fd`. The phase table and latest-review paragraph still reflected the earlier four-plus-one count.

## Affected paths

- `docs/sdlc/STATE.md`
- `docs/changes/0450-reconcile-s2-exact-head-selector-counts.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Four selectors at `dc1741b`: evidence `s2-review-regression-dc1741b-20261027.md`.
- Three bounded-Git selectors at `79155fd`: constructor run and reader reruns in `s2-vst017-constructor-failure-run-79155fd-20261027.md` and `s2-vst017-reader-reruns-79155fd-20261027.md`.
- This is a documentation correction; it does not change S2 acceptance. Phase 8 remains NOT APPROVED pending system acceptance.
- No tests/checks/build/CI/migrations were run.

## Ordered next steps and owners

1. Codex: preserve evidence at its exact source/test revision; do not merge results across heads.
2. Operator: owns any policy changes or actual platform/deployment attestations.
3. GPT-PM: adjudicates the exact final S2 head only after system acceptance is complete.

## Attribution

Change: 0450
Executor: Codex
