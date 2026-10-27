# Change 0409: reconcile the latest S3–S5 state note

## What changed

- Updated the top-level continuation note in `docs/sdlc/STATE.md` to acknowledge changes 0407 and 0408 instead of presenting change 0406 as the latest reconciliation.
- Restated the current S3 design-only acceptance and the still-open runtime, provenance, legal/acquisition, S2/S4, candidate-comparison, and S5 prerequisites.
- Preserved S4 `INCONCLUSIVE`, the 53 policy selectors as `NOT_RUN`, and the protected untracked S2 evidence file.

## Why

The top of the phase record lagged the current commit history. That made the accepted S3 design and later VST-028 wording correction difficult to reconcile with the present sprint status. This is a documentation synchronization only; it does not change evidence or acceptance.

## Affected paths

- `docs/sdlc/STATE.md`
- `governance/DOCUMENT_REGISTRY.md` (generated from the staged index)
- `docs/changes/0409-reconcile-latest-s3-s5-state.md`
- `core/DECISION_LOG.md`

## Provenance and review

- Starting HEAD: `ba15e78f141770cdb8b58625f6305fec829a250d`, branch `s4-canonical-continuation`.
- Changes 0407 and 0408 are already present in local Git history; this record makes no claim to have authored them.
- GPT-PM's design-only decision remains correlated to request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245` / reply `14aedf85-c52b-5d64-b84b-40baf9a99455`.
- The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and unstaged.
- Only read-only source-page browsing was used to recheck the exact pinned dependency page. No runtime network probe, source download, source code change, test, build, CI, migration, acquisition, installation, candidate execution, push, PR, merge, or sprint-specific worktree/fork occurred.

## Verification and acceptance

- Regenerate the document registry from the staged index.
- No HTML report changed. No project tests/checks were run.
- S2 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE` with 53 policy selectors `NOT_RUN`; S5 remains gated.

## Ordered next steps and owners

1. Codex: commit this phase-state synchronization with its linked change record.
2. Codex: continue only permitted read-only evidence work; preserve all prohibited scenarios as `NOT_RUN`.
3. Operator: provide an exact S4 waiver or maintain `INCONCLUSIVE`; decide the S3 legal/acquisition disposition and identify/authorize an in-scope AEVE source when its gates are met.
4. GPT-PM: adjudicate any changed architecture and the exact final head after acceptance; the prior G03/G07 decision is design-only.
