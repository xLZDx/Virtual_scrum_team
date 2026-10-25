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

- Test cases authored. The initial focused execution passed before this test commit, but exact committed-head verification is pending and will be recorded separately after rerun.
- No product source was changed by this test-owner commit.

## Ownership and next step

- Accountable task owner: operator (delegated S2 continuation).
- Test author/executor: functional-test-reviewer.
- Next: rerun these selectors on the committed source/test HEAD and record exact command, environment, counts, warning, and HEADs in evidence/change record 0164.
