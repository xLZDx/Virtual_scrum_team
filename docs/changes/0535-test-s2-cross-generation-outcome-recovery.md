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

- Coverage is authored only; no test or check was run by the test author.
- The designated `e2e-runner` must run the focused selectors at the resulting exact commit and
  record exact commands, environment, test-file hashes, and results before acceptance is claimed.
- The Windows-only external-anchor case is explicitly `NOT_RUN` outside POSIX; it is selected in
  the authorized WSL run.
- M03 and overall S2 remain open until the exact run and fresh specialist reviews pass. Production
  coordinator, runtime/E5, root configuration/credentials, prohibited selectors, and the final
  exact-head GPT-PM gate remain separate.
