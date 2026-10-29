# Change 0444: record final S2 source reviews and durability follow-up

## What changed

- Added five fresh exact-source specialist review outcomes at `79155fd`.
- Reconciled S2 state and backlog to show no code BLOCKER/MAJOR and one nonblocking database durability MINOR.
- Linked the new review evidence and retained the open system acceptance and policy exclusions.

## Why

S2 source/test corrections and their focused regression evidence require current-head specialist review before describing the code findings as closed. The database review also identified a bounded availability limitation for first-time anchor creation that must remain visible without overstating it as an integrity bypass.

## Affected paths

- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `docs/sdlc/evidence/s2-final-specialist-review-79155fd-20261027.md`
- `docs/changes/0444-record-s2-final-specialist-reviews.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)

## Provenance and verification

- Review target source/test HEAD: `79155fdf9f1f4a7ba71358592ccd54c669a76291`.
- Reliability, architecture, silent-failure and security reviewers reported no actionable code BLOCKER/MAJOR.
- Database reviewer reported no transaction/locking/checkpoint integrity BLOCKER/MAJOR and one MINOR: initial anchor-file creation does not fsync the containing directory; possible power-loss directory-entry loss would cause fail-closed unavailability for nonempty data.
- The reviews were read-only and ran no tests/checks. Four prior selectors passed at `dc1741b`; the constructor-failure selector passed at `79155fd`, as recorded in changes 0439 and 0442.
- Phase 8 remains NOT APPROVED. System acceptance and restricted scenarios are still open/NOT_RUN. No push/PR/merge is authorized by these reviews.

## Ordered next steps and owners

1. Codex: keep the initial-directory-fsync item visible as a nonblocking durability follow-up; only implement if required by the S2 durability contract.
2. Codex: continue permitted S2 system evidence; maintain `NOT_RUN` for process-kill, crash/resume, mutation, timeout/restart, and policy-restricted selectors.
3. Operator: owns any change to the explicit selector restrictions and required production/environment attestations.
4. GPT-PM: adjudicates the exact final S2 head only after mandatory acceptance evidence is complete.

## Attribution

Change: 0444
Executor: Codex
