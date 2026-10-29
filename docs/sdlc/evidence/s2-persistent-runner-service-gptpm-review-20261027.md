# S2 persistent runner service GPT-PM design review

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Review target implementation reference: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`  
Request: `4c2b6ea5-7de8-4d08-9d24-5c24e38d4b76`  
Reply: `c92f2614-885e-4e44-9160-c23650f80cb9`  
Job: `7e29045d-0ef8-433c-a4ab-f3ed987fe77d`  
Focused N02 verification request: `d43c1542-f603-4ad4-a961-9b81d5c4df6d`  
Reply: `3a49c0fa-66c1-434d-9de5-93e26dd1f723`  
Job: `c0938a8b-5a9b-4f65-a0c0-bb14566fc69a` (`succeeded`, correlated)  
Prior decision: `MODIFY`, request `0ea02a82-72ba-44dc-a431-213d99bf8192`, reply
`62890e6f-0fc5-432c-8bde-ba46be1fad8b`.

## Decision

GPT-PM returned **`ACCEPT — DESIGN ONLY`** for the revised persistent runner architecture,
closing prior findings `S2-RF-SVC-M01`, `S2-RF-SVC-M02`, `S2-RF-SVC-M03`, and
`S2-RF-SVC-N01` at design level. The decision reports zero remaining design BLOCKERs and zero
design MAJORs. It does not approve implementation, provisioning, runtime probes, tests, host
changes, waivers, S2 acceptance, S3 work, push, PR, merge, or deployment.

The decision preserves the distinct parent finding `S2-RF-M01` as open until deployment/runtime
evidence proves the stable service-parent lifecycle. S2 Phase 8 remains `NOT APPROVED`.

## Finding dispositions

| Finding | Severity | Design disposition | Remaining qualification |
|---|---|---|---|
| `S2-RF-SVC-M01` predecessor lifecycle fence | MAJOR | CLOSED — DESIGN | Exact systemd manager, directives, helper credentials, ordering, durable record behavior, and effective cgroup lifecycle need independent host qualification. |
| `S2-RF-SVC-M02` grant authority and replay | MAJOR | CLOSED — DESIGN | Ed25519 issuance and Store claim code are in progress; migration, authenticated Supervisor IPC, key lifecycle provisioning, tests, and runtime remain outstanding. |
| `S2-RF-SVC-M03` direct-library/signer bypass | MAJOR | CLOSED — DESIGN | Direct manifest-library calls now require an execution-authority object, but daemon-bound socket construction, signer peer PIDFD/cgroup checks, and runtime proof remain outstanding. |
| `S2-RF-SVC-N01` replacement-mode ambiguity | MINOR | CLOSED — DESIGN | Supported replacement is limited to one unit and normal in-unit restart; host reboot or alternate mode requires separate bootstrap. |
| `S2-RF-SVC-N02` changed-parent failure wording | MINOR | CLOSED — DESIGN ONLY | Focused GPT-PM verification confirmed the changed-parent rule, failure-table consistency, unknown/populated-scope refusal, failed-start handling, and scope limits; no correction remains. |

## Evidence and limitations

Focused GPT-PM verification request `d43c1542-f603-4ad4-a961-9b81d5c4df6d`, correlated reply
`3a49c0fa-66c1-434d-9de5-93e26dd1f723`, job `c0938a8b-5a9b-4f65-a0c0-bb14566fc69a`
closed N02 at design level. GPT-PM confirmed the changed-parent rule, failure-table consistency,
unknown/populated-scope refusal, failed-start handling, and scope limits; no correction remains.

The correlated reply states that the revised proposal provides manager-mediated generation
fencing; a Supervisor/Store-issued signed grant tied to current durable authority; and a dedicated
daemon execution boundary requiring a verified grant and pre-dispatch Store claim. It separately
states that proposed systemd directives, privileged hooks, kernel interfaces, identities, and
Store integration had not been implemented or qualified when the reply was issued. Since then,
Codex began source implementation of Ed25519 grant issuance, direct-library authorization, and
the additive Store claim schema; none of that source has yet been tested, migrated, wired to a
service IPC, or qualified on a provisioned host.

The initial response identified `S2-RF-SVC-N02` as a non-blocking clarification because the main
design allowed a changed delegated parent only after a verified empty predecessor fence while the
failure table said a changed parent must always remain unavailable. Codex updated the failure-table
row in `s2-persistent-runner-service-design-20261027.md` to permit the transition only after the
verified fence and fresh identity/admission checks; unknown or populated scopes remain unavailable.
The focused reply above confirms this correction and closes N02 at design level only.

The review was design-only. At decision time, no source code, tests, checks, systemd unit, account,
key, or host state was included in or validated by this decision. Source implementation is being
handled separately. The 20 restricted/unavailable S2 selectors remain `NOT_RUN`; Windows ACL/Job
Object cleanup acceptance and fresh signed E5 inventory remain open.

Owner: Codex records the decision and continues S2 design/implementation preparation; GPT-PM owns
architecture adjudication; the operator owns eventual host/key provisioning and reserved runtime
authorization; designated test roles own tests after all in-scope coding is complete.

Next: implement only the accepted design in the canonical checkout, complete all S2 coding before
the designated test/review phase, then obtain host-runtime evidence and a fresh exact-head GPT-PM
gate before delivery actions. Do not start S3 before S2 closes.
