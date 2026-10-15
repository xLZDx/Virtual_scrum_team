---
name: backlog-and-dod
description: Build and prioritize a backlog of epics and user stories with acceptance criteria, Definition of Ready and Definition of Done. Use after requirements exist and at sprint planning and acceptance.
---

# backlog-and-dod

## Apply when
Requirements need to become sprint-sized, accepted work, or a sprint needs acceptance.

## Method
1. Group requirements into epics; split into stories small enough for one sprint, each tracing to `REQ` ids.
2. Give every story numbered Given/When/Then criteria `AC-n` that a test can falsify.
3. Definition of Ready: requirement traced, criteria testable, design and UI inputs available, dependencies known.
4. Definition of Done: code committed with change record, per-epic functional tests green (authored by test agents), review consensus, GPT APPROVE for the head, docs and release notes updated.
5. Prioritize by value, risk and dependency; state the rule used. One sprint goal; ONE PR per sprint.
6. Acceptance: mark each story accepted or rejected with evidence links; carry rejected work as new stories.

## Required output
Prioritized backlog, sprint scope with goal, DoR/DoD, and `acceptance.md` at sprint end.

## Do not
Accept a story without evidence; add stories outside the sprint goal; reorder silently.
