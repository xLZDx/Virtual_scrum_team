# Change 0482: Record S2 Windows containment selector audit

## What changed

- Recorded the designated `e2e-runner` read-only review of the remaining Windows containment
  selectors at current source/test commit `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- Preserved `VST-013` as `PARTIAL / NOT_VERIFIED`; no tests ran and no files were changed by the
  test agent.
- Kept process and descendant termination scenarios `NOT_RUN` under the existing restriction.

## Why

The Windows containment criterion is still open, so the remaining selector family was checked for
a scenario that could produce genuine containment evidence without crossing the process-kill or
descendant-termination boundary. The only superficially safe selector uses mocked APIs and proves
launch ordering, not real Job Object containment. The real descendant selector depends on
termination and is prohibited. Recording this prevents a mocked result from being overstated as
platform acceptance.

## Affected paths

- `docs/sdlc/evidence/s2-windows-safe-selector-audit-20261028.md`
- `docs/sdlc/STATE.md`
- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- `tests/vst/test_s2_runner_lifecycle.py::test_strict_windows_launch_suspends_assigns_job_then_resumes_before_command`
  uses mocked Windows APIs and a synthetic command callback; it does not prove real containment.
- `tests/vst/test_e4_runner.py::test_stray_descendant_is_killed_after_the_root_command_exited_normally`
  relies on descendant termination and remains prohibited.
- No tests or checks were run for this audit. The agent made no file changes.
- `VST-013` remains `PARTIAL / NOT_VERIFIED`; the exact GPT-PM gate remains `NOT APPROVED` and
  S2 remains blocked.

## Remaining acceptance and next action

Real Windows containment evidence requires an explicitly permitted scenario that does not depend
on process or descendant termination. No such selector was identified in this pass. Owner: Codex
coordinates the acceptance boundary; GPT-PM adjudicates any proposed alternative; the operator owns
any scope exception that changes the existing process-termination restriction. Until then keep
containment `NOT_VERIFIED` and the prohibited selectors `NOT_RUN`.

## Commit attribution

Executor: Codex
