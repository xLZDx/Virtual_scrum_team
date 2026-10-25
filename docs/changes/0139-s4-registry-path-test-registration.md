# 0139 S4 register source-path regression selectors

## What changed

- Registered the three path-confinement regression selectors from test-source commit `f7098d145e3af7d6a00eeae78209d973ce077afe` in the API category.
- Advanced the registry and API `source_head` values to that committed test source and clarified the partial API coverage reason.

## Why

The registry loader validates that declared selectors resolve from a source commit in candidate history. Registering the tests only after their source commit keeps this provenance claim reproducible and allows the real committed registry to exercise the new IDs.

## Affected contracts and paths

- `docs/qa/categories.json`: canonical selector denominator and source provenance.
- `docs/changes/0138-s4-registry-path-regression-tests.md`: test-source record.

## Verification state

- Registry registration is authored but not yet runtime-verified. The focused `tests/qa/test_s4_registry_contracts.py` module is scheduled on the clean exact head after this commit.
- No product code changed.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for the registry trust boundary is not separately named in repository ownership records.
- Commit this registration, run the focused module, and record command, environment, result, skip/warning details, exact HEAD, and generated document registry in record 0140.
