# 0132 S5 E2E candidate-head fixture correction

## What changed

- Changed the stale-head E2E fixture to set `candidate_head` on the unsigned receipt body and then sign the completed body.
- Removed the unsupported attempt to pass `candidate_head` through the existing helper's keyword overrides.

## Why

The focused run at clean HEAD `2f4f8cee96d6058aba6f7993236abd2b19715276` collected all three cases, but each failed in fixture setup with `TypeError: unsigned_receipt() got multiple values for keyword argument 'candidate_head'`. This is a test-authoring defect; Store/Gate behavior had not yet been reached.

## Affected contracts and paths

- `tests/vst/test_s5_v3_store_gate_e2e.py`
- No product source or acceptance contract changed.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- Retain the failed attempt in evidence; no assertion was weakened and no product failure is inferred.

## Verification state

- Exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_store_gate_e2e.py`.
- Result at the prior clean HEAD: **3 failed during fixture setup**, 0 passed; one global `pytest-asyncio` deprecation warning.
- Corrected clean-head execution is pending.

## Follow-up

1. Run the focused module once on the clean corrected commit and record the complete attempt sequence and final outcome.
2. Update the E2E category denominator and regenerate the document registry in the evidence commit.
