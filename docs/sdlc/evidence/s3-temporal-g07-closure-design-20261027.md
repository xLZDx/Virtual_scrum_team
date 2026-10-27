# S3 Temporal G07 closure design proposal — 2026-10-27

## Status

**PROPOSED FOR GPT-PM ADJUDICATION; NOT APPROVED; NOT IMPLEMENTED.** This document addresses GPT-PM findings G07-M01 and G07-M02. It does not authorize provisioning, acquisition, build, installation, runtime execution, tests, a policy waiver, S2 acceptance, S3 acceptance, or candidate promotion. The provisional Temporal comparator and the no-winner/no-TOP state remain unchanged.

## Target and explicit exclusions

- Temporal Server `v1.32.1`, source pin `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- Python SDK `1.34.0`, source pin `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.
- Linux x86-64 / CPython 3.12 planning target; source-declared Go 1.26.8 and Rust bridge pin remain as previously recorded.
- Continue read-only source evaluation only. Do not resolve S3-G01 rights or S3-G04 acquisition; those remain operator-owned.
- Explicitly exclude `development-sqlite.yaml` (both stores use `mode: memory`) from any durable restart/replay qualification.
- Do not use `--allow-no-auth` or an empty/no-op authorizer as a candidate-comparison profile.

## Proposed one-sandbox process and authority boundary

Retain one per-run S2 boundary only if it can enforce the following four distinct principals. These names describe required security roles, not existing accounts; only `vst-worker` and `vst-runner` were observed in the 2026-10-27 root inventory. No new account or service was provisioned by this design task.

| Principal | Responsibility | Required access | Explicit denial |
|---|---|---|---|
| `vst-runner` | Existing trusted VST Supervisor, Store, signer, policy and final acceptance authority | Existing Store and signer interfaces; launches/authenticates the adapter; receives sanitized outcome | No need to execute candidate code or expose Store/signer credentials to Temporal |
| `vst-engine` | Temporal server process and engine persistence | Pinned server config, per-run engine-state directory, internal service IPC, server TLS keys | No candidate worktree writes; no candidate credentials; no broad access to VST Store or signer |
| `vst-adapter` | Trusted Temporal SDK client/worker and VST integration shim | Server endpoint with one namespace-scoped identity; bounded adapter IPC to `vst-runner`; launches candidate through the existing bounded runner interface | No direct Store mutation/signing; no unrestricted VST administrative API; no promotion authority |
| `vst-worker` | Candidate-controlled code | One synthetic story and its allowlisted worktree effects only | No Temporal tokens/certificates, Store/signer IPC, engine-state/config files, server/admin ports, or process inspection of trusted principals |

The adapter must not execute candidate code in its own process. It dispatches candidate work through the restricted runner boundary, passes only declared input/output, and validates the returned typed response against the run, attempt, epoch/fence and sandbox identity. The trusted Supervisor remains the sole authority for durable receipts, final VST verdicts and gate decisions. Temporal history is supporting state only.

This separation must be enforced by OS identity, filesystem permissions, process-inspection denial and per-principal endpoint rules inside the S2 boundary. Sharing a network namespace or loopback interface does not count as authentication. If the existing S2 controls cannot express these boundaries, G07 stays open; do not replace the enforcement with a code convention.

## Proposed persistence profile

Use the pinned server's `config/development-sqlite-file.yaml` as the source template for a future single-run synthetic qualification, not its in-memory sibling. The exact pinned file sets both stores to SQLite with `setup: true`, `journal_mode: wal`, `synchronous: 2`, one connection and no `mode: memory`. The pinned SQLite plugin builds a `file:<databaseName>` DSN and performs schema setup when file mode uses `setup: true`.

For the VST-specific profile, replace the template placeholder `databaseName: "default"` with one stable absolute path under the approved per-run S2 ext4 state mount, e.g. `/srv/vst-engine/state/<run-id>/temporal.sqlite`; both default and visibility stores use the same file as in the pinned template. The path is stable across Temporal server process restart within that one run. Its parent directory is engine-owned mode `0700`, database and SQLite WAL/SHM files are engine-owned mode `0600`, and candidate identity has no path traversal/read/write access. The state mount and files are retained for the run/recovery evidence; no automatic deletion is authorized.

The initial synthetic profile proposes a 256 MiB maximum engine-state allocation within the previously recorded 1 GiB S2 `/tmp` cap; this cap and mount binding must be confirmed against the actual S2 quota mechanism before any runtime work. If the quota cannot be enforced or the database hits it, the outcome is non-approving (`INCONCLUSIVE` or `BLOCKED`), never a silent empty database/restart. Corrupt, missing, inaccessible or inconsistent persistence fails closed. VST reconciles its own attempt/epoch/fence and signed receipt chain independently of Temporal replay. Restart/replay remains `NOT_RUN` until separately permitted and tested.

The example path is a proposed contract value, not an observed or provisioned path. The pinned upstream file uses a relative placeholder and is not itself an approved S2 configuration.

## Authentication, authorization and listeners

- Configure `global.authorization.authorizer: default` and `claimMapper: default`; prohibit empty authorizer and no-auth startup. The pinned default authorizer denies calls without claims except health checks and maps system/namespace roles using method metadata. The exact claim role mapping and client certificate/token delivery must be frozen before qualification.
- Use the pinned server's internal-frontend path for trusted internal services as recommended in `common/config/config.go` when using an authorizer/claim mapper; configure internode TLS. The adapter connects to the public frontend with an audience-bound, namespace-scoped least-privilege credential. Candidate receives no token or key material.
- Candidate activity code runs in the separate `vst-worker` process, never inside the SDK process that holds Temporal credentials. The SDK process and any credentials/config files are unreadable to `vst-worker`; process inspection and ptrace between principals are denied.
- Enumerate frontend gRPC/HTTP, internal-frontend, history, matching, worker, membership, metrics and pprof endpoints in the generated run profile. Disable unnecessary HTTP/admin/diagnostic listeners where the pinned configuration supports it; otherwise bind to loopback and deny candidate-UID access with an enforced per-principal rule. Keep all external egress denied except an explicitly documented local control path.
- A loopback binding alone does not establish authorization. Every reachable RPC path must require authenticated claims and be mapped to the minimum API methods/actions needed by the adapter. Candidate identity receives no engine identity and cannot invoke privileged Temporal APIs directly.
- The exact JWT/JWKS or certificate files, claim names/regex, audience, tokens and service TLS settings remain to be pinned in a run-specific config and threat-flow record. Use only local, integrity-checked key material; no external key fetch during a run.

## Fencing and failure contract

1. Trusted Supervisor advances the VST epoch/fence durably before requesting cancellation or cleanup.
2. The adapter asks Temporal to cancel/stop the run and the bounded runner to stop candidate work. Physical child cleanup is recorded separately; a timeout or unverified child state cannot be reported as stopped.
3. Every late Temporal/activity completion is checked against the current VST run, attempt and epoch before it can influence an authoritative receipt. Stale completions are rejected.
4. Recovery reconciles the file-backed Temporal history with VST Store and the existing receipt/idempotency chain before a new attempt. History alone cannot authorize resume.
5. Lost server/worker, failed or partial cancellation, inaccessible/corrupt persistence, resource exhaustion, missing credential, stale history, or mismatched epoch produces a typed non-approving result. No automatic engine fallback or final approval is allowed.

## Required threat-flow evidence before G07 closure

| Flow | Required proof | Current state |
|---|---|---|
| `vst-runner` → authenticated adapter → Temporal frontend | Authenticated identity, scope, audience, exact endpoint and run/attempt binding | `NOT_VERIFIED` |
| Temporal server → adapter/system workers | Internal endpoint and internode TLS path, not reachable by candidate principal | `NOT_VERIFIED` |
| Adapter → candidate subprocess | Distinct UID, bounded executable/input/output and no credential inheritance | `NOT_VERIFIED` |
| Candidate → VST Store/signer/engine DB/admin APIs | OS/filesystem/IPC/network denials, including same-host loopback | `NOT_VERIFIED` |
| STOP → VST fence → cancellation/cleanup → late-result rejection | Fencing precedes result acceptance; child cleanup is independently observed | `NOT_RUN` |
| Server restart → Temporal history → VST reconciliation → resumed attempt | File survives server process restart; replay is deterministic/idempotent; VST reconciliation controls resume | `NOT_RUN` |
| Resource exhaustion and recovery | Enforced disk/DB, memory, process, time and output bounds; every failure stays non-approving | `NOT_VERIFIED` |

## Acceptance mapping and review boundary

The design addresses GPT-PM G07-M01/G07-M02 and S3 plan AC-3, AC-5, AC-7, AC-8, AC-9, AC-10, AC-11 and AC-13. It also supports G03's exact runtime profile but does not close dependency/provenance or general compatibility. The following remain separate: S2 Phase 8 is NOT APPROVED; shared-fixture Temporal comparison and restart/replay are `NOT_RUN`; S3-G01 exact-version rights remain `NOT_VERIFIED`; acquisition/execution are not authorized; S4's 53 policy selectors remain `NOT_RUN` and no waiver is supplied; S5 remains gated on S2/S4 closure plus an operator-provided or specifically authorized AEVE source.

GPT-PM's correlated `MODIFY` adjudication on request `7c8a0d32-75c7-4f89-a43a-20243c8383bc` (reply `d878985f-e205-5fd8-b70e-0a80254ade69`) accepted the VST contract design direction but found these two design MAJORs. This proposal is the Codex-owned corrective design for a subsequent full GPT-PM review; it does not close those findings by itself.

## Ownership and next actions

1. **Codex:** send this complete design, the S3 plan, pinned source evidence and relevant adapter/control-plane source to GPT-PM for adversarial adjudication; preserve any remaining findings.
2. **GPT-PM:** accept or modify the design against the exact attached source; closure requires agreement on the precise persistence, identity, authorization, endpoint and threat-flow contract.
3. **Codex:** after design acceptance, finish G03 artifact/compatibility and G07 config/provenance dossier without acquiring or executing Temporal.
4. **Operator:** retain legal disposition, acquisition, any policy waiver, sandbox boundary changes, and execution authorization. No operator decision is requested in this document.
5. **Test roles:** only after S2/S4 acceptance and approved S3 runtime scope, author/execute the mapped permitted scenarios; all currently prohibited scenarios retain `NOT_RUN`.

## Primary pinned sources

- [Pinned file-backed SQLite config](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-sqlite-file.yaml)
- [Pinned in-memory SQLite config](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-sqlite.yaml)
- [Pinned SQLite plugin DSN/setup](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/persistence/sql/sqlplugin/sqlite/plugin.go)
- [Pinned authorization factory](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/authorizer.go)
- [Pinned default authorizer](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_authorizer.go)
- [Pinned JWT claim mapper](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_jwt_claim_mapper.go)
- [Pinned server config/auth/TLS model](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/config/config.go)
