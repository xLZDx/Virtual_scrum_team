# 0038 S2 focused test suite and S3 preparation

## What

- Added functional contract and diff-gate scenarios in `tests/vst/test_s2_contract_gate.py` and `tests/vst/test_s2_diffgate.py`.
- Added runner/lifecycle, store/anchor, and sandbox-probe scenarios in `tests/vst/test_s2_runner_lifecycle.py`, `tests/vst/test_s2_store_lifecycle.py`, and `tests/vst/test_s2_sandbox_probe.py`.
- Added receipt-signature authority routing cases through the public gate, including wrong-key rejection; all six trust roots also have pairwise-distinctness coverage.
- Corrected the S2 plan's receipt/key denominator to reflect the gate's receipt authorities and six distinct key roots.
- Prepared `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md` with candidate audit gates, adapter contract, acceptance and test mapping, DoR/DoD, dependencies, and proposed backlog items. S3 remains not started.
- Retained `docs/sdlc/evidence/s2-e2e-platform-run.md` as preliminary historical evidence only; it explicitly does not satisfy the committed-head acceptance run.

## Why

S2 requires negative tests for trust boundaries, lifecycle, external anchor, diff scope and probe contract before the final exact-head pass. Source inspection established receipt-type-specific signing authorities; the test scenarios and plan now use those authorities. S3 preparation is required by the sprint workflow while S2 verification proceeds.

## Affected contracts and paths

- S2 acceptance: reviewer identity and registry, parser catalog pin, runner/signer authority, lifecycle/idempotency, event anchor, diff gate, probe schema, and explicit platform-dependent `NOT_RUN` cases.
- Added five focused S2 test modules and the S3 worker-pilot plan.
- Updated `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md` denominator and authority rule.
- Added preliminary historical evidence under `docs/sdlc/evidence/` with provenance and limitations stated in the document.

## Decisions

- Only `functional-test-reviewer` and `e2e-runner` own required test authoring and execution. The primary coordinator commits their completed files and reconciles evidence.
- Receipt authority follows the gate contract: TestRun uses the isolated signer; IndependentReview uses the registry-mapped reviewer; StaticAnalysis and Documentation use worker or supervisor authority by slot. Operator and event keys have separate registry/waiver and checkpoint roles.
- No synthetic inventory is accepted as proof of a real sandbox. Platform cases unavailable on the current host remain `NOT_RUN` until operator provisioning and a real probe.
- S3 candidate audit and acquisition are not performed by this preparation document; Temporal is provisional and its exact revision/license/compatibility remain unverified.

## Verification state

- The E2E agent ran `C:\Python314\python.exe -m pytest --collect-only -q -p no:cacheprovider tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py tests/vst/test_s2_runner_lifecycle.py tests/vst/test_s2_store_lifecycle.py tests/vst/test_s2_sandbox_probe.py` after both test owners completed their changes and reported exit 0 with 126 collected IDs (55 functional IDs and 71 E2E IDs). This is collection evidence only; no runtime pass is claimed.
- Functional runtime execution on pre-fix code HEAD `b2b168e71000323443882988cd24af2cdbabf4df` reported 30 passed and 3 parser-pin failures. The implementation fix is in commit `3af18a1bc7f87ba9f31cd86e98888f2aecf58922`; the fix has not yet been runtime-verified here.
- The historical preliminary run file records older dirty-tree results and is not exact-head evidence.
- The committed-head functional/E2E run, sandbox inventory, specialist reviews, and final exact-head approval are outstanding.

## Ownership and next action

- Accountable task owner: operator. Executor: Codex. Required test authors and executors: `functional-test-reviewer` and `e2e-runner` roles. No named technical service owner for host sandbox provisioning is established by current project records.
- Next: commit the complete authored suite and this record; then run the focused set on that exact commit, keeping unavailable platform scenarios explicitly `NOT_RUN`.

Agent-Attribution: functional-test-reviewer, e2e-runner (gpt-6-luna); Codex executor
