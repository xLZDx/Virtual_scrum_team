# S3 Temporal G07 exact configuration proposal — 2026-10-27

## Status

**GPT-PM accepted the corrected G07 design only.** Persistence design was accepted at design level. The 9cc85 focused review accepted the JWT audience design, but found the bootstrap RPC missing and the persisted VST binding incomplete. Exact pinned-source review confirms `GetSystemInfo` is called during Core connection and requires cluster-read authorization; Python's bridge does not expose the relevant Core skip flag or transport callback. The corrected mapping proposes a mandatory trusted network gateway plus complete identity binding. Correlated review request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` / reply `c9313616-dae6-5e23-9d94-21297ae17ec5` accepted the design and closed `G07-CFG-M01` at design level. This proposal remains unimplemented and not runtime-qualified; it does not authorize sandbox reconfiguration, acquisition, build/install, execution, test runs, S2/S3 acceptance, or delivery.

## Pinned server configuration delta

Start from Temporal Server `v1.32.1` source `af08a5e5f2dd40f545f2afac7780daaa6987001e` and use `config/development-sqlite-file.yaml` as the base. Do not use `config/development-sqlite.yaml` or the JWT example's in-memory SQLite stores for restart/replay qualification.

For both `sqlite-default` and `sqlite-visibility`, keep the pinned file profile's single logical database name, one connection, `setup: true`, `journal_mode: wal`, and `synchronous: 2`; omit the `mode` attribute. Set both `databaseName` values to the same absolute run-specific file, `/tmp/vst-temporal/state/<run-id>/temporal.sqlite`. The pinned plugin translates `databaseName` to a `file:<databaseName>` SQLite DSN and runs schema setup in file mode. The run-specific parent directory is created before starting the server, owned by `vst-engine`, mode `0700`; the database and `-wal`/`-shm` sidecars remain engine-owned, mode `0600`.

The complete persistence tree must remain on the S2 per-run `/tmp` tmpfs, with the recorded maximum of 1 GiB bound to the actual mount. The 1 GiB limit was observed in the earlier signed S2 E5 run, not in a new run; a fresh run-bound probe must confirm it before use. This replaces the prior proposed 256 MiB limit on `/srv`, which was not tied to a quota mechanism. The selected state survives a Temporal server process restart inside the same live S2 run. It is not claimed to survive termination/recreation of the entire WSL/S2 boundary. If that boundary is lost, or state is missing, corrupt, inaccessible or oversized, the result is non-approving and no empty-state restart is allowed. Evidence must capture DB/WAL/SHM identity and VST reconciliation without exposing secrets.

Illustrative configuration values (the `<run-id>` substitution is supplied by the trusted run launcher; this block is not a production-ready config file):

```yaml
persistence:
  defaultStore: sqlite-default
  visibilityStore: sqlite-visibility
  datastores:
    sqlite-default:
      sql:
        pluginName: sqlite
        databaseName: /tmp/vst-temporal/state/<run-id>/temporal.sqlite
        connectAttributes:
          setup: "true"
          journal_mode: wal
          synchronous: "2"
        maxConns: 1
        maxIdleConns: 1
    sqlite-visibility:
      sql:
        pluginName: sqlite
        databaseName: /tmp/vst-temporal/state/<run-id>/temporal.sqlite
        connectAttributes:
          setup: "true"
          journal_mode: wal
          synchronous: "2"
        maxConns: 1
        maxIdleConns: 1
```

Other required connection fields from the pinned schema remain supplied by the complete base config. The snippet is not a verified Temporal config and no config-validation command has been run.

## Principals, namespaces and credentials

The four principal roles accepted by GPT-PM remain required: `vst-runner` (trusted Supervisor/Store/signer), `vst-engine` (Temporal server and state), `vst-adapter` (trusted SDK adapter/broker), and `vst-worker` (untrusted candidate). Current static inventory confirms only `vst-runner` and `vst-worker` accounts; it does not prove the required other identities or separation. Do not add users or capabilities as part of this read-only audit.

Use one synthetic namespace, `vst-synthetic`, for an authorized future single-story run. The pinned `default` authorizer and JWT claim mapper use a namespace `permissions` claim. GPT-PM's exact-config review identified that the proposed run-specific token audience was not enough by itself: its enforcement component and the run/workflow/API mapping had not been stated. The corrective `s3-temporal-g07-authorization-mapping-20261027.md` now binds a per-run server's non-empty `global.authorization.audience`, default mapper, exact role claim, source-derived RPC allowlist, and workflow identity. GPT-PM accepted this mapping at design level only in correlated request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` / reply `c9313616-dae6-5e23-9d94-21297ae17ec5`; this is not implementation or runtime proof. The claim mapper supports a local `file://` JWKS source, so the server can verify locally without public egress. The run launcher (`vst-runner`) creates/holds private signing material; the public verification keys and server TLS material are readable only by `vst-engine`; the short-lived JWT is delivered only to the trusted adapter boundary through a protected descriptor or equivalent IPC. It is absent from environment variables, files, pipes or process arguments visible to the candidate. The candidate gets no Temporal credential.

The pinned Python SDK/Core performs `GetSystemInfo` during connection establishment. Server metadata classifies it as cluster-scoped/read-only, and the default authorizer requires the system-reader claim for cluster scope. The Python bridge does not expose Core's `skip_get_system_info` flag or its lower-level transport override. The future token therefore includes only `temporal-system:read` plus `vst-synthetic:write`; the server-level system reader also permits other cluster-read APIs, so this is not by itself an acceptable method boundary.

The trusted Python adapter must use a dedicated gRPC gateway as the mandatory path for every SDK connection and RPC/retry; it cannot connect directly to the server. The gateway parses and allowlists every RPC at the shared network edge, including bootstrap. It permits `GetSystemInfo` and only the listed workflow/worker operations; it denies other cluster reads such as `ListNamespaces`, `GetSearchAttributes` and `GetClusterInfo`, all admin methods, and unknown methods. It returns the expected pinned protobuf response shape and required capability fields, rejects incompatible or permission errors without broadening the claim/list, and cannot be bypassed because the server accepts traffic only from the gateway while the candidate has no route to the gateway or server and cannot reconfigure the gateway. The gateway is a proposed trusted component, not current code or proof. GPT-PM accepted this architecture at design level only; implementation, network reachability, and compatibility remain unverified. The VST identity mapping and response checks are in `s3-temporal-g07-authorization-mapping-20261027.md`.

## Network and endpoint inventory

The candidate process receives no network interface/route to the trusted engine network namespace; it uses only bounded stdin/stdout/descriptor IPC from the adapter/runner. The Temporal server and trusted adapter may share an internal per-run namespace, with client/server TLS and authenticated frontend access. The candidate namespace has loopback only and no route to the host, engine or public network. This must be enforced and proven by the S2 launch policy; it is not inferred from WSL loopback binds or the current host firewall configuration.

| Listener/service | Pinned development profile | Proposed exposure | Candidate access |
|---|---|---|---|
| Frontend gRPC | 7233, localhost bind | Trusted engine namespace; TLS + client authentication and JWT authorization | Deny; no route and no credential |
| Frontend HTTP | 7243 | Set `httpPort: 0` (pinned config comments say 0 disables frontend HTTP) | Deny |
| Internal frontend | 7236 when enabled by the authenticated profile | Trusted service namespace only; internode TLS | Deny |
| History / matching / worker RPC | 7234 / 7235 / 7239; membership 6934 / 6935 / 6939 | Trusted internal namespace; authenticated internode config | Deny |
| Frontend membership | 6933 | Trusted internal namespace only | Deny |
| Metrics | 127.0.0.1:8000 in the development profiles | No host exposure; trusted-namespace-only or disabled by a verified supported setting | Deny |
| pprof | Port 7936 in the development profiles | No host exposure; trusted-namespace-only or disabled by a verified supported setting | Deny |

The exact effective listener list must be generated from the final merged config, including any defaults. Every endpoint not needed for the one-run fixture must be disabled; otherwise it must be blocked from `vst-worker` by an enforceable namespace/UID policy. Authenticated frontend access does not substitute for denying candidate access to unauthenticated diagnostics or internode listeners.

## Authority and fail-closed flow

1. `vst-runner` admits the synthetic story and provides a typed, run-bound operation to the adapter; it does not share Store/signer handles or credentials with candidate code.
2. `vst-adapter` starts the Temporal workflow with an ID derived from the VST run/attempt/epoch, then supervises only the mapped activity. It does not issue arbitrary RPCs from candidate input.
3. Candidate code runs as `vst-worker` in the restricted worktree, separate process/network/mount scope, with no Temporal channel, engine-state path, VST Store, signer, or trusted IPC endpoint.
4. On STOP, the Supervisor advances the VST epoch/fence first. Adapter cancellation and physical child cleanup follow. Any late Temporal result is rejected against current VST identity/fence before a receipt or verdict is accepted.
5. Restart/replay reads the same run-scoped Temporal file state, validates history under the pinned code/profile, and reconciles with VST receipts/idempotency. A replay mismatch, unknown process state, corrupt/missing DB, quota error, stale epoch, or failed cancellation becomes non-approving; it cannot create a new authority path.

## Acceptance and evidence still required

| Requirement | Current disposition | Closure evidence | Owner |
|---|---|---|---|
| File-backed persistence and 1 GiB cap | Design proposed; runtime `NOT_RUN` | Fresh S2 probe binds `/tmp` cap; exact final config/path; DB/WAL/SHM inventory; survives server-process restart | Codex |
| Namespace and bootstrap auth | Design proposed; authorization `NOT_VERIFIED` | Exact role claims for namespace writer and cluster reader; gateway proves only `GetSystemInfo` from cluster scope is forwarded; later assigned tests | Codex; GPT-PM adjudicates |
| Candidate has no engine network | Design proposed; `NOT_VERIFIED` | S2-enforced separate network namespace, no veth/route, deny paths verified under candidate UID; zero external egress | Codex; GPT-PM adjudicates |
| Credential non-inheritance | Design proposed; `NOT_VERIFIED` | Run-scoped token/CA inventory, owner/mode and process visibility checks; candidate cannot read token or inspect adapter | Codex |
| Filesystem isolation | Design proposed; `NOT_VERIFIED` | Candidate denied DB/WAL/SHM/config/keys/Store/signer paths; engine state remains writable only to `vst-engine` | Codex |
| Listener closure | Inventory baseline only | Effective config dump and per-principal reachability matrix for all services, metrics and pprof | Codex |
| RPC gateway reference monitor | Source/design only | Exact pinned bootstrap and worker RPC map; shared gateway filters all calls/retries and binds complete VST identity; specialist review; later assigned tests | Codex; GPT-PM adjudicates |
| STOP, replay and failure behavior | Design specified; runtime `NOT_RUN` | Only after S2/S4 acceptance and approved S3 execution scope, test roles run the accepted non-prohibited scenarios | Functional-test-reviewer / e2e-runner |

S2 Phase 8 remains NOT APPROVED. S3-G01 rights, S3-G02 provenance and G03 compatibility remain open. No server/SDK artifact is acquired, built, installed or run. S4 remains `INCONCLUSIVE`, the 53 policy selectors remain `NOT_RUN`, and no waiver is supplied. S5 remains gated by S2/S4 and a specifically authorized AEVE source.

## Pinned source basis

- [File-backed SQLite template](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-sqlite-file.yaml)
- [SQLite plugin and DSN construction](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/persistence/sql/sqlplugin/sqlite/plugin.go)
- [Authorization configuration and TLS fields](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/config/config.go)
- [Default JWT claim mapper](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_jwt_claim_mapper.go)
- [Default authorizer](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_authorizer.go)
- [API method access metadata](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/api/metadata.go)
- [JWT development example](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-jwt.yaml)
