# Change 0527: document dispatch replay generation boundary

## Why

The accepted S2 acknowledgement design permits exact same-request replay only when the complete
idempotency payload matches, including the service generation. A read-only review of the current
Runner generation reader confirmed that it binds the active generation to `INVOCATION_ID`; a
generation change therefore makes the earlier acceptance payload unavailable for ordinary replay.

## What changed

- Clarified in the M03 design and dispatch-owner contract that a pending outcome remains blocked if
  the generation changes and must be resolved only through separately authorized reconciliation.
- Recorded the source evidence path and separated it from unverified installed-runtime behavior.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- Read-only evidence: `tools/vst/runner_service.py::read_service_generation_record` requires
  `record["generation"] == os.environ["INVOCATION_ID"]` and requires the record invocation ID to
  match the active process environment.
- No test, check, runtime restart, or privileged recovery was run. `functional-test-reviewer` is
  adding the generation-mismatch refusal case; execution remains pending `e2e-runner`.
- This clarification preserves the GPT-PM accepted fail-closed rule. It does not claim automatic
  recovery after a generation change or claim S2/M03 is closed.
