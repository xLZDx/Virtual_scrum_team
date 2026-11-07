# Virtual Scrum Team worker sandbox specification

Status: implementation contract for S2. A sandbox is not accepted until the
operator provisioned it and the signed, run-bound pre-flight inventory passes.
The repository code does not provision or weaken the host boundary.

## Isolation boundary

Use a dedicated WSL distribution or a dedicated virtual machine for each
trusted execution environment. In WSL, disable Windows drive automount and
Windows/Linux interoperability in `/etc/wsl.conf`; restart the distribution
after changing either setting. The worker must not see `/mnt/c`, other Windows
drive mounts, host home directories, host credential stores, Docker/Podman or
container-engine sockets, or any host path outside the per-run workspace.
Prefer a VM when the WSL host cannot enforce these conditions.

Run the worker as a non-root, unprivileged account distinct from the runner,
signer, supervisor, and reviewer accounts. The worker account receives only
the run directory and per-run scoped credentials needed for the task. Those
credentials are created for one run and removed during cleanup. They must
never include receipt-signing keys or signer credentials. The signing key is
owned by the signer identity and mode 0600. The Unix signer socket lives in a
signer-owned directory that grants traversal only to the runner group (mode
0710); the socket is group-owned by the runner group and mode 0660. The worker
account is not a member of the runner group and the runner drops supplementary
groups when launching it. The signer authenticates runner UID using kernel
peer credentials and rejects all other identities.

Review runs under a separate read-only identity. Its credential must have no
write access to the worker worktree or control-plane store. The runner verifies
that the mounted review tree is read-only before launching review. A failure
to prove the effective OS permissions blocks the review.

## Network policy

Egress is default-deny at the sandbox network boundary. The external egress
allowlist is empty by default; adding an endpoint requires a separately
recorded task-specific policy. DNS and indirect routes are also denied unless
explicitly allowed. The local pre-flight loopback canary binds an ephemeral
127.0.0.1 port inside the sandbox and is not a public-network exception. An
operator-root-signed, run/spec/nonce-bound network-policy attestation identifies
the environment, SHA-256 digests of the enforced policy and private evidence,
an empty external allowlist, no container socket, and no unapproved host paths.
The supervisor verifies this attestation independently. A connection attempt
to one reserved documentation address is only a limited smoke probe; failure
does not prove default-deny egress and success fails pre-flight.

## Resource and filesystem limits

Each run has an operator-configured CPU quota, memory ceiling, process count
limit, disk quota, and wall-clock deadline. The values are recorded in the
run configuration before launch; absence of any limit blocks the worker.
Commands use the run directory as their working directory, a minimal
allowlisted environment, no inherited stdin, bounded output capture, and
process-tree termination. No host path beyond that run directory may be
mounted or passed to the worker. Job Object nesting on Windows must be
verified on the target host; unsupported nesting is a refusal, not a
best-effort success.

## Required pre-flight evidence

Before each worker run, the standard-library-only probe records the mount
table and an explicit `windows_drive_mounts` list. It classifies a mount as a
Windows drive only when the mount source is a drive root (`C:` or `C:\\`) and
the filesystem is `drvfs` directly or WSL's `9p` with `aname=drvfs`; unrelated
mount targets such as `/mnt/wslg` do not count as Windows-drive automount. It
also records Windows interop state,
user and group identity, container socket paths,
blocked-target smoke-probe result, sandbox-local loopback result, and
environment variable names. It binds the inventory to the run ID, a fresh
nonce, and this file's SHA-256 digest. The operator separately signs the
network-policy attestation with a distinct
operator-only key. The probe inventory itself is not cryptographically signed.
The root Supervisor accepts it only from its root-owned mode-0600 preflight file,
checks the exact run/spec/nonce and all required measurements, and independently
verifies the operator-signed network-policy attestation. The root-controlled
systemd unit and the root capture of its exact invocation are the provenance
boundary for the inventory. The operator key is never copied to the runner,
worker, or analyzer. All six receipt and policy trust roots (worker, supervisor,
operator, event, reviewer, runner-signer) remain pairwise distinct. Socket discovery spans known engine
endpoints, numeric per-user runtime directories, and `/proc/net/unix`; inability
to enumerate a required source fails closed.
The supervisor may start a worker only when the root-captured inventory is
fresh and bound to the same run and spec digest, every check passes, and the
operator-signed network-policy attestation verifies.
An enabled automount or interop setting, present container socket, root UID,
reachable external target, failed loopback canary, missing inventory field,
or stale run binding blocks launch.

The probe can observe configured conditions; it does not prove that a host
firewall or hypervisor is correctly configured. Provisioning and enforcement
of the OS/network/resource boundary are operator-verified acceptance items.
Record the exact distribution/VM identity and policy evidence with the run.

## External event anchor coordination

The external event anchor and its `.coord.lock` sidecar must both be outside
the worker mount. Every store process that can write events or make an
authoritative gate decision must use the same coordinator lock path. The lock
is held across the SQLite write transaction and all external checkpoint
appends; an authoritative read holds it from before opening the database
snapshot through comparison with the external anchor. This prevents a reader
from interpreting a concurrent valid checkpoint advance as tampering and
prevents concurrent store writers from appending out of order.

After a crash, startup may advance the external anchor across more than one
event only when the full database event HMAC chain verifies and the latest
external checkpoint exactly matches the event at its recorded count. The
store then compare-and-appends each missing checkpoint in order before
permitting a lease or gate decision. It never creates a missing anchor for a
non-empty database, never accepts an anchor ahead of the database, and never
repairs a fork, malformed event chain, invalid checkpoint, or mismatching
prefix. Any such condition stays write-locked for operator recovery.
