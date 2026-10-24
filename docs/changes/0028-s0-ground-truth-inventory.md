# Change record 0028: S0 ground-truth inventory

## What changed
- Added `docs/sdlc/s0/REPO_REGISTRY.md`: git state (branch, short HEAD, dirty count, last commit date, origin presence) of 12 local repositories with their organizational role, observed 2026-10-24.
- Added `docs/sdlc/s0/PROFILE_RESOLUTION.md`: resolution of every roster and 39-role catalog name to a tracked file, an installed file, or unresolved; QUALIFIED / PARTIAL / UNAVAILABLE status; model-policy facts and the three policy sources; S0 open items for the operator.
- Added `docs/sdlc/s0/TOOLS_CAPABILITY_MATRIX.md`: availability, risk and license of the tools named in the blueprint, with the exact probe that was run for each.

## Why
Sprint S0 ("Ground truth") of the blueprint roadmap needs a registry of repositories, a profile-resolution table and a tools matrix before S2 routing can rely on them. Unresolved aliases block execution, so they must be listed explicitly.

## Key results
- Roles: 5 QUALIFIED, 16 PARTIAL, 18 UNAVAILABLE of 39; 18 unresolved agent names, 3 unresolved operator aliases, 8 unnamed skill references.
- Model drift: installed agents are all `sonnet`; the `agents-skills-repo` source still has 2 `opus` and 5 `haiku` agents; the workspace `AGENTS.md` still names GPT-6 Luna as the default reviewer model.
- Dirty repositories at observation time: 10 of 12 had uncommitted files (only `MegaGpt/MetaGPT` and `Personal_DC` were clean; `Personal_Decision_Command_Center` 366, `Fitness_App` 226, `ERP_MCP` 103 were the largest).
- Installed copies of `reporting-analyst`, `sdlc-orchestrator`, `sdlc-metrics`, `sprint-ceremonies` are older than the tracked versions.

## Paths
- `docs/sdlc/s0/REPO_REGISTRY.md`
- `docs/sdlc/s0/PROFILE_RESOLUTION.md`
- `docs/sdlc/s0/TOOLS_CAPABILITY_MATRIX.md`
- `docs/changes/0028-s0-ground-truth-inventory.md`

## Contracts affected
None. Documentation only. No schema, code, workflow or installed file changed.

## Verification state
Read-only commands only: `git status --short | wc -l`, `rev-parse`, `remote -v`, `log -1`, directory listings, front-matter `model:` and `maxTurns:` lines, file comparison between tracked, installed and source copies, and version/status queries for git, gh, Python, pytest, WSL and the Docker client. Nothing was installed, cloned, fetched or written outside `docs/`. No tests, lint or control-plane checks were run. Not verified: remote state, tool function beyond version output, runtime launch of any role, whether the `sonnet` alias maps to Sonnet 5.5 or newer.

Public-repository hygiene: no personal names, no absolute local paths (`<workspace>`, `<claude-home>`, `<python314>` placeholders), no private repository URLs.
