# Virtual Scrum Team

A virtual scrum team for Claude Code: specialist agents and skills that carry a project through the
SDLC, from idea to full delivery, with one role per responsibility and written artifacts at every
phase.

This repository is the **source of truth** for the team's definitions. Installed copies in
`~/.claude/` are separate files and do not track this repository (see "Install").

## Roles

| Role | Agent |
|---|---|
| Business analyst | `business-analyst` |
| Product owner | `product-owner` |
| Architect | `architect`, `code-architect` (existing global agents) |
| UI designer | `ui-designer` |
| Tester | `e2e-runner`, `functional-test-reviewer` (authors and runners); `tdd-guide` is advisory only (ADR-0001) |
| Developer | `implementation-engineer` |
| Project manager / scrum master | skill `sdlc-orchestrator` (run by the main session) |
| Technical writer | `technical-writer` |
| Reporting | `reporting-analyst` |

Full roster, aliases and phase mapping: `team/skills/sdlc-orchestrator/references/team-roster.md`.

## Process

Ten phases, each with a role and an exit artifact: Discovery, Backlog, Design, Docs and test plan,
Doc review, Build, Verify, Gate, Accept and release, Report and retro. See `docs/SDLC_PROCESS.md`.
Project state lives in `docs/sdlc/STATE.md` of the project being delivered. Once the S1 state store (`tools/vst/store.py`) is in use, the store is the authority and `STATE.md` is its generated read-only view (baseline decision BD-1).

## Layout

| Path | Content |
|---|---|
| `team/agents/` | Agent definitions authored for this team (new roles and the changed `functional-test-reviewer`) |
| `team/skills/` | Skills: `sdlc-orchestrator`, `requirements-elicitation`, `backlog-and-dod`, `sprint-ceremonies`, `ui-design-contract`, `release-documentation`, `sdlc-metrics` |
| `docs/` | Process, templates, change records, document index |
| `core/` | Current state, backlog and decision log of this project |
| `governance/` | Definition of Done and the generated document registry |
| `tools/` | Maintenance tools (`build_document_registry.py`) |
| `tests/`, `reports/` | Test files and generated reports |

## Install

Installation is a manual copy; installed copies do not track this repository.

```
copy team\agents\*.md  %USERPROFILE%\.claude\agents\
xcopy /E /I team\skills\<name>  %USERPROFILE%\.claude\skills\<name>
```

Agents must use the `sonnet` model alias (Claude Sonnet 5.5 minimum). Reviewer runs use only Claude
Sonnet 5.5 at medium effort or GPT-5.6 Luna at low or medium effort. No secrets, no PII and no
project-specific domain rules belong in this repository.

## Origins

Phase and role structure adapted conceptually from BMAD-METHOD (MIT), GitHub spec-kit (MIT) and
claude-scrum-team. No upstream text was copied.

## License

Not chosen yet.
