# S3 Temporal dependency license metadata screen — 2026-10-27

## Scope

Read-only comparison of publicly displayed repository-level metadata with the exact S3-pinned dependency tag `github.com/nexus-rpc/nexus-proto-annotations@v0.1.0`. No source archive, module archive, candidate binary, or other artifact was downloaded. No legal conclusion is made.

## Observations

- The Temporal server pin `af08a5e5f2dd40f545f2afac7780daaa6987001e` requires `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`; see the exact pinned server `go.mod` link below and the existing narrow compatibility audit.
- The official GitHub repository page for `nexus-rpc/nexus-proto-annotations` at tag `v0.1.0` lists the repository's visible root entries. The listing includes `go.mod`, `go.sum`, `README.md`, and source directories, but no root license or notice file.
- GitHub's organization repository listing displays an MIT repository-level badge for `nexus-proto-annotations`. That listing is not bound to tag `v0.1.0` and does not expose the license text or its applicability to that exact version.
- Existing exact-tag checks recorded HTTP 404 for conventional root files `LICENSE`, `LICENSE.txt`, and `COPYING`; the exact tag tree search found no `LICENSE`, `LICENSE.md`, `LICENCE`, `COPYING`, `NOTICE`, or `COPYRIGHT`. Existing pkg.go.dev metadata recorded `NONE_DETECTED` for v0.1.0.

## Interpretation and acceptance

The repository-level MIT badge is a new metadata signal, but it does not reconcile the missing exact-tag notice and `NONE_DETECTED` package result. The exact-version legal status therefore remains `NOT_VERIFIED`; this evidence is not legal approval and does not authorize acquisition, build, installation, or execution. Operator owns legal disposition. Codex owns any additional read-only evidence package; GPT-PM owns architectural adjudication.

## Primary sources

- [nexus-proto-annotations repository at exact tag v0.1.0](https://github.com/nexus-rpc/nexus-proto-annotations/tree/v0.1.0)
- [nexus-rpc organization repositories](https://github.com/orgs/nexus-rpc/repositories)
- [Pinned Temporal server go.mod](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod)
- [Existing exact-version source and metadata reconciliation](s3-temporal-narrow-compatibility-audit-20261026.md)

## Next action

Operator records an exact-version legal disposition or decides that this candidate will not be acquired. Until then, preserve Temporal as a read-only comparator and keep S3-G01 open.
