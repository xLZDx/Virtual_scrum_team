# Change 0513 — Document the S2 dispatcher fail-stop recovery boundary

## Why

The post-functional reliability review found a non-blocking operational gap: the dispatcher stops on
any unhandled Supervisor/Store/grant/runner error and the systemd unit uses `Restart=no`. This is
conservative for an ambiguous runner outcome, but even a transient error before launch then needs a
manual recovery action.

## What changed

- `tools/vst/systemd/README.md` now documents the journal and durable-claim inspection required
  before a separately authorized manual restart. It explicitly says that PENDING,
  EXECUTION_RESERVED, and INDETERMINATE do not authorize relaunch, and that the note is not tested
  WSL runbook evidence.
- `core/BACKLOG.md` records a MINOR follow-up for observed alerting and a production recovery
  runbook. Ambiguous launch auto-retry remains disabled.
- `core/STATE.md` records exact-head architect/security/reliability review results and the known
  limitations.

## Evidence

- Reliability-reviewer, GPT-6 Luna, medium effort, read-only review of HEAD
  `197140be4b7dad9018426026a71eebedc62ec2dc`: no BLOCKER/MAJOR; one MINOR concerning fail-stop on
  any uncaught error with `Restart=no` (`tools/vst/dispatcher_service.py` and
  `tools/vst/systemd/vst-dispatcher.service`). No tests/runtime checks were run by the reviewer.
- Security-reviewer and architect, GPT-6 Luna, medium effort, read-only review of the same exact
  head: no actionable BLOCKER/MAJOR/MINOR in their scopes.
- The mapped functional suite remains 20 passed at source HEAD
  `61bfe643e52362fbe4c680ade2c3cb150997dedc`; this documentation change does not alter production
  source or tests. The actual POSIX service/runtime E2E remains `NOT_RUN` due missing provisioned
  config/credentials/E5 and no authorized activation.
- No tests, checks, builds, migrations, WSL changes, service operations, real dispatch, push/PR,
  merge, or deployment were performed for this documentation-only change.

## Remaining acceptance

`S2-DISPATCH-M01` stays MAJOR/OPEN. The production owner caller, root configuration/credentials,
current signed E5, installed runtime, and real dispatch acceptance remain absent or unproven. The
schema-v6 migration remains unapplied pending separate review/authorization. Do not start S3 until
S2 closes.
