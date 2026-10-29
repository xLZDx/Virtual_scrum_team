# S2 attachment-backed AF review contract

Sprint: 39b7cc253f5d

Owner: Codex (implementation/evidence), GPT-PM (independent final adjudication).
Scope: project-owned tools/af_attachment_review.mjs through AF_PM_REVIEW_JS.
No framework or PM Bridge repository modification, global config/daemon restart,
new checkout, source truncation, alternate base or manually authored approval.
The source implementation freeze for this review contract is SHA-256
`9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e`.

## Observed failure and supported contract

The native AF request at62bb632 failed before review: complete canonical UTF-8
prompt5,634,022 bytes exceeds the4,194,304-byte HTTP body limit. Native result:
review_status ERROR, okfalse, no verdict/reply/correlation; request12ac66ae-3d75-
4a45-a849-3bdca0599aa3 has no durable job. Full promptSHA256 is
86e55cbce55ad1ebe65270ffa41d089bf5ae248c891881e41550fa7c64a0e945.

The exact unchanged prompt was sent as a supported file attachment. Actual send
job1ea194b2-c1c7-458f-a1f4-12a3bfe26545/request5d936b12-7a4b-4f76-9b41-
a8c42e8cde65 has status succeeded/sendPhase sent and a sendSnapshot descriptor
with the same5,634,022 bytes and SHA256. Full packet delivery is not approval.
The short await expired; a later successful peek recovered a request-matching
HOLD response and matching declared attachment hash. The peek row has null replyId/
correlated, so this is observed architectural guidance, NOT formal correlation or
AF approval. Raw response is retained only in new private Git metadata; project
records state the result in English without inventing a correlated verdict.

GPT-PM retained S2 NOT APPROVED and actual staging/selection/keys/E5 HOLD. It
permitted immutable plan preparation and instructed Codex to implement a minimal
adapter if the actual supported hook/attachment contract exists. Actual architect
review established that it does: AF overrides the review CLI path and still checks
its deterministic full prompt hash; the existing PM Bridge daemon admits attachments
and preserves validated descriptors. The native caller, not the daemon, omits them.

## Required implementation boundary

1. Delegate canonical prompt generation to the configured native review.js in
   dump-only mode. Preserve AF debug-dump behavior and every original input byte.
   Normal wrapper operation must never accidentally perform the old inline send.
2. Freeze exactly that UTF-8 prompt as one validated immutable file, bind HEAD/base,
   byte count, SHA256 and a durable request UUID before sending. Reuse the UUID for
   exact retries; reject changed bytes or identity under an existing intent.
3. Require the existing compatible authenticated daemon and file-attachments
   capability. Reuse its client and repository-authoritative routing. Send a short
   instruction plus the full attachment through send_and_await; retain mandatory
   waitForCompletionControls and native durable wait semantics. No clipboard/browser
   fallback, chunk splitting, new independent requests after uncertain delivery,
   or reduced material.
4. Obtain real durable job status. Require succeeded/sent, exact request/project/
   conversation, userTurnId/replyId, correlated true and the exact attachment
   manifest name/path/size/SHA256. Match actual durable reply and explicit reviewer
   REVIEW_HEAD plus REVIEW_INPUT_SHA256 acknowledgments. Caller metadata alone is
   not proof. Missing or ambiguous evidence is fail-closed.
5. Parse actual verdict with the existing strict native verdict logic; HOLD, missing
   verdict, contradiction, unsupported/hash/correlation failure cannot approve.
   Return the canonical input hash only by projection from verified attachment
   evidence matching local bytes. Expose the attachment representation explicitly
   in audit metadata; never substitute the short instruction hash.
6. AF remains the sole approval writer and applies its current _accept and expected
   full-input hash checks unchanged. Adapter writes no gate-approval.md, approval.json,
   forged provider receipt, or production authorization. Recheck HEAD and bytes.

## Evidence and acceptance obligations

After complete adapter coding, actual functional-test-reviewer and e2e-runner derive
and execute falsifiable focused tests. Required contracts include exact dump-only
behavior/no send; full-byte preservation and immutable reuse; missing capability,
changed file/hash/HEAD/base, wrong project/request/conversation, missing durable
snapshot, false correlation, missing/changed reply hash/head, conflicting verdict,
uncertain recovery and exact retry identity. Actual review must remain independent.

Relevant security/code review follows tests. Final actual formal AF review receives
the complete new exact HEAD package, including this adapter, through the verified
transport. Existing S2 source/Store evidence is not reclassified as runtime proof.
Actual privileged stage/selection/config/keys/services/E5 remain held independently.
S3–S5 remain queued until S2 acceptance; this integration fixes only transport.
