# S3 Temporal Go dependency license detail follow-up — 2026-10-27

## Scope and provenance

Read-only inspection of the two unresolved source entries in `s3-temporal-server-go-license-source-followup-2026-10-25.tsv`, using their already pinned revisions. This records visible upstream source text and previously recorded license-file inventory results. It is not a legal opinion, SPDX determination, acquisition approval, or a complete dependency license inventory. No package/archive was acquired or copied into this repository.

## Observations

- `github.com/planetscale/vtprotobuf@v0.6.1-0.20240319094008-0393e58bdf10`, source revision `0393e58bdf10`: the pinned `LICENSE` contains a three-condition BSD-style grant, attribution/notice retention, non-endorsement and warranty/liability disclaimers. The text names PlanetScale, GoGo Authors and Go Authors. The inspected text differs from the canonical BSD-3-Clause template, so retain `BSD-3-Clause-like (SPDX unverified)`; this screen does not assign an SPDX identifier.
- `github.com/nexus-rpc/nexus-proto-annotations@v0.1.0`, source revision `e558d6edaf84e280dddfc87b5b8ce1662f66ac8b`: the previously recorded recursive tag-tree screen found no conventional root `LICENSE`, `LICENSE.md`, `LICENCE`, `COPYING`, `NOTICE`, or `COPYRIGHT` path, and pkg.go.dev metadata reported `NONE_DETECTED`. Read-only inspection of the pinned `nexusannotations/v1/options.proto` and generated `go/nexusannotations/v1/options.pb.go` showed no inline copyright/license header in the returned file text. This does not establish the governing terms or prove that no other source-level notice exists.

## Acceptance and ownership

- Technical source observations are narrowed for the two previously unresolved entries; legal status remains `NOT_VERIFIED` for the candidate dependency inventory, and the Nexus entry remains `UNKNOWN`.
- Codex owns bounded source-only evidence reconciliation. The operator owns legal/acquisition disposition. GPT-PM owns architecture adjudication; neither design acceptance nor this evidence is legal approval.
- No candidate acquisition, build, install, execution, project test, policy selector, or license-verification script was performed.

## Primary sources

- [Pinned vtprotobuf LICENSE](https://raw.githubusercontent.com/planetscale/vtprotobuf/0393e58bdf10/LICENSE)
- [Pinned Nexus annotations proto source](https://raw.githubusercontent.com/nexus-rpc/nexus-proto-annotations/e558d6edaf84e280dddfc87b5b8ce1662f66ac8b/nexusannotations/v1/options.proto)
- [Pinned generated Go source](https://raw.githubusercontent.com/nexus-rpc/nexus-proto-annotations/e558d6edaf84e280dddfc87b5b8ce1662f66ac8b/go/nexusannotations/v1/options.pb.go)
- [Previously recorded exact-tag recursive tree and pkg.go.dev metadata observations](s3-temporal-server-go-license-source-followup-2026-10-25.tsv)
