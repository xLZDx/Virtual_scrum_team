# Change 0342 — Record unavailable S4 wheelhouse

## Summary

- Recorded the operator's answer that no existing trusted offline wheelhouse path is available for S4 report-bound execution.
- Kept AC-17 and the fresh exact-candidate seeded-failure report blocked.
- Clarified that the response does not authorize downloading or provisioning a new wheelhouse.
- Updated VST-036/VST-040, the S4 and S5 plans, and the decision/lesson logs.

## Why

The report-bound QA runner requires a distinct existing wheelhouse with locked wheel contents. The checked project-referenced path is an installed dependency target, not a wheelhouse. The operator answered “нет” to whether an existing wheelhouse could be provided. Durable records must not leave “find a path” as an open search after that response, and must not treat it as permission to create or download dependencies.

## Evidence and decision

- Operator response was received for the exact-path request in the current conversation: no existing path is available.
- Prior bounded evidence: `docs/changes/0328-pm-bridge-and-wheelhouse-evidence.md` records no wheel archives under the named installed-target path and confirms no other locations were scanned.
- Current report-bound runner requires `--dependency-wheelhouse`; a missing/non-directory or candidate/target-overlapping path is rejected before test execution.
- Historical seeded-failure results remain 3/3 on Windows and 3/3 on WSL at candidate `05b18450176109aafc108020bc2fafb7136a43d6`; they are not current-candidate evidence for later `ece6065`.
- No tests, checks, builds, CI, migrations, downloads, or runtime actions were performed for this record.

## Decision and next action

Keep S4 AC-17 and current-candidate report-bound seeded-failure execution `BLOCKED`. Do not download or provision wheels based on this response. Operator owns any future authorization and exact source/path; Codex coordinates once authorized; `functional-test-reviewer` or `e2e-runner` owns execution after the prerequisite exists. S5 remains blocked on current S4 evidence and S2 gate acceptance.

## Attribution

Change: 0342  
Executor: Codex
