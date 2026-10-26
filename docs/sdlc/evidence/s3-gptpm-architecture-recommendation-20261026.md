# S3 GPT-PM architecture recommendation — 2026-10-26

## Correlation and scope

- PM Bridge request: `b10f9f72-c0d1-4ac1-b020-38cb3af40345`.
- Correlated reply: `07970c00-b864-55eb-aa39-fc028d1cabd6`.
- PM Bridge job: `b322746e-9458-4b56-b142-b4c6f4034cbe`.
- Reviewed attachment: `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md`.
- Verdict: **RECOMMEND TEMPORAL — READ-ONLY AUDIT CONTINUATION ONLY**.

The recommendation selects Temporal server plus its Python SDK as the durable-engine comparator for continued read-only audit, retaining BMad Loop as a distinct coding-agent-loop comparator. It is not a final candidate win, “TOP” designation, acquisition authorization, execution permission, S2 acceptance, or S3 completion. The review notes that detailed external audit artifacts were not attached and their contents/provenance were therefore not independently verified by GPT-PM.

## Pins recommended for audit

| Component | Version | Immutable source identity | Use |
|---|---|---|---|
| Temporal server | `v1.32.1` | `af08a5e5f2dd40f545f2afac7780daaa6987001e` | Read-only audit comparator |
| Temporal Python SDK | `1.34.0` | `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` | Read-only audit comparator |
| SDK Rust Core gitlink | — | `e163abd6dc19040064986a63c8b8cf4756ffd320` | Record as transitive source identity |
| BMad Loop | `v0.13.2` | `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60` | Separate comparator, not the durable engine |

Do not replace these audit pins with a branch, moving tag, or unpinned package without a recorded decision.

## Findings and unresolved gates

- Temporal has the architectural shape needed for the S3 durable-engine comparison, but VST replay/recovery behavior and server/SDK compatibility remain unproven.
- Third-party license/notice closure and selected build/runtime dependency closure remain incomplete, including the exact-version `github.com/nexus-rpc/nexus-proto-annotations@v0.1.0` license question.
- Selected artifacts do not yet have complete source-to-wheel provenance.
- A VST-specific server/worker/listener/store topology and threat model remain to be prepared.
- S2 is not accepted; full sandbox/process boundaries are incomplete or `NOT_RUN`.
- No candidate was acquired or executed by this GPT-PM review. Candidate runtime remains `NOT_RUN`.
- The recorded recommendation does not claim that Temporal outperforms BMad in the fixture; no common runtime result exists.

## Additional pinned-source audit by Codex

Read-only browsing of the exact official GitHub revision pages confirmed the following source facts:

- The Temporal server pin's [`go.mod`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/go.mod) declares Go `1.26.8` and includes `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`; this confirms the specific version whose license evidence remains unresolved. The pinned [`LICENSE`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/LICENSE) declares MIT for the server repository itself. The pinned [`Makefile`](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/Makefile) builds `./cmd/server` with `go build`; the runtime/build profile and full feature-resolved dependency set are not established by this source inspection.
- The pinned SDK [`pyproject.toml`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/pyproject.toml) identifies version `1.34.0`, MIT, Python `>=3.10`, and classifiers through Python 3.14. It declares `nexus-rpc==1.4.0`, protobuf, conditional `python-dateutil`, `types-protobuf`, and `typing-extensions`. The Python extension is built with Maturin from `temporalio/bridge/Cargo.toml`; therefore a selected wheel must be tied to the pinned source, Rust SDK-core gitlink, and resolved Cargo input set before provenance can be accepted.
- The pinned SDK [`.gitmodules`](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/.gitmodules) identifies the `sdk-core` submodule URL as `https://github.com/temporalio/sdk-rust.git`. This inspection verified the declared submodule path and URL; it did not independently verify the gitlink SHA reported in the PM recommendation.
- The pinned server `go.mod` requires `github.com/nexus-rpc/nexus-proto-annotations v0.1.0`. The official [`nexus-rpc/nexus-proto-annotations` v0.1.0 tree](https://github.com/nexus-rpc/nexus-proto-annotations/tree/v0.1.0) lists no root `LICENSE` file, and the exact tag's [`LICENSE` URL returns 404](https://github.com/nexus-rpc/nexus-proto-annotations/blob/v0.1.0/LICENSE). GitHub's organization page displays MIT metadata for this repository, but the tag-specific source archive lacks the license text. This is a provenance/notice gap, not a conclusion that the dependency is unlicensed; keep legal closure unresolved pending exact-version authoritative license/notice evidence.

This bounded source review strengthens identity/build-profile understanding but is not a complete SBOM, legal notice closure, signed provenance chain, compatibility proof, or runtime result. The recommended pins remain audit pins only.

## Owners and next action

- Accountable task owner: operator under the delegated sprint request.
- Read-only source audit and acquisition-package preparation: Codex.
- Product/architecture recommendation recorded here: GPT-PM.
- Next: continue read-only primary-source audit against the pinned revisions and prepare the license/build/provenance/topology dossier. Acquisition and execution remain behind the corresponding policy, legal, S2, and explicit gate requirements.
