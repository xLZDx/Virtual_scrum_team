# S2 persistent runner service design and implementation record

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Observed documentation HEAD before this note: `2da827be982d3f2d6f2adf152668af6ff8007f21`  
Status: source implementation is present in the canonical checkout working tree; it has not been
tested, provisioned, runtime-proven, or accepted. GPT-PM's correlated decision approved design
only; implementation still needs exact-diff specialist review and a fresh exact-head GPT-PM gate.
Correlated design decision: request
`0ea02a82-72ba-44dc-a431-213d99bf8192`, reply
`62890e6f-0fc5-432c-8bde-ba46be1fad8b`, job `411b4d13-4c15-400c-85f6-54c8f7db289b`.

## Goal

Close the S2 restart-fence deployment gap by ensuring every real call to
`run_manifest_commands` runs inside one persistent, stable, delegated systemd service cgroup.
Replacement processes must inherit the same parent cgroup and shared admission-lock directory,
then reconcile abandoned command scopes before accepting another run.

## Non-goals

- Do not weaken the fail-closed POSIX identity and cgroup checks or claim Windows support.
- Do not create a no-op unit or use a synthetic `systemd-run --wait --collect` unit as evidence.
- Do not add arbitrary command execution, remote access, shell evaluation, policy-selector
  execution, process-kill/crash scenarios, or a new test entry point that bypasses manifests.
- Do not provision accounts, install the units/helper, enable services, migrate the Store, or
  mutate host state during this source-code pass. Deployment preparation is recorded in
  `tools/vst/systemd/README.md`.
- Do not begin S3 work or approve S2 from a design note.

## Current behavior and constraints

- `tools/vst/runner.py::run_manifest_commands` now requires an `ExecutionAuthority`, binds each
  manifest/run field and bounded execution deadline to one signed grant, claims it durably before
  the first child, and persists the validated receipt through the Supervisor before returning it.
  Store completion appends the same receipt to the normal `receipts` table and
  `RECEIPT_APPENDED` hash chain in the claim-completion transaction; gate reads and retry tips
  therefore use the ordinary receipt path. This source path remains untested.
- `_DelegatedCgroup._runner_parent` reads `/proc/self/cgroup`; stale-scope reconciliation can
  only inspect strict `vst-command-<pid>-<uuid>` children under that current process's parent.
  The new fixed persistent unit and root lifecycle fence provide the source contract for keeping
  the same manager-owned parent across process replacement; this behavior remains unverified.
- `tools/vst/signer.py::AuthenticatedSigner` provides the persistent Unix-socket signer and pins
  runner peer credentials, pidfd, cgroup, signed grant, active service generation, and current
  Store `PENDING` claim.
- `tools/vst/runner_service.py` provides the manifest-only runner entry point;
  `tools/vst/supervisor_service.py` provides the root-owned authenticated grant/Store boundary.
  `Supervisor.start_worker` remains the separate callback-based lifecycle coordinator.
- The current source tree contains the runner, Supervisor and signer service entry points, fixed
  units, lifecycle fence, and exact-HEAD installers. Existing transient-unit evidence is not
  restart evidence and does not establish that these new paths work.

## Options and decision criterion

1. **Preferred: add a small foreground runner daemon with a private local Unix socket.** The
   daemon is the sole production entry point for manifest-bound runs, validates each bounded
   request, calls the existing `run_manifest_commands` library, and returns a receipt/result.
   A persistent systemd unit owns its cgroup parent and `/run/vst-runner` lock directory across
   process replacement. This directly connects the deployment invariant to real work.
2. **Integrate the library into an identified existing trusted service.** This avoids a new
   daemon, but no such in-scope service entry point is currently identified in repository
   evidence. It remains viable if a concrete caller is named and can guarantee the same unit,
   cgroup, lock, and restart behavior.
3. **Keep transient invocation and waive persistence.** Rejected for S2 acceptance because the
   current evidence does not show that replacement invocations share the predecessor's cgroup
   parent or reconcile its scopes.

The decisive criterion is observable proof that the same stable service boundary owns actual
manifest-run calls before and after replacement, while preserving the existing worker/signer
separation and fail-closed recovery.

## Proposed design

### Service boundary

- Add a foreground `python -I -S -m tools.vst.runner_service` entry point. It loads a root-owned,
  non-writable service configuration from a fixed path, resolves the repository/run root once,
  validates that configured `vst-worker` UID/GID differs from the runner and signer identities,
  and refuses unsupported platforms or cgroup v2/delegation profiles before binding its socket.
- Bind one Unix stream socket under the provisioned `/run/vst-runner` directory, owned by
  the fixed `vst-runner` daemon identity (`997:988`) and the dedicated dispatcher group with mode `0710`; the group may traverse but
  cannot list or write the directory. Keep the shared admission lock owned by the daemon with
  mode `0600`, and the socket mode `0660` for the dispatcher group. The worker must not belong to
  that group. Authenticate each peer with `SO_PEERCRED`; reject unexpected UID/GID and
  malformed or oversized messages before dispatch. The candidate worker is never a permitted
  client and cannot read or write the socket directory.
- Accept only a versioned, bounded JSON request containing an immutable manifest digest, slot,
  attempt/epoch, signed run authorization, and relative artifact paths. Do not accept `argv`,
  parser functions, signing keys, arbitrary environment entries, or caller-supplied
  cwd/UID/GID/model/runner identity as authority. Derive worker identity, signer socket, working
  root, environment, and limits from trusted service configuration.
- The manifest must come from a trusted source and its provenance must be verified before
  dispatch. Existing `validate_task_manifest` and `manifest_sha256` validate structure/digest,
  not author authenticity. The proposed execution authorization is a signed, bounded grant
  verified against a provisioned trust root, binding manifest digest, task, slot, attempt, epoch,
  run ID, invocation ID, resolved-model provenance, and expiry. Peer UID authentication alone
  does not authorize arbitrary manifests. The grant includes a unique `grant_id`, `request_id`,
  and service audience; the caller cannot change any of them without invalidating its signature.
  **Grant authority and trust root:** the sole issuer is the trusted Supervisor/Store
  authorization transaction, never the runner daemon, dispatcher, or caller. Before signing,
  it verifies current task registration, immutable manifest digest, authorized test slot,
  attempt and epoch, current lease/fence, run-bound preflight, remaining budget, and active
  service generation. Grants have a 30-second claim window and an expiry covering the signed
  overall execution deadline (capped at 1,800 seconds) plus 30 seconds of completion slack. Store
  accepts a new claim only inside the claim window; a PENDING grant remains verifiable through the
  bounded run deadline. An expired COMPLETE grant may return only its identical stored receipt;
  it cannot start new work. The canonical, versioned grant uses a distinct signature domain
  (`VST_EXECUTION_GRANT_V1\0`) and binds the audience, service generation, manifest, task, slot,
  attempt, epoch, run/invocation/request/grant IDs, resolved-model provenance, and expiry.
  The grant uses Ed25519 signatures with the root-owned OpenSSL `pkeyutl` provider: only the
  Supervisor reads the issuer private key, while the runner receives a key-ID-indexed public-key
  ring. OpenSSL and key paths are absolute, root-owned, and non-writable by group/other; the
  signature input is a bounded regular temporary file so Ed25519 verification does not depend on
  an unknown-length stdin stream. Unsupported OpenSSL/Ed25519/key conditions refuse admission.
  The official OpenSSL interface requires `-rawin` for Ed25519 before OpenSSL 3.5 and describes
  its one-shot input requirement: https://docs.openssl.org/3.1/man1/openssl-pkeyutl/.
  Root-provisioned private key custody is restricted to the issuer; the daemon has only a
  separately provisioned verification trust root. Key IDs, rotation, revocation, and an
  unknown-key fail-closed rule are part of the signed root-owned trust configuration. STOP,
  epoch/fence changes, grant revocation, or service-generation replacement invalidate unused
  grants. The durable Store `PENDING` claim rechecks current authority immediately before
  dispatch; a grant cannot restore authority revoked by Supervisor/Store. No key is provisioned
  by this proposal. Operator owns actual host key provisioning; Codex owns the implementation
  contract and evidence.
- Resolve the manifest from the configured immutable/read-only registry by its authorized digest,
  verify the digest against canonical bytes, and dispatch only through `run_manifest_commands`.
  Restrict each grant to its exact manifest, slot, attempt, epoch and one invocation. The
  production boundary uses the existing fixed `vst-runner` daemon (997:988), a distinct
  dispatcher UID/GID, and the fixed `vst-worker` (999:989). This preserves the operator-approved
  narrow helper contract; do not create an alternate per-sprint checkout or daemon user. Only the daemon
  identity may write the delegated cgroup and create command scopes; dispatcher and worker
  identities have neither cgroup write access nor execution authority. Daemon code/config are
  root-owned and non-writable to those identities; requests cannot choose a library entry point,
  signer socket, cgroup, worktree, or executable. A fixed service configuration supplies the
  signer endpoint and execution capability. A static call-site inventory is evidence, not
  enforcement. `run_manifest_commands` itself requires a verified grant plus an atomically
  claimed Store `PENDING` authorization and daemon-only execution capability before spawning the
  first child; direct callers without both are denied before child creation. The signer
  independently validates pinned daemon identity, pidfd-bound peer, cgroup, service-generation
  ID, and invocation-specific grant; a generic invalid-request ping is not authorization. Bind
  `SO_PEERCRED` to Linux `SO_PEERPIDFD`, keep the pidfd open through validation/request handling,
  require the peer to remain alive, and fail closed when peer-pidfd support is absent. Do not
  authorize from an unpinned PID followed by `/proc/<pid>` lookup. The systemd unit keeps the
  daemon in the manager-reported `ControlGroup` and delegates only its descendant subtree; record
  parent/subtree permissions, identity separation, and all service processes in runtime evidence.
  Root remains trusted. Key material and Store credentials never enter requests, receipts,
  candidate environment, or process arguments.
- Close the production call-path inventory by static search of all import/call sites and by
  runtime enumeration of every process running under the daemon (`vst-runner`), dispatcher
  (`vst-dispatcher`), and worker (`vst-worker`) identities, plus every unit that can access the
  signer socket. The only allowed production caller is the pinned foreground daemon in the
  configured cgroup; tests may call the library only through explicit test fixtures. Any
  alternate service, scheduled task, shell path, or direct production call blocks acceptance.
- Bound request bytes, concurrent requests, per-command/overall deadline, output and response
  sizes. Serialize distinct-UID admission using the existing cross-process `flock`; startup and
  every request fail closed if runtime-directory ownership/mode, lock, delegated parent, or stale
  scope reconciliation cannot be verified. Return structured non-approving errors; never return
  a successful-looking receipt on partial capture or cleanup failure.
- Make duplicate request delivery idempotent with a crash-safe ledger: the database has unique
  constraints on `grant_id`, `invocation_id`, and `request_id`; all three are cryptographically
  bound in the grant. Atomically insert `PENDING` for all three with the authorization/payload
  digest before any command can start; reject a grant, invocation, or request already seen,
  including when replayed with a different request ID; reject same-ID concurrent requests while
  pending; reject a different payload under the same ID; after
  `run_manifest_commands` returns and the complete receipt is durably stored, atomically
  transition to `COMPLETE`. A duplicate `COMPLETE` request returns the exact stored receipt. On
  restart, any surviving `PENDING` request becomes `INDETERMINATE` and is permanently
  non-replayable until explicit signed reconciliation; it is never automatically rerun. A crash
  after signer acceptance but before runner-ledger completion therefore cannot execute the
  command twice or emit a false receipt. The signer ledger is a separate replay/signature boundary
  and does not replace the runner's pre-execution `PENDING` claim.
  The in-repository implementation adds Store schema version 5; the additive migration has not
  been executed. The root Supervisor now verifies a root-controlled run-bound probe and operator
  attestation, idempotently records the exact preflight tuple on restart, and refuses startup on
  changed evidence. The source wires the ledger through authenticated Supervisor IPC and startup
  recovery, but neither the migration nor recovery path has been run in dedicated WSL.

### Persistent systemd contract and lifecycle fence

- Support exactly one manager-controlled systemd unit and normal in-unit process restart. Do not
  support parallel unit instances, transient invocations, unit renames, in-process replacement,
  direct startup, or host reboot without a separately re-authorized bootstrap. Each process
  generation records unit name, manager `InvocationID`,
  manager-reported `ControlGroup`, observed cgroup directory device/inode, lock file device/inode,
  and predecessor fence outcome. `RuntimeDirectoryPreserve=restart` is proposed to retain the
  private runtime directory across restart; actual behavior must be observed before acceptance.
- Set an explicit stop/restart policy, proposed as `KillMode=control-group` and
  `SendSIGKILL=no`, so systemd does not restart the unit while processes remain in its unit cgroup.
  A root-controlled system-manager lifecycle helper is the sole fence writer: the fixed unit uses
  `ExecStartPre=+/usr/libexec/vst-runner-fence start` and
  `ExecStopPost=+/usr/libexec/vst-runner-fence stop`. The `+` command prefix makes both hooks
  privileged even though the service itself runs as `vst-runner`; the manager runs `ExecStartPre`
  before `ExecStart`, and `ExecStopPost` after the stop command but before it completes the unit
  stop/restart transaction. The helper is installed root-owned and cannot be invoked or replaced
  by the daemon, dispatcher, or worker.
  On start it obtains unit name, current `InvocationID`, and `ControlGroup` from systemd; validates
  the durable prior-generation record; then atomically writes a `RUNNING` record for this exact
  invocation before `ExecStart` can admit work. On stop it obtains the invocation and cgroup
  identity from the manager, confirms the only remaining process (if any) is the lifecycle helper
  itself, confirms no command scopes remain, and writes `STOPPED_EMPTY`; any query/check/write
  failure writes or leaves `UNVERIFIED` and prevents the next start. Records are versioned,
  root-owned, append-only or atomically replaced via temp-file, fsync, and rename, and bind unit
  name, predecessor `InvocationID`, manager `ControlGroup`, cgroup device/inode, lock
  device/inode, generation sequence, and observed cleanup outcome. The next `ExecStartPre` must
  match the last `RUNNING` generation to its `STOPPED_EMPTY` predecessor record; a missing,
  duplicate, out-of-order, or mismatched record fails closed. Because systemd also invokes
  `ExecStopPost` after a failed start, that helper may transition only a matching current
  `RUNNING` generation; it must never turn a missing/malformed start record or an older
  `UNVERIFIED` state into `STOPPED_EMPTY`. First install has no inferred clean
  predecessor: a one-time root provisioning step must inventory existing runner identities and
  scopes, establish they are absent, create a generation-zero `BOOTSTRAP_EMPTY` record, and then
  enable the fixed unit. No automated startup may create this baseline from missing state. Startup
  also refuses on changed lock inode, unexpected unit identity, or unexplained delegation
  identity change. If parent path and directory identity are preserved, it reconciles only safe
  empty stale scopes under the shared lock before admission. A changed parent is eligible only
  after a verified empty predecessor fence; path or inode equality alone is insufficient. This is
  a manager-mediated predecessor-stop/fence-before-replacement protocol, not an assumption that
  a unit name or shared lock provides exclusivity.
- The unit owns lifecycle of worker descendants and must not permit an older pre-lock process or
  alternate unit to run concurrently. Before rollout, stop and account for every prior runner
  process; then enable exactly one service instance. Any uncertainty blocks worker admission.
- Resource limits and restart policy must be bounded and explicit. The service must not restart
  indefinitely while unresolved cleanup is present; it should start in a refusing state until
  `reconcile_stale` has completed under the shared lock.
- This note does not prescribe unverified systemd directive semantics. The exact unit and
  runtime-directory preservation behavior require primary-documentation review and exact WSL
  observation before claiming acceptance.

Systemd's cgroup interface describes the unit cgroup as managed by PID 1 while a delegated
service controls its descendant subtree; it also recommends asking the manager for the unit's
`ControlGroup` rather than translating unit names locally. See
https://systemd.io/CONTROL_GROUP_INTERFACE/ and
https://systemd.io/CGROUP_DELEGATION/. Linux `SO_PEERPIDFD` pins the Unix-socket peer process
identity rather than exposing only a reusable numeric PID; see the upstream kernel change
https://github.com/torvalds/linux/commit/7b26952a91cf65ff1cc867a2382a8964d8c0ee7d. These are
design references; support in the provisioned WSL kernel is not yet runtime-verified.
The proposed `KillMode=control-group` and `SendSIGKILL=no` combination is based on systemd's
documented behavior: the manager targets the unit cgroup and does not restart a control-group or
mixed service while processes from a prior instance remain there
(https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html). The proposal still
requires exact unit validation and runtime observation before this behavior is counted as S2
evidence. `RuntimeDirectoryPreserve=restart` preserves the configured runtime directory on
automatic and manual service restart, but not system reboot; see
https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html. The fence record must
therefore fail closed when manager invocation identity or runtime state cannot be reconciled.
The `+` prefix on `ExecStartPre=`/`ExecStopPost=` is systemd's documented privileged-command
exception to the unit's `User=` setting; see the same `systemd.exec` reference. Exact directive
support and the helper's effective credentials still require validation in the provisioned
system manager.
systemd documents that `ExecStopPost=` runs after stop and also after start failure, and that
restart consists of stop followed by start; see
https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html. The hook contract
above accounts for those cases and never upgrades absent start evidence to a clean predecessor.

## Failure modes and required behavior

| Failure | Required behavior |
|---|---|
| Unsupported OS, missing `SO_PEERCRED`/`SO_PEERPIDFD`, or non-unified/missing delegation | Service refuses startup; no worker command starts. |
| Wrong peer UID/GID or cgroup, candidate peer, oversized/malformed request | Reject before dispatch; signer refuses direct library calls outside the configured runner service cgroup; record bounded diagnostic without request secrets. |
| Missing/untrusted config, private runtime directory, signer socket, or lock | Refuse admission and return a non-approving result. |
| Cgroup parent differs after restart or contains unknown stale scope | A changed parent is eligible only after the manager-mediated predecessor record proves `STOPPED_EMPTY`, current unit/generation/lock identities pass fresh admission checks, and only safe empty scopes require reconciliation; otherwise remain unavailable. Unknown or populated scopes always remain unavailable and are never killed or adopted. |
| Crash after atomic `PENDING` claim but before durable `COMPLETE` receipt | Restart marks the request `INDETERMINATE`; return no approving receipt and do not replay absent explicit signed reconciliation. |
| Worker timeout, capture failure, or cleanup not confirmed | Preserve existing non-approving receipt semantics; reconcile under the same stable parent before a later admission. |
| Two service instances or rolling replacement overlap | Shared lock serializes compliant calls; signer cgroup allowlist plus unit provisioning must prevent an alternate production caller or second parent and refuse if stable-parent identity cannot be established. |

## Rollout and rollback

1. Obtain GPT-PM adjudication of whether this service is required and whether the proposed request,
   idempotency, and restart boundaries satisfy S2 architecture.
2. Complete the final source/documentation pass in the canonical checkout only; launch actual
   specialist reviewers against the exact diff before the functional-test phase.
3. Run the required focused tests only through the designated functional test reviewer, followed
   by a bounded e2e-runner runtime run after coding is complete. Record exact source head, service
   unit hash, UID/GID, cgroup path before/after replacement, lock path/inode, requests, and outcomes.
4. Provision the unit only after code review and explicit runtime change authorization; preserve
   previous config and provide a rollback that stops the new unit, prevents parallel old/new
   runners, restores prior config, and leaves existing scopes available for safe reconciliation.
5. Do not claim Phase 8 acceptance until GPT-PM reviews exact-head code, required test/runtime
   evidence, and the other outstanding S2 criteria.

## Test and verification plan

After code completion, the `functional-test-reviewer` authors/runs focused tests for request schema
and size bounds, peer authentication, manifest-only dispatch, config ownership/mode, duplicate
request semantics, deadline/output limits, fail-closed startup, and restart reconciliation. The
`e2e-runner` then proves that an actual `run_manifest_commands` call is served by the persistent
unit and that a replacement process reports the same delegated parent and lock identity before
reconciling the controlled safe stale-scope fixture. No crash, process-kill, mutation, or restricted
policy selector is implied; those retain their current `NOT_RUN` state unless separately authorized.

## Unknowns / owners / next actions

- **Codex:** completed the initial source implementation in the canonical checkout; owns remaining
  code reconciliation, actual test/review coordination, and bounded runtime evidence collection.
  Preserve the one-checkout rule.
- **GPT-PM:** the prior correlated decision was `MODIFY`. It identified three MAJOR
  findings and one MINOR: incomplete predecessor lifecycle fencing; undefined grant issuer/key
  trust lifecycle/current-authority checks; and cgroup membership alone failing to prevent a
  same-UID/direct-library caller. This revision addresses those design points with a manager-
  mediated predecessor fence, a named Supervisor/Store grant authority and fail-closed key
  lifecycle, and a dedicated daemon OS identity with an unavoidable Store/grant/capability check
  before child creation. The MINOR is addressed by limiting replacement modes and recording a
  service-generation identity. Source controls for those design points are now present in this
  working tree; they remain untested and unreviewed against the exact final diff.
  Focused architecture/security reviewers previously found no design-level finding in their
  narrower scope; that did not supersede GPT-PM's broader contract findings. Fresh focused
  architecture and security follow-ups reviewed M01-M03/N01 after correction and found no
  remaining design-level issue. GPT-PM then returned correlated `ACCEPT — DESIGN ONLY`, closing
  those four findings. The reply added non-blocking `S2-RF-SVC-N02` for changed-parent failure
  wording; the failure-table row is reconciled and focused verification is pending. Reviewers and
  GPT-PM explicitly retain manager directive/effective-credential behavior, implementation,
  provisioning, and runtime behavior as unverified. See
  `s2-persistent-runner-service-gptpm-review-20261027.md`.
- **Operator:** provision/attest the persistent systemd unit and authorize actual host-state
  changes; this note performs no provisioning.
- **Functional-test-reviewer / e2e-runner:** own post-code tests and runtime evidence under the
  global test ownership rule.

Design state: `ACCEPTED — DESIGN ONLY` (N02 wording verification pending). The working-tree
implementation has not been tested, reviewed against its exact final diff, migrated, provisioned,
or runtime-proven. This note adds no test, runtime, provisioning, waiver, or candidate-acceptance
evidence. S2 Phase 8 remains `NOT APPROVED`.
