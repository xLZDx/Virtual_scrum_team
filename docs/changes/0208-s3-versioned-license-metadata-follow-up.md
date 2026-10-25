# Change record 0208: Record versioned Temporal license metadata follow-up

## What changed

- Resolved license metadata for all 362 registry package/version entries in the pinned Temporal Python bridge `Cargo.lock`; all 362 crates.io checksums matched the lock. These entries include optional, build, and target-specific dependencies.
- Reconciled the 11 direct Rust registry crate licenses and recorded exact-version license pages for 15 illustrative Temporal server Go modules.
- Audited the broader 223-entry Go `go.mod` version list; recorded 116 license pages, one page without license data, and 106 lookup errors after HTTP 429 rate limiting. Full Go closure remains incomplete.
- Updated the S3 plan, backlog, bilingual report, decision log, lesson log, and generated document registry. This addendum supersedes the `UNKNOWN` status for the 11 Rust and 15 Go direct entries in change 0207.

## Why

The lockfile and module graph expose package versions but not licenses. Exact-version registry/module license metadata was available for the direct subset, and crates.io metadata allowed a lock-checksum consistency check for the complete Cargo registry version set. The Go full-graph lookup hit service rate limits; it must remain explicitly partial.

## Evidence and limits

- Read-only metadata requests only. No package archive, candidate source repository, or binary was downloaded; no install, build, execution, or test occurred.
- Temporal Python SDK/Core source pin: `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`; [pinned Cargo.lock](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.lock). A scan of 362 registry crate/version entries returned a crates.io license field for every entry and a SHA-256 checksum matching the lock entry. This is the complete registry-version inventory of the lock, not a default-runtime or selected-artifact claim. The JSON parser initially misread one response whose feature keys differ only by case; a case-preserving parse rechecked all 362 entries and returned 0 missing licenses, 0 lookup errors, and 0 checksum mismatches. A subsequent attempt to serialize all 362 rows was rate-limited by crates.io HTTP 429; no full machine-readable artifact was created.
- Exact-version direct Rust crate license pages:

| Crate/version | crates.io license metadata |
|---|---|
| [anyhow 1.0.104](https://crates.io/api/v1/crates/anyhow/1.0.104) | `MIT OR Apache-2.0` |
| [async-trait 0.1.91](https://crates.io/api/v1/crates/async-trait/0.1.91) | `MIT OR Apache-2.0` |
| [futures 0.3.33](https://crates.io/api/v1/crates/futures/0.3.33) | `MIT OR Apache-2.0` |
| [prost 0.14.4](https://crates.io/api/v1/crates/prost/0.14.4) | `Apache-2.0` |
| [pyo3 0.29.0](https://crates.io/api/v1/crates/pyo3/0.29.0) | `MIT OR Apache-2.0` |
| [pyo3-async-runtimes 0.29.0](https://crates.io/api/v1/crates/pyo3-async-runtimes/0.29.0) | `Apache-2.0` |
| [pythonize 0.29.0](https://crates.io/api/v1/crates/pythonize/0.29.0) | `MIT` |
| [tokio 1.53.1](https://crates.io/api/v1/crates/tokio/1.53.1) | `MIT` |
| [tokio-rustls 0.26.4](https://crates.io/api/v1/crates/tokio-rustls/0.26.4) | `MIT OR Apache-2.0` |
| [tokio-stream 0.1.19](https://crates.io/api/v1/crates/tokio-stream/0.1.19) | `MIT` |
| [tonic 0.14.6](https://crates.io/api/v1/crates/tonic/0.14.6) | `MIT` |

- Temporal server source pin: `af08a5e5f2dd40f545f2afac7780daaa6987001e`; pinned [go.mod](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod). Exact-version [pkg.go.dev license pages](https://pkg.go.dev/go.temporal.io/api@v1.63.5?tab=licenses) confirmed the following 15 illustrative direct module licenses:

| Go module/version | License |
|---|---|
| [cloud.google.com/go/storage v1.62.1](https://pkg.go.dev/cloud.google.com/go/storage@v1.62.1?tab=licenses) | `Apache-2.0` |
| [github.com/aws/aws-sdk-go-v2 v1.43.4](https://pkg.go.dev/github.com/aws/aws-sdk-go-v2@v1.43.4?tab=licenses) | `Apache-2.0` |
| [github.com/aws/aws-sdk-go-v2/config v1.32.16](https://pkg.go.dev/github.com/aws/aws-sdk-go-v2/config@v1.32.16?tab=licenses) | `Apache-2.0` |
| [github.com/aws/aws-sdk-go-v2/credentials v1.19.15](https://pkg.go.dev/github.com/aws/aws-sdk-go-v2/credentials@v1.19.15?tab=licenses) | `Apache-2.0` |
| [github.com/aws/aws-sdk-go-v2/service/s3 v1.99.1](https://pkg.go.dev/github.com/aws/aws-sdk-go-v2/service/s3@v1.99.1?tab=licenses) | `Apache-2.0` |
| [github.com/go-jose/go-jose/v4 v4.1.4](https://pkg.go.dev/github.com/go-jose/go-jose/v4@v4.1.4?tab=licenses) | `Apache-2.0` |
| [github.com/go-sql-driver/mysql v1.9.3](https://pkg.go.dev/github.com/go-sql-driver/mysql@v1.9.3?tab=licenses) | `MPL-2.0` |
| [github.com/gocql/gocql v1.7.0](https://pkg.go.dev/github.com/gocql/gocql@v1.7.0?tab=licenses) | `Apache-2.0` |
| [github.com/jackc/pgx/v5 v5.10.0](https://pkg.go.dev/github.com/jackc/pgx/v5@v5.10.0?tab=licenses) | `MIT` |
| [github.com/lib/pq v1.12.3](https://pkg.go.dev/github.com/lib/pq@v1.12.3?tab=licenses) | `MIT` |
| [github.com/prometheus/client_golang v1.21.0](https://pkg.go.dev/github.com/prometheus/client_golang@v1.21.0?tab=licenses) | `Apache-2.0` |
| [go.temporal.io/api v1.63.5](https://pkg.go.dev/go.temporal.io/api@v1.63.5?tab=licenses) | `MIT` |
| [go.temporal.io/sdk v1.44.0](https://pkg.go.dev/go.temporal.io/sdk@v1.44.0?tab=licenses) | `MIT` |
| [google.golang.org/grpc v1.83.2](https://pkg.go.dev/google.golang.org/grpc@v1.83.2?tab=licenses) | `Apache-2.0` |
| [google.golang.org/protobuf v1.36.11](https://pkg.go.dev/google.golang.org/protobuf@v1.36.11?tab=licenses) | `BSD-3-Clause` |

- The full versioned Go lookup counted 223 `go.mod` module/version entries: 116 license pages contained license sections, one (`github.com/nexus-rpc/nexus-proto-annotations@v0.1.0`) had no license section, and 106 lookups failed after HTTP 429 responses began. These are counts of metadata lookups, not unique runtime dependencies. Full Go license/notice closure and the runtime-only build profile remain `NOT_VERIFIED`.
- Candidate choice, acquisition authorization, source-linked wheel provenance, general server/SDK compatibility, effective server policy, and runtime containment remain open.

## Ownership and next step

- Accountable task owner: operator for candidate selection and acquisition authorization.
- Executor: Codex for bounded read-only source and metadata audit.
- Technical sandbox/service owner: not identified in inspected S3 records.
- Next: when pkg.go.dev rate limiting recovers, retry the 106 failed Go version lookups and resolve the one package page without a license section; persist the full versioned Go inventory. Then define the selected candidate's runtime/build profile and close applicable build notices. Do not acquire or execute before explicit authorization and a fresh run-bound S2 probe.

## Verification state

Documentation-only metadata audit. No tests, checks, build, package download, candidate acquisition, installation, or runtime execution were performed.
