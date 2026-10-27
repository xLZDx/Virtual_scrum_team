# S3 Temporal upstream CI risk disposition — 2026-10-27

## Scope and decision boundary

This is the bounded source-only disposition requested by GPT-PM finding `S3-CI-N01`. It maps each failure family reported by the pinned-source upstream CI screen to the proposed VST lifecycle. It does not reproduce the failures, establish root cause, change candidate pins, qualify the server/SDK pair, or authorize acquisition, build, install, or execution.

Reviewed candidate pins:

- Temporal Server `v1.32.1`, commit `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- Python SDK `1.34.0`, commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`; SDK Core gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320`.

The source-only VST profile uses one synthetic namespace, fixed per-run workflow/activity task queues, exact workflow/execution identity, a trusted adapter and a mandatory deny-by-default gateway. Default and visibility persistence are proposed as file-backed SQLite. Workflow type and queue values are constrained fields, but the inspected profile does not freeze their concrete strings. These are design facts, not deployed or runtime evidence. Primary in-repository references are the G03 compatibility design, G07 authorization mapping, exact-config proposal, and target-profile proposal listed below.

## Per-shard evidence and disposition

| Upstream shard and evidence | Observed failure family | VST lifecycle intersection | Disposition | Boundary / required qualification |
|---|---|---|---|---|
| SQLite shard 0, job [112946311749](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311749), Server SHA above | Worker Deployment v3 could not find build ID `b_2` during versioning output | The proposed G07 method map contains no Worker Deployment/build-ID operation; the profile uses fixed queues and has no candidate/admin registration fallback. | `NOT_APPLICABLE_WITH_EVIDENCE` to the currently proposed VST lifecycle | This class is outside the reviewed method/path contract. Its upstream root cause remains unknown. If a later profile uses Worker Deployment or build-ID routing, reopen and qualify this path before acceptance. |
| SQLite shard 1, job [112946311912](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311912) | SQLite rejected observed `workflow_type_name` length 275 against a 255-character constraint | The VST profile proposes file-backed SQLite and constrains the workflow-type field, but does not freeze the concrete workflow-type value. | `QUALIFICATION_REQUIRED` | Before runtime acceptance, freeze the exact workflow-type string and verify it against the pinned schema/storage behavior; exercise the selected profile under its approved bounded runtime evidence. Until then, applicability is not cleared. |
| SQLite shards 0/1/2, jobs [112946311749](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311749), [112946311912](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311912), [112946311985](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311985) | Repeated `context deadline exceeded`; each shard later reported the upstream runner's 39-minute overall timeout | The VST lifecycle includes bounded startup, polling, workflow/activity processing, STOP and recovery. The G03 design requires timeouts and ambiguous outcomes to fail closed, but the exact pair and bounded resource behavior are not runtime-qualified. | `QUALIFICATION_REQUIRED` | Later authorized qualification must demonstrate bounded operations and non-approving timeout/reconciliation behavior for the selected lifecycle. The upstream runner timeout is a different measurement and is not compared to a VST budget. |
| SQLite shard 1, job [112946311912](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311912) | One `send on closed channel` warning in versioning-related output | The current profile has worker polling, cancellation, retry and shutdown paths, but the available log excerpt does not establish which call/channel closed or whether it intersects those paths. | `UNRESOLVED` | Do not infer irrelevance from the test label. Keep the behavior open for any later lifecycle/retry/shutdown qualification; preserve the exact uncertainty unless readable source evidence narrows it. |
| Failed `cass_os3` shard 2, job [112946311769](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311769) | Initially unread; subsequently decoded summary/JUnit artifacts report callback run-ID mismatches, a scheduler backfill assertion, versioning/task-forward errors, an activity goroutine panic, and an overall runner timeout. | Details and provisional classifications are in `s3-temporal-cassos3-artifact-detail-20261027.md`. Callback/schedule cases are outside the proposed API scope; versioning/task-forward paths remain unresolved; activity timeout/error handling requires qualification. | `DETAILS RECOVERED`; supplemental impact review pending GPT-PM | The shard remains failed. The decoded outputs do not establish common root cause, reproducibility, or local acceptance. Do not aggregate reporter rows as unique defects. |

The per-shard failure totals (49/52/59) are partial upstream reports and not distinct-defect counts. The three SQLite jobs each later hit the reported 39-minute runner timeout. Root cause and reproducibility remain unknown across all shards; no common cause is inferred. `cass_os3` is a separate unknown and is not conflated with SQLite.

## Acceptance disposition

- The exact-pinned upstream `All Tests` run remains **FAILED**. Successful Build/Publish or Release workflows do not overwrite that result.
- `S3-CI-N01` has a reasoned source-only disposition for every observed error family. The concrete workflow type is still not frozen, deadline behavior and the closed-channel warning remain open qualifications, and `cass_os3` failure details remain unknown.
- The read-only Temporal comparator remains provisional. This disposition does not establish exact server/SDK compatibility, runtime acceptance, or candidate suitability.
- G03/G07 runtime qualification remains open. SQLite persistence/recovery, identity reconciliation, bounded timeout handling and unexpected-error behavior still require authorized evidence.
- S3-CI-I01 source-to-artifact provenance remains incomplete. The evidence-availability portion of S3-CI-I02 is resolved by verified summary/JUnit downloads; the shard remains failed and its supplemental impact mapping awaits GPT-PM review. See `s3-temporal-cassos3-artifact-detail-20261027.md`.
- No local acceptance test, build, install, candidate run, network probe, restricted selector, push, PR or merge was performed.

## Correlated GPT-PM adjudication

- Project: `virtual_scrum_team`.
- Request ID: `c91fcd58-8ab7-4bf5-994b-c3ea8f1c4713`.
- Conversation: `6ae05dd9-6a90-83ed-901d-e60b81981dae`.
- User turn: `f06da59e-e43a-4011-8fd1-e6308749c3fd`.
- Reply: `48f7b17e-69ab-412b-aa83-17de146f1c9f`.
- Job: `4fd15141-45f6-445a-9483-5216dbc16b96`; final poll reported complete and `correlated=true`.
- GPT-PM verdict: **ACCEPT — provisional read-only comparator retained**; 0 new architecture BLOCKER, 0 new architecture MAJOR, 1 MINOR (`S3-CI-N01`) and 2 INFO (`S3-CI-I01`, `S3-CI-I02`). Acquisition/runtime readiness remains `NOT_APPROVED`; final winner/TOP remains none.
- The first wait timed out; the later durable job-status and reply retrieval confirmed the exact correlated response. This was architecture adjudication, not exact-head implementation approval.

GPT-PM's `S3-CI-N01` closure criterion is that every observed error family receives a reasoned impact disposition. The correlated focused verification at declared HEAD `0a9a70bd5d80a64bba4c7d6e9f8ae7f47dd24ac6` closed `S3-CI-N01` at source-only documentation level; exact response and correlation are recorded in `s3-temporal-upstream-ci-gptpm-verification-20261027.md`. GPT-PM added `S3-CI-I03` (INFO): preserve this documentation closure as distinct from compatibility closure. Root-cause resolution is not required to retain a read-only comparator, but lifecycle-relevant unresolved failures remain open for later runtime acceptance.

## Sources and ownership

- `s3-temporal-upstream-ci-failure-detail-20261027.md` — observed shard summaries and error text.
- `s3-temporal-upstream-ci-artifact-metadata-20261027.md` — `cass_os3` artifact metadata and limits.
- `s3-temporal-cassos3-artifact-detail-20261027.md` — decoded `cass_os3` outputs and supplemental impact mapping.
- `s3-temporal-target-profile-proposal-20261027.md` — provisional pins and proposed lifecycle profile.
- `s3-g03-profile-compatibility-design-20261027.md` — fixed queues, bounded lifecycle and SQLite profile.
- `s3-temporal-g07-authorization-mapping-20261027.md` and `s3-temporal-g07-exact-config-proposal-20261027.md` — closed RPC map, identity and file-backed persistence design.

Codex owns documenting this bounded impact mapping and coordinating exact-head verification. GPT-PM owns design adjudication. The operator retains legal, acquisition, execution and final-candidate decisions. No operator decision is required to retain the current read-only comparator.
