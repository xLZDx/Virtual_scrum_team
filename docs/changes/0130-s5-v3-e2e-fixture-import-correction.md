# 0130 S5 E2E fixture import correction

## What changed

- Corrected the E2E test module to import shared story/task/epoch constants directly from `tests.vst.e1e4_helpers`, where they are defined.
- Removed unused imported fixture constants.

## Why

The first focused collection attempt at HEAD `030607975e99acbbe66aefad8fc789fe1f3f577b` stopped before test execution because `test_s5_v3_evidence.py` does not export `STORY`. This was a test-authoring defect, not a product failure. The test was updated at its owning source.

## Affected contracts and paths

- `tests/vst/test_s5_v3_store_gate_e2e.py`
- No product source or acceptance contract changed.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- The failed collection event is retained in the evidence trail; this correction does not remove or weaken an assertion.

## Verification state

- Initial focused command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_store_gate_e2e.py`.
- Initial result: collection error, 0 tests executed; ImportError for missing exported name `STORY`.
- Corrected test execution is pending this commit and will be recorded separately on the exact clean HEAD.

## Follow-up

1. Run only `tests/vst/test_s5_v3_store_gate_e2e.py` on the clean corrected commit.
2. Record exact environment, IDs, counts, warnings and limitations in change record 0131 and update the QA registry denominator.
