# Change 0511 — Fix the S2 pub/sub Supervisor config predicate syntax

## Why

The first assigned functional-test attempt could not collect the new focused suite because the
committed strict `dispatch_owner` peer-config predicate in `tools/vst/supervisor_service.py` was
missing one closing parenthesis. This prevented the module from importing and meant no test body
ran.

## What changed

- Added the missing close parenthesis to the nested owner-principal predicate so the `if` condition
  is syntactically complete. The exact predicate was re-reviewed by the read-only code-reviewer
  agent; grouping and malformed-key short-circuit behavior were confirmed.
- Added `docs/sdlc/evidence/s2-pubsub-e2e-triage-ec9aefe-20261028.md`: actual production E2E is
  `NOT_RUN` because current root configuration/credentials, authenticated owner identity, migrated
  Store/current preflight, installed runtime, active services and fresh E5 are absent. WSL/config/
  keys/migration/service activation and real dispatch were outside the authorized test scope.
- Added `docs/sdlc/evidence/s2-pubsub-functional-run-ec9aefe-20261028.md`, preserving the failed
  collection attempt and marking the revised focused suite `NOT_RUN` pending this fix's commit.
- Updated the S2 status/backlog to record the collection failure and keep the focused test retry
  open. The new test source remains owned by functional-test-reviewer and is not included in this
  source-fix commit.

## Verification

- `functional-test-reviewer` attempted `python -m pytest -q tests/vst/test_s2_store_backed_pubsub.py`
  at source HEAD `ec9aefe9444003a65af81f27eaf813b250e25c10`. Collection failed with
  `SyntaxError: '(' was never closed` in `supervisor_service.py` around line 714; **0 test cases
  executed**. This is recorded as a failed collection attempt, not a test failure or pass.
- Code-reviewer, GPT-6 Luna, medium effort, re-reviewed the exact missing-parenthesis fix and found
  no further issue in that predicate. No checks/tests were run by the reviewer.
- E2E-runner, GPT-6 Luna, medium effort, recorded production E2E as `NOT_RUN`; no tests, checks,
  builds, migrations, WSL changes, or service operations were performed by that role.
- Functional-test-reviewer owns rerunning the focused suite after this source fix is committed.

## Safety and remaining acceptance

No migration, WSL change, key/config provisioning, service enable/start, real dispatch, push/PR,
merge, or deployment occurred. `S2-DISPATCH-M01` remains MAJOR/OPEN because the production owner
caller and runtime acceptance are not established. Preserve prohibited crash/process-kill/mutation/
policy cases as `NOT_RUN`; keep S3 unstarted until S2 closes.
