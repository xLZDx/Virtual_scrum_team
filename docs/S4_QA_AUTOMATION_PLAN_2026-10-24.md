# Sprint S4 plan: reproducible QA automation

Status: **S4 IMPLEMENTED; PLATFORM MATRIX INCONCLUSIVE/FAIL; ACCEPTANCE OPEN.** At candidate `05b18450176109aafc108020bc2fafb7136a43d6`, exact-head Windows and WSL reports and the 15-reference matrix are recorded in change 0308. The matrix is non-approving because 52 explicit policy selectors remain `NOT_RUN`. The operator authorized one narrow WSL runner-to-worker identity-boundary helper and one report-bound test. Helper source and installer are committed in change 0310; installation and runtime proof remain pending. A correlated GPT-PM review at `3b8d80ff5456192c2419d9515b47fb843939ee16` rejected the candidate with two MAJOR findings. The dependency-content remediation is committed in change 0313; report-bound runtime proof remains pending (design and finding record 0311). This authorization does not lift existing process-kill, timeout, process-death, mutation, or E8 policy exclusions. CI, mutation runs, seeded product-code defects, and external service calls remain prohibited; the bounded synthetic seeded-failure fixtures in AC-12 are distinct from those prohibited activities.

Continuation note (2026-10-26): the three synthetic seeded-failure fixtures passed 3/3 on Windows and 3/3 on WSL at historical candidate `05b1845` (VST-036). That evidence does not establish the later `ece6065` candidate: `tools/qa/run.py` and `docs/qa/categories.json` changed after `05b1845`. The report-bound runner now requires a trusted external wheelhouse; the only checked named path is an installed dependency target, not a wheelhouse (change 0328). Keep seeded-failure rows distinct from policy-excluded mutation/process-death selectors and refresh their exact-head report once the wheelhouse prerequisite is available.

Latest autonomous continuation (2026-10-26; supersedes earlier continuation notes below): At exact candidate `621ddc01d1b5bbf701ccced7bb073c26e89c8c07`, report-bound Windows seeded-failure passed 3/3, WSL seeded-failure passed 3/3, and WSL AC-16 identity passed 1/1; all used the refreshed registry SHA `7b03dd4a…a4f2dd7a` and verified dependency contents before/after. The full allowed Windows regression at code-identical candidate `bdc8e3be7d74ca20a380ecade6acd4e277e9c4dd` passed 897/897 expected selector IDs (1,845 concrete cases) with zero failures; report result remains `INCONCLUSIVE` because 53 policy selectors are `NOT_RUN`. This count is the previous 52 plus the explicitly excluded timeout-cleanup selector. AC-17's pre/post content and persistent-mutation checks have runtime evidence, but same-identity in-run change-and-restore remains `NOT_VERIFIED`, as required by the report contract. The exact-head helper was rebuilt/installed through the previously authorized immutable installer and the prior helper was preserved with setuid disabled. Fresh exact S4 code/security reviews found no BLOCKER/MAJOR; exact-head GPT-PM gate remains pending. S2 Phase 8 is NOT APPROVED; S3 acquisition/execution remain NOT APPROVED; S5 remains blocked on S2/S4 and AEVE provenance. See `docs/sdlc/evidence/s4-windows-regression-report-bound-bdc8e3be-20261026.md` and `docs/sdlc/evidence/s4-report-bound-targeted-621ddc01-20261026.md`.
Latest autonomous continuation (2026-10-26): a trusted six-wheel wheelhouse and Ubuntu 24.04 compiler toolchain are provisioned as recorded in `docs/sdlc/evidence/s4-prerequisite-provisioning-20261026.md`. The WSL-only AC-16 identity test's AF_UNIX fixture path was shortened in change 0352 after a report-bound failure showed `OSError: AF_UNIX path too long`; the assertions were unchanged. Registry change 0353 binds test source `96c9c1556e0bd7d7731bbfba40806c4d1e209907` (SHA-256 `9d232d33…e3601b70`). At exact report-bound candidate `4fe150326a36faf401b045cfa1b9a2e64d89436b`, AC-16 identity passed 1/1 (`s4-identity-20261026-r3`), the three permitted AC-12 seeded-failure selectors passed 3/3 (`s4-seeded-failure-20261026-r4`), and locked dependency contents matched before and after execution. AC-17 in-run mutation/change-and-restore integrity remains `NOT_VERIFIED`, per contract. The 52 policy selectors remain `NOT_RUN`; the broad platform matrix and GPT-PM exact-head gate remain open.

Follow-up (2026-10-26): the designated functional-test reviewer added four focused assertions in change 0347 for singleton membership, regression exclusion, WSL-only matrix binding and fixed identity artifact paths. Change 0348 regenerated the registry at test source HEAD `4d4341e`; it contains 905 runnable regression selectors plus 52 policy `NOT_RUN` selectors. All four assertions passed at exact repository HEAD `f3677a9` (change 0350). The pre-existing untracked S2 artifact was left untouched; the report-bound runner used a clean committed candidate snapshot and preserved that artifact in the canonical checkout. Report-bound AC-16 and the three permitted seeded-failure selectors now have exact candidate-head results documented above.

Sources: `docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md` section 1; `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`; `governance/DEFINITION_OF_DONE.md`; S2 and S3 plans; current `tests/vst/`, `tools/vst/runner.py`, `tools/vst/slice.py`, and `tools/vst/{contracts,gate,store}.py`.

## Goal and scope

Wire reproducible, category-specific native test runs for the repository's functional, integration, Python API, end-to-end, worker-identity, regression, and seeded-failure scenarios, with exact test-ID accounting and machine-readable artifacts; any skipped or uncollected required test makes the result non-approving.

The repository currently has Python tests under `tests/vst/`, using both pytest-style tests and unittest-compatible tests. Existing S2 modules exercise VST contracts, gate, runner, store, lifecycle, and sandbox-probe interfaces. This plan treats the Python module boundary as the API surface: no HTTP or other network service is evidenced in the current repository. If S3 adds a transport API, it must be separately identified and covered; no HTTP API is presumed here.

Out of scope: CI or release pipelines; mutation testing; red/green cycles that alter product code; live service, customer, production, or external API calls; test execution in the planning phase; accepting skips as satisfied coverage; silently replacing an unavailable test category with an unrelated suite. ADR-0001 remains binding: only `functional-test-reviewer` and `e2e-runner` author and execute required tests.

## Current evidence and constraints

- `tests/vst/` contains the S1 contract, gate, store, runner, process-death, and slice tests, plus the five S2 acceptance modules. The current discovery evidence is source-path inspection only; this plan makes no runtime claim.
- `tools/vst/slice.py` provides a synthetic, local vertical-slice harness. `tools/vst/runner.py` executes allowlisted local commands and captures bounded command evidence. They are possible integration points, not yet QA category runners.
- ADR-0001 forbids CI and mutation runs and requires exact-head agent-run evidence. Its permitted synthetic known-defect fixtures may demonstrate a falsifying oracle without mutating product code.
- The committed category/test-ID registry is `docs/qa/categories.json`; its generator is `tools/qa/build_registry.py`. The runner and lock are committed under `tools/qa/`. The environment reports CPython 3.14.3; the existing pytest 8.4.2 is not selected because the official PyPI record documents a UNIX temporary-directory vulnerability fixed in 9.0.3. S4 pins pytest 9.0.3 and its runtime dependencies with wheel hashes in `tools/qa/requirements.lock`; an isolated external target is prepared, and dependency installation remains separate from test execution.
- S3 adapter artifacts and test paths now exist in `tools/vst/worker_adapter.py`, `tools/vst/pilot.py`, `tests/vst/test_s3_worker_adapter.py`, and `tests/vst/test_s3_worker_pilot_e2e.py`. Full S3 candidate/sandbox acceptance is still incomplete. S4 includes committed S3 test selectors in its regression denominator, but sandbox/candidate-dependent claims remain `NOT_RUN` until their dependencies pass.

## Stories and acceptance criteria

### E1 — Category and test-ID contract

**S4.1.1** Define the supported categories (`functional`, `integration`, `api`, `e2e`, `identity`, `regression`, `seeded-failure`), their test-owner roles, exact source paths/selectors, required test-ID inventory, applicable environment, and category-level denominator.

**AC-1:** Every required test ID resolves to a committed test and exactly one `primary_category` among `functional`, `integration`, `api`, `e2e`, `identity`, or `seeded-failure`; duplicate, missing, unknown, or unassigned IDs are rejected before a run can produce an accepting result. `identity` is a singleton WSL-only category for the authorized AC-16 selector. `regression` is an aggregate run manifest, not a primary category: it references the union of the accepted functional, integration, API, and E2E test IDs while preserving each ID's single primary category and source-commit provenance; the isolated `identity` selector is not duplicated into that aggregate.

**AC-2:** Each category has a real native invocation. `api` covers the documented Python API of `tools.vst`; a network API is marked unsupported unless the product adds one and records its route contract.

**AC-3:** The category registry is bound to its content hash and candidate HEAD; stale registry or candidate HEAD cannot produce current evidence.

### E2 — Reproducible environment and native runner

**S4.2.1** Establish a repository-owned, hash-pinned QA wheel input compatible with the strict Windows CPython 3.14.3 and POSIX CPython 3.12.3 runtime profiles. Prepare a fresh isolated external target from an already-present wheelhouse and verify the target content against the locked wheel bytes before and after each run.

**S4.2.2** Implement one bounded runner entry point that launches pytest's native discovery/execution for the requested category, preserving existing unittest discovery. It records argv, exit code, duration, stdout/stderr references, environment identity, expected and collected IDs, and output artifact digests.

**S4.2.3** Add a fixed-identity helper used by one report-bound WSL `identity` selector. A child launched by `vst-runner` UID/GID 997:988 must run only as `vst-worker` UID/GID 999:989 with supplementary groups cleared. The helper accepts no arbitrary target identity or executable and does not replace the QA runner's process or artifact ownership. The test verifies the child identity and denial of runner-owned file/socket sentinels. Contract and constraints: `docs/S4_WSL_WORKER_UID_HELPER_DESIGN.md`.

**S4.2.4** Before any pytest child starts, bind the isolated dependency target's executable Python files to the exact hash-pinned wheel inputs; report the verified dependency-content digest and recheck the target after execution. The runner must remain offline and must not install, download, or repair dependencies. Contract: `docs/S4_QA_DEPENDENCY_PROVENANCE_DESIGN.md`.

**AC-4:** Running the same committed category manifest under the same platform profile and dependency lock yields the same selected test-ID set; the platform matrix binds each profile report to the exact candidate, registry and selected wheel hashes, and artifact timestamps may differ but are excluded from normalized content hashes.

**AC-5:** A missing interpreter, locked wheel, exact dependency target file, category selector, artifact, or test ID produces a typed non-approving result with a cause; no fallback interpreter or empty-success result is allowed.

**AC-6:** The runner does not install or download dependencies during a test run. `tools/qa/prepare_dependencies.py` may create a new external target only from an already-present wheelhouse whose exact wheel hashes match the committed lock; it performs no network access and never overlays a target.

### E3 — Functional and Python API lanes

**S4.3.1** Define and run functional test subsets for contract validation and verdict behavior using native pytest selection.

**S4.3.2** Define and run Python API contract scenarios over public entry points in `tools/vst/contracts.py`, `gate.py`, `store.py`, `runner.py`, and `supervisor.py`, with local temporary state only.

**AC-7:** Each lane exercises valid and invalid inputs, stale HEAD/evidence and signature failures where applicable; every required ID appears exactly once in the execution record.

**AC-8:** API scope is truthful: direct Python APIs are supported; absent HTTP routes are recorded as `UNSUPPORTED` with repository evidence, and cannot be reported as tested.

### E4 — Integration and end-to-end lanes

**S4.4.1** Define integration selections that cross the real store, signer/runner, gate and local synthetic repository boundaries.

**S4.4.2** Define E2E selections that run the synthetic VST vertical slice and S3 worker adapter through real local boundaries after S3 acceptance exists.

**AC-9:** Integration/E2E use isolated temporary directories and local synthetic repositories/remotes; they make no external network or production writes.

**AC-10:** Missing S3 adapter or sandbox-dependent capability remains `NOT_RUN` or `UNSUPPORTED` with an exact dependency and is never omitted from the denominator.

### E5 — Regression and seeded-failure evidence

**S4.5.1** Define regression as an aggregate manifest containing the explicit union of accepted functional, integration, API and E2E IDs for the current HEAD, with each ID retaining its unique `primary_category` and source-commit provenance. The aggregate does not reassign IDs to a second primary category.

**S4.5.2** Add a bounded synthetic fixture catalog for known failure classes (for example stale HEAD, missing required receipt, invalid signature, out-of-scope diff, skipped required ID, artifact digest mismatch). Each fixture supplies a controlled input record to the unchanged product interface and the expected non-approving outcome; it does not patch, monkeypatch, or rewrite product source.

**AC-11:** The regression matrix reports every required ID exactly once on each profile assigned to it and fails on any missing, duplicate, skipped, xfailed, unexpected, or uncollected assigned ID. The union of passing assigned IDs must equal the full committed regression denominator; a platform skip is never a pass.

**AC-12:** Each seeded-failure fixture is itself a test with a committed fixture ID, input hash, expected rejection, observed rejection and test ID. No actual failing product test is relabeled as an expected seed; no product code is modified to inject a defect.

**AC-13:** Mutation testing and red/green loops remain `NOT_RUN` under ADR-0001. Seeded fixtures do not claim mutation score or prove every defect class.

### E6 — Evidence envelope and gate compatibility

**S4.6.1** Serialize a machine-readable report for each category with schema version, candidate HEAD, dirty-tree state, category-manifest hash, expected/collected/executed/skipped/xfail/unexpected IDs, interpreter and dependency-lock hash, command/exit status, artifact digests, and typed result.

**AC-14:** `APPROVE` is impossible if any assigned required ID is missing, skipped, or `NOT_RUN`, if evidence is stale or hash-invalid, or if a category is unsupported. Matrix approval requires every ID to pass on every explicitly assigned profile; operator waiver behavior remains governed only by ADR-0001 and the authoritative VST gate.

**AC-15:** Evidence artifacts are reproducible and contain no secrets, user-specific absolute paths, tokens, or unrestricted environment values. Environment variable names may be reported only under the existing privacy contract.

**AC-16:** The report-bound identity selector passes on the WSL UID-997 profile using the installed root-owned helper at its fixed path. The helper accepts only caller UID/GID 997:988, drops to UID/GID 999:989, clears supplementary groups and inherited descriptors, enables `no_new_privs`, uses the fixed interpreter without a shell, and fails closed on any mismatch. Its embedded candidate/source hashes match the exact report head. The selector observes the child identity and confirms the worker cannot read the runner-owned sentinel file or connect to its runner-only socket. The restricted-root profile remains separate; existing `NOT_RUN` policy exclusions are unchanged.

**AC-17:** Immediately before pytest starts, every file in the external dependency target matches the exact inventory and bytes of a wheel whose SHA-256 is permitted by the committed lock; immediately after pytest exits, the runner recomputes and compares that inventory. Missing, extra, linked, changed, unsupported-layout, or lock-mismatched content produces a typed non-approving result. The report binds selected wheel and pre/post target-content digests without absolute external paths and explicitly reports in-run immutability as `NOT_VERIFIED`; no claim is made that these snapshots prevent a same-identity change-and-restore while pytest is running. The runner performs no network access or installation.

## Requirements-to-test map and denominator

| Requirement | ACs | Required falsifying scenario / oracle | Layer | State/dependency |
|---|---|---|---|---|
| Native category selection | AC-1, AC-2 | Unknown category, overlapping ID, unknown ID, missing test path -> runner refuses an accepting report | Runner contract | Planned; category registry is new |
| Exact test accounting | AC-1, AC-11 | Required ID absent, duplicate ID, collection mismatch, skipped or xfailed required ID -> non-approval | Runner integration | Planned |
| Reproducible environment | AC-4..6 | Wrong Python, missing locked dependency, changed lock hash, missing artifact -> typed failure; runner performs no install/download | Runner/environment integration | Dependency: establish lock format and pinned tool set in E1/E2 |
| Functional contracts | AC-7 | Valid and invalid contract/gate inputs, including stale evidence and signature failures -> expected verdict | Functional | S2 tests exist; S3 additions are future inputs |
| Python API | AC-2, AC-8 | Public API accepts valid request and rejects malformed/stale request; nonexistent HTTP route is explicitly unsupported | API contract | Python API exists; transport API UNKNOWN/absent in current paths |
| Integration boundaries | AC-9 | Real local store/gate/runner flow with temp state; corrupted signature/chain/receipt fails closed | Integration | S2 modules exist; S3 dependency only for worker adapter |
| E2E journey | AC-9, AC-10 | Synthetic story run through control plane and adapter; missing sandbox/adapter remains NOT_RUN | E2E | S3 and operator sandbox evidence may be required |
| Regression denominator | AC-11 | Delete, duplicate, skip or xfail one registered test ID -> non-approving report | Aggregate regression run over primary-category IDs | Depends on all prior category IDs |
| Seeded failure | AC-12, AC-13 | Each unchanged-product synthetic negative fixture triggers its documented rejection; fixture mismatch cannot pass | Seeded-failure | Fixture catalog is new; no mutation or source patch |
| Evidence integrity | AC-3, AC-14, AC-15 | Alter report/hash or replay against another HEAD -> gate rejects; reports contain no secret values | Evidence/gate integration | Requires report schema and authoritative gate binding |
| WSL worker identity | AC-16 | Caller other than 997:988, helper with changed owner/mode, extra groups, wrong UID/GID, readable runner sentinel, or connectable runner-only socket -> selector fails | Report-bound WSL `identity` selector | Helper implementation exists; compiler/wheelhouse prerequisites are provisioned; exact-head helper installation and runtime evidence remain pending |
| Dependency content provenance | AC-4..6, AC-17 | Same-version package file changed, wheel/lock mismatch, added importable target file, or target mutated during pytest -> typed non-approval | Runner/environment integration | GPT-PM MAJOR at exact head `3b8d80f`; design in change 0311, implementation and test evidence pending |

**Denominator rule:** At sprint start, freeze a committed registry containing every test ID and one `primary_category`, including `UNSUPPORTED` and `NOT_RUN` rows with reasons. The regression manifest is a separate aggregate reference to the required functional, integration, API, and E2E IDs; it does not create duplicate primary-category assignments. Per-primary-category and regression reports must account for 100% of their applicable registry or aggregate manifest. No percentage or category-level PASS can hide an unaccounted ID. Recompute and review the inventory when tests are added or removed; bind it to the exact source HEAD and registry hash.

## Evidence record

Each run appends one JSON Lines envelope and output chunks to fixed per-category artifacts containing:

- sprint, category, run id, category report schema version 3, exact repository HEAD, branch, dirty flag and changed-path list;
- category-registry version/hash, expected, collected, executed, skipped, xfailed, failed, unexpected and uncollected test IDs;
- normalized selected wheel hashes and pre/post dependency-target content digests with verification state;
- exact argv, working-directory-relative selector, exit code, start/end/duration, interpreter path/version, OS/runtime identity, pytest version and lockfile hash;
- output artifact relative paths, exact per-run stdout/stderr byte ranges, byte sizes, and SHA-256 chunk digests; the normalized semantic digest excludes nondeterministic wall-clock fields, raw output size/hash metadata, and prior append-only history, while each exact per-run output hash and size is still verified against its captured byte range;
- per-fixture seeded-failure ID, input digest, expected/observed verdict and linked test ID, where applicable;
- result: `PASS`, `FAIL`, `NOT_RUN`, `UNSUPPORTED`, `INCONCLUSIVE` or `BLOCKED`, with reason and dependency; no implicit conversion between states.

Exact commands are formed from committed category selectors. The implemented interface is:

```text
C:\Python314\python.exe -m tools.qa.run --category <category> --repo-root <candidate-repo> --dependency-target <isolated-external-target> --dependency-wheelhouse <external-wheelhouse> --scratch-root <external-scratch-root> --run-id <unique-id> --report-path docs/sdlc/evidence/qa/<category>.report.jsonl --stdout-path docs/sdlc/evidence/qa/<category>.stdout.txt --stderr-path docs/sdlc/evidence/qa/<category>.stderr.txt
```

`tools.qa.run` is implemented and delegates to pytest's native CLI. It captures collection and runtime output without claiming that collection alone is a pass. The category arguments and output paths are exact; a VST caller must allowlist the exact three paths for that invocation. Test files and fixtures are authored but require committed registry regeneration before any run. Runtime category evidence remains `NOT_RUN`.

## Definition of Ready

- S2 exact-head acceptance and S3 worker adapter scope are reconciled; all dependent or unavailable capabilities are explicit.
- Category owners, source paths, selectors, test-ID inventory and denominator are agreed from repository artifacts.
- Existing pinned interpreter and test dependency inventory are recorded; the lock format is selected based on reproducibility and approved repository constraints.
- Evidence schema and gate-binding interface are specified; a report cannot be treated as a receipt until the authoritative gate validates it.
- Functional and E2E test agents own the required test map; only those roles will author or execute required QA tests.
- New expected-failure fixtures use controlled synthetic input records, have a stable version/hash and invoke unchanged product code.

## Definition of Done

1. All six categories have an implemented native runner or a truthful `UNSUPPORTED` row backed by repository evidence; API means Python API unless a real transport API is added.
2. Functional, integration, Python API, E2E, regression and seeded-failure tests run from committed category manifests using the pinned interpreter and lock, with reproducible artifacts linked from exact-head evidence.
3. Complete per-epic test sets run after each epic and once again on the exact final committed head by `functional-test-reviewer` and `e2e-runner`; exact commands, test IDs, environment, counts, HEAD, dirty note and outputs are retained.
4. Every expected test ID is accounted for. Any skipped, xfailed, missing, duplicate, unexpected or uncollected required ID blocks ordinary approval and cannot satisfy DoD.
5. Seeded fixtures reject their named negative inputs through unmodified product contracts; no mutation-testing result or red/green product-source loop is claimed.
6. `NOT_RUN`, `UNSUPPORTED`, `INCONCLUSIVE` and `BLOCKED` remain explicit and non-approving absent the signed, scoped waiver defined by ADR-0001.
7. Relevant specialist reviews reach evidence-based consensus on the exact head, all valid BLOCKER/MAJOR findings are resolved and affected tests rerun, then GPT-PM approves that exact head before push/one PR.
8. Change records, decision/lessons logs, backlog, state, registry and bilingual S4 sprint report are updated under the repository workflow.

## Ownership and proposed backlog

The operator is accountable task owner under the delegated continuation; Codex coordinates implementation. Canonical technical service owners for the QA runner, lock maintenance, and test-category ownership are not identified in current project records (`core/BACKLOG.md` and team roster do not assign them); these remain `UNKNOWN`, not invented. `functional-test-reviewer` and `e2e-runner` are accountable roles for required test authorship/execution, not named people. `implementation-engineer` executes production-code changes.

| Proposed item | Scope | Accountable / executor | Dependency |
|---|---|---|---|
| S4-A / VST-032 | Category manifest, test-ID registry and denominator | Operator accountable; implementation-engineer executes; technical service owner UNKNOWN | S3 story list and repository test inventory |
| S4-B / VST-033 | Pinned test environment and bounded native runner | Operator accountable; implementation-engineer executes; lock maintenance owner UNKNOWN | S4-A, pinned Python |
| S4-C / VST-034 | Functional, integration and Python API selectors | Operator accountable; test-agent roles author/run; technical owner UNKNOWN | S4-A/B |
| S4-D / VST-035 | E2E and regression selectors | Operator accountable; test-agent roles author/run; technical owner UNKNOWN | S3 acceptance and S4-A/B |
| S4-E / VST-036 | Synthetic seeded-failure fixture catalog | Operator accountable; test-agent roles author/run; fixture service owner UNKNOWN | S4-A, ADR-0001 constraints |
| S4-F / VST-037 | Evidence envelope, hashes and no-skip gate integration | Operator accountable; implementation-engineer executes; technical gate owner UNKNOWN | S4-B through E; current VST gate contract |

VST-032–037 are registered in the canonical backlog as the six S4 implementation and evidence items.

## POSIX runtime matrix addendum — 2026-10-25

The original S4.2.1 contract named only Windows CPython 3.14.3, while the committed denominator
contains POSIX-only selectors and acceptance forbids satisfying them by skipping. Windows evidence
at `fd49fad` cannot execute those selectors. Under the operator's prior authorization to provision
and use the dedicated Ubuntu-24.04 WSL2 environment, the runtime contract is extended with an
explicit POSIX CPython 3.12.3 profile. This is a platform-coverage clarification, not a skip waiver:
selectors must pass on each profile assigned to them, and all assigned profile reports must agree
on the same candidate, registry and lock. See `docs/sdlc/S4_POSIX_RUNTIME_MATRIX_DESIGN.md` and
change 0272. The POSIX profiles are not accepted until the matrix code is committed and tested, the
pinned dependency target is prepared, exact-head execution completes, and matrix verification
succeeds. The implementation adds an unprivileged UID-997 profile and a separate restricted root
harness for two identity-isolation selectors. The candidate must be copied beneath WSL's
distro-local `/tmp/vst-s4-candidate`; Windows-drive `drvfs` sources and `drvfs`/`9p` mounts covering
the candidate are rejected, while unrelated WSL `9p` mounts are allowed. The runner records the
candidate path and mount-table hash. The root proof is local QA evidence only and does not replace
the S2 sandbox receipt. The runner also requires a private root-profile namespace with no
non-loopback interface and a passing local loopback canary. Current registry accounting retains 51
selectors as policy `NOT_RUN`, so passing every runnable profile row alone cannot approve full S4
acceptance.

## Ordered work and safe stopping points

1. Reconcile the S3 accepted adapter interfaces and enumerate the S4 denominator; stop safely after E1 if an interface or test ID remains unavailable, with unknowns recorded rather than guessed.
2. Implement and commit the locked Windows/POSIX runtime profiles, runner, platform assignments, matrix validator, and evidence schema; verify each new seam with its own focused local contract proof after all S4 coding is complete.
3. Add category manifests and synthetic fixtures; connect all six category selectors to native execution.
4. Complete all S4 code before test phase; only then test agents author/run the per-epic and final exact-head suites.
5. Run relevant reviewers, resolve valid findings, request the exact-head GPT-PM gate, then push and merge one S4 PR only after approval.

The first independently safe implementation point was after E1, with the S3 dependency map and denominator frozen. Total gates: **6**, one per epic above. The new POSIX matrix code and regenerated category registry are currently uncommitted. Focused contract tests and exact-head runtime execution remain next after coding is complete. E2E rows that require incomplete S2/S3 external acceptance stay in the denominator as `NOT_RUN` and cannot satisfy DoD.

## Unknowns to resolve at S4 start

- Pytest 9.0.3 and its runtime dependency set are selected from the pinned interpreter's current inventory and official exact-release metadata. Wheel hashes and the isolated install procedure are recorded in `tools/qa/requirements.lock` and `docs/QA_RUNNER_DESIGN.md`.
- Whether S3 adds a transport API: current S3 artifacts expose an in-repository Python adapter and no network route is established; report Python API only and mark transport API unsupported.
- The canonical service owner for category registry, runner, and evidence gate: no owner is established in the inspected repository sources; preserve `UNKNOWN` and proceed with role-based execution.
- Which S3 test IDs belong in the regression denominator: derive from committed test files and exact-head test records when S3 is accepted.

The selector accounting contract is recorded in `docs/QA_RUNNER_DESIGN.md`: function-level registry
selectors map to all concrete pytest cases; reports retain case-level outcomes, and a selector-level
pass is emitted only when every concrete case passes. This preserves VST's current TestRun receipt
contract and prevents parameterized case fan-out from being mistaken for missing or unexpected tests.
