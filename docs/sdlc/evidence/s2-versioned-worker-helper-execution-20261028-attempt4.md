# S2 versioned worker-helper focused test execution — attempt 4

## Provenance

- Repository: canonical `Virtual_scrum_team` checkout.
- Git HEAD: `9a5c41de5ce2878558402665eafaa0a80c09d177`.
- Worktree: dirty; production and test changes were uncommitted.
- Interpreter: CPython 3.14.3 (`C:\Python314\python.exe`).
- The protected pre-existing `s2-functional-test-run.md` remained untracked and
  untouched.
- Earlier diagnostic attempts and their defects remain recorded in attempts
  1–3; those failures were corrected in test fixtures without source changes.

## Exact execution

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py
```

Result: **179 passed, 0 failed, 6 skipped**, 1 pytest-asyncio deprecation
warning, exit code 0, elapsed 80.78 seconds. Total collected: 185 cases.

SHA-256 at execution:

- `tests/vst/test_s2_persistent_runner_service.py`:
  `efcfce624c6e4e45d8dfb8addad2215707a06ed2662109f3d756ad4b8ace5ee3`
- `tests/vst/test_s2_runner_lifecycle.py`:
  `f4abf50c7558fd7fde805a95ee33e1e9be7e7a185e00ee5f74b621cd601a1d9d`
- `tools/vst/runner.py`:
  `02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecb545e7e67eb902a07ee`
- `tools/vst/runner_service.py`:
  `729e62edbc5e011f3d7294d754b6b34adfc0256802879ba263604c36150b76c4`

## Disposition and limits

The focused two-module run is green for the 179 selected cases on this dirty
Windows base. The six platform-conditional cases were skipped and do not count
as passes; their POSIX-only identity/cgroup behavior still needs the relevant
platform evidence. One `pytest-asyncio` deprecation warning was reported. No
WSL provisioning or helper installation/runtime was performed in this run.

This is diagnostic evidence on a dirty working tree, not an exact committed
head result. After the final source, test, and evidence changes are committed,
the designated test role must rerun this same focused command at the resulting
exact commit and record the new head and hashes. The helper installation and
WSL runtime acceptance remain separate E2E work.
