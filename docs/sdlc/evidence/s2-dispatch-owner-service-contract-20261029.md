# S2 dispatch-owner service contract — 2026-10-29

## Decision and scope

This note defines the smallest in-repository ingress adapter needed to make the already-approved
signed dispatch-instruction path callable. It adds no task source, scheduler, assignment authority,
queue, disk spool, signer, private key, or retry policy. The service accepts one signed instruction
per local stream connection and forwards that exact envelope to the existing root Supervisor RPC.
The root Supervisor remains the authorization boundary and independently verifies the signature,
principal, expiry, live Store ownership/lease, manifest slot, preflight, budget, and generation before
appending an event.

The provenance decision is correlated to PM Bridge request
`7c64c79c-452c-454f-9c55-3143a0fe2976`, user turn
`820712a7-3927-4abd-b115-8755623ac987`, and reply
`4c5606a1-6026-56e3-914b-61c89a7e45a9`. It accepts a purpose-specific signed envelope as provenance
only with independent root Supervisor verification. It does not establish a production issuer or
authorize key creation, privileged provisioning, migration, runtime activation, real dispatch, or
E5 attestation.

## Request and response boundary

- Input is one bounded, length-prefixed canonical JSON object with exactly one field,
  `instruction`; the client must half-close its write side after that frame. Any trailing byte or
  failure to observe EOF within the request timeout is refused before Supervisor RPC.
- `instruction` is the exact v1 signed envelope; no principal, task, lease, worker, command, model,
  artifact, grant, or alternate endpoint is accepted outside that envelope.
- For a currently valid envelope, the owner service validates it against the root-owned public
  trust registry and fixed principal `Codex`, then calls
  `SupervisorClient.submit_dispatch_intent` at the fixed root socket. Supervisor verifies the same
  envelope again using its own root configuration.
- A separate authenticated `replay_dispatch_outcome` RPC is read-only. It returns an exact
  historical result only when the authenticated principal and complete signed envelope match a
  previously accepted result in fully verified Store history. It does not authorize new work or
  fall through to admission. Expired or revoked current credentials may use this route only to
  retrieve that exact accepted result; a miss remains a refusal. If a security incident raises
  doubt about whether the historical acceptance was trustworthy when recorded, this route is not
  an incident adjudicator; dispatch stays closed pending separately authorized security
  reconciliation.
- Success returns the exact bounded Supervisor result. After a complete local `sendall`, the relay
  invokes authenticated `ack_dispatch_intent`; the Store clears the pending admission barrier only
  for that exact result. The acknowledgement means relay-forwarded, not caller-received. The
  configured `dispatch_owner` peer must have exactly `submit_dispatch_intent`,
  `replay_dispatch_outcome`, and `ack_dispatch_intent` operations; no other role receives
  historical replay or acknowledgement authority. Refusal
  returns only a generic error code.
- The service processes connections sequentially, with a fixed request timeout and bounded request
  and response sizes. It stores no task state and performs no automatic retries. A client must
  preserve the original `request_id` when reconciling; Store idempotency binds principal, service
  generation, and the complete signed envelope.
- The caller's Unix-socket group membership only permits reaching this relay. A valid instruction
  signature and Supervisor's live authority checks are still required for durable acceptance. The
  accepted event, idempotency result, and pending-outcome control note commit atomically. If local
  forwarding or acknowledgement fails, the barrier remains pending, the relay stops, and a
  different request ID is refused. Same-generation exact submission retains its idempotency
  behavior. After an ambiguous submission or current-generation refusal, the relay may query the
  separate historical route; Store returns only the exact result from the original generation.
  Expired or revoked instructions may query this route directly, but absent or mismatched history
  is refused and never becomes new admission. The in-repository Runner generation reader binds new
  admission to the active `INVOCATION_ID`; historical replay preserves the original generation.
  The installed restart behavior is not exercised by this source change.
  Store validates the full ordered history at startup and before each new admission/acknowledgement;
  legacy accepted events without this protocol remain unresolved and block ordinary replay.

## Local transport and process identity

- The systemd socket unit owns `/run/vst-supervisor/dispatch-owner.sock`, mode `0660`, owner root,
  group `vst-supervisor-client` (proposed GID 984). Parent directory remains the existing
  root-owned `vst-supervisor-client` directory, mode `0710`.
- Socket activation is `Accept=no`, backlog 1, and exposes exactly one AF_UNIX stream descriptor.
  The service rejects an unexpected PID, descriptor count/name, socket type, or path.
- `vst-dispatch-owner.service` runs as UID 980, primary group `vst-dispatch-owner` GID 982,
  supplementary group `vst-supervisor-client` GID 984, in the fixed cgroup
  `/system.slice/vst-dispatch-owner.service`. UID/GID values are provisional and must be freshly
  rechecked before provisioning.
- The service has no network address family, no Store path, no persistent writable path, no
  capabilities, no private key, and no access to the runner socket. Its private temporary `/tmp`
  is used only by the existing OpenSSL verifier and disappears with the service. It can read only its root-controlled service
  config and public dispatch trust registry, and connect to the root Supervisor socket.
- `Restart=no` alone is not the fail-stop boundary: an active `.socket` unit can reactivate a stopped
  service. `ExecStopPost=+...dispatch_owner_latch.main` therefore runs as root after every service
  termination, including an unexpected exit or failed start. It first issues a synchronous socket
  stop and confirms `ActiveState=inactive`; it retries failed or indeterminate stop/confirmation
  calls with bounded per-call timeouts and capped backoff, and does not proceed while admission is
  unconfirmed. Only after this same-boot barrier does it inspect `/etc` and persist the root-owned
  `/etc/vst-runner/dispatch-owner-admission-blocked.json` fence (root:root `0644`). Both the socket
  and service units have `ConditionPathExists=!` for that fence, and the unprivileged service loader
  checks its existence before accepting the inherited descriptor. `TimeoutStopSec=infinity` keeps
  systemd from killing this safety hook while it confirms socket shutdown or persists the latch;
  consequently a failed systemctl call or unhealthy `/etc` can hold service stop indefinitely and
  requires operator-visible recovery. Persistent blocking across reboot requires healthy durable
  root-controlled `/etc`; if latch creation fails, same-boot socket shutdown is confirmed but
  cross-reboot admission safety is not established. An orderly service stop is also fenced until
  recovery; only the operator, after the reviewed recovery procedure, may clear the file and reopen
  the socket.
- Local framing and canonical-JSON refusals occur before Supervisor RPC. A malformed envelope is
  refused. A validly shaped envelope whose current signature, expiry, or key check fails may only
  query the historical read-only route; a miss is refused and does not call admission. Once a
  currently verified envelope is passed to `SupervisorClient`, a transport error, malformed
  response, timeout, lost connection, or response-binding mismatch triggers a read-only history
  lookup. An exact match recovers the committed result; a lookup error remains outcome-unknown,
  while an explicit refusal with no exact history remains refused. The relay exits with code 75
  whenever an outcome cannot be established safely.
  Systemd runs the root `ExecStopPost` fence before the service stop completes. A queued connection
  may remain in the kernel backlog during teardown; the synchronous stop and inactive-state check
  close the listener before any filesystem inspection that could stall. Until that confirmation,
  the helper remains in `ExecStopPost`, with this unit's stop timeout disabled. If the persistent
  write fails after the socket is confirmed inactive, the helper fails visibly and the listener
  is inactive at that point; without the latch, a later explicit socket start is not guarded. A
  durable `/etc` latch is required before any future reboot or start. The source contract does not
  prove installed-systemd behavior or storage health.
- For the new protocol, a pending accepted result can be recovered only by submitting the same
  signed instruction/request ID through normal admission or querying the separate historical
  read-only route. Store returns the immutable result only after complete Store/control-history
  verification; the relay forwards it and records the exact acknowledgement. A different request
  remains refused until that acknowledgement is durable. No new ID is generated or automatically
  retried. Legacy accepted history, malformed or
  contradictory controls, or an integrity/anchor failure remain closed for separately authorized
  root reconciliation; ordinary replay cannot clear those states. Clearing the existing systemd
  latch remains a separate privileged operation and is not performed by this source change.

## Configuration and source of truth

The non-secret service config fixes the principal to `Codex`, the OpenSSL executable to the
accepted system path, and the public registry to
`/etc/vst-runner/dispatch-instruction-trust.json`. The service config is root-owned, readable by
the dedicated owner primary group, mode `0640`; the public registry is root-owned, mode `0644`, and
contains only key ID, principal, purpose, and public-key path. Public-key files and every parent
directory are root-controlled; each public-key file is a regular root:root `0644` file. No private
key is placed in either artifact.

Both services now read the same fixed public registry path from
`dispatch_instruction.py`: `/etc/vst-runner/dispatch-instruction-trust.json`. The root Supervisor
configuration carries only that exact fixed path, and both loaders require the registry and public
keys to be root-controlled and read-only. Application data access is limited to those files and
the service's own cgroup metadata; the Python runtime and OpenSSL executable are immutable
read-only inputs. There is no copied key map in either service config.
Missing, malformed or unavailable trust data keeps service startup/dispatch fail-closed. No public
key or config value is fabricated in source.

## Acceptance and review boundary

The initial latch draft persisted `/etc` before stopping the socket and used an asynchronous stop
request. Code and reliability reviews identified that filesystem stalls or a failed latch write
could leave the active listener available. The corrected source order is: confirm socket inactive,
then access/persist the latch; the service stop timeout is disabled so the system manager cannot
kill the hook while it holds this barrier. Focused synthetic tests and runtime systemd validation
are tracked separately; this source contract is not runtime proof.

Source acceptance requires review of exact socket activation, bounded single-frame EOF framing,
config ownership, signature validation, one-request behavior, every relay/socket termination path,
the Store pending/ack barrier, ambiguous RPC recovery, and no retry/state/authority expansion.
Synthetic-key contract coverage is authored by `functional-test-reviewer` and executed by
`e2e-runner` only after S2 coding is complete. The production path remains disabled until a genuine
authorized signer and public key, exact authenticated OS identity, reviewed root configuration,
current runtime provenance, and allowed runtime evidence exist. The service template itself is not
provisioning authorization or evidence of a started service.

