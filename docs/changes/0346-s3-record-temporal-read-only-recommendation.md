# Change 0346 — Record the S3 Temporal read-only audit recommendation

## Summary

- Recorded GPT-PM's correlated architecture recommendation and exact audit pins for Temporal server, Python SDK and Rust SDK-core gitlink.
- Kept BMad Loop as a separate coding-agent-loop comparator.
- Added an independently browsed, pinned-source addendum for Temporal server `go.mod`, repository license, server build entry point, SDK package/build metadata, and SDK submodule declaration.
- Updated the S3 plan and current state without acquiring or executing an external candidate.

## Why

S3 requires an immutable candidate identity and a comparative architecture/security audit. GPT-PM returned a bounded recommendation for which durable-engine candidate to audit next, while explicitly withholding acquisition/execution approval and S3 completion. Recording the exact correlation and limits prevents the recommendation from being promoted to a broader gate.

## Evidence and limits

- Request `b10f9f72-c0d1-4ac1-b020-38cb3af40345`; correlated reply `07970c00-b864-55eb-aa39-fc028d1cabd6`; job `b322746e-9458-4b56-b142-b4c6f4034cbe`.
- Official pinned-source links and observed facts are in `docs/sdlc/evidence/s3-gptpm-architecture-recommendation-20261026.md`.
- Server pin `af08a5e5f2dd40f545f2afac7780daaa6987001e`; SDK pin `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`; PM-reported Rust Core gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320` (not independently verified in the browser inspection); BMad pin `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`.
- The server declares MIT, Go 1.26.8, and a broad module graph that includes `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`; exact-version dependency license closure remains incomplete.
- The SDK declares MIT, Python `>=3.10`, and a Maturin/Rust extension with an `sdk-core` submodule. Wheel-to-source provenance, selected build profile, compatibility and runtime evidence are not established.
- No candidate was acquired, installed, built, or run. S2/S3 gates remain open; no TOP is assigned.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Read-only audit coordination and documentation: Codex.
- Architecture recommendation: GPT-PM.
