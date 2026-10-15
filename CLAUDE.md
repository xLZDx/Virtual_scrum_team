# Virtual Scrum Team - project router

Follows the global contract in `%USERPROFILE%\.claude\CLAUDE.md` and the workspace workflow in
`D:\Repo\AGENTS.md`. Project conventions: `AGENTS.md`.

## 1. Mission and current state

Source repository of the virtual scrum team (agents, skills, templates, process). Do not trust
status text here: read `core/STATE.md`, then verify branch, HEAD and dirty tree. Remote `origin` is
`https://github.com/xLZDx/Virtual_scrum_team.git` (public); default branch `main`. Pushing is a
separate explicit operator command.

## 2. Boundaries

- Installed copies in `~/.claude/` are separate from `team/`; a change here changes nothing in a
  running session until re-installed. Compare before concluding the two are in sync.
- Project-specific agents belong to that project's own `.claude/agents`, not here.
- Model policy: `%USERPROFILE%\.claude\control-plane\model_policy.json`.

## 3. Documentation map

- Current state and open items: `core/STATE.md`, `core/BACKLOG.md`
- Decisions and evidence: `core/DECISION_LOG.md`
- Process: `docs/SDLC_PROCESS.md`; templates: `docs/templates/`
- Definition of Done: `governance/DEFINITION_OF_DONE.md`
- Document registry (generated, do not edit): `governance/DOCUMENT_REGISTRY.md`, built by
  `tools/build_document_registry.py`; regenerate when Markdown documents change.
- Change records: `docs/changes/`
