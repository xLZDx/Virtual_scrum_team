# Virtual Scrum Team - current state (read first)

Last updated: 2026-10-25. Re-verify volatile facts (`git log --oneline -1`, `git status`) before trusting them.

## Current continuation checkpoint — S4 QA automation

Active coding/testing sprint: S4 on branch `s4-reproducible-qa-automation`; exact candidate `fd49fad2bac249f329f4020ca5c1d55e38aa9bd7`, with registry source `1012a5e15715777ea70fc63ef0c132e625eb7975`. Functional passed 59/59 selectors (114 nodes); seeded-failure passed 3/3. Integration recorded 42 pass / 6 POSIX skips / 36 policy `NOT_RUN`; API 688 pass / 5 skips / 12 policy `NOT_RUN`; E2E 55 pass / 1 policy `NOT_RUN`; regression initially recorded 843 pass / 1 failed / 11 skips / 49 policy `NOT_RUN`. A same-head regression-category rerun recorded 844 pass / 0 failed / 11 skips / 49 policy `NOT_RUN`; the failed selector also passed in three isolated reruns. The original failure is unexplained because its captured child output used `--tb=no`; the later passes do not erase the original failure. See change 0271 and `docs/sdlc/evidence/qa/`. Integration/API/regression remain `FAIL` and E2E `INCONCLUSIVE` because required skips and policy `NOT_RUN` are non-approving. The 18 primary run artifacts and three rerun artifacts match the test-only clone by SHA-256 and size. No process-kill, timeout, or `os._exit` selector ran. The POSIX platform-matrix design is recorded in change 0272 but not implemented or runtime-proven. Current repository HEAD has a documentation-only follow-up after the tested candidate. S4 remains open; specialist review and exact-head GPT-PM approval for a final code candidate are pending; no push/PR is ready.

The S2 sandbox gate remains open. S3 has local synthetic pilot evidence but candidate, sandbox, egress, and process-death acceptance remains partial. S5 remains prepared, not active, pending S2 and S4 dependencies. No push or PR is ready.

## Historical checkpoint: S3 vendor-neutral worker pilot (S2 gate remains open)

Current branch: `s3-vendor-neutral-worker-pilot`, current documentation/test HEAD `2c4e9fd0d546d26212dcffa8348fe5349386e2d3`. Source fixes are committed in `040a3f2af217f38254cf91f2cb0559fb61fe2c80`; test files were committed in `3283bface17fe01d4661f248ab8b6502647f5fb2`. Both focused functional/E2E modules were rerun by their designated test agents at exact repository HEAD `2c4e9fd`: 9/9 each, with one pytest-asyncio deprecation warning on E2E. Fresh security and reliability reviews at `3283bfa` found no valid BLOCKER/MAJOR/MINOR. Correlated GPT-PM final review APPROVED the local synthetic pilot scope at exact HEAD `7f1aa35` (request `e4f16fdc-6175-43f1-97a1-74d50e173970`, reply `7d317e5b-bff9-485f-bce5-d09390f000f3`); later S3 commits were documentation-only, and this approval explicitly does not close full S3 acceptance. The process-hook test is confined to a disposable repository; the STOP lock orders one pilot instance in one process and does not prove cross-process behavior. S3 candidate choice/acquisition, fresh S2-bound sandbox probe, external egress/replay, and process-kill cleanup remain NOT_RUN or gated. S2 remains unmerged: its latest correlated exact-head PM review returned MAJOR/MODIFY, with E4/E5/E8 acceptance gaps. No push/PR is ready. See [`core/BACKLOG.md`](BACKLOG.md) and [`reports/S3_WORKER_PILOT_2026-10-25.ru.html`](../reports/S3_WORKER_PILOT_2026-10-25.ru.html) for evidence.

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
