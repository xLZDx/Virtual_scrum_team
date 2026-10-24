# 0054 S2 signed provider breaker override

## What changed

- `tools/vst/signing.py`: added the distinct operator manual-override HMAC domain label `vst-operator-manual-override-v1`.
- `tools/vst/supervisor.py` and `tools/vst/store.py`: `manual_override` requires and verifies the configured trusted operator key. The signature binds `action=manual_override`, `breaker_state=PAUSED_PROVIDER`, stable record ID, current pause-episode ID (threshold-crossing failure event), breaker-config event ID, non-APPROVE verdict, and lowercase evidence SHA-256. Store verifies the signature and current episode atomically at action admission before the callback, then rechecks the episode atomically before appending the breaker-clearing event. A duplicate old override cannot clear a later pause episode.
- S2 E7.3 contract, decision/lesson logs and registry were updated.

## Why

Security review of HEAD `19fb0088e2d4b237de6f0c7beb7aab2c648b66aa` found that manual override validated record shape and verdict but did not authenticate the operator decision. Follow-up review identified that a signed `PAUSED_PROVIDER` assertion without a unique episode binding could be replayed after a later breaker trip. An untrusted caller could therefore submit a fabricated record, or reuse stale authority.

## Verification state

No tests, checks, builds, CI, migrations or runtime probes were run. The E2E test owner will add unsigned, tampered, replayed-after-new-episode and valid signed-record cases after this commit. No operator private key was accessed or provided.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Runtime/test owner: designated E2E agent.
- Next: run the signed override regression cases on the exact resulting head.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
