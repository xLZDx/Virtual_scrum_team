# S3 focused synthetic test evidence

- Exact repository HEAD before and after both runs: `58088c804ee3d444919ec433b656c80ec3106f37`.
- Functional owner: `functional-test-reviewer` (GPT-6 Luna, medium).
- E2E owner: `e2e-runner` (GPT-6 Luna, medium).
- Environment: pinned `C:\Python314\python.exe`; Windows host. No external candidate or sandbox mode.

| Lane | Exact command | Result | Coverage and limitation |
|---|---|---|---|
| Functional adapter contract | `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_adapter.py` | 8 passed; 1 pytest-asyncio deprecation warning; 1.97 s | Typed bounds, identity/fencing, Store operation and budget idempotency, named Store checkpoint resume, worker non-authority. |
| Synthetic pilot E2E | `C:\Python314\python.exe -m pytest -q tests/vst/test_s3_worker_pilot_e2e.py` | 5 passed; 1 pytest-asyncio deprecation warning; 42.64 s | Scoped synthetic edit, trusted candidate binding, named application checkpoint/resume, STOP fencing and stale-start rejection. |

Fresh signed sandbox probe, actual WSL boundary, operating-system process cleanup after STOP/timeout, process-kill/kill-table cases, external candidate comparison, and the full S3 scenario denominator are `NOT_RUN` or `NOT_VERIFIED`. The tests exercise the committed in-repository synthetic code only; they do not establish containment or cleanup of an external process.
