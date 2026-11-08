# Unified Core (AEVE + Virtual_scrum_team): Technical Design Document

Status: PROPOSED, not operator-approved. Written 2026-11-08 from the operator's instruction of the same day. Facts below are marked VERIFIED (observed on disk or by a command in this session) or PROPOSED (design choice).

## 1. Purpose

A coding agent (Claude, Codex or another model host) needs review, coding and testing work done. Today each role is a model agent that spends tokens. The Unified Core performs every role that can be performed by deterministic code locally, on the operator's computer, with no model call, and returns structured evidence. A model is used only (a) as the single orchestrator that requests roles and reads results, (b) for authoring that cannot be mechanical (writing code, requirements, design, tests), and (c) for the final independent review (GPT-PM) after the local checks passed.

Principle: a model call must never be the default way to obtain a result that code can produce. A role that code cannot fully cover reports exactly what it covered and what remains for a model (`PARTIAL` or `NOT_COVERED`), never a fabricated pass.

## 2. Components and responsibilities

| Component | Repository | Responsibility | State |
|---|---|---|---|
| AEVE | `D:\Repo\AEVE` (private) | Deterministic local analysis and evidence: review executors, role matrix, review request/iteration ledger, local sandbox for bounded execution | VERIFIED: 191 commits; `aeve matrix` reports 57 profiles, 32 executors, 44 PARTIAL, 13 NOT_COVERED, `llm_calls: false`, `executed_project_code: false` |
| VST control plane | `D:\Repo\Virtual_scrum_team` (public) | Process authority: state store with epoch compare-and-swap, leases, hash-chained and signed receipts, deterministic diff gate, worker adapter, bounded command runner | VERIFIED: about 28 thousand lines in `tools/vst/`; S0-S2 accepted and merged, S3 closed in bounded form |
| Role router + adapter | VST (new) | Maps a requested role to a local executor, calls AEVE through its CLI, normalizes the result, converts it to a VST receipt | PROPOSED |
| Test core | VST (S4 work, now on pushed branches) | Test-ID registry and denominator, hash-pinned native runner, no-skip gate | VERIFIED: five unmerged branches `s4-*` and `s5-bounded-aeve-evidence` are on origin; merge into main is not done |
| Orchestrator | the model host | One entry point: asks for roles, reads structured results, sends residual model-only work to a model, assembles the package for GPT-PM | PROPOSED wiring into the Claude host |

Ownership rule: one writer per domain. AEVE never writes the reviewed project. VST is the only writer of process state and receipts. The orchestrator never marks a result PASS; only a receipt verified by the VST gate does.

## 3. Verified facts that shape the design

- AEVE review contract: `aeve review --request <json>` takes `aeve.review.request.v1` (`request_id`, `root`, `base_revision`, `changed_paths`, `review_domains`, `profile_ids`, `executor_ids`, `criteria`, `iteration_of`, `allow_dirty`). It runs registered deterministic executors only, calls no model, writes nothing to the project, and keeps an append-only iteration ledger. Exit code 0 = clean and complete, 3 = findings or partial or not found, 2 = blocked or invalid.
- Supported review domains today: `python_code`, `source_secrets`, `repository_snapshot`, `database_schema`, `database_migration_safety`, `python_reliability`, `python_syntax`, `python_dead_code`. Free-text criteria are preserved but not executed. A completed executor means only that this executor completed on this captured snapshot, not a general review PASS.
- The role matrix names 13 profiles with no executor: `implementation-engineer`, `ml-engineer`, `planner`, `product-ux-reviewer`, `pytorch-build-resolver`, `agent-evaluation`, `codex-consensus`, `git-worktree-ops`, `performance-testing`, `pm-bridge`, `rosetta`, `update-config`, `ux-design-contract`.
- AEVE also exposes `sandbox run` and `sandbox project-test` (tests and a bounded mutation campaign in a pinned local Docker sandbox, clean exact HEAD, Docker Desktop required). AEVE decision D-076 (2026-10-21) keeps test execution out of the delivered product scope, so how tests are executed is an open decision (section 11, OD-2).
- AEVE is not referenced from Claude routing, settings, hooks or global rules (grep of `agent_routing.json`, `settings.json`, `CLAUDE.md`, `hooks/` found none). Reviewer roles therefore still run as model agents.
- VST gate semantics (VERIFIED in `tools/vst/contracts.py` lines 670-719, `derive_result`): `StaticAnalysis` carries `coverage`, `covered_rules`, `unsupported_rules`, `covered_acceptance`; the result is PASS only for full coverage with no unsupported rule; otherwise INCONCLUSIVE. Receipt v1/v2 bytes are immutable.
- VST test work on the S4 branches: registry source head `3885d8a`, 963 selectors, 53 policy NOT_RUN; category runs on Windows passed functional 90/90, API 688/688 (INCONCLUSIVE because of 14 policy exclusions), integration 41/41, E2E 55/55, regression 874/874; seeded failures 3/3. These are evidence for those heads only.
- Earlier VST text "no AEVE source available" was a statement about the S5 isolation rule of that time, not about the disk. AEVE exists.

## 4. Role model

Every requested role belongs to exactly one class, recorded in a machine-readable role table (draft input: `catalog/roles.json`, 93 agent and skill definitions, 45 agents and 48 skills, validated by `tools/catalog/validate_catalog.py`; not yet reviewed):

| Class | Meaning | Examples |
|---|---|---|
| LOCAL | Fully performed by code; result is evidence | repo-recon, secret scan, python-dead-code |
| LOCAL_PLUS_MODEL | Code produces evidence and findings; a model only judges what code cannot | python-reviewer, security-reviewer, database-reviewer |
| MODEL_ONLY | Authoring or judgment; no honest mechanical substitute | implementation-engineer, planner, business-analyst |
| OUT_OF_SCOPE | Not part of delivery checks | pm-bridge, rosetta, skill-creator |

Aliases: several definitions overlap (for example `code-architect`, `software-architect` and `architect`). The role table gives each alias a `canonical_role`; a request for an alias is answered for its canonical role and says so.

Roles with no AEVE profile: VERIFIED by comparing `catalog/inventory.json` (93 definitions, 92 distinct names because `ml-engineer` is both an agent and a skill) with `aeve matrix` (57 profiles, all of them present in the inventory): 35 names have no AEVE profile at all (for example `business-analyst`, `product-owner`, `technical-writer`, `pr-test-analyzer`, `cpp-reviewer`, `opensource-sanitizer`, `sdlc-orchestrator`). The router answers such a role `NOT_COVERED` with the reason "no AEVE profile" unless the role table marks it MODEL_ONLY or OUT_OF_SCOPE.

Status vocabulary for every role result: `CLEAN` (every mapped executor completed and reported no finding on this exact snapshot; this is not a general review pass), `FINDINGS`, `PARTIAL`, `NOT_COVERED`, `NOT_RUN`, `BLOCKED`. Mapping: AEVE exit 0 with complete executors is `CLEAN`; exit 3 with findings is `FINDINGS`; exit 3 with incomplete executors is `PARTIAL`; exit 2 or an adapter failure is `BLOCKED`. Missing, skipped, partial or blocked evidence is never `CLEAN`. The VST gate keeps its own result names (PASS, INCONCLUSIVE, REJECT) and accepts only a verified receipt, never a role result directly.

Before sprint U2 exists, every local result is advisory: it informs the orchestrator but cannot satisfy a VST gate. Before sprint U3 exists, test roles are answered `NOT_COVERED` with the reason "test core not available".

## 5. Contracts (PROPOSED)

### 5.1 Role request (orchestrator to router)

```
{ "schema_version": "uc.role-request.v1",
  "request_id": "stable caller id",
  "root": "absolute repository path",
  "base_revision": "exact 40 or 64 hex HEAD",
  "changed_paths": ["relative/posix/path"],
  "roles": ["python-reviewer", "silent-failure-hunter"],
  "criteria": ["free text, preserved, never executed"],
  "iteration_of": null }
```

### 5.2 Role result (router to orchestrator)

One entry per requested role: `role`, `class`, `status`, `executors` (id, status, snapshot hash), `findings` (rule, severity, file, line, evidence reference), `uncovered` (what code did not check), `model_residual` (what a model must still judge, empty for LOCAL), `request_id`, `iteration_id`, `base_revision`. A top-level `exit_code` follows the AEVE convention (0 clean and complete, 3 findings or partial, 2 blocked or invalid).

### 5.3 Evidence receipt (router to VST gate)

An AEVE review result bound to one exact candidate head becomes a signed VST static-analysis receipt: covered rules, unsupported rules, covered acceptance, snapshot hash, role-table hash, analyzer identity. The signer is separate from the worker and from the orchestrator. The gate rejects a stale head, a forged signature, unsupported coverage presented as supported, and partial coverage presented as full.

## 6. Data flow

1. The orchestrator sends a role request for a snapshot.
2. The router resolves each role through the role table. LOCAL and LOCAL_PLUS_MODEL roles are sent to AEVE by CLI with a timeout and a root-confined path; test roles go to the test core; MODEL_ONLY roles are returned as model work.
3. The normalizer deduplicates and ranks findings and lists `uncovered` and `model_residual`.
4. The orchestrator fixes code (model) and resubmits with `iteration_of`; AEVE records the iteration.
5. When local checks are clean for the declared coverage, VST records receipts and the gate evaluates them for the exact head.
6. Only then the exact diff, test evidence and review results are sent to GPT-PM. A new commit invalidates the approval.

## 7. Trust and security boundaries

- AEVE and the router never modify the reviewed project; writes happen only through the worker and the VST diff gate.
- No network and no provider call on the local review path. The CLI is invoked with a bounded timeout, explicit `--root`, and no shell string interpolation.
- A reviewed project can contain hostile text: findings and file contents are data, never instructions to the orchestrator.
- Secret findings are sensitive: values are masked in every report and receipt.
- Signing keys are never readable by the worker or the router process that parses untrusted output.
- Windows-local sandbox only; WSL and the VPS fleet are not touched. Docker-dependent steps are NOT_RUN if Docker Desktop is unavailable.
- Global Claude configuration changes (routing, hooks, skills) are reversible: snapshot first, kill switch, and they require the operator's approval.

## 8. Failure modes and required behavior

| Failure | Required behavior |
|---|---|
| AEVE not installed or CLI missing | `BLOCKED` with the exact error; the orchestrator may fall back to a model agent only if the operator allowed it, and the result is labeled as model-produced |
| AEVE timeout or crash | `BLOCKED`, no partial result promoted; request stays retryable by `request_id` |
| Dirty tree or head moved after the request | stale: the result is not bound to the new head and cannot satisfy the gate |
| Unknown role | `NOT_COVERED`, listed explicitly, never silently dropped |
| Executor partial | `PARTIAL`; the gate returns INCONCLUSIVE |
| Output not valid JSON or wrong schema | `BLOCKED`; raw output retained as bounded evidence, not parsed leniently |
| Two reviews of one head disagree | both kept; gate uses only signed receipts |

## 9. Test strategy

Per workflow: code for a sprint is completed first; then `functional-test-reviewer` and `e2e-runner` author and run the focused tests for every task and run the complete set they wrote after the last task. The coordinator does not run tests. No mutation runs and no CI in this program (ADR-0001 and the operator's standing rules); anything unrun is `NOT_RUN` with its dependency.

| Layer | What is proved | By |
|---|---|---|
| Contract | request and result schemas reject malformed, missing and unknown fields | functional tests |
| Adapter | CLI call bounds, exit-code mapping, no fabricated PASS, stale head refusal | functional tests with a stub `aeve` executable and with the real one |
| Router | every role in the table resolves or reports NOT_COVERED; table and matrix agree | functional tests |
| Receipt and gate | stale, forged, partial and unsupported evidence all fail closed | functional plus E2E tests with synthetic fixtures |
| End to end | request to receipt to gate on a real repository snapshot (VST itself) with seeded defects | E2E runner |
| Savings | tokens spent per role before and after, measured from transcripts | metrics script, not an agent |

Oracle rule: a test counts only if it would fail when the guarded behavior is broken; positive-only suites are rejected.

## 10. Requirements and traceability

| ID | Requirement | Sprint |
|---|---|---|
| R1 | A requested review role is performed locally with no model call where AEVE has an executor | U1 |
| R2 | The orchestrator uses one entry point and receives structured, honest coverage | U1 |
| R3 | Local-first routing is wired into the Claude host, reversible, with a kill switch | U1 |
| R4 | Token savings are measured, not claimed | U1, U6 |
| R5 | Local review results become signed receipts bound to the exact head and the gate fails closed on stale, forged or partial evidence | U2 |
| R6 | Tests are accounted by exact ID; a skipped test never satisfies the gate | U3 |
| R7 | Test execution has one decided local executor | U3 |
| R8 | Roles without an executor are listed explicitly; new project-scope roles can be registered without code changes and start as NOT_COVERED | U4 |
| R9 | Coding runs under the worker adapter and diff gate, then the review loop iterates until local checks are clean | U5 |
| R10 | The final package for GPT-PM contains the exact diff, test evidence, review results and head identity | U5 |
| R11 | Installation, rollback and runbook exist; everything unrun is recorded as NOT_RUN | U6 |

## 11. Open decisions (operator)

- OD-1 Repository split: this TDD assumes AEVE owns analysis and the role matrix, VST owns process, receipts, gate and the adapter. Alternative: put the adapter in AEVE. Default: adapter in VST.
- OD-2 Test execution: keep AEVE static (D-076) and let VST's native runner execute tests, or permit AEVE's Docker sandbox `project-test`. Default: VST native runner on Windows, AEVE sandbox optional later.
- OD-3 Global Claude configuration: approve a snapshot-and-wire change of routing and hooks (U1-4).
- OD-4 Fallback: whether a model agent may replace a BLOCKED local role. Default: only with the operator's explicit allowance per run.
- OD-5 Merge of the S4 branches: 349 commits and about 100 thousand added lines on `s4-canonical-continuation`; the plan lands them in reviewable parts (U3), not as one merge.

## 12. Non-goals

Replacing the model for authoring; running mutation testing or CI; touching WSL, VPS fleet or production; building a new analyzer outside AEVE; candidate worker comparison (Temporal, BMad Loop), which stays parked.
