# Sprint S4 plan: reproducible QA automation

Status: **PREPARED; NOT STARTED**. This document defines the next sprint and authorizes no tests, builds, CI, installs, mutations, seeded product-code defects, or external service calls during preparation.

Sources: `docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md` section 1; `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`; `governance/DEFINITION_OF_DONE.md`; S2 and S3 plans; current `tests/vst/`, `tools/vst/runner.py`, `tools/vst/slice.py`, and `tools/vst/{contracts,gate,store}.py`.

## Goal and scope

Wire reproducible, category-specific native test runs for the repository's functional, integration, Python API, end-to-end, regression, and seeded-failure scenarios, with exact test-ID accounting and machine-readable artifacts; any skipped or uncollected required test makes the result non-approving.

The repository currently has Python tests under `tests/vst/`, using both pytest-style tests and unittest-compatible tests. Existing S2 modules exercise VST contracts, gate, runner, store, lifecycle, and sandbox-probe interfaces. This plan treats the Python module boundary as the API surface: no HTTP or other network service is evidenced in the current repository. If S3 adds a transport API, it must be separately identified and covered; no HTTP API is presumed here.

Out of scope: CI or release pipelines; mutation testing; red/green cycles that alter product code; live service, customer, production, or external API calls; test execution in the planning phase; accepting skips as satisfied coverage; silently replacing an unavailable test category with an unrelated suite. ADR-0001 remains binding: only `functional-test-reviewer` and `e2e-runner` author and execute required tests.

## Current evidence and constraints

- `tests/vst/` contains the S1 contract, gate, store, runner, process-death, and slice tests, plus the five S2 acceptance modules. The current discovery evidence is source-path inspection only; this plan makes no runtime claim.
- `tools/vst/slice.py` provides a synthetic, local vertical-slice harness. `tools/vst/runner.py` executes allowlisted local commands and captures bounded command evidence. They are possible integration points, not yet QA category runners.
- ADR-0001 forbids CI and mutation runs and requires exact-head agent-run evidence. Its permitted synthetic known-defect fixtures may demonstrate a falsifying oracle without mutating product code.
- A repository-owned QA dependency lock and stable category/test-ID registry do not currently appear in the inspected paths. Their exact formats and dependency resolution are UNKNOWN and must be established in Gate 1.
- S3 acceptance artifacts and any new S3 test paths do not yet exist. S4's regression denominator must include the accepted S3 tests once their paths and IDs are established.

## Stories and acceptance criteria

### E1 — Category and test-ID contract

**S4.1.1** Define the supported categories (`functional`, `integration`, `api`, `e2e`, `regression`, `seeded-failure`), their test-owner roles, exact source paths/selectors, required test-ID inventory, applicable environment, and category-level denominator.

**AC-1:** Every required test ID resolves to a committed test and exactly one `primary_category` among `functional`, `integration`, `api`, `e2e`, or `seeded-failure`; duplicate, missing, unknown, or unassigned IDs are rejected before a run can produce an accepting result. `regression` is an aggregate run manifest, not a primary category: it references the union of the accepted functional, integration, API, and E2E test IDs while preserving each ID's single primary category and source-commit provenance.

**AC-2:** Each category has a real native invocation. `api` covers the documented Python API of `tools.vst`; a network API is marked unsupported unless the product adds one and records its route contract.

**AC-3:** The category registry is bound to its content hash and candidate HEAD; stale registry or candidate HEAD cannot produce current evidence.

### E2 — Reproducible environment and native runner

**S4.2.1** Establish a repository-owned, hash-pinned QA dependency input compatible with the required pinned interpreter `C:\Python314\python.exe`, and record relevant OS/runtime/tool versions for each category.

**S4.2.2** Implement one bounded runner entry point that launches pytest's native discovery/execution for the requested category, preserving existing unittest discovery. It records argv, exit code, duration, stdout/stderr references, environment identity, expected and collected IDs, and output artifact digests.

**AC-4:** Running the same committed category manifest with the same interpreter and dependency lock yields the same selected test-ID set; artifact timestamps may differ but are excluded from normalized content hashes.

**AC-5:** A missing interpreter, dependency, category selector, artifact, or test ID produces a typed non-approving result with a cause; no fallback interpreter or empty-success result is allowed.

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

**S4.5.2** Add a bounded synthetic fixture catalog for known failure classes (for example stale HEAD, missing required receipt, invalid signature, out-of-scope diff, skipped required ID, artifact digest mismatch). Each fixture supplies a controlled input record to the unchanged product interface and the expected non-approving outcome; it does not patch, monkeypatch, or rewrite product source.

**AC-11:** Regression reports every required ID and fails on any missing, duplicate, skipped, xfailed, unexpected, or uncollected ID.

**AC-12:** Each seeded-failure fixture is itself a test with a committed fixture ID, input hash, expected rejection, observed rejection and test ID. No actual failing product test is relabeled as an expected seed; no product code is modified to inject a defect.

**AC-13:** Mutation testing and red/green loops remain `NOT_RUN` under ADR-0001. Seeded fixtures do not claim mutation score or prove every defect class.

### E6 — Evidence envelope and gate compatibility

**S4.6.1** Serialize a machine-readable report for each category with schema version, candidate HEAD, dirty-tree state, category-manifest hash, expected/collected/executed/skipped/xfail/unexpected IDs, interpreter and dependency-lock hash, command/exit status, artifact digests, and typed result.

**AC-14:** `APPROVE` is impossible if required IDs are missing or skipped, if evidence is stale or hash-invalid, or if a category is unsupported or `NOT_RUN`; operator waiver behavior remains governed only by ADR-0001 and the authoritative VST gate.

**AC-15:** Evidence artifacts are reproducible and contain no secrets, user-specific absolute paths, tokens, or unrestricted environment values. Environment variable names may be reported only under the existing privacy contract.

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

**Denominator rule:** At sprint start, freeze a committed registry containing every test ID and one `primary_category`, including `UNSUPPORTED` and `NOT_RUN` rows with reasons. The regression manifest is a separate aggregate reference to the required functional, integration, API, and E2E IDs; it does not create duplicate primary-category assignments. Per-primary-category and regression reports must account for 100% of their applicable registry or aggregate manifest. No percentage or category-level PASS can hide an unaccounted ID. Recompute and review the inventory when tests are added or removed; bind it to the exact source HEAD and registry hash.

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
C:\Python314\python.exe -m tools.qa.run --category <category> --manifest docs/qa/categories.json --output <run-dir>
```

This command and its module are **new paths**, not currently runnable. The runner delegates to pytest's native CLI and captures collection and runtime output without claiming that collection alone is a test pass. The exact pytest flags and artifact format are resolved during E2 design and then pinned in the committed manifest.

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

Identifiers VST-032–037 are proposals only and must be reconciled with the canonical backlog when S4 formally starts.

## Ordered work and safe stopping points

1. Reconcile the S3 accepted adapter interfaces and enumerate the S4 denominator; stop safely after E1 if an interface or test ID remains unavailable, with unknowns recorded rather than guessed.
2. Implement and commit environment lock, runner and evidence schema; verify each new seam with its own focused local contract proof after all S4 coding is complete.
3. Add category manifests and synthetic fixtures; connect all six category selectors to native execution.
4. Complete all S4 code before test phase; only then test agents author/run the per-epic and final exact-head suites.
5. Run relevant reviewers, resolve valid findings, request the exact-head GPT-PM gate, then push and merge one S4 PR only after approval.

The first independently safe stopping point is after E1, with the S3 dependency map and denominator frozen. Total gates: **6**, one per epic above. No active S4 implementation or test execution is authorized by this prepared plan.

## Unknowns to resolve at S4 start

- Exact pytest version, full transitive QA dependency set, and supported lock-with-hashes format: establish from the pinned interpreter's authorized environment and repository constraints before coding; do not infer from cached bytecode.
- Whether S3 adds a transport API, more test categories, or sandbox-bound E2E paths: inspect the accepted S3 plan and implementation; absent evidence, report Python API only and mark transport API unsupported.
- The canonical service owner for category registry, runner, and evidence gate: no owner is established in the inspected repository sources; preserve `UNKNOWN` and proceed with role-based execution.
- Which S3 test IDs belong in the regression denominator: derive from committed test files and exact-head test records when S3 is accepted.
