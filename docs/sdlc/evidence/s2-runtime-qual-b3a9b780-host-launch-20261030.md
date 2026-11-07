# S2-4.12c host-launch attempt — authorization b3a9b780

Date: 2026-10-30 (local date; time not recorded by the runner)  
Task: S2-4, permitted current-run qualification  
Repository HEAD bound by the authorization: `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`  
GPT-PM authorization: `b3a9b780-6998-47f1-a944-aed40c19db45`  
Runtime run ID in the authorized launcher: `s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910`

## Result

The single authorized host-launch attempt failed before Python started. The command was passed
through `cmd.exe`; its quoting caused Windows to treat the quoted interpreter token as an
unrecognized command. Exact command as reported by the designated `e2e-runner`:

```text
"C:\Python314\python.exe" -I -B -S "D:\Repo\Virtual_scrum_team\docs\sdlc\evidence\s2-runtime-qual-b3a9b780-launcher.py"
```

Observed output:

```text
'\"C:\Python314\python.exe\"' is not recognized as an internal or external command,
operable program or batch file.
```

The host process returned exit code 1. Python did not start; the launcher did not execute, no WSL
child was created, and no post-apply status, preflight, claim/probe, or TestRun ran. No WSL
stdout/stderr or runtime artifacts were produced. No configuration, service, Store, selector,
credential, or production state was changed by this attempt.

The launcher source hash was SHA-256
`B2DF5FBD8A2CD4EC4D45B24F3900B46294A56E1869003434DB3F0419C90F4A6C`. This identifies the
untracked evidence launcher at the time of the attempt; it is not an execution result.

## Disposition

The authorization was one-shot with retry cap zero and is consumed. No second invocation was
made. S2-4 remains `IN PROGRESS`; S2-5 remains queued; S2 remains `NOT APPROVED`; production
activation remains `NOT_RUN`.

## Correlated GPT-PM adjudication and authorized correction

GPT-PM replied under request `98594d0e-1fb5-40ba-9ad5-148a3413e4e8` at
`2026-10-30T12:10:17.135Z`: the tuple is valid for conditional reuse, but the attached launcher
is on HOLD for two MAJOR findings. The pre-Python failure alone does not require tuple regeneration;
reuse remains conditional on fresh HEAD, six source pins, boot/runtime, configuration and candidate
state checks. GPT-PM authorized launcher-only corrections and static review, preserving HEAD
`7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`, the tuple and all six source pins. No WSL invocation
was authorized by that reply.

Codex changed only this launcher: both `findmnt` calls now require the exact `/mnt/d` mountpoint,
and after all six source pins pass it establishes and verifies `/mnt/d/Repo/Virtual_scrum_team`
as the explicit import root while retaining isolated Python mode. Application/runtime source,
tests, tuple, HEAD and pins were not changed by this correction. The corrected launcher hash is
recorded in the follow-up review request and will be recorded here after GPT-PM's focused verdict.

Next: GPT-PM performs focused review of MAJOR-01/02 and direct launcher regressions. Only after
approval may Codex request a separate runtime authorization; this launcher must not be run under
the consumed `b3a9b780` authorization. The next authorized execution must still stop at its first
failure or ambiguity.
