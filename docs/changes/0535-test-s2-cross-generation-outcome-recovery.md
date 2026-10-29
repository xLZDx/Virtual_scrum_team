# Change 0535: add S2 M03 cross-generation recovery acceptance coverage

## Why

GPT-PM's M03 ruling requires a distinct historical read-only route and evidence that it cannot
authorize new work, bypass current checks, or clear unresolved/corrupt history. The previous
119/119 focused result predates this recovery implementation and does not verify it.

## What changed

The functional-test-reviewer added acceptance-mapped cases in:

- `tests/vst/test_s2_store_backed_pubsub.py`
- `tests/vst/test_s2_signed_dispatch_instruction.py`
- `tests/vst/test_s2_dispatch_owner_service.py`

Coverage maps to `S2-PROV-M03-R01` and the read-only recovery contract:

- Exact prior result is returned after generation changes, preserving G1 in the result and ACK;
  the case asserts no second accepted event.
- Expired or currently revoked accepted envelopes recover the historical result; never-accepted
  expired/revoked envelopes are refused without invoking admission.
- Changed authenticated principal, envelope, key/signature bytes, or caller-asserted principal are
  refused; non-owner RPC roles cannot call replay.
- Store replay does not change event anchor, event count, or operation count.
- Legacy, malformed/contradictory control history, and incomplete external-anchor reconciliation
  fail closed.
- A current admission refusal may trigger only one historical lookup; ACK remains bound to the
  original service generation. Existing send-failure and ACK-failure regressions remain in scope.

## Verification state

- The functional-test-reviewer did not run tests. The designated e2e-runner executed the four
  focused selectors at exact HEAD `c855ca4f2888d7288b006973950e4c6d28023b63`: **130 passed,
  0 failed**, exit 0. Exact command, environment, hashes, and limits are in
  `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-test-run-20261029.md`.
- The external-anchor selector is POSIX-only; it ran in the authorized WSL environment.
- The exact run and fresh specialist reviews passed. GPT-PM request
  `d16dbf96-54f8-4c96-8fa7-2b24445f85d9` closed `S2-PROV-M03-R01` for source/test scope; see
  `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
  Overall S2 remains open: production coordinator, runtime/E5, root configuration/credentials,
  prohibited selectors, and the final exact-head GPT-PM gate remain separate.
