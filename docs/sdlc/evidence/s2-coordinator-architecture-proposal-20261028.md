# S2 coordinator architecture proposal — 2026-10-28

> **Status correction (2026-10-28):** The historical proposal sections below predate the latest
> GPT-PM adjudication recorded in the addendum at the end of this file. The earlier request for
> adjudication and statement that no coordinator source may be implemented are superseded only
> within the precise source-implementation scope granted by that correlated response. Runtime,
> migration application, key creation, activation, and S2 acceptance remain separate gates.

## Operator direction

The operator now directs Codex to implement the missing coordinator and to prepare the root-owned
runner configuration and fresh E5 evidence. This supersedes the earlier assumption that the
operator was expected to locate an existing coordinator. It does not authorize fabricated
credentials, signatures, or claims about system isolation.

## Existing in-repository execution boundary

The repository already contains a root Supervisor service, signed one-use execution grants, a
persistent runner service, fixed systemd unit templates, and an integration helper named
`dispatch_authorized_manifest_run`. The helper obtains grants from the Supervisor and forwards
only those grants to the runner. The systemd README records that this helper is not a runnable
production coordinator and that no production caller is established.

The dedicated `Ubuntu-24.04` WSL2 distribution is present. A read-only check on 2026-10-28 found
the runner, Supervisor, and signer root configuration files absent; all three services are
disabled and inactive. Historical E5 records exist for earlier code heads, so they are not fresh
acceptance evidence for current HEAD `70f8953c69276fa9cbc00f2695dde2ca5aded1cc`.

## Proposed minimum coordinator contract

1. Add a local-only coordinator integration to the existing Supervisor/runner path. It must not
   create stories, assign tasks, issue leases, select workers, or maintain a separate queue/spool.
2. Treat the existing root-owned Store task/lease/manifest state as the sole execution authority.
   For every request, the root Supervisor re-reads and validates task owner, active lease, epoch,
   manifest digest, budget, run preflight, and service generation before issuing its existing
   signed one-use grant.
3. Authenticate the coordinator peer with kernel Unix-socket peer credentials and the fixed
   systemd service cgroup. Bind its OS identity to the already restricted `dispatcher` Supervisor
   role. Do not accept caller-selected UIDs, executable paths, commands, model identities, grant
   signatures, or alternate Store paths.
4. Keep transport on a private AF_UNIX socket. No TCP listener, inbound network access, user-writable
   queue, spool, retry after ambiguous claim, or fallback execution path is permitted.
5. Keep Supervisor as the only grant authority and Store as the only durable task/lease authority.
   The coordinator forwards requests; it must not widen operations available to dispatcher peers.
6. Generate any required private keys only inside the dedicated WSL distribution with root-only
   permissions, record public fingerprints only, and refuse service startup when root-owned
   configuration, exact helper/runtime artifacts, or run-bound E5 provenance is missing or stale.
7. Fresh E5 must bind the actual current code/spec digests, run ID, nonce, signed inventory, and
   network-policy attestation. A generated signature is not itself evidence that firewall or host
   isolation controls are enforced; record any property not independently observable as
   `NOT_VERIFIED` and do not claim S2 acceptance from the coordinator implementation.

## Operator-requested pub/sub transport amendment

The operator requests pub/sub to remove point-to-point coordination and avoid debating ownership.
This is adopted as a transport proposal, while task authorization remains unchanged: delivery does
not create permission to run a task.

The repository already has a durable append-only, hash-chained Store event log. `LEASE_ACQUIRED`
records a task, actor, attempt, epoch, and lease ID, but does not include an explicit run/request ID
or the coordinator's authenticated principal. The Store also enforces a closed event-kind set. A
subscriber that reads all leases and chooses work would become a new scheduler and is therefore
not acceptable.

Recommended shape for GPT-PM adjudication:

1. Keep Store and root Supervisor as the only assignment/lease and grant authorities. Do not add a
separate Redis, NATS, RabbitMQ, Kafka, filesystem spool, or user-writable queue.
2. A trusted existing task owner submits one exact dispatch intent through a root Supervisor
operation. The request binds one task, slot, attempt, epoch, run ID, and unique request ID; its
principal comes from authenticated kernel peer credentials and deployment mapping, never from the
message body.
3. Supervisor verifies current task ownership, the live lease, request generation, manifest,
budget, and preflight before durably recording/publishing the authorized intent. The Store event
log may support replay/cursor recovery, but the dispatcher has no direct Store read/write access.
4. The local-only pub/sub adapter sends only that authorized intent to the fixed coordinator peer
over AF_UNIX. Duplicate delivery is idempotent by request ID and canonical payload; stale,
revoked, cross-generation, malformed, or ambiguous requests fail closed without an automatic
retry.
5. The coordinator only invokes the existing grant-forwarding path for the received exact intent.
It cannot enumerate tasks, subscribe to an unfiltered task queue, create tasks or leases, choose a
slot, sign grants, or supply commands/paths.

The open design question for GPT-PM is whether the existing `LEASE_ACQUIRED` Store event plus a
Supervisor-filtered live subscription is sufficient provenance, or whether the event schema and
Supervisor API must add an explicit, owner-authenticated dispatch-intent event. The existing event
does not contain enough request identity to assume the answer. No code, schema change, service
activation, or tests are authorized until this transport amendment is adjudicated. Runtime remains
disabled and `S2-DISPATCH-M01` remains MAJOR/OPEN meanwhile.

## GPT-PM adjudication and mandatory amendment

GPT-PM reviewed the proposal under request `dd7175f5-40f3-4714-932d-dc44dca55cc2`, reply
`c064e8f2-eb6d-5945-97e1-f6f6c71d6b92`, job `e93fd0e2-2097-4e6d-8728-756d7672a99b`, and user turn
`3ecfb955-de1d-4d63-8e05-173846fa7275`. Result: `MODIFY — CONDITIONAL DESIGN`; production runtime
remains disabled and `S2-DISPATCH-M01` remains MAJOR/OPEN. The architecture is acceptable only
after request provenance is explicitly bound to an already-authorized assignment. An authenticated
coordinator process alone is insufficient; it must not select arbitrary work or enumerate tasks.

GPT-PM permits the existing `vst-dispatcher` peer to request a grant for an independently
authorized existing assignment and forward that grant to Runner. It forbids grant signing, task or
lease creation, arbitrary work selection, and direct Store mutation. Root Supervisor remains the
only grant issuer. Each peer must be pinned to its provisioned UID/GID, exact systemd cgroup, and
kernel-verifiable process identity. No dispatcher UID may be hard-coded before provisioning.

### Request-provenance amendment submitted for adjudication

The proposed bound is:

1. The trusted source is an explicit operator instruction to Codex for an existing Codex-owned VST
   task. The corresponding task and live lease must already exist in the root Store; the
   coordinator cannot create, lease, list, or select them.
2. The caller is authenticated by AF_UNIX peer credentials and the pinned process identity. A
   root-owned deployment mapping binds that peer to the fixed principal `Codex`; the principal is
   never accepted from the JSON body. Each request names one exact task, slot, attempt, epoch, and
   unique request ID. The coordinator refuses batch or enumeration requests.
3. The coordinator forwards the principal and identifiers through the existing dispatcher grant
   request. Root Supervisor verifies that the current Store story owner is `Codex`, that the exact
   lease/attempt/epoch is live, and that the manifest, budget, preflight and service generation are
   current before issuing a grant. If the existing RPC cannot perform this principal-to-owner
   check, implementation must add it to that existing operation; no new Supervisor operation is
   presumed authorized.
4. An identical request ID and canonical payload may only resolve its existing same-generation
   grant/claim/result. A reused request ID with different payload, stale/revoked lease, duplicate
   launch, or cross-generation retry is refused. The coordinator never automatically retries an
   ambiguous launch.
5. The caller cannot provide commands, executable paths, worker identity, Store/config paths,
   model provenance, or artifact paths; those values come from the root-owned validated manifest
   and configuration.

This amendment uses the operator's current instruction as authorization for Codex-owned work and
the pre-existing Store owner/lease as durable execution authority. It does not claim that an
independent operator signing key exists. GPT-PM has been asked to approve or modify this precise
binding before coordinator implementation.

## Provisioning authorization and E5 boundary

The same GPT-PM decision conditionally permits local root-only service keys/configuration inside
the dedicated WSL2 after review of the exact service configuration and key custody. Codex may
generate local Store event-integrity and startup/reconciliation keys, and service keys only under
the approved custody rules. The operator network-policy attestation key remains
operator-controlled; Codex must not impersonate it. The independent probe identity must be
separately established. External provider/production credentials must come from their authorized
owners. This adjudication did not authorize systemd enable/start.

Fresh E5 must bind the exact committed source/runtime/helper revision, installed sandbox-spec
digest, fresh run ID and nonce, authentic probe signature, independently operator-authorized
network-policy attestation, actual environment inventory, and service generation/cgroup/artifacts.
Automount/interoperability, Windows-drive absence, egress policy, host paths/sockets, UID/GID and
capabilities, cgroup containment, filesystem isolation, restart fencing, and reviewer/signer
isolation need real host evidence. Anything not observed remains `NOT_VERIFIED`.

## Current status

No coordinator source, key, root configuration, service state, test, migration, or E5 run has been
created under this proposal. The amended request-provenance contract is pending a correlated
GPT-PM decision. No code may implement the coordinator until that amendment is approved; source
tests and documentation preparation may proceed within the approved scope.

## Verification and operational boundary

This proposal is not implementation, provisioning, runtime evidence, or S2 approval. No tests,
service start/enable, key generation, firewall change, or migration was performed. After approval,
Codex owns implementation and root configuration generation in the existing dedicated WSL2;
designated test agents own required tests; GPT-PM owns exact-head review; runtime E5 may be claimed
only from fresh evidence actually produced in that environment.

## Correlated pub/sub adjudication and implementation status

GPT-PM's later correlated response is request `274a8f94-9438-4f16-8dd4-98a8daf64b37`, job
`232e6309-ea24-405e-b8c6-771215cdde2e`, user turn `d82d2124-ec09-4e3b-a321-d767350ed73a`,
response `67045970-e83f-538b-866e-ba97e9d269ec`. It returns **ACCEPT — WITH BINDING CONSTRAINTS**.
This supersedes only the earlier point-to-point proposal and permits implementation of the narrow
Store-backed pub/sub source path. `S2-DISPATCH-M01` remains OPEN until implementation, tests,
independent review, and separately authorized runtime acceptance are complete.

The accepted contract is one typed `DISPATCH_INTENT_ACCEPTED` event in the hash-chained Store,
published through a Supervisor-filtered AF_UNIX subscription to the dedicated dispatcher. The
intent binds request ID, task, slot, attempt, epoch, run ID, derived lease ID, kernel-authenticated
principal, canonical payload digest, current service generation, and manifest digest. The
dispatcher may forward only the exact accepted intent. No general-purpose bus, external broker,
task enumeration/selection, queue or spool, scheduler/assignment authority, grant signing, or
automatic retry is allowed. Replay is at-least-once and must revalidate current owner, lease,
epoch, manifest, preflight, and generation; same-ID/different-payload and ambiguous launch fail
closed. Store event-chain and cursor integrity are mandatory.

The implementation source currently present in the worktree adds the typed Store event and
schema-v6 migration, Supervisor owner binding and filtered subscription/grant operations, the
`tools/vst/dispatcher_service.py` adapter, its systemd unit template, and installer/documentation
references. These are source changes only; their origin is not established by this record. The
v6 migration is gated by `allow_schema_upgrade` and has not been applied. No tests, service
activation, key generation, runtime dispatch, or E5 evidence are claimed here.

The GPT-PM decision authorizes source implementation and tests after coding, but does **not**
authorize migration application, runtime activation, key generation, dispatch, push/PR/merge, or
deployment. Migration/schema code requires an independent review before application. Exact
acceptance still needs owner identity, durable intent, delivery/replay, idempotency, revocation and
generation fencing, grant integration, negative tests, exact-head independent review, and a
separately authorized runtime run. The earlier response under request
`9fcaec9d-c344-4388-b79a-1392fb6f4cb4` remains uncertain and is not approval.
