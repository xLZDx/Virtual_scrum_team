# S4 specialist review evidence for source range `dd50fa5..3885d8a`

## Scope and exact identities

- Repository: `D:\Repo\Virtual_scrum_team`.
- Code/test-policy range reviewed: `dd50fa5..3885d8a`.
- S4 registry source head: `3885d8a143d4cfa95cd3f0c0e5c840a6ed72dfda`.
- Report-bound runtime candidates: Windows regression `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd`; targeted Windows/WSL `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`.
- Reviewers were read-only and did not execute tests or edit files.

## Code review

The `code-reviewer` reviewed the exact source range and found no material findings. The four fixture changes retained relevant failure and approval assertions while correcting stale setup/expectations. The registry explicitly classifies `tests/vst/test_e4_runner.py::test_root_that_survives_the_kill_gives_exit_minus_four` as policy `NOT_RUN`; the generated registry contains the selector, and the audited exclusion assertion includes it. The review did not independently verify runtime evidence. Profile: GPT-6 Luna, low effort.

## Security review

The `security-reviewer` reviewed the helper/runner/dependency boundary and found no reachable BLOCKER or MAJOR under the documented authorized local-operator invocation model. Scope included `tools/qa/worker_exec.c`, `install_wsl_worker_helper.sh`, `root_harness.py`, dependency verification/preparation and relevant call sites in `run.py`, the WSL identity fixture, design acceptance notes, and report-bound helper evidence. No tests were run and no files were changed. Profile: GPT-6 Luna, medium effort.

Evidence-backed review conclusions:

- The worker helper checks the fixed `vst-runner` identity, restricts invocation to the expected isolated interpreter form, drops groups and identity to the fixed worker account, sets `NO_NEW_PRIVS`, closes inherited descriptors, clears the environment, and executes the fixed interpreter.
- The installer requires a full commit identity and clean staged candidate, validates the WSL/account assumptions, compiles the helper from the selected commit blob, binds the embedded head/source identity, and installs at a fixed destination. The chosen candidate is still a trusted input; this review did not claim safety for an untrusted selected commit.
- `root_harness.py` verifies isolated interpreter startup, installed-file ownership/mode, byte identity with the candidate, and expected candidate HEAD. The WSL report records helper hash `a9d381acab8cbfd299be2e631caeca370f98193271df85fa8583172dbc0591dc`, mode `0:988:4750`, and preservation of the previous helper with setuid disabled. These are recorded artifacts, not independently reproduced by the reviewer.
- The root harness runs selected QA input as UID 0 with a reduced capability set inside a checked network namespace. Its precondition remains trusted, operator-selected candidate code; a malicious selected candidate could execute as that UID. No untrusted remote caller path was found in the reviewed scope.
- Locked-wheel metadata/content is checked during preparation and immediately before and after execution. These snapshots do not prove continuous immutability during pytest. The Python root-helper installer was not separately examined.
- AC-17 same-identity change-and-restore during actual pytest remains `NOT_VERIFIED`/`NOT_RUN`; a same-identity writer with target access could modify and restore between snapshots. GPT-PM must decide whether that criterion is mandatory; until runtime evidence exists, do not claim it passed.

## Remaining acceptance and next actions

The full regression report remains `INCONCLUSIVE` because all 53 policy selectors remain `NOT_RUN`. The review does not waive these exclusions, establish in-run AC-17 integrity, close S2 Phase 8, or authorize delivery. Codex records the review; GPT-PM adjudicates the exact-head S4 gate and AC-17 scope; the operator owns any change to the prohibited-selector policy. Preserve those statuses and reconcile the exact-head GPT-PM verdict before any PR/merge action.

Supporting runtime records:

- `s4-windows-regression-report-bound-bdc8e3be-20261026.md`
- `s4-report-bound-targeted-621ddc01-20261026.md`
- `s4-regression-fixture-focused-diagnostic-20261026.md`
