# 0178 — Correct idempotent epoch test precondition

## What changed

Updated `test_api_acquire_epoch_idempotent_replay_keeps_one_new_epoch` to release the fixture's live `owner-a` epoch before asking `acquire_epoch_idempotent` to transfer ownership to `owner-b`. The test now calls the public `Store.release_epoch` API to establish the valid precondition.

## Why

The first complete-denominator run on `3df219e4b4cd1700e80b282c0d08fba8205006f5` produced 92 passed, 1 skipped, and 1 failed. The failure was the new test attempting an epoch transfer while the helper intentionally retained a live owner. `Store.acquire_epoch_idempotent` correctly rejected the live-owner conflict. This was a fixture setup defect, not a product defect.

## Verification state

The corrected test source is committed separately. The canonical category provenance must be advanced to the corrected test commit, then the full API+seeded selector set must be rerun on the exact resulting manifest HEAD. The previous failing result remains recorded as superseded test evidence.

## Scope

No product source or assertions were weakened. The test still proves one idempotency key advances one released story epoch exactly once.
