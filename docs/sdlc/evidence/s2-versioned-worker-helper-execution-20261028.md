# S2 versioned worker-helper focused test execution

## Provenance

- Repository: canonical `Virtual_scrum_team` checkout.
- Git HEAD: `9a5c41de5ce2878558402665eafaa0a80c09d177`.
- Worktree: dirty; source and test changes were uncommitted at execution time.
- Interpreter: CPython 3.14.3 (`C:\Python314\python.exe`).
- Test-author specification: `s2-versioned-worker-helper-functional-20261028.md`.
- The protected pre-existing untracked `s2-functional-test-run.md` was not
  changed or staged.

## Exact execution

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py
```

Result: **173 passed, 6 failed, 6 skipped**, 1 pytest-asyncio deprecation
warning, exit code 1, elapsed 66.67 seconds. Total collected: 185 cases.

SHA-256 at execution:

- `tests/vst/test_s2_persistent_runner_service.py`:
  `294cceba6a9b194fff1ff0242197443ea393e71e67563abfd1c4ed994b241e22`
- `tests/vst/test_s2_runner_lifecycle.py`:
  `1a24be32dce7f1d75934a6b0a68a8ff8f03a6d8c734583dfce22bb5c7b26fc`
- `tools/vst/runner.py`:
  `02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecb545e7e67eb902a07ee`
- `tools/vst/runner_service.py`:
  `729e62edbc5e011f3d7294d754b6b34adfc0256802879ba263604c36150b76c4`

## Failures and disposition

1. Three parameters of
   `test_versioned_worker_helper_rejects_unbound_path_before_filesystem`
   failed only because the expected-message regular expression says
   `not bound to the exact-version path`, while the implementation raises
   `worker helper path is not the configured exact-version path`. The
   rejection occurs before filesystem access. Classification: **test defect**;
   the test owner should match the existing precise contract message.
2. `test_posix_stale_cgroup_reconciliation_removes_only_owned_scope` and
   `test_posix_stale_cgroup_reconciliation_refuses_unconfirmed_cleanup` failed
   because their temporary directory fixtures lack the kernel cgroup files
   `cgroup.events` and `cgroup.procs`; the observed missing path was under the
   Windows pytest temp directory. No real cgroup was created, inspected, or
   killed. Classification: **test fixture/platform defect**; the test owner
   must supply deterministic pseudo-file contents or run an appropriate
   platform fixture.
3. `test_run_manifest_commands_stops_after_incomplete_cleanup_and_records_later_command_not_run`
   failed before reaching the mocked process launch because it called
   `run_manifest_commands` without a valid `ExecutionAuthority`, rejected by
   the existing production guard. Classification: **stale test fixture**; the
   test owner must provide the authorized fixture or recast the test around
   the service boundary.

No failure was repeated, so none is classified as a flake. The six skips are
the collected platform-conditional cases; they remain skipped and do not count
as passes. No source files were edited by the execution role.

## Next action

Owner: functional-test-reviewer. Fix the three test-fixture/assertion defects
without weakening assertions, then rerun the same exact two-module command.
After those results, decide whether the two POSIX pseudo-cgroup cases should be
covered by a real WSL fixture or remain platform-specific with an explicit
reason. Do not claim the focused helper gate as passing until the rerun is
green; this execution is not WSL installation or runtime proof.
