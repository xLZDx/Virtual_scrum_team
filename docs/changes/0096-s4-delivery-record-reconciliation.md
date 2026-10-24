# 0096 S4 delivery record reconciliation

## What changed

- Added a decision-log entry for the worker-to-runner event permissions and report-bound pytest plugin policy implemented in source commit `a914213152710a498bd1709e80bd78163e1c3c4c`.
- Reconciled the prior S4 source commits `217bd2b64d8dc7557ba130f80dbf786fc08122ba` and `a914213152710a498bd1709e80bd78163e1c3c4c`: each already contains its own detailed `docs/changes/0094-*` or `docs/changes/0095-*` record; this follow-up supplies the missing decision-log reference and generated document registry state without rewriting history.
- Regenerated `governance/DOCUMENT_REGISTRY.md` for the newly added S4 records.

## Why

The S4 continuation task requires a decision-log entry for each commit and an up-to-date generated document registry. The two source commits had detailed change records but missed those complementary project records. Preserve their history and repair the current records in a dedicated follow-up.

## Affected contracts and paths

- `core/DECISION_LOG.md`: S4 permission and plugin-loading decision.
- `governance/DOCUMENT_REGISTRY.md`: generated Markdown inventory.
- `docs/changes/0096-s4-delivery-record-reconciliation.md`: this reconciliation record.

## Decisions and ownership

- Accountable task owner: operator under delegated continuation. Executor: Codex.
- Historical commits are preserved; no amend, reset, or history rewrite is used.

## Verification state

- The registry is regenerated using the repository's documented generator command.
- No tests, checks, builds, CI, installation, migration, or QA execution are run in this documentation reconciliation step.

## Follow-up

1. Continue S4 source coding before starting test authorship/execution.
2. Include the decision-log entry, dedicated change record, generated registry and `Executor: Codex` attribution in subsequent commits.
