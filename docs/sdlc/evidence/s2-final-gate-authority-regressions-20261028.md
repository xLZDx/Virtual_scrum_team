# S2 focused evidence: gate and authority reconciliation regressions

## Exact source identity and scope

This is the functional-test review record for the implementation owner's frozen S2 source changes in `Store.evaluate_gate`, execution-reconciliation predecessor binding, and post-reservation boundary fail-stop. It records only approved focused tests. It does not claim a live daemon, systemd restart, POSIX/WSL sandbox, or complete S2 acceptance. The protected `docs/sdlc/evidence/s2-functional-test-run.md` was not modified.

| Field | Value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Branch / base HEAD | `s4-canonical-continuation` / `2da827be982d3f2d6f2adf152668af6ff8007f21` |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Tracked binary diff SHA-256 | `4a9ea8fa78009134042224f563bf8705b68c05db2ce749f1f2767d0bdae58e19` |
| Complete working-delta SHA-256 | `b45ba45bc05028a84a9b065642a12833e6b7c75d521359d61250dca3f210fde2` |
| Fingerprint definition | SHA-256 over the tracked `git diff --binary` SHA-256, followed by sorted untracked path/content SHA-256 entries. This report is excluded to avoid self-reference; 24 other untracked files were included. This captures modified tracked paths plus all untracked source, test, and evidence files at the final run. |
| Test file before this task | `tests/vst/test_s2_persistent_runner_service.py` SHA-256 `d4faf6b621c8805ed2d05b9d74f76f7f10b546b178a9b67cfb66aed650adcab6`. The file was already untracked; this task added the gate/reconciliation/boundary regression cases. |
| Worktree / staging | Dirty with concurrent project work. No files were staged, committed, reverted, or edited outside the test file and this evidence record during this task. |

Relevant file SHA-256 values at final run:

| Path | SHA-256 |
|---|---|
| `tools/vst/store.py` | `43b5b605e9763ddb53c4b4d80c37db9072d04b80a0b93742a83908bee2065738` |
| `tools/vst/execution_grant.py` | `0eddf396459ed33780c8c93d84e4b2ce9f895cb76b3b3c357cf2b9f0ad4554b6` |
| `tools/vst/runner_service.py` | `f6db3bb2989121a539da07cbdfac3e766e07d6c55c8a3a0fb8deeeef75c71ce5` |
| `tools/vst/runner.py` | `efff9b1798dd05eada91843a382cedefd7045a7d7fe4097a08d80e05d3bbd7b7` |
| `tools/vst/supervisor.py` | `56df972d93c0439622f4cdf0cd34c45b3e66fbc8d81dc7689d22049d373686f3` |
| `tests/vst/test_s2_persistent_runner_service.py` | `20b1d7192443b34f2bd1ff682f0398c32663ab660d1383eaae9683d653ae4055` |
| `tests/vst/test_s2_runner_lifecycle.py` | `fbed70655086bb84f2ba0fc2b203756f3c83778edd49f1d60e1c85f02ec29394` |

## Approved commands and final outcomes

All commands ran separately from the repository root. Aggregate: **138 passed, 0 failed, 0 skipped**. Each command emitted one installed `pytest_asyncio` deprecation warning: `asyncio.get_event_loop_policy` is scheduled for removal in Python 3.16.

1. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` — exit 0; **46 passed**, 0 failed, 0 skipped; 1 warning; 1.22s.
2. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence` — exit 0; **32 passed**, 0 failed, 0 skipped; 1 warning; 0.47s.
3. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority` — exit 0; **38 passed**, 0 failed, 0 skipped; 1 warning; 3.75s.
4. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py` — exit 0; **22 passed**, 0 failed, 0 skipped; 1 warning; 16.05s.

## Acceptance mapping for new regressions

| Acceptance behavior | Test IDs / result | Evidence and limitation |
|---|---|---|
| A stale PASS cannot mask a later unresolved `PENDING`, `EXECUTION_RESERVED`, or `INDETERMINATE` claim | `test_gate_refuses_stale_pass_when_newer_execution_is_unresolved[PENDING/EXECUTION_RESERVED/INDETERMINATE]` — passed | Starts with a committed PASS receipt for attempt 1, claims attempt 2, then verifies `Store.evaluate_gate` refuses before stale receipt evaluation for each unresolved state. In-memory Store only. |
| Gate evaluation proceeds only after safe terminal conditions: `COMPLETE`, signed `EFFECTS_RESOLVED`, or justified pre-spawn `PENDING` recovery | `test_gate_stays_default_closed_and_evaluates_only_after_safe_execution_terminal[COMPLETE/EFFECTS_RESOLVED/PENDING_PRESPAWN]` — passed | Gate proceeds to its ordinary evaluator after each safe terminal/exception. It remains `MODIFY` because the fixture intentionally omits other required manifest receipt types; a prior PASS alone does not approve. |
| `AUTHORITY_CHANGED_BEFORE_COMPLETION` binds reconciliation to `EXECUTION_RESERVED` and permits only the valid outcome matrix | `test_authority_changed_before_complete_reconciliation_requires_exact_reserved_predecessor` — passed | Expired lease between reservation and completion emits the authority-changed indeterminate record. Null or wrong predecessor and `NO_EXECUTION_PROVEN` against an `EXECUTION_RESERVED` predecessor are rejected; exact signed `EFFECTS_RESOLVED` is accepted. |
| Exception from the post-reservation daemon-boundary callback confirms reservation and triggers fail-stop | `test_post_reservation_boundary_exception_confirms_reservation_and_fails_stop` — passed | Real `ExecutionAuthority.reserve()` receives exact reservation confirmation, then the fake boundary callback raises `OSError`. `_run_grant` raises `AmbiguousExecutionAuthorityError`; the test observes `reservation_confirmed=True`, `completion_confirmed=False`, and no child launch. No service installation/runtime was used. |
| Exact COMPLETE replay and pre-reservation ordinary refusal remain intact | `test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt`; `test_exact_current_generation_not_found_is_nonfatal_refusal` — passed | Store replay returns only the exact committed receipt; exact current-generation `NOT_FOUND` remains a nonfatal refusal. |

The added acceptance regressions use fresh `Store(":memory:")` instances, a fake clock, and fake RPC/runner callbacks. They prove the Python Store and service method contracts, not a live systemd process restart or OS containment.

## Scope exclusions and handoff

The full suite, protected 20 selectors, process/crash/recovery/mutation/E8/policy selectors, checks/build/CI/migrations, service installation, WSL runtime, and provisioning were not run. Those items remain `NOT_RUN` under the task boundary.

During test development, an initial persistent-module run exposed fixture-only mistakes (missing imported worker key and a second attempt receipt lacking its previous-receipt hash). A subsequent run exposed a one-slot setup in the two-task resolution-ID fixture. These fixtures were corrected; the final approved commands above passed. No product-source changes were made by this test task.

1. Codex links this evidence and test IDs to the exact S2 source change record.
2. Codex keeps unavailable service/runtime acceptance explicitly `NOT_RUN` until separately authorized evidence exists.
3. GPT-PM reviews the exact source diff and test evidence at its separate gate.

Report SHA-256: recorded in the test-agent handoff after creation.
