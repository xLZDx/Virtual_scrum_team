# Virtual Scrum Team - current state (read first)

Last updated: 2026-10-15. Re-verify volatile facts (`git log --oneline -1`, `git status`) before trusting them.

## What exists

- 5 new agents (`business-analyst`, `product-owner`, `ui-designer`, `technical-writer`,
  `reporting-analyst`) and the amended `functional-test-reviewer` in `team/agents/`.
- 7 skills in `team/skills/` (`sdlc-orchestrator` with templates and roster, `requirements-elicitation`,
  `backlog-and-dod`, `sprint-ceremonies`, `ui-design-contract`, `release-documentation`, `sdlc-metrics`).
- Installed copies in `%USERPROFILE%\.claude\agents` and `...\skills` were created from the same
  content on 2026-10-15; the global lint (`agentctl.py --strict`) passed with model policy PASS.

## Pilot

First pilot: sprint G10-FEED-0 in the RQDO repository (a separate local checkout,
branch `g10-feed-0`). Phases 1-5 round 1 produced requirements, backlog, design and test plan; GPT-PM
documentation review round 1 returned REJECT (2 BLOCKER, 7 MAJOR) and remediation was in progress.
Pilot observations that change the team definitions are recorded in `core/DECISION_LOG.md`.

## Open items

See `core/BACKLOG.md`.

## Remote

`origin` = `https://github.com/xLZDx/Virtual_scrum_team.git` (public, empty at creation). Nothing has
been pushed; pushing is a separate explicit operator command.
