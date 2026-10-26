# Change 0362 — Refresh S4 registry after cache-prefix test assertions

## What changed

- Regenerated `docs/qa/categories.json` after test-source commit `0a6b47806482dd16b4944b1ee005fe458eab78e7`, binding its source inventory and E2E selector metadata to the tests that assert per-run cache-prefix isolation.
- The registry contains 963 selectors; 52 have no runnable runtime profile and remain excluded. The E2E category lists 59 selectors, including one policy `NOT_RUN` selector.

## Provenance and command

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --write`
- Result: exit 0; output `wrote docs/qa/categories.json`.
- Registry SHA-256: `8d44b98a1ef55f5b5549deefc2cb0aca05e019a12ae5da726958735352e4126e`.
- Registry `source_head`: `0a6b47806482dd16b4944b1ee005fe458eab78e7`.

## Verification state and next action

- Focused test-source verification is recorded in change 0361: 2 passed, exit 0, with one existing `pytest-asyncio` deprecation warning.
- This registry revision has not yet been used for report-bound acceptance. Run E2E and regression on this exact committed candidate with separate fresh dependency targets; preserve the 52 profile-excluded selectors as `NOT_RUN`.
- Historical report-bound FAIL rows and bytecode inventory diffs remain unchanged and do not serve as rerun evidence.

## Ownership

- Accountable owner: Codex.
- Registry generation: Codex.
- Report-bound test execution: E2E runner.
