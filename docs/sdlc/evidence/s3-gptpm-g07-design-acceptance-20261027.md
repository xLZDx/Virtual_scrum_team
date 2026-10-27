# S3 GPT-PM G07-CFG-M01 design acceptance — 2026-10-27

## Correlation and scope

- Request ID: `f591d5e7-9be2-4e26-94ce-d8e16be73b6e`
- Correlated reply ID: `c9313616-dae6-5e23-9d94-21297ae17ec5`
- PM Bridge job: `9b792eb2-e051-4a3a-9d38-638694b05a6b`
- User turn ID: `7fa604df-dfd2-4cbb-b3da-7b1d444760c8`
- Durable result: `status=succeeded`, `sendPhase=sent`, `correlated=true`.
- Target: Temporal Server `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e`; Python SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`; SDK-Core gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320`.

## Verdict

**ACCEPT — design only.** GPT-PM closed `G07-CFG-M01` at design level, with zero remaining design BLOCKERs and zero design MAJORs. The reply accepted the exact-source evidence for `GetSystemInfo` bootstrap and server cluster-read authorization, and found the mandatory shared gateway plus complete durable VST identity mapping defensible at design level.

The gateway is acceptable only if it is an unavoidable boundary: the adapter cannot connect directly to Temporal; only the gateway can reach the server; candidate code cannot reach either endpoint or alter gateway configuration. The gateway must deny all methods outside the closed map, mediate connection/bootstrap/retry calls, constrain request payloads, and reject permission/compatibility failures without broadening access. The proposed `temporal-system:read` server role is broader than `GetSystemInfo`; the gateway must block other cluster-read methods. The gateway must preserve the exact pinned protobuf response shape and mandatory capability fields; incompatible filtering must fail closed.

GPT-PM accepted full request/STOP/RESUME/response identity binding, including operation keys, payload/effect digests, fence, workflow ID and separately persisted Temporal execution run ID. It did not require encoding every field into the workflow ID itself.

## Remaining acceptance boundaries

The response grants design acceptance only. It does not approve implementation, runtime qualification, provisioning, acquisition, tests, policy waiver, S2/S3 acceptance, candidate selection/TOP, push, PR, or merge.

- Gateway implementation and specialist review: `NOT_IMPLEMENTED` — Codex.
- Actual RPC/retry enforcement and listener no-bypass: `NOT_VERIFIED` — Codex.
- Four-principal/process/credential isolation: `NOT_VERIFIED` — Codex; operator provides any genuinely required host-level authorization.
- SQLite quota/persistence lifecycle and server restart/replay: `NOT_VERIFIED` / `NOT_RUN` — Codex.
- Server/SDK runtime interoperability: `NOT_RUN` — Codex, after all prerequisites and test-owner assignment.
- G03 dependency/provenance and exact-version legal disposition: open; Codex owns read-only source evidence, operator owns legal/acquisition decisions.
- S2 Phase 8: `NOT APPROVED`; S4: `INCONCLUSIVE`, all 53 policy selectors `NOT_RUN`; S5: gated on S2/S4 and a concrete authorized AEVE source.

## Non-blocking documentation precision

GPT-PM noted two documentation corrections that do not reopen the MAJOR:

1. Keep the namespace role row consistent with the separate `temporal-system:read` bootstrap claim; no system write/admin role is present.
2. State explicitly that the gateway is mandatory for all SDK client connections, not an optional workflow-call interceptor.

Codex applied these clarifications in the mapping and configuration proposal. The first gateway source implementation still needs its own implementation review and allowed runtime qualification before any S3 execution.
