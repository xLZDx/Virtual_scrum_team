# 0072 S2 synthetic Git publication security design

## Goal

Prevent a worker-controlled source repository from executing Git hooks or redirecting the trusted supervisor's local publication operation, which could inherit runner identity and reach runner-only signer IPC.

## Current behavior and evidence

- At code head `c0e7e9ce15958b6c6de7811bcaf1020119ba169d`, `SyntheticOperationBackend` invokes `git -C <source_repo> push <bare_target> <head>:<ref>`.
- A Git push may invoke the source repository's `pre-push` hook. Source hooks or `core.hooksPath` are worker-controlled unless separately protected. The WSL evidence records runner UID 997 as authorized to use signer IPC and worker UID 999 denied; therefore a hook invoked by the runner would cross the intended identity boundary.
- Security reviewer `security-reviewer` / GPT-6 Luna, medium, classified this S2 S7.2 / VST-017 risk as MAJOR. The current tests do not establish that worker access to `.git` configuration is denied.

## Options

1. Keep `git push` and pass `--no-verify` plus a trusted empty `core.hooksPath`. This blocks `pre-push` hooks but still asks Git to interpret a worker-controlled repository configuration and remote URL.
2. Export/import Git objects through a worker-controlled Git remote. This can invoke upload-pack configuration or helper behavior from the source repo.
3. Run bounded local `git pack-objects --stdout --revs` against the exact requested source commit, import the resulting pack into the supervisor-owned bare target with `git index-pack --stdin`, then atomically update the target ref with `git update-ref <ref> <new> <expected-old>`. **Chosen:** it avoids `push`, transport helpers, source hooks and remote URL rewriting. Fast-forward and pull-request conflict behavior are checked explicitly.

## Design

- Source operation: allowlisted command `git -C <source_repo> pack-objects --stdout --revs`, with exactly the requested candidate head on stdin, a finite timeout, bounded/sanitized environment, and no network or credential configuration. No Git command mutates or executes repository hooks in the worker source.
- Target operation: `git --git-dir <bare_target> index-pack --strict --stdin` imports the pack in the trusted target; then target-side `cat-file` verifies the commit and target-side `merge-base --is-ancestor` enforces fast-forward for branch refs. `update-ref` uses the observed old value (or all-zero sentinel for create-only) to prevent concurrent clobber. Pull-request refs remain create-only for a key and reject a different head.
- Existing operation-key/payload binding is written in the trusted target before object transfer. The Store's durable pending/completion protocol and same-key retry behavior remain unchanged. A timeout leaves `PENDING`; imported but unreferenced objects are harmless and same-key retry is safe.
- No SQLite schema, receipt bytes, or key boundary changes. No real remote, network access, source clone or install.

## Failure modes and rollback

- Invalid/missing source head, invalid pack, timeout, non-fast-forward branch update or unexpected existing pull-request head returns no success and leaves the Store operation pending for same-key diagnosis/retry.
- A crash after pack import but before ref update leaves unreachable objects in the local bare repository; retry imports/reuses objects and attempts the ref update with the same expected-old rules.
- A source-controlled `pre-push` file is never invoked because no push command is used.
- Reverting the code commit restores the previous backend; promotion remains blocked until the hook-denial regression passes.

## Verification and ownership

- `e2e-runner` owns a regression with a malicious source `pre-push` hook marker and timeout/restart publication through the pack path. The test agent runs it only after the source change is complete.
- `security-reviewer` rechecks the exact final code path; `reliability-reviewer` reviews timeout/crash/ref-race behavior.
- Accountable task owner: operator. Executor: Codex. No named technical service owner is established in the repository.

## Unknowns

- Runtime pack import/ref-update behavior across supported Windows and WSL Git versions remains for E2E evidence. The test will not invoke process-kill or kill-table scenarios.
