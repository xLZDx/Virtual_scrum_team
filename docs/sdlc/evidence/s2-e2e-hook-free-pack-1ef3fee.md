# S2 hook-free Git pack publication E2E evidence

## Revision and ownership

- Source code under test: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Windows test invocation began with repository HEAD `1ef3fee07d5743dc8e42c632e1dc3100601116a7`. The functional reviewer committed record 0078 while the Windows suite was running; the repository HEAD later became `060a7dc938b9b55ed9654356c268bf742d391adb`. The `tools/vst` source tree matched source HEAD `1ef3fee` at the later check, and no production source file was modified by this E2E task.
- Accountable task owner: operator, by delegated task. Executor/test author: Codex E2E runner (`gpt-6-luna`, medium effort).
- The POSIX test copy was created from the same workspace. At copy time repository HEAD was `060a7dc`; `git diff --exit-code 1ef3fee..060a7dc -- tools/vst` reported no source difference.

## Windows focused E2E modules

- Exact command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Source HEAD printed immediately before the command: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Environment: Python 3.14.3; pytest 8.4.2; Windows 11 build 10.0.26300-SP0.
- Result: exit 0; 76 passed, 14 skipped, 1 pytest-asyncio `get_event_loop_policy` deprecation warning; 90 total cases. Pytest reported 150.80 seconds.
- New E2E IDs passed:
  - `test_hook_free_publication_transfers_source_only_commit_without_running_pre_push`
  - `test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs`
  - `test_cumulative_target_storage_cap_rejects_before_pack_process_starts`
  - `test_target_storage_lock_times_out_on_another_process_then_releases_normally`
  - `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`
- Existing callback and local Git idempotency coverage also passed: `test_external_backend_callback_runs_outside_store_anchor_transaction` and `test_idempotent_push_and_pull_request_use_local_bare_remote`.

## Security and resource assertions

- The hook test first uses a disposable ordinary local `git push` as a positive control; its source-controlled pre-push hook writes a marker. It then removes the marker, invokes the supervisor-only synthetic backend for a candidate commit that exists only in the source repository, and asserts the marker remains absent while the commit and target ref appear in the bare target.
- The source repository's local Git config is deliberately set to high pack thread/window/cache values. The test captures the source `pack-objects` process command and environment, checks the fixed low resource options, and checks that hostile `GIT_CONFIG_COUNT` variables are absent from the child environment.
- Branch tests accept a fast-forward and reject a divergent update without changing the target branch. Pull-request tests verify same-key replay, changed-payload rejection, and rejection of a pre-existing PR ref that points at a different commit.
- The cumulative storage test pre-populates the operation key, sets a tiny remaining object-store budget, calls public `push`, and guards `Popen` to prove the cumulative preflight rejects before any `pack-objects` or `index-pack` child starts. The post-import overflow cleanup path is intentionally not exercised.
- The timeout test injects `subprocess.TimeoutExpired` before `Popen` creates a child, checks that Store persists `PENDING` plus the unresolved event, restarts Store, and retries with the same key/payload. The test does not invoke or test `process.kill()`.
- The cross-process lock test starts a small lock-holder child, waits until it has acquired the actual lock file, verifies the backend times out while contended, then sends the child's normal stdin release and waits for exit code 0. No process is forcibly terminated.

## POSIX `flock` verification in selected WSL2

- Distro: selected `Ubuntu-24.04`; Python 3.12.3, pytest 7.4.4, Linux kernel `6.6.114.1-microsoft-standard-WSL2-x86_64`.
- The account's configured shell prevents direct `wsl --user vst-runner` launch (`CreateProcessCommon: chdir(/nonexistent) failed`; `This account is currently not available`). The test process was instead launched via `setpriv` as the actual `vst-runner` user, UID 997, with groups `[987, 988]`; it was not run as root. A short identity check printed UID 997 against the provisioned `vst-runner` UID 997.
- A disposable copy was transferred to `/tmp/vst-s2-e2e-1ef3fee-posix`, owned by `vst-runner`. The Windows and WSL SHA-256 values matched for `tools/vst/slice.py` (`8bc428df670beaf46e2be1b1391b14bd602f4c0c8c9b8ea6e7d2e3a2fe6bb1d1`) and `tests/vst/test_s2_runner_lifecycle.py` (`469ade9bc9a38b8e7001e6f9dab059f2b7d58f815df08c1e12a0f951e56036ab`).
- Exact successful command:
  `wsl.exe -d Ubuntu-24.04 --user root -- bash -lc "cd /tmp/vst-s2-e2e-1ef3fee-posix && exec setpriv --reuid=vst-runner --regid=vst-runner --init-groups -- env PYTHONPATH=/tmp/vst-s2-e2e-1ef3fee-posix python3 -m pytest -q -c /dev/null --rootdir=/tmp/vst-s2-e2e-1ef3fee-posix -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_target_storage_lock_times_out_on_another_process_then_releases_normally"`
- Result: exit 0; 1 passed in 1.24 seconds. This specifically exercised POSIX `fcntl.flock` contention and normal release.
- One earlier attempt printed the test pass marker but pytest exited 1 during teardown because it tried to chdir back to inherited `/root`, which `vst-runner` cannot access. The corrected command changes to the runner-owned temporary project directory before `setpriv`; this supersedes the harness failure.
- A separate direct `runuser` pytest version check from `/root` failed because pytest searched unreadable `/root/pytest.ini`; no test was executed by that command.

## Skips and explicit NOT_RUN scope

- The 14 Windows skips are: 9 POSIX anchor permission/recovery/failure-state cases; 1 POSIX worker identity/key/Unix-socket case; and 4 E4 process-containment cases (POSIX process-group cleanup, post-exit descendants, worker key permissions, and nested Windows Job Object runtime proof).
- `NOT_RUN`: any overflow detected only after pack/import starts, including its process cleanup path that may call `process.kill()`; real child termination after a live timeout; process-kill and kill-table suites; and full E4 process-containment acceptance.
- The cumulative storage test proves preflight rejection before child launch, not post-launch overflow cleanup. The timeout test injects at Popen before launch and does not claim process termination behavior.

## Historical results and classification

- Source HEAD `202e0680e8e1b4fb30dcbe9659bf550d06443d90`: the first full module run reported 73 passed, 14 skipped, 1 failed. The failure was a test defect: the expected PR-key conflict text did not match the backend's `remote idempotency key reused with different payload`. The assertion was corrected without weakening it.
- An intermediate run on repository HEAD `8eb7f40040f4c05d4cea04529469a531d5309fbe` completed 74 passed, 14 skipped, 1 warning. It predates the final cumulative-storage source commit and is diagnostic, not final acceptance.
- Final Windows and POSIX results are the exact-source runs above. Earlier red results are not called flakes.

## Conclusion

Hook-free source-backed object transfer, config/environment pinning, fast-forward and conflict handling, cumulative-cap preflight, and safe pending/restart retry pass on source HEAD `1ef3fee`. Windows lock behavior passes in the full run; POSIX `flock` contention passes in selected WSL2 under the real `vst-runner` identity. Overflow cleanup and process-kill acceptance remain `NOT_RUN`.
