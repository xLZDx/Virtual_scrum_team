# 0272 S4 POSIX runtime matrix design

**Date:** 2026-10-25  
**Executor:** Codex  
**Current repository HEAD before this design record:** `bd4457dcdadf005ec41cf1973a14f48e3e309146`  
**Reviewed design basis:** S4 candidate `fd49fad2bac249f329f4020ca5c1d55e38aa9bd7`  
**Review:** `code-architect`, GPT-6 Luna, medium effort, read-only

## What changed

- Added `docs/sdlc/S4_POSIX_RUNTIME_MATRIX_DESIGN.md` and a platform-matrix addendum to the S4 plan and runner design.
- Clarified S4 acceptance: selector outcomes must pass on each explicitly assigned runtime profile; platform skips never count as passing coverage. The matrix must bind every run to the same candidate, registry, and lock.
- Updated current S4 state and backlog to say the matrix is designed but is not implemented or runtime-proven.

## Why

The runner currently accepts only Windows CPython 3.14.3. On exact candidate `fd49fad`, integration/API/regression retain POSIX skips and policy `NOT_RUN`; the current Windows profile cannot execute POSIX-only selectors. Leaving these results non-approving is truthful, but does not complete S4's required-selector acceptance. Duplicating a second runner would risk diverging selector accounting and report integrity. The selected design extends the current runner with strict Windows/POSIX profiles plus a matrix validator.

## Evidence and constraints

- `tools/qa/run.py` checks CPython 3.14 and the approved `C:/Python314/python.exe` path. `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md` S4.2.1 and AC-11/AC-14 require pinned execution and non-approval for skipped required IDs.
- Read-only environment commands from the canonical project session: `wsl.exe -d Ubuntu-24.04 -- python3 --version` returned `Python 3.12.3`; `wsl.exe -d Ubuntu-24.04 -- python3 -m pytest --version` returned `pytest 7.4.4`. The ambient pytest does not match `tools/qa/requirements.lock` and is not accepted for runs.
- `wsl.exe -d Ubuntu-24.04 -- cat /etc/wsl.conf` returned `automount.enabled=false`, `interop.enabled=false`. `wsl.exe -d Ubuntu-24.04 --user vst-runner id` failed with `chdir(/nonexistent) failed` / `This account is currently not available`; the account is UID 997 with `/usr/sbin/nologin` and `/nonexistent` as home.
- `wsl.exe -d Ubuntu-24.04 -- runuser -u vst-runner -- id` returned UID 997 and showed supplementary group `vst-signer`. The root-invoked command `wsl.exe -d Ubuntu-24.04 -- setpriv --reuid=997 --regid=988 --clear-groups /usr/bin/id` returned UID 997 with only the `vst-runner` primary group. `Test-Path \\\\wsl$\\Ubuntu-24.04\\root` and the corresponding `tmp` path both returned true from Windows.
- The official pytest compatibility documentation says pytest 9.0+ supports Python 3.10 and later: <https://docs.pytest.org/en/latest/backwards-compatibility.html>. The WSL run must still use the hash-locked 9.0.3 target rather than ambient pytest 7.4.4.
- `code-architect` recommended strict dual runtime profiles with an aggregator and reported no mandatory operator decision under the prior WSL authorization. No test or check was run for this design; no packages were installed and no WSL files were changed.

## Chosen design and acceptance boundary

- Runtime profiles: Windows CPython 3.14.3 and POSIX CPython 3.12.3. The runner derives the current profile and rejects unknown versions or an interpreter that does not match the approved profile. Both use the same hash lock in separate external dependency targets.
- Registry: explicit platform assignments for each selector; unqualified selectors run on both profiles. A run accounts for assigned selectors only and records other-profile selectors as not assigned, never as pass/skip. The matrix requires exactly one passing result per assigned selector/profile.
- Aggregator: validates candidate HEAD, registry and lock hashes, profile identity, expected assignments, concrete outcomes, capture completeness, and artifact range hashes. A missing/stale/corrupt run, skipped or `NOT_RUN` assigned selector, unexpected case, or policy-excluded required selector prevents matrix approval.
- WSL transport: create a Git bundle from the canonical checkout and transfer it through the observed `\\wsl$` path into a disposable `/tmp` clone. Verify full candidate HEAD before running; return evidence to the canonical checkout and compare hashes. This is test-only staging, not a development worktree.
- WSL process identity: launch via a narrow `setpriv` command to UID 997/GID 988 with supplementary groups cleared. Do not run as root or retain the signer supplementary group.
- Prohibited process-kill, timeout, `os._exit`, and kill-table cases remain policy `NOT_RUN`; this matrix design does not authorize them.

## Rollout, test plan, and remaining facts

1. Implement the runtime profile and platform-assignment contracts, plus the matrix validator; keep source changes in `D:\Repo\Virtual_scrum_team`.
2. Have `functional-test-reviewer` author focused profile/assignment/matrix tests after implementation. Do not modify these tests in the coordinator session.
3. Have `e2e-runner` verify Git-bundle transfer, exact HEAD, WSL UID 997 with signer group cleared, separately prepare the locked dependency target, and execute assigned Windows/POSIX category runs only after all S4 code and registry changes are complete.
4. Compare and preserve evidence hashes, then run fresh specialist reviews and request exact-head GPT-PM approval. No push/PR/merge before approval.

Transfer integrity and the exact WSL interpreter path still need preflight. The repository does not identify a technical QA runtime/lock owner; operator is accountable under the delegated task and Codex executes. No Git worktree was created or used. The untracked `docs/sdlc/evidence/s2-functional-test-run.md` was left untouched.
