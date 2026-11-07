# Change record 0205: Reconcile S2 state to explicit-nonce evidence

## What changed

- Updated `core/STATE.md` and `docs/sdlc/STATE.md` with the current implementation source HEAD, focused test HEAD, and repository HEAD before the reconciliation.
- Preserved earlier Phase 7 evidence at its original source HEAD rather than attributing it to the nonce change.
- Recorded the exact focused result and kept remaining platform and Phase 8 GPT-PM gates open.
- Updated the decision log, lesson log, and generated document registry.

## Why

The state summaries still listed an earlier S2 implementation and repository head after the explicit-nonce implementation and its focused functional run had been recorded in the backlog and bilingual status report. State must separate implementation identity from the checkout on which a test ran.

## Evidence and limits

- Current S2 repository head before this documentation change: `7acb30d8a87e17b972a66a9e528f6b450ba8777a`.
- Nonce implementation source head: `6ee97cb06b52900c3c2ab2a9b1b415ae117a7932`.
- Designated functional test evidence: 4 passed / 22 deselected / 0 failed at test head `deed6abe34eeaa8620593442bcdb1413d846f798`; Python 3.14.3 and pytest 8.4.2 are recorded in the S2 report and change 0165 evidence.
- Prior Phase 7 functional/E2E and specialist evidence remains attached to source `dc95915018b80f498d5cf775363712fb915fe04e` and is not evidence for the later source.
- One signed WSL2 E5 inventory/attestation was accepted for run `280e2d0`; this is not persistent deployment proof.
- Prohibited process-kill/kill-table, post-start overflow cleanup, Windows Job Object nesting, full POSIX containment and full E8 crash/resume remain `NOT_RUN`; OS quotas, exact workspace binding and direct-writer exclusion remain `NOT_VERIFIED`.
- No code, test, build, or runtime was changed or run in this reconciliation.

## Ownership and next step

- Accountable task owner: operator for delegated S2 completion.
- Executor: Codex for state and evidence reconciliation.
- GPT-PM owns the exact-head approval gate; current PM Bridge status and health calls returned `Transport closed`.
- Next: resolve S2-specific gate status when PM Bridge is reachable; push/PR remains prohibited until fresh approval for the exact final repository HEAD. Keep restricted runtime criteria explicitly unrun.

## Verification state

Documentation-only reconciliation. Document registry generation is recorded separately by the commit workflow. No tests/checks/build/runtime were performed.
