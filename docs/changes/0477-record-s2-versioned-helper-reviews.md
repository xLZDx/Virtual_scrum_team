# Change 0477: Record exact-source S2 versioned-helper reviews

## What changed

- Recorded six fresh read-only specialist reviews of change 0475 at exact source/test commit
  `d5001797cb94113efd9a8dc26e4a15f2dc130976`.
- Reconciled the earlier test-evidence note so the first three failed diagnostic attempts are
  clearly historical and attempt 5 is the final exact-head result.
- Updated S2 state and backlog with review results and the remaining acceptance boundaries.

## Why

The committed implementation and exact-head evidence required a fresh review pass before the
GPT-PM sprint gate. Reviewers confirmed the code-level identity and no-replace properties without
promoting artifact installation to service/runtime acceptance. This record preserves reviewer
scope, model/effort, findings and the remaining blockers.

## Review matrix

All reviewers inspected the code diff from `9a5c41de5ce2878558402665eafaa0a80c09d177` through
`d5001797cb94113efd9a8dc26e4a15f2dc130976`. Their review checkout had evidence-only HEAD
`59e26ab6897d5cbfb7a12f1d24c67fcb7b50293d`. Agents used GPT-6 Luna at medium reasoning effort.
Reviews were read-only; they did not run tests/checks or modify files.

The final GPT-PM request will attach the exact scoped patch generated from that source range; the
committed source commits remain the canonical reconstruction source.

| Role | Scope | Result |
|---|---|---|
| architect | Helper/config ownership boundaries, installer contract, service launch and deployment claims | No confirmed BLOCKER/MAJOR. `S2-DISPATCH-M01` remains independently MAJOR/OPEN; no new coordinator authority was recommended. |
| security-reviewer | Privileged path identity, root-config binding, digest/mode/link checks, pre-spawn verification, no-replace publication | No confirmed BLOCKER/MAJOR/MINOR in changed source. Runtime, credentials, E5, effective egress, Windows containment and prohibited cases remain unproven. |
| reliability-reviewer | Installer atomicity/idempotency, partial failure and service pre-spawn lifecycle | No confirmed BLOCKER/MAJOR. Non-blocking operational limitation: a later revision-switch/rollback procedure should be documented before another rollout; current no-replace behavior refuses a different `/opt/vst-runtime` target. Owner: Codex. Next: document the separately authorized revision-switch procedure before any subsequent rollout; this does not block this artifact-install evidence. |
| python-reviewer | Python validation, exception propagation, lifecycle and pre-spawn checks | No actionable Python correctness finding. Verification failures propagate through the existing fail-closed path. |
| silent-failure-hunter | False-success paths, swallowed verification errors, installer collision and partial-failure handling | No actionable finding; mismatch and verification failures fail closed. |
| code-reviewer | General behavior regressions, compatibility, error paths and evidence claims | No actionable code defect. Confirmed limitations remain service activation, root configuration, effective egress, process containment and overall S2 closure. |

## Verification state

- Exact focused run at committed source/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976`:
  **179 passed, 0 failed, 6 skipped**, CPython 3.14.3, exit 0. The six platform-conditional
  skips remain unverified. Full command and file hashes are in
  `docs/sdlc/evidence/s2-versioned-worker-helper-execution-20261028-attempt5.md`.
- Exact-head WSL artifact installation succeeded; the versioned helper/runtime/three unit files
  matched recorded hashes and the legacy helper was unchanged. Units were not enabled or started.
  See `docs/sdlc/evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`.
- No root Runner config, credentials, fresh signed E5, manifest run, effective egress probe,
  service activation, or Windows/POSIX process-containment proof was produced.
- `S2-DISPATCH-M01` remains MAJOR/OPEN because no production coordinator source or trusted caller
  identity is present. No scheduler, CLI, queue, spool, or assignment authority was added.
- Process-kill, crash/recovery, mutation, E8 and policy selectors remain `NOT_RUN`.
- The final exact-head GPT-PM S2 gate is pending. S2 is not approved; no push/PR/merge and no S3
  start are authorized by these reviews.

## Next action and owner

Codex requests GPT-PM's exact-head S2 gate with the source diff, test evidence and reviewer
results. Operator owns actual root-owned Runner configuration/credentials and the current-run E5
signature. E2E-runner owns only the permitted runtime tests after their exact prerequisites exist.

## Commit attribution

Executor: Codex
