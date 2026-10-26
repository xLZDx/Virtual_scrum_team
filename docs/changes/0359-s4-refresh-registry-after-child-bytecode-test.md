# Change 0359 — Regenerate S4 registry after child bytecode isolation test

## What changed

- Regenerated `docs/qa/categories.json` after test-source commit `ec2a8e21ad5ca1c03f6752567ccf94a6eea1a46a` so the registry's source inventory and selector list include the E2E child-environment regression.
- The manifest contains 963 selector entries, including 52 with no runnable runtime profile that remain excluded from execution. The Windows E2E category lists 59 selectors, of which one remains policy `NOT_RUN`.

## Why

The previous registry described the E2E runner tests before the new assertion that nested CLI children disable dependency-target bytecode writes. This refresh binds the manifest to the committed test source.

## Provenance and command

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --write`
- Result: exit 0; output `wrote docs/qa/categories.json`.
- Registry SHA-256: `d4bb84bda27001a806e43639e1b74c434043bea2d36a7685f1cdcdde2084351d`.
- Registry `source_head`: `ec2a8e21ad5ca1c03f6752567ccf94a6eea1a46a`.

## Verification state and next action

- The focused new selector passed before the source commit: 1 passed, exit 0, with one existing pytest-asyncio deprecation warning.
- This generated manifest has not yet been used for report-bound acceptance. Run the focused E2E regression and report-bound E2E and regression categories only after this registry commit, with fresh targets.
- Keep all 52 selectors without an allowed runtime profile `NOT_RUN`; no policy or process-control selector is authorized by this record.

## Ownership

- Accountable owner: Codex.
- Registry generation: Codex.
- Report-bound test execution: E2E runner.
