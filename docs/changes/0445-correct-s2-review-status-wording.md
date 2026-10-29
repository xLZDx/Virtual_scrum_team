# Change 0445: correct S2 review-status wording

## What changed

- Corrected the active S2 status paragraph to distinguish the prior GPT-PM-reviewed full candidate from the newer exact-head focused regressions and specialist reviews.
- Removed the stale statement that current source fixes were awaiting all specialist re-reviews.

## Why

Change 0444 recorded five fresh specialist reviews at exact source/test HEAD `79155fd`, but one adjacent status sentence still said those reviews were pending. The wording also conflated a prior full-candidate gate with the newer focused regression head.

## Affected paths

- `docs/sdlc/STATE.md`
- `docs/changes/0445-correct-s2-review-status-wording.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- New exact test evidence is linked in `docs/sdlc/evidence/s2-vst017-constructor-failure-run-79155fd-20261027.md` and specialist evidence in `docs/sdlc/evidence/s2-final-specialist-review-79155fd-20261027.md`.
- This wording correction does not change S2 acceptance state: Phase 8 remains NOT APPROVED pending system evidence.
- No tests/checks/build/CI/migration were run.

## Ordered next steps and owners

1. Codex: maintain exact-head separation between full S2 evidence and targeted regression evidence.
2. Codex: continue permitted S2 system evidence; keep restricted scenarios `NOT_RUN`.
3. GPT-PM: review the exact final S2 head only when required acceptance evidence is complete.

## Attribution

Change: 0445
Executor: Codex
