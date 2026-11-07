# S2 runner-claim reconciliation adjudication

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Declared base HEAD: `2da827be982d3f2d6f2adf152668af6ff8007f21`  
Request: `e73cabde-5580-4be5-9ad1-63f65521f347`  
Reply: `9f337b5f-04f6-4610-b453-3926ba4a6bc8`  
PM Bridge job: `3cbf606b-b4ea-4902-9ad6-f3a05958d807`  
Correlation: `correlated=true`; request payload hash `62b49ee34d9ae746e73e4177cd5419b06772fc478610f9d82b39777ef9f51ecc`.

## Verdict and core invariant

GPT-PM returned `MODIFY`: `S2-RC-M01` is a valid MAJOR and source correction is required.
The response considered supplied source context and prior review; it did not independently
verify the complete working diff or committed exact head.

`INDETERMINATE` terminalizes the original grant, but does not prove that its command had no
effects and does not authorize attempt+1. After a claim reached `EXECUTION_RESERVED` or may have
started a command, a successor attempt must remain blocked until a distinct authenticated
reconciliation establishes a disposition that explicitly permits continuation. Lease expiry and
a `WORKER_LOST` marker do not substitute for execution reconciliation. Retry authorization is a
separate action by the existing coordinator under current epoch, budget and policy.

## Finding

`S2-RC-M01 — ambiguous execution does not fence successor attempts` (**MAJOR, source correction
required**). Store terminalizes predecessor claims as `INDETERMINATE`, while normal lease and
execution grant admission did not require a distinct effect-resolution record before a later
attempt. This can permit attempt N+1 despite unresolved effects of attempt N; no duplicate effect
needs to be reproduced for this to be a valid contract defect.

## Required source boundary

The correction is confined to existing Store/Supervisor reconciliation and admission boundaries:

- A distinct `RECONCILED` event must bind the exact predecessor `grant_id`, `request_id`,
  `invocation_id`, `task_id`, `slot`, `attempt`, `epoch`, `run_id`, `service_generation`, and
  grant payload digest.
- It must include a unique durable `resolution_id`, closed outcome enum, evidence digest,
  authenticated actor/key identity, and a domain-separated signature over the complete record.
- Outcomes that leave effects unresolved or reject reconciliation keep the task blocked. At minimum,
  only evidence-backed `NO_EXECUTION_PROVEN` or `EFFECTS_RESOLVED` can become retry-eligible, with
  ordinary epoch/budget/policy checks still required.
- Store admission must enforce the block at lease acquisition, execution-grant basis, and claim,
  so a prior lease cannot bypass it.
- A generic `NOTE`, unsigned boolean, `INDETERMINATE` event, expired lease, or `WORKER_LOST`
  receipt is not reconciliation authority.
- Recovery remains separate from grant issuance: no implicit global reaper in `issue_grant` and
  no dispatcher-facing reaper or general reconciliation capability.
- No new scheduler, CLI, spool, broad dispatcher capability, or second assignment authority.

The existing production coordinator call site remains unidentified and `S2-DISPATCH-M01` remains
MAJOR/OPEN. Source corrections may proceed within this S2 boundary, but production integration and
the S2 code gate cannot be declared closed without that real source.

## Acceptance disposition

| Criterion | State | Owner | Next step |
|---|---|---|---|
| `S2-RC-M01` successor-attempt fence | OPEN — source correction required | Codex | Implement authenticated reconciliation and enforce all three Store admission guards |
| `S2-DISPATCH-M01` production coordinator | MAJOR / OPEN | Codex identifies; GPT-PM verifies | Find actual in-scope coordinator; if absent, retain blocker |
| `issue_grant` implicit global reaper | PROHIBITED | Codex | Keep recovery and grant issuance separate |
| S2 Phase 8 | NOT APPROVED | Codex coordinates; GPT-PM adjudicates | Complete remaining S2 code/evidence and exact-head gate |
| Restricted/unavailable selectors | 20 `NOT_RUN` | Codex preserves | Do not execute without changed authorization boundary |
| E5 signed inventory | OUTSTANDING | Operator signs; Codex collects permitted evidence | Do not fabricate attestation |
| S3 work | BLOCKED until S2 closure | Codex | Do not start S3 |

This decision authorizes no new service, scheduler, CLI, spool, migration, broad dispatcher
capability, tests, runtime action, provisioning, push, PR, or merge. The operator's earlier GO
authorizes autonomous S2 work but does not erase the stated project safety and approval gates.

