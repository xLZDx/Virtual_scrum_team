# 0077 S2 cumulative synthetic target object-storage cap

## What changed

- Enforced a 512 MiB cumulative byte cap over the complete synthetic bare repository `objects` tree, including loose objects, packs, and indexes.
- Added a shared OS file lock at `<bare-path>/.vst-object-storage.lock`, outside the counted object tree. POSIX uses `flock`; Windows uses a one-byte `msvcrt` lock. Acquisition has the backend's bounded command timeout, and the kernel releases the lock on process exit.
- Serialized both target object-write paths (`hash-object -w` for idempotency records and `index-pack` for transferred packs) across separate backend/supervisor processes.
- Before pack import, reserved the maximum 64 MiB pack plus a conservative index/reverse-index bound (48 bytes per entry plus 4 KiB) derived from 250,000 objects. A request fails closed when the cumulative cap cannot cover that reservation. Idempotency blobs reserve their raw size plus conservative compression/header overhead.
- Sanitized target Git process environments and pinned `GIT_OBJECT_DIRECTORY` to the bare repository's managed `objects` directory. Untrusted alternate-object-directory and other ambient Git environment variables are not inherited.
- Reject a symlink target object directory or symlink entries in the counted object tree.

## Why

Change 0076 bounded each import but did not bound cumulative storage across distinct operation keys. Repository inspection found `run_lifecycle_scenarios` creates `local-bare.git` beneath its caller-provided `workdir`; the function does not create or clean a per-run temporary root, and no in-repository caller was found that proves `workdir` is always per-run. Focused test helpers create bare repositories beneath pytest `tmp_path`, but that is test-fixture behavior and cannot establish an operational per-run guarantee. Therefore the backend now enforces its own cumulative logical storage cap and serializes every backend object writer.

## Concurrency and boundary

The lock file is located at `<bare-path>/.vst-object-storage.lock`. Advisory locks are cross-process and shared by all backend instances resolving to the same target bare repository. Every object write in `SyntheticOperationBackend` is inside this lock. The target Git environment fixes its object directory and omits alternate object directories, so the byte counter covers the destination that those commands write.

This is a logical file-length quota, not an operating-system filesystem quota. It bounds backend-managed file bytes at 512 MiB when all writers use this backend. A separate process that writes directly into the same bare repository and ignores the advisory lock can bypass the cap. The target must remain supervisor-owned and exclusively writable through this backend; canonical project records do not identify a separate technical service owner for that boundary. Filesystem metadata, journals, and unrelated files outside the Git object directory are also outside this cap.

## Ownership

- Accountable task owner: operator.
- Executor: Codex implementation agent.
- Required test author/executor: `e2e-runner`, after S2 coding is complete.
- Required fresh review: independent reliability/security review on the exact resulting source HEAD.
- Technical owner for any non-backend writer or filesystem quota service: not identified in canonical project records.

## Verification state

- Baseline source HEAD: `4671e2a804aaae6b0d1eb25c093d439850a0fce2`.
- Code and documentation are implemented; no tests, checks, builds, CI, migrations, or runtime pack operations were run for this change.
- E2E must verify cumulative cap refusal, idempotency blob accounting, concurrent independent backend instances, POSIX and Windows lock behavior, timeout/restart recovery, path pinning, and fail-closed behavior for symlinked storage entries.
- External direct writers and OS filesystem metadata remain outside the code-level cap; do not claim a filesystem quota or production qualification from this implementation.
