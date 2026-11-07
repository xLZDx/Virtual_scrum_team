# Change 0492 — Isolate the synthetic candidate commit hash output

Date: 2026-10-28

## What changed and why

The focused run after change 0491 reached the helper's synthetic candidate commit setup but failed
before any test body. `git commit` wrote its summary to the same captured stdout stream used by the
helper to print `git rev-parse HEAD`; the combined text was then rejected as an invalid candidate
head. The child now sends the human-readable commit summary to `DEVNULL`, leaving stdout for the
machine-readable hash only.

## Affected paths and contracts

- `tools/vst/slice.py::HandWrittenWorker._run(action="commit")`.
- The focused synthetic tests in `tests/vst/test_s2_e8_synthetic_lifecycle.py` are unchanged.
- Restricted crash/process scenarios remain `NOT_RUN`; real E8 placeholders remain unchanged.

## Verification state

- Attempt 1, exact HEAD `83ffe604bcba9293407741510f14420fed580b68`, command
  `python -m pytest tests/vst/test_s2_e8_synthetic_lifecycle.py -q`: 6 setup errors, 0 test bodies
  passed. The helper-created `Supervisor` was missing the required distinct `operator_key`; fixed in
  change 0491.
- Attempt 2, exact HEAD `99368ebbb2110706f108a75bfeae224b96026d92`, same command: 6 setup errors, 0
  test bodies passed. `ContractError: candidate_head must be 40 lowercase hex characters` resulted
  from the captured `git commit` summary contaminating the hash output; fixed here.
- Both attempts were run by `e2e-runner` under CPython 3.14.3 / pytest 8.4.2 and stopped before the
  test assertions or restricted process/crash scenario ran. No real sandbox, system mutation,
  egress probe, candidate comparison, or E8 acceptance was exercised.
- Pytest retained its second attempt's disposable fixture directory under
  `D:\Temp\pytest-of-koros\pytest-3188`; it was left untouched. Operator owns any cleanup.
- This corrected revision has not yet been run. A focused `e2e-runner` retry is required.

## Ownership and next step

Codex owns the source fix, review coordination, and evidence reconciliation. `e2e-runner` owns the
focused retry; `functional-test-reviewer` owns the assertions. GPT-PM owns exact-head adjudication.
The operator owns the provisioned sandbox, genuine current-run E5, worker choice, and any deletion
of the retained temporary fixture. Keep S2 and production dispatch open until their independent
acceptance gates are satisfied.
