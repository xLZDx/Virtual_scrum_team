# 0036 S2 control plane, sandbox and lifecycle implementation

## What

Implements the S2 v2 contracts and gate, reviewer identity verification, trusted command parser catalog, runner-derived repository head, isolated signer IPC, signed external event anchor and recovery, deterministic diff gate, sandbox pre-flight, supervisor lifecycle and synthetic hand-written-worker fixture.

## Why

S2 closes trust gaps carried forward from S1 and adds an isolated worker execution boundary while preserving the existing v1 signed data and keeping the S1 gate as the sole acceptance authority.

## Affected contracts and paths

- `tools/vst/contracts.py`, `tools/vst/gate.py`, `tools/vst/signing.py`, `tools/vst/schemas/README.md`
- `tools/vst/runner.py`, `tools/vst/signer.py`, `tools/vst/sandbox.py`, `tools/vst/preflight.py`, `tools/vst/diffgate.py`
- `tools/vst/store.py`, `tools/vst/lifecycle.py`, `tools/vst/supervisor.py`, `tools/vst/slice.py`
- `docs/SANDBOX_SPEC.md`
- `core/LESSONS_LOG.md`, `core/STATE.md`, `docs/sdlc/STATE.md`, `governance/DOCUMENT_REGISTRY.md`

## Decisions

V2 manifests and receipts are explicit; v1 bytes/hashes remain immutable. Reviewer registry trust uses the operator key. Runner, signer, worker and reviewer identities have distinct permissions. Gate evaluation remains pure; authoritative decisions go through the Supervisor/Store wrapper that verifies event chain, external anchor and receipt/event digests on one snapshot. Anchor recovery auto-appends only one verified event. The hand-written worker is the only bake-off candidate; simulated push/PR effects are supervisor-only and idempotent.

## Verification state

Implementation files were produced by three `implementation-engineer` agents using `gpt-6-luna` at medium effort. No tests, builds, lint, CI, runtime probes or migrations were run. Code status is implementation-only; all acceptance claims require test-agent evidence. Two accidental `git diff --check` invocations occurred before coding completed: one by the coordinator and one by the store implementation agent. Both are recorded in `core/LESSONS_LOG.md`; neither is acceptance evidence. Process-kill/kill-table, mutation and CI runs remain prohibited by the continuation instructions and must be `NOT_RUN` if required for acceptance.
