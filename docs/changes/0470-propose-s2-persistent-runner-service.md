# Change 0470: Propose persistent S2 runner service boundary

## What changed

- Revised the proposal after GPT-PM's correlated `MODIFY` response (request
  `0ea02a82-72ba-44dc-a431-213d99bf8192`, reply `62890e6f-0fc5-432c-8bde-ba46be1fad8b`, job
  `411b4d13-4c15-400c-85f6-54c8f7db289b`) identified three MAJOR findings and one MINOR.
- Added the predecessor lifecycle fence and explicitly restricted supported replacement to one
  manager-controlled unit; specified root-controlled `ExecStartPre=+...` and
  `ExecStopPost=+...` hooks, ordering, root-owned generation-bound durable records, and explicit
  first-install `BOOTSTRAP_EMPTY`; defined grant issuer, current authorization checks, signature domain,
  key custody/rotation/revocation and fail-closed trust-root behavior; and replaced cgroup-only
  enforcement with a dedicated daemon OS identity, daemon-only execution capability, and a
  required signed grant plus durable Store `PENDING` claim before child creation.
- Clarified that these are design requirements only. Implementation, host/key provisioning,
  runtime evidence, tests and S2 acceptance remain open pending focused reviews and a fresh
  GPT-PM adjudication.
- Added an implementation-ready design proposal for a foreground manifest-bound runner daemon
  hosted by one persistent delegated systemd unit.
- Documented current call boundaries, options, peer/request contract, idempotency and recovery
  requirements, failure behavior, rollout/rollback, and verification ownership.
- Updated the first draft after independent architecture and security reviews identified missing
  trusted manifest authorization and duplicate-execution prevention: the revision requires a
  signed, manifest-bound execution grant and an atomic durable `PENDING` state before dispatch.
- Updated the second draft after re-review identified reusable-grant replay and an underspecified
  direct-library boundary: the grant now binds unique grant/request/invocation IDs and audience,
  while the signer is required to validate peer cgroup against the configured service unit.
- Added a third-round fail-closed requirement to bind `SO_PEERCRED` to `SO_PEERPIDFD` when reading
  peer cgroup identity and to keep the daemon in the systemd-managed unit cgroup; primary
  systemd/kernel references are recorded in the design note.
- GPT-PM returned correlated `MODIFY` (request `0ea02a82-72ba-44dc-a431-213d99bf8192`, reply
  `62890e6f-0fc5-432c-8bde-ba46be1fad8b`, job `411b4d13-4c15-400c-85f6-54c8f7db289b`): three
  MAJOR findings on predecessor fencing, grant issuer/key trust, and direct-library/same-UID
  enforcement, plus one MINOR on replacement-mode identity. The design now defines one supported
  systemd replacement mode with a predecessor stop/fence record; a single Supervisor/Store grant
  authority, current-state checks, separate signing/verification trust roots and key lifecycle;
  and a dedicated daemon OS identity whose capability, signed grant and durable `PENDING` claim
  are required before child creation. Implementation and runtime evidence remain open; design
  adjudication is recorded below.
- Fresh focused architecture and security reviews found no remaining design-level issue across
  M01-M03/N01. GPT-PM then returned correlated `ACCEPT — DESIGN ONLY` under request
  `4c2b6ea5-7de8-4d08-9d24-5c24e38d4b76`, reply `c92f2614-885e-4e44-9160-c23650f80cb9`, job
  `7e29045d-0ef8-433c-a4ab-f3ed987fe77d`, closing those four findings at design level while
  preserving S2-RF-M01 deployment/runtime evidence as open. PM identified non-blocking MINOR
  `S2-RF-SVC-N02` for inconsistent changed-parent failure wording; the design failure table is
  reconciled, and a focused verification is pending. Evidence is in
  `docs/sdlc/evidence/s2-persistent-runner-service-gptpm-review-20261027.md`.

## Why

S2's code-level shared lock only reconciles scopes beneath the current process's delegated cgroup.
The current repository exposes `run_manifest_commands` as a library call and has no identified
persistent service entry point. A transient/no-op unit does not prove that real calls share a
stable delegated parent across process replacement.

## Affected contracts and paths

- `tools/vst/runner.py` (`run_manifest_commands`, `_DelegatedCgroup._runner_parent`)
- `tools/vst/signer.py` (`AuthenticatedSigner` peer-authenticated Unix socket pattern)
- `tools/vst/supervisor.py` (`Supervisor.start_worker` callback boundary)
- `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`
- `docs/sdlc/evidence/s2-persistent-runner-service-design-20261027.md`
- `core/BACKLOG.md`

## Verification state

- Static source and repository-record inspection only; no source code, tests, checks, builds,
  provisioning, migration, or systemd unit was changed or run.
- GPT-PM accepted the corrected architecture at design level only. The proposal is not
  implemented, provisioned, or runtime-proven. S2 remains `NOT APPROVED`; restricted selectors
  remain `NOT_RUN`.
- Architecture review: two MAJOR and one MINOR findings were returned. Security review returned
  two MAJOR findings. The second review round returned a MAJOR for signed-grant replay and kept
  direct-library production enforcement open; both were addressed in the third draft. A third
  review round identified peer PID-reuse and same-UID service-membership constraints; the design
  now requires peer-pidfd binding and cites systemd's delegation boundary. The earlier scoped
  final re-review found no remaining issue in that narrower scope, but GPT-PM then returned the
  correlated `MODIFY` with three MAJOR and one MINOR. Fresh focused `architect` and
  `security-reviewer` follow-ups (GPT-6 Luna / medium) reviewed M01-M03/N01 corrections and found
  no remaining design-level issue. GPT-PM's subsequent correlated `ACCEPT — DESIGN ONLY` closed
  those findings and added non-blocking clarification N02; the changed-parent failure wording was
  corrected, with focused PM verification pending. Reviewers and PM retain actual systemd hook
  credentials/directive support, daemon enforcement, key provisioning, and runtime behavior as
  unverified. No tests/checks were run; runtime evidence requires later implementation and
  provisioning.

## Decision and ownership

- Preferred direction: a bounded local Unix-socket daemon that accepts only manifest-bound
  requests and calls the existing runner library inside a stable delegated service cgroup.
- Current status is `ACCEPTED — DESIGN ONLY`; GPT-PM approved the architecture for future,
  separately reviewed implementation. Focused verification of N02 wording is pending, and
  implementation remains gated on the S2 workflow and separate code review. Codex owns in-repository design and implementation preparation; GPT-PM owns architecture
  adjudication; operator owns host service provisioning/authorization; functional-test-reviewer
  and e2e-runner own post-code tests and runtime evidence.

Executor: Codex
