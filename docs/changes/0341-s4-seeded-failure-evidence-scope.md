# Change 0341 — Clarify S4 seeded-failure evidence scope

## Summary

- Clarified that the three synthetic seeded-failure fixtures passed 3/3 on Windows and 3/3 on WSL at historical candidate `05b1845`.
- Marked that evidence as historical for the later `ece6065` candidate because the report-bound QA runner and selector registry changed afterward.
- Distinguished AC-12 synthetic negative-input fixtures from the prohibited mutation tests and seeded product-code defects.
- Recorded the exact next prerequisite: an authorized trusted external wheelhouse for the current report-bound runner.
- Updated the S5 entry condition so historical S4 evidence is not mistaken for current-candidate evidence.

## Why

The backlog called the seeded-fixture runtime evidence complete but did not make its historical candidate boundary prominent. S4 requires exact current-candidate artifacts. The approved synthetic fixture contract is not a mutation run, so policy should not be described as prohibiting those fixtures. Current report-bound execution still cannot proceed without the trusted wheelhouse required by `tools/qa/run.py`.

## Evidence and decision

- Historical Windows/WSL seeded-failure report: `docs/sdlc/evidence/qa/s4-05b1845-platform-matrix-manifest.json`, candidate `05b18450176109aafc108020bc2fafb7136a43d6`, 3/3 per platform.
- Current later S4 candidate: `ece606584a7c0dd86e76ce475d6f6728c6804508`.
- Between those candidates, `git diff` showed changes to `tools/qa/run.py` and `docs/qa/categories.json`; the three seeded test functions, fixture catalog, and VST contract interface were unchanged in the scoped comparison.
- S4 plan AC-12/13 specifies synthetic invalid inputs through unmodified product interfaces and explicitly distinguishes them from mutation testing and product-code defect injection.
- Current `tools/qa/run.py` requires `--dependency-wheelhouse` and rejects a path that is absent or inside the candidate/installed dependency target. Change 0328 records the bounded recursive archive scan of `D:\Temp\virtual_scrum_team_qa_f4ef8e7`: it returned no wheel archives, and that path is an installed target rather than a wheelhouse. No other location was scanned and no download/install occurred.
- No tests, checks, builds, CI, migrations, or runtime scenarios ran while recording this clarification.

## Decision and next action

Keep historical 05b results as evidence for that candidate only. Do not classify synthetic seeded-failure fixtures as prohibited mutation runs. Operator is accountable; Codex owns locating an authorized wheelhouse only within the named scope or obtaining a specific path/provisioning decision; `functional-test-reviewer` or `e2e-runner` executes the current report-bound category after the dependency is available. S5 must continue to treat current-candidate S4 evidence as pending. No external path was searched, and no provisioning was performed.

## Attribution

Change: 0341  
Executor: Codex
