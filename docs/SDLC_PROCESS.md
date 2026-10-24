# SDLC process of the virtual scrum team

Operated by the main session through the skill `sdlc-orchestrator`. Subagents never launch other
agents. Source: `team/skills/sdlc-orchestrator/SKILL.md` (kept short on purpose; this page is the readable summary).

| # | Phase | Role (agent) | Exit artifact |
|---|---|---|---|
| 1 | Discovery | `business-analyst` | `requirements.md` |
| 2 | Backlog | `product-owner` | `backlog.md` with stories, DoR and DoD |
| 3 | Design | `architect` / `code-architect`, `ui-designer` | `design.md`, ADRs, `ui-spec.md` |
| 4 | Docs and test plan | `technical-writer`, `functional-test-reviewer`, `e2e-runner` | design/TDD docs, `test-plan.md` |
| 5 | Doc review | relevant reviewers, then GPT-PM | review record, fixes |
| 6 | Build | `implementation-engineer` | all sprint code committed, change record per commit |
| 7 | Verify | test agents per epic, then specialists | green evidence, review consensus |
| 8 | Gate | GPT-PM APPROVE on the exact head | approval, push and ONE PR per sprint |
| 9 | Accept and release | `product-owner`, `technical-writer` | `acceptance.md`, release notes |
| 10 | Report and retro | `reporting-analyst` | sprint report, retro actions |

Rules: existing project gets one review of current docs and code and one fix pass; no tests or checks
during coding; only focused tests written and run by the test agents; reviewers use only Claude
Sonnet 5.5 medium or GPT-5.6 Luna low or medium; until the S1 state store (`tools/vst/store.py`) is in use for a project, `docs/sdlc/STATE.md` is the phase authority; once it is in use, the store is the authority and `STATE.md` is its generated read-only view (baseline decision BD-1).
Artifact templates: `docs/templates/artifact-templates.md`.
