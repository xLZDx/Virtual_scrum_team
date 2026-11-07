# Change 0590 — Record exact-head S2-4 V2 source approval

Date: 2026-10-30
Owner: Codex
Task: S2-4 bounded source/test acceptance reconciliation

## Why

After source commit `aa3496322ca7b05955dd60dfee7decd8056f34ee` was created, GPT-PM reviewed its
exact code head. This documentation-only change records that correlated verdict in the backlog
and verification evidence so the delivered task state and its boundary remain visible.

## What changed

- Recorded GPT-PM request `b53d89ab-aca1-4432-87d3-5b139592f575`, job
  `5ab58c00-1f88-4e4e-b393-1d3cdff2f7d8`, correlated reply
  `0477831c-98fa-5e91-8416-5b5b4ff7cacd`, and exact reviewed code HEAD.
- Marked only the bounded S2-4 V2 source/test slice accepted; full S2-4 remains not accepted.
- Recorded the still-open V1 caller-selected operation-ID integration, issuance/downstream gate,
  production identity/configuration, current E5, and real owner-to-Runner evidence.
- Kept the next step ordered: normally push the accepted source task, then prepare a separately
  gated issuer-integration proposal; no privileged signing implementation is authorized here.

## Files

- `docs/sdlc/backlog.md`
- `docs/sdlc/verify-evidence.md`
- `docs/sdlc/evidence/s2-4-v2-authorization-source-20261030.md`
- `docs/changes/0589-s2-4-v2-authorization-source.md`
- `docs/changes/0590-s2-4-v2-source-approval-ledger.md`

## Verification and limits

This commit changes documentation only. The GPT-PM verdict approved the exact code commit
`aa3496322ca7b05955dd60dfee7decd8056f34ee`; no code or test file changed after that review.
No tests or runtime actions were run for this ledger update. The source approval does not accept
full S2-4 or close S2. Normal push of both task commits remains the next delivery action.
