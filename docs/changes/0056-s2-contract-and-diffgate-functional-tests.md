# 0056 S2 contract, gate and diff-gate functional coverage

## What changed

- Extended `tests/vst/test_s2_contract_gate.py` with gate-level regressions for missing diff evidence, stale manifest and candidate-head bindings, a failing diff verdict, and an invalid diff signature.
- Added `docs/sdlc/evidence/s2-contract-diffgate-run-280e2d0.md` with exact source HEAD, command, environment, outcome, acceptance mapping, and the S6.3 runtime limitation.

## Why

The existing S2 suite covered diff path classification and signing fields, but did not demonstrate that the final gate refuses absent, stale, failing, or unsigned diff evidence. These cases directly exercise E6.2's non-approval contract.

## Verification state

- Exact source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py`.
- Final result: exit 0; 60 passed, 0 skipped, 1 pytest-asyncio deprecation warning.
- Environment and acceptance mapping: `docs/sdlc/evidence/s2-contract-diffgate-run-280e2d0.md`.
- E6.3 reviewer-identity write denial was not exercised in this Windows run; sandbox evidence remains with the E2E test owner.

## Ownership

- Accountable task owner: operator.
- Test executor: functional-test-reviewer (`gpt-6-luna`); test/evidence edits in this turn by Codex.

Agent-Attribution: functional-test-reviewer (`gpt-6-luna`); Codex executor
