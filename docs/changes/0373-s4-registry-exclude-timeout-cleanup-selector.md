# Change 0373: Refresh S4 registry with timeout cleanup excluded

## What changed

- Regenerated `docs/qa/categories.json` after policy commit `3885d8a143d4cfa95cd3f0c0e5c840a6ed72dfda`.
- Registry SHA-256: `7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a`.
- Registry `source_head`: `3885d8a143d4cfa95cd3f0c0e5c840a6ed72dfda`.
- Inventory remains 963 selectors; 53 selectors are profile-less `NOT_RUN`; 900 selectors are assigned to Windows; Windows E2E remains 58 selectors.

## Why

The S4 regression aggregates categories that include API test selectors. A read-only preflight found `test_root_that_survives_the_kill_gives_exit_minus_four` was still assigned to Windows and WSL. Although the test monkeypatches the kill implementation to a no-op, it deliberately reaches timeout and post-timeout cleanup behavior. The S4 scope excludes timeout/process-cleanup scenarios, so the selector is now explicitly excluded. All previous 52 policy exclusions remain; the extra selector makes the report’s non-run reason accurate.

## Verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --write`; exit 0, `wrote docs/qa/categories.json`.
- The generated registry was parsed to verify the inventory counts, exact `source_head`, and SHA-256 listed above.
- `git diff --check`: exit 0.
- No test or runtime selector was run for this registry generation.

## Acceptance still pending

- Run the focused policy contract test and the full allowed Windows report-bound regression at the next exact candidate head.
- Keep all 53 policy `NOT_RUN` selectors out of execution; do not run timeout/process-kill, process-death, crash/resume, or mutation-and-restore scenarios.

## Ownership and next action

Accountable task owner: operator under the delegated sprint request. Registry generation and local Git: Codex. Test execution and report-bound runtime: designated E2E runner. Next: commit this registry record and run the focused contract test, then the authorized full Windows regression with a fresh target.
