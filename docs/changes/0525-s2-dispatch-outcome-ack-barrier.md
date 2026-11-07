# Change 0525: make S2 dispatch outcome acknowledgement Store-authoritative

## Why

GPT-PM accepted the revised M03 architecture for implementation. The existing root systemd latch
was written after the service stopped, leaving a crash window before durable latch creation. This
change closes new-request admission in the Store transaction that accepts an intent, then permits
admission to resume only after an authenticated relay-forwarding acknowledgement is durably
recorded. It introduces no scheduler, assignment authority, table migration, or runtime operation.

## What changed

- `tools/vst/store.py` sets `PRAGMA synchronous=FULL`, reads the setting back, commits the pending
  outcome control note with the accepted event and idempotency result, reconstructs the complete
  ordered dispatch event/operation/pending/ack history at startup and before admission or ack, and
  keeps legacy accepted events unresolved. It exposes an idempotent, tuple-bound acknowledgement.
- `tools/vst/supervisor.py` delegates acknowledgement to Store.
- `tools/vst/supervisor_service.py` exposes `ack_dispatch_intent` only for the authenticated
  `dispatch_owner` role and includes it in that role's exact operation allowlist.
- `tools/vst/dispatch_owner_client.py` binds acknowledgement to the canonical Supervisor result.
- `tools/vst/dispatch_owner_service.py` acknowledges only after local response `sendall()` succeeds;
  forwarding or acknowledgement failure keeps admission pending and stops the relay. The ack means
  relay-forwarded, not caller-received.
- Updated the S2 design note, dispatch-owner service contract, and VST schema documentation to
  match the implementation and preserve the boundary between source behavior and unverified runtime.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- GPT-PM design acceptance: request `b992acde-35f0-4f18-91a2-0522c3d4e5f6`, reply
  `8109099c-53f6-45db-be51-13a0d1e36acf`; this is design authorization, not implementation approval.
- No tests or runtime dispatch have been run against this change. The earlier 107/107 result at
  `34bd7dc1b085789341b29937655af52e07f2ddbd` verifies the latch-only version and is not evidence
  for this Store barrier.
- Required next evidence: focused functional tests authored by `functional-test-reviewer`, executed
  by `e2e-runner` after the test source is frozen, fresh code/reliability/security reviews, and
  GPT-PM exact-head adjudication. M03 remains OPEN until those gates close.
- No `/etc`, systemd, account/group, key, production configuration, E5, runtime, or real dispatch
  state was changed or exercised. S2 remains NOT APPROVED; S3 remains unstarted.
- The pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` is protected and was
  not read, modified, staged, or removed.
