# S3 Temporal target profile proposal — 2026-10-27

## Status and scope

This is a planning proposal for read-only S3 audit and a future separately authorized comparison. GPT-PM's first target-profile review returned `MODIFY` with one MAJOR, `S3-PROFILE-M01`, because the earlier profile and plan did not make the accepted G07 topology normative. Codex reconciled both documents; post-fix GPT-PM request `b69437f8-fb54-4075-9fe1-3a08eb75e8c0` returned `ACCEPT`, zero BLOCKER/MAJOR, and closed `S3-PROFILE-M01` at documentation/design level only. The reply repeats the request ID and is in the inbound PM Bridge log; durable job metadata has no `replyId`/`correlated=true`, so formal job correlation and repository HEAD verification are not claimed. The G07 authorization mapping and file-backed configuration design remain normative and supersede less restrictive topology wording. A later G03 architecture review at declared HEAD `20499392f8d78b56214d0d109c9532d50531ac86` returned `MODIFY` (two MAJOR, one MINOR): add a pinned offline Go toolchain contract, full lifecycle compatibility map, and closed network/provider matrix. Changes 0404/0405 recorded the corrections. GPT-PM subsequently returned correlated `ACCEPT` for that corrected G03 design and the narrow cancellation-RPC design exception at exact reviewed HEAD `77b319367b575b9f4c0a193e91405df507c886e6` (request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245`, reply `14aedf85-c52b-5d64-b84b-40baf9a99455`). Both acceptances are design-only; implementation, artifact/runtime evidence, legal/acquisition and S3 acceptance remain open. This document does not approve implementation, acquire any package, resolve a license, provision an environment, or authorize a build, install, test, or execution.

## Proposed comparison target

| Dimension | Proposed value | Evidence and limitation |
|---|---|---|
| CPU/OS | Linux x86-64 inside one per-run S2 boundary | Matches the previously documented hypothetical S3 package profile; actual S2 acceptance remains open. |
| Python runtime | CPython 3.12 | Existing bounded license/profile screen used this version hypothetically; it is proposed here as one stable comparison target, not a claim about an installed environment. |
| Temporal server | `v1.32.1`, source commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` | Immutable audit pin. Pinned `go.mod` declares Go `1.26.8`; source identity does not establish a built artifact. |
| Python SDK | `1.34.0`, source commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` | Immutable audit pin. The wheel/source route remains undecided pending artifact provenance and legal gates. |
| Rust bridge | Gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320` | Recorded source identity; full build closure remains open. |
| Bridge features | Source-declared `tls-ring` default; do not select optional `fips` for this proposal | The actual platform-resolved feature graph has not been built or independently resolved. Required path features remain as declared by the pinned manifest. |
| Go build/toolchain | Official `go1.26.10.linux-amd64.tar.gz` distribution selected as the design pin for the server source's `go 1.26.8` baseline; expected official SHA-256 and offline/no-switch build contract are in `s3-g03-profile-compatibility-design-20261027.md` | Design selection only; archive not downloaded/hash-verified, module cache not resolved, server not built. |
| Extras | No optional Python integration extras in the minimal comparison profile | This is a profile proposal, not a dependency lock or proof of a minimal transitive closure. |
| Topology | One run-scoped Temporal server (`vst-engine`), one trusted SDK adapter (`vst-adapter`), one isolated untrusted candidate worker (`vst-worker`), and the trusted VST runner/Supervisor (`vst-runner`) use distinct principals. Every SDK connection, RPC and retry must pass through the mandatory deny-by-default gRPC gateway. The adapter cannot connect directly to the server; the candidate cannot reach the server or gateway or alter gateway configuration. Server audience and authorization follow the reviewed G07 mapping. Default and visibility stores use the reviewed file-backed per-run state profile. The VST Store/Supervisor remains the sole acceptance authority. | Normative design only: `s3-temporal-g07-authorization-mapping-20261027.md` and `s3-temporal-g07-exact-config-proposal-20261027.md` supersede the older, less-specific topology text. Principals, gateway, listeners, quotas, persistence behavior and no-bypass controls remain unimplemented or unverified. |
| Network and authority | No public egress; Temporal history is supporting state only; VST owns run state, stop fence and authoritative receipts | Configuration and runtime enforcement remain unverified until permitted S2 evidence exists. |
| Workload | One synthetic story, one worker, fixed budget and allowed paths | Matches S3 plan scope. No customer or live repository data. |

### Normative topology and authority

The G07 authorization mapping and exact-config proposal define the mandatory topology for this profile and supersede older, less restrictive wording in this file or S3 plan section 10. The design requires four distinct security principals: trusted `vst-runner` (VST Supervisor/Store/signer), `vst-engine` (Temporal server/state), `vst-adapter` (trusted SDK client/worker), and isolated untrusted `vst-worker` (candidate code). The adapter dispatches candidate work through the bounded runner interface and never executes candidate code in its own process.

Every SDK connection, RPC and retry must pass through the mandatory trusted deny-by-default gRPC gateway, including connection-time `GetSystemInfo`. The adapter cannot connect directly to the server; only the gateway can reach the server; candidate code cannot reach either endpoint or change gateway configuration. A per-run server audience, reviewed cluster-reader plus synthetic-namespace writer claims, closed RPC allowlist, and complete persisted VST request/STOP/RESUME/response identity mapping are required. Both default and visibility persistence use the reviewed file-backed database under bounded per-run `/tmp`, engine-owned and outside candidate access. The VST Store/Supervisor alone authorizes receipts and final acceptance.

These are design requirements, not existing implementation or runtime facts. Principals, gateway, route/listener isolation, claims, file ownership, quota enforcement, server restart/replay and no-bypass behavior remain unimplemented or `NOT_VERIFIED`/`NOT_RUN`. No reading of the older loopback-only or same-identity topology as an approved alternative is permitted. `S3-PROFILE-M01` and the corrected G03 design findings are closed at documentation/design level only. Exact implementation, artifact provenance, runtime interoperability and candidate acceptance remain open.

## Acceptance mapping and outstanding proof

The candidate-independent contract and scenario denominator are in `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md` sections 3 and 5 (AC-1–AC-15). Required observable behavior includes idempotent start/resume, typed non-approving status on uncertainty, STOP fencing against late writes/receipts, checkpoint recovery, bounded budget, path isolation, signed evidence authority, and egress refusal. The status matrix in `s3-static-candidate-comparison-20261027.md` records that the required shared-fixture runtime comparison remains `NOT_RUN` for all candidates.

The target profile still needs a platform-resolved dependency/license graph, server and SDK artifact provenance, build reproducibility, runtime qualification, exact server storage/listener/auth configuration, and a threat-flow review. S2 Phase 8 must be accepted before any sandbox-bound run. The 53 S4 policy selectors remain `NOT_RUN` and are not prerequisites to be waived as part of this S3 proposal; no such waiver is requested. `S3-PROFILE-M01` and the corrected G03 design findings are accepted at documentation/design level only; see the pinned toolchain, lifecycle compatibility and network/provider matrix in `s3-g03-profile-compatibility-design-20261027.md` and correlated adjudication in `s3-g03-g07-adjudication-0405-20261027.md`. Implementation, runtime, artifact and S3 acceptance gates remain open.

## Candidate role terminology

- `LOCAL_CONTRACT_BASELINE`: the existing hand-written VST adapter and its bounded synthetic evidence.
- `READ_ONLY_COMPARATOR`: BMad or Temporal under source-only inspection; no candidate execution is implied.
- `QUALIFIED_FALLBACK`: none at this time.
- `ACTIVE_ENGINE`: none selected or authorized by this proposal.

The proposal intentionally prevents the word “fallback” from implying production readiness or automatic routing. It does not name a final winner or a `TOP` candidate.

## Ownership and next steps

- Codex: reconcile this profile with the existing S3 plan, exact pinned manifests, and source implementation; keep artifact/runtime rows `NOT_RUN` until gates allow execution.
- GPT-PM: the corrected G03/G07 design was accepted at exact reviewed HEAD `77b319367b575b9f4c0a193e91405df507c886e6`; review future architecture changes and the exact delivery head, without carrying design approval over to implementation or runtime.
- Operator: resolve exact-version legal status and make the separate acquisition decision after technical prerequisites close.

## Primary in-repository evidence

- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md` sections 2, 3, 5, 10 and 12
- `docs/sdlc/evidence/s3-temporal-sdk-feature-profile-screen-20261027.md`
- `docs/sdlc/evidence/s3-g03-profile-compatibility-design-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-authorization-mapping-20261027.md`
- `docs/sdlc/evidence/s3-temporal-g07-exact-config-proposal-20261027.md`
- `docs/sdlc/evidence/s3-temporal-exact-version-license-metadata-20261027.md`
- `docs/sdlc/evidence/s3-static-candidate-comparison-20261027.md`
