# Change 0518: fence S2 dispatch-owner admission after uncertain completion

## Why

GPT-PM identified that `Restart=no` does not disable a separate active systemd socket unit. After a
Supervisor call whose durable result is unknown, the socket could start the relay again and admit a
later instruction before the first request had been reconciled. The exact correlated review and
required lifecycle design are recorded in
`docs/sdlc/evidence/s2-admission-fence-adjudication-20261029.md`.

## What changed

- `tools/vst/dispatch_owner_client.py` now distinguishes a local signed-envelope refusal from any
  unconfirmed result after the transport call starts. Transport errors, explicit error replies,
  malformed responses and response-binding failures become `DispatchOutcomeUnknown`; no exception
  is interpreted as proof that a durable intent was not accepted.
- `tools/vst/dispatch_owner_service.py` requires a single bounded canonical frame followed by EOF
  (client write-half-close), refuses trailing bytes before Supervisor RPC, returns
  `reconciliation_required` for unknown results when possible, and exits with status 75 without
  accepting another connection.
- `tools/vst/dispatch_owner_latch.py` is a root-only systemd `ExecStopPost` helper. On every service
  termination it atomically persists a root-owned admission latch under `/etc/vst-runner`, then
  requests that systemd stop the socket unit. It records bounded systemd termination metadata and
  logs latch/socket-stop outcomes. The unprivileged relay never writes this file.
- Both dispatch-owner systemd units use `ConditionPathExists=!` for the latch, and service config
  loading independently refuses while the latch exists. The service unit invokes the root helper
  with the documented `+` command prefix. The runtime allowlist includes the helper.
- The service contract, deployment README, non-secret provisioning plan, project state/backlog,
  decision log and lessons log now specify service/socket lifecycle, failure classes, queued
  connection behavior, exact Store reconciliation and explicit reopening.

## Contracts and decisions

The local owner relay remains a signed-instruction ingress only. Pub/Sub and the existing Store and
Supervisor remain the sole assignment/delivery authorities. Local framing, canonical-JSON,
signature, expiry, principal and trust-registry failures happen before Supervisor RPC and do not
fence admission. Once a verified envelope crosses that RPC boundary, an unconfirmed result is
non-approving and stops the relay. There is no automatic retry or latch clearing.

Before independently authorized recovery, inspect the exact signed request ID in the verified
`DISPATCH_INTENT_ACCEPTED` event and matching `supervisor_operations` idempotency result; compare the
complete envelope, principal, generation and digest; and inspect subscription/grant state. Store
commits the event and idempotency result transactionally. Do not replay a present event. Absence is
not inferred from an RPC error; any retry or replacement requires fresh root/Store checks and a
separately authorized recovery. Stop and verify the socket is inactive before clearing the latch;
then explicitly reopen it after reconciliation.

## Verification state

- Tests, checks, builds and systemd validation: `NOT_RUN` in this change.
- Runtime provisioning, `/etc` writes, root helper invocation, service/socket activation, migration,
  real dispatch, key operation, E5, push, PR and merge: not performed.
- `functional-test-reviewer` updated focused test sources for the new EOF and fail-stop contract;
  they remain unexecuted pending the e2e-runner phase.
- Source is uncommitted pending coding freeze, designated test author/executor, specialist review,
  fixes and exact-head GPT-PM code/plan gates.

## Acceptance and ownership

This change resolves the draft for `S2-PROV-M03`; it does not close the finding. Required synthetic
coverage includes an ambiguous Supervisor completion followed by another connection, no RPC for a
trailing frame or non-half-closed request, persistent root latch behavior, startup refusal with a
latch, and explicit reconciliation/reopen ordering. Codex owns source and evidence; the
functional-test-reviewer/e2e-runner own mapped test authoring/execution after source freeze; GPT-PM
owns focused architecture adjudication; the operator owns any separately authorized privileged
recovery or production provisioning. `S2-DISPATCH-M01` remains MAJOR/OPEN, S2 remains NOT APPROVED,
and S3 remains unstarted.

The functional-test-reviewer mapped these focused identifiers to M03/M01 (authored, not run):

- `test_s2_owner_service_accepts_only_one_bounded_canonical_instruction_frame`
- `test_s2_owner_service_refuses_trailing_second_frame`
- `test_s2_owner_service_refuses_request_without_eof_before_supervisor_rpc`
- `test_s2_owner_service_requires_reconciliation_after_ambiguous_supervisor_outcome[timeout|explicit-error|malformed-result|response-binding-mismatch]`
- `test_s2_dispatch_owner_loader_refuses_existing_admission_latch`
- `test_s2_admission_latch_creation_is_exclusive_durable_root_root_and_0644`
- `test_s2_latch_main_requires_root_before_persistence_or_socket_stop`
- `test_s2_latch_main_stops_dispatch_socket_even_when_persistence_fails`
- `test_s2_dispatch_owner_systemd_units_share_latch_condition_and_exec_stop_post`
