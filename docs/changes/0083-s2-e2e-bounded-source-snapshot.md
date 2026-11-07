# 0083 S2 bounded source snapshot E2E regressions

## Scope

Added focused E2E coverage in `tests/vst/test_s2_runner_lifecycle.py` for the source snapshot and bounded object-import follow-up: hook-free publication of a source-only commit, fixed pack settings and child environment, snapshot isolation, rejection of source object alternates, bounded source preflight rejection before object writers, target cumulative-storage preflight, branch and pull-request conflicts, durable `IN_PROGRESS`/`POISONED` refusal before object writes, normal cross-process lock release, and safe Popen-boundary timeout/restart retry.

## Verification

- Initial diagnostic source HEAD: `ed531264d0344c67e948e126c420e60f5272226c`. The Windows modules reported 77 passed, 14 skipped, 3 failed, 1 warning, exit 1. The three publication failures shared the Windows source snapshot identity guard and are preserved as historical evidence; they were not relabeled or repeated on that same revision.
- Final source HEAD: `dc95915018b80f498d5cf775363712fb915fe04e`. Repository HEAD at final Windows run: the same `dc95915018b80f498d5cf775363712fb915fe04e`; a source diff check (`git diff --exit-code dc959... -- tools/vst`) returned no source changes.
- Exact Windows command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`.
- Windows environment: Python 3.14.3, pytest 8.4.2, Windows 11 build 10.0.26300-SP0. Result: exit 0; 80 passed, 14 skipped, 1 pytest-asyncio deprecation warning; 94 total, 160.40 seconds.
- Exact selected WSL command and matched file SHA values are in `docs/sdlc/evidence/s2-e2e-bounded-snapshot-ed531.md`. WSL result: exit 0; 1 POSIX `flock` contention/release test passed in 2.23 seconds under `vst-runner` UID 997, Ubuntu-24.04, Python 3.12.3, pytest 7.4.4.
- The prior 0079 evidence remains historical for source HEAD `1ef3fee` and is not replaced by this record.
- 14 skips are not passes. Process-kill, `os._exit()`, kill-table, live child termination, and post-start overflow cleanup remain `NOT_RUN`.

## Workflow and ownership

- Accountable task owner: operator by delegated assignment. Test author/executor: Codex E2E runner (`gpt-6-luna`, medium effort).
- No production source was edited by this test agent.
- The unrelated S3 plan edit and untracked functional evidence are preserved outside this change.
- Source record 0081 separately notes an accidental source-phase `git diff --check` with no recorded exit status. It is not verification evidence; this E2E task did not run that check.

## Acceptance state

The new falsifying cases and WSL lock scenario are runtime-exercised as described. Windows publication/snapshot acceptance passes on source HEAD `dc959`. The `ed531` red result remains diagnostic history. Fourteen platform skips are not passes; actual process termination, kill-table behavior, and overflow cleanup remain `NOT_RUN`. This commit records tests and evidence only; product source changes are in the source commit, not this E2E change.
