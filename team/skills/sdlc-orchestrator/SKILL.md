---
name: sdlc-orchestrator
description: Drive a project through the SDLC from idea to release with a scrum-style virtual team. Use at project/sprint start, at every phase transition, and when asked for process status. The main session runs it; subagents cannot launch other agents.
---

# sdlc-orchestrator

## Apply when
A project or sprint needs to move through phases with the right specialist at each step.

## Method
1. Read `docs/sdlc/STATE.md` (create from `references/artifact-templates.md` if missing). It is the only source of phase truth; confirm HEAD with git.
2. Find the current phase below; launch ONLY that phase's role agents (actual Agent runs, never in-chat role play). Each role writes its artifact to `docs/sdlc/`.
3. When every exit artifact of the phase exists and is linked in STATE.md, advance the phase. Record head, date, artifact paths and the agents/models actually used.
4. Reviewer agents use only Sonnet 5.5 medium or GPT-5.6 Luna low/medium. Opus is never automatic.

## Phases, roles, exit artifacts
| # | Phase | Role (agent) | Exit artifact |
|---|---|---|---|
| 1 | Discovery | `business-analyst` (skill `requirements-elicitation`) | requirements.md, glossary, open questions |
| 2 | Backlog | `product-owner` (`backlog-and-dod`) | prioritized backlog, stories with DoR/DoD, sprint goal |
| 3 | Design | `architect`/`code-architect` (`technical-design`, `architecture-contract`), `ui-designer` (`ui-design-contract`) | design.md, ADRs, ui-spec.md |
| 4 | Docs + test plan | `technical-writer`, `functional-test-reviewer`, `e2e-runner` | TDD, acceptance->test map |
| 5 | Doc review | relevant reviewers (`agent-consensus`), then GPT-PM | review record, fixes applied |
| 6 | Build | `implementation-engineer` (`implementation-workflow`) | all sprint code committed, change record per commit |
| 7 | Verify | test agents write+run per-epic functional/E2E sets, then specialists | green evidence, review consensus |
| 8 | Gate | GPT-PM APPROVE on exact head | approval id; then push + ONE PR per sprint |
| 9 | Accept + release | `product-owner` acceptance, `technical-writer` (`release-documentation`) | acceptance.md, release notes |
| 10 | Report + retro | `reporting-analyst` (`sdlc-metrics`), `sprint-ceremonies` | sprint report, retro actions |

## Rules
- Existing project: one review of current docs/code, one fix pass; do not rewrite settled documents.
- Phase 6 runs no tests or checks (delivery-efficiency v4). Phase 7 runs only test-agent-authored focused tests. Never full suites, lint, typecheck, build or CI.
- Gating applies only to irreversible actions and the push/PR gate; missing artifacts are reported and produced, not used as extra approval steps.
- When sprint testing starts, delegate next-sprint doc review in parallel.
- Project architecture and domain rules stay in that project; never import them from siblings.

## Required output
Current phase, artifacts present/missing, next role to launch, agents and models actually run.

## Do not
Skip a phase silently; let an implementer approve its own work; simulate roles in chat; add per-step approval prompts.

Full team roster with agent names and aliases: `references/team-roster.md`. Templates and origins: `references/artifact-templates.md`.
