# S0 repository registry

**Observed on:** 2026-10-24
**Method:** read-only git commands per repository (`status --short | wc -l`, `rev-parse --abbrev-ref HEAD`, `rev-parse --short HEAD`, `log -1 --format=%cs`, `remote -v`), plus directory listing. No fetch, clone, install or network access.
**Rule: values are volatile; re-verify with git before use.** Branch, HEAD and dirty counts below describe the moment of observation only. Several repositories are edited by other concurrent sessions, so a dirty count is a snapshot, not a property of the repository. Nothing in this table authorizes any write to these repositories.

Path convention: `<workspace>` is the operator-configured local repository root. Private repository URLs are withheld (baseline decision BD-7); only names and short HEADs are recorded. The `origin` column records only whether an `origin` remote exists and its host.

## Inventory

| Repository (`<workspace>/...`) | Exists | Git repo | Branch | Short HEAD | Dirty files | Last commit | Origin | Role in the organization (blueprint section 2) |
|---|---|---|---|---|---|---|---|---|
| `Virtual_scrum_team` | yes | yes | `s1-control-plane-core` | `5427bb7` | 6 (see note 1) | 2026-10-24 | yes, github.com (public repository) | KEEP: SDLC source of truth and control plane |
| `agents-skills-repo` | yes | yes | `main` | `3826576` | 2 | 2026-10-16 | yes, github.com (public per the blueprint listing) | KEEP: reusable specialist registry (roles and skills source) |
| `AEVE` | yes | yes | `codex/real-repo-hardening-2` | `e26ca48` | 1 | 2026-10-24 | yes, github.com (private) | KEEP: independent bounded evidence engine; actual development checkout |
| `MegaGpt/MetaGPT` | yes | yes | `main` | `11cdf466` | 0 | 2026-01-21 | yes, github.com (public upstream) | REFERENCE ONLY (structured handoffs, role SOP) |
| `pm-bridge` | yes | yes | `master` | `14c7957` | 1 | 2026-10-23 | yes, github.com (private) | KEEP: sprint closure reporting only, after acceptance |
| `pm-bridge-codex` | yes | yes | `codex/pm-bridge-completion` | `1801425` | 10 | 2026-10-18 | yes, github.com (visibility not recorded in docs) | Not in blueprint section 2; sibling folder of `pm-bridge` (see note 2) |
| `Personal_DC` | yes | yes | `wip-snapshot-2026-10-20` | `fe08cbb` | 0 | 2026-10-23 | yes, github.com (visibility not recorded in docs) | KEEP: bounded Windows access bridge (Personal DC v2.2) |
| `Personal_Decision_Command_Center` | yes | yes | `work/pdcc-s7-main-reconcile-2026-10-21` | `aa59afa1` | 366 | 2026-10-24 | yes, github.com (private) | PILOT: multi-tenant PWA; read-only until sandbox is qualified |
| `Fitness_App` | yes | yes | `sprint/hardening-followups-2026-10` | `74ba5adc` | 226 | 2026-10-16 | yes, github.com (public per the blueprint listing) | PILOT: Flutter/mobile + Firebase |
| `ERP` | yes | yes | `integration/erp-all-branches-final` | `c38b1e94` | 40 | 2026-10-21 | yes, github.com (private) | LATER PILOT: multi-module ERP |
| `ERP_MCP` | yes | yes | `codex/erp-mcp-autonomous-2026-10-21` | `3e12436` | 103 | 2026-10-22 | yes, github.com (public per the blueprint listing) | LATER PILOT: 1C read-only gateway; distinct from ERP |
| `Remote_Quality_Delivery_Office_Platform_rqdo` | yes | yes | `g10-feed-0` | `af30017` | 29 | 2026-10-15 | yes, github.com (visibility not recorded in docs) | Not in blueprint section 2: no declared role (see note 3) |

Repositories named in the blueprint but not inventoried in S0 (outside the requested list): `AI_trading_assistance`, `ERP_UNIFIED_WORKTREE`, `ERP_MCP_R2`. Not checked, status UNKNOWN.

## Notes

1. `Virtual_scrum_team` dirty files at observation time: 2 modified (`core/BACKLOG.md`, `core/STATE.md`) and 4 untracked documents (a sprint S2 plan, two change records, an S1 retrospective). These belong to other work in the same checkout and were not touched by S0. The S0 documents themselves are added after this observation.
2. `pm-bridge-codex` is a second checkout whose relation to `pm-bridge` (separate clone, worktree-like variant) was not determined; the blueprint names only `pm-bridge`. Decision for the operator: whether it is a registered variant or stale.
3. `Remote_Quality_Delivery_Office_Platform_rqdo` is not in the blueprint inventory. Its role is undeclared; the registry records it as observed and does not assign one.
4. Dirty entries of the two registry/engine repositories: `agents-skills-repo` has one modified skill file and one untracked agent file; `AEVE` has one untracked report folder. Treat them as other sessions' work and preserve them. The `agents-skills-repo/agents` folder holds 37 files (36 tracked per the historical inventory plus the 1 untracked agent file).
5. `AEVE` is the development checkout. The Personal DC project registry points the alias `AEVE` to a frozen temporary snapshot instead (see the S0 open items in `PROFILE_RESOLUTION.md`).
6. All twelve checked folders had an `origin` remote on github.com. Public or private visibility is taken only from the blueprint listing; where the blueprint is silent it is recorded as "not recorded in docs", not guessed.

## Not verified

- Remote state (no fetch): ahead/behind counts against origin are unknown.
- Linked worktrees of each repository were not enumerated.
- Visibility of repositories marked "not recorded in docs".
