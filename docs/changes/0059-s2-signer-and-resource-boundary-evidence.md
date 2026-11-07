# 0059 S2 signer and bounded resource boundary evidence

## What changed

- Extended the S2 E2E evidence with a real runner-only signer socket exercise and worker connection denial.
- Recorded the minimal temporary signer-only search ACL and its restoration, preserving the dedicated runner-signer directory and key owner/modes.
- Verified the per-run systemd resource boundary for a disposable verification unit and one child: bounded `/tmp` tmpfs, finite runtime, memory/CPU/task caps, and namespace properties.
- Added the current sanitized nftables ruleset digest and retained the unresolved host-mount attestation boundary.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The previous signer attempt failed because the signer identity could not traverse root-owned parent directories. A narrowly scoped, reversible search-only ACL allowed the dedicated signer process to open its own key without granting directory listing or changing other role paths. The systemd resource proof adds the missing writable workspace quota and wall-clock ceiling evidence without claiming that an uninstalled production worker unit already uses those properties.

## Verification state

- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Repository documentation/test commit before this addendum: `c9690fe5c599833e5884468546e2bfba497f3392`.
- WSL environment: Ubuntu 24.04.5 LTS, systemd 255, `Ubuntu-24.04` distribution, Python 3.12.3.
- Signer test: runner `SO_PEERCRED` UID/GID `997:988`; valid request signed; same ID/payload replay returned the same signature; changed payload replay rejected; worker UID/GID `999:989` was denied with errno 13 before the signer handler. The signature digest is recorded in the E2E evidence.
- ACL delta: only `vst-signer` execute/search was temporarily granted on the two root-owned intermediary directories. The ACLs were restored; final intermediary modes are root-owned `0700`; the dedicated signer directory is `995:987` mode `0700`; its key is `995:987` mode `0600`. No other role path or operator key was read, invoked, or changed.
- Resource proof effective properties: `CPUQuotaPerSecUSec=1s`, `MemoryMax=2147483648`, `TasksMax=64`, `RuntimeMaxUSec=30s`; `/tmp` was a 1 GiB `tmpfs`, mode `1777`, for the parent and its child. The child inherited the mount and wrote a disposable file.
- Network summary: `nftables.service` active; input/output chains default-drop; two loopback accept rules; sanitized raw-ruleset SHA-256 `dbaadc56201799974415694d76208d9931f151a3b31fa28dc52fd9f6d0f1bba0`.
- No operator attestation was signed. `environment_id` is not emitted by the inventory schema and remains `UNKNOWN`; `no_unapproved_host_paths=true` is not established because sanitized host/system mount approval remains outstanding. The full `run_manifest_commands` integration and production worker unit inheritance remain `NOT_RUN`.
- No source or test files were edited and no test suite was executed in this documentation/provisioning follow-up.

## Ownership and next action

- Accountable task owner: operator.
- Executor: E2E runner (`gpt-6-luna`).
- Technical owner for production runner-unit provisioning and host mount approval is not identified by current repository records.
- Recommended next actions: have the deployment/security owner approve the sanitized host mount inventory and configure the production runner parent unit with the verified resource/namespace properties; then run `run_manifest_commands` against the real signer socket. Do not sign the operator attestation until `environment_id` and `no_unapproved_host_paths` are backed by reviewed evidence.

## Related evidence

- [S2 E2E lifecycle and platform acceptance evidence](../sdlc/evidence/s2-e2e-acceptance-280e2d0.md).
