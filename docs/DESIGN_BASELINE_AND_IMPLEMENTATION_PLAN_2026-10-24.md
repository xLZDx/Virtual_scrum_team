# Design baseline 1.0 and implementation plan

**Date:** 2026-10-24  
**Status:** BASELINE FOR THE S1 PILOT, set by the operator's instruction of 2026-10-24 ("assemble the final design and implementation plan, commit, push, start development"). Not independently reviewed. Runtime, autonomous pilot beyond S1 and production or release remain NO-GO.  
**Supersedes for planning purposes:** the S0-S9 roadmap in section 10 of the master blueprint. The blueprint, the dossier and ADR-0001 stay as the reasoning record.

## 1. What this baseline is

The operator accepted the architecture direction and asked for development to start. The review rounds (six read-only reviewers, a self-verification and an external verification) all returned MODIFY DESIGN because the core properties were stated but had no mechanism. This baseline keeps the architecture and turns every open blocker into a concrete S1 work item. It does not claim the blockers are closed.

Kept architecture: this repository (Virtual Scrum Team) is the single SDLC authority; isolated workers never approve their own output; native focused tests by the two test agents are the evidence; AEVE is an optional bounded evidence input; PM Bridge only consumes accepted sprint closure; operator-only actions stay operator-only.

## 2. Binding decisions in force

| Decision | Source |
|---|---|
| Only `functional-test-reviewer` and `e2e-runner` author and run required tests; `tdd-guide` and `performance-optimizer` are advisory | ADR-0001 (operator answer 2026-10-24) |
| Reviewer and test-agent models: Sonnet 5.5 medium or GPT-5.6 Luna low/medium; no silent substitution; no GPT-5.6 Sol; Opus never automatic | ADR-0001, operator global contract |
| No CI; no mutation runs; no red/green loop | ADR-0001 |
| A mandatory `NOT_RUN` never gives an ordinary approval; `APPROVED_WITH_WAIVER` needs a named operator record | ADR-0001 |
| Code of a sprint is finished before tests run; one pull request per sprint; push or merge of the sprint pull request only after the final independent approval on the exact head | operator workflow |
| Git text is English; the repository is public | repository `AGENTS.md` |

## 3. Baseline design decisions taken now (proposals accepted by the start instruction; reversible until S1 closes)

| ID | Decision | Why | Reversal condition |
|---|---|---|---|
| BD-1 | **State authority:** a local SQLite database (write-ahead logging, single writer process, compare-and-swap epoch) is the one authoritative store for phase state, attempts, leases and receipts. `docs/sdlc/STATE.md` becomes a read-only generated view. Resolves finding VEO-R2-B01 once `sdlc-orchestrator/SKILL.md:12` is updated in the same sprint | Stdlib only, atomic, no new service; matches the review's fencing requirement | Failed crash/restart drills, or a decision to adopt a durable workflow engine after the bake-off |
| BD-2 | **Receipt trust root (MVP):** receipts are produced by a runner process outside the worker's working directory and signed with HMAC-SHA256 using a key file readable only by the runner account. The gate recomputes the HMAC and recomputes artifact hashes itself. Known limit: HMAC proves origin within the machine's trust boundary, not that tests were honest; honesty comes from the typed success conditions in BD-3 | Smallest mechanism that stops a worker forging or replaying receipts | A requirement for third-party verifiability (then asymmetric signatures) |
| BD-3 | **Typed receipts with closed enums and default-deny:** `TestRunReceipt` (collected ids equal expected ids, none skipped or xfail, every exit code 0, count above zero), `StaticAnalysisReceipt` (coverage FULL, PARTIAL or NOT_COVERED; PARTIAL never satisfies a required id), `IndependentReviewReceipt` (signed verdict, reviewer principal different from author), `DocumentationReceipt` (its stated check). Unknown field, unknown enum value or missing field is rejected | Fixes the false-green paths found by the review | New receipt type required by a later sprint |
| BD-4 | **Gate verdict function:** a pure function. Required evidence slots come from the manifest and the phase policy, never from the decision author. Verdict set: `APPROVE`, `APPROVED_WITH_WAIVER`, `MODIFY`, `NO_GO`. Any missing, malformed, stale-head, stale-epoch or unlisted-but-present receipt gives a non-approval | R-2 | — |
| BD-5 | **Failures are never erased:** receipts are append-only with attempt number and previous-receipt hash; a lease expiry without a receipt writes `INCONCLUSIVE(WORKER_LOST)`; retries stop at the cap with `BLOCKED(RETRY_EXHAUSTED)` | R-4 | — |
| BD-6 | **Limits are enforced by the store:** a slot table acquired in the same transaction as the lease enforces the concurrency limit (initially 1 AI slot for S1 drills, configurable up to the operator-stated 5); the budget ledger is a table decremented by metered usage. A worker over budget is marked `BLOCKED(budget)` by the supervisor | R-6 | — |
| BD-7 | **Public-repository hygiene:** URLs of private repositories are withheld from this public document set; names of components may remain. Evidence artifacts are stored outside the repository tree | VEO-R2-M03 | — |

## 4. Implementation plan

Sprint S1 goal: prove the control-plane core on a synthetic story with no real project, no external service and no provider call. All code is Python 3 standard library only, deterministic, and lives under `tools/vst/`; schemas under `tools/vst/schemas/`. One branch `s1-control-plane-core`, one pull request.

| Epic | Content | Acceptance (proved by the test agents' focused tests) |
|---|---|---|
| E1 Contracts | JSON schemas and a strict validator for TaskManifest and the four receipt types plus GateDecision; closed enums; no defaults | Missing field, unknown enum, extra field, zero collected, skipped required test, PARTIAL coverage are all rejected |
| E2 Gate | Pure verdict function per BD-4 | Required receipt deleted gives non-approval; unlisted FAIL receipt gives non-approval; stale head gives non-approval; waiver without operator record gives non-approval |
| E3 State store | SQLite store: epoch compare-and-swap, attempts, lease and slot tables, append-only hash-chained receipts and event log; renderer for the `STATE.md` view | Two writers on one story: exactly one holds the epoch; stale epoch write rejected; broken hash chain detected |
| E4 Runner and signing | Runner that executes a command list, records argv, exit codes and artifact hashes, and signs the receipt with a key outside the worker directory | Forged unsigned receipt rejected; receipt replayed against another head or task rejected; modified artifact rejected |
| E5 Vertical slice harness | Synthetic story driven through supervisor, worker stub, runner and gate, with injected worker death before receipt, a zombie late write, a stale head and a retry after FAIL | Worker death gives `INCONCLUSIVE(WORKER_LOST)` and a blocked gate; zombie write rejected; stale head blocks; the earlier FAIL stays visible after a later PASS |
| E6 Process alignment | Update `sdlc-orchestrator/SKILL.md` step 1 and `governance/DEFINITION_OF_DONE.md` to match BD-1; change record, decision log and lessons log; regenerate the document registry | Static grep finds one state-authority statement across `SKILL.md`, DoD, blueprint |

Order inside the sprint (operator workflow): all E1-E6 code and documents are written first by `implementation-engineer`; then `functional-test-reviewer` writes and runs focused tests per epic and again for the whole set; then relevant read-only reviewers (silent-failure-hunter, security-reviewer, reliability-reviewer, architect) on the exact head; fixes; then the final independent review of the exact head; then push and the one pull request.

Sprint S2 (after S1 is accepted): replace the worker stub by a real isolated worker candidate in a sandbox specification written first (WSL distribution or VM with Windows drive automount and interoperability disabled, default-deny egress, per-run scoped credentials, deterministic diff gate), with a bake-off on one crash/resume fixture. Sprint S3 and later follow the blueprint only after the S1 evidence exists.

## 5. Out of scope for S1

Real projects (any pilot repository), real worker tools, external AI or provider calls, CI, mutation runs, production or release, global configuration changes, history rewriting.

## 6. Open items that stay with the operator

- Align the workspace `AGENTS.md` model default and the global contract's list of test-writing agents with ADR-0001.
- Re-install the changed roster and skill into `~/.claude/` and run the global lint after S1 closes (needs a snapshot first).
- Decide whether component names of private repositories may stay in this public repository (URLs are already withheld).
- Independent review of the S1 head on an allowed model before the sprint pull request.
