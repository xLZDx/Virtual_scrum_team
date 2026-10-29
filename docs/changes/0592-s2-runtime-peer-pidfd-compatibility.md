# Change 0592 — S2 runtime peer-pidfd ABI compatibility

Date: 2026-10-30
Owner: Codex
Task: S2-4 runtime-config preparation, concrete Python/kernel compatibility correction

## Acceptance delta

Current target inventory reports Ubuntu-24.04 Python 3.12.3 on kernel
6.6.114.1-microsoft-standard-WSL2 with no socket.SO_PEERPIDFD name. Existing production
constructors reject that missing name before requesting a descriptor. This is a directly observed
runtime compatibility defect in the accepted implementation, not a reason to redesign issuer
architecture. The target /usr/include/asm-generic/socket.h and Linux v6.6 UAPI both define the
option as 77:
https://raw.githubusercontent.com/torvalds/linux/v6.6/include/uapi/asm-generic/socket.h

## Source change

Added tools/vst/peer_pidfd.py and used its option resolver at the existing Supervisor, Runner,
signer and owner-transport boundaries. A positive exact native integer is preferred. If the
name is absent, numeric ABI 77 is permitted only for the actual stdlib socket module on Linux
x86-64. Explicit None or malformed constants, fake adapters without the name and unverified
platform ABIs remain unavailable. The resolver does not prove kernel capability: each caller
still performs the existing real getsockopt, descriptor, credential and liveness checks. No
PID-only success fallback or socket-module monkeypatch was introduced.

## Actual verification

functional-test-reviewer authored tests/vst/test_s2_peer_pidfd.py and ran it with the unchanged
owner transport suite in Ubuntu-24.04 WSL: 45 passed (11 helper cases + 34 transport cases),
exit 0. Evidence: docs/sdlc/evidence/s2-peer-pidfd-functional-5318743.md.

e2e-runner used a real local AF_UNIX socketpair and actual kernel getsockopt(77), observed a
valid descriptor whose fdinfo PID matched SO_PEERCRED (404), and observed no alive-poll events.
Python 3.12.3, kernel 6.6.114.1-microsoft-standard-WSL2, exit 0. Evidence with the full script:
docs/sdlc/evidence/s2-peer-pidfd-runtime-capability-5318743.md.

After the run, the test author removed only one extra EOF blank line to satisfy the Git
whitespace check; no assertion changed and no rerun was needed. Final test file SHA-256:
5ec33095ed6eb53fb4e19926ec038933a1fd211b51af588a0f4fe50b7690e36d. The evidence report retains
the actual tested byte identity.

Both ran against the worktree based on HEAD 531874302f0c559fd83872fcb5d1880f41ca1bea, not
against this eventual commit. Source/test byte identities are retained in those records.
Final read-only security-reviewer found no actionable security regression; it did not run tests.
No service activation, process kill/crash, restricted mutation/E8/policy selector or production
journey was run. The primary agent did not author or execute the tests.

## Files and follow-up

Changed: tools/vst/peer_pidfd.py; tools/vst/supervisor_service.py;
tools/vst/runner_service.py; tools/vst/signer.py; tools/vst/dispatch_owner_transport.py;
tests/vst/test_s2_peer_pidfd.py; the two linked evidence reports; docs/sdlc/backlog.md;
docs/sdlc/test-plan.md; core/DECISION_LOG.md; this change record.

The exact non-secret configuration bundle remains the current S2-4 task. After normal delivery
of this correction, refresh its concrete runtime source/helper/source-snapshot pins. Reusing the
old staged runtime would omit this actual fix, so new artifact preparation is justified by this
specific code delta, not by a documentation-only HEAD change. Existing issuer source acceptance
is preserved. Full S2 runtime acceptance and S2-5 remain pending actual execution evidence.
