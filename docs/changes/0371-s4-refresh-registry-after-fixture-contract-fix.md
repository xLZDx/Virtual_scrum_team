# Change 0371: Refresh S4 registry after fixture contract fixes

## What changed

- Regenerated `docs/qa/categories.json` after test commit `78f6944ccf77a3a2bee9750a640444c491316f37`.
- Registry SHA-256: `a9f63462630d9a22408da605087ca428ef9906c843e800c29dc53ff14ca26fa2`.
- Registry `source_head`: `78f6944ccf77a3a2bee9750a640444c491316f37`.
- Inventory: 963 selectors; 52 profile-less policy selectors; 901 selectors assigned to Windows; 58 Windows E2E selectors.
- Corrected the focused evidence record's copied command to exactly match its preserved command file. No runtime result changed.

## Why

The focused fixture changes modify four registered test modules. The registry must bind their new committed source hashes before a report-bound candidate is constructed. The evidence command correction prevents a copy/paste representation from being mistaken for the executed command.

## Verification

- Generator: `C:\Python314\python.exe -m tools.qa.build_registry --write`; exit 0, registry written.
- Registry structure/counts and SHA-256 were read from the generated JSON; values are listed above.
- `git diff --check`: exit 0.
- No test or runtime scenario was run for registry generation.

## Acceptance still pending

- The full authorized Windows report-bound regression has not yet run at the refreshed registry/source head.
- Preserve the 52 policy `NOT_RUN` selectors. The prior five S2 lifecycle failures remain unresolved until the next report-bound run.

## Ownership and next action

Accountable task owner: operator under the delegated sprint request. Registry generation and local Git: Codex. Next: designated E2E runner executes the report-bound regression at the exact candidate commit with a fresh dependency target, then records all failures and policy exclusions.
