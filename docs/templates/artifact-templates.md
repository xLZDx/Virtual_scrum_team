# SDLC artifact templates

Origins: the phase/role split and artifact chain are adapted conceptually from BMAD-METHOD (MIT), GitHub spec-kit (MIT: constitution -> specify -> plan -> tasks) and claude-scrum-team (ceremony skills). No upstream text was copied; everything is rewritten for this control plane. Re-check upstream licenses before copying any wording.

## docs/sdlc/STATE.md
```
# SDLC state
Project: <name>   Sprint: <n>   Phase: <1-10 name>   HEAD: <sha>   Updated: <date>
## Artifacts
| Phase | Artifact path | Author agent/model | Head | Status |
## Open questions / backlog items (owner)
## Decisions (link to ADRs)
```

## requirements.md (business-analyst)
Context and goal; stakeholders; in/out of scope; functional requirements `REQ-001..` (one testable statement each, with source); non-functional requirements with numbers; constraints; assumptions; open questions; glossary.

## Story (product-owner)
`US-001` As a <role> I want <capability> so that <outcome>. Traces: REQ ids. Acceptance (Given/When/Then, numbered `AC-1..`). Priority, size, dependencies. DoR checklist; DoD checklist.

## design.md (architect)
Problem, constraints, options and decisive criterion, chosen design, data/state ownership, failure modes, rollout/rollback, risks, unknowns. Decisions go to `docs/adr/ADR-NNN.md` (context, decision, consequences).

## ui-spec.md (ui-designer)
Journeys, screen/state inventory (empty/loading/error/success/permission), component contract, copy, responsive and accessibility behavior, open design questions.

## TDD / test plan (technical-writer + test agents)
Requirement -> story -> acceptance criterion -> test file map; negative and boundary cases; data fixtures; environment; NOT_RUN conditions.

## Change record (every commit, linked from the commit message)
What changed, why, affected contracts/paths, decisions, verification state.

## acceptance.md (product-owner)
Per story: AC result with evidence link, accepted/rejected, follow-ups.

## Sprint report (reporting-analyst)
Goal vs outcome, stories done/carried, defects found/fixed, review findings by severity, agent/model runs, risks, next sprint.
