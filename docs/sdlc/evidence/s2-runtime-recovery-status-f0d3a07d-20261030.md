# S2-4 bounded recovery status observation — 2026-10-30

Task: S2-4 runtime configuration qualification.  
Owner: Codex (coordination/evidence); `e2e-runner` (runtime execution role).  
Authorization: GPT-PM request `f0d3a07d-4b1d-4eb7-a04e-25bbdf0be93d`, bound to HEAD
`7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`.

## Fresh inventory and validator

The single authorized collector/validator chain ran through one continuous Ubuntu-24.04 WSL
process. The D: repository mount was read-only 9p and source HEAD matched the authorization.

- Collector captured at `2026-10-30T11:17:48.149468Z` (13:17:48 +02:00), exit 0.
- Collector raw stdout: `s2-runtime-qual-f0d3a07d-s2-runtime-20261030-2b5e04a3-collector.stdout.bin`,
  SHA-256 `6d9e4f818c91ee986c131dfef7b08aee36f36267e029302707f470be0cb23f53`.
- Validator ran once, exit 0, and reported `PASS: complete S2 runtime inventory` for exactly
  26 configuration destinations, repo HEAD `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`, and
  runtime selector `/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2`.
- Validator stdout: `s2-runtime-qual-f0d3a07d-s2-runtime-20261030-2b5e04a3-validator.stdout.bin`,
  SHA-256 `1bb165b1935462a671230d7a6566c957ef599277c0d7587daf44e1327a8818f7`.

## Narrow post-inventory status query

The project host-capture implementation documents `systemctl show` properties including
`LoadState`, `ActiveState`, `SubState`, `Result`, `MainPID`, `InvocationID`, `ControlGroup`, and
`PrivateNetwork` (`tools/vst/preflight_host_capture.py`). A targeted query was made only for the
nine VST units already named by the collector. It did not enumerate host-wide processes.

At `2026-10-30T11:19:50Z`, all nine units were `loaded / inactive / dead`, `Result=success`, and
`MainPID=0` for service units. `systemctl list-jobs --no-legend --no-pager` returned no jobs.
The runtime symlink still pointed to the pinned candidate.

The shell returned exit 2 after printing the systemd results with
`Syntax error: end of file unexpected (expecting "done")`. No `PATH_*` lines were emitted, so the
intended path checks did not produce a second filesystem observation for the Store, preflight,
attestation or socket paths; the transcript does not establish which loop caused the syntax error.
The fresh inventory itself recorded Store,
preflight and attestation absent and `candidate_identity_collision=false`; its validator accepted
the complete 26-file original-baseline comparison.

## Disposition

The fresh inventory recorded boot ID
`270cd88b-183f-426c-8add-872d9e98bcec`; the later targeted status query recorded
`b0d0e05e-8705-44ab-9f32-277742e4a343`. The WSL boot identity changed after inventory capture.
This violates GPT-PM's condition that boot identity remain unchanged and invalidates the captured
target state for a subsequent apply, even though the inventory is still within its five-minute
wall-clock freshness window.

No configuration apply, preflight, claim/probe, TestRun, process termination, or Store mutation was
performed. The one-shot collector and validator authorizations were each consumed and were not
repeated. The remaining runtime chain is `NOT_RUN` pending a separate authorization for a fresh
qualification after the boot-identity change.
