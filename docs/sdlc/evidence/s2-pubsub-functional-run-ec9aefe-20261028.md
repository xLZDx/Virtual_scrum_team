# S2 Store-Backed Pub/Sub Focused Functional Evidence

## Revision and scope

- Source revision under test: `ec9aefe9444003a65af81f27eaf813b250e25c10` (`git rev-parse HEAD`).
- Focused test file: `tests/vst/test_s2_store_backed_pubsub.py`.
- Test-file SHA-256 at the failed collection attempt: `45125F8C0ABAF700F1846B0E85CC9B5AFAB84802F34EE419F54F3B1973D39CA5`.
- Current focused-test-file SHA-256 after adding a separate released-lease regression case: `CE52618D22D7CF4F26037B69C618C824C03E65CCADEFC78C5AE8E2BAA1C02F87`. This exact current file has not yet been executed; rerun after the implementation fix is committed.
- Scope: local Store/Supervisor contracts for owner intent admission, durable idempotency, subscription revalidation and cursor binding, failure propagation, grant derivation/cache binding, RPC peer authorization, and receipt-to-grant binding.
- No production source was edited by the test owner. The existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` was preserved and not overwritten.

## Execution

Exact command:

```text
python -m pytest -q tests/vst/test_s2_store_backed_pubsub.py
```

Result: **NOT RUN (collection failed before any test case executed)**. Pytest exited with status 1 while importing `tools.vst.runner_service`; its import of `tools.vst.supervisor_service` raised:

```text
SyntaxError: '(' was never closed
tools/vst/supervisor_service.py:714
```

The same malformed multiline condition is present in the exact committed source (`git show HEAD:tools/vst/supervisor_service.py`, around lines 714–724): the opening `if (` is not closed before the colon following the `dispatch_owner` principal check. This is a source defect and was not changed by this test work. The parent implementation owner must correct the committed source, freeze the corrected revision, and request this focused test run again. No test result is represented as PASS.

## Contract-to-test map

| S2 contract / gate | Focused test(s) | Observable acceptance assertion | Result |
|---|---|---|---|
| Owner intent is accepted only for valid principal/slot/request ID and is durably event-bound | `test_owner_intent_is_atomically_bound_and_idempotently_replayed`; `test_invalid_owner_slot_or_request_id_cannot_publish_an_intent` | Returned fields bind principal, task, slot, attempt, epoch, run, generation, lease, manifest and payload; one signed-chain event exists; invalid requests create no acceptance event | NOT_RUN: collection error |
| Request ID replay is idempotent only for the identical payload | `test_owner_intent_is_atomically_bound_and_idempotently_replayed`; `test_reusing_request_id_with_changed_payload_is_refused` | Identical request returns same record with one event; changed payload raises duplicate and does not append a second event | NOT_RUN: collection error |
| Subscription revalidates active generation and current owner/lease authority | `test_supervisor_subscription_revalidates_generation_and_live_owner_lease` | Existing intent is delivered before authority change; generation and owner/epoch change prevent stale delivery | NOT_RUN: collection error |
| Subscription must stop delivering after explicit lease revocation | `test_supervisor_subscription_does_not_deliver_after_live_lease_is_released` | Releasing the live lease after intent acceptance causes the next subscription poll to omit the stale intent | NOT_RUN: added after the failed collection attempt |
| Replay cursor is authenticated and bound to generation and subscriber audience | `test_dispatch_cursor_is_bound_to_mac_generation_and_subscriber` | MAC tamper, audience change, and service-generation change are rejected; valid cursor resumes at its authenticated sequence | NOT_RUN: collection error |
| Transient and integrity errors do not produce a successful cursor advancement | `test_subscription_propagates_systemic_store_errors_without_advancing_replay[busy]`; `[integrity]` | Busy/integrity errors propagate; no idle/advanced cursor is returned and the intent remains readable from the original replay position | NOT_RUN: collection error |
| Dispatcher grant is derived from accepted intent and replay returns one cached grant | `test_grant_forwarding_uses_exact_intent_and_replays_one_cached_grant` | Exactly one grant call receives fields derived from the stored intent/current manifest and replay returns the same result | NOT_RUN: collection error |
| RPC principal comes from authenticated owner peer; dispatch role cannot submit | `test_supervisor_rpc_derives_principal_from_peer_and_limits_operations` | Accepted principal equals peer principal; body-supplied principal and dispatcher submission are rejected | NOT_RUN: collection error |
| Runner receipt must match every grant binding | `test_dispatch_response_receipt_must_match_exact_grant[task_id]`, `[manifest_sha256]`, `[slot]`, `[attempt]`, `[epoch]`, `[runner_id]`, `[invocation_id]`; `test_dispatch_response_returns_valid_receipt_when_grant_bindings_match` | Every mismatched binding is refused; exact matching receipt is returned | NOT_RUN: collection error |

## Deliberately excluded runtime scenarios

Real POSIX peer credential/cgroup enforcement, root-owned production configuration and service-generation provenance, production service activation, real task dispatch, and prohibited crash/process-kill/mutation/policy scenarios were not exercised by this focused local test attempt. They remain outside this run; see the separate in-scope E2E triage record for its recorded runtime dependencies. This report does not claim those scenarios passed.

## Next action

Codex implementation owner: add the missing closing parenthesis in the Supervisor peer-policy validation, commit/freeze the corrected source revision, then rerun only the exact focused command above against current test-file SHA-256 `CE52618D22D7CF4F26037B69C618C824C03E65CCADEFC78C5AE8E2BAA1C02F87` and update this report with its result. If further test failures identify product defects, report them to the implementation owner without changing production source in this role.
