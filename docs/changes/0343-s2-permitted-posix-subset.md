# Change 0343 — Record fresh permitted S2 POSIX evidence

## Summary

- Recorded six permitted WSL identity, reviewer-write-denial and temporary external-anchor selectors run from an exact archive of repository HEAD `022fd6b`.
- Reconciled the S2 phase state and VST-013 backlog note without changing source or test code.
- Preserved the pre-existing untracked evidence file and did not create a worktree or fork.

## Why

S2 Phase 8 remains open, but the operator requested autonomous collection of permitted Windows/POSIX and system evidence. The previous S2 record had no fresh POSIX identity/anchor rerun bound to the canonical continuation repository HEAD. The selected cases are within the allowed fixture scope and can be run without process termination or full crash/resume.

## Evidence

- Exact start/final repository HEAD: `022fd6bc5d68e94edde6d281e7e5bec4030b2908`.
- Exact environment, command, selectors, duration, status, cleanup and limitations: `docs/sdlc/evidence/s2-permitted-posix-runtime-evidence-f0bbac8-20261026.md`, section “Fresh permitted POSIX subset at repository HEAD `022fd6b`”.
- Runtime result: 6 passed, 0 failed, 0 skipped; exit code 0; 0.63 seconds.
- Scope: fixture-scoped worker key/socket denial, reviewer write denial, and temporary SQLite/external-anchor recovery. No process was terminated.
- No helper, compiler, package, source, or test file was installed or changed in this evidence run.
- The temporary archive was removed; the pre-existing `docs/sdlc/evidence/s2-functional-test-run.md` remained untouched.

## Acceptance boundary

This run does not prove full POSIX containment, Windows Job Object nesting, real process-group or descendant cleanup, system resource enforcement, full egress denial, or policy-excluded process-kill/kill-table/mutation/full crash-resume scenarios. Those remain `NOT_RUN`, `INCOMPLETE`, or `NOT_VERIFIED` under the S2 gate. It does not change the latest GPT-PM `NOT APPROVED` decision.

## Attribution

- Change: 0343
- Evidence executor: designated `e2e-runner`
- Documentation executor: Codex
- Test environment: selected Ubuntu-24.04 WSL2
