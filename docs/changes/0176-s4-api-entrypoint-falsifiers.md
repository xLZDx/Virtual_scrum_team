# 0176 — Add falsifiers for unmapped S4 Python entrypoints

## What changed

Added `tests/vst/test_s4_python_api_entrypoints.py` with 13 focused tests for entrypoints whose existing tests had no exact-name reference or whose only candidate selector already belonged to `functional`/`e2e`:

1. `contracts.validate_task_manifest_v2` rejects missing required contract fields.
2. `Store.acquire_epoch_idempotent` replays one epoch acquisition without a second advance.
3. `Store.resume_epoch_idempotent` rejects an unrecorded checkpoint without changing the epoch.
4. `Store.charge_idempotent` replays a charge once and verifies the expected ledger snapshot through the public API.
5. `Store.append_manual_override` rejects an unsigned record without a control-history write.
6. `Store.begin_action` rejects a mismatched action/transaction ID without recording intent.
7. `Store.startup_reconcile` verifies the local event history and leaves it valid.
8. `Store.lookup_idempotent_operation` returns a payload-bound completed result and rejects a changed lookup payload.
9. `Store.stop_attempt_fenced` advances the epoch, reports the lease as fenced, and prevents an old-epoch receipt from being appended.
10. `Store.append_receipt_idempotent` returns one receipt for replay and rejects changed payload under the same key.
11. `Store.consume_preflight` permits one run/nonce and rejects reuse without changing the public event anchor.
12. `Supervisor.prepare_run` binds fresh run and nonce values and rejects reuse.
13. `Supervisor.resume` transitions STOPPED to READY only after invoking the supplied epoch callback.

Assertions use public return values and store read APIs. No product code was changed. The inventory and category selector updates are sequenced after this test commit so the category provenance can point to the exact committed test source.

## Why

The source-derived inventory in change 0175 identified ten names with no exact test-body reference. It also identified three names whose only exact candidate selector was already assigned to another primary category (`functional` or `e2e`): `Store.resume_epoch_idempotent`, `Store.charge_idempotent`, and `Supervisor.resume`. Because AC-1 permits one primary category per test ID, these receive separate API selectors rather than duplicate assignments. The cases cover positive and negative outcomes for AC-2/AC-7 within the accepted five-module S4.3.2 scope.

## Verification state

Tests have not yet been run. After committing this file, the canonical API category will include these 13 node IDs plus one distinct existing candidate selector per remaining inventory row. The resulting focused API+seeded run must execute on the exact manifest commit and report every selected node, with the Windows symlink scenario retained as NOT_RUN if the host privilege remains unavailable.

## Remaining scope

The full API denominator also includes existing candidate tests from other API callables. They will be added only when their IDs are not already assigned to functional/integration/E2E. Tests outside the accepted five modules and S4 QA registry contract selectors are not being added. Signer/report-bound acceptance remains a separate environment-dependent gate.
