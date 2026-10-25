# Change record 0212: Persist the versioned Temporal Go license metadata scan

## What changed

- Added a 223-row TSV mapping each pinned Temporal server Go module/version to the exact pkg.go.dev HTTP status and displayed license metadata.
- Reconciled the S3 plan, VST-028 backlog, bilingual report, decision/lesson logs, and generated document registry with the controlled rerun.

## Why

The earlier 223-row scan produced only aggregates and 106 transient HTTP 429 responses; it did not preserve its full package-level output. A low-rate, parser-validated rerun produced a complete row-level record and an accurate denominator. The output is needed to identify unresolved exact versions without downloading candidate packages.

## Evidence and limits

- Audit: read-only security reviewer, GPT-6 Luna, medium effort. The exact pinned source was Temporal server commit `af08a5e5f2dd40f545f2afac7780daaa6987001e`; its raw `go.mod` returned HTTP 200 and yielded 223 module/version rows.
- Each version was queried at `https://pkg.go.dev/<module>@<version>?tab=licenses` with a controlled one-second cadence. Parser controls: `cloud.google.com/go/storage@v1.62.1` displayed `Apache-2.0`; `nexus-proto-annotations@v0.1.0` displayed `License: None detected`.
- Final result: 211/223 pages returned HTTP 200 with license sections; 1/223 returned HTTP 200 with `License: None detected`; 11/223 exact-version pages returned HTTP 404; no HTTP 429 occurred in this rerun. The 12 rows without license values remain `UNKNOWN`/`NOT_VERIFIED`, not proof of no license. Individual status and metadata are in `docs/sdlc/evidence/s3-temporal-server-go-license-metadata-2026-10-25.tsv`.
- Exact comma-delimited pkg.go.dev metadata group counts: `Apache-2.0` 87; `Apache-2.0, BSD-3-Clause` 14; `Apache-2.0, BSD-3-Clause, MIT` 2; `Apache-2.0, MIT` 2; `BSD-2-Clause` 2; `BSD-2-Clause-Views` 1; `BSD-2-Clause, ISC` 1; `BSD-3-Clause` 31; `ISC` 1; `MIT` 68; `MPL-2.0` 2 (211 total rows with license sections). Commas preserve the page's metadata values; they are not interpreted here as license conjunctions.
- No source/package/archive was downloaded. No installation, build, candidate execution, or test occurred. The 223 rows include indirect/build/test modules and do not define a selected runtime profile or complete legal notice closure. Candidate selection/acquisition, 12 unresolved version licenses, runtime/build selection, and compatibility remain open.

## Ownership and next step

- Accountable task owner: operator for the delegated S3 sprint.
- Audit executor: Codex; the security-reviewer agent performed read-only metadata lookup.
- The technical candidate/runtime service owner is not established in canonical repository records. Operator owns candidate choice and acquisition authorization.
- Next: obtain exact-version license evidence for the 12 unresolved rows where available. After candidate choice, map the selected target/runtime/build profile and source-linked artifact provenance; do not acquire/run before explicit authorization and a fresh S2 probe.

## Verification state

The TSV was read back with PowerShell `Import-Csv -Delimiter "`t"`: 223 data rows, HTTP 200 = 212, HTTP 404 = 11, and rows without a versioned license value = 12. Registry generation, report conformance, and `git diff --check` are recorded by the commit workflow. No test/build was run.
