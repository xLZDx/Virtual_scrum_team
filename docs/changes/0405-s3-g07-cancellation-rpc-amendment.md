# Change 0405: isolate the SDK activity-cancellation RPC as a pending G07 amendment

## What changed

- Corrected the S3-G03 workflow-ID seed statement to `(run_id, attempt, epoch)`; fence and full VST identity remain separately persisted and bound by the accepted G07 identity map.
- Removed `RespondActivityTaskCanceled` from the accepted G07 RPC allowlist because the correlated G07 design acceptance did not include it, even though the pinned SDK-Core worker client has a source-mapped cancellation response path.
- Added a separately labeled, exact one-method amendment proposal. It requires a Supervisor-signed permit per task-token digest, issued only after durable STOP; gateway verification against the poll-token ledger, exact workflow/execution binding and a successfully forwarded matching `RequestCancelWorkflowExecution`; per-token replay state; no candidate-originated cancellation details; and no VST acceptance authority.
- Added the proposed local Supervisor→adapter→gateway control-plane flow to the G03 network/provider matrix. This flow is design-only, not implemented or runtime-proven.
- Updated S3 plan/state, backlog, decision and lesson records, and RU/EN continuation reports to keep the method unauthorized and G03 open pending exact GPT-PM adjudication.

## Why

The exact pinned SDK-Core source path uses `RespondActivityTaskCanceled`, while the already accepted G07 closed method map does not authorize it. Source use is not authorization. Omitting the call without documenting it would leave lifecycle compatibility incomplete; silently adding it would expand an accepted security contract. This change isolates the conflict for narrow architecture adjudication and describes explicit enforceable inputs without claiming the gateway or permit path exists.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-g07-authorization-mapping-20261027.md`
- `docs/sdlc/evidence/s3-g03-profile-compatibility-design-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`
- `docs/sdlc/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated from staged index)
- `docs/changes/0405-s3-g07-cancellation-rpc-amendment.md`

## Provenance and review

- Starting HEAD: `7f292705824964dc13887f11e7b2626892b43eff` on branch `s4-canonical-continuation`. The only pre-existing untracked file was `docs/sdlc/evidence/s2-functional-test-run.md`; it remains protected and unstaged.
- The pinned call path is SDK-Core `e163abd6dc19040064986a63c8b8cf4756ffd320`, `crates/sdk-core/src/worker/client.rs`, `cancel_activity_task` (linked with the method's source lines in the G07 map). This is source evidence, not runtime evidence.
- One read-only local `code-reviewer` pass (GPT-6 Luna, low effort) identified missing gateway inputs, multi-token permit handling, and omission of the control flow from the G03 network matrix. Codex added signed per-token STOP permits, token/cancellation correlation, exact retry and ambiguity behavior, candidate-detail exclusion, and the matrix row. The reviewer confirmed the authorization path and requested the final narrow data-scrubbing/retry wording, which is included. No tests/checks were run by the reviewer.
- PM Bridge exact-head GPT-PM adjudication is pending; the new method is not authorized unless a correlated ACCEPT approves the exact committed amendment.
- No code, tests, builds, CI, migration, package/source acquisition, install, Temporal execution/runtime probe, network probe, push, PR, or merge was performed. The existing S2 `NOT_RUN` restrictions, S4 `INCONCLUSIVE` state and 53 `NOT_RUN` selectors, and S5 prerequisites remain unchanged.
- No per-sprint worktree/fork was created; all work stayed in `D:\Repo\Virtual_scrum_team`.

## Verification and acceptance

- Regenerate `governance/DOCUMENT_REGISTRY.md` after staging the full document set, then run its `--check`.
- Run the mandated report-format conformance check for both HTML reports.
- GPT-PM must adjudicate change 0405 and direct G03/G07 regressions against the exact committed HEAD. Keep the `RespondActivityTaskCanceled` amendment pending and unauthorized until a correlated ACCEPT is reconciled.
- No project tests, builds, policy selectors, candidate operations, or network probes are in scope.

## Ordered next steps and owners

1. Codex: finish this docs-only change, refresh the staged-index registry, and run only the registry and report-format checks.
2. Codex: commit change 0405 locally with its linked record, preserving the protected pre-existing untracked S2 evidence.
3. GPT-PM: review the exact committed HEAD for the narrow G07 amendment, G03 lifecycle matrix, and direct accepted-contract regressions.
4. Codex: retain G03/G07 as open if GPT-PM modifies the proposal; otherwise record only the design decision. Do not treat it as runtime qualification or S3 acceptance.
5. Keep S2 Phase 8 `NOT APPROVED`, S4 `INCONCLUSIVE`, all prohibited S2 cases and all 53 S4 policy selectors `NOT_RUN`, and S5/downstream gates blocked by their exact prerequisites.
