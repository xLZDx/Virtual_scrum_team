# S2 versioned worker-helper implementation design

Date: 2026-10-28  
Base HEAD: `9a5c41de5ce2878558402665eafaa0a80c09d177`  
GPT-PM decision: correlated request `b84e73a1-55ac-47b0-87f8-20261028f003`, reply `fc67f0f3-fd09-4c38-81cb-5988d8fe61d9`; ACCEPT — design only.

## Goal

Install and execute the exact S2 worker UID-transition helper without replacing the existing root-owned setuid helper. The observed fixed helper `/usr/local/libexec/vst-s4-worker-exec` is mode 4750 and belongs to an older build (`621ddc01`); the installer correctly refuses to overwrite different privileged bytes.

## Non-goals

Do not delete, chmod, rename, relink, or overwrite the existing helper. Do not add helper-path fallback/search, change the UID 997→999 transition, create a scheduler/assignment authority, activate operator credentials, or run process-kill/crash/mutation/E8/policy selectors. This design does not approve S2, runtime, E5, push, PR, or merge.

## Design

Install each build at `/usr/local/libexec/vst-s4-worker-exec-<full-40-hex-commit>`. Root-owned runner configuration binds that exact absolute path, full source commit, helper source SHA-256, and binary SHA-256. The path suffix must equal the configured full commit. Dispatcher and worker requests cannot choose the path.

At configuration load and immediately before each child launch, the runner opens the configured helper without following symlinks, verifies root ownership, the approved runner group, mode 4750, regular-file type, binary digest, and reported build/source identity. It passes only that configured path into the launch code. Missing, changed, or mismatched identity fails closed; there is no fallback to the old fixed path.

The installer builds under a private root-controlled staging directory, verifies compiler output and embedded source identity, and publishes only to an absent exact-version path with no-replace semantics. An existing byte-identical file with exact owner/group/mode/version is an idempotent success without metadata changes. Any collision, symlink, wrong owner/mode, or different bytes fails closed. Old and prior versioned helpers stay untouched. The deploy archive pins both `core.autocrlf=false` and `core.eol=lf` so shell scripts retain committed LF bytes under the host Git configuration.

The Runner config schema adds required `worker_exec_helper_path`, validated against the full configured helper commit. Systemd deployment documentation records versioned installation and clarifies that the optional operator RPC peer is absent/inactive unless independently provisioned.

## Failure and rollback

If archive bytes differ, compilation fails, the exact versioned destination collides, or post-install identity verification fails, refuse before publishing a runtime reference. Never fall back to the old fixed path. A missing/mismatched configured helper prevents service execution.

The current installer does not implement an upgrade, runtime-selector switch, or rollback. It installs immutable `/opt/vst-runtime-<full-commit>` trees and accepts `/opt/vst-runtime` only when it already points at the exact requested revision. It also refuses mismatching fixed systemd unit files. Re-running it against a different revision on an already-deployed host therefore fails closed; it is not a switch procedure. The exact-head artifact-only installation recorded in change 0476 did not enable or start any unit.

Before a later revision rollout, prepare a separate deployment change and reviewed runbook. It must define the operator-authorized service stop/quiesce sequence, confirm no active or unresolved assignment can survive the cutover, install and verify the immutable runtime/helper artifacts, provision the matching root-owned Runner configuration, and specify the order and failure handling for selector, unit and configuration changes. It must include an abort/rollback path that restores a mutually consistent retained runtime and configuration without replacing or deleting helper artifacts, plus post-switch verification of source/helper identity and service fencing. GPT-PM must review that deployment contract, and runtime execution must use a separately authorized isolated environment. Until then, keep the current selected revision and do not treat a later installer retry as an upgrade.

## Verification plan

After coding, the designated `functional-test-reviewer` adds/runs tests for exact path binding, malformed/traversing path, symlink and collision rejection, digest/build mismatch, idempotent exact existing file, and replacement between initial validation and launch. Then rerun affected S2 focused groups. At exact committed HEAD, `e2e-runner` verifies archive member bytes and performs the approved WSL installer/system evidence, checking the old helper's metadata/digest before and after. No prohibited selector runs. Fresh specialist reviews and a correlated exact-head GPT-PM final gate follow.

## Unknowns and owners

The root-owned Runner service configuration is provisioned outside the source installer; Codex owns the required config contract and evidence. Effective egress, inherited descriptor/forwarding controls, Windows process containment, production coordinator integration, operator-peer credentials, and run-bound E5 attestation remain separate open S2 acceptance items. GPT-PM owns adjudication; the operator owns actual E5 signature and independently provisioned operator credentials.
