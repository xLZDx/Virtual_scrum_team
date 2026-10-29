# Change 0400: reconcile S2–S5 continuation acceptance and status

## What changed

- Recorded the current S2–S5 acceptance checkpoint at canonical repository baseline `a583514b58e0cfab95fe2e8cbf921634aaa6857f`.
- Added current S2 read-only evidence limits and the designated E2E auditor's finding that no additional safe selector remained; no test was run by that audit.
- Reconciled S3 pinned-source facts, the accepted G07 design, and the correlated exact-config `MODIFY` finding `G07-CFG-M01`. Traced the pinned audience enforcement path and the Python SDK-Core gitlink/RPC call paths; added a source-backed authorization/audience/API/identity mapping and sent it to GPT-PM for focused re-review. Runtime/config/G03/legal/acquisition remain open.
- Recorded GPT-PM's focused correlated `MODIFY` response `9cc85b3d-644d-45b4-a80c-5dabd8f1ed18` / `bcfe039f-a0af-5695-b26b-ef23631e7d8a` (zero BLOCKER, one MAJOR `G07-CFG-M01`). Reconciled exact pinned `GetSystemInfo` bootstrap behavior and cluster-read authorization, then updated the design to require a shared deny-by-default gRPC gateway and to bind every request/response identity field. The corrected design awaits a new focused GPT-PM review; no implementation or runtime claim is made.
- Reconfirmed the recorded S4 wheelhouse's six file hashes without installing or running tests. Kept all 53 policy selectors `NOT_RUN`, AC-17 in-run mutation `NOT_VERIFIED`, and S4 `INCONCLUSIVE`.
- Reconfirmed S5 and post-acceptance test/review/PR gates are deferred on their documented prerequisites.
- Created Russian and English acceptance reports with owner, evidence, remaining work and next action per criterion.
- Preserved the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`; no sprint worktree/fork, source/test edit, acquisition, installation, candidate execution, software test/check, build, CI, migration, push, PR, or merge was performed.

## Why

The operator directed continuation of criteria 1–5, with strict S2/S4 run exclusions, autonomous assignment, and all development in the canonical repository. This checkpoint distinguishes a design approval from runtime acceptance and records conditional downstream work without claiming it is complete.

## Affected paths

- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `docs/sdlc/STATE.md`
- `docs/sdlc/evidence/s4-prerequisite-provisioning-20261026.md`
- `docs/sdlc/evidence/s3-gptpm-g07-corrective-design-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-closure-design-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-exact-config-proposal-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-authorization-mapping-20261027.md`
- `docs/sdlc/evidence/s3-gptpm-g07-exact-config-review-20261027.md`
- `docs/sdlc/evidence/s3-gptpm-g07-focused-review-20261027.md`
- `docs/sdlc/evidence/s3-temporal-pinned-dev-config-screen-20261027.md`
- `docs/sdlc/evidence/s3-temporal-exact-pin-license-screen-20261027.md` (read-only top-level license-file facts; not a legal disposition or transitive inventory)
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0400-s2-s5-continuation-acceptance-reconciliation.md`

The untracked S2 evidence file `docs/sdlc/evidence/s2-functional-test-run.md` was not staged and is not part of this change.

## Evidence and verification state

- Baseline captured before edits: branch `s4-canonical-continuation`, HEAD `a583514b58e0cfab95fe2e8cbf921634aaa6857f`; protected untracked file above was present.
- S2 read-only system/firewall evidence: `docs/sdlc/evidence/s2-readonly-wsl-system-inventory-20261027.md` and `s2-readonly-firewall-inventory-20261027.md`. These are configuration snapshots and do not prove runtime isolation or egress.
- Design adjudication: PM Bridge request `3d72de89-1451-43d5-8a4f-4ca3b141d875`, reply `56a5f7a5-71ae-5080-9dc0-f8dcc3f0f7dd`, correlated job `920893d1-73a9-4945-b373-526c8859dbb1`; verdict accepted the G07 corrective design only.
- Exact config review request `a5f46781-b5f6-436c-b2d4-bf8f38bd317c`, reply `d2f7f553-f270-597b-a0ac-15400d67b948`, is correlated. GPT-PM returned `MODIFY`, one MAJOR `G07-CFG-M01` open. The parked send-and-await job status is uncertain after its deadline, but the durable result records `correlated: true`; see `s3-gptpm-g07-exact-config-review-20261027.md`.
- Initial focused mapping request `f8bcdb1b-6baa-47a1-88aa-d4550ec5d7bb` was rejected before send because its attachment changed after admission (`sendPhase: not-started`; no content was sent). Final request `9cc85b3d-644d-45b4-a80c-5dabd8f1ed18` was sent and returned correlated reply `bcfe039f-a0af-5695-b26b-ef23631e7d8a` (PM Bridge job `021dc375-a6e2-4097-8ece-d5830d52bc6f`, user turn `435076d7-48dd-43ec-887a-489a28d4cfe7`): `MODIFY`, zero BLOCKER, one MAJOR `G07-CFG-M01` remains. The review requested exact bootstrap RPC and full VST identity binding; see `s3-gptpm-g07-focused-review-20261027.md`.
- After the reply, read-only exact-pin inspection found SDK-Core calls `GetSystemInfo` on connect; its Python bridge does not expose the skip flag or lower-level gRPC override. Temporal metadata marks this RPC cluster/read-only and the default authorizer requires a system-reader claim. The updated mapping proposes `temporal-system:read` plus the namespace writer but requires a trusted shared gateway to expose only `GetSystemInfo` from cluster scope. Full WorkerRequest/StopRequest/ResumeRequest fields and WorkerResponse identity echoes now bind to the durable mapping. The updated mapping is unapproved, unimplemented, and not runtime-qualified. A new focused GPT-PM re-review is the next S3 design gate.
- Corrected mapping request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` was sent to GPT-PM with the updated mapping, exact config proposal, pinned-source screen, prior correlated focused review, and S3 plan attached. No correlated reply is yet recorded. Do not resend; keep G07-CFG-M01 open pending this response.
- Exact pinned source evidence: Temporal server `audience_mapper.go`, `interceptor.go`, `default_jwt_claim_mapper.go`, `default_token_key_provider.go`, `default_authorizer.go`, `config.go`, and `api/metadata.go` at `af08a5e5f2dd40f545f2afac7780daaa6987001e`; Python SDK pin `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` links SDK-Core commit `e163abd6dc19040064986a63c8b8cf4756ffd320`. Static call paths were inspected in the pinned SDK-Core workflow handle and worker client. No source was downloaded into the repository; no build or runtime call occurred.
- Exact-pin license screen: the Server, Python SDK and gitlinked SDK-Core repository-level license files identify MIT terms. This does not cover transitive dependencies and is not legal approval; legal/acquisition disposition remains with the operator. The pinned URLs and scope limitation are recorded in `s3-temporal-exact-pin-license-screen-20261027.md`.
- S4 wheelhouse evidence: six recorded wheel hashes match the read-only recheck in `docs/sdlc/evidence/s4-prerequisite-provisioning-20261026.md`; no dependency target was touched and no installation/test occurred.
- Report conformance command `py -3 C:/Users/koros/.claude/tools/report_conform.py ...` could not launch because the `py` shim referenced a missing interpreter at `D:\Repo\ERP\Python\pythoncore-3.15-64\python.exe`. The explicit command `C:\Python314\python.exe C:\Users\koros\.claude\tools\report_conform.py <ru-report> <en-report>` completed and injected both reports; the follow-up `--check` reported `all reports carry the mandated block`. No unrelated project contents were inspected.
- No project test/check/build/CI/migration command was run. The required report-format `--check` passed with `all reports carry the mandated block`. No push/PR/merge occurred. No exact-head delivery approval is claimed.

## Decision and remaining acceptance

- S2 Phase 8 remains `NOT APPROVED`; prohibited S2 cases remain `NOT_RUN`.
- S3 is read-only/provisional. GPT-PM G07 design MAJORs are closed only at design level; runtime/config, G03, legal/acquisition and same-fixture comparison remain open.
- S4 remains `INCONCLUSIVE`; all 53 policy selectors remain `NOT_RUN`; AC-17 in-run behavior remains `NOT_VERIFIED`.
- S5 remains not started pending S2/S4 and an identified or authorized AEVE source.
- Assigned tests/reviews, exact-head GPT-PM gate, and separate PR/merge are deferred until acceptance.

## Next steps and owners

1. Codex: capture and record the correlated verdict for sent request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e`; keep G07-CFG-M01 open until adjudicated.
2. Codex: continue permissible read-only S3 provenance/compatibility audit; operator decides legal/acquisition sufficiency for the recorded exact-pin license evidence; do not acquire/build/install/execute the candidate.
3. Operator: provide an exact S4 waiver if desired; otherwise retain `INCONCLUSIVE`. The 53 selectors remain unrun in either case unless authorized scope explicitly changes.
4. Codex: preserve S2 prohibited cases as `NOT_RUN` and collect only genuinely permitted evidence.
5. After S2/S4 close, operator identifies/authorizes an AEVE source, then Codex resumes S5.
6. After all acceptance gates close, Codex coordinates assigned tests/reviews, GPT-PM reviews the exact final head, and separate sprint PR/merge steps follow.
