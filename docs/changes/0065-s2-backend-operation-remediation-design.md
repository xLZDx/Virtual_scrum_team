# 0065 S2 bounded idempotent operation remediation design

## Goal

Address reliability review findings for S2 S7.2 and S7.3 before changing code: backend calls must not hold SQLite transactions or the shared event-anchor lock while executing, and retries of a manual breaker override must preserve the original signed payload.

## Current behavior and constraint

- `Store.execute_idempotent` currently invokes the effect callback inside `_tx`; push and pull-request callbacks run local Git subprocesses from `Supervisor._simulate`.
- The existing `supervisor_operations` table already has an append-only record with operation key, payload digest and JSON result. Schema migration is prohibited; use the existing row and represent an unfinished outcome as a typed JSON result.
- The synthetic Git backend persists operation-key/payload binding in a bare-repository ref, so retrying the same operation key after an interrupted callback is safe and a conflicting payload is rejected.
- A completed manual override action currently returns its earlier action event without comparing the retry's embedded signed record.

## Options considered

1. Keep callbacks inside the Store transaction and add a timeout. This still holds the global database and anchor locks throughout the timeout and leaves the action record uncommitted while the side effect runs.
2. Commit a durable pending intent first, run the backend outside the Store transaction with bounded subprocess operations, then commit the result. On timeout/crash, retain `PENDING`; retry only with the same key/payload, relying on the backend's own idempotency binding. **Chosen:** it releases Store locks during backend execution, makes the uncertain state durable and uses the existing schema.

## Design

- Add an external-operation path separate from the existing transaction-callback helper used by internal receipt insertion.
- In a short transaction, validate the key/payload digest and either return a committed result, create a `PENDING` result plus intent event, or reject conflicting reuse. Then leave the transaction before invoking the external callback.
- Bound each local Git subprocess with the configured operation timeout. If the callback raises or times out, leave the row pending and surface the failure. A retry with identical key/payload re-invokes the backend using its same idempotency key; the Git ref binding prevents duplicate or conflicting effects. On success, use a second short transaction to write the canonical result and completion event. Never map `PENDING` to success.
- For a completed `manual_override` action ID, compare canonical bytes of the requested override record with the record embedded in the prior durable action. Reject any mismatch before returning the old completion. Continue validating the signed record against the current breaker episode.
- Keep V1/V2 receipt bytes, event anchors, gate contracts, and schema version unchanged; no migration, external backend acquisition, network calls, or real remote is introduced.

## Failure modes and rollout

- A process exit or timeout before effect completion leaves `PENDING`; no approval/success is emitted. Same-key retry is allowed and backend-idempotent. Changed key payload is rejected. A persisted completed result is returned without a second callback.
- A failure after backend effect but before Store completion remains `PENDING`; retry recovers the backend's original result from its idempotency ref and then stores it.
- Keep current S2 implementation behind the existing API; record `operation_timeout_sec` in the synthetic backend with a conservative finite default. No destructive rollback is needed; a code revert is the rollback path before promotion.

## Verification plan and owners

- `functional-test-reviewer` and `e2e-runner` own regression cases for pending/complete/retry/conflicting payload, callback outside Store transaction, bounded Git subprocess timeout, crash window, and changed manual-override payload under an already completed action ID.
- They execute only after implementation is complete. No tests/checks/builds/CI/migrations are run during design or coding.
- Reliability reviewer finding owner: S2 executor (Codex) under operator accountability. Exact-head post-fix review remains required before final S2 approval.

## Unknowns

- Runtime timeout behavior on supported Git/platform combinations remains to be established by the designated E2E run.
- If a future non-Git backend lacks durable idempotency under the operation key, it cannot use this external-operation path without its own recovery contract.
