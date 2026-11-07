# S2 focused functional evidence — `e987a244`

Date: 2026-10-29. Scope: `functional-test-reviewer` assignment-bootstrap and pure dispatch-issuance selectors only. Source HEAD at start and finish of these runs: `e987a24483a5130298a28cccd2efd08f457aab9a`.

## Source freeze and test identity

The target product source files were unchanged across the run. SHA-256 values captured before execution and checked again after execution:

| Source file | SHA-256 |
|---|---|
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` |
| `tools/vst/store.py` | `176a61e9543f3a2b730111d8bf65a1e7b8da8758197163bac8b968ec7717e6b9` |
| `tools/vst/dispatch_issuance.py` | `6f3671f5f2446ff222e620fcb38dfd975c8b787bfa9e3adddf1e8d375cc1f668` |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` |
| `tools/vst/supervisor_service.py` | `2a351270df79a4aef05dc06eb9eb95d4131ba9e1bc7b30fbe39334f1242ddac0` |

Python: `C:\Python314\python.exe`; pytest: `8.4.2`.

Final test SHA-256 values:

| Test file | SHA-256 |
|---|---|
| `tests/vst/test_s2_assignment_bootstrap.py` | `76d8087f7fcb795d9b96aa798acc2d54c689b61038ab9f93074f26f9f88a87cf` |
| `tests/vst/test_s2_dispatch_issuance_contract.py` | `0e0795bf87f5bac3e4678a4050666508144013f84dd28e799f92d987ba1af44d` |
| `tests/vst/test_s2_assignment_basis.py` | `7d97e39635683373bb771ae7826bc41b1c8fc79b7f346cf256856b45aa3488f6` |
| `tests/vst/test_s2_machine_source_contracts.py` | `b11c345ff1c032ee903d59a2896eb42ecb7fa4d57c6868a8bb216870c1a93f09` |

The assignment-basis fixture was updated in this turn to include the accepted root-policy tuple (`project_id`, `phase`, runner ID and bounded owner/lease TTLs) and handoff project/phase. Existing malformed identity, journal, trust-provider, stale generation/run and RPC negative cases were retained. The machine-source fixture already used the accepted closed policy/authorization shapes and retained its existing rejection cases; no product behavior or machine-source test was changed in this turn.

## Executed commands and outcomes

1. `& 'C:\Python314\python.exe' -m pytest --version` — **PASS**, `pytest 8.4.2`.
2. `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py` — **39 passed, 6 skipped**, exit code 0. The six skips are the existing POSIX-only OpenSSL fixture cases on Windows. One pytest-asyncio deprecation warning was emitted; it did not affect outcomes.
3. `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py` — **43 passed, 3 failed, 6 skipped**, exit code 1. The three failures share one product defect described below. The prior failures from an incorrect fixture clock and missing fixture handoff fields were corrected before this result; they are not part of the remaining defect set.

The bootstrap, assignment-basis and machine-source results are the exact source-head run above. Issuance acceptance is incomplete because the pure freeze path fails before reducer cases can exercise their intended states.

## Requirements and acceptance map

| Requirement / story meaning | State and evidence | Remaining acceptance / blocker | Owner and next action |
|---|---|---|---|
| TP-29, S2-3 AC-1/4, REQ-005/006: one fresh atomic bootstrap creates the story/task, exact zero-cost budget, epoch 2, attempt-1 lease and linked handoff | **PASS, fixture-proven:** `test_fresh_bootstrap_commits_one_complete_epoch_two_zero_budget_handoff`; included in 39-pass command. | Temporary in-memory SQLite only; not real Store/runtime proof. | Codex: retain this selector in final allowed set. |
| TP-30, S2-3 AC-1/4: exact replay is byte-identical; conflict has no effects | **PASS, fixture-proven:** `test_exact_bootstrap_replay_returns_same_bytes_and_conflicting_payload_has_no_effect`. | Does not prove concurrent callers or process crash. | Codex: retain; E2E owns the integrated journey separately. |
| TP-31, S2-3 AC-1/4: bootstrap refuses prior assignment history without adopting it | **PASS, fixture-proven:** parameterized story/task/event/budget/lease history refusals preserve snapshots. | Terminal marker, receipt, prior handoff and noninitial attempt are not each separately seeded by this file. No crash proof. | Codex: add only if required by final frozen API; keep unavailable cases explicit. |
| TP-32, S2-3 AC-1/4: zero budget is valid; invalid/exhausted budget and slot boundaries refuse | **PARTIAL:** `cost_cap=0` and `spent=0` pass in TP-29 positive boundary. | This file does not separately falsify over-cap, exhausted-attempt and occupied-slot fixtures. | Codex: determine coverage against the final Store API and add mapped cases if accepted source exposes deterministic fixtures. |
| TP-33, S2-4 AC-2, I01-SRC-03: immutable key class/purpose/fingerprint, verifier-required completion and journal integrity | **PARTIAL / BLOCKED:** binding negative cases pass; reducer tests could not build a valid frozen intent due the product defect below. | Completed signed record and reducer integrity cases must run after the fix. No real key/signature used. | Codex: fix source; functional-test-reviewer reruns issuer selectors. |
| TP-34, S2-4 AC-2, I01-SRC-01/03/05: one intent/start, no automatic resign from ambiguous state | **NOT_RUN:** pure ordering cases are in the blocked issuer module; these tests do not establish Store signer-call concurrency. | Store journal/signer-call-counter integration belongs to the frozen integrated suite. | Codex / E2E owner: execute permitted fixture integration after source fix; no process-kill inference. |
| TP-35–37, S2-4 AC-2, I01-SRC-01/04: exact grant provenance, current checks at admission/grant/claim/reservation | **NOT_RUN by this role:** covered by separate integrated-root-dispatch selectors. | Root/E2E results and exact source hash are pending. | E2E role: report its separate selectors/results; Codex reconciles acceptance. |
| TP-38, S2-4 AC-2, I01-SRC-04/05: issuer default-off, exact authenticated role/request and immutable current trust tuple | **PARTIAL / NOT_ACCEPTED:** no pure test here proves configured RPC/service behavior. Manual source read found cached trust/config state (see finding). | Current trusted-root registry/config disable/revocation provider must be adjudicated. | Codex: close source question, then functional/E2E roles test exact service/RPC behavior. |
| E1/E3/E6/E7 original gates: key/signature boundary, durable journal integrity, Store assignment isolation and idempotency | **PARTIAL:** this run proves focused synthetic source contracts for E1/E6/E7 and basis reads; it does not close the original epic denominators. | Original allowlist and restricted selectors remain outside this focused execution. | Codex: reconcile full final allowed selector inventory after fixes. |

## Product defect requiring a source fix

All three failing new pure issuance cases stop in `tools/vst/dispatch_issuance.py:263`. `freeze_issuance_intent()` spreads `issuance_identity()` into the frozen intent, but that identity contains `request_id`, `operation_key` and `operation_sha256` only. `_INTENT_FIELDS` also requires `assignment_operation_id`, and the frozen object does not provide it. Reproduction of the closed-field comparison reported exactly one missing field, `assignment_operation_id`, and no extra fields. This causes a valid freeze to raise `ContractError("frozen issuance intent fields do not match the closed schema")`; dependent reducer assertions therefore cannot run. This is a product-source defect, not a fixture-only issue. The implementation owner is Codex; the issuer selectors remain paused until its fix batch is complete.

## Source review concern and limits

Manual read of `tools/vst/supervisor_service.py:844` shows the dispatch trust registry is read into a value once during service loading, then passed as a dictionary to `Supervisor`; use-time checks consume cached registry/config plus file fingerprint checks. No current trusted-root provider that reloads the registry or issuer-enabled state at each authorization boundary was found. The root owner confirmed this as a valid known source gap against I01-SRC-04's current root key-registry/config-disable requirement. It is not counted as a passing test.

No production configuration, service, root key, private signing key, external network, real Store, worker, or process lifecycle was used. Real signer call, grant/admission integration not owned here, root configuration activation, E5, process-kill/crash/recovery, mutation, E8 and restricted policy selectors are `NOT_RUN`.

## Ordered closure steps

1. **Codex:** fix the frozen-intent `assignment_operation_id` omission and adjudicate the trusted-root registry/config provider concern.
2. **Functional-test-reviewer:** rerun `test_s2_dispatch_issuance_contract.py` against the new exact source hash; preserve failures rather than weakening the contract.
3. **E2E role / Codex:** finish the separately owned integrated root-dispatch test and report exact command, source/test hashes, and results.
4. **Codex:** reconcile TP-29–38 and original E1/E3/E6/E7 coverage; keep all prohibited lifecycle selectors `NOT_RUN` and map their owner/dependency.

## Post-fix frozen-head addendum — `a20283da`

Root recorded a new S2 source freeze at `a20283da75a1900b2ee297cd4215b87ac3c9059f` after change 0561. Product source hashes remained stable across this role's post-fix focused run:

| Source file | SHA-256 |
|---|---|
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` |
| `tools/vst/store.py` | `176a61e9543f3a2b730111d8bf65a1e7b8da8758197163bac8b968ec7717e6b9` |
| `tools/vst/dispatch_issuance.py` | `e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a` |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` |
| `tools/vst/supervisor.py` | `62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71` |
| `tools/vst/supervisor_service.py` | `14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2` |

Post-fix test hashes:

| Test file | SHA-256 |
|---|---|
| `tests/vst/test_s2_assignment_bootstrap.py` | `8d6c50da428ac68de95a9587caa4609e506427f95350c1b2022e8869b168cd70` |
| `tests/vst/test_s2_dispatch_issuance_contract.py` | `25ad2f0062f830c523b5a157960c7fd6090901fda8bc89a520a7fe3cc20eafc2` |
| `tests/vst/test_s2_assignment_basis.py` | `7d97e39635683373bb771ae7826bc41b1c8fc79b7f346cf256856b45aa3488f6` |
| `tests/vst/test_s2_machine_source_contracts.py` | `b11c345ff1c032ee903d59a2896eb42ecb7fa4d57c6868a8bb216870c1a93f09` |

Exact post-fix command: `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py` — **54 passed, 6 skipped**, exit code 0. The skips remain existing POSIX-only OpenSSL fixture cases on Windows; one pytest-asyncio deprecation warning was emitted. This is a new exact-head result and is not added to or combined with the historical e987a24 counts above.

Post-fix coverage closes this role's accepted bootstrap cases as follows:

| Requirement | Post-fix state and evidence | Remaining acceptance / owner |
|---|---|---|
| TP-29, S2-3 AC-1/4: fresh atomic assignment | **PASS, fixture-proven:** complete story/task, zero-cost budget (`cap=0`, `spent=0`), epoch 2, attempt-1 live lease, handoff and linked operation event are asserted. The pre-commit ordinary-error regression now compares every Store table, event, and external-anchor bytes and proves they remain unchanged. | Temporary Store only; no runtime/production proof. Codex maps this case into final allowed inventory. |
| TP-30, S2-3 AC-1/4: replay/conflict | **PASS, fixture-proven:** exact replay returns the identical handoff and changes no table; same assignment with a fresh request ID is refused after the existing valid handoff without state changes. | No concurrency or literal crash claim. |
| TP-31, S2-3 AC-1/4: fresh-only history | **PASS, fixture-proven:** prior story, task, generic event, budget, lease, valid worker receipt, valid `RETRY_EXHAUSTED` marker receipt and an actual prior valid handoff are refused without state adoption. | The same-identity exact replay remains allowed by TP-30. |
| TP-32, S2-3 AC-1/4: budget, attempt and slot boundaries | **PASS, source-fixture-proven:** zero-cost boundary passes; fault-injected `spent=cap+1` after task/budget insertion refuses and rolls back; a valid occupied slot refuses and leaves target absent; attempt 2 and boolean attempt refuse without writes; a valid retry-exhausted marker receipt is refused as prior receipt history. | The retry marker is caught by fresh-only receipt history before the inner lease helper's terminal branch; this proves fail-closed refusal, not a claim that the lower terminal predicate was reached. |
| TP-33, S2-4 AC-2, I01-SRC-03: immutable pure issuance | **PASS, pure contract:** valid frozen handoff includes assignment operation identity and exact v1 fields; key class/purpose/closed binding, event ordering, closed schemas, no-verifier refusal, literal-`True` verification and `may_sign=false` are asserted. | No real root signing key or external crypto was used. |
| TP-34, S2-4 AC-2, I01-SRC-01/03/05: journal at-most-once behavior | **PARTIAL / separate integration owned by E2E:** pure reducer covers PENDING/UNKNOWN/conflict ordering; Store signer-call count and ambiguity persistence are not claimed by these tests. | E2E role supplies its integrated result; Codex reconciles against TP-34. |
| TP-35–38, I01-SRC-01/04/05: end-to-end provenance and current providers | **Pure provider contract PASS:** enabling the issuer without both providers fails construction; matching live issuer/trust values are accepted; disabled/changed issuer, changed trust registry and provider exception fail closed. | Integrated root issuance/grant/claim/reservation journey and real root-controlled file reader remain with E2E role; no activation or production identity evidence. |
| E1/E3/E6/E7 original epic gates and prohibited selectors | **Partial / NOT_RUN:** focused source regressions do not close original denominators. Process-kill/crash/recovery, mutation, E8 and restricted policy selectors remain unrun. | Codex reconciles final allowed inventory and retains exact restricted `NOT_RUN` statuses. |

Root had confirmed the identified `assignment_operation_id` source defect and cached current-trust gap as the 0561 fix batch. The corresponding post-fix pure assignment/provider regressions now pass at the exact head above. No source file was modified by this test role.

After this run, the root owner relayed a new E2E finding: `authenticated_assignment_basis` returns a handoff enriched with `payload_sha256`, and the pure closed-handoff validator rejects that enriched object. This is a separately reported integrated-path source issue; it was not exercised by this role's 54/6 command and must not be presented as resolved by that result. **Owner:** Codex to complete the next source fix batch; functional-test-reviewer and E2E role to rerun only after a new freeze GO.

## Post-0562 frozen-head addendum — `6f4ad200`

Root recorded S2 source freeze `6f4ad200091a06a8318e7b90158f1948c7d3cf24` after change 0562. That change returns the exact validated stored handoff and retains internal payload-digest checks. Product source hashes were stable during this role's focused run:

| Source file | SHA-256 |
|---|---|
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` |
| `tools/vst/store.py` | `10ec8eff9b92b39cca3045a358bd6659a6b8c0a8bfe129755cd79df48e86c035` |
| `tools/vst/dispatch_issuance.py` | `e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a` |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` |
| `tools/vst/supervisor.py` | `62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71` |
| `tools/vst/supervisor_service.py` | `14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2` |
| `tools/vst/machine_observations.py` | `9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11` |

Current test hashes:

| Test file | SHA-256 |
|---|---|
| `tests/vst/test_s2_assignment_bootstrap.py` | `8d6c50da428ac68de95a9587caa4609e506427f95350c1b2022e8869b168cd70` |
| `tests/vst/test_s2_dispatch_issuance_contract.py` | `25ad2f0062f830c523b5a157960c7fd6090901fda8bc89a520a7fe3cc20eafc2` |
| `tests/vst/test_s2_assignment_basis.py` | `77f9c8724a84511b1882c9a3834ff4518fd8fef406df142b46a7de222dac5533` |
| `tests/vst/test_s2_machine_source_contracts.py` | `b2f646393c5239822b7bd2853cb450ca2fd785b99daf164b54b9954d902f7743` |

Exact command: `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py` — **60 passed, 6 skipped**, exit code 0. The six skips are existing POSIX-only OpenSSL fixture cases on Windows; one pytest-asyncio deprecation warning appeared. The first attempt at this command had three new collector-fixture failures because its simulated Windows `os` object lacked `path.isabs`; after correcting that fixture shim, the exact command passed. These results are distinct from prior heads and are not cumulative.

| Requirement / behavior | State at `6f4ad200` | Remaining acceptance / owner |
|---|---|---|
| Change 0562, TP-26: exact stored handoff representation | **PASS, Store fixture:** `test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment` compares returned handoff to the canonical stored operation result and asserts no derived `payload_sha256`. | E2E role separately verifies integrated positive issuance. |
| Change 0562: closed-schema rejection | **PASS, Store fixture:** `unknown_handoff_field` is retained in the malformed handoff and rejected; no input field is stripped. | Existing missing/malformed-field regressions remain in the same file. |
| Change 0555, TP-25: Windows collector profile and process contract | **PASS, mocked process boundary:** two profiles assert fixed executable/arguments, exact profile-specific `PSModulePath`, empty `PATH`, fixed working directory, closed stdin, `close_fds`, and `CREATE_NO_WINDOW`; ambient user/module variables are absent. | No Windows PowerShell or host query was launched; runtime collection remains unverified. |
| Change 0555, TP-25: unknown/unavailable profile behavior | **PASS, mocked process boundary:** unknown profile launches no subprocess and remains `UNSUPPORTED`; unavailable PowerShell 5 launches only the selected executable and remains `UNKNOWN`, with no profile fallback or PASS. | Real host behavior is not proven by mocks. |
| TP-29–32 bootstrap scope | **PASS, fixture-proven and retained in the 60/6 current run:** zero-cost happy path, replay/conflict, valid prior story/task/event/budget/lease/receipt/terminal/handoff history, over-cap spend, occupied slot, noninitial/boolean attempt, and all-table/event/anchor rollback after an ordinary exception. | Temporary Store fixtures only; no production or crash proof. A retry marker is refused by fresh receipt-history eligibility before the lower terminal branch. |
| TP-33–34 pure issuance/provider contracts | **PASS, pure contract:** frozen identity, closed issuer binding, event ordering, verifier requirement and live provider changes fail closed. | Store-level signer-call concurrency and ambiguous completion remain integrated TP-34 work. |
| TP-35–38 / original E1/E3/E6/E7 denominators | **PARTIAL:** this role's focused run does not close integrated S2 issuance or original epic denominators. | E2E supplies its exact WSL archive run; Codex reconciles final denominators and restricted `NOT_RUN` selectors. |

New WSL-capable mocked collector and exact-handoff selectors were sent to E2E. This role ran no real PowerShell command, network request, signing, service activation, or production configuration operation.

## Post-0563 frozen-head addendum — `8beffcc8`

Root recorded new S2 source freeze `8beffcc8807c7a522fed9527022819a67741dcee` after change 0563. The Store adapter now parses and canonical-checks serialized issuance operation results before invoking the unchanged typed pure reducer. Product source hashes captured after the scoped run:

| Source file | SHA-256 |
|---|---|
| `tools/vst/store.py` | `610f9482fea889e2ff0767b8696caa16290e46f9aeff92a1e048a93d625b8c60` |
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` |
| `tools/vst/dispatch_issuance.py` | `e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a` |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` |
| `tools/vst/supervisor.py` | `62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71` |
| `tools/vst/supervisor_service.py` | `14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2` |
| `tools/vst/machine_observations.py` | `9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11` |

Current test hashes:

| Test file | SHA-256 |
|---|---|
| `tests/vst/test_s2_assignment_bootstrap.py` | `8d6c50da428ac68de95a9587caa4609e506427f95350c1b2022e8869b168cd70` |
| `tests/vst/test_s2_dispatch_issuance_contract.py` | `397007d580a77abae7f7b7461ff2d6efb6ce3f2821e7006c30f04293d5be011b` |
| `tests/vst/test_s2_assignment_basis.py` | `77f9c8724a84511b1882c9a3834ff4518fd8fef406df142b46a7de222dac5533` |
| `tests/vst/test_s2_machine_source_contracts.py` | `b2f646393c5239822b7bd2853cb450ca2fd785b99daf164b54b9954d902f7743` |

Exact command: `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py` — **62 passed, 6 skipped**, exit code 0. Six skips are existing POSIX-only OpenSSL fixture cases on Windows; one pytest-asyncio deprecation warning appeared. This exact-head outcome is not combined with prior-head counts.

| Requirement / behavior | State at `8beffcc8` | Remaining acceptance / owner |
|---|---|---|
| TP-29–32: bootstrap atomicity, replay, history, budget/attempt/slot boundaries | **PASS, fixture-proven:** the `6f4ad200` bootstrap cases and test hashes are unchanged and passed in the current 62/6 command. | No production or crash proof. Codex keeps final selector mapping separate from integrated gates. |
| TP-26 / change 0562: exact persisted handoff identity and closed-schema refusal | **PASS, Store fixture:** exact stored handoff equality and unknown-field rejection passed at the prior `6f4ad200` run; unchanged tests passed again at `8beffcc8`. | E2E still owns integrated positive issuance confirmation. |
| TP-33 / change 0563: Store-to-pure issuance result serialization boundary | **PASS, negative adapter contract:** `test_store_adapter_rejects_malformed_or_noncanonical_issuance_result` rejects invalid JSON and parseable noncanonical JSON before reducer use. The pure reducer remains typed and strict. | E2E owns real positive issuance/reducer/grant path; the adapter negatives do not claim it. |
| TP-34–37: legacy grant compatibility and delegated grant provenance | **NOT_RUN by this role:** root assigned these source regressions to E2E; this role did not author integrated grant tests. | E2E: prove legacy/direct allowed behavior and delegated origin without exact grant linkage remains refused. |
| TP-38 / change 0555: provider and collector source contracts | **PASS in focused source tests:** current-provider rejection and mocked collector profile/env/no-window/unsupported/no-fallback assertions passed at `6f4ad200` and unchanged tests passed again at `8beffcc8`. | No real Windows collection or production trust/config activation is proven. |
| Original E1/E3/E6/E7 denominators and restricted selectors | **PARTIAL / NOT_RUN:** this focused command does not close original epic totals. | Codex reconciles final selector inventory; preserve process-kill/crash/recovery, mutation, E8 and restricted policy cases as `NOT_RUN`. |

The two additional adapter tests are negative Store-boundary cases only; they do not mirror or substitute for E2E's positive integrated issuance journey. E2E was sent the updated issuance test-file hash and exact new selector IDs for any WSL archive run that had not started.

### Fixture portability follow-up (not run)

After E2E's WSL run at `8beffcc8`, its report identified test-environment incompatibilities: OpenSSL fixtures were created beneath world-writable `/tmp`, which the unchanged root-controlled key guard correctly rejects; the missing-Windows-profile mock also lacked POSIX's absent `subprocess.CREATE_NO_WINDOW` constant. The functional-test-reviewer updated only `tests/vst/test_s2_machine_source_contracts.py` to create disposable keys beneath `/root` with mode `0700` (skipping explicitly when a root-owned private ancestor is unavailable) and to mock the Windows creation flag on POSIX. The trust guard and behavioral assertions were not changed. New test-file SHA-256 is `93cd62e6b4c8f9aa2db758b90b6fd00e1e4b3552e193dd3936351df25d4c73ef`. **These fixture edits are NOT_RUN** pending root's next source freeze GO; the prior `8beffcc8` 62/6 result remains bound to the prior machine-source test hash `b2f646...` and is not evidence for this updated test file.

## Post-0563 frozen-head Windows run — `67d1d55e`

Root authorized a new source freeze at `67d1d55e5556c6936516f3404202faecba1e6707`. Exact Windows command: `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py` — **62 passed, 6 skipped**, exit code 0. Six skips are the existing POSIX-only signed OpenSSL machine authorization cases on Windows; the updated root-owned key directory fixture is expected to execute those in the E2E WSL counterpart. One pytest-asyncio deprecation warning appeared. These counts are specific to this exact head and are not combined with any prior run.

Source hashes captured after the Windows run:

| Source file | SHA-256 |
|---|---|
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` |
| `tools/vst/store.py` | `d0a5516531b0941654a5b262e24d2ee5d9513de888f0c8f9b2b1176ac09a7a12` |
| `tools/vst/dispatch_issuance.py` | `e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a` |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` |
| `tools/vst/supervisor.py` | `62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71` |
| `tools/vst/supervisor_service.py` | `14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2` |
| `tools/vst/machine_observations.py` | `9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11` |
| `tools/vst/machine_authorization.py` | `8c031f5547874b4811264e400d0b28166f1ca7b3d962ee0d04e75ba9d140e8ff` |

Test hashes in the executed payload:

| Test file | SHA-256 |
|---|---|
| `tests/vst/test_s2_assignment_bootstrap.py` | `8d6c50da428ac68de95a9587caa4609e506427f95350c1b2022e8869b168cd70` |
| `tests/vst/test_s2_dispatch_issuance_contract.py` | `397007d580a77abae7f7b7461ff2d6efb6ce3f2821e7006c30f04293d5be011b` |
| `tests/vst/test_s2_assignment_basis.py` | `77f9c8724a84511b1882c9a3834ff4518fd8fef406df142b46a7de222dac5533` |
| `tests/vst/test_s2_machine_source_contracts.py` | `93cd62e6b4c8f9aa2db758b90b6fd00e1e4b3552e193dd3936351df25d4c73ef` |

The exact-handoff, unknown-field, TP-29–32 bootstrap, TP-33 adapter rejection, live-provider, and mocked collector profile/environment/unsupported-profile cases all passed in the assigned Windows command. The POSIX key-signature cases and E2E-integrated legacy/delegated grant journey remain pending their exact WSL run; no production Store, signing key, host collector query or service activation was used.

## Post-freeze E7 Store, dispatch-owner, transport, and latch supplement — Windows `67d1d55e`

This supplement records the independently bounded E7 source-contract selectors authorized after the existing four-module assignment/issuer run. Source HEAD remained `67d1d55e5556c6936516f3404202faecba1e6707` throughout; the exact test additions are confined to the listed test file fixture portability adjustment. A separate E2E role owns the WSL/runtime counterpart.

### Executed selector payload

| Area and accepted contract | Selected cases | Windows result | Remaining acceptance |
|---|---|---:|---|
| TP-30 / E7 dispatch outcome transaction, duplicate prevention and acknowledgement | pending marker rolls back with rejected acceptance; exact replay returns original result; changed request conflicts; exact acknowledgement is idempotent; changed result/principal conflicts; replay identity binds principal, signed envelope and signature; owner-role RPC authorization; acknowledgement RPC failure preserves pending barrier | Included in **40 passed, 17 skipped** run; the Store tests in this group were skipped on Windows because fixture keys require the designated root-owned POSIX fixture | POSIX synthetic-key run; E2E owns integrated positive dispatch journey |
| E7 intent binding and replay boundaries | atomic intent result/event binding; wrong owner or slot refusal; malformed request ID refusal; reused request ID with changed payload refusal | Same scoped run; keypair-dependent Store cases skipped for the same POSIX fixture dependency | POSIX synthetic-key run |
| E7 subscription and cursor integrity | generation/owner lease and released lease suppress stale delivery; subscriber/MAC/generation-bound cursor rejects tampering; systemic Store error propagates without advancing replay | Same scoped run; keypair-dependent Store cases skipped | POSIX synthetic-key run |
| E7 admission latch and stop ordering | existing latch blocks load; exclusive durable root-owned latch write; root check occurs before persistence/stop; socket stop occurs even on persistence failure; retry until stopped/inactive; persistent latch written only after socket is off; service/socket unit latch conditions agree | **7 passed** on the final latch-only rerun | Windows mocks do not prove systemd/POSIX filesystem behavior; WSL E2E counterpart owns platform evidence |
| E7 owner transport authentication and idempotency boundary | systemd peer identity and write-half-close ordering; fixed socket path/timeout; missing pidfd, wrong peer identity, malformed pidfd, exited peer, untrusted filesystem identity and connect failure refuse before submission; malformed/oversized/trailing/truncated post-submit responses and send uncertainty fail closed without retry; explicit refusal is not retried; result identity binding rejects each changed field | The transport selections were included in the **40 passed, 17 skipped** scoped run | Real systemd/PID 1 credentials and installed socket remain unverified; WSL E2E owns its local socketpair/runtime counterpart |
| Owner service framing and signed request contract | canonical single-frame acceptance, forwarding failure does not ack, wrong response principal is unknown, never-accepted expired/revoked requests do not reach admission, trailing frame/EOF/bounds/duplicate/noncanonical/expanded/truncated wire input refuse before RPC, invalid instruction refuses before RPC | **NOT_RUN on Windows:** collection of `test_s2_dispatch_owner_service.py` fails at module import because Windows `socket` has no `AF_UNIX`; pytest reported `AttributeError: module 'socket' has no attribute 'AF_UNIX'`. No service selector executed by that attempt. | POSIX/WSL owner-service selectors are assigned to E2E; no source defect is inferred from the platform collection failure |

The literal final command used a PowerShell `$nodes` array of 35 explicit node IDs from the Store-backed Pub/Sub, dispatch-owner latch, and dispatch-owner transport files, followed by:

```powershell
& 'C:\Python314\python.exe' -m pytest -q -rs $nodes
```

It returned **40 passed, 17 skipped, 0 failed**, exit code 0, with one pytest-asyncio deprecation warning. All 17 skips were from keypair-dependent Store-backed Pub/Sub selectors requiring the designated root-owned POSIX fixture. The command did not select whole modules. The seven latch selectors were separately rerun with literal node IDs and returned **7 passed, 0 skipped, 0 failed**, exit code 0, one pytest-asyncio deprecation warning.

A first combined attempt included owner-service selectors and failed during module collection on the Windows-only `socket.AF_UNIX` absence; no tests ran in that attempt. After removing that module from the Windows command, the first scoped result was **36 passed, 17 skipped, 4 failed**: four latch tests attempted to monkeypatch POSIX-only `os.fchown` / `os.geteuid`. A focused latch rerun then exposed an additional POSIX-only `O_NOFOLLOW` assertion on Windows. The test fixture was corrected to create absent mocked `os` attributes with `raising=False` and to assert `O_NOFOLLOW` only on platforms defining it; source code and security assertions on POSIX were not changed. The final scoped and latch-only reruns above passed. These failed attempts remain historical and are not added to final pass counts.

### Exact identities and changed test payload

Source hashes at the final scoped run:

| Source file | SHA-256 |
|---|---|
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` |
| `tools/vst/store.py` | `d0a5516531b0941654a5b262e24d2ee5d9513de888f0c8f9b2b1176ac09a7a12` |
| `tools/vst/dispatch_issuance.py` | `e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a` |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` |
| `tools/vst/supervisor.py` | `62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71` |
| `tools/vst/supervisor_service.py` | `14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2` |
| `tools/vst/machine_observations.py` | `9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11` |
| `tools/vst/machine_authorization.py` | `8c031f5547874b4811264e400d0b28166f1ca7b3d962ee0d04e75ba9d140e8ff` |

| Test file | SHA-256 after this turn's edit |
|---|---|
| `tests/vst/test_s2_store_backed_pubsub.py` | `b5f6a36ab8511ea7e09a67d327a44b637b94faab312e0d13293cd735e293b0bc` |
| `tests/vst/test_s2_dispatch_owner_service.py` | `fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71` |
| `tests/vst/test_s2_dispatch_owner_transport.py` | `e9ce576a549d9617b39d9469200030548a4c8c81cc8f3ac3f879490ea5d40` |
| `tests/vst/test_s2_dispatch_owner_latch.py` | `dd747aa5c42cf4745197c77b0138c2e71bdd9690ed3d779d00969142382d35f1` |

Only the latch test file was changed in this supplement. The change adapts mocked POSIX ownership/effective-user calls on Windows and does not relax POSIX assertions. No product source was edited.

### Original E7 denominator and explicit limits

The original E7 denominator in `docs/sdlc/S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md` covers VST-016–019 state/event transitions, operation identity and duplicate-effect prevention, breaker state, provider replay, ambiguous callback handling, STOP/rollback continuation, concurrent starts, and stale or invalid operator resolution. This run adds Windows evidence for bounded Store/dispatch-owner transport contracts and mock-only latch behavior; it does not close that full denominator.

| E7 portion | State | Evidence / remaining acceptance | Owner and next action |
|---|---|---|---|
| Dispatch outcome/idempotency and owner transport source contracts | **PARTIAL / Windows source tests pass** | 40 passed; 17 POSIX-root-fixture cases skipped. Owner service could not collect on Windows (`socket.AF_UNIX` unavailable). | E2E: report POSIX/WSL exact selectors and platform limits; Codex: reconcile the accepted E7 node inventory. |
| Breaker transitions, provider replay, ambiguous callback recovery, concurrent starts, and STOP/rollback continuation | **NOT_RUN here** | This selector payload did not cover lifecycle/recovery modules or concurrent/process behavior. Process kill, crash/restart/recovery and mutation remain prohibited by the current test scope. | Codex: map any allowed non-recovery source selectors from the accepted inventory; restricted runtime claims remain NOT_RUN. |
| Stale/invalid operator resolution and full E7 closure | **NOT_RUN / not established by this run** | This run covers transport owner-role and request refusal only; it does not prove operator-resolution stories or every original state/event pair. | Codex: reconcile against the original E7 matrix and identify which accepted cases have another exact-head record; do not infer a denominator count from this subset. |
| Installed runtime, actual PID 1 credentials, real systemd stop semantics, real crash recovery | **NOT_RUN** | Windows mocks and temporary SQLite fixtures are source contracts only. | Operator for any real-host authorization; until authorized and evidenced, keep runtime acceptance open. |

Restricted process termination, crash/restart/recovery, mutation, E8, S4, production Store/configuration, real key material, and service activation were not executed. No total E7 node count is claimed because the accepted denominator is expressed as a contract set with overlapping test modules and parameterized selectors, not a reconciled unique-node inventory.

## Additional E7 lifecycle, breaker, concurrency and operator-resolution selectors — Windows `67d1d55e`

Root requested a selector-level gap check rather than treating whole recovery/lifecycle modules as prohibited. I reviewed the selected test bodies. Every selector below uses pure values, temporary SQLite, synthetic HMAC/operator fixture keys, in-process callbacks, or threads; none starts an external worker, runs process-kill logic, performs a real crash, contacts a remote backend, activates services, or mutates a real Store. The two Store-reopen cases exercise a temporary database fixture and are only source-level replay predicates, not real process-restart evidence.

### Executed cases and outcomes

The combined focused command selected these exact existing test IDs:

```powershell
$nodes = @(
 'tests/vst/test_s2_runner_lifecycle.py::test_lifecycle_transition_table_rejects_unlisted_pairs',
 'tests/vst/test_s2_runner_lifecycle.py::test_breaker_requires_operator_signed_override_bound_to_active_episode',
 'tests/vst/test_s2_runner_lifecycle.py::test_manual_override_replay_is_stale_after_a_later_breaker_episode',
 'tests/vst/test_s2_runner_lifecycle.py::test_stale_second_supervisor_cannot_start_after_peer_opens_persisted_breaker',
 'tests/vst/test_s2_runner_lifecycle.py::test_reconciliation_rejects_unsigned_false_and_accepts_signed_operator_resolution',
 'tests/vst/test_s2_runner_lifecycle.py::test_restart_resumes_the_correct_cleanup_phase_after_reconciliation',
 'tests/vst/test_s2_runner_lifecycle.py::test_two_cached_ready_supervisors_allow_only_one_concurrent_start_callback',
 'tests/vst/test_s2_operation_recovery.py::test_external_operation_intent_and_completion_are_committed_around_callback',
 'tests/vst/test_s2_operation_recovery.py::test_external_operation_timeout_stays_pending_and_same_key_payload_recovers',
 'tests/vst/test_s2_persistent_runner_service.py::test_store_reservation_fails_for_stale_expired_or_epoch_fenced_authority',
 'tests/vst/test_s2_persistent_runner_service.py::test_store_reservation_is_one_time',
 'tests/vst/test_s2_persistent_runner_service.py::test_new_generation_marks_predecessor_claim_indeterminate',
 'tests/vst/test_s2_persistent_runner_service.py::test_reserved_or_unsafe_reconciled_predecessor_blocks_every_successor_gate',
 'tests/vst/test_s2_persistent_runner_service.py::test_execution_reserved_predecessor_blocks_successor_gates_before_recovery',
 'tests/vst/test_s2_persistent_runner_service.py::test_effects_resolved_operator_record_allows_only_a_separately_authorized_successor',
 'tests/vst/test_s2_persistent_runner_service.py::test_pre_spawn_pending_predecessor_can_retry_only_after_normal_lease_rules',
 'tests/vst/test_s2_persistent_runner_service.py::test_execution_reconciliation_rejects_tampered_mismatched_or_invalid_records',
 'tests/vst/test_s2_persistent_runner_service.py::test_execution_reconciliation_rejects_resolution_id_reused_for_another_grant',
 'tests/vst/test_s2_persistent_runner_service.py::test_authority_changed_before_complete_reconciliation_requires_exact_reserved_predecessor'
)
& 'C:\Python314\python.exe' -m pytest -q -rs $nodes
```

Result: **28 passed, 0 skipped, 0 failed**, exit code 0; one pytest-asyncio deprecation warning. The two remaining exact selectors were separately executed:

```powershell
& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_breaker_pause_replays_after_store_restart_and_provider_success_does_not_close_it
```

Result: **1 passed**, exit code 0; one deprecation warning.

```powershell
& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_operation_recovery.py::test_completed_override_action_id_with_changed_valid_signed_record_rejected_after_restart
```

Result: **1 passed**, exit code 0; one deprecation warning.

Across these three independent invocations: **30 passed, 0 skipped, 0 failed**. This is a sum of disjoint selected node IDs for this exact frozen head only, not a project-wide E7 total.

| E7 requirement slice | State | Evidence / exact boundary | Remaining acceptance |
|---|---|---|---|
| Lifecycle transition table, including START/STOP/ROLLBACK/cleanup/resume pairs | **PASS, source fixture** | `test_lifecycle_transition_table_rejects_unlisted_pairs` tests each defined pair and rejects an unlisted pair. `test_restart_resumes_the_correct_cleanup_phase_after_reconciliation[stop/rollback]` exercises simulated temp-SQL callback recovery and confirms primary action is not repeated. No worker is stopped or restarted. | Does not prove actual worker STOP, process cleanup or crash recovery. |
| Breaker pause, open-breaker refusal, valid operator override and stale override | **PASS, synthetic operator-key/temp-SQL fixtures** | Active-episode signature, tampered/unsigned/APPROVE, wrong episode/config, valid override, later-episode stale reuse, replayed paused state and provider-success-not-closing-pause all have positive/negative assertions. | No production operator key or service. |
| Concurrent starts and stale cached supervisor | **PASS, temporary SQLite and in-process thread fixtures** | A concurrent callback test proves only one supervisor callback runs; another test rechecks a cached supervisor after peer opens the persisted breaker. | Does not cover multiple host processes or systemd workers. |
| External operation kind/key intent, ambiguity and replay | **PASS, temp SQLite and injected callback fixture** | Intent and completion are transactionally separated around callback; timeout records PENDING/UNKNOWN; changed same-key payload is rejected; exact same-key payload retries and replays one completion. | Real remote provider ambiguity and provider-side idempotency are NOT_RUN. The exact selected operation test does not exercise a process crash between callback and completion. |
| Runner claim/reservation and signed resolution boundaries | **PASS, deterministic Store fixtures** | Stale/expired/epoch-fenced authority and one-time reserve; predecessor states block successor gates; authorized `EFFECTS_RESOLVED` path; signed record tampering, resolution-ID collision and authority change all exercise fail-closed boundaries. | These are temporary Store state predicates, not real worker claims or recovery. |
| E7 full denominator | **PARTIAL** | The original matrix also calls for every operation kind/key, breaker/provider replay, ambiguous callback recovery, STOP/rollback, concurrent starts, and stale/invalid operator resolution. The cases above now cover source fixtures for each named class, while dispatch Store/owner/latch selectors are in the previous supplement. | Exact original-selector reconciliation remains Codex-owned. Actual process/worker lifecycle, real provider, runtime services and all non-selected selector variants are not established by these focused cases. |

### Current identities

Frozen product HEAD remained `67d1d55e5556c6936516f3404202faecba1e6707`. Product source files did not change during this supplement. Test file hashes at execution:

| Test file | SHA-256 |
|---|---|
| `tests/vst/test_s2_runner_lifecycle.py` | `f4abf50c7558fd7fde805a95ee33e1e9be7e7a185e00ee5f74b621cd601a1d9d` |
| `tests/vst/test_s2_operation_recovery.py` | `a3b865c8d8024e337bec2199b0d67cbc359d98ae8ed9f1fbdf29c1fef7659107` |
| `tests/vst/test_s2_persistent_runner_service.py` | `2d8b8c8f061c67ead0c022f44e7334e1d6bdebc90f5e1cdc01745ff81f6218d6` |

Remaining E7 `NOT_RUN` classes are specifically real process/worker kill or cleanup, actual process crash/restart, real worker STOP/rollback, production or remote provider execution, service activation, and mutation testing; they are prohibited or outside the accepted source-only fixture scope. The mocked/in-process lifecycle rows above must not be cited as runtime proof. Any source selector not listed in the exact commands remains unexecuted, not implicitly passed.

### Additional simulated callback and seeded-history predicates

Two more existing lifecycle selectors were reviewed and run because they use only injected in-process callbacks and disposable SQLite, without launching or killing a worker process:

```powershell
$nodes = @(
 'tests/vst/test_s2_runner_lifecycle.py::test_failed_start_side_effect_blocks_restart_until_verified_reconciliation',
 'tests/vst/test_s2_runner_lifecycle.py::test_replay_keeps_invalid_legacy_reconciliation_unresolved'
)
& 'C:\Python314\python.exe' -m pytest -q -rs $nodes
```

Result: **2 passed, 0 skipped, 0 failed**, exit code 0; one pytest-asyncio deprecation warning. The first fixture models an uncertain callback side effect, closes and reopens only its temporary Store, and requires signed reconciliation before another start. The second seeds one malformed legacy control event in a disposable Store and verifies it remains unresolved after reopening. Neither is process-crash evidence.

Thus the supplementary E7 lifecycle group consists of the earlier 19-node selection (**28 passed**) plus the two individual selectors (**1 + 1 passed**) and this two-node selection (**2 passed**): **32 passed, 0 skipped, 0 failed** across four exact invocations. No totals are combined with the separate Store/latch/transport or assignment/issuer runs.

### Local bare-remote idempotency and injected Git timeout selectors

Root authorized two additional existing Git-backend tests after body inspection. The first creates a bare remote under pytest `tmp_path`, pushes only to that local filesystem path, and uses the in-module `Backend.open_pull_request` fake; it performs no network request or real PR-provider call. The second also creates a temporary local bare remote. Its timeout injection monkeypatch raises `TimeoutExpired` before the first `Popen` can create the selected `pack-objects` child; the retry runs local Git commands that complete normally. No process is killed or left running. Both remain fixture-level source evidence, not remote-provider or process-crash evidence.

Exact commands and results:

```powershell
& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_idempotent_push_and_pull_request_use_local_bare_remote
```

**1 passed, 0 skipped, 0 failed**, exit code 0; one pytest-asyncio deprecation warning.

```powershell
& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_local_git_timeout_leaves_pending_then_restart_retry_completes_same_key
```

**1 passed, 0 skipped, 0 failed**, exit code 0; one pytest-asyncio deprecation warning. Classification: synthetic timeout before child creation, temporary Store close/reopen, local Git retry; no actual process kill or crash.

With these two disjoint selectors, the lifecycle supplement is **34 passed, 0 skipped, 0 failed** across six exact invocations. This count remains separate from Pub/Sub/latch/transport and assignment/issuer runs. Actual remote provider/PR behavior and real child timeout termination remain `NOT_RUN`.
