# Backlog

| ID | Item | State | Notes |
|---|---|---|---|
| VST-001 | Raise `maxTurns` or split tasks for read-heavy design/explore agents | done 2026-10-15 | Raised in the global agents: code-explorer 8->16, code-architect 16->20, tdd-guide 16->24, e2e-runner 16->24, functional-test-reviewer 20->25 (lint cap), security-reviewer 16->24, doc-updater 8->12. Pilot evidence: test, security and design agents each hit their limit and needed a resume. Large multi-epic authoring tasks should still be split per epic |
| VST-002 | Let design agents save their own document | open | `code-architect` is read-only; the coordinator saved `design.md`. Decide: add Write for a docs path or keep the technical-writer hand-off |
| VST-003 | Choose a license for the public repository | open | Operator decision |
| VST-004 | Decide whether `security-reviewer` runs in every SDLC pilot sprint | open (pilot data: it found no BLOCKER/MAJOR twice, GPT-PM still required exact-head correlation) | Routing makes it opt-in only; GPT-PM asked for an independent security review in the pilot |
| VST-005 | Add a project template (`docs/sdlc/` skeleton with STATE.md) installable into a new project | open | Currently created by the orchestrator at first use |
| VST-006 | Resolve role alias `adk-tune-sql-query` with a dedicated SQL-tuning agent if `database-reviewer` proves too broad | open | Mapped to `database-reviewer` on 2026-10-15 |
| VST-007 | Keep the exact verification record of the final test run in the repo (command, collected list, head) | open | Pilot: GPT-PM rejected the first final review because the agents' run record and head were not retained; the orchestrator should require `docs/sdlc/evidence/` files before the final GPT review |
| VST-008 | Put the exact-head rule into `sdlc-orchestrator`: run the security review and GPT-PM on one committed head, avoid source commits afterwards | open | Pilot cost one extra GPT round |
