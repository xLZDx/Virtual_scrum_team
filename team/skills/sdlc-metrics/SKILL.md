---
name: sdlc-metrics
description: Report sprint and project status from git and SDLC artifacts with labelled evidence. Use at sprint end, for status requests and for retrospectives.
---

# sdlc-metrics

## Apply when
A status, sprint report or retrospective input is needed.

## Method
1. Take the changed set from git (log, diff stat, branch, HEAD), not from chat history; take phase and artifact state from the phase authority: until the S1 state store (`tools/vst/store.py`) is in use for a project, `docs/sdlc/STATE.md` is the phase authority; once it is in use, the store is the authority and `STATE.md` is its generated read-only view (baseline decision BD-1). Read the store or the generated view.
2. Report: goal vs outcome; stories done/carried/rejected; commits and PRs; test evidence (exact commands, results, NOT_RUN reasons); review findings by severity with duplicates merged; agent and model runs actually used; open risks and blockers with verified cause.
3. Label every number MEASURED (from a tool result) or INFERRED; never present a reviewer claim as own measurement.
4. For substantive reports use the `html-report` skill conventions.

## Required output
Sprint report or status table: item, state, evidence, blocker (if any), next action.

## Do not
Count agents or tokens as quality; report green without the test result; hide failed or skipped items.
