# Change 0401: record S3 G07 design acceptance and reconcile continuation status

## What changed

- Recorded GPT-PM's correlated `ACCEPT — DESIGN ONLY` for the corrected S3 G07 authorization mapping: request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e`, reply `c9313616-dae6-5e23-9d94-21297ae17ec5`, job `9b792eb2-e051-4a3a-9d38-638694b05a6b`, user turn `7fa604df-dfd2-4cbb-b3da-7b1d444760c8`.
- Closed `G07-CFG-M01` as a design finding only. The accepted architecture requires an unavoidable deny-by-default gateway on every pinned SDK connection, RPC and retry; compatible `GetSystemInfo` response shape/capability fields; and full persisted VST request/stop/resume/response identity binding.
- Reconciled the authorization mapping, exact-config proposal, state/backlog/decision/lesson records, and RU/EN continuation reports. Corrected namespace-role wording to show the separate `temporal-system:read` claim and made mandatory gateway scope explicit. No runtime, code implementation or acceptance claim was added.
- Preserved S2 Phase 8 as `NOT APPROVED`, S4 as `INCONCLUSIVE` with all 53 policy selectors `NOT_RUN` and AC-17 `NOT_VERIFIED`, S5 gated, and downstream tests/reviews/exact-head gate/PR/merge deferred.
- Preserved the protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; it was not edited or staged. No sprint worktree/fork was created.

## Why

The new correlated GPT-PM response supersedes the prior `MODIFY` state for design finding `G07-CFG-M01`. Updating durable records prevents the accepted design finding from appearing open while preserving the separate implementation, runtime, S2, G03, legal/acquisition, and candidate-comparison gates.

## Affected paths

- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `docs/sdlc/STATE.md`
- `docs/sdlc/evidence/s3-gptpm-g07-design-acceptance-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-authorization-mapping-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-exact-config-proposal-20261027.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0401-s3-g07-design-acceptance-status-reconciliation.md`

## Provenance and verification

- Turn baseline before these edits: branch `s4-canonical-continuation`, HEAD `5df846df92e8b8152cf86be1cf9b660ef4f6a3cb`.
- At baseline, the authorization mapping and exact-config proposal were already modified, the correlated acceptance evidence file was already untracked, and protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was present. These pre-existing turn changes were preserved and extended; they are not newly created by this change record.
- The correlated response is stored in `docs/sdlc/evidence/s3-gptpm-g07-design-acceptance-20261027.md`; status is `succeeded`, `sendPhase=sent`, and `correlated=true`.
- Current-turn edits correct stale G07 review status and precision text in the mapping, proposal, state, backlog, decision and lesson records, and continuation reports.
- No project test, build, CI, migration, acquisition, installation, candidate execution, policy selector, push, PR, or merge was run/performed.
- `C:\Python314\python.exe tools/build_document_registry.py --check` exited 0: `DOCUMENT_REGISTRY.md is current`.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports --check` exited 0: `all reports carry the mandated block`.
- One actual read-only local documentation review was completed by `code-reviewer` / GPT-6 Luna, low effort. It found two documentation defects: the lesson-log link omitted its `docs/sdlc/evidence/` prefix, and this record's review outcome was still pending. Both were corrected by pointing to the repository-relative evidence path and recording the review outcome/fix below. No software test result is claimed.
- Review result: after correction, reviewer follow-up confirmed no remaining actionable documentation consistency findings. The review was read-only and ran no tests/checks/builds.

## Acceptance and remaining work

- S2: permitted evidence is recorded; Phase 8 remains `NOT APPROVED`; prohibited scenarios remain `NOT_RUN`.
- S3: read-only audit continues. `G07-CFG-M01` is closed at design level only. Gateway implementation/no-bypass/runtime proof, S2 isolation, G03 provenance/compatibility, transitive legal inventory/disposition, and common-fixture comparison remain open. Operator owns legal/acquisition decisions; Codex owns source evidence and implementation coordination; GPT-PM owns architecture adjudication.
- S4: remains `INCONCLUSIVE`; all 53 policy selectors remain `NOT_RUN`; AC-17 remains `NOT_VERIFIED`. No waiver is inferred.
- S5: remains gated on S2/S4 and an identified/authorized AEVE source.
- Downstream tests/reviews, exact-head GPT-PM approval and separate per-sprint PR/merge remain deferred until prerequisite acceptance.

## Ordered next steps and owners

1. Codex: continue read-only S3 provenance/compatibility evidence without acquiring/building/installing/running the candidate.
2. Operator: decide S3 legal/acquisition sufficiency when the technical evidence is ready; keep S4 `INCONCLUSIVE` absent an exact signed waiver.
3. Codex: continue permitted S2 evidence only; keep prohibited S2 cases and all 53 S4 selectors `NOT_RUN`.
4. Operator: after S2/S4 acceptance, provide or authorize a specific AEVE source; Codex resumes S5.
5. After acceptance: Codex coordinates the authorized test/review sequence, GPT-PM reviews the exact final head, and operator retains applicable PR/merge authority.
