# Sprint S3 plan: vendor-neutral worker pilot

Status: **IN-REPOSITORY S3 CODE, FOCUSED FUNCTIONAL/E2E TESTS, AND FINAL CODE/SECURITY/RELIABILITY REVIEWS PASS; FULL CANDIDATE/SANDBOX ACCEPTANCE INCOMPLETE**. The STOP cleanup diagnostic functional module passed 16 cases on source HEAD `2a8c175` (change 0098); the S3 worker-pilot E2E module passed 8 cases on repository HEAD `71169f7e004160f9bc0781de2dce1568bbaa8e49` (change 0099; product/test source remains `2a8c175`). Fresh code, security, and reliability reviews at HEAD `86f59dc911f9a9ddbef029b2e9f57b6b7052bb92` found no open findings. A bilingual checkpoint is in `reports/S3_WORKER_PILOT_2026-10-25.ru.html` and `.html` (change 0100). The worktree contained one unrelated untracked S2 evidence file before and after the E2E run; it was preserved and not staged. Candidate comparison remains incomplete. `docs/sdlc/STATE.md` remains the phase authority for S2 Phase 8 GPT-PM gate, which is pending. No external candidate is acquired, installed, cloned, or executed; each sandbox-bound run still needs a fresh signed probe.

Baseline reference: S2 source head `dc95915018b80f498d5cf775363712fb915fe04e` on branch `s2-isolated-worker-sandbox`. The functional recovery-module rerun at source `dc959` recorded 4 passed / 0 skipped (record 0085). The focused Windows runner/store E2E run recorded 80 passed / 14 skipped and the POSIX flock test recorded 1 passed under `vst-runner` in the selected Ubuntu-24.04 WSL2 (record 0083). Earlier E2E results at `ed531` include 3 Windows snapshot-identity failures; the following source fix `dc959` passed the focused suite. Fresh security and reliability reviews found no source blocker; the database review likewise found no MAJOR, while confirming that abrupt-crash child cleanup and filesystem quotas remain unverified. Earlier S2 Windows/WSL evidence is recorded at source head `280e2d0a613a0b70252c13ce7afe85f22734f7d1`; it is evidence for that head only. The selected dedicated Ubuntu-24.04 WSL2 environment has per-run E5 evidence, not persistent deployment proof. S2 retains explicit `NOT_RUN` criteria for process-kill/kill-table, post-start overflow cleanup, Windows Job Object nesting, full POSIX containment, and complete E8 crash/resume. OS memory and per-run filesystem quotas, source-workspace binding, and external-writer exclusion are `NOT_VERIFIED`; production qualification requires those environmental limits. Reconcile the final S2 state before S3 worker execution; no S2 result is inherited as an S3 acceptance pass.

### Continuation status reconciliation — 2026-10-26

The historical S2 references above remain evidence for their named source heads. The latest S2 cleanup-fix code/test candidate is `9ce27f0d9837e2d302872df0b878ebcaba15b513` on `s4-canonical-continuation`; the S2 phase record includes 66 lifecycle passes (5 skipped, 4 deselected), 60 contract/diffgate passes, and fresh security/reliability/silent-failure/architecture review outcomes. The exact-head GPT-PM gate is still pending; therefore S3 worker execution must still satisfy section 2.1 and must not infer S2 approval from these tests or source reviews. Current shared safe S3 regression evidence remains bound to `2eec051`: adapter 8 passed / 1 resume case deselected, pilot 3 passed. S3 STOP/resume and sandbox-boundary scenarios remain `NOT_RUN`; the current POSIX WSL reviewer-boundary selector also could not run because the canonical checkout is not exposed under `/mnt/d`. See `docs/sdlc/evidence/s2-s3-current-source-regression-5ae495c.md` and `docs/sdlc/evidence/s2-exact-head-review-9ce27f0.md`.

Sources: `docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md` section 1; `docs/UNIFIED_ENGINEERING_ORGANIZATION_MASTER_BLUEPRINT_2026-10-23.md` sections 6, 10, 13.2-13.4; `docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md` section 4; S2 interfaces and prerequisites in `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`; ADR-0001 (`docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`). Where the blueprint names an OpenHands/Aider comparison, this S3 plan follows the later explicit continuation: BMad Loop, a hand-written worker, and one durable engine (Temporal provisionally).

## 1. Goal and scope

Run one synthetic story through one isolated story adapter on the S2 sandbox. Compare three worker implementations on the same fixture and evidence contract:

1. BMad Loop.
2. A hand-written worker loop.
3. Temporal as the provisional durable-engine candidate from the project's in-scope candidate set.

The comparison is about recovery and safety behavior, not an overall product ranking. The adapter interface remains vendor-neutral, and the VST control plane remains the only phase, acceptance, and receipt authority. No candidate may approve its own work or write authoritative VST state.

Out of scope: more than one story, concurrency/scale, live repositories or customer data, push/merge, unattended workers, candidate auto-fallback, public-network access, unreviewed candidate acquisition, CI, mutation runs, process-kill/kill-table tests, and a “TOP” designation before all comparison evidence and the operator decision exist. Follow ADR-0001: skipped or unavailable tests are `NOT_RUN`, never a pass; no mutation or CI checks are run.

## 2. Entry conditions and dependencies

### 2.1 S2 acceptance dependency

Before S3 implementation starts, reconcile S2 against its Definition of Done and exact final code head. In particular, verify the signed gate/store contracts, retry and lease fencing, STOP behavior, deterministic diff gate, reviewer credential boundary, signer separation, external anchor, and startup reconciliation. Record every unavailable scenario as `NOT_RUN` with its exact environment/dependency.

### 2.2 Sandbox dependency

The operator-provisioned S2 sandbox is required for all worker comparison runs. The sandbox must have a fresh passing probe tied to the run id, default-deny egress, no host path outside the run directory, no container-engine socket, non-root worker identity, and no worker signing key or signer IPC access. Do not simulate this evidence. If the sandbox is unavailable, finish documentation and platform-independent fixture work, and mark sandbox-dependent execution `NOT_RUN`.

### 2.3 Candidate acquisition gate

The candidates are **not yet identified by immutable revision**. Before acquiring any candidate, create an audit record for each one containing:

- exact upstream identity (canonical repository/project and owner);
- immutable commit SHA, with tag/branch recorded only as descriptive metadata;
- license identifier and the in-scope license text/source reviewed;
- dependency and install/build inputs, including hash-lock feasibility;
- sandbox/runtime compatibility, required network/provider access, and data/credential behavior;
- security review of permissions, auto-commit/push behavior, external calls, and repository-content prompt injection;
- approval/authorization to acquire the pinned source into a quarantined evaluation location.

For Temporal, record the identity, exact revision, license, and compatibility from primary project artifacts before acquisition. At plan time these details are **UNKNOWN / NOT_VERIFIED**. Do not clone, install, update, or execute any candidate while preparing this plan. If audit prerequisites cannot be satisfied, that candidate is `NOT_RUN`; do not substitute a different durable engine silently.

## 3. Vendor-neutral adapter contract

One isolated `StoryWorkerAdapter` translates the stable VST run request into the selected backend and returns typed status/evidence. Backend-specific task state must not become a second VST state authority.

| Operation | Input | Observable result and invariant |
|---|---|---|
| `start` | run id, story manifest digest, candidate id/revision, sandbox run id, epoch/fence, budget, allowed paths | One attempt is created with a stable operation/idempotency key. Duplicate identical start returns the same attempt. A conflicting payload under that key is rejected. No start occurs if stopped, unreconciled, over budget, or sandbox probe is stale/failed. |
| `status` | run id and attempt id | Returns a typed state (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `STOPPED`, `INCONCLUSIVE`, `BLOCKED`) plus bounded progress/evidence references. It does not turn missing evidence into success. |
| `stop` | run id, attempt id, reason, authorized actor | Idempotently records STOP and prevents later writes/receipts from the stopped epoch. The adapter returns only after stop state is observable or reports timeout/partial stop as `INCONCLUSIVE`; it does not claim cleanup succeeded without evidence. |
| `resume` | run id, prior attempt id, current epoch/fence, remaining budget | Creates a new attempt/epoch after VST reconciliation. It binds to the prior receipt chain and current candidate revision. It cannot reuse an earlier epoch receipt, repeat completed side effects, or resume a stopped attempt without an allowed transition. |

All calls are bounded by explicit time/cost budgets and carry `run_id`, `attempt_id`, `candidate_id`, `candidate_revision`, manifest digest, epoch/fence, invocation id, and sandbox run id. Adapter errors are typed and visible; provider/model fallback is prohibited unless separately recorded as an authorized manual override and never represented as an ordinary approval.

## 4. Epics and stories

### E1 — Adapter contract and single synthetic story

**S3.1.1** Define and validate the vendor-neutral `start/status/stop/resume` request, response, state, timeout, and error contract.

**S3.1.2** Connect exactly one synthetic story to the adapter and S2 lease/receipt/gate path. Keep task inputs and repository contents synthetic and treat repository text as untrusted.

Acceptance:

- AC-1: All three worker implementations use the same adapter contract and fixture input; no backend-specific branch bypasses VST receipt validation.
- AC-2: `start` and `resume` are idempotent for the same key/payload and reject same-key/different-payload reuse.
- AC-3: VST remains the sole owner of phase state, attempt fencing, required receipt set, and final verdict; the worker cannot self-approve.
- AC-4: An unavailable status, malformed response, or unsupported backend state remains non-approving and diagnosable.

### E2 — Candidate identity and controlled execution

**S3.2.1** Complete identity/revision/license/dependency/compatibility/security audit before candidate acquisition.

**S3.2.2** Run each candidate only inside the probed S2 sandbox, with identical fixture, allowed paths, budget rules, stop conditions, and evidence collection.

Acceptance:

- AC-5: Every executed run is bound to an audited immutable candidate SHA and sandbox run id.
- AC-6: Missing identity, pin, license evidence, audit, or sandbox probe prevents acquisition/start and is recorded as `NOT_RUN` or `BLOCKED` with cause.
- AC-7: No worker receives signing keys, signer IPC, push credentials, store write credentials, or unrestricted host paths.
- AC-8: External egress is denied; only the explicitly permitted sandbox-local loopback canary may succeed.

### E3 — Shared crash/resume and STOP fixture

**S3.3.1** Implement a deterministic synthetic repository fixture with checkpointed interruption inside the worker loop. The interruption is an application-level injected crash/restart at a named checkpoint; do not use prohibited process-kill or kill-table runs.

**S3.3.2** Exercise STOP, retry, resume, budget, worktree isolation, and evidence-chain transitions on the same initial repository state for all candidates.

Acceptance:

- AC-9: A crash after an edit but before receipt leaves no false PASS; restart reconciles state and resumes only with a new fenced attempt.
- AC-10: STOP is idempotent; after STOP, writes from the stopped attempt and late receipts cannot change the accepted candidate state.
- AC-11: A failed attempt remains visible after a later PASS; retry count never exceeds the manifest cap; duplicate operation keys do not repeat effects.
- AC-12: Budget zero starts no worker; exact-cap work may complete only under the documented boundary; any operation that would exceed budget is blocked and recorded without exceeding the cap.
- AC-13: Candidate edits are confined to the run worktree and manifest allowlist; worktrees for candidates/attempts are isolated and cleanup/retention outcome is recorded.
- AC-14: An attempted write outside the allowed paths, including a protected hook/config/manifest path, fails the diff gate and cannot yield APPROVE.
- AC-15: External egress attempt fails closed; no public-network target is used as a positive probe.

## 5. Requirements-to-acceptance and test coverage map

Only `functional-test-reviewer` and `e2e-runner` author and run required S3 tests. This map defines required outcomes; it does not create test code. Use the cheapest layer that exercises the actual seam. For backend recovery, sandbox credentials, filesystem isolation, and external calls, focused integration/E2E coverage is required because lower-level unit tests cannot prove those boundaries.

| Source requirement | S3 ACs | Required falsifying scenario / oracle | Cheapest proving layer | State/dependency |
|---|---|---|---|---|
| Continuation S3: one isolated adapter; vendor-neutral start/status/stop/resume | AC-1..4 | Same fixture through each adapter operation; malformed/unknown state and timeout remain non-approving; duplicate start/resume is idempotent; key collision with changed payload is rejected; STOP cleanup return/exception stays non-approving, fenced and safely diagnosable | Contract unit tests plus Store-backed adapter integration | Local synthetic suite passed at exact test HEAD `2a8c175` (16 passed, 0 skipped); evidence `docs/sdlc/evidence/s3-stop-cleanup-functional-2a8c175.md`. Candidate and sandbox runtime remain gated; exact-head specialist review is pending |
| Blueprint 13.2 R-1/R-2: signed runner receipts and total gate | AC-3, AC-4, AC-9..11 | Forged PASS, missing required receipt, stale epoch receipt, modified-after-hash artifact, partial acceptance, unlisted receipt all fail gate | Gate integration with real signed records | S2 source/test evidence is recorded through `9ce27f0`, but S2 exact-head GPT-PM gate is pending and platform runtime gaps remain `NOT_RUN`/`NOT_VERIFIED`; S3 entry remains blocked until section 2.1 is reconciled |
| Blueprint 13.2 R-3/R-4: durable state, fencing, append-only attempt chain | AC-9..11 | Crash at each named checkpoint, stale/zombie late receipt, broken previous-receipt hash, lease expiry, restart reconciliation before new lease | Store/adapter integration with deterministic checkpoint injection | Requires proven S2 store, anchor and reconciliation; no process-kill test |
| Blueprint 13.2 R-5 / ADR-0001 | AC-4, AC-6 | Every unavailable/prohibited scenario stays `NOT_RUN`; no CI, mutation, seeded-failure, or kill-table run is claimed as PASS | Evidence-record validation/static audit | Policy dependency; ADR-0001 applies |
| Blueprint 13.2 R-6: infrastructure-enforced budget and kill path | AC-12 | Budget 0, exact cap, one unit over; assert starts, operation counts, ledger totals, terminal state, and no excess spend. Because kill-table tests are prohibited, do not claim a real kill action was runtime-proven | Deterministic budget unit/integration test; signed ledger assertion | The actual kill path remains `NOT_RUN` under current restriction; no unattended mode |
| S2 E5 / blueprint 13.4: sandbox preflight, default-deny egress and least privilege | AC-5..8, AC-15 | Fresh run-bound probe required; stale/missing probe blocks; worker key/signer/store access denied; blocked external target denied; local loopback canary succeeds; no host path/socket leak | Real sandbox E2E and signed probe inventory | Requires operator-provisioned S2 sandbox; no fake inventory |
| S2 E6 / blueprint 13.4: diff gate before review and read-only reviewer | AC-7, AC-13, AC-14 | Out-of-scope, traversal, symlink, rename-to-hook, CI/config/lockfile/manifest/install-script changes rejected; reviewer cannot write worktree/store | Diff-gate unit plus sandbox identity integration | Requires verified S2 E6 and actual read-only credential boundary |
| S2 E7: STOP, idempotency, circuit breaker and startup reconciliation | AC-2, AC-9..11 | Stop/retry/resume transitions; repeated operation key causes no second effect; conflicting payload fails; breaker open prevents start and silent fallback; reconciliation precedes lease | State-machine unit and store/adapter integration | Requires verified S2 E7 contracts; any uncovered transition remains open |
| Candidate audit requirements in this plan | AC-5..8 | Missing immutable SHA/license/compatibility/security record prevents acquisition; attempt to start an unaudited or mismatched revision is rejected | Static audit plus adapter start contract test | Candidate acquisition remains prohibited until separately authorized after audit |
| Same-fixture comparison and no “TOP” before evidence | AC-1, AC-5, AC-9..15 | For each candidate, preserve identical fixture seed, checkpoints, budget, scope, and environment; compare outcome/evidence completeness; missing candidate result is `NOT_RUN`; no ranking label until all required rows are reviewed | Deterministic comparison record and independent review | Temporal revision/license/compatibility currently UNKNOWN; candidate set not acquired |

### Scenario denominator

For **each** of the three candidates, record these outcomes on the same fixture. An unavailable candidate or environment is a named `NOT_RUN`, not removed from the denominator:

1. Clean start, status progression, completion, and signed gate outcome.
2. Application-level crash at each declared checkpoint, restart, reconciliation, and resume.
3. STOP before start, during execution, after edit/before receipt, duplicate STOP, and late write/receipt.
4. Retry after failure, retry-cap boundary, duplicate operation key, and key reuse with changed payload.
5. Budget at zero, exactly at cap, and one unit over cap.
6. Allowed worktree edit; outside-scope write; protected hook/config/manifest/install-script change; rename into a blocked path; symlink change.
7. Worker attempt to read signer/key/store/push credentials or write outside the scoped worktree.
8. Blocked external egress and permitted sandbox-local loopback canary.
9. Fresh versus stale/missing sandbox probe and exact candidate revision mismatch.
10. Evidence chain integrity: missing receipt, stale epoch receipt, invalid signature, modified artifact, and prior failed attempt retained after a later pass.

Each result records candidate id + commit SHA, fixture version/seed, sandbox probe/run id, manifest hash, attempt/epoch, exact command or adapter request, expected and observed result, receipt references, test ID, test command, interpreter, HEAD, dirty note, and whether it ran or is `NOT_RUN` with exact cause.

## 6. Candidate comparison and decision rule

The comparison table has one row per scenario and candidate, including `NOT_RUN` rows. Compare recovery correctness, STOP behavior, retry/budget enforcement, worktree confinement, unauthorized access attempts, egress, evidence completeness, restart determinism, and operator-visible failure modes. Do not combine missing evidence with success and do not score candidates on speed alone.

No candidate receives a “TOP” label until:

1. all candidates have immutable identity/revision and completed license/compatibility/security audits;
2. each required scenario is either runtime-proven or explicitly `NOT_RUN` with its dependency;
3. independent reviewers reconcile the comparison and open findings;
4. the operator records a decision on the chosen worker and accepted residual gaps.

The durable engine is Temporal for this plan, provisionally. If the pin, license or compatibility audit fails, report the exact blocker; do not silently choose a replacement. The operator owns candidate acquisition authorization and final worker choice; implementation, functional-test and E2E roles execute only after S3 is accepted and its entry gates are met.

## 7. Definition of Ready

- **Vendor-neutral contract/code preparation:** the S2 control-plane interfaces are inspected; candidate state cannot authorize a lease, receipt, or verdict. This slice may be implemented without acquiring a candidate or running a worker.
- **In-repository synthetic integration:** one story and deterministic application-level checkpoints are specified, including inputs, expected state transitions, idempotency keys, and allowed paths. This may use only the hand-written in-repository worker and does not imply sandbox runtime acceptance.
- **Candidate adapters and comparison:** S2 exact-head acceptance is reviewed and reconciled; immutable candidate identity, license, compatibility, dependency and security audit records are complete; operator acquisition authorization is explicit. No unpinned upstream is introduced.
- **Sandbox-bound worker execution:** the operator-provisioned dedicated sandbox is available and a fresh signed probe passes for the intended run. Earlier probes are not reused.
- Adapter contract, S2 state/gate integration points, test ownership, budget semantics, STOP table and evidence format are reviewed for the relevant slice.
- Test scenarios map to every applicable S3 AC and have valid and invalid fixtures. Test agents confirm the focused command set without running it before coding is complete.

## 8. Definition of Done

- One story adapter provides vendor-neutral `start/status/stop/resume`; VST remains the sole state and acceptance authority.
- The same fixture and scenario denominator has been run for the three candidates, or every unavailable row is explicitly `NOT_RUN` with exact cause.
- Crash/resume, STOP, retries, budget zero/exact/over, worktree confinement, unauthorized writes, and egress outcomes satisfy AC-9..15; no weak/partial run is described as a pass.
- Candidate immutable identity, commit, license, compatibility and security audit are linked to all run evidence.
- Diff gate and reviewer isolation reject unauthorized writes and access; sandbox probe is fresh and tied to each run.
- Complete focused functional tests run after each epic and once again on the exact final committed head by the authorized test agents. Evidence includes test IDs, exact commands, interpreter, count, environment, HEAD, dirty note, result, and `NOT_RUN` limitations.
- Relevant specialist reviews have no open valid BLOCKER/MAJOR; final exact-head approval is recorded before push/PR under project process.
- The comparison and explicit operator decision are recorded. No “TOP” label appears before these gates pass.
- Change record, decision/lessons logs, backlog, state, document registry and sprint report are updated as required by the project workflow.

## 9. Backlog and ownership

Canonical S3 backlog grouping. These items are registered while local contract code is prepared; candidate and sandbox gates still govern dependent execution:

| Proposed item | Scope | Accountable / technical ownership | Entry/dependency |
|---|---|---|---|
| S3-A / VST-027 | Vendor-neutral single-story adapter, in-repository synthetic integration, and idempotent operations | Operator is accountable for the delegated sprint; Codex executes. Canonical service owner is UNKNOWN. | S2 control-plane contract inspection; code preparation does not start worker execution |
| S3-B / VST-028 | Candidate identity, immutable revision, license, dependency, compatibility, and security audits | Operator owns explicit acquisition authorization; Codex performs the read-only audit; technical audit service owner is UNKNOWN. | Complete before any candidate acquisition |
| S3-C / VST-029 | Shared deterministic crash/resume, STOP, retry, and budget fixture | Operator is accountable; Codex implements product fixture; functional-test-reviewer and e2e-runner own required test authorship/execution. These are roles, not named people. | Accepted requirements and code completion; process-kill scenarios remain separately gated |
| S3-D / VST-030 | Sandbox-bound worktree, credentials, diff, and egress proof | Operator is accountable for sandbox provisioning; Codex binds a fresh probe to each authorized run; exact platform/service owner is UNKNOWN. | Verified sandbox and fresh signed probe for each run |
| S3-E / VST-031 | Candidate comparison, residual risk, and operator choice | Operator owns the final choice; reviewers supply evidence, not the decision. | Complete denominator, candidate gates, and exact-head review |

The matching IDs are tracked in `core/BACKLOG.md`. The operator is the accountable task owner under delegated work; Codex is the executor. No named human/service technical owner is asserted where project records do not identify one.

## 10. Open dependencies and decisions

| Dependency | Current status at S3 plan preparation | Owner and next action |
|---|---|---|
| S2 exact-head test/review evidence | Historical source `dc959` outcomes remain as recorded in 0083/0085. Latest cleanup code/test candidate `9ce27f0` has exact committed lifecycle and contract/diffgate outcomes plus fresh security/reliability/silent-failure/architecture reviews; exact S2 GPT-PM gate remains pending and platform/system limits remain `NOT_RUN`/`NOT_VERIFIED`. | Operator is accountable; Codex reconciles the phase record and exact residuals. GPT-PM owns the S2 gate decision. S3 worker execution waits for the recorded S2 entry decision. |
| Dedicated S2 sandbox and fresh probe | Dedicated Ubuntu-24.04 WSL2 selected and provisioned; per-run probe/attestation passed for the recorded E5 correlation. Persistent deployment is not claimed. A fresh probe is required for each S3 run. | Operator is accountable; Codex uses the provisioned WSL2 and records a fresh run-bound signed probe before each S3 worker execution |
| BMad Loop candidate identity/pin/license/compatibility | Historical public metadata was first recorded at `v0.10.0`, then updated to `v0.11.0`; latest official release rechecked 2026-10-25 is `v0.13.2`, exact tag SHA `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`, MIT, Python >=3.11, with PyYAML, regex and platform-specific psutil dependencies. Public docs still describe an early open beta, coding-agent subprocesses, test/lint execution, and optional local commits/worktree merges. Full source/security/dependency/license-notice and sandbox compatibility audit remains `NOT_VERIFIED`; no acquisition authorization recorded. See change 0168. | Codex may continue read-only public/source audit; operator owns explicit acquisition authorization. Do not clone/install until audit and authorization are recorded |
| Temporal candidate identity/pin/license/compatibility | Preliminary public metadata verified: `temporalio/temporal`, release `v1.32.1`, tag/commit `af08a5e5f2dd40f545f2afac7780daaa6987001e`, MIT, Go 1.26.8, large server dependency graph. Suitability as a bounded worker engine, runtime footprint, security and sandbox compatibility remain `NOT_VERIFIED`; no acquisition authorization recorded. | Codex can finish read-only public audit; operator owns explicit acquisition authorization. Do not clone/install until both are recorded |
| Hand-written comparator revision | The local vendor-neutral adapter and synthetic worker are already implemented in `tools/vst/worker_adapter.py`, `tools/vst/pilot.py`, and `tools/vst/slice.py`; change 0088 records their initial scope and later changes 0215-0217 record fixes/reviews. S2 entry-gate reconciliation and full S3 runtime comparison remain pending. | Do not duplicate the existing common adapter. After S2 reconciliation, Codex should implement only a concrete, source-evidenced local gap; record the exact S3 candidate revision before any comparison. |
| Budget kill-action runtime proof | `NOT_RUN` under current no-kill-table restriction | Do not enable unattended mode; any later authorization/policy change must be recorded before a real kill-path test |
| S3 technical service owner | Not identified in the inspected backlog/plan sources | Remains UNKNOWN; continue with role-based ownership and operator accountability |

## 11. Ordered next steps

1. Close the pending S2 exact-head GPT-PM gate against the committed evidence at `9ce27f0`; retain every prohibited/unavailable scenario as `NOT_RUN` and do not begin S3 worker execution before the gate's recorded outcome.
2. Before each S3 worker run, collect a fresh signed probe in the selected dedicated WSL2 environment and bind it to the run. The previously recorded E5 probe is not reused for S3.
3. Complete candidate identity, immutable SHA, license, dependency, compatibility and security audits before any candidate acquisition.
4. The S3 cleanup-diagnostic review/fix is already recorded in changes 0215-0217. Rerun the relevant specialist review only if its source changes; preserve candidate, comparison, sandbox-run, timeout-cleanup, and prohibited-crash criteria as gated or `NOT_RUN` until their dependencies are met.
5. After specialist findings are resolved, request the exact-head GPT-PM gate; do not push/merge before its correlated approval. Keep candidate acquisition and final worker choice behind their separate audit and operator gates.
6. Record the comparison and operator's worker choice. Publish no “TOP” label without complete evidence and that decision.

## 12. Public candidate source audit (no acquisition)

This section records candidate release-pin/license/dependency metadata checked on 2026-10-24, preliminary pinned-source behavior review updated on 2026-10-25, and current official pins rechecked on 2026-10-25. It is not a security/compatibility approval and does not authorize clone, install, or execution.

| Candidate | Canonical upstream and immutable pin | License/toolchain/dependency evidence | Audit state and next owner |
|---|---|---|---|
| BMad Loop | `https://github.com/bmad-code-org/bmad-loop`, release `v0.13.2` at immutable commit `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60` | Pinned `pyproject.toml`: MIT, Python >=3.11, direct dependencies; pinned `uv.lock` exists. Full transitive license inventory and built-artifact provenance remain open. Official pinned [`pyproject.toml`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/pyproject.toml), [`uv.lock`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/uv.lock), and [`LICENSE`](https://github.com/bmad-code-org/bmad-loop/blob/4a5c45390ff46c0fc28d316004ffe0ed7c8eea60/LICENSE) | Pinned source review found that project-declared shell hooks execute via the BMad process with inherited environment/project worktree, with no trust allowlist; Python plugins are enabled by project-local name-only policy, project plugins override same-name built-ins, and manifests have no digest/signature pin. A repo contributor able to control these files can conditionally run code as the BMad process identity; impact depends on that identity. This is an intentional execution surface and conditional risk, not an exploit or proven sandbox escape. No OS egress/credential boundary or runtime containment was proven. No source was acquired or executed. Keep acquisition gated pending full dependency/license/artifact audit, fresh S2 probe, and explicit operator authorization. Owner: Codex for read-only audit; operator for acquisition authorization/final choice |
| Temporal server | `https://github.com/temporalio/temporal`, release `v1.32.1`, tag resolves to `af08a5e5f2dd40f545f2afac7780daaa6987001e` | Tag `LICENSE`: MIT; `go.mod` requires Go 1.26.8 and declares cloud storage/SDK, telemetry, gRPC, and SQLite dependencies among a large server dependency graph. Official [`LICENSE`](https://github.com/temporalio/temporal/blob/v1.32.1/LICENSE), [`go.mod`](https://github.com/temporalio/temporal/blob/v1.32.1/go.mod), and [`README`](https://github.com/temporalio/temporal/blob/v1.32.1/README.md) | README describes a separate server that executes application-provided workflows and requires workers/SDKs. Fit as a minimal single-story backend, service topology, footprint, security and sandbox compatibility remain `NOT_VERIFIED`; runtime and dependency-closure audit are still required. Do not acquire pending audit and operator authorization. Owner: Codex for read-only audit; operator for explicit acquisition authorization |
| Temporal Python SDK worker | `https://github.com/temporalio/sdk-python`, release `1.34.0`, lightweight tag resolves via read-only `git ls-remote` to `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` | Pinned `pyproject.toml` and `LICENSE`: MIT, Python >=3.10; direct runtime requirements include `nexus-rpc`, `protobuf`, and typing packages. Source builds require `uv`, Rust, Protobuf compiler and the SDK Core submodule; gitlink `temporalio/bridge/sdk-core` resolves to SDK Rust `e163abd6dc19040064986a63c8b8cf4756ffd320`, whose workspace/license declares MIT. The repository `uv.lock` and bridge `Cargo.lock` pin resolutions but do not prove selected runtime closure/license inventory. PyPI 1.34.0 JSON lists wheel hashes with `provenance=false`, so source-linked build provenance is unverified. Official pinned [`release`](https://github.com/temporalio/sdk-python/releases/tag/1.34.0), [`pyproject.toml`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/pyproject.toml), [`LICENSE`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/LICENSE), [`README`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/README.md), [`bridge Cargo.lock`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.lock), and [`SDK Core LICENSE`](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/LICENSE.txt) | README confirms a separate Python `Client` and `Worker`, so SDK 1.34.0 is a plausible application-worker component, not a replacement for the server. Its 1.34.0 release notes state one feature needs server 1.32.0 or later; server 1.32.1 meets that feature-specific minimum, but no general compatibility matrix was found. The workflow sandbox is explicitly best-effort determinism tooling, not OS isolation. Release notes include a replay-grouping fix matching the mechanism in upstream issue #1881 (reported for SDK 1.32.0/1.33.0); the issue-specific reproduction has not been run on this pin. Transitive license closure, a minimal runtime profile, source-linked wheel provenance/reproducible build, runtime behavior and sandbox fit remain `NOT_VERIFIED`/`NOT_RUN`. Reviewer: security-reviewer, GPT-6 Luna, medium effort (changes 0201, 0203). Do not acquire pending residual audit and operator authorization. Owner: Codex for read-only audit; operator for explicit acquisition authorization |
| Hand-written worker | In-repository candidate: `tools/vst/slice.py` at source head `dc95915018b80f498d5cf775363712fb915fe04e` | Same repo license/requirements apply; no additional external package is introduced by the current worker harness | Source identity known; S2 is functionally reviewed with residuals, while S3 adapter integration and full scenario review remain pending. Owner: Codex |

The selected source pins above came from official release pages and read-only `git ls-remote` tag resolution; behavior notes came from pinned source, release notes and configuration. On 2026-10-25 the latest BMad release tag resolved to `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`; the Temporal server pin is `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e`, paired for feasibility review with Python SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`. No candidate source was cloned or installed. This read-only audit is not an approval: source-level permissions, prompt injection, dependency/license closure, offline operation, service topology and sandbox compatibility still require review. The operator-owned acquisition gate remains open. See changes 0168–0201.

### Temporal server and Python SDK source review — 2026-10-25

The bounded read-only source audit paired official Temporal server `v1.32.1` (`af08a5e5f2dd40f545f2afac7780daaa6987001e`) with official Python SDK `1.34.0` (`a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`). The reviewer was `security-reviewer`, GPT-6 Luna, medium effort (change 0201). The server repository and Python SDK both declare MIT. The server README and SDK README show separate server and application-worker components; the SDK examples connect a client and run a worker with registered workflows/activities. This is a possible worker/server topology, not a completed adapter design or deployment approval.

The SDK declares Python >=3.10 and direct requirements including `nexus-rpc`, `protobuf` and typing packages. Building from source requires `uv`, Rust, Protobuf compiler and the SDK Core submodule; the exact Core gitlink is SDK Rust `e163abd6dc19040064986a63c8b8cf4756ffd320`, whose root license declares MIT. The pinned `uv.lock` and bridge `Cargo.lock` pin package resolutions, but full third-party license closure and the minimal production runtime profile remain unverified. SDK 1.34.0 release notes state that a feature using the server-provided first execution run ID needs server 1.32.0 or later; server 1.32.1 satisfies only that explicitly stated feature minimum. The reviewed sources did not provide a general server/SDK compatibility matrix.

The SDK README calls its workflow sandbox best-effort determinism tooling and documents ways to relax or disable it. It does not provide OS process, filesystem, credential, signer-IPC or egress isolation. S2 controls therefore remain mandatory. Upstream SDK issue #1881 reported local-activity result regrouping during replay on SDK 1.32.0/1.33.0; SDK 1.34.0 release notes describe a replay-grouping fix matching that mechanism, but do not name the issue or prove its exact reproducer passes on this pin. Keep same-version replay acceptance `NOT_RUN` pending the authorized scenario.

An additional bounded artifact/dependency audit resolved the SDK Core gitlink at the Python SDK pin: `temporalio/bridge/sdk-core` points to `temporalio/sdk-rust` commit `e163abd6dc19040064986a63c8b8cf4756ffd320`. The pinned SDK Rust workspace manifest and `LICENSE.txt` declare MIT. The Python SDK repository has both `temporalio/bridge/Cargo.lock` and `uv.lock`; these pin package resolutions but do not constitute a complete third-party license inventory or establish a minimal production runtime profile. The Temporal Python 1.34.0 PyPI JSON lists platform wheels and SHA-256 digests, but the inspected artifacts report `provenance=false`; hashes alone identify artifacts and do not bind them to this source commit/build. For the server, `go.mod` and `go.sum` declare/resolve dependencies, but a comprehensive third-party license inventory or SBOM was not found in this bounded tree review.

No Temporal source was cloned, installed, built, executed or tested. No reachable exploit in the proposed deployment was established by this source-only review. Residuals: transitive dependency/license closure for the selected SDK runtime/Rust and server Go profiles; wheel-to-source build provenance or reproducibility; general server/SDK compatibility; deployment listener/auth/egress settings; adapter and service topology; process/filesystem/credential containment; and runtime replay verification. Operator remains accountable for candidate acquisition authorization and final choice; Codex is audit executor. The technical sandbox/service owner is not identified in inspected project records.

### BMad Loop source review — 2026-10-25

The code-level read-only review was performed against official source at immutable commit `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60` (GPT-6 Luna security-reviewer, medium effort; change 0169). `src/bmad_loop/engine.py` describes a deterministic orchestration loop ending in orchestrator commit; `workspace.py` documents direct-project default (`isolation = none`) and branch/worktree creation plus merge-back in worktree mode. `verify.py` runs configured commands through the orchestrator, while `plugins/bus.py` executes declarative shell hooks. `plugins/registry.py` gates in-process Python plugins on enablement and checks module-path containment before import; enabled plugin code still runs in-process. `adapters/profile.py` allows project-local TOML profile overlays and out-of-tree entry-point adapters. `childrun.py` documents a race where a process reparented between descendant harvests can escape observation; `process_host.py` states the native Windows branch is not exercised.

The expanded code-level review used the official GitHub tree/API and immutable source commit `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60` (security-reviewer, GPT-6 Luna, medium effort; change 0204). It resolved `plugins/trust.py`, `loader.py`, `manifest.py`, `bus.py`, `policy.py`, `registry.py`, and the plugin model. Declarative project plugin manifests are discovered under `.bmad-loop/plugins`; the manifest may carry a shell `cmd`, and the bus runs it as a child process using the BMad process identity, inherited environment, and project worktree. This is executable project input by design.

For Python plugins, `policy.load()` reads project-scoped `.bmad-loop/policy.toml`; the enablement check is plugin-name membership, the manifest has no content digest/signature, and project plugin discovery has precedence including same-name overrides. The loader and registry then import/instantiate the enabled Python module. Thus a repository contributor able to control these project files can cause shell-hook or Python plugin code to run with the BMad process identity when the corresponding lifecycle is reached. Impact is bounded by that identity's accessible files, environment, credentials and OS policy. This is a conditional reachable execution risk, not evidence of an exploit or sandbox escape. No code was run.

The pinned trust implementation is name/project-policy based, not immutable content approval. No OS-enforced egress or credential boundary was established by these source files. No candidate source was cloned, installed or executed. Remaining: third-party dependency license closure and built-artifact provenance; a fresh S2 probe and runtime proof for process, filesystem, credential, signer-IPC and egress boundaries. Treat manifests and repository text as untrusted; any authorized trial must run inside the fresh S2 sandbox without signing keys or signer IPC. Operator remains accountable for acquisition authorization and final choice; Codex is source-audit executor. The technical sandbox/service owner is not identified in project records. Change 0204 supersedes the earlier statement in change 0169 that plugin trust/loader paths remained unresolved.

### Hypothetical Python base-profile license screen — 2026-10-25

A read-only follow-up (security-reviewer, GPT-6 Luna, medium effort; change 0206) used pinned lockfiles and package metadata to map a deliberately hypothetical Linux x86-64 / Python 3.12 / base-dependency profile. This is a bounded inventory aid, not a candidate selection, acquisition, or runtime approval.

| Candidate profile | Locked Python packages and license evidence | Scope limits |
|---|---|---|
| BMad Loop 0.13.2, Linux base | `bmad-loop` 0.13.2 — MIT from pinned `pyproject.toml`; PyYAML 6.0.3 — MIT from pinned `uv.lock` and upstream project; `regex` 2026.7.19 — `Apache-2.0 AND CNRI-Python` from exact-version PyPI metadata | Excludes Windows-only `psutil`, `tui`, `opencode`, and non-Linux extras. Hatchling is a separate build dependency; the coding-agent/provider executable invoked by BMad is outside this lock and remains unidentified. |
| Temporal Python SDK 1.34.0, Python 3.12 base | `temporalio` 1.34.0 — MIT from pinned `pyproject.toml`; `nexus-rpc` 1.4.0 — MIT; `protobuf` 6.33.6 — BSD-3-Clause; `types-protobuf` 7.34.1.20260518 — Apache-2.0 type stubs; `typing-extensions` 4.16.0 — PSF-2.0, from pinned `uv.lock` and exact-version PyPI metadata | `python-dateutil` and `six` are guarded by Python `<3.11` and excluded in this hypothetical profile. The compiled Rust bridge, its submodule crates, and the complete wheel contents/license notices are not closed. |

The locks establish package versions and dependency edges, not installed contents, a chosen trial profile, or complete source-build license notice closure. The Temporal server Go module graph remains unmapped. PyPI reports `provenance=false` for inspected SDK wheels; listed hashes do not bind them to the pinned source build. General server/SDK compatibility, the exact replay scenario, and all deployment/runtime boundaries remain open or `NOT_RUN`. No packages or candidate sources were downloaded or executed. The operator owns candidate choice and any acquisition authorization; the technical sandbox/service owner remains unidentified. See change 0206.

### Temporal Rust bridge and server Go module metadata screen — 2026-10-25

A follow-up read only opened the pinned raw manifests/lockfiles (security-reviewer, GPT-6 Luna, medium effort; change 0207). It resolved a bounded package/version subset but did not close third-party licensing:

- The Python SDK bridge manifest selects `tls-ring` by default. The pinned manifest/lock identify 11 direct registry crates: `anyhow 1.0.104`, `async-trait 0.1.91`, `futures 0.3.33`, `prost 0.14.4`, `pyo3 0.29.0`, `pyo3-async-runtimes 0.29.0`, `pythonize 0.29.0`, `tokio 1.53.1`, `tokio-rustls 0.26.4`, `tokio-stream 0.1.19`, and `tonic 0.14.6`. Their license metadata is `UNKNOWN` in this audit: the lock records versions, checksums and edges but contains no license fields, and no authoritative exact-version record was retrieved. The pinned `Cargo.lock` is 3,553 lines and includes optional/target/build entries, so these are not total graph counts or a minimal-runtime closure. The `fips` / `aws-lc` dependency path is optional and excluded from the default `tls-ring` profile.
- The pinned Temporal server `go.mod` / `go.sum` provide 15 illustrative direct module/version entries, including `cloud.google.com/go/storage 1.62.1`, AWS SDK v2 core/config/credentials/S3, `go-jose/v4 4.1.4`, MySQL driver `1.9.3`, `gocql 1.7.0`, `pgx/v5 5.10.0`, `lib/pq 1.12.3`, Prometheus client `1.21.0`, Temporal API `1.63.5` and SDK `1.44.0`, gRPC `1.83.2`, and protobuf `1.36.11`. License metadata is `UNKNOWN` for this subset: module versions and hashes are not licenses. The 239-line `go.mod` and 716-line `go.sum` cover a broad graph but do not identify a runtime-only build-tag/profile; no total graph count is asserted.

The minimum follow-up evidence is authoritative version-specific license/notice data for each resolved third-party component plus a feature/target/build-resolved inventory (for example, a pinned SBOM). Candidate selection remains open, and no package source was downloaded or executed. See change 0207.

### Versioned license metadata follow-up — 2026-10-25

Change 0208 supersedes the direct-dependency license `UNKNOWN` statements in change 0207 for the entries below. The audit used the official crates.io version API and pkg.go.dev's exact-version license pages; it did not download package archives.

| Rust crate version | crates.io license field |
|---|---|
| `anyhow 1.0.104` | `MIT OR Apache-2.0` |
| `async-trait 0.1.91` | `MIT OR Apache-2.0` |
| `futures 0.3.33` | `MIT OR Apache-2.0` |
| `prost 0.14.4` | `Apache-2.0` |
| `pyo3 0.29.0` | `MIT OR Apache-2.0` |
| `pyo3-async-runtimes 0.29.0` | `Apache-2.0` |
| `pythonize 0.29.0` | `MIT` |
| `tokio 1.53.1` | `MIT` |
| `tokio-rustls 0.26.4` | `MIT OR Apache-2.0` |
| `tokio-stream 0.1.19` | `MIT` |
| `tonic 0.14.6` | `MIT` |

The full pinned bridge `Cargo.lock` scan resolved 362 registry package/version entries (349 unique crate names). All 362 had a crates.io license value and their API SHA-256 checksum matched the exact lock entry. The count includes optional, target-specific, and build/test dependencies; it is a lock-wide license metadata inventory, not proof of the contents of one selected runtime artifact. Repeated attempts to serialize the full package list were rate-limited, so only the aggregate result and direct package table are retained here; a machine-readable 362-row artifact was not produced.

The 15 illustrative Temporal server Go modules from change 0207 have versioned license pages: cloud storage `Apache-2.0`; AWS SDK v2 core/config/credentials/S3 `Apache-2.0`; go-jose `Apache-2.0`; MySQL driver `MPL-2.0`; gocql `Apache-2.0`; pgx and lib/pq `MIT`; Prometheus client `Apache-2.0`; Temporal API/SDK `MIT`; gRPC `Apache-2.0`; protobuf `BSD-3-Clause`. A controlled exact-version scan of all 223 Go `go.mod` module/version rows returned 211 pkg.go.dev pages with license sections, one page explicitly saying `License: None detected` (`github.com/nexus-rpc/nexus-proto-annotations@v0.1.0`), and 11 exact-version page URLs with HTTP 404; there were no HTTP 429 responses on this rerun. All 11 pkg.go.dev 404 rows were then checked against raw `LICENSE`/`LICENSE.md` files at the commit suffix recorded in each pinned pseudo-version: ten have exact-revision license files with MIT/BSD/Apache text; `vtprotobuf` has three-condition BSD-style text but does not exactly match SPDX BSD-3-Clause text. Classifications and exact URLs are in `docs/sdlc/evidence/s3-temporal-server-go-license-source-followup-2026-10-25.tsv`. The single `None detected` row remains `UNKNOWN`/`NOT_VERIFIED`, not proof of no license; its exact `v0.1.0` GitHub tree resolves to `e558d6edaf84e280dddfc87b5b8ce1662f66ac8b` and contains no `LICENSE`, `LICENSE.md`, `LICENCE`, `COPYING`, `NOTICE`, or `COPYRIGHT` path. No named license maintainer is identified in this repository. See full pkg.go.dev data in `s3-temporal-server-go-license-metadata-2026-10-25.tsv`; exact pkg.go.dev metadata grouping (preserving comma-delimited page values) is `Apache-2.0` 87, `Apache-2.0, BSD-3-Clause` 14, `Apache-2.0, BSD-3-Clause, MIT` 2, `Apache-2.0, MIT` 2, `BSD-2-Clause` 2, `BSD-2-Clause-Views` 1, `BSD-2-Clause, ISC` 1, `BSD-3-Clause` 31, `ISC` 1, `MIT` 68, `MPL-2.0` 2. Current upstream `main` license and a missing exact tag `v0.1.0/LICENSE` do not establish a version license. The 223 rows include indirect/build/test dependencies and do not identify a selected runtime profile or complete legal notice closure. Evidence: exact-version page `https://pkg.go.dev/github.com/nexus-rpc/nexus-proto-annotations@v0.1.0?tab=licenses`, upstream tag LICENSE path `https://github.com/nexus-rpc/nexus-proto-annotations/blob/v0.1.0/LICENSE` (404), exact tree API URL in the supplemental TSV, changes 0211–0214.
