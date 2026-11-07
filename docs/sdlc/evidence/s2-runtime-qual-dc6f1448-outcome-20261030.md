# S2-4 bounded runtime attempt — GPT-PM request `dc6f1448`

## Disposition

**HOLD before WSL.** The single-use authorization is consumed. The host launcher ran once and
returned exit code 0 after recording a child-spawn error. Windows rejected the one attempted
`wsl.exe` child with `FileNotFoundError: [WinError 206] The filename or extension is too long`.
No WSL process started and no runtime-stage command ran. Do not retry this authorization.

## Identity and exact host invocation

- Authorization: GPT-PM request `dc6f1448-e8ab-47e5-a653-962d9ff48c34`, one attempt, zero retries.
- Local checkout observed before invocation: branch `s2-canonical-continuation`, HEAD
  `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`.
- Launcher:
  `docs/sdlc/evidence/s2-runtime-qual-b3a9b780-launcher.py`, SHA-256
  `d4cd4b3d4eacc1ca620223db7ec997821106528e345a6110531ca1a8d32511d5`.
- Command: `C:\Python314\python.exe -I -B -S D:\Repo\Virtual_scrum_team\docs\sdlc\evidence\s2-runtime-qual-b3a9b780-launcher.py`.
- Working directory: `D:\Repo\Virtual_scrum_team`.
- Outer process started `2026-10-30T12:26:01.2038544Z`, finished
  `2026-10-30T12:26:01.3911619Z`, exit code `0`.
- Launcher attempt record timestamps: started `2026-10-30T12:26:01.370319+00:00`, finished
  `2026-10-30T12:26:01.373623+00:00`; `wsl_spawned=false`.
- The launcher recorded the exact child-spawn error above. Its WSL stdout was empty; WSL stderr
  contained only `FileNotFoundError: [WinError 206] The filename or extension is too long`.

## Reached stages

| Stage | Result | Evidence |
|---|---|---|
| Authorization / one host invocation | CONSUMED; exactly one attempted | Outer stdout and attempt record |
| Host Python launcher | STARTED; exit 0 | Outer process record |
| WSL child | NOT_STARTED | `wsl_spawned=false`; WinError 206 |
| `/mnt/d` detection or temporary read-only mount | NOT_RUN | No WSL process |
| Exact HEAD and six source-pin checks inside WSL | NOT_RUN | No WSL process; local HEAD observation above is not runtime pin evidence |
| Fresh post-apply inventory/config/runtime/systemd/candidate status | NOT_RUN | No WSL process |
| Root-captured preflight | NOT_RUN | No WSL process |
| Owner→Runner claim/probe | NOT_RUN | No WSL process |
| Exact report-bound TestRun selector | NOT_RUN | No WSL process |
| Restricted tests, production activation, migrations, credential/key operations | NOT_RUN | Outside this authorization's scope |

## Raw artifacts

- Outer stdout: `s2-runtime-qual-dc6f1448-outer.stdout.bin`, 36,790 bytes, SHA-256
  `da6e103956b4305b3d2ae1ab5e3e087b204c8aaa2582f6f70e93929221615c92`.
- Outer stderr: `s2-runtime-qual-dc6f1448-outer.stderr.bin`, 0 bytes, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Launcher attempt record:
  `s2-runtime-qual-b3a9b780-s2-runtime-20261030-2b5e04a3.attempt.json`, 36,960 bytes,
  SHA-256 `e9aada51fcb599368409993dc192eba756813ce159c2a4c3c6b6a1e0805f84ea`.
- Captured child stdout:
  `s2-runtime-qual-b3a9b780-s2-runtime-20261030-2b5e04a3-wsl.stdout.bin`, 0 bytes, SHA-256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Captured child stderr:
  `s2-runtime-qual-b3a9b780-s2-runtime-20261030-2b5e04a3-wsl.stderr.bin`, 71 bytes, SHA-256
  `6432d39107ce2c19135d41644fad43543b5b4f6ef41d4b8a4a7138dbdeb279e2`.

## Next action

S2-4 remains **IN PROGRESS**; S2-5 remains queued. Codex owns coordinating a corrected command-length
transport and obtaining a new correlated GPT-PM authorization for its exact launcher bytes. The
`e2e-runner` may execute only under that new one-shot authorization. No source, launcher, WSL
configuration, or runtime state was changed by this attempt.
