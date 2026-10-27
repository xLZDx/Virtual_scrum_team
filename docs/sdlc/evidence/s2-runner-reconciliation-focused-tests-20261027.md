# S2 focused tests: runner execution reconciliation freeze

## Scope and source identity

This report records the accepted focused functional test run for the S2 reconciliation source freeze. It covers Store continuation guards and in-memory authority behavior. It does not claim a live service/systemd/WSL runtime result or complete S2 acceptance. The protected `docs/sdlc/evidence/s2-functional-test-run.md` was preserved without edits.

| Field | Value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Branch / base HEAD | `s4-canonical-continuation` / `2da827be982d3f2d6f2adf152668af6ff8007f21` |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Tracked binary diff SHA-256 | `ef7402fc18453bb64d8182c56b8979d54915d64d1101448430235f7cfc747ea7` |
| Complete working-delta SHA-256 | `b746b0dc1384fe3c97238addbbd8b17d4be441fb528237e706418ff9886b2d30` |
| Fingerprint method | SHA-256 over the tracked `git diff --binary` SHA-256 followed by sorted untracked path and content SHA-256 entries; this report is excluded to avoid self-reference. The entry list includes all current untracked files, including implementation sources and tests. |
| Test file before this task | SHA-256 `01061832e57e03d9aeab08523ec828c3c6f138123af7e4c3a82bae6f237057a6`; file was already untracked at task start. |
| Worktree / staging | Dirty with pre-existing concurrent changes. No files were staged, committed, reverted, or edited outside the test file and this evidence report. |

Source/test path hashes at the final run:

| Path | SHA-256 |
|---|---|
| `tools/vst/store.py` | `616fc73f118b46fec36f5ccf55a507582b72dc13c8d136ad9b81200bde973d4b` |
| `tools/vst/execution_grant.py` | `305cad3216222399f221ad91e53514ab726ee119437bf5cf56d453f766e52d27` |
| `tools/vst/runner_service.py` | `f6db3bb2989121a539da07cbdfac3e766e07d6c55c8a3a0fb8deeeef75c71ce5` |
| `tools/vst/runner.py` | `efff9b1798dd05eada91843a382cedefd7045a7d7fe4097a08d80e05d3bbd7b7` |
| `tools/vst/supervisor.py` | `56df972d93c0439622f4cdf0cd34c45b3e66fbc8d81dc7689d22049d373686f3` |
| `tests/vst/test_s2_persistent_runner_service.py` | `d4faf6b621c8805ed2d05b9d74f76f7f10b546b178a9b67cfb66aed650adcab6` |
| `tests/vst/test_s2_runner_lifecycle.py` | `fbed70655086bb84f2ba0fc2b203756f3c83778edd49f1d60e1c85f02ec29394` |

Changed product source files were not edited by this test task. The relevant current source set includes the changed tracked `tools/vst/store.py` and the untracked `tools/vst/execution_grant.py`, `tools/vst/runner_service.py`, and related runner/service files; their complete working-tree content is covered by the fingerprint above.

## Focused commands and outcomes

Commands were run separately from the repository root. Aggregate result: **130 passed, 0 failed, 0 skipped**. Each command emitted one `pytest_asyncio` deprecation warning for `asyncio.get_event_loop_policy`, scheduled for removal in Python 3.16.

1. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` — exit 0; **38 passed**, 0 failed, 0 skipped; 1 warning; 1.27s.
2. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence` — exit 0; **32 passed**, 0 failed, 0 skipped; 1 warning; 0.68s.
3. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority` — exit 0; **38 passed**, 0 failed, 0 skipped; 1 warning; 5.89s.
4. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py` — exit 0; **22 passed**, 0 failed, 0 skipped; 1 warning; 16.29s.

## Acceptance mapping

| Requested behavior | Test IDs / result | Evidence and limits |
|---|---|---|
| Successors remain blocked by an `EXECUTION_RESERVED` predecessor or unresolved `INDETERMINATE` state | `test_execution_reserved_predecessor_blocks_successor_gates_before_recovery`; `test_reserved_or_unsafe_reconciled_predecessor_blocks_every_successor_gate[None]` — passed | All three Store entry points (`acquire_lease`, `execution_grant_basis`, `claim_runner_execution`) refuse. In-memory Store only. |
| Successors remain blocked after invalid-signature, `EFFECTS_UNRESOLVED`, or `RECONCILIATION_REJECTED` outcomes | `test_execution_reconciliation_rejects_tampered_mismatched_or_invalid_records` cases; `test_reserved_or_unsafe_reconciled_predecessor_blocks_every_successor_gate[EFFECTS_UNRESOLVED/RECONCILIATION_REJECTED]` — passed | Invalid record leaves predecessor `INDETERMINATE`; each unsafe signed outcome has `continuation_allowed=False`, and all three successor gates remain closed. |
| Exact operator HMAC `EFFECTS_RESOLVED` permits a separately authorized successor | `test_effects_resolved_operator_record_allows_only_a_separately_authorized_successor` — passed | Resolution binds exact grant identity and predecessor; a distinct attempt acquires a lease, obtains a fresh grant basis and claims only after a new run-bound preflight. In-memory keys/Store; no operator action was performed. |
| Pre-spawn `PENDING` predecessor remains retryable under normal lease/retry rules | `test_pre_spawn_pending_predecessor_can_retry_only_after_normal_lease_rules` — passed | Startup marks predecessor indeterminate with predecessor state `PENDING`; the test advances the fake clock, reaps/marks the expired lease, then obtains attempt 2 through ordinary Store gates. |
| Tampered/mismatched fields, reused resolution ID, invalid HMAC and invalid outcome reject | `test_execution_reconciliation_rejects_tampered_mismatched_or_invalid_records` parameter cases; `test_execution_reconciliation_rejects_resolution_id_reused_for_another_grant` — passed | Signatures use the existing HMAC signing helper and distinct in-memory resolution key. Rejected records do not alter the predecessor from `INDETERMINATE`. |
| Fail-stop after reservation until durable `COMPLETE`; preserve exact COMPLETE replay and ordinary pre-reservation refusal | `test_runner_service_fail_stops_every_post_reservation_failure_before_complete` parameter cases; `test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt`; `test_exact_current_generation_not_found_is_nonfatal_refusal` — passed | Failure cases exercise `_run_grant`'s fail-stop wrapper with a fake runner callback; exact COMPLETE replay uses the in-memory Store. These do not start the daemon or prove systemd restart behavior. |
| E1, E2 selected contracts, E6 diff gate | Group 2: 32 passed; group 3: 38 passed; group 4: 22 passed | These are the previously approved selectors only. No additional policy selectors were executed. |

## Runtime boundary and ordered handoff

All added acceptance tests use in-memory `Store(":memory:")`, a fake clock, or faked runner/authority callbacks. They prove the scoped Python contracts, not actual service process termination, systemd generation rotation, POSIX credentials, WSL sandbox isolation, or an installed worker helper. Those platform/runtime claims remain `NOT_RUN` and require separate approved runtime work owned by Codex coordination.

Forbidden full-suite, protected 20 selectors, process/crash/recovery/mutation/E8/policy selectors, checks/build/CI/migrations, service installation, and runtime/provisioning were not run.

Test-authoring note: the first run of the expanded persistent-service file reported 37 passed and 1 failed because the two-task duplicate-resolution fixture had initialized only one Store concurrency slot. The fixture was corrected to initialize two slots; the final permitted command above then passed all 38. This was a test-fixture setup error; no product source was changed.

1. Codex links this artifact and the test IDs to the exact S2 source change record.
2. Codex records runtime/service-manager acceptance separately as `NOT_RUN` until executed in the authorized environment.
3. GPT-PM reviews the exact diff and evidence at its separate acceptance gate; this test report is not that approval.

Report SHA-256 is provided in the task handoff after artifact creation.
