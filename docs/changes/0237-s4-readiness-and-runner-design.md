# 0237 S4 readiness reconciliation and QA runner design

**Date:** 2026-10-25  
**Executor:** Codex

## What changed

- Updated the S4 plan from prepared/not-started to implementation in progress under the operator's existing S2-S5 continuation request.
- Reconciled the S3 dependency inventory with this checkout: the adapter and its focused test paths exist, while full candidate/sandbox acceptance and the S2 exact-head gate remain open.
- Added `docs/QA_RUNNER_DESIGN.md` defining category registry, registered selector versus concrete pytest case accounting, report artifacts, bounded execution, failure states, and compatibility with the unchanged VST receipt contract.
- Registered VST-032 through VST-037 in the canonical backlog as S4 implementation/evidence items.
- Added `tools/qa/requirements.lock` for pytest 9.0.3 and exact runtime dependencies using wheel SHA-256 values from the official PyPI JSON records. The pinned interpreter reports Python 3.14.3 and a pre-existing pytest 8.4.2; the new isolated QA environment will not reuse that pytest installation.

## Why

The S4 plan had become stale after the S3 adapter and test paths were committed. A readiness review also identified that a function-level test selector may expand to several concrete parameterized cases. The QA runner must retain each concrete outcome and only project a selector to a PASS record when every case passes, so parameter expansion cannot be mistaken for missing or unexpected tests. S2/S3 external acceptance remains separate from local coding readiness.

## Affected contracts and paths

- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`
- `docs/QA_RUNNER_DESIGN.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `tools/qa/requirements.lock` pins the isolated native QA environment.
- Existing TestRun receipt validators and schemas are intentionally unchanged.

## Verification state

- Read-only plan review: completed by `code-reviewer`, GPT-6 Luna, medium effort; identified stale S3 dependency claims and selector fan-out accounting requirement.
- Environment metadata: `C:\Python314\python.exe --version` reported Python 3.14.3; metadata reported pytest 8.4.2, pluggy 1.6.0, packaging 26.2, iniconfig 2.3.0, Pygments 2.20.0, colorama 0.4.6. These were metadata queries, not test execution.
- Exact package metadata and wheel hashes: official PyPI JSON pages for each pinned release; pytest 9.0.3 advertises Python 3.14 support. Pytest 8.4.2's PyPI vulnerability record reports the UNIX temp-directory issue fixed in 9.0.3.
- No tests, checks, builds, installs, CI, or candidate/sandbox runs were performed for this change.

## Ownership and next action

- Accountable task owner: operator under delegated S2-S5 continuation.
- Executor: Codex.
- Test authors/executors after all S4 coding is committed: `functional-test-reviewer` and `e2e-runner`.
- Technical QA lock/service owner: UNKNOWN in canonical project records.
- Next: implement VST-032 through VST-037 in the canonical checkout, then begin the test phase only after all S4 code is committed.
