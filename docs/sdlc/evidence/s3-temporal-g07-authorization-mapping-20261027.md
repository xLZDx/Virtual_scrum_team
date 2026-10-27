# S3 G07 authorization and run-identity mapping — 2026-10-27

## Status and scope

**Codex read-only correction after focused GPT-PM review; pending re-adjudication; not implemented or runtime-qualified.** This addresses `G07-CFG-M01` from the correlated review chain: initial config review request `a5f46781-b5f6-436c-b2d4-bf8f38bd317c` / reply `d2f7f553-f270-597b-a0ac-15400d67b948`, followed by focused mapping request `9cc85b3d-644d-45b4-a80c-5dabd8f1ed18` / reply `bcfe039f-a0af-5695-b26b-ef23631e7d8a`, job `021dc375-a6e2-4097-8ece-d5830d52bc6f`. The focused verdict is `MODIFY`, with one MAJOR still open. It does not authorize account/capability changes, Temporal acquisition/build/install/execution, S2/S3 acceptance, tests, or delivery. No local code has been changed.

Pinned target remains Temporal Server `v1.32.1` commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` and Python SDK `1.34.0` commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`. Its `temporalio/bridge/sdk-core` entry is gitlink commit `e163abd6dc19040064986a63c8b8cf4756ffd320`. The operation-path screen below uses those exact pins. It records a proposed boundary and static source behavior, not proof the proposed adapter exists or a runtime trace.

## Pinned-source facts relevant to token checks

The server configuration has `global.authorization.audience`. Its configured `AudienceMapper` returns that fixed string. The authorization interceptor places the mapper result in `AuthInfo.Audience` before invoking the claim mapper. The pinned default JWT mapper calls `parseJWTWithAudience`; when its expected audience is non-empty, it requires `aud` to contain that value. Therefore a run-specific audience is server-checked only when the server's own `global.authorization.audience` is set to that exact run audience. A run-specific `aud` token claim alone does not make an empty/default server audience run-specific.

The config audience is static for one server config. The proposed profile must therefore run one Temporal server instance per synthetic VST run, with the exact run audience frozen in that instance's config. A shared server instance cannot claim distinct per-run audience enforcement from this field.

The pinned default key provider accepts only `RS256` and `ES256` and resolves the token `kid` against configured keys. The default mapper requires a string `sub` and maps strings in the `permissions` array into namespace/system roles. It invokes JWT `Claims.Valid()` and does not explicitly validate an issuer claim or require that an expiry claim be present. Therefore:

- This profile selects `RS256`, a unique `kid`, and a local per-run JWKS file readable only by `vst-engine`; `vst-runner` holds the corresponding private key. No network JWKS source is used.
- The trusted issuer must require a short `exp`, include it in every token, and reject token creation if it is absent; server-side mapper validation does not establish mandatory expiry presence.
- `iss` is descriptive only for this pinned default mapper. The security proof comes from the run-specific verifier key, checked `aud`, namespace claim, protected token delivery, and process/network boundary—not from an `iss` check that the mapper does not implement.
- Token `sub` is `vst-adapter:<run-id>` for audit identity. This is not a workflow-level permission: the default authorizer does not enforce `sub` restrictions.
- Exact pinned SDK/Core source shows connection establishment calls `GetSystemInfo` unless `skip_get_system_info` is true. The pinned C bridge options do not expose that skip flag, default construction does not set it, and the pinned Python `ConnectConfig`/`ClientConfig` expose neither the skip flag nor the lower-level gRPC override callback. `Client.connect` defaults `lazy=False`; worker clients cannot use lazy mode. The normal connection path used for this worker therefore sends this bootstrap call.
- Pinned server API metadata classifies `GetSystemInfo` as `ScopeCluster` / `AccessReadOnly`; the default authorizer evaluates cluster-scoped calls against `claims.System`. The default JWT mapper maps `temporal-system:read` to the reader role, which is needed for `GetSystemInfo` under this profile. That role also makes other cluster-read APIs eligible at the server layer, including `ListNamespaces`, `GetSearchAttributes`, and `GetClusterInfo`. The trusted network gateway below must therefore allow exactly `GetSystemInfo` and reject those other cluster-read methods. No system write/admin role is proposed.
- The exact claim payload is `{"sub":"vst-adapter:<run-id>","aud":["vst-temporal://<run-id>"],"exp":<short-unix-expiry>,"permissions":["temporal-system:read","vst-synthetic:write"]}`. It grants only the named cluster-reader and synthetic-namespace writer roles at the server's default role layer; the gateway further restricts the actual methods.

## Enforcement layers

| Boundary | Exact proposed control | Evidence type | Current state |
|---|---|---|---|
| JWT signature and algorithm | Pinned default key provider: only `RS256` or `ES256`; key selected by `kid` from local run JWKS. Profile chooses RS256. | Pinned source fact plus proposed run values | No key material/provisioning; runtime `NOT_RUN` |
| Audience | Set `global.authorization.audience` to `vst-temporal://<run-id>` in the sole run's server config. Adapter token `aud` must contain exactly that value. Empty server audience is forbidden. | Pinned source fact plus proposed per-run config | Not generated or tested |
| Token time claims | Issuer requires a short-lived `exp`; server calls JWT `Claims.Valid()` but profile does not rely on the mapper to require claim presence. | Pinned source fact plus issuer contract | Not implemented |
| Namespace role | `permissions` contains only `vst-synthetic:write`; no system role. The default authorizer grants this role all non-admin APIs classified for that namespace, not a selected method or workflow. | Pinned source fact | Coarse role accepted only for trusted adapter principal |
| Bootstrap authorization | Add only `temporal-system:read` for the pinned SDK bootstrap; the default server role also permits other cluster-read APIs. No cluster write/admin claim is present. | Pinned source fact plus proposed claim | Not implemented or runtime-qualified |
| Method allowlist | A trusted network gRPC gateway is required as the shared reference monitor. The pinned Python bridge does not expose the Core skip flag or raw gRPC override callback needed to intercept the initial Core connection at the Python client layer. The gateway admits only the RPCs below, including exactly `GetSystemInfo` from cluster scope; all unlisted methods fail closed. Candidate-to-gateway, adapter-to-gateway, and gateway-to-server paths must be enforced so no client bypasses it. | Pinned source fact plus proposed architecture | Not implemented or proven |
| Workflow/run binding | The gateway/adapter validates the full persisted VST request identity, per-operation key and payload digest before every workflow call and validates response echoes before returning them to the VST Supervisor. | Existing VST contract plus proposed enforcement | Not implemented or proven |
| Candidate exclusion | Candidate has no token/key/file access, no Temporal endpoint route, no adapter process inspection, and only bounded typed IPC for candidate work. | S2 OS/network boundary | `NOT_VERIFIED` |
| VST authority | VST Store/Supervisor remains the only receipt signer and final verdict authority; Temporal completion alone never yields acceptance. | Existing VST contract plus proposed integration | Design only |

## Closed proposed RPC allowlist

This list is deliberately a contract allowlist, not a claim that the pinned Python SDK has already been integrated. The pinned SDK-Core workflow handle has call paths for start, describe, history and cancellation; its worker client has poll, complete/fail/cancel and heartbeat paths named below. Before execution, implementation must reconcile every actual outgoing call, including initialization and retries. The transport allowlist remains closed: any unlisted call is denied and becomes a compatibility failure requiring review, not an automatic expansion. Broader SDK operations (including signal, terminate, reset and schedules) are intentionally outside this VST profile.

| RPC | Intended purpose | Pinned method metadata | Adapter rule |
|---|---|---|---|
| `StartWorkflowExecution` | Start one synthetic run | Namespace / write | Exact namespace, workflow type, task queue, workflow ID and input digest only |
| `DescribeWorkflowExecution` | Read current state and bind server run ID | Namespace / read | Exact workflow ID and execution run ID only |
| `GetWorkflowExecutionHistory` | Read history for reconciliation | Namespace / read | Exact workflow ID and execution run ID only; no arbitrary namespace/history query |
| `RequestCancelWorkflowExecution` | Request cancellation after VST fence advances | Namespace / write | Exact workflow ID and execution run ID only; no terminate or reset |
| `GetSystemInfo` | Pinned Python SDK/Core connection bootstrap and capability negotiation (`Connection::connect_once`, unless skip flag is true; pinned Python C-bridge path does not expose that flag) | Cluster / read | The gateway permits only this cluster-scoped method. Project only the capability fields required by the pinned client; never allow `ListNamespaces`, `GetSearchAttributes`, or `GetClusterInfo`. A permission error is a hard connection failure, not grounds to broaden claims or the allowlist. |
| `DescribeNamespace` | Trusted SDK worker verifies the configured namespace at worker startup | Namespace / read | Exact `vst-synthetic` namespace only; no namespace enumeration |
| `PollWorkflowTaskQueue` | Trusted SDK adapter polls its fixed task queue | Namespace / write | Fixed namespace and run-specific task queue; candidate never polls |
| `RespondWorkflowTaskCompleted` | Complete a task after adapter-controlled workflow logic | Namespace / write | Task token must be held by adapter and map to the current run tuple |
| `RespondWorkflowTaskFailed` | Record a workflow-task failure | Namespace / write | Same task-token and run-tuple binding; no candidate-supplied token |
| `PollActivityTaskQueue` | Trusted adapter polls its fixed activity queue | Namespace / write | Fixed namespace and queue; adapter dispatches candidate work through separate bounded runner |
| `RecordActivityTaskHeartbeat` | Adapter reports bounded activity progress | Namespace / write | Adapter-held task token only; payload scrubbed and bounded |
| `RespondActivityTaskCompleted` | Return typed candidate result | Namespace / write | Adapter validates output size/schema and current run tuple first |
| `RespondActivityTaskFailed` | Return typed non-approving activity failure | Namespace / write | Adapter creates failure; candidate cannot choose acceptance status |
| `RespondActivityTaskCanceled` | Acknowledge activity cancellation | Namespace / write | Only after run tuple and cancellation token match |

All other APIs are denied by the trusted gateway, including cluster reads other than `GetSystemInfo`, namespace administration, cluster administration, workflow signal/terminate/reset/delete, schedule/task-queue administration, Nexus operations, and unknown/new APIs. Exact pinned-source inspection confirmed `GetSystemInfo` in SDK-Core `crates/client/src/lib.rs:401-425`, the C bridge connection options/conversion, and the Python SDK bridge/client connection config. If a required RPC is absent, or the gateway cannot inspect and constrain every connection/retry call, the integration remains blocked pending a new reviewed mapping; there is no wildcard or fallback expansion.

Because default `RoleWriter` admits every non-admin API in the synthetic namespace and `temporal-system:read` admits the server's cluster-read methods, this allowlist is not enforced by the server's built-in authorizer. A trusted gRPC gateway is the proposed reference monitor because the pinned Python SDK's initial Core `GetSystemInfo` call occurs before Python workflow operations and its bridge config does not expose Core's raw gRPC override hook. The gateway must bind all connections/retries to one run identity, admit only this map, inspect/limit payloads, and deny unlisted methods before forwarding. S2 must prevent direct access to the server and gateway from candidate code. If this gateway cannot be implemented and independently reviewed, G07 remains open; use a separately reviewed custom server authorizer or a different SDK path only after new GPT-PM adjudication. This is not a claim that the current server config provides per-RPC authorization.

## Deterministic workflow identity and idempotency

Define the workflow-ID seed tuple as `(run_id, attempt, epoch)`, with positive unsigned 64-bit `attempt` and `epoch`. This compact tuple selects one workflow ID; it is not the complete authorization identity. Build a versioned, unambiguous byte encoding using a domain tag plus length-prefixed UTF-8 `run_id` and fixed-width big-endian integers. Set:

```text
workflow_id = "vst1-" + lowercase_hex(SHA-256(canonical_tuple_bytes))
```

Before first start, the durable VST mapping must bind the workflow ID and Temporal execution `run_id` to the full VST contract identity, not just the seed tuple:

- Stable `WorkerRequest` identity: `run_id`, `attempt`, `epoch`, `fence`, `attempt_id`, `operation_key`, `effect_key`, `candidate_id`, `candidate_revision`, `manifest_sha256`, `task_id`, `story_id`, `sandbox_run_id`, `base_head`, `budget_cap`, `budget_spent`, `budget_units`, canonical `allowed_paths`, `change_path`, `invocation_id`, and `timeout_sec`.
- Payload binding: SHA-256 of the exact canonical request payload, including `change_content`; require `effect_key` to match the VST derivation and reject same-key/different-payload retries.
- Operation binding: persist the operation name and its exact operation key. For STOP, bind the full `StopRequest` (`reason`, `authorized_actor`, `budget_remaining`, identity fields, and operation key) to the current stored run/attempt/fence. For RESUME, bind `prior_operation_key`, `prior_attempt_id`, `prior_attempt`, `prior_epoch`, optional `prior_receipt_sha256`, remaining budget, and the complete new `WorkerRequest`; require a new attempt ID/number and newer epoch as the VST contract does.
- Response reconciliation: before returning a `WorkerResponse` to VST, require exact equality for its echoed `run_id`, `attempt_id`, `operation_key`, `effect_key`, `candidate_id`, `candidate_revision`, `manifest_sha256`, `epoch`, `fence`, `invocation_id`, and `sandbox_run_id`; also enforce the persisted budget bounds and typed output contract. Workflow/execution IDs must match the stored binding. Any missing or mismatched field is non-approving. Never infer unchecked fields from the compact workflow-ID tuple.

Every allowed workflow call and retry resolves to this durable full binding and to the gateway's run-scoped channel; retries cannot broaden the method set or change request identity after permission denial. A new VST attempt or epoch produces a different workflow ID. Do not accept Continue-As-New, child-workflow, signal, terminate, reset, or cross-namespace behavior in this one-run profile.

## STOP, failure and candidate denial

1. The VST Supervisor commits its epoch/fence transition before any Temporal cancellation request.
2. The adapter issues only `RequestCancelWorkflowExecution` for the exact stored workflow/execution pair; physical candidate cleanup remains separate and unproven until S2 acceptance permits its evidence.
3. Late task/results are compared to the live VST tuple and task-token binding; stale results are discarded and cannot be signed or accepted.
4. Missing execution ID, mismatched tuple/payload, conflicting retry, expired/invalid token, unknown RPC, unverified cancellation, lost process, or unavailable history yields a non-approving result. No fallback to a new empty history is allowed.
5. Candidate code receives neither the JWT nor file/key/socket descriptors. S2 must prove UID/process inspection denial, endpoint no-route, filesystem denial and bounded IPC before any S3 execution.

## Required next evidence

- Codex: propose the pinned bootstrap method and `temporal-system:read` constraint behind a mandatory deny-by-default trusted gateway; the exact SDK does not expose the Python-layer connection skip/transport override. No gateway code, build, or runtime is authorized yet.
- GPT-PM: adjudicate this corrected exact mapping against `G07-CFG-M01`, AC-2/3/5/7/10 and the pinned source. The latest correlated review says `MODIFY`, one MAJOR open.
- Operator: retain legal/acquisition and any sandbox-change authorization. No operator decision is needed to complete this read-only mapping.
- Functional-test-reviewer / e2e-runner: after code completion and S2/S4 acceptance, derive and run assigned tests; currently `NOT_RUN`.

S2 Phase 8 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE` with 53 selectors `NOT_RUN`; S5 remains gated; no candidate/TOP is selected.

## Pinned sources

- [Audience and configuration type](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/config/config.go)
- [Static audience mapper](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/audience_mapper.go)
- [Authorization interceptor](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/interceptor.go)
- [Default JWT claim mapper](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_jwt_claim_mapper.go)
- [Default token key provider](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_token_key_provider.go)
- [Default authorizer](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_authorizer.go)
- [API method metadata](https://raw.githubusercontent.com/temporalio/temporal/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/api/metadata.go)
- [Pinned Python SDK generated service operations](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/services_generated.py)
- [Pinned SDK-Core workflow handle call paths](https://raw.githubusercontent.com/temporalio/sdk-rust/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/client/src/workflow_handle.rs)
- [Pinned SDK-Core worker call paths](https://raw.githubusercontent.com/temporalio/sdk-rust/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/sdk-core/src/worker/client.rs)
- [Pinned SDK-Core connection bootstrap and GetSystemInfo call](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/client/src/lib.rs#L401-L425)
- [Pinned SDK-Core C bridge options and connection conversion](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/sdk-core-c-bridge/src/client.rs#L24-L65)
- [Pinned Python SDK bridge ClientConfig](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/client.py#L70-L88)
- [Pinned Python SDK ConnectConfig and Core bridge construction](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/service.py#L225-L307)
- [Pinned Python Client.connect defaults to non-lazy](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/client/_client.py#L135-L158)
- [Pinned server API metadata for cluster methods](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/api/metadata.go#L128-L132)
- [Pinned server default authorization by API scope](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_authorizer.go#L45-L56)
- [Pinned system namespace and default JWT permission mapping](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/primitives/namespaces.go#L10-L13)
- [VST WorkerRequest/StopRequest/ResumeRequest/WorkerResponse contract](../../../tools/vst/worker_adapter.py)
