# Independent Review Dossier — Unified Virtual Engineering Organization

**Date:** 2026-10-23  
**Status:** REVIEW CANDIDATE — NOT APPROVED, NOT INSTALLED, NOT OPERATING. Devil's-advocate agent review done 2026-10-23: MODIFY DESIGN (section 11)  
**Scope:** Adversarial architecture, process and implementation-readiness review of the proposed integration of the Virtual Scrum Team, global role/skill catalog, AEVE, execution harnesses, CI/test infrastructure, Windows gateway and sprint closure service.  
**Related:** `UNIFIED_ENGINEERING_ORGANIZATION_MASTER_BLUEPRINT_2026-10-23.md`; earlier `FULL_TEAM_EXPANSION_PLAN_2026-10-23.md`.

## 1. Purpose, review boundary and evidence classification

This dossier records **why choices were proposed**, not just the selected architecture. It preserves rejected, deferred and insufficiently researched alternatives, material contradictions, safety boundaries, tests required to falsify assumptions, and exact sources for a future reviewer. It does **not** claim an independent review was actually performed.

Evidence tags in this report:

- **S** — current repository source/README inspected through Personal DC on 2026-10-23, with path supplied; exact Git HEAD still UNVERIFIED.
- **H** — recorded user decision or historical review/conversation, not revalidated against current source.
- **W** — public upstream GitHub project/documentation inspected in research on 2026-10-23; **not** a local integration result.
- **I** — inference or recommendation derived from S/H/W; explicitly needs validation.
- **N** — unknown, NOT_CHECKED, NOT_RUN, or open design question.

Never treat a source count, an instruction profile, a reviewed design, an AI output, a zero-finding scan, or a saved artifact as proof of a runnable fully automated organization. Each is a different capability class.

## 2. Chronological provenance of requirements and decisions

| When | Decision/request or observation | Basis | Consequence for design |
|---|---|---|---|
| 2026-10-09 and later | User requested a full set of reusable specialists including functional, E2E, security, database, code explorers, architects, writers and build resolvers. | H | Build role coverage inventory; do not implement a separate monolithic agent for each skill. |
| 2026-10-09 | AEVE emerged as a separate local-first execution/evidence project; 28 agent plus 29 skill instruction-contract design. | H/S | Keep AEVE autonomous as a separately versioned verifier/router and constrain claims to implemented tools. |
| 2026-10-18 to 2026-10-23 | AEVE static-review specialization E14 developed via several review/remediation rounds; false PASS, branch-aware failure analysis and isolation repeatedly highlighted. | H/S | Demand machine-verifiable negative probes and explicit unsupported states for every verification feature. |
| 2026-10-21 onward | User required global agents/Skills and virtual Scrum workflow to be used across projects; do not replace installed Claude/Codex assets indiscriminately. | H | Versioned role registry plus separately qualified installed copies. |
| 2026-10-23 | User identified `Virtual_scrum_team` as workflow to automate and `agents-skills-repo` as current specialist/skill inventory, requesting a full team. | H | Existing ten-phase Scrum process stays single control plane. |
| 2026-10-23 | User asked to examine local `MegaGpt`, possible upstream updates, and GitHub `AIDAR` (assumed to refer to **Aider**, still to confirm). | H/W | Evaluate MetaGPT SOP/handoffs, Aider editing mode, external BMad/OpenHands options without blindly importing runtimes. |
| 2026-10-23 | User asked where AEVE belongs in the chain. | H/S | AEVE is independent evidence/verification layer, not general developer or primary sprint board. |
| 2026-10-23 | User requested one final plan and then a saved history for external independent review. | H | Produce reproducible blueprint and this deliberation/evidence dossier. |
| 2026-10-23 | Live Personal DC read confirms `Virtual_scrum_team`, `agents-skills-repo`, `AEVE` and `MegaGpt` folders exist; README/AGENTS/SDLC reviewed. | S | Confidence is source-specific, not full Git or runtime qualification. |
| 2026-10-23 | Live global workspace `AGENTS.md` model rules conflict with older Virtual Scrum Team role-model statements. | S | Block automated role selection pending policy reconciliation and tests. |

## 3. Verified current-source record

| Source | Observed facts (S) | Qualification missing (N) |
|---|---|---|
| `Virtual_scrum_team/README.md` | Ten named SDLC phases; `sdlc-orchestrator` delegates; authored agents + 7 skills; installed copies are independent; team README says Sonnet alias. | Live installed profile versions, dispatch and model resolution. |
| `Virtual_scrum_team/docs/SDLC_PROCESS.md` and `team/skills/sdlc-orchestrator/SKILL.md` | Phases 1–10, main-session delegation, no child delegation, no test/check in Build, required tests in Verify. Skill explicitly forbids full suites, lint, typecheck, build or CI in phase 7. | Whether project-level CI/release-head gates can be incorporated without violating the global rules. |
| `Virtual_scrum_team/docs/FULL_TEAM_EXPANSION_PLAN_2026-10-23.md` | A proposal already exists for 39 logical roles with P0–P4 adoption sequence; explicitly not installed or accepted. | Role-to-install mapping, runtime and test evidence. |
| `Virtual_scrum_team/AGENTS.md` | Only main orchestrator delegates; generic repository no project-private content; English commits; role `sonnet`; change records for commits. | This file sets only the `sonnet` alias and has no Luna text; the Sonnet / GPT-5.6 Luna wording is in `README.md`, `docs/SDLC_PROCESS.md` and the orchestrator skill. Reconcile with the workspace policy and with the operator's global contract (a third source). |
| `${WORKSPACE_REPOS}\AGENTS.md` | Global policy currently calls for `gpt-6-luna` on standard reviewer/test-agent runs; narrow `gpt-5.6-luna` exception for selected consensus; test author/execution limited to `functional-test-reviewer` and `e2e-runner`; code before tests, one PR/sprint, GPT approval. | Which policy resolution mechanism and runtime config should win when applied to source-authored VST profile. |
| `agents-skills-repo/README.md` | Reusable generic Claude agents/Skills; installation is manual copy; user catalog historically 36 agent profiles and 8 tracked qualifying skills. | Current file counts, duplicate aliases, tool and model enforcement. |
| `AEVE/README.md` | Local-first Python 3.12+; 28 role, 29 skill instruction contracts; 15/57 profile routes PARTIAL to any deterministic executor and 42 NOT_COVERED; limited Python/JS/SQLite/recovery analysis and fixed Docker boundary; no general provider execution or arbitrary code writes. | Current exact-head executor coverage, individual rule probes, successful model host integrations. |
| Personal DC project list | `AEVE` registered to frozen temp snapshot rather than working `AEVE` checkout; seven other registered entries including one nonexistent legacy `ERP_MCP_ChatGPT`. | Exact registry change scope and read/write interfaces. |
| `MegaGpt/MetaGPT` directory | Upstream MetaGPT clone exists inside `MegaGpt`, plus local virtual environments. | Updated upstream HEAD, license and reproducible compatibility of a chosen slice. |

**Version caveat:** All current-source observations above are path/time-bound but **not Git commit SHA bound**. This is sufficient to prepare an advisory review package, not a final code/installation gate. Before implementation, record `git status`, branch, remote, exact HEAD and content hashes. Personal DC does not currently register `Virtual_scrum_team` as a project ID; direct file access succeeds, but the attempted registered-project Git status call did not resolve it. No Git commands or repository mutations were performed to infer a fake HEAD.

## 4. Decision register: chosen approach vs alternatives

The status `PROPOSED` means not operator acceptance and not a deployed capability.

| ID | Decision (proposed) | Why this path | Alternative(s) considered | Why not selected now | Evidence | Reversal trigger |
|---|---|---|---|---|---|---|
| D-01 | VST owns the ten-phase SDLC state | Existing process, project `STATE.md`, clear phase artifacts | Replace with BMad board, MetaGPT manager, OpenHands sessions, new orchestrator | Competing state owners, migration risk, lost acceptance chain | S/H/I | Failed phase-transition/recovery tests or explicit redesign approval |
| D-02 | Generic agents/Skills versioned in `agents-skills-repo` | Already built and installed in places; cross-project reuse | Copy complete agent sets into every product repo | Drift, prompt conflicts, per-project duplicated fixes | S/H/I | Source/installation qualification proves central distribution cannot work |
| D-03 | AEVE verifies bounded facts, not autonomous coding | Its own README expressly limits capability and requires external reasoning host | Make AEVE full AI orchestration and execution host | Implemented bounded tools do not support such claims | S | Independently qualified new AEVE capabilities and authorized changed contracts |
| D-04 | Use real CI/test tools for execution and evidence | Commands, environment, failure oracle and exit codes are falsifiable | LLM-generated “all passed” prose | No execution proof, false-green risk | S/I | Never reverse without equivalent verifiable evidence |
| D-05 | Choose BMad Loop for first isolated worker pilot | Worktree/run/review/retry mechanisms align with story delivery | OpenHands-first, Aider-first, hand-written loop | Comparative benchmark not yet done; BMad Loop higher fit on paper | W/I | Pilot demonstrates unsafe actions, unresolved bugs, Windows mismatch or poor reliability |
| D-06 | OpenHands and Aider are bounded alternatives, not control planes | Useful execution/editor mechanics without new board authority | Install both broadly as new co-orchestrators | Larger operational and permission surface | W/I | Approved controlled benchmark materially outperforms first pilot |
| D-07 | MetaGPT supplies artifact-handoff ideas only | Existing clone useful, but whole Python runtime is not validated for local setup | Make MetaGPT main team | Uncontrolled generated code execution/installation and compatibility risk | S/W/I | Safe isolated exact-version benchmark proves large advantage |
| D-08 | BMad TEA supplies QA strategy and skill templates | Risk mapping, test review, trace and NFR model | Write complete custom QA theory/rules | Duplicates mature community material; better to adapt and evaluate | W/I | Incompatible process, license, poor oracles or QA misrouting discovered |
| D-09 | 39 logical roles, bounded active jobs | Complete competency coverage without 39 model processes | Resident agent per role | Cost, conflicts and duplicate reviews | S/I | Workload/eval data requires adjusted roster |
| D-10 | At most 5 AI jobs + 5 CI runners first | Established user capacity bound and narrow blast radius | Unbounded parallel work | Race conditions, cost spikes and source conflict | H/I | Capacity stress pass and explicit operator override |
| D-11 | Immutable head-bound evidence and independent reviewer | Prevent stale approvals, fabricated PASS, author self-approval | General “approved” note | Cannot identify code that was checked | S/H/I | Never reverse without equivalent cryptographic/version binding |
| D-12 | PM Bridge only receives accepted sprint closure | Previously scoped PM Bridge contract; single SDLC owner | PM Bridge updates every task/phase | Split-brain authority | H/I | Approved new PM Bridge integration contract |
| D-13 | Personal DC exposes only listed capabilities | Live read bridge and permission fence; no arbitrary exec observed | Assume a generic remote shell exists | Unsupported and potentially unsafe | S | Capability listing and contract explicitly grant a bounded runner |
| D-14 | Release, provider, money, deletion and production remain operator-bound | User intent and workspace/global safety rules | Full unattended arbitrary publication | Irreversible and high-impact operations require distinct authority | S/H | Narrow explicit operator authorization and effective platform enforcement |
| D-15 | Phased roll-out: synthetic → FitnessUp → PDCC → ERP/ERP_MCP | Escalates from bounded app flows to tenant/financial/1C risks | All projects at once | Scope and hazard amplification | H/I | Safe verified pilots and operator priority change |

## 5. Rejected, deferred, and NOT EVALUATED options

Distinct categories matter: **rejected after fit analysis** is not the same as **not looked at**.

### Discussed but not selected for primary control plane

1. **MetaGPT as the entire company** — role/SOP structure is relevant; integration, safety/compatibility and native test coverage unproven. Status: REFERENCE.
2. **AEVE as the entire company** — contradicts present bounded executor coverage and model-host separation. Status: REJECTED FOR CURRENT CAPABILITIES; revisit if product scope changes.
3. **Aider as manager** — excellent developer/editor focus, not owner of backlog/phase/acceptance. Status: PILOT EDITOR ONLY.
4. **OpenHands as manager** — supports coding agents and sandboxes but should not become second product/SDLC board. Status: PILOT EXECUTOR ONLY.
5. **BMad Method replacing VST** — would throw away current ten-phase ownership and custom gates. Status: METHODOLOGY INPUT ONLY.
6. **Multiple live orchestrators simultaneously** — likely conflicting writes, approvals and opaque recoveries. Status: REJECTED.
7. **Building a custom orchestration runtime immediately** — duplicates existing candidates before feature-gap benchmark. Status: DEFERRED unless BMad Loop/OpenHands controlled tests fail.

### Promising candidates not comparatively researched or not prototyped

These are **NOT_EVALUATED**; neither recommendation nor dismissal should be inferred:

| Domain | Unassessed examples | Why assess later | Required comparison |
|---|---|---|---|
| Durable orchestration | Temporal, Prefect, Dagster, Argo Workflows | Strong recovery/exactly-once-ish coordination | Event replay, durable resume, complexity, Windows/WSL support |
| Agent frameworks | CrewAI, AutoGen, OpenAI Agents SDK, LangGraph | Task graphs, persistence or hosted tool integration | No double orchestration, permission model, model/provider fit |
| Code workers | SWE-agent, OpenHands Agent SDK, coding agents beyond Aider | Specialized benchmark performance | Diff accuracy, task completion, sandbox, cost, adversarial prompt data |
| CI and reproducibility | Dagger, Nix, GitHub Actions self-hosted runner, Buildkite | Environment drift and supply-chain control | Reproducible offline runner and cost |
| Contract/security tools | Pact, pgTAP, Semgrep, Trivy, CodeQL, OPA, Syft/Grype, Renovate | Stronger API, DB, auth and supply-chain gates | Project stack relevance, privileges and evidence coverage |
| Mobile E2E | Patrol, Appium alongside Maestro | Flutter/platform specifics | Device coverage, flakiness, maintenance |
| Observability | OpenTelemetry, Prometheus/Grafana, structured SARIF/JUnit aggregation | Correlation and release evidence | Cost, trace correlation, privacy |
| Security methodologies | OWASP ASVS, NIST SSDF, SLSA, threat-model as code | Assurance maturity | Scope and criteria mapping; avoid premature compliance claims |

No benchmark rankings, license approval, maintainer security status, vulnerability audit or SDK compatibility are claimed for these.

## 6. External upstream evidence and caveats

| Upstream GitHub reference | What was observed in public documentation (W) | How it informed selection | What is still NOT_CHECKED |
|---|---|---|---|
| https://github.com/bmad-code-org/bmad-loop | Early open beta; worktree isolation recommended; real coding/commits; pre-1.0 changes expected; native Windows runtime roadmap incomplete. | Good first bounded execution **experiment**, with pinned version and WSL2 sandbox. | Actual replay, unattended stall/review defects, released tag, security isolation and licensing review. |
| https://github.com/bmad-code-org/bmad-method-test-architecture-enterprise | TEA proposes risk-based plans, test generation/review, NFR and evidence/trace gates; execution targets vary. | Adopt knowledge/process to supplement authorized test agents. | CLI/Node requirements on local machine, true Flutter/SQL coverage and conflicts with no-test-during-build rule. |
| https://github.com/bmad-code-org/BMAD-METHOD | Role/workflow methodology. | Source of reusable document/phase patterns, not second authority. | Feature parity vs VST and upstream update compatibility. |
| https://github.com/Aider-AI/aider | Repository mapping, architect/editor editing; upstream issue #5058 documents repository-content prompt injection affecting architect/editor handoff. | Useful as guarded editing adapter with independent patch audit. | Whether vulnerability is fixed in intended pin; local runtime and auto-commit flags. |
| https://github.com/OpenHands/OpenHands | Supports Docker sandbox modes, model-assisted code tasks. | Alternative worker benchmark rather than direct host executor. | Specific host/container isolation and resource/network controls. |
| https://github.com/FoundationAgents/MetaGPT | Structured role SOP and artifacts. | Borrow transferable design ideas. | Full runtime/compatibility, safety of generated-code execution. |
| https://github.com/github/spec-kit | Specification-first artifacts. | Adapt spec templates to existing VST phases. | Overlapping state artifacts and tooling side effects. |
| https://github.com/microsoft/playwright and https://github.com/mobile-dev-inc/maestro | Practical web and mobile test runners. | Native execution sources and logs/traces; do not hand-wave tests. | Runtime availability and real project fixtures. |

Every adopted upstream must be pinned to a digest/tag, scanned, license-checked, and validated on synthetic fixtures. GitHub links are *discovery references* until versions are recorded.

## 7. Critical contradictions / unresolved design choices

| ID | Severity if unresolved | Conflict / gap | Required resolution and test |
|---|---|---|---|
| C-01 | BLOCKER for activation | Global workspace model allowlist (`gpt-6-luna`) conflicts with team `sonnet`, VST orchestrator reviewer guidance and the operator's global contract (Sonnet 5.5 medium or GPT-5.6 Luna low/medium): three sources disagree. | Decide and version source precedence; runtime resolved-model audit; negative tests for Opus and silent fallback. |
| C-02 | BLOCKER for modifying SDLC | VST calls test agents only after code, yet TEA's ATDD/test-red mode and `tdd-guide` suggest pre-code tests. | Respect existing phase 6/7 order until explicit ADR; no silent adoption of red-first flow. |
| C-03 | BLOCKER for broad CI | VST orchestrator explicitly forbids full suites, lint, typecheck, builds and CI in phase 7 while the unified blueprint proposes release-head CI. | Clarify whether independent release gate outside phase 7 is approved and which actor owns it. |
| C-04 | BLOCKER for correctness | VST-007 retained evidence and VST-008 exact-head gate historically open. | Implement measurable receipt retention and stale-head fail fixtures before auto-acceptance. |
| C-05 | BLOCKER for integration | Personal DC `AEVE` registry points to frozen temp checkout instead of working development repository. | Separate canonical checkout and immutable benchmark ID; verify paths, no snapshot overwrite. |
| C-06 | BLOCKER for trust | 57 AEVE instruction contracts are conflated with 57 runnable deterministic specialists. | Publish per-capability coverage, one finding/no-finding semantic and unsupported/NOT_RUN statuses. |
| C-07 | HIGH | Exact Git HEAD/dirty/remote and installed agent profile hashes unavailable in current evidence. | S0 Git manifest with user-change preservation and no implicit install. |
| C-08 | HIGH | External worker may inspect untrusted README/prompt instructions and commit malicious code. | Least-privilege sandbox, explicit file scope, diff/secret checks, independent reviewer, malicious repository fixture. |
| C-09 | HIGH | Hidden background network/provider calls or auto-install from MetaGPT/OpenHands/BMad/Aider may violate grant boundaries. | Tool allowlists, traffic isolation, cost budgets, simulated network denial and provider-fallback negative test. |
| C-10 | HIGH | Multiwriter across VST board, execution loop, AEVE task ledger and PM Bridge. | Single-writer schema, immutable IDs, conflict simulation, replay/recovery oracle. |
| C-11 | HIGH | Agent author/reviewer or test author/evidence auditor can become same process/context. | Independent immutable snapshot, identity separation and tamper-detection tests. |
| C-12 | HIGH | Future scope expands to real tenant data, production load, 1C native reports or financial migrations. | Project-specific execution fences; refuse unsupported production/test targets by default. |

## 8. Mandatory adversarial review questions

The independent reviewer should answer **every** question with `SUPPORTED`, `UNSUPPORTED`, `UNCLEAR`, or `NOT_CHECKED`, citing exact artifact and line, plus a reproduced scenario for any BLOCKER/MAJOR.

### A. Architecture and authority
1. Can VST remain sole SDLC authority even if BMad Loop has its own story tracking and run-state? Where can split-brain writes occur?
2. Does an accepted task receipt bind the exact project, branch/HEAD, source hashes, role/skill hashes, model, allowed tools and real invocation ID?
3. Is every automated irreversible step enforceably denied until the correct actor approves it?
4. Does PM Bridge only consume accepted sprint closure without reopening/editing authoritative phase status?

### B. Execution isolation and lifecycle
5. What prevents a model seeing a malicious README or tool result from modifying out-of-scope code or extracting credentials?
6. How do worktree crashes, retries, duplicate workers, forced STOP, power-off and expired leases preserve one authoritative result?
7. Can a stale sandbox write into a new epoch/worktree? Prove fenced updates rather than checking only recovery inventory.
8. Can an unreviewed upstream update change agent behavior, tool permissions, defaults or install time side effects?

### C. Testing and review truthfulness
9. Can generated tests be skipped/xfail/quarantined or assertions weakened yet still satisfy required acceptance?
10. Which agent is authorized to **author and execute** each suite given the global two-author rule? Do proposed skills broaden that authority accidentally?
11. Are full-suite/CI recommendations consistent with the actual phase-7 prohibition? If not, what exact ADR is required?
12. What is the false-negative corpus proving each test can detect a seeded defect?
13. Does AEVE return `PARTIAL`/`NOT_COVERED` for unsupported rules instead of implying full profile pass?
14. Can a source commit after review reuse an older GPT or CI approval? What invalidation is enforceable?

### D. Resource governance and release
15. Are only approved models used, with no silent fallback or external AI reviewer?
16. Can the initial 5 AI and 5 CI limit be exceeded by nested tools, retry or worker leaks?
17. Are time, token, money and network budgets enforced by systems rather than prompts alone?
18. Are production, tenant, database, 1C and real-money boundaries protected under negative execution tests?

### E. Product and maintainability
19. Why is the 39-role team necessary, and which roles may be optional based on actual risk frequency?
20. Does adding BMad TEA, Spec Kit and VST create duplicate specs and conflicting document owners?
21. Are the selected GitHub components actively supportable, appropriately licensed and compatible with Windows/WSL2/local Python/Node toolchains?
22. Are the alternatives marked NOT_EVALUATED genuinely potential blockers, or safe to defer with a measured re-evaluation point?

## 9. Findings template for the reviewer

Return one comprehensive adversarial pass and a decision, not a generic approval. Findings must contain:

```yaml
finding_id: VEO-R1-<unique>
severity: BLOCKER|MAJOR|MINOR|INFO
status: CONFIRMED|SUSPECTED|NOT_REPRODUCED
affected_component: canonical-repo-and-path
head_or_artifact_hash: exact-hash-or-NOT_VERIFIED
source_location: file:line-or-document-section
failure_path: concrete-steps-or-input
expected_invariant: explicit-condition
observed_or_predicted_violation: explanation
minimum_fix: bounded-remediation
verification_oracle: executable-check-or-accepted-proof
```

Conclude with:

1. `APPROVE DESIGN` / `MODIFY DESIGN` / `NO-GO DESIGN`.
2. All distinct BLOCKER and MAJOR findings in one batch, grouped by root cause.
3. Evidence/source gaps and `NOT_CHECKED` areas, not silently green.
4. Ranked options to reconsider and cost of a wrong architectural choice.
5. Proposed minimal safe S0/S1 gates and acceptance criteria.
6. Separate engineering architecture acceptance from permission to install, call external AI, push, merge, delete or deploy.

## 10. Reviewer package and handoff checklist (a tick means "recorded", not "verified")

- [x] Main blueprint, full 39-role roster proposal and source-of-truth decision identified.
- [x] Ten-phase VST SDLC and current local orchestrator behavior inspected.
- [x] AEVE bounded README scope inspected; explicit 15/57 PARTIAL vs 42 NOT_COVERED distinction recorded.
- [x] Key external GitHub candidates and high-risk assumptions recorded.
- [x] Architecture alternatives, unknowns and adversarial questions recorded.
- [ ] Full Git exact HEAD/remote/dirty state of all repositories (`NOT_CHECKED`).
- [ ] Hashes and installation resolution for current global agents/Skills (`NOT_CHECKED`).
- [ ] BMad Loop / OpenHands / Aider local sandbox benchmark (`NOT_RUN`).
- [ ] S0 source/model policy reconciliation, ADR and synthetic acceptance tests (`NOT_RUN`).
- [x] Devil's-advocate review by six read-only agents completed 2026-10-23: MODIFY DESIGN (section 11).
- [ ] Operator design acceptance and final GPT review (`NOT_RUN`).

**Disposition:** This is a design review request ready to hand to an independent reviewer. It is intentionally **not** a final approval or runtime qualification. No project deployment, external AI invocation, automatic role installation, Git commit, push or merge is authorized by this report.

## 11. Devil's-advocate review outcome (2026-10-23)

Six read-only agents (architecture, security, reliability, test strategy, silent-failure, consistency; Sonnet 5.5, medium effort) reviewed the three documents. Every verdict was **MODIFY DESIGN**. The accepted amendments and the required pre-S3 items are in section 13 of the master blueprint. Reviewer findings are claims; the consistency items marked VERIFIED there were re-checked by the coordinator.

New contradictions and gaps added to section 7 (all unresolved):

| ID | Severity if unresolved | Conflict / gap | Required resolution and test |
|---|---|---|---|
| C-13 | BLOCKER for QA design | Red/green, mutation and seeded-defect clauses conflict with code-before-tests and the operator's no-mutation-run rule; no document lists this as a conflict. | One ADR with C-02 and C-03; every such clause cites the ADR or reads `NOT_RUN`. |
| C-14 | BLOCKER for trust | Receipts are producer-asserted and unsigned; `result` and `reviewer_identity` are free text. | Signed receipts from a runner outside the worker's trust domain; forged and replayed receipts rejected. |
| C-15 | BLOCKER for correctness | The gate has no total verdict function; partial coverage and unsupported rules can end in APPROVE; required receipts are chosen by the decision author. | Gate derives required slots from the manifest; fixtures for partial coverage and missing receipts. |
| C-16 | BLOCKER for concurrency | No state store, lease, epoch or fencing; the "single writer" is an LLM-edited markdown file; the 5+5 limit and cost caps have no enforcer. | State store with compare-and-swap epoch; slot table; budget ledger with kill action. |
| C-17 | HIGH | No sandbox, credential or egress specification; the local access bridge has no threat model; upstream pins are stated, not enforced. | Specifications and pre-flight probes listed in blueprint section 13.4. |
| C-18 | HIGH | Public-repository disclosure of private repository names, URLs and bridge topology. | Operator decision O-1 in blueprint section 13.6. |

Reviewer questions 9-14 in section 8 are answered **UNSUPPORTED** or **UNCLEAR** by the current design text, not SUPPORTED. The "NOT_EVALUATED" alternatives (section 5) stay unevaluated; the review asks only that the worker choice be made after a bake-off on one crash/resume fixture.

## 12. Operator decisions of 2026-10-24 (ADR-0001)

The operator answered four open questions; see `ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`. Effect on section 7: C-02 and C-03 are settled at documentation level (no red/green, no CI outside the two test agents' focused runs); C-13 is settled by "no mutation runs, known-defect fixtures on synthetic repositories only"; C-01 is settled for this repository (the operator's global contract governs) but the workspace `AGENTS.md` outside the repository still disagrees. Decision O-2 (more than two test authors): no. Decision O-3 (CI): none. Settled at documentation level is not implemented: C-14, C-15 and C-16 (signed receipts, gate verdict function, fenced state store) and the single phase-state authority remain open.
