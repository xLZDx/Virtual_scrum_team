# S2 safe functional selector evidence — working tree at `2da827b`

Status: **SAFE SELECTORS PASS ON THE POST-FIX DIRTY DIFF; NOT AN S2 ACCEPTANCE OR APPROVAL.** The first pre-fix runs below remain diagnostic only. The subsequent rerun includes the capability-clearing source/spec correction in the working tree and establishes fresh E1/E2/E6 selector evidence for the fingerprint recorded below. Persistent-service, platform, Store migration, crash/recovery, and other restricted acceptance remains untested.

## Post-capability-fix rerun

The coordinator reported that the explicit capability-clearing source/spec correction was present in the working tree. I refreshed status and fingerprints, then reran only the same E1/gate, E2, and E6 selectors documented below. No other tests were launched.

| Field | Observed value |
|---|---|
| Repository / HEAD / branch | `D:\Repo\Virtual_scrum_team`; HEAD before and after all three batches `2da827be982d3f2d6f2adf152668af6ff8007f21`; branch `s4-canonical-continuation` |
| Environment | Windows 11 Pro, PowerShell 7.6.9, Python 3.14.3 at `C:\Python314\python.exe` |
| Worktree | Dirty; no staging. Existing/current changes retained. The test-only signer fixture correction remains the only test-file change made by this test owner. |
| Changed tracked paths / stats | 15 paths, 1,191 insertions and 85 deletions |
| Tracked diff SHA-256 | `5cd8fd04a118d125615181f18fd337624de6ef298222497eaba5e3b1514f6c29` |
| Working-delta manifest SHA-256, excluding this evidence file | `938f935d39e0e6f33ad70073b1794d99c00711ea0296f3a2e94d42350848891f` (current tracked binary diff plus the 14 other untracked path/content entries; recomputed after the evidence update) |
| E1/gate rerun | Same command below; exit 0, 32 passed, no skips, 1 warning, 1.09 seconds |
| E2 rerun | Same command below; exit 0, 38 passed, no skips, 1 warning, 4.72 seconds |
| E6 rerun | Same command below; exit 0, 22 passed, no skips, 1 warning, 17.30 seconds |
| Aggregate for selected batches | **92 passed, 0 failed, 0 skipped**, three pytest_asyncio deprecation warnings across three commands |

The capability correction remains in the dirty diff, not a committed source head. These exact selector groups do not directly exercise the `worker_exec.c` capability-drop branch, persistent service/grant path, or real platform isolation; the capability correction's runtime behavior therefore remains unverified here. Each successful batch emitted the installed `pytest_asyncio` `DeprecationWarning` for `asyncio.get_event_loop_policy`, scheduled for removal in Python 3.16.

The post-run fingerprint refresh confirmed HEAD remained `2da827be982d3f2d6f2adf152668af6ff8007f21` and the worktree remained dirty. `git diff --binary` SHA-256 remained `5cd8fd04a118d125615181f18fd337624de6ef298222497eaba5e3b1514f6c29`. The stable working-delta fingerprint above excludes this evidence artifact to avoid self-reference. Git reported line-ending normalization warnings for existing dirty files; no file was staged or committed.

## Initial pre-fix source and worktree identity

| Field | Observed value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` (canonical checkout only) |
| HEAD before and after these selector runs | `2da827be982d3f2d6f2adf152668af6ff8007f21` |
| Branch | `s4-canonical-continuation` |
| Worktree | Dirty before, during and after the runs; no files were staged. Existing source/docs changes and untracked artifacts were preserved. |
| Runtime environment | Windows 11 Pro, PowerShell 7.6.9, `C:\Python314\python.exe` / Python 3.14.3 |
| Initial tracked diff | 12 changed paths, 1,142 insertions and 80 deletions; SHA-256 of `git diff --binary`: `ee4d7246d76b70c3d49e30c18d7a1f347d63018f18ad555f17e283010e2c3036` |
| Initial working-delta fingerprint | `cf09414c5c595abc5b08c7632636cbda49bbd37e940e935f1514e9f189932ba3` (tracked diff plus then-current 14 untracked file contents) |
| Tracked diff after test-only fixture correction, before capability spec update | 14 changed paths, 1,154 insertions and 80 deletions; SHA-256 of `git diff --binary`: `a2a08f82736314a46c4f20ab430fcffe5005db7c516a8b883d2effce30f2b336` |
| Working-delta fingerprint at that pre-fix snapshot | `373916c31a4fe0b63b2b2834d6da45760fc2dcd693b2a58bffcdcc95a19cd510` (tracked diff plus then-current 14 untracked file contents) |
| Additional change made by this test owner | Test-only fixture initialization in `tests/vst/test_s2_runner_lifecycle.py`: set `runner_gid=None` and `require_pinned_daemon=False` in the in-process signer protocol test, matching its explicit “without OS claim” contract. No product source was edited. This is included in the tracked-diff fingerprint above. |
| Evidence file timing | Initial snapshot hashes predate this artifact. The refreshed full-delta hash was computed while this file still contained only pre-fix results, then became stale when this record was amended. A new stable snapshot excluding this evidence artifact is recorded below. The previously existing `docs/sdlc/evidence/s2-functional-test-run.md` remains untouched. |

The working source change under review is the persistent manifest-runner boundary: modified paths include `tools/vst/runner.py`, `signer.py`, `store.py`, `supervisor.py`, `tools/qa/worker_exec.c`, and `tools/qa/install_wsl_worker_helper.sh`; untracked implementation artifacts include `execution_grant.py`, `runner_fence.py`, `runner_service.py`, `supervisor_service.py`, systemd unit templates and a runtime installer. Those changes were already present when this testing turn began; their authorship is not attributed to this test owner.

## Accepted story mapping

| Story/gate | Plain-language acceptance | Selectors run and outcome | Remaining acceptance / owner |
|---|---|---|---|
| VST-009 / E1 | Reviewer identity is authenticated through the signed registry and distinct key. | Post-fix registry normalization, valid/invalid registry cases, V2 receipt schemas, key-root distinctness, and unknown/author reviewer cases passed. The E2 authority matrix also passed its worker-signed IndependentReview rejection case. | Persistent service integration is not covered; Codex owns any separately authorized service-path tests. GPT-PM owns later exact-diff adjudication. |
| VST-010 / E2 | Runner derives candidate head and rejects caller-provided authority/evidence. | Three distinct git heads and caller-override rejection selectors passed in the post-fix E2 batch. | New grant-backed persistent service path is not covered by these library selectors; Codex owns a future focused run after service test contracts exist. |
| VST-011 / E2 | Worker cannot sign or access signer credentials; signer requests are authorized and replay-safe. | Post-fix type-specific gate key routing and in-process signing protocol replay/schema selector passed after test-only fixture correction. | Real persistent daemon, UID/GID/SID boundary, key access, `SO_PEERCRED`/pidfd binding, grant issuance, Store claim and systemd enforcement are `NOT_RUN` because service start/provisioning/migration are prohibited. Capability-drop runtime is not exercised by this exact selector batch. |
| VST-015 / E6 | Diff evidence is deterministic, path-scoped, and bound to the manifest/head. | All 22 selectors in `test_s2_diffgate.py` passed after the capability source/spec correction was present. | This does not prove the new persistent service consumes current Store authority or enforces the read-only reviewer OS credential. |
| VST-012 / E3 and VST-019 / E7 | External anchor integrity and startup reconciliation fail closed. | No Store selectors were run in this task. | Store schema v5 is not applied; store migration and crash/recovery selectors were prohibited. `NOT_RUN`. |
| VST-013 / E4, VST-014 / E5, VST-020 / E8 | Platform containment, real sandbox inventory and isolated bake-off. | No platform/service provisioning or prohibited selectors were run. | Kill/descendant cleanup, crash/recovery, network-policy, E8 and service lifecycle remain `NOT_RUN`. |

### Exact selector command mapping

**E1 plus V2 gate contract — 32 passed pre-fix and 32 passed post-fix.** Command:

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence
```

Initial pre-fix result: exit code 0, **32 passed**, no skips, one warning, 0.70 seconds. Post-fix rerun: exit code 0, **32 passed**, no skips, one warning, 1.09 seconds. Expanded IDs: `test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key`; `test_reviewer_registry_failures_do_not_produce_a_trusted_mapping[wrong_key|stale_version|digest_mismatch|duplicate_principal]`; `test_v2_contract_accepts_each_receipt_type_with_its_required_fields[TestRun|StaticAnalysis|IndependentReview|Documentation]`; `test_v2_trust_root_keys_are_pairwise_distinct[worker-supervisor|worker-operator|worker-signer|worker-event|worker-reviewer|supervisor-operator|supervisor-signer|supervisor-event|supervisor-reviewer|operator-signer|operator-event|operator-reviewer|signer-event|signer-reviewer|event-reviewer]`; `test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review[unknown-reviewer|author-y]`; `test_gate_refuses_caller_supplied_parser_implementation`; `test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence[missing|wrong_manifest|wrong_head|fail_verdict|bad_signature]`.

**E2 runner/signature authority — initial diagnostic and corrected rerun.** Exact command for both attempts:

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority
```

- First attempt: exit code 1; **37 passed, 1 failed**, one warning, 6.01 seconds. Failure: `test_signing_request_exact_schema_and_replay_protocol_without_os_claim`; the fixture constructed `AuthenticatedSigner` through `object.__new__` and omitted the new `runner_gid` and `require_pinned_daemon` attributes. `_handle` raised `AttributeError` before protocol assertions. This was a test-fixture defect, not an observed runtime signer rejection.
- Authorized test-only correction: initialized those omitted fields to `None` and `False`, respectively, retaining the test's explicit no-OS-claim intent. No product source changed.
- Corrected rerun: exit code 0; **38 passed**, no skips, one warning, 6.82 seconds.
- Expanded IDs: `test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides`; `test_runner_rejects_caller_supplied_head_parser_key_or_commands[candidate_head|commands|parser|test_result_parser|key|signing_key]`; `test_signing_request_exact_schema_and_replay_protocol_without_os_claim`; `test_gate_routes_each_v2_receipt_to_its_designated_authority[receipt_type-slot-expected_key-key_kind]` across five receipt/slot configurations and six supplied key kinds (30 IDs).

**E6 deterministic diff gate — 22 passed pre-fix and 22 passed post-fix.** Command:

```text
C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py
```

Initial pre-fix result: exit code 0, **22 passed**, no skips, one warning, 17.58 seconds. Post-fix rerun: exit code 0, **22 passed**, no skips, one warning, 17.30 seconds. Collected selectors: five runner/untracked-file evidence scenarios, allowed deterministic change, seven blocked file classes, explicitly scoped blocked-class control, four invalid path cases, out-of-scope path, rename into blocked hook, symlink change, and manifest/head binding.

All three final successful batches emitted the same installed `pytest_asyncio` `DeprecationWarning`: `asyncio.get_event_loop_policy` is deprecated and slated for removal in Python 3.16. It did not fail the run.

## Explicitly not run

No selector for kill/descendant cleanup, process kill, crash, restart/recovery, mutation or seeded defect, E8 bake-off, waiver/policy, real sandbox inventory/egress, or service installation/start was included. These remain `NOT_RUN` under the task restrictions; they were not converted into skips or passes by these commands.

No new tests were found that reference `execution_grant`, `runner_service`, `supervisor_service`, `execution_grant_basis`, or `claim_runner_execution`. The existing passing selectors therefore do not prove the new persistent service/grant path, Store schema v5 claims, or systemd peer enforcement. Store-backed tests were not run because instantiating the current Store would apply the prohibited schema migration. Service/systemd integration is not run because starting services is prohibited.

## Disposition and next action

The selected E1/gate, E2 library-contract, and E6 diff-gate checks passed again with the capability correction present in the dirty working diff. The initial E2 fixture failure is retained as a superseded diagnostic above. These results are not committed-head acceptance and do not exercise the capability-drop branch or persistent service. Codex owns the next action: reconcile and commit the source fix, establish a fresh exact diff/head, then select only permitted tests directly covering the changed capability behavior. Keep all prohibited/platform/persistent-service scenarios `NOT_RUN` until their separate authorization and environment requirements are met. No files were staged or committed.
