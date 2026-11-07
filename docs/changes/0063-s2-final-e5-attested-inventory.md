# 0063 S2 final attested E5 inventory

## What changed

- Recorded the final reserved E5 probe as `PASS` after the primary coordinator independently verified both the runner-signed inventory and operator-root attestation.
- Added the public run/spec/nonce-bound operator attestation JSON. It contains only the public attestation fields and signature; no private inventory is included.
- Recorded the exact seven check results, zero-socket and zero-Windows-drive inventory counts, runner/operator signature digests, final-time nftables hashes, scoped unit, and command/API path.
- Recorded the private inventory location and mode without committing its contents.
- Clarified that Codex performed the operator-root signing and host-mount review under the user's delegated autonomous WSL task; no independent human approval is claimed.
- Updated the document registry and decision/lesson logs.

## Why

The final inventory was collected only after the operator-root attestation for the exact reserved correlation was supplied. Independent verification returned true for both the probe and network-policy attestation. This record closes the E5 inventory acceptance while preserving the separate provenance of Codex execution and the absence of independent human approval.

## Verification state

- Product source HEAD: `280e2d0a613a0b70252c13ce7afe85f22734f7d1`.
- Repository HEAD before this documentation update: `19669151cbe1ec9fa48246374211e2a80bbb3101`.
- Final result: exit 0; inventory result `PASS`; `verify_fresh_probe=true`; `verify_network_policy_attestation=true`.
- Seven checks were true: automount disabled, interop disabled, no container socket, non-root identity, blocked egress smoke probe, loopback canary, and empty external allowlist.
- Socket enumeration complete, zero socket paths; Windows-drive source count zero; inventory UID:GID `997:988`; signer peer `997:988`.
- Runner signature SHA-256: `bf05ab2d68880f4d64f5f585e4b6ae9c710ab00898cea4dccf815bde87740820`.
- Operator signature SHA-256: `efbe3e659313415350d3dedb8766828b3cc1fa7600a15a578afe7be1a0e2b8f1`.
- The full signed inventory remains outside Git at `/var/lib/vst/private-e5-final-inventory-8024493e38ba44df96ee5f127a24b338.json`, `root:root` mode `0600`, pending retention under operator policy.
- No key was accessed by the E2E subagent. The final probe was not rerun, and no alternate correlation was used.
- Evidence: `docs/sdlc/evidence/s2-e5-runmanifest-wsl-280e2d0.md` and `docs/sdlc/evidence/s2-e5-operator-attestation.json`.

## Ownership and next action

- Accountable task owner: operator.
- Executor and signer/reviewer recorded for this delegated task: Codex under the user's autonomous WSL authorization; no independent human approval.
- E2E subagent preserved the signed inventory privately and committed only sanitized fields and the public attestation.
- Next: retain the root-only raw inventory according to the operator's evidence-retention policy. No further probe may reuse this run ID/nonce/spec bundle.
