# 0084 S2 Windows source-object snapshot identity

## What changed

- Replaced the Windows source-file identity check that compared `DirEntry.stat()` with `os.fstat()` fields. The E2E report records that this comparison failed on Windows for all three snapshot-backed publication regressions, before either pack writer started.
- On Windows, source object files are now opened with `CreateFileW` using `FILE_FLAG_OPEN_REPARSE_POINT` and a read-only sharing mode. The code rejects reparse points, directories, negative sizes, and files with more than one hard link. The sharing mode prevents concurrent write or delete opens while the snapshot is copied.
- The opened handle is identified through `GetFileInformationByHandleEx` (`FileIdInfo`), and its volume serial, 128-bit file ID, size, and link count must remain unchanged after copying. Failure to obtain these Win32 properties fails closed; there is no fallback to the mismatched Python stat fields.
- POSIX retains its `O_NOFOLLOW` open and compares directory-entry and descriptor device, inode, and size, also rejecting multiple hard links.
- The existing source-root containment and symlink/junction checks remain. The copied Git object files are still consumed by Git's object reader and `pack-objects`; the requested commit must still resolve in the isolated snapshot before transfer.

## Why

The E2E run documented in `docs/sdlc/evidence/s2-e2e-bounded-snapshot-ed531.md` used source HEAD `ed531264d0344c67e948e126c420e60f5272226c` on Windows 11 / Python 3.14.3. It reported 77 passed, 14 skipped, and 3 failed. The failed cases were:

- `test_hook_free_publication_transfers_source_only_commit_without_running_pre_push`
- `test_synthetic_backend_fast_forward_and_conflicting_branch_and_pr_refs`
- `test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key`

All three raised `RuntimeError: synthetic source object file changed during snapshot` at `_copy_source_object_file`. The guard compared `st_dev`, `st_ino`, and `st_size` returned by `DirEntry.stat(follow_symlinks=False)` against `os.fstat(fd)`. The report confirms the comparison failed but does not preserve the individual values. These failures were classified as one Windows compatibility defect, not a flake; no repeat was run before this remediation.

## Safety behavior and residual limits

- Windows identity is now taken from the opened file handle, not from Python's directory-entry stat cache. `OPEN_REPARSE_POINT` plus `FileAttributeTagInfo` rejects a path that resolves to a reparse point; `FileStandardInfo.NumberOfLinks == 1` rejects hard-linked source objects. The handle is held with sharing that denies concurrent write/delete access during the copy.
- POSIX retains no-follow open and path-to-handle identity comparison. Source repository and object-store real-path containment checks remain unchanged.
- This code does not independently hash every unreachable loose object copied into the snapshot. Git's object traversal validates objects it reads while generating the transfer pack; candidate commit resolution remains required. Runtime proof of these paths is pending the E2E rerun.
- If the Windows API binding or `GetFileInformationByHandleEx` queries fail, the import stops before packing; it does not weaken identity or link checks. Microsoft documents `FileIdInfo` support starting with Windows 8 / Windows Server 2012; older Windows versions and filesystems that do not provide it fail closed ([`FILE_INFO_BY_HANDLE_CLASS`](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ne-minwinbase-file_info_by_handle_class), [`FILE_ID_INFO`](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)). `FILE_FLAG_OPEN_REPARSE_POINT` is used to open the reparse point itself for explicit rejection ([Reparse Points and File Operations](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations)).

## Ownership

- Accountable task owner: operator by delegated S2 assignment.
- Executor: Codex implementation agent.
- Test author/executor: E2E runner, for a fresh Windows run against the resulting source commit.
- Technical owner of the Windows host/runtime: not established by the inspected project records.

## Verification state

- Failing source revision: `ed531264d0344c67e948e126c420e60f5272226c`.
- The recorded failing E2E command was `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py`; evidence is in `docs/sdlc/evidence/s2-e2e-bounded-snapshot-ed531.md`.
- No tests, checks, builds, CI, migrations, or runtime imports were run for this implementation. The prior red result is diagnostic evidence for the defect, not verification of this fix.
- Required next step: E2E runner executes the focused Windows lifecycle/store run on this exact new source HEAD. Preserve all existing skipped process-kill/overflow cleanup cases as `NOT_RUN`.
