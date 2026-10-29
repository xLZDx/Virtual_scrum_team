# Change 0552: Fresh-only authenticated S2 assignment bootstrap

## State

Source implemented and disabled by default. No tests, build, provisioning, or
activation were performed in the coding pass. The implementer later reported one accidental
`git diff --check` invocation with no output; this was not independently reproduced and is not
functional/runtime evidence. The designated functional-test owner must run the
mapped rollback, replay, eligibility, stale-state, and budget regressions after the source batch
freezes; no test files were edited here.

## Contract

- The authenticated Supervisor RPC operation is bootstrap_assignment. Its only caller role is
  assignment_bootstrap, with exactly that operation. Kernel peer UID/GID, pidfd, and cgroup checks
  are inherited from the existing root Supervisor RPC boundary.
- Root policy is the only source for the allowed story/task/project/phase, canonical manifest
  digest and TestRun slot, owner principal, runner identity, owner/lease TTLs, policy digest, and
  maximum handoff lifetime. The configured runner_id maps directly to the Store lease worker_id
  and the handoff runner_id. The caller cannot supply those trusted fields.
- The exact bootstrap request contains schema, request_id, story_id, task_id, task_manifest,
  slot, attempt, and run_id. It must be a canonical valid TaskManifest, an exact root-policy tuple,
  and attempt 1. Extra or missing request fields fail closed.
- The operation key is SHA-256 over the domain-separated canonical tuple of policy digest,
  task_id, story_id, task-manifest digest, and request_id. The idempotency payload is the canonical
  request, kernel-mapped bootstrap peer, and policy digest. Exact replay returns the exact stored
  result; conflicting operation or payload refuses.
- One Store.execute_idempotent transaction creates a previously absent story and task, seeds the
  exact manifest cost budget, advances the new story from epoch 1 to epoch 2, claims attempt 1 and
  one free Store slot, writes the handoff, then writes the immutable operation row and linked
  supervisor event. A pre-commit verifier rechecks event/table integrity, policy digest, current
  generation, consumed probe, owner, lease, and handoff on the same transaction connection. Any
  failed check rolls back the entire transaction.
- Fresh eligibility requires no story/task row, relevant event history, lease, receipt, budget row,
  terminal marker, prior handoff, or noninitial attempt. It does not adopt, resume, retry, renew,
  or switch an assignment. Public Store methods retain their own transaction boundaries and the
  legacy acquire_lease commit-before-raise behavior.

## Changed paths

- tools/vst/assignment_basis.py: exact policy and request schemas, project/phase tuple fields,
  bounded integer TTL validation, operation and payload identity formulas.
- tools/vst/store.py: connection-taking story/task helpers, the fresh-only lease helper, atomic
  bootstrap effect and pre-commit verification; existing public APIs retain their wrappers.
- tools/vst/supervisor.py: fail-closed method deriving policy, current run and generation and
  checking the authenticated peer.
- tools/vst/supervisor_service.py: optional root-pinned assignment_bootstrap role and its single
  RPC route; existing configs do not enable it.

## Explicit limits

- A root policy and assignment_bootstrap role are not installed or activated by this source.
- The delegated_issuer can be configured separately and remains limited to assignment_basis.
- No producer outside the root Supervisor, signing, private key, dispatch instruction, database
  migration, E5 evidence, service activation, or production authority was added.
- The root policy supports whole-policy revocation by removal or digest replacement; individual
  assignment revocation requires replacing the entire pinned policy.
- Store cost_cap is preserved exactly, including zero-cost assignments with spent = 0. Fresh
  lease eligibility uses the existing spent > cap and retry-count rules; it does not introduce a
  spent >= cap check or alter the public acquire_lease semantics.

## Verification

- Tests/checks/build: NOT_RUN by instruction; functional-test-reviewer owns mapped test authoring
  and execution after coding freeze.
- Runtime acceptance: NOT_RUN. A root policy and authenticated peer are not installed.
- This coding pass did not create a commit. Commit `0552` is recorded by the subsequent
  coordination pass after the explicit source and record paths were staged.
