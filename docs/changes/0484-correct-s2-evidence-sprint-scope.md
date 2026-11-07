# Change 0484: Keep S2 evidence scoped to the active sprint

## What changed

- Corrected the S2 controlled-selector evidence to clarify that the separate 53-selector policy
  family belongs to S4 and was not part of this S2 execution.
- Recorded that no S4 tests or other S4 work were performed in this continuation.

## Why

The project is being handled one sprint at a time. The S2 test evidence mentioned a 53-selector
policy family without stating that it belongs to S4, which could incorrectly imply that S4 work was
part of the active S2 test phase. This correction preserves sprint sequencing and keeps S2 and S4
acceptance denominators separate.

## Affected paths

- `docs/sdlc/evidence/s2-controlled-runtime-selectors-20261028.md`
- `docs/sdlc/STATE.md`
- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Reconciled the referenced 53-selector statements against current project records; they are S4
  acceptance records, not S2 selectors.
- No tests or checks were run for this documentation correction.
- No S4 source, test, state, or acceptance record was changed.

## Commit attribution

Executor: Codex
