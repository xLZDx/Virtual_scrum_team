# Change 0532: test S2 cross-request barrier ordering

## Why

The MAJOR finding in change 0531 was a corrupted-but-hash-valid history where request B is
accepted before request A is acknowledged, even though each request's individual pending/ack
records are ordered correctly. The Store must reject the full history at startup.

## What changed

- Added `test_dispatch_outcome_history_rejects_cross_request_ack_ordering` in
  `tests/vst/test_s2_store_backed_pubsub.py`. It creates A/PENDING, uses narrow fixture-only
  monkeypatches to construct B/PENDING before A/ACK, confirms the event chain remains valid, then
  reopens Store and verifies integrity lock and refused admission.
- Test authored by `functional-test-reviewer` (GPT-6 Luna, medium effort) against source HEAD
  `0889b60`; no tests or checks were executed by the author.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- New regression remains `NOT_RUN`; `e2e-runner` owns the next exact-head focused execution.
- The prior 118/118 run at HEAD `80b01c55c700d029e357297f1af920e3b3033683` predates the ordering
  fix and does not verify it.
- A separate MAJOR recovery gap remains: a pending request cannot be replayed after the active
  Runner service generation changes, and a dispatch-outcome reconciliation endpoint is not yet
  established. GPT-PM owns architecture adjudication; Codex owns preparing the narrow proposal.
