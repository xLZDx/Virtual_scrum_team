# 0076 S2 bounded Git pack resources

## What changed

- Replaced whole-pack `subprocess.run(..., stdout=PIPE)` buffering with a 64 KiB streaming pipe from source `pack-objects` into target `index-pack`.
- Added a 64 MiB maximum transferred pack size and a 250,000 object-count ceiling checked from the Git pack header before forwarding its first complete header.
- Forced trusted Git pack settings on the source command: one packing thread, 16 MiB window memory, a 10-object delta window, 16 MiB delta cache, and a 32 KiB delta-cache item limit. These command-line settings override worker-controlled repository-local configuration for the relevant resource controls.
- Added a single bounded timeout for both subprocesses, termination and cleanup when the size/time bounds are exceeded, and bounded diagnostic capture.
- Kept target-side `index-pack --strict`, commit verification, and guarded ref update. The hook-free pack path remains free of source transport helpers and push hooks.

## Why

An independent code review of exact source HEAD `202e0680e8e1b4fb30dcbe9659bf550d06443d90` found that worker-local Git configuration could select unlimited `pack.windowMemory` and automatic thread count, while the trusted process buffered the entire pack in memory. The source command now overrides these settings and streams with byte and object limits.

Git 2.53.0.windows.1 was observed in the local environment with `git --version`. Its `git index-pack -h` output did not advertise a maximum-input-size option, and the current official `git-index-pack` manual does not list one, so the implementation does not rely on that flag. The current official `git-config` manual documents `pack.windowMemory`, `pack.deltaCacheSize`, `pack.deltaCacheLimit`, and `pack.threads`; the selected settings are passed through Git's standard `-c` command-line configuration interface. The implementation requires no newer index-pack option.

## Resource boundary and remaining dependency

The code bounds each transferred pack to 64 MiB and the associated pack index to at most 250,000 entries. This bounds per-import pack and index material, but it does not impose an aggregate quota on a persistent target object directory across many distinct operations, nor does Git expose a portable per-process memory quota for all object traversal allocations. The synthetic target must therefore remain run-scoped and reside on a quota-limited disposable filesystem; exact aggregate disk and process-memory quota enforcement remains `NOT_VERIFIED` and must be included in fresh S2 E2E/security review before this path is treated as production-capable.

## Ownership

- Accountable task owner: operator.
- Executor: Codex implementation agent.
- Required test author/executor: `e2e-runner`, after all S2 coding is complete.
- Required independent review: fresh reliability/security/code review on the exact resulting source HEAD.
- Technical service owner for aggregate target-storage and process-memory quotas: not identified in canonical project records.

## Verification state

- Baseline source HEAD: `202e0680e8e1b4fb30dcbe9659bf550d06443d90`.
- Local tool evidence: `git --version` reported `git version 2.53.0.windows.1`; `git index-pack -h` did not list a max-input-size option. These were capability inspection commands, not tests.
- Official references: [git-index-pack documentation](https://git-scm.com/docs/git-index-pack) and [git-config documentation](https://git-scm.com/docs/git-config).
- No tests, checks, builds, CI, migrations, or runtime pack operations were run for this change.
- E2E pack transfer, local malicious-config resistance, hard timeout/size cleanup, and exact-head specialist review remain `NOT_RUN` pending designated agents. Aggregate target-storage and full process-memory containment remain dependent on a quota-limited per-run environment.
