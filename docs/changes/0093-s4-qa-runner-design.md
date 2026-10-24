# 0093 S4 QA runner contract design

## What changed

- Specified the S4 report-to-gate contract using existing v2 `TestRun` receipts and the validated VST task manifest as the canonical category registry.
- Bound the machine-readable QA report as a receipt artifact; kept the authoritative gate, exact-head check, signature check, test-ID denominator, and artifact resolver in the existing VST boundary.
- Preserved v1/v2 signed-body compatibility and S5's planned v3 scope.

## Why

The S4 plan required stale/hash-invalid QA evidence to fail closed but did not identify the receipt shape or registry authority. The S4 architecture review identified this as the material implementation gap.

## Affected contracts and paths

- `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md`
- S4 implementation is expected under `tools/qa/`, with integration limited to existing `tools/vst/runner.py`, `contracts.py`, and `gate.py` as needed.
- Source references: `tools/vst/contracts.py` v2 `TestRun` and manifest validators; `tools/vst/runner.py::run_and_sign`; `tools/vst/gate.py::evaluate`; `docs/S5_AEVE_GATE_PLAN_2026-10-24.md` v3 compatibility rules.

## Decisions and ownership

- Accountable task owner: operator under delegated S2-S5 continuation. Executor: Codex; production-code executor: `implementation-engineer` (GPT-6 Luna, medium).
- Canonical technical owner for the runner and QA dependency lock is not established in repository ownership records; keep `UNKNOWN`.
- No new signed fields are added to v1/v2, and S4 does not repurpose the S5 v3 extension.

## Verification state

- Read-only architecture review: `code-architect` (GPT-6 Luna, medium) recommended existing v2 `TestRun` receipts and manifest-derived categories.
- Current environment inspection with `C:\Python314\python.exe` reported Python 3.14.3, pytest 8.4.2, and pytest-asyncio 0.26.0. This is inventory evidence only; dependency hashes and reproducible installation are not yet established.
- No tests, checks, builds, CI, dependency installation, or migration were performed for this design.
