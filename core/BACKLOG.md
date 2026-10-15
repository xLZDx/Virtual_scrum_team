# Backlog

| ID | Item | State | Notes |
|---|---|---|---|
| VST-001 | Raise `maxTurns` or split tasks for read-heavy design/explore agents | open | Pilot: `code-explorer` (8 turns) and `code-architect` (16 turns) both stopped at their turn limit before delivering a result and had to be resumed |
| VST-002 | Let design agents save their own document | open | `code-architect` is read-only; the coordinator saved `design.md`. Decide: add Write for a docs path or keep the technical-writer hand-off |
| VST-003 | Choose a license for the public repository | open | Operator decision |
| VST-004 | Decide whether `security-reviewer` runs in every SDLC pilot sprint | open | Routing makes it opt-in only; GPT-PM asked for an independent security review in the pilot |
| VST-005 | Add a project template (`docs/sdlc/` skeleton with STATE.md) installable into a new project | open | Currently created by the orchestrator at first use |
| VST-006 | Resolve role alias `adk-tune-sql-query` with a dedicated SQL-tuning agent if `database-reviewer` proves too broad | open | Mapped to `database-reviewer` on 2026-10-15 |
