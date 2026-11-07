# S2 dispatch-owner transport focused WSL run — 2026-10-29

## Purpose and scope

This is source-level integration evidence for the transport-only dispatch-owner client. It verifies
the exact request/half-close/EOF/response path between `DispatchOwnerSocketClient` and the real
`DispatchOwnerService._handle()` method over a local AF_UNIX socketpair. It does not connect to the
installed systemd socket, Supervisor/Store, Runner, or any production identity.

## Candidate provenance

- Canonical checkout: `D:\Repo\Virtual_scrum_team`.
- Windows Git HEAD before and after: `20fda2cbf26274192652a1c829a19f6b1844e9c4`.
- Source Git blob: `tools/vst/dispatch_owner_transport.py`, `81d1624421341b65a0cde95215bf03c08330b520`.
- Source SHA-256: `134ECE4FD7E20B947EE3E91EA08909B359E03542BC0243C77E753B54591D4DE4`.
- Test Git blob: `tests/vst/test_s2_dispatch_owner_transport.py`, `768a6ea9097d2284bc0fc546495630e9ed8518b3`.
- Test SHA-256: `E9CE576A549D9617B39D9469200030548A4C8C81CC41C8F3AC3F879490EA5D40`.
- Working-tree status before/after the WSL run was identical. Modified project files were the
  active S2 records; new files were this source, its tests and adjudication note. The protected
  pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remained untouched.

## Windows focused result

The designated `functional-test-reviewer` ran:

```text
python -m pytest -q tests/vst/test_s2_dispatch_owner_transport.py
```

Environment: Python 3.14.3, pytest 8.4.2.

Result: **33 passed, 1 skipped, 0 failed**, exit code 0. The skip was the POSIX/root-owned
synthetic Ed25519 fixture. One existing pytest-asyncio deprecation warning was emitted. This run
does not execute the AF_UNIX socketpair selector.

## WSL focused result

The designated `e2e-runner` used the existing dedicated `Ubuntu-24.04` WSL2 and the canonical
repository mounted at `/mnt/d/Repo/Virtual_scrum_team`; no copy, fork, or worktree was created.
`/etc/wsl.conf` has `automount.enabled=false`, so the runner temporarily mounted D: inside the same
WSL invocation and ran the exact selector as root.

```text
python3 -m pytest -q -rs tests/vst/test_s2_dispatch_owner_transport.py
```

Environment: Ubuntu-24.04 WSL2, root, Python 3.12.3, pytest 7.4.4.

Result: **34 passed, 0 skipped, 0 failed**, exit code 0. Runtime was 0.88 seconds. The real local
AF_UNIX socketpair and unmodified `DispatchOwnerService._handle()` verified a single request,
`SHUT_WR`, observed EOF, response and ACK without deadlock.

The first WSL attempt reached the same selector but used test-mock constant `6` for `SHUT_WR`; the
real Linux socket requires its actual `socket.SHUT_WR` value, so the fixture raised `EINVAL`. The
test owner corrected the test-only constant and reran. The final invocation was the pytest command
itself, captured exit 0, and had no skips.

## Evidence limits

- Kernel peer credentials, pidfd and socket filesystem metadata are mocked in this source fixture.
- The test does not exercise the systemd `Accept=no` socket activation endpoint or confirm live
  PID 1 credentials, installed ownership/modes, real keys/configuration, or E5.
- Production `owner -> Supervisor -> Store -> dispatcher -> Runner` remains `NOT_RUN`.
- No service identities/configuration were provisioned; no keys were generated outside disposable
  test fixtures; no Store migration, runtime installation, service activation or real dispatch was
  performed.
- Prohibited process-kill/crash/recovery/mutation/policy scenarios remain `NOT_RUN`.
