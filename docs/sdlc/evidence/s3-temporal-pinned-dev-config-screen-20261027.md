# S3 Temporal pinned development configuration screen — 2026-10-27

## Scope and provenance

Read-only inspection of official Temporal source pinned by the S3 profile proposal to server commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` (`v1.32.1`). No source or artifact was downloaded into the repository, acquired, built, installed, or executed. This is static source evidence only; it is not a runtime configuration or approval.

Primary sources inspected:

- `config/development.yaml` at the pinned commit delegates to the SQLite development profile.
- `config/development-sqlite.yaml` at the pinned commit.
- `common/authorization/authorizer.go` at the pinned commit.
- `cmd/server/main.go` at the pinned commit.
- `Makefile` at the pinned commit.

## Observed source facts

- Both `sqlite-default` and `sqlite-visibility` use SQLite with `mode: memory`, private cache, and one maximum connection in `config/development-sqlite.yaml` (lines 7–49). This profile does not provide durable history across process restart.
- Frontend gRPC/HTTP and membership, matching, history, and worker endpoints set `bindOnLocalHost: true` (lines 63–87). Prometheus metrics bind to `127.0.0.1:8000`; pprof uses port 7936 (lines 50–62). Loopback binding limits interface exposure but does not isolate another process running in the same sandbox or identity boundary.
- The development config does not set an authorization authorizer in the inspected file. The pinned `GetAuthorizerFromConfig` maps an empty authorizer name to `NewNoopAuthorizer()` (`common/authorization/authorizer.go`, lines 60–67). The server startup logs a warning when that authorizer is used without `--allow-no-auth`; the warning is not itself an enforcement failure (`cmd/server/main.go`, lines 186–198).
- The pinned server exposes an `--allow-no-auth` start flag (`cmd/server/main.go`, lines 64–73). The pinned Makefile's SQLite development target uses `config/development-sqlite.yaml --allow-no-auth` (Makefile start target). This is evidence about a development startup path, not a recommendation for the S3 comparison profile.
- The pinned `config/development-sqlite-file.yaml` is a separate file-backed profile: both stores set `setup: true`, `journal_mode: wal`, and `synchronous: 2`, without `mode: memory`. The file uses the placeholder `databaseName: "default"`; it does not establish an absolute path, owner, permissions, quota, restart policy, or protected lifecycle.
- The pinned SQLite plugin constructs its SQLite DSN from `databaseName` as `file:<databaseName>?...`; it runs schema setup for file mode when `setup` is true. This makes file-backed SQLite a concrete supported starting point, but does not establish that the placeholder path is appropriate or that file permissions protect it from candidate processes.
- The pinned `common/config/config.go` defines `authorization.authorizer` (`"default"` selects the default authorizer), JWT key provider, claim mapper, permissions claim/regex, and TLS client authentication settings. The server's default authorizer maps claims to health, system, or namespace roles. These mechanisms can support an authenticated design, but the development profile does not configure them and this source screen does not establish a least-privilege candidate role or enforcement.
- The pinned `config/development-jwt.yaml` demonstrates `authorizer: "default"`, `claimMapper: "default"`, a `file://` JWKS source, an internal-frontend service and loopback binds. It still uses `mode: memory` and a test-only `/tmp/temporal-jwt-test/...` key path, so it is mechanism evidence only and is not suitable as the complete comparison profile.
- The pinned default JWT claim mapper reads a `permissions` array (or configured claim/regex) and maps namespace or system roles; the default authorizer evaluates those claims against API method metadata. The key provider supports `file://`, `http://` and `https://` JWKS sources. For an offline run, local key material is technically supported by this source, but its integrity, ownership, audience, role scope, refresh and rotation still require an explicit run profile.

### Exact audience and token-validation path

Read-only follow-up of the pinned files `common/authorization/audience_mapper.go`, `interceptor.go`, `default_jwt_claim_mapper.go`, `default_token_key_provider.go`, `default_authorizer.go`, `common/api/metadata.go`, and `common/config/config.go` established:

- `global.authorization.audience` is the configured expected JWT audience. The default `AudienceMapper` returns this static string; the frontend authorization interceptor places it in `AuthInfo.Audience`; the default JWT claim mapper verifies `aud` against it when that expected value is non-empty. Therefore, a run-specific token audience is enforced only when the matching non-empty audience is in that run's server config. A static config cannot provide distinct per-run audiences for a shared server process.
- The default key provider allows only `RS256` and `ES256`, and resolves `kid` to a configured key. The mapper requires `sub` to be a string, reads the `permissions` array, invokes the JWT library's `Claims.Valid()`, and checks `aud` when configured. The pinned mapper does not explicitly compare an issuer claim or enforce that `exp` is present. Issuer-side policy must therefore require and include a short expiry; an `iss` field must not be reported as a server-validated boundary.
- The default authorizer uses API metadata to admit read/write/admin role levels. Namespace `writer` admits every method classified as non-admin for that namespace; it is not per-workflow or per-RPC authorization. The exact methods and run identity still require an adapter enforcement contract.

### Pinned Python SDK operation path screen

The pinned Python SDK `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` has the `temporalio/bridge/sdk-core` gitlink at `e163abd6dc19040064986a63c8b8cf4756ffd320` (repository `temporalio/sdk-rust`). Static source inspection of that exact SDK-Core commit found the workflow handle paths for start, describe, history and cancel; worker client paths for workflow/activity polling, task responses, activity heartbeat and namespace describe. It also calls `GetSystemInfo` in `Connection::connect_once` unless `skip_get_system_info` is set. The Python bridge client config has no such field; the C bridge connection options contain no skip field and their conversion constructs default Rust `ConnectionOptions` without setting the skip flag. The Python config also does not expose the C bridge's raw gRPC override callback. Python `Client.connect` defaults `lazy=False`, and worker clients cannot use lazy mode. Thus the normal pinned Python worker connection performs the bootstrap RPC and cannot install a call filter through that Python bridge config alone. The exact proposed RPC map, required gateway boundary and restrictions are recorded in `s3-temporal-g07-authorization-mapping-20261027.md`. This is source-path inspection only; no adapter or gateway was built or run.

The pinned server `common/api/metadata.go` classifies `GetSystemInfo` as cluster-scope, read-only. `default_authorizer.go` resolves cluster-scope calls through `claims.System`; the default JWT mapper maps `temporal-system:read` to the reader role. The same server scope also lets that role satisfy other cluster-read methods, so the gateway must deny those except `GetSystemInfo`. This is static authorization metadata, not runtime proof.

## S3 G07 disposition

The earlier proposed profile's generic statement “Temporal history is supporting state only; VST owns authoritative run state” remains a design boundary, not demonstrated behavior. The default in-memory development profile cannot establish restart/replay durability. The pinned file-backed SQLite profile is a viable planning candidate for review, but its placeholder path and runtime behavior are not yet qualified. Loopback listeners plus a no-op authorizer do not by themselves establish isolation between the Temporal server and candidate worker when both share a sandbox. G07 therefore remains open for an explicitly selected persistence mode/path, server/adapter/candidate identity separation, least-privilege API authorization, endpoint controls, filesystem and resource enforcement, and a threat-flow review.

Do not use the default in-memory/no-authorizer profile as evidence for restart/replay qualification. Do not infer that another profile is suitable until its exact pinned configuration and boundary controls are inspected and GPT-PM adjudicates the architecture. No server, worker, listener, persistence service, build, test, or candidate was run.

## Ownership and next actions

- Codex: continue source-only audit of the exact pinned configuration and record any additional G07 constraints; do not acquire, build, install, or execute Temporal.
- GPT-PM: adjudicate whether a candidate architecture can satisfy G07 and what exact server/worker separation and persistence contract is required.
- Operator: retains legal disposition and any acquisition decision; no action is requested by this evidence record.

## Source links

- [Pinned development SQLite configuration](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-sqlite.yaml)
- [Pinned file-backed SQLite configuration](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-sqlite-file.yaml)
- [Pinned SQLite plugin](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/persistence/sql/sqlplugin/sqlite/plugin.go)
- [Pinned authorization factory](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/authorizer.go)
- [Pinned default authorizer](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_authorizer.go)
- [Pinned config/auth/TLS types](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/config/config.go)
- [Pinned JWT development config](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/config/development-jwt.yaml)
- [Pinned JWT key provider](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_token_key_provider.go)
- [Pinned server startup](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/cmd/server/main.go)
- [Pinned Makefile](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/Makefile)
- [Pinned SDK-Core connection code (`GetSystemInfo`)](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/client/src/lib.rs#L401-L425)
- [Pinned SDK-Core C bridge connection options](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/sdk-core-c-bridge/src/client.rs#L24-L65)
- [Pinned Python SDK Core client config](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/client.py#L70-L88)
- [Pinned server API metadata and default authorization](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/api/metadata.go#L128-L132)
