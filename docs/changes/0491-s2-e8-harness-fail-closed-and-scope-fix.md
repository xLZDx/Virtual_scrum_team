# Change 0491 — Keep restricted S2 E8 crash scenario unrun and fix harness setup

Date: 2026-10-28

## What changed and why

The first focused run of change 0490 stopped during module-fixture setup: all six cases received a
`ValueError` because the synthetic `Supervisor` omitted its required distinct operator key. No test
body ran. This change passes the existing synthetic operator key to the helper-created supervisor.

The focused helper previously invoked `HandWrittenWorker.crash_mid_edit`, which is a process/crash
scenario. The active S2 scope requires such scenarios to remain `NOT_RUN`, so the helper now reports
that scenario as `NOT_RUN` and does not invoke it during the safe focused flow. This also avoids
claiming process-kill containment. Existing STOP cleanup, fresh-epoch resume, budget rejection,
out-of-scope write rejection, and caller-supplied probe labeling remain bounded to the disposable
synthetic fixture.

## Affected contracts and paths

- `tools/vst/slice.py::run_lifecycle_scenarios` passes the distinct operator key and leaves the
  restricted child-exit scenario unexecuted.
- `tests/vst/test_s2_e8_synthetic_lifecycle.py` asserts the restricted scenario is `NOT_RUN`.
- `docs/S2_E8_SYNTHETIC_HARNESS_DESIGN_2026-10-28.md` records the no-crash-run boundary.
- The real sandbox E8 placeholders in `tests/vst/test_s2_sandbox_probe.py` remain unchanged.

## Verification state

- Failed setup attempt at `83ffe604bcba9293407741510f14420fed580b68`: command
  `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`; 6 setup errors, 0 test bodies
  passed. Environment reported by `e2e-runner`: CPython 3.14.3 and pytest 8.4.2. Failure:
  `ValueError: sandbox supervisor requires trusted run id, nonce and probe verification key`
  while constructing the helper's `Supervisor`; code defect, not an environment dependency.
- No restricted child crash, process termination, system mutation, real sandbox, egress probe, or
  candidate comparison ran.
- This corrected revision has not yet been tested; designated `e2e-runner` execution is next.

## Ownership and next step

Codex owns the code correction, evidence reconciliation, and Git change. The e2e-runner owns the
focused execution; the functional-test-reviewer owns the assertions. GPT-PM owns exact-head
adjudication. The operator owns the provisioned sandbox, current-run E5, and candidate choice
needed for real E8. If the safe focused run passes, record its exact evidence and obtain relevant
exact-diff reviews; keep S2 and production dispatch open pending their independent acceptance
gates.
