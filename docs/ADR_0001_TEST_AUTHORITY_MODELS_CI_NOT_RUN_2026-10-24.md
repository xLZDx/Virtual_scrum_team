# ADR-0001: test authority, reviewer models, CI and NOT_RUN handling

**Date:** 2026-10-24  
**Status:** ACCEPTED by the operator (four answers given in the session of 2026-10-24; not automatic acceptances)  
**Scope:** this repository's process documents and team definitions. Settles contradictions C-01, C-02, C-03 and C-13 of the review dossier and the open operator decisions O-2 and O-3 of the blueprint.

## Decisions

1. **Test authority.** Only `functional-test-reviewer` and `e2e-runner` author and execute required tests. `tdd-guide` and `performance-optimizer` are advisory only: they may review test quality or analyse performance but do not author or run required tests. The QA roles in the 39-role catalog are skills or overlays loaded by these two agents, not additional test authors.
2. **Reviewer and test-agent models.** The operator's global contract is the governing source: Sonnet 5.5 at medium effort or GPT-5.6 Luna at low or medium effort; GPT-5.6 Sol is not allowed; no silent substitution. The repository sources (`README.md`, `docs/SDLC_PROCESS.md`, `team/skills/sdlc-orchestrator/SKILL.md`, `team/agents/*.md`) already match this.
3. **CI.** No CI is used. Evidence is the focused test runs of the two test agents on the exact head, with command, environment, exit code, expected and executed test ids. Release-head CI is removed from the S6 and S9 exits and from the Definition of Done.
4. **NOT_RUN.** A mandatory test with status `NOT_RUN` never yields an ordinary APPROVE. A separate verdict `APPROVED_WITH_WAIVER` exists; it requires a named operator record (identity, waived items, scope, head, expiry). Without that record the gate result is not an approval.
5. **Mutation and red/green.** No mutation runs and no red/green loops are authorized. Falsifiability is shown by assertion review and by known-defect fixtures on synthetic repositories that are never injected into product code. Mutation evidence is `NOT_RUN` by operator decision.

## Consequences and what remains open

- Repository sources changed in the same commit as this ADR: `team-roster.md`, `README.md`, `governance/DEFINITION_OF_DONE.md`, the blueprint (sections 4, 8, 10, 13) and the dossier (new section 12).
- **Not changed (outside this repository, needs the operator):** the workspace `AGENTS.md` still names GPT-6 Luna as the default reviewer model (lines 63-69), and the operator's global contract still lists four test-writing agents (`tdd-guide`, `performance-optimizer`, `e2e-runner`, `functional-test-reviewer`). Until those two files are aligned, sources outside this repository contradict this ADR.
- Still open from the review, not addressed here: the single phase-state authority (`SKILL.md:12` against the blueprint's generated-view proposal), signed receipts and the gate verdict function (R-1, R-2), fencing and retry history (R-3, R-4), enforced limits (R-6). The public-history decision is recorded in `core/STATE.md`.
- This ADR records decisions only. It implements nothing and does not make the design APPROVE.
