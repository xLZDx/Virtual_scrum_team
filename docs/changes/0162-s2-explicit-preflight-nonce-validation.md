# Change 0162: Reject explicitly invalid S2 preflight nonces

## What changed

- `tools/vst/preflight.py::collect_inventory` now generates a nonce only when the argument is omitted as `None`.
- Explicit empty or non-string nonce values now raise `ContractError` before platform probing or inventory collection.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, and `core/LESSONS_LOG.md` record the S2 E5/VST-014 scope, reasoning, and pending verification.

## Why

The previous `nonce = nonce or uuid.uuid4().hex` expression silently changed falsey caller input into a fresh value. Run-bound preflight callers that accidentally supplied an empty nonce could therefore obscure a configuration error. The change preserves existing automatic nonce generation for omitted input and preserves valid explicitly supplied nonce values.

## Affected contracts and paths

- S2 E5/VST-014 run-bound sandbox inventory and preflight nonce binding.
- No signer format, attestation schema, sandbox policy, or accepted nonce value is changed.
- Paths: `tools/vst/preflight.py`, `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`.

## Verification state

- Code implemented; not runtime-proven.
- No tests or checks were run by Codex during this coding step. The designated `functional-test-reviewer` owns focused verification for omitted nonce generation, valid explicit nonce preservation, and rejection of empty/non-string explicit values.
- Exact source head and test result must be recorded after the test-owner run.

## Ownership and next step

- Accountable task owner: operator (delegated S2 continuation).
- Executor: Codex.
- Test author/executor: `functional-test-reviewer`.
- Next: commit this coherent change, then run the focused functional verification on the committed exact head; preserve unrelated process-kill and production quota gates as `NOT_RUN`/`NOT_VERIFIED`.
