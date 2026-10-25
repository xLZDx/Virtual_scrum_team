# S3 GPT-PM M01/M02 regression evidence

## Source and test context

- Source commit: `040a3f2af217f38254cf91f2cb0559fb61fe2c80` (`fix(s3): fence commits from hooks and STOP races`).
- The source checkout HEAD did not change during either run. Each test agent ran with its own focused test file modified and uncommitted; the unrelated pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved.
- Both runs used Windows, Python 3.14.3, pytest 8.4.2, and the pinned `C:\Python314\python.exe` interpreter. Each run emitted one pytest-asyncio deprecation warning.

## S3-M01: repository commit hooks

- Owner: `functional-test-reviewer` (GPT-6 Luna, low effort).
- Command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py`
- Result: 9 passed, 0 failed, 0 skipped; 4.11 seconds.
- Test file SHA-256 at run: `5B4E57E3A69F0F23B1B3465D0079B6F81C635DFF6362C07524E973D8AC325D33`.
- The test installs `pre-commit`, `commit-msg`, and `post-commit` hooks in a pytest `tmp_path` Git repository. A direct calibration commit first verifies all three marker writes; after clearing the marker, adapter commit succeeds without running any hook and leaves the candidate's configured `core.hooksPath` unchanged.
- Scope: local synthetic repository hook behavior only; no external candidate or sandbox execution is established.

## S3-M02: STOP and commit ordering

- Owner: `e2e-runner` (GPT-6 Luna, low effort).
- Command: `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_pilot_e2e.py`
- Result: 9 passed, 0 failed, 0 skipped; 17.06 seconds.
- Test file SHA-256 at run: `C8F6271F2E6A36B5F1C7DB6E4A55E8716129173544E735D14A7154E91737EA24`.
- The deterministic STOP-first case pauses at the adapter checkpoint before the publication lock, calls durable `pilot.stop()`, then resumes the stale start. It verifies the response remains non-approving, the candidate HEAD and file remain unchanged, the Store epoch advances, and no verification receipt is created.
- Scope: ordering through one `SyntheticStoryPilot` instance. This does not establish cross-process or multi-instance serialization, actual OS process cleanup, or runtime sandbox acceptance.

## Test-design shortcoming

An initial threaded E2E draft failed (8 passed, 1 failed) because the fixture's SQLite connection is bound to the thread that created it. The test agent replaced that draft with the deterministic same-thread checkpoint scenario above. The exact initial traceback was not retained; this was a test-design failure, not a product-code failure. No test result is reported from the initial draft as acceptance evidence.
