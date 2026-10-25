# S4 exact-head GPT-PM acceptance finding — evidence summary

## What changed

- Preserved the complete correlated final GPT-PM response for S4 exact HEAD `45095867163fc3e25184b49c328eb3c5b49dbea6` in `docs/sdlc/evidence/s4-gptpm-final-review-4509586.json`.
- Updated the S4 backlog, decision and lesson logs, and bilingual report to record the `MAJOR — MODIFY` disposition and the exact report-bound acceptance boundary.
- Recorded a fresh `e2e-runner` scope audit: the current local synthetic fixture already covers signed receipt/artifact/gate paths but excludes `tools.qa.run`, deployed signer and sandbox. The agent made no changes and ran no tests.

## Why

The exact-head GPT-PM sweep found no demonstrated source defect (`0` confirmed source-level BLOCKER and `0` confirmed source-level MAJOR) but returned `MAJOR — MODIFY` because the required report-bound runtime journey and aggregate regression are not executed. This must remain a full-acceptance blocker and must not be downgraded to approval based on local synthetic tests.

## Correlated review

- Request: `eb320905-19ac-4353-a028-7d2613721987`
- Reply: `3310760a-833d-4e37-85ed-18858bb90c68`
- Input hash: `def75f9a0fed5cba23307a5acf6209ff467b4507ad7bd473e18e8b8ca251a0aa`
- Reviewed branch: `s4-native-qa-runner`
- Exact reviewed HEAD: `45095867163fc3e25184b49c328eb3c5b49dbea6`
- Verdict: `MAJOR — MODIFY` for complete S4 AC-1–AC-15 acceptance. The single unclosed requirement is report-bound v2 signed execution and aggregate regression.

## Required boundary and ownership

The missing run must exercise `tools.qa.run`, v2 report serialization, a trusted deployed signer, a run-specific manifest, report/receipt/artifact resolution, authoritative gate consumption, and the aggregate report-bound regression. Current evidence does not establish these paths together. The recorded WSL runner UID is `997`, the worker UID is `999`, and the signer UID is `995`; the runner lacks sudo and file capabilities to make the required UID/GID transition. A disposable signer socket does not solve that dependency. The E2E category remains PARTIAL and cannot be signed; a COMPLETE functional category can be selected for a narrower report-serialization run once the transition is approved.

Canonical project records do not identify the technical owner of the WSL identity-transition or QA runner/gate service. Owner gap: technical service owner UNKNOWN. The operator is accountable for delegated S4; Codex is executor; functional-test-reviewer and e2e-runner own later test authoring/execution. Next: establish a project-approved least-privilege transition and trusted signer/manifest, then run report-bound E2E and aggregate scenarios; request a fresh exact-head GPT-PM review only after those results.

## Verification state

- Prior exact-source/test evidence remains scoped as described in change 0198; focused POSIX symlink selectors passed 3/3 at `1c97ee968e6c9f8ab133a3b6d7452e17a17ee600` in change 0201.
- Fresh `e2e-runner` inspection of the current selector contract made no file changes and ran no test/check.
- No product tests/checks were run for this documentation update. The response is a record of the correlated GPT-PM message, not independent runtime evidence.
