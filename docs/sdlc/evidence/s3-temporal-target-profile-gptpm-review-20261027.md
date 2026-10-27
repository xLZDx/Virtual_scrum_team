# S3 Temporal target-profile GPT-PM review — 2026-10-27

## Request and delivery evidence

- Project: `virtual_scrum_team`
- Declared canonical repository: `D:\Repo\Virtual_scrum_team`
- Declared HEAD in review request: `e78e0497b9e6d5b46684647ab7e55043696a8017`
- Request ID: `d7a90df8-02dc-4fe4-8745-5857228e94b0`
- PM Bridge job ID: `cf418651-28bf-469d-89f1-94a24a3d3423`
- User turn ID: `9c0f127a-4ac1-4ed3-a21b-972dbf5abb0e`
- The reply returned by `gpt_await_reply` began with the exact matching `REQUEST_ID` above. `pm_bridge_status` records the inbound message under the same request ID.
- **Durability limitation:** `pm_bridge_job_status` still reports `status=uncertain`, `sendPhase=sent`, `replyId=null`, and `correlated=null`, even though the exact-ID reply was retrieved and logged inbound. Therefore this is recorded as a request-ID-matched PM Bridge reply, not as a durably correlated/closed gate. A new post-fix verification request is required for closure.
- Scope was target-profile design only. The request explicitly excluded acquisition, legal disposition, provisioning, implementation, build/install, testing, execution, S2/S4 acceptance, candidate selection, PR and merge.

## Verdict returned

**MODIFY — technical direction accepted; one design MAJOR open; zero BLOCKERs.** GPT-PM considered the proposed Temporal source pins, Linux x86-64 / CPython 3.12 planning target, source-declared feature baseline and VST authority model coherent as a future one-story comparison planning basis. The provisional read-only comparator remains Temporal; this is not general compatibility qualification, production acceptance, candidate promotion, or TOP selection.

## Finding `S3-PROFILE-M01` — canonical topology precedence ambiguity

The top-level target profile still described a same-sandbox server/worker and loopback endpoint, while accepted G07 design requires four distinct principals and a mandatory trusted gRPC gateway. Older S3 plan section 10 also contained the less-specific topology. Reading these artifacts at equal authority could lead an implementer to omit mandatory G07 security and persistence boundaries.

The one MAJOR's required correction:

- One run-scoped Temporal server, one trusted SDK adapter that does not run candidate code, one separately isolated candidate process, and distinct `vst-runner`, `vst-engine`, `vst-adapter`, and `vst-worker` principals.
- Mandatory deny-by-default gRPC gateway for every SDK connection, RPC and retry, including `GetSystemInfo`; no direct adapter-to-server path and no candidate route to gateway/server or permission to alter gateway configuration.
- Per-run JWT audience and reviewed authorization claims/RPC map; full VST request/STOP/RESUME/response identity binding.
- File-backed default/visibility stores under bounded per-run `/tmp` state, engine-owned and outside candidate access.
- VST Store/Supervisor remains the sole receipt and final acceptance authority.
- Mark older S3 plan topology as superseded by the accepted G07 design; preserve implementation/runtime qualification as open.

GPT-PM asked Codex to reconcile the target profile and S3 plan, then requested a new GPT-PM verification of `S3-PROFILE-M01` and direct regressions only.

## Applied correction and remaining acceptance

Codex updated `s3-temporal-target-profile-proposal-20261027.md` to make the four-principal/gateway/persistence/authority design normative, and revised S3 plan section 10 to state explicit precedence over its older topology wording. This evidence file and those corrections do not close the MAJOR until the follow-up GPT-PM verification is received with durable correlation.

The design findings `G07-M01`, `G07-M02`, and `G07-CFG-M01` remain accepted at design level only. Gateway/principal implementation, listener/no-bypass enforcement, S2 Phase 8, runtime qualification, G03 dependency/provenance/compatibility, legal/acquisition and candidate comparison remain open. S4 remains `INCONCLUSIVE`; all 53 policy selectors remain `NOT_RUN`; S5 remains gated.

Owner: Codex — profile/plan reconciliation and verification request; GPT-PM — design finding verification; operator — legal/acquisition decisions. No implementation, candidate acquisition, build, install, test or execution was authorized or performed.
