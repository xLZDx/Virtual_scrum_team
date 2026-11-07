# 0062 S2 fresh WSL mount classification and approval rationale

## What changed

- Corrected the prior statement about `/usr/lib/modules`: it is not a distinct host mount and resolves through the distro root; the scoped runner unit creates a tmpfs mask and the worker confirmed denial.
- Added the fresh 19:55 UTC raw and normalized nftables hashes, active service state, chain-policy summary, and the limitation that raw snapshots were not preserved for handle-only attribution.
- Added complete sanitized category/type counts for the 31-row host mount inventory and 27-row scoped unit view, including redacted non-standard targets.
- Recorded fresh WSL distro identity, `wsl.conf` isolation values, and effective unit properties without reading another distro or exposing personal path/source names.
- Recorded the primary coordinator's bounded rationale for the library-level socket and host-path acceptance, clearly as input to operator review rather than an operator signature.
- Preserved the existing unused final-probe run ID, nonce, and spec digest unchanged.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Why

The operator requested current pre-attestation evidence after raw nftables digests differed between snapshots. The normalized semantic digest matches the coordinator's independent review, and the mount classification distinguishes distro, pseudo-filesystem, runtime, and WSL bridge mounts from path-backed host data. This supports a bounded operator decision while keeping the final probe and key under operator control.

## Verification state

- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Repository HEAD before this evidence-only update: `79ca9cf` (scope-correction record 0061).
- Snapshot time: `2026-10-24T19:55:40Z`.
- Raw nft JSON SHA-256: `9aa0d3519e0f49fe76eb5b0675dbb3204c065a51aee1800b8e784c193f6efa1f`.
- Handle-stripped canonical semantic SHA-256: `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f5b7f8f0875cc8b0`.
- WSL identity: named distro `Ubuntu-24.04`, Ubuntu 24.04.5 LTS, systemd 255.4, Python 3.12.3; systemd enabled, automount and interop disabled.
- Host inventory: 31 rows, zero Windows-drive sources. Scoped unit inventory: 27 rows, zero Windows-drive sources; no visible `9p`, overlay, or non-root `ext4` mounts.
- The inspection used systemd only to expose effective properties and read mount metadata. It did not collect or sign a probe and did not use the reserved final correlation.
- Raw JSON snapshots from previous digests were not retained; a handles-only cause for their differences remains `NOT_VERIFIED`.
- No product source or tests changed. No operator key was accessed or used.
- Full details: [S2 E5 WSL integration evidence](../sdlc/evidence/s2-e5-runmanifest-wsl-280e2d0.md).

## Ownership and next action

- Accountable task owner: operator.
- Executor: E2E runner (`gpt-6-luna`).
- Primary coordinator provided the bounded mount-acceptance rationale; the operator retains authority over final attestation.
- Next: recompute raw and normalized nftables hashes at final-probe time, verify the reserved correlation remains unchanged, and run/sign only after the operator provides the public signed attestation for that exact run ID, nonce, and spec digest.
