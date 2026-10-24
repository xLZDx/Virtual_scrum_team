# Operator guide: provision the S2 worker sandbox

Status: operator action required. A sandbox is not accepted until the target host is provisioned and a fresh signed probe inventory passes. This guide does not claim that any sandbox exists.

## Recommended setup

Use a dedicated WSL2 distribution only when its network, filesystem, and identity boundaries can be enforced and evidenced. Otherwise use a dedicated VM with equivalent or stronger isolation. Do not repurpose the interactive development distribution or mount the repository's parent directory.

The operator owns host provisioning. The repository does not identify a named infrastructure service owner; that technical ownership remains unknown. Codex can review the resulting evidence and run the repository probe after the operator provides the environment.

## Provisioning sequence

1. Create a dedicated WSL2 distribution or VM for this project. Keep its image and mutable runtime state outside the repository. Record the environment name, image/version or VM identity, host platform, and provisioning date in the private operator handoff; do not put personal paths, secrets, or host identifiers in public repository files.
2. Configure the network boundary before starting a worker. Deny outbound traffic including DNS and indirect routes by default. Do not add an external allowlist entry for S2. Permit only the probe's ephemeral sandbox-local `127.0.0.1` canary. Record the firewall/network policy and the control that enforces it.
3. For WSL, set `/etc/wsl.conf` so Windows drive automount is disabled and Windows/Linux interoperability is disabled (`[automount] enabled=false`; `[interop] enabled=false`, `appendWindowsPath=false`). Restart the distribution after changing this file. Confirm that no Windows drive, host home directory, Windows executable path, or host credential store is visible. If these controls cannot be enforced, use a VM.
4. Create distinct unprivileged identities for worker, runner, signer, supervisor, and read-only reviewer. Do not run the worker as root. Keep the worker out of the runner group and drop supplementary groups at launch. The reviewer must have read-only access to the worktree and no store write access.
5. Keep all six S2 trust roots pairwise distinct: worker, supervisor, operator, event, reviewer, and runner-signer. The runner's OS identity is separate from the signer key root; only that runner identity may use signer IPC. Store keys outside the worker mount. The signer key must be readable only by the signer identity (POSIX mode `0600`). Place the Unix signer socket under a signer-owned directory with traversal restricted to the runner group (directory `0710`; socket group-owned by the runner group with mode `0660`). Do not copy signer or operator credentials into the worker environment.
6. Ensure there is no Docker/Podman/container-engine socket, host socket, or host path exposed to the worker. Mount only a per-run workspace. Provide only short-lived, run-scoped credentials required by the fixture and remove them during cleanup.
7. Set and record CPU quota, memory ceiling, process-count limit, disk quota, and wall-clock deadline before any worker run. Missing limits block launch. Verify the host's process containment behavior; unsupported Windows Job Object nesting must refuse execution.
8. From the provisioned target, execute the repository's standard-library pre-flight probe using the actual sandbox configuration and a fresh run ID and nonce. Preserve its signed inventory, exact command, interpreter/version, probe output, spec SHA-256, run ID, nonce, environment identity, and code HEAD. Do not substitute a hand-written or synthetic inventory.
9. Confirm that the probe records all required properties in `docs/SANDBOX_SPEC.md`: mount table, interop state, user/group identity, container socket paths, denied external target, successful local loopback canary, and environment variable names. A reachable external endpoint, failed loopback, root UID, exposed host path/socket, missing field, invalid signature, or stale run binding is a failed pre-flight.
10. Return the private provisioning evidence and signed inventory to the project coordinator. The coordinator records only non-sensitive identifiers and hashes in the repository, verifies the signature and binding, and leaves every unproven property `NOT_RUN`.

## Acceptance record

The handoff must contain:

- Environment identity and type (dedicated WSL2 distribution or VM), image/version, and host platform.
- Evidence that automount/interoperability are disabled when using WSL, or equivalent VM isolation evidence.
- Network policy showing default-deny egress, DNS/indirect-route denial, and no external allowlist for S2.
- User/group and key/socket permission evidence, with secret material withheld.
- Resource limits and evidence of their enforcement.
- Evidence that no host drive, host credential store, container socket, or unapproved path is mounted into the worker.
- Fresh signed probe inventory bound to run ID, nonce, `docs/SANDBOX_SPEC.md` digest, and exact code HEAD.
- Explicit result for process containment and reviewer read-only enforcement.

No worker execution or E5-E8 sandbox-dependent acceptance is approved by this document alone. An unavailable property remains `NOT_RUN` with its exact reason.

## References

- Contract: [`SANDBOX_SPEC.md`](SANDBOX_SPEC.md)
- S2 acceptance: [`S2_SANDBOX_WORKER_PLAN_2026-10-24.md`](S2_SANDBOX_WORKER_PLAN_2026-10-24.md), sections 3-6 and 10
- Probe implementation: `tools/vst/preflight.py`
- Probe receipt contract: `tools/vst/contracts.py` and `tools/vst/schemas/`
