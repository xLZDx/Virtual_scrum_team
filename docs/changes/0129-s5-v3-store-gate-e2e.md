# 0129 S5 v3 Store-to-Gate integration tests

## What changed

- Added three focused E2E journeys that append a v3 `StaticAnalysis` receipt to a real temporary SQLite Store, read it back, then submit it to the authoritative Gate.
- Covered exact-head acceptance limited to the manifest's static-analysis acceptance ID, stale-head non-acceptance, and a persisted finding whose derived result is `FAIL`.
- Resolver callbacks hash temporary report, finding-evidence, and source-snapshot files; no product source or external service is executed.

## Why

The S5 functional module proves contract predicates and gate branches directly. These journeys cover the persistence boundary and demonstrate that a stored receipt still requires independent Gate verification and artifact/source digest resolution.

## Affected contracts and paths

- `tests/vst/test_s5_v3_store_gate_e2e.py`
- S5 AC-3/4: independent analyzer trust and signed provenance binding at the Gate boundary.
- S5 AC-9/10/11: exact-head static acceptance scope, stale-head rejection, and failure evidence non-approval.

## Decisions and ownership

- Accountable task owner: operator under delegated S5 continuation. Executor: Codex.
- Evidence is synthetic and local to VST. It does not claim that AEVE, its adapter, signer provisioning, or sandbox runtime was executed.
- Existing v1/v2 canonical receipt hashes and signatures remain covered by the already committed functional tests; this change does not edit their contracts or fixtures.

## Verification state

- Test source authored at pre-test HEAD `5f88b893c64652056ffe1728f458678abcc7fe69`.
- Test execution is intentionally pending until this test source and record are committed, so the exact-head run can be recorded separately.
- Planned exact test IDs:
  - `tests/vst/test_s5_v3_store_gate_e2e.py::test_s5_store_round_trips_v3_receipt_and_gate_accepts_only_static_acceptance`
  - `tests/vst/test_s5_v3_store_gate_e2e.py::test_s5_store_persisted_stale_v3_receipt_does_not_satisfy_current_head`
  - `tests/vst/test_s5_v3_store_gate_e2e.py::test_s5_store_persisted_finding_remains_failure_at_authoritative_gate`

## Follow-up

1. Run only the three IDs above on the clean test commit and record exact command, environment and outcome in a separate evidence record.
2. Update the E2E registry denominator to include these committed nodes and regenerate `governance/DOCUMENT_REGISTRY.md` in the evidence commit.
3. Keep actual AEVE execution and sandbox proof `NOT_RUN` until an authorized in-scope runtime and its trust boundaries are available.
