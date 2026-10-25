# S3 STOP cleanup diagnostic functional evidence

## Run identity

| Field | Evidence |
|---|---|
| Exact test/code HEAD before and after | `2a8c17583e4e7594464b85aace6addb827a5eb6c` (same before and after) |
| Branch | `s3-vendor-neutral-worker-pilot` |
| Worktree state before and after | Existing unrelated untracked file `docs/sdlc/evidence/s2-functional-test-run.md`; it was not staged or changed by this run |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Runtime command | `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s3_worker_adapter.py tests/vst/test_s3_worker_pilot_e2e.py` |
| Result | **16 passed, 0 skipped, 0 failed**, exit code 0; pytest reported 53.86 seconds |
| Warning | One installed `pytest_asyncio` deprecation warning: `asyncio.get_event_loop_policy` is deprecated and scheduled for removal in Python 3.16. |

## S3 AC-4 coverage

- `test_s3_stop_fences_interrupted_attempt_idempotently_and_rejects_stale_start` verifies a successful adapter return remains `INCONCLUSIVE`, reports process cleanup as `NOT_VERIFIED`, replays the same response, increments the Store epoch once, and rejects stale work.
- `test_s3_stop_cleanup_exception_preserves_fence_and_hides_exception_text` injects a deterministic application checkpoint, then makes adapter cleanup raise `RuntimeError` containing a private marker. It verifies the same durable epoch fence and non-approving response, bounded type diagnostic, redaction of the exception text, no receipts, and stale-start rejection.
- `test_s3_stop_cleanup_exception_class_falls_back_to_bounded_safe_name` covers overlong and non-identifier exception class names and verifies only `UnknownError` is returned.

This proves local synthetic Store/Supervisor behavior and response contents. It does not prove OS process termination, sandbox isolation, candidate execution, or the prohibited process-kill/kill-table paths; those remain `NOT_RUN`/`NOT_VERIFIED`.

## Provenance

The functional-test-reviewer authored these regressions in commit `2a8c17583e4e7594464b85aace6addb827a5eb6c` and ran the exact command above after that commit. No source changes occurred during the run. The pre-existing untracked S2 evidence file remains outside this S3 evidence commit.
