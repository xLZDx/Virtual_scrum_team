# 0097 S3 STOP cleanup diagnostic functional coverage

## What changed

- Added Store-backed functional regression coverage for successful and failed adapter cleanup during STOP.
- Covered the durable epoch fence and non-approving response on both paths, suppression of raw exception text, and fallback for overlong/non-identifier exception class names.
- Reused the existing synthetic pilot fixture; no new dependency or external runtime was added.

## Why

Change 0096 fixed a reliability-review MINOR by distinguishing adapter cleanup outcome while preserving the safety boundary. The regression proves outward response and durable Store state, not just that an implementation helper formats a value.

## Affected contracts and paths

- `tests/vst/test_s3_worker_pilot_e2e.py`: S3 AC-4 STOP cleanup diagnostics and fence regressions.
- `core/DECISION_LOG.md` and `core/LESSONS_LOG.md`: coverage decision and verification rule.
- `governance/DOCUMENT_REGISTRY.md`: generated index.

## Decisions and ownership

- Accountable task owner: operator under the delegated S2-S5 continuation; test author/executor: functional-test-reviewer; coordinator: Codex.
- The existing synthetic Store/Supervisor integration is the cheapest layer that proves durable fencing plus response serialization. Actual process cleanup remains outside this test and remains `NOT_VERIFIED`.

## Verification state

- Test source is committed in `2a8c17583e4e7594464b85aace6addb827a5eb6c`. Focused execution passed at that same exact HEAD: 16 passed, 0 skipped, 0 failed; exit code 0; one pytest-asyncio deprecation warning. See `docs/sdlc/evidence/s3-stop-cleanup-functional-2a8c175.md` and evidence record 0098.
- Required outcomes: adapter return remains `INCONCLUSIVE` and `NOT_VERIFIED`; adapter exception remains `INCONCLUSIVE`, fences the stale attempt, identifies only a validated bounded class name, and does not disclose exception text; invalid/overlong class names map to a safe fallback.
- Process note: the test author accidentally ran `git diff --cached --check` while inspecting staged changes. It printed no diagnostics, but the exit code was not captured; this is not verification evidence and is recorded as a workflow failure in `core/LESSONS_LOG.md`.
- No process-kill, sandbox, candidate, build, CI, or migration evidence is claimed.
