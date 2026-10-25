# Change 0260: Align signer ACL assertions with the POSIX contract

## What changed

- Updated three signer ACL regressions to assert the implementation's specific `extended POSIX ACL` error text.
- No product source or category mapping changed.

## Why

At source HEAD `c51105a`, the ACL verifier standardized its rejection as `path has an extended POSIX ACL`. The older signer-path tests still matched the narrower phrase `extended ACL`, which no longer appeared contiguously in that message. Runtime execution confirmed that the guard rejected the synthetic ACL and that only the stale regex caused those three selectors to fail.

## Decisions and ownership

- Keep the assertion tied to the explicit ACL rejection and current contract message; do not weaken it to a generic exception check.
- Test author/executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator; executor: Codex.

## Affected contracts and paths

- `tests/qa/test_s4_worker_boundary_contracts.py`
- POSIX ACL rejection text in `tools/vst/sandbox.py` (unchanged by this commit)

## Verification state

- Initial exact-head snapshot: source/test HEAD `180e330f5bf1f4f74c6245eba2ffb099a1bffad6`, WSL run `15e0b1e3d2a443c4b52dcbe6af43a759`.
- Focused run result before this correction: 12 passed, 3 failed. All failures were legacy regex mismatches against `path has an extended POSIX ACL`; the ACL guard rejected the test ACL in each case.
- This test-only correction has not been executed. Required next step: commit this change, transfer a fresh exact-head WSL snapshot, then rerun the mapped focused selectors and the synthetic functional CLI only if focused selectors pass.

Executor: Codex
