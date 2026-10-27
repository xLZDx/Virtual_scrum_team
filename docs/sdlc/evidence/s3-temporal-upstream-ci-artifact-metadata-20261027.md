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

Owner: Codex owns read-only source and artifact metadata reconciliation; GPT-PM owns architecture adjudication; the operator retains legal/acquisition authority. Next: use the artifact ID through authorized GitHub access if the exact test summary is required for the architecture decision; keep this metadata distinct from interpreted test evidence.
