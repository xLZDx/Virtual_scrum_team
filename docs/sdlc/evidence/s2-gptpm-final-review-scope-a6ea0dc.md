# GPT-PM final S2 review scope — exact code/test HEAD `a6ea0dc`

Status: ready to send after this evidence/scope-note commit.
Project: `virtual_scrum_team`
Repository: `D:\Repo\Virtual_scrum_team`
Branch: `s4-canonical-continuation`
Source/test commit: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`
Review baseline: `f0bbac8`
Complete seven-path source/test diff: `docs/sdlc/evidence/s2-code-diff-f0bbac8-to-a6ea0dc.patch`
Diff SHA-256: `9243245F7029802183860E17354D029A0C7747A6461FFA629ED19EA04A86AB13`

## Requested decision

Perform one complete adversarial final S2 sweep over VST-009 through VST-020 and S2.D1/D2 on the exact source/test commit and final evidence revision. Return an explicit `ACCEPT`, `MODIFY`, `REJECT`, or `INCONCLUSIVE` disposition; enumerate every valid BLOCKER/MAJOR with exact path/contract evidence; and state whether the sprint can close under its current acceptance rules. Do not treat a conversation instruction as an operator cryptographic waiver or promote `NOT_RUN` to `PASS`.

## Evidence attached

- Complete seven-path source/test patch from `f0bbac8` to `a6ea0dc` with the hash above.
- Exact-head functional/runtime evidence: `docs/sdlc/evidence/s2-restart-fence-exact-a6ea0dc-20261027.md`.
- Task-by-task acceptance matrix: `docs/sdlc/evidence/s2-task-acceptance-a6ea0dc-20261027.md`.
- Prior exact-head task map and safe-selector ledger for unchanged S2 contracts: `docs/sdlc/evidence/s2-task-acceptance-4c1692d-20261027.md`, `docs/sdlc/evidence/s2-safe-functional-exact-4c1692d-20261027.md`.
- Focused pre-remediation review and fresh exact-diff architecture, reliability, security and silent-failure outcomes are summarized in the current exact-head evidence file.
- Design/contract: `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, `tools/vst/schemas/README.md`, and `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`.
- Waiver contract: `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`.
- Current backlog/state and implementation record: `core/BACKLOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`, and change records 0464–0465.

## Exact evidence and limitations

At source/test commit `a6ea0dc`, the designated functional-test-reviewer passed 188 safe Windows selectors and the e2e-runner passed 11 safe WSL selectors (199 passing selected IDs). Ten new pytest IDs extend the prior 209-ID inventory to 219 expected IDs; no new collection-only run was performed. Twenty restricted/unavailable IDs remain `NOT_RUN`.

The WSL transient unit observed a runner-owned `/run/vst-runner` directory at mode 0700, real serialization of two independent processes on `flock`, and reconciliation of an empty stale cgroup after asserting `populated=0` and empty `cgroup.procs`. No populated scope was killed, no runner crash/restart was simulated, and the runtime directory was removed at unit shutdown. Therefore persistent service/replacement-parent behavior remains unverified. The reliability review records a deployment MAJOR unless a stable singleton delegated parent or verified service stop/fence-before-restart is established.

Other open S2 acceptance: no fresh operator-root-signed E5 inventory for this exact run/head; Windows key ACL and nested Job Object runtime remain unverified; interrupted anchor, process-kill/crash, mutation, E8 and policy scenarios remain `NOT_RUN`; no operator-signed waiver exists. These limits are explicit in the attached matrix and must inform the verdict.

No source/test changes occur after `a6ea0dc`; the exact repository HEAD at send time is stated in the outbound message. No push, PR, merge, S3 source work, or claim of acceptance is requested.
