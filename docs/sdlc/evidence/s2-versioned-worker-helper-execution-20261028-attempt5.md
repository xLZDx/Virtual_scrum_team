# S2 versioned worker-helper focused test execution — attempt 5

## Provenance

- Repository: canonical `Virtual_scrum_team` checkout.
- Exact committed HEAD: `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- Tracked worktree and index were clean before and after execution.
- Only untracked path was the protected pre-existing
  `docs/sdlc/evidence/s2-functional-test-run.md`; its SHA-256 remained
  `1273679ac992268bb6faac4ac002edcede5d884a7470325314d181e67f6b6b08` and it
  was not changed or staged.
- Interpreter: CPython 3.14.3 (`C:\Python314\python.exe`).

## Exact execution

```text
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py tests/vst/test_s2_runner_lifecycle.py
```

Result: **179 passed, 0 failed, 6 skipped**, 1 pytest-asyncio deprecation
warning, exit code 0, elapsed 77.53 seconds. Total collected: 185 cases.

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

All 179 selected cases passed at the exact committed S2 helper change. Six
platform-conditional cases remain skipped and do not count as passes. The run
reported one `pytest-asyncio` deprecation warning. No WSL install/runtime,
effective-egress, systemd service, or Windows process containment behavior was
exercised by these two modules.

The source/tests are exact-head tested. Separate E2E system evidence, specialist
reviews and the exact-head GPT-PM sprint gate are still required before any
claim of S2 closure or delivery.
