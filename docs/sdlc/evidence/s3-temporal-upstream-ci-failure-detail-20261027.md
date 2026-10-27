# S3 Temporal upstream SQLite CI failure-log screen — 2026-10-27

## Scope and provenance

Read-only examination of historical GitHub Actions logs for the upstream `All Tests` run `37665870783` on exact Temporal Server SHA `af08a5e5f2dd40f545f2afac7780daaa6987001e` (`release/v1.32.x`). Logs were fetched through the connected GitHub workflow-job-logs tool and inspected in memory; no raw log archive or artifact was saved. This was not a local test run and did not download a Temporal candidate binary.

## Decoded failed SQLite shard summaries

| Job | Partial test-run summary in the job log | Additional observed log text |
|---|---|---|
| [SQLite shard 0 — job 112946311749](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311749) | 2,782 tests; 1,491 skipped; 49 failures; 1,114.498 seconds. The runner later reached its 39-minute total timeout and reported partial results from two completed attempts. | Versioning-test output repeatedly reported that build ID `b_2` was not found in Worker Deployment `v3`; the wait ended with `context deadline exceeded`. |
| [SQLite shard 1 — job 112946311912](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311912) | 2,829 tests; 1,497 skipped; 52 failures; 1,285.911 seconds. The runner later reached its 39-minute total timeout and reported partial results from one completed attempt. | Logs include a SQLite `workflow_type_name` length CHECK failure (observed value 275 against limit 255), repeated context deadlines, and a `send on closed channel` warning in a versioning test. |
| [SQLite shard 2 — job 112946311985](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311985) | 2,826 tests; 1,486 skipped; 59 failures; 1,210.576 seconds. The runner later reached its 39-minute total timeout and reported partial results from one completed attempt. | The extracted failure lines include repeated `context deadline exceeded` errors. |

These are upstream per-shard report counts, not unique defect counts. The logs establish observed failures and timeout behavior but do not establish one root cause or whether the failures are reproducible. Resource pressure, runner contention, flaky tests, and product defects are not distinguished by this screen.

The All Tests run also had failed `cass_os3` shard 2 (job `112946311769`). The workflow-job-logs tool returned an empty content field for that request in this turn; its failure details remain unknown. No test-summary artifact was downloaded.

## Acceptance disposition

This evidence adds risk information to the read-only candidate audit. It does not overturn or finalize the provisional Temporal selection by itself, and it does not prove that the SQLite profile is the selected deployment profile. No local acceptance test, build, installation, candidate execution, or policy selector was run. Source-to-release-asset digest verification, exact target runtime compatibility, and legal/acquisition disposition remain open. The historical upstream CI result is not local acceptance evidence.

Owner: Codex owns source evidence and failure-log follow-up; GPT-PM owns architecture adjudication; operator retains legal/acquisition authority. Next: present the complete S3 candidate decision and these bounded CI facts to GPT-PM for adversarial architecture adjudication; leave the final candidate decision provisional until required runtime/compatibility evidence is authorized and available.

## Primary evidence

- [All Tests workflow run](https://github.com/temporalio/temporal/actions/runs/37665870783)
- [SQLite shard 0 job](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311749)
- [SQLite shard 1 job](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311912)
- [SQLite shard 2 job](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311985)
- [cass_os3 shard 2 job](https://github.com/temporalio/temporal/actions/runs/37665870783/job/112946311769)
- Earlier run and build-profile reconciliation: `s3-temporal-server-build-profile-source-screen-20261027.md` and change 0419.
