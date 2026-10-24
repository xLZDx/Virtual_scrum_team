# 0100 S4 validate fixture metadata before use

## What changed

- Moved seeded fixture test-ID comparison to immediately after report metadata validation, before initial candidate state capture or command launch.
- The direct report-bound runner now enforces the same 16 KiB canonical input limit as the CLI loader.
- Updated the S4 plan/design, backlog, decision log, lessons log, and generated document registry.

## Why

The fixture-to-manifest comparison previously indexed `report_metadata` before `_validate_qa_report_request` had checked nested types. Malformed direct calls could therefore leak `KeyError` or `TypeError` rather than failing through the typed contract path. The signing boundary must also enforce the fixture input bound itself, rather than relying on the higher-level CLI.

## Affected contracts and paths

- `tools/vst/runner.py`: validated ordering and canonical-input bound.
- `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md`, `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`, backlog, decision/lessons records, generated registry.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- Metadata is structurally validated before fixture rows are indexed.
- Fixture test IDs continue to require exact set equality with the manifest slot before any command can run.
- The report-bound input maximum remains 16 KiB, matching the CLI loader.

## Verification state

- Manual source/diff inspection only. No tests, checks, builds, CI, installs, migrations, or runtime execution were performed.
- Malformed direct metadata and oversized fixture input cases remain `NOT_RUN` pending designated test-agent coverage after source freeze.

## Follow-up

1. Preserve this direct-call validation ordering in future runner changes.
2. Have functional test owners cover malformed metadata, input bounds, and exact manifest fixture-ID equality after all S4 source coding is complete.
