# S2 coordinator source-scope decision — 2026-10-28

## Decision

Codex keeps the production-coordinator investigation inside `D:\Repo\Virtual_scrum_team` until an
exact external repository or file path is identified. The operator's latest reply delegated the
choice to Codex but did not provide a path. The prior authorization covered read-only review of a
named source; it does not identify which neighboring checkout or general folder to inspect.

## Evidence

- The scoped repository search was run from `D:\Repo\Virtual_scrum_team` for coordinator and
  dispatch call-site terms over Markdown, Python, TOML and YAML source/documentation. Results in
  `docs/sdlc/STATE.md`, `docs/sdlc/evidence/s2-task-acceptance-2da827be-20261027.md`,
  `docs/changes/0471-implement-s2-persistent-runner-service.md` and later S2 records say the
  production call site is absent; no external path was present in the search results.
- The correlated GPT-PM final gate recorded in
  `docs/sdlc/evidence/s2-gptpm-final-gate-381435a-20261028.md` is `NOT APPROVED` and retains
  `S2-DISPATCH-M01` as MAJOR/OPEN.
- Existing acceptance explicitly says not to create a new scheduler, CLI, spool or assignment
  authority when no in-scope production coordinator is found.

## Consequence

No external checkout was read. No production dispatch path or new assignment authority was
created. `S2-DISPATCH-M01` remains open, S2 remains not approved, and S3 must not start. The
operator can unblock the read-only integration review by providing the exact existing repository
or file path. If no such source exists, GPT-PM must adjudicate any proposed architecture before
implementation; Codex will not invent it as a routine implementation choice.

## Ownership

- Codex: maintain the scope boundary and review a specifically named source when available.
- Operator: provide the external source path if it is outside the requested repository.
- GPT-PM: adjudicate any architecture proposal and the eventual exact-head S2 gate.
