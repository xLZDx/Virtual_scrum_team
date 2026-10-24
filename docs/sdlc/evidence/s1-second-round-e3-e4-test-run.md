# S1 second round: E3 (store) and E4 (runner) test run

## Command
`C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e3_store.py tests/vst/test_e4_runner.py`
(repo root `D:\Repo\Virtual_scrum_team`, Windows 11, Python 3.14)

## Revision
`git rev-parse HEAD` = `5a749ee620cb65fc09ba36575c27d1999dfa215e`, working tree dirty: the second-round code
(`tools/vst/store.py`, `runner.py`, `slice.py`, `gate.py`, `contracts.py`, schema README), changes 0019 and 0020
and the test files are uncommitted (24 entries in `git status --short`). The result proves this working-tree
state only.

## Result
Final run (after the runner Job Object fix, change record 0021):
`506 passed, 2 skipped, 1 warning in 61.59s (0:01:01)` - no failures.

An earlier run on the same HEAD before the fix: `1 failed, 505 passed, 2 skipped` - the failing test was
`test_stray_descendant_is_killed_after_the_root_command_exited_normally` (taskkill found no descendants after
the root exited; heartbeat file grew 11 -> 19 bytes). After the fix it passes and also asserts
`report['commands'][0]['job_object'] is True` on Windows.

- Test adjustments for the fix: the `no_stray_kill` fixture also disables `_JobObject.attach` so the two
  exit -4 tests still hold a pipe from a stray holder; the per-command report key set now includes
  `job_object` (True on Windows).
- Skipped (2): POSIX permission-bit test (Windows host) and one POSIX-only/symlink-capability skip.

## Tests added or changed
- `tests/vst/test_e3_store.py`: schema version 3, `receipt_count` column; retry cap by `failed_attempts`
  (lost leases, FAIL/INCONCLUSIVE counted, BLOCKED/NOT_RUN/PASS not, max over slots, released and fenced
  leases never counted, several takeovers then lease granted, boundary, marker once); budget seeded from
  `cost_cap`, `set_budget` above cap / unregistered refused, `acquire_lease` and `append_receipt` refuse at
  spent >= cap, `charge` over cap commits marker then raises, concurrent charges; 12 anchor tamper variants
  raise `integrity` on append and are not repaired, valid-MAC wrong count/head with a control; snapshot
  reads under a concurrent writer; `LEASE_EXPIRED_PARTIAL`; `supervisor_key == event_key` -> kind `key`;
  `OPERATOR_ACTION` refused.
- `tests/vst/test_e4_runner.py`: `extra_env` shadowing (26 names incl. case variants, DYLD_*, allowlist),
  benign look-alike names allowed, report `capture_incomplete`, exit -4 (hermetic: post-exit kill disabled
  and short join), -4 beats -3, short-lived holder not flagged, post-exit tree kill (asserts job_object True on Windows).
- `tests/vst/e1e4_helpers.py`: not modified.

## Not verified
POSIX behavior (process-group kill, permission bits, symlinks); the real (unpatched) capture-incomplete path (tests disable job and taskkill); mutation checks NOT_RUN by operator decision; slice/E5 and
E1/E2 files not run here.
