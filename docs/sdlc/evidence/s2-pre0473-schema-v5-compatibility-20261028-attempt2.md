# S2 pre-0473 schema-v5 recovery-history compatibility attempt 2

## Scope and exact source identity

This report records a focused test-only pass for the exact pre-0473 schema-v5 `PREDECESSOR_GENERATION_STOPPED` event shape with `predecessor_state=PENDING`. The tests write authenticated Store history to a temporary SQLite database, close it, reopen it through a fresh `Store` so startup reconciliation runs, and verify that only a separately authorized successor can proceed. Malformed/mismatched legacy variants are independently re-opened with valid event-chain MACs and must fail closed.

| Field | Value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Branch / committed base HEAD | `s4-canonical-continuation` / `7120e2c647cc95703704905efa76de735ca8d0ec` |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Store source SHA-256 | `e92c4b829a3887cd09dfee88aab808cd5775263e6f42d70cb213777bd1263a68` |
| Test file SHA-256 | `6b9f62d9e9c4d7729bf1e82c7923890ac9a764b56d79f3c015251734f66faff6` |
| Store diff Git object ID | `2c98f1050bc54e193be8c4b6ff88f33f42a1f8a7` |
| Test diff Git object ID | `18a4ed5189ccce46f03c00b78ab78d0132dee44a` |
| Whole-worktree diff Git object ID | `8d98121c20f45d4b0d3a22c2ab0041c20d65a6b4` |
| Other focused test file SHA-256: E1 / E2 / E6 | E1 `aac3b57631b0530ade78c2d0173060f5f6333d8d7f04e5075b3e82ee99656e39`; E2 `fbed70655086bb84f2ba0fc2b203756f3c83778edd49f1d60e1c85f02ec29394`; E6 `10e17cd62d71b7c49bb3fdabc7a873721ecd797ce1f3fa36876f06f6dac499cc` |

Git object IDs above are from `git diff --binary [path] | git hash-object --stdin`; they are not presented as SHA-256. The whole-worktree diff includes concurrent edits to `docs/sdlc/STATE.md` and `tools/qa/install_wsl_runtime.ps1`; this test role did not modify those files. Pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not read or changed. The test role modified no product source.

## Regression nodes and observable contract

| Node ID | State in final focused run | Observable behavior asserted |
|---|---|---|
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` | PASS | Exact legacy seven-field event is stored with schema `user_version=5`; raw event MAC chain and anchor are valid; a newly constructed `Store` completes startup reconciliation and reads the predecessor as `INDETERMINATE`; a successor grant basis is refused before its run-bound preflight is consumed, then a separately preflight-authorized successor can be claimed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[unexpected-legacy-field]` | PASS | Unexpected extra field is rejected after fresh Store startup reconciliation. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[predecessor-mismatch]` | PASS | Event claiming `EXECUTION_RESERVED` when actual predecessor state is `PENDING` fails closed after fresh startup reconciliation. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[grant-mismatch]` | PASS | Wrong grant binding fails closed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[claim-digest-mismatch]` | PASS | Wrong grant payload digest fails closed. |
| `tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields[not-a-successor-generation]` | PASS | Recovery generation equal to the predecessor claim generation fails closed. |

For each malformed/mismatched fixture, the test independently recomputes every event MAC from the genesis hash and verifies the stored anchor count/head before close. The changed legacy field is therefore a semantic mismatch inside an authentic append-only chain, not a broken-chain shortcut.

## Execution attempts

All commands ran from `D:\Repo\Virtual_scrum_team`. Each pytest execution emitted one installed `pytest-asyncio` warning: `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16.

### Before the final Store replay fix

Command:

```text
C:\Python314\python.exe -m pytest -q -rs -x -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_remains_readable_after_0473 tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields
```

Result: **1 failed, 0 passed, 0 skipped; exit 1**. The valid legacy record was readable through claim status, but successor admission failed with `StoreError: prior runner execution 'grant-1' is INDETERMINATE and blocks continuation`. This run stopped under `-x`; no negative cases ran. The intermediate two-pass / predecessor-mismatch failure from the in-memory version is recorded in [attempt 1](s2-pre0473-schema-v5-compatibility-20261028-attempt1.md). Parent then confirmed the source fix should cover validation, startup history replay, and successor state validation.

### After the Store replay fix

1. New regression group:

```text
C:\Python314\python.exe -m pytest -q -rs -x -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields
```

Result: **6 passed, 0 failed, 0 skipped; exit 0**; 1 warning; 0.89s.

2. Full focused persistent runner module:

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py
```

Result: **62 passed, 0 failed, 0 skipped; exit 0**; 1 warning; 1.78s.

3. Approved E1 contract-gate selectors (32 cases):

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence
```

Result: **32 passed, 0 failed, 0 skipped; exit 0**; 1 warning; 0.75s.

4. Approved E2 runner-lifecycle selectors (38 cases):

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority
```

Result: **38 passed, 0 failed, 0 skipped; exit 0**; 1 warning; 6.14s.

5. Approved E6 diff-gate file (22 cases):

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py
```

Result: **22 passed, 0 failed, 0 skipped; exit 0**; 1 warning; 32.15s.

Final approved-group outcome: **154 distinct focused cases passed, 0 failed, 0 skipped** (62 persistent runner + 32 E1 + 38 E2 + 22 E6). The six-node focused command is a repeat of new cases already included in the 62-node module result and is not double-counted.

## Limits

The new legacy-history test uses a temporary local SQLite database and Store's startup reconciliation; it does not invoke process termination, crash semantics, recovery runtime, service installation, systemd, E8, or policy selectors. No check, build, CI, migration, runtime deployment/E2E, commit, or push was run. No commits were created by this test role.
