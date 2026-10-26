# S4 exact-head GPT-PM review scope

- Project: `virtual_scrum_team`
- Review range: base `3b8d80ff5456192c2419d9515b47fb843939ee16` (previous GPT-PM reviewed head) through exact head `ece606584a7c0dd86e76ce475d6f6728c6804508`.
- Sprint/gate: S4 QA automation, with focus on AC-16 fixed WSL worker identity and AC-17 locked dependency-content provenance, including every integration in the selector registry, report runner, root harness, matrix, evidence schema and rollout design.
- This is a complete adversarial sweep of the full gate/mechanism and connected paths across the stated range, not only the latest test changes or the prior MAJOR findings. Search for reasons the implementation or acceptance contract is incomplete, unsafe, incompatible, or falsely reports a pass; do not manufacture findings.

## Prior GPT-PM disposition

The previous correlated review of S4 candidate `3b8d80ff5456192c2419d9515b47fb843939ee16` was REJECT (request `60398591-4c20-4b77-933c-d65c46b38cd0`, response `fc40dc74-e30e-55d3-b7b8-78e431c08ccd`). MAJOR-01 was the set of 52 policy-excluded selectors that remain `NOT_RUN`. MAJOR-02 was that installed dependency files were checked by package name/version but not bound to locked wheel bytes. The current source adds locked wheel hash, exact target-content, prelaunch and postrun verification, plus truthful `dependency_execution_integrity: NOT_VERIFIED` for same-identity mutation-and-restore during pytest. The 52 policy exclusions remain untouched and must not be executed or waived by this review.

## Evidence at exact head

- Functional-test-reviewer, GPT-6 Luna, medium effort: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_dependency_provenance.py` — 7 passed, 0 failed/skipped, 1 pytest-asyncio deprecation warning, exit 0; exact HEAD before/after `ece606584a7c0dd86e76ce475d6f6728c6804508`; only the pre-existing untracked S2 evidence file was present.
- E2E-runner, GPT-6 Luna, low effort: `C:\Python314\python.exe -m pytest -q tests/qa/test_s4_e2e_runner_cli.py::test_s4_e2e_cli_requires_explicit_dependency_wheelhouse tests/qa/test_s4_e2e_runner_cli.py::test_s4_worker_helper_selector_is_wsl_only` — 2 passed, 0 failed/skipped, 1 pytest-asyncio deprecation warning, exit 0; same exact HEAD before/after.
- Exact-head code review: GPT-6 Luna, medium effort, no evidence-backed BLOCKER/MAJOR/MINOR in AC-16/AC-17 source and integrations.
- Exact-head security review: GPT-6 Luna, medium effort, no reachable BLOCKER/MAJOR/MINOR in AC-16/AC-17 security surfaces.
- Report-bound AC-16 WSL runtime and full AC-17 WSL runtime remain `NOT_RUN`. The operator-authorized helper was not installed because Ubuntu lacks `/usr/bin/cc`; packages were not installed and no downloads were made. The named `D:\Temp\virtual_scrum_team_qa_f4ef8e7` path is an installed dependency target, not a trusted wheelhouse. The exact existing trusted wheelhouse path is unknown.
- The selector manifest at source head `5d1a8d599bec046da9b3afd36e697774e65ac49b` preserves 52 policy `NOT_RUN` rows and maps AC-16 only to WSL; its SHA-256 is recorded in `docs/changes/0315-s4-selector-registry-refresh.md`.

## Requested output

Return one verdict for this exact head and review range. List each evidence-backed finding with severity, exact path/line, reachable actor/action, contract impact, and required correction. Explicitly distinguish source-review conclusions from unrun WSL/runtime evidence. If the remaining runtime or policy gaps prevent approval, state that directly and identify the exact next evidence/decision needed. This review does not authorize push, PR, merge, selector-policy changes, downloads, or broader system changes.
