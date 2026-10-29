# Change 0568: Add an exact-input attachment transport for the S2 AF review

Sprint: 39b7cc253f5d

## What changed and why

The native Agentic_Framework review request at source HEAD `62bb632909205fe21a6b61b4ac5b56dbc8176285` stopped before contacting GPT-PM because the complete canonical prompt was 5,634,022 bytes, above the PM Bridge JSON request-body limit of 4,194,304 bytes. The full input was already delivered once through the existing file-attachment transport, but its recovered reply lacked durable `replyId` and correlation evidence; it was recorded as HOLD guidance, not approval.

This change adds a VST-owned `tools/af_attachment_review.mjs` adapter selected only through Agentic_Framework's existing `AF_PM_REVIEW_JS` override. It delegates complete prompt construction and verdict parsing to the native PM Bridge review CLI. It freezes the exact prompt bytes, binds the request to HEAD/base/project/conversation, sends one real attachment through the existing authenticated daemon, and accepts only a completed durable send snapshot and correlated reply with exact attachment and reviewer acknowledgments. AF remains the only approval writer.

The implementation is frozen at SHA-256 `9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e`. The source contract and falsifiable plan are `docs/sdlc/S2_AF_ATTACHMENT_REVIEW_CONTRACT.md` and `docs/sdlc/S2_AF_ATTACHMENT_TEST_PLAN.md`.

## Decisions and affected contracts

- Do not modify Agentic_Framework, PM Bridge source, global configuration, daemon state, or another checkout. Use only the existing PM Bridge attachment capability and authenticated daemon client.
- Preserve the full native review input exactly. No truncation, chunking, alternate base, fake receipt, inline fallback, or manually authored approval.
- Persist a stable request identity before sending; ambiguous retries recover only that ID and fail closed when no durable job is visible. Verify the daemon's actual attachment manifest, wire descriptor/hash, user turn, correlated reply, exact acknowledgments, and unchanged HEAD.
- Leave runtime staging, selector changes, keys/configuration, service activation, and E5 outside this transport change. Existing source-fixture passes do not become runtime acceptance.

## Verification state at this source commit

- Implementation and test-plan documents are present; the adapter has not yet been exercised by its designated functional/E2E tests. Those tests must bind to the committed source SHA and report exact commands/results.
- No PM-GPT approval was obtained by this commit. The prior 180-second wait/peek response had no `replyId` or correlation and remains unapproved.
- No production staging, key/configuration provisioning, service activation, push, PR, merge, CI, or prohibited process/crash/mutation/E8/policy scenario was performed.

The registry is regenerated after the new Markdown files are staged. This record is the detail file for its own commit.
