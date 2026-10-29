# S2-3 inactive stage-only result — 2026-10-29

## Exact inputs and authorization

- Source HEAD: `ef465cd8790518e405164c82ec1598f843ae8a58`.
- Source plan SHA-256: `59ebfee0435d7a34f4c09de6ef5269e08d7a6713a5e7301497ba754ef348d8e9`.
- Source archive SHA-256: `bc489ce6155e178b1f2c2ef6a9e8b88e78c3b3e991576107319c9b34c3543d44`.
- Fresh inventory SHA-256: `a3b6ea38103edfb0d25cab8ef3c2e405d8bcb2d08c0d16194668b4860095d054`.
- Exact-bundle approval: GPT-PM request `29c0c463-9d18-4c35-ae9d-8ed5331a4f70` plus approved fresh inventory replacement under request `5f47ce5d-3db2-4f22-9e72-cad81a139c9c`.
- Target: existing `Ubuntu-24.04` WSL distribution only.

## Command and result

The Windows handoff was run from the canonical checkout with the reviewed hashes:

```powershell
tools/qa/install_wsl_runtime.ps1 -ExpectedHead ef465cd8790518e405164c82ec1598f843ae8a58 `
  -Distribution Ubuntu-24.04 `
  -ExpectedPlanSha256 59ebfee0435d7a34f4c09de6ef5269e08d7a6713a5e7301497ba754ef348d8e9 `
  -ExpectedInventorySha256 a3b6ea38103edfb0d25cab8ef3c2e405d8bcb2d08c0d16194668b4860095d054 `
  -StageOnly
```

The exact plan/inventory SHA-256 values and committed blob identities matched before execution;
inventory age was 141 seconds. The installer reverified the source archive and member map,
compiled the worker helper, verified the staged runtime, and returned success:

- Versioned runtime staged at `/opt/vst-runtime-ef465cd8790518e405164c82ec1598f843ae8a58`.
- Runtime tree SHA-256 from the post-stage candidate: `7f4806079c675364434492e9402b3ce56b942e515edcbd3eea33f4d765a47938`.
- Versioned helper: `/usr/local/libexec/vst-s4-worker-exec-ef465cd8790518e405164c82ec1598f843ae8a58`.
- Helper binary SHA-256: `820851edd723e999bac226b3e1ce028a464ed9ec42cfe254fd6fa4a0d28c0f3d`.
- Helper owner/group/mode: root, GID 988 (`vst-runner`), mode `4750`.
- Installer output: `selected=false`, `selector_unchanged=true`, `systemd_units_installed=0`,
  `runtime_stage_only=true`.
- Old selector still points to `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- No service identity/configuration, Store, key/E5, dispatch, activation, or production action was
  performed.

The root-run read-only `bootstrap_runtime.py prepare` then checked the staged tree/helper and the
unchanged selector/unit baseline and emitted the unsigned canonical post-stage candidate
`s2-runtime-post-stage-manifest-ef465cd8790518e405164c82ec1598f843ae8a58.json`, digest
`78d21af798f66a3e54a8d638f393773af5d20120075cd02599ac70675cb84be7`. The candidate binds the
complete new runtime tree, helper binary, compiler, source plan/archive/inventory, previous
selector, six unit fingerprints, and fixed parent metadata. It is not a signature or approval.

## Post-stage review and remaining gate

GPT-PM separately accepted the exact post-stage candidate under request
`ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4`, correlated reply
`1c8d392e-1a57-533c-b874-97823f5e4628`, with decision **APPROVE — S2-3 post-stage manifest
acceptance only**. The exact manifest digest and limits are recorded in
`s2-3-post-stage-manifest-review-ac2d25a2.md`.

This evidence does not authorize selector mutation, systemd unit writes/reload/start/enable, Store
access/migration, identity/config creation, production key/E5 work, dispatch, production,
deployment, or S2 closure. The S2-3 evidence/backlog/change record was committed as
`ae07f8708adcc7ef4f69505477ad6b72e3c912cf` and normally pushed to
`origin/s2-canonical-continuation`. TP-10's broader refusal matrix remains PARTIAL, and the review
does not prove its unexecuted cases.
