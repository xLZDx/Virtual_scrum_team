---
name: requirements-elicitation
description: Turn an idea or change request into testable, traceable requirements. Use for discovery, new features and existing-project scope review before backlog work.
---

# requirements-elicitation

## Apply when
An idea, request or bug report has no agreed, testable requirements yet.

## Method
1. Read existing docs, code and decision logs first; extract current behavior as FACT with file references.
2. Identify stakeholders, goal, scope and non-goals; separate FACT, ASSUMPTION and UNKNOWN.
3. Write each requirement as one testable statement with id `REQ-nnn`, source and priority; give non-functional requirements numbers.
4. List open questions with an owner; resolve routine ones from evidence instead of asking.
5. Check: no requirement is ambiguous, duplicated, or untestable; every one can map to an acceptance criterion.

## Required output
`docs/sdlc/requirements.md` per the template in `sdlc-orchestrator/references/artifact-templates.md`.

## Do not
Invent requirements; write solutions as requirements; hide unknowns.
