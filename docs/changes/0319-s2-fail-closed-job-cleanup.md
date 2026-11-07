# Change 0319 — Fail closed when Windows Job Object cleanup is unconfirmed

## What changed

- Changed `tools/vst/runner.py` so `_JobObject.terminate_and_close()` checks the Win32 Boolean return values and exceptions from `TerminateJobObject` and `CloseHandle`. It keeps the handle for the final cleanup retry unless `CloseHandle` succeeds.
- Routed each Job Object cleanup path through one helper. An unconfirmed cleanup triggers the existing best-effort process-tree fallback and remains sticky as `capture_incomplete`, forcing `EXIT_CAPTURE_INCOMPLETE` even if a later close retry succeeds.
- Updated `tools/vst/schemas/README.md` to describe strict and compatibility behavior and the fail-closed exit code.

## Why

Three independent exact-head S2 reviews found that the Windows runner ignored both API results and could sign a successful receipt after process-tree cleanup failed. The Job Object contract requires terminating associated processes, and its kill-on-close behavior depends on successfully closing the final handle. Microsoft documents nonzero as success and zero as failure for both APIs: [TerminateJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-terminatejobobject) and [CloseHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle). The runner must not treat an unconfirmed cleanup as success.

## Evidence and verification

- Baseline before source edits: canonical checkout `D:\Repo\Virtual_scrum_team`, HEAD `08cb561d0c3187c2c023349ba9dd519fcf9339f3`; `tools/vst/runner.py` had no pre-existing diff. The preserved untracked `docs/sdlc/evidence/s2-functional-test-run.md` remained untouched.
- `silent-failure-hunter` (GPT-6 Luna, low effort), `reliability-reviewer` (GPT-6 Luna, medium effort), and `security-reviewer` (GPT-6 Luna, medium effort) independently reported the same reachable MAJOR in `runner.py`; `architect` (GPT-6 Luna, medium effort) separately identified that existing S2 tests do not cover later S3 changes to `tools/vst/store.py` and `tools/vst/slice.py`. These reviews were read-only and ran no tests/checks/builds.
- No tests, builds, or runtime scenarios were run for this change. Required test authorship/execution remains with the designated test agents.
- Shortcoming: the implementation agent ran `git diff --check -- tools/vst/runner.py` contrary to its instruction. It reported no output, but did not preserve an exit code; treat this as non-evidence. No tests or builds were run by that agent.

## Remaining acceptance and owners

- Functional/E2E regression coverage of Win32 false/exception returns and exact-head S2 behavior is still required. Operator is accountable for S2; Codex coordinates; `functional-test-reviewer` and `e2e-runner` own required test authorship/execution.
- Current S2 runtime evidence remains tied to source HEAD `dc95915018b80f498d5cf775363712fb915fe04e`. The later shared `store.py` and `slice.py` changes still need applicable exact-head test evidence before the S2 gate.
- Platform-dependent Job Object nesting, prohibited process-kill scenarios, full POSIX containment, and E8 crash/resume remain `NOT_RUN`; resource limits and external-writer exclusion remain `NOT_VERIFIED` as listed in `docs/sdlc/STATE.md`.

Change: 0319
Executor: Codex
