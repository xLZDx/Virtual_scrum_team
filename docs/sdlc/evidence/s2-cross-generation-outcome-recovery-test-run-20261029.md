# S2 M03 cross-generation outcome recovery focused test run — 2026-10-29

## Exact execution

- Exact repository HEAD: `c855ca4f2888d7288b006973950e4c6d28023b63`.
- Executor: `e2e-runner` role.
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4. The canonical checkout
  `D:\Repo\Virtual_scrum_team` was mounted from D: into that same WSL invocation at
  `/mnt/d/Repo/Virtual_scrum_team`. No copy, fork, worktree, or per-sprint directory was used.
- Exact invocation:

  ```powershell
  wsl.exe -d Ubuntu-24.04 --user root -- sh -lc 'set -eu; mkdir -p /mnt/d; if mountpoint -q /mnt/d && grep -Fq " /mnt/d " /proc/mounts; then umount /mnt/d; fi; mount -t drvfs D: /mnt/d; cd /mnt/d/Repo/Virtual_scrum_team; git rev-parse HEAD; git rev-parse HEAD | grep -Fx c855ca4f2888d7288b006973950e4c6d28023b63; python3 --version; python3 -m pytest --version; sha256sum tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py; /usr/bin/time -f "DURATION_SEC=%e" python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py'
  ```

- Result: **130 passed, 0 failed**, pytest exit 0; pytest reported 11.23 seconds and
  `/usr/bin/time` reported 12.42 seconds.
- The test suite selected exactly:

  ```text
  tests/vst/test_s2_signed_dispatch_instruction.py
  tests/vst/test_s2_store_backed_pubsub.py
  tests/vst/test_s2_dispatch_owner_service.py
  tests/vst/test_s2_dispatch_owner_latch.py
  ```

- SHA-256 at the tested revision:
  - `tests/vst/test_s2_signed_dispatch_instruction.py` —
    `13b436675383e98449520c15c640a87fcb84370ade534475b5ad2c63ece8b76f`
  - `tests/vst/test_s2_store_backed_pubsub.py` —
    `b5f6a36ab8511ea7e09a67d327a44b637b94faab312e0d13293cd735e293b0bc`
  - `tests/vst/test_s2_dispatch_owner_service.py` —
    `fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71`
  - `tests/vst/test_s2_dispatch_owner_latch.py` —
    `fd8c7e9710b6904f41fd503990b651021f58567b59c21719511056ae23671356`

Two pre-run attempts exited before pytest: one HEAD check emitted `fatal: not a git repository`,
and a later invocation could not change directory because the WSL D: mount had ended between
invocations. Neither started pytest. The passing invocation explicitly mounted and ran the suite
within the same WSL process.

## M03 acceptance mapping

The functional-test-reviewer authored the cases; the e2e-runner executed them. This run covers
`S2-PROV-M03-R01` and the separate historical read-only recovery contract:

- `test_verified_replay_returns_original_result_for_expired_or_revoked_acceptance` verifies exact
  stored result retrieval after expiry/current key removal and verifies no event, operation, or
  anchor mutation.
- `test_never_accepted_expired_or_revoked_instruction_never_reaches_admission` verifies a replay
  miss refuses without calling new admission.
- `test_replay_rejects_changed_principal_envelope_or_signature` verifies mismatched identity,
  signed fields, signature bytes, and key ID do not retrieve another result.
- `test_supervisor_replays_pending_result_from_original_generation_after_rotation` rotates G1 to
  G2, confirms normal admission refuses, returns the original G1 result, appends no second accepted
  event, and records ACK against G1.
- `test_replay_after_current_admission_refusal_acks_original_generation_without_retry` exercises
  the relay route and checks one admission call, one read-only replay, and ACK against the original
  generation.
- `test_replay_refuses_incomplete_external_anchor_reconciliation` verifies stale external anchor
  state is refused and Store integrity is locked. The selector is POSIX-only and ran in WSL.
- Legacy-unresolved, malformed/out-of-order control history, unauthorized role, and caller-supplied
  principal cases fail closed. Existing pending-barrier and forwarding/ACK failure regressions ran
  in the same selected files.

## Limits

This synthetic source-level suite does not prove installed systemd behavior, production identity or
root configuration, runtime/E5, a production coordinator call site, Windows/POSIX process
containment, prohibited scenarios, physical power-loss behavior, or overall S2 acceptance. Fresh
specialist review and final exact-head GPT-PM approval remain required.
