# Change 0510 — Build the constrained S2 Store-backed pub/sub coordinator

## Why

The operator confirmed the production coordinator and authenticated assignment caller do not exist
and directed Codex to create the bounded path. GPT-PM's correlated decision accepted source
implementation only under the constraints in
`docs/sdlc/evidence/s2-pubsub-architecture-adjudication-20261028.md`. Store-backed pub/sub avoids
introducing a general broker or assignment authority while letting the coordinator forward an
exact already-authorized intent.

## What changed

- `tools/vst/store.py`: schema-v6 closed event kind; gated v3–v5 event-table upgrade; atomic
  `DISPATCH_INTENT_ACCEPTED` write and idempotency record; validated replay lookup; generation- and
  audience-bound HMAC cursor; grant basis checks the exact owner and derived lease ID.
- `tools/vst/supervisor.py`: narrow owner intent admission, filtered replay/subscription, current
  authority revalidation, and root-config-derived model provenance for exact grant forwarding.
- `tools/vst/supervisor_service.py`: role-limited owner submit, dispatcher subscription, and
  dispatcher grant-forward operations; root-owned principal mapping; strict response contracts.
- `tools/vst/dispatcher_service.py` and `tools/vst/systemd/vst-dispatcher.service`: fail-stop
  at-least-once subscriber that forwards one accepted intent through the existing runner boundary;
  cursor advances only after a structurally valid complete receipt.
- `tools/vst/runner_service.py`: authorized-grant forwarding contract, bounded timeout, and receipt
  binding to the dispatched grant.
- `tools/qa/install_wsl_runtime.ps1` and `tools/qa/install_wsl_runner_runtime.sh`: include the
  dispatcher module/unit in the immutable runtime artifact.
- `tools/vst/schemas/README.md`, `tools/vst/systemd/README.md`, the proposal, decision log, backlog,
  state, and this evidence record: document accepted source scope and the still-open gates.

## Decisions and invariants

- Transport is the existing hash-chained Store event log plus Supervisor-filtered AF_UNIX delivery.
  There is no Redis/NATS/Kafka/RabbitMQ, separate queue/spool, task listing, work selection, task or
  lease creation, grant signing in the dispatcher, or automatic retry.
- Principal comes from the authenticated peer and root-owned mapping, never request JSON. Store
  compares it with the live task owner and binds the event to the exact live lease, slot, attempt,
  epoch, run, manifest, generation, and request digest.
- Transient Store busy, integrity, and unknown errors stop delivery without advancing the cursor;
  only enumerated stale/revoked authority states are skipped.
- Schema migration is opt-in (`allow_schema_upgrade=false` by default). The schema-v6 migration has
  not been applied and requires independent database review plus separate authorization.
- `S2-DISPATCH-M01` remains MAJOR/OPEN because no production owner caller is integrated and no
  runtime acceptance has occurred. The latest GPT-PM decision does not authorize key provisioning,
  migration application, service activation, real dispatch, push/PR/merge, or deployment. Root
  configuration and fresh signed E5 remain absent/unproven. S3 remains unstarted.

## Review and verification

- Code-reviewer, GPT-6 Luna, medium effort: first found a MAJOR where Store errors were all treated
  as stale and could advance the replay cursor; the implementation was corrected to propagate
  transient, integrity, and unknown failures. The reviewer rechecked the branch and found no further
  actionable BLOCKER/MAJOR.
- Database-reviewer, GPT-6 Luna, medium effort: no actionable BLOCKER/MAJOR found. MINOR observation:
  grant lookup verifies/scans the append-only history and may cost more as the event log grows; no
  workload evidence is available.
- No tests or checks have run in the source-completion phase. Required focused tests are next and
  belong to `functional-test-reviewer` and `e2e-runner` after source coding is frozen.
- No database migration, WSL mutation, key/config provisioning, service start/enable, runtime
  dispatch, or E5 run was performed.

## Provenance and remaining work

At turn start, the worktree already contained the S2 source/document changes listed above (origin
not verified) and the untracked file `docs/sdlc/evidence/s2-functional-test-run.md`. That untracked
file was preserved and was not staged or edited. This turn fixed the missing `lease_id` projection
in grant-basis SQL, prevented cursor advancement on transient/systemic Store failures, added strict
RPC/receipt result validation, and corrected the S2 pub/sub decision and schema documentation.

Next: mapped functional/E2E tests; address findings; obtain exact-head specialist review and
GPT-PM gate; only then pursue separately authorized host configuration and real E5 evidence. Do
not start S3 before S2 closes.
