# S2 persistent runner deployment contract

This directory contains unit templates for the source implementation in
`tools/vst/runner_service.py`, `tools/vst/supervisor_service.py`,
`tools/vst/dispatcher_service.py`, and `tools/vst/signer.py`. The templates and installers are preparation only. No
account, key, unit, runtime directory, database migration, or service has been
provisioned or started by these files in the current coding pass.

## Runtime roles

- `vst-runner` (UID:GID `997:988`) is the only runner daemon identity and owns
  the delegated cgroup. This fixed identity matches the narrowly scoped worker
  helper.
- `vst-worker` (`999:989`) runs manifest-pinned commands. The setuid helper
  clears supplementary groups, drops permanently to this identity, clears and
  reads back all Linux capability sets, and sets `no_new_privs` before the gate
  can execute a command.
- A separate `vst-dispatcher` identity is the only permitted runner-socket
  peer. It has no cgroup write access and may request grants only for
  Supervisor-accepted dispatch intents; it never creates or signs grants
  locally. `vst-dispatcher.service` consumes only filtered Store-backed intents
  over authenticated Supervisor IPC and forwards the exact grant to Runner.
  It does not list tasks or choose work. The separate `dispatch_owner` peer
  submits one exact intent under a root-owned principal mapping; Supervisor
  compares that authenticated principal with the live Store story owner.
- `vst-dispatch-owner.service` is an unprivileged, socket-activated relay.
  `vst-dispatch-owner.socket` accepts one bounded, single-frame AF_UNIX request containing an exact signed
  dispatch instruction. The relay validates its public signature and forwards the same envelope
  to root Supervisor, which verifies it independently. The unprivileged relay has no Store path,
  assignment authority, task queue, retry loop, persistent writable data path, runner socket, private key, or network
  family. Its private temporary directory exists only for bounded OpenSSL verification. Every
  service termination runs a narrowly scoped root `ExecStopPost` helper that first synchronously
  stops the socket and confirms it is inactive, then persists an admission fence; startup refuses
  while the fence exists. The stop hook has no timeout, so an unconfirmed stop or unhealthy durable
  `/etc` can hold service shutdown indefinitely. If latch persistence fails after socket shutdown,
  the socket is inactive at that point, but no latch guards a later explicit start and cross-reboot
  safety is unproven. Ambiguous Supervisor results
  return `reconciliation_required` when possible, then exit without another request. Reopening
  requires independent Store/request-ID reconciliation and a separately authorized root action.
- A separate `vst-signer` identity serves the signer socket. Its primary GID
  is `988` so only the runner group can connect; its private signing key and
  replay ledger remain signer-owned.
- `vst-supervisor-client` is the shared Supervisor-socket access group for the
  authenticated dispatch owner, dispatcher, runner, and signer. It must not
  include the worker identity.
- The root Supervisor alone opens the Store and signs execution grants. RPC
  peers are pinned by UID/GID, exact systemd cgroup, and `SO_PEERPIDFD`.
  The fixed runner peer may claim an exact grant, query that grant's claim
  state, reserve its one allowed launch, and complete it. Status and reservation
  requests require the signed grant and active service generation; no operation
  transfers work to a replacement generation. The signer may check
  PENDING/EXECUTION_RESERVED authority but cannot claim or reserve work.

The dispatcher UID/GID and signer UID are assigned when the dedicated WSL
instance is provisioned. They must be distinct from `997:988`, `999:989`, and
each other. No free numeric IDs are assumed by the source contract.

## Paths and state

The fixed runner unit is `vst-runner.service` in
`/system.slice/vst-runner.service`. `/run/vst-runner` is preserved across a
systemd restart, mode `0710`, daemon-owned, and grouped to the dispatcher. The
admission lock is daemon-owned mode `0600`; the root fence records and checks
its device and inode. A changed lock or cgroup identity refuses admission.
The unit's graceful stop timeout is 1900 seconds to cover the maximum
1800-second signed execution deadline, 90-second completion slack, and cleanup
overhead. `SendSIGKILL=no` remains set; an overrun therefore fails the manager
transition closed instead of claiming a clean stop.
If the runner cannot establish whether an exact claim or launch reservation committed, it sends a
bounded `REFUSED` response when possible and exits nonzero. `Restart=on-failure` starts a new
service generation; startup recovery terminalizes predecessor `PENDING` and `EXECUTION_RESERVED`
claims as `INDETERMINATE`. The old generation never retries or reclaims an ambiguous launch. A
reserve error whose exact status remains `PENDING` also fail-stops; no same-generation retry is
attempted.
Once reservation has been confirmed, any exception before the Supervisor confirms durable
`COMPLETE` sends `REFUSED` when possible and exits nonzero so startup recovery can mark an
unfinished predecessor `INDETERMINATE`. Exact `COMPLETE` replay remains safe; ordinary refusals
before reservation do not restart the unit.
A failed initial claim followed by an exact-shape `NOT_FOUND` for the current generation is an
ordinary refusal because no durable claim exists; the daemon remains available. `NOT_FOUND` at
the reservation boundary after claim admission remains fatal and rotates the generation.
Signer socket client and handler operations have a 10-second bound and a
4-KiB response cap; the client reads the complete response through EOF rather
than assuming one stream `recv()` returns the full JSON message.

The root fence keeps its append-only, hash-chained ledger in a root-only
directory (mode `0700`) and publishes the current record as a root-owned,
read-only JSON snapshot (mode `0644`) under a separate root-controlled
directory. The runner and Supervisor check the snapshot hash, systemd
`InvocationID`, `ControlGroup`, and live cgroup/lock inodes before accepting a
grant. First install requires an explicit `bootstrap` operation after inventory
proves the unit inactive and the reserved UIDs and cgroups empty. A reboot does
not silently recreate the baseline.

The root Supervisor configuration at `/etc/vst-runner/supervisor-service.json`
contains absolute paths for the Store, external anchor, root-only event and
startup keys, a root-owned run-bound preflight record and an operator
verification key, its exact run ID and nonce, grant key ID/private-key
path/public-key ring, OpenSSL executable,
generation snapshot and lock, fixed runner unit/cgroup, socket path and its
group, plus exact peer UID/GID/cgroup/operation entries for `dispatch_owner`,
`dispatcher`, `runnerd`, and `signer`. The `dispatch_owner` peer also carries
its root-owned principal mapping. The model-provenance map binds each allowed resolved
model ID to one SHA-256 digest. Configuration and its parent directories must
be root-owned and not group/world writable.
`allow_schema_upgrade` is an explicit boolean and must remain `false` unless the
schema-v6 migration has received its separate review and application is
authorized. A v5 Store refuses Supervisor startup while this value is false.

An optional `operator` Supervisor reconciliation peer is inactive by default;
it exists only when an operator explicitly provisions and configures its peer
identity and transport. Deployment does not generate operator credentials.

At startup, the root service reads the root-owned mode-0600 measured probe JSON
and verifies its exact run/spec/nonce, required checks and operator network-policy
attestation against the installed
`docs/SANDBOX_SPEC.md` digest, then idempotently records that exact run/nonce
tuple in the append-only Store only after startup reconciliation and event-chain
verification succeed, before exposing its socket. An integrity-locked Store
refuses even that preflight write. A restart may confirm
the same tuple; any changed run, nonce, spec digest, or probe digest refuses
startup. The record and service verification keys are root-owned mode `0600`;
the operator key is not copied into runner, worker, or reviewer identities.

The runner configuration at `/etc/vst-runner/runner-service.json` contains the
daemon UID/GID (`997:988`), dispatcher socket/cgroup identities, canonical
repository path, signer and Supervisor socket paths, public grant-key ring,
worker IDs, audience, bounded request/output/deadline limits, and the worker
helper's exact absolute path, full commit, source digest, and binary digest.
`worker_exec_helper_path` must equal
`/usr/local/libexec/vst-s4-worker-exec-<full-40-character-lowercase-commit>`
for `worker_exec_helper_head`; dispatcher and worker requests cannot select
that path. At startup and immediately before each child launch, the runner
revalidates the root-owned regular file, `vst-runner` group, mode `4750`,
binary digest, and embedded build identity. There is no fallback to another
helper. `daemon_gid` is required by the configuration schema and must be
`988`; omission is a configuration error. The old unversioned
`/usr/local/libexec/vst-s4-worker-exec` is left untouched. Lock inodes are read
from the published root snapshot at runtime, not copied into static
configuration.

The source installer does not generate this privileged Runner configuration.
Deployment must provision it as a root-owned artifact from the exact audited
runtime/helper build record; the helper path, source digest, and binary digest
must agree with that record. A missing or stale configuration is a startup
failure, not permission to select a helper from a request or to fall back to
the legacy path.

The signer configuration at `/etc/vst-runner/signer-service.json` binds the
signer key and persistent replay-ledger paths, `vst-runner` peer UID/GID and
service cgroup, public grant-key ring, OpenSSL path, audience, and Supervisor
socket. The worker receives neither the signer group nor the supervisor-client
group.

## Dispatcher failure handling

`vst-dispatcher.service` uses `Restart=no`. An uncaught Supervisor RPC, Store,
grant, or runner error stops delivery and is emitted to the service journal; the
dispatcher does not retry automatically because a runner response can be
ambiguous. Before any manually authorized restart, the operator must inspect
the dispatcher/Supervisor/Runner journals and the exact grant's durable claim
state. `PENDING`, `EXECUTION_RESERVED`, or `INDETERMINATE` is not permission to
launch again; follow the existing claim reconciliation boundary. A clearly
pre-launch transient may be recovered only after verifying that no runner
claim or child execution began. This source note is not a provisioned runbook
or evidence that journal/claim recovery was exercised in WSL.

## Isolated Python launch

The systemd units use `python3.12 -I -S -c` and explicitly add the immutable,
root-owned `/opt/vst-runtime` deployment artifact to `sys.path` before importing
the service entry point. This path insertion is intentional and does not use a
working directory or environment variable. Python isolated mode removes both
the current directory and the script directory from `sys.path`; see the
[official Python command-line documentation](https://docs.python.org/3.12/using/cmdline.html#cmdoption-I).
`tools/qa/install_wsl_runtime.ps1` packages only the requested committed HEAD
from the one canonical `D:\Repo\Virtual_scrum_team` checkout and streams the
bounded Git archive over `wsl.exe` stdin. The host script verifies HEAD and its
committed bytes; the Linux bootstrap verifies the archive digest and member
allowlist, Ubuntu/WSL identity, disabled automount/interop, no `appendWindowsPath`,
and absence of Windows-drive mounts. It extracts runtime modules and the matching
`docs/SANDBOX_SPEC.md` into a root-private, per-attempt
`/run/vst-deploy-<HEAD>-<transfer-id>` directory; no drive mount or second
checkout is used.

Before either installer mutates a fixed destination, the bootstrap checks every
runtime path. An existing runtime directory is accepted only with the matching
HEAD/archive manifest and byte-identical runtime/spec tree; existing unit files
must be root-owned mode `0644` and byte-identical. The helper installer compiles
the expected binary first and accepts an existing helper only when its digest
and embedded HEAD/source identity match, then repairs its fixed owner/mode. Each
new transfer uses a fresh random ID, so an interrupted source extraction does
not block a retry. Unrelated pre-existing state is preserved and causes refusal.
This is source-only, unreviewed, and unexecuted; it does not establish E5 or
deployment acceptance.

## Installation and verification boundary

`tools/qa/install_wsl_runner_runtime.sh` installs the immutable Python source
artifact and six unit files. It accepts only matching prior artifacts and
refuses to replace mismatched host state; it does not enable or start units.
`tools/qa/install_wsl_worker_helper.sh` builds the fixed C helper from the same
committed source revision. These scripts are not run during code completion.
The exact-head artifact-only installation for change 0476 is recorded in
`docs/sdlc/evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`;
the three installed units were not enabled or started. This records artifact
presence only, not service acceptance.
The one-time `bootstrap` fence action, key provisioning, systemd enable/start,
database schema upgrade, and all runtime evidence wait until the code and
security review phase and a cleanly provisioned dedicated WSL host.

Functional and E2E test authoring/execution belongs to the designated test
agents after all S2 coding is complete. Required policy selectors and forbidden
process/crash/mutation scenarios remain `NOT_RUN`. A successful install or
unit startup alone is not S2 acceptance; acceptance also requires exact-head
tests, restart evidence, reviews, and a correlated final GPT-PM decision.
