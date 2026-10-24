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
127.0.0.1 port inside the sandbox and is not a public-network exception. The
probe separately attempts a connection to a reserved documentation address;
that connection must fail. A successful external connection fails pre-flight.

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
table, Windows interop state, user and group identity, known container socket
paths, blocked external-egress result, sandbox-local loopback result, and
environment variable names. It binds the inventory to the run ID, a fresh
nonce, and this file's SHA-256 digest. The trusted runner signs the inventory.
The supervisor may start a worker only when the signature verifies, the probe
is fresh and bound to the same run and spec digest, and every check passes.
An enabled automount or interop setting, present container socket, root UID,
reachable external target, failed loopback canary, missing inventory field,
or stale run binding blocks launch.

The probe can observe configured conditions; it does not prove that a host
firewall or hypervisor is correctly configured. Provisioning and enforcement
of the OS/network/resource boundary are operator-verified acceptance items.
Record the exact distribution/VM identity and policy evidence with the run.
