# Sprint S4 plan: reproducible QA automation

Status: **The last completed exact-head evidence is change 0261 at source/test HEAD `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`: 15 focused selectors passed and synthetic outer functional CLI accounted for 33/33 IDs with PASS QA report, TestRun receipt, and manifest diff gate. E2E and regression selector denominators are COMPLETE under the outer-run contract below; that is coverage inventory status, not runtime acceptance. Exact-head outer CLI runs for functional, integration, API, E2E, seeded-failure, and regression are pending on the updated contract head. The signer remains synthetic; deployed signer, authoritative VST gate consumption, sandbox deployment, and exact-head GPT-PM approval remain separate open gates.**

The path-confinement MINOR was resolved in 0137 and the source parser was bounded in 0142. The focused registry suite then failed twice at test HEAD `64b8bb1` (14 passed, 1 skipped, 1 failed each run): a separate bounded `git cat-file` query returned false for valid provenance SHAs, which direct Git queries later confirmed existed. Change 0146 removes that redundant live query; full lowercase-SHA syntax remains checked, and the bounded ancestry query now supplies the single existence/history proof. The code reviewer reported the earlier source-read MINOR; the security reviewer reported no finding. The corrected committed-registry module passed at `56a58a7` (15 passed, 1 skipped, 0 failed) in the exact-head functional rerun recorded by change 0149; symlink runtime remains `NOT_RUN` on Windows.

## Current S4 status — 2026-10-25, latest completed runtime evidence at `bc32f6fa6c9ae864dc897b252ffa9cef6fc4fd5c`

This section supersedes older statements below that the report-bound functional path was wholly `NOT_RUN`. At exact source/test HEAD `bc32f6f`, 15 focused worker/signer-path/parser/ACL selectors passed, and synthetic outer `tools.qa.run` functional invocation accounted for 33/33 IDs with PASS report, TestRun receipt, and diff gate. Evidence is change 0261 and `docs/sdlc/evidence/s4-source-acl-preflight-runtime-bc32f6f.md`; test agent was `e2e-runner` (GPT-6 Luna, medium). The signer was ephemeral and in-process. E2E and regression denominators are now COMPLETE because all required selectors are committed and mapped: the report-bound boundary is the outer category CLI, which runs mapped selectors under worker identity and then binds report, receipt, and gate evidence. Selectors must not recursively invoke `tools.qa.run` or regain runner privileges. Exact-head outer CLI execution of all six categories is pending. This does not establish trusted deployed-signer acceptance, authoritative VST gate consumption, or sandbox deployment.

Sources: `docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md` section 1; `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`; `governance/DEFINITION_OF_DONE.md`; S2 and S3 plans; current `tests/vst/`, `tools/vst/runner.py`, `tools/vst/slice.py`, and `tools/vst/{contracts,gate,store}.py`.

## Goal and scope

Wire reproducible, category-specific native test runs for the repository's functional, integration, Python API, end-to-end, regression, and seeded-failure scenarios, with exact test-ID accounting and machine-readable artifacts; any skipped or uncollected required test makes the result non-approving.

The repository currently has Python tests under `tests/vst/`, using both pytest-style tests and unittest-compatible tests. Existing S2 modules exercise VST contracts, gate, runner, store, lifecycle, and sandbox-probe interfaces. This plan treats the Python module boundary as the API surface: no HTTP or other network service is evidenced in the current repository. If S3 adds a transport API, it must be separately identified and covered; no HTTP API is presumed here.

Out of scope: CI or release pipelines; mutation testing; red/green cycles that alter product code; live service, customer, production, or external API calls; test execution in the planning phase; accepting skips as satisfied coverage; silently replacing an unavailable test category with an unrelated suite. ADR-0001 remains binding: only `functional-test-reviewer` and `e2e-runner` author and execute required tests.

## Current evidence and constraints

- The committed registry at `docs/qa/categories.json` maps functional (33), integration (6), Python API (73), seeded-failure (7), and E2E (12) selectors. Change 0261 records 33/33 functional outer-run IDs at `bc32f6f` with synthetic signer. E2E and regression coverage denominators are COMPLETE under the outer-run contract; exact-head runs of all six categories remain pending.
- `tools/qa/run.py`, `tools/qa/registry.py`, `tools/qa/wsl_snapshot.py`, `tools/qa/requirements.in`, and `tools/qa/requirements.lock` exist. The bounded WSL runner/worker identities are 997/999; the worker intentionally has no capabilities after the trampoline. The synthetic functional run exercised report serialization but does not establish trusted deployed signer or authoritative gate consumption. E2E outer-run acceptance is pending exact-head runtime, separate from its complete selector denominator. See change 0261.
- The ancestry source fix at `7b8200c` distinguishes Git exit status 1 (non-ancestor) from other verification failures; the functional selector set tests exit 0/1/>1, exhausted timeout, and `OSError`. All five pass at the mapped exact head in 0198.
- `tools/vst/slice.py` provides a synthetic local vertical-slice harness; `tools/vst/runner.py` executes allowlisted local commands and captures bounded command evidence. All 12 mapped E2E selectors passed on Windows at `20fa7bb`, but this does not establish the separate current-head POSIX sandbox gate.
- ADR-0001 remains binding: CI and mutation/red-green runs are `NOT_RUN`; `functional-test-reviewer` and `e2e-runner` own required test authorship/execution. The earlier WSL transfer and seven POSIX selectors are recorded in change 0159 at source HEAD `56dce67`; that run does not establish current-head S4 acceptance.

## Stories and acceptance criteria

### E1 — Category and test-ID contract

**S4.1.1** Define the supported categories (`functional`, `integration`, `api`, `e2e`, `regression`, `seeded-failure`), their test-owner roles, exact source paths/selectors, required test-ID inventory, applicable environment, and category-level denominator.

**AC-1:** Every required test ID resolves to a committed test and exactly one `primary_category` among `functional`, `integration`, `api`, `e2e`, or `seeded-failure`; duplicate, missing, unknown, or unassigned IDs are rejected before a run can produce an accepting result. `regression` is an aggregate run manifest, not a primary category: it references the union of the accepted functional, integration, API, and E2E test IDs while preserving each ID's single primary category and source-commit provenance.

**AC-2:** Each category has a real native invocation. `api` covers the documented Python API of `tools.vst`; a network API is marked unsupported unless the product adds one and records its route contract.

**AC-3:** The category registry is bound to its content hash and candidate HEAD; stale registry or candidate HEAD cannot produce current evidence. Registry and supported-category provenance heads must be ancestors of the candidate, and the v2 receipt binds the actual candidate HEAD.

### E2 — Reproducible environment and native runner

**S4.2.1** Establish a repository-owned, hash-pinned QA dependency input compatible with the verified named `Ubuntu-24.04` WSL interpreter CPython 3.12.3; record relevant OS/runtime/tool versions for each category. This supersedes the plan's stale Windows interpreter pin because the v2 signer runner refuses non-POSIX execution.

**S4.2.2** Implement one bounded runner entry point that launches pytest's native discovery/execution for the requested category, preserving existing unittest discovery. It records argv, exit code, duration, stdout/stderr references, environment identity, expected and collected IDs, and output artifact digests. Disable pytest's cache provider and Python bytecode writes in report-bound runs so the isolated worker does not mutate the read-only source snapshot.

**AC-4:** Running the same committed category manifest with the same interpreter and dependency lock yields the same selected test-ID set; artifact timestamps may differ but are excluded from normalized content hashes.

**AC-5:** A missing/wrong WSL interpreter, dependency, category selector, artifact, or test ID produces a typed non-approving result with a cause; no fallback interpreter or empty-success result is allowed.

**AC-6:** The runner does not install or download dependencies during a test run. Dependency installation, if needed, is an explicit environment-preparation step from the exact lock and isolated target.

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

**S4.5.2** Add a bounded synthetic fixture catalog for known failure classes (for example stale HEAD, missing required receipt, invalid signature, out-of-scope diff, skipped required ID, artifact digest mismatch). Each fixture supplies a controlled input record to the unchanged product interface and the expected non-approving outcome; it does not patch, monkeypatch, or rewrite product source. The catalog binds the canonical input hash, expected rejection, observed rejection, and exactly one committed test ID into the QA report and signed artifact set.

**AC-11:** Regression reports every required ID and fails on any missing, duplicate, skipped, xfailed, unexpected, or uncollected ID.

**AC-12:** Each seeded-failure fixture is itself a test with a committed fixture ID, input hash, expected rejection, observed rejection and test ID. No actual failing product test is relabeled as an expected seed; no product code is modified to inject a defect.

**AC-13:** Mutation testing and red/green loops remain `NOT_RUN` under ADR-0001. Seeded fixtures do not claim mutation score or prove every defect class.

### E6 — Evidence envelope and gate compatibility

**S4.6.1** Serialize a machine-readable report for each category with schema version, candidate HEAD, dirty-tree state, category-manifest hash, expected/collected/executed/skipped/xfail/unexpected IDs, interpreter and dependency-lock hash, command/exit status, artifact digests, and typed result.

**AC-14:** `APPROVE` is impossible if required IDs are missing or skipped, if evidence is stale or hash-invalid, or if a category is unsupported or `NOT_RUN`; operator waiver behavior remains governed only by ADR-0001 and the authoritative VST gate.

**AC-15:** Evidence artifacts are reproducible and contain no secrets, user-specific absolute paths, tokens, or unrestricted environment values. Environment variable names may be reported only under the existing privacy contract.

**Evidence-to-gate design resolved:** Committed `docs/qa/categories.json` is the canonical static category/test-ID/selector registry. A run-specific v2 VST task manifest must match its supported projection exactly. The registry, canonical QA report, event record, and bounded stdout/stderr integrity references are predeclared artifacts bound by an ordinary v2 `TestRun` receipt and the exact-head gate. No v1/v2 fields are added; the trusted runner/parser remains responsible for truthful report content. The registry's source HEAD is provenance; each receipt/report separately records the actual candidate HEAD. A valid observed failure remains `FAIL` where v2 derivation supports it; malformed/inconsistent evidence aborts before signing, while zero executed IDs remain `INCONCLUSIVE` under the existing contract. See `docs/S4_QA_RUNNER_TECHNICAL_DESIGN.md` and change records 0093–0094.

## Requirements-to-test map and denominator

| Requirement | ACs | Required falsifying scenario / oracle | Layer | State/dependency |
|---|---|---|---|---|
| Native category selection | AC-1, AC-2 | Unknown category, overlapping ID, unknown ID, missing test path -> runner refuses an accepting report | Runner contract | Planned; category registry is new |
| Exact test accounting | AC-1, AC-11 | Required ID absent, duplicate ID, collection mismatch, skipped or xfailed required ID -> non-approval | Runner integration | Planned |
| Reproducible environment | AC-4..6 | Wrong Python, missing locked dependency, changed lock hash, missing artifact -> typed failure; runner performs no install/download | Runner/environment integration | Dependency: establish lock format and pinned tool set in E1/E2 |
| Functional contracts | AC-7 | Valid and invalid contract/gate inputs, including stale evidence and signature failures -> expected verdict | Functional | S2 tests exist; S3 additions are future inputs |
| Python API | AC-2, AC-8 | Public API accepts valid request and rejects malformed/stale request; nonexistent HTTP route is explicitly unsupported | API contract | Python API exists; transport API UNKNOWN/absent in current paths |
| Integration boundaries | AC-9 | Real local store/gate/runner flow with temp state; corrupted signature/chain/receipt fails closed | Integration | S2 modules exist; S3 dependency only for worker adapter |
| E2E journey | AC-2, AC-9–11, AC-14 | The outer `tools.qa.run --category e2e` is the report-bound boundary: it runs all 12 committed local journey selectors under worker identity, accounts for exact IDs/events, then serializes and binds the v2 report, stream references, manifest diff gate, and TestRun receipt. Selectors exercise local deterministic runner/gate behavior and must not recursively launch `tools.qa.run`. Exact-head outer E2E run is pending; deployed signer, authoritative gate consumption, and sandbox deployment are separate runtime gates. | Outer E2E category run | Selector denominator COMPLETE; exact-head runtime pending; trusted signer/gate/sandbox NOT_RUN |
| Regression denominator | AC-11 | Delete, duplicate, skip or xfail one registered test ID -> non-approving report | Aggregate regression run over primary-category IDs | Depends on all prior category IDs |
| Seeded failure | AC-12, AC-13 | Each unchanged-product synthetic negative fixture triggers its documented rejection; fixture mismatch cannot pass | Seeded-failure | Fixture catalog is new; no mutation or source patch |
| Evidence integrity | AC-3, AC-14, AC-15 | Alter report/hash or replay against another HEAD -> gate rejects; reports contain no secret values | Evidence/gate integration | Requires report schema and authoritative gate binding |

**Denominator rule:** Freeze a committed registry containing every test ID and one `primary_category`, including `UNSUPPORTED` and `NOT_RUN` rows with reasons. The regression manifest is the explicit aggregate union of functional, integration, API, and E2E IDs (currently 124); seeded-failure remains its own primary category and is not included under S4.5.1. Each category's outer `tools.qa.run` invocation is the report-bound layer: it launches mapped selectors as worker, then binds exact accounting, report, streams, diff gate, and receipt. Selectors must not recursively invoke the CLI. Denominator `COMPLETE` means every required ID is committed and mapped; runtime PASS requires a separate exact-head outer run. No category PASS can hide an unaccounted ID. Bind each run to exact source HEAD and registry hash.

## Evidence record

Each run emits an immutable JSON envelope and referenced artifacts containing:

- sprint, category, run id, schema version, exact repository HEAD, branch, dirty flag and changed-path list;
- category-registry version/hash, expected, collected, executed, skipped, xfailed, failed, unexpected and uncollected test IDs;
- exact argv, working-directory-relative selector, exit code, start/end/duration, interpreter path/version, OS/runtime identity, pytest version and lockfile hash;
- output artifact relative paths and SHA-256 digests; normalized summary digest excludes nondeterministic wall-clock fields;
- per-fixture seeded-failure ID, input digest, expected/observed verdict and linked test ID, where applicable;
- result: `PASS`, `FAIL`, `NOT_RUN`, `UNSUPPORTED`, `INCONCLUSIVE` or `BLOCKED`, with reason and dependency; no implicit conversion between states.

Exact commands are formed from committed category selectors; proposed interface:

```text
/usr/bin/python3 -m tools.qa.run --category <category> --manifest <run-specific-vst-v2-manifest> --registry docs/qa/categories.json --signer-socket <trusted-local-socket> ...
```

The fresh bounded source transfer and seven mapped native POSIX pytest selectors passed on WSL2 in run `f3ad62c94bc0429987bc24277103d5b4` at source HEAD `56dce67e508ccf452b2b7b39ed7f33c863081269` (change 0159); that older run does not establish current S4 HEAD. At exact S4 HEAD `1c97ee9`, three focused POSIX symlink selectors passed 3/3 (change 0201). Changes 0189–0190 add five deterministic local fixture selectors for pytest discovery and the v1 runner/gate artifact boundary; they do not exercise v2 signing. All twelve mapped E2E selectors passed together on Windows at `20fa7bb` (0198). At exact source/test HEAD `bc32f6f`, 15 focused selectors and synthetic functional outer report-bound CLI passed; see change 0261. The earlier E2E PARTIAL state reflected an incorrect nested-selector interpretation and is superseded by the outer-run contract above: all 12 E2E selectors are mapped, while exact-head outer E2E runtime remains pending. Trusted signer and authoritative gate were not used. No packages were installed for these recorded runs.

## Definition of Ready

- S2 exact-head acceptance and S3 worker adapter scope are reconciled; all dependent or unavailable capabilities are explicit.
- Category owners, source paths, selectors, test-ID inventory and denominator are agreed from repository artifacts.
- Named WSL runtime inventory is recorded and the SHA-256 dependency lock is committed. The runner verifies versions and lock identity without installation.
- Evidence schema and gate-binding interface are specified in the S4 technical design; report artifacts are not treated as receipts without existing VST v2 signature, exact-head and digest validation.
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

Identifiers VST-032–037 are reconciled to the canonical S4 backlog row in `core/BACKLOG.md`; current evidence and remaining acceptance are tracked there and in the bilingual report.

## Ordered work and safe stopping points

The current exact-head local category tests remain recorded in change 0198. Report-bound execution was blocked first by a WSL identity-transition dependency; the operator then authorized a bounded helper. A probe exposed a capability leak; the trampoline and focused selectors now have passing runtime evidence at `7b0fe23`. The follow-up CLI exposed an artifact-group ownership issue, while security review found a POSIX ACL validation gap. Changes 0242–0253 address those issues; the current runtime evidence is in the evidence file above:

1. Provision/identify the trusted S4 signer service and create a run-specific v2 task manifest; canonical technical owner is UNKNOWN.
2. Define a contract-safe runner-owned orchestration path for report-bound E2E without recursive runner/worker invocation, then map and run its selector.
3. Run the authoritative task gate and aggregate regression with complete report-bound evidence on an exact final head; keep any prohibited ADR-0001 scenarios `NOT_RUN`.
4. Obtain fresh specialist consensus and exact-head GPT-PM approval. Do not push or open a PR without the required APPROVE.

The earlier WSL transfer and seven POSIX selectors in run `f3ad62c94bc0429987bc24277103d5b4` remain valid only for source HEAD `56dce67e508ccf452b2b7b39ed7f33c863081269`. They do not establish current-head S4 acceptance.
## Unknowns to resolve at S4 start

- Runtime inventory: the named distro reported Python 3.12.3, pytest 7.4.4, iniconfig 1.1.1, packaging 24.0 and pluggy 1.4.0. pytest-asyncio is absent, and no current test source has async tests/markers. The lock pins pytest and its required runtime dependencies; no plugin is added absent a concrete need.
- Source transfer: `tools/qa/wsl_snapshot.py` transferred exact source/test HEAD `7b0fe23` in run `b5bcb1fc2b42449894785c588e20a65f`; ten focused selectors passed and the functional report-bound synthetic run passed 28/28, as recorded in change 0254. The older transfer without correlated run ID remains `RESULT_NOT_CAPTURED`; its destination was not inspected or retried. Trusted signer and authoritative task-gate execution remain `NOT_RUN`; canonical signer/gate technical owner is UNKNOWN. Operator remains accountable under delegated continuation.
- Whether S3 adds a transport API, more test categories, or sandbox-bound E2E paths: inspect the accepted S3 plan and implementation; absent evidence, report Python API only and mark transport API unsupported.
- The canonical service owner for category registry, runner, and evidence gate: no owner is established in the inspected repository sources; preserve `UNKNOWN` and proceed with role-based execution.
- Which S3 test IDs belong in the regression denominator: derive from committed test files and exact-head test records when S3 is accepted.
