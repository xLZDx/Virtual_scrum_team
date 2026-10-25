# Change 0315 — Regenerate S4 selector registry for AC-16/AC-17 coverage

## What changed

- Regenerated `docs/qa/categories.json` after test-source commit `5d1a8d599bec046da9b3afd36e697774e65ac49b` so the manifest records committed provenance for the seven AC-17 contract tests, the AC-16 WSL worker-identity selector, and two E2E/CLI selectors.
- Preserved all 52 policy-excluded selectors as `NOT_RUN`; the AC-16 selector is assigned only to `wsl-ubuntu-24.04-cpython-3.12.3`.
- Updated current state, backlog and helper design status to distinguish authored coverage, registry generation and still-unrun WSL runtime evidence.

## Why

The S4 registry generator requires committed source provenance. Change 0314 committed the new test sources; the selector manifest now binds them to that exact source head before any report-bound run.

## Verification

- Command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` — exit 0; `docs/qa/categories.json` written.
- Manifest `source_head`: `5d1a8d599bec046da9b3afd36e697774e65ac49b`.
- Manifest SHA-256: `1105267d25cad88e31d57bd61aab8593a514adb7a0b52fad56c4dd5138f7c669`.
- Inventory: functional 98; integration 84; API 705; E2E 58; seeded-failure 3; regression 893 runnable plus 52 policy `NOT_RUN` entries (945 total rows).
- AC-16 selector is present and WSL-only. Registry generation is inventory evidence, not test/runtime evidence.
- No test, helper installation, package installation, network access or Git worktree creation was performed for this change.

## Remaining acceptance

AC-16 report-bound runtime remains `NOT_RUN` until the authorized helper is installed from an exact committed source snapshot and the WSL runner has a pre-existing trusted wheelhouse matching the committed lock. The path `D:\Temp\virtual_scrum_team_qa_f4ef8e7` is an installed target, not a wheelhouse. Do not change the 52 policy exclusions. The accountable task owner is the operator under the delegated program; the WSL/dependency-environment technical owner is not identified in canonical project records. Next, use the existing Ubuntu 24.04 WSL2 environment and authorized helper installation, then run only allowed report-bound cases once a trusted wheelhouse is located.
