# S2 bounded source snapshot E2E evidence (diagnostic)

## Correlation and scope

- E2E run IDs: historical diagnostics `S2-E2E-ED531-WIN-20261025-01` and `S2-E2E-ED531-WSL-20261025-01`; final runs `S2-E2E-DC959-WIN-20261025-01` and `S2-E2E-DC959-WSL-20261025-01`.
- Historical source: `ed531264d0344c67e948e126c420e60f5272226c`. Final source under test: `dc95915018b80f498d5cf775363712fb915fe04e`.
- Windows suite began with repository HEAD `ed531264d0344c67e948e126c420e60f5272226c`. The functional reviewer later committed record 0082; the repository HEAD at WSL copy time was `16f25507d530742f9d8c9ebeab3377031bafa1af`. `git diff --exit-code ed531264d0344c67e948e126c420e60f5272226c -- tools/vst` produced no diff.
- Test author/executor: Codex E2E runner (`gpt-6-luna`, medium effort); accountable task owner: operator by delegated task.
- Historical failure below remains diagnostic and is not upgraded to a pass. Final acceptance results for the fixed source follow it. No production code was edited by the E2E agent.

## Windows lifecycle/store run

- Exact command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Environment: Python 3.14.3, pytest 8.4.2, Windows 11 build 10.0.26300-SP0.
- Result: exit 1; 77 passed, 14 skipped, 3 failed; 94 total; 1 `pytest-asyncio` deprecation warning (`asyncio.get_event_loop_policy`); 186.60 seconds.
- Failed IDs: `test_hook_free_publication_transfers_source_only_commit_without_running_pre_push`, `test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs`, `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`.
- All three fail at the same product guard in `tools/vst/slice.py::_copy_source_object_file`, line 1473:
  `RuntimeError: synthetic source object file changed during snapshot`
  The guard compares `DirEntry.stat(follow_symlinks=False)` with `os.fstat(fd)` (`st_dev`, `st_ino`, `st_size`). The traceback shows the comparison evaluated false on Windows but does not print the individual values. The failures happen while copying source objects into the sanitized snapshot, before `pack-objects` or `index-pack` starts. Classification: product/platform compatibility defect candidate, not an assertion mismatch and not established as a flake. No repeat was run pending source remediation.
- Newly added alternates rejection, bounded source object-count preflight, and both durable journal refusal cases passed in this Windows run. Existing target cumulative-cap preflight, ref conflict, normal lock release, and unrelated lifecycle/store cases passed as included in the 77 passing cases.
- The 14 skips remain skips and do not count as passes: nine POSIX-only anchor cases, one POSIX worker identity/key/socket case, and four platform containment cases (POSIX process-group cleanup, post-exit descendants, worker-key permission boundary, and Windows Job Object runtime proof). Process-kill/kill-table and actual overflow cleanup remain explicitly `NOT_RUN`.

## Final Windows lifecycle/store run after source fix

- Exact source HEAD: `dc95915018b80f498d5cf775363712fb915fe04e`; repository HEAD immediately before the command was the same.
- Verified source worktree: `git diff --exit-code dc95915018b80f498d5cf775363712fb915fe04e -- tools/vst` returned no diff.
- Exact command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Environment: Python 3.14.3; pytest 8.4.2; Windows 11 build 10.0.26300-SP0.
- Result: exit 0; 80 passed, 14 skipped, 1 warning; 94 total in 160.40 seconds. The warning was pytest-asyncio's deprecation warning for `asyncio.get_event_loop_policy`.
- The three publication tests that failed on `ed531` now pass: hook-free source-only transfer, branch/PR conflict handling, and timeout/PENDING/restart retry. New source-alternates rejection, bounded source-count preflight, and both `IN_PROGRESS`/`POISONED` journal refusal cases also pass. Pack command resource settings and isolated snapshot environment checks pass. The cumulative target-storage cap rejection, normal cross-process lock release, and other runner/store cases pass.
- The prior `ed531` run remains recorded above as 77 passed, 14 skipped, 3 failed and is historical evidence of the Windows snapshot identity defect.

## POSIX lock scenario in selected WSL2

- Distro: `Ubuntu-24.04`; Python 3.12.3; pytest 7.4.4; test process identity `vst-runner`, UID 997, groups `[987, 988]`.
- Disposable copy: `/tmp/vst-s2-e2e-ed531-posix`. The source and test SHA-256 values in the copy were `tools/vst/slice.py` = `62fdabde2b5408984dd7f4571ad7404206a410188c31a892b1337db023e04fe5`; `tests/vst/test_s2_runner_lifecycle.py` = `765745b3fa46be84f32862a8a306cc4a91188fe2da9b4239a61b2a35390d27a5`.
- Exact command:
  `wsl.exe -d Ubuntu-24.04 --user root -- bash -lc "cd /tmp/vst-s2-e2e-ed531-posix && exec setpriv --reuid=vst-runner --regid=vst-runner --init-groups -- env PYTHONPATH=/tmp/vst-s2-e2e-ed531-posix python3 -m pytest -q -c /dev/null --rootdir=/tmp/vst-s2-e2e-ed531-posix -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_target_storage_lock_times_out_on_another_process_then_releases_normally"`
- Result: exit 0; 1 passed in 2.28 seconds. This exercises POSIX `flock` contention and normal lock release as the actual `vst-runner` identity. It does not test child termination or process cleanup.
- Final source/test copy: `/tmp/vst-s2-e2e-dc959-posix`; Windows source SHA-256 was `c9e652d8be53175ecf1b9b14f2fec2e16aac952e6fae166721ca819ff0a32ae0`, and the test file SHA-256 was `765745b3fa46be84f32862a8a306cc4a91188fe2da9b4239a61b2a35390d27a5`. The WSL copy hashes matched exactly.
- Final exact command:
  `wsl.exe -d Ubuntu-24.04 --user root -- bash -lc "cd /tmp/vst-s2-e2e-dc959-posix && exec setpriv --reuid=vst-runner --regid=vst-runner --init-groups -- env PYTHONPATH=/tmp/vst-s2-e2e-dc959-posix python3 -m pytest -q -c /dev/null --rootdir=/tmp/vst-s2-e2e-dc959-posix -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_target_storage_lock_times_out_on_another_process_then_releases_normally"`
- Final result: exit 0; 1 passed in 2.23 seconds; selected WSL distro Ubuntu-24.04, Python 3.12.3, pytest 7.4.4, process UID 997 (`vst-runner`).

## Safety boundary and next action

- No actual `process.kill()`, `os._exit()`, process-kill/kill-table suite, or overflow cleanup path was exercised. The timeout regression injects at the `Popen` boundary before creating the pack child.
- The earlier source-phase `git diff --check` event is recorded by source change record 0081 as an accidental workflow check with no preserved exit code. It is not test evidence; this E2E run did not execute `git diff --check`.
- Current acceptance: the Windows snapshot identity regression is fixed on `dc959` for the focused lifecycle/store suite, and the POSIX lock scenario passes under the selected WSL runner identity. The old red run remains historical. Process-kill, live child termination, and post-start overflow cleanup remain `NOT_RUN` and are outside this accepted test execution.
