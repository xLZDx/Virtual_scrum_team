---
name: sprint-ceremonies
description: Run lightweight scrum ceremonies (planning, refinement, review, retrospective) as written artifacts. Use at sprint start, mid-sprint scope change and sprint end.
---

# sprint-ceremonies

## Apply when
A sprint opens, scope changes, or a sprint closes.

## Method
- **Planning:** confirm sprint goal, pull ready stories (DoR met), record capacity assumptions and risks through the orchestrator. Until the S1 state store (`tools/vst/store.py`) is in use for a project, `docs/sdlc/STATE.md` is the phase authority; once it is in use, the store is the authority and `STATE.md` is its generated read-only view (baseline decision BD-1), so record items through the orchestrator/store and never hand-edit the view.
- **Refinement:** product-owner and business-analyst clarify upcoming stories; unresolved items go to the backlog, not into the sprint.
- **Review:** compare outcome to goal using acceptance evidence; list accepted, rejected, carried stories.
- **Retrospective:** from measured data (`sdlc-metrics`) list what worked, what failed, and at most three concrete actions with owners; apply process fixes to skills/agents, not to chat memory.

## Required output
Short written record per ceremony appended to `docs/sdlc/` and referenced from the phase state (store or STATE.md, per the rule above).

## Do not
Hold ceremonies as in-chat role play; add meetings that produce no artifact; start next-sprint work in a way that delays closing the current sprint.
