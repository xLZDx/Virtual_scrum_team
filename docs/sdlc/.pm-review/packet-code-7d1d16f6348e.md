# PM-GPT code review request
Project root: D:\Repo\Virtual_scrum_team
Reviewed range: 2e6a796eaa04664812cf1266322b083f18770fa1...7d1d16f6348e6c00a5a568b5cfbc8caf309194b9
Exact HEAD under review: 7d1d16f6348e6c00a5a568b5cfbc8caf309194b9
Reply format: first line `VERDICT: APPROVE|MINOR|MAJOR|BLOCKER`, then one finding per line as `SEVERITY | basis | claim | evidence | required change`.
Approve only if the exact head is safe to push. Verify claims against the diff.

## Evidence file: verify-evidence.json (sha256 f505950cb507e5f325b684d78b548655bedbf0f8436a3151e57158d098965ba8)
{
  "tested_head": "adda2692451217e7de469d3102ac7cd3b4b35cee",
  "runs": [
    {
      "command": "python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py",
      "total": 52,
      "passed": 52,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "tested_head": "adda2692451217e7de469d3102ac7cd3b4b35cee",
      "log": "Functional-test-reviewer; Python 3.14.3; exit 0; 52 passed, 1 existing pytest-asyncio deprecation warning in 22.58s. Covers production assemble_inventory through real validate_inventory, plus missing and contradictory values for all eight readiness fields.",
      "test_blobs": {
        "tests/vst/test_s2_runtime_inventory_collector.py": "16e9cb9fdb6835593c9fee5dee905e7c659af238d9ec7969306411f9740ff21b"
      },
      "source_blobs": {
        "tools/qa/collect_s2_runtime_config_inventory.py": "453fe70732c7309158cab7a0876b6bb7347b895056969ef87dbf988dd8cfa838"
      }
    }
  ],
  "latest_test_execution": {
    "tested_head": "adda2692451217e7de469d3102ac7cd3b4b35cee",
    "command": "python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py",
    "total": 52,
    "passed": 52,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "log": "Functional-test-reviewer; Python 3.14.3; exit 0; 52 passed, 1 existing pytest-asyncio deprecation warning in 22.58s.",
    "test_blobs": {
      "tests/vst/test_s2_runtime_inventory_collector.py": "16e9cb9fdb6835593c9fee5dee905e7c659af238d9ec7969306411f9740ff21b"
    },
    "source_blobs": {
      "tools/qa/collect_s2_runtime_config_inventory.py": "453fe70732c7309158cab7a0876b6bb7347b895056969ef87dbf988dd8cfa838"
    }
  },
  "not_run": [
    {
      "item": "Fresh permitted WSL target inventory and conditional runtime qualification",
      "reason": "The prior one-shot authorizations were consumed by collector serialization refusals on older HEADs. Obtain a new correlated authorization for the pushed corrected HEAD, then e2e-runner performs the committed collector and validator once; no apply, preflight, claim, probe, or TestRun is claimed here."
    },
    {
      "item": "Restricted process-kill, crash/recovery, mutation, E8, and S4/policy selectors",
      "reason": "These scenarios remain explicitly NOT_RUN and are outside this task's permitted runtime sequence."
    }
  ],
  "findings": {
    "open_blocker": 0,
    "open_major": 0
  },
  "reviewers": [
    {
      "role": "functional-test-reviewer",
      "model": "gpt-6-luna",
      "effort": "inherited; no explicit override recorded",
      "verdict": "52 focused collector-to-real-validator tests passed at exact HEAD adda269."
    },
    {
      "role": "code-reviewer",
      "model": "gpt-6-luna",
      "effort": "inherited; no explicit override recorded",
      "verdict": "MAJOR-01 remediation and integration-test contract re-reviewed; no actionable B/M findings."
    },
    {
      "role": "security-reviewer",
      "model": "gpt-6-luna",
      "effort": "inherited; no explicit override recorded",
      "verdict": "No actionable B/M finding in the collector assembler delta; test execution not performed."
    }
  ],
  "reviewers_waived_reason": "Not applicable; specialist reviewers are listed above.",
  "resolved_prior_finding": {
    "request_id": "cf7a9515-0cd8-47d2-a0cb-1c351a3ef1e0",
    "finding": "MAJOR-01: six validator-required fields were absent inside readiness.",
    "resolution": "assemble_inventory writes all top-level and nested copies from the same captured values; real validator integration tests cover valid, missing, and contradictory values."
  },
  "review_base_reconciliation": {
    "previous_start_head": "20fda2cbf26274192652a1c829a19f6b1844e9c4",
    "previous_start_head_is_ancestor": false,
    "corrected_start_head": "2e6a796eaa04664812cf1266322b083f18770fa1",
    "corrected_start_head_is_ancestor": true,
    "reason": "The previous tracked AF baseline belonged to another branch and made a scoped S2 exact-head review impossible."
  }
}


## Evidence file: verify-evidence.md (sha256 8128cb3825593c902ae89476f24a28507e0ddf4d536dc32e21a5238896e4447d)
# S2 verification evidence and remaining acceptance

Sprint: 39b7cc253f5d

Product sprint: existing S2. Framework phase: 7 Verify. This is an evidence record, not an
approval file. Overall S2 remains NOT APPROVED; production/runtime criteria below are unresolved.

## Provenance and verification layers

Continuation baseline: `9c1be0f`. Runtime journal correction: `5724ba8`. Read-only authenticated
assignment API: `c2b1cd2`; current run/generation correction: `3d5f6c2048238a79fb92ddf805bc562b4b392a63`.
Later documentation changes do not imply these tests executed at a different source revision.
The primary agent coordinated tests and assessed coverage but did not author or execute them.

Reconciliation addendum (2026-10-29): the complete original epic/deferred-item denominator and
the 0552/0553 decision boundary are mapped in [S2 original epic coverage reconciliation](S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md).
The corrected historical schema-v5 fixture has its own two-selector result in
[s2-legacy-v5-fixture-run-20261029.md](evidence/s2-legacy-v5-fixture-run-20261029.md); it is
maintenance evidence and does not combine with the component rows below or establish final-head
S2 acceptance. GPT-PM's recovered correlated source reply and exact limits are recorded in
[the bootstrap and issuer adjudication](evidence/s2-bootstrap-source-and-root-issuer-adjudication-20261029.md).
Unsigned host/guest observations remain UNKNOWN as detailed in
[s2-machine-observations-20261029.md](evidence/s2-machine-observations-20261029.md). The root-bound
issuer design is linked separately at [S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md](S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md);
it is design/source preparation only and does not close its issuance-state finding.

The implementer reported one accidental `git diff --check` invocation during this continuation
with no output. This report was not independently reproduced and is not a test, build, runtime,
or acceptance result. It does not alter the exact commands and owners reported below.

| Actual role / model / effort | Source and command scope | Recorded result | Boundary |
|---|---|---|---|
| functional-test-reviewer / gpt-6-luna / medium | Three new runtime-bundle/source-plan/machine-contract test files; exact source/hash references in s2-bootstrap-functional-run-20261029.md | Windows 30 passed / 6 POSIX skips; WSL 36 passed, exit 0 | Real synthetic Ed25519 keys and public verification in WSL; detached candidate contracts, no production authority |
| e2e-runner / gpt-6-luna / medium | Two bootstrap/stage-only test files at c2b1cd2; s2-bootstrap-e2e-run-20261029.md | WSL 16 passed; Windows 8 passed / 8 POSIX skips | Disposable filesystem and mocked systemd boundaries; real harmless Python argv mapping; ordinary partial-write exceptions, no process crash |
| functional-test-reviewer / gpt-6-luna / medium | test_s2_assignment_basis.py plus two explicitly named safe Store regressions at 3d5f6c2; s2-assignment-basis-functional-run-20261029.md | Windows 23 passed; WSL 23 passed, exit 0 | Real disposable Store read transactions and synthetic future handoff; no authenticated production writer or configured peer |

The three rows are separate commands at their identified revisions; do not present them as one
full-suite or final deployed-head run. Runtime-bundle and journal components unchanged by the
run/generation correction retain their recorded component-level evidence. All exact commands,
tool versions, hashes, skipped cases and limitations are in the linked records.

## Independent review and corrections

| Actual reviewer / model / effort | Findings and disposition | Remaining scope |
|---|---|---|
| code-reviewer (s2_runtime_code_review) / gpt-6-luna / medium | Two valid MAJORs: partial preparation journal and partial retention copy could strand retry. Fixed at 5724ba8, reproduced then passing by E2E owner, focused source recheck on 3d5f6c2 resolved both. Argument-index finding explicitly retracted; actual subprocess test confirms existing indexing. | Source/fixture proof only |
| security-reviewer (s2_runtime_security_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in reviewed runtime/candidate-contract diff 9c1be0f..7e9c519 | Production trust and E5 unchanged |
| database-reviewer (s2_basis_database_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in read-only source diff 5724ba8..3d5f6c2; one consistent read transaction and rollback-only close, chain/anchor/journal/probe/live-authority checks | Future writer needs atomic conn-taking helpers and explicit failure contract |
| security-reviewer (s2_basis_security_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in the same read-only source; optional issuer-only operation, trusted current policy/run/generation | Future writer and real deployment are not accepted by this source review |
| database-reviewer and security-reviewer focused design rechecks / gpt-6-luna / medium | Fresh-only writer addendum resolves the previously reported transaction, eligibility, authenticated caller and replay/legacy design gaps; no remaining design-level MAJOR in the reviewed slice | Explicit GPT-PM SOURCE decision still required before writer implementation; production is separate |

Focused tests also found duplicate embedded guard, independent revocation-ID conflation, and
stale Supervisor run/generation acceptance. Fixes 0544, 0545 and 0549 are linked to their negative
regressions. An exploratory historical schema-v5 selector is incompatible with the pre-existing
schema-v6 baseline; its unchanged hard-coded assertion and failed command remain recorded, not
hidden or counted as new-feature coverage. Codex owns its backlog reconciliation.

## Acceptance matrix

| Criterion / meaning | State | Evidence/completed work | Remaining acceptance | Dependency/blocker | Owner | Next step |
|---|---|---|---|---|---|---|
| S2-1 / signed admission and recovery | Delivered — bounded source/test acceptance | Four-file WSL selection 130/130 at `2befed5`; source-fidelity verifier 5/5 at `206a746`; adapter functional/E2E 35/35 and 2/2 at `2befed5`; parser regression 38/38 at `6952469`; exact Bridge-wrapper regression 38/38 at `0da595e`. All 41 redactions map across 15 exact Git blobs/lines. GPT-PM request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` resolved S2-REVIEW-02 for S2-1 source/test acceptance at submitted HEAD `57c734e60787a9db14bb888116d7e808bc46970e`; see `evidence/s2-1-coverage-adjudication-f92b750e.md`. Delivery: commit `e332ec4` pushed. GPT-PM did not execute tests. | No remaining S2-1 source/test work. Installed runtime, systemd/kernel identity, production configuration, current E5 and restricted scenarios remain unproven or NOT_RUN. | None for bounded S2-1 delivery; full S2 runtime/acceptance remains open. | Codex owns task delivery; GPT-PM owns the bounded coverage adjudication. | Proceed to the next ordered task, S2-2; keep runtime claims separate. |
| S2-1 / current PM coverage adjudication | Correlated GPT-PM decision recorded; test evidence is inherited | Request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` at submitted HEAD `57c734e60787a9db14bb888116d7e808bc46970e` accepted baseline-plus-delta evidence for S2-1 and resolved S2-REVIEW-02. GPT-PM accepted the reported no-change comparison for six S2-1 paths, while noting it did not independently reproduce that Git-object comparison or execute tests. Full disposition: `evidence/s2-1-coverage-adjudication-f92b750e.md`. | No further coverage review is required for S2-1 source/test acceptance. This was delivered in `e332ec4`. Do not treat it as runtime or full-S2 approval. | None for S2-1 source/test delivery; production/runtime and E5 are not proven. | Codex owns the evidence update and push; GPT-PM owns the submitted adjudication. | S2-1 is done; S2-2 is now the next queued task. |
| S2-2 / authenticated owner transport | Delivered — bounded source/test acceptance | GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55`; recovered PM Bridge job `68efb4e6-a296-4fd7-bcfc-2c6fe2568d5c`, correlated reply `d555b078-5647-46eb-bfc1-dd99654d634f`. Exact source/test blobs are in pushed commit `e987a24`; designated WSL run reports 34 passed, 0 skipped/failed. Delivery record 0588 reconciles the previously uncertain wait state. | Real activated endpoint to Runner; actual systemd/PID1 credentials, kernel credentials, pidfd, socket metadata, root configuration, production authority/E5. | Production `S2-DISPATCH-M01` and real runtime remain unproven. | Codex owns evidence; GPT-PM owns bounded source/test decision; operator owns genuine production authority/signature. | S2-2 bounded task is delivered; next incomplete task is S2-4 after change record 0588 is pushed. |
| S2-3 / exact bundle and bounded inactive preparation | Focused M-S2-3-03 review approved on source HEAD `ef465cd` (request `17aa39d9-fb95-4d27-ba94-858fe1cc954d`); exact bundle approved for inactive stage-only on plan SHA `59ebfee0435d7a34f4c09de6ef5269e08d7a6713a5e7301497ba754ef348d8e9`, inventory SHA `a3b6ea38103edfb0d25cab8ef3c2e405d8bcb2d08c0d16194668b4860095d054`, archive SHA `bc489ce6155e178b1f2c2ef6a9e8b88e78c3b3e991576107319c9b34c3543d44` (requests `29c0c463-9d18-4c35-ae9d-8ed5331a4f70`, refreshed inventory `5f47ce5d-3db2-4f22-9e72-cad81a139c9c`). | Designated-runner direct regression: 4 passed, 8 deselected, 0 skipped on committed source `043980f`; blobs unchanged at reviewed `ef465cd`. The authorized stage-only handoff installed the immutable runtime/helper in Ubuntu-24.04 and returned `selected=false`, `selector_unchanged=true`, `systemd_units_installed=0`, `runtime_stage_only=true`. | Exact post-stage manifest was separately reviewed; resulting bounded preparation acceptance is recorded. The broader TP-10 rejection/error matrix remains PARTIAL; live collision refusal, selector transition, services, Store, identities, keys/E5, dispatch and production are not accepted by this task. | GPT-PM request `ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4` / correlated reply `1c8d392e-1a57-533c-b874-97823f5e4628` approved manifest SHA `78d21af798f66a3e54a8d638f393773af5d20120075cd02599ac70675cb84be7`, with 0 BLOCKER/MAJOR in scope. Store remains UNKNOWN; no selection, unit writes/activation, keys/E5 or production authorized. | Codex committed and pushed task record `ae07f8708adcc7ef4f69505477ad6b72e3c912cf`; GPT-PM owns the bounded manifest decision; `e2e-runner` owns mapped runtime tests. | S2-3 task delivery is complete. Advance only according to the sequential backlog. Do not infer S2 sprint acceptance or production readiness. |
| S2-4 / authenticated assignment and runtime provenance | Issuer SOURCE implemented and bounded code/test approved; runtime OPEN | I01 SOURCE GO `c7a8e23e`; exact code/test APPROVE at `c978360`, request `8fc2e0ba`; additional V2 verification slice approved at `aa349632`, pushed through `e09c78b` | Production configuration/key provenance, current E5 and real owner-to-Runner journey | REQ-005 runtime prerequisites unverified; no missing issuer source implementation asserted | Codex: preparation/evidence; GPT-PM: adjudication; operator: reserved authority/custody/attestation | Follow the current ordered queue in backlog.md; reconcile permitted runtime inputs without reopening accepted source |
| S2-5 / exact-head gate and delivery | OPEN | Correlated architecture decisions and actual role evidence retained | Fresh full S2 acceptance and exact-head GPT-PM approval, then one sprint PR | S2-3/S2-4 runtime acceptance unresolved | GPT-PM; Codex coordinates | Submit complete evidence only when prerequisites established; never self-approve |
| Restricted scenarios / process-kill, crash/recovery, mutation, E8 and policy selectors | NOT_RUN | Explicit restrictions preserved | No pass or waiver inferred | Prohibited execution | Operator for any changed scope; Codex preserves status | Leave NOT_RUN; obtain only a precise authorized disposition if required for acceptance |

## Historical remaining-work narrative (superseded by backlog.md current checkpoint)

1. S2-1 is delivered in pushed commit `e332ec4` with change records 0586/0587; its bounded
   source/test coverage acceptance is complete.
2. S2-2 bounded source/test delivery is recorded in pushed `e987a24`; change record 0588
   reconciles the exact PM correlation, source/test blobs and mixed-commit limitation.
   Production identity and owner-to-Runner runtime remain open, not accepted by S2-2.
3. S2-3's bounded inactive stage-only task is already accepted and delivered in pushed commit
   `ae07f8708adcc7ef4f69505477ad6b72e3c912cf`; this does not close the full runtime story.
   S2-4 is the next incomplete task. Obtain its focused DB/security review and explicit bounded
   GPT-PM source decision before implementing newly authorized scope.
4. Collect genuine current runtime/E5/authority evidence only if its prerequisites and authorization
   exist. Restricted scenarios remain NOT_RUN. Finish full S2 acceptance before S3.

Current human E5 verifier is unchanged; unsigned machine observations always remain UNKNOWN.
No production signing key/service, Store migration, dispatch activation, PR or merge is claimed by
this record. A task push is delivery evidence, not S2 sprint closure.


## Post-integration current source verification — 2026-10-29

Sprint: 39b7cc253f5d

Source freeze: `67d1d55e5556c6936516f3404202faecba1e6707` on
`s2-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
The earlier writer-HOLD matrix above is historical and superseded for SOURCE by
GPT-PM's I01 SOURCE GO and the implementation/fixes through change 0564. It remains
correct that installed runtime, current E5 and final Phase 8 are not thereby proven.
No existing external coordinator is required: the bounded assignment/issuer source
is implemented in Store/Supervisor and the operation-ID-only authenticated route.

### Current permitted evidence

The actual functional and E2E roles are `gpt-6-luna`, medium effort. Their public
records retain exact commands, overlay hashes, environment, failed prior revisions
and current results. Tests are synthetic source/Store/RPC or explicit dedicated-WSL
permission boundaries, not production service activation. Results must not be added
across overlapping groups or revisions.

| Current selection | Source / result | Evidence and limit | Owner / next acceptance |
|---|---|---|---|
| Four functional modules, Windows | 67d1d55: 62 passed, 6 skipped | `evidence/s2-final-functional-e987a24-20261029.md`; six POSIX-only signed-key fixture cases are not Windows passes. | Codex reviews exact evidence; POSIX counterpart below. |
| Same four functional modules, WSL | 67d1d55: 68 passed | E2E reported terminal success with exact overlay hashes, including private-root fixture correction. | Codex reconciles the final E2E public command record. |
| Full delegated issue-to-reservation path and negative integration controls | 67d1d55 WSL: 26 passed | Completed issuance, admission/replay, exact grant persistence/replay, claim/reserve, duplicate refusal, live revocation and missing-link refusal. | Codex obtains fresh independent source reviews. |
| Legacy schema-v5 and TP28 regressions | 67d1d55 WSL: 7 passed | Current legacy/direct compatibility remains permitted without delegated downgrade. | Codex retains separate exact selector evidence. |
| POSIX anchor and worker/reviewer identity boundary | 67d1d55 WSL: 10 passed | Dedicated existing WSL fixture only; not production credentials or Windows ACL proof. | Codex preserves the platform limitation. |
| Windows allowed E1/E3/E6 and integration selection | 67d1d55: 97 passed, 26 skipped | E2E current report; skips are 25 POSIX-only integration cases and one POSIX reviewer case. | Codex maps each allowed result to original acceptance; no skip promoted. |
| Bundle/source plan/bootstrap/stage-only fixture groups | Prior 8beffcc: WSL 36 passed; Windows 28 passed, 8 skipped | Product paths and test modules unchanged by Store-only 0564. Historical scoped evidence, not a claim of a new run or installed bundle. | Codex includes source/blob identity in review; GPT-PM reviews exact staging candidate later. |
| Additional allowed E7 pub/sub, owner and idempotency contracts | 67d1d55: Windows 40 passed / 17 skipped; WSL 35 passed; separate WSL latch 7 passed | Exact nodes and fixtures in both public role reports. Windows POSIX skips have an explicitly separate WSL counterpart, not a Windows pass. | Codex obtains independent review; no real service/process operation is inferred. |
| Allowed E7 lifecycle, breaker and simulated recovery contracts | 67d1d55 Windows: 34 passed across six exact invocations | Source-inspected callbacks, synthetic keys, disposable SQLite and in-process threads. Real process recovery is NOT_RUN. | Local bare-Git/fake-PR fixture and pre-spawn injected timeout also passed; actual termination, remote providers and runtime remain NOT_RUN. |

### Remaining real acceptance and ordered closure

1. Allowed E7 regression mapping and current public records are complete for the
   permitted source scope. Codex commits the package with change record 0565; the
   source/test blobs, not an invented cumulative count, identify this evidence.
2. Codex launches fresh actual general-code, database and security/reliability reviews
   for the exact source package. Fix all confirmed code BLOCKER/MAJOR findings in a
   focused batch and run only designated direct regressions.
3. Codex prepares the exact final non-secret source staging plan and current target/
   compiler metadata. GPT-PM adjudicates the bounded source/runtime package before
   any actual staging, key/policy installation, runtime signing or service activation.
4. Current E5 still requires genuine run-bound evidence under the accepted contract.
   Operator owns any reserved human attestation; Codex owns permitted preparation and
   collection. No signature, policy installation or activation is inferred here.
5. Restricted actual termination/crash/mutation/E8 scenarios remain NOT_RUN. Codex
   supplies exact remaining scope; GPT-PM adjudicates acceptance and the operator
   owns any genuine scoped waiver or restriction change. A waiver cannot erase FAIL.
6. Only after acceptance and fresh exact-head GPT approval may Codex push/open the
   single S2 PR. S3–S5 remain ordered behind S2 closure. No self-written approval.


### Frozen-source specialist consensus and live observation

All three actual fresh-context reviewers completed their declared full new S2
source surfaces at d3f326f37a40936402d3933d5266e0ffb01017f0. Confirmed code
BLOCKER:0; MAJOR:0. See
`evidence/s2-frozen-source-reviews-d3f326f-20261029.md` for roles, exact scopes,
base, line evidence, initial capacity rejection and corrected security-scope sweep.
These findings do not claim an exhaustive generic audit or runtime acceptance.

The six committed test blobs at d3f326f match the exact SHA-256 overlays recorded
for current67d1d55 execution. The only tools/vst or tools/qa path changed between
those commits is tools/vst/schemas/README.md; product source did not change.

Permitted live Windows collection was actually attempted with fixed PS7, no fallback.
`Get-NetFirewallProfile` is unavailable in that restricted PS7 context although the
NetSecurity2.0.0.0 module is discoverable. An explicit native import also failed;
its precise exception is UNKNOWN, not an asserted permission error or source bug.
No complete snapshot/counts exist; normalization remains unsupported. Raw host data
is private and not part of this packet. Public sanitized record:
`evidence/s2-windows-live-observations-d3f326f-20261029.md`.

Requested GPT-PM adjudication is the exact code package and residual acceptance,
not a claim that S2 is fully done. If a bounded runtime step is authorized, state
its exact scope separately: stage an immutable versioned tree and helper from the
reviewed source/compiler recipe only, preserve the selected old runtime and units,
collect post-stage fingerprints, then review that transition manifest before any
selector/config/keys/service signing or activation. No source-plan JSON grants
permission. Existing compiler/path inventory is dated evidence and must be refreshed
for the actual stage. Genuine E5 and restricted-case disposition remain explicit;
Codex will not invent an operator signature/waiver or an external coordinator.

### S2-3 reviewed source/stage bundle verifier follow-up (2026-10-29)

- Baseline source HEAD: `c97836029a5d94ff84dee5cb15d1757efd5525c3` on
  `s2-canonical-continuation`; code and tests were run from the working-tree overlay, not from a
  committed S2-3 revision.
- The exact focused command was:
  `python -m pytest -q tests/vst/test_s2_wsl_bundle_verifiers.py tests/vst/test_s2_source_staging_plan.py tests/vst/test_s2_runtime_bundle.py tests/vst/test_s2_bootstrap_runtime.py tests/vst/test_s2_stage_only_install.py`.
- Designated `e2e-runner` execution: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4;
  **54 passed, 0 failed, 0 skipped**, exit code 0. The initial run had 46 passed and 8 failed;
  triage established two test matcher wording defects and six failures from bootstrap's obsolete
  schema-1 marker comparison. The matchers now accept the actual hard-link refusal diagnostics,
  and bootstrap compares the complete schema-3 provenance marker to the reviewed manifest.
- Exact run ID, transfer and archive digests, and all 45 input-file SHA-256 values are recorded at
  `evidence/s2-3-focused-posix-rerun-d6d3fea7d21c4d01900b37860a29c2fa.md`.
- Independent `code-reviewer` reviewed that final schema-3 bootstrap comparison and found no
  blocker: the exact field set matches the bundle builder and stage verifier, so missing, extra,
  or mismatched marker values are refused.
- The test runner used and removed `/run/vst-test-8f280caeee154d11aa483cfef987a2c7`. It reports
  no repository/system/runtime mutation. These are fixture/source-contract results; no WSL target
  inventory, live runtime installation/selection, service activation, Store/key/E5 action, or
  production owner-to-Runner path was performed.
- S2-3 bounded stage-only acceptance and post-stage manifest review are recorded in
  `evidence/s2-3-stage-only-ef465cd.md` and
  `evidence/s2-3-post-stage-manifest-review-ac2d25a2.md`. The accepted evidence/change record was
  committed as `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` and pushed to
  `origin/s2-canonical-continuation`. This closes only that bounded S2-3 task delivery. TP-10's
  full refusal matrix remains partial; S2-4/S2-5 and the overall S2 gate remain open.

### S2-4 bounded V2 authorization source slice (2026-10-30)

- This is a bounded source/test delivery candidate, not full S2-4 acceptance. GPT-PM request
  `70c7fd31-463d-47ad-b95b-dd8916d7218c` approved the design clarification only. It did not
  authorize privileged signing/issuance, production providers/keys/configuration, activation,
  dispatch, E5 replacement, or S2 closure.
- Test owner: `functional-test-reviewer`; the primary session did not author or execute tests.
  Windows command `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_machine_authorization_v2.py`
  returned **2 passed, 11 skipped**, exit 0, Python 3.14.3. The skips are POSIX-only synthetic-key/Supervisor cases.
- Ubuntu-24.04 WSL command: `wsl.exe -d Ubuntu-24.04 -u root -- bash -lc 'set -e; mkdir -p /mnt/d; mountpoint -q /mnt/d || mount -t drvfs D: /mnt/d -o ro; cd /mnt/d/Repo/Virtual_scrum_team; PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/vst/test_s2_machine_authorization_v2.py'` returned **13 passed in 0.79s, 0 skipped**, exit 0, no warnings. The read-only mount and test ran in one root process; fixture files stayed under `/root`. Exact file SHA-256 values and iteration history are in `evidence/s2-4-v2-authorization-source-20261030.md`.
- Final read-only `code-reviewer` and `security-reviewer` reviews found no actionable finding in this bounded diff. They did not run tests. The verifier is not connected to an RPC route; the legacy V1 caller-selected operation-ID route remains a separate open integration item.
- `git diff --check` returned no output. Production identity/configuration, keys, E5, Store mutation, activation, dispatch, and restricted process-kill/crash/mutation/E8/policy selectors were not exercised. The restricted selectors remain `NOT_RUN`.

Exact-head bounded-source decision: GPT-PM returned **APPROVE** for source/test scope at code HEAD
`aa3496322ca7b05955dd60dfee7decd8056f34ee` (request `b53d89ab-aca1-4432-87d3-5b139592f575`,
correlated reply `0477831c-98fa-5e91-8416-5b5b4ff7cacd`, 0 BLOCKER / 0 MAJOR). The full S2-4
acceptance remains NOT APPROVED. This decision does not authorize privileged issuer implementation,
production keys/configuration, activation, dispatch, E5 replacement, runtime acceptance, or S2
closure. The V1 caller-selected operation-ID route and real owner-to-Runner evidence remain open.

### S2-4.12b runtime inventory MAJOR-01 remediation

- The local task commit contains the single-path `assemble_inventory()` correction, the focused integration
  regression, the two prior one-shot
  runtime refusal artifacts, and the task change record. Collector Git-blob and worktree bytes
  match at SHA-256 `453fe70732c7309158cab7a0876b6bb7347b895056969ef87dbf988dd8cfa838`.
- GPT-PM review request `cf7a9515-0cd8-47d2-a0cb-1c351a3ef1e0` on prior HEAD
  `1a7dca5527dbe48324426f9b5f56621e85a6279b` returned HOLD / MAJOR-01: six fields checked by the
  real validator were absent from nested `readiness`. The shared assembler now derives both copies
  from the same read-only capture. The code reviewer confirmed no remaining actionable B/M finding;
  security review likewise found no actionable B/M finding.
- The designated functional-test-reviewer ran
  `python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py` at pre-commit working-tree
  state on HEAD `1a7dca5527dbe48324426f9b5f56621e85a6279b`: 52 passed, one existing pytest-asyncio
  deprecation warning, exit 0, Python 3.14.3. This covers valid assembly through the real
  `validate_inventory` and missing/contradictory cases for all eight duplicated readiness fields.
  The reviewer reran this command after the code/test commit at HEAD
  `b927a438a72d14a31229c9d0ad7514a19606c98e`: 52 passed, one existing deprecation warning, exit 0.
  A subsequent task-record-only amendment changed no collector or test bytes. No target runtime was
  invoked.
- Remaining: run exact-head GPT-PM remediation review, pass the enforced pre-push gate, push
  normally, then request a fresh one-shot runtime
  authorization. Neither consumed authorization can be reused; no apply, preflight, claim/probe,
  or TestRun occurred under them.
- Review-range correction: tracked AF `start_head` previously pointed to
  `20fda2cbf262...` on `s4-canonical-continuation`, which is not an ancestor of this S2 branch. It
  now points to previous delivered S2 HEAD `2e6a796eaa04664812cf1266322b083f18770fa1`, so the exact
  review can cover only the current S2 continuation. See change record
  `docs/changes/0618-s2-4.12b-review-baseline-reconciliation.md`.

### S2-4 exact configuration preparation — 2026-10-30

Delivered code a600774 corrects the actually observed Python3.12 missing pidfd constant; its
45 focused passes and real kernel descriptor evidence are in change0592. The exact updated
runtime/helper was actually staged without selection or activation. The non-secret config
bundle in runtime-config/ binds that source, official transition tree/helper hashes, isolated
roles, one exact task/policy, configured model record and real run/nonce.

Designated verification and its initial findings/fixes are linked from change0595. A local
reviewer witness is explicitly distinct from GPT-PM, and root technical delegation is not a
claim of personal human signing. No service journey, preflight success or task approval is
inferred from these preparation artifacts. Current execution order is in backlog.md.


## Evidence file: review-record.md (sha256 1964eff1b98e4132b705f911d5433cae1114f73c9166bb945e07b295663185ac)
# S2 phase 5 document review

Sprint: `39b7cc253f5d` (existing S2). Baseline: `9c1be0fbe42b48f7a9cd547be36af23413fcfc8e`.
Reviewed working-tree requirements/backlog/design/test-plan and candidate machine trust design.

## Actual independent reviews

| Agent / profile / effort | Finding | Focused resolution / disposition |
|---|---|---|
| s2_phase5_arch / architect / gpt-6-luna / medium | Staging previously coupled selector/unit install; journal had rename-to-record interruption window | design.md now specifies explicit stage-only path, separate transition, fsynced write-ahead intent/completion and recovery by old/new fingerprints for every path. Architect rechecked both and returned GO for bounded runtime implementation. |
| s2_phase5_code / code-reviewer / gpt-6-luna / medium | Machine assignment purpose described as existing; assignment/E5 closed schemas absent; stale owner wording | Machine implementation held; Codex owns correction. Backlog now distinguishes candidate machine policy authorization, active human E5 and bounded delegated setup. Reviewer returned GO for independent runtime manifest/staging/transition. |
| s2_machine_security_design / security-reviewer / gpt-6-luna / medium | Same new-authority/schema gap; signed Store chain alone does not establish upstream authority | Candidate machine design remains unapproved and is being corrected. No production signer/key/activation is authorized. Pure schemas/read-only preparation require precise contracts first. |
| s2_phase4_writer / technical-writer / gpt-6-luna / low | Candidate machine acceptance needs explicit traceability; do not infer existing signed assignment events | Runtime plan aligned by functional-test-reviewer; machine implementation remains held until exact fields/verification are defined and reviewed. |
| s2_plan_align / functional-test-reviewer / gpt-6-luna / medium | Bootstrap-only test map must match absent configs, inactive units, UNKNOWN Store and per-path recovery | Updated TP-06 through TP-13 and actual machine adjudication boundary. Planning only, no executable tests or execution. |

## Bounded phase exit

GO to phase 6 for runtime manifest, explicit stage-only install, and separate bootstrap-only
transition. This is permission to implement reviewed design, not evidence that source exists or
runtime is verified. All services stay inactive, existing Store stays unopened, old artifacts
remain retained. Configured-host upgrades are refused. Keep machine issuer/E5 implementation
held until its candidate schemas are corrected; that independent hold does not stop runtime work.

No test/check/build/provisioning/activation was performed for this review. GPT-PM's architecture
reply is MODIFY (exact correlated evidence in s2-machine-authority-adjudication-20261029.md), not
overall S2 approval. Final exact-head code gate remains open. No approval files were hand-written.

## S2 exact-head code-coverage adjudication — current through 242f5d5

GPT-PM request `4986ec77-698e-4dd0-bdd9-7ca5c6281a46` reviewed base
`6117ba24b08a260b42402db6da0bf767864e1c04` through HEAD
`242f5d56f5b48603141d148d71d724bec7fb2b37`. The 5,876,444-byte input was
SHA-256 `f7685bce6b5e30c0e266f7e4eebf009d1f64ad9d8f6c4583a90241fbf9488b42`.
The correlated reply (job `c6ea42b2-462e-41a1-83a2-1632850c22c8`, reply
`541aa937-3513-570e-8b25-daaa99ae0854`) resolved S2-REVIEW-01 and found no confirmed
BLOCKER/MAJOR in the AF parser correction, but retained S2-REVIEW-02 as MAJOR/HOLD:
complete adversarial coverage of every changed source/test integration path was not
independently established. No exact-head approval was granted; Phase 8 remains unaccepted.

### Review coverage evidence

- The prior full-range S2 source audit is recorded in
  `docs/sdlc/evidence/s2-frozen-source-reviews-d3f326f-20261029.md`. It documents actual
  database-, security- and code-reviewer work through `d3f326f37a40936402d3933d5266e0ffb01017f0`,
  including the Store/issuance, dispatcher, Supervisor/RPC, Runner/sandbox, grant and
  trust-boundary integrations. It is inherited evidence from that review, not a new review
  performed in this turn.
- The current code-reviewer delta audit compared `d3f326f` to `242f5d5` and read all six
  changed `tools/` and `tests/` paths in full: `tools/af_attachment_review.mjs`,
  `tools/verify_s2_review_source_fidelity.py`, `tests/vst/test_af_attachment_review.mjs`,
  `tests/af/test_s2_attachment_adapter_e2e.mjs`,
  `tests/af/test_s2_review_source_fidelity.py`, and
  `tests/vst/test_s2_store_backed_pubsub.py`. It found no confirmed B/M in those deltas.
  The reviewer ran no tests and edited no files.
- A prior exact-range evidence note,
  `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md`, records a code-reviewer
  inventory and review of the 74 changed `tests/` and `tools/` paths in the exact range,
  including the 30 changed test/helper paths. This record is supplied for GPT-PM to assess
  together with the baseline and delta reports; it is not represented as work performed in
  the current turn.
- The focused exact-commit functional test is reported separately: 38/38 at code HEAD
  `0da595e6574856ed0c85a181941e822031b80787`. Review reports are not test results, and
  test reports are not GPT-PM approval.

### Superseding S2-1 disposition — current through 57c734e

The historical hold above was resolved for S2-1 source/test acceptance by correlated
GPT-PM request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` at submitted HEAD
`57c734e60787a9db14bb888116d7e808bc46970e`. GPT-PM accepted the baseline-plus-delta
coverage evidence for `S2-REVIEW-02` and reported no new confirmed BLOCKER/MAJOR. It
accepted the reported six-path continuity comparison but explicitly did not independently
reproduce it or execute tests. The decision is limited to S2-1 source/test coverage and does
not approve the full S2 sprint, runtime, production identity, E5, activation or restricted
selectors. Full disposition and limitations are in
`docs/sdlc/evidence/s2-1-coverage-adjudication-f92b750e.md`.

Codex recorded this decision and synchronized the affected task documents in pushed commit
`e332ec4` (change record 0586). S2-1 task delivery is complete; S2-2 is now the next queued
task. The separate S2 runtime and full-sprint acceptance limits above remain unchanged.


## S2 post-functional source reviews — current at d3f326f

Sprint: 39b7cc253f5d

Actual fresh-context database-reviewer, security-reviewer and code-reviewer ran
on gpt-6-luna medium after designated tests completed. Full declared new S2 source
was compared with origin/main, including bootstrap/issuer integration already in
the snapshot port; the small later fix delta alone was insufficient. Security
finished the additional owner/dispatcher/Runner/signer/latch/fence trust surfaces.
No confirmed code BLOCKER/MAJOR remains in those reviewed scopes. Detailed evidence
and manual-review limits are in
[evidence/s2-frozen-source-reviews-d3f326f-20261029.md](evidence/s2-frozen-source-reviews-d3f326f-20261029.md).
Reviewers ran no tests/checks/build/CI and wrote no source. Prior design/runtime
HOLD statements are historical; current source implementation/review is established,
while installed trust, service behavior, genuine current E5 and final Phase8 remain
separate. This record is not GPT approval and writes no approval artifact.


## Evidence file: test-plan.md (sha256 e5574dda828a4b640a330466b404ea76a9b0be407adea38f7e556c73d5680ece)
# S2 focused functional and runtime test plan

Sprint: `39b7cc253f5d` — active project sprint S2  
Status: planning only; S2 coding is still in progress. No tests were authored or executed for this plan.

## Purpose and evidence boundary

This plan maps future tests to the accepted S2 stories and numbered acceptance criteria in `docs/sdlc/backlog.md`. It covers the accepted Store-authorized path: `DispatchOwnerService` → authenticated Supervisor/Store admission → Store-filtered Pub/Sub → `StoreBackedDispatcher` → Runner. Store remains the only assignment and lease authority. It does not add another coordinator, scheduler, or assignment authority.

The recorded source/test evidence is bounded:

| Story | Recorded evidence | What it establishes | What it does not establish |
|---|---|---|---|
| S2-1, `S2-PROV-M03-R01` | GPT-PM source/test acceptance at `c855ca4`; the linked M03 run record reports 130 passed, 0 failed in Ubuntu 24.04 WSL with Python 3.12.3/pytest 7.4.4. | Source/test behavior for cross-generation historical-result recovery at that revision. | Installed runtime, systemd identity, kernel credentials, current-head equivalence, production issuer/E5, or full S2 acceptance. |
| S2-2 | GPT-PM transport request `b0f60d46-42b7-486a-b2f0-5d2253780f55`; PM Bridge job `68efb4e6-a296-4fd7-bcfc-2c6fe2568d5c` recovered correlated reply `d555b078-5647-46eb-bfc1-dd99654d634f` (`correlated=true`); source/test blobs delivered in pushed `e987a24`. `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` reports 34 passed, 0 skipped, 0 failed at HEAD `20fda2c`. | One local AF_UNIX socketpair request/half-close/EOF/response/ACK path through the real `DispatchOwnerService._handle()` method. | Live systemd socket activation, actual PID 1 credentials, kernel peer credentials, pidfd, socket filesystem metadata, provisioned identities/configuration, Store, Runner, or production owner-to-Runner behavior. Those properties were mocked or absent. |

These historical results are not rerun or promoted to current-head proof by this plan. Source/test acceptance of S2-1 and S2-2 is distinct from S2 runtime acceptance. S2-3's bounded inactive stage-only preparation and post-stage manifest identity are accepted and delivered in pushed commit `ae07f8708adcc7ef4f69505477ad6b72e3c912cf`. S2-4 remains blocked by `S2-DISPATCH-M01` (MAJOR/OPEN), S2-5 is pending, S2 is NOT APPROVED, and S3 remains unstarted (`docs/sdlc/backlog.md`, `docs/sdlc/requirements.md`).

## Execution order and ownership

1. The S2-3 immutable bundle/schema and inactive-stage implementation is source-complete for the accepted bounded task; mapped test-role evidence and the authorized stage-only run are recorded. Do not infer full transition/refusal-matrix coverage or activation acceptance from this result.
2. After coding is complete, `functional-test-reviewer` authors the focused source-level tests in this matrix. `e2e-runner` owns permitted runtime selectors and reports exact command, source HEAD, environment, and result. Neither role may convert a prohibited or unavailable scenario into a pass.
3. Run source-level cases first. Proceed to permitted runtime qualification only after the exact non-secret bundle has been reviewed by GPT-PM under the recorded conditional scope, required configuration/identities exist, and the Store has been read-only classified. Store disposition `UNKNOWN` blocks initialization; only a separately gated fresh schema-v6 Store may be initialized. Existing Store migration remains behind its separate gate.
4. Keep affected services inactive through bundle preparation and artifact transition. The initial transition is only for an unconfigured host: `/etc/vst-runner` and runtime socket directories must be absent; all six affected units/socket must be inactive, with no queued systemd jobs or populated VST cgroups. A configured host is refused; upgrades remain out of scope. Each individual rename is atomic; replacing the selector and multiple units is a recoverable sequence, not a single atomic transaction. Store `UNKNOWN` permits selecting already verified inactive artifacts because selection does not open or mutate Store data; it continues to block Store initialization, migration, activation, and dispatch.
5. GPT-PM's correlated architecture decision `a3e130f0-9aec-4304-b001-388a45c0be55` (reply `0b0b8a4d-0816-4166-ba21-71857b5de49d`) is `MODIFY — DESIGN ONLY`: bounded delegation contracts, pure validators, and read-only measurement collectors may be designed/implemented. Production signing keys/services, E5 contract replacement, and activation are not authorized. The findings `S2-MACHINE-ISSUER-M01` and `S2-MACHINE-E5-M01` remain open pending design and review. This decision is not runtime evidence. See `docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md`.
5. After mapped tests and permitted runtime evidence, relevant specialist reviews, and fixes, GPT-PM reviews the exact final head and correlated evidence. A changed head requires a fresh exact-head decision (S2-5 / REQ-006).

## Acceptance-mapped test matrix

“Existing” refers only to the cited historical source/test evidence. “Planned” means not yet authored or run. Runtime rows are conditional on their prerequisites. Every test must assert externally observable state (Store events/lease, selected link/unit bytes, process/unit activity, or actual Runner outcome), not just helper return values.

| ID / acceptance mapping | Future scenario and falsifiable assertion | Evidence layer / status | Owner and prerequisite |
|---|---|---|---|
| TP-01 — S2-1 AC-1; REQ-001/002 | For each unsigned, invalid-signature, expired, wrong-purpose, or mismatched request/task/slot/attempt/epoch/run/key binding instruction, assert rejection occurs before durable dispatch intent; Store assignment, lease, and event chain remain unchanged. Include a valid instruction as the positive control. | Existing source coverage is present in `tests/vst/test_s2_signed_dispatch_instruction.py` and related S2 source suite; specific scenarios/result must be reconciled to the accepted M03 test record. Do not claim installed-runtime coverage. | `functional-test-reviewer`; after source coding complete; use deterministic valid/invalid signed fixtures. |
| TP-02 — S2-1 AC-2; REQ-004 | Replay a previously accepted outcome after generation change: matching complete historical envelope returns only the immutable historical result from one verified snapshot; absent, mismatched, corrupt, or unresolved history fails closed. Assert no duplicate append, lease mutation, new grant/admission, or Runner launch. | Historical M03 source/test evidence: 130 passed at `c855ca4`; additional rerun only if changed code or exact-head regression requires it. Existing named source tests include `test_s2_operation_recovery.py` and `test_s2_persistent_runner_service.py`; their recorded outcomes are not assumed from filenames. | `functional-test-reviewer`; source change complete; disposable isolated Store fixture. |
| TP-03 — S2-1 AC-3 / S2-2 AC-3; REQ-006 | Evidence/reporting check: label source tests and mocks as source/test only; assert the report records exact test HEAD, command, environment, pass/skip/fail counts, and explicit unproven runtime properties. | Existing records are historical evidence; no new test needed unless evidence-generation code changes. | Codex reconciles records; GPT-PM adjudicates final exact-head claim. |
| TP-04 — S2-2 AC-1/2; REQ-002/003 | Valid one-frame request follows existing authenticated Supervisor/Store admission and Store-backed dispatch, with no assignment created by transport. For malformed, partial, duplicated, EOF/ambiguous, or response-loss cases, assert fail-closed outcome and no unsigned fallback or second request on the same connection. | Transport source/test acceptance is recorded: WSL `test_s2_dispatch_owner_transport.py`, 34 passed at `20fda2c`; actual local socketpair and `_handle()` path only. New coverage is conditional on code changes. | `functional-test-reviewer`; isolated socketpair and deterministic service fixture. |
| TP-05 — S2-2 AC-2; REQ-003 | On ambiguous admission/outcome, assert caller receives an explicit unresolved/fail-closed result and subsequent retry cannot duplicate durable dispatch or bypass Store filtering. | Planned regression coverage if the final code changes the ambiguity path; must not be inferred from the 34-case transport run. | `functional-test-reviewer`; source coding complete; injected deterministic response loss, no process-kill/crash scenario. |
| TP-06 — S2-3 AC-1; REQ-005/006 | Build a bundle from one exact source HEAD; assert manifest binds repository identity, full source HEAD, archive SHA-256, sandbox spec digest, six unit hashes, helper revision/source/binary digests, paths, schema, intended owner/group/modes, Store disposition, and transition baseline. Assert no secret bytes are present; changing a bound input changes validation. | **PASS — source/contract scope.** Focused WSL selection: 54 passed, 0 failed, 0 skipped at baseline `c97836029a5d94ff84dee5cb15d1757efd5525c3`; exact current committed-head replay remains pending. | Designated `functional-test-reviewer` coverage; executed by `e2e-runner` in bounded Ubuntu 24.04 WSL. Evidence proves fixture/source contract only, not an installed runtime. |
| TP-07 — S2-3 AC-1; REQ-005 | Reject missing/unknown fields, malformed digests/HEADs, and placeholder credentials. `UNKNOWN` Store rejects initialization, migration, and activation but does not by itself reject inactive artifact selection, which neither opens nor changes Store data. Existing Store must never silently become `FRESH`. | **PASS — tested schema/source-plan rejection subset.** Same 54-case focused run. No Store was opened or mutated; production Store initialization/migration behavior is not claimed by this selection. | `e2e-runner` executed the designated fixture suite; GPT-PM exact bundle review remains pending. Do not mutate or initialize a real Store in unit tests. |
| TP-08 — S2-3 AC-2/3/4; REQ-005 | An unreviewed/changed bundle fails authorization preconditions. Fresh schema-v6 Store initialization is permitted only under its explicit reviewed gate; existing/unknown Store cannot initialize or migrate. Assert no issuer key or E5 signature is synthesized. | **PARTIAL — artifact review-pin and inactive-selection contracts covered by fixtures;** no Store initialization/migration, key generation, signing, or E5 use was attempted or proven. | GPT-PM owns exact bundle adjudication; Codex preserves no-activation/no-secret limits. Any Store/key/E5 runtime acceptance remains separate. |
| TP-09 — S2-3 design acceptance; REQ-005/006 | Install only absent immutable destinations with no-replace semantics. Verify exact artifacts and owner/group/mode/digests; collisions or mismatches refuse without overwrite. Old runtime/helper remain intact. | **PARTIAL — fixture/source regressions pass; the authorized real Ubuntu-24.04 WSL stage-only run succeeded** and published the exact versioned runtime/helper, with manifest tree/helper digests and preserved old selector/unit baselines accepted by GPT-PM (`ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4`). A live collision case was not exercised. | Codex owns the recorded bounded stage and evidence. No selector or fixed-unit mutation is authorized. Collision refusal remains established only by fixture/source coverage, not a live collision experiment. |
| TP-10 — S2-3 design acceptance; REQ-005/006 | Bootstrap transition refuses configured hosts (`/etc/vst-runner` or runtime socket dirs exist), active affected units/socket, queued systemd jobs, populated VST cgroups, stale selector/unit fingerprints, unresolved claims, unverified artifacts, or collisions. Assert all baseline bytes remain unchanged on precondition failure. Store `UNKNOWN` alone does not reject artifact-only inactive selection. | **PARTIAL — fixture tests cover selected stage preflight config/inactive/job/cgroup guards and bootstrap stale/unverified-artifact checks;** the full listed refusal/error matrix is not independently certified. The authorized stage run and its fresh inventory established only the real target's safe baseline at execution, not the entire negative matrix. | `e2e-runner` owns fixture test execution; Codex owns non-secret run evidence. Keep untested refusal/error cases partial; do not exercise prohibited mutation/crash cases. |
| TP-11 — S2-3 design acceptance; REQ-005/006 | In an unconfigured disposable host model with exact old/new runtime and helper fingerprints, install the new immutable artifacts and replace selector plus six fixed-name units through individually atomic renames. Assert final digests match the reviewed manifest, prior artifacts remain, and no enable/start occurs. Do not assert multi-path atomicity. | **PASS — disposable-host model only.** Focused bootstrap tests verify selector/unit replacement and that service start/reload is false; no live runtime was selected. | `e2e-runner`; actual stage-only operation still depends on fresh exact bundle approval and inventory. |
| TP-12 — S2-3 design acceptance; REQ-005/006 | Inject failures between selector/unit renames. Assert a durable journal records completed steps, services remain inactive, and recovery restores each exact prior selector/unit byte set and hashes or fails closed for read-only recovery. Retain new immutable artifacts. | **PASS — deterministic injected exceptions and recovery only.** Real process-kill/crash/power-loss remains prohibited and `NOT_RUN`. | `e2e-runner` ran the focused fixture selection; no real crash or production filesystem test. |
| TP-13 — S2-3/S2-4 boundary; REQ-005 | Preparation/transition never start/enable services, create/activate issuer keys, sign/replace E5, enable dispatch, or mutate/migrate Store. Assert no such command/write occurs. `UNKNOWN` Store blocks all Store-changing and activation actions. | **PARTIAL — fixture evidence reports services_started_or_reloaded=false; the real stage-only result reports `selected=false`, `selector_unchanged=true`, and `systemd_units_installed=0`.** Store, service identity/configuration, issuer key, E5, and dispatch were not touched. Live activation and Store behavior remain unverified. | Codex records the exact non-secret stage evidence. The accepted candidate manifest is not an activation permit; production behavior remains separately gated by exact authorization and fresh run-bound evidence. |
| TP-14 — S2-4 AC-1/4; REQ-003/005 | Conditional permitted runtime journey: from a genuinely authorized owner request through the installed authenticated endpoint and existing Supervisor/Store/filter/dispatcher to the real Runner. Capture exact HEAD, systemd identity, root-controlled config, current run-bound provenance, selected E5 format/binding/nonce/spec digest, Store assignment/lease, and Runner result. Positive result must correspond to one authorized assignment. | **NOT_RUN / blocked.** Current transport test does not reach systemd, Store, or Runner. `S2-DISPATCH-M01` remains MAJOR/OPEN. | `e2e-runner` executes only after exact bundle review, accepted authorization format/policy, provisioned identities/configuration and current run-bound evidence. Current human E5 v1 remains mandatory unless a separately reviewed/approved machine format is explicitly selected. Operator owns the exact production policy authorization/reserved custody; Codex gathers permitted evidence; GPT-PM adjudicates. |
| TP-15 — S2-4 AC-2; REQ-001/003/005 | In the permitted runtime journey, refuse missing/unauthenticated issuer or trust key, wrong owner, expired/revoked/badly bound instruction, stale lease/epoch/generation, mismatched payload, duplicate, or ambiguous result. Assert no unauthorized/duplicate Runner execution and Store authority remains unchanged. | **NOT_RUN / blocked** until TP-14 prerequisites. No synthetic identity may be reported as production acceptance. | `e2e-runner`; same prerequisites as TP-14. Synthetic negative fixtures may be used only within the separately accepted mapped test scope and must be labeled synthetic. |
| TP-16 — S2-4 AC-3; REQ-006 | Report restricted process-kill, crash/recovery, mutation, E8, and policy selectors exactly as `NOT_RUN`; assert no skipped/synthetic result is counted as pass. | **PROHIBITED — NOT_RUN.** No execution or test authoring for these selectors. | Codex preserves this status in the evidence record; no test-role execution. |
| TP-17 — S2-5 AC-1/2/3; REQ-006 | After all accepted evidence and fixes, reconcile the final Git HEAD with the exact test commands/results and reviewer evidence; any subsequent code change makes approval stale. Verify acceptance record distinguishes accepted source/test stories from carried runtime/gates. | Planned closure evidence, not an executable test. No final overall GPT-PM approval recorded. | Codex assembles exact-head evidence; GPT-PM owns final exact-head approval. S2 remains NOT APPROVED and S3 unstarted until approval/acceptance. |

## Explicitly prohibited or unavailable coverage

The following remain `NOT_RUN`, not pass, skip, waiver, or implied coverage:

- Process kill, crash recovery, mutation, E8, and all restricted policy selectors (S2-4 AC-3; REQ-006).
- Real systemd/PID 1 peer authentication, production credentials/keys, current signed E5, and installed production configuration until their genuine prerequisites and separate authorization exist.
- Existing Store migration and production service activation/dispatch. Store disposition is currently `UNKNOWN`; do not infer that it is fresh.
- Any scenario that would create/impersonate an issuer or trust key, fabricate an operator-root signature, overwrite/delete an existing runtime/helper, or create a second assignment authority.
- GPT-PM permits bounded delegation-contract design, pure validators, and read-only measurement collectors only; production signing keys/services and E5 contract replacement remain unauthorized (`docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md`).

If a permitted scenario cannot run, record `NOT_RUN` with the exact unavailable prerequisite/error, revision, and owner. Never replace it with a synthetic pass. Test evidence is complete only for the mapped acceptance criterion and exact revision that the test actually exercised.

## References

- `docs/sdlc/requirements.md` — REQ-001 through REQ-006, constraints, and current blockers.
- `docs/sdlc/backlog.md` — S2-1 through S2-5, numbered acceptance criteria, current disposition, and DoD.
- `docs/sdlc/design.md` — exact bundle, inactive revision transition, rollback, and activation boundaries.
- `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` — exact transport command, revision, environment, result, and limitations.
- `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md` and linked `s2-cross-generation-outcome-recovery-test-run-20261029.md` — M03 source/test acceptance and limits.
- `docs/sdlc/evidence/s2-runtime-bundle-inventory-20261029.md` — point-in-time WSL inventory; not provisioning or current E5 acceptance.
- `docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md` — correlated design-only machine authority ruling; not production signer authority or runtime evidence.
- `docs/sdlc/evidence/s2-assignment-basis-functional-run-20261029.md` — focused synthetic assignment-basis source tests, exact run command/result, freshness defect/fix, hashes, and evidence limits.

### Additional source-contract coverage for the active S2 candidate scope

These cases extend TP-06 through TP-13 and trace the GPT-PM bounded source authorization to
REQ-005/006 and S2-3/S2-4. The machine schemas remain candidate contracts; the bounded V2
validator and root-Supervisor comparison source slice is now implemented and its focused tests are
recorded in `evidence/s2-4-v2-authorization-source-20261030.md`. This does not authorize a signing
route, production trust, activation, dispatch, E5 replacement, or full S2-4 acceptance.

| ID / acceptance mapping | Focused falsifiable assertion | Layer / status | Owner / prerequisite |
|---|---|---|---|
| TP-18 — S2-3 AC-1; REQ-005/006 | `prepare_wsl_runtime_plan.py` accepts only canonical repository root and exact committed 40-hex HEAD. Repeated preparation over unchanged HEAD produces identical canonical bytes and binds archive/spec/all six unit/helper source+build recipe hashes; changed HEAD or absent required archive member refuses. Assert it labels compiler, target inventory and binary digest UNKNOWN, creates no file, and emits no approval/activation claim. | **PASS — fixture/source-contract subset.** The 54-case selection exercised deterministic plan output, identity/path refusals and required-member checks. Exact committed source plan was not generated as part of this test run. | `e2e-runner` executed the designated selection; Codex separately generates an exact committed-head plan for review. |
| TP-19 — S2-3 AC-1; REQ-005/006 | `runtime_bundle.validate_manifest` rejects missing/unknown/duplicate fields, bool-as-int, malformed digest/HEAD/path, inconsistent expected helper identity and unsupported old/current selector/unit fingerprint shapes. Canonical manifest hash remains stable. | **PASS — fixture/source-contract scope.** Valid, malformed, extra-field, boolean-metadata, helper-identity, link-count, and parent-shape cases passed in the 54-case selection. | `e2e-runner`; no real filesystem identity was modified by these fixture tests. |
| TP-20 — S2-3 AC-2/3; REQ-005/006 | Stage-only preflight refuses each present config/socket sentinel, active/activating/failed/unloaded unit, malformed/failed systemd job inventory, affected queued job, unreadable/nonempty cgroup, and cgroup symlink. Parse list-jobs as JOB/UNIT/TYPE/STATE. Positive fixture has inactive loaded units or documented not-found and empty/no cgroups. | **PARTIAL — selected stage-guard fixtures passed** for config sentinel, inactive state, affected queued job, and populated cgroup cases. The full listed state/error matrix is not certified by this selection. | `e2e-runner` executed fixture-backed POSIX tests. The real WSL service state remains unobserved by this result. |
| TP-21 — S2-3 AC-2/3; REQ-005/006 | Direct distro `--stage-only` invocation repeats the host predicates; valid stage retains exact immutable runtime/helper, reports selected=false and units-installed=0, and never reads/writes selector or fixed units. Existing exact versioned artifact is idempotent; matching schema-3 marker is accepted and a changed inventory/source identity refuses without overwrite. | **PARTIAL — direct existing-runtime verifier regression PASS** on committed source: 4 passed, 8 deselected, 0 skipped (`evidence/s2-3-existing-runtime-regression-043980f.md`). Separately, the authorized Windows-to-WSL stage-only handoff successfully published the exact immutable artifacts and the resulting manifest was accepted; it is recorded in `evidence/s2-3-stage-only-ef465cd.md` and `evidence/s2-3-post-stage-manifest-review-ac2d25a2.md`. No live collision or changed-inventory refusal was induced. | `e2e-runner` owns fixture regressions; Codex owns the bounded stage evidence. Do not repeat or broaden the runtime action without its own authorization. |
| TP-22 — S2-3 design; REQ-005/006 | `bootstrap_runtime` preparation hashes complete staged runtime/helper plus old selector and six unit fingerprints without mutation; rejects manifest digest mismatch and configured host. Apply requires external exact manifest digest, current pristine bootstrap conditions and retained journal, changes each path by individual rename, verifies all new bytes/metadata, emits no start/reload. | **PASS — disposable host model only.** Manifest pin, staged artifacts, selector/unit replacement, no-start result, preflight and journal behavior passed. | `e2e-runner`; fixture path mapping prevents access to real `/opt`, `/etc`, `/run`, Store and systemd. |
| TP-23 — S2-3 design; REQ-005/006 | Inject ordinary exceptions before/after each rename, fsync, and journal state update. Recovery compares every path with old/new digest irrespective recorded state; restores exact old values or absence and retains new artifacts. Any third-party bytes cause zero recovery writes. Successful group replacement is never asserted collectively atomic. | **PASS — tested deterministic injected exceptions and partial journal/retained-copy recovery.** Process kill, power-loss and real crash recovery remain prohibited `NOT_RUN`. | `e2e-runner` executed fixtures only; no real root paths, systemd, WSL runtime, or Store used. |
| TP-24 — S2-3/S2-4 candidate delegation; REQ-005/006 | `machine_authorization` exact policy and external assignment validators bind operator key purpose, separate authorization signer key and intended machine issuer key, project/repo/sprint/manifest, principal, task tuple, expiry/revocation. Mismatch, stale current Store snapshot, wrong purpose, unknown field or duplicate key fails closed. Test signatures only with synthetic public/private fixtures; do not connect signing service. | **PASS — bounded source tests.** Windows: 2 passed, 11 POSIX cases skipped. Ubuntu-24.04 WSL: 13 passed, 0 skipped (`evidence/s2-4-v2-authorization-source-20261030.md`). Includes closed schemas/downgrade refusal, purpose separation, synthetic signatures/revocation/scope, root Supervisor provider boundary, internally obtained Store tuple and fail-closed refusals. | `functional-test-reviewer` authored and executed the mapped tests. Synthetic keys and disposable Store only. This does not prove production authorization, issuer signing, dispatch, E5 or runtime. |
| TP-25 — S2-3/S2-4 machine observation candidate; REQ-005/006 | `machine_observations` accepts only exact raw-bundle and source schema; duplicate/missing source, incomplete command, changed hash, unsupported platform, malformed type, inconsistent host/WSL metadata return UNKNOWN/INCOMPLETE/UNSUPPORTED. `OBSERVATIONS_COMPLETE` means schema collection completeness only; there is no PASS output or route into current Supervisor human E5 verifier. | Planned pure fixture test; collector not executed. | Same owner after source freeze. Never collect host observations as a test, sign E5, replace v1, create keys, or assert production. |
| TP-26 — S2-3 exact reviewed source and staged tree; REQ-005/006 | V2 source plan records every Git archive member path, type, byte length, and SHA-256. Bundle verifier rejects modified, missing, extra, hard-linked, symlink, or special members despite unchanged review pins. Before runtime publication, stage verifier compares the complete tree and marker to that exact source map, rejecting unexpected links/types and changed bytes. Inventory is source-head-bound and at most 300 seconds old on Windows and after WSL receipt; helper compiler selector, resolved path, owner/group/mode, and binary digest must match it. | **PASS — focused fixture/source-contract subset.** Exact member-map and stage-tree comparisons rejected modified, missing, extra, hard-linked, symlink and special files; source-plan freshness/compiler binding cases passed. This does not constitute target inventory or real stage proof. | `functional-test-reviewer` authored; `e2e-runner` executed. Fresh exact-head source plan/inventory review remains before any real stage. |

No tests, checks, provisioning, migration, service activation, or production dispatch were performed for this planning artifact. The focused assignment-basis candidate tests and their exact results are recorded separately below; they do not establish production authentication or runtime acceptance.

### Authenticated assignment-basis candidate source tests

At source HEAD `3d5f6c2048238a79fb92ddf805bc562b4b392a63`, the read-only assignment-basis candidate source is present. The focused tests use disposable SQLite state and synthetic journal rows that model a future writer; they do not prove that an authenticated production assignment writer, trusted root policy, issuer peer, or current production provenance exists.

| ID / acceptance mapping | Focused falsifiable assertion | Evidence layer / status | Owner / prerequisite |
|---|---|---|---|
| TP-26 — S2-3/S2-4 candidate; REQ-005/006 | For one exact synthetic operation ID, resolve the canonical handoff and current task/owner/lease/probe basis, return the closed response, and show the query uses one locked Store read snapshot and changes no table, event, operation, lease, probe, or other DB state. | `tests/vst/test_s2_assignment_basis.py`: 21 passed as part of the final 23-test command at source `3d5f6c2`. | `functional-test-reviewer`; synthetic fixtures only. No production writer, issuer, key, or authority claim. |
| TP-27 — S2-3/S2-4 candidate; REQ-005/006 | Refuse malformed/unknown or legacy operation IDs; mismatched task-manifest, policy, principal, payload, row/event actor or duplicate event; stale epoch/lease/probe/runner; changed/missing/expired root policy; wrong RPC role or caller-selected request fields. Also refuse otherwise valid unexpired handoff/probe data from a previous Supervisor run or service generation instead of relabeling it with the current generation. | Final focused run passed. The previous-run defect was reproduced at `c2b1cd2` (one test failed with `DID NOT RAISE`) and fixed at `3d5f6c2`; both prior-run and prior-generation regressions pass on the fix. | Codex owns source correction; `functional-test-reviewer` owns focused tests. No production authentication or runtime claim. |
| TP-28 — S2-1 regression; REQ-001/005 | Keep existing `execution_grant_basis` and verified startup-history semantics intact while using the extracted locked helper. Run only named safe selectors exercising those paths; do not select entire runtime/service test files. | The final command included `test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt` and `test_store_refuses_preflight_consumption_before_verified_startup_history`; both passed. A four-file S2-1 recovery regression at code HEAD `56cd816` exposed a direct-Store fixture missing `key_fingerprint`; after supplying the trusted synthetic fingerprint, that selection passed 130/130 at both `56cd816` and exact HEAD `2befed5`. Commit `dcb5d63` contains the corrected fixture. Exact current-head command, environment, hashes, and limitations are in `docs/sdlc/evidence/s2-exacthead-review-2befed5-20261029.md`. | `e2e-runner` executed the focused WSL selection. No full suite or restricted runtime scenarios. Current-head source/test execution does not establish installed runtime or exact-head GPT-PM approval. |
| TP-29 — S2-1 exact-review source fidelity; review evidence integrity | For the immutable review attachment, bind exact full base/HEAD and attachment size/SHA-256; match the complete attachment diff to the exact raw Git diff; map each redaction through ordered hunks to exact blobs and lines; fail closed on tampering; preserve CRLF and embedded fences; emit no source values or per-line fingerprints. | `tests/af/test_s2_review_source_fidelity.py`: 5 passed via `python tests/af/test_s2_review_source_fidelity.py -v`, with committed-baseline HEAD `2befed5515455c4dbf022cad68e839a8a2ce799c`; verifier and test file were uncommitted at execution. The run mapped all 41 markers across 15 files. Full provenance, test hash, and limits: `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`. | Source fidelity and static invariant review are evidence for GPT-PM re-adjudication; they are not GPT-PM approval, runtime evidence, or authorization to push. | Focused tests are fixture/offline and use the exact local PM attachment; they do not prove production behavior. | `functional-test-reviewer` authored/executed focused tests; Codex owns implementation/evidence; GPT-PM owns re-adjudication. |
| TP-39 — S2-1 exact-head AF correlation; REQ-006 | For a correlated PM Bridge response with the exact `ChatGPT said:` transport wrapper, require a leading UUIDv4 `REQUEST_ID` that exactly matches persisted intent before accepting one top-level verdict. Reject wrapper without ID, mismatched/duplicate/malformed IDs, arbitrary wrapper/preamble, missing/repeated verdicts; mismatch must not create a receipt or approval artifact. | `functional-test-reviewer`: `node --test tests/vst/test_af_attachment_review.mjs`, 38 passed, 0 failed/cancelled/skipped at exact committed HEAD `0da595e6574856ed0c85a181941e822031b80787`, duration 149843.3314 ms. Tester verified test and adapter Git blobs matched before/after; no tracked edits. Full output, environment, hashes, PM response and limits: `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md`. | Test/regression evidence is exact-head; separate GPT-PM S2-1 coverage adjudication is request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db`. | S2-1 source/test coverage was accepted narrowly; runtime and full S2 approval remain separate. | `functional-test-reviewer` owns execution; Codex owns adapter/evidence; GPT-PM owns review decision. |

### Fresh bootstrap and integrated I01 issuer source contract (S2-3/S2-4 candidate)

These cases derive from accepted S2-3 AC-1/4, S2-4 AC-2/3, the fresh-only bootstrap contract in change0552, and I01-SRC-01 through I01-SRC-05 in the correlated GPT-PM source adjudication. They are planned only: the assigned source batch is still in progress. No test code or execution is authorized until Codex records the final S2 source freeze and gives the test-role GO. Use disposable SQLite/filesystem/RPC fixtures and synthetic keys only where a signature-format test is essential; never provision or activate a real root key or run production requests.

| ID / acceptance mapping | Focused falsifiable scenario and observed contract | Original epic trace | Layer / state / owner and prerequisite |
|---|---|---|---|
| TP-29 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | Through the Store transaction boundary, start with a valid fresh synthetic policy/request and assert one complete bootstrap: story/task, exact manifest budget (including `cost_cap=0`, `spent=0`), epoch advance, attempt-1 lease, handoff, immutable operation and linked event all commit together. Inject each deterministic pre-commit validation failure and assert the database snapshot is unchanged across every affected table/event. A failure before commit must not leave a partial assignment. | E6 (Store isolation/assignment boundary); E7 (durable lifecycle/idempotency). | Disposable SQLite integration fixture; planned, not authored/run. `functional-test-reviewer`, after root's explicit final S2 code-freeze GO. No real Store. |
| TP-30 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | Repeat the exact bootstrap operation/request and assert the byte-identical stored result is returned with no additional task/story/event/lease/handoff/operation effects. Reuse the operation identity with changed request, policy digest, peer identity or manifest and assert conflict/refusal with no state change. | E7 (idempotency and duplicate-effect prevention). | Disposable SQLite integration fixture; planned, not authored/run. Same owner and freeze gate. |
| TP-31 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | For each prior-history condition (existing story/task, relevant event, lease, receipt, budget row, terminal marker, handoff, or noninitial attempt), assert bootstrap refuses rather than adopts, resumes, retries, renews or switches assignment; assert preexisting bytes/state are preserved. Include valid pristine state as positive control. | E6 (assignment isolation); E7 (replay/recovery safety). | Disposable SQLite boundary fixture; planned, not authored/run. Same owner and freeze gate. No manually seeded state may be described as proof of process-crash behavior. |
| TP-32 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | At exact cost boundary, prove a zero-cost manifest bootstraps with `cost_cap=0` and `spent=0`; separately exercise over-cap/invalid budget and exhausted-attempt/occupied-slot inputs and assert refusal with no partial state. Preserve the documented existing `spent > cap` rule; do not silently substitute `spent >= cap` or change legacy `acquire_lease` behavior. | E6 (budget and lease invariants); E7 (valid transition boundaries). | Disposable SQLite integration fixture; planned, not authored/run. Same owner and freeze gate. |
| TP-33 — S2-4 AC-2; REQ-001/005; I01-SRC-03/04; issuer design key-class contract | With synthetic trust material, assert immutable key class/purpose/fingerprint binding survives restart/read verification. `LEGACY_V1` retains its accepted path; `DELEGATED_V1` requires a fully correlated verified issuance; missing/unclassified, purpose mismatch, fingerprint drift, altered class, missing/corrupt/mixed-family journal or attempted downgrade fails closed. Observe admission refusal and unchanged assignment/lease/event state. | E1 (key/signature boundary); E3 (durable integrity/reconciliation); E7 (fail-closed lifecycle). | Store/Supervisor source integration with disposable journal; planned, not authored/run. `functional-test-reviewer` after source freeze. No real root key, provisioning, or runtime signing. |
| TP-34 — S2-4 AC-2; REQ-001/005; I01-SRC-01/03/05; issuer journal contract | For one immutable assignment-operation identity, assert reserve creates exactly one INTENT and only one caller can durably create STARTED; the signer-call seam is reached at most once for that identity. Exact frozen replay before STARTED can proceed only under the defined same identity; after STARTED, an absent completion reduces to UNKNOWN and retry does not call signer again. Changed handoff, policy, run, generation, key, expiry or unsigned bytes is CONFLICT. | E3 (journal integrity); E7 (idempotency and ambiguous external outcome). | Deterministic Store integration plus injected signer-call counter, planned, not authored/run. Same owner/freeze gate. Do not kill/terminate a process or claim literal crash proof from seeded journal rows. |
| TP-35 — S2-4 AC-2; REQ-001/005; I01-SRC-01/03; grant provenance binding | Persist exact signed grant bytes and assert their operation and accepted dispatch identity link to the same completed issuance and immutable handoff. Exercise exact grant replay, altered bytes, absent/mismatched linkage, and issuance/payload collision; only exact replay succeeds, with no second durable grant/admission or Runner authority. | E1 (authorization binding); E6 (assignment-to-execution provenance); E7 (duplicate/recovery behavior). | Store/Supervisor integration using synthetic signature fixtures and outcome assertions; planned, not authored/run. Same owner/freeze gate; no real signing. |
| TP-36 — S2-4 AC-2; REQ-001/003/005; I01-SRC-02/04; admission transaction | For both new delegated admission and exact replay, make current task/owner epoch, lease, manifest, attempt/receipt gap, consumed probe, active run, service generation or current policy stale/mismatched. Assert both branches refuse within the transaction and leave Store state unchanged; valid current authority admits exactly once. Historical replay may return only the persisted fact and cannot create execution authority. | E1 (dispatch verification); E6 (atomic admission); E7 (idempotent replay). | Store transactional integration, planned, not authored/run. Same owner/freeze gate. |
| TP-37 — S2-4 AC-2; REQ-001/003/005; I01-SRC-01/04; grant and Runner boundaries | At grant persistence, grant replay, durable Runner claim and reservation seams, independently stale or change current policy/revocation, generation, key registry, run/probe, lease/owner, or exact grant-to-issuance link between earlier read and write. Assert the same connection-taking current-authority predicate is re-evaluated at each write boundary and no grant/claim/reservation is written on failure. Positive control reaches only the authorized matching boundary. | E1 (authority); E6 (Runner execution boundary); E7 (claim/replay consistency). | Store/Supervisor/Runner source integration with deterministic transaction seam; planned, not authored/run. Same owner/freeze gate. |
| TP-38 — S2-3/S2-4 AC-2; REQ-005/006; I01-SRC-04/05; issuer service boundary | Assert issuer configuration is absent/default-off by default and exposes no issuance route; when explicitly configured in an isolated RPC fixture, only the exact authenticated `delegated_issuer` role and operation-ID-only request can reach the bounded root operation. Wrong role, extra caller-selected task/policy/key/run fields, malformed operation ID or disabled feature refuses without Store/signing effects. Root policy/key purpose separation and immutable source-derived tuple remain observable. | E1 (identity and capability boundary); E2 (service/RPC isolation); E6 (authority boundary). | RPC integration fixture, planned, not authored/run. Same owner/freeze gate. No real process identity, root policy install, key provisioning or activation. |

**Coverage limits and execution boundary:** These planned cases are source-level or disposable-fixture contracts. They do not prove real process-kill/crash recovery, host filesystem durability under power loss, systemd/PID 1 credentials, production root-key custody, real root signing/provisioning/activation, E5, or a production owner-to-Runner journey. Those remain `NOT_RUN`; process kill/crash, mutation, E8 and restricted policy selectors remain prohibited. Never seed `STARTED`/`UNKNOWN` rows and call that literal runtime crash proof. After source freeze, the functional-test-reviewer and e2e-runner may finalize exact node selectors against stabilized APIs; no E2E/runtime selector is authorized by this planning update. Existing TP-01–TP-28 and historical result records remain unchanged and are not promoted to the current source head.

### TP-39 — S2-4 real peer identity on the configured Python runtime

REQ-003/005: missing Python SO_PEERPIDFD spelling must not be mistaken for absent Linux x86-64
kernel ABI support. Native positive constants remain preferred; malformed/explicit None values,
fake adapters without the option and unverified ABIs fail closed. Actual peers must still yield
real valid pidfds and satisfy the unchanged credential/cgroup/liveness guards.

functional-test-reviewer: 11 new resolver cases plus 34 unchanged transport cases passed in WSL
(45 total); e2e-runner: real getsockopt returned a pidfd whose fdinfo PID matched SO_PEERCRED,
with an alive poll. Worktree baseline 5318743, not eventual committed-head execution. Exact
commands/hashes and limitations: evidence/s2-peer-pidfd-functional-5318743.md and
evidence/s2-peer-pidfd-runtime-capability-5318743.md. Full services/runtime journey remain
unexecuted by these tests. Restricted scenarios remain NOT_RUN.

### TP-40 — S2-4 exact runtime-config bundle and truthful command evidence

REQ-003/005/006: validate the exact config/task/policy/bootstrap/model/helper/source hash graph,
root/role ownership plan, secret exclusion, local-review identity limits and fail-closed
preflight entrypoint. The exact inline pytest adapter may emit PASS IDs only for genuinely
successful setup/call/teardown reports; failed, skipped or xfailed items must not manufacture a
PASS. Exercise the existing trusted parser against captured output and require its exact executed
ID; a `.PASS` progress-prefix or substring-only assertion is insufficient. Disable bytecode/pytest
caches so command evidence does not dirty the read-only snapshot.

Actual commands/results and first-run failures are recorded by the designated test role in
evidence/s2-runtime-config-functional-a600774.md. Unit parsing and diagnostic limits are in
evidence/s2-runtime-config-unit-verification-a600774.md. At baseline HEAD
`002e3617d51ed782fb46a63e9d7266696a6298e8`, the functional-test-reviewer ran the final focused helper/config
suite after the bounded root-to-worker identity-settling change, shared-deadline fix and retired-tuple
regression: 93 passed, one existing pytest-asyncio deprecation warning. Coverage includes decreasing
timeouts for nested systemd commands, deadline exhaustion, worker-first late validation, and refusing
the consumed tuple before marker creation. This is source/fixture evidence, not runtime proof. The
separately authorized attempt for run
`s2-runtime-20261030-334296bd0779488d837a27e283b50b6a` consumed its durable claim and failed before
root preflight; no TestRun occurred. That tuple is retired. Candidate
`s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910` later received two bounded inventory
authorizations (request `c84a91af-1ce6-4a55-9ce7-eed30c64ba66` and replacement request
`9357ee74-c0ac-4ed4-9568-1b4a192bf874`); the first inventory failed before collection and the second
was incomplete. Neither reached configuration apply, root preflight, claim/probe, or TestRun. Both
inventory invocations are consumed and the candidate remains unapplied/unclaimed. Actual
owner/Store/dispatcher/Runner qualification remains open for S2-4 AC-1. Restricted scenarios
remain NOT_RUN.

The worker identity-settling subtask's final focused helper/config suite reports 93 passed at
pre-delivery HEAD `002e361`; it does not prove runtime behavior. The permitted candidate's first
inventory attempt failed before collection with `D_MOUNT_NOT_9P_RO`. A separately authorized
replacement read-only inventory verified D: / 9p / `ro,relatime` and returned exit 0, but omitted
required PID1 identity, `vst-runner`, systemd-version, exact 26-file baseline comparison, and
verbatim JSON persistence. The full result is `evidence/s2-runtime-owner-runner-qualification-9357ee74.json`.
The dedicated inventory-validator test now reports 31 passed, one existing deprecation warning,
including validator-to-payload integration and the remote octal-mode parse contract; this is
code-level fail-closed evidence only. Neither target attempt reached configuration apply, root preflight,
probe/claim, or TestRun. Both inventory authorizations are consumed; the candidate remains
unapplied/unclaimed. A fresh exact-head runtime authorization is required before the e2e-runner
performs another inventory. Restricted process/crash/mutation/E8/policy selectors remain NOT_RUN.

The separate authorization for HEAD `f9f488f` permitted exactly one fresh inventory. Its raw JSON
is `evidence/s2-runtime-target-inventory-f9f488f.json` (SHA-256
`d4dc31bcd0eb97478677a844b80c2f7ccfbb9d176a8197b52c4a7ea7cdb340a9`). The verifier ran once and
refused because of a stale applier SHA pin; no apply, root preflight, claim, or TestRun occurred.
The captured PID1 record also shows collector path `/proc/1/ns/mount` returned FileNotFoundError;
the required proc path is `/proc/1/ns/mnt`, and PID1 UID/GID arrays were consequently not captured.
Both the inventory and verifier slots under that authorization are consumed. The code now derives
applier/verifier hashes from exact HEAD blobs and checks worktree equality; 31 focused tests and local
code/security reviews pass. A new exact-head authorization is required after the correction is
committed/pushed, followed by one fresh corrected inventory. See
`evidence/s2-runtime-owner-runner-qualification-f9f488f.json` and
`../changes/0617-s2-runtime-inventory-source-pins.md`.

**Current S2-4.12b update:** GPT-PM exact-head request
`cf7a9515-0cd8-47d2-a0cb-1c351a3ef1e0` found MAJOR-01: six validator-required fields were absent
inside `readiness`, although present at inventory top level. The production collector now routes
the same captured values through one `assemble_inventory()` function and persists both copies.
The prior 35 collector-helper tests did not prove this real collector-to-validator contract. The
functional-test-reviewer added a focused integration regression that invokes the real
`validate_inventory`, including missing and contradictory nested values. It returned 52 passed,
one existing pytest-asyncio deprecation warning, exit 0, Python 3.14.3 at HEAD
`1a7dca5527dbe48324426f9b5f56621e85a6279b`. Updated test-contract code review found no actionable
B/M issue. The tester reran the focused command at committed HEAD
`b927a438a72d14a31229c9d0ad7514a19606c98e`: 52 passed, one existing deprecation warning, exit 0.
A subsequent task-record-only amendment changed no collector or test bytes. Request remediation
approval for the exact committed HEAD
and source bytes, push normally, and request one fresh runtime authorization. Do not reuse either
consumed authorization or begin S2-5 first.

The first fresh authorization `53f946da-755c-4859-adca-6bfd64fb2293` / reply
`09ac688e-5ded-5b7b-aa9c-5e6a69e13ff7` at HEAD `2e6a796` produced inventory
`7a7e97b1e9a7dedbfd57592c3df66fea7ff6847c0a6ff3e77d6e49abd5b168d0`; the verifier refused
because `readiness.units` was omitted. No apply, root preflight, claim/probe or TestRun occurred.
The exact inventory and authorization transcript are the `2e6a796`-suffixed evidence files.

The replacement GPT-PM authorization `a2bd39ce-8ae4-4416-9b82-56382a610c92` / reply
`80091d4f-cbf2-5c72-af15-7ef9a48020bf` permitted one inventory and one verifier on exact HEAD
`2e6a796eaa04664812cf1266322b083f18770fa1`, followed only by conditional apply, root preflight,
and one report-bound TestRun. The inventory SHA was
`acb6b116aa66f4ba764a9e7c9ad505b90574323ed16129a71a61a970956e151c`; the validator ran once and
refused because `readiness.runtime_selector` was omitted from the persisted inventory even though
the observed top-level symlink matched. Apply, root preflight, claim/probe and TestRun were
`NOT_RUN`; the authorization is consumed. Full records are
`evidence/s2-runtime-target-inventory-a2bd39ce.json` and
`evidence/s2-runtime-owner-runner-qualification-a2bd39ce.json` (SHA-256
`ef84d142d52e0fe8c19364d360bc91209fdcc7bf3525709cd017fd419538a87c`).

To prevent further hand-assembled schema omissions, the current task adds
`tools/qa/collect_s2_runtime_config_inventory.py` (SHA-256
`95a28412a9a12ac365a8d8e36bd0e61b431ae5aa9f1cbfe134e2d1de68d0ef06`). Its focused regression suite is
`python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py`: 35 passed, one existing
pytest-asyncio deprecation warning, exit 0; Python 3.14.3 at HEAD
`2e6a796eaa04664812cf1266322b083f18770fa1`. These are code-level collection/schema tests only;
they do not prove target runtime acceptance. Use the committed collector and a new exact-head
authorization for the next live inventory; all prohibited scenario groups remain `NOT_RUN`.


## Evidence file: requirements.md (sha256 c17974c311e1c660b25520af85b8477ccd18784b8b81e7be3bbdbe81f7009394)
# S2 Requirements Reconciliation

Sprint: 39b7cc253f5d — active project sprint: S2

The Agentic_Framework phase-1 record is attached to the already active S2. It does not create a new product sprint or authorize starting S3. This document consolidates the existing S2 scope and acceptance state; it does not add product scope or reopen the accepted architecture.

## Context and goal

S2 delivers a bounded, authenticated path for dispatching work that has already been assigned by the existing Store, and establishes the evidence needed to qualify its runner boundary. The Store remains the sole task, assignment, and lease authority. The accepted coordinator path is the existing `DispatchOwnerService`, authenticated Supervisor/Store admission, Store-filtered Pub/Sub, and `StoreBackedDispatcher`. No external coordinator, second scheduler, or assignment authority is required. [S1: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”.]

## Current delegated execution scope — 2026-10-30

The operator's later explicit GO covers the exact configuration bundle, technical preparation and
permitted runtime qualification. The global settled-decision rule assigns the concrete technical
configuration, isolated service material and genuine evidence work to Codex; repeated generic
permission requests are superseded. Missing artifacts are execution work, not proof of a new
operator decision. Actual signatures/measurements still must be produced truthfully, with the
root policy signer outside Runner/worker and its delegated machine actor explicitly identified.
No personal human signature or successful measurement is inferred from authorization. Existing
restricted-selector and data-integrity safeguards continue to apply. The ordered current task
and evidence pointers are in backlog.md; earlier dated decisions retain their historical scope.

## Scope

**In scope:** source-level signed-instruction verification and owner relay for already-authorized work; fail-closed admission and outcome handling; bounded runtime configuration/evidence under the recorded authorization; truthful S2 acceptance and exact-head review.

**Out of scope:** unrestricted dispatch beyond the exact qualification task, impersonation of a personal human signature, fabrication of evidence, migration of an existing Store, restricted process-kill/crash/recovery/mutation-campaign/E8/policy selectors, and starting S3 before S2 acceptance. The current exact technical bundle and permitted qualification proceed under the later operator delegation above; preserve the existing cryptographic verification, role separation, source pins and enforced controls.

## Requirements

### Historical machine-delegation adjudication amendment (2026-10-29)

GPT-PM returned `MODIFY` for request `a3e130f0-9aec-4304-b001-388a45c0be55`,
correlated reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`. The exact harvested response is
preserved in `evidence/s2-machine-authority-adjudication-20261029.md`. Machine issuance and
machine E5 are permissible in principle. Codex owns preparing the explicit delegation policy,
assignment-provenance contract, independent measurement topology, versioned schemas and bounded
pure validators/read-only collectors; GPT-PM owns adjudicating the two reported MAJOR findings.
Private-key-bearing production signing services, production signing-key provisioning, replacement
of the current operator E5 contract and activation remain held. A concrete operator-authorized
policy is required before granting production powers; a prepared policy is not an authorization
or a human signature. The earlier unknowns below describe the current runtime contract, not a
requirement to locate a nonexistent external coordinator or to request another generic GO.

| ID | Requirement | Source and priority | Current evidence/state |
|---|---|---|---|
| REQ-001 | A dispatch instruction MUST be accepted only after independent root-Supervisor verification of its purpose-specific signature and bindings for request ID, task, slot, attempt, epoch, run ID, key ID, absolute UTC expiry, version, algorithm, and purpose. Invalid, expired, mismatched, or unsigned instructions MUST fail closed. | Accepted S2 contract in `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; S2 goal. | Verifier/client source is recorded as committed; `core/STATE.md` records source/test acceptance. This does not prove production issuer/key provisioning or runtime acceptance. |
| REQ-002 | The Store MUST remain the sole authority for task assignment, leases, and durable dispatch state; the signer/transport MUST NOT assign work or provide an alternate scheduler. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope. | Architecture is adjudicated and accepted. Production integration remains incomplete under REQ-005. |
| REQ-003 | The owner relay MUST deliver only already-authorized signed instructions through the accepted authenticated Supervisor/Store and Store-filtered dispatch path, with ambiguous outcomes handled fail-closed and without unsigned fallback. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope. | Existing bounded architecture and transport-only source/test scope are recorded as accepted. The qualified production owner-to-Runner journey remains open. |
| REQ-004 | Runner admission and recovery MUST preserve the accepted fail-closed boundary: unresolved or ambiguous dispatch outcomes MUST NOT permit an unauthorized or duplicate execution, and the existing admission fence MUST remain effective across the recorded recovery path. | `core/BACKLOG.md`, S2 section, including `S2-PROV-M03-R01` source/test closure and changes 0518/0522. | `S2-PROV-M03-R01` is recorded closed for source/test only. Installed systemd behavior and production runtime remain unverified. |
| REQ-005 | S2 production-runtime acceptance MUST be supported by an authenticated owner identity and root-controlled configuration, an authorized production instruction issuer/trust key, current run-bound E5/runtime evidence, and a qualified real owner-to-Runner journey. The probe inventory is captured root-owned and bound to run/spec/nonce; a Runner signature on the inventory is not required. The root-signed network-policy attestation remains independently verified. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 closure boundary; operator contract decision recorded in the current S2-4 change record. | `S2-DISPATCH-M01` is MAJOR/OPEN. Current production integration, current run-bound E5, and service/runtime qualification are not established. |
| REQ-006 | Evidence and approval MUST identify the exact reviewed source revision. Source/test results, synthetic fixtures, or prior-head records MUST NOT be represented as installed-production or current-runtime acceptance. S2 MUST remain NOT APPROVED and S3 unstarted until its required acceptance and exact-head gate are satisfied. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope and closure queue. | Current records explicitly distinguish source/test closure from runtime acceptance and state S2 is NOT APPROVED; S3 remains unstarted. |

## Non-functional requirements and constraints

- **Security:** fail closed on invalid provenance and ambiguous admission; keep signer authority distinct from Store assignment authority. [REQ-001–REQ-004; sources above.]
- **Runtime isolation:** use the accepted authenticated identities, root-controlled configuration, and bounded runtime profile; do not claim isolation from mocked peer credentials or transient test units. [REQ-004–REQ-005; `core/STATE.md`, current S2 coordinator/runtime adjudication.]
- **Numeric service targets:** UNKNOWN. The active S2 records do not establish a numeric dispatch-latency, availability, throughput, or recovery-time target. No target is invented here.
- **Restricted verification:** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN` under the recorded restrictions. A skipped or unrun selector is not a pass. [`core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 closure boundary.]
- **Data safety:** fresh schema-v6 Store initialization is conditionally allowed by the recorded adjudication; migration of an existing Store requires a separate gate. [`core/STATE.md`, current S2 coordinator/runtime adjudication.]

## Facts, assumptions, and unknowns

### Facts

- GPT-PM accepted the existing bounded coordinator architecture; no external coordinator path is required. [`core/STATE.md`, current S2 coordinator/runtime adjudication.]
- Transport-only source/test scope has recorded GPT-PM acceptance; the recorded functional and WSL runs are source/test evidence, not production-runtime proof. [Same state section; `core/BACKLOG.md`, S2 section.]
- S2 remains `NOT APPROVED`; `S2-DISPATCH-M01` remains `MAJOR/OPEN`; current run-bound E5, service/runtime qualification, and final exact-head approval remain open. [Same state section.]
- The operator is the sole human owner. Service identities are technical isolation identities, not project owners. [Same state section.]

### Assumptions

- This artifact belongs to the existing active S2 because the project state and backlog identify S2 as active. The framework sprint ID above is recorded as its phase-1 tracking ID, not evidence of a new sprint. [This mapping follows the parent-task instruction and the active S2 records; framework state is tracked separately.]
- Historical test counts and acceptance matrices at earlier revisions are not promoted to current-head evidence. The latest current-state summary governs this reconciliation.

### Unknowns that block S2 closure

| ID | Unknown / missing acceptance evidence | Owner | Next action |
|---|---|---|---|
| UNKNOWN-001 | Concrete isolated service material is prepared in root-controlled WSL staging, with only public fingerprints in the non-secret bundle. Exact installation and real runtime evidence remain execution work; no new generic permission is pending. | Codex owns exact configuration/material handling and observed verification under the existing delegation; GPT-PM adjudicates required final acceptance. | Deliver the verified exact bundle, install only its collision-checked paths/identities, preserve existing Store data and record actual outcomes. Never infer installation or a signature from a prepared policy. |
| UNKNOWN-002 | Current run-bound preflight and real owner-to-Runner execution are not yet measured. The root-policy signature stays outside Runner/worker; the measured inventory is root-captured without a Runner signature. | Codex owns actual isolated observation, root policy signing and configuration under the settled delegation; designated test roles execute permitted qualification; GPT-PM decides final acceptance. | Produce actual namespace/network/mount/socket and service evidence, sign only verified network-policy facts, and run the exact allowed task. Failure/unknown remains failure/unknown. Preserve restricted selectors as NOT_RUN. |
| UNKNOWN-003 | Exact-head GPT-PM final approval for the completed S2 code, mapped tests, and relevant specialist reviews is not recorded. | GPT-PM; Codex owns coordination and submission. | After coding and permitted test/review work are complete, submit the exact final revision and correlated evidence for the required gate; any later code change requires a fresh gate. |

## Traceability and acceptance boundary

`REQ-001`–`REQ-004` describe the accepted bounded source contract. Their recorded source/test evidence does not close production-runtime acceptance. `REQ-005` is currently unmet and is tracked by `S2-DISPATCH-M01` (MAJOR/OPEN). `REQ-006` prevents premature sprint closure or S3 work. Restricted selectors remain `NOT_RUN`; no waiver or pass is inferred from their absence. Once runtime evidence and all permitted source/test/review work are reconciled, GPT-PM must adjudicate the exact final revision before S2 can be reported closed.

## Glossary

- **E5:** the project’s sandbox/runtime inventory and provenance acceptance item; current S2 requires fresh run-bound evidence, and any operator-root-signed attestation must be genuine.
- **Exact-head gate:** GPT-PM approval correlated to the precise final Git revision and its evidence.
- **Store:** the existing durable authority for task assignment, leases, and dispatch state.
- **`NOT_RUN`:** a scenario was not executed; it is not a pass.


## Evidence file: backlog.md (sha256 0fc87c4432af216613075e4d9cf65892bb25d56402cb9770597bb980193d6470)
# S2 backlog and acceptance plan

Sprint identity: Agentic_Framework sprint `39b7cc253f5d`, mapped to the already active project sprint **S2**. This is a tracking association, not a new sprint. S3 remains unstarted.

## Current execution checkpoint — 2026-10-30

This backlog is the ordered task queue. Dated evidence and older narrative sections retain their
historical scope; they must not silently reopen accepted code. Before a new implementation or
review, identify the missing numbered acceptance criterion and check its existing approval and
implementation. An accepted item is reopened only with a concrete regression or changed accepted
requirement. Permission to prepare a candidate does not make that candidate mandatory for S2.

| Order | Task / state | Evidence / remainder | Owner / next action |
|---|---|---|---|
| 1 | S2-4 tracking reconciliation — corrected in change0591 | Correct stale writer/issuer HOLD and push-pending summaries against I01 SOURCE GO, code/test approval `c978360`, and successful task push through `e09c78b`. | Codex: verify the containing commit is normally pushed, then take item 2. |
| 2 | S2-4 exact runtime inputs — DELIVERED `473e559` | Source compatibility fix a600774 is pushed; actual strict stage-only publication succeeded. Bundle32 artifacts, nine unit bindings and three rate-limit overrides are pinned to actual source/helper/task/policy/run identities. False local GPT-PM credential labeling was corrected; review and test evidence is retained in change0595. | Codex: delivered change0595 in473e559; normal push output `9021b98..473e559` succeeded. Focused9-case suite and actual UID999 command/parser passed; local registry HMAC valid/tamper checks passed. Continue only item3. Existing delegation is carried forward; no generic permission is pending. |
| 3 | S2-4 current E5 and real owner-to-Runner evidence — IN PROGRESS after `473e559` push | Operator decision on 2026-10-30 removes any Runner-signature requirement for preflight inventory; root-owned exact run/spec/nonce capture and independently verified root-signed network-policy evidence remain required. The current source/config delta is in progress; runtime journey is NOT_RUN. Restricted scenarios remain NOT_RUN. | Codex implements and records the exact contract delta; functional-test-reviewer owns focused tests; security-reviewer reviews the trust-boundary change; e2e-runner executes the allowed runtime selector after code acceptance; GPT-PM adjudicates final S2 acceptance. Do not repeat generic permission requests. |
| 4 | S2-5 final acceptance — not started | Requires S2-4 acceptance plus final revision/evidence review. | Codex assembles; GPT-PM decides. S3 remains unstarted. |

## Historical source update — change0556 (current state above)

The fresh-only authenticated assignment bootstrap is implemented in change0552 (`45dcf47`);
the detached issuance/verifier contract is change0553 (`e44f48d`). GPT-PM request
`c7a8e23e-91f5-489c-a096-c813d84c3b12`, correlated reply
`7c3e4eb6-3300-5c5b-ba5c-85aaa10d0487`, returned **GO for bounded integrated SOURCE** and
accepted the corrected I01 design as implementation-ready. This supersedes the earlier source
HOLD for the issuer; it does not supersede runtime, key provisioning, real signing, E5, forbidden
selector or final S2 gates. The specialized journal, root-Supervisor v1 issuer and transaction-bound admission/grant/runner
guards are present in the code/test scope approved at `c97836029a5d94ff84dee5cb15d1757efd5525c3`. There is no missing external
coordinator or unassigned owner. Required I01-SRC-01 through I01-SRC-05 are recorded in
`evidence/s2-i01-integrated-source-adjudication-20261029.md` and design change0554.

The historical schema-v5 fixture item below is resolved by change0551 and its designated
six-case fixture evidence; it is not a current product blocker. Final S2 tests still wait until
all in-scope coding is complete. Historical story/epic rows retain their original evidence scope.

## Sprint goal

Deliver and qualify the existing Store-authorized signed dispatch path through the real Runner boundary, while preserving fail-closed behavior and keeping production dispatch disabled until the required runtime evidence and exact-head approval exist.

**Scope boundary:** use the accepted `DispatchOwnerService` → authenticated Supervisor/Store admission → Store-filtered Pub/Sub → `StoreBackedDispatcher` path. Store remains the sole task, assignment, lease, and durable dispatch authority. No new scheduler, coordinator product, assignment authority, or external coordinator is needed. For the current exact qualification, Codex executes the delegated technical configuration, key preparation and truthful root-machine measurements described in requirements.md, current execution scope. Do not migrate an existing Store, enable unrestricted production dispatch, fabricate an issuer identity or personal human signature, or run restricted process-kill, crash/recovery, mutation, E8, or policy selectors. Keep those restricted selectors `NOT_RUN`.

**Prioritization rule:** finish the highest-risk dependency chain in order: establish source/test correctness first; prepare and review the exact non-secret runtime bundle next; collect permitted runtime evidence and qualify real owner-to-Runner integration; then run the final exact-head gate. A later item cannot substitute for missing evidence in an earlier item.

## Prioritized S2 stories

The machine-delegation decision is now recorded, rather than pending: request
`a3e130f0-9aec-4304-b001-388a45c0be55`, reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`,
`MODIFY`; exact response in `evidence/s2-machine-authority-adjudication-20261029.md`.
Within S2-3, Codex prepares the concrete issuer-provenance and independent measurement contracts,
pure validators and read-only collectors. GPT-PM adjudicates corrections to both reported MAJORs.
This does not activate a replacement E5 contract or authorize production signing keys/services.
Operator authorization of the exact production delegation policy remains distinct from Codex's
preparation. No new external coordinator or human owner is required.

| Priority / story | Requirement trace | Owner | State at recorded evidence | Dependency / next action |
|---|---|---|---|---|
| S2-1 — Fail-closed signed instruction, Store admission, and recovery | REQ-001, REQ-002, REQ-004 | Codex | **Delivered — bounded source/test acceptance.** Evidence record and synchronized task documents were pushed in `e332ec4` (change records 0586/0587). GPT-PM request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` accepted baseline-plus-delta coverage and resolved S2-REVIEW-02 for this bounded scope at submitted HEAD `57c734e60787a9db14bb888116d7e808bc46970e`. Recorded tests: M03 130/130 at `c855ca4`; source-fidelity 5/5 at `206a746`; adapter 38/38 at `6952469`; exact wrapper regression 38/38 at `0da595e`. These are inherited reports, not tests run in the delivery turn; GPT-PM did not execute them or reproduce the Git continuity comparison. | No S2-1 source/test work remains. Runtime, production identity, current E5 and restricted scenarios remain unproven or NOT_RUN for their separate S2 acceptance. | None for bounded S2-1 delivery; full S2 remains open separately. | Codex owns task delivery; GPT-PM supplied the correlated source/test decision. | Start only the next queued task, S2-2; do not skip ahead to S2-4. |
| S2-2 — Authenticated owner transport to the existing Store-backed dispatcher | REQ-002, REQ-003 | Codex | **Delivered — bounded source/test acceptance.** GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55` is correlated to reply `d555b078-5647-46eb-bfc1-dd99654d634f` (job `68efb4e6-a296-4fd7-bcfc-2c6fe2568d5c`, `correlated=true`); it accepted the bounded source/test scope and resolved transport M01/M02. Exact source/test blobs are in pushed commit `e987a24`; delivery reconciliation is change record 0588. The 34-case WSL result is inherited evidence. | Production `S2-DISPATCH-M01`, genuine systemd/PID1 identity, kernel peer credentials, pidfd, socket filesystem metadata, provisioned identities/configuration, Store/Runner integration and E5 remain open/unproven. | None for bounded source/test delivery; runtime acceptance remains a separate S2-4 dependency. | Codex owns evidence and delivery; GPT-PM owns the recorded source/test decision. | After change record 0588 is pushed, proceed to the next incomplete task, S2-4; preserve runtime limits. |
| S2-3 — Immutable non-secret runtime bundle and bounded WSL qualification preparation | REQ-004, REQ-005, REQ-006 | Codex; GPT-PM adjudicates the reviewed bundle | **Accepted and delivered for bounded inactive stage-only preparation; commit `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` is pushed to `origin/s2-canonical-continuation`.** The exact source bundle and refreshed inventory were approved; the designated-runner direct regression passed 4/4 (8 deselected, 0 skipped) at `043980f`, and the blobs remained unchanged at reviewed source HEAD `ef465cd`. Stage-only execution then published the immutable versioned runtime/helper in Ubuntu-24.04, reporting `selected=false`, `selector_unchanged=true`, `systemd_units_installed=0`, `runtime_stage_only=true`. GPT-PM request `ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4`, correlated reply `1c8d392e-1a57-533c-b874-97823f5e4628`, approved the exact post-stage manifest SHA `78d21af798f66a3e54a8d638f393773af5d20120075cd02599ac70675cb84be7` with 0 BLOCKER/MAJOR in that scope. Evidence: `evidence/s2-3-stage-only-ef465cd.md`, `evidence/s2-3-post-stage-manifest-review-ac2d25a2.md`, and change record `0584-s2-3-stage-only-runtime-bundle.md`. | Task evidence and documentation are committed and pushed; advance only according to the sequential backlog. TP-10 remains PARTIAL for its broader refusal/error matrix; this task does not prove those unexecuted cases. Stage-only does not authorize selector/unit changes, activation, Store, service identity/configuration, keys/E5, dispatch, production, deployment, or S2 closure. |
| S2-4 — Production provenance and permitted real owner-to-Runner journey | REQ-001, REQ-003, REQ-004, REQ-005 | Codex: delegated technical configuration and evidence; GPT-PM: final adjudication; operator: expressly reserved actions only | **IN PROGRESS — runtime acceptance.** Existing I01 root V1 issuer code is implemented and covered by code/test APPROVE at `c97836029a5d94ff84dee5cb15d1757efd5525c3` (request `8fc2e0ba-07c9-49fc-b6b0-fac897e4408b`). The additional V2 verifier source/test slice was approved at `aa349632` and delivered with ledger `e09c78b`; normal push succeeded. | Remaining: exact authorized production configuration/key provenance, current run-bound E5 and permitted real owner-to-Runner qualification. `S2-DISPATCH-M01` describes this runtime/provenance remainder; an absent issuer implementation is not the blocker. Codex reconciles/prepares the permitted non-secret runtime inputs under existing authorization. A new V2 signing integration is not automatically an S2 prerequisite. |
| S2-5 — Final S2 review, exact-head approval, and sprint acceptance | REQ-006 | GPT-PM owns approval; Codex owns coordination and evidence submission | **Open.** No final GPT-PM approval for the complete S2 code, mapped test results, permitted runtime evidence, and relevant specialist reviews is recorded. | After S2-1 through S2-4 evidence is reconciled, obtain fresh relevant specialist reviews and submit the precise final Git head with correlated evidence to GPT-PM. Any subsequent code change invalidates that approval. Then record accepted/rejected/carried stories in `docs/sdlc/acceptance.md`. Do not begin S3 before S2 closes. |

## Numbered acceptance criteria

These criteria make the existing requirements testable; they do not add product scope. Source/test evidence and installed-runtime acceptance are separate.

### S2-1 — Signed instruction and recovery source contract

1. **Given** an instruction with any invalid, unsigned, expired, purpose-mismatched, or request/task/slot/attempt/epoch/run/key binding, **When** the root Supervisor verifies it, **Then** it rejects before durable dispatch intent and leaves Store assignment/lease authority unchanged. (REQ-001, REQ-002)
2. **Given** an ambiguous admission or a previously accepted outcome replayed after generation change, **When** the existing recovery path handles it, **Then** it follows the accepted read-only historical-result rule or fails closed; it does not append a duplicate event, mutate a lease, grant new admission, or launch a duplicate Runner. (REQ-004)
3. **Given** the recorded source/test evidence at the accepted revisions, **When** this story is assessed, **Then** it is labeled source/test accepted only and is not represented as proof of systemd, kernel identity, or production runtime behavior. (REQ-006)

**Recorded result:** source/test acceptance is retained; delivery is not closed until the task commit is pushed. `S2-PROV-M03-R01` evidence is linked from `core/BACKLOG.md` and `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`. The fixture correction is in `dcb5d63`. The four-file WSL selection passed 130/130 at `56cd816` and exact HEAD `2befed5`; adapter functional/E2E passed 35/35 and 2/2 at that HEAD. The source-fidelity verifier passed 5/5 focused tests and maps all 41 redactions. Independent review found no confirmed source defect; source identity and static invariants are documented in `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`. GPT-PM re-adjudication remains pending; no approval or push is claimed. |

### S2-2 — Owner transport source/test contract

1. **Given** a valid signed instruction for work already authorized by Store, **When** the accepted owner transport path forwards it, **Then** the existing authenticated Supervisor/Store path performs admission and the existing Store-backed dispatcher relays it; transport does not create or assign work. (REQ-002, REQ-003)
2. **Given** malformed, partial, duplicated, or ambiguous transport input/outcome, **When** the owner service handles it, **Then** it fails closed without unsigned fallback or a second request on the same one-frame connection. (REQ-003)
3. **Given** the recorded WSL transport run, **When** reporting its result, **Then** report 34 passed, 0 skipped, 0 failed for that source/test run and explicitly retain mocked peer credentials, pidfd, and filesystem metadata as unproven runtime properties. (REQ-006)

**Recorded result:** accepted at source/test scope under GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55`; exact run record: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`. This result is not production-runtime acceptance.

### S2-3 — Reviewed runtime bundle and bounded preparation

1. **Given** the accepted source/test scope and current repository revision, **When** Codex prepares runtime inputs, **Then** the review bundle identifies the exact source/artifact revision and contains configuration values and hashes without exposing secret contents. (REQ-005, REQ-006)
2. **Given** the GPT-PM conditional WSL authorization, **When** preparation reaches provisioning, **Then** it proceeds only after GPT-PM has reviewed the exact immutable bundle and the stated source/test gate is satisfied. (REQ-005)
3. **Given** an empty Store or an existing Store, **When** initialization is planned, **Then** only the conditionally allowed fresh schema-v6 initialization may proceed under its reviewed gate; an existing Store migration remains stopped for its separate gate. (REQ-006)
4. **Given** delegated production instruction issuer/trust-key and root policy authority, **When** runtime preparation records these inputs, **Then** Codex creates the authorized machine artifacts from verified source and measured evidence without claiming a personal human signature. The root policy signature is separate from the unsigned root-captured probe inventory. (REQ-005)

**Current result:** accepted and delivered for the bounded inactive stage-only preparation and exact post-stage manifest identity. The evidence set and backlog were committed as `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` and pushed to `origin/s2-canonical-continuation`. TP-10's broad refusal matrix remains partial. This approval does not authorize runtime selection/activation, service or Store mutation, keys/E5, dispatch, production, or S2 closure.

### S2-4 — Permitted runtime and production integration

1. **Given** a reviewed bundle and genuinely provisioned authorized identities/configuration, **When** the permitted runtime qualification is executed, **Then** evidence identifies the exact revision, effective service identity, root-controlled configuration boundary, current run-bound provenance, and real owner-to-Runner result. (REQ-004, REQ-005, REQ-006)
2. **Given** missing or unauthenticated production issuer/trust-key provenance, owner identity, root configuration, or current E5/runtime evidence, **When** S2 acceptance is evaluated, **Then** `S2-DISPATCH-M01` remains MAJOR/OPEN and production dispatch remains disabled. (REQ-005)
3. **Given** any selector explicitly restricted by the current adjudication, **When** runtime coverage is reported, **Then** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`; no skip or synthetic test is counted as a pass. (REQ-006)
4. **Given** runtime observations for the configured run/spec/nonce, **When** E5 provenance is recorded, **Then** Codex captures the exact probe JSON under root ownership, signs the network-policy attestation only after independently verifying its measured facts, and makes no personal human-signature claim. A probe signature is not required. (REQ-005, REQ-006)

**Current result:** IN PROGRESS for runtime acceptance. The existing I01 root V1 issuer implementation is present and covered by the bounded code/test approval at `c97836029a5d94ff84dee5cb15d1757efd5525c3`, request `8fc2e0ba-07c9-49fc-b6b0-fac897e4408b`, reply `c0ff978a-76a3-5c9e-a0d4-e98fef016357`. The separate V2 verifier slice was approved at `aa349632` and pushed through `e09c78b`. Ordered source/test child tasks S2-4.2 (invocation-bound root capture/freshness) and S2-4.3 (safe StageOnly beside an existing root-owned config directory) are implemented and focused-test reviewed; evidence is in `docs/changes/0598-s2-4-root-capture.md` and `docs/changes/0599-s2-stage-only-with-existing-config.md`. Production configuration/key provenance, live journal capture, current E5 and a qualified real owner-to-Runner journey remain unverified under REQ-005. Do not reopen accepted issuer source or make a V2 signing replacement mandatory without a concrete defect or changed accepted requirement. Codex owns the delegated technical configuration and actual measurements; GPT-PM owns final adjudication. The current execution scope in requirements.md supersedes generic historical permission-pending wording; no personal human signature is asserted.

**Delivered ordered subtask S2-4.1 — remove the Runner probe-signature cycle:** source/test and synchronized contract records are pushed in `8acd56ccb37e888a64b4f5898864bb07599683d0`; push output was `473e559..8acd56c` to `origin/s2-canonical-continuation`. The designated functional-test reviewer reports 65 passed, 8 skipped for the unsigned exact-schema/run-binding contract, synthetic Supervisor/Store path, removed `probe_key_path`, and runtime-config bundle. The security reviewer found no source regression from removing that signature, conditional on a trusted root capture. That condition is source-implemented and focused-test reviewed by ordered child S2-4.2 below, but not runtime-proven. Evidence and scope are in change record `0597-s2-4-remove-runner-probe-signature.md`.

**Delivered ordered subtask S2-4.2 — root capture source and freshness:** Codex added `tools/vst/preflight_capture.py` to accept exactly one systemd invocation, validate its worker journal record and root systemd success record against root-controlled run/spec/nonce inputs and attestation, and atomically publish a root-owned mode-0600 record without overwrite. Probe validation now rejects timestamps older than 120 seconds or from the future. Focused evidence: the designated functional-test reviewer reports 87 passed, 9 skipped for `python -m pytest -q tests/vst/test_s2_preflight_capture.py tests/vst/test_s2_sandbox_probe.py`; a further 7 passed for `python -m pytest -q tests/vst/test_s2_e8_synthetic_lifecycle.py tests/vst/test_s2_store_lifecycle.py::test_supervisor_consumes_a_synthetic_probe_once_for_one_run`. The Windows run skipped POSIX publication; the designated e2e-runner separately ran the exact committed S2-4.2 publication test on the WSL target at HEAD `29f2671` with Python 3.12.3 and pytest 7.4.4: 1 passed; eight other existing skip cases are not passes. Python and security reviewers found no concrete source issue. A real captured systemd probe invocation, bundle repinning/install, current E5 and owner-to-Runner runtime acceptance remain open; S2-4 stays IN PROGRESS and S2-5/S3 remain queued. Detailed record: `docs/changes/0598-s2-4-root-capture.md`.

**Delivered ordered subtask S2-4.3 — StageOnly with existing root config:** target inventory showed `/etc/vst-runner` already exists as root-owned mode `0755`, while the relevant units are inactive and runtime socket directories absent. The installer now allows that directory only when it is a real root-owned directory without group/world write bits; existing config is left untouched. The focused functional-test reviewer reports 8 passed, 1 warning in `tests/vst/test_s2_runtime_stage_policy.py`; the security reviewer found no concrete source defect. Detailed record: `docs/changes/0599-s2-stage-only-with-existing-config.md`.

**S2-4.4 — exact StageOnly inputs:** source plan and Ubuntu-24.04 target inventory for source `7c7d599af03860ede7d4960301ed8d0456c360c0` are captured in `docs/changes/0600-s2-runtime-source-inputs.md`, including exact SHA-256 identities. GPT-PM confirmed the plan/source hash and StageOnly boundary but held the first execution because its inventory aged past five minutes. Codex refreshed the read-only inventory at `2026-10-30T02:01:02.747390+00:00`, SHA-256 `37a9577b0e710c911dd3f6f84da43be9d756b22106460581bf5a53e121436848`; this exact digest must be reviewed before StageOnly. StageOnly has not run. Existing configuration, selector and services must remain unchanged.

**S2-4.4 result:** GPT-PM follow-up request `7ede96a5-6419-4510-afd8-64e480c2e54d` approved the refreshed inventory and resolved `M-S2-4-STAGE-01`. The exact StageOnly command then exited 1 because Python imports added unplanned `__pycache__` members. Read-only post-failure verification showed no target change: selector remains on `a600774`; requested runtime/helper are absent; nine S2 units are inactive; jobs, Store and runtime record are absent. Detailed evidence: `docs/changes/0600-s2-runtime-source-inputs.md`.

**S2-4.5 — preserve exact StageOnly source members:** Codex added `-B` to both StageOnly module-import paths; the functional-test reviewer added and ran the focused two-case regression (2 passed, one existing deprecation warning) in `tests/vst/test_s2_stage_only_install.py`. Commit `f685cc9778e516b277e243a14dfa123db34ec247` was normally pushed to `origin/s2-canonical-continuation`. Detailed record: `docs/changes/0601-s2-stage-only-import-fix.md`.

**Delivered S2-4.6 — bounded StageOnly publication:** GPT-PM request `7d4bd70e-ebbc-4b98-ac3b-fe6b84825fca` approved source plan SHA-256 `90b88d12f571b0e9bc3744e4f9aff723ee2c0740f5895108726b8e52da2b1a5d` and fresh target inventory SHA-256 `8ede4656da3c18eda730873524534892c58ac0c9056885a3cbd59045a66ff733`. The normal installer ran at about `2026-10-30T02:13Z`, exit 0: it published the immutable `f685cc9` runtime and helper with `selected=false`, `systemd_units_installed=0`. Read-only post-stage verification at `2026-10-30T02:17:23.380934+00:00` matched the complete runtime tree and marker to the pinned plan; helper SHA-256 `3e7fe2ed0006b9e86ceb08f41071ac6a69b547bb2fe603255a3763643ce2cf91`, owner/mode `root:vst-runner 0:988 4750`. Selector still points to `a600774`; nine units are inactive; no jobs/cgroups, Store, run record, or runtime sockets; config directory and unit/drop-in metadata are unchanged. Detailed record: `docs/changes/0602-s2-stage-only-refreshed-inputs.md`. This closes only inactive source publication. Next ordered task remains S2-4 permitted current-run qualification and owner-to-Runner evidence; S2-4 and S2-5 remain open.

**Delivered S2-4.7 — permit runtime selection beside existing safe configuration.** The selector validates only the
existing root-owned `/etc/vst-runner` directory metadata and leaves its files and Store untouched. It continues to
require absent `/run` service paths, inactive units, no pending jobs, and empty cgroups. Focused results: Windows
12 passed/2 POSIX-only skipped; WSL Python 3.12 ran the two POSIX selector cases 2/2; the code reviewer found no
actionable BLOCKER/MAJOR. Commit `80c2b81deac364ed6466600fd46af47aafe805e2` was normally pushed to
`origin/s2-canonical-continuation`. Evidence: `docs/changes/0603-s2-existing-config-runtime-selection.md`. The
selector has not been applied. A separate runtime configuration candidate still pins `a600774` and remains
uncommitted; it is not an activation input.

**S2-4.8 — exact source and target inputs for the selector fix.** Source plan for committed source
`80c2b81deac364ed6466600fd46af47aafe805e2` is `docs/sdlc/evidence/s2-runtime-source-plan-80c2b81deac364ed6466600fd46af47aafe805e2.json`
(SHA-256 `01818efcd23bc20a3a4b408921d7342f5e5f95adc16ad86fe7b2a3b7176e2344`). A fresh read-only Ubuntu-24.04
inventory refreshed at `2026-10-30T02:49:02Z` is
`docs/sdlc/evidence/s2-runtime-target-inventory-80c2b81deac364ed6466600fd46af47aafe805e2.json` (SHA-256
`5f011ff65577a9363d2c1b60747e586d12042995dc88e8dff8779bdb81b28a66`), refreshed at
`2026-10-30T02:49:02Z` after the prior inventory expired at installer validation (318.9 seconds old; limit 300).
It confirms the selector still points to `a600774`, all nine S2 units are inactive, no jobs are pending, Store
and current preflight are absent, and the root-owned compiler identity is present. The failed attempt made no
target change. No private bytes were read or hashed. Detailed record:
`docs/changes/0604-s2-runtime-inputs-80c2b81.md`.

**Delivered S2-4.9 — bounded StageOnly publication for `80c2b81`.** After pushing the refreshed inventory,
the normal installer exited 0 at `2026-10-30T02:50Z`. It verified the exact source map, published
`/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2`, and reported helper SHA-256
`0ee613b289ab4fcf79d82f1cae777b96fcd97c8a02c59dded50736797a4381f5`, owner/mode `root:vst-runner 0:988 4750`,
`selected=false`, `systemd_units_installed=0`. Record: `docs/changes/0605-s2-stage-only-80c2b81.md`.
This is immutable publication only; the selector is still on `a600774` and no services were activated. Next:
the non-secret candidate rebinding was delivered as S2-4.10 below. Current E5 and the one permitted
owner-to-Runner journey remain open.
Restricted process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`.

**Delivered S2-4.10 — rebind and test the non-secret runtime configuration candidate.** The candidate
now binds task/runtime/helper source to `80c2b81deac364ed6466600fd46af47aafe805e2`, uses a fresh
run/nonce/request identity, pins the verified incremental Git bundle, and contains a read-only
transition manifest generated by the staged runtime's `bootstrap_runtime prepare`. The focused
functional-test reviewer reports `python -m pytest -q tests/vst/test_s2_runtime_config_bundle.py`:
9 passed on HEAD `c59f1c5` / Python 3.14.3; one existing pytest-asyncio deprecation warning. No
runtime selection, configuration installation, or service start occurred. Exact record:
`docs/changes/0606-s2-runtime-config-80c2b81.md`.

**Delivered ordered preparation S2-4.11a — build and test the pinned non-secret config applier.**
`tools/qa/apply_s2_runtime_configuration.py` reads all bundle sources from an exact committed Git
revision, pins the bundle/layout digests, and lets WSL independently verify the exact 26
destination map, metadata, content hashes, fresh target inventory and selected runtime. It refuses
unknown target bytes, excludes private key material, applies only while the nine relevant units
are inactive, atomically replaces approved regular files, reloads systemd and confirms
loaded-inactive unit state. The focused functional-test reviewer reports 9 passed with one existing
pytest-asyncio deprecation warning; these are local payload-contract tests, not WSL installation or
runtime proof. Security review found no remaining concrete issue. Evidence and scope:
`docs/changes/0607-s2-runtime-config-applier.md`.

**Delivered ordered preparation S2-4.11b — select the exact staged runtime without activation.**
The existing root-only `bootstrap_runtime apply` transition accepted the exact candidate manifest
digest `dc516f6b7053ec48bf96aaa3ddb3042d87d57f8f7199284e27e98f8203cc7935` and returned
`bootstrap_selection=complete`, `services_started_or_reloaded=false`,
`store_opened_or_changed=false`. A post-selection e2e-runner inventory then confirmed selector
`80c2b81`, all nine relevant units `loaded/inactive`, no jobs, and an absent Store target. It found
19/26 config destinations matching and seven known differences. The config applier was corrected
to consume the actual `runtime_selector.link_target` inventory field; its focused regression suite
reports 10 passed with one existing pytest-asyncio warning. Exact evidence is in
`docs/changes/0608-s2-runtime-selection-and-inventory-contract.md`.

**Delivered ordered subtask S2-4.11c — apply and verify the exact 26-file configuration.** The
committed pinned applier ran against post-selection inventory SHA-256
`d68d5679936927172b2b143fb3c80c28278f7034940bbbf93ffdd72aeda8fba3` at source commit
`aa32afd6298233666897b8753efafa84909715ef`. It updated seven exact known config files; the other
19 destinations were already exact. All 26 post-install hashes match, systemd `daemon-reload`
succeeded, all nine units remained loaded/inactive, there were no jobs, and Store stayed absent.
Private bytes were excluded. Evidence and exact command are in
`docs/changes/0609-s2-runtime-config-install.md` and
`docs/sdlc/evidence/s2-runtime-config-post-install-20261030T033734Z.json`.

**Delivered ordered subtask S2-4.12a — root-measured probe capture implementation.** The helper
and focused synthetic coverage are complete: 53 passed; security and reliability reviewers found
no remaining MAJOR. GPT-PM request `69174c68-5974-4b48-bcfe-f356a763746d` approved bounded code
HEAD `19338baebc865bbc9fabec45115340a629c61807` (reply
`e273369c-e309-5a80-a3b7-eabe92d6e9bc`); normal push to `origin/s2-canonical-continuation`
succeeded. Local diff verification confirmed the reviewed four-file scope. This does not claim
live WSL/Runner evidence.

**Current ordered subtask S2-4.12b — bounded worker identity settling and one current-run qualification.**
The prior one-use authorization for run `s2-runtime-20261030-334296bd0779488d837a27e283b50b6a`,
request `212a23e66ee94a7d87355b11e07e34fe`, nonce `b57520d076e1acd355d310ed18364907` was consumed.
Its exact runtime error was UID/GID arrays `[0,0,0,0]` instead of configured `[999,999,999,999]`
and `[989,989,989,989]`; no root preflight record, Store, bootstrap, Supervisor, Runner, network
attestation, or TestRun was produced. The correlated evidence is
`docs/sdlc/evidence/s2-runtime-owner-runner-qualification-20261030-334296bd.json` (SHA-256
`94229746889b17186e0a421babeef87afd69e7c99136d57204c0590508292732`). A later journal/unit
observation showed the configured worker identity 999:989. A systemd credential-transition race is
plausible, not proven; do not report it as the established cause. The consumed identity is now
permanently retired and cannot be retried.

The current source candidate waits at most five seconds for only the exact same-process root-to-worker
credential transition while pinning PID start time, cgroup, invocation, systemd generation and boot
identity; all other mismatches and timeout remain fail-closed. Review found that nested subprocesses
could exceed the advertised wall-clock bound; the current code now passes one remaining monotonic
deadline to every nested systemd command and checks expiry even when the first sample is already the
worker identity. The functional-test-reviewer reran the focused suite on the final code: 93 passed,
one existing pytest-asyncio deprecation warning. Coverage includes declining command timeouts,
deadline exhaustion, worker-first late validation, and refusal of the consumed tuple before marker
creation. Security and final code reviews passed. GPT-PM exact-head review request
`7e63f76e-4454-4b9d-80ad-c8ce77f607f6` returned HOLD because its declared helper digest was stale:
request `d324c810…` versus actual committed/worktree helper bytes `0f3b7b6f…` (55,295 bytes).
Direct Git-blob/worktree comparison matches the latter; the mismatch is in the request metadata,
not evidence of a source defect. GPT-PM's exact-source follow-up request
`d5ba635a-dac4-45ab-9fed-6fae692d104a` approved implementation HEAD
`1b5dd9d7a639b629465ac6fcf29e300ba80c18ca`; that task was normally pushed to
`origin/s2-canonical-continuation` (output `002e361..1b5dd9d`). This approval covers the worker
identity-settling implementation only, not the new inventory validator. Detailed change record:
`docs/changes/0615-s2-4.12b-worker-identity-settle.md`.

**Current subtask update — fail-closed inventory validation.** The designated functional-test-reviewer
reports 29 passed, one existing pytest-asyncio deprecation warning for
`tests/vst/test_s2_runtime_config_inventory.py`; code and security reviewers found no remaining
concrete issue in the validator/applier path. It requires the exact 26-file consumed-run baseline,
complete fresh WSL/PID1/account/unit/source evidence, a read-only D: 9p mount, canonical octal mode
strings, matching top-level/readiness boot IDs, and the exact runtime symlink shape before apply.
The privileged applier checks and executes the verifier source from the exact committed Git blob and
validates the same inventory bytes before payload construction. GPT-PM request
`c21b6374-653d-46c5-9732-fcc810a81be5` held earlier HEAD `4f9887fc03d773c7159c87b105093a3a751cc3b0`
for the boot-ID and mode integration gaps; both have been corrected and need a new exact-head GPT-PM review. The
authorized replacement inventory request `9357ee74-c0ac-4ed4-9568-1b4a192bf874`
and correlated reply `6d0a5e51-1809-5420-8c45-9ebc6beb9ec4` are recorded in
`docs/sdlc/evidence/s2-runtime-owner-runner-qualification-9357ee74.json`. That read-only result
exited 0 but was incomplete: PID1 namespaces/start identity, `vst-runner` identity, systemd version,
baseline fingerprint comparison, and verbatim inventory persistence were missing. No apply,
preflight, claim/probe, or TestRun occurred. Both inventory authorizations are consumed. The new
corrected source still needs exact-head GPT-PM approval and push. Detailed record:
`docs/changes/0616-s2-runtime-inventory-validator.md`.

The candidate tuple remains unapplied and unclaimed. Before another target command, Codex must
finish exact-head GPT-PM source review, commit and normally push this validator task, then obtain a
new correlated runtime authorization for the pushed head and exact source pins. `e2e-runner` then
owns the one authorized complete inventory/apply/preflight/test sequence. S2-4 remains IN PROGRESS;
S2-5 is queued and S3 unstarted.

**Latest runtime result and source-pin correction.** GPT-PM request
`733857ce-024e-42ab-b65a-25e12162dc38`, reply `6402ed93-9fb2-5569-8710-50b32034b531`, authorized one
inventory and conditional downstream sequence on HEAD `f9f488f`. The one raw inventory is
`docs/sdlc/evidence/s2-runtime-target-inventory-f9f488f.json`, SHA-256
`d4dc31bcd0eb97478677a844b80c2f7ccfbb9d176a8197b52c4a7ea7cdb340a9`. The committed verifier ran
once and refused because its applier SHA pin was stale (`ac512…` vs authorized `7d208…`). No apply,
root preflight, durable claim/probe, or TestRun occurred. The collector also used
`/proc/1/ns/mount` rather than `/proc/1/ns/mnt`, leaving mount namespace and PID1 UID/GID evidence
incomplete; this is a collector-command defect. The expected old installed bootstrap identity was
observed, and candidate collision was false. Codex now derives both verifier and applier digests
from exact HEAD Git blobs and requires byte-identical worktree files; the focused suite reports 31
passed. Local code and security reviews found no concrete defect. This correction still needs a
task commit, exact-head GPT-PM source review, normal push, and a new bounded runtime authorization.
Next collector must use `/proc/1/ns/mnt` and `/proc/1/status`, persist full JSON, and run the verifier
once; do not repeat any used inventory/verifier invocation. Detailed record:
`docs/changes/0617-s2-runtime-inventory-source-pins.md`.

The candidate tuple remains unapplied and unclaimed: run
`s2-runtime-20261030-2b5e04a37cbc430f0adb239658a29910`, request
`e520e04f58ad5e6a431a3a20b0efb87c`, nonce `0aac24fec9a2a5c53c5e9da21cbb4a42`, bundle SHA-256
`388e6bb00f97b54bbd456994ccdd399317ab2e527c6f37d8a1b71ce20a280e45`. Runtime request
`c84a91af-1ce6-4a55-9ce7-eed30c64ba66` authorized one inventory, and replacement request
`9357ee74-c0ac-4ed4-9568-1b4a192bf874` authorized one corrected read-only inventory. Both inventory
invocations are used; the first failed before collection, and the second was incomplete. Neither
authorized path reached apply, root capture, claim/probe, or TestRun. Their exact-head scope is the
old HEAD `1b5dd9d7a639b629465ac6fcf29e300ba80c18ca`; the validator changes the code HEAD, so a new
correlated runtime authorization is required after this task is pushed. The prior installation
remains bound to the consumed run. S2-4 remains IN PROGRESS, S2-5 is queued, and S3 is unstarted.

**Latest S2-4.12b runtime attempts.** Request `53f946da-755c-4859-adca-6bfd64fb2293` / reply
`09ac688e-5ded-5b7b-aa9c-5e6a69e13ff7` authorized one inventory and validator at HEAD `2e6a796`;
the collector omitted `readiness.units`, so validation refused. No runtime mutation occurred. Its
inventory SHA was `7a7e97b1e9a7dedbfd57592c3df66fea7ff6847c0a6ff3e77d6e49abd5b168d0`; both records
are preserved under the `2e6a796` evidence suffix. Replacement request
`a2bd39ce-8ae4-4416-9b82-56382a610c92`, reply
`80091d4f-cbf2-5c72-af15-7ef9a48020bf`, authorized one inventory plus one validator and conditional
apply/preflight/TestRun at exact HEAD `2e6a796eaa04664812cf1266322b083f18770fa1`. Inventory SHA
`acb6b116aa66f4ba764a9e7c9ad505b90574323ed16129a71a61a970956e151c` recorded values matching
the requested target predicates but omitted the duplicate `readiness.runtime_selector`; the one verifier refused with
`selected runtime path differs from the pinned S2 runtime`. No apply, preflight, claim/probe, or
TestRun occurred; this was a collector serialization defect, not a confirmed target failure. Codex
added a collector candidate at `tools/qa/collect_s2_runtime_config_inventory.py`; its current
integration-corrected SHA-256 is `453fe70732c7309158cab7a0876b6bb7347b895056969ef87dbf988dd8cfa838`.
GPT-PM request `cf7a9515-0cd8-47d2-a0cb-1c351a3ef1e0` returned HOLD / MAJOR-01: six validator-
required fields were only top-level and absent from `readiness`, so the next verifier would fail.
The current uncommitted assembler correction duplicates the same captured values into both places.
The functional-test-reviewer added an integration regression through the production assembler and
real validator. `python -m pytest -q tests/vst/test_s2_runtime_inventory_collector.py` returned 52
passed, one existing pytest-asyncio deprecation warning, exit 0, Python 3.14.3, at HEAD
`1a7dca5527dbe48324426f9b5f56621e85a6279b`. The tests prove the valid assembly passes and missing
or contradictory values are refused for all eight duplicated readiness fields. Code review
re-reviewed the integration contract and found no actionable B/M issue. Security re-review found no
actionable B/M finding. The tester reran the command on committed HEAD
`b927a438a72d14a31229c9d0ad7514a19606c98e`: 52 passed, one existing deprecation warning, exit 0;
a subsequent task-record-only amendment changed no source or test bytes. Do not call this ready for
PM review yet. Current S2-4.12b next step: obtain
remediation review bound to exact HEAD and exact collector bytes, normally push, then request a fresh
one-shot runtime authorization bound to that pushed HEAD and pins. Execute no further runtime
command under the consumed requests.
S2-4 remains IN PROGRESS; S2-5 remains queued; S3 is unstarted.

The active AF push gate's `start_head` had pointed to `20fda2c` on the other
`s4-canonical-continuation` branch, not an ancestor of the S2 branch. Codex corrected this single
pointer to the previous delivered S2 HEAD `2e6a796`, preserving sprint ID and phase history. This
keeps the required exact-head review scoped to the current S2 continuation.

### S2-5 — Exact-head gate and sprint decision

1. **Given** completed source, mapped test, permitted runtime, and relevant specialist-review evidence, **When** final approval is requested, **Then** GPT-PM's approval names/correlates to the exact final Git head and evidence set. (REQ-006)
2. **Given** any code change after that approval, **When** sprint closure is reconsidered, **Then** the approval is stale and a fresh exact-head gate is required. (REQ-006)
3. **Given** missing runtime acceptance, a remaining valid code BLOCKER/MAJOR, or missing exact-head approval, **When** S2 status is recorded, **Then** S2 stays NOT APPROVED and S3 stays unstarted. (REQ-005, REQ-006)

**Current result:** open. Next: after all prior criteria are evidenced, Codex submits the exact head and correlated evidence to GPT-PM and writes sprint acceptance from the verdict.

## Definition of Ready

- The story traces to one or more `REQ` identifiers in `docs/sdlc/requirements.md`.
- Acceptance criteria are numbered, falsifiable, and identify whether source/test or runtime evidence is required.
- The accepted architecture and relevant GPT-PM authorization are linked; dependencies and restrictions are explicit.
- The exact evidence source and responsible project owner (Codex, GPT-PM, or operator) are named.

S2-1's bounded source/test task is delivered in pushed commit `e332ec4` after GPT-PM accepted S2-REVIEW-02 under request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db`. S2-2's bounded source/test task is delivered in pushed commit `e987a24` and reconciled by change record 0588; its runtime limitations remain open. S2-3's bounded inactive stage-only preparation and post-stage manifest identity are accepted and delivered. S2-4 is the next incomplete task; it cannot be accepted until its genuine provenance and runtime prerequisites exist. S2-5 is a closing gate, not a substitute for unfinished stories.

## Definition of Done

- All in-scope source changes are committed with a dedicated linked change record in the same commit; the accepted source/test revisions and evidence are identified.
- Required mapped tests are authored/executed by the designated test roles after coding is complete; exact commands, revision, environment, results, and limitations are recorded. Unavailable or restricted scenarios are `NOT_RUN`, never `PASS`.
- Relevant specialist reviews are completed on the exact final diff; valid BLOCKER/MAJOR findings are resolved and rechecked.
- Runtime acceptance, if required by the story, is backed by current run-bound evidence from the authorized environment; mocks and source tests are not promoted to production proof.
- GPT-PM gives fresh approval for the exact final head and correlated evidence before push/PR. A later code change requires a new approval.
- `docs/sdlc/acceptance.md` records each S2 story as accepted, rejected, or carried with evidence and reason. One PR is used for S2. S3 begins only after S2 acceptance and required gates are complete.

## Current sprint disposition

| Story | Decision | Evidence / limitation |
|---|---|---|
| S2-1 | Delivered — bounded source/test acceptance | M03 130/130 at `c855ca4`; source-fidelity 5/5 at `206a746`; adapter 38/38 at `6952469`; correlated-wrapper regression 38/38 at `0da595e`. GPT-PM request `f92b750e-485d-4f97-8c28-3bb2b8bfc3db` resolved S2-REVIEW-02 for this scope at submitted HEAD `57c734e60787a9db14bb888116d7e808bc46970e`; evidence: `evidence/s2-1-coverage-adjudication-f92b750e.md`. Delivery: `e332ec4` pushed. Tests/reviews are inherited records, not work rerun by GPT-PM. Runtime remains unproven. |
| S2-2 | Delivered — bounded source/test only | GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55`, correlated reply `d555b078-5647-46eb-bfc1-dd99654d634f`; exact source/test blobs are in pushed `e987a24`. WSL run record `evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` reports 34 passed; peer credentials, pidfd and filesystem metadata are mocked. See delivery reconciliation 0588. |
| S2-3 | Bounded stage-only acceptance and delivery complete | Commit `ae07f8708adcc7ef4f69505477ad6b72e3c912cf` is pushed. Exact bundle/inventory and post-stage manifest identities, PM decision `ac2d25a2-8b62-4d79-8614-fc6a9f7d0bb4`, and stage result are linked above. Selector/units were not changed; TP-10 remains partial. |
| S2-4 | IN PROGRESS — runtime evidence remains | Existing issuer SOURCE is implemented and bounded code/test approved at `c978360`; V2 verification slice approved at `aa349632` and pushed. `S2-DISPATCH-M01` remains for production configuration/key provenance, current E5 and real owner-to-Runner qualification. Codex owns permitted preparation/evidence; GPT-PM adjudicates; operator owns reserved authority/custody and genuine attestation. Restricted selectors stay `NOT_RUN`. |
| S2-5 | Carried — final gate pending | No final exact-head GPT-PM approval for full S2 is recorded. Codex coordinates the submission after S2-3/S2-4 and reviews complete. |

### Focused test maintenance note

Historical item, resolved in change0551: Codex reconciled the exploratory selector `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` in `tests/vst/test_s2_persistent_runner_service.py`. It assumes a Store with `PRAGMA user_version == 5`, while both baseline `9c1be0f` and current source declare schema version 6. The selector is outside TP-26/27 acceptance and was excluded from the final focused assignment-basis run; do not silently change its historical fixture or count its failure against the accepted S2 candidate tests. Resolution: the designated functional-test reviewer restored a true schema-v5 fixture and reported six passing cases over two selectors; see `evidence/s2-legacy-v5-fixture-run-20261029.md`. Include its permitted regression only after the final S2 code freeze.

## Required evidence references

- Requirements and current limitation register: `docs/sdlc/requirements.md`.
- Current S2 coordinator/runtime adjudication and correlated decisions: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.
- S2 source/test backlog and M03 source/test closure: `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- Transport test details and limits: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.



## Evidence file: design.md (sha256 d43a99939d2282bcb5617e142991f05eb9c1b52653241125b6d0b9bcc369088d)
# S2 exact runtime bundle and revision transition

Sprint: `39b7cc253f5d` (active S2)
Design scope: source/config preparation and a reversible, bootstrap-only artifact transition from the observed runtime `d5001797cb94113efd9a8dc26e4a15f2dc130976` to source revision `9c1be0fbe42b48f7a9cd547be36af23413fcfc8e`. This transition is supported only while the host remains unconfigured; upgrades of configured hosts are refused and deferred to a separately reviewed design.

## Goal and non-goals

Prepare the smallest reproducible, non-secret deployment description and a safe way to select the exact initial runtime revision on the observed unconfigured host, while retaining the previous revision. Keep all S2 services inactive until their separately gated configuration and activation prerequisites pass verification.

This design does not create or impersonate an instruction issuer, sign E5, execute provisioning, migrate or initialize a Store, activate a service, dispatch work, or close S2. It does not add a scheduler, coordinator, or assignment authority: GPT-PM accepted the existing bounded `DispatchOwnerService` → authenticated Supervisor/Store → filtered Pub/Sub → `StoreBackedDispatcher` path; production M01 remains open pending real authorized runtime evidence (`docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`). The machine issuer/attestor source design is accepted in principle only; production signing and attestation remain gated by the separate trust-contract review recorded by GPT-PM.

## Current behavior and evidence

The point-in-time WSL inventory records `/opt/vst-runtime` resolving to the immutable `d5001797…` directory, and Supervisor, Runner, and Signer units loaded but inactive. It found no Store database by immediate-entry metadata inspection, so Store disposition remains **UNKNOWN**, not “fresh” (`docs/sdlc/evidence/s2-runtime-bundle-inventory-20261029.md`). The observed identity and UID/GID availability is not a reservation; repeat collision checks immediately before any authorized identity creation.

`tools/qa/install_wsl_runtime.ps1` packages the committed HEAD and writes a root-only source manifest containing schema, full HEAD, and archive SHA-256. `tools/qa/install_wsl_runner_runtime.sh` installs a versioned `/opt/vst-runtime-<HEAD>` tree with a matching manifest and checks systemd unit bytes. Both installers deliberately fail closed if `/opt/vst-runtime` already selects a different revision or an installed unit differs. They install immutable artifacts; they do not implement revision switching, rollback, or service activation. The old runtime and versioned worker helper are retained and must not be overwritten or deleted. `docs/sdlc/S2_VERSIONED_WORKER_HELPER_DESIGN.md` records the same no-overwrite rule for the helper. The inventory shows `/etc/vst-runner`, `/run/vst-supervisor`, and `/run/vst-runner` absent, and the observed relevant loaded units inactive. This supports only a first-deployment transition while those preconditions still hold; it is not evidence for a configured-host upgrade.

Service loaders are strict contracts, not config generators: Supervisor requires its exact field set (`tools/vst/supervisor_service.py`), Runner binds the full helper commit, source digest, binary digest, and exact versioned helper path (`tools/vst/runner_service.py`), Signer has a separate key/ledger contract (`tools/vst/signer.py`), Dispatcher has fixed Supervisor/Runner socket paths (`tools/vst/dispatcher_service.py`), and Dispatch Owner accepts only the fixed principal/OpenSSL contract plus a root-controlled trust registry (`tools/vst/dispatch_owner_service.py`). `tools/vst/systemd/README.md` documents the root-owned config paths, service identities, startup preflight, inactive-by-default operator peer, schema-v6 migration gate, and unit ordering.

## Design

Keep the deployment description separate from secrets and executable authority. Add one canonical, non-secret bundle manifest during source/config preparation. It binds:

- repository identity, full source HEAD, exact archive SHA-256, `docs/SANDBOX_SPEC.md` digest, source-manifest schema, and hashes of all six shipped systemd unit files;
- the exact runtime and worker-helper paths, full helper HEAD, helper source and binary digests, and the expected root/group/mode metadata;
- each service config's schema/field set and intended absolute path, owner, group, and mode; fixed service UID/GID and socket/cgroup relationships; and the required unit start order;
- Store disposition as `UNKNOWN`, `FRESH`, or `EXISTING`, with evidence reference. `UNKNOWN` blocks Store initialization, migration, and service activation. It does not block selecting inactive code artifacts because the bootstrap transition neither opens nor changes Store data. An existing Store is read-only inspected and any migration remains behind its separate gate;
- key purpose, custody owner, and expected key-file path only. Never include private key bytes, passwords, tokens, or signing material. Public trust entries may name a verified public-key path and key ID, but must not be fabricated to make validation pass;
- the prior selected runtime, prior unit digests, and rollback target so the transition is reviewable and recoverable.

Config examples produced at this stage are explicitly non-installable templates: values for runtime keys, issuer identity, signed probe, operator attestation, and unresolved Store disposition remain absent. Do not write placeholder JSON into privileged config paths. A schema validator should reject missing values and any unknown field before installation; the existing loaders remain the final runtime contract.

### Ordered operational stages

1. **Source and config preparation (non-privileged).** Finish source changes and their required test/review gates first. Rebuild the archive from the canonical checkout at the exact reviewed HEAD; record archive, sandbox-spec, helper, and unit digests. Prepare the manifest and non-installable schema templates. Reconcile it with the accepted conditional PM scope in `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`. No WSL state changes.
2. **Artifact staging (conditional GO only).** Recheck host identity and exact old runtime, helper, and unit fingerprints. Require `/etc/vst-runner`, `/run/vst-supervisor`, and `/run/vst-runner` absent; require all six S2 service/socket units inactive, no systemd jobs for them, and no nonempty S2 service cgroups. Verify that the exact new versioned runtime and helper destinations are absent, then install them with no-replace semantics and verify owner, group, mode, manifests, and every digest. Do not create identities, configs, sockets, or Store data in this stage. Store remains UNKNOWN and unopened. Keep every old immutable artifact. Any failed precondition or destination collision aborts before selector or unit changes.
3. **Bootstrap artifact selection (new code required).** Add a separate explicit root transition operation limited to that unconfigured state. It rechecks every staging precondition immediately before mutation and verifies exact old selector/link and fixed-name unit bytes plus exact staged runtime/helper fingerprints against the reviewed manifest. It must refuse if any service config/runtime/socket directory exists, any relevant unit is active/has a job, an S2 cgroup is nonempty, any baseline fingerprint differs, or a destination is unexpected. Preserve old selector and unit bytes as a verified rollback snapshot. Replace the selector and each unit file through same-filesystem temporary files and atomic rename; each individual rename is atomic, while the multi-path set is not one atomic transaction. Record completed replacements in a root-owned transition journal before proceeding to the next path. Re-read and verify all selected paths and fingerprints. Never start, enable, or reload a service as part of selection. This design explicitly refuses configured-host upgrades; support for them needs a later independent cutover/rollback design.
4. **Configuration and Store classification (separately gated).** Only after artifact selection, recheck identities and inspect Store using the authorized procedure. Install exact root-owned configuration only when all values and trust references are known. Store UNKNOWN continues to block initialization, migration, and activation; an EXISTING Store remains read-only until its separate migration gate. Do not generate issuer authority or attestation keys as a side effect of artifact selection.
5. **Service activation (blocked).** Keep units disabled/inactive and production dispatch fail-closed until an authorized issuer policy/key and the applicable accepted machine or human E5 trust contract exist, plus authentic fresh run-bound host/probe evidence passes against the exact sandbox-spec and policy digests. A machine attestation must be explicitly machine-labelled, sourced from independent trusted measurements, and accepted under its own versioned trust domain; it must never masquerade as a human signature. Then, only within the accepted mapped scope and separate activation gate, execute the precise unit activation and runtime E2E sequence. Restricted process/crash/mutation/policy selectors remain `NOT_RUN`.

## State ownership and failure behavior

### Staging and journal implementation contract

Use two different manifests. The reviewed pre-stage source plan binds source HEAD, archive,
sandbox spec, helper source/build recipe, shipped unit bytes and fixed target paths. It does not
claim installed-runtime or compiler-result provenance. After stage-only finishes, a read-only
target-host `prepare` emits a second canonical manifest with the actual complete new tree and
helper binary digests plus the exact old selector/unit/runtime baseline. GPT-PM must review that
second manifest's digest before selector mutation; a locally calculated digest is not approval.

Add an explicit `--stage-only` argument to the distro runtime installer and a corresponding
`-StageOnly` argument to the Windows handoff. Launch the selector with Python `-B -I -S` and
load it from the fixed full-versioned runtime path so importing it cannot create `__pycache__`
inside the immutable measured tree. The repository wrapper must disable bytecode before import.
Default install behavior stays fail-closed and
unchanged. Stage-only validates the same source archive, host restrictions and immutable tree.
Before publication it rescans the complete staged runtime tree against the reviewed member map;
missing, extra, changed, linked, or special files fail closed on fresh and existing destination
paths. Stage-only installs only the absent versioned runtime/helper and must skip the fixed selector/unit
collision checks and ALL selector/unit writes. Report `selected=false`; the separate bootstrap
transition consumes the staged tree, never calls the default installer, and verifies its complete
tree against the source bundle plus helper identity before mutation. Stage-only is not selection
or authority to activate anything.

There are two distinct reviewable records. Before staging, a source/staging plan derived from
the committed archive binds HEAD, archive/spec/unit/helper-source hashes, compile flags and
requested fixed destinations. The V2 plan records every archive member's path, type, size, and
SHA-256; the WSL receiver compares every extracted member with that reviewed map before it hands
the bundle to either installer. A separate non-secret target inventory binds the source HEAD, an
observation no older than five minutes, and compiler selector/resolved path/metadata/digest.
Windows checks its pin and freshness, then WSL repeats them after transfer and verifies the actual
compiler bytes before building the helper. This reviewed plan and source/test gate are prerequisites
to artifact installation.
After staging, a separate read-only `prepare` operation binds the actual complete installed tree,
compiled helper digest/metadata and current old selector/unit baseline. Its exact manifest digest
must be reviewed before selection. A prepared selection manifest cannot retroactively authorize
earlier staging. Neither manifest is a GPT approval, authority delegation or activation permit.

Use a write-ahead journal under a root-owned, mode-0700, no-follow transition directory with
exclusive lock. Before any replacement, persist the exact old and new fingerprints, retained
old bytes/link target, ordered paths and manifest digest; fsync the journal and containing
directory. For each path persist/fsync `intent`, recheck current old fingerprint, rename the
prepared file/link, fsync its parent directory, verify new fingerprint, then persist/fsync
`complete`. A missing completion record never proves a rename did not happen. Recovery checks
EVERY path against old AND new fingerprints, regardless of progress flags: old means untouched
or already restored, new means eligible for exact old restoration, anything else means unresolved
and prohibits writes/start. Refuse an unfinished prior journal on normal apply; explicit recovery
requires its exact original manifest digest and the same inactive/unconfigured preconditions.
Persist/fsync restore intent and completion around each restoration too. Snapshots and journal
are retained, never deleted by successful apply/recovery. No process-crash test is authorized;
later source tests use deterministic injected exceptions only.

The Git source/archive owns revision identity; the root-owned manifest owns the deployment's immutable digest record; systemd owns active unit/process state; the root-controlled Store remains the sole assignment/lease authority; and each root config references purpose-separated key paths without transporting secret bytes in the bundle. No cross-service atomic transaction is assumed. During bootstrap selection, the selector and each fixed-name unit file are changed only while the host is unconfigured and all affected units are inactive. Atomicity applies per rename only. A root-owned journal records progress across the selector and unit replacements. A partial transition fails closed: keep services stopped, inspect which exact renames completed, and restore the prior selector and each old unit file from the verified snapshot before any start. If rollback cannot be proven, leave services inactive and stop for recovery; never claim a collectively atomic replacement. Never infer success from a command exit alone: re-read selector, files, ownership, digests, unit states, and Store/claim disposition.

If the host differs from its reviewed baseline, an unexpected config/key or Store mutation is observed, a key or required signature is unavailable, or any per-path replacement/rollback cannot be proven, stop before modifying that dependency. Store UNKNOWN alone does not block inactive artifact staging/selection, but it blocks any Store initialization, migration, or activation. Preserve all prior runtime/helper artifacts and evidence. No automatic retry may reinterpret an ambiguous dispatch result or reactivate production dispatch.

## Rollback

Before the selector/unit transition, rollback is simply to leave the old selector and units untouched; newly installed versioned artifacts remain retained and inactive. After transition starts but before any service start, use the journal to restore the old selector and each unit file through individual atomic renames, verify their hashes and inactive state, and retain the new immutable tree for diagnosis. These operations are recoverable as a sequence, not one atomic transaction. Once any service starts, do not use this bootstrap rollback as a live downgrade: first reconcile Supervisor/Store/Runner claims and outcomes under the existing recovery contract, then use a separately reviewed and authorized stop/rollback procedure. Never delete or overwrite the old runtime or helper.

## Acceptance and verification plan

The design is accepted when the bundle is deterministic for the exact reviewed HEAD and contains no secret material; schema templates map exactly to existing loaders; Store UNKNOWN/EXISTING states cannot trigger initialization or migration; artifact staging preserves prior artifacts; bootstrap selection refuses a configured host, active/job-bearing units, nonempty S2 cgroups, stale baseline, collision, digest mismatch, and incomplete rollback metadata; the journal recovers interrupted per-path replacements; and no unit is activated by preparation or selection. Configured-host upgrades remain unsupported and must be refused. After implementation is complete, assigned functional/e2e test owners should verify archive/hash binding, schema rejection, no-overwrite behavior, interrupted transition recovery, per-path selector/unit rollback, inactive-unit invariants, refusal on configured hosts, and permitted mapped runtime evidence. No tests, checks, provisioning, migration, or service activation were run for this design artifact.

## Ownership and remaining gate

Codex owns the manifest/schema-preparation and reversible transition implementation plus permitted evidence. GPT-PM owns architecture/source adjudication and the exact-head final gate. The operator is the sole human owner for any human attestation and for genuine key-custody actions. GPT-PM accepted bounded machine trust in principle, but the precise versioned issuer/attestor contracts, independent measurement provenance, key custody/revocation, and separate production authority gate remain incomplete. Until those contracts are reviewed and their applicable evidence is genuine and verified, activation and production dispatch remain blocked, and S2 remains open.

GPT-PM adjudicated the machine issuer/attestor architecture under request `a3e130f0-9aec-4304-b001-388a45c0be55` (reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`): bounded machine trust is accepted in principle, but production signing/attestation remain held pending corrected provenance, independent measurements, and separate authority review. This decision does not authorize production keys, replace the active E5 contract, or activate services. The design must be amended with the precise versioned trust contracts before those components are used.
