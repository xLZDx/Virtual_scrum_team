# S2 adjudicated runner regression test attempt 2

## Scope, provenance, and environment

This test pass resumed after GPT-PM allowed a successor receipt gap when every missing attempt has either exact authenticated `NO_EXECUTION_PROVEN` from `PENDING` or exact signed `EFFECTS_RESOLVED` from `EXECUTION_RESERVED`. Generic `INDETERMINATE` and unresolved/rejected/worker-lost/lease-expiry states remain ineligible. Correlated decision: request `b84e73a1-55ac-47b0-87f8-20261028f002`, reply `8cc3b2ca-fc98-4d8a-98ee-120579a9cde6`.

| Field | Value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Branch / committed base HEAD | `s4-canonical-continuation` / `378df7260d8654f396ae1b45eaa9462d4bb4b88f` |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Final persistent test-file SHA-256 | `63fd8c5696ebb9020b230e84d901a6de1394bcf79f6597c3a93b34218bd002b6` |
| Test execution | Focused pytest selectors only; no checks, build, CI, migrations, runtime/systemd/provisioning, prohibited process/crash/recovery/mutation/E8/policy selectors, commit, or push. |
| Protected pre-existing evidence | `docs/sdlc/evidence/s2-functional-test-run.md` was not modified. |

Only test code and this new evidence file were authored by this test role. No product source was edited. The one test-fixture authority window was raised to 3600 seconds to satisfy the accepted full-manifest-window contract. Two test-only stale contract references were updated to the source's renamed successor-eligibility API and evidence argument. The effects-resolved receipt assertion was narrowed to the specific `tests` / `TestRun` slot after diagnosis showed a separate supervisor `Documentation` receipt in the task-wide receipt list.

## Exact source and test identities

| Path | SHA-256 |
|---|---|
| `tools/vst/store.py` | `2cebe8f213caf8091c960cc941755c55d6bb2d8d96c0eb7ee2edeba9b7c4e51f` |
| `tools/vst/gate.py` | `562474f756cd897b9239fc1573870e15924c547547412be2ab8813d23a71600f` |
| `tools/vst/execution_grant.py` | `f99810d04664f6d95e336be2138001c2e255e6ae9e8eb531b806d745fc4c7c43` |
| `tools/vst/supervisor.py` | `d6ed3463d3a830a4cf46424a9e3fb8d9d79b173b559e03184646d9fa7e3ec55f` |
| `tools/vst/supervisor_service.py` | `684eabcca773fe54a6fcaab7936e05b8bcad2940f6dca128c6644ad8e3c83a78` |
| `tools/vst/runner_service.py` | `a4357d4757e8a4a307b0c952c5df4eda73773b64af4eecf53ad5a8fdddfe1d7f` |
| `tools/vst/systemd/vst-runner.service` | `4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be` |
| `tests/vst/test_s2_persistent_runner_service.py` | `63fd8c5696ebb9020b230e84d901a6de1394bcf79f6597c3a93b34218bd002b6` |
| `tests/vst/test_s2_runner_lifecycle.py` | `fbed70655086bb84f2ba0fc2b203756f3c83778edd49f1d60e1c85f02ec29394` |
| `tests/vst/test_s2_contract_gate.py` | `aac3b57631b0530ade78c2d0173060f5f6333d8d7f04e5075b3e82ee99656e39` |
| `tests/vst/test_s2_diffgate.py` | `10e17cd62d71b7c49bb3fdabc7a873721ecd797ce1f3fa36876f06f6dac499cc` |

## Final focused commands and outcomes

Commands were run from `D:\Repo\Virtual_scrum_team`. Each command below exited 0. Pytest reported one installed `pytest-asyncio` deprecation warning per execution: `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.

| Group / node IDs | Exact command | Result |
|---|---|---|
| Persistent runner module; 56 collected node IDs, all passed. Newly added/changed behavioral nodes: `test_verified_pre_spawn_gap_allows_next_receipt_and_preserves_receipt_hash_chain`, `test_effects_resolved_gap_links_successor_to_last_real_receipt_hash`, `test_execution_gap_rejects_reserved_predecessor_and_untrusted_gate_gap_evidence`, `test_runner_prespawn_terminalization_binds_exact_claim_and_blocks_later_reserve`, `test_pre_reserve_runner_failure_terminalizes_claim_without_calling_reserve`, `test_runner_authority_window_must_cover_manifest_timeout_and_completion_margin[issue|claim|reserve]`, `test_runner_grant_uses_full_manifest_timeout_when_issuance_is_feasible`, and `test_operator_reconciliation_rpc_is_versioned_and_role_pinned`. | `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` | **56 passed**, 0 failed, 0 skipped; exit 0; 1 warning; 1.73s. |
| E1 contract-gate; 7 selectors, 32 cases. Exact IDs appear in command. | `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence` | **32 passed**, 0 failed, 0 skipped; exit 0; 1 warning; 0.59s. |
| E2 runner-lifecycle; 4 selectors, 38 cases. Exact IDs appear in command. | `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority` | **38 passed**, 0 failed, 0 skipped; exit 0; 1 warning; 5.41s. |
| E6 diff-gate; 22 cases in the file. | `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py` | **22 passed**, 0 failed, 0 skipped; exit 0; 1 warning; 21.37s. |

Total final focused coverage: **148 passed, 0 failed, 0 skipped across four commands**. The 56-node persistent module collection was independently enumerated using `C:\Python314\python.exe -m pytest --collect-only -q -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` (56 tests collected, exit 0). The full collection output is available from that command; the focused acceptance IDs and all E1/E2 selectors are listed above and correspond to the established regression groups in `s2-final-gate-authority-regressions-20261028.md`.

## Retry diagnostics and corrected test issues

The first full-file retry after the source predicate change collected 56 nodes and reported 54 passed, 2 failed, 0 skipped. It exposed two test defects, not a proven product defect:

1. `tests/vst/test_s2_persistent_runner_service.py::test_effects_resolved_gap_links_successor_to_last_real_receipt_hash` initially compared receipt attempts across all task slots and observed `[1, 1, 3]`. A targeted diagnostic captured exact rows: `[('tests', 1, 'r-tests-1', 'TestRun'), ('__supervisor__', 1, 'sup-T1-1', 'Documentation'), ('tests', 3, 'receipt-after-effects-resolved', 'TestRun')]`. The middle row was the distinct supervisor Documentation receipt, not a duplicate. The test now asserts the `tests`/`TestRun` slot only and verifies attempt 3 links to the actual attempt 1 receipt digest.
2. `tests/vst/test_s2_persistent_runner_service.py::test_execution_gap_rejects_reserved_predecessor_and_untrusted_gate_gap_evidence` used a stale one-argument private predicate call and obsolete `verified_no_execution_attempts` gate argument. The test now passes both previous and successor attempts to `_runner_receipt_gap_is_eligible_locked` and supplies `verified_successor_attempts`; it asserts Store rejects caller-supplied evidence with the current contract error.

After these test-only corrections, the complete persistent module and all required prior E1/E2/E6 selectors passed as listed above. The predicate behavior specifically exercised in the added tests distinguishes the approved signed `EFFECTS_RESOLVED` and authenticated pre-spawn `NO_EXECUTION` paths from unresolved reserved claims and forged caller-provided gate evidence. Receipt continuity assertions compare against `contracts.receipt_sha256(first_receipt)` from the actual Store receipt body.

## Limits and remaining evidence

These are focused in-memory Store, fake-clock, and RPC unit-path tests. They do not establish live Windows/POSIX/systemd execution, real peer credentials/PIDFD/cgroup identity, installed service behavior, crash/process behavior, policy-selector behavior, or operator provisioning. Such scenarios were intentionally not run under this assignment. No production or system mutation occurred.
