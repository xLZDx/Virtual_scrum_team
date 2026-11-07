# Change 0570: Make the attachment tamper fixture byte-precise

Sprint: 39b7cc253f5d

## Observed result

At HEAD `7b12776365607a6d1daf17c0c5631820cb641ff9`, the designated functional command
`node --test tests/vst/test_af_attachment_review.mjs` returned exit 1: 34 passed, 1 failed,
0 skipped. Its sole failure was an expectation mismatch in the post-send attachment-tamper
test. The fixture wrote the different-length text `changed after send`, so the adapter
correctly refused at its size check before reaching the test's narrower expected hash-error
message. This was not an acceptance failure in product code.

At that same HEAD, the separate designated E2E command
`node --test tests/af/test_s2_attachment_adapter_e2e.mjs` returned exit 0: 2 passed,
0 failed, 0 skipped. It verified the >4 MiB loopback attachment path and real native
`review.js` dump-only bytes; the fake verdict was not GPT approval. The prior first
functional command at HEAD `00cd67b7a07d299081e8c3356de8465698c4de58` remains unverified
because its session output/exit code were lost.

## Correction and scope

Only `tests/vst/test_af_attachment_review.mjs` changed. The post-send fixture now flips a
byte in the existing attachment buffer without changing its size and asserts the resulting
SHA-256 mismatch is rejected before acceptance. Updated test SHA-256:
`1c42e35d6ae8b790e5c722f44217620b53f018b82809f7d6fea99f5450243c5d`.

Product adapter SHA `9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e`
is unchanged. The E2E test file is unchanged from its 2/2 pass. Both suites must be rerun
at the new committed HEAD. No real GPT/daemon review, CI/build, production/runtime action,
protected evidence access, push, PR, or merge occurred.

The registry is regenerated after the new Markdown file is staged. This record is the
detail file for its own commit.
