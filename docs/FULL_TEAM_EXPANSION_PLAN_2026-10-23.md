# Full Virtual Engineering Team — Expansion Plan

Status: PROPOSAL / SOURCE INVENTORY ONLY — NOT INSTALLED, NOT ROUTED, NOT ACCEPTED
Date: 2026-10-23
Scope: reusable, project-agnostic software delivery team. This document does not change the live SDLC router or installed agents.

## Intent and boundaries

Extend the existing ten-phase Scrum delivery workflow into a full software engineering organization. Preserve the existing `sdlc-orchestrator` as the only delegation owner; use one outcome-owning role per task with on-demand skills rather than spawning a separate process for each skill. Select specialist roles by the changed risk surface. Never activate every profile for every sprint.

The source repositories, installed profiles, execution harness and live agent behavior are distinct inventories. Existing global profiles must not be replaced or silently reconfigured. No external AI/provider calls, production deployment, destructive operation or automatic installation is authorized by this plan. Use the global model allowlist (Sonnet alias in authored team roles; never automatically select Opus), least privilege and bounded turns. Git records and role definitions are English. Keep this public repository free from personal paths, secrets, PII and project-specific content.

## Canonical responsibility split

- This repository: SDLC orchestration, generic team-specific role definitions, phase routing, acceptance templates and verification contracts.
- Reusable agent/skill library: generic specialist source profiles and portable domain skills, with installed copies verified separately.
- Existing approved execution/verification engine: deterministic routing, source digests, permission fences, evidence capture and reproducible evaluation. Do not build a second engine.
- Delivered project repository: its domain requirements, code, acceptance criteria, fixtures and exact-head evidence.

## Team catalog (39 logical roles, not 39 always-running agents)

Each logical role must resolve to exactly one qualified profile or remain UNAVAILABLE. A listed source profile is not evidence of successful installation, routing or runtime behavior.

| Group | Logical role | Candidate owner / implementation | Disposition |
|---|---|---|---|
| Product and Scrum | Business analyst | `business-analyst` | REUSE team |
| Product and Scrum | Product manager / PRD owner | `product-manager` | ADD scoped profile if no approved installed equivalent |
| Product and Scrum | Product owner / backlog | `product-owner` | REUSE team |
| Product and Scrum | Scrum master / SDLC coordinator | main-session `sdlc-orchestrator` skill | REUSE; no child delegation |
| Product and Scrum | Sprint planner / estimator | `planner` + `sprint-ceremonies` | VERIFY model routing first |
| Product and Scrum | UX / customer researcher | `ux-researcher` | ADD on demand |
| Architecture and Design | System / solution architect | `architect` | VERIFY model routing first |
| Architecture and Design | Feature / code architect | `code-architect` | REUSE library; docs hand-off |
| Architecture and Design | Data architect | `database-reviewer` + scoped data-design skill | EXTEND without promoting reviewer to approver |
| Architecture and Design | Security / trust-boundary architect | `security-architect` | ADD |
| Architecture and Design | UI / interaction designer | `ui-designer` | REUSE team |
| Architecture and Design | Accessibility specialist | `a11y-architect` | REUSE library after validation |
| Engineering | Engineering lead / technical owner | `engineering-lead` | ADD, planning/coordination only |
| Engineering | Backend / Python engineer | `implementation-engineer` + Python/FastAPI skills | VERIFY installed owner |
| Engineering | Frontend engineer | `implementation-engineer` + web UI skill | VERIFY installed owner |
| Engineering | Mobile / Flutter engineer | `implementation-engineer` + Flutter skill | VERIFY installed owner |
| Engineering | API / integration engineer | `integration-engineer` | ADD for connector-heavy scope |
| Engineering | Data / migration engineer | `data-migration-engineer` | ADD for migration/transaction scope |
| Engineering | AI / ML engineer | `ml-engineer` | REUSE library when applicable |
| Engineering | Build / refactor specialist | `build-error-resolver`, `refactor-cleaner` | REUSE risk-scoped |
| Quality Engineering | QA architect / test-strategy owner | `qa-test-architect` | ADD; specifications only |
| Quality Engineering | Functional / unit / property tests | `functional-test-reviewer` | REUSE authorized test author |
| Quality Engineering | Web E2E testing | `e2e-runner` | REUSE authorized test author |
| Quality Engineering | Mobile E2E design | `mobile-test-specialist` skill/profile | ADD skill; execution through authorized test owner |
| Quality Engineering | API / contract test design | `api-contract-test-specialist` skill/profile | ADD skill; execution through authorized test owner |
| Quality Engineering | Integration test design | `integration-test-specialist` skill/profile | ADD skill; execution through authorized test owner |
| Quality Engineering | Regression and mutation analysis | `regression-mutation-hunter` | ADD review / reproduction skill |
| Quality Engineering | Performance / load analysis | `performance-optimizer` + k6 skill | EXTEND; distinguish analysis from load execution |
| Quality Engineering | Security test analysis | `security-reviewer` + security validation skill | EXTEND; authorized targets only |
| Quality Engineering | Database integrity analysis | `database-reviewer` + DB invariant skill | EXTEND |
| Quality Engineering | Network / chaos analysis | `network-troubleshooter` + fault-injection skill | EXTEND; isolated environment only |
| Quality Engineering | Independent evidence auditor | `test-evidence-auditor` | ADD; read-only, cannot accept own tests |
| Operations and Delivery | CI/CD and build pipeline engineer | `ci-cd-engineer` | ADD; no unapproved publish |
| Operations and Delivery | SRE / observability engineer | `sre-observability-engineer` | ADD |
| Operations and Delivery | Release manager | `release-manager` | ADD; operator-reserved gates remain |
| Operations and Delivery | Technical writer | `technical-writer` | REUSE team |
| Operations and Delivery | Reporting analyst | `reporting-analyst` | REUSE team |
| Operations and Delivery | Incident / recovery reviewer | `recovery-concurrency-reviewer` | ADD risk-scoped, read-only |
| Operations and Delivery | Compliance / privacy reviewer | `privacy-compliance-reviewer` | ADD risk-scoped, read-only |

Cross-cutting existing reviewers remain available: `code-reviewer`, `python-reviewer`, `flutter-reviewer`, `fastapi-reviewer`, `silent-failure-hunter`, `code-explorer`, and other risk-specific roles. Do not count a reviewer as an implementation or test-execution owner by name alone.

## Skills to integrate selectively

| Domain | Candidate externally reviewed foundation | Required local adaptation |
|---|---|---|
| Requirements / sprint / roles | BMad Method, Spec Kit, OpenSpec | Preserve existing ten phases and artifacts; no second PM router |
| UI/UX | UI UX Pro Max | Existing components/tokens first; screenshot and accessibility evidence |
| Web E2E | Playwright Test Agents | No silent healer-induced skip or assertion weakening |
| Mobile E2E | Maestro, Patrol | Device/emulator ownership, app reset, permission and offline cases |
| API / integration | Schemathesis, Pact, Testcontainers | Isolated staging, deterministic fixtures, no production mutation |
| Property / regression | Hypothesis, Trail of Bits | Demonstrate red/green or equivalent falsifiability evidence |
| Load / performance | Grafana k6 | Approved load target, SLO thresholds, bounded intensity |
| Security | Trail of Bits, Semgrep, Trivy, OWASP ZAP | Respect explicit security test target scope |
| Database | pgTAP, Testcontainers, project-native DB harness | Migration fences, transaction and row-scope invariants |
| Network / resilience | Toxiproxy, DevTools, project-native fault injection | No unauthorized network attack, outages or device reconfiguration |
| Evidence | JUnit, SARIF, traces, test manifests | Exact HEAD, command, environment, results, reviewer independence |

Skills are additive knowledge and bounded methods; they cannot widen tool permissions or create execution authority.

## Non-negotiable constraints to reconcile before implementation

1. The workspace workflow currently makes only `functional-test-reviewer` and `e2e-runner` owners of required test authoring/execution, and mandates testing after all in-scope sprint code is complete. Other testing specialists may advise and inspect or supply on-demand skills, but must not become independent test authors without an explicit policy revision.
2. The reusable library's `architect` and `planner` source frontmatter selects Opus. The team policy forbids automatic Opus. Verify resolved installed model before routing, then use a separately approved Sonnet profile if needed; do not modify global profiles without authorization.
3. The reusable library's `tdd-guide` runs tests before code, contradicting the current sprint execution order. The orchestrator must avoid invoking that mode in the Build phase. Test plans can be written during documentation phases.
4. The reusable E2E instructions allow flaky tests to be skipped. An `xfail`, `skip`, quarantine or healer patch cannot satisfy a mandatory acceptance criterion without independently documented scope and approval.
5. `implementation-engineer`, `technical-design`, `architecture-contract`, `verification-contract` and other names referenced by the orchestrator must be resolved against the installed inventory; they are not proven to exist merely because the roster names them.
6. Every final review and approval must bind to the same committed HEAD. New source commits invalidate prior code acceptance.
7. Retain exact test evidence: commands, collection list, environment, HEAD, exit codes, counts, artifacts and `NOT_RUN` dependencies, not agent claims alone.
8. Keep a single source of truth for phase state; do not confuse proposed definitions with installed or running profiles.
9. Only necessary roles run per risk map. Use the existing concurrency cap and isolate incompatible writes. External AI reviewers require separate authorization.
10. Preserve existing unrelated work. Publish, merge, production changes, deletion, real money and credential changes keep their reserved approvals.

## Implementation sequence

### P0 — Repair foundational correctness (before expansion)
- Resolve live inventory / source drift and model routing without changing installed copies.
- Close existing backlog issues VST-007 (retained evidence) and VST-008 (exact-head gate).
- Define deterministic PASS / FAIL / BLOCKED / NOT_RUN / INCONCLUSIVE result schema.
- Establish role-to-skill compatibility and permission matrix; detect unresolved aliases.
- Add executable evaluation fixtures for phase routing and the evidence contract.

### P1 — Complete source roster
- Reuse existing suitable profiles first.
- Draft only missing bounded profiles with Sonnet alias, least-privilege tools, scope/trigger, required evidence and explicit forbidden actions.
- Add focused skills and reference files; do not inline large reference corpora in agent bodies.
- Keep author, implementer, reviewer, acceptance and release authorities separate.
- Keep a migration manifest; no wholesale replacement of any installed agent/skill.

### P2 — Bounded execution adapters
- Wire existing approved test runners and orchestration engine, not new LLM runtimes.
- Validate CLI/tool availability and permission on isolated fixtures.
- Make the two authorized test owners execute relevant test categories through selected skills, with specialist reviews after testing.
- Emit local immutable-ish evidence records bound to source and test hashes.

### P3 — Adversarial qualification
- Replay seeded defects for each specialist; prove tests fail when the target bug exists.
- Run negative routing tests: unauthorized roles, duplicate aliases, missing tools, model policy, stale HEAD, skipped tests, provider outage, missing evidence, timeout and crash.
- Compare findings, false positives, escaped defects, duplicate work, runtime and context cost.
- Verify source-only changes do not masquerade as installed/routed functionality.

### P4 — Pilot and controlled activation
- Run on a non-production synthetic sprint first, then one approved real sprint.
- Repeat exact-head reviews, test evidence and acceptance gate.
- Install or enable profiles separately with operator authority and required validation.
- Update roster, changelog, decision log, generated document registry and runbook before closure.

## Acceptance definition

The expansion is accepted only if all 39 logical roles are either mapped to a working, approved profile with evidence or marked explicitly OPTIONAL / UNAVAILABLE; no ambiguous alias remains; all mandatory tasks have a unique outcome owner; existing ten-phase workflow and global authority constraints remain intact; routing and negative tests pass; test evidence is on exact HEAD; no test skip masquerades as green; external AI remains off unless authorized; and the operator's install/push/release gates remain separate.

This document records a design proposal and a read-only source inventory. It is not runtime verification or permission to deploy.
