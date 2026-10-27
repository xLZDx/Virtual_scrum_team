# S3 GPT-PM G07 corrective design adjudication — 2026-10-27

## Correlation

- Request ID: `3d72de89-1451-43d5-8a4f-4ca3b141d875`
- Reply ID: `56a5f7a5-71ae-5080-9dc0-f8dcc3f0f7dd`
- PM Bridge job: `920893d1-73a9-4945-b373-526c8859dbb1` (send-and-await); reply correlation verified by `pm_bridge_job_status`.
- Review target pins: Temporal Server `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e`; Python SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.
- Review type: read-only adversarial design review against the attached S3 plan, corrective proposal, pinned-source evidence and VST adapter/pilot/slice/store source.

## Verdict

**ACCEPT — corrective design; implementation and qualification remain OPEN.** GPT-PM closed G07-M01 (in-memory persistence selection) and G07-M02 (server/worker trust boundary) at design level. It identified zero remaining design BLOCKERs and zero design MAJORs in the attached proposal. This does not accept G03 compatibility/provenance, G07 configuration/runtime, S2 Phase 8, S3 runtime, acquisition, execution or candidate promotion.

## Findings and required follow-up

- The pinned `development-sqlite-file.yaml` is accepted as a planning template; the in-memory profile is excluded from restart/replay qualification. The run-specific file path, DB/WAL/SHM inventory, stable process-restart lifecycle and quota remain to be bound to the actual environment.
- The proposed `/srv/vst-engine/state/...` path is not covered by the previously observed 1 GiB `/tmp` cap. The design's proposed 256 MiB limit needs an actual filesystem/quota enforcement mechanism; merely documenting a cap is insufficient. Codex owns this configuration closure.
- The four principal roles are accepted as a design: trusted VST runner, Temporal engine, trusted adapter, untrusted candidate worker. Candidate code must not share credentials, Store/signer access, engine state or process/network authority.
- Temporal's default authorizer and claim mapper are plausible but do not establish per-run or per-method restrictions by naming them. Codex must map every used API call and required denial; if the pinned authorizer cannot enforce those restrictions, an additional trusted adapter/gateway enforcement layer is required.
- The attached VST Store/pilot contracts are consistent with the proposed authority boundary and fencing order. A Temporal implementation must not move candidate execution into a privileged SDK process; cross-process enforcement remains `NOT_VERIFIED`.
- GPT-PM requires exact final server config, identity enforcement, credentials, all listeners, filesystem/resource controls, STOP/replay mapping and threat flows before G07 configuration/runtime can close.

## Status boundaries

S2 Phase 8 remains `NOT APPROVED`. Shared-fixture Temporal comparison and restart/replay remain `NOT_RUN`. S4's 53 policy selectors remain `NOT_RUN`; AC-17 in-run mutation/change-and-restore remains `NOT_VERIFIED`; S5 remains gated by S2/S4 plus an authorized AEVE source. No acquisition/build/install/execute, test, waiver, push, PR, merge, final candidate or TOP was approved.

## Review limitations

GPT-PM reviewed the attached design and source files but did not independently verify the Windows Git HEAD, generate the Temporal config, or inspect actual host isolation/runtime behavior. The correlated reply itself states this limitation. See request/reply IDs above for the durable PM Bridge record.
