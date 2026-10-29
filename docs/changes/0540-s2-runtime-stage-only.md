# Change 0540: add explicit S2 runtime artifact staging

## Purpose

Separate immutable artifact installation from selector and fixed-name unit selection so the
reviewed bootstrap transition can inspect exact staged bytes before any path is switched.

## Changes

- Added opt-in PowerShell `-StageOnly`, passed to the WSL bootstrap as an explicit mode and to the
  runtime installer as `--stage-only`. The default installer invocation keeps its existing
  selector/unit validation and installation path.
- Stage-only performs the source-bundle, OS/WSL configuration, mount and immutable destination
  checks, then retains the exact versioned runtime tree and worker helper. It skips fixed selector
  and unit checks/writes and reports `selected=false`, `systemd_units_installed=0`.
- Stage-only requires absent `/etc/vst-runner`, `/run/vst-supervisor` and `/run/vst-runner`;
  exactly inactive or not-found S2 units; no matching systemd jobs (parsed as `JOB UNIT TYPE
  STATE`); and empty inspectable cgroups. Unknown unit states, malformed job rows, or failure to
  enumerate any required state refuse staging. The WSL installer independently repeats these
  preconditions so direct invocation cannot bypass the host handoff checks.
- Added no transition, config, Store, key, identity, service-start or cleanup operation. Existing
  immutable destination collision remains fail-closed. The separate reviewed bootstrap selector
  transition is still required.

## Paths and contract

`tools/qa/install_wsl_runtime.ps1` and `tools/qa/install_wsl_runner_runtime.sh`. Stage output
retains `/opt/vst-runtime-<full-head>` and the versioned worker helper for a later exact-fingerprint
transition. This interface does not claim that the versioned artifacts are selected or accepted.

## Verification and status

No tests, checks, build, WSL provisioning or service operation were run. This change is uncommitted.
It implements the phase-6 runtime staging slice only; the bootstrap selector/unit transition and
manifest validator remain outstanding. Later test roles must verify default-mode compatibility,
stage-only no-selection, collisions and exact immutable artifact verification after all S2 coding
is complete.
