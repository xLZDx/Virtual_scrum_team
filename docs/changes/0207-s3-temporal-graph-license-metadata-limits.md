# Change record 0207: Enumerate Temporal dependency metadata limits

## What changed

- Enumerated a bounded direct Rust-crate subset from the pinned Temporal Python bridge manifest and lockfile, and a bounded direct Go-module subset from the pinned Temporal server module files.
- Recorded that versions/checksums do not provide the third-party license evidence or runtime-only dependency closure needed by VST-028.
- Updated the S3 plan, backlog, bilingual report, decision log, lesson log, and generated document registry.

## Why

Change 0206 mapped a hypothetical Python base profile but left the native bridge and server dependency graphs at a broad summary level. The follow-up determines what can be stated from the official pinned graph files and what still requires per-version license records and a feature/target-specific inventory.

## Evidence and limits

- Reviewer: `security-reviewer`, GPT-6 Luna, medium effort. Read-only inspection of official pinned raw manifests/lockfiles; no source package acquisition, download, install, build, execution, or tests.
- Python SDK bridge at `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`: [`Cargo.toml`](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.toml) selects `tls-ring` by default. The audit enumerated 11 direct Rust registry crate/version pairs: `anyhow 1.0.104`, `async-trait 0.1.91`, `futures 0.3.33`, `prost 0.14.4`, `pyo3 0.29.0`, `pyo3-async-runtimes 0.29.0`, `pythonize 0.29.0`, `tokio 1.53.1`, `tokio-rustls 0.26.4`, `tokio-stream 0.1.19`, `tonic 0.14.6`. Their licenses are `UNKNOWN`: the [`Cargo.lock`](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.lock) carries versions/checksums/edges but no license fields; exact-version authoritative license records were not retrieved. Optional FIPS/`aws-lc` is not part of the default `tls-ring` feature. The 3,553-line lock contains optional/target/build entries, so 11 is a bounded direct subset, not a total graph count.
- Temporal server at `af08a5e5f2dd40f545f2afac7780daaa6987001e`: official [`go.mod`](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod) and [`go.sum`](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.sum) were read at pinned commit. The audit resolved 15 illustrative direct module/version entries: `cloud.google.com/go/storage 1.62.1`; AWS SDK v2 `core 1.43.4`, `config 1.32.16`, `credentials 1.19.15`, `service/s3 1.99.1`; `go-jose/v4 4.1.4`; MySQL driver `1.9.3`; `gocql 1.7.0`; `pgx/v5 5.10.0`; `lib/pq 1.12.3`; Prometheus `client_golang 1.21.0`; Temporal API `1.63.5` and SDK `1.44.0`; gRPC `1.83.2`; protobuf `1.36.11`. License status is `UNKNOWN` for these entries because `go.mod`/`go.sum` record module versions/hashes, not licenses. The files are 239 and 716 lines respectively; no total module count or runtime-only graph was established.
- Candidate choice/profile remains open. The 11 and 15 counts are bounded subsets, not license-closure totals. Minimum next evidence: authoritative version-specific license/notice sources and a feature/target/build-resolved inventory such as a pinned SBOM.

## Ownership and next step

- Accountable task owner: operator for candidate selection and acquisition authorization.
- Executor: Codex for bounded read-only source audit and documentation.
- Technical sandbox/service owner: not identified in inspected S3 records.
- Next: identify authoritative license/notice evidence and a resolved feature/target build inventory for the operator-selected profile. Do not acquire or execute before explicit authorization and a fresh run-bound S2 probe.

## Verification state

Documentation-only source audit. No tests, checks, build, package download, candidate acquisition, installation, or runtime execution were performed.
