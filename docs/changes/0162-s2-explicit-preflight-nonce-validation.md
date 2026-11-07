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

- Code implemented at HEAD `6ee97cb06b52900c3c2ab2a9b1b415ae117a7932`.
- The designated functional-test-reviewer verified omitted nonce generation, valid explicit nonce preservation, and empty/non-string rejection: 4 passed, 22 deselected, 0 failed at test HEAD `deed6abe34eeaa8620593442bcdb1413d846f7982`; see record 0165 and `docs/sdlc/evidence/s2-preflight-nonce-functional-run.md`.

## Ownership and next step

- Accountable task owner: operator (delegated S2 continuation).
- Executor: Codex.
- Test author/executor: `functional-test-reviewer`.
- Next: use the exact final branch HEAD for GPT-PM review after specialist review; preserve unrelated process-kill and production quota gates as `NOT_RUN`/`NOT_VERIFIED`.
