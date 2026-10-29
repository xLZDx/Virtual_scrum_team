# S2 state history preserved before Agentic_Framework activation

Active sprint: S2. The framework now generates STATE.md; current acceptance is maintained in core/STATE.md. The complete historical state below is preserved from Git HEAD 20fda2c.

# SDLC state

## S2 persistent runner proposal — focused correction after GPT-PM MODIFY — 2026-10-27

Change 0470's correlated GPT-PM decision was `MODIFY` (request
`0ea02a82-72ba-44dc-a431-213d99bf8192`, reply `62890e6f-0fc5-432c-8bde-ba46be1fad8b`, job
`411b4d13-4c15-400c-85f6-54c8f7db289b`), with three MAJOR findings and one MINOR. The proposal
now defines one manager-controlled service replacement mode and a predecessor stop/fence record;
Supervisor/Store as sole grant issuer with current-authority checks and a separate, revocable
trust-root lifecycle; and a dedicated daemon OS identity with a grant-bound durable pre-dispatch
claim before child creation. GPT-PM returned correlated `ACCEPT — DESIGN ONLY` for M01-M03/N01
(request `4c2b6ea5-7de8-4d08-9d24-5c24e38d4b76`, reply
`c92f2614-885e-4e44-9160-c23650f80cb9`); a non-blocking changed-parent wording clarification
N02 was corrected and focused verification is pending. This accepts the architecture only:
systemd directive/effective-credential behavior, implementation, provisioning, and runtime
enforcement remain open. No source implementation or provisioning is approved. S2 Phase 8 remains
`NOT APPROVED`; restricted selectors stay `NOT_RUN`. See change 0470 and
`evidence/s2-persistent-runner-service-gptpm-review-20261027.md`.

## S2 Windows ACL/signer boundary design — 2026-10-27

At documentation baseline `41cfd5e`, actual architect and security-reviewer agents found the S2.3 Windows ACL requirement is not reachable through the current signed v2 Windows code path: `run_manifest_commands` fails closed on non-POSIX; its worker identity API accepts POSIX UID/GID; and the signer requires POSIX `O_NOFOLLOW` and Unix `SO_PEERCRED`. A DACL-only helper would not establish effective worker access or authenticated signer IPC. Windows VST-011 and VST-015 remain `NOT_VERIFIED`. The fail-closed code is preserved; GPT-PM owns the platform-scope adjudication. If Windows v2 execution is selected, define SID/token provisioning, secure key opening, and caller-authenticated signer IPC before implementation. Design evidence: `evidence/s2-windows-acl-boundary-design-20261027.md`; change 0468. S2 remains NOT APPROVED and S3 source work remains deferred.

## S2 Windows E4.2 strict launch evidence — 2026-10-27

At exact source/test HEAD `a6ea0dc`, the designated E2E role confirmed the actual project strict suspended-create/Job Object attach/resume sequence with one harmless child that exited normally. It was observed in both outer and inner jobs; no termination API was invoked. This does not prove kill-on-close, descendant cleanup, timeout/crash, or ACL behavior, which remain `NOT_VERIFIED`/`NOT_RUN`. The executor wrapper's process exit and elapsed time were not recorded. Evidence: `evidence/s2-windows-strict-suspended-launch-a6ea0dc-20261027.md`; change 0469. VST-013 and S2 remain open.

## Latest S2 runner restart-fence follow-up — 2026-10-27

At the previously reviewed code/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`, architecture and reliability review found that an in-process cleanup latch did not fence a replacement process from an abandoned worker cgroup. Change 0464 added shared `flock` admission and strict stale-scope reconciliation. At exact code/test HEAD `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`, 188 safe Windows plus 11 safe WSL selector IDs passed. WSL additionally demonstrated cross-process lock serialization and removal of an empty stale scope after verifying `populated=0`; it did not exercise a populated orphan or crash. A later bounded WSL namespace observer found no Windows-drive or host-backed mount candidates in its 29-row view; it is not a signed E5 inventory and is documented in `evidence/s2-current-namespace-snapshot-a6ea0dc-20261027.md`. A bounded Windows probe confirmed nested Job Object assignment for a naturally exiting child, but not strict suspended launch or kill-on-close cleanup; see `evidence/s2-windows-nested-job-safe-a6ea0dc-20261027.md`. Fresh architecture/security/silent-failure reviews found no code BLOCKER/MAJOR; reliability retains a deployment MAJOR because no persistent service or stable delegated-parent replacement evidence exists. Detailed evidence and the task matrix are in `evidence/s2-restart-fence-exact-a6ea0dc-20261027.md` and `evidence/s2-task-acceptance-a6ea0dc-20261027.md`. Ten new pytest IDs extend the previous 209-ID inventory to 219 expected IDs; the same 20 restricted/unavailable selectors remain `NOT_RUN` and were not run. The transient `/run/vst-runner` directory was mode 0700, owned by runner UID/GID 997:988, and removed after unit shutdown; persistent provisioning is `NOT_VERIFIED`. Fresh signed E5 inventory, Windows ACL and strict launch/cleanup runtime, populated-scope crash/recovery behavior, valid operator waiver and exact GPT-PM decision remain outstanding. S2 is not approved; S3 source work remains deferred.

Project: Virtual Scrum Team   Sprint: S2   Phase: 8 - Gate (NOT APPROVED; mandatory runtime/system acceptance incomplete)   Base HEAD: `6117ba24`   Prior tested S2 source/test HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`   Current exact regression source/test HEAD: `79155fdf9f1f4a7ba71358592ccd54c669a76291` (seven focused selector executions passed across exact heads: four at `dc1741b`, three bounded-Git at this head; 5 fresh specialist reviews complete, no code BLOCKER/MAJOR; one nonblocking database MINOR)   Updated: 2026-10-27

## Latest docs-only continuation — 2026-10-27

Canonical checkout `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`; the pinned build-profile source screen starts at HEAD `3467945` after change 0416; this workflow-run follow-up starts at HEAD `4878bd4` after change 0417. A read-only GitHub Actions API query found a successful `Build and Publish` run (`37665870819`) on the exact pinned Temporal commit and a failed separate `All Tests` run (`37665870783`); linked logs/artifacts were not retrieved and no artifact bytes were acquired. Therefore this confirms workflow status for the source commit but does not bind the released archive to a particular build output or checksum. Changes 0407 and 0408 supersede the earlier 0406 status note: 0407 reconciles S3 state with GPT-PM's design-only acceptance at exact reviewed HEAD `77b319367b575b9f4c0a193e91405df507c886e6`; 0408 aligns VST-028 with that status. The accepted G03/G07 design remains design-only (correlated request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245`, reply `14aedf85-c52b-5d64-b84b-40baf9a99455`). Permit/gateway implementation, exact SDK/server runtime, full dependency provenance/license closure, operator legal/acquisition disposition, S2/S4 acceptance, and candidate comparison remain open. S4 stays `INCONCLUSIVE`; all 53 policy selectors stay `NOT_RUN`. S5 remains gated on S2/S4 and an identified/authorized in-scope AEVE source. No source/test code, project acceptance tests, candidate build/acquisition/install/execution, or delivery occurred in this reconciliation; documentation-hygiene checks are not acceptance tests. The pre-existing untracked `evidence/s2-functional-test-run.md` remains protected and unstaged. No per-sprint worktree/fork was created.

The latest read-only job/source follow-up starts at HEAD `166ddc3` (change 0418). On the exact pinned Temporal SHA, Build and Publish had successful amd64, arm64, and Docker jobs. The pinned release workflow checks out `${{ github.ref }}` and invokes the local Build Binaries action with release mode enabled; that action configures Go from `go.mod` and GoReleaser v2.13.1. The exact-SHA Release job's checkout and binary build steps succeeded. The separate All Tests run had four failed functional shards (`sqlite` 0/1/2 and `cass_os3` 2), followed by a failed Test Status job. At the time of change 0418, failure logs had not been inspected; the later 0421 read-only follow-up decoded three SQLite shard logs and bounded their observed failures. Causes remain unknown. This is upstream CI/build provenance evidence, not independent verification that a published asset digest matches the build output, nor local acceptance evidence. No candidate artifact was acquired or run.

Read-only logs for the three failed SQLite shards in upstream All Tests run `37665870783` were decoded: per-shard summaries report 49/52/59 failures and each reached the 39-minute runner timeout. Observed messages include worker-versioning lookup failures, a SQLite `workflow_type_name` length constraint failure, and context deadlines; root causes and reproducibility are unknown. At this earlier workflow-run follow-up, the `cass_os3` failed-shard artifact content was unavailable; it was later recovered and separately adjudicated in `evidence/s3-temporal-cassos3-artifact-detail-20261027.md` and `evidence/s3-temporal-cassos3-gptpm-adjudication-20261027.md`. This does not replace local acceptance or prove a candidate failure. See `evidence/s3-temporal-upstream-ci-failure-detail-20261027.md`.

## S2–S5 continuation reconciliation — baseline `a583514` (2026-10-27)

The current canonical checkout was verified at `D:\Repo\Virtual_scrum_team`, branch `s4-canonical-continuation`, baseline `a583514b58e0cfab95fe2e8cbf921634aaa6857f`. This documentation update does not alter the recorded S2 implementation/test heads. No sprint-specific worktree/fork was created. The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains protected and unstaged. No source/test code, project test/check, build, CI, migration, acquisition, install, or Temporal candidate execution occurred in this continuation. The report-format conformance check was run for the new HTML reports.

### S2 — permitted evidence only

The read-only Windows/WSL/firewall snapshots recorded in the 2026-10-27 evidence files remain point-in-time configuration observations, not proof of worker identity, Windows Job Object or POSIX descendant containment, end-to-end egress control, workspace binding, or persistent deployment. A current designated `e2e-runner` audit of the safe evidence denominator concluded that no additional selector can be run under the present scope without repeating already recorded selectors; it ran no tests and made no repository edits. Existing test evidence remains attributed to its exact recorded source/repository heads. Process-kill, crash/resume, mutation, and the other policy-restricted scenarios stay `NOT_RUN`; the incomplete platform controls stay `INCOMPLETE` or `NOT_VERIFIED`. S2 Phase 8 remains `NOT APPROVED`.

Latest permitted static recheck from repository HEAD `c528913` is recorded in `evidence/s2-readonly-static-system-recheck-20261027-0423.md`. It again observed Windows firewall inbound Block/outbound Allow and WSL input/output drop with loopback-only accepts; the inventory ran as root, not as the worker. The distro was started for the read-only inspection and later observed stopped. No egress packet or restricted acceptance scenario was run; this adds configuration evidence only and does not change Phase 8 `NOT APPROVED`.

### S3 — read-only audit and G07 adjudication

Pinned source screen: Temporal Server `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e` and Python SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`, with SDK-Core gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320`. Static source evidence records the in-memory default SQLite profile, file-backed template, and coarse default authorizer. GPT-PM accepted the corrected base G07 design in correlated request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` / reply `c9313616-dae6-5e23-9d94-21297ae17ec5`. It later accepted the corrected G03 design at exact reviewed HEAD `77b319367b575b9f4c0a193e91405df507c886e6` (request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245`, reply `14aedf85-c52b-5d64-b84b-40baf9a99455`, correlated), including the separately bounded `RespondActivityTaskCanceled` design exception. This closes design findings only. Read-only official release metadata lists SHA-256 `4260448d650c1ba7ee7683ff0c93d5c6a1709260e3a7ef543bfa34e06cff6051` for the Linux amd64 server archive and `2a59896f80e27864c7a817ed54aec9d8f5fd2b82d9a794e09951ec243503f70c` for its checksum-list asset; no bytes were acquired or independently verified. The official Go downloads index publishes the full proposed Go `1.26.10` Linux amd64 SHA-256; the reproducible-build report marks the archive PASS and shows the matching 16-hex-character digest prefix. The toolchain archive was not acquired or run. Gateway/permit implementation, source-to-binary provenance, exact server/SDK runtime, transitive license inventory, operator legal/acquisition disposition, S2, S4 and candidate comparison remain open; G07 cancellation interoperation remains `NOT_VERIFIED` / `NOT_RUN`. See changes 0404–0406 and `evidence/s3-g03-g07-adjudication-0405-20261027.md`, `evidence/s3-temporal-server-release-provenance-screen-20261027.md`, `evidence/s3-go-toolchain-release-provenance-screen-20261027.md`.  Repository-level MIT license facts are not legal approval (`evidence/s3-temporal-exact-pin-license-screen-20261027.md`). A read-only follow-up inspected the exact pinned `vtprotobuf` license and Nexus annotations source: `vtprotobuf` remains BSD-style with SPDX unverified; `nexus-proto-annotations` remains UNKNOWN despite no conventional license path or inline header in the inspected files and `NONE_DETECTED` package metadata. The recorded metadata table has 223 rows; all 12 package-metadata gaps are in the source follow-up (10 source-text/template classifications, one BSD-style entry without verified SPDX, one UNKNOWN). See `evidence/s3-temporal-go-license-detail-followup-20261027.md`; operator legal/acquisition disposition is still required. The pinned server `.goreleaser.yml` declares `cmd/server`, `CGO_ENABLED=0`, Linux amd64 among targets, `go mod download`, and SHA-256 checksums; its `go.mod` declares Go 1.26.8. This remains source configuration only, not release-job or artifact provenance. See `evidence/s3-temporal-server-build-profile-source-screen-20261027.md`.

### S4 — keep `INCONCLUSIVE`

The read-only wheelhouse recheck found the exact previously recorded directory and six wheel bytes matching the provisioning record; see `evidence/s4-prerequisite-provisioning-20261026.md`. No installation or test was performed. This is not an operator waiver. All 53 policy selectors remain `NOT_RUN`; AC-17 same-identity in-run change-and-restore remains `NOT_VERIFIED`; S4 remains `INCONCLUSIVE`. The safest current disposition is to preserve this state until an exact operator signature exists or the test contract changes through its authorized path.

### S5 and downstream delivery

S5 remains not started: S2/S4 closure and a specifically identified or authorized in-scope AEVE source identity/license/interface are prerequisites; the prior profile transport result is `NOT_COVERED: AEVE_PROFILE_TRANSPORT_UNAVAILABLE`. Assigned tests/reviews, exact-head GPT-PM gate, and separate sprint PR/merge steps are deferred until acceptance gates close. No push, PR, or merge is authorized or performed. Detailed criterion matrix is in `../../reports/S2_S5_CONTINUATION_2026-10-27.ru.html` and `.html`.

`6117ba24` is the recorded S2 base. The last prior GPT-PM-reviewed full S2 candidate is `f0bbac8`; source corrections are committed in `324f901` and `f95ceb1`; four focused regressions passed at `dc1741b`; constructor-failure, reader-start-failure, and pipe-read-failure selectors passed at exact source/test HEAD `79155fd`. Fresh reliability, architecture, silent-failure, and security reviews at `79155fd` found no actionable code BLOCKER/MAJOR. Database review found no integrity/locking BLOCKER/MAJOR and one MINOR: initial anchor-file creation does not fsync the parent directory, which may lose availability after power loss while failing closed. Because the S2 contract requires fail-closed integrity but does not require uninterrupted availability after host power loss, this remains a nonblocking availability improvement and does not hold code closure. Change 0334 corrected GPT-PM MAJOR S2-M01 by separately inventorying ordinary and ignored untracked files in the signed DiffGate evidence. At `f0bbac8`, the designated E2E role reports 5 new integration cases, 22 DiffGate cases, 5 contract-gate cases, and 7 provenance cases passing. The earlier correlated review `bb6a1039-7e7d-4578-ad43-ac498dc1e259` / `faee14fe-5c0b-56ee-83d8-1633b3dae415` preceded the fresh E5 run. The latest prior GPT-PM review `e2eb4388-fc76-4f2f-96d9-eac9bf583a6a` / `5a9fc968-e9c0-5225-bfde-9cff30165cdb` examined repository HEAD `4d9e76f`, confirmed S2-M01 CLOSED and zero source findings at that reviewed head, accepted E5 for that signed run only, and returned NOT APPROVED for Phase 8. A fresh exact-source review pass on `6117ba24..f0bbac8` then found a capability-boundary BLOCKER (exploitability inferred, not runtime-reproduced), an external-anchor tail MAJOR, and a bounded Git cleanup MAJOR. These findings and their corrections are recorded in changes 0436 and 0440; five focused regressions passed across exact heads `dc1741b` and `79155fd`, and fresh specialist reviews found no code BLOCKER/MAJOR. Broader system acceptance remains open. Read-only inventories on 2026-10-27 observed WSL nftables output policy drop, while Windows host outbound policy is Allow. These observations do not prove end-to-end egress enforcement, containment or worker identity. The prior GPT-PM response is summarized in `docs/sdlc/evidence/s2-gptpm-final-review-f0bbac8-e5-20261026.md` (change 0340).

Remaining system acceptance includes actual Windows Job Object nesting/descendant cleanup (`NOT_RUN`), full POSIX containment (`INCOMPLETE`), external direct-writer exclusion, worker workspace binding, full egress enforcement, and persistent production deployment (`NOT_VERIFIED`). Policy-restricted process-kill, kill-table, mutation, and full E8 crash/resume scenarios remain `NOT_RUN`. Fresh E5 evidence at exact code/test head `f0bbac8` is recorded in `s2-e5-runmanifest-wsl-f0bbac8-20261026.md`: the signed per-run probe passed all seven checks and observed a 2 GiB memory/64 task cap, 45-second ceiling, 1 GiB `/tmp`, 64 MiB `/dev/shm`, private network, path masks, no container sockets, and zero Windows-drive mounts. A fresh permitted subset at repository HEAD `022fd6b` passed six identity/reviewer-denial and temporary external-anchor selectors; this remains fixture-scoped (change 0343). The single-run UID 995 search ACL was restored exactly. The reserved-target egress check remains only a smoke probe. Source corrections are in `324f901` (capability drop, anchor-tail separator, bounded-Git reader cleanup) and `f95ceb1` (guard all post-spawn reader setup). Four focused regressions passed at `dc1741b`, including the capability test under `vst-runner` with ambient `CAP_SETUID`/`CAP_SETGID`; the constructor-failure regression passed separately at `79155fd`. Five fresh specialist reviews at `79155fd` found no code BLOCKER/MAJOR; database noted one nonblocking initial-directory-fsync MINOR. Use only the existing provisioned environment for qualifying permitted cases. Do not run prohibited scenarios or treat mocks as platform proof. No push/PR/merge is approved. The accidental phase-6 `git diff --check` with no output and no preserved exit code is recorded in change 0081 and is not verification evidence. The project has not initialized a VST store instance as its phase-state authority, so this file remains the phase record until the explicit cutover described in the S2 plan.

## Artifacts

| Phase | Artifact path | Author agent/model | Head | Status |
|---|---|---|---|---|
| 2 - Backlog | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` | Existing artifact; origin not verified | `6117ba24` | Entry criteria and backlog decisions reconciled with evidence |
| 3 - Design | `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` section 10 | `code-architect` / `gpt-6-luna` | `6117ba24` | Trust roots, signer boundary, external-anchor recovery, parser catalog, state cutover and compatibility recorded |
| 4 - Docs and test plan | S2 plan sections 4-10 | Coordinator / Codex | `6117ba24` | Requirements-derived acceptance and negative-input denominators recorded; test authorship belongs to test agents |
| 5 - Documentation review | S2 design review and source map in execution records | `code-architect`, `code-explorer` / `gpt-6-luna` | `6117ba24` | One review/fix pass completed; findings reconciled in the plan |
| 6 - Build | `tools/vst/` and linked change records 0065-0084, 0319, 0331, 0334, 0436, 0440 | `implementation-engineer` / `gpt-6-luna`; Codex | Source corrections `324f901`, `f95ceb1`; regression test commits `dc1741b`, `79155fd` | Three prior source findings were fixed in 0436; the additional bounded-Git post-spawn guard is in 0440. Five fresh specialist reviews completed at `79155fd`: no code BLOCKER/MAJOR; database recorded one nonblocking durability MINOR. |
| 7 - Verify | `tests/vst/` and `docs/sdlc/evidence/` | `functional-test-reviewer`, `e2e-runner` / `gpt-6-luna` | Four selectors at `dc1741b`, 4 passed/0 skipped; three bounded-Git executions at `79155fd`, 3 passed/0 skipped (five unique regression selectors total) | Exact records: `s2-review-regression-dc1741b-20261027.md`, `s2-vst017-constructor-failure-run-79155fd-20261027.md`, and `s2-vst017-reader-reruns-79155fd-20261027.md`. The new selector uses a fake process and does not prove real process termination. Prior `f0bbac8` results remain scoped to that head. The read-only denominator audit found no additional safe non-duplicative selector; evidence: `s2-safe-selector-denominator-20261027.md`. Policy-excluded process-kill/crash/mutation/timeout selectors remain `NOT_RUN`. |
| 8 - Gate | Exact source diff, test evidence and reviewer records | GPT-PM / Codex | Latest prior correlated review: repo HEAD `4d9e76f`, source/test HEAD `f0bbac8`; current regression source/test head `79155fd` has 3 passing selectors; four earlier selectors remain at `dc1741b`; five specialist reviews completed with no code BLOCKER/MAJOR and one nonblocking database MINOR; NOT APPROVED | The prior GPT-PM decision accepted E5 only for its signed run. New code findings were corrected; seven selector executions passed across two exact-head revisions (four at `dc1741b`, three at `79155fd`); five fresh specialist reviews found no code BLOCKER/MAJOR, with one nonblocking database MINOR. A read-only audit found no further permitted non-duplicative S2 selector. Mandatory system acceptance remains open; the database MINOR is tracked as a nonblocking durability follow-up. No push/PR before final GPT-PM approval. |

## Open acceptance and backlog items

- Process-kill/kill-table and post-start overflow-cleanup scenarios are `NOT_RUN` under the active prohibition. Accountable owner: operator; test executor: `e2e-runner` only after the prohibition changes. Until then, preserve these cases as `NOT_RUN`.
- Nested Windows Job Object runtime behavior and POSIX process-group/descendant cleanup remain `NOT_RUN`; the `f0bbac8` WSL run proved only temporary-fixture signer/reviewer identity denial and Store anchor concurrency/recovery, not full containment. Full E8 crash/resume is also `NOT_RUN`. Accountable owner: operator; Codex owns preparing exact permitted fixtures and coordinating evidence; `e2e-runner` executes only after the applicable policy gate permits scenarios. Next: retain prohibited termination scenarios as `NOT_RUN`; do not claim full platform containment.
- E5 has a fresh signed per-run WSL preflight PASS at exact source/test `f0bbac8` (change 0339), including observed 2 GiB memory, 64-task, 45-second, `/tmp` and `/dev/shm` limits, private network, path masks, complete socket enumeration with zero paths, and zero Windows-drive mounts. GPT-PM reviewed it in request `e2eb4388-fc76-4f2f-96d9-eac9bf583a6a` / reply `5a9fc968-e9c0-5225-bfde-9cff30165cdb` and accepted only the per-run preflight; the review could not independently recompute all signatures/digests without private WSL material. The run does not establish persistent production deployment, external direct-writer exclusion, worker workspace binding, or complete host/network egress enforcement; the reserved-target check is only a smoke probe. Accountable owner: operator; Codex owns evidence and gate reconciliation; designated `e2e-runner` executed the probe. Next: collect permitted system-boundary evidence and keep these unproven controls open; do not request another final gate until the mandatory evidence denominator is reconciled.
- Latest Phase 8 GPT-PM decision is NOT APPROVED (request `e2eb4388-fc76-4f2f-96d9-eac9bf583a6a`, reply `5a9fc968-e9c0-5225-bfde-9cff30165cdb`; full summary in change 0340). At that reviewed head S2-M01 was closed and no new source BLOCKER/MAJOR was found; E5 passed for that signed run only. Later specialist reviews found a capability-boundary BLOCKER (inference), an anchor-tail MAJOR, and a bounded-Git cleanup MAJOR; fixes are recorded in 0436 and 0440; four focused regressions passed at `dc1741b` and three bounded-Git regressions passed at `79155fd` (changes 0438, 0441, 0442, 0449). Fresh reliability, architecture, silent-failure, and security reviews found no actionable code BLOCKER/MAJOR; database review found no such finding and one nonblocking initial-directory-fsync MINOR. Real Windows containment and complete POSIX containment remain unproven; memory/storage enforcement, workspace binding, external direct-writer exclusion, and comprehensive egress lack complete evidence; policy-restricted process-kill/kill-table/mutation/full crash-resume remain `NOT_RUN`. Operator is accountable; Codex owns evidence coordination and implementation; designated `e2e-runner` executes permitted scenarios; GPT-PM owns adjudication. S4 evidence is separate and is not S2 approval. No push/PR before fresh approval correlated to the exact final repository HEAD.
- External worker candidate remains out of scope; only the hand-written worker is authorized by `core/DECISION_LOG.md`.

## Decisions and evidence

- The operator explicitly selected `gpt-6-luna` for agents in this continuation. This run-specific choice does not edit global model configuration.
- S2 implementation contracts and waiver limits: [S2 plan](../S2_SANDBOX_WORKER_PLAN_2026-10-24.md#10-decisions-required-before-implementation) and [decision log](../../core/DECISION_LOG.md).
- Current evidence: `docs/sdlc/evidence/s2-bounded-operation-recovery-run.md`, `docs/sdlc/evidence/s2-e2e-bounded-snapshot-ed531.md`, and fresh per-run WSL preflight `docs/sdlc/evidence/s2-e5-runmanifest-wsl-f0bbac8-20261026.md`; linked records 0076-0085 and 0339. Historical E5 evidence remains tied to its recorded code head; only the new signed run is bound to `f0bbac8`.
- Supplemental read-only system inventory at the 2026-10-27 repository baseline is in `docs/sdlc/evidence/s2-readonly-wsl-system-inventory-20261027.md`. It was run as root and does not establish `vst-worker` identity, containment, firewall/egress, or persistent deployment.
- Supplemental read-only firewall configuration inventory is in `docs/sdlc/evidence/s2-readonly-firewall-inventory-20261027.md`. WSL's current nftables output policy is observed as drop; Windows firewall profiles allow outbound traffic. No egress test was run, so this is not end-to-end enforcement proof.
- Final source reviews on `dc95915018b80f498d5cf775363712fb915fe04e`: `security-reviewer` (GPT-6 Luna, low effort; reviewed diff from `280e2d0`), `reliability-reviewer` (GPT-6 Luna, low effort), and `database-reviewer` (GPT-6 Luna, medium effort) reported no remaining source MAJOR/BLOCKER. The security/reliability review context was repository evidence HEAD `e262e11003e16ec392203ed074d1fb490a9aa00e`; database reviewed source commit `dc959` with checkout HEAD `648012236a783e36c88573b34cf3a0c302413958`. All reviews were read-only and ran no tests/checks. Their shared residuals are live-child termination/abrupt-crash cleanup `NOT_RUN`, plus OS memory and temp-storage quota `NOT_VERIFIED`.

### S3-CI-N01 disposition — source-only, exact upstream pin

GPT-PM's correlated architecture adjudication request `c91fcd58-8ab7-4bf5-994b-c3ea8f1c4713` / reply `48f7b17e-69ab-412b-aa83-17de146f1c9f` retained Temporal Server `v1.32.1` + Python SDK `1.34.0` as a provisional read-only comparator (0 new architecture BLOCKER/MAJOR, 1 MINOR, 2 INFO). It did not approve acquisition, runtime, final selection, or S3 acceptance. Codex recorded the requested CI-risk mapping in `evidence/s3-temporal-upstream-ci-risk-disposition-20261027.md`: the Worker Deployment build-ID message is outside the current fixed-queue/closed-RPC design; SQLite workflow-type length and context deadline handling require qualification; the closed-channel warning and `cass_os3` details were unresolved at that review stage. The SQLite workflow type is not frozen in the proposed profile. The later-recovered `cass_os3` artifacts and source-only GPT-PM adjudication are recorded in `evidence/s3-temporal-cassos3-artifact-detail-20261027.md` and `evidence/s3-temporal-cassos3-gptpm-adjudication-20261027.md`; S3-CI-I02's missing-content gap is resolved, while the upstream failure and runtime qualifications remain open. The upstream All Tests result stays FAILED; G03/G07 runtime qualification stays open. GPT-PM's focused verification then closed `S3-CI-N01` against its submitted evidence. No local test, candidate acquisition/run, or policy selector was performed for this documentation change.

### S3-CI-N01 — closed at source-only documentation level

GPT-PM's focused verification at declared exact HEAD `0a9a70bd5d80a64bba4c7d6e9f8ae7f47dd24ac6` closed S3-CI-N01 with zero new BLOCKER/MAJOR/MINOR and one INFO, S3-CI-I03 (preserve the distinction between documentation closure and compatibility closure). Correlated request `7bbd3f85-a0e3-40bc-8b81-6052dd228a31`, reply `b14bdbb9-b8f3-46a7-8ce5-913bfb5999b2`; exact response is retained at `evidence/s3-temporal-upstream-ci-gptpm-verification-20261027.md`. The review verified the attached source-only risk mapping but did not independently inspect the checkout or verify attachment bytes against Git HEAD. Root cause/reproducibility, exact server/SDK runtime, SQLite schema/type, timeout, channel-close behavior, and cass_os3 details remain unresolved as applicable; upstream All Tests remains FAILED and G03/G07 runtime qualification stays open. No S3 acceptance or acquisition authorization follows.

### S3 cass_os3 artifact follow-up — decoded upstream evidence

Codex recovered the `test-summary.json` and JUnit artifacts for failed upstream job `112946311769`; both downloaded ZIP SHA-256 values match GitHub's listed artifact digests. GPT-PM's correlated supplemental response (request `d09d38ca-76f4-47c2-9bd2-aa2e6d8cd38f`, reply `453a15fe-f0d3-4944-a9ee-f2986a34d3a7`, `correlated=true`) accepted the source-only impact mapping and resolved S3-CI-I02's missing-content gap. The summary contains 676 rows (675 Failed, 1 PANIC); 657 failure rows show only RUN/PAUSE and are not independently confirmed defects. Callback and schedule/backfill are outside the current G07 feature profile; versioning/task-forward deadlines/RST_STREAM and redirect remain unresolved against the selected lifecycle; the activity timeout goroutine panic requires qualification. Root cause/reproducibility remain unknown, and the upstream shard remains FAILED. GPT-PM reviewed the six supplied documents but did not independently inspect the checkout or parse the raw archives. This does not provide runtime compatibility or S3 acceptance; no local acceptance test or candidate execution occurred.

## S2 E4 coding continuation — 2026-10-27

The current S2 continuation now includes the VST-013 cross-UID cleanup correction described in change 0454. The failure at `161dcc7` showed a UID 999 descendant surviving UID 997 process-group cleanup. The new implementation uses a sanitized, gated child in a unique runner-delegated cgroup-v2 scope and refuses non-approved execution if attachment or cleanup is not confirmed. Architecture design review and 5 focused fake-boundary tests passed; the test run was on an uncommitted working tree based at `47cdc48`, so exact-head functional evidence and delegated WSL E2E remain pending. This does not close E4, E5, S2 Phase 8, or establish persistent service deployment. S3 work has not started. The protected pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was left untouched.

## S2 E4 post-review safety follow-up — 2026-10-27

At exact HEAD `ce8f7eeae840d911ae89ae91f0264eec2d540874`, the selected POSIX cross-UID WSL E4.1 selector passed (1 passed in 4.11s), and exact-head unit tests passed (5 passed). The active cgroup path/events were not retained. Fresh architecture and reliability reviews then found a gate-start timeout gap and that later manifest commands could run after cgroup cleanup was unconfirmed; security review found no issue. Codex fixed both; nine focused unit selectors passed on the uncommitted follow-up. Since source changed, the prior real E2E result is not exact-head acceptance for the current tree. Exact-head functional and WSL E2E reruns remain pending. VST-013 and S2 Phase 8 remain open, and S3 has not started. See change 0455.

## S2 E4 runner retry-latch follow-up — 2026-10-27

At `55cc6313dceeffe2d6777b10e686ab851e0a8b8c`, 9 focused unit tests and the real UID 997→999 delegated-WSL selector passed; the active child cgroup path and `cgroup.kill` were captured, while the final `populated 0` event was not retained. Fresh security review raised a conditional same-process retry concern after an unconfirmed cleanup. Codex added a process-local latch and the functional-test reviewer passed four focused latch/deadline selectors on the uncommitted tree. Exact-head unit, E2E and fresh review are required after this source change. S2 remains open; S3 has not started. See change 0456.

## S2 E4 concurrent runner admission — 2026-10-27

At `b00edae5cdd46920c2a1ec26bfc58796ba58f372`, 10 focused selectors and the real delegated WSL cross-UID selector passed. Architecture/security review identified a conditional race between the process-local cleanup latch and concurrent calls. Codex serialized distinct-UID POSIX launches over launch, wait, and cleanup; the new bounded concurrency test confirmed the second call waits and then refuses after the first cleanup fails. Eleven focused selectors passed on the uncommitted tree. Exact-head tests and WSL E2E remain pending. VST-013/S2 remain open; S3 has not started. See change 0457.

## S2 E4 admission deadline correction — 2026-10-27

At exact commit `3be44ad4ea93bc9e68cee1534d1d4c4e731ac451`, 11 focused lifecycle selectors and the designated POSIX cross-UID WSL selector passed. The WSL runner/test archive matched the exact commit; `Delegate=yes`, cgroup controls, UID/capability boundary, and bounded resource profile were observed. The fast final `populated=0` cgroup event was not retained, while assertions for `capture_incomplete=False` and stopped heartbeat passed. Exact-head architecture/security review then found lock wait was outside the deadline. Change 0458 now bounds admission by the original command budget and refuses to spawn after expiry. Exact-head test/runtime/review results are pending; prior 3be44ad evidence does not verify the correction. VST-013/S2 remain open; S3 has not started.

## S2 E4 absolute deadline follow-up — 2026-10-27

At exact commit `2a71cf4fc32715a1f9f502ab5e7e7788aeff45e8`, the designated functional reviewer passed 12 focused lifecycle selectors and the E2E role passed one bounded POSIX cross-UID WSL E4.1 selector. Evidence and exact environment limits are in change 0460 and `evidence/s2-e4-deadline-exact-2a71cf4-20261027.md`. Fresh architecture/security/silent-failure reviews found no actionable issue there; reliability identified that the relative budget could be rebased between caller calculation and wrapper entry. Change 0461 propagates the original absolute deadline; its exact-head tests, WSL runtime, and fresh reviews are pending. Do not reuse 2a71 results as verification of 0461. VST-013/S2 remain open; S3 has not started.

## S2 exact-head acceptance checkpoint — 2026-10-27

At exact code/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`, 178 focused Windows tests passed. Eight POSIX E3 temporary-anchor selectors, the VST-011 capability-drop selector, and two POSIX identity-boundary selectors passed in bounded WSL; a separate POSIX E4.1 cross-UID cleanup selector passed 1/1. Of 209 collected IDs, 189 passed and 20 remain `NOT_RUN`; E4.1 is outside this denominator. Commands, WSL unit profiles, archive hashes and limits are in `evidence/s2-safe-functional-exact-4c1692d-20261027.md`; task-by-task status is in `evidence/s2-task-acceptance-4c1692d-20261027.md`.

Four focused specialist reviews (architect, security, reliability and silent-failure; GPT-6 Luna, medium effort) found no actionable BLOCKER/MAJOR in their reviewed code scope at 4c1692d. This does not approve the sprint. E5 fresh signed inventory, Windows key ACL behavior, Windows Job Object nesting and E8 remain incomplete. Prohibited process/kill, crash/recovery and mutation-testing scenarios remain `NOT_RUN`. Exact-head GPT-PM adjudication and any required signed operator evidence are outstanding. S2 remains NOT APPROVED; no S3 changes were made during this continuation.

## S2 persistent runner implementation continuation — 2026-10-27

The current canonical-checkout working tree now contains the persistent manifest runner, root
Supervisor IPC, strict signer admission, execution grants, Store schema v5 claims/events, lifecycle
fence, fixed systemd units, and exact-HEAD helper/runtime installers. The source implementation and
documentation are recorded in change 0471 and the revised S2 design/evidence pages. These edits
have not been tested, checked, built, migrated, provisioned, reviewed against the final exact diff,
or runtime-proven. The earlier design-only GPT-PM acceptance is not an implementation approval.
The full current diff still needs actual assigned functional/E2E work after coding closure, relevant
specialist reviews, and fresh exact-head GPT-PM adjudication. The selected WSL setup must also
reconcile disabled automount with access to the one canonical `/mnt/d/Repo/Virtual_scrum_team`
checkout without creating a separate worktree. Existing forbidden process-kill, crash/recovery,
mutation, E8, and restricted policy selectors remain `NOT_RUN`; no waiver was inferred. S2 remains
open, and S3 has not started. Owner: Codex for code/review coordination; functional-test-reviewer
and e2e-runner for permitted post-code test/runtime evidence; relevant specialist agents and GPT-PM
for exact-diff review and gate; operator for any required WSL host action or attestation.

The 2026-10-27 focused lease/dispatch adjudication is `MODIFY` (request
`1ff3b849-6180-4cb3-83ea-0eab47e56a3e`, reply `762291a2-5c34-470d-8b98-9a38a4cfc5ee`). GPT-PM
rejected invoking the global reaper from `issue_grant` because that would expand dispatcher
authority to reconcile unrelated tasks; missing lease markers require trusted recovery and grant
refusal. `S2-DISPATCH-M01` remains MAJOR/OPEN because no production coordinator source/call site
was identified; no scheduler, CLI, spool, or new assignment authority is approved. Recovery,
retry authorization, and grant issuance remain separate. Evidence:
`evidence/s2-persistent-runner-lease-dispatch-gptpm-review-20261027.md`. This adjudication did not
independently verify the current checkout or approve the current exact diff, runtime, release, or
restricted selectors.

Subsequent correlated GPT-PM review opened `S2-RC-M01` MAJOR: a predecessor `INDETERMINATE`
grant is terminal but does not resolve its possible effects or authorize attempt+1. A distinct
authenticated evidence-bound `RECONCILED` disposition that permits continuation is required before
a separately authorized successor attempt; enforcement is required at lease acquisition, grant
basis and claim admission. Request `e73cabde-5580-4be5-9ad1-63f65521f347`, reply
`9f337b5f-04f6-4610-b453-3926ba4a6bc8`; evidence is
`evidence/s2-runner-claim-reconciliation-gptpm-review-20261027.md`. Fresh reliability review also
opened `REL-M01` MAJOR: a generic exception after a durable reservation can leave the current
service generation running with an unresolved claim; it must fail-stop or enter authenticated
recovery. The earlier 117/130 focused passes predate the final gate/reconciliation corrections and
are not current-source verification. Change 0472 records the source fixes and final 138-ID focused
rerun; runtime remains NOT_RUN. The current regression fixes still require fresh specialist review
and exact-head GPT-PM approval. S2 remains NOT APPROVED, S3 has not started, and the production
coordinator blocker remains open.

## S2 final gate authority corrections — 2026-10-28

The assigned functional-test-reviewer ran four approved groups on the working source/test diff based
on base HEAD `2da827be982d3f2d6f2adf152668af6ff8007f21`: 46 persistent-runner, 32 E1, 38 E2, and 22
E6 tests passed (138 passed, 0 failed, 0 skipped). The direct regressions prove that unresolved
runner claims block a stale PASS at gate time, signed reconciliation binds the exact
`EXECUTION_RESERVED` predecessor and closed outcome matrix, and an exception after confirmed
reservation enters the fail-stop path before child launch. Evidence:
`evidence/s2-final-gate-authority-regressions-20261028.md`.

The focused tests use in-memory Store fixtures and fake callbacks; they do not establish installed
service framing, daemon/systemd restart, Windows/WSL containment, E5 signed inventory, or production
coordinator integration. `S2-DISPATCH-M01` remains MAJOR/OPEN because no production coordinator
callsite has been found and no new scheduler, CLI, spool, or assignment authority is approved. The
operator-reconciliation method is still in-process only; deployed service dispatch/role allowlist
exposes no reconciliation operation. Fresh specialist review and exact-head GPT-PM approval are
pending. Prohibited process/crash/recovery/mutation/E8/policy selectors remain `NOT_RUN`. S2 remains
NOT APPROVED; S3 has not started. Owner: Codex for bounded source correction, permitted evidence and
integration discovery; GPT-PM for architecture/exact-head adjudication; operator for any required
signed attestation.

## S2 retry-authority and systemd egress correction — 2026-10-28

Working change 0473 is based on committed HEAD `378df7260d8654f396ae1b45eaa9462d4bb4b88f`. The designated functional-test-reviewer completed four approved groups against the working diff: 56 persistent-runner, 32 E1, 38 E2, and 22 E6 tests passed (148 passed, 0 failed, 0 skipped). Exact commands, environment, hashes, failed-attempt history, warning and limitations are in `evidence/s2-adjudicated-runner-regressions-20261028-attempt2.md`; change record 0473 summarizes the delta. Correlated GPT-PM clarification `b84e73a1-55ac-47b0-87f8-20261028f002` / `8cc3b2ca-fc98-4d8a-98ee-120579a9cde6` permits a successor only after exact authenticated PENDING `NO_EXECUTION_PROVEN` or exact signed `EFFECTS_RESOLVED` from `EXECUTION_RESERVED`, followed by separately authorized successor; no receipt is synthesized. Full manifest timeout plus five-second margin must fit both owner and lease authority. The fixed runner unit declares PrivateNetwork, AF_UNIX-only and namespace restrictions. Optional operator-only reconciliation RPC is implemented but inactive; no operator peer/account/key is evidenced.

The focused functional evidence was run against a working diff based on the recorded base HEAD; the test result is not a post-commit rerun or final exact-head review. Live WSL/systemd/POSIX boundary, worker egress and inherited descriptor/forwarding absence, run-bound operator E5 attestation, Windows containment, and production dispatch remain unproven. `S2-DISPATCH-M01` remains MAJOR/OPEN because this repository has no production coordinator call site; no scheduler, CLI, spool, or second assignment authority was added. Prohibited process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`. Phase 8 remains `NOT APPROVED`; S3 has not started. Next: perform permitted WSL/system evidence after exact-head preconditions, then obtain fresh exact-head specialist reviews and GPT-PM adjudication. Owners: Codex for code/evidence/review coordination; GPT-PM for adjudication; operator for any actual signed E5 attestation or operator credential provisioning.


## S2 WSL installer preflight — 2026-10-28

At exact code/test HEAD `7120e2c647cc95703704905efa76de735ca8d0ec`, read-only inspection found Ubuntu 24.04.5 on WSL2, automount and interop disabled, no Windows-drive mounts in the inspected table, expected runner/worker UID/GID, active systemd, and nftables input/output drop with loopback-only acceptance. These are configuration observations; no traffic or worker execution was tested. The exact-head installer failed before deployment because `git archive` exported shell scripts as CRLF under global `core.autocrlf=true` and `* text=auto`; WSL `/bin/sh` rejected `set -eu\r` in the helper installer. Evidence: `evidence/s2-wsl-installer-preflight-7120e2c-20261028.md`. The reported `/run/vst-deploy-...` stage was absent at subsequent read-only inspection; no deletion was performed. The old helper still reports HEAD `621ddc01`, `/opt/vst-runtime` is absent, and all VST units are not found/inactive. No E5 signature or runtime acceptance is claimed. Codex owns the archive correction; e2e-runner owns the approved retry and system evidence; GPT-PM owns final adjudication; operator owns any fresh run-bound E5 attestation. Keep process-kill, crash/recovery, mutation, E8, policy selectors, and fresh run-bound E5 signing `NOT_RUN`.

## S2 legacy recovery and installer archive correction — 2026-10-28

Change 0474 fixes the legacy schema-v5 PENDING recovery-history finding from exact-head review of change 0473. The exact pre-0473 event shape is validated consistently through fresh startup replay, claim status, and successor eligibility; malformed or mismatched semantic fields fail closed, and a distinct run-bound successor preflight remains mandatory. The functional-test-reviewer reports 154 unique focused cases passing (62 persistent runner, 32 E1, 38 E2, 22 E6), with detailed commands and failure history in `evidence/s2-pre0473-schema-v5-compatibility-20261028-attempt2.md`. The exact 7120e2c WSL preflight found no effective runtime installation and failed because `git archive` converted shell scripts to CRLF under global `core.autocrlf=true`; change 0474 forces raw LF archive bytes. The fix awaits a committed exact-head retry. S2-DISPATCH-M01 remains open; system runtime/effective egress, Windows/POSIX process containment, operator E5 signature, operator reconciliation peer identity, fresh reviews and exact-head GPT-PM gate remain open. Restricted scenarios stay `NOT_RUN`. Do not start S3 or publish S2.

## S2 versioned helper design and archive correction — 2026-10-28

Correlated GPT-PM request `b84e73a1-55ac-47b0-87f8-20261028f003` / reply `fc67f0f3-fd09-4c38-81cb-5988d8fe61d9` accepted design only for `S2-HELPER-M01`: version each privileged helper path by the full source commit; bind path/head/source SHA/binary SHA in root Runner config; verify before launch; publish privately with no-replace semantics; preserve the old fixed helper with no fallback or replacement. Design note: `S2_VERSIONED_WORKER_HELPER_DESIGN.md`. The old helper remains untouched. Change 0475 is committed at `d5001797cb94113efd9a8dc26e4a15f2dc130976`; the two focused modules passed 179, failed 0, skipped 6 on that exact head with CPython 3.14.3 (attempt 5). Six platform skips remain unverified. The exact-head WSL installer also succeeded: versioned helper/runtime/three units matched recorded hashes, and the legacy helper remained unchanged; units were not enabled or started. Exact evidence: `evidence/s2-versioned-worker-helper-execution-20261028-attempt5.md` and `evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`. `core.autocrlf=false` alone had been insufficient at HEAD 9a5; the committed archive contract pins `core.eol=lf` too. The repository has no Runner root-config producer; root-owned config/credentials, current-run signed E5, service activation/manifest, effective egress and platform containment remain unproven. S2-DISPATCH-M01 remains MAJOR/OPEN. Fresh architect, security, reliability, Python, silent-failure and general code reviews found no confirmed code BLOCKER/MAJOR; reliability recommended documenting how a later revision switch is authorized before another rollout. Exact-head GPT-PM gate remains pending. Restricted process-kill, crash/recovery, mutation, E8 and policy selectors stay `NOT_RUN`; no S3.

## S2 final GPT-PM gate — 2026-10-28 (change 0478)

PM Bridge request `7c9fcb10-61cc-4fdd-8292-c2dfbf97ff04` / correlated reply `f347e63d-f691-4561-86d9-95968bb3bb4e` adjudicated repository HEAD `381435a91c8483d7e6a38b2fe5678f4f15a1da76` and implementation/test commit `d5001797cb94113efd9a8dc26e4a15f2dc130976`: **NOT APPROVED**. `S2-HELPER-M01` is closed for source correction and recorded artifact installation only. Existing `S2-DISPATCH-M01` remains MAJOR/OPEN; service/restart qualification, root config/credentials, current signed E5, effective egress and mandatory platform evidence remain open. The six focused-test skips are not passes, and restricted selectors remain `NOT_RUN`. Codex locally verified the exact submitted patch and source ancestry after the GPT-PM response; that closes a provenance note only. No additional unconditional code change was recommended. No S3 work has started. See `evidence/s2-gptpm-final-gate-381435a-20261028.md`.

## S2 deployment revision-switch follow-up — 2026-10-28 (change 0479)

The non-blocking reliability-review follow-up is documented: the installer refuses a different runtime selector and does not implement an upgrade/rollback procedure. Any future switch requires a separate reviewed runbook and operator authorization; no switch or service activation occurred here. S2 stays NOT APPROVED per final PM gate 0478. See `docs/changes/0479-document-s2-revision-switch-boundary.md`.

## S2 permitted WSL remainder checked — 2026-10-28 (change 0480)

A read-only selector triage by the designated e2e-runner found no further WSL/POSIX scenario that fits the current safety boundary; no tests were run. Root config/credentials, service activation, worker launch and E5 remain absent or unauthorized, while E4 and restricted selector families stay `NOT_RUN`. The operator owns the exact prerequisite/authorization; Codex coordinates. S2 remains blocked. See `evidence/s2-safe-wsl-remainder-audit-d500-20261028.md`.

## S2 coordinator source-scope decision — 2026-10-28 (change 0481)

The operator delegated the coordinator-source question to Codex but supplied no repository or file path. Codex searched only this repository; existing records and source confirm no production call site is present here. No neighboring checkout or general folder was inspected, and no new scheduler, CLI, spool, or assignment authority was created. `S2-DISPATCH-M01` remains MAJOR/OPEN, the prior exact-head GPT-PM verdict remains `NOT APPROVED`, and S3 has not started. To resume read-only integration review, the operator must identify the exact external source path; if none exists, any proposed new architecture requires GPT-PM adjudication before implementation. Evidence: `evidence/s2-coordinator-source-scope-decision-20261028.md`.

## S2 Windows containment selector audit — 2026-10-28 (change 0482)

The designated `e2e-runner` found no remaining Windows selector that both proves real containment and avoids the current process/descendant-termination restriction. The strict-launch candidate mocks Windows APIs and proves ordering only; the real descendant test depends on termination and remains `NOT_RUN`. No tests ran. `VST-013` stays `PARTIAL / NOT_VERIFIED`; see `evidence/s2-windows-safe-selector-audit-20261028.md`.

## S2 controlled runtime selectors — 2026-10-28 (change 0483)

Under GPT-PM controlled-testing authorization (request `a94486c9-f8e2-451e-91d2-4adb1799b8d6`, reply `85eba0d2-3670-5274-a787-58012255f22b`, job `3ff013cd-f5e4-441e-98c5-8c823f62a96f`), Windows E4 cleanup passed 2/2 and waiver-boundary selectors passed 7/7 at source/test commit `d5001797cb94113efd9a8dc26e4a15f2dc130976`. The retained WSL E3 summary (10 passed), synthetic identity summary (2 passed), and capability/timeout summary (2 skipped) are NOT_VERIFIED: their raw command/output are unavailable and the recorded module-qualified IDs for the first two groups are invalid. Their actual current selectors remain NOT_RUN pending exact evidence. Change 0487 records the corrected paths and status. No production/service/capability/credential/E5/E8/manifest activity occurred. `VST-013` remains partial; `S2-DISPATCH-M01` remains MAJOR/OPEN; S2 remains NOT APPROVED.

## S2 evidence scope correction — 2026-10-28 (change 0484)

The 53-selector policy family belongs to S4, not this active S2 run. No S4 tests or other S4 work were performed. Change 0484 clarifies this in the S2 evidence so sprint acceptance denominators remain separate.

## S2 selector provenance correction — 2026-10-28 (change 0485)

The retained e2e-runner summary says two POSIX runner selectors skipped, but the verbatim command/output are unavailable and the recorded command names `test_runner_drops_uid_change_capabilities_before_worker_command` in the wrong module. Both selector results are therefore NOT_VERIFIED and NOT_RUN for acceptance. Do not infer a skip/pass from the summary. No rerun or capability provisioning occurred. Full correction: `evidence/s2-controlled-runtime-selectors-20261028.md`.

## S2 dispatch architecture adjudication — 2026-10-28 (change 0486)

GPT-PM confirmed that production dispatch stays disabled/fail-closed until an existing trusted coordinator and authenticated assignment identity are identified. No new scheduler, assignment authority, CLI, queue, spool or validation bypass is authorized. `S2-DISPATCH-M01` remains MAJOR/OPEN and S2 remains NOT APPROVED. Correlated PM Bridge request `fca31d62-2d04-4d22-9753-103b748b5ae9`, reply `73847bec-1421-53e7-8c8d-ffb98ef240e5`, job `a1d2be1d-1d39-4edc-a369-76772cb8587c`. Evidence: `evidence/s2-dispatch-architecture-adjudication-20261028.md`.

## S2 WSL selector provenance correction — 2026-10-28 (change 0487)

Further exact-source review found invalid module paths in the retained WSL E3 and synthetic-identity commands as well as the capability-drop command. Exact command/output are unavailable; the retained result summaries (10 passed, 2 passed, 2 skipped) are NOT_VERIFIED and do not count toward acceptance. Current correct E3 IDs and identity module paths are recorded in `evidence/s2-controlled-runtime-selectors-20261028.md`; re-run only through the designated test role. No tests or capability provisioning occurred in change 0487.

## S2 corrected WSL runtime selectors — 2026-10-28 (change 0488)

Designated e2e-runner executed the corrected six E3 and two synthetic POSIX identity selectors against source/test commit `d5001797cb94113efd9a8dc26e4a15f2dc130976`; three test-file hashes matched Git. First batch: 11 passed, one failed because the disposable archive root mode `0700` prevented a child identity from importing `tools`. The targeted selector passed after changing only that temporary root to `0755`; functional-test-reviewer confirmed 12 unique cases pass after this harness correction. Exact commands and the initial failure are preserved in `evidence/s2-corrected-wsl-runtime-selectors-20261028.md`. No service, identity, capability, credential or production provisioning occurred. E5, production dispatch, system boundary, capability-dependent selectors and E8 remain open; S2 stays NOT APPROVED.

## S2 dispatch-owner admission fence — 2026-10-29 (change 0518 in progress)

GPT-PM's correlated follow-up returned MODIFY with MAJOR `S2-PROV-M03`: `Restart=no` does not
prevent an active socket unit from reactivating the owner relay after an ambiguous Supervisor RPC.
Change 0518 drafts a single-frame EOF contract, classifies unconfirmed post-RPC outcomes as
reconciliation-required, exits before another request, and adds a root persistent latch through
`ExecStopPost` plus socket/service startup conditions. Code/reliability review found the first latch
draft used an asynchronous socket stop after filesystem access. Change 0522 corrects source order:
the socket is stopped synchronously and confirmed inactive before `/etc` access; the hook retries
uncertain stop results with bounded per-call timeouts and capped backoff, and has no systemd stop
timeout. If persistence fails after confirmed socket shutdown, the socket is inactive at that
point, but no latch guards a later explicit start and cross-reboot safety is not established;
durable root-controlled `/etc` is required. Exact request-ID/Store reconciliation remains required
before separately authorized reopening. Evidence and request correlation are in
`evidence/s2-admission-fence-adjudication-20261029.md`; the source contract and provisioning plan
were updated. `git diff --check` passed for the corrective source/docs before commit. The focused
suite passed 107/107 on code/test revision `34bd7dc1b085789341b29937655af52e07f2ddbd`; the later
`ac64402` changed docs only. Installed-unit validation and runtime behavior remain unverified.
Independent re-review, PM re-adjudication and exact-head source approval remain open. No privileged
writes, service activation, real dispatch, E5, push, PR or merge occurred. `S2-DISPATCH-M01` remains MAJOR/OPEN, S2
remains NOT APPROVED, and S3 remains unstarted.

## S2 M03 cross-generation outcome recovery — 2026-10-29

GPT-PM returned MODIFY on the historical-result recovery proposal: exact replay from fully
verified immutable Store history is within the existing M03 scope, with a separate authenticated
read-only RPC. The route matches the complete original signed envelope and authenticated
principal, validates accepted event/operation/control history and the external anchor in one read
snapshot, preserves the original result/generation, and cannot create or authorize new work.
Current signature expiry or key revocation may not block retrieval of that exact historical fact;
new admission retains all current checks. An absent/mismatched request and legacy or corrupt
history fail closed.

Implementation is present in the canonical checkout. The designated e2e-runner executed the
four-file focused suite at exact HEAD `c855ca4f2888d7288b006973950e4c6d28023b63`: 130 passed,
0 failed. Fresh code, security, reliability and database reviews found no valid BLOCKER/MAJOR.
GPT-PM request `d16dbf96-54f8-4c96-8fa7-2b24445f85d9` returned ACCEPT — SOURCE/TEST SCOPE and
closed `S2-PROV-M03-R01`; full decision/limits are in
`evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
`S2-DISPATCH-M01` remains MAJOR/OPEN; production
coordinator, runtime/E5, production credentials/configuration, prohibited scenarios, and exact-head
GPT-PM acceptance remain separate S2 gates. S3 remains unstarted. Decision evidence:
`evidence/s2-cross-generation-outcome-recovery-adjudication-20261029.md`.
