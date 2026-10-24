# Change record 0012: S1 E6 state authority alignment

## What changed
- `team/skills/sdlc-orchestrator/SKILL.md` step 1 and `governance/DEFINITION_OF_DONE.md` item 1 now state one rule: once the S1 state store is accepted and in use it is the only source of phase truth and `docs/sdlc/STATE.md` is its generated read-only view; until then `docs/sdlc/STATE.md` stays the only source (baseline decision BD-1, review finding VEO-R2-B01).

## Why
The skill named a markdown file as the only source of truth while the baseline moves authority to a store; the transitional wording keeps exactly one authority at every moment.

## Affected contracts and paths
The installed copy of the skill under `~/.claude/skills/sdlc-orchestrator/` is now older than the repository copy; re-installation and the global lint are not done (global configuration, snapshot needed, operator task). `docs/sdlc/STATE.md` generation is implemented in epic E3.

## Verification state
Documentation only; nothing run. The document registry is regenerated at the end of the sprint, not in this commit.
