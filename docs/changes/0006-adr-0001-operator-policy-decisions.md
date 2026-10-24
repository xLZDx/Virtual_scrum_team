# Change record 0006: ADR-0001 operator policy decisions and source alignment

## What changed
- New `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md` recording four operator decisions given on 2026-10-24: only `functional-test-reviewer` and `e2e-runner` author and run required tests; the operator's global contract governs reviewer models; no CI; `NOT_RUN` never yields an ordinary approval and a separate `APPROVED_WITH_WAIVER` verdict needs a named operator record.
- Aligned repository sources: `team-roster.md` (`tdd-guide` and `performance-optimizer` advisory only), `README.md` tester row, `governance/DEFINITION_OF_DONE.md` item 3, blueprint (phase-10 owner, test matrix rows, S6 and S9 exits, CI wording, open decisions O-2 and O-3 and conflict C-1 marked resolved), dossier section 12, `docs/INDEX.md`.
- Fixed two of my earlier over-general clauses in blueprint section 13 (universal PASS formula and universal seeded-input demand), replaced by typed success conditions and acceptance-mechanism classes.

## Why
Round 3 verification found that sources disagreed on test authority and model policy and that CI and `NOT_RUN` handling were undecided. The operator answered the four questions directly (not through the automatic-answer policy).

## Affected contracts and paths
Process documents and one roster. The installed copy of `team-roster.md` under `~/.claude/skills/sdlc-orchestrator/references/` is now older than the repository copy; re-installing it and running the global lint was NOT done here (it changes global configuration and needs a snapshot first). The workspace `AGENTS.md` (model default) and the operator's global contract (four test-writing agents) were not edited and still contradict this ADR.

## Verification state
Documentation only; nothing run. Open from the review: single phase-state authority, signed receipts, gate verdict function, fenced state store, enforced limits, independent review of the new head. Nothing was pushed.
