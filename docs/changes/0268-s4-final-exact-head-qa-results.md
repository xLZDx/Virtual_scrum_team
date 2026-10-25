# 0268 S4 final exact-head QA results

**Date:** 2026-10-25  
**Executor:** Codex (documentation reconciliation)  
**Branch/head under test:** `s4-reproducible-qa-automation` / `ac17bdef511f980c6f92dbd5d13fd008aaa72ef0`  
**Registry source head:** `28e7c50c11fccd2acd7e2e59ea15ddeed0078ec6`

## What changed

- Recorded the final six-category QA run at candidate head `ac17bde`, after the duplicate-event assertion correction and manifest refresh.
- Reconciled S4 state, backlog, and decision history with the latest run reports. Passing individual assertions do not override required skips or policy `NOT_RUN` rows.
- Preserved the evidence files under `docs/sdlc/evidence/qa/`; all 18 report/stdout/stderr files match the test candidate by SHA-256 and byte size.

## Why

The prior checkpoint described the exact-head rerun as pending. Six current run records now bind to `ac17bde`, but only functional and seeded-failure categories report `PASS`. The remaining categories correctly remain non-approving because Windows skipped required POSIX cases and the run policy prohibited process termination.

## Evidence and verification

- Candidate: `ac17bdef511f980c6f92dbd5d13fd008aaa72ef0`; manifest source head: `28e7c50c11fccd2acd7e2e59ea15ddeed0078ec6`.
- Runtime: Windows 11 AMD64, CPython 3.14.3, pytest 9.0.3; dependency lock SHA-256 `b4e6eea19e0e0d498d82756fe94ed343b8ed147a660a876b50b8283ba32a51e3`; dependency target was isolated outside the checkout. Reports say capture complete, not timed out, not truncated, and Job Object present.
- Exact runner invocation template used by the designated E2E role (the table gives each category and run ID): `C:\Python314\python.exe -m tools.qa.run --category <category> --repo-root D:\Temp\vst_s4_acceptance_ac17bde_20261025T --manifest docs/qa/categories.json --fixtures docs/qa/fixtures.json --dependency-target D:\Temp\virtual_scrum_team_qa_f4ef8e7 --scratch-root D:\Temp\vst_s4_scratch_ac17bde_20261025T --run-id <run-id> --expected-head ac17bdef511f980c6f92dbd5d13fd008aaa72ef0 --report-path docs/sdlc/evidence/qa/<category>.report.jsonl --stdout-path docs/sdlc/evidence/qa/<category>.stdout.txt --stderr-path docs/sdlc/evidence/qa/<category>.stderr.txt`. The report records the nested pytest command and category source modules.
- Latest report outcomes (selector counts are registered selectors; concrete cases are pytest node IDs):

| Category / run ID | Selector outcome | Concrete nodes passed / skipped | QA result |
|---|---|---:|---|
| Functional / `s4-ac17bde-functional-20261025t` | 58 passed, 0 failed/skipped/NOT_RUN | 113 / 0 | PASS |
| Integration / `s4-ac17bde-integration-20261025t` | 42 passed, 0 failed, 6 skipped, 36 NOT_RUN | 84 / 10 | FAIL |
| API / `s4-ac17bde-api-20261025t` | 688 passed, 0 failed, 5 skipped, 12 NOT_RUN | 1,492 / 10 | FAIL |
| E2E / `s4-ac17bde-e2e-20261025t` | 55 passed, 0 failed/skipped, 1 NOT_RUN | 59 / 0 | INCONCLUSIVE |
| Regression / `s4-ac17bde-regression-20261025t` | 843 passed, 0 failed, 11 skipped, 49 NOT_RUN | 1,748 / 20 | FAIL |
| Seeded failure / `s4-ac17bde-seeded-failure-20261025t` | 3 passed, 0 failed/skipped/NOT_RUN | 3 / 0 | PASS |

- Integration skips are six POSIX-only worker/store scenarios. API adds five Windows-inapplicable or sandbox-dependent selectors. Regression contains eleven skipped selectors. E2E has one timeout/process-tree selector kept `NOT_RUN`. Integration/regression each keep 35 `os._exit` process-death selectors and one process-kill selector `NOT_RUN`; API has 12 prohibited termination/timeout selectors. No process-kill, timeout, or `os._exit` selector ran.
- Reports show zero failed selectors in all six final runs. FAIL/INCONCLUSIVE statuses arise from required skips and explicit policy `NOT_RUN`, not a passing gate. Functional and seeded-failure are the only category-level PASS results.
- Candidate-to-canonical evidence comparison: 18 files checked, 0 mismatches. Hashes and byte sizes:

| File | SHA-256 | Bytes |
|---|---|---:|
| `functional.report.jsonl` | `6798E2CC3670C5670EDD64F6F00402227F99FBAEBAADE918E74EC61CBE1BDFB3` | 624173 |
| `functional.stdout.txt` | `317DC23EE6BD1FE70B626AAA50303A0A964A45E9D7D084B0BCAD64DA88F9EB17` | 1580 |
| `functional.stderr.txt` | `1932684BD5FF43A2D720E739EFF51D82C5EC576D20819B33633255A5462B3451` | 199 |
| `integration.report.jsonl` | `4858E20059CA33B8783BC5A1B19A856109FCBCAB83587F0AE7A8CB7CE7414AD3` | 515941 |
| `integration.stdout.txt` | `81BD90A06811D0E0C41CF220DC8F06B22AB8B663C66A2D300EA9C644626E6573` | 1290 |
| `integration.stderr.txt` | `A790BE6D8B616F585F3632A59DBD5D6DD00DF05596EDDAB3DC067C19B938BAAB` | 167 |
| `api.report.jsonl` | `AF3A987875E6EEC9D818498F51CD96828ED04C296B0CDF52735A3458782A06CB` | 4352005 |
| `api.stdout.txt` | `5578D5DE66800A2324CA592EFF50B2E4194B5F48E18A2ECD4C734BA6522872F9` | 8828 |
| `api.stderr.txt` | `A790BE6D8B616F585F3632A59DBD5D6DD00DF05596EDDAB3DC067C19B938BAAB` | 167 |
| `e2e.report.jsonl` | `6A7865C07FD3A753D9043E6ECD2506DCBC44D6A21C61F06D667A6E6ECACE260B` | 200064 |
| `e2e.stdout.txt` | `42A6963B37EA3A223BA32CC2B6B1131DC3242FF07B1B9C1C3CBBE9187902C5C6` | 536 |
| `e2e.stderr.txt` | `A528B1E4D996E9B60ECCBC8A0592358D1272E47B0EEDCBDEE4F448EE8777562B` | 101 |
| `regression.report.jsonl` | `2B0FD093469CE919A6C3F0FDF9289C2B882C7C1B0C9995FB1A48419543416FFF` | 2015897 |
| `regression.stdout.txt` | `3549DC8D9AA9E4A871129C64CBB58E2E16C48D1AC4122AF7F6722456010F850D` | 4183 |
| `regression.stderr.txt` | `A528B1E4D996E9B60ECCBC8A0592358D1272E47B0EEDCBDEE4F448EE8777562B` | 101 |
| `seeded-failure.report.jsonl` | `F0982FD8B2C2B379A34E51A1AC8540CBD8D5FE0F8D8FCF63C5CA199046A4231F` | 14562 |
| `seeded-failure.stdout.txt` | `E6D438A0185E1E8EC5428144E5E44738C5522F4F815C75584D133F67E3CBD199` | 200 |
| `seeded-failure.stderr.txt` | `A528B1E4D996E9B60ECCBC8A0592358D1272E47B0EEDCBDEE4F448EE8777562B` | 101 |

- Registry command: `C:\Python314\python.exe tools\build_document_registry.py` exited 0 and generated 243 lines. This documentation reconciliation did not run product tests, product checks, builds, migrations, or CI. Test evidence is read from the exact-head reports produced by the designated test roles.
- Development remains in `D:\Repo\Virtual_scrum_team`. Registered extra worktrees were observed but not entered, created, or removed in this reconciliation; their origin is not verified here. The untracked S2 evidence file was not modified.

## Acceptance and next steps

- VST-032: reports bind to candidate `ac17bde` and registry source `28e7c50`; selector inventory is current for this run.
- VST-033: exact-head runner completed all six category invocations without timeout/truncation; dependency lock and environment are recorded.
- VST-034: functional passed; API remains non-approving due five skipped selectors and 12 policy `NOT_RUN` selectors.
- VST-035: integration and regression remain non-approving due POSIX skips and prohibited process-death selectors; E2E remains inconclusive due one prohibited timeout selector.
- VST-036: seeded-failure passed 3/3 selectors.
- VST-037: all 18 evidence files are hash/size-identical between candidate and canonical copies. A no-skip VST gate receipt is unavailable because required selectors remain skipped or `NOT_RUN`.
- Accountable task owner: operator under delegated continuation. Executor: Codex. Test execution owners: functional-test-reviewer and e2e-runner. Technical owner for a POSIX/Windows cross-platform runner environment is not identified in canonical records.
- Next: obtain required POSIX and sandbox runtime evidence on the accepted platform; keep process-kill and abrupt-death cases `NOT_RUN` until the run policy permits them. Then rerun affected exact-head categories and request fresh specialist consensus and GPT-PM review. Do not push/PR while the code gate is non-approving.
