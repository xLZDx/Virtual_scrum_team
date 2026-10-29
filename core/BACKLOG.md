# Backlog

## S2 — signed dispatch-instruction provenance and owner relay (source implemented; runtime open)

GPT-PM's correlated adjudication selects a purpose-specific, operator-authorized signed envelope
and requires independent verification in the root Supervisor before any durable intent event.
The Store remains the sole task/assignment/lease authority; the signer may authorize only one exact
request for already-assigned work. The envelope binds request ID, task, slot, attempt, epoch, run
ID, key ID, absolute UTC expiry, version, algorithm and purpose. The exact signed bytes and key
identity must be bound to durable idempotency and the hash-chained event. No unsigned fallback,
instruction-signing key generation/reuse, scheduler, account creation, root-config installation,
migration application, service activation, real dispatch or E5 attestation is authorized by this
decision. Source implementation and synthetic-fixture tests are authorized. S2 M01 remains
MAJOR/OPEN until source review, a real authorized issuer and trust key, runtime evidence, and
exact-head GPT-PM approval. The signed-instruction verifier/client is committed at `3fc010c`; the
owner relay, unit/socket templates, installer allowlist and plan corrections were committed as
`978aa5b` (change 0517). GPT-PM's follow-up returned MODIFY with new MAJOR `S2-PROV-M03`: an active
socket unit can reactivate the relay after an ambiguous Supervisor RPC. The correlated response and
current remediation design are in `docs/sdlc/evidence/s2-admission-fence-adjudication-20261029.md`.
Change 0518 added single-frame EOF enforcement, conservative unknown-outcome handling, and the
root `ExecStopPost` admission fence. Change 0522 corrects the stop ordering; installed systemd
behavior remains unverified. The subsequent MAJOR `S2-PROV-M03-R01` generation-recovery gap is
**CLOSED — SOURCE/TEST** at source/test HEAD
`c855ca4f2888d7288b006973950e4c6d28023b63`: the focused suite passed 130/130, four fresh
specialist reviewers found no valid BLOCKER/MAJOR, and GPT-PM returned ACCEPT under request
`d16dbf96-54f8-4c96-8fa7-2b24445f85d9`. Correlated evidence:
`docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
At code HEAD `56cd816b1b03b39c3f4b4a70ecf00d96ef95d321`, the same four-file WSL selection
initially found a stale direct-Store fixture missing the now-required synthetic `key_fingerprint`;
the test fixture was corrected without weakening its duplicate/lifecycle/replay assertions, and
the rerun passed 130/130. Commit `dcb5d63c19eeb63f2f17fce0add510937688e819` contains the exact
test blob executed by that rerun (SHA-256 `435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7`);
commands, environment and limits are in
`docs/sdlc/evidence/s2-cross-generation-outcome-recovery-rerun-56cd816-worktree-20261029.md`.
Exact-head GPT-PM approval and normal push remain pending.

This is source/test closure only. GPT-PM's correlated coordinator adjudication confirms the
existing `DispatchOwnerService` + authenticated Supervisor/Store admission + filtered Pub/Sub +
`StoreBackedDispatcher` is the accepted bounded coordinator architecture; no external coordinator,
second scheduler, or assignment authority is needed. `S2-DISPATCH-M01` remains MAJOR/OPEN only for
production integration: an authorized production instruction issuer/trust key, provisioned owner
identity and root configuration, current E5/runtime evidence, and a qualified real owner-to-Runner
journey are not established. This is not a request for another human user or an external path.

GPT-PM recognized the operator's existing autonomous authorization for bounded Ubuntu-24.04 WSL
preparation/provisioning, subject to exact source/test review and a reviewed immutable non-secret
configuration bundle. Fresh v6 Store initialization is conditionally allowed; an existing Store
migration has a separate gate. Distinct local service keys are conditionally allowed, but production
instruction-issuer authority/key and a purported operator E5 signature may not be invented or
impersonated. Restricted selectors remain `NOT_RUN`. Owners: Codex for source, exact config and
permitted evidence; GPT-PM for technical and final-gate adjudication; operator as the sole human
owner for genuine independent attestation/key-custody actions that cannot be produced by Codex.
Next: commit the accepted transport-only source/test scope with its detailed change record, then
prepare the exact immutable non-secret bundle for review and continue through conditional WSL gates
without asking for a nonexistent coordinator. Keep production dispatch closed and S3 unstarted until
full S2 acceptance. Full correlation and scope:
`docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.

## S2 — root/runtime preparation correction (changes 0517–0518 in progress)

Read-only Ubuntu-24.04 inventory confirms services inactive, runtime config absent, and no
dispatcher/owner/client identities. The 2026-10-29 `getent` rerun also found proposed UIDs 980/981
and GIDs 982/983/984 absent at that moment; these values are not provisioned or reserved. The
owner primary GID is now distinct from shared socket GID 984. The runtime symlink points to a
root-owned 0755 target; its 0777 symlink mode is not a permission issue. GPT-PM accepted correction
of the mistaken target-mode interpretation and withdrew that permission blocker, while runtime
acceptance remains unverified. No credentials or keys were read. The exact owner-service template
and field-level config matrix resolved the prior plan findings. The persistent admission fence and
cross-generation history replay are implemented; `S2-PROV-M03-R01` is CLOSED for source/test scope
under change 0537. Privileged production/service provisioning and runtime acceptance remain
unverified. Evidence:
`docs/sdlc/evidence/s2-root-runtime-provisioning-plan-20261028.md`,
`docs/sdlc/evidence/s2-provisioning-plan-adjudication-20261029.md`,
`docs/sdlc/evidence/s2-admission-fence-adjudication-20261029.md`, and GPT-PM correction request
`e2ce2445-58d8-4c93-acd9-8bb536767f58`, reply `83e0dbcb-e0bd-5ad5-aa37-80198e03c8ba`; M03 closure
evidence is in `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
Owner: Codex for non-secret plan/config preparation; GPT-PM for architecture/final gate; operator
for any separately privileged provisioning and genuine signed E5/network-policy attestation. Next:
resolve the coordinator architecture, then establish the exact authorized runtime identity/config
and E5 source before runtime acceptance.

## S2 follow-up — Windows ACL/signed-worker platform boundary (2026-10-27)

S2.3 requires Windows ACL key protection, but the signed v2 runner rejects non-POSIX execution and its signer requires POSIX `O_NOFOLLOW` and Unix `SO_PEERCRED`. Read-only architect and security reviews found no safe helper-only ACL fix: there is no Windows worker SID/token contract or authenticated Windows signer IPC path. Design and evidence are in `docs/sdlc/evidence/s2-windows-acl-boundary-design-20261027.md` (change 0468). Windows VST-011 and VST-015 acceptance remain `NOT_VERIFIED`; the current fail-closed behavior is preserved. Owner: GPT-PM for platform-scope adjudication; Codex for follow-up and complete implementation if Windows signed-worker support is selected; `functional-test-reviewer`/`e2e-runner` for tests/runtime after coding. Next: get GPT-PM's scope disposition; if Windows v2 is in scope, define SID/token, secure key-open, and authenticated signer IPC together before source changes. Do not infer acceptance from the separate nested Job Object probe.

## S2 follow-up — cross-process cgroup restart fencing (2026-10-27)


Exact-diff architecture and reliability reviewers found a MAJOR: process-local cleanup state did not prevent a replacement runner from starting while an old delegated worker cgroup remained. Change 0464 adds a private shared `flock` plus bounded stale-scope reconciliation in `tools/vst/runner.py`. At exact code/test HEAD `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`, designated test roles passed 188 safe Windows and 11 safe WSL IDs; real cross-process lock serialization and empty stale-scope removal were observed. Change 0465 committed the exact-head evidence and task matrix. Ten new pytest IDs extend the earlier 209-ID inventory to 219 expected IDs; the same 20 restricted/unavailable IDs remain `NOT_RUN`. Fresh architecture/security/silent-failure reviews found no source-level BLOCKER/MAJOR; reliability retains a deployment MAJOR because stable service cgroup/runtime-directory behavior across replacement is unverified. A supplemental bounded WSL namespace snapshot found no host-backed mount candidates but is not a signed E5 inventory (change 0466). A safe Windows nested Job Object assignment probe passed for a naturally exiting child; it does not establish strict suspended launch, kill-on-close cleanup, or Windows ACL/key isolation (change 0467). `/run/vst-runner` existed only in bounded transient units; no persistent runner service was found by the recorded read-only unit-name inventory. Owner: Codex for code/evidence; functional-test-reviewer/e2e-runner for test/runtime evidence; operator for persistent service/subtree provisioning and any signed E5/waiver; GPT-PM for exact-head adjudication. The exact PM Bridge request `d9e174a1-fbdf-4ba7-bcd0-ec1902ed38c4` remains uncertain; a peek surfaced text naming it but no correlated reply ID/user turn, so no new gate result is recorded. Next: reconcile that PM Bridge lineage without resending, then resolve only permitted E5/service/platform evidence. Keep live populated-scope kill, runner-crash/recovery, mutation, E8 and policy scenarios `NOT_RUN`.

### Persistent runner service implementation continuation

Change 0471 now adds the manifest-bound runner service, root Supervisor IPC, strict signer
admission, Ed25519 execution grants, append-only Store v5 execution claims/events, root lifecycle
fence, three fixed systemd unit templates, and exact-HEAD helper/runtime installers in the
canonical checkout. It implements the design accepted by GPT-PM at design level (request
`4c2b6ea5-7de8-4d08-9d24-5c24e38d4b76`, reply `c92f2614-885e-4e44-9160-c23650f80cb9`), but
that earlier decision is not approval of this code. The current diff has not been tested, reviewed
against its exact final contents, migrated, provisioned, or runtime-proven. The helper and runtime
installers were not run. The canonical checkout is the only source and no sprint worktree was
created. Static review found the WSL installers require source under `/mnt/d/Repo/Virtual_scrum_team`
while also requiring automount disabled; no verified hash-bound artifact handoff into distro-local
storage exists. Deployment therefore remains unavailable under the required E5 profile until that
handoff source is now present in `tools/qa/install_wsl_runtime.ps1` and the two Linux installers;
it has not yet been reviewed or executed. Owner: Codex for code completion and test/review coordination; functional-test-reviewer
and e2e-runner for post-code functional tests and allowed runtime evidence; GPT-PM for exact-head
architecture and final gate; operator for dedicated WSL host changes and any required attestations.
Next: finish code/doc reconciliation and exact-diff review of the handoff, then run only permitted
assigned scenarios after coding is complete; retain crash/process-kill/mutation and policy selectors
as `NOT_RUN` unless existing authorization explicitly covers them. S2 remains open; do not start S3
before S2 closure.

## S2 E4.2 strict suspended-launch evidence (2026-10-27)

At source/test HEAD `a6ea0dc`, designated `e2e-runner` confirmed the actual project suspended-create/Job Object attach/resume sequence with a harmless child that exited normally; nested membership was confirmed in outer and inner jobs. No termination API or pytest selector was used. Exact record: `docs/sdlc/evidence/s2-windows-strict-suspended-launch-a6ea0dc-20261027.md` (change 0469). Wrapper exit code and exact elapsed time are `NOT_RECORDED`. This does not prove kill-on-close, descendants, timeout/crash, or ACL isolation. Owner: Codex for evidence; GPT-PM for gate; operator for any change to the restricted process-termination scope. Next: keep VST-013 partial and preserve restricted scenarios as `NOT_RUN`.

## S2 acceptance checkpoint at source/test HEAD 4c1692d (2026-10-27; superseded for runner restart code)

## S2 E4.2 strict suspended-launch evidence (2026-10-27)

At source/test HEAD `a6ea0dc`, designated `e2e-runner` confirmed the actual project suspended-create/Job Object attach/resume sequence with a harmless child that exited normally; nested membership was confirmed in outer and inner jobs. No termination API or pytest selector was used. Exact record: `docs/sdlc/evidence/s2-windows-strict-suspended-launch-a6ea0dc-20261027.md` (change 0469). Wrapper exit code and exact elapsed time are `NOT_RECORDED`. This does not prove kill-on-close, descendants, timeout/crash, or ACL isolation. Owner: Codex for evidence; GPT-PM for gate; operator for any change to the restricted process-termination scope. Next: keep VST-013 partial and preserve restricted scenarios as `NOT_RUN`.

Exact test ledger and task-by-task matrix: `docs/sdlc/evidence/s2-safe-functional-exact-4c1692d-20261027.md` and `docs/sdlc/evidence/s2-task-acceptance-4c1692d-20261027.md`. Six-module inventory: 189/209 IDs passed (178 focused Windows functional selections, 8 POSIX E3 temporary-anchor selectors, 1 WSL VST-011 capability-drop selector, and 2 POSIX identity-boundary selectors); a separate E4.1 cross-UID WSL runtime selector passed 1/1 outside the inventory. Twenty IDs remain `NOT_RUN`. Four focused specialist reviews found no actionable BLOCKER/MAJOR in scope; exact-head GPT-PM gate remains outstanding. E5 fresh signed probe, Windows ACL key isolation, Windows nested Job Object and E8 remain incomplete. S2 is not closed; no S3 changes were made during this continuation and existing S3 records remain unchanged. Owners: Codex for evidence/docs/local Git, GPT-PM for adjudication, operator for any required signature or genuinely missing environment authorization. Next: commit this evidence bundle, obtain one exact-head GPT-PM sweep, then resolve only permitted S2 gaps; no push/PR/merge before approval.

| ID | Item | State | Notes |
|---|---|---|---|
| VST-001 | Raise `maxTurns` or split tasks for read-heavy design/explore agents | done 2026-10-15 | Raised in the global agents: code-explorer 8->16, code-architect 16->20, tdd-guide 16->24, e2e-runner 16->24, functional-test-reviewer 20->25 (lint cap), security-reviewer 16->24, doc-updater 8->12. Pilot evidence: test, security and design agents each hit their limit and needed a resume. Large multi-epic authoring tasks should still be split per epic |
| VST-002 | Let design agents save their own document | open | `code-architect` is read-only; the coordinator saved `design.md`. Decide: add Write for a docs path or keep the technical-writer hand-off |
| VST-003 | Choose a license for the public repository | done 2026-10-15 | Operator delegated the choice; MIT selected (permissive; recommended in chat). `LICENSE` added |
| VST-004 | Decide whether `security-reviewer` runs in every SDLC pilot sprint | open (pilot data: it found no BLOCKER/MAJOR twice, GPT-PM still required exact-head correlation) | Routing makes it opt-in only; GPT-PM asked for an independent security review in the pilot |
| VST-005 | Add a project template (`docs/sdlc/` skeleton with STATE.md) installable into a new project | open | Currently created by the orchestrator at first use |
| VST-006 | Resolve role alias `adk-tune-sql-query` with a dedicated SQL-tuning agent if `database-reviewer` proves too broad | open | Mapped to `database-reviewer` on 2026-10-15 |
| VST-007 | Keep the exact verification record of the final test run in the repo (command, collected list, head) | closed in effect 2026-10-24 | Retained evidence files under `docs/sdlc/evidence/` record command, head and counts. Origin: pilot, GPT-PM rejected the first final review because the run record and head were not retained |
| VST-008 | Put the exact-head rule into `sdlc-orchestrator`: run the security review and GPT-PM on one committed head, avoid source commits afterwards | partly done 2026-10-24 | The exact-head rule is enforced in code by `tools/vst/gate.py` (stale head gives non-approval). Open sub-item (small): add the wording to the `sdlc-orchestrator` skill. Origin: pilot cost one extra GPT round |
| VST-009 | S2 E1: authenticated reviewer key, distinct from the worker key; verify IndependentReview receipts with it | implemented; focused tests passed; security/reliability/database reviews found no code-level MAJOR/BLOCKER; full required specialist consensus and exact-head GPT-PM gate pending | Reviewer registry is operator-root signed and bound by manifest version/digest; see S2 functional/E2E evidence and change records 0056-0058. The recorded review set and focused tests do not close remaining system/runtime acceptance in `docs/sdlc/STATE.md` |
| VST-010 | S2 E2: runner-derived `candidate_head` | implemented; focused tests passed; security/reliability/database reviews found no code-level MAJOR/BLOCKER; full required specialist consensus and exact-head GPT-PM gate pending | Runner/diff evidence is bound and consumed by the gate. Reviews are recorded against their stated source/repository heads; a fresh S2 GPT-PM decision for the final repository HEAD is still required |
| VST-011 | S2 E2: isolate the signing key from the process that runs commands | POSIX capability drop and synthetic signer-key/IPC boundary selectors passed at exact code/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468` | WSL evidence verifies existing runner/worker/signer identities, zero worker capabilities, denied synthetic key/socket access, and inability to change UID to signer. Read-only architecture/security review confirms the signed v2 path is POSIX-only and a standalone Windows ACL helper would be disconnected; see `docs/sdlc/evidence/s2-windows-acl-boundary-design-20261027.md`. | Windows ACL/signer isolation and persistent deployment remain `NOT_VERIFIED`; no real key was inspected. Owner: GPT-PM for platform-scope adjudication; Codex for complete implementation/evidence if Windows v2 is selected; operator for persistent environment attestation if required. Next: preserve fail-closed behavior and obtain GPT-PM's explicit scope disposition before changing the trust boundary. |
| VST-012 | S2 E3: whole-database rollback detection through an externally anchored event head | Existing anchor tests passed; no-final-newline append recovery correction passed its focused fixture regression at `dc1741b`; database review at `79155fd` found no integrity/locking blocker and one MINOR initial-directory-entry durability limitation | Cross-process anchor serialization and bounded recovery are in record 0043; prior tests at `f0bbac8` and safe WSL2 anchor evidence at `6ca2ee0` remain separately scoped. The new test confirms a valid no-final-newline checkpoint stays a readable two-record JSONL history after append; evidence: `docs/sdlc/evidence/s2-review-regression-dc1741b-20261027.md`. This fixture result is not crash or production rollback proof. Database reviewer noted the initial anchor-file creation does not fsync its parent directory; a power-loss directory-entry loss would fail closed for nonempty data (availability loss, not a rollback acceptance bypass). Codex assessed the S2 anchor contract: integrity must fail closed for a missing anchor, while uninterrupted service after host power loss is not an explicit acceptance requirement. Track this as a nonblocking availability improvement; it does not hold S2 code closure. Outstanding runtime/system limits are listed in `docs/sdlc/STATE.md`. |
| VST-013 | S2 E4: verify POSIX permissions and process-group behavior; verify Job Object nesting | At source/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`, the focused 13-case admission/deadline run and bounded POSIX E4.1 cross-UID runtime pass. | Functional and WSL commands, hashes, profiles, counts, and limitations are in `docs/sdlc/evidence/s2-safe-functional-exact-4c1692d-20261027.md`. E4.1 passed 1/1 in the exact archive; child `populated=0` after cleanup was not separately retained. Windows nested Job Object and prohibited process/kill selectors remain `NOT_RUN`; mocked Windows Job Object unit tests are not host nesting proof. The 20 remaining IDs are across several S2 epics, not all VST-013. Owner: Codex for evidence, GPT-PM for final adjudication; operator for any additional environment authorization. Next: retain VST-013 open until every platform denominator item is either permitted and evidenced or has an explicit scoped operator waiver. |
| VST-014 | S2 E5: sandbox specification (dedicated WSL distro or VM, automount and interop off, no container socket, default-deny egress, non-root, per-run secrets) and pre-flight probe | **PASS for the signed per-run WSL probe** at exact code/test HEAD `f0bbac8`; GPT-PM confirms the narrow per-run scope, while full system acceptance remains open. | Fresh run-bound operator attestation and runner-signed inventory are in `s2-e5-operator-attestation-f0bbac8-20261026.json` and `s2-e5-runmanifest-wsl-f0bbac8-20261026.md` (change 0339). All seven probe checks passed; socket enumeration was complete with zero paths, Windows-drive mounts were zero, and runner limits/masks were observed. Supplemental read-only host and firewall inventories at repository baseline `6b50527` and documentation baseline `9326f17` are in `s2-readonly-wsl-system-inventory-20261027.md` and `s2-readonly-firewall-inventory-20261027.md`; they record root execution and WSL output policy drop, but Windows host outbound is Allow and neither inventory proves end-to-end egress or containment. Current HEAD `c528913` static recheck is recorded in `s2-readonly-static-system-recheck-20261027-0423.md`; it repeats the same configuration limits and does not alter E5/Phase 8 acceptance. The correlated GPT-PM review (request `e2eb4388-fc76-4f2f-96d9-eac9bf583a6a`, reply `5a9fc968-e9c0-5225-bfde-9cff30165cdb`, change 0340) accepted E5 only for the earlier signed run. GPT-PM could not independently recompute all signatures/digests from the private WSL inventory and unavailable keys; coordinator verification is recorded in change 0339. The egress check remains a reserved-target smoke probe; memory/storage enforcement, external direct-writer exclusion, comprehensive egress, production deployment, and worker workspace binding remain incomplete or `NOT_VERIFIED`. Operator is accountable; Codex owns evidence/provenance and gate coordination; `e2e-runner` executed the probe; GPT-PM adjudicates the gate. Next: preserve these limits and keep S2 open. |
| VST-015 | S2 E6: deterministic diff gate and read-only reviewer credential | 22 focused diff-gate selectors and the bounded POSIX reviewer read-only fixture passed at exact code/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`. | Exact test ledger includes path/hash coverage and a reviewer identity that could not write its temporary worktree/SQLite fixture. Design review confirms the current Windows behavior fails closed; see `docs/sdlc/evidence/s2-windows-acl-boundary-design-20261027.md`. | Windows reviewer-credential behavior remains `NOT_VERIFIED`; overall S2 system acceptance and GPT-PM gate remain open. Owner: GPT-PM for platform-scope adjudication; Codex for implementation/evidence if selected. Next: keep Windows acceptance open pending explicit scope adjudication. |
| VST-016 | S2 E7: STOP and rollback transition table | implemented; owned WSL lifecycle scenarios passed; security/reliability/database reviews found no code-level MAJOR/BLOCKER; full required specialist consensus and exact-head GPT-PM gate pending | STOP/cleanup order and rollback transitions are covered in owned E2E evidence; full E8 crash/resume remains separate and `NOT_RUN` |
| VST-017 | S2 E7: idempotency keys for push, pull request and receipts | Safe synthetic push/pull and recovery selectors pass at exact source/test HEAD `4c1692d61ee04e945fc0ccdd44db71869ccd5468`, including the synthetic timeout/restart retry selector | `docs/sdlc/evidence/s2-safe-functional-exact-4c1692d-20261027.md` records the exact timeout/retry selector: monkeypatched `Popen` raises before a Git child starts; a reopened synthetic store retries the same key. This is not a worker crash/resume or process-kill scenario. The synthetic cross-process storage-lock helper exits normally. Real child kill paths and STOP/rollback restart-resume remain `NOT_RUN`; OS memory/temp-space enforcement, workspace binding, and external direct-writer exclusion remain `NOT_VERIFIED`. GPT-PM exact-head gate remains before PR. |
| VST-018 | S2 E7: circuit breaker with a paused-provider state and manual-override record | implemented; focused tests passed; security/reliability/database reviews found no code-level MAJOR/BLOCKER; full required specialist consensus and exact-head GPT-PM gate pending | Durable breaker state and authenticated episode-bound override; tests and implementation in records 0054 and 0057 |
| VST-019 | S2 E7: startup reconciliation after restart | implemented; focused tests passed; security/reliability/database reviews found no code-level MAJOR/BLOCKER; full required specialist consensus and exact-head GPT-PM gate pending | Lifecycle intent/completion/unknown/reconciliation behavior and restart blocks are in records 0047-0049 and E2E evidence |
| VST-020 | S2 E8: isolated worker bake-off on one crash/resume fixture | partial; full crash/resume, child-kill and mutation acceptance `NOT_RUN` under current policy | At exact source/test HEAD `f0bbac8`, safe WSL lifecycle, operation-recovery, Store, and synthetic-probe subsets passed as enumerated in `s2-permitted-posix-runtime-evidence-f0bbac8-20261026.md`; none proves a real worker crash or process termination. Correlated GPT-PM review `bb6a1039-7e7d-4578-ad43-ac498dc1e259` says mandatory E8 scenarios remain unexecuted. Operator owns any policy decision; Codex maintains exact fixture/evidence; `e2e-runner` executes only after authorization. Next: preserve `NOT_RUN`; if authorization is later granted, run the exact acceptance fixture and return for a new gate. |
| VST-027 | S3.1.1: vendor-neutral worker adapter request/response/state/error contract | M01/M02 fixes committed in `040a3f2`; focused functional/E2E modules rerun 9/9 each at exact repository HEAD `2c4e9fd`; fresh security/reliability reviews at `3283bfa` found no valid BLOCKER/MAJOR/MINOR; GPT-PM APPROVE at `7f1aa35` is scoped to the local adapter | Operator is accountable; Codex is executor. Hook regression is confined to a disposable repository; STOP ordering is limited to one pilot instance/process. Exact rerun evidence is `docs/sdlc/evidence/s3-exact-head-reruns-2c4e9fd.md` (0221); exact GPT-PM response is `docs/sdlc/evidence/s3-gptpm-final-review-7f1aa35.json` (0218); specialist evidence is `docs/sdlc/evidence/s3-specialist-review-3283.md`. Full S3 acceptance remains incomplete. |
| VST-028 | S3.2.1: candidate identity, immutable revision, license, dependency, compatibility, and security audit | GPT-PM conditionally selects Temporal as the sole provisional durable-engine comparator at server `af08a5e` / SDK `a4c2bb3`; read-only audit APPROVED, acquisition NOT APPROVED. | Pinned-source review confirms the server tag's GitHub signature is marked verified, server MIT/Go 1.26.8, and SDK MIT/Python >=3.10 with a Maturin/Rust extension. The 2026-10-27 feature screen records bridge default `tls-ring`, optional `fips`, and source-declared SDK-core/common feature requests; the `uv.lock` remains multi-platform and no S3 target runtime is selected. SDK 1.34.0 release notes document a narrow Server >=1.32.0 behavior, satisfied by pinned server 1.32.1. PyPI now displays verified publishing provenance for all 8 SDK artifacts and links the Linux x86-64 wheel to exact source commit `a4c2bb3`; it has not been independently cryptographically verified because that requires artifact download. Read-only GitHub release metadata for pinned server `v1.32.1` lists Linux amd64 archive digest `4260448d650c1ba7ee7683ff0c93d5c6a1709260e3a7ef543bfa34e06cff6051` and `checksums.txt` digest `2a59896f80e27864c7a817ed54aec9d8f5fd2b82d9a794e09951ec243503f70c`; no asset bytes were acquired or independently verified. The official Go downloads index publishes the full `go1.26.10.linux-amd64.tar.gz` SHA-256 `ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c`; the Go rebuild report marks the archive PASS and shows the matching 16-hex-character prefix. The toolchain was not downloaded or run. The exact pinned server `.goreleaser.yml` declares `cmd/server`, `CGO_ENABLED=0`, Linux amd64 among the targets, a `go mod download` hook, and SHA-256 checksums; `go.mod` declares Go 1.26.8. A read-only GitHub Actions API query found successful amd64, arm64, and Docker jobs in Build and Publish (37665870819) on this exact source commit. The separate All Tests run (37665870783) had failed functional shards for SQLite 0/1/2 and cass_os3 shard 2; the summary status job failed. Read-only logs for the three SQLite shards report 49/52/59 per-shard failures and a 39-minute runner timeout; observed messages include versioning lookup failures, a SQLite length CHECK failure, and context deadlines. Root causes remain unknown; cass_os3 summary and JUnit artifacts were subsequently decoded and both ZIP digests matched GitHub metadata. GPT-PM accepted the supplemental failure-family mapping at source-only scope; see `docs/sdlc/evidence/s3-temporal-cassos3-artifact-detail-20261027.md` and `s3-temporal-cassos3-gptpm-adjudication-20261027.md`. See `s3-temporal-upstream-ci-failure-detail-20261027.md` and `s3-temporal-upstream-ci-artifact-metadata-20261027.md`. The pinned release workflow checks out the release ref and calls GoReleaser release mode; release job 37850182088 reported checkout/build steps successful. This is upstream risk evidence, not local acceptance or independent source-to-archive/checksum binding. See `s3-temporal-server-build-profile-source-screen-20261027.md`. The pinned server go.mod requires `nexus-proto-annotations@v0.1.0` (Go 1.25.4 / protobuf 1.36.1). Its exact tag tree had no conventional license/notice path; the pinned proto and generated Go source showed no inline license header in the inspected file text, while pkg.go.dev reports `NONE_DETECTED`; terms remain UNKNOWN/NOT_VERIFIED. The pinned `vtprotobuf` LICENSE is three-condition BSD-style text but differs from canonical BSD-3-Clause, so its SPDX identifier remains unverified. The recorded metadata table has 223 rows; all 12 package-metadata gaps appear in the source follow-up (10 source-text/template classifications, one BSD-style entry without verified SPDX, one UNKNOWN). See `s3-temporal-go-license-detail-followup-20261027.md`; this is not legal approval. This is partial G02 evidence; server source-to-binary provenance and selected runtime closure remain open. G03 toolchain/lifecycle/network findings are accepted at design level, but exact server/SDK compatibility remains NOT_VERIFIED. Evidence: S3 recommendation, `s3-temporal-narrow-compatibility-audit-20261026.md`, `s3-temporal-sdk-pypi-provenance-20261026.md`, `s3-temporal-sdk-feature-profile-screen-20261027.md`, `s3-temporal-server-release-provenance-screen-20261027.md`, and `s3-go-toolchain-release-provenance-screen-20261027.md`. Owner: Codex continues technical read-only audit; operator owns legal/acquisition decision; GPT-PM architecture gate. Next: do not acquire/build/run; resolve legal notice and full profile/provenance/compatibility evidence before separate acquisition request. |
| VST-029 | S3.3.1: shared deterministic crash/resume, STOP, retry, and budget fixture | At exact canonical HEAD `7816aeb`, designated E2E reruns passed all 9 adapter and all 9 synthetic pilot selectors. They use local synthetic fixtures; process-kill, mutation, external candidate and sandbox selectors were not included. | Accountable owner: operator; executor: Codex. Exact-head commands, environment, durations and limits: `docs/sdlc/evidence/s3-exact-head-safe-rerun-7816aeb.md`. Full S3 acceptance remains incomplete: no real worker STOP/crash recovery, cross-process locking, external candidate comparison or sandbox proof. Keep prohibited process-kill/kill-table scenarios `NOT_RUN`; local fixture locks do not prove cross-process behavior. |
| VST-030 | S3.3.2: sandbox-bound worktree, credentials, diff, and egress proof | pending a fresh run-bound signed probe and applicable gates | Accountable owner: operator; Codex owns the evidence and boundary integration; each worker run requires a fresh probe. The underlying platform/service boundary is not identified, which is a technical fact rather than an ownership gap. |
| VST-031 | S3.4: candidate comparison, residual risk, and operator choice | GPT-PM selected Temporal PROVISIONALLY as the durable-engine comparator; acquisition/execution NOT APPROVED. Static source comparison recorded in `s3-static-candidate-comparison-20261027.md`; no common runtime denominator or final worker choice exists. | The static matrix distinguishes source facts from missing runtime evidence and recommends no final winner. Required comparison remains blocked on S3-G01–G09, S2 acceptance, and same-fixture runtime evidence. Owner: operator for legal/acquisition/final choice; Codex prepares evidence; GPT-PM adjudicates architecture/exact-head gate. Next: finish permitted audit, close legal/build/compatibility and S2 sandbox requirements, then seek separate acquisition/execution decisions; do not assign TOP before results. |
| VST-032 | S4.1: category manifest, selector registry and denominator | Current registry source head `3885d8a`; manifest SHA-256 `7b03dd4a…a4f2dd7a`; 963 selectors, 53 policy `NOT_RUN`, 900 Windows assignments. New timeout-cleanup selector is explicitly excluded. | Accountable owner: operator; registry implementation/maintenance: Codex; E2E execution: designated runner. Next: preserve all 53 policy rows; no timeout/process-kill or other excluded scenarios without policy authorization.
| VST-033 | S4.2: hash-pinned pytest environment and bounded native runner | Exact candidate `05b1845` used CPython 3.14.3 / pytest 9.0.3 on Windows and CPython 3.12.3 / pytest 9.0.3 on Ubuntu 24.04 WSL; normalized dependency-lock SHA `6e23fdd3…45e691`. Root integration/API/regression assigned selectors passed 1/1, 1/1, 2/2 through the installed report-bound helper; all three category reports remain `INCONCLUSIVE` due policy rows. Root preflight is local QA only, not an S2 receipt. | Operator accountable; Codex owns runner and evidence; `e2e-runner` executes. Next: preserve root proof and report artifacts; no stronger authority is claimed. |
| VST-034 | S4.3: functional and Python API selectors | Focused Windows contracts passed 110/110; full Windows functional passed 90/90 and API passed 688/688 with no failures/skips, but API is `INCONCLUSIVE` due 14 policy exclusions. WSL functional passed 90/90; API passed 690/690, also `INCONCLUSIVE` due 14 exclusions. | Operator accountable; functional/e2e test roles own execution. Next: maintain excluded APIs as `NOT_RUN` until the applicable policy gate is changed or waived. |
| VST-035 | S4.4: integration, E2E and regression selectors | Windows assigned counts passed: integration 41/41, E2E 55/55, regression 874/874. WSL user: 46/46, 55/55 and 881/881. Each category is `INCONCLUSIVE` only due its category policy exclusions. Earlier WSL layout failures are diagnostic-only; corrected nested-layout reports are the retained acceptance evidence. | Operator accountable; Codex owns report and evidence reconciliation; `e2e-runner` executes. Next: preserve policy exclusions as `NOT_RUN`; do not run timeout, process-kill/death, mutation or sandbox-dependent selectors unless the applicable gate explicitly permits them. |
| VST-036 | S4.5: synthetic seeded-failure fixture catalog | Exact report-bound candidate `621ddc01`: Windows 3/3 PASS and WSL 3/3 PASS; all three selectors passed at both profiles. Evidence: `docs/sdlc/evidence/s4-report-bound-targeted-621ddc01-20261026.md`; dependency target snapshots verified before/after. | Owner: operator accountable; Codex records evidence; E2E runner executed. Remaining: exact-head GPT-PM gate and overall S4 closure; no seeded product-code defects or prohibited mutation tests were run.
| VST-037 | S4.6: report envelope, hashes, platform matrix and gate compatibility | Windows regression at `bdc8e3b` passed 897/897 expected selectors (1,845 concrete nodes); report is `INCONCLUSIVE` because 53 policy selectors remain `NOT_RUN`. Exact-candidate Windows seeded-failure 3/3, WSL seeded-failure 3/3 and WSL AC-16 1/1 passed at `621ddc01`. | GPT-PM request `77bff3fa-6203-49a0-aa98-84267ba2bcd9` returned correlated `REJECT` at exact HEAD `1e75d5b`: no new source BLOCKER/MAJOR; the unwaived 53 `NOT_RUN` selectors prevent S4 acceptance; AC-16 and AC-17 are accepted only within documented scope. PM identified the missing current Windows raw report row; it is now retained with candidate-bound artifacts and SHA-256 manifest under `docs/sdlc/evidence/qa/s4-regression-20261026-win-bdc8e3b-r1/`. Full reply: `docs/sdlc/evidence/s4-gptpm-final-review-1e75d5b-20261026.md`. Fresh GPT-6 Luna code/security reviews found no BLOCKER/MAJOR (`s4-specialist-reviews-3885d8a-20261026.md`). Owner: Codex packages the evidence and coordinates the next exact-head request; GPT-PM adjudicates; operator is required only for an explicit scoped waiver decision. Next: preserve all 53 policy `NOT_RUN` rows and AC-17 `NOT_VERIFIED`; do not infer waiver from the instruction to keep selectors unrun; keep S4 open pending the waiver or a changed permitted test contract. No push/PR/merge without exact-head approval. |
| VST-038 | S4.2.3 / AC-16: report-bound WSL child identity boundary | **PASS 1/1 at exact candidate `621ddc01`**; UID/GID 997:988, no supplementary groups, no Windows drive mounts; candidate-bound helper version/hash and target before/after are recorded. | Evidence: `docs/sdlc/evidence/s4-report-bound-targeted-621ddc01-20261026.md`. Owner: operator accountable; Codex evidence coordination; E2E runner executed. Remaining: exact-head GPT-PM gate; this one selector does not prove the full S2 sandbox or all S4 matrix profiles.
| VST-040 | S4.2.4 / AC-17: bind external QA dependency contents to locked wheels | **Report-bound pre/post target-content checks PASS** on Windows regression and Windows/WSL targeted rows at candidate `621ddc01`; synthetic persistent post-execution mutation test passed in the Windows regression at code-identical candidate `bdc8e3b`. | `dependency_execution_integrity=NOT_VERIFIED` remains correct: no same-identity change-and-restore during actual pytest was demonstrated. Evidence: S4 regression and targeted report documents. Owner: operator accountable; Codex preserves exact limitation and coordinates any further approved work; GPT-PM adjudicates the gate.
| VST-041 | S5: bounded AEVE static-analysis receipt and exact-head gate | **PREPARED / BLOCKED FROM IMPLEMENTATION.** No S5 source/test implementation. In-scope `tools/` and `tests/` inventory found no AEVE source/analyzer; the `aeve-router` check also returned `NOT_COVERED: AEVE_PROFILE_TRANSPORT_UNAVAILABLE` because no AEVE MCP tool or `aeve` CLI was available. S2 Phase 8 and S4 acceptance remain open. | Dependencies: S2 gate acceptance; S4 exact-head disposition; an authorized in-scope source for AEVE identity/revision/license/interface; available AEVE profile/source transport. Neighboring checkout remains out of scope. Owner: Codex resumes the bounded audit when transport or an in-scope source is available; GPT-PM adjudicates the contract; operator authorizes any external scope expansion. Next: preserve runtime `NOT_RUN`; do not search other checkouts for an alternate transport. |

| VST-021 | Operator: align the workspace `AGENTS.md` model default with ADR-0001 | open (operator-owned) | Outside this repository |
| VST-022 | Operator: align the global contract's list of test-writing agents with ADR-0001 | open (operator-owned) | Outside this repository |
| VST-023 | Operator: re-install the changed roster and skills into `~/.claude` with a snapshot first, then run the global lint | open (operator-owned) | Do after S1 closes |
| VST-024 | Operator decision O-1: keep, generalize or move the private repository names in this public repository | open (operator-owned) | Blueprint section 13.6 |
| VST-025 | S2: mandatory commands per slot listed in the manifest and checked by the gate; pin the test result parser | implemented; focused tests passed; specialist review pending | V2 manifest, trusted parser catalog, and required command validation are in code; focused coverage in record 0056 |
| VST-026 | S2 decision: restrict waivable results to NOT_RUN/INCONCLUSIVE/BLOCKED, or record in ADR_0001 that a FAIL may be waived | decided and implemented; focused tests passed | S2 decision restricts waivers to `NOT_RUN`, `INCONCLUSIVE`, and `BLOCKED`; `FAIL`, `MODIFY`, and `NO_GO` cannot be waived. See `core/DECISION_LOG.md` and record 0055 |

## 2026-10-27 continuation reconciliation (baseline `a583514`)

### S3-G03 follow-up — baseline `20499392f8d78b56214d0d109c9532d50531ac86`

- GPT-PM's correlated full G03 design sweep (`571f620e-852f-4fa5-8a08-93da4fd18b14` / `412fba96-2690-5f55-8bcc-916b95e67975`) returned `MODIFY`: zero BLOCKER, two MAJOR (Go toolchain/provenance contract; full SDK/server lifecycle compatibility), and one MINOR (closed network/provider dependency matrix). Codex corrected the design in change 0404 and isolated the G07 cancellation-method discrepancy in change 0405. GPT-PM subsequently returned correlated `ACCEPT` with zero BLOCKER/MAJOR for exact HEAD `77b319367b575b9f4c0a193e91405df507c886e6` (request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245` / reply `14aedf85-c52b-5d64-b84b-40baf9a99455`). Design acceptance does not resolve artifact provenance, exact-pair runtime, S2/S4, legal/acquisition or candidate comparison. Owner: Codex for remaining source evidence; GPT-PM for architecture gates; operator for reserved legal/acquisition. Next: preserve runtime and independent sprint gates.

- **S2 / VST-020 and Phase 8:** Codex collected only read-only Windows/WSL/firewall configuration snapshots. The designated E2E role audited the latest denominator at source/test HEAD `79155fd` and found no additional non-duplicative safe selector; the audit ran no tests. Five unique regression selectors have seven executions across `dc1741b` and `79155fd`; evidence: `docs/sdlc/evidence/s2-safe-selector-denominator-20261027.md`. Existing evidence remains bound to its recorded heads. Actual Windows/POSIX process containment, full egress, worker identity/workspace controls and persistence remain incomplete or `NOT_VERIFIED`; process-kill, crash/resume and mutation scenarios remain `NOT_RUN`. Phase 8 is still `NOT APPROVED`. Owner: Codex for allowed evidence; operator for any policy exception; GPT-PM for gate adjudication. Next: preserve prohibited cases as `NOT_RUN` and close only with required, authorized evidence.
- **S2 Phase 8 persistent-runner proposal / change 0470:** GPT-PM first returned correlated `MODIFY` (request `0ea02a82-72ba-44dc-a431-213d99bf8192`, reply `62890e6f-0fc5-432c-8bde-ba46be1fad8b`), identifying three MAJOR and one MINOR. Following design corrections and focused reviewer consensus, GPT-PM returned correlated `ACCEPT — DESIGN ONLY` for M01-M03/N01 (request `4c2b6ea5-7de8-4d08-9d24-5c24e38d4b76`, reply `c92f2614-885e-4e44-9160-c23650f80cb9`; job `7e29045d-0ef8-433c-a4ab-f3ed987fe77d`). The acceptance does not approve implementation, provisioning, runtime, tests, or S2. PM added non-blocking N02 for changed-parent wording; Codex updated the failure table and seeks focused verification. The parent deployment/runtime `S2-RF-M01` remains open; restricted scenarios stay `NOT_RUN`. Owner: Codex for implementation and evidence; GPT-PM for focused N02 confirmation and later exact-head gate; operator for later host/key provisioning. Next: verify N02, then proceed only with accepted S2 implementation and preserve all remaining runtime restrictions.
- **S2 persistent runner / change 0473 current working checkpoint:** The designated functional-test-reviewer ran four approved groups: 56 persistent-runner + 32 E1 + 38 E2 + 22 E6 = **148 passed, 0 failed, 0 skipped**. Exact commands, hashes, warning and scope limits are in `docs/sdlc/evidence/s2-adjudicated-runner-regressions-20261028-attempt2.md`. Correlated GPT-PM clarification permits only authenticated PENDING `NO_EXECUTION_PROVEN` or signed `EFFECTS_RESOLVED` from exact `EXECUTION_RESERVED` to justify a receipt gap; separate successor authorization remains required. Focused tests do not establish WSL/systemd egress, Windows/POSIX containment, signed E5, or production integration. `S2-DISPATCH-M01` remains MAJOR/OPEN: no production coordinator call site; Codex must not invent another scheduler, CLI, spool or assignment authority. Prohibited process-kill, crash/recovery, mutation, E8 and policy selectors remain `NOT_RUN`. Owner: Codex for source, committed evidence and permitted system qualification; GPT-PM for exact-head adjudication; operator for actual signed E5/operator credential provisioning. Next: complete docs and commit, perform permitted WSL/system proof via `e2e-runner`, then exact-head specialist reviews and GPT-PM gate; keep S2 NOT APPROVED and do not start S3.
- **S2 change 0472 follow-up corrections:** Fresh database and silent-failure reviews found three MAJOR source gaps: a stale PASS could mask a newer unresolved execution in `evaluate_gate`; `AUTHORITY_CHANGED_BEFORE_COMPLETION` omitted the exact `EXECUTION_RESERVED` predecessor and the outcome matrix admitted insufficiently bound resolutions; and an exception from the post-reservation boundary callback could leave the generation active. Codex corrected these in `tools/vst/store.py` and `tools/vst/execution_grant.py`. The designated functional-test-reviewer added direct regressions; all four approved groups passed 138/138. Evidence: `docs/sdlc/evidence/s2-final-gate-authority-regressions-20261028.md`. Fresh specialist review and exact-head GPT-PM approval remain pending. The operator-reconciliation method is still in-process only; deployed service dispatch/allowlist has no reconciliation operation, and the production coordinator callsite remains absent. Owner: Codex coordinates source/review/integration discovery; GPT-PM adjudicates the existing boundary; operator supplies any signed execution attestation. Next: do not add assignment authority; obtain exact-head review and retain these integration/system gates as open.
- **S3 / VST-028, VST-031:** read-only pinned-source audit added static evidence for file-backed SQLite setup, authorization, exact SDK bootstrap, and the RPC/identity contract. GPT-PM's correlated corrective review `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` / `c9313616-dae6-5e23-9d94-21297ae17ec5` accepted the G07 mapping at design level and closed `G07-CFG-M01` with zero design BLOCKERs/MAJORs. The accepted constraints are a mandatory deny-by-default gateway for every SDK connection/call/retry and complete VST request/response identity binding. A later target-profile review found one MAJOR `S3-PROFILE-M01`; Codex reconciled the target profile and S3 plan section 10 with the accepted G07 topology. GPT-PM's post-fix reply under request `b69437f8-fb54-4075-9fe1-3a08eb75e8c0` returned `ACCEPT`, zero BLOCKER/MAJOR, closing the documentation finding only. The reply repeats the exact request ID and is in the inbound PM Bridge log; the durable job lacks `replyId`/`correlated=true`. Gateway/config implementation, no-bypass/listener controls, S2, G03 provenance/compatibility, legal/acquisition, runtime and candidate comparison remain open. See both target-profile review records. Operator owns legal/acquisition decisions; Codex owns read-only evidence/correction; GPT-PM owns design review. Do not acquire, build, install, or execute Temporal.
- **S4 / VST-032–040:** preserve status `INCONCLUSIVE`. Read-only recheck confirmed the exact previously recorded trusted wheelhouse and six matching SHA-256 values; no installation or tests occurred. This does not satisfy an exact signed operator waiver. All 53 policy selectors remain `NOT_RUN`; AC-17 in-run same-identity change-and-restore remains `NOT_VERIFIED`. Owner: operator for a scoped signature; Codex for accurate accounting. Next: maintain `INCONCLUSIVE` unless the explicit waiver is received; do not execute policy selectors.
- **S5 / VST-041:** no implementation. S2/S4 gates and an identified/authorized AEVE source remain prerequisites; current transport is unavailable. Owner: operator for external scope/source authorization, Codex for bounded audit, GPT-PM for contract. Next: resume only when both gates close and an in-scope source is named or authorized.
- **Downstream acceptance/testing/release:** assigned tests and specialist reviews, exact-head GPT-PM approval, and distinct sprint PR/merge remain conditional on acceptance. Owner: Codex coordinates; functional/E2E roles execute assigned tests; GPT-PM approves the exact head; operator handles merge/deployment authority. No PR or merge occurred.

### S3-G03 / G07 exact cancellation-method amendment — baseline `7f292705824964dc13887f11e7b2626892b43eff`

- The pinned SDK-Core activity client has a `RespondActivityTaskCanceled` call path, while the original GPT-PM-accepted G07 RPC allowlist omitted it. Change 0405 corrected the workflow-ID seed to `(run_id, attempt, epoch)` and proposed one narrowly bounded exception with a Supervisor-signed per-token STOP permit, gateway token ledger, exact Temporal cancellation observation, and non-authoritative acknowledgment. GPT-PM accepted the change 0405 design at exact HEAD `77b319367b575b9f4c0a193e91405df507c886e6` (correlated request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245` / reply `14aedf85-c52b-5d64-b84b-40baf9a99455`), with zero BLOCKER/MAJOR. Change 0406 records its non-blocking terminal-outcome wording clarification. Owner: Codex for documentation and future authorized implementation; GPT-PM for architecture gates. Next: keep G03/G07 implementation and runtime qualification open; do not activate the RPC on design acceptance alone.

- **S3-CI-N01 / VST-028:** **CLOSED — source-only documentation for evidence available at the original review** after focused correlated GPT-PM verification (request `7bbd3f85-a0e3-40bc-8b81-6052dd228a31`, reply `b14bdbb9-b8f3-46a7-8ce5-913bfb5999b2`; exact response: `docs/sdlc/evidence/s3-temporal-upstream-ci-gptpm-verification-20261027.md`). GPT-PM found zero new BLOCKER/MAJOR/MINOR and added INFO `S3-CI-I03`: preserve documentation closure separately from compatibility closure. The build-ID path is outside the fixed-queue/closed-RPC design; SQLite workflow-type length and deadlines require qualification; channel-close behavior remains unresolved. The cass_os3 details unavailable in that original review have since been recovered and separately accepted at source-only scope in the supplemental record below. Upstream All Tests remains FAILED; root cause/reproducibility and the concrete workflow-type name remain unknown/unfrozen; G03/G07 runtime, provenance, and candidate-selection gates remain open. This is not acquisition/runtime approval, S3 acceptance, or exact-head code approval. Owner: Codex maintains evidence and status; GPT-PM adjudicates future transitions; operator retains legal/acquisition/final-choice authority. Next: keep runtime/acquisition closed until their independent prerequisites are met.

- **S3 cass_os3 follow-up / VST-028:** Codex recovered summary and JUnit for failed job `112946311769`; both local SHA-256 digests match GitHub artifact metadata. GPT-PM's correlated supplemental response (request `d09d38ca-76f4-47c2-9bd2-aa2e6d8cd38f`, reply `453a15fe-f0d3-4944-a9ee-f2986a34d3a7`, `correlated=true`) accepted the source-only mapping with zero new BLOCKER/MAJOR/MINOR and INFO `S3-CI-SUP-I01`; see `docs/sdlc/evidence/s3-temporal-cassos3-gptpm-adjudication-20261027.md`. S3-CI-I02 missing-content gap is resolved; the upstream shard remains FAILED and root cause/reproducibility remain UNKNOWN. Callback/schedule exclusions apply only to the current G07 feature profile; versioning/task-forward stays UNRESOLVED; activity timeout/goroutine behavior remains QUALIFICATION_REQUIRED. GPT-PM did not independently inspect the checkout or parse raw archives. Owner: Codex maintains bounded evidence; GPT-PM owns later architecture/gate adjudication; operator retains legal/acquisition/final choice. Next: keep runtime/acquisition closed until independent prerequisites are met.

- **S2 / changes 0475–0477 — versioned worker helper:** GPT-PM accepted design only for `S2-HELPER-M01` (request `b84e73a1-55ac-47b0-87f8-20261028f003`, reply `fc67f0f3-fd09-4c38-81cb-5988d8fe61d9`): full-commit versioned path; root-config path/head/source/binary binding; strict verification; private staging/no-replace; exact idempotent collision handling; preserve old bytes; no fallback/overwrite. Implementation is committed at `d5001797cb94113efd9a8dc26e4a15f2dc130976`. The focused command passed **179, failed 0, skipped 6** on that exact head under CPython 3.14.3; six platform skips remain unverified. The exact-head WSL installer succeeded: versioned helper/runtime/three units matched recorded hashes and legacy helper stayed unchanged; units were not enabled or started. Evidence: `docs/sdlc/evidence/s2-versioned-worker-helper-execution-20261028-attempt5.md` and `docs/sdlc/evidence/s2-versioned-worker-helper-install-d5001797-20261028.md`. Fresh architect, security, reliability, Python, silent-failure and code reviews found no confirmed code BLOCKER/MAJOR; reliability identified a non-blocking need to document revision switching before a later rollout. The repository has no Runner root-config producer; root configuration/credentials, fresh current-run signed E5, service activation/manifest, effective egress and platform containment are not proven. `S2-DISPATCH-M01` remains MAJOR/OPEN; prohibited process-kill, crash/recovery, mutation, E8 and policy selectors remain `NOT_RUN`. Owners: Codex for implementation/evidence/review coordination; GPT-PM for adjudication; operator for actual root-owned configuration/credentials and E5 signature; e2e-runner for permitted runtime evidence. Next: see the final-gate disposition in change 0478 and preserve the remaining blockers; do not start S3.


## 2026-10-28 — S2 Phase 8 final GPT-PM gate (change 0478)

GPT-PM's exact-revision gate returned `NOT APPROVED`: request `7c9fcb10-61cc-4fdd-8292-c2dfbf97ff04`, correlated reply `f347e63d-f691-4561-86d9-95968bb3bb4e`, job `4c4c10e6-9195-44df-a4dc-34a76316417e`. This supersedes the earlier “gate pending” status. `S2-HELPER-M01` is closed only for bounded source and recorded artifact-install scope; zero new source BLOCKER/MAJOR were found. `S2-DISPATCH-M01` remains one blocking MAJOR; persistent service/restart boundary, root-owned configuration/credentials, manifest runtime, current signed E5, effective egress and full platform acceptance are still incomplete. Restricted process-kill, crash/recovery, mutation, E8 and policy selectors stay `NOT_RUN`; no waiver exists. Owners: Codex coordinates the actual existing coordinator and permitted evidence; operator supplies root configuration/credentials and genuine E5 attestation; GPT-PM adjudicates the allowed integration and a later exact-head gate; e2e-runner executes only authorized runtime tests. Next: close each prerequisite or preserve the blocker; do not start S3. Full response and local patch/ancestry verification: `docs/sdlc/evidence/s2-gptpm-final-gate-381435a-20261028.md`.

- **S2 / change 0479 — revision switch documentation:** Closed the reliability review's non-blocking documentation follow-up. The versioned installer refuses a runtime selector for another HEAD and has no upgrade/rollback operation; do not treat retry as an upgrade. Codex owns a future explicit runbook; GPT-PM reviews its deployment contract; operator authorizes privileged switch actions. The runbook must define safe quiescence, mutually consistent artifacts/config, failure and rollback handling, and post-switch verification. This does not alter the final S2 `NOT APPROVED` gate or authorize runtime changes. See `docs/changes/0479-document-s2-revision-switch-boundary.md`.

## 2026-10-28 — S2 safe WSL remainder (change 0480)

The designated `e2e-runner` read-only audit at source/test HEAD `d5001797cb94113efd9a8dc26e4a15f2dc130976` found no additional WSL selector that can run within the current restrictions. No tests were executed. The key/worker, temporary-write, E4 containment and service-dependent candidates remain `NOT_RUN` or blocked for the exact reasons in `docs/sdlc/evidence/s2-safe-wsl-remainder-audit-d500-20261028.md`. The operator owns root Runner configuration/credentials and any required authorization for those scenarios; Codex coordinates; `e2e-runner` runs only newly authorized selectors. S2 stays blocked and S3 does not start.

# S2 coordinator source path — scope decision (change 0481)

The operator delegated the decision but did not identify an external repository/file. Codex
searched only `D:\Repo\Virtual_scrum_team`; no production coordinator call site exists in the
in-scope source/records. Do not search neighboring checkouts and do not create a substitute
assignment authority. `S2-DISPATCH-M01` remains MAJOR/OPEN and the GPT-PM S2 gate remains
NOT APPROVED. Owner: Codex for scoped review; operator for providing an exact external path; GPT-PM
for adjudicating any new architecture. Next: review the named source read-only if a path is
provided; otherwise retain the blocker and keep S3 unstarted. Evidence:
`docs/sdlc/evidence/s2-coordinator-source-scope-decision-20261028.md`.

## S2 Windows containment evidence — change 0482

The designated e2e-runner reviewed the remaining Windows containment selectors at source/test
commit `d5001797cb94113efd9a8dc26e4a15f2dc130976` and found no permitted selector that proves real
containment. The strict-launch test mocks Windows APIs; the real descendant test requires
termination and is prohibited. No tests ran. `VST-013` stays `PARTIAL / NOT_VERIFIED`. Owner:
Codex coordinates; GPT-PM adjudicates an alternative acceptance path; the operator owns any scope
exception. Next: retain the blocker until a genuinely permitted runtime scenario exists. Evidence:
`docs/sdlc/evidence/s2-windows-safe-selector-audit-20261028.md`.

## S2 follow-up after controlled selectors — 2026-10-28 (change 0483)

- POSIX runner capability/timeout behavior remains unverified. Change 0485 found that the exact command/raw output were not retained and the recorded module path for the capability-drop selector is wrong; both selectors remain `NOT_VERIFIED` and `NOT_RUN` for acceptance. The dedicated runner capability profile is also absent. Operator owns any separate operational provisioning; Codex owns evidence correction and coordinates a focused rerun only after a valid safe environment exists.
- `S2-DISPATCH-M01` remains MAJOR/OPEN because no production coordinator call site exists in the in-scope repository. Codex maintains scoped evidence; operator supplies a named external source if review is requested; GPT-PM adjudicates any new architecture.
- S2 remains NOT APPROVED pending complete acceptance and exact-revision GPT-PM adjudication. Evidence: `docs/sdlc/evidence/s2-controlled-runtime-selectors-20261028.md`.

## S2 evidence scope correction — change 0484

Clarified that the 53-selector policy family is S4 acceptance and was not part of the S2 run; no S4 tests or other S4 work occurred in this continuation. Owner: Codex. Next: keep S2 and S4 evidence denominators separate and continue S2 only.

## S2 selector provenance correction — change 0485

The two POSIX runner selector results are `NOT_VERIFIED` and `NOT_RUN` for acceptance: raw invocation/output were not retained, and one logged module path is incorrect. The dedicated capability profile is absent. Owner: Codex for evidence correction and coordination; operator for any separate operational provisioning. Next: retain as open until an exact safe profile and a new e2e-runner invocation produce command/output evidence.

## S2 dispatch architecture decision — change 0486

GPT-PM confirmed `S2-DISPATCH-M01` remains MAJOR/OPEN: keep production dispatch fail-closed until an existing trusted coordinator and authenticated caller are identified. No new scheduler, assignment authority, CLI, queue, spool or validation bypass is authorized. Owner: Codex for source review inside this repo; operator for an exact external source path if it exists; GPT-PM for any future architecture decision. Next: do not inspect neighboring checkouts; review only a specifically named source or preserve the blocker. Evidence: `docs/sdlc/evidence/s2-dispatch-architecture-adjudication-20261028.md`.

## S2 WSL runtime evidence correction — change 0487

The retained WSL E3, identity, and capability/timeout result summaries are `NOT_VERIFIED`; exact command/output are missing and several module-qualified node IDs are wrong. Actual current E3 IDs are in the corrected evidence. Owner: Codex for source/evidence reconciliation; designated e2e-runner for a fresh controlled run. Next: run only the corrected temporary-fixture selectors; leave service/capability-dependent cases `NOT_RUN` until their environment gate exists.

## S2 corrected WSL E3 and identity selectors — change 0488

The corrected six E3 and two synthetic identity selectors now have 12 passing cases after the one harness-only temporary-root permission issue was fixed and rerun. Exact commands, hashes, and the initial 11-pass/1-setup-failure result are preserved in `docs/sdlc/evidence/s2-corrected-wsl-runtime-selectors-20261028.md`. Owner: Codex for evidence; e2e-runner for execution; functional-test-reviewer for coverage. Next: retain capability/service, real E5, production dispatch and E8 gaps as open; no S3 before S2 closes.

## S2 bounded synthetic helper — changes 0490–0503

The safe local helper subtask is closed only for its bounded synthetic scope. At exact
source/test head `0c7c31dc19181b80b6629d6ba0b13b1112eaf6a4`, `e2e-runner` passed 6/6 focused
selectors; Python review found no remaining issue and the relevant security review found no issue.
GPT-PM approved only this local helper subtask (request
`f5ed34f1-34ef-4774-ac47-b4c2ad6b0343`, reply `d708b09a-c960-5a4d-bde4-9370c2e29e81`). Full
E8/S2 remains NOT APPROVED. Evidence and limitations are in
`docs/sdlc/evidence/s2-e8-safe-synthetic-run-0c7c31d-20261028.md` and
`docs/sdlc/evidence/s2-gptpm-synthetic-helper-0c7c31d-20261028.md`.

Still open for S2, in order:

1. `S2-DISPATCH-M01`: no production owner caller or end-to-end coordinator runtime is established.
   The operator confirmed those components do not exist and delegated the bounded coordinator
   implementation to Codex. GPT-PM's later correlated decision accepts a narrow Store-backed
   pub/sub source path: one owner-authenticated intent, Supervisor filtering, AF_UNIX delivery, and
   forwarding the exact grant. It forbids a new assignment authority, task/lease creation, arbitrary
   selection/enumeration, grant signing by the dispatcher, external broker/spool, and automatic
   retry. Source implementation is in progress; tests and independent review have not completed.
   Production dispatch remains disabled. Codex owns source completion and permitted integration;
   GPT-PM owns architecture/final adjudication. The operator has no current action to locate a
   nonexistent external source.
2. Root configuration/current E5: the operator confirmed no current root-owned runner/Supervisor
   configuration, credentials, signed E5, or current sandbox provenance is available. Do not treat
   historical records or unverified key files as current evidence. Codex owns preparation after
   source review, but the latest GPT-PM response does not authorize key generation, migration
   application, or service activation. E5 requires genuine current host inventory and independent
   network-policy attestation; Codex must not impersonate the operator or infer the attestation.
   Any human-only attestation/authorization is owned by the operator only if that gate is reached.
   No secrets are requested in chat.
3. Remaining Windows/POSIX containment and E5/E8 system acceptance must be evidenced. Restricted
   process/crash/kill, STOP, resume/restart, out-of-scope mutation and policy scenarios remain
   `NOT_RUN`; no waiver is inferred. Egress, host isolation, service restart fencing, and any
   unobserved property remain `NOT_VERIFIED`.
4. After in-scope code and evidence are complete, Codex coordinates fresh exact-head specialist
   consensus and GPT-PM final S2 gate. No S3, PR, merge, or deployment before that gate.

Owners: Codex — amendment, implementation, evidence and safe WSL preparation; GPT-PM — architecture
adjudication and final gate; operator — only genuinely independent network-policy attestation or
other human-only authorization if the accepted contract requires it. The operator is not expected
to locate nonexistent external artifacts or send secrets in chat.

## S2 prerequisite absence confirmed — 2026-10-28

The operator clarified that no existing production coordinator/authenticated assignment source is
available and directed Codex to implement one without creating a second assignment authority.
GPT-PM's first review (`dd7175f5-40f3-4714-932d-dc44dca55cc2` / reply
`c064e8f2-eb6d-5945-97e1-f6f6c71d6b92`) returned MODIFY: a local AF_UNIX adapter is acceptable in
principle but a mandatory request-provenance amendment is required before implementation. The
amendment is currently being adjudicated under request `9fcaec9d-c344-4388-b79a-1392fb6f4cb4`;
the PM Bridge wait is uncertain and no correlated final reply is recorded yet. Root service config
and runtime are absent from the WSL distribution, while role-separated key files and historical
E5 records from earlier heads exist; see `docs/sdlc/evidence/s2-wsl-provisioning-baseline-20261028.md`.
Current-head E5 remains unproven. Do not ask the operator to find an external coordinator or send
secrets. Keep dispatch disabled and S3 unstarted until S2 formally closes.

## S2 pub/sub implementation queue — supersedes “awaiting coordinator source” — 2026-10-28

The operator confirmed the coordinator and authenticated assignment source do not exist and
delegated their bounded creation to Codex. Do not ask the operator for a nonexistent path. GPT-PM's
later correlated decision ACCEPTS the narrow source design: request
`274a8f94-9438-4f16-8dd4-98a8daf64b37`, reply `67045970-e83f-538b-866e-ba97e9d269ec`. It permits one
owner-authenticated Store intent event and a Supervisor-filtered AF_UNIX subscription. It does not
authorize a new assignment authority, task/lease creation, grant signing by the dispatcher, external
broker/spool, automatic retry, migration application, runtime activation, or deployment.

Current source progress: Store event and schema-v6 migration gate; owner-bound Supervisor submit,
filtered subscription and exact grant-forwarding operations; a dedicated dispatcher service/unit;
installer and schema contract documentation. The source and project records received a code-reviewer
and database-reviewer pass. Code-reviewer found and rechecked a fix for cursor advancement after
transient Store errors; no actionable BLOCKER/MAJOR remains in that reviewed scope. Database-reviewer
found no BLOCKER/MAJOR and noted a MINOR O(n) full-history grant lookup; no workload evidence supports
optimization yet. The production owner caller is still absent, so the data path is source-prepared
but not end-to-end integrated. `S2-DISPATCH-M01` remains MAJOR/OPEN; no runtime pass is claimed.
Schema upgrade remains opt-in and unapplied. The initial focused attempt at source HEAD
`ec9aefe9444003a65af81f27eaf813b250e25c10` failed during collection with a syntax error; zero tests
executed. Codex fixed it, code-reviewer re-reviewed, and functional-test-reviewer passed the
corrected focused suite at source HEAD `61bfe643e52362fbe4c680ade2c3cb150997dedc`: **20 passed,
0 failed, 0 skipped, 1 pytest-asyncio deprecation warning**. Exact command and contract map:
`docs/sdlc/evidence/s2-pubsub-functional-run-ec9aefe-20261028.md`. Production E2E is still
`NOT_RUN` because the required config/credentials, current E5 and active runtime are absent; exact
reason: `docs/sdlc/evidence/s2-pubsub-e2e-triage-ec9aefe-20261028.md`.

Ordered closure:

1. Codex preserves the focused 20/20 local source result; functional coverage is complete for this
   bounded contract. E2E remains `NOT_RUN` until its provisioned runtime prerequisites exist.
   Prohibited crash/process-kill/mutation/policy scenarios remain `NOT_RUN`.
2. Codex prepares a root-owned authenticated owner caller path that does not add assignment
   authority; GPT-PM adjudicates any material architecture change. Until such a caller is deployed,
   the coordinator cannot claim production integration.
3. GPT-PM owns a separately scoped authorization decision for any root-owned key/config
   provisioning. Codex owns preparing a non-secret config contract and migration code; the v6
   migration separately requires independent database review and authorization before application.
   The operator owns any genuine human network-policy attestation. Runtime stays disabled until
   those gates and fresh E5 provenance exist.
4. After exact-head tests/reviews, GPT-PM adjudicates final S2 acceptance. S3 stays unstarted until
   S2 closes.

Backlog MINOR: grant lookup verifies/scans full append-only history per request ID. Codex owns any
later bounded optimization, only if measurements show material cost; the next step is to capture
representative Store sizes/lookup timing after source tests and runtime evidence are available.

Backlog MINOR: the dispatcher intentionally uses `Restart=no` and stops on any unhandled delivery
error. This preserves fail-stop behavior for ambiguous outcomes but means a transient pre-launch
Supervisor outage also requires manual recovery. The service journal and claim-state inspection
sequence are documented in `tools/vst/systemd/README.md`; a production recovery runbook and observed
alerting remain unverified. Codex owns the runbook; e2e-runner may evidence it only after separately
authorized runtime setup. Keep automatic retries disabled for ambiguous claims.

## S2 bounded Pub/Sub source gate — accepted; runtime gate still open (2026-10-28)

GPT-PM request `b2d8f20e-4eb0-4a4c-98ec-13c1c9437279` approved the attached Store-backed Pub/Sub
source/test scope with 0 confirmed BLOCKER/MAJOR findings. Codex verified the attached implementation
and test files against Git blobs at HEAD `673479dccc0f37de7d723ede275c46a8f4b4595c`; the recorded
focused test file hash matches. Evidence: `docs/sdlc/evidence/s2-pubsub-gpt-pm-source-review-20261028.md`.
This closes the bounded source-review item only. It does not close `S2-DISPATCH-M01` or S2 and is
not runtime approval. Full acceptance still depends on an authenticated production owner caller,
separately reviewed/authorized schema-v6 application, root-owned runtime config and credentials,
current signed E5 and sandbox provenance, active services, POSIX identity/cgroup proof, and remaining
Windows/POSIX acceptance. Restricted process/crash/mutation/policy scenarios stay `NOT_RUN` absent
authorization. Owner: Codex for source/evidence coordination; GPT-PM for gate adjudication; operator
for genuinely privileged provisioning or human attestation. Do not start S3.
