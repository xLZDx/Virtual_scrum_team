# Change 0573: record S2 exact-head gate evidence and review disposition

## Why

The enforced AF pre-push gate rejected the stale S2 verification packet. Refreshing the changed-code tests allowed the exact full-sprint packet to be sent through the project's attachment adapter, but GPT-PM reported that its execution environment could not inspect the attachment.

## What changed

- Recorded current committed-head functional and E2E results for the code paths AF identified as changed after its prior tested head.
- Updated the S2-1 backlog and evidence matrix to distinguish source/test acceptance from the still-open exact-head approval and push.
- Recorded the durable request, reply and full-attachment identity, and preserved the fact that no approval was issued.
- Added `docs/sdlc/evidence/s2-exacthead-branch-refresh-00312f0-20261029.md` with exact commands, environments, hashes, outcomes and limitations.

## Verification

- `functional-test-reviewer`: 35 passed, 0 failed for `tests/vst/test_af_attachment_review.mjs` at `00312f0`.
- `e2e-runner`: 2 passed, 0 failed for `tests/af/test_s2_attachment_adapter_e2e.mjs` at `00312f0`.
- Existing S2-1 WSL run: 130 passed, 0 failed; committed blob verified against its recorded SHA-256.
- AF/GPT-PM exact-head review request was correlated but returned `NOT REVIEWED — EXECUTION ENVIRONMENT UNAVAILABLE`; approval and push are not claimed.

## Closure boundary

This record does not close delivery. Retry the exact full-range review through the supported attachment adapter when GPT-PM can inspect the input, then use the normal pre-push path. S2-2 remains unstarted by this continuation.
