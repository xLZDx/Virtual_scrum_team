# S2 POSIX cross-UID process cleanup design

Status: persistent-service, lifecycle-fence, and fixed UID-drop helper source is implemented in the current working tree but has not been tested, reviewed against the exact final diff, provisioned, or runtime-proven. Earlier exact-head tests and bounded WSL lock/empty-scope observations describe earlier revisions only, 2026-10-27.
Scope: VST-013 / S2 E4.1 and VST-017 bounded process cleanup in the existing Ubuntu-24.04 WSL sandbox.

## Goal and constraints

The runner must stop a worker and every descendant after timeout, normal root exit, output-reader failure, or runner cleanup, even when runner UID and worker UID differ. Keep the worker's effective/permitted/inheritable/ambient capability sets empty. Do not give the runner broad `CAP_KILL`, use a shell, or fall back to a best-effort success when containment is unavailable.

## Options and decision

1. **Grant `CAP_KILL` to the runner.** Small change, but the capability can signal unrelated processes in the runner's user/PID namespace. Rejected as broader authority than the worker process tree requires.
2. **Use a systemd-delegated cgroup-v2 child per worker command.** The trusted runner can create and kill only a child cgroup under its own delegated service subtree. Chosen; the scoped destructive boundary matches the process tree.
3. **Use a fixed narrow identity-drop helper together with systemd cgroup delegation.** The helper does not kill processes or manage cgroups; it accepts only the configured `vst-runner` to `vst-worker` transition, validates two pipe descriptors, clears supplementary groups and capability sets, sets `no_new_privs`, and irreversibly drops privileges. The systemd delegated cgroup remains the only process-tree cleanup authority. This narrow helper is authorized for the selected WSL boundary; its binary provenance and installation still require review and runtime evidence.

## Design

The runner service must have `Delegate=yes` and run on unified cgroup v2. For each POSIX launch using the fixed `vst-runner` (997:988) to `vst-worker` (999:989) identity boundary, the runner creates a unique child cgroup under its delegated cgroup and requires `cgroup.procs`, `cgroup.events`, and `cgroup.kill`. It starts the fixed root-owned `/usr/local/libexec/vst-s4-worker-exec` helper, which accepts only the exact runner identity, worker gate, and two pipe descriptors. The helper clears supplementary groups and capabilities, irreversibly drops to the worker identity, sets `no_new_privs`, closes every descriptor except standard streams and the two validated pipes, and runs the isolated (`python -I -S`) exec gate. No UID, GID, environment, shell, or executable path is accepted from the caller. The gate starts with a fixed environment containing no loader hooks or Python startup controls. The intended worker environment is sent as data through a separate inherited pipe, never as the helper/gate process environment. The gate waits on a second inherited pipe; the worker command has not executed yet. The runner moves the gated process PID into the child cgroup, starts output readers, then releases the gate to `execvpe` the manifest-pinned argv with the supplied worker environment. Descendants inherit the cgroup even if they change session or process group.

On timeout, root-command exit, reader failure, or exceptional cleanup, the runner writes `1` only to that current run's `cgroup.kill`, waits for `cgroup.events` to report `populated 0`, reaps the root process, closes capture pipes, and removes the empty child cgroup. Each command owns a unique scope; concurrent commands in one process never share a kill target. A private `/run/vst-runner` directory is provisioned for the daemon with mode 0710 and the dispatcher group; the daemon-owned admission lock is mode 0600. The runner holds `cgroup-admission.lock` with an exclusive POSIX `flock` across stale-scope reconciliation, command admission, execution, and cleanup. Under that lock it inspects only strict `vst-command-<pid>-<uuid>` child scopes under its delegated cgroup. Empty scopes are removed only after bounded `populated 0` and empty `cgroup.procs` confirmation. Populated, unknown, inaccessible, or unremovable scopes refuse admission and are never killed or adopted. A root-only manager fence records BOOTSTRAP_EMPTY, RUNNING, STOPPED_EMPTY, or UNVERIFIED transitions, exact systemd invocation and cgroup identity, lock/cgroup inodes, and a hash-chained audit record. The runner accepts only a matching root-owned published RUNNING snapshot. Windows continues to use the existing Job Object path. The all-descendant guarantee applies to distinct-UID worker launches that use this cgroup path; same-UID compatibility calls retain the legacy process-group behavior and are outside this S2 acceptance guarantee.

## Failure behavior

- Missing unified cgroup v2, missing `Delegate=yes`, unwritable delegated parent, or absent cgroup control files: refuse to execute a distinct-UID worker and return a non-approving containment result.
- Failure to attach the gated PID: close the gate without releasing the requested command, reap the no-op trampoline, and return non-approving. The trampoline runs only with the fixed sanitized environment until attached, so inherited dynamic-loader variables cannot execute code before containment.
- Failure to kill/reap the cgroup or confirm `populated 0`: return `EXIT_CAPTURE_INCOMPLETE`, preserve diagnostics, never report PASS, and stop launching later commands from the same manifest run.
- Distinct-UID launches are serialized both within one process and across processes by the private runtime lock. Waiting for the lock and reconciling abandoned scopes consume the same per-command/overall time budget. If the budget expires while queued or reconciling, the runner returns timeout without creating a cgroup or starting a process. If a scope's kill/removal remains unconfirmed, latch the failure and refuse subsequent launches from that process; a replacement runner must first acquire the same stable lock and reconcile every stale runner-owned scope. The service must use one stable delegated subtree and stop all pre-lock runner instances before rollout; a runner in a different subtree cannot prove or clean scopes in the old subtree.
- The exec-gate environment handoff is nonblocking and shares the command deadline. If the gate cannot receive the environment before the deadline, close the gate and kill its cgroup without releasing worker code.
- Do not add `CAP_KILL` as a fallback. The outer service timeout is only emergency cleanup, not acceptance evidence.

## Rollout and rollback

Provision the runner systemd service/scope with `Delegate=yes`, a stable delegated subtree, and `RuntimeDirectory=vst-runner` with mode `0710` (runner owner and dispatcher group); retain the existing memory, task, time, private-network and temp-filesystem limits. The service must ensure only the lock-aware runner version can start in that subtree. Validate delegation, private lock ownership, restart recovery, and stale-scope reconciliation before enabling worker commands. Rollback reverts the code/config contract and leaves cross-UID POSIX execution refused; it does not restore broad process-kill capability.

## Verification plan and owners

- `functional-test-reviewer`: maintain a temp-only acceptance test where UID 997 runner launches UID 999 worker, a bounded descendant writes a heartbeat, timeout cleanup stops it, and the descendant self-exits within six seconds if cleanup fails; also cover fail-closed gate handoff timeout and stopping later manifest commands after incomplete cleanup.
- `e2e-runner`: execute that selector in the existing Ubuntu-24.04 WSL profile with `Delegate=yes`; record exact source/test head, cgroup path/properties, capabilities, command, result, and cleanup.
- `functional-test-reviewer`: author deterministic helper tests for unavailable delegation and gated-launch failure; Codex implements least-privilege cleanup and reconciles the systemd sandbox specification and evidence.
- Fresh reliability/security/architecture reviewers: inspect the exact post-test head; no real process result may be upgraded from the scoped WSL profile to general platform proof.
- GPT-PM: exact final S2 gate only after remaining acceptance evidence is ready.

## Unknowns

The initial read-only systemd preflight established that this WSL host can run a transient `Delegate=yes` unit whose cgroup directory is writable by `vst-runner` and exposes `cgroup.kill`. Exact-head evidence at `a6ea0dc` subsequently established a runner-owned mode-0700 `/run/vst-runner`, real cross-process `flock` serialization, and removal of a synthetic stale scope only after confirming `populated=0` and empty `cgroup.procs`; see `docs/sdlc/evidence/s2-restart-fence-exact-a6ea0dc-20261027.md`. A separate bounded read-only namespace observer found no Windows-drive or host-backed mount candidates in its 29-row view; details and limits are in `docs/sdlc/evidence/s2-current-namespace-snapshot-a6ea0dc-20261027.md`. These observations do not establish a persistent runner service, stable delegated-parent behavior across replacement, populated-scope cleanup, runner crash/restart recovery, Windows Job Object nesting, or a complete signed E5 preflight.

Change 0470 proposes a dedicated persistent manifest-runner service; its first GPT-PM adjudication
returned `MODIFY` with three MAJOR and one MINOR design findings. The revised proposal now records
the required manager-mediated predecessor stop/fence, the Supervisor/Store grant issuer and
fail-closed key lifecycle, and a daemon-only OS execution boundary with grant plus durable
pre-dispatch claim. This remains a proposal: it is not approved, implemented, provisioned, or
runtime-proven. See `docs/sdlc/evidence/s2-persistent-runner-service-design-20261027.md` and the
correlated decision IDs recorded there.

## Attribution

Executor: Codex. Change 0470 records the approved design only; the source implementation is
tracked separately in change 0471 and does not establish acceptance without assigned evidence.

## Persistent runner entry point follow-up

Repository inspection at documentation HEAD `2da827b` found `run_manifest_commands` only as a
library entry point; `Supervisor.start_worker` accepts a caller callback and does not host or
dispatch manifest runs. The current working tree now adds a bounded foreground daemon and
authenticated local Unix-socket contract, signed one-use run grants, atomic pre-dispatch `PENDING`
claims, non-replayable `INDETERMINATE` recovery, signer-side peer-cgroup enforcement, and
race-resistant peer PID binding with `SO_PEERPIDFD`. These source controls are implemented but
unreviewed against the exact final diff and not tested or runtime-proven. Systemd's
delegated-subtree ownership, installation, migration, restart behavior, and exact production-call-
path evidence remain open. See `docs/sdlc/evidence/s2-persistent-runner-service-design-20261027.md`
and the current implementation record in `docs/changes/0471-implement-s2-persistent-runner-service.md`.
GPT-PM owns architecture adjudication; Codex owns the in-repository implementation; the operator
owns host provisioning and authorization. No runtime, crash, process-kill, or policy-restricted
scenario is implied by source implementation.
