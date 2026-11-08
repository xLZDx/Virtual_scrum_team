# Unified Core (AEVE + Virtual_scrum_team): Technical Design Document

Status: plan approved by the operator on 2026-11-08 with the default decisions in section 11; revision 2 after four internal agent reviews (architecture, sequencing, security, test strategy) of head 4ac4b5c. Facts are marked VERIFIED (observed on disk or by a command in this session) or PROPOSED (design choice).

## 1. Purpose

A coding agent (Claude, Codex or another model host) needs review, coding and testing work done. Today each role is a model agent that spends tokens. The Unified Core performs every role that can be performed by deterministic code locally, on the operator's computer, with no model call, and returns structured evidence. A model is used only (a) as the single orchestrator that requests roles and reads results, (b) for authoring that cannot be mechanical (writing code, requirements, design, tests), (c) for the part of a role that code cannot judge, handed over as a narrow slice, and (d) for the final independent review (GPT-PM) after the local checks passed.

Principle: a model call must never be the default way to obtain a result that code can produce. A role that code cannot fully cover reports exactly what it covered and what remains for a model (`PARTIAL` or `NOT_COVERED`), never a fabricated pass. A local result is worth routing local-first only if it removes or shrinks a model call; this is measured per role (section 9), not assumed.

## 2. Components and responsibilities

| Component | Repository | Responsibility | State |
|---|---|---|---|
| AEVE | `D:\Repo\AEVE` (private) | Deterministic local analysis and evidence: review executors, role matrix, review request and iteration ledger, local sandbox | VERIFIED: 191 commits; `aeve matrix`: 57 profiles, 32 executors, 44 PARTIAL, 13 NOT_COVERED, `llm_calls: false`, `executed_project_code: false`; head `25a8fea` at probe time |
| VST control plane | `D:\Repo\Virtual_scrum_team` (public) | Process authority: state store with epoch compare-and-swap, leases, hash-chained signed receipts, deterministic diff gate, worker adapter, bounded command runner | VERIFIED: about 28 thousand lines in `tools/vst/`; S0-S2 accepted and merged, S3 closed in bounded form |
| Environment probe, role router, adapter | VST, `tools/uc/` (new) | Probe AEVE identity, map a role to a local executor, call AEVE through its CLI, normalize the result, build a VST receipt | `aeve_probe.py` written (U1-2); rest PROPOSED |
| Test core | VST (S4 work on pushed branches) | Test-ID registry and denominator, hash-pinned native runner, no-skip gate | VERIFIED: branches `s4-*` and `s5-bounded-aeve-evidence` are on origin; none is merged into main |
| Orchestrator | the model host | One entry point: asks for roles, reads structured results, hands model-only work and residual slices to a model, assembles the package for GPT-PM | PROPOSED |

Ownership rule: one writer per domain. AEVE never writes the reviewed project. VST is the only writer of process state and receipts. The orchestrator never marks anything accepted; only a receipt verified by the VST gate does.

## 3. Verified facts that shape the design

- AEVE review contract: `aeve review --request <json>` takes `aeve.review.request.v1` (`request_id`, `root`, `base_revision`, `changed_paths`, `review_domains`, `profile_ids`, `executor_ids`, `criteria`, `iteration_of`, `allow_dirty`). It runs registered deterministic executors only, calls no model, writes nothing to the project and keeps an append-only iteration ledger under the local application data folder. Exit 0 = clean and complete, 3 = findings, partial or not found, 2 = blocked or invalid. `allow_dirty` yields partial evidence.
- Supported review domains: `python_code`, `source_secrets`, `repository_snapshot`, `database_schema`, `database_migration_safety`, `python_reliability`, `python_syntax`, `python_dead_code`. Free-text `criteria` are preserved, not executed. A completed executor means only that it completed on this captured snapshot, not a general review pass.
- 13 AEVE profiles have no executor: `implementation-engineer`, `ml-engineer`, `planner`, `product-ux-reviewer`, `pytorch-build-resolver`, `agent-evaluation`, `codex-consensus`, `git-worktree-ops`, `performance-testing`, `pm-bridge`, `rosetta`, `update-config`, `ux-design-contract`.
- 35 of the 92 distinct names in `catalog/inventory.json` (93 definitions, `ml-engineer` is both agent and skill) have no AEVE profile at all; all 57 AEVE profiles exist in the inventory.
- AEVE also has `sandbox run` and `sandbox project-test` (Docker, clean exact HEAD). AEVE decision D-076 (2026-10-21, test execution out of the product scope) means test execution is decided separately (section 11, OD-2).
- AEVE is not referenced from Claude routing, settings, hooks or global rules; reviewer roles still run as model agents.
- Probe result (U1-2, run on this machine): status READY, interpreter 3.14, matrix digest `357592f3de7b3000695488d0e38b7d8af8d27841a794d0c4cec09724838dd2a8`, AEVE tree unchanged after the run.
- VST gate semantics (VERIFIED in `tools/vst/contracts.py` lines 670-722, `_derive_static_analysis`): PASS when `coverage == FULL`, no `unsupported_rules` and a non-empty `covered_rules`. The receipt has no findings field today, so complete executors that report findings would give FULL coverage. In `gate.py` a static-analysis receipt is verified with the worker key (lines 296-306) and the key-distinctness check lists five keys (lines 675-681). Signing is symmetric HMAC (`signing.py`). The signer accepts only runner-shaped requests with trusted parser pins (`signer.py`). Receipt v1 and v2 bytes are immutable.
- VST test work on the S4 branches: registry source head `3885d8a`, 963 selectors, 53 policy NOT_RUN; Windows runs on those heads passed functional 90/90, API 688/688 (INCONCLUSIVE, 14 policy exclusions), integration 41/41, E2E 55/55, regression 874/874, seeded failures 3/3. This is evidence for those heads only and is re-earned for every part that lands.
- The old VST sentence "no AEVE source available" came from an isolation rule of that time; AEVE exists.

## 4. Role model

Every requested role belongs to exactly one class in a machine-readable role table (draft input: `catalog/roles.json`, 93 definitions, validated by `tools/catalog/validate_catalog.py`, not yet reviewed):

| Class | Meaning | Examples |
|---|---|---|
| LOCAL | Fully performed by code; the result is evidence | repo-recon, secret scan, python-dead-code |
| LOCAL_PLUS_MODEL | Code produces evidence and findings; a model judges only the residual | python-reviewer, security-reviewer, database-reviewer |
| MODEL_ONLY | Authoring or judgment; no honest mechanical substitute | implementation-engineer, planner, business-analyst |
| OUT_OF_SCOPE | Not part of delivery checks | pm-bridge, rosetta, skill-creator |

Aliases: overlapping definitions (for example `code-architect`, `software-architect`, `architect`) carry a `canonical_role`; a request for an alias is answered for its canonical role and says so.

Roles with no AEVE profile (35 names, section 3) are answered `NOT_COVERED` with the reason "no AEVE profile" unless the table marks them MODEL_ONLY or OUT_OF_SCOPE.

Table versus matrix: the table may be stricter than the AEVE matrix, never looser. Every entry carries a `coverage_state` (`COVERED_PARTIAL`, `NOT_COVERED_NO_EXECUTOR`, `NOT_COVERED_NO_PROFILE`, `NOT_APPLICABLE`) and the executors that the matrix really lists for its canonical role. An entry whose executors differ from the matrix, that claims coverage the matrix does not list, or that says "no profile" while the matrix has one, fails validation. The class records the nature of the role: a role whose draft class is MODEL_ONLY or OUT_OF_SCOPE but for which AEVE lists executors is upgraded to LOCAL_PLUS_MODEL by that evidence (the entry keeps its `draft_class` and a flag); a local-class role the matrix cannot serve is `NOT_COVERED_*`, and the router answers it NOT_COVERED with the stated reason. The table pins the AEVE head and the matrix digest it was validated against; the adapter refuses to run when the probe reports another head or digest (a deliberate table refresh is a reviewed change).

Status vocabulary for every role result: `CLEAN` (every mapped executor completed and reported no finding on this exact snapshot; not a general review pass), `FINDINGS`, `PARTIAL`, `NOT_COVERED`, `NOT_RUN`, `BLOCKED`. Mapping: AEVE exit 0 with complete executors is `CLEAN`; exit 3 with findings is `FINDINGS`; exit 3 with incomplete executors is `PARTIAL`; exit 2 or an adapter failure is `BLOCKED`. A LOCAL_PLUS_MODEL role with a non-empty `model_residual` is never reported as more than `PARTIAL`. Missing, skipped, partial or blocked evidence is never `CLEAN`. The VST gate keeps its own result names (PASS, INCONCLUSIVE, REJECT) and accepts only a verified receipt, never a role result directly.

Before sprint U2 exists every local result is advisory: it informs the orchestrator and cannot satisfy a VST gate. Before sprint U3 lands the test core, test roles are answered `NOT_COVERED` with the reason "test core not available".

## 5. Contracts (PROPOSED)

### 5.1 Role request (orchestrator to router)

```
{ "schema_version": "uc.role-request.v1",
  "request_id": "stable caller id",
  "root": "absolute path of a registered repository root",
  "base_revision": "exact 40 or 64 hex HEAD",
  "changed_paths": ["relative/posix/path"],
  "roles": ["python-reviewer", "silent-failure-hunter"],
  "criteria": ["free text, preserved, never executed"],
  "iteration_of": null,
  "purpose": "advisory | receipt" }
```

Validation: `root` must be on an allowlist of registered roots; `changed_paths` are relative POSIX paths without `..`, drive letter, control characters or symlink components and with a length cap; unknown fields are rejected. `purpose: receipt` forces `allow_dirty=false`, requires a clean tree at the requested head, and requires `changed_paths` to cover the signed diff-gate path list for the candidate (reviewed scope is derived from the diff, not chosen by the caller).

### 5.2 Role result (router to orchestrator)

One entry per requested role: `role`, `canonical_role`, `class`, `status` (section 4), `executors` (id, status, snapshot hash), `findings`, `uncovered`, `model_residual`, `request_id`, `iteration_id`, `base_revision`, `snapshot_hash`. Top-level `exit_code` follows the AEVE convention.

Injection-safe shape: a finding contains only enumerated values (rule id, severity), integers (line, column), hashes, and a relative path that passed the same charset and length check as `changed_paths`. Evidence is a hash plus a line reference, never source text. Unknown fields are rejected. The orchestrator renders a result as quoted data and never as instructions. Retained raw executor output (kept only for BLOCKED diagnosis) is size-capped, redacted for secrets, access-restricted and excluded from model context.

### 5.3 Evidence receipt (router to VST gate)

A new static-analysis receipt version (not an attestation blob, which has no epoch, attempt or chain and loses replay protection). It carries: analyzer identity, AEVE head, role-table hash, snapshot or tree hash, hash of the reviewed path list, `findings_count`, highest severity, a `model_residual` flag, covered and unsupported rules (explicit AEVE rule ids), and the binding task, slot, attempt, epoch, manifest hash and candidate head used by v2 receipts. Result derivation: PASS only when coverage is FULL, no unsupported rule, covered rules non-empty, `findings_count == 0`, and `model_residual` is empty; any other combination is INCONCLUSIVE or REJECT. The builder records a non-CLEAN result as a non-PASS receipt and never as PASS.

Trust chain: the analyzer signs with a dedicated key and label that is distinct from the worker, runner, router and orchestrator keys (added to the key-distinctness check). The signing or verifying component re-derives coverage from the raw AEVE response (or re-runs the deterministic `aeve review` on the same snapshot and compares result hashes); it does not sign what the router parsed from untrusted output. Because current signing is symmetric HMAC, whoever runs the gate holds a forging key: the gate runs outside the orchestrator's principal, or the receipt uses asymmetric verification (the repository already shells out to openssl for execution grants). The choice is OD-7. The reviewed ledger under the application data folder is never evidence.

## 6. Data flow

1. The orchestrator sends a role request for a snapshot.
2. The probe confirms the pinned AEVE head and matrix digest.
3. The router resolves each role through the table. LOCAL and LOCAL_PLUS_MODEL roles go to AEVE by CLI with a timeout; test roles go to the test core once it exists; MODEL_ONLY roles return as model work.
4. The normalizer deduplicates and ranks findings and lists `uncovered` and `model_residual`; for LOCAL_PLUS_MODEL roles it hands the model only the residual slice.
5. The orchestrator fixes code (model) and resubmits with `iteration_of`; AEVE records the iteration.
6. For a receipt, the request is repeated with `purpose: receipt`; VST records the receipt and the gate evaluates it for the exact head.
7. Only then the exact diff, test evidence and review results go to GPT-PM. A new commit invalidates the approval.

## 7. Trust and security boundaries

- AEVE and the router never modify the reviewed project; writes happen only through the worker and the VST diff gate.
- The AEVE process is started with a neutral working directory outside the reviewed root, interpreter flags that stop the working directory and user site from joining the import path (`-P -s -B` or the equivalent), an explicit minimal environment (no inherited tokens), a pinned application-data location, `shell=False`, a stdout size cap, a timeout, and termination of the whole process tree on timeout. A reviewed repository containing `json.py` or an `aeve/` package must not be importable by the analyzer.
- No network and no provider call on the local review path.
- A reviewed project can contain hostile text. File contents, file names, identifiers and findings are data. The result schema (section 5.2) removes free text from the channel to the orchestrator.
- Secret findings are sensitive: values are masked in every report, receipt and retained output; the secrets rule applies to retained raw output too.
- Signing keys are never readable by the worker or by the process that parses untrusted output (operating-system access test, section 9).
- Windows-local only; WSL and the VPS fleet are not touched. Docker-dependent steps are NOT_RUN when Docker Desktop is unavailable.
- Global Claude configuration changes need the operator's approval, a snapshot of `settings.json`, `agent_routing.json`, `hooks/` and the model-policy gate before the change, a rollback verified by hash and by `agentctl.py --strict`, and a kill switch that is read first by a minimal stage and cannot be set from a project-scope settings file of a reviewed repository. A CLEAN result for a LOCAL_PLUS_MODEL role never suppresses the model agent; any fallback agent still passes the model-policy gate.

## 8. Failure modes and required behavior

| Failure | Required behavior |
|---|---|
| AEVE missing, wrong head or wrong matrix digest | `BLOCKED` with the exact reason |
| Timeout or crash | `BLOCKED`, process tree killed, no partial result promoted; the request stays retryable by `request_id` |
| Output not JSON, wrong schema, oversized, with control bytes | `BLOCKED`; bounded redacted raw output retained for diagnosis; never parsed leniently into CLEAN |
| Dirty tree, or head moved after the request | stale: not bound to the new head; a receipt is never built from an `allow_dirty` run |
| Narrow or empty `changed_paths` for a receipt | refused: reviewed paths must cover the diff-gate path list |
| Unknown role, or role with no AEVE profile | `NOT_COVERED`, listed explicitly |
| Executor partial, or non-empty model residual | `PARTIAL`; the gate returns INCONCLUSIVE |
| Findings present | `FINDINGS`; the receipt is never PASS |
| Two results for one head disagree | both kept; the gate uses only verified receipts |
| Concurrent requests with one `request_id` | serialized by the router; a duplicate with different content is refused |
| Same head, changed snapshot | a new iteration, never a reused one |
| Replay of an old receipt on a new head, expired receipt, role-table hash or AEVE pin mismatch | the gate refuses |

## 9. Test strategy

Per workflow: the code of a sprint is completed first; then `functional-test-reviewer` and `e2e-runner` author and run the focused tests for every task and run the complete set they wrote after the last task. The coordinator does not run tests. No mutation runs and no CI in this program; anything unrun is `NOT_RUN` with its dependency. A test counts only if it would fail when the guarded behavior is broken.

| Layer | What is proved |
|---|---|
| Contract | request and result schemas reject malformed, missing, unknown and injection-shaped fields; a seeded instruction string in a path and in a docstring never reaches the result |
| Environment | the probe's before/after tree hash of the AEVE repository is identical; a wrong path, head or digest gives BLOCKED |
| Adapter | each row of section 8 has a test that expects its listed outcome, with a stub `aeve` executable and with the real one; a repository containing `json.py` and an `aeve/` package does not change the analyzer |
| Router | every role in the table resolves or reports NOT_COVERED; counts are generated from the catalog and the matrix and drift fails the test; MODEL_ONLY versus matrix cases follow section 4 |
| Receipt and gate | golden-bytes test for v1 and v2; findings present, non-empty residual, narrow paths, dirty tree, stale head, forged signature, replay on another head, expired receipt, role-table drift and AEVE pin mismatch are each refused; no rendered report contains a pass token for partial coverage |
| Keys | an operating-system access test: a process running with the worker's real credentials gets an access error on the analyzer key |
| End to end | request to receipt to gate on a real snapshot with seeded defects |
| Savings | see below |

Seeded-defect proof (U5): run with the model fallback disabled and every model invocation stubbed to raise; assert the model-call count is 0; a clean control story must return CLEAN; each seeded defect names its expected stage, executor and rule and its resulting status; classes covered: moved head, forged signature, skipped test, partial coverage, unsupported rule, role-table drift, secret in a finding; a negative control disables the responsible check by hand and the defect is then no longer caught (this is not a mutation run).

Token savings: a baseline manifest pins the existing sessions (identifiers plus content hashes), the token fields that are summed (input, output, cache read, cache write, reported separately), and the rule that attributes a turn to a role. The "after" is measured on paired tasks (the same story or diff run once with local-first on and once off). Fixture transcripts with hand-computed totals test the script. A missing, empty or hash-mismatched baseline gives NOT_RUN, never an estimate. A role is routed local-first only if its measured result avoids or shrinks the model call.

## 10. Requirements and traceability

| ID | Requirement | Sprint |
|---|---|---|
| R1 | A requested review role is performed locally with no model call where AEVE has an executor | U1 |
| R2 | The orchestrator uses one entry point and receives structured, honest coverage | U1 |
| R3 | Local-first routing is wired into the Claude host, reversible, with a kill switch | U1 (optional last task) |
| R4 | Token savings are measured against a pinned baseline, not claimed | U1, U6 |
| R5 | Local review results become signed receipts bound to the exact head; the gate fails closed on stale, forged, partial, findings-bearing or residual-bearing evidence | U2 |
| R6 | Tests are accounted by exact ID; a skipped test never satisfies the gate | U3 |
| R7 | Test execution has two local executors built behind one interface and compared, and the operator decides which stays | U3 |
| R8 | Roles without an executor are listed explicitly; new project-scope roles register without code changes and start as NOT_COVERED | U4 |
| R9 | Coding runs under the worker adapter and diff gate, then the review loop iterates until local checks are clean | U5 |
| R10 | The final package for GPT-PM contains the exact diff, test evidence, review results and head identity | U5 |
| R11 | Installation, rollback and runbook exist; everything unrun is recorded as NOT_RUN | U6 |

## 11. Decisions

Accepted on 2026-11-08 (operator approved the plan; these defaults apply unless the operator changes them):
- OD-1 adapter location: in Virtual_scrum_team (`tools/uc/`).
- OD-2 test execution (changed by the operator on 2026-11-08): build both executors behind one interface, the VST native runner on Windows and AEVE's existing `sandbox project-test`, run the same tests through both, then the operator decides which stays (tasks U3-2 and U3-7). The AEVE executor runs only with a profile that excludes the mutation campaign, because mutation runs are forbidden by the operator's standing rules unless the operator names that exact run; this narrows the effect of AEVE decision D-076 for that executor only and changes nothing in AEVE.
- OD-8 coding (operator, 2026-11-08): patches proposed by AEVE's repair lab (which never applies a patch itself) are applied by VST through the isolated worktree and the diff gate; the model writes code only for what AEVE proposed no patch for (task U5-2).
- OD-4 fallback: a BLOCKED local role stays BLOCKED. A model agent replaces it only when the operator allows it for that run.
- OD-5 the S4 branches land in reviewable parts; evidence is re-earned for every landed part; if the carve-out does not fit, only the registry and the no-skip gate are rewritten.

Open (needs the operator before the task that depends on it):
- OD-3 changing the global Claude routing, settings and hooks (task U1-9). Not covered by the plan approval.
- OD-6 whether sprint U3 may use several pull requests (the sprint rule is one). Default if unanswered: two pull requests, registry with runner, then gate with seeded fixtures.
- OD-7 analyzer signing: owner of the analyzer key and the gate process, and symmetric versus asymmetric verification (task U2-2). Default if unanswered: a dedicated symmetric analyzer key held by the gate process, which runs outside the orchestrator.

## 12. Non-goals

Replacing the model for authoring; mutation testing or CI; touching WSL, the VPS fleet or production; building a new analyzer outside AEVE; the candidate worker comparison (Temporal, BMad Loop), which stays parked.
