# Definition of Done (for a team change and for a delivered sprint)

## A change to the team (agent, skill, template)

1. The definition follows the model policy: alias `sonnet`, bounded `maxTurns`, minimal tools, risk-based effort.
2. The roster (`team/skills/sdlc-orchestrator/references/team-roster.md`) and `README.md` stay consistent with it.
3. The global lint `agentctl.py --strict` and the router eval pass after re-installing the change into `~/.claude/`.
4. A change record is committed in the same commit under `docs/changes/` and a dated entry exists in `core/DECISION_LOG.md`.

## A sprint delivered by the team (applied through the `sdlc-orchestrator` skill)

1. Every phase has its exit artifact recorded in the phase state: the state store once it is in use (then `docs/sdlc/STATE.md` is its generated view), otherwise the project's `docs/sdlc/STATE.md`.
2. All sprint code is committed, each commit with its change record.
3. Per-epic functional tests were authored and run in full by `functional-test-reviewer` and `e2e-runner`; results recorded with exact commands. A mandatory test recorded as NOT_RUN blocks an ordinary approval; only the separate verdict APPROVED_WITH_WAIVER with a named operator record may proceed (ADR-0001).
4. Relevant specialist reviewers reached consensus on the exact head; all valid BLOCKER/MAJOR findings are fixed.
5. GPT-PM approved the exact final head; ONE pull request per sprint; the push happens only on the operator's explicit command where the project requires it.
6. `product-owner` accepted each story on evidence; `reporting-analyst` produced the sprint report.
