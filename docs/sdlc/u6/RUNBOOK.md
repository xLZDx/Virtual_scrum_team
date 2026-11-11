# U6-1 Install and rollback runbook

Scope: how to set the pipeline up on a Windows machine, how to pin the AEVE role table, how to undo a schema change and a code change, and how to prove that an undo restored the exact previous state. Every command and function named here exists in this repository at the time of writing (read in U6-1). Nothing in this document was executed: every step is **NOT_RUN** unless a line says otherwise, because running tests and scripts for this task is forbidden by the operator.

## 1. Prerequisites

- Python 3.14 at `C:/Python314/python.exe`. Always call it explicitly and with `-s` (skip the user site directory, which is slow and can shadow modules): `C:/Python314/python.exe -s ...`. Bare `python` may be another virtual environment.
- `PYTHONPATH` is the repository root (the checkout you work in), because the tools import as `tools.vst...` and `tools.uc...`. Example in Git Bash: `PYTHONPATH=D:/Repo/Virtual_scrum_team C:/Python314/python.exe -s -m tools.vst.<module>`. Example in PowerShell: `$env:PYTHONPATH = "D:/Repo/Virtual_scrum_team"`.
- Git, on PATH. A read-only AEVE checkout (see section 3) when the role table is rebuilt.
- Standard library only for the modules named here; no network is needed for install, rollback or the rollback exercise.

Windows notes:

- **CRLF versus LF.** `.gitattributes` pins `* text=auto` and `eol=lf` for `*.md`, `*.py`, `*.json`, `*.yml`, `*.yaml`. Python on this machine writes CRLF with `write_text` and `open(..., "w")`; pass `newline="\n"` (or write bytes) when a file is pinned to LF. Digests that must not depend on line endings normalize them explicitly (the project-role `source_sha256` converts CRLF and CR to LF); other digests hash raw bytes, so a CRLF checkout of a file gives another digest. The patch writer refuses any repository that sets `text` or `eol` attributes on the target (`UNTRUSTED_GIT_CONFIG`, see `docs/sdlc/u5/REAL_CHANGE.md`, defect 1); this repository does, so the pipeline cannot apply a patch here today.
- **Long paths (more than 260 characters).** A path longer than the Windows limit fails with WinError 3 or 206 inside `os.replace` and file opens. The AEVE ledger under a deep state directory failed this way (`docs/sdlc/u5/REAL_CHANGE.md`, defect 4). Use a short state directory such as `D:/tmp/u5-7-aeve-state`, and a short worktree path. The rollback directory `<db>.rollback/` adds a manifest and backup name of about 60 characters to the database path.
- **`os.replace` transient refusals.** `os.replace` and file deletion can be refused briefly (WinError 5 or 32) while another process, an indexer or an antivirus holds the file. `pipeline_migration` replaces files through its own `_replace` helper; if a step still fails, wait a few seconds and run it again. All steps below are safe to repeat unless a step says otherwise. Never delete a lock file by hand: use `clear_stale_lock` (section 4).
- Windows reserves some TCP ports (8054-8153 on this machine); not used here.

## 2. Install

All steps are NOT_RUN.

1. Create a scratch worktree for the work (not the shared checkout): `git worktree add D:/tmp/scratch_worktrees/<name> -b <branch> <base>`. Check `git status --short` is empty and note `git rev-parse HEAD`; this is the **base head** used by section 5.
2. Set `PYTHONPATH` to that worktree and call `C:/Python314/python.exe -s`.
3. Migrate the pipeline schema of the store (writes `pl_` tables into the same SQLite file; store `user_version` must be 7):
   `C:/Python314/python.exe -s -c "from tools.vst.pipeline_migration import migrate_pipeline; print(migrate_pipeline(r'<db_path>'))"`
   Stop every writer of the store first. The call takes the lock `<db>.migrate.lock`, writes a verified rollback point into `<db>.rollback/` (`rp-<utc>-<id>.manifest.json` plus `.sqlite`), applies the DDL and commits, or leaves the database unchanged. A second call on a migrated database changes nothing (`performed` False).
4. Check: `migration_status(r'<db_path>')` (same module) must report `state: CURRENT`, `pipeline_version: 1`, `journal_state: COMMITTED`. `INTERRUPTED` or `COMMIT_UNRECORDED` mean an earlier run stopped half-way; run `migrate_pipeline` again (it resumes).
5. Keep `<db>.rollback/` until the sprint is accepted; it is the input of every rollback in section 4.

## 3. Pin the AEVE role table

Facts from `docs/sdlc/u4/PROJECT_ROLES.md` and `tools/uc/role_table.py`; the pin value itself is an owner decision and is not changed by any tool here.

1. The pin has two parts. In the committed table `catalog/role_table.json`, `aeve_pin` is `{head, matrix_digest_sha256}` taken from the AEVE probe. At the gate, `analyzer_trust["pinned"]["role_table_sha256"]` (and the AEVE head) are gate-owned values compared by strict equality with the receipt (`tools/vst/gate.py`; refusals `ROLE_TABLE_DRIFT`, `AEVE_HEAD_DRIFT`).
2. Rebuild or check the global table against a read-only AEVE checkout:
   `C:/Python314/python.exe -s tools/uc/role_table.py build --aeve-root <AEVE> --inventory catalog/inventory.json --draft <draft.json> --out <table.json>`
   `C:/Python314/python.exe -s tools/uc/role_table.py validate --aeve-root <AEVE> --inventory catalog/inventory.json --table catalog/role_table.json`
   Exit 0 prints `status: VALID` with the `aeve_pin`; exit 1 lists problems; exit 2 is an AEVE probe failure (`BLOCKED`). `build` writes only a validated table.
3. Project-scope roles (extended table), with the project label always given explicitly:
   `C:/Python314/python.exe -s tools/uc/project_roles.py scan --project-root <repo> --project-label <label> --print`
   `C:/Python314/python.exe -s tools/uc/project_roles.py register --project-root <repo> --project-label <label> --base-table catalog/role_table.json --aeve-root <AEVE> --inventory catalog/inventory.json [--mapping mapping.json] --out table.json`
   `C:/Python314/python.exe -s tools/uc/project_roles.py validate --project-root <repo> --project-label <label> --table table.json --aeve-root <AEVE> --inventory catalog/inventory.json [--mapping mapping.json]`
   The digest to pin is `table_sha256(table)` (`tools/uc/project_roles.py`), the sha256 of the canonical file bytes (`serialize_table`); `validate` checks the file bytes are canonical, so the printed digest is the file digest.
4. Any change to a role file, the manifest or the table changes `source_sha256`, the manifest digest and the table digest. After such a change a receipt carrying the new digest against the old pin is refused with `ROLE_TABLE_DRIFT`. The pin owner re-issues the pin deliberately from the new `table_sha256`. Wiring the extended table into the live router invocation is an owner step and is not done by any tool here.
5. To roll a pin back: restore the previous table file from git (section 5 for a committed change) and re-issue the previous digest; confirm with `validate` and by recomputing the digest.

## 4. Roll back the pipeline schema

Choose the smallest rollback that fits. All steps are NOT_RUN.

**A. Scoped: drop only the pipeline tables** (`tools/vst/pipeline_migration.py`, `down_migrate_pipeline`). Use this to undo `migrate_pipeline`.

1. Stop every writer. An open `PipelineState` (`tools/vst/pipeline_state.py`) refuses its next step after the schema is gone; that is expected.
2. `C:/Python314/python.exe -s -c "from tools.vst.pipeline_migration import down_migrate_pipeline; print(down_migrate_pipeline(r'<db_path>'))"`
3. If it refuses with `kind='data'` because `pl_` rows exist, the rows would be lost. A `pre-down-migration` rollback point is written first and keeps them, so after you have decided: `down_migrate_pipeline(r'<db_path>', allow_data_loss=True)`.
4. Result: `pipeline_version` 0, journal `DOWNGRADED`, everything that is not `pl_` unchanged (events, receipts, leases, budget). On a database already at version 0 it does nothing.

**B. Whole store: restore a rollback point** (`restore_rollback_point`). Last resort: everything written after the point is lost, the event hash chain is cut back and an external event anchor then no longer matches.

1. Stop every writer; close every `Store`.
2. Pick the manifest in `<db>.rollback/` (for example the `pre-migration` one named in the `MigrationResult.rollback_manifest` of the install step).
3. `C:/Python314/python.exe -s -c "from tools.vst.pipeline_migration import restore_rollback_point; print(restore_rollback_point(r'<db_path>', r'<manifest_path>', confirm_stopped=True))"`
   It verifies the manifest and backup completely, probes `BEGIN EXCLUSIVE`, writes a `pre-restore` point of the current state, then copies the backup in. `allow_store_version_change=True` is needed only when the point has another store schema version and is recorded in the journal.
4. Reopen the store. The result is a logical copy (same objects and rows), not byte-for-byte.

**Stale lock.** A crashed run can leave `<db>.migrate.lock`. Locks are never broken automatically. Read the token inside the lock file, then call `clear_stale_lock(r'<db_path>', '<token>')` (same module) once you are sure no process uses the store.

**Interrupted migration.** `migration_status` says `INTERRUPTED` or `COMMIT_UNRECORDED`; run `migrate_pipeline` again to resume, or do A to go back.

The pipeline has no separate "rollback point" API in `pipeline_state.py`: it requires the migrated schema and raises `kind='schema'` otherwise. Rollback points belong to `pipeline_migration.create_rollback_point`, which `migrate_pipeline`, `down_migrate_pipeline` and `restore_rollback_point` call for you.

## 5. Roll back a code change applied by the pipeline

The patch writer is `apply_proposals` in `tools/vst/patch_proposals.py` (`docs/sdlc/u5/PATCH_PROPOSALS.md`). Rules from that document:

- A failure before `MATERIALIZE` leaves the worktree byte-identical (nothing was written).
- A write failure is rolled back by the writer; if it cannot restore a file the result is BLOCKED with `ROLLBACK_CONFLICT`.
- A crash during `MATERIALIZE` leaves the journal `.git/vst-u5-2.journal` and the lock `.git/vst-u5-2.lock` (for a linked worktree, in its own git directory). The next call is BLOCKED (`JOURNAL_PRESENT`, `WORKTREE_LOCKED`). The operator inspects the worktree, restores it, and removes the two files by hand.
- An ACCEPTED apply leaves an **unstaged modification and no commit**. A retry is BLOCKED `DIRTY_WORKTREE`.

Steps (NOT_RUN):

1. Take the **pre-change snapshot** before any change, on a copy or a clean worktree: `snapshot_hash(root)` from `tools/vst/rollback_exercise.py` (format in section 6). Record the base head (`git rev-parse HEAD`).
2. Not yet committed: list the changed paths with `git status --short`, then restore exactly those paths from the base head: `git restore --source=<base_head> --staged --worktree -- <path> [<path> ...]`. Do not use `git reset --hard` or `git clean -f` (operator-only). Remove only files the change created (`git status --short` shows them as `??`), by naming them.
3. Already committed on the sprint branch, not pushed: `git revert <commit>` (creates a new commit; history is kept). Already pushed or merged: `git revert` through a new PR; never force-push.
4. Take the **post-rollback snapshot** and compare (section 6). The rollback is proven only when the two hashes are equal.

## 6. Prove the rollback: rollback exercise

`tools/vst/rollback_exercise.py` exercises a rollback on a directory tree and compares hashes. Tests: `tests/vst/test_u6_rollback_exercise.py` (written, NOT_RUN).

- `snapshot_hash(root)`: SHA-256 over the regular files under `root`, `.git` (file or directory, any depth) excluded, in the order of the sorted relative POSIX paths; per file the bytes `<path UTF-8> 0x00 <decimal length> 0x00 <file bytes>`. Empty directories, timestamps and permissions are not hashed. A symlink or other non-regular entry makes the snapshot fail (fail closed).
- `exercise_rollback(root, change, rollback)`: takes a snapshot, calls `change(Path(root))`, takes a snapshot, calls `rollback(Path(root))`, takes a snapshot. Returns a frozen `RollbackExerciseResult` with `snapshot_before`, `snapshot_after_change`, `snapshot_after_rollback`, `rollback_proven` (before equals after-rollback AND after-change differs from before), `error_code`, `error_detail`. It never raises for expected failures. Error codes: `ROOT_NOT_DIRECTORY`, `BAD_CALLABLE`, `SNAPSHOT_FAILED`, `CHANGE_FAILED` (rollback not run), `CHANGE_NO_EFFECT` (rollback not run; a rollback proves nothing then), `ROLLBACK_FAILED`, `ROLLBACK_INCOMPLETE` (a stray or changed file remains).
- Example (run against a scratch copy, never the live tree):
  `C:/Python314/python.exe -s -c "from tools.vst.rollback_exercise import exercise_rollback; r = exercise_rollback(r'<scratch_copy>', change_fn, rollback_fn); print(r.to_dict())"` where `change_fn` and `rollback_fn` are Python callables that take the root path.

## 7. Verify

NOT_RUN unless stated. After install: `migration_status` shows `CURRENT`. After a schema rollback: `migration_status` shows `NOT_MIGRATED`, `pipeline_version` 0. After a code rollback: `git status --short` shows no path of the change, `git diff <base_head> --stat` is empty for the change paths, and the snapshot hash equals the pre-change hash. After a pin change: `role_table.py validate` or `project_roles.py validate` exits 0 and the digest equals the intended pin. Tests for the helper are run once, by the test agents, per the sprint plan; this task did not run them.

## 8. Known limits

- Nothing here was executed. The commands were checked against the source by reading; their behaviour on this machine is unproven.
- The rollback exercise proves file bytes and relative paths only. It does not cover a SQLite database as a live file (use the manifest checks of `load_rollback_point`; the restore is a logical copy), permissions, timestamps, empty directories, or anything outside `root`. `.git` is excluded, so it says nothing about commits or refs.
- The exercise runs caller code. It cannot undo a change by itself and a failed change or rollback can leave the tree half-changed.
- The hash proves two states are byte-equal; it does not prove who made the change or that the rollback procedure used in production equals the one exercised.
- The rollback manifest detects accidental corruption; it is not a signature. A person with file write access can edit the database.
- `restore_rollback_point` cannot detect idle connections; `confirm_stopped=True` is the real guard. The rollback point is made while the write lock is held, so the lock lasts as long as the store copy takes.
- The pipeline cannot apply a patch in this repository while `.gitattributes` sets `text`/`eol` (`UNTRUSTED_GIT_CONFIG`); an ACCEPTED apply leaves no commit (`docs/sdlc/u5/REAL_CHANGE.md`, defects 1 and 5). The code rollback in section 5 is therefore reasoned from the documented behaviour, not seen in a real run.
- Re-pinning the gate value is an owner step; this runbook describes it and does not do it.
- Windows long paths, transient `os.replace` refusals and CRLF are handled by workarounds, not by checks in the helper.
