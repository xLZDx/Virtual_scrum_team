# S3 Temporal cass_os3 shard-2 artifact detail — 2026-10-27

## Provenance and bounded extraction

Read-only recovery of artifacts for failed `cass_os3` shard 2 in upstream `All Tests` run `37665870783`, exact Temporal Server SHA `af08a5e5f2dd40f545f2afac7780daaa6987001e`. GitHub listed the artifacts under failed job `112946311769`:

| Artifact | ID | Downloaded ZIP bytes | GitHub listed SHA-256 | Locally computed SHA-256 |
|---|---:|---:|---|---|
| `test-summary-json--37665870783--112946311769--1--cass_os3--shard2--functional-test` | `11505227999` | 14,568 | `a626dc457d9c7a39571a7af0f2ca0ac132f0626c70b396377a0279635fe0bc60` | `a626dc457d9c7a39571a7af0f2ca0ac132f0626c70b396377a0279635fe0bc60` |
| `junit-xml--37665870783--112946311769--1--cass_os3--shard2--functional-test` | `11505437566` | 122,301 | `919df4fb8ce68b78316690f84e022ffbc00038894d1bea2f97dec21572693e56` | `919df4fb8ce68b78316690f84e022ffbc00038894d1bea2f97dec21572693e56` |

Both downloaded ZIP digests match GitHub's listed archive digests. The summary archive contained `test-summary.json` (271,733 extracted bytes); the JUnit archive contained one XML file (2,411,281 extracted bytes). The XML was parsed with DTD processing prohibited and external resolution disabled. The archives and extracted files were read in a temporary directory, not copied into the repository; no Temporal source or executable artifact was acquired.

## Reporter counts and limits

- `test-summary.json` contains 676 rows: 675 marked `Failed`, 1 marked `PANIC`.
- 657 of the 675 `Failed` rows show only `=== RUN` / `=== PAUSE` output and no `--- FAIL:` line. These are incomplete/interrupted reporter entries and must not be treated as 657 independently confirmed defects.
- Ten rows contain an explicit `--- FAIL:` marker. Readable examples include two callback carried-over workflow-run ID mismatches, a scheduler backfill assertion, several versioning/task-forward errors, and a timeout-related activity goroutine panic. The suite also records a final 39-minute runner total timeout.
- The JUnit document reports root suite aggregates `tests=5408`, `failures=878`, `errors=0`; child suite aggregates include the initial run, a retry, a final runner-timeout record and an ALERTS record. It contains 4,644 testcase nodes, 676 with a `<failure>` element and 2,459 skipped. These are reporter/attempt aggregates, not unique test failures or unique product defects.
- The artifact does not establish a common root cause or reproducibility. No overall pass/fail percentage or distinct defect count is inferred.

## Newly readable failure signals and proposed VST impact

| Failure signal from artifact | Proposed VST lifecycle intersection | Provisional classification | Boundary / next evidence |
|---|---|---|---|
| `TestCallbacksSuiteCHASM` and `TestCallbacksSuiteHSM` carried-over `WorkflowRunTimeout` retries reported expected/actual workflow run-ID mismatch. | The reviewed G07 method contract explicitly excludes callback/Nexus operations; the synthetic profile does not select callbacks. | `NOT_APPLICABLE_WITH_EVIDENCE` to the current profile. | This says nothing about callbacks generally. Reopen if callback or Nexus operations enter the profile. |
| `TestScheduleCHASM/IdleClose/BackfillBlocks` reported that backfill did not fire after about 30 seconds (144 attempts, zero attempt timeouts). | G07 explicitly excludes schedules and schedule/task-queue administration; the VST profile does not use schedule/backfill APIs. | `NOT_APPLICABLE_WITH_EVIDENCE` to the current profile. | Reopen if schedule/backfill functionality is added. The upstream assertion remains a real failure signal for its test. |
| `TestVersioningFunctionalSuite` cross-task-queue forwarding and workflow-task redirect retries reported context deadlines, `RST_STREAM` cancellation, and one expected/actual version mismatch (`t6225:v1.1` vs `t6225:v1`). | The proposed VST profile fixes run-specific workflow/activity queues and has no cross-task-queue forwarding contract. These failures touch task routing/retry/identity areas, but the artifact does not prove whether the underlying paths intersect the fixed-queue lifecycle. | `UNRESOLVED` for the specific forwarding/redirect failures; retain `QUALIFICATION_REQUIRED` for exact-pair retry and execution-identity behavior. | Do not extend the closed RPC allowlist from these tests. Any later runtime qualification must exercise the selected fixed-queue retry/identity contract and explain whether these feature-specific failures are excluded. |
| `TestStandaloneActivityTestSuite/TestStartDelay/ResetRestoreOriginal...` reported `Fail in goroutine after ... has completed`, with panic from `testing.(*common).Fail`. | The VST profile uses bounded activity processing, cancellation/failure handling and late-result rejection; exact SDK/server runtime behavior is unqualified. | `QUALIFICATION_REQUIRED`. | Future authorized qualification must show timeout/late activity outcomes remain bounded and non-approving. This artifact does not establish the VST path fails. |

The existing classifications for the three SQLite shards are unchanged: Worker Deployment build-ID is outside the fixed-queue/closed-RPC profile; workflow-type length and deadline behavior require qualification; the channel-close warning remains unresolved. Those records are in `s3-temporal-upstream-ci-risk-disposition-20261027.md`.

## Acceptance and next review

- This resolves the prior `cass_os3` **failure-details-unknown** evidence gap (`S3-CI-I02`): the artifacts have now been read and digested, and the shard remains **FAILED**.
- This supplemental artifact surfaces additional upstream failure signals beyond those in GPT-PM's prior `S3-CI-N01` review. The source-only mappings above are provisional until GPT-PM reviews this supplemental record; do not claim that the earlier S3-CI-N01 response adjudicated newly recovered details.
- The earlier S3-CI-N01 source-only closure remains a record of the evidence it reviewed. This supplement neither changes that historical response nor closes exact-pair/runtime compatibility.
- No local acceptance test, build, install, candidate run, network probe, restricted selector, CI rerun, push, PR, or merge was performed.

## Sources and ownership

- GitHub run: [All Tests `37665870783`](https://github.com/temporalio/temporal/actions/runs/37665870783)
- Failed shard job: [cass_os3 shard 2 `112946311769`](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311769)
- Artifact IDs and listed hashes: `s3-temporal-upstream-ci-artifact-metadata-20261027.md`.
- VST operation scope: `s3-temporal-g07-authorization-mapping-20261027.md` and `s3-g03-profile-compatibility-design-20261027.md`.

Codex owns the read-only artifact evidence and impact mapping. GPT-PM owns adjudicating this supplemental architecture evidence. The operator retains legal, acquisition, execution and final-candidate authority. No runtime action is authorized by this record.
