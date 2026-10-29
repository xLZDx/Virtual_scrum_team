# S2 Store-Backed Pub/Sub Focused Functional Evidence

## Revision and scope

- Initial source revision: `ec9aefe9444003a65af81f27eaf813b250e25c10` (`git rev-parse HEAD`). It contained the syntax error recorded below.
- Corrected source revision used for the passing run: `61bfe643e52362fbe4c680ade2c3cb150997dedc` (`git rev-parse HEAD`).
- Focused test file: `tests/vst/test_s2_store_backed_pubsub.py`.
- Test-file SHA-256 at initial collection failure: `45125F8C0ABAF700F1846B0E85CC9B5AFAB84802F34EE419F54F3B1973D39CA5`.
- Test-file SHA-256 at passing run: `78EC9DB801D31E98B4918D70CD3735C714DAFEA3A6B8FCFE5FD3B50016ECC867`.
- Scope: local Store/Supervisor contracts for owner intent admission, durable idempotency, subscription revalidation and cursor binding, failure propagation, grant derivation/cache binding, RPC peer authorization, and receipt-to-grant binding.
- No production source was edited by the test owner. The existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not overwritten.

## Execution

Exact focused command for every attempt:

```text
python -m pytest -q tests/vst/test_s2_store_backed_pubsub.py
```

Results, chronologically:

1. At initial source revision `ec9aefe9444003a65af81f27eaf813b250e25c10`, collection failed before any test case executed. Pytest exited 1 while importing `tools.vst.runner_service`; its import of `tools.vst.supervisor_service` raised:

```text
SyntaxError: '(' was never closed
tools/vst/supervisor_service.py:714
```

The malformed condition was confirmed in the exact source with `git show HEAD:tools/vst/supervisor_service.py` (around lines 714–724). It was corrected by the implementation owner and committed in `61bfe643e52362fbe4c680ade2c3cb150997dedc`; test work did not modify production source.

2. At corrected source HEAD, an initial focused attempt collected but had `12 passed, 8 failed`: failures were test-harness setup defects (the fake Supervisor lacked required signing configuration, and the Windows host path/socket semantics did not match the mocked POSIX boundary). A second attempt had `19 passed, 1 failed` because the attempt-2 receipt fixture lacked its required previous-receipt digest. A later test-only edit had a collection `IndentationError`; this was corrected without production changes.

3. Final focused run at source HEAD `61bfe643e52362fbe4c680ade2c3cb150997dedc` and test-file SHA-256 `78EC9DB801D31E98B4918D70CD3735C714DAFEA3A6B8FCFE5FD3B50016ECC867`: **20 passed, 1 warning, exit status 0**. The sole warning is pytest-asyncio deprecation of `asyncio.get_event_loop_policy` from the installed plugin; no test was skipped.

## Contract-to-test map

| S2 contract / gate | Focused test(s) | Observable acceptance assertion | Result |
|---|---|---|---|
| Owner intent is accepted only for valid principal/slot/request ID and is durably event-bound | `test_owner_intent_is_atomically_bound_and_idempotently_replayed`; `test_invalid_owner_slot_or_request_id_cannot_publish_an_intent` | Returned fields bind principal, task, slot, attempt, epoch, run, generation, lease, manifest and payload; one signed-chain event exists; invalid requests create no acceptance event | PASS (final focused run) |
| Request ID replay is idempotent only for the identical payload | `test_owner_intent_is_atomically_bound_and_idempotently_replayed`; `test_reusing_request_id_with_changed_payload_is_refused` | Identical request returns same record with one event; changed payload raises duplicate and does not append a second event | PASS (final focused run) |
| Subscription revalidates active generation and current owner/lease authority | `test_supervisor_subscription_revalidates_generation_and_live_owner_lease` | Existing intent is delivered before authority change; generation and owner/epoch change prevent stale delivery | PASS (final focused run) |
| Subscription must stop delivering after explicit lease revocation | `test_supervisor_subscription_does_not_deliver_after_live_lease_is_released` | Releasing the live lease after intent acceptance causes the next subscription poll to omit the stale intent | PASS (final focused run) |
| Replay cursor is authenticated and bound to generation and subscriber audience | `test_dispatch_cursor_is_bound_to_mac_generation_and_subscriber` | MAC tamper, audience change, and service-generation change are rejected; valid cursor resumes at its authenticated sequence | PASS (final focused run) |
| Transient and integrity errors do not produce a successful cursor advancement | `test_subscription_propagates_systemic_store_errors_without_advancing_replay[busy]`; `[integrity]` | Busy/integrity errors propagate; no idle/advanced cursor is returned and the intent remains readable from the original replay position | PASS (final focused run) |
| Dispatcher grant is derived from accepted intent and replay returns one cached grant | `test_grant_forwarding_uses_exact_intent_and_replays_one_cached_grant` | Exactly one grant call receives fields derived from the stored intent/current manifest and replay returns the same result | PASS (final focused run) |
| RPC principal comes from authenticated owner peer; dispatch role cannot submit | `test_supervisor_rpc_derives_principal_from_peer_and_limits_operations` | Accepted principal equals peer principal; body-supplied principal and dispatcher submission are rejected | PASS (final focused run) |
| Runner receipt must match every grant binding | `test_dispatch_response_receipt_must_match_exact_grant[task_id]`, `[manifest_sha256]`, `[slot]`, `[attempt]`, `[epoch]`, `[runner_id]`, `[invocation_id]`; `test_dispatch_response_returns_valid_receipt_when_grant_bindings_match` | Every mismatched binding is refused; exact matching receipt is returned | PASS (final focused run) |

## Deliberately excluded runtime scenarios

Real POSIX peer credential/cgroup enforcement, root-owned production configuration and service-generation provenance, production service activation, real task dispatch, and prohibited crash/process-kill/mutation/policy scenarios were not exercised by this focused local test attempt. They remain outside this run; see the separate in-scope E2E triage record for its recorded runtime dependencies. This report does not claim those scenarios passed.

## Next action

Codex test owner: preserve this exact-head result; parent/primary must include the focused test file and evidence in the S2 acceptance review. This run proves local Store/Supervisor and mocked receipt-binding contracts only. Production POSIX peer credentials, service activation and real dispatch remain outside this test and are not claimed as passed. If production source changes after `61bfe643e52362fbe4c680ade2c3cb150997dedc`, rerun the focused suite against the new exact source head.
