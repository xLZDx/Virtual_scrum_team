# U5-3: pipeline state and store migration

Modules: `tools/vst/pipeline_schema.py` (DDL and enums), `tools/vst/pipeline_migration.py` (migration, rollback point, restore), `tools/vst/pipeline_state.py` (`PipelineState`). Tests: `tests/vst/test_u5_pipeline_state.py` (written, **NOT_RUN**: running tests is forbidden by the operator for this sprint, so no result is claimed; nothing was executed, only syntax-parsed).

Acceptance (PROJECT_PLAN U5-3): the store models story, worker attempt, patch proposal, diff gate, review iterations, tests and receipts with epoch checks, idempotent steps and a stop path; any schema change has a migration, a rollback point and a test that restores the previous state.

## Where the state lives

Baseline decision BD-1 stays: `tools/vst/store.py` is the state authority. The pipeline tables are an additive extension in the same SQLite file. They are versioned on their own in `pl_schema_version` (pipeline schema version 1; version 0 means no `pl_` table). The store's `PRAGMA user_version` stays 7 and no existing table, trigger or API changed, so every existing store test keeps its meaning. The story itself is the existing `stories` row (id, project, phase, epoch, owner); the pipeline never copies it.

## Data model (pipeline schema version 1)

| Table | One row is | Key | Notes |
|---|---|---|---|
| `pl_schema_version` | the pipeline schema version | component | never deleted |
| `pl_steps` | one accepted step (the idempotency ledger) | story_id, step_id | kind, epoch, payload sha256, stored result; append-only |
| `pl_story_control` | a stop marker | story_id | row present = story stopped; append-only |
| `pl_worker_attempts` | one worker attempt | story_id, attempt_no | base_head, candidate_head, state STARTED then SUCCEEDED, FAILED or STOPPED; identity immutable, a closed row never changes |
| `pl_patch_proposals` | one U5-2 run record | story_id, proposal_id | proposal_document_sha256 (the record's report_sha256), base_head, candidate_head, verdict, stage, attempted_hunks, applied_hunks, proposal_lines, model_lines, the full run record as JSON |
| `pl_diff_gates` | one U5-1 gate verdict | story_id, gate_id | verdict, reasons, isolation proof JSON, per-property statuses (VERIFIED, NOT_VERIFIED, CALLER_ASSERTED, FAILED) |
| `pl_review_iterations` | one review iteration | story_id, iteration_index | iteration_of, findings_count, declared coverage, verdict CLEAN, FINDINGS, PARTIAL or BLOCKED |
| `pl_test_evidence` | one test result of one attempt | story_id, evidence_id (unique per attempt and test_id) | status PASS, FAIL, BLOCKED, NOT_RUN, INCONCLUSIVE; evidence sha256; reason |
| `pl_receipt_links` | a link from a pipeline row to an existing receipt | story_id, receipt_id, subject_kind, subject_key | the receipt stays in the store's `receipts` table and is not copied |

Database-level rules (CHECK and triggers): no update or delete on any row except `pl_worker_attempts` going STARTED to one terminal state once; an applied hunk count never exceeds the attempted count and is 0 unless the verdict is ACCEPTED; an ACCEPTED gate has an isolation proof; iteration 1 has no `iteration_of`, later ones point to an earlier index; CLEAN has zero findings; PASS and FAIL carry an evidence digest and every other status carries a reason.

## Step rules

Every mutating `PipelineState` method is a step with `(story_id, step_id)` and the caller's `epoch`. In one `BEGIN IMMEDIATE` transaction of the store:

1. Unknown story: `StoreError(kind='story')`. Epoch not equal to the story's current epoch: `kind='epoch'`, nothing written. The epoch check comes first, so a stale caller is refused even when it only replays an old step.
2. `pl_steps` lookup. Same id, same kind, same payload digest: the stored result is returned (`StepResult.replayed` is True) and nothing is written. Same id with another kind or payload: `kind='conflict'`. The digest covers kind and payload, not the epoch, so a new owner may replay a step recorded under an older epoch.
3. Story stopped: `kind='stopped'`, unless the step is the stop path.
4. The step applies its rows (argument and consistency checks raise `kind='argument'` or `'pipeline'`) and records itself. Any exception rolls the whole transaction back; a crash before COMMIT leaves nothing, a retry after COMMIT replays.

Two concurrent requests with the same step id: the second waits for the write lock and then replays. Steps do not take or check a lease; the fence is the epoch only (see Limits).

State machine of a worker attempt: `STARTED -> SUCCEEDED` (candidate head required) or `FAILED` by `finish_worker_attempt`; `STARTED -> STOPPED` only by `stop_story`. Only one attempt may be open; numbers are consecutive from 1. Patch proposals, gates, reviews and tests attach to an attempt that exists and is not STOPPED.

Recording rules that guard the data: a patch proposal record with `applied` true but a non-ACCEPTED verdict, proposal lines without `applied`, or an ACCEPTED verdict without `candidate_head` and `report_sha256` is refused; `applied_hunks` equals the attempted hunk count only when the record says applied, otherwise 0 (built but not verifiably written hunks are never counted as applied). A gate ACCEPTED needs an isolation proof that `worker_gate.proof_is_honest` accepts and without FAILED entries; statuses are stored as reported and never promoted. REFUSED and BLOCKED gates need a reason.

## Stop path

`stop_story(story_id, epoch, step_id, reason)` writes one `pl_story_control` row and marks the open attempt STOPPED in the same transaction. It is idempotent: the same step id replays; another step id returns the first stop (`already_stopped` true) and writes nothing. After a stop every other step is refused with `kind='stopped'`. Accepted after a stop: reads (`get_status`, `get_step`, `list_*`), replays of steps recorded earlier, and `acknowledge_stop(story_id, epoch, step_id, actor)`, which records a `STOP_ACK` step (refused with `kind='pipeline'` when the story is not stopped). The stop does not touch leases or the epoch of the store; stopping the worker process is the supervisor's job.

## Migration and rollback procedure

The only way to create the pipeline tables is `migrate_pipeline(db_path)`; `PipelineState(store)` raises `kind='schema'` while the pipeline version is not 1.

1. Take the lock file `<db>.migrate.lock` (`O_EXCL`). Held or stale: `MigrationError(kind='locked')`; locks are never broken automatically, `clear_stale_lock(db_path, token)` needs the token written inside the file.
2. Require `PRAGMA user_version` equal to the store's `SCHEMA_VERSION` (7). Newer: `kind='newer'`; older: `kind='schema'`. Pipeline version above 1: `kind='newer'`. Pipeline tables without a version row, or tables that do not match the recorded version: `kind='partial'`. A missing file is refused and not created.
3. Create the rollback point in `<db>.rollback/`: SQLite online backup (`rp-<utc>-<id>.sqlite`, journal mode DELETE so it is one file) and `rp-<utc>-<id>.manifest.json` with `store_user_version`, `pipeline_version`, the backup file's `size` and `sha256`, and `content_sha256` (a digest of the user_version, every schema object and every row, in rowid order, including the AUTOINCREMENT counters). The point is re-read and verified before the migration continues.
4. Journal `migration.journal.json` is set to STARTED.
5. In one `BEGIN IMMEDIATE` transaction: create the nine tables and triggers, insert the version row, prove that the digest of everything that is not `pl_` is unchanged, check the pipeline version and `PRAGMA foreign_key_check`, COMMIT. Any failure rolls back; the journal becomes ABORTED and `MigrationError(kind='migration')` is raised. The database is at the old version or the new one, never in between.
6. Journal set to COMMITTED, lock released.

Detecting and resuming: `migration_status(db_path)` returns NOT_MIGRATED, CURRENT, INTERRUPTED (journal STARTED, database at the old version) or COMMIT_UNRECORDED (committed, journal not closed). Running `migrate_pipeline` again resumes in both cases (INTERRUPTED takes a fresh rollback point and migrates; COMMIT_UNRECORDED only closes the journal). A second run on a current database changes nothing and takes no new rollback point.

Rollback: `restore_rollback_point(db_path, manifest_path)`. The manifest must live in this store's rollback directory. Under the lock it verifies the manifest keys, the backup file name, size and sha256, SQLite `integrity_check`, `user_version` and the row digest, and refuses a corrupted or foreign point before touching the store (`kind='backup'`). It then takes a `pre-restore` rollback point of the current database, copies the backup over the store with the SQLite backup API, and proves `integrity_check`, `user_version` and the row digest against the manifest (`kind='restore'` otherwise, naming the pre-restore point). Result: the same schema objects and the same rows as before the migration (a logical, not byte-for-byte, copy: file layout and the free list may differ).

Operator steps: stop every writer; `migrate_pipeline(path)`; keep `<db>.rollback/` until the sprint is accepted; to roll back, stop writers, run `restore_rollback_point` with the `pre-migration` manifest, reopen the store.

## Limits

- Pipeline writes are not in the store's HMAC event chain (the `events` table has a closed kind list and its upgrade would change the store schema); `pl_steps` is append-only by trigger but not signed. A person with file write access can edit the database.
- The manifest detects accidental corruption and truncation; it is not a signature.
- The epoch is the only fence: a step does not require a live lease or an unexpired owner, and `stop_story` does not fence leases.
- Restore needs all other connections closed (SQLite refuses it otherwise), and an open `Store` must be reopened. A stale lock needs a manual `clear_stale_lock`.
- The content digest reads every row of the database: cost grows with the store size.
- `applied_hunks` is derived: the run record carries attempted hunks and a boolean `applied`, so the applied count equals the attempted count when `applied` is true.
- The review-loop driver (U5-4) and the final package (U5-5) are not part of this task; only their rows exist.
- All tests are NOT_RUN; the SQL, the trigger behaviour and the Windows file handling were checked by reading only.
