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

## Review remediation

Three reviewers reported on 039493f; one batch fixed, static only (`ast.parse`), tests still NOT_RUN. Operator decision kept and documented: the store `SCHEMA_VERSION` stays 7 and the extension has its own `pl_schema_version`.

Database findings:
- Rollback point tied to the migrated state: `migrate_pipeline` opens `BEGIN IMMEDIATE` first, takes the backup from that locked state and refuses a point whose cheap state invariant differs (`create_rollback_point(expect_invariant=...)`).
- Restore safety: `confirm_stopped=True` is required, a `BEGIN EXCLUSIVE` probe must succeed, the point's store schema version must equal the current one unless `allow_store_version_change=True` (recorded in the journal), and the documentation lists what a whole-store restore loses. New scoped rollback `down_migrate_pipeline` drops only the pl_ objects and refuses while pl_ rows exist unless `allow_data_loss=True`.
- Schema v1 frozen: literal enum lists in the DDL, `schema_sha256` stored in `pl_schema_version` and compared with the live schema and with the module DDL on every `pipeline_version` call; a dropped trigger or index is `partial`.
- Lock time: the live database is checked inside the lock only by the cheap invariant (non-pl_ schema entries, per-table count and max rowid, sequences). Deviation to state plainly: the backup copy and its full digest are still produced while the write lock is held, so the rollback point is complete before the first DDL statement; the lock grows with the store size.
- Minor: every step maps `sqlite3.IntegrityError` to a typed `StoreError` (`duplicate`, `constraint`, `append_only`); the DDL gained a partial unique index (one STARTED attempt per story) and a CHECK (SUCCEEDED needs a candidate head), and the frozen hash covers them (nothing had shipped); the lock release compares the token before removing; `pl_schema_version` is fully immutable.

Python findings:
- `applied` is derived (ACCEPTED and `post_materialize_verified` exactly true), a disagreeing stored flag is refused, hunks are validated as non-negative integer pairs, and the line totals must agree (`record_patch_proposal`).
- `link_receipt` needs canonical decimal keys for attempts and review iterations.
- Proposals attach only to a STARTED attempt with the same `base_head` (`conflict`); a SUCCEEDED finish must name the candidate head of an ACCEPTED proposal when one exists.
- Every step re-checks the pipeline schema inside its transaction, so a restore or down-migration under an open `PipelineState` is noticed.

Tests added (NOT_RUN): typed duplicates, crash half-way through a step and during stop, a receipt of another story, a real path-traversal case with a control, restore failure paths (missing confirmation, corrupt manifest, missing backup, version mismatch and override, live writer), down-migration (exact dump, data guard, open state notices it), frozen-hash failures (dropped trigger or index), lock token, rollback point from another state aborts, applied derivation with exact numbers, attempt and base-head rules, DB-level attempt invariants.

Remaining limits: nothing was executed; epoch-only fencing; no signature on the manifest; pipeline rows outside the signed event chain.
