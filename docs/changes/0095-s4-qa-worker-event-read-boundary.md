# 0095 S4 QA worker event read boundary

## What changed

- Changed the bounded pytest event file to mode `0644`; it remains inside the per-run directory whose `0730` mode permits traversal only by its runner owner and worker group. The runner can now read the event file after the worker exits without assuming it belongs to the worker group.
- Set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` only for report-bound QA invocations in `tools.vst.runner.run_manifest_commands`. The exact plugin named by the tracked manifest remains explicitly loaded; ambient installed pytest entry points cannot silently alter collection or execution.
- Updated the S4 plan with the correction and current verification state.

## Why

The S4 runner launches tests under a distinct worker UID/GID, then reads the event record under the runner identity before it can create and sign the QA report. A worker-owned `0600` file is unreadable to that runner. Separately, automatic pytest entry-point loading would allow packages outside the lock and manifest to alter the QA run.

## Affected contracts and paths

- `tools/qa/pytest_pass_plugin.py`: bounded event creation and permissions.
- `tools/vst/runner.py`: minimal child environment for report-bound QA runs.
- `docs/S4_QA_AUTOMATION_PLAN_2026-10-24.md`: status and sequencing.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex.
- The technical service owner for the QA runner and lock remains `UNKNOWN` in canonical project records.
- The per-run parent directory stays mode `0730`; its boundary was not widened. The event file's world-read bit does not grant access to users who cannot traverse the parent directory.

## Verification state

- Source inspection only. No tests, checks, builds, CI, dependency installation, migration, or QA execution were run.
- Runtime confirmation of the distinct runner/worker permission behavior and pinned pytest plugin set remains `NOT_RUN` and belongs to the designated functional/E2E test phase in the named WSL runtime.

## Follow-up

1. Finish all S4 source work before starting tests.
2. Have `functional-test-reviewer` and `e2e-runner` expand the complete accepted-story denominator, author tests, and run exact-head evidence after coding closes.
3. Provision the in-scope WSL source snapshot and signer socket before attempting the v2 native QA runtime path; platform/service owner is `UNKNOWN`.
