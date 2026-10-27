# Change 0457: Serialize distinct-UID POSIX runner admission

## What changed

- Serialize distinct-UID POSIX `_run_one` calls in one runner process from before cgroup admission through process wait and cgroup cleanup.
- Preserve concurrent execution for calls that do not use the POSIX distinct-UID cgroup path.
- Add a deterministic lifecycle regression that pauses the first call during unconfirmed cgroup cleanup, proves a concurrent second call cannot reach cgroup creation or `Popen`, and proves the second call is refused after the cleanup latch is set.
- Update the POSIX design, sandbox specification, schema notes, state, decision, lesson, and backlog to record the serialized admission rule and its evidence boundary.

## Why

Architecture and security reviews of the process-local cleanup latch identified a conditional race: concurrent launches could both pass the latch check before either call recorded an unconfirmed cleanup. Serializing this narrow launch class makes admission and cleanup atomic relative to other distinct-UID launches in the same process. The outer service/sandbox still must be stopped or fenced before a replacement runner is admitted.

## Affected paths and contracts

- `tools/vst/runner.py`: process-local lock around the full distinct-UID POSIX `_run_one` lifecycle.
- `tests/vst/test_s2_runner_lifecycle.py`: concurrent admission/cleanup-latch regression.
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, `docs/SANDBOX_SPEC.md`, `tools/vst/schemas/README.md`: serialized admission and fail-stop semantics.
- `core/BACKLOG.md`, `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`: S2 evidence and remaining acceptance.

## Verification state

- A designated `functional-test-reviewer` ran 11 focused lifecycle selectors against the working tree based on `b00edae5cdd46920c2a1ec26bfc58796ba58f372`; 11 passed, 85 deselected. This was not an exact-commit run.
- At the base commit `b00edae5cdd46920c2a1ec26bfc58796ba58f372`, the delegated WSL cross-UID selector had passed once, but that predates this serialization change and is not evidence for this commit.
- Exact-head functional execution, delegated WSL E2E, and fresh exact-head architecture/security/reliability reviews remain pending.
- This change does not close VST-013, S2 E4, or S2 Phase 8. Prohibited process/crash/mutation scenarios remain `NOT_RUN`; Windows nested Job Object and other remaining acceptance still require their own evidence.

## Decision and ownership

- Decision: serialize only POSIX launches where both worker UID and GID are distinct-run parameters, retaining fail-closed latch behavior.
- Implementation, evidence coordination, and local Git: Codex.
- Required focused test authoring/execution: `functional-test-reviewer` and `e2e-runner` technical roles.
- Independent architecture/security/reliability adjudication: GPT-PM or the designated reviewer agents as applicable; agent role is not a project owner.
- No push, PR, merge, or external service configuration is part of this change.
