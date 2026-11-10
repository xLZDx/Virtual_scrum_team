# U2-6 GPT-PM review scope

Task: U2-6, negative-case tests and fixtures. Base d4d1543 (U2-5 accepted), head = current HEAD. Delta: tests/uc/test_coverage_report.py, tests/uc/test_u2_result_bridge.py, tests/vst/test_u2_bridge.py, tests/vst/test_u2_gate.py, tests/vst/u2_helpers.py, tools/qa/build_registry.py (four test modules registered), docs/qa/categories.json (generated), and a docstring correction in tools/uc/coverage_report.py (the clean role keeps its CLEAN_LOCAL cell in a mixed report; this matches the code).

Delivers: tests for every refusal of U2-1, U2-3, U2-4 and U2-5: bridge facts validation, role-result binding, one test per receipt-builder RB_* code (including a seeded secret and a narrow changed-path set), the gate refusals STATIC_FINDINGS_PRESENT, MODEL_RESIDUAL_OPEN, ROLE_TABLE_DRIFT, AEVE_HEAD_DRIFT with and without waivers, replay, and the scan-every-rendering test for the coverage report. A static reviewer traced the base APPROVE path of the gate tests against the product code and found no first-run failure.

Settled, do not reopen: ALL TESTS ARE NOT_RUN (operator forbids pytest); only a syntax parse and static review were done, so nothing is runtime-proven. Seeded-failure catalog entries were not added because catalog.json is pinned by raw-byte hash in the frozen rule catalog and the S4 catalog test pins 8 fixtures; adding fixtures would need a product pin change. No product code was mutated.

Ask: the complete BLOCKER/MAJOR set for this delta only (tests that cannot work as written, vacuous assertions, wrong contracts in fixtures).
