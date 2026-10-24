# 0087 S3 adapter code preparation

## What changed

- Registered S3 stories VST-027 through VST-031 in `core/BACKLOG.md`, consistently with the plan's ID map and with accountable operator ownership separate from Codex execution and technical ownership.
- Updated the S3 plan to record local contract-code preparation on `s3-vendor-neutral-worker-pilot`, the reconciled S2 source baseline, and the pending S2 Phase 8 gate.
- Split readiness requirements for local adapter code, in-repository synthetic integration, candidate acquisition/comparison, and sandbox-bound execution.
- Kept S3 worker execution, candidate acquisition, external clone/install, fresh sandbox run, and S3 tests out of this preparation step.

## Why

The S2 exact-source functional/E2E evidence and three independent reviews are reconciled, so the vendor-neutral in-repository adapter can be implemented as independent local code. The operator asked to continue autonomously with an 80% code / 20% documentation-and-test effort balance. S2's Phase 8 publication gate remains pending because PM Bridge calls returned `Transport closed`; this record therefore keeps S2 as the phase authority while S3 work stays local and unpromoted.

## Affected contracts and paths

- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`: S3 execution status, entry dependency, and ordered next steps.
- `core/BACKLOG.md`: S3 adapter/in-repository integration, candidate audit, deterministic fixture, sandbox proof, and comparison items VST-027..031.
- S3 code will use the existing S2 Store/Supervisor/gate as the sole lease, receipt, and verdict authority. External backend state cannot approve its own work.

## Decisions and ownership

- Accountable owner: operator by delegated S3 task.
- Executor: Codex; implementation agent role is reserved for the code slice.
- S2 Phase 8 remains pending exact-head GPT-PM review. PM Bridge tool calls for delegation matrix, project gate, and health returned `Transport closed`; no manual or alternate approval is claimed.
- Candidate acquisition authorization and final worker choice remain operator-owned. No external source was acquired, cloned, installed, or executed.
- Technical owner for the S3 worker service is not identified in the inspected project sources.

## Verification state

- S2 source baseline is `dc95915018b80f498d5cf775363712fb915fe04e`; S3 branch was created from the S2 documentation commit `3505f769f9c1c245d368a8318aeb04a76e1c5537`.
- Documentation was reviewed by a read-only `code-architect` agent (GPT-6 Luna, low effort). It identified a backlog-ID collision and an over-broad readiness gate; this record and plan now reconcile both findings.
- Process error: `git diff --check` was inadvertently run before S3 code completion. It emitted no diagnostics and returned exit code 0; this is not verification evidence. The rule breach and corrective rule are recorded in `core/LESSONS_LOG.md` and `core/DECISION_LOG.md`.
- Other than that explicitly recorded command, no tests, checks, builds, CI, migrations, or runtime worker scenarios were run during this documentation pass.
