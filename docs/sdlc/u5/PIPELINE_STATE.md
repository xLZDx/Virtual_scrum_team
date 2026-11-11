# U5-3: pipeline state and store migration

Modules: `tools/vst/pipeline_schema.py` (DDL and enums), `tools/vst/pipeline_migration.py` (migration, rollback point, restore), `tools/vst/pipeline_state.py` (`PipelineState`). Tests: `tests/vst/test_u5_pipeline_state.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint, so no result is claimed; nothing was executed, only syntax-parsed).

Acceptance (PROJECT_PLAN U5-3): the store models story, worker attempt, patch proposal, diff gate, review iterations, tests and receipts with epoch checks, idempotent steps and a stop path; any schema change has a migration, a rollback point and a test that restores the previous state.

## Where the state lives

Baseline decision BD-1 stays: `tools/vst/store.py` is the state authority. The pipeline tables are an additive extension in the same SQLite file. They are versioned on their own in `pl_schema_version` (pipeline schema version 1; version 0 means no `pl_` table). The store's `PRAGMA user_version` stays 7 and no existing table, trigger or API changed, so every existing store test keeps its meaning. This is a deliberate decision, accepted by the operator: bumping the store's `SCHEMA_VERSION` would have changed `store.py` and the existing tests that assert version 7 and the v6 to v7 upgrade, for no benefit to the pipeline. Consequence: the pipeline version and the store version are checked separately, the migration requires store version 7 exactly, and a future store version bump must re-check this extension. The story itself is the existing `stories` row (id, project, phase, epoch, owner); the pipeline never copies it.

## Data model (pipeline schema version 1)

| Table | One row is | Key | Notes |
|---|---|---|---|
| `pl_schema_version` | the pipeline schema version and the frozen schema hash | component | fully immutable (no update, no delete) |
| `pl_steps` | one accepted step (the idempotency ledger) | story_id, step_id | kind, epoch, payload sha256, stored result; append-only |
| `pl_story_control` | a stop marker | story_id | row present = story stopped; append-only |
| `pl_worker_attempts` | one worker attempt | story_id, attempt_no | base_head, candidate_head, state STARTED then SUCCEEDED, FAILED or STOPPED; identity immutable, a closed row never changes; a partial unique index allows one STARTED attempt per story; CHECK SUCCEEDED needs a candidate head |
| `pl_patch_proposals` | one U5-2 run record | story_id, proposal_id | proposal_document_sha256 (the record's report_sha256), base_head, candidate_head, verdict, stage, attempted_hunks, applied_hunks, proposal_lines, model_lines, the full run record as JSON |
| `pl_diff_gates` | one U5-1 gate verdict | story_id, gate_id | verdict, reasons, isolation proof JSON, per-property statuses (VERIFIED, NOT_VERIFIED, CALLER_ASSERTED, FAILED) |
| `pl_review_iterations` | one review iteration | story_id, iteration_index | iteration_of, findings_count, declared coverage, verdict CLEAN, FINDINGS, PARTIAL or BLOCKED |
| `pl_test_evidence` | one test result of one attempt | story_id, evidence_id (unique per attempt and test_id) | status PASS, FAIL, BLOCKED, NOT_RUN, INCONCLUSIVE; evidence sha256; reason |
| `pl_receipt_links` | a link from a pipeline row to an existing receipt | story_id, receipt_id, subject_kind, subject_key | the receipt stays in the store's `receipts` table and is not copied |

Database-level rules (CHECK, partial unique index and triggers): no update or delete on any row except `pl_worker_attempts` going STARTED to one terminal state once; an applied hunk count never exceeds the attempted count and is 0 unless the verdict is ACCEPTED; an ACCEPTED gate has an isolation proof; iteration 1 has no `iteration_of`, later ones point to an earlier index; CLEAN has zero findings; PASS and FAIL carry an evidence digest and every other status carries a reason.

## Step rules

Every mutating `PipelineState` method is a step with `(story_id, step_id)` and the caller's `epoch`. In one `BEGIN IMMEDIATE` transaction of the store:

1. Unknown story: `StoreError(kind='story')`. Epoch not equal to the story's current epoch: `kind='epoch'`, nothing written. The epoch check comes first, so a stale caller is refused even when it only replays an old step.
2. `pl_steps` lookup. Same id, same kind, same payload digest: the stored result is returned (`StepResult.replayed` is True) and nothing is written. Same id with another kind or payload: `kind='conflict'`. The digest covers kind and payload, not the epoch, so a new owner may replay a step recorded under an older epoch.
3. Story stopped: `kind='stopped'`, unless the step is the stop path.
4. The step applies its rows (argument and consistency checks raise `kind='argument'` or `'pipeline'`) and records itself. Any `sqlite3.IntegrityError` (duplicate id, CHECK, unique index, append-only trigger) becomes a typed `StoreError` with `kind='duplicate'`, `'constraint'` or `'append_only'`. Any exception rolls the whole transaction back; a crash before COMMIT leaves nothing, a retry after COMMIT replays.

Before step 1 every step re-reads the pipeline schema inside its transaction (version, table set and the frozen schema hash), so a restore or down-migration under an open `PipelineState` is refused (`kind='schema'` or `'partial'`) instead of writing into another schema.

Two concurrent requests with the same step id: the second waits for the write lock and then replays. Steps do not take or check a lease; the fence is the epoch only (see Limits).

State machine of a worker attempt: `STARTED -> SUCCEEDED` (candidate head required) or `FAILED` by `finish_worker_attempt`; `STARTED -> STOPPED` only by `stop_story`. Only one attempt may be open; numbers are consecutive from 1. Patch proposals, gates, reviews and tests attach to an attempt that exists and is not STOPPED.

Attempt rules: a patch proposal attaches only to a STARTED attempt and must carry that attempt's `base_head` (otherwise `kind='conflict'`). Finishing an attempt as SUCCEEDED must name the `candidate_head` of an ACCEPTED proposal of that attempt when one exists (otherwise `kind='conflict'`); with no ACCEPTED proposal the candidate head is the caller's report of the worker's own commit and is only format-checked. Gates, reviews and tests attach to any attempt that is not STOPPED (tests are run after the worker finished). `link_receipt` for WORKER_ATTEMPT and REVIEW_ITERATION needs a positive decimal key without leading zeros, compared as an integer; the receipt must belong to the same story.

Recording rules that guard the data: `applied` is derived, never trusted: it is true only for verdict ACCEPTED with `post_materialize_verified` exactly true, and a record whose `applied` field differs is refused. Every hunk must be `[added, deleted]` non-negative integers, `attempted_proposal_lines` must equal the sum over the hunks, an applied record must have `proposal_lines` equal to that sum and any other record `proposal_lines` 0, and an ACCEPTED record needs `candidate_head` and `report_sha256`. `applied_hunks` equals the attempted hunk count only when applied, otherwise 0 (built but not verifiably written hunks are never counted as applied). A gate ACCEPTED needs an isolation proof that `worker_gate.proof_is_honest` accepts and without FAILED entries; statuses are stored as reported and never promoted. REFUSED and BLOCKED gates need a reason.

## Stop path

`stop_story(story_id, epoch, step_id, reason)` writes one `pl_story_control` row and marks the open attempt STOPPED in the same transaction. It is idempotent: the same step id replays; another step id returns the first stop (`already_stopped` true) and writes nothing. After a stop every other step is refused with `kind='stopped'`. Accepted after a stop: reads (`get_status`, `get_step`, `list_*`), replays of steps recorded earlier, and `acknowledge_stop(story_id, epoch, step_id, actor)`, which records a `STOP_ACK` step (refused with `kind='pipeline'` when the story is not stopped). The stop does not touch leases or the epoch of the store; stopping the worker process is the supervisor's job.

## Migration and rollback procedure

The only way to create the pipeline tables is `migrate_pipeline(db_path)`; `PipelineState(store)` raises `kind='schema'` while the pipeline version is not 1.

1. Take the lock file `<db>.migrate.lock` (`O_EXCL`). Held or stale: `MigrationError(kind='locked')`. Locks are never broken automatically; `clear_stale_lock(db_path, token)` needs the token written inside the file. A holder removes the lock on release only if the file still carries its own token; otherwise it leaves the file alone and raises (`kind='locked'`).
2. Open the write transaction (`BEGIN IMMEDIATE`) first. Inside it require `PRAGMA user_version` equal to the store's `SCHEMA_VERSION` (7); newer is `kind='newer'`, older is `kind='schema'`. A pipeline version above 1 is `kind='newer'`; pipeline tables without a version row, a table set that does not match, or a schema that differs from the frozen hash is `kind='partial'`. A missing file is refused and not created.
3. From that locked state create the rollback point in `<db>.rollback/` (SQLite online backup through a second connection, which sees the committed snapshot while the write lock is held, so nobody can change the state in between) and assert that the cheap state invariant of the backup equals the invariant of the locked state; otherwise `kind='backup'` and nothing is migrated. The manifest `rp-<utc>-<id>.manifest.json` holds `store_user_version`, `pipeline_version`, the backup file's `size` and `sha256`, `content_sha256` (user_version, every schema object and every row in rowid order, with the AUTOINCREMENT counters) and `invariant_sha256`. The point is re-read and fully verified before the migration continues.
4. Journal `migration.journal.json` is set to STARTED.
5. In the same transaction: create the nine tables, triggers and the partial index, insert the version row with the frozen schema hash, prove that everything that is not `pl_` is unchanged, check the pipeline version and `PRAGMA foreign_key_check`, COMMIT. Any failure rolls back; the journal becomes ABORTED and `MigrationError(kind='migration')` is raised. The database is at the old version or the new one, never in between.
6. Journal set to COMMITTED, lock released.

Lock time. Inside the write lock the live database is scanned only by the cheap state invariant: the non-pl_ `sqlite_master` entries, the row count and max rowid of every table, the sequences and `user_version`. It does not see an UPDATE that keeps counts and max rowid. The full row digest is computed on the backup copy, so a corrupted or altered backup is still caught at load time. The backup copy, its digest and the manifest are produced while the write lock is held, because the rollback point must be complete and verified before the first DDL statement; for a large store this lengthens the lock (see Limits).

Frozen schema v1. The DDL uses literal enum lists. The SHA-256 of the pl_ entries of `sqlite_master` (type, name, table, sql, sorted) is stored in `pl_schema_version.schema_sha256` and compared at every `pipeline_version` call (migration, status, `PipelineState` construction, every step) with the live schema and with the hash of the DDL in `pipeline_schema.py` applied to an empty in-memory database. A dropped trigger or index or an edited CHECK is reported as `kind='partial'` and nothing is repaired. A change of the v1 DDL after release needs pipeline schema version 2.

Detecting and resuming: `migration_status(db_path)` returns NOT_MIGRATED, CURRENT, INTERRUPTED (journal STARTED, database at the old version) or COMMIT_UNRECORDED (committed, journal not closed). Running `migrate_pipeline` again resumes in both cases (INTERRUPTED takes a fresh rollback point and migrates; COMMIT_UNRECORDED only closes the journal). A second run on a current database changes nothing and takes no new rollback point.

### Scoped rollback: `down_migrate_pipeline(db_path, allow_data_loss=False)`

This is the targeted rollback of the schema change. Under the lock and `BEGIN IMMEDIATE` it checks the store version, refuses (`kind='data'`) while any pl_ row besides the version row exists unless `allow_data_loss=True`, writes a `pre-down-migration` rollback point, drops the nine pl_ tables (their triggers and index go with them) and proves that the state invariant of everything else is unchanged and that no pl_ object remains. Result: exactly the schema objects and rows of the store before the migration, with nothing else touched (events, receipts, leases, budget stay). On a database at version 0 it does nothing. The dropped rows stay in the pre-down-migration point.

### Whole-store restore: `restore_rollback_point(db_path, manifest_path, confirm_stopped=True, allow_store_version_change=False)`

Restore is whole-store and is the last resort. Everything written after the point is lost: events (the event hash chain is cut back and an external event anchor then no longer matches the database), receipts, leases, budget, phases and all pipeline rows. Use `down_migrate_pipeline` when only the schema change must go.

It refuses unless: the caller passes `confirm_stopped=True` (an attestation that no Store, worker or supervisor uses the file); the manifest lives in this store's rollback directory; the manifest keys, backup file name (no path separators), size, sha256, SQLite `integrity_check`, `user_version`, row digest and invariant all verify (`kind='backup'`); the point's store schema version equals the current one, unless `allow_store_version_change=True`, which is recorded in the journal note (`kind='restore'`); and a `BEGIN EXCLUSIVE` probe on the target succeeds (a live writer makes it fail, `kind='restore'`). Idle connections cannot be detected by the probe, and the window between the probe and the copy is not closed, so `confirm_stopped` is the real guard. It then takes a `pre-restore` point of the current state, copies the backup over the store with the SQLite backup API, and proves `integrity_check`, `user_version` and the row digest against the manifest (`kind='restore'` otherwise, naming the pre-restore point). The result is a logical copy (same objects and rows), not byte-for-byte.

Operator steps: stop every writer; `migrate_pipeline(path)`; keep `<db>.rollback/` until the sprint is accepted. To undo the schema change: `down_migrate_pipeline(path)`. To return the whole store to the migration time: stop writers, `restore_rollback_point(path, <pre-migration manifest>, confirm_stopped=True)`, reopen the store.

## Limits

- Pipeline writes are not in the store's HMAC event chain (the `events` table has a closed kind list and its upgrade would change the store schema); `pl_steps` is append-only by trigger but not signed. A person with file write access can edit the database.
- The manifest detects accidental corruption and truncation; it is not a signature.
- The epoch is the only fence: a step does not require a live lease or an unexpired owner, and `stop_story` does not fence leases.
- Restore needs all other connections closed and an open `Store` must be reopened. A stale lock needs a manual `clear_stale_lock`.
- The rollback point (online backup, full digest, manifest) is made while the write lock is held, so the lock lasts as long as it takes to copy and read the whole store; the in-lock checks of the live database are the cheap invariant only.
- The cheap invariant misses an UPDATE that keeps row counts and max rowids; the backup's full digest and the transaction itself bound that risk, nothing more.
- `applied_hunks` is derived: the run record carries attempted hunks and a boolean `applied`, so the applied count equals the attempted count when the record is applied.
- Without an ACCEPTED proposal the candidate head of a SUCCEEDED attempt is a caller report only.
- The review-loop driver (U5-4) and the final package (U5-5) are not part of this task; only their rows exist.
- All tests are NOT_RUN; the SQL, the trigger behaviour, the online backup into a WAL database and the Windows file handling were checked by reading only.
- U5-4 remediation (additive): `record_review_iteration` and `record_diff_gate` accept an optional `facts` JSON object. It is part of the step payload digest and of the stored step result (readable with `get_step`), written in the same transaction as the row. No table, column or trigger changed, so the frozen schema v1 and its hash are untouched; a call without `facts` has the same payload digest as before.
