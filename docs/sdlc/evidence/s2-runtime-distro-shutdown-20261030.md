# S2-4 runtime interruption diagnosis — 2026-10-30

## Scope and evidence

This is a read-only follow-up to the consumed runtime attempt recorded in
`s2-4-runtime-owner-runner-attempt-20261030.json`. No service was started by this follow-up; it
queried the existing WSL journal only.

The attempt record binds the interrupted run to source HEAD
`b38e723922102695cb20c579aea274dc46a86a18`, runtime selector
`/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2`, boot ID
`270cd88b-183f-426c-8add-872d9e98bcec`, and probe InvocationID
`9ae0fc43f0534cc99dda2acb2f0661b0`. This is historical failure evidence, not evidence that the
current `aedf712c` candidate ran.

Command:

```text
wsl.exe -d Ubuntu-24.04 -u root -- journalctl --utc --no-pager -o short-precise --since '2026-10-30 03:41:40 UTC' --until '2026-10-30 03:43:00 UTC' -u vst-sandbox-probe.service
```

Observed records for InvocationID `9ae0fc43f0534cc99dda2acb2f0661b0`:

- `03:41:51.925972Z`: systemd started `vst-sandbox-probe.service`.
- `03:42:29.655973Z`: the probe main process exited with signal 15 (`SIGTERM`).
- systemd immediately recorded the unit failure and stop.

A second read-only query of all journal entries from `03:42:15Z` through `03:42:40Z` showed,
before the probe's signal:

- `03:42:29.579768Z`: `systemd-logind` — “The system will power off now!”
- `03:42:29.601567Z`: `systemd-logind` — “System is powering down.”
- systemd then stopped the session and services; the probe was killed during that shutdown.

## Conclusion and limits

**Confirmed:** the probe's `SIGTERM` coincided with a WSL distro system shutdown. This was not a
probe timeout: the journal records the system power-off sequence before the unit's signal exit.

**Inference:** the attempt record shows the probe was started using a standalone
`wsl.exe ... systemctl start --no-block ...` call and then root observations were attempted via
separate commands. The gap between WSL client invocations is consistent with the distro becoming
idle and shutting down. The journal does not identify the external actor or prove the exact WSL
idle-shutdown trigger, so that trigger remains `NOT_ESTABLISHED`.

The implementation direction is to keep one WSL child/session alive for the full authorized,
bounded stage sequence instead of returning to the Windows host between a nonblocking unit start
and its observation. This does not justify retrying the consumed run, reusing its nonce, bypassing
preflight, or treating the interrupted probe as a pass. A fresh run requires its own valid
one-shot authorization after the exact launcher and source candidate are reviewed.

## Acceptance disposition

- Root preflight and Owner-to-Runner/TestRun: `NOT_RUN` for this interrupted invocation.
- Runtime/E5 acceptance: `INCONCLUSIVE`; the system shutdown is diagnosed, but no run-bound
  attestation or TestRun was produced.
- Retry: `NOT_AUTHORIZED` under the consumed attempt's `retry_cap=0`.
- Current task: S2-4 remains active; S2-5 remains queued.
