# S2 dispatch-owner admission-fence adjudication — 2026-10-29

## Correlated GPT-PM review

GPT-PM reviewed the revised non-secret provisioning plan and dispatch-owner source draft. The
request was `1da9e3cf-2321-4a24-8710-1b80348cdd6b`, job
`aec6fceb-86dd-4953-81e2-cb4f49847d08`, user turn
`5be19da9-703b-4cb5-b363-469cdf2d7fee`. The exact reviewed attachment did not include the later
local commit `978aa5b70c57113cb4e0533bfa6e2dd1c3f3a182`; this is design feedback, not exact-HEAD
source approval.

**Verdict: MODIFY.** The two MAJOR and two MINOR provisioning-plan findings recorded in
`s2-provisioning-plan-adjudication-20261029.md` were resolved in that candidate. GPT-PM identified
one new MAJOR: `S2-PROV-M03`, socket activation can reactivate a relay after an ambiguous Supervisor
RPC outcome. `Restart=no` does not disable an active `.socket` unit. The review did not find a
duplicate-acceptance defect or establish that duplicate execution occurs; the issue is that new
submissions could continue while the first result remains unknown.

Required design closure:

- Define which local refusals remain ordinary and which post-RPC outcomes are ambiguous.
- Stop future socket submissions after an unknown outcome, including a process crash/timeout path.
- Specify listener and queued-connection behavior during teardown and how a persistent fence blocks
  later service/socket activation.
- Reconcile by the exact `request_id` and complete instruction against Store's durable event and
  idempotency result before any separately authorized reopening or retry.
- Add synthetic tests for an ambiguous Supervisor completion followed by another connection. Do not
  activate the service or perform a real dispatch.

The review permitted continued non-secret design and source drafting only. It did not authorize
privileged provisioning, `/etc` writes, key work, migration, service activation, real dispatch, E5,
push, PR or merge. Existing Pub/Sub remains the assignment-intent transport; the owner relay is only
the authenticated ingress for one signed instruction and adds no scheduler or assignment authority.

## Codex remediation in progress

The new source draft changes the relay to require exactly one canonical frame followed by client
write-half-close. Local frame/signature/trust refusals happen before RPC and do not fence the relay.
After verified input crosses the Supervisor transport boundary, every unconfirmed outcome—including
error replies and response-binding failures—is treated conservatively as ambiguous. The relay sends
`reconciliation_required` when possible, then exits with code 75 without processing another
connection.

`vst-dispatch-owner.service` has a root `ExecStopPost` helper. The first draft wrote the persistent
latch and issued `systemctl --no-block stop`; independent code and reliability reviews found that
filesystem stalls or a failed latch write could leave the socket active. The corrected source first
stops the socket synchronously and confirms `ActiveState=inactive`, retrying indeterminate outcomes
with bounded subprocess timeouts and capped backoff while keeping the service stop hook alive. Only
then does it inspect `/etc` and persist the root-owned latch. `TimeoutStopSec=infinity` prevents
systemd from killing this hook while the stop barrier or persistence is unresolved. Both systemd
units and the unprivileged service loader refuse while a latch exists. The latch is not automatically
cleared. Reopening requires explicit Store/request-ID reconciliation and separately authorized root
recovery. A queued connection can remain in the kernel backlog until listener shutdown; no further
request is handled after the inactive state is confirmed. If latch creation fails, the socket is
inactive at that point, but no latch guards a later explicit start and cross-reboot safety is not
established; durable root-controlled `/etc` is required before any reboot or start. Recovery stops the socket and verifies it is inactive,
reconciles the Store record, then separately clears the latch and starts the socket.

Store's current implementation writes `DISPATCH_INTENT_ACCEPTED` and the
`supervisor_operations` idempotency result in the same transaction. Reconciliation must compare the
complete signed envelope, principal, generation, request ID, payload digest and stored result; then
inspect subscription/grant state. If the event exists, do not replay. If it is absent, a transport
error alone is not evidence of non-acceptance; any retry/replacement is an operator-owned action
after independent authorization and fresh checks of Store health, live owner/lease, preflight,
expiry and generation.

The initial source implementation passed 105 focused synthetic tests at commit
`cec0dbf3249b5734bdae52f644ac790e07d869f8`, but code/reliability review found a fail-open fallback.
That finding is being corrected in source and mapped test cases before a fresh test run and review.
No root helper, `/etc` path, or systemd unit was activated in WSL. Specialist re-review, focused
GPT-PM re-adjudication and exact-head final gates remain open. S2 remains NOT APPROVED and S3
remains unstarted.

The systemd contract is based on documented `ExecStopPost=` behavior (runs after unexpected service
exit and receives `$SERVICE_RESULT`, `$EXIT_CODE`, `$EXIT_STATUS`) and the documented `+` command
prefix (runs with full privileges despite unit-level `User=`, `Group=` and selected filesystem
restrictions): [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html),
[systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html). These
references support the source design only; no installed systemd version or unit behavior has been
validated in the selected WSL environment.
