REVIEW ITEM: task plan for sprints U2-U6 (documentation review, requested explicitly by the operator; one request for the whole set).

Context: Unified Core program. Operator goal: a deterministic local analyzer (AEVE, zero model tokens) plus the Virtual Scrum Team (VST) automate review, coding and testing locally; only one orchestrator model, authoring that code cannot produce, and a final GPT review remain. Sprint U1 is accepted (entry command, role table, adapter, probe, token baseline, measurement). U2-U6 are PLANNED ONLY and are not started: no code exists for them. The sections are in PROJECT_PLAN.md (Sprint U2 ... Sprint U6) and the design in docs/unified/UNIFIED_CORE_TDD.md.

Please review ONLY the task decomposition of U2-U6 for BLOCKER/MAJOR defects with a concrete example:
1. a task whose acceptance cannot be checked by a deterministic test or a stated measurement;
2. a missing or wrong dependency (a task that needs another task's output but does not list it, or a cycle);
3. a task that contradicts the operator goal, the U1 results (the AEVE interface is request v2, the router returns uc.role-result.v1, a clean result never suppresses a model role of class LOCAL_PLUS_MODEL) or the standing rules (two planning levels only: sprint and tasks; no stories or extra gates; tests only by the named test agents; GPT review is one task at a time and for code and contracts);
4. a gap: something the operator goal requires that no task covers, or a task that invents scope the goal does not need.

Settled decisions (do not reopen): U1-9 (changes to global Claude configuration) is parked until real measurements exist; real paired token measurement is NOT_RUN; no sprint beyond U1 starts without operator approval. Do not ask for tests, lint, typecheck or verification scripts (prohibited by the operator). Style, wording and formatting findings are out of scope.
