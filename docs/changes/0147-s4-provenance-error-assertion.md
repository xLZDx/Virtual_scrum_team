# 0147 S4 align provenance regression with typed error text

## What changed

- Updated only the expected message in `test_s4_registry_rejects_provenance_outside_candidate_history` to match the implementation's exact `missing, stale, or outside` wording.
- The test continues to assert that a non-ancestor provenance head raises `ContractError`.

## Why

The S4 provenance implementation intentionally gives one typed message for missing, stale, or out-of-history provenance. The prior test failed only because its regular expression did not include the word `missing`; the behavior rejection remains the same.

## Affected contracts and paths

- `tests/qa/test_s4_registry_contracts.py`: one error-message expectation.
- `docs/qa/categories.json`: API source provenance will be advanced in a subsequent registry commit to include this test source.

## Verification state

- Test correction is authored but not executed. The focused registry module will run once after the source and registry updates are committed on a clean exact HEAD.
- Prior NOT_PASS run and the passing committed-loader result remain preserved in change record 0145 and subsequent run evidence; they are not rewritten.

## Ownership and next steps

- Accountable task owner: operator under delegated S4 work. Executor: Codex.
- Technical owner for the registry trust boundary is not separately named in canonical ownership records.
- Commit this source adjustment, register its committed source head, run only the focused module once, and record the outcome.
