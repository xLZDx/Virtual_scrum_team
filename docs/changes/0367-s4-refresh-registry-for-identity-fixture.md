# Change 0367 — Refresh registry for the synthetic identity fixture update

## What changed

- Regenerated `docs/qa/categories.json` after test commit `d1b030139e6df5ab130a71e8686d1d4e106fb282` so the committed source inventory binds the updated E2E fixture test.
- Registry SHA-256: `5d62689a72a77237173b9c58cd1329bfde78ee5999250a74d8660fb2cf96abd5`.
- The registry contains 963 selectors, including E2E 59 and identity 1. The 52 selectors without an allowed runtime profile remain excluded from execution and `NOT_RUN`.

## Why

The preceding test change updates the synthetic candidate fixture to include the committed identity selector required by the current registry contract. The registry source head and source file hash must bind that test change before another exact candidate is prepared.

## Verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --write`
- Result: exit 0; `wrote docs/qa/categories.json`.
- Registry `source_head`: `d1b030139e6df5ab130a71e8686d1d4e106fb282`.
- Parsed selector count: 963; no-profile selector count: 52.
- Category counts: functional 106, integration 86, API 708, E2E 59, identity 1, seeded-failure 3, regression aggregate 907.
- `git diff --check`: exit 0.
- No runtime selector was executed by this registry refresh.

## Acceptance still pending

- Commit this registry and record separately from test commit d1b0301.
- The focused synthetic report-bound native-collection selector passed and preserved dependency-target integrity, but this is not a full E2E category result.
- Keep the 52 policy-excluded selectors `NOT_RUN`. Any broader E2E run must exclude the registered resume, out-of-scope edit, worker-death and zombie-late-write scenarios under the active constraints.

## Ownership and next action

- Accountable owner: Codex.
- Registry generation: Codex.
- Next: commit the registry and this record separately, then continue only with exact candidate/profile runs that satisfy the active selector exclusions.
