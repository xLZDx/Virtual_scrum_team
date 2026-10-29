# Change 0485 — Correct S2 POSIX selector provenance

Date: 2026-10-28

## What and why

Corrected the S2 runtime evidence after discovering that the retained summary for two POSIX runner
selectors had no recoverable exact command or raw pytest output. The recorded command also placed
`test_runner_drops_uid_change_capabilities_before_worker_command` under `test_e4_runner.py`, while
the source definition is in `test_s2_runner_lifecycle.py`. The logged two-skip result is therefore
not established at selector level.

## Change

- Mark both POSIX runner selector outcomes `NOT_VERIFIED` and `NOT_RUN` for acceptance.
- Preserve the executor's retained “two skipped” summary only as an unverified historical claim.
- Update S2 state, backlog, decision, lesson, and change records to remove the unsupported skip
  acceptance claim.
- Keep the absent dedicated `CAP_SETGID,CAP_SETUID` runner profile as a separate environmental
  prerequisite. No rerun, capability provisioning, or service operation occurred.
- Keep S2 active; no S3/S4 task or evidence was changed.

## Affected acceptance and evidence

`VST-013` remains partial. The valid Windows cleanup, WSL E3 store, synthetic identity, and waiver
boundary results remain unchanged. The two POSIX runner selectors do not contribute to passed or
skipped acceptance counts until a future designated e2e-runner invocation preserves exact command,
environment, and output. Evidence: `docs/sdlc/evidence/s2-controlled-runtime-selectors-20261028.md`.

## Verification state

- Inspected the recorded evidence and change 0483.
- Verified the selector definitions by repository search: capability-drop is in
  `tests/vst/test_s2_runner_lifecycle.py`; cross-UID timeout is in
  `tests/vst/test_e4_runner.py`.
- Queried the prior e2e-runner; it confirmed exact command/output are unavailable and ran no tests
  during follow-up.
- No tests/checks were run for this documentation correction.

## Ownership and next step

Codex owns the evidence correction and coordination. The operator owns any separately required
operational provisioning of the dedicated runner capability profile. Next: leave both selectors
`NOT_RUN` until that profile and service boundary are valid and a designated e2e-runner can capture
the exact invocation/output. S2 remains `NOT APPROVED`; S3 has not started.
