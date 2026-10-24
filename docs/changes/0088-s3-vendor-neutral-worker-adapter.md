# 0088 S3 vendor-neutral worker adapter

## What changed

- Added a bounded typed `WorkerRequest` / `WorkerResponse` contract with `start`, `status`, `stop`, and `resume` operations, candidate and manifest identity, attempt/epoch fencing, budget context, allowed paths, invocation identity, sandbox run binding, bounded progress, evidence references, errors, and named application checkpoints.
- Added an in-repository `HandWrittenWorkerAdapter` and `SyntheticStoryPilot`. The pilot uses only the synthetic worker fixture, durable Store operation records, Store leases/epochs/budget, and the Supervisor gate. Worker output never creates test, review, or acceptance receipts.
- Added exact-payload idempotent epoch acquisition/resume, budget charge, operation lookup, and atomic STOP fencing to `Store`. STOP invalidates the old Store epoch and returns `INCONCLUSIVE`; it does not claim operating-system process cleanup.
- Added optional bounded subprocess timeouts to `HandWrittenWorker.edit` and `commit_candidate`, preserving existing default behavior and leaving `crash_mid_edit` unchanged.
- Bound the handwritten adapter to an explicitly supplied trusted candidate ID and immutable revision. The pilot verifies a fresh signed sandbox probe and network-policy attestation before a resume mutates the Store epoch; the Supervisor still performs one-time probe consumption.

## Why

S3 requires one vendor-neutral story contract that cannot become a second acceptance authority. The initial adapter draft exposed only `run()` and did not meet the accepted four-operation contract or durable budget/fencing requirements. Source review against S3 AC-1..4 and the locally implementable parts of AC-9..12 led to the current Store-owned operation keys, stale-snapshot rejection, pre-mutation probe verification, and trusted candidate binding.

## Affected contracts and paths

- `tools/vst/worker_adapter.py`: typed vendor-neutral request, response, state, error, checkpoint, and adapter protocol.
- `tools/vst/pilot.py`: hand-written adapter and single-story orchestration using Store/Supervisor authority.
- `tools/vst/store.py`: idempotent budget, operation status, epoch acquire/resume, and STOP fence APIs.
- `tools/vst/slice.py`: optional timeout forwarding for synthetic worker edit/commit calls.
- `core/BACKLOG.md` and `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`: local code state and remaining S3 gates.

## Decisions and ownership

- Accountable task owner: operator under delegated S2-S5 continuation. Executor: Codex; code agent: `implementation-engineer` (GPT-6 Luna, medium effort).
- S2 Store/Supervisor remain the only lease, attempt, receipt, and verdict authorities. No candidate adapter can self-approve.
- The in-repository hand-written candidate is the only implemented adapter. BMad Loop and Temporal remain unacquired and unexecuted pending complete read-only audit and explicit operator acquisition authorization.
- Resume is accepted only for a returned, durable application-level checkpoint and a released prior lease. A timeout, pending external operation, or unknown process state remains non-resumable and `INCONCLUSIVE`.
- STOP fences the old epoch atomically but does not terminate an operating-system process. Process-kill/kill-table and cleanup-after-timeout scenarios remain prohibited or unverified.
- `StopRequest.authorized_actor` is an audit identity string, not proof of authentication. The caller must be authenticated by a trusted service boundary before invoking STOP; no such external service/API boundary is implemented in this repository slice.
- S2 Phase 8 exact-head GPT-PM approval remains pending. Additional `pm_bridge_mode_status` and `pm_bridge_health` calls returned the exact error `Transport closed`; this is not approval and no push/PR is authorized.

## Verification state

- Manual source review was performed by the coordinator after implementation. Findings corrected before handoff include budget snapshot validation before spend, probe verification before resume epoch mutation, trusted candidate identity/revision binding, durable attempt binding before STOP, bounded path data, and resume binding before epoch mutation. This is code inspection, not runtime evidence.
- No tests, checks, builds, CI, migrations, WSL worker run, or candidate execution were performed for this code change. Required functional/E2E test-agent runs remain pending on the exact committed head.
- STOP caller authentication, process cleanup after STOP, subprocess-timeout cleanup, Windows containment, prohibited process-kill/kill-table behavior, external candidate comparisons, and the full S3 scenario denominator remain `NOT_RUN` or `NOT_VERIFIED`.
