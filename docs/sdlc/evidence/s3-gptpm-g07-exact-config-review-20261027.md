# S3 GPT-PM exact G07 config review — 2026-10-27

## Correlation

- Request ID: `a5f46781-b5f6-436c-b2d4-bf8f38bd317c`
- Reply ID: `d2f7f553-f270-597b-a0ac-15400d67b948`
- User turn ID: `70f688cf-e40d-4b77-a7e6-9cf09985436e`
- Send-and-await job: `f03b4be7-6a10-4944-8a84-2e8df491fdf2`; durable status is `uncertain` because the parked wait deadline elapsed, but the job result records `correlated: true`, the exact matching request ID and reply ID above.
- A subsequent same-request `peek` job `279dfff4-ecee-4d27-b7c5-6f17529ac019` reproduced the same request-bound response. The authoritative correlation fields are from the send-and-await job.
- Target pins: Temporal Server `v1.32.1` / `af08a5e5f2dd40f545f2afac7780daaa6987001e`; Python SDK `1.34.0` / `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.
- Review scope included the exact config proposal, S3 plan, pinned-source evidence and attached VST control-plane files.

## Verdict

**MODIFY — persistence design accepted; authorization configuration incomplete.** GPT-PM confirms zero new design BLOCKERs and one remaining MAJOR: `G07-CFG-M01`, authorization and run-scope enforcement not fully specified. A run-specific JWT `aud` is not proof of server enforcement unless the pinned server's expected audience is configured and validated. Namespace `writer` is broader than per-method/per-run capability. The exact allowed RPC set and mapping from VST run/attempt/epoch to Temporal workflow/execution IDs were missing from the reviewed proposal.

The response says the file-backed SQLite and same-live-S2-run process-restart design are acceptable at design level. It explicitly does not claim cross-Wsl/S2-boundary durability. The observed 1 GiB `/tmp` cap is overall, not reserved for Temporal. The four-principal/process/network/filesystem separation remains design-consistent but unproven under S2.

## Required closure mapping from GPT-PM

Provide an exact map that identifies:

- token signature algorithm/key, issuer, audience, expiry, and which checks the pinned mapper actually performs;
- exact permission claim shape and namespace role;
- the default authorizer's method scope and exact permitted methods;
- the adapter's closed RPC allowlist;
- deterministic binding of VST run, attempt and epoch to Temporal workflow and execution IDs;
- duplicate/retry conflict behavior and STOP/cancel ordering;
- candidate exclusions and mandatory denial of unexpected RPCs;
- whether each property is enforced by server, trusted adapter or S2 OS/network boundary.

If the trusted adapter and S2 boundary cannot guarantee the necessary method restriction, select and specify an enforceable custom-authorizer or gateway. GPT-PM requires exact pinned-source semantics and a complete RPC/identity mapping, without unsupported audience or role assumptions.

## Status boundaries and owners

- S3 G07 config acceptance remains open until this mapping is adjudicated; this is not rejection of Temporal as the provisional read-only comparator.
- S2 Phase 8 remains `NOT APPROVED`; S4 remains `INCONCLUSIVE`; all 53 S4 policy selectors remain `NOT_RUN`; S5 remains gated.
- No acquisition, build/install, execution, test, waiver, S2/S3 acceptance, candidate winner/TOP, push, PR or merge was approved.
- Owner: Codex prepares the exact mapping and continues read-only source audit; GPT-PM adjudicates the mapping; operator retains legal/acquisition and sandbox-change decisions.

The evidence for the Codex response is `docs/sdlc/evidence/s3-temporal-g07-authorization-mapping-20261027.md`, which maps pinned server auth behavior and the pinned Python SDK/SDK-Core operation paths. It remains a proposal pending a new GPT-PM review.
