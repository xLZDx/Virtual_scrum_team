# S2 persistent-runner lease and dispatch adjudication

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Declared code HEAD: `2da827be982d3f2d6f2adf152668af6ff8007f21`  
Review request: `1ff3b849-6180-4cb3-83ea-0eab47e56a3e`  
GPT-PM reply: `762291a2-5c34-470d-8b98-9a38a4cfc5ee`  
PM Bridge job: `0594bd8d-c06a-4c3c-9970-ed44ca2c1a0d`  
Correlation: `correlated=true`; request hash `fa0d72a98ac700b519ed544981448e82800cf4277bf9b41eea5d72479ae651c9`.

## Verdict

`MODIFY`. GPT-PM found 0 BLOCKER and 2 MAJOR acceptance gaps. The response adjudicated
the submitted source description and prior context; it explicitly did not independently verify
the current checkout, HEAD, or dirty-diff fingerprint. It authorized no code implementation,
tests, runtime execution, migrations, provisioning, restricted selectors, push, PR, or merge.

## Decisions

1. Do not call the global `supervisor_reap_and_mark` from `issue_grant`. Grant issuance must
   remain side-effect-free with respect to unrelated tasks. Lease reconciliation belongs to
   trusted coordinator or existing Supervisor-owned recovery authority. A missing lease marker
   must produce a non-approving result such as `RECOVERY_REQUIRED`.
2. The absence of an identified production coordinator call site is a blocker for persistent
   runner production-path acceptance. Do not invent a coordinator, scheduler, CLI, queue, spool,
   or second assignment authority.
3. Preserve the distinction between a `PENDING` claim, `EXECUTION_RESERVED` with uncertain
   outcome, exact `COMPLETE` replay, expired lease, required loss marker, and a separately
   authorized later attempt. Lease expiry alone never authorizes replay or attempt advancement.

## Findings and disposition

- `S2-LEASE-M01` — **MAJOR**: invoking the global reaper as a grant-issuance side effect would
  expand the dispatcher request's authority to reconcile unrelated tasks. Keep recovery separate.
- `S2-DISPATCH-M01` — **MAJOR, OPEN**: `dispatch_authorized_manifest_run()` is a library helper,
  and no actual production coordinator source/call site was identified in the supplied/current
  repository scope. An existing in-scope coordinator must be identified and integrated through
  the bounded authenticated interface, or production dispatch remains incomplete.
- Lost-claim/reply protocol: retain the previously directed `EXECUTION_RESERVED` correction;
  unresolved reservation is not replayable. The focused review does not close its functional or
  runtime evidence requirements.

## Acceptance state

| Criterion | State | Remaining evidence/action | Owner | Next step |
|---|---|---|---|---|
| Grant issuance does not perform unrelated recovery | Decision: retain boundary | Confirm source contract and regression coverage; do not add implicit reaper | Codex | Keep `issue_grant` scoped to existing authority |
| Lost execution outcome is never automatically replayed | Design direction retained; runtime open | Exact final-diff functional and allowed runtime evidence | Codex coordinates; designated test roles execute | Continue only permitted verification after coding freeze |
| Production coordinator invokes the runner | OPEN / NOT IDENTIFIED | Actual existing coordinator source and durable assignment identity | Codex | Search only this repository; if absent, preserve blocker |
| S2 Phase 8 | NOT APPROVED | All remaining S2 evidence, exact-diff reviews and final gate | Codex coordinates; GPT-PM adjudicates | Keep S2 open; do not start S3 |
| Restricted selectors | `NOT_RUN` | No authorization to execute them in this reply | Codex | Preserve exact `NOT_RUN` status |

