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

- Input is a bounded, length-prefixed canonical JSON object with exactly one field, `instruction`.
- `instruction` is the exact v1 signed envelope; no principal, task, lease, worker, command, model,
  artifact, grant, or alternate endpoint is accepted outside that envelope.
- The owner service validates the signed envelope against the root-owned public trust registry and
  fixed principal `Codex`, then calls `SupervisorClient.submit_dispatch_intent` at the fixed root
  socket. Supervisor verifies the same envelope again using its own root configuration.
- Success returns the exact bounded Supervisor result. Refusal returns only a generic error code.
- The service processes connections sequentially, with a fixed request timeout and bounded request
  and response sizes. It stores no task state and performs no retries. A client must preserve the
  original `request_id` when replaying; Store idempotency binds the complete envelope.
- The caller's Unix-socket group membership only permits reaching this relay. A valid instruction
  signature and Supervisor's live authority checks are still required for durable acceptance.

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
- `Restart=no`; an ambiguous RPC outcome is not retried by the service. The caller receives a
  refusal or connection failure and must reconcile using the existing Store/Supervisor evidence.

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

Source acceptance requires review of exact socket activation, bounded framing, config ownership,
signature validation, one-request behavior, error handling, and no retry/state/authority expansion.
Synthetic-key contract coverage is authored by `functional-test-reviewer` and executed by
`e2e-runner` only after S2 coding is complete. The production path remains disabled until a genuine
authorized signer and public key, exact authenticated OS identity, reviewed root configuration,
current runtime provenance, and allowed runtime evidence exist. The service template itself is not
provisioning authorization or evidence of a started service.

