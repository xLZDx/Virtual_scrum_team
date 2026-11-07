# Change 0534: implement S2 M03 cross-generation outcome recovery

## Why

After a crash leaves an accepted dispatch result pending, a new Runner generation can make normal
same-generation idempotency unable to return the original result. The pending barrier then blocks
new owner submissions. GPT-PM adjudicated request
`f67c5dd7-5279-42b1-9dc4-94ed4b72b5a1` as MODIFY: exact historical replay is within accepted M03
scope, provided it is a separate authenticated read-only path and never becomes new admission.

## What changed

- `tools/vst/store.py`: added a consistent-snapshot read-only lookup that verifies the full event
  chain and anchor plus accepted event, operation result, and ordered pending/ack protocol. It
  returns a result only for an exact authenticated-principal and complete-envelope match, preserves
  the original event sequence and service generation, and refuses legacy-unresolved history.
- `tools/vst/supervisor.py` and `tools/vst/supervisor_service.py`: added
  `replay_dispatch_outcome`, restricted to the authenticated `dispatch_owner` role. It has no
  current-generation, lease, preflight, grant, or Runner side effects. The role operation allowlist
  includes only submit, historical replay, and acknowledgement.
- `tools/vst/dispatch_owner_client.py`: current-valid requests continue through normal admission.
  After an ambiguous admission response, the client reads verified history without repeating
  admission. When current signature/expiry/key verification fails, it may only use historical
  lookup; a miss is refused. Exact response principal and envelope bindings are validated before
  local forwarding/ACK.
- Updated the S2 schema and owner-service contract, recorded GPT-PM's adjudication, and reconciled
  project state.

## Decision and boundaries

GPT-PM reply `5cd963a6-2a9a-4ae7-96c6-f3955df216ea` requires current key expiry/revocation not to
erase a previously accepted fact, while current authorization remains mandatory for new admission.
An absent or mismatched result never falls through to admission. Legacy, incomplete, corrupt, or
contradictory Store history remains closed. A compromise incident that casts doubt on a historical
acceptance requires separate security reconciliation; replay does not make a new trust decision.
The Store outcome barrier remains separate from Runner claim/reservation recovery.

## Verification state

- Baseline repository HEAD before these source/docs edits: `1bd00cbacac099f34717e9c68fc720a467f6d519`.
- Mapped focused functional tests at exact follow-up HEAD
  `c855ca4f2888d7288b006973950e4c6d28023b63`: **130 passed, 0 failed**; exact commands, hashes,
  and limits are in `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-test-run-20261029.md`.
  Fresh code, security, reliability and database reviews found no valid BLOCKER/MAJOR. GPT-PM
  request `d16dbf96-54f8-4c96-8fa7-2b24445f85d9` returned ACCEPT — SOURCE/TEST SCOPE and closed
  `S2-PROV-M03-R01`; see
  `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- No production identity, root configuration, key, service, runtime/E5, real dispatch, prohibited
  selector, push, PR, or merge was performed by this change.
- `S2-PROV-M03-R01` is closed for source/test scope. Overall S2 remains NOT APPROVED;
  `S2-DISPATCH-M01`, runtime/E5, production configuration, prohibited selectors, and the final
  exact-head S2 gate remain open. S3 remains unstarted.
