# Change 0522: stop S2 dispatch socket before latch storage access

## Why

Independent code and reliability reviews of the 0518 admission fence found a fail-open path. The
root `ExecStopPost` helper first inspected and wrote `/etc`, then requested an asynchronous socket
stop. A filesystem stall could let systemd kill the hook while the listener remained active, and a
latch write failure did not prove that socket shutdown had completed. An active `.socket` can
activate the relay even when its service uses `Restart=no`.

## What changed

- `tools/vst/dispatch_owner_latch.py` now synchronously stops
  `vst-dispatch-owner.socket` and confirms `ActiveState=inactive` before any `/etc` filesystem
  access. Failed commands, timeouts and uncertain states retry with a bounded timeout per
  `systemctl` call and capped exponential backoff. The hook logs each unresolved state and does not
  proceed while socket shutdown is uncertain.
- `tools/vst/systemd/vst-dispatch-owner.service` sets `TimeoutStopSec=infinity`, so systemd does
  not kill `ExecStopPost` while it is holding the admission barrier or persisting the latch. This
  deliberately trades availability for fail-closed behavior: an unavailable system manager or
  unhealthy `/etc` can hold service shutdown indefinitely and requires operator-visible recovery.
- Latch persistence follows confirmed socket shutdown. If the persistent write fails, the listener
  is inactive at that point and the helper reports failure; without the latch, a later explicit
  socket start is not guarded. Cross-reboot safety is not established in that case; healthy durable
  root-controlled `/etc` remains a hard requirement before any later start or reboot. No `/etc`
  write, root helper invocation, systemd activation or runtime
  provisioning occurred in this change.
- `tests/vst/test_s2_dispatch_owner_latch.py` was updated by `functional-test-reviewer` to cover
  stop-before-storage ordering, inactive-state confirmation, retry after failure/active state,
  per-command timeout, the absence of `--no-block`, persistence failure after shutdown, and the
  unit timeout contract. The designated test executor has not run these tests yet.
- The service contract, admission-fence adjudication, root runtime plan, systemd README and project
  state/backlog now record the corrected order, indefinite-stop trade-off and storage limitation.

## Failure matrix

| Failure step | Resulting state | Recovery owner/action | Evidence |
|---|---|---|---|
| Stop command fails, times out, or socket remains active/unknown | Hook stays in `ExecStopPost`; no `/etc` access; no acceptance of successful shutdown | Codex keeps the code fail-closed; operator restores systemd availability; hook retries | Synthetic retry/confirmation test; installed-systemd behavior remains `NOT_RUN` |
| Parent `stat`, latch open/write, or `fsync` stalls after socket is inactive | Listener is confirmed stopped; systemd does not kill the hook due to `TimeoutStopSec=infinity`; service shutdown may remain pending | Operator repairs durable root-controlled storage; then verifies persistent fence before restart | Test asserts ordering and unit timeout; filesystem-stall runtime scenario `NOT_RUN` |
| Latch persistence errors after socket stop | Socket is inactive at confirmation; helper exits visibly, but no latch guards a later explicit start and cross-reboot safety is unproven | Operator must restore `/etc` and ensure the durable fence exists before any later start/reboot; no automatic reopening | Synthetic persistence-failure test; root filesystem behavior `NOT_RUN` |
| Latch persists successfully | Both service/socket startup conditions and loader reject admission; no automatic retry/reopen | Operator reconciles exact Store request ID and idempotency record before separately authorized recovery | Existing mapped latch/source tests; runtime unit activation `NOT_RUN` |

## Verification and acceptance

- Source/tests were not run by the primary agent. `e2e-runner` owns the next focused run after this
  coding change is committed.
- Previous 105/105 synthetic results apply to `cec0dbf3249b5734bdae52f644ac790e07d869f8`, before
  this correction; they do not validate this change.
- Systemd unit validation, WSL `/etc` writes, root helper invocation, service/socket activation,
  real dispatch, migration, account/group creation, keys, E5, push, PR and merge are `NOT_RUN` or
  prohibited. S2 remains `NOT APPROVED`; S3 remains unstarted.
- Code and reliability reviewers own fresh focused re-review after the new test run; GPT-PM owns
  focused M03 re-adjudication and the later exact-head gate. Codex owns this implementation and
  evidence; the operator owns any future privileged runtime recovery.
