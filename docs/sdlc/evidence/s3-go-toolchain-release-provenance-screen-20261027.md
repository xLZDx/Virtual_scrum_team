# Go toolchain release provenance screen — 2026-10-27

## Scope and provenance

Read-only cross-check of the official Go downloads index and Go reproducible-build report for the S3 design-pinned `go1.26.10.linux-amd64.tar.gz`. No toolchain archive was downloaded, installed, or executed, and no local checksum was computed.

## Observed official metadata

- The Go downloads index lists `go1.26.10.linux-amd64.tar.gz` with SHA-256 `ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5`.
- The Go reproducible-build report marks `go1.26.10.linux-amd64.tar.gz` with a pass indicator and lists the matching 64-bit digest prefix `ccfe7ae822d2c2f4` for the rebuilt archive.
- The report identifies the source archive `go1.26.10.src.tar.gz` and records `PASS: rebuilt with [GOOS=linux GOARCH=amd64]`.

This independently published Go project evidence supports the reproducibility of the official release for the reported build process. It does not establish that any future locally acquired bytes match the published digest, or that this toolchain has been installed or used for the Temporal server. Local byte verification, module-cache closure, and the server build remain `NOT_RUN`.

## Acceptance and ownership

- Codex: retain this source-only provenance evidence; do not acquire or execute the toolchain under the current scope.
- Operator: authorize any future toolchain/server artifact acquisition as part of the separate legal/acquisition gate.
- GPT-PM: the G03 toolchain design remains accepted at design level only; this source evidence does not extend approval to a build or runtime.

## Primary sources

- [Official Go downloads index](https://go.dev/dl/)
- [Official Go reproducible-build report, go1.26.10](https://go.dev/rebuild)
