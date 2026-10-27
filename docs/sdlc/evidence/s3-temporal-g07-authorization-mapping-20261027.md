# S3 G07 authorization and run-identity mapping — 2026-10-27

## Status and scope

**GPT-PM accepted at design level only; not implemented or runtime-qualified.** This addresses `G07-CFG-M01` from the correlated review chain: initial config review request `a5f46781-b5f6-436c-b2d4-bf8f38bd317c` / reply `d2f7f553-f270-597b-a0ac-15400d67b948`, focused mapping request `9cc85b3d-644d-45b4-a80c-5dabd8f1ed18` / reply `bcfe039f-a0af-5695-b26b-ef23631e7d8a`, and corrective request `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` / correlated reply `c9313616-dae6-5e23-9d94-21297ae17ec5` (PM Bridge job `9b792eb2-e051-4a3a-9d38-638694b05a6b`). The latest verdict is `ACCEPT — DESIGN ONLY`; `G07-CFG-M01` is closed as a design finding, with zero design BLOCKERs and MAJORs. GPT-PM's exact-head review of change 0405 also accepted the single `RespondActivityTaskCanceled` design amendment, request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245` / correlated reply `14aedf85-c52b-5d64-b84b-40baf9a99455` (PM Bridge job `cc0802b8-7662-47b8-95ba-88613d58be83`), at reviewed HEAD `77b319367b575b9f4c0a193e91405df507c886e6`. This accepts the design exception only; it does not authorize RPC activation or gateway implementation. No account/capability changes, Temporal acquisition/build/install/execution, S2/S3 runtime acceptance, tests, or delivery are authorized.

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
| Namespace role | `permissions` includes `vst-synthetic:write` for the one synthetic namespace. The default authorizer grants this role all non-admin APIs classified for that namespace, not a selected method or workflow. The separate `temporal-system:read` claim is also present for the connection bootstrap below; no system write/admin role is present. | Pinned source fact | Coarse roles narrowed by the mandatory gateway; not runtime-qualified |
| Bootstrap authorization | Add only `temporal-system:read` for the pinned SDK bootstrap; the default server role also permits other cluster-read APIs. No cluster write/admin claim is present. | Pinned source fact plus proposed claim | Not implemented or runtime-qualified |
| Method allowlist | A trusted network gRPC gateway is the mandatory path for every adapter-side Python SDK client connection and every SDK RPC/retry. The pinned Python bridge does not expose the Core skip flag or raw gRPC override callback needed to intercept initial Core connection at the Python client layer. The gateway admits only the RPCs below, including exactly `GetSystemInfo` from cluster scope; all unlisted methods fail closed. The adapter connects only to the gateway; only the gateway can reach the server. Candidate code has no route to either endpoint and cannot alter gateway configuration. | Pinned source fact plus proposed architecture | Not implemented or proven |
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
| `GetSystemInfo` | Pinned Python SDK/Core connection bootstrap and capability negotiation (`Connection::connect_once`, unless skip flag is true; pinned Python C-bridge path does not expose that flag) | Cluster / read | The mandatory gateway permits only this cluster-scoped method. Return the exact expected pinned protobuf response shape and capability information required by the SDK; do not remove mandatory fields. Never allow `ListNamespaces`, `GetSearchAttributes`, or `GetClusterInfo`. An incompatible filtered response or permission error is a hard failure, not grounds to broaden claims or the allowlist. |
| `DescribeNamespace` | Trusted SDK worker verifies the configured namespace at worker startup | Namespace / read | Exact `vst-synthetic` namespace only; no namespace enumeration |
| `PollWorkflowTaskQueue` | Trusted SDK adapter polls its fixed task queue | Namespace / write | Fixed namespace and run-specific task queue; candidate never polls |
| `RespondWorkflowTaskCompleted` | Complete a task after adapter-controlled workflow logic | Namespace / write | Task token must be held by adapter and map to the current run tuple |
| `RespondWorkflowTaskFailed` | Record a workflow-task failure | Namespace / write | Same task-token and run-tuple binding; no candidate-supplied token |
| `PollActivityTaskQueue` | Trusted adapter polls its fixed activity queue | Namespace / write | Fixed namespace and queue; adapter dispatches candidate work through separate bounded runner |
| `RecordActivityTaskHeartbeat` | Adapter reports bounded activity progress | Namespace / write | Adapter-held task token only; payload scrubbed and bounded |
| `RespondActivityTaskCompleted` | Return typed candidate result | Namespace / write | Adapter validates output size/schema and current run tuple first |
| `RespondActivityTaskFailed` | Return typed non-approving activity failure | Namespace / write | Adapter creates failure; candidate cannot choose acceptance status |

All other APIs are denied by the trusted gateway, including cluster reads other than `GetSystemInfo`, namespace administration, cluster administration, workflow signal/terminate/reset/delete, schedule/task-queue administration, Nexus operations, and unknown/new APIs. Exact pinned-source inspection confirmed `GetSystemInfo` in SDK-Core `crates/client/src/lib.rs:401-425`, the C bridge connection options/conversion, and the Python SDK bridge/client connection config. If a required RPC is absent, or the gateway cannot inspect and constrain every connection/retry call, the integration remains blocked pending a new reviewed mapping; there is no wildcard or fallback expansion.

## Narrow G07 amendment — separately accepted at design level, not active implementation

The exact pinned SDK-Core worker client has an activity-cancellation response path that calls `RespondActivityTaskCanceled` (`crates/sdk-core/src/worker/client.rs`, `cancel_activity_task`). The accepted G07 base RPC map above did not authorize this method. GPT-PM accepted the separate single-method amendment at design level only in correlated request `4e961c19-8b4b-4cc2-b2af-45ea9bfb0245` / reply `14aedf85-c52b-5d64-b84b-40baf9a99455`, reviewing exact HEAD `77b319367b575b9f4c0a193e91405df507c886e6`. The base list remains closed; the method is a separately adjudicated narrow design exception. No implementation, runtime behavior, or permission to activate the RPC follows.

Under the accepted design, a future gateway may forward `RespondActivityTaskCanceled` only when all of the following hold; the RPC is not authorized for activation before separately reviewed implementation and runtime qualification:

- After the VST Supervisor durably commits STOP and advances the fence, it can issue a signed cancellation permit for an individual outstanding task token. The permit contains the SHA-256 digest of that opaque token, audience for this gateway/run, STOP operation key, old run/attempt/epoch/fence, new epoch/fence, exact stored workflow ID and Temporal execution run ID, creation/expiry times, and a unique nonce. The Supervisor verifies the STOP operation against durable VST state before signing; its signing key is unavailable to the adapter and candidate. The gateway pins the verifier for the active run. Separate tokens each require their own permit, so one STOP can authorize several outstanding activities without reusing one token's permit.
- The trusted adapter requests a permit per token from the VST Supervisor after STOP commit, then delivers each signed permit to a narrowly scoped authenticated gateway control endpoint. This is an explicit bounded local control-plane message, not another Temporal RPC or a wildcard method. The gateway verifies signature, audience, token digest against its observed token ledger, exact stored workflow/execution binding, monotonic fence advance, expiry and one-use nonce before recording that token's permit. Missing, stale, duplicate, malformed or mismatched permits fail closed.
- The gateway's `PollActivityTaskQueue` proxy records the opaque token returned by Temporal together with the exact workflow/execution pair and the current stored pre-STOP VST tuple. It never trusts token or identity values supplied by candidate code.
- The gateway observes and successfully forwards `RequestCancelWorkflowExecution` for the same exact workflow/execution pair before it accepts a cancellation response. A response is eligible only for an outstanding token in the token ledger whose workflow/execution pair matches the signed STOP permit and the observed Temporal cancellation request.
- The request cannot introduce a token, workflow/run identity, namespace, queue, payload, or candidate result. Candidate-originated cancellation details are omitted; if the pinned SDK requires details, the trusted adapter supplies only a fixed or sanitized bounded diagnostic. Unknown, duplicate, expired, or unbound tokens fail closed.
- The acknowledgment only terminates that Temporal activity task. It cannot create or modify a VST receipt, result, acceptance status, budget, or current fence. Any completion/result from the stale activity remains rejected against the live VST fence.
- Consume each per-token permit for the exact token/request digest; allow only a byte-identical SDK retry within the bounded retry window. After recorded upstream success, return the cached terminal response for an identical retry without forwarding again. Resolve an ambiguous upstream outcome into one recorded terminal disposition: (1) conclusive history evidence of success consumes the permit without another forward; (2) conclusive evidence of non-success permits only the bounded identical retry; or (3) insufficient/conflicting evidence leaves a terminal non-approving/blocked state with no automatic retry. Reject conflicting or later replay. Record each token's terminal disposition durably for the run.
- No other cancellation, completion, workflow-control, or namespace method is added by implication. If the pinned SDK requires another method or the gateway cannot enforce this token ledger, the candidate profile remains blocked pending a separate exact-method review.

This design proposal adds a Supervisor-to-gateway control message and token/cancellation correlation state that do not exist as implementation evidence. GPT-PM must adjudicate both the method exception and these enforcement inputs. No current authorization or runtime behavior is inferred from the proposal.

Owner: GPT-PM accepted this architecture amendment at design level; Codex owns the documented follow-up and exact-source evidence. Codex closed the non-blocking terminal-reconciliation wording note in change 0406. The RPC is accepted only as a design exception with the specified permit contract; gateway/Supervisor implementation and exact-pair cancellation interoperability remain `NOT_VERIFIED` / `NOT_RUN`.

Because default `RoleWriter` admits every non-admin API in the synthetic namespace and `temporal-system:read` admits the server's cluster-read methods, this allowlist is not enforced by the server's built-in authorizer. A trusted gRPC gateway is the mandatory reference monitor because the pinned Python SDK's initial Core `GetSystemInfo` call occurs before Python workflow operations and its bridge config does not expose Core's raw gRPC override hook. Every adapter SDK connection and call/retry must target the gateway; the adapter cannot connect directly to the server, only the gateway can reach the server, and candidate code cannot reach either endpoint or change gateway configuration. The gateway must bind each connection/retry to one run identity, admit only this map, inspect/limit payloads, and deny unlisted methods before forwarding. For `GetSystemInfo`, it preserves the pinned protobuf response shape and required capability fields; if this cannot be done compatibly, it fails closed. These no-bypass controls require later implementation review and S2/runtime evidence. If the gateway cannot be implemented and independently reviewed, G07 implementation remains blocked; use a separately reviewed custom server authorizer or a different SDK path only after new GPT-PM adjudication. This is not a claim that the current server config provides per-RPC authorization.

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
- GPT-PM: the correlated corrective adjudication `f591d5e7-9be2-4e26-94ce-d8e16be73b6e` / `c9313616-dae6-5e23-9d94-21297ae17ec5` accepted this mapping at design level and closed `G07-CFG-M01`. Gateway implementation, independent review, and allowed runtime qualification remain separate gates.
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
- [Pinned SDK-Core activity cancellation response path](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/sdk-core/src/worker/client.rs#L784-L808)
- [Pinned SDK-Core connection bootstrap and GetSystemInfo call](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/client/src/lib.rs#L401-L425)
- [Pinned SDK-Core C bridge options and connection conversion](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/crates/sdk-core-c-bridge/src/client.rs#L24-L65)
- [Pinned Python SDK bridge ClientConfig](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/client.py#L70-L88)
- [Pinned Python SDK ConnectConfig and Core bridge construction](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/service.py#L225-L307)
- [Pinned Python Client.connect defaults to non-lazy](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/client/_client.py#L135-L158)
- [Pinned server API metadata for cluster methods](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/api/metadata.go#L128-L132)
- [Pinned server default authorization by API scope](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/authorization/default_authorizer.go#L45-L56)
- [Pinned system namespace and default JWT permission mapping](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/common/primitives/namespaces.go#L10-L13)
- [VST WorkerRequest/StopRequest/ResumeRequest/WorkerResponse contract](../../../tools/vst/worker_adapter.py)
