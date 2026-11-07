# 0039 S2 TestRun signature authority wiring fix

## What

Passes the optional trusted `signer_key` from `gate.evaluate` into `_check_latest`, where the v2 TestRun path verifies the signed diff-gate evidence and runner attestation.

## Why

The first committed-head S2 runner/lifecycle batch reached the valid v2 TestRun route and raised `NameError: name 'signer_key' is not defined` in `_check_latest`. The helper referenced the authority key without accepting it as an argument. This made the required positive signature route crash instead of producing a gate decision.

## Affected contract and paths

- `tools/vst/gate.py`: the single `_check_latest` call site now passes the `signer_key` already validated by `evaluate`.
- V2 TestRun uses the signer trust root to verify the diff-gate and runner-attestation signatures. The v1 validation path does not execute these v2-only checks, so it continues to receive no behavioral change.
- Only the gate implementation and this change record, decision/lesson logs, and generated document registry belong to this change. Concurrent test-only edits are not included.

## Verification state

- Trigger evidence: E2E agent command `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py` on exact HEAD `d7d2e02de56d2388c6bba4160959a432e7f4a43d`; result 44 passed, 1 failed, 5 skipped. Failure ID: `test_gate_routes_each_v2_receipt_to_its_designated_authority[signer-TestRun-tests-signer]`; traceback reports the undefined `signer_key` at `tools/vst/gate.py:471`.
- The E2E agent reported store/anchor batch 4 passed and 8 skipped; sandbox-probe batch 2 passed and 7 skipped. Skips are retained as `NOT_RUN` for POSIX/WSL/VM scenarios and sandbox-dependent bake-off cases.
- This implementation change was made by an implementation agent on `gpt-6-luna`, low effort. No test, check, build, CI or migration command was run during implementation.
- Required next verification: the test agents rerun the affected runner/lifecycle scenario and full S2 focused suite after the exact commit is established. No runtime pass is claimed by this record.

## Ownership and next action

- Accountable task owner: operator. Executor: Codex implementation agent. Test authors/executors: `functional-test-reviewer` and `e2e-runner` roles. No human/service technical owner for the S2 gate is established in this record.
- Next: run the affected test on the committed exact head, then continue the full S2 test/review and sandbox provisioning gates.

Agent-Attribution: implementation-engineer (gpt-6-luna); Codex executor
