# Change 0351 — Record provisional Temporal selection and withheld acquisition

## Summary

- Recorded GPT-PM's correlated decision to select Temporal provisionally as the sole S3 durable-engine comparator.
- Kept BMad Loop as the separate coding-agent-loop comparator and retained the hand-written VST worker in the three-way plan.
- Recorded explicit approval for continued read-only audit while marking acquisition, build/install and execution `NOT APPROVED`.
- Assigned all nine S3 closure gates to the project's accountable owners and the appropriate execution roles.

## Correlation

- Request: `b681dfc9-0cf7-4231-9a6f-ea034de54f76`.
- Correlated reply: `2541471a-a991-51ed-85e0-cda5691ba9a3`.
- Job: `7e20129a-7834-4214-97ad-04e5755ebc3b`.
- Verdict: **CONDITIONAL SELECTION — ACQUISITION NOT APPROVED**.

## Exact selected pins

- Temporal server `v1.32.1`: `af08a5e5f2dd40f545f2afac7780daaa6987001e`.
- Temporal Python SDK `1.34.0`: `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.
- Rust SDK-Core gitlink `e163abd6dc19040064986a63c8b8cf4756ffd320` (PM-reported; current browser audit independently verified the submodule URL, not this gitlink SHA).
- BMad Loop `v0.13.2`: `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`, separate comparator.

## Closure gates and owners

| Gate | Missing prerequisite | Accountable owner | Next action |
|---|---|---|---|
| S3-G01 | Exact-version authoritative license/notice for `nexus-proto-annotations@v0.1.0`, plus dependency license closure. | Operator for legal determination; Codex for evidence. | Obtain exact-version terms/maintainer evidence; keep status NOT_VERIFIED meanwhile. |
| S3-G02 | Feature/build-resolved dependency inventory and source/artifact provenance. | Codex. | Prepare locked SBOM and reproducible provenance dossier. |
| S3-G03 | Build/runtime profile, Go 1.26.8 handling, SDK/server compatibility and network/provider needs. | Codex; GPT-PM architecture adjudication. | Prepare compatibility/build design for review. |
| S3-G04 | Separate acquisition authorization and quarantined location. | Operator. | Record decision only after G01–G03 close. |
| S3-G05 | S2 mandatory acceptance remains NOT APPROVED. | Operator accountable; Codex coordinates; GPT-PM adjudicates. | Reconcile permitted evidence and retain prohibited cases as NOT_RUN. |
| S3-G06 | Fresh signed S2 sandbox probe for the intended run. | Operator for attestation; Codex binds evidence. | Validate boundary and run-bound signatures after policy gates. |
| S3-G07 | VST-specific Temporal topology, auth, persistence, egress, STOP/fence and receipt authority. | Codex; GPT-PM architecture adjudication. | Prepare architecture and threat-flow. |
| S3-G08 | Authorized same-fixture functional/replay/STOP/budget plan and runtime evidence. | Codex coordinates; designated test roles execute after gate. | Specify falsifiable scenarios and execute only after prerequisites. |
| S3-G09 | Separate candidate execution decision. | Operator. | Record only after G01–G08 close. |

## Acceptance boundary

The operator's autonomous-development GO does not supply the exact-version legal determination or separate acquisition/execution decisions. No candidate source/artifacts were acquired, downloaded, built, installed or run. This does not assign a final worker winner or “TOP”; S2, S3 and S4 gates remain open. The PM transport's generic push/CI instructions do not override repository policy; no push, PR or merge is authorized by this record.

## Attribution

- Accountable task owner: operator under the delegated sprint request.
- Read-only audit, coordination and record: Codex.
- Architecture/gate adjudication: GPT-PM.
