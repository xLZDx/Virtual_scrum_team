# S2-4 runtime owner-to-Runner attempt — change-note draft

- **Task:** `S2-4-runtime-owner-runner-qualification`
- **Status:** `INCONCLUSIVE`; the single permitted runtime attempt did not reach root capture or Runner execution.
- **Source head:** `b38e723922102695cb20c579aea274dc46a86a18`.
- **Installed runtime:** `/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2` in Ubuntu-24.04 WSL2.
- **Runtime boot:** `270cd88b-183f-426c-8add-872d9e98bcec`.
- **Task binding:** `S2-4-runtime-owner-runner-qualification`, run `s2-runtime-20261030-87d47f635f1c4231ab052a074dba4be8`, request nonce `0d2bb2c5f977478a924f7ec6629a339d`; `retry_cap: 0`.
- **Only authorized TestRun selector:** `tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment`.
- **Action observed:** one `systemctl start --no-block vst-sandbox-probe.service`; command exit code 0. While active, PID 373, InvocationID `9ae0fc43f0534cc99dda2acb2f0661b0`, `PrivateNetwork=yes`, state `activating/start` were observed.
- **Actual outcome:** the exact invocation journal says the main process exited `code=killed, status=15/TERM` at `2026-10-30T03:42:29.655Z`, then the unit failed with result `signal`. The reason/actor for SIGTERM is not established by these records.
- **Root command errors:** the three root namespace-observation attempts failed before producing evidence: empty MainPID (`test: integer expression expected`), PowerShell/WSL quoting (`C:Userskoros: line 1: test: : integer expression expected`), then Python `KeyError: 'P'` because the PID variable was not exported. No network-policy attestation was published and no private key material was read or output.
- **Final read-only state:** attestation absent, root preflight record absent, Store absent, systemd job queue empty, all dependent services/socket inactive. No bootstrap, issuer, Supervisor, Signer, Runner, Dispatcher, or dispatch-owner action occurred.
- **Test result:** the one authorized TestRun is `NOT_RUN`. No selector or broader suite was invoked.
- **Boundary:** no retry/restart/resend is allowed under this task's `retry_cap: 0`; do not reuse its run/request identity. Preserve the exact journal and errors. Codex owns diagnosing the interrupted invocation and preparing a new bounded authorization before another runtime attempt.
- **Evidence:** see `s2-4-runtime-owner-runner-attempt-20261030.json` for timestamps, journal fields, systemd observations, command failures, and final state.
