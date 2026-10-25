# Virtual Scrum Team - current state (read first)

Last updated: 2026-10-25. Re-verify volatile facts (`git log --oneline -1`, `git status`) before trusting them.

## Active sprint: S2 isolated worker sandbox

Current branch: `s2-isolated-worker-sandbox`. Latest implementation source: `6ee97cb06b52900c3c2ab2a9b1b415ae117a7932`; the focused functional run is at test HEAD `deed6abe34eeaa8620593442bcdb1413d846f798`. A later WSL E2E subset ran at source/test HEAD `ed723a953d51b92827d3977c96e833258a38342c`: 109 passed / 11 skipped across 120 collected. The E6 diff-gate module then passed 17/17 at repository/test HEAD `6b426b775e7ce92ad2fe6d42c1ede7f620ee4994`. Exact evidence is linked from `docs/sdlc/STATE.md`. Earlier Phase 7 functional/E2E and specialist-review evidence applies to source HEAD `dc95915018b80f498d5cf775363712fb915fe04e`; it is not inherited by later code. Process-kill/kill-table, post-start overflow cleanup, Windows Job Object nesting, full POSIX containment, and complete E8 crash/resume remain `NOT_RUN`; OS memory/temp-storage quotas and workspace binding remain `NOT_VERIFIED`. Phase 8 GPT-PM exact-head approval is pending for the final repository HEAD, so no push/PR is ready. See [`docs/sdlc/STATE.md`](../docs/sdlc/STATE.md), [`core/BACKLOG.md`](BACKLOG.md), and the bilingual S2 report for evidence and next steps.

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

## S1 control-plane core (merged to main)

Code is complete in `tools/vst` (merged from branch `s1-control-plane-core`): contracts, signing, gate, store,
runner and slice. Four specialist review rounds are closed with no open BLOCKER or MAJOR. Focused
tests are green: E1+E2 863 passed; E3+E4 593 passed with 2 skipped; E5 64 passed; E1, E2, E3 and E5
together 1205 passed and 1 skipped after the zero-cost-cap fix (a task with `cost_cap` 0 could never
start; the fix is committed). A fresh independent review then returned MODIFY with two MAJOR store
defects (the per-epoch slot bound counted PASS receipts; `acquire_lease` committed a terminal budget
marker at spent equal to cap); both are fixed (change record 0031) and re-tested: E1+E2+E3 1193
passed, 1 skipped; E4 289 passed, 1 skipped; E5 72 passed. The GPT-PM final gate returned APPROVE for
the exact head `abc0d50`; pull request 1 (S0 + S1) was merged into `origin/main` as `d5cd7f5` on
2026-10-24 on the operator's authorization. The S0 inventory documents are in `docs/sdlc/s0/`
(change record 0028). The earlier S2 execution entry is historical: current test and runtime evidence is recorded in `docs/sdlc/STATE.md` and `docs/sdlc/evidence/`, with implementation records 0036-0054 and verification/evidence records 0056-0063. The base `6117ba24` was verified against `origin/main` before the branch was created. Until a VST store instance is initialized as this repository's phase-state authority, `docs/sdlc/STATE.md` is the phase record; at that cutover the store becomes authoritative and `STATE.md` becomes a generated read-only view (baseline decision BD-1).

## Open items

See `core/BACKLOG.md`.

## Remote

`origin` = `https://github.com/xLZDx/Virtual_scrum_team.git` (public). `git ls-remote origin refs/heads/main`
reported `6117ba24b08a260b42402db6da0bf767864e1c04` on 2026-10-24; local `main` matched it before the S2 branch was created. Merge `d5cd7f5` and follow-ups are present; branch `s1-control-plane-core` is kept on the remote. The first commit `0a5821b` on `origin/main` contains a local
absolute path in this file; the operator decided on 2026-10-23 to keep history unrewritten.
