# 0099 S4 QA catalog boundary hardening

## What changed

- Made the report-bound VST runner independently validate the seeded-failure catalog's exact root fields, schema version type, fixture list bound, and coherent `NOT_RUN`/`SUPPORTED` state and reason fields.
- Required a seeded-failure catalog's fixture test IDs to exactly equal the manifest slot's required IDs before any command starts.
- Rejected duplicate JSON object keys in the shared QA registry/manifest loader and in the report-bound catalog loader.
- Rejected boolean values where the catalog schema version must be integer `1`.
- Disabled pytest's cache provider in the exact category argv and set `PYTHONDONTWRITEBYTECODE=1` only for report-bound QA children; both environment variable names appear in the report.
- Updated the S4 plan, technical design, backlog, decision and lessons records, then regenerated the document registry.

## Why

The `tools.qa.run` CLI performs strict catalog loading, but `tools.vst.runner.run_manifest_commands` is itself a report-signing boundary and can be called directly. It must not depend on the CLI to enforce catalog shape/state or fixture-to-manifest completeness. Duplicate JSON keys are also ambiguous because different parsers can select different values for the same signed bytes.

## Affected contracts and paths

- `tools/qa/registry.py`: duplicate-key rejection and strict integer schema-version validation.
- `tools/vst/runner.py`: direct catalog schema/state/reason validation, duplicate-key rejection, exact manifest ID comparison before command launch.
- `core/DECISION_LOG.md`, `core/LESSONS_LOG.md`, `core/BACKLOG.md`, S4 plan/design, generated document registry.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The report-bound runner independently enforces its signing preconditions even when called outside the higher-level CLI.
- Runtime cache and bytecode writes are suppressed because the runner requires worker source and Git state to remain read-only.
- Every seeded fixture must map one-to-one to the entire required-test-ID set for the seeded-failure manifest slot.
- Existing untracked `tools/qa/wsl_snapshot.py` is unrelated shared work and is preserved outside this commit.

## Verification state

- Manual source/diff inspection only. No tests, checks, builds, CI, installs, migrations, or runtime execution were performed.
- New direct-boundary rejection paths remain `NOT_RUN` pending the authorized functional/E2E test phase.

## Follow-up

1. Finish remaining S4 source coding.
2. After source freeze, have the designated test roles cover duplicate JSON keys, schema type/state mismatch, exact manifest fixture-ID equality, and malformed catalogs.
