# S2 POSIX cross-UID process cleanup design

Status: implemented in the S2 working tree; exact-head and WSL runtime acceptance pending, 2026-10-27.
Scope: VST-013 / S2 E4.1 and VST-017 bounded process cleanup in the existing Ubuntu-24.04 WSL sandbox.

## Goal and constraints

The runner must stop a worker and every descendant after timeout, normal root exit, output-reader failure, or runner cleanup, even when runner UID and worker UID differ. Keep the worker's effective/permitted/inheritable/ambient capability sets empty. Do not give the runner broad `CAP_KILL`, use a shell, or fall back to a best-effort success when containment is unavailable.

## Options and decision

1. **Grant `CAP_KILL` to the runner.** Small change, but the capability can signal unrelated processes in the runner's user/PID namespace. Rejected as broader authority than the worker process tree requires.
2. **Use a systemd-delegated cgroup-v2 child per worker command.** The trusted runner can create and kill only a child cgroup under its own delegated service subtree. Chosen; the scoped destructive boundary matches the process tree.
3. **Install a custom privileged root helper.** Could encapsulate launch and kill, but requires privileged binary ownership/install/review and introduces a new root trust surface. Rejected while the existing systemd delegation boundary is available.

## Design

The runner service must have `Delegate=yes` and run on unified cgroup v2. For each POSIX launch using a distinct worker UID/GID, the runner creates a unique child cgroup under its delegated cgroup and requires `cgroup.procs`, `cgroup.events`, and `cgroup.kill`. It starts the fixed `/usr/bin/setpriv` helper with a sanitized environment before the first child `exec`, then launches a trusted, isolated (`python -I -S`) exec gate under the worker UID. The gate starts with the same fixed, sanitized environment that contains no loader hooks or Python startup controls. The intended worker environment is sent as data through a separate inherited pipe, never as the helper/gate process environment. The gate waits on a second inherited pipe; the worker command has not executed yet. The runner moves the gated process PID into the child cgroup, starts output readers, then releases the gate to `execvpe` the original argv with the supplied worker environment. Descendants inherit the cgroup even if they change session or process group.

On timeout, root-command exit, reader failure, or exceptional cleanup, the runner writes `1` to that command's `cgroup.kill`, waits for `cgroup.events` to report `populated 0`, reaps the root process, closes capture pipes, and removes the empty child cgroup. Each command owns a unique scope; concurrent commands never share a kill target. Windows continues to use the existing Job Object path. The all-descendant guarantee applies to distinct-UID worker launches that use this cgroup path; same-UID compatibility calls retain the legacy process-group behavior and are outside this S2 acceptance guarantee.

## Failure behavior

- Missing unified cgroup v2, missing `Delegate=yes`, unwritable delegated parent, or absent cgroup control files: refuse to execute a distinct-UID worker and return a non-approving containment result.
- Failure to attach the gated PID: close the gate without releasing the requested command, reap the no-op trampoline, and return non-approving. The trampoline runs only with the fixed sanitized environment until attached, so inherited dynamic-loader variables cannot execute code before containment.
- Failure to kill/reap the cgroup or confirm `populated 0`: return `EXIT_CAPTURE_INCOMPLETE`, preserve diagnostics, never report PASS, and stop launching later commands from the same manifest run.
- Distinct-UID launches in one runner process are serialized, and waiting for admission consumes the same per-command/overall time budget. If the budget expires while queued, the runner returns timeout without creating a cgroup or starting a process. If a scope's kill/removal remains unconfirmed, latch the failure and refuse subsequent launches from that process. A new runner must not be admitted until its outer service/sandbox boundary has stopped or fenced the prior scope.
- The exec-gate environment handoff is nonblocking and shares the command deadline. If the gate cannot receive the environment before the deadline, close the gate and kill its cgroup without releasing worker code.
- Do not add `CAP_KILL` as a fallback. The outer service timeout is only emergency cleanup, not acceptance evidence.

## Rollout and rollback

Provision the runner systemd service/scope with `Delegate=yes` and retain the existing memory, task, time, private-network and temp-filesystem limits. Validate delegation before enabling worker commands. Rollback reverts the code/config contract and leaves cross-UID POSIX execution refused; it does not restore broad process-kill capability.

## Verification plan and owners

- `functional-test-reviewer`: maintain a temp-only acceptance test where UID 997 runner launches UID 999 worker, a bounded descendant writes a heartbeat, timeout cleanup stops it, and the descendant self-exits within six seconds if cleanup fails; also cover fail-closed gate handoff timeout and stopping later manifest commands after incomplete cleanup.
- `e2e-runner`: execute that selector in the existing Ubuntu-24.04 WSL profile with `Delegate=yes`; record exact source/test head, cgroup path/properties, capabilities, command, result, and cleanup.
- `functional-test-reviewer`: author deterministic helper tests for unavailable delegation and gated-launch failure; Codex implements least-privilege cleanup and reconciles the systemd sandbox specification and evidence.
- Fresh reliability/security/architecture reviewers: inspect the exact post-test head; no real process result may be upgraded from the scoped WSL profile to general platform proof.
- GPT-PM: exact final S2 gate only after remaining acceptance evidence is ready.

## Unknowns

The read-only systemd preflight established that this WSL host can run a transient `Delegate=yes` unit whose cgroup directory is writable by `vst-runner` and exposes `cgroup.kill`. The implementation must still verify child-cgroup creation, PID placement, kill and removal in the exact bounded service profile. No persistent production service deployment is established by that preflight.

## Attribution

Executor: Codex. This design does not itself change source or establish acceptance.
