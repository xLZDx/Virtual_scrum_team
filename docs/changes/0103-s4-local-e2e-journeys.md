# 0103 S4 local synthetic E2E journeys

## What changed

- Added `tests/qa/test_s4_qa_e2e.py` with a CLI-level synthetic VST slice journey and an early-refusal test for an unapproved WSL distribution.
- Added `docs/sdlc/evidence/s4-e2e-local-1cd868b.md` with exact local commands, environment, the corrected test-defect classification, and native-runtime dependencies.

## Why

S4 requires integration and E2E scenarios to run across real local boundaries while keeping unavailable sandbox-dependent acceptance visible in the denominator. These local scenarios exercise the synthetic CLI boundary without inventing private provisioning values or claiming native signed-run acceptance.

## Affected contracts and paths

- `tests/qa/test_s4_qa_e2e.py`: executes the existing `tools.vst.slice` CLI and the public WSL snapshot CLI refusal path.
- `docs/sdlc/evidence/s4-e2e-local-1cd868b.md`: records local runtime evidence and precise `NOT_RUN` dependencies.

## Decisions and ownership

- Accountable task owner: operator under delegated S4 continuation. Executor: Codex (`e2e-runner`).
- The two new E2E node IDs are not yet in the committed category registry. The coordinator will add them with a `source_head` that is an ancestor containing the committed test nodes; this avoids claiming invalid provenance.
- The local snapshot case uses an intentionally unsupported distribution, so it returns before WSL invocation and does not use a runner account, worker GID, destination root, or signer socket.
- The WSL account, worker GID, private destination root, and S4 signer socket remain unknown; no values are copied from S2 records. Canonical technical owner remains `UNKNOWN`.
- No E2E framework or dependency was added. No product source was changed by this E2E work.

## Verification state

- On the Windows host, Python 3.14.3 and pytest 8.4.2: the first test execution reported one pass and one failure caused by my test's incorrect expected slice-report shape. After correction, the module passed 2/2 at product source HEAD `1cd868b776a50147b951c9282cc73e2868c6bad6` (10.52 seconds) and again at `b0c61a1ec96b6152157bf9e681f1f5d86f1c1771` after coordinator commit 0104 (5.79 seconds). Both passing runs showed one existing `pytest-asyncio` deprecation warning.
- The new test source was untracked during those executions. Exact committed-candidate acceptance must be recorded by the coordinator after the registry and remaining test changes are committed.
- Native S4 runner/report/signature/gate execution and snapshot transfer remain `NOT_RUN`; see the evidence file for exact dependencies.
- No CI, build, migration, package installation, or source transfer was run.

## Follow-up

1. The coordinator adds the test IDs to the category registry using valid ancestor provenance and commits the complete S4 denominator, preserving concurrent work.
2. After all code and tests are committed, rerun the E2E module on the exact candidate and record the result.
3. Obtain S4 provisioning inputs from the designated private evidence, then run native S4 E2E/signing/gate journeys in `Ubuntu-24.04`; until then retain the affected criteria as `NOT_RUN`.
