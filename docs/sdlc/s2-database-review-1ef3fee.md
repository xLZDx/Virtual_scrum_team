# S2 database and object-store review

## Review identity

- Review role: `database-reviewer`.
- Model and effort: GPT-6 Luna, medium effort.
- Source code reviewed: `1ef3fee07d5743dc8e42c632e1dc3100601116a7`.
- Repository head during review: `eab4ea5d6363e3f8efa99533a996a5388ffaa48c`; this later commit adds tests/evidence only, not production source.
- Review scope: `SyntheticOperationBackend` target object accounting, cumulative storage cap, object-write serialization, lock release behavior, and partial import failures in `tools/vst/slice.py`.
- Evidence consulted: source code, change records 0076-0077, and [`s2-e2e-hook-free-pack-1ef3fee.md`](evidence/s2-e2e-hook-free-pack-1ef3fee.md).
- No tests, checks, builds, CI, migrations, or runtime operations were run for this review.

## Finding

### MAJOR — an unreaped Git child can outlive the target storage lock

In `tools/vst/slice.py`, `_import_head_locked` starts `pack-objects` and `index-pack` while `_import_head` holds `_target_storage_lock` (`1232-1242`). The timeout callback suppresses errors from `process.kill()` (`1286-1296`). Its `finally` block repeats that suppression and also suppresses a one-second `process.wait()` timeout (`1355-1371`). If `index-pack` remains alive after either condition, `_import_head_locked` can unwind and `_target_storage_lock` can release its OS lock while the child continues writing into `objects/`.

A second backend instance can then acquire the same lock, scan current object-file lengths, reserve capacity, and begin another object write while the first child is still adding files. The serialized-writer assumption and 512 MiB cumulative cap no longer hold. The same race is possible after a non-timeout exception in the streaming path if cleanup cannot terminate and reap the child.

This failure path is not covered by the current E2E evidence: live child termination and post-start overflow cleanup are explicitly `NOT_RUN` because the test policy prohibits process-kill scenarios. The Windows normal lock behavior and WSL POSIX `flock` contention test prove acquisition, contention, and normal release only; they do not prove lock retention when process cleanup fails.

**Required disposition:** treat the target as poisoned and refuse any later object writes if child exit cannot be confirmed, or use a termination/reap strategy that guarantees every writer has exited before releasing the storage lock. Do not suppress cleanup failures and proceed as if the object store were quiescent. The operator is accountable for the delegated S2 task; Codex is the executor. No separate technical service owner for direct target writers is established in canonical project records.

## Other reviewed invariants

- The target object-byte walk recursively counts file lengths under the managed `objects/` directory and rejects symlinked entries. Target Git processes receive a pinned `GIT_OBJECT_DIRECTORY`; the backend does not inherit ambient alternate-object-directory variables.
- Both backend object writers—`hash-object -w` for idempotency blobs and `index-pack` for candidate packs—run while holding the same per-target OS lock and in-process lock. The reservation is made before launching the pack processes. Cross-process lock contention/release is covered on Windows and POSIX by the E2E record.
- The 512 MiB cap is a backend-managed logical file-length limit. It does not constrain a direct external writer that ignores the advisory lock, filesystem metadata, or files outside `objects/`. The change record explicitly requires a supervisor-owned target and identifies that limitation; no separate disk-quota claim is made.
- A failed or partial `index-pack` may leave target files. Under the current single-writer assumption, later scans account for those files and subsequent reservations fail closed when insufficient capacity remains. This accounting conclusion is conditional on resolving the unreaped-child finding above.
- The pack and object-count reservations are conservative by inspection, but no runtime test exercised a maximum-sized pack/index or post-import overflow because the cleanup path would invoke process termination. Keep that scenario `NOT_RUN`.

## Conclusion

The cumulative object-store cap and cross-process serialization are sound for normal backend-managed writes, as covered by the available Windows/WSL lock evidence. One MAJOR remains: cleanup does not prove child exit before releasing the lock, so an orphaned `index-pack` could invalidate both properties. No other database finding is raised in this review.
