# S3 GPT-PM focused G07 mapping re-review — 2026-10-27

## Correlation and exact pins

- Request ID: `9cc85b3d-644d-45b4-a80c-5dabd8f1ed18`
- Correlated reply ID: `bcfe039f-a0af-5695-b26b-ef23631e7d8a`
- PM Bridge job: `021dc375-a6e2-4097-8ece-d5830d52bc6f`
- User turn ID: `435076d7-48dd-43ec-887a-489a28d4cfe7`
- Durable result: `status=succeeded`, `sendPhase=sent`, `correlated=true`.
- Target: Temporal Server `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e`; Python SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`; SDK-Core gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320`.

## Verdict

**MODIFY — zero BLOCKER, one existing MAJOR `G07-CFG-M01` remains open.** GPT-PM accepted the JWT audience design at source-evidence scope and accepted that the workflow ID need not encode every VST field. It did not accept S3 architecture/config or runtime behavior. The finding remains on two linked design gaps:

1. The closed RPC map omits `GetSystemInfo`, which may be part of connection bootstrap, and the reviewed mapping had not established its exact pinned call path or server authorization metadata. GPT-PM requires an exact-pin source reconciliation and a deny-by-default transport with no wildcard expansion. Affected acceptance areas: AC-3, AC-5, AC-7.
2. The durable workflow mapping was not explicitly required to bind the complete VST request identity and operation key. It must bind at minimum `attempt_id`, `operation_key`, `sandbox_run_id`, candidate revision, manifest digest and fence, alongside the compact workflow-ID seed. Affected acceptance areas: AC-2, AC-3, AC-10.

GPT-PM also requires connection/bootstrap calls and retries to pass through the same guarded transport. Unknown SDK calls remain denied and reported as compatibility failures. The review recommended a separately reviewed trusted gateway or custom server authorizer if the selected Python path cannot enforce the method boundary. It made no request to run code or tests and preserved S2 Phase 8 `NOT APPROVED`, S4 `INCONCLUSIVE`, all 53 S4 policy selectors `NOT_RUN`, and S5 gated.

## Codex exact-pin source reconciliation after the verdict

Read-only inspection of the named exact pins, completed after the correlated reply:

- SDK-Core `crates/client/src/lib.rs` calls `GetSystemInfo` during `Connection::connect_once` unless `skip_get_system_info` is true; non-`Unimplemented` errors fail connection. Pinned C bridge connection options expose neither that skip field nor a path that sets it in the conversion to default Core `ConnectionOptions`.
- Pinned Python `temporalio/bridge/client.py` `ClientConfig` and `temporalio/service.py` `ConnectConfig` do not expose `skip_get_system_info` or the lower-level C bridge raw gRPC override callback. The standard pinned Python path therefore performs the bootstrap call and cannot enforce the complete method list solely at a Python service-call wrapper.
- Pinned Server `common/api/metadata.go` classifies `GetSystemInfo` as cluster/read-only. `default_authorizer.go` checks cluster-scope methods against `claims.System`; the pinned default claim mapper maps `temporal-system:read` to `RoleReader`. This permits other cluster-read APIs at the server authorization layer, so the corrected proposal keeps the token at `temporal-system:read` and requires a trusted shared network gateway to forward `GetSystemInfo` only while denying `ListNamespaces`, `GetSearchAttributes`, and `GetClusterInfo`.
- Exact VST contract fields and response echoes were reconciled against in-repository `tools/vst/worker_adapter.py`. The corrected map now binds full request/stop/resume identity and operation payload digests to the durable workflow mapping, and checks every response identity echo before VST receives a result.

The evidence links and complete proposed boundary are in `s3-temporal-g07-authorization-mapping-20261027.md`. These checks are static source evidence only. The gateway and integration remain unimplemented; authorization enforcement, S2 route separation, SDK/server runtime compatibility, and all runtime claims remain `NOT_VERIFIED` or `NOT_RUN`.

## Next action

Codex owns the exact-pin correction and focused re-review request. GPT-PM owns architecture adjudication. The corrected mapping must remain unapproved until a new correlated response. No acquisition, build/install, execution, test, waiver, acceptance, candidate/TOP, push, PR, or merge is authorized by this response.
