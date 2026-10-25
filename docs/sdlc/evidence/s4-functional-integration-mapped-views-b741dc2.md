# S4 mapped functional and integration category evidence

## Scope and exact revision

- Categories: `functional` (8 mapped IDs) and `integration` (1 mapped ID) from `docs/qa/categories.json`.
- Owner role for both categories: `functional-test-reviewer`.
- Code HEAD: `b741dc205a111e56bb984c59a63af2801870e4fc` on `s4-native-qa-runner`.
- Before either run: `git status --short --branch` showed only `## s4-native-qa-runner`; clean.
- After both runs, before this evidence edit: HEAD remained `b741dc205a111e56bb984c59a63af2801870e4fc`; status remained clean.
- Environment: Windows; Python 3.14.3; pytest 8.4.2.

## Functional category: eight S3 worker-adapter selectors

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/vst/test_s3_worker_adapter.py::test_ac1_request_contract_enforces_identity_fence_and_payload_bounds tests/vst/test_s3_worker_adapter.py::test_ac1_response_contract_rejects_untyped_or_oversized_worker_claims tests/vst/test_s3_worker_adapter.py::test_ac2_resume_and_stop_requests_require_new_fence_and_bound_keys tests/vst/test_s3_worker_adapter.py::test_ac3_idempotency_replay_returns_original_and_rejects_changed_payload tests/vst/test_s3_worker_adapter.py::test_ac3_budget_exact_cap_replay_over_cap_and_stale_snapshot tests/vst/test_s3_worker_adapter.py::test_ac3_zero_budget_allows_zero_charge_but_blocks_positive_charge tests/vst/test_s3_worker_adapter.py::test_ac4_resume_accepts_only_returned_named_app_checkpoint_and_is_idempotent tests/vst/test_s3_worker_adapter.py::test_ac4_worker_state_alone_never_creates_verification_receipts
```

Result: exit 0; **8 passed, 0 skipped, 0 failed**, 1 pytest-asyncio deprecation warning, 1.29s. All eight IDs listed in the current functional category mapping passed.

## Integration category: signed passing TestRun selector

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider -p tools.qa.pytest_pass_plugin tests/vst/test_e4_runner.py::test_harmless_command_produces_signed_passing_testrun
```

Result: exit 0; **1 passed, 0 skipped, 0 failed**, 1 pytest-asyncio deprecation warning, 2.02s. No signer/dependency failure occurred in this local synthetic test.

These runs cover only the mapped IDs at this exact Windows code HEAD. They do not establish broader category completeness, POSIX behavior, or external signer deployment.
