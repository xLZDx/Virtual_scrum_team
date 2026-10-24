# 0085 S2 Windows snapshot functional rerun

## What changed

- Recorded the functional-owned recovery module result against source HEAD `dc95915018b80f498d5cf775363712fb915fe04e`.
- The checkout was E2E evidence commit `e262e11003e16ec392203ed074d1fb490a9aa00e`, whose parent was the exact source revision; its intervening changes did not modify production source or the functional recovery module.

## Acceptance mapping and result

| Test ID | Contract | Result |
| --- | --- | --- |
| `test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart` | A changed but valid signed override cannot replay under the same action ID after restart. | PASS |
| `test_external_operation_intent_and_completion_are_committed_around_callback` | Intent persists before callback; completion is durably recorded afterward. | PASS |
| `test_external_operation_timeout_stays_pending_and_same_key_payload_recovers` | Timeout leaves the operation pending; identical key and payload recover it. | PASS |
| `test_completed_legacy_idempotent_operation_remains_replayable` | Existing completed legacy operation results remain replayable. | PASS |

## Verification

- Exact source HEAD: `dc95915018b80f498d5cf775363712fb915fe04e`.
- Test checkout HEAD: `e262e11003e16ec392203ed074d1fb490a9aa00e` (parent: exact source HEAD). The only intervening files were decision/lesson logs, registry, change/evidence docs, and the E2E-owned runner test file.
- Exact command: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_operation_recovery.py`.
- Environment: Python 3.14.3, pytest 8.4.2, Windows NT 10.0.26300.0, PowerShell 7.6.7.
- Result: exit 0; 4 passed, 0 skipped, 1 pytest-asyncio deprecation warning in 1.60 seconds.
- E2E authoring and runs were complete before this functional-only run. The four named tests above are the complete scope of this command; no other tests or checks were run.

## Ownership and limits

- Accountable task owner: operator by delegated S2 assignment.
- Executor and test author: functional-test-reviewer (GPT-6 Luna, medium effort).
- This evidence covers Store recovery/idempotency and signed override replay only. The E2E source snapshot and bounded import acceptance is recorded separately in change 0083. This functional rerun does not independently claim that E2E coverage.
