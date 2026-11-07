# Change 0322 — Align S2 lifecycle test double with cleanup contract

## What changed

- Updated `MockJob.terminate_and_close()` in `tests/vst/test_s2_runner_lifecycle.py` to return explicit `True` after successful cleanup, including its idempotent already-closed path.
- Preserved failure coverage for Job Object assignment, primary-thread discovery, and thread resume.
- Recorded the initial fixture-only failures, successful post-fix run, WSL mount limitation, and remaining acceptance in the evidence file and S2 state/backlog.

## Why

The implementation now treats cleanup as confirmed only when `terminate_and_close()` returns true. The lifecycle fake implicitly returned `None`, so two otherwise-successful Windows launch tests falsely represented unconfirmed cleanup. Aligning the fake with the established contract restores accurate assertions without changing production behavior or weakening failure cases.

## Evidence and verification

- Before this change, the safe lifecycle selector at source HEAD `c7ad087c9006d07eeafd348cdc3df8cbc73888d1` returned 64 passed, 2 failed, 5 skipped, and 4 deselected. Both failures expected exit 0 but got `EXIT_CAPTURE_INCOMPLETE` (-4) because the mock returned `None`.
- After the mock correction, `C:\Python314\python.exe -m pytest tests/vst/test_s2_runner_lifecycle.py -k 'not signer_rejects_malformed_signing_evidence' -q` exited 0: 66 passed, 5 skipped, 4 deselected; Python 3.14.3; one pytest-asyncio deprecation warning; 47.63 seconds.
- This run used a modified working-tree test file on product/source HEAD `c7ad087`. After commit, the designated functional-test reviewer repeated the same command at exact committed HEAD `9ce27f0d9837e2d302872df0b878ebcaba15b513`: exit 0, 66 passed, 5 skipped, 4 deselected, one pytest-asyncio deprecation warning, Python 3.14.3, 69.49 seconds. HEAD/status were unchanged; only the preserved untracked S2 evidence file remained.
- At source HEAD `c7ad087c9006d07eeafd348cdc3df8cbc73888d1`, `functional-test-reviewer` ran `C:\Python314\python.exe -m pytest tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py -q`: exit 0, 60 passed, one pytest-asyncio deprecation warning, Python 3.14.3. These are in-memory contract and diff-gate cases, not platform containment runtime evidence.
- The POSIX reviewer-boundary WSL selector is `NOT_RUN`: `/mnt/d/Repo/Virtual_scrum_team` was absent because `/mnt/d` was an empty mount placeholder. No mount or system provisioning change was attempted.
- Full evidence and commands: `docs/sdlc/evidence/s2-s3-current-source-regression-5ae495c.md`.
- No source build, primary-session test, or broad check was run in this change.

## Remaining acceptance and owners

- The test/evidence change is committed locally as `9ce27f0`. Codex owns coordinating fresh exact-head specialist reviews; GPT-PM owns the final S2 gate decision.
- Operator remains accountable for S2. Prohibited process-kill/kill-table, nested Windows Job Object runtime, full POSIX containment, and E8 crash/resume evidence remain `NOT_RUN` pending the applicable authorization/environment. The current WSL boundary selector also needs the canonical checkout mounted into the existing distro; no owner-provided mount is available in this run.
- No push, PR, or merge is authorized by this change.

Change: 0322  
Executor: Codex
