# S3 Temporal Server pinned build-profile source screen — 2026-10-27

## Scope and provenance

Read-only inspection of build configuration and module metadata at the already pinned Temporal Server commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` (`v1.32.1`). No release asset, module archive, or source archive was acquired. No build, installation, or candidate execution was performed.

## Source-declared profile

- The pinned `go.mod` declares `go 1.26.8`.
- The pinned `.goreleaser.yml` identifies itself as GoReleaser v2 configuration and defines a `temporal-server` build from `cmd/server` with `CGO_ENABLED=0`.
- The declared server build targets Linux, macOS, and Windows for `amd64` and `arm64`; Linux amd64 is therefore included in the source-declared build matrix.
- The archive configuration includes the `temporal-server` binary and other server tools. The configured checksum file is `checksums.txt` and its algorithm is SHA-256.
- The configuration has a pre-build `go mod download` hook.

These are repository configuration facts only. They do not identify the exact workflow invocation, runner image, effective toolchain patch version, release-job logs, build provenance attestation, or a cryptographic binding between the published Linux archive and this source commit. The previously recorded official Go 1.26.10 digest is a design/toolchain metadata proposal; this source screen does not establish that the pinned release was built with Go 1.26.10. Source-to-binary provenance, local artifact hash verification, selected runtime closure, and runtime compatibility remain `NOT_VERIFIED` or `NOT_RUN`.

## Acceptance and ownership

- Codex: retain this source-only profile evidence and continue bounded primary-source audit.
- Operator: decide legal/acquisition disposition before any artifact is obtained.
- GPT-PM: adjudicate architecture; neither this configuration nor design acceptance authorizes acquisition or runtime claims.

## Primary sources

- [Pinned Temporal Server `.goreleaser.yml`](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/.goreleaser.yml)
- [Pinned Temporal Server `go.mod`](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod)
- [Pinned Temporal Server release metadata screen](s3-temporal-server-release-provenance-screen-20261027.md)
- [Pinned Go toolchain release metadata screen](s3-go-toolchain-release-provenance-screen-20261027.md)
