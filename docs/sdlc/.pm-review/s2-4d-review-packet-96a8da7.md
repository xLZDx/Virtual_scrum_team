# S2-4D exact-head code review packet

## Review target
- Task: S2-4D / REQ-003; S2-5 bounded S2 code acceptance.
- Base: `eb9b0ed53c66cfb21dc9a2e23265772293daaabb`.
- Candidate commit: `96a8da7` (full identity is in the attached exact diff/commit header).
- Scope: remove retired QA-only WSL inventory/configuration-apply/qualification scripts and their tests; keep the product `tools/vst` path unchanged; correct the bundle contract test to reflect that `scope` permits a file path while `required_tests` and `mandatory_commands` retain the exact selector.

## Operator scope decision
The operator removed the WSL collector/apply/qualification workflow and its Git source checks from active S2 work. Do not request or perform runtime grants, WSL actions, collector runs, configuration apply, or Git source checks. Historical records remain provenance only. The bounded S2 code acceptance does not claim a live Runner, E5, deployment, or production result.

## Test evidence (actual e2e-runner role, Windows project checkout)
1. `python -B -m pytest -q -p no:cacheprovider tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment` — exit 0; `1 passed, 1 warning in 0.39s`. Attempt JSON: `docs/sdlc/evidence/s2-4d-req003-windows-selector-20261106-02.attempt.json`; stdout SHA-256 `0b3ac25ac7a19019e8cd950f7373c2cf51917772bbdea43a4fa4ab05948e16ff`; stderr empty. This proves persisted Store handoff equality only.
2. `python -B -m pytest -q -p no:cacheprovider tests/vst/test_s2_runtime_config_bundle.py` — exit 0; `11 passed, 1 warning in 5.08s`. Attempt JSON: `docs/sdlc/evidence/s2-4d-runtime-config-bundle-windows-20261106-02.attempt.json`; stdout SHA-256 `0105a76d04b99ea98248ceb51ac90fc9b007227e880a232a5d09594eeeec6de6`; stderr empty.
3. The earlier bundle attempt (`...-01.attempt.json`) failed `1 failed, 10 passed` because the assertion incorrectly expected a selector in `scope`. The assertion was corrected to the allowed file path; the exact selector remains in `required_tests` and `mandatory_commands`. The subsequent focused run passed. Both attempt records and raw outputs are attached.

## Internal review
- `code-reviewer` configured role, model `gpt-5.6-luna`; effort used inherited/default and was not explicitly recorded. Scope: five removed QA scripts, four related test modules, bundle-test adjustment, product-call boundary. Result: no code BLOCKER/MAJOR; `tools/vst` does not call/import the removed QA scripts.
- `code-explorer` independently confirmed the product path is `DispatchOwnerService` → authenticated Supervisor/Store → StoreBackedDispatcher → Runner, and the REQ-003 selector remains Store-local rather than live runtime proof.

## Source fidelity and limits
The test-attempt SHA-256 values for `tools/vst/store.py`, `tools/vst/assignment_basis.py`, `tools/vst/contracts.py`, and both involved test files were independently compared to the current files and matched. No product dispatch source changed in this candidate. No `evidence.py` or documented project evidence command exists in the repository; the attempts and raw output were manually checked. CI, broad tests, WSL runtime, E5, production identity/configuration, and live service-to-Runner were not run and are not claimed.

## Requested verdict
Review the exact candidate commit and bounded source/test acceptance. Return `APPROVE` or findings by severity with exact path/criterion and evidence. This is code adjudication only; no runtime authorization is requested.
