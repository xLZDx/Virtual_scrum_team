# Change record 0310: fixed WSL worker UID helper source

## What changed

- Added `tools/qa/worker_exec.c`, a fixed launcher that accepts only `/usr/bin/python3.12 -I -c`, verifies caller identity 997:988, clears supplementary groups and inherited file descriptors, drops real/effective/saved IDs to 999:989, sets `no_new_privs`, replaces the environment, and executes without a shell. It embeds the exact candidate HEAD and source hash and provides a non-privileged `--version` identity response.
- Added `tools/qa/install_wsl_worker_helper.sh`, which installs only at the fixed WSL helper path with owner `root`, group `vst-runner`, and mode `4750`. The root script must be streamed from its immutable Git blob with sanitized Git configuration and replacement refs disabled; it is not safe to invoke from the runner-writable candidate checkout. It validates the selected Ubuntu 24.04 WSL configuration, fixed account mappings, exact candidate commit, clean worktree, and install directory before making any system change. Git configuration, replacement refs, fsmonitor, hooks and pagers are disabled. It builds from the exact committed C blob in a root-only directory on the destination filesystem and atomically installs one binary; it refuses to replace an existing target.
- Updated the plan, backlog, decision log and design status. The report-bound selector and runtime proof remain pending.

## Why

The operator authorized one narrow report-bound child identity transition from the WSL QA runner UID/GID 997:988 to the worker UID/GID 999:989. The helper fixes the caller, target and interpreter; it does not alter the whole QA runner, its scratch/evidence ownership, or the separate restricted-root harness.

## Contracts and paths

- `tools/qa/worker_exec.c`
- `tools/qa/install_wsl_worker_helper.sh`
- `docs/S4_WSL_WORKER_UID_HELPER_DESIGN.md`
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` (S4.2.3 / AC-16)
- `core/BACKLOG.md` (VST-038)
- `core/DECISION_LOG.md`

## Verification state

No tests, builds, helper installation, or runtime checks were run in this implementation step. Read-only GPT-6 Luna code and security reviews identified and drove fixes for root-script trust, Git replacement refs, environment inheritance, and same-filesystem installation; both final follow-ups reported no remaining finding in their scope. The existing S4 platform matrix remains non-approving, and the identity selector is not yet present. The documentation registry is refreshed in this source commit.

## Ownership and next action

Operator is accountable; Codex implemented the helper. Test authorship and execution belong to `functional-test-reviewer` and `e2e-runner`. WSL infrastructure service owner is unknown. Next: have the designated test agent author and map the selector, commit that test/code work, then install and run it on the exact candidate head.
