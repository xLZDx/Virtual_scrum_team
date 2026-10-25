# 0241 S4 test authorship and fixture catalog

**Date:** 2026-10-25  
**Executor:** Codex  
**Test authors:** `functional-test-reviewer` and `e2e-runner`, GPT-6 Luna, medium effort  
**Branch/head before this change:** `s4-reproducible-qa-automation` / `857e9a8660816105b9c3299403a20281ec004207`

## What changed

- Added focused functional contracts for the native QA runner, report envelopes, and seeded-failure observations under `tests/qa/`.
- Added a CLI/E2E contract module covering positive invocation, stale head/registry and dirty-source failures, missing dependencies, and bounded output behavior.
- Added three hash-bound synthetic seeded-failure fixtures in `docs/qa/fixtures.json` and linked each fixture to its consuming test selector.
- Updated `core/BACKLOG.md` and the S4 plan to distinguish authored test sources from uncommitted registry generation and runtime evidence.
- Kept the process-tree timeout selector policy-prohibited as explicit `NOT_RUN`; no process termination scenario is authorized by this test batch.

## Why

S4 product code was committed before the test phase. The required test roles have now authored their focused test sources. The category inventory must be regenerated only after these sources are committed so the registry can bind selectors to committed source provenance.

## Evidence and limits

- Authored files: `tests/qa/test_s4_functional_runner_contracts.py`, `tests/qa/test_s4_functional_report_contracts.py`, `tests/qa/test_s4_seeded_failure_contracts.py`, `tests/qa/test_s4_e2e_runner_cli.py`, and `docs/qa/fixtures.json`.
- Authorship was delegated to the named test roles using GPT-6 Luna at medium effort. Test sources were reviewed statically in this turn; **no tests were executed**.
- Exact category-registry regeneration and its commit are pending this commit, because the generator requires committed source provenance.
- No CI, build, process-kill, mutation run, network call, or worktree creation occurred. The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was not staged or modified.
- Isolated dependency preparation from change 0239 remains separate from test execution.

## Acceptance mapping and next steps

- VST-032: authored selector tests are present; regenerate the category manifest after this commit.
- VST-034: functional/API, report and seeded-failure test sources are authored; execution remains `NOT_RUN`.
- VST-035: CLI/E2E source is authored; category execution remains pending and sandbox-dependent selectors remain `NOT_RUN`.
- VST-036: three fixture inputs and consumer selectors are authored; runtime observations remain pending.
- VST-037: report and path-bound behavior has authored coverage; exact-head category evidence and VST gate receipt remain pending.
- Accountable task owner: operator under the delegated S2–S5 continuation. Executor: Codex. Required test authors/executors: `functional-test-reviewer` and `e2e-runner`.
- Next: commit these source/document changes, regenerate `docs/qa/categories.json` from committed test selectors, commit the generated manifest with a separate change record, then begin agent-owned functional and E2E test execution at the resulting exact head.
