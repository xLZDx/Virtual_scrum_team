# 0096 S3 STOP cleanup diagnostic

## What changed

- `SyntheticStoryPilot.stop` now distinguishes an `adapter.stop` return from an exception while preserving the non-approving `INCONCLUSIVE` response and durable epoch fence.
- The failure response includes only a validated exception class name, capped at 64 ASCII identifier characters. Raw exception messages are not exposed.
- The response continues to state that worker process cleanup is `NOT_VERIFIED` even when the adapter returns successfully; adapter completion is not OS cleanup proof.
- Updated VST-029 and the decision and lesson logs.

## Why

The S3 reliability review recorded that cleanup exceptions were swallowed, obscuring whether the adapter returned or raised. Better diagnostics support investigation without claiming process termination or leaking exception content.

## Affected contracts and paths

- `tools/vst/pilot.py`: S3 `SyntheticStoryPilot.stop` response diagnostics and a bounded exception-type formatter.
- `core/BACKLOG.md`: VST-029 status.
- `core/DECISION_LOG.md`: retain fencing and `NOT_VERIFIED`, expose only bounded type.
- `core/LESSONS_LOG.md`: preserve safe cleanup diagnostics.
- `governance/DOCUMENT_REGISTRY.md`: generated index.

## Decisions and ownership

- Accountable task owner: operator under the delegated S2-S5 continuation; executor: Codex.
- No technical service owner for this in-repository synthetic pilot is named in the inspected project records.
- The change does not authenticate STOP callers or prove OS process cleanup; those existing boundaries remain unchanged.

## Verification state

- Code and documentation were inspected and updated; no tests, checks, builds, CI, migrations, or runtime probes were run during implementation.
- Functional cleanup response/fence regression passed at exact test HEAD `2a8c17583e4e7594464b85aace6addb827a5eb6c` (16 passed, 0 skipped, 0 failed); see `docs/sdlc/evidence/s3-stop-cleanup-functional-2a8c175.md`. Exact-head specialist re-review remains pending.
- Process cleanup after timeout, sandbox runtime, candidate execution, and prohibited process-kill/kill-table scenarios remain `NOT_RUN` or `NOT_VERIFIED`.
