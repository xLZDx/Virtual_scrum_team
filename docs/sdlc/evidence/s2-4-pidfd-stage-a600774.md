# S2-4 immutable runtime stage evidence

## Outcome

The existing strict PowerShell handoff completed successfully with exit code `0` using source revision `a600774649527ff0b33eb81f4d431f8226119b2c` and the exact reviewed source plan and fresh target inventory hashes below. This was `-StageOnly`: it staged a versioned source tree and its worker helper, left the selected runtime unchanged, installed no systemd units, and did not start or activate services.

The stage wrapper itself checked the target inventory timestamp against its five-minute maximum age, target compiler metadata, exact source-plan and inventory hashes, source ancestry, host installer identity, reviewed archive hash, and destination collision rules. The wrapper passed those checks; no freshness value was edited or bypassed.

## Exact command

```powershell
& .\tools\qa\install_wsl_runtime.ps1 -ExpectedHead a600774649527ff0b33eb81f4d431f8226119b2c -Distribution Ubuntu-24.04 -ExpectedPlanSha256 620e4614929109e2c7689781943bf50e5cf5ad29703d407cb7ebef019cbff29d -ExpectedInventorySha256 c61bc6c10a042d207d2d7d15b3d58b8b69e331cad885624b88d1fb980c54c049 -StageOnly
```

The invocation ran from `D:\Repo\Virtual_scrum_team` on branch `s2-canonical-continuation`. The checkout `HEAD` at execution was `9021b98d6458cb09d7ea1d35942661ff1fee9587`; the requested source revision was its ancestor, and the wrapper archived the exact requested source revision rather than the later checkout tip. The target inventory was captured immediately before handoff, and its timestamp age at save was under one second; the wrapper independently accepted its freshness bound at execution.

## Exact wrapper output

```text
verified exact reviewed source bundle
verified exact reviewed source bundle
installed immutable versioned WSL worker helper from source bundle a600774649527ff0b33eb81f4d431f8226119b2c
binary_sha256=40cca741389d4b711dfca45da2698846a6acc801be006456cc7af207e2dd6353
helper_mode=0:988:4750
verified exact reviewed source bundle
verified staged runtime against exact reviewed source map
staged immutable runtime revision a600774649527ff0b33eb81f4d431f8226119b2c from the verified source bundle
runtime_dir=/opt/vst-runtime-a600774649527ff0b33eb81f4d431f8226119b2c
selected=false
systemd_units_installed=0
source_bundle_path=/run/vst-deploy-a600774649527ff0b33eb81f4d431f8226119b2c-bcf2d613487749af83b2c94acbe5bad3
source_head=a600774649527ff0b33eb81f4d431f8226119b2c
source_archive_sha256=f3d58625475ee48f7b9350df30a48d3b0fc0c61cf33c253432e5004846a2dc4c
source_plan_sha256=620e4614929109e2c7689781943bf50e5cf5ad29703d407cb7ebef019cbff29d
target_inventory_sha256=c61bc6c10a042d207d2d7d15b3d58b8b69e331cad885624b88d1fb980c54c049
source_transfer=stdin; no Windows-drive mount or second checkout used
runtime_stage_only=true; selector_unchanged=true; systemd_units_installed=0
```

## Post-stage read-only metadata

A separate read-only WSL metadata query after staging observed:

- Runtime path: `/opt/vst-runtime-a600774649527ff0b33eb81f4d431f8226119b2c`.
- Runtime tree SHA-256: `42faf63589d480da0b495ed2ba3a1083d1471dd75ff081f03d68d5d988f56997`.
- Tree digest definition: SHA-256 over sorted UTF-8 records `relative_path NUL type(F|L) NUL file_sha256_or_symlink_target LF`; directory metadata is excluded. The observed tree had 41 regular files totaling 1,181,905 bytes and included `.vst-runtime-manifest.json`.
- Helper path: `/usr/local/libexec/vst-s4-worker-exec-a600774649527ff0b33eb81f4d431f8226119b2c`.
- Helper SHA-256: `40cca741389d4b711dfca45da2698846a6acc801be006456cc7af207e2dd6353`; observed owner/group/mode: UID `0`, GID `988`, mode `4750`.
- Existing selector symlink `/opt/vst-runtime` still targeted `/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- All six systemd units were inactive/dead after staging. The three existing service units remained loaded; dispatcher and dispatch-owner service/socket were not-found. No unit files were installed by this operation.
- Runtime and helper paths were versioned with the requested `a600774…` source identity.

The tree/helper metadata query read the staged source tree and helper bytes to calculate digests and queried systemd state. It did not inspect root's staged key directory, runtime configuration candidates, key contents, or secrets.

## Scope and remaining boundary

This evidence establishes successful immutable source/helper staging only. No runtime selector or `/etc/vst-runner` configuration was changed; no systemd unit was written, enabled, or started; no store was migrated; no keys were read or operated; no test suite was rerun; and no runtime command was executed. The runtime remains unselected (`selected=false`). Further activation or live runtime verification is outside this stage-only action and must use its own existing authorization and safeguards.
