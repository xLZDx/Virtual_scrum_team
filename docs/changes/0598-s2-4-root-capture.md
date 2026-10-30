# Change 0598 — S2-4.2 root probe capture

Date: 2026-10-30

Owner: Codex

Backlog task: S2-4.2, ordered child of S2-4

## Acceptance delta

S2-4.1 removed the Runner's probe-signing dependency. The remaining source gap was the lack of a
trusted path from the non-root systemd probe's output to the root-owned record consumed by
Supervisor. This task adds that capture path and rejects probe observations outside a 120-second
monotonic freshness window. It does not claim that the target runtime has been installed or
measured.

## Implementation

- `tools/vst/preflight_capture.py` accepts a single 32-character systemd invocation ID and reads
  only that service invocation's journal output. It requires exactly one worker-identity JSON
  inventory, matching root-controlled run/spec/nonce inputs and the separately verified
  network-policy attestation.
- The capture also requires one successful systemd manager result for the same unit and invocation,
  filtered to trusted PID 1 / UID 0 journal records. The record is published canonically with
  root ownership and mode `0600` by an atomic no-overwrite link in a root-controlled mode-`0700`
  directory; files and parent directory are synced before success is reported.
- `tools/vst/preflight.py` rejects stale and future monotonic timestamps. Synthetic probe fixtures
  in the affected tests now use the current monotonic clock; E8 and Store lifecycle coverage remains
  synthetic and is not runtime evidence.

## Verification

The designated `functional-test-reviewer` ran:

```text
python -m pytest -q tests/vst/test_s2_preflight_capture.py tests/vst/test_s2_sandbox_probe.py
87 passed, 9 skipped, 1 warning in 2.91s; exit 0
```

and:

```text
python -m pytest -q tests/vst/test_s2_e8_synthetic_lifecycle.py tests/vst/test_s2_store_lifecycle.py::test_supervisor_consumes_a_synthetic_probe_once_for_one_run
7 passed, 1 warning in 35.48s; exit 0
```

Both Windows-hosted runs used HEAD `312090a949e78f1db4d3877978781c5a568417d0`. Warnings are
pytest-asyncio's Python 3.14 deprecation notice. The first run skipped the POSIX root-owned
publication test because that test process ran on Windows; it did not establish that WSL lacked
Python.

The designated `e2e-runner` then archived the exact committed `tools/vst` and focused test files
from HEAD `29f2671` into a temporary WSL directory and ran the POSIX publication integration as
root:

```text
/usr/bin/python3 --version
Python 3.12.3
/usr/bin/python3 -m pytest --version
pytest 7.4.4
/usr/bin/python3 -m pytest -q tests/vst/test_s2_preflight_capture.py::test_posix_record_has_real_root_owner_mode_0600_and_never_overwrites
1 passed in 0.30s; exit 0
```

The `e2e-runner` confirmed the temporary directory was removed. No VST service or persistent
runtime configuration changed. This verifies root-owned mode-`0600` atomic publication and
no-overwrite behavior on the target OS; capture of an actual systemd probe invocation and its
manager result remains unverified.

Independent read-only Python and security reviews found no concrete source defect. The security
review specifically confirms the root manager query is invocation-bound and filters trusted
manager PID/UID fields. This is source review, not live systemd evidence.

## Acceptance disposition and next task

- **S2-4.2 source and focused tests:** implementation, synthetic tests, and the target-OS root
  publication integration are complete.
- **S2-4 runtime acceptance:** remains `IN PROGRESS`. Actual systemd journal behavior, target-side
  root capture, candidate bundle repinning/installation, current E5 provenance and a real
  owner-to-Runner result have not been established by this task.
- **Restricted runtime selectors:** process-kill, crash/recovery, mutation and policy selectors
  remain `NOT_RUN`; synthetic lifecycle tests are not counted as runtime passes.
- Continue with the next ordered S2-4 runtime task after this task is committed and normally pushed.
  Do not reopen S2-4.1 or start S2-5/S3 before the remaining S2-4 runtime acceptance is evidenced.
