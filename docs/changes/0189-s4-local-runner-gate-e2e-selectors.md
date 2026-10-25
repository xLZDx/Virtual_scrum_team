# 0189 — Add deterministic S4 local runner-to-gate E2E selectors

## What changed

- Added five pytest E2E selectors for native collection of the committed E2E ID list and the local signed runner-to-gate artifact path.
- The local journeys cover exact-head approval plus stale-head, missing-artifact, and changed-artifact rejection.
- Reused the repository's existing `tools.vst.runner.run_and_sign`, VST gate, and deterministic `tests.vst.e1e4_helpers` manifest/receipt fixtures. No framework or dependency was added.

## Why

The S4 E2E lane needed committed selectors for native test discovery and the deepest local receipt/artifact/gate boundaries that the existing fixtures can exercise without provisioning OS identities or a signer service.

## Contracts and paths

- `tests/qa/test_s4_report_bound_e2e.py` adds stable node IDs. The discovery selector reads `docs/qa/categories.json` and runs pytest collection only for the mapped E2E IDs.
- Each gate journey runs a real local command through `run_and_sign`, hashes a temporary artifact, and passes the signed receipt plus local synthetic StaticAnalysis and IndependentReview receipts to `tools.vst.gate.evaluate`.
- Stale-head and missing/corrupt artifact checks retain rejecting assertions; no assertion was weakened.
- This does not exercise `tools.qa.run` report serialization, the v2 authenticated signer socket, the S4 WSL transfer, or sandbox deployment. Those remain separately open.

## Verification

- State at this commit: `NOT_RUN`; the five selectors are to be executed after all test/mapping edits are committed.
- Planned command: `python -m pytest -q -p no:cacheprovider` followed by the five exact E2E node IDs listed in `tests/qa/test_s4_report_bound_e2e.py`.
- No package installation, OS account change, external service, or production data is involved.

Executor: Codex
