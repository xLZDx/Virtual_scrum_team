# Change 0240: Drop runner capabilities before worker command execution

## What changed

- Added `tools/vst/worker_exec.py`, a POSIX-only trusted trampoline that verifies the exact worker real/effective/saved UID/GID and empty supplementary groups, sets `PR_SET_NO_NEW_PRIVS`, clears ambient/effective/permitted/inheritable capabilities, verifies the cleared capability state, then `execvpe`s the original manifest argv unchanged. Any failed invariant exits `126` before the manifest command runs.
- Updated `tools/vst/runner.py` so POSIX launches with distinct worker UID/GID invoke the isolated trampoline after CPython applies the identity transition. Windows and launches without a worker identity retain their prior path.
- Recorded the base-head capability leak, the current-head WSL snapshot, the operator authorization, and the unverified remediation state in `docs/sdlc/evidence/s4-worker-capability-drop-probe-0aa7a53.md`.
- Updated the S4 technical design, sprint plan, VST-032–037 backlog row, decision log, lessons log, and Russian/English status reports with the new threat evidence and remediation status.

## Why

The operator explicitly authorized a narrow S4 runner-to-worker helper. A test-agent probe showed that an ambient-capability systemd unit could switch the child from runner UID 997 to worker UID 999 while retaining `CAP_SETUID`/`CAP_SETGID` in every capability set. The child then successfully switched back to UID 997, which could cross the intended signer boundary. The QA CLI was stopped before creating a signer or manifest. The capability grant therefore needs to be dropped inside a trusted child trampoline before the manifest-authorized program starts.

## Decisions and ownership

- Use a trusted `python -I -S` trampoline instead of `preexec_fn`. The implementation agent inspected pinned CPython 3.12.3 `_posixsubprocess.c`: credential changes precede `preexec_fn`, but CPython warns that `preexec_fn` may deadlock in threaded applications.
- Preserve manifest argv semantics: the trampoline replaces itself with the original argv only after clearing capabilities and setting no-new-privileges.
- Accountable task owner: operator. Implementation executor: Codex via `implementation-engineer`. Test authorship/execution: `e2e-runner` or `functional-test-reviewer`. Canonical QA infrastructure owner: UNKNOWN.

## Affected contracts and paths

- S4 `tools/vst/runner.py` POSIX worker launch path and new `tools/vst/worker_exec.py`.
- S4 QA boundary: worker cannot regain runner identity or access the signer socket.
- S4 documentation and status: technical design, plan, backlog, evidence, decision and lesson logs.

## Verification state

- Base source HEAD: `0aa7a53cdf7c4ad160ee40af00dd9743646a0b08`.
- Exact-base WSL snapshot transferred by `tools/qa/wsl_snapshot.py`: run `28f9a8ea3833471e841ee113615d1db3`, 1,244,496 bytes, SHA-256 `aafffd2cb1ecbdf17968043dcbaf70f59b4d48c93dd3262ba380c99394b812f5`; the WSL Git HEAD matched and `git status --short` under `vst-runner` was empty.
- `e2e-runner` (GPT-6 Luna, medium effort) ran a focused capability probe in transient unit invocation `cef3d18bae714213a1878c88e022297a` at the base HEAD. It observed all five capability sets at `0xc0` and confirmed `os.setuid(997)` succeeded from UID 999. This is a confirmed failure of the original ambient-capability mechanism, not a test of the remediation.
- `implementation-engineer` (GPT-6 Luna, medium effort) added the source fix. No tests, build, or QA CLI run were performed against the fix. The agent accidentally ran `git diff --check` on a preliminary draft before the final helper correction; it exited 0 and is not evidence for the final diff.
- The bilingual S4 report and document registry are awaiting the required report-conformance/document-registry reconciliation after this commit is prepared.
- Remaining: fresh exact-head snapshot, test-agent runtime proof that capabilities are cleared and UID regain/signer access fail, trusted S4 signer, run-specific manifest, registered report-bound E2E selector, signed report/receipt consumption, aggregate regression, specialist review and exact-head GPT-PM approval.
