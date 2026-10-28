# Change 0512 — Add focused S2 pub/sub functional acceptance

## Why

The Store-backed pub/sub coordinator needed requirement-mapped functional evidence for durable
intent admission, idempotency, replay fencing, owner/lease revalidation, grant derivation, and
receipt binding. Repository rules assign test design and execution to functional-test-reviewer;
production E2E remains separately owned and requires provisioned runtime evidence.

## What changed

- Added `tests/vst/test_s2_store_backed_pubsub.py`, a focused acceptance suite covering the local
  Store/Supervisor/RPC/dispatcher-response contracts without provisioning host services.
- Added and reconciled
  `docs/sdlc/evidence/s2-pubsub-functional-run-ec9aefe-20261028.md`, including every run attempt,
  exact source/test hashes, contract-to-test mapping, initial collection error, intermediate
  test-harness errors, and final result.
- Updated `core/STATE.md` and `core/BACKLOG.md` to separate the passing local functional result from
  unrun production E2E/runtime acceptance.

## Verification

- Test owner: functional-test-reviewer, GPT-6 Luna, medium effort.
- Exact source HEAD: `61bfe643e52362fbe4c680ade2c3cb150997dedc`.
- Exact command: `python -m pytest -q tests/vst/test_s2_store_backed_pubsub.py`.
- Final result: **20 passed, 0 failed, 0 skipped, 1 warning, exit 0**. The warning is pytest-asyncio
  deprecation of `asyncio.get_event_loop_policy` from the installed plugin.
- Test-file SHA-256:
  `78EC9DB801D31E98B4918D70CD3735C714DAFEA3A6B8FCFE5FD3B50016ECC867`.
- Evidence-file SHA-256:
  `4A897328BBDD1F8063B49BC1F09F560F0A0F39E0EC199B3895CF6FD266D210B1`.
- This local suite does not prove Linux `SO_PEERCRED`/`SO_PEERPIDFD`, cgroup enforcement, root
  configuration, service activation, current E5, or real task dispatch. The E2E role separately
  recorded those scenarios `NOT_RUN` in
  `docs/sdlc/evidence/s2-pubsub-e2e-triage-ec9aefe-20261028.md`.
- No schema migration, WSL/config/key change, service operation, real dispatch, push/PR/merge, or
  deployment occurred.

## Acceptance and remaining gates

The bounded local source-functional acceptance passes. `S2-DISPATCH-M01` remains MAJOR/OPEN because
the production owner caller and runtime integration are not established. Root configuration,
credentials, fresh signed E5, and active services remain absent/unproven. The schema-v6 migration
remains unapplied pending independent review and separate authorization. Prohibited
crash/process-kill/mutation/policy scenarios remain `NOT_RUN`. Do not start S3 until S2 closes.
