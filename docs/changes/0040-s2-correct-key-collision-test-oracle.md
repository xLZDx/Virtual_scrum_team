# 0040 S2 key-collision test oracle correction

## What

Corrected the pairwise trust-root collision assertion in `tests/vst/test_s2_contract_gate.py`. It now requires a non-approving verdict and the specific reviewer-key collision reason when the reviewer key collides with another root. Other key pairs still require the general pairwise-distinctness reason.

## Why

On committed HEAD `d7d2e02de56d2388c6bba4160959a432e7f4a43d`, the functional test agent ran the contract/gate module and observed 5 failures and 33 passes. The five cases were reviewer-key collisions. The gate rejected them with the dedicated reason `reviewer keys must differ from worker, supervisor, operator, signer, and event keys` and a non-approving `MODIFY` verdict, while the tests incorrectly required `NO_GO` and the general collision message. `MODIFY` is a valid fail-closed rejection; no accepting result was observed.

## Affected contract

- Test oracle for all 15 pairwise key-collision combinations across worker, supervisor, operator, signer, event, and reviewer trust roots.
- No production source changed in this record.

## Verification state

- Before this correction: `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py` reported 5 failed, 33 passed, 1 warning; `tests/vst/test_s2_diffgate.py` reported 17 passed, 1 warning. The warnings were `pytest_asyncio` deprecations on Python 3.14.
- After the correction, the functional agent ran collection only for the two functional modules: 55 IDs collected, exit 0. No corrected runtime test has run yet.
- E2E evidence at `d7d2e02...` separately found the product `NameError` in the positive signer/TestRun route. That production defect was fixed in commit `9d612c98b81fdf7b38c61eda235771b1f8011bc7`; the new code and corrected test oracle still require runtime execution on a later exact head.

## Ownership and next action

- Accountable task owner: operator. Test author: `functional-test-reviewer` on `gpt-6-luna`. Executor/coordinator: Codex. Canonical technical service owner is not identified for this test contract.
- Next: commit this corrected oracle and run the affected functional module, runner/lifecycle module, and complete five-file focused set on the exact new HEAD.

Agent-Attribution: functional-test-reviewer (gpt-6-luna); Codex executor
