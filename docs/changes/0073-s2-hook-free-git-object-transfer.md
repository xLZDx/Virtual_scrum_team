# 0073 S2 hook-free Git object transfer

## What changed

- Replaced `git push` from the worker source repository with a bounded source-side `pack-objects --stdout --revs` operation, target-side strict `index-pack --stdin`, target commit verification, and target-side ref compare-and-swap.
- Source Git receives a minimal environment that disables system/global configuration, interactive prompting, optional locks, lazy promisor fetch and replace objects. No remote URL, transport helper, push command or source hook is used.
- Branch ref updates preserve fast-forward behavior through an ancestry check; pull-request refs remain create-only; concurrent ref changes are rejected or treated as the identical already-completed head.
- Updated S2 S7.2 and schema documentation to describe the protected publication path.

## Why

Fresh security review at source HEAD `c0e7e9ce15958b6c6de7811bcaf1020119ba169d` identified that `git -C <worker-source> push` may execute a worker-controlled `pre-push` hook under the trusted runner identity. The WSL evidence records that runner identity as the only identity authorized to reach signer IPC; therefore a worker-controlled hook could cross the signer boundary. Review role/model/effort: `security-reviewer` / GPT-6 Luna / medium. The finding was MAJOR for S2 S7.2 / VST-017; its evidence and design alternatives are in change record 0072.

## Ownership

- Accountable task owner: operator.
- Executor: Codex.
- Required test author/executor: `e2e-runner` for a hostile source pre-push hook, publication, timeout/restart and conflicting ref regression.
- Required fresh review owner: security reviewer for exact final source head.

## Verification state

- Prior source head reviewed and found vulnerable: `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`.
- Prior focused tests at that source head passed (76 passed, 14 skipped), but they do not verify this later security fix; see records 0070-0071.
- No tests, checks, builds, CI, migrations, or hook execution were run by Codex for this change.
- The new hook-denial and pack-transfer regressions are assigned to `e2e-runner` after code completion.
