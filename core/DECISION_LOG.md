# Decision log

Append-only. One dated entry per decision, piece of evidence or refusal.

## 2026-10-15 -- Team created from the operator's request

Operator asked for a virtual scrum team (BA, product owner, architect, UI designer, tester, developer,
PM, technical writer, reporting) following the SDLC from idea to delivery. Inventory of the existing 28
global agents and 31 skills found gaps: no BA, product owner or UI designer; weak PM, technical writer
and reporting roles. Decisions: create 5 agents and 7 skills; PM is the skill `sdlc-orchestrator` run
by the main session because subagents cannot launch other agents; reuse existing architect, developer
and tester agents; map operator aliases `adk-test-engineer` to `tdd-guide` (E2E: `e2e-runner`, test
assessment: `functional-test-reviewer`), `adk-data-engineer/perf-tuning` to `performance-optimizer`,
`adk-tune-sql-query` to `database-reviewer`. Concepts adapted from BMAD-METHOD, spec-kit and
claude-scrum-team (all inspected only through web search summaries; no text copied).
Evidence: global lint after installation reported MODEL_POLICY=PASS, 0 model violations, 0 unresolved routes;
router eval 15 of 15 fixtures passed.

## 2026-10-15 -- `functional-test-reviewer` made an author

The agent lacked Write, Edit and Bash although workflow rules require it to write and run per-epic
functional tests. Added the tools and an explicit default read-only review mode; author mode only on
the parent's request, document or test files only, never product code.

## 2026-10-15 -- Pilot lessons (RQDO G10-FEED-0)

- Turn limits of T1/T3 agents were too small for read-heavy tasks (see VST-001).
- Three independent reviewers (reliability, silent-failure, architect) found no BLOCKER but 9 MAJOR
  design defects before any code existed; GPT-PM then rejected the documentation gate with 2 BLOCKER
  and 7 MAJOR findings the internal reviewers had not found (tenant-bound identity, visibility-scoped
  removal). Lesson: internal review does not replace the GPT gate; include security-reviewer for
  trust-boundary designs when the operator allows it.
