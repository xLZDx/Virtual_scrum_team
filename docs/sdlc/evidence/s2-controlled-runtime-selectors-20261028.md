# S2 controlled runtime selectors — 2026-10-28

## Authorization and source identity

GPT-PM controlled-test decision: request `a94486c9-f8e2-451e-91d2-4adb1799b8d6`, reply `85eba0d2-3670-5274-a787-58012255f22b`, job `3ff013cd-f5e4-441e-98c5-8c823f62a96f`. It authorizes the listed controlled selectors only, keeps `S2-DISPATCH-M01` MAJOR/OPEN, and does not authorize a new authority, production activation, real credentials, or E5 fabrication.

Test source revision: `d5001797cb94113efd9a8dc26e4a15f2dc130976`. Repository HEAD during runs: `a94486c9f8e2051e01d2ad2adb1799b8d238ace5`; the source revision is an ancestor; intervening HEAD changes are documentation only, with no test or executable source changes. The WSL archive was streamed from this exact Git revision and its source/test file hashes were checked against Git before tests. No development worktree or clone was created.

## Windows

CPython 3.14.3, `C:\Python314\python.exe`; pytest 8.4.2.

1. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_e4_runner.py::test_timeout_kills_the_whole_process_tree tests/vst/test_e4_runner.py::test_stray_descendant_is_killed_after_the_root_command_exited_normally` — **2 passed**, 0 failed, exit 0, 12.47 s. This is focused test-created process cleanup evidence; production service behavior remains unproven.
2. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_v2_waiver_scope_never_includes_failure_or_review_rejection tests/vst/test_s2_contract_gate.py::test_v2_waiver_allows_only_named_non_execution_results` — **7 passed**, 0 failed, exit 0, 0.89 s. This is policy-boundary test evidence, not a waiver or approval.

Both runs emitted one `pytest_asyncio` deprecation warning about `asyncio.get_event_loop_policy`.

## WSL controlled selectors

WSL distro `Ubuntu-24.04`; Python 3.12.3; pytest 7.4.4. Existing `/opt/vst-s2/source` had hash mismatches and was not used. A unique disposable archive was extracted to `/tmp/vst-s2-d500-5223c710` and consumed in one WSL invocation because `/tmp` did not persist across separate invocations. No systemd, service, sudo, capability, account, key, credential, or identity provisioning occurred.

1. Six E3 store lifecycle selectors in `tests/vst/test_s2_store_lifecycle.py` (`test_anchor_compare_and_append_is_idempotent`, `test_append_after_non_newline_terminated_log`, `test_detects_restored_older_database`, `test_recovers_exactly_one_event_ahead`, `test_recovers_multi_event_suffix`, `test_invalid_external_anchor_suffix_fails_closed`): `python3 -m pytest -q -rs -p no:cacheprovider --basetemp=/tmp/vst-s2-qa-store-undefined tests/vst/test_s2_store_lifecycle.py::test_anchor_compare_and_append_is_idempotent tests/vst/test_s2_store_lifecycle.py::test_append_after_non_newline_terminated_log tests/vst/test_s2_store_lifecycle.py::test_detects_restored_older_database tests/vst/test_s2_store_lifecycle.py::test_recovers_exactly_one_event_ahead tests/vst/test_s2_store_lifecycle.py::test_recovers_multi_event_suffix tests/vst/test_s2_store_lifecycle.py::test_invalid_external_anchor_suffix_fails_closed` — **10 passed**, 0 failed, exit 0, 0.88 s (parameterized cases included).
2. Synthetic identity selectors `tests/vst/test_e4_runner.py::test_posix_worker_cannot_read_signer_or_key_file` and `::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture`: `python3 -m pytest -q -rs -p no:cacheprovider --basetemp=/tmp/vst-s2-qa-identity-undefined tests/vst/test_e4_runner.py::test_posix_worker_cannot_read_signer_or_key_file tests/vst/test_e4_runner.py::test_posix_read_only_reviewer_cannot_write_worktree_or_store_fixture` — **2 passed**, 0 failed, exit 0, 1.36 s. Fixtures were synthetic and temporary; no real key/credential was created or used.
3. `tests/vst/test_e4_runner.py::test_runner_drops_uid_change_capabilities_before_worker_command` and `::test_posix_worker_timeout_kills_descendant_across_uid_boundary`: `python3 -m pytest -q -rs -p no:cacheprovider --basetemp=/tmp/vst-s2-qa-runner-undefined tests/vst/test_e4_runner.py::test_runner_drops_uid_change_capabilities_before_worker_command tests/vst/test_e4_runner.py::test_posix_worker_timeout_kills_descendant_across_uid_boundary` — **2 skipped**, 0 failed, exit 0. Skip reason: dedicated runner `AmbientCapabilities=CAP_SETGID,CAP_SETUID` profile absent. Direct existing `vst-runner` had zero effective and ambient caps; no caps were added.

The first WSL harness attempt extracted the archive in one invocation and tried to use it in another. The later invocation could not change directory because `/tmp` was ephemeral; pytest found no tests and exited 4. This was a **harness setup failure**, not a test result. The successful one-invocation archive-and-test run above resolved the harness issue.

## Acceptance limits

Windows E4 test behavior, E3 store recovery, synthetic POSIX identity isolation, and waiver-boundary cases have focused runtime evidence. `VST-013` remains partial because production behavior is not established. POSIX capability-dependent runner behavior is `NOT_RUN` for acceptance due to the skip. No full suite, E5 probe, E8 bake-off, the 53-selector policy family, manifest execution, production dispatch, service activation, persistent runner configuration, real credential, or capability provisioning occurred. `S2-DISPATCH-M01` remains MAJOR/OPEN and S2 remains NOT APPROVED. Operator owns a separate operational capability-profile authorization if those POSIX selectors are required; Codex owns evidence coordination; GPT-PM owns final exact-revision adjudication.
