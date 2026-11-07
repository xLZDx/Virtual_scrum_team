# Change 0569: Fix S2 attachment E2E fixture evidence

Sprint: 39b7cc253f5d

## Failure observed

At HEAD `00cd67b7a07d299081e8c3356de8465698c4de58`, the designated E2E role ran
`node --test tests/af/test_s2_attachment_adapter_e2e.mjs`. The command returned exit 1:
2 tests, 0 passed, 2 failed. One test referenced an undefined imported verdict-module name.
The native dump-only test did execute the real native `review.js`, but its expected prompt
was one LF short because the fixture helper trimmed the raw `git diff` output. This was a
test-harness defect; it did not establish an adapter failure or pass.

The designated functional role also ran `node --test tests/vst/test_af_attachment_review.mjs`
at the same committed HEAD. Its Node process later became terminal (observed PIDs 30144 and
22984 absent), but the nested execution wrapper had not retained the session ID, so the full
stdout and exit code could not be recovered. The partial stdout is not acceptance evidence.

## Correction and affected files

Only `tests/af/test_s2_attachment_adapter_e2e.mjs` changed: the fixture now spreads the
actual imported verdict module and preserves raw diff stdout, including its terminal LF,
when constructing the expected native prompt. Updated test-file SHA-256:
`9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07`.

Production adapter SHA `9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e`
is unchanged. The rerun of both designated focused tests is required at the new committed
HEAD; no pass is claimed here. No live GPT/PM Bridge request, production/runtime action,
CI/build, protected evidence read, or push/PR/merge occurred.

The registry is regenerated after the new Markdown files are staged. This record is the
detail file for its own commit.
