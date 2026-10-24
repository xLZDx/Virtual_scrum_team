# Virtual Scrum Team - current state (read first)

Last updated: 2026-10-24. Re-verify volatile facts (`git log --oneline -1`, `git status`) before trusting them.

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

## Unified organization design (proposal)

`docs/UNIFIED_ENGINEERING_ORGANIZATION_MASTER_BLUEPRINT_2026-10-23.md` and its review dossier are a
proposal with verdict MODIFY DESIGN (Round 1 and Round 2 reviews; a Round 3 self-check by the
authoring session confirmed it). That design review history (2026-10-23) is kept as written: no design
blocker was closed by it. Implementation has since started with S1 (see below). Open operator
decisions: test-authoring authority (workspace `AGENTS.md`, `team-roster.md` and the global contract
disagree), model-allowlist precedence, CI ownership, a distinct verdict for NOT_RUN waivers, and the
public-repository inventory question (blueprint section 13.6).

## S1 control-plane core (in progress)

Implemented in `tools/vst` on branch `s1-control-plane-core`: contracts, signing, gate, store, runner
and slice. Three remediation rounds followed specialist reviews. The third round is implemented,
retested (E1+E2 863 passed, E3+E4 593 passed with 2 skipped, E5 64 passed on the working tree) and
committed locally as 176a095; a fourth specialist check found one regression (a task with
`cost_cap` 0 could never start) that is fixed in the next local commit and still needs focused
tests. Independent review and the pull request are pending. Nothing is pushed. Until the state store (`tools/vst/store.py`) is in use for a
project, `docs/sdlc/STATE.md` is the phase authority; once it is in use, the store is the authority
and `STATE.md` is its generated read-only view (baseline decision BD-1).

## Open items

See `core/BACKLOG.md`.

## Remote

`origin` = `https://github.com/xLZDx/Virtual_scrum_team.git` (public). `origin/main` is at `9b5b597`
(verified with `git ls-remote` on 2026-10-24, pushed on the operator's instruction); the commits of
branch `s1-control-plane-core` are local and not pushed. Pushing is a separate explicit operator
command. The first commit `0a5821b` on `origin/main` contains a local
absolute path in this file; the operator decided on 2026-10-23 to keep history unrewritten.
