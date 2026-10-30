# Change 0605 — Stage the exact S2 runtime source without selecting it

Date: 2026-10-30
Owner: Codex
Runtime execution role: `e2e-runner` support for exact target evidence
Backlog task: S2-4.9, ordered child of S2-4

## Acceptance delta

Publish the committed source `80c2b81deac364ed6466600fd46af47aafe805e2` as an immutable staged
runtime while leaving the current selector, systemd units, configuration, Store, and dispatch
state unchanged. The exact source plan and target inventory are committed in `20dcb87` and
`cb7aefc`.

## Execution

The first normal installer attempt used inventory
`ef7fc473efc734ae2e5be1b4e0181f4bf2d70939c045f2a720301fcae119412d`. It was rejected before target
mutation because the snapshot had aged to 318.9 seconds, beyond the 300-second freshness bound.
Read-only fields still matched; a fresh inventory was captured and pushed as
`5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66` in `cb7aefc`.

The successful normal installer command was:

```powershell
& .\tools\qa\install_wsl_runtime.ps1 -ExpectedHead 80c2b81deac364ed6466600fd46af47aafe805e2 -Distribution Ubuntu-24.04 -ExpectedPlanSha256 01818efcd23bc20a3a4b408921d7342f5e5f95adc16ad86fe7b2a3b7176e2344 -ExpectedInventorySha256 5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66 -StageOnly
```

The installer exited 0 and reported:

- exact source bundle and staged source map verified;
- runtime path `/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2`;
- helper SHA-256 `0ee613b289ab4fcf79d82f1cae777b96fcd97c8a02c59dded50736797a4381f5`, owner/mode
  `root:vst-runner` (`0:988`), mode `4750`;
- `selected=false`, `systemd_units_installed=0`, `runtime_stage_only=true`;
- source archive SHA-256 `06122645bfe6b1b9c8139fa4a77cca63aab3fd17918245cd75cee1f8f83aae4c`, plan SHA-256
  `01818efcd23bc20a3a4b408921d7342f5e5f95adc16ad86fe7b2a3b7176e2344`, inventory SHA-256
  `5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66`.

The e2e-runner then performed read-only post-stage reconciliation. The root-owned mode-0644
runtime manifest SHA-256 is `09926bd48ba2a130721233c79648c23a164c4873d246621c5c6aabf88ed92c0a`; its
source, archive, plan, inventory and compiler fields match the committed source plan and
inventory. The helper is root-owned by group `vst-runner` (`0:988`), mode `4750`, size 17,200,
SHA-256 `0ee613b289ab4fcf79d82f1cae777b96fcd97c8a02c59dded50736797a4381f5`. The selector still
points to `a600774`; all nine units remain inactive/dead, MainPID is 0 where applicable, and there
are no invocation IDs or systemd jobs. This follow-up made no target changes.

## Acceptance disposition and next action

- Exact immutable runtime publication and exact source-tree verification: **PASS**.
- Runtime selection, systemd unit installation/start, configuration installation, Store
  initialization, bootstrap, and dispatch: **NOT_RUN** in this task.
- The separate uncommitted configuration candidate still binds run data to `a600774`; it is not
  an activation input. Next ordered task: rebind and validate the non-secret candidate against
  `80c2b81`, then gather current run-bound E5 and perform the one permitted owner-to-Runner
  journey. Restricted selectors remain `NOT_RUN`.
