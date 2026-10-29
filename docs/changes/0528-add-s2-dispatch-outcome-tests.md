# Change 0528: add S2 dispatch outcome acknowledgement tests

## Why

The M03 Store barrier must survive transaction interruption, relay forwarding failure, lost
acknowledgement responses, restart, legacy history, malformed controls, and generation changes.
The accepted design requires behavior evidence for those failure boundaries before M03 can close.

## What changed

- `tests/vst/test_s2_store_backed_pubsub.py` covers transactional pending-marker atomicity,
  same-ID replay, different-ID refusal, acknowledgement binding/idempotency/conflict behavior,
  role authorization, reopen recovery, generation mismatch, legacy history, malformed/out-of-order
  controls, and `synchronous=FULL` read-back.
- `tests/vst/test_s2_dispatch_owner_service.py` covers acknowledgement after successful forwarding,
  no acknowledgement when local forwarding fails, and the exact peer operation allowlist.
- `tests/vst/test_s2_signed_dispatch_instruction.py` updates its in-process transport to expose the
  new acknowledgement RPC.
- Test cases were authored by `functional-test-reviewer` (GPT-6 Luna, medium effort) against source
  head `1ad9e7c`. The owner also covered restart generation mismatch: a retry with a different
  service generation is refused and leaves the pending barrier intact.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- The authoring agent did not execute tests or checks. This change records test source only; result
  remains `NOT_RUN` pending execution by `e2e-runner` against the exact committed head.
- Required focused selectors: the three changed files plus existing dispatch-owner latch coverage;
  `e2e-runner` owns command selection and execution.
- No runtime provisioning, systemd activation, `/etc` writes, account/group/key changes, E5, or real
  dispatch occurred. M03 and overall S2 remain open pending test results, fresh specialist reviews,
  and exact-head GPT-PM adjudication.
- The protected pre-existing `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched and
  unstaged.
