# Virtual Scrum Team - conventions

`D:\Repo\AGENTS.md` is the authoritative workspace workflow (autonomy, development order, testing,
reviewers, commits, GPT approval, delivery). This file adds only what is specific to this repository.

## Scope

- This repository defines the team (agents, skills, templates, process). It does not hold any
  delivered project's code or domain rules; those stay in each project's own repository.
- Never copy a project's private requirements, designs or decisions into this repository.
- No secrets, no PII, no project-bound content (public repository).

## Rules for changing the team

- An agent definition uses model alias `sonnet`, a risk-based effort tier, a bounded `maxTurns`
  and only the tools its role needs. Opus is never automatic.
- Authoring roles write documents only; implementers never approve their own work; reviewers are
  read-only unless a rule explicitly makes them test authors.
- Subagents cannot launch other agents; orchestration is the `sdlc-orchestrator` skill run by the
  main session.
- After changing an agent or skill here, re-install it into `~/.claude/` and run the global lint:
  `C:\Python314\python.exe %USERPROFILE%\.claude\control-plane\agentctl.py --strict`.
- All text committed here is English.

## Commits

Every commit includes a change-record file under `docs/changes/` linked from its message, and a
dated entry in `core/DECISION_LOG.md` when it records a decision or evidence.
