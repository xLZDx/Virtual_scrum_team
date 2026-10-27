# S3 Temporal target profile proposal — 2026-10-27

## Status and scope

This is a planning proposal for read-only S3 audit and a future authorized comparison. It does not approve Temporal architecture, acquire any package, resolve a license, provision an environment, or authorize a build, install, test, or execution. GPT-PM adjudication is required before treating it as the accepted S3 target profile.

## Proposed comparison target

| Dimension | Proposed value | Evidence and limitation |
|---|---|---|
| CPU/OS | Linux x86-64 inside one per-run S2 boundary | Matches the previously documented hypothetical S3 package profile; actual S2 acceptance remains open. |
| Python runtime | CPython 3.12 | Existing bounded license/profile screen used this version hypothetically; it is proposed here as one stable comparison target, not a claim about an installed environment. |
| Temporal server | `v1.32.1`, source commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` | Immutable audit pin. Pinned `go.mod` declares Go `1.26.8`; source identity does not establish a built artifact. |
| Python SDK | `1.34.0`, source commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` | Immutable audit pin. The wheel/source route remains undecided pending artifact provenance and legal gates. |
| Rust bridge | Gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320` | Recorded source identity; full build closure remains open. |
| Bridge features | Source-declared `tls-ring` default; do not select optional `fips` for this proposal | The actual platform-resolved feature graph has not been built or independently resolved. Required path features remain as declared by the pinned manifest. |
| Extras | No optional Python integration extras in the minimal comparison profile | This is a profile proposal, not a dependency lock or proof of a minimal transitive closure. |
| Topology | One server and one worker inside the same per-run sandbox, loopback-only endpoint; VST Store, signer and acceptance authority remain outside candidate access | Aligns with the already proposed S3 topology in plan section 10. Startup, listener, auth and persistence settings still need exact implementation review. |
| Network and authority | No public egress; Temporal history is supporting state only; VST owns run state, stop fence and authoritative receipts | Configuration and runtime enforcement remain unverified until permitted S2 evidence exists. |
| Workload | One synthetic story, one worker, fixed budget and allowed paths | Matches S3 plan scope. No customer or live repository data. |

## Acceptance mapping and outstanding proof

The candidate-independent contract and scenario denominator are in `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md` sections 3 and 5 (AC-1–AC-15). Required observable behavior includes idempotent start/resume, typed non-approving status on uncertainty, STOP fencing against late writes/receipts, checkpoint recovery, bounded budget, path isolation, signed evidence authority, and egress refusal. The status matrix in `s3-static-candidate-comparison-20261027.md` records that the required shared-fixture runtime comparison remains `NOT_RUN` for all candidates.

The target profile still needs a platform-resolved dependency/license graph, server and SDK artifact provenance, source/build reproducibility, exact server storage/listener/auth configuration, and a threat-flow review. S2 Phase 8 must be accepted before any sandbox-bound run. The 53 S4 policy selectors remain `NOT_RUN` and are not prerequisites to be waived as part of this S3 proposal; no such waiver is requested.

## Candidate role terminology

- `LOCAL_CONTRACT_BASELINE`: the existing hand-written VST adapter and its bounded synthetic evidence.
- `READ_ONLY_COMPARATOR`: BMad or Temporal under source-only inspection; no candidate execution is implied.
- `QUALIFIED_FALLBACK`: none at this time.
- `ACTIVE_ENGINE`: none selected or authorized by this proposal.

The proposal intentionally prevents the word “fallback” from implying production readiness or automatic routing. It does not name a final winner or a `TOP` candidate.

## Ownership and next steps

- Codex: reconcile this profile with the existing S3 plan, exact pinned manifests, and source implementation; keep artifact/runtime rows `NOT_RUN` until gates allow execution.
- GPT-PM: adversarially adjudicate the architecture and this profile against the full plan and current comparison evidence.
- Operator: resolve exact-version legal status and make the separate acquisition decision after technical prerequisites close.

## Primary in-repository evidence

- `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md` sections 2, 3, 5, 10 and 12
- `docs/sdlc/evidence/s3-temporal-sdk-feature-profile-screen-20261027.md`
- `docs/sdlc/evidence/s3-temporal-exact-version-license-metadata-20261027.md`
- `docs/sdlc/evidence/s3-static-candidate-comparison-20261027.md`
