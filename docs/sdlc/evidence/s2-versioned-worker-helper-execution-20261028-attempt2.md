# S2 versioned worker-helper focused test execution — attempt 2

## Provenance

- Repository: canonical `Virtual_scrum_team` checkout.
- Git HEAD: `9a5c41de5ce2878558402665eafaa0a80c09d177`.
- Worktree: dirty; source and test changes were uncommitted at execution time.
- Interpreter: CPython 3.14.3 (`C:\Python314\python.exe`).
- The protected pre-existing untracked `s2-functional-test-run.md` remained
  untracked and untouched.
- Attempt 1 is in `s2-versioned-worker-helper-execution-20261028.md`.

## Exact execution

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py
```

Result: **176 passed, 3 failed, 6 skipped**, 1 pytest-asyncio deprecation
warning, exit code 1, elapsed 67.75 seconds. Total collected: 185 cases.

SHA-256 at execution:

- `tests/vst/test_s2_persistent_runner_service.py`:
  `efcfce624c6e4e45d8dfb8addad2215707a06ed2662109f3d756ad4b8ace5ee3`
- `tests/vst/test_s2_runner_lifecycle.py`:
  `e3c402e480955d445473a0d01cd4dc03d0b4e1bc0e9f17f3529cf5a3d284f29a`
- `tools/vst/runner.py`:
  `02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecb545e7e67eb902a07ee`
- `tools/vst/runner_service.py`:
  `729e62edbc5e011f3d7294d754b6b34adfc0256802879ba263604c36150b76c4`

## Failures and disposition

1. `test_posix_stale_cgroup_reconciliation_removes_only_owned_scope` reached
   the real `os.rmdir` call after reading fake `cgroup.events` and
   `cgroup.procs` files, but Windows reported `WinError 145` because ordinary
   files keep a temporary directory nonempty. Kernel cgroup control files are
   virtual entries and do not behave as ordinary files. Classification:
   **test fixture/platform defect**. Keep assertions and emulate the cgroup
   file reads and `rmdir` boundary rather than using regular files as virtual
   cgroup entries.
2. `test_posix_stale_cgroup_reconciliation_refuses_unconfirmed_cleanup` failed
   for the same ordinary-file/rmdir mismatch. It expected
   `could not be confirmed empty`, while the actual safe refusal was
   `verified empty stale command scope could not be removed`. Classification:
   **test fixture/expectation defect**; inject a failing `rmdir` at the intended
   boundary and assert the resulting non-approval.
3. `test_run_manifest_commands_stops_after_incomplete_cleanup_and_records_later_command_not_run`
   failed during setup because Windows' `os` module has no `geteuid` attribute;
   `monkeypatch.setattr(execution_grant.os, "geteuid", ...)` raised
   `AttributeError` before the test reached the runner. Classification:
   **test fixture/platform defect**; install the POSIX identity shim with an
   explicit absent-attribute allowance or use a controlled module-level shim.

The earlier three path-message assertion failures are fixed and now pass. No
failure was repeated, so none is classified as a flake. Six skips remain
platform-conditional and are not passes. No production source was edited during
this execution.

## Next action

Owner: functional-test-reviewer. Correct these three platform fixture defects
without weakening assertions, then rerun the same exact two-module command.
This Windows run contains no real cgroup or helper execution evidence and is
not WSL installation/runtime proof.
