# S2 E2E and platform test evidence

> **Preliminary only; does not satisfy S2 verification.** These runs occurred before the implementation/D1-fix commit `3af18a1bc7f87ba9f31cd86e98888f2aecf58922` and before the root coordinator's instruction to hold test execution until tests are committed. They are retained as provenance; the required committed-head epic and final runs remain outstanding. The current test files now also include explicit E4 and E8 `NOT_RUN` denominator cases that were not part of the run below.

## Scope and provenance

- Test owner/executor: Codex E2E runner for `tests/vst/test_s2_runner_lifecycle.py`, `tests/vst/test_s2_store_lifecycle.py`, and `tests/vst/test_s2_sandbox_probe.py`.
- Accountable task owner: operator. No canonical technical owner for host sandbox provisioning is established in this repository (`docs/sdlc/STATE.md`, blocker entry).
- Repository: `D:\Repo\Virtual_scrum_team`.
- Exact Git HEAD observed before and after runs: `b2b168e71000323443882988cd24af2cdbabf4df`.
- Runtime: Windows (`os.name == "nt"`), `C:\Python314\python.exe`, Python 3.14, pytest.
- The working tree was dirty during execution. `tools/vst/contracts.py` was modified by another concurrent activity (origin not verified); the five `test_s2_*.py` files were untracked. Results therefore apply to the observed working tree, not to the bare HEAD. The two other untracked S2 test files were authored outside this E2E ownership and were included in the focused S2 set.
- No tests were run against a real WSL/VM sandbox. No process was killed and no mutation/kill-table suite was invoked.

## Commands and execution record

Focused complete S2 set:

```powershell
C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py
```

The complete set was run after E2, E3, E4, E5, E7, E8 epic batches and once as the final run. First run: `13 failed, 24 passed, 2 skipped` (failures in independent S2 contract/diff-gate tests and Windows anchor setup). After the local bare-remote and platform-scoping test corrections: E2 `3 failed, 36 passed, 5 skipped`; E3 `3 failed, 36 passed, 5 skipped`; E4 `3 failed, 36 passed, 5 skipped`; E5 `39 passed, 5 skipped`; E7 `39 passed, 5 skipped`; E8 `39 passed, 5 skipped`; final `39 passed, 5 skipped`. The three contract-parser failures disappeared during the sequence as `tools/vst/contracts.py` changed in the dirty tree; no attribution to a particular author is verified.

Final detailed command:

```powershell
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py
```

Final result: exit 0; **39 passed, 5 skipped, 1 warning** in 3.72 seconds. The warning is a `pytest_asyncio` deprecation warning for `asyncio.get_event_loop_policy` in the plugin. `pytest --collect-only -q -p no:cacheprovider` collected 44 tests. The five skips are listed below and count as `NOT_RUN`, never PASS.

## Exact collected test IDs

```text
tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin[<lambda>0]
tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin[<lambda>1]
tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin[<lambda>2]
tests/vst/test_s2_contract_gate.py::test_v2_manifest_rejects_missing_or_untrusted_mandatory_parser_pin[<lambda>3]
tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation
tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key
tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping[wrong_key]
tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping[stale_version]
tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping[digest_mismatch]
tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping[duplicate_principal]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection[FAIL]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection[MODIFY]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection[NO_GO]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection[PASS]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results[NOT_RUN]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results[INCONCLUSIVE]
tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results[BLOCKED]
tests/vst/test_s2_diffgate.py::test_allowed_change_passes_with_stable_digest_and_normalized_order
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[.github/workflows/ci.yml]
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[.husky/pre-commit]
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[hooks/pre-commit]
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[package-lock.json]
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[vendor.lock]
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[setup.py]
tests/vst/test_s2_diffgate.py::test_blocked_file_classes_fail_even_when_other_paths_are_allowed[install.ps1]
tests/vst/test_s2_diffgate.py::test_escaping_or_ambiguous_paths_are_rejected[../secret]
tests/vst/test_s2_diffgate.py::test_escaping_or_ambiguous_paths_are_rejected[src//app.py]
tests/vst/test_s2_diffgate.py::test_escaping_or_ambiguous_paths_are_rejected[/etc/passwd]
tests/vst/test_s2_diffgate.py::test_escaping_or_ambiguous_paths_are_rejected[C:/outside]
tests/vst/test_s2_diffgate.py::test_path_outside_manifest_scope_fails
tests/vst/test_s2_diffgate.py::test_rename_from_allowed_file_into_blocked_hook_fails
tests/vst/test_s2_diffgate.py::test_symlink_change_fails_even_when_target_path_is_allowed
tests/vst/test_s2_diffgate.py::test_diff_evidence_is_bound_to_manifest_and_candidate_head
tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs
tests/vst/test_s2_runner_lifecycle.py::test_breaker_blocks_start_until_distinct_manual_override
tests/vst/test_s2_runner_lifecycle.py::test_idempotent_push_and_pull_request_use_local_bare_remote
tests/vst/test_s2_runner_lifecycle.py::test_posix_worker_cannot_read_signer_or_key_file
tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork
tests/vst/test_s2_store_lifecycle.py::test_external_anchor_detects_restored_older_database_and_locks_writes
tests/vst/test_s2_store_lifecycle.py::test_sandbox_mode_requires_anchor_and_supervisor_reconciliation_key
tests/vst/test_s2_store_lifecycle.py::test_exactly_one_event_ahead_is_recovered_before_mutation
tests/vst/test_s2_sandbox_probe.py::test_probe_verification_binds_signature_run_spec_nonce_and_every_check
tests/vst/test_s2_sandbox_probe.py::test_sign_inventory_rejects_incomplete_or_extra_contract_fields
tests/vst/test_s2_sandbox_probe.py::test_real_sandbox_inventory_has_all_required_properties
```

## NOT_RUN platform scenarios

| Scenario | State | Evidence and reason | Required action / owner |
|---|---|---|---|
| Worker process identity cannot read signer key or reach signer IPC | `NOT_RUN` | Windows host; acceptance requires a provisioned POSIX sandbox and real distinct OS identity. Test skip at `test_s2_runner_lifecycle.py:104`. | Provision sandbox; accountable owner: operator; technical provisioning owner is unknown. |
| External anchor POSIX permissions/locking | `NOT_RUN` | Windows host; POSIX file mode and lock semantics are not established by this run. Test skip at `test_s2_store_lifecycle.py:17`. | Run on provisioned POSIX sandbox. |
| Restored older database is rejected by external anchor | `NOT_RUN` | Same POSIX anchor dependency; test skip at `test_s2_store_lifecycle.py:32`. | Run on provisioned POSIX sandbox. |
| Interrupted one-event anchor recovery | `NOT_RUN` | Same POSIX anchor dependency; test skip at `test_s2_store_lifecycle.py:54`. | Run on provisioned POSIX sandbox. |
| Actual WSL/VM inventory, mount/interop state, sockets and egress probes | `NOT_RUN` | No provisioned WSL/VM sandbox; a synthetic inventory cannot prove isolation. Test skip at `test_s2_sandbox_probe.py:50`. | Provision sandbox and run the probe. |
| Mutation, process-kill, and kill-table suites | `NOT_RUN` | Explicit continuation prohibition; no process was killed and those suites were not invoked. | No action in this test assignment; prohibition must be lifted by operator before execution. |

## Acceptance matrix

| Criterion | State | Evidence / remaining acceptance | Dependency and recommended next action |
|---|---|---|---|
| E2, runner and signer boundary | Partial | Local runner lifecycle and synthetic supervisor behavior passed; worker OS identity/key/IPC separation is `NOT_RUN`. The current `test_s2_runner_lifecycle.py` does not prove signer IPC isolation on Windows. | Operator provisions POSIX sandbox; rerun platform case. |
| E3, external rollback anchor | Partial | Anchor semantics and database recovery scenarios were authored, but all three platform-specific scenarios are `NOT_RUN` on Windows. Sandbox-mode configuration rejection passed. | Run POSIX external-anchor cases after provisioning. |
| E4, platform process containment | `NOT_RUN` | POSIX process-group, descendant cleanup and key permission checks need sandbox. Windows parent Job Object nesting and kill-table tests were prohibited/not executed. | Platform-owner evidence required; owner for host provisioning unknown. |
| E5, sandbox specification and probe | Partial | Probe signature/schema binding and each of seven check booleans reject unsafe/tampered evidence; actual host inventory and egress are `NOT_RUN`. | Operator provisions WSL/VM; run actual probe against `docs/SANDBOX_SPEC.md`. |
| E7, lifecycle | Partial | Transition table, breaker/manual override, idempotent simulated push/PR against a local bare remote passed. Restart reconciliation, receipt operation idempotency and complete crash/resume lifecycle are outside these three files. | Functional test owner to close missing acceptance coverage; root coordinates test mapping. |
| E8, isolated worker bake-off | `NOT_RUN` | Actual sandboxed crash/resume bake-off was not executed. Existing run verifies a local bare remote idempotency primitive only and does not claim an isolated worker comparison. | Operator authorization/provisioning and dedicated E8 scenario required. |

No product failure is confirmed by this final passing run. Earlier failures from the first/intermediate working-tree states are recorded in the execution history above; because production `contracts.py` changed during the shared run, their resolution provenance is not verified here.
