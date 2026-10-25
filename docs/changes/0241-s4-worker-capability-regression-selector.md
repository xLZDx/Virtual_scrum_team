# Change 0241: Add a worker capability-drop regression selector

## What changed

- Added `tests/qa/test_s4_worker_exec.py` with a mapped functional selector that verifies the worker UID/GID and empty supplementary groups, zero inheritable/permitted/effective/ambient capabilities, enabled `no_new_privs`, and denial of `setuid(997)` before the manifest command can proceed.
- Added a separate focused synthetic-socket boundary probe that invokes `_run_one()` and checks the worker cannot traverse/connect to a runner-owned Unix socket. This selector is not included in the category denominator because it is a focused runner-owned harness probe.
- Updated `docs/qa/categories.json` to map the regression selector and set the category source provenance to the committed source fix `45f4bb7ee7a62ac3f700533e20ec1a60a2f05139`.

## Why

The ambient-capability probe on base HEAD `0aa7a53` showed that UID 999 retained `CAP_SETUID` and could regain UID 997. The source remediation in change 0240 therefore needs a falsifiable runtime regression that executes after the credential switch and before an authorized command can reach the signer boundary.

## Decisions and ownership

- Test author and executor: `e2e-runner` (GPT-6 Luna, medium effort).
- The mapped selector is Linux-specific and must be run in the pinned Ubuntu-24.04 WSL environment; a Windows platform skip is not a passing result for this required case.
- The synthetic Unix socket only verifies local filesystem/socket access denial. It is not evidence of a deployed or trusted S4 signer service.
- Accountable task owner: operator. Coordinator/executor: Codex. Canonical QA infrastructure owner: UNKNOWN.

## Affected contracts and paths

- S4 worker identity and signer boundary in `tools/vst/runner.py` / `tools/vst/worker_exec.py`.
- Functional test denominator and category projection in `docs/qa/categories.json`.
- Focused test coverage in `tests/qa/test_s4_worker_exec.py`.

## Verification state

- Base source HEAD: `45f4bb7ee7a62ac3f700533e20ec1a60a2f05139`.
- The test and registry changes were authored after the source fix. They have not yet been committed or executed at this record's creation.
- Required next run: fresh exact-head snapshot, then `e2e-runner` executes the mapped Linux selector under the bounded transient runner unit. Acceptance requires UID 999, empty `CapInh/CapPrm/CapEff/CapAmb`, `PR_GET_NO_NEW_PRIVS=1`, `EPERM` on `setuid(997)`, and signer-socket traversal/connect denial. Report-bound v2, trusted signer, signed receipt/gate, E2E denominator completion, and aggregate regression remain separate.
