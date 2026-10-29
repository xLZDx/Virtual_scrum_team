# Change 0338 — Prepare the exact-head S2 E5 signer boundary

## Summary

Record the fresh S2 E5 runtime preparation at exact code/test HEAD `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2` and its concrete signer traversal blocker. The no-`.git` archive snapshot is prepared in the dedicated WSL distro, but no signer, preflight probe, or persistent WSL configuration was changed.

## Why

The earlier signed sandbox run is tied to source HEAD `280e2d0` and cannot establish current-head acceptance. A current run needs a new nonce, evidence digest, operator-root signature and runner-signer signature. The prepared identity-bound service cannot reach its own mode-0600 key because its root-owned mode-0700 parent directories have no ACL traversal entries.

## Scope and evidence

- Canonical checkout remains `D:\Repo\Virtual_scrum_team`; no worktree or fork was created.
- Exact code/test HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`.
- WSL archive stream SHA-256: `2c6be40566806d164fac515cfca18f8584ecc3df6087c017f0f3e321d848dec1`.
- Archive has no `.git`; its `docs/SANDBOX_SPEC.md` digest matches the expected `7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997`.
- Sanitized WSL inspection: signer UID/GID 995:987 owns its key and dedicated directory; key mode 0600; root-owned key-parent directories mode 0700; no ACL xattr on those parents. The signer service and prior run socket are absent.
- Existing nftables policy is active with input/output default-drop and loopback-only accepts; raw digest `0859b0c672f56a06bdb5861fa2ed45072fec039a93cb964f459a7adb5bed1dc7`; handle-stripped digest `c88c93ba40791971895a4c6c719c8ae37d2b2b676d499fb5f7b8f0875cc8b0`.
- Prepared run ID and nonce remain unused. No key content was read or emitted. No probe was run.

## Decision and remaining action

Keep E5 open. Codex owns preparing a temporary, signer-only search ACL on the two parent directories, verifying exact prior metadata and restoration, and collecting a fresh non-secret evidence digest. The designated `e2e-runner` owns execution of the exact-head probe under the recorded transient sandbox limits. Any ACL that cannot be removed and verified immediately after the run is a stop condition. No current-head E5 PASS is claimed by this change.

## Verification state

Documentation-only reconciliation; no tests, checks, build, service launch, key read, ACL change or sandbox probe was performed for this record. Probe: `NOT_RUN`.

## Attribution

Change: 0338  
Executor: Codex
