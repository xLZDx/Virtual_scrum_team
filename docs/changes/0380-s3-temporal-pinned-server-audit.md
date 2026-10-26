# Change 0380: S3 pinned Temporal server metadata audit

## What changed

- Recorded primary-source metadata for the exact Temporal server commit and its exact-version `nexus-proto-annotations` dependency.
- Updated current state and backlog with the verified source-tag signature status, Go toolchain minimum, dependency versions, and unresolved license notice.

## Why

The S3 plan permits read-only primary-source audit before candidate acquisition. This narrows the technical evidence without downloading or executing candidate material and keeps the legal decision separate from technical inspection.

## Affected contracts and paths

- S3 G01 license/notice and G02 pinned source/dependency provenance.
- `docs/sdlc/evidence/s3-temporal-narrow-compatibility-audit-20261026.md`
- `core/STATE.md`
- `core/BACKLOG.md`

## Evidence and verification

- Exact pinned release: `https://github.com/temporalio/temporal/releases/tag/v1.32.1`, which identifies commit `af08a5e` and displays a verified signature.
- Exact pinned server module: `https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod` declares Go 1.26.8 and requires `nexus-proto-annotations v0.1.0`.
- Exact dependency module metadata: `https://raw.githubusercontent.com/nexus-rpc/nexus-proto-annotations/v0.1.0/go.mod` declares Go 1.25.4 and protobuf v1.36.1.
- The pinned server `LICENSE` is MIT. The dependency's root `LICENSE`, `LICENSE.txt`, and `COPYING` raw paths returned HTTP 404; the repository tree was not exhaustively enumerated, so the exact-version license remains `NOT_VERIFIED`.
- No source or artifact acquisition, build, installation, or execution occurred.

## Decision and limitations

Temporal remains a provisional comparator only. These source facts do not close server binary provenance, full dependency closure, complete SDK/server compatibility, legal notice status, S2 sandbox acceptance, or the S3 runtime comparison. The operator retains the legal/acquisition decision; GPT-PM retains architecture adjudication.
