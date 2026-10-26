# Change 0348 — Regenerate S4 registry after identity contract tests

## Summary

- Regenerated `docs/qa/categories.json` after focused functional test commit `4d4341e4812ba726c0b35e83ee2fad0a3fb5a7f1`.
- Added the three newly authored functional test selectors to the inventory; the AC-16 `identity` category remains a singleton and WSL-only.
- Preserved all 52 policy exclusions and the regression member set.

## Evidence

- Generator: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write` (exit 0).
- Registry `source_head`: `4d4341e4812ba726c0b35e83ee2fad0a3fb5a7f1`.
- Registry SHA-256: `33e78cda053e0d7ad1d7d52b96b46c78188913b33b4cb4e8104d6a7374b0d935`.
- Counts: functional 105; integration 86 runnable + 37 `NOT_RUN`; API 708 runnable + 14 `NOT_RUN`; E2E 58 runnable + 1 `NOT_RUN`; identity 1 WSL-only; seeded-failure 3; regression 905 runnable + 52 policy `NOT_RUN`.
- Regression members remain `functional`, `integration`, `api`, and `e2e`; the identity selector is excluded from regression.
- The four new/changed functional assertions have not been executed yet; this change is registry evidence only.

## Acceptance boundary

Registry generation records the committed test inventory. It does not prove the new assertions, helper compilation/installation, AC-16 or AC-17 report-bound runtime, seeded-failure execution, or S4 acceptance. Keep all 52 policy scenarios `NOT_RUN`.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Registry generation and documentation: Codex.
- Test authorship: designated `functional-test-reviewer`; execution is pending that role.
