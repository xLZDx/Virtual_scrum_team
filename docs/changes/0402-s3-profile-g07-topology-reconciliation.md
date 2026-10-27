# Change 0402: reconcile S3 target profile with accepted G07 topology

## What changed

- Recorded the target-profile design review. GPT-PM accepted the pinned technology profile as a planning basis but returned `MODIFY` with one MAJOR, `S3-PROFILE-M01`, requiring explicit precedence for the accepted G07 topology over older high-level wording.
- Updated the S3 target-profile proposal to require four distinct principals, the mandatory deny-by-default gateway for all SDK connections/RPCs/retries, no direct adapter-to-server path, per-run audience/claims, the closed RPC map, complete VST identity binding, file-backed bounded per-run state, and VST Store/Supervisor as sole acceptance authority.
- Reconciled S3 plan section 10: explicitly marked the earlier topology superseded, established precedence for the accepted G07 mapping/config proposal, and removed the same-identity SDK/candidate interpretation.
- Added an evidence record for the review and preserved the boundary that all changes are design/documentation only. GPT-PM post-fix verification returned ACCEPT with zero BLOCKER/MAJOR and closed `S3-PROFILE-M01` at design/documentation level only.
- Kept S2 Phase 8 `NOT APPROVED`, S4 `INCONCLUSIVE`, all 53 S4 selectors `NOT_RUN`, S5 gated, and acquisition/build/install/tests/runtime/PR/merge unauthorized.

## Why

GPT-PM identified that a reader could follow the high-level profile or older S3 plan section 10 and omit the mandatory G07 gateway and principal separation already accepted by GPT-PM. A single normative topology is needed before the profile can be treated as a coherent implementation target.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-target-profile-proposal-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`
- `docs/sdlc/evidence/s3-temporal-target-profile-gptpm-review-20261027.md`
- `docs/sdlc/evidence/s3-temporal-target-profile-gptpm-verification-20261027.md`
- `docs/sdlc/STATE.md`
- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `docs/changes/0402-s3-profile-g07-topology-reconciliation.md`

## Provenance and review

- Turn baseline before these edits: branch `s4-canonical-continuation`, HEAD `e78e0497b9e6d5b46684647ab7e55043696a8017`; only protected untracked `docs/sdlc/evidence/s2-functional-test-run.md` was present.
- GPT-PM request ID: `d7a90df8-02dc-4fe4-8745-5857228e94b0`; PM Bridge job `cf418651-28bf-469d-89f1-94a24a3d3423`; project `virtual_scrum_team`; user turn ID `9c0f127a-4ac1-4ed3-a21b-972dbf5abb0e`.
- `gpt_await_reply` returned a message whose first line repeated the exact request ID and whose text is summarized in `s3-temporal-target-profile-gptpm-review-20261027.md`; `pm_bridge_status` logged the inbound message under that request ID.
- The durable job status for this initial review still reports `status=uncertain`, `sendPhase=sent`, `replyId=null`, and `correlated=null`. The returned MODIFY was recorded as request-ID-matched but not durably correlated. A separate post-fix request and response are documented below.
- A read-only `code-reviewer` / GPT-6 Luna, low-effort review completed with no material consistency findings in the target profile, S3 plan section 10, EN/RU continuation rows, state or backlog. The reviewer ran no tests/checks. No candidate action is authorized here.

## Verification and acceptance

- GPT-PM post-fix request `b69437f8-fb54-4075-9fe1-3a08eb75e8c0` returned `ACCEPT`, zero BLOCKER/MAJOR, and closed `S3-PROFILE-M01` at design/documentation level. The response repeats the exact request ID and is present in the PM Bridge inbound log. The durable job still reports `status=uncertain`, `replyId=null`, and `correlated=null`; no formal job correlation or independent HEAD verification is claimed.
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (425 lines); follow-up `--check` exited 0: `DOCUMENT_REGISTRY.md is current`.
- `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py reports --check` exited 0: `all reports carry the mandated block`.
- The actual read-only code-reviewer pass found no material consistency issue and ran no tests/checks.
- No project tests, build, CI, migration, acquisition, installation, candidate execution, policy selector, push, PR, or merge was run/performed.

## Ordered next steps and owners

1. Codex: commit this verified documentation correction locally, with the generated registry and a dedicated change record.
2. Codex: preserve the design-only closure and continue source-only G03 provenance/compatibility work; operator decides legal/acquisition status; no candidate artifact action before separate authorization.
3. Codex/operator: keep S2/S4 boundaries intact; prohibited S2 cases and all 53 S4 selectors stay `NOT_RUN`, S4 remains `INCONCLUSIVE` absent an exact signed waiver.
4. After S2/S4 closure, operator provides/authorizes the concrete AEVE source; Codex resumes S5.
5. After acceptance, assigned test/review roles execute, GPT-PM reviews exact HEAD, and separate per-sprint PR/merge steps follow.
