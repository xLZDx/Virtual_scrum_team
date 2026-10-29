# Change 0481: Record S2 coordinator source-scope decision

## What changed

- Recorded Codex's decision to keep investigation inside `D:\Repo\Virtual_scrum_team` because the
  operator's response asked Codex to decide but did not provide an external repository or file path.
- Kept `S2-DISPATCH-M01` MAJOR/OPEN and production dispatch unaccepted; no scheduler, CLI, spool,
  coordinator, or assignment authority was created.
- Preserved the existing S2 `NOT APPROVED` verdict and the one-sprint-at-a-time boundary.

## Why

The operator had authorized read-only review of a named existing coordinator if its exact location
was supplied. The follow-up response delegated the choice but did not identify that source. The
project scope rule prohibits searching neighboring checkouts or general folders based on inference,
and prior S2/GPT-PM records explicitly reject inventing a new production assignment authority.
Therefore the safe decision is to stop external source discovery, leave dispatch disabled, and
continue only with in-scope S2 work.

## Affected paths

- `docs/sdlc/evidence/s2-coordinator-source-scope-decision-20261028.md`
- `docs/sdlc/STATE.md`
- `core/STATE.md`
- `core/BACKLOG.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Read-only search was limited to `D:\Repo\Virtual_scrum_team`; the searched coordinator terms
  returned existing documentation of the missing production call site, not an external source path.
- No source code, service, configuration, credentials, test, or runtime state was changed or run.
- The existing correlated GPT-PM exact-revision verdict remains `NOT APPROVED`; this decision does
  not override or substitute for that adjudication.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved.

## Remaining acceptance and next action

`S2-DISPATCH-M01` remains MAJOR/OPEN. To resume coordinator integration review, provide the exact
existing repository/file path; Codex can then perform the already authorized read-only review
within that named scope. Without the path, keep production dispatch disabled and S2 open. Owner:
Codex for scope-bounded investigation and evidence; GPT-PM for architecture adjudication; operator
for supplying a path if the source is outside the current repository.

## Commit attribution

Executor: Codex
