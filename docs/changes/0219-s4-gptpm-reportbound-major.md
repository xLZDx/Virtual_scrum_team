# Change 0219: Record S4 report-bound acceptance finding

## What changed

- Preserved the full correlated GPT-PM final response for S4 exact HEAD `45095867163fc3e25184b49c328eb3c5b49dbea6` at `docs/sdlc/evidence/s4-gptpm-final-review-4509586.json`.
- Updated the S4 backlog, decision and lesson logs, and English/Russian status reports to distinguish local selector evidence from the unexecuted report-bound acceptance journey.
- Recorded the fresh `e2e-runner` inspection of the existing report-bound fixture. The fixture already covers synthetic signed receipt, artifact and gate behavior; its docstring excludes the `tools.qa.run` CLI, deployed signer and sandbox. The agent made no changes and ran no tests.

## Why

The final exact-head GPT-PM sweep returned `MAJOR — MODIFY` for full S4 acceptance while confirming no source-level blocker or major defect. The remaining major is missing runtime evidence for the report-bound v2 signing and aggregate regression paths. Local selector results cannot replace the deployed identity, signer, receipt and authoritative-gate boundary.

## Correlated review

- Request ID: `eb320905-19ac-4353-a028-7d2613721987`
- Reply ID: `3310760a-833d-4e37-85ed-18858bb90c68`
- Review-input hash: `def75f9a0fed5cba23307a5acf6209ff467b4507ad7bd473e18e8b8ca251a0aa`
- Branch: `s4-native-qa-runner`
- Exact reviewed HEAD: `45095867163fc3e25184b49c328eb3c5b49dbea6`
- Verdict: `MAJOR — MODIFY` for full S4 AC-1–AC-15 acceptance; one unclosed acceptance requirement; 0 confirmed source-level BLOCKER and 0 confirmed source-level MAJOR.

## Remaining acceptance and ownership

Required but unexecuted: `tools.qa.run` report serialization, a run-specific v2 manifest, a trusted deployed signer, report/receipt/artifact resolution, authoritative gate consumption and the aggregate report-bound regression. The read-only WSL feasibility audit records runner UID `997`, worker UID `999`, and signer UID `995`; the runner lacks sudo and file capabilities for the required UID/GID switch. A disposable signer socket alone is insufficient. The E2E category remains PARTIAL and cannot be signed; a COMPLETE functional category is eligible for a narrower serialization run after the identity transition is approved.

The technical WSL identity-transition and QA runner/gate service owner are UNKNOWN in canonical records. The operator is accountable for the delegated sprint; Codex is executor. The `functional-test-reviewer` and `e2e-runner` roles own subsequent test authoring/execution. Next: establish an approved least-privilege identity transition and trusted signer/manifest, run the report-bound and aggregate scenarios, then obtain a fresh exact-head GPT-PM review. This MODIFY does not authorize push, PR or merge.

## Verification state

- Existing functional, API, E2E and focused POSIX selector evidence remains recorded in changes 0198 and 0201; these runs do not establish the missing report-bound boundary.
- Fresh `e2e-runner` inspection made no file changes and ran no tests/checks.
- No product tests were run for this documentation update. `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and generated 297 lines. `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports\S4_QA_AUTOMATION_2026-10-25.ru.html reports\S4_QA_AUTOMATION_2026-10-25.html` exited 0 and refreshed both reports; `report_conform.py reports --check` exited 0 with “all reports carry the mandated block”. `git diff --check` exited 0.
