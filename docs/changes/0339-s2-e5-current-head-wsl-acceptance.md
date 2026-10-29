# Change 0339 — Record current-head S2 E5 WSL acceptance

## Summary

Record a fresh, signed S2 E5 preflight PASS at exact code/test HEAD `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2` and reconcile current state/backlog. No product source or test code changed.

## Why

The prior signed E5 run was bound to older product source `280e2d0`; it could not establish current-head acceptance. The new run binds a freshly collected environment/policy evidence digest and sandbox specification to a unique run ID and nonce, executes the signed preflight in the selected WSL distro, and verifies both operator and runner signatures.

## Evidence

- Canonical checkout at runtime: `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`, HEAD `ca3e31ff1172c899458a7a8f1886539d1d1ae634`.
- Exact code/test HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- WSL archive stream SHA-256: `2c6be40566806d164fac515cfca18f8584ecc3df6087c017f0f3e321d848dec1`; no `.git`, read-only runner bind.
- Run ID: `s2-f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2-e5-20261026-591249434bde4989b6d320bf3675fe20`.
- Nonce: `591249434bde4989b6d320bf3675fe20`; consumed once and never to be reused.
- Spec SHA-256: `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.
- Sanitized private evidence bundle SHA-256: `d247417dddde3dffe388312cf925ace5aff91c497f5a32b33b0557aa7d08a745`.
- Normalized network policy SHA-256: `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f5b7f8f0875cc8b0`.
- Public signed attestation: `docs/sdlc/evidence/s2-e5-operator-attestation-f0bbac8-20261026.json`.
- Private signed inventory remains in the dedicated WSL at root:root mode `0600`, SHA-256 `de8fd9394867f8c79bfe0d516143d922c1c1fe5b97728ef5ea986a18c9aaf995`. Runner signature fingerprint SHA-256: `70247361463a7c8150afaa91fa2c28eb641e72b0aee4d9a91341fa6e431874a9`.
- Full sanitized scope and run manifest: `docs/sdlc/evidence/s2-e5-runmanifest-wsl-f0bbac8-20261026.md`.

## Decision and limitations

Mark VST-014 E5 `PASS` for this exact per-run WSL probe only. The runner exited zero and all seven checks were true. It observed zero Windows-drive mounts, complete socket enumeration with zero paths, runner UID:GID `997:988`, and the configured CPU/memory/task/runtime/tmpfs/mount/network limits. The user-selected dedicated WSL distro had automount and interop disabled; the current normalized nftables policy was default-drop with loopback-only accepts.

The runner-signer key remained UID:GID `995:987`, mode `0600`. For this run only, UID 995 received search-only ACL entries on exactly `/var/lib/vst` and `/var/lib/vst/keys`. Cleanup restored both original root:root mode `0700` parents with no ACL xattr; signer/runner units, socket, ledger and run directory were absent. No key contents were printed. The full inventory is not committed.

The reserved-address egress check is only a smoke probe. This evidence does not establish persistent production deployment, complete host egress enforcement, external direct-writer exclusion, worker-specific workspace binding, Windows Job Object nesting, full POSIX process-tree cleanup, or process-kill/kill-table/mutation/crash-resume acceptance. Keep S2 Phase 8 open.

## Work provenance

The designated `e2e-runner` executed the probe using GPT-6 Luna; effort metadata for the resumed agent is not available. Codex collected/verified evidence and signed the operator attestation under the user's delegated autonomous WSL task. No independent human signature or approval is claimed. Codex independently verified `verify_network_policy_attestation` and `verify_fresh_probe` against the WSL-held keys without printing them.

The pre-run guard rejected a manually transcribed 62-character policy hash before ACL changes or service launch. It was recomputed from current nftables JSON, validated at 64 hexadecimal characters, and signed programmatically. Earlier disposable observation attempts also stopped before acceptance collection due a private-`/tmp` bind and an observer `__file__` assumption; the final read-only boundary observation succeeded and used a distinct nonce. No failed diagnostic consumed the final acceptance run ID/nonce.

## Verification state

Runtime preflight: `PASS`. Signed attestation: independently verified. Signed private inventory: independently verified. ACL and transient-service cleanup: independently verified. No additional tests, checks, build, mutation scenario, process-kill scenario, or crash/resume scenario was run in this change.

## Attribution

Change: 0339  
Executor: Codex
