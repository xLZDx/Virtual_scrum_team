# S2 legacy schema-v5 recovery fixture repair

Date: 2026-10-29  
Repository: `D:\Repo\Virtual_scrum_team`  
Frozen product-source HEAD: `6a6d7886746379e2b68218bd8d4fba01edf0bf56`  
Test executor: `functional-test-reviewer`; Windows CPython 3.14.3, pytest 8.4.2.

## Acceptance and result

This maintenance repairs the historical S2 compatibility fixture used by the two existing pre-0473 schema-v5 recovery selectors. The old fixture created a current Store (schema v6) and then asserted that its `PRAGMA user_version` was 5. It therefore never supplied a real schema-v5 database to the compatibility path.

After the fixture repair, the exact two requested selectors passed: **6 passed, 0 failed, 0 skipped**, exit code 0, in 1.43 seconds. The first selector verifies a seven-field historical pending-recovery event survives schema upgrade and startup reconciliation, remains bound to the exact pending claim and authenticated event chain, blocks continuation until the current run preflight is consumed, and then permits only the authorized successor. The parameterized selector verifies five malformed or mismatched historical event forms remain fail-closed.

Exact command, run from the canonical repository root:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields
```

Observed output: `6 passed, 1 warning in 1.43s`, exit code 0. The warning is the existing `pytest_asyncio` deprecation of `asyncio.get_event_loop_policy`; it did not affect the result. No other selectors, modules, suite, build, lint, or migration verification script ran.

An initial invocation from `D:\Repo` rather than the repository root returned `ERROR: file or directory not found` and `no tests ran`; it did not execute tests. The passing command above was rerun from `D:\Repo\Virtual_scrum_team`.

## Historical fixture provenance

The fixture uses the historical schema-v5 event-kind set and confirms the created database has `user_version=5` and a v5 `events` table constraint before adding the old event. The exact seven-field event shape is grounded in the in-repository pre-0473 writer at `7120e2c^:tools/vst/store.py` (blob `81f3d2c4d5a0d3b75891207257408373000a86c2`): its `mark_pending_runner_executions_indeterminate` emitted only `event`, `state`, `grant_id`, `payload_sha256`, `reason`, `predecessor_state`, and `recovery_service_generation` for a pending predecessor. The same source declares `SCHEMA_VERSION = 5`.

The v5 table DDL is verified against the in-repo schema-v5 source at `9a5c41d^:tools/vst/store.py` (blob `3850bab9e953a3f57cb295be4153779f69e8cd15`). The v5-to-v6 change is in commit `ec9aefe`: its schema diff changes the version and adds `DISPATCH_INTENT_ACCEPTED` to the `events.kind` constraint, then migrates the `events` table; no other table DDL is added or changed by that schema bump. The fixture therefore builds the regular schema through the repository's schema generator while temporarily supplying the exact historical v5 version and event-kind set. It does not construct a v6 database and relabel only its pragma.

The test writes only a disposable `tmp_path` SQLite fixture. `allow_schema_upgrade=True` is used only when reopening that fixture through the product Store constructor. Both selectors assert the old fixture is schema v5 before reopening and schema v6 afterward. The hash-chained raw event assertions are retained both before and after upgrade: every row's previous hash and HMAC are verified and the external-anchor count/head must equal the complete event chain. This checks that the migration preserved the seven-field payload bytes, event MACs, and anchor state.

The malformed variants remain the original accepted negatives: unexpected legacy field, wrong predecessor state, grant mismatch, claim digest mismatch, and a recovery generation that is not a successor. No assertion was weakened.

## Prior failure and corrected fixture

The earlier combined Windows attempt is recorded in `s2-assignment-basis-functional-run-20261029.md` as an interim run at source HEAD `3d5f6c2048238a79fb92ddf805bc562b4b392a63`: **19 passed, 3 failed**. Its exact command was:

```powershell
C:\Python314\python.exe -m pytest -q tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_persistent_runner_service.py::test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor tests/vst/test_s2_persistent_runner_service.py::test_store_refuses_preflight_consumption_before_verified_startup_history
```

Two failures were over-narrow error-message expectations in the newly authored assignment-basis tests and were corrected there. The remaining failure was the historical selector's fixture assertion at then-line 189: it expected schema version 5 after `_store_with_claim_basis` had initialized schema version 6. The test had not yet reached the actual legacy recovery compatibility behavior. This was a test-fixture defect, not evidence of a product-code defect. The dedicated two-selector run above now executes the old event against a verified v5 fixture and passes; no selector remains failed in the focused current run.

The test module had no pre-existing working-tree changes at turn start (`git status --short -- tests/vst/test_s2_persistent_runner_service.py` was empty). Its HEAD blob before this repair was `695a677baaff2d68163f3f0c6d0af272dfe0aae1`; product source was not edited. The current product Store blob is `a1bcb739be2ee022fc18292ff988355610329608` at frozen HEAD `6a6d7886746379e2b68218bd8d4fba01edf0bf56`.

## Coverage map and limits

| S2 acceptance | Selector | Outcome proved | Limit |
|---|---|---|---|
| REQ-005 / REQ-006; legacy recovery compatibility | `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` | Real disposable v5 schema upgrades; seven-field event is accepted only for the matching pending claim; raw event HMAC/anchor survive; successor remains blocked until fresh run-bound preflight and then is accepted under current lease/claim checks. | Synthetic temporary SQLite database and synthetic event key; no production Store or peer. |
| REQ-005 / REQ-006; fail-closed legacy contract | `test_pre_0473_schema_v5_pending_recovery_event_rejects_malformed_or_mismatched_fields` (5 parameter cases) | Unknown fields, predecessor, grant, digest, or generation mismatch prevent reconciliation and claim-status approval after schema upgrade; raw event HMAC/anchor remain valid, isolating semantic rejection from hash corruption. | Does not test production key custody or runtime startup. |

Process-kill, crash, mutation, E8, restricted policy selectors, production runtime, and real authorization were not run. This evidence closes only the focused test-fixture maintenance and these two functional selectors; it does not close S2.

## Artifact identities

| Artifact | Identity |
|---|---|
| Frozen source HEAD | `6a6d7886746379e2b68218bd8d4fba01edf0bf56` |
| Product `tools/vst/store.py` blob | `a1bcb739be2ee022fc18292ff988355610329608` |
| Test module pre-edit HEAD blob | `695a677baaff2d68163f3f0c6d0af272dfe0aae1` |
| Test module after this repair, Git blob SHA-1 | `00558048e7e5a400f3cbd663973f39974e68a58f` |
| Historical pre-0473 schema/event writer | `7120e2c^:tools/vst/store.py`, blob `81f3d2c4d5a0d3b75891207257408373000a86c2` |
| Historical schema-v5 DDL | `9a5c41d^:tools/vst/store.py`, blob `3850bab9e953a3f57cb295be4153779f69e8cd15` |
| Schema-v5 to schema-v6 migration | `ec9aefe`, new Store blob `c2eb1834f1fe3e7f35af514a5c2d18c8cf508f74` |
