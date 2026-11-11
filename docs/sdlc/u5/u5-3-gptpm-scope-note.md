# U5-3 GPT-PM code review scope

Task: U5-3, pipeline state and store migration. Base: U5-2 approved head, head = current HEAD. Review the delta only: tools/vst/pipeline_schema.py, tools/vst/pipeline_migration.py, tools/vst/pipeline_state.py, docs/sdlc/u5/PIPELINE_STATE.md, tests/vst/test_u5_pipeline_state.py (tests are NOT_RUN; judge by reading), tools/qa/build_registry.py (two map lines), core/DECISION_LOG.md and core/LESSONS_LOG.md entries.

Delivers: nine `pl_` tables in the store's SQLite file (steps ledger, stop marker, worker attempts, patch proposals, diff gate results, review iterations, test evidence, receipt links); `PipelineState` with epoch-checked, idempotent steps and a stop path; `migrate_pipeline` with a lock, a rollback point (online backup plus manifest with versions and sha256), a journal and a transactional DDL step; `restore_rollback_point` that verifies the point and returns the exact previous rows; `migration_status` that detects interrupted or half-recorded migrations. `tools/vst/store.py`, `diffgate.py`, `worker_gate.py`, `patch_proposals.py` and AEVE are unchanged (the new code only imports them).

Interpretation decisions:
- The schema change is an additive extension with its own version (pipeline schema 0 to 1), not a bump of the store's `SCHEMA_VERSION` 7. A bump would change `store.py` and break existing store tests that assert version 7 and the v6 to v7 upgrade; the extension keeps every existing table and API as is. The store stays the authority (BD-1).
- The epoch is the fence for pipeline steps (same as `set_phase`), checked before the idempotency lookup, so a stale caller is refused even for a replay. The epoch is not in the payload digest.
- A replay of an already recorded step is allowed after a stop (it only reads); every new step except the stop acknowledgment is refused.
- A second stop with another step id writes nothing, not even a step row.
- `applied_hunks` is derived from the U5-2 run record: the attempted hunk count when `applied` is true, else 0.
- The rollback point is made by the migration function, not inside `Store.__init__`; stale locks are never broken automatically.
- Pipeline rows are not appended to the HMAC event chain (the event kind list is closed in the store schema).

Limits: nothing was run (SQLite DDL, triggers, the online backup into a WAL database and the Windows file handling are unproven); no signature on the manifest; epoch-only fencing without a lease check; restore needs writers stopped; pipeline writes are not in the signed event chain; no wiring to a driver (U5-4).

Tests: written, NOT_RUN (running tests is forbidden by the operator). Evidence is static reading and `ast.parse` only.
