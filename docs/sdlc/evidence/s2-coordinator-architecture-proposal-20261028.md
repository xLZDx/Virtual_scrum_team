# S2 coordinator architecture proposal — 2026-10-28

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

## Required adjudication before implementation

GPT-PM must approve or amend the trust boundary above and state whether this coordinator closes
`S2-DISPATCH-M01` when the authenticated caller is the fixed in-repository dispatcher service and
the Store remains the sole assignment authority. The previous GPT-PM decision prohibited a new
assignment authority and required separate adjudication for a new architecture. No code, service,
credential, or configuration has been changed under this proposal.

## Verification and operational boundary

This proposal is not implementation, provisioning, runtime evidence, or S2 approval. No tests,
service start/enable, key generation, firewall change, or migration was performed. After approval,
Codex owns implementation and root configuration generation in the existing dedicated WSL2;
designated test agents own required tests; GPT-PM owns exact-head review; runtime E5 may be claimed
only from fresh evidence actually produced in that environment.
