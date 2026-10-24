# S1 remediation: E1-E4 functional test run

## Scope
Focused functional tests for epics E1 (contracts), E2 (gate), E3 (store) and E4 (runner and signing) after review remediation A (change record 0015) and B (change record 0016). E5 (slice and process death) is covered by a separate evidence file (`s1-remediation-e5-test-run.md`) and is not part of this run.

## Revision
- `git rev-parse HEAD`: `63e0e3515801b707b67352ed1122559199aeb616`
- Working tree was DIRTY: the tested code (`tools/vst/contracts.py`, `gate.py`, `signing.py`, `store.py`, `runner.py`, `slice.py`, `schemas/README.md`) and the tests (`tests/vst/e1e4_helpers.py`, `test_e1_contracts.py`, `test_e2_gate.py`, `test_e3_store.py`, `test_e4_runner.py`) are uncommitted modifications on top of that HEAD; `core/DECISION_LOG.md` and `core/LESSONS_LOG.md` are staged. The result therefore proves the working tree, not the commit.

## Command
Run from `D:\Repo\Virtual_scrum_team` with the project interpreter:

```
C:\Python314\python.exe -m pytest -q -p no:cacheprovider tests/vst/test_e1_contracts.py tests/vst/test_e2_gate.py tests/vst/test_e3_store.py tests/vst/test_e4_runner.py -rs
```

Result (all four files in one run): `1105 passed, 2 skipped, 1 warning in 85.54s`.
The one warning is a third-party `pytest_asyncio` deprecation notice, unrelated.

## Per-file results (each file also run on its own)
| File | Passed | Skipped | Failed | Test functions (before -> after) |
|---|---|---|---|---|
| `tests/vst/test_e1_contracts.py` | 379 | 0 | 0 | not changed in this task |
| `tests/vst/test_e2_gate.py` | 308 | 0 | 0 | not changed in this task |
| `tests/vst/test_e3_store.py` | 210 | 1 | 0 | 67 -> 159 |
| `tests/vst/test_e4_runner.py` | 208 | 1 | 0 | 62 -> 108 |

Skips (both are environment guards, reported by `-rs`):
- `test_e3_store.py`: `test_database_file_is_owner_only_on_posix` skipped on Windows (POSIX permission bits are meaningless here), so the 0o600 chmod is NOT verified.
- `test_e4_runner.py`: `test_link_created_by_the_command_itself_gets_a_zero_digest` skipped because `os.symlink` is not permitted for this user; the pre-existing symlink/junction cases ran (junctions via `mklink /J`) and passed.

## What E3 now covers (contract -> tests)
- Construction and schema: required keyword `event_key` (>= 32 bytes), `PRAGMA user_version` 2, WAL, legacy un-versioned database refused (data left intact), foreign versions refused and not upgraded, no partial schema, foreign keys enforced, no dangling transaction after success or error.
- `StoreBusyError` (kind `busy`, subclass of `StoreError`) at call time and at open time, nothing written, retry works after the lock is released.
- Epoch CAS (existing cases kept, concurrent race with 4 stores), counter exhaustion, ttl bounds including NaN/inf; `set_phase`/`get_phase` (owner, epoch CAS, expiry, takeover, bounds 1..10, event payload, visibility to a second instance).
- `register_task`/`get_manifest`: hash, deep copy, idempotence without a second event, conflicting manifest, unknown story, project mismatch, invalid manifest, append-only `tasks`.
- Lease history: one row per attempt never overwritten (triggers for identity, delete, closed-lease reopen), one LIVE lease per task (database index), consecutive attempts, status values, slot points at `lease_id`, supervisor_key required and validated, task/story link, concurrent same-task and last-slot races.
- Retry cap: `RETRY_EXHAUSTED` marker committed before `kind='retry'` is raised, signed with the supervisor key, written once, blocks later leases and receipts; boundaries for cap 0, 1, 2; slot-at-cap without PASS vs with PASS; receipt attempt bound; gate hard-blocks it.
- Receipts: worker signature (wrong key, wrong label, old unlabeled HMAC, tampering, forged PASS with valid signature), manifest and role hash, task/story link, declared slot and type, epoch, live lease holder and expiry, released lease, chain gap and prev hash, replay, duplicate `receipt_id` (also across tasks), `wrote` flag set only on success, atomic failure, concurrent identical append, store output approved by the gate.
- Supervisor isolation both ways (worker path refuses the supervisor slot even when perfectly signed; supervisor path refuses worker slots), supervisor key signature, marker shape rules, `WORKER_LOST` only for leases with `wrote = 0` (leases that wrote are flagged only), current epoch on markers, gap-free supervisor chain, idempotent `mark_budget_exceeded` (second call returns the first marker, one `BUDGET_BLOCKED` event), terminal markers block leases and receipts, both terminal markers in one chain.
- Keyed event chain: different key fails, store-internal kinds closed for `record_event`, CHECK constraints for event kind, story state, lease status and `wrote`; 16 tamper cases on a copy including tail truncation by 1 and 3 events, truncation of everything, deleted/forged/garbage anchor and a forged unkeyed anchor; `event_anchor()` values; the documented limit (full rollback to an older consistent pair passes the chain check and is only caught by comparing against an anchor kept outside).
- Budget (including concurrent charges that never exceed the cap), integer bounds (`init_slots`, counters, ttl, budget), render of lease history, phase and read-only behaviour.

## What E4 now covers
- Manifest binding: `task_id`, `role_sha256`, `manifest_sha256` come from the manifest (the old `task_id`/`role_sha256` parameters are gone), hash changes with the manifest, manifest is not mutated, invalid/foreign manifests refused before anything runs.
- `allowed_commands` equality (extra arg, prefix, whitespace, case, reordered, command of another slot, one bad command blocks the whole run before any starts); `expected_test_ids` set-equality with the slot's required tests (missing, extra, duplicate, case, empty, wrong type); slot must be a TestRun slot; `covered_acceptance` subset; `retry_cap` and `timeout_sec`/`deadline_sec` bounds.
- Output cap: exit -3 for stdout and stderr independently, exact-cap boundary, default 1 MiB boundary, drain of an 80x64 KiB flood without deadlock, truncated exit code wins over a failing exit code, ids hidden beyond the cap never PASS.
- Process-tree kill on timeout (a grandchild writing a heartbeat file must stop), overall deadline (later commands are skipped and never started), deadline below the per-command timeout.
- Minimal environment: only allowlisted names plus `PYTHONIOENCODING` and explicit `extra_env`; secrets set in the parent (including the signing key) are invisible to the child; `build_environment` unit test; stdin closed.
- Artifact containment: traversal, absolute, drive-letter, backslash, `.`/empty segments, surrounding whitespace refused before running; link/junction components refused (to outside and to inside); directory as artifact gets the zero digest; nested relative artifacts hashed after the commands; gate resolver cases and "no resolver means denied".
- Label-scoped HMAC: the signature equals HMAC(key, `vst-receipt-v1\0` + canonical body) computed independently; the unlabeled HMAC and the waiver-labeled signature do not verify; bad labels raise; keys of 31 bytes rejected, 32 accepted (also bytearray); every receipt field tamper (including `manifest_sha256`) breaks verification.
- Gate integration: runner receipt plus bound sibling receipts is APPROVE; replay against another head, epoch, task, changed manifest and widened `allowed_commands` manifest is rejected; forged, wrong-key and relabeled signatures are rejected; retry chain through the runner.

## Defects found
- Product bugs: none. No file under `tools/vst` was edited by this task.
- Test defects fixed while regressing (all in the tests I wrote, none weakened to force a pass):
  1. `test_parser_receives_joined_stdout_in_order` compared raw stdout; on Windows the child emits CRLF and the runner does not translate newlines (it decodes the raw bytes). The test now normalises `\r\n` before comparing the join order.
  2. `test_timeouts_are_bounded_by_the_manifest`: the helper default `timeout_sec=30` violated the 5 second manifest bound first, so the deadline branch was not reached; the deadline cases now pass `timeout_sec=None`.
  3. `test_invalid_or_foreign_manifests_are_rejected_before_running`: the helper replaced `m=None` by a default manifest, so the `None` case did not exercise the runner; the helper now uses a sentinel.
  4. `test_ids_hidden_beyond_the_cap_cannot_produce_a_pass` expected FAIL; the real, stronger outcome is INCONCLUSIVE with no executed ids and exit -3 (never PASS). The expectation was corrected to the real contract.
  5. `test_edited_exit_code_after_signing_is_rejected` used a manifest that allowed only the failing command but ran the default command; it now runs the allowed one.
- Observations for the owner (not defects against a decision): the runner returns CRLF on Windows unchanged, so parsers must tolerate `\r\n` (the line parser used in the tests does). The A-owned "Known limits" bullet in `tools/vst/schemas/README.md` about event tail truncation is stale (reported in change record 0016); the new tests prove truncation is detected.

## Unverified remainder
- File mode 0o600 of the database and its WAL files (POSIX only; skipped on Windows).
- Creation of a symlink by the child command itself during the run (skipped: `os.symlink` not permitted); post-run hashing of a link is thus covered only by code reading, while pre-existing links and junctions are covered by tests.
- POSIX process-group kill (`os.killpg`) and the POSIX branch of the environment allowlist were not exercised; only the Windows `taskkill /T /F` path ran.
- Behavior of `StoreBusyError` under real inter-process contention beyond a second connection holding `BEGIN IMMEDIATE` (single machine, SQLite WAL).
- Mutation or red-first evidence was not produced (operator rule: no mutation runs); assertion strength is argued from the assertions themselves (exact values, kinds and row states, not "did not raise").
- E5 and the slice harness, and any repo-wide suite, lint or CI, were not run here.
