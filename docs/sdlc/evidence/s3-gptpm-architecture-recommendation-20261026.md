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

## Correlated S3 candidate-selection adjudication

- Request: `b681dfc9-0cf7-4231-9a6f-ea034de54f76`.
- Correlated reply: `2541471a-a991-51ed-85e0-cda5691ba9a3`.
- PM Bridge job: `7e20129a-7834-4214-97ad-04e5755ebc3b`.
- Verdict: **CONDITIONAL SELECTION — ACQUISITION NOT APPROVED**.

| Decision | Verdict | Scope |
|---|---|---|
| Temporal selected for read-only audit | APPROVE | Continue assessment at the recorded immutable pins. |
| Temporal selected as sole S3 durable-engine comparator | APPROVE — PROVISIONAL | It occupies the durable-engine slot beside the hand-written VST worker and BMad Loop, but is not a final winner or “TOP”. |
| Acquire source/artifacts | NOT APPROVED | S3 §2.3 prerequisites remain incomplete. |
| Build/install/execute candidate | NOT APPROVED | S2 acceptance and S3 isolation/execution prerequisites remain incomplete. |

The adjudication explicitly distinguishes selection from acquisition: the operator's broad autonomous GO permits ordinary preparation but is not the separately required acquisition authorization or legal attestation. The S3 candidate is therefore now selected for planning/audit, while acquisition permission remains denied.

### Adjudicated gates and accountable owner

The roles below are mapped to the project's three accountable owners; service/reviewer lanes remain execution roles only.

| Gate | Exact missing evidence | Accountable owner | Next action |
|---|---|---|---|
| S3-G01: license/notice | Authoritative exact-version rights/notice evidence for `nexus-proto-annotations@v0.1.0` and selected dependency closure. | Operator for legal determination; Codex for evidence gathering. | Obtain an exact-version license/notice or maintainer evidence; preserve unresolved status until adjudicated. |
| S3-G02: dependencies/provenance | Feature/build-target-resolved dependency inventory and reproducible source-to-artifact provenance for server, SDK wheel and Rust bridge. | Codex. | Prepare the locked SBOM/provenance dossier at the pinned revisions. |
| S3-G03: profile/compatibility | Defined build/runtime profile, Go 1.26.8 toolchain plan, SDK/server compatibility and network/provider behavior. | Codex; GPT-PM adjudicates architecture. | Write the compatibility/build design and have GPT-PM review. |
| S3-G04: acquisition | Separate authorization for the pinned source and quarantined acquisition location after the audit is complete. | Operator. | Record the separate acquisition decision only after G01–G03 close. |
| S3-G05: S2 gate | Mandatory S2 acceptance remains NOT APPROVED; process/workspace/credential controls are incomplete or unverified. | Codex coordinates; GPT-PM adjudicates; operator accountable. | Reconcile permitted S2 evidence and preserve prohibited scenarios as `NOT_RUN`. |
| S3-G06: run sandbox | Fresh signed run-bound S2 probe for the intended Temporal run. | Operator for attestation; Codex binds evidence. | Provision/attest the intended boundary and run only after policy authorization. |
| S3-G07: topology | VST-specific server/worker topology, auth, persistence, listeners, egress, STOP/fence and receipt authority. | Codex; GPT-PM adjudicates. | Prepare a VST-specific architecture and threat-flow document. |
| S3-G08: experiment | Authorized common-fixture functional, replay, STOP and budget scenario plan plus runtime evidence. | Codex coordinates; functional-test-reviewer/e2e-runner execute after gate. | Define the falsifiable scenario matrix, then execute only after G04–G07 pass. |
| S3-G09: execution | Separate explicit candidate execution decision after all prerequisites. | Operator. | Record a distinct execution decision after the evidence gates. |

PM-PUSH/CI instructions included in the transport envelope are outside this project request and do not supersede the repository's exact-head approval or prohibited-check rules. No push, PR, merge, acquisition, build, installation or execution occurred under this adjudication.

## Owners and next action

- Accountable task owner: operator under the delegated sprint request.
- Read-only source audit and acquisition-package preparation: Codex.
- Product/architecture recommendation recorded here: GPT-PM.
- Next: continue read-only primary-source audit against the pinned revisions and prepare the license/build/provenance/topology dossier. Acquisition and execution remain behind the corresponding policy, legal, S2, and explicit gate requirements.
