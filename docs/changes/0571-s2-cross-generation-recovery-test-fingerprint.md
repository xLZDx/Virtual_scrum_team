# Change 0571: supply the trusted key fingerprint in the S2-1 recovery test fixture

## Why

The current `Store.accept_dispatch_intent` legacy path requires a trusted public-key fingerprint. The S2-1 reopen regression test called Store directly and omitted that value, so the test stopped at the authorization guard before exercising its intended duplicate-outcome barrier.

## What changed

- `tests/vst/test_s2_store_backed_pubsub.py` imports the existing `public_key_fingerprint` helper.
- The three direct Store calls in `test_pending_dispatch_barrier_survives_store_reopen` pass the fingerprint of the test's synthetic public key.
- No production code changed. All duplicate, lifecycle, pending barrier, and replay assertions remain unchanged.
- S2-1 status and evidence references were reconciled in `docs/sdlc/backlog.md` and `core/BACKLOG.md`.
- `docs/sdlc/test-plan.md` and `docs/sdlc/verify-evidence.md` record the focused rerun and its source/runtime boundary.
- Independent read-only `code-reviewer` review found no material issue; it confirmed that the synthetic key fingerprint matches the production Supervisor call path and that the assertions were preserved.

## Verification

`e2e-runner` executed the four focused S2-1 files in Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4, on code HEAD `56cd816b1b03b39c3f4b4a70ecf00d96ef95d321` with the exact test worktree hashes recorded in `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-rerun-56cd816-worktree-20261029.md`: **130 passed, 0 failed**, exit 0. The run record is worktree-bound and requires matching the committed Git blob to the recorded file hash before claiming commit-bound proof. Restricted selectors were not run.

## Closure boundary

The task closes at source/test scope only after the corrected test blob is verified at the task commit and that task commit is normally pushed. No claim is made here about installed runtime behavior, production configuration, E5, restricted selectors, or overall S2 acceptance.
