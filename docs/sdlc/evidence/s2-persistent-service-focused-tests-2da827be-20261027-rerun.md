# S2 focused functional test evidence — reservation and replay revision

**Disposition:** final approved safe selector set passed against the frozen dirty working diff after the `EXECUTION_RESERVED` source update. This is focused runtime evidence only, not complete S2 acceptance, exact-head reviewer approval, or authorization to provision/start services.

## Exact source and environment

| Field | Observed value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| HEAD / branch | `2da827be982d3f2d6f2adf152668af6ff8007f21` / `s4-canonical-continuation` |
| Runtime | `C:\Python314\python.exe`, Python 3.14.3 |
| Tracked binary diff SHA-256 | `19789f7df3fdba8f6493e42459a16ee9cd5c179a0bd283b0b0decf1c80625647` |
| Working-delta manifest SHA-256 | `fee22c51808c0d09fb91b475d48fecbc38d72e9a57c05548bd7bdef1b9a413d6`; sorted untracked path/content digests plus tracked diff digest, excluding this report to avoid self-reference |
| Working tree | Dirty; no files staged or committed. Existing concurrent changes retained. Git emitted line-ending normalization warnings for dirty files; they did not affect test results. |

The final run followed the implementation owner's explicit source-freeze confirmation. The accepted dirty source includes the durable `PENDING -> EXECUTION_RESERVED -> COMPLETE/INDETERMINATE` flow and claim/reservation status RPCs. This test report does not adjudicate the separate GPT-PM question about caller/lost-PENDING design; that decision remains with GPT-PM and Codex coordination.

## Final focused commands and results

Commands were run independently from the repository root. No migration, full-suite, build, lint, typecheck, CI, installer, service-runtime, or forbidden selector was run.

1. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` — **exit 0; 21 passed, 0 failed, 0 skipped; 1 warning; 0.93s**.
2. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence` — **exit 0; 32 passed, 0 failed, 0 skipped; 1 warning; 1.29s**.
3. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority` — **exit 0; 38 passed, 0 failed, 0 skipped; 1 warning; 7.94s**.
4. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py` — **exit 0; 22 passed, 0 failed, 0 skipped; 1 warning; 19.45s**.

**Final aggregate:** 114 passed, 0 failed, 0 skipped across four focused commands. Each command emitted the installed `pytest_asyncio` deprecation warning that `asyncio.get_event_loop_policy` is slated for removal in Python 3.16.

## New transition and replay coverage

The 21 tests in `tests/vst/test_s2_persistent_runner_service.py` cover:

- Store grant basis, deadline refusal, claim and PENDING verification; completion enters the normal receipt/hash chain and exact COMPLETE replay returns the one stored receipt.
- Preflight consumption refuses mutation before verified Store history.
- Supervisor claim RPC wraps a duplicate COMPLETE receipt as `{"state": "COMPLETE", "receipt": ...}` and preserves `None` for a new PENDING claim.
- Lost claim response followed by exact same-generation PENDING status allows reservation for that exact grant.
- Lost reservation response followed by EXECUTION_RESERVED status refuses to infer launch ownership; the test observes no child-launch call.
- Stale generation, expired grant and epoch-fenced lease reject reservation; a second reservation fails.
- A new generation marks predecessor PENDING and EXECUTION_RESERVED records INDETERMINATE.
- Signer response reads fragmented JSON through EOF and rejects empty, malformed, non-object and oversized replies; server bounds requests and tolerates a disconnected response peer.
- Runner config requires fixed `daemon_gid=988`; dispatcher obtains the grant before forwarding it to the runner.

The Store tests use fresh `:memory:` databases only. The grant fixture validates the Store transition shape; it does not prove Ed25519 grant trust, kernel peer credentials, or service isolation.

## Diagnostics, superseded runs and provenance

- An earlier pre-reservation provisional run (before the latest production freeze) passed the focused module 13, E1 32, E2 38 and E6 22 selectors. It is not final evidence for the reservation code.
- The first new-module attempt against the reservation code had three test-side failures: a Store completion fixture had not reserved before completion, and two Windows fake-authority tests tried to monkeypatch absent `os.geteuid` without `raising=False`. No implementation change was made by this test agent; the fixtures were corrected.
- A preceding collection attempt used a nonexistent class name (`SupervisorRPCServer`) for the test fake. The in-scope class is `AuthenticatedSupervisorAPI`; the test import was corrected.
- The successful final commands above were rerun after these test-only corrections and after the confirmed source freeze. The implementation owner owns the production source changes; this test agent changed only tests and this evidence artifact.
- The earlier `docs/sdlc/evidence/s2-persistent-service-focused-tests-2da827be-20261027.md` remains as a separate prior-pass report; this file supersedes its results for the newer reservation source fingerprint. The protected `docs/sdlc/evidence/s2-functional-test-run.md` was not edited by this test agent.

## Acceptance map and remaining scope

| Story / gate | Result and evidence | Remaining acceptance / owner / next action |
|---|---|---|
| VST-009 / E1 | Selected reviewer trust, receipt, and gate contracts: **32 passed**. | Selected contracts only; GPT-PM reviews the exact final source fingerprint. |
| VST-010 / E2 | Selected derived-head and caller-override contracts: included in **38 passed**. | Persistent runtime and OS identity boundary remain `NOT_RUN`; Codex coordinates only after the applicable environment authorization. |
| VST-011 / E2 signer | In-process signing, replay and receipt routing plus focused bounded stream/error contracts passed. | Real signer daemon, credentials, peer PID binding, and filesystem permissions remain `NOT_RUN`. |
| S2 grant/Store/service contracts | **21 passed**, including reservation, lost-response status, duplicate reserve, COMPLETE replay, and predecessor-state reconciliation. | No service start/stop or provisioning proof. Codex retains those runtime dependencies; do not infer runtime acceptance from these tests. |
| VST-015 / E6 | Selected diff-gate suite: **22 passed**. | Selected suite only; does not prove all S2 acceptance. |
| VST-012 / E3; VST-016–019 / E7 | Migrations, external anchor migration, crash/recovery and database restart selectors were not run. | `NOT_RUN`; prohibited migration/recovery scenarios remain out of scope. |
| VST-013 / E4; VST-014 / E5; VST-020 / E8 | No process-kill, descendant-cleanup, seeded mutation, E8, policy, platform-provisioning or systemd runtime selectors were run. | `NOT_RUN`; keep them restricted until separately authorized and provisioned. |

## Ordered next actions

1. **Codex:** link this rerun report and the focused test file to the S2 change record; preserve the dirty worktree and exact fingerprint.
2. **GPT-PM:** resolve the pending caller/lost-PENDING design question and review the exact final source diff plus this evidence.
3. **Codex / authorization owner:** retain service, migration, crash/recovery, mutation, E8 and policy runtime scenarios as `NOT_RUN` until their specific gates permit execution.
