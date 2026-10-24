# 0049 S2 supervisor admission and anchor lock fixes

## What changed

- `tools/vst/store.py`: added atomic admission for `manual_override`; lifecycle admission also derives the durable provider breaker under the same write transaction and refuses `start` while paused. A stale provider-success report cannot close a breaker after it has paused. Reconciliation records are accepted only when their exact action/outcome/evidence fields verify under the trusted operator key. Invalid or legacy unsigned resolutions remain unresolved and cannot authorize a retry.
- `tools/vst/supervisor.py`: passes the operator trust key through Store admission and requires a signed resolution record binding action ID, action, attempt, completion status, external resolution ID and evidence SHA-256.
- `tools/vst/lifecycle.py`: Windows external-anchor compare-and-append now seeks to byte zero before releasing the one-byte `msvcrt` lock; append moves the file pointer to EOF, so the prior unlock targeted the wrong region.
- S2 E7 acceptance criteria, decision/lesson logs and document registry were updated.

## Why

E2E execution on code HEAD `43d0a87f73ef94cbe5bc34aed04921bbe31cf716` reported a valid provider override rejected as an unknown lifecycle action, two Windows external-anchor startup races entering integrity lock, and reviewer findings that stale Supervisor state could bypass a newly opened breaker and an unsigned `completed=False` could authorize a non-idempotent retry.

The anchor failure cause was not present in captured output because `Store.__init__` retains only the integrity-locked state. Source inspection identified the Windows byte-range unlock closure: append moved the target stream to EOF before unlock. The fix records the startup reconciliation cause for future diagnostics and corrects the lock offset.

## Verification state

The E2E agent's reported failures are diagnostic evidence only; this implementation task ran no tests, checks, builds, CI, migrations or runtime probes. The two-store start race, stale-breaker admission, override and signed-resolution scenarios require rerun by the E2E test owner on the resulting exact head.

## Ownership and next action

- Accountable task owner: operator. Executor: implementation engineer (`gpt-6-luna`).
- Runtime/test owner: designated E2E agent.
- Next: rerun the focused lifecycle and anchor scenarios, including the two-store Windows races; then request independent reliability review.

Agent-Attribution: implementation-engineer (`gpt-6-luna`); Codex executor
