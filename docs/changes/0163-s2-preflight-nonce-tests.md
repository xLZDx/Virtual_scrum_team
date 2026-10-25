# Change 0163: Add S2 preflight nonce contract tests

## What changed

- Added focused functional coverage to `tests/vst/test_s2_sandbox_probe.py` for the S2 `collect_inventory` nonce contract.
- Covered omitted nonce generation, preservation of a valid explicit nonce, and rejection of empty/non-string explicit values before platform probing.

## Why

S2 E5/VST-014 binds preflight inventory to a caller-selected run and nonce. The tests falsify the previous falsey-value fallback, which silently replaced an invalid explicit input.

## Affected acceptance and paths

- S2 E5/VST-014: explicit run/nonce-bound preflight input validation.
- `tests/vst/test_s2_sandbox_probe.py`.

## Verification state

- Test cases authored and exact committed-head verification passed; see change record 0164 and `docs/sdlc/evidence/s2-preflight-nonce-functional-run.md`.
- No product source was changed by this test-owner commit.

## Ownership and next step

- Accountable task owner: operator (delegated S2 continuation).
- Test author/executor: functional-test-reviewer.
- Next: continue the remaining S2 acceptance queue; prohibited process-kill scenarios, unverified production quotas/workspace binding, and exact-head GPT-PM approval remain separate gates.
