# Change record 0014: S1 test-phase defect fixes

## What changed
- `tools/vst/runner.py`: (1) a missing or invalid cwd, a missing executable, a permission error and any other `OSError` while starting a process now record `exit_code` -2 (`FileNotFoundError`, `NotADirectoryError`, `PermissionError` caught explicitly, other `OSError` too; `TimeoutExpired` stays -1; non-OSError exceptions propagate). (2) New `_validate_inputs`: every receipt-level input is validated and `ContractError` is raised BEFORE any subprocess starts; a nonexistent cwd is not a validation error. (3) `run_and_sign` has a new REQUIRED keyword `artifact_paths: list[str]` (may be empty); artifacts are hashed after the commands ran (relative to cwd) into `artifact_digests`; an unreadable artifact gets the all-zero digest `MISSING_ARTIFACT_DIGEST`.
- `tools/vst/contracts.py`: TestRun receipts carry a REQUIRED `artifact_digests` field (dict, non-empty str path -> 64-hex sha256, may be empty), validated; new constant `MISSING_ARTIFACT_DIGEST`; `derive_result` for TestRun returns FAIL when any digest is all zeros (checked first).
- `tools/vst/gate.py`: `evaluate(..., waiver=None, artifact_resolver=None)`. When a resolver is given, each (path, digest) of every otherwise-valid TestRun receipt must equal `artifact_resolver(path)`; otherwise a hard reason naming the receipt id and path is added and the receipt is invalid. With None, artifacts are not re-checked. All other rules unchanged.
- `tools/vst/slice.py`: synthetic TestRun receipts get `artifact_digests: {}`.
- `tools/vst/schemas/README.md`: field, derive rule, runner behaviour, artifact binding and a "Known limits" list (event-chain tail truncation undetectable; gate reviewer==author check is defence in depth; HMAC proves origin within the machine trust boundary, not honesty of the run).

## Why
S1 E1-E4 test run (`docs/sdlc/evidence/s1-e1-e4-test-run.md`): `test_missing_cwd_records_exit_minus_two` failed because Windows raises `NotADirectoryError` for a missing cwd; runner validated fields only after running commands; plan E4 acceptance "modified artifact rejected" had no code path (no artifact binding in the receipt or the gate).

## Affected contracts and paths
Contract change: TestRun receipt gains the required field `artifact_digests` (existing stored or hand-built TestRun receipts without it are now invalid). API change: `run_and_sign` requires `artifact_paths`; `gate.evaluate` has an optional `artifact_resolver`. Paths: `tools/vst/runner.py`, `contracts.py`, `gate.py`, `slice.py`, `schemas/README.md`. `store.py` needed no change. Standard library only.

## Verification state
Code changed only. Tests were NOT rerun by design: the test agents must update `tests/vst` (helpers that build TestRun receipts need `artifact_digests`; `run_and_sign` callers need `artifact_paths`) and rerun them. Not independently reviewed.
