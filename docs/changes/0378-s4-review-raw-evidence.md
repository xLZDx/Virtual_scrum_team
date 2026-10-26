# Change 0378: S4 GPT-PM disposition and raw regression evidence

## What changed

- Added the correlated GPT-PM exact-head `REJECT` response for repository HEAD `1e75d5b50985646f8f891c2b81b7281b063eb7fc`.
- Copied the named Windows report-bound regression evidence package into `docs/sdlc/evidence/qa/s4-regression-20261026-win-bdc8e3b-r1/`, including the current `bdc8e3b` JSONL row that was absent from the initial PM attachment.
- Recorded SHA-256 for each retained artifact and confirmed the current row hash matches the run's recorded `report-row-sha256.txt`.
- Updated S4 plan, state, backlog and regression evidence to state the exact PM verdict and the remaining unwaived 53 `NOT_RUN` selectors.

## Why

The exact-head GPT-PM review confirmed there is no new source BLOCKER/MAJOR, but rejected S4 acceptance because 53 mandatory selectors remain `NOT_RUN` without an applicable named operator waiver. It also identified an evidence-packaging gap: the attached historical `regression.report.jsonl` did not include the current Windows regression row. This change preserves that raw evidence and prevents the package from overstating approval.

## Affected contracts and paths

- S4 acceptance, policy-selector accounting, report-bound evidence and exact-head review records.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `docs/sdlc/evidence/s4-gptpm-final-review-1e75d5b-20261026.md`
- `docs/sdlc/evidence/s4-windows-regression-report-bound-bdc8e3be-20261026.md`
- `docs/sdlc/evidence/qa/s4-regression-20261026-win-bdc8e3b-r1/`
- `core/STATE.md`, `core/BACKLOG.md`

## Decisions and verification

- No policy selector was run or converted from `NOT_RUN`.
- No waiver was inferred from the instruction to keep prohibited selectors unrun.
- No source code changed and no tests/checks were executed in this documentation/evidence update.
- The copied report row SHA-256 matches the recorded run row hash; the full copied report SHA-256 matches the run summary.
- Exact repository HEAD before this change: `1e75d5b50985646f8f891c2b81b7281b063eb7fc`.
- A fresh exact-head GPT-PM review is required for any future code/delivery gate after this commit.

## Origin and limitations

The correlated GPT-PM response is request `77bff3fa-6203-49a0-aa98-84267ba2bcd9`. It is a rejection of overall S4 acceptance, not a source-code defect finding. AC-16 was accepted only for the defined WSL identity selector; AC-17 was accepted only for pre/post target-content checks and persistent-mutation rejection. Same-identity in-run change-and-restore remains `NOT_VERIFIED`. This change documents prior runtime evidence; it does not claim that the current agent executed those runs.
