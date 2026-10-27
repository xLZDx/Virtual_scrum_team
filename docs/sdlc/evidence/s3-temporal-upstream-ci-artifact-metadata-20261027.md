# S3 Temporal upstream CI artifact metadata follow-up — 2026-10-27

## Scope and provenance

Read-only artifact metadata for upstream `All Tests` run `37665870783`, exact server SHA `af08a5e5f2dd40f545f2afac7780daaa6987001e`. GitHub's artifact-list API returned entries bound to that workflow run and source SHA.

## `cass_os3` shard 2

The API listed these artifacts for failed job `112946311769`:

| Artifact | ID | Listed size | GitHub listed archive digest |
|---|---:|---:|---|
| `test-summary-json--37665870783--112946311769--1--cass_os3--shard2--functional-test` | `11505227999` | 14,568 bytes | `sha256:a626dc457d9c7a39571a7af0f2ca0ac132f0626c70b396377a0279635fe0bc60` |
| `junit-xml--37665870783--112946311769--1--cass_os3--shard2--functional-test` | `11505437566` | 122,301 bytes | `sha256:919df4fb8ce68b78316690f84e022ffbc00038894d1bea2f97dec21572693e56` |

The test-summary ZIP was retrieved through the connected GitHub artifact tool as a temporary file reference, but the file contents were not decoded or inspected in this session. The JUnit artifact was not downloaded. The listed digests are metadata from GitHub; the downloaded archive bytes were not independently hashed or compared to the listed digest. The separate job-log tool returned empty content for this job. Therefore the failed tests, count and cause for this shard remain unknown.

## Acceptance disposition

This improves artifact traceability only. It does not establish a root cause, product defect, reproducibility, or local acceptance result. No test was run locally, no candidate artifact was acquired, and no repository artifact copy was stored. Temporal remains a provisional comparator pending GPT-PM architecture adjudication and the open source-to-asset, runtime, license, and common-fixture gates.

Owner: Codex owns read-only source and artifact metadata reconciliation; GPT-PM owns architecture adjudication; the operator retains legal/acquisition authority. At this initial metadata stage, the artifact contents were still unread.

## Content recovery update — 2026-10-27

Codex subsequently downloaded both listed archives through the connected GitHub Actions artifact tool and inspected them read-only. The locally computed SHA-256 values match the GitHub-listed archive digests for summary artifact `11505227999` and JUnit artifact `11505437566`. The extracted summary and JUnit content, bounded counts, newly visible failure families and provisional VST-impact classifications are recorded in `s3-temporal-cassos3-artifact-detail-20261027.md`. The earlier `FAILURE_DETAILS_UNKNOWN` status is superseded as an evidence-availability statement; the shard remains failed, causes/reproducibility remain unknown, and GPT-PM review of the newly recovered impact mapping is pending. No candidate source or executable artifact was downloaded or run.
