# Sprint S3 plan: vendor-neutral worker pilot

Status: **PREPARED; NOT STARTED**. This document is a next-sprint plan only. It authorizes no candidate acquisition, installation, cloning, sandbox provisioning, production use, or test execution.

Baseline reference: S2 code commit `3af18a1bc7f87ba9f31cd86e98888f2aecf58922` on branch `s2-isolated-worker-sandbox`, observed 2026-10-24. The current S2 test and platform evidence is **NOT_VERIFIED** at this code commit. No S2 result is inherited as an S3 acceptance pass. Reconcile the S2 evidence directory and exact committed head before S3 starts.

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
| Continuation S3: one isolated adapter; vendor-neutral start/status/stop/resume | AC-1..4 | Same fixture through each adapter operation; malformed/unknown state and timeout remain non-approving; duplicate start/resume is idempotent; key collision with changed payload is rejected | Contract unit tests plus adapter integration | Planned; S2 control-plane acceptance must be verified first |
| Blueprint 13.2 R-1/R-2: signed runner receipts and total gate | AC-3, AC-4, AC-9..11 | Forged PASS, missing required receipt, stale epoch receipt, modified-after-hash artifact, partial acceptance, unlisted receipt all fail gate | Gate integration with real signed records | Dependency: S2 exact-head gate/store evidence is `NOT_VERIFIED` at commit `3af18a1` |
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

- S2 exact-head acceptance evidence has been reviewed and reconciled; code presence alone is insufficient.
- Operator has provisioned the dedicated sandbox and a fresh probe passes on the intended environment.
- Candidate identity, immutable commit, license, compatibility, dependency and security audit records exist for BMad Loop, the hand-written loop implementation, and Temporal. Candidate acquisition has explicit authorization; no unpinned upstream is introduced.
- One synthetic story and deterministic crash/resume fixture are specified, including checkpoints, inputs, expected state transitions, idempotency keys, and allowed paths.
- Adapter contract, S2 state/gate integration points, test ownership, budget semantics, STOP table and evidence format are reviewed.
- Test scenarios map to every S3 AC and have valid and invalid fixtures. Test agents confirm the focused command set without running it before coding is complete.

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

Proposed S3 backlog grouping; add these items to the canonical backlog when S3 is formally started, after confirming the S2 state:

| Proposed item | Scope | Accountable / technical ownership | Entry/dependency |
|---|---|---|---|
| S3-A / VST-027 | Vendor-neutral single-story adapter and idempotent operations | Operator is accountable for the delegated sprint; implementation-engineer role executes. Canonical service owner is not identified in current backlog and remains UNKNOWN. | Verified S2 control-plane contracts |
| S3-B / VST-028 | Candidate identity, immutable revision, license, dependency and compatibility audits | Operator owns candidate acquisition authorization; technical audit owner is UNKNOWN in canonical records. | Must complete before acquisition |
| S3-C / VST-029 | Shared deterministic crash/resume, STOP, retry and budget fixture | Functional-test-reviewer and e2e-runner own required test authorship/execution; implementation-engineer owns product changes. These are roles, not named people. | Accepted requirements and code completion |
| S3-D / VST-030 | Sandbox-bound worktree, credentials, diff and egress proof | Operator owns sandbox provisioning and external candidate acquisition authorization; exact platform/service owner is UNKNOWN. | Verified S2 sandbox and fresh probe |
| S3-E / VST-031 | Candidate comparison, residual risk and operator choice | Operator owns the final choice; reviewers supply evidence, not the decision. | Complete denominator and exact-head review |

These are proposed identifiers, not current backlog entries. The operator is the accountable task owner under delegated work; Codex prepares this document. No named human/service technical owner is asserted where project records do not identify one.

## 10. Open dependencies and decisions

| Dependency | Current status at S3 plan preparation | Owner and next action |
|---|---|---|
| S2 exact-head test/review evidence | `NOT_VERIFIED` at code commit `3af18a1bc7f87ba9f31cd86e98888f2aecf58922` | S2 coordinator and authorized test/review roles must complete and reconcile before S3 starts |
| Dedicated S2 sandbox and fresh probe | Not evidenced as provisioned in the S2 plan; actual current provisioning state is `UNKNOWN` | Operator provisions/authorizes the isolated environment; then run and record the signed preflight |
| BMad Loop candidate identity/pin/license/compatibility | `NOT_VERIFIED`; S0 tool matrix says no local acquisition and license unknown | Audit exact source and immutable revision before any authorized acquisition |
| Temporal candidate identity/pin/license/compatibility | `NOT_VERIFIED`; selected provisionally from in-scope candidate set only | Audit primary candidate artifacts; no clone/install until audit and authorization |
| Hand-written comparator revision | Not yet implemented; exact code revision is `UNKNOWN` | S3 implementation records its own exact commit and dependency inventory |
| Budget kill-action runtime proof | `NOT_RUN` under current no-kill-table restriction | Do not enable unattended mode; any later authorization/policy change must be recorded before a real kill-path test |
| S3 technical service owner | Not identified in the inspected backlog/plan sources | Remains UNKNOWN; continue with role-based ownership and operator accountability |

## 11. Ordered next steps

1. Finish S2 functional/E2E runs, exact-head review, and evidence reconciliation; keep all unverified cases `NOT_RUN`.
2. Verify operator provisioning and the S2 sandbox probe; this is a hard dependency for worker runs.
3. Complete candidate identity, immutable SHA, license, dependency, compatibility and security audits before any candidate acquisition.
4. On formal S3 start, register the proposed backlog stories, confirm ownership/dependencies, and implement the adapter and fixture before starting tests.
5. After all S3 code is complete, let the authorized test agents run the mapped focused suite by epic and on the exact final head; then run specialist reviews and the final approval gate.
6. Record the comparison and operator's worker choice. Publish no “TOP” label without complete evidence and that decision.
