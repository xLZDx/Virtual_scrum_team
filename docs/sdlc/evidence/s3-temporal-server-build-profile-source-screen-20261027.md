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

## Public workflow-run observation

The GitHub Actions API was queried read-only for runs whose `head_sha` is exactly `af08a5e5f2dd40f545f2afac7780daaa6987001e`. It returned four runs:

- `Build and Publish`, event `push`, branch `release/v1.32.x`, run `37665870819`, completed `success` on 2026-10-07.
- `All Tests`, event `push`, branch `release/v1.32.x`, run `37665870783`, completed `failure` on 2026-10-07.
- `Release`, event `release`, branch `v1.32.1`, run `37850182088`, completed `success` on 2026-10-08.
- `Trigger version-info-service release`, event `release`, branch `v1.32.1`, run `37850182398`, completed `success` on 2026-10-08.

The successful build-and-publish run is direct evidence that the exact pinned commit had a successful workflow result. It does not alone prove that the published Linux amd64 release asset came from a specific uploaded workflow artifact, that the asset bytes match the workflow output, or that a provenance attestation binds source, builder, and digest. The separate `All Tests` workflow failed; this record does not infer the failing job or reason. The full API response and linked logs/artifacts were not retrieved. No asset, log bundle, or build artifact was downloaded; no local checksum, build, install, or candidate execution occurred. These observations do not close S3 provenance, runtime, compatibility, or legal/acquisition acceptance.

## Acceptance and ownership

- Codex: retain this source-only profile evidence and continue bounded primary-source audit.
- Operator: decide legal/acquisition disposition before any artifact is obtained.
- GPT-PM: adjudicate architecture; neither this configuration nor design acceptance authorizes acquisition or runtime claims.

## Primary sources

- [Pinned Temporal Server `.goreleaser.yml`](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/.goreleaser.yml)
- [Pinned Temporal Server `go.mod`](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod)
- [Pinned Temporal Server release metadata screen](s3-temporal-server-release-provenance-screen-20261027.md)
- [Pinned Go toolchain release metadata screen](s3-go-toolchain-release-provenance-screen-20261027.md)
- [Pinned commit Build and Publish run](https://github.com/temporalio/temporal/actions/runs/37665870819)
- [Pinned commit All Tests run](https://github.com/temporalio/temporal/actions/runs/37665870783)
- [Pinned tag Release run](https://github.com/temporalio/temporal/actions/runs/37850182088)
- [Pinned commit Build and Publish run](https://github.com/temporalio/temporal/actions/runs/37665870819)
- [Pinned commit All Tests run](https://github.com/temporalio/temporal/actions/runs/37665870783)
- [Pinned tag Release run](https://github.com/temporalio/temporal/actions/runs/37850182088)
