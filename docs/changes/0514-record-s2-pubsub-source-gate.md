# Change 0514: Record S2 Pub/Sub source adjudication

## What changed

- Added the correlated GPT-PM source-review result and local file-provenance verification to
  `docs/sdlc/evidence/s2-pubsub-gpt-pm-source-review-20261028.md`.
- Updated `core/STATE.md`, `core/BACKLOG.md`, and `core/DECISION_LOG.md` to close the bounded
  Pub/Sub source-review item while keeping `S2-DISPATCH-M01` and full S2 open.

## Why

GPT-PM completed an adversarial review of the attached Store/Supervisor/AF_UNIX Pub/Sub source and
focused test scope. The decision must be recorded without overstating it as full S2 or runtime
approval. GPT-PM could not inspect the local `.git` checkout; this turn independently checked each
attached source/test file against its Git blob at HEAD and matched the test-file hash to the passing
run record.

## Contracts and paths

- Request: `b2d8f20e-4eb0-4a4c-98ec-13c1c9437279`.
- Repository HEAD checked: `673479dccc0f37de7d723ede275c46a8f4b4595c`.
- Focused acceptance evidence: 20 passed, 0 failed, 0 skipped, one pytest-asyncio deprecation
  warning; the run proves local Store/Supervisor and mocked receipt binding only.
- GPT-PM verdict: `APPROVE — ATTACHED SOURCE SCOPE`, 0 confirmed BLOCKER/MAJOR findings; full S2
  remains `NOT APPROVED`.
- `S2-DISPATCH-M01` stays `MAJOR / OPEN`. Production E2E remains `NOT_RUN`; kernel peer/cgroup
  enforcement, root-owned configuration/credentials, current signed E5/sandbox provenance, active
  services and real dispatch are not evidenced. Migration application, key/config provisioning,
  service activation, real dispatch and publish/merge/deploy remain outside this decision.
- Restricted process/crash/mutation/policy scenarios remain `NOT_RUN`; S3 remains unstarted.

## Decisions

- Record only the bounded Pub/Sub source/test scope as accepted.
- Preserve fail-closed runtime status and the existing safety boundaries.
- Do not treat the GPT-PM source verdict as runtime evidence or complete S2 approval.

## Verification

- Compared SHA-256 and Git blob IDs for all attached source/test files against the recorded HEAD;
  all matched. The focused test SHA-256 matches the recorded passing-run evidence.
- Inspected the resulting documentation diff and Git status. No test, build, service operation,
  migration, provisioning, push, PR, merge or deployment was performed for this documentation
  change.
