# 0081 S2 fail-closed bounded object import

## What changed

- Added a durable one-byte state journal to the shared target lock file: `HEALTHY`, `IN_PROGRESS`, or `POISONED`. The state is written and `fsync`ed under the cross-process lock. The state is set to `IN_PROGRESS` before a target object-writing child starts.
- Changed the target lock file format from the prior one-byte mutex file to a two-byte file (byte 0 is the OS lock; byte 1 is the durable state). A legacy one-byte lock file is rejected, because prior code did not record whether an un-reaped Git child might remain.
- After starting source `pack-objects` or target `index-pack`, cleanup attempts to kill active processes and requires successful `wait()`/reap of both. Any timeout or OS error that prevents confirming reaping durably marks the target `POISONED` before the storage lock is released. If writing `POISONED` fails, the previous durable `IN_PROGRESS` byte remains fail-closed.
- Every backend object writer (`hash-object -w` and `index-pack`) checks the journal while holding the same in-process and OS-level lock. `POISONED` and recovered `IN_PROGRESS` targets reject all future backend writes; no automatic clear/reset path is provided.
- Rejected source repository alternates (`objects/info/alternates`, `http-alternates`, Git worktree `commondir`, and external `.git` layouts). Source Git commands receive an allowlisted environment with `GIT_OBJECT_DIRECTORY` pinned to the intended local object directory.
- Added a bounded source preflight before packing: Git `count-objects -v` output is capped at 4 KiB per stream and command time is bounded; alternate output is rejected; object count is capped at 250,000; Git-reported source object size and a no-follow filesystem scan are capped at 512 MiB; filesystem entries are capped at 500,000.
- Copies only local loose objects and pack/index files into a temporary bare snapshot that omits `objects/info` and all source Git configuration. The requested commit must exist in that isolated object store before pack generation. `pack-objects` runs only against the sanitized snapshot with trusted pack resource settings.
- Added a 64 KiB limit to durable idempotency blobs and bounded the Git command output used to compare a prior record.
- Updated VST-017 to distinguish implemented controls from runtime evidence and remaining resource/environment limits.

## Why

The independent reliability review of code at `1ef3fee07d5743dc8e42c632e1dc3100601116a7` found that subprocess kill/wait errors were suppressed, after which the target lock could be released while `index-pack` was still writing. A security review also found that repository-local object alternates could make trusted source-side Git resolve worker-selected object IDs from a supervisor-readable object store. Git pack generation had no bounded source database preflight before traversal.

## Safety behavior and residual limits

- A child that cannot be confirmed reaped leaves the shared status `POISONED`; the recorded state cannot be cleared by this backend. If the final poison-state `fsync` fails, the earlier durable `IN_PROGRESS` state is retained; any later backend writer promotes/rejects that state before object writes.
- A legacy one-byte lock from changes 0077/0078 fails closed. Use of that target remains `NOT_RUN` until a fresh supervisor-owned target is provisioned; this change does not delete or rewrite existing target data.
- The source object count and byte caps, trusted pack settings, pack byte cap and bounded command time reduce the Git traversal surface. They do **not** prove a hard process-memory ceiling. An enforced OS memory limit (for example a verified cgroup or Windows Job Object limit) remains `NOT_VERIFIED`; the technical service owner is not identified in canonical project records. The operator is accountable for supplying/authorizing the sandbox runtime evidence.
- Each sanitized source snapshot is capped at 512 MiB but uses temporary disk under the target bare repository. No filesystem quota is enforced by this code; disk metadata and stale snapshot retention after abrupt supervisor loss are outside the logical object-store cap. A quota-limited per-run filesystem is still required before production qualification.
- The class requires `.git` and its object store to reside inside the supplied source repository root. External worktree common object databases are unsupported and must remain `NOT_RUN` until a separately safe source path is established. Repository inspection found no in-repository production caller or registry that proves the supplied source path is a designated per-run workspace.
- The cap and poison state govern writers that use this backend and honor the shared advisory lock. An external direct writer that bypasses this lock can alter the bare target; the target must remain supervisor-owned and exclusive to this backend.

## Ownership

- Accountable task owner: operator.
- Executor: Codex implementation agent.
- Required test author/executor: `e2e-runner`, after S2 coding is complete.
- Required independent review: fresh reliability and security review on the exact resulting source HEAD.
- Technical owner for the OS memory limit, filesystem quota, and any non-backend target writer: not identified in canonical project records.

## Verification state

- Review source: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`; implementation baseline: `7833b92` (documentation-only follow-up commits followed the source baseline).
- No tests, builds, CI, migrations, or runtime object imports were run for this change. During phase-6 coding, `git diff --check -- tools/vst/slice.py core/BACKLOG.md` was inadvertently run; it produced no output, and its exit code was not preserved. It is not test or runtime evidence and is not reported as a pass. No further checks are being run.
- E2E must cover injected cleanup uncertainty and persistent poison rejection, two independent backend processes contending on one target, state recovery after restart, alternate and worktree rejection, source object count/size overflow, bounded preflight output, source-only candidate transfer from the isolated snapshot, and target storage caps.
- Live-child termination/overflow cleanup remains `NOT_RUN` under the process-kill restriction. The OS memory ceiling, per-run filesystem quota, external direct-writer exclusion, and operational source-workspace binding remain `NOT_VERIFIED`.
