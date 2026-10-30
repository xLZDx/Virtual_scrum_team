# Change 0622 — S2-4 masked WSL mount classification and shutdown diagnosis

## Task and acceptance delta

- **Task:** S2-4 runtime/E5 qualification; S2-5 remains queued.
- **Delta:** accept only the exact systemd-inaccessible backing mount for configured WSL paths, while continuing to reject visible Windows/host mounts; diagnose why a prior authorized sandbox-probe invocation ended with `SIGTERM`.
- **Current disposition:** source correction and focused regression are complete in the dirty worktree; the runtime/E5 result is still `INCONCLUSIVE` and S2-4 is not closed.

## Implementation

`tools/vst/preflight.py` now permits a WSL integration target only when its path is exactly one of
`SYSTEMD_MASKED_WSL_PATHS` and the observed mount matches the root device and filesystem with
mount root `/run/systemd/inaccessible/dir`. Other `/mnt/*` paths remain unapproved; drive-backed
`drvfs` and `9p` mounts continue to fail the Windows-drive check. Unrelated host mounts continue to
fail the source/root checks.

The runtime qualification launcher candidate uses a single long-lived WSL child and streams one
bounded protocol through that process (`tools/qa/run_s2_runtime_qualification.py::_run_bounded_wsl`).
This is the intended remedy for the prior split-call lifecycle; it is not yet runtime-proven.

## Verification and review evidence

- Read-only systemd journal query confirmed that the earlier invocation's `SIGTERM` coincided with
  distro shutdown. At `2026-10-30T03:42:29.579768Z`, `systemd-logind` recorded “The system will
  power off now!”; at `03:42:29.601567Z`, it recorded “System is powering down.” The probe exited
  from `SIGTERM` at `03:42:29.655973Z`. See
  `docs/sdlc/evidence/s2-runtime-distro-shutdown-20261030.md` and the original attempt JSON.
- A separate read-only journal query of the probe unit returned the start and exact `INVOCATION_ID`
  records; it started at `03:41:51.925972Z` and exited at `03:42:29.655973Z`.
- A `code-reviewer` found the incorrect unconditional WSL-path refusal and, after this correction,
  confirmed the exact masked-path predicate and fail-closed handling for all other `/mnt/*`, drive,
  and unrelated host paths. Read-only; no tests run by the reviewer.
- `functional-test-reviewer` added regression coverage for one correct `/mnt` systemd mask, both
  `drvfs` and `9p` drive mounts, an unrelated `/mnt/wslg` mount, and an unrelated host ext4 mount.
  Command:
  `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_sandbox_probe.py::test_environment_collector_accepts_systemd_inaccessible_directory_mount_for_masked_wsl_path tests/vst/test_s2_sandbox_probe.py::test_environment_collector_classifies_windows_drive_mounts tests/vst/test_s2_sandbox_probe.py::test_environment_collector_fails_closed_for_unlisted_host_mount`
  Result: **5 passed, 1 warning, 0 skipped**, exit 0, 0.32 s, Python 3.14.3 on Windows/PowerShell.
  The test ran at committed base `aedf712c07eb0cc531852d18443faa497e19bb2d` plus the in-progress
  S2-4 source/config worktree. It is not exact-commit evidence. Full log and provenance:
  `docs/sdlc/evidence/s2-masked-wsl-mount-regression-2026-10-30.txt` and `.json`.
- The same test owner added mock-only contract coverage for the bounded runtime harness:
  uncorrelated/oversized input refuses before WSL, exact archived source pins are accepted while
  worktree drift is rejected, exactly one WSL child is launched, and terminal HOLD with output hashes
  is persisted without retry. Command:
  `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runtime_qualification_harness.py`
  Result: **4 passed, 1 warning**, exit 0, 0.38 s, Python 3.14.3/Windows PowerShell. This ran at
  `aedf712c` plus the dirty S2-4 worktree and is not exact-commit evidence. Full log and provenance:
  `docs/sdlc/evidence/s2-runtime-qualification-harness-tests-final-2026-10-30.txt` and
  `docs/sdlc/evidence/s2-runtime-qualification-harness-test-run-2026-10-30.json`.

## Limits and next action

### Recovery freshness defect found during final S2-4 review

The focused security re-review found that existing-Store recovery accepted the original durable
runtime-observation claim without measuring the environment again. A newly accessible container
socket or changed mount could therefore make the stored “safe” inventory stale before API
readiness. This was a concrete S2-4 acceptance defect, not another runtime attempt.

Codex added a recovery-path correction in `tools/vst/supervisor_service.py` and
`tools/vst/preflight_capture.py`: recovery first verifies the original single-use Store claim,
then takes a new bounded Supervisor-captured systemd observation with a fresh random nonce,
validates its current spec/network-profile identity, namespace boundaries and ≤120-second
freshness, and only then proceeds. It does not rewrite or re-consume the original Store binding.
The security re-review and independent code review found no remaining BLOCKER/MAJOR in this
focused delta. Neither reviewer ran tests or runtime.

The designated functional-test reviewer added recovery-loader regression cases and ran the bounded
selector group on Windows. The command selected nine cases, but **all nine were skipped** by the
POSIX-path guard (`9 skipped, 21 deselected`); this is **NOT_RUN**, not PASS. A follow-up attempt
found the existing Ubuntu-24.04 WSL has no `/mnt/d` project mount; the exact `cd` failed and pytest
was not reached. Evidence:
`docs/sdlc/evidence/s2-4-supervisor-recovery-loader-tests-final-2026-10-30.txt` and
`docs/sdlc/evidence/s2-4-supervisor-recovery-loader-test-run-2026-10-30.json`, plus
`docs/sdlc/evidence/s2-4-supervisor-recovery-loader-wsl-attempt-2026-10-30.txt` and `.json`. The
The test owner streamed only the required source/test archive to a disposable WSL test directory
(no installation, mount, or service changes). Two fixture-only attempts failed before recovery
assertions; their exact causes (`capture.Path` and a mismatched mocked PID namespace) are retained
as superseded history in the final evidence record. After correcting those test fixtures, the same
bounded group passed: **9 passed, 21 deselected, exit 0** on Ubuntu-24.04 / Python 3.12.3 / pytest
7.4.4. The run used an exact temporary source archive with SHA-256
`B80FE142657E9322A05F9BB5EC894F01DBC54321AB2F500FF816B51C55C69591` and test source SHA-256
`E231200D024677C3FA8EE33C673DE501031BA637243C05DF7DFABB1BFEF744AF`, at committed base
`aedf712c` plus the dirty candidate. It proves the mocked Supervisor recovery contract, not real
WSL/systemd runtime. Full evidence:
`docs/sdlc/evidence/s2-4-supervisor-recovery-loader-wsl-tests-final-2026-10-30.txt` and
`docs/sdlc/evidence/s2-4-supervisor-recovery-loader-wsl-final-run-2026-10-30.json`. The separate
Windows skip and WSL mount-access attempt are retained in their own files.

- The journal proves the distro was powering off when it sent `SIGTERM`; it does not identify the
  external shutdown trigger. The gap between separate WSL client calls is consistent with idle
  shutdown, but that specific trigger remains `NOT_ESTABLISHED`.
- The previous runtime attempt is consumed (`retry_cap=0`). Its run ID and nonce must not be reused.
- No runtime preflight, E5 attestation, bootstrap, issuer, Supervisor/Runner/Owner action, or
  report-bound TestRun passed from that interrupted attempt.
- **Next:** Codex incorporates the passing focused WSL contract evidence, completes exact-source
  review and commits the S2-4 candidate. After push, obtain a fresh correlated runtime
  authorization bound to exact pushed source/config/run identity; the designated `e2e-runner` runs
  only that bounded qualification. Until runtime acceptance passes, S2-4 stays active and S2-5 stays
  unstarted.
