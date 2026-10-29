# Change 0546: record focused S2 runtime and candidate contract tests

## Baseline and scope

Source baseline for this continuation: `9c1be0f`; tested source fixes end at `7e9c519`.
The primary agent coordinated but did not author or execute tests. Actual
`functional-test-reviewer` and `e2e-runner` agents (gpt-6-luna, medium) authored the five new
focused test files after source completion, then reran direct regressions after implementer fixes.
No protected pre-existing untracked evidence was included.

## Tests and results

- Functional role: `test_s2_runtime_bundle.py`, `test_s2_source_staging_plan.py`,
  `test_s2_machine_source_contracts.py`; Windows 30 passed, 6 POSIX crypto skips; Ubuntu 24.04
  WSL 36 passed, exit 0, including real OpenSSL Ed25519 verification with disposable synthetic keys.
- E2E role: `test_s2_bootstrap_runtime.py`, `test_s2_stage_only_install.py`; Ubuntu WSL 13 passed,
  exit 0; Windows stage-only subset 7 passed. Selector apply/recover used disposable filesystem
  fixtures and mocked systemd boundaries, not the actual deployed selector or services.
- Tests exposed the duplicate embedded stage guard and conflated policy/assignment revocation
  IDs. Implementer fixes are in 0544 and 0545. Fixture-only construction/assertion errors were
  corrected by test owners without weakening production contracts.

Exact commands, environment, hashes and limitations are in
`docs/sdlc/evidence/s2-bootstrap-functional-run-20261029.md` and
`docs/sdlc/evidence/s2-bootstrap-e2e-run-20261029.md`. Do not treat the counts as full-suite,
current production, systemd identity, E5, real Store deployment or owner-to-Runner acceptance.
Restricted process-kill/crash/mutation/E8/policy selectors remain NOT_RUN.

## Phase and remaining work

Record the framework phase-6 source checkpoint and generated phase-7 state. Independent runtime
code/security review is now running; no final approval is implied. A separately correlated
architecture response permits replacing mandatory per-task human signatures with authenticated
Store assignment provenance, authorizing a bounded read-only basis API after exact contract
preparation; it does not authorize a mutation producer, private signer or production activation.
The exact response is preserved in
`docs/sdlc/evidence/s2-store-assignment-provenance-adjudication-20261029.md`.

Owner: Codex coordinates source corrections and evidence; GPT-PM owns architecture and final
exact-head adjudication. S2 remains open, later sprint implementation deferred, no push/PR/merge.
