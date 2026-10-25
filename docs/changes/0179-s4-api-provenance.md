# 0179 — Advance API category provenance to corrected tests

## What changed

Updated the API category's `source_head` in `docs/qa/categories.json` to `d06e92b1d5460ee892754aa08916abb2179874e0`, the commit containing the final API falsifiers after fixing the live-owner precondition in the idempotent epoch test.

## Why

The 73-selector API denominator now includes `tests/vst/test_s4_python_api_entrypoints.py`. Its category provenance must include the committed test source it names before a current-head registry validation or acceptance run can be trusted.

## Verification state

No tests were run before this documentation/manifest commit. The next action is the exact focused API plus seeded-failure invocation on the resulting manifest HEAD. The previous run on `3df219e4b4cd1700e80b282c0d08fba8205006f5` was 92 passed, 1 skipped, 1 failed due solely to the corrected fixture precondition; it is superseded by the rerun.

## Scope

No product code or test selector IDs changed. API coverage remains statically `COMPLETE` for the 79-entry source inventory; run-time acceptance is pending exact-head execution.
