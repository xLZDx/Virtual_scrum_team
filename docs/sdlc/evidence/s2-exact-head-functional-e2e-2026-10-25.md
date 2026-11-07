# S2 exact repository-head functional and WSL E2E reruns

Date: 2026-10-25

## Functional recovery module

- Test owner/executor: `functional-test-reviewer` (GPT-6 Luna, medium effort).
- Repository: `D:\Repo\Virtual_scrum_team-s2`, branch `s2-isolated-worker-sandbox`.
- HEAD before and after: `c2771b5968afcdd2b027f1c008fc8023fd0e0f12`.
- Environment: Windows NT 10.0.26300.0; PowerShell 7.6.7; Python 3.14.3; pytest 8.4.2.
- Exact command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py`.
- Result: exit 0; 4 passed, 0 failed, 0 skipped; 0.57 seconds. One pytest-asyncio deprecation warning for `asyncio.get_event_loop_policy`, scheduled for removal in Python 3.16.
- Mapping: E7, VST-017 operation-intent idempotency/timeout recovery/replay; VST-018 signed manual-override replay protection; VST-019 restart behavior.

## WSL runner/probe and Store lifecycle E2E modules

- Test owner/executor: `e2e-runner` (GPT-6 Luna, medium effort).
- Repository commit under test: `c2771b5968afcdd2b027f1c008fc8023fd0e0f12`.
- Source staging: `git archive HEAD` copied the committed runner/probe modules, Store lifecycle module, and `docs/SANDBOX_SPEC.md` into the project-designated WSL staging directory `/opt/vst-s2/source-c2771b`. The agent verified the Git blob hashes against repository HEAD for those files.
- Environment: Ubuntu 24.04.5 LTS on WSL2; kernel `6.6.114.1-microsoft-standard-WSL2`; systemd `255.4-1ubuntu8.17`; Python 3.12.3; pytest 7.4.4.
- Runner/probe command: `/usr/bin/python3 -m pytest -q -rs -p no:cacheprovider -k 'not test_signer_rejects_malformed_signing_evidence' tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_sandbox_probe.py`.
- Runner/probe result: 86 passed, 11 skipped, 4 deselected, 0 failed, 4.68 seconds. Deselects were the malformed-signing-evidence mutation parameters. Skips were the existing four E4 containment, one actual inventory probe, and six E8 cases, all retained as NOT_RUN.
- Store lifecycle command: `/usr/bin/python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_store_lifecycle.py`.
- Store lifecycle result: 19 passed, 0 skipped, 0 failed, 1.07 seconds, executed as `vst-runner` in the bounded/private `systemd-run` unit.
- E3/VST-012 mapping within that complete module: the POSIX-only decorators were inactive in WSL, and the complete 19-pass/0-skip result includes `test_anchor_compare_append_is_idempotent_and_rejects_same_count_fork`, `test_external_anchor_detects_restored_older_database_and_locks_writes`, `test_exactly_one_event_ahead_is_recovered_before_mutation`, `test_multi_event_transaction_recovers_suffix_after_one_checkpoint_append`, and all five `test_invalid_external_anchor_suffix_fails_closed[...]` parameters (`external_anchor_ahead_of_database`, `external_anchor_missing_for_nonempty_database`, `forked_checkpoint_suffix`, `malformed_checkpoint_suffix`, `tampered_checkpoint_suffix`). The agent confirmed the staged test module's Git blob matched exact HEAD. The summary output did not preserve separate per-node results, so the evidence is the whole-module no-skip/no-fail result plus committed source mapping.
- No warnings or failures. The agent made no repository edits or commits; the source staging directory is retained.

## Limits

These exact-commit reruns cover the mapped local functional and permitted E2E cases, including nine POSIX-only external-anchor scenarios in the WSL Store module. They do not establish the missing run-bound environment/workspace linkage or OS memory/temp/process quotas; they do not exercise actual inventory during this run, prohibited process-kill/kill-table/mutation cases, Windows Job Object nesting, or the complete E8 crash/resume bake-off. Existing skipped cases remain `NOT_RUN`; four mutation parameters were explicitly deselected.
