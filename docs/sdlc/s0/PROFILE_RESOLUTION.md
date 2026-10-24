# S0 profile resolution

**Observed on:** 2026-10-24
**Method (read-only):** directory listings, front-matter `model:` and `maxTurns:` lines, and byte/text comparison of files. No installed file was edited. `<claude-home>` below is the operator's installed Claude configuration folder (`agents/` and `skills/` inside it); `<workspace>` is the local repository root.

Resolution classes:

- (a) a file under this repository's `team/`;
- (b) an installed file under `<claude-home>/agents` or `<claude-home>/skills`;
- (c) unresolved: no file in (a) or (b). A name that exists only in the `agents-skills-repo` source and is not installed is also (c) for execution purposes.

Status definitions used by S0 (static evidence only, no runtime qualification was performed):

- **QUALIFIED**: resolves to a tracked file in this repository, the installed copy is byte-identical, model alias conforms to policy, `maxTurns` is set, and every skill the role needs is named and resolves.
- **PARTIAL**: resolves, but at least one of: no tracked source in this repository, installed copy differs from the tracked copy, a required skill is unnamed or unresolved, or the role is only a composite of an existing agent plus new duties.
- **UNAVAILABLE**: unresolved (class c). Per the blueprint (S2 exit) an unresolved alias blocks execution.

No role is "runtime qualified": no role-invocation harness, role hash manifest or receipt exists yet (S1 and S2 scope). QUALIFIED here means "static checks passed", not "proven working".

## 1. Orchestrator roster (`team/skills/sdlc-orchestrator/references/team-roster.md`)

| Name used by the roster | Class | Where | Model alias | maxTurns | Note |
|---|---|---|---|---|---|
| `business-analyst` | a + b | team and installed, identical | sonnet | 14 | |
| `product-owner` | a + b | identical | sonnet | 14 | |
| `ui-designer` | a + b | identical | sonnet | 16 | |
| `technical-writer` | a + b | identical | sonnet | 14 | |
| `reporting-analyst` | a + b | **differ**: installed copy still says phase comes from `docs/sdlc/STATE.md`; team copy names the S1 state authority | sonnet | 12 | Installed copy is older; re-install is an operator item |
| `functional-test-reviewer` | a + b | identical | sonnet | 25 | Authorized test author (ADR-0001) |
| `architect` | b | installed only | sonnet | 16 | Source in `agents-skills-repo` says `opus` (see section 4) |
| `code-architect` | b | installed only | sonnet | 20 | |
| `implementation-engineer` | b | installed only | sonnet | 20 | Not in `agents-skills-repo` |
| `tdd-guide` | b | installed only | sonnet | 24 | Advisory only (ADR-0001) |
| `e2e-runner` | b | installed only | sonnet | 24 | Authorized test author (ADR-0001) |
| `performance-optimizer` | b | installed only | sonnet | 15 | Advisory only (ADR-0001) |
| `database-reviewer` | b | installed only | sonnet | 15 | |
| `silent-failure-hunter` | b | installed only | sonnet | 12 | |
| `code-explorer` | b | installed only | sonnet | 16 | |
| `build-error-resolver` | b | installed only | sonnet | 15 | |
| `refactor-cleaner` | b | installed only | sonnet | 12 | Source says `haiku` |
| `doc-updater` | b | installed only | sonnet | 12 | Source says `haiku` |
| `python-reviewer` | b | installed only | sonnet | 10 | |
| `code-reviewer` | b | installed only | sonnet | 12 | |
| Skill `e2e-testing-contract` | b | installed only | n/a | n/a | |
| Skill `functional-testing` | b | installed only | n/a | n/a | |
| Skill `performance-testing` | b | installed only | n/a | n/a | |
| Skill `db-change-contract` | b | installed only | n/a | n/a | |
| Skill `sdlc-orchestrator` | a + b | **differs** (installed `SKILL.md` and `references/team-roster.md` are older) | n/a | n/a | |
| Skills `sdlc-metrics`, `sprint-ceremonies` | a + b | **differ** (installed older) | n/a | n/a | |
| Skills `backlog-and-dod`, `release-documentation`, `requirements-elicitation`, `ui-design-contract` | a + b | identical | n/a | n/a | |
| Alias `adk-test-engineer` (3 roster rows) | c | no file | n/a | n/a | Roster maps it to `tdd-guide`, `e2e-runner`, `functional-test-reviewer`; launching under the alias name is unresolved |
| Alias `adk-data-engineer/perf-tuning` | c | no file | n/a | n/a | Maps to `performance-optimizer` |
| Alias `adk-tune-sql-query` | c | no file | n/a | n/a | Maps to `database-reviewer` |

Roster summary: 20 real agent names, all 20 resolve (6 with a tracked source, 14 installed only); 4 named skills resolve plus 7 team skills resolve; 3 operator aliases do not resolve as names and must be launched under the mapped real name.

## 2. The 39-role catalog (`docs/FULL_TEAM_EXPANSION_PLAN_2026-10-23.md`)

| # | Logical role | Candidate owner | Class | Status | Reason |
|---|---|---|---|---|---|
| 1 | Business analyst | `business-analyst` | a + b | QUALIFIED | identical copies, sonnet |
| 2 | Product manager / PRD owner | `product-manager` | c | UNAVAILABLE | no file anywhere |
| 3 | Product owner / backlog | `product-owner` | a + b | QUALIFIED | identical copies |
| 4 | Scrum master / coordinator | `sdlc-orchestrator` skill (main session) | a + b | PARTIAL | installed skill copy is older than the tracked one |
| 5 | Sprint planner / estimator | `planner` + `sprint-ceremonies` | b + (a+b) | PARTIAL | `planner` installed only (source says `opus`); `sprint-ceremonies` copy differs |
| 6 | UX / customer researcher | `ux-researcher` | c | UNAVAILABLE | no file |
| 7 | System architect | `architect` | b | PARTIAL | installed only; source `opus` vs installed `sonnet` |
| 8 | Feature / code architect | `code-architect` | b | PARTIAL | installed only |
| 9 | Data architect | `database-reviewer` + "scoped data-design skill" | b + unnamed | PARTIAL | the skill is not named and does not resolve |
| 10 | Security / trust architect | `security-architect` | c | UNAVAILABLE | no file |
| 11 | UI / interaction designer | `ui-designer` | a + b | QUALIFIED | identical copies |
| 12 | Accessibility specialist | `a11y-architect` | b | PARTIAL | installed only |
| 13 | Engineering lead | `engineering-lead` | c | UNAVAILABLE | no file |
| 14 | Backend / Python engineer | `implementation-engineer` + "Python/FastAPI skills" | b + unnamed | PARTIAL | skills unnamed |
| 15 | Frontend engineer | `implementation-engineer` + "web UI skill" | b + unnamed | PARTIAL | skill unnamed |
| 16 | Mobile / Flutter engineer | `implementation-engineer` + "Flutter skill" | b + unnamed | PARTIAL | skill unnamed |
| 17 | API / integration engineer | `integration-engineer` | c | UNAVAILABLE | no file |
| 18 | Data / migration engineer | `data-migration-engineer` | c | UNAVAILABLE | no file |
| 19 | AI / ML engineer | `ml-engineer` | b | PARTIAL | installed only |
| 20 | Build / refactor specialist | `build-error-resolver`, `refactor-cleaner` | b | PARTIAL | installed only; `refactor-cleaner` source says `haiku` |
| 21 | QA architect / test strategy | `qa-test-architect` | c | UNAVAILABLE | no file |
| 22 | Functional / unit / property tests | `functional-test-reviewer` | a + b | QUALIFIED | identical copies; authorized author |
| 23 | Web E2E testing | `e2e-runner` | b | PARTIAL | installed only; authorized author |
| 24 | Mobile E2E design | `mobile-test-specialist` | c | UNAVAILABLE | no file |
| 25 | API / contract test design | `api-contract-test-specialist` | c | UNAVAILABLE | no file |
| 26 | Integration test design | `integration-test-specialist` | c | UNAVAILABLE | no file |
| 27 | Regression and mutation analysis | `regression-mutation-hunter` | c | UNAVAILABLE | no file; mutation runs are NOT_RUN by ADR-0001 |
| 28 | Performance / load analysis | `performance-optimizer` + "k6 skill" | b + unnamed | PARTIAL | skill unnamed; advisory only |
| 29 | Security test analysis | `security-reviewer` + "security validation skill" | b + unnamed | PARTIAL | skill unnamed |
| 30 | Database integrity analysis | `database-reviewer` + "DB invariant skill" | b + unnamed | PARTIAL | skill unnamed |
| 31 | Network / chaos analysis | `network-troubleshooter` + "fault-injection skill" | c | UNAVAILABLE | exists only in the `agents-skills-repo` source, not installed; skill unnamed |
| 32 | Independent evidence auditor | `test-evidence-auditor` | c | UNAVAILABLE | no file |
| 33 | CI/CD engineer | `ci-cd-engineer` | c | UNAVAILABLE | no file; also inactive, no CI authorized (ADR-0001) |
| 34 | SRE / observability engineer | `sre-observability-engineer` | c | UNAVAILABLE | no file |
| 35 | Release manager | `release-manager` | c | UNAVAILABLE | no file |
| 36 | Technical writer | `technical-writer` | a + b | QUALIFIED | identical copies |
| 37 | Reporting analyst | `reporting-analyst` | a + b | PARTIAL | installed copy differs from tracked copy |
| 38 | Recovery / concurrency reviewer | `recovery-concurrency-reviewer` | c | UNAVAILABLE | no file; the installed `reliability-reviewer` is a related profile but no mapping was decided, so it is not substituted |
| 39 | Compliance / privacy reviewer | `privacy-compliance-reviewer` | c | UNAVAILABLE | no file |

Tally: QUALIFIED 5, PARTIAL 16, UNAVAILABLE 18 (total 39).

## 3. Unresolved aliases (these block execution per the blueprint)

Unresolved agent names (18): `product-manager`, `ux-researcher`, `security-architect`, `engineering-lead`, `integration-engineer`, `data-migration-engineer`, `qa-test-architect`, `mobile-test-specialist`, `api-contract-test-specialist`, `integration-test-specialist`, `regression-mutation-hunter`, `network-troubleshooter` (source only, not installed), `test-evidence-auditor`, `ci-cd-engineer`, `sre-observability-engineer`, `release-manager`, `recovery-concurrency-reviewer`, `privacy-compliance-reviewer`.

Unresolved operator aliases (3): `adk-test-engineer`, `adk-data-engineer/perf-tuning`, `adk-tune-sql-query` (mapped by the roster to real agents; usable only under the real name).

Unnamed skill references in the catalog (8): scoped data-design skill, Python/FastAPI skills, web UI skill, Flutter skill, k6 skill, security validation skill, DB invariant skill, fault-injection skill. These cannot be resolved because they have no name; installed skills with similar purpose exist (for example contract skills for security evidence, observability, migration safety) but no mapping was decided, so none is assumed.

Total blocking unresolved items: 18 agent names + 3 aliases + 8 unnamed skill references = 29.

## 4. Model-policy facts

Installed agents (observed): 33 files in `<claude-home>/agents`; every one carries `model: sonnet` and a `maxTurns` value. No installed file selects `opus` or `haiku`. That the alias `sonnet` resolves to Sonnet 5.5 or newer is governed by the operator's control-plane policy; it could not be proven from the agent files and the control-plane lint was not run in S0.

Source repository `agents-skills-repo/agents` (observed, 36 files with a `model:` line): 29 `sonnet`, 5 `haiku` (`comment-analyzer`, `doc-updater`, `opensource-sanitizer`, `pr-test-analyzer`, `refactor-cleaner`), 2 `opus` (`architect`, `planner`). Haiku is not permitted for agents by the operator's global contract and Opus is never automatic. So the installed copies are policy-conformant while their source is not: re-syncing from source over the installed set would reintroduce the violations. Of the 33 installed agents, 24 also exist in the source and all 24 differ from it byte-wise; for five sampled files (`architect`, `tdd-guide`, `e2e-runner`, `security-reviewer`, `planner`) the difference remains after line-ending normalization, so the installed set was rewritten rather than copied. 9 installed agents are not in the source at all: `business-analyst`, `functional-test-reviewer`, `implementation-engineer`, `product-owner`, `product-ux-reviewer`, `reliability-reviewer`, `reporting-analyst`, `technical-writer`, `ui-designer` (6 of them have tracked copies in this repository).

Correction note: the blueprint (sections 4 and 5) says the installed `architect` and `planner` are Opus-selecting. That is not what is installed on 2026-10-24: both are `sonnet`. The Opus selection exists only in the `agents-skills-repo` source files.

Policy to compare against:

| Rule | Value |
|---|---|
| Agent model minimum | Sonnet 5.5 |
| Opus | never automatic; only an explicit operator authorization per run, high effort |
| Reviewer and test agents | Sonnet 5.5 medium effort, or GPT-5.6 Luna at low or medium effort; no GPT-5.6 Sol; no silent substitution |
| Haiku and lower families | not permitted for agents |

Three known model-policy sources and their precedence:

| Source | What it says | Status |
|---|---|---|
| Workspace `AGENTS.md` (outside this repository) | Default reviewer and test agent model is GPT-6 Luna at low or medium effort; GPT-5.6 Luna only as an operator-selected consensus override | DRIFT: names a model the other sources do not allow as default |
| Operator global contract | Sonnet 5.5 medium or GPT-5.6 Luna low/medium; no Sol; Opus never automatic | Governing source |
| This repository (`README.md`, `docs/SDLC_PROCESS.md`, `sdlc-orchestrator/SKILL.md`; repository `AGENTS.md` sets only the alias `sonnet` and has no Luna text) | Sonnet 5.5 medium or GPT-5.6 Luna low/medium | Agrees with the global contract |

Precedence decided by ADR-0001 (for this repository): the operator's global contract governs. The workspace `AGENTS.md` correction is outside this repository and still open; until it is done, any role launch follows the global contract.

## 5. S0 open items for the operator

These are reported only; S0 changed nothing outside `docs/`.

1. **Workspace `AGENTS.md` model default.** Lines near 63 to 69 name GPT-6 Luna as the ordinary reviewer and test-agent model. ADR-0001 chose the global contract's wording. Consequence of editing: the workspace file agrees with the global contract and this repository; consequence of leaving it: any session that follows the workspace file launches reviewers on a model the contract does not list.
2. **Global contract test-author list.** The contract still lists four test-writing agents (`tdd-guide`, `performance-optimizer`, `e2e-runner`, `functional-test-reviewer`); ADR-0001 allows only `functional-test-reviewer` and `e2e-runner`. Consequence of editing: a single list; consequence of leaving it: the installed global rule and this repository disagree on who may author required tests.
3. **Personal DC project misbinding for AEVE.** Observed read-only: the Personal DC project registry file `config/projects.json` maps the alias `AEVE` to a frozen temporary snapshot folder (`AEVE-clean-runtime-6787c8db` under the temporary directory), not to `<workspace>/AEVE`, which is the development checkout (branch `codex/real-repo-hardening-2`, HEAD `e26ca48`). Other aliases in that file: `Personal_DC`, `ERP_MCP`, `ERP_MCP_ChatGPT` (target folder is absent from the workspace listing), `PDCC`, `AI_Trading`, `Fitness_App`, `PM_Bridge`. Personal DC docs and tests also reference the snapshot, so the binding appears intentional for its showcase bridge; changing it needs a scoped configuration change under approval and the frozen snapshot must be preserved. Consequence of leaving it: AEVE work routed through Personal DC runs against the frozen snapshot, not current code.
4. **Installed copies lag the tracked ones.** Installed `reporting-analyst`, `sdlc-orchestrator`, `sdlc-metrics` and `sprint-ceremonies` (and the installed roster file) differ from the tracked S1 versions. Re-install needs a snapshot first and the global lint afterwards (baseline section 6).
5. **Source repository drift.** `agents-skills-repo` still carries `opus` and `haiku` model values. Decide whether to correct the source (a change in that repository) before any manifest references its hashes.
6. **Two undeclared repositories.** `pm-bridge-codex` and `Remote_Quality_Delivery_Office_Platform_rqdo` have no role in the blueprint.
7. **Private component names in a public repository** (blueprint O-1) remain an operator decision.

## Not verified

- Whether the alias `sonnet` is bound to Sonnet 5.5 or newer at launch time.
- That any agent can actually be launched and obeys its tool list; no role was invoked.
- Content of `tools:` front-matter beyond `model` and `maxTurns` was not evaluated.
- The control-plane lint and router checks were not run.
