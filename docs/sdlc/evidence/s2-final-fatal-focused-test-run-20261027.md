# S2 focused functional evidence: ambiguous authority fail-stop

## Scope and provenance

This is the assigned functional-test execution record for the final S2 source freeze. It does not claim full S2 acceptance, service-runtime proof, GPT-PM approval, or permission to provision/install a service. The protected `docs/sdlc/evidence/s2-functional-test-run.md` was left unchanged.

| Field | Observed value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| HEAD / branch | `2da827be982d3f2d6f2adf152668af6ff8007f21` / `s4-canonical-continuation` |
| Interpreter | `C:\Python314\python.exe`, Python 3.14.3 |
| Tracked binary diff SHA-256 | `e89fa993dd253ca5396b1c1fcb83759d7aca0c2133f1ea73e61d5cbd2b1d1d69` |
| Working-delta SHA-256 | `65d12475738dda9ba92320a0c7e4a8c39a6e641c07ed2f5157de8495619622c4` |
| Fingerprint definition | SHA-256 over tracked `git diff --binary` digest plus sorted untracked path/content SHA-256 entries; this evidence file excluded to avoid self-reference. 20 untracked files were included. |
| Worktree / staging | Dirty; no files staged or committed by this test task. Existing concurrent work was preserved. |

The persistent runner implementation files and the initial untracked test module were already present at assignment time. This task added focused test cases to `tests/vst/test_s2_persistent_runner_service.py` and this separate evidence record; it did not edit product source. The exact additions are the claim-status ambiguity, reservation-status ambiguity, exact same-generation `NOT_FOUND`, and malformed authority-context cases.

## Final permitted commands

All commands ran independently from the repository root. The aggregate is 117 passed, 0 failed, 0 skipped across these four final commands. Each emitted one installed `pytest_asyncio` deprecation warning (`asyncio.get_event_loop_policy`, scheduled for removal in Python 3.16).

1. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` — exit 0; **25 passed**, 0 failed, 0 skipped; 1 warning; 1.31s.
2. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence` — exit 0; **32 passed**, 0 failed, 0 skipped; 1 warning; 1.10s.
3. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority` — exit 0; **38 passed**, 0 failed, 0 skipped; 1 warning; 6.19s.
4. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py` — exit 0; **22 passed**, 0 failed, 0 skipped; 1 warning; 20.12s.

## Acceptance map and limits

| Story / gate | Evidence from this run | Remaining acceptance, dependency, owner, next action |
|---|---|---|
| VST-011 / E2 execution grant ambiguity | In-memory authority fakes exercise claim transport failure followed by failed claim-status lookup, and reserve transport failure followed by failed status lookup. Both raise `AmbiguousExecutionAuthorityError`; no child-launch callback occurs. | The service `_handle` REFUSED frame and actual manager-driven process restart were not run in this focused test set. Codex owns a separately authorized service-boundary test/run; any OS/service-manager runtime evidence remains NOT_RUN under this scope. |
| VST-011 / exact `NOT_FOUND` edge | Exact `NOT_FOUND` bound to the current generation raises ordinary `ContractError`, leaves `_claimed` false, and does not reach child launch. | This tests authority semantics with fakes, not an installed supervisor/runner service. Codex owns any additional allowed integration evidence. |
| VST-011 / ordinary invalid request | Malformed authority context raises ordinary `ContractError`, not `AmbiguousExecutionAuthorityError`, and cannot reach child launch. | The service response remains code-inspected only; no daemon or systemd runtime is claimed. |
| VST-009 / E1 | Seven approved reviewer-registry, receipt-schema, trust-root and gate selectors: 32 passed. | Selected contract tests only; GPT-PM owns required exact-diff architecture adjudication. |
| VST-010 / E2 | Four approved caller-authority/head selectors: 38 passed. | They do not prove the live persistent service, process identity, or helper runtime. Codex owns authorized runtime evidence. |
| VST-015 / E6 | `test_s2_diffgate.py`: 22 passed. | No broader S2 policy-selector claim is made. |
| Forbidden / platform scope | No process/crash/recovery/mutation/E8/policy selectors, full suite, checks/build, migrations, service installation, WSL runtime, or provisioning ran. | These remain NOT_RUN; the next step requires the specifically authorized scenario/tool boundary and the owning S2 coordinator to schedule it. |

During test development, an initial service-handler fake did not reach the handler path and produced two test-harness failures. That harness was removed; the final added cases exercise the authority failure contract directly. These failures did not identify a product-source defect. The final four commands above were rerun successfully after the test-only correction.

## Ordered handoff

1. Codex links this evidence to the S2 change record and requests exact-head GPT-PM review after all source changes are frozen.
2. Codex coordinates only the remaining allowed service-boundary/runtime evidence; record any prohibited or unavailable runtime step as `NOT_RUN` with its exact dependency.
3. Preserve all forbidden process/crash/recovery/mutation/E8/policy selectors as `NOT_RUN` unless their owning authorization boundary is explicitly satisfied.

Report SHA-256 is recorded after file creation in the task handoff.
