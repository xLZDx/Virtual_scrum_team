# Change 0407: reconcile S3 phase state with the accepted G03 design

## What changed

- Reconciled the S3 section of `docs/sdlc/STATE.md` with GPT-PM's correlated exact-head acceptance recorded in change 0406.
- Distinguished accepted G03/G07 design findings from still-open implementation, exact-pair runtime, provenance, legal/acquisition, S2/S4, and candidate-comparison gates.
- Updated the latest continuation note to identify the reviewed design revision and the follow-up record without claiming current runtime acceptance.

## Why

The S3 phase summary still said the G03 review returned `MODIFY` and that the cancellation amendment was unapproved, which contradicted the later correlated GPT-PM `ACCEPT` at design level. The phase record must reflect the accepted design while preserving all runtime and acquisition boundaries.

## Affected paths

- `docs/sdlc/STATE.md`
- `governance/DOCUMENT_REGISTRY.md` (generated from staged index)
- `docs/changes/0407-reconcile-s3-phase-state.md`

## Provenance and review

- Starting HEAD: `13382bed1fbf4ab174947cb48a380476799d1246`, branch `s4-canonical-continuation`.
- Source decision is correlated in request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245`, PM Bridge job `cc0802b8-7662-47b8-95ba-88613d58be83`, user turn `8de9ea84-35b0-45fe-8eb0-87cc0bb182c0`, and reply `14aedf85-c52b-5d64-b84b-40baf9a99455`; durable metadata reports `succeeded`, `correlated=true`. GPT-PM accepted only the change 0405 design at its exact reviewed HEAD, not implementation or runtime.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not read, staged, or modified.
- No source code, tests, build, CI, migration, acquisition, installation, candidate execution, network probe, push, PR, or merge occurred. No sprint worktree/fork was created.

## Verification and acceptance

- Regenerate the document registry from the staged index, then run its `--check`.
- No HTML content changed; run the mandated report-format check only.
- Preserve S2 `NOT APPROVED`, S4 `INCONCLUSIVE` / 53 selectors `NOT_RUN`, and S5 gating.

## Ordered next steps and owners

1. Codex: commit this phase-state reconciliation with its linked change record.
2. Codex: continue only permitted S2 host evidence and read-only S3 source audit; do not run prohibited scenarios or acquire candidate material.
3. GPT-PM: design adjudication for G03/G07 change 0405 is complete; any final exact-head delivery gate remains future work.
4. Operator: retain legal/acquisition and any reserved production/merge decision; these are not resolved by design review.
