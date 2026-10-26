# S3 Temporal pinned-version compatibility audit — narrow result

## Scope

Read-only review of official upstream release/source records for the provisional S3 pins:

- Server: `temporalio/temporal` tag `v1.32.1`, commit `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- Python SDK: `temporalio/sdk-python` release `1.34.0`, commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.

No candidate source or artifact was acquired, built, installed, or executed.

## Evidence and result

The official SDK 1.34.0 release notes state that when a start request attaches to an already running workflow, the SDK uses the server-provided first execution run ID with Temporal Server 1.32.0 or later. The selected server pin is 1.32.1, which satisfies that stated minimum for this behavior. The same release notes describe other SDK 1.34.0 changes; they do not establish compatibility for the complete S3 pilot topology.

The exact SDK source pin's `pyproject.toml` declares version 1.34.0, Python `>=3.10`, MIT, and a Rust extension build through Maturin (the existing S3 audit covers those details). The exact server pin's `go.mod` requires `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`; that component's exact-version license/notice question remains unresolved in the existing S3 evidence.

Primary sources:

- SDK release notes: <https://github.com/temporalio/sdk-python/releases/tag/1.34.0>
- SDK source at the immutable pin: <https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/pyproject.toml>
- Server release at the immutable pin: <https://github.com/temporalio/temporal/releases/tag/v1.32.1>
- Server dependency manifest at the immutable pin: <https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod>

## Acceptance disposition

This closes only the narrow compatibility fact for the SDK's documented first-execution-run-ID behavior. General server/SDK compatibility, the pilot's exact replay/start/status/STOP/resume path, listener and persistence topology, source-to-artifact provenance, dependency closure, and runtime behavior remain `NOT_VERIFIED` or `NOT_RUN`. S3-G01 license/notice and S3-G02 dependency/provenance remain open. Acquisition and execution remain `NOT_APPROVED`; S2 Phase 8 is still not approved. No final candidate or “TOP” decision follows from this audit.

Owner: Codex records pinned-source evidence; GPT-PM adjudicates the architecture contract; operator retains legal/acquisition decisions. Next: continue read-only primary-source audit and close build/profile provenance without acquiring candidate material; obtain authorization separately only after all audit gates are closed.
