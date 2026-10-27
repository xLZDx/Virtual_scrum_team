# Change 0471: Implement the S2 persistent manifest runner boundary

## What changed

- Added `tools/vst/runner_service.py`, a bounded Unix-socket service that accepts only signed
  manifest execution grants, verifies its fixed service generation and dispatcher peer, fetches
  the exact manifest from Supervisor, and calls the existing manifest runner.
- Added `tools/vst/supervisor_service.py`, a root-owned authenticated RPC boundary that pins
  dispatcher, runner, and signer peers by UID/GID, systemd cgroup and kernel peer pidfd; it
  exposes only the operations assigned to each peer and keeps Store credentials inside the root
  process.
- Added `tools/vst/execution_grant.py` and Supervisor issuance/verification for one-use,
  Ed25519-signed grants with a 30-second claim window and expiry covering the signed, bounded run
  deadline plus completion slack. Grants bind task, TestRun slot, attempt, story epoch, manifest,
  consumed run preflight, worker identity, resolved model/provenance, request, invocation, audience,
  and current service generation. Key material is read through fixed root-controlled paths and
  passed to OpenSSL by file path; private bytes are not placed in argv or environment.
- Added Store schema v5 append-only runner execution claims/events. Admission rechecks owner,
  epoch, manifest, lease, receipt slot, preflight and budget in one transaction before recording
  `PENDING`. The fixed runner daemon then atomically reserves the exact grant as
  `EXECUTION_RESERVED`, rechecking current generation, story epoch/owner, lease, deadline and
  budget immediately before the first command launch. Completion requires this reserved state,
  stores the exact validated receipt, and appends it to the ordinary receipt table/hash chain in
  the same transaction. Exact-grant status queries resolve uncertain claim RPC replies only
  within the original active service generation; they never reclaim work. A new generation turns
  predecessor `PENDING` and `EXECUTION_RESERVED` claims into terminal `INDETERMINATE` events,
  and never replays them. A lost reservation reply is ambiguous and cannot authorize a launch.
  If claim/reservation status is unavailable or shows an already reserved/otherwise ambiguous
  outcome, the runner sends a bounded refusal when possible and exits nonzero. Existing
  `Restart=on-failure` creates a new generation whose startup recovery terminalizes the
  predecessor claim. A reserve failure whose exact status still shows `PENDING` also fail-stops;
  this source path does not retry reservation in the same generation. By contrast, a claim
  failure followed by exact-shape `NOT_FOUND` for the same active generation is a normal refusal:
  no durable claim exists to recover, so it does not restart the service. `NOT_FOUND` after claim
  admission at the reserve boundary remains fatal.
  Any later run, signing, receipt, or completion exception after reservation confirmation but
  before the Supervisor confirms durable `COMPLETE` sends a bounded refusal and exits nonzero
  before the service can admit another request; exact durable `COMPLETE` replay remains safe, and
  ordinary pre-reservation refusals remain nonfatal.
- Added a source-only execution reconciliation boundary using the existing append-only schema-v5
  runner events. Any task with a nonterminal claim is blocked at `acquire_lease`, grant-basis
  issuance, and claim admission. A recovered `INDETERMINATE` claim whose predecessor was exactly
  `PENDING` is proven pre-spawn because launch reservation precedes every child; ordinary lease,
  retry, epoch, and budget checks still apply. `EXECUTION_RESERVED` and other may-have-started
  claims remain blocked until a distinct signed resolution. Only `INDETERMINATE` can transition to `RECONCILED`; the signed
  record binds the full canonical grant digest and grant/request/invocation/task/slot/attempt/epoch/
  run/service-generation identity, unique resolution ID, evidence digest, actor/key ID, predecessor
  state, and a closed outcome (`NO_EXECUTION_PROVEN`, `EFFECTS_RESOLVED`, `EFFECTS_UNRESOLVED`,
  or `RECONCILIATION_REJECTED`) plus its corresponding fixed operator attestation under
  `vst-runner-execution-resolution-v1` HMAC domain separation;
  `key_id` is the SHA-256 fingerprint of the configured operator HMAC key. Only the first two
  permit successor admission; `NO_EXECUTION_PROVEN` is valid only for predecessor `PENDING`. The
  operator HMAC attests that the evidence digest supports the stated outcome; evidence bytes are external and
  Store does not independently fetch or validate them. No actual operator-signed resolution is
  present. The in-process Supervisor/Store API is implemented, but no operator RPC, coordinator
  caller, or production dispatch path is added or claimed.
- Updated `tools/vst/runner.py` to require the grant-backed `ExecutionAuthority` for manifest
  execution and the fixed UID/GID worker helper rather than a `subprocess.Popen(user=...)` path.
- Added `tools/vst/runner_fence.py`, a root-only hash-chain manager fence that binds systemd
  `InvocationID`, `ControlGroup`, cgroup and lock inodes, and only removes verified empty command
  scopes. It fails closed on unknown/populated scopes and never kills predecessor work.
- Added fixed Supervisor, signer and runner systemd unit templates plus
  `tools/vst/systemd/README.md`. Added `tools/qa/install_wsl_runtime.ps1` to stream a bounded,
  exact-HEAD Git archive from the canonical checkout over WSL stdin without a drive mount or
  second checkout, including `docs/SANDBOX_SPEC.md` needed by runtime preflight. The Linux
  bootstrap verifies the bundle digest and allowlisted paths and extracts under a unique
  root-private per-attempt path. Before either installer mutates a fixed destination, it checks
  existing runtime files/units; exact prior artifacts are accepted only with matching HEAD and
  archive digest, while mismatched state is preserved and refused. A fresh transfer ID makes a
  failed extraction retryable without removing old staging state. Installers do not enable or
  start services. The worker helper clears ambient and effective/permitted/inheritable capability
  sets, reads them back, and refuses launch if any capability remains.
- Reconciled `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`, the implementation/design evidence, and
  `core/BACKLOG.md` with the source state, runtime-directory mode `0710`, and the remaining gates.
- Current-turn implementation follow-up fixed the runner config contract: `daemon_gid` is now
  required, type-checked, and pinned with the other fixed worker-boundary IDs before helper
  verification. Added `dispatch_authorized_manifest_run` as a library integration function; it
  requests a grant over authenticated Supervisor IPC and forwards only that grant to the runner
  socket. It is not a runnable production dispatcher, and no trusted coordinator caller identity
  or request source is currently established. The source alone therefore does not close dispatcher
  deployment acceptance.
- Reconciled the systemd runner stop timeout with its 1800-second maximum grant deadline and
  bounded post-run signer/Git work: grants allow a 30-second claim window plus 1800 seconds of
  execution and 90 seconds of completion slack; graceful stop allows 1900 seconds while keeping
  `SendSIGKILL=no`; failure to exit still cannot be recorded as a clean stop.
- Bounded signer IPC client/server reads to 10 seconds and complete 4-KiB-or-smaller JSON
  responses; stream responses are accumulated through EOF rather than assuming one `recv()` is
  complete. Disconnected-client writes no longer terminate the signer accept loop.
- Required completed Store startup reconciliation and verified event-chain integrity before
  idempotently consuming the service preflight record, so an integrity-locked Store cannot be
  mutated during Supervisor startup.
- Corrected all execution-grant budget checks to pass the task ID expected by the Store helper,
  rather than a SQLite row object; grant basis, claim, signer revalidation, and completion now use
  the same typed input.
- Resolved the correlated GPT-PM architecture MODIFY for claim ambiguity (request
  `7f9f9a30-4f93-4df9-9b5f-6f354eac58c1`, reply
  `bec8fd4b-c921-43bf-a697-63922b9d7970`) by adding the append-only
  `EXECUTION_RESERVED` transition, an exact-grant status query and a single compare-and-set
  reservation operation available only to the fixed runner service peer. The claim window gates
  only the initial one-time claim; a later same-generation reservation still requires the grant's
  full remaining execution window and current lease/epoch/budget. A timeout before any launch
  returns no receipt; the runner never completes an unreserved grant. Restart recovery marks
  predecessor claims terminal instead of reclaiming them.
- The separate dispatcher integration dependency remains open: GPT-PM did not authorize a new
  CLI, queue or scheduler, and no in-repository production coordinator call site was found.
  `dispatch_authorized_manifest_run` remains a library integration function, not a runnable
  dispatcher. Next: name and authorize a trusted coordinator identity/request source; Codex then
  binds it to this fixed runner and Supervisor boundary. S2-M01 remains open until this is closed;
  do not invent an authority path or treat the reservation implementation as integration evidence.
- A focused GPT-PM adjudication (request `1ff3b849-6180-4cb3-83ea-0eab47e56a3e`, reply
  `762291a2-5c34-470d-8b98-9a38a4cfc5ee`, correlated PM Bridge job
  `0594bd8d-c06a-4c3c-9970-ed44ca2c1a0d`) rejected invoking the global Store lease reaper as an
  implicit `issue_grant` side effect: grant issuance must not gain authority to reconcile unrelated
  tasks. Keep recovery under trusted coordinator or existing Supervisor-owned recovery authority;
  if a marker is missing, grant issuance must refuse. GPT-PM also confirmed that missing production
  coordinator source/call site blocks persistent-runner production-path acceptance. No new
  scheduler, CLI, spool, reaper RPC, or assignment authority is approved. Full request, findings,
  and acceptance disposition are retained in
  `docs/sdlc/evidence/s2-persistent-runner-lease-dispatch-gptpm-review-20261027.md`.
- After the reconciliation/fail-stop source freeze, the designated `functional-test-reviewer` ran
  four authorized focused groups: persistent runner 38, E1 32, E2 38, and E6 DiffGate 22; total
  **130 passed, 0 failed, 0 skipped**. New cases exercise every successor guard, signed safe/unsafe
  reconciliation outcomes, PENDING pre-spawn recovery, tampered records, duplicate resolution IDs,
  post-reservation fail-stop, exact COMPLETE replay, and nonfatal exact `NOT_FOUND`. The report is
  `docs/sdlc/evidence/s2-runner-reconciliation-focused-tests-20261027.md` (SHA-256
  `cacdfa3e857aae72ae23bd2e2bed2c591a168ff5126110e3c449bc98153b13e2`). It explicitly does not
  prove service socket framing, daemon exit, systemd restart, or operator-signed resolution; those
  remain NOT_RUN/not present.

## Why

Earlier S2 source supplied cgroup cleanup primitives but no persistent production entry point
binding actual manifest runs to one stable delegated service parent across process replacement.
The service contract connects execution to a root-owned grant issuer, current Store authorization,
one-run durable claim, and a manager-mediated lifecycle fence while preserving refusal behavior
when identity, authority, or cleanup evidence cannot be established.

## Affected contracts and paths

- `tools/vst/runner.py`, `tools/vst/signer.py`, `tools/vst/store.py`, `tools/vst/supervisor.py`
- `tools/vst/execution_grant.py`, `tools/vst/runner_fence.py`, `tools/vst/runner_service.py`,
  `tools/vst/supervisor_service.py`
- `tools/vst/systemd/`, `tools/qa/worker_exec.c`,
  `tools/qa/install_wsl_worker_helper.sh`, `tools/qa/install_wsl_runner_runtime.sh`
- `tools/vst/schemas/README.md`, `docs/S2_POSIX_WORKER_CGROUP_DESIGN.md`,
  `docs/sdlc/evidence/s2-persistent-runner-service-design-20261027.md`, `core/BACKLOG.md`,
  `core/LESSONS_LOG.md`, `governance/DOCUMENT_REGISTRY.md`

## Verification state

- Code and documentation are present only in the canonical `D:\Repo\Virtual_scrum_team`
  checkout. No sprint worktree or alternate checkout was created.
- This change record describes a working-tree implementation based on repository HEAD
  `2da827be982d3f2d6f2adf152668af6ff8007f21`; the working tree was already dirty before this
  implementation. The final diff/head must be recorded after functional tests and specialist
  review.
- Four approved focused test groups were executed after the reconciliation/fail-stop source freeze
  and passed 130 selected IDs as described above. No full suite, check, build, migration, installer,
  bootstrap, account/key provisioning, systemd enable/start, service-boundary/restart runtime, or
  restricted process/crash/recovery/mutation/E8/policy scenario was executed. Store schema v5 remains
  source-only and has not been applied to a database.
- Before the reservation/state-machine follow-up, the designated functional-test reviewer ran
  four bounded commands on the dirty diff based on HEAD `2da827be982d3f2d6f2adf152668af6ff8007f21`:
  11 new persistent-runner cases, 32 E1, 38 E2, and 22 E6; aggregate 103 passed, 0 failed,
  0 skipped. That result is superseded by the later 130-ID reconciliation rerun above. The tracked diff hash was
  `ec755e99e2c9dcb6f35b6c89ab5be21d8650f19179eed98e6c19523b772bb5e5`. Evidence and exact
  commands are in `docs/sdlc/evidence/s2-persistent-service-focused-tests-2da827be-20261027.md`.
  These results cover the grant library handoff, config, Store preflight guard, signer framing
  and duplicate-COMPLETE Store behavior, but not the new claim-status/reservation transition or
  exact Supervisor RPC replay shape below. They are not exact committed-head evidence.
- The earlier 92-pass selector record predates the final focused rerun and is superseded for
  those selectors; its provenance remains in
  `docs/sdlc/evidence/s2-safe-functional-selectors-2da827be-20261027.md`.
- The 1900-second unit stop bound is a source-only contract change and has not been exercised
  against systemd or an in-flight run.
- Signer timeout, fragmented response, oversized response, disconnect handling, Store integrity
  refusal for preflight consumption, config validation, grant basis and claim/completion Store
  paths were included in the 103-pass run above. The SQLite row/task-ID defect found during an
  earlier diagnostic run was corrected before that successful rerun.
- Database review identified a duplicate-COMPLETE replay contract mismatch: Store and the
  in-process Supervisor API return the stored receipt object directly, while
  `ExecutionAuthority.authorize_and_claim()` expects the explicit
  `{"state":"COMPLETE","receipt":...}` form. The authenticated Supervisor RPC now wraps only
  a non-null completed receipt in that form; a new PENDING claim still returns `null`. Store and
  in-process Supervisor return shapes remain unchanged for compatibility. The focused replay case
  is included in the subsequent 130-pass functional rerun; exact-diff database/reliability review
  remains separate.
- The subsequent correlated GPT-PM resolution added claim-status and reservation semantics; that
  source follow-up has not been tested or reviewed yet. Its change is described above.
- Static reconciliation found that direct `/mnt/d` source access conflicts with the required
  disabled-automount E5 profile. The host-to-WSL bundle handoff addresses that source path conflict
  in code, but the handoff/retry flow is unreviewed and unexecuted; it is not deployment evidence.
- Handoff retries use a fresh per-invocation transfer ID, so a failed extraction leaves its
  root-private `/run` staging directory intact without blocking a later invocation. Exact prior
  runtime/helper/unit outputs are validated and reused; any mismatched or unrelated fixed path is
  refused before replacement. For a refusal, preserve host state and collect read-only evidence:

  ```sh
  # Replace this with the attempted commit ID.
  HEAD=0123456789abcdef0123456789abcdef01234567
  sudo stat -c '%F %U:%G %a %n' \
    "/opt/vst-runtime-$HEAD" /opt/vst-runtime \
    /etc/systemd/system/vst-supervisor.service \
    /etc/systemd/system/vst-signer.service \
    /etc/systemd/system/vst-runner.service \
    /usr/local/libexec/vst-s4-worker-exec
  sudo readlink /opt/vst-runtime
  sudo sha256sum \
    "/opt/vst-runtime-$HEAD/tools/vst/systemd/vst-supervisor.service" \
    "/opt/vst-runtime-$HEAD/tools/vst/systemd/vst-signer.service" \
    "/opt/vst-runtime-$HEAD/tools/vst/systemd/vst-runner.service" \
    /etc/systemd/system/vst-supervisor.service \
    /etc/systemd/system/vst-signer.service \
    /etc/systemd/system/vst-runner.service \
    /usr/local/libexec/vst-s4-worker-exec
  ```

  Do not remove or overwrite a mismatch; the operator owns any later host-state repair
  authorization. A matching prior exact artifact is resumed by rerunning the host script with the
  same HEAD; each invocation transfers into a new unique staging path.
- Prior GPT-PM response `c92f2614-885e-4e44-9160-c23650f80cb9` accepted the architecture at
  design-only scope; it is not approval of this implementation. Exact-diff reviews and a fresh
  correlated GPT-PM decision remain required.
- Existing process-kill, crash/recovery, mutation and restricted policy scenarios remain
  `NOT_RUN`. The WSL requirement to disable automount while consuming source from the canonical
  `/mnt/d/Repo/Virtual_scrum_team` path still needs safe host-side qualification; no alternate
  checkout is permitted.

## Decision and ownership

- Codex owns source reconciliation, implementation fixes, documentation and coordination.
- `functional-test-reviewer` and `e2e-runner` own the post-coding focused test design/execution
  and any allowed runtime run. Their results must name exact source/test revisions.
- Fresh relevant specialist agents own read-only review of the final diff; GPT-PM owns exact-head
  architecture/final adjudication; the operator owns any host provisioning or attestation that
  actually requires operator authority.
- S2 is not closed by source implementation. Do not start S3 until S2 acceptance is completed.

Executor: Codex
