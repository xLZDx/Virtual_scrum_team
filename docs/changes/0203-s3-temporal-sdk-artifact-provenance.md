# Change record 0203: Record Temporal SDK Core and artifact provenance audit

## What changed

- Recorded the SDK Python 1.34.0 Core gitlink and pinned SDK Rust commit.
- Distinguished lockfile package resolution from complete license inventory and a minimal runtime profile.
- Recorded official PyPI wheel hashes as artifact identifiers only, because inspected metadata reports `provenance=false`.
- Clarified that the pinned Temporal server Go dependency files do not constitute a comprehensive third-party license inventory or SBOM.
- Updated VST-028, the S3 plan, decision log, lesson log, bilingual report and document registry.

## Why

The candidate audit requires immutable component identity, build/dependency evidence, license closure, and artifact provenance before acquisition. Recording only the Python SDK tag left its Rust Core input unresolved and risked overstating what hashes and lockfiles prove.

## Evidence and limits

- Reviewer: `security-reviewer`, GPT-6 Luna, medium effort. Read-only official source/metadata review; no source checkout, acquisition, install, build, execution or test.
- SDK Python pin: `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`; its `temporalio/bridge/sdk-core` gitlink points to SDK Rust `e163abd6dc19040064986a63c8b8cf4756ffd320`.
- Official pinned evidence: SDK Python [`.gitmodules`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/.gitmodules), [`Cargo.lock`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.lock), [`uv.lock`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/uv.lock), SDK Rust [`Cargo.toml`](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/Cargo.toml), and [`LICENSE.txt`](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/LICENSE.txt).
- Official [PyPI 1.34.0 JSON](https://pypi.org/pypi/temporalio/1.34.0/json) lists wheel hashes but reports `provenance=false` for inspected files. Hashes prove artifact identity/integrity only, not a source-linked build.
- Server [`go.mod`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod) and associated `go.sum` resolve dependencies; no comprehensive server third-party license inventory/SBOM was established by the bounded tree review.
- Transitive third-party license closure, minimal production runtime dependency profile, source-linked wheel provenance/reproducible build, effective server policy, sandbox runtime and exact replay scenario remain open or `NOT_RUN`.

## Ownership and next step

- Accountable task owner: operator for candidate authorization and selection.
- Executor: Codex for bounded source audit and documentation.
- Technical sandbox/service owner: not identified in inspected S3 records.
- Next: finish license closure for the selected runtime profiles and source provenance assessment. Do not acquire or execute before residual audit, operator authorization, and a fresh run-bound S2 probe.

## Verification state

Documentation and registry only. No tests, checks, build, candidate acquisition, installation, or runtime execution were performed.
