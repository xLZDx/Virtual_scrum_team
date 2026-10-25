# 0175 — Inventory the accepted Python API surface and exact gaps

## What changed

Added `docs/qa/python_api_inventory.md`, a source-derived table of the non-private top-level functions/classes and public methods defined in the five modules named by S4.3.2. It records 79 names, one candidate existing pytest ID where the parsed test body references the callable, whether that ID is required by the current canonical category manifest, and ten names with no exact-name test-body reference. Underscore-prefixed helpers are excluded; `supervisor.py` follows its explicit `__all__`. The API category coverage reason now links this inventory and states the concrete PARTIAL basis: 20 required API selectors do not map the full inventory, including ten names with no exact-name test reference.

The inventory labels name-reference matches as candidate evidence rather than claiming every name reference proves a falsifying assertion. It separates category-level runtime evidence from tests that merely exist elsewhere in the repository.

## Why

S4.3.2 and AC-2/AC-8 name five Python modules but do not enumerate their callable API. A source-derived finite inventory provides a reproducible denominator without inventing product APIs. It shows that a complete callable-by-callable category denominator is not established by the current 20 mapped API selectors. The explicit missing-reference set is:

- `contracts.validate_task_manifest_v2`
- `store.Store.acquire_epoch_idempotent`
- `store.Store.append_manual_override`
- `store.Store.begin_action`
- `store.Store.startup_reconcile`
- `store.Store.lookup_idempotent_operation`
- `store.Store.stop_attempt_fenced`
- `store.Store.append_receipt_idempotent`
- `store.Store.consume_preflight`
- `supervisor.Supervisor.prepare_run`

The inventory also lists existing but unregistered candidate tests for other names; a candidate in another category is not counted as API-category evidence because the registry requires a unique primary category per ID.

## Verification state and scope decision

No product code changed. AC-7's applicable stale-evidence and forged-signature cases were added to the API selectors and passed in focused run evidence 0174. The unchanged API+seeded denominator will be rerun after this inventory/coverage-reason commit to validate the committed registry and exact category selectors. The 79-name inventory is deliberately not used to add dozens of unreviewed selectors: the explicit S4 plan acceptance is module-level documented Python API coverage and does not expressly require every non-underscore implementation callable to be a separately supported stable contract. The missing selector mapping is recorded as the concrete remaining acceptance gap rather than silently claiming full API completeness.

Network API remains explicitly `UNSUPPORTED`. Full aggregate regression and report-bound signer/receipt/gate remain separate S4 work and are not covered by this local API run.
