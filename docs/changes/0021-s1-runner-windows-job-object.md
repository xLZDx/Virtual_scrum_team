# Change record 0021: S1 runner uses a Windows Job Object for process-tree containment

## What changed
- `tools/vst/runner.py`: on Windows the child is assigned right after `Popen` to a Job Object created with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (ctypes, stdlib only, `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` via `SetInformationJobObject`; lazy, typed `ctypes.wintypes` bindings, import-safe on non-Windows). On every exit path (normal exit, timeout/deadline, any exception) `TerminateJobObject` then `CloseHandle` run. If job setup or assignment fails, the previous behavior is used (`taskkill /PID <pid> /T /F` after a normal exit) and the per-command report has `job_object = False`. On timeout `taskkill /T /F` plus `proc.kill()` stay as an extra fallback. POSIX process-group path and exit codes -1/-2/-3/-4 are unchanged. New helpers: `_win_api`, `_JobObject` (`attach`, `terminate_and_close`).
- `tools/vst/schemas/README.md`: Runner section describes the job object, the race and the fallback; per-command report gains `job_object`.

## Why
After a normal root exit, `taskkill /PID <root> /T /F` reports "process not found" and never reaches descendants, so a grandchild kept running after `run_and_sign` returned (test `test_stray_descendant_is_killed_after_the_root_command_exited_normally`). Job membership survives the exit of the root.

## Affected contracts and paths
Per-command report dict gains the bool key `job_object` (additive). Known limits: the child is not created suspended, so a grandchild spawned between `Popen` and the assignment is not a member; a process already in a non-nestable job falls back to taskkill. Paths: `tools/vst/runner.py`, `tools/vst/schemas/README.md`.

## Verification state
Code changed only. No tests and no Python were run. Not independently reviewed. Tests that monkeypatch `runner._taskkill_tree` to simulate a stray holder (`no_stray_kill` fixture in `tests/vst/test_e4_runner.py`) must also disable the job (`_JobObject.attach` -> None), otherwise the holder is killed with the job and exit code -4 is not produced on Windows.
