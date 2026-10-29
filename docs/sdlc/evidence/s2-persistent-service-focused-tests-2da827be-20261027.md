# S2 focused functional test evidence — persistent runner source diff

**Disposition:** selected safe contracts passed on the current dirty working diff. This is focused runtime evidence only; it is not S2 acceptance, exact-head review, or approval to provision, commit, or merge.

## Source and environment identity

| Field | Observed value |
|---|---|
| Repository | `D:\Repo\Virtual_scrum_team` |
| Git HEAD / branch | `2da827be982d3f2d6f2adf152668af6ff8007f21` / `s4-canonical-continuation` |
| Runtime | `C:\Python314\python.exe`, Python 3.14.3; pytest via repository environment |
| Tracked binary diff SHA-256 | `ec755e99e2c9dcb6f35b6c89ab5be21d8650f19179eed98e6c19523b772bb5e5` |
| Working-delta manifest SHA-256 | `cd80800c6044241d8d77d63799af4e6ab5dee827f5a3d959c340f14cdd0532fa`; combines tracked diff digest and sorted untracked path/content digests, excluding this report to avoid self-reference |
| Working tree | Dirty; no staging or commit performed. Existing concurrent files were preserved. Git emitted line-ending normalization warnings for dirty files; no warning was a test failure. |

The source diff includes execution grants, durable Store claim/receipt-chain changes, supervisor/runner service code, signer bounded socket I/O, fixed runner service identity configuration, and runtime/systemd artifacts. Those implementation files were already in the shared dirty worktree; this test agent does not claim to have authored them.

## Final commands and results

Each command was run independently from `D:\Repo\Virtual_scrum_team`, with no cache provider and no selection beyond the listed paths/selectors.

1. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_persistent_runner_service.py` — **exit 0; 11 passed, 0 failed, 0 skipped; 1 warning; 1.22s**.
2. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_contract_gate.py::test_reviewer_registry_is_verified_and_maps_normalized_principal_to_trusted_key tests/vst/test_s2_contract_gate.py::test_reviewer_registry_failures_do_not_produce_a_trusted_mapping tests/vst/test_s2_contract_gate.py::test_v2_contract_accepts_each_receipt_type_with_its_required_fields tests/vst/test_s2_contract_gate.py::test_v2_trust_root_keys_are_pairwise_distinct tests/vst/test_s2_contract_gate.py::test_unknown_or_author_reviewer_does_not_authenticate_as_independent_review tests/vst/test_s2_contract_gate.py::test_gate_refuses_caller_supplied_parser_implementation tests/vst/test_s2_contract_gate.py::test_gate_rejects_missing_stale_or_inconsistent_diff_gate_evidence` — **exit 0; 32 passed, 0 failed, 0 skipped; 1 warning; 0.80s**.
3. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands tests/vst/test_s2_runner_lifecycle.py::test_signing_request_exact_schema_and_replay_protocol_without_os_claim tests/vst/test_s2_runner_lifecycle.py::test_gate_routes_each_v2_receipt_to_its_designated_authority` — **exit 0; 38 passed, 0 failed, 0 skipped; 1 warning; 4.58s**.
4. `C:\Python314\python.exe -m pytest -q -rs -p no:cacheprovider tests/vst/test_s2_diffgate.py` — **exit 0; 22 passed, 0 failed, 0 skipped; 1 warning; 15.15s**.

**Final aggregate:** 103 passed, 0 failed, 0 skipped across four focused commands. Each command emitted the installed `pytest_asyncio` warning that `asyncio.get_event_loop_policy` is deprecated and planned for removal in Python 3.16. No test was marked xfail.

## Diagnostics superseded by the final runs

- The first run of the new module was a setup-only test-fixture failure: 2 passed and 2 failed before product assertions because the fresh Store fixture had not initialized a concurrency slot. The fixture was corrected to call `store.init_slots(1)`; this run is diagnostic only.
- A later pre-fix run of the new module had 10 passed and 1 failed. The completion test exposed a product defect: `claim_runner_execution` passed a `sqlite3.Row` instead of the task ID into `_budget_block_locked`, causing `sqlite3.ProgrammingError`. The implementation owner corrected the affected Store call sites, then explicitly reconfirmed production code freeze. The final 11-pass run above was after that fix.
- The first E2 batch after the signer timeout change had 37 passed and 1 failed because the in-process test peer lacked the newly required `settimeout` method. This was a fixture defect; the peer fixture now stores the timeout value. The final 38-pass run above was after that test-only correction.

None of these diagnostic results is counted as acceptance evidence. The Store failure was reported to the implementation owner and fixed there; this test agent edited no product source.

## Coverage-to-acceptance map

| Story / gate | What the selected tests establish | State and remaining acceptance |
|---|---|---|
| VST-009 / E1 reviewer trust and receipt gate | Selected registry validity/failure, V2 receipt schema, trust-root separation, reviewer identity, caller-parser rejection, and gate-evidence selectors: 32 passed. | **Selected contracts passed.** Does not establish full E1 acceptance beyond these selectors. GPT-PM still owns exact-diff adjudication. |
| VST-010 / E2 derived runner evidence | Selected distinct-head and caller-override selectors: included in 38 passed. | **Selected library contracts passed.** Persistent service runtime and platform boundary are not established here. |
| VST-011 / E2 signer authority | Existing in-process signer replay/schema/receipt-routing selectors passed; new tests cover fragmented signer reply to EOF, empty/malformed/non-object/oversized replies, bounded request rejection, and disconnected response writes. | **Selected protocol contracts passed.** No real UID/GID, SO_PEERCRED/pidfd, key-permission, daemon, or socket runtime proof. |
| S2 persistent runner / grant and Store contract | New tests cover fixed `daemon_gid=988` config requirement, Supervisor grant before runner dispatch, deadline rejection before durable claim, grant basis, PENDING verification, receipt/hash-chain completion, exact COMPLETE replay, and preflight integrity guard. | **11 focused contracts passed.** Uses only fresh `:memory:` Store. Does not run migrations or validate an existing database. Cryptographic grant verification and service OS trust boundary are not established by these tests. |
| VST-015 / E6 diff gate | Existing selected `test_s2_diffgate.py` cases: 22 passed. | **Selected diff-gate suite passed.** Does not validate all S2 acceptance. |
| VST-012 / E3 and VST-016–019 / E7 | No external anchor migration, store migration, restart/reconciliation, crash, or recovery selectors run. | **NOT_RUN.** Migration/recovery scenarios were expressly outside this test scope. |
| VST-013 / E4, VST-014 / E5, VST-020 / E8 | No platform provisioning, kill/descendant cleanup, seeded mutation, E8 bake-off, network-policy, or service lifecycle execution. | **NOT_RUN.** Prohibited selectors and runtime provisioning were not invoked. |

## Exact limitations and provenance

- All added database evidence used newly created `Store(":memory:", ...)`; no existing database was opened or upgraded.
- The claim fixture uses a structurally valid envelope; this Store contract intentionally does not prove grant signature cryptography. Real signer trust, process identity, UID/GID isolation, systemd stop behavior, worker helper installation, service start/stop, process kill/crash/recovery, mutation/E8/policy selectors, and the full suite remain **NOT_RUN**.
- The new tests are in `tests/vst/test_s2_persistent_runner_service.py`. The test-only timeout support is in the `_RequestConnection` fixture in `tests/vst/test_s2_runner_lifecycle.py`. No product source was changed by this test agent.
- The pre-existing/protected `docs/sdlc/evidence/s2-functional-test-run.md` was not edited by this agent. No files were staged or committed.

## Ordered next actions

1. **Codex:** preserve this report and test file with the S2 change record, then have a fresh reviewer inspect the final source diff and focused evidence.
2. **GPT-PM:** adjudicate the exact final dirty diff plus this report; approval must identify that exact source fingerprint.
3. **Codex / operator authorization:** only after the separate authorized environment gate, address runtime/system identity and restricted acceptance. Until then retain the listed scenarios as `NOT_RUN`.
