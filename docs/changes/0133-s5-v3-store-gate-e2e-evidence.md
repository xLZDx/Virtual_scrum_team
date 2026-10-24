# 0133 S5 v3 Store-to-Gate exact-head E2E evidence

## What changed

- Recorded the exact clean-head execution of the three focused S5 Store-to-Gate E2E scenarios.
- Added the three committed test node IDs to the E2E denominator and kept coverage marked `PARTIAL`.
- Preserved both earlier test-authoring failures and their classifications in the evidence trail.
- Regenerated the governance document registry.

## Why

The S5 acceptance map calls for evidence that exact-head signed receipts survive persistence and are independently checked by Gate, while stale or failing evidence remains non-approving. The run distinguishes that VST integration proof from absent AEVE/runtime proof.

## Affected contracts and paths

- `tests/vst/test_s5_v3_store_gate_e2e.py`
- `docs/qa/categories.json`
- `docs/sdlc/evidence/s5-v3-store-gate-e2e-7cd83ea.md`
- `core/DECISION_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`
- S5 AC-3/4, AC-7, AC-9/10/11.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- Only local synthetic artifacts were used. No real AEVE identity/runtime, sandbox, signer service, or external repository is claimed.
- E2E category state remains `SUPPORTED` with `PARTIAL` coverage; current S3 nodes remain in its registry alongside the new S5 nodes.

## Verification state

- Exact clean test HEAD: `7cd83eac005e318dca5ae8784b25d2c443cdccc0`.
- Exact command: `$env:PYTHONDONTWRITEBYTECODE='1'; python -m pytest -q -rs -p no:cacheprovider tests/vst/test_s5_v3_store_gate_e2e.py`.
- Environment: Windows PowerShell, Python `3.14.3`, pytest `8.4.2`.
- Result: 3 passed, 0 failed, 0 skipped; one global pytest-asyncio deprecation warning.
- Detailed mapping, prior failed attempts, classifications, and limitations: `docs/sdlc/evidence/s5-v3-store-gate-e2e-7cd83ea.md`.
- Real AEVE execution and sandbox acceptance remain `NOT_RUN`.

## Follow-up

1. Keep actual AEVE/runtime and sandbox acceptance open until an authorized immutable analyzer identity, adapter, and trust provisioning are available.
2. Retain the E2E denominator as partial until remaining S4/S5 acceptance journeys have mapped runtime evidence.
