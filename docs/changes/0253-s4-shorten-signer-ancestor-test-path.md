# Change 0253: Shorten the signer ancestor regression socket path

## What changed

- Shortened the non-sticky world-writable ancestor regression fixture to `tmp_path/u/r/s` while preserving the runner-owned intermediate child and the unsafe ancestor.
- The test binds the Unix socket directly at the short path so it reaches the signer guard rather than exceeding the platform socket pathname limit.

## Why

The first exact-head run at `e7f857f` executed ten focused selectors: nine passed, while the new ancestor regression failed before invoking product code because its nested `AF_UNIX` socket path exceeded the platform limit. The unit returned exit 1; the failure was in test setup. The fixture now keeps the unsafe world-writable directory as an intermediate ancestor and uses short names, so the intended guard assertion can execute.

## Decisions and ownership

- Keep the test focused on the intermediate-parent threat, not merely a writable immediate socket parent.
- Do not interpret the fixture setup error as a product guard failure.
- Test owner and executor: `e2e-runner` (GPT-6 Luna, medium effort). Accountable task owner: operator. Coordinator: Codex.

## Affected contracts and paths

- Signer ancestor mode regression in `tests/qa/test_s4_worker_boundary_contracts.py`.
- Source implementation remains in `tools/vst/sandbox.py` at code commit `b96d78b`.

## Verification state

- First snapshot source/test HEAD: `e7f857fd44a5d8747fac50195beacd74a21aa604`.
- Failed focused unit: `vst-s4-boundary-ancestor-e7.service`, invocation `d607892bc38e43c792fc925b56af03a9`; 9 passed, 1 test-fixture failure before the signer guard due `AF_UNIX path too long`.
- The corrected test has not been executed. Required next step: fresh exact-head WSL snapshot and rerun all ten focused selectors. If green, run the functional CLI at the same exact head.
