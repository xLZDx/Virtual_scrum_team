# Change 0345 — Regenerate S4 registry and record provisioned prerequisites

## Summary

- Regenerated `docs/qa/categories.json` after code commit `05f3d13e5ba2ee06e293c7ded6318fdc68c86cc9`.
- Added the singleton `identity` report category for the AC-16 selector, assigned only to the unprivileged WSL profile.
- Reconciled the S4 plan and VST-036 through VST-040 backlog details with the current category model and prerequisite state.
- Recorded the locked wheelhouse and offline Ubuntu toolchain evidence in `docs/sdlc/evidence/s4-prerequisite-provisioning-20261026.md`, including the copied 30-package SHA-256 manifest.

## Why

The earlier registry was stale relative to the committed runner tests and assigned the AC-16 identity selector to the broad `functional` category. A dedicated singleton category lets the report-bound runner select the one authorized identity scenario without executing unrelated functional selectors. The code fix also required a regenerated manifest tied to the exact source commit.

## Registry evidence

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --repo-root . --write`.
- Generated `source_head`: `05f3d13e5ba2ee06e293c7ded6318fdc68c86cc9`.
- Category inventory: functional 102; integration 123 total with 37 `NOT_RUN`; API 722 total with 14 `NOT_RUN`; E2E 59 total with 1 `NOT_RUN`; identity 1 WSL-only; seeded-failure 3; regression aggregate 954 total with 902 runnable and 52 policy `NOT_RUN`.
- Regression members remain exactly `functional`, `integration`, `api`, and `e2e`; identity is intentionally excluded from that aggregate.
- All 52 policy exclusions and their reasons remain in the generated registry.

## Provisioning boundary

The six locked wheels and the compiler toolchain satisfy prerequisites for a future report-bound run; they do not prove AC-16 or AC-17. The helper is not installed. No S4 tests were run in this registry/documentation step. The three seeded-failure selectors remain pending exact-head report-bound execution. The 52 policy selectors remain `NOT_RUN` and prohibited by the current policy.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Registry generation and documentation: Codex.
- Test authoring and execution: assigned to the test-owner roles after coding completion.
