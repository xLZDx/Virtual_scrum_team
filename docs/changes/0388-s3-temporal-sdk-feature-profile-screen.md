# Change 0388: S3 pinned SDK feature-profile screen

## What changed

- Recorded source-declared Python and Rust feature/profile facts from the immutable Temporal SDK pin.
- Updated the S3 plan, backlog, and current portfolio state to distinguish this source-level narrowing from a selected runtime dependency closure.

## Why

S3-G02/G03 still lacked a bounded description of the SDK bridge's default feature choices. The official pinned manifests expose useful metadata without acquiring or executing the candidate.

## Affected paths

- `docs/sdlc/evidence/s3-temporal-sdk-feature-profile-screen-20261027.md`
- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`
- `core/BACKLOG.md`
- `core/STATE.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Read official pinned source files: `pyproject.toml`, `temporalio/bridge/Cargo.toml`, `uv.lock`, and `temporalio/bridge/Cargo.lock` at SDK commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.
- No candidate source/artifact was acquired into the repository; no package was installed, built, or executed.
- No tests or checks were run. S3 acquisition and execution remain NOT APPROVED.

## Decision

Treat source feature declarations as profile-planning evidence only. Resolve the selected runtime closure and provenance after the legal, sandbox, and acquisition gates permit that work.
