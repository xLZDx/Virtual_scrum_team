# 0052 S2 coordinator lock teardown hardening

## What changed

- `tools/vst/lifecycle.py`: coordinator teardown now attempts OS unlock, then stream close, then always releases the per-path mutex through nested `finally` blocks. Unlock/close `OSError` becomes `AnchorError` when the protected operation itself succeeded; an exception from the protected operation remains primary.
- Decision/lesson logs and document registry were updated.

## Why

Two independent reliability reviews of `8eed294` found that linear teardown could skip stream close and mutex release if unlock or close raised, leaving local callers blocked indefinitely.

## Verification state

No tests, checks, builds, CI, migrations or runtime probes were run. E2E should verify coordinator recovery after injected teardown failures and rerun anchor scenarios on this exact head.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Runtime/test owner: designated E2E agent.
- Next: rerun focused anchor scenarios after this source head is available.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
