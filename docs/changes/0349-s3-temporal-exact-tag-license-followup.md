# Change 0349 — Record exact-tag Temporal dependency license follow-up

## Summary

- Continued the read-only S3 audit of the pinned Temporal server dependency `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`.
- Recorded that the exact public tag tree has no root `LICENSE` path and the direct tag-specific `LICENSE` URL returns 404, while GitHub organization/repository metadata displays MIT.
- Preserved this as an exact-version notice/provenance gap rather than concluding that the dependency is unlicensed.
- Updated the S3 evidence and VST-028 backlog row; no candidate source was cloned, installed, built, or run.

## Evidence

- Temporal server pinned `go.mod` lists `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`.
- Exact tagged tree: `https://github.com/nexus-rpc/nexus-proto-annotations/tree/v0.1.0`.
- Exact tag LICENSE path: `https://github.com/nexus-rpc/nexus-proto-annotations/blob/v0.1.0/LICENSE` (404 at review time).
- Organization metadata page: `https://github.com/nexus-rpc` displays MIT beside the repository but does not supply exact-tag license text.
- The resulting conflict and acceptance boundary are described in `docs/sdlc/evidence/s3-gptpm-architecture-recommendation-20261026.md`.

## Decision and limits

This is not legal advice or legal approval. Keep exact-version notice closure unresolved until authoritative license/notice text or maintainer confirmation tied to the exact published module version is available. Other Temporal dependency/build profile, SDK source-to-wheel provenance, server/SDK compatibility, S2 gate and runtime acceptance remain open.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Read-only source audit and record: Codex.
- Architecture recommendation: GPT-PM.
