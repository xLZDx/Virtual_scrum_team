# Change 0490 — Add bounded S2 E8 synthetic lifecycle reporting

Date: 2026-10-28

## What changed and why

Extended the existing local lifecycle helper to report only outcomes it can observe in its
synthetic repository. The report distinguishes child self-exit from external process-kill
containment, labels the existing supervisor cleanup call as non-injected STOP, records fresh-epoch
resume, budget rejection, and an out-of-scope edit rejected before target creation. Probe values
supplied by the caller are recorded as such and are not promoted to sandbox or egress evidence.

Added focused functional assertions for these report boundaries. The existing real-sandbox E8
placeholders and skips were not changed. This does not establish E8 acceptance.

## Affected paths and contracts

- `tools/vst/slice.py::HandWrittenWorker.crash_mid_edit` and
  `tools/vst/slice.py::run_lifecycle_scenarios`.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` (new focused synthetic contract tests).
- `docs/S2_E8_SYNTHETIC_HARNESS_DESIGN_2026-10-28.md` (accepted scope and limitations).
- `tests/vst/test_s2_sandbox_probe.py` real-sandbox placeholder selectors remain unchanged and
  `NOT_RUN`.

## Decisions and boundaries

- Use only a disposable local repository and bare Git remote under the caller-provided temporary
  root.
- Keep real E5/E6/S1 qualification, blocked-egress attempt, external-candidate comparison, and
  operator worker choice as `NOT_RUN` or `NOT_ESTABLISHED`.
- Preserve the public helper signature. Do not change production dispatch or add a new authority.

## Verification state at this commit

- Source and focused tests are implemented; tests have not yet been executed.
- `functional-test-reviewer` authored the six focused assertions; `e2e-runner` execution and
  specialist review are pending.
- No real sandbox, egress, candidate-selection, or E8 acceptance evidence is claimed.
- Existing protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` is not part of this
  change.

## Ownership and next steps

Codex owns the implementation, evidence reconciliation, and local Git record. The functional test
and E2E roles own test authoring and execution. GPT-PM owns exact-head adjudication. The operator
owns the actual provisioned sandbox, current-run E5 evidence, and candidate choice required for
full E8 acceptance. After the focused tests and relevant code review, record the exact results;
leave S2 and the production dispatch gate open until their independent acceptance dependencies are
met.
