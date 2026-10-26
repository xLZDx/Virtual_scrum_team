# Change 0365 — Refresh selector registry for nested wheelhouse handoff

## What changed

- Regenerated `docs/qa/categories.json` after test commit `18108e85c6ff703a1cbe241af9713fafa49ac667` so its source head and source inventory bind the three updated QA test modules.
- Registry SHA-256: `202387bbab1babc467a29d44f03e184c61ff18435738f5f8624b65049a5594e3`.
- The registry contains 963 selectors: functional 106, integration 86, API 708, E2E 59, identity 1, seeded-failure 3, plus a 907-selector regression aggregate. The 52 selectors without an allowed runtime profile remain excluded from execution and `NOT_RUN`.

## Why

The preceding test commit updates E2E and functional runner contract tests to pass and verify the validated dependency wheelhouse environment. The committed registry must bind those test sources to their current source hashes before a clean candidate can be used for report-bound verification.

## Verification

- Generator command: `C:\Python314\python.exe -m tools.qa.build_registry --write`
- Result: exit 0; `wrote docs/qa/categories.json`.
- Registry `source_head`: `18108e85c6ff703a1cbe241af9713fafa49ac667`.
- Parsed selector count: 963; no-profile selector count: 52.
- `git diff --check`: exit 0.
- No runtime selector was executed by this registry refresh.

## Acceptance still pending

- Commit this registry and record separately from test commit 18108e8.
- Then run the approved nested native-collection selector and report-bound E2E on a fresh exact candidate and dependency target. Keep all 52 policy selectors `NOT_RUN`.

## Ownership and next action

- Accountable owner: Codex.
- Registry generation: Codex.
- Next: commit `docs/qa/categories.json` with this record, then continue with the authorized fresh-candidate report-bound verification.
