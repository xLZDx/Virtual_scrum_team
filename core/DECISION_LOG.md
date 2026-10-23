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

## 2026-10-15 -- Team fixes after the RQDO pilot (VST-001 done)

- Raised `maxTurns` of the agents that hit their limit in the pilot (see VST-001); `functional-test-reviewer` stays at the lint cap of 25. Snapshot of the previous definitions: `~/.claude/control-plane/snapshots/team-fixes-before-2026-10-15/`. After the change `agentctl.py --strict` shows only a pre-existing ERP CLAUDE.md size error and `run_eval.py --router` passes 15/15.
- Added a "Reporting discipline" section to `security-reviewer`, `silent-failure-hunter` and `reliability-reviewer`: the final message must contain full findings in the finding contract, never only titles, and the agent must report early when turns run out.
- Pilot lessons: (1) GPT-PM final review rejected a head whose evidence was only agent-reported with no retained run record: keep `docs/sdlc/evidence/` files (VST-007); (2) a security review must name the exact committed head, and a later source commit invalidates it (VST-008); (3) tests written from the plan and design found five real defects (DNS failure outcome, Retry-After shortening, missing source time, deadline precedence, tenant mismatch handling) and the GPT-PM review found three more that tests and three specialist reviews missed (rescan authority, terminal-path deadline, freshness aggregate consistency): keep the final GPT gate; (4) large multi-epic test authoring is better split per epic.

## 2026-10-15 -- License: MIT (VST-003 done)

The operator asked for a license to be set after MIT and Apache-2.0 were named as the usual options. MIT was chosen as the simplest permissive license; the copyright holder is the repository owner handle `xLZDx`. Change: add `LICENSE`. Reversible by a later relicense commit; earlier commits remain under the terms they were published with (none stated).

## 2026-10-23 -- Unified organization design: MODIFY after devil's-advocate review

Evidence: six read-only reviewer agents (architecture, security, reliability, test strategy, silent-failure, consistency) all returned MODIFY DESIGN for the proposed integration blueprint. Decision: keep the architectural boundaries (Virtual Scrum Team as the single SDLC authority, workers never self-approve, PM Bridge only at closure, `NOT_RUN` never becomes `PASS`) and withdraw the earlier "DESIGN GO" wording. Six items (signed receipts, a total gate verdict function, a fenced state store, append-only receipts with terminal failure states, an ADR for test order / CI / mutation policy, enforced concurrency and cost limits) are required before the worker pilot S3. Open operator decisions: whether private repository names stay in this public repo (O-1), whether more than two agents may author tests (O-2), whether any CI outside phase 7 is allowed (O-3). Details: blueprint section 13, dossier section 11, change record `docs/changes/0004-unified-organization-blueprint-and-review-amendments.md`. Reversible: documentation only.
