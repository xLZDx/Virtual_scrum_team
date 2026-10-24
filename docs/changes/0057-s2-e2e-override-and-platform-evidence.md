# 0057 S2 E2E override, anchor and platform evidence

## What changed

- Extended the owned S2 runner lifecycle tests for operator-signed manual overrides: unsigned and tampered records, plain `APPROVE`, mismatched breaker episode/configuration, stale replay after a later episode, and valid active-episode approval.
- Replaced the POSIX worker identity placeholder with a real identity boundary test and added a distinct read-only reviewer write-denial test against worktree and SQLite Store fixtures.
- Added synthetic mount classification checks proving `/mnt/wslg` is not a Windows drive while Windows `drvfs` and `9p` mounts with `aname=drvfs` are rejected.
- Corrected POSIX anchor test diagnostics and failure-injection wrapper signatures so tests exercise the actual POSIX `flock` contract.
- Recorded Windows and Ubuntu WSL test results, unsigned preflight findings, read-only reviewer permission evidence, and remaining acceptance blockers in `docs/sdlc/evidence/s2-e2e-acceptance-280e2d0.md`.
- Ran safe selected E8 fixture operations for STOP/cleanup, budget exhaustion, epoch fencing, out-of-scope write rejection, and reserved-target egress smoke. The complete bake-off and `crash_mid_edit` remain `NOT_RUN` because the available `run_lifecycle_scenarios` unconditionally reaches `os._exit(97)`.

## Why

The implementation now requires operator signature and breaker-episode binding for a manual override. The prior E2E coverage did not exercise that trust boundary. POSIX anchor behavior and WSL mount classification also needed runtime evidence on the provisioned environment, while preserving the explicit prohibition on process-kill and mutation scenarios.

## Verification state

- Exact product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Windows focused command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py`.
- Windows result: exit 0; 84 passed, 22 skipped, 1 pytest-asyncio deprecation warning (106 collected).
- POSIX Store command: run as `vst-runner` in `vst-run.slice` with the four per-run `InaccessiblePaths`; `python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_store_lifecycle.py`.
- POSIX Store result: exit 0; 19 passed, no skips.
- POSIX synthetic probe command: same slice/identity/isolation properties; `python3 -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_sandbox_probe.py`.
- POSIX runner/sandbox result: exit 0; 76 passed, 11 skipped. The separately selected identity tests passed 2/2. Actual WSL/VM host isolation and E8 crash cases remain `NOT_RUN`.
- Read-only reviewer probe: `require_read_only_reviewer` passed under reviewer UID 993 against worker UID 999 fixtures; writes to a worktree file, store fixture, and new worktree path were denied.
- Unsigned WSL preflight: `FAIL`. `container_socket_inventory_complete` was false because `vst-runner` cannot traverse the root-owned `/run/user` numeric entry with mode `0700`. A scoped empty read-only `/run/user` mask yielded complete inventory, but worker inheritance and system mount approval are unresolved. The final probe was not signed and no operator key was read or invoked.
- Scoped masked-inventory diagnostic: `TemporaryFileSystem=/run/user:ro` produced an empty runtime directory and `container_socket_inventory_complete=true`; the overall unsigned probe remained `FAIL`. No installed application unit confirms the actual worker inherits this mask.
- Selected safe E8 fixture operations passed their assertions; full E8 and process-kill cases remain `NOT_RUN`.
- Real signer socket and `run_manifest_commands` integration: `NOT_RUN`. A transient unit setup had previously been attempted, but on resumed inspection the unit was inactive/not found and its runtime launcher directory was absent; no client request or signature was made in this resumed turn. The dedicated runner-signer key path must be available only to a live signer process. Operator-key access remains prohibited and was not performed.
- Process-kill, kill-table, mutation, CI, build, and migration scenarios were not run.

## Ownership

- Accountable task owner: operator.
- Test author and executor: E2E runner (`gpt-6-luna`).
- Technical owner for root-runtime socket inventory and system-mount approval is not identified by the available project records; operator decision/provisioning remains the dependency.

## Related records

- Test evidence: `docs/sdlc/evidence/s2-e2e-acceptance-280e2d0.md`.
- Earlier unsigned diagnostic, retained as historical failure: `docs/sdlc/evidence/s2-e2e-wsl-diagnostic-c470542.md`.
