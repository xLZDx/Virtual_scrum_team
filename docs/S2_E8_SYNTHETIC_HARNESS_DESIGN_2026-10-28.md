# S2 E8 synthetic harness design — 2026-10-28

## Goal

Make the existing helper executable for a narrow, safe synthetic candidate and budget flow, while
restricted process/crash, STOP/resume, out-of-scope mutation, and external-egress scenarios remain
`NOT_RUN`. No result represents real sandbox or E8 acceptance. The active source is
`tools/vst/slice.py` (`HandWrittenWorker` and
`run_lifecycle_scenarios`); `tests/vst/test_s2_sandbox_probe.py` currently has six unconditional
E8 skips because real sandbox evidence is absent.

## Non-goals

- Close VST-020/E8 or replace the real sandbox skip placeholders.
- Create an E5 signature, real worker identity, external candidate, production coordinator,
  service configuration or egress boundary.
- Make an operator candidate choice or claim production isolation from a synthetic fixture.

## Options and decision

1. Leave the existing helper uncalled and E8 wholly untested. This avoids code risk but leaves
   locally reproducible lifecycle behavior without evidence.
2. Add a narrow safe synthetic candidate/report contract to the existing helper and test it with
   temporary repositories and the existing test-owned worker. This yields local evidence while
   retaining process/crash, STOP/resume, mutation, real E5/E6/S1, external egress, candidate
   comparison and operator choice as separate gates.

Choose option 2. It reuses the existing helper and avoids a second execution authority. The report
must label its environment as synthetic and must never return an E8 acceptance PASS. Real E8
acceptance remains blocked on the provisioned sandbox, valid current-run E5, actual worker path,
egress evidence and operator decision required by the S2 plan.

## Design

- Extend only `run_lifecycle_scenarios` and its existing synthetic worker helpers.
- Return a local synthetic candidate head, gate/receipt outcomes and budget rejection. Mark child
  process exit, process kill, STOP, crash/restart/resume, out-of-scope write attempt and external
  egress as `NOT_RUN`; do not invoke those scenarios.
- Record the probe properties that the supplied signed probe actually asserts, but label the
  provider as caller-supplied; synthetic probe fixtures are not host-boundary evidence.
- Mark candidate comparison, real blocked-egress attempt and operator choice as unavailable in
  the synthetic report. Do not infer these from “no remote configured” or a synthetic attestation.
- Require a fresh, non-existing work directory under the caller-provided temporary parent. Keep all
  repositories, databases and files beneath that new directory so an existing path cannot be
  reinitialized or overwritten.

## Failure modes and boundaries

- A report consumer could mistake local results for real E8; prevent this with a stable
  `environment_scope: synthetic` marker and explicit unavailable fields.
- A fabricated probe callback could be mistaken for E5; label it caller-supplied and make no
  environment assertion from it.
- Do not invoke the child's `os._exit(97)` path, a process restart/recovery path, an out-of-scope
  write attempt, STOP injection or resume during this focused run. Keep their outcomes `NOT_RUN`.
- No real network probe, external candidate, persistent service, key or credential is used.

## Verification plan

`functional-test-reviewer` derives focused acceptance tests for the safe synthetic report.
`e2e-runner` executes them against disposable local repositories and verifies
cleanup. Relevant code reviewers inspect the final implementation diff. Keep the real E8
placeholder selectors `NOT_RUN` until a genuine operator-provisioned sandbox and signed current-run
E5 evidence exist. No production/system check or external candidate run is part of this design.

## Rollout, rollback and ownership

The helper is test-facing and is not activated by production. Revert the focused code/test commit
if it introduces a compatibility or fixture-safety regression; do not modify real service state.
Codex owns implementation and evidence coordination; functional-test-reviewer and e2e-runner own
test authoring/execution; GPT-PM owns final gate; operator owns the real sandbox, signed E5 and
candidate choice.

## Remaining unknowns

The actual E8 run still depends on the real operator-provisioned sandbox and current-run E5. The
external candidate and S3 worker choice remain operator decisions under the accepted plan.
