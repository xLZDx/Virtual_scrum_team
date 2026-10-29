# Change 0326 — Track the S2 review residual and PM Bridge state

## What changed

- Preserved an earlier reliability review's non-blocking `CloseHandle` setup-failure advisory in VST-013, separate from the reviewed false-success fix.
- Recorded that the exact S2 PM Bridge request has no correlated user/reply turn and therefore does not establish a GPT-PM decision.

## Why

The reliability review at `c7ad087` had identified a possible kernel-handle leak if `CloseHandle` itself returns false during `_JobObject.attach()` setup failure. The strict caller refuses execution on attachment failure, so this does not permit a false PASS and is a non-blocking follow-up rather than a gate blocker. Fresh exact-head reviews at `9ce27f0` reported no actionable source finding. Separately, the required GPT-PM final review request became `CHATGPT_SEND_UNCONFIRMED`; accurate gate state must remain pending until a correlated answer exists.

## Evidence and verification

- Source location: `tools/vst/runner.py`, `_JobObject.attach()` exception cleanup around lines 415-418.
- Review history and exact status: `docs/sdlc/evidence/s2-exact-head-review-9ce27f0.md`; the earlier reliability review at `c7ad087` is preserved in the continuation record.
- PM Bridge request ID: `d923dc1a-4a93-45d5-8524-61b6352df401`; durable job ID: `1aacdfa4-3a58-46bf-ac5f-55d7520eba78`. Tool status is `uncertain`, `CHATGPT_SEND_UNCONFIRMED`, `userTurnId=null`, `replyId=null`, `generationLease=held`. No approval is recorded.
- This is a documentation-only update. No tests/checks/builds were run, and no source/test code changed.

## Remaining acceptance and owners

- Codex owns a future focused fix/disposition of the possible setup-handle cleanup leak; it does not block the S2 code gate unless later evidence establishes a reachable severity that changes acceptance.
- GPT-PM owns the exact S2 gate decision. Codex owns recovering the existing PM Bridge request using the same request ID when safe; do not mint a replacement request or claim approval while the outcome is uncertain.
- Operator remains accountable for S2. Prohibited process-kill/kill-table and E8 runtime scenarios remain `NOT_RUN`; Windows Job Object runtime/system qualification remains open. No push, PR, or merge is authorized.

Change: 0326  
Executor: Codex
