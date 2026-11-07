# Sprint S5 plan: bounded AEVE evidence gate

Status: **PREPARED / NOT STARTED**. This is a VST-side plan. It does not access, acquire, or execute the separate AEVE repository and does not claim the analyzer is available in this checkout.

Sources: continuation scope and exit rule in `docs/sdlc/AUTONOMOUS_CONTINUATION_PROMPT_S2_S5.md` section 1; AEVE bounded-evidence role and unsupported-capability caveat in `docs/UNIFIED_ENGINEERING_ORGANIZATION_MASTER_BLUEPRINT_2026-10-23.md` sections 1, 8, 10, 11, 13.1 and 13.2; existing VST receipt contract in `tools/vst/contracts.py`; gate behavior in `tools/vst/gate.py`; S2 authority and exact-head boundaries in `docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`; and `docs/ADR_0001_TEST_AUTHORITY_MODELS_CI_NOT_RUN_2026-10-24.md`. This plan follows the later S2–S5 continuation rather than stale blueprint roadmap labels.

## 1. Goal and constraints

Produce a bounded static-analysis evidence record for one exact VST candidate head, independently authenticate its origin, and have the VST gate reject stale, forged, unsupported-as-supported, incomplete, or out-of-scope evidence. The evidence must identify exactly which rules and acceptance IDs were examined and which were unsupported.

S5 is complete only when the analyzer's supported/unsupported status is truthful and the stale-head negative case fails closed. An analyzer finding no issues on a subset is not a full review or security approval.

Constraints already recorded in this repository:

- VST is the decision authority; AEVE is a bounded, optional source of deterministic evidence, not a general programming or runtime authority (`docs/DESIGN_BASELINE_AND_IMPLEMENTATION_PLAN_2026-10-24.md`, decision summary).
- Required tests are authored and run only by `functional-test-reviewer` and `e2e-runner`; test execution follows all sprint coding (`ADR-0001`, continuation prompt section 2).
- CI, mutation, and seeded red/green execution are not authorized by ADR-0001. S5 uses reviewable synthetic positive/negative fixtures and assertion review.
- The analyzer must not execute the candidate, call a provider, write to the worktree, use network access, mutate VST state, or approve its own output.
- V1 and v2 receipt bytes and hashes remain immutable. The existing v2 signed body must not gain optional provenance fields after the fact.
- The exact AEVE source revision, license, supported rule inventory, transport, and runnable integration are **UNKNOWN / NOT_VERIFIED in this repository**. Do not fill these gaps by reading a sibling checkout or by treating blueprint summaries as reproduced evidence.

## 2. Existing interfaces and proposed design

### Existing VST surface

- `tools/vst/contracts.py`: `StaticAnalysis` has `coverage`, `covered_rules`, `unsupported_rules`, and `covered_acceptance`; v2 adds fields only to `TestRun` and `IndependentReview` today. Its `derive_result` returns `PASS` only for `coverage == FULL`, no unsupported rules, and a non-empty covered-rule list; otherwise it returns `INCONCLUSIVE` (see `_validate_static_analysis`, `_derive_static_analysis`, and `RECEIPT_V2_TYPE_FIELDS`).
- `tools/vst/gate.py`: `evaluate(...)` is the pure, default-deny decision boundary. For a current-epoch slot it verifies receipt validity/signature, chain, manifest binding, candidate head, required rule coverage, and acceptance coverage; stale deciding receipts do not satisfy the slot. The current public API has no AEVE-specific analyzer/profile trust key or source-bundle digest contract.
- `tools/vst/slice.py`: the existing synthetic fixture can exercise signed receipts, stale heads, unsupported coverage, and `GateDecision` outcomes without using a real project or external service.
- `tools/vst/schemas/README.md`: the human-readable schema must document any accepted v3 fields and remain consistent with validators and gate behavior.

### Proposed minimum design (decision for S5 implementation)

Retain `StaticAnalysis` as the VST evidence type and introduce an explicit v3 manifest/receipt contract for bounded analyzer provenance; do not add optional fields to the v2 signed body or introduce a second phase-state machine/general-purpose agent protocol. V3 must be opt-in through the manifest contract version, and its schema and signature domain must be distinct from v1/v2. The extension should include, at minimum:

```text
analyzer_id, analyzer_version, analyzer_sha256,
profile_id, profile_sha256,
source_tree_sha256,
analysis_scope, report_sha256
```

`analysis_scope` is an exact list of repository-relative included paths (no globs at receipt-validation time); the input to the analyzer is a read-only snapshot whose source tree digest is computed by the trusted VST runner. A separately trusted analyzer identity signs the canonical evidence payload through an explicit domain label. VST verifies the signer against a trust configuration and keeps the analyzer trust root pairwise distinct from worker, supervisor, operator, event, reviewer, and runner-signer roots. No signing key is provided to analyzer code.

The exact trust handoff (direct analyzer signature versus runner-captured output plus independent supervisor/analyzer attestation) must be settled against S2's committed signer/socket boundaries before implementation. Keep the payload contract above stable whichever transport is selected. It is not yet proven that the existing AEVE process can authenticate without adding a new key/service; that remains an implementation discovery, not a reason to infer a pass. V1/v2 fixtures must continue to validate and their canonical bodies/hashes must remain byte-for-byte unchanged; an S5 manifest requiring the new provenance contract must use v3 and cannot silently accept a v2 receipt as equivalent.

The manifest separates `required_rule_ids` from the analyzer's optional rule inventory and lists required acceptance IDs. Under blueprint section 13.3, a rule is mandatory for this receipt only when its stable rule ID is linked to committed seeded-defect evidence that demonstrates the rule's rejecting behavior; other analyzer rules remain optional and do not become S5 acceptance obligations merely because the analyzer can report them. The required ID-to-fixture mapping must be frozen in a committed catalog before S5 implementation; S4's seeded-failure catalog is a prerequisite. For each required rule, the receipt must assign exactly one status: `SUPPORTED_AND_CHECKED` or `UNSUPPORTED`; no missing or duplicate required-rule status is permitted. `covered_rules` remains the set actually checked; `unsupported_rules` is the exact unsupported set. `FULL` is permitted only if every required rule is checked and no required rule is unsupported. `PARTIAL` or `NOT_COVERED` is non-approving for a required full-coverage slot. Optional rules may be reported as checked or unsupported but cannot expand the mandatory denominator. A finding is typed with stable rule ID, severity enum, evidence reference/digest, and path/line provenance. An empty finding list means only “no findings among the rules actually covered.”

### Data flow

1. The supervisor obtains an immutable, read-only candidate snapshot and computes its exact Git HEAD and deterministic source-tree digest over the manifest scope.
2. The VST runner launches the bounded analyzer with the pinned analyzer/profile identities, read-only input, output directory, resource limits, and no network/credential access.
3. The analyzer returns a closed-shape report of checked/unsupported rules and findings. It cannot choose the source digest or current HEAD; the runner binds both from its own snapshot.
4. The trusted signer authenticates the canonical request/evidence payload under the S5 domain. The analyzer never receives signing keys or signer IPC.
5. VST validates the receipt, provenance hashes, rule partition, signature, manifest/head/epoch and required acceptance mapping. It stores the append-only receipt, and `gate.evaluate` decides. Any identity or hash mismatch, missing rule, stale head, untrusted profile, report tampering, unsupported required rule, timeout, or malformed response is non-approval.

Dependency direction: analyzer adapter -> immutable report value; runner -> adapter and source snapshot; signer -> canonical request; VST contracts/gate -> receipt and decision. Analyzer code must not import or write the VST store, and the gate must not call the analyzer or trust analyzer-supplied current-head values.

## 3. Failure modes and safe outcomes

| Condition | Required outcome |
|---|---|
| Exact analyzer or profile SHA absent/untrusted | Refuse launch or produce `BLOCKED`; no analyzer PASS |
| Rule not implemented by analyzer | Put the rule in `unsupported_rules`; force PARTIAL/NOT_COVERED and non-approval if required |
| Analyzer claims a rule was checked but emits no check evidence for it | Reject malformed evidence |
| Empty findings on partial coverage | Preserve partial status; never infer “clean” or full coverage |
| Source-tree digest, report digest, signature, manifest, scope, candidate HEAD, or epoch mismatch | Hard non-approval; stale exact-head evidence cannot satisfy slot |
| Analyzer timeout, crash, resource cap, invalid output, or unavailable tool | Record `INCONCLUSIVE`, `BLOCKED`, or `NOT_RUN` with exact cause; no success fallback |
| Analyzer attempts write, network, subprocess execution, secret access, or path escape | Refuse/terminate within enforced boundary; record the observable violation; never count as clean analysis |
| Concurrent candidate changes after snapshot | Analyze immutable snapshot; candidate HEAD binding mismatch prevents acceptance |
| New code commit after evidence | Evidence is stale; rerun affected analysis for the new exact head |

No hard reason is waived. Any allowed non-execution waiver must follow ADR-0001, name the operator record, and cannot turn unsupported coverage into a normal APPROVE.

## 4. Epics and acceptance criteria

### E1 — Versioned bounded evidence contract

**S5.1.1** Add a v3 manifest/receipt contract for exact analyzer provenance fields and closed enums for rule status, severity, and finding reference. Preserve v1 and v2 validators, signed bodies, and hashes unchanged.

**AC-1:** V3 rejects missing, extra, malformed, duplicate, or contradictory provenance fields. Golden v1 and v2 fixtures continue to validate with unchanged canonical hashes and signatures; v2 cannot be upgraded by adding optional provenance fields.

**AC-2:** Every manifest-required rule has exactly one checked or unsupported status; the sets are disjoint and their union equals the declared analysis rule set.

### E2 — Authenticated independent analyzer provenance

**S5.2.1** Resolve the actual trust flow using only S2 runner/signer contracts; keep analyzer executable outside the candidate worktree and do not expose signer credentials.

**AC-3:** The evidence signature verifies only under the explicitly trusted analyzer authority and domain label; worker, supervisor, operator, event, reviewer and runner-signer keys are rejected for the analyzer receipt.

**AC-4:** Analyzer identity, version, executable digest, profile digest, source-tree digest, report digest, manifest, run ID, candidate head, epoch, and scope are bound to the signed payload.

### E3 — Bounded execution and immutable source snapshot

**S5.3.1** Define an adapter that accepts only a read-only snapshot, explicit in-scope paths/rules, and CPU/memory/time/output limits. Network, candidate execution, VST writes and host path access are denied.

**AC-5:** Positive bounded fixture yields a report whose hashes recompute from the exact fixture and whose analyzer cannot modify the source snapshot.

**AC-6:** Path traversal, symlinks/renames outside allowed scope, oversized input/output, timeout, unexpected subprocess request, and network attempt are refused or non-approving with observable cause.

### E4 — Coverage truth and findings

**S5.4.1** Map analyzer-supported rule IDs to manifest rules; preserve unsupported rules explicitly; bind each finding to rule ID, severity and immutable evidence reference.

**AC-7:** Full coverage is emitted only when every required rule was actually checked and no rule is unsupported. A seeded synthetic “known issue” fixture yields its expected finding; a clean fixture yields no finding only for the checked rules.

**AC-8:** An unsupported required rule, omitted rule, duplicate rule, malformed finding, or incomplete evidence never yields PASS or full acceptance coverage.

### E5 — Authoritative gate and exact-head binding

**S5.5.1** Require the signed analyzer receipt as a manifest-declared VST evidence slot. Gate coverage derives from manifest-required rules/acceptance, not analyzer claims alone.

**AC-9:** A valid exact-head, fully covered receipt can satisfy only its declared static-analysis acceptance IDs; it cannot satisfy functional tests or independent review.

**AC-10:** Any receipt from another head, manifest, scope, profile hash, source-tree hash, report hash, run ID, or epoch is rejected or leaves the slot unmet; stale-head test explicitly yields non-approval.

**AC-11:** Missing, extra, forged, replayed, partial, unsupported, `NOT_RUN`, or `INCONCLUSIVE` evidence cannot produce ordinary APPROVE.

### E6 — Operational and evidence record

**S5.6.1** Retain deterministic evidence artifacts and update the schema guide, backlog, state, change records, decision/lessons logs, registry, and bilingual sprint report.

**AC-12:** Evidence records exact HEAD, clean/dirty note, analyzer/profile/source/report digests, manifest/scope, required/checked/unsupported rule sets, findings, command, limits, environment, signature verification, test IDs/counts, and exact unavailable cases.

**AC-13:** Every unsupported analyzer capability is labeled `UNSUPPORTED`; absent integration or platform proof is `NOT_RUN`; neither is described as success.

## 5. Requirements-to-test map and denominator

Only `functional-test-reviewer` and `e2e-runner` author and run required tests. Author all focused tests after the S5 code is complete; execute per epic and once on the final committed head. The primary coordinator checks coverage against this map.

| Requirement | AC | Falsifying scenario / oracle | Layer | Dependency |
|---|---|---|---|---|
| Strict, versioned receipt, immutable v1/v2 | 1-2 | Missing/extra fields, bool for int, duplicate/conflicting rule statuses; golden v1/v2 canonical hashes unchanged; v2 manifest cannot claim v3 provenance | Contract unit | S2 gate APIs stable |
| Independent analyzer trust | 3-4 | Correct signature accepted; each other trust root, unknown key, replayed request and altered payload rejected | Gate integration | S2 signer boundary verified; analyzer trust provisioning resolved |
| Bounded execution | 5-6 | Read-only fixture; verify source bytes unchanged; forbidden path, symlink, size/time/output bound, subprocess and egress cases fail closed | E2E at runner boundary | Actual analyzer adapter/runtime identity is available and audited |
| Truthful support coverage | 7-8 | Full, partial and not-covered matrices; unsupported required rule, omitted/duplicate status, no-findings on partial remain non-approving | Functional + gate integration | Actual pinned capability catalog or explicit all-unsupported fixture |
| Exact-head gate binding | 9-11 | Exact head passes required static slot only; stale head, changed source/profile/report digest, wrong scope, epoch replay, missing/partial receipt fail | Gate integration | Gate accepts v3 static receipt provenance and records current HEAD |
| Reproducible evidence | 12-13 | Recompute all hashes from saved synthetic artifacts; evidence loader rejects changed bytes or stale HEAD; `NOT_RUN` fixture stays non-pass | Functional and evidence integration | Stable evidence format and artifact retention location |

### Scenario denominator

For each declared S5 rule, include one supported positive or explicit unsupported case. For every run, include:

1. Exact-head clean synthetic snapshot, one supported rule with findings, and one supported rule with no findings.
2. Unsupported rule, unsupported required rule, partial coverage, and not-covered profile.
3. Missing, duplicate, overlapping, unknown, and contradictory rule statuses.
4. Valid analyzer/profile/source/report digest; each digest altered independently; wrong scope and path traversal.
5. Valid independent authority and one rejection case per worker, supervisor, operator, event, reviewer, and runner-signer authority.
6. Exact candidate head accepted and three-head fixture with evidence from each earlier head rejected for current head.
7. Manifest, run ID, epoch, nonce, profile and analyzer revision mismatches; replayed and malformed signature requests.
8. Timeout, output cap, input-size cap, subprocess, attempted write, network, missing executable and analyzer crash.
9. Missing receipt, `NOT_RUN`, `INCONCLUSIVE`, malformed finding and unsupported status preserve non-approval.
10. Reproducibility: repeat same immutable fixture and compare deterministic report bytes/digest; compare changed source/profile to changed digest and stale/invalid result.

Use a deterministic synthetic fixture and never inject a seeded defect into production code. Do not execute mutation or red/green fault injection: ADR-0001 prohibits those methods. Test assertions may use fixed “known issue” fixture inputs whose expected rule finding is independently reviewed.

## 6. Evidence contract

One evidence record per analyzer run must include:

- repository and exact full Git HEAD; `git status` dirty note; manifest digest and candidate/run/epoch IDs;
- analyzer ID, immutable version/revision, executable digest; profile ID/digest; policy/config digest;
- exact included source paths and deterministic source-tree digest; excluded paths and reason;
- required, checked, unsupported rule IDs; coverage enum; acceptance IDs covered and mapping source;
- findings with stable ID/rule ID/severity and evidence artifact path + SHA-256;
- exact executable/adapter command and argv, runtime identity, platform/interpreter, and enforced resource/network/write boundaries;
- report bytes digest, signer authority/key ID (never secret material), signature result, and gate decision/reasons;
- exact test command, test IDs, count and outcome, skipped/xfail IDs; unavailable proof recorded as `NOT_RUN` with cause and owner.

All digest algorithms and canonicalization must be versioned. Paths are repository-relative, normalized, unique and traversal-free. Evidence artifacts contain no secrets, private URLs, personal absolute paths, or customer data.

## 7. Definition of Ready

- S2 is merged and its signer, sandbox, store and gate exact-head evidence has been reconciled; any S2 operator-only sandbox dependency is resolved for sandbox-required S5 scenarios.
- S5 scope, required analyzer rules, supported/unsupported semantics, manifest mapping and exact-head policy are accepted in repository docs.
- Actual AEVE integration source identity/revision/license/security and available adapter interface are evidenced through an authorized in-scope source; until then integration is `NOT_RUN` and no sibling checkout is accessed.
- Analyzer trust authority, key provisioning and signed payload/domain contract are reviewed; signer key material is not given to analyzer code.
- Synthetic fixtures, resource limits, failure boundaries and evidence retention path are specified.
- Functional and E2E test agents confirm the test map before implementation; they do not run tests until all S5 coding is complete.

## 8. Definition of Done

- Bounded static analyzer integration is pinned and cannot write, execute candidate code, reach network, or access signing/VST secrets.
- Analyzer and profile provenance, source snapshot, report, manifest, scope, candidate HEAD and epoch are independently hashed and signed.
- Coverage is truthful: every required rule is checked or explicitly unsupported; unsupported coverage never passes as full.
- VST gate consumes exact-head signed evidence, gives no acceptance credit outside its manifest mapping, and rejects stale HEAD, forged authority, altered artifacts, partial required coverage, replay and missing evidence.
- Functional/E2E agents run complete focused per-epic sets and the final committed-head suite; exact IDs, interpreter, environment, counts, command, HEAD and `NOT_RUN` reasons are retained. Skips do not satisfy DoD.
- Relevant specialists report no open valid BLOCKER/MAJOR; GPT-PM approves the exact final head before one push/PR for S5, then merge is verified against `origin/main`.
- Change record per commit, decision/lessons logs, state, backlog, document registry, schema guide and bilingual S5 report are current.

## 9. Ownership, backlog, and dependencies

Operator is the accountable owner of the delegated S5 sprint; Codex coordinates implementation. `functional-test-reviewer` and `e2e-runner` own required test authorship/execution. No named AEVE technical service owner or adapter maintainer is established by this repository; that specific ownership gap remains UNKNOWN. Do not label a reviewer role as a person or technical service.

Proposed backlog items, to register when S5 is formally started:

| Proposed item | Scope | Accountable / technical owner | Dependency |
|---|---|---|---|
| VST-038 | Versioned static evidence provenance contract and v1 compatibility | Operator accountable; implementation-engineer executes; service owner unknown | S2 exact-head gate state |
| VST-039 | Independent analyzer authority and signature binding | Operator accountable; signer service owner unknown | S2 signer boundary and key provisioning |
| VST-040 | Bounded, read-only analyzer adapter and deterministic snapshot hashing | Operator accountable; adapter technical owner unknown | Authorized immutable AEVE identity and sandbox |
| VST-041 | Truthful rule coverage and finding evidence map | Test agents own required tests; implementation-engineer owns production changes | Audited rule inventory or explicit unsupported fixture |
| VST-042 | Exact-head gate and reproducible evidence integration | Operator accountable; VST gate is technical boundary | VST v3 contract and signed evidence format |

These IDs are proposals, not canonical backlog entries. The actual AEVE candidate identity, license, revision, support matrix, adapter, and any external trust service are unavailable in this repository and are not attributed to a named owner.

## 10. Ordered work

1. After S4 closure, inspect only authorized S5 source/evidence and reconcile the AEVE identity and capability inventory; keep unknown rules unsupported.
2. Finalize source snapshot, report digest, signature authority and exact v3 receipt fields while preserving v1/v2 hashes.
3. Implement contracts and signer/gate path; commit each coherent change with its own detail record and logs.
4. Implement the bounded adapter around immutable input and resource limits; deny unavailable boundaries rather than emulate success.
5. Complete full/partial/unsupported and stale-head paths plus evidence retention; finish all coding before testing.
6. Have the two authorized test agents author/run mapped per-epic tests and final exact-head suite; resolve product defects and rerun affected cases.
7. Run relevant specialist reviews, remediate valid BLOCKER/MAJOR findings, obtain GPT-PM approval on the exact head, then push one PR and merge under the program authorization.

No claim of analyzer availability, coverage, or S5 acceptance follows from this plan alone.
