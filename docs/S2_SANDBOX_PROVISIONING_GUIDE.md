# Operator guide: provision the S2 worker sandbox

Status: dedicated Ubuntu-24.04 WSL2 provisioned and accepted for the recorded per-run E5 correlation; persistent production deployment is not claimed. The operator selected WSL2 and delegated autonomous execution to Codex. The final signed inventory and attestation passed for one fresh run, but this does not waive remaining E4/E8 limits or qualify other environments. See `docs/sdlc/evidence/s2-e5-operator-attestation.json` and `docs/sdlc/evidence/s2-e5-runmanifest-wsl-280e2d0.md`.

## Recommended setup

Use a dedicated WSL2 distribution only when its network, filesystem, and identity boundaries can be enforced and evidenced. Otherwise use a dedicated VM with equivalent or stronger isolation. Do not repurpose the interactive development distribution or mount the repository's parent directory.

For this delegated run, the operator is the accountable task owner and Codex is the executor. The repository does not identify a named infrastructure service owner; that technical ownership remains unknown. Evidence records distinguish Codex's execution/signing from independent human approval; no independent human review is claimed.

## Provisioning sequence

1. Create a dedicated WSL2 distribution or VM for this project. Keep its image and mutable runtime state outside the repository. Record the environment name, image/version or VM identity, host platform, and provisioning date in the private operator handoff; do not put personal paths, secrets, or host identifiers in public repository files.
2. Configure the network boundary before starting a worker. Deny outbound traffic including DNS and indirect routes by default. Do not add an external allowlist entry for S2. Permit only the probe's ephemeral sandbox-local `127.0.0.1` canary. Record the firewall/network policy and the control that enforces it. Prepare an operator-root-signed attestation bound to the run ID, spec SHA-256 and fresh nonce; include environment identity, policy SHA-256, private evidence SHA-256, `empty_external_allowlist=true`, `no_container_socket=true`, and `no_unapproved_host_paths=true`. The supervisor validates this signature independently. The reserved-address connection is only a smoke probe and cannot establish the policy.
3. For WSL, set `/etc/wsl.conf` so Windows drive automount is disabled and Windows/Linux interoperability is disabled (`[automount] enabled=false`; `[interop] enabled=false`, `appendWindowsPath=false`). Restart the distribution after changing this file. Confirm that no Windows drive, host home directory, Windows executable path, or host credential store is visible. If these controls cannot be enforced, use a VM.
4. Create distinct unprivileged identities for worker, runner, signer, supervisor, and read-only reviewer. Do not run the worker as root. Keep the worker out of the runner group and drop supplementary groups at launch. The reviewer must have read-only access to the worktree and no store write access.
5. Keep all six S2 trust roots pairwise distinct: worker, supervisor, operator, event, reviewer, and runner-signer. The runner's OS identity is separate from the signer key root; only that runner identity may use signer IPC. Store keys outside the worker mount. The signer key must be readable only by the signer identity (POSIX mode `0600`). Place the Unix signer socket under a signer-owned directory with traversal restricted to the runner group (directory `0710`; socket group-owned by the runner group with mode `0660`). Do not copy signer or operator credentials into the worker environment.
6. Ensure there is no Docker/Podman/container-engine socket, host socket, or host path exposed to the worker. Mount only a per-run workspace. Provide only short-lived, run-scoped credentials required by the fixture and remove them during cleanup.
7. Set and record CPU quota, memory ceiling, process-count limit, disk quota, and wall-clock deadline before any worker run. Missing limits block launch. Verify the host's process containment behavior; unsupported Windows Job Object nesting must refuse execution.
8. From the provisioned target, execute the repository's standard-library pre-flight probe using the actual sandbox configuration and a fresh run ID and nonce, supplying the signed network-policy attestation. Preserve its runner-signed inventory, operator-signed attestation, exact command, interpreter/version, probe output, spec SHA-256, run ID, nonce, environment identity, and code HEAD. Do not substitute a hand-written or synthetic inventory. If any socket inventory source cannot be enumerated, launch is refused.
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
- Operator-root-signed network-policy attestation bound to the same run ID, nonce and spec digest; policy and evidence hashes are retained, while sensitive evidence remains private.
- Explicit result for process containment and reviewer read-only enforcement.

The recorded E5 per-run acceptance is documented above; this guide alone does not approve persistent deployment or all E5-E8 criteria. Windows Job Object nesting, process-kill/kill-table scenarios, and full E8 crash/resume remain `NOT_RUN` with their exact constraints in the S2 state and evidence records.

## References

- Contract: [`SANDBOX_SPEC.md`](SANDBOX_SPEC.md)
- S2 acceptance: [`S2_SANDBOX_WORKER_PLAN_2026-10-24.md`](S2_SANDBOX_WORKER_PLAN_2026-10-24.md), sections 3-6 and 10
- Probe implementation: `tools/vst/preflight.py`
- Probe receipt contract: `tools/vst/contracts.py` and `tools/vst/schemas/`
